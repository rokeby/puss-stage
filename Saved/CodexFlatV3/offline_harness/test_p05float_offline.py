"""Offline controls for the real P05 FLOAT scripts.  No editor or network use."""
import copy
import hashlib
import importlib
import json
import random
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
KIT = REPO / "Saved" / "CodexFlatV3" / "swapkit"
PROBE = REPO / "Saved" / "CodexFlatV3" / "probe_c2_world_out.json"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(KIT))
import fake_unreal
sys.modules["unreal"] = fake_unreal

import p05float_support as support
import p05float_preflight as preflight
import p05float_dry as dry
import p05float_backup as backup
import p05float_revert as revert
import p05float_apply as apply
import p05float_verify as verify
import p05float_verify_saved as verify_saved


RESULTS = []


def record(name, polarity, expected, passed, detail):
    RESULTS.append({"name": name, "polarity": polarity, "expected": expected,
                    "passed": bool(passed), "detail": str(detail)})


class Exported:
    def __init__(self, text):
        self.text = str(text)

    def export_text(self):
        return self.text


class InstanceComponent(fake_unreal.Component):
    def __init__(self, mesh, transform):
        super().__init__(static_mesh=mesh)
        self.instance_transform = transform

    def get_instance_transform(self, instance_index, world_space):
        if int(instance_index) != 0 or not world_space:
            return False, fake_unreal.Transform()
        return self.instance_transform


class P05Actor(fake_unreal.PassageActor):
    def __init__(self, show, refs, baselines):
        super().__init__(show_asset=show, passage_guid=fake_unreal.Guid("P05-PASSAGE"),
                         materialized_panels=refs)
        self.baselines = baselines

    def get_actor_label(self):
        return "Passage 05 Fake"

    def materialize_passage(self):
        cues = fake_unreal.STATE.assets[fake_unreal.SHOW].get_editor_property("cues")
        for ref in self.get_editor_property("materialized_panels"):
            guid = ref.get_editor_property("cue_guid").to_string()
            side_text = str(ref.get_editor_property("side")).lower()
            side = "left" if "left" in side_text else "right"
            baseline = self.baselines[(guid, side)]
            cue = next(value for value in cues
                       if value.get_editor_property("cue_guid").to_string() == guid)
            panel = cue.get_editor_property("wing_pair").get_editor_property(side)
            local_z = panel.get_editor_property("local_transform").translation.z
            delta = local_z - baseline["old_local_z"]
            old = baseline["world_transform"]
            ref.get_editor_property("component").instance_transform = fake_unreal.Transform(
                location=fake_unreal.Vector(old.translation.x, old.translation.y,
                                            old.translation.z + delta),
                rotation=old.rotation.rotator(),
                scale=fake_unreal.Vector(old.scale3d.x, old.scale3d.y, old.scale3d.z))
        fake_unreal.STATE.map_dirty.add(fake_unreal.WORLD)
        return True


def panel_record(mesh_path, x, y, z):
    return {
        "mesh": mesh_path, "material_overrides": [],
        "local_transform": {"location": [x, y, z], "rotation": [0.0, 0.0, 0.0],
                            "scale": [1.0, 1.0, 1.0]},
        "facing_policy": "PRESERVE_ASSET", "flip_image_horizontally": False,
        "cast_shadow": True, "visible_in_main_pass": True, "collision": "NO_COLLISION",
    }


def panel_from(record):
    return fake_unreal.Obj(
        mesh=fake_unreal.STATE.assets[record["mesh"]], material_overrides=[],
        local_transform=fake_unreal.plain_transform(record["local_transform"]),
        facing_policy=record["facing_policy"],
        flip_image_horizontally=record["flip_image_horizontally"],
        cast_shadow=record["cast_shadow"], visible_in_main_pass=record["visible_in_main_pass"],
        collision=record["collision"])


def side_measurement(probe, index, side):
    if str(index) in probe:
        entries = probe[str(index)]["sides"]
        key = next(name for name in entries if side.upper() in name.upper())
        return entries[key]["world_min"], entries[key]["world_max"]
    ordinal = index - 122
    bottom = (-100.0, 0.0, 100.0, 200.0)[(ordinal + (side == "right")) % 4]
    height = (200.0, 400.0, 520.0)[(ordinal + (side == "right")) % 3]
    x = ordinal * 500.0 + (15.0 if side == "right" else 0.0)
    y = 319750.0 if side == "left" else 320250.0
    return [x - 10.0, y - 120.0, bottom], [x + 10.0, y + 120.0, bottom + height]


def guid_for(index):
    return hashlib.sha256(("P05-FLOAT-%d" % index).encode("utf-8")).hexdigest()[:32].upper()


