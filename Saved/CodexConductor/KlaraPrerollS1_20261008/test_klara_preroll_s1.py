"""Offline harness for klara_preroll_s1.py (8 Oct). Runs with plain CPython; nothing touches Unreal.
  python test_klara_preroll_s1.py          -> prints "HARNESS n/n passed" (exit 1 on any failure)
Parts: pure planning (mapping, loop shifts, alignment, strip, gates, revert drift, probe classification), a FAKE editor
(an injected `unreal` module) driving DRY / APPLY / DRY-after / REVERT, and negative controls that must FAIL.
Fake fixtures use the report's [bin] section table (S1_ANIMALS_SNAP_INVESTIGATION_2026-10-08.md section 2) and the reveal
record's slot (klara_reveal_record_S1.json: [594, 5769), 86400 ticks, her frame -202). The fake's mapping and
loop semantics are the tool's own assumptions [inf]; the harness proves the tool's arithmetic and guards, not UE.
"""
import ast
import copy as _copy
import json
import math
import os
import shutil
import struct
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_01"
COPY = "/Game/InfinityStage/KlaraHookin/LS_Animals_1_S1Hangar"
DUP = "/Game/InfinityStage/KlaraHookin/LS_Animals_1_S1Preroll"
HERS = "/Game/KK_S1_Animals/LS_Animals_1"
L_ANIMALS = "/Game/KK_S1_Animals/L_Animals"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"


def f32(x):
    return struct.unpack("f", struct.pack("f", float(x)))[0]


# =====================================================================================================================
# Fake unreal
# =====================================================================================================================

class _R:
    pass


R = _R()


def _reset(root):
    R.root = root
    R.assets, R.dirty, R.dirty_maps, R.saved, R.logs = {}, set(), set(), [], []
    R.open_seq, R.pie_world, R.sabotage, R.actors, R.levels = None, None, set(), [], []


def _dirty(seq):
    R.dirty.add(seq.path)


class Cls:
    def __init__(self, n):
        self.n = n

    def get_name(self):
        return self.n


class Obj:
    def get_class(self):
        return Cls(type(self).__name__)


class FR:
    def __init__(self, n, d=1):
        self.numerator, self.denominator = n, d


class FrameNumber:
    def __init__(self, v):
        self.value = int(v)


class Struct:
    def __init__(self, **kw):
        self._d = dict(kw)

    def get_editor_property(self, k):
        if k not in self._d:
            raise AttributeError(k)
        return self._d[k]

    def set_editor_property(self, k, v):
        self._d[k] = v


class TimeWarp:
    def __init__(self, rate):
        self.rate = rate

    def to_fixed_play_rate(self):
        return self.rate


class AnimSequenceBase(Obj):
    def __init__(self, path, length):
        self.path, self.length = path, f32(length)

    def get_play_length(self):
        return self.length

    def get_path_name(self):
        return self.path + "." + self.path.rsplit("/", 1)[-1]


class MovieSceneSection(Obj):
    def __init__(self, owner, start=None, end=None):
        self.owner, self.start, self.end, self.completion = owner, start, end, None

    def _tpf(self):
        return int(round(_rate(self.owner.tick) / _rate(self.owner.fps)))

    def has_start_frame(self):
        return self.start is not None

    def has_end_frame(self):
        return self.end is not None

    def get_start_frame(self):
        return int(math.floor(self.start / float(self._tpf())))

    def get_end_frame(self):
        return int(math.floor(self.end / float(self._tpf())))

    def get_start_frame_seconds(self):
        return f32(self.start / _rate(self.owner.tick))

    def get_end_frame_seconds(self):
        return f32(self.end / _rate(self.owner.tick))

    def set_start_frame(self, f):
        self.start = int(f) * self._tpf() + (self._tpf() if "extend_off_by_frame" in R.sabotage else 0)
        _dirty(self.owner)

    def set_start_frame_seconds(self, sec):
        # fake model [inf]: UE's seconds->tick rounding is .cpp only; the tool must not rely on it (read-back decides)
        t = f32(sec) * _rate(self.owner.tick)
        self.start = int(math.floor(t)) - 1 if "seconds_setter_floors" in R.sabotage else int(round(t))
        _dirty(self.owner)

    def set_range(self, a, b):
        self.start, self.end = int(a) * self._tpf(), (int(b) + (1 if "range_past_cut" in R.sabotage else 0)) * self._tpf()
        _dirty(self.owner)

    def set_completion_mode(self, m):
        self.completion = m
        _dirty(self.owner)


class MovieSceneSkeletalAnimationSection(MovieSceneSection):
    def __init__(self, owner, start, end, anim, first_loop=0):
        MovieSceneSection.__init__(self, owner, start, end)
        self.params = Struct(animation=anim, start_frame_offset=FrameNumber(0), end_frame_offset=FrameNumber(0),
                             first_loop_start_frame_offset=FrameNumber(first_loop), play_rate=TimeWarp(1.0),
                             reverse=False)

    def get_editor_property(self, k):
        if k != "params":
            raise AttributeError(k)
        return self.params


class MovieSceneSubSection(MovieSceneSection):
    def __init__(self, owner, start=None, end=None, seq=None, offset=0):
        MovieSceneSection.__init__(self, owner, start, end)
        self.seq_path = seq.path if seq is not None else None
        self.parameters = Struct(start_frame_offset=FrameNumber(offset))

    def set_sequence(self, s):
        self.seq_path = s.path
        _dirty(self.owner)

    def get_sequence(self):
        return R.assets.get(self.seq_path)

    def get_editor_property(self, k):
        if k != "parameters":
            raise AttributeError(k)
        return Struct(**_copy.deepcopy(self.parameters._d))          # struct copy semantics

    def set_editor_property(self, k, v):
        self.parameters = v
        _dirty(self.owner)


class MovieSceneCinematicShotSection(MovieSceneSubSection):
    pass


class MovieSceneCameraCutSection(MovieSceneSection):
    pass


class Key:
    def __init__(self, t, v):
        self.t, self.v = t, v

    def get_time(self, time_unit=None):
        return types.SimpleNamespace(frame_number=FrameNumber(self.t))

    def get_value(self):
        return self.v


class Channel:
    def __init__(self, name, keys, default=None):
        self.channel_name, self.keys, self.default = name, keys, default

    def get_keys(self):
        return [Key(t, v) for t, v in self.keys]

    def has_default(self):
        return self.default is not None

    def get_default(self):
        return self.default


class MovieScene3DTransformSection(MovieSceneSection):
    def __init__(self, owner, start, end, loc):
        MovieSceneSection.__init__(self, owner, start, end)
        self.channels = [Channel("Location.%s_%d" % (ax, 100 + i), [(800 * 3000, loc[i]), (800 * 4000, loc[i] + 50)])
                         for i, ax in enumerate("XYZ")]

    def get_all_channels(self):
        return list(self.channels)


class MovieSceneTrack(Obj):
    SECTION = MovieSceneSection

    def __init__(self, owner, name=""):
        self.owner, self.name, self.sections = owner, name, []

    def get_sections(self):
        return list(self.sections)

    def get_display_name(self):
        return self.name

    def set_display_name(self, n):
        self.name = n
        _dirty(self.owner)

    def add_section(self):
        s = self.SECTION(self.owner)
        self.sections.append(s)
        _dirty(self.owner)
        return s

    def remove_section(self, s):
        self.sections.remove(s)
        _dirty(self.owner)


class MovieSceneSubTrack(MovieSceneTrack):
    SECTION = MovieSceneSubSection


class MovieSceneCinematicShotTrack(MovieSceneSubTrack):
    SECTION = MovieSceneCinematicShotSection


class MovieSceneCameraCutTrack(MovieSceneTrack):
    pass


class MovieSceneSkeletalAnimationTrack(MovieSceneTrack):
    pass


class MovieSceneControlRigParameterTrack(MovieSceneTrack):
    pass


class MovieScene3DTransformTrack(MovieSceneTrack):
    pass


class MovieSceneFloatTrack(MovieSceneTrack):
    pass


class MovieSceneAudioTrack(MovieSceneTrack):
    pass


class _Invalid:
    def is_valid(self):
        return False


class Binding:
    def __init__(self, owner, guid, name, parent=None):
        self.owner, self.guid, self.name, self.parent, self.tracks = owner, guid, name, parent, []

    def is_valid(self):
        return True

    def get_id(self):
        return self.guid

    def get_display_name(self):
        return self.name

    def get_parent(self):
        return self.parent if self.parent is not None else _Invalid()

    def get_tracks(self):
        return list(self.tracks)

    def remove(self):
        self.owner.bindings = [b for b in self.owner.bindings if b is not self]
        _dirty(self.owner)

    def remove_track(self, t):
        if "keep_transform" in R.sabotage and isinstance(t, MovieScene3DTransformTrack):
            return None
        self.tracks = [x for x in self.tracks if x is not t]
        _dirty(self.owner)

    def add(self, cls, name=""):
        t = cls(self.owner, name)
        self.tracks.append(t)
        return t


def _rate(fr):
    return float(fr.numerator) / float(fr.denominator)


class LevelSequence(Obj):
    def __init__(self, path, tick, fps, start, end):
        self.path, self.tick, self.fps, self.pstart, self.pend = path, FR(tick), FR(fps), start, end
        self.tracks, self.bindings = [], []

    def get_path_name(self):
        return self.path + "." + self.path.rsplit("/", 1)[-1]

    def get_tracks(self):
        return list(self.tracks)

    def get_bindings(self):
        return list(self.bindings)

    def get_tick_resolution(self):
        return self.tick

    def get_display_rate(self):
        return self.fps

    def get_playback_start(self):
        return self.pstart

    def get_playback_start_seconds(self):
        tpf = _rate(self.tick) / _rate(self.fps)
        return f32((self.pstart * tpf + (1 if "pstart_off" in R.sabotage else 0)) / _rate(self.tick))

    def get_playback_end(self):
        return self.pend

    def set_playback_start(self, f):
        self.pstart = int(f)
        _dirty(self)

    def add_track(self, cls, name=""):
        t = cls(self, name)
        self.tracks.append(t)
        _dirty(self)
        return t

    def remove_track(self, t):
        self.tracks = [x for x in self.tracks if x is not t]
        _dirty(self)
        return None                                           # memory: return values lie

    def bind(self, guid, name, parent=None):
        b = Binding(self, guid, name, parent)
        self.bindings.append(b)
        return b


