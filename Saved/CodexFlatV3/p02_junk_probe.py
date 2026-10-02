"""READ-ONLY probe of the 7 unsaved P02 junk packages (FV3P02I-20261002-03). No edits, no saves."""
import json, os, unreal
BASE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexFlatV3")
EXPECTED = json.load(open(os.path.join(BASE, "p02_junk_packages.json")))
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
def census():
    n = lambda ps: sorted(str(p.get_name()).split(".", 1)[0] for p in ps)
    return {"content": n(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": n(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}
def disk(path):
    root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir())
    return os.path.normpath(os.path.join(root, path[len("/Game/"):].replace("/", os.sep) + ".uasset"))
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
out = {"world": world.get_outermost().get_name() if world else None,
       "pie": editor.get_game_world() is not None, "census": census(), "assets": {}}
for path in EXPECTED:
    refs = [str(r) for r in unreal.EditorAssetLibrary.find_package_referencers_for_asset(path, False)]
    asset = unreal.EditorAssetLibrary.find_asset_data(path)
    out["assets"][path] = {"on_disk": os.path.isfile(disk(path)), "referencers": refs,
                           "in_registry": bool(asset and asset.is_valid()),
                           "class": str(asset.asset_class_path.asset_name) if asset and asset.is_valid() else None}
ok = (out["world"] == WORLD and not out["pie"] and out["census"] == {"content": EXPECTED, "maps": []}
      and not any(a["on_disk"] for a in out["assets"].values())
      and all(set(a["referencers"]) <= set(EXPECTED) for a in out["assets"].values()))
out["safe_to_discard"] = ok
p = os.path.join(BASE, "p02_junk_probe_out.json"); open(p, "w").write(json.dumps(out, indent=1))
unreal.log("FLATV3_P02_JUNK_PROBE safe=%s path=%s census_after=%s" % (ok, p, json.dumps(census())))
