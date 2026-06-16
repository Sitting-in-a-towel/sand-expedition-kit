# Extract the research-node catalog (ProgressionTreeDescriptions TextAsset)
# from walkershared_assets_all.bundle -> extracted/json/progression_tree_descriptions.json
import UnityPy

BUNDLE = 'gamefiles/Sand_Data/StreamingAssets/aa/StandaloneWindows64/walkershared_assets_all.bundle'
OUT = 'extracted/json/progression_tree_descriptions.json'

env = UnityPy.load(BUNDLE)
for obj in env.objects:
    if obj.type.name == 'TextAsset':
        d = obj.read()
        if d.m_Name == 'ProgressionTreeDescriptions':
            raw = bytes(d.m_Script) if isinstance(d.m_Script, (bytes, bytearray)) else d.m_Script.encode('utf-8', 'surrogateescape')
            open(OUT, 'wb').write(raw)
            print('saved', OUT, len(raw), 'bytes')
            break
else:
    print('NOT FOUND — bundle layout may have changed in this game build')
