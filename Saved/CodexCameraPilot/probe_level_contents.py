"""Read-only: anything of Look & camera's in the level that should not be. Marker: PUSS_LEVEL_CONTENT_PROBE"""
import unreal
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
pilot = [a.get_actor_label() for a in actors if a.get_actor_label().startswith("PILOT ")]
captures = [a.get_actor_label() for a in actors if a.get_class().get_name() == "SceneCapture2D" or a.get_actor_label().startswith("ZZ_")]
handoff = sorted(a.get_actor_label() for a in actors if isinstance(a, unreal.CineCameraActor) and a.actor_has_tag("InfinityStage.SceneHandoff"))
other_cine = sorted(a.get_actor_label() for a in actors if isinstance(a, unreal.CineCameraActor) and not a.actor_has_tag("InfinityStage.SceneHandoff"))
curtains = [a.get_actor_label() for a in actors if "Curtain" in a.get_class().get_name()]
dirty = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()] + [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
unreal.log(f"PUSS_LEVEL_CONTENT_PROBE|actors={len(actors)}|pilot={pilot}|captures={captures}|handoff_cams={len(handoff)}|other_cine={other_cine}|curtains={curtains}|dirty={dirty}")
