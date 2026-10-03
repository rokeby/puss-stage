"""SK apply: repoint one Passage's Front/Flap MIs to saved _o2 textures."""
import sys as _fv3_sys, os as _fv3_os
if __name__ == "__main__":
    _fv3_here = _fv3_os.path.dirname(_fv3_os.path.abspath(__file__))
    for _fv3_name, _fv3_mod in list(_fv3_sys.modules.items()):
        _fv3_file = getattr(_fv3_mod, "__file__", None) or ""
        if (_fv3_name != "__main__" and _fv3_file and
                _fv3_os.path.dirname(_fv3_os.path.abspath(_fv3_file)) == _fv3_here):
            del _fv3_sys.modules[_fv3_name]
    if _fv3_here not in _fv3_sys.path:
        _fv3_sys.path.insert(0, _fv3_here)

import json
import traceback

import unreal

import sk_common as c


def main(passage=None, config_path=None):
    cfg = c.config(config_path)
    if passage is None:
        raise RuntimeError("SK_APPLY_PASSAGE_REQUIRED")
    ordinal, _batch = c.batch(cfg, passage)
    rows = c.rows_for_passage(cfg, passage)
    run = cfg["apply_run_id"]
    changed = []
    saved = []
    revert_saved = []
    prior_passages = c.completed_passages_before(cfg, passage)
    prior_saved = sorted({
        row["mi"] for row in cfg["rows"] if row.get("passage") in prior_passages
    })
    report = {
        "status": "RUNNING", "run": run, "phase": "apply_batch",
        "passage": passage, "ordinal": ordinal,
    }
    final_status = "FAIL"
    try:
        c.assert_context(clean=True)
        log_checks = {
            "import_complete": c.require_marker(
                "FLATV3_SK_IMPORT_OK", cfg["import_run_id"]
            ),
            "apply_run_open": c.require_run_open(run),
            "current_batch_unused": c.require_token_unused(
                c.batch_success_token(run, passage)
            ),
        }
        if ordinal == 1:
            log_checks["apply_run_unused"] = c.require_run_unused(run)
        else:
            log_checks["prior_batches"] = {
                prior: c.require_batch_marker(run, prior) for prior in prior_passages
            }

        # Bound the working set before any texture or MI is loaded. UE 5.8 has
        # no supported Python getter for current D3D12 budget/usage.
        unreal.SystemLibrary.collect_garbage()
        gpu_guard = c.gpu_memory_guard()
        unreal.log(
            "FLATV3_SK_GPU_GUARD passage=%s run=%s available=false action=%s"
            % (passage, run, gpu_guard["action"])
        )

        texture_readback = {}
        for replacement, (original, kind) in sorted(
                c.planned_texture_pairs(rows).items()):
            texture_readback[replacement] = c.verify_texture_pair(
                original, replacement, kind
            )

        for row in rows:
            instance = c.load_asset(row["mi"], unreal.MaterialInstanceConstant)
            c.assert_mi(instance, row["old_textures"], row["mi"] + ":before")
            # Track before mutation so a mid-parameter failure is still reverted.
            changed.append((row, instance))
            c.set_mi_textures(instance, row["new_textures"])
            c.assert_mi(instance, row["new_textures"], row["mi"] + ":after")

        expected_dirty = sorted({row["mi"] for row in rows})
        actual_dirty = c.census()
        if actual_dirty["maps"] or actual_dirty["content"] != expected_dirty:
            raise RuntimeError(
                "SK_APPLY_DIRTY_SET_FAIL|passage=%s|expected=%s|actual=%s"
                % (passage, json.dumps(expected_dirty),
                   json.dumps(actual_dirty, sort_keys=True))
            )
        saved = c.save_exact(expected_dirty)
        if c.census() != c.CLEAN:
            raise RuntimeError(
                "SK_APPLY_DIRTY_AFTER_SAVE|passage=%s|census=%s"
                % (passage, json.dumps(c.census(), sort_keys=True))
            )

        # Read back the same in-memory MIs; referenced packages are never reloaded.
        fresh = {}
        for row in rows:
            instance = c.load_asset(row["mi"], unreal.MaterialInstanceConstant)
            fresh[row["mi"]] = c.assert_mi(
                instance, row["new_textures"], row["mi"] + ":fresh"
            )
        if c.census() != c.CLEAN:
            raise RuntimeError(
                "SK_APPLY_DIRTY_AFTER_FRESH_READBACK|passage=%s|census=%s"
                % (passage, json.dumps(c.census(), sort_keys=True))
            )

        next_stage = (cfg["apply_batches"][ordinal]["passage"]
                      if ordinal < len(cfg["apply_batches"]) else "verify")
        report.update({
            "status": "PASS", "log_checks": log_checks,
            "gpu_memory_guard": gpu_guard,
            "texture_pair_readback": texture_readback,
            "mi_readback_fresh": fresh, "saved_roots": saved,
            "census": c.census(), "next_required_stage": next_stage,
            "terminal": False,
        })
        path = c.write_report("sk_apply_%s_%s.json" % (run, passage), report)
        unreal.log(
            "FLATV3_SK_APPLY_BATCH_OK passage=%s run=%s mis=%d saved_count=%d "
            "report=%s next=%s terminal=false"
            % (passage, run, len(fresh), len(saved), path, next_stage)
        )
        if ordinal == len(cfg["apply_batches"]):
            all_saved = sorted({row["mi"] for row in cfg["rows"]})
            unreal.log(
                "FLATV3_SK_APPLY_OK run=%s batches=%d mis=%d saved_count=%d "
                "next=verify terminal=false"
                % (run, len(cfg["apply_batches"]), len(cfg["rows"]), len(all_saved))
            )
        final_status = "OK"
        return report
    except Exception as exc:
        reverted = []
        revert_failure = None
        try:
            for row, instance in reversed(changed):
                c.set_mi_textures(instance, row["old_textures"])
                c.assert_mi(
                    instance, row["old_textures"], row["mi"] + ":failure_revert"
                )
                reverted.append(row["mi"])
            if reverted:
                expected_revert_dirty = sorted(set(reverted))
                actual_revert_dirty = c.census()
                if actual_revert_dirty != {
                        "content": expected_revert_dirty, "maps": []}:
                    raise RuntimeError(
                        "SK_APPLY_REVERT_DIRTY_SET_FAIL|expected=%s|actual=%s"
                        % (json.dumps(expected_revert_dirty),
                           json.dumps(actual_revert_dirty, sort_keys=True))
                    )
                revert_saved = c.save_exact(expected_revert_dirty)
            if c.census() != c.CLEAN:
                raise RuntimeError(
                    "SK_APPLY_REVERT_DIRTY_AFTER|" + json.dumps(c.census())
                )
        except Exception as revert_exc:
            revert_failure = str(revert_exc)
        aggregate_saved = sorted(set(prior_saved + revert_saved))
        report.update({
            "status": "FAIL", "reason": str(exc),
            "traceback": traceback.format_exc(),
            "completed_passages_retained": prior_passages,
            "completed_saved_roots_retained": prior_saved,
            "current_batch_reverted": sorted(set(reverted)),
            "current_batch_revert_saved": revert_saved,
            "revert_failure": revert_failure,
            "saved_roots": aggregate_saved, "census": c.census(),
        })
        c.write_report("sk_apply_%s_%s_FAILURE.json" % (run, passage), report)
        final_status = "REVERT_FAIL" if revert_failure else "FAIL_REVERTED"
        raise
    finally:
        # Successful batches keep the run open for the next passage and verify.
        # A failed batch releases and leaves earlier saved passages intact.
        if final_status != "OK":
            c.release(run, final_status,
                      sorted(set(prior_saved + revert_saved)),
                      "apply_batch", report)


if __name__ == "__main__":
    main(globals().get("FLATV3_PASSAGE"), globals().get("FLATV3_CONFIG"))
