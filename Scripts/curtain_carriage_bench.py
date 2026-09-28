"""Carriage probe (Unreal Python, MCP route; announce first). Transient only: NOTHING is saved.

Is the free cloth being CARRIED rigidly by its component? A real cloth cannot be pushed: jerk the
heading UP and a physical curtain bunches; a carried one rises intact. Jerk it sideways and a physical
curtain swings like a pendulum; a carried one translates intact.

  P1 vs1_jerk_x   transient + VelocityScale 1.0 (value READ BACK from the running interactor), 300 cm upstage in 0.25 s
  P2 asset_jerk_x the saved CA_CurtainChaos_Plain_Q15, the same horizontal jerk
  P3 asset_jerk_up the saved asset, 300 cm UP in 0.25 s

Cost: BASE_S with the actors spawned and the cloth NOT simulating, then COST_S with all three
simulating and NO captures, both timed by WALL CLOCK (perf_counter): the tick delta is clamped at 0.125 s.
"""
import json
import os
import time

import unreal

BASE_S, COST_S, HANG_S, JERK_S, SETTLE_S, CAP_S = 3.0, 3.0, 1.0, 0.25, 4.0, 0.1
JERK_CM = 300.0
HOLD_S, DROP_S = COST_S + HANG_S, JERK_S   # names kept for the capture bookkeeping
ROOT = "/Game/Scenes/Curtain/Chaos"
ASSET = f"{ROOT}/CA_CurtainChaos_Plain_Q15"
MESH = f"{ROOT}/Meshes/SM_CurtainChaos_Plain_Q15"
ORTHO_W, SIDE_W, SIDE_H = 2600.0, 640, 360
PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
SIDECAR = os.path.join(PROJECT, "DerivedAssets", "CurtainCloth", "Chaos", "CurtainChaos_Plain_Q15.json")
SAVED = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
OUT = os.path.join(SAVED, "CodexSoftGoods", "Frames", "carriage")
LOG = os.path.join(SAVED, "CodexSoftGoods", "carriage_bench.json")
# Mirrors PHYSICS and AIR_BY_STEM["CurtainChaos_Plain_Q15"] in Scripts/build_curtain_chaos_asset.py (fly mode).
P = {"density": 0.8, "stretch": 1.0, "bending": 0.8, "buckling_ratio": 0.0, "buckling": 0.005, "damping": 0.05,
     "drag": 0.08, "lift": 0.03, "self_friction": 0.9, "substeps": 4, "iterations": 8, "max_iterations": 10,
     "tether_scale": 1.0, "max_distance": 10000.0, "self_thickness": 3.0, "self_stiffness": 1.0,
     "collision_thickness": 1.0, "floor_friction": 0.8}
VARIANTS = [
    {"id": "P1_vs1_jerk_x", "cloth": "vs1", "floor": False, "jerk": (1.0, 0.0)},
    {"id": "P2_asset_jerk_x", "cloth": "asset", "floor": False, "jerk": (1.0, 0.0)},
    {"id": "P3_asset_jerk_up", "cloth": "asset", "floor": False, "jerk": (0.0, 1.0)},
]

ss = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if "L_InfinityStage_V1VerticalSlice" not in world.get_name():
    raise RuntimeError("wrong world")
DIRTY_BEFORE = sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
if DIRTY_BEFORE:
    raise RuntimeError(f"dirty content {DIRTY_BEFORE}: refusing")
if any(a.get_actor_label().startswith("ZZ_") for a in ss.get_all_level_actors()):
    raise RuntimeError("ZZ_ actors already present")
os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT):
    if f.endswith(".png"):
        os.remove(os.path.join(OUT, f))

sidecar = json.load(open(SIDECAR, encoding="utf-8"))
mesh = unreal.EditorAssetLibrary.load_asset(MESH)
dfl = unreal.DataflowEditorBlueprintLibrary
report = {"errors": [], "property_failures": [], "captures": [], "variants": {}, "deltas": [],
          "hold": int(round(HOLD_S / CAP_S)), "drop": int(round(DROP_S / CAP_S)), "cap_s": CAP_S,
          "side": {"ortho_width": ORTHO_W, "w": SIDE_W, "h": SIDE_H}}


def w(v, anim=True):
    return f"({'bIsAnimatable=True,' if anim else ''}Low={v},High={v})"


