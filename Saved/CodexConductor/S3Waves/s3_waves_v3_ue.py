"""S3 waves v3, variant B -- the editor tool.  Modes (one per MCP call; args file s3_waves_v3_args.json):

  DRY           read-only: root landed?, the 9 "S3 Wave Split" pieces (flags, attach parent, every track on bindings
                that resolve to them in LS_DevScene_03 AND LS_S3_HangarRise, rise visibility sections), our labels,
                asset state, the full APPLY plan.  Writes s3_waves_v3_dry_<run>.json.  Marker S3WAVESV3_DRY_OK.
  IMPORT        ONE piece: its FBX (LodGroup, materials/textures OFF) + its 3 skin PNGs -> new packages under
                /Game/Scenes/Wings/FlatV3/Scene3/WavesV3; nanite off; LOD1 screen size 0.3; gates: 2 LODs, slot order,
                UV0 signs (V runs DOWN), front normal -X, LOD1 has no Flap section, bounds and triangle counts = the
                clean Blender re-import, no sockets, no stray assets, census = exactly the 4 new packages; save; GC.
                Texture SIZE is NOT gated here (first-load sizes read 32x32): VERIFY does it in a later call.
  VERIFY        read-only, PIE-safe (unreal.load_asset only): every piece's mesh/texture/MI state incl. texture sizes
                == the PNG headers.  Writes s3_waves_v3_verify.json (APPLY needs it newer than every import/mat run).
  BUILD_MAT     1..4 pieces: create-only MI_..._Front / _Flap (parents MI_Billboard_Front/Flap; textures + sheet
                scalars from <piece>_mi_params.json; foam layers also get Flap flutter overrides), assign the 4 mesh
                slots (Timber + Edge = M_Wing_CanvasEdge_Master); read back; save MIs + mesh only.
  APPLY         record FIRST, Backups/PreS3WavesV3-<run> (umap + LS_DevScene_03 + LS_S3_HangarRise + record), spawn 12
                tool-owned Movable StaticMeshActors attached KEEP_RELATIVE to "S3 Hangar Root" at the planned local
                transforms (root must read LANDED live; every actor's world AABB, mapped into the LIVE root's frame,
                must lie in the wave guard box), hide the 9 split pieces (component visibility off + component
                hidden-in-game + actor hidden-in-game; originals recorded; a rise VISIBILITY track only drives the
                actor flag, so component visibility keeps them hidden [inf: UE visibility track semantics]), copy the
                split pieces' rise reveal onto the new actors when they all share one (else none), narrow save, read
                back after the save.  Marker S3WAVESV3_APPLY_OK.
  REVERT        exact inverse from the record (refuses while a MOTION record exists).
  MOTION_DRY / MOTION_APPLY / MOTION_REVERT   baked Transform keys (sway Y, bob Z, roll X) on the 12 actors in
                LS_DevScene_03, LINEAR every 3 frames from strike-1 to the Scene end 6240, own record.
  LIGHT_DRY / LIGHT_APPLY / LIGHT_REVERT      rake key retint (temperature only), 6 hidden ground rows + the warm side
                light (RectLights on the root, Intensity keyed 0 -> strike ramp -> held to 6240 in LS_DevScene_03),
                sea-band LocalFogVolume ONLY if an ExponentialHeightFog exists in S3 (else spec only), own record.

Safety (memory notes): no unreal object at module level; runner purges the Saved module cache; no
get_bound_objects (locate_bound_objects only); no reloading the open world; modify() before setters; every setter
read back; success markers only after asserted read-back; ZZ_/TEMP guard (GameplayStatics, sees transients) in the
same call as every save; a failure saves nothing ("Don't-Save restart", never reload).
"""
import datetime
import hashlib
import importlib.util
import json
import os
import shutil
import struct
import sys

try:
    import unreal
except ModuleNotFoundError:   # offline harness imports the pure core only
    unreal = None

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
ARGS = os.path.join(HERE, "s3_waves_v3_args.json")
B_BUILD = os.path.join(PROJECT, "DerivedAssets", "FlatV3", "Scene3", "waves_v3", "B_build")
BUILD_REPORT = os.path.join(B_BUILD, "build_report_B.json")
BUILD_PLAN = os.path.join(HERE, "build_plan_B.json")
MOTION_PLAN = os.path.join(HERE, "s3_waves_v3_motion_plan.json")
APPLY_RECORD = os.path.join(HERE, "s3_waves_v3_apply_record.json")
MOTION_RECORD = os.path.join(HERE, "s3_waves_v3_motion_record.json")
LIGHT_RECORD = os.path.join(HERE, "s3_waves_v3_light_record.json")
VERIFY_REPORT = os.path.join(HERE, "s3_waves_v3_verify.json")


