"""Offline harness for i2_order.py with a FAKE `unreal` (system Python; nothing touches Unreal or project data).

The fake I2 is built from the project's own records (curtain_sleight_record_I2.json, the IST I2 record, the GoboSpot
record, AG-I2-TEST-004) so the DRY it prints is a PREDICTION of the live DRY [inferred: level lights, volumes and fog
positions in the fake are invented where no record holds them; those numbers are not predictions].
Writes only into a temp project under the scratch dir given by --tmp (default: system temp).  Report:
test_i2_order_report.json next to this file.
Run:  python -X utf8 test_i2_order.py
"""
import copy
import importlib.util
import json
import math
import os
import shutil
import sys
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
CC = os.path.dirname(HERE)                       # Saved/CodexConductor
SAVED = os.path.dirname(CC)


def jload(path):
    with open(path, "r", encoding="utf-8") as h:
        return json.load(h)


SLEIGHT = jload(os.path.join(CC, "curtain_sleight_record_I2.json"))
IST = jload(os.path.join(CC, "interaction_shadow_transition_record_I2.json"))
GSREC = jload(os.path.join(CC, "GoboSpot_20261008", "gobo_spot_record_LS_Interaction_02_Turnips.json"))
AGREC = jload(os.path.join(CC, "animated_gobo_records", "AG-I2-TEST-004.json"))
S2EXT = jload(os.path.join(SAVED, "CodexSoftGoods", "extend_scene_playback.json"))

# =====================================================================================================================
# fake unreal
# =====================================================================================================================


class State:
    def __init__(self):
        self.reset()

    def reset(self):
        self.log, self.dirty, self.dirty_maps, self.saves = [], set(), set(), []
        self.pie, self.open_seq, self.world_name = False, None, "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
        self.project = None
        self.eval_bias = {}            # channel raw name -> added to engine evaluation (lying-engine negative)
        self.lie_vis_property = None   # FIX negative: the setter writes this property instead


ST = State()


def mark_dirty():
    ST.dirty.add("/Game/InfinityStage/Interactions/LS_Interaction_02_Turnips")


class _Cls:
    def __init__(self, name):
        self._n = name

    def get_name(self):
        return self._n


class Obj:
    """props via get/set_editor_property"""
    def __init__(self, **props):
        self._p = dict(props)

    def get_editor_property(self, name):
        if name not in self._p:
            raise AttributeError(name)
        return self._p[name]

    def set_editor_property(self, name, value):
        self._p[name] = value


class FrameNumber:
    def __init__(self, v):
        self.value = int(v)


class FrameRate:
    def __init__(self, n, d=1):
        self.numerator, self.denominator = n, d


class FrameTime:
    def __init__(self, f):
        self.frame_number = FrameNumber(int(math.floor(f)))
        self.sub_frame = float(f) - math.floor(f)


class Guid:
    _n = [0]

    def __init__(self, s=None):
        if s is None:
            Guid._n[0] += 1
            s = "FAKE%028d" % Guid._n[0]
        self.s = s


class Vector:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)


class Rotator:
    def __init__(self, roll=0.0, pitch=0.0, yaw=0.0):
        self.roll, self.pitch, self.yaw = float(roll), float(pitch), float(yaw)


class Key:
    def __init__(self, ch, f, v):
        self.ch, self.f, self.v = ch, f, v

    def get_time(self, time_unit=None):
        return FrameTime(self.f)

    def get_value(self):
        return self.v

    def get_interpolation_mode(self):
        return "RichCurveInterpMode.RCIM_LINEAR"


class Channel:
    def __init__(self, raw, kind, default=None, keys=()):
        self.channel_name, self.kind, self.default = raw, kind, default
        self.keys = [Key(self, f, v) for f, v in keys]

    def get_keys(self):
        return sorted(self.keys, key=lambda k: k.f)

    def has_default(self):
        return self.default is not None

    def get_default(self):
        if self.default is None:
            raise RuntimeError("no default")
        return self.default

    def set_default(self, v):
        mark_dirty()
        self.default = v

    def add_key(self, fn, value, time_unit=None, interpolation=None, sub_frame=0.0):
        mark_dirty()
        self.keys = [k for k in self.keys if k.f != fn.value]
        k = Key(self, fn.value, bool(value) if self.kind == "bool" else float(value))
        self.keys.append(k)
        return k

    def _eval(self, f):
        rows = [[k.f, k.v] for k in self.get_keys()]
        if self.kind == "bool":
            v = bool(self.default) if self.default is not None else False
            for kf, kv in rows:
                if kf <= f:
                    v = kv
            return v
        if not rows:
            return self.default if self.default is not None else 0.0
        if f <= rows[0][0]:
            return rows[0][1]
        for (a, x), (b, y) in zip(rows, rows[1:]):
            if a <= f <= b:
                return y if a == b else x + (y - x) * (f - a) / float(b - a)
        return rows[-1][1]

    def evaluate_keys(self, rng, rate):
        start, dur = rng
        bias = ST.eval_bias.get(self.channel_name, 0.0)
        return [self._eval(start + i) + (bias if self.kind != "bool" else 0) for i in range(dur)]


class Section:
    def __init__(self, track, a, b, chans, params=None, cam_guid=None):
        self.track, self.a, self.b, self.chans, self.params, self.cam_guid = track, a, b, chans, params, cam_guid
        self.completion = "MovieSceneCompletionMode.PROJECT_DEFAULT"

    def get_completion_mode(self):
        return self.completion

    def set_completion_mode(self, m):
        mark_dirty()
        self.completion = m

    def has_start_frame(self):
        return self.a is not None

    def has_end_frame(self):
        return self.b is not None

    def get_start_frame(self):
        return self.a

    def get_end_frame(self):
        return self.b

    def set_range(self, a, b):
        mark_dirty()
        self.a, self.b = int(a), int(b)

    def get_all_channels(self):
        return list(self.chans)

    def get_editor_property(self, name):
        if name == "params":
            return self.params
        raise AttributeError(name)

    def set_editor_property(self, name, v):
        mark_dirty()
        self.params = v

    def is_active(self):
        return True

    def get_camera_binding_id(self):
        return Obj(guid=self.cam_guid)


PROPERTY_TRACKS = {"MovieSceneFloatTrack", "MovieSceneVisibilityTrack", "MovieScene3DTransformTrack", "MovieSceneBoolTrack"}
TRANSFORM_RAW = ["Location.X", "Location.Y", "Location.Z", "Rotation.X", "Rotation.Y", "Rotation.Z", "Scale.X", "Scale.Y", "Scale.Z"]


class Track:
    def __init__(self, cls, name="", prop="", path="", template=None):
        self.cls, self.name, self.prop, self.path = cls, name, prop, path
        self.sections = []
        if template is None:
            if cls == "MovieScene3DTransformTrack":
                template = [(r, "float", 1.0 if r.startswith("Scale") else 0.0) for r in TRANSFORM_RAW]
            elif cls in ("MovieSceneSpawnTrack", "MovieSceneVisibilityTrack", "MovieSceneBoolTrack"):
                template = [("", "bool", None)]
            elif cls in ("MovieSceneFloatTrack",):
                template = [("", "float", None)]
            else:
                template = []
        self.template = template
        if cls == "MovieScene3DTransformTrack" and not prop:
            self.prop, self.path = "Transform", "Transform"

    def get_class(self):
        return _Cls(self.cls)

    UE_FIXED_NAMES = {"MovieSceneSpawnTrack": "Spawned", "MovieSceneGeometryCacheTrack": "Geometry Cache",
                      "MovieSceneVisibilityTrack": "Visibility"}

    def get_display_name(self):
        return self.UE_FIXED_NAMES.get(self.cls, self.name)

    def set_display_name(self, n):
        mark_dirty()
        self.name = n

    def get_property_name(self):
        if self.cls not in PROPERTY_TRACKS:
            raise AttributeError("not a property track")
        return self.prop

    def get_property_path(self):
        if self.cls not in PROPERTY_TRACKS:
            raise AttributeError("not a property track")
        return self.path

    def set_property_name_and_path(self, prop, path):
        mark_dirty()
        if self.cls == "MovieSceneVisibilityTrack" and ST.lie_vis_property:
            prop = path = ST.lie_vis_property
        self.prop, self.path = str(prop), str(path)

    def get_sections(self):
        return list(self.sections)

    def remove_section(self, s):
        mark_dirty()
        self.sections.remove(s)

    def add_section(self):
        mark_dirty()
        s = Section(self, None, None, [Channel(r, k, d) for r, k, d in self.template])
        self.sections.append(s)
        return s

    def get_editor_property(self, name):
        if name == "mpc" and hasattr(self, "mpc"):
            return self.mpc
        raise AttributeError(name)


class Binding:
    def __init__(self, seq, name, guid=None, parent=None, template=None):
        self.seq, self.name, self.guid, self.parent, self.template = seq, name, Guid(guid), parent, template
        self.tracks = []

    def get_id(self):
        return self.guid

    def get_display_name(self):
        return self.name

    def set_display_name(self, n):
        mark_dirty()
        self.name = n

    def get_parent(self):
        return self.parent

    def set_parent(self, p):
        mark_dirty()
        self.parent = p

    def is_valid(self):
        return self in self.seq.bindings

    def get_tracks(self):
        return list(self.tracks)

    def add_track(self, cls):
        mark_dirty()
        t = Track(cls._n if isinstance(cls, _Cls) else cls.__name__)
        self.tracks.append(t)
        return t

    def remove_track(self, t):
        mark_dirty()
        self.tracks.remove(t)

    def remove(self):
        mark_dirty()
        self.seq.bindings.remove(self)

    def get_object_template(self):
        return self.template


class Asset:
    def __init__(self, path, **props):
        self.path = path
        self._p = props

    def get_path_name(self):
        return self.path + "." + self.path.split("/")[-1]

    def get_editor_property(self, n):
        return self._p[n]


