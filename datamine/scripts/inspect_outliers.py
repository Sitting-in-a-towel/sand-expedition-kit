"""Why didn't the medical bay bake (still white)? And is the round steering missing geo?
Loads the walker bundle once and inspects both."""
import UnityPy, glob
BASE = 'gamefiles/Sand_Data/StreamingAssets/aa/StandaloneWindows64/'
dup = glob.glob(BASE + 'duplicateassetisolation_assets_all_*.bundle')[0]
print('loading...', flush=True)
env = UnityPy.load(BASE + 'walker_assets_all.bundle', dup)

# dump every Material whose name hints at medical, show its shader + texture props
print('\n=== MEDICAL materials: shader + texture slots present ===')
for o in env.objects:
    if o.type.name != 'Material':
        continue
    t = o.read_typetree()
    nm = (t.get('m_Name') or '')
    if 'medic' not in nm.lower() and 'medbay' not in nm.lower() and 'hospital' not in nm.lower():
        continue
    sh = t.get('m_Shader', {})
    texs = []
    for te in t.get('m_SavedProperties', {}).get('m_TexEnvs', []):
        if isinstance(te, dict):
            n = te.get('first'); n = n.get('name') if isinstance(n, dict) else n
            has = bool((te.get('second') or {}).get('m_Texture', {}).get('m_PathID'))
            if has:
                texs.append(n)
    print(f'  {nm}: tex_props_with_texture={texs}')
