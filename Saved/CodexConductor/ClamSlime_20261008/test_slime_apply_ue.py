"""OFFLINE harness for slime_apply_ue.py (no Unreal).  Pure checks + a FAKE editor (actors, LS_DevScene_03 bindings,
census, assets, AnimationLibrary) running DRY / APPLY / REVERT, with negative controls that must FAIL with their
named reason.  Run:  python test_slime_apply_ue.py   -> CLAMSLIME_HARNESS|pass=n|fail=m|total=t

The fake's live lid keys are the REAL read-back keys of the applied opening (ClamOpen_20261008/clam_open_record.json
after_roll, CLAMOPEN-20261008-032251) and the fake anim's lid curve is the REAL design curve (build/slime_design.json),
mirrored to UE as Roll = -deg (the [inf] the tool gates).  Records, backups and the dry output go to a temp folder.
When gitignored build fixtures are absent from the worktree, set CLAMSLIME_FIXTURE_DIR to the read-only live folder.
"""
import copy
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/") + "/"
FIXTURES = os.environ.get("CLAMSLIME_FIXTURE_DIR", HERE).replace("\\", "/").rstrip("/") + "/"
RESULTS = []
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
LVL = WORLD + ".L_InfinityStage_V1VerticalSlice:PersistentLevel."


def check(name, cond, info=""):
    RESULTS.append((name, bool(cond)))
    print("%s %s %s" % ("PASS" if cond else "FAIL", name, "" if cond else info))


