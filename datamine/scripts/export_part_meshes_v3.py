"""Mesh pipeline v3 — adds real UVs + albedo TEXTURES on top of v2.

Per part: ../site/public/meshes3/<id>.bin
  layout (all per-triangle, non-indexed, T triangles):
    [T*9 f32 positions][T*9 i8 normals(/127)][T*6 f32 uvs][T*1 u8 texSlot]
  texSlot indexes into this part's local texture list (mesh_index_v3[id].tex).
Shared albedo textures: ../site/public/tex3/<n>.png  (downscaled to <=512px)
Index: ../site/src/data/mesh_index_v3.json
  { id: {t, b:[min,max], l:lod, tex:["tex3/3.png", ...], col:[[r,g,b]...]} , _cell }
  (`col` = fallback flat colour per slot, used if a texture fails to load)

Only 34 unique albedo textures cover all 126 parts (a shared trim/atlas set), so
this stays small (~few MB). Builds alongside meshes2 (vertex-colour) — BuilderScene
switches to v3 once verified.
"""
import UnityPy, json, os, re, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from odin_parser import decode

BASE = 'gamefiles/Sand_Data/StreamingAssets/aa/StandaloneWindows64/'
OUT = '../site/public/meshes3'
TEXOUT = '../site/public/tex3'
os.makedirs(OUT, exist_ok=True)
os.makedirs(TEXOUT, exist_ok=True)
MAXTEX = 512

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
for pid in pinfo:
    view_of.setdefault(pid, f'walker_{pid}_view')
print('views resolved:', len(view_of), '/', len(pinfo), flush=True)

# ---- 2. combined env: walker (prefabs+meshes+materials) + shared-asset bundle (textures) ----
env = UnityPy.load(BASE + 'walker_assets_all.bundle',
                   BASE + 'duplicateassetisolation_assets_all_fb84156cf155cf0afd68566bd5e732f9.bundle')
objs = {}
for o in env.objects:
    objs[(o.assets_file, o.path_id)] = o

go_name, go_active, tf_data, filters, renderers = {}, {}, {}, {}, {}
def deref(owner, ptr):
    """resolve a PPtr dict {m_FileID, m_PathID} against the combined env."""
    pid = ptr.get('m_PathID', 0) if isinstance(ptr, dict) else getattr(ptr, 'm_PathID', 0)
    if not pid:
        return None
    try:
        if hasattr(ptr, 'deref'):
            return ptr.deref()
    except Exception:
        pass
    # fallback: same assets_file, then any
    o = objs.get((owner.assets_file, pid))
    if o:
        return o
    for (af, p), oo in objs.items():
        if p == pid:
            return oo
    return None

for o in env.objects:
    t = o.type.name
    if t == 'GameObject':
        try:
            d = o.read()
            go_name[(o.assets_file, o.path_id)] = d.m_Name
            go_active[(o.assets_file, o.path_id)] = bool(getattr(d, 'm_IsActive', True))
            for c in (d.m_Component if hasattr(d, 'm_Component') else d.m_Components):
                ptr = c['component'] if isinstance(c, dict) else c.component
                co = deref(o, ptr if isinstance(ptr, dict) else {'m_PathID': ptr.path_id})
                if not co:
                    continue
                if co.type.name == 'MeshFilter':
                    mf = co.read_typetree()
                    filters[(o.assets_file, o.path_id)] = mf.get('m_Mesh', {})
                elif co.type.name == 'MeshRenderer':
                    rt = co.read_typetree()
                    renderers[(o.assets_file, o.path_id)] = rt.get('m_Materials', [])
        except Exception:
            pass
    elif t == 'Transform':
        try:
            tf_data[(o.assets_file, o.path_id)] = (o, o.read_typetree())
        except Exception:
            pass

# transform graph keyed by (assets_file, path_id)
children_of = {}
roots = {}
for k, (o, d) in tf_data.items():
    f = d.get('m_Father', {})
    fpid = f.get('m_PathID', 0)
    if fpid:
        fco = deref(o, f)
        if fco:
            children_of.setdefault((fco.assets_file, fco.path_id), []).append(k)
    else:
        gp = d.get('m_GameObject', {})
        gco = deref(o, gp)
        if gco:
            nm = go_name.get((gco.assets_file, gco.path_id))
            if nm:
                roots.setdefault(nm, k)

# ---- material -> (albedo texture key, flat colour) ----
mat_cache = {}
tex_registry = {}   # texture obj id -> {slot:int, file:str}
tex_export = {}     # slot -> PIL save path (dedup by content)

def resolve_texture(texco):
    """register a texture object, export its PNG once, return slot index."""
    tid = (texco.assets_file, texco.path_id)
    if tid in tex_registry:
        return tex_registry[tid]['slot']
    slot = len(tex_registry)
    fn = f'{slot}.png'
    try:
        img = texco.read().image
        if img is None:
            return None
        w, h = img.size
        sc = MAXTEX / max(w, h)
        if sc < 1:
            img = img.resize((max(1, int(w * sc)), max(1, int(h * sc))), Image.LANCZOS)
        img.convert('RGB').save(f'{TEXOUT}/{fn}')
    except Exception:
        return None
    tex_registry[tid] = {'slot': slot, 'file': f'tex3/{fn}'}
    return slot

