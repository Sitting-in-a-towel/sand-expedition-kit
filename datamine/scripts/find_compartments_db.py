"""Find the CompartmentsDatabase asset across candidate bundles and decode it.
Usage: python scripts/find_compartments_db.py
"""
import UnityPy, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
from odin_parser import decode

BASE = 'gamefiles/Sand_Data/StreamingAssets/aa/StandaloneWindows64/'
CANDIDATES = [
    'walkereditor_assets_all.bundle',
    'walkershared_assets_all.bundle',
    'configuration_assets_all.bundle',
    'walker_assets_all.bundle',
]

for b in CANDIDATES:
    path = BASE + b
    if not os.path.exists(path):
        continue
    env = UnityPy.load(path)
    for o in env.objects:
        if o.type.name not in ('MonoBehaviour', 'ScriptableObject'):
            continue
        try:
            t = o.read_typetree()
        except Exception:
            continue
        nm = t.get('m_Name', '')
        if 'ompartment' not in nm:
            continue
        print(f'{b}: {o.type.name} "{nm}" path_id={o.path_id}')
        sb = (t.get('serializationData') or {}).get('SerializedBytes')
        if sb:
            print('   has Odin blob,', len(sb), 'bytes')
            if nm == 'CompartmentsDatabase':
                doc = decode(sb)
                out = 'extracted/json/compartments_database.json'
                json.dump(doc, open(out, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
                print('   -> wrote', out)
        else:
            # plain unity-serialized: dump typetree keys
            print('   plain fields:', [k for k in t.keys() if not k.startswith('m_')][:15])
            if nm == 'CompartmentsDatabase':
                out = 'extracted/json/compartments_database_typetree.json'
                json.dump(t, open(out, 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
                print('   -> wrote', out)
