"""Census before/after materialize P02 alone (no Show change). If only the main level dirties, save it (a no-op
re-materialize, what rzswap APPLY would save anyway); if anything else dirties (e.g. /Game/L_KK_children), STOP,
save nothing. Marker RZSWAP_MATPROBE."""
import unreal
GUID = "7FF34BBDA744E406C264A7B7E4DD61D9"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
lib = unreal.EditorLoadingAndSavingUtils
def cen():
    return (sorted(str(p.get_path_name()).split(".")[0] for p in lib.get_dirty_content_packages()),
            sorted(str(p.get_path_name()).split(".")[0] for p in lib.get_dirty_map_packages()))
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if ed.get_game_world() is not None: raise RuntimeError("PIE")
c0 = cen()
if c0 != ([], []):
    unreal.log_error("RZSWAP_MATPROBE|STOP|dirty_at_start=%s" % (c0,)); raise RuntimeError("dirty start")
acts = [a for a in unreal.GameplayStatics.get_all_actors_of_class(ed.get_editor_world(), unreal.InfinityStagePassageActor)
        if str(unreal.GuidLibrary.conv_guid_to_string(a.get_editor_property("passage_guid"))).upper() == GUID]
if len(acts) != 1: raise RuntimeError("P02 actor count %d" % len(acts))
ok = bool(acts[0].materialize_passage())
c1 = cen()
if c1[0] or not set(c1[1]) <= {WORLD}:
    unreal.log_error("RZSWAP_MATPROBE|STOP|materialize=%s|after=%s|NOTHING SAVED" % (ok, c1)); raise RuntimeError("scope")
saved = None
if c1[1]:
    saved = bool(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level())
c2 = cen()
unreal.log("RZSWAP_MATPROBE|OK|materialize=%s|after=%s|saved_level=%s|end=%s" % (ok, c1, saved, c2))
