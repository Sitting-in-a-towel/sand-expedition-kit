# SAND — Research Notes (2026-06-10)

## 🔑 CompartmentsDatabase — THE builder data source (found 2026-06-10, builder-v2 session)
The in-game Trampler editor does NOT assemble part data from EPBs at runtime — it loads ONE
asset: **TextAsset `CompartmentsDatabase` (JSON, 244KB) in `walkershared_assets_all.bundle`**
(Addressables key `CompartmentsDatabase.json`, group WalkerEditor; loader =
`ClientCompartmentsDatabase.CreateDatabase(serializedText)` in dump.cs). Schema =
`CompartmentInfoDatabase { groupsInfo, socketInfo, compartments[126] }`; per compartment:
`entityId, mirrorEntityId, group[], enabled, rotationEnabled, startRotation, pivot, pivotOffset,
cells[] { position, sockets{CubeDir→{slotType→{editable,snap,blockedConnections}}}, volumeOccupied,
requireSupport }`. Slot types: DOOR/HATCH/STRUCTURE/BALCONY/DECK; connection states
DEFAULT/DOOR/OPEN (HATCH+DOOR spawns `walker_ladderHatch` = inter-deck ladder). Group limits:
REACTOR/STEERING/CAPTAIN = 1. Extraction: `datamine/scripts/find_db_textasset.py` →
`extracted/json/compartments_database.json` → `scripts/build_parts_v2.py` → site `parts_v2.json`.
**Re-run these on the 22 June release build.** Notes: 47/126 of our old name-parsed footprints
were wrong; part stats (Weight/HP/prices) remain server-side (`CompartmentDefinitionDto` via
masterserver — unchanged conclusion). Mesh pipeline v2 + the v2 builder page are documented in
`SITE_REQUIREMENTS.md` (milestone section). EPBs without a `ViewDataComponent` resolve their view
prefab by convention `walker_<id>_view` (e.g. the engines).

## 🖥️ LOCAL SITE BUILT (2026-06-10, same day) — `SAND/site/`, owner testing
Owner dropped the seed-finder (POIs are named on the in-game map at spawn) and asked for a local
testable frontend (requirements in `SITE_REQUIREMENTS.md`). Built + verified with Playwright
(screenshots in `SAND/screenshots/`): **React/Vite app at `site/` → `npm run dev` →
http://localhost:3010**. Pages: Operations Board (representative sector map, 96 named locations,
filters + spawn-cap intel), Loot Tables (193, Voyage/Storm toggle — values differ in 152
tables!), Item Index (99 items, 83 with mined game icons, reverse lookup), Crafting (30
recipes), **Trampler Blueprint Builder** (278 real compartments with true grid footprints
parsed from EPB names, 4 deck levels, manifest, `SANDBP1.` share codes, localStorage).
Additional extractions this round: **ItemType flags enum** (decodes lootset caps),
**341 UI icons** (`datamine/extracted/icons/`), **362 walker EPBs** (`walker_epbs.txt`),
**in-game blueprint format** (`WalkerBlueprintDto`: chassis + compartments at CellCoordinate +
rotation + connections — a future import-from-game feature is plausible; local saves live in
`LocalWalkerBlueprintStorage`, likely `Sand.es3`). Data pipeline: `datamine/scripts/build_site_data.py`.

## ⭐ DATAMINE FINDINGS (2026-06-10) — the decisive investigation is DONE

### TL;DR — we are in **branch 2 (location/loot catalog), with a realistic upgrade path toward a map tool**
- **Map = procedurally generated per match from a server-chosen 32-bit seed.** NOT a finite pre-baked seed set like Nightreign's 520 → a "mark landmarks → identify seed" finder is **not viable** (4.29 billion possible maps).
- **BUT generation is fully deterministic client-side** — the server sends `WorldSettings { worldSeed, worldSetupId, gameMode }` and every client generates the same world locally. If a player can ever *see/read their seed legitimately* (log file, UI, post-match screen), we can regenerate their entire map offline. **ACTION (owner): after playing a match, check `C:\Users\hanbo\AppData\LocalLow\Hologryph\Sand\Player.log` for seed/world output** — current logs on disk are menu-only sessions from Oct 2025 and show nothing.
- **POI/loot question: SETTLED — loot tables and crafting recipes are 100% FIXED definitions in the game files.** We extracted them. The location/loot catalog is not just viable, it's largely *already extracted*.

