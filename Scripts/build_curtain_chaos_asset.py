"""Build the Chaos Cloth curtain in the open PussStage editor (Unreal Python).

Run through the guarded project-Python MCP route (copy into Saved/CodexSoftGoods/ first):
ExecuteProjectPythonFile with relativeSavedPath "CodexSoftGoods/build_curtain_chaos_asset.py".

Inputs (made outside Unreal, see the scripts beside this one):
- DerivedAssets/CurtainCloth/Chaos/SM_<STEM>.fbx + <STEM>.json   build_curtain_chaos_pattern.py (Blender)
- DerivedAssets/CurtainCloth/Chaos/Textures/T_CurtainWeave*.png  build_curtain_weave_maps.py

Creates, all under /Game/Scenes/Curtain/Chaos and nothing else:
- Textures/T_CurtainWeave, Textures/T_CurtainWeave_N
- Materials/M_CurtainVelvet (Cloth shading model: sheen from Fuzz Color, flat colour,
  weave and seams from UV0) and Materials/MI_CurtainVelvet_DeepRed
- Meshes/SM_<STEM>                      the cut pattern: UV0 = flat 2D pattern, positions = pleated start pose
- DF_<STEM>[_Fall]_v<N>                the Chaos Dataflow graph, built node by node, a new version per run
- CA_<STEM>[_Fall]                      the Chaos Cloth Asset, evaluated from the newest graph

MODE "fall" (Gary, 26 Sep: the curtain is already down and FALLS, then piles on the floor):
nothing is pinned, and the component starts suspended so the cloth holds its hanging start pose
until the cue resumes it. It collides with the environment and piles with thick self-collision.
MODE "fly" is the earlier pinned-heading build (CA_<STEM>), kept for reference.

It touches no level actor and saves only the packages above. It refuses to run with any dirty
package. The cloth asset is NEVER deleted (Blueprints and the level reference it): each run makes
a new graph version, re-links the cloth asset to it, evaluates, then deletes the older graphs.

The physics carries the Blender findings over as relationships, not numbers:
- rest shape = flat pattern (2D rest lengths, flat rest angles), pleats only in the start pose;
- stretch stiff, no area constraint; bending low with a much lower buckling stiffness, so the
  fabric resists stretching but folds for free (the tension >> compression asymmetry);
- realistic heavy velvet density, low drag, high self-friction, damping that kills flutter.
"""

import json
import os
import warnings

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
STEM = os.environ.get("CURTAIN_STEM", "CurtainChaos_Ragged_Q15")
MODE = os.environ.get("CURTAIN_MODE", "fall")   # "fall" (current) or "fly" (pinned heading, superseded)
ROOT = "/Game/Scenes/Curtain/Chaos"
CLOTH_NAME = f"CA_{STEM}" if MODE == "fly" else f"CA_{STEM}_Fall"
DF_BASE = f"DF_{STEM}" if MODE == "fly" else f"DF_{STEM}_Fall"
PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
SOURCE = os.path.join(PROJECT, "DerivedAssets", "CurtainCloth", "Chaos")
LOG = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods", f"build_{STEM}.json")