def make_state():
    fake_unreal.STATE = fake_unreal.State()
    probe = json.loads(PROBE.read_text(encoding="utf-8"))
    cues = [fake_unreal.Obj(label="unused", cue_guid=fake_unreal.Guid("UNUSED-%03d" % i))
            for i in range(215)]
    refs = []
    baselines = {}
    top_mesh_path = "/Fake/P05/Top"
    fake_unreal.STATE.assets[top_mesh_path] = fake_unreal.StaticMesh(
        top_mesh_path, fake_unreal.Vector(-5.0, -100.0, 0.0),
        fake_unreal.Vector(5.0, 100.0, 200.0))
    for index in range(122, 215):
        guid = guid_for(index)
        ordinal = index - 121
        side_records = {}
        for side in ("left", "right"):
            minimum, maximum = side_measurement(probe, index, side)
            centre = [(minimum[axis] + maximum[axis]) * 0.5 for axis in range(3)]
            half = [(maximum[axis] - minimum[axis]) * 0.5 for axis in range(3)]
            mesh_path = "/Fake/P05/%03d_%s" % (ordinal, side)
            mesh = fake_unreal.StaticMesh(
                mesh_path, fake_unreal.Vector(-half[0], -half[1], -half[2]),
                fake_unreal.Vector(half[0], half[1], half[2]))
            fake_unreal.STATE.assets[mesh_path] = mesh
            old_local_z = float(((index + (side == "right")) % 5) * 25 - 50)
            side_records[side] = panel_record(
                mesh_path, float(index - 122), -250.0 if side == "left" else 250.0,
                old_local_z)
            world_transform = fake_unreal.Transform(location=fake_unreal.Vector(*centre))
            component = InstanceComponent(mesh, world_transform)
            refs.append(fake_unreal.Obj(cue_guid=fake_unreal.Guid(guid), side=side.upper(),
                                        component=component, instance_index=0))
            baselines[(guid, side)] = {"old_local_z": old_local_z,
                                       "world_transform": world_transform}
        top_record = panel_record(top_mesh_path, 0.0, 0.0, 600.0)
        pair = fake_unreal.Obj(
            occurrence_guid=fake_unreal.Guid("OCC-" + guid),
            left=panel_from(side_records["left"]), right=panel_from(side_records["right"]),
            has_top=True, top=panel_from(top_record), interval_to_next=fake_unreal.FrameNumber(48000),
            gap_to_next_cm=500.0,
            occurrence_offset=fake_unreal.Transform(), mechanism=Exported("MECHANISM-%03d" % ordinal),
            mute_mechanism_sound=False, attachments=[Exported("ATTACHMENTS-%03d" % ordinal)],
            local_override_mask=0)
        cues[index] = fake_unreal.Obj(
            cue_guid=fake_unreal.Guid(guid), type="WING_PAIR",
            label="P05 Wing %03d" % (((ordinal - 1) % 22) + 1), enabled=True,
            tags=["P05"], wing_pair=pair, scene=Exported("SCENE-EMPTY"))
    show = fake_unreal.Show(cues=cues)
    actor = P05Actor(show, refs, baselines)
    fake_unreal.STATE.assets[fake_unreal.SHOW] = show
    fake_unreal.STATE.actor = actor
    fake_unreal.STATE.logs.extend(["FLATV3_C_OK", "editor is offline fake harness"])
    return fake_unreal.STATE


def staged_config(folder):
    config = json.loads((KIT / "run_p05float.json").read_text(encoding="utf-8"))
    source_dir = folder / "sources"
    source_dir.mkdir()
    show_source = source_dir / "DA_InfinityStage_V1Show.uasset"
    level_source = source_dir / "L_InfinityStage_V1VerticalSlice.umap"
    show_source.write_bytes(b"fake-show-source\n")
    level_source.write_bytes(b"fake-level-source\n")
    config["backup_path"] = str(folder / "Backups" / "PreFlatV3P05Float-FV3F-20261002-01")
    config["backup_sources"] = {
        "DA_InfinityStage_V1Show.uasset": str(show_source),
        "L_InfinityStage_V1VerticalSlice.umap": str(level_source),
    }
    path = folder / "run_p05float.json"
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return path, config


def install_artifact_root(folder):
    modules = (support, preflight, dry, backup, revert, apply, verify, verify_saved)
    for module in modules:
        if hasattr(module, "f"):
            module.f.BASE = str(folder)
    support.BASE = str(folder)
    support.log_has = lambda token: any(token in line for line in fake_unreal.STATE.logs)


def expect_failure(callable_value, token):
    try:
        callable_value()
    except Exception as exc:
        return token in str(exc), str(exc)
    return False, "unexpectedly succeeded"


def local_zs(show):
    result = {}
    for index in range(122, 215):
        cue = show.get_editor_property("cues")[index]
        pair = cue.get_editor_property("wing_pair")
        guid = cue.get_editor_property("cue_guid").to_string()
        result[guid] = {side: pair.get_editor_property(side).get_editor_property(
            "local_transform").translation.z for side in ("left", "right")}
    return result


