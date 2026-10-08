"""P6 ANIMATED GOBO editor tool (offline-authored; NEVER RUN IN UNREAL).

Assets:
  * shared, created on first use and REUSED after structural validation:
      M_ShadowGobo_LightFunction (Light Function domain, atlas compatible)
      MPC_ShadowGobo (Sequencer-keyed scalar ``Frame``)
  * per run, create-only: one imported grayscale atlas texture and one MI

Sequence edit:
  * assign the MI to exactly named SpotLight spawnable template(s)
  * add one MPC track and linearly key Frame over [frame_start, frame_end]

Modes: DRY, APPLY, VERIFY, REVERT.  APPLY deliberately ends PENDING_VERIFY:
material/import values read in the build call are not independent proof.  A later
VERIFY call reloads and reads the named packages and emits ANIMATED_GOBO_SUCCESS.
REVERT restores previous light functions, removes the tool-owned track, backs up
the packages, then deletes only the assets THAT run created.

Every run has its own plan and record (keyed by run_id), so the tool can be used
once per Interaction.  VERIFY and REVERT name the APPLY run with ``apply_run``.
Revert runs in reverse order: the run that created the shared master/MPC is refused
while later runs' MIs still reference them.

Fixed 8 Oct (review of 48d30b1):
  * UE 5.8 has no master-track API; uses get_tracks/add_track/remove_track
    [decl] MovieSceneSequenceExtensions.h:49,79,89.
  * add_scalar_parameter_key takes a raw FFrameNumber [decl]
    MovieSceneParameterSection.h:346, which is tick resolution [inf]; keys are
    converted from display frames, and read back in display frames
    [decl] MovieSceneScriptingChannel.h:30 (GetTime defaults to DisplayRate).
  * the end key is Frames (not Frames-1), so every cell gets an equal share; the
    shader clamps to the last cell.

Safety: refuses PIE/SIE, an open Sequencer, a wrong world, any pre-existing dirty
package, duplicate/missing labels, existing per-run targets, an invalid shared
asset, an existing owned track, or a stale DRY digest.  It writes a sequence
backup and exclusive record before mutation, saves only named packages, and never
calls Save All or deletes material expressions.

Tiers used below: [decl] engine header/shader; [prec] repository precedent;
[inf] offline-authored call that the conductor must first exercise with DRY.
"""
from __future__ import annotations

import copy
import datetime
import fractions
import hashlib
import json
import os
import re
import shutil

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # Offline harness.
    unreal = None


MARK = "ANIMATED_GOBO"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ASSET_ROOT = "/Game/InfinityStage/Lighting/Gobo"
MASTER = ASSET_ROOT + "/M_ShadowGobo_LightFunction"
MPC = ASSET_ROOT + "/MPC_ShadowGobo"
SHARED_ASSETS = (MASTER, MPC)
TRACK_NAME = "ShadowGobo Frame (Conductor)"
FRAME_PARAMETER = "Frame"
TEXTURE_PARAMETER = "FlipbookAtlas"
ARGS_NAME = "animated_gobo_args.json"
PLANS_DIR = "animated_gobo_plans"
RECORDS_DIR = "animated_gobo_records"
MODES = ("DRY", "APPLY", "VERIFY", "REVERT")
FLOAT_TOL = 1.0e-4
RUN_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
# Scripting channel names can carry a numeric suffix (Location.Y_183) [prec] memory ue58-sequencer-read-traps.
FRAME_CHANNEL_RE = re.compile(r"^%s(_\d+)?$" % FRAME_PARAMETER)
SPEED_WARN = 0.02

SCALAR_DEFAULTS = {
    "Cols": 6.0,
    "Rows": 4.0,
    "Frames": 24.0,
    "GutterUV": 8.0 / 341.0,
    "CellUV": 341.0 / 2048.0,
    "BlurUV": 0.00075,
    "Softness": 0.08,
    "Contrast": 1.35,
    "Depth": 1.0,
    "Scale": 1.0,
    "FlipU": 0.0,
    "FlipV": 0.0,
}

CODE_UV = """// Row-major atlas UV. Frame comes from Sequencer's MPC track.
float count = max(1.0, Frames);
float f = floor(clamp(Frame, 0.0, count - 1.0) + 1e-4);
float col = fmod(f, max(1.0, Cols));
float row = floor(f / max(1.0, Cols));
float2 p = (UV - 0.5) / max(Scale, 1e-4) + 0.5;
p = lerp(p, 1.0 - p, saturate(float2(FlipU, FlipV)));
float2 safe = saturate(p) * (1.0 - 2.0 * GutterUV) + GutterUV;
return (float2(col, row) + safe) * CellUV;
"""

CODE_EDGE = """// Softness is an edge transition, not an optical convolution.
float w = max(1e-4, Softness);
float shaped = smoothstep(0.5 - w, 0.5 + w, Mask);
shaped = saturate((shaped - 0.5) * max(0.0, Contrast) + 0.5);
return lerp(1.0, shaped, saturate(Depth));
"""

CODE_AVG = """// Five-tap cross blur; BlurUV offsets are clamped inside the 8 px source gutter.
return (C + L + R + U + D) * 0.2;
"""


class PlanError(ValueError):
    pass


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _asset_path(value: str) -> str:
    return str(value).split(".", 1)[0]


def _path_of(obj):
    return _asset_path(str(obj.get_path_name())) if obj is not None else None


def _load_json(path):
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path, value, exclusive=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | (os.O_EXCL if exclusive else os.O_TRUNC)
    fd = os.open(path, flags)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def plan_file(here, run):
    return os.path.join(here, PLANS_DIR, "%s.json" % run)


def record_file(here, run):
    return os.path.join(here, RECORDS_DIR, "%s.json" % run)


def confirm_text(mode: str) -> str:
    if mode == "REVERT":
        return "REVERT ANIMATED_GOBO DELETE CREATED ASSETS"
    return "%s ANIMATED_GOBO" % mode


def confirm_ok(mode: str, value) -> bool:
    return str(value or "") == confirm_text(mode)


