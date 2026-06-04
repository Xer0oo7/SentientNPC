# SentientNPC — Features Log

> Code-level summary of what was built in each implementation cycle.

---

## Cycle 0 — Project Scaffold (Week 1) ✅

**Date:** Pre-existing  
**Status:** Complete

### What was built

Backend FastAPI server with SQLite persistence, React analytics dashboard with Vite, and seed data for 3 NPCs.

### Backend (`backend/`)

| File | What it does |
|------|-------------|
| `main.py` | FastAPI app entry point. Mounts 5 routers (`npc`, `memory`, `relationship`, `dialogue`, `analytics`). CORS enabled for all origins. `/health` returns table counts, `/ready` checks DB + optional Ollama. |
| `database.py` | SQLAlchemy ORM models: `NPC`, `Memory`, `Relationship`, `Quest`, `DialogueLog`. SQLite at `sentient_npc.db`. Foreign keys enabled via PRAGMA. |
| `models.py` | Pydantic schemas: `NPCCreate/Read`, `MemoryCreate/Read`, `RelationshipCreate/Read/WithLabel`, `QuestCreate/Read`, `DialogueRequest/Response/LogRead`, `EmotionUpdate`, `ReputationDelta`, `RelationshipDelta`, `PersonalitySchema` (6 traits, 0–100). |
| `seed.py` | Seeds 3 NPCs (`guard_01`, `merchant_01`, `elder_01`) with personalities, 3 memories each, and 1 relationship each to `player_001`. |
| `routers/npc.py` | CRUD for NPCs. `POST /npc/` creates, `GET /npc/` lists, `GET /npc/{id}` reads, `PATCH /npc/{id}/emotion` updates emotion (validates against 6 allowed states), `PATCH /npc/{id}/reputation` applies delta with clamping, `DELETE /npc/{id}` deletes. |
| `routers/memory.py` | `POST /memory/` creates memory (auto-promotes to longterm if importance ≥ 0.7). `GET /memory/{npc_id}` lists with filters (longterm_only, min_importance, event_type, limit). `DELETE /memory/{npc_id}/shortterm` purges short-term. `GET /memory/{npc_id}/summary` returns counts + avg importance. |
| `routers/relationship.py` | `POST /relationship/` upserts. `GET /relationship/{npc_id}/{player_id}` reads with label. `PATCH /relationship/{npc_id}/{player_id}` applies delta. `GET /relationship/{npc_id}` lists all. Labels: enemy (<-50), hostile (<0), neutral, friendly (>50), best_friend (100). |
| `routers/dialogue.py` | `POST /dialogue/{npc_id}` sends player message → builds LLM prompt with personality, emotion, relationship, top 5 memories → calls Ollama (llama3) → falls back to template if Ollama fails → logs to `dialogue_log`. `GET /dialogue/{npc_id}/history` returns last 20 entries. |
| `routers/analytics.py` | `GET /analytics/overview` returns all NPCs with memory/relationship counts. `GET /analytics/npc/{npc_id}` returns full NPC state: personality, memories, relationships with labels, recent dialogue. |

### Dashboard (`dashboard/`)

| File | What it does |
|------|-------------|
| `src/api/client.js` | Axios client pointing at `http://localhost:8000`. Exports: `getAllNPCs()`, `getNPC(id)`, `getMemories(npc_id)`, `getRelationships(npc_id)`, `getAnalyticsOverview()`, `getNPCAnalytics(id)`. |
| `src/App.jsx` | React Router with 2 routes: `/` → Overview, `/npc/:id` → NPCDetail. Header with "SentientNPC" branding. |
| `src/pages/Overview.jsx` | Fetches `/analytics/overview` every 5 seconds. Renders NPC cards in a grid: name, id, EmotionBadge, ReputationBar, memory count, relationship count. Each card links to detail page. |
| `src/pages/NPCDetail.jsx` | Fetches `/analytics/npc/{id}`. Shows: personality radar chart (Chart.js), reputation bar, emotion/memory/dialogue stats, memory log table with importance color-coding (red ≥ 0.7, yellow ≥ 0.4, gray), relationships list with labels, dialogue history. |
| `src/components/EmotionBadge.jsx` | Colored pill badge for emotion states: happy=green, angry=red, fearful=yellow, sad=blue, neutral=gray, excited=purple. |
| `src/components/ReputationBar.jsx` | Horizontal bar from -100 to +100 with center line. Green if >25, red if <-25, gray otherwise. |

