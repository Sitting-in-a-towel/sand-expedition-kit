"""Build site/src/data/turret_stats.json (display-ready) from extracted/json/turret_stats.json.

The site shows the carryable packed-turret items (game_packed*TurretT*Container, present in
items.json); the mined stats are keyed by the deployed mounted turret (walker_*MountedTurret_T*).
This maps each container -> its mounted turret by family + tier (+ variant), so statsFor(containerId)
in the site resolves turret stats. Damage is the turret's ammo damage (ammoTypes -> ammo[] in
weapon_stats.json); fire rate = barrels / fireInterval.
"""
import json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "extracted" / "json" / "turret_stats.json"
ITEMS = HERE.parent.parent / "site" / "src" / "data" / "items.json"
OUT = HERE.parent.parent / "site" / "src" / "data" / "turret_stats.json"

raw = json.loads(SRC.read_text(encoding="utf-8"))["turrets"]
items = json.loads(ITEMS.read_text(encoding="utf-8"))
item_ids = {i["id"] for i in items} if isinstance(items, list) else set(items)

# index mined turrets by (family, tier, variant) — non-armored only (containers are carryable)
by_key = {}
for tid, t in raw.items():
    if t.get("armored"):
        continue
    key = (t["family"], t.get("tier"), (t.get("variant") or "").lower())
    by_key[key] = (tid, t)


def container_key(cid):
    """Derive (family, tier, variant) from a packed-container id."""
    low = cid.lower()
    if "packedautoturret" in low:
        fam = "auto"
    elif "packedshotgunturret" in low:
        fam = "shotgun"
    else:
        fam = "cannon"
    tm = re.search(r"t(\d)", low)
    tier = f"T{tm.group(1)}" if tm else None
    variant = None
    for v in ("railgun", "doublebarrel", "accelerating"):
        if v in low:
            variant = v
            break
    return fam, tier, variant


def fire_rate(t):
    iv = t.get("fireInterval")
    n = t.get("barrels") or 1
    if not iv:
        return None
    return round(n / iv, 2)


turrets = {}
unmatched = []
for cid in sorted(i for i in item_ids if "turret" in i.lower() and "ammo" not in i.lower()):
    fam, tier, variant = container_key(cid)
    hit = by_key.get((fam, tier, (variant or "")))
    if not hit:
        # fall back to same family+tier without a variant
        hit = by_key.get((fam, tier, ""))
    if not hit:
        unmatched.append(cid)
        continue
    tid, t = hit
    turrets[cid] = {
        "family": t["family"],
        "tier": t.get("tier"),
        "variant": t.get("variant"),
        "barrels": t.get("barrels"),
        "fireRate": fire_rate(t),          # shots/sec across all barrels
        "fireInterval": t.get("fireInterval"),
        "reloadSeconds": t.get("reloadSeconds"),
        "clipSize": t.get("clipSize"),
        "autoRefill": t.get("autoRefill"),
        "ammoTypes": t.get("ammoTypes"),   # join to ammo[] in weapon_stats.json for damage
        "spreadIdleMax": t.get("spreadIdleMax"),
        "projectileVelocity": (t.get("projectile") or {}).get("velocity"),
        "penetrates": ((t.get("projectile") or {}).get("penetrationCount") or 0) > 0,
        "source": tid,
    }

OUT.write_text(json.dumps({"turrets": turrets}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote {OUT} — turrets={len(turrets)}")
if unmatched:
    print(f"unmatched containers ({len(unmatched)}): {unmatched}")
