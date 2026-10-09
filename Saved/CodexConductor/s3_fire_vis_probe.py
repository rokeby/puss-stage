import unreal
seq = unreal.load_asset("/Game/InfinityStage/Dev/Sequences/LS_DevScene_03")
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
out = []
for b in seq.get_bindings():
    n = str(b.get_display_name())
    if n not in ("S3 Fire A", "S3 Fire B", "S3 Fire C", "S3 Ghost Light Flame"): continue
    try:
        objs = [str(o.get_actor_label()) if isinstance(o, unreal.Actor) else o.get_name() for o in seq.locate_bound_objects(b, w)]
    except Exception as e:
        objs = ["ERR %r" % e]
    out.append((n, b.get_id().export_text()[:8], objs, [str(t.get_name()) for t in b.get_tracks()]))
unreal.log("S3FIREVISPROBE_OK|%s" % out)
