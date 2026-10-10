import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "job127_p04_smoke_prop_hide.py")
spec = importlib.util.spec_from_file_location("job127_tested", PATH)
T = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = T
spec.loader.exec_module(T)

passed = 0
failed = 0
rows_out = []


def check(name, fn, positive=True, contains=None):
    global passed, failed
    try:
        value = fn()
        if not positive:
            raise AssertionError("negative control unexpectedly accepted")
        ok, detail = True, repr(value)
    except Exception as exc:
        ok = (not positive) and (contains is None or contains in str(exc))
        detail = repr(exc)
    if ok:
        passed += 1
    else:
        failed += 1
    rows_out.append({"name": name, "control": "+" if positive else "-", "passed": ok, "detail": detail})


TAG = "InfinityStage.Attachment.CDF8F937C64C300A9B8F3A99112AEAE0|1EF8837543EE305D494A26A4AC1DCE1E"
GOOD = [
    {"label": "FX SMOKE P04 B04 L", "class": T.TARGET_CLASS,
     "identity": ("A" * 32, "B" * 32), "apparatus_count": 1, "plume_count": 1},
    {"label": "FX SMOKE P04 B11 R", "class": T.TARGET_CLASS,
     "identity": ("C" * 32, "D" * 32), "apparatus_count": 1, "plume_count": 1},
    {"label": T.TARGET_LABEL, "class": T.TARGET_CLASS,
     "identity": T.parse_identity_tag(TAG), "apparatus_count": 1, "plume_count": 1},
]

check("P.identity tag parses", lambda: T.parse_identity_tag(TAG) ==
      ("CDF8F937C64C300A9B8F3A99112AEAE0", "1EF8837543EE305D494A26A4AC1DCE1E"))
check("P.non identity ignored", lambda: T.parse_identity_tag("P04") is None)
check("P.bay ordinal", lambda: T.bay_ordinal(T.TARGET_LABEL) == 18)
check("P.unique latest near-final target", lambda: T.choose_candidate(GOOD, T.TARGET_LABEL, 21, 3)["label"])
check("P.confirm strings distinct", lambda: len(set(T.CONFIRMS.values())) == 3)
check("P.apply state is component-only hidden", lambda: {"visible": False, "hidden_in_game": True, "static_mesh": None})

check("P.bad identity syntax ignored", lambda: T.parse_identity_tag("InfinityStage.Attachment.bad|tag") is None)
check("N.missing target", lambda: T.choose_candidate(GOOD[:2], T.TARGET_LABEL, 21, 3), False, "TARGET_LABEL_COUNT")
check("N.duplicate target", lambda: T.choose_candidate(GOOD + [dict(GOOD[-1])], T.TARGET_LABEL, 21, 3), False,
      "DUPLICATE_P04_SMOKE_LABEL")
check("N.target not latest", lambda: T.choose_candidate(GOOD + [{"label": "FX SMOKE P04 B19 R", "class": T.TARGET_CLASS,
      "identity": ("E" * 32, "F" * 32), "apparatus_count": 1, "plume_count": 1}], T.TARGET_LABEL, 21, 3),
      False, "TARGET_NOT_LATEST_SMOKE")
check("N.too far from final", lambda: T.choose_candidate(GOOD, T.TARGET_LABEL, 22, 3), False, "FINAL_WING_GAP")
check("N.wrong class", lambda: T.choose_candidate(GOOD[:-1] + [dict(GOOD[-1], **{"class": "StaticMeshActor"})],
      T.TARGET_LABEL, 21, 3), False, "TARGET_CLASS")
check("N.identity missing", lambda: T.choose_candidate(GOOD[:-1] + [dict(GOOD[-1], **{"identity": None})],
      T.TARGET_LABEL, 21, 3), False, "TARGET_IDENTITY_TAG_MISSING")
check("N.stale identity reports rematerialize decision", lambda: T.choose_candidate(
      GOOD[:-1] + [dict(GOOD[-1], **{"identity": None, "expected_identity": ("A" * 32, "B" * 32),
                                    "all_identities": [("C" * 32, "D" * 32)]})],
      T.TARGET_LABEL, 21, 3), False, "TARGET_IDENTITY_TAG_MISMATCH")
check("N.no apparatus", lambda: T.choose_candidate(GOOD[:-1] + [dict(GOOD[-1], **{"apparatus_count": 0})],
      T.TARGET_LABEL, 21, 3), False, "APPARATUS_COUNT")
check("N.multiple apparatus", lambda: T.choose_candidate(GOOD[:-1] + [dict(GOOD[-1], **{"apparatus_count": 2})],
      T.TARGET_LABEL, 21, 3), False, "APPARATUS_COUNT")
check("N.no plume refuses destructive actor ambiguity", lambda: T.choose_candidate(
      GOOD[:-1] + [dict(GOOD[-1], **{"plume_count": 0})], T.TARGET_LABEL, 21, 3), False, "PLUME_COUNT")
check("N.label without bay", lambda: T.bay_ordinal("FX SMOKE P04 FINAL L"), False, "LABEL_HAS_NO_BAY")

source = open(PATH, encoding="utf-8").read()
check("P.source saves current level only", lambda: "save_current_level()" in source and "save_asset(SHOW" not in source)
check("P.source records before mutation", lambda: source.index("_write_json(record_path, record, True)") <
      source.index("_set_component(apparatus, False, True, None)"))
check("P.source preserves actor bHidden", lambda: "ACTOR_bHidden_CHANGED" in source and
      "set_actor_hidden_in_game" not in source)
check("P.source verifies plume unchanged", lambda: "PLUMEFX_CHANGED" in source and "plume_unchanged=1" in source)
check("P.source has backup before apply", lambda: source.index("backup = _backup(run, \"PreJ127SmokeProp\")") <
      source.index("_set_component(apparatus, False, True, None)"))
check("P.source clears mesh against BeginPlay reset", lambda: "ApplySettings reasserts Apparatus visibility" in source and
      '"static_mesh": None' in source)
check("P.success markers", lambda: all(x in source for x in ("_DRY_OK", "_APPLY_OK", "_REVERT_OK")))
request = __import__("json").load(open(os.path.join(HERE, "job127_request.json"), encoding="utf-8"))
check("P.guarded project-Python request", lambda:
      request["arguments"]["toolset_name"] == "MCPBlueprintsGenerator.MCPBlueprintsGeneratorToolset" and
      request["arguments"]["tool_name"] == "ExecuteProjectPythonFile" and
      request["arguments"]["arguments"]["relativeSavedPath"].startswith("CodexConductor/"))

result = {"passed": passed, "failed": failed, "total": passed + failed, "cases": rows_out}
with open(os.path.join(HERE, "harness_result.json"), "w", encoding="utf-8") as handle:
    import json
    json.dump(result, handle, indent=2)
print("JOB127_OFFLINE_HARNESS|passed=%d|failed=%d|total=%d" % (passed, failed, passed + failed))
if failed:
    for row in rows_out:
        if not row["passed"]:
            print("FAIL|%s|%s" % (row["name"], row["detail"]))
    raise SystemExit(1)
