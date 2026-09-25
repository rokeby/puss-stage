import json
import pathlib
import unreal
folder=pathlib.Path('E:/PussStage/Saved/CodexMocap')
out=[]
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    c=a.get_component_by_class(unreal.ChaosClothComponent)
    if c:
        out.append({'actor':a.get_actor_label(),'simulate_in_editor':c.get_editor_property('simulate_in_editor'),'enabled':c.is_simulation_enabled(),'suspended':c.is_simulation_suspended(),'tick_enabled':c.is_component_tick_enabled(),'blend':c.get_editor_property('blend_weight')})
        c.set_simulate_in_editor(True)
        c.set_component_tick_enabled(True)
        c.resume_simulation()
        c.force_next_update_teleport_and_reset()
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_set_viewport_realtime(True)
(folder/'shore_six_editor_cloth_flags.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
unreal.log('SHORE_SIX_CLOTH_EDITOR_FLAGS|' + json.dumps(out))
