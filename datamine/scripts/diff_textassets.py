"""Diff all TextAssets between two data.unity3d builds (content-level).

Usage: python scripts/diff_textassets.py <old_data.unity3d> <new_data.unity3d>

Names repeat (several "Items", "Composite"...), so we key by name and compare the
multiset of per-asset content hashes. Reports names added / removed / changed,
with size deltas, so we can see exactly what the update touched.
"""
import sys, hashlib, UnityPy
from collections import defaultdict


def load(path):
    env = UnityPy.load(path)
    by_name = defaultdict(list)  # name -> [(sha1, len)]
    for o in env.objects:
        if o.type.name != "TextAsset":
            continue
        d = o.read()
        s = d.m_Script
        b = s.encode("utf-8", "replace") if isinstance(s, str) else bytes(s)
        by_name[d.m_Name].append((hashlib.sha1(b).hexdigest(), len(b)))
    for n in by_name:
        by_name[n].sort()
    return by_name


old = load(sys.argv[1])
new = load(sys.argv[2])

added = sorted(set(new) - set(old))
removed = sorted(set(old) - set(new))
changed = sorted(n for n in set(old) & set(new) if [h for h, _ in old[n]] != [h for h, _ in new[n]])

print(f"TextAssets: old={sum(len(v) for v in old.values())} new={sum(len(v) for v in new.values())}")
print(f"names: added={len(added)} removed={len(removed)} changed={len(changed)}\n")

if added:
    print("--- ADDED names ---")
    for n in added:
        print(f"  + {n}  ({sum(l for _, l in new[n])} B over {len(new[n])} asset(s))")
if removed:
    print("--- REMOVED names ---")
    for n in removed:
        print(f"  - {n}  ({sum(l for _, l in old[n])} B)")
print("\n--- CHANGED names (content differs) ---")
for n in changed:
    ob = sum(l for _, l in old[n])
    nb = sum(l for _, l in new[n])
    print(f"  ~ {n}  ({ob} -> {nb} B, {len(old[n])}->{len(new[n])} asset(s))")
