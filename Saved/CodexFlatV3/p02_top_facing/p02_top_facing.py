"""Job 106 live driver.  Offline-written; run later through p02_top_facing_run.py.

DRY/APPLY/REVERT are guarded and recorded.  The sole authoring write is
WingPair.Top.FacingPolicy on the 23 P02 rows.  No image flip or transform write.
"""
import copy
import datetime
import importlib.util
import json
import os

try:
    import unreal
except ModuleNotFoundError:  # offline harness
    unreal = None


ARGS_NAME = "p02_top_facing_args.json"
CLEAN = {"content": [], "maps": []}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write(path, value, fsync=False):
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=1, default=str)
        handle.flush()
        if fsync:
            os.fsync(handle.fileno())
    os.replace(temp, path)
    return path


def active_path(here):
    return os.path.join(here, "p02_top_facing_ACTIVE.json")


def stop(ops, core, run_id, reason):
    ops.log_error("%s_STOPPED|run=%s|passage=P02|reason=%s" % (core.MARK, run_id, str(reason)[:700]))
    raise core.PlanError(reason)


def guard_start(ops, core, run_id):
    try:
        ops.guard_context()
    except core.PlanError as exc:
        stop(ops, core, run_id, str(exc))
    census = ops.census()
    if census != CLEAN:
        stop(ops, core, run_id, "DIRTY_CENSUS %s" % json.dumps(census))
    if ops.zz_actors():
        stop(ops, core, run_id, "ZZ_OR_TEMP_ACTORS %s" % ops.zz_actors())


class FacingOps:
    """Composition over rzswap.UnrealOps; adds a facing-policy-only write."""
    def __init__(self, base, core):
        self.base, self.core = base, core

    def __getattr__(self, name):
        return getattr(self.base, name)

    def write_top_policies(self, policies):
        show = self.base._show()
        self.base._pristine = list(show.get_editor_property("cues"))
        work = list(show.get_editor_property("cues"))
        index = {self.base._guid(c.get_editor_property("cue_guid")): i for i, c in enumerate(work)}
        enum_values = {
            self.core.AUTO: unreal.InfinityPanelFacingPolicy.AUTO_BY_ROLE,
            self.core.ROTATE: unreal.InfinityPanelFacingPolicy.ROTATE180_AROUND_UP,
        }
        for key, policy in sorted(policies.items()):
            cue_guid, side = key.split("|")
            if side != "T" or cue_guid not in index:
                raise self.core.PlanError("NON_P02_TOP_TARGET %s" % key)
            cue = work[index[cue_guid]]
            pair = cue.get_editor_property("wing_pair")
            panel = pair.get_editor_property("top")
            panel.set_editor_property("facing_policy", enum_values[policy])
            pair.set_editor_property("top", panel)
            cue.set_editor_property("wing_pair", pair)
        if len(work) != len(self.base._pristine):
            raise self.core.PlanError("CUE_COUNT_WOULD_CHANGE")
        show.modify()
        show.set_editor_property("cues", work)


def _expected_panel(panel, core, policy):
    result = copy.deepcopy(panel)
    result["facing_policy"] = policy
    return result


def _panel_bad(core, got, expected, key):
    if got is None:
        return "PANEL_MISSING %s" % key
    for field in ("mesh", "material_overrides", "local_transform", "flip_image_horizontally"):
        if got.get(field) != expected.get(field):
            return "PANEL_FIELD_CHANGED %s %s" % (key, field)
    if core.policy_name(got.get("facing_policy")) != core.policy_name(expected.get("facing_policy")):
        return "PANEL_POLICY_WRONG %s %s" % (key, got.get("facing_policy"))
    return None


def _target_indexes(dry):
    return {int(target["show_index"]) for target in dry["targets"]}


def _current_target_indexes(tc, cue_texts, keys):
    wanted = {key.split("|")[0] for key in keys}
    found = {}
    for index, cue_text in enumerate(cue_texts):
        guid = str(tc.get_field(cue_text, "CueGuid")).replace("-", "").upper()
        if guid in wanted:
            found[guid] = index
    missing = sorted(wanted - set(found))
    if missing:
        raise ValueError("TARGET_CUES_MISSING %s" % missing[:4])
    return set(found.values())


