"""Offline +/- controls for the passage-parameterised Flat V3 swap kit."""
import importlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
SLOT = HERE.parent
KIT = SLOT / "swapkit"
REPO = SLOT.parents[1]
PROBE = SLOT / "probe_p05_labels_out.json"
P05_MEASURED_DRY = KIT / "swapkit_dry_run_FV3C-20261002-02.json"
P05_MEASURED_DOC = json.loads(P05_MEASURED_DRY.read_text(encoding="utf-8"))
P05_FLAGGED_GUIDS = {row["cue_guid"] for row in P05_MEASURED_DOC["overreach_flags"]}
P05_MEASURED_ROWS = {
    row["cue_guid"]: row
    for row in P05_MEASURED_DOC["rows"] if row["cue_guid"] in P05_FLAGGED_GUIDS
}
ROWS_DUMP = REPO / "Saved" / "CodexWingHandedness2" / "rows_dump.json"
sys.path.insert(0, str(HERE))
import fake_unreal
sys.modules["unreal"] = fake_unreal

RESULTS = []
GAP_TABLE = []
FORBIDDEN = ("save_asset", "save_current_level", "materialize_passage", "set_editor_property")


class ConfigActor(fake_unreal.PassageActor):
    def __init__(self, label, **props):
        super().__init__(**props)
        self.label = label

    def get_actor_label(self):
        return self.label + " Fake"

    def materialize_passage(self):
        fake_unreal.STATE.map_dirty.add(fake_unreal.WORLD)
        rebuild_refs(self)
        return True


def panel_record(mesh, y, top=False):
    return {"mesh": mesh, "material_overrides": [],
            "local_transform": {"location": [0.0, float(y), 0.0],
                                "rotation": [0.0, 0.0, 0.0],
                                "scale": [1.0, 1.0, 1.0]},
            "facing_policy": "PRESERVE_ASSET", "flip_image_horizontally": False}


def mechanism_record():
    return {"kind": "SLIDE", "playback_mode": "LOOP", "phase_origin": "PASS_FRAME",
            "explicit_origin_frame": 0, "cycle_rate_hz": 1.0,
            "phase_offset_cycles": 0.0, "inward_travel_cm": 100.0}


def register_mesh(path, side):
    if path is None or path in fake_unreal.STATE.assets:
        return
    if side == "left":
        minimum, maximum = fake_unreal.Vector(-5, 0, 0), fake_unreal.Vector(5, 300, 1000)
    elif side == "right":
        minimum, maximum = fake_unreal.Vector(-5, -300, 0), fake_unreal.Vector(5, 0, 1000)
    else:
        minimum, maximum = fake_unreal.Vector(-5, -100, 0), fake_unreal.Vector(5, 100, 200)
    fake_unreal.STATE.assets[path] = fake_unreal.StaticMesh(path, minimum, maximum)


def mapping_rows(config):
    doc = json.loads(Path(config["mapping_file"]).read_text(encoding="utf-8"))
    if config["mapping_kind"] == "kept_map":
        return [row for row in doc["entries"] if row["passage"] == config["passage"]]
    return doc["occurrences"]


def probe_rows(config):
    if config["passage"] == "P06":
        dump = json.loads(ROWS_DUMP.read_text(encoding="utf-8"))
        rows = [row for row in dump["rows"] if row.get("passage") == 6]
        return [[int(row["index"]), str(row["label"]),
                 "P06-OFFLINE-GUID-%03d" % int(row["ordinal"]),
                 str(row["left"]["mesh"])] for row in rows]
    probe = json.loads(PROBE.read_text(encoding="utf-8"))
    return probe[config["passage"] + " Wing"]["rows"]


def package_path(value):
    return str(value).split(".", 1)[0]


def p01_right(left):
    replacements = {
        "/StaticMeshes/SM_L_pillar1_bw": "/StaticMeshes/SM_R_Pillar1_bw",
        "/StaticMeshes/SM_L_Pillar2_bw": "/StaticMeshes/SM_R_Pillar2_bw",
        "/StaticMeshes/SM_L_1_roccoco": "/StaticMeshes/SM_R__1_roccoco",
        "/StaticMeshes/SM_SaltFormation_01_L_v2": "/StaticMeshes/SM_SaltFormation_01_R_v2",
    }
    for old, new in replacements.items():
        if left.endswith(old):
            return left[:-len(old)] + new
    return left + "_HARNESS_RIGHT"


def register_mapping_meshes(config, doc):
    kind = config["mapping_kind"]
    if kind == "kept_map":
        for entry in doc["entries"]:
            if entry.get("passage") == config["passage"]:
                side = {"L": "left", "R": "right", "C": "top"}[entry["side"]]
                register_mesh(config["destination_root"] + "/StaticMeshes/" +
                              entry["new_mesh"], side)
    elif kind == "p03_layout":
        for family in doc["family_catalog"].values():
            asset = family["asset"]
            side = "right" if "_R" in asset else ("top" if "_C" in asset else "left")
            register_mesh(config["destination_root"] + "/StaticMeshes/" +
                          asset, side)
    elif kind == "p02_layout":
        for row in doc["occurrences"]:
            for key, side in (("left", "left"), ("right", "right"), ("top", "top")):
                proposal = row["proposal"][key]
                root = ("/Game/Scenes/Wings/FlatV3/Passage04" if
                        str(proposal.get("family_class", "")).upper() == "MYSTICAL" else
                        config["destination_root"])
                register_mesh(root + "/StaticMeshes/" + proposal["asset"], side)
    elif kind == "p06_layout":
        for family in doc["family_catalog"].values():
            if family.get("pair_status") != "true_pair":
                continue
            root = ("/Game/Scenes/Wings/FlatV3/Passage02" if
                    family.get("kind") == "p02_industrial" else
                    config["destination_root"])
            register_mesh(root + "/StaticMeshes/" + family["left_asset"], "left")
            register_mesh(root + "/StaticMeshes/" + family["right_asset"], "right")


def apply_measured_p05_old_edges(guid, records):
    """Make the fake old panels reproduce the released -02 dry-run edges."""
    measured = P05_MEASURED_ROWS.get(guid)
    if measured is None:
        return
    for side in ("left", "right"):
        if side not in measured.get("placement", {}):
            continue
        placement = measured["placement"][side]
        outer = float(placement["old_outer_edge_cm"])
        inner = float(placement["old_inner_edge_cm"])
        width = abs(inner - outer)
        record = records[side]
        record["local_transform"]["location"][1] = outer
        record["local_transform"]["scale"][1] = width
        record["facing_policy"] = "PRESERVE_ASSET"
        record["flip_image_horizontally"] = False
        minimum_y, maximum_y = ((0.0, 1.0) if side == "left" else (-1.0, 0.0))
        fake_unreal.STATE.assets[record["mesh"]] = fake_unreal.StaticMesh(
            record["mesh"], fake_unreal.Vector(-5, minimum_y, 0),
            fake_unreal.Vector(5, maximum_y, 1000))


