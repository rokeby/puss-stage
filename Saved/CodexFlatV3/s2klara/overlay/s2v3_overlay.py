"""S2 V3 WINGS OVERLAY -- editor tool (8 Oct). Offline-written, NOT RUN IN UNREAL. One mode per MCP call.
Runner s2v3_overlay_run.py, request s2v3_overlay_request.json, args s2v3_overlay_args.json, pure maths in
s2v3_overlay_core.py (loaded by file path each call; harness test_s2v3_overlay_offline.py).

GOAL (Gary 8 Oct): Klara's 15 falling S2 wings (5 L, 5 R, 5 ceiling; actors in her streamed level Japanese_Alley; they
fall via the keys of her re-keyed copy LS_NEW_SHRINE_S2Hangar, nested in LS_DevScene_02 on 'Klara Hookin - Replacement
Shot') are replaced by OUR Flat V3 rebuilds (owners S2K_*), WITHOUT saving her level or her sequences.

MECHANISM (conductor rules, 8 Oct)
  * A NEW level sequence of ours (args.overlay_asset) nested in LS_DevScene_02 on OUR OWN MovieSceneSubTrack named
    'S2 V3 Wings Overlay'.  COVERAGE (Gary 8 Oct, 'ours throughout'): default 'scene' = from the moment her level becomes
    visible (the hookin's 'Klara Levels (hookin)' Level Visibility section start, read live; recorded 104) to the hookin
    section end (3891).  Over the wide shot [104, 376) our wings HOLD her pre-section pose -- the pose her actor shows
    while her section is not evaluating (DRY measures it: her live actor pose vs her keys' rest/first pose; the offline
    census reads her saved actors at the REST height, z 789 / 2430 [meas her_wings_census.json]) -- via one CONSTANT key
    at our local 0; her keys follow, shifted by the pre-roll in ticks (272 parent frames @25 = 10.88 s = 261120 ticks),
    so at parent 376 our keys line up with hers.  'cinematic' = the old behaviour (exactly the hookin section).
    Section parameters are copied from the hookin section (start offset must be 0: checked by the mapping).
    Nothing else in LS_DevScene_02 changes: a semantic fingerprint (every binding/track/section/channel: keys, values,
    defaults, ranges, sub-section parameters via export_text) before vs after may differ ONLY by our track's rows.
  * In the overlay, 15 possessables on HER actors (resolve into her non-instanced streamed level by package path, as
    the hookin's own 'Hers Dark' bindings do [prec klara_hookin.py:1858-1872]), each with a MovieSceneVisibilityTrack
    bound to bHidden whose bool channel stores VISIBLE: default False = hidden, RESTORE_STATE
    [decl MovieScenePropertyTrack.h:53-56; meas s2_vis_fix.py PIE probe PIES2VIS-185717: bHiddenInGame is inert].
  * 15 SPAWNABLE StaticMeshActors of ours (design choice: see PROPOSAL section in the final report) with the S2K_* mesh
    of their type, Front material variant A|B, scale 1, mobility MOVABLE, and a 3D transform track whose keys copy her
    binding's keys in the hookin COPY (world-space after its rigid re-key [meas seq record S2 rekey: ABSOLUTE,
    world-space]) composed with the per-type child transform from DerivedAssets/FlatV3/KlaraS2/pivot/pivot_offsets.json
    (rule 'world(ours) = HerActorTransform(location, rotation only) * Translate(T) * RotZ(180)'), cross-checked with
    IMPORT_MANIFEST_KlaraS2.json klara_s2.pivot; mesh paths from rzimport_plan_offline_KlaraS2.json (planned);
    A/B material maps from the manifest's klara_s2.front_variants (Timber/Edge 'unchanged' = mesh default).
    Her X/Y/roll/pitch are NOT constant (x +-5..34 cm, y down 131 cm, roll to 3.3 deg [meas her_seq_decode.json]), so
    the default copies all six channels ('copy_channels': 'all'); 'z_only' holds the rest values instead.
  * SAMPLED, not copied (live DRY S2V3OV-20261008-212010: the copy's x/y/z/roll/pitch keys are RCIM_CUBIC for all 15
    wings; whether that is her authoring or the re-key is not assumed).  Each channel is EVALUATED BY UE
    (evaluate_keys on a make_range(start, duration) built in DISPLAY frames; the value count is asserted -- a default
    SequencerScriptingRange is 60000 fps and returns ~1 value, conductor 8 Oct) at every 160 ticks (150 fps = gcd of
    the copy's 30 fps and the Scene's 25 fps frames, so every renderable tick is a sample)
    [decl MovieSceneScriptingChannel.h:218-245: EvaluateKeysInChannel steps one requested-rate frame from the range's
    lower tick].  Proof the samples sit on the right ticks: at every key tick the evaluated value equals the key value.
    Each sample is composed with the child transform; LINEAR keys are fitted (0.1 cm / 0.01 deg) and GATED: at every
    sample our keys must match her composed pose within 0.5 cm / 0.05 deg.  Source key hashes (values, interpolation
    and tangents) stay, for re-ingest detection.

MODES (args.mode; confirm '<MODE> S2V3OVERLAY'; decided_by for writes)
  DRY      read-only: her 15 actors (live), the copy's 15 transform channels (+ source key hashes), the plan, box
           alignment, fingerprint of LS_DevScene_02, expected foreign bindings (bHidden-fixed), census, API probes.
           -> s2v3_overlay_dry_<run>.json + S2V3OV_DRY_OK.  APPLY requires args.dry_report and the same plan digest.
  APPLY    originals FIRST (path logged), record, Backups/PreS2V3Overlay-<run>; create the overlay (create-only); hide
           bindings; spawnables; nest; fingerprint diff; census EXACTLY {overlay, LS_DevScene_02}, NO map dirty (a
           Klara package dirty = stop); save overlay, then LS_DevScene_02; same-call read-back.  S2V3OV_APPLY_OK
  VARIANT  args.variant A|B: rewrite ONLY our 15 templates' override_materials (every material must load first, else
           nothing changes); census {overlay}; save overlay.  B's MIs are made by a later Unreal step (manifest
           'who_writes_it'), so DRY only WARNS when the variant not being applied is missing.
  RESYNC   re-ingest detected (copy key hashes != record): re-copy keys into our 15 transform tracks; census {overlay}.
           Equal hashes -> S2V3OV_RESYNC_NOOP (nothing saved).  A moved hookin section needs REVERT + APPLY.
  VERIFY   read-only, a LATER call: LS_DevScene_02 vs record, our track/section, bindings resolve to her actors
           (locate_bound_objects, never get_bound_objects), templates, keys, source hashes.  S2V3OV_VERIFY_OK/_FAILED
  REVERT   field-scoped: removes OUR track from LS_DevScene_02 (fingerprint after == now minus our rows); save it.
           The overlay asset stays on disk, unreferenced (re-APPLY needs a new overlay_asset path or a manual delete).

Never: Save All, save_map, reload a level, open/scrub Sequencer, end PIE, poke a spawned actor (writes the template
[memory ue58-geometrycache-sequencer-traps]), get_bound_objects, delete assets; no unreal objects at module level.
"""
import datetime
import hashlib
import importlib.util
import json
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:  # offline harness
    unreal = None

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
ARGS_NAME = "s2v3_overlay_args.json"
RECORD = os.path.join(HERE, "s2v3_overlay_record.json")
ORIGINALS = os.path.join(HERE, "s2v3_overlay_originals.json")
CENSUS_JSON = os.path.join(HERE, "..", "her_wings_census.json")


# =================================================================================================== small helpers
def _core():
    spec = importlib.util.spec_from_file_location("s2v3_overlay_core_live", os.path.join(HERE, "s2v3_overlay_core.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read(path):
    if not path or not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write(path, data, exclusive=False):
    if exclusive:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        f = os.fdopen(fd, "w", encoding="utf-8")
    else:
        tmp = path + ".tmp"
        f = open(tmp, "w", encoding="utf-8")
    with f:
        json.dump(data, f, indent=1, sort_keys=True, default=str)
        f.flush()
        os.fsync(f.fileno())
    if not exclusive:
        os.replace(tmp, path)


def _abs(p):
    if not p:
        return None
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(PROJECT, p))


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _content_file(path, ext=".uasset"):
    return os.path.join(PROJECT, "Content", *path[len("/Game/"):].split("/")) + ext


def _pkg(obj):
    return str(obj.get_path_name()).split(".")[0] if obj is not None else None


def _enum(v):
    return str(getattr(v, "name", v)).split(".")[-1]


def _guid(b):
    return str(unreal.GuidLibrary.conv_guid_to_string(b.get_id()))


def _rate(fr):
    return [int(fr.numerator), int(fr.denominator)]


def _cls(o):
    return str(o.get_class().get_name())


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(str(p.get_name()).split(".", 1)[0] for p in lib.get_dirty_content_packages()),
            "maps": sorted(str(p.get_name()).split(".", 1)[0] for p in lib.get_dirty_map_packages())}


def _sequencer_open():
    cur = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
    return _pkg(cur) if cur is not None else None


def _load(path, what):
    o = unreal.load_asset(path)
    if o is None:
        raise RuntimeError("LOAD_FAIL|%s|%s" % (what, path))
    return o


