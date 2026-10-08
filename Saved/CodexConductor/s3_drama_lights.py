"""S3 lighting drama, first pass (Gary 8 Oct ~01:40 UTC, chat): "more lighting on the waves with some dynamism", glinting
bright lights (the wash "made everything look more ugly"), something to show up the grease handprints, and "when the clam
rises up from where it now sits behind the first waves, a soft warm white light should shine at an angle upon it, but
not enough to outshine the glow of its pearl, which emits a pinkish glow from within that becomes bright and prominent
once it opens up".

Timing anchors (LS_DevScene_03, 24 fps) [measured probe_s3_clam_anim.json / scene_audio_import_S3_record.json]:
  clam rise keys 3593 -> 4170 (Gary's PearlClam transform keys); choir sings 2:10 = 3120; Puss takes clam 3:10 = 4560;
  waves full at 528.  The lid has NO opening animation yet [measured: lid keys constant] -> "open" is taken as the end
  of the rise (4170) [inferred].

Writes (all lights tagged S3Drama, folder RigAtmos/S3Drama, attached KEEP_WORLD):
  1. S3 Drama Clam Key   - SpotLight, warm white 4200 K, soft (source radius 15 cm), aimed at the risen clam.
  2. S3 Drama Pearl Glow - PointLight, pink, attached to S3 PearlClam Pearl (rises with it), shadowed so the closed lid
                            holds it in; faint through the rise, bright after it, out at 3:10 (the pearl is taken).
  3. S3 Drama Graze L1/L2/R1/R2 - narrow cool 6500 K SpotLights skimming each marble wall (40 cm off it, along it) for
                            the handprint glint; up at the choir (3120), down to 30 % after 3:10.
  4. The 7 wave lights (S3.WavesV3.Light): lit level x2.5 / x1.8 and a deterministic shimmer (two sines per light,
                            per-light phase) after the 19-22 s fade.
Intensity tracks for 1-3 are 'S3.Drama.Light' in LS_DevScene_03.  Saves the map + LS_DevScene_03 only.
Args s3_drama_lights_args.json {"mode":"DRY"|"APPLY"|"REVERT","confirm":"<MODE> S3DRAMA","run":..}.
Record s3_drama_lights_record.json + Backups/PreS3Drama-<run>/ (umap + uasset) first.
Markers S3DRAMA_<MODE>_OK|run=.. / S3DRAMA_FAILED|run=..|reason."""
import json
import math
import os
import shutil

HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "s3_drama_lights_record.json"
MAP = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
FILES = ["E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap",
         "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"]
TAG = "S3Drama"
FOLDER = "RigAtmos/S3Drama"
TRACK = "S3.Drama.Light"
WAVE_TRACK = "S3.WavesV3.Light"
END = 6240
RUN = {"run": "?"}

CLAM_RISEN = (15484.4, 160169.5, 141.0)          # risen clam shell centre, world [meas keys + bounds offset 22 cm]
WALL_L, WALL_R = 159001.0, 160999.0              # marble inner faces, world y [meas grease placement]

