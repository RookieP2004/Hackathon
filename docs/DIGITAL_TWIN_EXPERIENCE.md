# AEGIS AI — The Digital Twin Experience
### 3D Rendering, Animation, and Temporal Navigation Design

**Classification:** Internal — Engineering / Graphics & Simulation
**Document Owner:** Office of the CTO / Digital Twin Engineering
**Version:** 1.0
**Companion Documents:** `ARCHITECTURE.md` §16 (Digital Twin Architecture — this document specifies its rendering/experience layer in full), `UI_UX_SPECIFICATION.md` §3-4 (Digital Twin & Factory Map screens — this document is what powers them), `KNOWLEDGE_GRAPH.md` (the scene graph is generated *from* this, not authored separately), `DATABASE_SCHEMA.md` §20-21 (Sensor/Machine History — the data source for every animation), `RISK_FUSION_ENGINE.md` (the source of the Predictive Overlay)

---

## 0. The Presence Design Thesis

> **A digital twin that looks like a dashboard with a 3D background has failed at the one thing that justifies building it in 3D at all.**

"Feel like you're inside the factory" is not a rendering-quality bar — plenty of photorealistic renders feel like watching a video, not being somewhere. Presence comes from four properties working together, and this document is organized around achieving each honestly rather than faking it with visual polish:

1. **Scale-accurate, geo-referenced space** — every object is where its real counterpart actually is, at real-world scale, not a stylized abstraction of relative position (§1.2).
2. **Motion that is driven by real state, never authored for effect** — a worker walks because Worker Agent said they're walking there; a pump's rotor spins because `machine_state_history` says it's running. Nothing animates for demo polish alone (§7.1, and restated wherever it matters).
3. **Consequence-aware rendering** — hazards, risk, and prediction are rendered with the same physical plausibility as buildings and pipes, not as a flat UI overlay pasted on top of a 3D scene that doesn't know about them (§4, §6).
4. **A single source of truth across live and replayed time** — walking through what's happening right now and scrubbing back through what happened during last Tuesday's near-miss must look and feel like the *same place*, not two different products (§9).

---

## 1. Scene Architecture, Asset Pipeline & Live Telemetry Binding

### 1.1 The Scene Graph Is Generated From the Knowledge Graph, Not Authored Separately

The 3D scene's hierarchy — Plant → Building → Zone → Equipment — is not hand-built in a 3D authoring tool and then separately kept in sync with `KNOWLEDGE_GRAPH.md`'s node/relationship model. **It is generated directly from it**: a `HAS_BUILDING`/`HAS_ZONE`/`CONTAINS` traversal from the Plant root produces the scene graph's parent-child structure automatically, and every 3D object's transform-parenting matches its graph containment exactly. This is the same discipline `ARCHITECTURE.md` §16.4 established ("the visualization is a client of the Twin's state API, never a separate source of truth") pushed one level deeper: the *topology* itself, not just the *state* painted onto it, has exactly one source of truth. A newly-onboarded valve (`ARCHITECTURE.md` §17.3) appears in the 3D scene the moment it's registered in the graph, parented into its zone correctly, with zero manual 3D-scene authoring step.

### 1.2 Geo-Referencing and Scale

Every plant's scene origin is anchored to its real `latitude`/`longitude` (`DATABASE_SCHEMA.md` §4.1), and every object within it is placed at true real-world scale and true relative position — a 40-meter reactor is 40 meters tall in scene units, not a stylized proportion. This single decision is what makes the geo-referenced solar lighting (§7.2) and accurate walk-through wayfinding (§8.1) possible at all; a scene built at "impressionistic" scale cannot support either honestly.

### 1.3 Asset Pipeline: Stylized-but-Precise, Consistent With `ARCHITECTURE.md` §16.5

