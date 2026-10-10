"""Job 179 P02 haze/beam trim through Show attachments.

DRY is read-only. APPLY/REVERT back up the Show and persistent level, change
only recorded attachment fields, materialize Passage 02, narrowly save, read
back, and emit run-id markers. No attachment or actor is deleted.
"""
from __future__ import annotations

import copy
import glob
import hashlib
import importlib.util
import json
import os

try:
    import unreal  # type: ignore
except ModuleNotFoundError:
    unreal = None


HERE = (os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                     "CodexFlatV3", "p02lighting") if unreal is not None else os.path.dirname(__file__))
ARGS_PATH = os.path.join(HERE, "p02_trim_args.json")
RECORD_PATH = os.path.join(HERE, "p02_trim_record.json")
MARK = "P02TRIM"
HERO_ORDINALS = (3, 7, 12, 20)
DEFAULTS = {
    "mode": "DRY",
    "confirm": "",
    "expected_plan_sha256": "",
    "expected_changes": None,
    "density_scale": 0.5,
    "hero_ordinals": list(HERO_ORDINALS),
    "hero_intensity_cap": 650.0,
    "hero_scatter_cap": 0.75,
    "beam_low_intensity": 50.0,
    "rig_low_intensity": 35.0,
    "rig_label_tokens": ["PRACTICAL", "PARCAN", "FIXTURE"],
}