SPECS = [
    {"label": "S3 Drama Clam Key", "cls": "SpotLight", "loc": (15134.0, 159869.0, 431.0), "aim": CLAM_RISEN,
     "cd": 400.0, "kelvin": 4200.0, "inner": 8.0, "outer": 20.0, "radius": 15.0, "atten": 1500.0, "shadows": True,
     "keys": [(0, 0.0), (3593, 0.0), (4170, 1.0), (END, 1.0)]},
    {"label": "S3 Drama Pearl Glow", "cls": "PointLight", "attach": "S3 PearlClam Pearl", "loc": None,
     "cd": 40.0, "rgb": (1.0, 0.45, 0.62), "radius": 3.0, "atten": 220.0, "shadows": True,
     "keys": [(0, 0.0), (3593, 0.0), (3700, 0.1), (4170, 0.1), (4290, 1.0), (4560, 1.0), (4584, 0.0), (END, 0.0)]},
]
for side, y, d in (("L", WALL_L, 40.0), ("R", WALL_R, -40.0)):
    SPECS.append({"label": "S3 Drama Graze %s1" % side, "cls": "SpotLight", "loc": (11700.0, y + d, 260.0),
                  "aim": (17300.0, y + d * 0.2, 300.0), "cd": 3000.0, "kelvin": 6500.0, "inner": 3.0, "outer": 9.0,
                  "radius": 2.0, "atten": 7000.0, "shadows": True,
                  "keys": [(0, 0.0), (3120, 0.0), (3192, 1.0), (4560, 1.0), (4656, 0.3), (END, 0.3)]})
    SPECS.append({"label": "S3 Drama Graze %s2" % side, "cls": "SpotLight", "loc": (17200.0, y + d, 420.0),
                  "aim": (11600.0, y + d * 0.2, 380.0), "cd": 3000.0, "kelvin": 6500.0, "inner": 3.0, "outer": 9.0,
                  "radius": 2.0, "atten": 7000.0, "shadows": True,
                  "keys": [(0, 0.0), (3150, 0.0), (3222, 1.0), (4560, 1.0), (4656, 0.3), (END, 0.3)]})

WAVE_GAIN = {"Ground Row": 2.5, "Warm Side": 1.8}
SHIMMER = {"from": 540, "step": 12, "a1": 0.22, "p1": 3.7, "a2": 0.12, "p2": 1.3}


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
    a = json.load(open(HERE + "s3_drama_lights_args.json", encoding="utf-8"))
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
    wave_before = {o: [(int(k.get_time().frame_number.value), float(k.get_value())) for k in ch.get_keys()] for o, ch in waves}
    if mode == "DRY":
        unreal.log("S3DRAMA_DRY_OK|run=%s|existing_ours=%d|waves=%d|wave_key_counts=%s|have_root=%s|have_pearl=%s" % (
            run, len(ours), len(waves), sorted(set(len(v) for v in wave_before.values())),
            "S3 Hangar Root" in acts, "S3 PearlClam Pearl" in acts))
        return
    if mode == "APPLY":
        if a.get("confirm") != "APPLY S3DRAMA" or os.path.exists(REC) or ours:
            raise RuntimeError("CONFIRM_OR_RECORD_OR_EXISTING|ours=%d" % len(ours))
        if len(waves) != 7 or any(len(v) != 4 for v in wave_before.values()):
            raise RuntimeError("WAVE_SHAPE|%s" % {o: len(v) for o, v in wave_before.items()})
        rec = {"run": run, "state": "applying", "wave_before": wave_before, "created": []}
        json.dump(rec, open(REC, "w"), indent=1)
        bdir = "E:/PussStage/Backups/PreS3Drama-%s" % run
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
        for i, (o, ch) in enumerate(waves):
            ks = sorted(ch.get_keys(), key=lambda k: k.get_time().frame_number.value)
            gain = next(g for n, g in WAVE_GAIN.items() if n in o)
            lit = ks[2].get_value() * gain
            ks[2].set_value(lit)
            ks[3].set_value(lit)
            for fr, v in shimmer_keys(lit, i):
                ch.add_key(unreal.FrameNumber(fr), v, time_unit=DR, interpolation=unreal.MovieSceneKeyInterpolation.AUTO)
            n = len(ch.get_keys())
            if n != 4 + len(shimmer_keys(lit, i)):
                raise RuntimeError("WAVE_READBACK|%s|%d|NOTHING SAVED; Don't-Save restart" % (o, n))
    elif mode == "REVERT":
        if a.get("confirm") != "REVERT S3DRAMA" or not os.path.exists(REC):
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
        unreal.log("S3DRAMA_APPLY_OK|run=%s|lights=%d|waves=%d|saved=map+scene" % (run, len(rec["created"]), len(waves)))
    else:
        os.rename(REC, REC + ".reverted-" + run)
        unreal.log("S3DRAMA_REVERT_OK|run=%s|removed=%d" % (run, len(ours)))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3DRAMA_FAILED|run=%s|%r" % (RUN["run"], exc))
