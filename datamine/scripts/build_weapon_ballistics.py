"""Build site/src/data/weapon_ballistics.json from extracted/json/weapon_ballistics.json.
All three turret kinds (cannon/auto/shotgun) are grouped under one "Turrets" family,
with a per-row turret type + ammo variant label so the variants are legible.
"""
import json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "extracted" / "json" / "weapon_ballistics.json"
OUT = HERE.parent.parent / "site" / "src" / "data" / "weapon_ballistics.json"

raw = json.loads(SRC.read_text(encoding="utf-8"))["ammo"]


def classify(ammo_id):
    """-> (group, turretType or None). All turrets share one group."""
    s = ammo_id.lower()
    if "shotgunturret" in s:
        return "Turrets", "Shotgun Turret"
    if "smallcannon" in s:
        return "Turrets", "Auto Turret"
    if "turretammo" in s:
        return "Turrets", "Cannon Turret"
    for fam, label in (("rocketlauncher", "Rocket Launcher"), ("pistol", "Pistol"),
                       ("rifle", "Rifle"), ("shotgun", "Shotgun"), ("grapple", "Grapple")):
        if fam in s:
            return label, None
    return "Other", None


def variant(ammo_id):
    """Humanised ammo variant from the id suffix after 'Ammo' (Standard if none)."""
    suf = ammo_id.split("Ammo", 1)[1] if "Ammo" in ammo_id else ""
    suf = suf.lstrip("_")
    if not suf:
        return "Standard"
    suf = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", suf).replace("_", " ")
    out = suf.strip().title()
    return re.sub(r"\bEmp\b", "EMP", out)


ammo = {}
for k, v in raw.items():
    group, tt = classify(k)
    var = variant(k)
    label = f"{tt} · {var}" if tt else (v.get("name") or k)
    ammo[k] = {
        "id": k,
        "name": v.get("name"),
        "family": group,
        "turretType": tt,
        "variant": var,
        "label": label,
        "inherited": bool(v.get("inheritedBallistics")),
        "velocity": v.get("velocity"),
        "gravity": v.get("gravity"),
        "drag": v.get("drag"),
        "ricochet": v.get("ricochet"),
        "penetration": v.get("penetration"),
    }

OUT.write_text(json.dumps({"ammo": ammo}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote {OUT}  ({len(ammo)} ammo)")
from collections import Counter
print("groups:", Counter(a["family"] for a in ammo.values()))