class Vec:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class _Outer:
    def __init__(self, p):
        self.p = p

    def get_path_name(self):
        return self.p

    def get_name(self):
        return self.p.rsplit("/", 1)[-1]


class Level:
    def __init__(self, pkg):
        self.outer = _Outer(pkg)

    def get_outer(self):
        return self.outer


class Actor(Obj):
    def __init__(self, label, name, level, loc):
        self.label, self.name, self.level, self.loc = label, name, level, loc

    def get_actor_label(self):
        return self.label

    def get_name(self):
        return self.name

    def get_level(self):
        return self.level

    def get_actor_location(self):
        return Vec(*self.loc)


class _Pkg:
    def __init__(self, p):
        self.p = p

    def get_path_name(self):
        return self.p


def _file(path, ext=".uasset"):
    return os.path.join(R.root, "Content", *path[len("/Game/"):].split("/")) + ext


def _write_file(path):
    fp = _file(path)
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, "wb") as h:
        h.write(("fake %s %d" % (path, len(R.saved))).encode())


class EditorAssetLibrary:
    @staticmethod
    def duplicate_asset(src, dst):
        if dst in R.assets or src not in R.assets:
            return None
        new = _copy.deepcopy(R.assets[src])
        new.path = dst
        R.assets[dst] = new
        R.dirty.add(dst)
        return new

    @staticmethod
    def does_asset_exist(p):
        return p in R.assets

    @staticmethod
    def save_asset(p, only_if_is_dirty=True):
        R.saved.append(p)
        R.dirty.discard(p)
        _write_file(p)
        return True

    @staticmethod
    def find_package_referencers_for_asset(p, load=False):
        out = []
        for path, a in R.assets.items():
            if isinstance(a, LevelSequence):
                for t in a.tracks:
                    for s in t.sections:
                        if isinstance(s, MovieSceneSubSection) and s.seq_path == p:
                            out.append(path)
        return sorted(set(out))


class EditorLoadingAndSavingUtils:
    @staticmethod
    def get_dirty_content_packages():
        return [_Pkg(p) for p in sorted(R.dirty)]

    @staticmethod
    def get_dirty_map_packages():
        return [_Pkg(p) for p in sorted(R.dirty_maps)]


class _World:
    def __init__(self, name):
        self.name = name

    def get_outermost(self):
        return types.SimpleNamespace(get_name=lambda: self.name)


class UnrealEditorSubsystem:
    def get_game_world(self):
        return R.pie_world

    def get_editor_world(self):
        return _World(WORLD)


class EditorActorSubsystem:
    def get_all_level_actors(self):
        return list(R.actors)


def _psf(sec, in_frame, parent):
    inner = sec.get_sequence()
    itpf = int(round(_rate(inner.tick) / _rate(inner.fps)))
    off = sec.parameters.get_editor_property("start_frame_offset").value
    parent_tick = sec.start + (int(in_frame) * itpf - (inner.pstart * itpf + off))
    ptpf = _rate(parent.tick) / _rate(parent.fps)
    return int(math.floor(parent_tick / ptpf + 1e-9)) + (2 if "psf_off" in R.sabotage else 0)


def make_fake():
    u = types.ModuleType("unreal")
    u._PUSS_FAKE = True
    for c in (MovieSceneSection, MovieSceneSkeletalAnimationSection, MovieSceneSubSection, MovieSceneCinematicShotSection,
              MovieSceneTrack, MovieSceneSubTrack, MovieSceneCinematicShotTrack, MovieSceneCameraCutTrack,
              MovieSceneSkeletalAnimationTrack, MovieSceneControlRigParameterTrack, MovieScene3DTransformTrack,
              MovieSceneFloatTrack, MovieSceneAudioTrack, AnimSequenceBase, EditorAssetLibrary,
              EditorLoadingAndSavingUtils, UnrealEditorSubsystem, EditorActorSubsystem, FrameNumber):
        setattr(u, c.__name__, c)
    u.Paths = types.SimpleNamespace(project_saved_dir=lambda: os.path.join(R.root, "Saved"),
                                    project_dir=lambda: R.root, convert_relative_path_to_full=lambda p: p)
    u.GuidLibrary = types.SimpleNamespace(conv_guid_to_string=lambda g: str(g))
    u.get_editor_subsystem = lambda cls: cls()
    u.load_asset = lambda p: R.assets.get(p)
    u.LevelSequenceEditorBlueprintLibrary = types.SimpleNamespace(get_current_level_sequence=lambda: R.open_seq)
    u.EditorLevelUtils = types.SimpleNamespace(get_levels=lambda w: list(getattr(w, "levels", None) or R.levels))
    u.MovieSceneSectionExtensions = types.SimpleNamespace(get_parent_sequence_frame=_psf, set_start_frame=1,
                                                          set_start_frame_seconds=1, get_start_frame_seconds=1,
                                                          get_end_frame_seconds=1)
    u.MovieSceneBindingExtensions = types.SimpleNamespace(remove_track=1, remove=1)
    u.MovieSceneSequenceExtensions = types.SimpleNamespace(set_playback_start=1, get_playback_start_seconds=1)
    u.MovieSceneTimeWarpExtensions = types.SimpleNamespace(to_fixed_play_rate=1)
    u.MovieSceneCompletionMode = types.SimpleNamespace(RESTORE_STATE="RESTORE_STATE", KEEP_STATE="KEEP_STATE")
    u.log = lambda m: R.logs.append(("log", m))
    u.log_warning = lambda m: R.logs.append(("warn", m))
    u.log_error = lambda m: R.logs.append(("error", m))
    return u


sys.modules["unreal"] = make_fake()
sys.path.insert(0, HERE)
import klara_preroll_s1 as P  # noqa: E402  (the fake carries _PUSS_FAKE: importing runs nothing)


# =====================================================================================================================
# Fixtures
# =====================================================================================================================

LOC = {"Pig_anim_RM": (100.0, 200.0, 10.0), "RedDeer_Calf_anim_IP": (300.0, 250.0, 12.0),
       "medhue_raccoon": (150.0, 400.0, 8.0)}


BIN_SPEC = {   # [bin] S3Diag/s3_seq_sem.py Model over Content/InfinityStage/KlaraHookin/LS_Animals_1_S1Hangar.uasset
    # (sha256 7d0e9eaa...f998bf, 8 Oct): the skeletal sections around the cut, exact ticks. Pig Section_10's END is
    # -17199 t = -0.7166249752 s (f32) = her frame -21.499: the bound the 8 Oct live DRY refused (SECTION_OFF_FRAME).
    "Pig_anim_RM": [(-235200, -135199, "Pig_Eat_loop_1", 0), (-144800, -36799, "Pig_Eat_loop_2", 92000),
                    (-43200, -17199, "Pig_Eat_loop_1", 0), (-25600, 320800, "Pig_Eat_loop_1", 0),
                    (322400, 422401, "Pig_Eat_loop_1", 0)],
    "RedDeer_Calf_anim_IP": [(-235200, -135199, "Deer_Eat_loop", 0), (-147200, 8000, "Deer_EatDig_loop", 0),
                             (-5600, 94401, "Deer_EatDig_loop", 0)],
    "medhue_raccoon": [(-234400, 347200, "Raccoon_Eating", 0)]}


