"""PIE-only: run console commands from pie_console_args.json {"cmds": [...]} in the game world and log the cvar values after. PIE_CONSOLE_OK|.."""
import json, unreal
a = json.load(open("E:/PussStage/Saved/CodexConductor/pie_console_args.json"))
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if w is None:
    unreal.log_error("PIE_CONSOLE_FAILED|no PIE")
else:
    for c in a["cmds"]:
        unreal.SystemLibrary.execute_console_command(w, c)
    vals = {}
    for n in a.get("read", []):
        try: vals[n] = unreal.SystemLibrary.get_console_variable_int_value(n)
        except Exception as e: vals[n] = repr(e)
    unreal.log("PIE_CONSOLE_OK|cmds=%s|vals=%s" % (a["cmds"], vals))
