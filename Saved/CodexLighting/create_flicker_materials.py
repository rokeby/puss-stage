"""Create a light-function flicker master material and six instances under /Game/InfinityStage/Lighting.
Saves only that folder. Idempotent: existing assets are reused."""
import unreal
ROOT = "/Game/InfinityStage/Lighting"
MASTER = f"{ROOT}/M_LF_StageFlicker"
tools = unreal.AssetToolsHelpers.get_asset_tools(); mel = unreal.MaterialEditingLibrary
def ensure_master():
    if unreal.EditorAssetLibrary.does_asset_exist(MASTER):
        return unreal.EditorAssetLibrary.load_asset(MASTER)
    m = tools.create_asset("M_LF_StageFlicker", ROOT, unreal.Material, unreal.MaterialFactoryNew())
    m.set_editor_property("material_domain", unreal.MaterialDomain.MD_LIGHT_FUNCTION)
    def param(name, default, x, y):
        p = mel.create_material_expression(m, unreal.MaterialExpressionScalarParameter, x, y)
        p.set_editor_property("parameter_name", name); p.set_editor_property("default_value", default); return p
    speed = param("Speed", 6.0, -1100, -200); depth = param("Depth", 0.35, -1100, 300); phase = param("Phase", 0.0, -1100, 0)
    speed2 = param("SpeedRatio", 2.73, -1100, 100)
    t = mel.create_material_expression(m, unreal.MaterialExpressionTime, -1100, -400)
    ts = mel.create_material_expression(m, unreal.MaterialExpressionMultiply, -900, -300); mel.connect_material_expressions(t, "", ts, "A"); mel.connect_material_expressions(speed, "", ts, "B")
    tp = mel.create_material_expression(m, unreal.MaterialExpressionAdd, -750, -300); mel.connect_material_expressions(ts, "", tp, "A"); mel.connect_material_expressions(phase, "", tp, "B")
    s1 = mel.create_material_expression(m, unreal.MaterialExpressionSine, -600, -300); mel.connect_material_expressions(tp, "", s1, "")
    t2 = mel.create_material_expression(m, unreal.MaterialExpressionMultiply, -750, 0); mel.connect_material_expressions(tp, "", t2, "A"); mel.connect_material_expressions(speed2, "", t2, "B")
    s2 = mel.create_material_expression(m, unreal.MaterialExpressionSine, -600, 0); mel.connect_material_expressions(t2, "", s2, "")
    prod = mel.create_material_expression(m, unreal.MaterialExpressionMultiply, -450, -150); mel.connect_material_expressions(s1, "", prod, "A"); mel.connect_material_expressions(s2, "", prod, "B")
    # prod in [-1,1] -> 0.5 + 0.5*prod in [0,1]
    half = mel.create_material_expression(m, unreal.MaterialExpressionConstant, -450, 50); half.set_editor_property("r", 0.5)
    hp = mel.create_material_expression(m, unreal.MaterialExpressionMultiply, -300, -100); mel.connect_material_expressions(prod, "", hp, "A"); mel.connect_material_expressions(half, "", hp, "B")
    n01 = mel.create_material_expression(m, unreal.MaterialExpressionAdd, -150, -100); mel.connect_material_expressions(hp, "", n01, "A"); mel.connect_material_expressions(half, "", n01, "B")
    dm = mel.create_material_expression(m, unreal.MaterialExpressionMultiply, 0, -100); mel.connect_material_expressions(n01, "", dm, "A"); mel.connect_material_expressions(depth, "", dm, "B")
    one = mel.create_material_expression(m, unreal.MaterialExpressionConstant, 0, 100); one.set_editor_property("r", 1.0)
    out = mel.create_material_expression(m, unreal.MaterialExpressionSubtract, 150, -50); mel.connect_material_expressions(one, "", out, "A"); mel.connect_material_expressions(dm, "", out, "B")
    mel.connect_material_property(out, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.recompile_material(m); return m
master = ensure_master()
profiles = [("Steady", 0.0, 1.0, 0.0), ("Slow", 1.8, 0.18, 0.7), ("Breath", 3.2, 0.25, 2.1), ("Hum", 7.5, 0.22, 4.4), ("Buzz", 14.0, 0.30, 1.3), ("Fault", 22.0, 0.55, 3.8)]
made = []
for name, speed, depth, phase in profiles:
    path = f"{ROOT}/MI_LF_Flicker_{name}"
    if not unreal.EditorAssetLibrary.does_asset_exist(path):
        mi = tools.create_asset(f"MI_LF_Flicker_{name}", ROOT, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        mi.set_editor_property("parent", master)
        mel.set_material_instance_scalar_parameter_value(mi, "Speed", speed); mel.set_material_instance_scalar_parameter_value(mi, "Depth", depth)
        mel.set_material_instance_scalar_parameter_value(mi, "Phase", phase); mel.update_material_instance(mi)
    made.append(path)
saved = unreal.EditorAssetLibrary.save_directory(ROOT, only_if_is_dirty=False, recursive=True)
dirty = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
unreal.log(f"PUSS_FLICKER_MATERIALS_SUCCESS|master={MASTER}|instances={len(made)}|saved={saved}|dirty_after={len(dirty)}")
