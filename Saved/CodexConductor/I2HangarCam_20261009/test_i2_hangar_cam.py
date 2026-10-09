"""Offline fake-Unreal harness for i2_hangar_cam.py.

No Unreal process, MCP call, PIE session, or project Content package is opened.
Positive, negative, and seeded-mutation controls all exercise the real tool.
"""
import copy
import importlib.util
import json
import math
import os
import shutil
import sys
import tempfile
import types


HERE = os.path.dirname(os.path.abspath(__file__))
TOOL_PATH = os.path.join(HERE, "i2_hangar_cam.py")


class FakeClass:
    def __init__(self, name):
        self.name = name

    def get_name(self):
        return self.name


class EnumValue:
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name


class Guid:
    def __init__(self, text):
        self.text = text


class Struct:
    def __init__(self, **values):
        self.values = dict(values)

    def get_editor_property(self, name):
        if name not in self.values:
            raise AttributeError(name)
        return self.values[name]

    def set_editor_property(self, name, value):
        self.values[name] = value

    def __getattr__(self, name):
        try:
            return self.values[name]
        except KeyError as error:
            raise AttributeError(name) from error


class FrameRate:
    def __init__(self, numerator, denominator=1):
        self.numerator = numerator
        self.denominator = denominator


class FrameNumber:
    def __init__(self, value):
        self.value = int(value)


class Vector:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)


class Rotator:
    def __init__(self, roll=0.0, pitch=0.0, yaw=0.0):
        self.roll, self.pitch, self.yaw = float(roll), float(pitch), float(yaw)


class Name(str):
    pass


class Key:
    def __init__(self, frame, value):
        self.frame, self.value = frame, value

    def get_time(self, time_unit=None):
        del time_unit
        return Struct(frame_number=FrameNumber(self.frame), sub_frame=0.0)

    def get_value(self):
        return self.value


class Channel:
    def __init__(self, name, default, keys):
        self.channel_name = name
        self.default = default
        self.keys = [Key(*row) for row in keys]

    def get_keys(self):
        return list(self.keys)

    def has_default(self):
        return self.default is not None

    def get_default(self):
        return self.default


class Section:
    def __init__(self, env, start, end, channels=None, active=True, camera_guid=None):
        self.env, self.start, self.end = env, start, end
        self.channels, self.active, self.camera_guid = channels or [], active, camera_guid

    def has_start_frame(self):
        return self.start is not None

    def has_end_frame(self):
        return self.end is not None

    def get_start_frame(self):
        return self.start

    def get_end_frame(self):
        return self.end

    def is_active(self):
        return self.active

    def get_all_channels(self):
        return list(self.channels)

    def get_camera_binding_id(self):
        return Struct(guid=Guid(self.camera_guid))

    def set_camera_binding_id(self, binding_id):
        self.camera_guid = binding_id.get_editor_property("guid").text
        self.env.dirty_content.add(self.env.mod.SEQ_PATH)
        if self.env.mutate_unrelated_on_cut and not self.env.mutation_done:
            self.env.mutation_done = True
            self.env.sequence.bindings_by_name("I2 Sleight Mouth Camera")[0].tracks[0].display_name = "MUTATED"


class Track:
    def __init__(self, cls, name, sections=None, prop="", path=""):
        self.cls, self.display_name = cls, name
        self.sections, self.prop, self.path = sections or [], prop, path

    def get_class(self):
        return FakeClass(self.cls)

    def get_display_name(self):
        return self.display_name

    def get_sections(self):
        return list(self.sections)

    def get_property_name(self):
        return self.prop

    def get_property_path(self):
        return self.path


class InvalidBinding:
    def is_valid(self):
        return False


class Binding:
    def __init__(self, env, guid, name, tracks=None, template=None, parent=None):
        self.env, self.guid, self.name = env, guid, name
        self.tracks, self.template, self.parent = tracks or [], template, parent

    def get_id(self):
        return Guid(self.guid)

    def get_display_name(self):
        return self.name

    def set_display_name(self, value):
        self.name = str(value)
        self.env.dirty_content.add(self.env.mod.SEQ_PATH)

    def get_parent(self):
        return self.parent if self.parent is not None else InvalidBinding()

    def get_tracks(self):
        return list(self.tracks)

    def get_object_template(self):
        return self.template

    def is_valid(self):
        return True

    def remove(self):
        self.env.sequence.bindings.remove(self)
        self.env.dirty_content.add(self.env.mod.SEQ_PATH)


