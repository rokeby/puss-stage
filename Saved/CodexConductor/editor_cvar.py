"""Set console variables in the EDITOR world (live, not saved). Args editor_cvar_args.json {"cvars":[...]}. EDITOR_CVAR_OK."""
import json
def main():
    import unreal
    a = json.load(open("E:/PussStage/Saved/CodexConductor/editor_cvar_args.json"))
    w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    for c in a["cvars"]:
        unreal.SystemLibrary.execute_console_command(w, c)
    unreal.log("EDITOR_CVAR_OK|%s" % a["cvars"])
main()
