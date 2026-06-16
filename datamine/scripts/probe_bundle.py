"""Probe a SAND addressables bundle: list object types/names, check type trees."""
import sys, UnityPy

path = sys.argv[1]
env = UnityPy.load(path)
counts = {}
named = []
for obj in env.objects:
    t = obj.type.name
    counts[t] = counts.get(t, 0) + 1
print("OBJECT TYPE COUNTS:", counts)

for obj in env.objects:
    if obj.type.name in ("MonoBehaviour", "MonoScript", "ScriptableObject"):
        try:
            if obj.serialized_type and obj.serialized_type.node:
                tree = obj.read_typetree()
                name = tree.get("m_Name", "")
                print(f"[typetree] {obj.type.name} name={name!r} keys={list(tree.keys())[:12]}")
            else:
                d = obj.read()
                print(f"[no-tree] {obj.type.name} name={getattr(d, 'm_Name', '?')}")
        except Exception as e:
            print(f"[err] {obj.type.name}: {e}")