def _chan_base(c):
    name = str(c.channel_name) if hasattr(c, "channel_name") else str(c.get_name())
    for base in ("Location.X", "Location.Y", "Location.Z", "Rotation.X", "Rotation.Y", "Rotation.Z",
                 "Scale.X", "Scale.Y", "Scale.Z"):
        if name == base or name.startswith(base + "_"):
            return base
    return name


def _chan_map(section):
    out = {}
    for c in section.get_all_channels():
        b = _chan_base(c)
        if b in out:
            raise RuntimeError("DUPLICATE_CHANNEL|%s" % b)
        out[b] = c
    return out


def _tick_rows(ch):
    rows = []
    for k in ch.get_keys():
        ft = k.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION)
        if abs(float(ft.sub_frame)) > 1e-6:
            raise RuntimeError("SUBTICK_KEY|%s+%s" % (ft.frame_number.value, ft.sub_frame))
        rows.append([int(ft.frame_number.value), float(k.get_value()), _enum(k.get_interpolation_mode())])
    return sorted(rows, key=lambda r: r[0])


def _src_rows(ch):
    """Her keys with tangents (for the source hash only; evaluation is UE's)."""
    rows = []
    for k in ch.get_keys():
        ft = k.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION)
        if abs(float(ft.sub_frame)) > 1e-6:
            raise RuntimeError("SUBTICK_KEY|%s+%s" % (ft.frame_number.value, ft.sub_frame))
        rows.append([int(ft.frame_number.value), float(k.get_value()), _enum(k.get_interpolation_mode()),
                     _enum(k.get_tangent_mode()), float(k.get_arrive_tangent()), float(k.get_leave_tangent()),
                     _enum(k.get_tangent_weight_mode())])
    return sorted(rows, key=lambda r: r[0])


def _sample(C, seq, ch, grid):
    """UE-evaluated values of one channel at grid['ticks'] (count asserted)."""
    rng = seq.make_range(int(grid["start_frame"]), int(grid["duration"]))           # DISPLAY rate [decl :137-145]
    vals = [float(v) for v in ch.evaluate_keys(rng, unreal.FrameRate(numerator=int(grid["rate"][0]),
                                                                     denominator=int(grid["rate"][1])))]
    if len(vals) != grid["expected_count"]:
        raise C.PlanError("SAMPLE_COUNT|got %d want %d (range must be make_range in display frames)"
                          % (len(vals), grid["expected_count"]))
    return vals


def _src_channel(ch):
    return {"keys": _src_rows(ch), "default": float(ch.get_default()) if ch.has_default() else None,
            "pre": _enum(ch.get_pre_infinity_extrapolation()), "post": _enum(ch.get_post_infinity_extrapolation())}


def _blend(section):
    try:
        v = section.get_blend_type()
        if hasattr(v, "get_editor_property"):
            v = v.get_editor_property("blend_type")
        return _enum(v)
    except Exception as exc:  # noqa: BLE001  -- unclassifiable = refuse, never guess
        return "ERROR:%s" % type(exc).__name__


def _completion(section):
    try:
        return _enum(section.get_completion_mode())
    except Exception as exc:  # noqa: BLE001
        return "UNREADABLE:%s" % type(exc).__name__


def _params_text(section):
    p = section.get_editor_property("parameters")
    return str(p.export_text())


def _editor_world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


# =================================================================================================== fingerprint
def _plain(v):
    if isinstance(v, bool):
        return bool(v)
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return str(v.get_path_name())
    except Exception:  # noqa: BLE001
        pass
    try:  # struct: export_text is value-only (str() embeds the wrapper address: 8 Oct false positive, s3waves_t5o)
        return "T:" + str(v.export_text())
    except Exception:  # noqa: BLE001
        import re
        return re.sub(r"0x[0-9A-Fa-f]+", "0x?", str(v))


def _all_bindings(seq):
    out, stack = {}, list(seq.get_bindings())
    while stack:
        b = stack.pop(0)
        g = _guid(b)
        if g in out:
            continue
        out[g] = b
        try:
            stack.extend(b.get_child_possessables())
        except Exception:  # noqa: BLE001
            pass
    return out


def _channel_fp(C, c):
    try:
        rows = sorted([[int(k.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number.value),
                        _plain(k.get_value())] for k in c.get_keys()], key=lambda r: r[0])
        fp = {"n": len(rows), "sha": C.value_sha(rows)}
    except Exception as exc:  # noqa: BLE001  -- event/object channels: count only, named as such
        try:
            fp = {"n": len(list(c.get_keys())), "sha": "UNREADABLE:%s" % type(exc).__name__}
        except Exception:  # noqa: BLE001
            fp = {"n": -1, "sha": "UNREADABLE"}
    try:
        sig = sorted([[int(k.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number.value),
                       _enum(k.get_interpolation_mode()), _enum(k.get_tangent_mode())] for k in c.get_keys()])
        fp["interp"] = hashlib.sha256(json.dumps(sig).encode()).hexdigest() if sig else None
    except Exception:  # noqa: BLE001
        fp["interp"] = "n/a"
    try:
        fp["default"] = _plain(c.get_default()) if c.has_default() else None
    except Exception:  # noqa: BLE001
        fp["default"] = "n/a"
    return fp


def _section_fp(s):
    row = {"struct": "section", "class": _cls(s)}
    for k, fn in (("start", "get_start_frame"), ("end", "get_end_frame")):
        try:
            row[k] = int(getattr(s, fn)())
        except Exception:  # noqa: BLE001
            row[k] = None
    for k, fn in (("has_start", "has_start_frame"), ("has_end", "has_end_frame"), ("active", "is_active")):
        try:
            row[k] = bool(getattr(s, fn)())
        except Exception:  # noqa: BLE001
            row[k] = None
    row["completion"] = _completion(s)
    try:
        nested = s.get_sequence()
        row["sequence"] = _pkg(nested)
        row["params"] = _params_text(s)
    except Exception:  # noqa: BLE001
        pass
    return row


def _track_fp(C, fp, prefix, ti, t):
    tp = C.track_path(prefix, ti, _cls(t), str(t.get_display_name()))
    try:
        prop = str(t.get_property_name())
    except Exception:  # noqa: BLE001
        prop = None
    secs = list(t.get_sections())
    fp[tp] = {"struct": "track", "property": prop, "sections": len(secs)}
    for si, s in enumerate(secs):
        chans = list(s.get_all_channels())
        fp["%s/S%d" % (tp, si)] = dict(_section_fp(s), channels=len(chans))
        for ci, c in enumerate(chans):
            fp["%s/S%d/C%d:%s" % (tp, si, ci, _chan_base(c))] = _channel_fp(C, c)


def _fingerprint(C, seq):
    fp = {}
    fp["SEQ"] = {"struct": "sequence", "fps": _rate(seq.get_display_rate()), "tick": _rate(seq.get_tick_resolution()),
                 "playback": [int(seq.get_playback_start()), int(seq.get_playback_end())]}
    for ti, t in enumerate(seq.get_tracks()):
        _track_fp(C, fp, "M", ti, t)
    for g, b in sorted(_all_bindings(seq).items()):
        parent = None
        try:
            p = b.get_parent()
            parent = _guid(p) if p is not None and p.is_valid() else None
        except Exception:  # noqa: BLE001
            pass
        tracks = list(b.get_tracks())
        fp["B:%s" % g] = {"struct": "binding", "name": str(b.get_display_name()), "parent": parent,
                          "tracks": len(tracks)}
        for ti, t in enumerate(tracks):
            _track_fp(C, fp, "B:%s" % g, ti, t)
    return fp


def _foreign_bindings(seq):
    rows = []
    for b in _all_bindings(seq).values():
        rows.append({"name": str(b.get_display_name()),
                     "vis_props": [str(t.get_property_name()) for t in b.get_tracks()
                                   if _cls(t) == "MovieSceneVisibilityTrack"]})
    return rows


# =================================================================================================== live reads
def _her_actors(C, world, wings):
    """{label: actor} for her 15 wings in the streamed level, matched by OBJECT NAME, cross-checked by label + mesh."""
    by_name, problems = {}, []
    for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.StaticMeshActor):
        if str(a.get_outermost().get_name()) == C.HER_LEVEL:
            by_name.setdefault(str(a.get_name()), []).append(a)
    out = {}
    for w in wings:
        hits = by_name.get(w["actor_name"], [])
        if len(hits) != 1:
            problems.append("HER_ACTOR_COUNT|%s|%s|%d (her level streamed and loaded?)" % (w["label"], w["actor_name"],
                                                                                          len(hits)))
            continue
        a = hits[0]
        mesh = _pkg(a.get_editor_property("static_mesh_component").get_editor_property("static_mesh"))
        if str(a.get_actor_label()) != w["label"] or mesh != str(w["mesh"]).split(".")[0]:
            problems.append("HER_ACTOR_MISMATCH|%s|label=%s|mesh=%s" % (w["actor_name"], a.get_actor_label(), mesh))
            continue
        out[w["label"]] = a
    return out, problems


def _pose(a):
    l, r = a.get_actor_location(), a.get_actor_rotation()
    return [float(l.x), float(l.y), float(l.z), float(r.roll), float(r.pitch), float(r.yaw)]


