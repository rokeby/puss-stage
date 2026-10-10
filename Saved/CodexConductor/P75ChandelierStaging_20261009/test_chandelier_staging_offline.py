from __future__ import annotations

import copy
import importlib.util
import json
import os
import py_compile
from typing import Callable


HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location("p75_core", os.path.join(HERE, "chandelier_staging_core.py"))
CORE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(CORE)
LIVE_SPEC = importlib.util.spec_from_file_location("p75_live_offline", os.path.join(HERE, "chandelier_staging.py"))
LIVE = importlib.util.module_from_spec(LIVE_SPEC)
assert LIVE_SPEC and LIVE_SPEC.loader
LIVE_SPEC.loader.exec_module(LIVE)


def _json(name: str) -> dict:
    with open(os.path.join(HERE, name), encoding="utf-8") as handle:
        return json.load(handle)


def _args() -> dict:
    return _json("chandelier_staging_args.json")


def _chain() -> dict:
    return _json("chandelier_Iron3_chain.json")


def _plan(raw: dict | None = None, chain: dict | None = None) -> dict:
    return CORE.build_plan(raw or _args(), chain or _chain())


def _fails(fn: Callable[[], object], token: str) -> None:
    try:
        fn()
    except CORE.P75Error as error:
        assert token in str(error), (token, str(error))
        return
    raise AssertionError("expected failure: " + token)


