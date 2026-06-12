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

## Cycle 3 — Testing Infrastructure + Bug Fixes + Hardening (Week 3) ✅

**Date:** 2026-06-07  
**Status:** Complete

### What was built

Comprehensive pytest test suite covering core simulation logic, CI pipeline with automated test execution, critical bug fix in `_determine_action` rule evaluation, deprecation fixes across all datetime usage, memory-efficient ring buffers, event injection validation guards, configurable CORS origins, and environment variable documentation.

### Backend — New Files

| File | What it does |
|------|-------------|
| `conftest.py` | Pytest configuration. Adds `backend/` directory to `sys.path` so tests can import backend modules (e.g., `simulation_engine`, `memory_manager`, `world`) without package installation. |
| `tests/__init__.py` | Empty package marker enabling `python -m pytest tests/` discovery. |
| `tests/test_core.py` | 31 unit tests across 4 test classes covering core simulation logic without requiring a running server or database. **`TestDetermineAction`** (10 tests): verifies personality-driven action selection — unknown events return `"observe"`, high/low trait thresholds produce correct actions, multi-rule evaluation doesn't short-circuit, all known event types produce non-empty results. **`TestDetermineEmotionShift`** (6 tests): verifies emotion transitions — no shift for unknown events, attack→angry, help→happy, threat→fearful, highest-intensity emotion wins, no shift if already in target state. **`TestMemoryManager`** (5 tests): verifies STM without DB — low importance goes to STM, capacity enforced (oldest dropped), TTL expiry works, multi-NPC counts correct, auto-importance lookup from `EVENT_IMPORTANCE`. **`TestWorldState`** (16 tests): verifies spatial model — place/get/remove entities, distance calculation, radius queries with exclusion, type filtering, FOV cone (directly ahead, behind, edge, just outside, out of range), move entity, auto zone detection, zone queries, snapshot structure. |
| `.env.example` | Documents all configurable environment variables with comments: `TICK_INTERVAL_MS` (default 200), `STM_TTL_SECONDS` (default 30), `STM_CAPACITY` (default 20), `OLLAMA_URL`, `CHECK_OLLAMA`, `CORS_ORIGINS` (default `*`), `PYTHONUNBUFFERED`. |

---

## Cycle 4 — FSM Foundation + Decision Visibility (Week 4) ✅

**Date:** 2026-06-10  
**Status:** Complete

### What was built

Persistent finite-state machine support for each NPC, deterministic state transitions driven by event rules, a decision-state API for inspection, and dashboard visibility for the current FSM state and latest processed decision.

### Backend — New Files

| File | What it does |
|------|-------------|
| `fsm.py` | Defines the NPC FSM state set, initial-state selection, deterministic transition rules, and state-based fallback actions. |
| `tests/test_fsm.py` | Unit tests for state normalization, initial-state derivation, event-driven transitions, and state-driven action fallbacks. |

### Backend — Modified Files

| File | What changed |
|------|-------------|
| `database.py` | Added persistent `fsm_state` storage to `NPC` and `simulation_event`, plus idempotent migration helpers for existing SQLite databases. |
| `models.py` | Added `fsm_state` to NPC create/read schemas, `fsm_state` to simulation event read schema, and `DecisionStateRead` for the new inspection endpoint. |
| `seed.py` | Seeds each NPC with an initial FSM state derived from zone and emotion. |
| `simulation_engine.py` | Loads NPC FSM state on each processed event, updates state transitions per tick, and includes the resulting state in processed simulation events. |
| `routers/simulation.py` | Added `GET /simulation/state/{npc_id}` to expose the current FSM state, last processed event, and available state set. |
| `routers/analytics.py` | Includes `fsm_state` and last decision metadata in NPC analytics and overview responses. |
| `routers/npc.py` | New NPCs are created with a sensible initial FSM state when one is not provided. |
| `perception.py` | Fixed recent perception history access so `/simulation/status` can safely report perception event counts. |

### Dashboard — Modified Files

| File | What changed |
|------|-------------|
| `src/pages/Overview.jsx` | Shows each NPC's current FSM state badge on the overview cards. |
| `src/pages/NPCDetail.jsx` | Shows the current FSM state and latest processed decision details in the NPC detail view. |

### New API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/simulation/state/{npc_id}` | Returns the current FSM state, emotion, and latest processed decision for one NPC. |

### Validation

- FSM unit smoke checks passed.
- Dashboard production build passed.
- Backend `/simulation/status` was hardened to avoid crashing on perception history access.

### Backend — Modified Files

