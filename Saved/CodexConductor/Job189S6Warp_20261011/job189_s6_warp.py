"""Job 189: P06->S6 move-in and one-pass S6 fallback-video warp.

Offline-authored. Run only through ExecuteProjectPythonFile after job 185 releases
the editor. DRY is the default. APPLY/REVERT require exact confirmation strings.

APPLY creates/reuses one UI material and one MPC, adds one keyed MPC track to
LS_DevScene_06, keys a transform-only 2.8 s P06 dolly through the established
camera-pilot API, and retakes the single tagged Scene 6 entry camera to preserve
the seam. It saves only the two sequences, named assets, and current map.

The source patch in Scripts/patches/2026-10-11_job189_s6_warp_overlay.patch is a
build prerequisite: the current video is Slate, not world geometry, so only that
hook can give the transient MediaTexture to this material.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
import shutil
import sys

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import job189_core as core

ARGS = os.path.join(HERE, "job189_args.json")
SCORES = os.path.join(HERE, "warp_scores.json")
RECORDS = os.path.join(HERE, "records")
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
WORLD_PATH = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
MASTER_PATH = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_Master"
S6_PATH = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_06"
MPC_PATH = "/Game/InfinityStage/Effects/S6/MPC_S6Warp"
MATERIAL_PATH = "/Game/InfinityStage/Effects/S6/M_S6Warp_UI"
ENGINE_WHITE = "/Engine/EngineResources/WhiteSquareTexture.WhiteSquareTexture"
TRACK_NAME = "S6 Warp Score (Job189)"
VIDEO_MATERIAL_CVAR = "InfinityStage.VideoFallback.WarpMaterial"
CAMERA_CHANNELS = (
    "Camera.LongitudinalOffsetCm", "Camera.LateralOffsetCm", "Camera.HeightOffsetCm",
    "Camera.PitchDegrees", "Camera.YawDegrees", "Camera.RollDegrees",
)
FLOAT_TOL = 1.0e-4

WARP_HLSL = r"""
float master = saturate(Weird);
float2 centre = UV - 0.5;
float radius = length(centre);
float angle = atan2(centre.y, centre.x);

// Analytic, texture-free panning noise plus a radius-weighted slow swirl.
float n1 = sin(UV.y * 17.0 + Phase * 0.73 + sin(UV.x * 11.0 - Phase * 0.37));
float n2 = cos(UV.x * 13.0 - Phase * 0.51 + cos(UV.y * 9.0 + Phase * 0.29));
float swirl = sin(radius * 18.0 - Phase * 0.43) * exp(-radius * 2.2);
angle += master * Warp * (0.42 * swirl + 0.08 * n1);
float2 warped = float2(cos(angle), sin(angle)) * radius;
warped += master * Warp * float2(n1, n2) * (0.008 + 0.018 * radius);

// Mirror is a polar kaleidoscope fold. Zero is exact pass-through.
float blades = 2.0 + floor(saturate(Mirror) * 6.0);
float folded = abs(frac((atan2(warped.y, warped.x) / 6.2831853) * blades + 0.5) * 2.0 - 1.0);
float foldAngle = (folded - 0.5) * (6.2831853 / blades);
float2 kaleido = float2(cos(foldAngle), sin(foldAngle)) * length(warped);
warped = lerp(warped, kaleido, master * saturate(Mirror));
float2 baseUV = saturate(warped + 0.5);

// Three source samples, still one material pass. No history or render targets.
float2 tangent = normalize(float2(-warped.y, warped.x) + float2(1e-5, 0.0));
float split = master * saturate(ChromaSplit) * 0.018;
float r = Texture2DSample(VideoTexture, VideoTextureSampler, saturate(baseUV + tangent * split)).r;
float g = Texture2DSample(VideoTexture, VideoTextureSampler, baseUV).g;
float b = Texture2DSample(VideoTexture, VideoTextureSampler, saturate(baseUV - tangent * split)).b;
float3 colour = float3(r, g, b);

// Hue rotation in YIQ space.
float hue = saturate(HueDrift) * master * 3.14159265;
float Y = dot(colour, float3(0.299, 0.587, 0.114));
float I = dot(colour, float3(0.596, -0.275, -0.321));
float Q = dot(colour, float3(0.212, -0.523, 0.311));
float cs = cos(hue), sn = sin(hue);
float I2 = I * cs - Q * sn;
float Q2 = I * sn + Q * cs;
colour = saturate(float3(Y + 0.956 * I2 + 0.621 * Q2,
                         Y - 0.272 * I2 - 0.647 * Q2,
                         Y - 1.106 * I2 + 1.703 * Q2));