def main() -> None:
    tests: list[tuple[str, str, Callable[[], None]]] = []

    def add(kind: str, name: str, fn: Callable[[], None]) -> None:
        tests.append((kind, name, fn))

    def positive_global_cap() -> None:
        plan = _plan()
        assert plan["global_light_budget"] == {"lights": 4, "shadow_casters": 2}
        opening = plan["parts"]["opening"]["lights"]
        assert opening[0]["kind"] == "spot" and opening[0]["cast_shadows"] is True
        assert len(opening) == 3 and len(plan["parts"]["p06"]["lights"]) == 1

    def positive_parts_isolated() -> None:
        both = _plan()
        opening = _plan({**_args(), "parts": ["opening"]})
        p06 = _plan({**_args(), "parts": ["p06"]})
        assert opening["selected_parts"] == ["opening"] and p06["selected_parts"] == ["p06"]
        assert opening["parts"]["opening"]["plan_sha256"] == both["parts"]["opening"]["plan_sha256"]
        assert p06["parts"]["p06"]["plan_sha256"] == both["parts"]["p06"]["plan_sha256"]
        opening_labels = set(opening["instance_actor_labels"]["opening"]["link_actor_labels"])
        p06_labels = set(p06["instance_actor_labels"]["p06"]["link_actor_labels"])
        assert not opening_labels.intersection(p06_labels)

    def positive_no_foreign_writes() -> None:
        plan = _plan()
        CORE.verify_no_forbidden_writes(plan)
        assert plan["ownership"]["flames"] == "P56"
        assert plan["ownership"]["swing_keys"] == ["P52", "P52B"]
        assert plan["parts"]["opening"]["owned_sequence_writes"] == [
            "drive_by_intensity", "drive_by_arc_rotation"]

    def positive_chain_assembly() -> None:
        plan = _plan()
        assert plan["chain"]["count"] == 24
        assert len(plan["assets"]["chain_meshes"]) == 24
        for part in CORE.PARTS:
            labels = plan["instance_actor_labels"][part]["link_actor_labels"]
            assert len(labels) == 24 and len(set(labels)) == 24
        assert plan["chain"]["links"][23]["pivot_cm"] == [0.0, 0.0, -287.5]

    def positive_production_assets() -> None:
        plan = _plan()
        assert plan["assets"]["body_mesh"] == CORE.BODY_MESH
        assert plan["assets"]["material"] == CORE.MATERIAL
        assert plan["assets"]["chain_meshes"] == CORE.CHAIN_MESHES
        assert not any(path.startswith(CORE.OLD_ASSET_ROOT) for path in
                       [plan["assets"]["body_mesh"], plan["assets"]["material"]] +
                       plan["assets"]["chain_meshes"])

    def positive_p06_off() -> None:
        plan = _plan()
        assert len(plan["parts"]["p06"]["lights"]) == 1
        assert plan["parts"]["p06"]["lights"][0]["enabled_default"] is False
        assert plan["parts"]["p06"]["owned_sequence_writes"] == []

    def positive_hidden() -> None:
        row = {"hidden_in_game": True, "cast_hidden_shadow": True}
        CORE.verify_hidden_shadow(row, [dict(row) for _ in range(24)])

    def positive_shadow_and_clearance() -> None:
        plan = _plan()
        shadow = plan["parts"]["opening"]["projected_shadow_at_peak"]
        assert abs(shadow["width_cm"] - 331.57894736842104) < 1.0e-9
        assert plan["parts"]["p06"]["clearances_cm"] == {
            "nearest_topple_row": 3750.0, "nearest_wing_station": 550.0}

    def positive_cleanup_classifies_failed_and_legacy_tags() -> None:
        base = [LIVE.OWNER_TAG, "P75_PART_OPENING", "P75_ROLE_BODY"]
        legacy = LIVE.cleanup_tag_decision(base, "opening", "P75CHAN-20261009-204553")
        tagged = LIVE.cleanup_tag_decision(base + ["P75_RUN_P75CHAN-20261009-204553"],
                                           "opening", "P75CHAN-20261009-204553")
        assert legacy == {"eligible": True, "reason": "legacy_no_run_tag", "run_tags": []}
        assert tagged["eligible"] and tagged["reason"] == "failed_run"

    def positive_adopt_or_clean_confirmation() -> None:
        plan = _plan({**_args(), "mode": "ADOPT_OR_CLEAN", "parts": ["opening"],
                      "confirm": "DRY ADOPT_OR_CLEAN P75"})
        assert plan["args"]["cleanup_failed_run_id"] == "P75CHAN-20261009-204553"

    add("POSITIVE", "global cap includes drive-by", positive_global_cap)
    add("POSITIVE", "opening and p06 part isolation", positive_parts_isolated)
    add("POSITIVE", "no flames or swing keys", positive_no_foreign_writes)
    add("POSITIVE", "24-link pivot assembly", positive_chain_assembly)
    add("POSITIVE", "production asset paths", positive_production_assets)
    add("POSITIVE", "P06 light off by default", positive_p06_off)
    add("POSITIVE", "hidden-shadow flags for body plus links", positive_hidden)
    add("POSITIVE", "shadow forecast and P06 clearances", positive_shadow_and_clearance)
    add("POSITIVE", "cleanup accepts exact failed-run and legacy no-run tags",
        positive_cleanup_classifies_failed_and_legacy_tags)
    add("POSITIVE", "ADOPT_OR_CLEAN has exact dry confirmation", positive_adopt_or_clean_confirmation)

    add("NEGATIVE", "global light cap across parts", lambda: _fails(
        lambda: _plan({**_args(), "p06_group_light_count": 2}), "GLOBAL_GPU_LIGHT_CAP_4"))
    add("NEGATIVE", "global caster cap includes drive-by", lambda: _fails(
        lambda: _plan({**_args(), "p06_group_shadow_caster_count": 1}), "GLOBAL_GPU_SHADOW_CAP_2"))
    add("NEGATIVE", "existing plus candidate global cap", lambda: _fails(
        lambda: CORE.validate_global_light_guard([
            {"label": "drive", "cast_shadows": True}, {"label": "open-a", "cast_shadows": True},
            {"label": "open-b", "cast_shadows": False}, {"label": "p06-a", "cast_shadows": False},
            {"label": "foreign-p75", "cast_shadows": False}]), "GLOBAL_GPU_LIGHT_CAP_4"))
    add("NEGATIVE", "24-link count", lambda: _fails(
        lambda: _plan(chain={**_chain(), "count": 23}), "CHAIN_LINK_COUNT_24"))

    def bad_pivot() -> None:
        chain = copy.deepcopy(_chain())
        chain["links"][7]["pivot_cm"][2] = -88.0
        _fails(lambda: _plan(chain=chain), "CHAIN_LINK_PIVOT_07")

    add("NEGATIVE", "chain pivot drift", bad_pivot)
    add("NEGATIVE", "old body path refused", lambda: _fails(
        lambda: _plan({**_args(), "body_mesh": "/Game/Scenes/Chandelier/Iron3/SM_Chandelier_Iron3"}),
        "OLD_ASSET_ROOT_REFUSED"))

    def old_chain_path() -> None:
        raw = _args()
        raw["chain_meshes"] = list(raw["chain_meshes"])
        raw["chain_meshes"][0] = "/Game/Scenes/Chandelier/Iron3/SM_Chandelier_Iron3_Chain"
        _fails(lambda: _plan(raw), "OLD_ASSET_ROOT_REFUSED")

    add("NEGATIVE", "old chain path refused", old_chain_path)
    add("NEGATIVE", "APPLY one part only", lambda: _fails(
        lambda: _plan({**_args(), "mode": "APPLY", "parts": ["opening", "p06"],
                       "confirm": "APPLY P75 CHANDELIER"}), "MUTATION_ONE_PART_REQUIRED"))
    add("NEGATIVE", "stale opening review hash", lambda: _fails(
        lambda: _plan({**_args(), "mode": "APPLY", "parts": ["opening"],
                       "confirm": "APPLY P75 CHANDELIER",
                       "reviewed_plan_sha256": {"opening": "stale", "p06": ""}}),
        "REVIEWED_PLAN_HASH_OPENING"))
    add("NEGATIVE", "hidden link flag", lambda: _fails(
        lambda: CORE.verify_hidden_shadow(
            {"hidden_in_game": True, "cast_hidden_shadow": True},
            ([{"hidden_in_game": True, "cast_hidden_shadow": False}] +
             [{"hidden_in_game": True, "cast_hidden_shadow": True} for _ in range(23)])),
        "LINK_00_NO_HIDDEN_SHADOW"))
    add("NEGATIVE", "topple overlap", lambda: _fails(
        lambda: _plan({**_args(), "p06_hang_station_cm": 9450.0}), "TOPPLE_ROW_OVERLAP"))
    add("NEGATIVE", "P75 may not add sound", lambda: _fails(
        lambda: _plan({**_args(), "new_sound": True}), "SILENT_DEFAULT_REQUIRED"))
    add("NEGATIVE", "cleanup refuses a different run tag", lambda: (
        (_ for _ in ()).throw(AssertionError("different run incorrectly eligible"))
        if LIVE.cleanup_tag_decision(
            [LIVE.OWNER_TAG, "P75_PART_OPENING", "P75_RUN_P75CHAN-20261009-999999"],
            "opening", "P75CHAN-20261009-204553")["eligible"] else None))
    add("NEGATIVE", "cleanup exact confirmation", lambda: _fails(
        lambda: _plan({**_args(), "mode": "CLEAN", "parts": ["opening"],
                       "confirm": "CLEAN P75"}), "CONFIRM"))

    passed, failed, details = 0, 0, []
    for kind, name, fn in tests:
        try:
            fn()
            passed += 1
            details.append({"kind": kind, "name": name, "ok": True})
        except Exception as error:  # noqa: BLE001 - retain every exact harness failure.
            failed += 1
            details.append({"kind": kind, "name": name, "ok": False, "error": repr(error)})

    for filename in ("chandelier_staging_core.py", "chandelier_staging.py", "chandelier_staging_run.py",
                     "make_timeline_previews.py", "test_chandelier_staging_offline.py"):
        py_compile.compile(os.path.join(HERE, filename), doraise=True)
    plan = _plan()
    with open(os.path.join(HERE, "p75_offline_plan.json"), "w", encoding="utf-8") as handle:
        json.dump(plan, handle, indent=2, sort_keys=True)
    result = {"pass": passed, "fail": failed, "total": len(tests),
              "positive": sum(1 for kind, _, _ in tests if kind == "POSITIVE"),
              "negative": sum(1 for kind, _, _ in tests if kind == "NEGATIVE"),
              "offline": True, "unreal": False, "blender": False, "details": details}
    with open(os.path.join(HERE, "harness_result.json"), "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
    line = ("P75_CHANDELIER_HARNESS|PASS=%d|FAIL=%d|TOTAL=%d|POSITIVE=%d|NEGATIVE=%d|"
            "OFFLINE=1|UNREAL=0|BLENDER=0" %
            (passed, failed, len(tests), result["positive"], result["negative"]))
    with open(os.path.join(HERE, "harness_result.txt"), "w", encoding="utf-8") as handle:
        handle.write(line + "\n")
    print(line)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