class Seq:
    def __init__(self):
        self.bindings, self.tracks, self.markers = [], [], []
        self.pb = [0, 2226]

    def get_path_name(self):
        return "/Game/InfinityStage/Interactions/LS_Interaction_02_Turnips.LS_Interaction_02_Turnips"

    def get_bindings(self):
        return list(self.bindings)

    def get_tracks(self):
        return list(self.tracks)

    def find_tracks_by_type(self, cls):
        return [t for t in self.tracks if t.cls == cls.__name__]

    def get_marked_frames_from_sequence(self, unit):
        return [Obj(label=l, frame_number=FrameNumber(f)) for l, f in self.markers]

    def get_playback_start(self):
        return self.pb[0]

    def get_playback_end(self):
        return self.pb[1]

    def get_display_rate(self):
        return FrameRate(25, 1)

    def get_tick_resolution(self):
        return FrameRate(24000, 1)

    def make_range(self, start, dur):
        return (int(start), int(dur))

    def modify(self):
        mark_dirty()

    def add_possessable(self, obj):
        mark_dirty()
        for b in self.bindings:
            if getattr(b, "obj", None) is obj:
                return b
        b = Binding(self, getattr(obj, "label", "comp"))
        b.obj = obj
        self.bindings.append(b)
        return b


class Comp(Obj):
    pass


class Actor(Obj):
    def __init__(self, label, cls, loc, rot=(0, 0, 0), parent=None, tags=(), comps=None, bounds=None, **props):
        super().__init__(**props)
        self.label, self.cls, self.loc, self.rot, self.parent = label, cls, Vector(*loc), Rotator(roll=rot[2], pitch=rot[0], yaw=rot[1]), parent
        self.tags, self.comps, self.bounds = list(tags), comps or {}, bounds
        self.level = props.pop("_level", "L_InfinityStage_V1VerticalSlice") if "_level" in props else "L_InfinityStage_V1VerticalSlice"
        Actor._n += 1
        self.path = "/Game/%s.%s:PersistentLevel.%s_%d" % (self.level, self.level, cls, Actor._n)

    _n = 0

    def get_path_name(self):
        return self.path

    def get_outer(self):
        lvl = self.level
        return types_ns(get_outer=lambda: types_ns(get_name=lambda: lvl))

    def get_actor_label(self):
        return self.label

    def get_actor_location(self):
        return self.loc

    def get_actor_rotation(self):
        return self.rot

    def get_attach_parent_actor(self):
        return self.parent

    def actor_has_tag(self, t):
        return t in self.tags

    def get_class(self):
        return _Cls(self.cls)

    def get_actor_bounds(self, only_colliding):
        if self.bounds:
            return Vector(*self.bounds[0]), Vector(*self.bounds[1])
        return self.loc, Vector(10, 10, 10)

    def get_cine_camera_component(self):
        return self.comps["camera"]

    def get_component_by_class(self, cls):
        for c in self.comps.values():
            if isinstance(c, cls):
                return c
        return None


def make_fake_unreal():
    import types
    ue = types.ModuleType("unreal")

    class Light(Actor):
        pass

    class SpotLight(Light):
        pass

    class PointLight(Light):
        pass

    class DirectionalLight(Light):
        pass

    class PostProcessVolume(Actor):
        pass

    class CineCameraActor(Actor):
        pass

    class LightComponent(Comp):
        pass

    class ExponentialHeightFogComponent(Comp):
        pass

    for c in (Light, SpotLight, PointLight, DirectionalLight, PostProcessVolume, CineCameraActor, LightComponent,
              ExponentialHeightFogComponent):
        setattr(ue, c.__name__, c)
    for n in ("MovieSceneCameraCutTrack", "MovieScene3DTransformTrack", "MovieSceneFloatTrack", "MovieSceneVisibilityTrack",
              "MovieSceneSpawnTrack", "MovieSceneGeometryCacheTrack", "MovieSceneMaterialParameterCollectionTrack",
              "InfinityStageTransportController", "UnrealEditorSubsystem", "EditorActorSubsystem"):
        setattr(ue, n, type(n, (), {}))
    ue.FrameNumber, ue.Vector, ue.Rotator = FrameNumber, Vector, Rotator
    ue.MovieSceneTimeUnit = types.SimpleNamespace(DISPLAY_RATE="DISPLAY_RATE", TICK_RESOLUTION="TICK")
    ue.MovieSceneKeyInterpolation = types.SimpleNamespace(LINEAR="LINEAR")
    ue.MovieSceneCompletionMode = types.SimpleNamespace(RESTORE_STATE="MovieSceneCompletionMode.RESTORE_STATE",
                                                        KEEP_STATE="MovieSceneCompletionMode.KEEP_STATE")

    class Paths:
        @staticmethod
        def project_saved_dir():
            return os.path.join(ST.project, "Saved")

        @staticmethod
        def project_dir():
            return ST.project

        @staticmethod
        def convert_relative_path_to_full(p):
            return p

    ue.Paths = Paths
    ue.log = lambda m: ST.log.append(("log", m))
    ue.log_error = lambda m: ST.log.append(("error", m))
    ue.log_warning = lambda m: ST.log.append(("warning", m))
    ue.GuidLibrary = types.SimpleNamespace(conv_guid_to_string=lambda g: g.s)

    class Pkg:
        def __init__(self, p):
            self.p = p

        def get_path_name(self):
            return self.p + "." + self.p.split("/")[-1]

        def get_name(self):
            return self.p

    ue.EditorLoadingAndSavingUtils = types.SimpleNamespace(
        get_dirty_content_packages=lambda: [Pkg(p) for p in sorted(ST.dirty)],
        get_dirty_map_packages=lambda: [Pkg(p) for p in sorted(ST.dirty_maps)])

    def save_asset(path, only_if_is_dirty=True):
        ST.saves.append(path)
        ST.dirty.discard(path)
        return True

    ue.EditorAssetLibrary = types.SimpleNamespace(save_asset=save_asset)
    ue.LevelSequenceEditorBlueprintLibrary = types.SimpleNamespace(get_current_level_sequence=lambda: ST.open_seq)

    class World:
        def get_outermost(self):
            return types.SimpleNamespace(get_name=lambda: ST.world_name)

    class EdSub:
        def get_game_world(self):
            return object() if ST.pie else None

        def get_editor_world(self):
            return World()

        def get_all_level_actors(self):
            return list(WORLD["actors"])

    ue.get_editor_subsystem = lambda cls: EdSub()

    def load_asset(path):
        return WORLD["assets"].get(path)

    ue.load_asset = load_asset

    class Transport:
        def build_segments(self, show):
            self.segs = [Obj(label=s["label"], start_frame=FrameNumber(round(s["start"] * 24000)),
                             end_frame=FrameNumber(round(s["end"] * 24000)), cue_index=i) for i, s in enumerate(WORLD["segments"])]

        def get_editor_property(self, n):
            return self.segs

    ue.new_object = lambda cls: Transport()
    return ue


WORLD = {}

# =====================================================================================================================
# the fake I2 (from records)
# =====================================================================================================================

H_GUID = "79E6AD814115D22A888C409AA2F57A77"
M_GUID = "E6CF63464549232FD6CEA88D81178F0D"


def tchans(keys, raw_suffix=""):
    """(frame, x, y, z, pitch, yaw, roll[, ...]) -> 9 transform channels."""
    idx = {"Location.X": 1, "Location.Y": 2, "Location.Z": 3, "Rotation.X": 6, "Rotation.Y": 4, "Rotation.Z": 5}
    out = []
    for raw in TRANSFORM_RAW:
        if raw in idx:
            out.append(Channel(raw + raw_suffix, "float", 0.0, [(int(k[0]), float(k[idx[raw]])) for k in keys]))
        else:
            out.append(Channel(raw + raw_suffix, "float", 1.0, []))
    return out


def add_track(b, cls, name, prop, sections, template=None, path=None):
    t = Track(cls, name, prop, path if path is not None else prop, template)
    if cls == "MovieScene3DTransformTrack":
        t.template = [(c.channel_name, "float", c.default) for c in sections[0].chans]
    for s in sections:
        s.track = t
    t.sections = sections
    b.tracks.append(t)
    return t