def _core():
    spec = importlib.util.spec_from_file_location("s3_waves_v3_core_live", os.path.join(HERE, "s3_waves_v3_core.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pilot():
    """Saved/CodexFlatV3/phase1_import.py as a library (its main() only runs when FLATV3_MODE is set,
    phase1_import.py:1182-1183) -- the house Flat V3 import helpers, ran FV3P06I-20261002-04 / P06IMP 7 Oct [prec]."""
    path = os.path.join(PROJECT, "Saved", "CodexFlatV3", "phase1_import.py")
    spec = importlib.util.spec_from_file_location("s3wv3_pilot_lib", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# =================================================================================================== small helpers
def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _png_size(path):
    with open(path, "rb") as f:
        head = f.read(33)
    if head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        raise RuntimeError("NOT_PNG|%s" % path)
    return list(struct.unpack(">II", head[16:24]))


def _write(path, value, exclusive=False):
    tmp = path + ".tmp"
    if exclusive and os.path.exists(path):
        raise RuntimeError("RECORD_EXISTS|%s" % path)
    with open(tmp, "w", encoding="utf-8") as h:
        json.dump(value, h, indent=1, sort_keys=True, default=str)
        h.flush()
        os.fsync(h.fileno())
    os.replace(tmp, path)
    with open(path, encoding="utf-8") as h:
        if json.load(h) != json.loads(json.dumps(value, sort_keys=True, default=str)):
            raise RuntimeError("JSON_READBACK|%s" % path)
    return path


def _read(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as h:
        return json.load(h)


def _path(o):
    return str(o.get_path_name()) if o is not None else None


def _pkg(o):
    return None if o is None else str(o.get_path_name()).split(".", 1)[0]


def _guid(g):
    return str(unreal.GuidLibrary.conv_guid_to_string(g))


def _enum(v):
    return str(getattr(v, "name", v)).split(".")[-1].split(":")[0].strip("<> ").upper()


def _v(x):
    return [float(x.x), float(x.y), float(x.z)]


def _r(rot):
    return [float(rot.roll), float(rot.pitch), float(rot.yaw)]


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(str(p.get_name()).split(".", 1)[0] for p in lib.get_dirty_content_packages()),
            "maps": sorted(str(p.get_name()).split(".", 1)[0] for p in lib.get_dirty_map_packages())}


def _load(path, cls=None):
    o = unreal.load_asset(path)                      # EditorAssetLibrary.load_asset returns None in PIE (brief)
    if o is None or (cls is not None and not isinstance(o, cls)):
        raise RuntimeError("LOAD_FAIL|%s" % path)
    return o


def _exists(path):
    return bool(unreal.EditorAssetLibrary.does_asset_exist(path))


def _editor_world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


def _all_actors(world):
    return list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))   # sees transient actors


def _index(world):
    out = {}
    for a in _all_actors(world):
        out.setdefault(str(a.get_actor_label()), []).append(a)
    return out


def _by_path(world, path):
    rows = [a for a in _all_actors(world) if _path(a) == path]
    return rows[0] if len(rows) == 1 else None


def _temp_actors(index):
    return sorted(k for k in index if k.startswith("ZZ_") or "TEMP" in k.upper())


def _world_tf(actor):
    return {"location": _v(actor.get_actor_location()), "rotation": _r(actor.get_actor_rotation()),
            "scale": _v(actor.get_actor_scale3d())}


def _rel_tf(actor):
    t = actor.get_editor_property("root_component").get_relative_transform()
    return {"location": _v(t.translation), "rotation": _r(t.rotation.rotator()), "scale": _v(t.scale3d)}


def _bounds(actor):
    o, e = actor.get_actor_bounds(False)
    return {"min": [o.x - e.x, o.y - e.y, o.z - e.z], "max": [o.x + e.x, o.y + e.y, o.z + e.z]}


def _smc(actor):
    comps = list(actor.get_components_by_class(unreal.StaticMeshComponent))
    if len(comps) != 1:
        raise RuntimeError("SMC_COUNT|%s|%d" % (actor.get_actor_label(), len(comps)))
    return comps[0]


def _flags(actor):
    c = _smc(actor)
    return {"actor_hidden": bool(actor.get_editor_property("hidden")),     # Actor bHidden (no is_hidden() in 5.8)
            "comp_visible": bool(c.is_visible()), "comp_hidden_in_game": bool(c.get_editor_property("hidden_in_game"))}


def _set_flags(actor, flags):
    """S3Millstone/s3_props_ue.py:673-681 _set_flags (ran S3PROPS-20261007-173446) [prec]."""
    actor.modify()
    c = _smc(actor)
    c.modify()
    actor.set_actor_hidden_in_game(bool(flags["actor_hidden"]))
    c.set_visibility(bool(flags["comp_visible"]), False)
    c.set_hidden_in_game(bool(flags["comp_hidden_in_game"]), False)
    got = _flags(actor)
    if got != {k: bool(v) for k, v in flags.items()}:
        raise RuntimeError("FLAGS_READBACK|%s|%s" % (actor.get_actor_label(), got))


def _fps(seq):
    r = seq.get_display_rate()
    return r.numerator / float(r.denominator)


def _frame(t):
    if hasattr(t, "frame_number"):
        return int(t.frame_number.value)
    return int(t.value if hasattr(t, "value") else t)


def _located(seq, b, world):
    try:
        return sorted(_path(o) for o in seq.locate_bound_objects(b, world))
    except Exception:  # noqa: BLE001
        return None


def _prop(t, getter):
    try:
        return str(getattr(t, getter)())
    except Exception:  # noqa: BLE001
        return None


def _seq_tracks_for(seq, world, obj_paths, names):
    """Bindings in seq that resolve to any of obj_paths (or whose display name is in names): list of
    {guid, name, tracks: [{class, name, property}]}.  None-safe; locate_bound_objects only."""
    rows = []
    for b in seq.get_bindings():
        loc = _located(seq, b, world) or []
        if not (set(loc) & set(obj_paths)) and str(b.get_display_name()) not in names:
            continue
        rows.append({"guid": _guid(b.get_id()), "name": str(b.get_display_name()), "resolved": loc,
                     "tracks": [{"class": t.get_class().get_name(), "name": str(t.get_display_name()),
                                 "property": _prop(t, "get_property_name")} for t in b.get_tracks()]})
        for c in b.get_child_possessables():
            rows.append({"guid": _guid(c.get_id()), "name": str(c.get_display_name()), "child_of": _guid(b.get_id()),
                         "resolved": _located(seq, c, world) or [],
                         "tracks": [{"class": t.get_class().get_name(), "name": str(t.get_display_name()),
                                     "property": _prop(t, "get_property_name")} for t in c.get_tracks()]})
    return rows


def _visibility_sections(binding, fps):
    """S3Millstone/s3_props_ue.py:706-722 [prec]."""
    out = []
    for t in binding.get_tracks():
        if t.get_class().get_name() != "MovieSceneVisibilityTrack":
            continue
        for s in t.get_sections():
            chans = list(s.get_all_channels())
            try:
                mode = _enum(s.get_completion_mode())
            except Exception:  # noqa: BLE001
                mode = _enum(s.get_editor_property("eval_options").get_editor_property("completion_mode"))
            out.append({"range_s": [float(s.get_start_frame_seconds()), float(s.get_end_frame_seconds())],
                        "completion_mode": mode, "channels": len(chans),
                        "keys": [[int(k.get_time().frame_number.value), bool(k.get_value())] for k in chans[0].get_keys()]
                        if len(chans) == 1 else None, "fps": fps})
    return out


def _rise_visibility(rise, world, actor):
    want = _path(actor)
    found = []
    try:
        for b in rise.get_bindings():
            if _located(rise, b, world) == [want]:
                found.extend(_visibility_sections(b, _fps(rise)))
    except Exception:  # noqa: BLE001
        return "UNREAD"
    return found


def _read_strike(C, root_seq, rise):
    """s3_wave_split_apply.py:317-353 _read_strike (ran 4 Oct, record s3_wave_split_record.json) [prec]."""
    matches = []
    for track in root_seq.get_tracks():
        if isinstance(track, unreal.MovieSceneSubTrack):
            for section in track.get_sections():
                nested = section.get_sequence()
                if nested is not None and _pkg(nested) == C.RISE:
                    matches.append(section)
    if len(matches) != 1 or not matches[0].is_active():
        raise C.PlanError("RISE_SUBSECTION|expected one active")
    section = matches[0]
    parameters = section.get_editor_property("parameters")
    offset = _frame(parameters.get_editor_property("start_frame_offset"))
    time_scale = float(unreal.MovieSceneTimeWarpExtensions.conv_time_warp_variant_to_play_rate(
        parameters.get_editor_property("time_scale")))
    candidates = []
    for binding in rise.get_bindings():
        parent = binding.get_parent()
        label = str(parent.get_display_name()) if parent is not None and parent.is_valid() else str(binding.get_display_name())
        if label != C.UPLIGHT_LABEL:
            continue
        for track in binding.get_tracks():
            if isinstance(track, unreal.MovieSceneFloatTrack) and str(track.get_property_name()) == "Intensity":
                for cand in track.get_sections():
                    keys = sorted(cand.get_all_channels()[0].get_keys(), key=lambda k: _frame(k.get_time()))
                    rows = [[_frame(k.get_time()), float(k.get_value())] for k in keys]
                    candidates.extend(rows[i][0] for i in range(len(rows) - 1)
                                      if abs(rows[i][1]) < 1e-6 and rows[i + 1][1] > 0.0)
    if len(candidates) != 1:
        raise C.PlanError("STRIKE_AMBIGUOUS|%s" % candidates)
    pf, cf = _fps(root_seq), _fps(rise)
    raw = float(_frame(section.get_start_frame())) + (candidates[0] - offset) * pf / cf / time_scale
    return {"frame": int(round(raw)), "raw": raw, "child_frame": candidates[0], "child_fps": cf, "parent_fps": pf,
            "section_start": _frame(section.get_start_frame()), "offset": offset, "time_scale": time_scale,
            "section_end": _frame(section.get_end_frame())}


def _seq_state(C):
    root_seq, rise = _load(C.ROOT_SEQ, unreal.LevelSequence), _load(C.RISE, unreal.LevelSequence)
    return root_seq, rise, {"fps": _fps(root_seq), "playback": [int(root_seq.get_playback_start()),
                                                                int(root_seq.get_playback_end())],
                            "strike": _read_strike(C, root_seq, rise)}


def _guard(C, world, need_clean=True):
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        raise C.PlanError("PIE_ACTIVE")
    if world is None or str(world.get_outermost().get_name()) != C.WORLD:
        raise C.PlanError("WRONG_WORLD|%s" % (world.get_outermost().get_name() if world else None))
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        raise C.PlanError("SEQUENCER_IS_OPEN (close it: opening/scrubbing dirties the map)")
    census = _census()
    if need_clean and census != {"content": [], "maps": []}:
        raise C.PlanError("DIRTY_BEFORE|%s" % json.dumps(census))
    return census


def _backup(C, run, tag, extra_files=()):
    d = os.path.join(PROJECT, "Backups", "PreS3WavesV3%s-%s" % (tag, run))
    os.makedirs(d)
    for rel in (C.UMAP_REL, C.ROOT_SEQ_REL, C.RISE_REL):
        src = os.path.join(PROJECT, rel)
        dst = os.path.join(d, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        if _sha(dst) != _sha(src):
            raise RuntimeError("BACKUP_HASH|%s" % dst)
    for f in extra_files:
        shutil.copy2(f, os.path.join(d, os.path.basename(f)))
    return d


def _save(C, world, content, map_expected):
    """Census must be EXACTLY content (+ the map when expected); ZZ_ guard in the same call; save; census clean."""
    c = _census()
    want = {"content": sorted(content), "maps": [C.WORLD] if map_expected else []}
    if c != want:
        raise RuntimeError("DIRTY_SCOPE|got=%s|want=%s" % (json.dumps(c), json.dumps(want)))
    temps = _temp_actors(_index(world))
    if temps:
        raise RuntimeError("ZZ_ACTORS_PRESENT|%s" % temps[:5])
    for p in content:
        if not unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False):
            raise RuntimeError("SAVE|%s" % p)
    if map_expected and not unreal.EditorLoadingAndSavingUtils.save_map(world, C.WORLD):
        raise RuntimeError("SAVE_MAP")
    after = _census()
    if after != {"content": [], "maps": []}:
        raise RuntimeError("POST_SAVE_DIRTY|%s" % json.dumps(after))
    return after


def _rows(C):
    return C.piece_table(_read(BUILD_REPORT), _read(BUILD_PLAN))


def _piece_files(suffix):
    f = os.path.join(B_BUILD, "pieces", suffix)
    return {"dir": f, "fbx": os.path.join(f, "SM_FlatV3_%s.fbx" % suffix),
            "tex": {k: os.path.join(f, "T_%s_%s.png" % (suffix, k)) for k in ("SkinColor", "SkinMask", "SkinNormal")},
            "mi_params": os.path.join(f, "%s_mi_params.json" % suffix),
            "validation": os.path.join(f, "SM_FlatV3_%s_validation.json" % suffix)}


def _pick(rows, names):
    by = {r["suffix"][len("S3_WaveV3_"):]: r for r in rows}
    out = []
    for n in names:
        n = n[len("S3_WaveV3_"):] if n.startswith("S3_WaveV3_") else n
        if n not in by:
            raise RuntimeError("UNKNOWN_PIECE|%s|known=%s" % (n, sorted(by)))
        out.append(by[n])
    return out


# =================================================================================================== IMPORT
def _folder_assets(folder):
    eal = unreal.EditorAssetLibrary
    if not eal.does_directory_exist(folder):
        return set()
    return set(str(n).split(".")[0] for n in eal.list_assets(folder, recursive=True, include_folder=False))


def _configure_texture(pilot, tex, kind, C):
    pilot.configure_texture(tex, kind)                          # modify() + house profile [prec]
    comp, srgb = C.TEX_PROFILE[kind]
    tex.set_editor_property("compression_settings", getattr(unreal.TextureCompressionSettings, comp))
    tex.set_editor_property("srgb", srgb)
    return _texture_state(tex, C, kind, check_size=False)


def _texture_state(tex, C, kind, check_size, want_size=None):
    comp, srgb = C.TEX_PROFILE[kind]
    st = {"compression": _enum(tex.get_editor_property("compression_settings")),
          "srgb": bool(tex.get_editor_property("srgb")), "flip_green": bool(tex.get_editor_property("flip_green_channel")),
          "mip_gen": _enum(tex.get_editor_property("mip_gen_settings")),
          "size": [int(tex.blueprint_get_size_x()), int(tex.blueprint_get_size_y())]}
    if st["compression"] != comp or st["srgb"] != srgb or st["flip_green"] or st["mip_gen"] == "TMGS_NO_MIPMAPS":
        raise RuntimeError("TEXTURE_SETTINGS|%s|%s" % (tex.get_path_name(), st))
    if check_size and st["size"] != list(want_size):
        raise RuntimeError("TEXTURE_SIZE|%s|got=%s|want=%s" % (tex.get_path_name(), st["size"], want_size))
    return st


def _mesh_gate(pilot, C, mesh, row, val):
    out = {"num_lods": int(mesh.get_num_lods())}
    if out["num_lods"] != 2:
        raise RuntimeError("LOD_COUNT|%s|%d (LodGroup not honoured?)" % (row["suffix"], out["num_lods"]))
    slots = [str(s.get_editor_property("material_slot_name")) for s in mesh.get_editor_property("static_materials")]
    if slots != list(C.SLOTS):
        raise RuntimeError("SLOT_ORDER|%s|%s" % (row["suffix"], slots))
    if pilot.socket_report(mesh):
        raise RuntimeError("SOCKETS_PRESENT|%s|%s" % (row["suffix"], sorted(pilot.socket_report(mesh))))
    bb = mesh.get_bounding_box()
    got = {"min": _v(bb.min), "max": _v(bb.max)}
    want = row["bounds_cm"]
    if not (C.near(got["min"], want["min"], 1.5) and C.near(got["max"], want["max"], 1.5)):
        raise RuntimeError("BOUNDS|%s|got=%s|want=%s" % (row["suffix"], got, want))
    out["bounds_cm"] = got
    sections = {}
    for lod in (0, 1):
        _, by_slot = pilot.lod_section_slots(mesh, lod)
        front = pilot.section_uv0(mesh, lod, by_slot[0]) if 0 in by_slot else None
        flap = pilot.section_uv0(mesh, lod, by_slot[1]) if 1 in by_slot else None
        if front is None or front["du_dY"] <= 0.0 or front["dv_dZ"] >= 0.0:      # V runs DOWN (ue58-fbx-import-traps)
            raise RuntimeError("FRONT_UV0_SIGN|%s|lod%d|%s" % (row["suffix"], lod, front))
        if front["normal"][0] > -0.99:
            raise RuntimeError("FRONT_NORMAL|%s|lod%d|%s" % (row["suffix"], lod, front["normal"]))
        if lod == 0 and (flap is None or flap["du_dY"] <= 0.0 or flap["dv_dZ"] >= 0.0):
            raise RuntimeError("FLAP_UV0_SIGN|%s|%s" % (row["suffix"], flap))
        if lod == 1 and flap is not None:
            raise RuntimeError("LOD1_FLAP_SURVIVED|%s" % row["suffix"])
        dyn = pilot.dynamic_lod(mesh, lod)
        wantt = int(val["triangle_counts"]["lod%d" % lod])
        if abs(int(dyn["triangles"]) - wantt) > 1:                                   # slot_a +-1 [prec]
            raise RuntimeError("TRIANGLES|%s|lod%d|%d|%d" % (row["suffix"], lod, dyn["triangles"], wantt))
        flap_m = dyn["materials"].get("1") or {}
        sections[str(lod)] = {"front": {k: front[k] for k in ("du_dY", "dv_dZ", "normal")},
                              "flap_triangles": flap_m.get("triangles", 0), "flap_r_range": flap_m.get("r_range"),
                              "triangles": int(dyn["triangles"])}
    rr = sections["0"]["flap_r_range"] or [1, 0]
    if not (rr[0] <= 0.01 and rr[1] >= 0.99):
        raise RuntimeError("FLAP_WEIGHTS|%s|%s" % (row["suffix"], rr))
    out["sections"] = sections
    out["nanite"] = bool(mesh.get_editor_property("nanite_settings").get_editor_property("enabled"))
    if out["nanite"]:
        raise RuntimeError("NANITE_ON|%s" % row["suffix"])
    sme = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    out["screen_sizes"] = [float(x) for x in sme.get_lod_screen_sizes(mesh)]
    return out


def run_import(C, run, args, world):
    pilot = _pilot()
    rows = _pick(_rows(C), args["pieces"])
    row = rows[0]
    files = _piece_files(row["suffix"])
    val = _read(files["validation"])
    if not val or not val.get("pass"):
        raise RuntimeError("VALIDATION_NOT_PASS|%s" % files["validation"])
    planned = [row["mesh"]] + [row["tex"][k] for k in C.TEX_KINDS]
    for p in planned + list(row["mi"].values()):
        if _exists(p):
            raise RuntimeError("DESTINATION_EXISTS|%s (create-only; never re-import in place)" % p)
    srcs = [files["fbx"]] + [files["tex"][k] for k in C.TEX_KINDS]
    for s in srcs:
        if not os.path.isfile(s):
            raise RuntimeError("SOURCE_MISSING|%s" % s)
    folders = sorted({p.rsplit("/", 1)[0] for p in planned})
    before = {f: _folder_assets(f) for f in folders}
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    tools.import_asset_tasks([pilot.import_task(files["fbx"], row["mesh"], pilot.fbx_options(True))])
    mesh = _load(row["mesh"], unreal.StaticMesh)
    mesh.modify()
    nan = mesh.get_editor_property("nanite_settings")
    nan.set_editor_property("enabled", False)
    mesh.set_editor_property("nanite_settings", nan)
    sme = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    sizes = [float(x) for x in sme.get_lod_screen_sizes(mesh)]
    if len(sizes) != 2:
        raise RuntimeError("SCREEN_SIZES_READ|%s" % sizes)
    sme.set_lod_screen_sizes(mesh, [sizes[0], C.LOD1_SCREEN_SIZE])      # flutter_lod.py:184-187 [prec]
    got_sizes = [float(x) for x in sme.get_lod_screen_sizes(mesh)]
    if abs(got_sizes[1] - C.LOD1_SCREEN_SIZE) > 1e-4:
        raise RuntimeError("SCREEN_SIZE_READBACK|%s" % got_sizes)
    tex_state = {}
    for k in C.TEX_KINDS:
        tools.import_asset_tasks([pilot.import_task(files["tex"][k], row["tex"][k])])
        tex = _load(row["tex"][k], unreal.Texture2D)
        tex_state[k] = _configure_texture(pilot, tex, k, C)
        tex_state[k]["png_size"] = _png_size(files["tex"][k])
        tex_state[k]["size_first_load_unverified"] = tex_state[k].pop("size")
    gate = _mesh_gate(pilot, C, mesh, row, val)
    after = set()
    for f in folders:
        after |= _folder_assets(f) - before[f]
    strays = sorted(after - set(planned))
    if strays or sorted(after) != sorted(planned):
        raise RuntimeError("STRAY_OR_MISSING|new=%s|planned=%s (never saved: Don't-Save restart)" % (sorted(after), planned))
    _save(C, world, planned, map_expected=False)
    unreal.SystemLibrary.collect_garbage()
    rec = {"run": run, "suffix": row["suffix"], "packages": planned, "mesh_gate": gate, "textures": tex_state,
           "fbx_sha256": _sha(files["fbx"]), "screen_sizes": got_sizes, "saved": True,
           "utc": datetime.datetime.utcnow().isoformat() + "Z"}
    _write(os.path.join(HERE, "s3_waves_v3_import_%s.json" % row["suffix"]), rec)
    return rec


# =================================================================================================== BUILD_MAT
def _mi_state(pilot, mi):
    return {"parent": pilot.asset_package(mi.get_editor_property("parent")),
            "textures": pilot.serialized_texture_parameters(mi), "scalars": pilot.serialized_scalar_parameters(mi)}


def run_build_mat(C, run, args, world):
    pilot = _pilot()
    mel = unreal.MaterialEditingLibrary
    out = {}
    for row in _pick(_rows(C), args["pieces"]):
        if not _read(os.path.join(HERE, "s3_waves_v3_import_%s.json" % row["suffix"]), {}).get("saved"):
            raise RuntimeError("NOT_IMPORTED|%s" % row["suffix"])
        for p in row["mi"].values():
            if _exists(p):
                raise RuntimeError("MI_EXISTS|%s" % p)
        params = _read(_piece_files(row["suffix"])["mi_params"])
        if params["parents"]["Front"] != C.PARENTS["Front"] or params["parents"]["Flap"] != C.PARENTS["Flap"]:
            raise RuntimeError("MI_PARAMS_PARENTS|%s" % params["parents"])
        textures = {k: _load(row["tex"][k], unreal.Texture2D) for k in C.TEX_KINDS}
        scalars = {k: float(v) for k, v in params["scalar_parameters"].items()}
        made = {}
        for slot in ("Front", "Flap"):
            parent = _load(C.PARENTS[slot])
            folder, name = row["mi"][slot].rsplit("/", 1)
            mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                name, folder, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
            if not isinstance(mi, unreal.MaterialInstanceConstant):
                raise RuntimeError("MI_CREATE|%s" % row["mi"][slot])
            mi.modify()
            mel.set_material_instance_parent(mi, parent)
            for k, tex in textures.items():
                mel.set_material_instance_texture_parameter_value(mi, k, tex)        # bool lies: read back
            want_s = dict(scalars)
            if slot == "Flap" and row["foam"]:
                names = [str(n) for n in mel.get_scalar_parameter_names(mi)]
                missing = [n for n in C.FLUTTER_NAMES if n not in names]
                if missing:
                    raise RuntimeError("FLUTTER_PARAMS_MISSING|%s (foam flicker needs them)" % missing)
                want_s.update(C.FOAM_FLUTTER)
            for k, v in want_s.items():
                mel.set_material_instance_scalar_parameter_value(mi, k, float(v))
            mel.update_material_instance(mi)
            st = _mi_state(pilot, mi)
            if st["parent"] != C.PARENTS[slot] or st["textures"] != {k: row["tex"][k] for k in C.TEX_KINDS}:
                raise RuntimeError("MI_READBACK|%s|%s" % (row["mi"][slot], st))
            if set(st["scalars"]) != set(want_s) or any(abs(st["scalars"][k] - want_s[k]) > 1e-4 for k in want_s):
                raise RuntimeError("MI_SCALARS|%s|%s|%s" % (row["mi"][slot], st["scalars"], want_s))
            if slot == "Flap":
                sw = None
                if "Flutter" in [str(n) for n in mel.get_static_switch_parameter_names(mi)]:
                    sw = bool(mel.get_material_instance_static_switch_parameter_value(mi, "Flutter"))
                st["flutter_switch"] = sw
            made[slot] = st
        mesh = _load(row["mesh"], unreal.StaticMesh)
        mesh.modify()
        want_slots = [row["mi"]["Front"], row["mi"]["Flap"], C.PARENTS["Timber"], C.PARENTS["Edge"]]
        for i, p in enumerate(want_slots):
            mesh.set_material(i, _load(p))                                         # slot_a_import.py:518-521 [prec]
        got = [pilot.asset_package(s.get_editor_property("material_interface")) for s in mesh.get_editor_property("static_materials")]
        if got != want_slots:
            raise RuntimeError("SLOT_MATERIALS|%s|%s" % (row["suffix"], got))
        out[row["suffix"]] = {"mis": made, "slots": got}
    planned = sorted([r["mesh"] for r in _pick(_rows(C), args["pieces"])] +
                     [p for r in _pick(_rows(C), args["pieces"]) for p in r["mi"].values()])
    _save(C, world, planned, map_expected=False)
    unreal.SystemLibrary.collect_garbage()
    for suffix, v in out.items():
        _write(os.path.join(HERE, "s3_waves_v3_mat_%s.json" % suffix), {"run": run, "suffix": suffix, **v, "saved": True})
    return {"pieces": sorted(out), "saved": planned}


# =================================================================================================== VERIFY
def run_verify(C, run):
    pilot = _pilot()
    sme = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    rep = {"run": run, "pieces": {}}
    for row in _rows(C):
        s = row["suffix"]
        r = {"status": "MISSING"}
        try:
            mesh = unreal.load_asset(row["mesh"])
            if mesh is None:
                rep["pieces"][s] = r
                continue
            files = _piece_files(s)
            r["lods"] = int(mesh.get_num_lods())
            r["screen_sizes"] = [float(x) for x in sme.get_lod_screen_sizes(mesh)]
            r["nanite"] = bool(mesh.get_editor_property("nanite_settings").get_editor_property("enabled"))
            r["slots"] = [pilot.asset_package(x.get_editor_property("material_interface"))
                          for x in mesh.get_editor_property("static_materials")]
            r["textures"] = {k: _texture_state(_load(row["tex"][k], unreal.Texture2D), C, k, True,
                                               _png_size(files["tex"][k])) for k in C.TEX_KINDS}
            problems = []
            if r["lods"] != 2:
                problems.append("lods")
            if abs(r["screen_sizes"][1] - C.LOD1_SCREEN_SIZE) > 1e-4:
                problems.append("lod1_screen_size")
            if r["nanite"]:
                problems.append("nanite")
            want_slots = [row["mi"]["Front"], row["mi"]["Flap"], C.PARENTS["Timber"], C.PARENTS["Edge"]]
            if r["slots"] != want_slots:
                problems.append("slots(BUILD_MAT?)")
            else:
                mis = {sl: _mi_state(pilot, _load(row["mi"][sl], unreal.MaterialInstanceConstant)) for sl in ("Front", "Flap")}
                r["mis"] = {k: v["parent"] for k, v in mis.items()}
                if any(mis[sl]["textures"] != {k: row["tex"][k] for k in C.TEX_KINDS} for sl in mis):
                    problems.append("mi_textures")
                if row["foam"] and any(abs(mis["Flap"]["scalars"].get(k, -1) - v) > 1e-4 for k, v in C.FOAM_FLUTTER.items()):
                    problems.append("foam_flutter")
            r["problems"] = problems
            r["status"] = "READY" if not problems else "INCOMPLETE"
        except Exception as exc:  # noqa: BLE001 -- a verifier must be able to FAIL: recorded, marker says so
            r = {"status": "FAIL", "error": str(exc)[:400]}
        rep["pieces"][s] = r
    rep["ready"] = sorted(s for s, r in rep["pieces"].items() if r["status"] == "READY")
    rep["all_ready"] = len(rep["ready"]) == 12
    rep["texture_gpu_mb_est"] = _read(BUILD_REPORT, {}).get("texture_memory", {}).get("total_gpu_mb")
    _write(VERIFY_REPORT, rep)
    rep["written_mtime"] = os.path.getmtime(VERIFY_REPORT)
    _write(VERIFY_REPORT, rep)
    return rep


def _newest_asset_write():
    ts = [os.path.getmtime(os.path.join(HERE, f)) for f in os.listdir(HERE)
          if f.startswith(("s3_waves_v3_import_", "s3_waves_v3_mat_")) and f.endswith(".json")]
    return max(ts) if ts else 0.0


# =================================================================================================== APPLY / DRY
def live_state(C, world, rows):
    idx = _index(world)
    roots = idx.get(C.ROOT_LABEL, [])
    if len(roots) != 1:
        raise C.PlanError("ROOT_COUNT|%d" % len(roots))
    root = roots[0]
    rise = _load(C.RISE, unreal.LevelSequence)
    root_seq = _load(C.ROOT_SEQ, unreal.LevelSequence)
    split = []
    for label in C.SPLIT_LABELS:
        acts = idx.get(label, [])
        row = {"label": label, "count": len(acts)}
        if len(acts) == 1:
            a = acts[0]
            p = a.get_attach_parent_actor()
            row.update({"object_path": _path(a), "parent": str(p.get_actor_label()) if p else None,
                        "flags": _flags(a), "tool_owned_v3": C.TAG in [str(t) for t in a.tags],
                        "rise_visibility": _rise_visibility(rise, world, a),
                        "rise_bindings": _seq_tracks_for(rise, world, [_path(a)], [label]),
                        "scene_bindings": _seq_tracks_for(root_seq, world, [_path(a)], [label]),
                        "relative": _rel_tf(a)})
        split.append(row)
    verify = _read(VERIFY_REPORT)
    newest = _newest_asset_write()
    assets = {}
    for r in rows:
        ok = bool(verify and verify.get("written_mtime", 0) > newest and
                  verify.get("pieces", {}).get(r["suffix"], {}).get("status") == "READY")
        assets[r["suffix"]] = {"verified": ok, "mesh_exists": _exists(r["mesh"])}
    labels = [r["label"] for r in rows]
    return {"root": {"world": _world_tf(root), "object_path": _path(root)}, "split": split, "assets": assets,
            "label_count": {l: len(idx.get(l, [])) for l in labels}, "temp_actors": _temp_actors(idx),
            "verify_report_mtime": (verify or {}).get("written_mtime"), "newest_asset_write": newest}


def run_dry(C, run, world, census):
    rows = _rows(C)
    st = live_state(C, world, rows)
    out = {"run": run, "census": census, "state": st}
    try:
        out["apply_plan"] = C.plan_apply(st, rows)
        out["apply"] = "would_apply"
    except C.PlanError as exc:
        out["apply"] = "APPLY_WOULD_REFUSE|%s" % exc
    try:
        _rs, _rise, seqst = _seq_state(C)
        out["sequence"] = seqst
    except Exception as exc:  # noqa: BLE001
        out["sequence"] = "UNREAD|%s" % exc
    if _census() != census:
        raise RuntimeError("DRY_DIRTIED|%s" % _census())
    path = os.path.join(HERE, "s3_waves_v3_dry_%s.json" % run)
    _write(path, out)
    return out, path


def _spawn(C, world, root, s):
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    a = eas.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0), False)
    if a is None:
        raise RuntimeError("SPAWN_FAILED|%s" % s["label"])
    a.set_actor_label(s["label"])
    c = a.static_mesh_component
    c.modify()
    c.set_mobility(unreal.ComponentMobility.MOVABLE)
    c.set_static_mesh(_load(s["mesh"], unreal.StaticMesh))                # return value not trusted: read back
    a.set_editor_property("tags", [unreal.Name(t) for t in s["tags"]])
    a.set_folder_path(s["folder"])
    a.attach_to_actor(root, "", unreal.AttachmentRule.KEEP_RELATIVE, unreal.AttachmentRule.KEEP_RELATIVE,
                      unreal.AttachmentRule.KEEP_RELATIVE, False)
    rc = a.get_editor_property("root_component")
    rel = s["relative"]
    rc.set_relative_location(unreal.Vector(*rel["location"]), False, False)
    rc.set_relative_rotation(unreal.Rotator(roll=rel["rotation"][0], pitch=rel["rotation"][1], yaw=rel["rotation"][2]),
                             False, False)
    rc.set_relative_scale3d(unreal.Vector(*rel["scale"]))
    return a


