# AI Integration Plan for SentientNPC

## Purpose
This document proposes a practical way to implement AI in the current project based on:
- Existing code in backend and dashboard
- Existing design docs in Readme.md and docs/
- Current implementation status (Weeks 1 to 5 complete, Weeks 6 to 9 pending)

## Current State (What already works)

### Backend
- FastAPI service with routers for npc, memory, relationship, dialogue, analytics, simulation, and perception
- SQLite models for NPCs, memory, relationship, dialogue logs, and simulation events
- Tick based simulation engine with per NPC priority queues
- Perception engine with vision cone and hearing propagation
- Memory manager with short term memory (TTL and capacity) and long term promotion by importance
- Event bus with WebSocket stream and event history buffer

### Dashboard
- Overview page for NPC summary
- Simulation page for start/stop, event feed, and queue visualization
- Perception page with world map, FOV overlays, and sound triggers
- NPC detail page with personality chart, memory, relationships, and dialogue history

### What is partially implemented
- Personality and emotion are used in event reaction logic
- Dialogue route includes Ollama call and fallback templates

## Main Gaps to Close for Real AI Behavior
1. No persistent decision state machine per NPC
2. No behavior tree node evaluation engine
3. No GOAP planning for multi step goals
4. No strong memory driven action selection (memory exists but is weakly used in decisions)
5. Reputation is stored but not deeply integrated into behavior
6. Dialogue to behavior loop is weak (dialogue does not strongly change long term plans)
7. No schedule or time of day driven behavior

## Recommended AI Architecture

Use a layered decision architecture that fits the current codebase:

1. Perception layer
- Keep world and perception modules as sensors
- Output normalized events to simulation queue

2. Memory and context layer
- Keep current memory_manager for STM and LTM
- Add a decision context builder to collect:
  - recent memories
  - relationship score
  - reputation and faction view
  - current emotion
  - location and nearby entities

3. Decision layer
- Add FSM for high level states (idle, patrol, investigate, chase, talk, trade, flee, sleep)
- Add behavior tree for in state tactical decisions
- Add GOAP planner for goals requiring multiple actions

4. Dialogue layer
- Keep template fallback plus LLM generation
- Use dialogue outcomes to write memory and relationship deltas
- Feed dialogue effects back to decision context

5. Execution layer
- Convert chosen actions to simulation events and world updates
- Emit all decisions to dashboard for debugging and trust

## Suggested Implementation Phases

## Phase 1: FSM Foundation
Goal: introduce persistent state per NPC

Create:
- backend/fsm.py

Change:
- backend/simulation_engine.py
- backend/database.py
- backend/models.py

Actions:
- add npc state field in DB (fsm_state)
- load and update state each tick
- expose decision state endpoint for dashboard

Success criteria:
- each NPC has a stable state over time
- state transitions happen from explicit rules

## Phase 2: Behavior Tree Engine
Goal: replace flat action table with composable decisions

Create:
- backend/behaviour_tree.py
- backend/decision_context.py

Change:
- backend/simulation_engine.py

Actions:
- implement Selector, Sequence, Condition, Action nodes
- evaluate BT using decision context
- keep ACTION_RULES as fallback during migration

Success criteria:
- actions are chosen through BT node path
- logs show evaluated conditions and winning branch

## Phase 3: Memory Driven Decisions
Goal: make past events change future behavior

Change:
- backend/simulation_engine.py
- backend/memory_manager.py

Actions:
- query recent and high importance memories before action selection
- add utility methods like:
  - has_recent_event(npc_id, event_type, window)
  - hostility_signal(npc_id, player_id)

Success criteria:
- repeated theft or attack changes guard and merchant behavior without manual rules per case

## Phase 4: GOAP Planner
Goal: support autonomous multi step goals

Create:
- backend/goap.py
- backend/routers/goals.py

Change:
- backend/simulation_engine.py
- backend/database.py
- backend/models.py

Actions:
- represent world state facts and action preconditions/effects
- run A star planning per NPC goal
- execute plans with interruption and replanning

Success criteria:
- NPC can run plans like investigate sound then report then return patrol

## Phase 5: Reputation and Factions
Goal: global social consequences across NPC groups

Create:
- backend/routers/reputation.py

Change:
- backend/database.py
- backend/simulation_engine.py
- backend/seed.py

Actions:
- add faction model and faction reputation
- include faction reputation in context and BT conditions
- propagate reputation events to group members

Success criteria:
- harming one faction member influences responses from others in that faction

## Phase 6: Dialogue Loop Upgrade
Goal: connect dialogue to memory and planning

Change:
- backend/routers/dialogue.py
- docker-compose.yml
- backend/tests/

Actions:
- harden Ollama availability checks and timeouts
- map dialogue intent to relationship delta and memory write
- add tests with mocked Ollama and fallback path

Success criteria:
- dialogue can improve or worsen future treatment by NPCs

## Phase 7: Scheduling and Daily Routines
Goal: world feels alive when no external events happen

Create:
- backend/scheduler.py

Change:
- backend/simulation_engine.py
- backend/world.py

Actions:
- add time of day model
- assign simple role based schedules
- schedule goals become GOAP inputs

Success criteria:
- NPCs move and act by role even without player input

## Phase 8: Dashboard Visibility
Goal: expose AI internals for debugging and demo quality

Create:
- dashboard/src/pages/Decisions.jsx
- dashboard/src/components/FSMDiagram.jsx
- dashboard/src/components/BehaviourTreeViewer.jsx
- dashboard/src/components/GOAPPlanPanel.jsx

Change:
- dashboard/src/App.jsx
- dashboard/src/pages/NPCDetail.jsx
- dashboard/src/api/client.js

Actions:
- show current state, BT branch, active goal, and plan steps
- show why a decision was selected

Success criteria:
- every visible NPC action has an inspectable reasoning trail in dashboard

## Testing Strategy

Backend tests to add:
- tests/test_fsm.py
- tests/test_behaviour_tree.py
- tests/test_goap.py
- tests/test_reputation.py
- tests/test_dialogue.py

Scenario tests:
- player steals near market and guard sees it
- loud sound in market triggers investigation chain
- player apologizes and relationship recovers over time
- low faction reputation changes merchant and guard behavior

Performance checks:
- 7 NPC baseline then 25 NPC stress run
- maintain stable tick loop and queue bounds

## Practical First Sprint (recommended)
Start with the smallest high impact slice:
1. Implement fsm.py and DB fsm_state field
2. Add decision context builder
3. Route one event family (player_stole) through BT path
4. Expose decision trace endpoint
5. Visualize state and trace in dashboard

This gives immediate visible AI improvement while keeping migration risk low.

## Expected Outcome
After these phases, the project moves from event reaction simulation to memory driven autonomous NPC behavior with explainable AI decisions, stronger dialogue consequences, and clear dashboard observability.
