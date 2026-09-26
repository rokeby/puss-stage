"""Read-only audit for the Transitions & Scale brief (26 Sep 2026): what is in each
Scene, how big it is, and whether anything already reads as wall or rig.

A Scene cue references only a Level Sequence; its world is whatever Level
Instances that sequence films. So this reports (1) the Show's Scene cues, (2)
every Level Instance and the measured extents of its contents (floor and
ceiling candidates, wall-like and rig-like primitives, lights, sky/fog), and
(3) camera actors, so Scenes can be tied to the instances they film.
Mutates nothing.
"""
import collections
import json
import os
import statistics

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
SKY_EXTENT_CM = 50000.0   # anything larger is a sky dome or backdrop, not architecture

ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"


def enum_name(v):
    return str(v).split(".")[-1].split(":")[0].strip().rstrip(">")


report = {"scene_cues": [], "level_instances": [], "groups": {}, "cameras": []}

show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
for i, cue in enumerate(show.get_editor_property("cues")):
    kind = enum_name(cue.get_editor_property("type"))
    if kind == "WING_PAIR":
        continue
    rec = {"index": i, "label": str(cue.get_editor_property("label")), "type": kind}
    try:
        scene = cue.get_editor_property("scene")
        seq = scene.get_editor_property("sequence")
        rec["sequence"] = seq.get_path_name() if seq else None
        rec["camera_owner"] = enum_name(scene.get_editor_property("camera_owner"))
    except Exception as exc:
        rec["scene_error"] = exc.__class__.__name__
    report["scene_cues"].append(rec)

for li in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.LevelInstance):
    loc = li.get_actor_location()
    try:
        asset = li.get_editor_property("world_asset")
        asset_path = asset.get_path_name() if hasattr(asset, "get_path_name") else str(asset)
    except Exception:
        asset_path = None
    report["level_instances"].append({
        "label": li.get_actor_label(), "asset": asset_path,
        "location": [round(loc.x), round(loc.y), round(loc.z)],
        "yaw": round(li.get_actor_rotation().yaw, 1),
        "hidden_in_editor": bool(li.is_temporarily_hidden_in_editor()) if hasattr(li, "is_temporarily_hidden_in_editor") else None,
    })

groups = collections.defaultdict(lambda: {"actors": 0, "boxes": [], "floors": [], "walls": [], "tall": [],
                                          "lights": collections.Counter(), "env": collections.Counter()})
for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
    level = a.get_outer()
    key = level.get_outer().get_path_name() if level and level.get_outer() else "?"
    g = groups[key]
    g["actors"] += 1
    cls = a.get_class().get_name()
    if cls in ("ExponentialHeightFog", "SkyAtmosphere", "SkyLight", "DirectionalLight", "VolumetricCloud"):
        g["env"][cls] += 1
    for lc in a.get_components_by_class(unreal.LightComponent):
        g["lights"][lc.get_class().get_name()] += 1
    for comp in a.get_components_by_class(unreal.PrimitiveComponent):
        if not comp.is_visible() or isinstance(comp, unreal.LightComponent):
            continue
        origin, ext, _ = unreal.SystemLibrary.get_component_bounds(comp)
        if max(ext.x, ext.y, ext.z) > SKY_EXTENT_CM or max(ext.x, ext.y, ext.z) < 1.0:
            continue
        lo = (origin.x - ext.x, origin.y - ext.y, origin.z - ext.z)
        hi = (origin.x + ext.x, origin.y + ext.y, origin.z + ext.z)
        g["boxes"].append((lo, hi))
        w, d, h = ext.x * 2, ext.y * 2, ext.z * 2
        label = a.get_actor_label()
        if h < 60 and w * d > 250000:            # flat and at least ~25 m2: floor-like
            g["floors"].append(round(hi[2]))
        if h > 600 and min(w, d) < 120 and max(w, d) > 500:   # tall, thin, wide: wall-like
            g["walls"].append({"actor": label, "h": round(h), "len": round(max(w, d)), "z0": round(lo[2])})
        if h > 1500:
            g["tall"].append({"actor": label, "h": round(h), "z0": round(lo[2])})

for key, g in groups.items():
    if not g["boxes"]:
        continue
    xs0 = [b[0][0] for b in g["boxes"]]; xs1 = [b[1][0] for b in g["boxes"]]
    ys0 = [b[0][1] for b in g["boxes"]]; ys1 = [b[1][1] for b in g["boxes"]]
    zs0 = [b[0][2] for b in g["boxes"]]; zs1 = [b[1][2] for b in g["boxes"]]
    # Robust extents: the 2nd and 98th percentiles, so one stray prop far away
    # does not define a Scene's size.
    def pct(values, q):
        values = sorted(values)
        return values[min(len(values) - 1, max(0, int(q * (len(values) - 1))))]
    report["groups"][key] = {
        "actors": g["actors"], "primitives": len(g["boxes"]),
        "extent_cm": {"x": [round(pct(xs0, .02)), round(pct(xs1, .98))], "y": [round(pct(ys0, .02)), round(pct(ys1, .98))],
                      "z": [round(pct(zs0, .02)), round(pct(zs1, .98))]},
        "size_m": [round((pct(xs1, .98) - pct(xs0, .02)) / 100), round((pct(ys1, .98) - pct(ys0, .02)) / 100),
                   round((pct(zs1, .98) - pct(zs0, .02)) / 100)],
        "floor_top_cm": {"count": len(g["floors"]),
                         "median": statistics.median(g["floors"]) if g["floors"] else None},
        "wall_like": sorted(g["walls"], key=lambda w: -w["h"] * w["len"])[:6],
        "tall_over_15m": sorted(g["tall"], key=lambda t: -t["h"])[:5],
        "lights": dict(g["lights"]), "environment": dict(g["env"]),
    }

for cam in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.CameraActor):
    loc = cam.get_actor_location()
    report["cameras"].append({"label": cam.get_actor_label(), "class": cam.get_class().get_name(),
                              "location": [round(loc.x), round(loc.y), round(loc.z)]})

out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "scene_scale_audit.json")
json.dump(report, open(out, "w"), indent=1, default=str)
dirty = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
         len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
unreal.log(f"SCENE_SCALE_AUDIT_OK|scene_cues={len(report['scene_cues'])}|level_instances={len(report['level_instances'])}"
           f"|groups={len(report['groups'])}|cameras={len(report['cameras'])}|dirty={dirty[0]}+{dirty[1]}|mutated=0")
