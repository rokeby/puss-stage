"""S3 waves t5o -- the editor tool (one mode per MCP call; args file s3waves_t5o_args.json, runner s3waves_t5o_run.py).

Gary 8 Oct (own answers): 5 cm pieces with outward V3 edges, more space between layers, edge = painted sea colour.
Conductor 8 Oct: in LS_DevScene_03 touch ONLY the 12 wave bindings' Location.X channels; fingerprint every other
binding/track/section/channel before and after and refuse on any difference; S3.Fire.* / S3.Crowd.Light /
S3.Opening.Ghost are expected and never fail the tool; DRY goes to the conductor before any APPLY.

  MI       create-only MI_WaveEdge_SeaPaint (parent M_Wing_CanvasEdge_Master_v3, never edited): sea-paint vectors +
           EdgeCentreXCm -12.5 / HalfThicknessCm 2.5; read back; save the MI only.          Marker S3T5O_MI_OK
  IMPORT   1..3 pieces: create-only import of SM_FlatV3_<piece>_t5o (LodGroup, materials/textures OFF, nanite off)
           with the S3WAVESV3 mesh gates (2 LODs, slot order, UV0 signs, front normal, LOD1 without Flap, bounds and
           triangles = the clean Blender re-import, no sockets, no strays); save the meshes only; GC.  Screen sizes are
           NOT set here (live 7 Oct: L6 read [0,0] in the import call).                    Marker S3T5O_IMPORT_OK
  MATS     1..4 imported pieces (a LATER call): slots 0/1 = the live Front/Flap MIs, 2 = Timber v1 master,
           3 = MI_WaveEdge_SeaPaint; LOD screen sizes [2.0, 0.3]; read back; save the meshes only.  S3T5O_MATS_OK
  VERIFY   read-only: every t5o mesh + the MI (+ the level/sequence state when an apply record exists:
           mesh, relative x, every Location.X key, and the whole-sequence fingerprint vs the record).  S3T5O_VERIFY_*
  DRY      read-only: live actors, bindings, every Location.X key, the APPLY plan, layout, sequence fingerprint
           summary (incl. the expected foreign tracks), census.  Self-contained JSON for the conductor.  S3T5O_DRY_OK
  APPLY    originals file FIRST (path logged), record, Backups/PreS3WavesT5O-<run> (umap + LS_DevScene_03 + files);
           per actor: static mesh -> t5o, relative x -> new x; per binding: every Location.X key += dx (set_value,
           read back); census must be EXACTLY {map, LS_DevScene_03} with the map dirty (else stop, nothing saved);
           fingerprint diff must show ONLY the 12 X channels, each exactly as planned; Sequencer CLOSED (guard);
           save map + sequence only; read back in the same call; VERIFY in a LATER call.        S3T5O_APPLY_OK
  REVERT   field-scoped inverse from the originals (mesh, relative x, X keys); same census/fingerprint/save rules.

Safety (memory notes): no unreal object at module level; runner purges the Saved module cache; no get_bound_objects
(locate_bound_objects only); never reload the open world; modify() before setters; every setter read back; markers only
after asserted read-back; ZZ_/TEMP guard in the save call (s3_waves_v3_ue._save); a failure saves nothing (Don't-Save
restart, never reload); never re-import in place (create-only); no build_skin anywhere.
"""
import datetime
import hashlib
import importlib.util
import json
import os
import re
import shutil

try:
    import unreal
except ModuleNotFoundError:   # offline harness
    unreal = None

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
S3W = os.path.join(PROJECT, "Saved", "CodexConductor", "S3Waves")
ARGS = os.path.join(HERE, "s3waves_t5o_args.json")
T5O_REPORT = os.path.join(PROJECT, "DerivedAssets", "FlatV3", "Scene3", "WavesV3_t5o", "build_report_t5o.json")
BUILD_PLAN = os.path.join(S3W, "build_plan_B.json")
V3_APPLY_RECORD = os.path.join(S3W, "s3_waves_v3_apply_record.json")
V3_MOTION_RECORD = os.path.join(S3W, "s3_waves_v3_motion_record.json")
RECORD = os.path.join(HERE, "s3waves_t5o_apply_record.json")
ORIGINALS = os.path.join(HERE, "s3waves_t5o_originals.json")
MI_RECORD = os.path.join(HERE, "s3waves_t5o_mi_record.json")
VERIFY_REPORT = os.path.join(HERE, "s3waves_t5o_verify.json")


def _load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _core():
    return _load_file("s3waves_t5o_core_live", os.path.join(HERE, "s3waves_t5o_core.py"))


def _v3core():
    return _load_file("s3wv3_core_for_t5o", os.path.join(S3W, "s3_waves_v3_core.py"))


def _w():
    """s3_waves_v3_ue.py as a library (its main() only runs as __main__; no unreal objects at its module level)."""
    return _load_file("s3wv3_ue_for_t5o", os.path.join(S3W, "s3_waves_v3_ue.py"))


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _rec_path(kind, suffix):
    return os.path.join(HERE, "s3waves_t5o_%s_%s.json" % (kind, suffix))


