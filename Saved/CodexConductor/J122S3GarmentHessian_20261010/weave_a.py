import json, os, unreal
mel = unreal.MaterialEditingLibrary
OUT = unreal.Paths.project_saved_dir() + "CodexConductor/J122S3GarmentHessian_20261010/weave_a_record.json"
FIG = ["Shore01_M56", "Shore02_F52", "Shore03_M59", "Shore04_F55", "Shore05_M53", "Shore06_F25"]
BC = unreal.load_asset("/Game/Metahuman/ShoreCast_20260910/ShroudHessian/Textures/T_Shroud_Weave_BC")
N = unreal.load_asset("/Game/Metahuman/ShoreCast_20260910/ShroudHessian/Textures/T_Shroud_Weave_N")
assert BC and N, "WEAVE_TEXTURES_MISSING"
TILING = 12.0   # garment detail tiling (was 80 micro-weave); hessian weave is coarse
lib = unreal.EditorLoadingAndSavingUtils
assert not list(lib.get_dirty_content_packages()), "DIRTY_CONTENT_BEFORE"
assert not os.path.exists(OUT), "RECORD_EXISTS"
rows, mis = [], []
for f in FIG:
    for k in ("Shirt", "Shorts"):
        p = "/Game/Metahuman/ShoreCast_20260910/OutfitHessian/MI_%s_%s_Hessian_v1" % (f, k)
        mi = unreal.load_asset(p); assert mi, "MISSING|" + p
        ct = mel.get_material_instance_texture_parameter_value(mi, "DetailTex_Color")
        nt = mel.get_material_instance_texture_parameter_value(mi, "detailTex_normal")
        rows.append({"path": p, "old": {"DetailTex_Color": ct.get_path_name() if ct else None,
            "detailTex_normal": nt.get_path_name() if nt else None,
            "DetailTex_UVTtiling": float(mel.get_material_instance_scalar_parameter_value(mi, "DetailTex_UVTtiling")),
            "DoDetailColor": bool(mel.get_material_instance_static_switch_parameter_value(mi, "DoDetailColor"))}})
        mis.append((p, mi))
with open(OUT, "w") as fh: json.dump({"tiling": TILING, "rows": rows}, fh, indent=1)
for p, mi in mis:
    mel.set_material_instance_texture_parameter_value(mi, "DetailTex_Color", BC)
    mel.set_material_instance_texture_parameter_value(mi, "detailTex_normal", N)
    mel.set_material_instance_scalar_parameter_value(mi, "DetailTex_UVTtiling", TILING)
    mel.set_material_instance_static_switch_parameter_value(mi, "DoDetailColor", True)
    mel.update_material_instance(mi)
for p, mi in mis:
    ct = mel.get_material_instance_texture_parameter_value(mi, "DetailTex_Color")
    nt = mel.get_material_instance_texture_parameter_value(mi, "detailTex_normal")
    assert ct and ct.get_path_name() == BC.get_path_name(), "READBACK_COLOR|" + p
    assert nt and nt.get_path_name() == N.get_path_name(), "READBACK_NORMAL|" + p
    assert mel.get_material_instance_static_switch_parameter_value(mi, "DoDetailColor"), "READBACK_SWITCH|" + p
dirty = [x.get_name() for x in lib.get_dirty_content_packages()]
assert set(dirty) <= {p for p, _ in mis}, "DIRTY_SCOPE|%s" % dirty
unreal.EditorAssetLibrary.save_loaded_assets([mi for _, mi in mis], True)
assert not list(lib.get_dirty_content_packages()), "STILL_DIRTY"
unreal.log("WEAVE_A_APPLY_OK|n=%d|tiling=%.1f|record=%s" % (len(mis), TILING, OUT))
