"""Mouth lanterns (30 Sep; conductor-approved, reversible, additive): one front lantern per
transition mouth, Passages 02-06, so the show cloth that hangs there through the
Interaction is lit from the house side. Today every true pass at P02-P06 renders
black there.

One instrument, repeated in each mouth's own frame (the route's start transform:
+x into the passage, +y to its right, z up from the stage floor):
- a single spot (one source, so a shadow play later cast by a light function on it
  stays single), house side, LOW and RAKING rather than a frontal flood;
- behind the stalls camera's plane (x < -1400), so it is never in the stalls shot;
- warm 2800 K, steady, shadows on, aimed at the cloth's centre;
- intensity calibrated to the show's ACTUAL exposure: the unbound PPV pins EV100 -3
  at every mouth (no stalls camera overrides it), 16x the sensitivity of the EV100 1.0
  at which 6 lux on the dark velvet read well (R ~ 152) on 28 Sep. So about 0.37 lux
  at the cloth centre here is that same picture.
Every number is a parameter (LANTERN below, or MOUTH_LANTERN in globals). Gary is
away, so this is built to be cheap to change, not guessed as final.

Not done here, deliberately: the passages are not lit (arrive-dark is intended), and
no exposure is touched. PPVs that pin exposure at a mouth are reported, not changed.

Dry run (MOUTH_LANTERN_DRY_RUN): the plan and the PPV report, nothing written.
Apply: guards (world, no PIE, 0+0 dirty, no Sequencer, no ZZ_ actors), plain-number
revert record written BEFORE any change, level backup to
Backups/PreMouthLanterns-<ts>/, idempotent (tag RigAtmos.MouthLantern.P0N:
updated in place, never duplicated), read-back against the plan, level saved,
dirty 0+0 after. Revert: mouth_lanterns_revert.py. Lean: all work in main().
"""
import datetime
import json
import math
import os
import shutil

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "mouth_lanterns_record.json")
TAG = "RigAtmos.MouthLantern"
PASSAGES = ("02", "03", "04", "05", "06")
LANTERN = {
    "local_cm": (-1600.0, -1300.0, 300.0),   # 16 m back, 13 m to house left, 3 m up: low, raking (~39 deg)
    "aim_local_cm": (0.0, 0.0, 525.0),       # the cloth's centre on the curtain line (the portal posts, x 0)
    "candela": 210.0,                        # ~0.37 lux at the centre (cos 0.77 at 20.7 m) = 6 lux at EV 1, shown at EV -3
    "outer_deg": 30.0, "inner_deg": 16.0,
    "kelvin": 2800.0, "radius_cm": 4500.0, "shadows": True,
}
LANTERN.update(globals().get("MOUTH_LANTERN", {}))


def fail(msg):
    unreal.log_error("MOUTH_LANTERNS_STOPPED|" + msg)
    raise RuntimeError(msg)


def pose_for(frame):
    loc = frame.transform_location(unreal.Vector(*LANTERN["local_cm"]))
    aim = frame.transform_location(unreal.Vector(*LANTERN["aim_local_cm"]))
    d = aim - loc
    yaw = math.degrees(math.atan2(d.y, d.x))
    pitch = math.degrees(math.atan2(d.z, math.hypot(d.x, d.y)))
    return loc, unreal.Rotator(roll=0.0, pitch=pitch, yaw=yaw), d.length()


