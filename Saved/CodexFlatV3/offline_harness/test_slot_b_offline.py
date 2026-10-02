"""Offline positive/negative proof harness for the real Slot B scripts."""
import importlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
SLOT = HERE.parent
RUN = "FV3B-20261002-03"
FORBIDDEN = (
    "save_asset", "save_current_level", "save_packages", "materialize_passage",
    "evaluate_mechanisms", "set_editor_property", ".modify(",
)

sys.path.insert(0, str(HERE))
import fake_unreal
sys.modules["unreal"] = fake_unreal


def load_named(name, path):
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


ORIGINALS = load_json(SLOT / ("slot_b_originals_%s.json" % RUN))
PLAN = load_json(SLOT / ("slot_b_dry_run_%s.json" % RUN))


def stage_artifacts(folder):
    for prefix in ("slot_b_originals_", "slot_b_dry_run_", "slot_b_apply_"):
        source = SLOT / (prefix + RUN + ".json")
        shutil.copyfile(source, Path(folder) / source.name)


def load_common(path, folder):
    common = load_named("slot_b_common", path)
    common.BASE = str(folder)
    return common


def last_release():
    matches = [line for line in fake_unreal.STATE.logs if line.startswith("FLATV3_SLOT_RELEASED")]
    if not matches:
        raise AssertionError("release marker missing")
    return matches[-1]


RESULTS = []


def record(name, polarity, expected, passed, detail):
    RESULTS.append({"name": name, "polarity": polarity, "expected": expected,
                    "passed": bool(passed), "detail": str(detail)})


def test_new_revert(folder):
    fake_unreal.reset(ORIGINALS, PLAN, "mutated")
    common = load_common(SLOT / "slot_b_common.py", folder)
    module = load_named("slot_b_revert_new_harness", SLOT / "slot_b_revert.py")
    module.c.BASE = str(folder)
    none_top = next(row["top"] for row in ORIGINALS["rows"] if row["top"]["mesh"] is None)
    probe = fake_unreal.Obj(mesh=fake_unreal.Asset("/Probe"), material_overrides=[],
                           local_transform=fake_unreal.Transform(), facing_policy="AUTO_BY_ROLE",
                           flip_image_horizontally=False)
    common.set_panel(probe, none_top)
    if probe.get_editor_property("mesh") is not None:
        raise AssertionError("None mesh was not restored explicitly")
    roots = module.revert("offline_positive")
    show = fake_unreal.STATE.assets[common.SHOW]
    cues = show.get_editor_property("cues")
    for row in ORIGINALS["rows"]:
        pair = cues[row["cue_index"]].get_editor_property("wing_pair")
        for side in ("left", "right", "top"):
            if common.panel_plain(pair.get_editor_property(side)) != row[side]:
                raise AssertionError("field mismatch %s %s" % (row["cue_label"], side))
        if common.mechanism_plain(pair.get_editor_property("mechanism")) != row["mechanism"]:
            raise AssertionError("mechanism mismatch " + row["cue_label"])
        if not common.close_transform(
                common.transform_plain(pair.get_editor_property("occurrence_offset")),
                row["occurrence_offset"]):
            raise AssertionError("offset mismatch " + row["cue_label"])
    if common.census() != {"content": [], "maps": []}:
        raise AssertionError("revert census not clean")
    if roots != sorted([common.SHOW, common.WORLD]):
        raise AssertionError("wrong saved roots")
    return "21 real rows restored; None mesh handled; 18 empty tops untouched"


def test_old_revert_fails(folder):
    fake_unreal.reset(ORIGINALS, PLAN, "mutated")
    load_common(HERE / "originals" / "slot_b_common.py", folder)
    real_reload = importlib.reload
    try:
        # Keep the OLD revert bound to the preserved OLD common despite its
        # module-level reload; otherwise Python resolves the production copy.
        importlib.reload = lambda module: module
        module = load_named("slot_b_revert_old_harness", HERE / "slot_b_revert_OLD.py")
    finally:
        importlib.reload = real_reload
    module.c.BASE = str(folder)
    try:
        module.revert("offline_negative")
    except TypeError as exc:
        if "NoneType" not in str(exc):
            raise
        return "FAIL (expected): %s" % exc
    raise AssertionError("old revert unexpectedly succeeded")


def test_verify_clean(folder):
    fake_unreal.reset(ORIGINALS, PLAN, "verify")
    load_common(SLOT / "slot_b_common.py", folder)
    verifier = load_named("slot_b_verify_harness", SLOT / "slot_b_verify.py")
    verifier.c.BASE = str(folder)
    before = verifier.c.census()
    report = verifier.run_verify(RUN, "FV3BV-OFFLINE-POSITIVE", emit_report=False)
    after = verifier.c.census()
    if before != {"content": [], "maps": []} or after != before:
        raise AssertionError("verify changed dirty census")
    if report["movement_sample_count"] != 3:
        raise AssertionError("wrong movement sample count")
    return "clean before/after; 3 analytic occurrences x 3 phases"


