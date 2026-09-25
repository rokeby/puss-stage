"""Read-only: is the relief master's BumpOffset actually wired into any sampler's UVs?"""
import json, os
import unreal
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
MASTER = "/Game/Scenes/Wings/StageOpeningV2/Materials/M_StageOpeningV2_Relief_Master"
MEL = unreal.MaterialEditingLibrary
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w = editor.get_editor_world()
assert w is not None and w.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "Unexpected world"
assert editor.get_game_world() is None, "PIE active"
m = unreal.EditorAssetLibrary.load_asset(MASTER)
out = {"api": [n for n in dir(MEL) if "expression" in n.lower() or "input" in n.lower()]}
def props(e):
    r = {"class": e.get_class().get_name(), "name": e.get_name()}
    for p in ("parameter_name", "height_ratio", "reference_plane", "const_coordinate"):
        try: r[p] = str(e.get_editor_property(p))
        except Exception: pass
    return r
nodes = []
try:
    exprs = MEL.get_material_expressions(m)
except Exception as exc:
    exprs = []; out["expr_err"] = repr(exc)
for e in exprs:
    r = props(e)
    try:
        ins = MEL.get_inputs_for_material_expression(m, e)
        r["inputs"] = [None if i is None else i.get_name() for i in ins]
    except Exception as exc:
        r["inputs_err"] = repr(exc)[:200]
    try:
        r["input_names"] = [str(x) for x in MEL.get_material_expression_input_names(e)]
    except Exception as exc:
        r["input_names_err"] = repr(exc)[:200]
    nodes.append(r)
out["nodes"] = nodes
with open(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                       "CodexWingMateriality", "bump_wiring.json"), "w") as fh:
    json.dump(out, fh, indent=1)
unreal.log(f"PUSS_WING_BUMP_WIRING_SUCCESS|nodes={len(nodes)}")
