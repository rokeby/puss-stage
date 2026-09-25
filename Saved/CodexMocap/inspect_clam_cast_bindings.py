import json
import pathlib
import unreal
seq=unreal.load_asset('/Game/Scenes/LS_Clams')
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
rows=[]
for b in seq.get_bindings():
    parent=b.get_parent()
    rows.append({'name':str(b.get_display_name()),'id':unreal.GuidLibrary.conv_guid_to_string(b.get_id()),'parent':unreal.GuidLibrary.conv_guid_to_string(parent.get_id()),'objects':[o.get_path_name() for o in seq.locate_bound_objects(b,world)],'tracks':[t.get_class().get_name() for t in b.get_tracks()]})
pathlib.Path('E:/PussStage/Saved/CodexMocap/clam_cast_bindings.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
unreal.log('CLAM_CAST_BINDINGS_READ|'+json.dumps(rows))
