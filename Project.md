## Module Reference
 
### Module 1 — Perception System
The NPC's senses. Determines what the NPC can see and hear at any given moment, and fires events into the memory pipeline.
 
**Vision**
- Field of View: 120° cone, 20m range
- Implemented via Physics raycasting in the simulation environment
- Detects: Player, enemies, objects of interest
**Hearing**
- Detects: gunshots, footsteps, explosions
- Uses distance-based intensity falloff
- Stores: sound type, position, intensity
**Event Detection**
Events auto-fire on simulation actions and are immediately stored in memory:
| Event | Importance |
|---|---|
| `player_stole` | 0.8 |
| `player_attacked_ally` | 0.9 |
| `player_helped_npc` | 0.7 |
| `player_completed_quest` | 0.6 |
| `player_said_hello` | 0.1 |
 
---
 
### Module 2 — Memory System
The most important module. Gives NPCs the ability to recall past events and use them to drive future behaviour.
 
**Short-Term Memory**
- In-memory cache (C# Dictionary)
- Stores recent sightings, sounds, conversations
- Auto-expires after a configurable TTL (default: 30 seconds)
**Long-Term Memory**
- Persisted to SQLite via FastAPI
- Never forgotten
- Queryable by event type, importance threshold, time range
**Memory Object Schema**
```json
{
  "id": 42,
  "npc_id": "guard_01",
  "event_type": "player_stole",
  "description": "Player stole bread from market stall",
  "location": "market_district",
  "importance": 0.8,
  "is_longterm": true,
  "timestamp": "2025-06-01T14:32:00"
}
```
 
**Importance Scale**
```
0.1  ──── irrelevant (ambient, forgotten quickly)
0.3  ──── minor (noted, low influence)
0.5  ──── moderate (affects short-term behaviour)
0.7  ──── significant (affects long-term attitude)
0.9  ──── critical (permanent relationship shift)
1.0  ──── life-changing (never forgotten, always referenced)
```
 
---
 
### Module 3 — Personality System
Every NPC is defined by a personality profile stored as a ScriptableObject. Trait values (0–100) influence every downstream decision.
 
```json
{
  "aggressive": 80,
  "friendly": 20,
  "greedy": 60,
  "bravery": 90,
  "curiosity": 40,
  "loyalty": 75
}
```
 
**How traits affect behaviour**
| Trait | High Value Effect | Low Value Effect |
|---|---|---|
| Aggressive | Attacks sooner, shorter forgiveness window | Avoids conflict, prefers dialogue |
| Friendly | Forgives player actions, offers help | Stays neutral, minimal interaction |
| Greedy | Raises prices, demands payment | Fair pricing, generous rewards |
| Bravery | Holds position under threat | Flees at first sign of danger |
 
---
 
### Module 4 — Relationship System
Each NPC tracks a per-player relationship score from −100 to +100.
 
```
-100  ┤ ENEMY        — refuses service, calls guards, attacks on sight
 -50  ┤ Hostile      — short dialogue, raised prices
   0  ┤ NEUTRAL      — standard behaviour
 +50  ┤ Friendly     — helpful, shares rumours
+100  ┤ BEST FRIEND  — discounts, secret quests, protects player
```
 
**Score modifiers**
| Player Action | Score Delta |
|---|---|
| Give gift | +10 |
| Complete quest | +20 |
| Defend NPC in combat | +25 |
| Steal from NPC | −30 |
| Attack NPC | −50 |
| Kill NPC's ally | −40 |
 
---
 
### Module 5 — Reputation System
A global score per region/faction. NPCs within the same faction share reputation data.
 
```
+100  Hero      — guards greet you, merchants offer deals
   0  Neutral   — standard NPC behaviour
-100  Criminal  — guards attack on sight, merchants refuse service
```
 
---
 
### Module 6 — Decision Engine
The NPC's brain. Two-tier system: FSM for state management, Behaviour Trees for complex decision logic.
 
**Finite State Machine (FSM)**
```
States: Idle → Patrol → Investigate → Chase → Attack → Flee → Talk → Trade → Sleep
 
Transition examples:
  Idle       + player_visible(hostile)  → Chase
  Patrol     + sound_detected           → Investigate
  Investigate + player_found            → Chase or Talk (based on relationship)
  Chase      + bravery < 30             → Flee
  Talk       + conversation_ended       → Idle
```
 
**Behaviour Tree**
The Behaviour Tree runs inside each FSM state for fine-grained decisions. Uses Selector and Sequence nodes, driving actions based on memory queries and personality scores.
 
---
 
### Module 7 — GOAP (Goal Oriented Action Planning)
NPCs generate their own action sequences to satisfy goals. This is the standout technical feature of the framework.
 
**How it works**
1. NPC has a set of goals (e.g. `EatFood`, `ReportCrime`, `SeekShelter`)
2. Each goal has a world-state precondition and a cost
3. GOAP planner runs A* search over action graph to find cheapest plan
4. NPC executes plan step-by-step; replans if world state changes
**Example goal chain**
```
Goal: EatFood
  ├── Action: FindFoodSource   (precondition: none)
  ├── Action: BuyFood          (precondition: has_gold)
  │     OR
  ├── Action: StealFood        (precondition: player_not_watching, aggressive > 60)
  └── Action: EatFood          (precondition: has_food)
```
 
---
 
### Module 8 — Dialogue Engine
Two-tier system: template fallback + LLM generation.
 
**Template system** (always available, no latency)
```
relationship > 50  → "Good to see you, friend."
relationship < -50 → "Get out of my sight."
memory contains player_stole → "I know what you did at the market."
emotion == angry → "Now's not a good time. Leave me alone."
```
 
**LLM system** (Ollama, runs locally)
Prompt structure injected into Llama 3:
```
System: You are {npc_name}, a {npc_role} in a medieval fantasy world.
 
Personality: aggressive={x}, friendly={y}, greedy={z}
Relationship with player: {score}/100
Current emotion: {emotion_state}
Recent memories:
  - {memory_1}
  - {memory_2}
 
Generate a single natural response to the player greeting you.
Stay in character. Keep it under 2 sentences.
```
 
---
 
### Module 9 — Emotional System
NPCs have a current emotional state that shifts based on events.
 
**States:** `Happy`, `Sad`, `Angry`, `Fearful`, `Neutral`, `Excited`
 
**Event → emotion mapping**
| Event | Emotion shift |
|---|---|
| Ally died | Sadness +70, Anger +40 |
| Quest completed | Happy +50 |
| Player attacked NPC | Angry +80, Fearful +30 |
| Gift received | Happy +30 |
| Threat detected | Fearful +60 |
 
Emotion state directly modifies dialogue tone and decision thresholds.
 
---
 
### Module 10 — Analytics Dashboard
A React web application that shows every NPC's internal state in real time.
 
**Features**
- NPC selector with live status indicators
- Memory log with importance heatmap
- Relationship score timeline (Chart.js)
- Emotion state donut chart
- Reputation by region
- Live event feed (WebSocket)
**Tech stack:** React 18, Supabase (or local FastAPI WebSocket), Chart.js, Tailwind CSS
 
---
 
## Technology Stack
 
| Layer | Technology |
|---|---|
| Simulation Engine | Unity 2022.3 LTS |
| Scripting Language | C# |
| AI Backend | Python 3.11 + FastAPI |
| Database | SQLite (via SQLAlchemy) |
| LLM Runtime | Ollama (Llama 3 / Mistral / Gemma) |
| Dashboard | React 18 + Chart.js |
| Pathfinding | Unity NavMesh |
| Version Control | Git + GitHub |
 
---
 
## Project Structure
 
```
SentientNPC/
├── SimulationProject/
│   └── Assets/
│       └── _Project/
│           ├── Scripts/
│           │   ├── NPC/
│           │   │   ├── Core/           NPCController.cs, NPCData.cs
│           │   │   ├── Perception/     VisionSystem.cs, HearingSystem.cs
│           │   │   ├── Memory/         MemorySystem.cs, MemoryEvent.cs
│           │   │   ├── Personality/    PersonalityProfile.cs
│           │   │   ├── Relationship/   RelationshipSystem.cs
│           │   │   ├── Emotion/        EmotionSystem.cs
│           │   │   ├── Decision/       FSM.cs, BehaviourTree.cs, GOAP.cs
│           │   │   └── Dialogue/       DialogueEngine.cs, LLMClient.cs
│           │   ├── SimAgent/           SimAgentController.cs, SimAgentEvents.cs
│           │   ├── Backend/            APIClient.cs, DatabaseSync.cs
│           │   └── UI/                 DebugOverlay.cs, DialogueUI.cs
│           ├── Prefabs/
│           ├── ScriptableObjects/
│           └── Scenes/
│               └── SimSandbox.unity
│
├── backend/
│   ├── main.py                 FastAPI app entry point
│   ├── database.py             SQLite init + connection
│   ├── models.py               Pydantic models
│   ├── routers/
│   │   ├── memory.py           Memory CRUD endpoints
│   │   ├── npc.py              NPC data endpoints
│   │   └── dialogue.py         LLM dialogue endpoint
│   └── requirements.txt
│
├── dashboard/                  React analytics app
│   ├── src/
│   │   ├── components/
│   │   └── pages/
│   └── package.json
│
└── README.md
```
 
---
 
## Getting Started
 
### Prerequisites
 
- Unity Hub + Unity 2022.3 LTS
- Python 3.11+
- Node.js 18+ (for dashboard)
- [Ollama](https://ollama.ai) installed locally
### 1. Clone the repo
 
```bash
git clone https://github.com/YOURUSERNAME/SentientNPC.git
cd SentientNPC
```
 
### 2. Start the backend
 
```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python database.py               # initialises SQLite tables
uvicorn main:app --reload --port 8000
```
 
Verify: open `http://localhost:8000/health` → should return `{"status":"ok"}`
 
### 3. Pull a local LLM
 
```bash
ollama pull llama3
ollama serve                     # starts on localhost:11434
```
 
### 4. Open in Unity
 
- Open Unity Hub → Add project → select `SimulationProject/`
- Open scene: `Assets/_Project/Scenes/SimSandbox.unity`
- Hit Play — NPC agents should initialise and log to Console
### 5. Start the dashboard
 
```bash
cd dashboard
npm install
npm run dev                      # opens on localhost:5173
```
 
---
 
## Development Roadmap
 
| Week | Module | Status |
|---|---|---|
| 1 | Project scaffold, folder structure, FastAPI + SQLite setup | ✅ Complete |
| 2 | Memory System (short-term + long-term + importance scoring) | 🔲 Next |
| 3 | Perception System (vision FOV, hearing, event detection) | 🔲 Planned |
| 4 | Personality + Relationship + Emotion systems | 🔲 Planned |
| 5 | FSM + Behaviour Tree decision engine | 🔲 Planned |
| 6 | GOAP planner | 🔲 Planned |
| 7 | LLM dialogue (Ollama integration) | 🔲 Planned |
| 8 | Analytics dashboard + live WebSocket feed | 🔲 Planned |
| 9 | Sim stress testing (multi-NPC scenarios) + demo video | 🔲 Planned |
 
---
 
## Why This Project
 
> "Built a Unity game" is forgettable.  
> "Built a memory-driven autonomous NPC simulation framework with dynamic dialogue, relationship modelling, behaviour trees, GOAP planning, reputation systems, and local LLM integration" is not.
 
SentientNPC is a pure AI simulation — no game wrapper, no gameplay loop. It is designed to demonstrate systems-level thinking across autonomous agent AI, backend architecture, database design, and modern LLM integration — the exact combination that game AI and simulation engineering roles look for.
 
**GOAP** is used in shipped AAA titles (F.E.A.R., S.T.A.L.K.E.R.) and is a genuine signal of game AI knowledge. Most candidates have never implemented it.
 
**Local LLM dialogue** puts this project in conversation with companies like Inworld AI, Convai, and NVIDIA ACE — the frontier of real-time AI-driven characters.
 
**Simulation-first** means every module is testable, measurable, and visible through the analytics dashboard — no art, no level design, just pure AI systems running in a sandbox.

---