| File | What changed |
|------|-------------|
| `simulation_engine.py` | **Bug fix**: `_determine_action()` had a premature `return action_false` inside the `for` loop, causing only the first rule to ever be evaluated. Refactored to accumulate `fallback = action_false` and return it after the loop, so all rules are evaluated in order. Added expanded docstring clarifying the evaluation semantics. |
| `event_bus.py` | Replaced manual list slicing ring buffer (`self._event_history = self._event_history[-200:]`) with `collections.deque(maxlen=200)` for O(1) append with auto-eviction. Fixed `datetime.utcnow()` → `datetime.now(timezone.utc)` (Python 3.12 deprecation). |
| `perception.py` | Same `deque(maxlen=100)` migration for `_recent_perception_events`, removing manual length-check-and-slice logic. |
| `database.py` | Fixed `datetime.utcnow` → `lambda: datetime.now(timezone.utc)` in `DialogueLog.timestamp` and `SimulationEvent.timestamp` column defaults. |
| `main.py` | Fixed `datetime.utcnow()` → `datetime.now(timezone.utc)` in `/health` response. Fixed `db.execute("SELECT 1")` → `db.execute(text("SELECT 1"))` to resolve SQLAlchemy 2.x deprecation warning. Added `CORS_ORIGINS` env var support: `os.getenv("CORS_ORIGINS", "*").split(",")` replaces hardcoded `["*"]`. |
| `routers/simulation.py` | Added **event type validation** on `POST /simulation/inject`: rejects unknown `event_type` with error response listing valid types. Added **queue depth guard** (`MAX_QUEUE_DEPTH = 50`): rejects injection if NPC's queue already has ≥ 50 events, preventing memory exhaustion from flooding. |
| `requirements.txt` | Added `pytest==8.2.2` and `pytest-asyncio==0.23.8`. |
| `.gitignore` | Fixed DB ignore pattern from `backend/sentient.db` → `backend/sentient_npc.db` + added wildcard `backend/*.db`. |

### Infrastructure — Modified Files

| File | What changed |
|------|-------------|
| `.github/workflows/ci.yml` | Renamed job from `backend-seed-and-check` → `backend-test`. Added `Run tests` step: `python -m pytest tests/ -v` with `working-directory: backend`. CI now runs seed sanity check + full test suite on push/PR to main/master. |
| `Readme.md` | Added **Development Roadmap** table (9 weeks, Weeks 1–3 ✅, Weeks 4–9 planned). Added **Why This Project** section explaining portfolio value (GOAP, local LLM, simulation-first architecture). |

### Bug Fixes

| Bug | Impact | Fix |
|-----|--------|-----|
| `_determine_action()` short-circuit | Only the first personality rule for any event type was ever evaluated. NPCs with `aggressive < 60` but `bravery ≥ 50` for `player_stole` events would incorrectly get `alert_guard` instead of `confront`. | Replaced `return action_false` inside loop with `fallback = action_false`, returning fallback after full loop. |
| `datetime.utcnow()` deprecation | Python 3.12+ emits `DeprecationWarning` for `datetime.utcnow()` — returns naive datetime without timezone info. | Migrated all 4 call sites to `datetime.now(timezone.utc)`. |
| Raw SQL string in `db.execute()` | SQLAlchemy 2.x warns when passing raw strings to `execute()`. | Wrapped with `text("SELECT 1")`. |
| Event history memory leak potential | Manual `list[-N:]` slicing creates a new list on every append, briefly doubling memory. | Replaced with `deque(maxlen=N)` for constant-memory ring buffers. |

### How to test

```bash
# Terminal 1 — Run the full test suite
cd backend
python -m pytest tests/ -v

# Expected output: 31 passed
# Tests cover: action rules, emotion shifts, STM management, spatial queries, FOV cones

# Terminal 2 — Test injection validation
cd backend
python seed.py
uvicorn main:app --port 8000

# Try injecting an unknown event type (should be rejected)
curl -X POST http://localhost:8000/simulation/inject \
  -H "Content-Type: application/json" \
  -d '{"npc_id":"guard_01","event_type":"invalid_event","description":"test"}'

# Try injecting a valid event (should succeed)
curl -X POST http://localhost:8000/simulation/start
curl -X POST http://localhost:8000/simulation/inject \
  -H "Content-Type: application/json" \
  -d '{"npc_id":"guard_01","event_type":"player_stole","description":"Player stole bread"}'
```

---

## Cycle 5 — Conversation UI + Ollama Integration + Docker Hardening (Week 5) ✅

**Date:** 2026-06-12  
**Status:** Complete

### What was built

