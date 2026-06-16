"""Scan data.unity3d (Resources) for the CompartmentsDatabase asset and dump it.
Usage: python scripts/find_compartments_db2.py
"""
import UnityPy, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
from odin_parser import decode

env = UnityPy.load('gamefiles/Sand_Data/data.unity3d')
hits = 0
for o in env.objects:
    if o.type.name not in ('MonoBehaviour', 'ScriptableObject', 'TextAsset'):
        continue
    try:
        t = o.read_typetree()
    except Exception:
        continue
    nm = t.get('m_Name', '')
    if 'ompartment' not in nm:
        continue
    hits += 1
    keys = [k for k in t.keys() if not k.startswith('m_')]
    print(f'{o.type.name} "{nm}" path_id={o.path_id} fields={keys[:12]}')
    if nm == 'CompartmentsDatabase':
        sb = (t.get('serializationData') or {}).get('SerializedBytes')
        if sb:
            doc = decode(sb)
            out = 'extracted/json/compartments_database.json'
            json.dump(doc, open(out, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
            print('   -> Odin doc written to', out)
        else:
            out = 'extracted/json/compartments_database_typetree.json'
            json.dump(t, open(out, 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
            print('   -> typetree written to', out)
print('hits:', hits)
