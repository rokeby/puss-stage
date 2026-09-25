import json
import pathlib
import unreal

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
assert world.get_path_name().startswith('/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.')
assert editor.get_game_world() is None, 'PIE/SIE is active'
def path(obj):
    return obj.get_path_name() if obj else None
def prop(obj, name):
    try:
        value = obj.get_editor_property(name)
        return value.export_text() if hasattr(value, 'export_text') else str(value)
    except Exception as exc:
        return 'ERROR: ' + str(exc)
def dirty():
    return [path(p) for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())]
def track_info(track):
    out = {'class':track.get_class().get_name(), 'name':str(track.get_display_name()), 'sections':[]}
    for sec in track.get_sections():
        row = {'class':sec.get_class().get_name(), 'start':sec.get_start_frame() if sec.has_start_frame() else None, 'end':sec.get_end_frame() if sec.has_end_frame() else None, 'active':sec.is_active(), 'channels':[]}
        for ch in sec.get_all_channels():
            channel = {'class':ch.get_class().get_name(), 'keys':[]}
            for key in ch.get_keys():
                k = {'frame':key.get_time(unreal.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value, 'value':str(key.get_value())}
                if hasattr(key, 'get_interpolation_mode'):
                    k['interpolation'] = str(key.get_interpolation_mode())
                channel['keys'].append(k)
            row['channels'].append(channel)
        out['sections'].append(row)
    return out
out = {'world':path(world), 'dirty_before':dirty(), 'sequences':[], 'cues':[], 'roots':[]}
for name in ['LS_Opening_Curtain', 'LS_Interaction_01_WashingTheBoy']:
    seq = unreal.load_asset('/Game/InfinityStage/Interactions/' + name)
    row = {'path':path(seq), 'start':seq.get_playback_start(), 'end':seq.get_playback_end(), 'rate':seq.get_display_rate().export_text(), 'tracks':[track_info(t) for t in seq.get_tracks()], 'bindings':[], 'markers':[m.export_text() for m in seq.get_marked_frames()]}
    for binding in seq.get_bindings():
        template = binding.get_object_template()
        row['bindings'].append({'name':binding.get_name(), 'tracks':[track_info(t) for t in binding.get_tracks()], 'template':{k:prop(template,k) for k in ['curtain_active','curtain_progress','follow_player_camera','curtain_distance_cm','use_authored_open_closed_transforms','curtain_open_relative_transform','curtain_closed_relative_transform']} if template else None})
    out['sequences'].append(row)
show = unreal.load_asset('/Game/InfinityStage/Dev/DA_InfinityStage_V1Show')
for cue in show.cues:
    if str(cue.label).startswith('Opening') or str(cue.label).startswith('Interaction 1'):
        out['cues'].append(cue.export_text())
for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if isinstance(actor, unreal.InfinityStageShowRoot):
        out['roots'].append({'path':path(actor), 'playback':prop(actor,'playback_settings'), 'prepare_on_begin_play':prop(actor,'prepare_on_begin_play'), 'auto_scene':prop(actor.transport,'auto_play_scene_after_passage')})
out['dirty_after'] = dirty()
assert out['dirty_after'] == out['dirty_before']
pathlib.Path('E:/PussStage/Saved/CodexSceneTransitions/curtain_inspection.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
unreal.log('CURTAIN_READ_ONLY_INSPECTION_SUCCESS|sequences=2|dirty=' + str(out['dirty_after']))
