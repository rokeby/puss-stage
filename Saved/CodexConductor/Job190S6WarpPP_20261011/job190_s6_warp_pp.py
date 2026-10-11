"""Job 190: live-3D S6 post-process warp and P06 -> S6 move-in.

Offline-authored. Run only through ExecuteProjectPythonFile after the conductor
releases the editor. DRY is the default. APPLY/REVERT require exact confirmation.

APPLY, if a green DRY can prove the ownership boundary, creates (or reuses
without editing) one create-only post-process material
and the Job 189 MPC design, creates one unbound PostProcessVolume whose default
BlendWeight is zero, and keys that weight only inside LS_DevScene_06. It adds a
keyed MPC score to S6. The optional P06 dolly may key only the P06/Master camera.
The nested KlaraHookin shot is read-only; when continuity would require changing
its camera, DRY refuses APPLY and records that reason. No build is required.
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
import job190_core as core

ARGS = os.path.join(HERE, "job190_args.json")
SCORES = os.path.join(HERE, "warp_scores.json")
VOID_PROPOSAL = os.path.join(HERE, "void_proposal.json")
RECORDS = os.path.join(HERE, "records")
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
WORLD_PATH = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
MASTER_PATH = core.MASTER_PATH
S6_PATH = core.S6_PATH
SHOT_PATH = core.NESTED_SHOT_PATH
MPC_PATH = core.MPC_PATH
MATERIAL_PATH = core.MATERIAL_PATH
METAHUMAN_BINDING = "BP_MHC_Elder_Female"
FIRST_CAMERA_BINDING = "CineCameraActor5"
VOLUME_LABEL = "S6 Warp PostProcess (Job190)"
VOLUME_TAG = "Codex.Job190.S6WarpPP"
SCORE_TRACK_NAME = "S6 Warp Score (Job190)"
VOLUME_BINDING_NAME = "S6 Warp PostProcess (Job190)"
EXPECTED_EXPRESSIONS = 16
EXPECTED_CUSTOM_DESCRIPTIONS = (
    "Job190 S6 warp UV B",
    "Job190 S6 warp UV G",
    "Job190 S6 warp UV R",
    "Job190 S6 warp colour",
)
CAMERA_CHANNELS = (
    "Camera.LongitudinalOffsetCm", "Camera.LateralOffsetCm", "Camera.HeightOffsetCm",
    "Camera.PitchDegrees", "Camera.YawDegrees", "Camera.RollDegrees",
)
FLOAT_TOL = 1.0e-4

WARP_UV_HLSL = r"""
float master = saturate(Weird);
float2 centre = ScreenUV.xy - 0.5;
float radius = length(centre);
float angle = atan2(centre.y, centre.x);

// Texture-free panning pseudo-noise and a slow swirl about screen centre.
float n1 = sin(ScreenUV.y * 17.0 + Phase * 0.73 + sin(ScreenUV.x * 11.0 - Phase * 0.37));
float n2 = cos(ScreenUV.x * 13.0 - Phase * 0.51 + cos(ScreenUV.y * 9.0 + Phase * 0.29));
float swirl = sin(radius * 18.0 - Phase * 0.43) * exp(-radius * 2.2);
angle += master * saturate(Warp) * (0.42 * swirl + 0.08 * n1);
float2 warped = float2(cos(angle), sin(angle)) * radius;
warped += master * saturate(Warp) * float2(n1, n2) * (0.008 + 0.018 * radius);

// Polar kaleidoscope fold. Weird or Mirror at zero is exact pass-through.
float blades = 2.0 + floor(saturate(Mirror) * 6.0);
float folded = abs(frac((atan2(warped.y, warped.x) / 6.2831853) * blades + 0.5) * 2.0 - 1.0);
float foldAngle = (folded - 0.5) * (6.2831853 / blades);
float2 kaleido = float2(cos(foldAngle), sin(foldAngle)) * length(warped);
warped = lerp(warped, kaleido, master * saturate(Mirror));

float2 tangent = normalize(float2(-warped.y, warped.x) + float2(1e-5, 0.0));
float split = master * saturate(ChromaSplit) * 0.018 * __SPLIT_SIGN__;
return saturate(warped + 0.5 + tangent * split);
"""

WARP_COLOUR_HLSL = r"""
float master = saturate(Weird);
float3 colour = float3(RScene.r, GScene.g, BScene.b);

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

// Swap luminance while preserving chroma.
float lum = dot(colour, float3(0.299, 0.587, 0.114));
float3 lumInverted = saturate(colour + (1.0 - 2.0 * lum));
colour = lerp(colour, lumInverted, master * saturate(Invert));

// Posterized triangular solarization at the intense end.
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
    unreal.log_error("JOB190_FAILED|run=%s|%s" % (run, reason))
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
    return str(unreal.GuidLibrary.conv_guid_to_string(value)).replace("-", "").replace("{", "").replace("}", "").upper()


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


def find_channel(section, wanted):
    hits = [channel for channel in section.get_all_channels()
            if str(channel.get_editor_property("channel_name")) == wanted
            or str(channel.get_editor_property("channel_name")).startswith(wanted + "_")]
    if len(hits) != 1:
        raise Stop("CHANNEL_COUNT|%s|%d" % (wanted, len(hits)))
    return hits[0]


