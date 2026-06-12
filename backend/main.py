import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, text

from database import DialogueLog, Memory, NPC, Quest, Relationship, SessionLocal, init_db
from event_bus import EventBus
from memory_manager import MemoryManager
from perception import PerceptionEngine
from routers import analytics, dialogue, memory, npc, relationship
from routers import perception as perception_router
from routers import simulation as simulation_router
from simulation_engine import SimulationEngine
from world import WorldState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Shared instances
event_bus = EventBus()
memory_mgr = MemoryManager(
    stm_ttl=float(os.getenv("STM_TTL_SECONDS", "30")),
    stm_capacity=int(os.getenv("STM_CAPACITY", "20")),
)
world = WorldState()
perception_eng = PerceptionEngine(world=world)

engine = SimulationEngine(
    event_bus=event_bus,
    memory_manager=memory_mgr,
    tick_interval_ms=int(os.getenv("TICK_INTERVAL_MS", "200")),
    world=world,
    perception_engine=perception_eng,
)

# Cross-wire: perception engine needs reference to sim engine for enqueuing events
perception_eng.set_sim_engine(engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    
    # Auto-seed if database is empty
    from database import SessionLocal, NPC
    from seed import seed
    db = SessionLocal()
    try:
        if db.query(NPC).count() == 0:
            logger.info("Database is empty. Running initial seed...")
            seed()
    finally:
        db.close()

    simulation_router.set_engine(engine, event_bus, memory_mgr)
    perception_router.set_perception(world, perception_eng, engine)
    logger.info("SentientNPC backend ready (tick_interval=%dms)", int(engine.tick_interval * 1000))
    yield
    # Shutdown
    if engine.running:
        await engine.stop()
    logger.info("SentientNPC backend shutting down")


app = FastAPI(title="SentientNPC Backend", lifespan=lifespan)

_cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(npc.router, prefix="/npc")
app.include_router(memory.router, prefix="/memory")
app.include_router(relationship.router, prefix="/relationship")
app.include_router(dialogue.router, prefix="/dialogue")
app.include_router(analytics.router, prefix="/analytics")
app.include_router(simulation_router.router, prefix="/simulation")
app.include_router(perception_router.router, prefix="/perception")


@app.get("/health")
def health():
    db = SessionLocal()
    try:
        return {
            "status": "ok",
            "simulation_running": engine.running,
            "simulation_tick": engine.tick_count,
            "world_entities": world.entity_count,
            "table_counts": {
                "npc": db.query(func.count(NPC.id)).scalar() or 0,
                "memory": db.query(func.count(Memory.id)).scalar() or 0,
                "relationship": db.query(func.count(Relationship.player_id)).scalar() or 0,
                "quest": db.query(func.count(Quest.id)).scalar() or 0,
                "dialogue_log": db.query(func.count(DialogueLog.id)).scalar() or 0,
            },
            "server_timestamp": datetime.now(timezone.utc).isoformat(),
        }
    finally:
        db.close()


@app.get("/ready")
def readiness():
    """Readiness probe: verifies DB access and optionally checks Ollama if enabled.

    Set environment variable `CHECK_OLLAMA=1` to enable a quick Ollama POST check to
    `OLLAMA_URL` (defaults to http://localhost:11434/api/generate).
    """
    import httpx

    # Check database
    db = SessionLocal()
    try:
        # lightweight DB check
        db.execute(text("SELECT 1"))
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