def install_measured_p05_new_edges():
    widths = {}
    for measured in P05_MEASURED_ROWS.values():
        for side in ("left", "right"):
            if side not in measured.get("placement", {}):
                continue
            placement = measured["placement"][side]
            outer = float(placement["old_outer_edge_cm"])
            inner = float(placement["new_inner_edge_cm"])
            path = measured[side]["mesh"]
            width = abs(inner - outer)
            if path in widths and abs(widths[path] - width) > 0.000001:
                raise AssertionError("measured width drift for " + path)
            widths[path] = width
            minimum_y, maximum_y = ((0.0, width) if side == "left" else (-width, 0.0))
            fake_unreal.STATE.assets[path] = fake_unreal.StaticMesh(
                path, fake_unreal.Vector(-5, minimum_y, 0),
                fake_unreal.Vector(5, maximum_y, 1000))
def reset_for_config(config):
    fake_unreal.STATE = fake_unreal.State()
    passage = config["passage"]
    rows = probe_rows(config)
    mapping = json.loads(Path(config["mapping_file"]).read_text(encoding="utf-8"))
    max_index = max(int(row[0]) for row in rows)
    cues = [fake_unreal.Obj(label="unused", wing_pair=None,
                            cue_guid=fake_unreal.Guid("UNUSED-%03d" % index))
            for index in range(max_index + 1)]
    passage_guid = fake_unreal.Guid(passage + "-PASSAGE-GUID")
    for ordinal, probe_row in enumerate(rows):
        index, label, guid, left_value = probe_row
        left = package_path(left_value)
        top = None
        if passage == "P03":
            layout = mapping["occurrences"][ordinal]
            right = "/Game/Legacy/P03/" + layout["existing"]["R"]
            top_name = layout["existing"].get("C")
            top = None if top_name is None else "/Game/Legacy/P03/" + top_name
        elif passage == "P02":
            layout = mapping["occurrences"][ordinal]
            right = package_path(layout["existing"]["right_mesh"])
            top = "/Game/Legacy/P02/Top_%02d" % (ordinal + 1)
        elif passage == "P01":
            right = p01_right(left)
        elif passage == "P06":
            layout = mapping["occurrences"][ordinal]
            right = "/Game/Scenes/Wings/StageOpeningV2/StaticMeshes/" + \
                    layout["existing"]["R"]
            top = "/Game/Legacy/P06/Top_%02d" % (ordinal + 1)
        else:
            right = left[:-2] + "_R" if left.endswith("_L") else left + "_R"
        records = {"left": panel_record(left, -500),
                   "right": panel_record(right, 500),
                   "top": panel_record(top, 0, True)}
        if passage == "P05":
            apply_measured_p05_old_edges(guid, records)
        for side in ("left", "right", "top"):
            register_mesh(records[side]["mesh"], side)
        pair = fake_unreal.Obj(
            left=fake_unreal.panel_from(records["left"]),
            right=fake_unreal.panel_from(records["right"]),
            top=fake_unreal.panel_from(records["top"]),
            mechanism=fake_unreal.mechanism_from(mechanism_record()),
            occurrence_offset=fake_unreal.plain_transform(
                {"location": [0, 0, 0], "rotation": [0, 0, 0], "scale": [1, 1, 1]}),
            interval_to_next=fake_unreal.FrameNumber(600000))
        cues[int(index)] = fake_unreal.Obj(label=label, wing_pair=pair,
                                           cue_guid=fake_unreal.Guid(guid))
    register_mapping_meshes(config, mapping)
    if passage == "P05":
        install_measured_p05_new_edges()
    library_path = "/Game/Test/WingLibrary"
    fake_unreal.STATE.assets[library_path] = fake_unreal.Obj(entries=[])
    settings = fake_unreal.Obj(passage_guid=passage_guid, lead_in_frames=fake_unreal.FrameNumber(0))
    show = fake_unreal.Show(cues=cues, passage_settings=[settings],
                            tick_resolution=fake_unreal.FrameRate(),
                            wing_library=fake_unreal.Asset(library_path))
    actor = ConfigActor(config["passage_actor_label_prefix"], show_asset=show,
                        passage_guid=passage_guid, materialized_panels=[])
    fake_unreal.STATE.assets[fake_unreal.SHOW] = show
    fake_unreal.STATE.actor = actor
    rebuild_refs(actor)
    fake_unreal.STATE.logs.append(config["required_previous_marker"])
    return fake_unreal.STATE


def rebuild_refs(actor):
    show = actor.get_editor_property("show_asset")
    refs = []
    for cue in show.get_editor_property("cues"):
        if str(cue.get_editor_property("label")) == "unused":
            continue
        pair = cue.get_editor_property("wing_pair")
        for side, inward in (("left", fake_unreal.Vector(0, 1, 0)),
                             ("right", fake_unreal.Vector(0, -1, 0))):
            panel = pair.get_editor_property(side)
            mesh = panel.get_editor_property("mesh")
            if mesh is None:
                continue
            refs.append(fake_unreal.Obj(
                cue_guid=cue.get_editor_property("cue_guid"), side=side.upper(),
                component=fake_unreal.Component(static_mesh=mesh),
                base_world_transform=panel.get_editor_property("local_transform"),
                inward_world_direction=inward))
    actor.props["materialized_panels"] = refs


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def stage_config(source, folder):
    config = json.loads(source.read_text(encoding="utf-8"))
    config["mapping_file"] = str((REPO / config["mapping_file"]).resolve())
    backup = Path(folder) / ("backup_" + config["slot"])
    backup.mkdir()
    for name in config["backup_files"]:
        (backup / name).write_text("offline harness", encoding="utf-8")
    config["backup_path"] = str(backup)
    path = Path(folder) / source.name
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return path, config


def modules(folder, config=None):
    for name in list(sys.modules):
        if name in {"common", "preflight", "dry", "apply", "revert", "verify", "verify_saved"}:
            del sys.modules[name]
    common = load("common", KIT / "common.py")
    preflight = load("preflight", KIT / "preflight.py")
    dry = load("dry", KIT / "dry.py")
    revert = load("revert", KIT / "revert.py")
    apply = load("apply", KIT / "apply.py")
    verify = load("verify", KIT / "verify.py")
    verify_saved = load("verify_saved", KIT / "verify_saved.py")
    all_modules = (common, preflight, dry, revert, apply, verify, verify_saved)
    for module in all_modules:
        if hasattr(module, "c"):
            module.c.BASE = str(folder)
            module.c.log_has = lambda token: any(token in line for line in fake_unreal.STATE.logs)
    apply.revert_module.c.BASE = str(folder)
    verify_saved.verifier.c.BASE = str(folder)
    verify_saved.verifier.c.log_has = lambda token: any(
        token in line for line in fake_unreal.STATE.logs)
    if config is not None and config.get("mapping_kind") == "p06_layout":
        support = load("p06_support_harness", KIT / "p06_support.py")
        for module in all_modules:
            if hasattr(module, "c"):
                support.install(module.c)
        support.install(apply.revert_module.c)
        support.install(verify_saved.verifier.c)
    return all_modules


def record(name, polarity, expected, passed, detail):
    RESULTS.append({"name": name, "polarity": polarity, "expected": expected,
                    "passed": bool(passed), "detail": str(detail)})


def cleanup_census():
    return {
        "content": sorted(fake_unreal.STATE.content_dirty),
        "maps": sorted(fake_unreal.STATE.map_dirty),
    }


def cleanup_fixture_state(paths):
    fake_unreal.STATE = fake_unreal.State()
    for path in paths:
        fake_unreal.STATE.assets[path] = fake_unreal.Asset(path)
        fake_unreal.STATE.content_dirty.add(path)