### Infrastructure

| File | What it does |
|------|-------------|
| `docker-compose.yml` | Single `backend` service. Builds from `backend/Dockerfile`. Exposes port 8000. Mounts `./backend` as volume. Healthcheck on `/health`. |
| `backend/Dockerfile` | Python 3.11-slim, installs requirements, runs `uvicorn main:app --host 0.0.0.0 --port 8000`. |

### Data Flow (C# → Python → React)

```
Unity (C#)                    FastAPI (Python)              React Dashboard
──────────                    ───────────────              ───────────────
NPCController.cs              POST /npc/                   GET /analytics/overview
  → HTTP POST NPC data    →   Stores in SQLite         →   Polls every 5s, renders cards

MemorySystem.cs                POST /memory/                GET /analytics/npc/{id}
  → HTTP POST events      →   Writes Memory row       →   Shows memory table + charts

RelationshipSystem.cs          POST /relationship/          GET /relationship/{npc_id}
  → HTTP POST score delta  →  Upserts Relationship    →   Shows relationship list

DialogueEngine.cs              POST /dialogue/{npc_id}      GET /dialogue/{npc_id}/history
  → HTTP POST message      →  LLM prompt → response   →   Shows dialogue history
```

---

## Cycle 1 — Simulation Engine + Priority Queues + Memory System + Live Events (Week 2) ✅

**Date:** 2026-06-02  
**Status:** Complete

### What was built

Tick-based simulation engine with per-NPC min-heap priority queues, in-memory short-term memory with TTL expiry, WebSocket live event broadcasting, and a full dashboard simulation page.

### Backend — New Files

| File | What it does |
|------|-------------|
| `event_bus.py` | `EventBus` class manages WebSocket subscriber connections. `SimEvent` data class represents a processed simulation event with tick, NPC, priority, action, emotion shift. Defines priority constants (0=CRITICAL → 4=IDLE), `EVENT_IMPORTANCE` mapping (12 event types → importance scores 0.02–0.95), `EVENT_PRIORITY` mapping (event type → priority level). Broadcasts JSON to all subscribers, auto-removes dead connections. Keeps ring buffer of last 200 events for REST fallback. |
| `memory_manager.py` | `MemoryManager` class with `STMEntry` dataclass. STM is an in-memory dict of lists keyed by `npc_id`, TTL-based expiry (default 30s), capacity-limited (default 20 per NPC). `add_memory()` auto-promotes to SQLite long-term if importance ≥ 0.7. `expire_stm()` called each tick to garbage-collect. `query_recent()` merges STM + LTM results. `get_stm_snapshot()` returns serialized STM for dashboard display. |
| `simulation_engine.py` | `SimulationEngine` class with `QueuedEvent` dataclass (priority + sequence for FIFO tie-breaking). Per-NPC priority queues using Python `heapq` (min-heap). `ACTION_RULES` dict maps event types to personality-trait-weighted action decisions (e.g., `player_stole` + `aggressive≥60` → `chase`, else `alert_guard`). `EMOTION_RULES` dict maps events to emotion shifts. Each tick: `expire_stm()` → pop highest-priority event per NPC → `add_memory()` → `_determine_action()` using NPC personality from DB → `_determine_emotion_shift()` → update NPC emotion in DB → broadcast SimEvent via EventBus → persist to `simulation_event` audit table. Configurable via `TICK_INTERVAL_MS` env var (default 200ms). |
| `routers/simulation.py` | REST endpoints: `POST /simulation/start`, `POST /simulation/stop`, `GET /simulation/status` (tick count, running state, queue depths, STM counts, WS subscriber count), `POST /simulation/inject` (enqueue event with NPC ID, event type, description, optional priority/location/importance), `GET /simulation/events` (REST fallback for recent events), `GET /simulation/queues` (all NPC queue snapshots), `GET /simulation/queues/{npc_id}`, `GET /simulation/memory/{npc_id}` (STM snapshot). WebSocket endpoint: `WS /simulation/ws` for live event streaming. |

