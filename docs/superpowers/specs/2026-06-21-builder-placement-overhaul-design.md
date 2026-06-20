# Builder Placement Overhaul — Legs, Free-Place Validity, Directional Entrances, Controls

**Date:** 2026-06-21
**Scope:** Builder V2 (`/builder2`) — `site/src/pages/BuilderV2.jsx`, `site/src/components/BuilderScene.jsx`, `site/src/lib/builderCore.js`, plus a new datamine bake script for the walker leg.
**Status:** Design — awaiting owner review.

The wrong-facing Left/Right **structure parts** are a *separate* workstream (needs an owner orientation walkthrough; see `builder-structure-mirror` memory) and are **out of scope** for this spec.

---

## 1. Goals

1. **Render the walker legs** under every chassis, using the real datamined leg mesh, instanced per leg.
2. **Directional entrance placement** — entrances place at the hull edge where the ladder column is clear, *and not on the face a leg points out of*. Legal spots highlight when an entrance is selected.
3. **Non-blocking validity** — place / move / rotate any part freely; invalid placements glow red and are fixed by rearranging. The only hard block is two parts occupying the same cell.
4. **Keyboard remap** — Space = rotate, R = level up, F = level down.

## 2. Background (current state)

- Parts are defined verbatim from the game's `CompartmentsDatabase` in `parts_v2.json` (cells, sockets, groups, limits). No name-parsing.
- A chassis is a part with `category:"Chassis"`, a `legs` count (4/6/8), and a footprint of cells: volume deck cells plus a **ring of `noVol` cells** marking leg/clearance positions.
- The **entrance** (`compSpecial_Entry_*_1x1`, group `ENTRANCE`) is a 1×1 vestibule (one volume cell) with a **6-cell `noVol` ladder shaft hanging straight down** (`p.y` = 0..-6, all `noVol`, `ignOOR`). Its in-game description: *"cannot be installed on top of other compartments or chassis, as the access hatch with the ladder is mounted in its lower deck."*
- The extracted chassis **mesh has no leg geometry** — it runs y≈0.03→2.17 (deck plate + lip only). Legs hang to the ground in-game from a separate shared rig.
- `validate()` today is a **gate**: placement, move, and rotate are rejected/reverted when invalid.

## 3. Part A — Legs

### 3.1 Leg mesh (datamine + bake)

- The walker leg is a **prefab hierarchy** named `game_ironcladLeg` in `walker_assets_all.bundle` (a single shared leg used for all hulls), composed of child meshes: `footGround_LOD0` (~14k verts), `foot_detail_A4`, `foot_inner_gear_*`, piston meshes, thigh/shin meshes.
- New script `datamine/scripts/export_leg_mesh.py` (mirrors `export_part_meshes_v4.py`):
  - Resolve the `game_ironcladLeg` GameObject; walk its transform hierarchy.
  - For each child MeshFilter, read mesh (LOD0) + accumulated local transform (bind/default standing pose), merge into one static leg mesh.
  - Emit `site/public/meshes3_v4/_leg.bin` in the existing v4 layout (`[T*9 f32 pos][T*9 i8 nrm][T*6 f32 uv][T*1 u8 texSlot]`) + its albedo texture(s) to `tex3_v4/`, and a `_leg` entry into `mesh_index_v4.json` (`{t, b, tex, col}`).
- The leg is a **render-only asset**, never a placeable/selectable part. It is not added to `PARTS`.

### 3.2 Leg anchors + facing (data)

Each leg needs a position **and an outward-facing direction** (the latter drives the entrance rule).

- New build step `datamine/scripts/build_chassis_legs.py` writes `site/src/data/chassis_legs.json`:
  ```
  { "<chassisId>": [ { "x": int, "z": int, "dir": "Left"|"Right"|"Forward"|"Back", "yaw": float }, ... ] }
  ```
- **Primary source:** the chassis prefab's leg mount transforms (each leg child carries position + rotation → real anchor + outward direction). Investigate the chassis EPB/prefab for explicit leg mounts during implementation.
- **Fallback:** cluster the chassis `noVol` ring cells into `legs` groups (count from `legs` field); anchor = group centroid; `dir` = dominant horizontal direction from hull centre to the anchor, snapped to one of Left/Right/Forward/Back.
- `dir` is the **outward face the leg projects from** — the value the entrance rule compares against. Because owner is not 100% certain of the directional rule, `chassis_legs.json` is human-correctable and treated as the single tunable source of truth.

### 3.3 Render

- `BuilderScene` loads `_leg` once, then for each anchor in `chassis_legs.json[state.chassisId]` adds an instance: positioned at the anchor cell, rotated by `yaw`, scaled/translated so the **foot plants on the sand plane** (ground `y=-7`) and the top meets the deck underside.
- Legs join the rig group, `castShadow`, slightly dimmed material so they read as structure (never selectable; excluded from `placedMeshes` pick set).

## 4. Part B — Entrance placement

### 4.1 Legal-spot rule

A candidate entrance placement (cell `(x, y, z)`, rotation `rot`) is **valid** when **all** hold:

