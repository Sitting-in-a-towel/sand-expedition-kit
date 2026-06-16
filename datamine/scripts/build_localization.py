"""Build site/src/data/localization.json from the game's I2 Localization table.

The I2 `I2Languages` LanguageSourceAsset (baked into Sand_Data/data.unity3d) is the
authoritative source for every in-game display name + description — items, walker
compartments, and research factions/nodes. This replaces our heuristic prettify()
guesses and our hand-typed name overrides with the devs' real strings.

Inputs (in extracted/json/):
  - i2_terms_en.json      full English term table (3440 terms)
  - items_registry.json   authoritative carriable-item list (121 items w/ type + descriptions)
Both were extracted by the community SandTools project (downloadpizza) from data.unity3d;
see datamine/UPDATE_PIPELINE.md for re-extraction at release.

Output: ../site/src/data/localization.json
  { items: {id: {name, short, desc}}, compartments: {epbId: {name, desc}},
    factions: [name...], researchNodes: {name: realName} }
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXT = HERE.parent / "extracted" / "json"
OUT = HERE.parent.parent / "site" / "src" / "data" / "localization.json"


def main():
    terms = json.loads((EXT / "i2_terms_en.json").read_text(encoding="utf-8"))["terms"]
    registry = json.loads((EXT / "items_registry.json").read_text(encoding="utf-8"))["items"]

    # ---- items: registry is authoritative (name+type+descriptions); fall back to I2 Items/ terms
    items = {}
    for iid, e in registry.items():
        items[iid] = {
            "name": e.get("name"),
            "short": e.get("shortDescription") or None,
            "desc": e.get("description") or None,
        }
    # backfill any Items/<id>_name not in the registry (world objects etc.)
    for k, v in terms.items():
        m = re.match(r"Items/(item_\w+)_name$", k)
        if m and m.group(1) not in items and isinstance(v, str):
            iid = m.group(1)
            desc = terms.get(f"Items/{iid}_description")
            short = terms.get(f"Items/{iid}_shortDescription")
            items[iid] = {"name": v, "short": short or None, "desc": desc or None}

    # ---- walker compartments: WalkerCompartments/<epbId>_epb_name + _epb_description
    compartments = {}
    for k, v in terms.items():
        m = re.match(r"WalkerCompartments/(walker_\w+?)_epb_name$", k)
        if m and isinstance(v, str):
            epb = m.group(1)
            desc = terms.get(f"WalkerCompartments/{epb}_epb_description")
            compartments[epb] = {"name": v, "desc": desc or None}

    # ---- research factions (real names beat our guessed Science/Military/Smuggling)
    factions = []
    for k in ("godlewskiExpedition", "landwehr", "kaiserFriends"):
        n = terms.get(f"ResearchTree/faction-{k}-name")
        if n:
            factions.append(n)
    # fall back to any faction-*-name if the keys above shift between builds
    if not factions:
        for k, v in terms.items():
            if re.match(r"ResearchTree/faction-\w+-name$", k) and isinstance(v, str):
                factions.append(v)

    out = {
        "_source": "I2 Localization (data.unity3d) via community SandTools extract",
        "items": items,
        "compartments": compartments,
        "factions": factions,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(
        f"wrote {OUT} — {len(items)} items, "
        f"{sum(1 for i in items.values() if i['desc'])} with descriptions, "
        f"{len(compartments)} compartments, factions={factions}"
    )


if __name__ == "__main__":
    main()
