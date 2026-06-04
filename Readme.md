# SentientNPC
### Memory-Driven AI Framework for Dynamic Game Characters
 
> *NPCs that remember, learn, adapt, and feel.*
 
[![Unity](https://img.shields.io/badge/Unity-2022.3%20LTS-black?logo=unity)](https://unity.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/SQLite-3-003B57?logo=sqlite&logoColor=white)](https://sqlite.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
 
---
 
## What is SentientNPC?
 
Most game NPCs are forgettable. They follow fixed scripts, repeat the same three lines, and treat every player interaction as if it never happened. SentientNPC is a framework that changes that.
 
Built on top of Unity with a Python/FastAPI brain, SentientNPC gives NPCs:
 
- **Persistent memory** — they remember what you did, days later
- **Personality traits** — aggression, friendliness, greed, bravery drive every decision
- **Relationship scoring** — help an NPC and they become an ally; betray them and face consequences
- **Emotion states** — NPCs feel happy, fearful, angry, sad — and it shows in their dialogue
- **Dynamic dialogue** — powered by a local LLM (Llama 3 via Ollama), every conversation is unique
- **GOAP planning** — NPCs generate their own action plans to achieve goals
- **Analytics dashboard** — a React web UI showing every NPC's memory, emotion, and relationship state in real time
---
## Architecture Overview
 
```
Player Input / Game Events
          │
          ▼
  ┌───────────────┐
  │ Perception    │  ← Vision (FOV raycasting), Hearing (falloff), Event Detection
  └──────┬────────┘
         │
         ▼
  ┌───────────────┐
  │ Memory System │  ← Short-term cache + Long-term SQLite storage
  └──────┬────────┘
         │
         ├──────────────────────────────┐
         ▼                              ▼
  ┌───────────────┐            ┌────────────────────┐
  │  Personality  │            │  Relationship Score │
  │  + Emotion    │            │  + Reputation       │
  └──────┬────────┘            └──────────┬──────────┘
         │                               │
         └──────────────┬────────────────┘
                        ▼
               ┌─────────────────┐
               │ Decision Engine │  ← FSM → Behaviour Tree → GOAP
               └────────┬────────┘
                        │
                        ▼
               ┌─────────────────┐
               │ Dialogue Engine │  ← Template system + LLM (Ollama)
               └────────┬────────┘
                        │
                        ▼
               ┌─────────────────┐
               │ Action Execution│  ← NavMesh movement, animations, API sync
               └─────────────────┘
                        │
                        ▼
               ┌─────────────────┐
               │   FastAPI +     │  ← Backend API, SQLite persistence,
               │   SQLite        │      analytics data feed
               └─────────────────┘
                        │
                        ▼
               ┌─────────────────┐
               │ React Dashboard │  ← NPC stats, memory logs, relationship
               └─────────────────┘    graph, emotion state
```
 
---

## Development Roadmap
 
| Week | Module | Status |
|---|---|---|
| 1 | Project scaffold, folder structure, FastAPI + SQLite setup | ✅ Complete |
| 2 | Simulation Engine + Priority Queues + Memory System + Live Events | ✅ Complete |
| 3 | Perception System (vision FOV, hearing, spatial world, 7 NPCs) | ✅ Complete |
| 4 | Personality + Relationship + Emotion systems | 🔲 Next |
| 5 | FSM + Behaviour Tree decision engine | 🔲 Planned |
| 6 | GOAP planner | 🔲 Planned |
| 7 | LLM dialogue (Ollama integration) | 🔲 Planned |
| 8 | Analytics dashboard + live WebSocket feed | 🔲 Planned |
| 9 | Sim stress testing (multi-NPC scenarios) + demo video | 🔲 Planned |
 
---
 
## Why This Project
 
> "Built a Unity game" is forgettable.  
> "Built a memory-driven autonomous NPC simulation framework with dynamic dialogue, relationship modelling, behaviour trees, GOAP planning, reputation systems, and local LLM integration" is not.
 
SentientNPC is a pure AI simulation — no game wrapper, no gameplay loop. It is designed to demonstrate systems-level thinking across autonomous agent AI, backend architecture, database design, and modern LLM integration — the exact combination that game AI and simulation engineering roles look for.
 
**GOAP** is used in shipped AAA titles (F.E.A.R., S.T.A.L.K.E.R.) and is a genuine signal of game AI knowledge. Most candidates have never implemented it.
 
**Local LLM dialogue** puts this project in conversation with companies like Inworld AI, Convai, and NVIDIA ACE — the frontier of real-time AI-driven characters.
 
**Simulation-first** means every module is testable, measurable, and visible through the analytics dashboard — no art, no level design, just pure AI systems running in a sandbox.

---