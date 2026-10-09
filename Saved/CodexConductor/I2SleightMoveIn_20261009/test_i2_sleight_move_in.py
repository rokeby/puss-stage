"""Offline fake-Unreal harness for P34 I2 sleight move-in."""
import copy
import importlib.util
import json
import os
import tempfile
import traceback


HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location("i2_sleight_move_in", os.path.join(HERE, "i2_sleight_move_in.py"))
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)


SHIFTED_MOUTH_COMPONENT_GUID = "D5173C9D4C80612C7E84CFA8EC530EA2"


def section(channels, end=1950):
    return {"range": [0, end], "active": True, "completion": "PROJECT_DEFAULT", "channels": channels}


def channel(name, default, keys):
    return {"name": name, "default": default, "keys": copy.deepcopy(keys)}


def track(cls, name, prop, path, channels, end=1950):
    return {"class": cls, "display_name": name, "property": prop, "path": path,
            "sections": [section(channels, end)]}


def fixture_snapshot():
    transform_values = {
        "Location.X": -2167.135009765625, "Location.Y": 160000.0, "Location.Z": 444.86566162109375,
        "Rotation.X": 0.0, "Rotation.Y": 0.0, "Rotation.Z": 0.0,
    }
    channels = [channel(name, 0.0, [[0, value], [2226, value]]) for name, value in transform_values.items()]
    channels += [channel(name, 1.0, []) for name in ("Scale.X", "Scale.Y", "Scale.Z")]
    snapshot = {
        "display_rate": 25.0, "tick_resolution": 24000.0, "playback": [0, 1950],
        "bindings": [
            {"guid": TOOL.HANGAR_GUID, "name": TOOL.HANGAR_NAME, "parent": "", "tracks": []},
            {"guid": TOOL.MOUTH_GUID, "name": TOOL.MOUTH_NAME, "parent": "",
             "tracks": [track(TOOL.TRANSFORM_CLASS, TOOL.ORIGINAL_TRACK_NAME, "Transform", "Transform", channels)]},
            {"guid": SHIFTED_MOUTH_COMPONENT_GUID, "name": TOOL.MOUTH_COMPONENT_NAME, "parent": TOOL.MOUTH_GUID,
             "tracks": [
                 track(TOOL.FLOAT_CLASS, TOOL.ORIGINAL_TRACK_NAME, "CurrentFocalLength", "CurrentFocalLength",
                       [channel("None", None, [[0, 33.49193572998047], [2226, 33.49193572998047]])]),
                 track(TOOL.FLOAT_CLASS, TOOL.ORIGINAL_TRACK_NAME, "ManualFocusDistance", "FocusSettings.ManualFocusDistance",
                       [channel("None", None, [[0, 1378.7957763671875], [2226, 1378.7957763671875]])]),
             ]},
            {"guid": "2D6DC35E47AA01CE86607AAF286A5C50", "name": "Sleight Hangar Drape", "parent": "", "tracks": []},
        ],
        "cuts": [
            {"track_index": 0, "section_index": 0, "range": [0, 1250], "active": True, "binding_guid": TOOL.HANGAR_GUID},
            {"track_index": 0, "section_index": 1, "range": [1250, 1950], "active": True, "binding_guid": TOOL.MOUTH_GUID},
        ],
        "markers": [["CST sleight", 1250]], "root_tracks": [], "cut_track_count": 1,
    }
    snapshot["bindings"].sort(key=lambda row: (row["guid"], row["name"]))
    return snapshot


