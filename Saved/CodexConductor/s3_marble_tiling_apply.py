"""S3 marble: put the TILING marble on the 10 S3 liner actors (Gary 6 Oct: "just marble for now").

Targets (exactly 10, else refuse): "S3 Marble Inner Wall Left|Right" (base liners, 3 Oct) and the 8 upper tiles
"S3 Marble Inner Wall Left|Right Upper 1..4" tagged RigAtmos.S3MarbleLinerUpper (s3_backwall_marble.py, 5 Oct).
Material: s3_marble_tiling_material.py (create-only M_S3_MarbleTiling + MI_S3_Marble_Tiling_Daylight).

Args s3_marble_tiling_apply_args.json:
  {"mode": "DRY"|"BUILD"|"APPLY"|"REVERT"|"VERIFY", "confirm": "<MODE> S3MARBLE",
   "frame": "world"|"object", "source": "starter"|"custom", "textures": {BaseColorTexture, NormalTexture,
   RoughnessTexture}}
  frame "world"  = every target gets MI_S3_Marble_Tiling_Daylight (as briefed; correct once the box has LANDED).
  frame "object" = every target gets its own create-only child MI_S3_Marble_Tiling_Daylight_<L|R><k> carrying the
                   frame offsets, so the marble stays rigid on the walls while the box rises (see the material doc).
Modes:
  DRY     read-only: targets, record preview, frame params, HP_S03 count/transform hash, census. Writes _dry.json.
  BUILD   create the material assets only (no level change); census must be exactly the created packages.
          Recommended before APPLY so VERIFY can read compile results before the level is touched.
  APPLY   guards (world, no PIE, clean census, record absent, 10 targets on the OLD MI, 449 HP_S03 decals) -> record
          (fsync) -> umap backup -> ensure materials (create-only; census may add exactly those) -> set slot 0 on
          the 10 components -> read back -> HP_S03 transforms unchanged -> census = level (+ created) -> save
          exactly those -> clean.
  REVERT  restores each recorded override material, read back, HP unchanged, save level only. Materials stay.
  VERIFY  read-only: materials, MI values, master shader stats, compile errors in the log since the last
          BUILD/APPLY marker, targets on the expected MI, HP count.
Markers: S3_MARBLE_TILING_<MODE>_OK|run=.. / S3_MARBLE_TILING_FAILED|run=..
Importing without Unreal (offline harness) runs nothing.
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

HERE = "E:/PussStage/Saved/CodexConductor/"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
ARGS = HERE + "s3_marble_tiling_apply_args.json"
REC = HERE + "s3_marble_tiling_record.json"
DRY_OUT = HERE + "s3_marble_tiling_dry.json"
VERIFY_OUT = HERE + "s3_marble_tiling_verify.json"
BACKUP_ROOT = "E:/PussStage/Backups/PreS3MarbleTiling-"
LOG_FILE = "E:/PussStage/Saved/Logs/PussStage.log"
CUBE = "/Engine/BasicShapes/Cube"
LINERS = {"L": "S3 Marble Inner Wall Left", "R": "S3 Marble Inner Wall Right"}
TILE_TAG = "RigAtmos.S3MarbleLinerUpper"
UPPER_COUNT = 4
EXPECTED_TARGETS = 10
HP_TAG = "HP_S03"
HP_EXPECTED = 449
CONFIRM_WORD = "S3MARBLE"
COMPILE_MARKER = [("S3_MARBLE_TILING_START|", "|mode=BUILD|"), ("S3_MARBLE_TILING_START|", "|mode=APPLY|")]
TOL = 1e-3


def _load_material_module():
    """Fresh load every run (memory ue58-python-stale-module-cache): not registered in sys.modules."""
    spec = importlib.util.spec_from_file_location("_s3_marble_tiling_material_run",
                                                  os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                               "s3_marble_tiling_material.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M = _load_material_module()


class PlanError(ValueError):
    pass


# ----------------------------------------------------------------------------------------------- pure planning
def check_mode(args, record_exists):
    mode = str(args.get("mode", "DRY")).upper()
    if mode not in ("DRY", "BUILD", "APPLY", "REVERT", "VERIFY"):
        raise PlanError("MODE|" + mode)
    if mode in ("BUILD", "APPLY", "REVERT") and args.get("confirm") != "%s %s" % (mode, CONFIRM_WORD):
        raise PlanError("CONFIRM_MISSING")
    if mode == "APPLY" and record_exists:
        raise PlanError("ALREADY_APPLIED|record exists")
    if mode == "REVERT" and not record_exists:
        raise PlanError("NO_RECORD")
    frame = str(args.get("frame", "world")).lower()
    if frame not in ("world", "object"):
        raise PlanError("FRAME|" + frame)
    source = str(args.get("source", "starter")).lower()
    if source not in ("starter", "custom"):
        raise PlanError("SOURCE|" + source)
    if source == "custom":
        tex = args.get("textures") or {}
        missing = [k for k in M.TEXTURE_PARAMS if not tex.get(k)]
        if missing:
            raise PlanError("TEXTURES_MISSING|%s" % missing)
    return mode, frame, source


def textures_for(args):
    return dict(M.SOURCES["starter"]) if str(args.get("source", "starter")).lower() == "starter" \
        else {k: args["textures"][k] for k in M.TEXTURE_PARAMS}


def select_targets(actors):
    """actors: rows {label, tags, class, object_path, mesh, num_slots, materials, world, parent_label}.
    Returns the 10 target rows with side/role/index, or raises. Lists near-misses so a DRY explains itself."""
    by_label = {}
    for a in actors:
        by_label.setdefault(a["label"], []).append(a)
    fails, rows = [], []
    for side, base in LINERS.items():
        hits = by_label.get(base, [])
        if len(hits) != 1:
            fails.append("BASE_COUNT|%s|%d" % (base, len(hits)))
            continue
        rows.append(dict(hits[0], side=side, role="base", index=0))
    tagged = [a for a in actors if TILE_TAG in a["tags"]]
    want = {"%s Upper %d" % (LINERS[s], k): (s, k) for s in "LR" for k in range(1, UPPER_COUNT + 1)}
    for a in tagged:
        if a["label"] not in want:
            fails.append("TAGGED_UNEXPECTED|%s" % a["label"])
    for label, (side, k) in sorted(want.items()):
        hits = [a for a in tagged if a["label"] == label]
        if len(hits) != 1:
            fails.append("UPPER_COUNT|%s|%d" % (label, len(hits)))
            continue
        rows.append(dict(hits[0], side=side, role="upper", index=k))
    if len(rows) != EXPECTED_TARGETS:
        fails.append("TARGET_COUNT|%d!=%d" % (len(rows), EXPECTED_TARGETS))
    for r in rows:
        if r["mesh"] != CUBE:
            fails.append("MESH|%s|%s" % (r["label"], r["mesh"]))
        if r["num_slots"] != 1:
            fails.append("SLOTS|%s|%d" % (r["label"], r["num_slots"]))
    if fails:
        raise PlanError(";".join(fails))
    return rows


def target_material(row, frame):
    return M.MI if frame == "world" else M.CHILD_PREFIX + M.child_suffix(row)


def plan_assignment(rows, frame, mode):
    """Decide per-target from/to and refuse mixed or foreign states."""
    params = M.object_frame_params(rows) if frame == "object" else {}
    plan, fails = [], []
    new_set = {target_material(r, frame) for r in rows}
    for r in rows:
        cur = r["materials"][0]
        to = target_material(r, frame)
        if mode == "APPLY" and cur != M.OLD_MI:
            fails.append("NOT_ON_OLD_MI|%s|%s" % (r["label"], cur))
        plan.append({"label": r["label"], "object_path": r["object_path"], "side": r["side"], "role": r["role"],
                     "index": r["index"], "from": cur, "to": to,
                     "frame_params": params.get(r["label"])})
    if mode == "APPLY" and fails:
        if all(p["from"] in new_set for p in plan):
            raise PlanError("ALREADY_ON_NEW_MATERIAL")
        raise PlanError(";".join(fails))
    children = {}
    if frame == "object":
        for r in rows:
            children[M.child_suffix(r)] = params[r["label"]]
    return plan, children


def hp_digest(hp_rows):
    """Order-independent digest of the HP_S03 decals' labels, parents and world transforms (0.01 cm / 0.001)."""
    keyed = sorted("%s|%s|%s|%s|%s" % (h["object_path"], h["parent_label"],
                                       ",".join("%.2f" % v for v in h["location"]),
                                       ",".join("%.3f" % v for v in h["rotation"]),
                                       ",".join("%.4f" % v for v in h["scale"])) for h in hp_rows)
    return hashlib.sha256("\n".join(keyed).encode("utf-8")).hexdigest()


