"""Scan ALL bundles for TextAssets, looking for CompartmentsDatabase."""
import UnityPy, os, glob

BASE = 'gamefiles/Sand_Data/StreamingAssets/aa/StandaloneWindows64/'
for path in sorted(glob.glob(BASE + '*.bundle')):
    b = os.path.basename(path)
    try:
        env = UnityPy.load(path)
    except Exception as e:
        print(b, 'LOAD FAIL', e)
        continue
    for o in env.objects:
        if o.type.name != 'TextAsset':
            continue
        try:
            d = o.read()
        except Exception:
            continue
        print(f'{b}: TextAsset "{d.m_Name}"')
        if 'ompartment' in d.m_Name:
            raw = d.m_Script if isinstance(d.m_Script, bytes) else d.m_Script.encode('utf-8', 'surrogateescape')
            open('extracted/json/compartments_database.json', 'wb').write(raw)
            print('  -> WROTE extracted/json/compartments_database.json,', len(raw), 'bytes')