def channel_base(channel):
    name = str(channel.get_editor_property("channel_name"))
    tail = name.rsplit("_", 1)
    return tail[0] if len(tail) == 2 and tail[1].isdigit() else name


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


def general_channel_snapshot(section, names):
    channels = {channel_base(channel): channel for channel in section.get_all_channels()}
    if not all(name in channels for name in names):
        raise Stop("TRANSFORM_CHANNELS_MISSING|have=%r|want=%r" % (sorted(channels), sorted(names)))
    return {name: {
        "default": float(channels[name].get_default()) if channels[name].has_default() else None,
        "keys": sorted((key_row(key) for key in channels[name].get_keys()),
                       key=lambda row: (row["tick"], row["sub"])),
    } for name in names}


def find_context(run):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world is None or asset_id(world) != WORLD_PATH:
        stop(run, "WRONG_WORLD|%r" % asset_id(world))
    if editor.get_game_world() is not None:
        stop(run, "PIE_OR_SIE_ACTIVE")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        stop(run, "SEQUENCER_OPEN")
    census = dirty_census()
    if census["content"] or census["maps"]:
        stop(run, "DIRTY_BEFORE|%s" % json.dumps(census, sort_keys=True))
    show = unreal.load_asset(SHOW_PATH)
    master = unreal.load_asset(MASTER_PATH)
    s6 = unreal.load_asset(S6_PATH)
    shot = unreal.load_asset(SHOT_PATH)
    if show is None or master is None or s6 is None or shot is None:
        stop(run, "ASSET_LOAD|show=%r|master=%r|s6=%r|shot=%r" % (show, master, s6, shot))
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
    actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in actor_sub.get_all_level_actors():
        if isinstance(actor, unreal.CineCameraActor) and actor.actor_has_tag("InfinityStage.SceneEntry"):
            if str(actor.get_actor_label()).startswith("Scene 6 "):
                entries.append(actor)
    if len(entries) != 1:
        stop(run, "S6_ENTRY_COUNT|%d" % len(entries))
    frame_range = unwrap(unreal.InfinityStageCameraPilotLibrary.get_passage_frame_range(show, guid), 2, "P06_RANGE")
    return {"editor": editor, "actor_sub": actor_sub, "world": world, "show": show, "master": master,
            "s6": s6, "shot": shot, "guid": guid, "section": sections[0], "entry": entries[0],
            "start": int(frame_range[0]), "end": int(frame_range[1]), "dirty": census}


def first_camera_binding(ctx):
    rows = [binding for binding in ctx["shot"].get_bindings()
            if str(binding.get_display_name()) == FIRST_CAMERA_BINDING]
    return rows[0] if len(rows) == 1 else None


def first_camera_transform_section(ctx):
    binding = first_camera_binding(ctx)
    if binding is None:
        return None
    sections = [section for track in binding.get_tracks()
                if track.get_class().get_name() == "MovieScene3DTransformTrack"
                for section in track.get_sections()]
    return sections[0] if len(sections) == 1 else None


def first_camera_transform_state(ctx):
    section = first_camera_transform_section(ctx)
    names = ("Location.X", "Location.Y", "Location.Z", "Rotation.X", "Rotation.Y", "Rotation.Z")
    if section is None:
        return {"section_count": 0}
    channels = general_channel_snapshot(section, names)
    pose = None
    if all(channels[name]["default"] is not None and not channels[name]["keys"] for name in names):
        pose = {
            "location": [channels["Location.X"]["default"], channels["Location.Y"]["default"],
                         channels["Location.Z"]["default"]],
            "rotation": [channels["Rotation.X"]["default"], channels["Rotation.Y"]["default"],
                         channels["Rotation.Z"]["default"]],
            "scale": [1.0, 1.0, 1.0],
        }
    return {"section_count": 1, "channels": channels, "pose": pose}


def transform_delta(a, b):
    if not a or not b:
        return None
    return {
        "position_cm": math.sqrt(sum((x - y) ** 2 for x, y in zip(a["location"], b["location"]))),
        "rotation_deg_euler_max": max(abs(x - y) for x, y in zip(a["rotation"], b["rotation"])),
    }


def route_snapshot(ctx):
    shot_sections = []
    for track in ctx["s6"].get_tracks():
        if track.get_class().get_name() != "MovieSceneCinematicShotTrack":
            continue
        for section in track.get_sections():
            sequence = section.get_sequence()
            if asset_id(sequence) == SHOT_PATH:
                shot_sections.append({"start": int(section.get_start_frame()), "end": int(section.get_end_frame())})
    bindings = list(ctx["shot"].get_bindings())
    names = [str(binding.get_display_name()) for binding in bindings]
    by_guid = {guid_text(binding.get_id()): binding for binding in bindings}
    cuts = []
    for track in ctx["shot"].get_tracks():
        if track.get_class().get_name() != "MovieSceneCameraCutTrack":
            continue
        for section in track.get_sections():
            binding_guid = guid_text(section.get_camera_binding_id().get_editor_property("guid"))
            binding = by_guid.get(binding_guid)
            cuts.append({"start": int(section.get_start_frame()), "end": int(section.get_end_frame()),
                         "binding": str(binding.get_display_name()) if binding else None,
                         "guid": binding_guid})
    cuts.sort(key=lambda row: (row["start"], row["end"]))
    metahumans = [binding for binding in bindings if str(binding.get_display_name()) == METAHUMAN_BINDING]
    cameras = [binding for binding in bindings if str(binding.get_display_name()) == FIRST_CAMERA_BINDING]
    camera_transform = first_camera_transform_state(ctx)
    entry_transform = actor_state(ctx["entry"])["transform"]
    return {
        "parent_sequence": S6_PATH,
        "shot_sequence": SHOT_PATH,
        "shot_sections": shot_sections,
        "metahuman_binding_count": len(metahumans),
        "metahuman_binding": METAHUMAN_BINDING if len(metahumans) == 1 else None,
        "first_camera_binding_count": len(cameras),
        "first_camera_cut": cuts[0] if cuts else None,
        "first_camera_transform": camera_transform,
        "first_camera_to_entry_delta": transform_delta(camera_transform.get("pose"), entry_transform),
        "camera_cut_count": len(cuts),
        "binding_names": sorted(names),
    }