def build_world(ue, ghost_keys=None, seg_shift=74.64, extra_s2=None, extra_ev3=False):
    plan = SLEIGHT["plan"]
    seq = Seq()
    seq.markers = [list(m) for m in IST["snapshot_after"]["markers"]]

    def B(name, guid=None, parent=None, template=None):
        b = Binding(seq, name, guid, parent, template)
        seq.bindings.append(b)
        return b

    # cameras (possessables) + their CameraComponent children
    for name, guid, keys in ((plan["hangar_camera"]["label"], H_GUID, plan["hangar_camera"]["keys"]),
                             (plan["mouth_camera"]["label"], M_GUID, plan["mouth_camera"]["keys"])):
        b = B(name, guid)
        add_track(b, "MovieScene3DTransformTrack", "CurtainSleight (Conductor)", "", [Section(None, 0, 2227, tchans(keys))])
        c = B(name + "/CameraComponent", None, b)
        add_track(c, "MovieSceneFloatTrack", "CurtainSleight (Conductor)", "CurrentFocalLength",
                  [Section(None, 0, 2227, [Channel("", "float", None, [(int(k[0]), float(k[7])) for k in keys])])])
        add_track(c, "MovieSceneFloatTrack", "CurtainSleight (Conductor)", "ManualFocusDistance",
                  [Section(None, 0, 2227, [Channel("", "float", None, [(int(k[0]), float(k[8])) for k in keys])])],
                  path="FocusSettings.ManualFocusDistance")
    # hangar drape (suffixed raw channel names: memory ue58-sequencer-read-traps)
    cache = Asset("/Game/Scenes/Curtain/Baked/GC_CurtainDrop_Opening", start_frame=0, end_frame=330)
    d = B("Sleight Hangar Drape", "2D6DC35E47AA01CE86607AAF286A5C50")
    add_track(d, "MovieSceneSpawnTrack", "", "", [Section(None, 0, 2227, [Channel("", "bool", False, [(75, True), (1300, False)])])])
    add_track(d, "MovieScene3DTransformTrack", "CurtainSleight (Conductor)", "",
              [Section(None, 0, 2227, tchans(plan["hangar_drape"]["keys"], "_183"))])
    gp = Obj(start_frame_offset=FrameNumber(23200), end_frame_offset=FrameNumber(240799), geometry_cache_asset=cache)
    add_track(d, "MovieSceneGeometryCacheTrack", "", "", [Section(None, 75, 1300, [], gp)])
    # mouth drape
    mt = Obj(root_component=Obj(relative_location=Vector(0, 160000, 0), relative_rotation=Rotator(0, 0, 0)))
    md = B("Transition Drape (baked)", "D4C22D82489569F31A3C55B2567230CB", template=mt)
    add_track(md, "MovieSceneSpawnTrack", "", "", [Section(None, 0, 2226, [Channel("", "bool", True, [])])])
    secs = []
    for a, b_, so, eo in ((0, 1675, 23200, 240799), (1675, 1925, 23200, 0), (1925, 2226, 263999, 0)):
        secs.append(Section(None, a, b_, [], Obj(start_frame_offset=FrameNumber(so), end_frame_offset=FrameNumber(eo), geometry_cache_asset=cache)))
    add_track(md, "MovieSceneGeometryCacheTrack", "", "", secs)
    # twin spots (IST) with GoboSpot props + AG LF
    for side, label, guid in (("hangar", "Shadow Play Spot (Hangar)", "562CF91B4AD669E49447619E70ADC9CB"),
                              ("mouth", "Shadow Play Spot (Mouth)", "C3077618453206D0F5B255994BD16709")):
        sp = IST["plan"]["spots"][side]
        props = dict(GSREC["after"][label])
        lf = Asset(AGREC["snapshot_after"]["lights"][label])
        comp = Obj(**{k: v for k, v in props.items() if k != "light_function_material"})
        comp.set_editor_property("light_function_material", lf)
        root = Obj(relative_location=Vector(*sp["pose"]["loc"]), relative_rotation=Rotator(0, sp["pose"]["pitch"], sp["pose"]["yaw"]))
        b = B(label, guid, template=Obj(spot_light_component=comp, root_component=root))
        add_track(b, "MovieScene3DTransformTrack", "ShadowPlaySpot (Conductor)", "", [Section(None, 0, 2227, tchans(sp["transform_keys"]))])
        add_track(b, "MovieSceneFloatTrack", "ShadowPlaySpot (Conductor)", "Intensity",
                  [Section(None, 0, 2227, [Channel("", "float", None, [tuple(k) for k in sp["intensity_keys"]])])], path="LightComponent0.Intensity")
        add_track(b, "MovieSceneSpawnTrack", "", "", [Section(None, 0, 2227, [Channel("", "bool", False, [tuple(k) for k in sp["spawn"]])])])
    # possessable lights keyed by curtain_sleight
    for label, keys in (("S2 Ghost Light", ghost_keys or plan["lights"][0]["keys"]), ("S2 Sleight Twin Lantern", plan["lantern"]["keys"])):
        b = B(label)
        c = B(label + "/LightComponent", None, b)
        add_track(c, "MovieSceneFloatTrack", "CurtainSleight (Conductor)", "Intensity", [Section(None, 0, 2227, [Channel("", "float", None, [tuple(k) for k in keys])])])
    # untouched noise: curtain rig, cards
    r = B("Curtain Rig - Fire Safety Curtain", "CADCDD324D30B60303DE0887AB056510")
    add_track(r, "MovieSceneFloatTrack", "CurtainProgress", "CurtainProgress", [Section(None, 0, 2226, [Channel("", "float", None, [(0, 0.0), (500, 1.0)])])])
    for i in range(4):   # extra untouched bindings (I2 also carries e.g. 'Interaction 2 — Stalls Camera')
        b = B("Noise %d" % i)
        add_track(b, "MovieSceneFloatTrack", "Noise", "Noise", [Section(None, 0, 2226, [Channel("", "float", None, [(0, float(i))])])])
    for label in ("Sleight Hangar Shadow Card", "Sleight Mouth Shadow Card"):
        b = B(label)
        add_track(b, "MovieSceneSpawnTrack", "", "", [Section(None, 0, 2227, [Channel("", "bool", False, [(0, False)])])])
    # root tracks: AG-004 MPC frame track, camera cuts
    mpc = Track("MovieSceneMaterialParameterCollectionTrack", "ShadowGobo Frame (Conductor)")
    mpc.mpc = Asset(AGREC["snapshot_after"]["track"]["mpc"])
    mpc.sections = [Section(mpc, 175, 251, [Channel("Frame", "float", None, [(175, 0.0), (250, 24.0)])])]
    cut = Track("MovieSceneCameraCutTrack")
    cut.sections = [Section(cut, 0, 1250, [], cam_guid=Guid(H_GUID)), Section(cut, 1250, 2226, [], cam_guid=Guid(M_GUID))]
    seq.tracks = [mpc, cut]

    # ---- level actors
    root_pose = SLEIGHT["root_pose"]
    rootf = {"loc": root_pose["loc"], "yaw": root_pose["rot"][2]}
    root = Actor("S2 Hangar Root", "Actor", root_pose["loc"], (0, root_pose["rot"][2], 0))

    def W(p):
        c, s = math.cos(math.radians(rootf["yaw"])), math.sin(math.radians(rootf["yaw"]))
        return [rootf["loc"][0] + p[0] * c - p[1] * s, rootf["loc"][1] + p[0] * s + p[1] * c, p[2]]

    film = Obj(sensor_width=23.760000228881836, sensor_height=13.364999771118164)

    def cam(label, loc, parent):
        cc = Comp(filmback=film, current_focal_length=35.0, constrain_aspect_ratio=True, aspect_ratio=23.76 / 13.365,
                  post_process_blend_weight=1.0, post_process_settings=Obj(override_auto_exposure_method=False,
                  override_auto_exposure_bias=False, override_auto_exposure_min_brightness=False, override_auto_exposure_max_brightness=False))
        return ue.CineCameraActor(label, "CineCameraActor", loc, parent=parent, comps={"camera": cc})

    hcam = cam("S2 Sleight Hangar Camera", W([-500, 0, 180]), root)
    mcam = cam("I2 Sleight Mouth Camera", [-1200, 160000, 510], None)

    def light(cls, label, loc, rot, intensity, units="LightUnits.CANDELAS", radius=4500.0, outer=30.0, inner=16.0, tags=(), parent=None):
        comp = ue.LightComponent(intensity=intensity, intensity_units=units, attenuation_radius=radius, outer_cone_angle=outer,
                                 inner_cone_angle=inner, light_color=types_color(), use_temperature=True, temperature=2800.0,
                                 light_function_material=None, affects_world=True, visible=True)
        return cls(label, cls.__name__, loc, rot, parent=parent, tags=tags, comps={"light": comp}, hidden=False)

    lt = plan["lantern"]
    twin = light(ue.SpotLight, "S2 Sleight Twin Lantern", W(lt["root"]["loc"]), (lt["root"]["pitch"], rootf["yaw"] + lt["root"]["yaw"], 0), 0.0, parent=root)
    s = lt["scale"]
    ml = [lt["rel_drape"]["loc"][i] / s for i in range(3)]
    ml[2] = lt["rel_drape"]["loc"][2] / s if False else 478.0
    mouth_l = light(ue.SpotLight, "S03 Mouth Lantern", [ml[0], 160000 + ml[1], ml[2]], (lt["rel_drape"]["pitch"], lt["rel_drape"]["yaw"], 0), 210.0,
                    tags=("RigAtmos.MouthLantern.P03",))
    ghost = light(ue.PointLight, "S2 Ghost Light", W([3000, 0, 300]), (0, 0, 0), 60.0, radius=6000.0)
    beam = light(ue.SpotLight, "P03 SCORE B01 P03_STIFF_BRIGHT BEAM_R", [-1500, 161500, 900], (-15, -45, 0), 9000.0, radius=4000.0, outer=20.0, inner=10.0)
    ppv_u = ue.PostProcessVolume("PostProcessVolume", "PostProcessVolume", [0, 0, 0], unbound=True, priority=0.0, enabled=True, blend_weight=1.0, blend_radius=100.0,
                                 settings=Obj(override_auto_exposure_method=True, auto_exposure_method="AutoExposureMethod.AEM_HISTOGRAM",
                                              override_auto_exposure_bias=True, auto_exposure_bias=0.0,
                                              override_auto_exposure_min_brightness=True, auto_exposure_min_brightness=-3.0,
                                              override_auto_exposure_max_brightness=True, auto_exposure_max_brightness=-3.0))
    c = W([3000, 0, 1500])
    ppv_h = ue.PostProcessVolume("S2 Hangar Pinned Exposure", "PostProcessVolume", c, unbound=False, priority=0.0, enabled=True, blend_weight=1.0,
                                 blend_radius=0.0, bounds=(c, [4200, 4200, 1600]),
                                 settings=Obj(override_auto_exposure_method=False, override_auto_exposure_bias=False,
                                              override_auto_exposure_min_brightness=True, auto_exposure_min_brightness=0.5,
                                              override_auto_exposure_max_brightness=True, auto_exposure_max_brightness=0.5))
    fog = Actor("ExponentialHeightFog", "ExponentialHeightFog", [0, 0, 0],
                comps={"fog": ue.ExponentialHeightFogComponent(fog_density=0.02, fog_height_falloff=0.2, fog_max_opacity=1.0, start_distance=0.0,
                                                               volumetric_fog=True, volumetric_fog_extinction_scale=1.0, volumetric_fog_distance=6000.0)})
    show = Obj(cues=[Obj(label="Interaction 2 — Turnips", enabled=True, scene=Obj(sequence=seq), type="SEQUENCE")],
               tick_resolution=FrameRate(24000, 1))
    segs = []
    shift = 0.0
    for srow in S2EXT["segments_before"]:
        row = {"label": srow["label"], "start": srow["start"] + shift, "end": srow["end"] + shift}
        if srow["label"].startswith("Scene 2"):
            row["end"] += seg_shift
            shift = seg_shift
        segs.append(row)
    actors = [root, hcam, mcam, twin, mouth_l, ghost, beam, ppv_u, ppv_h, fog]
    # the 57 S2 hangar lights/emissives (labels from s2_arrival_strike_dry.json 'ours'), along the hangar walls
    s2_labels = list(S2_DRY["ours"]) + list(extra_s2 or [])
    for i, label in enumerate(s2_labels):
        if label == "S2 Ghost Light":
            continue
        is_light = not (label.endswith("Body") or label.endswith("Bulb"))
        y = -900.0 if i % 2 else 900.0
        loc = W([600.0 + 90.0 * i, y, 400.0 + 10 * (i % 7)])
        if is_light:
            cls = ue.PointLight if "Lattice" in label else ue.SpotLight
            actors.append(light(cls, label, loc, (-30, rootf["yaw"], 0), 0.0, radius=1500.0, tags=("RigAtmos.Scene2Hangar",)))
        else:
            actors.append(Actor(label, "StaticMeshActor", loc, tags=("RigAtmos.Scene2Hangar",), hidden=False))
    # a persistent work light inside the held frame (seen extra) and a streamed (Klara) light in the frame
    actors.append(light(ue.PointLight, "S2 Hangar Work Light", W([4600, 200, 500]), (0, 0, 0), 300.0, radius=2000.0))
    k = light(ue.SpotLight, "SpotLight5", W([4500, -300, 600]), (0, rootf["yaw"], 0), 126.7, radius=3000.0)
    k.level = "Japanese_Alley"
    actors.append(k)
    ppv_u2 = ue.PostProcessVolume("PostProcessVolume", "PostProcessVolume", [0, 0, 0], unbound=True, priority=0.0, enabled=True, blend_weight=1.0,
                                  blend_radius=100.0,
                                  settings=Obj(override_auto_exposure_method=True, auto_exposure_method="AutoExposureMethod.AEM_HISTOGRAM",
                                               override_auto_exposure_bias=True, auto_exposure_bias=1.0,
                                               override_auto_exposure_min_brightness=True, auto_exposure_min_brightness=1.0,
                                               override_auto_exposure_max_brightness=True, auto_exposure_max_brightness=1.0))
    actors.append(ppv_u2)
    if extra_ev3:
        actors.append(ue.PostProcessVolume("PostProcessVolume", "PostProcessVolume", [0, 0, 0], unbound=True, priority=0.0, enabled=True,
                                           blend_weight=1.0, blend_radius=100.0, settings=ppv_u.get_editor_property("settings")))
    by_label = {a.label: a for a in actors if hasattr(a, "label")}
    for b in seq.bindings:
        if b.parent is None and b.name in by_label:
            b.obj = by_label[b.name]
    dev = Seq()
    dev.pb = [0, 3891]
    for label in s2_labels:
        b = Binding(dev, "S2 Arrival Ours Dark: " + label)
        add_track(b, "MovieSceneVisibilityTrack", "", "bHidden", [Section(None, 0, 3891, [Channel("", "bool", False, [])])])
        b.tracks[0].sections[0].completion = "MovieSceneCompletionMode.RESTORE_STATE"
        dev.bindings.append(b)
    WORLD.clear()
    WORLD.update({"seq": seq, "dev": dev, "actors": actors, "segments": segs,
                  "assets": {"/Game/InfinityStage/Dev/DA_InfinityStage_V1Show": show,
                             "/Game/InfinityStage/Interactions/LS_Interaction_02_Turnips": seq,
                             "/Game/InfinityStage/Dev/Sequences/LS_DevScene_02": dev}})
    return seq


