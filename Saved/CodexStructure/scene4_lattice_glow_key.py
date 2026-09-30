"""Scene 4 lattice glow, keyed (30 Sep): the glow lights must REST DARK.

Found by projection (p04_end_lights_projection_readonly.py): at rest the lattice's first
row hangs only 3.75 m below floor level in the open-topped pit, so the 24 glow lights
(scene4_lattice_glow_apply.py, 20 cd) showed as a row of warm pools at the end of
Passage 4, before anything rises. Gary's rule is that nothing of the Scene shows until
the rise. So, like the practicals and uplights:
- the level holds every glow light at 0 cd (the rest state);
- LS_S4_HangarRise fades them 0 -> GLOW_CD over RAMP (4 -> 8 s by default): the lattice
  crosses the floor line at about 3-4 s and sweeps up through the frame 8-12 s, the
  darkest moment Gary described. Sequencer restores 0 on leaving the Scene.
Refuses if the glow lights are already bound (revert first), so it can never double a track.
Guards: world, no PIE, 0+0 dirty, no Sequencer, no ZZ_. Backs up the sequence and the
level to Backups/PreLatticeGlowKey-<ts>; plain record written first; read-back of every
key and every rest intensity; saves only the sequence and the level; dirty 0+0 after.
Revert: scene4_lattice_glow_key_revert.py. Lean: all work in main()."""
import datetime
import json
import os
import shutil

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SEQ = "/Game/InfinityStage/RigAtmos/LS_S4_HangarRise"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "scene4_lattice_glow_key_record.json")
KEY = {"ramp_s": (4.0, 8.0), "cd": 20.0}
KEY.update(globals().get("LATTICE_GLOW_KEY", {}))


def fail(msg):
    unreal.log_error("LATTICE_GLOW_KEY_STOPPED|" + msg)
    raise RuntimeError(msg)


def main():
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
    glows = sorted((a for a in actors if a.get_actor_label().startswith("S4 Lattice Glow ")), key=lambda a: a.get_actor_label())
    if len(glows) != 24:
        fail(f"expected 24 glow lights, found {len(glows)}")
    seq = unreal.load_asset(SEQ)
    fps = seq.get_display_rate().numerator / seq.get_display_rate().denominator
    end = seq.get_playback_end()
    existing = {str(b.get_display_name()): b for b in seq.get_bindings()}
    if any(n.startswith("S4 Lattice Glow ") for n in existing):
        fail("the glow lights are already bound in the sequence: run scene4_lattice_glow_key_revert.py first")
    before = {a.get_actor_label(): float(a.get_component_by_class(unreal.PointLightComponent).get_editor_property("intensity")) for a in glows}
    record = {"written": datetime.datetime.now().isoformat(timespec="seconds"), "rest_cd_before": before, "key": KEY,
              "bindings_before": sorted(existing)}
    with open(RECORD, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1)
        fh.flush()
        os.fsync(fh.fileno())
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = os.path.join(project, "Backups", "PreLatticeGlowKey-" + datetime.datetime.now().strftime("%Y%m%d-%H%M"))
    os.makedirs(backup, exist_ok=True)
    shutil.copy2(os.path.join(project, "Content", *EXPECTED_WORLD[len("/Game/"):].split("/")) + ".umap", backup)
    shutil.copy2(os.path.join(project, "Content", *SEQ[len("/Game/"):].split("/")) + ".uasset", backup)
    shutil.copy2(RECORD, backup)

    r0, r1 = KEY["ramp_s"]
    frame = lambda s: unreal.FrameNumber(int(round(s * fps)))
    keyed = 0
    for a in glows:
        comp = a.get_component_by_class(unreal.PointLightComponent)
        comp.set_editor_property("intensity", 0.0)                 # the rest state: dark
        binding = seq.add_possessable(comp)
        tr = binding.add_track(unreal.MovieSceneFloatTrack)
        tr.set_property_name_and_path("Intensity", "Intensity")
        sec = tr.add_section()
        sec.set_range(0, end)
        ch = sec.get_all_channels()[0]
        for t_s, v in ((0.0, 0.0), (r0, 0.0), (r1, KEY["cd"])):
            ch.add_key(frame(t_s), float(v), time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                       interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
        keyed += 1

    # Read back: every glow at 0 cd in the level, and one Intensity track per glow reading 0 -> cd.
    bad = [a.get_actor_label() for a in glows if abs(a.get_component_by_class(unreal.PointLightComponent).get_editor_property("intensity")) > 1e-3]
    tracks = 0
    for bnd in seq.get_bindings():
        for t in bnd.get_tracks():
            if isinstance(t, unreal.MovieSceneFloatTrack) and str(t.get_property_name()) == "Intensity":
                vals = [k.get_value() for k in t.get_sections()[0].get_all_channels()[0].get_keys()]
                if len(vals) == 3 and abs(vals[-1] - KEY["cd"]) < 1e-3:
                    tracks += 1
    if tracks != 24:
        fail(f"{tracks} glow intensity tracks read back, expected 24 (NOTHING saved; backup {backup})")
    if bad:
        fail(f"glow lights not dark at rest: {bad}")
    c1 = sorted(p.get_path_name().split(".")[0] for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m1 = sorted(p.get_path_name().split(".")[0] for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    if c1 != [SEQ] or m1 != [EXPECTED_WORLD]:
        fail(f"unexpected dirty set: {c1} {m1} (NOTHING saved; backup {backup})")
    if not unreal.EditorAssetLibrary.save_asset(SEQ, only_if_is_dirty=False):
        fail("sequence save failed")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed")
    after = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()), len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
    unreal.log(f"LATTICE_GLOW_KEY_OK|keyed={keyed}|glow_tracks_read_back={tracks}|rest=0cd|ramp={r0}-{r1}s|cd={KEY['cd']}|backup={backup}|dirty_after={after[0]}+{after[1]}")


main()
