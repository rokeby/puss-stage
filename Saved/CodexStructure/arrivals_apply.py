"""The other five transitions, steps 1 and 2 of 3 (30 Sep; the conductor approved 1 and 2 under
Gary's 29 Sep delegation). Step 3, nesting each hangar into its Scene, is GARY'S and is not here.

For each Scene N in SCENES (1, 2, 3, 5, 6; Scene 4 is p04_arrival_apply.py's and is refused):
1. RE-KEY LS_SN_HangarRise's root pitch the way Scene 4's was: -90 at a NEGATIVE start, 0 at the
   builder's landing (16 s x K, read from the sequence's own last key), AUTO (flat ends). Every
   later beat is untouched. The start is read from LS_S4_HangarRise's applied first key (P04's
   cloth release, -3.567 s), not typed: every Passage ends at 2.5 m/s, so the same time before
   the cut is the same distance before the stop. That start is TRANSPLANTED from P04, not
   measured: when a backcloth is placed for Passage N, rerun with ARRIVAL_RISE_START_S =
   {N: cross_N - lead_N} (revert first) and it becomes derived, as P04's is.
2. PLACE "SN Arrival": SceneCueGuid = the Show cue whose Scene sequence is LS_DevScene_0N (read,
   never written), MotionSequence = LS_SN_HangarRise, MotionBindingGuid = the root's binding,
   DrivenActor = SN Hangar Root. Unnested, it declines on every frame (NoSubSection, one
   warning per session) and never touches the root: checked structurally before, and by asking
   each Arrival after.

Refuses if any rise is already nested or referenced by the Show or a Scene sequence, if anything
is dirty, Sequencer is open, or a ZZ_/TEMP actor exists. Dry run (default): every derived number,
nothing written. Apply (ARRIVALS_APPLY): plain record first, Backups/PreArrivalSequences-*
(level, the five rises, the Show), read-back, saves only the five rises and the level.
Revert (ARRIVALS_REVERT): restores the recorded keys, deletes the Arrivals. Lean: main()."""
import datetime
import json
import os
import shutil

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
S4_RISE = "/Game/InfinityStage/RigAtmos/LS_S4_HangarRise"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "arrivals_record.json")
SCENES = tuple(globals().get("ARRIVAL_SCENES", (1, 2, 3, 5, 6)))
RISE_START_S = dict(globals().get("ARRIVAL_RISE_START_S", {}))


def fail(msg):
    unreal.log_error("ARRIVALS_STOPPED|" + msg)
    raise RuntimeError(msg)


def root_pitch(rise, n):
    binding = next((b for b in rise.get_bindings() if str(b.get_display_name()) == f"S{n} Hangar Root"), None)
    if binding is None:
        fail(f"S{n}: no 'S{n} Hangar Root' binding in {rise.get_name()}")
    track = next(t for t in binding.get_tracks() if isinstance(t, unreal.MovieScene3DTransformTrack))
    return binding, track.get_sections()[0].get_all_channels()[4]


