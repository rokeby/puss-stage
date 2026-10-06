"""P04 strobe: a local HALO, not a fog wash (Gary note 59, 6 Oct ~00:30: "too strong - more of a local halo than a big
wash through the fog"; keep the stormy strobe opening). DRY / APPLY / REVERT on the ONE level actor
"P04 Strobe (default, Gary to place)" (AInfinityStageStrobeLight, placed STROBE-20261005-004420).

What changes (args p04_strobe_halo_args.json, defaults below):
  peak_intensity        20000 cd -> 3500 cd   (a ~6x cut; the flash still reads as a strobe at the lamp)
  attenuation_radius_cm 1500 cm  -> 450 cm    (the lit fog sphere shrinks from 15 m to 4.5 m: a halo round the lamp)
  ghost_max_weight      1.0      -> 0.35      (the camera-side ghost PPV (bloom/exposure) is a full-frame wash)
Period / flash / decay / colour / place are untouched (Gary liked the rhythm, note 23).

Proof tiers:
  declaration-proven: PeakIntensity, AttenuationRadiusCm, GhostMaxWeight are EditAnywhere/Interp UPROPERTYs
    (InfinityStageStrobeLight.h:39-40, 57-58, 84-85); Tick applies AttenuationRadiusCm and PeakIntensity*Level to the
    transient point light every frame (InfinityStageStrobeLight.cpp:140-160); the light's volumetric scattering is
    NOT exposed (no property; component default) - lowering it needs C++ (see the round-2 report spec).
  measured: the 5 Oct placement wrote and read back period/flash/decay/ghost via these Python names
    (place_default_strobe_p04_record.json "applied"); peak_intensity / attenuation_radius_cm are the same naming the
    Sweep Light took live (place_p02_car_light_record.json "applied").
  inferred: that a 4.5 m radius at 3500 cd reads as a halo in the fog - Gary's stills decide.

Safety: refuses on PIE, a dirty census, a missing/duplicate actor, or current values that differ from the expected
5 Oct values unless args "expected" is updated (Gary may have tuned it by hand: the DRY prints what it found).
Originals are written to p04_strobe_halo_originals_<run>.json BEFORE any change; only the level is saved; read back.
REVERT restores the originals file named in args "revert_from".
"""
from __future__ import annotations

import datetime
import json
import os
import shutil

try:
    import unreal  # type: ignore
except ModuleNotFoundError:
    unreal = None

HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = os.path.join(HERE, "p04_strobe_halo_args.json")
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
LABEL = "P04 Strobe (default, Gary to place)"
FIELDS = ("peak_intensity", "attenuation_radius_cm", "ghost_max_weight")
EXPECTED_5_OCT = {"peak_intensity": 20000.0, "attenuation_radius_cm": 1500.0, "ghost_max_weight": 1.0}
TARGET = {"peak_intensity": 3500.0, "attenuation_radius_cm": 450.0, "ghost_max_weight": 0.35}
LIMITS = {"peak_intensity": (200.0, 8000.0), "attenuation_radius_cm": (150.0, 900.0), "ghost_max_weight": (0.0, 0.6)}


class HaloError(RuntimeError):
    pass


def require(ok, msg):
    if not ok:
        raise HaloError(msg)


def plan_change(current, expected, target):
    """Pure: what APPLY will write. Refuses a target outside the halo LIMITS or a current state that is not the
    expected one (a hand-tuned strobe must be looked at, not overwritten blind)."""
    require(set(current) == set(FIELDS) and set(expected) == set(FIELDS) and set(target) == set(FIELDS),
            "HALO_FIELDS|%s" % sorted(current))
    drift = {k: (current[k], expected[k]) for k in FIELDS if abs(float(current[k]) - float(expected[k])) > 1e-3}
    require(not drift, "HALO_CURRENT_NOT_EXPECTED|%s|update args.expected after reading the DRY" % json.dumps(drift))
    for key, (lo, hi) in LIMITS.items():
        require(lo <= float(target[key]) <= hi, "HALO_TARGET_OUT_OF_RANGE|%s=%s|[%s,%s]" % (key, target[key], lo, hi))
    require(float(target["peak_intensity"]) < float(current["peak_intensity"])
            and float(target["attenuation_radius_cm"]) < float(current["attenuation_radius_cm"]),
            "HALO_NOT_A_CUT|a halo is LESS light over LESS fog")
    return {k: float(target[k]) for k in FIELDS}


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def _read(actor):
    return {k: float(actor.get_editor_property(k)) for k in FIELDS}


