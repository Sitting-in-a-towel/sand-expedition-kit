"""Inspect UnityPy Mesh parsed fields for the reactor interior LOD0."""
import UnityPy

BASE = 'gamefiles/Sand_Data/StreamingAssets/aa/StandaloneWindows64/'
env = UnityPy.load(BASE + 'walker_assets_all.bundle')
for o in env.objects:
    if o.type.name != 'Mesh':
        continue
    m = o.read()
    if m.m_Name != 'walker_reactorCompartment_int_LOD0':
        continue
    print('attrs:', [a for a in dir(m) if a.startswith('m_')])
    print('vtx count:', m.m_VertexCount if hasattr(m, 'm_VertexCount') else '?')
    for attr in ('m_Vertices', 'm_Normals', 'm_Colors', 'm_Indices', 'm_IndexBuffer'):
        v = getattr(m, attr, None)
        if v is None:
            print(attr, ': None')
        else:
            try:
                print(attr, ': len', len(v), 'head', list(v[:6]))
            except Exception as e:
                print(attr, ':', type(v), e)
    subs = m.m_SubMeshes
    print('submeshes:', len(subs))
    for s in subs:
        d = s.__dict__ if hasattr(s, '__dict__') else s
        print('  ', {k: v for k, v in (d.items() if isinstance(d, dict) else []) if not k.startswith('_')})
    break