def run_dry(ops, core, run_id, here):
    guard_start(ops, core, run_id)
    measurement = ops.measure(core.PASSAGE, {})
    doc = core.make_dry(measurement, run_id)
    if ops.census() != CLEAN:
        stop(ops, core, run_id, "DRY_DIRTIED_SOMETHING %s" % json.dumps(ops.census()))
    doc["made"] = datetime.datetime.now().isoformat(timespec="seconds")
    path = os.path.join(here, "p02_top_facing_dry_%s.json" % run_id)
    _write(path, doc)
    _write(os.path.join(here, "p02_top_facing_dry_LATEST.json"), doc)
    ops.log("%s_DRY_OK|run=%s|passage=P02|tops=23|before=front_gt_back|after_expected=front_lt_back|state=%s|next_confirm=%s" %
            (core.MARK, run_id, doc["hash8"], core.confirm_for("APPLY", dry=doc)))
    return doc


def run_apply(ops, core, tc, args, dry, run_id, here):
    guard_start(ops, core, run_id)
    if os.path.exists(active_path(here)):
        stop(ops, core, run_id, "UNREVERTED_APPLY_EXISTS")
    measurement = ops.measure(core.PASSAGE, {})
    fresh = core.make_dry(measurement, "FRESH-BEFORE-APPLY")
    if fresh["state_hash"] != dry["state_hash"]:
        stop(ops, core, run_id, "DRY_STALE re-run DRY")
    keys = [target["key"] for target in dry["targets"]]
    before_panels = ops.live_panels(keys)
    before_texts = ops.cue_texts()
    settings_before = ops.settings_texts()
    segments_before = ops.segments()
    count_before = ops.materialized_count(core.PASSAGE)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    backup_dir, backup_files = ops.backup("PreP02TopFacing-%s" % stamp)
    originals_path = os.path.join(here, "p02_top_facing_originals_%s.json" % run_id)
    if os.path.exists(originals_path):
        stop(ops, core, run_id, "ORIGINALS_EXIST %s" % originals_path)
    originals = {
        "run_id": run_id, "passage": core.PASSAGE, "made": datetime.datetime.now().isoformat(timespec="seconds"),
        "decided_by": args.get("decided_by"), "dry_run_id": dry["run_id"], "dry_state_hash": dry["state_hash"],
        "backup_dir": backup_dir, "backup_files": backup_files, "targets": [
            {**target, "original_panel": before_panels[target["key"]],
             "written_panel": _expected_panel(before_panels[target["key"]], core, core.ROTATE)}
            for target in dry["targets"]
        ],
        "all_cue_texts": before_texts, "settings_texts": settings_before,
    }
    _write(originals_path, originals, fsync=True)
    _write(active_path(here), {"run_id": run_id, "originals": originals_path}, fsync=True)
    ops.log("%s_ORIGINALS|run=%s|path=%s|backup=%s" % (core.MARK, run_id, originals_path, backup_dir))

    def rollback(reason):
        try:
            restored = ops.restore_pristine() and ops.cue_texts() == before_texts
            if restored:
                restored = bool(ops.materialize(core.PASSAGE))
        except Exception as exc:  # noqa: BLE001
            restored = "RAISED %s" % exc
        retired = False
        if restored is True:
            failed_originals = originals_path.replace(".json", "_failed_before_save.json")
            failed_active = os.path.join(here, "p02_top_facing_ACTIVE_failed_%s.json" % run_id)
            os.replace(originals_path, failed_originals)
            os.replace(active_path(here), failed_active)
            retired = True
        stop(ops, core, run_id, "%s | in-memory restore=%s | NOTHING SAVED | failed records retired=%s" %
             (reason, restored, retired))

    try:
        ops.write_top_policies({key: core.ROTATE for key in keys})
        after_texts = ops.cue_texts()
        bad = core.verify_facing_only_texts(tc, before_texts, after_texts, _target_indexes(dry))
        live = ops.live_panels(keys)
        for target in originals["targets"]:
            problem = _panel_bad(core, live.get(target["key"]), target["written_panel"], target["key"])
            if problem:
                bad.append(problem)
        if ops.settings_texts() != settings_before:
            bad.append("PASSAGE_SETTINGS_CHANGED")
        if ops.segments() != segments_before:
            bad.append("COMPILED_SEGMENTS_CHANGED")
        if bad:
            rollback("FACING_ONLY_READBACK %s" % bad[:6])
        if not ops.materialize(core.PASSAGE):
            rollback("MATERIALIZE_FAILED")
        if ops.materialized_count(core.PASSAGE) != count_before:
            rollback("MATERIALIZED_COUNT_CHANGED")
        after_measure = ops.measure(core.PASSAGE, {})
        facing_probe, sign_bad = core.sign_readback(after_measure["rows"], -1)
        if sign_bad:
            rollback("FACING_SIGN_READBACK %s" % sign_bad[:6])
    except core.PlanError:
        raise
    except Exception as exc:  # noqa: BLE001
        rollback("WRITE_OR_READBACK_RAISED %s" % exc)
    census = ops.census()
    if not set(census["content"]) <= {core.SHOW_PATH} or not set(census["maps"]) <= {core.WORLD_PATH} or \
            core.SHOW_PATH not in census["content"]:
        rollback("DIRTY_SCOPE %s" % json.dumps(census))
    if ops.zz_actors():
        rollback("ZZ_ACTORS_APPEARED")
    if not ops.save_show():
        stop(ops, core, run_id, "SHOW_SAVE_FALSE; run REVERT after recovery")
    if not ops.save_level():
        stop(ops, core, run_id, "LEVEL_SAVE_FALSE; Show saved, run REVERT")
    if ops.census() != CLEAN:
        stop(ops, core, run_id, "DIRTY_AFTER_SAVE %s" % json.dumps(ops.census()))
    if ops.cue_texts() != after_texts:
        stop(ops, core, run_id, "POST_SAVE_TEXT_READBACK_DIFFERS")
    saved_measure = ops.measure(core.PASSAGE, {})
    saved_probe, saved_bad = core.sign_readback(saved_measure["rows"], -1)
    if saved_bad:
        stop(ops, core, run_id, "POST_SAVE_FACING_SIGN %s" % saved_bad[:6])
    record = {
        "run_id": run_id, "mode": "APPLY", "status": "PASS", "passage": core.PASSAGE,
        "originals": originals_path, "backup_dir": backup_dir, "dry_run_id": dry["run_id"],
        "written_field": "WingPair.Top.FacingPolicy", "written_count": len(keys),
        "written": {key: core.ROTATE for key in keys}, "image_flip_written": False,
        "local_transform_written": False, "facing_probe_after_materialize": facing_probe,
        "facing_probe_after_save": saved_probe, "saved": [core.SHOW_PATH, core.WORLD_PATH], "census_after": CLEAN,
        "decided_by": args.get("decided_by"),
    }
    _write(os.path.join(here, "p02_top_facing_apply_%s.json" % run_id), record, fsync=True)
    ops.log("%s_APPLY_OK|run=%s|passage=P02|tops=23|field=FacingPolicy|image_flip=false|materialized=P02|saved=show,level|readback=23/23_front_lt_back|census=clean" %
            (core.MARK, run_id))
    return record


