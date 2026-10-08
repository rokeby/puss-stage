"""S3 jawbone glint (Gary 8 Oct ~06:55, screenshot at S3 0:34.4: "I also need a slight glint of highlight on the
jawbone at this point").  Jaw = SM_HominidJaw2 at (14307, 160259, 9) [measured probe_jaw]; the shot looks at it from
the -x/+y side, low [inferred from the screenshot + B02's pose].  One tight SpotLight 'S3 Jaw Glint' 1.4 m up and back
toward that side, aimed at the jaw: cone 3/6 deg, source radius 1 cm (a crisp glint), 300 cd, 5000 K, diffuse 0.4,
specular 1.0.  Keyed in LS_DevScene_03 (track S3.Drama.Light): 0 -> full over 720-744 (B03 cut 0:30), off over
1056-1080 (0:45).  Record + backup; saves map + LS_DevScene_03.  S3JAW_OK / S3JAW_FAILED."""
import json, os, shutil, time
HERE = "E:/PussStage/Saved/CodexConductor/"
MAP = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SC = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
FILES = ["E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap",
         "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"]
def main():
    import unreal
    run = "S3JAW-" + time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        raise RuntimeError("SEQUENCER_OPEN")
    lib = unreal.EditorLoadingAndSavingUtils
    dirty = lambda: (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if dirty() != ([], []):
        raise RuntimeError("DIRTY_AT_START|%s" % (dirty(),))
    w = ed.get_editor_world()
    acts = {str(x.get_actor_label()): x for x in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor)}
    if "S3 Jaw Glint" in acts:
        raise RuntimeError("EXISTS")
    jaw = acts["SM_HominidJaw2"]
    c, _e = jaw.get_actor_bounds(False)
    loc = unreal.Vector(c.x - 100.0, c.y + 80.0, c.z + 130.0)
    bd = "E:/PussStage/Backups/PreS3Jaw-%s" % run
    os.makedirs(bd)
    for f in FILES:
        shutil.copy2(f, bd)
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    x = eas.spawn_actor_from_class(unreal.SpotLight, loc, unreal.MathLibrary.find_look_at_rotation(loc, c), False)
    x.set_actor_label("S3 Jaw Glint")
    x.set_editor_property("tags", [unreal.Name("S3Drama")])
    x.set_folder_path("RigAtmos/S3Drama")
    x.attach_to_actor(acts["S3 Hangar Root"], "", unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)
    comp = x.get_component_by_class(unreal.LightComponent)
    comp.set_mobility(unreal.ComponentMobility.MOVABLE)
    for k, v in (("intensity_units", unreal.LightUnits.CANDELAS), ("intensity", 0.0), ("inner_cone_angle", 3.0), ("outer_cone_angle", 6.0),
                 ("source_radius", 1.0), ("attenuation_radius", 400.0), ("use_temperature", True), ("temperature", 5000.0),
                 ("diffuse_scale", 0.4), ("specular_scale", 1.0), ("cast_shadows", True)):
        comp.set_editor_property(k, v)
    seq = unreal.load_asset(SC)
    seq.modify()
    b = seq.add_possessable(comp)
    t = b.add_track(unreal.MovieSceneFloatTrack)
    t.set_property_name_and_path("Intensity", "Intensity")
    t.set_display_name("S3.Drama.Light")
    s = t.add_section()
    s.set_range(0, 6241)
    ch = list(s.get_all_channels())[0]
    for f, v in ((0, 0.0), (720, 0.0), (744, 300.0), (1056, 300.0), (1080, 0.0), (6240, 0.0)):
        ch.add_key(unreal.FrameNumber(f), v, time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE, interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
    if ch.get_num_keys() != 6 or dirty() != ([SC], [MAP]):
        raise RuntimeError("READBACK_OR_CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (dirty(),))
    if not unreal.EditorAssetLibrary.save_asset(SC, only_if_is_dirty=False) or not lib.save_dirty_packages(True, False) or dirty() != ([], []):
        raise RuntimeError("SAVE|%s" % (dirty(),))
    unreal.log("S3JAW_OK|run=%s|light_at=%s|aim=%s" % (run, loc, c))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3JAW_FAILED|%r" % (exc,))
