"""Place the five transition stalls cameras (Look & camera owns them; Soft goods binds its cuts to them).

Gary, 29 Sep: each Interaction's shadow play runs on the curtain at the NEXT
Passage's mouth, then the curtain falls into that Passage. Each Interaction N
(1..5) gets a level CineCameraActor at Passage N+1's mouth, seated exactly as the
Opening stalls camera sits relative to Passage 1's route start. The seat is
DERIVED LIVE from the Opening camera and each route (not typed), so it follows
route changes; P02's bent route gives it yaw ~22.9.

Each camera gets:
  - label "Interaction N — Stalls Camera", folder InfinityStage/TransitionStalls;
  - tags InfinityStage.TransitionStalls and InfinityStage.Mouth.P0{N+1} (Soft
    goods' fit script binds by these and refuses unless exactly one per mouth);
  - the Opening camera's filmback, lens, focal length, aperture and focus;
  - the camera body hidden in game (the Opening's beige box lesson).

DRY_RUN = True only reports the plan. Set it False to place. Guards: the
expected world, no PIE, only the map may be dirty, no ZZ_ actors, and no
existing TransitionStalls camera. Saves the MAP only, re-checking for ZZ_ actors
in the same script first. Reads back every camera. Revert:
revert_transition_stalls.py. Back up the .umap first
(Backups/PreTransitionStalls-<stamp>/).
Success markers: PUSS_TRANSITION_STALLS_DRYRUN / PUSS_TRANSITION_STALLS_PLACED
"""

import json
import math
import os

import unreal

DRY_RUN = True

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
OPENING_CAMERA_LABEL = "Opening — Stalls Camera"
STALLS_TAG = "InfinityStage.TransitionStalls"
FOLDER = "InfinityStage/TransitionStalls"