def case_import_failure_cleanup_controls():
    helper = load("flatv3_import_failure_cleanup_harness", KIT / "import_failure_cleanup.py")
    helper.package_exists_on_disk = lambda path: path in fake_unreal.STATE.disk_packages
    paths = [
        "/Game/Test/StaticMeshes/SM_RunCreated",
        "/Game/Test/Materials/Instances/MI_RunCreated",
        "/Game/Test/Textures/T_RunCreated",
    ]

    fake_unreal.STATE = fake_unreal.State()
    tracker = helper.ImportRunTracker("P02", paths, cleanup_census(), cleanup_census)
    cleanup_fixture_state(paths)
    fake_unreal.STATE.referencers[paths[1]] = {paths[0]}
    fake_unreal.STATE.referencers[paths[2]] = {paths[1]}
    try:
        raise RuntimeError("PLANTED_AFTER_THREE_PACKAGES")
    except RuntimeError:
        result, cleanup_error = helper.cleanup_after_failure(
            "P02", "HARNESS-CLEAN", tracker, cleanup_census)
    expected_order = [paths[0], paths[1], paths[2]]
    passed = (cleanup_error is None and result["status"] == "CLEAN" and
              result["delete_order"] == expected_order and
              fake_unreal.STATE.deleted_assets == expected_order and
              cleanup_census() == {"content": [], "maps": []})
    record("import failure discards exact run set", "+", "clean census", passed,
           "status=%s deleted=%s census=%s" %
           (result["status"], result.get("deleted"), cleanup_census()))

    fake_unreal.STATE = fake_unreal.State()
    tracker = helper.ImportRunTracker("P02", paths, cleanup_census(), cleanup_census)
    cleanup_fixture_state(paths)
    tracker.observe_created()
    fake_unreal.STATE.disk_packages.add(paths[2])
    result, cleanup_error = helper.cleanup_after_failure(
        "P02", "HARNESS-ON-DISK", tracker, cleanup_census)
    passed = (cleanup_error is not None and "CLEANUP_ON_DISK" in str(cleanup_error) and
              paths[2] in fake_unreal.STATE.assets and not fake_unreal.STATE.deleted_assets and
              any("FLATV3_P02_IMPORT_CLEANUP_FAIL" in line and
                  "CLEANUP_ON_DISK" in line for line in fake_unreal.STATE.logs))
    record("cleanup preserves on-disk package", "-", "CLEANUP_ON_DISK", passed,
           "reason=%s deleted=%s remaining=%s" %
           (result.get("reason"), fake_unreal.STATE.deleted_assets, cleanup_census()))

    fake_unreal.STATE = fake_unreal.State()
    tracker = helper.ImportRunTracker("P02", paths, cleanup_census(), cleanup_census)
    cleanup_fixture_state(paths)
    tracker.observe_created()
    outside = "/Game/Existing/OutsideReferencer"
    fake_unreal.STATE.referencers[paths[2]] = {outside}
    result, cleanup_error = helper.cleanup_after_failure(
        "P02", "HARNESS-EXTERNAL-REF", tracker, cleanup_census)
    passed = (cleanup_error is not None and
              "CLEANUP_EXTERNAL_REFERENCER" in str(cleanup_error) and
              outside in str(cleanup_error) and not fake_unreal.STATE.deleted_assets and
              cleanup_census()["content"] == sorted(paths))
    record("cleanup blocks external referencer", "-", "CLEANUP_EXTERNAL_REFERENCER",
           passed, "reason=%s deleted=%s" %
           (result.get("reason"), fake_unreal.STATE.deleted_assets))

    old = load("flatv3_old_import_failure_boundary", HERE / "old_import_failure_boundary.py")
    fake_unreal.STATE = fake_unreal.State()

    def planted_old_import():
        cleanup_fixture_state(paths)
        raise RuntimeError("PLANTED_AFTER_THREE_PACKAGES")

    try:
        old.run(planted_old_import)
    except RuntimeError:
        pass
    old_dirty = cleanup_census()
    record("OLD importer planted failure", "-", "dirty census", old_dirty["content"] == sorted(paths),
           "dirty=%s" % old_dirty)

    required = ("ImportRunTracker", "install_deferred_cleanup", "cleanup_after_failure",
                "cleanup=%s")
    integration = {}
    for name in ("p02_import.py", "p03_import.py", "p06_import.py"):
        source = (KIT / name).read_text(encoding="utf-8")
        integration[name] = [token for token in required if token not in source]
        if name == "p03_import.py" and "P03_ASSET_GATE_FAIL" not in source:
            integration[name].append("P03_ASSET_GATE_FAIL")
    record("all Flat V3 importers use run cleanup", "+", "3 integrated", not any(integration.values()),
           integration)


def placed_side_gate(verifier, label, side, mesh, base, frame):
    bounds = verifier.bounds_in_frame(mesh, base, frame)
    centre_y = (bounds["min"][1] + bounds["max"][1]) * 0.5
    if (side == "left" and centre_y >= -1.0) or (side == "right" and centre_y <= 1.0):
        raise RuntimeError("PLACED_SIDE_BOUNDS_FAIL|label=%s|side=%s|bounds=%s" %
                           (label, side, json.dumps(bounds)))
    return bounds


def old_pair_frame(ref, left_local):
    """The pre-fix derivation, retained only as an explicit negative control."""
    base = ref.get_editor_property("base_world_transform")
    local = fake_unreal.Vector(*left_local)
    scaled = fake_unreal.Vector(local.x * base.scale3d.x, local.y * base.scale3d.y,
                                local.z * base.scale3d.z)
    location = base.translation - base.rotation.rotate_vector(scaled)
    return fake_unreal.Transform(location=location, rotation=base.rotation.rotator(),
                                 scale=base.scale3d)


def pair_frame_fixture():
    fake_unreal.STATE = fake_unreal.State()
    left_path = "/Game/Legacy/P05/SM_CloudRef02_L"
    right_path = "/Game/Scenes/Wings/FlatV3/Passage05/StaticMeshes/SM_FlatV3_P05_CloudRef02_R_R"
    left_mesh = fake_unreal.StaticMesh(
        left_path, fake_unreal.Vector(-50.0, 0.0, -1875.0),
        fake_unreal.Vector(50.0, 1658.75, 1375.0))
    right_mesh = fake_unreal.StaticMesh(
        right_path, fake_unreal.Vector(-5.0, -265.46112060546875, 0.0),
        fake_unreal.Vector(5.0, 0.0, 1000.0))
    fake_unreal.STATE.assets[left_path] = left_mesh
    fake_unreal.STATE.assets[right_path] = right_mesh
    left_record = {
        "mesh": left_path, "material_overrides": [],
        "local_transform": {"location": [-100.0, -250.0, 200.0],
                            "rotation": [0.0, 0.0, 0.0],
                            "scale": [1.0, 0.4, 0.4]},
        "facing_policy": "ROTATE180_AROUND_UP", "flip_image_horizontally": False,
    }
    right_record = {
        "mesh": right_path, "material_overrides": [],
        "local_transform": {"location": [0.0, 382.61065673828114, 0.0],
                            "rotation": [0.0, 0.0, 0.0],
                            "scale": [1.0, 1.0, 1.0]},
        "facing_policy": "PRESERVE_ASSET", "flip_image_horizontally": False,
    }
    pair = fake_unreal.Obj(left=fake_unreal.panel_from(left_record),
                           right=fake_unreal.panel_from(right_record))
    cue = fake_unreal.Obj(cue_guid=fake_unreal.Guid("D9809927C9409586DAE008839DE18EF5"))
    left_ref = fake_unreal.Obj(
        base_world_transform=fake_unreal.Transform(
            location=fake_unreal.Vector(-100.0, -250.0, 200.0),
            rotation=fake_unreal.Rotator(yaw=180.0),
            scale=fake_unreal.Vector(1.0, 0.4, 0.4)))
    right_ref = fake_unreal.Obj(
        base_world_transform=fake_unreal.Transform(
            location=fake_unreal.Vector(0.0, 382.61065673828114, 0.0)))
    row = {"cue_index": 123, "cue_label": "P05 Wing 002",
           "cue_guid": "D9809927C9409586DAE008839DE18EF5",
           "changed_sides": ["right"], "left": left_record, "right": right_record}
    return cue, pair, row, {"left": left_ref, "right": right_ref}, right_mesh