def owned_score_tracks(sequence):
    return [track for track in sequence.get_tracks()
            if track.get_class().get_name() == "MovieSceneMaterialParameterCollectionTrack"
            and str(track.get_display_name()) == SCORE_TRACK_NAME]


def conflicting_mpc_tracks(sequence):
    rows = []
    for track in sequence.get_tracks():
        if track.get_class().get_name() != "MovieSceneMaterialParameterCollectionTrack":
            continue
        if asset_id(track.get_editor_property("mpc")) == MPC_PATH:
            rows.append(str(track.get_display_name()))
    return rows


def score_track_snapshot(sequence):
    tracks = owned_score_tracks(sequence)
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


def volume_actors(ctx):
    return [actor for actor in ctx["actor_sub"].get_all_level_actors()
            if isinstance(actor, unreal.PostProcessVolume)
            and (str(actor.get_actor_label()) == VOLUME_LABEL or actor.actor_has_tag(VOLUME_TAG))]


def volume_bindings(sequence):
    return [binding for binding in sequence.get_bindings()
            if str(binding.get_display_name()) == VOLUME_BINDING_NAME]


def blendable_rows(volume):
    settings = volume.get_editor_property("settings")
    weighted = settings.get_editor_property("weighted_blendables")
    result = []
    for item in weighted.get_editor_property("array"):
        obj = item.get_editor_property("object")
        result.append({"object": asset_id(obj), "weight": float(item.get_editor_property("weight"))})
    return sorted(result, key=lambda row: (str(row["object"]), row["weight"]))


def volume_snapshot(ctx):
    actors = volume_actors(ctx)
    bindings = volume_bindings(ctx["s6"])
    result = {"actor_count": len(actors), "binding_count": len(bindings)}
    if len(actors) == 1:
        actor = actors[0]
        result["actor"] = {
            "path": actor.get_path_name(), "label": str(actor.get_actor_label()),
            "enabled": bool(actor.get_editor_property("enabled")),
            "unbound": bool(actor.get_editor_property("unbound")),
            "blend_weight": float(actor.get_editor_property("blend_weight")),
            "priority": float(actor.get_editor_property("priority")),
            "blendables": blendable_rows(actor),
        }
    if len(bindings) == 1:
        binding = bindings[0]
        tracks = [track for track in binding.get_tracks()
                  if track.get_class().get_name() == "MovieSceneFloatTrack"
                  and str(track.get_property_name()) == "BlendWeight"]
        result["binding"] = {"guid": guid_text(binding.get_id()), "track_count": len(tracks)}
        if len(tracks) == 1 and len(tracks[0].get_sections()) == 1:
            section = list(tracks[0].get_sections())[0]
            channels = list(section.get_all_channels())
            result["binding"].update({
                "property": [str(tracks[0].get_property_name()), str(tracks[0].get_property_path())],
                "range": [int(section.get_start_frame()), int(section.get_end_frame())],
                "channel_count": len(channels),
                "default": float(channels[0].get_default()) if len(channels) == 1 and channels[0].has_default() else None,
            })
    return result


def material_state():
    result = {"mpc": None, "material": None}
    if unreal.EditorAssetLibrary.does_asset_exist(MPC_PATH):
        mpc = unreal.load_asset(MPC_PATH)
        result["mpc"] = sorted(str(name) for name in mpc.get_scalar_parameter_names()) if mpc else ["LOAD_FAILED"]
    if unreal.EditorAssetLibrary.does_asset_exist(MATERIAL_PATH):
        material = unreal.load_asset(MATERIAL_PATH)
        if material is None:
            result["material"] = {"load": "FAILED"}
        else:
            expressions = list(unreal.MaterialEditingLibrary.get_material_expressions(material))
            customs = sorted(str(expr.get_editor_property("description")) for expr in expressions
                             if expr.get_class().get_name() == "MaterialExpressionCustom")
            scenes = [enum_name(expr.get_editor_property("scene_texture_id")) for expr in expressions
                      if expr.get_class().get_name() == "MaterialExpressionSceneTexture"]
            collections = sorted(str(expr.get_editor_property("parameter_name")) for expr in expressions
                                 if expr.get_class().get_name() == "MaterialExpressionCollectionParameter")
            result["material"] = {
                "domain": enum_name(material.get_editor_property("material_domain")),
                "blendable_location": enum_name(material.get_editor_property("blendable_location")),
                "expressions": len(expressions), "custom_descriptions": customs,
                "scene_texture_ids": sorted(scenes), "collection_parameters": collections,
            }
    return result


