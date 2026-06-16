# UPDATE PIPELINE — full data reset for a new game build

> Owner requirement (2026-06-11): *"make sure the database is always able to be reset with
> whatever new data comes with updates to keep all that hard work relevant."*
> This file is the answer: every site data file regenerates from the scripts below.
> **Release lands 22 June 2026 — run this whole pipeline against the release install.**

## 0. Refresh the file copy (NEVER mine the live install)
```powershell
# adjust source to the release install folder when it exists
$src = "H:\Steam Games\steamapps\common\Sand Playtest"
$dst = "H:\Project Folder\SAND\datamine\gamefiles"
robocopy "$src\Sand_Data" "$dst\Sand_Data" /MIR
Copy-Item "$src\GameAssembly.dll" $dst -Force
```
All scripts below run from `H:\Project Folder\SAND\datamine` with plain `python` (needs
`UnityPy`, `numpy`, `Pillow`).

## 1. Class/struct reference (only needed for new investigations)
Il2CppDumper (in `tools/il2cppdumper/`) on `gamefiles/GameAssembly.dll` +
`gamefiles/Sand_Data/il2cpp_data/Metadata/global-metadata.dat` → `extracted/il2cpp_dump/dump.cs`.

## 2. Core data extraction (order matters)
```bash
python scripts/extract_icons.py                       # item icons -> extracted/icons + site
python scripts/build_site_data.py                     # loot tables, items, recipes, locations -> site/src/data
python scripts/extract_loot_spawners.py               # raw per-entity drop weights (Odin blobs)
python scripts/build_loot_sources.py                  # -> site loot_sources.json (containers tab)
python scripts/scan_location_prefabs.py               # raw prefab content scan -> extracted/json/location_contents.json
python scripts/build_location_contents.py             # -> site location_contents.json + extra_locations.json
python scripts/extract_compartments_db.py             # CompartmentsDatabase (the in-game builder DB)
python scripts/build_parts_v2.py                      # -> site parts_v2.json
python scripts/extract_progression_descriptions.py    # research node catalog (tech tree)
python scripts/build_localization.py                  # I2 names+descriptions -> localization.json (run BEFORE build_site_data/parts/research)
python scripts/build_site_data.py                     # (re-run: items now pull loc names+descriptions)
python scripts/build_research_nodes.py                # -> site research_nodes.json (real faction names)
```
Localization source: `extracted/json/i2_terms_en.json` + `items_registry.json` — the game's I2
Localization table from `data.unity3d`. Currently vendored from the community SandTools extract
(downloadpizza); at release, re-extract the `I2Languages` LanguageSourceAsset from `data.unity3d`
(UnityPy + TypeTreeGenerator) or refresh from their repo. This is the authoritative name source —
it supersedes the heuristic prettify() fallbacks for items AND compartments.

## 3. Art pipelines (slow ones)
```bash
python scripts/render_part_thumbs.py        # v1 part thumbs  -> site/public/parts
python scripts/export_part_meshes_v3.py     # builder meshes WITH UVs + albedo textures -> meshes3/ + tex3/
python scripts/render_thumbs_v2.py          # v2 part thumbs  -> site/public/parts2
python scripts/render_location_thumbs.py    # ops board location art -> site/public/locart
python scripts/render_container_thumbs.py   # loot-container models -> site/public/containers
```
`render_location_thumbs.py` loads islands+pois+geometry bundles (~2 GB RAM, several minutes)
and skips art that already exists — delete `site/public/locart/*` first for a clean re-render.

## 4. Rebuild + deploy the site
```powershell
cd "H:\Project Folder\SAND\site"; npm run build
robocopy dist "H:\Project Folder\Predecessor website\backend\public\sand" /MIR
# then in the Predecessor website repo: git add backend/public/sand,
# pathspec commit, push -> Render auto-deploys.
# Verify https://pred.city/sand-wormpit-7x2k/ (URL deliberately non-obvious, owner 2026-06-11;
# must match `base` in site/vite.config.js AND the route in backend/server.js).
```

## 5. After-update checklist (things that drift between builds)
- **dump.cs TypeDefIndexes shift** — re-dump before trusting old line numbers.
- **Bundle names/layout can change** — every extractor prints what it found; a "NOT FOUND"
  means the asset moved, search with a name scan (see `find_db_textasset.py` pattern).
- **Re-verify the merge/alias maps in `site/src/lib/data.js`** (`MERGE_ALIAS`, `DISPLAY_ALIAS`)
  and the loot-flavour/instance regexes — new locations may need new entries.
- **Owner/friend in-game name collection** — internal names (e.g. `Factorio`) display until a
  real in-game name is added to `DISPLAY_ALIAS`.
- **Contracts data is flagged UNVERIFIED** — re-mine and re-check against the live game; remove
  the banner in `Contracts.jsx` once confirmed current.
- **Check Player.log after a real match** for a visible map seed (upgrade path: seed → map
  regeneration tool).
- **Research tree** — if the masterserver tree ever ships client-side (or dev data arrives),
  wire edges/prices into `research_nodes.json` and upgrade the Tech Tree page to a real graph.