def build_world(root, spec=None):
    _reset(root)
    t = lambda s: int(round(s * 24000))
    copy = LevelSequence(COPY, 24000, 30, -310, 6008)
    lvl = Level(L_ANIMALS)
    R.levels = [lvl, Level(WORLD)]
    anims = {}
    for name, length in (("Pig_Eat_loop_1", 4.1666665), ("Pig_Eat_loop_2", 4.1666665), ("Deer_Eat_loop", 4.1666665),
                         ("Deer_EatDig_loop", 4.1666665), ("Raccoon_Eating", 2.7)):
        anims[name] = AnimSequenceBase("/Game/KK_S1_Animals/Anims/" + name, length)
    spec = spec or {
        "Pig_anim_RM": [(-235200, -135200, "Pig_Eat_loop_1", 0), (-144800, -36800, "Pig_Eat_loop_2", 92000)],
        "RedDeer_Calf_anim_IP": [(-235200, -135200, "Deer_Eat_loop", 0), (-147200, 8000, "Deer_EatDig_loop", 0)],
        "medhue_raccoon": [(-234400, 347200, "Raccoon_Eating", 0)]}
    for i, (name, secs) in enumerate(sorted(spec.items())):
        b = copy.bind("g-animal-%d" % i, name)
        tr = b.add(MovieScene3DTransformTrack)
        tr.sections.append(MovieScene3DTransformSection(copy, -310 * 800, 6008 * 800, LOC[name]))
        sk = b.add(MovieSceneSkeletalAnimationTrack)
        for a, e, an, fl in secs:
            sk.sections.append(MovieSceneSkeletalAnimationSection(copy, a, e, anims[an], fl))
        if name == "medhue_raccoon":
            b.add(MovieSceneSkeletalAnimationTrack)                       # her empty second skeletal track [bin]
        cr = b.add(MovieSceneControlRigParameterTrack)
        cr.sections.append(MovieSceneSection(copy, None, None))
        R.actors.append(Actor(name, "SkeletalMeshActor_%d" % (7 + 2 * i), lvl, LOC[name]))
    sp = copy.bind("g-spot", "SpotLight3")
    lc = copy.bind("g-spot-lc", "LightComponent0", sp)
    lc.add(MovieSceneFloatTrack, "Intensity").sections.append(MovieSceneSection(copy, 0, 8000))
    cam = copy.bind("g-cam", "CineCameraActor")
    cam.add(MovieScene3DTransformTrack).sections.append(MovieSceneSection(copy, 0, 8000))
    cc = copy.bind("g-cam-cc", "CameraComponent", cam)
    cc.add(MovieSceneFloatTrack, "CurrentFocalLength")
    copy.bind("g-floor", "Floor").add(MovieScene3DTransformTrack)
    copy.add_track(MovieSceneAudioTrack, "Audio").sections.append(MovieSceneSection(copy, 0, 8000))
    ct = copy.add_track(MovieSceneCameraCutTrack, "Camera Cuts")
    ct.sections += [MovieSceneCameraCutSection(copy, -248000, 323200), MovieSceneCameraCutSection(copy, 323200, 900000)]
    for a in ("SpotLight3", "CineCameraActor", "Floor"):
        R.actors.append(Actor(a, a, lvl, (0.0, 0.0, 0.0)))
    hers = _copy.deepcopy(copy)
    hers.path = HERS
    rise = LevelSequence("/Game/InfinityStage/RigAtmos/LS_S1_HangarRise", 24000, 30, 0, 900)
    scene = LevelSequence(SCENE, 24000, 25, 0, 6176)
    R.assets.update({COPY: copy, HERS: hers, rise.path: rise, SCENE: scene})
    shots = scene.add_track(MovieSceneCinematicShotTrack, "Shots")
    shots.sections.append(MovieSceneCinematicShotSection(scene, 594 * 960, 5769 * 960, copy, 86400))
    fold = scene.add_track(MovieSceneSubTrack, "Hangar Fold")
    fold.sections.append(MovieSceneSubSection(scene, 0, 775 * 960, rise, 0))
    scene.add_track(MovieSceneCameraCutTrack, "Camera Cuts")
    R.dirty.clear()
    for p in (COPY, HERS, SCENE, rise.path):
        _write_file(p)
    R.saved = []
    here = os.path.join(root, "Saved", "CodexConductor", P.FOLDER)
    os.makedirs(here, exist_ok=True)
    ki = os.path.join(root, "Saved", "CodexConductor", "KlaraIngest")
    os.makedirs(ki, exist_ok=True)
    P.write_json(os.path.join(ki, "klara_reveal_record_S1.json"), {"applied": True, "plan": {
        "slot": {"range": [594, 5769], "start_offset_ticks": 86400, "her_frame_at_cut": -202, "her_range": [-310, 6008]},
        "strike_schedule": {"frames": [282, 306, 326, 342, 364, 391, 411, 437, 464, 481, 502, 529, 551, 575]},
        "timeline": {"cut": 594}}})
    return here


def base_args(mode, **kw):
    a = P.load_json(os.path.join(HERE, "klara_preroll_s1_args.json"))
    a.update(mode=mode, run_id="TEST-%s" % mode, decided_by="harness" if mode == "APPLY" else "",
             confirm="%s KLARAPREROLLS1" % mode if mode in ("APPLY", "REVERT") else "")
    a.update(kw)
    return a


def run_tool(args):
    P.KLARAPREROLLS1_ARGS = args
    try:
        P.main()
        return None
    except Exception as exc:  # noqa: BLE001
        return exc
    finally:
        del P.KLARAPREROLLS1_ARGS


def markers(prefix):
    return [m for _lv, m in R.logs if m.startswith(prefix)]


def report_secs():
    """The report's [bin] skeletal sections (her ticks), as plan_loop_shifts input."""
    mk = lambda key, a, e, anim, ln, fl=0: {"key": key, "track": 0, "start": a, "end": e, "anim": anim, "len_s": ln,
                                           "tick_res": 24000.0, "start_off": 0, "end_off": 0, "first_loop_off": fl,
                                           "rate": 1.0, "reverse": False, "bounded": True}
    return {"Pig": [mk("S8", -235200, -135200, "Pig_Eat_loop_1", f32(4.1666665)),
                    mk("S9", -144800, -36800, "Pig_Eat_loop_2", f32(4.1666665), 92000)],
            "Deer": [mk("S14", -235200, -135200, "Deer_Eat_loop", f32(4.1666665)),
                     mk("S15", -147200, 8000, "Deer_EatDig_loop", f32(4.1666665))],
            "Raccoon": [mk("S16", -234400, 347200, "Raccoon_Eating", f32(2.7))]}


def mapping(pr=(282, 594)):
    return P.preroll_mapping(list(pr), {"range": [594, 5769], "offset_ticks": 86400}, -310, 24000.0, 30.0, 25.0)


# =====================================================================================================================
# Pure planning
# =====================================================================================================================

class Mapping(unittest.TestCase):
    def test_numbers(self):
        m = mapping()
        self.assertEqual(m["refusals"], [])
        self.assertEqual(m["cut_her_tick"], -161600)                 # her -6.733 s
        self.assertEqual(m["cut_her_frame"], -202.0)
        self.assertEqual(m["pre_start_her_tick"], -461120)           # her -19.213 s (report 4.2)
        self.assertEqual(m["dup_playback_start_frame"], -577)
        self.assertEqual(m["offset_ticks"], 480)

    def test_same_tick_every_frame_and_end_exclusive(self):
        m = mapping()
        for f in range(282, 594):
            self.assertEqual(P.her_tick_dup(m, f), P.her_tick_main(m, f))
        self.assertEqual(P.her_tick_dup(m, 593), m["cut_her_tick"] - 960)   # last evaluated frame = one frame before
        self.assertLess(m["range"][1] - 1, m["cut"])                          # evaluated frames end strictly < 594

    def test_past_cut_refused(self):
        self.assertTrue(any("DUP_PAST_CUT" in r for r in mapping((282, 600))["refusals"]))

    def test_gap_before_cut_refused(self):
        self.assertTrue(any("PREROLL_END_NOT_THE_CUT" in r for r in mapping((282, 590))["refusals"]))

    def test_empty_refused(self):
        self.assertTrue(any("PREROLL_EMPTY" in r for r in
                            P.preroll_mapping([594, 594], {"range": [594, 5769], "offset_ticks": 86400}, -310,
                                              24000.0, 30.0, 25.0)["refusals"]))


class LoopPlan(unittest.TestCase):
    def setUp(self):
        self.m = mapping()
        self.p = P.plan_loop_shifts(report_secs(), self.m, 0, {"Pig": 3, "Deer": 3, "Raccoon": 4})

    def test_rows(self):
        self.assertEqual(self.p["refusals"], [])
        by = {r["animal"]: r for r in self.p["rows"]}
        self.assertEqual({k: v["loops"] for k, v in by.items()}, {"Pig": 3, "Deer": 3, "Raccoon": 4})
        self.assertEqual(by["Pig"]["shift_ticks"], 300000)
        self.assertAlmostEqual(by["Pig"]["shift_s"], 12.5)
        self.assertEqual(by["Raccoon"]["shift_ticks"], 259200)
        self.assertAlmostEqual(by["Raccoon"]["shift_s"], 10.8)
        self.assertEqual(by["Pig"]["new_range"], [-535200, -135200])
        self.assertEqual(by["Raccoon"]["new_range"], [-493600, 347200])
        self.assertAlmostEqual(by["Pig"]["clip_time_at_cut_s"], 3.0667, places=3)     # report: 3.07 s
        self.assertAlmostEqual(by["Raccoon"]["clip_time_at_cut_s"], 0.3333, places=3)  # report: 0.33 s, 2nd loop
        self.assertEqual(by["Pig"]["key"], "S8")
        self.assertEqual(by["Deer"]["key"], "S14")

    def test_covers_and_aligned(self):
        self.assertEqual(P.check_alignment(self.p["rows"], self.m), [])
        for r in self.p["rows"]:
            self.assertLessEqual(r["new_range"][0], self.m["pre_start_her_tick"])
            self.assertGreater(r["new_range"][0] + r["loop_ticks"], self.m["pre_start_her_tick"])   # minimal k
            self.assertEqual((r["shift_ticks"]) % r["loop_ticks"], 0)
            self.assertEqual(r["shift_ticks"] % 800, 0)

    def test_report_five_loops_also_align(self):
        p = P.plan_loop_shifts(report_secs(), self.m, 1)
        by = {r["animal"]: r for r in p["rows"]}
        self.assertEqual(by["Raccoon"]["loops"], 5)
        self.assertEqual(P.check_alignment(p["rows"], self.m), [])

    def test_expected_loops_mismatch_refused(self):
        p = P.plan_loop_shifts(report_secs(), self.m, 0, {"Raccoon": 5})
        self.assertTrue(any("LOOPS_DIFFER_FROM_EXPECTED" in r for r in p["refusals"]))

    def test_NEG_misaligned_at_cut(self):
        rows = _copy.deepcopy(self.p["rows"])
        rows[0]["new_range"][0] -= 1000                       # not a whole number of loops
        self.assertTrue(any("MISALIGNED_AT_CUT" in r for r in P.check_alignment(rows, self.m)))

    def test_NEG_misaligned_mapping(self):
        m = dict(self.m, offset_ticks=self.m["offset_ticks"] + 960)
        bad = P.check_alignment(self.p["rows"], m)
        self.assertTrue(any("MAPPING_MISALIGNED" in r for r in bad) and any("MISALIGNED_AT_CUT" in r for r in bad))

    def test_NEG_dup_reaching_past_cut(self):
        self.assertTrue(any("DUP_PAST_CUT" in r for r in P.check_alignment(self.p["rows"], self.m, dup_range=[282, 595])))

    def test_NEG_offsets_rate_reverse(self):
        for k, v in (("start_off", 800), ("first_loop_off", 92000), ("rate", 1.5), ("reverse", True)):
            s = report_secs()
            s["Pig"][0][k] = v
            self.assertTrue(any("UNSUPPORTED_SECTION" in r for r in P.plan_loop_shifts(s, self.m)["refusals"]), k)

    def test_NEG_two_active_at_cut(self):
        s = report_secs()
        s["Raccoon"].append(dict(s["Raccoon"][0], key="S99"))
        self.assertTrue(any("ACTIVE_AT_CUT_COUNT" in r for r in P.plan_loop_shifts(s, self.m)["refusals"]))

    def test_NEG_unbounded_active_section(self):
        s = report_secs()
        s["Raccoon"][0].update(start=None, end=None, bounded=False)
        self.assertTrue(any("UNSUPPORTED_SECTION" in r and "unbounded" in r
                            for r in P.plan_loop_shifts(s, self.m)["refusals"]))

    def test_NEG_new_overlap(self):
        s = report_secs()
        s["Pig"].append(dict(s["Pig"][0], key="S7", start=-560000, end=-500000))
        self.assertTrue(any("NEW_OVERLAP" in r for r in P.plan_loop_shifts(s, self.m)["refusals"]))

    def test_NEG_clip_off_tick(self):
        s = report_secs()
        s["Pig"][0]["len_s"] = 4.1667                         # 100000.8 ticks: phase would drift
        self.assertTrue(any("CLIP_LEN_NOT_ON_TICK" in r or "SHIFT_NOT_ON_FRAME" in r
                            for r in P.plan_loop_shifts(s, self.m)["refusals"]))


