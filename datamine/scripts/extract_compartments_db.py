"""Extract the CompartmentsDatabase.json TextAsset from walkereditor bundle."""
import UnityPy, io, sys

env = UnityPy.load('gamefiles/Sand_Data/StreamingAssets/aa/StandaloneWindows64/walkereditor_assets_all.bundle')
for o in env.objects:
    if o.type.name != 'TextAsset':
        continue
    d = o.read()
    print('TextAsset:', d.m_Name)
    if 'ompartment' in d.m_Name:
        raw = d.m_Script if isinstance(d.m_Script, bytes) else d.m_Script.encode('utf-8', 'surrogateescape')
        open('extracted/json/compartments_database.json', 'wb').write(raw)
        print('  -> wrote extracted/json/compartments_database.json,', len(raw), 'bytes')