def case_all(folder):
    config_path, config = staged_config(folder)
    install_artifact_root(folder)
    make_state()
    preflight_report = preflight.run(str(config_path))
    first = dry.run(str(config_path))
    second = dry.run(str(config_path))
    deterministic = first["rows"] == second["rows"]
    record("stable SHA plan across two runs", "+", "identical", deterministic,
           "rows=%d panels=%d" % (first["row_count"], first["panel_count"]))

    targets = [value["target_world_bottom_cm"] for row in first["rows"]
               for value in row["sides"].values()]
    record("all target bottoms", "+", "[150,450]", len(targets) == 186 and
           all(150.0 <= value <= 450.0 for value in targets),
           "min=%.6f max=%.6f" % (min(targets), max(targets)))

    def random_variant(seed):
        random.seed(seed)
        return [150.0 + 300.0 * random.random() for _ in range(186)]
    random_detected = random_variant(1) != random_variant(2)
    record("random.random variant determinism", "-", "FAIL", random_detected,
           "two seeded executions differ=%s" % random_detected)

    measurements = {}
    for row in first["rows"]:
        measurements[row["cue_guid"]] = {}
        for side in ("left", "right"):
            value = row["sides"][side]
            measurements[row["cue_guid"]][side] = {
                "world_min": list(value["measured_world_min"]),
                "world_max": list(value["measured_world_max"]),
                "mesh": value["mesh"], "instance_index": value["instance_index"],
            }
    planted = copy.deepcopy(measurements)
    first_record = preflight_report["rows"][0]
    planted[first_record["cue_guid"]]["left"]["world_max"][2] = 2000.0
    planted_top_passed, planted_top_detail = expect_failure(
        lambda: support.plan_from_measurements(config, preflight_report["rows"], planted),
        "P05FLOAT_WORLD_TOP_LIMIT_FAIL")
    record("planted world top >1100", "-", "FAIL", planted_top_passed,
           planted_top_detail)

    backup_report = backup.run(str(config_path))
    before = local_zs(fake_unreal.STATE.assets[fake_unreal.SHOW])
    applied = apply.run(str(config_path))
    fake_unreal.STATE.logs.append(config["verify_token"])
    verified = verify.main(str(config_path))
    saved_verified = verify_saved.main(str(config_path))

    target_row = first["rows"][0]
    target_cue = fake_unreal.STATE.assets[fake_unreal.SHOW].get_editor_property(
        "cues")[target_row["cue_index"]]
    target_panel = target_cue.get_editor_property("wing_pair").get_editor_property("left")
    transform = target_panel.get_editor_property("local_transform")
    original_x = transform.translation.x
    transform.translation.x = original_x + 5.0
    x_passed, x_detail = expect_failure(
        lambda: verify.run_verify(str(config_path), require_token=True),
        "P05FLOAT_VERIFY_LOCAL_XY_CHANGED")
    transform.translation.x = original_x
    record("verify with changed X", "-", "FAIL", x_passed, x_detail)

    revert.revert("offline-positive-revert", str(config_path))
    after = local_zs(fake_unreal.STATE.assets[fake_unreal.SHOW])
    record("revert restores local Z", "+", "exact", before == after,
           "rows=%d exact=%s" % (len(after), before == after))

    release_lines = [line for line in fake_unreal.STATE.logs
                     if "FLATV3_SLOT_RELEASED" in line]
    integration = (backup_report["file_count"] == 2 and applied["saved_roots"] ==
                   sorted([fake_unreal.SHOW, fake_unreal.WORLD]) and
                   verified["placed_panels"] == 186 and saved_verified["placed_panels"] == 186 and
                   any("run=FV3F-20261002-01 status=OK saved_count=2" in line
                       for line in release_lines) and
                   any("run=FV3FV-20261002-01 status=OK saved_count=2" in line
                       for line in release_lines))
    record("full fake 93-row workflow", "+", "PASS", integration,
           "backup=%d apply_rows=%d verify_panels=%d saved_verify_panels=%d" %
           (backup_report["file_count"], applied["rows"], verified["placed_panels"],
            saved_verified["placed_panels"]))


def case_read_only_tokens():
    forbidden = ("save_asset", "save_current_level", "set_editor_property",
                 "materialize_passage", ".modify(")
    hits = {}
    for name in ("p05float_verify.py", "p05float_verify_saved.py"):
        text = (KIT / name).read_text(encoding="utf-8")
        hits[name] = [token for token in forbidden if token in text]
    record("read-only verifier token check", "+", "clean", not any(hits.values()), hits)


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
    with tempfile.TemporaryDirectory(prefix="flatv3_p05float_offline_") as name:
        case_all(Path(name))
    case_read_only_tokens()
    print_table()
    failed = [row for row in RESULTS if not row["passed"]]
    print("\nOVERALL: %s (%d/%d harness assertions passed)" %
          ("PASS" if not failed else "FAIL", len(RESULTS) - len(failed), len(RESULTS)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