class Strip(unittest.TestCase):
    ANIMALS = ["Pig_anim_RM", "RedDeer_Calf_anim_IP", "medhue_raccoon"]

    def rows(self):
        T = lambda *c: [{"cls": x, "name": ""} for x in c]
        return [{"guid": "p", "name": "Pig_anim_RM", "parent": None,
                 "tracks": T("MovieScene3DTransformTrack", "MovieSceneSkeletalAnimationTrack",
                             "MovieSceneControlRigParameterTrack")},
                {"guid": "d", "name": "RedDeer_Calf_anim_IP", "parent": None,
                 "tracks": T("MovieScene3DTransformTrack", "MovieSceneSkeletalAnimationTrack")},
                {"guid": "r", "name": "medhue_raccoon", "parent": None, "tracks": T("MovieSceneSkeletalAnimationTrack")},
                {"guid": "s", "name": "SpotLight3", "parent": None, "tracks": []},
                {"guid": "s1", "name": "LightComponent0", "parent": "s", "tracks": T("MovieSceneFloatTrack")},
                {"guid": "c", "name": "CineCameraActor", "parent": None, "tracks": T("MovieScene3DTransformTrack")}]

    def test_whitelist(self):
        c = P.classify_strip(self.rows(), self.ANIMALS, [{"cls": "MovieSceneAudioTrack"}])
        self.assertEqual(c["refusals"], [])
        self.assertEqual(c["keep"], ["d", "p", "r"])
        self.assertEqual([x["name"] for x in c["remove"]][0], "LightComponent0")          # children first
        self.assertEqual(sorted(x["binding"] for x in c["strip_tracks"]), ["Pig_anim_RM", "RedDeer_Calf_anim_IP"])

    def test_NEG_extra_non_animation_track(self):
        after = [r for r in self.rows() if r["guid"] in "pdr"]
        self.assertTrue(any("NON_ANIMATION_TRACK_LEFT" in r for r in P.verify_strip(after, [], 0, self.ANIMALS)))

    def test_NEG_foreign_binding_root_cut(self):
        after = [dict(r, tracks=[t for t in r["tracks"] if t["cls"] in P.KEEP_TRACK_CLASSES]) for r in self.rows()]
        bad = P.verify_strip(after, [{"cls": "MovieSceneAudioTrack"}], 2, self.ANIMALS)
        for want in ("FOREIGN_BINDINGS_LEFT", "ROOT_TRACKS_LEFT", "CUT_SECTIONS_LEFT"):
            self.assertTrue(any(want in r for r in bad), want)

    def test_clean_strip_passes(self):
        after = [dict(r, tracks=[t for t in r["tracks"] if t["cls"] in P.KEEP_TRACK_CLASSES]) for r in self.rows()
                 if r["guid"] in "pdr"]
        self.assertEqual(P.verify_strip(after, [], 0, self.ANIMALS), [])

    def test_NEG_missing_animal(self):
        c = P.classify_strip([r for r in self.rows() if r["guid"] != "r"], self.ANIMALS, [])
        self.assertTrue(any("ANIMAL_BINDING_COUNT" in r for r in c["refusals"]))


class Gates(unittest.TestCase):
    def args(self, **kw):
        return base_args("APPLY", **kw)

    def test_args_ok(self):
        self.assertEqual(P.validate_args(self.args()), [])

    def test_NEG_write_targets_her_original(self):
        bad = P.validate_args(self.args(dup_path=HERS))
        self.assertTrue(any("DUP_PATH_IS_HERS" in r for r in bad) and any("DUP_PATH_NOT_OURS" in r for r in bad))
        self.assertTrue(any("DUP_PATH_COLLIDES" in r for r in P.validate_args(self.args(dup_path=COPY))))
        a = self.args()
        self.assertTrue(any("WRITE_TARGETS_HER_ASSET" in r for r in P.write_guard(HERS, a)))
        self.assertTrue(any("WRITE_TARGETS_HER_ASSET" in r for r in P.write_guard(L_ANIMALS, a)))
        self.assertTrue(any("WRITE_TARGETS_THE_COPY" in r for r in P.write_guard(COPY, a)))
        self.assertTrue(any("WRITE_TARGETS_A_MAP" in r for r in P.write_guard(WORLD, a)))
        self.assertEqual(P.write_guard(SCENE, a), [])
        self.assertEqual(P.write_guard(DUP, a), [])

    def test_NEG_target_not_scene01_or_master(self):
        self.assertTrue(P.validate_args(self.args(scene_sequence="/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master")))

    def state(self, **kw):
        s = {"mode": "APPLY", "confirm": "APPLY KLARAPREROLLS1", "pie": False, "wrong_world": None,
             "sequencer_open": None, "census": {"content": [], "maps": []}, "decided_by": "x",
             "record_exists": None, "record_applied": False}
        s.update(kw)
        return s

    def test_gates_ok(self):
        self.assertEqual(P.live_gates(self.state()), [])

    def test_NEG_klara_level_dirty(self):
        bad = P.live_gates(self.state(census={"content": [], "maps": [L_ANIMALS]}))
        self.assertTrue(any("KLARA_LEVEL_DIRTY" in r for r in bad))

    def test_NEG_sequencer_open(self):
        self.assertTrue(any("SEQUENCER_OPEN" in r for r in P.live_gates(self.state(sequencer_open=SCENE))))

    def test_NEG_reapply_over_record(self):
        self.assertTrue(any("RECORD_EXISTS" in r for r in P.live_gates(self.state(record_exists="x.json"))))

    def test_NEG_pie_confirm_decided(self):
        self.assertTrue(any("PIE" in r for r in P.live_gates(self.state(pie=True))))
        self.assertTrue(any("CONFIRM" in r for r in P.live_gates(self.state(confirm="APPLY KLARAPREROLL"))))
        self.assertTrue(any("NOT_DECIDED" in r for r in P.live_gates(self.state(decided_by=""))))
        self.assertTrue(any("NO_APPLIED_RECORD" in r for r in
                            P.live_gates(self.state(mode="REVERT", confirm="REVERT KLARAPREROLLS1"))))

    def test_probe_needs_pie(self):
        self.assertTrue(P.live_gates({"mode": "PROBE", "pie": False}))
        self.assertEqual(P.live_gates({"mode": "PROBE", "pie": True}), [])

    def test_census_gate(self):
        self.assertEqual(P.census_gate({"content": [DUP, SCENE], "maps": []}, [SCENE, DUP]), [])
        self.assertTrue(P.census_gate({"content": [DUP, SCENE, COPY], "maps": []}, [SCENE, DUP]))
        self.assertTrue(any("KLARA_LEVEL_DIRTY" in r for r in
                            P.census_gate({"content": [DUP, SCENE], "maps": [L_ANIMALS]}, [SCENE, DUP])))


class RevertCheck(unittest.TestCase):
    REC = {"section": {"range": [282, 594], "offset_ticks": 480}, "before": {"scene_tracks": ["Shots", "Hangar Fold"]}}
    ARGS = {"dup_path": DUP, "track_name": "Klara Preroll - S1"}

    def now(self, **kw):
        s = {"range": [282, 594], "sequence": DUP, "offset": 480}
        s.update(kw)
        return {"ours": [{"sections": [s]}], "others": ["Shots", "Hangar Fold"]}

    def test_ok(self):
        self.assertEqual(P.revert_check(self.REC, self.now(), self.ARGS), [])

    def test_NEG_drift(self):
        for kw in ({"range": [282, 600]}, {"offset": 0}, {"sequence": COPY}):
            self.assertTrue(any("STATE_DRIFTED" in r for r in P.revert_check(self.REC, self.now(**kw), self.ARGS)), kw)
        n = self.now()
        n["ours"].append({"sections": []})
        self.assertTrue(P.revert_check(self.REC, n, self.ARGS))
        n = self.now()
        n["others"].append("Someone Else")
        self.assertTrue(P.revert_check(self.REC, n, self.ARGS))