def hp_diff(before, after):
    b = {h["object_path"]: h for h in before}
    a = {h["object_path"]: h for h in after}
    moved = []
    for k in sorted(set(b) | set(a)):
        if k not in b or k not in a:
            moved.append("PRESENCE|" + k)
            continue
        x, y = b[k], a[k]
        if x["parent_label"] != y["parent_label"] or any(
                abs(float(x[f][i]) - float(y[f][i])) > TOL for f in ("location", "rotation", "scale") for i in range(3)):
            moved.append("MOVED|" + k)
    return moved


def census_ok(dirty, mode, created):
    """Exactly the packages this run is allowed to dirty."""
    want_maps = [] if mode == "BUILD" else [WORLD]
    return dirty["maps"] == want_maps and sorted(dirty["content"]) == sorted(created)


# ------------------------------------------------------------------------------------------------- unreal glue
def _v(x):
    return [float(x.x), float(x.y), float(x.z)]


def _r(rot):
    return [float(rot.roll), float(rot.pitch), float(rot.yaw)]


def _path(obj):
    return str(obj.get_path_name()).split(".", 1)[0] if obj is not None else None


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def _actors():
    return list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())


def _parent(actor):
    p = actor.get_attach_parent_actor()
    return str(p.get_actor_label()) if p else None