def types_ns(**kw):
    import types
    return types.SimpleNamespace(**kw)


S2_DRY = jload(os.path.join(CC, "KlaraIngest", "s2_arrival_strike_dry.json"))


def types_color():
    import types
    return types.SimpleNamespace(r=255, g=200, b=150)


# =====================================================================================================================
# harness
# =====================================================================================================================

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append({"name": name, "ok": bool(cond), "detail": str(detail)[:600]})
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  :: " + str(detail)[:400]))


def make_project(tmp):
    proj = os.path.join(tmp, "proj")
    if os.path.isdir(proj):
        shutil.rmtree(proj)
    cc = os.path.join(proj, "Saved", "CodexConductor")
    os.makedirs(os.path.join(cc, "I2Order_20261008"))
    os.makedirs(os.path.join(cc, "GoboSpot_20261008"))
    os.makedirs(os.path.join(cc, "animated_gobo_records"))
    os.makedirs(os.path.join(proj, "Saved", "CodexSoftGoods"))
    for rel in ("curtain_sleight_I2_dry.json", "curtain_sleight_record_I2.json", "interaction_shadow_transition_record_I2.json",
                os.path.join("GoboSpot_20261008", "gobo_spot_dry_GS-I2-DRY-2.json"),
                os.path.join("GoboSpot_20261008", "gobo_spot_record_LS_Interaction_02_Turnips.json"),
                os.path.join("animated_gobo_records", "AG-I2-TEST-004.json")):
        shutil.copy2(os.path.join(CC, rel), os.path.join(cc, rel))
    shutil.copy2(os.path.join(SAVED, "CodexSoftGoods", "extend_scene_playback.py"), os.path.join(proj, "Saved", "CodexSoftGoods"))
    content = os.path.join(proj, "Content", "InfinityStage", "Interactions")
    os.makedirs(content)
    with open(os.path.join(content, "LS_Interaction_02_Turnips.uasset"), "wb") as h:
        h.write(b"FAKE-UASSET" * 100)
    return proj


