import json, os, unreal
mel = unreal.MaterialEditingLibrary
OUT = unreal.Paths.project_saved_dir() + "CodexConductor/J115S3HessianShirts_20261009/shorts_demetal_record.json"
FIG = ["Shore01_M56", "Shore02_F52", "Shore03_M59", "Shore04_F55", "Shore05_M53", "Shore06_F25"]
TARGET = {"c_metalness value": 0.0, "C_roughness value": 0.84, "C_specular value": 0.18}
lib = unreal.EditorLoadingAndSavingUtils
dirty0 = sorted(p.get_name() for p in lib.get_dirty_content_packages()) + sorted(p.get_name() for p in lib.get_dirty_map_packages())
assert dirty0 == [], "DIRTY_BEFORE|%s" % dirty0
assert not os.path.exists(OUT), "RECORD_EXISTS"
rec = {"target": TARGET, "rows": []}
mis = []
for f in FIG:
    path = "/Game/Metahuman/ShoreCast_20260910/OutfitHessian/MI_%s_Shorts_Hessian_v1" % f
    mi = unreal.load_asset(path); assert mi, "MISSING|" + path
    old = {k: float(mel.get_material_instance_scalar_parameter_value(mi, k)) for k in TARGET}
    rec["rows"].append({"path": path, "old": old}); mis.append((path, mi))
with open(OUT, "w") as fh: json.dump(rec, fh, indent=1)
for path, mi in mis:
    for k, v in TARGET.items():
        mel.set_material_instance_scalar_parameter_value(mi, k, v)
    mel.update_material_instance(mi)
    for k, v in TARGET.items():
        got = float(mel.get_material_instance_scalar_parameter_value(mi, k))
        assert abs(got - v) < 1e-4, "READBACK|%s|%s=%s" % (path, k, got)
dirty = sorted(p.get_name() for p in lib.get_dirty_content_packages())
assert set(dirty) <= {p for p, _ in mis} and not lib.get_dirty_map_packages(), "DIRTY_SCOPE|%s" % dirty
ok = unreal.EditorAssetLibrary.save_loaded_assets([mi for _, mi in mis], True)
for path, _ in mis:
    unreal.EditorAssetLibrary.load_asset(path)
left = sorted(p.get_name() for p in lib.get_dirty_content_packages())
assert not left, "STILL_DIRTY|%s" % left
unreal.log("SHORTS_DEMETAL_APPLY_OK|n=%d|record=%s" % (len(mis), OUT))