def _smc(actor):
    comps = list(actor.get_components_by_class(unreal.StaticMeshComponent))
    return comps[0] if len(comps) == 1 else None


def _world(actor):
    return {"location": _v(actor.get_actor_location()), "rotation": _r(actor.get_actor_rotation()),
            "scale": _v(actor.get_actor_scale3d())}


def _overrides(comp):
    return [_path(m) for m in (comp.get_editor_property("override_materials") or [])]


def candidate_rows(actors):
    out = []
    for a in actors:
        label = str(a.get_actor_label())
        tags = [str(t) for t in a.tags]
        if not (label.startswith("S3 Marble Inner Wall") or TILE_TAG in tags):
            continue
        c = _smc(a)
        mesh = _path(c.get_editor_property("static_mesh")) if c else None
        n = int(c.get_num_materials()) if c else 0
        out.append({"label": label, "tags": tags, "class": a.get_class().get_name(), "object_path": a.get_path_name(),
                    "mesh": mesh, "num_slots": n, "materials": [_path(c.get_material(i)) for i in range(n)] if c else [],
                    "overrides": _overrides(c) if c else [], "world": _world(a), "parent_label": _parent(a)})
    return out


def hp_rows(actors):
    rows = []
    for a in actors:
        if HP_TAG in [str(t) for t in a.tags]:
            w = _world(a)
            rows.append({"label": str(a.get_actor_label()), "object_path": a.get_path_name(),
                         "parent_label": _parent(a), "location": w["location"], "rotation": w["rotation"],
                         "scale": w["scale"]})
    return rows


def _cross_check_axes(actor, row):
    """The pure rotator->axes maths must agree with UE's own vectors for this actor."""
    rot = actor.get_actor_rotation()
    fx, _, fz = M.rotator_axes(row["world"]["rotation"])
    for mine, ue in ((fx, rot.get_forward_vector()), (fz, rot.get_up_vector())):
        if any(abs(mine[i] - _v(ue)[i]) > 1e-4 for i in range(3)):
            raise PlanError("AXES_MATH_DISAGREES|%s|%s|%s" % (row["label"], mine, _v(ue)))


def _write(path, value, exclusive=False):
    with open(path, "x" if exclusive else "w", encoding="utf-8") as h:
        json.dump(value, h, indent=1)
        h.flush()
        os.fsync(h.fileno())


def _index_by_path(actors):
    return {a.get_path_name(): a for a in actors}


