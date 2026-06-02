from datetime import datetime
from pathlib import Path

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, event
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
    reputation = mapped_column(Float, nullable=False, default=0.0)
    created_at = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

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
    timestamp = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    npc = relationship("NPC", back_populates="memories")


class Relationship(Base):
    __tablename__ = "relationship"

    npc_id = mapped_column(Text, ForeignKey("npc.id", ondelete="CASCADE"), primary_key=True)
    player_id = mapped_column(Text, primary_key=True)
    score = mapped_column(Float, nullable=False, default=0.0)
    updated_at = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    npc = relationship("NPC", back_populates="relationships")


class Quest(Base):
    __tablename__ = "quest"

    id = mapped_column(Text, primary_key=True)
    npc_id = mapped_column(Text, ForeignKey("npc.id", ondelete="CASCADE"), nullable=False)
    description = mapped_column(Text, nullable=False)
    reward = mapped_column(Text, nullable=False)
    difficulty = mapped_column(Float, nullable=False)
    status = mapped_column(Text, nullable=False, default="active")
    created_at = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    npc = relationship("NPC", back_populates="quests")


class DialogueLog(Base):
    __tablename__ = "dialogue_log"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    npc_id = mapped_column(Text, ForeignKey("npc.id", ondelete="CASCADE"), nullable=False)
    player_id = mapped_column(Text, nullable=False)
    player_message = mapped_column(Text, nullable=False)
    npc_response = mapped_column(Text, nullable=False)
    prompt = mapped_column(Text, nullable=False)
    timestamp = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    npc = relationship("NPC", back_populates="dialogue_logs")


class SimulationEvent(Base):
    __tablename__ = "simulation_event"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    tick = mapped_column(Integer, nullable=False)
    npc_id = mapped_column(Text, ForeignKey("npc.id", ondelete="CASCADE"), nullable=False)
    event_type = mapped_column(Text, nullable=False)
    priority = mapped_column(Integer, nullable=False)
    action_taken = mapped_column(Text, nullable=True)
    description = mapped_column(Text, nullable=False)
    timestamp = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    npc = relationship("NPC")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print(f"SQLite tables initialised at {DATABASE_PATH}")