def _verify_spawned(C, world, path, s, root_path):
    a = _by_path(world, path)
    if a is None:
        raise RuntimeError("SPAWNED_MISSING|%s" % s["label"])
    p = a.get_attach_parent_actor()
    if p is None or _path(p) != root_path:
        raise RuntimeError("SPAWNED_PARENT|%s|%s" % (s["label"], _path(p)))
    rel = _rel_tf(a)
    if not (C.near(rel["location"], s["relative"]["location"], 0.05) and C.near(rel["rotation"], [0, 0, 0], 0.01)
            and C.near(rel["scale"], [1, 1, 1], 1e-5)):
        raise RuntimeError("SPAWNED_RELATIVE|%s|%s" % (s["label"], rel))
    if _pkg(_smc(a).get_editor_property("static_mesh")) != s["mesh"]:
        raise RuntimeError("SPAWNED_MESH|%s" % s["label"])
    if _enum(_smc(a).get_editor_property("mobility")) != "MOVABLE":
        raise RuntimeError("SPAWNED_MOBILITY|%s" % s["label"])
    if C.TAG not in [str(t) for t in a.tags]:
        raise RuntimeError("SPAWNED_TAG|%s" % s["label"])
    # landed guard against the LIVE root (memory puss-level-saved-landed-frame-trap)
    root = _by_path(world, root_path)
    local = C.box_local(_world_tf(root), _bounds(a))
    if not C.box_inside(local, C.WAVE_GUARD_LOCAL, tol=2.0):
        raise RuntimeError("OUTSIDE_LANDED_WAVE_BOX|%s|%s" % (s["label"], json.dumps(local)))
    return {"world_box_local": local}