def _save(ed, created, mode):
    bad = [str(a.get_actor_label()) for a in _actors()
           if str(a.get_actor_label()).startswith("ZZ_") or "TEMP" in str(a.get_actor_label()).upper()]
    if bad:
        raise PlanError("TEMP_ACTORS_PRESENT|%s" % bad[:5])
    dirty = _census()
    if not census_ok(dirty, mode, created):
        raise PlanError("DIRTY_SCOPE|%s|allowed=%s" % (json.dumps(dirty), created))
    for p in created:
        if not unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False):
            raise PlanError("SAVE_ASSET_FAILED|" + p)
    if mode != "BUILD" and not unreal.EditorLoadingAndSavingUtils.save_map(ed.get_editor_world(), WORLD):
        raise PlanError("SAVE_MAP_FAILED")
    if _census() != {"content": [], "maps": []}:
        raise PlanError("POST_SAVE_DIRTY|" + json.dumps(_census()))


def _gather(frame, mode):
    actors = _actors()
    cands = candidate_rows(actors)
    rows = select_targets(cands)
    idx = _index_by_path(actors)
    for r in rows:
        _cross_check_axes(idx[r["object_path"]], r)
    plan, children = plan_assignment(rows, frame, mode)
    hp = hp_rows(actors)
    return actors, cands, rows, plan, children, hp


def _hp_gate(hp):
    if len(hp) != HP_EXPECTED:
        raise PlanError("HP_COUNT|%d!=%d" % (len(hp), HP_EXPECTED))


def run_dry(run, args, frame):
    _, cands, rows, plan, children, hp = _gather(frame, "DRY")
    look, look_src = M.live_look()
    eal = unreal.EditorAssetLibrary
    textures = textures_for(args)
    tex = {}
    for k, p in textures.items():
        try:
            _, st = M.texture_sampler(p)
            tex[k] = {"path": p, "sampler": st}
        except Exception as exc:  # report, the DRY still finishes
            tex[k] = {"path": p, "error": str(exc)}
    census = _census()
    out = {"run": run, "frame": frame, "census": census, "apply_would_refuse_dirty": census != {"content": [], "maps": []},
           "candidates": cands, "plan": plan, "children": children, "look": look, "look_source": look_src,
           "textures": tex, "hp_count": len(hp), "hp_expected": HP_EXPECTED, "hp_digest": hp_digest(hp),
           "assets_exist": {p: eal.does_asset_exist(p) for p in
                            [M.MASTER, M.MI] + [M.CHILD_PREFIX + s for s in sorted(children)]}}
    _write(DRY_OUT, out)
    unreal.log("S3_MARBLE_TILING_PLAN|run=%s|%s" % (run, json.dumps(
        {"targets": [(p["label"], p["from"], p["to"]) for p in plan],
         "on_old_mi": sum(1 for p in plan if p["from"] == M.OLD_MI), "children": children, "look": look,
         "textures": tex, "hp": [len(hp), HP_EXPECTED], "census": census, "assets_exist": out["assets_exist"]})))
    if len(hp) != HP_EXPECTED:
        unreal.log_warning("S3_MARBLE_TILING_DRY_HP_COUNT|run=%s|%d!=%d" % (run, len(hp), HP_EXPECTED))
    if any("error" in v for v in tex.values()):
        unreal.log_warning("S3_MARBLE_TILING_DRY_TEXTURE|run=%s|%s" % (run, json.dumps(tex)))
    return {"targets": len(plan), "out": DRY_OUT}


def run_build(run, args, frame):
    _, _, rows, plan, children, _ = _gather(frame, "BUILD")
    look, _ = M.live_look()
    _, created, rb = M.ensure(look, textures_for(args), children)
    if not created:
        return {"created": [], "note": "all assets already existed (checked, not edited)", "readback": rb}
    return {"created": created, "readback": rb, "_save": created}


