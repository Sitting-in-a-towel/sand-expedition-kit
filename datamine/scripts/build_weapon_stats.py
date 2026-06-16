"""Build site/src/data/weapon_stats.json (display-ready) from extracted/json/weapon_stats.json.

Keyed by item id so it joins directly with items.json. Derives an effective-range summary
from the damage-vs-distance falloff curve and keeps only the fields the detail UI shows.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "extracted" / "json" / "weapon_stats.json"
OUT = HERE.parent.parent / "site" / "src" / "data" / "weapon_stats.json"


def rng(curve):
    if not curve:
        return None
    dists = [p["distance"] for p in curve if p.get("distance") is not None]
    mults = [p["multiplier"] for p in curve if p.get("multiplier") is not None]
    if not dists or not mults:
        return None
    full_mult = mults[0]
    full = dists[0]
    for d, m in zip(dists, mults):
        if m == full_mult:
            full = d
        else:
            break
    return {"full": full, "max": dists[-1], "minMult": min(mults), "falloff": min(mults) < full_mult}


raw = json.loads(SRC.read_text(encoding="utf-8"))


def _pair(node, *path):
    """Walk nested {min,max} dict by path; return max (the worst-case value)."""
    for p in path:
        if not isinstance(node, dict):
            return None
        node = node.get(p)
    if isinstance(node, dict):
        return node.get("max", node.get("min"))
    return node


def recoil_of(v):
    rd = v.get("recoil")
    if not isinstance(rd, dict):
        return None
    hip = _pair(rd, "recoilPower", "hip")
    scope = _pair(rd, "recoilPower", "scope")
    if not hip and not scope:
        return None
    return {"hip": hip, "scope": scope}


def spread_of(v):
    sd = v.get("spread")
    if not isinstance(sd, dict):
        return None
    hip = _pair(sd, "spreadAngles", "hip", "x")
    scope = _pair(sd, "spreadAngles", "scope", "x")
    if not hip and not scope:
        return None
    return {"hip": hip, "scope": scope}


weapons = {}
for k, v in raw["weapons"].items():
    weapons[k] = {
        "reloadSeconds": v.get("reloadSeconds"),
        "range": rng(v.get("rangeFalloff")),
        "recoil": recoil_of(v),
        "spread": spread_of(v),
    }

ammo = {}
for k, v in raw["ammo"].items():
    cap = v.get("capacity") or {}
    ammo[k] = {
        "turret": bool(v.get("turret")),
        "damagePhysical": v.get("damagePhysical"),
        "range": rng(v.get("rangeFalloff")),
        "penetrates": bool(v.get("penetration")),
        "stack": [cap.get("smallCapacity"), cap.get("mediumCapacity"), cap.get("largeCapacity")]
        if any(cap.values()) else None,
    }

armor = {}
for k, v in raw["armor"].items():
    armor[k] = {"armorRating": v.get("armorRating"), "regen": v.get("regen"), "durability": v.get("durability")}

out = {"weapons": weapons, "ammo": ammo, "armor": armor}
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote {OUT} — weapons={len(weapons)} ammo={len(ammo)} armor={len(armor)}")