def _rows(T):
    W = _w()
    return T.piece_rows(W._read(BUILD_PLAN), W._read(T5O_REPORT), W._read(V3_APPLY_RECORD))


# =================================================================================================== sequence reads
def _all_bindings(seq):
    out, stack = {}, list(seq.get_bindings())
    while stack:
        b = stack.pop(0)
        g = str(unreal.GuidLibrary.conv_guid_to_string(b.get_id()))
        if g in out:
            continue
        out[g] = b
        try:
            stack.extend(b.get_child_possessables())
        except Exception:  # noqa: BLE001
            pass
    return out


def _chan_name(c):
    try:
        name = str(c.get_name())
    except Exception:  # noqa: BLE001
        name = str(c.get_editor_property("channel_name"))
    return re.sub(r"_\d+$", "", name)


def _plain(v):
    if isinstance(v, bool):
        return bool(v)
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return str(v.get_path_name())
    except Exception:  # noqa: BLE001
        pass
    try:  # structs: export_text is value-only (str() embeds the wrapper's memory address, 8 Oct false positive)
        return "T:" + str(v.export_text())
    except Exception:  # noqa: BLE001
        return re.sub(r"0x[0-9A-Fa-f]+", "0x?", str(v))


def _key_frame(k):
    return int(k.get_time(time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value)


def _keys(c):
    return sorted([[_key_frame(k), _plain(k.get_value())] for k in c.get_keys()], key=lambda r: r[0])


def _interp_sig(c):
    out = []
    for k in c.get_keys():
        try:
            out.append([_key_frame(k), str(k.get_interpolation_mode()), str(k.get_tangent_mode())])
        except Exception:  # noqa: BLE001
            return None
    return hashlib.sha256(json.dumps(sorted(out)).encode()).hexdigest()


def _channel_fp(T, c):
    try:
        rows = _keys(c)
        fp = {"n": len(rows), "sha": T.value_sha(rows)}
    except Exception as exc:  # noqa: BLE001  -- event/object channels may not expose values: count only
        try:
            fp = {"n": len(list(c.get_keys())), "sha": "UNREADABLE:%s" % type(exc).__name__}
        except Exception:  # noqa: BLE001
            fp = {"n": -1, "sha": "UNREADABLE"}
    fp["interp"] = _interp_sig(c) if fp["n"] > 0 else None
    try:
        fp["default"] = _plain(c.get_default()) if c.has_default() else None
    except Exception:  # noqa: BLE001
        fp["default"] = "n/a"
    return fp


def _section_fp(s):
    row = {"class": s.get_class().get_name()}
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
    try:
        nested = s.get_sequence()
        row["sequence"] = str(nested.get_path_name()) if nested else None
    except Exception:  # noqa: BLE001
        pass
    return row


def _track_fp(T, fp, prefix, ti, t):
    cls, name = t.get_class().get_name(), str(t.get_display_name())
    tp = T.track_path(prefix, ti, cls, name)
    try:
        prop = str(t.get_property_name())
    except Exception:  # noqa: BLE001
        prop = None
    secs = list(t.get_sections())
    fp[tp] = {"struct": "track", "property": prop, "sections": len(secs)}
    for si, s in enumerate(secs):
        sp = "%s/S%d" % (tp, si)
        chans = list(s.get_all_channels())
        fp[sp] = dict(_section_fp(s), struct="section", channels=len(chans))
        for ci, c in enumerate(chans):
            fp[T.channel_path(tp, si, ci, _chan_name(c))] = _channel_fp(T, c)
    return name


def _fingerprint(T, seq):
    """Every binding / track / section / channel of the sequence -> {path: row}.  SEMANTIC fingerprint (keys, values,
    interpolation, defaults, ranges), not file bytes: the package is re-serialised by the save [inf]."""
    fp, names = {}, []
    r = seq.get_display_rate()
    fp["SEQ"] = {"struct": "sequence", "fps": [int(r.numerator), int(r.denominator)],
                 "playback": [int(seq.get_playback_start()), int(seq.get_playback_end())]}
    for ti, t in enumerate(seq.get_tracks()):
        names.append(_track_fp(T, fp, "M", ti, t))
    for g, b in sorted(_all_bindings(seq).items()):
        parent = None
        try:
            p = b.get_parent()
            parent = str(unreal.GuidLibrary.conv_guid_to_string(p.get_id())) if p is not None and p.is_valid() else None
        except Exception:  # noqa: BLE001
            pass
        tracks = list(b.get_tracks())
        fp["B:%s" % g] = {"struct": "binding", "name": str(b.get_display_name()), "parent": parent,
                          "tracks": len(tracks)}
        for ti, t in enumerate(tracks):
            names.append(_track_fp(T, fp, "B:%s" % g, ti, t))
    return fp, names


def _motion_channel(T, seq, guid):
    """-> (binding, ti, section, ci, channel) for the wave binding's single motion track's Location.X channel."""
    b = _all_bindings(seq).get(guid)
    if b is None:
        raise T.PlanError("WAVE_BINDING_MISSING|%s" % guid)
    tracks = list(b.get_tracks())
    ours = [i for i, t in enumerate(tracks) if str(t.get_display_name()) == T.MOTION_TRACK]
    if len(ours) != 1 or tracks[ours[0]].get_class().get_name() != "MovieScene3DTransformTrack":
        raise T.PlanError("MOTION_TRACK|%s|%s" % (guid, [str(t.get_display_name()) for t in tracks]))
    ti = ours[0]
    secs = list(tracks[ti].get_sections())
    if len(secs) != 1:
        raise T.PlanError("MOTION_SECTIONS|%s|%d" % (guid, len(secs)))
    chans = list(secs[0].get_all_channels())
    xs = [i for i, c in enumerate(chans) if _chan_name(c) == T.LOC_X]
    if len(xs) != 1:
        raise T.PlanError("X_CHANNEL|%s|%s" % (guid, [_chan_name(c) for c in chans]))
    return b, ti, secs[0], xs[0], chans[xs[0]], [str(t.get_display_name()) for t in tracks]


def _live(T, W, world, seq, rows):
    idx = W._index(world)
    guids = {b["label"]: b["guid"] for b in W._read(V3_MOTION_RECORD)["bindings"]}
    out = {}
    for r in rows:
        acts = idx.get(r["label"], [])
        row = {"label_count": len(acts), "actor_path": None, "parent_label": None, "mesh": None, "relative": None,
               "binding_guid": guids.get(r["label"]), "motion_tracks": None, "x_keys": None, "x_channel_path": None}
        if len(acts) == 1:
            a = acts[0]
            p = a.get_attach_parent_actor()
            row.update({"actor_path": W._path(a), "parent_label": str(p.get_actor_label()) if p else None,
                        "mesh": W._pkg(W._smc(a).get_editor_property("static_mesh")), "relative": W._rel_tf(a)})
        if row["binding_guid"]:
            b, ti, _s, ci, ch, names = _motion_channel(T, seq, row["binding_guid"])
            located = W._located(seq, b, world)
            if located != [row["actor_path"]]:
                raise T.PlanError("BINDING_RESOLVES|%s|%s" % (r["label"], located))
            row.update({"motion_tracks": names, "x_keys": _keys(ch),
                        "x_channel_path": T.x_channel_path(row["binding_guid"], ti, 0, ci)})
        out[r["suffix"]] = row
    return out


def _set_x_keys(T, seq, guid, want, label):
    _b, _ti, _s, _ci, ch, _n = _motion_channel(T, seq, guid)
    keys = sorted(ch.get_keys(), key=_key_frame)
    if [_key_frame(k) for k in keys] != [int(w[0]) for w in want]:
        raise RuntimeError("X_KEY_FRAMES|%s" % label)
    for k, w in zip(keys, want):
        k.set_value(float(w[1]))                                   # klara_hookin.py:1762 [prec]; return not trusted
    got = _keys(ch)
    if [g[0] for g in got] != [int(w[0]) for w in want] or any(abs(g[1] - float(w[1])) > 1e-4 for g, w in zip(got, want)):
        raise RuntimeError("X_KEY_READBACK|%s" % label)
    return len(got)


# =================================================================================================== asset modes
def _verify_assets(T, W, C3, rows):
    pilot = W._pilot()
    sme = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    mel = unreal.MaterialEditingLibrary
    rep = {"pieces": {}, "mi": None}
    try:
        mi = unreal.load_asset(T.MI_EDGE)
        if mi is None:
            rep["mi"] = {"status": "MISSING"}
        else:
            plan = T.mi_plan(**_mi_args())
            st = _mi_state(T, mi, plan)
            rep["mi"] = dict(st, status="READY" if st["ok"] else "WRONG")
    except Exception as exc:  # noqa: BLE001
        rep["mi"] = {"status": "FAIL", "error": str(exc)[:300]}
    for r in rows:
        s = r["suffix"]
        try:
            mesh = unreal.load_asset(r["mesh"])
            if mesh is None:
                rep["pieces"][s] = {"status": "MISSING"}
                continue
            x = {"lods": int(mesh.get_num_lods()), "screen_sizes": [float(v) for v in sme.get_lod_screen_sizes(mesh)],
                 "nanite": bool(mesh.get_editor_property("nanite_settings").get_editor_property("enabled")),
                 "slots": [pilot.asset_package(m.get_editor_property("material_interface"))
                           for m in mesh.get_editor_property("static_materials")]}
            probs = []
            if x["lods"] != 2:
                probs.append("lods")
            if not C3.screen_sizes_ok(x["screen_sizes"]):
                probs.append("screen_sizes")
            if x["nanite"]:
                probs.append("nanite")
            if x["slots"] != T.slot_plan(r):
                probs.append("slots(MATS?)")
            x["problems"] = probs
            x["status"] = "READY" if not probs else "INCOMPLETE"
            rep["pieces"][s] = x
        except Exception as exc:  # noqa: BLE001  -- a verifier must be able to FAIL
            rep["pieces"][s] = {"status": "FAIL", "error": str(exc)[:300]}
    rep["ready"] = sorted(s for s, v in rep["pieces"].items() if v["status"] == "READY")
    rep["all_ready"] = len(rep["ready"]) == 12 and (rep["mi"] or {}).get("status") == "READY"
    return rep


def _mi_args():
    a = _read_args()
    return {"vectors": a.get("mi_vectors"), "scalars": a.get("mi_scalars")}


def _read_args():
    if not os.path.exists(ARGS):
        return {}
    with open(ARGS, encoding="utf-8") as h:
        return json.load(h)


def _mi_state(T, mi, plan):
    mel = unreal.MaterialEditingLibrary
    parent = mi.get_editor_property("parent")
    st = {"parent": str(parent.get_path_name()).split(".", 1)[0] if parent else None, "vectors": {}, "scalars": {}}
    for k in plan["vectors"]:
        c = mel.get_material_instance_vector_parameter_value(mi, k)
        st["vectors"][k] = [float(c.r), float(c.g), float(c.b)]
    for k in plan["scalars"]:
        st["scalars"][k] = float(mel.get_material_instance_scalar_parameter_value(mi, k))
    st["ok"] = (st["parent"] == plan["parent"] and
                all(T.near(st["vectors"][k], v, 1e-4) for k, v in plan["vectors"].items()) and
                all(abs(st["scalars"][k] - v) <= 1e-4 for k, v in plan["scalars"].items()))
    return st


def run_mi(T, W, run, world):
    plan = T.mi_plan(**_mi_args())
    if W._exists(plan["path"]):
        raise T.PlanError("MI_EXISTS|%s (create-only)" % plan["path"])
    master = W._load(plan["parent"])
    mel = unreal.MaterialEditingLibrary
    names_v = [str(n) for n in mel.get_vector_parameter_names(master)]
    names_s = [str(n) for n in mel.get_scalar_parameter_names(master)]
    miss = [k for k in plan["vectors"] if k not in names_v] + [k for k in plan["scalars"] if k not in names_s]
    if miss:
        raise T.PlanError("MASTER_PARAMS_MISSING|%s" % miss)
    master_pkg = os.path.join(PROJECT, "Content", plan["parent"][len("/Game/"):] + ".uasset")
    master_before = (os.path.getsize(master_pkg), os.path.getmtime(master_pkg))
    folder, name = plan["path"].rsplit("/", 1)
    mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, unreal.MaterialInstanceConstant,
                                                                 unreal.MaterialInstanceConstantFactoryNew())
    if not isinstance(mi, unreal.MaterialInstanceConstant):
        raise RuntimeError("MI_CREATE|%s" % plan["path"])
    mi.modify()
    mel.set_material_instance_parent(mi, master)
    for k, v in plan["vectors"].items():
        mel.set_material_instance_vector_parameter_value(mi, k, unreal.LinearColor(v[0], v[1], v[2], 1.0))
    for k, v in plan["scalars"].items():
        mel.set_material_instance_scalar_parameter_value(mi, k, float(v))
    mel.update_material_instance(mi)
    st = _mi_state(T, mi, plan)
    if not st["ok"]:
        raise RuntimeError("MI_READBACK|%s" % json.dumps(st))
    W._save(T, world, [plan["path"]], map_expected=False)        # census must be EXACTLY the MI (master untouched)
    if (os.path.getsize(master_pkg), os.path.getmtime(master_pkg)) != master_before:
        raise RuntimeError("MASTER_FILE_CHANGED|%s" % master_pkg)
    rec = {"run": run, "plan": plan, "readback": st, "saved": True, "master_file_untouched": True,
           "utc": datetime.datetime.utcnow().isoformat() + "Z"}
    W._write(MI_RECORD, rec)
    return rec