Base geometry is clean, low-polygon, and stylized — never photorealistic, per the architecture document's explicit and still-binding reasoning: photorealism sets an unmeetable fidelity expectation and dates badly, while a stylized-but-dimensionally-precise model (the "engineering blueprint made physical" register `UI_UX_SPECIFICATION.md` §3 already established for this screen's color palette) ages well and renders fast at scale. Materials use physically-based rendering (PBR: metalness/roughness workflow) specifically so that the *lighting system* (§7.2) — not hand-painted texture detail — is what makes a steel valve read as steel and a painted pipe read as painted metal. This is a deliberate leverage point: PBR materials plus good lighting produce more perceived realism per unit of art-production effort than high-poly, high-texture-resolution assets without correct lighting response, which matters enormously given how many distinct equipment types (`DATABASE_SCHEMA.md` §3's `equipment_types`) a real plant deployment needs modeled.

### 1.4 The Live Telemetry Binding Layer

Every visual property that can change — a gauge's needle rotation, a pipe's flow-particle speed, a machine's operational animation state, a risk zone's color wash — is bound to a **Data Binding Layer**, a thin, uniform interface between the renderer and the data source, deliberately identical in shape whether the data source is:
- a live WebSocket feed (via the Realtime Gateway, `ARCHITECTURE.md` §11.2), or
- a historical query against `sensor_readings`/`machine_state_history`/`risk_scores` for a replay session (§9).

The renderer never knows or cares which; it binds to `{entity_id, property, value, timestamp}` tuples from whichever source is currently active. **This is the single architectural decision that makes §9's live/replay parity possible** — there is exactly one rendering code path, fed by two interchangeable data sources, rather than a "live mode" and a separate "history mode" that could subtly diverge in appearance and erode the trust that what you see in replay is what actually happened.

---

## 2. 3D Buildings & Pipelines

### 2.1 Buildings

Building envelopes render as extruded-footprint massing (matching the `buildings.floor_count`/footprint data, `DATABASE_SCHEMA.md` §4.2) with facade detail carried by PBR material and normal-map texture rather than modeled geometric detail — a deliberate cost/fidelity trade consistent with §1.3. An **X-ray/cutaway toggle** lets a user see equipment and zones inside a building without permanently modeling every interior wall as passable geometry or requiring the camera to physically clip through a facade (a jarring, presence-breaking interaction) — the building shell fades to a translucent, wireframe-edged state on toggle, revealing interior zone volumes and equipment beneath it, then restores fully opaque on toggle-off. **Roadmap fidelity** (`ARCHITECTURE.md` §16.5): as real CAD/P&ID/BIM data is ingested, building massing transitions from footprint-extrusion to true architectural geometry without changing the scene-graph structure described in §1.1 — the graph node the building geometry attaches to doesn't change, only the mesh bound to it.

### 2.2 Pipelines

Pipeline geometry is **procedurally generated from the Knowledge Graph's topology**, never hand-modeled per segment: a `Pipeline` node's `FLOWS_TO`/`INSTALLED_ON` relationships (`KNOWLEDGE_GRAPH.md` §3.2) define a spline path between its connected equipment endpoints, and a tube-mesh generator extrudes pipe geometry along that spline at the segment's actual `diameterMm` (`KNOWLEDGE_GRAPH.md` §2.2). This is what lets a newly-registered pipeline segment appear correctly routed in 3D space automatically, the same onboarding guarantee established for equipment in §1.1.

**Flow visualization:** an animated, tiling flow-texture (or lightweight particle stream for high-visibility lines) travels along each pipeline's surface, direction and speed driven by the Live Telemetry Binding Layer from the pipeline's associated flow-rate sensor — a stationary line reads immediately as "not flowing" without needing a label, and a fast-moving stream reads as high flow, giving an operator ambient awareness of process state that a numeric readout alone can't convey at a glance. Flow-texture color is medium-coded (a legend-documented palette distinct from the severity vocabulary, consistent with `UI_UX_SPECIFICATION.md` §8's rule that identity-coding and severity-coding must never share a color language) — steam, process gas, cooling water, and hydrocarbon lines are each a recognizable, consistent hue.

