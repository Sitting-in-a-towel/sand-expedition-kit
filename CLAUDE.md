# SAND — Community Tools Project

## What this is
Community resources for **SAND: Raiders of Sophie** — a PvPvE dieselpunk mech-extraction shooter by **Hologryph / TowerHaus**, published by **tinyBuild** (Steam app **1431300**). **Launches 22 June 2026** (delayed from 10 June) — so we have lead time, and the local install is currently the **PLAYTEST** (full release files land on the 22nd). You build/pilot giant walking "Trampler" mechs across a **procedurally generated** wasteland (planet Sophie), scavenge loot, and extract.

**NOT a competitive/tournament project** — these are fan/community tools. Public-facing materials: keep it light on the full "Raiders of Sophie" subtitle (owner preference) — that subtitle is here for our reference.

## Vision (owner)
- **Discord bot** — community bot, in the spirit of the Predecessor/Claw bot.
- **Website (later, NOT competitive):**
  - **Interactive map** of the procedurally generated desert.
  - **Seed / expedition finder** styled after https://nightreign-seed-finder.com/ — identify which map/seed you're in from observed landmarks, then reveal the full layout (POIs, loot, bosses).
  - **Build sharing** — players make mech/Trampler builds in-game and share them via the site.

## ⚠️ CRITICAL technical reality (verified from the local install 2026-06-10)
- **Engine = UNITY (IL2CPP), NOT Unreal.** Evidence: `UnityPlayer.dll`, `Sand_Data/`, `GameAssembly.dll` (~143MB = IL2CPP). → The Predecessor/Unreal playbook (FModel + the long **AES `.pak` key**) **DOES NOT APPLY**. Unity has no equivalent AES pak key.
- **BattlEye anti-cheat is present** (`Sand_BE.exe`, `BattlEye/`). This is the single biggest design constraint:
  - Mining **static files on disk** (game NOT running) = fine, normal, offline.
  - **Reading game MEMORY at runtime = BANNABLE.** So any live tool MUST be **input-driven** (user marks what they observe on-screen), exactly how nightreign-seed-finder works. **Never read game memory.**
  - **✅ DECIDED (owner): the whole project is 100% OFFLINE / input-driven.** It never touches the running game or its memory — all data comes from static file mining + user input. No exceptions.
- **Procedural generation — ✅ RESOLVED 2026-06-10 (datamined, see RESEARCH_NOTES.md "DATAMINE FINDINGS"):** We're in **branch 2**. Map = Voronoi procgen from a server-chosen 32-bit seed (deterministic client-side, but 4.29bn seeds → no Nightreign-style finite seed-finder). **POI archetypes, loot tables (193, fully extracted) and crafting recipes are FIXED** → the **location/loot catalog** is the confirmed deliverable. Upgrade path: if the player's seed turns out to be visible (check Player.log after a real match), a "paste seed → regenerate your map" tool becomes possible.

## Data source — two paths (decide)
1. **Official API / data from the devs** — ask Hologryph/TowerHaus/tinyBuild. Small indie team; no known public API yet. (Draft enquiry in `RESEARCH_NOTES.md`.)
2. **Data mining (Unity, static/offline — BattlEye-safe):**
   - **AssetRipper** / **AssetStudio** — assets in `Sand_Data/` (models, textures, items, map data).
   - **UABEA** (Unity Asset Bundle Extractor Avalonia) — asset bundles.
   - **Il2CppDumper** + **Il2CppInspector** — reconstruct C# class/data structures from `GameAssembly.dll` + `Sand_Data/il2cpp_data/Metadata/global-metadata.dat` (item defs, generation params, etc.).
   - Launches 22 June → community mining will be brand new → **we'd be early.** The PLAYTEST install gives us a head start *now* (structure likely carries to release).

## Tech stack (proposed — reuse Predecessor/Claw patterns where sensible)
- Discord bot: **Node.js + discord.js** (like the Towels/Claw bot).
- Website: **React + Node/Express + PostgreSQL** (like Predecessor), but non-competitive.
- Data pipeline: Unity extraction → structured DB → API → site.

## Working rules
- Status: **brand-new, scoping.** Confirm direction before building.
- Save to disk early/often (this PC has an idle-crash risk — CPU RMA pending).
- Local install (engine/data reference): `H:\Steam Games\steamapps\common\Sand Playtest\` (this is the PLAYTEST; the full-release install may be a separate folder — point me at it when known).
- **🛡️ Data mining works on a COPY — NEVER the live install.** Copy the needed files (`Sand_Data/`, `GameAssembly.dll`, the metadata file, etc.) into **`SAND/datamine/gamefiles/`** and operate only there. The `datamine/` folder is gitignored (large). This keeps us from ever reading/modifying/running against the live game.
- **POI rules = part file-mining, part in-game testing.** Owner is testing **in-game** whether each POI type (lighthouse, fort, …) has SET vs randomised loot/crafting; the session mines the files for fixed loot-table/recipe definitions and cross-references the owner's observations.
- **Dev enquiry: SENT** — owner opened a Discord thread with the SAND team (2026-06-10), awaiting reply. Draft kept in `RESEARCH_NOTES.md` for reference.
- Full research: `RESEARCH_NOTES.md`.