def ticks_per_display_frame(tick_num, tick_den, disp_num, disp_den) -> int:
    """Exact ticks per display frame; refuses a non-integer ratio rather than rounding keys."""
    if min(tick_num, tick_den, disp_num, disp_den) <= 0:
        raise PlanError("FRAME_RATE|non-positive|%s/%s %s/%s" % (tick_num, tick_den, disp_num, disp_den))
    ratio = fractions.Fraction(int(tick_num) * int(disp_den), int(tick_den) * int(disp_num))
    if ratio.denominator != 1:
        raise PlanError("TICKS_PER_FRAME_NOT_INTEGER|%s" % ratio)
    return int(ratio)


def channel_is_frame(name) -> bool:
    return bool(FRAME_CHANNEL_RE.match(str(name)))


def created_assets_for(plan: dict, existing_shared) -> list:
    """Shared assets are created only when absent; per-run assets are always created."""
    existing = set(existing_shared)
    return [p for p in SHARED_ASSETS if p not in existing] + [plan["texture"], plan["mi"]]


def timing_report(plan: dict, display_fps: float) -> dict:
    """Compare the keyed range with the flipbook's own frame rate (report only; never refuses)."""
    start, end = plan["sequence_range_requested"]
    frames, fps = plan["atlas"]["frames"], plan.get("take_fps")
    out = {"display_fps": display_fps, "requested_frames": end - start,
           "display_frames_per_cell": (end - start) / float(frames)}
    if fps:
        native = frames / float(fps) * display_fps
        out.update({"take_fps": fps, "native_frames": native,
                    "native_frame_end": start + int(round(native)),
                    "speed_vs_take": native / float(end - start)})
    return out


def shared_asset_problems(desc: dict) -> list:
    """Validate an existing master/MPC before reuse.  ``desc`` is read live; pure so the harness can drive it."""
    out = []
    master, mpc = desc.get("master"), desc.get("mpc")
    if master is not None:
        if not master.get("domain_ok"):
            out.append("MASTER_DOMAIN")
        if not master.get("atlas_compat"):
            out.append("MASTER_ATLAS_COMPAT")
        if sorted(master.get("scalars") or []) != sorted(SCALAR_DEFAULTS):
            out.append("MASTER_SCALARS|%s" % sorted(master.get("scalars") or []))
        if sorted(master.get("textures") or []) != [TEXTURE_PARAMETER]:
            out.append("MASTER_TEXTURES|%s" % sorted(master.get("textures") or []))
    if mpc is not None and FRAME_PARAMETER not in (mpc.get("scalars") or []):
        out.append("MPC_FRAME")
    if master is not None and mpc is None:
        out.append("MASTER_WITHOUT_MPC|master must read %s" % MPC)
    if master is not None and mpc is not None and MASTER not in (desc.get("mpc_referencers") or []):
        out.append("MASTER_NOT_ON_MPC|%s" % desc.get("mpc_referencers"))
    return out


def normalized_args(raw: dict) -> dict:
    allowed = {
        "mode", "confirm", "run_id", "apply_run", "world", "sequence", "light_label", "light_labels",
        "atlas_png", "manifest", "mi_path", "texture_path", "frame_start", "frame_end", "params",
    }
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise PlanError("UNKNOWN_ARGS|%s" % unknown)
    mode = str(raw.get("mode", "DRY")).upper()
    if mode not in MODES:
        raise PlanError("MODE|%s" % mode)
    run_id = str(raw.get("run_id") or "")
    if not RUN_ID_RE.match(run_id):
        raise PlanError("RUN_ID|need explicit [A-Za-z0-9_-]{1,64}; DRY and APPLY share it|%r" % run_id)
    apply_run = raw.get("apply_run")
    if mode in ("VERIFY", "REVERT"):
        if not RUN_ID_RE.match(str(apply_run or "")):
            raise PlanError("APPLY_RUN|%s needs apply_run = the APPLY run_id|%r" % (mode, apply_run))
        if str(apply_run) == run_id:
            raise PlanError("APPLY_RUN|%s needs its own run_id, not the APPLY one" % mode)
    labels = raw.get("light_labels")
    if labels is None:
        labels = [raw.get("light_label")] if raw.get("light_label") else []
    labels = [str(v).strip() for v in labels]
    if not labels or any(not v for v in labels) or len(labels) != len(set(labels)):
        raise PlanError("LIGHT_LABELS|need unique non-empty label(s)")
    sequence = _asset_path(str(raw.get("sequence", "")))
    mi_path = _asset_path(str(raw.get("mi_path", "")))
    texture_path = _asset_path(str(raw.get("texture_path", "")))
    if not sequence.startswith("/Game/"):
        raise PlanError("SEQUENCE_PATH|%s" % sequence)
    if not mi_path.startswith(ASSET_ROOT + "/MI_"):
        raise PlanError("MI_PATH|must be create-only under %s and start MI_|%s" % (ASSET_ROOT, mi_path))
    if not texture_path.startswith(ASSET_ROOT + "/T_"):
        raise PlanError("TEXTURE_PATH|must be create-only under %s and start T_|%s" % (ASSET_ROOT, texture_path))
    start, end = int(raw.get("frame_start", -1)), int(raw.get("frame_end", -1))
    if start < 0 or end <= start:
        raise PlanError("FRAME_RANGE|need 0 <= start < end|%d,%d" % (start, end))
    atlas_png, manifest = os.path.abspath(str(raw.get("atlas_png", ""))), os.path.abspath(str(raw.get("manifest", "")))
    if not os.path.isfile(atlas_png):
        raise PlanError("ATLAS_MISSING|%s" % atlas_png)
    if not os.path.isfile(manifest):
        raise PlanError("MANIFEST_MISSING|%s" % manifest)
    params = dict(raw.get("params") or {})
    unknown_params = sorted(set(params) - set(SCALAR_DEFAULTS))
    if unknown_params:
        raise PlanError("UNKNOWN_PARAMS|%s" % unknown_params)
    return {
        "mode": mode, "confirm": raw.get("confirm"), "run_id": run_id,
        "apply_run": str(apply_run) if apply_run else None,
        "world": _asset_path(str(raw.get("world", EXPECTED_WORLD))), "sequence": sequence,
        "light_labels": labels, "atlas_png": atlas_png, "manifest": manifest,
        "mi_path": mi_path, "texture_path": texture_path, "frame_start": start, "frame_end": end,
        "params": params,
    }