def main():
    dry = bool(globals().get("MOUTH_LANTERN_DRY_RUN"))
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
        fail("wrong world, or PIE")
    if unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
        fail("something is already dirty")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
        fail("Sequencer is open")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    if any(a.get_actor_label().startswith("ZZ_") for a in actors):
        fail("bench actors (ZZ_) in the level")
    structures = {a.get_actor_label()[-2:]: a for a in actors if isinstance(a, unreal.InfinityStageStructureActor)}
    existing = {}
    for a in actors:
        for t in a.get_editor_property("tags"):
            if str(t).startswith(TAG + ".P"):
                existing[str(t)[-3:]] = a
    ppvs = [a for a in actors if isinstance(a, unreal.PostProcessVolume)]
    plan, ppv_report = [], []
    for key in PASSAGES:
        s = structures[key]
        route = s.get_editor_property("passage").get_editor_property("route")
        frame = route.get_transform_at_distance_along_spline(0.0, unreal.SplineCoordinateSpace.WORLD, False)
        frame.scale3d = unreal.Vector(1.0, 1.0, 1.0)
        loc, rot, dist = pose_for(frame)
        cos_i = abs(LANTERN["local_cm"][0] - LANTERN["aim_local_cm"][0]) / dist
        plan.append({"passage": key, "label": f"S{key} Mouth Lantern", "loc": [loc.x, loc.y, loc.z],
                     "rot": [rot.roll, rot.pitch, rot.yaw], "throw_m": round(dist / 100.0, 2),
                     "lux_at_centre": round(LANTERN["candela"] * cos_i / (dist / 100.0) ** 2, 2),
                     "exists": ("P" + key) in existing})
        stalls = frame.transform_location(unreal.Vector(-1400.0, 0.0, 150.0))
        for v in ppvs:
            unbound = bool(v.get_editor_property("unbound"))
            o, e = v.get_actor_bounds(False)
            inside = unbound or (abs(stalls.x - o.x) <= e.x and abs(stalls.y - o.y) <= e.y and abs(stalls.z - o.z) <= e.z)
            if not inside:
                continue
            st = v.get_editor_property("settings")
            ppv_report.append({"passage": key, "ppv": v.get_actor_label(), "unbound": unbound,
                               "priority": v.get_editor_property("priority"), "enabled": bool(v.get_editor_property("enabled")),
                               "method_overridden": bool(st.get_editor_property("override_auto_exposure_method")),
                               "method": str(st.get_editor_property("auto_exposure_method")),
                               "min_ev": st.get_editor_property("auto_exposure_min_brightness") if st.get_editor_property("override_auto_exposure_min_brightness") else None,
                               "max_ev": st.get_editor_property("auto_exposure_max_brightness") if st.get_editor_property("override_auto_exposure_max_brightness") else None,
                               "bias": st.get_editor_property("auto_exposure_bias") if st.get_editor_property("override_auto_exposure_bias") else None})
    unreal.log(f"MOUTH_LANTERNS_PLAN|{json.dumps(plan)}")
    unreal.log(f"MOUTH_LANTERNS_PPV|{json.dumps(ppv_report)}")
    if dry:
        json.dump({"plan": plan, "ppv": ppv_report, "lantern": LANTERN}, open(os.path.join(HERE, "mouth_lanterns_plan.json"), "w"), indent=1)
        unreal.log("MOUTH_LANTERNS_DRY_RUN_OK|mutated=0")
        return

    before = {}
    for key, a in existing.items():
        c = a.get_component_by_class(unreal.SpotLightComponent)
        l, r = a.get_actor_location(), a.get_actor_rotation()
        before[a.get_actor_label()] = {"loc": [l.x, l.y, l.z], "rot": [r.roll, r.pitch, r.yaw], "cd": float(c.get_editor_property("intensity")),
                                       "outer": float(c.get_editor_property("outer_cone_angle")), "inner": float(c.get_editor_property("inner_cone_angle")),
                                       "k": float(c.get_editor_property("temperature")), "radius": float(c.get_editor_property("attenuation_radius")),
                                       "shadows": bool(c.get_editor_property("cast_shadows"))}
    created = [p["label"] for p in plan if not p["exists"]]
    old = json.load(open(RECORD, encoding="utf-8")) if os.path.exists(RECORD) else {}
    record = {"written": datetime.datetime.now().isoformat(timespec="seconds"),
              "created": sorted(set(old.get("created", [])) | set(created)), "updated_before": {**before, **old.get("updated_before", {})},
              "lantern": LANTERN}
    with open(RECORD, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1)
        fh.flush()
        os.fsync(fh.fileno())
    if json.load(open(RECORD, encoding="utf-8"))["created"] != record["created"]:
        fail("revert record did not read back")
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = os.path.join(project, "Backups", "PreMouthLanterns-" + datetime.datetime.now().strftime("%Y%m%d-%H%M"))
    os.makedirs(backup, exist_ok=True)
    umap = os.path.join(project, "Content", *EXPECTED_WORLD[len("/Game/"):].split("/")) + ".umap"
    shutil.copy2(umap, backup)
    shutil.copy2(RECORD, backup)

    for p in plan:
        a = existing.get("P" + p["passage"])
        if a is None:
            a = sub.spawn_actor_from_class(unreal.SpotLight, unreal.Vector(*p["loc"]), unreal.Rotator(*p["rot"]))
            a.set_actor_label(p["label"])
            a.set_editor_property("tags", [unreal.Name(TAG), unreal.Name(f"{TAG}.P{p['passage']}")])
        a.modify()
        a.set_actor_location(unreal.Vector(*p["loc"]), False, True)
        a.set_actor_rotation(unreal.Rotator(roll=p["rot"][0], pitch=p["rot"][1], yaw=p["rot"][2]), True)
        c = a.get_component_by_class(unreal.SpotLightComponent)
        c.set_mobility(unreal.ComponentMobility.MOVABLE)
        c.set_editor_property("intensity_units", unreal.LightUnits.CANDELAS)
        c.set_editor_property("intensity", LANTERN["candela"])
        c.set_editor_property("outer_cone_angle", LANTERN["outer_deg"])
        c.set_editor_property("inner_cone_angle", LANTERN["inner_deg"])
        c.set_editor_property("use_temperature", True)
        c.set_editor_property("temperature", LANTERN["kelvin"])
        c.set_editor_property("attenuation_radius", LANTERN["radius_cm"])
        c.set_editor_property("cast_shadows", LANTERN["shadows"])

    worst = 0.0
    for p in plan:
        a = next(x for x in sub.get_all_level_actors() if x.get_actor_label() == p["label"])
        l, r = a.get_actor_location(), a.get_actor_rotation()
        worst = max(worst, abs(l.x - p["loc"][0]), abs(l.y - p["loc"][1]), abs(l.z - p["loc"][2]))
        dyaw = (r.yaw - p["rot"][2] + 180.0) % 360.0 - 180.0
        if abs(dyaw) > 0.05 or abs(r.pitch - p["rot"][1]) > 0.05:
            fail(f"{p['label']} rotation did not land: {r}")
        c = a.get_component_by_class(unreal.SpotLightComponent)
        if abs(c.get_editor_property("intensity") - LANTERN["candela"]) > 0.5:
            fail(f"{p['label']} intensity did not land")
    if worst > 0.5:
        fail(f"a lantern landed {worst:.2f} cm off its plan")
    dirty_c = [x.get_path_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    if dirty_c:
        fail(f"content dirtied: {dirty_c}")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed")
    after = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()), len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
    unreal.log(f"MOUTH_LANTERNS_OK|lanterns={len(plan)}|created={len(created)}|worst_cm={worst:.3f}|backup={backup}|dirty_after={after[0]}+{after[1]}")


main()