### Backend — Modified Files

| File | What changed |
|------|-------------|
| `database.py` | Added `SimulationEvent` ORM model (columns: id, tick, npc_id FK, event_type, priority, action_taken, description, timestamp). |
| `models.py` | Added `SimEventCreate` (npc_id, event_type, description, priority 0–4, location, importance 0–1), `SimEventRead` (id, tick, npc_id, event_type, priority, action_taken, description, timestamp), `SimStatusRead` (running, tick, tick_interval_ms, queue_depths dict, stm_counts dict, ws_subscribers). |
| `main.py` | Rewrote to use FastAPI `lifespan` context manager (replacing deprecated `@app.on_event`). Creates shared `EventBus`, `MemoryManager` (STM_TTL_SECONDS, STM_CAPACITY env vars), `SimulationEngine` (TICK_INTERVAL_MS env var) instances. Injects into simulation router via `set_engine()`. Mounts `/simulation` router. `/health` now returns `simulation_running` and `simulation_tick`. Graceful shutdown stops engine. |
| `requirements.txt` | Added `websockets==12.0` (already installed as 15.0.1 via FastAPI dependency). |

### Dashboard — New Files

| File | What it does |
|------|-------------|
| `components/EventFeed.jsx` | Real-time scrolling event feed. Connects to `ws://localhost:8000/simulation/ws`, loads recent history via REST on mount. Shows events newest-first with priority-colored dots (red=CRITICAL, orange=HIGH, yellow=MEDIUM, gray=LOW, stone=IDLE), NPC name, priority badge, tick number badge, description, event type, action taken, emotion shift arrows, memory created indicator. Slide-in animation on new events. Auto-reconnects on disconnect (2s delay). Connection status indicator (green/red dot). |
| `components/SimulationControls.jsx` | Engine control panel. Start/Stop buttons (disabled when inappropriate). Live-updating status display: running indicator (green pulsing dot), tick counter, interval, WS subscriber count. Per-NPC queue depth grid (auto-populated from status). Event injection form: NPC selector dropdown (populated from queue data), event type dropdown (10 event types with labels), description text input, Inject button. Success/error feedback with auto-clear. Refreshes every 1s. |
| `components/QueueVisualization.jsx` | Visual display of all NPC priority queues. Grid layout (responsive: 1/2/3 columns). Each NPC card shows queue depth badge and sorted event list with priority-colored dots and badges, event types, truncated descriptions. Refreshes every 1s. |
| `pages/Simulation.jsx` | New page assembling SimulationControls → QueueVisualization → EventFeed vertically. |

### Dashboard — Modified Files

| File | What changed |
|------|-------------|
| `api/client.js` | Added 8 functions: `startSimulation()`, `stopSimulation()`, `getSimulationStatus()`, `injectEvent(npcId, eventType, description, priority, location)`, `getRecentEvents(limit)`, `getAllQueueSnapshots()`, `getNPCQueueSnapshot(npcId)`, `getNPCSTMSnapshot(npcId)`, `createSimulationWebSocket()`. |
| `App.jsx` | Added `/simulation` route → `Simulation` page. Created `NavLink` component with active-state highlighting (teal when active). Added top-nav with "Overview" and "Simulation" links. |

### New API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/simulation/start` | Start the tick engine |
| POST | `/simulation/stop` | Stop the tick engine |
| GET | `/simulation/status` | Tick count, running state, queue depths, STM counts, WS count |
| POST | `/simulation/inject` | Inject event into NPC's priority queue |
| GET | `/simulation/events` | Recent processed events (REST fallback) |
| GET | `/simulation/queues` | All NPC queue snapshots |
| GET | `/simulation/queues/{npc_id}` | Single NPC queue snapshot |
| GET | `/simulation/memory/{npc_id}` | STM snapshot for an NPC |
| WS | `/simulation/ws` | Live event stream |

### How to test

```bash
# Terminal 1 — Backend
cd backend
python seed.py
uvicorn main:app --port 8000

# Terminal 2 — Dashboard
cd dashboard
npm run dev
# Open http://localhost:5173/simulation

# Terminal 3 — Test injection
curl -X POST http://localhost:8000/simulation/start
curl -X POST http://localhost:8000/simulation/inject \
  -H "Content-Type: application/json" \
  -d '{"npc_id":"guard_01","event_type":"player_stole","description":"Player stole bread from market stall"}'
curl http://localhost:8000/simulation/status
```

