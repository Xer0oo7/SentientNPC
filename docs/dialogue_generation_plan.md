# Asynchronous Dialogue Generation Queue

This document outlines the plan to implement an asynchronous queue to generate autonomous NPC dialogue (barks) in response to simulation events without blocking the main 200ms tick engine.

## Problem Statement
When NPCs react to stimuli (e.g., seeing the player steal, hearing an explosion), generating their dialogue via Ollama takes 1-3 seconds. If we do this synchronously, the game's tick loop will freeze. Placing reactions in a queue allows the LLM to process them in the background and displaying the text bubbles as they finish generating.

## Proposed Changes

### 1. Backend (`backend/`)

#### [NEW] `dialogue_queue.py`
Create a new module to manage the asynchronous dialogue generation.
- **Queue Manager**: An `asyncio.Queue` to hold `DialogueGenerationRequest` items (NPC ID, event description, action taken, emotion).
- **Background Worker**: 2 concurrent background worker threads (async tasks) that run in a continuous loop, consuming requests from the queue to allow multiple dialogue generations in parallel.
- **LLM Prompting**: It will construct a strict prompt for Ollama: *"You are [Name], feeling [Emotion]. You experienced: [Event]. You took action: [Action]. Write a single, short sentence of what you say out loud."*
- **Broadcasting**: After Ollama returns the generated text, it will package it as a `SimEvent` with `event_type="npc_spoke"` and broadcast it to the frontend via the `EventBus`.

#### [MODIFY] `simulation_engine.py`
Hook the simulation engine into the new queue.
- Define a list of "vocal" actions (e.g., `alert_guard`, `chase`, `confront`, `greet_warmly`, `investigate_sound`, `thank`).
- In `_process_event()`, after deciding the action and emotion, if the action is in the "vocal" list, push the context to the `dialogue_queue`.
- This ensures the tick engine finishes instantly and moves on to the next NPC.

#### [MODIFY] `main.py`
Manage the lifecycle of the background worker.
- Import the new `dialogue_queue` module.
- Inside the FastAPI `lifespan` context manager, spawn the `dialogue_queue` worker as an `asyncio.create_task()` when the server starts, and cancel it gracefully on shutdown.

#### [MODIFY] `event_bus.py`
Register the new event type.
- Add `"npc_spoke"` to `EVENT_IMPORTANCE` (e.g., `0.8`) and `EVENT_PRIORITY` (e.g., `PRIORITY_HIGH`).

### 2. Dashboard (`dashboard/`)

No structural changes are strictly required, as the `EventFeed.jsx` is already built to consume any incoming `SimEvent` from the WebSocket. The spoken text will appear as the event `description`.