def material_state_valid(state):
    material = state.get("material")
    return bool(material
                and material.get("domain") == "MD_POST_PROCESS"
                and material.get("expressions") == EXPECTED_EXPRESSIONS
                and material.get("custom_descriptions") == sorted(EXPECTED_CUSTOM_DESCRIPTIONS)
                and material.get("scene_texture_ids") == ["PPI_POST_PROCESS_INPUT0"] * 3
                and material.get("collection_parameters") == sorted(core.PARAMETERS))


def api_probe():
    names = (
        "MaterialParameterCollection", "MaterialParameterCollectionFactoryNew", "CollectionScalarParameter",
        "Material", "MaterialFactoryNew", "MaterialEditingLibrary", "MaterialExpressionScreenPosition",
        "MaterialExpressionSceneTexture", "MaterialExpressionCollectionParameter", "MaterialExpressionCustom",
        "CustomInput", "MovieSceneMaterialParameterCollectionTrack", "MovieSceneFloatTrack",
        "MovieSceneKeyInterpolation", "PostProcessVolume", "InfinityStageCameraPilotLibrary",
    )
    result = {name: hasattr(unreal, name) for name in names}
    result["MaterialDomain.MD_POST_PROCESS"] = hasattr(getattr(unreal, "MaterialDomain", None), "MD_POST_PROCESS")
    result["SceneTextureId.PPI_POST_PROCESS_INPUT0"] = hasattr(
        getattr(unreal, "SceneTextureId", None), "PPI_POST_PROCESS_INPUT0")
    result["CustomMaterialOutputType.CMOT_FLOAT2"] = hasattr(
        getattr(unreal, "CustomMaterialOutputType", None), "CMOT_FLOAT2")
    result["CustomMaterialOutputType.CMOT_FLOAT4"] = hasattr(
        getattr(unreal, "CustomMaterialOutputType", None), "CMOT_FLOAT4")
    result["MaterialProperty.MP_EMISSIVE_COLOR"] = hasattr(
        getattr(unreal, "MaterialProperty", None), "MP_EMISSIVE_COLOR")
    result["BlendableLocation.BL_SCENE_COLOR_AFTER_TONEMAPPING"] = hasattr(
        getattr(unreal, "BlendableLocation", None), "BL_SCENE_COLOR_AFTER_TONEMAPPING")
    result["PostProcessVolume.add_or_update_blendable"] = hasattr(
        getattr(unreal, "PostProcessVolume", None), "add_or_update_blendable")
    result["MovieSceneParameterSection.add_scalar_parameter_key"] = hasattr(
        getattr(unreal, "MovieSceneParameterSection", None), "add_scalar_parameter_key")
    try:
        settings = unreal.PostProcessSettings()
        weighted = settings.get_editor_property("weighted_blendables")
        weighted.get_editor_property("array")
        result["PostProcessSettings.weighted_blendables.array"] = True
    except Exception:
        result["PostProcessSettings.weighted_blendables.array"] = False
    return result


