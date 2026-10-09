"""P87 transactional orchestrator: DRY/APPLY/REVERT.

The Unreal-facing implementation is injected as ``P87_BACKEND`` by
``p87_opening_run.py``.  Keeping orchestration independent lets the offline
harness exercise the same confirm, record, drift, save and read-back gates.
"""
from __future__ import annotations

import copy
import datetime
import json
import os
import tempfile

from p87_opening_common import (CONFIRM, P87Error, apply_model, build_plan,
                                canonical, digest, merge_args, preflight,
                                revert_model)

MARK = "P87_OPENING_FIXES"
HERE = os.path.dirname(os.path.abspath(__file__))
RECORD = os.path.join(HERE, "p87_opening_record.json")


def write_json(path, value, exclusive=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if exclusive:
        with open(path, "x", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.flush(); os.fsync(handle.fileno())
        return
    fd, tmp = tempfile.mkstemp(prefix=".p87-", suffix=".json", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def load_json(path):
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _run_id(value=None):
    return str(value or datetime.datetime.now().strftime("P87-%Y%m%d-%H%M%S"))


def run(raw, backend, record_path=RECORD, output_dir=HERE):
    mode = str(raw.get("mode", "DRY")).upper()
    confirm = str(raw.get("confirm", ""))
    run_id = _run_id(raw.get("run_id"))
    args = merge_args(raw.get("args"), require_flurry=(mode == "APPLY"))
    active = load_json(record_path)
    context = backend.context()
    failures = preflight(mode, confirm, context, active, args["parts"])
    if failures:
        raise P87Error("PREFLIGHT|" + ";".join(failures))

    before = backend.snapshot(args["parts"])
    report = {"schema": 1, "mode": mode, "run": run_id, "parts": args["parts"],
              "mutated": False, "census_before": context["dirty"]}
    if mode == "DRY":
        plan = build_plan(args, before["live"])
        report.update({"plan": plan, "plan_sha256": plan["plan_sha256"],
                       "apply_ready": args["first_flurry_frame"] is not None,
                       "clock_status": before["live"]["clock"],
                       "foreign_records": backend.foreign_records(args["parts"]),
                       "previews": backend.previews(plan, run_id)})
        if backend.context()["dirty"] != {"content": [], "maps": []}:
            raise P87Error("DRY_DIRTIED_EDITOR")
        path = os.path.join(output_dir, "p87_opening_DRY_%s.json" % run_id)
        write_json(path, report)
        line = "%s_DRY_OK|run=%s|mutated=0|apply_ready=%d|clock=%s|plan=%s|report=%s" % (
            MARK, run_id, int(report["apply_ready"]), before["live"]["clock"]["status"],
            plan["plan_sha256"][:16], path)
        backend.log(line)
        return report, line

    if mode == "APPLY":
        foreign = backend.foreign_records(args["parts"])
        unacked = sorted(set(os.path.normcase(os.path.abspath(v)) for v in foreign) - set(args["ack_records"]))
        if unacked:
            raise P87Error("FOREIGN_ACTIVE_RECORDS|" + canonical(unacked))
        plan = build_plan(args, before["live"])
        backup = backend.backup("PreP87OpeningFixes-" + run_id, before["packages"])
        record = {"schema": 1, "status": "prepared", "run": run_id, "parts": args["parts"],
                  "args": args, "plan": plan, "plan_sha256": plan["plan_sha256"],
                  "before": before["owned"], "before_sha256": digest(before["owned"]),
                  "packages": before["packages"], "backup": backup,
                  "acknowledged_records": args["ack_records"]}
        write_json(record_path, record, exclusive=True)  # before first mutation
        try:
            backend.apply(plan)
            after = backend.owned_state(args["parts"])
            record.update({"status": "mutated_verified_presave", "after": after,
                           "after_sha256": digest(after)})
            write_json(record_path, record)
            backend.assert_plan(after, plan)
        except Exception:
            backend.restore(before["owned"])
            record["status"] = "failed_rolled_back_in_memory"
            write_json(record_path, record)
            raise
        backend.save_named(before["packages"])
        readback = backend.readback(args["parts"])
        backend.assert_equivalent(readback, record["after"])
        final_census = backend.context()["dirty"]
        if final_census != {"content": [], "maps": []}:
            raise P87Error("DIRTY_AFTER_SAVE|" + canonical(final_census))
        record.update({"status": "saved_readback_verified", "readback": readback,
                       "census_after": final_census})
        write_json(record_path, record)
        report.update({"mutated": True, "saved": before["packages"], "backup": backup,
                       "record": record_path, "readback": True})
        path = os.path.join(output_dir, "p87_opening_APPLY_%s.json" % run_id)
        write_json(path, report)
        line = "%s_APPLY_OK|run=%s|parts=%s|saved=%d|readback=1|dirty_final=0|record=%s|report=%s" % (
            MARK, run_id, ",".join(args["parts"]), len(before["packages"]), record_path, path)
        backend.log(line)
        return report, line

    # REVERT
    if not active:
        raise P87Error("REVERT_RECORD_ABSENT")
    current = backend.owned_state(args["parts"])
    restored = revert_model(current, active)  # refuses drift before backup/write
    backup = backend.backup("PreP87OpeningFixesRevert-" + run_id, active["packages"])
    backend.restore(restored)
    backend.save_named(active["packages"])
    readback = backend.readback(args["parts"])
    backend.assert_equivalent(readback, active["before"])
    final_census = backend.context()["dirty"]
    if final_census != {"content": [], "maps": []}:
        raise P87Error("REVERT_DIRTY_AFTER_SAVE|" + canonical(final_census))
    archived = record_path + ".reverted-" + run_id
    active.update({"status": "reverted", "revert_run": run_id, "revert_backup": backup,
                   "revert_readback": readback})
    write_json(record_path, active)
    os.replace(record_path, archived)
    report.update({"mutated": True, "saved": active["packages"], "backup": backup,
                   "record_archived": archived, "readback": True})
    path = os.path.join(output_dir, "p87_opening_REVERT_%s.json" % run_id)
    write_json(path, report)
    line = "%s_REVERT_OK|run=%s|parts=%s|saved=%d|readback=1|dirty_final=0|record=%s|report=%s" % (
        MARK, run_id, ",".join(args["parts"]), len(active["packages"]), archived, path)
    backend.log(line)
    return report, line


def main():
    raw = globals().get("P87_REQUEST")
    backend = globals().get("P87_BACKEND")
    if not isinstance(raw, dict) or backend is None:
        raise P87Error("ENTRYPOINT|p87_opening_run.py must inject P87_REQUEST and P87_BACKEND")
    try:
        return run(copy.deepcopy(raw), backend)
    except Exception as error:
        run_id = _run_id(raw.get("run_id"))
        backend.log_error("%s_STOPPED|run=%s|%s:%s|NOTHING SAVED=%d" %
                          (MARK, run_id, type(error).__name__, error,
                           int(not getattr(backend, "saved", False))))
        raise