def load_tool():
    spec = importlib.util.spec_from_file_location("i2_order_under_test", os.path.join(HERE, "i2_order.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(T, mode, run_id, params=None, confirm=None):
    args = {"mode": mode, "confirm": confirm if confirm is not None else T.CONFIRMS[mode], "run_id": run_id, "params": params or {}}
    try:
        return True, T.main(args)
    except T.Stop as exc:
        return False, str(exc)


def marker(prefix):
    return [m for _, m in ST.log if m.startswith(prefix)]


def fresh(tmp, ue, **kw):
    ST.reset()
    ST.project = make_project(tmp)
    build_world(ue, **kw)


def snap_plain(T):
    return T._snapshot(WORLD["seq"])


def main():
    tmp = sys.argv[sys.argv.index("--tmp") + 1] if "--tmp" in sys.argv else tempfile.mkdtemp(prefix="i2order_")
    ue = make_fake_unreal()
    sys.modules["unreal"] = ue
    T = load_tool()
    P = T.DEFAULTS

    # ------------------------------------------------------------------ pure positives
    segs = []
    shift = 0.0
    for srow in S2EXT["segments_before"]:
        row = {"label": srow["label"], "start": srow["start"] + shift, "end": srow["end"] + shift}
        if srow["label"].startswith("Scene 2"):
            row["end"] += 74.64
            shift = 74.64
        segs.append(row)
    m = T.frame_mapping(segs, T.merged_params({}), 25.0, [0, 2226])
    check("P-map-frame-218", m["frame"] == 218 and m["cue_index_1based"] == 7 and m["segment_count"] == 19, m)
    check("P-map-clock-consistent", m["clock_consistent"] and not m["problems"], m)
    m2 = T.frame_mapping(segs, T.merged_params({"frame_rounding": "floor"}), 25.0, [0, 2226])
    check("P-map-floor-217", m2["frame"] == 217, m2["frame"])
    m3 = T.frame_mapping(segs, T.merged_params({"transport_clock": "12:30"}), 25.0, [0, 2226])
    check("N-map-clock-inconsistent", any(x.startswith("CLOCK_INCONSISTENT") for x in m3["problems"]), m3["problems"])
    m4 = T.frame_mapping(segs[:-1], T.merged_params({}), 25.0, [0, 2226])
    check("N-map-cue-count", any(x.startswith("CUE_COUNT_MISMATCH") for x in m4["problems"]), m4["problems"])

    # coverage maths: camera on the drape axis at distance d, focal f, filmback w x h, aspect = w/h
    box = {"x": [-41.3, 39.1], "y": [-940.0, 940.0], "z": [20.0, 1020.0]}
    for yaw in (0.0, -43.5725212097168, 120.0):
        df = {"loc": [1000.0, -500.0, 0.0], "yaw": yaw}
        d, f, fw, fh = 2000.0, 35.0, 23.76, 13.365
        camw = T.to_world(df, [-41.3 - d, 0.0, 520.0])
        c = T.coverage({"loc": camw, "pitch": 0.0, "yaw": yaw, "roll": 0.0}, f, [fw, fh], True, fw / fh, 16 / 9.0, df, box)
        half_w, half_h = d * fw / 2.0 / f, d * fh / 2.0 / f
        ok = (abs(c["margins"]["left"]["margin_cm"] - (940.0 - half_w)) < 1e-6 and abs(c["margins"]["right"]["margin_cm"] - (940.0 - half_w)) < 1e-6
              and abs(c["margins"]["top"]["margin_cm"] - (1020.0 - (520.0 + half_h))) < 1e-6
              and abs(c["margins"]["bottom"]["margin_cm"] - ((520.0 - half_h) - 20.0)) < 1e-6 and c["fills_frame"]
              and abs(c["coverage_fraction"] - 1.0) < 1e-12)
        check("P-coverage-analytic-yaw%.1f" % yaw, ok, c["margins"])
    df = {"loc": [0.0, 0.0, 0.0], "yaw": 0.0}
    c = T.coverage({"loc": [-41.3 - 6000.0, 0.0, 520.0], "pitch": 0.0, "yaw": 0.0, "roll": 0.0}, 28.0, [23.76, 13.365], True, 23.76 / 13.365, 16 / 9.0, df, box)
    check("N-coverage-far-camera-not-filled", not c["fills_frame"] and c["coverage_fraction"] < 1.0 and c["margins"]["left"]["margin_cm"] < 0, c["margins"])
    c = T.coverage({"loc": [-41.3 - 2000.0, 0.0, 520.0], "pitch": 0.0, "yaw": 180.0, "roll": 0.0}, 35.0, [23.76, 13.365], True, 1.7778, 16 / 9.0, df, box)
    check("N-coverage-looking-away", not c["fills_frame"] and c["coverage_fraction"] == 0.0, c["coverage_fraction"])
    # pitched camera: a tilt down raises nothing above, the bottom margin shrinks
    c0 = T.coverage({"loc": [-2041.3, 0.0, 520.0], "pitch": 0.0, "yaw": 0.0, "roll": 0.0}, 35.0, [23.76, 13.365], True, 1.7778, 16 / 9.0, df, box)
    c1 = T.coverage({"loc": [-2041.3, 0.0, 520.0], "pitch": -5.0, "yaw": 0.0, "roll": 0.0}, 35.0, [23.76, 13.365], True, 1.7778, 16 / 9.0, df, box)
    check("P-coverage-pitch-down-moves-bottom", c1["margins"]["bottom"]["margin_cm"] < c0["margins"]["bottom"]["margin_cm"]
          and c1["margins"]["top"]["margin_cm"] > c0["margins"]["top"]["margin_cm"], (c0["margins"], c1["margins"]))

    # typed pose refused
    spec = {"sections": [{"range": [0, 10], "channels": [{"name": "Location.X", "default": 0.0, "keys": [[0, 0.0], [10, 10.0]]}]}]}
    try:
        T.hold_spec(spec, {"values": {"Location.X": 5.0}}, 5, 10)
        check("N-typed-pose-refused", False, "accepted")
    except T.PlanError as e:
        check("N-typed-pose-refused", "POSE_NOT_EVALUATED" in str(e), e)
    try:
        forged = {"source": "sequence_evaluation", "frame": 5, "spec_digest": "0" * 20, "values": {"Location.X": 5.0}}
        T.hold_spec(spec, forged, 5, 10)
        check("N-forged-evaluation-refused", False, "accepted")
    except T.PlanError as e:
        check("N-forged-evaluation-refused", "POSE_NOT_EVALUATED" in str(e), e)
    ev = T.evaluated_record("g", 5, spec, {"Location.X": 5.0})
    hs = T.hold_spec(spec, ev, 5, 10)
    check("P-hold-spec-pure", T.check_hold(spec, hs, ev, 5, 10, 1e-3) == [] and hs["sections"][0]["channels"][0]["keys"] == [[0, 0.0], [5, 5.0], [10, 5.0]], hs)
    ev_bad = T.evaluated_record("g", 5, spec, {"Location.X": 7.0})
    check("N-eval-disagrees-with-keys", any(x.startswith("EVAL_DISAGREES_WITH_KEYS") for x in T.check_hold(spec, T.hold_spec(spec, ev_bad, 5, 10), ev_bad, 5, 10, 1e-3)))

    # fix steps
    try:
        T.fix_step_check({"id": "x", "kind": "LIGHT_HIDE", "actor_label": "L", "keys": [[0, True]], "property": "bHiddenInGame"})
        check("N-fix-bHiddenInGame-refused", False, "accepted")
    except T.PlanError as e:
        check("N-fix-bHiddenInGame-refused", "bHiddenInGame" in str(e), e)
    try:
        T.fix_step_check({"id": "x", "kind": "LIGHT_HIDE", "actor_label": "L", "keys": [[0, 1.0]]})
        check("N-fix-hide-needs-bools", False, "accepted")
    except T.PlanError:
        check("N-fix-hide-needs-bools", True)
    fs = T.fix_track_spec({"id": "x", "kind": "LIGHT_HIDE", "actor_label": "L", "keys": [[0, True], [10, False]]}, 100)
    check("P-fix-vis-spec-bHidden-true-visible", fs["prop"] == "bHidden" and fs["path"] == "bHidden" and fs["default"] is True, fs)

    # exposure tie
    ex = T.effective_exposure([{"name": "U", "priority": 0, "weight": 1, "overrides": {"min_ev": -3.0, "max_ev": -3.0}},
                               {"name": "H", "priority": 0, "weight": 1, "overrides": {"min_ev": 0.5, "max_ev": 0.5}}], None)
    check("P-exposure-tie-flagged", ex["tie_changes_result"] and ex["tie_groups"] == [["U", "H"]], ex)

    # ------------------------------------------------------------------ end-to-end on the fake I2
    fresh(tmp, ue)
    ok, rep = run(T, "DRY", "T-DRY-1")
    dry_lines = [m for _, m in ST.log if m.startswith("I2_ORDER")]
    check("P-dry-ok", ok and marker("I2_ORDER_DRY_OK|run=T-DRY-1|mutated=0|apply_ready=1"), (rep if not ok else dry_lines[-1]))
    check("P-dry-clean-census", not ST.dirty and not ST.saves, (ST.dirty, ST.saves))
    if ok:
        pl = rep["plan"]
        check("P-dry-H-218-hangar", pl["hold_frame"] == 218 and pl["held_camera"] == "S2 Sleight Hangar Camera" and pl["twin_needed"], pl["held_camera"])
        check("P-dry-fade-175", pl["drape"]["fade_start"] == 175, pl["drape"]["fade_start"])
        check("P-dry-curtain-not-visible-now-at-0", not pl["drape"]["states_now"][0]["visible"], pl["drape"]["states_now"])
        check("P-dry-F18-N", pl["f18"]["fall_end_frame"] == 1925 and pl["f18"]["new_end_frame"] == 1950 and pl["hold_end"] == 1950, pl["f18"])
        past = rep["f18_past_end"]
        check("P-dry-F18-lists-pile-cut-walk", any(s["owner"] == "Transition Drape (baked)" for s in past["sections"])
              and any(c["camera"] == "I2 Sleight Mouth Camera" for c in past["cuts"])
              and any(k["owner"] == "I2 Sleight Mouth Camera" for k in past["keys"]) and past["own_writes_after_apply_past_N"] == [], past)
        check("P-dry-F18-extend-refusal-predicted", rep["f18_extend_prediction"]["will_refuse"] is True, rep["f18_extend_prediction"])
        em = jload(os.path.join(ST.project, "Saved", "CodexConductor", "I2Order_20261008", "extend_i2_shorten_mode.json"))
        check("P-dry-extend-mode-file", em["new_end_frame"] == 1950 and em["dry_run"] is True and em["cue_label"] == "Interaction 2 — Turnips", em)
        lc = rep["lighting"]["cuts"]
        check("P-light-cut-1250-in-window", len(lc) == 1 and lc[0]["cut_frame"] == 1250 and lc[0]["in_gary_window"], [c.get("cut_frame") for c in lc])
        kinds = [i["kind"] for i in lc[0]["ranked"]]
        check("P-light-exposure-ranked", "EXPOSURE" in kinds and "EXPOSURE_TIE" in kinds, kinds)
        ties = [i for i in lc[0]["ranked"] if i["kind"] == "EXPOSURE_TIE"]
        check("P-light-exposure-tie-at-both-cameras", len(ties) == 2 and ties[0]["impact_stops"] == 5.0, [(i["what"], i["impact_stops"]) for i in ties])
        spots = [i for i in lc[0]["ranked"] if i["kind"] == "TWIN_SPOT_KEYS_AT_CUT"]
        check("P-light-twin-spots-equal-at-cut", spots and all(abs((i["before"] or 0) - 7482.80419921875) < 1e-3 for i in spots[:1]), spots)
        tw = pl["writes"]["twin"]
        hd = {"loc": pl["drape"]["hung_pose"]["loc"], "yaw": pl["drape"]["hung_pose"]["yaw"]}
        rel_h = T.to_local(hd, pl["held_world_pose"]["loc"])
        rel_m = T.to_local({"loc": [0.0, 160000.0, 0.0], "yaw": 0.0}, tw["pose"]["loc"])
        check("P-twin-matched-relative-pose", max(abs(a - b) for a, b in zip(rel_h, rel_m)) < 1e-6
              and abs(T.wrap(pl["held_world_pose"]["yaw"] - hd["yaw"]) - T.wrap(tw["pose"]["yaw"])) < 1e-9, (rel_h, rel_m))
        ag = rep["warnings"]
        check("P-dry-guards-match-records", not [w for w in ag if w.startswith(("AG004", "GOBOSPOT"))], ag)

    pre = snap_plain(T)
    ok, rec = run(T, "APPLY", "T-DRY-1")
    check("P-apply-ok", ok and marker("I2_ORDER_APPLY_OK|run=T-DRY-1"), rec if not ok else "")
    check("P-apply-saved-LS-only", ST.saves == ["/Game/InfinityStage/Interactions/LS_Interaction_02_Turnips"] and not ST.dirty, ST.saves)
    check("P-apply-backup-and-record", ok and os.path.isdir(rec["backup"]) and os.path.isfile(rec["backup_files"][0]), rec if ok else "")
    if ok:
        seq = WORLD["seq"]
        hb = [b for b in seq.bindings if b.name == "S2 Sleight Hangar Camera"][0]
        tr = hb.tracks[0]
        ev = rec["plan"]["held_values"]["transform"]
        got_ok = True
        for ch in tr.sections[0].chans:
            n = T.norm_channel(ch.channel_name)
            if n in ev:
                for f in (0, 75, 150, 218, 400, 1249, 1950, 2225):      # hold_start = 0: sits on the 12:18 frame
                    if abs(ch._eval(f) - ev[n]) > 1e-9:
                        got_ok = False
        check("P-hold-keys-equal-evaluated-pose-from-0", got_ok)
        d = [b for b in seq.bindings if b.name == "Sleight Hangar Drape"][0]
        sp = [t for t in d.tracks if t.cls == "MovieSceneSpawnTrack"][0].sections[0].chans[0]
        z = [c for c in [t for t in d.tracks if t.cls == "MovieScene3DTransformTrack"][0].sections[0].chans if c.channel_name.startswith("Location.Z")][0]
        gc = [t for t in d.tracks if t.cls == "MovieSceneGeometryCacheTrack"][0].sections[0]
        vis = all(sp._eval(f) and abs(z._eval(f) - 0.0) < 1e-6 and gc.a <= f < gc.b for f in range(0, 176))
        check("P-curtain-visible-before-175", vis, (sp.keys and [(k.f, k.v) for k in sp.keys], gc.a))
        mpc = [t for t in seq.tracks if t.cls == "MovieSceneMaterialParameterCollectionTrack"][0]
        check("P-ag004-unchanged", [(k.f, k.v) for k in mpc.sections[0].chans[0].get_keys()] == [(175, 0.0), (250, 24.0)]
              and T.guard_hashes(snap_plain(T)) == T.guard_hashes(pre))
        ok2, why = run(T, "APPLY", "T-DRY-1")
        check("N-reapply-over-record", not ok2 and "RECORD_EXISTS" in why, why)
        ok3, _ = run(T, "VERIFY", "T-VER-1")
        check("P-verify-ok", ok3 and marker("I2_ORDER_VERIFY_OK|run=T-VER-1"), ST.log[-1])
        # FIX on top, then main REVERT must refuse until FIX_REVERT
        step = {"id": "HIDE-BEAM", "kind": "LIGHT_HIDE", "actor_label": "P03 SCORE B01 P03_STIFF_BRIGHT BEAM_R", "keys": [[0, True], [1250, False], [1675, True]]}
        okf, why = run(T, "FIX", "T-FIX-1", {"fix_steps": [step]})
        check("P-fix-ok", okf and marker("I2_ORDER_FIX_OK|run=T-FIX-1"), why)
        if okf:
            b = [x for x in WORLD["seq"].bindings if x.name == step["actor_label"]][0]
            vt = [t for t in b.tracks if t.cls == "MovieSceneVisibilityTrack"][0]
            check("P-fix-vis-track-bHidden", vt.prop == "bHidden" and vt.path == "bHidden" and [(k.f, k.v) for k in vt.sections[0].chans[0].get_keys()] == [(0, True), (1250, False), (1675, True)])
            okr, why = run(T, "REVERT", "T-REV-0")
            check("N-revert-refused-while-fix-applied", not okr and "FIX_APPLIED" in why, why)
            okfr, why = run(T, "FIX_REVERT", "T-FIXR-1")
            check("P-fix-revert-ok", okfr and marker("I2_ORDER_FIX_REVERT_OK|run=T-FIXR-1"), why)
        okr, why = run(T, "REVERT", "T-REV-1")
        check("P-revert-ok", okr and marker("I2_ORDER_REVERT_OK|run=T-REV-1"), why)
        post = snap_plain(T)
        check("P-revert-exact", json.dumps(post, sort_keys=True, default=str) == json.dumps(pre, sort_keys=True, default=str),
              T.untouched_diff(pre, post, set()))

    # =========================================================== 9 Oct: DARKNESS + EXPOSURE + hold_start
    fresh(tmp, ue)
    dev_before = T.digest([[b.name, [(k.f, k.v) for t in b.tracks for sct in t.sections for c in sct.chans for k in c.keys],
                            [sct.completion for t in b.tracks for sct in t.sections], [t.prop for t in b.tracks]] for b in WORLD["dev"].bindings])
    ok, rep9 = run(T, "DRY", "T9-DRY")
    check("P9-dry-ok", ok and rep9["apply_ready"], rep9 if not ok else rep9["refusals"][:3])
    if ok:
        dk = rep9["plan"]["darkness"]
        groups = {}
        for t in dk["targets"]:
            groups.setdefault(t["group"], []).append(t)
        check("P9-darkness-s2-set-57", len(groups.get("S2_HANGAR", [])) == 57 and dk["foreign_source"]["count"] == 57,
              {k: len(v) for k, v in groups.items()})
        s2 = groups["S2_HANGAR"][0]
        check("P9-darkness-s2-until-hangar-strike", s2["until"] == 1300 and s2["range"] == [0, 1301]
              and s2["keys"] == [[0, False], [1300, True]] and s2["binding_name"].startswith("I2 Order Dark: "), s2)
        own = groups.get("I2_OWN", [])
        check("P9-darkness-twin-lantern-until-fade", [t["label"] for t in own] == ["S2 Sleight Twin Lantern"] and own[0]["until"] == 175, own)
        check("P9-darkness-seen-extra", [t["label"] for t in groups.get("SEEN_EXTRA", [])] == ["S2 Hangar Work Light"],
              [t["label"] for t in groups.get("SEEN_EXTRA", [])])
        check("P9-darkness-streamed-listed-not-written", [m["label"] for m in dk["streamed_listed"]] == ["SpotLight5"]
              and not any(t["label"] == "SpotLight5" for t in dk["targets"]), dk["streamed_listed"])
        check("P9-darkness-no-gobo-spot", not any(t["label"] in ("Shadow Play Spot (Hangar)", "Shadow Play Spot (Mouth)") for t in dk["targets"]))
        check("P9-fog-reported-and-proposed", dk["fog"] and dk["fog"][0]["proposal"]["kind"] == "ACTOR_HIDE"
              and dk["fog"][0]["proposal"]["fix_step"]["keys"] == [[0, False], [1250, True]], dk["fog"])
        ex = rep9["plan"]["exposure"]
        zero_names = sorted((z["label"], (z["overrides"] or {}).get("min_ev")) for z in ex["zero"])
        check("P9-exposure-keep-ev-3", ex["keep"]["overrides"].get("min_ev") == -3.0 and ex["keep"]["label"] == "PostProcessVolume", ex["keep"])
        check("P9-exposure-zero-tie-mate-and-one-sided", zero_names == [("PostProcessVolume", 1.0), ("S2 Hangar Pinned Exposure", 0.5)], zero_names)
        check("P9-exposure-model-deterministic", all(not m["tie_changes_result"] for m in ex["model_after"].values())
              and len({json.dumps(m["effective"], sort_keys=True) for m in ex["model_after"].values()}) == 1
              and any(m["tie_changes_result"] for m in ex["model_before"].values()), ex["model_after"])
        check("P9-dry-lines", marker("I2_ORDER_DARKNESS|run=T9-DRY") and marker("I2_ORDER_EXPOSURE|run=T9-DRY")
              and marker("I2_ORDER_FOG|run=T9-DRY") and any("hold_start=0|dark=59|exposure_zero=2" in m for m in marker("I2_ORDER_DRY_OK|run=T9-DRY")),
              marker("I2_ORDER_DRY_OK|run=T9-DRY"))
    pre9 = snap_plain(T)
    ok, rec9 = run(T, "APPLY", "T9-DRY")
    check("P9-apply-ok", ok and any('dark_tracks=59|exposure_tracks=2|reused_bindings=["S2 Ghost Light", "S2 Sleight Twin Lantern"]|foreign=unchanged' in m
                                    for m in marker("I2_ORDER_APPLY_OK|run=T9-DRY")),
          rec9 if not ok else marker("I2_ORDER_APPLY_OK|run=T9-DRY"))
    check("P9-apply-saved-LS-only", ST.saves == ["/Game/InfinityStage/Interactions/LS_Interaction_02_Turnips"] and not ST.dirty, ST.saves)
    if ok:
        seq = WORLD["seq"]
        dark = [b for b in seq.bindings if b.name.startswith("I2 Order Dark: ")]
        vis_ok = all(len(b.tracks) == 1 and b.tracks[0].cls == "MovieSceneVisibilityTrack" and b.tracks[0].prop == "bHidden"
                     and b.tracks[0].path == "bHidden" and b.tracks[0].sections[0].completion.endswith("RESTORE_STATE")
                     and b.tracks[0].sections[0].chans[0].default is False and b.tracks[0].sections[0].chans[0]._eval(174) is False
                     for b in dark)
        check("P9-dark-bindings-bHidden-true-visible-restore", len(dark) == 57 and vis_ok, len(dark))
        # 10: actors already bound in I2 keep their binding and name; exactly our one track is added
        for label in ("S2 Ghost Light", "S2 Sleight Twin Lantern"):
            bs = [b for b in seq.bindings if b.name == label]
            vt = [t for t in bs[0].tracks if t.cls == "MovieSceneVisibilityTrack"] if len(bs) == 1 else []
            check("P10-reused-binding-kept-%s" % label, len(bs) == 1 and len(bs[0].tracks) == 1 and len(vt) == 1 and vt[0].prop == "bHidden"
                  and vt[0].sections[0].chans[0]._eval(0) is False, [b.name for b in bs])
        rr = [c for c in rec9["created"] if c.get("reused")]
        check("P10-record-says-track-added-to-existing", sorted(c["binding_name"] for c in rr) == ["S2 Ghost Light", "S2 Sleight Twin Lantern"]
              and all(c["note"].startswith("track added to existing binding") for c in rr), rr)
        check("P10-dry-predicted-reuse", sorted(t["label"] for t in rep9["plan"]["darkness"]["targets"] if t.get("reuse_expected"))
              == ["S2 Ghost Light", "S2 Sleight Twin Lantern"])
        expo = [b for b in seq.bindings if b.name.startswith("I2 Order Exposure: ")]
        check("P9-exposure-bindings-blendweight-0", len(expo) == 2 and all(b.tracks[0].prop == "BlendWeight" and b.tracks[0].sections[0].chans[0]._eval(1249) == 0.0
                                                                          and b.tracks[0].sections[0].completion.endswith("RESTORE_STATE") for b in expo))
        dev_after = T.digest([[b.name, [(k.f, k.v) for t in b.tracks for sct in t.sections for c in sct.chans for k in c.keys],
                               [sct.completion for t in b.tracks for sct in t.sections], [t.prop for t in b.tracks]] for b in WORLD["dev"].bindings])
        check("P9-foreign-devscene-unchanged-after-apply", dev_after == dev_before)
        okv, why = run(T, "VERIFY", "T9-VER")
        check("P9-verify-ok", okv and marker("I2_ORDER_VERIFY_OK|run=T9-VER"), why)
        okr, why = run(T, "REVERT", "T9-REV")
        check("P9-revert-ok", okr and marker("I2_ORDER_REVERT_OK|run=T9-REV"), why)
        names_after = [b.name for b in WORLD["seq"].bindings]
        check("P9-revert-removes-only-ours", not any(n.startswith(("I2 Order Dark: ", "I2 Order Exposure: ")) for n in names_after)
              and "S2 Ghost Light" in names_after and "S2 Sleight Twin Lantern/LightComponent" in names_after)
        gl = [b for b in WORLD["seq"].bindings if b.name == "S2 Ghost Light"]
        check("P10-revert-removed-only-our-track-on-reused", len(gl) == 1 and gl[0].tracks == [], [t.cls for t in gl[0].tracks] if gl else None)
        post9 = snap_plain(T)
        check("P9-revert-exact", json.dumps(post9, sort_keys=True, default=str) == json.dumps(pre9, sort_keys=True, default=str),
              T.untouched_diff(pre9, post9, set()))
        dev_after = T.digest([[b.name, [(k.f, k.v) for t in b.tracks for sct in t.sections for c in sct.chans for k in c.keys],
                               [sct.completion for t in b.tracks for sct in t.sections], [t.prop for t in b.tracks]] for b in WORLD["dev"].bindings])
        check("P9-foreign-devscene-unchanged-after-revert", dev_after == dev_before)

    # legacy hold (hold_start None): frames before H unchanged
    fresh(tmp, ue)
    pre_l = snap_plain(T)
    run(T, "DRY", "T9-LEG", {"hold_start": None, "darkness": False, "exposure_fix": False})
    ok, recl = run(T, "APPLY", "T9-LEG", {"hold_start": None, "darkness": False, "exposure_fix": False})
    if ok:
        hb = [b for b in WORLD["seq"].bindings if b.name == "S2 Sleight Hangar Camera"][0]
        pre_t = [b for b in pre_l["bindings"] if b["name"] == "S2 Sleight Hangar Camera"][0]["tracks"][0]
        same = all(abs(ch._eval(f) - T.interp([c for c in pre_t["sections"][0]["channels"] if c["name"] == T.norm_channel(ch.channel_name)][0]["keys"], f)) < 1e-9
                   for ch in hb.tracks[0].sections[0].chans if T.norm_channel(ch.channel_name) in T.POSE_CH
                   for f in range(0, 218))
        check("P9-legacy-hold-start-none-keeps-push", same and not [b for b in WORLD["seq"].bindings if b.name.startswith("I2 Order")])
    else:
        check("P9-legacy-hold-start-none-keeps-push", False, recl)
    # pure hold_start
    spec = {"sections": [{"range": [0, 10], "channels": [{"name": "Location.X", "default": 0.0, "keys": [[0, 0.0], [10, 10.0]]}]}]}
    ev = T.evaluated_record("g", 5, spec, {"Location.X": 5.0})
    hs = T.hold_spec(spec, ev, 5, 10, 0)
    check("P9-hold-start-pure", hs["sections"][0]["channels"][0]["keys"] == [[0, 5.0], [5, 5.0], [10, 5.0]]
          and T.check_hold(spec, hs, ev, 5, 10, 1e-3, 0) == [], hs)
    try:
        T.hold_spec(spec, ev, 5, 10, 7)
        check("N9-hold-start-after-frame", False)
    except T.PlanError as e:
        check("N9-hold-start-after-frame", "HOLD_START_AFTER_FRAME" in str(e))

    # N: the darkness step would hide a gobo spot -> refuse
    fresh(tmp, ue, extra_s2=["Shadow Play Spot (Hangar)"])
    ok, repn = run(T, "DRY", "T9-SPOT")
    check("N9-darkness-hides-gobo-spot", ok and any(x.startswith("DARKNESS_HIDES_GOBO_SPOT") for x in repn["refusals"]) and not repn["apply_ready"],
          repn if not ok else repn["refusals"][:2])
    ok, why = run(T, "APPLY", "T9-SPOT")
    check("N9-darkness-hides-gobo-spot-apply-refused", not ok and "PLAN_REFUSED" in why and not ST.saves, why)
    # N: a darkness key outside I2
    fresh(tmp, ue)
    ok, repn = run(T, "DRY", "T9-OUT", {"darkness_s2_until": 5000})
    check("N9-darkness-key-outside-I2", ok and any(x.startswith("DARKNESS_KEY_OUTSIDE_I2") for x in repn["refusals"]), repn if not ok else repn["refusals"][:2])
    # N: a writer that touches LS_DevScene_02 (the foreign bindings) -> stop before save
    fresh(tmp, ue)
    run(T, "DRY", "T9-FOR")
    orig_c = T._create_all

    def bad_create(seq, plan, run_id):
        out = orig_c(seq, plan, run_id)
        WORLD["dev"].bindings[0].tracks[0].sections[0].chans[0].default = True
        return out

    T._create_all = bad_create
    ok, why = run(T, "APPLY", "T9-FOR")
    T._create_all = orig_c
    check("N9-foreign-devscene-changed-stops", not ok and "FOREIGN_S2_ARRIVAL_BINDINGS_CHANGED" in why and not ST.saves, why)
    # N: the visibility setter writes bHiddenInGame -> stop before save
    fresh(tmp, ue)
    run(T, "DRY", "T9-HIG")
    ST.lie_vis_property = "bHiddenInGame"
    ok, why = run(T, "APPLY", "T9-HIG")
    ST.lie_vis_property = None
    check("N9-darkness-bHiddenInGame-binding-stops", not ok and "VIS_TRACK_PROPERTY_NOT_bHidden" in why and not ST.saves, why)
    # N: two unbound EV -3 volumes -> the kept volume is ambiguous
    fresh(tmp, ue, extra_ev3=True)
    ok, why = run(T, "DRY", "T9-AMB")
    check("N9-exposure-keep-ambiguous", not ok and "EXPOSURE_KEEP_AMBIGUOUS" in why, why)
    # N (pure): a fix that leaves a tie is refused
    exn = {"model_after": {"a": {"tie_changes_result": True, "tie_groups": [["x", "y"]], "effective": {}},
                           "b": {"tie_changes_result": False, "tie_groups": [], "effective": {}}}}
    check("N9-exposure-still-tied", any(x.startswith("EXPOSURE_STILL_TIED") for x in T.check_exposure(exn)))
    # N: REVERT never removes a binding that is not ours
    try:
        ST.reset(); ST.project = make_project(tmp); build_world(ue)
        T._remove_created(WORLD["seq"], [{"guid": WORLD["seq"].bindings[0].guid.s, "binding_name": "S2 Sleight Hangar Camera"}], "T9-RM")
        check("N9-revert-refuses-foreign-binding", False)
    except T.Stop as e:
        check("N9-revert-refuses-foreign-binding", "REFUSE_REMOVE_FOREIGN" in str(e), e)

    # =========================================================== 10: live I2ORDER-DRY-3 stop, reproduced
    # a reused binding that already carries a visibility track -> DRY refusal
    fresh(tmp, ue)
    gb = [b for b in WORLD["seq"].bindings if b.name == "S2 Ghost Light"][0]
    add_track(gb, "MovieSceneVisibilityTrack", "", "bHidden", [Section(None, 0, 2227, [Channel("", "bool", True, [])])])
    ok, repn = run(T, "DRY", "T10-VIS")
    check("N10-reused-binding-has-visibility-refused", ok and any(x.startswith("DARKNESS_TARGET_BINDING_HAS_VISIBILITY|S2 Ghost Light") for x in repn["refusals"]),
          repn if not ok else repn["refusals"][:3])
    # the old behaviour (rename the reused binding) is caught by read-back
    fresh(tmp, ue)
    run(T, "DRY", "T10-REN")
    orig_c2 = T._create_all

    def renaming_create(seq, plan, run_id):
        out = orig_c2(seq, plan, run_id)
        for c in out:
            if c.get("reused"):
                [b for b in seq.bindings if b.guid.s == c["guid"]][0].name = c["planned_name"]
        return out

    T._create_all = renaming_create
    ok, why = run(T, "APPLY", "T10-REN")
    T._create_all = orig_c2
    check("N10-renamed-reused-binding-stops", not ok and "BINDING_RENAMED_OR_REPARENTED" in why and not ST.saves, why)
    # a stopped APPLY leaves an unapplied record: the next APPLY says so
    ST.dirty.clear()
    ok, why = run(T, "APPLY", "T10-REN")
    check("N10-stale-unapplied-record", not ok and "STALE_UNAPPLIED_RECORD" in why, why)
    # every problem is printed (no truncation)
    fresh(tmp, ue)
    run(T, "DRY", "T10-ALL")
    orig_w = T._apply_writes

    def noisy(seq, plan, run_id, originals=None):
        orig_w(seq, plan, run_id, originals)
        for b in [b for b in seq.bindings if b.name.startswith("S2 Practical")] or []:
            pass
        n = 0
        for b in seq.bindings:
            for t in b.tracks:
                if b.name.startswith(("Curtain Rig", "Sleight Hangar Shadow", "Sleight Mouth Shadow", "Shadow Play Spot", "S2 Ghost Light/", "S2 Sleight Twin Lantern/", "Transition Drape", "Noise ")):
                    if any(sct.chans for sct in t.sections):
                        TOUCHED.add((b.guid.s, t.cls, t.prop))
                    for sct in t.sections:
                        for c in sct.chans:
                            c.keys.append(Key(c, 99999 + n, True if c.kind == "bool" else 1.0))
                            n += 1

    TOUCHED = set()
    T._apply_writes = noisy
    ok, why = run(T, "APPLY", "T10-ALL")
    T._apply_writes = orig_w
    nprob = why.count("UNTOUCHED_TRACK_CHANGED")
    check("P10-stop-line-lists-all-problems", not ok and nprob == len(TOUCHED) and nprob > 12, (nprob, len(TOUCHED)))

    # REVERT drift
    fresh(tmp, ue)
    run(T, "DRY", "T-DRIFT")
    ok, _ = run(T, "APPLY", "T-DRIFT")
    hb = [b for b in WORLD["seq"].bindings if b.name == "S2 Sleight Hangar Camera"][0]
    hb.tracks[0].sections[0].chans[0].keys[-1].v += 50.0
    ok, why = run(T, "REVERT", "T-DRIFT-R")
    check("N-revert-drift", not ok and "STATE_DRIFTED_SINCE_APPLY" in why, why)

    # AG-004 changed during APPLY (a writer bug) -> stop before save
    fresh(tmp, ue)
    run(T, "DRY", "T-AG")
    orig = T._apply_writes

    def buggy(seq, plan, run_id, originals=None):
        orig(seq, plan, run_id, originals)
        mpc = [t for t in seq.tracks if t.cls == "MovieSceneMaterialParameterCollectionTrack"][0]
        mpc.sections[0].chans[0].keys[-1].v = 23.0

    T._apply_writes = buggy
    ok, why = run(T, "APPLY", "T-AG")
    T._apply_writes = orig
    check("N-ag004-changed-stops-before-save", not ok and "GUARD_CHANGED" in why and "NOTHING SAVED" in why and not ST.saves, why)
    r = jload(os.path.join(ST.project, "Saved", "CodexConductor", "I2Order_20261008", "i2_order_record.json"))
    check("N-ag004-record-not-applied", r["applied"] is False)

    # an untouched track changed during APPLY
    fresh(tmp, ue)
    run(T, "DRY", "T-UT")

    def buggy2(seq, plan, run_id, originals=None):
        orig(seq, plan, run_id, originals)
        g = [b for b in seq.bindings if b.name == "S2 Ghost Light/LightComponent"][0]
        g.tracks[0].sections[0].chans[0].keys[0].v = 0.0

    T._apply_writes = buggy2
    ok, why = run(T, "APPLY", "T-UT")
    T._apply_writes = orig
    check("N-untouched-track-changed", not ok and "UNTOUCHED_TRACK_CHANGED" in why, why)

    # bHiddenInGame: a lying setter in FIX
    fresh(tmp, ue)
    ST.lie_vis_property = "bHiddenInGame"
    step = {"id": "HIDE-BEAM", "kind": "LIGHT_HIDE", "actor_label": "P03 SCORE B01 P03_STIFF_BRIGHT BEAM_R", "keys": [[0, True], [1250, False]]}
    ok, why = run(T, "FIX", "T-FIXLIE", {"fix_steps": [step]})
    check("N-fix-bHiddenInGame-binding-stops", not ok and "VIS_TRACK_PROPERTY_NOT_bHidden" in why and not ST.saves, why)
    ST.lie_vis_property = None

    # drape carrying an inert bHiddenInGame visibility track -> DRY refuses
    fresh(tmp, ue)
    d = [b for b in WORLD["seq"].bindings if b.name == "Sleight Hangar Drape"][0]
    add_track(d, "MovieSceneVisibilityTrack", "", "bHiddenInGame", [Section(None, 0, 2227, [Channel("", "bool", True, [])])])
    ok, rep = run(T, "DRY", "T-INERT")
    check("N-drape-bHiddenInGame-refused", ok and "DRAPE_HAS_INERT_bHiddenInGame_TRACK" in rep["refusals"], rep if not ok else rep["refusals"])

    # curtain still hidden at 175: a bHidden visibility track keyed hidden until 180
    fresh(tmp, ue)
    d = [b for b in WORLD["seq"].bindings if b.name == "Sleight Hangar Drape"][0]
    add_track(d, "MovieSceneVisibilityTrack", "", "bHidden", [Section(None, 0, 2227, [Channel("", "bool", False, [(180, True)])])])
    ok, rep = run(T, "DRY", "T-HID")
    check("N-curtain-hidden-at-175", ok and any(x.startswith("DRAPE_NOT_VISIBLE_BEFORE_FADE") for x in rep["refusals"]) and not rep["apply_ready"],
          rep if not ok else rep["refusals"][:2])
    ok, why = run(T, "APPLY", "T-HID")
    check("N-curtain-hidden-apply-refused", not ok and "PLAN_REFUSED" in why and not ST.saves, why)

    # visible_from at/after the fade
    try:
        T.drape_plan({"spawn": {"sections": [{"range": [0, 10], "channels": [{"name": "", "default": False, "keys": [[75, True], [1300, False]]}]}]}},
                     175, 175, {}, 1.0)
        check("N-visible-from-not-before-fade", False)
    except T.PlanError as e:
        check("N-visible-from-not-before-fade", "VISIBLE_FROM_NOT_BEFORE_FADE" in str(e), e)

    # DARKNESS: not reached with the ghost light at 60 -> refused; reached when the I2 lights are dark at 0
    fresh(tmp, ue)
    ok, why = run(T, "DRY", "T-DARK", {"drape_visible_from": "DARKNESS"})
    check("N-darkness-not-reached", not ok and "DARKNESS_NOT_REACHED_BEFORE_FADE" in why, why)
    fresh(tmp, ue, ghost_keys=[[0, 0.0], [250, 0.0]])
    ok, rep = run(T, "DRY", "T-DARK2", {"drape_visible_from": "DARKNESS"})
    check("P-darkness-frame", ok and rep["plan"]["drape"]["visible_from"] == 0 and rep["plan"]["drape"]["visible_from_source"] == "DARKNESS",
          rep if not ok else rep["plan"]["drape"]["visible_from"])

    # the drape does not fill the frame -> flagged (not refused, not hidden)
    fresh(tmp, ue)
    ok, rep = run(T, "DRY", "T-FILL", {"seconds_into_cue": 4.0, "transport_clock": "12:14"})
    flags = rep["flags"] if ok else []
    line = [m for m in marker("I2_ORDER_DRY_OK|run=T-FILL")]
    check("N-not-filled-flagged", ok and any(f.startswith("DRAPE_DOES_NOT_FILL_FRAME|held") for f in flags) and line and "fills=0" in line[0]
          and any("DRAPE_DOES_NOT_FILL_FRAME" in m for m in marker("I2_ORDER_WARNING|run=T-FILL")), (flags, line))
    check("N-not-filled-still-apply-ready", ok and rep["apply_ready"], rep["refusals"] if ok else rep)

    # lying engine evaluation -> refusal (the cross-check can fail)
    fresh(tmp, ue)
    ST.eval_bias = {"Location.X": 5.0}
    ok, rep = run(T, "DRY", "T-LIE")
    check("N-engine-eval-disagrees", ok and any(x.startswith("EVAL_DISAGREES_WITH_KEYS") for x in rep["refusals"]), rep if not ok else rep["refusals"][:2])
    ST.eval_bias = {}

    # preflight negatives
    for name, setup, want in (("N-pie", lambda: setattr(ST, "pie", True), "PIE_OR_SIE_ACTIVE"),
                              ("N-sequencer-open", lambda: setattr(ST, "open_seq", object()), "SEQUENCER_IS_OPEN"),
                              ("N-dirty-census", lambda: ST.dirty_maps.add("/Game/X"), "DIRTY_CENSUS"),
                              ("N-wrong-world", lambda: setattr(ST, "world_name", "/Game/Other"), "WRONG_WORLD")):
        fresh(tmp, ue)
        setup()
        ok, why = run(T, "DRY", "T-" + name)
        check(name, not ok and want in why, why)
    fresh(tmp, ue)
    ok, why = run(T, "APPLY", "T-CONF", confirm="APPLY I2")
    check("N-confirm-mismatch", not ok and "CONFIRM_MISMATCH" in why, why)
    fresh(tmp, ue)
    run(T, "DRY", "T-CHG")
    WORLD["seq"].bindings[0].tracks[0].sections[0].chans[0].keys[100].v += 1.0
    ok, why = run(T, "APPLY", "T-CHG")
    check("N-plan-changed-since-dry", not ok and "PLAN_CHANGED_SINCE_DRY" in why, why)
    fresh(tmp, ue)
    ok, why = run(T, "FIX", "T-NOFIX")
    check("N-fix-default-does-nothing", not ok and "NO_FIX_STEPS" in why and not ST.saves, why)

    # KEEP_WALK reports the jump; HOLD warns WALKIN_REMOVED
    fresh(tmp, ue)
    ok, rep = run(T, "DRY", "T-WALK", {"mouth_after_hold": "KEEP_WALK"})
    check("P-keep-walk-jump-reported", ok and any(w.startswith("WALK_SEAT_JUMP") for w in rep["warnings"]), rep if not ok else rep["warnings"])

    # module import must not touch unreal objects: re-import with no unreal module
    sys.modules.pop("unreal", None)
    spec = importlib.util.spec_from_file_location("i2_order_plain", os.path.join(HERE, "i2_order.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    check("P-import-without-unreal", hasattr(mod, "main") and "unreal" not in sys.modules)
    sys.modules["unreal"] = ue

    # predicted DRY print (fake built from records)
    fresh(tmp, ue)
    ok, rep = run(T, "DRY", "I2ORDER-DRY-PREDICT")
    predicted = [m for _, m in ST.log if m.startswith("I2_ORDER")]
    npass = sum(1 for r in RESULTS if r["ok"])
    out = {"passed": npass, "failed": len(RESULTS) - npass, "total": len(RESULTS), "results": RESULTS,
           "predicted_dry_lines": predicted,
           "predicted_dry_plan_excerpt": None if not ok else {
               "mapping": rep["plan"]["mapping"], "held_world_pose": rep["plan"]["held_world_pose"], "lens": rep["plan"]["lens"],
               "coverage": rep["plan"]["coverage"], "drape": {k: v for k, v in rep["plan"]["drape"].items() if k != "states_now"},
               "f18": rep["plan"]["f18"], "flags": rep["flags"], "warnings": rep["warnings"], "refusals": rep["refusals"],
               "lighting_ranked": rep["lighting"]["cuts"][0]["ranked"] if rep["lighting"]["cuts"] else None,
               "lighting_proposals": rep["lighting"]["cuts"][0]["proposals"] if rep["lighting"]["cuts"] else None,
               "lighting_events": rep["lighting"]["events"], "f18_past_end": rep["f18_past_end"]}}
    with open(os.path.join(HERE, "test_i2_order_report.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=1, default=str, ensure_ascii=False)
    print("RESULT passed=%d failed=%d total=%d" % (npass, len(RESULTS) - npass, len(RESULTS)))
    return 0 if npass == len(RESULTS) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(2)
