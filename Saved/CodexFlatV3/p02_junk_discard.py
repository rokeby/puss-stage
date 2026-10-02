"""Discard EXACTLY the 7 unsaved P02 junk packages from FV3P02I-20261002-03 (conductor-approved, guarded).
NO save path. Mesh first, then textures. Each asset re-checked absent on disk at the moment of deletion."""
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
if world is None or world.get_outermost().get_name() != WORLD:
    raise RuntimeError("WRONG_WORLD")
if editor.get_game_world() is not None:
    raise RuntimeError("PIE_OR_SIE_ACTIVE")
if census() != {"content": EXPECTED, "maps": []}:
    raise RuntimeError("DIRTY_SET_NOT_EXACT|" + json.dumps(census()))
for path in EXPECTED:
    if os.path.isfile(disk(path)):
        raise RuntimeError("ON_DISK|" + path)
    if any(str(r) not in EXPECTED for r in unreal.EditorAssetLibrary.find_package_referencers_for_asset(path, False)):
        raise RuntimeError("EXTERNAL_REFERENCER|" + path)
order = sorted(EXPECTED, key=lambda p: (0 if "/StaticMeshes/" in p else 1, p))
done = []
for path in order:
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if asset is None or str(asset.get_outermost().get_name()) != path:
        raise RuntimeError("LOAD_FAIL|%s|done=%s" % (path, json.dumps(done)))
    if os.path.isfile(disk(path)):
        raise RuntimeError("APPEARED_ON_DISK|" + path)
    if not unreal.EditorAssetLibrary.delete_loaded_asset(asset):
        raise RuntimeError("DELETE_FAIL|%s|done=%s" % (path, json.dumps(done)))
    done.append(path)
    unreal.log("FLATV3_P02_JUNK_DELETED path=%s" % path)
after = census()
if after != {"content": [], "maps": []}:
    raise RuntimeError("CENSUS_NOT_CLEAN_AFTER|" + json.dumps(after))
left = [p for p in EXPECTED if unreal.EditorAssetLibrary.does_asset_exist(p)]
if left:
    raise RuntimeError("STILL_EXISTS|" + json.dumps(left))
unreal.log("FLATV3_P02_JUNK_DISCARDED count=%d census=%s" % (len(done), json.dumps(after)))