def snapshot(ctx):
    lib = unreal.InfinityStageCameraPilotLibrary
    end_pose = pose_row(unwrap(lib.get_passage_camera_pose(ctx["show"], ctx["guid"], ctx["end"]), 3, "P06_END_POSE"))
    entry = actor_state(ctx["entry"])
    return {
        "camera_channels": channel_snapshot(ctx["section"]), "entry": entry,
        "p06_end": end_pose, "seam_delta": pose_delta(end_pose, entry),
        "route": route_snapshot(ctx), "score_track": score_track_snapshot(ctx["s6"]),
        "mpc_track_conflicts": conflicting_mpc_tracks(ctx["s6"]),
        "volume": volume_snapshot(ctx), "assets": material_state(), "dirty": dirty_census(),
    }


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
    plan = {
        "camera_frames": frames, "camera_keys": desired, "tick_rate": tick_rate,
        "score_rows": rows, "score_keys": core.score_keys(rows, fps), "display_fps": fps,
        "volume": {"label": VOLUME_LABEL, "tag": VOLUME_TAG, "priority": args["volume_priority"],
                   "default_blend_weight": 0.0, "s6_blend_weight": 1.0},
        "void": read_json(VOID_PROPOSAL),
        "named_saves": [MASTER_PATH, S6_PATH, MATERIAL_PATH, MPC_PATH, WORLD_PATH],
        "mpc_key_sequence": S6_PATH,
        "camera_edit_targets": [MASTER_PATH],
        "nested_shot_policy": "read_only_never_save_never_edit",
        "runtime_prerequisite": "none; post-process route requires no C++ patch and no build",
    }
    core.validate_named_saves(plan["named_saves"], require_apply_set=True)
    core.validate_mpc_key_sequence(plan["mpc_key_sequence"])
    core.validate_camera_edit_targets(plan["camera_edit_targets"])
    return plan


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
    if unreal.EditorAssetLibrary.does_asset_exist(MATERIAL_PATH):
        stop(run, "CREATE_ONLY_MATERIAL_PATH_ALREADY_EXISTS")
    folder, name = MATERIAL_PATH.rsplit("/", 1)
    material = tools.create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
    mel = unreal.MaterialEditingLibrary
    if material is None or int(mel.get_num_material_expressions(material)) != 0:
        stop(run, "CREATE_MATERIAL_NOT_EMPTY")
    material.set_editor_property("material_domain", unreal.MaterialDomain.MD_POST_PROCESS)
    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    material.set_editor_property(
        "blendable_location", unreal.BlendableLocation.BL_SCENE_COLOR_AFTER_TONEMAPPING)
    material.set_editor_property("blendable_priority", 190)
    material.set_editor_property("is_blendable", True)

    screen = mel.create_material_expression(material, unreal.MaterialExpressionScreenPosition, -1500, -350)
    nodes = {"ScreenUV": screen}
    for index, parameter in enumerate(core.PARAMETERS):
        node = mel.create_material_expression(material, unreal.MaterialExpressionCollectionParameter,
                                              -1500, -150 + index * 95)
        node.set_editor_property("collection", mpc)
        node.set_editor_property("parameter_name", parameter)
        nodes[parameter] = node

    scene_nodes = {}
    for index, (suffix, sign) in enumerate((("R", 1.0), ("G", 0.0), ("B", -1.0))):
        uv = mel.create_material_expression(material, unreal.MaterialExpressionCustom, -900, -350 + index * 260)
        uv.set_editor_property("description", "Job190 S6 warp UV " + suffix)
        uv.set_editor_property("code", WARP_UV_HLSL.replace("__SPLIT_SIGN__", "%.1f" % sign))
        uv.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT2)
        uv.set_editor_property("inputs", [custom_input(value) for value in
                                          ("ScreenUV", "Weird", "Warp", "Mirror", "ChromaSplit", "Phase")])
        for value in ("ScreenUV", "Weird", "Warp", "Mirror", "ChromaSplit", "Phase"):
            if not mel.connect_material_expressions(nodes[value], "", uv, value):
                stop(run, "MATERIAL_CONNECT|%s->UV%s.%s" % (value, suffix, value))
        scene = mel.create_material_expression(material, unreal.MaterialExpressionSceneTexture,
                                               -500, -350 + index * 260)
        scene.set_editor_property("scene_texture_id", unreal.SceneTextureId.PPI_POST_PROCESS_INPUT0)
        scene.set_editor_property("filtered", True)
        if not mel.connect_material_expressions(uv, "", scene, "Coordinates"):
            stop(run, "MATERIAL_CONNECT|UV%s->Scene%s.Coordinates" % (suffix, suffix))
        scene_nodes[suffix] = scene

    colour = mel.create_material_expression(material, unreal.MaterialExpressionCustom, -80, -80)
    colour.set_editor_property("description", "Job190 S6 warp colour")
    colour.set_editor_property("code", WARP_COLOUR_HLSL)
    colour.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT4)
    colour.set_editor_property("inputs", [custom_input(value) for value in
                                          ("RScene", "GScene", "BScene", "Weird", "Invert", "HueDrift", "Solarize")])
    for suffix in ("R", "G", "B"):
        if not mel.connect_material_expressions(scene_nodes[suffix], "", colour, suffix + "Scene"):
            stop(run, "MATERIAL_CONNECT|Scene%s->Colour" % suffix)
    for value in ("Weird", "Invert", "HueDrift", "Solarize"):
        if not mel.connect_material_expressions(nodes[value], "", colour, value):
            stop(run, "MATERIAL_CONNECT|%s->Colour" % value)
    if not mel.connect_material_property(colour, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR):
        stop(run, "MATERIAL_OUTPUT")
    if int(mel.get_num_material_expressions(material)) != EXPECTED_EXPRESSIONS:
        stop(run, "MATERIAL_EXPRESSION_COUNT|%d" % mel.get_num_material_expressions(material))
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
    elif not material_state_valid(material_state()):
        stop(run, "CREATE_ONLY_MATERIAL_FINGERPRINT_MISMATCH")
    return mpc, material, created


def add_score_track(sequence, mpc, plan, run):
    if conflicting_mpc_tracks(sequence):
        stop(run, "MPC_TRACK_CONFLICT|%r" % conflicting_mpc_tracks(sequence))
    track = sequence.add_track(unreal.MovieSceneMaterialParameterCollectionTrack)
    if track is None:
        stop(run, "ADD_MPC_TRACK")
    track.set_display_name(SCORE_TRACK_NAME)
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


