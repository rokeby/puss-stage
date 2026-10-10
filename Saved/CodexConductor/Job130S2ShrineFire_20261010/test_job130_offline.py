"""Offline +/- harness for Codex job 130. No Unreal imports or processes."""
import importlib.util
import json
import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "job130_s2_shrine_fire.py")
PIE = os.path.join(HERE, "job130_s2_shrine_fire_pie.py")
RESULTS = []


def load():
    sys.modules.pop("unreal", None)
    spec = importlib.util.spec_from_file_location("job130_harness", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def case(name, fn):
    try:
        fn()
        RESULTS.append({"name": name, "status": "PASS"})
    except Exception as exc:
        RESULTS.append({"name": name, "status": "FAIL", "detail": "%s: %s" % (type(exc).__name__, exc)})


def base_component(**changes):
    row = {"auto_activate": True, "has_lifecycle_track": False, "allow_scalability": False,
           "has_distance_cull": False, "bound_tracks": []}
    row.update(changes)
    return row


def names(ranked):
    return [row["cause"] for row in ranked]


def test_rank_streaming():
    ranked = load().rank_causes([base_component()], [{"world_asset": "L_KK_S2_Shrine", "loaded": True, "visible": False}])
    assert ranked[0]["cause"] == "streamed level not visible in PIE"


def test_rank_auto_activate():
    ranked = load().rank_causes([base_component(auto_activate=False)], [])
    assert ranked[0]["cause"] == "auto_activate off with no trigger"


def test_lifecycle_defeats_auto_off():
    ranked = load().rank_causes([base_component(auto_activate=False, has_lifecycle_track=True)], [])
    score = next(x["score"] for x in ranked if x["cause"] == "auto_activate off with no trigger")
    assert score == 5


def test_rank_deactivation():
    track = {"class": "MovieSceneNiagaraSystemTrack", "sections": [{"end_behavior": "DEACTIVATE"}]}
    component = base_component(bound_tracks=[{"tracks": [track]}])
    assert load().rank_causes([component], [])[0]["cause"] == "deactivation track"


def test_lifecycle_spanning_probe_is_not_deactivation():
    track = {"class": "MovieSceneNiagaraSystemTrack", "sections": [
        {"range": [0, 240], "active": True, "end_behavior": "DEACTIVATE"}]}
    component = base_component(bound_tracks=[{"tracks": [track]}])
    ranked = load().rank_causes([component], [], probe_frame=120)
    assert next(x["score"] for x in ranked if x["cause"] == "deactivation track") == 10


def test_rank_inert_visibility_none():
    track = {"class": "MovieSceneVisibilityTrack", "property_name": "", "sections": []}
    component = base_component(bound_tracks=[{"tracks": [track]}])
    assert load().rank_causes([component], [])[0]["cause"] == "inert visibility track"


def test_rank_inert_visibility_hidden_in_game():
    track = {"class": "MovieSceneVisibilityTrack", "property_name": "bHiddenInGame", "sections": []}
    component = base_component(bound_tracks=[{"tracks": [track]}])
    assert load().rank_causes([component], [])[0]["cause"] == "inert visibility track"


def test_bhidden_is_not_inert():
    track = {"class": "MovieSceneVisibilityTrack", "property_name": "bHidden", "sections": []}
    ranked = load().rank_causes([base_component(bound_tracks=[{"tracks": [track]}])], [])
    assert next(x["score"] for x in ranked if x["cause"] == "inert visibility track") == 5


def test_rank_scalability():
    ranked = load().rank_causes([base_component(allow_scalability=True, has_distance_cull=True)], [])
    assert next(x["score"] for x in ranked if x["cause"] == "scalability culling") == 60


def test_scalability_disabled_is_low():
    ranked = load().rank_causes([base_component(allow_scalability=False, has_distance_cull=True)], [])
    assert next(x["score"] for x in ranked if x["cause"] == "scalability culling") == 10


def test_all_five_causes_present():
    assert set(names(load().rank_causes([], []))) == {
        "streamed level not visible in PIE", "deactivation track", "auto_activate off with no trigger",
        "inert visibility track", "scalability culling"}


def test_review_hash_ignores_execution_metadata():
    mod = load()
    a = {"run": "A", "mode": "PROBE", "dirty_census": {}, "probe_sha256": "x", "components": [1]}
    b = {"run": "B", "mode": "APPLY", "dirty_census": {"maps": []}, "probe_sha256": "y", "components": [1]}
    assert mod._hash_json(mod.review_payload(a)) == mod._hash_json(mod.review_payload(b))


def test_review_hash_detects_component_change():
    mod = load()
    assert mod._hash_json(mod.review_payload({"components": [1]})) != mod._hash_json(mod.review_payload({"components": [2]}))


def test_dry_plan_needs_reviewed_targets():
    plan = load().build_fix_plan({"target_component_paths": []}, {"components": []})
    assert plan["status"] == "NEEDS_REVIEWED_TARGETS"


def test_dry_plan_refuses_hash_drift():
    mod = load()
    probe = {"probe_sha256": "fresh", "components": [{"component": "C", "has_lifecycle_track": False}]}
    try:
        mod.build_fix_plan({"target_component_paths": ["C"], "reviewed_probe_sha256": "old"}, probe)
    except Exception as exc:
        assert "PROBE_HASH_MISMATCH" in str(exc)
        return
    raise AssertionError("hash drift accepted")


def test_track_property_none_sentinel():
    mod = load()
    class Track:
        def get_property_name(self): return "None"
        def get_property_path(self): return "None"
    assert mod._track_property(Track()) == ("", "")


def test_distance():
    assert load()._distance([0, 0, 0], [3, 4, 0]) == 5.0


def test_import_is_offline():
    load()
    assert "unreal" not in sys.modules


def test_args_are_safe_probe():
    args = json.load(open(os.path.join(HERE, "job130_args.json"), encoding="utf-8"))
    assert args["mode"] == "PROBE" and args["confirm"] == "PROBE JOB130"
    assert args["target_component_paths"] == [] and args["allow_scalability"] is False


def test_exact_confirmations():
    assert load().CONFIRMS == {"PROBE": "PROBE JOB130", "DRY": "DRY JOB130",
                               "APPLY": "APPLY JOB130 S2 SHRINE FIRE",
                               "REVERT": "REVERT JOB130 S2 SHRINE FIRE"}


def test_only_our_sequence_can_save():
    source = open(TOOL, encoding="utf-8").read()
    assert 'S2_SEQUENCE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_02"' in source
    assert "save_current_level" not in source and "save_dirty_packages" not in source and "save_all" not in source.lower()
    assert "EditorAssetLibrary.save_asset(S2_SEQUENCE" in source


def test_lifecycle_contract():
    source = open(TOOL, encoding="utf-8").read()
    for token in ("NiagaraSystemSpawnSectionStartBehavior.ACTIVATE",
                  "NiagaraSystemSpawnSectionEvaluateBehavior.ACTIVATE_IF_INACTIVE",
                  "NiagaraSystemSpawnSectionEndBehavior.DEACTIVATE",
                  "MovieSceneNiagaraSystemTrack"):
        assert token in source


def test_no_existing_binding_rename():
    source = open(TOOL, encoding="utf-8").read()
    assert ".set_display_name(" not in source
    assert "ADD_POSSESSABLE_REUSED_UNRESOLVED_BINDING" in source


def test_backup_precedes_mutation():
    source = open(TOOL, encoding="utf-8").read()
    block = source[source.index("def _apply("):source.index("def _revert(")]
    assert block.index("backup = _backup") < block.index("_find_binding") < block.index("binding.add_track")


def test_exact_dirty_census_and_no_map_save():
    source = open(TOOL, encoding="utf-8").read()
    assert source.count('{"content": [S2_SEQUENCE], "maps": []}') >= 2
    assert "Don't-Save restart" in source


def test_probe_inventory_contract():
    source = open(TOOL, encoding="utf-8").read()
    for token in ("auto_activate", "is_active", "owner_hidden", "owner_level", "fixed_bounds",
                  "warmup_time_s", "max_distance_cm", "level_visibility_tracks", "all_niagara_bindings"):
        assert token in source


def test_pie_contract():
    source = open(PIE, encoding="utf-8").read()
    for token in ('OFFSET_SECONDS = 5.0', 'unreal.load_asset("/Game/InfinityStage/Dev/Sequences/LS_DevScene_02")',
                  "get_num_active_particles", "is_level_visible", "JOB130_PIE_OK"):
        assert token in source
    assert "start_editor_play_simulate_session" not in source and "request_end_play_map" not in source


def test_revert_has_own_backup_and_readback():
    source = open(TOOL, encoding="utf-8").read()
    block = source[source.index("def _revert("):source.index("def run(")]
    assert "PreJob130S2ShrineFireRevert" in block
    assert "remaining =" in block and "REVERT_REMOVE_POSSESSABLE_FAILED" in block


def main():
    tests = [
        ("+ ranks invisible streamed shrine level", test_rank_streaming),
        ("+ ranks auto-activate off without lifecycle", test_rank_auto_activate),
        ("- lifecycle prevents false auto-activate diagnosis", test_lifecycle_defeats_auto_off),
        ("+ ranks deactivation lifecycle", test_rank_deactivation),
        ("- lifecycle spanning +5 is not blamed for its later end", test_lifecycle_spanning_probe_is_not_deactivation),
        ("+ ranks property-less visibility inert", test_rank_inert_visibility_none),
        ("+ ranks bHiddenInGame visibility inert", test_rank_inert_visibility_hidden_in_game),
        ("- bHidden visibility is not called inert", test_bhidden_is_not_inert),
        ("+ ranks enabled distance culling", test_rank_scalability),
        ("- disabled scalability suppresses cull diagnosis", test_scalability_disabled_is_low),
        ("+ ranking always contains five requested causes", test_all_five_causes_present),
        ("+ review hash ignores run/mode/census", test_review_hash_ignores_execution_metadata),
        ("- review hash catches component drift", test_review_hash_detects_component_change),
        ("- DRY without selection cannot claim ready", test_dry_plan_needs_reviewed_targets),
        ("- DRY refuses stale reviewed probe hash", test_dry_plan_refuses_hash_drift),
        ("+ Unreal None property sentinel normalizes", test_track_property_none_sentinel),
        ("+ distance helper", test_distance),
        ("+ module imports offline", test_import_is_offline),
        ("+ shipped args are non-mutating PROBE", test_args_are_safe_probe),
        ("- exact confirmations cannot alias", test_exact_confirmations),
        ("- save surface is only our S2 sequence", test_only_our_sequence_can_save),
        ("+ lifecycle uses activate/keep-alive/deactivate", test_lifecycle_contract),
        ("- existing bindings are never renamed", test_no_existing_binding_rename),
        ("- APPLY backup precedes first mutation", test_backup_precedes_mutation),
        ("- map dirtiness is refused and never saved", test_exact_dirty_census_and_no_map_save),
        ("+ probe covers required inventory", test_probe_inventory_contract),
        ("+ PIE variant probes t=+5 and never starts/stops PIE", test_pie_contract),
        ("+ REVERT has independent backup and binding readback", test_revert_has_own_backup_and_readback),
    ]
    for name, fn in tests:
        case(name, fn)
    passed = sum(row["status"] == "PASS" for row in RESULTS)
    result = {"passed": passed, "failed": len(RESULTS) - passed, "total": len(RESULTS), "results": RESULTS}
    with open(os.path.join(HERE, "harness_result.json"), "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    for row in RESULTS:
        print("%-4s %s%s" % (row["status"], row["name"], " | " + row.get("detail", "") if row.get("detail") else ""))
    print("JOB130_HARNESS|pass=%d|fail=%d|total=%d" % (passed, len(RESULTS) - passed, len(RESULTS)))
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
