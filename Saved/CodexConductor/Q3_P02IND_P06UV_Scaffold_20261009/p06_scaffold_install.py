"""Guarded import/placement scaffold for the P06 two-bay asset. Never auto-executes."""
from __future__ import annotations

import datetime
import importlib.util
import json
import os

try:
    import unreal  # type: ignore
except ModuleNotFoundError:
    unreal = None

HERE = os.path.dirname(os.path.abspath(__file__)); SAVED = os.path.dirname(os.path.dirname(HERE))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod


D = _load("q3_defaults", os.path.join(HERE, "q3_defaults.py"))
C = _load("p06_fx_common_q3", os.path.join(SAVED, "CodexConductor", "P06FX_20261008", "p06_fx_common.py"))


def require(value, message):
    if not value: raise RuntimeError(str(message))


def read(path):
    with open(path, encoding="utf-8") as h: return json.load(h)


def write(path, value, exclusive=False):
    with open(path, "x" if exclusive else "w", encoding="utf-8") as h: json.dump(value, h, indent=2, sort_keys=True); h.flush(); os.fsync(h.fileno())


def target_asset(args):
    return args["asset_root"] + "/SM_FlatV3_P06_Scaffold_" + ("2Bay" if args["variant"] == "2bay" else "3Bay")


def panel_plain(panel):
    value = panel.get_editor_property("local_transform"); rotation = value.rotation.rotator()
    return {"mesh": C.asset_id(panel.get_editor_property("mesh")),
            "material_overrides": [C.asset_id(x) for x in panel.get_editor_property("material_overrides")],
            "local_transform": {"location": [float(value.translation.x), float(value.translation.y), float(value.translation.z)],
                                "rotation": [float(rotation.roll), float(rotation.pitch), float(rotation.yaw)],
                                "scale": [float(value.scale3d.x), float(value.scale3d.y), float(value.scale3d.z)]},
            "facing_policy": str(panel.get_editor_property("facing_policy")),
            "flip_image_horizontally": bool(panel.get_editor_property("flip_image_horizontally"))}


def set_panel(panel, record):
    panel.set_editor_property("mesh", unreal.load_asset(record["mesh"]) if record["mesh"] else None)
    panel.set_editor_property("material_overrides", [unreal.load_asset(x) if x else None for x in record["material_overrides"]])
    t = record["local_transform"]; panel.set_editor_property("local_transform", unreal.Transform(location=unreal.Vector(*t["location"]), rotation=unreal.Rotator(roll=t["rotation"][0], pitch=t["rotation"][1], yaw=t["rotation"][2]), scale=unreal.Vector(*t["scale"])))
    policies = {"AUTO_BY_ROLE": unreal.InfinityPanelFacingPolicy.AUTO_BY_ROLE, "PRESERVE_ASSET": unreal.InfinityPanelFacingPolicy.PRESERVE_ASSET, "ROTATE180_AROUND_UP": unreal.InfinityPanelFacingPolicy.ROTATE180_AROUND_UP}
    policy = next((value for key, value in policies.items() if key in record["facing_policy"]), None); require(policy is not None, "FACING_POLICY|" + record["facing_policy"]); panel.set_editor_property("facing_policy", policy); panel.set_editor_property("flip_image_horizontally", bool(record["flip_image_horizontally"])); return panel


def _targets(show, args, expect_new=False):
    cues = list(show.get_editor_property("cues")); rows = []
    for guid, spec in args["replace"].items():
        index, cue = C.cue_by_identity(cues, spec["label"], guid); pair = cue.get_editor_property("wing_pair")
        for side in ("left", "right"):
            if side not in spec: continue
            panel = pair.get_editor_property(side); actual = C.asset_id(panel.get_editor_property("mesh")); expected = target_asset(args) if expect_new else spec[side]
            require(actual == expected, "MESH_DRIFT|%s|%s|expected=%s|actual=%s" % (spec["label"], side, expected, actual))
            plain = panel_plain(panel); require(not plain["material_overrides"], "MATERIAL_OVERRIDES_NOT_EMPTY|%s|%s" % (spec["label"], side))
            rows.append({"guid": guid, "label": spec["label"], "index": index, "side": side, "panel": plain})
    return cues, rows


def _held_rows(show, args):
    """Read and list explicit HOLD sides. They are never returned by _targets or written."""
    cues = list(show.get_editor_property("cues")); rows = []
    for spec in args["held_sides"]:
        index, cue = C.cue_by_identity(cues, spec["label"], spec["guid"])
        pair = cue.get_editor_property("wing_pair"); panel = pair.get_editor_property(spec["side"])
        actual = C.asset_id(panel.get_editor_property("mesh"))
        require(actual == spec["expected_mesh"],
                "HELD_MESH_DRIFT|%s|%s|expected=%s|actual=%s" %
                (spec["label"], spec["side"], spec["expected_mesh"], actual))
        rows.append({"guid": spec["guid"], "label": spec["label"], "index": index,
                     "side": spec["side"], "reason": spec["reason"], "panel": panel_plain(panel)})
    return cues, rows


