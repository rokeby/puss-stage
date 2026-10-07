"""Read-only census: flap count per placed Flat V3 mesh in P04/P05/P06 (offline, no Unreal)."""
import json, os, re, glob, collections
ROOT = r"E:\PussStage"
OUT = os.path.join(ROOT, r"Saved\CodexFlatV3\flutter")
idx = {}
for p in glob.glob(os.path.join(ROOT, r"DerivedAssets\FlatV3\**\*_build.json"), recursive=True):
    m = re.match(r"(.+)_(L|R)_build\.json$", os.path.basename(p))
    if not m: continue
    try: d = json.load(open(p, encoding="utf-8"))
    except Exception: continue
    if "flaps" not in d: continue
    key = "SM_FlatV3_" + m.group(1)
    fl = d["flaps"]
    sizes = []
    for f in fl:
        b = f.get("uv_bounds_bottom_left")
        sizes.append(f.get("orientation"))
    rec = {"build": os.path.relpath(p, ROOT), "mtime": os.path.getmtime(p), "flaps": len(fl),
           "curl_cm": [f.get("curl_cm") for f in fl], "orient": sizes,
           "height_m": d.get("dimensions_m", {}).get("height"), "width_m": d.get("dimensions_m", {}).get("width"),
           "flaps_input": d.get("inputs", {}).get("flaps")}
    if key not in idx or rec["mtime"] > idx[key]["mtime"]:
        idx[key] = rec
placed = json.load(open(os.path.join(ROOT, r"Saved\CodexFlatV3\floorgap\fbx_bottom_placed.json")))["meshes"]
p06 = json.load(open(os.path.join(ROOT, r"Saved\CodexFlatV3\p06relayout\relayout_plan.json")))["rows"]
p06_meshes = []
for r in p06:
    for s, v in r["sides"].items():
        m = v.get("mesh") or v.get("old_mesh")
        if m: p06_meshes.append((r["label"], s, m.rsplit("/", 1)[-1], v.get("action")))
rows = []
def look(name):
    r = idx.get(name)
    return (r["flaps"], r["build"], r["curl_cm"], r["height_m"], r["width_m"]) if r else (None, None, None, None, None)
for name in sorted(placed):
    pm = re.search(r"P0([45])", name)
    if not pm: continue
    n, b, c, h, w = look(name)
    rows.append({"passage": "P0" + pm.group(1), "src": "fbx_bottom_placed 6 Oct 21:52", "mesh": name, "flaps": n, "curl_cm": c, "h_m": h, "w_m": w, "build": b})
for label, s, name, act in p06_meshes:
    n, b, c, h, w = look(name)
    rows.append({"passage": "P06", "src": "relayout_plan 7 Oct 08:10", "label": label, "side": s, "action": act, "mesh": name, "flaps": n, "curl_cm": c, "h_m": h, "w_m": w, "build": b})
# realism builds summary
real = {k: v for k, v in idx.items() if "_real_" in k}
json.dump({"rows": rows, "realism_builds": real, "index_size": len(idx)}, open(os.path.join(OUT, "flap_census.json"), "w"), indent=1)
for pas in ("P04", "P05", "P06"):
    rs = [r for r in rows if r["passage"] == pas]
    c = collections.Counter(r["flaps"] for r in rs)
    print(pas, "meshes", len(rs), "flap-count histogram", dict(c), "total flaps", sum(r["flaps"] or 0 for r in rs))
    for r in rs:
        if r["flaps"] is None: print("   NOBUILD", r["mesh"])
print("realism builds", collections.Counter(v["flaps"] for v in real.values()))
