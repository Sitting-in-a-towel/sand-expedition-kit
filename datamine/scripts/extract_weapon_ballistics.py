"""Extract per-ammo projectile ballistics from data.unity3d — the data needed to model
bullet drop and trajectory: muzzle velocity, gravity, drag, plus ricochet and penetration.

Each ammo's CustomProjectileData names a projectile entry; that entry carries:
  BulletProjectileData     -> velocity, gravity, drag, weight
  ProjectileRicochetData   -> angle, count, damageDelta
  ProjectilePenetrationData-> angle, maxPenetrationCount

Output: extracted/json/weapon_ballistics.json (keyed by ammo id). Kept separate from
weapon_stats.json so it can drive an unlisted/offline page without touching public data.
"""
import UnityPy, json, re
from pathlib import Path


def lenient_loads(txt):
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
    return json.loads(re.sub(r",(\s*[}\]])", r"\1", "".join(out)))


HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "extracted" / "json" / "weapon_ballistics.json"
SRC = "gamefiles/Sand_Data/data.unity3d"

MARKERS = ("ItemTypeData", "Template", "BulletProjectileData", "CustomProjectileData",
           "ProjectileRicochetData", "ProjectilePenetrationData", "RangeDamageModifierData",
           "DamagePhysicalData", "NiceNameData")

REG = {}
env = UnityPy.load(SRC)
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

    def collect(node, depth=0):
        if not isinstance(node, dict) or depth > 5:
            return
        for k, v in node.items():
            if isinstance(v, dict):
                if any(m in v for m in MARKERS):
                    REG.setdefault(k, v)
                collect(v, depth + 1)
    collect(doc)

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
        if k != "Template":
            merged[k] = v
    _cache[name] = merged
    return merged


def ballistics_of(proj_name):
    if not isinstance(proj_name, str):
        return None
    p = resolve(proj_name)
    bpd = p.get("BulletProjectileData") or {}
    ric = p.get("ProjectileRicochetData") or {}
    pen = p.get("ProjectilePenetrationData") or {}
    if not (bpd or ric or pen):
        return None
    return {
        "projectile": proj_name,
        "velocity": bpd.get("velocity"),
        "gravity": bpd.get("gravity"),
        "drag": bpd.get("drag"),
        "projectileWeight": bpd.get("weight"),
        "projectileType": bpd.get("projectileType"),
        "ricochet": {"angle": ric.get("angle"), "count": ric.get("count"),
                     "damageDelta": ric.get("damageDelta")} if ric else None,
        "penetration": {"angle": pen.get("angle"),
                        "maxCount": pen.get("maxPenetrationCount")} if pen else None,
    }


def base_projectile_for(ammo_id):
    """Turret ammo variants that don't override the projectile inherit the turret's
    base projectile, so they carry no CustomProjectileData of their own."""
    s = ammo_id.lower()
    if "shotgunturret" in s:
        return "ShotgunTurretBaseProjectile"
    if "smallcannon" in s:
        return "AutoTurretBaseProjectile"
    if "turretammo" in s:
        return "TurretBaseProjectile"
    return None


ammo = {}
for name in REG:
    r = resolve(name)
    it = r.get("ItemTypeData")
    if it not in ("AMMO", "TURRET_AMMO"):
        continue
    b = ballistics_of(r.get("CustomProjectileData"))
    inherited = False
    if not b:
        # fall back to the turret's base projectile so standard/inherited rounds aren't dropped
        bp = base_projectile_for(name)
        if bp:
            b = ballistics_of(bp)
            inherited = bool(b)
    if not b:
        continue
    ammo[name] = {
        "name": r.get("NiceNameData"),
        "turret": it == "TURRET_AMMO",
        "inheritedBallistics": inherited,
        **b,
    }

out = {
    "_source": "data.unity3d ammo CustomProjectileData -> projectile BulletProjectileData "
               "(velocity/gravity/drag), ricochet and penetration. For bullet-drop/trajectory modelling.",
    "ammo": dict(sorted(ammo.items())),
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote {OUT}  ammo with ballistics = {len(ammo)}")
vels = [v["velocity"] for v in ammo.values() if v.get("velocity")]
if vels:
    print(f"velocity range: {min(vels)} to {max(vels)} m/s")