def case_pair_frame_controls(folder):
    *_, verifier, _ = modules(folder)
    cue, pair, row, refs, right_mesh = pair_frame_fixture()
    frame, source = verifier.pair_frame(None, cue, refs, pair, row, {})
    try:
        bounds = placed_side_gate(verifier, row["cue_label"], "right", right_mesh,
                                  refs["right"].get_editor_property("base_world_transform"), frame)
        passed = (source == "changed_right_preserve_identity_local_rotation" and
                  bounds["min"][1] > 1.0)
        record("P05 cue 123 pair frame", "+", "SUCCEED", passed,
               "source=%s bounds=%s" % (source, json.dumps(bounds)))
    except Exception as exc:
        record("P05 cue 123 pair frame", "+", "SUCCEED", False, exc)

    old_frame = old_pair_frame(
        refs["left"], row["left"]["local_transform"]["location"])
    try:
        placed_side_gate(verifier, row["cue_label"], "right", right_mesh,
                         refs["right"].get_editor_property("base_world_transform"), old_frame)
    except RuntimeError as exc:
        record("old P05 pair frame", "-", "PLACED_SIDE_BOUNDS_FAIL",
               "PLACED_SIDE_BOUNDS_FAIL" in str(exc), exc)
    else:
        record("old P05 pair frame", "-", "PLACED_SIDE_BOUNDS_FAIL", False,
               "old derivation unexpectedly accepted")

    bad_refs = dict(refs)
    bad_refs["right"] = fake_unreal.Obj(
        base_world_transform=fake_unreal.Transform(
            location=fake_unreal.Vector(0.0, -382.61065673828114, 0.0)))
    try:
        verifier.pair_frame(None, cue, bad_refs, pair, row, {})
    except RuntimeError as exc:
        record("genuine negative-Y right panel", "-", "FAIL",
               "PAIR_FRAME_REF_DISAGREEMENT" in str(exc), exc)
    else:
        record("genuine negative-Y right panel", "-", "FAIL", False,
               "misplaced right panel unexpectedly accepted")


def run_positive(config_path, config, folder):
    common, preflight, dry, revert, apply, verify, verify_saved = modules(folder, config)
    reset_for_config(config)
    preflight.c.BASE = dry.c.BASE = apply.c.BASE = revert.c.BASE = verify.c.BASE = str(folder)
    preflight.c.log_has = lambda token: any(token in line for line in fake_unreal.STATE.logs)
    preflight.run(str(config_path))
    plan = dry.run(str(config_path))
    if config["passage"] == "P05":
        expected_edges = {
            (entry["cue_guid"], entry["side"]):
            (round(float(entry["old_inner_edge_cm"]), 6),
             round(float(entry["new_inner_edge_cm"]), 6))
            for entry in P05_MEASURED_DOC["overreach_flags"]
        }
        actual_edges = {
            (row["cue_guid"], side):
            (round(float(row["placement"][side]["old_inner_edge_cm"]), 6),
             round(float(row["placement"][side]["new_inner_edge_cm"]), 6))
            for row in plan["rows"] for side in ("left", "right")
            if side in row.get("placement", {})
        }
        if any(actual_edges.get(key) != value for key, value in expected_edges.items()):
            raise AssertionError("P05 measured overreach edges drifted")
    applied = apply.run(str(config_path))
    fake_unreal.STATE.logs.append(config["verify_token"])
    verify.c.log_has = lambda token: any(token in line for line in fake_unreal.STATE.logs)
    checked = verify.run_verify(str(config_path), config["run_id"], config["run_id"], True, True)
    capture_label = config.get("capture_label")
    if capture_label:
        matches = sorted(row for row in probe_rows(config) if row[1] == capture_label)
        if not matches:
            raise AssertionError("configured capture label absent from probe")
        expected = matches[0]
        capture = checked["capture_plan"]
        if (capture["target_index"], capture["target_guid"], capture["target_label"]) != \
                (expected[0], expected[2], expected[1]):
            raise AssertionError("capture did not select first occurrence: " + repr(capture))
    verify_saved.c.BASE = verify_saved.verifier.c.BASE = str(folder)
    verify_saved.verifier.c.log_has = verify.c.log_has
    saved = verify_saved.main(str(config_path))
    if config["passage"] == "P06":
        originals_doc = common.read_json(config, "preflight")
        show = fake_unreal.STATE.assets[common.SHOW]
        cues = list(show.get_editor_property("cues"))
        untouched = originals_doc["rows"][32:]
        if len(untouched) != 23:
            raise AssertionError("P06 untouched source slice was not 23 rows")
        for original in untouched:
            pair = cues[original["cue_index"]].get_editor_property("wing_pair")
            for side in ("left", "right", "top"):
                if common.panel_plain(pair.get_editor_property(side)) != original[side]:
                    raise AssertionError("P06 untouched panel changed: %s %s" %
                                         (original["cue_label"], side))
    roots = revert.revert("offline_control", str(config_path))
    if roots != sorted([common.SHOW, common.WORLD]):
        raise AssertionError("wrong revert roots: " + repr(roots))
    if common.census() != common.CLEAN:
        raise AssertionError("revert left dirty packages")
    if config["passage"] == "P06":
        if len(common.read_json(config, "preflight")["rows"]) != 55:
            raise AssertionError("P06 preflight did not retain 55 occurrences")
        if len(plan["rows"]) != 32:
            raise AssertionError("P06 did not plan exactly 32 swaps")
        if 55 - len(plan["rows"]) != 23:
            raise AssertionError("P06 did not leave exactly 23 untouched")
    return ("rows=%d excluded_kept=%d applied=%d movement=%d saved_verify=%d "
            "unexplained=%d within_tolerance=%d kept_old_sides=%d") % (
        len(plan["rows"]), len(plan["excluded_rows_kept_old"]), applied["rows"],
        checked["movement_sample_count"], saved["rows"],
        len(plan.get("unexplained_overreach_flags", [])),
        len(plan.get("within_tolerance_overreach_flags", [])),
        len(plan.get("kept_old_sides", [])))


def case_positive(name, config_path, config, folder):
    try:
        detail = run_positive(config_path, config, folder)
        record(name, "+", "SUCCEED", True, detail)
    except Exception as exc:
        record(name, "+", "SUCCEED", False, "%s: %s" % (type(exc).__name__, exc))