def create_volume_and_track(ctx, material, plan, run):
    if volume_actors(ctx) or volume_bindings(ctx["s6"]):
        stop(run, "OWNED_VOLUME_OR_BINDING_EXISTS")
    volume = ctx["actor_sub"].spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector(0.0, 0.0, 0.0),
                                                     unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if volume is None:
        stop(run, "SPAWN_POST_PROCESS_VOLUME")
    volume.set_actor_label(VOLUME_LABEL)
    volume.set_editor_property("tags", list(volume.get_editor_property("tags")) + [unreal.Name(VOLUME_TAG)])
    volume.set_editor_property("enabled", True)
    volume.set_editor_property("unbound", True)
    volume.set_editor_property("blend_weight", 0.0)
    volume.set_editor_property("priority", float(plan["volume"]["priority"]))
    volume.add_or_update_blendable(material, 1.0)
    if blendable_rows(volume) != [{"object": MATERIAL_PATH, "weight": 1.0}]:
        stop(run, "VOLUME_BLENDABLE_READBACK|%r" % blendable_rows(volume))

    if volume_bindings(ctx["s6"]):
        stop(run, "BINDING_LOOKUP_CHANGED_BEFORE_ADD")
    binding = ctx["s6"].add_possessable(volume)
    if binding is None or not binding.is_valid():
        stop(run, "ADD_VOLUME_POSSESSABLE")
    binding.set_display_name(VOLUME_BINDING_NAME)
    if len(volume_bindings(ctx["s6"])) != 1:
        stop(run, "VOLUME_BINDING_READBACK")
    track = binding.add_track(unreal.MovieSceneFloatTrack)
    track.set_property_name_and_path("BlendWeight", "blend_weight")
    track.set_display_name("S6 Warp Enabled (Job190)")
    section = track.add_section()
    section.set_range(int(ctx["s6"].get_playback_start()), int(ctx["s6"].get_playback_end()))
    section.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
    channels = list(section.get_all_channels())
    if len(channels) != 1:
        stop(run, "BLEND_WEIGHT_CHANNEL_COUNT|%d" % len(channels))
    channels[0].set_default(1.0)
    return volume, binding


def content_file(package, extension=".uasset"):
    root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir())
    return os.path.join(root, package[len("/Game/"):].replace("/", os.sep) + extension)


def backup(ctx, run, existing_assets):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    directory = os.path.join(project, "Backups", "PreJob190S6WarpPP-%s-%s" % (run, stamp))
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


def assert_dirty_scope(paths, run, stage):
    try:
        core.validate_named_saves(paths, require_apply_set=(stage == "APPLY"))
    except ValueError as exc:
        stop(run, "%s_NAMED_SAVE_POLICY|%s" % (stage, exc))
    census = dirty_census()
    actual = set(census["content"] + census["maps"])
    allowed = set(paths)
    foreign = sorted(actual - allowed)
    if foreign:
        stop(run, "%s_FOREIGN_DIRTY|%s" % (stage, json.dumps(foreign)))
    return census


def save_named(paths, run):
    try:
        core.validate_named_saves(paths)
    except ValueError as exc:
        stop(run, "NAMED_SAVE_POLICY|%s" % exc)
    for path in paths:
        if path == WORLD_PATH:
            continue
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
                stop(run, "SAVE_ASSET|%s" % path)
    if WORLD_PATH in paths:
        if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
            stop(run, "SAVE_LEVEL")
    after = dirty_census()
    if after["content"] or after["maps"]:
        stop(run, "DIRTY_AFTER_SAVE|%s" % json.dumps(after, sort_keys=True))


def verify_score_track(sequence, plan):
    snap = score_track_snapshot(sequence)
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


def route_problems(route):
    problems = []
    if len(route["shot_sections"]) != 1:
        problems.append("S6_SHOT_SECTION_COUNT|%d" % len(route["shot_sections"]))
    if route["metahuman_binding_count"] != 1:
        problems.append("S6_METAHUMAN_BINDING_COUNT|%d" % route["metahuman_binding_count"])
    if route["first_camera_binding_count"] != 1:
        problems.append("S6_FIRST_CAMERA_BINDING_COUNT|%d" % route["first_camera_binding_count"])
    first = route.get("first_camera_cut") or {}
    if first.get("binding") != FIRST_CAMERA_BINDING:
        problems.append("S6_FIRST_CAMERA_CUT|%r" % first)
    camera = route.get("first_camera_transform") or {}
    if camera.get("section_count") != 1 or camera.get("pose") is None:
        problems.append("S6_FIRST_CAMERA_TRANSFORM_NOT_STATIC_DEFAULTS")
    alignment = route.get("first_camera_to_entry_delta")
    if (alignment is None or alignment["position_cm"] > 0.01
            or alignment["rotation_deg_euler_max"] > 0.001):
        problems.append("S6_FIRST_CAMERA_NOT_ALIGNED_TO_ENTRY|%r" % alignment)
    return problems


def dry_path(run):
    return os.path.join(RECORDS, "job190_%s_dry.json" % run)


def apply_path(run):
    return os.path.join(RECORDS, "job190_%s_apply.json" % run)