def _hookin_section(C, scene, copy_path):
    hits = [(t, s) for t in scene.get_tracks() if _cls(t) == "MovieSceneSubTrack"
            and str(t.get_display_name()) == C.HOOKIN_TRACK for s in t.get_sections()]
    if len(hits) != 1:
        raise C.PlanError("HOOKIN_SECTION_COUNT|%d" % len(hits))
    t, s = hits[0]
    if _pkg(s.get_sequence()) != copy_path:
        raise C.PlanError("HOOKIN_SECTION_SEQUENCE|%s want %s" % (_pkg(s.get_sequence()), copy_path))
    return t, s


def _level_vis_range(C, scene):
    """The hookin's Level Visibility section that shows her level (track 'Klara Levels (hookin)', level names incl.
    Japanese_Alley) -> [start, end] display frames, or None [prec klara_hookin.py _live_seq_state]."""
    rows = []
    for t in scene.get_tracks():
        if _cls(t) == "MovieSceneLevelVisibilityTrack" and str(t.get_display_name()) == C.LEVELS_TRACK:
            for s in t.get_sections():
                if C.HER_LEVEL_SHORT in [str(n) for n in s.get_level_names()]:
                    rows.append([int(s.get_start_frame()), int(s.get_end_frame())])
    if len(rows) != 1:
        raise C.PlanError("LEVEL_VIS_SECTION_COUNT|%d" % len(rows))
    return rows[0]


def _mapped(sec, scene):
    child = sec.get_sequence()
    f = unreal.MovieSceneSectionExtensions.get_parent_sequence_frame
    return [int(f(sec, int(child.get_playback_start()), scene)), int(f(sec, int(child.get_playback_end()), scene))]


def _copy_sources(C, copy, wings, actors):
    """{label: {"guid", "chans": {x..yaw}, "names"}} from the hookin copy (her keys, re-keyed to world)."""
    out, problems = {}, []
    bindings = list(copy.get_bindings())
    for w in wings:
        a = actors.get(w["label"])
        names = {w["label"], w["actor_name"]}
        hits = [b for b in bindings if str(b.get_display_name()) in names]
        if len(hits) != 1:
            problems.append("COPY_BINDING_COUNT|%s|%d" % (w["label"], len(hits)))
            continue
        b = hits[0]
        tr = [t for t in b.get_tracks() if _cls(t) == "MovieScene3DTransformTrack"]
        secs = [s for t in tr for s in t.get_sections()]
        if len(tr) != 1 or len(secs) != 1:
            problems.append("COPY_TRANSFORM_SHAPE|%s|tracks=%d|sections=%d" % (w["label"], len(tr), len(secs)))
            continue
        blend = _blend(secs[0])
        if blend != "ABSOLUTE":
            problems.append("COPY_BLEND|%s|%s" % (w["label"], blend))
            continue
        cm = _chan_map(secs[0])
        chans, names_seen, handles = {}, {}, {}
        for n in C.CHANNELS:
            ue = C.UE_CHANNEL[n]
            if ue not in cm:
                problems.append("COPY_CHANNEL_MISSING|%s|%s" % (w["label"], ue))
                break
            chans[n] = _src_channel(cm[ue])
            handles[n] = cm[ue]
            names_seen[n] = str(cm[ue].channel_name) if hasattr(cm[ue], "channel_name") else str(cm[ue].get_name())
        else:
            out[w["label"]] = {"guid": _guid(b), "binding_name": str(b.get_display_name()), "chans": chans,
                               "handles": handles, "channel_names": names_seen,
                               "her_actor": a.get_path_name() if a else None}
    return out, problems


def _mesh_info(path):
    m = unreal.load_asset(path)
    if m is None or _cls(m) != "StaticMesh":
        return None
    box = m.get_bounding_box()
    slots = [str(s.get_editor_property("material_slot_name")) for s in m.get_editor_property("static_materials")]
    return {"path": path, "box": [[box.min.x, box.min.y, box.min.z], [box.max.x, box.max.y, box.max.z]],
            "slots": slots}


def _variant_materials(info, vmap):
    """-> (list per slot: material path | None, problems)."""
    problems = [("VARIANT_SLOT_UNKNOWN|%s not in %s" % (k, info["slots"])) for k in vmap if k not in info["slots"]]
    mats = []
    for slot in info["slots"]:
        p = vmap.get(slot)
        if p is None:
            mats.append(None)
            continue
        m = unreal.load_asset(p)
        if m is None or not isinstance(m, unreal.MaterialInterface):
            problems.append("VARIANT_MATERIAL_LOAD|%s|%s" % (slot, p))
            mats.append(None)
        else:
            mats.append(_pkg(m))
    return mats, problems


def _api_table():
    rows = []

    def probe(api, tier, fn):
        try:
            res = fn()
            rows.append({"api": api, "tier": tier, "ok": bool(res), "result": repr(res)[:160]})
        except Exception as exc:  # noqa: BLE001
            rows.append({"api": api, "tier": tier, "ok": False, "result": "%s: %s" % (type(exc).__name__, exc)})

    u = unreal
    probe("LevelSequence.add_spawnable_from_class", "prec curtain_sleight.py:1897 (applied I1/I2 5 Oct)",
          lambda: hasattr(u.LevelSequence, "add_spawnable_from_class"))
    probe("MovieSceneBindingProxy.get_object_template", "prec curtain_sleight.py:1900",
          lambda: hasattr(u.MovieSceneBindingProxy, "get_object_template"))
    probe("LevelSequence.add_possessable", "prec klara_hookin.py:1860", lambda: hasattr(u.LevelSequence, "add_possessable"))
    probe("LevelSequence.locate_bound_objects (VERIFY resolution)", "inf (s3waves_t5o uses it; never get_bound_objects)",
          lambda: hasattr(u.LevelSequence, "locate_bound_objects"))
    probe("MovieSceneVisibilityTrack + set_property_name_and_path", "prec s2_vis_fix.py:68",
          lambda: hasattr(u.MovieSceneVisibilityTrack, "set_property_name_and_path"))
    probe("LevelSequence set_tick_resolution / set_display_rate", "prec p06_bee_glints.py:850-851 (applied 7 Oct)",
          lambda: [hasattr(u.LevelSequence, n) for n in ("set_tick_resolution", "set_display_rate")])
    probe("MovieSceneTimeUnit.TICK_RESOLUTION", "inf (enum name)", lambda: repr(u.MovieSceneTimeUnit.TICK_RESOLUTION))
    probe("MovieSceneSection.get_completion_mode", "inf", lambda: hasattr(u.MovieSceneSection, "get_completion_mode"))
    probe("MovieSceneSectionExtensions.get_parent_sequence_frame", "prec klara_hookin.py:1903",
          lambda: hasattr(u.MovieSceneSectionExtensions, "get_parent_sequence_frame"))
    probe("ComponentMobility.MOVABLE", "prec curtain_sleight.py:2029", lambda: repr(u.ComponentMobility.MOVABLE))
    probe("MovieSceneScriptingDoubleChannel.evaluate_keys (the sampled source)",
          "decl MovieSceneScriptingDouble.h:296; MovieSceneScriptingChannel.h:218-245",
          lambda: hasattr(u.MovieSceneScriptingDoubleChannel, "evaluate_keys"))
    probe("LevelSequence.make_range (DISPLAY-rate range)", "decl MovieSceneSequenceExtensions.h:145",
          lambda: hasattr(u.LevelSequence, "make_range"))
    probe("FrameRate(numerator=150, denominator=1)", "inf (struct ctor)",
          lambda: repr(u.FrameRate(numerator=150, denominator=1)))
    probe("MovieSceneKeyInterpolation.CONSTANT (the wide-shot hold key)", "inf (enum name)",
          lambda: repr(u.MovieSceneKeyInterpolation.CONSTANT))
    probe("MovieSceneLevelVisibilitySection.get_level_names", "prec klara_hookin.py:1693",
          lambda: hasattr(u.MovieSceneLevelVisibilitySection, "get_level_names"))
    return rows