class Asset:
    def __init__(self, path):
        self.path = path

    def get_path_name(self):
        return self.path + "." + self.path.rsplit("/", 1)[-1]


class RootComponent:
    def __init__(self):
        self.mobility = EnumValue("STATIC")

    def get_editor_property(self, name):
        if name == "mobility":
            return self.mobility
        raise AttributeError(name)

    def set_editor_property(self, name, value):
        if name != "mobility":
            raise AttributeError(name)
        self.mobility = value

    def set_mobility(self, value):
        self.mobility = value


class CameraComponent:
    def __init__(self, env):
        self.env = env
        self.props = {
            "filmback": Struct(sensor_width=36.0, sensor_height=20.25),
            "current_focal_length": 35.0,
            "focus_settings": Struct(focus_method=EnumValue("NONE"), manual_focus_distance=1000.0),
        }

    def get_editor_property(self, name):
        if name == "field_of_view":
            return self.get_horizontal_field_of_view()
        return self.props[name]

    def set_editor_property(self, name, value):
        self.props[name] = value

    def get_horizontal_field_of_view(self):
        fb = self.props["filmback"]
        width = fb.get_editor_property("sensor_width")
        focal = self.props["current_focal_length"]
        value = math.degrees(2.0 * math.atan(width / (2.0 * focal)))
        return value + (1.0 if self.env.lie_fov else 0.0)


class Actor:
    def __init__(self, env, path, label, location=None, rotation=None, camera=False):
        self.env, self.path, self.label = env, path, label
        self.location = location or Vector()
        self.rotation = rotation or Rotator()
        self.tags, self.parent = [], None
        self.root_component = RootComponent()
        self.camera = CameraComponent(env) if camera else None

    def get_path_name(self):
        return self.path

    def get_actor_label(self):
        return self.label

    def set_actor_label(self, value):
        self.label = str(value)
        self.env.dirty_maps.add(self.env.mod.MAP_PATH)

    def get_editor_property(self, name):
        if name == "tags":
            return list(self.tags)
        if name == "root_component":
            return self.root_component
        raise AttributeError(name)

    def set_editor_property(self, name, value):
        if name == "tags":
            self.tags = list(value)
            self.env.dirty_maps.add(self.env.mod.MAP_PATH)
            return
        raise AttributeError(name)

    def get_actor_location(self):
        return self.location

    def get_actor_rotation(self):
        return self.rotation

    def set_actor_location_and_rotation(self, location, rotation, sweep, teleport):
        del sweep, teleport
        self.location, self.rotation = location, rotation
        self.env.dirty_maps.add(self.env.mod.MAP_PATH)
        return True

    def get_attach_parent_actor(self):
        return self.parent

    def get_cine_camera_component(self):
        return self.camera

    def get_component_by_class(self, cls):
        del cls
        return self.camera


class SpotTemplate:
    def __init__(self, suffix):
        material = Asset("/Game/InfinityStage/Materials/MI_ShadowGobo_BoyRub")
        self.spot_light_component = Struct(
            attenuation_radius=6000.0, cast_shadows=True, disabled_brightness=0.0,
            inner_cone_angle=10.0, intensity=40000.0, intensity_units=EnumValue("CANDELAS"),
            light_function_fade_distance=10000.0, light_function_material=material,
            outer_cone_angle=25.0, soft_source_radius=12.0, source_length=0.0, source_radius=4.0,
            suffix=suffix,
        )

    def get_editor_property(self, name):
        if name == "spot_light_component":
            return self.spot_light_component
        raise AttributeError(name)