def run_import(T, W, C3, run, args, world):
    pilot = W._pilot()
    rows = T.pick(_rows(T), args["pieces"])
    for r in rows:                                     # every precondition for every piece before the first import
        if W._exists(r["mesh"]):
            raise T.PlanError("DESTINATION_EXISTS|%s (create-only; never re-import in place)" % r["mesh"])
        if not os.path.isfile(r["fbx"]) or _sha(r["fbx"]) != r["fbx_sha256"]:
            raise T.PlanError("FBX_MISSING_OR_CHANGED|%s" % r["fbx"])
        if os.path.exists(_rec_path("import", r["suffix"])):
            raise T.PlanError("IMPORT_RECORD_EXISTS|%s" % r["suffix"])
    folder = rows[0]["mesh"].rsplit("/", 1)[0]
    before = W._folder_assets(folder)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    gates = {}
    for r in rows:
        tools.import_asset_tasks([pilot.import_task(r["fbx"], r["mesh"], pilot.fbx_options(True))])
        mesh = W._load(r["mesh"], unreal.StaticMesh)
        mesh.modify()
        nan = mesh.get_editor_property("nanite_settings")
        nan.set_editor_property("enabled", False)
        mesh.set_editor_property("nanite_settings", nan)
        val = W._read(os.path.join(os.path.dirname(r["fbx"]), "SM_FlatV3_%s%s_validation.json" % (r["suffix"], T.T5O)))
        gates[r["suffix"]] = W._mesh_gate(pilot, C3, mesh, {"suffix": r["suffix"], "bounds_cm": r["bounds_cm"]}, val)
    new = sorted(W._folder_assets(folder) - before)
    if new != sorted(r["mesh"] for r in rows):
        raise RuntimeError("STRAY_OR_MISSING|new=%s (never saved: Don't-Save restart)" % new)
    W._save(T, world, [r["mesh"] for r in rows], map_expected=False)
    unreal.SystemLibrary.collect_garbage()
    for r in rows:
        W._write(_rec_path("import", r["suffix"]), {"run": run, "suffix": r["suffix"], "mesh": r["mesh"],
                                                    "fbx_sha256": r["fbx_sha256"], "mesh_gate": gates[r["suffix"]],
                                                    "saved": True, "utc": datetime.datetime.utcnow().isoformat() + "Z"})
    return {"imported": [r["suffix"] for r in rows], "lods": {s: g["num_lods"] for s, g in gates.items()}}