---

## 3. Dynamic Entities: Workers, Machines, Forklifts & Cranes

### 3.1 Workers

Worker avatars are deliberately **generic, low-poly, non-identifying figures** — no photorealistic personal likeness, no facial detail — directly continuing the privacy-by-design stance `UI_UX_SPECIFICATION.md` §6 established for Worker Tracking (a system built to protect the workforce must not visually read as surveillance of individuals). Position and orientation are driven by Worker Agent's live location feed (`AGENT_ARCHITECTURE.md` §3) through the Data Binding Layer, with a **path-interpolated walk cycle** — the avatar's legs animate as if walking at a speed consistent with the actual distance covered between position updates, rather than teleporting between points, matching the "movement reads as continuous, real motion" principle `UI_UX_SPECIFICATION.md` §4 already specified for Factory Map's personnel dots, now rendered as a full 3D figure instead of a 2D dot.

A worker's avatar carries a small, unobtrusive **state halo** — a colored ring at the figure's base — reflecting PPE compliance and hazard-zone status (neutral/no issue, amber for a PPE violation, red for currently inside an elevated-risk zone) using the exact severity palette from `UI_UX_SPECIFICATION.md` §0.2, so the 3D view and the 2D Factory Map never disagree about what a given status color means.

### 3.2 Machines

A machine's animation state is driven directly by `machine_state_history.operating_state` (`DATABASE_SCHEMA.md` §21) through the Data Binding Layer — a pump's rotor mesh spins only when state is `running` (at a rotation speed derived from its `rpm` reading), freezes on `idle`, and switches to a distinct juddering/stalled animation plus a warning material tint on `faulted`. **No machine ever animates a state it isn't actually reporting** — this is the 3D-rendering expression of the same rule that governs every other visualization in this system: the twin shows what the data says, not what would look good running continuously in a demo loop.

### 3.3 Forklifts & Cranes

Mobile equipment (forklifts, overhead cranes) renders with the same live-position-driven path interpolation as workers (§3.1), plus a feature workers don't need: a **projected-path indicator** — a short, fading directional trail extrapolated from recent heading and speed, showing where the vehicle is headed in the next several seconds. This is not decorative; it is the direct visual expression of the Worker Injury network's exposure-risk reasoning (`RISK_FUSION_ENGINE.md` §4.4) — when a projected forklift path is computed to intersect a tracked worker's current position within a short time window, both the path indicator and the worker's state halo shift to a warning state simultaneously, giving a control-room observer (or, via the mobile app, the worker themselves in a future field-alert iteration) a genuinely early, spatial warning that a text alert alone communicates less immediately.

---

## 4. Hazard Visualization: Gas Clouds & Fire

### 4.1 Gas Clouds

A confirmed or predicted gas release renders as a **volumetric density field** — a true 3D cloud with internal density variation, not a flat 2D decal or a translucent sphere — because a flat overlay cannot honestly communicate "the concentration is higher near the source and thins with distance," which is exactly the information a responder needs to judge a safe approach distance. Density and extent are driven by a **lightweight, fast-approximate dispersion model** (a Gaussian-plume-style approximation, explicitly *not* the full computational-fluid-dynamics simulation `ARCHITECTURE.md` §26.2 correctly scoped as a future roadmap item) taking the confirmed gas sensor concentration as its source term and the current `WeatherEpisode`'s wind speed/direction (`KNOWLEDGE_GRAPH.md` §2.5) as its transport input — good enough for real-time situational rendering at interactive frame rates, explicitly not claimed to be regulatory-grade dispersion modeling.

