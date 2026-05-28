from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func

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