def transient_cloth(tag, velocity_scale):
    df = unreal.new_object(unreal.Dataflow)
    spec = [
        ("Import", "FChaosClothAssetStaticMeshImportNode_v2", {"StaticMesh": mesh.get_path_name(), "bImportSimMesh": "True",
                                                              "bImportRenderMesh": "True", "UVChannel": "0",
                                                              "UVScale": "(X={},Y={})".format(*sidecar["uv_scale_cm"])}),
        ("BindToRoot", "FChaosClothAssetBindToRootBoneNode", {"bBindSimMesh": "True", "bBindRenderMesh": "True"}),
        ("Heading", "FChaosClothAssetSelectionNode_v2", {"OutputName": '(StringValue="Heading")', "Group": '(Name="SimVertices3D")',
                                                        "Indices": "(" + ",".join(str(i) for i in sidecar["heading_sim_indices"]) + ")"}),
        ("Mass", "FChaosClothAssetSimulationMassConfigNode", {"MassMode": "Density", "DensityWeighted": w(P["density"], False)}),
        ("Stretch", "FChaosClothAssetSimulationStretchConfigNode", {"bStretchUse3dRestLengths": "False", "SolverType": "PBD",
                                                                   "DistributionType": "Isotropic", "bAddAreaConstraint": "False",
                                                                   "StretchStiffness": w(P["stretch"])}),
        ("Bending", "FChaosClothAssetSimulationBendingConfigNode", {"RestAngleType": "FlatnessRatio", "FlatnessRatio": w(1.0, False),
                                                                   "SolverType": "PBD", "DistributionType": "Isotropic",
                                                                   "BendingStiffness": w(P["bending"]),
                                                                   "BucklingRatioWeighted": w(P["buckling_ratio"]),
                                                                   "BucklingStiffness": w(P["buckling"])}),
        ("Damping", "FChaosClothAssetSimulationDampingConfigNode", {"DampingCoefficientWeighted": w(P["damping"])}),
        ("Aero", "FChaosClothAssetSimulationAerodynamicsConfigNode", {"Drag": w(P["drag"]), "Lift": w(P["lift"]),
                                                                     "WindVelocitySpace": "ComponentSpace",
                                                                     "WindVelocity": "(X=0.0,Y=-1.5,Z=0.0)"}),
        ("Collision", "FChaosClothAssetSimulationCollisionConfigNode", {
            "CollisionThicknessImported": f"(ImportedValue={P['collision_thickness']},bUseImportedValue=False)",
            "FrictionCoefficientImported": f"(ImportedValue={P['floor_friction']},bUseImportedValue=False)"}),
        ("SelfCollision", "FChaosClothAssetSimulationSelfCollisionConfigNode_v2", {
            "bUseSelfCollisions": "True", "SelfCollisionFriction": f"(ImportedValue={P['self_friction']},bUseImportedValue=False)",
            "SelfCollisionThickness": w(P["self_thickness"]), "SelfCollisionStiffness": str(P["self_stiffness"])}),
        ("Solver", "FChaosClothAssetSimulationSolverConfigNode", {"NumIterations": str(P["iterations"]),
                                                                 "MaxNumIterations": str(P["max_iterations"]),
                                                                 "NumSubstepsImported": f"(ImportedValue={P['substeps']},bUseImportedValue=False)"}),
        ("MaxDistance", "FChaosClothAssetSimulationMaxDistanceConfigNode", {"MaxDistance": w(P["max_distance"]),
                                                                           "InKinematic": '(StringValue="Heading")'}),
        ("Tethers", "FChaosClothAssetSimulationLongRangeAttachmentConfigNode_v2", {"TetherStiffness": w(1.0),
                                                                                  "TetherScale": w(P["tether_scale"])}),
    ]
    if velocity_scale is not None:
        spec.append(("VelocityScale", "FChaosClothAssetSimulationVelocityScaleConfigNode", {
            "LinearVelocityScale": "(X={0},Y={0},Z={0})".format(velocity_scale),
            "AngularVelocityScale": str(velocity_scale)}))
    names = []
    for key, type_name, props in spec:
        name = dfl.add_dataflow_node(df, type_name, key, unreal.Vector2D(0, 0))
        if not name or str(name) == "None":
            raise RuntimeError(f"could not add {type_name}")
        for prop, value in props.items():
            if not dfl.set_dataflow_node_property(df, name, prop, value):
                report["property_failures"].append([tag, key, prop, value])
        names.append(name)
    term = dfl.add_dataflow_node(df, "FChaosClothAssetTerminalNode_v2", "Terminal", unreal.Vector2D(0, 0))
    for a, b in zip(names, names[1:]):
        if not dfl.connect_dataflow_nodes(df, a, "Collection", b, "Collection"):
            raise RuntimeError(f"could not connect {a} -> {b}")
    if not dfl.connect_dataflow_nodes(df, names[-1], "Collection", term, "CollectionLods[0]"):
        raise RuntimeError("could not connect terminal")
    ca = unreal.new_object(unreal.ChaosClothAsset)
    unreal.DataflowBlueprintLibrary.evaluate_dataflow(df, ca)
    return df, ca


