"""Read-only: measure which mesh-local Y extreme carries the straight (outer) edge for every
Wing mesh assigned to a Left/Right panel, via ProceduralMeshLibrary section reads. Saves nothing."""
import json, os, re, statistics
import unreal

SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
LABEL_RE = re.compile(r"^P(?P<passage>\d{2}) Wing (?P<ordinal>\d{3})$")

def pkg(v):
    if v is None: return None
    return v.get_path_name().split(".", 1)[0] if hasattr(v, "get_path_name") else str(v).split(".", 1)[0]

show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
if show is None: raise RuntimeError("Show did not load")
meshes = set()
for cue in show.get_editor_property("cues"):
    if not LABEL_RE.match(str(cue.get_editor_property("label"))): continue
    pair = cue.get_editor_property("wing_pair")
    for side in ("left", "right"):
        m = pkg(pair.get_editor_property(side).get_editor_property("mesh"))
        if m: meshes.add(m)

def measure(path):
    out = {"error": None}
    sm = unreal.EditorAssetLibrary.load_asset(path)
    if sm is None:
        out["error"] = "did not load"; return out
    try:
        verts, nx = [], []
        nsec = sm.get_num_sections(0)
        for s in range(nsec):
            r = unreal.ProceduralMeshLibrary.get_section_from_static_mesh(sm, 0, s)
            v, tri, nrm = r[0], r[1], r[2]
            verts.extend((p.x, p.y, p.z) for p in v)
            nx.extend(n.x for n in nrm)
        if not verts: raise RuntimeError("no vertices")
        xs, ys, zs = zip(*verts)
        y0, y1 = min(ys), max(ys); w = max(1e-6, y1 - y0)
        z0, z1 = min(zs), max(zs); h = max(1e-6, z1 - z0)
        eps = 0.005 * w
        lo = [z for y, z in zip(ys, zs) if abs(y - y0) < eps]
        hi = [z for y, z in zip(ys, zs) if abs(y - y1) < eps]
        # silhouette extent per Z bin: straight edge => near-constant extent
        nb = 24; bins_lo = [None]*nb; bins_hi = [None]*nb
        for y, z in zip(ys, zs):
            b = min(nb-1, int((z - z0) / h * nb))
            bins_lo[b] = y if bins_lo[b] is None or y < bins_lo[b] else bins_lo[b]
            bins_hi[b] = y if bins_hi[b] is None or y > bins_hi[b] else bins_hi[b]
        blo = [b for b in bins_lo if b is not None]; bhi = [b for b in bins_hi if b is not None]
        out.update({
            "sections": nsec, "verts": len(verts),
            "size": [round(max(xs)-min(xs),2), round(w,2), round(h,2)],
            "y_min": round(y0,2), "y_max": round(y1,2),
            "ymin_count": len(lo), "ymax_count": len(hi),
            "ymin_zspan": round((max(lo)-min(lo))/h,3) if lo else 0.0,
            "ymax_zspan": round((max(hi)-min(hi))/h,3) if hi else 0.0,
            "ymin_edge_std_over_w": round(statistics.pstdev(blo)/w,4) if len(blo) > 1 else None,
            "ymax_edge_std_over_w": round(statistics.pstdev(bhi)/w,4) if len(bhi) > 1 else None,
            "mean_normal_x": round(sum(nx)/len(nx),3) if nx else None,
        })
    except Exception as exc:
        out["error"] = repr(exc)
    return out

result = {m: measure(m) for m in sorted(meshes)}
out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexWingHandedness2", "mesh_geometry.json")
with open(out, "w", encoding="utf-8") as fh:
    json.dump(result, fh, indent=1, sort_keys=True)
ok = sum(1 for r in result.values() if r.get("verts"))
unreal.log(f"PUSS_WING_GEOM_SUCCESS|meshes={len(result)}|ok={ok}")
