"""Purpose-built fake Unreal surface for the W2 wave swap offline harness."""
import os


WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
LS = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
MEASURED_LOD1_TIMBER_R = 0.7333


class State:
    def __init__(self):
        self.assets = {}
        self.disk_packages = set()
        self.content_dirty = set()
        self.map_dirty = set()
        self.deleted_assets = []
        self.logs = []
        self.actors = []
        self.world = World()


STATE = None


class Vector:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)


class Rotator:
    def __init__(self, roll=0.0, pitch=0.0, yaw=0.0):
        self.roll, self.pitch, self.yaw = float(roll), float(pitch), float(yaw)


class Rotation:
    def __init__(self, rotator=None):
        self._rotator = rotator or Rotator()

    def rotator(self):
        return self._rotator


class Transform:
    def __init__(self, location=None, rotation=None, scale=None):
        self.translation = location or Vector()
        self.rotation = Rotation(rotation)
        self.scale3d = scale or Vector(1.0, 1.0, 1.0)


class Package:
    def __init__(self, name):
        self.name = str(name).split(".", 1)[0]

    def get_name(self):
        return self.name


class World:
    def get_outermost(self):
        return Package(WORLD)


class Asset:
    def __init__(self, path):
        self.path = str(path).split(".", 1)[0]

    def get_path_name(self):
        return self.path + "." + self.path.rsplit("/", 1)[-1]

    def get_outermost(self):
        return Package(self.path)


class StaticMesh(Asset):
    def __init__(self, path, width_cm=1000.0,
                 lod1_timber_r=MEASURED_LOD1_TIMBER_R):
        super().__init__(path)
        self.width_cm = float(width_cm)
        self.lod1_timber_r = float(lod1_timber_r)


class Texture2D(Asset):
    pass


class MaterialInstanceConstant(Asset):
    pass


class StaticMeshComponent:
    def __init__(self, mesh, owner=None):
        self.mesh = mesh
        self.owner = owner

    def get_owner(self):
        return self.owner

    def modify(self):
        # Measured live 2 Oct (FV3W2-20261002-02): modify() + set_static_mesh did NOT
        # dirty the level either; modify() alone is not modelled as dirtying.
        return True

    def get_editor_property(self, name):
        if name != "static_mesh":
            raise KeyError(name)
        return self.mesh

    def set_editor_property(self, name, value):
        if name != "static_mesh":
            raise KeyError(name)
        self.mesh = value
        STATE.map_dirty.add(WORLD)   # property-change path dirties the package

    def get_static_mesh(self):
        return self.mesh

    def set_static_mesh(self, mesh):
        # Measured live: set_static_mesh alone does NOT dirty the level package.
        self.mesh = mesh
        return True


class Actor:
    def __init__(self, label, path, mesh, transform=None):
        self.label = label
        self.path = path
        self.component = StaticMeshComponent(mesh, owner=self)
        self.transform = transform or Transform()

    def modify(self):
        return True

    def get_actor_label(self):
        return self.label

    def get_path_name(self):
        return self.path

    def get_component_by_class(self, _kind):
        return self.component

    def get_components_by_class(self, _kind):
        return [self.component]

    def get_actor_transform(self):
        return self.transform

    def get_actor_bounds(self, _only_colliding, _include_children):
        return Vector(), Vector(6.0, self.component.mesh.width_cm * 0.5, 100.0)


class Paths:
    @staticmethod
    def convert_relative_path_to_full(path):
        return os.path.abspath(path)

    @staticmethod
    def project_dir():
        return REPO

    @staticmethod
    def project_saved_dir():
        return os.path.join(REPO, "Saved")

    @staticmethod
    def project_content_dir():
        return os.path.join(REPO, "Content")

    @staticmethod
    def project_log_dir():
        return os.path.join(REPO, "Saved", "Logs")


class EditorLoadingAndSavingUtils:
    @staticmethod
    def get_dirty_content_packages():
        return [Package(path) for path in sorted(STATE.content_dirty)]

    @staticmethod
    def get_dirty_map_packages():
        return [Package(path) for path in sorted(STATE.map_dirty)]


class EditorAssetLibrary:
    @staticmethod
    def load_asset(path):
        return STATE.assets.get(str(path).split(".", 1)[0])

    @staticmethod
    def does_asset_exist(path):
        return str(path).split(".", 1)[0] in STATE.assets

    @staticmethod
    def save_asset(path, only_if_is_dirty=False):
        path = str(path).split(".", 1)[0]
        if path not in STATE.assets:
            return False
        STATE.disk_packages.add(path)
        STATE.content_dirty.discard(path)
        return True

    @staticmethod
    def delete_loaded_asset(asset):
        path = asset.path
        STATE.assets.pop(path, None)
        STATE.content_dirty.discard(path)
        STATE.deleted_assets.append(path)
        return True

    @staticmethod
    def find_package_referencers_for_asset(path, _load_assets):
        path = str(path).split(".", 1)[0]
        if any(actor.component.mesh.path == path for actor in STATE.actors):
            return [WORLD]
        return []