def run_mats(T, W, C3, run, args, world):
    pilot = W._pilot()
    rows = T.pick(_rows(T), args["pieces"])
    if not (W._read(MI_RECORD) or {}).get("saved"):
        raise T.PlanError("MI_NOT_BUILT (run MI first)")
    for r in rows:
        if not (W._read(_rec_path("import", r["suffix"])) or {}).get("saved"):
            raise T.PlanError("NOT_IMPORTED|%s" % r["suffix"])
        for p in T.slot_plan(r):
            if not W._exists(p):
                raise T.PlanError("SLOT_MATERIAL_MISSING|%s" % p)
    bdir = os.path.join(PROJECT, "Backups", "PreS3WavesT5OMats-%s" % run)
    os.makedirs(bdir)
    for r in rows:                                     # the only pre-existing assets this mode touches
        src = os.path.join(PROJECT, "Content", r["mesh"][len("/Game/"):] + ".uasset")
        shutil.copy2(src, os.path.join(bdir, os.path.basename(src)))
    out = {}
    for r in rows:
        mesh = W._load(r["mesh"], unreal.StaticMesh)
        mesh.modify()
        want = T.slot_plan(r)
        for i, p in enumerate(want):
            mesh.set_material(i, W._load(p))
        got = [pilot.asset_package(s.get_editor_property("material_interface"))
               for s in mesh.get_editor_property("static_materials")]
        if got != want:
            raise RuntimeError("SLOT_MATERIALS|%s|%s" % (r["suffix"], got))
        out[r["suffix"]] = {"slots": got, "screen_sizes": W._ensure_screen_sizes(C3, mesh)}
    W._save(T, world, [r["mesh"] for r in rows], map_expected=False)
    unreal.SystemLibrary.collect_garbage()
    for s, v in out.items():
        W._write(_rec_path("mats", s), {"run": run, "suffix": s, **v, "backup": bdir, "saved": True})
    return {"pieces": sorted(out), "backup": bdir}


