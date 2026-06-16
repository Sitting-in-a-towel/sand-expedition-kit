"""Dump all MonoBehaviour typetrees from a bundle to JSON.
Usage: python dump_bundle_json.py <bundle> <out.json> [name-filter]
"""
import sys, json, UnityPy

bundle, out = sys.argv[1], sys.argv[2]
env = UnityPy.load(bundle)
result = []
for obj in env.objects:
    if obj.type.name != "MonoBehaviour":
        continue
    try:
        tree = obj.read_typetree()
        result.append({"path_id": obj.path_id, "data": tree})
    except Exception as e:
        result.append({"path_id": obj.path_id, "error": str(e)})

def default(o):
    if isinstance(o, bytes):
        try:
            return o.decode("utf-8", "replace")
        except Exception:
            return repr(o)
    return str(o)

with open(out, "w", encoding="utf-8") as f:
    json.dump(result, f, indent=1, ensure_ascii=False, default=default)
print(f"wrote {len(result)} objects -> {out}")
