import json
import pathlib
import unreal
rows=[]
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if a.get_actor_label().endswith(' Clam'):
        c=a.get_component_by_class(unreal.ChaosClothComponent)
        body=next(c for c in a.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name()=='Body')
        row={'label':a.get_actor_label(),'actor':a.get_path_name(),'body':body.get_path_name(),'parent':str(c.get_attach_parent()),'socket':str(c.get_attach_socket_name()),'rotation':list(c.get_world_rotation().to_tuple()),'asset':str(c.get_asset())}
        a.call_method('ConfigureShoreDrape')
        row['parent_after']=str(c.get_attach_parent());row['socket_after']=str(c.get_attach_socket_name())
        rows.append(row)
pathlib.Path('E:/PussStage/Saved/CodexMocap/shore_clam_partial.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
unreal.log('SHORE_CLAM_PARTIAL_INSPECTION|'+json.dumps(rows))