def case_cloud_exclusion(config_path, config, folder):
    bad = dict(config)
    bad["excluded_new_meshes"] = []
    path = Path(folder) / "bad_cloud.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    common, *_ = modules(folder)
    try:
        common.load_config(str(path))
    except RuntimeError as exc:
        record("CloudRef02 included", "-", "FAIL", "KNOWN_FAILED_ASSET_INCLUDED" in str(exc), exc)
        return
    record("CloudRef02 included", "-", "FAIL", False, "unexpectedly accepted")


def case_zero_overreach_tolerance(config, folder):
    bad = json.loads(json.dumps(config))
    bad["run_id"] += "-ZERO-TOLERANCE"
    bad["saved_verify_run_id"] += "-ZERO-TOLERANCE"
    bad["overreach_tolerance_cm"] = 0
    bad["keep_old_sides"] = []
    path = Path(folder) / "p05_zero_tolerance.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    _, preflight, dry, *_ = modules(folder)
    reset_for_config(bad)
    preflight.c.log_has = lambda token: any(token in line for line in fake_unreal.STATE.logs)
    preflight.run(str(path))
    try:
        dry.run(str(path))
    except RuntimeError as exc:
        record("P05 zero overreach tolerance", "-", "FAIL with 13",
               "UNEXPLAINED_OVERREACH_FLAGS|count=13" in str(exc), exc)
        return
    record("P05 zero overreach tolerance", "-", "FAIL with 13", False,
           "unexpectedly accepted")


def case_unknown_keep_old_guid(config, folder):
    bad = json.loads(json.dumps(config))
    bad["run_id"] += "-UNKNOWN-KEEP"
    bad["saved_verify_run_id"] += "-UNKNOWN-KEEP"
    bad["keep_old_sides"] = [{"cue_guid": "00000000000000000000000000000000",
                              "side": "right", "reason": "offline negative control"}]
    path = Path(folder) / "p05_unknown_keep.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    _, preflight, *_ = modules(folder)
    reset_for_config(bad)
    preflight.c.log_has = lambda token: any(token in line for line in fake_unreal.STATE.logs)
    try:
        preflight.run(str(path))
    except RuntimeError as exc:
        record("unknown keep-old GUID", "-", "FAIL",
               "UNKNOWN_KEEP_OLD_GUID" in str(exc), exc)
        return
    record("unknown keep-old GUID", "-", "FAIL", False, "unexpectedly accepted")


def case_verify_kept_old_mutation(config_path, config, folder):
    common, preflight, dry, _, apply, verify, _ = modules(folder)
    reset_for_config(config)
    for module in (preflight, dry, apply, verify):
        module.c.BASE = str(folder)
    preflight.c.log_has = lambda token: any(token in line for line in fake_unreal.STATE.logs)
    preflight.run(str(config_path))
    plan = dry.run(str(config_path))
    apply.run(str(config_path))
    kept = plan["kept_old_sides"][0]
    cue = fake_unreal.STATE.assets[common.SHOW].get_editor_property("cues")[kept["cue_index"]]
    panel = cue.get_editor_property("wing_pair").get_editor_property(kept["side"])
    panel.props["flip_image_horizontally"] = not panel.props["flip_image_horizontally"]
    fake_unreal.STATE.logs.append(config["verify_token"])
    verify.c.log_has = lambda token: any(token in line for line in fake_unreal.STATE.logs)
    try:
        verify.run_verify(str(config_path), require_token=True)
    except RuntimeError as exc:
        record("verify kept-old mutation detector", "+", "DETECT FAIL", 
               "VERIFY_KEPT_OLD_SIDE_CHANGED" in str(exc), exc)
        return
    record("verify kept-old mutation detector", "+", "DETECT FAIL", False,
           "altered kept-old side unexpectedly accepted")


def case_verify_token(config_path, config, folder):
    common, preflight, dry, revert, apply, verify, _ = modules(folder)
    reset_for_config(config)
    for module in (preflight, dry, revert, apply, verify):
        module.c.BASE = str(folder)
    preflight.c.log_has = lambda token: any(token in line for line in fake_unreal.STATE.logs)
    preflight.run(str(config_path)); dry.run(str(config_path)); apply.run(str(config_path))
    verify.c.log_has = lambda token: False
    try:
        verify.run_verify(str(config_path), require_token=True)
    except RuntimeError as exc:
        record("verify token absent", "-", "FAIL", "VERIFY_TOKEN_NOT_FOUND" in str(exc), exc)
        return
    record("verify token absent", "-", "FAIL", False, "unexpectedly accepted")


def case_none_top(config_path, config, folder):
    common, preflight, dry, revert, apply, *_ = modules(folder)
    reset_for_config(config)
    for module in (preflight, dry, revert, apply):
        module.c.BASE = str(folder)
    preflight.c.log_has = lambda token: any(token in line for line in fake_unreal.STATE.logs)
    preflight.run(str(config_path)); dry.run(str(config_path)); apply.run(str(config_path))
    revert.revert("none_top_control", str(config_path))
    show = fake_unreal.STATE.assets[common.SHOW]
    tops = [cue.get_editor_property("wing_pair").get_editor_property("top")
            .get_editor_property("mesh") for cue in show.get_editor_property("cues")
            if str(cue.get_editor_property("label")).startswith(
                config["passage_label_prefix"])]
    record("revert with None tops", "+", "SUCCEED", any(value is None for value in tops),
           "None tops preserved without passing None to the asset loader")


def case_prefix_mismatch(config, folder):
    bad = dict(config)
    bad["passage_label_prefix"] = config["passage"] + " Wing WRONG "
    path = Path(folder) / "bad_prefix.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    _, preflight, *_ = modules(folder)
    reset_for_config(config)
    preflight.c.BASE = str(folder)
    preflight.c.log_has = lambda token: any(token in line for line in fake_unreal.STATE.logs)
    try:
        preflight.run(str(path))
    except RuntimeError as exc:
        record("wrong passage prefix", "-", "FAIL",
               "PASSAGE_IDENTITY_GATE_FAIL" in str(exc), exc)
        return
    record("wrong passage prefix", "-", "FAIL", False, "unexpectedly accepted")


def case_old_unique_label_gate(config):
    labels = [row[1] for row in probe_rows(config)]
    failed = len(labels) != len(set(labels))
    record("old unique-label preflight on real P05", "-", "FAIL", failed,
           "DUPLICATE_PASSAGE_LABEL" if failed else "unexpectedly accepted")


def case_duplicate_guid(config_path, config, folder):
    _, preflight, *_ = modules(folder)
    reset_for_config(config)
    targets = [cue for cue in fake_unreal.STATE.assets[fake_unreal.SHOW]
               .get_editor_property("cues")
               if str(cue.get_editor_property("label")).startswith(
                   config["passage_label_prefix"])]
    targets[1].props["cue_guid"] = targets[0].get_editor_property("cue_guid")
    preflight.c.BASE = str(folder)
    preflight.c.log_has = lambda token: any(token in line for line in fake_unreal.STATE.logs)
    try:
        preflight.run(str(config_path))
    except RuntimeError as exc:
        record("duplicated occurrence GUID", "-", "FAIL",
               "DUPLICATE_PASSAGE_GUID" in str(exc), exc)
        return
    record("duplicated occurrence GUID", "-", "FAIL", False, "unexpectedly accepted")