# Tunables. The Dataflow graph is the place to tune them afterwards; these are the starting point.
PHYSICS = {
    "density_kg_m2": 0.8,        # heavy stage velour 0.6-0.8; heaviness comes from low drag and no stretch
    "stretch_stiffness": 1.0,    # PBD, maximum: the fabric does not stretch
    "bending_stiffness": 0.8,    # 27 Sep bench: heavy velvet folds broad; 0.05 read as silk crinkle
    "buckling_ratio": 0.0,       # no buckle-softening: folds keep their body instead of collapsing flat
    "buckling_stiffness": 0.005, # an order below bending: once it starts to fold it folds freely
    "damping": 0.05,
    "drag": 0.03,
    "lift": 0.03,
    "self_friction": 0.9,        # grip holds the heap
    "substeps": 4,
    "iterations": 8,
    "max_iterations": 10,
    "tether_scale": 1.0,
    "max_distance_cm": 10000.0,  # everything free (fly mode: except the heading selection)
    "self_thickness_cm": 3.0,    # per side: thick velvet, so the pile has body
    "self_collision_stiffness": 1.0,
    "collision_thickness_cm": 1.0,
    "floor_friction": 0.8,       # the pile grips the boards instead of skating
}
# Per-pattern air (28 Sep, Gary chose "air at the release" over a breeze or a C++ timed gust): a
# constant 1.5 m/s wind UPSTAGE, in the cloth's own component space so it stays upstage wherever the
# curtain is placed (yaw 90 faces the audience, so upstage is local -Y). Benched inert while the
# curtain hangs (motion 1.41 vs 1.46 still), so it only acts once the cloth moves. Drag 0.08 as benched.
AIR_BY_STEM = {
    "CurtainChaos_Plain_Q15": {"wind_ms": (0.0, -1.5, 0.0), "space": "ComponentSpace", "drag": 0.08},
}
AIR = AIR_BY_STEM.get(STEM, {"wind_ms": (0.0, 0.0, 0.0), "space": "WorldSpace", "drag": None})

VELVET = {
    "VelvetColor": (0.12, 0.004, 0.008, 1.0),   # deep velvet red, linear
    "SheenColor": (0.45, 0.05, 0.07, 1.0),      # the travelling highlight as the nap turns
}

log = {"stem": STEM, "mode": MODE, "air": AIR, "steps": [], "property_failures": [], "physics": PHYSICS}


def step(name, **info):
    log["steps"].append({"step": name, **info})
    unreal.log(f"CURTAIN_CHAOS_STEP|{name}|{json.dumps(info, default=str)}")


def fail(message):
    """Stop, but never leave dirty packages behind in the shared editor: everything this run
    created is this stream's derived data, so save it as-is; the next run rebuilds it."""
    log["error"] = message
    if not log.get("failing"):
        log["failing"] = True
        for asset in globals().get("created", []):
            try:
                unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=True)
            except Exception as exc:  # noqa: BLE001
                log.setdefault("cleanup_errors", []).append(str(exc))
        log["dirty_after_failure"] = dirty_packages()
    write_log()
    raise RuntimeError(message)


def write_log():
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "w", encoding="utf-8") as handle:
        json.dump(log, handle, indent=1, default=str)


def dirty_packages():
    return [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()] + \
           [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]


