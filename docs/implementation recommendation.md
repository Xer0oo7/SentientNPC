# SentientNPC — Implementation Recommendations

> Summary of all design decisions made during our planning discussion.

---

## 1. Simulation-Only — No Game Wrapper

**Decision:** Build a pure AI simulation framework, not a game.

- No win/lose conditions, no player progression, no game loop
- The sim is a **sandbox** — you press Play, NPCs spawn and behave, you observe
- Sessions are like lab experiments: set initial conditions → inject events → observe emergent behaviour
- The **Analytics Dashboard** (React app) is the primary way to inspect NPC internals
- The project's value is the AI systems, not gameplay

**Why sim-only?**
- Faster iteration — no gameplay polish blocking AI work
- Each module is independently testable
- GOAP planning is extremely hard to debug inside a real game
- The dashboard IS the deliverable
- The project roadmap is already structured module-by-module

> The Project.md has already been updated to reflect this. All references to "game" have been replaced with "simulation." The MainDemo.unity scene was removed; only SimSandbox.unity remains.

---

## 2. Unity Over Unreal Engine

**Decision:** Stay with Unity 2022.3 LTS.

| Factor | Unity | Unreal |
|---|---|---|
| Language | C# — fast to write, easy to debug | C++ — slow compile, harder iteration |
| Compile time | ~2 seconds | 30–90 seconds |
| HTTP/API calls | `UnityWebRequest` — simple | C++ HTTP is painful |
| Behaviour Trees | Build your own (portfolio flex) | Built-in (undermines the project's purpose) |
| Low-poly visuals | Tons of free packs, URP is great | Overkill — Nanite/Lumen designed for photorealism |
| Hardware | Runs on most laptops | Needs decent GPU, 16GB+ RAM |

> Building your own Behaviour Tree and GOAP planner IS the whole portfolio flex. Unreal gives you a BT for free, which undermines your project's purpose.

---

## 3. Medieval Village Setting

**Decision:** The simulation world is a medieval fantasy village.

### NPC Roles and Their AI Purpose

| NPC Role | Personality Bias | What It Tests |
|---|---|---|
| **Town Guard** | High bravery, aggression, loyalty | Perception (patrol + vision), FSM (idle→chase→attack), reputation |
| **Merchant** | High greedy, moderate friendly | Relationship (dynamic prices), memory (remembers theft), GOAP (restock→sell) |
| **Blacksmith** | Low greedy, high loyalty | Dialogue variation, trade decisions |
| **Innkeeper** | High friendly, low aggression | Emotion system (reacts to fights), GOAP (serve→clean→sleep) |
| **Beggar** | Low bravery, high curiosity | GOAP (beg→steal if desperate), personality-driven decisions |
| **Priest** | High friendly, low aggression/greedy | Relationship recovery (forgiveness), dialogue variation |

### Village Layout (Zones)

```
┌─────────────────────────────────────────┐
│              MEDIEVAL SANDBOX            │
│                                          │
│   ┌──────┐          ┌──────┐            │
│   │GUARD │          │MARKET│  ← steal   │
│   │ POST │          │STALL │    events   │
│   └──────┘          └──────┘            │
│                                          │
│          ┌──────────────┐               │
│          │  TOWN SQUARE │ ← social hub  │
│          │   (center)   │               │
│          └──────────────┘               │
│                                          │
│   ┌──────┐          ┌──────┐            │
│   │TAVERN│          │CHURCH│            │
│   │      │          │      │            │
│   └──────┘          └──────┘            │
│                                          │
│          ┌──────┐                        │
│          │SMITHY│                        │
│          └──────┘                        │
└─────────────────────────────────────────┘
```

Zones matter for:
- **Patrol routes** — guard walks between guard post and market
- **Event triggers** — stealing only works near market stall
- **Location-tagged memories** — `"location": "market_district"` in memory schema
- **NPC schedules** — innkeeper goes to tavern in morning, home at night via GOAP

---

## 4. Visual Direction — Stylized, Not Photorealistic

**Decision:** Vibrant stylized art (Zelda: BotW / Genshin Impact vibe). No baked lighting. Everything dynamic and alive.

### Art Style Pillars

- **Colorful and warm** — saturated palette, not grey realism
- **Toon/cel-shaded** — bold colors, clean edges
- **Dynamic lighting** — real-time sun, moving shadows, glowing windows
- **Atmospheric** — volumetric fog, god rays, particles (fireflies, dust, sparks)
- **Alive** — nothing static, everything moves and breathes

### Visual Stack (How to Achieve This in Unity)

```
Blender models (clean, simple geometry)
        ↓
Toon/stylized shader (colors pop, no realism)
        ↓
Real-time URP lighting (dynamic sun, shadows move)
        ↓
Post-processing (bloom, color grading, fog)
        ↓
Particles (fireflies, dust, torch flames)
        ↓
✨ Beautiful
```

### Specific Unity Techniques

| Technique | Purpose | Effort |
|---|---|---|
| **URP (Universal Render Pipeline)** | Foundation for all visual effects | Project setup (one-time) |
| **Toon shader** | Stylized cel-shaded look on all models | Free packs or custom |
| **Real-time directional light** | Dynamic sun with moving shadows | Built-in, no baking |
| **Post-Processing Volume** | Bloom, color grading, AO, vignette | 10 min toggle |
| **Volumetric fog** | Atmosphere, depth, magical feel | URP setting or particles |
| **Emissive materials** | Glowing windows, torch light, forge fire | Emission channel + bloom |
| **Particle System** | Fireflies, dust motes, leaves, sparks | Built-in, drag and drop |
| **Stylized water shader** | Cartoon reflections, foam edges | Free Asset Store shaders |

> No textures need to be baked. All lighting is real-time. The beauty comes from shaders + lighting + post-processing, not from pre-rendered textures.

---

## 5. Art Pipeline — Blender → Unity

**Decision:** Model the medieval village in Blender, import into Unity.

### Workflow

```
Blender                              Unity
──────                              ─────
Model buildings (low-poly)      →   Import .fbx
UV unwrap (simple/flat colors)  →   Assign toon shader materials
Set origin points               →   Place in scene
Export as .fbx                  →   Bake NavMesh on geometry
                                    Add box colliders
                                    Set up real-time lighting
                                    Add post-processing
```

### Blender Guidelines

- **Keep it low-poly** — stylized art thrives on clean shapes, not dense meshes
- **Don't bake textures** — use flat/gradient colors, let Unity shaders do the work
- **Apply transforms** before export (Ctrl+A → All Transforms)
- **Scale: 1 unit = 1 meter** (Unity and Blender agree on this)
- **Export as FBX** with "Apply Scalings: FBX All"
- **Modular pieces** — separate buildings, walls, props (not one giant mesh)

### Alternative: Asset Packs (Faster)

| Pack | Cost | Notes |
|---|---|---|
| Synty POLYGON Starter Pack | Free | Good for prototyping |
| Kaykit Medieval Builder Pack | Free | Modular medieval buildings |
| Synty POLYGON Fantasy Kingdom | ~$20 | Complete medieval village kit |

Asset packs can be used as placeholders early, then replaced with Blender models later.

---

## 6. Build Order — Brain First, Beauty Later

**Decision:** Build AI systems with primitives first, add visuals at the end.

```
Week 1:    Project scaffold + FastAPI + SQLite            ✅ Done
Week 2:    Memory System (capsule NPCs on flat plane)     🔲 Next
Week 3:    Perception System (vision + hearing)           🔲
Week 4:    Personality + Relationship + Emotion           🔲
Week 5:    FSM + Behaviour Tree                           🔲
Week 6:    GOAP planner                                   🔲
Week 7:    LLM dialogue (Ollama)                          🔲
Week 8:    Analytics Dashboard + WebSocket feed            🔲
Week 9:    Blender village + URP polish + demo video       🔲
```

> **The AI code doesn't care what the buildings look like.** A cube tagged "Tavern" and a Blender tavern model tagged "Tavern" work identically. Build the brain with placeholders, then swap in beautiful models at the end.

### Why this order?

1. **No blocked work** — you're never waiting on art to test AI
2. **The hard part is the AI** — get it working and debuggable first
3. **Art is a skin swap** — drop in models, assign toon shaders, add lighting, done
4. **Demo video is last** — record when everything is polished

---

## 7. AI Debug Visualizations

Beyond the medieval world itself, the AI overlays are what make the sim stand out:

| Visualization | Purpose |
|---|---|
| **Glowing FOV cone** | Shows what each NPC can see |
| **Hearing radius circle** | Shows NPC's hearing range |
| **Floating emotion icon** | 😐😠😨😊 above NPC head |
| **State label** | "PATROL" / "CHASE" / "FLEE" floating text |
| **Path lines** | NavMesh path drawn as colored line |
| **GOAP plan display** | Current goal chain shown as floating text |
| **Relationship bar** | Color-coded bar above NPC (red→green) |

These overlays + the React dashboard = the "microscope" into the NPC's mind.

---

## Summary of All Decisions

| Question | Decision |
|---|---|
| Game or Sim? | **Sim only** — no game wrapper |
| Unity or Unreal? | **Unity** — faster iteration, C#, portfolio flex |
| Setting? | **Medieval fantasy village** |
| Art style? | **Stylized/toon** — vibrant, dynamic, not photorealistic |
| Baked lighting? | **No** — all real-time (URP + toon shaders) |
| Art pipeline? | **Blender → Unity** (FBX export) |
| Build order? | **AI first (primitives) → visuals last (week 9)** |
