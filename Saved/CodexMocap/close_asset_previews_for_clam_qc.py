import builtins
import json
import pathlib
import unreal
assert not hasattr(builtins,'PUSS_CLAM_SHORE_QC_HANDLE')
unreal.LevelSequenceEditorBlueprintLibrary.pause()
sub=unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
dirty=list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
assert not dirty,[p.get_path_name() for p in dirty]
root='/Game/Metahuman/ShoreCast_20260910'
cast=json.loads(pathlib.Path('E:/PussStage/Saved/CodexMocap/shore_cast_brief.json').read_text(encoding='utf-8'))['characters']
paths=[root+'/Cloth/CA_ShoreHeadDrape',root+'/Cloth/CA_ShoreHeadDrape_Bowed']
for c in cast:
    cid=c['id']
    paths += [root+'/Assembled/'+cid+'/MHC_'+cid+'/Body/SKM_MHC_'+cid+'_BodyMesh',root+'/Animations/AS_'+cid+'_'+c['take']+'_Full',root+'/SceneCharacters/BP_'+cid+'_Draped',root+'/Characters/MHC_'+cid]
closed=[]
for path in paths:
    assert path.startswith(root+'/')
    asset=unreal.load_asset(path)
    assert asset,path
    count=sub.close_all_editors_for_asset(asset)
    if count:closed.append({'asset':path,'closed':count})
pathlib.Path('E:/PussStage/Saved/CodexMocap/closed_asset_previews.json').write_text(json.dumps({'scope':'Only saved shore assets authored for this task; zero dirty packages checked before closing','closed':closed},indent=2),encoding='utf-8')
unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(unreal.load_asset('/Game/Scenes/LS_Clams'))
unreal.log('CLAM_OWN_SAVED_ASSET_PREVIEWS_CLOSED|'+json.dumps(closed))
