"""EDITOR-ONLY Unreal Insights trace (29 Sep): record the ~1 s stutter in the CURRENT (possibly dirty) editor state
before the restart, because if a restart kills the rhythm this will be the only record of it. PIE must be off.
Mode from editor_trace_mode.json: "start" (`trace.file` to a named .utrace, channels default,cpu,frame) or "stop".
Console state only; nothing saved to any asset. The conductor wants only the file path, not the UI."""
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods")


def main():
    with open(os.path.join(HERE, "editor_trace_mode.json"), encoding="utf-8") as h:
        cfg = json.load(h)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        unreal.log("PUSS_SOFTGOODS_EDITOR_TRACE_STOPPED|PIE is running")
        return
    world = editor.get_editor_world()
    if cfg.get("mode") in ("csv_start", "csv_stop"):
        # CSV profiler: one row per frame with per-thread timings (Game / Render / RHI / GPU), written to
        # Saved/Profiling/CSV. The split `stat unit` only draws on screen.
        unreal.SystemLibrary.execute_console_command(world, "csvprofile " + ("start" if cfg["mode"] == "csv_start" else "stop"))
        unreal.log(f"PUSS_SOFTGOODS_EDITOR_TRACE|{cfg['mode']}")
        del world
        return
    if cfg.get("mode") == "start":
        path = cfg["path"]
        unreal.SystemLibrary.execute_console_command(world, f'trace.file "{path}" default,cpu,frame')
        unreal.log(f"PUSS_SOFTGOODS_EDITOR_TRACE|start|{path}")
    else:
        unreal.SystemLibrary.execute_console_command(world, "trace.stop")
        unreal.log("PUSS_SOFTGOODS_EDITOR_TRACE|stop")
    del world


main()
