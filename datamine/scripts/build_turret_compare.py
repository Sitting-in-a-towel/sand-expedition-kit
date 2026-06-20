"""Build site/src/data/turret_compare.json — per-family turret stats across condition
states (Rusty/Worn/Pristine/Experimental = tiers T1-T4): fire rate, reload, clip.
Source: extracted/json/turret_stats.json (all tiers).
"""
import json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "extracted" / "json" / "turret_stats.json"
OUT = HERE.parent.parent / "site" / "src" / "data" / "turret_compare.json"

raw = json.loads(SRC.read_text(encoding="utf-8"))["turrets"]

STATE = {"T1": "Rusty", "T2": "Worn", "T3": "Pristine", "T4": "Experimental"}
STATE_ORDER = {"T1": 0, "T2": 1, "T3": 2, "T4": 3}
FAM = {
    "cannon": {"label": "Cannon Turret", "caliber": "80 mm"},
    "auto": {"label": "Auto Turret", "caliber": "40 mm"},
    "shotgun": {"label": "Shotgun Turret", "caliber": "70 mm"},
}


def humanize(v):
    if not v:
        return None
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", v)


fams = {}
for k, t in raw.items():
    if t.get("armored") or "MountedTurret" not in k or t.get("family") not in FAM:
        continue
    tier = t.get("tier")
    if tier not in STATE:
        continue
    iv = t.get("fireInterval")
    barrels = t.get("barrels") or 1
    row = {
        "state": STATE[tier],
        "tier": tier,
        "variant": humanize(t.get("variant")),
        "fireRate": round(barrels / iv, 2) if iv else None,
        "fireInterval": iv,
        "reloadSeconds": t.get("reloadSeconds"),
        "autoRefill": bool(t.get("autoRefill")),
        "clipSize": t.get("clipSize"),
        "barrels": barrels,
    }
    fams.setdefault(t["family"], []).append(row)

families = []
for fam, meta in FAM.items():
    rows = fams.get(fam, [])
    rows.sort(key=lambda r: (STATE_ORDER[r["tier"]], r.get("variant") or ""))
    families.append({"family": meta["label"], "caliber": meta["caliber"], "rows": rows})

OUT.write_text(json.dumps({"families": families}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote {OUT}")
for f in families:
    print(f"  {f['family']}: {len(f['rows'])} rows")
