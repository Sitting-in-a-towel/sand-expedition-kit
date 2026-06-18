"""Build site/src/data/weapon_ballistics.json from extracted/json/weapon_ballistics.json.
Groups ammo by weapon family and keeps the fields the ballistics page needs.
"""
import json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "extracted" / "json" / "weapon_ballistics.json"
OUT = HERE.parent.parent / "site" / "src" / "data" / "weapon_ballistics.json"

raw = json.loads(SRC.read_text(encoding="utf-8"))["ammo"]


def family(ammo_id):
    s = ammo_id.lower()
    for fam in ("shotgunturret", "turret", "smallcannon", "rocketlauncher",
                "pistol", "rifle", "shotgun", "grapple"):
        if fam in s:
            return {"shotgunturret": "Shotgun Turret", "turret": "Turret",
                    "smallcannon": "Auto Turret", "rocketlauncher": "Rocket Launcher",
                    "pistol": "Pistol", "rifle": "Rifle", "shotgun": "Shotgun",
                    "grapple": "Grapple"}[fam]
    return "Other"


ammo = {}
for k, v in raw.items():
    ammo[k] = {
        "id": k,
        "name": v.get("name"),
        "family": family(k),
        "turret": bool(v.get("turret")),
        "velocity": v.get("velocity"),
        "gravity": v.get("gravity"),
        "drag": v.get("drag"),
        "ricochet": v.get("ricochet"),
        "penetration": v.get("penetration"),
    }

OUT.write_text(json.dumps({"ammo": ammo}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote {OUT}  ({len(ammo)} ammo)")
