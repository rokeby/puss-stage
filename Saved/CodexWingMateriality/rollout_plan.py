"""Read-only: plan the move of every wing MI onto the new masters. Writes rollout_plan.json.

Nothing is changed. rollout_apply.py executes a plan for chosen passages.

Families, from the live components (the Show has no MaterialOverrides, so the mesh
slot MIs are what render):
  V2        MI on M_StageOpeningV2_Relief_Master -> painted master, textures kept
  GroupA    legacy FBX Phong with an unassigned relief MI (P03, P05 clouds) ->
            painted master, BaseColor/OpacityMask from DiffuseColorMap, Height/Normal
            from the relief MI (cross-root for P05 clouds, as the conductor approved)
  GroupB    legacy with no maps -> painted master; generated _H/_N if imported,
            else HasHeightMap=False (luminance relief)
  Edges     legacy per-mesh Edge MIs -> canvas-edge master (V2 edges use the shared
            M_StageOpeningV2_Edge material, which can't be reparented; left as is)
Checks, per mesh: the relief maps must be pixel-registered with the colour texture
(same size), and V2 OpacityMask must be the panel's own BaseColor.
"""
import collections, importlib.util, os
import unreal
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(os.path.dirname(__file__), "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)
MEL = wm.MEL

MASTER = "/Game/Scenes/Wings/PaintedSurface/M_Wing_PaintedSurface_Master"
EDGE = "/Game/Scenes/Wings/PaintedSurface/M_Wing_CanvasEdge_Master"
OLD_RELIEF = "/Game/Scenes/Wings/StageOpeningV2/Materials/M_StageOpeningV2_Relief_Master"
LEGACY = "/InterchangeAssets/Materials/FBXLegacyPhongSurfaceMaterial"
GEN_RELIEF = "/Game/Scenes/Wings/PaintedSurface/GeneratedRelief"
RELIEF_DIRS = ["/Game/Scenes/Wings/Passage03_ShrineToForgetting/Materials/Instances",
               "/Game/Scenes/Wings/Passage05_BirdToMountain/Materials/Instances"]


def tex(mi, name):
    try:
        return wm.pkg(MEL.get_material_instance_texture_parameter_value(mi, name))
    except Exception:  # noqa: BLE001
        return None


def size(path):
    t = unreal.EditorAssetLibrary.load_asset(path) if path else None
    return [t.blueprint_get_size_x(), t.blueprint_get_size_y()] if t else None


wm.editor_ready()
before = wm.dirty()
bounds = wm.read_json("mesh_bounds.json")

# Live components -> mesh -> slot MIs and passages.
meshes = {}
for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if actor.get_class().get_name() != "InfinityStagePassageActor":
        continue
    passage = actor.get_actor_label()[:10].replace("Passage ", "P")
    for comp in actor.get_components_by_class(unreal.InstancedStaticMeshComponent):
        m = wm.pkg(comp.get_editor_property("static_mesh"))
        rec = meshes.setdefault(m, {"slots": [wm.pkg(x) for x in comp.get_materials()], "passages": {}})
        rec["passages"][passage] = rec["passages"].get(passage, 0) + comp.get_instance_count()

relief_by_stem = {}
for folder in RELIEF_DIRS:
    for p in unreal.EditorAssetLibrary.list_assets(folder, recursive=False):
        p = p.split(".", 1)[0]
        stem = p.rsplit("/", 1)[-1]
        if stem.startswith("MI_") and stem.endswith("_Relief"):
            relief_by_stem[stem[3:-7]] = p

plan, problems = [], []
counts = collections.Counter()
for mesh, rec in sorted(meshes.items()):
    b = bounds.get(mesh)
    width, height, half = (b[3] - b[2], b[5] - b[4], (b[1] - b[0]) / 2.0) if b else (500.0, 1000.0, 5.0)
    stem = mesh.rsplit("/", 1)[-1][3:]
    slots = rec["slots"]
    front = unreal.EditorAssetLibrary.load_asset(slots[0])
    parent = wm.pkg(front.get_editor_property("parent")) if isinstance(front, unreal.MaterialInstance) else None
    item = {"mesh": mesh, "passages": rec["passages"], "panel_cm": [round(width, 1), round(height, 1)], "changes": []}
    if parent == OLD_RELIEF:
        family = "V2"
        base, om = tex(front, "BaseColor"), tex(front, "OpacityMask")
        change = {"mi": slots[0], "parent": MASTER, "keep_textures": True,
                  "scalars": {"PanelWidthCm": width, "PanelHeightCm": height}}
        if om != base:
            change["textures"] = {"OpacityMask": base}
            problems.append(f"{slots[0]}: OpacityMask {om} != BaseColor {base} (fixed by plan)")
        item["changes"].append(change)
    elif parent in (MASTER,):
        family = "already"
    elif parent == LEGACY:
        diffuse = tex(front, "DiffuseColorMap")
        relief = relief_by_stem.get(stem)
        gen_h, gen_n = f"{GEN_RELIEF}/T_{diffuse.rsplit('/', 1)[-1]}_H" if diffuse else None, None
        if relief:
            family = "GroupA"
            rmi = unreal.EditorAssetLibrary.load_asset(relief)
            h, n, rbase = tex(rmi, "Height"), tex(rmi, "Normal"), tex(rmi, "BaseColor")
            if size(h) != size(diffuse):
                problems.append(f"{mesh}: relief {h} {size(h)} not registered with colour {diffuse} {size(diffuse)}")
            textures = {"BaseColor": diffuse, "OpacityMask": diffuse, "Height": h, "Normal": n}
            switches = {"HasHeightMap": True}
            item["relief_source"] = relief
            item["relief_basecolor_for_pixel_check"] = rbase
        else:
            family = "GroupB"
            gh = f"{GEN_RELIEF}/T_{diffuse.rsplit('/', 1)[-1]}_H"
            gn = f"{GEN_RELIEF}/T_{diffuse.rsplit('/', 1)[-1]}_N"
            if unreal.EditorAssetLibrary.does_asset_exist(gh) and unreal.EditorAssetLibrary.does_asset_exist(gn):
                textures = {"BaseColor": diffuse, "OpacityMask": diffuse, "Height": gh, "Normal": gn}
                switches = {"HasHeightMap": True}
            else:
                textures = {"BaseColor": diffuse, "OpacityMask": diffuse, "Normal": "/Engine/EngineMaterials/DefaultNormal"}
                switches = {"HasHeightMap": False}
        scalars = {"PanelWidthCm": width, "PanelHeightCm": height,
                   "HeightRatio": 0.006 if switches["HasHeightMap"] else 0.003}
        for mi in dict.fromkeys(slots[:2]):  # Front, Back (distinct MIs on legacy meshes)
            item["changes"].append({"mi": mi, "parent": MASTER, "clear": True, "textures": textures,
                                    "switches": switches, "scalars": scalars})
        edge = unreal.EditorAssetLibrary.load_asset(slots[2])
        if isinstance(edge, unreal.MaterialInstance) and wm.pkg(edge.get_editor_property("parent")) == LEGACY:
            item["changes"].append({"mi": slots[2], "parent": EDGE, "clear": True,
                                    "scalars": {"HalfThicknessCm": half}})
    else:
        family = f"other:{parent}"
    item["family"] = family
    counts[family] += 1
    plan.append(item)

wm.require(wm.dirty() == before, f"dirty changed {wm.dirty()}")
wm.write_json("rollout_plan.json", {"families": dict(counts), "problems": problems, "plan": plan})
unreal.log(f"PUSS_WING_ROLLOUT_PLAN_SUCCESS|{dict(counts)}|problems={len(problems)}")