class Sequence:
    def __init__(self, env):
        self.env = env
        self.bindings = []
        old_track = Track("MovieScene3DTransformTrack", "CurtainSleight (Conductor)", [
            Section(env, 0, 2226, [Channel("Location.X", 13591.6, [[0, 13591.6], [2225, 13591.6]])])
        ])
        mouth_track = Track("MovieSceneFloatTrack", "CurtainSleight (Conductor)", [
            Section(env, 0, 2226, [Channel("CurrentFocalLength", 35.0, [[0, 35.0]])])
        ], "CurrentFocalLength", "CurrentFocalLength")
        self.bindings.extend([
            Binding(env, "OLD-CAMERA-GUID", "S2 Sleight Hangar Camera", [old_track]),
            Binding(env, "MOUTH-CAMERA-GUID", "I2 Sleight Mouth Camera", [mouth_track]),
            Binding(env, "SPOT-H-GUID", "Shadow Play Spot (Hangar)", template=SpotTemplate("H")),
            Binding(env, "SPOT-M-GUID", "Shadow Play Spot (Mouth)", template=SpotTemplate("M")),
            Binding(env, "ORDER-D-GUID", "I2 Order Dark: S2 Ghost Light", [
                Track("MovieSceneVisibilityTrack", "Visibility", [Section(env, 0, 1250, [Channel("", False, [[0, False]])])],
                      "bHidden", "bHidden")]),
            Binding(env, "ORDER-E-GUID", "I2 Order Exposure: PostProcessVolume", [
                Track("MovieSceneFloatTrack", "Exposure", [Section(env, 0, 1250, [Channel("", 0.0, [[0, 0.0]])])],
                      "BlendWeight", "BlendWeight")]),
        ])
        if env.return_existing_binding:
            self.bindings.append(Binding(env, "PREEXISTING-GUID", "Preexisting camera binding"))
        split = env.cut_frame
        self.cut_track = Track("MovieSceneCameraCutTrack", "Camera Cuts", [
            Section(env, 0, split, active=True, camera_guid="OLD-CAMERA-GUID"),
            Section(env, split, 2226, active=True, camera_guid="MOUTH-CAMERA-GUID"),
        ])
        self.mpc_track = Track("MovieSceneMaterialParameterCollectionTrack", "ShadowGobo Frame (Conductor)", [
            Section(env, 0, 2226, [Channel("ShadowGobo Frame", 0.0, [[175, 0.0], [275, 12.0]])])
        ])
        self.root_tracks = [self.cut_track, self.mpc_track]
        self.markers = [Struct(label="CST sleight", frame_number=FrameNumber(1250))]
        self.next_guid = 1

    def bindings_by_name(self, name):
        return [b for b in self.bindings if b.name == name]

    def get_bindings(self):
        return list(self.bindings)

    def get_tracks(self):
        return list(self.root_tracks)

    def find_tracks_by_type(self, cls):
        return [self.cut_track] if cls == self.env.unreal.MovieSceneCameraCutTrack else []

    def get_marked_frames_from_sequence(self, unit):
        del unit
        return list(self.markers)

    def get_display_rate(self):
        return FrameRate(25)

    def get_tick_resolution(self):
        return FrameRate(24000)

    def get_playback_start(self):
        return 0

    def get_playback_end(self):
        return 2226

    def modify(self):
        self.env.dirty_content.add(self.env.mod.SEQ_PATH)

    def find_binding_from_object(self, actor, world):
        del actor, world
        return InvalidBinding()

    def locate_bound_objects(self, binding, world):
        del world
        return list(self.env.bound_objects.get(binding.guid, []))

    def add_possessable(self, actor):
        self.env.dirty_content.add(self.env.mod.SEQ_PATH)
        if self.env.return_existing_binding:
            return self.bindings_by_name("Preexisting camera binding")[0]
        guid = "NEW-CAMERA-%d" % self.next_guid
        self.next_guid += 1
        binding = Binding(self.env, guid, "CineCameraActor")
        self.bindings.append(binding)
        self.env.bound_objects[guid] = [actor]
        return binding

    def get_binding_id(self, binding):
        return Struct(guid=Guid(binding.guid))


