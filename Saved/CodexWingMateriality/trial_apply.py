"""Two-panel trial of the new masters (Passage 1), by reparenting MIs only.

  A. SM_R__1_roccoco (legacy, no height map; 16 panels): Front/Back -> painted-surface
     master with HasHeightMap=False (luminance relief), Edge -> canvas-edge master.
     Its mirror SM_L_1_roccoco is left on the legacy material for a side-by-side.
  B. SM_CloudCeilingSmall_02_C (V2 relief, real _H/_N; 24 ceiling panels):
     MI_CloudCeilingSmall_02_C_Relief -> painted-surface master, textures unchanged.

No mesh, Show or level writes. Saves only the four MI packages. The exact prior
state of each MI is written to trial_rollback.json first (never overwritten), and
trial_revert.py restores it. File-level backup: Backups/PreWingMateriality-20260925-193234.
"""
import importlib.util, os
import unreal
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(os.path.dirname(__file__), "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)
MEL = wm.MEL

MASTER = "/Game/Scenes/Wings/PaintedSurface/M_Wing_PaintedSurface_Master"
EDGE = "/Game/Scenes/Wings/PaintedSurface/M_Wing_CanvasEdge_Master"
LEGACY_BASE = "/InterchangeAssets/Materials/FBXLegacyPhongSurfaceMaterial"
OLD_RELIEF = "/Game/Scenes/Wings/StageOpeningV2/Materials/M_StageOpeningV2_Relief_Master"
FLAT_N = "/Engine/EngineMaterials/DefaultNormal"
ROCOCO = "/Game/Scenes/Wings/Materials/M_R__1_roccoco_"
CLOUD = "/Game/Scenes/Wings/Passage05_BirdToMountain/Materials/Instances/MI_CloudCeilingSmall_02_C_Relief"
TARGETS = [ROCOCO + "Front", ROCOCO + "Back", ROCOCO + "Edge", CLOUD]


def snapshot(mi):
    def infos(prop, value_key):
        out = []
        for p in mi.get_editor_property(prop):
            info = p.get_editor_property("parameter_info")
            v = p.get_editor_property(value_key)
            if hasattr(v, "get_path_name"):
                v = wm.pkg(v)
            elif isinstance(v, unreal.LinearColor):
                v = [v.r, v.g, v.b, v.a]
            out.append([str(info.get_editor_property("name")), v])
        return out
    return {"parent": wm.pkg(mi.get_editor_property("parent")),
            "scalars": infos("scalar_parameter_values", "parameter_value"),
            "vectors": infos("vector_parameter_values", "parameter_value"),
            "textures": infos("texture_parameter_values", "parameter_value")}


def set_switch(mi, name, value):
    fn = getattr(MEL, "set_material_instance_static_switch_parameter_value", None)
    wm.require(fn is not None, "no static switch setter in this build")
    fn(mi, name, value)
    wm.require(MEL.get_material_instance_static_switch_parameter_value(mi, name) == value, f"switch {name} did not take")


def set_tex(mi, name, path):
    MEL.set_material_instance_texture_parameter_value(mi, name, unreal.EditorAssetLibrary.load_asset(path))
    got = wm.pkg(MEL.get_material_instance_texture_parameter_value(mi, name))
    wm.require(got == path, f"{wm.pkg(mi)}.{name} = {got}, wanted {path}")


def set_scalar(mi, name, value):
    MEL.set_material_instance_scalar_parameter_value(mi, name, value)
    got = MEL.get_material_instance_scalar_parameter_value(mi, name)
    wm.require(abs(got - value) < 1e-4, f"{wm.pkg(mi)}.{name} = {got}, wanted {value}")


wm.editor_ready()
before = wm.dirty()  # other streams may hold unsaved level work; add nothing to it
mis = {p: unreal.EditorAssetLibrary.load_asset(p) for p in TARGETS}
for p, mi in mis.items():
    wm.require(isinstance(mi, unreal.MaterialInstanceConstant), f"{p} is not an MIC")

rollback_path = os.path.join(wm.OUT_DIR, "trial_rollback.json")
if not os.path.exists(rollback_path):
    snap = {p: snapshot(mi) for p, mi in mis.items()}
    for p in (ROCOCO + "Front", ROCOCO + "Back", ROCOCO + "Edge"):
        wm.require(snap[p]["parent"] == LEGACY_BASE, f"{p} parent is {snap[p]['parent']}, expected legacy")
    wm.require(snap[CLOUD]["parent"] == OLD_RELIEF, f"cloud parent is {snap[CLOUD]['parent']}")
    wm.write_json("trial_rollback.json", snap)
master = unreal.EditorAssetLibrary.load_asset(MASTER)
# Centimetres covered by UV 0..1, measured from each mesh's UVs (probe_uv_axes_readonly.py).
UV = wm.read_json("uv_axes.json")["rows"]
def span(mesh):
    r = UV[mesh]
    return abs(1.0 / r["U_per_cm_Y"]), abs(1.0 / r["V_per_cm_Z"])
ROCOCO_SPAN = span("/Game/Scenes/Wings/StaticMeshes/SM_R__1_roccoco")
CLOUD_SPAN = span("/Game/Scenes/Wings/Passage05_BirdToMountain/StaticMeshes/SM_CloudCeilingSmall_02_C")
edge = unreal.EditorAssetLibrary.load_asset(EDGE)

# A. Rococo right wing: luminance relief, same image on Front and Back as before.
diffuse = wm.read_json("trial_rollback.json")[ROCOCO + "Front"]["textures"]
diffuse = dict(diffuse)["DiffuseColorMap"]
for side in ("Front", "Back"):
    mi = mis[ROCOCO + side]
    MEL.clear_all_material_instance_parameters(mi)
    MEL.set_material_instance_parent(mi, master)
    set_tex(mi, "BaseColor", diffuse)
    set_tex(mi, "OpacityMask", diffuse)
    set_tex(mi, "Normal", FLAT_N)
    set_switch(mi, "HasHeightMap", False)
    set_scalar(mi, "HeightRatio", 0.003)
    set_scalar(mi, "UVSpanUCm", ROCOCO_SPAN[0])
    set_scalar(mi, "UVSpanVCm", ROCOCO_SPAN[1])
    set_switch(mi, "UseBurn", True)  # P01 only, for Effects sources' first PIE proof
    MEL.update_material_instance(mi)
mi = mis[ROCOCO + "Edge"]
MEL.clear_all_material_instance_parameters(mi)
MEL.set_material_instance_parent(mi, edge)
set_scalar(mi, "HalfThicknessCm", 2.5)
MEL.update_material_instance(mi)

# B. Cloud ceiling: V2 relief with real maps; parameter names match, so textures carry over.
mi = mis[CLOUD]
MEL.set_material_instance_parent(mi, master)
set_scalar(mi, "UVSpanUCm", CLOUD_SPAN[0])
set_scalar(mi, "UVSpanVCm", CLOUD_SPAN[1])
set_switch(mi, "UseBurn", True)
MEL.update_material_instance(mi)
for name, want in (("BaseColor", "T_CloudCeilingSmall_02_C"), ("Height", "T_CloudCeilingSmall_02_C_H"),
                   ("Normal", "T_CloudCeilingSmall_02_C_N"), ("OpacityMask", "T_CloudCeilingSmall_02_C")):
    got = wm.pkg(MEL.get_material_instance_texture_parameter_value(mi, name)) or ""
    wm.require(got.endswith("/" + want), f"cloud {name} = {got}")

dirty = wm.dirty()
wm.require(set(dirty) <= set(TARGETS) | set(before), f"Unexpected dirty packages: {dirty}")
for p in TARGETS:
    if p in dirty and p not in before:
        wm.require(unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=True), f"save failed {p}")
after = wm.dirty()
wm.require(set(after) <= set(before), f"Dirty after save: {after}")
readback = {p: wm.pkg(unreal.EditorAssetLibrary.load_asset(p).get_editor_property("parent")) for p in TARGETS}
wm.require(all(v in (MASTER, EDGE) for v in readback.values()), f"parents: {readback}")
wm.write_json("trial_apply_result.json", {"parents": readback, "dirty_after": after})
unreal.log("PUSS_WING_TRIAL_APPLY_SUCCESS|mis=4|dirty=0")
