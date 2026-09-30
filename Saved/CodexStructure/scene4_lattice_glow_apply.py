"""Scene 4 lattice glow (30 Sep; Gary: the lattice in the darkest moment is "too dark",
reads "abstract", the "sense of architecture might be stronger if they were a bit
brighter even in the darkest moment"). Conductor-approved as a reversible change.

Measured first (lattice_probe_readonly.py): the 24 lattice bulbs are EMISSIVE cubes
only, no light rides the lattice, and its 14 beams and 3 rails are M_Metal_Black_01
(about 4% reflectance, the plate that stayed black under 10,000 cd). So nothing can
light the structure: brighter dots would still be dots. Two parts, each optional:
- GLOW: a small shadowless warm point light AT each bulb, attached to it, so it rides
  the lattice fly and the root; the beams and rails around each bulb catch its light.
  Local (radius 8 m) and low, so the dark stays dark: architecture inside it.
- MATERIAL: the 17 beams and rails to a lighter steel that can catch light at all
  (default StarterContent M_Metal_Burnished_Steel; plain, no per-instance data).
Parameters: LATTICE_GLOW in globals. Dry run (LATTICE_GLOW_DRY_RUN) writes nothing.
Apply: guards, plain-string/number revert record BEFORE any change, level backup,
idempotent (tag RigAtmos.LatticeGlow), read-back, level saved, dirty 0+0 after.
Revert: scene4_lattice_glow_revert.py. Lean: all work in main().
"""
import datetime
import json
import os
import shutil

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "scene4_lattice_glow_record.json")
TAGS = ("RigAtmos.Scene4Hangar", "RigAtmos.LatticeGlow")
GLOW = {"lights": True, "candela": 20.0, "radius_cm": 800.0, "kelvin": 2700.0, "source_radius_cm": 4.0,
        "material": "/Game/StarterContent/Materials/M_Metal_Burnished_Steel.M_Metal_Burnished_Steel"}
GLOW.update(globals().get("LATTICE_GLOW", {}))


def fail(msg):
    unreal.log_error("LATTICE_GLOW_STOPPED|" + msg)
    raise RuntimeError(msg)


