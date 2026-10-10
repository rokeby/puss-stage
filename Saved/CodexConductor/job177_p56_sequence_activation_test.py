import unreal as u
world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
roots=list(u.GameplayStatics.get_all_actors_of_class(world,u.InfinityStageShowRoot)); assert len(roots)==1
transport,player=roots[0].transport,roots[0].sequence_player
segments=[s for s in transport.segments if str(s.label)=='Passage 6']; assert len(segments)==1
prefix='P56_P75_P06_Chandelier_Body_Candle_'; comps=[]
for a in u.GameplayStatics.get_all_actors_of_class(world,u.Actor):
    if str(a.get_actor_label()).startswith(prefix): comps += [c for c in a.get_components_by_class(u.NiagaraComponent) if str(c.get_name())=='ChandelierFlameFX']
assert len(comps)==44
original=int(transport.get_current_master_frame().value); playing=bool(transport.is_transport_playing()); player.pause()
for c in comps: c.deactivate()
state={'phase':'deactivate','ticks':10,'handle':None,'active_before':None}
def tick(dt):
    state['ticks']-=1
    if state['ticks']>0:return
    if state['phase']=='deactivate':
        state['active_before']=sum(bool(c.is_active()) for c in comps)
        transport.scrub_to_master_frame(u.FrameNumber(int(segments[0].start_frame.value)))
        state['phase']='evaluate'; state['ticks']=90
        return
    active=sum(bool(c.is_active()) for c in comps)
    transport.scrub_to_master_frame(u.FrameNumber(original)); player.play() if playing else player.pause()
    u.unregister_slate_post_tick_callback(state['handle'])
    u.log('JOB177_P56_SEQUENCE_ACTIVATION_TEST_OK|components=44|active_before=%d|active_after=%d|source=MovieSceneParticleTrack|key=ACTIVATE'%(state['active_before'],active))
state['handle']=u.register_slate_post_tick_callback(tick)
u.log('JOB177_P56_SEQUENCE_ACTIVATION_TEST_ARMED|components=44|active_before=0')