def case_missing_capture_label(config_path, config, folder):
    bad = dict(config)
    bad["capture_label"] = config["passage"] + " Wing 999"
    bad["run_id"] = config["run_id"] + "-MISSING-CAPTURE"
    bad["saved_verify_run_id"] = bad["run_id"] + "-VERIFY"
    path = Path(folder) / (config["passage"].lower() + "_missing_capture.json")
    path.write_text(json.dumps(bad), encoding="utf-8")
    _, preflight, dry, _, apply, verify, _ = modules(folder)
    reset_for_config(bad)
    preflight.run(str(path)); dry.run(str(path)); apply.run(str(path))
    fake_unreal.STATE.logs.append(bad["verify_token"])
    verify.c.log_has = lambda token: any(token in line for line in fake_unreal.STATE.logs)
    try:
        verify.run_verify(str(path), require_token=True)
    except RuntimeError as exc:
        record("missing capture label", "-", "FAIL",
               "CAPTURE_LABEL_NOT_PLANNED" in str(exc), exc)
        return
    record("missing capture label", "-", "FAIL", False, "unexpectedly accepted")


def case_static_tokens():
    hits = {}
    for path in (KIT / "verify.py", KIT / "verify_saved.py"):
        source = path.read_text(encoding="utf-8")
        hits[path.name] = [token for token in FORBIDDEN if token in source]
    record("read-only verify tokens", "+", "SUCCEED", not any(hits.values()), hits)


def case_p03_import_sources():
    tools = REPO / "Tools" / "FlatV3"
    sys.path.insert(0, str(tools))
    import socket_contract
    root = REPO / "DerivedAssets" / "FlatV3" / "Overnight" / "P03" / "flats"
    failures = []
    count = 0
    built_assets = set()
    for folder in sorted(path for path in root.iterdir() if path.is_dir()):
        status_path = folder / "status.json"
        if not status_path.is_file():
            continue
        status = json.loads(status_path.read_text(encoding="utf-8"))
        if status.get("passage") != "P03":
            continue
        count += 1
        built_assets.add(status["asset_name"])
        validation = json.loads((folder / "validation.json").read_text(encoding="utf-8"))
        manifest_path = Path(status["build_manifest"])
        if not manifest_path.is_file():
            matches = sorted(folder.glob("*_build.json"))
            manifest_path = matches[0] if len(matches) == 1 else Path("missing")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected = socket_contract.make_socket_payload(
            asset=status["asset_name"], side=status["build_side"], mount=status["mount"],
            height_cm=status["height_cm"], width_m=manifest["dimensions_m"]["width"],
            pole_positions_y_m=socket_contract.as_pole_list(manifest.get("pole_positions_y_m")))
        payload = socket_contract.load_json(folder / ("sockets_" + status["asset_name"] + ".json"))
        socket_failures = socket_contract.validate_socket_payload(payload, expected)
        lod = validation.get("checks", {}).get("fbx_lod_group", {})
        if (status.get("status") != "built" or not status.get("validation_pass") or
                not validation.get("pass") or not lod.get("pass") or
                lod.get("mechanism") != "FBX LodGroup NodeAttribute" or socket_failures):
            failures.append({"asset": status["asset_name"], "sockets": socket_failures})
    layout = json.loads((REPO / "DerivedAssets" / "FlatV3" / "Overnight" /
                         "P03_LAYOUT_DRAFT.json").read_text(encoding="utf-8"))
    mapped_assets = {row["asset"] for row in layout["family_catalog"].values()}
    mapping_match = mapped_assets == built_assets
    record("P03 import sources", "+", "11 gated", count == 11 and not failures and mapping_match,
           "count=%d failures=%s layout_matches=%s" % (count, failures, mapping_match))


def case_p02_import_sources():
    root = REPO / "DerivedAssets" / "FlatV3" / "Overnight"
    flats = root / "P02Sets" / "flats"
    passing = []
    rejected = []
    for folder in sorted(path for path in flats.iterdir() if path.is_dir()):
        validation_path = folder / "validation.json"
        status_path = folder / "status.json"
        if not validation_path.is_file() or not status_path.is_file():
            continue
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        status = json.loads(status_path.read_text(encoding="utf-8"))
        (passing if validation.get("pass") else rejected).append(status["asset_name"])
    industrial_root = root / "P02Industrial"
    industrial = json.loads((industrial_root / "validation.json").read_text(encoding="utf-8"))
    industrial_fbx = sorted(industrial_root.glob("SM_FlatV3_P02_IND_*.fbx"))
    layout = json.loads((root / "P02_LAYOUT_DRAFT_v2.json").read_text(encoding="utf-8"))
    sequence = [row["sequence_order"] for row in layout["occurrences"]]
    mystical = {proposal["asset"] for row in layout["occurrences"]
                for proposal in (row["proposal"]["left"], row["proposal"]["right"])
                if str(proposal.get("family_class", "")).upper() == "MYSTICAL"}
    expected_mystical = {"SM_FlatV3_P04_coventry_ruin_L_v1",
                         "SM_FlatV3_P04_coventry_ruin_R_v1",
                         "SM_FlatV3_P04_ruined_gallery_L_v1",
                         "SM_FlatV3_P04_ruined_gallery_R_v1",
                         "SM_FlatV3_P04_coventry_ruin_L_v2"}
    passing_set = set(passing)
    rejected_set = set(rejected)
    industrial_names = {path.stem for path in industrial_fbx}
    coverage_failures = []
    used_industrial = set()
    for row in layout["occurrences"]:
        for key in ("left", "right", "top"):
            proposal = row["proposal"][key]
            asset = proposal["asset"]
            family_class = str(proposal.get("family_class", "")).upper()
            if family_class == "MYSTICAL":
                continue
            if family_class == "INDUSTRIAL":
                used_industrial.add(asset)
                if asset not in industrial_names:
                    coverage_failures.append(asset)
            elif asset not in passing_set | rejected_set:
                coverage_failures.append(asset)
    unused_industrial = industrial_names - used_industrial
    passed = (len(passing) + len(rejected) == 24 and
              industrial.get("all_pass") and len(industrial_fbx) == 8 and
              sequence == list(range(1, 24)) and mystical == expected_mystical and
              not coverage_failures and
              unused_industrial == {"SM_FlatV3_P02_IND_DuctVent_L",
                                    "SM_FlatV3_P02_IND_DuctVent_R"})
    record("P02 import/layout sources", "+", "passing-only + 8 / 23 positions", passed,
           "plant_pass=%d plant_reject=%d industrial=%d sequence=%d mystical=%d" %
           (len(passing), len(rejected), len(industrial_fbx), len(sequence), len(mystical)))


def case_p02_industrial_socket_admission():
    """Exercise the real P02 industrial admission gate without Unreal."""
    try:
        module = load("p02_import_socket_admission", KIT / "p02_import.py")
        module.PROJECT = str(REPO)
        module.c._project_path = lambda value: str(REPO / value)

        class SlotA:
            @staticmethod
            def load_json(path):
                return json.loads(Path(path).read_text(encoding="utf-8"))

        config = json.loads((KIT / "run_p02.json").read_text(encoding="utf-8"))
        rows = module.industrial_inventory(config, SlotA)
        counts = {row["mesh_name"]: row["socket_count"] for row in rows}
        expected = {
            "SM_FlatV3_P02_IND_FenceTarp_L": 6,
            "SM_FlatV3_P02_IND_FenceTarp_R": 6,
            "SM_FlatV3_P02_IND_FenceOpen_L": 6,
            "SM_FlatV3_P02_IND_FenceOpen_R": 6,
            "SM_FlatV3_P02_IND_RollerShutter_L": 4,
            "SM_FlatV3_P02_IND_RollerShutter_R": 4,
            "SM_FlatV3_P02_IND_DuctVent_L": 4,
            "SM_FlatV3_P02_IND_DuctVent_R": 4,
        }
        record("P02 industrial socket admission", "+", "8 contract sidecars", counts == expected,
               json.dumps(counts, sort_keys=True))
    except Exception as exc:
        record("P02 industrial socket admission", "+", "8 contract sidecars", False, exc)


