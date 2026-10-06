"""Gary note 59 (6 Oct ~00:30), P06: "another dramatic car drive-by light". Places ONE AInfinityStageSweepLight like
the P02 car (place_p02_car_light.py, run CAR-20261005-092430), but timed to the music: a SINGLE pass whose middle
lands on the strongest change in SW_P06_IntoVoid (68.55 s, strength 1.0, majorChangeProposals in
P06_WalkingMusic_6_into_void.analysis.json), restricted to the P06 segment.

How it moves (declaration-proven, InfinityStageSweepLight.h:80-112, .cpp:182-259): in game worlds the pass clock is
Master time from the start of the CURRENT segment (bTimeFromSegmentStart), so StartDelaySeconds = seconds into P06;
RepeatEverySeconds <= 0 = a single pass; ActiveSegmentGuids = run only in these segments (here P06's PassageGuid,
read from the Show by label "Passage 6", never typed).
Placement (inferred): beside P06's route at bay 44 of 64 (~2 bays past the 68.55 s beat bay under the uniform-speed
model lighting_scores_round2_build.py p06_beat_model), 2400 cm outside house RIGHT (-Y; the P02 car is house left),
driving along the route and aiming across the passage so its light rakes through the wing gaps.

Backs up the level, saves ONLY the level, reads back, writes place_p06_car_light_record.json. Refuses on PIE, a dirty
census, a wrong world, an existing car, or a passage-actor count other than 1. REVERT: delete the actor by label in
the editor (or run with args mode REVERT: destroys exactly this label, saves the level).
"""
import datetime
import json
import os
import shutil

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = datetime.datetime.now().strftime("CAR6-%Y%m%d-%H%M%S")
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
LABEL = "P06 Car Light (drive-by on the 68.55 s change)"
BEAT_S = 68.55
TRAVEL_S = 3.0
BAY_FRACTION = 43.5 / 64.0
OUTSIDE_Y = -2400.0
HEIGHT = 90.0
SETTINGS = {"start_offset": unreal.Vector(-1600.0, 0.0, 0.0), "end_offset": unreal.Vector(1600.0, 0.0, 0.0),
            "curved_path": True, "arc_control_offset": unreal.Vector(0.0, 500.0, 0.0),
            "aim_at_target": True, "aim_target_local": unreal.Vector(0.0, -OUTSIDE_Y, 0.0),
            "start_delay_seconds": BEAT_S - TRAVEL_S / 2.0, "travel_seconds": TRAVEL_S,
            "repeat_every_seconds": 0.0, "repeat_jitter_seconds": 0.0, "time_from_segment_start": True,
            "fade_in_seconds": 0.5, "fade_out_seconds": 0.9, "peak_intensity": 12000.0,
            "use_temperature": True, "temperature_kelvin": 5200.0, "attenuation_radius_cm": 3200.0,
            "cast_shadows": True, "cast_volumetric_shadow": False}
ARGS = os.path.join(HERE, "place_p06_car_light_args.json")


def stop(msg):
    unreal.log_error("CAR6_PLACE_FAILED|run=%s|%s" % (RUN, msg))
    raise RuntimeError(msg)


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def plain(value):
    if isinstance(value, unreal.Vector):
        return [value.x, value.y, value.z]
    if isinstance(value, (list, tuple)) or type(value).__name__.startswith("Array"):
        return [str(v) for v in value]
    return value