1. **Attached:** the vestibule volume cell connects to the rig via at least one **side door socket** to an adjacent occupied compartment (existing socket-connectivity check).
2. **Clear ladder column:** every cell directly below the vestibule down to the ground (the 6 `noVol` ladder cells' x/z column) contains **no volume cell** of the chassis or any compartment — i.e. it overhangs the hull edge. (This is the data encoding of "cannot be installed on top of other compartments or chassis.")
3. **Leg-face clearance (directional):** the entrance's **outward face** (the horizontal direction toward the open side, derived from `rot`) must **not equal** the `dir` of any leg anchor at that cell. A corner leg facing Left still leaves the corner's Forward face open. *(This replaces the original blanket "no corners" rule.)*

There is **no standalone corner exclusion** — corners are governed entirely by rule 3.

### 4.2 Highlighting (chosen UX)

- When `activePart` is an `ENTRANCE`-group part, `BuilderScene` computes all cells on the current level that satisfy 4.1 and draws them as **green pads**.
- The ghost still follows the cursor; on an illegal cell it goes red with the specific reason (`ladder blocked`, `leg in the way`, `not attached`).

## 5. Part C — Non-blocking validity

### 5.1 Model

`validate()` is split into two outcomes:

- **Blocked (hard):** the placement would put a volume cell into a cell already holding another part's **volume** cell (overlap). This is the *only* condition that prevents place / move / rotate.
- **Invalid (soft, red):** any of — not connected, unsupported, floating, out of grid, over a leg face (entrances), or **group-limit exceeded** (e.g. 2nd reactor). The part still places; it renders red and is listed as a problem.

New signature (illustrative):
```
validate(...) -> { blocked: bool, blockReason: string, invalid: bool, reasons: string[] }
```
`buildOccupancy` already distinguishes `vol` per cell, so overlap = "my vol cell lands on another part's vol cell".

### 5.2 Behaviour changes (`BuilderV2.jsx`)

- `place()` — commit unless `blocked`. Drop the "invalid → flash + return" gate.
- `movePlacement()` commit / `rotate()` — commit unless `blocked`; **remove the revert-on-invalid** logic and `moveBackup` revert path (still snap-back only on a true overlap block).
- New `useMemo` computes a **per-placement validity map** `plId -> { invalid, reasons }` over `state`, passed to the scene.

### 5.3 Render (`BuilderScene.jsx`)

- Placed meshes whose plId is `invalid` render with a **red tint/emissive** (distinct from the green selection highlight).
- Ghost has **three** states: green (valid), red (placeable-but-invalid), and a **locked/grey** state (overlap — can't place here).
- Requirements panel (`bv2-manifest`) gains an **"⚠ N invalid parts"** row listing reasons; export/publish still allowed (build may be a work in progress).

## 6. Part D — Keyboard

In `BuilderV2.jsx` keydown handler:

| Key | Action | (was) |
|-----|--------|-------|
| **Space** | rotate active/selected part | (R) |
| **R** | level up | (▲ button only) |
| **F** | level down | (▼ button only) |
| M | mirror selected | unchanged |
| Del / Backspace | remove selected | unchanged |
| Esc | cancel selection/placement | unchanged |
| Shift (hold) | keep placing after place | unchanged |

- Space must `preventDefault` (avoid page scroll) and be ignored when focus is in an INPUT/TEXTAREA.
- Update the on-screen HUD/help strings to match.

## 7. Files touched

- **New:** `datamine/scripts/export_leg_mesh.py`, `datamine/scripts/build_chassis_legs.py`, `site/src/data/chassis_legs.json`, `site/public/meshes3_v4/_leg.bin` (+ tex).
- **Edit:** `site/src/lib/builderCore.js` (validity split, entrance rule, leg-anchor accessor), `site/src/components/BuilderScene.jsx` (legs, red invalids, entrance highlights, 3-state ghost), `site/src/pages/BuilderV2.jsx` (non-blocking place/move/rotate, validity memo, keyboard remap, requirements panel).
- `mesh_index_v4.json` gains a `_leg` entry.

## 8. Out of scope

- Wrong-facing Left/Right **structure parts** (`builder-structure-mirror`) — separate workstream, needs owner walkthrough.
- Per-leg articulation/animation — legs render in a single static standing pose.

## 9. Open items to verify in-game (owner)

- The **directional leg rule** (4.1.3) — confirm the ladder can sit on a corner face the leg does *not* point out of. `chassis_legs.json` `dir` values are tunable to match observation.
- Whether entrances can attach on **upper decks** as well as the hull deck (spec allows any level that satisfies the rule).

## 10. Testing

- Each chassis (4/6/8 leg) renders the correct number of legs at sane positions, feet on the sand.
- Entrance highlight pads appear only on legal edge cells; the directional leg-face exclusion is observable.
- Place an unsupported/floating part → it places red; move a blocker away → it turns valid live.
- Two parts cannot be dropped into the same cell (ghost locks/greys).
- Space rotates, R/F change level, in viewport focus; typing in the name field does not trigger them.
