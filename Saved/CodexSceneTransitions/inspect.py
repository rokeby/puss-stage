import json
import pathlib
import unreal

folder = pathlib.Path('E:/PussStage/Saved/CodexSceneTransitions')
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
assert world.get_path_name().startswith('/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.')
assert editor.get_game_world() is None
show = unreal.load_asset('/Game/InfinityStage/Dev/DA_InfinityStage_V1Show')
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
def dirty():
    return [p.get_path_name() for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())]
def path(obj):
    return obj.get_path_name() if obj else None
def prop(obj, key):
    try:
        v = obj.get_editor_property(key)
        return v.export_text() if hasattr(v, 'export_text') else str(v)
    except Exception as e:
        return str(e)
def sequence_info(seq, depth=0):
    info = {'path':path(seq), 'display_rate':prop(seq.get_display_rate(),'numerator'), 'tick_resolution':seq.get_tick_resolution().numerator, 'start':seq.get_playback_start(), 'end':seq.get_playback_end(), 'tracks':[]}
    for track in seq.get_tracks():
        tr = {'class':track.get_class().get_name(), 'sections':[]}
        for sec in track.get_sections():
            s = {'class':sec.get_class().get_name(), 'start':sec.get_start_frame(), 'end':sec.get_end_frame(), 'active':sec.is_active()}
            if isinstance(sec, unreal.MovieSceneSubSection):
                child = sec.get_sequence()
                s['sequence'] = path(child)
                s['parameters'] = prop(sec,'parameters')
                if child and depth < 2:s['child'] = sequence_info(child,depth+1)
            if isinstance(sec, unreal.MovieSceneCameraCutSection):
                bid = sec.get_camera_binding_id()
                s['binding'] = bid.export_text()
                s['objects'] = []
                for b in seq.get_bindings():
                    if unreal.GuidLibrary.conv_guid_to_string(b.get_id()) == unreal.GuidLibrary.conv_guid_to_string(bid.get_editor_property('guid')):
                        for obj in seq.locate_bound_objects(b,world):
                            camera = obj if isinstance(obj,unreal.Actor) else obj.get_owner()
                            component = camera.get_component_by_class(unreal.CineCameraComponent)
                            s['objects'].append({'path':path(obj),'label':camera.get_actor_label(),'transform':camera.get_actor_transform().export_text(),'focal':component.current_focal_length if component else None,'focus':prop(component,'focus_settings') if component else None})
            tr['sections'].append(s)
        info['tracks'].append(tr)
    info['bindings']=[{'name':b.get_name(),'id':unreal.GuidLibrary.conv_guid_to_string(b.get_id()),'tracks':[t.get_class().get_name() for t in b.get_tracks()]} for b in seq.get_bindings()]
    return info
out={'world':path(world),'dirty_before':dirty(),'show_tick':show.get_editor_property('tick_resolution').export_text(),'show_display':show.get_editor_property('display_rate').export_text(),'cues':[],'roots':[]}
for i,cue in enumerate(show.cues):
    if cue.type == unreal.InfinityCueType.WING_PAIR:continue
    seq = cue.scene.sequence
    if not isinstance(seq,unreal.LevelSequence):
        import re
        match=re.search(r'Sequence="([^"]+)"',cue.scene.export_text())
        seq=unreal.load_asset(match.group(1)) if match else None
    out['cues'].append({'index':i,'label':str(cue.label),'data':cue.scene.export_text(),'sequence':sequence_info(seq) if seq else None})
for actor in actors:
    if isinstance(actor,unreal.InfinityStageShowRoot):
        master=actor.get_editor_property('master_sequence')
        out['roots'].append({'path':path(actor),'label':actor.get_actor_label(),'show':path(actor.show_asset),'master':sequence_info(master,0),'playback':prop(actor,'playback_settings'),'override_owner':prop(actor,'override_camera_owner')})
out['dirty_after']=dirty()
(folder/'inspection.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
(folder/'show_before.txt').write_text('\n'.join(c.export_text() for c in show.cues),encoding='utf-8')
unreal.log('SCENE_TRANSITION_INSPECT_SUCCESS|cues='+str(len(out['cues']))+'|roots='+str(len(out['roots']))+'|dirty='+str(out['dirty_after']))
