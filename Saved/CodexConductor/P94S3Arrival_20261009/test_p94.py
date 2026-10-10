"""Offline positive/negative harness for Codex job 94."""
import importlib.util
import json
import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "p94_s3_arrival.py")
RESULTS = []


def load():
    sys.modules.pop("unreal", None)
    spec = importlib.util.spec_from_file_location("p94_s3_arrival_harness", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def case(name, function):
    try:
        function()
        RESULTS.append({"name": name, "status": "PASS"})
    except Exception as exc:  # noqa: BLE001
        RESULTS.append({"name": name, "status": "FAIL", "detail": "%s: %s" % (type(exc).__name__, exc)})


def refuses(function, token):
    try:
        function()
    except Exception as exc:  # noqa: BLE001
        assert token in str(exc), (token, str(exc))
        return
    raise AssertionError("did not refuse " + token)


def test_defaults():
    p = load().merged_params({})
    assert (p["light_rise_root_frame"], p["light_full_root_frame"]) == (372, 444)
    assert (p["light_rise_child_frame"], p["light_full_child_frame"]) == (465, 555)


def test_enum_normalise():
    mod = load()
    assert mod.enum_token("<MovieSceneBlendType.ADDITIVE: 2>") == "ADDITIVE"


def test_enum_member():
    class Value:
        name = "RCIM_LINEAR"
    assert load().enum_token(Value()) == "RCIM_LINEAR"


def test_channel_suffixes():
    mod = load()
    assert mod.canonical_channel_name("Value_12") == mod.canonical_channel_name("Value")
    assert mod.canonical_channel_name("Rotation.X 3") == "rotation.x"


def test_unreal_none_property_sentinel():
    mod = load()
    class Sentinel:
        def __str__(self):
            return "None"
    class Track:
        def get_property_name(self):
            return Sentinel()
        def get_property_path(self):
            return Sentinel()
    assert mod._track_property(Track()) == ("", "")


def test_inert_visibility_property_not_normalised():
    mod = load()
    class Track:
        def get_property_name(self):
            return "bHiddenInGame"
        def get_property_path(self):
            return "bHiddenInGame"
    assert mod._track_property(Track()) == ("bHiddenInGame", "bHiddenInGame")


def test_parent_child():
    mod = load()
    assert mod.root_to_child(372) == 465 and mod.root_to_child(444) == 555


def test_nonintegral_parent_child():
    refuses(lambda: load().root_to_child(1), "NONINTEGRAL")


def test_two_key_retime():
    assert load().retime_pairs([-176, 124], [0, 160], 465, 555) == [465, 555]


def test_three_key_retime():
    assert load().retime_pairs([0, 300, 306], [0, 0, 1600], 465, 555) == [0, 465, 555]


def test_bad_shape():
    refuses(lambda: load().retime_pairs([0], [0], 465, 555), "LIGHT_KEY_SHAPE")


def test_not_dark():
    refuses(lambda: load().retime_pairs([0, 300, 306], [1, 0, 10], 465, 555), "DARK_LEADING")


def test_second_not_dark():
    refuses(lambda: load().retime_pairs([0, 300, 306], [0, 1, 10], 465, 555), "SECOND_KEY")


def test_shift_fire():
    frames, delta = load().shift_from([0, 230, 232, 6239], 230, 372, 6240)
    assert frames == [0, 372, 374, 6381] and delta == 142


def test_shift_fire_early_refuses():
    refuses(lambda: load().shift_from([0, 230], 230, 100, 6240), "BEFORE_SOURCE")


def test_gate_wave_ramp():
    got = load().gate_values([0, 360, 372, 408, 444, 446], [0, 0, 10, 10, 10, 10], 360, 372, 444)
    assert got == [0, 0, 0, 5, 10, 10]


def test_gate_bad_order_refuses():
    refuses(lambda: load().gate_values([360], [1], 360, 372, 371), "SHAPE_OR_ORDER")


def test_copy_count_guard():
    refuses(lambda: load().merged_params({"crowd_copy_count": 14}), "CROWD_COPY_COUNT")


def test_negative_settle():
    refuses(lambda: load().merged_params({"settle_padding_frames": -1}), "SETTLE_PADDING")


def test_short_rise():
    refuses(lambda: load().merged_params({"rise_duration_frames": 23}), "RISE_DURATION")


def test_long_rise():
    refuses(lambda: load().merged_params({"rise_duration_frames": 145}), "RISE_DURATION")


def test_import_has_no_unreal():
    load()
    assert "unreal" not in sys.modules


def test_contract_source():
    source = open(TOOL, encoding="utf-8").read()
    required = [
        "conv_guid_to_string", "set_property_name_and_path(\"bHidden\", \"bHidden\")",
        "get_property_name()", "get_property_path()", "EXACT_DIRTY_CENSUS",
        "save_asset(package, only_if_is_dirty=False)", "P94_S3_ARRIVAL_APPLY_OK",
        "P94_S3_ARRIVAL_REVERT_OK", "P94_S3_ARRIVAL_DRY_OK",
    ]
    assert all(token in source for token in required)
    assert "str(binding.get_id())" not in source
    assert "bHiddenInGame" not in source


def test_args_confirm():
    args = json.load(open(os.path.join(HERE, "p94_args.json"), encoding="utf-8"))
    assert args["mode"] == "DRY" and args["confirm"] == "DRY P94S3ARRIVAL"


def main():
    tests = [
        ("+ default darkness/settle/rise frames", test_defaults),
        ("+ UE enum string normalises", test_enum_normalise),
        ("+ enum accessor normalises", test_enum_member),
        ("+ channel suffixes normalise", test_channel_suffixes),
        ("+ Unreal None property sentinel becomes unbound", test_unreal_none_property_sentinel),
        ("- inert bHiddenInGame remains rejectable", test_inert_visibility_property_not_normalised),
        ("+ 24-to-30 fps mapping", test_parent_child),
        ("- non-integral frame mapping refuses", test_nonintegral_parent_child),
        ("+ two-key dim rig ramp retimes", test_two_key_retime),
        ("+ three-key strike ramp retimes", test_three_key_retime),
        ("- malformed light channel refuses", test_bad_shape),
        ("- illuminated first key refuses", test_not_dark),
        ("- illuminated hold key refuses", test_second_not_dark),
        ("+ fire reveal shifts and preserves tail", test_shift_fire),
        ("- fire cannot move earlier", test_shift_fire_early_refuses),
        ("+ wave values gate after crowd settle", test_gate_wave_ramp),
        ("- wave value gate order refuses", test_gate_bad_order_refuses),
        ("- crowd census default cannot drift", test_copy_count_guard),
        ("- negative settle pad refuses", test_negative_settle),
        ("- sub-second light rise refuses", test_short_rise),
        ("- over-six-second light rise refuses", test_long_rise),
        ("+ module imports without Unreal", test_import_has_no_unreal),
        ("+ source contains UE 5.8 safety contract", test_contract_source),
        ("+ shipped args are safe DRY", test_args_confirm),
    ]
    for name, function in tests:
        case(name, function)
    passed = sum(row["status"] == "PASS" for row in RESULTS)
    report = {"passed": passed, "failed": len(RESULTS) - passed, "total": len(RESULTS), "results": RESULTS}
    with open(os.path.join(HERE, "harness_result.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    for row in RESULTS:
        print("%-4s %s%s" % (row["status"], row["name"],
                             " | " + row.get("detail", "") if row.get("detail") else ""))
    print("P94_HARNESS|pass=%d|fail=%d|total=%d" % (passed, len(RESULTS) - passed, len(RESULTS)))
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