def plan_from_args(args: dict) -> dict:
    manifest = _load_json(args["manifest"])
    if not isinstance(manifest, dict):
        raise PlanError("MANIFEST_JSON")
    atlas = manifest.get("atlas") or {}
    take = manifest.get("take") or {}
    supplied = manifest.get("light_function_params") or {}
    aliases = {"Cols": "GoboCols", "Rows": "GoboRows", "Frames": "GoboFrames",
               "GutterUV": "GoboGutterUV", "CellUV": "GoboCellUV"}

    def supplied_value(name, default=0):
        return supplied.get(name, supplied.get(aliases.get(name, ""), default))

    frames = int(take.get("frames_packed", supplied_value("Frames")))
    cols, rows = int(atlas.get("cols", supplied_value("Cols"))), int(atlas.get("rows", supplied_value("Rows")))
    px = list(atlas.get("px") or [])
    if frames < 2 or cols < 1 or rows < 1 or frames > cols * rows:
        raise PlanError("MANIFEST_GRID|frames=%d grid=%dx%d" % (frames, cols, rows))
    if len(px) != 2 or px[0] != px[1] or px[0] not in (1024, 2048, 4096, 8192):
        raise PlanError("ATLAS_SIZE|need square power-of-two 1024..8192|%r" % px)
    if os.path.basename(args["atlas_png"]) != str(atlas.get("file")):
        raise PlanError("ATLAS_FILENAME|%s vs %s" % (os.path.basename(args["atlas_png"]), atlas.get("file")))
    with open(args["atlas_png"], "rb") as handle:
        atlas_sha = hashlib.sha256(handle.read()).hexdigest()
    if manifest.get("sha256") and atlas_sha != manifest["sha256"]:
        raise PlanError("ATLAS_SHA256")
    params = dict(SCALAR_DEFAULTS)
    params.update({k: float(supplied_value(k, params[k])) for k in params if k in supplied or aliases.get(k) in supplied})
    params.update({k: float(v) for k, v in args["params"].items()})
    params.update({"Cols": float(cols), "Rows": float(rows), "Frames": float(frames)})
    if not (0.0 <= params["BlurUV"] <= 0.003 and 0.0 <= params["Softness"] <= 0.49 and params["Contrast"] >= 0.0 and
            0.0 <= params["Depth"] <= 1.0 and params["Scale"] > 0.0):
        raise PlanError("LOOK_PARAMS|blur 0..0.003, softness 0..0.49, contrast >=0, depth 0..1, scale >0")
    gutter_px = int(atlas.get("gutter_px", 0))
    # The blur taps step BlurUV in ATLAS uv; past the gutter they read the neighbouring frame.
    if gutter_px > 0 and params["BlurUV"] > gutter_px / float(px[0]):
        raise PlanError("LOOK_PARAMS|BlurUV %.5f exceeds the %d px gutter (%.5f atlas uv)" %
                        (params["BlurUV"], gutter_px, gutter_px / float(px[0])))
    fps = take.get("fps")
    plan = {
        "schema_version": 2, "run": args["run_id"], "world": args["world"], "sequence": args["sequence"],
        "light_labels": list(args["light_labels"]), "atlas_png": args["atlas_png"],
        "atlas_sha256": atlas_sha, "manifest": args["manifest"],
        "shared_assets": list(SHARED_ASSETS), "own_assets": [args["texture_path"], args["mi_path"]],
        "master": MASTER, "mpc": MPC, "mi": args["mi_path"], "texture": args["texture_path"],
        "frame_parameter": FRAME_PARAMETER,
        # Display frames.  End value = Frames so each cell holds (end-start)/Frames frames; the shader clamps.
        "frame_keys": [[args["frame_start"], 0.0], [args["frame_end"], float(frames)]],
        "sequence_range_requested": [args["frame_start"], args["frame_end"]], "params": params,
        "take_fps": float(fps) if fps else None,
        "atlas": {"px": px, "cols": cols, "rows": rows, "frames": frames,
                  "cell_px": int(atlas.get("cell_px", 0)), "gutter_px": int(atlas.get("gutter_px", 0))},
    }
    plan["digest"] = _digest(plan)
    return plan


def preflight_refusals(mode: str, args: dict, state: dict, plan=None) -> list[str]:
    out = []
    if not confirm_ok(mode, args.get("confirm")):
        out.append("CONFIRM_MISMATCH|want %r" % confirm_text(mode))
    if state.get("pie"):
        out.append("PIE_OR_SIE_ACTIVE")
    if state.get("sequencer_open"):
        out.append("SEQUENCER_IS_OPEN")
    if not state.get("world_ok"):
        out.append("WRONG_WORLD")
    if state.get("census") != {"content": [], "maps": []}:
        out.append("DIRTY_CENSUS|%s" % state.get("census"))
    if mode in ("DRY", "APPLY"):
        counts = state.get("label_counts") or {}
        for label in args.get("light_labels", []):
            if counts.get(label) != 1:
                out.append("LIGHT_LABEL_COUNT|%s|%s" % (label, counts.get(label, 0)))
        if state.get("record_exists"):
            out.append("RECORD_EXISTS|run=%s" % args.get("run_id"))
        existing = sorted(state.get("existing_own") or [])
        if existing:
            out.append("CREATE_ONLY_TARGET_EXISTS|%s" % existing)
        shared_problems = list(state.get("shared_problems") or [])
        if shared_problems:
            out.append("SHARED_ASSET_INVALID|%s" % shared_problems)
        if state.get("owned_track_count"):
            out.append("OWNED_TRACK_EXISTS|%d|one gobo track per sequence" % state["owned_track_count"])
        if not state.get("ticks_per_frame"):
            out.append("TICK_RATE|%s" % state.get("rate_error"))
        playback = state.get("playback") or [0, -1]
        # Playback end treated as exclusive [inf]; keys must sit strictly inside it.
        if plan and (plan["frame_keys"][0][0] < playback[0] or plan["frame_keys"][-1][0] >= playback[1]):
            out.append("KEYS_OUTSIDE_PLAYBACK|keys=%s playback=%s" % (plan["sequence_range_requested"], playback))
    elif mode == "VERIFY":
        if not state.get("record_exists"):
            out.append("NOTHING_TO_VERIFY")
    elif mode == "REVERT":
        if not state.get("record_exists"):
            out.append("NOTHING_TO_REVERT")
    return out


