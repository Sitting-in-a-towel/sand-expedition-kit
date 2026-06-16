"""Build source-level loot data for the site's containers spreadsheet.
Merges entities the player sees as ONE thing (Ironclad boxes, mob drops, crate tiers)
and computes real per-item % using entity set-weights where available.
Output: site/src/data/loot_sources.json
"""
import json, re
from collections import defaultdict

entity_loot = json.load(open('extracted/json/entity_loot.json', encoding='utf-8'))
voy = json.load(open('extracted/json/loottables_voyage.json', encoding='utf-8'))['_lootTables']['$items']
sto = json.load(open('extracted/json/loottables_storm.json', encoding='utf-8'))['_lootTables']['$items']

tables = {}
for mode, lst in (('voyage', voy), ('storm', sto)):
    for t in lst:
        e = tables.setdefault(t['lootTableId'], {})
        e[mode] = [
            {'item': i['itemBlueprint'], 'min': i['countMin'], 'max': i['countMax']}
            for i in t['items']['$items']
        ]

# ---- source definitions: entity prefix -> source name ----
SOURCES = [
    (r'^game_armyBox_t(\d)_(low|mid|high)Effort$', 'Weapons Crate'),
    (r'^game_foodBox_t(\d)_(low|mid|high)Effort$', 'Food Crate'),
    (r'^game_partsBox_t(\d)_(low|mid|high)Effort$', 'Resource Crate'),
    (r'^game_medicalCabinet_t(\d)_(low|mid|high)Effort$', 'Medical Cabinet'),
    (r'^game_safeMiddle_t(\d)_(low|mid|high)Effort$', 'Safe'),
    (r'^game_shellsBox_t(\d)_(low|mid|high)Effort$', 'Shell Box'),
    (r'^item_ironcladContainer(\d+)mm$', 'Ironclad Loot Box'),
    (r'^game_buriedTreasure$', 'Buried Treasure'),
    (r'^game_aurogenCrystal\d$', 'Aurogen Crystal'),
    (r'^game_navalMine$', 'Naval Mine'),
    (r'^game_militiaBox_(\d+)mm$', 'Militia Box'),
]

sources = {}

def add_sets(source, tier, effort, entries, mandatory):
    src = sources.setdefault(source, {'name': source, 'cells': {}, 'mandatory': []})
    key = f'{tier or 0}|{effort or ""}'
    cell = src['cells'].setdefault(key, {'tier': tier, 'effort': effort, 'sets': []})
    cell['sets'].extend(entries)
    for m in mandatory:
        if m not in src['mandatory']:
            src['mandatory'].append(m)

for ent, data in entity_loot.items():
    for pat, source in SOURCES:
        m = re.match(pat, ent)
        if not m:
            continue
        tier = None
        effort = None
        g = m.groups()
        if len(g) >= 1 and g[0] and g[0].isdigit() and source not in ('Ironclad Loot Box', 'Militia Box'):
            tier = int(g[0])
        if len(g) >= 2 and g[1]:
            effort = g[1]
        entries = [e for e in data['entries'] if e.get('tableId')]
        mand = [e.get('tableId') for e in data['mandatory'] if e.get('tableId')]
        if source == 'Buried Treasure':
            # one entity rolls sets across zone tiers — split by table tier
            byt = defaultdict(list)
            for e in entries:
                mt = re.search(r'_T(\d)_', e['tableId'])
                byt[int(mt.group(1)) if mt else 0].append(e)
            for t2, es in byt.items():
                add_sets(source, t2, None, es, mand)
        else:
            add_sets(source, tier, effort, entries, mand)
        break

# Mob drops: tables exist but no entity weights -> equal weights per sub-group
mob_groups = defaultdict(list)
for tid in tables:
    m = re.match(r'mobLoot_([a-zA-Z]+)_set(\d+)', tid)
    if m:
        mob_groups[m.group(1)].append(tid)
MOB_LABEL = {'ghoulMelee': 'melee mob', 'ghoulRange': 'ranged mob', 'ghoulMeleeShovel': 'melee mob (tool)'}
for grp, tids in mob_groups.items():
    add_sets('Mob Drops', None, MOB_LABEL.get(grp, grp), [{'tableId': t, 'chance': 1} for t in sorted(tids)], [])

# ---- compute cells: per mode, item -> pct + counts ----
def compute(cell, mode):
    total = sum(s.get('chance', 1) or 1 for s in cell['sets'])
    items = {}
    known_sets = 0
    for s in cell['sets']:
        tid = s['tableId']
        ch = (s.get('chance', 1) or 1) / total if total else 0
        content = tables.get(tid, {}).get(mode)
        if content is None:
            continue
        known_sets += 1
        for it in content:
            e = items.setdefault(it['item'], {'pct': 0, 'min': it['min'], 'max': it['max']})
            e['pct'] += ch
            e['min'] = min(e['min'], it['min'])
            e['max'] = max(e['max'], it['max'])
    out = [
        {'item': k, 'pct': round(v['pct'] * 100, 1), 'min': v['min'], 'max': v['max']}
        for k, v in items.items()
    ]
    out.sort(key=lambda x: -x['pct'])
    return out, known_sets, len(cell['sets'])

result = []
for src in sources.values():
    cells_out = {}
    tiers = set()
    efforts = set()
    unknown = 0
    for key, cell in src['cells'].items():
        for mode in ('voyage', 'storm'):
            items, known, totaln = compute(cell, mode)
            cells_out.setdefault(key, {})[mode] = items
        cells_out[key]['tier'] = cell['tier']
        cells_out[key]['effort'] = cell['effort']
        cells_out[key]['sets'] = totaln
        if cell['tier']:
            tiers.add(cell['tier'])
        if cell['effort']:
            efforts.add(cell['effort'])
        unknown += totaln - known
    mand_items = []
    for tid in src['mandatory']:
        c = tables.get(tid, {}).get('voyage')
        if c:
            for it in c:
                mand_items.append({'item': it['item'], 'min': it['min'], 'max': it['max']})
    result.append({
        'name': src['name'],
        'tiers': sorted(tiers),
        'efforts': [e for e in ('low', 'mid', 'high') if e in efforts] or sorted(efforts),
        'cells': cells_out,
        'mandatory': mand_items,
        'unknownSets': unknown,
        'approx': src['name'] == 'Mob Drops',
    })

order = ['Weapons Crate', 'Resource Crate', 'Food Crate', 'Medical Cabinet', 'Safe', 'Shell Box',
         'Buried Treasure', 'Ironclad Loot Box', 'Mob Drops', 'Aurogen Crystal', 'Naval Mine', 'Militia Box']
result.sort(key=lambda s: order.index(s['name']) if s['name'] in order else 99)
json.dump(result, open('../site/src/data/loot_sources.json', 'w', encoding='utf-8'), indent=1)
for s in result:
    print(s['name'], '| tiers', s['tiers'], '| efforts', s['efforts'], '| cells', len(s['cells']), '| unknown sets', s['unknownSets'])