def mat_info(matco):
    """-> (texSlot or None, (r,g,b) flat colour)"""
    key = (matco.assets_file, matco.path_id)
    if key in mat_cache:
        return mat_cache[key]
    slot, col = None, (170, 170, 170)
    try:
        mt = matco.read_typetree()
        props = mt.get('m_SavedProperties', {})
        slots = {}
        for te in props.get('m_TexEnvs', []):
            if isinstance(te, dict):
                slots[te.get('first')] = te.get('second')
            elif isinstance(te, (list, tuple)) and len(te) == 2:
                slots[te[0]] = te[1]
        for s in ('_BaseMap', '_MainTex', '_BaseColorMap'):
            te = slots.get(s)
            if te and te.get('m_Texture', {}).get('m_PathID'):
                texco = deref(matco, te['m_Texture'])
                if texco and texco.type.name == 'Texture2D':
                    slot = resolve_texture(texco)
                    break
        cols = {}
        for c in props.get('m_Colors', []):
            if isinstance(c, dict):
                cols[c.get('first')] = c.get('second')
            elif isinstance(c, (list, tuple)) and len(c) == 2:
                cols[c[0]] = c[1]
        v = cols.get('_BaseColor') or cols.get('_Color')
        if v:
            col = (int(min(v['r'], 1) * 255), int(min(v['g'], 1) * 255), int(min(v['b'], 1) * 255))
    except Exception:
        pass
    mat_cache[key] = (slot, col)
    return mat_cache[key]

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

# ---- mesh OBJ parse with submesh groups + UVs ----
mesh_cache = {}
def mesh_arrays(meshco):
    mid = (meshco.assets_file, meshco.path_id)
    if mid in mesh_cache:
        return mesh_cache[mid]
    out = None
    try:
        vs, vts, vns, faces = [], [], [], []
        sub = -1
        for line in meshco.read().export().splitlines():
            if line.startswith('g '):
                m = re.search(r'_(\d+)$', line.strip())
                sub = int(m.group(1)) if m else -1
            elif line.startswith('vt '):
                _, u, v = line.split()[:3]
                vts.append((float(u), float(v)))
            elif line.startswith('v '):
                _, x, y, z = line.split()[:4]
                vs.append((float(x), float(y), float(z)))
            elif line.startswith('vn '):
                _, x, y, z = line.split()[:4]
                vns.append((float(x), float(y), float(z)))
            elif line.startswith('f '):
                toks = line.split()[1:]
                vi, ti = [], []
                for p in toks:
                    parts_ = p.split('/')
                    vi.append(int(parts_[0]) - 1)
                    ti.append(int(parts_[1]) - 1 if len(parts_) > 1 and parts_[1] else -1)
                for k in range(1, len(vi) - 1):
                    faces.append((max(sub, 0), vi[0], vi[k], vi[k + 1], ti[0], ti[k], ti[k + 1]))
        if vs and faces:
            out = (np.array(vs, dtype=np.float64),
                   np.array(vns, dtype=np.float64) if len(vns) == len(vs) else None,
                   np.array(vts, dtype=np.float64) if vts else None,
                   faces)
    except Exception:
        out = None
    mesh_cache[mid] = out
    return out

def collect(tfk, M, lods):
    item = tf_data.get(tfk)
    if item is None:
        return
    o, d = item
    M2 = M @ trs(d)
    gco = deref(o, d.get('m_GameObject', {}))
    gk = (gco.assets_file, gco.path_id) if gco else None
    nm = go_name.get(gk, '') if gk else ''
    if gk and (not go_active.get(gk, True) or 'Damaged' in nm):
        return
    mf = filters.get(gk)
    if mf and mf.get('m_PathID'):
        m = re.search(r'_LOD(\d)', nm)
        key = re.sub(r'_LOD\d', '', nm)
        lod = int(m.group(1)) if m else -1
        lods.setdefault(key, {})[lod] = (mf, gk, M2.copy())
    for ch in children_of.get(tfk, []):
        collect(ch, M2, lods)

def pick_lod(group, level):
    prefs = {0: (0, -1, 1, 2, 3), 1: (1, 0, -1, 2, 3), 2: (2, 1, 0, -1, 3)}[level]
    for want in prefs:
        if want in group:
            return group[want]
    return group[min(group)]

def tri_count(group, level):
    mf, gk, M = pick_lod(group, level)
    mco = deref(tf_data and list(tf_data.values())[0][0], mf)  # owner irrelevant for global lookup
    if not mco:
        return 0
    arr = mesh_arrays(mco)
    return len(arr[3]) if arr else 0