class ProbeClassify(unittest.TestCase):
    def s(self, w, f, mf, t=0.0, found=True, animal="Pig"):
        return {"window": w, "animal": animal, "scene_frame": f, "master_frame": mf, "found": found,
                "mode": "AnimationCustomMode", "anim_class": None,
                "bones": {"head": {"t": [0.0, 0.0, t], "q": [0.0, 0.0, 0.0, 1.0]}}}

    def test_static(self):
        v = P.classify_probe([self.s(300.0, 300.1, 1), self.s(300.0, 300.5, 2), self.s(300.0, 300.9, 3)], 594)
        self.assertEqual(v["answers"]["Pig"], "STATIC")

    def test_moving(self):
        v = P.classify_probe([self.s(300.0, 300.1, 1, 0.0), self.s(300.0, 300.5, 2, 0.5)], 594)
        self.assertEqual(v["answers"]["Pig"], "MOVING")

    def test_paused_is_unclear(self):
        v = P.classify_probe([self.s(300.0, 300.1, 1), self.s(300.0, 300.1, 1)], 594)
        self.assertEqual(v["answers"]["Pig"], "UNCLEAR")

    def test_post_cut_samples_excluded(self):
        v = P.classify_probe([self.s(593.0, 593.2, 1, 0.0), self.s(593.0, 594.1, 2, 9.0)], 594)
        self.assertEqual(v["answers"]["Pig"], "UNCLEAR")          # only one pre-cut sample left
        v = P.classify_probe([self.s(600.0, 600.1, 1, 0.0), self.s(600.0, 600.5, 2, 9.0)], 594)
        self.assertEqual(v["answers"], {})                         # post-cut window is a reference, not an answer
        self.assertEqual(v["windows"]["600.0|Pig"]["state"], "moving")

    def test_missing_actor(self):
        v = P.classify_probe([self.s(300.0, 300.1, 1, found=False), self.s(300.0, 300.5, 2, found=False)], 594)
        self.assertEqual(v["answers"]["Pig"], "UNCLEAR")


# =====================================================================================================================
# Fake editor
# =====================================================================================================================

class FakeEditor(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="klara_preroll_s1_")
        self.here = build_world(self.root)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def apply(self, **kw):
        return run_tool(base_args("APPLY", **kw))

    def assertNothingSaved(self):
        self.assertEqual(R.saved, [])
        self.assertNotIn(HERS, R.saved)

    def failed(self, want):
        f = markers("KLARAPREROLLS1_FAILED")
        self.assertTrue(f and any(want in x for x in f), "want %s in %s" % (want, f))

    # ---- positive path ----
    def test_dry(self):
        self.assertIsNone(run_tool(base_args("DRY")))
        ok = markers("KLARAPREROLLS1_DRY_OK")
        self.assertEqual(len(ok), 1, R.logs[-5:])
        self.assertIn("apply_ready=1", ok[0])
        self.assertIn("mutated=0", ok[0])
        self.assertEqual(R.saved, [])
        self.assertEqual((R.dirty, R.dirty_maps), (set(), set()))
        rep = P.load_json(os.path.join(self.here, P.DRY_NAME))
        self.assertEqual({r["animal"]: r["loops"] for r in rep["facts"]["plan"]}, {"Pig": 3, "Deer": 3, "Raccoon": 4})
        self.assertTrue(all(r["ok"] for r in rep["api_table"]))

    def test_apply_dry_revert(self):
        before_copy = _copy.deepcopy(R.assets[COPY])
        self.assertIsNone(self.apply(), [m for _l, m in R.logs if "FAILED" in m])
        self.assertEqual(len(markers("KLARAPREROLLS1_APPLY_OK")), 1)
        self.assertEqual(sorted(R.saved), sorted([SCENE, DUP]))                  # exactly the expected packages
        self.assertEqual((R.dirty, R.dirty_maps), (set(), set()))                # 0 + 0
        dup = R.assets[DUP]
        self.assertEqual(sorted(b.name for b in dup.bindings), ["Pig_anim_RM", "RedDeer_Calf_anim_IP", "medhue_raccoon"])
        self.assertEqual({t.get_class().get_name() for b in dup.bindings for t in b.tracks},
                         set(P.KEEP_TRACK_CLASSES))
        self.assertEqual(dup.tracks, [])
        self.assertEqual(dup.pstart, -577)
        starts = {b.name: sorted(s.start for t in b.tracks if isinstance(t, MovieSceneSkeletalAnimationTrack)
                                 for s in t.sections) for b in dup.bindings}
        self.assertEqual(starts["Pig_anim_RM"], [-535200, -144800])              # S8 extended 3 loops, S9 untouched
        self.assertEqual(starts["medhue_raccoon"], [-493600])                    # S16 extended 4 loops
        scene = R.assets[SCENE]
        ours = [t for t in scene.tracks if t.name == "Klara Preroll - S1"]
        self.assertEqual(len(ours), 1)
        s = ours[0].sections[0]
        self.assertEqual([s.get_start_frame(), s.get_end_frame()], [282, 594])
        self.assertEqual(s.parameters.get_editor_property("start_frame_offset").value, 480)
        self.assertEqual(s.completion, "RESTORE_STATE")
        main = scene.tracks[0].sections[0]
        self.assertEqual([main.start, main.end, main.parameters.get_editor_property("start_frame_offset").value],
                         [594 * 960, 5769 * 960, 86400])
        # the copy and her original are never written or changed
        self.assertNotIn(COPY, R.saved)
        self.assertNotIn(HERS, R.saved)
        self.assertEqual([[x.start for t in b.tracks for x in t.sections] for b in R.assets[COPY].bindings],
                         [[x.start for t in b.tracks for x in t.sections] for b in before_copy.bindings])
        rec = P.load_json(os.path.join(self.here, P.RECORD_NAME))
        self.assertTrue(rec["applied"])
        self.assertEqual(len(os.listdir(rec["backup"])), 2)
        # DRY after APPLY: applied, not stale, not apply-ready
        R.logs = []
        self.assertIsNone(run_tool(base_args("DRY")))
        ok = markers("KLARAPREROLLS1_DRY_OK")
        self.assertTrue(ok and "apply_ready=0" in ok[0])
        self.assertFalse([m for m in markers("KLARAPREROLLS1_REFUSAL") if "STALE" in m or "DRIFT" in m])
        # REVERT
        R.logs, R.saved = [], []
        self.assertIsNone(run_tool(base_args("REVERT")), [m for _l, m in R.logs if "FAILED" in m])
        ok = markers("KLARAPREROLLS1_REVERT_OK")
        self.assertEqual(len(ok), 1)
        self.assertIn("dup_left_on_disk=%s" % DUP, ok[0])
        self.assertEqual(R.saved, [SCENE])
        self.assertEqual((R.dirty, R.dirty_maps), (set(), set()))
        self.assertEqual([t.name for t in R.assets[SCENE].tracks], ["Shots", "Hangar Fold", "Camera Cuts"])
        self.assertIn(DUP, R.assets)
        self.assertEqual(EditorAssetLibrary.find_package_referencers_for_asset(DUP), [])
        self.assertFalse(os.path.exists(os.path.join(self.here, P.RECORD_NAME)))

    def test_dry_refuses_dup_left_by_revert(self):
        self.apply()
        run_tool(base_args("REVERT"))
        R.logs = []
        run_tool(base_args("DRY"))
        self.assertTrue(any("DUP_EXISTS" in m for m in markers("KLARAPREROLLS1_REFUSAL")))

    # ---- negative controls: each must FAIL with nothing saved ----
    def test_NEG_klara_level_dirty(self):
        R.dirty_maps.add(L_ANIMALS)
        self.assertIsNotNone(self.apply())
        self.failed("KLARA_LEVEL_DIRTY")
        self.assertNothingSaved()
        self.assertFalse(os.path.exists(os.path.join(self.here, P.RECORD_NAME)))

    def test_NEG_sequencer_open(self):
        R.open_seq = R.assets[SCENE]
        self.assertIsNotNone(self.apply())
        self.failed("SEQUENCER_OPEN")
        self.assertNothingSaved()

    def test_NEG_pie(self):
        R.pie_world = object()
        self.assertIsNotNone(self.apply())
        self.failed("PIE_OR_SIE_ACTIVE")
        self.assertNothingSaved()

    def test_NEG_extra_non_animation_track_copied(self):
        R.sabotage.add("keep_transform")
        self.assertIsNotNone(self.apply())
        self.failed("NON_ANIMATION_TRACK_LEFT")
        self.assertNothingSaved()

    def test_NEG_misaligned_mapping(self):
        R.sabotage.add("psf_off")
        self.assertIsNotNone(self.apply())
        self.failed("SECTION_READBACK")
        self.assertNothingSaved()

    def test_NEG_misaligned_extension(self):
        R.sabotage.add("extend_off_by_frame")
        self.assertIsNotNone(self.apply())
        self.failed("EXTEND_READBACK")
        self.assertNothingSaved()

    def test_NEG_dup_past_cut_args(self):
        self.assertIsNotNone(self.apply(preroll_range=[282, 600]))
        self.failed("DUP_PAST_CUT")
        self.assertNothingSaved()

    def test_NEG_dup_past_cut_live(self):
        R.sabotage.add("range_past_cut")
        self.assertIsNotNone(self.apply())
        self.failed("SECTION_READBACK")
        self.assertNothingSaved()

    def test_NEG_reapply_over_applied_record(self):
        self.assertIsNone(self.apply())
        R.saved, R.logs = [], []
        self.assertIsNotNone(self.apply())
        self.failed("RECORD_EXISTS")
        self.assertNothingSaved()

    def test_NEG_revert_with_drift(self):
        self.assertIsNone(self.apply())
        ours = [t for t in R.assets[SCENE].tracks if t.name == "Klara Preroll - S1"][0]
        ours.sections[0].start += 960                         # someone moved our section
        R.dirty.clear()
        R.saved, R.logs = [], []
        self.assertIsNotNone(run_tool(base_args("REVERT")))
        self.failed("STATE_DRIFTED")
        self.assertNothingSaved()

    def test_NEG_write_targeting_her_original(self):
        self.assertIsNotNone(self.apply(dup_path=HERS))
        self.failed("DUP_PATH_IS_HERS")
        self.assertNothingSaved()
        self.assertEqual(len(R.assets[HERS].tracks), 2)

    def test_NEG_slot_drift(self):
        R.assets[SCENE].tracks[0].sections[0].parameters.set_editor_property("start_frame_offset", FrameNumber(0))
        R.dirty.clear()
        self.assertIsNotNone(self.apply())
        self.failed("SLOT_DRIFT")
        self.assertNothingSaved()

    def test_NEG_census_foreign_dirty_mid_apply(self):
        orig = EditorAssetLibrary.duplicate_asset

        def dup_and_dirty(src, dst):
            R.dirty_maps.add(L_ANIMALS)                       # her level gets dirty during the write
            return orig(src, dst)
        EditorAssetLibrary.duplicate_asset = staticmethod(dup_and_dirty)
        try:
            self.assertIsNotNone(self.apply())
        finally:
            EditorAssetLibrary.duplicate_asset = staticmethod(orig)
        self.failed("KLARA_LEVEL_DIRTY")
        self.assertNothingSaved()


