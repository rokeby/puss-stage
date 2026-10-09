"""Offline positive/negative/seeded-mutation harness for P29."""
import copy
import importlib.util
import json
import os
import sys
import types


HERE = os.path.dirname(os.path.abspath(__file__))
TOOL_PATH = os.path.join(HERE, "s1_rig_fade.py")


def load_tool(name="s1_rig_fade_tested"):
    spec = importlib.util.spec_from_file_location(name, TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EnumValue:
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name


class FrameNumber:
    def __init__(self, value):
        self.value = int(value)


class FrameTime:
    def __init__(self, frame):
        self.frame_number = FrameNumber(frame)
        self.sub_frame = 0.0


class ClassValue:
    def __init__(self, name):
        self.name = name

    def get_name(self):
        return self.name


class Key:
    def __init__(self, frame, value, interp="RCIM_CONSTANT"):
        self.frame, self.value, self.interp = int(frame), float(value), interp

    def get_time(self, time_unit=None):
        del time_unit
        return FrameTime(self.frame)

    def set_time(self, frame, sub_frame, time_unit):
        del sub_frame, time_unit
        self.frame = int(frame.value)

    def get_value(self):
        return self.value

    def get_interpolation_mode(self):
        return EnumValue(self.interp)

    def set_interpolation_mode(self, value):
        self.interp = value.name


class Channel:
    channel_name = "Value"

    def __init__(self, env, keys=None, default=None):
        self.env = env
        self.keys = list(keys or [])
        self.default = default

    def get_keys(self):
        return list(self.keys)

    def has_default(self):
        return self.default is not None

    def get_default(self):
        return self.default

    def add_key(self, frame, value, time_unit=None, interpolation=None):
        del time_unit
        key = Key(frame.value, value, interpolation.name if interpolation else "RCIM_CONSTANT")
        self.keys.append(key)
        self.keys.sort(key=lambda row: row.frame)
        return key

    def evaluate_keys(self, rng, rate):
        del rate
        if self.env.bad_evaluate_count:
            return []
        out = []
        for frame in range(rng[0], rng[0] + rng[1]):
            keys = sorted(self.keys, key=lambda row: row.frame)
            if not keys:
                out.append(self.default)
            elif frame <= keys[0].frame:
                out.append(keys[0].value)
            elif frame >= keys[-1].frame:
                out.append(keys[-1].value)
            else:
                left, right = next((a, b) for a, b in zip(keys, keys[1:]) if a.frame <= frame <= b.frame)
                alpha = (frame - left.frame) / float(right.frame - left.frame)
                out.append(left.value + (right.value - left.value) * alpha)
        return out


class Section:
    def __init__(self, env, channel=None):
        self.env = env
        self.channel = channel or Channel(env)
        self.start, self.end, self.active, self.completion = 0, 0, True, None

    def set_range(self, start, end):
        self.start, self.end = int(start), int(end)

    def get_start_frame(self):
        return self.start

    def get_end_frame(self):
        return self.end

    def has_start_frame(self):
        return True

    def has_end_frame(self):
        return True

    def is_active(self):
        return self.active

    def set_completion_mode(self, value):
        self.completion = value

    def get_all_channels(self):
        return [self.channel]


class Track:
    def __init__(self, env, cls="MovieSceneFloatTrack", prop="", path=""):
        self.env, self.cls, self.prop, self.path = env, cls, prop, path
        self.display = "Visibility" if cls == "MovieSceneVisibilityTrack" else "Float"
        self.sections = []

    def get_class(self):
        return ClassValue(self.cls)

    def set_property_name_and_path(self, prop, path):
        self.prop, self.path = str(prop), str(path)

    def get_property_name(self):
        return self.prop

    def get_property_path(self):
        return self.path

    def set_display_name(self, value):
        self.display = str(value)

    def get_display_name(self):
        return self.display

    def add_section(self):
        section = Section(self.env)
        self.sections.append(section)
        return section

    def get_sections(self):
        return list(self.sections)


class Guid:
    def __init__(self, text):
        self.text = text


class InvalidParent:
    def is_valid(self):
        return False


class Binding:
    def __init__(self, env, guid, name="Binding"):
        self.env, self.guid, self.name = env, guid, name
        self.parent, self.tracks = None, []

    def get_id(self):
        return Guid(self.guid)

    def get_display_name(self):
        return self.name

    def set_display_name(self, value):
        self.name = str(value)

    def get_parent(self):
        return self.parent if self.parent else InvalidParent()

    def set_parent(self, value):
        self.parent = value

    def get_tracks(self):
        return list(self.tracks)

    def add_track(self, cls):
        del cls
        track = Track(self.env)
        self.tracks.append(track)
        return track

    def remove_track(self, track):
        self.tracks.remove(track)


class Component:
    def __init__(self, path, name="LightComponent0"):
        self.path, self.name = path, name

    def get_path_name(self):
        return self.path

    def get_name(self):
        return self.name


class Rate:
    numerator, denominator = 25, 1


class Sequence:
    def __init__(self, env):
        self.env = env
        self.bindings = []
        self.bound = {}

    def get_bindings(self):
        return list(self.bindings)

    def locate_bound_objects(self, binding, world):
        del world
        return list(self.bound.get(binding.guid, []))

    def add_possessable(self, component):
        if self.env.return_existing:
            return self.bindings[-1]
        binding = Binding(self.env, "NEW-%d" % (len(self.bindings) + 1))
        self.bindings.append(binding)
        self.bound[binding.guid] = [component]
        return binding

    def make_range(self, start, duration):
        return int(start), int(duration)

    def get_display_rate(self):
        return Rate()


class Env:
    def __init__(self):
        self.bad_evaluate_count = False
        self.return_existing = False
        self.unreal = types.ModuleType("unreal")
        self.unreal.MovieSceneFloatTrack = "MovieSceneFloatTrack"
        self.unreal.MovieSceneKeyInterpolation = types.SimpleNamespace(LINEAR=EnumValue("RCIM_LINEAR"))
        self.unreal.RichCurveInterpMode = types.SimpleNamespace(RCIM_LINEAR=EnumValue("RCIM_LINEAR"),
                                                               RCIM_CONSTANT=EnumValue("RCIM_CONSTANT"))
        self.unreal.MovieSceneTimeUnit = types.SimpleNamespace(DISPLAY_RATE="DISPLAY_RATE")
        self.unreal.MovieSceneCompletionMode = types.SimpleNamespace(RESTORE_STATE="RESTORE_STATE")
        self.unreal.FrameNumber = FrameNumber
        self.unreal.GuidLibrary = types.SimpleNamespace(conv_guid_to_string=lambda value: value.text)
        sys.modules["unreal"] = self.unreal
        self.mod = load_tool("s1_rig_fade_fake")
        self.seq = Sequence(self)


def candidate(label="Infinity Stage - Dusk Sun", mechanism="visibility", switch=269, **extra):
    row = {"mechanism": mechanism, "switch_frame": switch, "light_label": label,
           "property": "Intensity", "base_value": 3.0, "target_object_path": "/World/" + label,
           "visibility_binding_guid": "VIS-" + label, "unsupported": False}
    row.update(extra)
    return row


RESULTS = []


def case(name, function):
    try:
        function()
        RESULTS.append({"name": name, "status": "PASS"})
    except Exception as error:  # noqa: BLE001
        RESULTS.append({"name": name, "status": "FAIL", "detail": "%s: %s" % (type(error).__name__, error)})


def expect_error(function, text):
    try:
        function()
    except Exception as error:  # noqa: BLE001
        assert text in str(error), (text, str(error))
        return
    raise AssertionError("did not raise " + text)


def test_defaults():
    mod = load_tool()
    p = mod.merged_params({})
    assert (p["fade_frames"], p["scene_local_switch_frame"], p["expected_target_scene_frame"]) == (38, 282, 783)


def test_master_clock_mapping():
    mod = load_tool()
    row = mod.map_master_time(224.0, 4624705.0 / 24000.0, 25.0, 10553665.0 / 24000.0)
    assert row["scene_frame"] == 783 and abs(row["scene_frame_exact"] - 782.5989583333334) < 1.0e-9


def test_master_clock_outside_refuses():
    mod = load_tool()
    expect_error(lambda: mod.map_master_time(190.0, 192.0, 25.0, 300.0), "OUTSIDE_MASTER_SECTION")


def test_short_fade():
    expect_error(lambda: load_tool().merged_params({"fade_seconds": 0.99}), "FADE_SECONDS")


def test_long_fade():
    expect_error(lambda: load_tool().merged_params({"fade_seconds": 2.01}), "FADE_SECONDS")


def test_negative_radius():
    expect_error(lambda: load_tool().merged_params({"search_radius_frames": -1}), "SEARCH_RADIUS")


def test_pair():
    mod = load_tool()
    p = mod.merged_params({})
    assert mod.pair_glow_label("S1 Lattice Bulb 2-7", p) == "S1 Lattice Glow 2-7"
    assert mod.pair_glow_label("Infinity Stage - Moon", p) is None


def test_plan_positive():
    mod = load_tool()
    p = mod.merged_params({})
    plan = mod.make_plan([candidate(switch=269), candidate(label="S1 Lattice Bulb 1-1", switch=282,
                                                           mechanism="visibility_paired_glow")], p)
    assert [r["source_switch_frame"] for r in plan["targets"]] == [269, 282]
    assert [r["switch_frame"] for r in plan["targets"]] == [783, 783]
    assert [r["fade_start_frame"] for r in plan["targets"]] == [745, 745]


def test_plan_filters_outside():
    mod = load_tool()
    p = mod.merged_params({})
    plan = mod.make_plan([candidate(switch=269), candidate(label="Far", switch=400)], p)
    assert len(plan["targets"]) == 1


def test_no_target():
    mod = load_tool()
    expect_error(lambda: mod.make_plan([candidate(switch=400)], mod.merged_params({})), "NO_RIG_LIGHT")


def test_duplicate():
    mod = load_tool()
    row = candidate()
    expect_error(lambda: mod.make_plan([row, copy.deepcopy(row)], mod.merged_params({})), "DUPLICATE_TARGET")


def test_unsupported():
    mod = load_tool()
    row = candidate(unsupported=True, reason="NO_LIGHT")
    expect_error(lambda: mod.make_plan([row], mod.merged_params({})), "UNSUPPORTED_VISIBILITY")


def test_write_ramp():
    env = Env()
    binding = Binding(env, "B1")
    plan = dict(candidate(), fade_start_frame=231)
    track = env.mod._write_ramp(env.seq, binding, plan, "HARNESS")
    assert (track.prop, track.path) == ("Intensity", "Intensity")
    assert [(k.frame, k.value, k.interp) for k in track.sections[0].channel.keys] == [
        (231, 3.0, "RCIM_LINEAR"), (269, 0.0, "RCIM_LINEAR")]
    assert (track.sections[0].start, track.sections[0].end) == (231, 270)


def test_eval_count_guard():
    env = Env()
    env.bad_evaluate_count = True
    binding = Binding(env, "B1")
    plan = dict(candidate(), fade_start_frame=231)
    expect_error(lambda: env.mod._write_ramp(env.seq, binding, plan, "HARNESS"), "EVALUATE_COUNT")


def test_bind_new():
    env = Env()
    parent = Binding(env, "ACTOR", "Actor")
    env.seq.bindings.append(parent)
    component = Component("/World/Actor.Light")
    binding, created, returned = env.mod._bind_component(env.seq, component, "ACTOR", object(), "HARNESS")
    assert created and not returned and binding.parent is parent and binding.name.startswith("S1 Rig Fade")


def test_bind_existing_lookup():
    env = Env()
    existing = Binding(env, "EXISTING", "Do Not Rename")
    component = Component("/World/Actor.Light")
    env.seq.bindings.append(existing)
    env.seq.bound[existing.guid] = [component]
    binding, created, returned = env.mod._bind_component(env.seq, component, "ACTOR", object(), "HARNESS")
    assert binding is existing and not created and not returned and binding.name == "Do Not Rename"


def test_add_returns_existing():
    env = Env()
    existing = Binding(env, "EXISTING", "Still Do Not Rename")
    env.seq.bindings.append(existing)
    env.return_existing = True
    binding, created, returned = env.mod._bind_component(
        env.seq, Component("/World/New.Light"), "ACTOR", object(), "HARNESS")
    assert binding is existing and not created and returned and binding.name == "Still Do Not Rename"


def test_retime_step():
    env = Env()
    binding = Binding(env, "B1", "Light")
    track = Track(env, prop="Intensity", path="Intensity")
    section = Section(env, Channel(env, [Key(268, 3.0), Key(269, 0.0)]))
    section.set_range(0, 1000)
    track.sections.append(section)
    binding.tracks.append(track)
    plan = dict(candidate(mechanism="intensity_step", switch=783), fade_start_frame=745, key_index=0,
                end_key_index=1, original_key=env.mod._key_row(section.channel.keys[0]),
                original_end_key=env.mod._key_row(section.channel.keys[1]), target_binding_guid="B1")
    env.mod._retime_step(env.seq, binding, plan, "HARNESS")
    assert section.channel.keys[0].frame == 745 and section.channel.keys[0].interp == "RCIM_LINEAR"
    assert section.channel.keys[1].frame == 783


def test_retime_visibility():
    env = Env()
    binding = Binding(env, "VIS", "S1 Lattice Bulb 1-1")
    track = Track(env, cls="MovieSceneVisibilityTrack", prop="bHidden", path="bHidden")
    section = Section(env, Channel(env, [Key(282, 0.0)], default=1.0))
    section.set_range(282, 6001)
    track.sections.append(section)
    binding.tracks.append(track)
    changed, index, before, after = env.mod._retime_visibility(
        env.seq, binding, {"source_switch_frame": 282, "switch_frame": 783,
                           "light_label": binding.name}, "HARNESS")
    assert changed is track and index == 0 and before == [282, 6001] and after == [783, 6001]


def test_restore_step_after_key_reordering():
    env = Env()
    binding = Binding(env, "B1", "Light")
    track = Track(env, prop="Intensity", path="Intensity")
    section = Section(env, Channel(env, [Key(268, 3.0), Key(269, 0.0), Key(400, 5.0), Key(500, 4.0)]))
    section.set_range(0, 1000)
    track.sections.append(section)
    binding.tracks.append(track)
    original = env.mod._key_row(section.channel.keys[0])
    original_end = env.mod._key_row(section.channel.keys[1])
    plan = dict(candidate(mechanism="intensity_step", switch=783), fade_start_frame=745, key_index=0,
                end_key_index=1, original_key=original, original_end_key=original_end,
                target_binding_guid="B1")
    env.mod._retime_step(env.seq, binding, plan, "HARNESS")
    op = {"property": "Intensity", "original_key": original, "original_end_key": original_end,
          "retimed_start_frame": 745, "retimed_end_frame": 783}
    env.mod._restore_key(track, op, "HARNESS")
    rows = sorted((key.frame, key.value, key.interp) for key in section.channel.keys)
    assert rows == [(268, 3.0, "RCIM_CONSTANT"), (269, 0.0, "RCIM_CONSTANT"),
                    (400, 5.0, "RCIM_CONSTANT"), (500, 4.0, "RCIM_CONSTANT")]


def snapshots_for_scope(mod):
    base_track = {"class": "MovieSceneVisibilityTrack", "property": "bHidden", "path": "bHidden",
                  "display_name": "Visibility", "sections": []}
    before = {"display_rate": 25.0, "tick_resolution": 24000.0, "playback": [0, 6176],
              "root_tracks": [], "markers": [],
              "bindings": [{"guid": "A", "name": "Actor", "parent": "", "tracks": [base_track]}]}
    added = {"class": "MovieSceneFloatTrack", "property": "Intensity", "path": "Intensity",
             "display_name": "S1 Rig Fade - Intensity", "sections": []}
    after = copy.deepcopy(before)
    after["bindings"][0]["tracks"].append(added)
    after["bindings"][0]["tracks"].sort(key=lambda row: (row["class"], row["property"], row["path"], mod.digest(row)))
    before["bindings"][0]["tracks"].sort(key=lambda row: (row["class"], row["property"], row["path"], mod.digest(row)))
    op = {"kind": "new_track", "binding_guid": "A", "binding_created": False, "track_after": added}
    return before, after, op


def test_scope_positive():
    mod = load_tool()
    before, after, op = snapshots_for_scope(mod)
    mod._assert_scoped_change(before, after, [op])


def test_scope_seeded_unrelated():
    mod = load_tool()
    before, after, op = snapshots_for_scope(mod)
    after["markers"] = [["seeded mutation", 1]]
    expect_error(lambda: mod._assert_scoped_change(before, after, [op]), "UNTOUCHED_CHANGED")


def test_scope_seeded_extra_track():
    mod = load_tool()
    before, after, op = snapshots_for_scope(mod)
    after["bindings"][0]["tracks"].append({"class": "MovieSceneFloatTrack", "property": "Other",
                                            "path": "Other", "display_name": "seed", "sections": []})
    after["bindings"][0]["tracks"].sort(key=lambda row: (row["class"], row["property"], row["path"], mod.digest(row)))
    expect_error(lambda: mod._assert_scoped_change(before, after, [op]), "UNSCOPED_TRACK_CHANGE")


def test_import_without_unreal():
    sys.modules.pop("unreal", None)
    mod = load_tool("s1_rig_fade_no_unreal")
    assert hasattr(mod, "main") and "unreal" not in sys.modules


def main():
    case("+ defaults give a 38-frame fade", test_defaults)
    case("+ Master 3:44 maps to S1-local frame 783", test_master_clock_mapping)
    case("- Master time outside S1 refuses", test_master_clock_outside_refuses)
    case("- fade below Gary's 1 s bound refuses", test_short_fade)
    case("- fade above Gary's 2 s bound refuses", test_long_fade)
    case("- negative search radius refuses", test_negative_radius)
    case("+ lattice bulb maps to paired glow", test_pair)
    case("+ planner includes 269 and 282 mechanisms", test_plan_positive)
    case("+ planner filters switches outside the review window", test_plan_filters_outside)
    case("- empty target window refuses", test_no_target)
    case("- duplicate target refuses", test_duplicate)
    case("- unsupported visibility target refuses", test_unsupported)
    case("+ fake Unreal writes linear property ramp", test_write_ramp)
    case("- evaluate_keys count mismatch refuses", test_eval_count_guard)
    case("+ new component binding is parented and named", test_bind_new)
    case("+ existing component binding is reused unchanged", test_bind_existing_lookup)
    case("+ add_possessable returned-existing is not renamed", test_add_returns_existing)
    case("+ fake Unreal retimes one-frame intensity step", test_retime_step)
    case("+ fake Unreal retargets bHidden section", test_retime_visibility)
    case("+ REVERT finds retimed keys after ordering changes", test_restore_step_after_key_reordering)
    case("+ scoped-change proof accepts only recorded track", test_scope_positive)
    case("- seeded marker mutation refuses", test_scope_seeded_unrelated)
    case("- seeded extra track mutation refuses", test_scope_seeded_extra_track)
    case("+ module imports offline without Unreal", test_import_without_unreal)
    for result in RESULTS:
        print("%-4s %s%s" % (result["status"], result["name"],
                             " | " + result.get("detail", "") if result.get("detail") else ""))
    passed = sum(1 for row in RESULTS if row["status"] == "PASS")
    report = {"passed": passed, "failed": len(RESULTS) - passed, "total": len(RESULTS), "results": RESULTS}
    with open(os.path.join(HERE, "harness_result.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    print("S1_RIG_FADE_HARNESS|pass=%d|fail=%d|total=%d" %
          (passed, len(RESULTS) - passed, len(RESULTS)))
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())