def main():
    run = datetime.datetime.now().strftime("HALO-%Y%m%d-%H%M%S")
    args = json.load(open(ARGS, encoding="utf-8"))
    mode = str(args.get("mode", "DRY")).upper()
    require(mode in ("DRY", "APPLY", "REVERT") and args.get("confirm") == "%s P04STROBE" % mode,
            "HALO_CONFIRM|mode=%s|confirm must be '%s P04STROBE'" % (mode, mode))
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    require(editor.get_game_world() is None, "HALO_PIE_ACTIVE")
    world = editor.get_editor_world()
    require(world.get_path_name().split(".")[0] == WORLD, "HALO_WRONG_WORLD")
    require(_census() == {"content": [], "maps": []}, "HALO_DIRTY_BEFORE|" + json.dumps(_census()))
    actors = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
              if str(a.get_actor_label()) == LABEL]
    require(len(actors) == 1 and actors[0].get_class().get_name() == "InfinityStageStrobeLight",
            "HALO_ACTOR_COUNT|%d" % len(actors))
    strobe = actors[0]
    current = _read(strobe)
    if mode == "REVERT":
        original = json.load(open(os.path.join(HERE, args["revert_from"]), encoding="utf-8"))
        require(original.get("label") == LABEL, "HALO_REVERT_FILE")
        target = original["values"]
        applied = json.load(open(os.path.join(HERE, original["applied_file"]), encoding="utf-8"))["values"] \
            if original.get("applied_file") else None
        if applied is not None:
            require(all(abs(current[k] - applied[k]) <= 1e-3 for k in FIELDS), "HALO_REVERT_DRIFT|" + json.dumps(current))
    else:
        target = plan_change(current, args.get("expected", EXPECTED_5_OCT), args.get("target", TARGET))
    report = {"run": run, "mode": mode, "label": LABEL, "current": current, "target": target,
              "location": [strobe.get_actor_location().x, strobe.get_actor_location().y, strobe.get_actor_location().z]}
    if mode == "DRY":
        unreal.log("P04_STROBE_HALO_DRY_OK|run=%s|current=%s|target=%s|mutated=0" % (run, json.dumps(current), json.dumps(target)))
        json.dump(report, open(os.path.join(HERE, "p04_strobe_halo_report_%s.json" % run), "w"), indent=1)
        return report
    originals = os.path.join(HERE, "p04_strobe_halo_originals_%s.json" % run)
    json.dump({"label": LABEL, "run": run, "values": current}, open(originals, "w"), indent=1)
    unreal.log("P04_STROBE_HALO_ORIGINALS|run=%s|path=%s" % (run, originals))
    backup = "E:/PussStage/Backups/PreP04StrobeHalo-" + run
    os.makedirs(backup)
    shutil.copy2(UMAP, backup)
    strobe.modify()
    for key in FIELDS:
        strobe.set_editor_property(key, float(target[key]))
    got = _read(strobe)
    require(all(abs(got[k] - float(target[k])) <= 1e-3 for k in FIELDS), "HALO_SETTER_READBACK|" + json.dumps(got))
    dirty = _census()
    require(not dirty["content"] and dirty["maps"] == [WORLD], "HALO_DIRTY_SCOPE|%s|NOTHING SAVED; Don't-Save restart"
            % json.dumps(dirty))
    require(unreal.EditorLoadingAndSavingUtils.save_map(world, WORLD), "HALO_SAVE_FAILED")
    require(_census() == {"content": [], "maps": []}, "HALO_POST_SAVE_DIRTY")
    again = _read(strobe)
    require(all(abs(again[k] - float(target[k])) <= 1e-3 for k in FIELDS), "HALO_SAVED_READBACK|" + json.dumps(again))
    applied_file = os.path.join(HERE, "p04_strobe_halo_applied_%s.json" % run)
    json.dump({"label": LABEL, "run": run, "values": again, "originals": os.path.basename(originals)}, open(applied_file, "w"), indent=1)
    if mode == "APPLY":  # the originals file learns where its APPLY result is, so a REVERT can refuse on drift
        data = json.load(open(originals, encoding="utf-8"))
        data["applied_file"] = os.path.basename(applied_file)
        json.dump(data, open(originals, "w"), indent=1)
    unreal.log("P04_STROBE_HALO_%s_OK|run=%s|values=%s|level_saved=1|readback=1|backup=%s|originals=%s"
               % (mode, run, json.dumps(again), backup, originals))
    return report


if unreal is not None:
    main()
