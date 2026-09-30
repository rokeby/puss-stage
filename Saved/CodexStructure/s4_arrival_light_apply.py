"""Scene 4 arrival lighting (30 Sep). Gary picked (a) (b) (c) via the conductor, CONFIRMED in the Rig & atmosphere session
("just build them, sheet is of limited use"). Camera stays free (no keyed tilt: the dog looks up live).
  (a) LIGHT THE RISE FROM THE CURTAIN: the 14 wall practicals' wave moves from 16.5 s to the cut (0 s), same 0.3 s stagger
      and 0.2 s ramp to their keyed value. They ride the walls, so the walls are lit as they emerge.
  (b) LATTICE GLOW FROM THE CURTAIN: the 24 glow lights reach their keyed value (20) by 2.0 s, not 0 until 4 s then 8 s.
  (c) EXPOSURE WITH THE RISE: "S4 Hangar Pinned Exposure" (EV100 0.5 against the passage's -3) no longer switches when the
      camera crosses into it: its saved BlendWeight goes 1 -> 0 (the ONE level property, saved on its own, first), and the
      rise keys BlendWeight 0 at the cut -> 1 at 8 s. So the ~3.5-stop darkening is an 8 s fade driven by the rise.
Uplights (18 s), roof (18.5-24.5 s), lattice fly (24.5-28.5 s) and the root rise are unchanged.
Edits the sequence through the asset API only: Sequencer is NEVER opened (opening a Master-bound sequence dirties the map).
Dry run (default): what would change, mutates nothing. Apply (S4LIGHT_APPLY): guards (world, no PIE, BOTH packages clean,
no Sequencer open, no record), record of every original key as plain floats first, Backups/PreS4ArrivalLight-* (the
sequence + umap), step 1 the PPV weight + level save, step 2 the keys + the sequence save ONLY, read back, census after.
Revert (S4LIGHT_REVERT): original keys back, the PPV binding removed, weight back to 1, same two saves. Lean: main()."""
import datetime
import json
import os
import shutil

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SEQ = "/Game/InfinityStage/RigAtmos/LS_S4_HangarRise"
PPV_LABEL = "S4 Hangar Pinned Exposure"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "s4_arrival_light_record.json")
PRACTICAL_SHIFT_S, GLOW_ON_S, EXPOSURE_S = -16.5, 2.0, (0.0, 8.0)


def fail(msg):
    unreal.log_error("S4LIGHT_STOPPED|" + msg)
    raise RuntimeError(msg)


def dirty():
    return [str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()] + \
        [str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]


def intensity_channels(seq):
    """{parent label: channel} for every LightComponent binding under an S4 Practical / S4 Lattice Glow actor binding."""
    out = {}
    for b in seq.get_bindings():
        parent = b.get_parent()
        pname = str(parent.get_display_name()) if parent and parent.is_valid() else None
        if not pname or not (pname.startswith("S4 Practical") or pname.startswith("S4 Lattice Glow")):
            continue
        for t in b.get_tracks():
            if isinstance(t, unreal.MovieSceneFloatTrack) and str(t.get_property_name()) == "Intensity":
                for s in t.get_sections():
                    for ch in s.get_all_channels():
                        out[pname] = ch
    return out


def keys_of(ch, fps):
    return [[k.get_time().frame_number.value / fps, float(k.get_value())] for k in ch.get_keys()]


def set_keys(ch, keys, fps):
    for k in list(ch.get_keys()):
        ch.remove_key(k)
    for t, v in keys:
        ch.add_key(unreal.FrameNumber(int(round(t * fps))), float(v), time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                   interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)


def new_keys(label, keys):
    if label.startswith("S4 Practical"):
        shifted = [[0.0, 0.0]] + [[max(0.0, t + PRACTICAL_SHIFT_S), v] for t, v in keys if t > 0.0]
    else:
        top = max(v for _, v in keys)
        shifted = [[0.0, 0.0], [GLOW_ON_S, top]]
    out = []
    for t, v in shifted:                      # one key per time: a ramp that now starts at 0 loses its duplicate 0-key
        if out and abs(out[-1][0] - t) < 1e-6:
            out[-1] = [t, v]
        else:
            out.append([round(t, 4), v])
    return out


def ppv_binding(seq):
    for b in seq.get_bindings():
        if str(b.get_display_name()) == PPV_LABEL:
            return b
    return None