temps, runs, keep = [], [], []


def capture_rig(tag, base, cloth_actor):
    rt = unreal.RenderingLibrary.create_render_target2d(world, 640, 360, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    cam = ss.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(base.x - 2400.0, base.y - 900.0, 700.0),
                                    unreal.Rotator(roll=0.0, pitch=-10.0, yaw=20.0))
    cam.set_actor_label(f"ZZ_TransientCapture_SoftGoods_VS_{tag}")
    cc = cam.capture_component2d
    cc.set_editor_property("texture_target", rt)
    cc.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
    cc.set_editor_property("fov_angle", 75.0)
    cc.set_editor_property("capture_every_frame", False)
    side_center = unreal.Vector(base.x + 300.0, base.y + 4000.0, 600.0)
    srt = unreal.RenderingLibrary.create_render_target2d(world, SIDE_W, SIDE_H, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    side = ss.spawn_actor_from_class(unreal.SceneCapture2D, side_center, unreal.Rotator(roll=0.0, pitch=0.0, yaw=-90.0))
    side.set_actor_label(f"ZZ_TransientCapture_SoftGoods_VSSide_{tag}")
    sc = side.capture_component2d
    sc.set_editor_property("texture_target", srt)
    sc.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_BASE_COLOR)
    sc.set_editor_property("projection_type", unreal.CameraProjectionMode.ORTHOGRAPHIC)
    sc.set_editor_property("ortho_width", ORTHO_W)
    sc.set_editor_property("primitive_render_mode", unreal.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST)
    sc.show_only_actor_components(cloth_actor, False)
    sc.set_editor_property("capture_every_frame", False)
    temps.extend([cam, side])
    return cc, rt, sc, srt, side_center


def setup():
    built = {}
    for key, vs in (("vs1", 1.0), ("vs0", None)):
        df, ca = transient_cloth(key, vs)
        keep.extend([df, ca])
        built[key] = ca
    built["asset"] = unreal.EditorAssetLibrary.load_asset(ASSET)
    if report["property_failures"]:
        raise RuntimeError(f"property failures {report['property_failures']}")
    bp = unreal.EditorAssetLibrary.load_blueprint_class(f"{ROOT}/BP_CurtainChaosCloth")
    floor_bp = unreal.EditorAssetLibrary.load_blueprint_class(f"{ROOT}/BP_CurtainFloorCatch")
    for i, v in enumerate(VARIANTS):
        tag = v["id"]
        base = unreal.Vector(5400.0, 73000.0 + i * 3500.0, 0.0)
        rot = unreal.Rotator(roll=0.0, pitch=0.0, yaw=90.0)
        actor = ss.spawn_actor_from_class(bp, base, rot)
        actor.set_actor_label(f"ZZ_TEMP_SoftGoods_VS_{tag}")
        temps.append(actor)
        if v["floor"]:
            fa = ss.spawn_actor_from_class(floor_bp, base, rot)
            fa.set_actor_label(f"ZZ_TEMP_SoftGoods_VSFloor_{tag}")
            temps.append(fa)
        lamp = ss.spawn_actor_from_class(unreal.SpotLight, unreal.Vector(base.x - 1600.0, base.y, 1400.0),
                                         unreal.Rotator(roll=0.0, pitch=-35.0, yaw=0.0))
        lamp.set_actor_label(f"ZZ_TEMP_SoftGoods_VSLamp_{tag}")
        lamp.spot_light_component.set_editor_property("intensity", 30000.0)
        lamp.spot_light_component.set_editor_property("attenuation_radius", 8000.0)
        lamp.spot_light_component.set_editor_property("outer_cone_angle", 60.0)
        temps.append(lamp)
        cloth = actor.get_components_by_class(unreal.ChaosClothComponent)[0]
        cloth.set_asset(built[v["cloth"]])
        cloth.set_editor_property("suspend_simulation", False)
        cc, rt, sc, srt, side_center = capture_rig(tag, base, actor)
        report["variants"][tag] = {"cloth": v["cloth"], "floor": v["floor"], "base": [base.x, base.y, base.z],
                                   "side_center": [side_center.x, side_center.y, side_center.z]}
        runs.append({"v": v, "tag": tag, "actor": actor, "cloth": cloth, "base": base, "cc": cc, "rt": rt, "sc": sc, "srt": srt})


