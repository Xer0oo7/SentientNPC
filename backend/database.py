from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, mapped_column, relationship, sessionmaker


DATABASE_PATH = Path(__file__).resolve().parent / "sentient_npc.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class NPC(Base):
    __tablename__ = "npc"

    id = mapped_column(Text, primary_key=True)
    name = mapped_column(Text, nullable=False)
    personality = mapped_column(Text, nullable=False)
    emotion = mapped_column(Text, nullable=False, default="neutral")
    fsm_state = mapped_column(Text, nullable=False, default="idle")
    reputation = mapped_column(Float, nullable=False, default=0.0)
    created_at = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Spatial position (2D ground plane)
    pos_x = mapped_column(Float, nullable=False, default=0.0)
    pos_z = mapped_column(Float, nullable=False, default=0.0)
    facing_angle = mapped_column(Float, nullable=False, default=0.0)
    zone = mapped_column(Text, nullable=True, default=None)

    # Perception config
    vision_range = mapped_column(Float, nullable=False, default=20.0)
    vision_fov = mapped_column(Float, nullable=False, default=120.0)
    hearing_range = mapped_column(Float, nullable=False, default=30.0)

    memories = relationship("Memory", back_populates="npc", cascade="all, delete-orphan")
    relationships = relationship("Relationship", back_populates="npc", cascade="all, delete-orphan")
    quests = relationship("Quest", back_populates="npc", cascade="all, delete-orphan")
    dialogue_logs = relationship("DialogueLog", back_populates="npc", cascade="all, delete-orphan")


class Memory(Base):
    __tablename__ = "memory"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    npc_id = mapped_column(Text, ForeignKey("npc.id", ondelete="CASCADE"), nullable=False)
    event_type = mapped_column(Text, nullable=False)
    description = mapped_column(Text, nullable=False)
    location = mapped_column(Text, nullable=True)
    importance = mapped_column(Float, nullable=False)
    is_longterm = mapped_column(Boolean, nullable=False, default=False)
    timestamp = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    npc = relationship("NPC", back_populates="memories")


class Relationship(Base):
    __tablename__ = "relationship"

    npc_id = mapped_column(Text, ForeignKey("npc.id", ondelete="CASCADE"), primary_key=True)
    player_id = mapped_column(Text, primary_key=True)
    score = mapped_column(Float, nullable=False, default=0.0)
    updated_at = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    npc = relationship("NPC", back_populates="relationships")


class Quest(Base):
    __tablename__ = "quest"

    id = mapped_column(Text, primary_key=True)
    npc_id = mapped_column(Text, ForeignKey("npc.id", ondelete="CASCADE"), nullable=False)
    description = mapped_column(Text, nullable=False)
    reward = mapped_column(Text, nullable=False)
    difficulty = mapped_column(Float, nullable=False)
    status = mapped_column(Text, nullable=False, default="active")
    created_at = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    npc = relationship("NPC", back_populates="quests")


class DialogueLog(Base):
    __tablename__ = "dialogue_log"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    npc_id = mapped_column(Text, ForeignKey("npc.id", ondelete="CASCADE"), nullable=False)
    player_id = mapped_column(Text, nullable=False)
    player_message = mapped_column(Text, nullable=False)
    npc_response = mapped_column(Text, nullable=False)
    prompt = mapped_column(Text, nullable=False)
    timestamp = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    npc = relationship("NPC", back_populates="dialogue_logs")


class SimulationEvent(Base):
    __tablename__ = "simulation_event"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    tick = mapped_column(Integer, nullable=False)
    npc_id = mapped_column(Text, ForeignKey("npc.id", ondelete="CASCADE"), nullable=False)
    event_type = mapped_column(Text, nullable=False)
    priority = mapped_column(Integer, nullable=False)
    action_taken = mapped_column(Text, nullable=True)
    fsm_state = mapped_column(Text, nullable=False, default="idle")
    description = mapped_column(Text, nullable=False)
    timestamp = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    npc = relationship("NPC")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns added in Cycle 2 (Perception System) that need migration for existing DBs
_NPC_NEW_COLUMNS = [
    ("pos_x", "REAL DEFAULT 0.0"),
    ("pos_z", "REAL DEFAULT 0.0"),
    ("facing_angle", "REAL DEFAULT 0.0"),
    ("zone", "TEXT DEFAULT NULL"),
    ("fsm_state", "TEXT DEFAULT 'idle'"),
    ("vision_range", "REAL DEFAULT 20.0"),
    ("vision_fov", "REAL DEFAULT 120.0"),
    ("hearing_range", "REAL DEFAULT 30.0"),
]


_SIMULATION_EVENT_NEW_COLUMNS = [
    ("fsm_state", "TEXT DEFAULT 'idle'"),
]


def _migrate_npc_columns() -> None:
    """Idempotent migration: add new columns to existing NPC table."""
    import sqlite3
    conn = sqlite3.connect(str(DATABASE_PATH))
    cursor = conn.cursor()
    for col_name, col_def in _NPC_NEW_COLUMNS:
        try:
            cursor.execute(f"ALTER TABLE npc ADD COLUMN {col_name} {col_def}")
        except sqlite3.OperationalError:
            pass  # Column already exists
    conn.commit()
    conn.close()


def _migrate_simulation_event_columns() -> None:
    """Idempotent migration: add new columns to existing simulation_event table."""
    import sqlite3

    conn = sqlite3.connect(str(DATABASE_PATH))
    cursor = conn.cursor()
    for col_name, col_def in _SIMULATION_EVENT_NEW_COLUMNS:
        try:
            cursor.execute(f"ALTER TABLE simulation_event ADD COLUMN {col_name} {col_def}")
        except sqlite3.OperationalError:
            pass  # Column already exists
    conn.commit()
    conn.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    _migrate_npc_columns()
    _migrate_simulation_event_columns()


if __name__ == "__main__":
    init_db()
