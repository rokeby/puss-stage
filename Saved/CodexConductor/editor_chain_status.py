"""Read-only editor-chain safety status: world, PIE/SIE, and full dirty census."""
import datetime
import json

import unreal

run = datetime.datetime.now().strftime("%H%M%S")
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
census = {
    "content": sorted(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    "maps": sorted(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
}
unreal.log("EDITOR_CHAIN_STATUS|run=%s|pie=%s|world=%s|census=%s" % (
    run,
    "true" if editor.get_game_world() is not None else "false",
    world.get_outermost().get_name() if world is not None else "None",
    json.dumps(census, separators=(",", ":"), sort_keys=True),
))