def dirty():
    return sorted(
        [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
        + [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])


def route_start(passage):
    route = passage.get_editor_property("route")
    start = route.get_location_at_distance_along_spline(0.0, unreal.SplineCoordinateSpace.WORLD)
    direction = route.get_direction_at_distance_along_spline(0.0, unreal.SplineCoordinateSpace.WORLD)
    return start, math.degrees(math.atan2(direction.y, direction.x))


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
        raise RuntimeError("Unexpected editor world (or PIE is running)")
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE/SIE is active")
    others = [p for p in dirty() if p != EXPECTED_WORLD]
    if others:
        raise RuntimeError(f"Refusing: packages other than the map are dirty {others}")
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = actor_subsystem.get_all_level_actors()
    if [a for a in actors if a.get_actor_label().startswith("ZZ_")]:
        raise RuntimeError("Refusing: ZZ_ actors present")
    existing = [a.get_actor_label() for a in actors if a.actor_has_tag(STALLS_TAG)]
    if existing:
        raise RuntimeError(f"Refusing: stalls cameras already exist {existing} (revert first)")

    show = unreal.load_asset(SHOW_PATH)
    guid_to_label = {unreal.GuidLibrary.conv_guid_to_string(p.get_editor_property("passage_guid")):
                     str(p.get_editor_property("label")) for p in show.get_editor_property("passage_settings")}
    starts = {}
    for actor in actors:
        if actor.get_class().get_name() == "InfinityStagePassageActor":
            label = guid_to_label.get(unreal.GuidLibrary.conv_guid_to_string(actor.get_editor_property("passage_guid")))
            if label:
                starts[label] = route_start(actor)
    openings = [a for a in actors if isinstance(a, unreal.CineCameraActor) and a.get_actor_label() == OPENING_CAMERA_LABEL]
    del actors
    if len(openings) != 1 or "Passage 1" not in starts:
        raise RuntimeError("Need exactly one Opening stalls camera and Passage 1")
    opening = openings[0]
    lens = opening.get_cine_camera_component()
    open_loc, open_rot = opening.get_actor_location(), opening.get_actor_rotation()
    p1_start, p1_yaw = starts["Passage 1"]
    y1 = math.radians(p1_yaw)
    d = open_loc - p1_start
    along = d.x * math.cos(y1) + d.y * math.sin(y1)
    across = -d.x * math.sin(y1) + d.y * math.cos(y1)

    plan = []
    for n in range(1, 6):
        passage_label = f"Passage {n + 1}"
        if passage_label not in starts:
            raise RuntimeError(f"{passage_label} not found")
        start, yaw = starts[passage_label]
        yr = math.radians(yaw)
        location = [start.x + along * math.cos(yr) - across * math.sin(yr),
                    start.y + along * math.sin(yr) + across * math.cos(yr),
                    start.z + d.z]
        plan.append({"label": f"Interaction {n} — Stalls Camera", "mouth_tag": f"InfinityStage.Mouth.P0{n + 1}",
                     "location": [round(v, 2) for v in location],
                     "rotation": [round(open_rot.pitch, 3), round(yaw + (open_rot.yaw - p1_yaw), 3), round(open_rot.roll, 3)]})
    report = {"pattern": {"along": round(along, 1), "across": round(across, 1), "rise": round(d.z, 1)},
              "lens": {"focal_mm": lens.get_editor_property("current_focal_length"),
                       "filmback": [lens.get_editor_property("filmback").get_editor_property("sensor_width"),
                                    lens.get_editor_property("filmback").get_editor_property("sensor_height")]},
              "plan": plan, "dirty_before": dirty()}
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                       "CodexCameraPilot", "place_transition_stalls.json")
    if DRY_RUN:
        with open(out, "w", encoding="utf-8") as handle:
            json.dump({"dry_run": True, **report}, handle, indent=2, ensure_ascii=False)
        unreal.log("PUSS_TRANSITION_STALLS_DRYRUN|%s" % json.dumps(plan, ensure_ascii=True))
        return

    # --- place ---------------------------------------------------------------
    for row in plan:
        loc = unreal.Vector(*row["location"])
        rot = unreal.Rotator(roll=row["rotation"][2], pitch=row["rotation"][0], yaw=row["rotation"][1])
        camera = actor_subsystem.spawn_actor_from_class(unreal.CineCameraActor, loc, rot)
        camera.set_actor_label(row["label"])
        camera.set_folder_path(FOLDER)
        camera.tags = [unreal.Name(STALLS_TAG), unreal.Name(row["mouth_tag"])]
        target = camera.get_cine_camera_component()
        for prop in ("filmback", "lens_settings", "focus_settings", "current_focal_length", "current_aperture"):
            target.set_editor_property(prop, lens.get_editor_property(prop))
        target.set_editor_property("camera_mesh_hidden_in_game", True)

    # --- save the map only, re-checking for transient actors in this same script
    actors = actor_subsystem.get_all_level_actors()
    if [a for a in actors if a.get_actor_label().startswith("ZZ_")]:
        raise RuntimeError("Refusing to save: ZZ_ actors present")
    saved = unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD)

    # --- read back -----------------------------------------------------------
    placed = [a for a in actors if a.actor_has_tag(STALLS_TAG)]
    problems = []
    if len(placed) != 5:
        problems.append(f"expected 5 stalls cameras, found {len(placed)}")
    for row in plan:
        match = [a for a in placed if a.get_actor_label() == row["label"]]
        if len(match) != 1:
            problems.append(f"{row['label']}: found {len(match)}")
            continue
        camera = match[0]
        loc = camera.get_actor_location()
        if (loc - unreal.Vector(*row["location"])).length() > 0.5:
            problems.append(f"{row['label']}: location {loc}")
        if not camera.actor_has_tag(row["mouth_tag"]):
            problems.append(f"{row['label']}: missing {row['mouth_tag']}")
        target = camera.get_cine_camera_component()
        if abs(target.get_editor_property("current_focal_length") - lens.get_editor_property("current_focal_length")) > 0.01:
            problems.append(f"{row['label']}: focal length")
        if not target.get_editor_property("camera_mesh_hidden_in_game"):
            problems.append(f"{row['label']}: body visible in game")
    del actors, placed
    report.update({"saved": saved, "problems": problems, "dirty_after": dirty()})
    with open(out, "w", encoding="utf-8") as handle:
        json.dump({"dry_run": False, **report}, handle, indent=2, ensure_ascii=False)
    if problems or not saved:
        raise RuntimeError(f"Placement read-back failed: saved={saved} {problems}")
    unreal.log("PUSS_TRANSITION_STALLS_PLACED|cameras=5|saved=%s|dirty_after=%s" % (saved, report["dirty_after"]))


main()
