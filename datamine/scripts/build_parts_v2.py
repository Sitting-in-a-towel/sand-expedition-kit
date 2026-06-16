"""Build parts_v2.json — the TRUTH-based part roster for the identical builder.
Source: CompartmentsDatabase.json (the exact data the in-game editor loads).
Output: ../site/src/data/parts_v2.json

Per part: true cells (position, per-direction sockets w/ type+editable+snap),
volumeOccupied, requireSupport, pivot, rotation rules, groups, mirror pairing.
DB-level: group part limits, socket state -> spawned entity (door/ladder/hatch).
"""
import json, re
from collections import Counter

DIRS = ['Left', 'Right', 'Up', 'Down', 'Forward', 'Back']

db = json.load(open('extracted/json/compartments_database.json', encoding='utf-8-sig'))

# keep display names/categories from the existing roster where ids overlap
old = {}
try:
    old = {p['id']: p for p in json.load(open('../site/src/data/parts.json', encoding='utf-8'))}
except FileNotFoundError:
    pass

# authoritative compartment names+descriptions from the I2 Localization table
# (build_localization.py). Keyed by full epb id `walker_<pid>`.
LOC_COMP = {}
try:
    LOC_COMP = json.load(open('../site/src/data/localization.json', encoding='utf-8'))['compartments']
except FileNotFoundError:
    print('WARNING: localization.json missing — run build_localization.py first; using prettified part names')


def pid_of(entity_id):
    return re.sub(r'^walker_', '', re.sub(r'_epb$', '', entity_id))


def prettify(ident):
    s = re.sub(r'^comp', '', ident)
    s = s.replace('_', ' ')
    s = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', s)
    return ' '.join(w if w.isupper() else w.capitalize() for w in s.split())


parts = []
for c in db['compartments']:
    pid = pid_of(c['entityId'])
    cells = []
    for cl in c['cells']:
        p = cl['position']
        sockets = {}
        for d in DIRS:
            socks = cl['sockets'].get(d)
            if not socks:
                continue
            sockets[d] = [
                {
                    't': st,
                    'e': bool(si.get('editable')),
                    'sn': bool(si.get('snap')),
                    **({'bl': si['blockedConnections']} if si.get('blockedConnections') else {}),
                }
                for st, si in socks.items()
            ]
        cell = {'p': [p['x'], p['y'], p['z']], 's': sockets}
        if not cl['volumeOccupied']:
            cell['noVol'] = True
        if cl['requireSupport']:
            cell['sup'] = True
        if cl['ignoreOutOfRange']:
            cell['ignOOR'] = True
        cells.append(cell)

    xs = [cl['p'][0] for cl in cells]
    ys = [cl['p'][1] for cl in cells]
    zs = [cl['p'][2] for cl in cells]

    o = old.get(pid, {})
    m = re.match(r'comp(?P<cat>[A-Za-z]+?)_', pid)
    category = (m.group('cat') if m else None) or o.get('category') or 'Other'

    loc = LOC_COMP.get(f'walker_{pid}', {})
    entry = {
        'id': pid,
        'name': loc.get('name') or o.get('name') or prettify(pid),
        'desc': loc.get('desc'),
        'category': category,
        'groups': c['group'],
        'enabled': c['enabled'],
        'rotationEnabled': c['rotationEnabled'],
        'startRotation': c.get('startRotation', 0),
        'pivot': [c['pivot']['x'], c['pivot']['y'], c['pivot']['z']],
        'pivotOffset': [c['pivotOffset']['x'], c['pivotOffset']['y'], c['pivotOffset']['z']],
        'bounds': [max(xs) - min(xs) + 1, max(ys) - min(ys) + 1, max(zs) - min(zs) + 1],
        'cells': cells,
    }
    if c.get('mirrorEntityId'):
        entry['mirror'] = pid_of(c['mirrorEntityId'])
    if o.get('label'):
        entry['label'] = o['label']
    if o.get('legs'):
        entry['legs'] = o['legs']
    parts.append(entry)

out = {
    'groupLimits': {g: gi['partsLimit'] for g, gi in db['groupsInfo'].items()},
    # slot type -> connection state -> entity spawned (e.g. HATCH+DOOR = ladder hatch)
    'socketStates': {
        st: {state: cfg.get('entityId', '') for state, cfg in states.items()}
        for st, states in db['socketInfo'].items()
    },
    'parts': sorted(parts, key=lambda p: (p['category'], p['id'])),
}

json.dump(out, open('../site/src/data/parts_v2.json', 'w', encoding='utf-8'),
          separators=(',', ':'), ensure_ascii=False)

print('parts_v2.json written:', len(parts), 'parts')
print('categories:', Counter(p['category'] for p in parts).most_common())
print('enabled:', sum(1 for p in parts if p['enabled']))
print('multi-level:', sum(1 for p in parts if p['bounds'][1] > 1))
print('mirrors:', sum(1 for p in parts if 'mirror' in p))
