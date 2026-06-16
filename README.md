# SAND — Expedition Kit

Community tools for **SAND: Raiders of Sophie** (Hologryph / TowerHaus, pub. tinyBuild).
An offline, input-driven reference site plus the datamining pipeline that feeds it.

> ⚠️ **Unofficial fan project.** Not affiliated with or endorsed by Hologryph, TowerHaus, or
> tinyBuild. This repository is **private** and contains datamined game data and extracted assets
> for community reference only — **do not redistribute the extracted assets** (`site/public/*`:
> meshes, textures, icons). All extraction is done offline from static files (never the running
> game / never game memory — BattlEye-safe).

## What's here

| Path | What |
|------|------|
| `site/` | React + Vite app — loot/crafting/locations browser, **Trampler Builder V2** (three.js), tech tree, build-sharing gallery |
| `site/src/data/` | Game-derived data the site reads (items, loot tables, recipes, parts, **weapon/ammo/armor stats**, locations) |
| `site/public/` | Extracted art used by the site (part meshes, icons, location/container thumbnails) |
| `datamine/scripts/` | The extraction pipeline (Python + UnityPy) that regenerates everything in `site/src/data` and `site/public` |
| `datamine/UPDATE_PIPELINE.md` | Step-by-step runbook to re-mine after a game update |
| `RESEARCH_NOTES.md` | Findings log (engine, feasibility, patch diffs, field locations) |
| `SITE_REQUIREMENTS.md` | Feature spec + feedback-round history |

`datamine/gamefiles/` (a **copy** of the game install, ~10GB) and `datamine/extracted/` (raw
intermediates) are intentionally **gitignored** — never committed.

## Run the site locally

```bash
cd site
npm install
npm run dev      # → http://localhost:3010
```

The site is fully static/offline — no backend needed except the optional build-sharing gallery
(`/api/sand`, hosted separately).

## Re-mine after a game update

The game data resets cleanly from a new build — see `datamine/UPDATE_PIPELINE.md`. In short: copy
the new install into `datamine/gamefiles/`, then run the `datamine/scripts/extract_*` and
`build_*` scripts (Python 3 + `UnityPy`, `numpy`, `Pillow`). The weapon/ammo/armor stats come from
`extract_weapon_stats.py` → `build_weapon_stats.py`.

## Engine note

SAND is **Unity (IL2CPP) + BattlEye**, not Unreal — so there is no AES pak key; extraction uses
the Unity toolchain (UnityPy / AssetRipper) against static files only.
