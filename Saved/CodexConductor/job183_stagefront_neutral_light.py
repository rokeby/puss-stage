"""Create or remove one unsaved, exactly-owned neutral stage-front review light."""
import json
import unreal


ARGS = "E:/PussStage/Saved/CodexConductor/job183_stagefront_neutral_light_args.json"
LABEL = "JOB183 TEMP Stage Front Neutral Review Light"
TAG = "JOB183_STAGEFRONT_NEUTRAL_TEMP"


def owned():
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    return [a for a in actors if str(a.get_actor_label()) == LABEL and
            TAG in {str(t) for t in a.get_editor_property("tags")}]


args = json.load(open(ARGS, encoding="utf-8"))
mode = str(args.get("mode", "")).upper()
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if editor.get_game_world() is not None:
    raise RuntimeError("JOB183_NEUTRAL_LIGHT_PIE_ACTIVE")
if mode == "CREATE":
    if owned():
        raise RuntimeError("JOB183_NEUTRAL_LIGHT_ALREADY_EXISTS")
    dirty_content = list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    dirty_maps = list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    if dirty_content or dirty_maps:
        raise RuntimeError("JOB183_NEUTRAL_LIGHT_DIRTY_BEFORE|content=%d|maps=%d" %
                           (len(dirty_content), len(dirty_maps)))
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = subsystem.spawn_actor_from_class(unreal.PointLight,
                                             unreal.Vector(-1450.0, 0.0, 1050.0),
                                             unreal.Rotator())
    if actor is None:
        raise RuntimeError("JOB183_NEUTRAL_LIGHT_SPAWN_FAILED")
    actor.set_actor_label(LABEL, mark_dirty=True)
    actor.set_editor_property("tags", [unreal.Name(TAG)])
    actor.set_folder_path("Codex/Job183/Temporary")
    component = actor.get_editor_property("point_light_component")
    component.set_mobility(unreal.ComponentMobility.MOVABLE)
    component.set_editor_property("intensity_units", unreal.LightUnits.CANDELAS)
    component.set_editor_property("intensity", float(args.get("intensity_cd", 1200.0)))
    component.set_editor_property("use_temperature", True)
    component.set_editor_property("temperature", 5600.0)
    component.set_editor_property("attenuation_radius", 3500.0)
    component.set_editor_property("source_radius", 80.0)
    component.set_editor_property("cast_shadows", False)
    component.set_editor_property("volumetric_scattering_intensity", 0.0)
    maps = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    unreal.log("JOB183_NEUTRAL_LIGHT_CREATE_OK|label=%s|temp=true|saved=false|dirty_maps=%s" % (LABEL, maps))
elif mode == "TUNE":
    hits = owned()
    if len(hits) != 1:
        raise RuntimeError("JOB183_NEUTRAL_LIGHT_TUNE_COUNT|%d" % len(hits))
    component = hits[0].get_editor_property("point_light_component")
    component.set_editor_property("intensity", float(args["intensity_cd"]))
    unreal.log("JOB183_NEUTRAL_LIGHT_TUNE_OK|label=%s|intensity_cd=%.3f|saved=false" %
               (LABEL, float(component.get_editor_property("intensity"))))
elif mode == "REMOVE":
    hits = owned()
    if len(hits) != 1:
        raise RuntimeError("JOB183_NEUTRAL_LIGHT_REMOVE_COUNT|%d" % len(hits))
    ok = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(hits[0])
    if not ok or owned():
        raise RuntimeError("JOB183_NEUTRAL_LIGHT_REMOVE_FAILED")
    unreal.log("JOB183_NEUTRAL_LIGHT_REMOVE_OK|label=%s|saved=false|restart_required=true" % LABEL)
else:
    raise RuntimeError("JOB183_NEUTRAL_LIGHT_BAD_MODE|" + mode)
