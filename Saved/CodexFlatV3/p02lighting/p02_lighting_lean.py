"""Record-scoped lean pass for the P02 lights applied on 9/10 October 2026.

DRY/APPLY/REVERT only.  Attachment edits are restricted to the 414 GUIDs
minted by passage_lighting_record.json.  The separate car edit is restricted
to the exact actor recorded by p02_car_light_tune's applied record.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os

try:
    import unreal  # type: ignore
except ModuleNotFoundError:
    unreal = None

import _fx_authoring_common as C
import passage_lighting_as_source as P

HERE = (os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                     "CodexFlatV3", "p02lighting") if unreal is not None else os.path.dirname(__file__))
CONDUCTOR = (os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                          "CodexConductor") if unreal is not None else os.path.normpath(
                              os.path.join(HERE, "..", "..", "CodexConductor")))
ARGS_PATH = os.path.join(HERE, "p02_lighting_lean_args.json")
ORIGIN_PATH = os.path.join(HERE, "passage_lighting_record.json")
CAR_APPLIED_PATH = os.path.join(CONDUCTOR, "p02_car_light_tune_applied_P02CAR-TUNE-20261010-012009.json")
RECORD_PATH = os.path.join(HERE, "p02_lighting_lean_record.json")
MARK = "P02LIGHTLEAN"
HERO_ORDINALS = (3, 7, 12, 20)
DISABLE_ROLES = {"LOW_SIDE_R_FILL", "TOP_L", "TOP_R"}
DEFAULTS = {
    "mode": "DRY",
    "confirm": "",
    "expected_plan_sha256": "",
    "hero_ordinals": list(HERO_ORDINALS),
    "key_intensity_scale": 1.35,
    "key_radius_cap_cm": 1800.0,
    "car_radius_cm": 4600.0,
}


def require(value, message):
    if not value:
        raise RuntimeError(str(message))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def close(a, b, tolerance=1.0e-4):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= tolerance
    return a == b


def role(label):
    text = str(label)
    marker = " P01STRUCT B"
    if marker not in text:
        return text
    tail = text.split(marker, 1)[1]
    return tail.split(" ", 1)[1] if " " in tail else tail


def check_args(raw):
    unknown = set(raw) - set(DEFAULTS)
    require(not unknown, "ARGS_UNKNOWN|" + ",".join(sorted(unknown)))
    out = copy.deepcopy(DEFAULTS)
    out.update(raw)
    out["mode"] = str(out["mode"]).upper()
    require(out["mode"] in ("DRY", "APPLY", "REVERT"), "MODE_INVALID")
    require(out["hero_ordinals"] == sorted(set(int(x) for x in out["hero_ordinals"])),
            "HERO_ORDINALS_UNSORTED_OR_DUPLICATE")
    require(tuple(out["hero_ordinals"]) == HERO_ORDINALS, "HERO_ORDINALS_NOT_RECORDED_BEAMS")
    require(1.0 <= float(out["key_intensity_scale"]) <= 2.0, "KEY_SCALE_OUT_OF_RANGE")
    require(1200.0 <= float(out["key_radius_cap_cm"]) <= 2600.0, "KEY_RADIUS_OUT_OF_RANGE")
    require(4200.0 <= float(out["car_radius_cm"]) <= 5000.0, "CAR_RADIUS_NOT_LEAN_REACH")
    if out["mode"] != "DRY":
        want = "%s %s" % (out["mode"], MARK)
        require(out["confirm"] == want, "CONFIRM_MISSING|want=" + want)
    if out["mode"] == "APPLY":
        require(len(str(out["expected_plan_sha256"])) == 64, "EXPECTED_PLAN_SHA256_REQUIRED")
    return out


def origin_rows(record):
    require(record.get("status") == "saved_readback_verified", "ORIGIN_RECORD_NOT_READY")
    require(record.get("run") == "20261009-224343", "ORIGIN_RUN_DRIFT")
    require(record.get("args", {}).get("target_passage") == "P02", "ORIGIN_TARGET_NOT_P02")
    rows = []
    for target in record["plan"]["targets"]:
        added = {item["guid"] for item in target.get("added", [])}
        after = {item["guid"]: item for item in target.get("after_rows", [])}
        require(added <= set(after), "ORIGIN_ADDED_ROWS_MISSING|" + target["cue_guid"])
        for guid in sorted(added):
            rows.append((int(target["ordinal"]), target["cue_guid"], int(target["show_index"]), after[guid]))
    require(len(rows) == int(record.get("added_count", -1)) == 414, "ORIGIN_OWNED_COUNT_NOT_414")
    return rows


def validate_car_record(record):
    require(record.get("mode") == "APPLY" and record.get("mutated") is True, "CAR_RECORD_NOT_APPLIED")
    require(record.get("run") == "P02CAR-TUNE-20261010-012009", "CAR_RECORD_RUN_DRIFT")
    require(record.get("label") == "P02 Car Light (trial, Gary to tune)", "CAR_LABEL_DRIFT")
    values = record.get("values", {})
    require(close(values.get("attenuation_radius_cm"), 10000.0), "CAR_RECORD_RADIUS_NOT_10000")
    require(close(values.get("peak_intensity"), 9000.0), "CAR_RECORD_INTENSITY_DRIFT")
    require(close(values.get("outer_cone_degrees"), 28.0), "CAR_RECORD_CONE_DRIFT")
    return {"actor_path": record["actor_path"], "label": record["label"],
            "before_radius_cm": 10000.0}


def build_plan(origin, car_record, args):
    heroes = set(args["hero_ordinals"])
    changes = []
    for ordinal, cue_guid, show_index, baseline in origin_rows(origin):
        current = copy.deepcopy(baseline)
        r = role(baseline["label"])
        if r in DISABLE_ROLES or (r == "BEAM_R" and ordinal not in heroes):
            current["enabled"] = False
        lighting = current["lighting"]
        lighting["cast_shadows"] = bool(r == "LOW_SIDE_L_KEY" and ordinal in heroes)
        lighting["cast_volumetric_shadow"] = False
        if not (r == "BEAM_R" and ordinal in heroes):
            lighting["volumetric_scattering_intensity"] = 0.0
        if r == "LOW_SIDE_L_KEY":
            lighting["intensity"] = float(lighting["intensity"]) * float(args["key_intensity_scale"])
            lighting["attenuation_radius_cm"] = min(float(lighting["attenuation_radius_cm"]),
                                                     float(args["key_radius_cap_cm"]))
        before = {"enabled": bool(baseline["enabled"]), "lighting": {}}
        after = {"enabled": bool(current["enabled"]), "lighting": {}}
        for name in ("intensity", "attenuation_radius_cm", "cast_shadows",
                     "cast_volumetric_shadow", "volumetric_scattering_intensity"):
            if not close(baseline["lighting"].get(name), current["lighting"].get(name)):
                before["lighting"][name] = baseline["lighting"].get(name)
                after["lighting"][name] = current["lighting"].get(name)
        if before["enabled"] != after["enabled"] or before["lighting"]:
            changes.append({"ordinal": ordinal, "cue_guid": cue_guid, "show_index": show_index,
                            "guid": baseline["guid"], "label": baseline["label"], "role": r,
                            "before": before, "after": after})
    car = validate_car_record(car_record)
    car["after_radius_cm"] = float(args["car_radius_cm"])
    owned = origin_rows(origin)
    enabled_before = sum(bool(row[3]["enabled"]) for row in owned)
    enabled_after = enabled_before + sum(int(x["after"]["enabled"]) - int(x["before"]["enabled"])
                                         for x in changes)
    shadow_before = sum(bool(row[3]["lighting"]["cast_shadows"]) for row in owned)
    shadow_after = shadow_before + sum(
        int(x["after"]["lighting"].get("cast_shadows", x["before"]["lighting"].get("cast_shadows", False))) -
        int(x["before"]["lighting"].get("cast_shadows",
                                        x["after"]["lighting"].get("cast_shadows", False)))
        for x in changes if "cast_shadows" in x["after"]["lighting"])
    positive_volume_before = sum(bool(row[3]["enabled"]) and
                                 float(row[3]["lighting"]["volumetric_scattering_intensity"]) > 0.0
                                 for row in owned)
    state = {x["guid"]: x for x in changes}
    positive_volume_after = 0
    for _ordinal, _cue, _index, row in owned:
        item = state.get(row["guid"])
        enabled = item["after"]["enabled"] if item else bool(row["enabled"])
        scattering = (item["after"]["lighting"].get("volumetric_scattering_intensity",
                                                     row["lighting"]["volumetric_scattering_intensity"])
                      if item else row["lighting"]["volumetric_scattering_intensity"])
        positive_volume_after += bool(enabled and float(scattering) > 0.0)
    payload = {
        "origin_run": origin["run"], "hero_ordinals": list(args["hero_ordinals"]),
        "changes": changes, "car": car,
        "counts": {"owned": 414, "changed": len(changes),
                   "owned_enabled_before": enabled_before, "owned_enabled_after": enabled_after,
                   "owned_shadow_flags_before": shadow_before, "owned_shadow_flags_after": shadow_after,
                   "owned_positive_scatter_enabled_before": positive_volume_before,
                   "owned_positive_scatter_enabled_after": positive_volume_after},
    }
    payload["plan_sha256"] = hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()
    return payload


def report_path(mode, run_id):
    return os.path.join(HERE, "p02_lighting_lean_report_%s_%s.json" % (mode, run_id))


def live_rows(show, indexes):
    result = {}
    for index in sorted(set(indexes)):
        result[index] = {P._guid_text(a.get_editor_property("attachment_guid")): a
                         for a in P._pair_attachments(show, index)}
    return result


def nonowned_hash(show, plan):
    owned = {x["guid"] for x in plan["changes"]}
    indexes = {x["show_index"] for x in plan["changes"]}
    rows = []
    for index in sorted(indexes):
        for attachment in P._pair_attachments(show, index):
            state = P._full_attachment_state(attachment)
            if state["guid"] not in owned:
                rows.append([index, state])
    return hashlib.sha256(canonical(rows).encode("utf-8")).hexdigest()


def validate_live(show, plan, side):
    by_index = live_rows(show, [x["show_index"] for x in plan["changes"]])
    for item in plan["changes"]:
        require(item["guid"] in by_index[item["show_index"]], "OWNED_GUID_MISSING|" + item["guid"])
        got = P._full_attachment_state(by_index[item["show_index"]][item["guid"]])
        want = item[side]
        require(bool(got["enabled"]) == bool(want["enabled"]), "ENABLED_DRIFT|" + item["guid"])
        for name, expected in want["lighting"].items():
            require(close(got["lighting"].get(name), expected),
                    "LIGHTING_DRIFT|%s|%s|got=%s|want=%s" %
                    (item["guid"], name, got["lighting"].get(name), expected))


def mutate_rows(show, plan, side):
    indexes = sorted({x["show_index"] for x in plan["changes"]})
    attachments_by_index = {index: P._pair_attachments(show, index) for index in indexes}
    by_index = {
        index: {P._guid_text(a.get_editor_property("attachment_guid")): a for a in attachments}
        for index, attachments in attachments_by_index.items()
    }
    for item in plan["changes"]:
        attachment = by_index[item["show_index"]][item["guid"]]
        values = item[side]
        attachment.set_editor_property("enabled", values["enabled"])
        if values["lighting"]:
            lighting = attachment.get_editor_property("lighting")
            for name, value in values["lighting"].items():
                lighting.set_editor_property(name, value)
            attachment.set_editor_property("lighting", lighting)
    # UE nested structs are value-like.  Mutating an attachment proxy alone does
    # not serialize it into the Show; reassign the full attachments -> wing pair
    # -> cue -> cues chain through the proven helper.
    for index in indexes:
        P._set_pair_attachments(show, index, attachments_by_index[index])


def car_actor(plan):
    actors = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
              if a.get_path_name() == plan["car"]["actor_path"]]
    require(len(actors) == 1 and str(actors[0].get_actor_label()) == plan["car"]["label"],
            "CAR_ACTOR_IDENTITY|count=%d" % len(actors))
    require(actors[0].get_class().get_name() == "InfinityStageSweepLight", "CAR_CLASS_DRIFT")
    return actors[0]


def validate_car_live(plan, side):
    actor = car_actor(plan)
    key = "before_radius_cm" if side == "before" else "after_radius_cm"
    got = float(actor.get_editor_property("attenuation_radius_cm"))
    require(close(got, plan["car"][key]), "CAR_RADIUS_DRIFT|got=%s|want=%s" % (got, plan["car"][key]))


def mutate_car(plan, side):
    actor = car_actor(plan)
    key = "before_radius_cm" if side == "before" else "after_radius_cm"
    actor.modify()
    actor.set_editor_property("attenuation_radius_cm", plan["car"][key])


def run(raw):
    require(unreal is not None, "UNREAL_MODULE_REQUIRED")
    args = check_args(raw)
    run_id = C.stamp_now()
    report = {"ok": False, "run": run_id, "mode": args["mode"], "args": args}
    try:
        _editor, world = C.editor_context(unreal)
        dirty = C.require_clean(unreal, "PRE")
        show = unreal.EditorAssetLibrary.load_asset(C.SHOW_PATH)
        require(show is not None, "SHOW_LOAD_FAILED")
        if args["mode"] == "REVERT":
            require(os.path.isfile(RECORD_PATH), "LEAN_RECORD_MISSING")
            active = C.load_json(RECORD_PATH)
            require(active.get("status") == "saved_readback_verified", "LEAN_RECORD_NOT_READY")
            plan = active["plan"]
            validate_live(show, plan, "after")
            validate_car_live(plan, "after")
            backup = C.backup_packages(unreal, "PreP02LightingLeanRevert-", run_id,
                                       [C.SHOW_PATH, C.EXPECTED_WORLD])
            outside = nonowned_hash(show, plan)
            mutate_rows(show, plan, "before")
            mutate_car(plan, "before")
            require(nonowned_hash(show, plan) == outside, "NONOWNED_ROW_CHANGED")
        else:
            require(os.path.isfile(ORIGIN_PATH), "ORIGIN_RECORD_MISSING")
            require(os.path.isfile(CAR_APPLIED_PATH), "CAR_APPLIED_RECORD_MISSING")
            plan = build_plan(C.load_json(ORIGIN_PATH), C.load_json(CAR_APPLIED_PATH), args)
            validate_live(show, plan, "before")
            validate_car_live(plan, "before")
            report.update({"dirty_before": dirty, "plan": plan})
            if args["mode"] == "DRY":
                require(C.dirty_census(unreal) == dirty, "DRY_CHANGED_CENSUS")
                report.update({"ok": True, "mutated": False, "dirty_after": C.dirty_census(unreal)})
                C.write_json(report_path("DRY", run_id), report)
                unreal.log("%s_DRY_OK|run=%s|enabled=%d->%d|shadows=%d->%d|scatter=%d->%d|car=10000->%.0f|plan_sha256=%s|mutated=0" %
                           (MARK, run_id, plan["counts"]["owned_enabled_before"],
                            plan["counts"]["owned_enabled_after"],
                            plan["counts"]["owned_shadow_flags_before"],
                            plan["counts"]["owned_shadow_flags_after"],
                            plan["counts"]["owned_positive_scatter_enabled_before"],
                            plan["counts"]["owned_positive_scatter_enabled_after"],
                            plan["car"]["after_radius_cm"], plan["plan_sha256"]))
                return report
            require(args["expected_plan_sha256"] == plan["plan_sha256"], "PLAN_DRIFT")
            require(not os.path.exists(RECORD_PATH), "ACTIVE_LEAN_RECORD_EXISTS")
            backup = C.backup_packages(unreal, "PreP02LightingLean-", run_id,
                                       [C.SHOW_PATH, C.EXPECTED_WORLD])
            active = {"schema_version": 1, "status": "prepared_before_mutation", "run": run_id,
                      "args": args, "plan": plan, "backup": backup, "dirty_before": dirty,
                      "gpu_health_probe": P._gpu_log_cursor()}
            C.write_json(RECORD_PATH, active, exclusive=True)
            outside = nonowned_hash(show, plan)
            try:
                mutate_rows(show, plan, "after")
                mutate_car(plan, "after")
                validate_live(show, plan, "after")
                validate_car_live(plan, "after")
                require(nonowned_hash(show, plan) == outside, "NONOWNED_ROW_CHANGED")
            except Exception:
                mutate_rows(show, plan, "before")
                mutate_car(plan, "before")
                active["status"] = "failed_rolled_back_in_memory"
                C.write_json(RECORD_PATH, active)
                os.rename(RECORD_PATH, RECORD_PATH + ".failed-" + run_id)
                raise
        actor = P._passage_actor(show, 2)
        require(bool(actor.materialize_passage()), "P02_MATERIALIZE_FAILED")
        expected_dirty = {"content": [C.SHOW_PATH], "maps": [C.EXPECTED_WORLD]}
        require(C.dirty_census(unreal) == expected_dirty, "DIRTY_SCOPE|%s" % C.dirty_census(unreal))
        C.save_show_and_level(unreal)
        show_rb = unreal.EditorAssetLibrary.load_asset(C.SHOW_PATH)
        side = "before" if args["mode"] == "REVERT" else "after"
        validate_live(show_rb, plan, side)
        validate_car_live(plan, side)
        command = C.queue_saved_master_test(unreal, world, MARK, run_id)
        if args["mode"] == "REVERT":
            archived = C.archive_record(RECORD_PATH, run_id)
            report.update({"ok": True, "backup": backup, "record_archived": archived,
                           "dirty_after": C.dirty_census(unreal), "saved_master_command": command})
            C.write_json(report_path("REVERT", run_id), report)
            unreal.log("%s_REVERT_OK|run=%s|show_saved=1|level_saved=1|readback=1|saved_master=queued" %
                       (MARK, run_id))
        else:
            active.update({"status": "saved_readback_verified", "saved_census": C.dirty_census(unreal),
                           "next": "owned P02 PIE perf probe, then 30/60 percent stills"})
            C.write_json(RECORD_PATH, active)
            report.update({"ok": True, "backup": backup, "record": RECORD_PATH,
                           "dirty_after": C.dirty_census(unreal), "saved_master_command": command})
            C.write_json(report_path("APPLY", run_id), report)
            unreal.log("%s_APPLY_OK|run=%s|show_saved=1|level_saved=1|readback=1|saved_master=queued|perf=PENDING|stills=PENDING" %
                       (MARK, run_id))
        return report
    except Exception as error:
        report["error"] = "%s: %s" % (type(error).__name__, error)
        try:
            report["census_at_stop"] = C.dirty_census(unreal)
        except Exception:
            pass
        C.write_json(report_path(args["mode"] + "_STOPPED", run_id), report)
        unreal.log_error("%s_STOPPED|run=%s|mode=%s|%s|census=%s|if dirty: Don't-Save restart" %
                         (MARK, run_id, args["mode"], report["error"], report.get("census_at_stop")))
        raise


if unreal is not None and __name__ in ("__main__", "__p02_lighting_lean_runner__"):
    run(globals().get("P02_LIGHTING_LEAN_ARGS") or C.load_json(ARGS_PATH))
