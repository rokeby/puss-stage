"""READ-ONLY: what the curtain placement needs to know (29 Sep, Gary: "place the opening curtain where it's supposed
to be (at the front and also in between transitions)"). Writes nothing; everything lives inside main().

Reports: the Opening and every Interaction/Closing sequence's bindings (spawnable/possessable, class, tracks,
spawnable template placement values), master tracks (camera cuts), the Show cues' camera/curtain fields for those
blocks, every AInfinityStageCameraRig and Passage actor's transform, and which GeometryCache / Alembic Python
classes and properties exist. Dirty set must be unchanged.
"""
import json
import os

import unreal


def dirty():
    return sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + \
        sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())


def vec(v):
    return [round(v.x, 1), round(v.y, 1), round(v.z, 1)]


def rot(r):
    return [round(r.roll, 2), round(r.pitch, 2), round(r.yaw, 2)]


def rng(s):
    a = s.get_start_frame() if s.has_start_frame() else None
    b = s.get_end_frame() if s.has_end_frame() else None
    return [a, b]


def describe_sequence(path):
    seq = unreal.load_asset(path)
    if not seq:
        return {"path": path, "missing": True}
    out = {"path": path, "display_rate": str(seq.get_display_rate()), "tick": str(seq.get_tick_resolution()),
           "range": [seq.get_playback_start(), seq.get_playback_end()], "bindings": [], "master_tracks": []}
    for t in seq.get_tracks():
        row = {"class": t.get_class().get_name(), "name": str(t.get_display_name())}
        row["sections"] = [rng(s) for s in t.get_sections()]
        out["master_tracks"].append(row)
    for b in seq.get_bindings():
        row = {"name": str(b.get_display_name()), "id": str(b.get_id())}
        try:
            row["possessed_class"] = str(b.get_possessed_object_class().get_name()) if b.get_possessed_object_class() else None
        except Exception as exc:  # noqa: BLE001
            row["possessed_class_err"] = str(exc)
        try:
            tmpl = b.get_object_template()
            row["spawnable"] = tmpl is not None
            if tmpl is not None:
                row["template_class"] = tmpl.get_class().get_name()
                for prop in ("curtain_distance_cm", "curtain_view_local_offset_cm", "b_follow_player_camera",
                             "follow_player_camera", "b_use_authored_open_closed_transforms",
                             "use_authored_open_closed_transforms", "curtain_closed_relative_transform",
                             "curtain_open_relative_transform", "curtain_active", "b_curtain_active"):
                    try:
                        v = tmpl.get_editor_property(prop)
                        if isinstance(v, unreal.Transform):
                            v = {"t": vec(v.translation), "r": rot(v.rotation.rotator()), "s": vec(v.scale3d)}
                        elif isinstance(v, unreal.Vector):
                            v = vec(v)
                        row[prop] = v
                    except Exception:  # noqa: BLE001
                        pass
                try:
                    mesh = tmpl.get_editor_property("curtain_mesh")
                    sm = mesh.get_editor_property("static_mesh") if mesh else None
                    row["curtain_static_mesh"] = sm.get_path_name() if sm else None
                    if sm:
                        bb = sm.get_bounds()
                        row["curtain_mesh_extent"] = vec(bb.box_extent)
                        row["curtain_mesh_origin"] = vec(bb.origin)
                except Exception:  # noqa: BLE001
                    pass
                try:
                    row["template_location"] = vec(tmpl.get_actor_location())
                    row["template_rotation"] = rot(tmpl.get_actor_rotation())
                except Exception:  # noqa: BLE001
                    pass
        except Exception as exc:  # noqa: BLE001
            row["template_err"] = str(exc)
        tracks = []
        for t in b.get_tracks():
            tr = {"class": t.get_class().get_name(), "name": str(t.get_display_name()), "sections": []}
            for s in t.get_sections():
                sec = {"range": rng(s)}
                try:
                    chans = s.get_all_channels()
                    keyed = []
                    for c in chans[:12]:
                        try:
                            ks = c.get_keys()
                            if ks:
                                keyed.append([str(c.get_name()), [(k.get_time().frame_number.value, k.get_value()) for k in ks[:6]]])
                        except Exception:  # noqa: BLE001
                            pass
                    if keyed:
                        sec["keys"] = keyed
                except Exception:  # noqa: BLE001
                    pass
                tr["sections"].append(sec)
            tracks.append(tr)
        row["tracks"] = tracks
        out["bindings"].append(row)
    return out


def show_rows():
    show = unreal.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
    rows = []
    for i, cue in enumerate(show.get_editor_property("cues")):
        scene = cue.get_editor_property("scene")
        seq = scene.get_editor_property("sequence")
        if not seq:
            continue
        row = {"index": i, "label": str(cue.get_editor_property("label")), "sequence": seq.get_name()}
        for prop in ("sequence_owns_curtain", "curtain_mode", "camera_owner", "retain_previous_camera",
                     "reveal_next_passage_when_covered", "camera_mode"):
            try:
                row[prop] = str(scene.get_editor_property(prop))
            except Exception:  # noqa: BLE001
                pass
        rows.append(row)
    return rows


def world_rows():
    ss = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    rows = []
    for a in ss.get_all_level_actors():
        cls = a.get_class().get_name()
        if "CameraRig" in cls or "PassageActor" in cls or cls.startswith("InfinityStagePassage") or "CineCamera" in cls \
                or "ShowRoot" in cls or "Structure" in cls:
            row = {"label": a.get_actor_label(), "class": cls, "loc": vec(a.get_actor_location()),
                   "rot": rot(a.get_actor_rotation()), "tags": [str(t) for t in a.tags][:6]}
            rows.append(row)
    return rows


def api_rows():
    names = ["GeometryCache", "GeometryCacheActor", "GeometryCacheComponent", "MovieSceneGeometryCacheTrack",
             "MovieSceneGeometryCacheSection", "MovieSceneGeometryCacheParams", "AbcImportSettings",
             "AbcGeometryCacheSettings", "AbcConversionSettings", "AlembicImportType", "AbcSamplingSettings",
             "AbcMaterialSettings", "AbcNormalGenerationSettings", "MovieSceneSpawnableOwnership",
             "MovieSceneSpawnTrack", "AssetImportTask"]
    out = {}
    for n in names:
        c = getattr(unreal, n, None)
        if c is None:
            out[n] = None
            continue
        try:
            props = [p for p in dir(c) if not p.startswith("_")]
        except Exception:  # noqa: BLE001
            props = []
        out[n] = props[:80]
    return out


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world_name = editor.get_editor_world().get_outermost().get_name()
    before = dirty()
    report = {"world": world_name, "pie": editor.get_game_world() is not None, "dirty_before": before}
    base = "/Game/InfinityStage/Interactions/"
    report["sequences"] = [describe_sequence(base + n) for n in (
        "LS_Opening_Curtain", "LS_Interaction_01_WashingTheBoy", "LS_Closing_Curtain")]
    report["show"] = show_rows()
    report["world_actors"] = world_rows()
    report["api"] = api_rows()
    report["dirty_after"] = dirty()
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods",
                       "inspect_curtain_sites.json")
    with open(out, "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1, default=str)
    ok = report["dirty_after"] == before
    unreal.log(("PUSS_SOFTGOODS_SITES_OK|" if ok else "PUSS_SOFTGOODS_SITES_DIRTY_CHANGED|") + out)


main()
