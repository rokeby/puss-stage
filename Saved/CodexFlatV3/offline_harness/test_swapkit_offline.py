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
sys.path.insert(0, str(HERE))
import fake_unreal
sys.modules["unreal"] = fake_unreal

RESULTS = []
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
        else:
            right = left[:-2] + "_R" if left.endswith("_L") else left + "_R"
        records = {"left": panel_record(left, -500),
                   "right": panel_record(right, 500),
                   "top": panel_record(top, 0, True)}
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


def modules(folder):
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
    return all_modules


def record(name, polarity, expected, passed, detail):
    RESULTS.append({"name": name, "polarity": polarity, "expected": expected,
                    "passed": bool(passed), "detail": str(detail)})


def run_positive(config_path, config, folder):
    common, preflight, dry, revert, apply, verify, verify_saved = modules(folder)
    reset_for_config(config)
    preflight.c.BASE = dry.c.BASE = apply.c.BASE = revert.c.BASE = verify.c.BASE = str(folder)
    preflight.c.log_has = lambda token: any(token in line for line in fake_unreal.STATE.logs)
    preflight.run(str(config_path))
    plan = dry.run(str(config_path))
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
    roots = revert.revert("offline_control", str(config_path))
    if roots != sorted([common.SHOW, common.WORLD]):
        raise AssertionError("wrong revert roots: " + repr(roots))
    if common.census() != common.CLEAN:
        raise AssertionError("revert left dirty packages")
    return "rows=%d excluded_kept=%d applied=%d movement=%d saved_verify=%d" % (
        len(plan["rows"]), len(plan["excluded_rows_kept_old"]), applied["rows"],
        checked["movement_sample_count"], saved["rows"])


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


def main():
    with tempfile.TemporaryDirectory(prefix="flatv3_swapkit_offline_") as folder_name:
        folder = Path(folder_name)
        configs = []
        for name in ("run_c_p05.json", "run_d_p01.json", "run_p03.json", "run_p02.json"):
            configs.append(stage_config(KIT / name, folder))
        for path, config in configs:
            case_positive("swapkit " + config["passage"], path, config, folder)
        case_cloud_exclusion(*configs[0], folder)
        case_verify_token(*configs[1], folder)
        case_none_top(*configs[0], folder)
        case_prefix_mismatch(configs[2][1], folder)
        case_old_unique_label_gate(configs[0][1])
        case_duplicate_guid(*configs[0], folder)
        case_missing_capture_label(*configs[0], folder)
        case_static_tokens()
        case_p03_import_sources()
        case_p02_import_sources()
    print_table()
    failed = [row for row in RESULTS if not row["passed"]]
    print("\nOVERALL: %s (%d/%d harness assertions passed)" %
          ("PASS" if not failed else "FAIL", len(RESULTS) - len(failed), len(RESULTS)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