def run_dry(ctx, args, rows, plan):
    before = snapshot(ctx)
    refusals = []
    apis = api_probe()
    for name in sorted(key for key, available in apis.items() if not available):
        refusals.append("PYTHON_API_MISSING|%s" % name)
    refusals.extend(route_problems(before["route"]))
    nested_pose = (before["route"].get("first_camera_transform") or {}).get("pose")
    predicted_nested_cut = transform_delta(plan["camera_keys"][-1]["transform"], nested_pose)
    if (predicted_nested_cut is None or predicted_nested_cut["position_cm"] > 0.01
            or predicted_nested_cut["rotation_deg_euler_max"] > 0.001):
        refusals.append(
            "MOVE_IN_DRY_ONLY|P06_MASTER_ONLY_CANNOT_MATCH_READ_ONLY_NESTED_CAMERA|%r"
            % predicted_nested_cut)
    if before["score_track"] is not None or before["mpc_track_conflicts"]:
        refusals.append("S6_MPC_TRACK_ALREADY_EXISTS|%r" % before["mpc_track_conflicts"])
    if before["volume"]["actor_count"] or before["volume"]["binding_count"]:
        refusals.append("OWNED_VOLUME_OR_BINDING_ALREADY_EXISTS")
    if before["assets"]["mpc"] not in (None, sorted(core.PARAMETERS)):
        refusals.append("MPC_PATH_OCCUPIED_WITH_DIFFERENT_PARAMETERS")
    if before["assets"]["material"] is not None and not material_state_valid(before["assets"]):
        refusals.append("CREATE_ONLY_MATERIAL_PATH_OCCUPIED_WITH_DIFFERENT_GRAPH")
    if args["void_mode"] != "off":
        refusals.append("VOID_PROPOSAL_REQUIRES_LIVE_STENCIL_AND_HAIR_COVERAGE_PROOF")
    report = {
        "schema": 1, "mode": "DRY", "run": args["run"], "args": args,
        "plan_digest": core.plan_digest(args, rows), "plan": plan, "before": before,
        "api_probe": apis, "predicted_nested_cut": predicted_nested_cut,
        "refusals": refusals, "apply_ready": not refusals, "writes": 0,
    }
    write_new(dry_path(args["run"]), report)
    if dirty_census() != {"content": [], "maps": []}:
        stop(args["run"], "DRY_DIRTIED_EDITOR")
    unreal.log("JOB190_DRY_OK|run=%s|apply_ready=%d|refusals=%d|preset=%s|move_s=%.3f|push_cm=%.1f|route=live3d|build=none|digest=%s|record=%s" %
               (args["run"], int(not refusals), len(refusals), args["preset"], args["move_seconds"],
                args["push_cm"], report["plan_digest"], dry_path(args["run"])))
    for refusal in refusals:
        unreal.log_warning("JOB190_REFUSAL|run=%s|%s" % (args["run"], refusal))


def run_apply(ctx, args, rows, plan):
    dry = read_json(dry_path(args["run"])) if os.path.isfile(dry_path(args["run"])) else {}
    digest = core.plan_digest(args, rows)
    if not dry.get("apply_ready") or dry.get("plan_digest") != digest:
        stop(args["run"], "CURRENT_GREEN_DRY_REQUIRED_WITH_SAME_RUN_AND_ARGS")
    try:
        core.validate_named_saves(plan["named_saves"], require_apply_set=True)
        core.validate_mpc_key_sequence(plan["mpc_key_sequence"])
        core.validate_camera_edit_targets(plan["camera_edit_targets"])
    except ValueError as exc:
        stop(args["run"], "JOB194_OWNERSHIP_POLICY|%s" % exc)
    before = snapshot(ctx)
    if route_problems(before["route"]):
        stop(args["run"], "S6_ROUTE_DRIFTED|%r" % route_problems(before["route"]))
    if before["score_track"] is not None or before["mpc_track_conflicts"]:
        stop(args["run"], "OWNED_OR_CONFLICTING_MPC_TRACK_EXISTS")
    if before["volume"]["actor_count"] or before["volume"]["binding_count"]:
        stop(args["run"], "OWNED_VOLUME_OR_BINDING_EXISTS")
    existing_assets = [path for path in (MPC_PATH, MATERIAL_PATH)
                       if unreal.EditorAssetLibrary.does_asset_exist(path)]
    backup_row = backup(ctx, args["run"], existing_assets)
    record_path = apply_path(args["run"])
    record = {
        "schema": 1, "status": "PREPARED_BEFORE_MUTATION", "run": args["run"],
        "args": args, "plan_digest": digest, "plan": plan, "before": before,
        "backup": backup_row, "existing_assets": existing_assets, "save_packages": plan["named_saves"],
    }
    write_new(record_path, record)

    mpc, material, created = get_or_create_assets(args["run"])
    volume, binding = create_volume_and_track(ctx, material, plan, args["run"])
    if asset_id(ctx["s6"]) != core.validate_mpc_key_sequence(plan["mpc_key_sequence"]):
        stop(args["run"], "MPC_KEY_SEQUENCE_MISMATCH")
    add_score_track(ctx["s6"], mpc, plan, args["run"])
    lib = unreal.InfinityStageCameraPilotLibrary
    camera_reports = []
    for item in plan["camera_keys"]:
        result = lib.key_passage_camera_pose(ctx["show"], ctx["guid"], int(item["frame"]),
                                             make_transform(item["transform"]), False,
                                             float(item["focal_mm"]), float(item["focus_cm"]))
        camera_reports.append(str(unwrap(result, 1, "KEY_CAMERA_%d" % item["frame"])[0]))
    dirty_before_save = assert_dirty_scope(plan["named_saves"], args["run"], "APPLY")
    save_named(plan["named_saves"], args["run"])
    after = snapshot(ctx)
    track_after = verify_score_track(ctx["s6"], plan)
    if not material_state_valid(after["assets"]):
        stop(args["run"], "POSTSAVE_MATERIAL_FINGERPRINT|%r" % after["assets"])
    volume_after = after["volume"]
    if volume_after.get("actor_count") != 1 or volume_after.get("binding_count") != 1:
        stop(args["run"], "POSTSAVE_VOLUME_COUNT|%r" % volume_after)
    actor_after = volume_after.get("actor", {})
    binding_after = volume_after.get("binding", {})
    if (not actor_after.get("enabled") or not actor_after.get("unbound")
            or abs(actor_after.get("blend_weight", -1.0)) > FLOAT_TOL
            or actor_after.get("blendables") != [{"object": MATERIAL_PATH, "weight": 1.0}]):
        stop(args["run"], "POSTSAVE_VOLUME_STATE|%r" % actor_after)
    if binding_after.get("property") != ["BlendWeight", "blend_weight"] or binding_after.get("default") != 1.0:
        stop(args["run"], "POSTSAVE_S6_SCOPE_TRACK|%r" % binding_after)
    end_after = pose_row(unwrap(lib.get_passage_camera_pose(ctx["show"], ctx["guid"], ctx["end"]), 3,
                                "END_READBACK"))
    entry_after = actor_state(ctx["entry"])
    nested_after = (after["route"].get("first_camera_transform") or {}).get("channels")
    nested_before = (before["route"].get("first_camera_transform") or {}).get("channels")
    if nested_after != nested_before:
        stop(args["run"], "FORBIDDEN_NESTED_CAMERA_CHANGED")
    record.update({
        "status": "APPLIED_AND_READ_BACK", "created_assets": created,
        "created_volume_path": volume.get_path_name(), "created_binding_guid": guid_text(binding.get_id()),
        "camera_reports": camera_reports, "track_after": track_after,
        "p06_end_after": end_after, "entry_after": entry_after,
        "dirty_before_save": dirty_before_save, "after": after, "dirty_after": dirty_census(),
    })
    replace_json(record_path, record)
    unreal.log("JOB190_APPLY_OK|run=%s|preset=%s|route=live3d|build=none|score_keys=%d|volume_s6_only=1|nested_camera=unchanged|saved=5|created=%d|record=%s|backup=%s" %
               (args["run"], args["preset"], sum(len(value) for value in plan["score_keys"].values()),
                 len(created), record_path, backup_row["directory"]))


