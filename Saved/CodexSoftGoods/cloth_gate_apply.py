"""Scene-scope the six Shore drape cloth sims (29 Sep; Gary: "least lag", the frame drop is "very core"). NOT RUN:
run only after cloth_gate_measure.py has shown which switch removes the 13.4 ms stall, AND with Gary's yes typed in
the Soft goods session (it edits his Scene 3 sequence and the level).

Design (jump-safe, no C++):
- LEVEL DEFAULT OFF. The six placed BP_Shore0x_Draped actors' ChaosClothComponents get PROPERTY = OFF_VALUE as a
  per-instance override, so every PIE start, and every segment outside Scene 3, costs nothing.
- SCENE 3 TURNS THEM ON. LS_DevScene_03 gets a folder "Soft goods — cloth gate" with one component binding per
  drape and a Bool track on PROPERTY: an INFINITE section keyed ON_VALUE, completion mode RESTORE STATE.
  Sequencer evaluates it at whatever frame Scene 3 is entered, by playing OR by a transport JUMP, and restores the
  level default when Scene 3 is left either way. So a jump into Scene 3 is not a trap.
- PROPERTY choice: bSuspendSimulation (default) FREEZES the last pose when Scene 3 ends, so a drape still on screen
  while Interaction 3 holds the Scene 3 exit camera does not pop. bEnableSimulation would snap to the skinned pose.
  Use bEnableSimulation only if the measurement shows suspend does not remove the stall.

Guards: expected world, no PIE, nothing dirty, no ZZ_/TEMP actors, exactly six drape components, no existing
PROPERTY track in LS_DevScene_03. Backs up the level and LS_DevScene_03 to Backups/PreClothGate-<ts>/ first. Saves
ONLY those two, and only if nothing else went dirty. Revert: restore the two files from the backup (with the editor
closed), or delete the folder's bindings and reset the six overrides.
Crash rules: all inside main(), no UE objects at module level.
"""
import datetime
import json
import os
import shutil

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SCENE3 = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
PROPERTY = "bSuspendSimulation"          # or "bEnableSimulation" if the measurement says so
OFF_VALUE = True if PROPERTY == "bSuspendSimulation" else False
ON_VALUE = not OFF_VALUE
FOLDER = "Soft goods — cloth gate"


def project():
    return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())


def dirty():
    return sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + \
        sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())


def content_file(asset_path, ext):
    return os.path.join(project(), "Content", *asset_path[len("/Game/"):].split("/")) + ext


def is_off(comp):
    return comp.is_simulation_suspended() if PROPERTY == "bSuspendSimulation" else not comp.is_simulation_enabled()


def set_level_default(comp):
    py_name = PROPERTY[1:2].lower() + "".join("_" + ch.lower() if ch.isupper() else ch for ch in PROPERTY[2:])
    comp.modify()
    try:
        comp.set_editor_property(py_name, OFF_VALUE)
    except Exception:  # noqa: BLE001
        comp.call_method("SuspendSimulation") if PROPERTY == "bSuspendSimulation" else comp.set_enable_simulation(False)
    return is_off(comp)


def main():
    report = {"ok": False, "property": PROPERTY}
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods",
                       "cloth_gate_apply.json")

    def finish(msg):
        report["message"] = msg
        with open(out, "w", encoding="utf-8") as h:
            json.dump(report, h, indent=1, default=str)
        unreal.log(("PUSS_SOFTGOODS_CLOTH_GATE_APPLIED|" if report["ok"] else "PUSS_SOFTGOODS_CLOTH_GATE_STOPPED|") + msg)

    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world.get_outermost().get_name() != EXPECTED_WORLD or editor.get_game_world() is not None:
        return finish("unsafe editor state (wrong world or PIE running)")
    if dirty():
        return finish(f"refusing: dirty packages {dirty()}")
    ss = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = ss.get_all_level_actors()
    benches = [a.get_actor_label() for a in actors if a.get_actor_label().startswith(("ZZ_", "TEMP"))]
    if benches:
        return finish(f"refusing: bench actors in the level {benches}")
    drapes = []
    for a in actors:
        if a.get_class().get_name().startswith("BP_Shore0") and a.get_class().get_name().endswith("_Draped_C"):
            for comp in a.get_components_by_class(unreal.ActorComponent):
                if comp.get_class().get_name() == "ChaosClothComponent":
                    drapes.append((a, comp))
    del actors
    report["drapes"] = [a.get_actor_label() for a, _ in drapes]
    if len(drapes) != 6:
        return finish(f"refusing: expected six drape cloth components, found {report['drapes']}")
    seq = unreal.load_asset(SCENE3)
    for b in seq.get_bindings():
        for t in b.get_tracks():
            if t.get_class().get_name() == "MovieSceneBoolTrack" and str(t.get_display_name()) in (PROPERTY, PROPERTY[1:]):
                return finish(f"refusing: LS_DevScene_03 already has a {PROPERTY} track on '{b.get_display_name()}'")

    backup = os.path.join(project(), "Backups", "PreClothGate-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(backup, exist_ok=True)
    shutil.copy2(content_file(EXPECTED_WORLD, ".umap"), backup)
    shutil.copy2(content_file(SCENE3, ".uasset"), backup)
    report["backup"] = backup

    try:
        start = seq.get_playback_start()
        folder = seq.add_root_folder_to_sequence(FOLDER)
        report["rows"] = []
        for actor, comp in drapes:
            off_ok = set_level_default(comp)
            binding = seq.add_possessable(comp)
            parent = binding.get_parent()
            if not parent or not parent.is_valid():
                raise RuntimeError(f"{actor.get_actor_label()}: the component binding has no parent actor binding, so it "
                                   "may not resolve inside the Master")
            track = binding.add_track(unreal.MovieSceneBoolTrack)
            track.set_property_name_and_path(PROPERTY, PROPERTY)
            section = track.add_section()
            section.set_start_frame_bounded(False)
            section.set_end_frame_bounded(False)
            channel = section.get_all_channels()[0]
            channel.set_default(ON_VALUE)
            channel.add_key(unreal.FrameNumber(start), ON_VALUE)
            section.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
            try:
                folder.add_child_object_binding(parent)
            except Exception:  # noqa: BLE001
                pass
            report["rows"].append({"actor": actor.get_actor_label(), "level_default_off": off_ok,
                                   "binding": str(binding.get_display_name()),
                                   "parent": str(parent.get_display_name())})
            del binding, parent, track, section, channel
        del folder
    except Exception as exc:  # noqa: BLE001
        report["dirty_after_failure"] = dirty()
        return finish(f"FAILED mid-authoring, NOTHING saved (relaunch to discard; backup {backup}): {exc}")
    del drapes
    if not all(r["level_default_off"] for r in report["rows"]):
        return finish(f"level default did not read back OFF {report['rows']}; NOTHING saved (relaunch to discard)")
    expected = {EXPECTED_WORLD, SCENE3}
    now = dirty()
    report["dirty_before_save"] = now
    if [p for p in now if p not in expected]:
        return finish(f"unexpected dirty packages {now}; NOTHING saved (relaunch to discard; backup {backup})")
    saved = {SCENE3: unreal.EditorAssetLibrary.save_asset(SCENE3, only_if_is_dirty=False),
             EXPECTED_WORLD: unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD)}
    del seq, world
    report["saved"] = saved
    report["dirty_final"] = dirty()
    report["ok"] = all(saved.values()) and not report["dirty_final"]
    finish(f"property={PROPERTY}|saved={saved}|rows={len(report['rows'])}|dirty_final={report['dirty_final']}|backup={backup}")


main()
