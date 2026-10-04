"""Create the S6 bee mesh and materials as NEW assets under /Game/Scenes/Effects/Swarm.

Modes (set BEE_SWARM_ASSETS_MODE via the *_run.py wrappers):
  DRY      read-only: checks APIs, folder, collisions; writes the plan; marker _DRY_OK.
  APPLY    creates every missing asset; refuses if ANY target already exists
           (fail closed: nothing half-made is overwritten).
  REBUILD_MATERIALS
           rebuilds the two masters' graphs IN PLACE. Only legal because both live
           in our own Swarm folder (never delete expressions on assets we did not create).

Assets (all new):
  SM_Bee        1.6 cm GeometryScript mesh, +X forward (Niagara faces velocity along +X).
                Section 0 = head+thorax (Body), 1 = abdomen (Glint), 2 = two wing cards.
  M_Bee_Body    opaque DefaultLit master; emissive glint with per-particle twinkle
                (Particle Random phase/rate); brightness = Particle Color alpha.
  M_Bee_Wing    masked two-sided master; temporal-dither opacity (reads as blur under
                TSR) and a flutter WPO about each wing's hinge.
  MI_Bee_Body   GlintStrength 0.     MI_Bee_Glint  GlintStrength 30 (firefly abdomen).
  MI_Bee_Wing   defaults.
Both masters set bUsedWithNiagaraMeshParticles and bUsedWithNiagaraSprites EXPLICITLY:
without the flag a packaged/-game run renders the default material.

Success marker (only after asserted creation, compile request, save and read-back):
  BEE_SWARM_ASSETS_APPLIED|run=...|mesh=...|sections=3|bounds=...|slots=...|mis=...
"""
from __future__ import annotations

import importlib.util
import json
import math
import os

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # offline import for the plan / py_compile
    unreal = None