# =====================================================================================================================
# 8 Oct live failures (first live run): tick-exact sections, Scene-gated probe, robust PIE actor match, S1 helper
# =====================================================================================================================

S1_START = 4624705                       # [meas S1PLAY line 07:23:37 start=4624705]
S1_END = S1_START + 6176 * 960           # fake: LS_DevScene_01 length 6176 Scene frames (fixture), exclusive
S3_START, S3_END = 18900000, 19600000    # fake S3 bracket around the live master 18979945 [meas probe file]
LIVE_S3_MASTER = 18979945                # [meas klara_preroll_s1_probe_KLARAPREROLLS1-20261008-032334.json]


class TickExact(unittest.TestCase):
    def test_live_bound_reproduced_and_read_exactly(self):
        sec = f32(-17199 / 24000.0)
        self.assertEqual(sec, -0.7166249752044678)                    # the live log value, bit for bit
        self.assertGreater(abs(-17199 - (-22) * 800), 1)               # why the OLD reader refused (SECTION_OFF_FRAME)
        self.assertEqual(P.section_ticks([(-54, f32(-43200 / 24000.0)), (-22, sec)], 24000.0, 800), (-43200, -17199))

    def test_section_starting_at_minus_17199(self):
        self.assertEqual(P.section_ticks([(-22, f32(-17199 / 24000.0)), (-20, f32(-16000 / 24000.0))], 24000.0, 800),
                         (-17199, -16000))

    def test_NEG_int_getter_disagrees(self):
        with self.assertRaises(P.PlanError) as c:
            P.section_ticks([(-21, f32(-17199 / 24000.0)), (-20, f32(-16000 / 24000.0))], 24000.0, 800)
        self.assertIn("TICK_XCHECK", str(c.exception))

    def test_NEG_seconds_precision(self):
        self.assertEqual(P.ticks_from_seconds(f32(511.0), 24000.0), 511 * 24000)
        with self.assertRaises(P.PlanError) as c:
            P.ticks_from_seconds(f32(600.0), 24000.0)
        self.assertIn("SECONDS_PRECISION", str(c.exception))

    def test_bin_sections_plan(self):
        s = report_secs()
        s["Pig"] = [dict(x, end=x["end"] + 1) for x in s["Pig"]]       # [bin] ends -135199 / -36799
        s["Pig"].append(dict(s["Pig"][0], key="S10", start=-43200, end=-17199))
        p = P.plan_loop_shifts(s, mapping(), 0, {"Pig": 3, "Deer": 3, "Raccoon": 4})
        self.assertEqual(p["refusals"], [])
        self.assertEqual(P.check_alignment(p["rows"], mapping()), [])

    def test_subframe_active_start_allowed(self):
        s = report_secs()
        s["Raccoon"][0]["start"] = -234399                              # one tick off her frame -293
        p = P.plan_loop_shifts(s, mapping(), 0, {"Pig": 3, "Deer": 3, "Raccoon": 4})
        self.assertEqual(p["refusals"], [])
        by = {r["animal"]: r for r in p["rows"]}
        self.assertEqual(by["Raccoon"]["new_range"][0], -234399 - 4 * 64800)
        self.assertFalse(by["Raccoon"]["new_start_on_frame"])
        self.assertEqual(P.check_alignment(p["rows"], mapping()), [])

    def test_NEG_loop_drift(self):
        s = report_secs()
        s["Raccoon"][0]["len_s"] = 64800.04 / 24000.0                   # 0.04 t off a tick (inside CLIP_TICK_TOL)
        p = P.plan_loop_shifts(s, mapping(), 30)                       # 34 loops -> 1.36 ticks accumulated
        self.assertTrue(any("LOOP_DRIFT" in r for r in p["refusals"]), p["refusals"])

    def test_NEG_cut_not_on_her_frame(self):
        m = P.preroll_mapping([282, 594], {"range": [594, 5769], "offset_ticks": 86401}, -310, 24000.0, 30.0, 25.0)
        self.assertTrue(any("CUT_NOT_ON_HER_FRAME" in r for r in m["refusals"]))

    def test_readback_step(self):
        m = mapping()
        self.assertEqual((m["readback_step_scene_frames"], m["readback_step_her_frames"]), (5, 6))

    def test_NEG_misaligned_by_two_ticks(self):
        p = P.plan_loop_shifts(report_secs(), mapping())
        rows = _copy.deepcopy(p["rows"])
        rows[0]["new_range"][0] -= 2                                    # was tolerated (< one her frame) before
        self.assertTrue(any("MISALIGNED_AT_CUT" in r for r in P.check_alignment(rows, mapping())))


class FakeEditorBin(unittest.TestCase):
    """The fake editor over the [bin] section table, incl. Pig Section_10's end at -17199 ticks."""
    SPEC = BIN_SPEC

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="klara_preroll_s1_bin_")
        self.here = build_world(self.root, _copy.deepcopy(self.SPEC))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def failed(self, want):
        f = markers("KLARAPREROLLS1_FAILED")
        self.assertTrue(f and any(want in x for x in f), "want %s in %s" % (want, f))

    def test_dry_live_failure_now_passes(self):
        self.assertIsNone(run_tool(base_args("DRY")), [m for _l, m in R.logs if "FAILED" in m])
        ok = markers("KLARAPREROLLS1_DRY_OK")
        self.assertTrue(ok and "apply_ready=1" in ok[0], R.logs[-6:])
        rep = P.load_json(os.path.join(self.here, P.DRY_NAME))
        self.assertEqual({r["animal"]: r["loops"] for r in rep["facts"]["plan"]}, {"Pig": 3, "Deer": 3, "Raccoon": 4})
        self.assertIn([-43200, -17199], [[s["start"], s["end"]] for s in rep["facts"]["skel_sections"]["Pig"]])

    def test_apply_keeps_offframe_sections_exact(self):
        self.assertIsNone(run_tool(base_args("APPLY")), [m for _l, m in R.logs if "FAILED" in m])
        self.assertEqual(len(markers("KLARAPREROLLS1_APPLY_OK")), 1)
        pig = [b for b in R.assets[DUP].bindings if b.name == "Pig_anim_RM"][0]
        rng = sorted([s.start, s.end] for t in pig.tracks if isinstance(t, MovieSceneSkeletalAnimationTrack)
                     for s in t.sections)
        self.assertEqual(rng[0], [-535200, -135199])                   # S8 extended 3 loops, end kept
        self.assertIn([-43200, -17199], rng)                           # S10 untouched, sub-frame end exact

    def test_NEG_slot_off_frame(self):
        R.assets[SCENE].tracks[0].sections[0].start += 1                # one tick: int getter still says 594
        R.dirty.clear()
        self.assertIsNotNone(run_tool(base_args("APPLY")))
        self.failed("SLOT_OFF_FRAME")
        self.assertEqual(R.saved, [])

    def test_NEG_copy_playback_start_off_frame(self):
        R.sabotage.add("pstart_off")
        self.assertIsNotNone(run_tool(base_args("APPLY")))
        self.failed("COPY_PLAYBACK_START_OFF_FRAME")
        self.assertEqual(R.saved, [])


class FakeEditorSubframe(FakeEditorBin):
    """The ACTIVE section starts between frames: the extension must go through the seconds setter, exact in ticks."""
    SPEC = dict(BIN_SPEC, medhue_raccoon=[(-234399, 347200, "Raccoon_Eating", 0)])

    def test_apply_subframe_extension(self):
        self.assertIsNone(run_tool(base_args("APPLY")), [m for _l, m in R.logs if "FAILED" in m])
        rac = [b for b in R.assets[DUP].bindings if b.name == "medhue_raccoon"][0]
        starts = [s.start for t in rac.tracks if isinstance(t, MovieSceneSkeletalAnimationTrack) for s in t.sections]
        self.assertEqual(starts, [-234399 - 4 * 64800])

    def test_NEG_seconds_setter_floors(self):
        R.sabotage.add("seconds_setter_floors")
        self.assertIsNotNone(run_tool(base_args("APPLY")))
        self.failed("EXTEND_READBACK")
        self.assertEqual(R.saved, [])


# ---- PIE fakes ------------------------------------------------------------------------------------------------------

class _Named:
    def __init__(self, path):
        self.p = path

    def get_path_name(self):
        return self.p

    def get_name(self):
        return self.p.split(".")[-1].rsplit("/", 1)[-1]


class PieLevel:
    """A level of the PIE world: package /Game/.../UEDPIE_0_<map>, world object named <map> (or prefixed too)."""
    def __init__(self, pkg, world_name=None):
        self.pkg = _Named(pkg)
        short = pkg.rsplit("/", 1)[-1]
        self.world = _Named("%s.%s" % (pkg, world_name or short.split("UEDPIE_0_")[-1]))

    def get_outer(self):
        return self.world

    def get_outermost(self):
        return self.pkg


