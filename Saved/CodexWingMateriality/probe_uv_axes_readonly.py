"""Read-only: fit U and V of each live wing mesh against its local Y and Z.

Gives Effects sources the exact UV -> panel-local mapping for placing flames on
the burn front: Y = (U - bU) / aU, Z = (V - bV) / aV.
"""
import importlib.util, os
import unreal
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(os.path.dirname(__file__), "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)
wm.editor_ready()
before = wm.dirty()


def fit(xs, ys):
    n = len(xs); mx = sum(xs) / n; my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs); sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    a = sxy / sxx if sxx else 0.0
    b = my - a * mx
    res = max(abs(y - (a * x + b)) for x, y in zip(xs, ys))
    return a, b, res


meshes = set()
for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if actor.get_class().get_name() == "InfinityStagePassageActor":
        for comp in actor.get_components_by_class(unreal.InstancedStaticMeshComponent):
            meshes.add(wm.pkg(comp.get_editor_property("static_mesh")))
rows, errors = {}, {}
for path in sorted(meshes):
    sm = unreal.EditorAssetLibrary.load_asset(path)
    try:
        desc = sm.get_static_mesh_description(0)
        Y, Z, U, V = [], [], [], []
        # Front section only (polygon group 0 = Front slot), where the image lives.
        for vi in range(desc.get_vertex_instance_count()):
            vid = unreal.VertexInstanceID()
            vid.set_editor_property("id_value", vi)
            v = desc.get_vertex_instance_vertex(vid)
            p = desc.get_vertex_position(v)
            uv = desc.get_vertex_instance_uv(vid, 0)
            if abs(p.x) < 1e-3 and False:
                continue
            Y.append(p.y); Z.append(p.z); U.append(uv.x); V.append(uv.y)
        aU, bU, rU = fit(Y, U)
        aV, bV, rV = fit(Z, V)
        rows[path] = {"U_per_cm_Y": aU, "U_at_Y0": bU, "U_fit_err": rU, "V_per_cm_Z": aV, "V_at_Z0": bV,
                      "V_fit_err": rV, "n": len(U)}
    except Exception as exc:  # noqa: BLE001
        errors[path] = repr(exc)[:200]
wm.require(wm.dirty() == before, f"dirty changed {wm.dirty()}")
wm.write_json("uv_axes.json", {"rows": rows, "errors": errors})
unreal.log(f"PUSS_WING_UV_AXES_SUCCESS|meshes={len(rows)}|errors={len(errors)}")
