"""A small fake of the `unreal` API surface hp_place_grease.py uses, for the OFFLINE harness only.

It models: actors with label/folder/tags/transform/attachment and a decal component; spawn/destroy; the dirty-map
census (any change dirties the map; save_current_level cleans it); assets that exist; logs.  Rotation axes use UE's
FRotationMatrix formulas (copied from Tools/FlatV3/handprints/build_handprint_placement.rotation_axes).
"""
import math
import types

WORLD_PATH = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"


class Vector:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)


class Rotator:
    def __init__(self, roll=0.0, pitch=0.0, yaw=0.0):
        self.roll, self.pitch, self.yaw = float(roll), float(pitch), float(yaw)


def axes(r):
    sp, cp = math.sin(math.radians(r.pitch)), math.cos(math.radians(r.pitch))
    sy, cy = math.sin(math.radians(r.yaw)), math.cos(math.radians(r.yaw))
    sr, cr = math.sin(math.radians(r.roll)), math.cos(math.radians(r.roll))
    x = [cp * cy, cp * sy, sp]
    y = [sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, -sr * cp]
    z = [-(cr * sp * cy + sr * sy), cy * sr - cr * sp * sy, cr * cp]
    return x, y, z


class Asset:
    def __init__(self, path):
        self.path = path

    def get_path_name(self):
        return self.path + "." + self.path.rsplit("/", 1)[1]


class Pkg:
    def __init__(self, p):
        self.p = p

    def get_path_name(self):
        return self.p


def make(state):
    u = types.ModuleType("unreal")
    u.Vector, u.Rotator = Vector, Rotator
    u.Name = str
    u.logs = state.setdefault("logs", [])

    def mark():
        state["dirty"] = True

    class DecalComponent:
        def __init__(self):
            self.props = {"decal_size": Vector(8, 10, 10), "sort_order": 0, "fade_screen_size": 0.01,
                          "mobility": "STATIC"}
            self.mat = None

        def modify(self):
            mark()

        def set_mobility(self, m):
            self.props["mobility"] = m

        def set_decal_material(self, m):
            self.mat = m

        def get_decal_material(self):
            return self.mat

        def set_sort_order(self, v):
            self.props["sort_order"] = int(v)

        def set_fade_screen_size(self, v):
            self.props["fade_screen_size"] = float(v)

        def set_editor_property(self, k, v):
            self.props[k] = v

        def get_editor_property(self, k):
            return self.props[k]

    class Actor:
        n = 0

        def __init__(self, loc, rot):
            Actor.n += 1
            self.name = "%s_%d" % (type(self).__name__, Actor.n)
            self.label, self.folder, self.tags = self.name, "", []
            self.loc, self.rot, self.scale, self.parent = loc, rot, Vector(1, 1, 1), None

        def modify(self):
            mark()

        def get_path_name(self):
            return WORLD_PATH + ".L_InfinityStage_V1VerticalSlice:PersistentLevel." + self.name

        def set_actor_label(self, l):
            if state.get("fault_label") and l == state["fault_label"]:
                return
            self.label = l

        def get_actor_label(self):
            return self.label

        def set_folder_path(self, f):
            self.folder = f

        def get_folder_path(self):
            return self.folder

        def set_editor_property(self, k, v):
            if k == "tags":
                if state.get("fault_drop_tag"):
                    v = [t for t in v if t != state["fault_drop_tag"]]
                self.tags = list(v)
            else:
                raise KeyError(k)

        def get_editor_property(self, k):
            if k == "tags":
                return list(self.tags)
            if k == "decal":
                return self.decal
            raise KeyError(k)

        def get_actor_location(self):
            return Vector(self.loc.x, self.loc.y, self.loc.z)

        def get_actor_rotation(self):
            return Rotator(self.rot.roll, self.rot.pitch, self.rot.yaw)

        def get_actor_scale3d(self):
            return Vector(self.scale.x, self.scale.y, self.scale.z)

        def set_actor_scale3d(self, s):
            self.scale = s

        def get_actor_transform(self):
            rot = self.get_actor_rotation()
            return types.SimpleNamespace(translation=self.get_actor_location(),
                                         rotation=types.SimpleNamespace(rotator=lambda: rot))

        def get_actor_forward_vector(self):
            return Vector(*axes(self.rot)[0])

        def get_actor_right_vector(self):
            return Vector(*axes(self.rot)[1])

        def get_actor_up_vector(self):
            return Vector(*axes(self.rot)[2])

        def attach_to_actor(self, parent, socket, a, b, c, weld):
            self.parent = parent
            return True

        def get_attach_parent_actor(self):
            return self.parent

    class DecalActor(Actor):
        def __init__(self, loc, rot):
            super().__init__(loc, rot)
            self.decal = DecalComponent()

    class StaticMeshActor(Actor):
        pass

    u.Actor, u.DecalActor, u.StaticMeshActor = Actor, DecalActor, StaticMeshActor
    u.ComponentMobility = types.SimpleNamespace(MOVABLE="MOVABLE", STATIC="STATIC")
    u.AttachmentRule = types.SimpleNamespace(KEEP_WORLD="KEEP_WORLD")

    class World:
        def get_outermost(self):
            return types.SimpleNamespace(get_name=lambda: WORLD_PATH)

    state.setdefault("actors", [])
    state["world"] = World()

    class EditorActorSubsystem:
        def spawn_actor_from_class(self, cls, loc, rot):
            a = cls(Vector(loc.x, loc.y, loc.z), Rotator(rot.roll, rot.pitch, rot.yaw))
            state["actors"].append(a)
            mark()
            return a

        def destroy_actor(self, a):
            if state.get("fault_destroy") and a.label == state["fault_destroy"]:
                return False
            state["actors"].remove(a)
            mark()
            return True

        def get_all_level_actors(self):
            return list(state["actors"])

    class UnrealEditorSubsystem:
        def get_editor_world(self):
            return state["world"]

        def get_game_world(self):
            return None

    class LevelEditorSubsystem:
        def save_current_level(self):
            state["saves"] = state.get("saves", 0) + 1
            state["dirty"] = False
            return True

    subs = {EditorActorSubsystem: EditorActorSubsystem(), UnrealEditorSubsystem: UnrealEditorSubsystem(),
            LevelEditorSubsystem: LevelEditorSubsystem()}
    u.EditorActorSubsystem, u.UnrealEditorSubsystem, u.LevelEditorSubsystem = (
        EditorActorSubsystem, UnrealEditorSubsystem, LevelEditorSubsystem)
    u.get_editor_subsystem = lambda cls: subs[cls]
    u.GameplayStatics = types.SimpleNamespace(
        get_all_actors_of_class=lambda world, cls: [a for a in state["actors"] if isinstance(a, cls)])
    u.EditorLoadingAndSavingUtils = types.SimpleNamespace(
        get_dirty_map_packages=lambda: [Pkg(WORLD_PATH)] if state.get("dirty") else [],
        get_dirty_content_packages=lambda: [])
    u.EditorAssetLibrary = types.SimpleNamespace(does_asset_exist=lambda p: p in state["assets"])
    u.load_asset = lambda p: Asset(p) if p in state["assets"] else None

    class Tx:
        def __init__(self, name):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    u.ScopedEditorTransaction = Tx
    u.Paths = types.SimpleNamespace(convert_relative_path_to_full=lambda p: p,
                                    project_dir=lambda: state["project"] + "/")
    u.log = lambda m: u.logs.append(("log", m))
    u.log_error = lambda m: u.logs.append(("error", m))
    u.log_warning = lambda m: u.logs.append(("warning", m))
    return u