def dry(args):
    require(unreal is not None, "UNREAL_REQUIRED_FOR_EDITOR_DRY"); C.editor_guard(); before = C.require_clean("PRE")
    fbx = args["fbx_2bay"] if args["variant"] == "2bay" else args["fbx_3bay"]; require(os.path.isfile(fbx), "FBX_MISSING|" + fbx)
    asset = target_asset(args); require(not unreal.EditorAssetLibrary.does_asset_exist(asset), "CREATE_ONLY_EXISTS|" + asset)
    for slot, path in args["materials"].items(): require(unreal.EditorAssetLibrary.does_asset_exist(path), "MATERIAL_MISSING|%s|%s" % (slot, path))
    show, _ = C.show_and_cues(); _, rows = _targets(show, args); _, held = _held_rows(show, args)
    require(C.census() == before, "DRY_CENSUS")
    return {"mode": "DRY", "run": "P06SCAFFOLD-DRY-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"), "marker": "P06SCAFFOLD_DRY_OK", "variant": args["variant"], "fbx": fbx, "asset": asset, "replace_rows": rows, "materials": args["materials"],
            "held_sides": held, "show": D.SHOW, "level": D.WORLD, "lights_imported": False,
            "creative_default": "two-bay 560cm; three-bay 840cm is blocked unless explicitly allowed"}


def _import(args):
    asset = target_asset(args); fbx = args["fbx_2bay"] if args["variant"] == "2bay" else args["fbx_3bay"]
    ui = unreal.FbxImportUI(); ui.set_editor_property("import_mesh", True); ui.set_editor_property("import_materials", False); ui.set_editor_property("import_textures", False); ui.set_editor_property("import_as_skeletal", False)
    ui.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH); ui.static_mesh_import_data.set_editor_property("import_mesh_lo_ds", True); ui.static_mesh_import_data.set_editor_property("combine_meshes", True); ui.static_mesh_import_data.set_editor_property("generate_lightmap_u_vs", True)
    task = unreal.AssetImportTask(); task.set_editor_property("filename", fbx); task.set_editor_property("destination_path", asset.rsplit("/", 1)[0]); task.set_editor_property("destination_name", asset.rsplit("/", 1)[1]); task.set_editor_property("automated", True); task.set_editor_property("replace_existing", False); task.set_editor_property("save", False); task.set_editor_property("options", ui)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task]); mesh = unreal.load_asset(asset); require(isinstance(mesh, unreal.StaticMesh), "IMPORT_FAILED|" + asset)
    mats = list(mesh.get_editor_property("static_materials")); by = {str(m.get_editor_property("material_slot_name")).replace("Q3_", ""): m for m in mats}; require(set(by) == {"Front", "Flap", "Timber", "Edge"}, "SLOTS|" + json.dumps(sorted(by)))
    ordered = []
    for slot in ("Front", "Flap", "Timber", "Edge"):
        item = by[slot]; item.set_editor_property("material_interface", unreal.load_asset(args["materials"][slot])); ordered.append(item)
    mesh.set_editor_property("static_materials", ordered); require(unreal.EditorAssetLibrary.save_loaded_asset(mesh, only_if_is_dirty=False), "SAVE_IMPORT")
    require(C.census() == {"content": [], "maps": []}, "IMPORT_POST_SAVE_DIRTY")
    return mesh


def _write_panels(show, cues, rows, mesh_path, originals=False):
    by_index = {r["index"]: r for r in rows}
    for index, row in by_index.items():
        cue = cues[index]; pair = cue.get_editor_property("wing_pair")
        for target in [x for x in rows if x["index"] == index]:
            panel = pair.get_editor_property(target["side"])
            if originals: set_panel(panel, target["panel"])
            else: panel.set_editor_property("mesh", unreal.load_asset(mesh_path)); panel.set_editor_property("material_overrides", [])
            pair.set_editor_property(target["side"], panel)
        cue.set_editor_property("wing_pair", pair); cues[index] = cue
    show.modify(); show.set_editor_property("cues", cues)


