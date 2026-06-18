"""Extract per-part combat/physics stats from the walker part EPBs (epb_assets_all.bundle).

parts_v2.json currently holds geometry only. Each part's entity blueprint also carries:
  HealthDataComponent.value            -> part HP
  PhysicsDataComponent.mass            -> part mass (build weight)
  WalkerCompartmentDataComponent       -> explodesOnDestruction (chain-explosion risk)
  SurfaceTypeDataComponent.value       -> surface/armour material id

Output: extracted/json/part_stats.json keyed by part id (no walker_ prefix, no _epb suffix),
so it merges 1:1 with parts_v2.json. Reads the newer gamefiles/ bundle.
"""
import UnityPy, json, os, sys, re
sys.path.insert(0, os.path.dirname(__file__))
from odin_parser import decode

BASE = 'gamefiles/Sand_Data/StreamingAssets/aa/StandaloneWindows64/'
OUT = 'extracted/json/part_stats.json'


def short(t):
    return str(t).split('.')[-1].split(',')[0]


def find(items, name):
    for it in items:
        if isinstance(it, dict) and short(it.get('$type', '')) == name:
            return it
    return None


env = UnityPy.load(BASE + 'epb_assets_all.bundle')
objs = {o.path_id: o for o in env.objects}

stats = {}
for obj in env.objects:
    if obj.type.name != 'GameObject':
        continue
    go = obj.read()
    name = go.m_Name
    if not (name.startswith('walker_comp') and name.endswith('_epb')):
        continue
    comps = go.m_Component if hasattr(go, 'm_Component') else go.m_Components
    doc = None
    for c in comps:
        ptr = c['component'] if isinstance(c, dict) else c.component
        o = objs.get(ptr['m_PathID'] if isinstance(ptr, dict) else ptr.path_id)
        if not o or o.type.name != 'MonoBehaviour':
            continue
        t = o.read_typetree()
        sb = t.get('serializationData', {}).get('SerializedBytes')
        if sb:
            doc = decode(sb)
            break
    if not doc:
        continue
    items = doc.get('components', {}).get('$items', [])
    health = find(items, 'HealthDataComponent')
    phys = find(items, 'PhysicsDataComponent')
    comp = find(items, 'WalkerCompartmentDataComponent')
    surf = find(items, 'SurfaceTypeDataComponent')

    pid = re.sub(r'^walker_', '', re.sub(r'_epb$', '', name))
    stats[pid] = {
        'hp': health.get('value') if health else None,
        'mass': phys.get('mass') if phys else None,
        'explodes': bool(comp.get('explodesOnDestruction')) if comp else None,
        'surfaceType': surf.get('value') if surf else None,
    }

os.makedirs('extracted/json', exist_ok=True)
json.dump(stats, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('wrote', OUT, '-', len(stats), 'parts')
hps = [v['hp'] for v in stats.values() if v['hp']]
masses = [v['mass'] for v in stats.values() if v['mass']]
expl = sum(1 for v in stats.values() if v['explodes'])
print(f'hp range:   {min(hps):.0f} to {max(hps):.0f}  (n={len(hps)})')
print(f'mass range: {min(masses):g} to {max(masses):g}  (n={len(masses)})')
print(f'explode-on-destruction parts: {expl}')
