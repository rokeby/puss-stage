import unreal
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not levels.is_in_play_in_editor()
targets=[]
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if a.get_actor_label() in ['BP_OrtalanSheet','BP_OrtalanSheet2','BP_OrtalanSheet3','BP_OrtalanSheet4']:
        assert a.get_editor_property('hidden')
        targets.append(a)
assert len(targets)==4
layers=unreal.get_editor_subsystem(unreal.LayersSubsystem)
layers.add_actors_to_layer(targets,'Shore_Retained_Mannys')
layers.set_layer_visibility('Shore_Retained_Mannys',False)
assert all(a.is_hidden_ed() for a in targets)
for a in targets:
    for name in ['SkeletalMesh','ChaosCloth']:
        c=next(c for c in a.get_components_by_class(unreal.PrimitiveComponent) if c.get_name()==name)
        c.set_editor_properties({'visible':False,'hidden_in_game':True})
assert levels.save_current_level()
unreal.log('RETAINED_MANNY_PERSISTENT_EDITOR_HIDING_SAVED|four_original_actors_retained')