Full NPC conversation interface in the React dashboard powered by a local LLM (Phi-3 via Ollama), Docker configuration hardened to run both backend and dashboard with a single command, auto-seeding on first boot, and Ollama environment variable fix for Docker networking.

### Backend — Modified Files

| File | What changed |
|------|-------------|
| `routers/dialogue.py` | **Bug fix**: `OLLAMA_URL` was hardcoded to `http://localhost:11434/api/generate`, which fails inside Docker containers (localhost points to the container itself, not the host). Now reads from `os.getenv("OLLAMA_URL")` with localhost as fallback for native development. Changed default model from `llama3` to `phi3` (Microsoft Phi-3 Mini 3.8B) — smaller, faster, lower VRAM usage while maintaining quality for short NPC dialogue. Model is also configurable via `OLLAMA_MODEL` env var. |
| `main.py` | Added auto-seeding: on startup, checks if the NPC table is empty and automatically runs `seed.py` to populate the database with 7 NPCs, 17 memories, and 7 relationships. Prevents data loss on subsequent restarts by only seeding when the database is completely empty. |

### Dashboard — New Files

| File | What it does |
|------|-------------|
| `src/pages/Conversation.jsx` | Full chat interface page. **NPC selector** dropdown populated from `GET /npc/`. **Chat window** with speech bubbles: player messages (teal, right-aligned, rounded) and NPC responses (gray, left-aligned) with NPC name and emotion-colored dot indicator. **Typing indicator** with animated bouncing dots while waiting for LLM response. **Message input** with send button, disabled state during generation. **NPC info sidebar** showing: name, ID, emotion badge, FSM state badge, personality radar chart (Chart.js), reputation score, and current zone/position. Loads dialogue history from `GET /dialogue/{npc_id}/history` on NPC selection. Sends messages via `POST /dialogue/{npc_id}`. Optimistic UI update for player messages. Auto-scrolls to newest message. |
| `Dockerfile` | New Dockerfile for the dashboard service. Uses `node:18-alpine` base image. Copies `package.json` first for layer caching, runs `npm install`, copies source. CMD runs `npm install` (to handle volume mount overwrites) then `npm run dev -- --host` to expose Vite dev server. |

### Dashboard — Modified Files

| File | What changed |
|------|-------------|
| `src/api/client.js` | Added 2 functions: `sendDialogue(npcId, playerMessage, playerId)` calls `POST /dialogue/{npc_id}`, `getDialogueHistory(npcId)` calls `GET /dialogue/{npc_id}/history`. Default `playerId` is `"player_001"` matching seed data. |
| `src/App.jsx` | Added `Conversation` import, `/conversation` route, and replaced grayed-out "Live NPC State" placeholder text with an active "Conversation" `NavLink`. |

### Infrastructure — Modified Files

| File | What changed |
|------|-------------|
| `docker-compose.yml` | Added `dashboard` service: builds from `dashboard/Dockerfile`, exposes port 5173, volume-mounts `./dashboard:/app` with anonymous volume for `node_modules` (prevents host OS binary conflicts), sets `VITE_API_URL` env var, depends on `backend` service. Removed obsolete `version: "3.8"` attribute. |
| `dashboard/Dockerfile` | Created Node.js 18 Alpine-based Dockerfile with npm install caching and Vite dev server startup. |

### Ollama Setup Guide

#### What is Ollama?

Ollama is a local LLM runtime that downloads, manages, and serves AI models directly on your machine. It exposes a simple HTTP API at `http://localhost:11434` that the backend calls to generate NPC dialogue. All processing happens on your GPU — no cloud, no API keys, no data leaves your machine.

#### Installation Steps

