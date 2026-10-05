"""Gary 5 Oct: try the window car light in P02's second half. Places ONE AInfinityStageSweepLight (built a52051c) outside
the house-left wing line near P02 bay 15, composed against the LIVE P02 route (curved: frame from the spline at that
distance). The car drives along the route outside the wings and aims across the passage, so its light comes through
the wing gaps. Backs up the level, saves ONLY the level, reads back. Refuses on PIE, a dirty census or an existing car.
"""
import datetime
import json
import os
import shutil

import unreal

RUN = datetime.datetime.now().strftime("CAR-%Y%m%d-%H%M%S")
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
LABEL = "P02 Car Light (trial, Gary to tune)"
BAY_FRACTION = 14.5 / 23.0          # between bays 14 and 15 of 23, inside the failing stretch (bays 12-19)
OUTSIDE_Y = 2400.0                  # beyond the wing line (half width ~1416) and the rig columns (+60), house left (+Y)
HEIGHT = 90.0                       # headlight height
SETTINGS = {"start_offset": unreal.Vector(-1400.0, 0.0, 0.0), "end_offset": unreal.Vector(1400.0, 0.0, 0.0),
            "curved_path": True, "arc_control_offset": unreal.Vector(0.0, -500.0, 0.0),
            "aim_at_target": True, "aim_target_local": unreal.Vector(0.0, -OUTSIDE_Y, 0.0),
            "travel_seconds": 3.5, "repeat_every_seconds": 11.0, "repeat_jitter_seconds": 4.0,
            "fade_in_seconds": 0.6, "fade_out_seconds": 0.8, "peak_intensity": 9000.0,
            "use_temperature": True, "temperature_kelvin": 4200.0, "attenuation_radius_cm": 3200.0,
            "cast_shadows": True, "cast_volumetric_shadow": False}


def stop(msg):
    unreal.log_error("CAR_PLACE_FAILED|run=%s|%s" % (RUN, msg))
    raise RuntimeError(msg)


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
if ed.get_game_world() is not None:
    stop("PIE_ACTIVE")
if census() != {"content": [], "maps": []}:
    stop("DIRTY_BEFORE|" + json.dumps(census()))
cls = getattr(unreal, "InfinityStageSweepLight", None)
if cls is None:
    stop("CLASS_MISSING")
actors = sub.get_all_level_actors()
if any(str(a.get_actor_label()) == LABEL for a in actors):
    stop("ALREADY_PLACED")
p02 = [a for a in actors if a.get_class().get_name() == "InfinityStagePassageActor"
       and str(a.get_actor_label()).startswith("Passage 02")]
if len(p02) != 1:
    stop("P02_COUNT|%d" % len(p02))
route = p02[0].get_editor_property("route")
W = unreal.SplineCoordinateSpace.WORLD
dist = route.get_spline_length() * BAY_FRACTION
xf = route.get_transform_at_distance_along_spline(dist, W, False)
xf = unreal.Transform(xf.translation, xf.rotation.rotator(), unreal.Vector(1, 1, 1))
loc = unreal.MathLibrary.transform_location(xf, unreal.Vector(0.0, OUTSIDE_Y, HEIGHT))
rot = xf.rotation.rotator()
backup = "E:/PussStage/Backups/PreP02CarLight-" + RUN
os.makedirs(backup)
shutil.copy2(UMAP, backup)
car = sub.spawn_actor_from_class(cls, loc, rot)
car.set_actor_label(LABEL)
applied = {}
for k, v in SETTINGS.items():
    try:
        car.set_editor_property(k, v)
        got = car.get_editor_property(k)
        applied[k] = [got.x, got.y, got.z] if isinstance(got, unreal.Vector) else got
    except Exception as exc:  # noqa: BLE001 -- report real names, never guess silently
        applied[k] = "ERR %s" % exc
bad = {k: v for k, v in applied.items() if isinstance(v, str) and v.startswith("ERR")}
if bad:
    stop("PROPERTY_NAMES|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(bad))
dirty = census()
if dirty["content"] or dirty["maps"] != [WORLD]:
    stop("DIRTY_SCOPE|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(dirty))
if not unreal.EditorLoadingAndSavingUtils.save_map(ed.get_editor_world(), WORLD):
    stop("SAVE_FAILED")
if census() != {"content": [], "maps": []}:
    stop("POST_SAVE_DIRTY|" + json.dumps(census()))
rec = {"run": RUN, "label": LABEL, "location": [loc.x, loc.y, loc.z], "yaw": rot.yaw, "applied": applied, "backup": backup}
json.dump(rec, open("E:/PussStage/Saved/CodexConductor/place_p02_car_light_record.json", "w", encoding="utf-8"), indent=1,
          default=str)
unreal.log("CAR_PLACED_OK|run=%s|loc=%.0f,%.0f,%.0f|yaw=%.1f|applied=%s|backup=%s"
           % (RUN, loc.x, loc.y, loc.z, rot.yaw, json.dumps(applied, default=str), backup))
