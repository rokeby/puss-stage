"""Clear a no-net-change dirty map (e.g. a transient-capture bench) with a VERIFIED
save. It saves only if nothing evaluated can be baked in:
- no ZZ_/TEMP actors;
- Sequencer closed;
- content 0 dirty; the only dirty map is the show level;
- every Scene 4 hangar hinge, the lattice and the 14 practicals sit EXACTLY at the
  recorded rest pose (packed hinges, lattice at standing z + 1600, lamps at 0 cd),
  which proves no scrubbed fold state is present;
- both Scene 4 handoff cameras sit at their probed transforms (10668.5, 240000,
  180), rot 0, as the Scene Handoff Builder set them.
Refuses otherwise and saves nothing. Lean: all work in main().
"""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
TAG = "RigAtmos.Scene4Hangar"
RECORD = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                      "CodexStructure", "scene4_fold_revert_record.json")
CAMERA = (10668.5, 240000.0, 180.0)


def pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD and ed.get_game_world() is None, "wrong world or PIE"
    assert not unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence(), "Sequencer is open"
    c = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    m = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    assert not c, f"content dirty: {c}"
    assert m in ([], [EXPECTED_WORLD]), f"other maps dirty: {m}"
    if not m:
        unreal.log("LEVEL_VERIFIED_SAVE|nothing to do: the map is clean")
        return
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    assert not any(a.get_actor_label().startswith(("ZZ_", "TEMP", "Temp")) for a in actors), "bench actors in the level"
    mine = {a.get_actor_label(): a for a in actors if TAG in [str(t) for t in a.get_editor_property("tags")]}
    bad = []
    v2_path = RECORD.replace("scene4_fold_revert_record.json", "scene4_v2_record.json")
    if os.path.exists(v2_path):
        # v2: the root hangs at -90; inside it the box rests assembled (hinges 0, the roof -90
        # upright), the lattice flown, practicals and uplights at 0 cd.
        v2 = json.load(open(v2_path, encoding="utf-8"))["rest"]
        checks = {"S4 Hangar Root": v2["root"], "S4 Hangar Roof Hinge": v2["roof"], **v2["internal"]}
        for label, want in checks.items():
            got = float(mine[label].root_component.get_editor_property("relative_rotation").pitch)
            if abs(got - want) > 0.05:
                bad.append(f"{label} pitch {got:.2f}, rest {want}")
        z = float(mine["S4 Hangar Lattice Fly"].root_component.get_editor_property("relative_location").z)
        if abs(z - v2["lattice_root_z"]) > 0.5:
            bad.append(f"lattice root-relative z {z:.1f}")
        for label in v2["lamps"] + v2["uplights"]:
            cd = mine[label].get_component_by_class(unreal.LightComponent).get_editor_property("intensity")
            if abs(cd) > 1e-3:
                bad.append(f"{label} {cd:.1f} cd")
        rest = {"packed": {}, "lamps": [], "lattice_standing_z": None}
    else:
        rest = json.load(open(RECORD, encoding="utf-8"))["rest_pose"]
    for label, (axis, packed) in rest["packed"].items():
        r = mine[label].root_component.get_editor_property("relative_rotation")
        got = r.roll if axis == "X" else r.pitch
        if abs(got - packed) > 0.05:
            bad.append(f"{label} {axis}={got:.2f}, rest {packed}")
    if rest["lattice_standing_z"] is not None:
        fly_z = mine["S4 Hangar Lattice Fly"].get_actor_location().z
        if abs(fly_z - (rest["lattice_standing_z"] + 1600.0)) > 0.5:
            bad.append(f"lattice z {fly_z:.1f}")
    for label in rest["lamps"]:
        cd = mine[label].get_component_by_class(unreal.SpotLightComponent).get_editor_property("intensity")
        if abs(cd) > 1e-3:
            bad.append(f"{label} {cd:.1f} cd")
    for a in actors:   # uplights (if present) also rest at 0 cd; the fold strikes them
        if "RigAtmos.Scene4Uplight" in [str(t) for t in a.get_editor_property("tags")]:
            sc = a.get_component_by_class(unreal.SpotLightComponent)
            if sc and abs(sc.get_editor_property("intensity")) > 1e-3:
                bad.append(f"{a.get_actor_label()} {sc.get_editor_property('intensity'):.1f} cd")
    for a in actors:
        if "Scene 4" in a.get_actor_label() and "Handoff Camera" in a.get_actor_label():
            loc, rot = a.get_actor_location().to_tuple(), a.get_actor_rotation()
            if any(abs(loc[i] - CAMERA[i]) > 0.5 for i in range(3)) or max(abs(rot.roll), abs(rot.pitch), abs(rot.yaw)) > 0.05:
                bad.append(f"{a.get_actor_label()} at {loc} {rot}")
            # Look & camera key their pitch on the CAMERA COMPONENT: a scrub must not leave it pitched.
            cc = a.get_component_by_class(unreal.CineCameraComponent)
            if cc:
                cr = cc.get_editor_property("relative_rotation")
                if max(abs(cr.roll), abs(cr.pitch), abs(cr.yaw)) > 0.05:
                    bad.append(f"{a.get_actor_label()} camera component pitched {cr}")
    assert not bad, f"evaluated state present, NOT saved: {bad}"
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "level save failed"
    m2 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    unreal.log(f"LEVEL_VERIFIED_SAVE_OK|rest_pose=verified|cameras=verified|dirty_maps_after={m2}")


main()
