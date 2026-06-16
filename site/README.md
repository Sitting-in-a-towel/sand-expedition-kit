# SAND // Expedition Kit — local site

Unofficial community field kit for SAND. React + Vite, fully static — all data is baked-in JSON
datamined from the playtest (see `../datamine/`).

## Run locally
```
cd site
npm install   # first time only
npm run dev   # → http://localhost:3010
```

## Pages
- `/#/map` — Operations Board: every named location on a representative sector board, filter by kind, click for spawn-cap intel.
- `/#/loot` — 193 loot tables, Voyage/Storm toggle, category/effort/tier filters, item search.
- `/#/items` — item gallery with mined icons + reverse lookup (drops from / crafting).
- `/#/crafting` — workbench recipes.
- `/#/builder` — Trampler blueprint builder: chassis picker, 4 deck levels, real part catalogue (278 compartments with true footprints), overlap/bounds validation, parts manifest, share codes (`SANDBP1.…`), localStorage autosave.

## Updating data after a new game build
```
cd ../datamine
python scripts/extract_icons.py          # icons from ui bundle
python scripts/dump_bundle_json.py ...   # re-dump changed bundles (see RESEARCH_NOTES.md)
python scripts/build_site_data.py        # rebuilds src/data/*.json + copies icons
```

## Hosting
Live at `https://pred.city/sand-wormpit-7x2k/` (URL deliberately non-obvious — owner request
2026-06-11; old `/sand` 404s). `npm run build` bakes that base path (vite.config.js) — it must
match the route in `Predecessor website/backend/server.js`. Deploy: copy `dist/` →
`backend/public/sand`, pathspec-commit, push (see `../datamine/UPDATE_PIPELINE.md` §4).