def run_apply(run, args, frame, ed):
    actors, _, rows, plan, children, hp_before = _gather(frame, "APPLY")
    _hp_gate(hp_before)
    backup = BACKUP_ROOT + run
    record = {"run": run, "world": WORLD, "frame": frame, "backup": backup, "saved": False,
              "targets": [{"label": r["label"], "object_path": r["object_path"], "materials": r["materials"],
                           "overrides": r["overrides"]} for r in rows],
              "plan": plan, "hp_count": len(hp_before), "hp_digest": hp_digest(hp_before)}
    _write(REC, record, exclusive=True)
    os.makedirs(backup)
    shutil.copy2(UMAP, backup)
    if not os.path.isfile(os.path.join(backup, os.path.basename(UMAP))):
        raise PlanError("BACKUP_MISSING")
    look, look_src = M.live_look()
    assets, created, rb = M.ensure(look, textures_for(args), children)
    record.update({"created": created, "look": look, "look_source": look_src})
    _write(REC, record)
    idx = _index_by_path(actors)
    for p in plan:
        mat = assets["mi"] if frame == "world" else assets["children"][M.child_suffix(p)]
        comp = _smc(idx[p["object_path"]])
        comp.modify()
        comp.set_material(0, mat)
    _readback_targets(plan, "to")
    hp_after = hp_rows(_actors())
    moved = hp_diff(hp_before, hp_after)
    if moved or hp_digest(hp_after) != record["hp_digest"]:
        raise PlanError("HP_MOVED|%s" % moved[:5])
    _save(ed, created, "APPLY")
    record["saved"] = True
    _write(REC, record)
    _readback_targets(plan, "to")                         # again, after the save
    return {"assigned": len(plan), "created": created, "hp": len(hp_after), "frame": frame}


def _readback_targets(plan, key):
    idx = _index_by_path(_actors())
    bad = []
    for p in plan:
        a = idx.get(p["object_path"])
        got = _path(_smc(a).get_material(0)) if a else None
        if got != p[key]:
            bad.append("%s|%s!=%s" % (p["label"], got, p[key]))
    if bad:
        raise PlanError("TARGET_READBACK|%s" % bad)


def run_revert(run, ed):
    with open(REC, encoding="utf-8") as h:
        record = json.load(h)
    if record.get("world") != WORLD or not record.get("saved"):
        raise PlanError("RECORD_INVALID")
    actors = _actors()
    idx = _index_by_path(actors)
    hp_before = hp_rows(actors)
    for t in record["targets"]:
        if t["object_path"] not in idx:
            raise PlanError("TARGET_GONE|" + t["label"])
        cur = _path(_smc(idx[t["object_path"]]).get_material(0))
        want_now = next(p["to"] for p in record["plan"] if p["object_path"] == t["object_path"])
        if cur != want_now:
            raise PlanError("TARGET_CHANGED_SINCE_APPLY|%s|%s" % (t["label"], cur))
    backup = BACKUP_ROOT + run
    os.makedirs(backup)
    shutil.copy2(UMAP, backup)
    for t in record["targets"]:
        comp = _smc(idx[t["object_path"]])
        comp.modify()
        ov = t["overrides"][0] if t["overrides"] else None
        comp.set_material(0, unreal.load_asset(ov) if ov else None)
    idx = _index_by_path(_actors())
    bad = []
    for t in record["targets"]:
        c = _smc(idx[t["object_path"]])
        if _path(c.get_material(0)) != t["materials"][0] or (_overrides(c)[:1] or [None]) != (t["overrides"][:1] or [None]):
            bad.append(t["label"])
    if bad:
        raise PlanError("REVERT_READBACK|%s" % bad)
    if hp_diff(hp_before, hp_rows(_actors())):
        raise PlanError("HP_MOVED_ON_REVERT")
    _save(ed, [], "REVERT")
    os.replace(REC, REC + ".reverted-" + run)
    return {"restored": len(record["targets"])}