def apply_model(before: dict, plan: dict) -> dict:
    after = copy.deepcopy(before)
    after["track"] = {"name": TRACK_NAME, "mpc": MPC, "parameter": FRAME_PARAMETER,
                      "keys": copy.deepcopy(plan["frame_keys"]), "channel_count": 1,
                      "range": [plan["frame_keys"][0][0], plan["frame_keys"][-1][0] + 1]}
    for label in plan["light_labels"]:
        after["lights"][label] = plan["mi"]
    return after


def revert_model(after: dict, record: dict) -> dict:
    restored = copy.deepcopy(after)
    restored["track"] = copy.deepcopy(record["snapshot_before"].get("track"))
    for label, path in record["snapshot_before"]["lights"].items():
        restored["lights"][label] = path
    return restored


def snapshot_diff(a: dict, b: dict) -> list[str]:
    return [] if a == b else ["SNAPSHOT_DIFF|got=%s|want=%s" % (_digest(a), _digest(b))]


def exact_dirty(actual: dict, expected_content: list[str]) -> list[str]:
    want = {"content": sorted(expected_content), "maps": []}
    got = {"content": sorted(actual.get("content") or []), "maps": sorted(actual.get("maps") or [])}
    return [] if got == want else ["DIRTY_SCOPE|got=%s|want=%s" % (got, want)]


# ------------------------------------------------------------------------------------------------------------------
# Unreal-only transport.  All calls are either declaration-backed or named as [inf] in the DRY API report.

def _here():
    if unreal is None:
        return os.path.dirname(os.path.abspath(__file__))
    return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")


def _stop(run, text):
    message = "%s_STOPPED|run=%s|%s" % (MARK, run, text)
    if unreal is not None:
        unreal.log_error(message)
    raise RuntimeError(message)


