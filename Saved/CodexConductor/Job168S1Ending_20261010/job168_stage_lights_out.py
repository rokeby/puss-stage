"""Job 168 stage B: reuse the reviewed Job 29 S1 rig-fade implementation.

The legacy implementation is executed as definitions only.  Its artifact root
is redirected here and its Master-clock mapper is replaced with a live section
read that targets the S1-local frame from Job 168.  No stale absolute Master
time is trusted.
"""
import os

import unreal


HERE = os.path.dirname(os.path.abspath(__file__))
LEGACY = os.path.normpath(os.path.join(HERE, "..", "S1RigFade_20261009", "s1_rig_fade.py"))
TAIL = "\nif unreal is not None:\n    main()"


def _asset_path(value):
    return "" if value is None else value.get_path_name().split(".", 1)[0]


def _load_legacy():
    with open(LEGACY, "r", encoding="utf-8") as handle:
        source = handle.read().rstrip()
    if not source.endswith(TAIL.strip()):
        raise RuntimeError("LEGACY_SHAPE_CHANGED")
    source = source[:-len(TAIL.strip())]
    namespace = {"__name__": "job168_s1_rig_fade_definitions", "__file__": LEGACY}
    exec(compile(source, LEGACY, "exec"), namespace)
    required = ("normalise_params", "run_dry", "run_apply", "run_revert")
    if any(name not in namespace for name in required):
        raise RuntimeError("LEGACY_HELPERS_MISSING")
    namespace["_here"] = lambda: HERE

    def live_local_clock(params, run):
        master = unreal.load_asset(params["master_sequence"])
        hits = []
        for track in master.get_tracks():
            for section in track.get_sections():
                try:
                    if _asset_path(section.get_sequence()) == namespace["SEQ_PATH"]:
                        hits.append(section)
                except Exception:
                    pass
        if len(hits) != 1:
            namespace["_stop"](run, "MASTER_S1_SECTION_COUNT|%d" % len(hits))
        section = hits[0]
        start = float(section.get_start_frame_seconds())
        end = float(section.get_end_frame_seconds())
        frame = int(params["expected_target_scene_frame"])
        review = start + frame / float(namespace["EXPECTED_FPS"])
        mapping = namespace["map_master_time"](review, start, namespace["EXPECTED_FPS"], end)
        mapping.update({"master_sequence": params["master_sequence"],
                        "scene_sequence": namespace["SEQ_PATH"],
                        "job168_local_frame_authority": True})
        return mapping

    namespace["_master_clock"] = live_local_clock
    return namespace


def _params(args):
    end = int(round(int(args["lights_out_start_frame"]) +
                    float(args["lights_out_fade_seconds"]) * 25.0))
    return {
        "review_time_seconds": 0.0,
        "master_sequence": "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master",
        "expected_master_section_start_seconds": 0.0,
        "expected_target_scene_frame": end,
        "scene_local_switch_frame": 282,
        "search_radius_frames": 20,
        "fade_seconds": float(args["lights_out_fade_seconds"]),
        "min_fade_seconds": 1.0,
        "max_fade_seconds": 2.0,
        "value_tolerance": 0.0001,
        "bulb_prefix": "S1 Lattice Bulb ",
        "glow_prefix": "S1 Lattice Glow ",
    }


def run(args):
    namespace = _load_legacy()
    mode = str(args["mode"]).upper()
    params = namespace["normalise_params"](_params(args))
    expected_start = int(args["lights_out_start_frame"])
    if params["expected_target_scene_frame"] - params["fade_frames"] != expected_start:
        raise RuntimeError("LIGHTS_OUT_START_ROUNDING")
    confirm = "%s S1RIGFADE" % mode
    result = {"DRY": namespace["run_dry"], "APPLY": namespace["run_apply"],
              "REVERT": namespace["run_revert"]}[mode](args["run_id"], params, confirm)
    unreal.log("JOB168_LIGHTS_OUT_%s_OK|run=%s|start=%d|end=%d|legacy=Job29-S1RigFade" %
               (mode, args["run_id"], expected_start, params["expected_target_scene_frame"]))
    return result