def write_fixture_evidence(root, snapshot):
    hangar_path = os.path.join(root, "hangar.json")
    order_path = os.path.join(root, "order.json")
    probe_path = os.path.join(root, "probe.json")
    actor = {"location_cm": [13393.0, 78777.0, 510.0],
             "rotation_deg": {"pitch": 0.0, "yaw": -43.57, "roll": 0.0},
             "sensor_width_mm": 36.0, "sensor_height_mm": 20.25}
    recorded_snapshot = copy.deepcopy(snapshot)
    TOOL._binding(recorded_snapshot, SHIFTED_MOUTH_COMPONENT_GUID)["guid"] = TOOL.RECORDED_MOUTH_COMPONENT_GUID
    recorded_snapshot["playback"] = [0, 2226]
    recorded_snapshot["cuts"][1]["range"] = [1250, 2226]
    for binding in recorded_snapshot["bindings"]:
        for item in binding.get("tracks", []):
            item["sections"][0]["range"] = [0, 2227]
    recorded_snapshot["bindings"].sort(key=lambda row: (row["guid"], row["name"]))
    TOOL.json_write(hangar_path, {"applied": True, "sequence": TOOL.SEQ_PATH, "actor_after": actor,
                                  "plan": {"actor": {"focus_point_world_cm": [15161.661337041618, 77094.49843646525, 510.0]}},
                                  "snapshot_after": recorded_snapshot})
    TOOL.json_write(order_path, {"applied": True, "sequence": TOOL.SEQ_PATH, "snapshot_after": recorded_snapshot,
                                 "plan": {"coverage": {"twin": {"tan_h": 0.35471225701076686}},
                                          "lens": {"focal_mm": 33.49193572998047}}})
    TOOL.json_write(probe_path, {"drapes": [
        {"label": "Geometry Cache Actor2", "origin": [15160.9513209271, 77095.35612612331, 519.7182273864746],
         "extent": [677.1713158961793, 708.8754231409403, 500.26535415649414],
         "gc": [{"asset": "/Game/Scenes/Curtain/Baked/GC_CurtainDrop_Opening.GC_CurtainDrop_Opening"}]},
        {"label": "Geometry Cache Actor", "origin": [-1.1043643951416016, 160000.1310119629, 519.7182273864746],
         "extent": [40.23932456970215, 940.1479797363281, 500.26535415649414],
         "gc": [{"asset": "/Game/Scenes/Curtain/Baked/GC_CurtainDrop_Opening.GC_CurtainDrop_Opening"}]},
    ]})
    return {"hangar_record": hangar_path, "order_record": order_path, "drape_probe": probe_path}


