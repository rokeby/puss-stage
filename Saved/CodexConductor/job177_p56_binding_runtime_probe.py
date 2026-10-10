import unreal as u
master=u.load_asset('/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master'); world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
rows=[]
for b in master.get_bindings():
    name=str(b.get_display_name())
    if name.startswith('P56 P06 Flame '):
        objs=list(master.locate_bound_objects(b,world)); rows.append((name,len(objs),','.join(str(o.get_name()) for o in objs)))
u.log('JOB177_P56_BINDING_RUNTIME_PROBE_OK|bindings=%d|resolved=%d|sample=%s'%(len(rows),sum(bool(r[1]) for r in rows),rows[0] if rows else None))