class SkeletalMeshComponent:
    def __init__(self, actor):
        self.actor = actor

    def get_skinned_asset(self):
        return _Named("/Game/KK_S1_Animals/X/%s.%s" % (self.actor.mesh, self.actor.mesh))

    def get_anim_instance(self):
        return None

    def get_num_bones(self):
        return 3

    def get_bone_name(self, i):
        return ["root", "pelvis", "head"][i]

    def get_animation_mode(self):
        return types.SimpleNamespace(name="ANIMATION_CUSTOM_MODE")

    def get_socket_transform(self, bn, space):
        z = float(R.transport.frame) * 1e-4 * self.actor.speed
        return types.SimpleNamespace(translation=Vec(0.0, 0.0, z), rotation=types.SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0))


class SkeletalMeshActor(Obj):
    def __init__(self, label, name, level, mesh="", speed=1.0):
        self.label, self.name, self.level, self.mesh, self.speed = label, name, level, mesh, speed

    def get_actor_label(self):
        return self.label

    def get_name(self):
        return self.name

    def get_path_name(self):
        return "%s:PersistentLevel.%s" % (self.level.world.get_path_name(), self.name)

    def get_level(self):
        return self.level

    def get_actor_location(self):
        return Vec(1.0, 2.0, 3.0)

    def get_component_by_class(self, cls):
        return SkeletalMeshComponent(self)


class _Seg:
    def __init__(self, label, typ, a, b):
        self.label, self.type, self.start_frame, self.end_frame = label, typ, FrameNumber(a), FrameNumber(b)


class Transport:
    """Models ScrubToMasterFrame's refusals [project source InfinityStageTransportController.cpp:1672-1690,
    2580-2590]: NoSegment, NotReady, then UnsafeExternalClock when performance mode is on, the CURRENT segment is
    DeclaredUnpausable and the target differs."""
    def __init__(self, frame):
        self.frame, self.pm, self.playing = frame, True, True
        self.segments = [_Seg("Passage 1", "PASSAGE", 0, S1_START), _Seg("Scene 1", "SCENE", S1_START, S1_END),
                         _Seg("Scene 3", "SCENE", S3_START, S3_END)]
        self.unpausable = {"Scene 3"}

    def _seg(self, f):
        return next((s for s in self.segments if s.start_frame.value <= f < s.end_frame.value), None)

    def get_editor_property(self, k):
        assert k == "performance_mode", k
        return self.pm

    def set_editor_property(self, k, v):
        assert k == "performance_mode", k
        if "pm_stuck_false" in R.sabotage and v:
            return
        self.pm = bool(v)

    def get_current_master_frame(self):
        return FrameNumber(self.frame)

    def is_transport_playing(self):
        return self.playing

    def scrub_to_master_frame(self, fn):
        tgt = self._seg(fn.value)
        if tgt is None:
            return InfinityTransportResult.NO_SEGMENT
        if "scrub_not_ready" in R.sabotage:
            return InfinityTransportResult.NOT_READY
        cur = self._seg(self.frame)
        if self.pm and cur is not None and cur.label in self.unpausable and fn.value != self.frame:
            return InfinityTransportResult.UNSAFE_EXTERNAL_CLOCK
        self.playing = False
        if "scrub_noop" not in R.sabotage:
            self.frame = fn.value
        return InfinityTransportResult.SUCCEEDED


class _Player:
    def play(self):
        if "play_noop" not in R.sabotage:
            R.transport.playing = True

    def pause(self):
        R.transport.playing = False


class InfinityStageShowRoot(Obj):
    def __init__(self):
        self.transport = R.transport
        self.sequence_player = _Player()


InfinityTransportResult = types.SimpleNamespace(SUCCEEDED="SUCCEEDED", NO_PLAYER="NO_PLAYER", NO_SEGMENT="NO_SEGMENT",
                                                NOT_READY="NOT_READY", UNSAFE_EXTERNAL_CLOCK="UNSAFE_EXTERNAL_CLOCK")


class PieWorld:
    def __init__(self, actors, levels):
        self.actors, self.levels = actors, levels


def _install_pie_fake():
    u = sys.modules["unreal"]
    u.SkeletalMeshActor, u.SkeletalMeshComponent, u.InfinityStageShowRoot = (SkeletalMeshActor, SkeletalMeshComponent,
                                                                           InfinityStageShowRoot)
    u.InfinityTransportResult = InfinityTransportResult
    u.InfinityCueType = types.SimpleNamespace(SCENE="SCENE", PASSAGE="PASSAGE")
    u.RelativeTransformSpace = types.SimpleNamespace(RTS_COMPONENT="RTS_COMPONENT")
    u.GameplayStatics = types.SimpleNamespace(get_all_actors_of_class=lambda w, cls: [
        a for a in (list(w.actors) + [InfinityStageShowRoot()]) if isinstance(a, cls)])

    def reg(fn):
        R.tick_cb = fn
        return "handle"

    def unreg(h):
        R.tick_cb = None
    u.register_slate_post_tick_callback, u.unregister_slate_post_tick_callback = reg, unreg


_install_pie_fake()
import s1_play_from_start as S  # noqa: E402  (the fake carries _PUSS_FAKE: importing runs nothing)

HER_PIE = "/Game/KK_S1_Animals/UEDPIE_0_L_Animals"
PERSIST_PIE = "/Game/InfinityStage/Dev/Maps/UEDPIE_0_L_InfinityStage_V1VerticalSlice"


def build_pie(root, animals=None, extra=()):
    """A PIE world: her level STREAMED (UEDPIE_0_ package), the persistent level, decoys with her labels/names."""
    _reset(root)
    R.transport = Transport(LIVE_S3_MASTER)
    R.tick_cb = None
    her, pers = PieLevel(HER_PIE), PieLevel(PERSIST_PIE)
    acts = [SkeletalMeshActor(lab, nm, her, mesh) for lab, nm, mesh in (animals or (
        ("Pig_anim_RM", "SkeletalMeshActor_13", "Pig_anim_RM"),
        ("RedDeer_Calf_anim_IP", "SkeletalMeshActor_15", "RedDeer_Calf_anim_IP"),
        ("medhue_raccoon", "SkeletalMeshActor_7", "medhue_raccoon")))]
    acts += [SkeletalMeshActor("Pig_anim_RM", "SkeletalMeshActor_99", pers),          # decoy label, wrong level
             SkeletalMeshActor("Somebody", "SkeletalMeshActor_15", pers)]             # decoy name, wrong level
    acts += list(extra)
    R.pie_world = PieWorld(acts, [pers, her])
    here = os.path.join(root, "Saved", "CodexConductor", P.FOLDER)
    os.makedirs(here, exist_ok=True)
    return here, her, pers


def drive(ticks):
    for f in ticks:
        R.transport.frame = int(f)
        if R.tick_cb is None:
            return
        R.tick_cb(0.025)


def s1_ticks(f0, f1, step=0.625):
    """Master ticks for Scene-1 frames f0..f1 at 25 fps, ~40 Hz editor ticks (0.625 Scene frames per tick)."""
    out, f = [], float(f0)
    while f <= f1:
        out.append(S1_START + int(round(f * 960)))
        f += step
    return out


class ProbeGate(unittest.TestCase):
    W = [300.0, 592.0, 600.0]

    def gate(self, mf, sf, filled=None):
        return P.probe_gate(mf, S1_START, S1_END, sf, self.W, filled or {}, 3, 594)

    def test_live_samples_rejected(self):
        # the 8 Oct live sample: master 18979945, 'scene frame' 14953.375 -> every window fired before; now NOT_IN_SCENE
        self.assertEqual(self.gate(LIVE_S3_MASTER, 14953.375), (None, "NOT_IN_SCENE"))

    def test_windows(self):
        self.assertEqual(self.gate(S1_START + 288000, 300.0), (300.0, None))
        self.assertEqual(self.gate(S1_START + 289900, 301.98), (300.0, None))
        self.assertEqual(self.gate(S1_START + 289920, 302.0), (None, "NO_WINDOW"))
        self.assertEqual(self.gate(S1_START + 569000, 593.9), (592.0, None))
        self.assertEqual(self.gate(S1_START + 570240, 594.0), (None, "NO_WINDOW"))     # pre-cut window clipped at cut
        self.assertEqual(self.gate(S1_START + 576480, 600.5), (600.0, None))
        self.assertEqual(self.gate(S1_START + 288000, 300.0, {300.0: 3}), (None, "NO_WINDOW"))   # window full

    def test_NEG_segment_end_exclusive(self):
        self.assertEqual(self.gate(S1_END, 300.5), (None, "NOT_IN_SCENE"))
        self.assertEqual(self.gate(S1_START - 1, 300.5), (None, "NOT_IN_SCENE"))


