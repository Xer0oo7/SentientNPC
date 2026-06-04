import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PersonalitySchema(BaseModel):
    aggressive: float = Field(default=0.0, ge=0, le=100)
    friendly: float = Field(default=0.0, ge=0, le=100)
    greedy: float = Field(default=0.0, ge=0, le=100)
    bravery: float = Field(default=0.0, ge=0, le=100)
    curiosity: float = Field(default=0.0, ge=0, le=100)
    loyalty: float = Field(default=0.0, ge=0, le=100)


class NPCCreate(BaseModel):
    id: str
    name: str
    personality: PersonalitySchema
    emotion: str = "neutral"
    reputation: float = Field(default=0.0, ge=-100, le=100)
    pos_x: float = 0.0
    pos_z: float = 0.0
    facing_angle: float = 0.0
    zone: Optional[str] = None
    vision_range: float = Field(default=20.0, ge=1, le=100)
    vision_fov: float = Field(default=120.0, ge=10, le=360)
    hearing_range: float = Field(default=30.0, ge=1, le=100)


class NPCRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    personality: PersonalitySchema
    emotion: str
    reputation: float
    created_at: datetime
    pos_x: float = 0.0
    pos_z: float = 0.0
    facing_angle: float = 0.0
    zone: Optional[str] = None
    vision_range: float = 20.0
    vision_fov: float = 120.0
    hearing_range: float = 30.0

    @field_validator("personality", mode="before")
    @classmethod
    def deserialize_personality(cls, value):
        if isinstance(value, str):
            return json.loads(value)
        return value


class MemoryCreate(BaseModel):
    npc_id: str
    event_type: str
    description: str
    location: Optional[str] = None
    importance: float = Field(ge=0, le=1)
    is_longterm: bool = False


class MemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    npc_id: str
    event_type: str
    description: str
    location: Optional[str]
    importance: float
    is_longterm: bool
    timestamp: datetime


class RelationshipCreate(BaseModel):
    npc_id: str
    player_id: str
    score: float = Field(default=0.0, ge=-100, le=100)


class RelationshipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    npc_id: str
    player_id: str
    score: float
    updated_at: datetime


class RelationshipWithLabel(RelationshipRead):
    label: str


class QuestCreate(BaseModel):
    id: str
    npc_id: str
    description: str
    reward: str
    difficulty: float = Field(ge=0, le=100)
    status: str = "active"


class QuestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    npc_id: str
    description: str
    reward: str
    difficulty: float
    status: str
    created_at: datetime


class EmotionUpdate(BaseModel):
    emotion: str


class ReputationDelta(BaseModel):
    delta: float


class RelationshipDelta(BaseModel):
    delta: float


class DialogueRequest(BaseModel):
    player_message: str
    player_id: str


class DialogueResponse(BaseModel):
    npc_id: str
    response: str
    emotion: str
    relationship_score: float


class DialogueLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    npc_id: str
    player_id: str
    player_message: str
    npc_response: str
    prompt: str
    timestamp: datetime


class SimEventCreate(BaseModel):
    npc_id: str
    event_type: str
    description: str
    priority: Optional[int] = Field(default=None, ge=0, le=4)
    location: Optional[str] = None
    importance: Optional[float] = Field(default=None, ge=0, le=1)


class SimEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tick: int
    npc_id: str
    event_type: str
    priority: int
    action_taken: Optional[str]
    description: str
    timestamp: datetime


class SimStatusRead(BaseModel):
    running: bool
    tick: int
    tick_interval_ms: int
    queue_depths: dict[str, int]
    stm_counts: dict[str, int]
    ws_subscribers: int


# ── Perception Models ─────────────────────────────────────────────────────────

class PositionUpdate(BaseModel):
    x: float
    z: float
    facing_angle: Optional[float] = None
    zone: Optional[str] = None


class SoundTrigger(BaseModel):
    x: float
    z: float
    sound_type: str
    loudness: float = Field(default=1.0, ge=0, le=1)


class PerceptionConfigUpdate(BaseModel):
    vision_range: Optional[float] = Field(default=None, ge=1, le=100)
    vision_fov: Optional[float] = Field(default=None, ge=10, le=360)
    hearing_range: Optional[float] = Field(default=None, ge=1, le=100)