def build():
    global created
    # --- guards ---------------------------------------------------------------------------------
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    world_path = world.get_path_name().split(".", 1)[0] if world else None
    if world_path != EXPECTED_WORLD:
        fail(f"Unexpected editor world: {world_path}")
    if editor.get_game_world() is not None:
        fail("PIE/SIE is active")
    # This script writes content packages only, never the level. So: no dirty content at the start
    # (someone would be mid-change), and the level's dirty flag must be the same at the end as at
    # the start (e.g. the conductor's net-nil capture flag is left exactly as found, not absorbed).
    dirty_content = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    if dirty_content:
        fail(f"Refusing to build with dirty content packages: {dirty_content}")
    log["dirty_maps_before"] = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]

    sidecar_path = os.path.join(SOURCE, f"{STEM}.json")
    fbx_path = os.path.join(SOURCE, f"SM_{STEM}.fbx")
    for path in (sidecar_path, fbx_path, os.path.join(SOURCE, "Textures", "T_CurtainWeave.png"), os.path.join(SOURCE, "Textures", "T_CurtainWeave_N.png")):
        if not os.path.isfile(path):
            fail(f"Missing input: {path}")
    with open(sidecar_path, encoding="utf-8") as handle:
        sidecar = json.load(handle)

    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    eal = unreal.EditorAssetLibrary
    mel = unreal.MaterialEditingLibrary
    created.clear()


    def import_file(filename, dest, name, options=None):
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", filename)
        task.set_editor_property("destination_path", dest)
        task.set_editor_property("destination_name", name)
        task.set_editor_property("automated", True)
        task.set_editor_property("replace_existing", True)
        task.set_editor_property("save", False)
        if options is not None:
            task.set_editor_property("options", options)
        asset_tools.import_asset_tasks([task])
        asset = eal.load_asset(f"{dest}/{name}")
        if asset is None:
            fail(f"Import produced nothing for {filename}")
        created.append(asset)
        return asset


    # --- textures -------------------------------------------------------------------------------
    tex_dir = f"{ROOT}/Textures"
    weave = import_file(os.path.join(SOURCE, "Textures", "T_CurtainWeave.png"), tex_dir, "T_CurtainWeave")
    weave.set_editor_property("srgb", False)
    weave.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_GRAYSCALE)
    weave_n = import_file(os.path.join(SOURCE, "Textures", "T_CurtainWeave_N.png"), tex_dir, "T_CurtainWeave_N")
    weave_n.set_editor_property("srgb", False)
    weave_n.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
    step("textures", weave=weave.get_path_name(), normal=weave_n.get_path_name())


    # --- velvet material ------------------------------------------------------------------------
    mat_dir = f"{ROOT}/Materials"
    mat_path = f"{mat_dir}/M_CurtainVelvet"
    # The base material is shared by every curtain pattern, so it is built once and left alone
    # (CURTAIN_REBUILD_MATERIAL=1 forces a rebuild). Per-pattern values (width, drop, seams) live on
    # each pattern's own instance, so building one pattern can never re-scale another's seams.
    build_material = not eal.does_asset_exist(mat_path) or os.environ.get("CURTAIN_REBUILD_MATERIAL") == "1"
    if not build_material:
        material = eal.load_asset(mat_path)
        step("material", path=material.get_path_name(), rebuilt=False)
    else:
        if eal.does_asset_exist(mat_path):
            material = eal.load_asset(mat_path)
            # DeleteAllMaterialExpressions removes only about half per call in UE 5.8 (15 -> 7 -> 3,
            # Saved/CodexSoftGoods/diag_material_count.json), so repeat until the graph is empty.
            for _ in range(32):
                if mel.get_num_material_expressions(material) == 0:
                    break
                mel.delete_all_material_expressions(material)
            if mel.get_num_material_expressions(material):
                fail(f"Could not clear M_CurtainVelvet: {mel.get_num_material_expressions(material)} expressions remain")
        else:
            material = asset_tools.create_asset("M_CurtainVelvet", mat_dir, unreal.Material, unreal.MaterialFactoryNew())
        created.append(material)
        material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_CLOTH)
        material.set_editor_property("two_sided", True)
        material.set_editor_property("used_with_skeletal_mesh", True)
        material.set_editor_property("used_with_clothing", True)   # else saving the cloth asset re-dirties the MI

        X = [-1800]


        def expr(cls, y, x=None, **props):
            node = mel.create_material_expression(material, cls, x if x is not None else X[0], y)
            for key, value in props.items():
                node.set_editor_property(key, value)
            return node


        def scalar(name, value, y, x=None):
            return expr(unreal.MaterialExpressionScalarParameter, y, x, parameter_name=name, default_value=value)


        def vector(name, rgba, y, x=None):
            return expr(unreal.MaterialExpressionVectorParameter, y, x, parameter_name=name, default_value=unreal.LinearColor(*rgba))


        def link(a, a_out, b, b_in):
            if not mel.connect_material_expressions(a, a_out, b, b_in):
                fail(f"Material link failed: {a.get_name()}.{a_out} -> {b.get_name()}.{b_in}")


        def binop(cls, a, b, y, x, a_out="", b_out=""):
            node = expr(cls, y, x)
            link(a, a_out, node, "A")
            link(b, b_out, node, "B")
            return node


        # UV0 in metres of flat fabric.
        uv = expr(unreal.MaterialExpressionTextureCoordinate, 0, -1800)
        width = scalar("PatternWidthM", float(sidecar["pattern_width_m"]), 120, -1800)
        drop = scalar("DropM", float(sidecar["drop_m"]), 220, -1800)
        size = binop(unreal.MaterialExpressionAppendVector, width, drop, 160, -1600)
        uv_m = binop(unreal.MaterialExpressionMultiply, uv, size, 60, -1400)

        # Weave: thread-scale grey detail and normal, tiled in metres.
        tile = scalar("WeaveTileM", 0.12, 300, -1400)
        weave_uv = binop(unreal.MaterialExpressionDivide, uv_m, tile, 200, -1200)
        weave_tex = expr(unreal.MaterialExpressionTextureSampleParameter2D, 100, -1000, parameter_name="Weave", texture=weave,
                         sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE)
        link(weave_uv, "", weave_tex, "UVs")
        weave_n_tex = expr(unreal.MaterialExpressionTextureSampleParameter2D, 500, -1000, parameter_name="WeaveNormal", texture=weave_n,
                           sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
        link(weave_uv, "", weave_n_tex, "UVs")
        two = expr(unreal.MaterialExpressionConstant, 0, -800, r=2.0)
        weave_x2 = binop(unreal.MaterialExpressionMultiply, weave_tex, two, 60, -700, a_out="R")
        one = expr(unreal.MaterialExpressionConstant, -80, -700, r=1.0)
        weave_amt = scalar("WeaveColorAmount", 0.2, 180, -700)
        weave_mod = expr(unreal.MaterialExpressionLinearInterpolate, 60, -500)
        link(one, "", weave_mod, "A")
        link(weave_x2, "", weave_mod, "B")
        link(weave_amt, "", weave_mod, "Alpha")

        # Seams: every SeamWidthM of flat fabric, a narrow darker line (the stitched join between bolts).
        u_m = expr(unreal.MaterialExpressionComponentMask, -300, -1200, r=True, g=False, b=False, a=False)
        link(uv_m, "", u_m, "")
        seam_w = scalar("SeamWidthM", float(sidecar["seam_width_m"]), -200, -1200)
        u_bolts = binop(unreal.MaterialExpressionDivide, u_m, seam_w, -300, -1000)
        t = expr(unreal.MaterialExpressionFrac, -300, -850)
        link(u_bolts, "", t, "")
        t_inv = expr(unreal.MaterialExpressionOneMinus, -220, -750)
        link(t, "", t_inv, "")
        t_min = binop(unreal.MaterialExpressionMin, t, t_inv, -300, -650)
        dist_m = binop(unreal.MaterialExpressionMultiply, t_min, seam_w, -300, -550)
        half = scalar("SeamHalfWidthM", 0.012, -200, -550)
        ratio = binop(unreal.MaterialExpressionDivide, dist_m, half, -300, -450)
        ratio_sat = expr(unreal.MaterialExpressionSaturate, -300, -350)
        link(ratio, "", ratio_sat, "")
        seam_dark = scalar("SeamDarken", 0.55, -180, -350)
        seam_mod = expr(unreal.MaterialExpressionLinearInterpolate, -300, -200)
        link(seam_dark, "", seam_mod, "A")
        link(one, "", seam_mod, "B")
        link(ratio_sat, "", seam_mod, "Alpha")

        # Nap: velvet reads darker face-on and lifts toward grazing; the Cloth model's fuzz adds the sheen.
        fresnel = expr(unreal.MaterialExpressionFresnel, 700, -700)
        nap_exp = scalar("NapExponent", 2.5, 800, -900)
        link(nap_exp, "", fresnel, "ExponentIn")
        facing = scalar("FacingDarken", 0.7, 650, -500)
        nap_mod = expr(unreal.MaterialExpressionLinearInterpolate, 700, -350)
        link(facing, "", nap_mod, "A")
        link(one, "", nap_mod, "B")
        link(fresnel, "", nap_mod, "Alpha")

        colour = vector("VelvetColor", VELVET["VelvetColor"], 300, -500)
        c1 = binop(unreal.MaterialExpressionMultiply, colour, weave_mod, 200, -200)
        c2 = binop(unreal.MaterialExpressionMultiply, c1, seam_mod, 100, 0)
        base = binop(unreal.MaterialExpressionMultiply, c2, nap_mod, 300, 150)

        sheen = vector("SheenColor", VELVET["SheenColor"], 500, 0)
        cloth_amt = scalar("ClothAmount", 1.0, 620, 0)
        rough = scalar("Roughness", 0.85, 720, 0)
        spec = scalar("Specular", 0.3, 820, 0)

        flat_n = expr(unreal.MaterialExpressionConstant3Vector, 950, -700, constant=unreal.LinearColor(0.0, 0.0, 1.0, 1.0))
        n_amt = scalar("WeaveNormalStrength", 0.35, 1050, -700)
        n_mix = expr(unreal.MaterialExpressionLinearInterpolate, 950, -450)
        link(flat_n, "", n_mix, "A")
        link(weave_n_tex, "RGB", n_mix, "B")
        link(n_amt, "", n_mix, "Alpha")
        n_norm = expr(unreal.MaterialExpressionNormalize, 950, -250)
        link(n_mix, "", n_norm, "VectorInput")

        # The Cloth model's "Cloth" amount is CustomData0, which Python cannot address as a material
        # property; Make Material Attributes exposes it as its ClearCoat pin (CustomData0).
        attrs = expr(unreal.MaterialExpressionMakeMaterialAttributes, 0, 1300)
        for source, pin in ((base, "BaseColor"), (sheen, "SubsurfaceColor"), (cloth_amt, "ClearCoat"),
                            (rough, "Roughness"), (spec, "Specular"), (n_norm, "Normal")):
            link(source, "", attrs, pin)
        material.set_editor_property("use_material_attributes", True)
        if not mel.connect_material_property(attrs, "", unreal.MaterialProperty.MP_MATERIAL_ATTRIBUTES):
            fail("Could not connect Make Material Attributes to the material")

        mel.recompile_material(material)
        step("material", path=material.get_path_name(), expressions=mel.get_num_material_expressions(material))

    # One instance per pattern (the ragged Q15 keeps the original name the existing assets reference).
    mi_name = "MI_CurtainVelvet_DeepRed" if STEM == "CurtainChaos_Ragged_Q15" else f"MI_CurtainVelvet_DeepRed_{STEM.split('CurtainChaos_')[-1]}"
    mi_path = f"{mat_dir}/{mi_name}"
    mi = eal.load_asset(mi_path) if eal.does_asset_exist(mi_path) else asset_tools.create_asset(
        mi_name, mat_dir, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    created.append(mi)
    mel.set_material_instance_parent(mi, material)
    mel.set_material_instance_vector_parameter_value(mi, "VelvetColor", unreal.LinearColor(*VELVET["VelvetColor"]))
    mel.set_material_instance_vector_parameter_value(mi, "SheenColor", unreal.LinearColor(*VELVET["SheenColor"]))
    for name, value in (("PatternWidthM", sidecar["pattern_width_m"]), ("DropM", sidecar["drop_m"]), ("SeamWidthM", sidecar["seam_width_m"])):
        mel.set_material_instance_scalar_parameter_value(mi, name, float(value))
    mel.update_material_instance(mi)
    step("material_instance", path=mi.get_path_name())


    # --- pattern mesh ---------------------------------------------------------------------------
    fbx = unreal.FbxImportUI()
    fbx.set_editor_property("import_mesh", True)
    fbx.set_editor_property("import_as_skeletal", False)
    fbx.set_editor_property("import_materials", False)
    fbx.set_editor_property("import_textures", False)
    fbx.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)
    smd = fbx.get_editor_property("static_mesh_import_data")
    smd.set_editor_property("combine_meshes", True)
    smd.set_editor_property("generate_lightmap_u_vs", False)
    smd.set_editor_property("auto_generate_collision", False)
    smd.set_editor_property("remove_degenerates", False)
    smd.set_editor_property("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    mesh = import_file(fbx_path, f"{ROOT}/Meshes", f"SM_{STEM}", fbx)
    mesh.set_material(0, mi)

    # The heading selection is by vertex index, so prove the index order survived the import:
    # every heading index must sit on the top edge, and the vertex count must match Blender's.
    desc = mesh.get_static_mesh_description(0)
    count = desc.get_vertex_count()
    if count != sidecar["vertices"]:
        fail(f"Vertex count changed on import: blender={sidecar['vertices']} unreal={count}")
    zs = [desc.get_vertex_position(unreal.VertexID(i)).z for i in range(count)]
    top = max(zs)
    heading = sidecar["heading_vertex_indices"]
    if "heading_sim_indices" not in sidecar:
        fail("Sidecar has no heading_sim_indices: re-run build_curtain_chaos_pattern.py (Chaos sim order)")
    heading_sim = sidecar["heading_sim_indices"]
    off_top = [i for i in heading if abs(zs[i] - top) > 0.01]
    if off_top:
        fail(f"{len(off_top)} heading indices are not on the top edge after import (first {off_top[:5]})")
    on_top = sum(1 for z in zs if abs(z - top) <= 0.01)
    if on_top != len(heading):
        fail(f"Top edge has {on_top} vertices but the sidecar lists {len(heading)} heading indices")
    step("mesh", path=mesh.get_path_name(), vertices=count, heading=len(heading), top_z_cm=top)


    # --- Dataflow graph -------------------------------------------------------------------------
    dfl = unreal.DataflowEditorBlueprintLibrary
    # A new graph version per run; the cloth asset is re-linked to it, and older versions go at the end.
    old_graphs = [str(a).split(".")[0] for a in eal.list_assets(ROOT, recursive=False)
                  if str(a).split(".")[0].split("/")[-1].startswith(f"{DF_BASE}_v")]
    version = 1 + max([int(g.rsplit("_v", 1)[1]) for g in old_graphs if g.rsplit("_v", 1)[1].isdigit()] or [0])
    dataflow = asset_tools.create_asset(f"{DF_BASE}_v{version}", ROOT, unreal.Dataflow, unreal.DataflowAssetFactory())
    created.append(dataflow)

    nodes = {}
    X = [0]   # Dataflow node layout cursor (the material branch sets its own when it runs)


    def node(key, type_name, props):
        name = dfl.add_dataflow_node(dataflow, type_name, key, unreal.Vector2D(X[0], 0.0))
        X[0] += 320
        if not name or str(name) == "None":
            fail(f"Could not add Dataflow node {type_name}")
        nodes[key] = name
        for prop, value in props.items():
            if not dfl.set_dataflow_node_property(dataflow, name, prop, value):
                log["property_failures"].append({"node": key, "property": prop, "value": value})
        return name


    def weighted(value, animatable=True):
        prefix = "bIsAnimatable=True," if animatable else ""
        return f"({prefix}Low={value},High={value})"


    mesh_ref = mesh.get_path_name()
    p = PHYSICS
    node("Import", "FChaosClothAssetStaticMeshImportNode_v2", {
        "StaticMesh": mesh_ref,
        "bImportSimMesh": "True",
        "bImportRenderMesh": "True",
        "UVChannel": "0",
        "UVScale": f"(X={sidecar['uv_scale_cm'][0]},Y={sidecar['uv_scale_cm'][1]})",
    })
    node("BindToRoot", "FChaosClothAssetBindToRootBoneNode", {"bBindSimMesh": "True", "bBindRenderMesh": "True"})
    node("Heading", "FChaosClothAssetSelectionNode_v2", {
        "OutputName": '(StringValue="Heading")',
        "Group": '(Name="SimVertices3D")',
        # SIM-order indices: Chaos re-sorts sim vertices (column by u, bottom-up), so mesh indices
        # pin the wrong particles. Proven only by Scripts/curtain_pin_check.py on a running sim.
        "Indices": "(" + ",".join(str(i) for i in heading_sim) + ")",
    })
    node("Mass", "FChaosClothAssetSimulationMassConfigNode", {
        "MassMode": "Density",
        "DensityWeighted": weighted(p["density_kg_m2"], animatable=False),
    })
    node("Stretch", "FChaosClothAssetSimulationStretchConfigNode", {
        "bStretchUse3dRestLengths": "False",
        "SolverType": "PBD",
        "DistributionType": "Isotropic",
        "bAddAreaConstraint": "False",
        "StretchStiffness": weighted(p["stretch_stiffness"]),
    })
    node("Bending", "FChaosClothAssetSimulationBendingConfigNode", {
        "RestAngleType": "FlatnessRatio",
        "FlatnessRatio": weighted(1.0, animatable=False),
        "SolverType": "PBD",
        "DistributionType": "Isotropic",
        "BendingStiffness": weighted(p["bending_stiffness"]),
        "BucklingRatioWeighted": weighted(p["buckling_ratio"]),
        "BucklingStiffness": weighted(p["buckling_stiffness"]),
    })
    node("Damping", "FChaosClothAssetSimulationDampingConfigNode", {"DampingCoefficientWeighted": weighted(p["damping"])})
    node("Aero", "FChaosClothAssetSimulationAerodynamicsConfigNode", {
        "Drag": weighted(AIR["drag"] if AIR["drag"] is not None else p["drag"]),
        "Lift": weighted(p["lift"]),
        "WindVelocitySpace": AIR["space"],
        "WindVelocity": "(X={},Y={},Z={})".format(*AIR["wind_ms"]),   # m/s, not cm/s
    })
    node("Collision", "FChaosClothAssetSimulationCollisionConfigNode", {
        "CollisionThicknessImported": f"(ImportedValue={p['collision_thickness_cm']},bUseImportedValue=False)",
        "FrictionCoefficientImported": f"(ImportedValue={p['floor_friction']},bUseImportedValue=False)",
    })
    node("SelfCollision", "FChaosClothAssetSimulationSelfCollisionConfigNode_v2", {
        "bUseSelfCollisions": "True",
        "SelfCollisionFriction": f"(ImportedValue={p['self_friction']},bUseImportedValue=False)",
        "SelfCollisionThickness": weighted(p["self_thickness_cm"]),
        "SelfCollisionStiffness": str(p["self_collision_stiffness"]),
    })
    node("Solver", "FChaosClothAssetSimulationSolverConfigNode", {
        "NumIterations": str(p["iterations"]),
        "MaxNumIterations": str(p["max_iterations"]),
        "NumSubstepsImported": f"(ImportedValue={p['substeps']},bUseImportedValue=False)",
    })
    # Fall: nothing kinematic (the component starts suspended instead). Fly: the heading is pinned.
    node("MaxDistance", "FChaosClothAssetSimulationMaxDistanceConfigNode", {
        "MaxDistance": weighted(p["max_distance_cm"]),
        "InKinematic": '(StringValue="Heading")' if MODE == "fly" else '(StringValue="")',
    })
    chain = ["Import", "BindToRoot", "Heading", "Mass", "Stretch", "Bending", "Damping", "Aero",
             "Collision", "SelfCollision", "Solver", "MaxDistance"]
    if MODE == "fly":   # tethers hang from the kinematic set; with nothing pinned there is nothing to tether to
        node("Tethers", "FChaosClothAssetSimulationLongRangeAttachmentConfigNode_v2", {
            "TetherStiffness": weighted(1.0),
            "TetherScale": weighted(p["tether_scale"]),
        })
        chain.append("Tethers")
    terminal = node("Terminal", "FChaosClothAssetTerminalNode_v2", {})

    for a, b in zip(chain, chain[1:]):
        if not dfl.connect_dataflow_nodes(dataflow, nodes[a], "Collection", nodes[b], "Collection"):
            fail(f"Could not connect {a} -> {b}")
    terminal_input = None
    for candidate in ("CollectionLods[0]", "CollectionLods_0", "CollectionLods", "Collection"):
        if dfl.connect_dataflow_nodes(dataflow, nodes[chain[-1]], "Collection", terminal, candidate):
            terminal_input = candidate
            break
    if terminal_input is None:
        fail("Could not connect the chain to the cloth terminal")
    step("dataflow", path=dataflow.get_path_name(), nodes={k: str(v) for k, v in nodes.items()},
         terminal_input=terminal_input, property_failures=len(log["property_failures"]))
    if log["property_failures"]:
        fail(f"Dataflow property sets failed: {log['property_failures']}")


    # --- cloth asset ----------------------------------------------------------------------------
    cloth_path = f"{ROOT}/{CLOTH_NAME}"
    if eal.does_asset_exist(cloth_path):
        cloth = eal.load_asset(cloth_path)   # never deleted: Blueprints and the level reference it
    else:
        factory = unreal.ChaosClothAssetFactory()
        factory.set_editor_property("edit_after_new", False)
        cloth = asset_tools.create_asset(CLOTH_NAME, ROOT, unreal.ChaosClothAsset, factory)
    created.append(cloth)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        instance = cloth.get_editor_property("dataflow_instance")
        instance.set_editor_property("dataflow_asset", dataflow)
        instance.set_editor_property("dataflow_terminal", str(terminal))
        cloth.set_editor_property("dataflow_instance", instance)
    # EvaluateDataflow returns False for cloth assets even when the build succeeds: Epic's own
    # DF_StaticMeshClothTemplate and DF_EmptyClothAssetTemplate return False the same way
    # (Saved/CodexSoftGoods/diag_eval_control.json, 25 Sep). Record it; don't gate on it.
    # The evidence that it built is the skeletal-mesh build line in the log and the saved package.
    evaluated = unreal.DataflowBlueprintLibrary.evaluate_dataflow(dataflow, cloth)
    try:
        materials = [str(m) for m in cloth.get_editor_property("materials")]
    except Exception as exc:  # noqa: BLE001 - informational only
        materials = f"unreadable: {exc}"
    step("cloth", path=cloth.get_path_name(), evaluated=evaluated, materials=materials)

    # Older graph versions are now unreferenced derived data.
    retired = []
    for old in old_graphs:
        if eal.delete_asset(old):
            retired.append(old)
        else:
            log.setdefault("retire_failures", []).append(old)
    step("retired_graphs", retired=retired)


    # --- save only what this script made --------------------------------------------------------
    saved = []
    for asset in created:
        if eal.save_loaded_asset(asset, only_if_is_dirty=False):
            saved.append(asset.get_path_name())
        else:
            fail(f"Save failed: {asset.get_path_name()}")
    log["saved"] = saved
    log["dirty_after"] = dirty_packages()
    log["dirty_maps_after"] = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    write_log()
    if [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]:
        fail(f"Content packages still dirty after save: {log['dirty_after']}")
    if sorted(log["dirty_maps_after"]) != sorted(log["dirty_maps_before"]):
        fail(f"Level dirty state changed during a content-only build: {log['dirty_maps_before']} -> {log['dirty_maps_after']}")
    unreal.log(f"PUSS_SOFTGOODS_CHAOS_BUILD_SUCCESS|stem={STEM}|saved={len(saved)}|cloth={cloth.get_path_name()}")


created = []
try:
    build()
except Exception as exc:  # noqa: BLE001 - any error: save what was made, then re-raise
    if not log.get("failing"):
        try:
            fail(f"Unhandled: {type(exc).__name__}: {exc}")
        except RuntimeError:
            pass
    raise
