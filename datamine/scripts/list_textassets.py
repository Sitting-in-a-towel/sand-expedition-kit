"""List all TextAssets in data.unity3d; print MedicalCompartment content head."""
import UnityPy

env = UnityPy.load('gamefiles/Sand_Data/data.unity3d')
names = []
for o in env.objects:
    if o.type.name != 'TextAsset':
        continue
    d = o.read()
    txt = d.m_Script if isinstance(d.m_Script, str) else d.m_Script.decode('utf-8', 'replace')
    names.append((d.m_Name, len(txt)))
    if d.m_Name == 'MedicalCompartment':
        print('--- MedicalCompartment head ---')
        print(txt[:1500])
        print('--- end ---')
for n, l in sorted(names):
    print(f'{l:>9}  {n}')
