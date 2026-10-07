"""READ-ONLY PIE probe (7 Oct): why S4 wide shots show open sky / water horizon.

Runs inside the conductor's OWN running PIE. Writes nothing to any asset, level or actor. Never ends PIE, never
saves, never calls Arrival.EvaluateAtMasterFrame / ApplyInitialTransformPose (both write), never calls
GetBoundObjects. One optional transport scrub (args "scrub_s4_frame", default null = read where PIE stands).

Hypothesis under test (ranked first offline): LS_DevScene_04's "Hangar Fold" sub-section plays LS_S4_HangarRise
only over S4 [0, 775) (the old 31 s Scene); S4 was relengthed to 4890 frames (eca8a5d). Past 775 nothing holds the
hangar landed, and in game the Arrival's ApplyInitialTransformPose REST pose (root pitch -90, sunk) is what remains
or is restored -> her L_KK_children sky (SM_SkySphere / SkyAtmosphere / VolumetricCloud, celestial-EXEMPT) shows.

Reads, all into Saved/CodexConductor/probe_s4_sky_pie_<run>.json, marker S4SKYPIE|run=<run>|...:
  1. Master frame -> S4 frame (segment start 28482625, 960 ticks/frame, measured from PSTILLS manifest).
  2. Every 'S4 Hangar*' actor: world loc/rot, bounds, hidden-in-game, root visible; the Arrival's driven root and
     its rotation (REST = pitch -90).
  3. Every sky/atmosphere/cloud/skylight/sun/fog component and every SkySphere/huge mesh: level, visible, hidden.
  4. The view camera (PlayerCameraManager) vs the LANDED box interior (dock 10668.47,240000; x 500..6500,
     |y|<=1400, z 0..3000 local).
  5. A 5x3 grid of visibility line traces from the camera through its frustum (what each ray hits; NO_HIT = sky).
  6. The asset side: Hangar Fold section range + completion mode; S4 playback end; LS_S4_HangarRise transform
     sections' ranges + completion modes; rise playback end.
"""
import datetime
import json
import math
import os

import unreal

ARGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "probe_s4_sky_pie_args.json")
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_04"
RISE = "/Game/InfinityStage/RigAtmos/LS_S4_HangarRise"
SEG_START = 28482625          # measured: PSTILLS-S4-20261007-135123 manifest segment.start
TICKS_PER_FRAME = 960          # (33177025 - 28482625) / 4890
DOCK = (10668.4695, 240000.0, 0.0)
BOX = {"x": (500.0, 6500.0), "y": (-1400.0, 1400.0), "z": (0.0, 3000.0)}
SKY_CLASSES = ("SkyAtmosphereComponent", "VolumetricCloudComponent", "SkyLightComponent",
               "DirectionalLightComponent", "ExponentialHeightFogComponent")


def v3(v):
    return [round(float(v.x), 1), round(float(v.y), 1), round(float(v.z), 1)]


def r3(r):
    return {"pitch": round(float(r.pitch), 2), "yaw": round(float(r.yaw), 2), "roll": round(float(r.roll), 2)}


def fval(x):
    return int(x.value if hasattr(x, "value") else x)


def level_of(a):
    try:
        return str(a.get_level().get_outermost().get_name())
    except Exception as exc:  # noqa: BLE001
        return "?%s" % exc


def label(a):
    try:
        return str(a.get_actor_label())
    except Exception:  # noqa: BLE001
        return str(a.get_name())


def hidden(a):
    try:
        return bool(a.get_editor_property("hidden"))
    except Exception as exc:  # noqa: BLE001
        return "?%s" % exc


def local(p):
    return [p[0] - DOCK[0], p[1] - DOCK[1], p[2] - DOCK[2]]


def inside_box(lp):
    return all(BOX[k][0] <= lp[i] <= BOX[k][1] for i, k in enumerate("xyz"))


