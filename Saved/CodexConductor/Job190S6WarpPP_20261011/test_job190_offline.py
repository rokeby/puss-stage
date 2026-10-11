"""Offline positive and negative controls for Job 190."""

from pathlib import Path
import copy
import json

import job190_core as core


HERE = Path(__file__).resolve().parent
SCORES = json.loads((HERE / "warp_scores.json").read_text(encoding="utf-8"))
PASSED = 0
FAILED = 0


def check(label, condition):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print("PASS", label)
    else:
        FAILED += 1
        print("FAIL", label)


def rejects(label, fn, needle=""):
    try:
        fn()
    except (ValueError, KeyError) as exc:
        check(label, needle.lower() in str(exc).lower())
    else:
        check(label, False)


def main():
    args = core.validate_args({})
    request = json.loads((HERE / "job190_request.json").read_text(encoding="utf-8"))
    check("MCP request uses call_tool envelope",
          request == {"name": "call_tool", "arguments": {
              "toolset_name": "MCPBlueprintsGenerator.MCPBlueprintsGeneratorToolset",
              "tool_name": "ExecuteProjectPythonFile",
              "arguments": {"relativeSavedPath":
                            "CodexConductor/Job190S6WarpPP_20261011/job190_run.py"}}})
    check("DRY is default", args["mode"] == "DRY")
    check("default preset is lowercase both", args["preset"] == "both")
    check("move defaults", (args["move_seconds"], args["push_cm"], args["ease_fraction"]) == (2.8, 240.0, 0.35))
    check("void proposal is off", args["void_mode"] == "off")
    check("production Master identity",
          core.MASTER_PATH == "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master")
    current_master = "/Game/InfinityStage/Current/LS_RuntimeMaster"
    dynamic_saves = (current_master,) + tuple(path for path in core.ALLOWED_NAMED_SAVES
                                               if path != core.MASTER_PATH)
    check("current Show Root Master accepted dynamically",
          core.validate_named_saves(dynamic_saves, require_apply_set=True,
                                    current_master_path=current_master) == dynamic_saves)
    rejects("obsolete Master rejected when current differs",
            lambda: core.validate_named_saves(core.ALLOWED_NAMED_SAVES, require_apply_set=True,
                                              current_master_path=current_master), "allowlist")
    check("dynamic Master is sole camera edit target",
          core.validate_camera_edit_targets((current_master,), current_master_path=current_master)
          == (current_master,))
    rejects("bad mode negative", lambda: core.validate_args({"mode": "GO"}), "mode")
    rejects("bad run negative", lambda: core.validate_args({"run": "bad"}), "run")
    rejects("APPLY confirm negative", lambda: core.validate_args({"mode": "APPLY", "run": "J190-ABC"}), "confirm")
    rejects("REVERT record negative", lambda: core.validate_args({"mode": "REVERT", "run": "J190-ABC",
                                                                   "confirm": core.CONFIRM["REVERT"]}), "record")
    check("exact APPLY accepted", core.validate_args({"mode": "APPLY", "run": "J190-ABC",
                                                       "confirm": core.CONFIRM["APPLY"]})["mode"] == "APPLY")
    rejects("push low negative", lambda: core.validate_args({"push_cm": 0}), "push")
    rejects("move high negative", lambda: core.validate_args({"move_seconds": 9}), "move")
    rejects("ease negative", lambda: core.validate_args({"ease_fraction": 0}), "ease")
    rejects("priority negative", lambda: core.validate_args({"volume_priority": 0}), "priority")
    rejects("void mode negative", lambda: core.validate_args({"void_mode": "do_it"}), "void")
    check("source preset alias accepted", core.validate_args({"preset": "Both"})["preset"] == "both")
    check("Job 194 APPLY save allowlist exact",
          core.validate_named_saves(core.ALLOWED_NAMED_SAVES, require_apply_set=True) == core.ALLOWED_NAMED_SAVES)
    rejects("KlaraHookin save negative",
            lambda: core.validate_named_saves((core.MASTER_PATH, core.NESTED_SHOT_PATH)), "KlaraHookin")
    rejects("extra named save negative",
            lambda: core.validate_named_saves((core.MASTER_PATH, "/Game/Foreign/Asset")), "allowlist")
    check("MPC keys accepted in S6", core.validate_mpc_key_sequence(core.S6_PATH) == core.S6_PATH)
    check("MPC keys accepted in Master", core.validate_mpc_key_sequence(core.MASTER_PATH) == core.MASTER_PATH)
    rejects("MPC keys in nested shot negative",
            lambda: core.validate_mpc_key_sequence(core.NESTED_SHOT_PATH), "only")
    check("P06 Master camera target accepted",
          core.validate_camera_edit_targets((core.MASTER_PATH,)) == (core.MASTER_PATH,))
    rejects("nested camera edit negative",
            lambda: core.validate_camera_edit_targets((core.NESTED_SHOT_PATH,)), "forbidden")

    digests = set()
    for preset in core.PRESETS:
        rows = core.compile_score(SCORES, preset)
        check("%s rows valid" % preset, len(rows) == 7 and rows[0]["time"] == 0 and rows[-1]["time"] == 194)
        check("%s unit bounded" % preset,
              all(0 <= row[name] <= 1 for row in rows for name in core.UNIT_PARAMETERS))
        keys = core.score_keys(rows, 25.0)
        check("%s key census" % preset,
              set(keys) == set(core.PARAMETERS) and all(len(value) == 7 for value in keys.values()))
        check("%s gentle then intense" % preset, rows[4]["Weird"] > rows[1]["Weird"])
        digests.add(core.stable_digest(rows))
    check("three presets distinct", len(digests) == 3)
    job189_scores = json.loads((HERE.parent / "Job189S6Warp_20261011" / "warp_scores.json").read_text(encoding="utf-8"))
    check("Job 189 scores reused value-for-value",
          core.stable_digest(SCORES) == core.stable_digest(job189_scores))

    bad = copy.deepcopy(SCORES)
    bad["presets"]["Both"][1]["time"] = 0.0
    rejects("duplicate time negative", lambda: core.compile_score(bad, "both"), "strictly")
    bad = copy.deepcopy(SCORES)
    bad["presets"]["Both"][1]["Weird"] = 1.1
    rejects("range negative", lambda: core.compile_score(bad, "both"), "[0, 1]")
    bad = copy.deepcopy(SCORES)
    bad["presets"]["Both"][1]["RenderTarget"] = 1
    rejects("unknown field negative", lambda: core.compile_score(bad, "both"), "unknown")
    bad = copy.deepcopy(SCORES)
    bad["schema"] = 2
    rejects("schema negative", lambda: core.compile_score(bad, "both"), "schema")

    check("move frame plan", core.move_frames(100000, 24000, 2.8, 0.35) == [32800, 56320, 100000])
    rejects("move underflow negative", lambda: core.move_frames(10, 24000, 2.8, 0.35), "invalid")
    midpoint = core.evaluate_score(core.compile_score(SCORES, "both"), 80.0)
    check("score interpolation", 0.30 < midpoint["Weird"] < 0.40)
    check("digest changes with void proposal", core.plan_digest(args, core.compile_score(SCORES, "both")) !=
          core.plan_digest({**args, "void_mode": "proposal"}, core.compile_score(SCORES, "both")))

    source = (HERE / "job190_s6_warp_pp.py").read_text(encoding="utf-8")
    check("live Master follows the single Show Root",
          'get_editor_property("master_sequence")' in source and
          '"master_path": master_path' in source and
          'unreal.load_asset(MASTER_PATH)' not in source)
    check("post-process material path", core.MATERIAL_PATH == "/Game/InfinityStage/Effects/S6/M_PP_S6Warp" and
          "MATERIAL_PATH = core.MATERIAL_PATH" in source)
    check("post-process domain", "MaterialDomain.MD_POST_PROCESS" in source)
    check("three PostProcessInput0 samples", "PPI_POST_PROCESS_INPUT0" in source and "MaterialExpressionSceneTexture" in source)
    check("screen UV source", "MaterialExpressionScreenPosition" in source)
    check("all effects in shader", all(token in source for token in
          ("Weird", "Invert", "HueDrift", "Solarize", "ChromaSplit", "Warp", "Mirror", "Phase")))
    check("swirl and panning noise", all(token in source for token in ("swirl", "n1", "n2", "Phase")))
    check("kaleidoscope fold", all(token in source for token in ("blades", "folded", "kaleido")))
    check("no render target dependency", "RenderTarget" not in source and "render_target" not in source)
    check("no C++ patch prerequisite", '"runtime_prerequisite": "none;' in source)
    check("create-only material guard", "CREATE_ONLY_MATERIAL_PATH_ALREADY_EXISTS" in source)
    check("never deletes material expressions", all(token not in source for token in
          ("delete_material_expression", "delete_all_material_expressions")))
    check("S6-only PPV blend track", 'set_property_name_and_path("BlendWeight", "blend_weight")' in source)
    check("PPV default off", 'volume.set_editor_property("blend_weight", 0.0)' in source)
    check("PPV restore state", "MovieSceneCompletionMode.RESTORE_STATE" in source)
    check("live 3D identities read-only guarded", all(token in source for token in
          ("BP_MHC_Elder_Female", "CineCameraActor5")) and
          core.NESTED_SHOT_PATH.endswith("/LS_Void_S6") and core.S6_PATH.endswith("/LS_DevScene_06"))
    check("nested and entry cameras are never edited", "set_first_camera_transform" not in source and
          "def set_camera_actor" not in source and
          'ctx["shot"].remove_track' not in source and 'ctx["shot"].add_track' not in source)
    check("move-in becomes DRY-only when nested edit would be required",
          "MOVE_IN_DRY_ONLY|P06_MASTER_ONLY_CANNOT_MATCH_READ_ONLY_NESTED_CAMERA" in source)
    check("named saves exclude KlaraHookin",
          '"named_saves": [ctx["master_path"], S6_PATH, MATERIAL_PATH, MPC_PATH, WORLD_PATH]' in source
          and '"named_saves": [MASTER_PATH' not in source)
    check("MPC target explicitly guarded", "validate_mpc_key_sequence" in source and
          '"mpc_key_sequence": S6_PATH' in source)
    check("binding lookup precedes add", "BINDING_LOOKUP_CHANGED_BEFORE_ADD" in source)
    check("dirty scope guarded", "assert_dirty_scope" in source and "FOREIGN_DIRTY" in source)
    check("success markers", all(marker in source for marker in
          ("JOB190_DRY_OK", "JOB190_APPLY_OK", "JOB190_REVERT_OK")))
    check("named saves only", "save_all" not in source.lower())
    check("no asset/file deletion APIs", all(token not in source for token in
          ("delete_asset", "os.remove", "shutil.rmtree")))
    check("revert retains generated assets", "retained_reusable_assets" in source)
    check("void proposal refuses apply-ready DRY", "VOID_PROPOSAL_REQUIRES_LIVE_STENCIL_AND_HAIR_COVERAGE_PROOF" in source)

    void = json.loads((HERE / "void_proposal.json").read_text(encoding="utf-8"))
    check("void is proposal only", void["status"] == "proposal_only" and not void["enabled_by_default"])
    check("void acceptance protects performer", all(word in void["acceptance"] for word in ("face", "body", "hair")))

    print("JOB190_OFFLINE_HARNESS|passed=%d|failed=%d|positive_and_negative=1" % (PASSED, FAILED))
    raise SystemExit(1 if FAILED else 0)


if __name__ == "__main__":
    main()

