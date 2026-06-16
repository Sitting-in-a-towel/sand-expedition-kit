"""Mesh pipeline v2 — LOD0/1 exports with real normals + material colours.
Per part: ../site/public/meshes2/<id>.bin
  layout: [t*9 f32 positions][t*9 i8 normals(/127)][t*3 u8 colors(per-tri RGB)]
Index:    ../site/src/data/mesh_index_v2.json  {id:{t,b:[minXYZ,maxXYZ],l:lod}, _cell}
Fixes the round-1 problems: no decimation (no holes), authored LODs only
(LOD0 small parts, LOD1/2 for heavy ones via 8k-tri budget), real colours.
"""
import UnityPy, json, os, re, sys
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from odin_parser import decode

BASE = 'gamefiles/Sand_Data/StreamingAssets/aa/StandaloneWindows64/'
OUT = '../site/public/meshes2'
os.makedirs(OUT, exist_ok=True)

parts = json.load(open('../site/src/data/parts_v2.json', encoding='utf-8'))['parts']
pinfo = {p['id']: p for p in parts}

# ---- 1. part -> view prefab name (EPB ViewDataComponent) ----
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
# EPBs without an explicit ViewDataComponent resolve by convention: walker_<id>_view
for pid in pinfo:
    if pid not in view_of:
        view_of[pid] = f'walker_{pid}_view'
print('views resolved:', len(view_of), '/', len(pinfo))

# ---- 2. walker bundle scene graph ----
env_w = UnityPy.load(BASE + 'walker_assets_all.bundle')
objs = {o.path_id: o for o in env_w.objects}
go_name, go_active, tf_data, filters, renderers = {}, {}, {}, {}, {}
for o in env_w.objects:
    t = o.type.name
    if t == 'GameObject':
        try:
            d = o.read()
            go_name[o.path_id] = d.m_Name
            go_active[o.path_id] = bool(getattr(d, 'm_IsActive', True))
            for c in (d.m_Component if hasattr(d, 'm_Component') else d.m_Components):
                ptr = c['component'] if isinstance(c, dict) else c.component
                pid2 = ptr['m_PathID'] if isinstance(ptr, dict) else ptr.path_id
                co = objs.get(pid2)
                if not co:
                    continue
                if co.type.name == 'MeshFilter':
                    filters[o.path_id] = co.read_typetree().get('m_Mesh', {}).get('m_PathID', 0)
                elif co.type.name == 'MeshRenderer':
                    renderers[o.path_id] = [m.get('m_PathID', 0) for m in co.read_typetree().get('m_Materials', [])]
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

roots = {}
for pid2, d in tf_data.items():
    if not d.get('m_Father', {}).get('m_PathID', 0):
        nm = go_name.get(d.get('m_GameObject', {}).get('m_PathID'))
        if nm:
            roots.setdefault(nm, pid2)

# ---- material colour cache ----
mat_color_cache = {}
def mat_color(mid):
    if mid in mat_color_cache:
        return mat_color_cache[mid]
    col = (180, 180, 180)
    mo = objs.get(mid)
    if mo and mo.type.name == 'Material':
        try:
            mt = mo.read_typetree()
            entries = mt.get('m_SavedProperties', {}).get('m_Colors', [])
            cols = {}
            for c in entries:
                if isinstance(c, dict):
                    k, v = c.get('first'), c.get('second')
                elif isinstance(c, (list, tuple)) and len(c) == 2:
                    k, v = c
                else:
                    continue
                cols[k] = v
            v = cols.get('_BaseColor') or cols.get('_Color')
            if v:
                col = (int(min(v['r'], 1) * 255), int(min(v['g'], 1) * 255), int(min(v['b'], 1) * 255))
        except Exception:
            pass
    mat_color_cache[mid] = col
    return col

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

# ---- OBJ parse with submesh groups ----
mesh_cache = {}
def mesh_arrays(mid):
    """-> (verts Nx3, normals Nx3, faces [(submesh_idx, i0,i1,i2)...]) or None"""
    if mid in mesh_cache:
        return mesh_cache[mid]
    o = objs.get(mid)
    out = None
    if o and o.type.name == 'Mesh':
        try:
            vs, vns, faces = [], [], []
            sub = -1
            for line in o.read().export().splitlines():
                if line.startswith('g '):
                    m = re.search(r'_(\d+)$', line.strip())
                    sub = int(m.group(1)) if m else -1
                elif line.startswith('v '):
                    _, x, y, z = line.split()[:4]
                    vs.append((float(x), float(y), float(z)))
                elif line.startswith('vn '):
                    _, x, y, z = line.split()[:4]
                    vns.append((float(x), float(y), float(z)))
                elif line.startswith('f '):
                    toks = line.split()[1:]
                    idx = [int(p.split('/')[0]) - 1 for p in toks]
                    for k in range(1, len(idx) - 1):  # fan-triangulate just in case
                        faces.append((max(sub, 0), idx[0], idx[k], idx[k + 1]))
            if vs and faces:
                out = (np.array(vs, dtype=np.float64),
                       np.array(vns, dtype=np.float64) if len(vns) == len(vs) else None,
                       faces)
        except Exception:
            out = None
    mesh_cache[mid] = out
    return out

