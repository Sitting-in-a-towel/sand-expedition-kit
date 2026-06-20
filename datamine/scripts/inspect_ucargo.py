"""Inspect what the mesh exporter's collect() keeps vs skips for the U-cargo,
to find the dropped second-bay frame."""
import UnityPy, glob
BASE = 'gamefiles/Sand_Data/StreamingAssets/aa/StandaloneWindows64/'
dup = glob.glob(BASE + 'duplicateassetisolation_assets_all_*.bundle')[0]
print('loading...', flush=True)
env = UnityPy.load(BASE + 'walker_assets_all.bundle', dup)
objs = {}
for o in env.objects:
    objs[(o.assets_file, o.path_id)] = o

def deref(owner, ptr):
    pid = ptr.get('m_PathID', 0) if isinstance(ptr, dict) else getattr(ptr, 'm_PathID', 0)
    if not pid:
        return None
    o = objs.get((owner.assets_file, pid))
    if o:
        return o
    for (af, p), oo in objs.items():
        if p == pid:
            return oo
    return None

go_name, go_active, tf_data, filters = {}, {}, {}, {}
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
                if co and co.type.name == 'MeshFilter':
                    mf = co.read_typetree()
                    filters[(o.assets_file, o.path_id)] = mf.get('m_Mesh', {})
        except Exception:
            pass
    elif t == 'Transform':
        try:
            tf_data[(o.assets_file, o.path_id)] = (o, o.read_typetree())
        except Exception:
            pass

children_of, roots = {}, {}
for k, (o, d) in tf_data.items():
    f = d.get('m_Father', {})
    if f.get('m_PathID', 0):
        fco = deref(o, f)
        if fco:
            children_of.setdefault((fco.assets_file, fco.path_id), []).append(k)
    else:
        gco = deref(o, d.get('m_GameObject', {}))
        if gco:
            nm = go_name.get((gco.assets_file, gco.path_id))
            if nm:
                roots.setdefault(nm, k)

cands = [nm for nm in roots if 'LargeU' in nm]
print('roots containing LargeU:', cands, flush=True)
for view in cands:
    root = roots[view]
    print(f'\n=== TREE for {view} ===')
    def walk(tfk, depth):
        item = tf_data.get(tfk)
        if not item:
            return
        o, d = item
        gco = deref(o, d.get('m_GameObject', {}))
        gk = (gco.assets_file, gco.path_id) if gco else None
        nm = go_name.get(gk, '') if gk else '?'
        act = go_active.get(gk, True) if gk else True
        hasmesh = bool(gk in filters and filters[gk].get('m_PathID'))
        skip = (not act) or ('Damaged' in nm)
        tag = ' <<SKIP' + ('(inactive)' if not act else '(Damaged)') if skip else (' [MESH]' if hasmesh else '')
        print('  ' * depth + f'{nm}{tag}')
        if skip:
            return
        for ch in children_of.get(tfk, []):
            walk(ch, depth + 1)
    walk(root, 0)