# =================================================================================================== DRY / APPLY / REVERT
def _plan_inputs(T, W, world):
    rows = _rows(T)
    layout = T.plan_layout(rows)
    seq = W._load(T.ROOT_SEQ, unreal.LevelSequence)
    live = _live(T, W, world, seq, rows)
    return rows, layout, seq, live


def _newest_asset_write():
    ts = [os.path.getmtime(os.path.join(HERE, f)) for f in os.listdir(HERE)
          if f.startswith(("s3waves_t5o_import_", "s3waves_t5o_mats_", "s3waves_t5o_mi_record")) and f.endswith(".json")]
    return max(ts) if ts else 0.0


def run_verify(T, W, C3, run, world):
    rows = _rows(T)
    rep = {"run": run, "assets": _verify_assets(T, W, C3, rows)}
    rec = W._read(RECORD)
    if rec and rec.get("saved"):
        seq = W._load(T.ROOT_SEQ, unreal.LevelSequence)
        live = _live(T, W, world, seq, rows)
        probs = []
        for op in rec["plan"]["ops"]:
            L = live[op["suffix"]]
            if L["mesh"] != op["mesh"]["after"]:
                probs.append("mesh|%s|%s" % (op["suffix"], L["mesh"]))
            if not T.near(L["relative"]["location"], op["relative_location"]["after"], T.REL_TOL_CM):
                probs.append("relative|%s|%s" % (op["suffix"], L["relative"]["location"]))
            if T.value_sha(L["x_keys"]) != op["x_keys"]["after_sha"]:
                probs.append("x_keys|%s" % op["suffix"])
        fp, names = _fingerprint(T, seq)
        after = W._read(rec["fp_after_file"])
        viol = T.fingerprint_diff(after, fp, {})
        rep["apply"] = {"record_run": rec["run"], "problems": probs, "fingerprint_violations": viol[:20],
                        "fingerprint_rows": len(fp), "expected_tracks": T.expected_tracks_report(names)}
        rep["apply_ok"] = not probs and not viol
    rep["written_mtime_utc"] = datetime.datetime.utcnow().isoformat() + "Z"
    W._write(VERIFY_REPORT, rep)
    return rep


