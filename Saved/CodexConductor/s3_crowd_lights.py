"""S3 CROWD LIGHTS (Gary 8 Oct evening: "I'll aim them but I'd like you to light them. It looks very dark for now").
Per cluster (live PIE positions, pie_crowd_pos.jsonl 8 Oct [measured]): a soft cool KEY from the camera side, high, and a
cool RIM from the wall side behind, low, for shoulders/shrouds and the wet floor. Cues (Scene 3 frames @24):
dark until 360 (spawn in darkness), up 360->408 (establishing 0:15), hold, lift x1.3 over 2160->2400 (soothing ->
choir from 1:30), down to 0.5 over 4488->4560 (chorus ends, crying). Intensity tracks 'S3.Crowd.Light' in LS_DevScene_03.
Tagged S3CrowdLight, folder RigAtmos/S3Crowd. Args s3_crowd_lights_args.json {"mode","confirm":"<MODE> S3CROWDLIGHT","run"}.
Markers S3CROWDLIGHT_<MODE>_OK / _FAILED. Pattern + code: s3_drama_lights.py (live-proven 8 Oct)."""
import json
import math
import os
import shutil

HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "s3_crowd_lights_record.json"
MAP = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
FILES = ["E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap",
         "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"]
TAG = "S3CrowdLight"
FOLDER = "RigAtmos/S3Crowd"
TRACK = "S3.Crowd.Light"
WAVE_TRACK = "S3.WavesV3.Light"
END = 6240
RUN = {"run": "?"}

CLAM_RISEN = (15484.4, 160169.5, 141.0)          # risen clam shell centre, world [meas keys + bounds offset 22 cm]
WALL_L, WALL_R = 159001.0, 160999.0              # marble inner faces, world y [meas grease placement]

CLUSTERS = {"A": (14600.0, 160220.0), "B": (14520.0, 160700.0), "C": (13420.0, 160550.0)}
CUE = [(0, 0.0), (360, 0.0), (408, 1.0), (2160, 1.0), (2400, 1.3), (4488, 1.3), (4560, 0.5), (END, 0.5)]
SPECS = []
for n, (cx, cy) in sorted(CLUSTERS.items()):
    SPECS.append({"label": "S3 Crowd Key %s" % n, "cls": "SpotLight", "loc": (cx - 250.0, cy - 650.0, 620.0),
                  "aim": (cx, cy, 110.0), "cd": 600.0, "kelvin": 5600.0, "inner": 14.0, "outer": 34.0, "radius": 30.0,
                  "atten": 2200.0, "shadows": True, "keys": CUE})
    SPECS.append({"label": "S3 Crowd Rim %s" % n, "cls": "SpotLight", "loc": (cx + 150.0, 160900.0, 300.0),
                  "aim": (cx, cy, 120.0), "cd": 900.0, "kelvin": 6500.0, "inner": 10.0, "outer": 26.0, "radius": 8.0,
                  "atten": 1800.0, "shadows": True, "keys": CUE})
WAVE_GAIN = {}
SHIMMER = {}

def shimmer_keys(lit, idx, fps=24.0):
    """Deterministic: [(frame, value)] from SHIMMER.from to END-12, per-light phase idx*1.7 rad."""
    out = []
    ph = idx * 1.7
    f = SHIMMER["from"]
    while f < END - SHIMMER["step"]:
        t = f / fps
        v = lit * (1.0 + SHIMMER["a1"] * math.sin(2 * math.pi * t / SHIMMER["p1"] + ph)
                   + SHIMMER["a2"] * math.sin(2 * math.pi * t / SHIMMER["p2"] + 2 * ph))
        out.append((f, round(v, 3)))
        f += SHIMMER["step"]
    return out


