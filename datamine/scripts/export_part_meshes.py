"""Export per-part low-LOD triangle soups for the site's 3D preview.
Output: ../site/public/meshes/<id>.bin (Float32 xyz*3 per tri, three.js handedness)
        ../site/src/data/mesh_index.json {id:{t:tris, b:[bounds]}, _cell: meters-per-cell}
"""
import UnityPy, json, os, re, sys
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from odin_parser import decode

BASE = 'gamefiles/Sand_Data/StreamingAssets/aa/StandaloneWindows64/'
OUT = '../site/public/meshes'
os.makedirs(OUT, exist_ok=True)
MAX_TRIS = 6000

parts = json.load(open('../site/src/data/parts.json', encoding='utf-8'))
pinfo = {p['id']: p for p in parts}

# part -> view name
env_epb = UnityPy.load(BASE + 'epb_assets_all.bundle')
objs_epb = {o.path_id: o for o in env_epb.objects}
view_of = {}
for obj in env_epb.objects:
    if obj.type.name != 'GameObject':
        continue
    go = obj.read()
    nm = go.m_Name
    if not (nm.startswith('walker_') and nm.endswith('_epb')):
        continue
    pid = nm[7:-4]
    if pid not in pinfo:
        continue
    for c in (go.m_Component if hasattr(go, 'm_Component') else go.m_Components):
        ptr = c['component'] if isinstance(c, dict) else c.component
        o = objs_epb.get(ptr['m_PathID'] if isinstance(ptr, dict) else ptr.path_id)
        if not o or o.type.name != 'MonoBehaviour':
            continue
        t = o.read_typetree()
        sb = t.get('serializationData', {}).get('SerializedBytes')
        if not sb:
            continue
        try:
            doc = decode(sb)
        except Exception:
            continue
        for comp in doc.get('components', {}).get('$items', []):
            if isinstance(comp, dict) and 'ViewDataComponent' in str(comp.get('$type', '')):
                view_of[pid] = comp.get('name')

# walker bundle graph (same as thumbs script)
env_w = UnityPy.load(BASE + 'walker_assets_all.bundle')
objs = {o.path_id: o for o in env_w.objects}
go_name, go_tf, tf_data, filters, mesh_cache = {}, {}, {}, {}, {}
for o in env_w.objects:
    t = o.type.name
    if t == 'GameObject':
        try:
            d = o.read()
            go_name[o.path_id] = d.m_Name
            for c in (d.m_Component if hasattr(d, 'm_Component') else d.m_Components):
                ptr = c['component'] if isinstance(c, dict) else c.component
                pid2 = ptr['m_PathID'] if isinstance(ptr, dict) else ptr.path_id
                co = objs.get(pid2)
                if co and co.type.name == 'Transform':
                    go_tf[o.path_id] = pid2
                elif co and co.type.name == 'MeshFilter':
                    filters[o.path_id] = co.read_typetree().get('m_Mesh', {}).get('m_PathID', 0)
        except Exception:
            pass
    elif t == 'Transform':
        try:
            tf_data[o.path_id] = o.read_typetree()
        except Exception:
            pass

children_of = {}
for pid2, d in tf_data.items():
    f = d.get('m_Father', {}).get('m_PathID', 0)
    if f:
        children_of.setdefault(f, []).append(pid2)

def trs(d):
    p, r, s = d['m_LocalPosition'], d['m_LocalRotation'], d['m_LocalScale']
    qx, qy, qz, qw = r['x'], r['y'], r['z'], r['w']
    R = np.array([
        [1-2*(qy*qy+qz*qz), 2*(qx*qy-qz*qw), 2*(qx*qz+qy*qw)],
        [2*(qx*qy+qz*qw), 1-2*(qx*qx+qz*qz), 2*(qy*qz-qx*qw)],
        [2*(qx*qz-qy*qw), 2*(qy*qz+qx*qw), 1-2*(qx*qx+qy*qy)],
    ])
    M = np.eye(4)
    M[:3, :3] = R @ np.diag([s['x'], s['y'], s['z']])
    M[:3, 3] = [p['x'], p['y'], p['z']]
    return M

def mesh_arrays(mid):
    if mid in mesh_cache:
        return mesh_cache[mid]
    o = objs.get(mid)
    out = None
    if o and o.type.name == 'Mesh':
        try:
            vs, fs = [], []
            for line in o.read().export().splitlines():
                if line.startswith('v '):
                    _, x, y, z = line.split()[:4]
                    vs.append((float(x), float(y), float(z)))
                elif line.startswith('f '):
                    fs.append([int(p.split('/')[0]) - 1 for p in line.split()[1:4]])
            if vs and fs:
                out = (np.array(vs, dtype=np.float32), np.array(fs))
        except Exception:
            pass
    mesh_cache[mid] = out
    return out

roots = {}
for pid2, d in tf_data.items():
    if not d.get('m_Father', {}).get('m_PathID', 0):
        nm = go_name.get(d.get('m_GameObject', {}).get('m_PathID'))
        if nm:
            roots.setdefault(nm, pid2)

def collect(tfp, M, lods):
    d = tf_data.get(tfp)
    if d is None:
        return
    M2 = M @ trs(d)
    g = d.get('m_GameObject', {}).get('m_PathID')
    nm = go_name.get(g, '')
    mp = filters.get(g)
    if mp:
        m = re.search(r'_LOD(\d)', nm)
        key = re.sub(r'_LOD\d', '', nm)
        lod = int(m.group(1)) if m else -1
        if key not in lods or lod > lods[key][0]:
            lods[key] = (lod, mp, M2.copy())
    for ch in children_of.get(tfp, []):
        collect(ch, M2, lods)

index = {}
cells = []
for pid, view in sorted(view_of.items()):
    root = roots.get(view)
    if not root:
        continue
    lods = {}
    collect(root, np.eye(4), lods)
    tris_all = []
    for lod, mp, M in lods.values():
        arr = mesh_arrays(mp)
        if not arr:
            continue
        vs, fs = arr
        if len(fs) > 60000:
            continue
        vw = (np.c_[vs, np.ones(len(vs))] @ M.T)[:, :3]
        tris_all.append(vw[fs])
    if not tris_all:
        continue
    tris = np.concatenate(tris_all)
    if len(tris) > MAX_TRIS:
        tris = tris[:: max(1, len(tris) // MAX_TRIS)][:MAX_TRIS]
    # Unity -> three.js: negate Z, flip winding
    tris = tris.astype(np.float32)
    tris[:, :, 2] *= -1
    tris = tris[:, ::-1, :]
    flat = tris.reshape(-1)
    open(f'{OUT}/{pid}.bin', 'wb').write(flat.tobytes())
    b = tris.reshape(-1, 3)
    mn, mx = b.min(0), b.max(0)
    index[pid] = {'t': int(len(tris)), 'b': [round(float(v), 3) for v in (*mn, *mx)]}
    p = pinfo[pid]
    if p['category'] == 'Chassis':
        cells.append((mx[0] - mn[0]) / p['w'])

cell = float(np.median(cells)) if cells else 3.0
index['_cell'] = round(cell, 4)
json.dump(index, open('../site/src/data/mesh_index.json', 'w'), separators=(',', ':'))
print('meshes exported:', len(index) - 1, '| cell size (m):', index['_cell'])