def keys_of(channel):
    return [(k.get_time(time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value, k.get_value()) for k in channel.get_keys()]


def nested_in(scene_seq, rise_path):
    for track in scene_seq.get_tracks():
        if isinstance(track, unreal.MovieSceneSubTrack):
            for sec in track.get_sections():
                seq = sec.get_sequence()
                if seq and seq.get_path_name().split(".")[0] == rise_path:
                    return True
    return False


def smooth_time(start, land, deg):
    """Scene time at which the AUTO two-key rise (an exact smoothstep) passes deg."""
    target, lo, hi = (deg + 90.0) / 90.0, 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if 3 * mid * mid - 2 * mid ** 3 < target else (lo, mid)
    return start + lo * (land - start)


def main():
    apply, revert = bool(globals().get("ARRIVALS_APPLY")), bool(globals().get("ARRIVALS_REVERT"))
    if 4 in SCENES:
        fail("Scene 4 is p04_arrival_apply.py's")
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
        fail("wrong world, or PIE")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    by_label = {a.get_actor_label(): a for a in actors}
    show = unreal.load_asset(SHOW)
    tick = show.get_editor_property("tick_resolution")
    rate = tick.numerator / tick.denominator
    tr = unreal.new_object(unreal.InfinityStageTransportController)
    tr.build_segments(show)
    seg_start = {}
    for s in tr.get_editor_property("segments"):
        label = str(s.get_editor_property("label"))
        if label.startswith("Scene "):
            seg_start[label.split()[1]] = s.get_editor_property("start_frame").value
    del tr
    # The pre-scene start, read from Scene 4's applied rise (P04's cloth release), never typed.
    s4 = unreal.load_asset(S4_RISE)
    s4_fps = s4.get_display_rate().numerator / s4.get_display_rate().denominator
    s4_keys = keys_of(root_pitch(s4, 4)[1])
    if not (s4_keys and s4_keys[0][0] < 0 and abs(s4_keys[0][1] + 90.0) < 1e-3):
        fail(f"LS_S4_HangarRise does not start at negative time: {s4_keys}")
    transplant_s = s4_keys[0][0] / s4_fps
    arrival_cls = getattr(unreal, "InfinityStageArrival", None)
    rows, cue_count, cue_of = [], {}, {}
    for c in show.get_editor_property("cues"):
        sq = c.get_editor_property("scene").get_editor_property("sequence")
        if sq:
            cue_count.setdefault(sq.get_path_name().split(".")[0], []).append(c)
    for n in SCENES:
        scene_path = f"/Game/InfinityStage/Dev/Sequences/LS_DevScene_0{n}"
        rise_path = f"/Game/InfinityStage/RigAtmos/LS_S{n}_HangarRise"
        cues = cue_count.get(scene_path, [])
        if len(cues) != 1:
            fail(f"S{n}: {len(cues)} Show cues play {scene_path}")
        cue_of[n] = cues[0]
        rise = unreal.load_asset(rise_path)
        if rise is None:
            fail(f"S{n}: {rise_path} missing")
        fps = rise.get_display_rate().numerator / rise.get_display_rate().denominator
        binding, pitch = root_pitch(rise, n)
        now = keys_of(pitch)
        land_f = now[-1][0]
        if abs(now[-1][1]) > 1e-3:
            fail(f"S{n}: the last root-pitch key is not the landing at 0: {now}")
        start_f = int(round(RISE_START_S[n] * fps)) if n in RISE_START_S else int(round(transplant_s * fps))
        builder_start = max(f for f, v in now if abs(v + 90.0) < 1e-3 and f < land_f)
        refs = [str(r) for r in unreal.EditorAssetLibrary.find_package_referencers_for_asset(rise_path, False)]
        rec = json.load(open(os.path.join(HERE, f"hangar_s{n}_record.json"), encoding="utf-8"))
        start, land = start_f / fps, land_f / fps
        u0 = -start / (land - start)
        rows.append({
            "scene": n, "cue_guid": cues[0].get_editor_property("cue_guid").to_string(), "cue_label": str(cues[0].get_editor_property("label")),
            "scene_sequence": scene_path, "scene_start_frame": seg_start.get(str(n)), "rise": rise_path, "binding": binding.get_id().to_string(),
            "root": f"S{n} Hangar Root", "root_placed": f"S{n} Hangar Root" in by_label, "arrival_placed": f"S{n} Arrival" in by_label,
            "nested": nested_in(unreal.load_asset(scene_path), rise_path), "referencers": refs,
            "k": rec.get("k"), "dims_cm": {k: rec["hangar"].get(k) for k in ("depth", "half_w", "height")},
            "roof": rec["hangar"].get("roof"), "placeholder": rec["hangar"].get("placeholder"),
            "keys_before": [(f / fps, v) for f, v in now], "keys_new": [(start, -90.0), (land, 0.0)],
            "builder_rise_s": round((land_f - builder_start) / fps, 4), "keyed_rise_s": round(land - start, 4),
            "start_basis": "override" if n in RISE_START_S else "transplanted from P04 (S4's applied start)",
            "pitch_at_scene_start": round(-90.0 + 90.0 * (3 * u0 * u0 - 2 * u0 ** 3), 3),
            "scene_time_at_minus30_to_minus20": [round(smooth_time(start, land, -30.0), 2), round(smooth_time(start, land, -20.0), 2)]})
    plan = {"transplant_start_s": round(transplant_s, 4), "arrival_class_loaded": arrival_cls is not None, "scenes": rows}
    unreal.log(f"ARRIVALS_PLAN|{json.dumps(plan)}")
    if not (apply or revert):
        unreal.log("ARRIVALS_DRY_RUN_OK|mutated=0")
        return
    if arrival_cls is None:
        fail("AInfinityStageArrival is not in the loaded binaries")
    if unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
        fail("something is already dirty")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
        fail("Sequencer is open")
    temps = [l for l in by_label if l.startswith("ZZ_") or "TEMP" in l.upper()]
    if temps:
        fail(f"bench/temp actors in the level: {temps[:5]}")
    rises = {r["scene"]: unreal.load_asset(r["rise"]) for r in rows}
    if revert:
        rec = json.load(open(RECORD, encoding="utf-8"))
        for r in rec["scenes"]:
            n = r["scene"]
            fps = rises[n].get_display_rate().numerator / rises[n].get_display_rate().denominator
            pitch = root_pitch(rises[n], n)[1]
            for k in list(pitch.get_keys()):
                pitch.remove_key(k)
            for t_s, v in r["keys_before"]:
                pitch.add_key(unreal.FrameNumber(int(round(t_s * fps))), float(v), time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                              interpolation=unreal.MovieSceneKeyInterpolation.AUTO)
            if f"S{n} Arrival" in by_label:
                sub.destroy_actor(by_label[f"S{n} Arrival"])
    else:
        bad = [(r["scene"], why) for r in rows for why, hit in (
            ("nested", r["nested"]), ("arrival exists", r["arrival_placed"]), ("no root", not r["root_placed"]),
            ("no scene start", r["scene_start_frame"] is None),
            ("referenced by the Show or a sequence", any(p == SHOW or "/Sequences/" in p for p in r["referencers"]))) if hit]
        if bad or os.path.exists(RECORD):
            fail(f"refused: {bad}, record exists={os.path.exists(RECORD)}")
        stamp = datetime.datetime.now()
        with open(RECORD, "w", encoding="utf-8") as fh:
            json.dump({"written": stamp.isoformat(timespec="seconds"), "transplant_start_s": plan["transplant_start_s"], "scenes": rows}, fh, indent=1)
            fh.flush()
            os.fsync(fh.fileno())
        project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
        backup = os.path.join(project, "Backups", "PreArrivalSequences-" + stamp.strftime("%Y%m%d-%H%M"))
        os.makedirs(backup, exist_ok=True)
        disk = lambda p, ext: os.path.join(project, "Content", *p[len("/Game/"):].split("/")) + ext
        shutil.copy2(disk(EXPECTED_WORLD, ".umap"), backup)
        shutil.copy2(disk(SHOW, ".uasset"), backup)
        for r in rows:
            shutil.copy2(disk(r["rise"], ".uasset"), backup)
        shutil.copy2(RECORD, backup)
        for r in rows:
            n = r["scene"]
            fps = rises[n].get_display_rate().numerator / rises[n].get_display_rate().denominator
            binding, pitch = root_pitch(rises[n], n)
            for k in list(pitch.get_keys()):
                pitch.remove_key(k)
            for t_s, v in r["keys_new"]:
                pitch.add_key(unreal.FrameNumber(int(round(t_s * fps))), float(v), time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                              interpolation=unreal.MovieSceneKeyInterpolation.AUTO)
            root = by_label[r["root"]]
            arr = sub.spawn_actor_from_class(arrival_cls, root.get_actor_location(), unreal.Rotator(0.0, 0.0, 0.0))
            arr.set_actor_label(f"S{n} Arrival")
            arr.set_folder_path(root.get_folder_path())
            arr.set_editor_property("tags", [unreal.Name(f"RigAtmos.Scene{n}Hangar"), unreal.Name("RigAtmos.Arrival")])
            arr.set_editor_property("scene_cue_guid", cue_of[n].get_editor_property("cue_guid"))
            arr.set_editor_property("motion_sequence", rises[n])
            arr.set_editor_property("motion_binding_guid", binding.get_id())
            arr.set_editor_property("driven_actor", root)
    # Read back, before any save: keys as planned; each Arrival carries its GUIDs and DECLINES
    # (unnested); the root never moved.
    back = []
    for r in rows:
        n = r["scene"]
        fps = rises[n].get_display_rate().numerator / rises[n].get_display_rate().denominator
        got = [(round(f / fps, 4), v) for f, v in keys_of(root_pitch(rises[n], n)[1])]
        want = [(round(round(t * fps) / fps, 4), v) for t, v in (r["keys_before"] if revert else r["keys_new"])]
        if got != want:
            fail(f"S{n}: keys {got}, wanted {want} (NOT saved)")
        if not revert:
            arr = next(a for a in sub.get_all_level_actors() if a.get_actor_label() == f"S{n} Arrival")
            ok = (arr.get_editor_property("scene_cue_guid").to_string() == r["cue_guid"]
                  and arr.get_editor_property("motion_binding_guid").to_string() == r["binding"])
            root = by_label[r["root"]]
            p0 = root.root_component.get_editor_property("relative_rotation").pitch
            mt = unreal.FrameTime(frame_number=unreal.FrameNumber(int(r["scene_start_frame"] - 2.0 * rate)), sub_frame=0.0)
            declined = arr.resolve_rotation_at_master_frame(show, mt) is None and not arr.evaluate_at_master_frame(show, mt)
            p1 = root.root_component.get_editor_property("relative_rotation").pitch
            if not (ok and declined and abs(p1 - p0) < 1e-6):
                fail(f"S{n}: arrival guids ok={ok}, declined={declined}, root pitch {p0}->{p1} (NOT saved)")
            back.append(f"S{n}:keys={got}:declined:root={p0:.3f}")
        else:
            back.append(f"S{n}:keys={got}")
    for r in rows:
        if not unreal.EditorAssetLibrary.save_asset(r["rise"], only_if_is_dirty=False):
            fail(f"save failed: {r['rise']}")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed")
    if revert:
        os.replace(RECORD, RECORD + ".reverted")
    dirty = [str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()] + \
            [str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    unreal.log(f"ARRIVALS_OK|{'reverted' if revert else 'applied'}|{'|'.join(back)}|dirty_after={dirty}")


main()