class MatchActor(unittest.TestCase):
    def c(self, i, label, name, pkg):
        return {"idx": i, "label": label, "name": name, "level_pkg": pkg}

    def test_label_in_pie_streamed_level(self):
        cands = [self.c(0, "Pig_anim_RM", "SkeletalMeshActor_99", PERSIST_PIE),
                 self.c(1, "Pig_anim_RM", "SkeletalMeshActor_13", HER_PIE)]
        v = P.match_actor(cands, "Pig_anim_RM", "SkeletalMeshActor_13", L_ANIMALS)
        self.assertEqual((v["found"], v["idx"], v["matched_by"], v["level_match"]), (True, 1, "label", "path"))

    def test_name_fallback_and_short_level(self):
        cands = [self.c(0, "Pig (renamed)", "SkeletalMeshActor_13", "/Temp/UEDPIE_0_L_Animals")]
        v = P.match_actor(cands, "Pig_anim_RM", "SkeletalMeshActor_13", L_ANIMALS)
        self.assertEqual((v["found"], v["matched_by"], v["level_match"]), (True, "name", "short"))

    def test_NEG_only_outside_her_level(self):
        cands = [self.c(0, "Pig_anim_RM", "SkeletalMeshActor_13", PERSIST_PIE)]
        v = P.match_actor(cands, "Pig_anim_RM", "SkeletalMeshActor_13", L_ANIMALS)
        self.assertFalse(v["found"])
        self.assertIn("L_InfinityStage_V1VerticalSlice", v["why"])

    def test_NEG_ambiguous_label(self):
        cands = [self.c(0, "Pig_anim_RM", "A", HER_PIE), self.c(1, "Pig_anim_RM", "B", HER_PIE)]
        self.assertFalse(P.match_actor(cands, "Pig_anim_RM", "SkeletalMeshActor_13", L_ANIMALS)["found"])
        v = P.match_actor(cands, "Pig_anim_RM", "B", L_ANIMALS)
        self.assertEqual((v["found"], v["matched_by"]), (True, "label+name"))

    def test_normalize(self):
        self.assertEqual(P.normalize_pkg(HER_PIE + ".L_Animals"), L_ANIMALS)
        self.assertEqual(P.normalize_pkg("/Game/X/UEDPIE_12_Map.Map:PersistentLevel"), "/Game/X/Map")


class ProbePIE(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="klara_preroll_s1_pie_")
        self.here, self.her, self.pers = build_pie(self.root)

    def tearDown(self):
        R.pie_world = None
        shutil.rmtree(self.root, ignore_errors=True)

    def probe(self, **kw):
        a = base_args("PROBE")
        a["probe"] = dict(a["probe"], **kw)
        self.assertIsNone(run_tool(a), R.logs[-3:])
        self.assertTrue(markers("KLARAPREROLLS1_PROBE_ARMED"))
        return P.load_json

    def result(self):
        return P.load_json(os.path.join(self.here, "klara_preroll_s1_probe_TEST-PROBE.json"))

    def test_live_failure_transport_in_scene3_waits(self):
        self.probe(not_in_scene_log_s=0)
        drive([LIVE_S3_MASTER + 600 * k for k in range(12)])           # the live run's situation
        self.assertIsNotNone(R.tick_cb)                                 # still armed, nothing sampled
        self.assertEqual(markers("KLARAPREROLLS1_PROBE_SAMPLE"), [])
        self.assertTrue(markers("KLARAPREROLLS1_PROBE_NOT_IN_SCENE"))
        R.pie_world = None
        drive([LIVE_S3_MASTER])
        self.assertTrue(any("PROBE_PIE_ENDED" in m for m in markers("KLARAPREROLLS1_FAILED")))
        v = self.result()["verdict"]
        self.assertEqual(v["answers"], {"Deer": "UNCLEAR", "Pig": "UNCLEAR", "Raccoon": "UNCLEAR"})
        self.assertEqual(v["windows"]["300.0|Pig"]["samples"], 0)

    def test_scene1_label_match_in_streamed_pie_level(self):
        self.probe()
        drive([LIVE_S3_MASTER] * 3 + s1_ticks(290, 605))
        ok = markers("KLARAPREROLLS1_PROBE_OK")
        self.assertEqual(len(ok), 1, [m for _l, m in R.logs if "FAILED" in m or "ERROR" in m])
        res = self.result()
        for s in res["samples"]:
            self.assertTrue(s["in_scene"])
            self.assertTrue(s["window"] <= s["scene_frame"] < s["window"] + 2, s)
            if s["window"] < 594:
                self.assertLess(s["scene_frame"], 594)
            self.assertTrue(s["found"])
            self.assertEqual(s["match"]["matched_by"], "label")
        self.assertEqual(len(res["samples"]), 3 * 3 * 3)
        self.assertEqual(len(markers("KLARAPREROLLS1_PROBE_CANDIDATE")), 5)          # every candidate, once
        self.assertEqual(res["verdict"]["answer"], "MOVING")
        self.assertIn(HER_PIE, res["levels"])

    def test_scrub_back_fills_earlier_window(self):
        self.probe()
        drive(s1_ticks(400, 405) + s1_ticks(299, 303) + s1_ticks(590, 602))
        self.assertEqual(len(markers("KLARAPREROLLS1_PROBE_OK")), 1)

    def test_NEG_actor_missing_and_candidates_logged(self):
        R.pie_world.actors = [a for a in R.pie_world.actors if a.label != "medhue_raccoon"]
        self.probe()
        drive(s1_ticks(299, 603))
        res = self.result()
        self.assertEqual(res["verdict"]["answers"]["Raccoon"], "UNCLEAR")
        self.assertTrue(any("Raccoon" in m for m in markers("KLARAPREROLLS1_PROBE_ACTOR_MISSING")))
        self.assertEqual(len(res["candidates"]), 4)

    def test_NEG_only_decoys(self):
        R.pie_world.actors = [a for a in R.pie_world.actors if a.level is self.pers]
        self.probe()
        drive(s1_ticks(299, 603))
        self.assertFalse(any(s["found"] for s in self.result()["samples"]))


class S1Play(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="s1play_")
        self.here, _h, _p = build_pie(self.root)
        self._orig_here = S._here
        S._here = lambda: self.here

    def tearDown(self):
        S._here = self._orig_here
        R.pie_world = None
        shutil.rmtree(self.root, ignore_errors=True)

    def state(self):
        return P.load_json(os.path.join(self.here, S.STATE_NAME))

    def test_live_failure_reproduced_by_the_fake(self):
        # the 07:23:37 call: performance mode on, current segment Scene 3 (external clock) -> UNSAFE_EXTERNAL_CLOCK
        self.assertEqual(R.transport.scrub_to_master_frame(FrameNumber(S1_START)), "UNSAFE_EXTERNAL_CLOCK")
        self.assertEqual(R.transport.frame, LIVE_S3_MASTER)

    def test_ok_from_scene3(self):
        self.assertTrue(S.main())
        ok = markers("S1PLAY_OK")
        self.assertEqual(len(ok), 1, R.logs)
        self.assertIn("scrub=SUCCEEDED", ok[0])
        self.assertEqual(R.transport.frame, S1_START)
        self.assertTrue(R.transport.playing)
        self.assertTrue(R.transport.pm)                                  # restored
        st = self.state()
        self.assertEqual((st["performance_mode_before"], st["restored"], st["master_before"]),
                         (True, True, LIVE_S3_MASTER))

    def neg(self, sab, want):
        R.sabotage.add(sab)
        self.assertFalse(S.main())
        f = markers("S1PLAY_FAILED")
        self.assertTrue(f and want in f[0], f)
        self.assertEqual(markers("S1PLAY_OK"), [])
        return f

    def test_NEG_scrub_refused(self):
        self.neg("scrub_not_ready", "SCRUB_NOT_READY")
        self.assertTrue(R.transport.pm)
        self.assertEqual(R.transport.frame, LIVE_S3_MASTER)

    def test_NEG_frame_readback(self):
        self.neg("scrub_noop", "FRAME_READBACK")
        self.assertTrue(R.transport.pm)

    def test_NEG_not_playing(self):
        self.neg("play_noop", "NOT_PLAYING")

    def test_NEG_restore_fails(self):
        self.neg("pm_stuck_false", "PERFORMANCE_MODE_RESTORE")
        self.assertFalse(self.state()["restored"])

    def test_unrestored_state_is_reused_not_overwritten(self):
        P.write_json(os.path.join(self.here, S.STATE_NAME), {"run": "old", "performance_mode_before": True,
                                                              "restored": False})
        R.transport.pm = False                                           # an earlier run left it off
        self.assertTrue(S.main())
        self.assertTrue(R.transport.pm)
        self.assertTrue(markers("S1PLAY_REUSED_STATE"))

    def test_NEG_no_pie(self):
        R.pie_world = None
        self.assertFalse(S.main())
        self.assertTrue(any("NO_PIE" in m for m in markers("S1PLAY_FAILED")))


class Hygiene(unittest.TestCase):
    def test_no_unreal_calls_at_module_level(self):
        tree = ast.parse(open(os.path.join(HERE, "klara_preroll_s1.py"), encoding="utf-8").read())
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)):
                continue
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                continue
            if isinstance(node, ast.Try) or isinstance(node, ast.If):
                continue                                       # the import guard and the main() guard
            src = ast.unparse(node)
            self.assertNotIn("unreal.", src, src)

    def test_request(self):
        r = P.load_json(os.path.join(HERE, "klara_preroll_s1_request.json"))
        self.assertEqual(r["arguments"]["tool_name"], "ExecuteProjectPythonFile")
        self.assertEqual(r["arguments"]["arguments"]["relativeSavedPath"],
                         "CodexConductor/KlaraPrerollS1_20261008/klara_preroll_s1.py")

    def test_helper_no_unreal_at_module_level_and_request(self):
        tree = ast.parse(open(os.path.join(HERE, "s1_play_from_start.py"), encoding="utf-8").read())
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom, ast.Try, ast.If)):
                continue
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                continue
            self.assertNotIn("unreal.", ast.unparse(node))
        r = P.load_json(os.path.join(HERE, "s1_play_from_start_request.json"))
        self.assertEqual(r["arguments"]["arguments"]["relativeSavedPath"],
                         "CodexConductor/KlaraPrerollS1_20261008/s1_play_from_start.py")

    def test_args_file_is_dry(self):
        a = P.load_json(os.path.join(HERE, "klara_preroll_s1_args.json"))
        self.assertEqual((a["mode"], a["confirm"], a["decided_by"]), ("DRY", "", ""))
        self.assertEqual(P.validate_args(a), [])


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    res = unittest.TextTestRunner(verbosity=1).run(suite)
    n = res.testsRun
    bad = len(res.failures) + len(res.errors)
    print("HARNESS %d/%d passed" % (n - bad, n))
    sys.exit(1 if bad else 0)
