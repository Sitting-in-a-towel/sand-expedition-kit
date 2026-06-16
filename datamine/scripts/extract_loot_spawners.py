"""Extract LootSetupDataComponent (loot table ids + chances) from every EPB.
Also records weight/HP-ish fields on walker_comp* EPBs if any exist.
Output: extracted/json/entity_loot.json
"""
import UnityPy, json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from odin_parser import decode

BUNDLES = ['epb_assets_all.bundle', 'env_epb_assets_all.bundle']
BASE = 'gamefiles/Sand_Data/StreamingAssets/aa/StandaloneWindows64/'

def find_components(doc, type_frag):
    out = []
    items = doc.get('components', {}).get('$items', [])
    for c in items:
        if isinstance(c, dict) and type_frag in str(c.get('$type', '')):
            out.append(c)
    return out

def parse_entries(node):
    """entries list -> [{tableId, chance} | {set: [...], chance}]"""
    out = []
    if not isinstance(node, dict):
        return out
    for e in node.get('$items', []):
        if not isinstance(e, dict):
            continue
        t = str(e.get('$type', ''))
        if 'LootTableSetEntry' in t:
            out.append({
                'chance': e.get('chance'),
                'set': parse_entries(e.get('entries', {})),
            })
        elif 'LootTableEntry' in t:
            out.append({'tableId': e.get('tableId'), 'chance': e.get('chance')})
    return out

result = {}
walker_stats = {}
errors = 0
for b in BUNDLES:
    env = UnityPy.load(BASE + b)
    objs = {obj.path_id: obj for obj in env.objects}
    for obj in env.objects:
        if obj.type.name != 'GameObject':
            continue
        try:
            go = obj.read()
            name = go.m_Name
            if not name.endswith('_epb'):
                continue
            comps = go.m_Component if hasattr(go, 'm_Component') else go.m_Components
            for c in comps:
                ptr = c['component'] if isinstance(c, dict) else c.component
                pid = ptr['m_PathID'] if isinstance(ptr, dict) else ptr.path_id
                o = objs.get(pid)
                if not o or o.type.name != 'MonoBehaviour':
                    continue
                t = o.read_typetree()
                sb = t.get('serializationData', {}).get('SerializedBytes', [])
                if not sb:
                    continue
                try:
                    doc = decode(sb)
                except Exception:
                    errors += 1
                    continue
                loots = find_components(doc, 'LootSetupDataComponent')
                for lc in loots:
                    entry = {
                        'entries': parse_entries(lc.get('entries', {})),
                        'mandatory': parse_entries(lc.get('mandatory', {})),
                    }
                    if entry['entries'] or entry['mandatory']:
                        result[name.removesuffix('_epb')] = entry
                if name.startswith('walker_comp'):
                    s = json.dumps(doc, default=str)
                    interesting = {}
                    for comp in doc.get('components', {}).get('$items', []):
                        if not isinstance(comp, dict):
                            continue
                        tn = str(comp.get('$type', '')).split(',')[0].split('.')[-1]
                        for k, v in comp.items():
                            if isinstance(v, (int, float)) and any(w in k.lower() for w in ('weight', 'hp', 'health', 'mass', 'durab', 'price')):
                                interesting[f'{tn}.{k}'] = v
                    if interesting:
                        walker_stats[name.removesuffix('_epb')] = interesting
        except Exception:
            errors += 1

os.makedirs('extracted/json', exist_ok=True)
json.dump(result, open('extracted/json/entity_loot.json', 'w', encoding='utf-8'), indent=1)
json.dump(walker_stats, open('extracted/json/walker_part_stats.json', 'w', encoding='utf-8'), indent=1)
print(f'{len(result)} entities with loot entries, {len(walker_stats)} walker parts with stat-ish fields, {errors} errors')
print('sample:', json.dumps(dict(list(result.items())[:2]), indent=1)[:600])