Cloud color and opacity map to concentration relative to the hazard's LEL/UEL thresholds using the same continuous, sigmoid-shaped mapping `RISK_FUSION_ENGINE.md` §3.4 specified for the *reasoning* layer — the visualization and the underlying probabilistic model share the same threshold curve, so the cloud a user sees is a faithful rendering of what the Bayesian network is actually reasoning about, not a separately-tuned "looks scary at the right moment" visual effect.

### 4.2 Fire

Fire renders as a particle-system flame effect (billboard sprites or a lightweight volumetric flame shader, scaled to the confirmed severity from Vision Agent's detection or an active Emergency Event, `AGENT_ARCHITECTURE.md` §2/§9) with an accompanying smoke plume whose drift direction is, like the gas cloud, wind-informed from the current `WeatherEpisode`. **Fire and smoke effects only render on confirmed detection or an active emergency event — never speculatively** — a predicted-but-unconfirmed fire risk is communicated through the Predictive Overlay (§6.2) and a risk-zone color wash (§5.1), using an entirely different, clearly-hypothetical visual language, never a literal flame rendered before the hazard is actually confirmed to exist. Conflating "predicted" and "observed" fire in the same visual register would be a serious violation of this entire system's foundational explainability commitment (`ARCHITECTURE.md` §9's design law), rendered concrete here at the level of a single shader decision.

---

## 5. Static Safety Overlays: Risk Zones, Emergency Exits, Cameras & Sensors

### 5.1 Risk Zones

A zone's risk state renders as a soft, low-opacity volumetric boundary wash — a translucent colored envelope following the zone's actual 3D volume (not just a ground-plane tint) — using the exact severity palette and "no looping alarm animation" motion rule already established in `UI_UX_SPECIFICATION.md` §0.2/§4: a one-time pulse on severity-tier transition, then a steady wash, never a continuous flashing effect, for the same alarm-fatigue reasons stated there.

### 5.2 Emergency Exits

Exit locations render as persistent, always-visible directional markers (visible regardless of zoom level or camera mode, unlike most other overlay layers which are toggleable) — safety wayfinding information is treated as a baseline layer, not an optional one. During an active Emergency Event, a **dynamic recommended-route highlight** computes and renders a glowing path from any occupied zone to the nearest safe exit, routing *around* currently-elevated-risk zones by traversing the Knowledge Graph's zone-adjacency topology (`KNOWLEDGE_GRAPH.md` §3) and excluding any zone whose live risk score exceeds a safe-passage threshold — the same evacuation-routing intelligence Emergency Agent's evacuation broadcast (`AGENT_ARCHITECTURE.md` §9) uses operationally, rendered spatially rather than only communicated as text.

### 5.3 Camera Locations

Cameras render as small directional icons with an optional, toggleable **field-of-view cone** (matching the layer-control pattern `UI_UX_SPECIFICATION.md` §4 established for Factory Map) — shown by default at high zoom for spatial planning, hidden by default at wide zoom to reduce visual clutter. Selecting a camera icon opens a live-feed inset directly in the 3D viewport, keeping a user's spatial context intact rather than navigating away to a separate camera-review screen.

### 5.4 Sensor Locations

Sensor markers use the same status-color convention as every other live-data element (severity/quality-flag color-coded), but with a **scale-aware clustering system**: at the density a commercial-scale deployment implies (`ARCHITECTURE.md` NFR-7's 500,000-sensor target), rendering every individual sensor icon at wide zoom would produce unreadable icon soup and a real frame-rate cost. Below a configurable zoom/density threshold, nearby sensors aggregate into a single cluster marker (showing count and worst-status color, the same pattern mapping applications use for dense point data); zooming in progressively de-clusters into individual, selectable sensor icons — a direct application of the Level-of-Detail principle from §1.3 to overlay data, not just geometry.

---

## 6. Heat Maps & Predictive Overlay

### 6.1 Heat Maps — Three Distinct Modes, Never Combined

A shader-based ground/surface density overlay supports three independently-toggleable modes, deliberately never blended into one composite view: **Risk heat map** (spatial risk-score density, sourced from Risk Fusion Engine output), **Thermal heat map** (raw thermal-camera-derived temperature field, sourced from Vision Agent's thermal capability, `ARCHITECTURE.md` §18.1), and **Occupancy heat map** (personnel density over time, sourced from Worker Agent). Combining these into a single "danger map" would conflate three genuinely different underlying facts (a computed prediction, a raw physical measurement, and a population-density statistic) into one number a viewer can't decompose — exactly the kind of false-precision compositing this entire design series has consistently refused to do (the same reasoning `RISK_FUSION_ENGINE.md` §2 gave for keeping evidence categories distinct rather than flattening them into one feature vector, now applied to a visual layer instead of a Bayesian network input).

### 6.2 Predictive Overlay

This is the layer that most directly visualizes the AI's forward-looking reasoning rather than only its present-tense assessment. Where Risk Fusion Engine and Prediction Agent output a time-to-event window (`RISK_FUSION_ENGINE.md` §3.5, `AGENT_ARCHITECTURE.md` §8), the Predictive Overlay renders a **forward-projected, visually distinct "ghost" extension** of the relevant hazard visualization — a dashed-boundary, higher-transparency extension of a gas cloud's current envelope showing its forecast dispersion boundary, or a risk-zone wash extending a translucent "projected escalation" gradient into a currently-nominal adjacent zone the model forecasts will be affected next.

**The ghost/ hypothetical rendering convention is applied with total consistency across this entire document**: anything rendered opaque and solid is observed, confirmed present-tense reality (a real gas cloud, a real fire, a real worker position); anything dashed, translucent, or rendered in the ghost material is a model's forecast or a hypothetical simulation (§9.4) — never the same visual weight, never ambiguous, and this single rule is what lets a user glance at the twin and instantly know whether they're looking at what *is* happening or what the AI believes *might*.

---

## 7. Animation & Lighting Systems

### 7.1 A Unified, State-Machine-Driven Animation Architecture

Every animated entity in this scene — a worker's gait, a machine's rotor, a valve's open/closed position, a gas cloud's dispersion, a flame's flicker — is driven by the same underlying principle stated in §0's presence thesis and enforced structurally here: **an entity's animation state machine has no "idle default" branch that plays when no data is available; it has a "data missing/stale" branch that visually communicates exactly that** (a desaturating filter or a distinct "last known state" material treatment, consistent with the stale-data conventions already established in `ARCHITECTURE.md` §16's Digital Twin failure handling and `UI_UX_SPECIFICATION.md` §3's error state). A demo environment is never allowed to fall back to a pleasant-looking looping idle animation when live data isn't actually present — that would be a fabricated-confidence failure mode in a 3D medium, exactly as serious as a fabricated number would be in a chart.

### 7.2 Lighting: Geo-Accurate, Time-of-Day, and Emergency States

Baseline lighting is a **dynamic time-of-day system** computing real solar position from the plant's actual `latitude`/`longitude`/`timezone` (`DATABASE_SCHEMA.md` §4.1) — the twin at 3 a.m. is genuinely dark with practical (fixture-based) lighting active, and at noon has a correspondingly different light angle and color temperature, because this is one more dimension along which the twin should match observable reality rather than a stylized, always-bright rendering convenience. Interior zones use practical fixture lighting (matching real fixture placement where known) independent of exterior solar state.

**Emergency lighting is a distinct, non-decorative state**, not a filter applied for visual drama: when an Emergency Event is active in a zone (`AGENT_ARCHITECTURE.md` §9), that zone's lighting shifts to a red emergency-sweep treatment consistent with real industrial emergency lighting systems — directly continuing the Emergency Control screen's "restrained, functional, never gratuitous" motion discipline (`UI_UX_SPECIFICATION.md` §10) into the lighting system: this state exists because it is informative (it tells anyone glancing at the twin, even without reading a single number, that this zone has an active emergency), not because red lighting looks dramatic.

Volumetric light shafts and bloom post-processing are used sparingly and only where they aid legibility (making a bright flame or an emergency beacon read clearly against a dim interior) — never as ambient atmospheric decoration, consistent with the "calm until it matters" design thesis this entire product family is built around.

---

## 8. Interaction & Selection Systems

### 8.1 Camera Rig

Three camera modes, matching `UI_UX_SPECIFICATION.md` §3's specification, detailed here at the implementation level: **Orbit** (spring-eased rotation around a focus point, snapping smoothly to a newly-selected entity's position); **Walk-through** (first-person free navigation with collision detection against building/equipment geometry, so a user cannot clip through a wall — a small detail with an outsized effect on presence, since clipping through solid geometry is one of the fastest ways a 3D space stops feeling physically real); **Top-down** (an orthographic-projection mode functionally converging with the Factory Map's 2D schematic view, `UI_UX_SPECIFICATION.md` §4, for users who want the wide-area clarity that mode is built around without leaving the 3D application).

### 8.2 Selection: GPU-Based Picking, Not CPU Raycasting

At the object density a fully-modeled plant implies (thousands of individual pieces of equipment, sensors, and dynamic entities simultaneously visible), naive CPU-side raycasting against every mesh in the scene to resolve a click does not scale. Selection instead uses **GPU object-ID picking**: a hidden render pass draws every selectable object with a unique flat color encoding its entity ID, and a click reads back the single pixel under the cursor from that hidden buffer — an O(1) lookup regardless of scene complexity, and the standard technique real-time engines use for exactly this reason.

### 8.3 Selection Highlight Language

A consistent highlight visual — an outline glow — is applied to the currently-selected entity, using **Aegis Cyan** specifically when the selection opens an AI-derived Evidence Drawer (`UI_UX_SPECIFICATION.md` §0.2's "Why?" affordance, extended into the 3D scene) and a neutral highlight color for plain navigational selection with no AI content attached — the same single-purpose color rule (`UI_UX_SPECIFICATION.md` §0.2: Aegis Cyan means "AI-generated," nothing else) holding exactly as strictly in the 3D medium as it does in every 2D screen this series has specified.

---

## 9. Time-Travel, Playback, Historical Replay & Incident Simulation

### 9.1 One Rendering Pipeline, Two Data Sources — Restated at the Feature Level

§1.4 established the architectural precondition; this section is what it enables. **Historical Replay** is not a separate "history mode" of the twin — it is the identical rendering and animation pipeline described in §§2-8, with the Data Binding Layer (§1.4) pointed at a historical query window against `sensor_readings`, `machine_state_history`, `camera_events`, and `risk_scores` (`DATABASE_SCHEMA.md` §20, §21, §14, §10) instead of the live WebSocket feed. Every visual rule established elsewhere in this document — the ghost-vs-solid convention (§6.2), the emergency lighting state (§7.2), the ambient flow animation (§2.2) — applies identically in replay, because it is, structurally, the exact same code executing against a different data source, not a re-implementation.

### 9.2 The Playback Scrubber

A VCR-style control (play/pause/scrub/speed-multiplier) extends the "now" marker concept from the Risk Timeline screen (`UI_UX_SPECIFICATION.md` §9) into full temporal navigation of the 3D scene itself. Scrubbing performance at arbitrary historical depth is what makes this genuinely usable rather than a laggy novelty: rather than querying raw hypertable rows for every scrub-frame (which would be both slow and unnecessary — a human scrubbing a timeline cannot perceive sub-second granularity anyway), the scrubber queries the pre-computed continuous aggregates (`DATABASE_SCHEMA.md` §22.4's `sensor_readings_1min`/`_1hour` rollups) at a resolution matched to the current scrub speed, only dropping to raw-resolution queries when the user pauses and zooms into a specific narrow window for detailed forensic review (`ARCHITECTURE.md` §19.5's Post-Incident Review).

### 9.3 Time Travel as a First-Class Navigation Mode

"Time travel" — jumping directly to an arbitrary past timestamp rather than scrubbing continuously to it — is exposed as its own interaction (a date/time picker alongside the scrubber), because Dr. Kwan's typical investigative workflow (`ARCHITECTURE.md` §4.3 persona) is rarely "watch continuously from now backward" — it's "jump directly to 14:32 on the day of the incident and look around." This mode respects the same document-supersession-aware temporal scoping already established for the RAG system (`RAG_SYSTEM.md` §5.4): any Knowledge Copilot query issued while time-traveled to a past date resolves against the SOP/regulation version that was actually in effect *at that date*, not today's — the 3D time-travel state and the RAG system's `as_of` parameter are the same underlying concept, expressed in two different parts of the product.

### 9.4 Incident Simulation — Clearly Distinguished From Replay

**Replay** renders ground truth — what the stored event log says actually happened. **Incident Simulation** ("what-if," `ARCHITECTURE.md` §16.2's Simulation Layer) renders a hypothetical: a user selects a piece of equipment and a hypothetical failure mode, and the twin projects the consequence forward using the Knowledge Graph's dependency traversal (`KNOWLEDGE_GRAPH.md` §6.1's downstream-impact query) combined with the Risk Fusion Engine's causal-chaining logic (`RISK_FUSION_ENGINE.md` §4.6) to render a plausible cascading-impact visualization. **This is rendered exclusively in the ghost/hypothetical visual language established in §6.2** — dashed boundaries, elevated transparency, a subtly desaturated color grade applied to the entire viewport for the duration of a simulation session — specifically so that switching from Replay (solid, real, ground truth) into Simulation (dashed, hypothetical, a model's projection) is visually unmistakable even to a user who wasn't watching the mode-switch UI control, matching the same non-negotiable convention already stated for Fire (§4.2) and the Predictive Overlay (§6.2): nothing hypothetical is ever rendered with the same visual authority as something observed.

---

## 10. Performance & Scale Considerations

At commercial scale (`ARCHITECTURE.md` NFR-7: 500,000 sensors across 50+ plants), no single client session renders more than one plant's active viewport at full fidelity — the Realtime Gateway's filtered-subscription pattern (`ARCHITECTURE.md` §11.2, "only zones currently in view are subscribed to") applies identically to the 3D scene's data bindings, and off-screen or distant zones fall back to a lower level of detail (§1.3) or unsubscribe entirely rather than maintaining full live bindings for geometry outside the current camera frustum. Repeated identical assets (valve models, sensor icon markers, standard structural elements) render via GPU instancing rather than as independent draw calls, keeping frame cost roughly constant as equipment count grows within a zone. Occlusion culling (not rendering geometry hidden behind other geometry from the current camera angle) and the LOD system from §1.3 are treated as baseline requirements, not later optimizations — a digital twin that only performs acceptably in a small demo plant has not actually validated its own core scalability claim.

---

## Closing Note: How This Experience Fits the Rest of the Series

Nothing in this document introduces a new data source, a new service, or a new autonomy boundary — every rendering system specified here is a *visualization* of a fact this series already established somewhere else: `machine_state_history` drives rotor animation (§3.2), the Knowledge Graph's topology drives both pipeline routing (§2.2) and downstream-impact simulation (§9.4), the Risk Fusion Engine's confidence and time-to-event outputs drive the Predictive Overlay (§6.2), and the event-sourced backbone (`ARCHITECTURE.md` §10) is what makes Replay possible at all (§9.1). What this document adds is the discipline that makes "feel like you're inside the factory" a true statement rather than a marketing line: scale-accurate geometry, motion that only ever reflects real data, and a visual language rigorous enough that a user can always tell, at a glance and without reading a single label, what is real, what is predicted, and what is merely hypothetical.

**End of Document.**