class FakeUnreal(object):
    def __init__(self, snapshot=None):
        self.snapshot_value = copy.deepcopy(snapshot or fixture_snapshot())
        self.original = copy.deepcopy(self.snapshot_value)
        self.pie = False
        self.dirty = {"content": [], "maps": []}
        self.logs = []
        self.events = []
        self.hangar_camera = {"binding_guid": TOOL.HANGAR_GUID, "location_cm": [13393.0, 78777.0, 510.0],
                              "rotation_deg": {"pitch": 0.0, "yaw": -43.57, "roll": 0.0},
                              "sensor_width_mm": 36.0, "sensor_height_mm": 20.25}
        self.mouth_camera = {"binding_guid": TOOL.MOUTH_GUID, "location_cm": [-2167.135, 160000.0, 444.86566],
                             "rotation_deg": {"pitch": 0.0, "yaw": 0.0, "roll": 0.0},
                             "sensor_width_mm": 23.76, "sensor_height_mm": 13.365}

    def log(self, message):
        self.logs.append(message)

    def stop(self, message):
        self.logs.append(message)

    def census(self):
        return copy.deepcopy(self.dirty)

    def preflight(self, mode):
        if self.pie:
            raise TOOL.PlanError("PIE_OR_SIE_ACTIVE")
        if self.dirty != {"content": [], "maps": []}:
            raise TOOL.PlanError("DIRTY_CENSUS|%s" % self.dirty)

    def probe(self):
        children = [copy.deepcopy(row) for row in self.snapshot_value["bindings"]
                    if row.get("parent") == TOOL.MOUTH_GUID]
        selected = []
        required = {(TOOL.FLOAT_CLASS, "CurrentFocalLength"),
                    (TOOL.FLOAT_CLASS, "ManualFocusDistance")}
        for row in children:
            signature = {(item.get("class"), item.get("property")) for item in row.get("tracks", [])}
            if required.issubset(signature):
                selected.append(row["guid"])
        return {"sequence": TOOL.SEQ_PATH, "parent_guid": TOOL.MOUTH_GUID,
                "expected_component_path": "/Fake/CameraComponent",
                "selected_by_tracks": selected,
                "selected_binds_expected_component": len(selected) == 1,
                "children": children, "all_bindings": copy.deepcopy(self.snapshot_value["bindings"]),
                "census": self.census()}

    def inspect(self):
        children = [row for row in self.snapshot_value["bindings"] if row.get("parent") == TOOL.MOUTH_GUID]
        component = TOOL._component_binding(self.snapshot_value, TOOL.MOUTH_GUID) if children else None
        return {"snapshot": copy.deepcopy(self.snapshot_value),
                "mouth_component_guid": component["guid"] if component is not None else None,
                "hangar_camera": copy.deepcopy(self.hangar_camera), "mouth_camera": copy.deepcopy(self.mouth_camera)}

    def backup(self, run):
        self.events.append("backup")
        return {"root": "FAKE/Backups/PreI2MoveIn-%s" % run,
                "files": [{"package": TOOL.SEQ_PATH, "sha256": "fake", "bytes": 1}]}

    def apply(self, plan):
        if self.events != ["backup"]:
            raise AssertionError("mutation preceded backup")
        self.events.append("apply")
        expected = TOOL.expected_owned_tracks(self.snapshot_value, plan)
        hangar = TOOL._binding(self.snapshot_value, TOOL.HANGAR_GUID)
        mouth = TOOL._binding(self.snapshot_value, TOOL.MOUTH_GUID)
        mouth_component_created = bool(plan.get("create_mouth_component"))
        if mouth_component_created:
            mouth_component_guid = "C5273C9D4C80612C7E84CFA8EC530EA3"
            mouth_comp = {"guid": mouth_component_guid, "name": TOOL.MOUTH_COMPONENT_NAME,
                          "parent": TOOL.MOUTH_GUID, "tracks": []}
            self.snapshot_value["bindings"].append(mouth_comp)
        else:
            mouth_component_guid = plan["guids"]["mouth_component"]
            mouth_comp = TOOL._binding(self.snapshot_value, mouth_component_guid)
        hangar["tracks"].append(copy.deepcopy(expected["hangar_transform"]))
        child_guid = "B4162B8C4B7F601B6D73BF97DB42FD92"
        self.snapshot_value["bindings"].append({"guid": child_guid, "name": TOOL.HANGAR_COMPONENT_NAME,
                                                 "parent": TOOL.HANGAR_GUID,
                                                 "tracks": [copy.deepcopy(expected["hangar_focal"]),
                                                            copy.deepcopy(expected["hangar_focus"])]})
        mouth["tracks"] = [copy.deepcopy(expected["mouth_transform"])]
        mouth_comp["tracks"] = [copy.deepcopy(expected["mouth_focal"]), copy.deepcopy(expected["mouth_focus"])]
        for row in self.snapshot_value["bindings"]:
            row["tracks"].sort(key=lambda item: (item["class"], item["property"], item["display_name"]))
        self.snapshot_value["bindings"].sort(key=lambda row: (row["guid"], row["name"]))
        self.dirty = {"content": [TOOL.SEQ_PATH], "maps": []}
        return {"hangar_component_guid": child_guid, "mouth_component_guid": mouth_component_guid,
                "mouth_component_created": mouth_component_created}

    def verify_evaluation(self, plan, mutation=None):
        return []

    def save(self):
        if self.dirty != {"content": [TOOL.SEQ_PATH], "maps": []}:
            raise TOOL.PlanError("FAKE_SAVE_SCOPE")
        self.events.append("save")
        self.dirty = {"content": [], "maps": []}
        return [TOOL.SEQ_PATH]

    def revert(self, record):
        if not self.events or self.events[-1] != "backup":
            raise AssertionError("revert preceded backup")
        self.events.append("revert")
        self.snapshot_value = copy.deepcopy(record["snapshot_before"])
        self.dirty = {"content": [TOOL.SEQ_PATH], "maps": []}


def fresh_case():
    root = tempfile.mkdtemp(prefix="i2movein-harness-")
    snapshot = fixture_snapshot()
    evidence = write_fixture_evidence(root, snapshot)
    params = copy.deepcopy(TOOL.DEFAULTS)
    params["evidence"] = evidence
    return root, FakeUnreal(snapshot), params


def args(mode, params, run):
    return {"mode": mode, "run_id": run, "confirm": "%s I2MOVEIN" % mode, "params": params}