# =================================================================================================== plan
def _plan(C, args, world, run):
    """Everything DRY reports and APPLY/RESYNC write.  -> plan dict with 'refusals', plus live handles (not in JSON)."""
    refusals, warnings = [], []
    wings = C.her_wings_from_census(_read(CENSUS_JSON))
    kit = dict(C.KIT, **(args.get("kit") or {}))
    kit_files = {k: _read(_abs(v)) for k, v in kit.items()}
    for k, v in kit_files.items():
        if v is None:
            refusals.append("KIT_FILE_MISSING|%s|%s" % (k, kit[k]))
    types, tp = C.resolve_types(args, kit_files["manifest_path"], kit_files["pivot_path"],
                                kit_files["rzimport_plan_path"])
    refusals += ["TYPES|" + x for x in tp] + C.check_her_actor_lists(types, wings)
    variant = str(args.get("variant") or C.DEFAULTS["variant"]).upper()
    scene = _load(C.SCENE_SEQ, "scene")
    copy_path = args.get("hookin_copy") or C.HOOKIN_COPY
    copy = _load(copy_path, "hookin copy")
    _t, hsec = _hookin_section(C, scene, copy_path)
    hookin_range = [int(hsec.get_start_frame()), int(hsec.get_end_frame())]
    want_sec = list(args.get("expected_section") or C.EXPECTED_SECTION)
    if hookin_range != want_sec:
        refusals.append("HOOKIN_SECTION_RANGE|live %s expected %s" % (hookin_range, want_sec))
    if not hsec.is_active():
        refusals.append("HOOKIN_SECTION_INACTIVE")
    hookin_mapped = _mapped(hsec, scene)
    if hookin_mapped[0] != hookin_range[0]:
        refusals.append("HOOKIN_OFFSET_NONZERO|child start maps to %s, section starts %s" % (hookin_mapped[0],
                                                                                           hookin_range[0]))
    copy_rates = {"fps": _rate(copy.get_display_rate()), "tick": _rate(copy.get_tick_resolution()),
                  "playback": [int(copy.get_playback_start()), int(copy.get_playback_end())]}
    coverage_mode = str(C.opt(args, "coverage"))
    lv = None
    try:
        lv = _level_vis_range(C, scene)
    except C.PlanError as exc:
        if coverage_mode == "scene":
            refusals.append(str(exc))
    try:
        cov = C.coverage_plan(coverage_mode, hookin_range, lv, _rate(scene.get_display_rate()), copy_rates["tick"])
    except C.PlanError as exc:
        refusals.append("COVERAGE|%s" % exc)
        cov = {"range": hookin_range, "pre_frames": 0, "pre_ticks": 0, "pre_seconds": 0.0}
    if args.get("expected_coverage") and cov["range"] != list(args["expected_coverage"]):
        refusals.append("COVERAGE_RANGE|live %s expected %s" % (cov["range"], args["expected_coverage"]))
    tpf = copy_rates["tick"][0] * copy_rates["fps"][1] / float(copy_rates["tick"][1] * copy_rates["fps"][0])
    if cov["pre_ticks"] and copy_rates["playback"][0] != 0:
        refusals.append("COPY_PLAYBACK_START_NOT_0|%s" % copy_rates["playback"])
    end_ticks = cov["pre_ticks"] + copy_rates["playback"][1] * tpf
    overlay_playback = [0 if cov["pre_ticks"] else copy_rates["playback"][0], int(-(-end_ticks // tpf))]
    actors, ap = _her_actors(C, world, wings)
    refusals += ap
    sources, sp = _copy_sources(C, copy, wings, actors)
    refusals += sp
    meshes = {}
    for t, row in types.items():
        row["variant_mats"] = {}
        if not row.get("mesh"):
            continue
        info = _mesh_info(str(row["mesh"]).split(".")[0])
        if info is None:
            refusals.append("OUR_MESH_NOT_LOADED|%s|%s" % (t, row["mesh"]))
            continue
        meshes[t] = info
        for vn in C.VARIANTS:
            mats, mp = _variant_materials(info, (row.get("variants") or {}).get(vn) or {})
            row["variant_mats"][vn] = mats
            msgs = ["%s.%s|%s" % (t, vn, x) for x in mp]
            if vn == variant:
                refusals += msgs
            else:
                warnings += ["NOT_APPLIED_VARIANT_NOT_READY|" + x for x in msgs]
    plan_wings = []
    tol_cm, tol_deg = float(C.opt(args, "midpoint_tol_cm")), float(C.opt(args, "midpoint_tol_deg"))
    pre_arg = str(C.opt(args, "pre_section_pose"))
    for w in wings:
        row = types.get(w["type"])
        src = sources.get(w["label"])
        a = actors.get(w["label"])
        pw = {"label": w["label"], "type": w["type"], "her_actor_path": a.get_path_name() if a else None}
        if src is None or row is None or row.get("pivot_offset_cm") is None or a is None:
            pw["skipped"] = "inputs unresolved"
            plan_wings.append(pw)
            continue
        pw["copy_binding"] = {"guid": src["guid"], "name": src["binding_name"], "channels": src["channel_names"]}
        pw["source_hashes"] = C.source_hashes(src["chans"])
        pw["source_key_counts"] = {n: len(src["chans"][n]["keys"]) for n in C.CHANNELS}
        kp = {"keys": [], "problems": []}
        try:
            sp_ = C.source_problems(src["chans"], linear_only=False)
            if sp_:
                raise C.PlanError(" ".join(sp_))
            key_ticks = [k[0] for n in C.CHANNELS for k in src["chans"][n]["keys"]]
            grid = C.sampling_grid(key_ticks, copy_rates["tick"], copy_rates["fps"], _rate(scene.get_display_rate()),
                                   cov["pre_ticks"])
            samples = {n: _sample(C, copy, src["handles"][n], grid) for n in C.CHANNELS}
            align = C.key_alignment(src["chans"], grid["ticks"], samples)
            kp = C.plan_wing_keys_sampled(samples, grid["ticks"], row, C.opt(args, "copy_channels"), tol_cm, tol_deg,
                                          float(C.opt(args, "fit_tol_cm")), float(C.opt(args, "fit_tol_deg")))
            kp["problems"] = align["problems"] + kp["problems"]
            pw["sampling"] = {k: grid[k] for k in ("start_frame", "duration", "rate", "interval", "expected_count")}
            pw["sampling"].update(alignment=align, samples=kp["samples"], keys=kp["n"], max_dev_cm=kp["max_dev_cm"],
                                  max_dev_deg=kp["max_dev_deg"])
            her_first = [samples[n][0] for n in C.CHANNELS]
            her_rest = [samples[n][-1] for n in C.CHANNELS]
        except C.PlanError as exc:
            kp = {"keys": [], "problems": [str(exc)]}
            her_first = [C.eval_channel(src["chans"][n], -10 ** 12) for n in C.CHANNELS]   # first/last key values
            her_rest = [C.eval_channel(src["chans"][n], 10 ** 12) for n in C.CHANNELS]
        refusals += ["%s|%s" % (w["label"], x) for x in kp["problems"]]
        live = _pose(a)
        cls = C.classify_pre_pose(live, her_first, her_rest, float(C.opt(args, "rest_vs_actor_tol_cm")))
        pw.update(her_live_pose=live, her_first_from_keys=her_first, her_rest_from_keys=her_rest,
                  pre_pose_measured=cls,
                  rest_vs_actor_cm=round(sum((live[i] - her_rest[i]) ** 2 for i in range(3)) ** 0.5, 3))
        pre = cls if pre_arg == "auto" else pre_arg
        if cov["pre_ticks"]:
            if pre == "unclear":
                refusals.append("PRE_POSE_UNCLEAR|%s|her live pose is neither her rest nor her first key pose "
                                "(Sequencer left an evaluated pose? set args.pre_section_pose rest|first)" % w["label"])
            elif pre_arg != "auto" and pre_arg != cls:
                warnings.append("PRE_POSE_FORCED|%s|measured %s, args %s" % (w["label"], cls, pre_arg))
        pw["pre_pose"] = pre if cov["pre_ticks"] else None
        if kp["keys"]:
            hold = (kp["rest"] if pre == "rest" else kp["first"])[1:]
            keys, interps = C.with_hold(kp["keys"], cov["pre_ticks"], hold)
            pw.update(keys=keys, interps=interps, keys_sha=C.keys_sha(keys, interps), n=len(keys),
                      fall_first=kp["first"], rest=kp["rest"], max_dev_cm=kp["max_dev_cm"],
                      max_dev_deg=kp["max_dev_deg"])
        sc = a.get_actor_scale3d()
        pw["her_scale"] = [float(sc.x), float(sc.y), float(sc.z)]
        her_info = _mesh_info(str(w["mesh"]).split(".")[0])
        if her_info and w["type"] in meshes:
            al = C.box_alignment(meshes[w["type"]]["box"], her_info["box"], pw["her_scale"], row)
            pw["box_alignment"] = al
            if al["max_yz_cm"] > float(C.opt(args, "align_tol_cm")):
                msg = "BOX_ALIGN|%s|%.1f cm > %s (pivot offset / scale / handedness?)" % (
                    w["label"], al["max_yz_cm"], C.opt(args, "align_tol_cm"))
                (refusals if C.opt(args, "align_refuse") else warnings).append(msg)
        plan_wings.append(pw)
    fp = _fingerprint(C, scene)
    foreign, fpp = C.expected_foreign_report(_foreign_bindings(scene))
    refusals += fpp
    if C.our_track_prefix(fp):
        refusals.append("OVERLAY_TRACK_ALREADY_IN_SCENE")
    ov = str(args["overlay_asset"])
    if unreal.EditorAssetLibrary.does_asset_exist(ov):
        refusals.append("OVERLAY_ASSET_EXISTS|%s (create-only: pick a new path or delete it by hand)" % ov)
    plan = {"tool": C.TOOL, "run": run, "overlay_asset": ov, "variant": variant, "copy": copy_path,
            "copy_rates": copy_rates, "overlay_playback": overlay_playback,
            "scene_rates": {"fps": _rate(scene.get_display_rate()), "tick": _rate(scene.get_tick_resolution())},
            "coverage": dict(cov, mode=coverage_mode), "section": cov["range"], "hookin_section": hookin_range,
            "level_vis_range": lv, "section_params": _params_text(hsec), "section_completion": _completion(hsec),
            "hookin_mapped": hookin_mapped, "kit": kit,
            "types": {t: {k: v for k, v in r.items()} for t, r in types.items()},
            "meshes": meshes, "wings": plan_wings, "foreign": foreign, "fingerprint_rows": len(fp),
            "refusals": refusals, "warnings": warnings}
    plan["digest"] = C.plan_digest(plan)
    return plan, {"scene": scene, "copy": copy, "hsec": hsec, "actors": actors, "fp": fp}


# =================================================================================================== writers
def _stop(C, msg):
    raise RuntimeError(msg)


def _add_hide(C, ov, actor, rng):
    b = ov.add_possessable(actor)
    if b is None or not b.is_valid():
        raise RuntimeError("ADD_POSSESSABLE|%s" % actor.get_actor_label())
    b.set_display_name(C.HIDE_PREFIX + str(actor.get_actor_label()))
    t = b.add_track(unreal.MovieSceneVisibilityTrack)
    if t is None:
        raise RuntimeError("ADD_VIS_TRACK|%s" % actor.get_actor_label())
    t.set_property_name_and_path("bHidden", "bHidden")             # s2_vis_fix.py [prec]; True=visible semantics
    s = t.add_section()
    s.set_range(int(rng[0]), int(rng[1]))
    s.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
    ch = list(s.get_all_channels())
    if len(ch) != 1:
        raise RuntimeError("VIS_CHANNELS|%d" % len(ch))
    ch[0].set_default(False)                                         # VISIBLE=False -> hidden
    return b


def _set_template(C, b, mesh_path, mats, pose):
    tmpl = b.get_object_template()
    if tmpl is None or _cls(tmpl) != "StaticMeshActor":
        raise RuntimeError("TEMPLATE_CLASS|%s" % (_cls(tmpl) if tmpl else None))
    comp = tmpl.get_editor_property("static_mesh_component")
    comp.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
    comp.set_editor_property("static_mesh", _load(mesh_path, "our mesh"))
    comp.set_editor_property("override_materials", [None if p is None else _load(p, "material") for p in mats])
    comp.set_editor_property("relative_location", unreal.Vector(pose[0], pose[1], pose[2]))  # TEMPLATE: no world
    comp.set_editor_property("relative_rotation", unreal.Rotator(roll=pose[3], pitch=pose[4], yaw=pose[5]))
    comp.set_editor_property("relative_scale3d", unreal.Vector(1.0, 1.0, 1.0))
    return _template_state(b)


def _template_state(b):
    tmpl = b.get_object_template()
    comp = tmpl.get_editor_property("static_mesh_component")
    loc, rot = comp.get_editor_property("relative_location"), comp.get_editor_property("relative_rotation")
    sc = comp.get_editor_property("relative_scale3d")
    return {"class": _cls(tmpl), "mesh": _pkg(comp.get_editor_property("static_mesh")),
            "mats": [_pkg(m) if m is not None else None for m in comp.get_editor_property("override_materials")],
            "mobility": _enum(comp.get_editor_property("mobility")),
            "rel": [float(loc.x), float(loc.y), float(loc.z), float(rot.roll), float(rot.pitch), float(rot.yaw)],
            "scale": [float(sc.x), float(sc.y), float(sc.z)]}


def _spawn_track(b, rng):
    existing = [t for t in b.get_tracks() if _cls(t) == "MovieSceneSpawnTrack"]  # UE adds one itself [prec 1820-1825]
    st = existing[0] if existing else b.add_track(unreal.MovieSceneSpawnTrack)
    for extra in existing[1:]:
        b.remove_track(extra)
    for old in list(st.get_sections()):
        st.remove_section(old)
    ss = st.add_section()
    ss.set_range(int(rng[0]), int(rng[1]))
    ch = list(ss.get_all_channels())
    ch[0].set_default(True)
    return st


def _write_keys(C, section, keys, interps):
    cm = _chan_map(section)
    for n in ("Scale.X", "Scale.Y", "Scale.Z"):
        cm[n].set_default(1.0)                                        # unkeyed scale would evaluate 0 [prec 1790-1791]
    modes = {"RCIM_LINEAR": unreal.MovieSceneKeyInterpolation.LINEAR,
             "RCIM_CONSTANT": unreal.MovieSceneKeyInterpolation.CONSTANT}
    for i, n in enumerate(C.CHANNELS):
        ch = cm[C.UE_CHANNEL[n]]
        for k in list(ch.get_keys()):
            ch.remove_key(k)
        for row, im in zip(keys, interps):
            made = ch.add_key(unreal.FrameNumber(int(row[0])), float(row[1 + i]),
                              time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION, interpolation=modes[im])
            if made is None:
                raise RuntimeError("ADD_KEY_NONE|%s|%s" % (n, row[0]))
    return _read_our_keys(C, section)


def _read_our_keys(C, section):
    cm = _chan_map(section)
    chans = {n: {"keys": _tick_rows(cm[C.UE_CHANNEL[n]])} for n in C.CHANNELS}
    bad = sorted({k[2] for n in C.CHANNELS for k in chans[n]["keys"]} - {"RCIM_LINEAR", "RCIM_CONSTANT"})
    if bad:
        raise RuntimeError("OUR_INTERP|%s" % bad)
    return C.keys_from_channels(chans)


def _add_ours(C, ov, w, trow, mats, rng):
    b = ov.add_spawnable_from_class(unreal.StaticMeshActor)
    if b is None or not b.is_valid():
        raise RuntimeError("ADD_SPAWNABLE|%s" % w["label"])
    b.set_display_name(C.OURS_PREFIX + w["label"])
    tstate = _set_template(C, b, trow["mesh"], mats, w["keys"][0][1:])
    _spawn_track(b, rng)
    t = b.add_track(unreal.MovieScene3DTransformTrack)
    if t is None:
        raise RuntimeError("ADD_TRANSFORM|%s" % w["label"])
    t.set_display_name(C.OUR_TRANSFORM_TRACK)
    s = t.add_section()
    s.set_range(int(rng[0]), int(rng[1]))
    s.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
    got, gi = _write_keys(C, s, w["keys"], w["interps"])
    if gi != w["interps"] or not C.keys_equal(got, w["keys"]):
        raise RuntimeError("KEY_READBACK|%s" % w["label"])
    return b, tstate


def _overlay_state(C, ov):
    """Read-only summary of our overlay (used for read-back and VERIFY)."""
    hide, ours = {}, {}
    for b in ov.get_bindings():
        name = str(b.get_display_name())
        if name.startswith(C.HIDE_PREFIX):
            vis = [t for t in b.get_tracks() if _cls(t) == "MovieSceneVisibilityTrack"]
            secs = [s for t in vis for s in t.get_sections()]
            chans = [c for s in secs for c in s.get_all_channels()]
            hide[name[len(C.HIDE_PREFIX):]] = {
                "guid": _guid(b), "tracks": len(list(b.get_tracks())), "vis_tracks": len(vis),
                "property": [str(t.get_property_name()) for t in vis], "sections": len(secs),
                "range": [[int(s.get_start_frame()), int(s.get_end_frame())] for s in secs],
                "completion": [_completion(s) for s in secs],
                "default": [bool(c.get_default()) if c.has_default() else None for c in chans],
                "keys": sum(len(list(c.get_keys())) for c in chans)}
        elif name.startswith(C.OURS_PREFIX):
            tr = [t for t in b.get_tracks() if _cls(t) == "MovieScene3DTransformTrack"]
            secs = [s for t in tr for s in t.get_sections()]
            row = {"guid": _guid(b), "template": _template_state(b), "transform_tracks": len(tr),
                   "sections": len(secs)}
            if len(secs) == 1:
                row["keys_sha"] = C.keys_sha(*_read_our_keys(C, secs[0]))
                row["range"] = [int(secs[0].get_start_frame()), int(secs[0].get_end_frame())]
            ours[name[len(C.OURS_PREFIX):]] = row
    return {"hide": hide, "ours": ours, "bindings": len(list(ov.get_bindings())),
            "master_tracks": len(list(ov.get_tracks())),
            "rates": {"fps": _rate(ov.get_display_rate()), "tick": _rate(ov.get_tick_resolution()),
                      "playback": [int(ov.get_playback_start()), int(ov.get_playback_end())]}}


def _expect_overlay(C, plan, variant):
    rng = plan["overlay_playback"]
    want = {"hide": {}, "ours": {}}
    for w in plan["wings"]:
        want["hide"][w["label"]] = {"vis_tracks": 1, "property": ["bHidden"], "sections": 1, "range": [rng],
                                    "completion": ["RESTORE_STATE"], "default": [False], "keys": 0}
        t = plan["types"][w["type"]]
        want["ours"][w["label"]] = {"mesh": str(t["mesh"]).split(".")[0], "mats": t["variant_mats"][variant],
                                    "keys_sha": w["keys_sha"], "range": rng, "scale": [1.0, 1.0, 1.0],
                                    "mobility": "MOVABLE"}
    return want


def _rates_want(plan):
    return {"fps": plan["copy_rates"]["fps"], "tick": plan["copy_rates"]["tick"], "playback": plan["overlay_playback"]}


def _overlay_problems(C, state, want, rates_want):
    p = []
    if sorted(state["hide"]) != sorted(want["hide"]):
        p.append("HIDE_SET|%s" % sorted(set(state["hide"]) ^ set(want["hide"])))
    if sorted(state["ours"]) != sorted(want["ours"]):
        p.append("OURS_SET|%s" % sorted(set(state["ours"]) ^ set(want["ours"])))
    for k, w in want["hide"].items():
        s = state["hide"].get(k) or {}
        bad = {f: s.get(f) for f in w if s.get(f) != w[f]}
        if bad:
            p.append("HIDE|%s|%s" % (k, bad))
    for k, w in want["ours"].items():
        s = state["ours"].get(k) or {}
        tm = s.get("template") or {}
        got = {"mesh": tm.get("mesh"), "mats": tm.get("mats"), "keys_sha": s.get("keys_sha"), "range": s.get("range"),
               "scale": tm.get("scale"), "mobility": tm.get("mobility")}
        bad = {f: got[f] for f in w if got[f] != w[f]}
        if bad:
            p.append("OURS|%s|%s" % (k, bad))
    if state["rates"] != rates_want:
        p.append("OVERLAY_RATES|%s want %s" % (state["rates"], rates_want))
    if state["bindings"] != len(want["hide"]) + len(want["ours"]):
        p.append("OVERLAY_BINDING_COUNT|%d" % state["bindings"])
    return p


def _backup(C, run, tag, files):
    d = os.path.join(PROJECT, "Backups", "PreS2V3Overlay%s-%s" % (tag, run))
    os.makedirs(d, exist_ok=False)
    man = []
    for src in files:
        if not os.path.isfile(src):
            raise RuntimeError("BACKUP_SOURCE_MISSING|%s" % src)
        dst = os.path.join(d, os.path.basename(src))
        shutil.copy2(src, dst)
        if _sha(src) != _sha(dst):
            raise RuntimeError("BACKUP_HASH|%s" % src)
        man.append({"source": src, "backup": dst, "sha256": _sha(dst)})
    _write(os.path.join(d, "manifest.json"), {"run": run, "files": man}, exclusive=True)
    return d


def _save(C, paths, content_want):
    gate = C.census_gate(_census(), content_want, [])
    if gate:
        raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % " || ".join(gate))
    for p in paths:
        if not unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False):
            raise RuntimeError("SAVE_FAILED|%s" % p)
    after = _census()
    if after != {"content": [], "maps": []}:
        raise RuntimeError("DIRTY_AFTER_SAVE|%s" % json.dumps(after))


# =================================================================================================== modes
def run_dry(C, args, run, world, census0):
    plan, _h = _plan(C, args, world, run)
    plan["api_table"] = _api_table()
    plan["census"] = census0
    plan["design"] = {"ours": "SPAWNABLES in the overlay asset (no persistent-level save)",
                      "hide": "possessables on her actors, MovieSceneVisibilityTrack bHidden default False"}
    plan["apply_ready"] = not plan["refusals"]
    path = os.path.join(HERE, "s2v3_overlay_dry_%s.json" % run)
    _write(path, plan)
    if _census() != census0:
        raise RuntimeError("DRY_DIRTIED|%s" % json.dumps(_census()))
    return plan, path


def _mapping_ok(section, mapped, hookin_mapped):
    """Our child start maps to our section start; our child end maps to within one parent frame of where the hookin's
    child end maps (both are the section end, floored on the parent grid [meas hookin APPLY_SEQ 8 Oct: 3890 for 3891])."""
    return mapped[0] == section[0] and abs(mapped[1] - hookin_mapped[1]) <= 1 and mapped[1] <= section[1]


def run_apply(C, args, run, world):
    dry = _read(os.path.join(HERE, str(args.get("dry_report") or "")))
    if not dry:
        raise C.PlanError("NO_DRY_REPORT|args.dry_report")
    plan, h = _plan(C, args, world, run)
    if plan["refusals"]:
        raise C.PlanError("PLAN_REFUSED|" + " || ".join(plan["refusals"][:12]))
    if plan["digest"] != dry.get("digest"):
        raise C.PlanError("PLAN_CHANGED_SINCE_DRY|dry=%s|now=%s|rerun DRY" % (dry.get("digest"), plan["digest"]))
    scene, hsec, actors, fp_before = h["scene"], h["hsec"], h["actors"], h["fp"]
    variant = plan["variant"]
    originals = {"run": run, "scene": C.SCENE_SEQ, "fp_before": fp_before, "overlay_existed": False,
                 "scene_tracks": [[_cls(t), str(t.get_display_name())] for t in scene.get_tracks()],
                 "her_actors": {k: {"path": a.get_path_name(), "pose": _pose(a)} for k, a in actors.items()}}
    _write(ORIGINALS, originals, exclusive=True)                                   # ORIGINALS FIRST
    unreal.log("%s_ORIGINALS|run=%s|path=%s" % (C.MARK, run, ORIGINALS))
    rec = {"tool": C.TOOL, "run": run, "mode": "APPLY", "decided_by": args.get("decided_by"), "applied": False,
           "saved": [], "overlay_asset": plan["overlay_asset"], "variant": variant, "plan_digest": plan["digest"],
           "dry_report": args.get("dry_report"), "section": plan["section"], "section_params": plan["section_params"],
           "hookin_section": plan["hookin_section"], "level_vis_range": plan["level_vis_range"],
           "coverage": plan["coverage"], "overlay_playback": plan["overlay_playback"],
           "copy": plan["copy"], "copy_rates": plan["copy_rates"], "types": plan["types"], "kit": plan["kit"],
           "wings": [{k: w.get(k) for k in ("label", "type", "her_actor_path", "copy_binding", "source_hashes",
                                             "keys_sha", "pre_pose", "pre_pose_measured", "rest")}
                     for w in plan["wings"]],
           "originals": ORIGINALS, "written": datetime.datetime.now().isoformat(timespec="seconds")}
    _write(RECORD, rec, exclusive=True)
    rec["backup"] = _backup(C, run, "", [_content_file(C.SCENE_SEQ), ORIGINALS, RECORD])
    _write(RECORD, rec)
    folder, name = plan["overlay_asset"].rsplit("/", 1)
    ov = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, unreal.LevelSequence,
                                                                 unreal.LevelSequenceFactoryNew())
    if ov is None:
        raise RuntimeError("CREATE_FAILED|%s" % plan["overlay_asset"])
    rec["created"] = plan["overlay_asset"]
    _write(RECORD, rec)
    copy = h["copy"]
    ov.set_tick_resolution(copy.get_tick_resolution())
    ov.set_display_rate(copy.get_display_rate())
    pb = plan["overlay_playback"]
    ov.set_playback_start(int(pb[0]))
    ov.set_playback_end(int(pb[1]))
    for w in plan["wings"]:
        _add_hide(C, ov, actors[w["label"]], pb)
    for w in plan["wings"]:
        _add_ours(C, ov, w, plan["types"][w["type"]], plan["types"][w["type"]]["variant_mats"][variant], pb)
    st = _overlay_state(C, ov)
    p = _overlay_problems(C, st, _expect_overlay(C, plan, variant), _rates_want(plan))
    if p:
        raise RuntimeError("OVERLAY_READBACK|%s|NOTHING SAVED; Don't-Save restart" % " || ".join(p[:6]))
    track = scene.add_track(unreal.MovieSceneSubTrack)
    if track is None:
        raise RuntimeError("ADD_SUBTRACK")
    track.set_display_name(C.OVERLAY_TRACK)
    sec = track.add_section()
    sec.set_sequence(ov)
    sec.set_range(int(plan["section"][0]), int(plan["section"][1]))             # one call: [a, b)
    sec.set_editor_property("parameters", hsec.get_editor_property("parameters"))
    sec.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
    got = {"range": [int(sec.get_start_frame()), int(sec.get_end_frame())], "params": _params_text(sec),
           "mapped": _mapped(sec, scene), "sequence": _pkg(sec.get_sequence()), "active": bool(sec.is_active())}
    want = {"range": plan["section"], "params": plan["section_params"], "mapped": got["mapped"],
            "sequence": plan["overlay_asset"], "active": True}
    if got != want or not _mapping_ok(plan["section"], got["mapped"], plan["hookin_mapped"]):
        raise RuntimeError("SUBSECTION_READBACK|got %s want %s|NOTHING SAVED; Don't-Save restart" % (got, want))
    fp_after = _fingerprint(C, scene)
    ours = C.our_track_prefix(fp_after)
    if len(ours) != 1:
        raise RuntimeError("OUR_TRACK_COUNT|%s|NOTHING SAVED; Don't-Save restart" % ours)
    viol = C.fingerprint_diff(fp_before, fp_after, ours[0])
    if viol:
        raise RuntimeError("FINGERPRINT_VIOLATIONS|%d|%s|NOTHING SAVED; Don't-Save restart"
                           % (len(viol), json.dumps(viol[:3], default=str)[:600]))
    _save(C, [plan["overlay_asset"], C.SCENE_SEQ], [plan["overlay_asset"], C.SCENE_SEQ])  # overlay first
    rec["saved"] = [plan["overlay_asset"], C.SCENE_SEQ]
    _write(RECORD, rec)
    scene2, ov2 = _load(C.SCENE_SEQ, "scene"), _load(plan["overlay_asset"], "overlay")
    fp_post = _fingerprint(C, scene2)
    if C.fingerprint_diff(fp_after, fp_post):
        raise RuntimeError("POST_SAVE_FINGERPRINT_CHANGED")
    p = _overlay_problems(C, _overlay_state(C, ov2), _expect_overlay(C, plan, variant), _rates_want(plan))
    if p:
        raise RuntimeError("POST_SAVE_OVERLAY|%s" % " || ".join(p[:6]))
    rec["fp_after_file"] = os.path.join(HERE, "s2v3_overlay_fp_after_%s.json" % run)
    _write(rec["fp_after_file"], fp_post)
    rec["our_track_path"] = ours[0]
    rec["applied"] = True
    rec["variant_history"] = [[run, variant]]
    _write(RECORD, rec)
    return {"overlay": plan["overlay_asset"], "hide": 15, "ours": 15, "section": plan["section"],
            "coverage": plan["coverage"]["mode"], "pre_ticks": plan["coverage"]["pre_ticks"],
            "pre_pose": sorted({w.get("pre_pose") or "none" for w in plan["wings"]}),
            "variant": variant, "backup": rec["backup"], "record": RECORD}


