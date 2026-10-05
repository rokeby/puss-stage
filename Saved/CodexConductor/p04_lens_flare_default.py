"""Gary 5 Oct: P04 camera lens flare back to the engine default (1.0) by clearing the tune-4 override (was 0.35).

Backs up the level, records the before value, edits ONLY the P04 camera rig's post-process override, saves only the
level, reads back. Refuses on PIE or a dirty census.
"""
import datetime
import json
import os
import shutil

import unreal

RUN = datetime.datetime.now().strftime("FLARE-%Y%m%d-%H%M%S")
BASE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"


def stop(msg):
    unreal.log_error("P04_FLARE_STOPPED|run=%s|%s" % (RUN, msg))
    raise RuntimeError(msg)


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if editor.get_game_world() is not None:
    stop("PIE_ACTIVE")
if census() != {"content": [], "maps": []}:
    stop("DIRTY_BEFORE|" + json.dumps(census()))
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
passages = [a for a in actors if a.get_class().get_name() == "InfinityStagePassageActor"
            and str(a.get_actor_label()).startswith("Passage 04")]
if len(passages) != 1:
    stop("P04_ACTOR_COUNT|%d" % len(passages))
rigs = [a for a in actors if a.get_class().get_name() == "InfinityStageCameraRig"
        and a.get_editor_property("passage_actor") == passages[0]]
if len(rigs) != 1:
    stop("P04_RIG_COUNT|%d" % len(rigs))
camera = rigs[0].get_editor_property("camera")
settings = camera.get_editor_property("post_process_settings")
before = {"override": bool(settings.get_editor_property("override_lens_flare_intensity")),
          "value": float(settings.get_editor_property("lens_flare_intensity"))}
backup = "E:/PussStage/Backups/PreP04FlareDefault-" + RUN
os.makedirs(backup)
shutil.copy2(UMAP, backup)
with open(os.path.join(BASE, "p04_lens_flare_default_record.json"), "w", encoding="utf-8") as h:
    json.dump({"run": RUN, "rig": str(rigs[0].get_actor_label()), "before": before, "backup": backup}, h, indent=1)
camera.modify()
settings.set_editor_property("override_lens_flare_intensity", False)
settings.set_editor_property("lens_flare_intensity", 1.0)
camera.set_editor_property("post_process_settings", settings)
after = camera.get_editor_property("post_process_settings")
if bool(after.get_editor_property("override_lens_flare_intensity")):
    stop("READBACK_OVERRIDE_STILL_ON")
dirty = census()
if dirty["content"] or dirty["maps"] != [WORLD]:
    stop("DIRTY_SCOPE|" + json.dumps(dirty))
if not unreal.EditorLoadingAndSavingUtils.save_map(editor.get_editor_world(), WORLD):
    stop("SAVE_FAILED")
if census() != {"content": [], "maps": []}:
    stop("POST_SAVE_DIRTY|" + json.dumps(census()))
unreal.log("P04_FLARE_DEFAULT_OK|run=%s|before=%s|override=off(engine default 1.0)|backup=%s"
           % (RUN, json.dumps(before), backup))
