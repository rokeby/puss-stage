"""Offline +/- harness for Job 121.  Does not import Unreal."""
from __future__ import annotations

import importlib.util
import inspect
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
RESULTS = []


def load():
    spec = importlib.util.spec_from_file_location("job121", HERE / "shroud_hessian_backface_fix.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


J = load()


def check(name, ok, detail=None):
    RESULTS.append({"check": name, "pass": bool(ok), "detail": detail})


def rejects(name, fn, token):
    try:
        fn()
        check(name, False, "accepted")
    except Exception as exc:
        check(name, token in str(exc), str(exc))


def args(mode):
    return {"mode": mode, "run": "JOB121-HARNESS-001", "compile_wait_seconds": 20.0,
            "confirm": J.CONFIRM.get(mode, "")}


def t_args():
    check("+ DRY accepted", J.parse_args(args("DRY"), False)["mode"] == "DRY")
    check("+ APPLY accepted with exact confirm", J.parse_args(args("APPLY"), False)["mode"] == "APPLY")
    check("+ REVERT accepted with active record", J.parse_args(args("REVERT"), True)["mode"] == "REVERT")
    bad = args("APPLY"); bad["confirm"] = "yes"
    rejects("- APPLY rejects wrong confirm", lambda: J.parse_args(bad, False), "CONFIRM")
    rejects("- APPLY rejects active record", lambda: J.parse_args(args("APPLY"), True), "ACTIVE_RECORD")
    rejects("- REVERT rejects missing record", lambda: J.parse_args(args("REVERT"), False), "NO_APPLY")
    bad = args("DRY"); bad["compile_wait_seconds"] = 1
    rejects("- compile wait cannot undercut async check", lambda: J.parse_args(bad, False), "COMPILE_WAIT")
    bad = args("DRY"); bad["run"] = "CONDUCTOR_SUPPLIES_RUN_ID"
    rejects("- placeholder run rejected", lambda: J.parse_args(bad, False), "PLACEHOLDER")


def t_log_gate():
    clean = ["LogMaterial: Display: Compiling M_Shroud_Hessian", "LogShaderCompilers: Display: done"]
    check("+ clean LogMaterial window passes", J.compile_log_errors(clean) == [])
    bad = clean + ["LogMaterial: Error: [SM6] M_Shroud_Hessian failed to compile"]
    check("- LogMaterial Error is caught", len(J.compile_log_errors(bad)) == 1)
    bad = clean + ["LogMaterial: Warning: Failed to compile Material M_Shroud_Hessian"]
    check("- failed-to-compile warning is caught", len(J.compile_log_errors(bad)) == 1)
    other = clean + ["LogPython: Error: unrelated transport error"]
    check("+ unrelated log category is not a material compile failure", J.compile_log_errors(other) == [])


def sample_state(terminal_class="MaterialExpressionCustom", skeletal=True, clothing=True):
    return {"flags": {"two_sided": True, "used_with_clothing": clothing,
                      "used_with_skeletal_mesh": skeletal},
            "normal": {"terminal": {"name": "Flip", "class": terminal_class, "output": ""},
                       "upstream": [{"pin": "N", "name": "NormalOut", "class": "MaterialExpressionCustom"},
                                    {"pin": "TwoSided", "name": "Sign", "class": "MaterialExpressionTwoSidedSign"}]}}


def t_readback_gate():
    expected = {"flags": {"two_sided": True, "used_with_clothing": True, "used_with_skeletal_mesh": True},
                "terminal": {"class": "MaterialExpressionCustom"},
                "upstream": {"N": {"name": "NormalOut"},
                             "TwoSided": {"class": "MaterialExpressionTwoSidedSign"}}}
    check("+ expected terminal, flags and chain pass", J.state_problems(sample_state(), expected) == [])
    check("- skeletal false is caught", any(x.startswith("FLAG|used_with_skeletal_mesh")
          for x in J.state_problems(sample_state(skeletal=False), expected)))
    check("- clothing false is caught", any(x.startswith("FLAG|used_with_clothing")
          for x in J.state_problems(sample_state(clothing=False), expected)))
    bad = sample_state(); bad["normal"]["upstream"][1]["class"] = "MaterialExpressionConstant"
    check("- missing TwoSidedSign chain is caught", any(x.startswith("NORMAL_UPSTREAM|TwoSided.class")
          for x in J.state_problems(bad, expected)))


def t_static_safety():
    src = (HERE / "shroud_hessian_backface_fix.py").read_text(encoding="utf-8")
    builder = (HERE / "shroud_hessian_ue.py").read_text(encoding="utf-8")
    check("+ imports offline without unreal", "unreal" not in sys.modules)
    check("+ no material-expression deletion API", "delete_material_expression" not in src and
          "delete_all_material_expressions" not in src)
    check("+ no Save All API", "save_all" not in src.lower() and "save_dirty_packages" not in src)
    check("+ exact target is hard-coded", J.TARGET.endswith("/Materials/M_Shroud_Hessian"))
    apply_src, revert_src = inspect.getsource(J._apply), inspect.getsource(J._revert)
    check("+ APPLY record and backup precede modify",
          apply_src.index("write_json(RECORD") < apply_src.index("_backup(") < apply_src.index("mat.modify()"))
    check("+ REVERT backup precedes modify", revert_src.index("_backup(") < revert_src.index("mat.modify()"))
    check("+ only final Normal terminal is rewired", "connect_material_property(flip" in apply_src and
          "MP_NORMAL" in apply_src)
    check("+ REVERT reconnects recorded original", "_find_node(mat, rec[\"normal_original\"])" in revert_src and
          "connect_material_property(original" in revert_src)
    check("+ compile check precedes target save", apply_src.index("_compile_and_check") < apply_src.index("_save_only_target"))
    check("+ setter return values are not trusted",
          "require(mel.connect_material" not in apply_src and "require(mel.connect_material" not in revert_src)
    check("+ builder regeneration contains TwoSidedSign", "MaterialExpressionTwoSidedSign" in builder and
          'set_editor_property("used_with_skeletal_mesh", True)' in builder)


def main():
    for test in (t_args, t_log_gate, t_readback_gate, t_static_safety):
        try:
            test()
        except Exception as exc:
            check(test.__name__ + " crashed", False, repr(exc))
    failures = [x for x in RESULTS if not x["pass"]]
    out = {"checks": len(RESULTS), "passes": len(RESULTS) - len(failures), "fails": len(failures),
           "failures": failures, "results": RESULTS}
    (HERE / "test_shroud_hessian_backface_offline_report.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")
    for row in failures:
        print("FAIL", row["check"], row["detail"])
    print("JOB121_OFFLINE_%s|checks=%d|passes=%d|fails=%d" %
          ("OK" if not failures else "FAILED", len(RESULTS), len(RESULTS) - len(failures), len(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
