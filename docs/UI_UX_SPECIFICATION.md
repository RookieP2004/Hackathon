# AEGIS AI — UI/UX Design Specification
### Premium Enterprise Interface for an Autonomous Industrial Safety Operating System

**Classification:** Internal — Design & Product
**Document Owner:** Office of the CTO / Design
**Version:** 1.0
**Companion Document:** `ARCHITECTURE.md` (this spec implements the Frontend Architecture in §7 and the personas in §4 of that document)

---

## How to Read This Document

This document specifies **design intent**, not markup. No React, no CSS — every screen is described in the same terms a design review at Apple, Palantir, or Tesla would use: what the screen is *for*, what it *feels* like to use under stress at 3 a.m., and what happens when things go wrong (empty/loading/error states are not afterthoughts here — for a safety system, the error state is sometimes the most important state in the file).

Every screen section below follows the same 13-part checklist the user requested: **Purpose, Widgets, Animations, Colors, User Interactions, Charts, Live Components, Notifications, Empty States, Loading States, Error States, Mobile Behavior, Accessibility, Dark Mode.**

### 0.1 The Design Thesis

> **Calm until it matters. Undeniable when it does.**

A safety operator who is alarmed 40 times a day for things that don't matter will, provably, stop reacting to the 41st alarm — the one that does. This is "alarm fatigue," the single most-cited root cause in real industrial incident post-mortems (Bhopal, Three Mile Island, Texas City). Every animation, color, and notification decision in this document is filtered through one question: **does this help an operator instantly tell "notice this" from "ignore this," or does it just look impressive?** Apple's restraint, Palantir's density-without-clutter, Tesla's confident dark industrial palette, and Notion's typographic warmth are borrowed for exactly this reason — they are, respectively, the best examples in the industry of clarity, information density, purposeful darkness, and humane software. None of them are decoration references; they are trust-engineering references.

---

## 0.2 Foundational Design System

Every screen in this document is a composition of the following shared system. Screens do not invent their own colors, type, or motion — they select from this palette. This is the design equivalent of the architecture document's shared event schemas (§10.3 of `ARCHITECTURE.md`): a common contract every surface obeys, which is what makes the product feel like *one system* rather than fifteen screens built by fifteen teams.

### Color System

**Dark mode is the primary, default experience** — not a toggle afterthought. Control rooms are dimly lit by design (so operators can see external CCTV monitors and physical annunciator panels without glare), and dark UI matches that environment exactly the way Tesla's Gigafactory wall displays and Palantir's Gotham do. Light mode exists for office/executive use (§4.4 James persona) and is a fully designed peer, not a CSS filter.

**Base neutrals (Dark):**
- `bg.void` `#0A0C0F` — the canvas behind everything; near-black, never pure black (pure black creates halation against bright chart data at night)
- `bg.surface` `#12151A` — card/panel background
- `bg.surface-raised` `#1A1E24` — elevated panels (modals, popovers)
- `border.subtle` `#252A31`
- `text.primary` `#F2F4F7`
- `text.secondary` `#9AA4B2`
- `text.tertiary` `#5B6472`

**Base neutrals (Light):**
- `bg.void` `#F7F8FA`
- `bg.surface` `#FFFFFF`
- `bg.surface-raised` `#FFFFFF` with elevated shadow
- `border.subtle` `#E4E7EC`
- `text.primary` `#0D1116`
- `text.secondary` `#4B5563`
- `text.tertiary` `#8A93A1`

**Semantic severity palette (identical hue-meaning in both modes — this mapping is never reused for anything else in the product, anywhere):**
- `severity.critical` — Red `#E5484D` (dark) / `#D3242C` (light) — imminent risk, requires action
- `severity.high` — Amber `#F5A524` — significant risk, response window exists
- `severity.medium` — Yellow `#E8C547` (desaturated, deliberately less alarming than amber) — watch-list
- `severity.low` — Slate Blue `#6E8FAE` — advisory, informational
- `severity.nominal` — Teal-Green `#2CC295` — safe, healthy, confirmed-resolved

**The AI / Intelligence accent — "Aegis Cyan"** `#3CD8E8` (dark) / `#0891A6` (light): used *exclusively* to mark "this element was generated, computed, or recommended by AEGIS AI's reasoning layer" — a risk score, an AI explanation, a recommended playbook step, the Knowledge Copilot's chat bubble. Raw sensor data is never rendered in this color. This single-purpose rule is a deliberate trust affordance: a user can tell, at a glance and without reading, whether they're looking at ground truth or an inference — directly supporting `NFR-9` (explainability) from the architecture doc.

**Brand accent — "Aegis Indigo"** `#4F5FE8`: chrome, navigation, primary buttons, focus states — structural, not semantic.

### Typography