def load_local(name):
    path = os.path.join(HERE, name + ".py")
    spec = importlib.util.spec_from_file_location("_p02trim_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


C = load_local("_fx_authoring_common")
P = load_local("passage_lighting_as_source")


def require(value, message):
    if not value:
        raise RuntimeError(str(message))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def close(a, b, tolerance=1.0e-4):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= tolerance
    return a == b


def enum_token(value):
    text = str(value).upper()
    for token in ("HAZE", "LIGHT", "EFFECT"):
        if token in text:
            return token
    return text


def check_args(raw):
    raw = dict(raw or {})
    require(not (set(raw) - set(DEFAULTS)), "ARGS_UNKNOWN|" + ",".join(sorted(set(raw) - set(DEFAULTS))))
    out = copy.deepcopy(DEFAULTS)
    out.update(copy.deepcopy(raw))
    out["mode"] = str(out["mode"]).upper()
    require(out["mode"] in ("DRY", "APPLY", "REVERT"), "MODE_INVALID")
    if out["mode"] != "DRY":
        require(out["confirm"] == "%s %s" % (out["mode"], MARK),
                "CONFIRM_MISSING|want=%s %s" % (out["mode"], MARK))
    if out["mode"] == "APPLY":
        require(isinstance(out["expected_changes"], int) and out["expected_changes"] >= 0,
                "EXPECTED_CHANGES_REQUIRED")
        require(len(str(out["expected_plan_sha256"])) == 64, "EXPECTED_PLAN_SHA256_REQUIRED")
    require(tuple(out["hero_ordinals"]) == HERO_ORDINALS, "HERO_ORDINALS_DRIFT")
    require(0.25 <= float(out["density_scale"]) <= 0.75, "DENSITY_SCALE_RANGE")
    for key in ("hero_intensity_cap", "hero_scatter_cap", "beam_low_intensity", "rig_low_intensity"):
        out[key] = float(out[key])
        require(out[key] >= 0.0, key.upper() + "_NEGATIVE")
    require(out["hero_intensity_cap"] > out["beam_low_intensity"], "HERO_NOT_ABOVE_LOW")
    require(out["rig_label_tokens"] and all(str(x).strip() for x in out["rig_label_tokens"]),
            "RIG_TOKENS_EMPTY")
    out["rig_label_tokens"] = sorted(set(str(x).upper() for x in out["rig_label_tokens"]))
    return out


def baseline_density_lookup(records):
    """Return GUID -> pre-copy density plus the record supplying it."""
    found = {}
    for path in records:
        try:
            record = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        if record.get("args", {}).get("target_passage") not in ("P02", "P2"):
            continue
        for target in record.get("plan", {}).get("targets", []):
            for row in target.get("before_rows", []):
                if enum_token(row.get("kind")) != "EFFECT":
                    continue
                effect = row.get("effect") or {}
                if "medium_density" in effect:
                    found.setdefault(row.get("guid"), {
                        "density": float(effect["medium_density"]), "record": path,
                        "record_run": record.get("run"),
                    })
    return found


def p02_rows(show):
    plain = P._plain_cues(show)
    rows, passage_guid = P._passage_rows(show, "Passage 2", plain)
    return rows, passage_guid


def build_plan(rows, args, baseline=None):
    baseline = baseline or {}
    changes = []
    density_report = []
    counts = {"attachments": 0, "lights": 0, "effects": 0, "beam_lights": 0,
              "hero_beams": 0, "zeroed_beams": 0, "low_rig_lights": 0,
              "haze_effects": 0, "attachments_enabled_before": 0,
              "attachments_enabled_after": 0}
    for ordinal, cue in enumerate(rows, 1):
        for row in cue["attachments"]:
            counts["attachments"] += 1
            counts["attachments_enabled_before"] += int(bool(row["enabled"]))
            counts["attachments_enabled_after"] += int(bool(row["enabled"]))
            kind = enum_token(row["kind"])
            before, after = {}, {}
            if kind == "EFFECT":
                counts["effects"] += 1
                effect = row.get("effect") or {}
                effect_type = enum_token(effect.get("type"))
                is_haze = effect_type == "HAZE" or any(x in row["label"].upper() for x in ("HAZE", "FOG", "ATMOS"))
                if is_haze and bool(effect.get("feeds_local_medium")):
                    current = float(effect.get("medium_density", 0.0))
                    half = current * float(args["density_scale"])
                    prior = baseline.get(row["guid"])
                    pre = None if prior is None else float(prior["density"])
                    target = half if pre is None else max(0.0, min(current, max(pre, half)))
                    counts["haze_effects"] += 1
                    density_report.append({"ordinal": ordinal, "cue_guid": cue["guid"], "guid": row["guid"],
                                           "label": row["label"], "current_density": current,
                                           "half_density": half, "pre_p01_copy_density": pre,
                                           "chosen_density": target,
                                           "baseline_record": None if prior is None else prior["record"],
                                           "baseline_run": None if prior is None else prior["record_run"]})
                    if not close(current, target):
                        before["effect"] = {"medium_density": current}
                        after["effect"] = {"medium_density": target}
            elif kind == "LIGHT":
                counts["lights"] += 1
                lighting = row["lighting"]
                label = row["label"].upper()
                is_beam = "BEAM" in label and float(lighting.get("volumetric_scattering_intensity", 0.0)) > 0.0
                is_rig = any(token in label for token in args["rig_label_tokens"])
                wanted = {}
                if is_beam:
                    counts["beam_lights"] += 1
                    if ordinal in set(args["hero_ordinals"]):
                        counts["hero_beams"] += 1
                        wanted = {
                            "intensity": min(float(lighting["intensity"]), args["hero_intensity_cap"]),
                            "volumetric_scattering_intensity": min(float(lighting["volumetric_scattering_intensity"]), args["hero_scatter_cap"]),
                        }
                    else:
                        counts["zeroed_beams"] += 1
                        wanted = {"intensity": min(float(lighting["intensity"]), args["beam_low_intensity"]),
                                  "volumetric_scattering_intensity": 0.0,
                                  "cast_shadows": False, "cast_volumetric_shadow": False}
                elif is_rig:
                    counts["low_rig_lights"] += 1
                    wanted = {"intensity": min(float(lighting["intensity"]), args["rig_low_intensity"]),
                              "volumetric_scattering_intensity": 0.0,
                              "cast_shadows": False, "cast_volumetric_shadow": False}
                for name, value in wanted.items():
                    if not close(lighting.get(name), value):
                        before.setdefault("lighting", {})[name] = lighting.get(name)
                        after.setdefault("lighting", {})[name] = value
            if before:
                changes.append({"ordinal": ordinal, "cue_guid": cue["guid"], "show_index": cue["show_index"],
                                "guid": row["guid"], "label": row["label"], "kind": kind,
                                "before": before, "after": after})
    require(counts["haze_effects"] > 0, "NO_P02_HAZE_EFFECT_ATTACHMENTS")
    require(counts["beam_lights"] > len(HERO_ORDINALS), "NOT_ENOUGH_VOLUMETRIC_BEAMS_TO_TRIM")
    payload = {"policy": "SHOW_ATTACHMENTS_ONLY_NO_DELETE", "hero_ordinals": list(args["hero_ordinals"]),
               "density_report": density_report, "counts": counts, "changes": changes}
    payload["plan_sha256"] = hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()
    return payload


def field_state(row, patch):
    out = {}
    if "lighting" in patch:
        out["lighting"] = {key: row["lighting"].get(key) for key in patch["lighting"]}
    if "effect" in patch:
        out["effect"] = {key: row["effect"].get(key) for key in patch["effect"]}
    return out


def live_state(show, plan):
    result = {}
    for index in sorted({x["show_index"] for x in plan["changes"]}):
        for attachment in P._pair_attachments(show, index):
            state = P._full_attachment_state(attachment)
            result[(index, state["guid"])] = state
    return result


def validate_live(show, plan, side):
    current = live_state(show, plan)
    for change in plan["changes"]:
        key = (change["show_index"], change["guid"])
        require(key in current, "ATTACHMENT_MISSING|" + change["guid"])
        got = field_state(current[key], change[side])
        require(not P.S.state_differences(change[side], got),
                "READBACK_DRIFT|%s|%s" % (change["guid"], canonical(P.S.state_differences(change[side], got))))


def outside_hash(show, plan):
    owned = {(x["show_index"], x["guid"]) for x in plan["changes"]}
    rows = []
    for cue in p02_rows(show)[0]:
        for attachment in cue["attachments"]:
            key = (cue["show_index"], attachment["guid"])
            if key not in owned:
                rows.append([cue["show_index"], attachment])
    return hashlib.sha256(canonical(rows).encode("utf-8")).hexdigest()


def mutate(show, plan, side):
    by_index = {}
    for change in plan["changes"]:
        by_index.setdefault(change["show_index"], []).append(change)
    for index, changes in sorted(by_index.items()):
        attachments = P._pair_attachments(show, index)
        by_guid = {P._guid_text(a.get_editor_property("attachment_guid")): a for a in attachments}
        for change in changes:
            attachment = by_guid[change["guid"]]
            values = change[side]
            if "lighting" in values:
                lighting = attachment.get_editor_property("lighting")
                for name, value in values["lighting"].items():
                    lighting.set_editor_property(name, value)
                attachment.set_editor_property("lighting", lighting)
            if "effect" in values:
                effect = attachment.get_editor_property("effect")
                for name, value in values["effect"].items():
                    effect.set_editor_property(name, value)
                attachment.set_editor_property("effect", effect)
        P._set_pair_attachments(show, index, attachments)


def evaluate_perf(before, after, max_regression=0.10):
    require(set(before) == set(after) and len(before) == 3, "P02_PERF_NEEDS_EXACTLY_THREE_MATCHED_SPOTS")
    rows = []
    for label in sorted(before):
        b, a = float(before[label]), float(after[label])
        require(b > 0.0 and a > 0.0, "P02_PERF_NONPOSITIVE|" + label)
        regression = (a - b) / b
        rows.append({"spot": label, "before_p95_ms": b, "after_p95_ms": a,
                     "regression_fraction": regression, "passes": regression <= max_regression})
    return {"pass": all(row["passes"] for row in rows), "auto_revert": False,
            "max_regression_fraction": max(row["regression_fraction"] for row in rows), "spots": rows}


def report_path(mode, run):
    return os.path.join(HERE, "p02_trim_report_%s_%s.json" % (mode, run))


def run(raw):
    require(unreal is not None, "UNREAL_MODULE_REQUIRED")
    args = check_args(raw)
    run_id = C.stamp_now()
    report = {"schema_version": 1, "ok": False, "mode": args["mode"], "run": run_id, "args": args}
    try:
        _editor, world = C.editor_context(unreal)
        dirty = C.require_clean(unreal, "PRE")
        show = unreal.EditorAssetLibrary.load_asset(C.SHOW_PATH)
        require(show is not None, "SHOW_LOAD_FAILED")
        if args["mode"] == "REVERT":
            require(os.path.isfile(RECORD_PATH), "TRIM_RECORD_MISSING")
            active = C.load_json(RECORD_PATH)
            require(active.get("status") == "saved_readback_verified", "TRIM_RECORD_NOT_READY")
            plan = active["plan"]
            validate_live(show, plan, "after")
            backup = C.backup_packages(unreal, "PreP02TrimRevert-", run_id, [C.SHOW_PATH, C.EXPECTED_WORLD])
            outside = outside_hash(show, plan)
            mutate(show, plan, "before")
            require(outside_hash(show, plan) == outside, "NONOWNED_ATTACHMENT_CHANGED")
        else:
            record_paths = sorted(glob.glob(os.path.join(HERE, "passage_lighting_record.json*")),
                                  key=lambda path: os.path.getmtime(path), reverse=True)
            rows, passage_guid = p02_rows(show)
            plan = build_plan(rows, args, baseline_density_lookup(record_paths))
            plan["passage_guid"] = passage_guid
            report.update({"dirty_before": dirty, "plan": plan, "baseline_records_searched": record_paths})
            if args["mode"] == "DRY":
                require(C.dirty_census(unreal) == dirty, "DRY_CHANGED_CENSUS")
                report.update({"ok": True, "mutated": False, "dirty_after": C.dirty_census(unreal)})
                C.write_json(report_path("DRY", run_id), report)
                c = plan["counts"]
                unreal.log("%s_DRY_OK|run=%s|changes=%d|haze=%d|beams=%d|hero=%d|zeroed=%d|rig_low=%d|attachments=%d->%d|plan_sha256=%s|mutated=0" %
                           (MARK, run_id, len(plan["changes"]), c["haze_effects"], c["beam_lights"],
                            c["hero_beams"], c["zeroed_beams"], c["low_rig_lights"],
                            c["attachments"], c["attachments"], plan["plan_sha256"]))
                return report
            require(args["expected_plan_sha256"] == plan["plan_sha256"], "PLAN_DRIFT")
            require(args["expected_changes"] == len(plan["changes"]), "EXPECTED_CHANGES_DRIFT")
            require(not os.path.exists(RECORD_PATH), "ACTIVE_TRIM_RECORD_EXISTS")
            validate_live(show, plan, "before")
            backup = C.backup_packages(unreal, "PreP02Trim-", run_id, [C.SHOW_PATH, C.EXPECTED_WORLD])
            active = {"schema_version": 1, "status": "prepared_before_mutation", "run": run_id,
                      "args": args, "plan": plan, "backup": backup, "dirty_before": dirty}
            C.write_json(RECORD_PATH, active, exclusive=True)
            outside = outside_hash(show, plan)
            try:
                mutate(show, plan, "after")
                validate_live(show, plan, "after")
                require(outside_hash(show, plan) == outside, "NONOWNED_ATTACHMENT_CHANGED")
            except Exception:
                mutate(show, plan, "before")
                active["status"] = "failed_rolled_back_in_memory"
                C.write_json(RECORD_PATH, active)
                os.rename(RECORD_PATH, RECORD_PATH + ".failed-" + run_id)
                raise
        actor = P._passage_actor(show, 2)
        require(bool(actor.materialize_passage()), "P02_MATERIALIZE_FAILED")
        require(C.dirty_census(unreal) == {"content": [C.SHOW_PATH], "maps": [C.EXPECTED_WORLD]},
                "DIRTY_SCOPE|" + canonical(C.dirty_census(unreal)))
        C.save_show_and_level(unreal)
        show_rb = unreal.EditorAssetLibrary.load_asset(C.SHOW_PATH)
        side = "before" if args["mode"] == "REVERT" else "after"
        validate_live(show_rb, plan, side)
        command = C.queue_saved_master_test(unreal, world, MARK, run_id)
        if args["mode"] == "REVERT":
            archived = C.archive_record(RECORD_PATH, run_id)
            report.update({"ok": True, "backup": backup, "record_archived": archived,
                           "dirty_after": C.dirty_census(unreal), "saved_master_command": command})
            C.write_json(report_path("REVERT", run_id), report)
            unreal.log("%s_REVERT_OK|run=%s|show_saved=1|level_saved=1|readback=1" % (MARK, run_id))
        else:
            active.update({"status": "saved_readback_verified", "saved_census": C.dirty_census(unreal),
                           "perf_gate": {"status": "PENDING", "spots": 3, "auto_revert": False}})
            C.write_json(RECORD_PATH, active)
            report.update({"ok": True, "backup": backup, "record": RECORD_PATH,
                           "dirty_after": C.dirty_census(unreal), "saved_master_command": command})
            C.write_json(report_path("APPLY", run_id), report)
            unreal.log("%s_APPLY_OK|run=%s|changes=%d|show_saved=1|level_saved=1|readback=1|perf=PENDING|auto_revert=0" %
                       (MARK, run_id, len(plan["changes"])))
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


if unreal is not None and __name__ in ("__main__", "__p02_trim_runner__"):
    run(C.load_json(ARGS_PATH))
