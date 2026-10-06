"""S3 marble: put the TILING marble on the 10 S3 liner actors (Gary 6 Oct: "just marble for now").

Targets (exactly 10, else refuse): "S3 Marble Inner Wall Left|Right" (base liners, 3 Oct) and the 8 upper tiles
"S3 Marble Inner Wall Left|Right Upper 1..4" tagged RigAtmos.S3MarbleLinerUpper (s3_backwall_marble.py, 5 Oct).
Material: s3_marble_tiling_material.py (create-only M_S3_MarbleTiling + MI_S3_Marble_Tiling_Daylight).

Args s3_marble_tiling_apply_args.json:
  {"mode": "DRY"|"IMPORT"|"BUILD"|"APPLY"|"REVERT"|"SWITCH"|"SWITCH_REVERT"|"VERIFY",
   "confirm": "<MODE> S3MARBLE", "frame": "object"|"world", "source": "A"|"B"|"starter"|"custom",
   "variant": "A"|"B" (SWITCH), "variants": ["A","B"] (IMPORT), "textures": {...} (source custom)}
  source A = ambientCG Marble012, B = Marble021 (Gary 6 Oct "Download both to try"); IMPORT must run first.
  Gary 6 Oct "Fixed to the walls": frame "object" is the default.
  frame "world"  = every target gets MI_S3_Marble_Tiling_Daylight (as briefed; correct once the box has LANDED).
  frame "object" = every target gets its own create-only child MI_S3_Marble_Tiling_Daylight_<L|R><k> carrying the
                   frame offsets, so the marble stays rigid on the walls while the box rises (see the material doc).
Modes:
  IMPORT  create-only import of DerivedAssets/S3Marble/<set>/<set>_2K-JPG_{Color,NormalDX,Roughness}.jpg into
          /Game/InfinityStage/Dev/Materials/S3Marble/<set>/T_<set>_<map>; Color sRGB TC_DEFAULT, NormalDX
          TC_NORMALMAP (no green flip), Roughness TC_GRAYSCALE sRGB off (LINEAR_GRAYSCALE sampler); Displacement
          skipped (no input uses it). Existing textures are checked, never edited. Census = exactly the new textures.
  SWITCH  after APPLY (object frame): set only the 10 child MIs' three texture parameters to variant A or B.
          Before-values appended (fsync) to s3_marble_tiling_switch_record.json; census = exactly the changed MIs.
  SWITCH_REVERT  restore the child textures from the LAST switch entry.
  Every write mode asserts the HP_S03 decal count (449) and transform digest are unchanged.
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
import copy
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
SWITCH_REC = HERE + "s3_marble_tiling_switch_record.json"
IMPORT_REC_FMT = HERE + "s3_marble_tiling_import_record_%s.json"
WRITE_MODES = ("IMPORT", "BUILD", "APPLY", "REVERT", "SWITCH", "SWITCH_REVERT")
LEVEL_MODES = ("APPLY", "REVERT")
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
    if mode not in ("DRY", "VERIFY") + WRITE_MODES:
        raise PlanError("MODE|" + mode)
    if mode in WRITE_MODES and args.get("confirm") != "%s %s" % (mode, CONFIRM_WORD):
        raise PlanError("CONFIRM_MISSING")
    if mode == "APPLY" and record_exists:
        raise PlanError("ALREADY_APPLIED|record exists")
    if mode in ("REVERT", "SWITCH", "SWITCH_REVERT") and not record_exists:
        raise PlanError("NO_RECORD|%s needs a saved APPLY" % mode)
    frame = str(args.get("frame", "object")).lower()
    if frame not in ("world", "object"):
        raise PlanError("FRAME|" + frame)
    source = source_key(args)
    if source not in ("starter", "custom") + tuple(M.VARIANTS):
        raise PlanError("SOURCE|" + source)
    if source == "custom":
        tex = args.get("textures") or {}
        missing = [k for k in M.TEXTURE_PARAMS if not tex.get(k)]
        if missing:
            raise PlanError("TEXTURES_MISSING|%s" % missing)
    if mode == "SWITCH":
        if str(args.get("variant", "")).upper() not in M.VARIANTS:
            raise PlanError("VARIANT|%s" % args.get("variant"))
        if frame != "object":
            raise PlanError("SWITCH_NEEDS_OBJECT_FRAME")
    if mode == "IMPORT":
        bad = [v for v in (args.get("variants") or list(M.VARIANTS)) if str(v).upper() not in M.VARIANTS]
        if bad:
            raise PlanError("IMPORT_VARIANTS|%s" % bad)
    return mode, frame, source


def source_key(args):
    src = str(args.get("source", "A"))
    return src.lower() if src.lower() in ("starter", "custom") else src.upper()


def textures_for(args):
    src = source_key(args)
    if src == "custom":
        return {k: args["textures"][k] for k in M.TEXTURE_PARAMS}
    return dict(M.SOURCES[src])


def extra_scalars_for(args):
    return {} if source_key(args) == "starter" else dict(M.VARIANT_SCALARS)


def switch_plan(children_now, variant_textures, scalars_now=None, want_scalars=None):
    """children_now: {mi_path: {param: texture_path}} effective values; scalars_now: {mi_path: {name: value}}.
    Returns the MIs that must change (textures differ, or an optional scalar differs by > 1e-4)."""
    out = []
    for p, tex in children_now.items():
        if any(tex.get(k) != v for k, v in variant_textures.items()):
            out.append(p)
        elif want_scalars and any(abs(float((scalars_now or {}).get(p, {}).get(k, 1e30)) - float(v)) > 1e-4
                                  for k, v in want_scalars.items()):
            out.append(p)
    return sorted(out)


def switch_history_push(history, run, variant, before):
    h = copy.deepcopy(history or {"history": [], "reverted": []})
    h["history"].append({"run": run, "variant": variant, "before": before})
    return h


def switch_history_pop(history, run):
    h = copy.deepcopy(history or {})
    if not h.get("history"):
        raise PlanError("NO_SWITCH_TO_REVERT")
    last = h["history"].pop()
    h.setdefault("reverted", []).append(dict(last, reverted_by=run))
    return h, last


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
    want_maps = [WORLD] if mode in LEVEL_MODES else []
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
    if mode in LEVEL_MODES and not unreal.EditorLoadingAndSavingUtils.save_map(ed.get_editor_world(), WORLD):
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


def _hp_snapshot():
    """Every write mode: 449 decals before, and the same digest before any save (Gary's gate, 6 Oct)."""
    hp = hp_rows(_actors())
    _hp_gate(hp)
    return hp


def _hp_check(before, where):
    after = hp_rows(_actors())
    moved = hp_diff(before, after)
    if moved or hp_digest(after) != hp_digest(before):
        raise PlanError("HP_MOVED|%s|%s" % (where, moved[:5]))
    return len(after)


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _texture_status(textures):
    out = {}
    for k, p in textures.items():
        try:
            _, st = M.texture_sampler(p)
            out[k] = {"path": p, "sampler": st}
        except Exception as exc:  # report only
            out[k] = {"path": p, "error": str(exc)}
    return out


def run_dry(run, args, frame):
    _, cands, rows, plan, children, hp = _gather(frame, "DRY")
    look, look_src = M.live_look()
    eal = unreal.EditorAssetLibrary
    tex = _texture_status(textures_for(args))
    imports = [{"dest": r["dest"], "exists": eal.does_asset_exist(r["dest"]), "file": r["file"],
                "file_ok": os.path.isfile(r["file"])} for r in M.import_plan()]
    master_samplers = None
    if eal.does_asset_exist(M.MASTER):
        master_samplers = M.master_samplers(unreal.load_asset(M.MASTER))
    census = _census()
    out = {"run": run, "frame": frame, "source": source_key(args), "census": census,
           "apply_would_refuse_dirty": census != {"content": [], "maps": []},
           "candidates": cands, "plan": plan, "children": children, "look": look, "look_source": look_src,
           "textures": tex, "imports": imports, "master_samplers": master_samplers,
           "hp_count": len(hp), "hp_expected": HP_EXPECTED, "hp_digest": hp_digest(hp),
           "assets_exist": {p: eal.does_asset_exist(p) for p in
                            [M.MASTER, M.MI] + [M.CHILD_PREFIX + s for s in sorted(children)]}}
    _write(DRY_OUT, out)
    unreal.log("S3_MARBLE_TILING_PLAN|run=%s|%s" % (run, json.dumps(
        {"targets": [(p["label"], p["from"], p["to"]) for p in plan],
         "on_old_mi": sum(1 for p in plan if p["from"] == M.OLD_MI), "children": children, "look": look,
         "textures": tex, "imports_existing": sum(1 for i in imports if i["exists"]),
         "import_files_ok": sum(1 for i in imports if i["file_ok"]), "hp": [len(hp), HP_EXPECTED],
         "census": census, "assets_exist": out["assets_exist"]})))
    if len(hp) != HP_EXPECTED:
        unreal.log_warning("S3_MARBLE_TILING_DRY_HP_COUNT|run=%s|%d!=%d" % (run, len(hp), HP_EXPECTED))
    if any("error" in v for v in tex.values()):
        unreal.log_warning("S3_MARBLE_TILING_DRY_TEXTURE|run=%s|%s (IMPORT first?)" % (run, json.dumps(tex)))
    return {"targets": len(plan), "out": DRY_OUT}


def run_import(run, args, ed):
    hp = _hp_snapshot()
    eal = unreal.EditorAssetLibrary
    variants = [str(v).upper() for v in (args.get("variants") or list(M.VARIANTS))]
    rows = M.import_plan(variants)
    missing = [r["file"] for r in rows if not os.path.isfile(r["file"])]
    if missing:
        raise PlanError("SOURCE_FILES_MISSING|%s" % missing)
    record = {"run": run, "rows": [], "created": []}
    todo = []
    for r in rows:
        entry = dict(r, sha256=_sha256(r["file"]), bytes=os.path.getsize(r["file"]))
        if eal.does_asset_exist(r["dest"]):
            _, got = M.read_texture_settings(r["dest"])     # existing: check, never edit
            probs = M.texture_settings_problems(r, got)
            if probs:
                raise PlanError("EXISTING_TEXTURE_WRONG|%s" % probs)
            entry["existing"] = got
        else:
            todo.append(r)
        record["rows"].append(entry)
    rec_path = IMPORT_REC_FMT % run
    _write(rec_path, record, exclusive=True)
    for r in todo:
        got = M.import_texture(r)
        record["created"].append(r["dest"])
        next(e for e in record["rows"] if e["dest"] == r["dest"])["readback"] = got
        _write(rec_path, record)
    created = list(record["created"])
    dirty_now = set(_census()["content"])
    resumed = [e["dest"] for e in record["rows"] if "existing" in e and e["dest"] in dirty_now]  # unsaved from a stopped run
    record["resumed_unsaved"] = resumed
    _write(rec_path, record)
    _hp_check(hp, "IMPORT")
    if created or resumed:
        _save(ed, created + resumed, "IMPORT")
        for r in todo:                                         # read back again after the save
            _, got = M.read_texture_settings(r["dest"])
            probs = M.texture_settings_problems(r, got)
            if probs:
                raise PlanError("POST_SAVE_TEXTURE|%s" % probs)
    record["saved"] = True
    _write(rec_path, record)
    return {"created": created, "existing_checked": len(rows) - len(todo), "record": rec_path}


def run_build(run, args, frame, ed):
    hp = _hp_snapshot()
    _, _, rows, plan, children, _ = _gather(frame, "BUILD")
    look, _ = M.live_look()
    _, created, rb = M.ensure(look, textures_for(args), children, extra_scalars_for(args))
    _hp_check(hp, "BUILD")
    if created:
        _save(ed, created, "BUILD")
    return {"created": created, "source": source_key(args), "master_samplers": rb["master"].get("param_samplers"),
            "note": "" if created else "all assets already existed (checked, not edited)"}


def run_apply(run, args, frame, ed):
    actors, _, rows, plan, children, hp_before = _gather(frame, "APPLY")
    _hp_gate(hp_before)
    backup = BACKUP_ROOT + run
    record = {"run": run, "world": WORLD, "frame": frame, "source": source_key(args), "backup": backup,
              "saved": False,
              "targets": [{"label": r["label"], "object_path": r["object_path"], "materials": r["materials"],
                           "overrides": r["overrides"]} for r in rows],
              "plan": plan, "hp_count": len(hp_before), "hp_digest": hp_digest(hp_before)}
    _write(REC, record, exclusive=True)
    os.makedirs(backup)
    shutil.copy2(UMAP, backup)
    if not os.path.isfile(os.path.join(backup, os.path.basename(UMAP))):
        raise PlanError("BACKUP_MISSING")
    look, look_src = M.live_look()
    assets, created, rb = M.ensure(look, textures_for(args), children, extra_scalars_for(args))
    record.update({"created": created, "look": look, "look_source": look_src})
    _write(REC, record)
    idx = _index_by_path(actors)
    for p in plan:
        mat = assets["mi"] if frame == "world" else assets["children"][M.child_suffix(p)]
        comp = _smc(idx[p["object_path"]])
        comp.modify()
        comp.set_material(0, mat)
    _readback_targets(plan, "to")
    n_hp = _hp_check(hp_before, "APPLY")
    _save(ed, created, "APPLY")
    record["saved"] = True
    _write(REC, record)
    _readback_targets(plan, "to")                         # again, after the save
    return {"assigned": len(plan), "created": created, "hp": n_hp, "frame": frame, "source": record["source"]}


def _children_from_record():
    rec = json.load(open(REC, encoding="utf-8"))
    if rec.get("frame") != "object" or not rec.get("saved"):
        raise PlanError("SWITCH_NEEDS_SAVED_OBJECT_APPLY|frame=%s" % rec.get("frame"))
    paths = sorted({p["to"] for p in rec["plan"]})
    if len(paths) != EXPECTED_TARGETS or not all(p.startswith(M.CHILD_PREFIX) for p in paths):
        raise PlanError("SWITCH_CHILDREN|%s" % paths)
    return rec, paths


def _set_children(targets, hp, mode, ed):
    """targets: {mi_path: {"textures": {...}, "scalars": {...}}}. Only our APPLY-created child MIs.
    Set, read back, HP gate, census = exactly these MIs, save, read back again."""
    mel = unreal.MaterialEditingLibrary
    for path, want in sorted(targets.items()):
        mi = unreal.load_asset(path)
        mi.modify()
        M.set_mi_textures(mi, want["textures"])
        for k, v in (want.get("scalars") or {}).items():
            mel.set_material_instance_scalar_parameter_value(mi, k, float(v))
        mel.update_material_instance(mi)
        M.check_mi(mi, mi.get_editor_property("parent"), want.get("scalars") or {}, want["textures"])
    _hp_check(hp, mode)
    changed = sorted(targets)
    _save(ed, changed, mode)
    for path, want in targets.items():                       # read back after the save
        mi = unreal.load_asset(path)
        M.check_mi(mi, mi.get_editor_property("parent"), want.get("scalars") or {}, want["textures"])
    return changed


def run_switch(run, args, ed):
    """Gary compares A/B without a rebuild. Textures only by default; optional "switch_scalars" (e.g.
    {"Brightness": 1.0} for B, which clips 84% of its pixels to pure white at the copied 1.15) are recorded too."""
    hp = _hp_snapshot()
    _, paths = _children_from_record()
    variant = str(args["variant"]).upper()
    want = M.SOURCES[variant]
    want_scalars = {str(k): float(v) for k, v in (args.get("switch_scalars") or {}).items()}
    bad = [k for k in want_scalars if k not in M.SCALARS or k in M.FRAME_PARAMS]
    if bad:
        raise PlanError("SWITCH_SCALARS_NOT_ALLOWED|%s" % bad)
    master = unreal.load_asset(M.MASTER)
    probs = M.sampler_problems(M.master_samplers(master), M.texture_samplers(want))
    if probs:
        raise PlanError(";".join(probs))
    now = {p: M.mi_textures(unreal.load_asset(p)) for p in paths}
    now_s = {p: M._mi_scalars(unreal.load_asset(p), list(want_scalars)) for p in paths}
    changed = switch_plan(now, want, now_s, want_scalars)
    if not changed:
        return {"variant": variant, "changed": 0, "note": "already showing this variant"}
    history = json.load(open(SWITCH_REC, encoding="utf-8")) if os.path.exists(SWITCH_REC) else None
    _write(SWITCH_REC, switch_history_push(history, run, variant,
                                           {p: {"textures": now[p], "scalars": now_s[p]} for p in changed}))
    done = _set_children({p: {"textures": dict(want), "scalars": want_scalars} for p in changed}, hp, "SWITCH", ed)
    return {"variant": variant, "changed": len(done), "scalars": want_scalars, "history": SWITCH_REC}


def run_switch_revert(run, ed):
    hp = _hp_snapshot()
    _children_from_record()
    if not os.path.exists(SWITCH_REC):
        raise PlanError("NO_SWITCH_RECORD")
    history = json.load(open(SWITCH_REC, encoding="utf-8"))
    new_hist, last = switch_history_pop(history, run)
    todo = {}
    for p, before in last["before"].items():
        mi = unreal.load_asset(p)
        if M.mi_textures(mi) != before["textures"] or any(
                abs(v - b) > 1e-4 for v, b in zip(M._mi_scalars(mi, list(before["scalars"])).values(),
                                                   before["scalars"].values())):
            todo[p] = before
    done = _set_children(todo, hp, "SWITCH_REVERT", ed) if todo else []
    _write(SWITCH_REC, new_hist)
    return {"undid": last["run"], "variant_undone": last["variant"], "changed": len(done)}


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
    _hp_gate(hp_before)
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
    _hp_check(hp_before, "REVERT")
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
        if rec.get("frame") == "object":
            out["child_textures"] = {p["to"]: M.mi_textures(unreal.load_asset(p["to"])) for p in rec["plan"]}
            shown = {json.dumps(t, sort_keys=True) for t in out["child_textures"].values()}
            out["variant_shown"] = [v for v in M.VARIANTS if json.dumps(M.SOURCES[v], sort_keys=True) in shown]
            if len(shown) != 1:
                fails.append("CHILDREN_DISAGREE|%d texture sets" % len(shown))
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
            c0 = _census()
            # IMPORT may resume over its OWN unsaved new textures (a run that stopped before saving); nothing else.
            resumable = (mode == "IMPORT" and not c0["maps"]
                         and all(p.startswith("/Game/InfinityStage/Dev/Materials/S3Marble/") for p in c0["content"]))
            if c0 != {"content": [], "maps": []} and not resumable:
                raise PlanError("DIRTY_BEFORE|" + json.dumps(c0))
            if mode == "IMPORT":
                result = run_import(run, args, ed)
            elif mode == "BUILD":
                result = run_build(run, args, frame, ed)
            elif mode == "SWITCH":
                result = run_switch(run, args, ed)
            elif mode == "SWITCH_REVERT":
                result = run_switch_revert(run, ed)
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
            if mode in WRITE_MODES else "read-only mode mutated nothing"))
        raise


if unreal is not None:
    main()