def expect_stop(function, contains):
    try:
        function()
    except TOOL.Stop as error:
        if contains not in str(error):
            raise AssertionError("wanted %r in %s" % (contains, error))
        return
    raise AssertionError("expected Stop containing %r" % contains)


def positive_plan_math():
    root, env, params = fresh_case()
    p = TOOL.merged_params(params)
    plan = TOOL.build_plan(env.inspect(), TOOL.load_evidence(p), p)
    assert abs(plan["cut_match"]["hangar_distance_cm"] - 600.0) < 1.0e-6
    assert abs(plan["cut_match"]["mouth_distance_cm"] - 600.0) < 1.0e-6
    assert plan["coverage"]["hangar"]["1250"]["fills_frame"]
    assert plan["coverage"]["mouth"]["1250"]["fills_frame"]
    assert abs(TOOL.coverage_for_pose(TOOL.pose_at(plan, "hangar", 1249), plan["hangar_drape"],
                                      plan["drape_bounds"], plan["hfov_deg"], plan["output_aspect"],
                                      plan["edge_guard_cm"])["distance_to_plane_cm"] - 600.0) < 1.0e-6
    assert plan["mouth"]["ease_end_frame"] == 1400
    assert plan["playback"] == [0, 1950]
    assert plan["guids"]["mouth_component"] == SHIFTED_MOUTH_COMPONENT_GUID


def positive_round_trip():
    root, env, params = fresh_case()
    TOOL.main(args("DRY", params, "HARNESS-DRY"), backend=env, tool_root=root)
    before = copy.deepcopy(env.snapshot_value)
    TOOL.main(args("APPLY", params, "HARNESS-APPLY"), backend=env, tool_root=root)
    assert env.snapshot_value != before
    assert env.events[:3] == ["backup", "apply", "save"]
    env.events = []
    TOOL.main(args("REVERT", params, "HARNESS-REVERT"), backend=env, tool_root=root)
    assert env.snapshot_value == before
    assert env.events == ["backup", "revert", "save"]
    assert any("I2_MOVE_IN_REVERT_OK" in row for row in env.logs)


def negative_missing_child_never_created():
    # Batch 1g: the child always exists live; an unresolved child means a GUID/lookup bug, so refuse (no duplicate).
    root, env, params = fresh_case()
    env.snapshot_value["bindings"] = [row for row in env.snapshot_value["bindings"]
                                      if row.get("guid") != SHIFTED_MOUTH_COMPONENT_GUID]
    env.original = copy.deepcopy(env.snapshot_value)
    before = copy.deepcopy(env.snapshot_value)
    expect_stop(lambda: TOOL.main(args("DRY", params, "MISSING-DRY"), backend=env, tool_root=root),
                "MOUTH_COMPONENT_NOT_RESOLVED")
    assert env.snapshot_value == before


def _retired_positive_missing_child_create_round_trip():
    root, env, params = fresh_case()
    env.snapshot_value["bindings"] = [row for row in env.snapshot_value["bindings"]
                                      if row.get("guid") != SHIFTED_MOUTH_COMPONENT_GUID]
    env.original = copy.deepcopy(env.snapshot_value)
    before = copy.deepcopy(env.snapshot_value)
    dry = TOOL.main(args("DRY", params, "MISSING-DRY"), backend=env, tool_root=root)
    assert dry["plan"]["create_mouth_component"] is True
    assert dry["plan"]["guids"]["mouth_component"] is None
    TOOL.main(args("APPLY", params, "MISSING-APPLY"), backend=env, tool_root=root)
    created = [row for row in env.snapshot_value["bindings"]
               if row.get("parent") == TOOL.MOUTH_GUID]
    assert len(created) == 1
    assert {item["property"] for item in created[0]["tracks"]} == {
        "CurrentFocalLength", "ManualFocusDistance"}
    for item in created[0]["tracks"]:
        keys = item["sections"][0]["channels"][0]["keys"]
        assert keys[0][0] == 0 and keys[1][0] == 1249
        assert keys[0][1] == keys[1][1]
    env.events = []
    TOOL.main(args("REVERT", params, "MISSING-REVERT"), backend=env, tool_root=root)
    assert env.snapshot_value == before


