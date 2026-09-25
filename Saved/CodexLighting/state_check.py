import unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
p1 = [a for a in sub.get_all_level_actors() if a.get_class().get_name()=="InfinityStagePassageActor" and a.get_actor_label().startswith("Passage 01")][0]
r = p1.get_editor_property("route"); L = r.get_spline_length()
rolls = [round(r.get_roll_at_distance_along_spline(L*f, unreal.SplineCoordinateSpace.WORLD),2) for f in (0,0.25,0.5,0.75,1.0)]
grid = [a for a in sub.get_all_level_actors() if any(str(t)=="InfinityStage.Gridiron" for t in a.get_editor_property("tags"))]
unreal.log(f"STATE|p1_roll={rolls}|autofit={p1.get_editor_property('auto_fit_straight_route')}|gridiron_actors={len(grid)}|dirty={len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())}+{len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}")
