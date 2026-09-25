import json
import unreal
out=[]
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if a.get_actor_label() in ['BP_OrtalanSheet','BP_OrtalanSheet2','BP_OrtalanSheet3','BP_OrtalanSheet4']:
        row={'label':a.get_actor_label(),'hidden':a.get_editor_property('hidden'),'hidden_ed':a.is_hidden_ed(),'layers':[str(n) for n in a.get_editor_property('layers')],'components':[]}
        for c in a.get_components_by_class(unreal.PrimitiveComponent):row['components'].append({'name':c.get_name(),'visible':c.get_editor_property('visible'),'hidden_in_game':c.get_editor_property('hidden_in_game')})
        out.append(row)
unreal.log('RETAINED_MANNY_FLAGS|'+json.dumps(out))