def _add_reveal(C, world, actor, section):
    """S3Millstone/s3_props_ue.py:843-860 _add_reveal (ran S3PROPS-20261007-173446) [prec]."""
    rise = _load(C.RISE, unreal.LevelSequence)
    if abs(_fps(rise) - section["fps"]) > 1e-6:
        raise RuntimeError("RISE_FPS_CHANGED")
    b = rise.add_possessable(actor)
    t = b.add_track(unreal.MovieSceneVisibilityTrack)
    s = t.add_section()
    s.set_range_seconds(section["range_s"][0], section["range_s"][1])
    s.set_completion_mode(getattr(unreal.MovieSceneCompletionMode, section["completion_mode"]))
    ch = list(s.get_all_channels())
    if len(ch) != 1:
        raise RuntimeError("REVEAL_CHANNELS|%d" % len(ch))
    for frame, value in section["keys"]:
        ch[0].add_key(unreal.FrameNumber(int(frame)), bool(value), time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    g = _guid(b.get_id())
    got = _rise_visibility(rise, world, actor)
    if got == "UNREAD" or len(got) != 1 or got[0]["keys"] != [[int(f), bool(v)] for f, v in section["keys"]]:
        raise RuntimeError("REVEAL_READBACK|%s" % got)
    return g


def _remove_binding(seq, world, guid, want_resolved):
    rows = [b for b in seq.get_bindings() if _guid(b.get_id()) == guid]
    if len(rows) != 1:
        raise RuntimeError("BINDING_COUNT|%s|%d" % (guid, len(rows)))
    if want_resolved is not None and _located(seq, rows[0], world) != sorted(want_resolved):
        raise RuntimeError("BINDING_TARGET|%s|%s" % (guid, _located(seq, rows[0], world)))
    rows[0].remove()                                                      # returns None: re-list
    if [b for b in seq.get_bindings() if _guid(b.get_id()) == guid]:
        raise RuntimeError("BINDING_SURVIVED|%s" % guid)


def _verify_apply(C, world, record):
    plan = record["plan"]
    for c in record["created"]:
        s = next(x for x in plan["spawns"] if x["label"] == c["label"])
        _verify_spawned(C, world, c["actor_path"], s, record["root_path"])
    for h in plan["hides"]:
        a = _by_path(world, h["object_path"])
        if a is None or _flags(a) != h["after"]:
            raise RuntimeError("SPLIT_FLAGS|%s|%s" % (h["label"], _flags(a) if a else None))


def run_apply(C, run, world):
    rows = _rows(C)
    st = live_state(C, world, rows)
    plan = C.plan_apply(st, rows)
    record = {"run": run, "world": C.WORLD, "plan": plan, "root_path": st["root"]["object_path"],
              "root_world": st["root"]["world"], "created": [], "saved": False, "applied": False}
    _write(APPLY_RECORD, record, exclusive=True)                         # RECORD FIRST
    unreal.log("%s_RECORD|run=%s|path=%s" % (C.MARK, run, APPLY_RECORD))
    record["backup"] = _backup(C, run, "", (APPLY_RECORD,))
    _write(APPLY_RECORD, record)
    root = _by_path(world, record["root_path"])
    for h in plan["hides"]:
        _set_flags(_by_path(world, h["object_path"]), h["after"])
    for s in plan["spawns"]:
        a = _spawn(C, world, root, s)
        row = {"label": s["label"], "actor_path": _path(a), "reveal_guid": None}
        record["created"].append(row)
        _write(APPLY_RECORD, record)
        _verify_spawned(C, world, row["actor_path"], s, record["root_path"])
        if plan["reveal"]["mode"] == "copy":
            row["reveal_guid"] = _add_reveal(C, world, a, plan["reveal"]["section"])
            _write(APPLY_RECORD, record)
    _verify_apply(C, world, record)
    _save(C, world, plan["content_saves"], map_expected=True)
    record["saved"] = True
    _write(APPLY_RECORD, record)
    _verify_apply(C, world, record)                                      # fresh lookups after the save
    record["applied"] = True
    _write(APPLY_RECORD, record)
    return {"spawned": len(record["created"]), "hidden": len(plan["hides"]), "reveal": plan["reveal"]["mode"],
            "backup": record["backup"]}


def run_revert(C, run, world):
    record = _read(APPLY_RECORD)
    if not record or not record.get("saved"):
        raise RuntimeError("RECORD_INVALID (partial APPLY: restore %s with the editor closed)" % (record or {}).get("backup"))
    _verify_apply(C, world, record)                                      # drift -> refuse before mutating
    backup = _backup(C, run, "-REVERT", (APPLY_RECORD,))
    rise = _load(C.RISE, unreal.LevelSequence)
    for op in C.revert_ops(record):
        if op["op"] == "remove_reveal":
            _remove_binding(rise, world, op["guid"], [op["actor_path"]])
        elif op["op"] == "destroy":
            a = _by_path(world, op["actor_path"])
            if a is None or str(a.get_actor_label()) != op["label"] or C.TAG not in [str(t) for t in a.tags]:
                raise RuntimeError("DESTROY_TARGET|%s" % op["label"])
            if not unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(a):
                raise RuntimeError("DESTROY|%s" % op["label"])
            if _by_path(world, op["actor_path"]) is not None:
                raise RuntimeError("DESTROY_SURVIVED|%s" % op["label"])
        elif op["op"] == "hide":
            _set_flags(_by_path(world, op["object_path"]), op["flags"])
    _save(C, world, record["plan"]["content_saves"], map_expected=True)
    for h in record["plan"]["hides"]:
        if _flags(_by_path(world, h["object_path"])) != h["before"]:
            raise RuntimeError("REVERT_FLAGS|%s" % h["label"])
    for c in record["created"]:
        if _by_path(world, c["actor_path"]) is not None:
            raise RuntimeError("REVERT_ACTOR_PRESENT|%s" % c["label"])
    os.replace(APPLY_RECORD, APPLY_RECORD + ".reverted-" + run)
    return {"backup": backup, "destroyed": len(record["created"])}


# =================================================================================================== MOTION
CHANNELS = ("Location.X", "Location.Y", "Location.Z", "Rotation.X", "Rotation.Y", "Rotation.Z",
            "Scale.X", "Scale.Y", "Scale.Z")


def _canonical(channel):
    import re
    try:
        name = str(channel.get_name())
    except Exception:  # noqa: BLE001
        name = str(channel.get_editor_property("channel_name"))
    name = re.sub(r"_\d+$", "", name)                                    # proxies renumber (ue58-fbx-import-traps)
    return name if name in CHANNELS else None


def _motion_rows_live(C, world):
    record = _read(APPLY_RECORD)
    if not record or not record.get("applied"):
        raise C.PlanError("APPLY_NOT_APPLIED")
    _verify_apply(C, world, record)
    rows = _rows(C)
    by_label = {r["label"]: r for r in rows}
    actors = {c["label"]: c["actor_path"] for c in record["created"]}
    return rows, actors, record, by_label


def run_motion_dry(C, run, world, census):
    rows, actors, _record, _ = _motion_rows_live(C, world)
    root_seq, _rise, seqst = _seq_state(C)
    plan = C.plan_motion(seqst, rows, _read(MOTION_PLAN))
    existing = {}
    for label, path in actors.items():
        existing[label] = _seq_tracks_for(root_seq, world, [path], [label])
    flick = {}
    pilot = _pilot()
    sme = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    mel = unreal.MaterialEditingLibrary
    for r in rows:
        mesh = _load(r["mesh"], unreal.StaticMesh)
        dyn = pilot.dynamic_lod(mesh, 0)
        fm = dyn["materials"].get("1") or {}
        mi = _load(r["mi"]["Flap"], unreal.MaterialInstanceConstant)
        sw = None
        if "Flutter" in [str(n) for n in mel.get_static_switch_parameter_names(mi)]:
            sw = bool(mel.get_material_instance_static_switch_parameter_value(mi, "Flutter"))
        flick[r["suffix"]] = {"foam": r["foam"], "lod0_flap_triangles": fm.get("triangles", 0),
                              "flap_r_range": fm.get("r_range"), "flutter_switch": sw,
                              "flutter_amp": float(mel.get_material_instance_scalar_parameter_value(mi, "FlutterAmpCm")),
                              "lod1_screen_size": float(sme.get_lod_screen_sizes(mesh)[1])}
    out = {"run": run, "census": census, "sequence": seqst,
           "plan_summary": {k: plan[k] for k in ("fps", "playback", "vamp", "frames", "layers", "worst", "track")},
           "existing_bindings": existing, "flicker": C.flicker_verdict(flick), "flicker_reads": flick,
           "conflicts": {l: v for l, v in existing.items() if v}}
    if _census() != census:
        raise RuntimeError("DRY_DIRTIED|%s" % _census())
    path = os.path.join(HERE, "s3_waves_v3_motion_dry_%s.json" % run)
    _write(path, out)
    return out, path


def _add_motion_track(C, seq, binding, keys):
    track = binding.add_track(unreal.MovieScene3DTransformTrack)
    track.set_display_name(C.MOTION_TRACK)
    section = track.add_section()
    section.set_range(keys[0]["frame"], keys[-1]["frame"] + 1)
    chans = {_canonical(c): c for c in section.get_all_channels() if _canonical(c)}
    if set(chans) != set(CHANNELS):
        raise RuntimeError("NEW_TRACK_CHANNELS|%s" % sorted(chans))
    for name, value in zip(CHANNELS[6:], keys[0]["scale"]):
        chans[name].set_default(float(value))
    for k in keys:
        for name, value in zip(CHANNELS[:6], k["location"] + k["rotation"]):
            chans[name].add_key(unreal.FrameNumber(int(k["frame"])), float(value),
                                time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                                interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
    return track


def _verify_motion_track(C, binding, keys, label):
    """s3_wave_split_apply.py:451-466 _verify_track [prec]."""
    ours = [t for t in binding.get_tracks() if str(t.get_display_name()) == C.MOTION_TRACK]
    if len(ours) != 1 or len(ours[0].get_sections()) != 1:
        raise RuntimeError("MOTION_TRACK_COUNT|%s" % label)
    sec = ours[0].get_sections()[0]
    chans = {_canonical(c): c for c in sec.get_all_channels() if _canonical(c)}
    frames_want = [k["frame"] for k in keys]
    for i, name in enumerate(CHANNELS[:6]):
        got = sorted(chans[name].get_keys(), key=lambda k: _frame(k.get_time()))
        fr = [_frame(k.get_time()) for k in got]
        vals = [float(k.get_value()) for k in got]
        want = [float((k["location"] + k["rotation"])[i]) for k in keys]
        if fr != frames_want or any(abs(a - b) > 0.001 for a, b in zip(vals, want)):
            raise RuntimeError("MOTION_KEY_READBACK|%s|%s" % (label, name))
    return {"keys": len(frames_want), "first": frames_want[0], "last": frames_want[-1],
            "section": [_frame(sec.get_start_frame()), _frame(sec.get_end_frame())]}


def run_motion_apply(C, run, world):
    rows, actors, _ar, _ = _motion_rows_live(C, world)
    root_seq, _rise, seqst = _seq_state(C)
    plan = C.plan_motion(seqst, rows, _read(MOTION_PLAN))
    for label, path in actors.items():
        if _seq_tracks_for(root_seq, world, [path], [label]):
            raise RuntimeError("ACTOR_ALREADY_BOUND|%s" % label)
    rec = {"run": run, "plan_summary": {k: plan[k] for k in ("fps", "playback", "vamp", "frames", "layers", "worst")},
           "bindings": [], "saved": False}
    _write(MOTION_RECORD, rec, exclusive=True)
    rec["backup"] = _backup(C, run, "Motion", (MOTION_RECORD,))
    _write(MOTION_RECORD, rec)
    for p in plan["pieces"]:
        a = _by_path(world, actors[p["label"]])
        b = root_seq.add_possessable(a)
        g = _guid(b.get_id())
        rec["bindings"].append({"label": p["label"], "guid": g, "actor_path": actors[p["label"]]})
        _write(MOTION_RECORD, rec)
        if _located(root_seq, b, world) != [actors[p["label"]]]:
            raise RuntimeError("BINDING_RESOLVES|%s" % p["label"])
        _add_motion_track(C, root_seq, b, p["keys"])
        rec["bindings"][-1]["readback"] = _verify_motion_track(C, b, p["keys"], p["label"])
    c = _census()
    if c["content"] != [C.ROOT_SEQ] or c["maps"] not in ([], [C.WORLD]):
        raise RuntimeError("DIRTY_SCOPE|%s" % json.dumps(c))
    _save(C, world, [C.ROOT_SEQ], map_expected=bool(c["maps"]))
    rec["saved"] = True
    _write(MOTION_RECORD, rec)
    root_seq = _load(C.ROOT_SEQ, unreal.LevelSequence)
    by = {_guid(b.get_id()): b for b in root_seq.get_bindings()}
    for brow, p in zip(rec["bindings"], plan["pieces"]):
        _verify_motion_track(C, by[brow["guid"]], p["keys"], p["label"])
    rec["applied"] = True
    _write(MOTION_RECORD, rec)
    return {"bindings": len(rec["bindings"]), "frames": plan["frames"], "worst": plan["worst"],
            "l5_clamp": [L for L in plan["layers"] if L["clamped_from"]]}


def run_motion_revert(C, run, world):
    rec = _read(MOTION_RECORD)
    if not rec or not rec.get("saved"):
        raise RuntimeError("MOTION_RECORD_INVALID (partial: restore %s with the editor closed)" % (rec or {}).get("backup"))
    root_seq = _load(C.ROOT_SEQ, unreal.LevelSequence)
    by = {_guid(b.get_id()): b for b in root_seq.get_bindings()}
    for brow in rec["bindings"]:
        b = by.get(brow["guid"])
        if b is None or [str(t.get_display_name()) for t in b.get_tracks()] != [C.MOTION_TRACK]:
            raise RuntimeError("MOTION_BINDING_CHANGED|%s" % brow["label"])
    backup = _backup(C, run, "Motion-REVERT", (MOTION_RECORD,))
    for brow in rec["bindings"]:
        _remove_binding(root_seq, world, brow["guid"], [brow["actor_path"]])
    c = _census()
    _save(C, world, [C.ROOT_SEQ], map_expected=bool(c["maps"]))
    os.replace(MOTION_RECORD, MOTION_RECORD + ".reverted-" + run)
    return {"removed": len(rec["bindings"]), "backup": backup}


# =================================================================================================== LIGHT
def _light_state(C, world):
    idx = _index(world)
    if len(idx.get(C.ROOT_LABEL, [])) != 1:
        raise C.PlanError("ROOT_COUNT|%d" % len(idx.get(C.ROOT_LABEL, [])))
    root = idx[C.ROOT_LABEL][0]
    rakes = idx.get(C.RAKE_LABEL, [])
    rake = {"count": len(rakes)}
    root_seq, rise, seqst = _seq_state(C)
    if len(rakes) == 1:
        comp = rakes[0].get_component_by_class(unreal.LightComponent)
        rake.update({"object_path": _path(rakes[0]), "component_path": _path(comp),
                     "colour": {"use_temperature": bool(comp.get_editor_property("use_temperature")),
                                "temperature": float(comp.get_editor_property("temperature"))},
                     "intensity": float(comp.get_editor_property("intensity"))})
        names = [C.RAKE_LABEL, str(comp.get_name())]
        b_rows = (_seq_tracks_for(rise, world, [_path(rakes[0]), _path(comp)], names) +
                  _seq_tracks_for(root_seq, world, [_path(rakes[0]), _path(comp)], names))
        rake["bindings"] = b_rows
        rake["animated_properties"] = sorted({t["property"] for b in b_rows for t in b["tracks"] if t["property"]})
    root_tf = _world_tf(root)
    ehf = []
    for a in _all_actors(world):
        if a.get_class().get_name() in ("ExponentialHeightFog",):
            p = a.get_attach_parent_actor()
            local = C.tf_inv_point(root_tf, _v(a.get_actor_location()))
            inside = -200 <= local[0] <= 6600 and -1200 <= local[1] <= 1200 and -400 <= local[2] <= 3500
            ehf.append({"label": str(a.get_actor_label()), "path": _path(a), "local": local,
                        "attached_to_root": bool(p and str(p.get_actor_label()) == C.ROOT_LABEL),
                        "in_s3": bool(inside or (p and str(p.get_actor_label()) == C.ROOT_LABEL) or
                                      str(a.get_actor_label()).startswith("S3"))})
    labels = [s["label"] for s in C.light_specs()] + [C.HAZE["label"]]
    return root_seq, {"root": {"world": root_tf, "object_path": _path(root)}, "rake": rake, "ehf": ehf,
                      "label_count": {l: len(idx.get(l, [])) for l in labels}, "local_fog_class": hasattr(unreal, "LocalFogVolume"),
                      **seqst}


def run_light_dry(C, run, world, census):
    _rs, st = _light_state(C, world)
    out = {"run": run, "census": census, "state": st}
    try:
        out["plan"] = C.plan_light(st)
        out["light"] = "would_apply"
    except C.PlanError as exc:
        out["light"] = "LIGHT_WOULD_REFUSE|%s" % exc
    if _census() != census:
        raise RuntimeError("DRY_DIRTIED|%s" % _census())
    path = os.path.join(HERE, "s3_waves_v3_light_dry_%s.json" % run)
    _write(path, out)
    return out, path


def _spawn_rect(C, root, spec):
    """s3_daylight_apply.py:380-401 _spawn_daylight (ran: s3_daylight_record.json applied) [prec]; modify() added."""
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    a = eas.spawn_actor_from_class(unreal.RectLight, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0), False)
    if a is None:
        raise RuntimeError("LIGHT_SPAWN|%s" % spec["label"])
    a.set_actor_label(spec["label"])
    a.set_editor_property("tags", [unreal.Name(C.LIGHT_TAG), unreal.Name(C.TAG)])
    a.set_folder_path(C.FOLDER)
    a.attach_to_actor(root, "", unreal.AttachmentRule.KEEP_RELATIVE, unreal.AttachmentRule.KEEP_RELATIVE,
                      unreal.AttachmentRule.KEEP_RELATIVE, False)
    rc = a.get_editor_property("root_component")
    rc.set_relative_location(unreal.Vector(*spec["location"]), False, False)
    r = spec["rotation"]
    rc.set_relative_rotation(unreal.Rotator(roll=r[0], pitch=r[1], yaw=r[2]), False, False)
    c = a.get_component_by_class(unreal.RectLightComponent)
    c.modify()
    c.set_mobility(unreal.ComponentMobility.MOVABLE)
    c.set_editor_property("intensity_units", unreal.LightUnits.CANDELAS)
    c.set_editor_property("intensity", float(spec["intensity_cd"]))
    c.set_editor_property("attenuation_radius", float(spec["attenuation_cm"]))
    c.set_editor_property("source_width", float(spec["rect_cm"][0]))
    c.set_editor_property("source_height", float(spec["rect_cm"][1]))
    c.set_editor_property("use_temperature", True)
    c.set_editor_property("temperature", float(spec["temperature_k"]))
    c.set_editor_property("cast_shadows", bool(spec["shadows"]))
    got = {"intensity": float(c.get_editor_property("intensity")), "temperature": float(c.get_editor_property("temperature")),
           "shadows": bool(c.get_editor_property("cast_shadows")), "rel": _rel_tf(a)}
    if (abs(got["intensity"] - spec["intensity_cd"]) > 1e-3 or abs(got["temperature"] - spec["temperature_k"]) > 1e-3
            or got["shadows"] != bool(spec["shadows"]) or not C.near(got["rel"]["location"], spec["location"], 0.05)):
        raise RuntimeError("LIGHT_READBACK|%s|%s" % (spec["label"], got))
    return a, c


def _add_intensity_track(C, seq, comp, keys):
    b = seq.add_possessable(comp)
    track = b.add_track(unreal.MovieSceneFloatTrack)
    track.set_property_name_and_path("Intensity", "Intensity")
    track.set_display_name(C.LIGHT_TRACK)
    s = track.add_section()
    s.set_range(int(keys[0][0]), int(keys[-1][0]) + 1)
    ch = list(s.get_all_channels())
    if len(ch) != 1:
        raise RuntimeError("LIGHT_CHANNELS|%d" % len(ch))
    for f, v in keys:
        ch[0].add_key(unreal.FrameNumber(int(f)), float(v), time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                      interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
    got = [[_frame(k.get_time()), float(k.get_value())] for k in sorted(ch[0].get_keys(), key=lambda k: _frame(k.get_time()))]
    if [g[0] for g in got] != [int(k[0]) for k in keys] or any(abs(g[1] - k[1]) > 1e-3 for g, k in zip(got, keys)):
        raise RuntimeError("LIGHT_KEYS_READBACK|%s" % got)
    return b


def run_light_apply(C, run, world):
    root_seq, st = _light_state(C, world)
    plan = C.plan_light(st)
    gs_before = {_guid(b.get_id()) for b in root_seq.get_bindings()}
    rec = {"run": run, "plan": plan, "created": [], "created_bindings": [], "rake_done": False, "saved": False}
    _write(LIGHT_RECORD, rec, exclusive=True)
    rec["backup"] = _backup(C, run, "Light", (LIGHT_RECORD,))
    _write(LIGHT_RECORD, rec)
    root = _by_path(world, st["root"]["object_path"])
    for spec in plan["lights"]:
        a, comp = _spawn_rect(C, root, spec)
        rec["created"].append({"label": spec["label"], "actor_path": _path(a)})
        _write(LIGHT_RECORD, rec)
        b = _add_intensity_track(C, root_seq, comp, spec["keys"])
        for bb in (b, b.get_parent()):
            if bb is not None and bb.is_valid():
                g = _guid(bb.get_id())
                if g not in gs_before and g not in [x["guid"] for x in rec["created_bindings"]]:
                    rec["created_bindings"].append({"guid": g, "child": bb is b, "label": spec["label"]})
        _write(LIGHT_RECORD, rec)
    if plan["haze"]["mode"] == "APPLY":
        h = plan["haze"]
        eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        a = eas.spawn_actor_from_class(unreal.LocalFogVolume, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0), False)
        a.set_actor_label(h["label"])
        a.set_editor_property("tags", [unreal.Name(C.LIGHT_TAG), unreal.Name(C.TAG)])
        a.set_folder_path(C.FOLDER)
        a.attach_to_actor(root, "", unreal.AttachmentRule.KEEP_RELATIVE, unreal.AttachmentRule.KEEP_RELATIVE,
                          unreal.AttachmentRule.KEEP_RELATIVE, False)
        rc = a.get_editor_property("root_component")
        rc.set_relative_location(unreal.Vector(*h["relative"]["location"]), False, False)
        rc.set_relative_scale3d(unreal.Vector(*h["relative"]["scale"]))
        fc = a.get_component_by_class(unreal.LocalFogVolumeComponent)
        fc.modify()
        for k, v in h["params"].items():
            fc.set_editor_property(k, unreal.LinearColor(*v) if k == "fog_albedo" else float(v))
        for k, v in h["params"].items():
            g = fc.get_editor_property(k)
            g = [g.r, g.g, g.b, g.a] if k == "fog_albedo" else [float(g)]
            if not C.near(g, v if isinstance(v, list) else [v], 1e-4):
                raise RuntimeError("HAZE_READBACK|%s|%s" % (k, g))
        rec["created"].append({"label": h["label"], "actor_path": _path(a)})
        _write(LIGHT_RECORD, rec)
    rake = _by_path(world, plan["rake"]["object_path"])
    rc = rake.get_component_by_class(unreal.LightComponent)
    rake.modify()
    rc.modify()
    rc.set_editor_property("use_temperature", True)
    rc.set_editor_property("temperature", float(plan["rake"]["after"]["temperature"]))
    if (not bool(rc.get_editor_property("use_temperature")) or
            abs(float(rc.get_editor_property("temperature")) - plan["rake"]["after"]["temperature"]) > 1e-3):
        raise RuntimeError("RAKE_READBACK")
    rec["rake_done"] = True
    _write(LIGHT_RECORD, rec)
    _save(C, world, [C.ROOT_SEQ], map_expected=True)
    rec["saved"] = True
    _write(LIGHT_RECORD, rec)
    root_seq = _load(C.ROOT_SEQ, unreal.LevelSequence)
    gl = {_guid(b.get_id()) for b in root_seq.get_bindings()}
    missing = [b["guid"] for b in rec["created_bindings"] if b["guid"] not in gl]
    if missing:
        raise RuntimeError("POST_SAVE_BINDINGS|%s" % missing)
    for c in rec["created"]:
        if _by_path(world, c["actor_path"]) is None:
            raise RuntimeError("POST_SAVE_LIGHT|%s" % c["label"])
    rec["applied"] = True
    _write(LIGHT_RECORD, rec)
    return {"lights": len(plan["lights"]), "haze": plan["haze"]["mode"], "rake": plan["rake"]["after"],
            "backup": rec["backup"]}


def run_light_revert(C, run, world):
    rec = _read(LIGHT_RECORD)
    if not rec or not rec.get("saved"):
        raise RuntimeError("LIGHT_RECORD_INVALID (partial: restore %s with the editor closed)" % (rec or {}).get("backup"))
    backup = _backup(C, run, "Light-REVERT", (LIGHT_RECORD,))
    root_seq = _load(C.ROOT_SEQ, unreal.LevelSequence)
    for b in sorted(rec["created_bindings"], key=lambda x: not x["child"]):      # children first
        _remove_binding(root_seq, world, b["guid"], None)
    for c in rec["created"]:
        a = _by_path(world, c["actor_path"])
        if a is None or C.LIGHT_TAG not in [str(t) for t in a.tags]:
            raise RuntimeError("LIGHT_DESTROY_TARGET|%s" % c["label"])
        if not unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(a):
            raise RuntimeError("LIGHT_DESTROY|%s" % c["label"])
    rake = _by_path(world, rec["plan"]["rake"]["object_path"])
    rc = rake.get_component_by_class(unreal.LightComponent)
    rake.modify()
    rc.modify()
    before = rec["plan"]["rake"]["before"]
    rc.set_editor_property("use_temperature", bool(before["use_temperature"]))
    rc.set_editor_property("temperature", float(before["temperature"]))
    if (bool(rc.get_editor_property("use_temperature")) != bool(before["use_temperature"]) or
            abs(float(rc.get_editor_property("temperature")) - float(before["temperature"])) > 1e-3):
        raise RuntimeError("RAKE_REVERT_READBACK")
    _save(C, world, [C.ROOT_SEQ], map_expected=True)
    os.replace(LIGHT_RECORD, LIGHT_RECORD + ".reverted-" + run)
    return {"backup": backup, "removed_lights": len(rec["created"]), "removed_bindings": len(rec["created_bindings"])}


# =================================================================================================== main
def main():
    C = _core()
    run = "S3WAVESV3-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    mode = "?"
    try:
        args = _read(ARGS, {})
        run = args.get("run") or run
        ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        in_pie = ed.get_game_world() is not None
        mode = C.check_mode(args, in_pie, {"apply": os.path.exists(APPLY_RECORD), "motion": os.path.exists(MOTION_RECORD),
                                           "light": os.path.exists(LIGHT_RECORD)})
        unreal.log("%s_START|run=%s|mode=%s|pieces=%s" % (C.MARK, run, mode, args.get("pieces")))
        if mode == "VERIFY":
            rep = run_verify(C, run)
            unreal.log("%s_VERIFY_%s|run=%s|ready=%d/12|out=%s" % (C.MARK, "OK" if rep["all_ready"] else "PARTIAL", run,
                                                                   len(rep["ready"]), VERIFY_REPORT))
            return
        world = _editor_world()
        census = _guard(C, world, need_clean=mode not in C.READ_ONLY)
        if mode == "DRY":
            out, path = run_dry(C, run, world, census)
            unreal.log("%s_DRY_OK|run=%s|mutated=0|apply=%s|out=%s" % (C.MARK, run, out["apply"], path))
        elif mode == "IMPORT":
            r = run_import(C, run, args, world)
            unreal.log("%s_IMPORT_OK|run=%s|piece=%s|lods=%d|sizes_unverified(VERIFY next)" % (
                C.MARK, run, r["suffix"], r["mesh_gate"]["num_lods"]))
        elif mode == "BUILD_MAT":
            r = run_build_mat(C, run, args, world)
            unreal.log("%s_BUILD_MAT_OK|run=%s|%s" % (C.MARK, run, json.dumps(r)))
        elif mode == "APPLY":
            try:
                r = run_apply(C, run, world)
            except Exception:
                rec = _read(APPLY_RECORD)
                if rec is not None and not rec.get("saved"):
                    os.replace(APPLY_RECORD, APPLY_RECORD + ".failed-" + run)
                raise
            unreal.log("%s_APPLY_OK|run=%s|level_saved=1|dirty_after=0+0|%s" % (C.MARK, run, json.dumps(r)))
        elif mode == "REVERT":
            r = run_revert(C, run, world)
            unreal.log("%s_REVERT_OK|run=%s|%s" % (C.MARK, run, json.dumps(r)))
        elif mode == "MOTION_DRY":
            out, path = run_motion_dry(C, run, world, census)
            unreal.log("%s_MOTION_DRY_OK|run=%s|mutated=0|worst=%s|conflicts=%d|out=%s" % (
                C.MARK, run, json.dumps(out["plan_summary"]["worst"]), len(out["conflicts"]), path))
        elif mode == "MOTION_APPLY":
            try:
                r = run_motion_apply(C, run, world)
            except Exception:
                rec = _read(MOTION_RECORD)
                if rec is not None and not rec.get("saved"):
                    os.replace(MOTION_RECORD, MOTION_RECORD + ".failed-" + run)
                raise
            unreal.log("%s_MOTION_APPLY_OK|run=%s|%s" % (C.MARK, run, json.dumps(r)))
        elif mode == "MOTION_REVERT":
            r = run_motion_revert(C, run, world)
            unreal.log("%s_MOTION_REVERT_OK|run=%s|%s" % (C.MARK, run, json.dumps(r)))
        elif mode == "LIGHT_DRY":
            out, path = run_light_dry(C, run, world, census)
            unreal.log("%s_LIGHT_DRY_OK|run=%s|mutated=0|light=%s|out=%s" % (C.MARK, run, out["light"], path))
        elif mode == "LIGHT_APPLY":
            try:
                r = run_light_apply(C, run, world)
            except Exception:
                rec = _read(LIGHT_RECORD)
                if rec is not None and not rec.get("saved"):
                    os.replace(LIGHT_RECORD, LIGHT_RECORD + ".failed-" + run)
                raise
            unreal.log("%s_LIGHT_APPLY_OK|run=%s|%s" % (C.MARK, run, json.dumps(r)))
        elif mode == "LIGHT_REVERT":
            r = run_light_revert(C, run, world)
            unreal.log("%s_LIGHT_REVERT_OK|run=%s|%s" % (C.MARK, run, json.dumps(r)))
    except Exception as exc:  # noqa: BLE001
        census = None
        try:
            census = _census()
        except Exception:  # noqa: BLE001
            pass
        unreal.log_error("%s_FAILED|run=%s|mode=%s|%s|census=%s|%s" % (
            C.MARK if "C" in dir() else "S3WAVESV3", run, mode, str(exc).replace("\n", " ")[:900], json.dumps(census),
            "nothing saved unless an _OK marker printed; dirty map/assets: Don't-Save restart (never reload)"))


if __name__ == "__main__" and unreal is not None:
    main()
