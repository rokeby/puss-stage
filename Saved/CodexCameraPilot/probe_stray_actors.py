"""Read-only: stray transient capture actors and dirty packages. Marker: PUSS_STRAY_PROBE"""
import unreal
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
stray = [a.get_actor_label() for a in actors if a.get_class().get_name() == "SceneCapture2D" or a.get_actor_label().startswith("ZZ_")]
content = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
maps = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
unreal.log(f"PUSS_STRAY_PROBE|stray={stray}|content={content}|maps={maps}")