class Package:
    def __init__(self, path):
        self.path = path

    def get_path_name(self):
        return self.path + ".Pkg"


class World:
    def __init__(self, path):
        self.path = path

    def get_outermost(self):
        return StructWithName(self.path)

    def get_path_name(self):
        return self.path + ".PersistentLevel"


class StructWithName:
    def __init__(self, name):
        self.name = name

    def get_name(self):
        return self.name


class Env:
    def __init__(self, cut_frame=1250, return_existing_binding=False):
        self.tmp = tempfile.mkdtemp(prefix="i2_hangar_cam_harness_")
        self.cut_frame = cut_frame
        self.return_existing_binding = return_existing_binding
        self.dirty_content, self.dirty_maps = set(), set()
        self.pie = False
        self.open_sequence = None
        self.lie_fov = False
        self.mutate_unrelated_on_cut = False
        self.mutation_done = False
        self.bound_objects = {}
        self.logs, self.errors, self.saves = [], [], []
        self.world = None
        self.actors = []
        self.mod = load_tool_placeholder()
        self.unreal = self.make_unreal()
        sys.modules["unreal"] = self.unreal
        self.mod = load_tool()
        self.world = World(self.mod.MAP_PATH)
        self.sequence = Sequence(self)
        self._make_files()
        self._make_curtain_record()

    def make_unreal(self):
        env = self
        u = types.ModuleType("unreal")
        u.MovieSceneCameraCutTrack = "MovieSceneCameraCutTrack"
        u.MovieSceneTimeUnit = types.SimpleNamespace(DISPLAY_RATE="DISPLAY_RATE")
        u.EditorActorSubsystem = "EditorActorSubsystem"
        u.UnrealEditorSubsystem = "UnrealEditorSubsystem"
        u.CineCameraActor = "CineCameraActor"
        u.CineCameraComponent = "CineCameraComponent"
        u.SpotLightComponent = "SpotLightComponent"
        u.ComponentMobility = types.SimpleNamespace(MOVABLE=EnumValue("MOVABLE"))
        u.CameraFocusMethod = types.SimpleNamespace(MANUAL=EnumValue("MANUAL"))
        u.Vector, u.Rotator, u.Name = Vector, Rotator, Name
        u.GuidLibrary = types.SimpleNamespace(conv_guid_to_string=lambda value: value.text)
        u.Paths = types.SimpleNamespace(project_saved_dir=lambda: os.path.join(env.tmp, "Saved") + os.sep,
                                        project_dir=lambda: env.tmp + os.sep,
                                        convert_relative_path_to_full=lambda value: value)

        class ActorSubsystem:
            def get_all_level_actors(self):
                return list(env.actors)

            def spawn_actor_from_class(self, cls, location, rotation, transient=False):
                del cls, transient
                path = env.mod.MAP_PATH + ".PersistentLevel.CineCameraActor_%d" % (len(env.actors) + 1)
                actor = Actor(env, path, "CineCameraActor", location, rotation, camera=True)
                if env.seed_attached:
                    actor.parent = Actor(env, env.mod.MAP_PATH + ".PersistentLevel.Parent", "Parent")
                env.actors.append(actor)
                env.dirty_maps.add(env.mod.MAP_PATH)
                return actor

            def destroy_actor(self, actor):
                env.actors.remove(actor)
                env.dirty_maps.add(env.mod.MAP_PATH)
                return True

        class EditorSubsystem:
            def get_game_world(self):
                return object() if env.pie else None

            def get_editor_world(self):
                return env.world

        actor_subsystem, editor_subsystem = ActorSubsystem(), EditorSubsystem()
        u.get_editor_subsystem = lambda cls: actor_subsystem if cls == u.EditorActorSubsystem else editor_subsystem
        u.LevelSequenceEditorBlueprintLibrary = types.SimpleNamespace(
            get_current_level_sequence=lambda: env.open_sequence)
        u.EditorLoadingAndSavingUtils = types.SimpleNamespace(
            get_dirty_content_packages=lambda: [Package(p) for p in sorted(env.dirty_content)],
            get_dirty_map_packages=lambda: [Package(p) for p in sorted(env.dirty_maps)],
            save_map=lambda world, path: env.save_map(world, path))
        u.EditorAssetLibrary = types.SimpleNamespace(save_asset=lambda path, only_if_is_dirty=True:
                                                     env.save_asset(path, only_if_is_dirty))
        u.load_asset = lambda path: env.sequence if path == env.mod.SEQ_PATH else None
        u.log, u.log_error = env.logs.append, env.errors.append
        return u

    seed_attached = False

    def _make_files(self):
        for package, ext in ((self.mod.MAP_PATH, ".umap"), (self.mod.SEQ_PATH, ".uasset")):
            path = os.path.join(self.tmp, "Content", *package[len("/Game/"):].split("/")) + ext
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as handle:
                handle.write((package + "\n").encode("utf-8"))

    def _make_curtain_record(self):
        path = os.path.join(self.tmp, "Saved", "CodexConductor", "curtain_sleight_record_I2.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        record = {"applied": True, "interaction": 2,
                  "plan": {"frames_of_reference": {"hangar_drape_world":
                  {"loc": [15000.0, 77000.0, 0.0], "yaw": 0.0}},
                  "cam_rel_drape": {"loc": [-3000.0, 0.0, 510.0]}}}
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(record, handle)

    def save_asset(self, path, only_if_dirty):
        del only_if_dirty
        self.saves.append(path)
        self.dirty_content.discard(path)
        return True

    def save_map(self, world, path):
        assert world is self.world
        self.saves.append(path)
        self.dirty_maps.discard(path)
        return True

    def cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