def _load_common():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_bs_common.py")
    spec = importlib.util.spec_from_file_location("_bs_common_assets", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


C = _load_common()

# ----------------------------------------------------------------- geometry ---
# (name, kind, material_id, location cm, rotation (roll, pitch, yaw) deg, scale, dims)
BEE_PARTS = (
    ("head", "sphere", 0, (0.56, 0.0, 0.02), (0.0, 0.0, 0.0), (1.0, 1.0, 0.95), {"radius": 0.21}),
    ("thorax", "sphere", 0, (0.16, 0.0, 0.03), (0.0, 0.0, 0.0), (1.15, 1.0, 0.95), {"radius": 0.27}),
    ("abdomen", "sphere", 1, (-0.36, 0.0, 0.0), (0.0, -6.0, 0.0), (1.5, 1.0, 0.92), {"radius": 0.31}),
    ("wing_l", "rect", 2, (0.04, 0.60, 0.28), (0.0, 0.0, 18.0), (1.0, 1.0, 1.0), {"x": 0.50, "y": 0.84}),
    ("wing_r", "rect", 2, (0.04, -0.60, 0.28), (0.0, 0.0, -18.0), (1.0, 1.0, 1.0), {"x": 0.50, "y": 0.84}),
)
SPHERE_STEPS = (6, 8)          # phi, theta: ~96 triangles a sphere; 1.6 cm needs no more
WING_HINGE_HALF_WIDTH_CM = 0.18
BOUNDS_TOLERANCE_CM = 0.08


def expected_bounds():
    """Analytic AABB of BEE_PARTS (offline check of the table above)."""
    lo = [1e9, 1e9, 1e9]
    hi = [-1e9, -1e9, -1e9]
    for _, kind, _, loc, rot, scale, dims in BEE_PARTS:
        if kind == "sphere":
            r = dims["radius"]
            # pitch rotation of an ellipsoid: bound by the largest semi-axis in XZ
            ext = [r * scale[0], r * scale[1], r * scale[2]]
            if rot[1]:
                a = math.radians(rot[1])
                ex = math.hypot(ext[0] * math.cos(a), ext[2] * math.sin(a))
                ez = math.hypot(ext[0] * math.sin(a), ext[2] * math.cos(a))
                ext = [ex, ext[1], ez]
            for i in range(3):
                lo[i] = min(lo[i], loc[i] - ext[i])
                hi[i] = max(hi[i], loc[i] + ext[i])
        else:
            a = math.radians(rot[2])
            hx, hy = dims["x"] / 2.0, dims["y"] / 2.0
            for sx in (-1, 1):
                for sy in (-1, 1):
                    x = loc[0] + sx * hx * math.cos(a) - sy * hy * math.sin(a)
                    y = loc[1] + sx * hx * math.sin(a) + sy * hy * math.cos(a)
                    lo[0], hi[0] = min(lo[0], x), max(hi[0], x)
                    lo[1], hi[1] = min(lo[1], y), max(hi[1], y)
            lo[2], hi[2] = min(lo[2], loc[2]), max(hi[2], loc[2])
    return {"x": (lo[0], hi[0]), "y": (lo[1], hi[1]), "z": (lo[2], hi[2])}


# ---------------------------------------------------------------- materials ---
CODE_GLINT = r"""
// Firefly glint: each particle twinkles at its own rate and phase.
float r1 = frac(Rand * 7.1373 + 0.13);
float rate = TwinkleRateHz * (0.6 + 0.8 * r1);
float ph = 6.2831853 * (Time * rate + Rand);
float tw = pow(saturate(0.5 + 0.5 * sin(ph)), max(TwinkleSharpness, 0.1));
float k = GlintFloor + (1.0 - GlintFloor) * tw;
return GlintColor * (GlintStrength * k * Brightness);
"""
CODE_WING_WPO = r"""
// Flap each wing card about its hinge line (local X axis at |y| = HingeHalfWidthCm).
float side = LocalPos.y >= 0.0 ? 1.0 : -1.0;
float d = max(abs(LocalPos.y) - HingeHalfWidthCm, 0.0);
float a = FlapAmplitudeRad * sin(6.2831853 * (Time * FlapHz + Rand * 13.0));
return float3(0.0, side * (d * cos(a) - d), d * sin(a));
"""
CODE_WING_DITHER = r"""
// Temporal interleaved-gradient dither: a pixel survives with probability Alpha;
// TSR/TAA integrates it into a soft, blurred-looking membrane.
float2 p = Parameters.SvPosition.xy + 5.588238 * float(View.StateFrameIndexMod8);
float n = frac(52.9829189 * frac(dot(p, float2(0.06711056, 0.00583715))));
return saturate(Alpha * Brightness) + 0.5 - n;
"""


class Graph:
    def __init__(self, mat):
        self.mat = mat
        self.mel = unreal.MaterialEditingLibrary

    def node(self, cls, x, y, **props):
        n = self.mel.create_material_expression(self.mat, cls, x, y)
        C.require(n is not None, "CREATE_EXPRESSION_FAILED|%s" % cls)
        for k, v in props.items():
            n.set_editor_property(k, v)
        return n

    def scalar(self, name, value, group, x, y):
        return self.node(unreal.MaterialExpressionScalarParameter, x, y, parameter_name=name,
                         default_value=value, group=group)

    def vector(self, name, rgb, group, x, y):
        return self.node(unreal.MaterialExpressionVectorParameter, x, y, parameter_name=name,
                         default_value=unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0), group=group)

    def link(self, a, a_out, b, b_in):
        ok = self.mel.connect_material_expressions(a, a_out, b, b_in)
        if not ok and len(self.mel.get_material_expression_input_names(b)) == 1:
            ok = self.mel.connect_material_expressions(a, a_out, b, "")
        if not ok:
            names = [str(n) for n in self.mel.get_material_expression_input_names(b)]
            raise C.BeeSwarmError("CONNECT_FAILED|%s.%r->%s.%r|inputs=%s" % (a.get_name(), a_out, b.get_name(), b_in, names))

    def prop(self, a, a_out, prop):
        C.require(self.mel.connect_material_property(a, a_out, prop),
                  "CONNECT_PROPERTY_FAILED|%s->%s" % (a.get_name(), prop))

    def custom(self, x, y, desc, code, inputs, out_type):
        n = self.node(unreal.MaterialExpressionCustom, x, y, description=desc, code=code, output_type=out_type)
        rows = []
        for name in inputs:
            ci = unreal.CustomInput()
            ci.set_editor_property("input_name", name)
            rows.append(ci)
        n.set_editor_property("inputs", rows)
        return n