def case_p06_contract(config, folder):
    support = load("p06_support_contract", KIT / "p06_support.py")
    common, *_ = modules(folder)
    support.install(common)
    mapping = common.load_mapping(config)
    dump = json.loads(ROWS_DUMP.read_text(encoding="utf-8"))
    readback = [row for row in dump["rows"] if row.get("passage") == 6]
    indices = [int(row["index"]) for row in readback]
    ordinals = [int(row["ordinal"]) for row in readback]
    labels = [str(row["label"]) for row in readback]
    unique = (indices == list(range(217, 272)) and
              ordinals == list(range(1, 56)) and
              labels == ["P06 Wing %03d" % value for value in range(1, 56)] and
              len(indices) == len(set(indices)) and len(labels) == len(set(labels)))
    counts = (len(readback) == 55 and mapping["swap_count"] == 32 and
              mapping["keep_count"] == 23 and unique)
    record("P06 55 / 32 / 23 + identity", "+", "55 total; 32 swap; 23 keep",
           counts, "indices=217..271 labels_unique=%s duplicates=%d" %
           (unique, len(labels) - len(set(labels))))

    swapped = [row for row in mapping["occurrences"] if row["action"] == "swap"]
    matched = all(row["left_family"] == row["right_family"] and
                  mapping["families"][row["left_family"]]["pair_status"] == "true_pair"
                  for row in swapped)
    record("P06 matched L/R family", "+", "all 32 matched", matched,
           "matched=%d" % sum(row["left_family"] == row["right_family"]
                               for row in swapped))

    source = json.loads(Path(config["mapping_file"]).read_text(encoding="utf-8"))
    mixed = json.loads(json.dumps(source))
    mixed["occurrences"][0]["right_family"] = "chinoiserie_garden"
    bad_mixed = dict(config)
    bad_mixed_path = Path(folder) / "p06_mixed_family.json"
    bad_mixed_path.write_text(json.dumps(mixed), encoding="utf-8")
    bad_mixed["mapping_file"] = str(bad_mixed_path)
    try:
        common.load_mapping(bad_mixed)
    except RuntimeError as exc:
        record("P06 mixed-family position", "-", "FAIL",
               "P06_MIXED_FAMILY_POSITION" in str(exc), exc)
    else:
        record("P06 mixed-family position", "-", "FAIL", False, "unexpectedly accepted")

    l_only = json.loads(json.dumps(source))
    l_only["occurrences"][0]["left_family"] = "girder_broken"
    l_only["occurrences"][0]["right_family"] = "girder_broken"
    bad_l_only = dict(config)
    bad_l_only_path = Path(folder) / "p06_l_only_family.json"
    bad_l_only_path.write_text(json.dumps(l_only), encoding="utf-8")
    bad_l_only["mapping_file"] = str(bad_l_only_path)
    try:
        common.load_mapping(bad_l_only)
    except RuntimeError as exc:
        record("P06 L-only family placement", "-", "FAIL",
               "P06_FAMILY_NOT_TRUE_PAIR" in str(exc), exc)
    else:
        record("P06 L-only family placement", "-", "FAIL", False,
               "unexpectedly accepted")


def case_p06_import_sources():
    layout = json.loads((KIT / "p06_layout.json").read_text(encoding="utf-8"))
    used_names = {row["left_family"] for row in layout["occurrences"]
                  if row.get("action") == "swap"}
    used = {name: layout["family_catalog"][name] for name in used_names}
    missing = []
    invalid = []
    selected = set()
    for name, family in used.items():
        if family.get("pair_status") != "true_pair":
            invalid.append(name + ":not_true_pair")
        for side in ("left", "right"):
            selected.add(family[side + "_asset"])
            source = REPO / family[side + "_source"]
            if not source.is_file():
                missing.append(str(source))
            if family["kind"] == "p06_flat":
                status = json.loads((source.parent / "status.json").read_text(encoding="utf-8"))
                validation = json.loads((source.parent / "validation.json").read_text(
                    encoding="utf-8"))
                if (status.get("status") != "built" or not status.get("validation_pass") or
                        not validation.get("pass")):
                    invalid.append(family[side + "_asset"] + ":flat_gate")
    industrial_validation = json.loads((REPO / "DerivedAssets" / "FlatV3" /
        "Overnight" / "P02Industrial" / "validation.json").read_text(encoding="utf-8"))
    industrial_by_name = {row["asset"]: row for row in industrial_validation["assets"]}
    for family in used.values():
        if family["kind"] != "p02_industrial":
            continue
        for side in ("left_asset", "right_asset"):
            if not industrial_by_name.get(family[side], {}).get("pass"):
                invalid.append(family[side] + ":industrial_gate")
    l_only_used = sorted(name for name in used_names
                         if layout["family_catalog"][name]["pair_status"] != "true_pair")
    passed = len(selected) == 12 and not missing and not invalid and not l_only_used
    record("P06 import source closure", "+", "6 P06 + 6 industrial only", passed,
           "selected=%d missing=%d invalid=%d l_only_used=%s" %
           (len(selected), len(missing), len(invalid), l_only_used))


