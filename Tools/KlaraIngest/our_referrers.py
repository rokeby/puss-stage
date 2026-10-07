"""Find PussStage packages (outside the colliding folders) whose header mentions a colliding path.
Read-only. Scans the first 8 MB of each .uasset/.umap (name table lives in the header)."""
import os, json, sys
OC = r"E:\PussStage\Content"
OUT = r"E:\PussStage\Saved\CodexConductor\KlaraIngest\our_referrers.json"
rep = json.load(open(r"E:\PussStage\Saved\CodexConductor\KlaraIngest\census_report.json", encoding="utf-8"))
targets = sorted({d["package"] for d in rep["collision_diff"]["files"] if d["class"] == "COLLIDES"})
# use the case-preserved spelling from the rel path
targets = sorted({"/Game/" + os.path.splitext(d["rel"])[0] for d in rep["collision_diff"]["files"] if d["class"] == "COLLIDES"})
pats = {t: (t.encode(), t.encode("utf-16le")) for t in targets}
prefixes = [b"/Game/KK_S1_Animals/", b"/Game/KK_S2_Shrine/"]
hits = {t: [] for t in targets}; prefix_hits = {p.decode(): [] for p in prefixes}
n = 0
for dp, _, fns in os.walk(OC):
    for fn in fns:
        if not fn.endswith((".uasset", ".umap")):
            continue
        f = os.path.join(dp, fn); rel = os.path.relpath(f, OC).replace("\\", "/")
        with open(f, "rb") as fh:
            d = fh.read(8 << 20)
        n += 1
        for p in prefixes:
            if p in d and not rel.startswith(p.decode()[6:]):
                prefix_hits[p.decode()].append(rel)
        for t, (a, w) in pats.items():
            if (a in d or w in d) and rel != t[6:] + os.path.splitext(fn)[1]:
                hits[t].append(rel)
json.dump({"scanned": n, "per_colliding_package": hits, "outside_folder_refs_to_prefix": prefix_hits}, open(OUT, "w"), indent=1)
print(n, {k: len(v) for k, v in prefix_hits.items()}); print({k: v[:5] for k, v in hits.items() if v})