state = {"t": 0.0, "base_t": 0.0, "sim_on": False, "next_cap": COST_S, "cap": 0, "handle": None}
report["cost"] = {"baseline_wall": [], "sim_nocapture_wall": []}
state["last_wall"] = None


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
    report["dirty_content_after"] = sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    # hold/drop in CAPTURE units for the measurer (captures follow tick delta, not a fixed rate)
    caps = report["captures"]
    first_drop = next((c for c, t in caps if t >= HOLD_S), None)
    first_done = next((c for c, t in caps if t >= HOLD_S + DROP_S), None)
    if first_drop is not None and first_done is not None:
        report["hold"], report["drop"] = first_drop, max(1, first_done - first_drop)
    with open(LOG, "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1, default=str)
    unreal.log(f"PUSS_SOFTGOODS_CARRIAGE_DONE|captures={len(report['captures'])}|stray={len(report['stray_after'])}"
               f"|dirty={report['dirty_content_after']}|errors={len(report['errors'])}")


def tick(delta):
    try:
        now = time.perf_counter()
        wall = None if state["last_wall"] is None else now - state["last_wall"]
        state["last_wall"] = now
        if not state["sim_on"]:
            if state["base_t"] > 0.5 and wall is not None:      # skip the spawn hitch
                report["cost"]["baseline_wall"].append(round(wall, 4))
            state["base_t"] += delta
            if state["base_t"] >= BASE_S:
                for r in runs:
                    r["cloth"].set_simulate_in_editor(True)
                state["sim_on"] = True
            return
        report["deltas"].append(round(delta, 4))
        t = state["t"]
        if t < COST_S:
            if t > 0.5 and wall is not None:
                report["cost"]["sim_nocapture_wall"].append(round(wall, 4))
            state["t"] += delta
            return
        if "readback" not in report:
            report["readback"] = {}
            for r in runs:
                inter = r["cloth"].get_cloth_outfit_interactor()
                if inter is None:
                    report["readback"][r["tag"]] = "no interactor"
                    continue
                names = [str(n) for n in inter.get_all_property_names(-1)]
                rb = {"has_LinearVelocityScale": "LinearVelocityScale" in names}
                if rb["has_LinearVelocityScale"]:
                    v = inter.get_vector_property_value("LinearVelocityScale", 0, unreal.Vector(-1, -1, -1))
                    rb["LinearVelocityScale"] = [v.x, v.y, v.z]
                    rb["AngularVelocityScale"] = inter.get_float_property_value("AngularVelocityScale", 0, -1.0)
                report["readback"][r["tag"]] = rb
        if t >= HOLD_S:
            s = min(1.0, (t - HOLD_S) / JERK_S)
            for r in runs:
                b = r["base"]
                jx, jz = r["v"]["jerk"]
                r["actor"].set_actor_location(unreal.Vector(b.x + JERK_CM * jx * s, b.y, b.z + JERK_CM * jz * s), False, False)
        if t >= state["next_cap"]:
            c = state["cap"]
            for r in runs:
                r["cc"].capture_scene()
                unreal.RenderingLibrary.export_render_target(world, r["rt"], OUT, f"{r['tag']}_{c:04d}.png")
                r["sc"].capture_scene()
                unreal.RenderingLibrary.export_render_target(world, r["srt"], OUT, f"{r['tag']}_side_{c:04d}.png")
            report["captures"].append([c, round(t, 3)])
            state["cap"] += 1
            state["next_cap"] += CAP_S
        state["t"] += delta
        if state["t"] > HOLD_S + JERK_S + SETTLE_S:
            cleanup()
    except Exception as exc:  # noqa: BLE001
        report["errors"].append(f"tick {exc}")
        cleanup()


try:
    setup()
except Exception as exc:  # noqa: BLE001
    report["errors"].append(f"setup {exc}")
    cleanup()
    raise
state["handle"] = unreal.register_slate_post_tick_callback(tick)
unreal.log("PUSS_SOFTGOODS_CARRIAGE_STARTED")