def _census():
    return {
        "content": sorted(str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": sorted(str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def _content_file(asset_path):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.join(project, "Content", *asset_path[len("/Game/"):].split("/")) + ".uasset"


def _bindings(seq, labels):
    by = {label: [] for label in labels}
    for binding in seq.get_bindings():
        label = str(binding.get_display_name())
        if label in by:
            by[label].append(binding)
    return by


def _component(binding, run):
    template = binding.get_object_template()  # [prec] shadow_play_spot.py:899-900
    if template is None or not isinstance(template, unreal.SpotLight):
        _stop(run, "NOT_SPOTLIGHT_SPAWNABLE|%s" % binding.get_display_name())
    comp = template.get_editor_property("spot_light_component")
    if comp is None:
        _stop(run, "SPOT_COMPONENT_MISSING|%s" % binding.get_display_name())
    return comp


def _rates(seq):
    tick, disp = seq.get_tick_resolution(), seq.get_display_rate()  # [decl] MovieSceneSequenceExtensions.h:98,116
    nums = (int(tick.numerator), int(tick.denominator), int(disp.numerator), int(disp.denominator))
    return nums, ticks_per_display_frame(*nums), nums[2] / float(nums[3])


def _key_rows(channel):
    rows = []
    for key in channel.get_keys():
        time = key.get_time()  # display rate by default [decl] MovieSceneScriptingChannel.h:30
        frame, sub = int(time.frame_number.value), float(time.sub_frame)
        rows.append([frame if abs(sub) < 1e-6 else frame + sub, float(key.get_value())])
    return rows


def _owned_tracks(seq):
    return [t for t in seq.get_tracks()  # [decl] MovieSceneSequenceExtensions.h:49
            if t.get_class().get_name() == "MovieSceneMaterialParameterCollectionTrack"
            and str(t.get_display_name()) == TRACK_NAME]


def _track_snapshot(seq):
    tracks = _owned_tracks(seq)
    if not tracks:
        return None
    if len(tracks) != 1:
        return {"invalid_count": len(tracks)}
    track = tracks[0]
    sections = list(track.get_sections())
    if len(sections) != 1:
        return {"invalid_sections": len(sections)}
    section = sections[0]
    channels = [c for c in section.get_all_channels() if channel_is_frame(c.channel_name)]
    span = None
    if section.has_start_frame() and section.has_end_frame():
        span = [int(section.get_start_frame()), int(section.get_end_frame())]
    return {"name": TRACK_NAME, "mpc": _path_of(track.get_editor_property("mpc")), "parameter": FRAME_PARAMETER,
            "keys": _key_rows(channels[0]) if len(channels) == 1 else [], "channel_count": len(channels),
            "range": span}


def _snapshot(seq, labels, run):
    rows = _bindings(seq, labels)
    lights = {}
    for label, bindings in rows.items():
        if len(bindings) != 1:
            _stop(run, "LIGHT_LABEL_COUNT|%s|%d" % (label, len(bindings)))
        lights[label] = _path_of(_component(bindings[0], run).get_editor_property("light_function_material"))
    return {"playback": [int(seq.get_playback_start()), int(seq.get_playback_end())],
            "lights": lights, "track": _track_snapshot(seq)}


def _api_probe(seq):
    names = (
        "MaterialParameterCollection", "MaterialParameterCollectionFactoryNew", "CollectionScalarParameter",
        "MaterialExpressionCollectionParameter", "MovieSceneMaterialParameterCollectionTrack",
        "MovieSceneParameterSection", "TextureCompressionSettings", "TextureMipGenSettings",
        "MovieSceneKeyInterpolation",
    )
    out = {name: hasattr(unreal, name) for name in names}
    for method in ("get_tracks", "add_track", "remove_track", "get_tick_resolution", "get_display_rate"):
        out["sequence." + method] = hasattr(seq, method)
    out["MovieSceneParameterSection.add_scalar_parameter_key"] = hasattr(
        getattr(unreal, "MovieSceneParameterSection", None), "add_scalar_parameter_key")
    out["MovieSceneKeyInterpolation.LINEAR"] = hasattr(getattr(unreal, "MovieSceneKeyInterpolation", None), "LINEAR")
    out["EditorAssetLibrary.find_package_referencers_for_asset"] = hasattr(
        unreal.EditorAssetLibrary, "find_package_referencers_for_asset")
    return out


def _referencers(path):
    return sorted(_asset_path(str(v)) for v in unreal.EditorAssetLibrary.find_package_referencers_for_asset(
        path, load_assets_to_confirm=True))


def _describe_shared(existing_shared):
    mel = unreal.MaterialEditingLibrary
    desc = {"master": None, "mpc": None, "mpc_referencers": []}
    if MASTER in existing_shared:
        mat = unreal.load_asset(MASTER)
        desc["master"] = {
            "domain_ok": mat is not None and
            mat.get_editor_property("material_domain") == unreal.MaterialDomain.MD_LIGHT_FUNCTION,
            "atlas_compat": mat is not None and bool(mat.get_editor_property("force_compatible_with_light_function_atlas")),
            "scalars": [str(v) for v in mel.get_scalar_parameter_names(mat)] if mat is not None else [],
            "textures": [str(v) for v in mel.get_texture_parameter_names(mat)] if mat is not None else [],
        }
    if MPC in existing_shared:
        mpc = unreal.load_asset(MPC)
        desc["mpc"] = {"scalars": [str(v) for v in mpc.get_scalar_parameter_names()] if mpc is not None else []}
        desc["mpc_referencers"] = _referencers(MPC)
    return desc


def _live_state(args, seq, run_for_record):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    bindings = _bindings(seq, args["light_labels"])
    existing_shared = [p for p in SHARED_ASSETS if unreal.EditorAssetLibrary.does_asset_exist(p)]
    state = {
        "pie": editor.get_game_world() is not None,
        "sequencer_open": unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None,
        "world_ok": world is not None and str(world.get_outermost().get_name()) == args["world"],
        "census": _census(), "label_counts": {k: len(v) for k, v in bindings.items()},
        "existing_own": [p for p in (args["texture_path"], args["mi_path"])
                         if unreal.EditorAssetLibrary.does_asset_exist(p)],
        "existing_shared": existing_shared,
        "shared_problems": shared_asset_problems(_describe_shared(existing_shared)),
        "owned_track_count": len(_owned_tracks(seq)),
        "record_exists": os.path.isfile(record_file(_here(), run_for_record)),
        "playback": [int(seq.get_playback_start()), int(seq.get_playback_end())],
        "ticks_per_frame": None, "display_fps": None, "rates": None, "rate_error": None,
    }
    try:
        state["rates"], state["ticks_per_frame"], state["display_fps"] = _rates(seq)
    except PlanError as exc:
        state["rate_error"] = str(exc)
    return state


def _custom_input(name):
    pin = unreal.CustomInput()
    pin.set_editor_property("input_name", name)
    return pin


def _create_mpc(tools, run):
    folder, name = MPC.rsplit("/", 1)
    obj = tools.create_asset(name, folder, unreal.MaterialParameterCollection,
                             unreal.MaterialParameterCollectionFactoryNew())
    if obj is None:
        _stop(run, "CREATE_MPC")
    scalar = unreal.CollectionScalarParameter()
    scalar.set_editor_property("parameter_name", FRAME_PARAMETER)
    scalar.set_editor_property("default_value", 0.0)
    obj.set_editor_property("scalar_parameters", [scalar])
    return obj


def _create_master(tools, texture, mpc, run):
    folder, name = MASTER.rsplit("/", 1)
    mat = tools.create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
    mel = unreal.MaterialEditingLibrary
    if mat is None or int(mel.get_num_material_expressions(mat)) != 0:
        _stop(run, "CREATE_MASTER")
    mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_LIGHT_FUNCTION)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    mat.set_editor_property("force_compatible_with_light_function_atlas", True)  # [decl] Material.h:920-927
    nodes = {}

    def node(key, cls, x, y, **props):
        obj = mel.create_material_expression(mat, cls, x, y)
        if obj is None:
            _stop(run, "CREATE_EXPRESSION|%s" % key)
        for prop, value in props.items():
            obj.set_editor_property(prop, value)
        nodes[key] = obj
        return obj

    node("UV", unreal.MaterialExpressionTextureCoordinate, -1500, -700, coordinate_index=0)
    node("Frame", unreal.MaterialExpressionCollectionParameter, -1500, -550,
         collection=mpc, parameter_name=FRAME_PARAMETER)
    for index, (name, value) in enumerate(SCALAR_DEFAULTS.items()):
        if name in ("BlurUV", "Softness", "Contrast", "Depth"):
            continue
        node(name, unreal.MaterialExpressionScalarParameter, -1500, -350 + 100 * index,
             parameter_name=name, default_value=float(value), group="01 Atlas")
    uv_inputs = ["UV", "Frame", "Cols", "Rows", "Frames", "GutterUV", "CellUV", "Scale", "FlipU", "FlipV"]
    node("AtlasUV", unreal.MaterialExpressionCustom, -900, -250, description="ShadowGobo atlas frame UV",
         code=CODE_UV, output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT2,
         inputs=[_custom_input(v) for v in uv_inputs])
    node("Atlas", unreal.MaterialExpressionTextureSampleParameter2D, -550, -200, parameter_name=TEXTURE_PARAMETER,
         texture=texture, sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_GRAYSCALE, group="01 Atlas")
    for index, name in enumerate(("BlurUV", "Softness", "Contrast", "Depth")):
        node(name, unreal.MaterialExpressionScalarParameter, -500, 100 + index * 110,
             parameter_name=name, default_value=float(SCALAR_DEFAULTS[name]), group="02 Look")
    offsets = {"L": (-1.0, 0.0), "R": (1.0, 0.0), "U": (0.0, -1.0), "D": (0.0, 1.0)}
    for index, (suffix, direction) in enumerate(offsets.items()):
        code = "return P + float2(%.1f, %.1f) * clamp(BlurUV, 0.0, 0.003);" % direction
        node("UV" + suffix, unreal.MaterialExpressionCustom, -700, 50 + index * 120,
             description="ShadowGobo blur " + suffix, code=code,
             output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT2,
             inputs=[_custom_input("P"), _custom_input("BlurUV")])
        node("Atlas" + suffix, unreal.MaterialExpressionTextureSampleParameter2D, -350, 50 + index * 120,
             parameter_name=TEXTURE_PARAMETER, texture=texture,
             sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_GRAYSCALE, group="01 Atlas")
    node("Blur", unreal.MaterialExpressionCustom, -50, -180, description="ShadowGobo five tap blur",
         code=CODE_AVG, output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT1,
         inputs=[_custom_input(v) for v in ("C", "L", "R", "U", "D")])
    node("Edge", unreal.MaterialExpressionCustom, -100, 0, description="ShadowGobo softness contrast depth",
         code=CODE_EDGE, output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT1,
         inputs=[_custom_input(v) for v in ("Mask", "Softness", "Contrast", "Depth")])
    for src in uv_inputs:
        if not mel.connect_material_expressions(nodes[src], "", nodes["AtlasUV"], src):
            _stop(run, "CONNECT|%s->AtlasUV.%s" % (src, src))
    if not mel.connect_material_expressions(nodes["AtlasUV"], "", nodes["Atlas"], "UVs"):
        _stop(run, "CONNECT|AtlasUV->Atlas.UVs")
    if not mel.connect_material_expressions(nodes["Atlas"], "R", nodes["Blur"], "C"):
        _stop(run, "CONNECT|Atlas.R->Blur.C")
    for suffix in offsets:
        if not mel.connect_material_expressions(nodes["AtlasUV"], "", nodes["UV" + suffix], "P"):
            _stop(run, "CONNECT|AtlasUV->UV%s.P" % suffix)
        if not mel.connect_material_expressions(nodes["BlurUV"], "", nodes["UV" + suffix], "BlurUV"):
            _stop(run, "CONNECT|BlurUV->UV%s.BlurUV" % suffix)
        if not mel.connect_material_expressions(nodes["UV" + suffix], "", nodes["Atlas" + suffix], "UVs"):
            _stop(run, "CONNECT|UV%s->Atlas%s.UVs" % (suffix, suffix))
        if not mel.connect_material_expressions(nodes["Atlas" + suffix], "R", nodes["Blur"], suffix):
            _stop(run, "CONNECT|Atlas%s.R->Blur.%s" % (suffix, suffix))
    if not mel.connect_material_expressions(nodes["Blur"], "", nodes["Edge"], "Mask"):
        _stop(run, "CONNECT|Blur->Edge.Mask")
    for name in ("Softness", "Contrast", "Depth"):
        if not mel.connect_material_expressions(nodes[name], "", nodes["Edge"], name):
            _stop(run, "CONNECT|%s->Edge.%s" % (name, name))
    if not mel.connect_material_property(nodes["Edge"], "", unreal.MaterialProperty.MP_EMISSIVE_COLOR):
        _stop(run, "CONNECT_PROPERTY|Emissive")
    mel.recompile_material(mat)
    return mat


def _import_texture(args, run):
    folder, name = args["texture_path"].rsplit("/", 1)
    task = unreal.AssetImportTask()
    for prop, value in (("filename", args["atlas_png"]), ("destination_path", folder),
                        ("destination_name", name), ("automated", True), ("replace_existing", False), ("save", False)):
        task.set_editor_property(prop, value)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    tex = unreal.load_asset(args["texture_path"])
    if tex is None or not isinstance(tex, unreal.Texture2D):
        _stop(run, "IMPORT_TEXTURE|%s" % args["texture_path"])
    tex.set_editor_property("srgb", False)
    tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_GRAYSCALE)
    tex.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
    tex.set_editor_property("never_stream", True)
    tex.set_editor_property("filter", unreal.TextureFilter.TF_BILINEAR)
    tex.set_editor_property("address_x", unreal.TextureAddress.TA_CLAMP)
    tex.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)
    return tex