def hit_of(res):
    if res is None:
        return None
    if isinstance(res, tuple):  # (bool, HitResult) or HitResult.to_tuple()
        for item in res:
            if isinstance(item, unreal.HitResult):
                return hit_of(item)
        return None
    try:
        t = res.to_tuple()
    except Exception:  # noqa: BLE001
        return None
    blocking = bool(t[0])
    act = next((x for x in t if isinstance(x, unreal.Actor)), None)
    dist = float(t[3]) if len(t) > 3 else None
    if not blocking or act is None:
        return None
    return {"actor": label(act), "level": level_of(act), "dist": round(dist, 0) if dist is not None else None}


def asset_side(out):
    seq = unreal.load_asset(SCENE)
    rise = unreal.load_asset(RISE)
    assert seq is not None and rise is not None, "S4SKYPIE_ASSET_MISSING"
    out["scene_playback"] = [int(seq.get_playback_start()), int(seq.get_playback_end())]
    folds = []
    for t in seq.get_tracks():
        if not isinstance(t, unreal.MovieSceneSubTrack):
            continue
        for s in t.get_sections():
            sub = s.get_sequence()
            if sub is None or "HangarRise" not in sub.get_path_name():
                continue
            folds.append({"track": str(t.get_display_name()), "range": [s.get_start_frame(), s.get_end_frame()],
                          "active": bool(s.is_active()), "completion": str(s.get_completion_mode())})
    out["hangar_fold_sections"] = folds
    out["rise_playback"] = [int(rise.get_playback_start()), int(rise.get_playback_end())]
    rows = []
    for b in rise.get_bindings():
        for t in b.get_tracks():
            if not isinstance(t, unreal.MovieScene3DTransformTrack):
                continue
            for s in t.get_sections():
                rows.append({"binding": str(b.get_display_name()),
                             "start": s.get_start_frame() if s.has_start_frame() else "-inf",
                             "end": s.get_end_frame() if s.has_end_frame() else "+inf",
                             "completion": str(s.get_completion_mode())})
    out["rise_transform_sections"] = rows


