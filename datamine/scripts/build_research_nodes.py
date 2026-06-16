# Build site/src/data/research_nodes.json from ProgressionTreeDescriptions
# (extracted from walkershared_assets_all.bundle — see UPDATE_PIPELINE.md).
#
# What IS in the files: the real research-node catalog (98 nodes: id GUID, name,
# description, uiPriority). What is NOT: edges (RequiredNodes), costs (ResearchPrice),
# tier, faction — those arrive per-account from the masterserver (ResearchTreeJsonDto).
#
# We enrich with: tier parsed from the name (T1-T4), a best-effort compartment match
# (so the page can show part thumbnails), and a category guess from the name.

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXTRACTED = HERE.parent / "extracted" / "json"
SITE_DATA = HERE.parent.parent / "site" / "src" / "data"

PLACEHOLDER = "Some beautiful and full of expression"


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def main():
    desc = json.loads((EXTRACTED / "progression_tree_descriptions.json").read_text(encoding="utf-8"))["database"]
    parts = json.loads((SITE_DATA / "parts_v2.json").read_text(encoding="utf-8"))
    part_list = parts["parts"] if isinstance(parts, dict) and "parts" in parts else parts

    # index compartments by normalized id fragments + display name; keep group lookup
    comp_index = []
    comp_group = {}
    for p in part_list:
        pid = p.get("id", "")
        comp_index.append((norm(pid.replace("comp", "")), norm(p.get("name", "")), pid))
        groups = p.get("groups") or []
        comp_group[pid] = groups[0] if groups else None

    # compartment partsGroup -> display row (matches the in-game tech-tree row layout)
    GROUP_ROW = {
        "CHASSIS": "Chassis", "WEAPONE": "Weapons", "WEAPON": "Weapons", "CARGO": "Cargo",
        "SPECIAL": "Special", "BALCONY": "Decks", "DECK": "Decks", "ENGINE": "Engines",
        "STEERING": "Steering", "REACTOR": "Engines", "CREW": "Crew", "CAPTAIN": "Crew",
        "CRAFTING": "Workshop", "CORRIDOR": "Entrances", "ARMOR": "Armor", "GENERIC": "Other",
    }

    def classify_row(name, comp):
        if comp and comp_group.get(comp) in GROUP_ROW:
            return GROUP_ROW[comp_group[comp]]
        n = name.lower()
        for pat, row in [
            (r"chassis", "Chassis"),
            (r"ammo|cannon|shotgun|shell|rifle|\bgun|explosiv|grenade|c4|turret|embrasure|battering|ram", "Weapons"),
            (r"armor|armour|plate", "Armor"),
            (r"cargo|storage", "Cargo"),
            (r"deck|balcony|stair|railing|bridge", "Decks"),
            (r"steering|helm|wheel|rudder", "Steering"),
            (r"engine|reactor|cruis|accelerat|cruise", "Engines"),
            (r"crew|captain|cabin|quarters|bed|medkit|medic", "Crew"),
            (r"corridor|entry|entrance|door|hatch|ladder", "Entrances"),
            (r"craft|workbench|workshop|sewing", "Workshop"),
            (r"resourc|food|fuel|repair|valuable", "Supplies"),
        ]:
            if re.search(pat, n):
                return row
        return "Other"

    nodes = []
    for guid, d in desc.items():
        name = d.get("name", guid)
        description = d.get("description", "")
        if PLACEHOLDER in description:
            description = ""  # dev placeholder text — not worth shipping
        m = re.search(r"\bT(\d)\b|T(\d)$", name)
        tier = int(m.group(1) or m.group(2)) if m else None

        # best-effort compartment match for a thumbnail: every meaningful token of the
        # node name must appear in the compartment id or display name ("framed" matches "frame")
        toks = [t.lower() for t in re.findall(r"[A-Za-z]+|\d+x\d+", name) if t.lower() not in ("bay", "and", "t")]
        toks = [t for t in toks if not re.fullmatch(r"t\d", t)]
        match = None
        best = 0
        for frag_id, frag_name, pid in comp_index:
            hay = frag_id + "|" + frag_name
            ok = [t for t in toks if t in hay or t.rstrip("d") in hay or t.rstrip("s") in hay]
            if len(ok) == len(toks) and len(toks) > best:
                match = pid
                best = len(toks)
        n = norm(name)

        cat = "Compartments"
        if "chassis" in n:
            cat = "Chassis"
        elif re.search(r"ammo|explosive|shotgun|cannon|turret|weapon|armor", n):
            cat = "Combat"
        elif re.search(r"medkit|resources|valuable|food|fuel|repair", n):
            cat = "Supplies"

        nodes.append({
            "id": guid,
            "name": name,
            "description": description,
            "uiPriority": d.get("uiPriority"),
            "tier": tier,
            "category": cat,
            "row": classify_row(name, match),
            "compartment": match,
        })

    # real faction names from the I2 Localization table (build_localization.py)
    factions = ["Science", "Military", "Smuggling"]  # fallback
    loc_path = SITE_DATA / "localization.json"
    if loc_path.exists():
        loc_factions = json.loads(loc_path.read_text(encoding="utf-8")).get("factions")
        if loc_factions:
            factions = loc_factions

    nodes.sort(key=lambda x: (x["uiPriority"] is None, x["uiPriority"] if x["uiPriority"] is not None else 0, x["name"]))
    out = {
        "source": "ProgressionTreeDescriptions (walkershared_assets_all.bundle)",
        "note": "Node catalog is real game data. Edges, unlock costs, tier zones and faction assignment are served per-account by the masterserver (ResearchTreeJsonDto) and are NOT in the files.",
        "factions": factions,
        "nodes": nodes,
    }
    dest = SITE_DATA / "research_nodes.json"
    dest.write_text(json.dumps(out, indent=1), encoding="utf-8")
    matched = sum(1 for x in nodes if x["compartment"])
    print(f"wrote {dest} — {len(nodes)} nodes, {matched} matched to compartments")


if __name__ == "__main__":
    main()
