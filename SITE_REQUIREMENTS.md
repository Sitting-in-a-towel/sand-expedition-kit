# SAND Community Site — Requirements (owner, 2026-06-10)

## Decisions
- **Seed finder: DROPPED** (for now). POIs are named on the in-game map at spawn, so identifying the exact seed isn't important. What matters is **POI information — what's available at each location**.
- **Build a full local frontend first** that the owner can view + test on this PC; only after that do we explore hosting it as a website.
- After local site works: revisit deeper mining (per-spawner loot weights etc. — saved as "open items" in RESEARCH_NOTES.md).

## 1) Interactive map (Fextralife interactive-map style)
- Reference: https://eldenring.wiki.fextralife.com/Interactive+Map
- Real layouts are procedural, so NO set POI locations. Instead: a **generic square map / representative board** with generic POI markers people can select.
- Filters (by POI type/category), click a POI → its info: loot available there, categories, caps, images.
- The POI info is the core value, not exact placement.

## 2) Catalog with IMAGES
- Items (and similar things) should show **name AND image** wherever possible — mine icons from the game files.
- Loot table browser + reverse lookup (where does item X drop), crafting recipes (how to make X).

## 3) Offline interactive blueprint builder (Trampler builds)
Pain points in-game (why this matters):
- In-game builder: pick a chassis, parts lock onto an **invisible grid**, multiple **height levels** (up/down).
- Sharing builds is janky: screenshots only; can't see walkways, lower levels, parts hidden behind things; can't tell WHICH component was used (storage compartment vs corridor look alike; variants exist).
What ours must do:
- Grid-based placement on a chassis, multiple height/deck levels with a level switcher.
- **Explicit parts manifest** — exactly what parts (and variants) were used, listed by name.
- See every level/walkway clearly (per-level view).
- Offline/local (localStorage), with export/share format for later website integration.

## Priorities answered by owner
1. Deeper mining (per-POI spawner weights) → AFTER working local site.
2. Images on items etc. → YES, as many as possible.
3. Seed checker → forget for now.

---

# ⭐ MILESTONE — IDENTICAL IN-GAME BUILDER ✅ BUILT 2026-06-10 — 🚀 DEPLOYED TO PRODUCTION 2026-06-11 (owner: "push it to production, keep both builders for now")
**Live at https://predecessor-tournament-api.onrender.com/sand/ — BOTH builders shipped: old `/builder` (Blueprints) + `/builder2` (Builder V2 β). Decide later which survives.**
Deploy notes: commits `6a961a49` + `c56f0493` in Predecessor website repo (static files only, no server.js change). Bonus fix shipped: old Builder.jsx had corrupted JSX (chassis `<image>` underlay opening tag deleted, stray attrs rendered as inert SVG text — was broken in the previous deploy too); restored. Smoke-tested headless pre-push: all 6 pages, 0 console errors.
Test: `cd site && npm run dev` → http://localhost:3010/#/builder2

What got built (vs the spec below):
1. ✅ **The actual in-game database found** — NOT per-EPB mining: the game editor loads a single
   `CompartmentsDatabase` JSON TextAsset from `walkershared_assets_all.bundle` (the exact data the
   in-game builder uses). Extracted verbatim → `datamine/extracted/json/compartments_database.json`
   → `site/src/data/parts_v2.json` (`scripts/build_parts_v2.py`). Contains per part: true cell
   occupancy incl. multi-level reservations, per-cell/per-face sockets (DOOR/HATCH/STRUCTURE/
   BALCONY/DECK + editable/snap flags), pivot/rotation rules, mirror pairs, group limits
   (REACTOR/STEERING/CAPTAIN = 1). **Audit: 47/126 name-parsed footprints were wrong** (all chassis,
   reactors, turret slots…) — owner's "Round Metal 2×1 is really 2×2" confirmed from data. The old
   roster also listed 152 phantom non-placeable parts; the real locker is 122 enabled compartments.
   Socket states decoded: DOOR socket → `walker_sqrDoor`; HATCH → ladder hatch (`walker_ladderHatch`)
   or open hatch — i.e. wall→door and floor→ladder conversion points are now data-driven.
2. ✅ **Mesh pipeline v2** (`scripts/export_part_meshes_v2.py` → `site/public/meshes2/`, 25MB):
   authored LODs only (LOD0, stepping to LOD1/2 over an 8k-tri budget — never decimated, so no holes),
   real material colours (_BaseColor per submesh baked as vertex colours), real normals (int8-quantized),
   damaged-state/disabled submeshes filtered out (they polluted v1), runtime-mounted reactor cores
   composited onto the Open reactor views. Thumbnails re-rendered with real colours
   (`scripts/render_thumbs_v2.py` → `parts2/`, fixed an upside-down projection bug from v1).
