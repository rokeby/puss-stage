"""Read-only follow-up to scene_scale_audit: the level holds no Level Instances,
and each Scene cue plays a dev sequence. So: which levels are loaded, what the
dev Scene sequences bind and cut to, and what physically stands around each
Scene's establishing camera (the "Scene 0N - Establishing / Exit Camera" actors
parked between Passages). Mutates nothing.
"""
import collections
import json
import math
import os
import re

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SITE_RADIUS_CM = 15000.0
SKY_EXTENT_CM = 50000.0

ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"
report = {"levels": [], "level_like_actors": [], "sequences": {}, "sites": {}}

try:
    report["levels"] = [lvl.get_path_name() for lvl in unreal.EditorLevelUtils.get_levels(world)]
except Exception as exc:
    report["levels"] = [f"unreadable: {exc.__class__.__name__}"]

actors = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))
for a in actors:
    cls = a.get_class().get_name()
    if "Level" in cls and cls not in ("LevelBounds",) or "Packed" in cls:
        report["level_like_actors"].append({"label": a.get_actor_label(), "class": cls})

for n in range(1, 7):
    path = f"/Game/InfinityStage/Dev/Sequences/LS_DevScene_{n:02d}"
    seq = unreal.EditorAssetLibrary.load_asset(path)
    if not seq:
        report["sequences"][n] = "missing"
        continue
    rec = {"bindings": [], "camera_cuts": [], "tracks": collections.Counter()}
    for b in seq.get_bindings():
        rec["bindings"].append(str(b.get_display_name()))
    for t in seq.get_tracks():
        rec["tracks"][t.get_class().get_name()] += 1
        if isinstance(t, unreal.MovieSceneCameraCutTrack):
            for sec in t.get_sections():
                try:
                    rec["camera_cuts"].append(str(sec.get_camera_binding_id()))
                except Exception:
                    rec["camera_cuts"].append("section")
    rec["tracks"] = dict(rec["tracks"])
    try:
        rng = seq.get_playback_range()
        rec["playback_frames"] = [rng.get_start_frame(), rng.get_end_frame()]
    except Exception:
        pass
    report["sequences"][n] = rec

cams = {}
for cam in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.CineCameraActor):
    m = re.match(r"^Scene (\d{2}) .*Establishing", cam.get_actor_label())
    if m:
        cams[int(m.group(1))] = cam.get_actor_location()

for n, centre in sorted(cams.items()):
    site = {"camera": [round(centre.x), round(centre.y), round(centre.z)], "classes": collections.Counter(),
            "labels": collections.Counter(), "lights": 0, "boxes": []}
    for a in actors:
        loc = a.get_actor_location()
        if math.hypot(loc.x - centre.x, loc.y - centre.y) > SITE_RADIUS_CM:
            continue
        cls = a.get_class().get_name()
        site["classes"][cls] += 1
        site["labels"][re.sub(r"[_ ]?\d+$", "", a.get_actor_label())] += 1
        site["lights"] += len(a.get_components_by_class(unreal.LightComponent))
        for comp in a.get_components_by_class(unreal.PrimitiveComponent):
            if not comp.is_visible():
                continue
            o, e, _ = unreal.SystemLibrary.get_component_bounds(comp)
            if max(e.x, e.y, e.z) > SKY_EXTENT_CM or max(e.x, e.y, e.z) < 1.0:
                continue
            site["boxes"].append((o.x - e.x, o.y - e.y, o.z - e.z, o.x + e.x, o.y + e.y, o.z + e.z))
    boxes = site.pop("boxes")
    if boxes:
        site["extent_m"] = [round((max(b[3] for b in boxes) - min(b[0] for b in boxes)) / 100),
                            round((max(b[4] for b in boxes) - min(b[1] for b in boxes)) / 100),
                            round((max(b[5] for b in boxes) - min(b[2] for b in boxes)) / 100)]
        site["z_range_cm"] = [round(min(b[2] for b in boxes)), round(max(b[5] for b in boxes))]
    site["primitives"] = len(boxes)
    site["classes"] = dict(site["classes"].most_common(12))
    site["labels"] = dict(site["labels"].most_common(15))
    report["sites"][n] = site

out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "scene_sites_probe.json")
json.dump(report, open(out, "w"), indent=1, default=str)
dirty = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
         len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
unreal.log(f"SCENE_SITES_PROBE_OK|levels={len(report['levels'])}|level_like={len(report['level_like_actors'])}"
           f"|sequences={len(report['sequences'])}|sites={len(report['sites'])}|dirty={dirty[0]}+{dirty[1]}|mutated=0")
