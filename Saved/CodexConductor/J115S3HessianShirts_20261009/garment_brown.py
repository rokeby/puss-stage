import json, os, unreal
mel = unreal.MaterialEditingLibrary
OUT = unreal.Paths.project_saved_dir() + "CodexConductor/J115S3HessianShirts_20261009/garment_brown_record.json"
FIG = ["Shore01_M56", "Shore02_F52", "Shore03_M59", "Shore04_F55", "Shore05_M53", "Shore06_F25"]
# Gary 10 Oct: shirts+shorts read as the old white; darken to the shrouds' stained mid-tone, sRGB ~0.45/0.38/0.30.
def lin(c): return ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92
COL = unreal.LinearColor(lin(0.45), lin(0.38), lin(0.30), 1.0)
VECS = ["C_color", "diffuse_color_1", "diffuse_color_2", "B_diffuse_color_1"]
SCAL = {"c_metalness value": 0.0, "C_roughness value": 0.84, "Metallic": 0.0, "B_Metallic": 0.0}
lib = unreal.EditorLoadingAndSavingUtils
d0 = [p.get_name() for p in lib.get_dirty_content_packages()]  # map may be dirty from Gary's own editing; we never save it
assert not d0, "DIRTY_BEFORE|%s" % d0
assert not os.path.exists(OUT), "RECORD_EXISTS"
mis, rec = [], {"color_linear": [COL.r, COL.g, COL.b], "rows": []}
for f in FIG:
    for kind in ("Shirt", "Shorts"):
        path = "/Game/Metahuman/ShoreCast_20260910/OutfitHessian/MI_%s_%s_Hessian_v1" % (f, kind)
        mi = unreal.load_asset(path); assert mi, "MISSING|" + path
        vnames = [str(n) for n in mel.get_vector_parameter_names(mi)]
        snames = [str(n) for n in mel.get_scalar_parameter_names(mi)]
        old = {"v": {}, "s": {}}
        for v in VECS:
            if v in vnames:
                c = mel.get_material_instance_vector_parameter_value(mi, v); old["v"][v] = [c.r, c.g, c.b, c.a]
        for s in SCAL:
            if s in snames: old["s"][s] = float(mel.get_material_instance_scalar_parameter_value(mi, s))
        rec["rows"].append({"path": path, "old": old}); mis.append((path, mi, vnames, snames))
with open(OUT, "w") as fh: json.dump(rec, fh, indent=1)
for path, mi, vnames, snames in mis:
    for v in VECS:
        if v in vnames: mel.set_material_instance_vector_parameter_value(mi, v, COL)
    for s, val in SCAL.items():
        if s in snames: mel.set_material_instance_scalar_parameter_value(mi, s, val)
    mel.update_material_instance(mi)
    for v in VECS:
        if v in vnames:
            c = mel.get_material_instance_vector_parameter_value(mi, v)
            assert abs(c.r - COL.r) < 1e-4 and abs(c.b - COL.b) < 1e-4, "READBACK|%s|%s" % (path, v)
dirty = [p.get_name() for p in lib.get_dirty_content_packages()]
assert set(dirty) <= {p for p, *_ in mis}, "DIRTY_SCOPE|%s" % dirty
unreal.EditorAssetLibrary.save_loaded_assets([mi for _, mi, *_ in mis], True)
left = [p.get_name() for p in lib.get_dirty_content_packages()]
assert not left, "STILL_DIRTY|%s" % left
unreal.log("GARMENT_BROWN_APPLY_OK|n=%d|vecs=%s|record=%s" % (len(mis), sorted({v for *_, vn, _ in mis for v in VECS if v in vn}), OUT))
