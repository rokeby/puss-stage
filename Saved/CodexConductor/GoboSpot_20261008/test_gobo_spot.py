"""Offline harness for gobo_spot.py (system Python, fake `unreal`; NEVER touches Unreal or the real project).

The fake scene is the I2 geometry from the records (shadow_play_spot_record_I2.json plan.spots / curtain_sleight
record I2 cards and drapes, curtain_sleight_I2_dry.json hang_aabb_cm).  Every Unreal write lands in a temp project.

Positive controls: plan maths for both variants, identical settings on both twins, APPLY -> REVERT -> APPLY, aim
point reproduction, fade floor.  Negative controls: one twin missing, curtain not hit, twins differ > 5 % must be
flagged (and 2 % must not), keyed property not written, lying setter, re-APPLY over a record, REVERT drift, plus
PIE / open Sequencer / dirty census / confirm / stale DRY / foreign dirty package / GC box unknown.

Run:  python test_gobo_spot.py      -> prints PASS/FAIL per check, writes test_gobo_spot_report.json, exit 1 on any FAIL.
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
SEQ = "/Game/InfinityStage/Interactions/LS_Interaction_02_Turnips"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
GC = "/Game/Scenes/Curtain/Baked/GC_CurtainDrop_Opening"
CUBE = "/Engine/BasicShapes/Cube"
HANG = {"x": [-41.3, 39.1], "y": [-940.0, 940.0], "z": [20.0, 1020.0]}   # curtain_sleight_I2_dry.json inputs.cache
HANGAR_YAW = -43.5725212097168
SPOT_H = [13089.310173457769, 79066.07881321739, 1536.0604299770062]      # shadow_play_spot_record_I2 plan.spots
SPOT_M = [-2860.3778623577255, 160000.0, 1536.0604299770062]
AIM_H = [15131.739178881979, 77122.96694000029, 510.0]
DRAPE_H = [15161.661337041618, 77094.49843646525, 0.0]
CARD_H = [15130.65262933638, 77123.99928469799, 510.0]

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append({"name": name, "ok": bool(cond), "detail": str(detail)[:400]})
    print("%s  %s  %s" % ("PASS" if cond else "FAIL", name, "" if cond else str(detail)[:400]))


def load_tool():
    spec = importlib.util.spec_from_file_location("gobo_spot_under_test", os.path.join(HERE, "gobo_spot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)          # no real `unreal` on system Python -> main() does not run
    assert mod.unreal is None
    return mod


# =====================================================================================================================
# Fake unreal
# =====================================================================================================================

class W:
    """Fake editor state shared by the fake objects."""

    def __init__(self, root):
        self.root = root
        self.dirty = set()
        self.dirty_maps = set()
        self.pie = False
        self.open_seq = None
        self.logs = []
        self.saves = []
        self.world = WORLD
        self.extra_dirty_on_set = None     # a foreign package that a setter dirties (scope negative)
        self.seq = None
        self.actors = []


class Cls:
    def __init__(self, name):
        self._n = name

    def get_name(self):
        return self._n


class Vec:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = float(x), float(y), float(z)


class Rot:
    def __init__(self, pitch=0.0, yaw=0.0, roll=0.0):
        self.pitch, self.yaw, self.roll = float(pitch), float(yaw), float(roll)


class Box:
    def __init__(self, lo, hi):
        self.min, self.max = Vec(*lo), Vec(*hi)


class Asset:
    def __init__(self, path):
        self.path = path

    def get_path_name(self):
        return "%s.%s" % (self.path, self.path.rsplit("/", 1)[1])


class Mesh(Asset):
    def __init__(self, path, lo, hi):
        super().__init__(path)
        self._box = Box(lo, hi)

    def get_bounding_box(self):
        return self._box


class Obj:
    def __init__(self, w, pkg, props, lie=()):
        self.w, self.pkg, self.props, self.lie = w, pkg, dict(props), set(lie)

    def get_editor_property(self, name):
        if name not in self.props:
            raise Exception("no property %s" % name)
        return self.props[name]

    def set_editor_property(self, name, value):
        if name not in self.props:
            raise Exception("no property %s" % name)
        self.w.dirty.add(self.pkg)
        if self.w.extra_dirty_on_set:
            self.w.dirty.add(self.w.extra_dirty_on_set)
        if name in self.lie:
            return None                     # lying setter: accepts, changes nothing
        self.props[name] = value

    def modify(self):
        self.w.dirty.add(self.pkg)
        return True


class SpotLight(Obj):
    pass


class StaticMeshActor(Obj):
    pass


class GeometryCacheActor(Obj):
    pass


class CineCameraActor(Obj):
    pass


class LevelSequence(Asset):
    def __init__(self, w, path, bindings):
        super().__init__(path)
        self.w, self.bindings = w, bindings

    def get_bindings(self):
        return list(self.bindings)

    def modify(self):
        self.w.dirty.add(self.path)
        return True


class Time:
    def __init__(self, frame):
        self.frame_number = types.SimpleNamespace(value=int(frame))
        self.sub_frame = 0.0


class Key:
    def __init__(self, frame, value):
        self.f, self.v = frame, value

    def get_time(self, time_unit=None):
        return Time(self.f)

    def get_value(self):
        return self.v


class Channel:
    def __init__(self, name, keys, default=None):
        self.channel_name, self._keys, self._default = name, [Key(f, v) for f, v in keys], default

    def get_keys(self):
        return list(self._keys)

    def get_default(self):
        if self._default is None:
            raise Exception("no default")
        return self._default


class Section:
    def __init__(self, channels):
        self._c = channels

    def get_all_channels(self):
        return list(self._c)


class Track:
    def __init__(self, cls, name="", sections=(), prop=None):
        self._cls, self._name, self._sections, self._prop = Cls(cls), name, list(sections), prop
        if prop is not None:
            self.get_property_name = lambda: prop
            self.get_property_path = lambda: "LightComponent0." + prop

    def get_class(self):
        return self._cls

    def get_display_name(self):
        return self._name

    def get_sections(self):
        return list(self._sections)


class Invalid:
    def is_valid(self):
        return False


class Binding:
    def __init__(self, name, guid, template=None, tracks=(), parent=None):
        self.name, self.guid, self.template, self.tracks, self.parent = name, guid, template, list(tracks), parent

    def get_display_name(self):
        return self.name

    def get_id(self):
        return self.guid

    def get_object_template(self):
        return self.template

    def get_tracks(self):
        return list(self.tracks)

    def get_parent(self):
        return self.parent if self.parent is not None else Invalid()

    def is_valid(self):
        return True


class Pkg:
    def __init__(self, name):
        self._n = name

    def get_name(self):
        return self._n


class Actor:
    def __init__(self, label, origin, extent, mesh=None):
        self.label, self.o, self.e, self.mesh = label, origin, extent, mesh

    def get_actor_label(self):
        return self.label

    def get_actor_bounds(self, only_colliding):
        return Vec(*self.o), Vec(*self.e)

    def get_component_by_class(self, cls):
        if self.mesh is None:
            return None
        return types.SimpleNamespace(get_editor_property=lambda n: self.mesh)


def make_unreal(w):
    u = types.SimpleNamespace()
    u.SpotLight, u.LevelSequence, u.StaticMeshComponent = SpotLight, LevelSequence, object
    u.MovieSceneTimeUnit = types.SimpleNamespace(DISPLAY_RATE="DISPLAY_RATE")
    u.GuidLibrary = types.SimpleNamespace(conv_guid_to_string=lambda g: str(g))
    u.Paths = types.SimpleNamespace(project_dir=lambda: w.root + "/", project_saved_dir=lambda: w.root + "/Saved/",
                                    convert_relative_path_to_full=lambda p: p)
    u.EditorLoadingAndSavingUtils = types.SimpleNamespace(
        get_dirty_content_packages=lambda: [Pkg(p) for p in sorted(w.dirty)],
        get_dirty_map_packages=lambda: [Pkg(p) for p in sorted(w.dirty_maps)])

    def save_asset(path, only_if_is_dirty=True):
        w.saves.append(path)
        w.dirty.discard(path)
        with open(os.path.join(w.root, "Content", *path[len("/Game/"):].split("/")) + ".uasset", "ab") as h:
            h.write(b"S")
        return True

    u.EditorAssetLibrary = types.SimpleNamespace(save_asset=save_asset)
    u.UnrealEditorSubsystem, u.EditorActorSubsystem = "UES", "EAS"
    editor_world = types.SimpleNamespace(get_outermost=lambda: Pkg(w.world))

    def subsystem(kind):
        if kind == "UES":
            return types.SimpleNamespace(get_editor_world=lambda: editor_world,
                                         get_game_world=lambda: object() if w.pie else None)
        return types.SimpleNamespace(get_all_level_actors=lambda: list(w.actors))

    u.get_editor_subsystem = subsystem
    u.LevelSequenceEditorBlueprintLibrary = types.SimpleNamespace(get_current_level_sequence=lambda: w.open_seq)
    cv = {"r.LightFunctionAtlas": 1, "r.Deferred.UsesLightFunctionAtlas": 1, "r.LightFunctionAtlas.SlotResolution": 32}
    u.SystemLibrary = types.SimpleNamespace(get_console_variable_int_value=lambda n: cv.get(n, 0),
                                            get_console_variable_float_value=lambda n: float(cv.get(n, 0)))
    u.load_asset = lambda path: w.seq if path == SEQ else None
    u.log = lambda m: w.logs.append(("log", m))
    u.log_warning = lambda m: w.logs.append(("warn", m))
    u.log_error = lambda m: w.logs.append(("error", m))
    return u


def xf_track(keys_by_frame, name):
    """keys_by_frame: [(frame, x, y, z, pitch, yaw, roll)] -> 3D transform track with suffixed channel names."""
    names = [("Location.X_183", 1), ("Location.Y_184", 2), ("Location.Z_185", 3), ("Rotation.X", 6),
             ("Rotation.Y", 4), ("Rotation.Z", 5)]
    chans = [Channel(n, [(k[0], k[i]) for k in keys_by_frame], 0.0) for n, i in names]
    chans += [Channel("Scale.%s" % a, [], 1.0) for a in "XYZ"]
    return Track("MovieScene3DTransformTrack", name, [Section(chans)])


def spawn_track(keys):
    return Track("MovieSceneSpawnTrack", "Spawned", [Section([Channel("None", keys, False)])])


def spot_template(w, lie=()):
    comp = Obj(w, SEQ, {"outer_cone_angle": 3.433630362450522, "inner_cone_angle": 2.9185858080829434,
                        "source_radius": 2.0, "soft_source_radius": 0.0, "source_length": 0.0,
                        "light_function_fade_distance": 100000.0, "attenuation_radius": 4500.0,
                        "intensity": 7482.804063965048, "disabled_brightness": 0.5, "cast_shadows": True,
                        "intensity_units": "LightUnits.CANDELAS", "light_function_material": None}, lie)
    root = Obj(w, SEQ, {"relative_location": Vec(0, 0, 0), "relative_rotation": Rot(), "relative_scale3d": Vec(1, 1, 1)})
    return SpotLight(w, SEQ, {"spot_light_component": comp, "root_component": root}), comp


def build_scene(root, mouth_spot=None, mouth_yaw=0.0, drop_mouth=False, keyed_source_radius=False, lie=(),
                camera_attached_hangar=True):
    w = W(root)
    os.makedirs(os.path.join(root, "Content", "InfinityStage", "Interactions"), exist_ok=True)
    with open(os.path.join(root, "Content", "InfinityStage", "Interactions", "LS_Interaction_02_Turnips.uasset"), "wb") as h:
        h.write(b"UASSET" * 100)
    b = []
    th, ch = spot_template(w, lie)
    h_tracks = [spawn_track([(150, True), (1302, False)]),
                xf_track([(0,) + tuple(SPOT_H) + (-20.0, HANGAR_YAW, 0.0), (2226,) + tuple(SPOT_H) + (-20.0, HANGAR_YAW, 0.0)],
                         "ShadowPlaySpot (Conductor)"),
                Track("MovieSceneFloatTrack", "ShadowPlaySpot (Conductor)",
                      [Section([Channel("Intensity", [(0, 0.0), (175, 0.0), (187, 7482.8), (1300, 7482.8), (1301, 0.0)])])],
                      prop="Intensity")]
    if keyed_source_radius:
        h_tracks.append(Track("MovieSceneFloatTrack", "", [Section([Channel("SourceRadius", [(0, 2.0)])])],
                              prop="SourceRadius"))
    hangar_spot = Binding("Shadow Play Spot (Hangar)", "G-SPOT-H", th, h_tracks)
    b.append(hangar_spot)
    if not drop_mouth:
        tm, cm = spot_template(w)
        ms = mouth_spot or SPOT_M
        b.append(Binding("Shadow Play Spot (Mouth)", "G-SPOT-M", tm, [
            spawn_track([(150, True), (1701, False)]),
            xf_track([(0,) + tuple(ms) + (-20.0, mouth_yaw, 0.0), (2226,) + tuple(ms) + (-20.0, mouth_yaw, 0.0)],
                     "ShadowPlaySpot (Conductor)")]))
    # child component binding of the hangar spot (keyed-track search must look here too)
    b.append(Binding("Shadow Play Spot (Hangar)/LightComponent0", "G-SPOT-H-C", None, [], parent=hangar_spot))

    def gc_actor(loc, yaw):
        gcc = Obj(w, SEQ, {"geometry_cache": Asset(GC)})
        root_c = Obj(w, SEQ, {"relative_location": Vec(*loc), "relative_rotation": Rot(0, yaw, 0),
                              "relative_scale3d": Vec(1, 1, 1)})
        return GeometryCacheActor(w, SEQ, {"geometry_cache_component": gcc, "root_component": root_c})

    drape_keys = [(75, DRAPE_H[0], DRAPE_H[1], 1970.0, 0.0, HANGAR_YAW, 0.0),
                  (150, DRAPE_H[0], DRAPE_H[1], 307.8125, 0.0, HANGAR_YAW, 0.0),
                  (175, DRAPE_H[0], DRAPE_H[1], 0.0, 0.0, HANGAR_YAW, 0.0),
                  (1300, DRAPE_H[0], DRAPE_H[1], 0.0, 0.0, HANGAR_YAW, 0.0)]
    b.append(Binding("Sleight Hangar Drape", "G-DRAPE-H", gc_actor(DRAPE_H, HANGAR_YAW),
                     [spawn_track([(75, True), (1300, False)]), xf_track(drape_keys, "CurtainSleight (Conductor)")]))
    b.append(Binding("Transition Drape (baked)", "G-DRAPE-M", gc_actor([0.0, 160000.0, 0.0], 0.0), []))

    def card(loc, yaw):
        smc = Obj(w, SEQ, {"static_mesh": Mesh(CUBE, [-50, -50, -50], [50, 50, 50])})
        root_c = Obj(w, SEQ, {"relative_location": Vec(*loc), "relative_rotation": Rot(0, yaw, 0),
                              "relative_scale3d": Vec(0.01, 4.8, 2.7)})
        return StaticMeshActor(w, SEQ, {"static_mesh_component": smc, "root_component": root_c})

    b.append(Binding("Sleight Hangar Shadow Card", "G-CARD-H", card(CARD_H, HANGAR_YAW),
                     [xf_track([(75,) + tuple(CARD_H[:2]) + (2480.0, 0.0, HANGAR_YAW, 0.0),
                                (175,) + tuple(CARD_H) + (0.0, HANGAR_YAW, 0.0),
                                (1300,) + tuple(CARD_H) + (0.0, HANGAR_YAW, 0.0)], "CurtainSleight (Conductor)")]))
    b.append(Binding("Sleight Mouth Shadow Card", "G-CARD-M", card([-42.8, 160000.0, 510.0], 0.0), []))

    def camera(loc, attached):
        root_c = Obj(w, SEQ, {"relative_location": Vec(*loc), "relative_rotation": Rot(), "relative_scale3d": Vec(1, 1, 1)})
        tracks = [Track("MovieScene3DAttachTrack", "Attach")] if attached else []
        return CineCameraActor(w, SEQ, {"root_component": root_c}), tracks

    cam_t, cam_tr = camera([-1200.0, 160000.0, 510.0], False)
    b.append(Binding("I2 Sleight Mouth Camera", "G-CAM-M", cam_t, cam_tr))
    cam_t2, cam_tr2 = camera([-1200.0, 0.0, 510.0], camera_attached_hangar)
    b.append(Binding("S2 Sleight Hangar Camera", "G-CAM-H", cam_t2, cam_tr2))
    b.append(Binding("Curtain Rig - Fire Safety Curtain", "G-FSC", None, [Track("MovieSceneBoolTrack")]))
    w.seq = LevelSequence(w, SEQ, b)
    w.actors = [Actor("Curtain Rig - Fire Safety Curtain", [0.0, -5000.0, 500.0], [1000.0, 50.0, 500.0]),
                Actor("Stage Floor", [0.0, 160000.0, -5.0], [5000.0, 5000.0, 5.0])]
    return w


# =====================================================================================================================
# Helpers
# =====================================================================================================================

class Env:
    def __init__(self, tool, **scene):
        self.tmp = tempfile.mkdtemp(prefix="gobospot_")
        self.w = build_scene(self.tmp, **scene)
        self.tool = tool
        tool.unreal = make_unreal(self.w)

    def args(self, mode, run, variant=None, **extra):
        a = {"mode": mode, "run_id": run, "sequence": SEQ, "confirm": self.tool.confirm_text(mode, variant),
             "gc_local_boxes": {GC: HANG}, "frame_start": 175, "frame_end": 250, "sample_step": 5}
        if variant:
            a["variant"] = variant
        a.update(extra)
        return a

    def run(self, raw):
        try:
            self.tool.main(raw)
            return None
        except RuntimeError as exc:
            return str(exc)

    def comp(self, label):
        for b in self.w.seq.bindings:
            if b.name == label:
                return b.template.props["spot_light_component"]
        return None

    def markers(self, prefix):
        return [m for _, m in self.w.logs if m.startswith(prefix)]

    def dry(self, run, **extra):
        err = self.run(self.args("DRY", run, **extra))
        rep = self.tool._load_json(self.tool.dry_path(run))
        return err, rep

    def record(self):
        return self.tool._load_json(self.tool.record_path(SEQ))

    def close(self):
        self.tool.unreal = None
        shutil.rmtree(self.tmp, ignore_errors=True)


def close(a, b, tol=1e-6):
    return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(b)))


def no_ue_globals(tool):
    fakes = (Obj, LevelSequence, Binding, Track, Channel, Section, Asset, Actor)
    bad = [k for k, v in vars(tool).items() if isinstance(v, fakes)]
    return bad


# =====================================================================================================================
# Tests
# =====================================================================================================================

def pure_tests(t):
    # rot_axes reproduces the record's aim point (spot + 3000 cm along forward) for both twins
    for name, loc, yaw, aim in (("hangar", SPOT_H, HANGAR_YAW, AIM_H), ("mouth", SPOT_M, 0.0, [-41.3, 160000.0, 510.0])):
        fwd = t.rot_axes(-20.0, yaw, 0.0)[0]
        got = [loc[i] + 3000.0 * fwd[i] for i in range(3)]
        check("P-rot-aim-%s" % name, max(abs(got[i] - aim[i]) for i in range(3)) < 0.01, (got, aim))
    x, y, z = t.rot_axes(0, 90, 0)
    check("P-rot-yaw90", close(x[1], 1) and close(y[0], -1) and close(z[2], 1), (x, y, z))
    # interpolation and step
    check("P-interp", close(t.interp_keys([[150, 307.8125], [175, 0.0]], 162.5), 153.90625), "")
    check("P-step", t.step_keys([[150, True], [1302, False]], 200, False) and
          not t.step_keys([[150, True], [1302, False]], 1302, False), "")
    # ray-box: axis-aligned box hit from the front
    box = {"loc": [0, 0, 0], "pitch": 0, "yaw": 0, "roll": 0, "lo": [-1, -100, -50], "hi": [1, 100, 50]}
    hit = t.ray_box([-1000.0, 0.0, 0.0], [1.0, 0.0, 0.0], box)
    check("P-raybox-hit", hit and close(hit["t"], 999.0) and close(hit["width_cm"], 200) and close(hit["height_cm"], 100)
          and close(hit["incidence_deg"], 0.0, 1e-9), hit)
    check("N-raybox-miss", t.ray_box([-1000.0, 500.0, 0.0], [1.0, 0.0, 0.0], box) is None, "")
    check("N-raybox-behind", t.ray_box([1000.0, 0.0, 0.0], [1.0, 0.0, 0.0], box) is None, "")
    # variant maths straight from the brief
    d, wdt = 600.0, 500.0
    pc = t.variant_props("CIRCUMSCRIBED", d, wdt, None, 0.0)
    pi = t.variant_props("INSCRIBED", d, wdt, None, 0.0)
    check("P-math-circ-600", close(pc["outer_cone_angle"], math.degrees(math.atan(250.0 / 600.0))), pc)
    check("P-math-insc-600", close(pi["outer_cone_angle"], math.degrees(math.atan(250.0 * math.sqrt(2) / 600.0))), pi)
    check("P-math-brief-22.6", abs(pc["outer_cone_angle"] - 22.62) < 0.01, pc["outer_cone_angle"])
    check("P-math-brief-14.0", abs(t.variant_props("CIRCUMSCRIBED", 1000.0, 500.0, None, 0)["outer_cone_angle"] - 14.04) < 0.01, "")
    check("P-math-inner", close(pc["inner_cone_angle"], pc["outer_cone_angle"] - 1.0), pc)
    check("P-math-zero-sources", pc["source_radius"] == 0 and pc["soft_source_radius"] == 0 and pc["source_length"] == 0, pc)
    check("P-math-fade-att", close(pc["light_function_fade_distance"], 800) and close(pc["attenuation_radius"], 900), pc)
    check("P-math-fade-floor", close(t.variant_props("CIRCUMSCRIBED", 600, 500, 4000.0, 0)["light_function_fade_distance"], 4000), "")
    check("P-math-att-keeps-larger", close(t.variant_props("CIRCUMSCRIBED", 600, 500, None, 4500.0)["attenuation_radius"], 4500), "")
    # footprint: perpendicular incidence, circumscribed -> cell side == W, disc == W
    spot = {"loc": [-600.0, 0.0, 0.0], "pitch": 0.0, "yaw": 0.0, "roll": 0.0}
    big = {"loc": [0, 0, 0], "pitch": 0, "yaw": 0, "roll": 0, "lo": [0, -1000, -1000], "hi": [1, 1000, 1000]}
    h2 = t.ray_box(spot["loc"], [1, 0, 0], big)
    fp = t.footprint(spot, pc["outer_cone_angle"], big, h2)
    check("P-footprint-circ-perp", close(fp["cell_width_cm"], 500, 1e-6) and close(fp["cell_height_cm"], 500, 1e-6)
          and close(fp["disc_width_cm"], 500, 1e-3), fp)
    fpi = t.footprint(spot, pi["outer_cone_angle"], big, h2)
    check("P-footprint-insc-perp", close(fpi["cell_width_cm"], 500 * math.sqrt(2), 1e-6), fpi)
    small = dict(big, lo=[0, -200, -200], hi=[1, 200, 200])
    fps = t.footprint(spot, pc["outer_cone_angle"], small, t.ray_box(spot["loc"], [1, 0, 0], small))
    check("N-footprint-clips", fps["cell_inside_face"] is False, fps)
    # verifiers can fail
    check("N-readback-detects", bool(t.readback_failures({"a": 1.0}, {"a": 2.0})), "")
    check("N-readback-missing", bool(t.readback_failures({}, {"a": 2.0})), "")
    check("N-census-foreign", bool(t.exact_census({"content": [SEQ, "/Game/X"], "maps": []}, SEQ)), "")
    check("N-census-map", bool(t.exact_census({"content": [SEQ], "maps": ["/Game/M"]}, SEQ)), "")
    check("P-census-exact", not t.exact_census({"content": [SEQ], "maps": []}, SEQ), "")
    # args
    for bad, code in (({"mode": "APPLY", "run_id": "r1"}, "VARIANT"), ({"mode": "DRY", "run_id": "bad id"}, "RUN_ID"),
                      ({"mode": "DRY", "run_id": "r", "light_labels": ["A"]}, "LIGHT_LABELS"),
                      ({"mode": "DRY", "run_id": "r", "zzz": 1}, "UNKNOWN_ARGS"),
                      ({"mode": "DRY", "run_id": "r", "gc_local_boxes": {GC: {"x": [0]}}}, "GC_LOCAL_BOX")):
        try:
            t.normalized_args(bad)
            check("N-args-%s" % code, False, "accepted")
        except t.PlanError as exc:
            check("N-args-%s" % code, code in str(exc), exc)


def scene_tests(t):
    # ---------------- positive: DRY on the I2 geometry
    e = Env(t)
    err, rep = e.dry("D1", target_width_cm=432.0)
    check("P-dry-ok", err is None and rep and rep["apply_ready"], (err, rep and rep["refusals"]))
    check("P-dry-marker", any("GOBOSPOT_DRY_OK|run=D1|mutated=0|apply_ready=1" in m for m in e.markers("GOBOSPOT_DRY_OK")),
          e.markers("GOBOSPOT"))
    check("P-dry-no-dirty", not e.w.dirty and not e.w.saves, (e.w.dirty, e.w.saves))
    plan = rep["plan"]
    tw = plan["twins"]
    dh, dm = tw["Shadow Play Spot (Hangar)"]["d_max_cm"], tw["Shadow Play Spot (Mouth)"]["d_max_cm"]
    # the mouth card face is 2 cm in front of the drape's front fold (-43.3 vs -41.3) but the card is not a curtain
    check("P-dry-D-3000", abs(dm - 3000.0) < 0.05 and abs(dh - dm) < 0.05, (dh, dm))
    check("P-dry-curtain-is-drape", tw["Shadow Play Spot (Mouth)"]["curtain"] == "Transition Drape (baked)" and
          tw["Shadow Play Spot (Hangar)"]["curtain"] == "Sleight Hangar Drape", tw)
    check("P-dry-curtain-size", close(tw["Shadow Play Spot (Mouth)"]["curtain_width_cm"], 1880) and
          close(tw["Shadow Play Spot (Mouth)"]["curtain_height_cm"], 1000), tw["Shadow Play Spot (Mouth)"])
    check("P-dry-incidence-20", abs(tw["Shadow Play Spot (Mouth)"]["incidence_deg"] - 20.0) < 1e-6 and
          abs(tw["Shadow Play Spot (Hangar)"]["incidence_deg"] - 20.0) < 1e-6, tw)
    check("P-dry-nearer-card-flagged", any(f.startswith("NEARER_SURFACE|Shadow Play Spot (Mouth)|") and "Shadow Card" in f
                                           for f in rep["flags"]), rep["flags"])
    check("P-dry-no-twin-flag", not any(f.startswith("TWIN_DISTANCE_DIFF") for f in rep["flags"]), rep["flags"])
    d, w = plan["d_cm"], plan["w_cm"]
    vc, vi = plan["variants"]["CIRCUMSCRIBED"], plan["variants"]["INSCRIBED"]
    check("P-plan-circ", close(vc["props"]["outer_cone_angle"], math.degrees(math.atan(216.0 / d)), 1e-5), vc["props"])
    check("P-plan-insc", close(vi["props"]["outer_cone_angle"], math.degrees(math.atan(216.0 * math.sqrt(2) / d)), 1e-5), vi["props"])
    check("P-plan-cell-W", close(vc["cell_side_perp_cm"], 432.0, 1e-6) and close(vi["cell_side_perp_cm"], 432 * math.sqrt(2), 1e-6),
          (vc["cell_side_perp_cm"], vi["cell_side_perp_cm"]))
    check("P-plan-insc-scale", close(vi["gobo_scale_for_image_W"], 1 / math.sqrt(2), 1e-5), vi)
    fp = vc["fits_on_curtain"]["Shadow Play Spot (Mouth)"]["at_ref_frame"]
    # 20 deg down-tilt: the disc's widest chord is exactly W; the cell's lower (farther) corners spread wider
    # (keystone, bbox ~2.7 % over W) and the height stretches by ~1/cos(20)
    check("P-plan-oblique-footprint", abs(fp["disc_width_cm"] - 432.0) < 0.5 and 432.0 < fp["cell_width_cm"] < 432 * 1.05 and
          432 / math.cos(math.radians(20)) * 0.97 < fp["cell_height_cm"] < 432 / math.cos(math.radians(20)) * 1.03, fp)
    check("P-plan-fits", vc["fits_on_curtain"]["Shadow Play Spot (Mouth)"]["cell_inside_face"] is True, vc["fits_on_curtain"])
    # camera: mouth camera at 1200 cm from drape origin -> 1158.7 cm to the hit; hangar camera attached -> unusable
    cam = plan["camera"]
    check("P-camera", abs(cam["max_cm"] - 1158.7) < 0.5 and any(r.get("unusable") for r in cam["rows"]), cam)
    check("P-fade", close(vc["props"]["light_function_fade_distance"], d + 200.0, 1e-6), vc["props"])
    check("P-att", close(vc["props"]["attenuation_radius"], 4500.0), vc["props"])
    check("P-dry-fade-lowers-flag", any(f.startswith("FADE_LOWERS_CURRENT") for f in rep["flags"]), rep["flags"])
    check("P-dry-keyed-intensity-reported", any(r["prop"] == "intensity" for r in rep["keyed"]["Shadow Play Spot (Hangar)"])
          and plan["keyed_skipped"] == [], rep["keyed"])
    check("P-dry-cvars", rep["cvars"]["r.LightFunctionAtlas.SlotResolution"] == 32, rep["cvars"])

    # ---------------- positive: APPLY circumscribed, identical on both twins
    before_h = dict(e.comp("Shadow Play Spot (Hangar)").props)
    err = e.run(e.args("APPLY", "D1", "CIRCUMSCRIBED", target_width_cm=432.0))
    check("P-apply-ok", err is None and e.markers("GOBOSPOT_APPLY_OK|run=D1|variant=CIRCUMSCRIBED"), (err, e.markers("GOBOSPOT")))
    ch, cm = e.comp("Shadow Play Spot (Hangar)"), e.comp("Shadow Play Spot (Mouth)")
    want = vc["write"]
    check("P-apply-values", all(close(ch.props[k], v, 1e-6) and close(cm.props[k], v, 1e-6) for k, v in want.items()), want)
    check("P-apply-identical-twins", all(ch.props[k] == cm.props[k] for k in t.WRITE_PROPS), "")
    check("P-apply-untouched", all(ch.props[k] == before_h[k] for k in before_h if k not in want), "")
    check("P-apply-saved-once", e.w.saves == [SEQ] and not e.w.dirty, (e.w.saves, e.w.dirty))
    rec = e.record()
    check("P-apply-record", rec and rec["applied"] and rec["variant"] == "CIRCUMSCRIBED" and
          close(rec["before"]["Shadow Play Spot (Hangar)"]["outer_cone_angle"], 3.433630362450522), rec and rec.get("applied"))
    check("P-apply-backup", os.path.isfile(os.path.join(e.tmp, "Backups", "PreGoboSpot-D1", "LS_Interaction_02_Turnips.uasset")), "")

    # ---------------- negative: re-APPLY over a record
    err2, rep2 = e.dry("D2", target_width_cm=432.0)
    check("N-reapply-dry-refuses", rep2 and not rep2["apply_ready"] and any(r.startswith("RECORD_EXISTS") for r in rep2["refusals"]),
          rep2 and rep2["refusals"])
    saves = len(e.w.saves)
    err = e.run(e.args("APPLY", "D2", "INSCRIBED", target_width_cm=432.0))
    check("N-reapply-apply-stops", err and "RECORD_EXISTS" in err and len(e.w.saves) == saves and
          close(ch.props["outer_cone_angle"], want["outer_cone_angle"], 1e-9), err)

    # ---------------- positive: the gobo tool later sets the light function -> REVERT still allowed
    ch.props["light_function_material"] = Asset("/Game/InfinityStage/Lighting/Gobo/MI_ShadowGobo_P6_TestBird")
    cm.props["light_function_material"] = ch.props["light_function_material"]
    err = e.run(e.args("REVERT", "R1"))
    check("P-revert-ok", err is None and e.markers("GOBOSPOT_REVERT_OK|run=R1"), (err, e.markers("GOBOSPOT")))
    check("P-revert-exact", all(ch.props[k] == before_h[k] for k in t.WRITE_PROPS), "")
    check("P-revert-keeps-other-tools", ch.props["light_function_material"] is not None, "")
    check("P-revert-archived", not os.path.isfile(t.record_path(SEQ)) and
          os.path.isfile(t.record_path(SEQ) + ".reverted-R1"), "")
    check("N-revert-nothing", "NOTHING_TO_REVERT" in (e.run(e.args("REVERT", "R2")) or ""), "")

    # ---------------- positive: variant B after revert
    ch.props["light_function_material"] = None
    cm.props["light_function_material"] = None
    err, rep3 = e.dry("D3", target_width_cm=432.0)
    err = e.run(e.args("APPLY", "D3", "INSCRIBED", target_width_cm=432.0))
    check("P-apply-B", err is None and close(ch.props["outer_cone_angle"], math.degrees(math.atan(216 * math.sqrt(2) / d)), 1e-5)
          and ch.props["outer_cone_angle"] == cm.props["outer_cone_angle"], err)

    # ---------------- negative: REVERT drift
    cm.props["outer_cone_angle"] = 9.0
    saves = len(e.w.saves)
    err = e.run(e.args("REVERT", "R3"))
    check("N-revert-drift", err and "STATE_DRIFTED_SINCE_APPLY" in err and len(e.w.saves) == saves and
          ch.props["outer_cone_angle"] != before_h["outer_cone_angle"] and os.path.isfile(t.record_path(SEQ)), err)
    check("P-no-ue-globals", not no_ue_globals(t), no_ue_globals(t))
    e.close()

    # ---------------- negative: only one twin
    e = Env(t, drop_mouth=True)
    err, rep = e.dry("O1")
    check("N-one-twin-dry", rep and not rep["apply_ready"] and any(r.startswith("LIGHT_LABEL_COUNT|Shadow Play Spot (Mouth)|0")
                                                                  for r in rep["refusals"]), rep and rep["refusals"])
    err = e.run(e.args("APPLY", "O1", "CIRCUMSCRIBED"))
    check("N-one-twin-apply", err and "REFUSED" in err and not e.w.saves and not e.w.dirty and e.record() is None, err)
    e.close()

    # ---------------- negative: curtain not hit (mouth spot turned 90 degrees)
    e = Env(t, mouth_yaw=90.0)
    err, rep = e.dry("C1")
    check("N-curtain-not-hit", rep and not rep["apply_ready"] and
          any(r.startswith("CURTAIN_NOT_HIT|Shadow Play Spot (Mouth)") for r in rep["refusals"]), rep and rep["refusals"])
    e.close()

    # ---------------- negative: GC box unknown -> drape unmeasurable -> no curtain
    e = Env(t)
    a = e.args("DRY", "G1")
    a["gc_local_boxes"] = {}
    e.run(a)
    rep = t._load_json(t.dry_path("G1"))
    check("N-gc-box-unknown", rep and not rep["apply_ready"] and any(r.startswith("CURTAIN_NOT_HIT") for r in rep["refusals"])
          and any("GC_BOX_UNKNOWN" in str(c.get("unmeasurable")) for c in rep["candidates"]), rep and rep["refusals"])
    e.close()

    # ---------------- negative: twins differ > 5 % must be flagged; 2 % must not
    for pct, expect in ((0.10, True), (0.02, False)):
        back = 3000.0 * pct
        loc = [SPOT_M[0] - back * math.cos(math.radians(20)), SPOT_M[1], SPOT_M[2] + back * math.sin(math.radians(20))]
        e = Env(t, mouth_spot=loc)
        err, rep = e.dry("T%d" % int(pct * 100))
        flagged = any(f.startswith("TWIN_DISTANCE_DIFF") for f in rep["flags"])
        check("%s-twins-%d%%" % ("N" if expect else "P", int(pct * 100)), flagged == expect and
              close(rep["plan"]["d_cm"], 3000.0 * (1 + pct), 1e-4), (rep["flags"], rep["plan"]["d_cm"]))
        e.close()

    # ---------------- negative: a keyed property must not be written (on either twin)
    e = Env(t, keyed_source_radius=True)
    err, rep = e.dry("K1", target_width_cm=432.0)
    check("N-keyed-reported", "source_radius" in rep["plan"]["keyed_skipped"] and
          "source_radius" not in rep["plan"]["variants"]["CIRCUMSCRIBED"]["write"] and
          any(f == "KEYED_NOT_WRITTEN|source_radius" for f in rep["flags"]), rep["plan"]["keyed_skipped"])
    err = e.run(e.args("APPLY", "K1", "CIRCUMSCRIBED", target_width_cm=432.0))
    ch, cm = e.comp("Shadow Play Spot (Hangar)"), e.comp("Shadow Play Spot (Mouth)")
    check("N-keyed-not-written", err is None and ch.props["source_radius"] == 2.0 and cm.props["source_radius"] == 2.0 and
          ch.props["soft_source_radius"] == 0.0, (err, ch.props["source_radius"], cm.props["source_radius"]))
    keys = [tr for b in e.w.seq.bindings for tr in b.tracks if getattr(tr, "_prop", None) == "SourceRadius"]
    check("N-keyed-keys-untouched", len(keys) == 1 and keys[0].get_sections()[0].get_all_channels()[0].get_keys()[0].v == 2.0, "")
    e.close()

    # ---------------- negative: lying setter
    e = Env(t, lie=("outer_cone_angle",))
    e.dry("L1", target_width_cm=432.0)
    before = dict(e.comp("Shadow Play Spot (Mouth)").props)
    err = e.run(e.args("APPLY", "L1", "CIRCUMSCRIBED", target_width_cm=432.0))
    rec = e.record()
    check("N-lying-setter", err and "PRESAVE_READBACK" in err and "outer_cone_angle" in err and not e.w.saves
          and rec and rec["applied"] is False, err)
    check("N-lying-setter-restored", all(e.comp("Shadow Play Spot (Mouth)").props[k] == before[k] for k in t.WRITE_PROPS), "")
    err = e.run(e.args("REVERT", "L2"))
    check("N-revert-unapplied-record", err and "RECORD_NOT_APPLIED" in err, err)
    e.close()

    # ---------------- negative: preflight refusals and stale DRY
    for name, mutate, code in (("pie", lambda w: setattr(w, "pie", True), "PIE_OR_SIE_ACTIVE"),
                               ("seq-open", lambda w: setattr(w, "open_seq", w.seq), "SEQUENCER_IS_OPEN"),
                               ("dirty", lambda w: w.dirty.add("/Game/Other"), "DIRTY_CENSUS"),
                               ("world", lambda w: setattr(w, "world", "/Game/Other/Map"), "WRONG_WORLD")):
        e = Env(t)
        e.dry("Q1")
        mutate(e.w)
        err = e.run(e.args("APPLY", "Q1", "CIRCUMSCRIBED"))
        check("N-%s" % name, err and code in err and e.record() is None and not e.w.saves, err)
        e.close()
    e = Env(t)
    err = e.run(e.args("APPLY", "S1", "CIRCUMSCRIBED"))
    check("N-apply-without-dry", err and "DRY_NOT_CURRENT" in err and e.record() is None, err)
    e.dry("S2")
    e.comp("Shadow Play Spot (Hangar)").props["attenuation_radius"] = 6000.0     # state changed after DRY
    err = e.run(e.args("APPLY", "S2", "CIRCUMSCRIBED"))
    check("N-stale-dry", err and "DRY_NOT_CURRENT" in err and e.record() is None, err)
    a = e.args("APPLY", "S2", "CIRCUMSCRIBED")
    a["confirm"] = "APPLY GOBOSPOT INSCRIBED"
    err = e.run(a)
    check("N-confirm-mismatch", err and "CONFIRM_MISMATCH" in err, err)
    e.close()

    # ---------------- negative: a foreign package becomes dirty during the write
    e = Env(t)
    e.dry("F1")
    e.w.extra_dirty_on_set = "/Game/Foreign/Thing"
    err = e.run(e.args("APPLY", "F1", "CIRCUMSCRIBED"))
    check("N-foreign-dirty", err and "CENSUS_SCOPE" in err and not e.w.saves, err)
    e.close()

    # ---------------- positive: camera distance arg raises the fade floor
    e = Env(t)
    err, rep = e.dry("CF", camera_distance_cm=3000.0)
    check("P-fade-camera-floor", close(rep["plan"]["variants"]["CIRCUMSCRIBED"]["props"]["light_function_fade_distance"],
                                       3000.0 / 0.8 + 200.0, 1e-6), rep["plan"]["camera"])
    # default W = 0.9 x curtain width
    err, rep = e.dry("DW")
    check("P-default-W", close(rep["plan"]["w_cm"], 0.9 * 1880.0, 1e-6) and rep["plan"]["w_source"].startswith("0.9"), rep["plan"]["w_cm"])
    e.close()


def main():
    tool = load_tool()
    pure_tests(tool)
    scene_tests(tool)
    passed = sum(r["ok"] for r in RESULTS)
    failed = len(RESULTS) - passed
    report = {"passed": passed, "failed": failed, "total": len(RESULTS), "results": RESULTS,
              "python": sys.version.split()[0]}
    with open(os.path.join(HERE, "test_gobo_spot_report.json"), "w", encoding="utf-8", newline="\n") as h:
        json.dump(report, h, indent=1)
    print("\nGOBOSPOT_HARNESS|passed=%d|failed=%d|total=%d" % (passed, failed, len(RESULTS)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