def _create_mi(tools, mat, texture, plan, run):
    folder, name = plan["mi"].rsplit("/", 1)
    mi = tools.create_asset(name, folder, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    if mi is None:
        _stop(run, "CREATE_MI|%s" % plan["mi"])
    mel = unreal.MaterialEditingLibrary
    mel.set_material_instance_parent(mi, mat)
    mel.set_material_instance_texture_parameter_value(mi, TEXTURE_PARAMETER, texture)
    for name, value in plan["params"].items():
        mel.set_material_instance_scalar_parameter_value(mi, name, float(value))
    mel.update_material_instance(mi)
    return mi


def _add_frame_track(seq, mpc, plan, ticks_per_frame, run):
    if _owned_tracks(seq):
        _stop(run, "OWNED_TRACK_EXISTS")
    track = seq.add_track(unreal.MovieSceneMaterialParameterCollectionTrack)  # [decl] ...SequenceExtensions.h:79
    if track is None:
        _stop(run, "ADD_TRACK")
    track.set_display_name(TRACK_NAME)
    track.set_editor_property("mpc", mpc)  # [decl] MovieSceneMaterialParameterCollectionTrack.h:26-28
    section = track.add_section()
    # Display frames [prec] key_walkin_i1_p02.py:331 (set_range(playback_start, playback_end + 1)).
    section.set_range(plan["frame_keys"][0][0], plan["frame_keys"][-1][0] + 1)
    interpolation = unreal.MovieSceneKeyInterpolation.LINEAR
    for frame, value in plan["frame_keys"]:
        # Raw FFrameNumber = tick resolution [inf]; read back in display frames by _key_rows.
        section.add_scalar_parameter_key(FRAME_PARAMETER, unreal.FrameNumber(int(frame) * ticks_per_frame),
                                         float(value), interpolation)
    return track


def _verify_assets(plan, seq, record, run):
    failures = []
    mel = unreal.MaterialEditingLibrary
    failures.extend(shared_asset_problems(_describe_shared(
        [p for p in SHARED_ASSETS if unreal.EditorAssetLibrary.does_asset_exist(p)])))
    for path in SHARED_ASSETS:
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            failures.append("SHARED_MISSING|%s" % path)
    tex, mi = unreal.load_asset(plan["texture"]), unreal.load_asset(plan["mi"])
    if tex is None:
        failures.append("TEXTURE_MISSING")
    else:
        for prop, want in (("srgb", False), ("never_stream", True)):
            if bool(tex.get_editor_property(prop)) != want:
                failures.append("TEXTURE_%s" % prop)
    if mi is None or _path_of(mi.get_editor_property("parent")) != plan["master"]:
        failures.append("MI_PARENT")
    elif _path_of(mel.get_material_instance_texture_parameter_value(mi, TEXTURE_PARAMETER)) != plan["texture"]:
        failures.append("MI_TEXTURE")
    else:
        for name, want in plan["params"].items():
            got = float(mel.get_material_instance_scalar_parameter_value(mi, name))
            if abs(got - float(want)) > FLOAT_TOL:
                failures.append("MI_SCALAR|%s|%.7g|%.7g" % (name, got, want))
    snap = _snapshot(seq, plan["light_labels"], run)
    failures.extend(snapshot_diff(snap, record["snapshot_after"]))
    return failures


def run_dry(args, plan, run):
    seq = unreal.load_asset(args["sequence"])
    if seq is None or not isinstance(seq, unreal.LevelSequence):
        _stop(run, "SEQUENCE_MISSING|%s" % args["sequence"])
    probe = _api_probe(seq)
    missing = sorted(k for k, value in probe.items() if not value)
    if missing:
        _stop(run, "PYTHON_API_MISSING|%s" % missing)
    state = _live_state(args, seq, run)
    refusals = preflight_refusals("DRY", args, state, plan)
    timing = timing_report(plan, state["display_fps"]) if state["display_fps"] else None
    report = {"run": run, "mode": "DRY", "plan": plan, "state": state, "api_probe": probe, "timing": timing,
              "created_assets": created_assets_for(plan, state["existing_shared"]),
              "refusals": refusals, "apply_ready": not refusals}
    _write_json(plan_file(_here(), run), report)
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|%s" % _census())
    marker = "%s_DRY_OK|run=%s|apply_ready=%d|refusals=%d|digest=%s|labels=%d|frames=%d|range=%s|reuse=%s|tpf=%s" % (
        MARK, run, int(not refusals), len(refusals), plan["digest"], len(plan["light_labels"]),
        plan["atlas"]["frames"], plan["sequence_range_requested"],
        ",".join(p.rsplit("/", 1)[1] for p in state["existing_shared"]) or "none", state["ticks_per_frame"])
    unreal.log(marker)
    if timing and "speed_vs_take" in timing and abs(timing["speed_vs_take"] - 1.0) > SPEED_WARN:
        unreal.log_warning("%s_TIMING|run=%s|speed_vs_take=%.3f|native_frame_end=%d|display_fps=%.3f" % (
            MARK, run, timing["speed_vs_take"], timing["native_frame_end"], timing["display_fps"]))
    for refusal in refusals:
        unreal.log_warning("%s_REFUSAL|run=%s|%s" % (MARK, run, refusal))


def run_apply(args, plan, run):
    seq = unreal.load_asset(args["sequence"])
    if seq is None or not isinstance(seq, unreal.LevelSequence):
        _stop(run, "SEQUENCE_MISSING|%s" % args["sequence"])
    state = _live_state(args, seq, run)
    refusals = preflight_refusals("APPLY", args, state, plan)
    dry = _load_json(plan_file(_here(), run)) or {}
    if (dry.get("plan") or {}).get("digest") != plan["digest"] or not dry.get("apply_ready"):
        refusals.append("DRY_NOT_CURRENT|rerun DRY with identical args and run_id")
    elif sorted((dry.get("state") or {}).get("existing_shared") or []) != sorted(state["existing_shared"]):
        refusals.append("DRY_NOT_CURRENT|shared assets changed since DRY")
    if refusals:
        _stop(run, "REFUSED|" + " || ".join(refusals))
    created = created_assets_for(plan, state["existing_shared"])
    ticks_per_frame = state["ticks_per_frame"]

    before = _snapshot(seq, plan["light_labels"], run)
    if before.get("track") is not None:
        _stop(run, "TRACK_PREEXISTS|create-only sequence track")
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = os.path.join(project, "Backups", "PreAnimatedGobo-%s" % run)
    os.makedirs(backup, exist_ok=False)
    source = _content_file(args["sequence"])
    copied = os.path.join(backup, os.path.basename(source))
    shutil.copy2(source, copied)
    if os.path.getsize(source) != os.path.getsize(copied):
        _stop(run, "BACKUP_SIZE|%s" % copied)
    record_path = record_file(_here(), run)
    record = {"schema_version": 2, "run": run, "applied": False, "verified": False, "plan": plan,
              "plan_digest": plan["digest"], "backup": backup, "backup_files": [copied],
              "snapshot_before": before, "sequence": args["sequence"], "created_assets": created,
              "reused_assets": sorted(state["existing_shared"]), "ticks_per_frame": ticks_per_frame,
              "rates": state["rates"]}
    try:
        _write_json(record_path, record, exclusive=True)
    except FileExistsError:
        _stop(run, "RECORD_EXISTS|nothing mutated")

    # Mutation begins only after backup + exclusive record.
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    texture = _import_texture(args, run)
    mpc = _create_mpc(tools, run) if MPC in created else unreal.load_asset(MPC)
    mat = _create_master(tools, texture, mpc, run) if MASTER in created else unreal.load_asset(MASTER)
    if mpc is None or mat is None:
        _stop(run, "SHARED_LOAD|mpc=%s|master=%s|NOTHING SAVED; Don't-Save restart" % (mpc, mat))
    mi = _create_mi(tools, mat, texture, plan, run)
    seq.modify()
    for label, bindings in _bindings(seq, plan["light_labels"]).items():
        _component(bindings[0], run).set_editor_property("light_function_material", mi)
    _add_frame_track(seq, mpc, plan, ticks_per_frame, run)
    after = apply_model(before, plan)
    live_after = _snapshot(seq, plan["light_labels"], run)
    problems = snapshot_diff(live_after, after)
    problems.extend(exact_dirty(_census(), created + [plan["sequence"]]))
    if problems:
        _stop(run, "PRESAVE_READBACK|%s|live_track=%s|NOTHING SAVED; Don't-Save restart; record remains applied=false" %
              (problems, live_after.get("track")))
    saved = {path: bool(unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False))
             for path in created + [plan["sequence"]]}
    if not all(saved.values()) or _census() != {"content": [], "maps": []}:
        _stop(run, "NARROW_SAVE|saved=%s|census=%s|restore sequence from %s" % (saved, _census(), backup))
    # Same-call read-back is a guard, not the independent material/import proof.
    record.update({"applied": True, "snapshot_after": after, "same_call_readback": live_after})
    _write_json(record_path, record)
    unreal.log("%s_APPLY_OK_PENDING_VERIFY|run=%s|saved=%d|created=%d|reused=%d|sequence=%s|mi=%s|backup=%s|next=VERIFY" %
               (MARK, run, len(saved), len(created), len(record["reused_assets"]), plan["sequence"], plan["mi"], backup))


