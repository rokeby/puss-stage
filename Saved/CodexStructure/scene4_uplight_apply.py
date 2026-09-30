"""Light the upper hangar (Gary, 29 Sep late: options 1 + 2, no haze). Look & camera's
tilt stills were black above about 20 deg, because nothing above 12 m had any light.

1. PLATE UPLIGHT: 3 shadowless spots attached to the far wall's hinge, 1.5 m in
   front of its inner face and 30 cm up, aimed 89 deg up, so each beam grazes
   the plate, then the roof held upright above it, to about 86 m. When the roof
   swings over, the beams rake its underside, so the lid closing is visible.
   10,000 cd, cone 8/12.5 deg, 3200 K, 95 m reach. They rest at
   0 cd and strike at 4.0 / 4.15 / 4.3 s in LS_S4_HangarFold, as the practical
   wave ends, before the far wall rises.
2. LATTICE BULBS: 24 small emissive cubes hanging under the 3 lattice rails, 8
   per rail every 7.5 m, attached to the lattice fly, so the grid reads as a lit
   truss flying in. No light cost: a new unlit material,
   /Game/InfinityStage/RigAtmos/M_RigAtmos_WorkBulb (one Constant3Vector into
   Emissive; no nodes are ever deleted).

Everything carries the hangar tag (RigAtmos.Scene4Hangar), so the hangar revert
still removes all of it, plus RigAtmos.Scene4Uplight for this pass's own
revert. Positions are the STANDING-frame offsets from each parent, set as
relative transforms, so they are right whatever pose the level rests in
(packed).

Guards: world, no PIE, 0+0, no ZZ_ actors, Sequencer closed, the 64-actor hangar
and its fold present, the fold clip check OK, no uplight actors yet. Record
first. Saves the new material, the fold sequence and the level. Dry run:
S4_UPLIGHT_DRY_RUN. Revert: scene4_uplight_revert.py. Lean: all work in main().
"""
import datetime
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HANGAR_TAG, TAG = "RigAtmos.Scene4Hangar", "RigAtmos.Scene4Uplight"
FOLD = "/Game/InfinityStage/RigAtmos/LS_S4_HangarFold"
MAT_DIR, MAT_NAME = "/Game/InfinityStage/RigAtmos", "M_RigAtmos_WorkBulb"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "scene4_uplight_record.json")
FOLDER = "Infinity Stage/Scene 04 Hangar"
FPS = 30
UPLIGHT_CD, UPLIGHT_STRIKES, UPLIGHT_RAMP = 10000.0, (4.0, 4.15, 4.3), 0.2
UPLIGHT_DY = (-600.0, 0.0, 600.0)
BULB_EMISSIVE = unreal.LinearColor(24.0, 14.0, 6.0, 1.0)
NAVE_LEN, LATTICE_Z = 6000.0, 1200.0


def fail(message):
    raise RuntimeError(f"S4_UPLIGHT_FAILED|{message}")


def pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
        fail("wrong world, or PIE active")
    c0 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    m0 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    if c0 or m0:
        fail(f"editor already dirty: {c0} {m0}")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
        fail("a sequence is open in Sequencer")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    if any(a.get_actor_label().startswith(("ZZ_", "TEMP", "Temp")) for a in actors):
        fail("bench actors in the level")
    mine = {a.get_actor_label(): a for a in actors if HANGAR_TAG in [str(t) for t in a.get_editor_property("tags")]}
    if any(TAG in [str(t) for t in a.get_editor_property("tags")] for a in mine.values()):
        fail("uplight actors already exist; run scene4_uplight_revert.py first")
    if len(mine) != 64:
        fail(f"expected the 64-actor hangar, found {len(mine)}")
    fold = unreal.EditorAssetLibrary.load_asset(FOLD)
    if not fold:
        fail("the fold sequence is missing")
    if unreal.EditorAssetLibrary.does_asset_exist(f"{MAT_DIR}/{MAT_NAME}"):
        fail("the bulb material already exists; run scene4_uplight_revert.py first")
    cams = [a for a in actors if "Scene 4" in a.get_actor_label() and "Entry Handoff Camera" in a.get_actor_label()]
    if len(cams) != 1:
        fail("Scene 4 Entry Handoff Camera not found")
    x0, cy = cams[0].get_actor_location().x, cams[0].get_actor_location().y
    x1 = x0 + NAVE_LEN
    far, fly = mine["S4 Hangar Far Wall Hinge"], mine["S4 Hangar Lattice Fly"]
    # Standing-frame offsets from each parent's pivot (hinges are unrotated when standing).
    far_pivot = unreal.Vector(x1 + 25.0, cy, 0.0)
    fly_pivot = unreal.Vector((x0 + x1) / 2.0, cy, LATTICE_Z)
    uplights = [{"label": f"S4 Uplight {i + 1}", "rel": [(x1 - 150.0) - far_pivot.x, dy, 30.0], "strike": UPLIGHT_STRIKES[i]}
                for i, dy in enumerate(UPLIGHT_DY)]
    bulbs = [{"label": f"S4 Lattice Bulb {r + 1}-{i + 1}",
              "rel": [(x0 + 375.0 + i * 750.0) - fly_pivot.x, yoff, 11.0]}
             for r, yoff in enumerate((-800.0, 0.0, 800.0)) for i in range(8)]
    record = {"written": datetime.datetime.now().isoformat(timespec="seconds"), "tag": TAG,
              "uplights": uplights, "bulbs": [b["label"] for b in bulbs], "material": f"{MAT_DIR}/{MAT_NAME}",
              "rest": {"uplight_cd": 0.0}}
    with open(RECORD, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1)
        fh.flush()
        os.fsync(fh.fileno())
    unreal.log(f"S4_UPLIGHT_PLAN|uplights={len(uplights)}|bulbs={len(bulbs)}|far_pivot={far_pivot}|x1={x1}")
    if globals().get("S4_UPLIGHT_DRY_RUN"):
        unreal.log("S4_UPLIGHT_DRY_RUN_OK|mutated=0")
        return "dry"

    # ---- The bulb material: new, unlit, one constant into Emissive -----------------
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    mat = tools.create_asset(MAT_NAME, MAT_DIR, unreal.Material, unreal.MaterialFactoryNew())
    if not mat:
        fail("bulb material not created")
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    mel = unreal.MaterialEditingLibrary
    const = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -300, 0)
    const.set_editor_property("constant", BULB_EMISSIVE)
    mel.connect_material_property(const, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.recompile_material(mat)

    cube = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Cube.Cube")
    created = []

    def attach(actor, parent, rel, rot=None):
        actor.attach_to_actor(parent, "", unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD,
                              unreal.AttachmentRule.KEEP_WORLD, False)
        actor.set_actor_relative_location(unreal.Vector(*rel), False, True)
        actor.set_actor_relative_rotation(rot or unreal.Rotator(0.0, 0.0, 0.0), False, True)

    for u in uplights:
        a = sub.spawn_actor_from_class(unreal.SpotLight, far.get_actor_location(), unreal.Rotator(0.0, 0.0, 0.0))
        sc = a.get_editor_property("spot_light_component")
        sc.set_mobility(unreal.ComponentMobility.MOVABLE)
        sc.set_editor_property("intensity_units", unreal.LightUnits.CANDELAS)
        sc.set_editor_property("intensity", 0.0)                     # rest: the fold strikes it
        sc.set_editor_property("attenuation_radius", 9500.0)
        sc.set_editor_property("use_temperature", True)
        sc.set_editor_property("temperature", 3200.0)
        sc.set_editor_property("inner_cone_angle", 8.0)
        sc.set_editor_property("outer_cone_angle", 12.5)
        sc.set_editor_property("cast_shadows", False)
        sc.set_editor_property("volumetric_scattering_intensity", 1.0)
        a.set_actor_label(u["label"])
        a.set_folder_path(FOLDER)
        a.set_editor_property("tags", [HANGAR_TAG, TAG, "Light|role=uplight"])
        attach(a, far, u["rel"], unreal.Rotator(roll=0.0, pitch=89.0, yaw=0.0))
        created.append(u["label"])
    for b in bulbs:
        a = sub.spawn_actor_from_class(unreal.StaticMeshActor, fly.get_actor_location(), unreal.Rotator(0.0, 0.0, 0.0))
        smc = a.get_editor_property("static_mesh_component")
        smc.set_mobility(unreal.ComponentMobility.MOVABLE)
        smc.set_static_mesh(cube)
        smc.set_material(0, mat)
        smc.set_cast_shadow(False)
        a.set_actor_scale3d(unreal.Vector(0.06, 0.06, 0.06))
        a.set_actor_label(b["label"])
        a.set_folder_path(FOLDER)
        a.set_editor_property("tags", [HANGAR_TAG, TAG, "Prop|role=bulb"])
        attach(a, fly, b["rel"])
        created.append(b["label"])

    # ---- Key the uplights' strike in the fold ------------------------------------
    by_label = {a.get_actor_label(): a for a in sub.get_all_level_actors() if TAG in [str(t) for t in a.get_editor_property("tags")]}
    for u in uplights:
        comp = by_label[u["label"]].get_component_by_class(unreal.SpotLightComponent)
        binding = fold.add_possessable(comp)
        track = binding.add_track(unreal.MovieSceneFloatTrack)
        track.set_property_name_and_path("Intensity", "Intensity")
        section = track.add_section()
        section.set_range(0, int(round((fold.get_playback_end_seconds()) * FPS)))
        ch = section.get_all_channels()[0]
        for t_s, v in ((0.0, 0.0), (u["strike"], 0.0), (u["strike"] + UPLIGHT_RAMP, UPLIGHT_CD)):
            ch.add_key(unreal.FrameNumber(int(round(t_s * FPS))), float(v), time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                       interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)

    # ---- Verify, save ---------------------------------------------------------------
    rels = {lab: [round(v, 1) for v in by_label[lab].root_component.get_editor_property("relative_location").to_tuple()]
            for lab in (uplights[0]["label"], bulbs[0]["label"])}
    if len(by_label) != len(uplights) + len(bulbs):
        fail(f"created {len(by_label)} actors")
    c1 = {pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}
    m1 = {pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()}
    if c1 - {FOLD, f"{MAT_DIR}/{MAT_NAME}"} or m1 - {EXPECTED_WORLD}:
        fail(f"out-of-scope dirty: {sorted(c1)} {sorted(m1)}")
    for path in (f"{MAT_DIR}/{MAT_NAME}", FOLD):
        if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
            fail(f"save failed: {path}")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed")
    record["created"] = created
    json.dump(record, open(RECORD, "w", encoding="utf-8"), indent=1)
    c2 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m2 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    unreal.log(f"S4_UPLIGHT_OK|uplights={len(uplights)}|bulbs={len(bulbs)}|rel={rels}|saved=material+fold+level|dirty_after={c2}+{m2}")
    return "applied"


result = main()