def positive_missing_child_probe_lists_all_bindings():
    root, env, params = fresh_case()
    env.snapshot_value["bindings"] = [row for row in env.snapshot_value["bindings"]
                                      if row.get("guid") != SHIFTED_MOUTH_COMPONENT_GUID]
    before = copy.deepcopy(env.snapshot_value)
    result = TOOL.main(args("PROBE", params, "MISSING-PROBE"), backend=env, tool_root=root)
    assert result["children"] == []
    assert result["selected_by_tracks"] == []
    assert len(result["all_bindings"]) == len(before["bindings"])
    assert env.snapshot_value == before


def negative_moved_cut():
    root, env, params = fresh_case()
    env.snapshot_value["cuts"][0]["range"] = [0, 1249]
    params["cut_frame"] = 1250
    env.snapshot_value["cuts"][1]["range"] = [1249, 1950]
    expect_stop(lambda: TOOL.main(args("DRY", params, "NEG-CUT"), backend=env, tool_root=root), "CUT_FRAME_ARG")


def negative_rebound_camera():
    root, env, params = fresh_case()
    env.snapshot_value["cuts"][0]["binding_guid"] = "79E6AD814115D22A888C409AA2F57A77"
    expect_stop(lambda: TOOL.main(args("DRY", params, "NEG-GUID"), backend=env, tool_root=root), "HANGAR_MOUTH_CUT_COUNT")


def negative_duplicate_cut_boundary():
    root, env, params = fresh_case()
    duplicate = copy.deepcopy(env.snapshot_value["cuts"][1])
    duplicate["section_index"] = 2
    env.snapshot_value["cuts"].append(duplicate)
    expect_stop(lambda: TOOL.main(args("DRY", params, "NEG-DUP-CUT"), backend=env, tool_root=root),
                "HANGAR_MOUTH_CUT_COUNT")


def negative_ambiguous_mouth_component():
    root, env, params = fresh_case()
    duplicate = copy.deepcopy(TOOL._binding(env.snapshot_value, SHIFTED_MOUTH_COMPONENT_GUID))
    duplicate["guid"] = "E6284DAE5D91723D8F95D0B9FD641FB3"
    duplicate["name"] = "Foreign CameraComponent"
    env.snapshot_value["bindings"].append(duplicate)
    expect_stop(lambda: TOOL.main(args("DRY", params, "NEG-DUP-COMP"), backend=env, tool_root=root),
                "MOUTH_COMPONENT_TRACK_BINDING_COUNT")


def negative_edge_in_frame():
    root, env, params = fresh_case()
    params["close_distance_cm"] = 2600.0
    expect_stop(lambda: TOOL.main(args("DRY", params, "NEG-EDGE"), backend=env, tool_root=root), "EDGE_IN_FRAME_AT_CUT")


def negative_pie_running():
    root, env, params = fresh_case()
    env.pie = True
    expect_stop(lambda: TOOL.main(args("DRY", params, "NEG-PIE"), backend=env, tool_root=root), "PIE_OR_SIE_ACTIVE")


def negative_dirty_census():
    root, env, params = fresh_case()
    env.dirty = {"content": ["/Game/Foreign"], "maps": []}
    expect_stop(lambda: TOOL.main(args("DRY", params, "NEG-DIRTY"), backend=env, tool_root=root), "DIRTY_CENSUS")


def negative_existing_hangar_track():
    root, env, params = fresh_case()
    TOOL._binding(env.snapshot_value, TOOL.HANGAR_GUID)["tracks"].append(
        track(TOOL.TRANSFORM_CLASS, "Foreign", "Transform", "Transform", [], 1251))
    expect_stop(lambda: TOOL.main(args("DRY", params, "NEG-H-TRACK"), backend=env, tool_root=root),
                "EXISTING_HANGAR_TRANSFORM_TRACK")


def negative_changed_since_dry():
    root, env, params = fresh_case()
    TOOL.main(args("DRY", params, "DRIFT-DRY"), backend=env, tool_root=root)
    env.snapshot_value["markers"].append(["Foreign", 42])
    expect_stop(lambda: TOOL.main(args("APPLY", params, "DRIFT-APPLY"), backend=env, tool_root=root),
                "I2_CHANGED_SINCE_DRY")
    assert env.events == []


