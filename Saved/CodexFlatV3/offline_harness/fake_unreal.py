"""Small offline Unreal stub for exercising the real Slot B Python scripts."""
import math
import os

SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


class State:
    def __init__(self):
        self.assets = {}
        self.content_dirty = set()
        self.map_dirty = set()
        self.logs = []
        self.world = World()
        self.actor = None


STATE = None


class Vector:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)

    def __add__(self, other):
        return Vector(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other):
        return Vector(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, value):
        return Vector(self.x * value, self.y * value, self.z * value)

    __rmul__ = __mul__

    def dot(self, other):
        return self.x * other.x + self.y * other.y + self.z * other.z

    def length(self):
        return math.sqrt(self.dot(self))


class Rotator:
    def __init__(self, roll=0.0, pitch=0.0, yaw=0.0):
        self.roll, self.pitch, self.yaw = float(roll), float(pitch), float(yaw)


class Rotation:
    def __init__(self, rotator=None):
        self._rotator = rotator or Rotator()
        self.x = self.y = self.z = 0.0
        self.w = 1.0

    def rotator(self):
        return self._rotator

    def rotate_vector(self, value):
        if any(abs(value) > 0.000001 for value in
               (self._rotator.roll, self._rotator.pitch, self._rotator.yaw)):
            # The harness only performs spatial gates on identity-rotation placed refs.
            return value
        return value


class Transform:
    def __init__(self, location=None, rotation=None, scale=None):
        self.translation = location or Vector()
        self.rotation = rotation if isinstance(rotation, Rotation) else Rotation(rotation)
        self.scale3d = scale or Vector(1.0, 1.0, 1.0)

    def transform_location(self, point):
        scaled = Vector(point.x * self.scale3d.x, point.y * self.scale3d.y,
                        point.z * self.scale3d.z)
        return self.translation + self.rotation.rotate_vector(scaled)

    def inverse_transform_location(self, point):
        delta = point - self.translation
        return Vector(delta.x / self.scale3d.x, delta.y / self.scale3d.y,
                      delta.z / self.scale3d.z)


class Box:
    def __init__(self, minimum, maximum):
        self.min, self.max = minimum, maximum


class Asset:
    def __init__(self, path):
        self.path = path

    def get_path_name(self):
        return self.path


class StaticMesh(Asset):
    def __init__(self, path, minimum=None, maximum=None):
        super().__init__(path)
        self.box = Box(minimum or Vector(-5.0, -5.0, 0.0),
                       maximum or Vector(5.0, 5.0, 1000.0))

    def get_bounding_box(self):
        return self.box


class Obj:
    def __init__(self, **props):
        self.props = props

    def get_editor_property(self, name):
        return self.props[name]

    def set_editor_property(self, name, value):
        self.props[name] = value
        STATE.content_dirty.add(SHOW)


class Show(Obj):
    def modify(self):
        STATE.content_dirty.add(SHOW)


class Guid:
    def __init__(self, value):
        self.value = str(value)

    def to_string(self):
        return self.value


class FrameNumber:
    def __init__(self, value):
        self.value = int(value)


class FrameRate:
    def __init__(self, numerator=48000, denominator=1):
        self.numerator, self.denominator = numerator, denominator


class NamedClass:
    def __init__(self, name):
        self.name = name

    def get_name(self):
        return self.name


class PassageActor(Obj):
    def get_class(self):
        return NamedClass("InfinityStagePassageActor")

    def get_actor_label(self):
        return "Passage 04 Fake"

    def materialize_passage(self):
        STATE.map_dirty.add(WORLD)
        return True

    def evaluate_mechanisms_at_master_frame(self, _frame):
        STATE.map_dirty.add(WORLD)
        return True


class Component(Obj):
    pass


class Package:
    def __init__(self, name):
        self.name = name

    def get_name(self):
        return self.name


class World:
    def get_outermost(self):
        return Package(WORLD)


class Paths:
    @staticmethod
    def convert_relative_path_to_full(path):
        return os.path.abspath(path)

    @staticmethod
    def project_saved_dir():
        return os.path.join(REPO, "Saved")

    @staticmethod
    def project_dir():
        return REPO

    @staticmethod
    def project_log_dir():
        return os.path.join(REPO, "Saved", "Logs")


class EditorAssetLibrary:
    @staticmethod
    def load_asset(path):
        if path is None:
            raise TypeError("Cannot nativize NoneType as AssetPath")
        return STATE.assets.get(path)

    @staticmethod
    def save_asset(path, only_if_is_dirty=False):
        del only_if_is_dirty
        STATE.content_dirty.discard(path)
        return True


class EditorLoadingAndSavingUtils:
    @staticmethod
    def get_dirty_content_packages():
        return [Package(value) for value in sorted(STATE.content_dirty)]

    @staticmethod
    def get_dirty_map_packages():
        return [Package(value) for value in sorted(STATE.map_dirty)]


class UnrealEditorSubsystem:
    def get_editor_world(self):
        return STATE.world

    def get_game_world(self):
        return None


class EditorActorSubsystem:
    def get_all_level_actors(self):
        return [STATE.actor] if STATE.actor is not None else []


class LevelEditorSubsystem:
    def save_current_level(self):
        STATE.map_dirty.discard(WORLD)
        return True


_EDITOR = UnrealEditorSubsystem()
_ACTORS = EditorActorSubsystem()
_LEVEL = LevelEditorSubsystem()


def get_editor_subsystem(kind):
    if kind is UnrealEditorSubsystem:
        return _EDITOR
    if kind is EditorActorSubsystem:
        return _ACTORS
    if kind is LevelEditorSubsystem:
        return _LEVEL
    raise KeyError(kind)


