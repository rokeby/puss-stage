import json
import math
import pathlib
import unreal
folder=pathlib.Path('E:/PussStage/Saved/CodexMocap')
root='/Game/Metahuman/ShoreCast_20260910'
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
assert world.get_path_name().split('.')[0]=='/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice'
assert not levels.is_in_play_in_editor()
unreal.LevelSequenceEditorBlueprintLibrary.pause()
unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
all_actors=actors.get_all_level_actors()
cast=json.loads((folder/'shore_draped_cast_components.json').read_text(encoding='utf-8'))
motions={p['id']:p for p in json.loads((folder/'shore_gentle_motion_selection.json').read_text(encoding='utf-8'))['characters']}
backup=json.loads((folder/'clam_integration_backup.json').read_text(encoding='utf-8'))
assert pathlib.Path(backup['backup'],'Content/Scenes/LS_Clams.uasset').is_file()
seq=unreal.load_asset('/Game/Scenes/LS_Clams')
assert seq.get_playback_start()==0 and seq.get_playback_end()==797
our_ids={unreal.GuidLibrary.conv_guid_to_string(b.get_id()) for b in seq.get_bindings() if str(b.get_display_name()).endswith(' Shore') and str(b.get_display_name()).startswith('Shore')}
for b in list(seq.get_bindings()):
    if str(b.get_display_name()).startswith('TRASH_') and unreal.GuidLibrary.conv_guid_to_string(b.get_parent().get_id()) in our_ids:
        assert not seq.locate_bound_objects(b,world)
        assert all(isinstance(t,unreal.MovieSceneSkeletalAnimationTrack) for t in b.get_tracks())
        b.remove()
tick=seq.get_tick_resolution();ticks=tick.numerator/tick.denominator
positions=[(13490.66,159780.28,0),(13143.29,159775.41,0),(13381.92,160104.60,0),(13505.20,160063.73,0),(13310,159530,0),(13300,160340,0)]
out={'world':world.get_path_name(),'sequence':seq.get_path_name(),'source_animations_preserved':True,'backup':backup['backup'],'characters':[],'retained_originals':[]}
for p,position in zip(cast,positions):
    motion=motions[p['id']];sel=motion['selected']
    yaw=math.degrees(math.atan2(159859.73-position[1],12647.78-position[0]))-90
    actor=next((a for a in all_actors if a.get_actor_label()==p['id']+' Clam'),None)
    if actor is None:
        actor=actors.spawn_actor_from_class(unreal.load_asset(p['blueprint']).generated_class(),unreal.Vector(*position),unreal.Rotator(pitch=0,yaw=yaw,roll=0))
    actor.set_actor_label(p['id']+' Clam')
    actor.set_folder_path('Scenes/Shore/MetaHuman Cast')
    body=next(c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name()=='Body')
    anim=unreal.load_asset(motion['animation'])
    body.override_animation_data(anim,False,False,sel['start_seconds'],sel['play_rate'])
    body.set_editor_property('visibility_based_anim_tick_option',unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
    cloth=actor.get_component_by_class(unreal.ChaosClothComponent)
    actor.call_method('ConfigureShoreDrape')
    cloth.set_simulate_in_editor(True);cloth.resume_simulation()
    cloth.force_next_update_teleport_and_reset()
    ab=next((b for b in seq.get_bindings() if str(b.get_display_name())==p['id']+' Shore'),None)
    if ab is None:
        ab=seq.add_possessable(actor);ab.set_display_name(p['id']+' Shore')
    bb=next((b for b in seq.get_bindings() if b.get_parent()==ab),None)
    if bb is None:
        body=next(c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name()=='Body')
        bb=seq.add_possessable(body);bb.set_parent(ab)
        track=bb.add_track(unreal.MovieSceneSkeletalAnimationTrack)
        section=track.add_section()
    else:
        section=bb.get_tracks()[0].get_sections()[0]
    section.set_range(0,797);section.set_pre_roll_frames(90)
    section.set_completion_mode(unreal.MovieSceneCompletionMode.KEEP_STATE)
    params=section.get_editor_property('params');params.animation=anim;params.force_custom_mode=True
    params.start_frame_offset=unreal.FrameNumber(round(sel['start_seconds']*ticks))
    rate=params.play_rate;rate.set_fixed_play_rate(sel['play_rate']);params.play_rate=rate
    section.set_editor_property('params',params)
    body=next(c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name()=='Body')
    cloth=actor.get_component_by_class(unreal.ChaosClothComponent)
    actor.call_method('ConfigureShoreDrape')
    cloth.set_simulate_in_editor(True);cloth.resume_simulation()
    assert cloth.get_attach_parent().get_path_name()==body.get_path_name() and str(cloth.get_attach_socket_name())=='head'
    out['characters'].append({'id':p['id'],'actor':actor.get_path_name(),'body':body.get_path_name(),'blueprint':p['blueprint'],'location':position,'yaw':yaw,'cloth':cloth.get_asset().get_path_name(),'animation':anim.get_path_name(),'source_start_seconds':sel['start_seconds'],'play_rate':sel['play_rate'],'actor_binding':unreal.GuidLibrary.conv_guid_to_string(ab.get_id()),'body_binding':unreal.GuidLibrary.conv_guid_to_string(bb.get_id())})
for label in ['BP_OrtalanSheet','BP_OrtalanSheet2','BP_OrtalanSheet3','BP_OrtalanSheet4']:
    actor=next(a for a in all_actors if a.get_actor_label()==label)
    row={'actor':actor.get_path_name(),'label':label,'recovery_authority':backup['backup'],'observed_hidden_during_resume':actor.get_editor_property('hidden'),'components':[]}
    for c in actor.get_components_by_class(unreal.PrimitiveComponent):
        row['components'].append({'name':c.get_name(),'visible':c.get_editor_property('visible'),'hidden_in_game':c.get_editor_property('hidden_in_game')})
        c.set_visibility(False,False);c.set_hidden_in_game(True,False)
        if isinstance(c,unreal.ChaosClothComponent):c.set_editor_property('suspend_simulation',True)
    actor.set_actor_hidden_in_game(True)
    actor.set_folder_path('Scenes/Shore/Retained Manny Replacements')
    out['retained_originals'].append(row)
assert unreal.EditorAssetLibrary.save_loaded_asset(seq,only_if_is_dirty=False)
assert levels.save_current_level()
(folder/'shore_clam_integration.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0)
unreal.LevelSequenceEditorBlueprintLibrary.play()
unreal.log('SIX_SHORE_METAHUMANS_PLACED_AT_CLAM_SAVED|six_body_tracks|four_originals_retained_hidden|full_sources_preserved')
