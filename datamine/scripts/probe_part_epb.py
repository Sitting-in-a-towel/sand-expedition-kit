"""Dump the FULL decoded Odin document of one walker part EPB to JSON for inspection.
Usage: python scripts/probe_part_epb.py <part_id> [out.json]
e.g.   python scripts/probe_part_epb.py compReactor_Round_Metal_2x1
"""
import UnityPy, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
from odin_parser import decode

BASE = 'gamefiles/Sand_Data/StreamingAssets/aa/StandaloneWindows64/'

part_id = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else f'extracted/json/epb_{part_id}.json'
target = f'walker_{part_id}_epb'

env = UnityPy.load(BASE + 'epb_assets_all.bundle')
objs = {o.path_id: o for o in env.objects}
for obj in env.objects:
    if obj.type.name != 'GameObject':
        continue
    go = obj.read()
    if go.m_Name != target:
        continue
    comps = go.m_Component if hasattr(go, 'm_Component') else go.m_Components
    for c in comps:
        ptr = c['component'] if isinstance(c, dict) else c.component
        o = objs.get(ptr['m_PathID'] if isinstance(ptr, dict) else ptr.path_id)
        if not o or o.type.name != 'MonoBehaviour':
            continue
        t = o.read_typetree()
        sb = t.get('serializationData', {}).get('SerializedBytes')
        if not sb:
            continue
        doc = decode(sb)
        json.dump(doc, open(out, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
        comp_types = [str(x.get('$type', '?')) for x in doc.get('components', {}).get('$items', []) if isinstance(x, dict)]
        print('wrote', out)
        print('component types:')
        for ct in comp_types:
            print('  ', ct)
        sys.exit(0)
print('EPB GameObject not found or no Odin blob:', target)
sys.exit(1)