def _set_niagara_usage(mat):
    used = []
    for names in (("used_with_niagara_mesh_particles", "b_used_with_niagara_mesh_particles"),
                  ("used_with_niagara_sprites", "b_used_with_niagara_sprites")):
        used.append(C.set_prop_any(mat, names, True))
    return used


def _material(path, rebuild):
    folder, name = path.rsplit("/", 1)
    mel = unreal.MaterialEditingLibrary
    if C.exists(unreal, path):
        C.require(rebuild, "ASSET_EXISTS|" + path)
        C.require(path.startswith(C.SWARM_FOLDER + "/"), "REFUSE_CLEAR_OUTSIDE_SWARM|" + path)
        mat = unreal.EditorAssetLibrary.load_asset(path)
        for e in list(mel.get_material_expressions(mat)):
            mel.delete_material_expression(mat, e)
        left = mel.get_num_material_expressions(mat)
        C.require(left == 0, "EXPRESSIONS_SURVIVED_CLEAR|%s|%d" % (path, left))
        return mat
    mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, unreal.Material,
                                                                  unreal.MaterialFactoryNew())
    C.require(mat is not None, "CREATE_FAILED|" + path)
    return mat


def build_body(rebuild):
    mat = _material(C.M_BODY, rebuild)
    g = Graph(mat)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    usage = _set_niagara_usage(mat)
    F3 = unreal.CustomMaterialOutputType.CMOT_FLOAT3
    body = g.vector("BodyColor", (0.022, 0.016, 0.010), "01 Body", -900, -200)
    pcol = g.node(unreal.MaterialExpressionParticleColor, -900, 0)
    base = g.node(unreal.MaterialExpressionMultiply, -500, -150)
    g.link(body, "", base, "A")
    g.link(pcol, "A", base, "B")
    g.prop(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
    g.prop(g.scalar("Roughness", 0.42, "01 Body", -500, 50), "", unreal.MaterialProperty.MP_ROUGHNESS)
    g.prop(g.scalar("Specular", 0.5, "01 Body", -500, 150), "", unreal.MaterialProperty.MP_SPECULAR)
    rand = g.node(unreal.MaterialExpressionParticleRandom, -900, 300)
    time = g.node(unreal.MaterialExpressionTime, -900, 400)
    params = {
        "TwinkleRateHz": g.scalar("TwinkleRateHz", 0.8, "02 Glint", -900, 500),
        "TwinkleSharpness": g.scalar("TwinkleSharpness", 6.0, "02 Glint", -900, 600),
        "GlintFloor": g.scalar("GlintFloor", 0.04, "02 Glint", -900, 700),
        "GlintColor": g.vector("GlintColor", (1.0, 0.78, 0.28), "02 Glint", -900, 800),
        "GlintStrength": g.scalar("GlintStrength", 0.0, "02 Glint", -900, 950),
    }
    glint = g.custom(-500, 400, "Firefly glint twinkle", CODE_GLINT,
                     ["Rand", "Time", "TwinkleRateHz", "TwinkleSharpness", "GlintFloor", "GlintColor",
                      "GlintStrength", "Brightness"], F3)
    g.link(rand, "", glint, "Rand")
    g.link(time, "", glint, "Time")
    g.link(pcol, "A", glint, "Brightness")
    for pin, node in params.items():
        g.link(node, "", glint, pin)
    g.prop(glint, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    return mat, usage


def build_wing(rebuild):
    mat = _material(C.M_WING, rebuild)
    g = Graph(mat)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    mat.set_editor_property("two_sided", True)
    mat.set_editor_property("opacity_mask_clip_value", 0.5)
    usage = _set_niagara_usage(mat)
    F1 = unreal.CustomMaterialOutputType.CMOT_FLOAT1
    F3 = unreal.CustomMaterialOutputType.CMOT_FLOAT3
    pcol = g.node(unreal.MaterialExpressionParticleColor, -900, -300)
    tint = g.vector("WingTint", (0.50, 0.46, 0.38), "01 Wing", -900, -150)
    base = g.node(unreal.MaterialExpressionMultiply, -500, -200)
    g.link(tint, "", base, "A")
    g.link(pcol, "A", base, "B")
    g.prop(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
    g.prop(g.scalar("WingRoughness", 0.28, "01 Wing", -500, -50), "", unreal.MaterialProperty.MP_ROUGHNESS)
    g.prop(g.scalar("WingSpecular", 0.65, "01 Wing", -500, 30), "", unreal.MaterialProperty.MP_SPECULAR)
    dither = g.custom(-500, 150, "Wing temporal dither (blur)", CODE_WING_DITHER, ["Alpha", "Brightness"], F1)
    g.link(g.scalar("WingOpacity", 0.35, "01 Wing", -900, 150), "", dither, "Alpha")
    g.link(pcol, "A", dither, "Brightness")
    g.prop(dither, "", unreal.MaterialProperty.MP_OPACITY_MASK)
    lpos = g.node(unreal.MaterialExpressionPreSkinnedPosition, -1100, 400)
    rand = g.node(unreal.MaterialExpressionParticleRandom, -1100, 500)
    time = g.node(unreal.MaterialExpressionTime, -1100, 600)
    wpo = g.custom(-700, 450, "Wing flap about hinge (local cm)", CODE_WING_WPO,
                   ["LocalPos", "Rand", "Time", "FlapHz", "FlapAmplitudeRad", "HingeHalfWidthCm"], F3)
    g.link(lpos, "", wpo, "LocalPos")
    g.link(rand, "", wpo, "Rand")
    g.link(time, "", wpo, "Time")
    g.link(g.scalar("FlapHz", 23.0, "02 Flap", -1100, 700), "", wpo, "FlapHz")
    g.link(g.scalar("FlapAmplitudeRad", 0.7, "02 Flap", -1100, 800), "", wpo, "FlapAmplitudeRad")
    g.link(g.scalar("HingeHalfWidthCm", WING_HINGE_HALF_WIDTH_CM, "02 Flap", -1100, 900), "", wpo, "HingeHalfWidthCm")
    to_world = g.node(unreal.MaterialExpressionTransform, -400, 450,
                      transform_source_type=unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_LOCAL,
                      transform_type=unreal.MaterialVectorCoordTransform.TRANSFORM_WORLD)
    g.link(wpo, "", to_world, "VectorInput")
    g.prop(to_world, "", unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    return mat, usage


MI_SPECS = (
    (C.MI_BODY, C.M_BODY, {"GlintStrength": 0.0}),
    (C.MI_GLINT, C.M_BODY, {"GlintStrength": 30.0}),
    (C.MI_WING, C.M_WING, {}),
)


def build_instances():
    mel = unreal.MaterialEditingLibrary
    rows = []
    for path, parent_path, scalars in MI_SPECS:
        folder, name = path.rsplit("/", 1)
        C.require(not C.exists(unreal, path), "ASSET_EXISTS|" + path)
        mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, folder, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        C.require(mi is not None, "CREATE_FAILED|" + path)
        parent = unreal.EditorAssetLibrary.load_asset(parent_path)
        mel.set_material_instance_parent(mi, parent)
        C.require(C.asset_id(mi.get_editor_property("parent")) == parent_path, "MI_PARENT_READBACK|" + path)
        for key, value in scalars.items():
            mel.set_material_instance_scalar_parameter_value(mi, key, value)  # bool lies (memory): read back
            got = mel.get_material_instance_scalar_parameter_value(mi, key)
            C.require(abs(float(got) - value) < 1e-4, "MI_SCALAR_READBACK|%s|%s=%s" % (path, key, got))
        rows.append({"path": path, "parent": parent_path, "scalars": scalars})
    return rows


def build_mesh():
    C.require(not C.exists(unreal, C.MESH), "ASSET_EXISTS|" + C.MESH)
    prim = unreal.GeometryScript_Primitives
    mesh = unreal.DynamicMesh()
    for name, kind, material_id, loc, rot, scale, dims in BEE_PARTS:
        opts = unreal.GeometryScriptPrimitiveOptions()
        opts.set_editor_property("material_id", material_id)
        xf = unreal.Transform(location=unreal.Vector(*loc),
                              rotation=unreal.Rotator(roll=rot[0], pitch=rot[1], yaw=rot[2]),
                              scale=unreal.Vector(*scale))
        if kind == "sphere":
            prim.append_sphere_lat_long(mesh, opts, xf, dims["radius"], SPHERE_STEPS[0], SPHERE_STEPS[1],
                                        unreal.GeometryScriptPrimitiveOriginMode.CENTER)
        else:
            prim.append_rectangle_xy(mesh, opts, xf, dims["x"], dims["y"], 0, 0)
    options = unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
    C.set_prop_any(options, ("enable_collision", "b_enable_collision"), False)
    C.set_prop_any(options, ("enable_nanite", "b_enable_nanite"), False)
    result = C.unwrap_out(unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(
        mesh, C.MESH, options))
    static_mesh = next((r for r in result if isinstance(r, unreal.StaticMesh)), None)
    if static_mesh is None:
        static_mesh = unreal.EditorAssetLibrary.load_asset(C.MESH)
    C.require(static_mesh is not None and C.exists(unreal, C.MESH), "MESH_CREATE_FAILED|result=%s" % (result,))
    sections = int(static_mesh.get_num_sections(0))
    C.require(sections == 3, "MESH_SECTIONS|expected=3|got=%d" % sections)
    slots = list(static_mesh.get_editor_property("static_materials"))
    while len(slots) < 3:
        static_mesh.add_material(None)
        slots = list(static_mesh.get_editor_property("static_materials"))
    C.require(len(slots) == 3, "MESH_SLOTS|got=%d" % len(slots))
    for index, mi_path in enumerate((C.MI_BODY, C.MI_GLINT, C.MI_WING)):
        static_mesh.set_material(index, unreal.EditorAssetLibrary.load_asset(mi_path))
    for index, mi_path in enumerate((C.MI_BODY, C.MI_GLINT, C.MI_WING)):
        C.require(C.asset_id(static_mesh.get_material(index)) == mi_path, "MESH_MATERIAL_READBACK|%d" % index)
    box = static_mesh.get_bounding_box()
    got = {"x": (box.min.x, box.max.x), "y": (box.min.y, box.max.y), "z": (box.min.z, box.max.z)}
    want = expected_bounds()
    for axis in "xyz":
        for k in (0, 1):
            C.require(abs(got[axis][k] - want[axis][k]) <= BOUNDS_TOLERANCE_CM,
                      "MESH_BOUNDS|%s|got=%s|want=%s (axis convention or scale wrong)" % (axis, got, want))
    return static_mesh, sections, got


def plan():
    return {
        "folder": C.SWARM_FOLDER,
        "assets": [C.M_BODY, C.M_WING, C.MI_BODY, C.MI_GLINT, C.MI_WING, C.MESH],
        "mesh_parts": [list(p[:4]) for p in BEE_PARTS],
        "expected_bounds_cm": expected_bounds(),
        "mesh_slots": {0: C.MI_BODY, 1: C.MI_GLINT, 2: C.MI_WING},
    }


def main(mode=None):
    C.require(unreal is not None, "UNREAL_MODULE_REQUIRED")
    selected = str(mode or globals().get("BEE_SWARM_ASSETS_MODE", "DRY")).upper()
    C.require(selected in ("DRY", "APPLY", "REBUILD_MATERIALS"), "MODE_INVALID|" + selected)
    run = C.stamp_now()
    report_path = os.path.join(C.saved_dir(unreal), "bee_swarm_assets_report.json")
    report = {"ok": False, "mode": selected, "run": run, "plan": plan()}
    try:
        C.editor_world(unreal)
        census_before = C.dirty_census(unreal)
        report["census_before"] = census_before
        ours_dirty = [p for p in census_before["content"] if p.startswith(C.SWARM_FOLDER + "/")]
        C.require(not ours_dirty, "SWARM_PACKAGES_ALREADY_DIRTY|" + ",".join(ours_dirty))
        existing = [p for p in report["plan"]["assets"] if C.exists(unreal, p)]
        report["existing"] = existing
        for api in ("GeometryScript_Primitives", "GeometryScript_NewAssetUtils", "DynamicMesh",
                    "MaterialExpressionParticleRandom", "MaterialExpressionParticleColor",
                    "MaterialExpressionPreSkinnedPosition", "MaterialInstanceConstantFactoryNew"):
            C.require(hasattr(unreal, api), "API_MISSING|" + api)
        if selected == "DRY":
            report["ok"] = True
            C.write_json(report_path, report)
            unreal.log("BEE_SWARM_ASSETS_DRY_OK|run=%s|existing=%s|report=%s" % (run, existing, report_path))
            return
        if selected == "REBUILD_MATERIALS":
            body, usage_b = build_body(True)
            wing, usage_w = build_wing(True)
            for m in (body, wing):
                unreal.MaterialEditingLibrary.recompile_material(m)
            for p in (C.M_BODY, C.M_WING):
                C.save_exact(unreal, p)
            report.update({"ok": True, "usage": usage_b + usage_w, "census_after": C.dirty_census(unreal)})
            C.write_json(report_path, report)
            unreal.log("BEE_SWARM_ASSETS_MATERIALS_REBUILT|run=%s|check the log ~20 s later for "
                       "'Failed to compile' on M_Bee_*" % run)
            return
        C.require(not existing, "ASSETS_EXIST_REFUSING_APPLY|" + ",".join(existing))
        body, usage_b = build_body(False)
        wing, usage_w = build_wing(False)
        for m in (body, wing):
            unreal.MaterialEditingLibrary.recompile_material(m)
        for m in (body, wing):
            for names in (("used_with_niagara_mesh_particles", "b_used_with_niagara_mesh_particles"),):
                C.require(bool(C.get_prop_any(m, names)), "USAGE_FLAG_READBACK|" + m.get_name())
        mis = build_instances()
        static_mesh, sections, bounds = build_mesh()
        saved = [C.save_exact(unreal, p) for p in (C.M_BODY, C.M_WING, C.MI_BODY, C.MI_GLINT, C.MI_WING, C.MESH)]
        census_after = C.dirty_census(unreal)
        still = [p for p in census_after["content"] if p.startswith(C.SWARM_FOLDER + "/")]
        C.require(not still, "SWARM_STILL_DIRTY_AFTER_SAVE|" + ",".join(still))
        for p in saved:
            C.require(C.exists(unreal, p), "READBACK_MISSING|" + p)
        report.update({"ok": True, "saved": saved, "sections": sections, "bounds": bounds,
                       "usage": usage_b + usage_w, "instances": mis, "census_after": census_after})
        C.write_json(report_path, report)
        unreal.log("BEE_SWARM_ASSETS_APPLIED|run=%s|mesh=%s|sections=%d|bounds=%s|slots=%s|mis=%d|report=%s" % (
            run, C.MESH, sections, json.dumps(bounds, separators=(",", ":")),
            ",".join((C.MI_BODY, C.MI_GLINT, C.MI_WING)), len(mis), report_path))
        unreal.log("BEE_SWARM_ASSETS_NOTE|run=%s|compile is async: grep the log for "
                   "'Failed to compile' and M_Bee_ about 20 s from now" % run)
    except Exception as error:  # noqa: BLE001 - every stop is reported
        report["error"] = str(error)
        try:
            report["census_at_stop"] = C.dirty_census(unreal)
        except Exception:  # noqa: BLE001
            pass
        C.write_json(report_path, report)
        unreal.log_error("BEE_SWARM_ASSETS_STOPPED|run=%s|mode=%s|%s" % (run, selected, error))
        raise


if __name__ == "__main__":
    main()