def run_revert(ops, core, tc, args, originals, run_id, here):
    guard_start(ops, core, run_id)
    apply_path = os.path.join(here, "p02_top_facing_apply_%s.json" % originals["run_id"])
    applied = _read(apply_path)
    if not applied:
        stop(ops, core, run_id, "APPLY_RECORD_MISSING %s" % apply_path)
    keys = [target["key"] for target in originals["targets"]]
    live = ops.live_panels(keys)
    drift = [key for key in keys if core.policy_name(live.get(key, {}).get("facing_policy")) != core.ROTATE]
    if drift:
        stop(ops, core, run_id, "DRIFT_SINCE_APPLY %s" % drift[:4])
    before_texts = ops.cue_texts()
    settings_before = ops.settings_texts()
    segments_before = ops.segments()
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    backup_dir, _ = ops.backup("PreP02TopFacingRevert-%s" % stamp)
    try:
        indexes = _current_target_indexes(tc, before_texts, keys)
    except ValueError as exc:
        stop(ops, core, run_id, str(exc))
    try:
        ops.write_top_policies({target["key"]: core.policy_name(target["original_panel"]["facing_policy"])
                                for target in originals["targets"]})
        after_texts = ops.cue_texts()
        bad = core.verify_facing_only_texts(tc, before_texts, after_texts, indexes)
        now = ops.live_panels(keys)
        for target in originals["targets"]:
            problem = _panel_bad(core, now.get(target["key"]), target["original_panel"], target["key"])
            if problem:
                bad.append(problem)
        if ops.settings_texts() != settings_before:
            bad.append("PASSAGE_SETTINGS_CHANGED")
        if ops.segments() != segments_before:
            bad.append("COMPILED_SEGMENTS_CHANGED")
        if bad:
            raise core.PlanError("REVERT_READBACK %s" % bad[:6])
        if not ops.materialize(core.PASSAGE):
            raise core.PlanError("REVERT_MATERIALIZE_FAILED")
        reverted_measure = ops.measure(core.PASSAGE, {})
        facing_probe, sign_bad = core.sign_readback(reverted_measure["rows"], 1)
        if sign_bad:
            raise core.PlanError("REVERT_FACING_SIGN %s" % sign_bad[:6])
    except Exception as exc:  # noqa: BLE001
        restored = ops.restore_pristine() and ops.cue_texts() == before_texts
        if restored:
            restored = bool(ops.materialize(core.PASSAGE))
        stop(ops, core, run_id, "%s | in-memory restore=%s | NOTHING SAVED" % (exc, restored))
    census = ops.census()
    if not set(census["content"]) <= {core.SHOW_PATH} or not set(census["maps"]) <= {core.WORLD_PATH}:
        stop(ops, core, run_id, "REVERT_DIRTY_SCOPE %s" % json.dumps(census))
    if not ops.save_show() or not ops.save_level():
        stop(ops, core, run_id, "REVERT_SAVE_FALSE")
    if ops.census() != CLEAN:
        stop(ops, core, run_id, "REVERT_DIRTY_AFTER_SAVE")
    saved_measure = ops.measure(core.PASSAGE, {})
    saved_probe, saved_bad = core.sign_readback(saved_measure["rows"], 1)
    if saved_bad:
        stop(ops, core, run_id, "REVERT_POST_SAVE_FACING_SIGN %s" % saved_bad[:6])
    record = {"run_id": run_id, "mode": "REVERT", "status": "PASS", "reverted": originals["run_id"],
              "backup_dir": backup_dir, "written_field": "WingPair.Top.FacingPolicy", "written_count": len(keys),
              "facing_probe_after_materialize": facing_probe, "facing_probe_after_save": saved_probe,
              "saved": [core.SHOW_PATH, core.WORLD_PATH], "census_after": CLEAN}
    _write(os.path.join(here, "p02_top_facing_revert_%s.json" % run_id), record, fsync=True)
    os.replace(originals["_path"], originals["_path"].replace(".json", "_reverted.json"))
    os.replace(active_path(here), os.path.join(here, "p02_top_facing_ACTIVE_reverted_%s.json" % run_id))
    ops.log("%s_REVERT_OK|run=%s|passage=P02|reverted=%s|tops=23|materialized=P02|saved=show,level|readback=23/23_front_gt_back|census=clean" %
            (core.MARK, run_id, originals["run_id"]))
    return record


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    core = _load("p02_top_facing_core_live", os.path.join(here, "p02_top_facing_core.py"))
    rzswap_dir = os.path.normpath(os.path.join(here, "..", "rzswap"))
    rzswap = _load("rzswap_for_p02_top_facing", os.path.join(rzswap_dir, "rzswap.py"))
    tc = _load("topple_core_for_p02_top_facing", os.path.normpath(os.path.join(here, "..", "topple", "topple_core.py")))
    base = rzswap.UnrealOps(core, tc, rzswap_dir)
    ops = FacingOps(base, core)
    run_id = datetime.datetime.now().strftime("P02TF-%Y%m%d-%H%M%S")
    args = _read(os.path.join(here, ARGS_NAME), {})
    mode = str(args.get("mode") or "").upper()
    dry = _read(os.path.join(here, args.get("dry_record") or "p02_top_facing_dry_LATEST.json")) if mode == "APPLY" else None
    originals = None
    if mode == "REVERT":
        active = _read(active_path(here))
        core.require(active, "NO_ACTIVE_APPLY")
        originals = _read(active["originals"])
        core.require(originals, "ORIGINALS_MISSING")
        originals["_path"] = active["originals"]
    try:
        core.validate_args(args, dry, originals)
        if mode == "DRY":
            run_dry(ops, core, run_id, here)
        elif mode == "APPLY":
            run_apply(ops, core, tc, args, dry, run_id, here)
        else:
            run_revert(ops, core, tc, args, originals, run_id, here)
    except core.PlanError:
        raise
    except Exception as exc:  # noqa: BLE001
        stop(ops, core, run_id, "UNEXPECTED %s: %s" % (type(exc).__name__, exc))


if unreal is not None:
    main()
