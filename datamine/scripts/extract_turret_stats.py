"""Extract mounted-turret weapon stats from data.unity3d.

Turrets aren't WEAPON-type items — each turret item (walker_*MountedTurret*) carries:
  - ClipData            -> magazine size + accepted ammo type ids (damage lives on the ammo,
                           already pulled by extract_weapon_stats.py)
  - InteractActionsData -> named actions; the one with ActionTypeData=="ATTACK" is the shot
                           (DurationData = fire interval, ApplySpawnProjectileData = projectile,
                            ApplyConsumeAmmoData = ammo per shot); ActionTypeData=="RELOAD" is reload.
  - SpreadData / RecoilData -> accuracy
The spawned projectile carries velocity / penetration / ricochet.

Three families (cannon / auto / shotgun), tiers T1-T4 (+ RailGun / DoubleBarrel / Accelerating),
plus Armored variants. Output: extracted/json/turret_stats.json (no site changes — diff/review first).
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
    clean = re.sub(r",(\s*[}\]])", r"\1", "".join(out))
    return json.loads(clean)


HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "extracted" / "json" / "turret_stats.json"
SRC = "gamefiles/Sand_Data/data.unity3d"

# ---- collect every named entry across all TextAssets into one global registry ----
REG = {}        # name -> raw dict
SRC_ASSET = {}  # name -> TextAsset (family) it came from

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
    if not isinstance(doc, dict):
        continue
    for sect, val in doc.items():
        if isinstance(val, dict):
            for k, v in val.items():
                if isinstance(v, dict):
                    REG.setdefault(k, v)
                    SRC_ASSET.setdefault(k, d.m_Name)

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
        if k != "Template":
            merged[k] = v
    _cache[name] = merged
    return merged


def family_of(item_id):
    low = item_id.lower()
    if "shotgun" in low:
        return "shotgun"
    if "auto" in low:
        return "auto"
    if "cannon" in low:
        return "cannon"
    return "other"


def tier_of(item_id):
    m = re.search(r"_(T\d)(?:_([A-Za-z]+))?$", item_id)
    if not m:
        return None, None
    return m.group(1), m.group(2)  # e.g. ("T4", "RailGun")


def spread_max(sd):
    """Worst-case idle horizontal spread angle."""
    if not isinstance(sd, dict):
        return None
    ang = sd.get("spreadAngles") or {}
    for bucket in ("idle", "hip", "scope"):
        b = ang.get(bucket)
        if isinstance(b, dict):
            x = b.get("x")
            if isinstance(x, dict):
                return x.get("max", x.get("min"))
    return None


def projectile_of(action):
    proj = action.get("ApplySpawnProjectileData")
    if isinstance(proj, dict) and isinstance(proj.get("name"), str):
        p = resolve(proj["name"])
        bpd = p.get("BulletProjectileData") or {}
        pen = p.get("ProjectilePenetrationData") or {}
        ric = p.get("ProjectileRicochetData") or {}
        return {
            "name": proj["name"],
            "velocity": bpd.get("velocity"),
            "gravity": bpd.get("gravity"),
            "drag": bpd.get("drag"),
            "penetrationCount": pen.get("maxPenetrationCount"),
            "ricochetCount": ric.get("count"),
        }
    return None


def action_names(r):
    """Manual actions live in InteractActionsData; auto-turret barrels in AutoTurretShotActionsData."""
    names = list((r.get("InteractActionsData") or {}).get("names") or [])
    names += list((r.get("AutoTurretShotActionsData") or {}).get("names") or [])
    return [n for n in names if isinstance(n, str)]


turrets = {}
for item_id, raw in REG.items():
    if "MountedTurret" not in item_id:
        continue
    r = resolve(item_id)
    clip = r.get("ClipData")
    names = action_names(r)
    if not isinstance(clip, dict) or not names:
        continue

    attacks, reload_act = [], None
    for an in names:
        a = resolve(an)
        t = a.get("ActionTypeData")
        if t == "ATTACK":
            attacks.append((an, a))
        elif t == "RELOAD" and reload_act is None:
            reload_act = (an, a)
    if not attacks:
        continue  # no fire action -> not a real mounted weapon

    an, a = attacks[0]  # barrels share stats; use the first
    tier, variant = tier_of(item_id)
    turrets[item_id] = {
        "name": r.get("NiceNameData"),
        "rarity": r.get("RarityData"),
        "family": family_of(item_id),
        "tier": tier,
        "variant": variant,
        "armored": "Armored" in item_id,
        "barrels": len(attacks),
        "clipSize": clip.get("size"),
        "autoRefill": bool(clip.get("autoRefill")),
        "ammoTypes": clip.get("ammoTypes"),
        "fireInterval": a.get("DurationData"),
        "ammoPerShot": a.get("ApplyConsumeAmmoData"),
        "reloadSeconds": resolve(reload_act[0]).get("DurationData") if reload_act else None,
        "spreadIdleMax": spread_max(r.get("SpreadData")),
        "projectile": projectile_of(a),
        "_attackAction": an,
    }

out = {
    "_source": "data.unity3d mounted-turret items (ClipData + ATTACK/RELOAD actions + spawned projectile). "
               "Turret damage comes from its ammo — see ammo[] in weapon_stats.json, keyed by the ammoTypes ids here.",
    "turrets": dict(sorted(turrets.items())),
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote {OUT}")
print(f"turrets={len(turrets)}")
for fam in ("cannon", "auto", "shotgun", "other"):
    print(f"  {fam}: {sum(1 for v in turrets.values() if v['family']==fam)}")