1. **Install Ollama**
   - Download from [ollama.com/download](https://ollama.com/download) or run:
     ```bash
     winget install Ollama.Ollama
     ```

2. **Pull the Phi-3 model** (~2.3 GB download, one-time)
   ```bash
   ollama pull phi3
   ```

3. **Verify it works**
   ```bash
   ollama list
   # Should show: phi3:latest    2.2 GB
   ```

4. **Run the project**
   ```bash
   docker-compose up --build
   ```
   The backend container automatically connects to Ollama on your host machine via `host.docker.internal`.

#### System Requirements for Phi-3

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| GPU VRAM | 2.5 GB | 4+ GB |
| RAM | 8 GB | 16 GB |
| Disk | 2.5 GB (model) | 2.5 GB |

Phi-3 runs on CPU if no GPU is available (responses take ~10-15s instead of ~3s).

#### Using a Different Model

To use a different Ollama model (e.g., `llama3`, `mistral`, `gemma2`):

1. Pull it: `ollama pull <model_name>`
2. Set the env var in `docker-compose.yml`:
   ```yaml
   environment:
     - OLLAMA_MODEL=llama3
   ```

#### Linux Users

On Linux, `host.docker.internal` may not resolve by default. Add this to the `backend` service in `docker-compose.yml`:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

#### Fine-Tuning (Advanced)

Ollama does not support fine-tuning directly, but you can import fine-tuned models:

1. Fine-tune Phi-3 using [Unsloth](https://github.com/unslothai/unsloth) or [Axolotl](https://github.com/OpenAccess-AI-Collective/axolotl)
2. Export as GGUF format
3. Create a `Modelfile`:
   ```
   FROM ./my-fine-tuned-phi3.gguf
   ```
4. Import into Ollama: `ollama create my-npc-model -f Modelfile`
5. Set `OLLAMA_MODEL=my-npc-model` in `docker-compose.yml`

### How to test

```bash
# Full project setup (first time)
docker-compose up --build
# Open http://localhost:5173/conversation

# Select any NPC from the dropdown and send a message
# With Ollama running: AI-generated in-character responses (~3s on GPU)
# Without Ollama: fallback template responses (instant)

# Test dialogue API directly
curl -X POST http://localhost:8000/dialogue/elder_01 \
  -H "Content-Type: application/json" \
  -d '{"player_message":"What wisdom do you have for me?","player_id":"player_001"}'

# Check dialogue history
curl http://localhost:8000/dialogue/elder_01/history
```

---

## Cycle 6 — RAG-Powered Memory Retrieval for Conversations (Proposed) 🔲

**Status:** Proposed

### Problem

The current dialogue system injects the NPC's top 5 memories by importance score into the LLM prompt, regardless of what the player is actually talking about. This means:

- If you say *"I saw bandits near the gate"*, the prompt might include a memory about *"Player gave a silver ring"* — completely irrelevant.
- The NPC cannot meaningfully recall past events in context. Memories exist in the database but are not semantically matched to the conversation.
- Previous conversation history (from `dialogue_log`) is not considered at all when generating new responses.

### Proposed Solution — RAG (Retrieval-Augmented Generation)

Replace the naive "top 5 by importance" query with a vector similarity search that finds memories **semantically relevant** to the current player message.

#### Architecture

```
Player Message: "I saw bandits near the gate"
        │
        ▼
┌─────────────────────┐
│  Embed player msg    │ ← Ollama /api/embeddings (nomic-embed-text)
│  into vector         │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  ChromaDB search     │ ← Cosine similarity against NPC's memory embeddings
│  Top-K relevant      │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Build prompt with   │ ← Only contextually relevant memories injected
│  relevant memories   │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Phi-3 generates     │ ← NPC response references actual past events
│  response            │
└─────────────────────┘
```

#### Key Components

| Component | Purpose |
|-----------|---------|
| **ChromaDB** | Lightweight vector database (Python-native, no server needed, stores embeddings alongside memory metadata) |
| **`nomic-embed-text`** | Ollama-supported embedding model (~274MB). Converts text into 768-dimensional vectors for similarity search |
| **Memory embedding pipeline** | On memory creation (`POST /memory/`), embed the description and store the vector in ChromaDB |
| **Conversation retriever** | On dialogue, embed the player message → query ChromaDB for top-K similar memories for that NPC → inject into prompt |

#### What would change

| File | Change |
|------|--------|
| `requirements.txt` | Add `chromadb` |
| `memory_manager.py` | On `add_memory()`, also embed and store in ChromaDB collection keyed by `npc_id` |
| `routers/dialogue.py` | Replace `db.query(Memory).order_by(importance)` with ChromaDB vector similarity search. Optionally also embed and search recent `dialogue_log` entries for conversation continuity |
| `seed.py` | Embed all seed memories into ChromaDB on initial seed |
| `docker-compose.yml` | Pull `nomic-embed-text` model on backend startup or document as setup step |

#### Example Impact

**Before (current):**
> Player: "Remember when I helped fix the lantern?"  
> NPC prompt includes: top 5 memories by importance (may not include the lantern memory)  
> NPC response: generic

**After (with RAG):**
> Player: "Remember when I helped fix the lantern?"  
> RAG retrieves: "Player helped repair a broken watch post lantern" (0.92 similarity)  
> NPC response: "Aye, I remember well. That lantern still burns bright thanks to you."

#### Setup for contributors

```bash
# Pull the embedding model (one-time, ~274MB)
ollama pull nomic-embed-text

# ChromaDB installs as a Python pip package, no server needed
pip install chromadb
```

---
