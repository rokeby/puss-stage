import builtins
import json
import pathlib
import unreal
folder=pathlib.Path('E:/PussStage/Saved/CodexMocap')
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not levels.is_in_play_in_editor()
assert not hasattr(builtins,'PUSS_SHORE_CLOTH_QC_HANDLE')
unreal.LevelSequenceEditorBlueprintLibrary.pause()
unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
for p in ['/Game/Metahuman/ShoreCast_20260910/Review/LS_ShoreDrape_Gentle']:
    assert unreal.EditorAssetLibrary.save_asset(p,only_if_is_dirty=True)
assert levels.save_current_level()
dirty=list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
assert not dirty,[p.get_path_name() for p in dirty]
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if world.get_path_name().split('.')[0]!='/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice':
    assert levels.load_level('/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice')
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
rows=[]
for a in actors:
    if 'Ortalan' in a.get_class().get_name() or 'Clam' in a.get_actor_label() or 'source_Anim'==a.get_actor_label():
        row={'actor':a.get_path_name(),'label':a.get_actor_label(),'class':a.get_class().get_path_name(),'location':list(a.get_actor_location().to_tuple()),'rotation':list(a.get_actor_rotation().to_tuple()),'scale':list(a.get_actor_scale3d().to_tuple()),'hidden_game':a.get_editor_property('hidden'),'components':[]}
        for c in a.get_components_by_class(unreal.SceneComponent):
            row['components'].append({'name':c.get_name(),'class':c.get_class().get_name(),'world_location':list(c.get_world_location().to_tuple())})
        rows.append(row)
(folder/'clam_live_placement_inspection.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
unreal.log('CLAM_PRODUCTION_WORLD_INSPECTED|actors='+str(len(rows)))
