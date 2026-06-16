"""Check OBJ export content + available mesh helpers."""
import UnityPy
print('UnityPy', UnityPy.__version__)
try:
    from UnityPy.helpers import MeshHelper
    print('MeshHelper:', [x for x in dir(MeshHelper) if not x.startswith('_')])
except ImportError as e:
    print('no MeshHelper:', e)

BASE = 'gamefiles/Sand_Data/StreamingAssets/aa/StandaloneWindows64/'
env = UnityPy.load(BASE + 'walker_assets_all.bundle')
for o in env.objects:
    if o.type.name != 'Mesh':
        continue
    m = o.read()
    if m.m_Name != 'walker_reactorCompartment_int_LOD0':
        continue
    txt = m.export()
    lines = txt.splitlines()
    print('obj lines:', len(lines))
    kinds = {}
    for ln in lines:
        k = ln.split(' ', 1)[0]
        kinds[k] = kinds.get(k, 0) + 1
    print('line kinds:', kinds)
    # show any group/material markers
    for ln in lines:
        if ln.startswith(('g ', 'o ', 'usemtl', 'mtllib')):
            print('MARKER:', ln)
    break
