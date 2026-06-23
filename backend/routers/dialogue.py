import json
import logging
import os
import re

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import DialogueLog, Memory, NPC, Relationship, get_db
from models import DialogueLogRead, DialogueRequest, DialogueResponse
from routers.relationship import clamp, relationship_label


logger = logging.getLogger(__name__)
router = APIRouter(tags=["dialogue"])

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi3")

# ── Keyword-based fallback sentiment analysis ─────────────────────────────────
# Used when Ollama is unavailable to still shift relationship scores.

NEGATIVE_KEYWORDS = {
    # Insults & hostility
    "fuck", "shit", "damn", "hate", "die", "kill", "idiot", "stupid",
    "ugly", "worthless", "useless", "pathetic", "loser", "scum",
    "bastard", "ass", "bitch", "moron", "fool", "coward", "liar",
    "thief", "cheat", "betray", "trash", "disgusting", "terrible",
    "awful", "worst", "dumb", "shut up", "go away", "leave me",
    "threaten", "threat", "punch", "fight", "attack", "rob", "steal",
}

POSITIVE_KEYWORDS = {
    # Kindness & respect
    "hello", "hi", "thanks", "thank", "please", "help", "friend",
    "love", "appreciate", "kind", "good", "great", "wonderful",
    "amazing", "beautiful", "brave", "hero", "gift", "give",
    "share", "generous", "noble", "protect", "bless", "honor",
    "respect", "praise", "admire", "sorry", "forgive", "welcome",
    "nice", "sweet", "gentle", "loyal", "trust", "care",
}

# How personality modifies the NPC's sensitivity to positive/negative speech.
# Format: (trait_name, threshold, positive_multiplier, negative_multiplier)
# Example: an aggressive NPC (aggressive >= 60) reacts MORE harshly to insults
# and is LESS moved by kind words.
PERSONALITY_SENSITIVITY = [
    ("aggressive", 60, 0.7, 1.5),   # aggressive NPCs punish rudeness harder
    ("friendly", 60, 1.4, 0.7),     # friendly NPCs reward kindness more
    ("greedy", 60, 0.8, 1.0),       # greedy NPCs are less moved by flattery
    ("bravery", 70, 1.0, 0.8),      # brave NPCs shrug off threats somewhat
    ("loyalty", 70, 1.3, 1.2),      # loyal NPCs react strongly to both
]


def analyze_sentiment_keywords(message: str, personality: dict) -> int:
    """Estimate a relationship delta (-10 to +10) from keyword matching.

    The raw score is modified by the NPC's personality traits so that
    e.g. an aggressive NPC reacts more harshly to insults.
    """
    words = set(re.findall(r'[a-z]+', message.lower()))

    pos_hits = len(words & POSITIVE_KEYWORDS)
    neg_hits = len(words & NEGATIVE_KEYWORDS)

    if pos_hits == 0 and neg_hits == 0:
        return 0  # neutral message, no shift

    # Raw delta: each positive word = +2, each negative word = -3
    raw = (pos_hits * 2) - (neg_hits * 3)

    # Apply personality multipliers
    pos_mult = 1.0
    neg_mult = 1.0
    for trait, threshold, p_mult, n_mult in PERSONALITY_SENSITIVITY:
        if personality.get(trait, 50) >= threshold:
            pos_mult *= p_mult
            neg_mult *= n_mult

    if raw >= 0:
        adjusted = raw * pos_mult
    else:
        adjusted = raw * neg_mult

    # Clamp to [-10, +10]
    return max(-10, min(10, int(round(adjusted))))


def determine_emotion_from_sentiment(delta: int, current_emotion: str) -> str:
    """Optionally shift the NPC's emotion based on how the conversation is going."""
    if delta <= -5:
        return "angry"
    if delta <= -2:
        # Mildly negative — might make them fearful or annoyed
        if current_emotion == "happy":
            return "neutral"
        return current_emotion
    if delta >= 5:
        return "happy"
    if delta >= 2:
        if current_emotion in ("angry", "fearful", "sad"):
            return "neutral"
    return current_emotion


def npc_role_from_name(name: str) -> str:
    return name.strip().lower().replace("_", " ") or "npc"