def test_verify_saved_entrypoint(folder):
    fake_unreal.reset(ORIGINALS, PLAN, "verify")
    load_common(SLOT / "slot_b_common.py", folder)
    module = load_named("slot_b_verify_saved_harness", SLOT / "slot_b_verify_saved.py")
    module.c.BASE = str(folder)
    module.verifier.c.BASE = str(folder)
    module.main()
    marker = next((line for line in fake_unreal.STATE.logs
                   if line.startswith("FLATV3_B_VERIFY_SAVED_OK")), None)
    if marker is None or "run=FV3BV-20261002-01" not in marker or "source_run=" + RUN not in marker:
        raise AssertionError("saved verifier marker missing")
    return marker


def test_dirty_variant_fails(folder):
    fake_unreal.reset(ORIGINALS, PLAN, "verify")
    load_common(SLOT / "slot_b_common.py", folder)
    verifier = load_named("slot_b_verify_dirty_harness", SLOT / "slot_b_verify.py")
    verifier.c.BASE = str(folder)
    variant = load_named("dirty_verify_variant_harness", HERE / "dirty_verify_variant.py")
    try:
        variant.run(verifier, fake_unreal.STATE.actor)
    except RuntimeError as exc:
        if "VERIFY_END_DIRTY" not in str(exc):
            raise
        return "FAIL (expected): end census caught dirty map"
    raise AssertionError("dirty verifier variant unexpectedly succeeded")


def test_new_release(folder):
    fake_unreal.reset(ORIGINALS, PLAN, "verify")
    common = load_common(SLOT / "slot_b_common.py", folder)
    common.log_release("FAIL", [], run=RUN, artifact_run=RUN)
    line = last_release()
    if "saved_count=2" not in line or common.SHOW not in line or common.WORLD not in line:
        raise AssertionError(line)
    return line


def test_old_release_control(folder):
    fake_unreal.reset(ORIGINALS, PLAN, "verify")
    common = load_common(HERE / "originals" / "slot_b_common.py", folder)
    common.log_release("FAIL", [])
    line = last_release()
    if "saved_count=0" not in line:
        raise AssertionError(line)
    return "FAIL (expected): " + line


def token_hits(path):
    source = path.read_text(encoding="utf-8")
    return [token for token in FORBIDDEN if token in source]


def run_case(name, polarity, expected, function, folder):
    try:
        detail = function(folder)
        record(name, polarity, expected, True, detail)
    except Exception as exc:
        record(name, polarity, expected, False, "%s: %s" % (type(exc).__name__, exc))


def print_table():
    headers = ("Test", "+/-", "Expected control outcome", "Harness", "Detail")
    rows = [headers]
    for item in RESULTS:
        rows.append((item["name"], item["polarity"], item["expected"],
                     "PASS" if item["passed"] else "FAIL", item["detail"]))
    widths = [max(len(str(row[index])) for row in rows) for index in range(len(headers))]
    for number, row in enumerate(rows):
        print(" | ".join(str(value).ljust(widths[index]) for index, value in enumerate(row)))
        if number == 0:
            print("-+-".join("-" * width for width in widths))


def main():
    with tempfile.TemporaryDirectory(prefix="flatv3_slot_b_offline_") as folder:
        stage_artifacts(folder)
        run_case("new revert / real originals", "+", "SUCCEED", test_new_revert, folder)
        run_case("old revert / real originals", "-", "FAIL", test_old_revert_fails, folder)
        run_case("read-only verify / clean world", "+", "SUCCEED", test_verify_clean, folder)
        run_case("saved verifier / fresh run id", "+", "SUCCEED", test_verify_saved_entrypoint, folder)
        run_case("dirty evaluation verifier", "-", "FAIL", test_dirty_variant_fails, folder)
        run_case("aggregated release", "+", "saved_count=2", test_new_release, folder)
        run_case("old release path", "-", "saved_count=0", test_old_release_control, folder)

        clean_paths = [SLOT / "slot_b_verify.py", SLOT / "slot_b_verify_saved.py"]
        hits = {path.name: token_hits(path) for path in clean_paths}
        record("static token check", "+", "SUCCEED", not any(hits.values()), json.dumps(hits))
        planted = token_hits(HERE / "planted_save_token.py")
        record("planted forbidden token", "-", "FAIL", planted == ["save_asset"],
               "FAIL (expected): hits=%s" % planted)

    print_table()
    failed = [item for item in RESULTS if not item["passed"]]
    print("\nOVERALL: %s (%d/%d harness assertions passed)" %
          ("PASS" if not failed else "FAIL", len(RESULTS) - len(failed), len(RESULTS)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