def main():
    import unreal
    a = json.load(open(HERE + "s3_crowd_lights_args.json", encoding="utf-8"))
    run, mode = a["run"], a["mode"]
    RUN["run"] = run
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    DR = unreal.MovieSceneTimeUnit.DISPLAY_RATE

    def census():
        return (sorted(p.get_name() for p in lib.get_dirty_content_packages()),
                sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    c0 = census()
    if c0 != ([], []):
        raise RuntimeError("DIRTY_AT_START|%s" % (c0,))
    w = ed.get_editor_world()
    acts = {str(x.get_actor_label()): x for x in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor)}
    scene = unreal.load_asset(SCENE)
    if int(scene.get_playback_end()) != END:
        raise RuntimeError("END|%s" % scene.get_playback_end())
    ours = [x for x in acts.values() if unreal.Name(TAG) in list(x.tags)]
    waves = []
    for b in scene.get_bindings():
        for t in b.get_tracks():
            if str(t.get_display_name()) == WAVE_TRACK:
                p = b.get_parent()
                owner = str(p.get_display_name()) if p is not None and p.is_valid() else str(b.get_display_name())
                ch = list(t.get_sections()[0].get_all_channels())[0]
                waves.append((owner, ch))
    waves.sort(key=lambda r: r[0])
    waves = []   # crowd lights never touch the wave lights
    wave_before = {o: [(int(k.get_time().frame_number.value), float(k.get_value())) for k in ch.get_keys()] for o, ch in waves}
    if mode == "DRY":
        unreal.log("S3CROWDLIGHT_DRY_OK|run=%s|existing_ours=%d|waves=%d|wave_key_counts=%s|have_root=%s|have_pearl=%s" % (
            run, len(ours), len(waves), sorted(set(len(v) for v in wave_before.values())),
            "S3 Hangar Root" in acts, "S3 PearlClam Pearl" in acts))
        return
    if mode == "APPLY":
        if a.get("confirm") != "APPLY S3CROWDLIGHT" or os.path.exists(REC) or ours:
            raise RuntimeError("CONFIRM_OR_RECORD_OR_EXISTING|ours=%d" % len(ours))
        rec = {"run": run, "state": "applying", "wave_before": wave_before, "created": []}
        json.dump(rec, open(REC, "w"), indent=1)
        bdir = "E:/PussStage/Backups/PreS3CrowdLight-%s" % run
        os.makedirs(bdir)
        for f in FILES:
            shutil.copy2(f, bdir)
        root = acts["S3 Hangar Root"]
        scene.modify()
        for spec in SPECS:
            cls = getattr(unreal, spec["cls"])
            parent = acts[spec["attach"]] if spec.get("attach") else root
            if spec["loc"] is None:
                c, _e = parent.get_actor_bounds(False)
                loc = unreal.Vector(c.x, c.y, c.z)
            else:
                loc = unreal.Vector(*spec["loc"])
            rot = unreal.MathLibrary.find_look_at_rotation(loc, unreal.Vector(*spec["aim"])) if spec.get("aim") else unreal.Rotator(0, 0, 0)
            x = eas.spawn_actor_from_class(cls, loc, rot, False)
            if x is None:
                raise RuntimeError("SPAWN|%s|NOTHING SAVED; Don't-Save restart" % spec["label"])
            x.set_actor_label(spec["label"])
            x.set_editor_property("tags", [unreal.Name(TAG)])
            x.set_folder_path(FOLDER)
            x.attach_to_actor(parent, "", unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD,
                              unreal.AttachmentRule.KEEP_WORLD, False)
            comp = x.get_component_by_class(unreal.LightComponent)
            comp.modify()
            comp.set_mobility(unreal.ComponentMobility.MOVABLE)
            comp.set_editor_property("intensity_units", unreal.LightUnits.CANDELAS)
            comp.set_editor_property("intensity", 0.0)
            comp.set_editor_property("attenuation_radius", spec["atten"])
            comp.set_editor_property("source_radius", spec["radius"])
            comp.set_editor_property("cast_shadows", spec["shadows"])
            if "kelvin" in spec:
                comp.set_editor_property("use_temperature", True)
                comp.set_editor_property("temperature", spec["kelvin"])
            if "rgb" in spec:
                comp.set_editor_property("use_temperature", False)
                comp.set_light_color(unreal.LinearColor(*spec["rgb"], 1.0))
            if spec["cls"] == "SpotLight":
                comp.set_editor_property("inner_cone_angle", spec["inner"])
                comp.set_editor_property("outer_cone_angle", spec["outer"])
            rec["created"].append({"label": spec["label"], "path": x.get_path_name()})
            json.dump(rec, open(REC, "w"), indent=1)
            b = scene.add_possessable(comp)
            t = b.add_track(unreal.MovieSceneFloatTrack)
            t.set_property_name_and_path("Intensity", "Intensity")
            t.set_display_name(TRACK)
            s = t.add_section()
            s.set_range(0, END + 1)
            ch = list(s.get_all_channels())[0]
            for fr, k in spec["keys"]:
                ch.add_key(unreal.FrameNumber(fr), float(k * spec["cd"]), time_unit=DR,
                           interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
            got = sorted((int(k.get_time().frame_number.value), round(k.get_value(), 3)) for k in ch.get_keys())
            if got != sorted((fr, round(k * spec["cd"], 3)) for fr, k in spec["keys"]):
                raise RuntimeError("KEYS_READBACK|%s|NOTHING SAVED; Don't-Save restart" % spec["label"])
            if x.get_attach_parent_actor() != parent:
                raise RuntimeError("ATTACH_READBACK|%s|NOTHING SAVED; Don't-Save restart" % spec["label"])
    elif mode == "REVERT":
        if a.get("confirm") != "REVERT S3CROWDLIGHT" or not os.path.exists(REC):
            raise RuntimeError("CONFIRM_OR_NO_RECORD")
        rec = json.load(open(REC))
        scene.modify()
        comps = {}
        for x in ours:
            c = x.get_component_by_class(unreal.LightComponent)
            if c:
                comps[c.get_path_name()] = x
        for b in list(scene.get_bindings()):
            if any(str(t.get_display_name()) == TRACK for t in b.get_tracks()):
                b.remove()
        for x in ours:
            eas.destroy_actor(x)
        for o, ch in waves:
            for k in list(ch.get_keys()):
                ch.remove_key(k)
            for fr, v in rec["wave_before"][o]:
                ch.add_key(unreal.FrameNumber(fr), v, time_unit=DR, interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
            if sorted((int(k.get_time().frame_number.value), round(k.get_value(), 3)) for k in ch.get_keys()) != \
                    sorted((f, round(v, 3)) for f, v in rec["wave_before"][o]):
                raise RuntimeError("WAVE_REVERT_READBACK|%s|NOTHING SAVED; Don't-Save restart" % o)
    else:
        raise RuntimeError("MODE")
    c1 = census()
    if c1 != ([SCENE], [MAP]):
        raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (c1,))
    if not unreal.EditorAssetLibrary.save_asset(SCENE, only_if_is_dirty=False):
        raise RuntimeError("SAVE_SCENE_FAILED")
    if not lib.save_dirty_packages(True, False):
        raise RuntimeError("SAVE_MAP_FAILED")
    if census() != ([], []):
        raise RuntimeError("DIRTY_AFTER|%s" % (census(),))
    if mode == "APPLY":
        rec["state"] = "applied"
        json.dump(rec, open(REC, "w"), indent=1)
        unreal.log("S3CROWDLIGHT_APPLY_OK|run=%s|lights=%d|waves=%d|saved=map+scene" % (run, len(rec["created"]), len(waves)))
    else:
        os.rename(REC, REC + ".reverted-" + run)
        unreal.log("S3CROWDLIGHT_REVERT_OK|run=%s|removed=%d" % (run, len(ours)))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3CROWDLIGHT_FAILED|run=%s|%r" % (RUN["run"], exc))