def _readback(show, args, expected_new):
    _, rows = _targets(show, args, expect_new=expected_new)
    actor = C.p06_actor(show); refs = list(actor.get_editor_property("materialized_panels")); runtime = []
    for row in rows:
        hits = [r for r in refs if C.guid_text(r.get_editor_property("cue_guid")) == row["guid"] and row["side"].upper() in str(r.get_editor_property("side")).upper()]
        require(len(hits) == 1, "MATERIALIZED_REF|%s|%s|%d" % (row["label"], row["side"], len(hits)))
        runtime.append({"guid": row["guid"], "side": row["side"], "component_mesh": C.asset_id(hits[0].get_editor_property("component").get_editor_property("static_mesh"))})
    return {"show_rows": rows, "materialized": runtime}


def apply(args):
    plan = dry(args); run = "P06SCAFFOLD-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"); record_path = os.path.join(HERE, "p06_scaffold_record.json"); require(not os.path.exists(record_path), "ACTIVE_RECORD_EXISTS")
    show, _ = C.show_and_cues(); cues, rows = _targets(show, args); backup = C.backup("PreP06Scaffold", run, [D.SHOW, D.WORLD], "before scaffold import/placement")
    applied = []
    for row in rows:
        value = dict(row["panel"]); value["mesh"] = plan["asset"]; value["material_overrides"] = []; applied.append(dict(row, applied_panel=value))
    record = {"run": run, "args": args, "backup": backup, "rows": applied,
              "held_sides": plan["held_sides"], "created_asset": plan["asset"]}; write(record_path, record, exclusive=True)
    _import(args); _write_panels(show, cues, rows, plan["asset"]); require(C.p06_actor(show).materialize_passage(), "MATERIALIZE")
    got = C.census(); require(set(got["content"]) <= {D.SHOW} and set(got["maps"]) <= {D.WORLD}, "DIRTY_SCOPE|" + json.dumps(got))
    C.save_show_level(); saved_show = unreal.load_asset(D.SHOW); readback = _readback(saved_show, args, True)
    _, held_after = _held_rows(saved_show, args); require(held_after == plan["held_sides"], "HELD_SIDE_CHANGED_DURING_APPLY")
    report = {"mode": "APPLY", "run": run, "asset": plan["asset"], "backup": backup,
              "readback": readback, "held_sides": held_after, "census_after": C.census(),
              "marker": "P06SCAFFOLD_APPLY_OK"}; write(os.path.join(HERE, "p06_scaffold_report.json"), report); unreal.log("P06SCAFFOLD_APPLY_OK|run=" + run); return report


def revert(args):
    C.editor_guard(); C.require_clean("PRE_REVERT"); path = os.path.join(HERE, "p06_scaffold_record.json"); require(os.path.isfile(path), "NO_ACTIVE_RECORD"); record = read(path); require(record["args"] == args, "ARGS_DRIFT")
    show, _ = C.show_and_cues(); cues, current = _targets(show, args, expect_new=True)
    _, held_before = _held_rows(show, args); require(held_before == record["held_sides"], "HELD_SIDE_DRIFT_BEFORE_REVERT")
    by = {(r["guid"], r["side"]): r for r in record["rows"]}
    for row in current: require(panel_plain(row_to_panel(cues, row)) == by[(row["guid"], row["side"])]["applied_panel"], "OWNED_FIELD_DRIFT|%s|%s" % (row["label"], row["side"]))
    run = "P06SCAFFOLD-REVERT-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"); C.backup("PreP06ScaffoldRevert", run, [D.SHOW, D.WORLD], "before scaffold placement revert")
    originals = [dict(r, panel=r["panel"]) for r in record["rows"]]; _write_panels(show, cues, originals, record["created_asset"], originals=True); require(C.p06_actor(show).materialize_passage(), "REVERT_MATERIALIZE"); C.save_show_level()
    _, held_after = _held_rows(unreal.load_asset(D.SHOW), args); require(held_after == record["held_sides"], "HELD_SIDE_CHANGED_DURING_REVERT")
    archived = path + ".reverted-" + run; os.replace(path, archived); report = {"mode": "REVERT", "run": run, "created_asset_retained": record["created_asset"], "held_sides": held_after, "record": archived, "marker": "P06SCAFFOLD_REVERT_OK"}; write(os.path.join(HERE, "p06_scaffold_revert_report.json"), report); unreal.log(report["marker"]); return report


def row_to_panel(cues, row):
    return cues[row["index"]].get_editor_property("wing_pair").get_editor_property(row["side"])


def main():
    args = D.validate_scaffold(read(os.path.join(HERE, "p06_scaffold_args.json")))
    result = dry(args) if args["mode"] == "DRY" else apply(args) if args["mode"] == "APPLY" else revert(args); unreal.log("%s|run=%s" % (result["marker"], result["run"])); print(json.dumps(result, indent=2, sort_keys=True)); return result


if __name__ == "__main__": main()