def main():
    dry = bool(globals().get("LATTICE_GLOW_DRY_RUN"))
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
        fail("wrong world, or PIE")
    if unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
        fail("something is already dirty")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
        fail("Sequencer is open")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    if any(a.get_actor_label().startswith("ZZ_") for a in actors):
        fail("bench actors (ZZ_) in the level")
    by_label = {a.get_actor_label(): a for a in actors}
    bulbs = sorted(l for l in by_label if l.startswith("S4 Lattice Bulb "))
    frame_pieces = sorted(l for l in by_label if l.startswith("S4 Hangar Lattice Beam ") or l.startswith("S4 Hangar Lattice Rail "))
    if len(bulbs) != 24 or len(frame_pieces) != 17:
        fail(f"expected 24 bulbs and 17 beams/rails, found {len(bulbs)} and {len(frame_pieces)}")
    mat = unreal.load_asset(GLOW["material"]) if GLOW.get("material") else None
    if GLOW.get("material") and not isinstance(mat, unreal.MaterialInterface):
        fail(f"{GLOW['material']} did not load")
    glow_labels = {b: "S4 Lattice Glow " + b.split()[-1] for b in bulbs}
    existing = {l for l in glow_labels.values() if l in by_label}
    mats_before = {}
    for l in frame_pieces:
        smc = by_label[l].get_component_by_class(unreal.StaticMeshComponent)
        mats_before[l] = [m.get_path_name() if m else None for m in smc.get_materials()]
    plan = {"lights": len(bulbs) if GLOW["lights"] else 0, "already": len(existing), "material_to": GLOW.get("material"),
            "material_from": sorted({p for v in mats_before.values() for p in v if p}), "glow": GLOW}
    unreal.log(f"LATTICE_GLOW_PLAN|{json.dumps(plan)}")
    if dry:
        unreal.log("LATTICE_GLOW_DRY_RUN_OK|mutated=0")
        return

    old = json.load(open(RECORD, encoding="utf-8")) if os.path.exists(RECORD) else {}
    record = {"written": datetime.datetime.now().isoformat(timespec="seconds"),
              "created_lights": sorted(set(old.get("created_lights", [])) | ({glow_labels[b] for b in bulbs} - existing if GLOW["lights"] else set())),
              "materials_before": old.get("materials_before", mats_before), "glow": GLOW}
    with open(RECORD, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1)
        fh.flush()
        os.fsync(fh.fileno())
    if json.load(open(RECORD, encoding="utf-8"))["materials_before"] != record["materials_before"]:
        fail("revert record did not read back")
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = os.path.join(project, "Backups", "PreLatticeGlow-" + datetime.datetime.now().strftime("%Y%m%d-%H%M"))
    os.makedirs(backup, exist_ok=True)
    shutil.copy2(os.path.join(project, "Content", *EXPECTED_WORLD[len("/Game/"):].split("/")) + ".umap", backup)
    shutil.copy2(RECORD, backup)

    if GLOW["lights"]:
        for b in bulbs:
            bulb = by_label[b]
            label = glow_labels[b]
            light = by_label.get(label)
            if light is None:
                light = sub.spawn_actor_from_class(unreal.PointLight, bulb.get_actor_location(), unreal.Rotator(0.0, 0.0, 0.0))
                light.set_actor_label(label)
                light.set_editor_property("tags", [unreal.Name(t) for t in TAGS])
                light.attach_to_actor(bulb, unreal.Name("None"), unreal.AttachmentRule.KEEP_WORLD,
                                      unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)
            light.modify()
            c = light.get_component_by_class(unreal.PointLightComponent)
            c.set_mobility(unreal.ComponentMobility.MOVABLE)
            c.set_editor_property("intensity_units", unreal.LightUnits.CANDELAS)
            c.set_editor_property("intensity", GLOW["candela"])
            c.set_editor_property("attenuation_radius", GLOW["radius_cm"])
            c.set_editor_property("use_temperature", True)
            c.set_editor_property("temperature", GLOW["kelvin"])
            c.set_editor_property("source_radius", GLOW["source_radius_cm"])
            c.set_editor_property("cast_shadows", False)
    if mat:
        for l in frame_pieces:
            a = by_label[l]
            a.modify()
            smc = a.get_component_by_class(unreal.StaticMeshComponent)
            for i in range(len(smc.get_materials())):
                smc.set_material(i, mat)

    lights = [a for a in sub.get_all_level_actors() if a.get_actor_label().startswith("S4 Lattice Glow ")]
    worst = 0.0
    for a in lights:
        bulb = by_label["S4 Lattice Bulb " + a.get_actor_label().split()[-1]]
        worst = max(worst, (a.get_actor_location() - bulb.get_actor_location()).length())
        if a.get_attach_parent_actor() != bulb:
            fail(f"{a.get_actor_label()} is not attached to its bulb")
    if GLOW["lights"] and (len(lights) != 24 or worst > 0.5):
        fail(f"{len(lights)} glow lights, worst offset {worst:.2f} cm")
    if mat:
        for l in frame_pieces:
            got = [m.get_path_name() for m in by_label[l].get_component_by_class(unreal.StaticMeshComponent).get_materials()]
            if any(g != mat.get_path_name() for g in got):
                fail(f"{l} material did not land: {got}")
    dirty_c = [x.get_path_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    if dirty_c:
        fail(f"content dirtied: {dirty_c}")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed")
    after = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()), len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
    unreal.log(f"LATTICE_GLOW_OK|lights={len(lights)}|worst_cm={worst:.3f}|material={'swapped' if mat else 'kept'}|backup={backup}|dirty_after={after[0]}+{after[1]}")


main()
