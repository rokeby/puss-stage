import unreal as u
prefix='P56_P75_P06_Chandelier_Body_Candle_'
world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
actors=[a for a in u.GameplayStatics.get_all_actors_of_class(world,u.Actor) if str(a.get_actor_label()).startswith(prefix)]
components=[]
for a in actors:
    components += [c for c in a.get_components_by_class(u.NiagaraComponent) if str(c.get_name())=='ChandelierFlameFX']
for c in components: c.activate(True)
def done():
    u.log('JOB177_P56_RUNTIME_ACTIVATE_PROBE_OK|components=%d|active=%d'%(len(components),sum(bool(c.is_active()) for c in components)))
u.register_slate_post_tick_callback(lambda dt: None)
done()
