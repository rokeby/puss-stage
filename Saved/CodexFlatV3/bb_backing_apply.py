"""Gary 3 Oct: peel under-layer BackingColor -> dark oxide red, PrimerColor -> dark warm grey,
on the two billboard PARENT MIs only. Originals to JSON first; save only these 2; read back."""
import json, os, unreal
BASE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexFlatV3")
MIS = ["/Game/Scenes/Wings/PaintedSurface/Billboard/MI_Billboard_Front",
       "/Game/Scenes/Wings/PaintedSurface/Billboard/MI_Billboard_Flap"]
NEW = {"BackingColor": (0.20, 0.06, 0.04, 1.0), "PrimerColor": (0.16, 0.13, 0.11, 1.0)}
MEL = unreal.MaterialEditingLibrary
def census():
    n = lambda ps: sorted(str(p.get_name()).split(".", 1)[0] for p in ps)
    return {"content": n(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": n(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}
if census() != {"content": [], "maps": []}:
    raise RuntimeError("BB_DIRTY_START|" + json.dumps(census()))
if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None:
    raise RuntimeError("BB_PIE_ACTIVE")
orig_path = os.path.join(BASE, "bb_backing_originals.json")
if not os.path.isfile(orig_path):
    orig = {}
    for p in MIS:
        mi = unreal.load_asset(p)
        orig[p] = {k: list(MEL.get_material_instance_vector_parameter_value(mi, k).to_tuple()) for k in NEW}
    open(orig_path, "w").write(json.dumps(orig, indent=1))
    unreal.log("FLATV3_BB_ORIGINALS path=%s %s" % (orig_path, json.dumps(orig)))
for p in MIS:
    mi = unreal.load_asset(p)
    mi.modify()
    for k, v in NEW.items():
        MEL.set_material_instance_vector_parameter_value(mi, k, unreal.LinearColor(*v))
    MEL.update_material_instance(mi)
dirty = census()
if dirty != {"content": sorted(MIS), "maps": []}:
    raise RuntimeError("BB_DIRTY_SCOPE_FAIL|" + json.dumps(dirty))
for p in MIS:
    if not unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False):
        raise RuntimeError("BB_SAVE_FAIL|" + p)
back = {}
for p in MIS:
    mi = unreal.load_asset(p)
    back[p] = {k: [round(x, 4) for x in MEL.get_material_instance_vector_parameter_value(mi, k).to_tuple()] for k in NEW}
    for k, v in NEW.items():
        if any(abs(a - b) > 1e-3 for a, b in zip(back[p][k], v)):
            raise RuntimeError("BB_READBACK_FAIL|%s|%s|%s" % (p, k, back[p][k]))
if census() != {"content": [], "maps": []}:
    raise RuntimeError("BB_DIRTY_END|" + json.dumps(census()))
unreal.log("FLATV3_BB_BACKING_OK saved_count=2 saved_roots=%s readback=%s" % (json.dumps(MIS), json.dumps(back)))