def run_dry(T, W, run, world, census):
    rows, layout, seq, live = _plan_inputs(T, W, world)
    fp, names = _fingerprint(T, seq)
    out = {"run": run, "census": census, "layout": layout, "live": {
        s: dict({k: v for k, v in L.items() if k != "x_keys"}, x_keys_count=len(L["x_keys"] or []),
                x_keys_first_last=[(L["x_keys"] or [None])[0], (L["x_keys"] or [None])[-1]],
                x_keys_values=sorted({round(v[1], 4) for v in (L["x_keys"] or [])})) for s, L in live.items()},
        "fingerprint": {"rows": len(fp), "channels": sum(1 for k in fp if "/C" in k),
                        "bindings": sum(1 for k in fp if k.startswith("B:") and "/" not in k),
                        "expected_tracks": T.expected_tracks_report(names)}}
    verify = W._read(VERIFY_REPORT)
    out["assets_verified"] = bool(verify and (verify.get("assets") or {}).get("all_ready") and
                                  os.path.getmtime(VERIFY_REPORT) > _newest_asset_write())
    try:
        plan = T.plan_apply(rows, live, layout)
        out["apply_plan"] = {"ops": plan["ops"], "allowed_channels": sorted(plan["allowed"])}
        missing = [k for k in plan["allowed"] if k not in fp]
        out["apply"] = "would_apply" if out["assets_verified"] and not missing else \
            "APPLY_WOULD_REFUSE|assets_verified=%s|allowed_missing=%s" % (out["assets_verified"], missing)
    except T.PlanError as exc:
        out["apply"] = "APPLY_WOULD_REFUSE|%s" % exc
    out["summary"] = [
        "pieces: 12 'S3 WaveV3 ...' actors -> SM_FlatV3_<piece>_t5o (5 cm board, outward edges, Edge = MI_WaveEdge_SeaPaint)",
        "x shifts (cm): " + ", ".join("%s %+.0f" % (T.short(p["suffix"]), p["dx"]) for p in layout["pieces"]),
        "layer gaps (clear, cm): " + ", ".join("%s->%s %.1f->%.1f" % (T.short(g["a"]), T.short(g["b"]), g["clear_old_live"],
                                                                     g["clear_new"]) for g in layout["layer_gaps"]),
        "LS_DevScene_03 writes: ONLY the 12 wave bindings' Location.X channels (each key += dx); every other of "
        "%d fingerprint rows must read back identical" % len(fp),
        "expected foreign tracks present: %s" % out["fingerprint"]["expected_tracks"]["present"],
        "apply: %s" % out["apply"]]
    if W._census() != census:
        raise RuntimeError("DRY_DIRTIED|%s" % W._census())
    path = os.path.join(HERE, "s3waves_t5o_dry_%s.json" % run)
    W._write(path, out)
    return out, path


