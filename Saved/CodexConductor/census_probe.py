"""Read-only: log the dirty package census and PIE state."""
import json
import unreal
lib = unreal.EditorLoadingAndSavingUtils
c = {"content": sorted(p.get_path_name() for p in lib.get_dirty_content_packages()),
     "maps": sorted(p.get_path_name() for p in lib.get_dirty_map_packages()),
     "pie": unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None}
unreal.log("CENSUS_PROBE|" + json.dumps(c))
