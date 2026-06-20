"""Build site/src/data/part_slug_map.json — our part id -> Baal's Sand-wiki entity slug.

Reproduces Baal's reconcile() exactly: slug = his baseline slug where the localized name
matches one of his committed trampler-part entities, else slugify(name)
(toLowerCase, non-alphanumeric -> "-", trimmed, numeric de-dup). His part-slug override
map is empty, so this is deterministic. The 22 baseline (name->slug) below are from his
packages/data/generated/entities.json (kind=trampler-part); only the captain compartment
is a non-slugify override.
"""
import json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARTS = HERE.parent.parent / "site" / "src" / "data" / "parts_v2.json"
OUT = HERE.parent.parent / "site" / "src" / "data" / "part_slug_map.json"

BASELINE = {
    "S&H Captain's Compartment": "captain-crew-module",
    'KF-B "Hole" Middling Chassis': "kf-b-hole-middling-chassis",
    'KF-B "Trench" Great Chassis': "kf-b-trench-great-chassis",
    'KF "Kormylo" Wheelhouse': "kf-kormylo-wheelhouse",
    'KF-L "Abyss" Royal Chassis': "kf-l-abyss-royal-chassis",
    'KF-L "Hole" Middling Chassis': "kf-l-hole-middling-chassis",
    'KF-L "Trench" Great Chassis': "kf-l-trench-great-chassis",
    'KF "Nest" Framed Armored Turret Deck': "kf-nest-framed-armored-turret-deck",
    'KF "Nest" Framed Turret Deck': "kf-nest-framed-turret-deck",
    'KF "Prolomnyk" Battering Ram': "kf-prolomnyk-battering-ram",
    'KF-Q "Abyss" Royal Chassis': "kf-q-abyss-royal-chassis",
    'KF-Q "Trench" Great Chassis': "kf-q-trench-great-chassis",
    'KF-Q "Well" Small Chassis': "kf-q-well-small-chassis",
    'NZ AzE80 Motor-Reactor, Covered (1x3)': "nz-aze80-motor-reactor-covered-1x3",
    'NZ AzE80 Motor-Reactor, Covered (2x2)': "nz-aze80-motor-reactor-covered-2x2",
    'NZ AzE81 Motor-Reactor, Armored': "nz-aze81-motor-reactor-armored",
    'NZ AzE81L Deck Motor-Reactor, Rounded': "nz-aze81l-deck-motor-reactor-rounded",
    'NZ AzE81S Deck Motor-Reactor, Long': "nz-aze81s-deck-motor-reactor-long",
    'NZ AzE81S Motor-Reactor, Framed Long': "nz-aze81s-motor-reactor-framed-long",
    'NZ AzE82 Motor-Reactor, Armored': "nz-aze82-motor-reactor-armored",
    'NZ Mb2k Maneuver Engine, Small': "nz-mb2k-maneuver-engine-small",
    'NZ Mb3 Maneuver Engine, Medium': "nz-mb3-maneuver-engine-medium",
}


def slugify(n):
    return re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")


parts = json.loads(PARTS.read_text(encoding="utf-8"))["parts"]
taken = set()
mapping = {}
matched = slugified = collisions = 0
for p in sorted(parts, key=lambda x: x["id"]):
    name = p.get("name") or p["id"]
    if name in BASELINE:
        slug = BASELINE[name]; matched += 1
    else:
        slug = slugify(name); slugified += 1
    base = slug
    n = 2
    while slug in taken:  # de-dup like reconcile (base-2, base-3, ...)
        slug = f"{base}-{n}"; n += 1; collisions += 1
    taken.add(slug)
    mapping[p["id"]] = slug

OUT.write_text(json.dumps(mapping, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote {OUT}  ({len(mapping)} parts)")
print(f"  baseline-matched: {matched}  | slugified: {slugified}  | de-dup collisions: {collisions}")
print("  samples:")
for pid in list(mapping)[:6]:
    print(f"    {pid:38} -> {mapping[pid]}")
