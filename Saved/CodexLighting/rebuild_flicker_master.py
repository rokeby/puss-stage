"""Rebuild M_LF_StageFlicker with: Speed (Hz), SpeedRatio (irregularity), Depth (how far it dips, 0-1),
Phase, Hardness (0 smooth wave .. 1 hard on/off), OnBias (share of time 'on' in hard mode). Retune the six
instances. Saves only /Game/InfinityStage/Lighting."""
import unreal
ROOT = "/Game/InfinityStage/Lighting"; mel = unreal.MaterialEditingLibrary
m = unreal.EditorAssetLibrary.load_asset(f"{ROOT}/M_LF_StageFlicker"); assert m, "master missing"
mel.delete_all_material_expressions(m)
m.set_editor_property("material_domain", unreal.MaterialDomain.MD_LIGHT_FUNCTION)
def P(name, default, x, y):
    p = mel.create_material_expression(m, unreal.MaterialExpressionScalarParameter, x, y)
    p.set_editor_property("parameter_name", name); p.set_editor_property("default_value", default); return p
def C(v, x, y):
    c = mel.create_material_expression(m, unreal.MaterialExpressionConstant, x, y); c.set_editor_property("r", v); return c
def N(cls, x, y): return mel.create_material_expression(m, cls, x, y)
def link(a, b, pin_b, pin_a=""): mel.connect_material_expressions(a, pin_a, b, pin_b)
speed, ratio, depth, phase = P("Speed", 1.0, -1500, -400), P("SpeedRatio", 1.37, -1500, -250), P("Depth", 0.3, -1500, 400), P("Phase", 0.0, -1500, -100)
hard, bias = P("Hardness", 0.0, -1500, 100), P("OnBias", 0.5, -1500, 250)
t = N(unreal.MaterialExpressionTime, -1500, -550)
ts = N(unreal.MaterialExpressionMultiply, -1300, -500); link(t, ts, "A"); link(speed, ts, "B")
ta = N(unreal.MaterialExpressionAdd, -1150, -500); link(ts, ta, "A"); link(phase, ta, "B")
sa = N(unreal.MaterialExpressionSine, -1000, -500); link(ta, sa, "")
tr = N(unreal.MaterialExpressionMultiply, -1300, -300); link(ts, tr, "A"); link(ratio, tr, "B")
p17 = N(unreal.MaterialExpressionMultiply, -1300, -150); link(phase, p17, "A"); link(C(1.7, -1450, -30), p17, "B")
tb = N(unreal.MaterialExpressionAdd, -1150, -300); link(tr, tb, "A"); link(p17, tb, "B")
sb = N(unreal.MaterialExpressionSine, -1000, -300); link(tb, sb, "")
q = C(0.25, -1000, -180); h = C(0.5, -1000, -80)
qa = N(unreal.MaterialExpressionMultiply, -850, -500); link(sa, qa, "A"); link(q, qa, "B")
qb = N(unreal.MaterialExpressionMultiply, -850, -300); link(sb, qb, "A"); link(q, qb, "B")
sum1 = N(unreal.MaterialExpressionAdd, -700, -400); link(qa, sum1, "A"); link(qb, sum1, "B")
s = N(unreal.MaterialExpressionAdd, -550, -400); link(sum1, s, "A"); link(h, s, "B")          # s in [0,1]
om = N(unreal.MaterialExpressionOneMinus, -1300, 100); link(hard, om, "")
w0 = N(unreal.MaterialExpressionMultiply, -1150, 100); link(om, w0, "A"); link(h, w0, "B")
w = N(unreal.MaterialExpressionAdd, -1000, 100); link(w0, w, "A"); link(C(0.002, -1150, 200), w, "B")
lo = N(unreal.MaterialExpressionSubtract, -850, 200); link(bias, lo, "A"); link(w, lo, "B")
hi = N(unreal.MaterialExpressionAdd, -850, 320); link(bias, hi, "A"); link(w, hi, "B")
ss = N(unreal.MaterialExpressionSmoothStep, -550, 0); link(lo, ss, "Min"); link(hi, ss, "Max"); link(s, ss, "Value")   # wave: 1 = on
off = N(unreal.MaterialExpressionOneMinus, -400, 0); link(ss, off, "")
dm = N(unreal.MaterialExpressionMultiply, -250, 100); link(off, dm, "A"); link(depth, dm, "B")
out = N(unreal.MaterialExpressionOneMinus, -100, 100); link(dm, out, "")                         # 1 - Depth*(1-wave)
mel.connect_material_property(out, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR); mel.recompile_material(m)
profiles = {  # name: Speed Hz, SpeedRatio, Depth, Phase, Hardness, OnBias
    "Steady": (0.0, 1.0, 0.0, 0.0, 0.0, 0.5),
    "Slow":   (0.2, 1.31, 0.45, 0.7, 0.0, 0.5),    # ~5 s breath, dips to 55%
    "Breath": (0.45, 1.23, 0.5, 2.1, 0.15, 0.5),   # ~2 s, dips to 50%
    "Hum":    (8.0, 1.9, 0.3, 4.4, 0.3, 0.5),      # fast shimmer, dips to 70%
    "Buzz":   (13.0, 2.7, 0.6, 1.3, 0.7, 0.55),    # harsh, dips to 40%
    "Fault":  (0.8, 1.43, 1.0, 3.8, 1.0, 0.45),    # hard on/off, 0.5-3 s intervals, fully off
}
for name, (sp, ra, de, ph, ha, ob) in profiles.items():
    mi = unreal.EditorAssetLibrary.load_asset(f"{ROOT}/MI_LF_Flicker_{name}"); assert mi, name
    for pn, v in (("Speed", sp), ("SpeedRatio", ra), ("Depth", de), ("Phase", ph), ("Hardness", ha), ("OnBias", ob)):
        mel.set_material_instance_scalar_parameter_value(mi, pn, v)
    mel.update_material_instance(mi)
saved = unreal.EditorAssetLibrary.save_directory(ROOT, only_if_is_dirty=False, recursive=True)
dirty = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
unreal.log(f"FLICKER_MASTER_REBUILT|profiles={len(profiles)}|saved={saved}|dirty_after={dirty}")
