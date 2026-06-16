"""Probe mesh+material structure for one part's view prefab in the walker bundle.
Usage: python scripts/probe_materials.py <view_prefab_name>
Find the view name first via the EPB (ViewDataComponent), or pass it directly.
"""
import UnityPy, sys, json

BASE = 'gamefiles/Sand_Data/StreamingAssets/aa/StandaloneWindows64/'
TARGET = sys.argv[1] if len(sys.argv) > 1 else 'walker_compartmentReactorRound'

env = UnityPy.load(BASE + 'walker_assets_all.bundle')
objs = {o.path_id: o for o in env.objects}

go_name, tf_data, comps_of = {}, {}, {}
for o in env.objects:
    if o.type.name == 'GameObject':
        try:
            d = o.read()
            go_name[o.path_id] = d.m_Name
            comps_of[o.path_id] = [
                (c['component'] if isinstance(c, dict) else c.component) for c in
                (d.m_Component if hasattr(d, 'm_Component') else d.m_Components)
            ]
        except Exception:
            pass
    elif o.type.name == 'Transform':
        try:
            tf_data[o.path_id] = o.read_typetree()
        except Exception:
            pass

children_of = {}
for pid, d in tf_data.items():
    f = d.get('m_Father', {}).get('m_PathID', 0)
    if f:
        children_of.setdefault(f, []).append(pid)

roots = {}
for pid, d in tf_data.items():
    if not d.get('m_Father', {}).get('m_PathID', 0):
        nm = go_name.get(d.get('m_GameObject', {}).get('m_PathID'))
        if nm:
            roots.setdefault(nm, pid)

# fuzzy find target root
cands = [n for n in roots if TARGET.lower() in n.lower()]
print('matching roots:', cands[:10])
if not cands:
    print('available walker_comp* roots sample:', [n for n in roots if 'eactor' in n][:20])
    sys.exit(0)
root = roots[cands[0]]

def pid_of(ptr):
    return ptr['m_PathID'] if isinstance(ptr, dict) else ptr.path_id

def walk(tfp, depth):
    d = tf_data.get(tfp)
    if d is None:
        return
    g = d.get('m_GameObject', {}).get('m_PathID')
    nm = go_name.get(g, '?')
    info = []
    for cp in comps_of.get(g, []):
        co = objs.get(pid_of(cp))
        if not co:
            continue
        if co.type.name == 'MeshFilter':
            mf = co.read_typetree()
            mid = mf.get('m_Mesh', {}).get('m_PathID', 0)
            mo = objs.get(mid)
            if mo:
                md = mo.read_typetree()
                sub = md.get('m_SubMeshes', [])
                info.append(f"Mesh path_id={mid} name={md.get('m_Name')} submeshes={len(sub)} vtx={md.get('m_VertexData',{}).get('m_VertexCount')}")
            else:
                info.append(f'Mesh EXTERNAL path_id={mid}')
        elif co.type.name == 'MeshRenderer':
            mr = co.read_typetree()
            mats = mr.get('m_Materials', [])
            mnames = []
            for mp in mats:
                mo = objs.get(mp.get('m_PathID', 0))
                if mo and mo.type.name == 'Material':
                    mt = mo.read_typetree()
                    cols = {c['first'] if isinstance(c, dict) and 'first' in c else (c[0] if isinstance(c, (list, tuple)) else '?'):
                            (c['second'] if isinstance(c, dict) and 'second' in c else (c[1] if isinstance(c, (list, tuple)) else '?'))
                            for c in mt.get('m_SavedProperties', {}).get('m_Colors', [])}
                    texs = [t[0] if isinstance(t, (list, tuple)) else t.get('first') for t in mt.get('m_SavedProperties', {}).get('m_TexEnvs', [])]
                    mnames.append({'name': mt.get('m_Name'), 'shaderKW': mt.get('m_ShaderKeywords', '')[:60],
                                   'colors': {k: v for k, v in cols.items() if k in ('_Color', '_BaseColor', '_MainColor', '_Tint')},
                                   'ntex': len(texs)})
                else:
                    mnames.append({'name': f'EXTERNAL {mp.get("m_PathID")}'})
            info.append('Mats: ' + json.dumps(mnames))
    print('  ' * depth + nm + ('  | ' + ' ; '.join(info) if info else ''))
    for ch in children_of.get(tfp, []):
        walk(ch, depth + 1)

walk(root, 0)
