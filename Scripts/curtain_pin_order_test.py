"""Pin-order test: which Chaos sim-vertex index is the plain curtain's top row?

Hypothesis (from two failed settle tests): Chaos sorts sim vertices column by column across the 2D
pattern. The plain pattern is a 147 x 67 grid, so the top row is c*67 (each column top-first) or
c*67 + 66 (bottom-first). Builds TWO TRANSIENT cloth assets (never saved) with those heading sets,
hangs them side by side off-stage (y >= 60000), captures, cleans up. No content is written.
"""
import json
import os

import unreal

SAVED = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
OUT = os.path.join(SAVED, "CodexSoftGoods", "Frames", "pin_order")
LOG = os.path.join(SAVED, "CodexSoftGoods", "pin_order_test.json")
MESH = "/Game/Scenes/Curtain/Chaos/Meshes/SM_CurtainChaos_Plain_Q15"
MI = "/Game/Scenes/Curtain/Chaos/Materials/MI_CurtainVelvet_DeepRed_Plain_Q15"
COLS, ROWS = 147, 67          # vertices per row, per column
UV_SCALE = (2222.4444444444443, 1000.0)
CAPTURE_AT = [0, 40, 80, 120]
HYPOTHESES = {"A_topfirst": [c * ROWS for c in range(COLS)], "B_bottomfirst": [c * ROWS + ROWS - 1 for c in range(COLS)]}

ss = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if "L_InfinityStage_V1VerticalSlice" not in world.get_name():
    raise RuntimeError("wrong world")
if [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]:
    raise RuntimeError("dirty content: refusing")
if any(a.get_actor_label().startswith("ZZ_") for a in ss.get_all_level_actors()):
    raise RuntimeError("ZZ_ actors already present")
os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT):
    if f.endswith(".png"):
        os.remove(os.path.join(OUT, f))

dfl = unreal.DataflowEditorBlueprintLibrary
mesh = unreal.EditorAssetLibrary.load_asset(MESH)
unreal.EditorAssetLibrary.load_asset(MI)
report = {"errors": [], "property_failures": [], "captures": []}


def w(v, anim=True):
    return f"({'bIsAnimatable=True,' if anim else ''}Low={v},High={v})"


def build_transient_cloth(tag, heading):
    df = unreal.new_object(unreal.Dataflow)
    nodes = []
    spec = [
        ("Import", "FChaosClothAssetStaticMeshImportNode_v2", {"StaticMesh": mesh.get_path_name(), "bImportSimMesh": "True",
                                                              "bImportRenderMesh": "True", "UVChannel": "0",
                                                              "UVScale": f"(X={UV_SCALE[0]},Y={UV_SCALE[1]})"}),
        ("BindToRoot", "FChaosClothAssetBindToRootBoneNode", {}),
        ("Heading", "FChaosClothAssetSelectionNode_v2", {"OutputName": '(StringValue="Heading")', "Group": '(Name="SimVertices3D")',
                                                        "Indices": "(" + ",".join(str(i) for i in heading) + ")"}),
        ("Mass", "FChaosClothAssetSimulationMassConfigNode", {"MassMode": "Density", "DensityWeighted": w(0.8, False)}),
        ("Stretch", "FChaosClothAssetSimulationStretchConfigNode", {"bStretchUse3dRestLengths": "False", "SolverType": "PBD",
                                                                   "DistributionType": "Isotropic", "bAddAreaConstraint": "False",
                                                                   "StretchStiffness": w(1.0)}),
        ("Bending", "FChaosClothAssetSimulationBendingConfigNode", {"RestAngleType": "FlatnessRatio", "FlatnessRatio": w(1.0, False),
                                                                   "SolverType": "PBD", "DistributionType": "Isotropic",
                                                                   "BendingStiffness": w(0.8), "BucklingRatioWeighted": w(0.0)}),
        ("SelfCollision", "FChaosClothAssetSimulationSelfCollisionConfigNode_v2", {"bUseSelfCollisions": "True",
                                                                                  "SelfCollisionThickness": w(3.0)}),
        ("Solver", "FChaosClothAssetSimulationSolverConfigNode", {"NumIterations": "8",
                                                                 "NumSubstepsImported": "(ImportedValue=4,bUseImportedValue=False)"}),
        ("MaxDistance", "FChaosClothAssetSimulationMaxDistanceConfigNode", {"MaxDistance": w(10000.0), "InKinematic": '(StringValue="Heading")'}),
        ("Tethers", "FChaosClothAssetSimulationLongRangeAttachmentConfigNode_v2", {"TetherStiffness": w(1.0)}),
    ]
    for key, type_name, props in spec:
        name = dfl.add_dataflow_node(df, type_name, key, unreal.Vector2D(0, 0))
        for prop, value in props.items():
            if not dfl.set_dataflow_node_property(df, name, prop, value):
                report["property_failures"].append([tag, key, prop])
        nodes.append(name)
    term = dfl.add_dataflow_node(df, "FChaosClothAssetTerminalNode_v2", "Terminal", unreal.Vector2D(0, 0))
    for a, b in zip(nodes, nodes[1:]):
        dfl.connect_dataflow_nodes(df, a, "Collection", b, "Collection")
    dfl.connect_dataflow_nodes(df, nodes[-1], "Collection", term, "CollectionLods[0]")
    ca = unreal.new_object(unreal.ChaosClothAsset)
    unreal.DataflowBlueprintLibrary.evaluate_dataflow(df, ca)
    return df, ca