3. ✅ **Socket-driven placement** (`site/src/lib/builderCore.js` + `components/BuilderScene.jsx` +
   `pages/BuilderV2.jsx`): full-3D editor (orbit/pan/zoom), ghost preview green/red with reason,
   validation = cell occupancy + requireSupport + face-socket compatibility (shared slot type on
   opposing faces — balconies bolt to walls/deck edges, decks stack on STRUCTURE roofs, etc.),
   group limits enforced, deck level switcher, auto-deselect after place (Shift = keep placing),
   click-drag move of placed parts w/ revert on invalid, R rotate / M mirror / Del remove,
   clickable socket spheres on selected part (wall → door → open cycling, ladder hatches),
   manifest + requirements panel (essentials, crew 6, weight "?" = server-side), SANDBP2 share
   codes + localStorage. Tested end-to-end with Playwright: placement, stacking, limits, share
   roundtrip — 0 console errors. Screenshot: `screenshots/builder-v2-first-build.png`.
4. ⏳ Stretch (.wbt import) not started.
Known mockup approximations for review: socket spheres are placeholder visuals (not in-game door
meshes); reactor-core composite is centered by bounds not slot data; in-game grid bounds unknown
(using generous 27×27×9); vertical pitch derived as 3.07m/floor from room meshes.

ORIGINAL SPEC (for reference):
- Reactor "Round Open" mesh has no top → looks flat (lowest-LOD export + decimation artifacts; rebuild must use LOD0/LOD1 + backface handling). **→ fixed in v2**
- Reactor "Round Metal" labelled 2×1 but really occupies 2×2 → footprints from compartment data, not filenames. **→ fixed via CompartmentsDatabase**
1. Mine COMPLETE per-part truth: cells, sockets, conversions, ladders. **→ done**
2. Mesh pipeline v2: LOD0/1, materials/colours, proper normals. **→ done**
3. Socket-driven placement mirroring the in-game editor. **→ done**
4. Stretch: .wbt import (gzip + XOR, partially cracked — round 1 notes). **→ parked**

# BUILD-SHARING GALLERY — ✅ BUILT + DEPLOYED 2026-06-13
First server-side SAND feature, fully isolated (sand_builds + sand_build_votes tables, no
tournament code/auth). Backend `backend/routes/sand.js` mounted at `/api/sand` BEFORE the CSRF
middleware (anonymous public endpoints: submit/list/vote; admin pending/approve/reject gated by a
standalone `SAND_ADMIN_KEY`). Frontend: Gallery page (nav) w/ top/new sort + vote + "open in
builder"; Builder V2 "Publish to gallery" (-> pending); `/moderate` (not in nav) for approve/reject.
Submissions are hidden until approved. Verified end-to-end on prod (submit->pending->approve->
list->vote dedup).
⚠️ ACTION REQUIRED: set `SAND_ADMIN_KEY` in the Render backend env for the `/moderate` page to work.
Until then, submissions pile up as `pending` (approve via DB or after setting the key). Key was
generated + given to owner 2026-06-13 (also in local backend/.env).