### What we extracted (all in `datamine/extracted/`, gitignored)
| Data | Where | What we got |
|---|---|---|
| **193 loot tables** | `json/loottables_voyage.json` + `loottables_storm.json` | Full contents: `lootTableId` → items with exact `countMin`/`countMax`. Organized as `{med,resource,food,valuables,weapons}_container_{low,mid,high}Effort_T{1-3}_set{N}` + specials (navalMine, keys, ArtefactCrystal). Same 193 IDs in both game modes (VOYAGE + STORM_DIVE). |
| **Crafting recipes** | `json/craftingrecipes.json` | 100% fixed: exact inputs → outputs + craft seconds, per workbench type+tier (`Recipes_Utility_Workbench_T1`, `Recipes_Armament_Workbench_T1/T2`). E.g. 5 fabricScraps + 15 threads → 1 fabric (2s); 5 scrappedAmmo + 5 metalParts → 20 pistolAmmo (3s). |
| **97 named LootSets** | `json/lootsets.json` | Per-location max-spawned-items caps, keyed by item-category bitmask. Location names are GOLD: `ArchipelLighthouseFishingVillage`, `Venedig`, `Achilleon`, `Kleineshaus`, `Factorio`, `DeusExMachine`, `POIShipBigWeapons`, `POILargeRockBigValuables`… |
| **Location pools** | `json/islandrosters.json` | The live "main" rosters: **12 islands, 38 POIs, 6 forts, 7 events** (+ dev/test rosters). Each match's world is populated from these fixed pools. |
| **World gen config** | `json/configuration.json` | `conf_worldConf_main`: **fortsAmount = 4 per map**, biome lists for islands/drops/extractions, Perlin noise params (danger, elevation). Multiple WorldConfigs exist (main/dev/test/oneIsland/biomeTest). |
| **93 item blueprint IDs** | `json/item_ids.txt` | All items referenced by loot (resources, ammo, weapons, meds, valuables, keys…). Full item defs live in EPB bundles (4533 entity prefab blueprints) — next mining target. |
| **Full C# layout** | `il2cpp_dump/dump.cs` (79MB) | Il2CppDumper output: every class/method/field. Key namespaces: `Hologryph.Sand.Shared.World.Map.Generation` (Voronoi/Graph/Round strategies), `…Shared.Loot.*`, `…Shared.Game.Features.Crafting`. |

### How the world is built (from code + assets)
1. Server picks `uint worldSeed` + a `WorldSetup` asset (worldConfig + islandsRoster + poiRoster + fortsRoster + eventsRoster + contractsRoster).
2. `WorldGeneratorModule.Generate(seed, config)` → **Voronoi-cell world layout** (`VoronoiWorldGeneratorStrategy`; Graph/Round/Single strategies also exist). Biomes assigned by danger-noise; islands/drop-zones/extraction-zones live on specific biome types.
3. POIs/islands/forts are **hand-designed prefabs** (with placed `LootSpawners`, `NPcSpawners`, workbenches, terrain stamps) picked from the rosters and placed into cells (biome-appearance rules per POI).
4. Loot spawners roll against the **fixed loot tables** (weighted `LootTableEntry { tableId, chance }`), capped by the location's LootSet.
   → **Same POI type = same loot table pool every match.** Owner's in-game observations should align: lighthouse/fishing-village locations have their own loot sets; forts have crafting workbenches (T1/T2 recipes fixed).

### Recommended deliverable (confirm before building)
1. **NOW — Location & Loot Catalog site/bot data**: per-POI pages (what spawns there, loot category caps, which biome it appears on), the full loot-table browser, crafting recipe browser ("how do I make X" → bot command). Data is already extracted; needs cleaning + DB schema.
2. **NOW — Discord bot** can serve recipes/loot answers from this data.
3. **LATER — map tool**: hinges on whether the seed is player-visible at/after release (Player.log check). If yes → "paste your seed → see your full map" (requires reimplementing/porting the Voronoi gen — `dump.cs` has the full algorithm structure; serious but bounded work). If no → input-driven landmark catalog only.
4. **Re-mine everything on 22 June release** (structure should carry; values may be rebalanced). Re-run is ~30 min with the scripts below.