temps, runs = [], []
keep = []   # keep transient objects alive for the run
bp = unreal.EditorAssetLibrary.load_blueprint_class("/Game/Scenes/Curtain/Chaos/BP_CurtainChaosCloth")
for i, (tag, heading) in enumerate(HYPOTHESES.items()):
    df, ca = build_transient_cloth(tag, heading)
    keep += [df, ca]
    base = unreal.Vector(5400.0, 60000.0 + i * 3000.0, 0.0)
    act = ss.spawn_actor_from_class(bp, base, unreal.Rotator(roll=0.0, pitch=0.0, yaw=90.0))
    act.set_actor_label(f"ZZ_TEMP_SoftGoods_Pin_{tag}")
    temps.append(act)
    cloth = act.get_components_by_class(unreal.ChaosClothComponent)[0]
    cloth.set_asset(ca)
    cloth.set_editor_property("suspend_simulation", False)
    rt = unreal.RenderingLibrary.create_render_target2d(world, 640, 360, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    cam = ss.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(base.x - 2200.0, base.y, 600.0),
                                    unreal.Rotator(roll=0.0, pitch=-6.0, yaw=0.0))
    cam.set_actor_label(f"ZZ_TransientCapture_SoftGoods_Pin_{tag}")
    temps.append(cam)
    cc = cam.capture_component2d
    cc.set_editor_property("texture_target", rt)
    cc.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
    cc.set_editor_property("fov_angle", 70.0)
    cc.set_editor_property("capture_every_frame", False)
    runs.append({"tag": tag, "cloth": cloth, "cc": cc, "rt": rt})
    cloth.set_simulate_in_editor(True)

state = {"n": 0, "handle": None}


def cleanup():
    if state["handle"] is not None:
        unreal.unregister_slate_post_tick_callback(state["handle"])
        state["handle"] = None
    for r in runs:
        try:
            r["cloth"].set_simulate_in_editor(False)
        except Exception:  # noqa: BLE001
            pass
    for a in temps:
        try:
            ss.destroy_actor(a)
        except Exception as exc:  # noqa: BLE001
            report["errors"].append(str(exc))
    report["stray_after"] = [a.get_actor_label() for a in ss.get_all_level_actors() if a.get_actor_label().startswith("ZZ_")]
    report["dirty_content_after"] = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    with open(LOG, "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1, default=str)
    unreal.log(f"PUSS_SOFTGOODS_PIN_ORDER_DONE|captures={len(report['captures'])}|stray={len(report['stray_after'])}")


def tick(delta):
    try:
        if state["n"] in CAPTURE_AT:
            for r in runs:
                r["cc"].capture_scene()
                unreal.RenderingLibrary.export_render_target(world, r["rt"], OUT, f"{r['tag']}_{state['n']:04d}.png")
            report["captures"].append(state["n"])
        state["n"] += 1
        if state["n"] > max(CAPTURE_AT):
            cleanup()
    except Exception as exc:  # noqa: BLE001
        report["errors"].append(f"tick {exc}")
        cleanup()


state["handle"] = unreal.register_slate_post_tick_callback(tick)
unreal.log("PUSS_SOFTGOODS_PIN_ORDER_STARTED")
