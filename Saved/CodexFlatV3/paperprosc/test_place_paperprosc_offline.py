"""Offline positive/negative harness for place_paperprosc.py; system Python, no Unreal."""
import ast
import copy
import importlib.util
import json
import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = []


def load_tool():
    path = os.path.join(HERE, "place_paperprosc.py")
    spec = importlib.util.spec_from_file_location("paperprosc_tool_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


T = load_tool()


def check(kind, name, condition, detail=""):
    row = {"kind": kind, "name": name, "pass": bool(condition), "detail": str(detail)[:500]}
    RESULTS.append(row)
    print("%s %s %s%s" % ("PASS" if condition else "FAIL", kind, name,
                           "" if condition else " | " + row["detail"]))


def expect_stop(name, function, token):
    try:
        function()
    except T.PlanError as exc:
        check("NEG", name, token in str(exc), exc)
        return
    check("NEG", name, False, "accepted invalid input")


def args(mode="DRY"):
    value = {"meshes": copy.deepcopy(T.MESH_DEFAULTS), "transforms": copy.deepcopy(T.DEFAULT_TRANSFORMS),
             "attach": T.DEFAULT_ATTACH, "parent_label": T.STRUCTURE_LABEL}
    value["mode"] = mode
    value["confirm"] = "%s PAPERPROSC" % mode
    return value


def clean_state():
    return {"world": T.WORLD, "pie": False, "sequencer_open": False,
            "census": {"content": [], "maps": []},
            "label_counts": {label: 0 for label in T.LABELS.values()}, "parent_count": 1,
            "tag_count": 0, "record_exists": False}


def main():
    plan = T.validate_args(args())
    check("POS", "default plan has the exact three owned actors", [row["key"] for row in plan["rows"]] == list(T.PIECES))
    check("POS", "Hyper3D defaults reproduce measured thick5 stage bounds within 0.5 cm",
          not T.stage_bound_default_errors(plan), T.stage_bound_default_errors(plan))
    check("POS", "attach defaults on from measured stage-front precedent and uses KEEP_WORLD",
          plan["attachment"] == {"enabled": True, "parent_label": T.STRUCTURE_LABEL, "rule": "KEEP_WORLD"})
    check("POS", "default component policy is four exact materials per actor",
          all(len(row["materials"]) == 4 and row["materials"][3].endswith("_v3") for row in plan["rows"]))
    check("POS", "plan hash is deterministic", plan["hash"] == T.validate_args(args())["hash"])
    shifted = args(); shifted["transforms"]["valance"]["location_cm"][2] += 1.0
    check("POS", "transform args are load-bearing", T.validate_args(shifted)["hash"] != plan["hash"])
    check("POS", "clean DRY context with one attach parent passes",
          T.context_errors("DRY", clean_state(), attach=True) == [])
    applied = clean_state(); applied.update({"label_counts": {label: 1 for label in T.LABELS.values()},
                                             "tag_count": 3, "record_exists": True})
    check("POS", "exact owned state passes later VERIFY and REVERT guards",
          T.context_errors("VERIFY", applied) == [] and T.context_errors("REVERT", applied) == [])

    bad = args(); bad["confirm"] = "APPLY PAPERPROSC"
    expect_stop("confirm mismatch refuses", lambda: T.validate_args(bad), "CONFIRM_MISMATCH")
    bad = args(); bad["mode"] = "BUILD"; bad["confirm"] = "BUILD PAPERPROSC"
    expect_stop("unknown mode refuses", lambda: T.validate_args(bad), "MODE_INVALID")
    bad = args(); bad["transforms"]["side_l"]["location_cm"][0] = float("nan")
    expect_stop("non-finite transform refuses", lambda: T.validate_args(bad), "NONFINITE")
    bad = args(); bad["meshes"]["side_l"] = "/Game/Someone/Else"
    expect_stop("mesh outside owned import root refuses", lambda: T.validate_args(bad), "MESH_OUT_OF_SCOPE")

    state = clean_state(); state["parent_count"] = 0
    check("NEG", "attach refuses a missing Structure 01 parent",
          any("ATTACH_PARENT_NOT_EXACT" in row for row in T.context_errors("DRY", state, attach=True)))
    state = clean_state(); state["world"] = "/Game/Wrong"
    check("NEG", "wrong world refuses", any("WRONG_WORLD" in row for row in T.context_errors("DRY", state)))
    state = clean_state(); state["pie"] = True
    check("NEG", "PIE/SIE refuses", "PIE_OR_SIE_ACTIVE" in T.context_errors("DRY", state))
    state = clean_state(); state["census"]["maps"] = [T.WORLD]
    check("NEG", "dirty start refuses", any("DIRTY_AT_START" in row for row in T.context_errors("DRY", state)))
    state = clean_state(); state["census"]["maps"] = ["/Game/Klara/L_KK_Void"]
    check("NEG", "Klara protected level dirt is named and refused",
          any("KLARA_LEVEL_DIRTY" in row for row in T.context_errors("DRY", state)))
    state = clean_state(); state["label_counts"][T.LABELS["side_l"]] = 1
    check("NEG", "APPLY refuses a label collision", any("OWNED_ACTORS_ALREADY_EXIST" in row for row in T.context_errors("APPLY", state)))
    state = clean_state(); state["tag_count"] = 1
    check("NEG", "APPLY refuses an ownership-tag collision", any("OWNED_ACTORS_ALREADY_EXIST" in row for row in T.context_errors("APPLY", state)))
    state = clean_state(); state["record_exists"] = True
    check("NEG", "APPLY refuses an extant record", "APPLY_RECORD_ALREADY_EXISTS" in T.context_errors("APPLY", state))
    check("NEG", "REVERT refuses missing actors and record",
          any("OWNED_ACTORS_NOT_EXACT" in row for row in T.context_errors("REVERT", clean_state())) and
          "APPLY_RECORD_MISSING" in T.context_errors("REVERT", clean_state()))

    source_path = os.path.join(HERE, "place_paperprosc.py")
    source = open(source_path, encoding="utf-8").read()
    tree = ast.parse(source, feature_version=(3, 11))
    check("STATIC", "tool parses as Python 3.11", tree is not None)
    check("STATIC", "tool contains no Save All, level reload, or broad asset deletion",
          not any(token in source for token in ("save_dirty_packages", "save_all", "SaveAll", "load_map(",
                                                "delete_asset", "delete_directory")))
    check("STATIC", "NoCollision uses both required calls",
          'set_collision_profile_name("NoCollision")' in source and
          "set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)" in source)
    runner = open(os.path.join(HERE, "place_paperprosc_run.py"), encoding="utf-8").read()
    check("STATIC", "runner purges Saved module cache before the tool",
          runner.index("purge_saved_module_cache.py") < runner.rindex("place_paperprosc.py"))
    request = json.load(open(os.path.join(HERE, "place_paperprosc_request.json"), encoding="utf-8"))
    call = request["arguments"]
    check("STATIC", "request uses guarded project-Python MCP route and runner",
          call["toolset_name"] == "MCPBlueprintsGenerator.MCPBlueprintsGeneratorToolset" and
          call["tool_name"] == "ExecuteProjectPythonFile" and
          call["arguments"]["relativeSavedPath"] == "CodexFlatV3/paperprosc/place_paperprosc_run.py")

    report = {"checks": RESULTS, "passed": sum(row["pass"] for row in RESULTS),
              "failed": sum(not row["pass"] for row in RESULTS),
              "by_kind": {kind: sum(row["kind"] == kind for row in RESULTS) for kind in ("POS", "NEG", "STATIC")},
              "plan_hash": plan["hash"]}
    with open(os.path.join(HERE, "test_place_paperprosc_offline_report.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1)
    print("PAPERPROSC_HARNESS_RESULT|passed=%d|failed=%d|positive=%d|negative=%d|static=%d|plan=%s" %
          (report["passed"], report["failed"], report["by_kind"]["POS"], report["by_kind"]["NEG"],
           report["by_kind"]["STATIC"], plan["hash"][:8]))
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