def negative_mouth_constant():
    root, env, params = fresh_case()
    transform = TOOL._track(TOOL._binding(env.snapshot_value, TOOL.MOUTH_GUID), TOOL.TRANSFORM_CLASS, "Transform")
    TOOL._channel(transform, "Location.X")["keys"][1][1] += 1.0
    expect_stop(lambda: TOOL.main(args("DRY", params, "NEG-MOUTH"), backend=env, tool_root=root),
                "RECORDED_CONSTANT_VALUES")


def negative_confirm():
    root, env, params = fresh_case()
    bad = args("DRY", params, "NEG-CONFIRM")
    bad["confirm"] = "yes"
    expect_stop(lambda: TOOL.main(bad, backend=env, tool_root=root), "CONFIRM_MISMATCH")


def positive_preview_files():
    root, env, params = fresh_case()
    report = TOOL.main(args("DRY", params, "PREVIEW"), backend=env, tool_root=root)
    assert len(report["previews"]) == 2
    for path in report["previews"]:
        assert os.path.getsize(path) > 500


def positive_probe_is_read_only():
    root, env, params = fresh_case()
    before = copy.deepcopy(env.snapshot_value)
    result = TOOL.main(args("PROBE", params, "PROBE"), backend=env, tool_root=root)
    assert result["children"][0]["guid"] == SHIFTED_MOUTH_COMPONENT_GUID
    assert result["selected_by_tracks"] == [SHIFTED_MOUTH_COMPONENT_GUID]
    assert result["selected_binds_expected_component"] is True
    assert env.snapshot_value == before
    assert env.events == []
    assert any("I2_MOVE_IN_PROBE_OK" in row for row in env.logs)


def positive_import_offline():
    assert TOOL.UnrealBackend.__name__ == "UnrealBackend"


CASES = [
    ("+ LIVE cut, shifted child GUID, shrunk sequence produce matched cut", positive_plan_math),
    ("+ fake Unreal APPLY->REVERT is exact", positive_round_trip),
    ("- unresolved mouth child is never created (refuses)", negative_missing_child_never_created),
    ("+ missing-child PROBE emits the complete binding inventory", positive_missing_child_probe_lists_all_bindings),
    ("- explicit stale cut arg refuses", negative_moved_cut),
    ("- rebound hangar camera refuses", negative_rebound_camera),
    ("- duplicate hangar/mouth boundary refuses", negative_duplicate_cut_boundary),
    ("- ambiguous mouth component child refuses", negative_ambiguous_mouth_component),
    ("- edge-in-frame close distance refuses", negative_edge_in_frame),
    ("- PIE running refuses", negative_pie_running),
    ("- dirty census refuses", negative_dirty_census),
    ("- existing hangar transform track refuses", negative_existing_hangar_track),
    ("- full I2 snapshot drift since DRY refuses before backup", negative_changed_since_dry),
    ("- mouth recorded constant drift refuses", negative_mouth_constant),
    ("- wrong confirm refuses", negative_confirm),
    ("+ analytical preview files are emitted", positive_preview_files),
    ("+ PROBE inventories the shifted child without mutation", positive_probe_is_read_only),
    ("+ module imports without Unreal", positive_import_offline),
]


def main():
    results = []
    for name, function in CASES:
        try:
            function()
            results.append({"name": name, "status": "PASS"})
            print("PASS|%s" % name)
        except Exception as error:  # noqa: BLE001
            results.append({"name": name, "status": "FAIL", "error": "%s: %s" % (type(error).__name__, error),
                            "traceback": traceback.format_exc()})
            print("FAIL|%s|%s" % (name, error))
    report = {"passed": len([row for row in results if row["status"] == "PASS"]),
              "failed": len([row for row in results if row["status"] == "FAIL"]),
              "total": len(results), "results": results}
    TOOL.json_write(os.path.join(HERE, "harness_result.json"), report)
    print("I2_MOVE_IN_HARNESS|passed=%d|failed=%d|total=%d" % (report["passed"], report["failed"], report["total"]))
    if report["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