def fallback_response(
    label: str, emotion: str, delta: int = 0
) -> str:
    """Template response when Ollama is unavailable.

    Now also considers the sentiment delta — if the player was rude,
    the NPC responds accordingly even without the LLM.
    """
    # Strong negative sentiment overrides relationship-based templates
    if delta <= -5:
        return "Watch your tongue. I will not tolerate such disrespect."
    if delta <= -2:
        return "I did not care for that remark. Choose your words more carefully."

    if label == "best_friend":
        return "For you, my trusted friend, I will always spare a moment."
    if label == "friendly":
        return "Good to see you again. Speak freely, and I will listen."
    if label == "enemy":
        return "You are not welcome here. Say what you must and leave."
    if label == "hostile":
        return "I have not forgotten your choices. Make this quick."
    if emotion == "angry":
        return "Now is not the time to test my patience."
    if emotion == "fearful":
        return "Keep your voice low. These are uneasy times."
    if emotion == "happy":
        return "A fine day for conversation. What brings you to me?"
    return "I hear you. Tell me what you need."


def build_prompt(
    npc: NPC,
    relationship_score: float,
    label: str,
    memories: list[Memory],
    player_message: str,
) -> str:
    """Build the LLM prompt that asks for BOTH a response AND a relationship delta."""
    personality = json.loads(npc.personality)
    memory_lines = [
        f"- {memory.event_type}: {memory.description}"
        for memory in memories
    ]
    if not memory_lines:
        memory_lines = ["- No relevant memories."]
    return f"""You are {npc.name}, a {npc_role_from_name(npc.name)} in a medieval fantasy world.

Your personality traits (0-100 scale):
  aggressive={personality.get("aggressive", 0)}, friendly={personality.get("friendly", 0)}, greedy={personality.get("greedy", 0)}, bravery={personality.get("bravery", 0)}, curiosity={personality.get("curiosity", 0)}, loyalty={personality.get("loyalty", 0)}
Your current emotion: {npc.emotion}
Your relationship with this player: {relationship_score}/100 ({label})

Your most relevant memories of this player:
{chr(10).join(memory_lines)}

The player says: "{player_message}"

Instructions:
1. Decide how the player's message makes you feel given your personality. If they are rude, threatening, or disrespectful and that clashes with your personality, you should be upset. If they are kind and that aligns with your personality, you should warm up to them.
2. Rate how this message affects your relationship with the player as an integer from -10 (very negative) to +10 (very positive). Consider your personality: an aggressive character is more offended by insults, a friendly character is more warmed by kindness.
3. Respond in character. One to two sentences only. Do not break character. Do not describe actions.

You MUST respond in this exact JSON format and nothing else:
{{{{
  "response": "your in-character reply here",
  "relationship_delta": 0
}}}}"""


def parse_llm_json(raw: str) -> tuple[str, int]:
    """Extract response text and relationship_delta from the LLM's JSON output.

    Handles common LLM quirks like markdown fences, +N numbers, trailing text, etc.
    Returns (response_text, delta).
    """
    # Strip markdown code fences if present
    cleaned = raw.strip()
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    cleaned = cleaned.strip()

    # Fix common LLM JSON quirks BEFORE parsing:
    # 1. Replace +N with N (e.g. "+7" -> "7", "+10" -> "10")
    fixed = re.sub(r':\s*\+(\d+)', r': \1', cleaned)
    # 2. Remove trailing commas before closing braces
    fixed = re.sub(r',\s*}', '}', fixed)

    try:
        data = json.loads(fixed)
        response_text = str(data.get("response", "")).strip()
        delta = int(data.get("relationship_delta", 0))
        delta = max(-10, min(10, delta))  # clamp
        if response_text:
            return response_text, delta
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    # Fallback: try to find JSON object anywhere in the output
    json_match = re.search(r'\{[^{}]*"response"\s*:\s*"[^"]+?"[^{}]*\}', fixed, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            response_text = str(data.get("response", "")).strip()
            delta = int(data.get("relationship_delta", 0))
            delta = max(-10, min(10, delta))
            if response_text:
                return response_text, delta
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    # Try to extract just the "response" field with regex as last resort
    resp_match = re.search(r'"response"\s*:\s*"((?:[^"\\]|\\.*)*)?"', cleaned, re.DOTALL)
    delta_match = re.search(r'"relationship_delta"\s*:\s*[+\-]?(\d+)', cleaned)
    if resp_match:
        response_text = resp_match.group(1).strip()
        delta = 0
        if delta_match:
            sign_match = re.search(r'"relationship_delta"\s*:\s*([+\-]?\d+)', cleaned)
            if sign_match:
                delta = max(-10, min(10, int(sign_match.group(1))))
        if response_text:
            return response_text, delta

    # Last resort: treat the whole output as a plain text response, delta=0
    logger.warning("Could not parse LLM JSON, using raw text. Output: %s", raw[:200])
    return cleaned or "I have nothing to say.", 0


async def call_ollama(prompt: str) -> str:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
        )
        response.raise_for_status()
        data = response.json()
        return (data.get("response") or "").strip()


