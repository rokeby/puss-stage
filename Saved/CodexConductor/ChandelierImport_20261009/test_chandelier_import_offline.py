"""Offline positive/negative harness for P80. No Unreal or Blender imports."""
from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import traceback

from PIL import Image

import chandelier_import_core as C
import chandelier_preview as P


PASS = 0
FAIL = 0


def check(name, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print("PASS|" + name)
    else:
        FAIL += 1
        print("FAIL|" + name)


def raises(fn, *args, contains=None):
    try:
        fn(*args)
    except Exception as exc:  # noqa: BLE001 - this is a refusal harness
        return contains is None or contains in str(exc)
    return False


def chain_doc():
    return {"schema": "chandelier_chain_v1", "units": "cm",
            "frame": "UE (x fwd, y right, z up), origin = top hang point",
            "count": 2, "length_cm": 40.0,
            "links": [{"index": 0, "pivot_cm": [0, 0, 0], "length_cm": 20.0, "mass_kg": 1.0},
                      {"index": 1, "pivot_cm": [0, 0, -20], "length_cm": 20.0, "mass_kg": 1.0}],
            "body": {"attach_cm": [0, 0, -40], "mass_kg": 25.0}}


def make_sources(root):
    mesh = os.path.join(root, C.SOURCE_MESH_REL)
    tex = os.path.join(root, C.SOURCE_TEX_REL)
    os.makedirs(mesh); os.makedirs(tex)
    for name in (C.BODY_NAME, C.CHAIN_NAME):
        open(os.path.join(mesh, name + ".fbx"), "wb").write((name + " synthetic").encode())
    with open(os.path.join(mesh, "chandelier_Iron3_chain.json"), "w", encoding="utf-8") as handle:
        json.dump(chain_doc(), handle)
    for name in ("BaseColor_Dusty", "BaseColor_Clean", "Masks", "N", "Roughness"):
        Image.new("RGBA", (4, 4), (120, 80, 40, 255)).save(
            os.path.join(tex, "Chandelier_Iron3_%s.png" % name))


def load_main_without_running():
    path = os.path.join(os.path.dirname(__file__), "chandelier_import.py")
    spec = importlib.util.spec_from_file_location("__p80_offline_harness__", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    # Positive socket contract and required negative controls.
    good = ["SOCKET_Candle_%02d" % i for i in range(1, 45)] + ["ChainAttach"]
    check("POS socket count 44 plus ChainAttach", C.socket_problems(good) == [])
    check("NEG socket count 43 refused", any("COUNT=43" in p for p in C.socket_problems(good[:-2] + ["ChainAttach"])))
    check("NEG duplicate socket refused", "DUPLICATE_SOCKET_NAMES" in C.socket_problems(good + [good[0]]))
    check("NEG foreign socket refused", any("FOREIGN" in p for p in C.socket_problems(good + ["BadSocket"])))

    # Texture profiles: BaseColor sRGB; masks/normal/roughness linear; normal stays DirectX/no flip.
    rows = [{"parameter": r[0], "srgb": r[3], "compression": r[4],
             "flip_green_channel": False if r[0] == "NormalTexture" else None} for r in C.TEXTURE_SPECS]
    check("POS texture profiles", all(C.texture_settings_problems(r, dict(r)) == [] for r in rows))
    bad_mask = dict(rows[2], srgb=True)
    check("NEG mask sRGB refused", any("srgb" in p for p in C.texture_settings_problems(rows[2], bad_mask)))
    bad_normal = dict(rows[3], flip_green_channel=True)
    check("NEG normal green flip refused", any("flip_green" in p for p in C.texture_settings_problems(rows[3], bad_normal)))
    bad_rough = dict(rows[4], srgb=True)
    check("NEG roughness sRGB refused", bool(C.texture_settings_problems(rows[4], bad_rough)))
    nc = C.normal_convention()
    check("POS DirectX equals UE convention", nc["conversion"] == "none" and nc["flip_green_channel"] is False)

    check("POS chain manifest", C.chain_manifest_problems(chain_doc()) == [])
    bad = chain_doc(); bad["count"] = 3
    check("NEG chain count refused", "COUNT" in C.chain_manifest_problems(bad))
    bad = chain_doc(); bad["schema"] = "v0"
    check("NEG chain schema refused", "SCHEMA" in C.chain_manifest_problems(bad))

    master = {"textures": list(C.TEXTURE_PARAMS), "scalars": list(C.SCALAR_PARAMS),
              "switches": list(C.SWITCH_PARAMS),
              "samplers": {r[0]: r[5] for r in C.TEXTURE_SPECS}}
    check("POS master contract", C.master_contract_problems(master) == [])
    bad_master = dict(master, textures=list(C.TEXTURE_PARAMS[:-1]))
    check("NEG master missing parameter refused", bool(C.master_contract_problems(bad_master)))
    check("POS empty target set is create-only", C.overwrite_problems(["/Game/A"], set()) == [])
    check("NEG existing asset overwrite refused", C.overwrite_problems(["/Game/A"], {"/Game/A"}) == ["TARGET_EXISTS|/Game/A"])

    check("POS DRY needs no confirm", C.validate_args({"mode": "DRY"})[0] == "DRY")
    check("NEG IMPORT lacks confirm", raises(C.validate_args, {"mode": "IMPORT"}, None, contains="CONFIRM"))
    check("POS IMPORT exact confirm", C.validate_args({"mode": "IMPORT", "confirm": C.CONFIRMS["IMPORT"]})[0] == "IMPORT")
    check("NEG APPLY before import record", raises(C.validate_args,
          {"mode": "APPLY", "confirm": C.CONFIRMS["APPLY"]}, None, contains="IMPORT_RECORD"))
    check("NEG creative value out of range", raises(C.validate_args,
          {"mode": "DRY", "dust_strength": 9}, None, contains="RANGE"))

    with tempfile.TemporaryDirectory() as temp:
        make_sources(temp)
        plan = C.build_plan(temp)
        check("POS synthetic source plan complete", plan["missing"] == [] and plan["manifest_problems"] == []
              and len(plan["hashes"]) == 8)
        os.remove(plan["meshes"][0]["source"])
        check("NEG missing FBX refused", bool(C.build_plan(temp)["missing"]))

        dusty = os.path.join(temp, "dusty.png"); clean = os.path.join(temp, "clean.png")
        masks = os.path.join(temp, "masks.png"); out = os.path.join(temp, "preview.png")
        Image.new("RGB", (8, 8), (200, 160, 120)).save(dusty)
        Image.new("RGB", (8, 8), (220, 200, 180)).save(clean)
        Image.new("RGBA", (8, 8), (128, 64, 255, 32)).save(masks)
        preview = P.render(dusty, clean, masks, out)
        check("POS preview emitted", os.path.isfile(out) and preview["size"] == [1024, 1096])

    module = load_main_without_running()
    check("POS live tool imports without Unreal", module.C.MARK == C.MARK)
    source = open(os.path.join(os.path.dirname(__file__), "chandelier_import.py"), encoding="utf-8").read()
    check("POS one import task per call", "import_asset_tasks([task])" in source and "replace_existing\", False" in source)
    check("POS modify-before texture setters", source.index("tex.modify()") < source.index("tex.set_editor_property(\"srgb\""))

    status = "PASS" if FAIL == 0 else "FAIL"
    here = os.path.dirname(os.path.abspath(__file__))
    project = os.path.abspath(os.path.join(here, "..", "..", ".."))
    production_plan = C.build_plan(project)
    result = {"status": status, "pass": PASS, "fail": FAIL, "unreal_processes_started": 0,
              "blender_processes_started": 0, "production_inputs_present_in_this_worktree": not production_plan["missing"],
              "production_input_refusals": production_plan["missing"] + production_plan["manifest_problems"]}
    with open(os.path.join(here, "chandelier_import_harness_result.json"), "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=1, sort_keys=True)
    print("CHANDELIER_IMPORT_HARNESS_%s|pass=%d|fail=%d|unreal=0|blender=0" % (status, PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:  # unexpected harness error still prints a stable result line
        traceback.print_exc()
        print("CHANDELIER_IMPORT_HARNESS_FAIL|pass=%d|fail=%d|unreal=0|blender=0" % (PASS, FAIL + 1))
        raise