# FEEDBACK ROUND 6 (friend via owner, 2026-06-11) — ✅ IMPLEMENTED + DEPLOYED same day (commit 450d2115)
Feedback: condense Ops Board like the containers (POI/gunboat/ship name repeats); rename World
Events; Living Sand ×4 = ONE POI (the worm pit); "Factorio" is the file name; Contracts unclear +
Tier-4 rewards look like 2024 lockbox loot; tech tree needs work ("have a deeper look in the
files"); keep the database resettable for game updates.
Delivered:
1. Ops Board condensed 142 → 75 archetype cards (loot-flavour + numbered-instance variants are
   chips in the detail; Little Factory 1-3/01-03 + Schwalbeninsel/Schwalbenlnsel deduped).
2. ⭐ LOCATION ART MINED — locations aren't baked meshes; each prefab is a hierarchy of Odin
   'blueprint' components naming module prefabs (geometry bundle). New
   `datamine/scripts/render_location_thumbs.py` assembles + renders 79 sepia isometric sketches
   → map stamps + detail images. (Runtime-procedural houses can't be reproduced — cities render
   as authored bones, reads like an ink field sketch.)
3. "World Events" → "Final Zone"; Living Sand → "Living Sand (Worm Pit)"; DISPLAY_ALIAS map in
   data.js ready for verified in-game names (internal names display until then — incl. Factorio).
4. Contracts: prominent UNVERIFIED/legacy-config banner; stays last in nav. Owner: contracts may
   exist "in part" — re-verify at release.
5. ⭐ TECH TREE — owner was right, the files DID have more: `ProgressionTreeDescriptions`
   TextAsset (walkershared bundle) = the real 98-node research catalog (names + uiPriority;
   descriptions are dev placeholders). Factions Science/Military/Smuggling + node UI styling
   from ResearchNodeUiData. Page rebuilt on real nodes w/ tier filter + matched part models.
   Edges/prices confirmed masterserver-only (ResearchTreeJsonDto; no local cache — checked
   LocalLow, Sand.es3 = settings only).
6. `datamine/UPDATE_PIPELINE.md` — full one-pass data-reset runbook for the 22 June release.

# FEEDBACK ROUND 5 (friend via owner, 2026-06-11) — ✅ IMPLEMENTED + DEPLOYED same day (commit 7460b364; owner pre-authorized push, friend to test on prod)
Source feedback: "Loot tables should be under container type, then tier, then the various outcomes.
The current listing is too much, there should only be 10-20 options for containers, then after a
selection show more details." + "Too much focus on the ingredients instead of the product. I want
to see what I can make, then select that to find out what it costs."
Confirmed plan:
1. Containers tab → picker grid of the 12 merged sources; click → detail view w/ Zone T1/T2/T3
   buttons (+ effort + Voyage/Storm), outcomes sorted by %, guaranteed pinned. (Data was already
   merged to 12 — this is a presentation fix.)
2. Loot page DEFAULTS to Containers tab (Items tab kept as reverse lookup). Crafting page's long
   scroll also flagged as "too much" — fixed by #3.
3. Crafting → product-first: grid of 29 craftable products, click → panel w/ cost, bench+tier, time.
4. Bonus: ingredient rows link to "where it drops"; craftable ingredients show recursive cost tree.
5. Owner pre-authorized prod push after local verification ("just do it then push to production").

# FEEDBACK ROUND 4 (owner, 2026-06-10) — ✅ implemented + DEPLOYED (owner pre-approved deploy after actioning)
- **Part IMAGES**: built a mesh-thumbnail pipeline (`datamine/scripts/render_part_thumbs.py`): part EPB → ViewDataComponent → prefab in walker bundle → lowest-LOD meshes → isometric software render (numpy+PIL). **253/278 parts** now show their REAL game model in the locker, on placed parts on the board, in the chassis bay, and on the new Tech Tree page. 25 parts have no resolvable view prefab (ghost icon).
- 🐛 hull-stacking fixed: HULL level now sits ON the chassis plate, decks stack above.
- **Tech Tree tab added**: full part roster by category w/ model thumbs. Unlock ORDER/costs are server-side (`GetResearchTree`, same as weights) — page says so; node paths pending dev data or manual collection.
- Manifest now has a WEIGHT box (total / capacity / progress bar) — shows "?" until weight data exists, wired to live-update.
- Owner notes 1+2 (map lock/labels, accordion): approved, will look later.

# FEEDBACK ROUND 3 (owner, 2026-06-10) — ✅ implemented LOCALLY, NOT deployed (owner flagged: never deploy without his go-ahead — earlier NoAB push was premature)
- Map: lock it (no zoom/pan) ✅; location names ALWAYS visible ✅ (truncated >15 chars, full name on hover/select); POI/fort/event zone boxes were oversized → compacted, zones resized to content (ships zone is biggest now) ✅. Extra locations got proper kinds (wreck/gunboat→ship etc.) + cleaned names ✅.
- Builder: parts locker categories = accordion, only one open at a time ✅; "Build requirements" panel added from analyzer code: crew limit 6 (hardcoded MEMBER_LIMIT), weight/energy limits enforced (values server-side), stability from chassis+centre-of-mass, maneuver degrades with load, reactor/steering/captain's cabin essentials ✅.
- Mandatory-parts SPECIFICS (e.g. exactly which parts count as essential) are in the server-side compartment definitions, same as weights — not minable from disk.

# FEEDBACK ROUND 2 (owner tested, 2026-06-10) — ✅ IMPLEMENTED same day (except: in-game-identical 3D builder mockup, doors/walls/ladders modeling, militia box table values, bench tier per location). Deployment PREPARED (files copied + server.js route added in Predecessor website working tree) — awaiting owner's explicit push command.
Round-2 mining wins: per-entity drop WEIGHTS from EPB Odin blobs (real % odds — ironclad boxes incl. guaranteed alloy, buried treasure set weights); per-location prefab scans (spawner/crate/mob/bench placements for 78 locations, 61 of them brand-new "extra" locations incl. Fort Istria/Arpad, Little Factories, world events); 20 locations confirmed with crafting stations; in-game map icon sprites extracted. Weights for Trampler parts re-verified NOT in files (EPB components carry only placeholder physics mass) — settled.

## Map
- Still wants the IN-GAME map look as background. Any map of the game is fine ("generate ANY of the maps"), static image, POIs removed — it just has to read as "the sand map from the game". Find screenshots online for art reference.

## Loot — containers tab redesign (owner may send a mockup)
- Containers tab should look like an EXCEL/SPREADSHEET table.
- Merge tier variants into ONE card with clickable T1/T2 tier buttons (e.g. Buried Treasure).
- Cap each card at ~10 most common/rarest items + "click to expand" for the rest. "You aren't being very space efficient."
- MERGE sources that are one thing in-game:
  - All Ironclad lockboxes (40/70/80mm) → one "Ironclad Loot Box" (killing an ironclad = chance of A box, can't target a specific one).
  - All mob drops → one "Mob Drops" group. Call the fish-zombie NPCs "mobs", never describe them.
- Find DROP RATES in game files ("I'm sure they're there").

## Crafting
- NEED POI→bench mapping (which locations have which tier benches) or the page doesn't really help.
- 🐛 At narrow page width, recipes overflow their boxes / hide behind containers.

## Builder
- Game has limitations we don't model: mandatory parts, weight limits.
- 3D preview must eventually look like the in-game models.
- 🐛 After placing a part it stays in placing mode — auto-deselect after placement; placed parts should be click+DRAG movable.
- Owner still believes weights are in the files — re-verify once more, then settle it.
- Should display doors/walls (and which walls can become doors/windows), ladders — to show inner navigation.
- Owner asks for a MOCKUP of a near-identical in-game builder to review later.

## Deployment (owner approved the plan, wants friend to test)
- Host static build under pred.city backend at /sand. NOT connected to anything else (no DB/API/tournament code).
- Catches found during review: icon paths in JSON are root-absolute (break under /sand/) → use BASE_URL; verify Express version for wildcard route syntax.

---

# FEEDBACK ROUND 1 (owner tested, 2026-06-10) — ✅ IMPLEMENTED same day, awaiting re-test
All items below shipped except: real part thumbnails (in-game ones are runtime-generated; needs a
mesh-render pipeline later), per-location bench lists + per-spawner % (future prefab mining pass),
and part WEIGHTS (master-server data — see Builder note; builder is wired to accept a weights file).
Bonus from this round's mining: official item names/rarity/pawn values from `data.unity3d`
TextAssets; in-game blueprint `.wbt` files found at `LocalLow/Hologryph/Sand/Data/Walkers/`
(gzip + 12-byte-XOR — import-from-game is feasible, parked).

## Ops Board (map)
- 🐛 Clicking a marker shows NOTHING in the right panel (worked in synthetic test → pointer-capture bug swallowing real clicks).
- 🐛 Scrolling on the map scrolls the whole page — wheel must zoom the map only.
- Map should look like the ACTUAL in-game sand map (the paper map your character holds in-match) — square, parchment style.
- GROUP locations by category into separate sections/areas of the map (all islands together, all wrecks together…) so nobody mistakes the board for real positions.

## Loot (major redesign)
- Owner didn't notice Voyage/Storm differences — surface them better.
- Filters must be FROZEN/sticky at top (usable without scrolling up).
- Pretty names everywhere: 'aurogenCrystal_set' → 'Aurogen Crystal', 'buriedTreasure_T1_set1' → 'Buried Treasure'. Merge set1/set2… variants.
- MERGE the Loot + Items tabs — same info, opposite workflows. Item-centric is how owner pictured it.
- Item search → matrix/table: rows = container/source types (merged), columns = tier zones, cells = drop chance/likelihood. (True per-spawner % needs the prefab weights — until then show "in X of Y sets".)
- Heatmap/split of where crate types drop per location (e.g. "Fort X: 70% food crates / 30% other") — we have per-location caps now; exact spawner distribution = future mining.
- Item detail must open in a SIDE panel, not at the top of the page (no scroll-to-top round trips).

## Crafting
- Must answer "WHERE do I craft this?" — which benches exist, are recipes bench-locked, where benches are found. (Recipes are per workbench type+tier; per-location bench placement = future prefab mining.)

## Builder (push toward in-game look)
- Ideal: near-identical to in-game 3D builder (click+drag orbit). Compromise accepted if too hard — but at minimum:
- Parts should show their IMAGE (locker + placed). (In-game thumbnails are runtime-generated by a thumbnail camera — check for stored sprites, else future mesh-render pipeline.)
- Parts locker + blueprint side by side; locker is a narrow column.
- Replace 'Rotate' button with click+drag rotation / joystick-like control moving the design in 3D space.
- Front/rear direction arrows + indicators on the board.
- Chassis names unclear — use better in-game names if they exist, plus visual footprint preview per chassis.
- ⚠ WEIGHTS: every part has weight, chassis have weight limits — REQUIRED. (Datamine finding: stats come from the master server `GetCompartmentDefinitions`, NOT the game files. Check local caches (Sand.es3 / LocalLow Data folder); else this needs the dev-API path or manual in-game collection.)