### Reproducible pipeline (all offline, BattlEye-safe, runs on the COPY)
- Copy: game → `datamine/gamefiles/` (9.7GB).
- `datamine/tools/il2cppdumper/` → ran on `GameAssembly.dll` + `global-metadata.dat` → `extracted/il2cpp_dump/` (dump.cs, il2cpp.h, script.json, stringliteral.json, DummyDll/).
- `datamine/tools/assetripper/` (downloaded, ultimately not needed — UnityPy did the job).
- **UnityPy (Python)** reads the Addressables bundles directly (type trees are intact): `scripts/probe_bundle.py`, `scripts/dump_bundle_json.py`.
- **`scripts/odin_parser.py`** — our own Odin Serializer binary-format decoder (the game uses Odin `SerializedScriptableObject` for the juicy configs; UnityPy can't read those blobs, this script can). Reusable for every Odin config in the game.
- Useful bundles: `lootsets`, `craftingrecipes`, `configuration` (114MB — world configs + loot tables), `islandrosters`, `pois` (9.6MB), `islands` (62MB), `equipment` (14MB), `epb`/`env_epb` (item/entity blueprints), `terrainstamps` (199MB).

### Open items
1. **Owner in-game**: cross-check POI loot consistency (expected: consistent per POI type) + grab `Player.log` after a real match → look for seed.
2. Mine **item definitions** (names/stats/sizes) from EPB bundles → turns item IDs into a real item database.
3. Mine `equipment`/`walker` bundles → Trampler parts data (for build-sharing tool).
4. `LootTableEntry { tableId, chance }` *weights per spawner* live in the POI prefabs (`LootSetupDataComponent`) — extract per-POI spawner→table mapping for exact "what drops where" odds.
5. Dev reply pending (Discord thread, sent 2026-06-10).

---

## The game
- **SAND: Raiders of Sophie** — PvPvE dieselpunk mech-extraction shooter. Devs **Hologryph + TowerHaus**, publisher **tinyBuild**. Steam app **1431300**. **Launches 22 June 2026** (delayed from 10 June) — so we have lead time; the local install is the **PLAYTEST** until then.
- Build/customize/pilot a giant walking mech ("Trampler") = mobile base + warehouse + weapon. Scavenge the **procedurally generated** dunes, loot, survive, extract. Solo or squad. BattlEye-protected online play.
- Sources: [Steam](https://store.steampowered.com/app/1431300/SAND_Raiders_of_Sophie/) · [SteamDB](https://steamdb.info/app/1431300/) · [Niche Gamer](https://nichegamer.com/sand-raiders-of-sophie-launches-in-early-2026/) · [GamingTrend](https://gamingtrend.com/news/sand-raiders-of-sophie-is-launching-on-june-10th-on-steam/)

## Engine / data format (verified from local install)
`H:\Steam Games\steamapps\common\Sand Playtest\` contains:
- `UnityPlayer.dll`, `Sand_Data/` → **Unity**
- `GameAssembly.dll` (~143MB) + (expected) `Sand_Data/il2cpp_data/Metadata/global-metadata.dat` → **IL2CPP** (C# compiled to native; reverse via Il2CppDumper, not a managed-DLL decompiler)
- `Sand_BE.exe`, `BattlEye/` → **BattlEye kernel anti-cheat**
- `nvngx_dlss.dll` (DLSS), `AMD/NVUnityPlugin.dll`

**=> NO Unreal "AES pak key."** The "long unique code" the owner remembers was for **Predecessor (Unreal Engine)** — its `.pak`/`.ucas` files are AES-256 encrypted, and FModel needs that key. Unity/IL2CPP has no such key. The closest Unity analog is `global-metadata.dat` (occasionally obfuscated, usually plain).

## Data mining SAND (Unity) — the right tools
**All STATIC/offline (game not running) = BattlEye-safe:**
- **AssetRipper** (https://github.com/AssetRipper/AssetRipper) — modern, best general extractor. Pull models/textures/prefabs/scriptable-objects (item & map data) from `Sand_Data/`.
- **AssetStudio** — older alternative GUI.
- **UABEA** (Unity Asset Bundle Extractor Avalonia) — for `.bundle`/asset-bundle files.
- **Il2CppDumper** (https://github.com/Perfare/Il2CppDumper) + **Il2CppInspector** — reconstruct class/struct/enum layouts + method names from `GameAssembly.dll` + `global-metadata.dat`. This is how you find generation parameters, item definitions, stats, etc.
- Has anyone mined it yet? Launches 22 June → assume **no public dataset yet**; we'd be early. The PLAYTEST files give a head start now (structure likely carries to release). (Recheck the SAND modding/datamining community + nexusmods + a SAND Discord once it forms.)

## BattlEye = hard design constraint
- BattlEye is kernel-level; **reading the running game's memory → ban.**
- So a live "what seed am I in" tool must be **input-driven** (user marks observed landmarks), exactly like nightreign-seed-finder. **Never** build a memory-reader.
- Static datamining of on-disk files is unaffected (do it with the game closed).

## nightreign-seed-finder.com — analysis (the design north-star)
- Planning tool for Elden Ring: Nightreign. Identifies which of **520 pre-baked map seeds** you're in by having the user **mark visible landmarks**, then reveals the full map: enemy/boss positions, treasure, merchants, route optimization.
- **Input-driven, NOT memory-reading** → anti-cheat-safe (the model we must copy for SAND).
- **No public API**, no data-source docs, fan-made (not affiliated with FromSoft/Bandai). Data is **data-mined** (the 520 seeds are baked into Elden Ring's files).
- **Feasibility for SAND — three branches** (their tool works because Nightreign has a FINITE pre-generated seed set):
  1. **Seed-based finite maps** → full seed-finder + interactive map (the dream).
  2. **Map random, POIs fixed** → a **location/loot catalog** still works: document what each POI TYPE gives. Owner's leads: lighthouses → more/better loot; forts → crafting stations. Verify whether each fort/lighthouse has a SET loot table + crafting recipe or is randomised per instance.
  3. **Fully random** → no map/seed tool; lean into build-sharing + a Discord bot + general POI-type guidance.
  Most likely a MIX (random layout, fixed POI archetypes) → branch 2 is the realistic deliverable even if branch 1 fails.

## OPEN QUESTIONS to resolve before building
1. **Procgen type:** seed-based (finite, mineable like Nightreign) or fully random per match? (Il2CppDump the generation code, or observe across matches.)
2. **POI rules (matters even if the map is random):** does each POI TYPE have a SET loot table + crafting recipe, or is it randomised per instance? Owner's leads to verify: lighthouses → more/better loot; forts → crafting stations. If POI archetypes are fixed → a location/loot catalog works regardless of map randomness.
3. What map/POI/item/loot data is extractable from `Sand_Data/`?
4. Does tinyBuild/Hologryph offer (or plan) any API or fan-tool support? (See draft below.)

---

## Dev enquiry message — ✅ SENT 2026-06-10 (owner opened a Discord thread with the SAND team; awaiting reply). Kept below for reference / re-use.

> Subject: Community tools for SAND — any data/API support for fan projects?
>
> Hi [team / name],
>
> Everything I've seen of SAND: Raiders of Sophie looks fantastic — the Trampler-building extraction loop and the world have a ton of character, and I'm really looking forward to the 22nd.
>
> I'm part of a small community group that builds free fan tools for games we love (interactive maps, build planners, that sort of thing). We'd love to make some community resources for SAND — an interactive map, a build/loadout sharer, and a Discord bot for the community.
>
> Before we go the data-mining route, I wanted to ask: **do you have (or plan) any public API or official data we could build on** — item/map/loadout data, for example? And just as importantly, **are you open to community-made fan tools** for SAND, or are there any guidelines you'd want us to follow?
>
> We're happy to keep everything clearly fan-made/unofficial, credit the game, and respect whatever boundaries you set. Just want to build the right way and support the community.
>
> Thanks for making such a cool game — looking forward to whatever you can share.
>
> [Your name] · [community / contact]

*(Confirmed by owner: this is aimed at the SAND dev team — Hologryph/TowerHaus/tinyBuild — they're the small team and they hold the data.)*

---

# DATAMINE FINDINGS — 2026-06-16 PLAYTEST UPDATE RE-MINE (4GB Steam update, build dated 06-16 00:07)

Copied live playtest -> `datamine/gamefiles_0616/` (now `datamine/gamefiles/`; Jun-10 build preserved at
`datamine/gamefiles_baseline_0610/`, baseline extracts at `extracted/json_baseline_0610/`). Game was
RUNNING during copy — file copy only, never memory (BattlEye-safe). Clean copy: 2202/2202 files, 0 failed.

## File-level diff (Sand_Data): 29 added, 1 removed, 43 changed, 2130 unchanged
- CHANGED bundles of interest: data.unity3d (+9MB), epb (+1KB), pois, islands, islandrosters,
  configuration (+41KB), walker_assets (-35KB), views (+7.8MB), ui (+71KB), customizations (-136KB),
  colliders, scenes, GameAssembly.dll + global-metadata.dat (IL2CPP code).
- Added: 28 new audio .wem + soundbanks (irrelevant); 1 duplicateassetisolation bundle re-hashed (Addressables churn).

## ✅ Builder V2 + Tech Tree data UNCHANGED (validated, not just byte-level)
- `walkereditor_assets_all.bundle` + `walkershared_assets_all.bundle` byte-identical between builds.
- Re-extracted from new build: compartments_database.json, progression_tree_descriptions.json,
  research_node_ui_data.json all IDENTICAL to Jun-10. => the integrated builder is still accurate.

## data.unity3d game-data (TextAssets): only 13 of 122 changed, ~3KB net
data.unity3d's +9MB is meshes/textures/audio/code, NOT gameplay data. Changed TextAssets:
Artefacts, BaseTurret, CannonTurret, ShotgunTurret, Client, Composite, Extraction, FlareGun,
LivingSand, PerformanceTestRunInfo, Server, Volatiles, and **item_rifleMusket (+2754B — headline
weapon change, likely new musket variant/stats)**. Crafting, CraftingResources, Items: UNCHANGED.

## ⭐ Loot rebalance (entity_loot.json): 2 of 92 entities changed
- `game_armyBox_t3_highEffort` (T3 high-effort weapons / army box): EXPANDED 4 -> 8 sets.
  New weapons_container_highEffort_T3_set5..8 added at chance 200 (double weight). set1-4 unchanged @100.
- `game_safeMiddle_t3_highEffort` (T3 high-effort safe / valuables): set3 & set4 NERFED chance 100 -> 15.
- set5-8 are BRAND-NEW loot tables (Jun-10 baseline only had set1-4). Their item CONTENTS live in
  LZ4-compressed bundle data via an undocumented/serialized extraction (loottables_voyage/storm.json
  provenance not in runbook) — NOT yet extracted. This is the one open item if we want the new weapon list.

## Locations (location_contents.json): 2 of 89 changed
- `island_testIsland` (dev, +2 nodes) and `loc_event_Dreadnought` (+2 nodes, minor turret spawner tweak). Stable otherwise.

## Verdict
Light data patch = a **loot/weapon rebalance** (army boxes buffed for weapons via 4 new T3 sets;
safes nerfed for valuables) + a musket weapon change. Builder/Tech unaffected. New tool: `scripts/diff_textassets.py`.

---

# WEAPON / AMMO / ARMOR STATS — extractor built 2026-06-16

The site/wiki was missing gun range+reload, ammo range, and armor rating. These were never
extracted (original item-def pass pulled icons only). They live in the per-weapon-family
blueprint TextAssets in `data.unity3d` (SniperRifle, Shotgun, SemiAutomaticPistol, RepeaterRifle,
RocketLauncher, Revolver*, item_rifleMusket, etc.) + the `Items` asset (armor jackets).

NOTE: these blueprint TextAssets are RELAXED JSON — BOM prefix, // and /* */ comments, trailing
commas. Strict json.loads parses only 42/122; need the lenient loader (string-aware comment strip
+ trailing-comma strip) in `scripts/extract_weapon_stats.py`. Entries inherit via "Template" (by
entry name, resolved globally).

Field locations:
- Gun RELOAD speed  = ActionData RELOAD action `DurationData` (e.g. SniperRifleReload 3.8s; variants like ironSights 2.5s).
- Gun/Ammo RANGE    = `RangeDamageModifierData` = distance->damage-multiplier falloff curve (on weapon AND per-ammo).
- Ammo damage/pen   = `DamagePhysicalData` + `CustomProjectileData`->GameData projectile `ProjectilePenetrationData`; mag = `StackableData` capacities.
- Armor RATING      = ARMOR items (jackets) `ArmorPhysicalData.value` + `ArmorPhysicalRegenerationData` {delay,speed}.

Output: `scripts/extract_weapon_stats.py` -> `extracted/json/weapon_stats.json`
(72 weapons, 24 ammo, 3 armor; reload on 71/72, range curve on 63/72 — melee/explosive have none).
Armor jackets: 50 / 100 / 150 rating (Uncommon/Rare/Noteworthy). NOT yet wired into the site (review first).
New weapon this patch: SGOW M82 Revolver Rifle (item_rifleMusket, reload ~2.95s).
