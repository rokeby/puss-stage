"""READ-ONLY PIE tap: lit SkyLight/DirectionalLight components (visible, intensity>0, actor not hidden) + segment time. PIE_SKYTAP|json"""
import json
import unreal
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
a = json.load(open("E:/PussStage/Saved/CodexConductor/pie_lights_tap_args.json"))
root = list(unreal.GameplayStatics.get_all_actors_of_class(w, unreal.InfinityStageShowRoot))[0]
tr = root.transport
seg = [s for s in list(tr.segments) if str(s.label).startswith(a["segment"])][0]
t = round((tr.get_current_master_frame().value - seg.start_frame.value) / 24000.0, 1)
rows = []
for act in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
    if act.get_editor_property("hidden"):
        continue
    for cls in (unreal.SkyLightComponent, unreal.DirectionalLightComponent):
        for c in act.get_components_by_class(cls):
            if c.is_visible() and float(c.intensity) > 0:
                rows.append([str(act.get_actor_label())[:40], cls.__name__[:12], round(float(c.intensity), 3), act.get_outer().get_outer().get_name()])
unreal.log("PIE_SKYTAP|" + json.dumps({"seg": a["segment"], "t": t, "lit": rows}))