def run_verify(run, args, frame):
    eal, mel = unreal.EditorAssetLibrary, unreal.MaterialEditingLibrary
    fails = []
    out = {"run": run, "frame": frame, "census": _census()}
    if not eal.does_asset_exist(M.MASTER) or not eal.does_asset_exist(M.MI):
        raise PlanError("MATERIALS_MISSING")
    master = unreal.load_asset(M.MASTER)
    out["master"] = M.readback_master(master)
    stats = mel.get_statistics(master)
    out["stats"] = {p: int(stats.get_editor_property(p)) for p in
                    ("num_pixel_shader_instructions", "num_vertex_shader_instructions", "num_pixel_texture_samples")}
    if out["stats"]["num_pixel_shader_instructions"] <= 0:
        fails.append("NO_PIXEL_SHADER|compile pending or failed; re-run VERIFY in ~30 s")
    try:
        text = open(LOG_FILE, encoding="utf-8", errors="replace").read()
    except OSError as exc:
        text, out["log_error"] = "", str(exc)
    # From the START line of the last BUILD or APPLY run (compile messages land between START and _OK, and after).
    marker = args.get("since_marker") or COMPILE_MARKER
    errs = M.compile_errors_since(text, marker)
    out["compile_errors"], out["log_marker"] = errs, marker
    if errs is None:
        fails.append("LOG_MARKER_NOT_FOUND|%s" % marker)
    elif errs:
        fails.append("COMPILE_ERRORS|%d" % len(errs))
    mi = unreal.load_asset(M.MI)
    out["mi_parent"] = _path(mi.get_editor_property("parent"))
    out["mi"] = M._mi_scalars(mi, list(M.SCALARS))
    if out["mi_parent"] != M.MASTER:
        fails.append("MI_PARENT")
    actors = _actors()
    hp = hp_rows(actors)
    out["hp_count"] = len(hp)
    if len(hp) != HP_EXPECTED:
        fails.append("HP_COUNT|%d" % len(hp))
    if os.path.exists(REC):
        rec = json.load(open(REC, encoding="utf-8"))
        out["hp_digest_matches_apply"] = hp_digest(hp) == rec.get("hp_digest")
        if not out["hp_digest_matches_apply"]:
            fails.append("HP_DIGEST_CHANGED_SINCE_APPLY")
        idx = _index_by_path(actors)
        out["targets"] = {}
        for p in rec["plan"]:
            a = idx.get(p["object_path"])
            got = _path(_smc(a).get_material(0)) if a else None
            out["targets"][p["label"]] = got
            if got != p["to"]:
                fails.append("TARGET|%s|%s" % (p["label"], got))
    out["fails"] = fails
    _write(VERIFY_OUT, out)
    if fails:
        raise PlanError("VERIFY|%s|out=%s" % (";".join(fails), VERIFY_OUT))
    return {"stats": out["stats"], "targets_checked": len(out.get("targets", {})), "out": VERIFY_OUT}


def main():
    run = datetime.datetime.now().strftime("S3MT-%Y%m%d-%H%M%S")
    mode = "DRY"
    try:
        with open(ARGS, encoding="utf-8") as h:
            args = json.load(h)
        mode, frame, _ = check_mode(args, os.path.exists(REC))
        ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = ed.get_editor_world()
        if world is None or world.get_outermost().get_name() != WORLD:
            raise PlanError("WRONG_WORLD")
        if ed.get_game_world() is not None:
            raise PlanError("PIE_ACTIVE")
        unreal.log("S3_MARBLE_TILING_START|run=%s|mode=%s|frame=%s" % (run, mode, frame))
        if mode == "DRY":
            result = run_dry(run, args, frame)
        elif mode == "VERIFY":
            result = run_verify(run, args, frame)
        else:
            if _census() != {"content": [], "maps": []}:
                raise PlanError("DIRTY_BEFORE|" + json.dumps(_census()))
            if mode == "BUILD":
                result = run_build(run, args, frame)
                created = result.pop("_save", [])
                if created:
                    _save(ed, created, "BUILD")
            elif mode == "APPLY":
                try:
                    result = run_apply(run, args, frame, ed)
                except Exception:
                    if os.path.exists(REC) and not json.load(open(REC, encoding="utf-8")).get("saved"):
                        os.replace(REC, REC + ".failed-" + run)
                    raise
            else:
                result = run_revert(run, ed)
        unreal.log("S3_MARBLE_TILING_%s_OK|run=%s|%s" % (mode, run, json.dumps(result, default=str)))
    except Exception as exc:
        census = {}
        try:
            census = _census()
        except Exception:
            pass
        unreal.log_error("S3_MARBLE_TILING_FAILED|run=%s|mode=%s|%s|census=%s|%s" % (
            run, mode, str(exc).replace("\n", " "), json.dumps(census),
            "NOTHING SAVED unless an _OK marker printed; if anything is dirty: Don't-Save restart"
            if mode in ("BUILD", "APPLY", "REVERT") else "read-only mode mutated nothing"))
        raise


if unreal is not None:
    main()
