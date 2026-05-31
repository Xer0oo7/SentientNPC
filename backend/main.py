from datetime import datetime
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
import httpx

from database import DialogueLog, Memory, NPC, Quest, Relationship, SessionLocal, init_db
from routers import analytics, dialogue, memory, npc, relationship


app = FastAPI(title="SentientNPC Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


app.include_router(npc.router, prefix="/npc")
app.include_router(memory.router, prefix="/memory")
app.include_router(relationship.router, prefix="/relationship")
app.include_router(dialogue.router, prefix="/dialogue")
app.include_router(analytics.router, prefix="/analytics")


@app.get("/health")
def health():
    db = SessionLocal()
    try:
        return {
            "status": "ok",
            "table_counts": {
                "npc": db.query(func.count(NPC.id)).scalar() or 0,
                "memory": db.query(func.count(Memory.id)).scalar() or 0,
                "relationship": db.query(func.count(Relationship.player_id)).scalar() or 0,
                "quest": db.query(func.count(Quest.id)).scalar() or 0,
                "dialogue_log": db.query(func.count(DialogueLog.id)).scalar() or 0,
            },
            "server_timestamp": datetime.utcnow().isoformat(),
        }
    finally:
        db.close()


@app.get("/ready")
def readiness():
    """Readiness probe: verifies DB access and optionally checks Ollama if enabled.

    Set environment variable `CHECK_OLLAMA=1` to enable a quick Ollama POST check to
    `OLLAMA_URL` (defaults to http://localhost:11434/api/generate).
    """
    # Check database
    db = SessionLocal()
    try:
        # lightweight DB check
        db.execute("SELECT 1")
    except Exception as e:
        db.close()
        return {"ready": False, "db_error": str(e)}
    finally:
        try:
            db.close()
        except Exception:
            pass

    # Optionally check Ollama (short timeout)
    if os.getenv("CHECK_OLLAMA", "0") == "1":
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
        try:
            r = httpx.post(ollama_url, json={"model": "llama3", "prompt": "ping", "stream": False}, timeout=3.0)
            return {"ready": r.status_code == 200, "ollama_status": r.status_code}
        except Exception as e:
            return {"ready": False, "ollama_error": str(e)}

    return {"ready": True}