def run_variant(C, args, run, world):
    rec = _read(RECORD)
    variant = str(args.get("variant") or "").upper()
    if variant not in C.VARIANTS:
        raise C.PlanError("VARIANT_ARG")
    want = {}
    for t, row in rec["types"].items():
        info = _mesh_info(str(row["mesh"]).split(".")[0])
        if info is None:
            raise C.PlanError("OUR_MESH_NOT_LOADED|%s" % row["mesh"])
        mats, mp = _variant_materials(info, (row.get("variants") or {}).get(variant) or {})
        if mp or not any(mats):
            raise C.PlanError("VARIANT_NOT_READY|%s.%s|%s|nothing changed" % (t, variant, mp or "no materials"))
        want[t] = mats
    ov = _load(rec["overlay_asset"], "overlay")
    backup = _backup(C, run, "-VARIANT", [_content_file(rec["overlay_asset"]), RECORD])
    changed = 0
    for b in ov.get_bindings():
        name = str(b.get_display_name())
        if not name.startswith(C.OURS_PREFIX):
            continue
        label = name[len(C.OURS_PREFIX):]
        w = next((x for x in rec["wings"] if x["label"] == label), None)
        if w is None:
            raise RuntimeError("UNKNOWN_OURS_BINDING|%s|NOTHING SAVED; Don't-Save restart" % name)
        mats = want[w["type"]]
        comp = b.get_object_template().get_editor_property("static_mesh_component")
        comp.set_editor_property("override_materials", [None if p is None else _load(p, "material") for p in mats])
        if _template_state(b)["mats"] != mats:
            raise RuntimeError("VARIANT_READBACK|%s|NOTHING SAVED; Don't-Save restart" % label)
        changed += 1
    if changed != 15:
        raise RuntimeError("VARIANT_COUNT|%d|NOTHING SAVED; Don't-Save restart" % changed)
    _save(C, [rec["overlay_asset"]], [rec["overlay_asset"]])
    st = _overlay_state(C, _load(rec["overlay_asset"], "overlay"))
    typ = {w["label"]: w["type"] for w in rec["wings"]}
    bad = [k for k, r in st["ours"].items() if r["template"]["mats"] != want[typ[k]]]
    if bad:
        raise RuntimeError("VARIANT_POST_SAVE|%s" % bad)
    for t, mats in want.items():
        rec["types"][t].setdefault("variant_mats", {})[variant] = mats
    rec["variant"] = variant
    rec.setdefault("variant_history", []).append([run, variant])
    _write(RECORD, rec)
    return {"variant": variant, "templates": changed, "backup": backup}