def main():
    apply, revert = bool(globals().get("S4LIGHT_APPLY")), bool(globals().get("S4LIGHT_REVERT"))
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
        fail("wrong world, or PIE")
    seq = unreal.load_asset(SEQ)
    rate = seq.get_display_rate()
    fps = rate.numerator / float(rate.denominator)
    chans = intensity_channels(seq)
    ppv = next((a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if a.get_actor_label() == PPV_LABEL), None)
    if ppv is None or len(chans) != 38:
        fail(f"expected 38 practical/glow channels and the PPV, found {len(chans)} channels, ppv={ppv is not None}")
    plan = {label: {"before": keys_of(ch, fps), "after": new_keys(label, keys_of(ch, fps))} for label, ch in sorted(chans.items())}
    sample = {k: plan[k] for k in list(plan)[:2] + [k for k in plan if k.startswith("S4 Practical")][:3]}
    unreal.log(f"S4LIGHT_PLAN|channels={len(plan)}|ppv_weight={ppv.get_editor_property('blend_weight')}|ppv_bound={ppv_binding(seq) is not None}|sample={json.dumps(sample)}")
    if not (apply or revert):
        unreal.log("S4LIGHT_DRY_RUN_OK|mutated=0")
        return
    if dirty() or unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
        fail(f"dirty {dirty()} or Sequencer open")
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    stamp = datetime.datetime.now()

    if revert:
        rec = json.load(open(RECORD, encoding="utf-8"))
        ppv.set_editor_property("blend_weight", float(rec["ppv_weight_before"]))
        if abs(ppv.get_editor_property("blend_weight") - rec["ppv_weight_before"]) > 1e-6 or not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
            fail("PPV weight revert/save failed")
        for label, row in rec["channels"].items():
            set_keys(chans[label], row["before"], fps)
        b = ppv_binding(seq)
        if b is not None:
            b.remove()
        back_bad = [l for l, row in rec["channels"].items() if [[round(t, 3), v] for t, v in keys_of(chans[l], fps)] != [[round(t, 3), v] for t, v in row["before"]]]
        if back_bad or ppv_binding(seq) is not None:
            fail(f"revert read-back failed {back_bad[:3]} (sequence NOT saved)")
        if not unreal.EditorAssetLibrary.save_asset(SEQ, only_if_is_dirty=False):
            fail("sequence save failed")
        os.replace(RECORD, RECORD + ".reverted")
        unreal.log(f"S4LIGHT_OK|reverted|dirty_after={dirty()}")
        return

    if os.path.exists(RECORD):
        fail("already applied (record exists); revert first")
    with open(RECORD, "w", encoding="utf-8") as fh:
        json.dump({"written": stamp.isoformat(timespec="seconds"), "ppv_weight_before": ppv.get_editor_property("blend_weight"), "channels": plan}, fh, indent=1)
    backup = os.path.join(project, "Backups", "PreS4ArrivalLight-" + stamp.strftime("%Y%m%d-%H%M"))
    os.makedirs(backup, exist_ok=True)
    shutil.copy2(os.path.join(project, "Content", *SEQ[len("/Game/"):].split("/")) + ".uasset", backup)
    shutil.copy2(os.path.join(project, "Content", *EXPECTED_WORLD[len("/Game/"):].split("/")) + ".umap", backup)
    shutil.copy2(RECORD, backup)

    # Step 1: the one level property, saved alone.
    ppv.set_editor_property("blend_weight", 0.0)
    if abs(ppv.get_editor_property("blend_weight")) > 1e-6:
        fail("PPV weight read-back (NOT saved)")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed")

    # Step 2: the keys, then the PPV weight track, then the sequence save only.
    for label, row in plan.items():
        set_keys(chans[label], row["after"], fps)
    b = seq.add_possessable(ppv)
    track = b.add_track(unreal.MovieSceneFloatTrack)
    track.set_property_name_and_path("BlendWeight", "BlendWeight")
    sec = track.add_section()
    sec.set_range_seconds(0.0, seq.get_playback_end_seconds())
    ch = sec.get_all_channels()[0]
    for t, v in ((EXPOSURE_S[0], 0.0), (EXPOSURE_S[1], 1.0)):
        ch.add_key(unreal.FrameNumber(int(round(t * fps))), v, time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                   interpolation=unreal.MovieSceneKeyInterpolation.AUTO)
    bad = [l for l, row in plan.items() if [[round(t, 3), v] for t, v in keys_of(chans[l], fps)] != [[round(t, 3), v] for t, v in row["after"]]]
    wk = [[round(t, 3), v] for t, v in keys_of(ch, fps)]
    if bad or wk != [[0.0, 0.0], [8.0, 1.0]]:
        fail(f"read-back failed: channels {bad[:3]}, weight keys {wk} (sequence NOT saved; the level already holds weight 0)")
    if not unreal.EditorAssetLibrary.save_asset(SEQ, only_if_is_dirty=False):
        fail("sequence save failed")
    unreal.log(f"S4LIGHT_OK|applied|channels={len(plan)}|ppv_weight_saved=0.0|weight_keys={wk}|backup={backup}|dirty_after={dirty()}")


main()