def _load_applied_record(args, run, missing_code):
    record_path = record_file(_here(), args["apply_run"])
    record = _load_json(record_path)
    if not record or not record.get("applied"):
        _stop(run, "%s|apply_run=%s" % (missing_code, args["apply_run"]))
    if record["plan"]["sequence"] != args["sequence"]:
        _stop(run, "RECORD_SEQUENCE_MISMATCH|record=%s|args=%s" % (record["plan"]["sequence"], args["sequence"]))
    return record_path, record


def run_verify(args, run):
    record_path, record = _load_applied_record(args, run, "NOTHING_TO_VERIFY")
    plan = record["plan"]
    seq = unreal.load_asset(plan["sequence"])
    state = _live_state(dict(args, light_labels=plan["light_labels"], texture_path=plan["texture"], mi_path=plan["mi"]),
                        seq, args["apply_run"])
    refusals = preflight_refusals("VERIFY", args, state, plan)
    if refusals:
        _stop(run, "REFUSED|" + " || ".join(refusals))
    failures = _verify_assets(plan, seq, record, run)
    if failures:
        _stop(run, "VERIFY_READBACK|%s" % failures)
    record.update({"verified": True, "verify_run": run,
                   "verified_at": datetime.datetime.now().isoformat(timespec="seconds")})
    _write_json(record_path, record)
    unreal.log("%s_SUCCESS|run=%s|apply_run=%s|created=%d|reused=%d|lights=%d|keys=%s|tpf=%s|dirty=0" %
               (MARK, run, record["run"], len(record["created_assets"]), len(record.get("reused_assets") or []),
                len(plan["light_labels"]), plan["frame_keys"], record.get("ticks_per_frame")))