def load_tool():
    spec = importlib.util.spec_from_file_location("slime_apply_offline", HERE + "slime_apply_ue.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


T = load_tool()
DESIGN = json.load(open(FIXTURES + "build/slime_design.json", encoding="utf-8"))
CLAMOPEN = json.load(open(FIXTURES + "../ClamOpen_20261008/clam_open_record.json", encoding="utf-8"))


# =====================================================================================================================
# Fake unreal
# =====================================================================================================================
class En:
    def __init__(self, name):
        self.name = name


class V:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = float(x), float(y), float(z)


class Rot:
    def __init__(self, roll=0.0, pitch=0.0, yaw=0.0):
        self.roll, self.pitch, self.yaw = float(roll), float(pitch), float(yaw)

    def rotator(self):
        return self


class FrameNumber:
    def __init__(self, v):
        self.value = int(v)


class Guid:
    n = 0

    def __init__(self):
        Guid.n += 1
        self.s = "%032X" % (0xABC0000 + Guid.n)


class Cls:
    def __init__(self, name):
        self.n = name

    def get_name(self):
        return self.n


class Asset:
    def __init__(self, path, kind, **kw):
        self.path, self.kind = path, kind
        self.props = kw

    def get_path_name(self):
        return self.path + "." + self.path.rsplit("/", 1)[1]

    def get_editor_property(self, k):
        return self.props.get(k)

    def set_editor_property(self, k, v):
        self.props[k] = v

    def modify(self):
        E.dirty_content.add(self.path)

    def get_play_length(self):
        return self.props["length"]

    def get_imported_bounds(self):
        return Asset("bounds", "bounds", origin=self.props["origin"], box_extent=self.props["extent"])


class FakeSkeletalMesh(Asset):
    pass


class SkelMat:
    def __init__(self, slot, mi):
        self.p = {"material_slot_name": slot, "material_interface": mi}

    def get_editor_property(self, k):
        return self.p[k]

    def set_editor_property(self, k, v):
        self.p[k] = v


class Comp:
    def __init__(self, owner, kind):
        self.owner, self.kind = owner, kind
        self.p = {"relative_location": V(0, 0, 0), "relative_rotation": Rot(), "relative_scale3d": V(1, 1, 1),
                  "mobility": En("STATIC"), "skeletal_mesh_asset": None}
        self.mats = []

    def get_editor_property(self, k):
        return self.p[k]

    def set_editor_property(self, k, v):
        if k == "skeletal_mesh_asset" and E.mesh_setter_lies:
            return
        self.p[k] = v
        E.touch_map()

    def set_mobility(self, m):
        self.p["mobility"] = m

    def set_skeletal_mesh_asset(self, m):
        self.p["skeletal_mesh_asset"] = m

    def get_skeletal_mesh_asset(self):
        return self.p["skeletal_mesh_asset"]

    def get_material_index(self, slot):
        mesh = self.p["skeletal_mesh_asset"]
        names = [m.get_editor_property("material_slot_name") for m in mesh.get_editor_property("materials")]
        return names.index(slot)

    def get_material(self, i):
        if self.kind == "static":
            return self.mats[i]
        return self.p["skeletal_mesh_asset"].get_editor_property("materials")[i].get_editor_property("material_interface")

    def get_num_materials(self):
        return len(self.mats)

    def is_visible(self):
        return True


class Actor:
    def __init__(self, label, name, loc=(0, 0, 0), yaw=0.0, kind="static"):
        self.label, self.name = label, name
        self.loc, self.yaw = V(*loc), yaw
        self.hidden, self.tags, self.folder, self.parent = True, [], "RigAtmos/S3Props", None
        self.root = Comp(self, kind)
        self.smc = self.root
        self.kind = kind

    def get_actor_label(self):
        return self.label

    def set_actor_label(self, v):
        self.label = v
        E.touch_map()

    def get_path_name(self):
        return LVL + self.name

    def get_name(self):
        return self.name

    def get_editor_property(self, k):
        return {"hidden": self.hidden, "tags": self.tags, "root_component": self.root,
                "skeletal_mesh_component": self.smc}[k]

    def set_editor_property(self, k, v):
        setattr(self, {"tags": "tags"}[k], [str(x) for x in v])
        E.touch_map()

    def set_folder_path(self, f):
        self.folder = f

    def get_folder_path(self):
        return self.folder

    def set_actor_hidden_in_game(self, h):
        self.hidden = bool(h)
        E.touch_map()

    def attach_to_actor(self, parent, socket, a, b, c, weld):
        self.parent = parent
        E.touch_map()
        if E.attach_offset:
            self.root.p["relative_location"] = V(0, 0, 0.5)

    def get_attach_parent_actor(self):
        return self.parent

    def get_actor_location(self):
        return self.loc

    def get_actor_rotation(self):
        return Rot(0, 0, self.yaw)

    def get_actor_scale3d(self):
        return V(1, 1, 1)

    def get_components_by_class(self, cls):
        return [self.root] if self.kind == "static" else []


class Key:
    def __init__(self, frame, value, interp="RCIM_LINEAR"):
        self.f, self.v, self.i = frame, value, interp

    def get_time(self, time_unit=None):
        return types.SimpleNamespace(frame_number=FrameNumber(self.f), sub_frame=0.0)

    def get_value(self):
        return self.v

    def get_interpolation_mode(self):
        return En(self.i)

    def get_tangent_mode(self):
        return En("RCTM_AUTO")


class Channel:
    def __init__(self, name, keys=()):
        self.name, self.keys = name, list(keys)

    def get_name(self):
        return self.name

    def get_keys(self):
        return list(self.keys)

    def add_key(self, fn, value, time_unit=None, interpolation=None):
        E.touch_scene()
        k = Key(fn.value, value)
        self.keys.append(k)
        return k


class Params:
    def __init__(self):
        self.p = {"animation": None, "start_frame_offset": FrameNumber(0), "end_frame_offset": FrameNumber(0),
                  "first_loop_start_frame_offset": FrameNumber(0),
                  "play_rate": types.SimpleNamespace(to_fixed_play_rate=lambda: 1.0), "reverse": False}

    def get_editor_property(self, k):
        return self.p[k]

    def set_editor_property(self, k, v):
        if k == "animation" and E.params_setter_lies:
            return
        self.p[k] = v


class Section:
    def __init__(self, cls, rng=(None, None), channels=None):
        self.cls, self.rng = cls, list(rng)
        self.channels = channels if channels is not None else ([Channel("Visibility")] if cls == "MovieSceneVisibilityTrack" else [])
        self.params = Params()

    def has_start_frame(self):
        return self.rng[0] is not None

    def has_end_frame(self):
        return self.rng[1] is not None

    def get_start_frame(self):
        return self.rng[0]

    def get_end_frame(self):
        return self.rng[1]

    def set_range(self, a, b):
        E.touch_scene()
        self.rng = [int(a), int(b)]

    def get_all_channels(self):
        return list(self.channels)

    def get_editor_property(self, k):
        assert k == "params"
        return self.params

    def set_editor_property(self, k, v):
        assert k == "params"
        E.touch_scene()
        self.params = v


class Track:
    def __init__(self, cls, sections=None):
        self.cls, self.sections = cls, sections or []
        self.prop = ("", "")

    def get_class(self):
        return Cls(self.cls)

    def get_sections(self):
        return list(self.sections)

    def add_section(self):
        E.touch_scene()
        s = Section(self.cls)
        self.sections.append(s)
        return s

    def get_property_name(self):
        return self.prop[0]

    def get_property_path(self):
        return self.prop[1]

    def set_property_name_and_path(self, n, p):
        self.prop = (n, p)

    def set_display_name(self, n):
        pass


class Binding:
    def __init__(self, seq, name, actor_path, tracks=None):
        self.seq, self.name, self.actor_path, self.tracks = seq, name, actor_path, tracks or []
        self.guid = Guid()
        self.alive = True

    def get_display_name(self):
        return self.name

    def set_display_name(self, n):
        self.name = n

    def get_id(self):
        return self.guid

    def get_tracks(self):
        return list(self.tracks)

    def add_track(self, cls):
        E.touch_scene()
        t = Track(cls.n)
        self.tracks.append(t)
        return t

    def is_valid(self):
        return self.alive

    def remove(self):
        E.touch_scene()
        self.seq.bindings.remove(self)
        self.alive = False


class Sequence:
    def __init__(self):
        self.bindings = []
        self.end = 6240

    def get_display_rate(self):
        return types.SimpleNamespace(numerator=24, denominator=1)

    def get_playback_end(self):
        return self.end

    def get_bindings(self):
        return list(self.bindings)

    def locate_bound_objects(self, b, world):
        return [a for a in E.actors if a.get_path_name() == b.actor_path]

    def add_possessable(self, actor):
        E.touch_scene()
        b = Binding(self, actor.label, actor.get_path_name())
        self.bindings.append(b)
        if E.side_effect:
            E.side_effect()
        return b

    def modify(self):
        E.touch_scene()


class Env:
    pass


E = Env()


def reset(**kw):
    E.dirty_content, E.dirty_maps = set(), set()
    E.mesh_setter_lies = E.params_setter_lies = E.attach_offset = False
    E.side_effect = None
    E.pie = False
    E.sequencer_open = False
    E.anim_offset_at = None
    E.anim_sign = 1.0
    E.saved = []
    root = Actor("S3 PearlClam", "StaticMeshActor_8", (14424.39, 159997.12, 121.97), 42.69)
    lid = Actor("S3 PearlClam Lid", "StaticMeshActor_511")
    lid.parent = root
    twin = Actor("S3 PearlClam Pearl Fade", "StaticMeshActor_900")
    twin.parent = root
    twin.root.mats = [Asset("/Game/X/MI_PearlClam_Pearl_Fade", "mi")]
    E.actors = [root, lid, twin]
    E.root, E.lid, E.twin = root, lid, twin
    E.seq = Sequence()
    chans = []
    for base, row in CLAMOPEN["channels"].items():
        keys = CLAMOPEN["after_roll"]["keys"] if base == "Rotation.X" else row["keys"]
        chans.append(Channel(row["name"], [Key(k["frame"], k["value"], k["interp"]) for k in keys]))
    xs = Track("MovieScene3DTransformTrack", [Section("MovieScene3DTransformTrack", (None, None), chans)])
    vs = Track("MovieSceneVisibilityTrack", [Section("MovieSceneVisibilityTrack", (744, 6240))])
    if kw.get("lid_binding", True):
        E.seq.bindings.append(Binding(E.seq, "S3 Hangar Float Hold: S3 PearlClam Lid", lid.get_path_name(), [xs, vs]))
    mats = [SkelMat("M_PearlClam_Ligament", Asset(T.MI_LIG, "mi")), SkelMat("M_PearlClam_Slime", Asset(T.MI_SLIME, "mi"))]
    E.assets = {T.MESH: FakeSkeletalMesh(T.MESH, "skm", materials=mats), T.ANIM: Asset(T.ANIM, "anim", length=4794 / 24.0),
                SCENE: E.seq}
    for p in (T.SKELETON, T.M_SLIME, T.MI_SLIME, T.M_LIG, T.MI_LIG):
        E.assets[p] = Asset(p, "x")
    if kw.get("actor_exists"):
        E.actors.append(Actor(T.LABEL, "SkeletalMeshActor_77", kind="skel"))


def touch_map():
    E.dirty_maps.add(WORLD)


def touch_scene():
    E.dirty_content.add(SCENE)


E.touch_map, E.touch_scene = touch_map, touch_scene


def fake_unreal():
    u = types.ModuleType("unreal")

    class UES:
        def get_game_world(self):
            return object() if E.pie else None

        def get_editor_world(self):
            return types.SimpleNamespace(get_name=lambda: "L_InfinityStage_V1VerticalSlice")

    class EAS:
        def spawn_actor_from_class(self, cls, loc, rot, transient):
            a = Actor("SkeletalMeshActor", "SkeletalMeshActor_%d" % (100 + len(E.actors)), (loc.x, loc.y, loc.z),
                      rot.yaw, kind="skel")
            a.hidden = False
            E.actors.append(a)
            touch_map()
            return a

        def destroy_actor(self, a):
            E.actors.remove(a)
            touch_map()
            return True

    class SMES:
        def get_num_verts(self, mesh, lod):
            return DESIGN["vertices"]

    subs = {"UES": UES(), "EAS": EAS(), "SMES": SMES()}
    u.UnrealEditorSubsystem, u.EditorActorSubsystem, u.SkeletalMeshEditorSubsystem = "UES", "EAS", "SMES"
    u.get_editor_subsystem = lambda k: subs[k]
    u.LevelSequenceEditorBlueprintLibrary = types.SimpleNamespace(
        get_current_level_sequence=lambda: object() if E.sequencer_open else None)
    pk = lambda n: types.SimpleNamespace(get_name=lambda: n)                       # noqa: E731
    u.EditorLoadingAndSavingUtils = types.SimpleNamespace(
        get_dirty_content_packages=lambda: [pk(x) for x in sorted(E.dirty_content)],
        get_dirty_map_packages=lambda: [pk(x) for x in sorted(E.dirty_maps)],
        save_map=lambda w, p: (E.dirty_maps.discard(p), E.saved.append(p)) and True or True)

    def save_asset(p, only_if_is_dirty=True):
        E.dirty_content.discard(p)
        E.saved.append(p)
        return True
    u.EditorAssetLibrary = types.SimpleNamespace(does_asset_exist=lambda p: p in E.assets, save_asset=save_asset)
    u.load_asset = lambda p: E.assets.get(p)
    u.GameplayStatics = types.SimpleNamespace(get_all_actors_of_class=lambda w, c: list(E.actors))
    u.GuidLibrary = types.SimpleNamespace(conv_guid_to_string=lambda g: g.s)
    u.MovieSceneTimeUnit = types.SimpleNamespace(DISPLAY_RATE="DISPLAY_RATE")
    u.FrameNumber = FrameNumber
    u.MovieSceneSkeletalAnimationTrack = Cls("MovieSceneSkeletalAnimationTrack")
    u.MovieSceneVisibilityTrack = Cls("MovieSceneVisibilityTrack")
    u.Vector, u.Name = V, str
    u.Rotator = lambda roll=0.0, pitch=0.0, yaw=0.0: Rot(roll, pitch, yaw)
    u.AttachmentRule = types.SimpleNamespace(KEEP_WORLD="KEEP_WORLD")
    u.ComponentMobility = types.SimpleNamespace(MOVABLE=En("MOVABLE"))
    u.SkeletalMeshActor, u.Actor, u.StaticMeshComponent = "SkeletalMeshActor", "Actor", "StaticMeshComponent"

    u.SkeletalMesh = FakeSkeletalMesh
    want = {int(f): deg for f, deg in DESIGN["anim"]["lid_open_deg_every_6th"]}

    def pose(anim, bone, frame, root_motion):
        deg = want.get(int(frame), 0.0)
        roll = -deg * E.anim_sign + (0.5 if E.anim_offset_at == int(frame) else 0.0)
        return types.SimpleNamespace(rotation=Rot(roll), translation=V(*T.LID_PIVOT_ANIM_M))
    u.AnimationLibrary = types.SimpleNamespace(get_bone_pose_for_frame=pose, get_num_frames=lambda a: 4795)
    u.log = lambda m: E.saved.append("LOG|" + m)
    u.log_error = lambda m: E.saved.append("ERR|" + m)
    u.SystemLibrary = types.SimpleNamespace(collect_garbage=lambda: None)
    return u


def setup_paths(tmp):
    """Redirect every file the tool writes or reads (except the read-only design/build reports) into tmp."""
    T.HERE = tmp + "/"
    T.APPLY_RECORD = tmp + "/slime_apply_record.json"
    T.IMPORT_RECORD = tmp + "/slime_import_record.json"
    T.BACKUP_ROOT = tmp + "/Backups/PreClamSlime-"
    os.makedirs(tmp + "/Backups", exist_ok=True)
    for name in ("umap.umap", "scene.uasset"):
        with open(tmp + "/" + name, "wb") as h:
            h.write(b"fake-" + name.encode())
    T.UMAP, T.SCENE_FILE = tmp + "/umap.umap", tmp + "/scene.uasset"
    cr = {"actor_paths": {"Bottom": LVL + "StaticMeshActor_8"}}
    with open(tmp + "/clam_record.json", "w") as h:
        json.dump(cr, h)
    T.CLAM_RECORD = tmp + "/clam_record.json"
    with open(T.IMPORT_RECORD, "w") as h:
        json.dump({"state": "saved"}, h)


def run(mode, **over):
    a = T.merged_args(dict({"mode": mode, "confirm": "" if mode == "DRY" else "%s CLAMSLIME" % mode,
                            "run": "TEST-%s" % mode}, **over))
    path = T.HERE + "args.json"
    with open(path, "w") as h:
        json.dump(a, h)
    return T.main(path)


# =====================================================================================================================
def pure_checks():
    check("args_dry_ok", T.validate_args(T.merged_args({"mode": "DRY"})) == [])
    check("args_apply_needs_confirm", any(e.startswith("CONFIRM") for e in T.validate_args(T.merged_args({"mode": "APPLY"}))))
    check("args_reveal_after_start_refused",
          any(e.startswith("FRAMES") for e in T.validate_args(T.merged_args({"mode": "DRY", "reveal_frame": 1500}))))
    lint = {p: T.spec_problems(s) for p, s in T.material_specs().items()}
    check("material_specs_lint_clean", not any(lint.values()), lint)
    bad = copy.deepcopy(T.material_specs()[T.M_SLIME])
    bad["edges"] = [e for e in bad["edges"] if e[3] != "R"]
    check("material_lint_catches_unfed_pin(-)", any(x.startswith("CUSTOM_PIN_UNFED") for x in T.spec_problems(bad)))
    bad2 = copy.deepcopy(T.material_specs()[T.M_SLIME])
    bad2["blend_mode"] = "BLEND_TRANSLUCENT"
    check("material_lint_mask_needs_masked(-)", any(x.startswith("MASK_BLEND") for x in T.spec_problems(bad2)))
    check("mi_values_equal_master_defaults", all(T.MI_SPECS[mi]["scalars"] == T.material_specs()[s["parent"]]["scalars"]
                                                 for mi, s in T.MI_SPECS.items()))
    tree = {b: (None if b == "root" else "root") for b in T.BONES}
    check("bone_tree_ok", T.bone_tree_problems(tree) == [])
    t2 = dict(tree, Armature=None)
    t2["root"] = "Armature"
    p = T.bone_tree_problems(t2)
    check("bone_tree_armature_bone_refused(-)", any(x.startswith("ARMATURE_BONE_PRESENT") for x in p) and
          any(x.startswith("ROOT_HAS_PARENT") for x in p), p)
    t3 = dict(tree)
    del t3["s4_up5"]
    check("bone_tree_missing_bone_refused(-)", any(x.startswith("BONES|") for x in T.bone_tree_problems(t3)))
    w = T.expected_bounds_ue(DESIGN)
    org = [(a + b) / 2 for a, b in zip(w["min"], w["max"])]
    ext = [(b - a) / 2 for a, b in zip(w["min"], w["max"])]
    check("bounds_ok", T.bounds_problems(org, ext, DESIGN) == [])
    lo, hi = DESIGN["rest_bounds_cm_blender"]["min"], DESIGN["rest_bounds_cm_blender"]["max"]
    org2 = [(a + b) / 2 for a, b in zip(lo, hi)]
    ext2 = [(b - a) / 2 for a, b in zip(lo, hi)]
    check("bounds_unflipped_named(-)", any(x.startswith("Y_NOT_FLIPPED") for x in T.bounds_problems(org2, ext2, DESIGN)))
    check("bounds_100x_refused(-)", any(x.startswith("BOUNDS") for x in
                                        T.bounds_problems([o * 100 for o in org], [e * 100 for e in ext], DESIGN)))
    want = T.design_want(DESIGN)
    rows = [(f, r, T.LID_PIVOT_ANIM_M) for f, r in want.items()]
    check("lid_curve_ok", T.lid_curve_problems(rows, want) == [])
    rows_f = [(f, -r, T.LID_PIVOT_ANIM_M) for f, r in want.items()]
    check("lid_curve_sign_flip_named(-)", T.lid_curve_problems(rows_f, want)[:1] == ["LID_SIGN_FLIPPED"])
    # Batch 1f regression triplet: the old centimetre expectation refused the
    # measured rows, the unit-correct expectation passes, and real axis drift
    # remains a refusal.
    logged = [(f, r, [0.0, -0.4786, 0.3002]) for f, r in want.items()]
    check("lid_pivot_logged_old_cm_gate_refuses(-)", any(
        abs(a - b) > T.TOL_CM for a, b in zip(logged[0][2], T.flip_y(T.LID_PIVOT_BLENDER_CM))))
    check("lid_pivot_logged_metres_passes", T.lid_curve_problems(logged, want) == [])
    rows_p = [(f, r, [0.0, 0.4786, 0.3002]) for f, r in want.items()]
    check("lid_pivot_unflipped_refused(-)", any(x.startswith("LID_PIVOT_M") for x in
                                                  T.lid_curve_problems(rows_p, want)))
    rows_d = [(f, r, [0.0, -0.4686, 0.3002]) for f, r in want.items()]
    check("lid_pivot_real_1cm_drift_refused(-)", any(x.startswith("LID_PIVOT_M") for x in
                                                       T.lid_curve_problems(rows_d, want)))
    live = CLAMOPEN["after_roll"]["keys"]
    check("anim_vs_live_ok", T.anim_vs_lid_problems(rows, live, DESIGN, 1446) == [])
    live_bad = copy.deepcopy(live)
    for k in live_bad:
        if k["frame"] == 1596:
            k["value"] += 0.5
    p = T.anim_vs_lid_problems(rows, live_bad, DESIGN, 1446)
    check("anim_vs_live_changed_opening_refused(-)", any(x.startswith("DESIGN_VS_LIVE") for x in p), p)
    p2 = T.anim_vs_lid_problems(rows, live, DESIGN, 1452)
    check("anim_vs_live_wrong_start_refused(-)", bool(p2), p2)
    root = {"path": LVL + "StaticMeshActor_8", "world": {"location": [0, 0, 0], "rotation": [0, 0, 0], "scale": [1, 1, 1]}}
    a = T.merged_args({"mode": "DRY"})
    plan = T.plan_apply(a, DESIGN, 24.0, 6240, root)
    check("plan_ranges", plan["anim_range"] == [1446, 6240] and plan["vis_keys"] == [[0, False], [1446, True]])
    for bad_end, tag in ((6300, "PLAYBACK_END"), ):
        try:
            T.plan_apply(a, DESIGN, 24.0, bad_end, root)
            check("plan_playback_end_refused(-)", False)
        except T.Fail as exc:
            check("plan_playback_end_refused(-)", str(exc).startswith(tag), exc)
    try:
        T.plan_apply(dict(a, expected_playback_end=6300), DESIGN, 24.0, 6300, root)
        check("plan_anim_shorter_than_scene_refused(-)", False)
    except T.Fail as exc:
        check("plan_anim_shorter_than_scene_refused(-)", str(exc).startswith("ANIM_SHORTER_THAN_SCENE"), exc)
    try:
        T.plan_apply(a, DESIGN, 30.0, 6240, root)
        check("plan_fps_refused(-)", False)
    except T.Fail as exc:
        check("plan_fps_refused(-)", str(exc).startswith("FPS"), exc)
    wm = T.interchange_wanted("SK_PearlClam_Slime", "mesh")
    check("interchange_mesh_ok", T.interchange_problems(wm, dict(wm)) == [])
    got = dict(wm)
    got[("mesh", "create_physics_asset")] = True
    check("interchange_physics_on_refused(-)", bool(T.interchange_problems(wm, got)))
    wa = T.interchange_wanted("A_PearlClam_SlimeOpen", "anim", T.SKELETON)
    check("interchange_anim_only", wa[("common_skeletal", "import_only_animations")] is True and
          wa[("mesh", "import_skeletal_meshes")] is False and wa[("common_skeletal", "skeleton")] == T.SKELETON)
    b = json.load(open(FIXTURES + "build/slime_build.json", encoding="utf-8"))
    v = json.load(open(FIXTURES + "validate_slime_report.json", encoding="utf-8"))
    check("sources_ok", T.source_problems(DESIGN, b, v, True) == [], T.source_problems(DESIGN, b, v, True))
    v2 = dict(v, failures=["SEAM_UPPER|55|0.9"])
    check("sources_validation_failed_refused(-)", any(x.startswith("VALIDATION_FAILED") for x in
                                                      T.source_problems(DESIGN, b, v2, True)))
    b2 = copy.deepcopy(b)
    b2["checks"]["reimport_lid_angle_within_1e-3_deg"] = False
    check("sources_build_check_false_refused(-)", any(x.startswith("BUILD_CHECKS") for x in
                                                      T.source_problems(DESIGN, b2, v, True)))
    check("bones_match_design", DESIGN["bones"] == T.BONES)


def flow_checks(tmp):
    sys.modules["unreal"] = fake_unreal()
    # --- DRY ready
    reset()
    setup_paths(tmp)
    m = run("DRY")
    check("dry_apply_ready", m.startswith("CLAMSLIME_DRY_OK") and "apply_ready=1" in m and "next=APPLY" in m, m)
    check("dry_wrote_nothing", not E.dirty_content and not E.dirty_maps)
    # Run-51c prerequisite regression: without the import record/assets the old
    # marker only said apply_ready=0; the new marker names IMPORT, while APPLY
    # still refuses NOT_IMPORTED.
    os.remove(T.IMPORT_RECORD)
    for path in T.created_assets():
        E.assets.pop(path, None)
    m = run("DRY", run="TEST-DRY-NOIMPORT")
    check("dry_missing_assets_names_import_prerequisite", "apply_ready=0" in m and "next=IMPORT" in m, m)
    m = run("APPLY", run="TEST-APPLY-NOIMPORT")
    check("apply_without_import_still_refuses(-)", "NOT_IMPORTED" in m, m)
    reset()
    setup_paths(tmp)
    # --- APPLY ok
    m = run("APPLY")
    check("apply_ok", m.startswith("CLAMSLIME_APPLY_OK"), m)
    rec = json.load(open(T.APPLY_RECORD))
    check("apply_record_applied", rec.get("state") == "applied")
    ours = [x for x in E.actors if x.label == T.LABEL]
    check("apply_one_actor_attached_hidden", len(ours) == 1 and ours[0].parent is E.root and ours[0].hidden)
    bs = [x for x in E.seq.bindings if x.name == T.BINDING]
    check("apply_one_binding_two_tracks", len(bs) == 1 and sorted(t.cls for t in bs[0].tracks) ==
          ["MovieSceneSkeletalAnimationTrack", "MovieSceneVisibilityTrack"])
    check("apply_saved_scene_and_map_only", sorted(set(x for x in E.saved if not x.startswith("LOG")))
          == sorted([SCENE, WORLD]), E.saved)
    check("apply_backup_written", os.path.isdir(rec["backup"]) and len(os.listdir(rec["backup"])) == 2)
    lid_b = [x for x in E.seq.bindings if x.name.startswith("S3 Hangar Float Hold")][0]
    check("apply_lid_binding_untouched", len(lid_b.tracks) == 2)
    # --- re-APPLY over the record
    E.saved = []
    m = run("APPLY", run="TEST-APPLY2")
    check("reapply_over_record_refused(-)", "RECORD_EXISTS" in m and
          not [x for x in E.saved if not x.startswith(("LOG|", "ERR|"))], m)
    # --- REVERT drift: section range edited after APPLY
    sk = [t for t in bs[0].tracks if t.cls == "MovieSceneSkeletalAnimationTrack"][0]
    sk.sections[0].rng = [1440, 6240]
    m = run("REVERT")
    check("revert_drift_section_refused(-)", "DRIFT" in m and "SKEL_RANGE" in m, m)
    sk.sections[0].rng = [1446, 6240]
    ours[0].root.p["relative_location"] = V(0, 0, 3.0)
    m = run("REVERT")
    check("revert_drift_moved_actor_refused(-)", "DRIFT" in m and "ACTOR_REL_LOCATION" in m, m)
    ours[0].root.p["relative_location"] = V(0, 0, 0)
    E.twin.hidden = False
    m = run("REVERT")
    check("revert_drift_twin_changed_refused(-)", "TWIN_CHANGED" in m, m)
    E.twin.hidden = True
    # --- REVERT ok
    E.saved = []
    m = run("REVERT")
    check("revert_ok", m.startswith("CLAMSLIME_REVERT_OK"), m)
    check("revert_removed_actor_and_binding", not [x for x in E.actors if x.label == T.LABEL] and
          not [x for x in E.seq.bindings if x.name == T.BINDING])
    check("revert_record_retired", not os.path.exists(T.APPLY_RECORD) and
          any(f.startswith("slime_apply_record.json.reverted-") for f in os.listdir(tmp)))
    check("revert_saved_scene_and_map_only", sorted(set(x for x in E.saved if not x.startswith("LOG")))
          == sorted([SCENE, WORLD]), E.saved)
    m = run("REVERT", run="TEST-REVERT2")
    check("revert_without_record_refused(-)", "NO_RECORD" in m, m)
    # backup folder already there (same run id) -> refused BEFORE the record is written
    reset()
    setup_paths(tmp)
    os.makedirs(T.BACKUP_ROOT + "TEST-APPLY", exist_ok=True)
    m = run("APPLY")
    check("apply_backup_exists_refused_before_record(-)", "BACKUP_EXISTS" in m and not os.path.exists(T.APPLY_RECORD), m)

    # --- negative controls on APPLY, each from a fresh fake world
    def fresh(**kw):
        for f in os.listdir(tmp):
            if f.startswith("slime_apply_record"):
                os.remove(os.path.join(tmp, f))
        shutil.rmtree(tmp + "/Backups", ignore_errors=True)
        reset(**kw)
        setup_paths(tmp)

    fresh()
    E.anim_offset_at = 150
    m = run("APPLY")
    check("apply_anim_curve_ne_lid_keys_refused(-)", "ANIM_VS_LID" in m and "LID_CURVE|f=150" in m and
          not os.path.exists(T.APPLY_RECORD) and not E.dirty_maps, m)
    fresh()
    E.anim_sign = -1.0
    m = run("APPLY")
    check("apply_anim_sign_flipped_refused(-)", "LID_SIGN_FLIPPED" in m and not os.path.exists(T.APPLY_RECORD), m)
    fresh(actor_exists=True)
    m = run("APPLY")
    check("apply_actor_exists_refused(-)", "ACTOR_EXISTS" in m and not os.path.exists(T.APPLY_RECORD), m)
    fresh(lid_binding=False)
    m = run("APPLY")
    check("apply_lid_binding_missing_refused(-)", "LID_BINDING_COUNT|0" in m and not os.path.exists(T.APPLY_RECORD), m)
    fresh()
    E.dirty_content.add("/Game/Other/Thing")
    m = run("APPLY")
    check("apply_dirty_editor_refused(-)", "DIRTY_AT_START" in m, m)
    fresh()
    E.sequencer_open = True
    m = run("APPLY")
    check("apply_sequencer_open_refused(-)", "SEQUENCER_OPEN" in m, m)
    fresh()
    E.pie = True
    m = run("APPLY")
    check("apply_pie_refused(-)", "PIE_RUNNING" in m, m)
    fresh()
    E.seq.end = 6300
    m = run("APPLY", expected_playback_end=6300)
    check("apply_scene_longer_than_anim_refused(-)", "ANIM_SHORTER_THAN_SCENE" in m, m)
    fresh()
    E.params_setter_lies = True
    m = run("APPLY")
    rec = json.load(open(T.APPLY_RECORD)) if os.path.exists(T.APPLY_RECORD) else {}
    check("apply_params_setter_lies_caught(-)", "READBACK" in m and "SKEL_ANIM" in m and "NOTHING SAVED" in m and
          rec.get("state") == "written" and SCENE not in E.saved, m)
    fresh()
    E.mesh_setter_lies = True
    m = run("APPLY")
    check("apply_mesh_setter_lies_caught(-)", "READBACK" in m and "ACTOR_MESH" in m, m)
    fresh()
    E.attach_offset = True
    m = run("APPLY")
    check("apply_non_identity_relative_caught(-)", "READBACK" in m and "ACTOR_REL_LOCATION" in m, m)
    fresh()
    E.side_effect = lambda: setattr(E.twin, "hidden", False)
    m = run("APPLY")
    check("apply_twin_touched_caught(-)", "READBACK" in m and "TWIN_CHANGED" in m, m)
    fresh()
    E.side_effect = lambda: E.dirty_content.add("/Game/Other/Stray")
    m = run("APPLY")
    check("apply_stray_dirty_package_refuses_save(-)", "CENSUS" in m and SCENE not in E.saved, m)
    fresh()
    os.remove(T.IMPORT_RECORD)
    m = run("APPLY")
    check("apply_before_import_refused(-)", "NOT_IMPORTED" in m, m)
    fresh()
    with open(T.CLAM_RECORD, "w") as h:
        json.dump({"actor_paths": {"Bottom": LVL + "StaticMeshActor_999"}}, h)
    m = run("APPLY")
    check("apply_root_not_clam_apply_root_refused(-)", "ROOT_NOT_CLAM_APPLY_ROOT" in m, m)
    fresh()
    m = run("IMPORT")
    check("import_targets_exist_refused(-)", "IMPORT_RECORD_EXISTS" in m or "TARGETS_EXIST" in m, m)
    os.remove(T.IMPORT_RECORD)
    m = run("IMPORT")
    check("import_create_only_refused_when_assets_exist(-)", "TARGETS_EXIST" in m, m)
    m = run("APPLY", confirm="APPLY")
    check("apply_wrong_confirm_refused(-)", "CONFIRM" in m, m)


def main():
    pure_checks()
    tmp = tempfile.mkdtemp(prefix="clamslime_harness_")
    try:
        flow_checks(tmp.replace("\\", "/"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(1 for _n, ok in RESULTS if ok)
    print("CLAMSLIME_HARNESS|pass=%d|fail=%d|total=%d" % (n, len(RESULTS) - n, len(RESULTS)))
    report = {"pass": n, "fail": len(RESULTS) - n, "total": len(RESULTS), "results": RESULTS}
    with open(HERE + "test_slime_apply_ue_report.json", "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1)
    return 0 if n == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
