"""Offline positive/negative harness for Job 131. Starts neither Unreal nor Blender."""
from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import traceback

from PIL import Image

import stage_front_3d_core as C


PASS = 0; FAIL = 0


def check(name, value):
    global PASS, FAIL
    if value: PASS += 1; print("PASS|" + name)
    else: FAIL += 1; print("FAIL|" + name)


def raises(fn, *args, contains=None):
    try: fn(*args)
    except Exception as exc: return contains is None or contains in str(exc)
    return False


def make_sources(project, omit=()):
    root = os.path.join(project, *C.SOURCE_REL.split("/")); os.makedirs(root, exist_ok=True)
    for key, row in C.PIECES.items():
        if row["fbx"] not in omit: open(os.path.join(root, row["fbx"]), "wb").write(("synthetic " + key).encode())
        for map_kind, _, _, _ in C.MAP_KINDS:
            name = "T_%s_%s.png" % (row["bake"], map_kind)
            if name not in omit: Image.new("RGBA", (4, 4), (128, 96, 64, 255)).save(os.path.join(root, name))


def import_without_run(filename):
    path = os.path.join(os.path.dirname(__file__), filename)
    spec = importlib.util.spec_from_file_location("__stage_front_3d_offline__", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def main():
    check("POS exactly six mesh archetypes", len(C.PIECES) == 6)
    check("POS exactly eight placed actors", len(C.build_plan(os.path.dirname(__file__))["actors"]) == 8)
    check("POS folder and root tag contract", C.FOLDER == "StageFront/3D" and C.TAG == "PussStage.StageFront3D")
    check("POS architecture world-origin transforms", all(C.PIECES[k]["instances"][0][1] == [0, 0, 0] for k in ("arch", "wall", "gilt")))
    check("POS paper-relative hero transforms", C.PIECES["crest"]["instances"][0][1] == [-500.0, 0, 1260.0] and
          C.PIECES["cat"]["instances"][0][1] == [-104.7, -1090.0, 0])
    check("POS right cat faces opposite", C.PIECES["cat"]["instances"][1][2] == [0, 0, 180.0])
    check("POS 36 one-file selectors", len(C.selectors()) == 36 and len(set(C.selectors())) == 36)
    check("POS DRY import no confirm", C.validate_import_args({"mode": "DRY"})[0] == "DRY")
    check("NEG IMPORT needs confirm", raises(C.validate_import_args, {"mode": "IMPORT", "asset": "mesh:arch"}, contains="CONFIRM"))
    check("POS one IMPORT selector", C.validate_import_args({"mode": "IMPORT", "confirm": C.CONFIRMS["IMPORT"], "asset": "mesh:arch"})[1]["asset"] == "mesh:arch")
    check("NEG list selector refused", raises(C.validate_import_args, {"mode": "IMPORT", "confirm": C.CONFIRMS["IMPORT"], "asset": ["mesh:arch"]}, contains="ASSET_ONE"))
    check("NEG unknown selector refused", raises(C.validate_import_args, {"mode": "IMPORT", "confirm": C.CONFIRMS["IMPORT"], "asset": "mesh:nope"}, contains="ASSET_ONE"))
    check("POS texture cap default 4K", C.validate_import_args({"mode": "DRY"})[1]["max_texture_size"] == 4096)
    check("NEG texture cap above 4K", raises(C.validate_import_args, {"mode": "DRY", "max_texture_size": 8192}, contains="MAX_4096"))
    check("NEG MATERIAL requires one piece", raises(C.validate_import_args, {"mode": "MATERIAL", "confirm": C.CONFIRMS["MATERIAL"]}, contains="PIECE_ONE"))
    check("POS MATERIAL one piece", C.validate_import_args({"mode": "MATERIAL", "confirm": C.CONFIRMS["MATERIAL"], "piece": "crest"})[1]["piece"] == "crest")
    check("NEG VERIFY needs record", raises(C.validate_import_args, {"mode": "VERIFY"}, contains="RECORD"))
    check("NEG APPLY place needs confirm", raises(C.validate_place_args, {"mode": "APPLY"}, contains="CONFIRM"))
    check("POS APPLY place confirm", C.validate_place_args({"mode": "APPLY", "confirm": "APPLY STAGEFRONT3D"})[0] == "APPLY")
    check("NEG place REVERT needs record", raises(C.validate_place_args, {"mode": "REVERT", "confirm": C.CONFIRMS["PLACE_REVERT"]}, contains="RECORD"))
    check("POS existing target refused", C.existing_target_problems(["/Game/A"], {"/Game/A"}) == ["TARGET_EXISTS|/Game/A"])
    check("POS exact one-object delta", C.import_delta_problems("/Game/A", {"/Game/A"}) == [])
    check("NEG multi-object FBX delta refused", bool(C.import_delta_problems("/Game/A", {"/Game/A", "/Game/B"})))
    with tempfile.TemporaryDirectory() as temp:
        make_sources(temp); plan = C.build_plan(temp, hash_sources=True)
        check("POS synthetic source plan complete", plan["missing"] == [] and len(plan["imports"]) == 36 and len(plan["hashes"]) == 36)
        check("POS import selector resolves once", C.find_import(plan, "tex:crest:Masks")["map_kind"] == "Masks")
        missing_name = C.PIECES["crest"]["fbx"]; os.remove(os.path.join(plan["source_root"], missing_name))
        check("NEG missing final crest FBX detected", any(missing_name in x for x in C.build_plan(temp)["missing"]))
    main_import = open(os.path.join(os.path.dirname(__file__), "stage_front_3d_import.py"), encoding="utf-8").read()
    main_place = open(os.path.join(os.path.dirname(__file__), "stage_front_3d_place.py"), encoding="utf-8").read()
    check("POS live import module loads offline", import_without_run("stage_front_3d_import.py").C.MARK == C.MARK)
    check("POS live place module loads offline", import_without_run("stage_front_3d_place.py").C.MARK == C.MARK)
    check("POS Interchange not FbxImportUI", "InterchangeGenericAssetsPipeline" in main_import and "FbxImportUI()" not in main_import)
    check("POS every mesh import enables and reads back Nanite before save",
          "enable_nanite(c, asset)" in main_import and "NANITE_IN_MEMORY_READBACK" in main_import and
          "NANITE_SAVED_READBACK" in main_import and "NANITE_DRIFT" in main_import and
          main_import.index("enable_nanite(c, asset)") < main_import.index("save_asset(row[\"dest\"]"))
    section = main_import[main_import.index("def run_import("):main_import.index("\ndef run_material(")]
    check("POS one import task call", "import_asset_tasks([task])" in main_import and "replace_existing\", False" in main_import)
    check("POS GC before targeted save", section.index("collect_garbage()") < section.index("save_asset(row[\"dest\"]"))
    check("POS import delta refuses split FBX", "multi-object FBX/strays are never deleted" in main_import)
    check("POS pre-existing master read-only", "PREEXISTING_MASTER_INCOMPATIBLE" in main_import and "if master_exists:" in main_import)
    check("POS never deletes material nodes", "delete_material_expression" not in main_import and "delete_all_material_expressions" not in main_import)
    check("POS mask strengths drive clean-to-dusty blend", all(x in main_import for x in
          ("MaterialExpressionComponentMask", "MaterialExpressionSaturate", "MaterialExpressionLinearInterpolate", "CONNECT_BLEND_ALPHA")))
    check("POS create-only MI", "REFUSE_OVERWRITE|\" + mi_path" in main_import)
    check("POS placement attachment KEEP_WORLD", "AttachmentRule.KEEP_WORLD" in main_place)
    check("POS placement targeted map save", "save_map(world, C.WORLD)" in main_place and "save_dirty_packages" not in main_place)
    check("POS readback includes transforms and materials", all(x in main_place for x in ("location_cm", "rotation_rpy_deg", "materials", "MESH_MATERIALS")))
    check("POS backups precede mutations", main_place.index("map_backup(c, \"StageFront3DPlace\"") < main_place.index("spawn_actor_from_class"))
    production = C.build_plan(r"E:\PussStage")
    expected_missing = []  # job 133 exported cat/column/crest (10 Oct)
    check("POS production has no FBX gaps (job 133)", production["missing"] == expected_missing)
    status = "PASS" if FAIL == 0 else "FAIL"
    result = {"status": status, "pass": PASS, "fail": FAIL, "unreal_processes_started": 0, "blender_processes_started": 0,
              "production_import_count": len(production["imports"]), "production_missing": production["missing"]}
    with open(os.path.join(os.path.dirname(__file__), "stage_front_3d_harness_result.json"), "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=1, sort_keys=True)
    print("STAGEFRONT3D_HARNESS_%s|pass=%d|fail=%d|unreal=0|blender=0" % (status, PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    try: raise SystemExit(main())
    except SystemExit: raise
    except Exception:
        traceback.print_exc(); print("STAGEFRONT3D_HARNESS_FAIL|pass=%d|fail=%d|unreal=0|blender=0" % (PASS, FAIL + 1)); raise