def _update_relationship(
    db: Session,
    npc_id: str,
    player_id: str,
    delta: int,
) -> float:
    """Apply a relationship delta and return the new score."""
    relationship = (
        db.query(Relationship)
        .filter(Relationship.npc_id == npc_id, Relationship.player_id == player_id)
        .first()
    )
    if relationship:
        relationship.score = clamp(relationship.score + delta)
        db.commit()
        db.refresh(relationship)
        return relationship.score
    else:
        # Create the relationship if it doesn't exist yet
        new_score = clamp(float(delta))
        new_rel = Relationship(
            npc_id=npc_id,
            player_id=player_id,
            score=new_score,
        )
        db.add(new_rel)
        db.commit()
        db.refresh(new_rel)
        return new_rel.score


@router.post("/{npc_id}", response_model=DialogueResponse)
async def dialogue(npc_id: str, payload: DialogueRequest, db: Session = Depends(get_db)):
    npc = db.get(NPC, npc_id)
    if not npc:
        raise HTTPException(status_code=404, detail="NPC not found")

    personality = json.loads(npc.personality)

    relationship = (
        db.query(Relationship)
        .filter(Relationship.npc_id == npc_id, Relationship.player_id == payload.player_id)
        .first()
    )
    relationship_score = relationship.score if relationship else 0.0
    label = relationship_label(relationship_score)
    memories = (
        db.query(Memory)
        .filter(Memory.npc_id == npc_id)
        .order_by(Memory.importance.desc(), Memory.timestamp.desc())
        .limit(5)
        .all()
    )
    prompt = build_prompt(npc, relationship_score, label, memories, payload.player_message)

    # --- Call LLM or fall back ---
    relationship_delta = 0
    used_llm = False

    try:
        raw_llm = await call_ollama(prompt)
        if raw_llm:
            npc_response, relationship_delta = parse_llm_json(raw_llm)
            used_llm = True
        else:
            relationship_delta = analyze_sentiment_keywords(payload.player_message, personality)
            npc_response = fallback_response(label, npc.emotion, relationship_delta)
    except httpx.HTTPError:
        relationship_delta = analyze_sentiment_keywords(payload.player_message, personality)
        npc_response = fallback_response(label, npc.emotion, relationship_delta)

    # If the LLM returned a delta of 0 but didn't seem to evaluate sentiment,
    # supplement with keyword analysis so conversations always have consequences
    if used_llm and relationship_delta == 0:
        keyword_delta = analyze_sentiment_keywords(payload.player_message, personality)
        # Only apply keyword delta if it's significant (±2 or more)
        if abs(keyword_delta) >= 2:
            relationship_delta = keyword_delta

    # --- Update relationship score ---
    new_score = relationship_score
    if relationship_delta != 0:
        new_score = _update_relationship(db, npc_id, payload.player_id, relationship_delta)
        logger.info(
            "Relationship %s↔%s shifted by %+d (%.1f → %.1f)",
            npc_id, payload.player_id, relationship_delta,
            relationship_score, new_score,
        )

    # --- Update NPC emotion based on conversation sentiment ---
    new_emotion = determine_emotion_from_sentiment(relationship_delta, npc.emotion)
    if new_emotion != npc.emotion:
        npc.emotion = new_emotion
        db.commit()
        logger.info("NPC %s emotion shifted to %s from conversation", npc_id, new_emotion)

    # --- Log the conversation ---
    log = DialogueLog(
        npc_id=npc_id,
        player_id=payload.player_id,
        player_message=payload.player_message,
        npc_response=npc_response,
        prompt=prompt,
    )
    db.add(log)
    db.commit()

    return {
        "npc_id": npc_id,
        "response": npc_response,
        "emotion": npc.emotion,
        "relationship_score": new_score,
        "relationship_delta": relationship_delta,
    }


@router.get("/{npc_id}/history", response_model=list[DialogueLogRead])
def dialogue_history(npc_id: str, db: Session = Depends(get_db)):
    if not db.get(NPC, npc_id):
        raise HTTPException(status_code=404, detail="NPC not found")
    return (
        db.query(DialogueLog)
        .filter(DialogueLog.npc_id == npc_id)
        .order_by(DialogueLog.timestamp.desc())
        .limit(20)
        .all()
    )