def case_inner_shift_controls(folder):
    """Measured and planted controls for Gary's 2 Oct offstage-only rule."""
    modules(folder)
    shift = load("shift_common_offline", KIT / "shift_common.py")
    p02 = json.loads((KIT / "swapkit_dry_run_FV3P02-20261002-02.json")
                     .read_text(encoding="utf-8"))
    wing002 = next(row for row in p02["rows"] if row["cue_label"] == "P02 Wing 002")
    after = {}
    for side in ("left", "right"):
        placement = wing002["placement"][side]
        current = float(placement["new_inner_edge_cm"])
        old = float(placement["old_inner_edge_cm"])
        after[side] = current + shift.offstage_delta(side, current, old)
    gap = after["right"] - after["left"]
    record("P02 Wing 002 restored centre gap", "+", "662 +/- 1 cm",
           abs(gap - 662.0) <= 1.0, "gap_cm=%.6f" % gap)

    shift_config = json.loads((KIT / "run_shift_p02.json").read_text(encoding="utf-8"))
    kept = next(row for row in p02["rows"] if row["cue_label"] == "P02 Wing 003")
    candidates = shift.candidate_sides(shift_config, kept)
    record("inner shift excludes kept-old side", "-", "no candidate side",
           candidates == [], "candidates=%s" % candidates)

    failures = []
    for side, delta in (("left", 1.0), ("right", -1.0)):
        try:
            shift.validate_offstage_delta(side, delta)
        except RuntimeError as exc:
            failures.append("SHIFT_ONSTAGE_DELTA_FAIL" in str(exc))
        else:
            failures.append(False)
    record("onstage shift variant", "-", "FAIL", all(failures),
           "left_positive=%s right_negative=%s" % tuple(failures))

    placement = wing002["placement"]["left"]
    new_inner = float(placement["new_inner_edge_cm"])
    old_inner = float(placement["old_inner_edge_cm"])
    old_flag = shift.old_centreline_flag("left", new_inner, old_inner)
    new_flag = shift.new_overreach_flag("left", new_inner, old_inner, 2.0)
    record("dry gate catches Wing 002 overreach", "-", "old false; new true",
           not old_flag and new_flag,
           "old_flag=%s new_flag=%s overreach_cm=%.6f" %
           (old_flag, new_flag, shift.overreach_cm("left", new_inner, old_inner)))

    for passage, plan_name, config_name, expected_current, expected_old in (
            ("P02", "swapkit_dry_run_FV3P02-20261002-02.json",
             "run_shift_p02.json", 48.6671752929684, 662.332885742188),
            ("P03", "swapkit_dry_run_FV3P03-20261002-01.json",
             "run_shift_p03.json", None, None),
            ("P04", "../slot_b_dry_run_FV3B-20261002-03.json",
             "run_shift_p04.json", 114.908966064453, 736.425018310547)):
        source = json.loads((KIT / plan_name).resolve().read_text(encoding="utf-8"))
        config = json.loads((KIT / config_name).read_text(encoding="utf-8"))
        current_rows = []
        shifted_rows = []
        for source_row in source["rows"]:
            candidates = shift.candidate_sides(config, source_row)
            if not candidates:
                continue
            old_inner = {}
            current_inner = {}
            for side in ("left", "right"):
                placement = source_row.get("placement", {}).get(side)
                if placement is not None:
                    old_inner[side] = float(placement["old_inner_edge_cm"])
                    current_inner[side] = float(placement["new_inner_edge_cm"])
            # P03 has one changed-side occurrence. Its untouched legacy pair mate
            # is symmetric in this offline fixture and remains at the old edge.
            if len(old_inner) == 1:
                present = next(iter(old_inner))
                missing = "right" if present == "left" else "left"
                old_inner[missing] = -old_inner[present]
                current_inner[missing] = old_inner[missing]
            if set(old_inner) != {"left", "right"}:
                raise AssertionError("gap fixture lacks both sides: " + source_row["cue_label"])
            shifted_sides = [side for side in candidates
                             if shift.overreach_cm(
                                 side, current_inner[side], old_inner[side]) > 0.000001]
            if not shifted_sides:
                continue
            after_inner = dict(current_inner)
            for side in shifted_sides:
                after_inner[side] += shift.offstage_delta(
                    side, current_inner[side], old_inner[side])
            base = {"cue_index": int(source_row["cue_index"]),
                    "cue_guid": str(source_row["cue_guid"]),
                    "cue_label": source_row["cue_label"],
                    "shifted_sides": shifted_sides,
                    "gap_old_cm": shift.centre_gap_cm(
                        old_inner["left"], old_inner["right"])}
            current_rows.append(dict(base, gap_new_cm=shift.centre_gap_cm(
                current_inner["left"], current_inner["right"])))
            shifted_rows.append(dict(base, gap_new_cm=shift.centre_gap_cm(
                after_inner["left"], after_inner["right"])))

        current_min = min(current_rows, key=lambda row: row["gap_new_cm"])
        after = shift.minimum_gap_gate(shifted_rows, 2.0, passage)
        GAP_TABLE.append({"passage": passage,
                          "min_old": float(current_min["gap_old_cm"]),
                          "min_current": float(current_min["gap_new_cm"]),
                          "min_after_shift": float(after["min_gap_new_cm"])})
        if expected_current is not None:
            try:
                shift.minimum_gap_gate(current_rows, 2.0, passage)
            except RuntimeError as exc:
                failed_as_expected = "SHIFT_MIN_GAP_FAIL" in str(exc)
            else:
                failed_as_expected = False
            record("%s current minimum-gap gate" % passage, "-", "FAIL",
                   failed_as_expected and
                   abs(current_min["gap_new_cm"] - expected_current) < 0.001 and
                   abs(current_min["gap_old_cm"] - expected_old) < 0.001,
                   "min_old=%.6f min_current=%.6f label=%s" %
                   (current_min["gap_old_cm"], current_min["gap_new_cm"],
                    current_min["cue_label"]))
            record("%s shifted minimum-gap gate" % passage, "+", "PASS",
                   after["min_gap_new_cm"] >= after["min_gap_old_cm"] - 2.0,
                   "min_old=%.6f min_after=%.6f rows=%d" %
                   (after["min_gap_old_cm"], after["min_gap_new_cm"],
                    after["row_count"]))


def print_table():
    headers = ("Test", "+/-", "Expected", "Harness", "Detail")
    rows = [headers] + [(row["name"], row["polarity"], row["expected"],
                        "PASS" if row["passed"] else "FAIL", row["detail"])
                       for row in RESULTS]
    widths = [max(len(str(row[index])) for row in rows) for index in range(len(headers))]
    for number, row in enumerate(rows):
        print(" | ".join(str(value).ljust(widths[index]) for index, value in enumerate(row)))
        if number == 0:
            print("-+-".join("-" * width for width in widths))


def print_gap_table():
    headers = ("Passage", "Min old (cm)", "Min current (cm)", "Min after shift (cm)")
    rows = [headers] + [(row["passage"], "%.3f" % row["min_old"],
                        "%.3f" % row["min_current"],
                        "%.3f" % row["min_after_shift"]) for row in GAP_TABLE]
    widths = [max(len(str(row[index])) for row in rows) for index in range(len(headers))]
    print("\nGAP TABLE")
    for number, row in enumerate(rows):
        print(" | ".join(str(value).ljust(widths[index]) for index, value in enumerate(row)))
        if number == 0:
            print("-+-".join("-" * width for width in widths))


def main():
    with tempfile.TemporaryDirectory(prefix="flatv3_swapkit_offline_") as folder_name:
        folder = Path(folder_name)
        configs = []
        for name in ("run_c_p05.json", "run_d_p01.json", "run_p03.json", "run_p02.json",
                     "run_p06.json"):
            configs.append(stage_config(KIT / name, folder))
        for path, config in configs:
            case_positive("swapkit " + config["passage"], path, config, folder)
        case_pair_frame_controls(folder)
        case_zero_overreach_tolerance(configs[0][1], folder)
        case_unknown_keep_old_guid(configs[0][1], folder)
        case_verify_kept_old_mutation(*configs[0], folder)
        case_cloud_exclusion(*configs[0], folder)
        case_verify_token(*configs[1], folder)
        case_none_top(*configs[0], folder)
        case_prefix_mismatch(configs[2][1], folder)
        case_old_unique_label_gate(configs[0][1])
        case_duplicate_guid(*configs[0], folder)
        case_missing_capture_label(*configs[0], folder)
        case_static_tokens()
        case_import_failure_cleanup_controls()
        case_p03_import_sources()
        case_p02_import_sources()
        case_p02_industrial_socket_admission()
        case_p06_contract(configs[4][1], folder)
        case_p06_import_sources()
        case_inner_shift_controls(folder)
    print_table()
    print_gap_table()
    failed = [row for row in RESULTS if not row["passed"]]
    print("\nOVERALL: %s (%d/%d harness assertions passed)" %
          ("PASS" if not failed else "FAIL", len(RESULTS) - len(failed), len(RESULTS)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