def run_resync(C, args, run, world):
    rec = _read(RECORD)
    a2 = dict(args, variant=rec["variant"], overlay_asset=rec["overlay_asset"])
    plan, h = _plan(C, a2, world, run)
    # the overlay exists (applied) and our track is in the scene: those two refusals are expected here
    ref = [r for r in plan["refusals"] if not r.startswith(("OVERLAY_ASSET_EXISTS", "OVERLAY_TRACK_ALREADY_IN_SCENE"))]
    if ref:
        raise C.PlanError("PLAN_REFUSED|" + " || ".join(ref[:12]))
    if (plan["section"], plan["hookin_section"], plan["section_params"], plan["overlay_playback"]) != (
            rec["section"], rec["hookin_section"], rec["section_params"], rec["overlay_playback"]):
        raise C.PlanError("SECTION_OR_COVERAGE_MOVED|ours %s hookin %s vs recorded %s / %s (REVERT + DRY + APPLY)"
                          % (plan["section"], plan["hookin_section"], rec["section"], rec["hookin_section"]))
    if plan["copy_rates"] != rec["copy_rates"]:
        raise C.PlanError("COPY_RATES_CHANGED|%s vs %s (REVERT + DRY + APPLY)" % (plan["copy_rates"], rec["copy_rates"]))
    for t, r in plan["types"].items():
        o = rec["types"].get(t) or {}
        if any(r.get(k) != o.get(k) for k in ("mesh", "pivot_offset_cm", "rot_offset_deg", "pivot_frame")):
            raise C.PlanError("TYPES_CHANGED|%s (mesh/pivot differ from the record: REVERT + DRY + APPLY)" % t)
    old = {w["label"]: w for w in rec["wings"]}
    stale = [w for w in plan["wings"] if w.get("source_hashes") != old[w["label"]].get("source_hashes")
             or w.get("keys_sha") != old[w["label"]].get("keys_sha")]
    if not stale:
        return None
    ov = _load(rec["overlay_asset"], "overlay")
    backup = _backup(C, run, "-RESYNC", [_content_file(rec["overlay_asset"]), RECORD])
    by = {str(b.get_display_name()): b for b in ov.get_bindings()}
    for w in stale:
        b = by.get(C.OURS_PREFIX + w["label"])
        tr = [t for t in b.get_tracks() if _cls(t) == "MovieScene3DTransformTrack"] if b else []
        secs = [s for t in tr for s in t.get_sections()]
        if len(secs) != 1:
            raise RuntimeError("RESYNC_SHAPE|%s|NOTHING SAVED; Don't-Save restart" % w["label"])
        got, gi = _write_keys(C, secs[0], w["keys"], w["interps"])
        if gi != w["interps"] or not C.keys_equal(got, w["keys"]):
            raise RuntimeError("RESYNC_READBACK|%s|NOTHING SAVED; Don't-Save restart" % w["label"])
        comp = b.get_object_template().get_editor_property("static_mesh_component")
        p0 = w["keys"][0][1:]
        comp.set_editor_property("relative_location", unreal.Vector(p0[0], p0[1], p0[2]))
        comp.set_editor_property("relative_rotation", unreal.Rotator(roll=p0[3], pitch=p0[4], yaw=p0[5]))
    _save(C, [rec["overlay_asset"]], [rec["overlay_asset"]])
    st = _overlay_state(C, _load(rec["overlay_asset"], "overlay"))
    for w in stale:
        if st["ours"][w["label"]].get("keys_sha") != w["keys_sha"]:
            raise RuntimeError("RESYNC_POST_SAVE|%s" % w["label"])
        o = old[w["label"]]
        o.update({k: w.get(k) for k in ("source_hashes", "keys_sha", "pre_pose", "pre_pose_measured", "rest",
                                         "copy_binding")})
    rec.setdefault("resyncs", []).append([run, [w["label"] for w in stale]])
    _write(RECORD, rec)
    return {"resynced": [w["label"] for w in stale], "backup": backup}