class EnumValue:
    def __init__(self, enum_name, member, ordinal):
        self.text = "<%s.%s: %d>" % (enum_name, member, ordinal)

    def __str__(self):
        return self.text


class InfinityPanelFacingPolicy:
    AUTO_BY_ROLE = EnumValue("InfinityPanelFacingPolicy", "AUTO_BY_ROLE", 0)
    PRESERVE_ASSET = EnumValue("InfinityPanelFacingPolicy", "PRESERVE_ASSET", 1)
    ROTATE180_AROUND_UP = EnumValue("InfinityPanelFacingPolicy", "ROTATE180_AROUND_UP", 2)


class InfinityStageCameraPilotLibrary:
    @staticmethod
    def get_passage_frame_range(_show, _guid):
        return True, FrameNumber(-10000000), FrameNumber(100000000)


def log(value):
    STATE.logs.append(str(value))


def log_error(value):
    STATE.logs.append(str(value))


def log_warning(value):
    STATE.logs.append(str(value))


def plain_transform(value):
    return Transform(
        location=Vector(*value["location"]),
        rotation=Rotator(roll=value["rotation"][0], pitch=value["rotation"][1],
                         yaw=value["rotation"][2]),
        scale=Vector(*value["scale"]))


def panel_from(record):
    mesh = None if record["mesh"] is None else STATE.assets[record["mesh"]]
    overrides = [None if path is None else STATE.assets[path]
                 for path in record["material_overrides"]]
    return Obj(mesh=mesh, material_overrides=overrides,
               local_transform=plain_transform(record["local_transform"]),
               facing_policy=record["facing_policy"],
               flip_image_horizontally=record["flip_image_horizontally"])


def mechanism_from(record):
    return Obj(kind=record["kind"], playback_mode=record["playback_mode"],
               phase_origin=record["phase_origin"],
               explicit_origin_frame=FrameNumber(record["explicit_origin_frame"]),
               cycle_rate_hz=record["cycle_rate_hz"],
               phase_offset_cycles=record["phase_offset_cycles"],
               inward_travel_cm=record["inward_travel_cm"])


def _register_record_assets(originals, plan):
    for record in originals["rows"]:
        for side in ("left", "right", "top"):
            mesh_path = record[side]["mesh"]
            if mesh_path is not None and mesh_path not in STATE.assets:
                STATE.assets[mesh_path] = StaticMesh(mesh_path)
            for path in record[side]["material_overrides"]:
                if path is not None and path not in STATE.assets:
                    STATE.assets[path] = Asset(path)
    for row in plan["rows"]:
        for side in ("left", "right"):
            path = row[side]["mesh"]
            if path in STATE.assets:
                continue
            placement = row["placement"][side]
            if side == "left":
                min_y = 0.0
                max_y = float(placement["new_inner_edge_cm"] - placement["old_outer_edge_cm"])
            else:
                min_y = float(placement["new_inner_edge_cm"] - placement["old_outer_edge_cm"])
                max_y = 0.0
            STATE.assets[path] = StaticMesh(
                path, Vector(-5.0, min_y, 0.0), Vector(5.0, max_y, 1000.0))


def reset(originals, plan, mode):
    global STATE
    STATE = State()
    _register_record_assets(originals, plan)
    plan_by_guid = {row["cue_guid"]: row for row in plan["rows"]}
    max_index = max(record["cue_index"] for record in originals["rows"])
    cues = [Obj(label="unused", wing_pair=Obj()) for _ in range(max_index + 1)]
    refs = []
    passage_guid = Guid("P04-PASSAGE-GUID")
    for record in originals["rows"]:
        target = plan_by_guid[record["cue_guid"]]
        if mode == "verify":
            left_record, right_record = target["left"], target["right"]
            offset = record["occurrence_offset"]
        else:
            left_record = dict(record["left"])
            left_record["mesh"] = target["left"]["mesh"]
            left_record["local_transform"] = target["left"]["local_transform"]
            left_record["material_overrides"] = []
            left_record["facing_policy"] = "PRESERVE_ASSET"
            left_record["flip_image_horizontally"] = False
            right_record = dict(record["right"])
            right_record["mesh"] = target["right"]["mesh"]
            right_record["local_transform"] = target["right"]["local_transform"]
            right_record["material_overrides"] = []
            right_record["facing_policy"] = "PRESERVE_ASSET"
            right_record["flip_image_horizontally"] = False
            offset = {"location": [99.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0],
                      "scale": [1.0, 1.0, 1.0]}
        pair = Obj(left=panel_from(left_record), right=panel_from(right_record),
                   top=panel_from(record["top"]), mechanism=mechanism_from(record["mechanism"]),
                   occurrence_offset=plain_transform(offset), interval_to_next=FrameNumber(600000))
        cue_guid = Guid(record["cue_guid"])
        cue = Obj(label=record["cue_label"], wing_pair=pair, cue_guid=cue_guid)
        cues[record["cue_index"]] = cue
        if mode == "verify":
            for side, inward in (("left", Vector(0.0, 1.0, 0.0)),
                                  ("right", Vector(0.0, -1.0, 0.0))):
                row = target[side]
                mesh = STATE.assets[row["mesh"]]
                base = plain_transform(row["local_transform"])
                refs.append(Obj(cue_guid=cue_guid, side=side.upper(),
                                component=Component(static_mesh=mesh),
                                base_world_transform=base,
                                inward_world_direction=inward))
    settings = Obj(passage_guid=passage_guid, lead_in_frames=FrameNumber(0))
    show = Show(cues=cues, passage_settings=[settings], tick_resolution=FrameRate())
    actor = PassageActor(show_asset=show, passage_guid=passage_guid,
                         materialized_panels=refs)
    STATE.assets[SHOW] = show
    STATE.actor = actor
    return STATE