---

## Cycle 2 — Perception System (Vision + Hearing + Spatial World) ✅

**Date:** 2026-06-04  
**Status:** Complete

### What was built

2D spatial world model tracking entity positions and zones, NPC vision system (120° FOV cone, 20m range) with per-tick scanning, hearing system with distance-based intensity falloff, expansion from 3 to 7 NPCs placed in their village zones, new perception API endpoints, and a full dashboard perception page with an interactive 2D world map.

### Backend — New Files

| File | What it does |
|------|-------------|
| `world.py` | `WorldState` class managing 2D entity positions (x, z ground plane). `WorldEntity` dataclass with id, type, position, facing angle, zone. 6 named village zones (`guard_post`, `market_stall`, `town_square`, `tavern`, `church`, `smithy`) each with center coordinates and radius. Methods: `place_entity()`, `move_entity()`, `remove_entity()`, `get_entities_in_radius()`, `get_entities_in_zone()`, `distance()`, `is_in_fov()` (dot-product-based FOV cone check), `get_snapshot()` (full world state for dashboard). Auto-detects zone from position. |
| `perception.py` | `PerceptionEngine` class with vision scanning and hearing propagation. **Vision**: each tick, scans all NPC entities, checks FOV cone (configurable per NPC: range 1–100m, FOV 10–360°), generates `vision_spotted` events with 5-tick cooldown between re-detections of same target. **Hearing**: event-triggered via `propagate_sound()`, calculates distance-based intensity falloff (`intensity = loudness * (1 - dist/range)`), generates `sound_heard` events for all NPCs in range. `SOUND_EVENTS` mapping: 9 event types with loudness (0.1–1.0) and sound category. Per-NPC perception config stored in memory with DB defaults. Methods: `tick_perception()`, `propagate_sound()`, `get_npc_fov_data()`, `get_nearby_entities()`, `get_recent_perception_events()`. |
| `routers/perception.py` | 8 REST endpoints for spatial/perception control. `GET /perception/world` returns full world snapshot. `PATCH /perception/move/{id}` moves entity and syncs DB. `GET /perception/fov/{npc_id}` returns vision cone data. `GET /perception/nearby/{npc_id}` returns entities with visibility/hearing status. `POST /perception/sound` manually triggers sound propagation at position. `GET/PATCH /perception/config/{npc_id}` reads/updates perception config. `GET /perception/events` returns recent perception events. |

### Backend — Modified Files

| File | What changed |
|------|-------------|
| `database.py` | Added 7 columns to `NPC` table: `pos_x`, `pos_z` (Float, 2D position), `facing_angle` (Float, degrees), `zone` (Text), `vision_range` (Float, default 20.0), `vision_fov` (Float, default 120.0), `hearing_range` (Float, default 30.0). Idempotent `_migrate_npc_columns()` with `ALTER TABLE` + try/except for existing DBs. Called from `init_db()`. |
| `models.py` | Added spatial fields to `NPCCreate` and `NPCRead`: `pos_x`, `pos_z`, `facing_angle`, `zone`, `vision_range`, `vision_fov`, `hearing_range`. New schemas: `PositionUpdate` (x, z, facing_angle, zone), `SoundTrigger` (x, z, sound_type, loudness), `PerceptionConfigUpdate` (vision_range, vision_fov, hearing_range). |
| `event_bus.py` | Added 4 perception event types: `vision_spotted` (importance 0.4, MEDIUM priority), `sound_heard` (0.5, HIGH), `entity_entered_zone` (0.3, LOW), `entity_left_zone` (0.2, IDLE). |
| `simulation_engine.py` | Constructor now accepts `world` and `perception_engine` parameters. `_init_world_entities()` loads NPC positions and perception configs from DB into WorldState on simulation start, places player at town square. Each tick now calls `perception_engine.tick_perception()` for vision scanning. Event processing calls `propagate_sound()` for sound-producing events. Added `vision_spotted` and `sound_heard` to ACTION_RULES (personality-weighted: aggressive NPCs watch closely, curious ones investigate sounds) and EMOTION_RULES. |
| `seed.py` | Expanded from 3 to 7 NPCs: Aldric (guard, guard_post), Hilda (merchant, market_stall), Elder Morvyn (elder, town_square), Tormund (blacksmith, smithy), Berta (innkeeper, tavern), Pip (beggar, town_square), Father Aldwin (priest, church). Each with position, facing angle, zone, customized perception config, and personality. 17 total memories, 7 relationships. Player entity at (0,0) town_square. |
| `main.py` | Creates `WorldState` and `PerceptionEngine` instances, cross-wires perception↔simulation references. Mounts `/perception` router. `/health` now returns `world_entities` count. |
| `routers/simulation.py` | `/simulation/status` now returns `world_entities` count and `perception_events_recent` count. |