def run_verify(C, args, run, world, census0):
    rec = _read(RECORD)
    problems, warnings, out = [], [], {"run": run, "record_run": (rec or {}).get("run")}
    if not rec or not rec.get("applied"):
        problems.append("NO_APPLIED_RECORD")
    else:
        scene = _load(C.SCENE_SEQ, "scene")
        fp_now = _fingerprint(C, scene)
        fp_after = _read(rec.get("fp_after_file")) or {}
        ours = C.our_track_prefix(fp_now)
        if ours != [rec.get("our_track_path")]:
            problems.append("OUR_TRACK|now %s recorded %s" % (ours, rec.get("our_track_path")))
        for v in C.fingerprint_diff(fp_after, fp_now):
            mine = rec.get("our_track_path") and v["path"].startswith(rec["our_track_path"])
            (problems if mine else warnings).append("%s|%s" % ("OUR_ROWS_CHANGED" if mine else "SCENE_CHANGED_SINCE_APPLY",
                                                              v["path"]))
        try:
            _t, hsec = _hookin_section(C, scene, rec["copy"])
            hr = [int(hsec.get_start_frame()), int(hsec.get_end_frame())]
            lv = _level_vis_range(C, scene) if rec["coverage"]["mode"] == "scene" else None
            cov = C.coverage_plan(rec["coverage"]["mode"], hr, lv, _rate(scene.get_display_rate()),
                                  rec["copy_rates"]["tick"])
            mine = [s for t in scene.get_tracks() if _cls(t) == "MovieSceneSubTrack"
                    and str(t.get_display_name()) == C.OVERLAY_TRACK for s in t.get_sections()]
            if len(mine) != 1:
                problems.append("OUR_SECTION_COUNT|%d" % len(mine))
            else:
                s = mine[0]
                got = {"range": [int(s.get_start_frame()), int(s.get_end_frame())], "params": _params_text(s),
                       "sequence": _pkg(s.get_sequence()), "active": bool(s.is_active()), "mapped": _mapped(s, scene)}
                out["section"] = {"ours": got, "hookin": hr, "level_visible": lv, "coverage_now": cov}
                if got["range"] != cov["range"] or got["params"] != _params_text(hsec) or \
                        got["sequence"] != rec["overlay_asset"] or not got["active"] or \
                        not _mapping_ok(got["range"], got["mapped"], _mapped(hsec, scene)):
                    problems.append("SECTION_VS_LIVE_COVERAGE|ours %s want %s (hookin %s, level %s)"
                                    % (got, cov["range"], hr, lv))
                if cov["pre_ticks"] != rec["coverage"]["pre_ticks"]:
                    problems.append("PRE_ROLL_CHANGED|%s vs %s (REVERT + DRY + APPLY)" % (cov["pre_ticks"],
                                                                                         rec["coverage"]["pre_ticks"]))
        except C.PlanError as exc:
            problems.append("HOOKIN_OR_COVERAGE|%s" % exc)
        ov = _load(rec["overlay_asset"], "overlay")
        st = _overlay_state(C, ov)
        out["overlay"] = st
        plan_like = {"copy_rates": rec["copy_rates"], "types": rec["types"], "overlay_playback": rec["overlay_playback"],
                     "wings": [dict(w) for w in rec["wings"]]}
        problems += _overlay_problems(C, st, _expect_overlay(C, plan_like, rec["variant"]), _rates_want(plan_like))
        res = {}
        by = {str(b.get_display_name()): b for b in ov.get_bindings()}
        for w in rec["wings"]:
            b = by.get(C.HIDE_PREFIX + w["label"])
            try:
                objs = [o.get_path_name() for o in ov.locate_bound_objects(b, world)] if b else []
                res[w["label"]] = objs
                if objs != [w["her_actor_path"]]:
                    problems.append("HIDE_RESOLVES|%s|%s want %s" % (w["label"], objs, w["her_actor_path"]))
            except Exception as exc:  # noqa: BLE001  -- an unverifiable binding is a FAILURE, never a pass
                problems.append("HIDE_RESOLVE_UNVERIFIED|%s|%s" % (w["label"], type(exc).__name__))
        out["hide_resolution_editor_world"] = res
        try:
            copy = _load(rec["copy"], "copy")
            wings = [x for x in C.her_wings_from_census(_read(CENSUS_JSON))]
            actors, _ap = _her_actors(C, world, wings)
            srcs, sp = _copy_sources(C, copy, wings, actors)
            problems += ["SOURCE|%s" % x for x in sp]
            stale = [w["label"] for w in rec["wings"] if w["label"] in srcs and
                     C.source_hashes(srcs[w["label"]]["chans"]) != w["source_hashes"]]
            out["source_stale"] = stale
            if stale:
                problems.append("SOURCE_KEYS_CHANGED|%s (re-ingest? run RESYNC)" % stale)
        except Exception as exc:  # noqa: BLE001
            problems.append("SOURCE_READ|%s: %s" % (type(exc).__name__, exc))
    if _census() != census0:
        problems.append("VERIFY_DIRTIED|%s" % json.dumps(_census()))
    out.update(problems=problems, warnings=warnings, census=census0)
    path = os.path.join(HERE, "s2v3_overlay_verify_%s.json" % run)
    _write(path, out)
    return out, path