- **UI Typeface:** A humanist grotesque (Inter or equivalent) — chosen because it renders exceptionally at small sizes with high legibility, the non-negotiable requirement for a data-dense control room UI, while still feeling warm enough (per Notion's influence) not to feel clinical.
- **Data/Telemetry Typeface:** A tabular monospace (e.g., IBM Plex Mono or JetBrains Mono) for every numeric readout — sensor values, timestamps, risk scores, coordinates. Tabular figures mean digits never shift width as they update, so a live-updating pressure reading doesn't visually "jitter" the layout around it — a small detail that reads as expensive, precise engineering the moment you notice it.
- **Type scale:** 12/14/16/20/24/32/48px, 1.5 line-height for body, 1.2 for data-dense tables. Weight is used more than size to create hierarchy (Apple's approach) — most of the UI sits at 13-14px; size jumps are reserved for genuinely different information tiers (a risk score is 32px; its label is 12px).

### Spacing & Grid

8px base unit throughout. A consistent 4px/8px/16px/24px/32px/48px/64px spacing scale. Panels snap to a 12-column responsive grid on desktop, 4-column on tablet, single-column stack on mobile.

### Motion Language

- **Physics-based easing** (spring curves, not linear/ease-in-out CSS defaults) for anything that represents a real state change — this is the Apple/Tesla influence: motion should feel like it has mass, not like a slide layered on top.
- **Severity-tiered motion intensity:** a Nominal→Low state change animates in ~200ms with a subtle fade; a jump to Critical uses a sharper, faster transition (~120ms) paired with a brief (one-cycle) pulse on the affected element — enough to pull the eye, never a strobing or looping animation (looping alarm animations are a proven contributor to control-room fatigue and are explicitly banned in this system).
- **Respect `prefers-reduced-motion` everywhere**, substituting opacity cross-fades for any transform/scale animation — this is treated as a hard accessibility requirement, not optional polish.
- **Never animate purely for delight** on any screen touched during an active incident (Emergency Control, Incident Center) — motion there is 100% functional (draw attention to change, show progress of an action). Delight-oriented micro-motion (gentle hover lifts, easing on non-critical panel transitions) is reserved for low-stakes surfaces (Reports, Settings, Knowledge Copilot).

### Iconography & Depth

- Custom line-icon set, 1.5px stroke, consistent corner radius (4px small components, 12px cards, 20px modals) — rounded enough to feel humane (Notion), not so rounded it feels playful (this is not a consumer app).
- Elevation is communicated primarily through **subtle background-color steps** (per the surface tokens above), not heavy drop shadows — a Palantir/dense-data-UI convention that avoids the "floating card soup" look common to lesser dashboards. Shadows are reserved for true overlays (modals, command palette, toasts) where establishing z-order matters.
- A restrained use of background blur (glassmorphism) **only** on the global command palette and notification tray overlays — anywhere else, and especially never in a live telemetry chart background, where it would degrade data legibility.

### Core Interaction Patterns (used across every screen)

- **The "Why?" affordance** (from `ARCHITECTURE.md` §7.4): any AI-derived value (risk score, explanation, recommendation) carries a small Aegis-Cyan-colored underline-dot affordance. Clicking/tapping expands an **Evidence Drawer** — a right-side sliding panel showing the raw signal chart, the relevant Knowledge Graph neighborhood, and RAG-cited source excerpts. This single interaction pattern is reused everywhere an AI claim appears, so users learn it once.
- **Command Palette** (⌘K / Ctrl+K): global, spotlight-style search/action launcher available from any screen — jump to any equipment, any incident, any report, or run an action ("acknowledge all Zone 3 alerts") without leaving keyboard focus. This is the Notion/Linear influence made literal, and it is what makes the product feel fast to power users (Dr. Kwan, Marcus) rather than click-heavy.
- **Persistent Notification Tray:** a bell icon in the global header, badge-counted by unacknowledged severity, opening a chronological feed — the UI-level counterpart to the Notification Service (`ARCHITECTURE.md` §11.3).
- **Global Status Bar:** a slim, always-visible strip at the very top of the app showing overall plant health (aggregate, one glance, color-coded) and connection status to the realtime gateway — so a user always knows, even while deep in a Report screen, whether "everything is fine right now."

---

## 1. Login

### Purpose
The first impression that tells every persona "this is a serious instrument, not a web app" — and, functionally, the gateway enforcing the Authentication Model (`ARCHITECTURE.md` §20). It must authenticate fast (control-room shift changes cannot afford friction) while looking like the cover of a product a Fortune 500 plant manager would trust with life-safety decisions.

### Widgets
Centered authentication card (max 420px wide) on a full-bleed, subtly animated dark background depicting an abstracted, low-opacity plant schematic (line-art, not photographic — never literal). Above the card: the AEGIS AI wordmark and a one-line tagline ("Autonomous Industrial Safety"). Below the primary email/SSO fields: an organization-picker for multi-tenant deployments (`ARCHITECTURE.md` §24.4), and a small "Badge / PIN" alternate entry mode toggle for shared control-room kiosks (§20.1).

### Animations
On load, the background schematic's line-art very slowly "draws itself" once (a single 1.5s stroke-animation, non-looping) — a restrained, premium touch reminiscent of Apple product pages, never repeated after first paint. The login card fades and lifts in (12px, 300ms spring). Field focus uses a soft Aegis-Indigo glow ring, no color-shifting borders.

### Colors
`bg.void` background throughout; the login card sits at `bg.surface-raised`. Primary CTA button in Aegis Indigo. No severity colors appear on this screen at all — deliberately, since severity color is a vocabulary reserved for plant state, never spent on marketing chrome.

### User Interactions
Standard email/password or "Continue with [Enterprise SSO]" (OIDC federation, §20.1). Badge/PIN mode swaps the card content via a horizontal cross-fade for kiosk terminals. "Forgot password" and MFA challenge (mandatory for Supervisor+ roles per §20.2) appear as sequential card states, not separate pages — preserving the sense of one continuous, calm flow rather than a multi-page bureaucratic process.

### Charts
None — intentionally. A login screen with data visualization is a design smell (nothing to visualize yet, and it would undercut the "calm" register before the user even reaches the plant).

### Live Components
A tiny, unobtrusive system-status indicator in the footer ("All AEGIS services operational" with a small teal dot, sourced from the platform's own health-check, tying back to `ARCHITECTURE.md` §25.3) — so even before login, a returning user senses the platform's own reliability posture.

### Notifications
None pre-auth. Post-MFA, a single toast confirms "Welcome back, [Name]" naming their role, immediately orienting them.

### Empty States
N/A (this screen has no data-dependent content).

### Loading States
Submit button transitions to an inline spinner *inside* the button (button retains its size/position — never a full-page spinner replacing the card, which would feel unstable). SSO redirect shows a brief branded interstitial ("Redirecting to your organization's identity provider…") rather than an abrupt blank redirect.

### Error States
Invalid credentials: the password field shakes very subtly (one 80ms horizontal oscillation, respecting reduced-motion) and an inline red-bordered message appears below the field — never a modal, never a page-level banner for something this routine. Account-locked or MFA-failure states get a distinct, calmer amber (not red) message directing the user to their Admin, since this is a process problem, not a security alarm.

### Mobile Behavior
Full-screen card (no floating card on a background) on the mobile Maintenance app (§7.1); biometric (Face ID/fingerprint) unlock is the default re-entry mode after first login, since Tasha (§4.5) is frequently re-authenticating between inspection sites.

### Accessibility
All fields fully labeled (not placeholder-only labels — a common and serious accessibility failure); tab order is logical top-to-bottom; error messages are announced via `aria-live` regions; contrast ratios validated at WCAG AAA for this screen specifically, since it is the one screen every single user, regardless of ability, must complete alone before any assistive configuration in their profile can even load.

### Dark Mode
This screen is authored dark-first; the light-mode variant swaps the background schematic to a light desaturated line-art on `bg.void` (light) and is used automatically when the OS-level preference is light, or when accessed from an office network context in future personalization — but dark is the canonical, default brand expression here.

---

## 2. Dashboard (Command Center)

### Purpose
The home screen — a role-adaptive command center answering, within two seconds of landing, the one question every persona shares: **"is everything OK, and if not, where do I look first?"** This is not one screen but one *layout template* populated differently per role (§21.2): Priya (Operator) sees her assigned zones' live risk feed front and center; Marcus (Supervisor) sees a cross-zone overview with escalation controls; James (Plant Manager) sees an executive rollup. The template is shared (per `ARCHITECTURE.md` §7.2's "shared widgets, role-specific composition" principle); this section specifies the Operator/Supervisor configuration as the primary reference, noting Executive variance at the end.

### Widgets
- **Plant Health Score** — a large (hero-sized) circular gauge, top-left, aggregating all zone risk into one 0-100 number with severity-color arc.
- **Ranked Risk Feed** — a vertically scrolling list of currently-elevated equipment/zones, sorted by (severity, time-to-event ascending) — the single most important widget on the page, styled like a premium activity feed, not a bootstrap table: each row is a card with equipment name, mini risk-trend sparkline, severity chip, and predicted time window.
- **Zone Overview Grid** — a compact grid of zone tiles (color-coded by worst-case severity within that zone), click-through to Factory Map filtered to that zone.
- **Live Incident Strip** — a slim horizontal strip of currently open incidents (if any), each an actionable chip.
- **Digital Twin Mini-Viewport** — a small embedded, live 3D/2D twin preview (§16), click to expand to the full Digital Twin screen.
- **Recent Activity Timeline** — condensed feed of acknowledgments, escalations, closed incidents — social-proof-style transparency into what the team has already handled.

### Animations
Risk Feed cards use FLIP-style reordering animation when priority changes (a card smoothly slides to its new rank position rather than the list jump-cutting) — this single animation does enormous trust-building work, because a user visually *sees* something's risk rising rather than just noticing a number changed. Plant Health Score gauge arc animates via a spring easing whenever it changes, with the numeral counting up/down digit-by-digit (odometer-style) rather than snapping.

### Colors
Severity palette governs almost the entire visual weight of this page — it is, intentionally, the screen where the semantic color system carries the most meaning. Nominal/all-clear state is deliberately quiet: mostly neutral grays with small teal accents, so that when something turns amber or red, it is the only saturated color on the screen and impossible to miss.

### User Interactions
Click any Risk Feed card to open its Evidence Drawer (§0.2) without navigating away. One-click "Acknowledge" and "Escalate" buttons inline on each card (optimistic UI update, per `ARCHITECTURE.md` §7.1's warm-state caching strategy). Zone tiles are draggable-reorderable per-user (Priya can pin her primary zones to the top) — a small personalization touch that meaningfully reduces scan time over a shift.

### Charts
Sparklines (60-90 second lookback, minimal axis chrome) embedded per risk-feed card. The Plant Health Score gauge is a radial/arc chart. A small multi-series area chart ("Risk Trend — Last 24h," stacked by severity band) sits below the fold for pattern-spotting across a shift.

### Live Components
Everything on this page is WebSocket-driven (§11.2) — Risk Feed, Zone Grid, Health Score, and Twin Mini-Viewport all update in place without page refresh or visible re-render flicker (state is patched, not replaced, per the architecture's diff/patch rendering strategy in §16.4).

### Notifications
New Critical/High items entering the Risk Feed trigger a brief, non-blocking **inline highlight flash** on the newly-inserted card (a single 400ms background pulse in the relevant severity color) plus a toast in the corner if the user's focus is elsewhere in the app, plus the persistent Notification Tray badge increment — three tiers of the same event, scaled to how likely the user is to already be looking.

### Empty States
An all-nominal plant state is not treated as "nothing to show" — it's an intentional, calm state: the Risk Feed area displays a clean confirmation ("All systems nominal — 214 sensors, 38 equipment units monitored") with a subtle teal checkmark motif, avoiding the awkward "empty dashboard" feeling common to lesser products while still being unmistakably different from a loading or error state.

### Loading States
Skeleton screens (shimmering placeholder shapes matching each widget's exact final layout) on first load — never a centered spinner replacing the whole page, since that would hide the layout structure the user is about to orient around. Widgets populate independently and asynchronously as their data sources resolve (a slow Knowledge Graph query for one widget never blocks the Risk Feed from appearing).

### Error States
If the Realtime Gateway connection drops, the Global Status Bar (§0.2) turns amber with "Reconnecting…" and every live widget freezes its last-known values with a subtle diagonal-hatch overlay treatment (a well-established "stale data" visual convention) rather than blanking — an operator must never be shown a *false* all-clear from an empty/blank state during a connectivity gap, per `NFR-2`/`NFR-3`'s no-shared-failure-domain principle.

### Mobile Behavior
Widgets stack single-column, Risk Feed becomes the dominant, nearly full-screen element (the Plant Health gauge shrinks to a compact header chip); Zone Grid becomes a horizontally swipeable carousel. This is a secondary experience for this particular screen — the primary mobile surface is the Maintenance work-order flow (§7 Mobile screen coverage below) — but Supervisors do check this on-the-go, so full functionality is retained, just re-flowed.

### Accessibility
Severity is always paired with an icon and text label, never color alone (WCAG 1.4.1) — critical given this screen's reliance on the severity palette. All live-updating regions use polite `aria-live` announcements throttled to avoid screen-reader flooding during high-alert periods (announcing only net-new Critical/High entries, not every sparkline tick). Full keyboard navigation across Risk Feed cards with visible focus rings.

### Dark Mode
Canonical/default. The severity palette values specified in §0.2 are tuned for dark backgrounds first (higher luminance, tested for sufficient contrast against `bg.void`); light mode uses the light-tuned severity values, and screenshots/exports (§12 Reports) default to light mode for print-friendliness regardless of the user's live app theme preference.

### Executive Variant (James / Plant Manager)
Replaces the Ranked Risk Feed's operational density with a higher-level summary: open incident count, month-over-month "predicted and averted" ROI counter (tying to `ARCHITECTURE.md` §26.3's North Star metric), and a trend-focused layout — same widget shells, different data granularity and reduced interaction density, consistent with the "role-adaptive template" principle stated above.

---

## 3. Digital Twin

### Purpose
The immersive, spatial expression of the Digital Twin Service (`ARCHITECTURE.md` §16) — the screen that makes AEGIS AI feel less like a dashboard and more like an operating system for a physical place. This is the "wow" surface for demos and executive tours, but it earns its place operationally too: Priya and Marcus use it to understand *where* a risk physically sits relative to personnel, adjacent equipment, and escape routes — spatial context a table of numbers cannot convey.

### Widgets
Full-viewport 3D scene (WebGL) of the plant with a floating, semi-transparent left rail for Zone/Equipment selection tree and a right rail Evidence/Detail panel that slides in on selection. A bottom-center floating control bar handles camera modes (Orbit / Walk-through / Top-down), layer toggles (show/hide piping, show/hide personnel, show thermal overlay), and a time-scrubber (see below). Equipment is rendered as clean, slightly stylized low-poly geometry (never attempting photorealism — photorealism would set an unmeetable fidelity expectation and date badly; stylized-but-precise is the Apple Maps/Tesla approach and ages well).

### Animations
Camera transitions between equipment selections use smooth eased flythrough (600-900ms), never an instant cut — spatial continuity is what makes a 3D view actually useful for building a mental map, versus disorienting jump-cuts. Risk-level color washes over equipment surfaces as a soft emissive glow (not a harsh solid-fill recolor) that pulses gently exactly once when severity changes tier, then settles to a steady glow — consistent with the "no looping alarm animation" rule in §0.2.

### Colors
Base scene rendered in cool neutral grays/blues (an "engineering blueprint at night" register) so that severity-colored glows on at-risk equipment read as unambiguous figure-against-ground. Personnel markers (from Worker Tracking, §6) render in a distinct neutral human-icon color, never overlapping the severity vocabulary.

### User Interactions
Click/tap any equipment node to open its Evidence Drawer and Machine Health quick-summary. Drag to orbit, scroll/pinch to zoom, right-click-drag to pan (desktop); standard touch equivalents (mobile/tablet, primarily for Marcus's on-floor tablet use). A **"What-If" mode toggle** invokes the Simulation Layer (§16.2): selecting equipment and activating What-If highlights the downstream dependency subgraph (traced live from the Knowledge Graph) with an animated "impact ripple" propagating outward from the selected node, frame by frame — a genuinely delightful, information-dense interaction that directly visualizes `ARCHITECTURE.md` FR-11.

### Charts
No traditional charts live in the 3D viewport itself (charts belong in the Evidence Drawer/Sensor Analytics) — the twin's "chart" *is* the spatial scene. A compact sparkline strip appears in the Evidence Drawer when equipment is selected.

### Live Components
The entire scene is a live client of the Twin's WebSocket state feed (§16.4) — glows, sparklines, and personnel positions update continuously; the scene never needs a manual refresh. A connection-quality indicator sits unobtrusively in the corner of the viewport specifically for this screen, since a stale 3D scene is a uniquely dangerous kind of wrong (visually confident, silently outdated).

### Notifications
New Critical anomalies trigger a camera "suggestion" — a small, dismissible floating prompt ("New critical risk detected on V-12 — View?") rather than an automatic camera hijack, because ripping control of a 3D camera away from a user mid-navigation is disorienting and a well-documented UX anti-pattern in spatial interfaces.

### Empty States
An unconfigured or newly-onboarded zone with no topology yet renders as a soft wireframe placeholder with a "Zone topology not yet configured — visit Admin to import layout" prompt (linking to §15 Admin) rather than an empty black viewport, which would look broken rather than intentionally empty.

### Loading States
The 3D scene loads with a progressive reveal — the base structural geometry (piping, buildings) resolves first (fast, low-poly), then equipment detail and live state layer in — communicated via a slim top-of-viewport progress bar, never a blocking spinner over the whole canvas, since partial scene exploration during load is both possible and useful.

### Error States
If the twin's state feed disconnects, the scene freezes with a desaturating filter applied to the entire viewport (a deliberate, unmistakable "you are looking at a photograph, not reality" visual cue) plus a persistent banner, directly preventing the dangerous failure mode of a stale-but-vivid 3D scene being mistaken for live truth.

### Mobile Behavior
On the Maintenance mobile app, the Digital Twin renders in the lightweight 2D schematic mode only (§16.2's Topology Layer rendered as SVG, not the full WebGL 3D scene) — this is a deliberate, stated trade-off (`ARCHITECTURE.md` §7.1) prioritizing battery life and load time on field devices over visual fidelity a technician standing in front of the actual equipment doesn't need anyway.

### Accessibility
The 3D view is supplemented, not replaced, by a fully keyboard/screen-reader-navigable equivalent: the left-rail Zone/Equipment tree is a complete, accessible alternative path to every piece of information and every action available in the 3D scene — no capability is 3D-view-exclusive, satisfying the principle that a rich visualization must always have a structured-data equivalent.

### Dark Mode
Canonical/default — the "engineering blueprint at night" aesthetic described above essentially *is* this screen's dark mode. Light mode renders the base scene in a lighter blueprint-paper register (warm off-white structural lines) — used for print/export snapshots (e.g., embedding a twin view in a Report, §12) more often than live interactive use.

---

## 4. Factory Map

### Purpose
The operational, top-down, geography-first counterpart to the Digital Twin — where the Twin answers "help me understand this equipment's context," the Factory Map answers "where, physically, on the plant floor, is everything right now, at a glance, across the whole site." This is the screen a Supervisor keeps open on a secondary monitor throughout a shift.

### Widgets
A precise 2D top-down schematic (SVG-based, per `ARCHITECTURE.md` §16.2's Topology Layer) with zone boundaries, equipment icons, sensor markers, camera FOV cones, and live personnel dots. A left-side filterable layer control (Sensors / Cameras / Personnel / Risk Overlay / Escape Routes). A right-side selected-item detail panel. A persistent legend (collapsible) explaining every icon and color — an explicit anti-clutter/anti-mystery-meat-icon decision, since this map will be read by people under stress who cannot afford to guess what a symbol means.

### Animations
Risk overlay renders as a soft, low-opacity heat-gradient wash over zone polygons (not per-pixel noisy heatmap — a clean, zone-bounded gradient) that eases between severity states over 300-500ms. Personnel dots move via interpolated easing between position updates (never teleporting/snapping) so movement reads as continuous, real motion rather than a data refresh artifact.

### Colors
Same severity palette as the Dashboard, applied to zone-fill washes at low opacity (10-20%) so underlying schematic detail (pipe runs, equipment outlines) always remains legible beneath the risk overlay — a deliberate restraint decision distinguishing this from a "solid red zone" treatment that would obscure the very detail a Supervisor needs during a high-risk moment.

### User Interactions
Click a zone to filter the entire app context to it (Dashboard, Incident Center, etc. all respect a global "active zone filter" set from this screen — a Palantir-style "pivot the whole workspace around this selection" interaction). Hover any equipment/sensor icon for an instant tooltip (value + status, no click required) — critical for the rapid-scan use pattern this screen is built for. Draw-a-box multi-select to batch-acknowledge or batch-inspect a cluster of sensors.

### Charts
Minimal — this screen is spatial, not analytical. A small inline sparkline appears in hover-tooltips only.

### Live Components
Personnel positions (from Worker Tracking's CV-derived location data, §18.1), sensor status dots, and zone risk overlays are all live WebSocket-driven, at the throttled/sampled rate specified in `ARCHITECTURE.md` §11.2 (only the zones currently in viewport are subscribed to, bounding bandwidth at scale).

### Notifications
A "someone entered a zone currently flagged high-risk" event (the intersection of Worker Tracking and Risk data) is the single highest-priority notification type on this screen — rendered as an urgent, distinctly-styled banner (not just another toast) because this specific event class represents actual, immediate physical danger to a person, distinct from equipment-only risk.

### Empty States
A zone with no personnel and no active sensors reads with simple, low-contrast "unoccupied / unmonitored" iconography — clearly different from an error, since an unmonitored storage zone is often entirely expected, not a data gap.

### Loading States
The schematic's static geometry (walls, zone boundaries) renders instantly from cached/versioned topology data (rarely changes, per §16.2); only the live overlay layers (personnel, risk, sensor status) show a brief shimmer while the WebSocket subscription establishes — a fast, layered load matching the Digital Twin's approach.

### Error States
Loss of camera/CV feed (affecting personnel-tracking accuracy) is surfaced as a specific, scoped warning icon on the affected zone ("Personnel tracking degraded in Zone 4 — last confirmed position 2 min ago") rather than a generic connection error, because the *specific kind* of stale data matters enormously for a Supervisor deciding whether it's safe to authorize entry.

### Mobile Behavior
Fully supported on Marcus's floor tablet (this is one of the most-used screens in tablet form) with pinch-zoom/pan; on phone-sized viewports it defaults to a zone-list view with a "view map" toggle, since a full plant schematic is not meaningfully readable below a certain screen size — degrading gracefully to a list is preferable to a cramped, useless minimap.

### Accessibility
Every spatial relationship communicated visually is also available via the same accessible Zone/Equipment tree pattern established in the Digital Twin screen (§3) — screen-reader users navigate identical underlying data through a structured list, never losing information relative to sighted map users.

### Dark Mode
Canonical/default, matching the Digital Twin's blueprint-at-night register for visual consistency between these two closely-related spatial screens — a deliberate design-system decision so switching between Twin and Map never feels like entering a different product.

---

## 5. Incident Center

### Purpose
The system of record for every Incident (`ARCHITECTURE.md` §19, the Incident Service) — a hybrid of an inbox and a case-management tool, built for triage speed (Priya/Marcus, live incidents) and forensic depth (Dr. Kwan, closed-incident review). This screen is the single most legally/operationally significant surface in the product, since it *is* the auditable record `NFR-17` requires.

### Widgets
Left: a filterable, sortable incident list (status: Open/Acknowledged/Escalated/Closed; severity; zone; date range) styled as clean rows, not a dense spreadsheet grid — each row surfaces severity chip, equipment, one-line AI-generated summary, and elapsed time. Right (on selection): the **Incident Detail panel** — a vertical timeline (mirroring the exact event sequence from `ARCHITECTURE.md` §10.3's `incident.*`/`action.*` topics: opened → evidence → notified → acknowledged → playbook proposed → approved/executed → field-confirmed → closed), each timeline entry expandable to its full evidence. A persistent action bar (Acknowledge / Escalate / Add Note / Close) pinned above the fold regardless of scroll position.

### Animations
New incoming Critical incidents animate into the top of the list with a brief lift-and-settle (never a jarring insert) plus a one-time severity-colored edge-glow on the row that fades over ~2s — attention-getting without being alarming enough to spike stress on an already-tense floor. Timeline entries reveal with a staggered fade (60ms delay per item) on first open, giving the case history a satisfying, considered "unfolding" quality appropriate to its seriousness.

### Colors
Severity chips as established; the timeline itself uses a neutral vertical rule with severity-colored dots at state-transition points, and Aegis Cyan specifically marks any AI-authored timeline entry (the risk detection, the AI-generated summary, the recommended playbook) versus human-authored entries (in `text.primary` neutral) — making it visually explicit, in the legal record itself, which parts of this incident's story were machine-generated versus human-decided.

### User Interactions
Click a list row to load detail without full navigation (persistent list context, split-view pattern). Inline "Add Note" supports @mentioning other roles (routes a targeted notification). A "Compare to Similar Incidents" button surfaces the Knowledge Graph's `SIMILAR_TO` relationships (§13.2) as a horizontal card carousel — directly exposing FR-10's evidence-citation requirement as a first-class interaction, not a buried feature.

### Charts
A small "risk trajectory" line chart at the top of the Detail panel showing the relevant signal(s) across the incident's full timespan, with the actual threshold-crossing moment marked — this is frequently the single most-referenced chart in a post-incident review, so it is never buried behind a click.

### Live Components
Open incidents update live (new evidence, status changes from other users) via WebSocket, with a subtle "updated" indicator if a user is viewing a detail panel that changes underneath them (never silently rewriting content a user is actively reading — the update is flagged, and the user chooses to refresh the view).

### Notifications
Every state transition on an incident a user is subscribed to (assigned, mentioned, or watching) triggers a toast; Critical incident creation additionally triggers the full escalation-ladder channels per `ARCHITECTURE.md` §11.3 outside the app entirely (push/SMS/call).

### Empty States
"No open incidents" renders with the same calm, confirmatory tone as the Dashboard's all-nominal state — explicitly avoiding any hint that an empty incident list is itself something to worry about or double-check.

### Loading States
List uses skeleton rows; Detail panel uses a skeleton timeline shape, both matching the final layout precisely (as established system-wide) so the eye already knows where to look before data arrives.

### Error States
A failed action (e.g., "Close Incident" fails to persist) surfaces an inline, specific error directly in the action bar ("Couldn't close — retry" with a retry button) and explicitly does *not* optimistically mark the incident closed in the UI until server confirmation — safety-record actions are the one place in this entire product where optimistic UI (used elsewhere for responsiveness) is deliberately not used, because a false "closed" state on an incident record is a compliance risk.

### Mobile Behavior
List/detail collapses to a single-pane, back-navigable stack on phone; the action bar remains pinned to the bottom of the viewport (thumb-reachable) rather than the top, adapting to mobile ergonomics.

### Accessibility
Timeline is structured as a proper ordered list in the DOM/accessibility tree (not just visually sequential divs), fully navigable and announced by screen readers as "step 3 of 7" style context. All actions have full keyboard shortcuts (documented in the Command Palette, §0.2).

### Dark Mode
Canonical/default; PDF/print export of an incident (for regulatory submission, tying to §12/§13 Reports and Compliance) always renders in a dedicated high-contrast light print stylesheet regardless of live theme, since this document may be read by a regulator with no relationship to the live app at all.

---

## 6. Worker Tracking

### Purpose
Real-time personnel-safety awareness — where every person is, relative to every risk zone, sourced from the Computer Vision Service's intrusion/occupancy detection (`ARCHITECTURE.md` §18.1). This is the screen with the highest ethical-design bar in the entire product: it is workplace personnel monitoring, and it must read, unambiguously, as a *safety* tool protecting workers — never a surveillance/productivity-monitoring tool watching them.

### Widgets
A roster-style list (not a map — the map view of this same data lives in Factory Map §4) of currently on-site personnel: name/role/badge ID, current zone, time-in-zone, and a safety-relevant status chip (Nominal / In Elevated-Risk Zone / PPE Non-Compliant / Unconfirmed Location). A "Zone Occupancy" summary card cluster showing headcount per zone against each zone's configured safe-occupancy limit. No individual movement history/trails are shown by default — only current position — a deliberate privacy-preserving design default (see Accessibility/Ethics note below).

### Animations
Status chip changes (e.g., a worker entering a zone that becomes high-risk while they're in it) animate with the same restrained severity-tier pulse used system-wide — this is one of the highest-stakes notification types in the product (§4 Factory Map's cross-reference), so consistency with the established "serious but not alarming" motion language matters even more here.

### Colors
Standard severity palette for status chips; person markers/avatars use a neutral, non-severity color family (cool gray/indigo) specifically so a "person" is never visually confusable with a "risk" — an important perceptual-safety distinction on a screen literally about protecting people.

### User Interactions
Click a roster row to locate that person on the Factory Map (cross-navigation, preserving context). Supervisors (only, per RBAC §21.2) can issue a direct "Evacuate Zone" broadcast action from this screen, which routes into the Emergency Response Workflow (§19)/Emergency Control screen (§10).

### Charts
A simple horizontal bar per zone (current occupancy vs. safe limit) — intentionally the simplest chart type in the entire product, because this data needs to be understood in under one second, not analyzed.

### Live Components
Roster and occupancy counts update live from the CV pipeline's `vision.inference` derived positions (§18.2), including the temporal-smoothing guarantees from that pipeline — meaning this screen inherits the CV architecture's false-positive suppression, an important trust point given how consequential a wrong "unconfirmed location" flag would be.

### Notifications
"Worker in elevated-risk zone" is escalated with the same urgency as the equivalent Factory Map alert (§4) — these are the same underlying event, surfaced consistently across both screens. Occupancy-limit-exceeded triggers a distinct, lower-urgency advisory (a capacity/compliance concern, not necessarily an active hazard).

### Empty States
Off-shift/unoccupied plant states show a simple "No personnel currently on site" message — common and expected outside working hours, styled neutrally, not as a gap or error.

### Loading States
Roster loads with skeleton rows; occupancy bars animate in from zero on load (a small, appropriate moment of delight-motion since this screen, while safety-relevant, is lower-stakes moment-to-moment than Incident Center or Emergency Control).

### Error States
"Location tracking degraded" (camera outage, poor CV confidence) is shown per-affected-zone/person with an explicit timestamp of last confirmed sighting — never silently dropping a person from the roster, since an unexplained disappearance from a safety roster is itself alarming and must instead read as "we don't currently know, here's what we last knew and when."

### Mobile Behavior
Marcus's tablet gets the full roster + occupancy view; the phone-sized Maintenance app surfaces only the current user's own "you are currently tracked in Zone X" self-status, plus any personal evacuation alerts — not the full roster (least-privilege by default even before RBAC is factored in, appropriate for a field worker's own device).

### Accessibility & Ethics Note
This screen deliberately **does not** expose historical movement trails, dwell-time analytics, or any productivity-framed metric (e.g., no "time spent per task") in its default view — the data model may support it at the service layer for legitimate safety-audit purposes (accessible only to Safety Officer role with a stated safety justification, logged per §21.5's access-audit requirement), but the Worker Tracking screen's default UI surface is scoped tightly to present-tense physical safety, both because that is the legitimate use case and because over-scoping this screen would erode the frontline workforce trust the entire system depends on to function (an operator who feels surveilled hides problems instead of reporting them — the opposite of AEGIS AI's purpose).

### Dark Mode
Canonical/default, consistent with the rest of the operational surfaces.

---

## 7. Machine Health

### Purpose
The single-equipment deep-dive — everything AEGIS AI knows about one piece of equipment (a specific valve, pump, reactor), aggregating live sensor state, historical maintenance record, Knowledge Graph relationships, and AI risk assessment into one authoritative "spec sheet for a living machine." This is where Tasha (Maintenance) and Dr. Kwan spend the most sustained, careful attention of any persona.

### Widgets
A header block: equipment name/tag/type/photo-or-render, current status chip, and a prominent Risk Score gauge with time-to-event if elevated. Below: a tabbed body — **Live Telemetry** (all sensors monitoring this equipment, §17.1's classes, each a compact live chart), **Health History** (a long-range degradation trend chart plus maintenance record timeline), **Relationships** (a focused Knowledge Graph mini-view showing this equipment's direct connections — feeding into/from, per §13.2), and **Documentation** (RAG-linked manual sections, §14, directly attached to this specific equipment node).

### Animations
Tab switches use a simple, fast cross-fade (150ms) — this screen favors information density and fast task-switching over expressive motion, appropriate to its "reference document" character rather than a "live monitoring" character (contrast with the Dashboard's more animated feel).

### Colors
Standard severity palette for the header risk gauge; the Health History degradation chart uses a distinct muted-purple accent (a chart-specific color, not part of the severity/AI/brand vocabulary, deliberately — this chart shows a *trend*, not a current alarm state, and must not visually compete with true severity signals elsewhere on the page).

### User Interactions
Any sensor's live chart can be clicked to jump directly into Sensor Analytics (§8) pre-filtered to that exact signal — this screen is a hub that routes into deeper analytical tools rather than replicating them. A "Request Maintenance" button creates a work order directly (feeding Tasha's queue), pre-populated with the AI's predicted failure mode and relevant manual excerpt — a direct product expression of the FR-12/FR-14 dispatch flow from the architecture doc.

### Charts
Multiple: live sparkline-to-full-chart per monitored sensor; a long-range (weeks/months) degradation trend line with confidence band; a maintenance-event overlay (vertical markers on the trend chart showing when service occurred) so a viewer can visually correlate "we serviced it here, and see how the trend responded."

### Live Components
Live Telemetry tab charts stream continuously; the header Risk Score updates in place with the same odometer-digit and arc-animation treatment as the Dashboard's Plant Health Score, for cross-screen consistency.

### Notifications
If this equipment's risk score changes while a user has the page open, a subtle, non-disruptive banner ("Risk score updated — refresh view") appears rather than silently jumping numbers around mid-read, preserving the reader's place, especially important given how much careful reading (manual excerpts, relationship graphs) happens on this specific screen.

### Empty States
Newly onboarded equipment with no accumulated history yet shows a clean "No maintenance history recorded yet" placeholder in the Health History tab with a prompt to log baseline data — distinct from a data-loss error, and framed positively (a fresh asset, not a problem).

### Loading States
Header loads first (fastest query), then tabs populate independently as their respective services (Knowledge Graph, RAG, Time-Series DB) respond — consistent with the system-wide principle of never blocking fast data behind slow data.

### Error States
If the Knowledge Graph service is unreachable, the Relationships tab specifically shows a scoped error ("Relationship data temporarily unavailable") while every other tab continues functioning normally — a direct UI expression of the architecture's service-isolation principle (`NFR-14`): one dependency's outage degrades one tab, not the page.

### Mobile Behavior
This is a core Maintenance mobile-app screen (Tasha's primary reference in the field) — tabs become a bottom sheet swipe-between pattern; the Documentation tab gains an offline-cached mode (per `ARCHITECTURE.md` §7.5's connectivity-tolerance requirement) since technicians frequently work in shielded, signal-dead structures.

### Accessibility
The Relationships graph mini-view has a full accessible list-equivalent (same pattern as Digital Twin/Factory Map, §3/§4); all charts have an accessible data-table alternative view (a toggle, not hidden/removed), meeting the general principle that no information on this content-dense screen is visualization-exclusive.

### Dark Mode
Canonical/default; the Documentation tab's manual-excerpt reading view gets a slightly warmer, higher-contrast "reading mode" background variant (still dark, but optimized for sustained text reading rather than glanceable monitoring) — a subtle, considered typographic-comfort touch appropriate to Notion's influence on this specific sub-surface.

---

## 8. Sensor Analytics

### Purpose
The power-user analytical workbench for raw telemetry — where Dr. Kwan and engineering-minded operators go to explore, correlate, and validate signals directly, independent of any AI interpretation layer. This screen is the deliberate "show your work" counterpart to the AI's summarized risk scores elsewhere: full access to Layer 1 (`ARCHITECTURE.md` §9.1) ground truth.

### Widgets
A flexible multi-chart workspace: a sensor/signal picker (searchable, Command-Palette-integrated) adds signals as overlaid or stacked chart panes; a shared time-range control governs all panes simultaneously; an annotation layer lets users mark up charts with notes (persisted, shareable via link — a lightweight collaboration feature). A statistics side-panel shows live computed stats (mean, std-dev, rate-of-change, last N-minute trend slope) for the currently-focused signal.

### Animations
Chart panes resize/rearrange with a smooth grid-reflow animation when panes are added/removed; zoom/pan on time-series charts uses momentum-based easing (a "flick to scroll" physicality) matching modern professional charting tools (Bloomberg Terminal/TradingView-caliber feel, explicitly referenced here as the bar for this screen specifically, distinct from the calmer register elsewhere in the product — this is the one screen where a more kinetic, tool-like feel is appropriate because its users are expert, focused, and task-driven rather than glancing under stress).

### Colors
Signal lines use a curated categorical palette (distinct hues per overlaid signal, colorblind-safe order) — this is the one place in the entire system where color is used for *identity* (which signal is which) rather than *severity*, and the UI clearly separates these registers (a small legend swatch beside each signal name, never reusing the severity red/amber/yellow vocabulary for a signal that simply happens to be, say, colored orange in the chart).

### User Interactions
Drag-select a time range on any chart to zoom (with a "reset zoom" affordance always visible); right-click a signal for a context menu (add to Evidence Drawer, export raw data, compare to similar equipment's same signal via Knowledge Graph). Multi-signal correlation mode overlays a computed correlation coefficient between two selected signals directly on the chart — exposing, in a controlled/scoped way, a taste of the Layer 2 cross-signal reasoning (§9.1) as a manual, user-driven tool rather than only an automated background process.

### Charts
The core content of this entire screen: line charts (primary), with optional bands (upper/lower control limits, statistically derived) overlaid to visualize exactly what Layer 1's anomaly detection is comparing against — directly supporting the explainability principle by letting a skeptical engineer see the *actual statistical model boundary*, not just its verdict.

### Live Components
Charts can toggle between "live tail" mode (continuously scrolling, like a heart-rate monitor) and "frozen/historical" mode (for careful analysis without data moving underneath the cursor) — an explicit, user-controlled mode switch, since live-scrolling data is actively hostile to the kind of careful inspection this screen is for.

### Notifications
Minimal by design — this is a pull, not push, screen. The only notification type here is a subtle badge if a signal currently open in the workspace crosses an anomaly threshold while being viewed, so a user mid-analysis doesn't miss it.

### Empty States
A freshly opened workspace shows a clean "Search or select a signal to begin" prompt with the Command Palette pre-focused — treating the blank canvas as an invitation (a whiteboard, Notion/Figma-style empty-state framing) rather than a deficiency.

### Loading States
Individual chart panes load independently with a shimmer matching final axis/legend layout; large historical range queries show a determinate progress indicator (since these can genuinely take a few seconds against the Time-Series DB per `ARCHITECTURE.md` §12.1) rather than an indeterminate spinner, respecting the user's time.

### Error States
A query exceeding a sane time/data-volume bound (e.g., requesting a year of 100Hz data across 50 signals) is caught proactively with a clear, specific message suggesting a downsampled or narrower alternative — never a silent timeout or a browser-crashing render attempt.

### Mobile Behavior
Explicitly a secondary, view-only experience on mobile (single-signal, single-pane, no multi-overlay authoring) — this is a deliberate scope reduction, not an oversight: deep analytical work of this kind is understood to be a desktop task, and pretending otherwise would produce a compromised experience on both platforms.

### Accessibility
Every chart has a "view as data table" toggle (raw values, sortable) — the single most important accessibility affordance on this screen given how central visual charting is to its purpose; keyboard shortcuts for zoom/pan/reset are documented and consistent with the Command Palette's conventions.

### Dark Mode
Canonical/default; this screen additionally offers a dedicated **high-contrast chart theme** (opt-in, in Settings §14) for extended analytical sessions or for users with specific visual needs, independent of the overall app theme — a level of per-screen personalization justified by how much time power users spend here.

---

## 9. Risk Timeline

### Purpose
The temporal, predictive counterpart to Sensor Analytics' signal-level view — this screen visualizes Layer 3's survival-analysis output (`ARCHITECTURE.md` §9.1: risk score and time-to-event, over time) across equipment, zones, or the whole plant, answering "how has risk evolved, and where is it forecast to go" rather than "what is the raw signal doing." This is the screen that makes AEGIS AI's *predictive* (not just reactive) value proposition visually undeniable — the hackathon-judge "wow, it saw this coming" moment lives here.

### Widgets
A large horizontal timeline chart spanning past (solid, observed risk) into future (dashed/gradient-faded, predicted risk band) with a clear "now" marker (a vertical line, always present, anchoring the view). Below it, a filterable equipment/zone selector lets a user swap what the timeline represents. Incident markers (from Incident Center, §5) are pinned directly onto the timeline at their historical moment, so predicted-risk-rise and actual-incident-occurrence can be visually compared — the single most powerful trust-building visual in the product, since it lets any skeptical viewer verify "did the prediction actually lead the event."

### Animations
The "now" marker's transition from past-to-future rendering styles (solid to dashed) uses a subtle animated gradient sweep rather than a hard visual seam — communicating "this is where certainty ends and forecast begins" as a felt visual quality, not just a legend note. New predictions extending the forecast band animate in with a gentle draw-on (the line "growing" rightward), reinforcing the sense of a living forecast rather than a static chart.

### Colors
The observed-past portion uses standard severity-band coloring (a stacked/colored area beneath the risk line); the predicted-future portion uses the same severity coloring but at reduced opacity with a soft outer gradient fade at the far edge of the forecast horizon — visually encoding "confidence decreases the further out we predict," a direct visualization of the uncertainty quantification principle in `ARCHITECTURE.md` §9.4.

### User Interactions
Hover anywhere on the timeline for a tooltip showing the exact score, confidence band, and (for predicted points) the top contributing factors — the "Why?" affordance (§0.2) embedded directly in the hover state for maximum efficiency on this particular screen. Click an incident marker to jump directly into that Incident's detail (§5). A comparison mode overlays two time periods (e.g., "this week vs. last week") as two distinct lines for trend analysis.

### Charts
This entire screen is, essentially, one large, richly-annotated area/line chart — the most visually sophisticated chart in the product, warranting the most design polish (gradient fills, careful axis typography, precise "now" marker treatment) of any single chart element.

### Live Components
The "now" marker and the most-recent segment of the observed line update live as new risk scores arrive; the forecast band recomputes and redraws (smoothly, not jarringly) whenever the underlying prediction updates materially — throttled to avoid distracting constant micro-redraws (a reasonable update cadence, e.g., every 10-30 seconds, rather than every single tick).

### Notifications
This screen doesn't originate its own notifications (it's an analytical/monitoring view) — but a small pulsing indicator on the "now" marker itself subtly reflects current overall severity, so even a user zoomed into historical exploration retains peripheral awareness of present state.

### Empty States
Newly onboarded equipment with insufficient history for a meaningful forecast shows the observed line alone with a clear note ("Predictive forecasting begins after 7 days of baseline data") rather than a fabricated or flat-lined fake forecast — honesty about model readiness is a direct expression of the "never invent a cause" principle applied to prediction confidence itself.

### Loading States
The chart renders its axis/grid immediately, then streams in data progressively left-to-right (oldest to newest) as it resolves — giving an immediate sense of scale and orientation even before all data has arrived, rather than a blank canvas until everything is ready.

### Error States
If the Predictive Risk Engine's forecast data is unavailable while historical observed data is fine, the screen clearly renders the observed portion normally and marks the forecast region with a distinct "Forecast temporarily unavailable" placeholder — never silently truncating the chart in a way that could be misread as "no risk predicted," which would be a dangerous misinterpretation.

### Mobile Behavior
A simplified, single-equipment version (no multi-compare) with horizontal scroll/pinch-zoom replacing hover-based tooltips with tap-to-reveal — retained on tablet for Marcus's use, present but de-emphasized on phone given its inherently wide/detailed chart format.

### Accessibility
A full data-table alternative (timestamp, score, confidence, contributing factors as columns) is available via a toggle, satisfying the same no-visualization-exclusive-information principle applied throughout; the "now" marker and forecast-vs-observed distinction are both reinforced with text labels, not solely a style/opacity difference.

### Dark Mode
Canonical/default; the gradient-fade forecast treatment is specifically tuned per-theme (opacity curves differ slightly between dark and light) since gradient legibility behaves differently against near-black versus near-white backgrounds — a small but real per-theme QA item flagged here so it isn't lost during implementation.

---

## 10. Emergency Control

### Purpose
The incident-command cockpit — where a Supervisor (Marcus) reviews and approves the Agentic Orchestrator's recommended Playbook (`ARCHITECTURE.md` §15) during an active Critical/High incident. This is the highest-stakes screen in the entire product: every design decision here is subordinated to speed-of-correct-decision and absolute clarity of what is about to happen and why. This screen is reached from an Incident (§5) or a direct Critical alert, never browsed to casually.

### Widgets
A focused, full-screen (modal-like but not a dismissible modal — this state is not meant to be casually closed) layout: top, a persistent incident summary header (equipment, severity, time-to-event countdown); center, the **Playbook Step List** — each recommended action shown as a card with its autonomy tier badge (§15.2: Recommend / Execute-with-notification / Execute-with-veto), a plain-language description, and its individual Approve/Reject/Modify controls; a live **Impact Preview** panel (powered by the Digital Twin's Simulation Layer, §16.2) showing what each step, if executed, physically affects. A large, unmissable **"Approve & Execute Playbook"** primary action and an equally prominent **"Reject — Escalate to Manual Response"** secondary path.

### Animations
Deliberately the *most restrained* motion in the entire product outside of purely functional progress indication — no decorative motion whatsoever. The time-to-event countdown updates with a steady, calm tick (not a frantic flashing countdown-timer aesthetic, which research on stress-induced decision-making shows measurably degrades judgment quality — this screen is designed to *lower* a supervisor's stress response enough to make a good decision, not spike it further). Step execution progress uses a simple, clean linear progress fill per step, completing with a single quiet checkmark.

### Colors
Severity red/amber used only for the header context, never as a background wash across the whole screen (a full-red screen would itself become a stressor working against clear thinking) — the working area (playbook cards) stays on the calm neutral dark surface palette, letting the *content* communicate urgency through language and structure rather than the chrome shouting via color.

### User Interactions
Each playbook step can be individually approved, rejected, or modified (e.g., adjust a "reduce flow 20%" parameter before approving) — never an all-or-nothing forced choice, respecting that a human supervisor's judgment may reasonably diverge from the AI's proposal on a subset of steps while agreeing on others. Rejecting the full playbook surfaces a structured "why" quick-select (informs model improvement, §9.5) before dropping to a blank manual-response mode. A physical confirmation pattern (press-and-hold, ~800ms, for the primary Execute action) is used specifically here — nowhere else in the product — as a deliberate anti-accidental-activation measure appropriate to a screen that can trigger real-world physical actions.

### Charts
A minimal, single live sparkline of the triggering signal(s) in the header only — this screen intentionally suppresses analytical depth (that belongs in Sensor Analytics/Risk Timeline, one click away via a "View full analysis" link) in favor of decision-focused minimalism.

### Live Components
The time-to-event countdown, the Impact Preview, and step statuses are all live; if the underlying risk assessment materially changes *while* a supervisor is reviewing (e.g., risk suddenly escalates further), the screen surfaces a clear, non-disruptive "Situation has updated" banner with a one-click refresh of the recommendation — never silently altering a plan mid-review out from under the decision-maker.

### Notifications
This screen itself is often the destination *of* a notification (an escalated Critical incident); once here, further notifications are suppressed/batched for the duration of active review specifically for this incident, to avoid the destructive-focus problem of new toasts competing for attention while a life-safety decision is being made — a rare, deliberate exception to the standard always-visible notification tray, scoped narrowly to this one high-stakes screen state.

### Empty States
N/A by construction — this screen only exists in the context of an active incident with a proposed playbook; if no playbook could be matched (an unrecognized pattern per `ARCHITECTURE.md` §15.3), the screen instead shows a clear "No matching playbook — recommend manual response" state with direct escalation contacts, never a blank or confusing void.

### Loading States
Because this screen is reached during a time-sensitive event, it is architected to load its critical path (incident header, step list) as fast as technically possible, with the Impact Preview (heavier, twin-simulation-dependent) allowed to resolve a beat later without blocking the ability to review and approve steps — speed of the primary decision path is prioritized over completeness of secondary context.

### Error States
If a playbook step fails to execute (per the Step Outcome Monitor, `ARCHITECTURE.md` §15.3), that step's card immediately shows a clear failure state with the specific reason, halts the remaining sequence, and elevates a direct, unmissable escalation prompt — this is the one error state in the entire product designed to be maximally, unapologetically loud, because a failed safety action mid-execution is the single most dangerous state the system can be in.

### Mobile Behavior
Fully available on Marcus's tablet (this is expected to be used on the floor, not only at a fixed console) with the same press-and-hold confirmation pattern preserved exactly — this is one screen where mobile is not a reduced experience, since incident command frequently happens away from a desk.

### Accessibility
The press-and-hold confirmation has a full keyboard/switch-access equivalent (a held keypress or an explicit two-step confirm dialog for assistive tech users, never a physical-gesture-only path to a safety-critical action) and all severity/tier badges are text-labeled, never color-only, with even more rigor applied here than elsewhere given the stakes.

### Dark Mode
Canonical/default and, uniquely on this screen, effectively the *only* mode offered live (light mode is available for consistency/settings-compliance but discouraged for this specific screen in real control-room deployment guidance, since a bright white full-screen surface at 3 a.m. is itself counter to the calm-decision-making goal) — noted here as a UX recommendation to surface in onboarding/Settings copy, not a hard technical restriction.

---

## 11. Knowledge Copilot

### Purpose
The conversational front door to the RAG Service (`ARCHITECTURE.md` §14) and Knowledge Graph (§13) — "Ask AEGIS," where Dr. Kwan investigates incidents, any operator gets a plain-language answer instead of hunting through manuals, and the system's explainability promise is most directly, personally experienced. This screen is the one place in the product explicitly modeled on modern AI-chat interaction conventions (familiar, low-friction) rather than industrial-console conventions — a deliberate register shift signaling "this is the conversational, exploratory tool" versus the operational screens' "this is the live-monitoring instrument."

### Widgets
A clean, centered chat column (Notion AI / modern-assistant convention) with a persistent left-side conversation history rail. Crucially, distinct from a generic chatbot: every substantive assistant response includes an inline **Sources** strip beneath it (small citation chips: manual section, incident ID, graph relationship) — never a wall of unsourced prose. A right-side, collapsible **Context Panel** shows the live Knowledge Graph subgraph the current answer drew from, visually, for users who want to verify the reasoning spatially rather than just reading citations.

### Animations
Responses stream token-by-token (per `ARCHITECTURE.md` §11.4) with a natural, un-jittery typing cadence; before generation begins, a brief sequence of small status lines animates in and settles ("Searching incident history…", "Querying knowledge graph…", "Reviewing 3 manual sections…") — genuinely functional, not decorative, since it materializes the retrieval step and is a key trust-building device establishing that the answer is being *assembled from evidence*, not freely generated.

### Colors
The assistant's message bubbles and all AI-sourced content use the Aegis Cyan accent consistently (per the system-wide "AI-generated" color convention, §0.2); user messages use neutral surface coloring; citation chips use a muted, consistent style regardless of source type, differentiated by a small icon (document / incident / graph-node) rather than color, keeping the color vocabulary uncluttered.

### User Interactions
Standard chat input with @-mention support to scope a question to a specific piece of equipment/zone (auto-completing from the Knowledge Graph — typing "@V-12" scopes the query precisely, avoiding ambiguous plant-wide searches when the user already knows their subject). Clicking any citation chip opens the source directly (a manual PDF viewer, an Incident detail panel, or a Knowledge Graph node) in the Context Panel without losing the conversation. A "Verify this" button on any claim triggers a secondary, explicit re-grounding pass (re-running retrieval and confirming citations) — a manual trust-but-verify affordance for especially consequential answers.

### Charts
Not a primary content type here, but the assistant can render an inline mini-chart (e.g., "show me the pressure trend during that incident") directly in the conversation flow when the question calls for it — composing a chart response rather than only prose, using the same chart components as Sensor Analytics for visual consistency.

### Live Components
Streaming generation itself is the primary live element; additionally, if the user asks about current/live plant state ("what's the risk on Reactor 3 right now"), the response includes a small embedded live-updating value inline in the answer text, sourced directly from the Digital Twin's state feed — bridging the conversational and live-monitoring registers in a single, well-scoped case.

### Notifications
None originate from this screen; it is a pull-oriented, user-initiated surface by design.

### Empty States
A fresh conversation shows a small set of suggested example queries tailored to the user's role (Dr. Kwan sees investigation-oriented prompts; an Operator sees more operational "what does this alarm mean" prompts) — a low-friction onboarding nudge rather than a blank input box, especially valuable for first-time users unsure what the assistant can do.

### Loading States
Covered by the streaming/status-line pattern above — there is no separate blocking loading state, since the retrieval-status sequence itself functions as the loading indicator, doing double duty as both progress feedback and explainability content.

### Error States
If retrieval finds no relevant grounding for a question, the assistant explicitly says so ("I couldn't find supporting documentation for that — here's what I do know from live sensor data" or a plain "I don't have enough information to answer that confidently") rather than generating an ungrounded, fluent-sounding guess — this refusal-to-hallucinate behavior is a core product-trust feature, and its UI treatment (a distinct, clearly-labeled "low confidence / no source" message style, never visually identical to a normal grounded answer) matters as much as the underlying model behavior.

### Mobile Behavior
Fully supported and genuinely useful on mobile (Tasha asking "what's the failure mode for this gasket" while standing in front of the actual equipment is a core intended use case) — the Context Panel becomes a swipe-up sheet rather than a side panel.

### Accessibility
Fully screen-reader compatible streaming (announced incrementally without overwhelming verbosity, using appropriate `aria-live="polite"` batching rather than per-token announcement); citation chips are fully keyboard-navigable and labeled with their source type and title, not icon-only.

### Dark Mode
Canonical/default; given this screen's closer kinship to consumer AI-chat conventions, it is also the screen where the light-mode variant is most likely to be preferred by office-based, non-control-room users (Dr. Kwan working from a desk) — both are fully first-class here, more so than the operational screens where dark is more strongly canonical.

---

## 12. Reports

### Purpose
Structured, exportable, point-in-time synthesis of plant performance and safety posture — serving James's (Plant Manager) periodic review needs and providing the raw material for external stakeholders (board reporting, insurance, regulatory bodies feeding into Compliance, §13). Where every other screen is about *now* or *what's coming*, Reports is deliberately about *what happened, summarized*.

### Widgets
A report-type gallery (card grid: "Monthly Safety Summary," "Incident Analysis," "Predictive Performance / ROI," "Equipment Health Rollup," "Custom Report Builder") leading into a generated-report viewer: a clean, document-like reading layout (generous margins, print-optimized typography) with embedded charts, a generated executive-summary paragraph (AI-authored via the same grounded-generation contract as the Knowledge Copilot, fully cited), and section navigation. A **Schedule** control lets a user set recurring auto-generation/delivery (e.g., "email me this every Monday").

### Animations
Minimal and document-appropriate — page-load fades, smooth scroll-to-section navigation. This screen deliberately borrows a reading-app register (more Notion/Apple Pages than live-dashboard) since its content is meant to be read carefully, exported, and shared outside the live system entirely.

### Colors
Muted, print-friendly palette even in dark mode (charts within reports use slightly desaturated versions of the standard palette, chosen to reproduce acceptably in both on-screen dark viewing and exported light-background PDF/print contexts without a jarring recolor between the two).

### User Interactions
"Generate Report" triggers a scoped date-range/zone picker; once generated, reports are editable in a light-touch way (hide a section, add a manual commentary block) before export/sharing — treating a report as a living document during preparation, not an immediately-frozen artifact. Export options: PDF (formatted for print/board decks), CSV (raw underlying data), and a shareable read-only link (respecting the viewer's own RBAC scope if they're an internal user, or a time-limited external-share token for board/regulator distribution).

### Charts
Reports aggregate and re-render the product's existing chart components (Risk Timeline snippets, Machine Health trend charts, Incident severity breakdowns as clean donut/bar summaries) — rather than inventing new chart types, reinforcing visual consistency between "what I saw live" and "what I'm reading in the report."

### Live Components
None within a generated report itself (reports are deliberately point-in-time snapshots — a report that silently changed after generation would undermine its use as a record) — the *gallery* of available/scheduled reports does live-update (e.g., "Generating…" status ticking to "Ready").

### Notifications
Scheduled report completion triggers a notification with a direct link; report generation failures (e.g., a data-source timeout) notify with a specific retry option rather than a silent failure.

### Empty States
No reports generated yet shows the report-type gallery prominently with a light "Get started" framing — the gallery itself functions as the empty state's primary content, not an afterthought below a "no data" message.

### Loading States
Report generation shows a determinate, staged progress indicator ("Gathering incident data… Computing trends… Drafting summary…") — mirroring the Knowledge Copilot's status-line pattern, appropriate since report generation genuinely involves a similar RAG/aggregation pipeline and users benefit from the same transparency.

### Error States
Partial-data reports (e.g., one data source was unavailable during generation) are clearly annotated inline at the relevant section ("Equipment health data for Zone 4 was unavailable at generation time") rather than silently omitted — a report is a record that may be relied upon later, so gaps must be self-documenting.

### Mobile Behavior
Report viewing (not authoring/scheduling) is fully supported on mobile in a clean, reflowed reading layout — appropriate for James checking a summary from his phone; the Custom Report Builder is desktop-only, a reasonable scope reduction for an authoring-heavy tool.

### Accessibility
Generated reports meet document-accessibility standards directly in their export (tagged PDF structure, alt-text on charts summarizing the key takeaway numerically) since exported reports leave the live application's accessibility tooling behind entirely and must stand on their own.

### Dark Mode
Live gallery/viewer UI follows canonical dark-first convention; exported artifacts (PDF/print) are always light-themed regardless of live preference, as established in the Incident Center's export behavior (§5) — a consistent, system-wide export rule worth stating once and applying everywhere.

---

## 13. Compliance

### Purpose
The regulatory-grade audit surface — direct, unfiltered access to the immutable event/action history (`ARCHITECTURE.md` §10.3, §19.5, `NFR-17`) formatted for OSHA/PSM/Seveso-style investigation and audit needs. Where Reports is a curated narrative, Compliance is the raw, tamper-evident ledger underneath it — the screen a regulator or internal auditor is handed direct access to.

### Widgets
A dense, precise audit-log table (this is the one screen in the product where a dense, spreadsheet-like table is the *correct* design choice, not a compromise — auditors expect and prefer this register) with immutable-record indicators (a small lock icon + cryptographic-hash-style reference per entry, communicating tamper-evidence), full filtering (date range, event type, user, equipment), and a permanent "Export for Regulatory Submission" action producing a formatted, indexed package (not just a CSV dump). A **Retention Policy** panel shows current configured retention windows per data category (tying to `ARCHITECTURE.md` §12.4) in plain language.

### Animations
Essentially none — intentionally the least-animated screen in the product. An audit log's credibility is partly conveyed by its *stillness and plainness*; any motion here would read as inappropriate for the register (nobody wants a "delightful" audit trail).

### Colors
Deliberately restrained — mostly neutral text/table styling, with severity color used only as a small inline reference chip where an audit entry relates to an incident, never as a dominant design element. This screen is the strongest expression in the whole product of the principle "severity color is a scarce, meaningful resource" — here it appears least often, precisely to command attention when it does.

### User Interactions
Row-level "view full context" opens the related Incident (§5) or Playbook execution (§10) record without leaving the audit context (opens in an overlay, preserving the filtered table state beneath it). Bulk-select for export scoped to a specific investigation. A "Verify Integrity" action re-computes and confirms the tamper-evidence chain for a selected range, surfacing a clear pass/fail confirmation — a literal, visible trust mechanism for this screen's core promise.

### Charts
Minimal — a small compliance-posture summary strip at the top (e.g., "342 days since last reportable incident," retention-policy adherence indicator) but the table, not visualization, is the primary content, matching how this data is actually consumed by its audience.

### Live Components
The table appends new entries live as events occur (append-only, matching the underlying event-sourced architecture exactly) but never re-orders or mutates existing rows — visually reinforcing the immutability guarantee at the UI level, not just the data level.

### Notifications
Retention-policy-relevant events (e.g., approaching a configured deletion/archival boundary for a data category) notify Admin/Safety Officer roles in advance — a compliance-hygiene notification type distinct from operational alerts.

### Empty States
N/A in practice (an operating plant always accumulates audit events quickly) — a brand-new, just-deployed instance shows a plain "Audit trail begins at system activation on [date]" note, avoiding any ambiguity about whether history before that point exists elsewhere.

### Loading States
Table loads with pagination from the start (never attempting to load an unbounded audit history at once) with a simple, precise "Loading records 1-100 of 48,203" style indicator — a register consistent with the screen's overall plain, precise character.

### Error States
Export failures are surfaced with specific, technical clarity (this audience needs accurate detail, not a friendly generic message) including a reference/correlation ID for the engineering team to investigate — this is the one screen where a more technical error-message register is the *correct* UX choice for its audience.

### Mobile Behavior
View/filter/search fully supported on tablet for on-the-go review; export/bulk-actions require desktop — a reasonable restriction given these are typically prepared, seated tasks, not walk-around ones.

### Accessibility
Full standard data-table accessibility (proper header associations, sortable-column announcements, keyboard-navigable pagination) — this screen's audience explicitly includes external auditors/regulators whose own accessibility needs are unknown to us, making rigorous baseline compliance here non-negotiable, fittingly, for the Compliance screen itself.

### Dark Mode
Both fully supported and genuinely equally likely to be used, since this screen is used in formal, seated audit-review contexts as often as live operational ones — no strong canonical default either way, a deliberate exception to the dark-first convention elsewhere.

---

## 14. Settings

### Purpose
Personal and plant-configuration preferences — the quieter, lower-stakes administrative layer for an individual user's experience (notification preferences, theme, accessibility options) and, for authorized roles, plant-level configuration like alert thresholds (`ARCHITECTURE.md` FR-20).

### Widgets
A standard settings-pattern layout: left-side category navigation (Profile, Notifications, Appearance & Accessibility, Alert Thresholds [role-gated], Integrations [role-gated], Security/MFA), right-side content panel per category using clear form patterns — toggles, segmented controls, sliders for threshold values with a live preview of what a given threshold would currently classify as (e.g., dragging a pressure-deviation threshold shows, live, how many currently-monitored assets would presently trigger it) — an unusually thoughtful, non-generic touch that turns an abstract number into an immediately understandable operational consequence.

### Animations
Standard, restrained settings-screen conventions — toggle switches animate their thumb position (150ms spring), section changes cross-fade. Nothing here competes for the "premium" register through motion; it earns it through clarity and the live-threshold-preview interaction described above.

### Colors
Fully neutral surface palette; Aegis Cyan appears only where a setting concerns an AI behavior (e.g., "Show AI confidence bands by default") — maintaining the system-wide meaning of that color even in this low-stakes context.

### User Interactions
Threshold sliders update a live preview chip (as above) before committing (an explicit "Save Changes" step for anything plant-configuration-level, since threshold changes are safety-relevant and should never auto-save on every drag-tick); Notification preferences let a user configure channel/severity-tier combinations precisely (e.g., "SMS me for Critical only; in-app only for Medium/Low").

### Charts
The live-threshold-preview mechanic described above is the closest thing to a "chart" here — effectively a real-time filtered-count indicator rather than a traditional chart type.

### Live Components
The threshold-preview count is live-computed against current plant state as the user adjusts a slider — the only genuinely "live" element on an otherwise mostly-static configuration screen.

### Notifications
A confirmation toast on successful save; a distinct, more prominent confirmation (with a summary of what changed) for any plant-wide threshold change specifically, since this is the one Settings action with genuine safety-operational consequence beyond the individual user's own experience.

### Empty States
N/A — settings screens always have their full set of configurable options present by definition; there's no "no settings yet" state.

### Loading States
Instant/local for personal preferences (client-side, low-latency); threshold/integration settings (server-persisted, potentially shared/audited) show a brief save-in-progress state on the Save button itself, matching the Login screen's in-button-spinner convention.

### Error States
Invalid threshold values (e.g., a lower-bound exceeding an upper-bound) are caught inline with immediate, specific validation messaging before any save attempt — never a rejected save with a generic "error" after the fact.

### Mobile Behavior
Personal preferences (Profile, Notifications, Appearance) fully supported on mobile; plant-configuration sections (Thresholds, Integrations) are view-only on mobile with editing reserved for desktop — consistent with the general pattern that configuration-of-consequence tasks are desktop-scoped throughout this product.

### Accessibility
This screen carries extra weight as the literal home of the app's own accessibility options (motion reduction override, high-contrast mode, font-size scaling, screen-reader verbosity preferences) — it must itself be exemplary in accessibility execution, since a user adjusting these settings is very likely doing so because they need them working correctly on this exact screen.

### Dark Mode
The literal control surface for this preference lives here (Appearance category: System / Light / Dark, plus the Sensor Analytics high-contrast opt-in from §8 and the Emergency Control guidance note from §10) — Settings is where every dark-mode decision documented elsewhere in this spec becomes a concrete, user-facing toggle.

---

## 15. Admin

### Purpose
The system-configuration and org-management console (`ARCHITECTURE.md` §21.2's Admin role; §17.3 sensor onboarding; §20 identity federation) — the least frequently visited but highest-leverage screen in the product, since misconfiguration here (a wrong RBAC scope, a missing sensor-to-equipment link) can silently degrade the entire system's correctness elsewhere.

### Widgets
A structured, multi-section console: **Users & Roles** (table with role/scope assignment, invite flow, MFA-status column), **Sensor & Equipment Registry** (the onboarding UI for `Sensor -[:MONITORS]-> Equipment` links per §17.3, with a guided wizard for new sensor registration and a bulk-import path for large onboarding batches), **Zones & Topology** (Digital Twin/Factory Map layout configuration, §16.5's schematic-import), **Integrations** (OIDC/SSO federation config, §20.1; protocol adapter configuration, §17.2), **Playbook Library** (versioned playbook authoring/review, §15.4, gated to Safety Officer + Admin), and **System Health** (a technical-operations view surfacing the observability stack, §25.3, for this Admin audience specifically — service status, event-lag metrics).

### Animations
Restrained, standard enterprise-console conventions — this screen prioritizes information scanability and form-completion speed over any expressive motion; the one exception is the guided sensor-onboarding wizard, which uses a clear multi-step progress animation (a horizontal stepper filling in) since walking a user through a multi-stage, consequential setup process benefits from a felt sense of progress and completion.

### Colors
Fully neutral; System Health section borrows the standard severity palette for service-status indicators (a degraded internal service is, functionally, the same severity vocabulary as a plant-equipment risk — consistent reuse rather than inventing a parallel "system status color language").

### User Interactions
Role/scope assignment uses a clear, explicit matrix-style picker (role × plant/zone scope) rather than a free-text permission string — directly reflecting the architecture's (Role, Resource Scope) model (§21.1) in the literal UI so an Admin's mental model matches the system's actual enforcement model precisely, reducing misconfiguration risk. Playbook authoring uses a visual step-graph editor (drag to sequence, click to configure a step's autonomy tier and tool binding) rather than a text/code editor — matching §15.4's "structurally represented as a directed graph of typed steps, not free-text scripts" architectural decision exactly, so the authoring tool's shape mirrors the underlying data model's shape.

### Charts
System Health includes small real-time sparkline strips per service (latency, error rate, event-lag) — a lightweight, ops-dashboard-style treatment distinct from the plant-monitoring charts elsewhere, since this is monitoring the *software system*, not the *physical plant* (a deliberate visual differentiation so Admins never confuse "AEGIS AI's own health" with "the plant's health").

### Live Components
System Health section is fully live (direct client of the observability stack, §25.3); Users/Sensors/Zones/Integrations sections are standard CRUD-pattern screens (fetch-on-load, optimistic-update-on-edit) rather than continuously live, appropriate to their configuration (not monitoring) nature.

### Notifications
Sensor/equipment registration success/failure surfaces inline; System Health degradation triggers a distinct "internal system alert" notification style (visually differentiated — a different icon/border treatment — from plant-safety alerts) so an Admin's attention is never confused between "the plant needs attention" and "our own software needs attention," two very different response playbooks.

### Empty States
A newly deployed instance's Sensor Registry shows a prominent "Import your first sensor layout" call-to-action with template/example options — this is often the very first substantive screen a new customer's Admin interacts with, so its empty state functions as onboarding, not just an absence indicator.

### Loading States
Standard table/form skeletons; the guided onboarding wizard shows clear per-step processing states (e.g., "Validating sensor connectivity…") since sensor registration genuinely involves a live handshake-style check against the Ingestion Gateway.

### Error States
Sensor registration failures (e.g., a protocol handshake failure) surface specific, actionable diagnostic detail (which protocol, what response was received) — this audience is technical, and vague "something went wrong" messaging here would be a significant, avoidable friction cost for exactly the users responsible for keeping the whole data pipeline healthy.

### Mobile Behavior
Explicitly desktop-primary — Admin is scoped out of the mobile app entirely aside from a minimal emergency "System Health quick-check" view, matching the general principle that heavy configuration/authoring work belongs on larger screens, and avoiding the cost of building and maintaining full mobile parity for a low-frequency, high-precision task set.

### Accessibility
Full form-accessibility rigor throughout (proper fieldset/legend grouping for the role×scope matrix, clear error-association via `aria-describedby`) — Admin screens are frequently overlooked in accessibility audits industry-wide precisely because they're low-traffic, which this spec explicitly flags as a trap to avoid given how consequential Admin errors are.

### Dark Mode
Canonical/default, consistent with the rest of the product; the visual-graph Playbook editor specifically gets a dedicated dark canvas treatment (matching the Digital Twin's blueprint aesthetic) so authoring a playbook *feels* connected to the physical/spatial system it will eventually act upon, rather than reading as generic disconnected business-process software.

---

## Closing Note: How This Document and the Architecture Document Relate

Every interaction specified above is a direct UI expression of a contract established in `ARCHITECTURE.md` — the "Why?" affordance is `NFR-9` made tangible; the Aegis Cyan convention is the AI-Last reasoning layer (§9) made visible; the press-and-hold confirmation on Emergency Control is Autonomy Tier 1 (§15.2) enforced at the pixel level; the append-only Compliance table is the event-sourced backbone (§10) rendered as a screen. A design review of any future new screen should start from the same question every section above answers: **which architectural contract does this screen make legible to a human, and does it do so calmly until the moment it must not be calm at all?**

**End of Document.**