class UnrealEditorSubsystem:
    def get_editor_world(self):
        return STATE.world

    def get_game_world(self):
        return None


class EditorActorSubsystem:
    def get_all_level_actors(self):
        return list(STATE.actors)


class LevelEditorSubsystem:
    def save_current_level(self):
        if WORLD not in STATE.map_dirty:
            return False
        STATE.map_dirty.discard(WORLD)
        return True


def get_editor_subsystem(kind):
    return kind()


def find_object(_outer, object_path):
    return STATE.assets.get(str(object_path).split(".", 1)[0])


def log(message):
    STATE.logs.append("Info|" + str(message))


def log_error(message):
    STATE.logs.append("Error|" + str(message))


class FakePilot:
    @staticmethod
    def dynamic_lod(mesh, lod):
        assert lod == 1
        value = mesh.lod1_timber_r
        return {"materials": {"2": {"r_range": [value, value]}}}

    @staticmethod
    def reload_new_packages(_paths):
        return None


class FakeSlotA:
    """Behavioral stand-in; production still calls the real Slot A functions."""
    pilot = FakePilot()
    fail_key = None
    fail_created_count = 0

    @staticmethod
    def _geometry():
        front = {"du_dY": 0.001, "dv_dZ": -0.001}
        flap = {"du_dY": 0.001, "dv_dZ": -0.001}
        return {"num_lods": 2, "slots": ["Front", "Flap", "Timber", "Edge"],
                "sections": {"0": {"Front": front, "Flap": flap},
                             "1": {"Front": front, "Flap": None}}}

    @staticmethod
    def load_json(path):
        import json
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def asset_paths(row):
        return sorted(row["destinations"].values())

    @classmethod
    def import_asset(cls, row):
        paths = cls.asset_paths(row)
        for index, path in enumerate(paths):
            if path == row["destinations"]["mesh"]:
                width = float(row["validation"]["dimensions_m"][1]) * 100.0
                asset = StaticMesh(path, width_cm=width,
                                   lod1_timber_r=MEASURED_LOD1_TIMBER_R)
            elif "/Textures/" in path:
                asset = Texture2D(path)
            else:
                asset = MaterialInstanceConstant(path)
            STATE.assets[path] = asset
            STATE.content_dirty.add(path)
            if row["key"] == cls.fail_key and index + 1 >= cls.fail_created_count:
                raise RuntimeError("FAKE_IMPORT_FAILURE|key=" + row["key"])
        return {"created": paths, "geometry": cls._geometry(),
                "slot_a_gates": "PASS"}

    @staticmethod
    def save_narrow(paths):
        if sorted(STATE.content_dirty) != sorted(paths) or STATE.map_dirty:
            raise RuntimeError("FAKE_SAVE_SCOPE_FAIL")
        for path in paths:
            EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)
        return {"before": {"content": sorted(paths), "maps": []},
                "after": {"content": [], "maps": []}}

    @staticmethod
    def verify_asset_fresh(row):
        paths = FakeSlotA.asset_paths(row)
        if any(path not in STATE.assets or path not in STATE.disk_packages for path in paths):
            raise RuntimeError("FAKE_FRESH_READBACK_FAIL")
        return {"fresh": True, "paths": paths, "geometry": FakeSlotA._geometry()}


def reset():
    global STATE
    STATE = State()
    ls = Asset(LS)
    STATE.assets[LS] = ls
    STATE.disk_packages.add(LS)
    widths = [1431.69, 1627.55, 1531.91, 1460.79, 1833.45, 1439.22]
    for index, (row, half) in enumerate((
            (1, "A"), (1, "B"), (2, "A"), (2, "B"), (3, "A"), (3, "B"))):
        old_path = "/Game/Legacy/SM_WaveRow%d_%s" % (row, half)
        old_mesh = StaticMesh(old_path, width_cm=widths[index])
        STATE.assets[old_path] = old_mesh
        STATE.disk_packages.add(old_path)
        STATE.actors.append(Actor(
            "S3 Wave Row%d %s" % (row, half),
            "%s:PersistentLevel.S3WaveRow%d%s" % (WORLD, row, half), old_mesh,
            Transform(location=Vector(row * 100.0, index * 50.0, 10.0),
                      rotation=Rotator(yaw=0.0), scale=Vector(1.0, 1.0, 1.0))))
    FakeSlotA.fail_key = None
    FakeSlotA.fail_created_count = 0
    return STATE
