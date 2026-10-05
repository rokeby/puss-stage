"""Import the music analyses in Saved/InfinityStage/MusicAnalysis (top level) into MM_Pxx_Analysis and relink the Show's
rails, via UInfinityStageCameraPilotLibrary::ImportMusicAnalysis (the Cue Desk 'Link / Reimport Music Analysis', scriptable;
it saves the maps + Show itself, keeps Confirmed/Suggested marker states, refuses during PIE). Guards: no PIE, clean census
before; after: only MM_ maps + the Show may have been saved, census clean. Marker MUSIC_ANALYSIS_IMPORT_OK|..."""
import datetime
import json
import unreal

RUN = datetime.datetime.now().strftime("MAI-%Y%m%d-%H%M%S")
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def main():
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None:
        raise RuntimeError("MUSIC_ANALYSIS_IMPORT_FAILED|run=%s|PIE_ACTIVE" % RUN)
    if census() != {"content": [], "maps": []}:
        raise RuntimeError("MUSIC_ANALYSIS_IMPORT_FAILED|run=%s|DIRTY_BEFORE|%s" % (RUN, json.dumps(census())))
    show = unreal.load_asset(SHOW)
    res = unreal.InfinityStageCameraPilotLibrary.import_music_analysis(show)
    ok, report = (res if isinstance(res, tuple) else (res, ""))
    after = census()
    unreal.log("MUSIC_ANALYSIS_IMPORT_REPORT|run=%s|%s" % (RUN, str(report).replace("\n", " || ")[:3000]))
    if not ok:
        unreal.log_error("MUSIC_ANALYSIS_IMPORT_FAILED|run=%s|returned_false|census=%s" % (RUN, json.dumps(after)))
        return
    if after != {"content": [], "maps": []}:
        unreal.log_error("MUSIC_ANALYSIS_IMPORT_FAILED|run=%s|DIRTY_AFTER|%s" % (RUN, json.dumps(after)))
        return
    unreal.log("MUSIC_ANALYSIS_IMPORT_OK|run=%s|census_clean=1" % RUN)


main()