def load_tool_placeholder():
    return types.SimpleNamespace(
        MAP_PATH="/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice",
        SEQ_PATH="/Game/InfinityStage/Interactions/LS_Interaction_02_Turnips")


def load_tool():
    spec = importlib.util.spec_from_file_location("i2_hangar_cam_tested", TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def args(mode, run="HARNESS"):
    return {"mode": mode, "confirm": "%s I2HANGARCAM" % mode, "run_id": "%s-%s" % (run, mode), "params": {}}


def run_dry_apply(env, name="CASE"):
    dry = env.mod.main(args("DRY", name))
    applied = env.mod.main(args("APPLY", name))
    return dry, applied


def expect_stop(env, call_args, reason):
    try:
        env.mod.main(call_args)
    except env.mod.Stop as error:
        assert reason in str(error), (reason, str(error))
        return str(error)
    raise AssertionError("did not stop for " + reason)


RESULTS = []


def case(name, function):
    try:
        function()
        RESULTS.append({"name": name, "status": "PASS"})
    except Exception as error:  # noqa: BLE001
        RESULTS.append({"name": name, "status": "FAIL", "detail": "%s: %s" % (type(error).__name__, error)})


def with_env(function, **kwargs):
    env = Env(**kwargs)
    try:
        return function(env)
    finally:
        env.cleanup()


def test_math():
    mod = load_tool()
    focal = mod.focal_for_hfov(36.0, 50.0)
    assert abs(mod.hfov_for_focal(36.0, focal) - 50.0) < 1.0e-12


def test_focus_derivation():
    mod = load_tool()
    record = {"plan": {"frames_of_reference": {"hangar_drape_world": {"loc": [10, 20, 0], "yaw": 0}},
                       "cam_rel_drape": {"loc": [-30, 0, 5]}}}
    distance, source, point = mod.focus_from_curtain_record(record, [0, 20, 5], 3000)
    assert point == [10.0, 20.0, 5.0] and abs(distance - 10.0) < 1e-9 and source.startswith("curtain_record")


def test_dry_no_mutation(env):
    before = copy.deepcopy(env.mod._snapshot(env.sequence))
    report = env.mod.main(args("DRY", "DRY"))
    assert report["apply_ready"] and report["plan"]["live_sleight_cut_frame"] == 1250
    assert env.mod._snapshot(env.sequence) == before and env.saves == []
    assert env.dirty_content == set() and env.dirty_maps == set()


def test_apply_scoped(env):
    before = copy.deepcopy(env.mod._snapshot(env.sequence))
    _dry, record = run_dry_apply(env, "APPLY")
    after = env.mod._snapshot(env.sequence)
    actor = env.mod._ours_actors()[0]
    state = env.mod._actor_state(actor)
    assert state["parent"] is None and state["mobility"] == "MOVABLE"
    assert abs(state["horizontal_fov_deg"] - 50.0) < 0.001
    assert after["cuts"][0]["binding_guid"] == record["binding"]["guid"]
    assert after["cuts"][1] == before["cuts"][1]
    old_before = [b for b in before["bindings"] if b["name"] == "S2 Sleight Hangar Camera"][0]
    old_after = [b for b in after["bindings"] if b["name"] == "S2 Sleight Hangar Camera"][0]
    assert old_after == old_before
    assert env.saves == [env.mod.SEQ_PATH, env.mod.MAP_PATH]
    assert os.path.isdir(record["backup"]["root"]) and len(record["backup"]["files"]) == 2


def test_revert_exact(env):
    before_seq = copy.deepcopy(env.mod._snapshot(env.sequence))
    before_actors = env.mod._level_actor_index()
    run_dry_apply(env, "REV")
    env.mod.main(args("REVERT", "REV"))
    assert env.mod._snapshot(env.sequence) == before_seq
    assert env.mod._level_actor_index() == before_actors and not env.mod._ours_actors()
    assert env.saves == [env.mod.SEQ_PATH, env.mod.MAP_PATH, env.mod.SEQ_PATH, env.mod.MAP_PATH]


def test_existing_return_handled(env):
    before = copy.deepcopy(env.mod._snapshot(env.sequence))
    _dry, record = run_dry_apply(env, "EXISTING")
    assert record["binding"]["created"] is False
    assert record["binding"]["add_possessable_returned_existing"] is True
    assert record["binding"]["display_name"] == "Preexisting camera binding"
    env.mod.main(args("REVERT", "EXISTING"))
    assert env.mod._snapshot(env.sequence) == before


def negative_pie(env):
    env.pie = True
    expect_stop(env, args("DRY", "PIE"), "PIE_OR_SIE_ACTIVE")


def negative_existing_actor(env):
    actor = Actor(env, env.mod.MAP_PATH + ".PersistentLevel.Existing", env.mod.ACTOR_LABEL, camera=True)
    actor.tags = [Name(env.mod.ACTOR_TAG)]
    env.actors.append(actor)
    expect_stop(env, args("DRY", "ACTOR"), "EXISTING_I2_HANGAR_HOLD_CAMERA")


def negative_cut_frame(env):
    expect_stop(env, args("DRY", "CUT"), "SLEIGHT_CUT_FRAME_MISMATCH")


def negative_extra_dirty(env):
    env.dirty_content.add("/Game/Other/Dirty")
    expect_stop(env, args("DRY", "DIRTY"), "DIRTY_CENSUS")


def negative_guard_changed(env):
    env.mod.main(args("DRY", "GUARD"))
    env.sequence.mpc_track.sections[0].channels[0].keys[-1].value = 13.0
    expect_stop(env, args("APPLY", "GUARD"), "GUARD_CHANGED_SINCE_DRY")
    assert env.saves == [] and not env.mod._ours_actors()


def negative_order_guard_changed(env):
    env.mod.main(args("DRY", "ORDERGUARD"))
    order = env.sequence.bindings_by_name("I2 Order Dark: S2 Ghost Light")[0]
    order.tracks[0].sections[0].channels[0].default = True
    expect_stop(env, args("APPLY", "ORDERGUARD"), "GUARD_CHANGED_SINCE_DRY")
    assert env.saves == [] and not env.mod._ours_actors()


def negative_spot_guard_changed(env):
    env.mod.main(args("DRY", "SPOTGUARD"))
    spot = env.sequence.bindings_by_name("Shadow Play Spot (Hangar)")[0]
    spot.template.spot_light_component.set_editor_property("intensity", 12345.0)
    expect_stop(env, args("APPLY", "SPOTGUARD"), "GUARD_CHANGED_SINCE_DRY")
    assert env.saves == [] and not env.mod._ours_actors()


def negative_attached(env):
    env.seed_attached = True
    env.mod.main(args("DRY", "ATTACH"))
    expect_stop(env, args("APPLY", "ATTACH"), "CAMERA_ATTACHED_AFTER_SPAWN")
    assert env.saves == []


def negative_fov(env):
    env.lie_fov = True
    env.mod.main(args("DRY", "FOV"))
    expect_stop(env, args("APPLY", "FOV"), "CAMERA_HFOV")
    assert env.saves == []


def negative_unrelated_mutation(env):
    env.mod.main(args("DRY", "MUT"))
    env.mutate_unrelated_on_cut = True
    expect_stop(env, args("APPLY", "MUT"), "UNTOUCHED_BINDING_CHANGED")
    assert env.saves == []


def negative_revert_drift(env):
    run_dry_apply(env, "DRIFT")
    env.mod._ours_actors()[0].location.x += 1.0
    expect_stop(env, args("REVERT", "DRIFT"), "STATE_DRIFTED_SINCE_APPLY")
    assert env.saves == [env.mod.SEQ_PATH, env.mod.MAP_PATH]


def negative_revert_guard(env):
    run_dry_apply(env, "RGUARD")
    env.sequence.mpc_track.sections[0].channels[0].keys[-1].value = 14.0
    expect_stop(env, args("REVERT", "RGUARD"), "GUARD_CHANGED_SINCE_DRY")
    assert env.saves == [env.mod.SEQ_PATH, env.mod.MAP_PATH]


def test_import_without_unreal():
    sys.modules.pop("unreal", None)
    mod = load_tool()
    assert hasattr(mod, "main") and "unreal" not in sys.modules


def main():
    case("+ HFOV/focal round trip", test_math)
    case("+ focus derives from Curtain Sleight record", test_focus_derivation)
    case("+ DRY is read-only and finds live cut", lambda: with_env(test_dry_no_mutation))
    case("+ APPLY scopes actor/cuts/save/backup", lambda: with_env(test_apply_scoped))
    case("+ REVERT restores exact sequence and level actor census", lambda: with_env(test_revert_exact))
    case("+ add_possessable returned-existing is not renamed or removed",
         lambda: with_env(test_existing_return_handled, return_existing_binding=True))
    case("- PIE refuses", lambda: with_env(negative_pie))
    case("- existing tagged/labelled actor refuses", lambda: with_env(negative_existing_actor))
    case("- live sleight cut mismatch refuses", lambda: with_env(negative_cut_frame, cut_frame=1249))
    case("- extra dirty package refuses", lambda: with_env(negative_extra_dirty))
    case("- guard changed since DRY refuses APPLY", lambda: with_env(negative_guard_changed))
    case("- I2 Order guard changed since DRY refuses APPLY", lambda: with_env(negative_order_guard_changed))
    case("- GoboSpot template guard changed since DRY refuses APPLY", lambda: with_env(negative_spot_guard_changed))
    case("- attached camera seed stops before save", lambda: with_env(negative_attached))
    case("- lying FOV readback stops before save", lambda: with_env(negative_fov))
    case("- unrelated binding mutation stops before save", lambda: with_env(negative_unrelated_mutation))
    case("- REVERT camera drift refuses", lambda: with_env(negative_revert_drift))
    case("- REVERT guard drift refuses", lambda: with_env(negative_revert_guard))
    case("+ module imports under system Python without unreal", test_import_without_unreal)
    for result in RESULTS:
        print("%-4s %s%s" % (result["status"], result["name"],
                             " | " + result.get("detail", "") if result.get("detail") else ""))
    passed = sum(1 for row in RESULTS if row["status"] == "PASS")
    report = {"passed": passed, "failed": len(RESULTS) - passed, "total": len(RESULTS), "results": RESULTS}
    with open(os.path.join(HERE, "harness_result.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    print("I2_HANGAR_CAM_HARNESS|pass=%d|fail=%d|total=%d" %
          (passed, len(RESULTS) - passed, len(RESULTS)))
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