// Invert luminance, preserving chroma: black/white swap without arbitrary RGB inversion.
float lum = dot(colour, float3(0.299, 0.587, 0.114));
float3 lumInverted = saturate(colour + (1.0 - 2.0 * lum));
colour = lerp(colour, lumInverted, master * saturate(Invert));

// Posterize into a solarized triangular response at the intense end.
float sol = master * saturate(Solarize);
float levels = lerp(10.0, 3.0, sol);
float3 poster = floor(colour * levels + 0.5) / levels;
float3 solar = 1.0 - abs(2.0 * poster - 1.0);
colour = lerp(colour, solar, sol);

return float4(colour, 1.0);
"""


class Stop(RuntimeError):
    pass


def stop(run, reason):
    unreal.log_error("JOB189_FAILED|run=%s|%s" % (run, reason))
    raise Stop(reason)


def read_json(path):
    with open(path, encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_new(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)


def replace_json(path, value):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def unwrap(result, count, label):
    if isinstance(result, tuple) and len(result) == count + 1 and isinstance(result[0], bool):
        if not result[0]:
            raise Stop("%s returned false" % label)
        return result[1:]
    if isinstance(result, tuple) and len(result) == count:
        return result
    raise Stop("%s returned unexpected %r" % (label, result))


def asset_id(obj):
    return obj.get_path_name().split(".", 1)[0] if obj else None


def guid_text(value):
    return unreal.GuidLibrary.conv_guid_to_string(value)


def enum_name(value):
    return str(value).split(".")[-1].split(":")[0].strip(" <>')")


def dirty_census():
    return {
        "content": sorted(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": sorted(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def vec(value):
    return [float(value.x), float(value.y), float(value.z)]


def rot(value):
    return [float(value.roll), float(value.pitch), float(value.yaw)]


def transform_row(value):
    return {"location": vec(value.translation), "rotation": rot(value.rotation.rotator()), "scale": vec(value.scale3d)}


def actor_state(actor):
    component = actor.get_cine_camera_component()
    focus = component.get_editor_property("focus_settings")
    return {
        "path": actor.get_path_name(), "label": str(actor.get_actor_label()),
        "transform": transform_row(actor.get_actor_transform()),
        "focal_mm": float(component.get_editor_property("current_focal_length")),
        "focus_cm": float(focus.get_editor_property("manual_focus_distance")),
    }


def make_transform(row):
    return unreal.Transform(
        location=unreal.Vector(*row["location"]),
        rotation=unreal.Rotator(roll=row["rotation"][0], pitch=row["rotation"][1], yaw=row["rotation"][2]),
        scale=unreal.Vector(*row.get("scale", [1.0, 1.0, 1.0])))


def set_camera_actor(actor, state):
    actor.modify()
    actor.set_actor_transform(make_transform(state["transform"]), False, True)
    component = actor.get_cine_camera_component()
    component.set_editor_property("current_focal_length", float(state["focal_mm"]))
    focus = component.get_editor_property("focus_settings")
    focus.set_editor_property("manual_focus_distance", float(state["focus_cm"]))
    component.set_editor_property("focus_settings", focus)


def pose_row(result):
    view, focal, focus = result
    return {"transform": transform_row(view), "focal_mm": float(focal), "focus_cm": float(focus)}


def pose_delta(a, b):
    la, lb = a["transform"]["location"], b["transform"]["location"]
    ra, rb = a["transform"]["rotation"], b["transform"]["rotation"]
    return {
        "position_cm": math.sqrt(sum((x - y) ** 2 for x, y in zip(la, lb))),
        "rotation_deg_euler_max": max(abs(x - y) for x, y in zip(ra, rb)),
        "focal_mm": abs(float(a["focal_mm"]) - float(b["focal_mm"])),
    }


def channel_name(channel):
    return str(channel.get_editor_property("channel_name")).rsplit("_", 1)[0]


def find_channel(section, wanted):
    hits = [ch for ch in section.get_all_channels()
            if str(ch.get_editor_property("channel_name")) == wanted
            or str(ch.get_editor_property("channel_name")).startswith(wanted + "_")]
    if len(hits) != 1:
        raise Stop("CHANNEL_COUNT|%s|%d" % (wanted, len(hits)))
    return hits[0]


def key_row(key):
    time = key.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION)
    return {
        "tick": int(time.frame_number.value), "sub": float(time.sub_frame), "value": float(key.get_value()),
        "interp": enum_name(key.get_interpolation_mode()), "tangent": enum_name(key.get_tangent_mode()),
        "weight": enum_name(key.get_tangent_weight_mode()),
        "arrive": float(key.get_arrive_tangent()), "leave": float(key.get_leave_tangent()),
        "arrive_weight": float(key.get_arrive_tangent_weight()), "leave_weight": float(key.get_leave_tangent_weight()),
    }


def channel_snapshot(section):
    result = {}
    for name in CAMERA_CHANNELS:
        channel = find_channel(section, name)
        result[name] = {
            "default": float(channel.get_default()) if channel.has_default() else None,
            "keys": sorted((key_row(key) for key in channel.get_keys()), key=lambda row: (row["tick"], row["sub"])),
        }
    return result


def restore_channels(section, snapshot):
    for name in CAMERA_CHANNELS:
        channel = find_channel(section, name)
        for key in list(channel.get_keys()):
            channel.remove_key(key)
        state = snapshot[name]
        if state["default"] is None:
            if channel.has_default():
                channel.remove_default()
        else:
            channel.set_default(float(state["default"]))
        for row in state["keys"]:
            key = channel.add_key(unreal.FrameNumber(int(row["tick"])), float(row["value"]),
                                  sub_frame=float(row["sub"]),
                                  time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION)
            key.set_interpolation_mode(getattr(unreal.RichCurveInterpMode, row["interp"]))
            key.set_tangent_mode(getattr(unreal.RichCurveTangentMode, row["tangent"]))
            key.set_tangent_weight_mode(getattr(unreal.RichCurveTangentWeightMode, row["weight"]))
            key.set_arrive_tangent(float(row["arrive"]))
            key.set_leave_tangent(float(row["leave"]))
            key.set_arrive_tangent_weight(float(row["arrive_weight"]))
            key.set_leave_tangent_weight(float(row["leave_weight"]))


def find_context(run):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world is None or asset_id(world) != WORLD_PATH:
        stop(run, "WRONG_WORLD|%r" % asset_id(world))
    if editor.get_game_world() is not None:
        stop(run, "PIE_OR_SIE_ACTIVE")
    census = dirty_census()
    if census["content"] or census["maps"]:
        stop(run, "DIRTY_BEFORE|%s" % json.dumps(census, sort_keys=True))
    show = unreal.load_asset(SHOW_PATH)
    master = unreal.load_asset(MASTER_PATH)
    s6 = unreal.load_asset(S6_PATH)
    if show is None or master is None or s6 is None:
        stop(run, "ASSET_LOAD|show=%r|master=%r|s6=%r" % (show, master, s6))
    passages = [row for row in show.get_editor_property("passage_settings")
                if str(row.get_editor_property("label")).replace("0", "").strip() in ("Passage 6", "Passage 6 -")]
    if len(passages) != 1:
        passages = [row for row in show.get_editor_property("passage_settings")
                    if str(row.get_editor_property("label")).startswith("Passage 06")
                    or str(row.get_editor_property("label")) == "Passage 6"]
    if len(passages) != 1:
        stop(run, "P06_ROW_COUNT|%d" % len(passages))
    guid = passages[0].get_editor_property("passage_guid")
    sections = []
    for track in master.get_tracks():
        if track.get_class().get_name() != "MovieSceneInfinityPassageTrack":
            continue
        for section in track.get_sections():
            if guid_text(section.get_editor_property("passage_guid")) == guid_text(guid):
                sections.append(section)
    if len(sections) != 1:
        stop(run, "P06_SECTION_COUNT|%d" % len(sections))
    entries = []
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if isinstance(actor, unreal.CineCameraActor) and actor.actor_has_tag("InfinityStage.SceneEntry"):
            if str(actor.get_actor_label()).startswith("Scene 6 "):
                entries.append(actor)
    if len(entries) != 1:
        stop(run, "S6_ENTRY_COUNT|%d" % len(entries))
    frame_range = unwrap(unreal.InfinityStageCameraPilotLibrary.get_passage_frame_range(show, guid), 2, "P06_RANGE")
    return {"editor": editor, "world": world, "show": show, "master": master, "s6": s6,
            "guid": guid, "section": sections[0], "entry": entries[0],
            "start": int(frame_range[0]), "end": int(frame_range[1]), "dirty": census}


def owned_tracks(sequence):
    return [track for track in sequence.get_tracks()
            if track.get_class().get_name() == "MovieSceneMaterialParameterCollectionTrack"
            and str(track.get_display_name()) == TRACK_NAME]


def track_snapshot(sequence):
    tracks = owned_tracks(sequence)
    if not tracks:
        return None
    if len(tracks) != 1 or len(tracks[0].get_sections()) != 1:
        return {"invalid_tracks": len(tracks)}
    track = tracks[0]
    section = list(track.get_sections())[0]
    rows = {}
    for channel in section.get_all_channels():
        name = str(channel.get_editor_property("channel_name")).rsplit("_", 1)[0]
        rows[name] = sorted([[int(key.get_time().frame_number.value), float(key.get_value())]
                             for key in channel.get_keys()])
    return {"mpc": asset_id(track.get_editor_property("mpc")), "channels": rows,
            "range": [int(section.get_start_frame()), int(section.get_end_frame())]}


def asset_state():
    result = {"mpc": None, "material": None}
    if unreal.EditorAssetLibrary.does_asset_exist(MPC_PATH):
        mpc = unreal.load_asset(MPC_PATH)
        result["mpc"] = sorted(str(name) for name in mpc.get_scalar_parameter_names()) if mpc else ["LOAD_FAILED"]
    if unreal.EditorAssetLibrary.does_asset_exist(MATERIAL_PATH):
        material = unreal.load_asset(MATERIAL_PATH)
        result["material"] = {
            "domain": enum_name(material.get_editor_property("material_domain")) if material else "LOAD_FAILED",
            "expressions": int(unreal.MaterialEditingLibrary.get_num_material_expressions(material)) if material else -1,
        }
    return result


def media_contract_probe():
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    cue = os.path.join(project, "Content", "InfinityStage", "CueSheet", "cue_director.txt")
    registry = os.path.join(project, "Renders", "Fallbacks", "current.json")
    result = {"cue_director": cue, "registry": registry, "cue_exists": os.path.isfile(cue),
              "registry_exists": os.path.isfile(registry), "s6_use_video": False, "s6_registry": None}
    if os.path.isfile(cue):
        text = open(cue, encoding="utf-8-sig").read().lower()
        result["s6_use_video"] = any(line.strip().replace(" ", "") == "use_video=s6" for line in text.splitlines())
    if os.path.isfile(registry):
        try:
            result["s6_registry"] = read_json(registry).get("scenes", {}).get("S6")
        except Exception as exc:
            result["registry_error"] = repr(exc)
    getter = getattr(unreal.SystemLibrary, "get_console_variable_string_value", None)
    if callable(getter):
        try:
            result["compiled_warp_material_cvar"] = str(getter(VIDEO_MATERIAL_CVAR))
        except Exception as exc:
            result["compiled_warp_material_cvar_error"] = repr(exc)
    return result


def api_probe():
    names = (
        "MaterialParameterCollection", "MaterialParameterCollectionFactoryNew", "CollectionScalarParameter",
        "Material", "MaterialFactoryNew", "MaterialEditingLibrary", "MaterialExpressionTextureCoordinate",
        "MaterialExpressionTextureObjectParameter", "MaterialExpressionCollectionParameter",
        "MaterialExpressionCustom", "CustomInput", "MovieSceneMaterialParameterCollectionTrack",
        "MovieSceneKeyInterpolation", "InfinityStageCameraPilotLibrary",
    )
    result = {name: hasattr(unreal, name) for name in names}
    result["MaterialDomain.MD_UI"] = hasattr(getattr(unreal, "MaterialDomain", None), "MD_UI")
    result["CustomMaterialOutputType.CMOT_FLOAT4"] = hasattr(
        getattr(unreal, "CustomMaterialOutputType", None), "CMOT_FLOAT4")
    result["MaterialProperty.MP_EMISSIVE_COLOR"] = hasattr(
        getattr(unreal, "MaterialProperty", None), "MP_EMISSIVE_COLOR")
    result["MovieSceneParameterSection.add_scalar_parameter_key"] = hasattr(
        getattr(unreal, "MovieSceneParameterSection", None), "add_scalar_parameter_key")
    result["SystemLibrary.get_console_variable_string_value"] = hasattr(
        unreal.SystemLibrary, "get_console_variable_string_value")
    return result


def snapshot(ctx):
    lib = unreal.InfinityStageCameraPilotLibrary
    end_pose = pose_row(unwrap(lib.get_passage_camera_pose(ctx["show"], ctx["guid"], ctx["end"]), 3, "P06_END_POSE"))
    entry = actor_state(ctx["entry"])
    return {"camera_channels": channel_snapshot(ctx["section"]), "entry": entry,
            "p06_end": end_pose, "seam_delta": pose_delta(end_pose, entry),
            "warp_track": track_snapshot(ctx["s6"]), "assets": asset_state(),
            "media_contract": media_contract_probe(), "dirty": dirty_census()}


def proposal(ctx, args, rows):
    tick = ctx["show"].get_editor_property("tick_resolution")
    tick_rate = tick.numerator / float(tick.denominator)
    frames = core.move_frames(ctx["end"], tick_rate, args["move_seconds"], args["ease_fraction"])
    lib = unreal.InfinityStageCameraPilotLibrary
    poses = [pose_row(unwrap(lib.get_passage_camera_pose(ctx["show"], ctx["guid"], frame), 3,
                                 "P06_POSE_%d" % frame)) for frame in frames]
    fractions = [0.0, 0.18, 1.0]
    desired = []
    for frame, pose, fraction in zip(frames, poses, fractions):
        transform = make_transform(pose["transform"])
        forward = unreal.MathLibrary.get_forward_vector(transform.rotation.rotator())
        moved = dict(pose["transform"])
        moved["location"] = vec(transform.translation + forward * (args["push_cm"] * fraction))
        desired.append({"frame": frame, "fraction": fraction, "transform": moved,
                        "focal_mm": pose["focal_mm"], "focus_cm": pose["focus_cm"]})
    fps = ctx["s6"].get_display_rate().numerator / float(ctx["s6"].get_display_rate().denominator)
    return {"camera_frames": frames, "camera_keys": desired, "tick_rate": tick_rate,
            "score_rows": rows, "score_keys": core.score_keys(rows, fps), "display_fps": fps,
            "named_saves": [MASTER_PATH, S6_PATH, MATERIAL_PATH, MPC_PATH, WORLD_PATH],
            "runtime_prerequisite": "apply/build Scripts/patches/2026-10-11_job189_s6_warp_overlay.patch",
            "video_material_cvar": VIDEO_MATERIAL_CVAR}


def custom_input(name):
    pin = unreal.CustomInput()
    pin.set_editor_property("input_name", name)
    return pin


def create_mpc(tools, run):
    folder, name = MPC_PATH.rsplit("/", 1)
    mpc = tools.create_asset(name, folder, unreal.MaterialParameterCollection,
                             unreal.MaterialParameterCollectionFactoryNew())
    if mpc is None:
        stop(run, "CREATE_MPC")
    scalars = []
    for parameter in core.PARAMETERS:
        scalar = unreal.CollectionScalarParameter()
        scalar.set_editor_property("parameter_name", parameter)
        scalar.set_editor_property("default_value", 0.0)
        scalars.append(scalar)
    mpc.set_editor_property("scalar_parameters", scalars)
    return mpc


def create_material(tools, mpc, run):
    folder, name = MATERIAL_PATH.rsplit("/", 1)
    material = tools.create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
    if material is None:
        stop(run, "CREATE_MATERIAL")
    material.set_editor_property("material_domain", unreal.MaterialDomain.MD_UI)
    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    mel = unreal.MaterialEditingLibrary
    uv = mel.create_material_expression(material, unreal.MaterialExpressionTextureCoordinate, -1100, -300)
    texture = mel.create_material_expression(material, unreal.MaterialExpressionTextureObjectParameter, -1100, -180)
    texture.set_editor_property("parameter_name", "VideoTexture")
    fallback_texture = unreal.load_asset(ENGINE_WHITE)
    if fallback_texture is None:
        stop(run, "ENGINE_WHITE_TEXTURE_MISSING")
    texture.set_editor_property("texture", fallback_texture)
    nodes = {"UV": uv, "VideoTexture": texture}
    for index, parameter in enumerate(core.PARAMETERS):
        node = mel.create_material_expression(material, unreal.MaterialExpressionCollectionParameter,
                                              -1100, -40 + index * 90)
        node.set_editor_property("collection", mpc)
        node.set_editor_property("parameter_name", parameter)
        nodes[parameter] = node
    custom = mel.create_material_expression(material, unreal.MaterialExpressionCustom, -350, -120)
    custom.set_editor_property("description", "Job189 one-pass feedback-free S6 video warp")
    custom.set_editor_property("code", WARP_HLSL)
    custom.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT4)
    custom.set_editor_property("inputs", [custom_input(name) for name in ("UV", "VideoTexture") + core.PARAMETERS])
    for name, node in nodes.items():
        if not mel.connect_material_expressions(node, "", custom, name):
            stop(run, "MATERIAL_CONNECT|%s" % name)
    if not mel.connect_material_property(custom, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR):
        stop(run, "MATERIAL_OUTPUT")
    mel.recompile_material(material)
    return material


def get_or_create_assets(run):
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    created = []
    mpc = unreal.load_asset(MPC_PATH) if unreal.EditorAssetLibrary.does_asset_exist(MPC_PATH) else None
    if mpc is None:
        mpc = create_mpc(tools, run)
        created.append(MPC_PATH)
    names = sorted(str(name) for name in mpc.get_scalar_parameter_names())
    if names != sorted(core.PARAMETERS):
        stop(run, "MPC_PARAMETERS|%r" % names)
    material = unreal.load_asset(MATERIAL_PATH) if unreal.EditorAssetLibrary.does_asset_exist(MATERIAL_PATH) else None
    if material is None:
        material = create_material(tools, mpc, run)
        created.append(MATERIAL_PATH)
    if enum_name(material.get_editor_property("material_domain")) != "MD_UI":
        stop(run, "MATERIAL_DOMAIN|%s" % enum_name(material.get_editor_property("material_domain")))
    return mpc, material, created


def add_score_track(sequence, mpc, plan, run):
    if owned_tracks(sequence):
        stop(run, "OWNED_TRACK_EXISTS")
    track = sequence.add_track(unreal.MovieSceneMaterialParameterCollectionTrack)
    if track is None:
        stop(run, "ADD_MPC_TRACK")
    track.set_display_name(TRACK_NAME)
    track.set_editor_property("mpc", mpc)
    section = track.add_section()
    section.set_range(int(sequence.get_playback_start()), int(sequence.get_playback_end()))
    tpf = int(round(sequence.get_tick_resolution().numerator * sequence.get_display_rate().denominator
                    / float(sequence.get_tick_resolution().denominator * sequence.get_display_rate().numerator)))
    for parameter in core.PARAMETERS:
        for frame, value in plan["score_keys"][parameter]:
            section.add_scalar_parameter_key(parameter, unreal.FrameNumber(int(frame) * tpf), float(value),
                                             unreal.MovieSceneKeyInterpolation.LINEAR)
    return track


def content_file(package, extension=".uasset"):
    root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir())
    return os.path.join(root, package[len("/Game/"):].replace("/", os.sep) + extension)


def backup(ctx, run, existing_assets):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    directory = os.path.join(project, "Backups", "PreJob189S6Warp-%s-%s" % (run, stamp))
    os.makedirs(directory, exist_ok=False)
    packages = [(MASTER_PATH, ".uasset"), (S6_PATH, ".uasset"), (WORLD_PATH, ".umap")]
    packages.extend((path, ".uasset") for path in existing_assets)
    rows = []
    for package, extension in packages:
        source = content_file(package, extension)
        if not os.path.isfile(source):
            stop(run, "BACKUP_SOURCE_MISSING|%s" % source)
        target = os.path.join(directory, os.path.basename(source))
        shutil.copy2(source, target)
        if os.path.getsize(source) != os.path.getsize(target) or sha256(source) != sha256(target):
            stop(run, "BACKUP_VERIFY|%s" % package)
        rows.append({"package": package, "file": target, "bytes": os.path.getsize(target), "sha256": sha256(target)})
    return {"directory": directory, "files": rows}


def save_named(ctx, paths, run):
    for path in paths:
        if path == WORLD_PATH:
            continue
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
                stop(run, "SAVE_ASSET|%s" % path)
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        stop(run, "SAVE_LEVEL")
    after = dirty_census()
    if after["content"] or after["maps"]:
        stop(run, "DIRTY_AFTER_SAVE|%s" % json.dumps(after, sort_keys=True))


def verify_score_track(sequence, plan):
    snap = track_snapshot(sequence)
    if not snap or snap.get("mpc") != MPC_PATH:
        raise Stop("TRACK_READBACK_MPC|%r" % snap)
    for parameter in core.PARAMETERS:
        got = snap["channels"].get(parameter)
        wanted = plan["score_keys"][parameter]
        if got is None or len(got) != len(wanted):
            raise Stop("TRACK_READBACK_COUNT|%s|%r" % (parameter, got))
        for actual, expected in zip(got, wanted):
            if actual[0] != expected[0] or abs(actual[1] - expected[1]) > FLOAT_TOL:
                raise Stop("TRACK_READBACK_KEY|%s|%r|%r" % (parameter, actual, expected))
    return snap


def dry_path(run):
    return os.path.join(RECORDS, "job189_%s_dry.json" % run)


def apply_path(run):
    return os.path.join(RECORDS, "job189_%s_apply.json" % run)


def run_dry(ctx, args, rows, plan):
    before = snapshot(ctx)
    refusals = []
    apis = api_probe()
    for name in sorted(key for key, available in apis.items() if not available):
        refusals.append("PYTHON_API_MISSING|%s" % name)
    if before["warp_track"] is not None:
        refusals.append("OWNED_TRACK_ALREADY_EXISTS")
    if before["assets"]["mpc"] not in (None, sorted(core.PARAMETERS)):
        refusals.append("MPC_PATH_OCCUPIED_WITH_DIFFERENT_PARAMETERS")
    if before["assets"]["material"] and before["assets"]["material"].get("domain") != "MD_UI":
        refusals.append("MATERIAL_PATH_OCCUPIED_WITH_NON_UI_MATERIAL")
    if not before["media_contract"]["cue_exists"] or not before["media_contract"]["registry_exists"]:
        refusals.append("CURRENT_VIDEO_CONTRACT_FILES_MISSING_IN_THIS_CHECKOUT")
    elif not before["media_contract"]["s6_use_video"] or not before["media_contract"]["s6_registry"]:
        refusals.append("S6_VIDEO_NOT_ENABLED_OR_NOT_REGISTERED")
    if before["media_contract"].get("compiled_warp_material_cvar") != MATERIAL_PATH + ".M_S6Warp_UI":
        refusals.append("OVERLAY_HOOK_NOT_BUILT_OR_CVAR_OVERRIDDEN")
    report = {"schema": 1, "mode": "DRY", "run": args["run"], "args": args,
              "plan_digest": core.plan_digest(args, rows), "plan": plan, "before": before,
              "api_probe": apis, "refusals": refusals, "apply_ready": not refusals, "writes": 0}
    write_new(dry_path(args["run"]), report)
    if dirty_census() != {"content": [], "maps": []}:
        stop(args["run"], "DRY_DIRTIED_EDITOR")
    unreal.log("JOB189_DRY_OK|run=%s|apply_ready=%d|refusals=%d|preset=%s|move_s=%.3f|push_cm=%.1f|digest=%s|record=%s" %
               (args["run"], int(not refusals), len(refusals), args["preset"], args["move_seconds"],
                args["push_cm"], report["plan_digest"], dry_path(args["run"])))
    for refusal in refusals:
        unreal.log_warning("JOB189_REFUSAL|run=%s|%s" % (args["run"], refusal))


def run_apply(ctx, args, rows, plan):
    dry = read_json(dry_path(args["run"])) if os.path.isfile(dry_path(args["run"])) else {}
    digest = core.plan_digest(args, rows)
    if not dry.get("apply_ready") or dry.get("plan_digest") != digest:
        stop(args["run"], "CURRENT_GREEN_DRY_REQUIRED_WITH_SAME_RUN_AND_ARGS")
    before = snapshot(ctx)
    if before["warp_track"] is not None:
        stop(args["run"], "OWNED_TRACK_EXISTS")
    existing_assets = [path for path in (MPC_PATH, MATERIAL_PATH)
                       if unreal.EditorAssetLibrary.does_asset_exist(path)]
    backup_row = backup(ctx, args["run"], existing_assets)
    record_path = apply_path(args["run"])
    record = {"schema": 1, "status": "PREPARED_BEFORE_MUTATION", "run": args["run"],
              "args": args, "plan_digest": digest, "plan": plan, "before": before,
              "backup": backup_row, "existing_assets": existing_assets,
              "save_packages": plan["named_saves"]}
    write_new(record_path, record)
    mpc, material, created = get_or_create_assets(args["run"])
    add_score_track(ctx["s6"], mpc, plan, args["run"])
    lib = unreal.InfinityStageCameraPilotLibrary
    reports = []
    for item in plan["camera_keys"]:
        result = lib.key_passage_camera_pose(ctx["show"], ctx["guid"], int(item["frame"]),
                                             make_transform(item["transform"]), False,
                                             float(item["focal_mm"]), float(item["focus_cm"]))
        values = unwrap(result, 1, "KEY_CAMERA_%d" % item["frame"])
        reports.append(str(values[0]))
    target = dict(plan["camera_keys"][-1])
    entry_target = {"transform": target["transform"],
                    "focal_mm": before["entry"]["focal_mm"], "focus_cm": before["entry"]["focus_cm"]}
    set_camera_actor(ctx["entry"], entry_target)
    save_named(ctx, plan["named_saves"], args["run"])
    track_after = verify_score_track(ctx["s6"], plan)
    end_after = pose_row(unwrap(lib.get_passage_camera_pose(ctx["show"], ctx["guid"], ctx["end"]), 3, "END_READBACK"))
    entry_after = actor_state(ctx["entry"])
    delta = pose_delta(end_after, entry_after)
    if delta["position_cm"] > 0.01 or delta["rotation_deg_euler_max"] > 0.001:
        stop(args["run"], "SEAM_READBACK|%r" % delta)
    record.update({"status": "APPLIED_AND_READ_BACK", "created_assets": created,
                   "camera_reports": reports, "track_after": track_after, "p06_end_after": end_after,
                   "entry_after": entry_after, "seam_after": delta, "dirty_after": dirty_census()})
    replace_json(record_path, record)
    unreal.log("JOB189_APPLY_OK|run=%s|preset=%s|move_s=%.3f|push_cm=%.1f|score_keys=%d|seam_cm=%.4f|saved=5|created=%d|record=%s|backup=%s" %
               (args["run"], args["preset"], args["move_seconds"], args["push_cm"],
                sum(len(v) for v in plan["score_keys"].values()), delta["position_cm"], len(created),
                record_path, backup_row["directory"]))


def run_revert(ctx, args):
    path = args["record"]
    if not os.path.isabs(path):
        path = os.path.join(HERE, path)
    source = read_json(path)
    if source.get("status") != "APPLIED_AND_READ_BACK" or source.get("schema") != 1:
        stop(args["run"], "INCOMPLETE_APPLY_RECORD")
    tracks = owned_tracks(ctx["s6"])
    if len(tracks) != 1:
        stop(args["run"], "OWNED_TRACK_COUNT|%d" % len(tracks))
    existing_assets = [asset for asset in (MPC_PATH, MATERIAL_PATH)
                       if unreal.EditorAssetLibrary.does_asset_exist(asset)]
    backup_row = backup(ctx, args["run"], existing_assets)
    revert_path = os.path.join(RECORDS, "job189_%s_revert.json" % args["run"])
    record = {"schema": 1, "status": "PREPARED_BEFORE_MUTATION", "run": args["run"],
              "source_record": path, "before_revert": snapshot(ctx), "backup": backup_row,
              "retained_reusable_assets": existing_assets,
              "retention_reason": "project rule forbids permanent deletion without specific approval; Weird defaults to 0"}
    write_new(revert_path, record)
    ctx["s6"].remove_track(tracks[0])
    restore_channels(ctx["section"], source["before"]["camera_channels"])
    set_camera_actor(ctx["entry"], source["before"]["entry"])
    save_named(ctx, [MASTER_PATH, S6_PATH, WORLD_PATH], args["run"])
    after = snapshot(ctx)
    if after["warp_track"] is not None:
        stop(args["run"], "TRACK_REVERT_READBACK")
    if after["camera_channels"] != source["before"]["camera_channels"]:
        stop(args["run"], "CAMERA_CHANNEL_REVERT_READBACK")
    delta = pose_delta(after["entry"], source["before"]["entry"])
    if delta["position_cm"] > 0.01 or delta["rotation_deg_euler_max"] > 0.001:
        stop(args["run"], "ENTRY_REVERT_READBACK|%r" % delta)
    record.update({"status": "REVERTED_AND_READ_BACK", "after": after, "dirty_after": dirty_census()})
    replace_json(revert_path, record)
    unreal.log("JOB189_REVERT_OK|run=%s|source=%s|track_removed=1|camera_restored=1|assets_retained=%d|record=%s|backup=%s" %
               (args["run"], path, len(existing_assets), revert_path, backup_row["directory"]))


def main():
    raw = read_json(ARGS)
    try:
        args = core.validate_args(raw)
        rows = core.compile_score(read_json(SCORES), args["preset"])
        ctx = find_context(args["run"])
        plan = proposal(ctx, args, rows)
        if args["mode"] == "DRY":
            run_dry(ctx, args, rows, plan)
        elif args["mode"] == "APPLY":
            run_apply(ctx, args, rows, plan)
        else:
            run_revert(ctx, args)
    except Exception as exc:
        run = str(raw.get("run", "UNKNOWN"))
        if not isinstance(exc, Stop):
            unreal.log_error("JOB189_FAILED|run=%s|%r" % (run, exc))
        raise