def collect(tfp, M, lods):
    """lods: key -> {lodNum: (mesh_pid, go_pid, world_matrix)}"""
    d = tf_data.get(tfp)
    if d is None:
        return
    M2 = M @ trs(d)
    g = d.get('m_GameObject', {}).get('m_PathID')
    nm = go_name.get(g, '')
    if not go_active.get(g, True) or 'Damaged' in nm:
        return  # disabled subtree (damage states, debug helpers) — not the pristine part
    mp = filters.get(g)
    if mp:
        m = re.search(r'_LOD(\d)', nm)
        key = re.sub(r'_LOD\d', '', nm)
        lod = int(m.group(1)) if m else -1
        lods.setdefault(key, {})[lod] = (mp, g, M2.copy())
    for ch in children_of.get(tfp, []):
        collect(ch, M2, lods)

def pick_lod(group, level):
    """level 0: LOD0/unLODed. level 1: prefer LOD1. level 2: prefer LOD2.
    Never decimate (round-1 holes) — always a complete authored LOD."""
    prefs = {0: (0, -1, 1, 2, 3), 1: (1, 0, -1, 2, 3), 2: (2, 1, 0, -1, 3)}[level]
    for want in prefs:
        if want in group:
            return group[want]
    return group[min(group)]

def tri_count(group, level):
    mp, g, M = pick_lod(group, level)
    arr = mesh_arrays(mp)
    return len(arr[2]) if arr else 0

# Runtime-mounted entities the view prefab does NOT contain (verified: reactor
# cores are separate reactorSlot entities) — composite them in for visual truth.
COMPOSITES = {
    'compReactor_Round_Open_2x1': ['walker_reactorOuter'],
    'compReactor_Long_Open_1x3': ['walker_reactorOuterLong'],
}

index = {}
cell_samples = []
total_bytes = 0
heavy = []
for pid, view in sorted(view_of.items()):
    root = roots.get(view)
    if not root:
        continue
    lods = {}
    collect(root, np.eye(4), lods)
    for extra in COMPOSITES.get(pid, []):
        er = roots.get(extra)
        if er:
            collect(er, np.eye(4), lods)
    BUDGET = 8000
    level = 0
    while level < 2 and sum(tri_count(g, level) for g in lods.values()) > BUDGET:
        level += 1
    pos_chunks, nrm_chunks, col_chunks = [], [], []
    for key, group in lods.items():
        mp, g, M = pick_lod(group, level)
        arr = mesh_arrays(mp)
        if not arr:
            continue
        vs, vns, faces = arr
        mats = renderers.get(g, [])
        vw = (np.c_[vs, np.ones(len(vs))] @ M.T)[:, :3]
        R = M[:3, :3]
        if vns is not None:
            nw = vns @ np.linalg.inv(R).T if abs(np.linalg.det(R)) > 1e-9 else vns
            nl = np.linalg.norm(nw, axis=1, keepdims=True)
            nw = nw / np.maximum(nl, 1e-9)
        f_arr = np.array([(f[1], f[2], f[3]) for f in faces])
        sub_arr = np.array([f[0] for f in faces])
        tri_pos = vw[f_arr]                      # (T,3,3)
        if vns is not None:
            tri_nrm = nw[f_arr]
        else:
            e1 = tri_pos[:, 1] - tri_pos[:, 0]
            e2 = tri_pos[:, 2] - tri_pos[:, 0]
            fn = np.cross(e1, e2)
            fn = fn / np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-9)
            tri_nrm = np.repeat(fn[:, None, :], 3, axis=1)
        cols = np.zeros((len(faces), 3), dtype=np.uint8)
        for si in np.unique(sub_arr):
            mid = mats[min(si, len(mats) - 1)] if mats else 0
            cols[sub_arr == si] = mat_color(mid)
        pos_chunks.append(tri_pos)
        nrm_chunks.append(tri_nrm)
        col_chunks.append(cols)
    if not pos_chunks:
        continue
    tris = np.concatenate(pos_chunks)
    nrms = np.concatenate(nrm_chunks)
    cols = np.concatenate(col_chunks)
    # Unity -> three.js: negate Z, flip winding
    tris[:, :, 2] *= -1
    nrms[:, :, 2] *= -1
    tris = tris[:, ::-1, :]
    nrms = nrms[:, ::-1, :]
    t = len(tris)
    nrm_q = np.clip(np.round(nrms * 127), -127, 127).astype(np.int8)
    buf = (tris.astype(np.float32).tobytes() +
           nrm_q.tobytes() +
           cols.tobytes())
    open(f'{OUT}/{pid}.bin', 'wb').write(buf)
    total_bytes += len(buf)
    if t > 20000:
        heavy.append((pid, t))
    b = tris.reshape(-1, 3)
    mn, mx = b.min(0), b.max(0)
    index[pid] = {'t': int(t), 'b': [round(float(v), 3) for v in (*mn, *mx)], 'l': level}
    p = pinfo[pid]
    bx = p['bounds'][0]
    if p['category'] in ('Deck', 'Corridor', 'Cargo', 'Crew') and p['bounds'][1] == 1:
        cell_samples.append((mx[0] - mn[0]) / bx)

cell = float(np.median(cell_samples)) if cell_samples else 3.0
index['_cell'] = round(cell, 4)
json.dump(index, open('../site/src/data/mesh_index_v2.json', 'w'), separators=(',', ':'))
print('meshes exported:', len(index) - 1, '| total MB:', round(total_bytes / 1e6, 1), '| cell (m):', index['_cell'])
print('heavy parts (>20k tris):', heavy)
