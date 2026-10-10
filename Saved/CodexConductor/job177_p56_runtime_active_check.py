import unreal as u
world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world(); prefix='P56_P75_P06_Chandelier_Body_Candle_'
components=[]
for a in u.GameplayStatics.get_all_actors_of_class(world,u.Actor):
    if str(a.get_actor_label()).startswith(prefix): components += [c for c in a.get_components_by_class(u.NiagaraComponent) if str(c.get_name())=='ChandelierFlameFX']
u.log('JOB177_P56_RUNTIME_ACTIVE_CHECK_OK|components=%d|active=%d'%(len(components),sum(bool(c.is_active()) for c in components)))
