"""PIE-only: set the two gobo spots ('Spot Light', 'Spot Light2' with the gobo LF) to intensity 0 (or restore from file). PIE_GOBOZERO_OK"""
import json, os, unreal
P = "E:/PussStage/Saved/CodexConductor/pie_gobo_spots_zero_orig.json"
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
rows = []
for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
    for c in a.get_components_by_class(unreal.SpotLightComponent):
        lf = c.get_editor_property("light_function_material")
        if lf and "ShadowGobo" in lf.get_path_name(): rows.append((str(a.get_name()), c))
if os.path.exists(P):
    orig = json.load(open(P))
    for n, c in rows: c.set_intensity(orig.get(n, c.intensity))
    os.remove(P); unreal.log("PIE_GOBOZERO_OK|restored=%d" % len(rows))
else:
    json.dump({n: c.intensity for n, c in rows}, open(P, "w"))
    for n, c in rows: c.set_intensity(0.0)
    unreal.log("PIE_GOBOZERO_OK|zeroed=%d" % len(rows))
