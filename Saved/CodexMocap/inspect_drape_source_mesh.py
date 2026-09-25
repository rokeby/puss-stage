import json
import pathlib
import unreal
folder=pathlib.Path('E:/PussStage/Saved/CodexMocap')
mesh=unreal.load_asset('/Game/Scenes/SM_OrtalanSheet')
out={'bounds':str(mesh.get_bounds()),'api':{}}
for name in ['GeometryScript_AssetUtils','GeometryScript_MeshQueries','GeometryScript_ListUtilityFunctions','DataflowEdNode']:
    cls=getattr(unreal,name,None)
    out['api'][name]={n:getattr(getattr(cls,n),'__doc__',None) for n in dir(cls) if any(k in n for k in ['copy_mesh','vertex','convert','property'])}
(folder/'drape_source_mesh_api.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
unreal.LevelSequenceEditorBlueprintLibrary.pause()
unreal.log('SHORE_DRAPE_SOURCE_MESH_INSPECTED|' + out['bounds'])