def run_revert(C, args, run, world):
    rec = _read(RECORD)
    scene = _load(C.SCENE_SEQ, "scene")
    fp_now = _fingerprint(C, scene)
    ours = C.our_track_prefix(fp_now)
    if ours != [rec.get("our_track_path")]:
        raise C.PlanError("STATE_DRIFTED|our track now %s recorded %s|nothing changed" % (ours, rec.get("our_track_path")))
    fp_rec = _read(rec["fp_after_file"]) or {}
    drift = [k for k in set(fp_now) | set(fp_rec) if k.startswith(ours[0]) and fp_now.get(k) != fp_rec.get(k)]
    if drift:
        raise C.PlanError("OUR_ROWS_DRIFTED|%s|nothing changed" % drift[:3])
    want = {k: v for k, v in fp_now.items() if not (k == ours[0] or k.startswith(ours[0] + "/"))}
    backup = _backup(C, run, "-REVERT", [_content_file(C.SCENE_SEQ), RECORD])
    tracks = [t for t in scene.get_tracks() if _cls(t) == "MovieSceneSubTrack"
              and str(t.get_display_name()) == C.OVERLAY_TRACK]
    if len(tracks) != 1:
        raise RuntimeError("REVERT_TRACK_COUNT|%d|NOTHING SAVED" % len(tracks))
    secs = list(tracks[0].get_sections())
    if [_pkg(s.get_sequence()) for s in secs] != [rec["overlay_asset"]]:
        raise RuntimeError("REVERT_TRACK_CONTENT|%s|NOTHING SAVED" % [_pkg(s.get_sequence()) for s in secs])
    scene.remove_track(tracks[0])                       # return value ignored (memory: return values lie); re-read
    fp_after = _fingerprint(C, scene)
    # Our track was appended LAST at APPLY, so removing it leaves every other master-track index unchanged.  If another
    # stream added a master track after ours, its index shifts by one: that shows as a diff and REVERT stops (fail-safe).
    if C.our_track_prefix(fp_after) or C.fingerprint_diff(want, fp_after):
        raise RuntimeError("REVERT_READBACK|NOTHING SAVED; Don't-Save restart (backup %s)" % backup)
    _save(C, [C.SCENE_SEQ], [C.SCENE_SEQ])
    if C.our_track_prefix(_fingerprint(C, _load(C.SCENE_SEQ, "scene"))):
        raise RuntimeError("REVERT_POST_SAVE")
    for p in (RECORD, ORIGINALS):
        if os.path.exists(p):
            os.replace(p, p + ".reverted-" + run)
    return {"removed_track": ours[0], "overlay_left_unreferenced": rec["overlay_asset"], "backup": backup}


# =================================================================================================== main
def main():
    C = _core()
    g = globals()
    args = g.get("S2V3OV_ARGS")
    if args is None:
        args = _read(os.path.join(HERE, ARGS_NAME)) or {}
    run = str(args.get("run") or "S2V3OV-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    mode = str(args.get("mode") or "?").upper()
    try:
        ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        in_pie = ed.get_game_world() is not None
        early = C.check_mode(args, in_pie, None if in_pie else _sequencer_open(), _read(RECORD))
        if early:
            raise C.PlanError("REFUSED|" + " || ".join(early))
        world = _editor_world()
        if world is None or str(world.get_outermost().get_name()) != C.WORLD:
            raise C.PlanError("WRONG_WORLD|%s" % (world.get_outermost().get_name() if world else None))
        census0 = _census()
        if mode not in C.READ_ONLY and census0 != {"content": [], "maps": []}:
            raise C.PlanError("DIRTY_BEFORE|%s" % json.dumps(census0))
        unreal.log("%s_START|run=%s|mode=%s|variant=%s|coverage=%s" % (C.MARK, run, mode, args.get("variant"),
                                                                      args.get("coverage")))
        if mode == "DRY":
            plan, path = run_dry(C, args, run, world, census0)
            unreal.log("%s_DRY_OK|run=%s|mutated=0|apply_ready=%s|refusals=%d|warnings=%d|digest=%s|out=%s" % (
                C.MARK, run, plan["apply_ready"], len(plan["refusals"]), len(plan["warnings"]), plan["digest"], path))
        elif mode == "APPLY":
            try:
                r = run_apply(C, args, run, world)
            except Exception:
                rec = _read(RECORD)
                if rec is not None and not rec.get("saved"):
                    for p in (RECORD, ORIGINALS):
                        if os.path.exists(p):
                            os.replace(p, p + ".failed-" + run)
                raise
            unreal.log("%s_APPLY_OK|run=%s|%s|VERIFY next (a later call)" % (C.MARK, run, json.dumps(r)))
        elif mode == "VARIANT":
            r = run_variant(C, args, run, world)
            unreal.log("%s_VARIANT_OK|run=%s|%s" % (C.MARK, run, json.dumps(r)))
        elif mode == "RESYNC":
            r = run_resync(C, args, run, world)
            if r is None:
                unreal.log("%s_RESYNC_NOOP|run=%s|source hashes unchanged; nothing saved" % (C.MARK, run))
            else:
                unreal.log("%s_RESYNC_OK|run=%s|%s" % (C.MARK, run, json.dumps(r)))
        elif mode == "VERIFY":
            out, path = run_verify(C, args, run, world, census0)
            if out["problems"]:
                unreal.log_error("%s_VERIFY_FAILED|run=%s|problems=%d|first=%s|out=%s" % (
                    C.MARK, run, len(out["problems"]), out["problems"][:2], path))
            else:
                unreal.log("%s_VERIFY_OK|run=%s|warnings=%d|out=%s" % (C.MARK, run, len(out["warnings"]), path))
        elif mode == "REVERT":
            r = run_revert(C, args, run, world)
            unreal.log("%s_REVERT_OK|run=%s|%s" % (C.MARK, run, json.dumps(r)))
    except Exception as exc:  # noqa: BLE001
        unreal.log_error("%s_FAILED|run=%s|mode=%s|%s: %s" % (C.MARK, run, mode, type(exc).__name__, exc))
        raise


if __name__ == "__main__" and unreal is not None:
    main()