def run_revert(args, run):
    record_path, record = _load_applied_record(args, run, "NOTHING_TO_REVERT")
    plan = record["plan"]
    created = list(record["created_assets"])
    seq = unreal.load_asset(plan["sequence"])
    state = _live_state(dict(args, light_labels=plan["light_labels"], texture_path=plan["texture"], mi_path=plan["mi"]),
                        seq, args["apply_run"])
    refusals = preflight_refusals("REVERT", args, state, plan)
    if refusals:
        _stop(run, "REFUSED|" + " || ".join(refusals))
    current = _snapshot(seq, plan["light_labels"], run)
    drift = snapshot_diff(current, record["snapshot_after"])
    if drift:
        _stop(run, "STATE_DRIFTED_SINCE_APPLY|%s" % drift)
    # Refuse before any mutation if anything outside this record still refers to an asset this run created (e.g. a
    # later run's MI on the shared master).  Revert runs in reverse order.
    external = {}
    allowed_referencers = set(created + [plan["sequence"]])
    for path in created:
        outside = [v for v in _referencers(path) if v not in allowed_referencers]
        if outside:
            external[path] = outside
    if external or _census() != {"content": [], "maps": []}:
        _stop(run, "REVERT_EXTERNAL_REFERENCERS|refs=%s|census=%s|nothing changed; revert later runs first" %
              (external, _census()))
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = os.path.join(project, "Backups", "PreAnimatedGoboRevert-%s" % run)
    os.makedirs(backup, exist_ok=False)
    for path in [plan["sequence"]] + created:
        source = _content_file(path)
        if os.path.isfile(source):
            shutil.copy2(source, os.path.join(backup, os.path.basename(source)))
    seq.modify()
    for label, bindings in _bindings(seq, plan["light_labels"]).items():
        old_path = record["snapshot_before"]["lights"][label]
        _component(bindings[0], run).set_editor_property("light_function_material",
                                                         unreal.load_asset(old_path) if old_path else None)
    tracks = _owned_tracks(seq)
    if len(tracks) != 1:
        _stop(run, "OWNED_TRACK_COUNT|%d|NOTHING SAVED; Don't-Save restart" % len(tracks))
    seq.remove_track(tracks[0])  # [decl] ...SequenceExtensions.h:89; return value not trusted, read back below
    restored = _snapshot(seq, plan["light_labels"], run)
    problems = snapshot_diff(restored, record["snapshot_before"])
    problems.extend(exact_dirty(_census(), [plan["sequence"]]))
    if problems:
        _stop(run, "REVERT_PRESAVE|%s|NOTHING SAVED; Don't-Save restart" % problems)
    if not unreal.EditorAssetLibrary.save_asset(plan["sequence"], only_if_is_dirty=True):
        _stop(run, "REVERT_SEQUENCE_SAVE|%s" % plan["sequence"])
    deleted = []
    # Dependency order: MI -> master -> MPC -> texture; only what this run created.
    for path in (plan["mi"], plan["master"], plan["mpc"], plan["texture"]):
        if path in created and unreal.EditorAssetLibrary.does_asset_exist(path) and \
                unreal.EditorAssetLibrary.delete_asset(path):
            deleted.append(path)
    survivors = [p for p in created if unreal.EditorAssetLibrary.does_asset_exist(p)]
    if survivors or _census() != {"content": [], "maps": []}:
        _stop(run, "REVERT_DELETE_READBACK|survivors=%s|census=%s|recover=%s" % (survivors, _census(), backup))
    archived = record_path + ".reverted-" + run
    os.rename(record_path, archived)
    unreal.log("%s_REVERT_OK|run=%s|apply_run=%s|restored_sequence=%s|deleted=%d|kept_shared=%s|recoverable_from=%s|record=%s" %
               (MARK, run, args["apply_run"], plan["sequence"], len(deleted),
                ",".join(record.get("reused_assets") or []) or "none", backup, archived))


def main(raw=None):
    raw = dict(raw if raw is not None else globals().get("ANIMATED_GOBO_ARGS") or {})
    run = str(raw.get("run_id") or "UNSET")
    try:
        args = normalized_args(raw)
        if not confirm_ok(args["mode"], args.get("confirm")):
            _stop(run, "CONFIRM_MISMATCH|want %r|got %r" % (confirm_text(args["mode"]), args.get("confirm")))
        if args["mode"] == "VERIFY":
            run_verify(args, run)
            return
        if args["mode"] == "REVERT":
            run_revert(args, run)
            return
        plan = plan_from_args(args)
        if args["mode"] == "DRY":
            run_dry(args, plan, run)
        else:
            run_apply(args, plan, run)
    except PlanError as exc:
        _stop(run, "PLAN_REFUSED|%s" % exc)


if unreal is not None:
    main()