def main():
    args = json.load(open(ARGS, encoding="utf-8")) if os.path.isfile(ARGS) else {"mode": "APPLY", "confirm": "APPLY P06CAR"}
    MODE = str(args.get("mode", "DRY")).upper()
    if MODE not in ("DRY", "APPLY", "REVERT") or args.get("confirm") != "%s P06CAR" % MODE:
        stop("CONFIRM|mode=%s|confirm must be '%s P06CAR'" % (MODE, MODE))
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if ed.get_game_world() is not None:
        stop("PIE_ACTIVE")
    if ed.get_editor_world().get_path_name().split(".")[0] != WORLD:
        stop("WRONG_WORLD")
    if census() != {"content": [], "maps": []}:
        stop("DIRTY_BEFORE|" + json.dumps(census()))
    actors = sub.get_all_level_actors()
    existing = [a for a in actors if str(a.get_actor_label()) == LABEL]
    if MODE == "REVERT":
        if len(existing) != 1:
            stop("REVERT_COUNT|%d" % len(existing))
        backup = "E:/PussStage/Backups/PreP06CarLightRevert-" + RUN
        os.makedirs(backup)
        shutil.copy2(UMAP, backup)
        sub.destroy_actor(existing[0])
        if census()["maps"] != [WORLD] or census()["content"]:
            stop("DIRTY_SCOPE|" + json.dumps(census()))
        if not unreal.EditorLoadingAndSavingUtils.save_map(ed.get_editor_world(), WORLD):
            stop("SAVE_FAILED")
        if any(str(a.get_actor_label()) == LABEL for a in sub.get_all_level_actors()):
            stop("REVERT_READBACK")
        unreal.log("CAR6_REVERT_OK|run=%s|backup=%s" % (RUN, backup))
        return
    cls = getattr(unreal, "InfinityStageSweepLight", None)
    if cls is None:
        stop("CLASS_MISSING")
    if existing:
        stop("ALREADY_PLACED")
    p06 = [a for a in actors if a.get_class().get_name() == "InfinityStagePassageActor"
           and str(a.get_actor_label()).startswith("Passage 06")]
    if len(p06) != 1:
        stop("P06_COUNT|%d" % len(p06))
    show = unreal.EditorAssetLibrary.load_asset(SHOW)
    rows = [s for s in show.get_editor_property("passage_settings") if str(s.get_editor_property("label")) == "Passage 6"]
    if len(rows) != 1:
        stop("PASSAGE6_ROWS|%d" % len(rows))
    segment_guid = rows[0].get_editor_property("passage_guid")
    route = p06[0].get_editor_property("route")
    W = unreal.SplineCoordinateSpace.WORLD
    dist = route.get_spline_length() * BAY_FRACTION
    xf = route.get_transform_at_distance_along_spline(dist, W, False)
    xf = unreal.Transform(xf.translation, xf.rotation.rotator(), unreal.Vector(1, 1, 1))
    loc = unreal.MathLibrary.transform_location(xf, unreal.Vector(0.0, OUTSIDE_Y, HEIGHT))
    rot = xf.rotation.rotator()
    plan = {"run": RUN, "label": LABEL, "location": [loc.x, loc.y, loc.z], "yaw": rot.yaw, "route_distance_cm": dist,
            "segment_guid": str(segment_guid), "settings": {k: plain(v) for k, v in SETTINGS.items()}}
    if MODE == "DRY":
        unreal.log("CAR6_DRY_OK|run=%s|plan=%s|mutated=0" % (RUN, json.dumps(plan, default=str)))
        return
    backup = "E:/PussStage/Backups/PreP06CarLight-" + RUN
    os.makedirs(backup)
    shutil.copy2(UMAP, backup)
    car = sub.spawn_actor_from_class(cls, loc, rot)
    car.set_actor_label(LABEL)
    applied = {}
    for k, v in list(SETTINGS.items()) + [("active_segment_guids", [segment_guid])]:
        try:
            car.set_editor_property(k, v)
            applied[k] = plain(car.get_editor_property(k))
        except Exception as exc:  # noqa: BLE001 -- report real names, never guess silently
            applied[k] = "ERR %s" % exc
    bad = {k: v for k, v in applied.items() if isinstance(v, str) and v.startswith("ERR")}
    if bad:
        stop("PROPERTY_NAMES|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(bad))
    if applied["active_segment_guids"] != [str(segment_guid)]:
        stop("SEGMENT_GUID_READBACK|%s|NOTHING SAVED; Don't-Save restart" % applied["active_segment_guids"])
    dirty = census()
    if dirty["content"] or dirty["maps"] != [WORLD]:
        stop("DIRTY_SCOPE|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(dirty))
    if not unreal.EditorLoadingAndSavingUtils.save_map(ed.get_editor_world(), WORLD):
        stop("SAVE_FAILED")
    if census() != {"content": [], "maps": []}:
        stop("POST_SAVE_DIRTY|" + json.dumps(census()))
    plan.update({"applied": applied, "backup": backup})
    json.dump(plan, open(os.path.join(HERE, "place_p06_car_light_record.json"), "w", encoding="utf-8"), indent=1, default=str)
    unreal.log("CAR6_PLACED_OK|run=%s|loc=%.0f,%.0f,%.0f|start_delay=%.2f|segment=%s|backup=%s"
               % (RUN, loc.x, loc.y, loc.z, SETTINGS["start_delay_seconds"], segment_guid, backup))


main()
