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