def main():
    run = "S4SKYPIE-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    args = {}
    if os.path.exists(ARGS):
        with open(ARGS, encoding="utf-8") as fh:
            args = json.load(fh)
    out = {"run": run, "args": args, "errors": []}
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if world is None:
        unreal.log_error("S4SKYPIE|run=%s|NO_PIE (start PIE first; this probe never starts or ends it)" % run)
        return
    roots = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot))
    assert len(roots) == 1, "S4SKYPIE_SHOW_ROOTS=%d" % len(roots)
    root = roots[0]
    if args.get("scrub_s4_frame") is not None:
        target = SEG_START + int(args["scrub_s4_frame"]) * TICKS_PER_FRAME
        out["scrub"] = {"target_master": target,
                        "result": str(root.transport.scrub_to_master_frame(unreal.FrameNumber(target)))}
    master = fval(root.transport.get_current_master_frame())
    out["master_frame"] = master
    out["s4_frame"] = round((master - SEG_START) / float(TICKS_PER_FRAME), 2)

    actors = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))
    # 2. hangar
    hang = []
    for a in actors:
        lab = label(a)
        if not lab.startswith("S4 Hangar"):
            continue
        o, e = a.get_actor_bounds(False)
        rc = a.get_editor_property("root_component")
        hang.append({"label": lab, "loc": v3(a.get_actor_location()), "rot": r3(a.get_actor_rotation()),
                     "bounds_c_local": [round(x, 0) for x in local(v3(o))], "ext": v3(e), "hidden": hidden(a),
                     "root_visible": bool(rc.is_visible()) if rc else None})
    out["hangar"] = sorted(hang, key=lambda r: r["label"])
    arr = []
    for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageArrival):
        ms = str(a.get_editor_property("motion_sequence"))
        if "S4_HangarRise" not in ms:
            continue
        d = a.get_editor_property("driven_actor")
        arr.append({"arrival": label(a), "motion": ms, "driven": label(d) if d else None,
                    "driven_rot": r3(d.get_actor_rotation()) if d else None,
                    "driven_loc": v3(d.get_actor_location()) if d else None,
                    "rest_pose_pitch_m90": bool(d and abs(float(d.get_actor_rotation().pitch) + 90.0) < 1.0)})
    out["arrival_s4"] = arr
    walls = [h for h in hang if any(k in h["label"] for k in ("Left Wall", "Right Wall", "Far Wall", "Roof"))
             and "Hinge" not in h["label"]]
    out["walls_landed"] = {h["label"]: (h["bounds_c_local"][2] > 0 and h["bounds_c_local"][0] > 400) for h in walls}

    # 3. sky
    sky = []
    for a in actors:
        lab = label(a)
        for c in a.get_components_by_class(unreal.ActorComponent):
            cls = c.get_class().get_name()
            mesh_sky = cls == "StaticMeshComponent" and ("sky" in lab.lower() or "sphere" in lab.lower())
            if cls in SKY_CLASSES or mesh_sky or (cls == "StaticMeshComponent" and "L_KK_children" in level_of(a)
                                                   and max(v3(a.get_actor_bounds(False)[1])) > 20000):
                row = {"level": level_of(a).split("/")[-1], "actor": lab[:48], "cls": cls,
                       "visible": bool(c.is_visible()), "actor_hidden": hidden(a)}
                try:
                    row["intensity"] = round(float(c.get_editor_property("intensity")), 3)
                except Exception:  # noqa: BLE001
                    pass
                sky.append(row)
    out["sky"] = sky
    out["sky_visible"] = [r for r in sky if r["visible"] and r["actor_hidden"] is False]

    # 4. camera
    pc = unreal.GameplayStatics.get_player_controller(world, 0)
    pcm = unreal.GameplayStatics.get_player_camera_manager(world, 0)
    cl, cr = pcm.get_camera_location(), pcm.get_camera_rotation()
    fov = float(pcm.get_fov_angle())
    vt = pc.get_view_target() if pc else None
    lp = local(v3(cl))
    out["camera"] = {"view_target": label(vt) if vt else None, "loc": v3(cl), "rot": r3(cr), "fov": round(fov, 2),
                     "local": [round(x, 0) for x in lp], "inside_landed_box": inside_box(lp),
                     "in_front_of_mouth_cm": round(BOX["x"][0] - lp[0], 0) if lp[0] < BOX["x"][0] else 0}

    # 5. frustum rays
    rays = []
    vfov = math.degrees(2 * math.atan(math.tan(math.radians(fov / 2)) * 9.0 / 16.0))
    for j, dv in enumerate((-0.45, 0.0, 0.45)):
        for i, dh in enumerate((-0.45, -0.2, 0.0, 0.2, 0.45)):
            rot = unreal.Rotator(pitch=cr.pitch + dv * vfov, yaw=cr.yaw + dh * fov, roll=0.0)
            end = cl + rot.get_forward_vector() * 200000.0
            try:
                res = unreal.SystemLibrary.line_trace_single(world, cl, end, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
                                                             True, [], unreal.DrawDebugTrace.NONE, True)
                h = hit_of(res)
            except Exception as exc:  # noqa: BLE001
                h = "TRACE_ERR %s" % exc
            rays.append({"row": j, "col": i, "hit": h if h else "NO_HIT"})
    out["rays"] = rays
    out["rays_no_hit"] = sum(1 for r in rays if r["hit"] == "NO_HIT")

    # 6. assets
    try:
        asset_side(out)
    except Exception as exc:  # noqa: BLE001
        out["errors"].append("ASSET_SIDE %s" % exc)

    path = os.path.join(OUT_DIR, "probe_s4_sky_pie_%s.json" % run)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=str)
    unreal.log("S4SKYPIE|run=%s|s4_frame=%s|cam_inside=%s|walls_landed=%s|rest_pose=%s|rays_no_hit=%d/15|"
               "fold=%s|errors=%d|OK|%s"
               % (run, out["s4_frame"], out["camera"]["inside_landed_box"],
                  all(out["walls_landed"].values()) if out["walls_landed"] else None,
                  [x["rest_pose_pitch_m90"] for x in arr], out["rays_no_hit"],
                  out.get("hangar_fold_sections"), len(out["errors"]), path))


main()