COMPOSITES = {
    'compReactor_Round_Open_2x1': ['walker_reactorOuter'],
    'compReactor_Long_Open_1x3': ['walker_reactorOuterLong'],
}

any_owner = next(iter(tf_data.values()))[0]
index = {}
cell_samples = []
total_bytes = 0
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

    pos_chunks, nrm_chunks, uv_chunks, slot_chunks = [], [], [], []
    part_tex = {}       # global slot -> local index
    part_tex_files = []
    part_tex_cols = []
    for key, group in lods.items():
        mf, gk, M = pick_lod(group, level)
        mco = deref(any_owner, mf)
        if not mco:
            continue
        arr = mesh_arrays(mco)
        if not arr:
            continue
        vs, vns, vts, faces = arr
        mats = renderers.get(gk, [])
        vw = (np.c_[vs, np.ones(len(vs))] @ M.T)[:, :3]
        R = M[:3, :3]
        if vns is not None:
            nw = vns @ np.linalg.inv(R).T if abs(np.linalg.det(R)) > 1e-9 else vns
            nw = nw / np.maximum(np.linalg.norm(nw, axis=1, keepdims=True), 1e-9)
        f_arr = np.array([(f[1], f[2], f[3]) for f in faces])
        t_arr = np.array([(f[4], f[5], f[6]) for f in faces])
        sub_arr = np.array([f[0] for f in faces])
        tri_pos = vw[f_arr]
        if vns is not None:
            tri_nrm = nw[f_arr]
        else:
            e1 = tri_pos[:, 1] - tri_pos[:, 0]
            e2 = tri_pos[:, 2] - tri_pos[:, 0]
            fn = np.cross(e1, e2)
            fn = fn / np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-9)
            tri_nrm = np.repeat(fn[:, None, :], 3, axis=1)
        # uvs per triangle-vertex
        if vts is not None and (t_arr >= 0).all():
            tri_uv = vts[t_arr]
        else:
            tri_uv = np.zeros((len(faces), 3, 2))
        # per-submesh material -> texture slot + colour
        slots = np.zeros(len(faces), dtype=np.uint8)
        for si in np.unique(sub_arr):
            matref = mats[min(si, len(mats) - 1)] if mats else None
            gslot, col = (None, (170, 170, 170))
            if matref and matref.get('m_PathID'):
                matco = deref(any_owner, matref)
                if matco and matco.type.name == 'Material':
                    gslot, col = mat_info(matco)
            if gslot is None:
                local = 255  # no texture -> flat colour fallback
            else:
                if gslot not in part_tex:
                    part_tex[gslot] = len(part_tex_files)
                    reg = next(r for r in tex_registry.values() if r['slot'] == gslot)
                    part_tex_files.append(reg['file'])
                    part_tex_cols.append(list(col))
                local = part_tex[gslot]
            slots[sub_arr == si] = local
        pos_chunks.append(tri_pos)
        nrm_chunks.append(tri_nrm)
        uv_chunks.append(tri_uv)
        slot_chunks.append(slots)
    if not pos_chunks:
        continue
    tris = np.concatenate(pos_chunks)
    nrms = np.concatenate(nrm_chunks)
    uvs = np.concatenate(uv_chunks)
    slots = np.concatenate(slot_chunks)
    tris[:, :, 2] *= -1
    nrms[:, :, 2] *= -1
    tris = tris[:, ::-1, :]
    nrms = nrms[:, ::-1, :]
    uvs = uvs[:, ::-1, :]
    slots_exp = np.repeat(slots, 1)  # one per triangle
    t = len(tris)
    nrm_q = np.clip(np.round(nrms * 127), -127, 127).astype(np.int8)
    buf = (tris.astype(np.float32).tobytes() +
           nrm_q.tobytes() +
           uvs.astype(np.float32).tobytes() +
           slots_exp.astype(np.uint8).tobytes())
    open(f'{OUT}/{pid}.bin', 'wb').write(buf)
    total_bytes += len(buf)
    b = tris.reshape(-1, 3)
    mn, mx = b.min(0), b.max(0)
    index[pid] = {'t': int(t), 'b': [round(float(v), 3) for v in (*mn, *mx)], 'l': level,
                  'tex': part_tex_files, 'col': part_tex_cols}
    p = pinfo[pid]
    bx = p['bounds'][0]
    if p['category'] in ('Deck', 'Corridor', 'Cargo', 'Crew') and p['bounds'][1] == 1:
        cell_samples.append((mx[0] - mn[0]) / bx)

cell = float(np.median(cell_samples)) if cell_samples else 3.0
index['_cell'] = round(cell, 4)
json.dump(index, open('../site/src/data/mesh_index_v3.json', 'w'), separators=(',', ':'))
print('meshes3 exported:', len(index) - 1, '| total MB:', round(total_bytes / 1e6, 1),
      '| textures:', len(tex_registry), '| cell (m):', index['_cell'])
