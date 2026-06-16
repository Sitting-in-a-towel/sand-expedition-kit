"""Extract gun / ammo / armor stats from the weapon-family blueprint TextAssets in
data.unity3d (range, reload, recoil, spread, magazine, damage, penetration, armor rating).

These stats were never pulled by the original item-def extraction (icons only), so the
site's gun/ammo/armor detail pages were missing them. Output: extracted/json/weapon_stats.json
(no site changes — diff/review first).

Blueprint shape (per TextAsset): { GameData{}, ActionData{}, Items{}, CustomizationData{} }
or a flat dict of entries. Entries inherit via "Template" (by entry name, resolved globally).
"""
import UnityPy, json, re
from pathlib import Path


def lenient_loads(txt):
    """Parse the game's relaxed JSON: BOM, // and /* */ comments, trailing commas."""
    txt = txt.lstrip("﻿")
    out = []
    i, n = 0, len(txt)
    instr = esc = False
    while i < n:
        c = txt[i]
        if instr:
            out.append(c)
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                instr = False
            i += 1
            continue
        if c == '"':
            instr = True; out.append(c); i += 1; continue
        if c == "/" and i + 1 < n and txt[i + 1] == "/":
            while i < n and txt[i] not in "\r\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and txt[i + 1] == "*":
            i += 2
            while i + 1 < n and not (txt[i] == "*" and txt[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(c); i += 1
    clean = re.sub(r",(\s*[}\]])", r"\1", "".join(out))  # trailing commas
    return json.loads(clean)

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "extracted" / "json" / "weapon_stats.json"
SRC = "gamefiles/Sand_Data/data.unity3d"

SECTIONS = ("GameData", "ActionData", "Items", "CustomizationData", "EntityData", "BlueprintData")

env = UnityPy.load(SRC)

# ---- collect every named entry across all TextAssets, remember its source asset ----
REG = {}        # name -> raw dict
SRC_ASSET = {}  # name -> TextAsset name (family)

MARKERS = ("ItemTypeData", "EquipTypeData", "ActionTypeData", "Template",
           "ArmorPhysicalData", "DamagePhysicalData", "DamageTrueData",
           "RangeDamageModifierData", "ProjectilePenetrationData",
           "RarityData", "NiceNameData", "DurationData", "StackableData")

def collect(node, asset, depth=0):
    """Register any dict that carries entry markers, keyed by its parent key; recurse."""
    if not isinstance(node, dict) or depth > 4:
        return
    for k, v in node.items():
        if isinstance(v, dict):
            if any(m in v for m in MARKERS):
                REG.setdefault(k, v); SRC_ASSET.setdefault(k, asset)
            collect(v, asset, depth + 1)

for o in env.objects:
    if o.type.name != "TextAsset":
        continue
    d = o.read()
    s = d.m_Script
    txt = s if isinstance(s, str) else s.decode("utf-8", "replace")
    if not txt.lstrip("﻿").lstrip().startswith(("{", "[")):
        continue
    try:
        doc = lenient_loads(txt)
    except Exception:
        continue
    collect(doc, d.m_Name)

# ---- resolve Template inheritance globally (parent merged, child overrides) ----
_cache = {}
def resolve(name, stack=()):
    if name in _cache:
        return _cache[name]
    ent = REG.get(name)
    if ent is None or name in stack:
        return ent or {}
    tmpl = ent.get("Template")
    base = resolve(tmpl, stack + (name,)) if isinstance(tmpl, str) and tmpl in REG else {}
    merged = dict(base)
    for k, v in ent.items():
        if k == "Template":
            continue
        merged[k] = v
    _cache[name] = merged
    return merged

def curve(field):
    if isinstance(field, dict) and isinstance(field.get("items"), list):
        return [{"distance": i.get("distance"), "multiplier": i.get("multiplier")}
                for i in field["items"] if isinstance(i, dict)]
    return None

# ---- per asset, index RELOAD actions (name -> duration) ----
reload_by_asset = {}  # asset -> {actionName: seconds}
for name in REG:
    r = resolve(name)
    if r.get("ActionTypeData") == "RELOAD" and isinstance(r.get("DurationData"), (int, float)):
        reload_by_asset.setdefault(SRC_ASSET[name], {})[name] = r["DurationData"]

def pick_reload(item_id, asset):
    opts = reload_by_asset.get(asset, {})
    if not opts:
        return None, opts
    tokens = item_id.lower()
    # prefer a reload action whose name shares a variant token (e.g. ironSights)
    for variant in ("ironsights", "doublebarrel", "eightshot", "small"):
        if variant in tokens:
            for an, sec in opts.items():
                if variant in an.lower():
                    return sec, opts
    # else the shortest-named reload = the family's primary
    primary = min(opts, key=lambda a: len(a))
    return opts[primary], opts

# ---- penetration: ammo.CustomProjectileData -> GameData projectile.ProjectilePenetrationData ----
def penetration(ammo):
    proj = ammo.get("CustomProjectileData")
    if isinstance(proj, str):
        p = resolve(proj).get("ProjectilePenetrationData")
        if p is not None:
            return p
    return None

weapons, ammo, armor = {}, {}, {}
for name in REG:
    r = resolve(name)
    it = r.get("ItemTypeData")
    asset = SRC_ASSET[name]
    if it == "WEAPON":
        sec, opts = pick_reload(name, asset)
        weapons[name] = {
            "name": r.get("NiceNameData"),
            "rarity": r.get("RarityData"),
            "family": asset,
            "reloadSeconds": sec,
            "reloadActions": opts,
            "rangeFalloff": curve(r.get("RangeDamageModifierData")),
            "recoil": r.get("RecoilData"),
            "spread": r.get("SpreadData"),
            "meleeDamageTrue": r.get("DamageTrueData"),
        }
    elif it in ("AMMO", "TURRET_AMMO"):
        st = r.get("StackableData") or {}
        ammo[name] = {
            "name": r.get("NiceNameData"),
            "rarity": r.get("RarityData"),
            "family": asset,
            "turret": it == "TURRET_AMMO",
            "damagePhysical": r.get("DamagePhysicalData"),
            "rangeFalloff": curve(r.get("RangeDamageModifierData")),
            "penetration": penetration(r),
            "capacity": {k: st.get(k) for k in ("smallCapacity", "mediumCapacity", "largeCapacity")} if st else None,
        }
    elif it == "ARMOR" or "ArmorPhysicalData" in r:
        ap = r.get("ArmorPhysicalData") or {}
        armor[name] = {
            "name": r.get("NiceNameData"),
            "rarity": r.get("RarityData"),
            "armorRating": ap.get("value") if isinstance(ap, dict) else ap,
            "regen": r.get("ArmorPhysicalRegenerationData"),
            "durability": r.get("DurabilityData"),
        }

out = {
    "_source": "data.unity3d weapon-family blueprint TextAssets (range/reload/recoil/spread/damage/penetration/armor)",
    "weapons": dict(sorted(weapons.items())),
    "ammo": dict(sorted(ammo.items())),
    "armor": dict(sorted(armor.items())),
}
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote {OUT}")
print(f"weapons={len(weapons)}  ammo={len(ammo)}  armor={len(armor)}")