def _backup(T, run, tag, files):
    d = os.path.join(PROJECT, "Backups", "PreS3WavesT5O%s-%s" % (tag, run))
    os.makedirs(d)
    for rel in (T.UMAP_REL, T.ROOT_SEQ_REL):
        src, dst = os.path.join(PROJECT, rel), os.path.join(d, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        if _sha(src) != _sha(dst):
            raise RuntimeError("BACKUP_HASH|%s" % dst)
    for f in files:
        shutil.copy2(f, os.path.join(d, os.path.basename(f)))
    return d


def _apply_ops(T, W, world, seq, ops, mesh_key, rel_key, keys_for):
    eas_world = world
    for op in ops:
        a = W._by_path(eas_world, op["actor_path"])
        if a is None:
            raise RuntimeError("ACTOR_MISSING|%s" % op["actor_path"])
        a.modify()
        c = W._smc(a)
        c.modify()
        c.set_static_mesh(W._load(mesh_key(op), unreal.StaticMesh))
        if W._pkg(c.get_editor_property("static_mesh")) != mesh_key(op):
            raise RuntimeError("MESH_READBACK|%s" % op["actor_path"])
        rc = a.get_editor_property("root_component")
        rc.modify()
        want = rel_key(op)
        rc.set_relative_location(unreal.Vector(*want), False, False)
        if not T.near(W._rel_tf(a)["location"], want, T.REL_TOL_CM):
            raise RuntimeError("RELATIVE_READBACK|%s|%s" % (op["actor_path"], W._rel_tf(a)))
        guid, keys = keys_for(op)
        _set_x_keys(T, seq, guid, keys, op["actor_path"])


def _readback(T, W, world, seq, rows, want):
    """want: {suffix: (mesh, rel_location, x_sha)} -> raises on any mismatch (fresh lookups)."""
    live = _live(T, W, world, seq, rows)
    for s, (mesh, rel, xsha) in want.items():
        L = live[s]
        if L["mesh"] != mesh or not T.near(L["relative"]["location"], rel, T.REL_TOL_CM) or \
                T.value_sha(L["x_keys"]) != xsha:
            raise RuntimeError("READBACK|%s|mesh=%s|rel=%s" % (s, L["mesh"], L["relative"]["location"]))
    return live


def run_apply(T, W, run, world):
    verify = W._read(VERIFY_REPORT)
    if not (verify and (verify.get("assets") or {}).get("all_ready") and
            os.path.getmtime(VERIFY_REPORT) > _newest_asset_write()):
        raise T.PlanError("ASSETS_NOT_VERIFIED (run VERIFY after the last MI/IMPORT/MATS)")
    rows, layout, seq, live = _plan_inputs(T, W, world)
    plan = T.plan_apply(rows, live, layout)
    fp_before, names = _fingerprint(T, seq)
    missing = [k for k in plan["allowed"] if k not in fp_before]
    if missing:
        raise T.PlanError("ALLOWED_PATHS_NOT_IN_FINGERPRINT|%s" % missing[:3])
    W._write(ORIGINALS, T.originals_from_live(rows, live), exclusive=True)          # ORIGINALS FIRST
    unreal.log("%s_ORIGINALS|run=%s|path=%s" % (T.MARK, run, ORIGINALS))
    fp_before_file = os.path.join(HERE, "s3waves_t5o_fp_before_%s.json" % run)
    W._write(fp_before_file, fp_before)
    rec = {"run": run, "plan": {"ops": plan["ops"], "allowed": plan["allowed"]}, "layout": layout,
           "originals": ORIGINALS, "fp_before_file": fp_before_file, "saved": False, "applied": False,
           "expected_tracks": T.expected_tracks_report(names)}
    W._write(RECORD, rec, exclusive=True)
    rec["backup"] = _backup(T, run, "", (ORIGINALS, RECORD, fp_before_file))
    W._write(RECORD, rec)
    by = {r["suffix"]: r for r in rows}
    new_keys = {op["suffix"]: T.shift_x_keys(live[op["suffix"]]["x_keys"], by[op["suffix"]]["mount_local"][0], op["dx"])
                for op in plan["ops"]}
    _apply_ops(T, W, world, seq, plan["ops"], lambda op: op["mesh"]["after"], lambda op: op["relative_location"]["after"],
               lambda op: (op["binding_guid"], new_keys[op["suffix"]]))
    T.apply_scope(W._census())                                                        # map dirty, nothing foreign
    fp_after, _n = _fingerprint(T, seq)
    viol = T.fingerprint_diff(fp_before, fp_after, plan["allowed"])
    if viol:
        raise RuntimeError("FINGERPRINT_VIOLATIONS|%d|%s" % (len(viol), json.dumps(viol[:3])[:600]))
    W._save(T, world, [T.ROOT_SEQ], map_expected=True)
    rec["saved"] = True
    W._write(RECORD, rec)
    seq = W._load(T.ROOT_SEQ, unreal.LevelSequence)
    _readback(T, W, world, seq, rows, {op["suffix"]: (op["mesh"]["after"], op["relative_location"]["after"],
                                                      op["x_keys"]["after_sha"]) for op in plan["ops"]})
    fp_post, _n = _fingerprint(T, seq)
    if T.fingerprint_diff(fp_after, fp_post, {}):
        raise RuntimeError("POST_SAVE_FINGERPRINT_CHANGED")
    rec["fp_after_file"] = os.path.join(HERE, "s3waves_t5o_fp_after_%s.json" % run)
    W._write(rec["fp_after_file"], fp_post)
    rec["applied"] = True
    W._write(RECORD, rec)
    return {"pieces": len(plan["ops"]), "x_channels_changed": len(plan["allowed"]), "fingerprint_rows": len(fp_post),
            "backup": rec["backup"]}


def run_revert(T, W, run, world):
    rec, orig = W._read(RECORD), W._read(ORIGINALS)
    if not rec or not rec.get("saved") or not orig:
        raise T.PlanError("RECORD_INVALID (partial APPLY: restore %s with the editor closed)" % (rec or {}).get("backup"))
    rows = _rows(T)
    seq = W._load(T.ROOT_SEQ, unreal.LevelSequence)
    live = _live(T, W, world, seq, rows)
    plan = T.revert_plan(rec, orig, live)
    fp_before, _n = _fingerprint(T, seq)
    backup = _backup(T, run, "-REVERT", (ORIGINALS, RECORD))
    by = {o["suffix"]: o for o in plan["ops"]}
    _apply_ops(T, W, world, seq, plan["ops"], lambda op: op["mesh"], lambda op: op["relative_location"],
               lambda op: (orig["pieces"][op["suffix"]]["binding_guid"], op["x_keys"]))
    T.apply_scope(W._census())
    fp_after, _n = _fingerprint(T, seq)
    viol = T.fingerprint_diff(fp_before, fp_after, plan["allowed"])
    applied_before = W._read(rec["fp_before_file"])
    restored = [k for k in plan["allowed"] if fp_after[k]["sha"] != applied_before[k]["sha"]]
    if viol or restored:
        raise RuntimeError("REVERT_FINGERPRINT|viol=%d|not_restored=%s" % (len(viol), restored[:3]))
    W._save(T, world, [T.ROOT_SEQ], map_expected=True)
    seq = W._load(T.ROOT_SEQ, unreal.LevelSequence)
    _readback(T, W, world, seq, rows, {s: (o["mesh"], o["relative_location"], T.value_sha(o["x_keys"]))
                                       for s, o in by.items()})
    for p in (RECORD, ORIGINALS):
        os.replace(p, p + ".reverted-" + run)
    return {"restored": len(plan["ops"]), "backup": backup}


# =================================================================================================== main
def main():
    T, W = _core(), _w()
    C3 = _v3core()
    run = "S3T5O-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    mode = "?"
    try:
        args = _read_args()
        run = args.get("run") or run
        ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        rec = W._read(RECORD)
        mode = T.check_mode(args, ed.get_game_world() is not None,
                            {"apply": rec is not None, "applied": bool(rec and rec.get("applied"))})
        unreal.log("%s_START|run=%s|mode=%s|pieces=%s" % (T.MARK, run, mode, args.get("pieces")))
        world = W._editor_world()
        census = W._guard(T, world, need_clean=mode not in T.READ_ONLY)      # PIE, world, Sequencer CLOSED, census
        if mode == "DRY":
            out, path = run_dry(T, W, run, world, census)
            unreal.log("%s_DRY_OK|run=%s|mutated=0|apply=%s|out=%s" % (T.MARK, run, out["apply"][:200], path))
        elif mode == "VERIFY":
            rep = run_verify(T, W, C3, run, world)
            ok = rep["assets"]["all_ready"] and rep.get("apply_ok", True)
            unreal.log("%s_VERIFY_%s|run=%s|assets=%d/12|mi=%s|apply=%s|out=%s" % (
                T.MARK, "OK" if ok else "PARTIAL", run, len(rep["assets"]["ready"]),
                (rep["assets"]["mi"] or {}).get("status"), rep.get("apply_ok", "n/a"), VERIFY_REPORT))
        elif mode == "MI":
            r = run_mi(T, W, run, world)
            unreal.log("%s_MI_OK|run=%s|%s" % (T.MARK, run, json.dumps(r["readback"])))
        elif mode == "IMPORT":
            r = run_import(T, W, C3, run, args, world)
            unreal.log("%s_IMPORT_OK|run=%s|%s|MATS next (a later call)" % (T.MARK, run, json.dumps(r)))
        elif mode == "MATS":
            r = run_mats(T, W, C3, run, args, world)
            unreal.log("%s_MATS_OK|run=%s|%s" % (T.MARK, run, json.dumps(r)))
        elif mode == "APPLY":
            try:
                r = run_apply(T, W, run, world)
            except Exception:
                rec = W._read(RECORD)
                if rec is not None and not rec.get("saved"):
                    os.replace(RECORD, RECORD + ".failed-" + run)
                    if os.path.exists(ORIGINALS):
                        os.replace(ORIGINALS, ORIGINALS + ".failed-" + run)
                raise
            unreal.log("%s_APPLY_OK|run=%s|level_saved=1|seq_saved=1|%s|VERIFY next (a later call)" % (
                T.MARK, run, json.dumps(r)))
        elif mode == "REVERT":
            r = run_revert(T, W, run, world)
            unreal.log("%s_REVERT_OK|run=%s|%s" % (T.MARK, run, json.dumps(r)))
    except Exception as exc:  # noqa: BLE001
        census = None
        try:
            census = W._census()
        except Exception:  # noqa: BLE001
            pass
        unreal.log_error("%s_FAILED|run=%s|mode=%s|%s|census=%s|%s" % (
            "S3T5O", run, mode, str(exc).replace("\n", " ")[:900], json.dumps(census),
            "nothing saved unless an _OK marker printed; dirty map/assets: Don't-Save restart (never reload)"))


if __name__ == "__main__" and unreal is not None:
    main()
