"""Build site/src/data/part_slug_map.json — our part id -> Baal's Sand-wiki entity slug.

Reproduces Baal's reconcile() (baseline slug by localized-name match, else slugify(name)),
then DETERMINISTICALLY disambiguates collisions. Our part names aren't unique (mirror parts
and size variants share a localized name), so colliding slugs get the footprint dimensions
(bounds[0]xbounds[2], matching Baal's baseline scheme e.g. 'covered-1x3'/'covered-2x2') and a
'-mirror' flag. Baal's authoritative baseline slugs are preserved untouched. Order-independent.
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


# explicit part-id -> slug overrides where our localized name can't name-match Baal's baseline
# (his name carries in-game dims our name lacks, and our raw bounds differ from his label).
PART_OVERRIDE = {
    "compReactor_Long_Wood_1x3": "nz-aze80-motor-reactor-covered-1x3",   # his "Covered (1x3)"
    "compReactor_Round_Wood_2x1": "nz-aze80-motor-reactor-covered-2x2",  # his "Covered (2x2)" (really 2x2)
}


def slugify(n):
    return re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")


parts = json.loads(PARTS.read_text(encoding="utf-8"))["parts"]
byid = {p["id"]: p for p in parts}

# pass 1: candidate slug (id override > baseline name-match > slugify)
cand = {}
for p in parts:
    name = p.get("name") or p["id"]
    if p["id"] in PART_OVERRIDE:
        cand[p["id"]] = (True, PART_OVERRIDE[p["id"]])
    elif name in BASELINE:
        cand[p["id"]] = (True, BASELINE[name])
    else:
        cand[p["id"]] = (False, slugify(name))

# which candidate slugs are shared by >1 part?
from collections import Counter
counts = Counter(s for _, s in cand.values())

mapping, taken, disamb = {}, set(), []
# baseline slugs first (reserved, never disambiguated)
for pid, (is_base, s) in cand.items():
    if is_base:
        mapping[pid] = s
        taken.add(s)
# slugified: keep if unique, else disambiguate by dims + mirror
for pid, (is_base, s) in sorted(cand.items()):
    if is_base:
        continue
    if counts[s] == 1 and s not in taken:
        mapping[pid] = s
        taken.add(s)
        continue
    p = byid[pid]
    b = p.get("bounds") or [0, 0, 0]
    slug = f"{s}-{b[0]}x{b[2]}"
    if pid.endswith("_mirror"):
        slug += "-mirror"
    base, n = slug, 2
    while slug in taken:
        slug = f"{base}-{n}"
        n += 1
    mapping[pid] = slug
    taken.add(slug)
    disamb.append((pid, p.get("name"), slug))

OUT.write_text(json.dumps(mapping, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote {OUT}  ({len(mapping)} parts | {len(set(mapping.values()))} unique slugs)")
print(f"  disambiguated (dims/mirror): {len(disamb)}")
for pid, nm, slug in sorted(disamb, key=lambda x: x[2]):
    print(f"    {slug:46} <- {nm}")