def run_revert(ctx, args):
    path = args["record"]
    if not os.path.isabs(path):
        path = os.path.join(HERE, path)
    source = read_json(path)
    if source.get("status") != "APPLIED_AND_READ_BACK" or source.get("schema") != 1:
        stop(args["run"], "INCOMPLETE_APPLY_RECORD")
    tracks = owned_score_tracks(ctx["s6"])
    bindings = [binding for binding in volume_bindings(ctx["s6"])
                if guid_text(binding.get_id()) == source.get("created_binding_guid")]
    actors = [actor for actor in volume_actors(ctx)
              if actor.get_path_name() == source.get("created_volume_path")]
    if len(tracks) != 1 or len(bindings) != 1 or len(actors) != 1:
        stop(args["run"], "OWNED_REVERT_SCOPE|tracks=%d|bindings=%d|actors=%d" %
             (len(tracks), len(bindings), len(actors)))
    existing_assets = [path for path in (MPC_PATH, MATERIAL_PATH)
                       if unreal.EditorAssetLibrary.does_asset_exist(path)]
    backup_row = backup(ctx, args["run"], existing_assets)
    revert_path = os.path.join(RECORDS, "job190_%s_revert.json" % args["run"])
    record = {
        "schema": 1, "status": "PREPARED_BEFORE_MUTATION", "run": args["run"],
        "source_record": path, "before_revert": snapshot(ctx), "backup": backup_row,
        "retained_reusable_assets": existing_assets,
        "retention_reason": "no permanent asset deletion; the material is unreferenced after volume removal and MPC defaults are zero",
    }
    write_new(revert_path, record)

    ctx["s6"].remove_track(tracks[0])
    bindings[0].remove()
    if not ctx["actor_sub"].destroy_actor(actors[0]):
        stop(args["run"], "DESTROY_OWNED_VOLUME_FAILED")
    restore_channels(ctx["section"], source["before"]["camera_channels"])
    revert_saves = [MASTER_PATH, S6_PATH, WORLD_PATH]
    dirty_before_save = assert_dirty_scope(revert_saves, args["run"], "REVERT")
    save_named(revert_saves, args["run"])
    after = snapshot(ctx)
    if after["score_track"] is not None or after["volume"]["actor_count"] or after["volume"]["binding_count"]:
        stop(args["run"], "REVERT_OWNED_STATE_REMAINS|%r" % after)
    if after["camera_channels"] != source["before"]["camera_channels"]:
        stop(args["run"], "CAMERA_CHANNEL_REVERT_READBACK")
    if after["route"]["first_camera_transform"]["channels"] != source["before"]["route"]["first_camera_transform"]["channels"]:
        stop(args["run"], "FORBIDDEN_NESTED_CAMERA_CHANGED_DURING_REVERT")
    record.update({"status": "REVERTED_AND_READ_BACK", "after": after,
                   "dirty_before_save": dirty_before_save, "dirty_after": dirty_census()})
    replace_json(revert_path, record)
    unreal.log("JOB190_REVERT_OK|run=%s|source=%s|score_removed=1|volume_removed=1|camera_restored=1|nested_camera=unchanged|assets_retained=%d|record=%s|backup=%s" %
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
            unreal.log_error("JOB190_FAILED|run=%s|%r" % (run, exc))
        raise