### Dashboard — New Files

| File | What it does |
|------|-------------|
| `components/WorldMap.jsx` | Canvas-based 2D world map renderer. Draws dark background with grid, zone regions as color-coded dashed circles with labels, entity markers as colored dots (teal=NPC, rose=player) with facing direction arrows, FOV cones as radial gradient arcs for selected NPC, hearing radius as dashed circles, sound ripple animations. High-DPI (devicePixelRatio) support. Click-to-select entities, click-to-move player. Legend overlay. Responsive sizing via ResizeObserver. |
| `components/PerceptionPanel.jsx` | Side panel showing selected NPC's perception config (vision range, FOV, hearing range) as colored stat cards, nearby entities list with distance and vision/hearing badges, and scrollable perception event feed with type-colored dots and icons (👁 vision, 👂 hearing). |
| `pages/Perception.jsx` | Full perception page. Auto-refreshes world state (800ms), perception events (1s), and selected NPC's FOV/nearby data (1s). Sound trigger control with dropdown (combat, explosion, speech, stealth, alert, ambient) triggers sound at player position with animated ripple effect. 2-column layout: WorldMap (left) + PerceptionPanel (right). Success/error feedback toasts. Entity count summary bar. |

### Dashboard — Modified Files

| File | What changed |
|------|-------------|
| `api/client.js` | Added 8 functions: `getWorldSnapshot()`, `moveEntity(id, x, z, facing, zone)`, `getNPCFOV(npcId)`, `getNearbyEntities(npcId)`, `triggerSound(x, z, type, loudness)`, `getPerceptionConfig(npcId)`, `updatePerceptionConfig(npcId, config)`, `getRecentPerceptionEvents(limit)`. |
| `App.jsx` | Added `/perception` route → `Perception` page. Added "Perception" nav link. |

### New API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/perception/world` | Full world state snapshot (all entities + zones) |
| PATCH | `/perception/move/{entity_id}` | Move entity to new position |
| GET | `/perception/fov/{npc_id}` | Vision cone data for an NPC |
| GET | `/perception/nearby/{npc_id}` | Entities in perception range with visibility status |
| POST | `/perception/sound` | Trigger sound at position, propagate to NPCs |
| GET | `/perception/config/{npc_id}` | Get NPC perception config |
| PATCH | `/perception/config/{npc_id}` | Update NPC perception config |
| GET | `/perception/events` | Recent perception events (newest first) |

### How to test

```bash
# Terminal 1 — Backend
cd backend
python seed.py
uvicorn main:app --port 8000

# Terminal 2 — Dashboard
cd dashboard
npm run dev
# Open http://localhost:5173/perception

# Terminal 3 — Test perception
curl -X POST http://localhost:8000/simulation/start

# Check world state
curl http://localhost:8000/perception/world

# Move player near beggar (beggar faces south at 180°, so player south of beggar is visible)
curl -X PATCH http://localhost:8000/perception/move/player_001 \
  -H "Content-Type: application/json" \
  -d '{"x": 5, "z": -5}'

# Wait 2 seconds, then check vision events
curl http://localhost:8000/perception/events?limit=5

# Check what beggar can see
curl http://localhost:8000/perception/nearby/beggar_01

# Trigger a loud sound at market
curl -X POST http://localhost:8000/perception/sound \
  -H "Content-Type: application/json" \
  -d '{"x": 30, "z": 30, "sound_type": "combat", "loudness": 1.0}'
```

---

