"""S3 less light, more reflection (Gary 8 Oct ~06:10): "get rid of the lightbulb lights in S3, and make sure the rect
lights are very low light and mostly emissive for reflection - there's a bit too much light generally".
  * The 8 'S3 Choir Glint' point lights are already keyed to 0 (S3KM ...glint*); here their actors are also set
    to intensity 0 and visible=False, so the editor viewport matches.
  * The choir bulb glow MI (MI_S3_ChoirBulb_Glow) Intensity 40 -> 12: the bulbs stay visible in reflections but light
    the room much less via Lumen [inferred: emissive GI scales with emissive intensity].
  * Every RectLight in S3 (label starts 'S3 '): diffuse_scale -> 0.1, specular_scale -> 1.0.  They then barely light
    surfaces but still show as bright rectangles in the wet floor / marble / grease [inferred: UE lights' DiffuseScale
    and SpecularScale are independent multipliers; the Diffuse/Specular split is declaration-level].  Keys untouched.
Record + backup first; saves the map + the MI.  Args s3_rect_reflect_args.json {"mode":"DRY"|"APPLY"|"REVERT","run":..}.
S3RECT_<MODE>_OK / S3RECT_FAILED."""
import json
import os
import shutil
HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "s3_rect_reflect_record.json"
MAP = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
MI = "/Game/InfinityStage/Dev/Generated/S3Drama/MI_S3_ChoirBulb_Glow"
GLOW, DIFF, SPEC = 12.0, 0.1, 1.0


def main():
    import unreal
    a = json.load(open(HERE + "s3_rect_reflect_args.json"))
    run, mode = a["run"], a["mode"]
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    dirty = lambda: (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if dirty() != ([], []):
        raise RuntimeError("DIRTY_AT_START|%s" % (dirty(),))
    mel = unreal.MaterialEditingLibrary
    w = ed.get_editor_world()
    acts = list(unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor))
    rects = [x for x in acts if str(x.get_actor_label()).startswith("S3 ") and x.get_component_by_class(unreal.RectLightComponent)]
    glints = [x for x in acts if str(x.get_actor_label()).startswith("S3 Choir Glint ")]
    mi = unreal.load_asset(MI)
    state = {"rects": {str(x.get_actor_label()): [x.get_component_by_class(unreal.RectLightComponent).get_editor_property("diffuse_scale"),
                                                  x.get_component_by_class(unreal.RectLightComponent).get_editor_property("specular_scale")] for x in rects},
             "glints": {str(x.get_actor_label()): [x.get_component_by_class(unreal.LightComponent).intensity,
                                                   x.get_component_by_class(unreal.LightComponent).is_visible()] for x in glints},
             "glow": mel.get_material_instance_scalar_parameter_value(mi, "Intensity")}
    if mode == "DRY":
        unreal.log("S3RECT_DRY_OK|run=%s|rects=%s|glints=%d|glow=%s" % (run, sorted(state["rects"]), len(glints), state["glow"]))
        return
    if mode == "APPLY":
        if os.path.exists(REC):
            raise RuntimeError("RECORD_EXISTS")
        json.dump({"run": run, "before": state}, open(REC, "w"), indent=1)
        bd = "E:/PussStage/Backups/PreS3RectReflect-%s" % run
        os.makedirs(bd)
        shutil.copy2(UMAP, bd)
        tgt = {"rects": {k: [DIFF, SPEC] for k in state["rects"]}, "glints": {k: [0.0, False] for k in state["glints"]}, "glow": GLOW}
    elif mode == "REVERT":
        tgt = json.load(open(REC))["before"]
    else:
        raise RuntimeError("MODE")
    for x in rects:
        c = x.get_component_by_class(unreal.RectLightComponent)
        c.modify()
        d, s = tgt["rects"][str(x.get_actor_label())]
        c.set_editor_property("diffuse_scale", float(d))
        c.set_editor_property("specular_scale", float(s))
    for x in glints:
        c = x.get_component_by_class(unreal.LightComponent)
        c.modify()
        i, v = tgt["glints"][str(x.get_actor_label())]
        c.set_intensity(float(i))
        c.set_visibility(bool(v))
    mi.modify()
    mel.set_material_instance_scalar_parameter_value(mi, "Intensity", float(tgt["glow"]))
    if abs(mel.get_material_instance_scalar_parameter_value(mi, "Intensity") - float(tgt["glow"])) > 1e-3:
        raise RuntimeError("MI_READBACK|NOTHING SAVED; Don't-Save restart")
    for x in rects:
        c = x.get_component_by_class(unreal.RectLightComponent)
        if abs(c.get_editor_property("diffuse_scale") - tgt["rects"][str(x.get_actor_label())][0]) > 1e-4:
            raise RuntimeError("RECT_READBACK|%s|NOTHING SAVED; Don't-Save restart" % x.get_actor_label())
    c1 = dirty()
    if c1 != ([MI], [MAP]):
        raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (c1,))
    if not unreal.EditorAssetLibrary.save_asset(MI, only_if_is_dirty=False) or not lib.save_dirty_packages(True, False) or dirty() != ([], []):
        raise RuntimeError("SAVE|%s" % (dirty(),))
    if mode == "REVERT":
        os.rename(REC, REC + ".reverted-" + run)
    unreal.log("S3RECT_%s_OK|run=%s|rects=%d|glints=%d|glow=%s" % (mode, run, len(rects), len(glints), tgt["glow"]))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3RECT_FAILED|%r" % (exc,))
