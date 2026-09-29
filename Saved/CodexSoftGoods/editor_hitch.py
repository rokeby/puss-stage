"""EDITOR-ONLY hitch dumps, PIE OFF (29 Sep): the ~1 s rhythm persists with no PIE, so name its owner in the editor.
Mode from editor_hitch_mode.json: "on" (t.HitchFrameTimeThreshold 45 + stat dumphitches) or "off" (toggle back).
Console state only; nothing saved. Parse with Scripts/parse_cloth_dumps.py (it reads every hitch block in the log)."""
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods")


def main():
    with open(os.path.join(HERE, "editor_hitch_mode.json"), encoding="utf-8") as h:
        mode = json.load(h).get("mode")
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        unreal.log("PUSS_SOFTGOODS_EDITOR_HITCH_STOPPED|PIE is running")
        return
    world = editor.get_editor_world()
    if mode in ("ism_off", "ism_on"):
        # Bisect: hide / restore instanced static meshes (the structure kit and wings) in the editor view only.
        unreal.SystemLibrary.execute_console_command(world, f"ShowFlag.InstancedStaticMeshes {0 if mode == 'ism_off' else 2}")
        del world
        unreal.log(f"PUSS_SOFTGOODS_EDITOR_HITCH|{mode}")
        return
    if mode == "on":
        unreal.SystemLibrary.execute_console_command(world, "t.HitchFrameTimeThreshold 45")
    unreal.SystemLibrary.execute_console_command(world, "stat dumphitches")
    del world
    unreal.log(f"PUSS_SOFTGOODS_EDITOR_HITCH|{mode}")


main()
