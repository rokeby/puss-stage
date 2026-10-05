"""READ-ONLY (5 Oct, offline-written, NEVER RUN): is each hangar exit-door leaf CLOSED in the saved level?

Why (Docs/Conductor/CURTAIN_SLEIGHT_TRANSITION_PLAN_2026-10-05.md section 4): scene_exit_block.py REVERT removes the
leaf's binding (and so its swing keys) but reads back no leaf pose. Once unbound, the leaf shows whatever pose the
level holds. APPLY never wrote the leaf's own transform (it only keyed it, scene_exit_block.py:939-944), so the saved
pose SHOULD be the doors tool's closed pose [inf]; a level save made while the Scene was evaluated could have persisted
an open leaf (memory: level saves persist evaluated state). This check reads it.

Per Scene in LEAF_CHECK_SCENES (default [1, 2, 4, 5, 6]): the leaf "S<N> Hangar Exit Door Leaf" must be attached to
"S<N> Hangar Root", and its RELATIVE location / rotation / scale must equal the doors record's closed piece
(hangar_exit_doors_record.json plan.scenes[].pieces role=leaf, state closed; rotation (0, 0, 0) as
hangar_exit_doors.py:603-613 sets it) within 0.1 cm / 0.01 deg / 1e-4. Also reported (info): whether the Scene
sequence still has a binding named like the leaf (an exit-block remnant would still animate it).

Writes Saved/CodexConductor/leaf_closed_check.json only. Asserts the dirty census is unchanged (nothing written).
Markers: LEAF_CLOSED_CHECK_OK|run=..|scenes=..   (every requested leaf closed)
         LEAF_CLOSED_CHECK_NOT_CLOSED|run=..|...  (STOP: re-closing is a separate, backed-up level write)
         LEAF_CLOSED_CHECK_STOPPED|run=..|reason=..
Never Save, never end PIE, never reload the level, no Sequencer UI.
"""
import datetime
import json
import os

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
DOORS_RECORD = "hangar_exit_doors_record.json"
TOL_CM = 0.1
TOL_DEG = 0.01
TOL_SCALE = 1.0e-4


def expected_closed(piece):
    """The closed relative pose the doors tool set (hangar_exit_doors.py:603-613, _set_root_local)."""
    if piece.get("role") != "leaf" or piece.get("state") != "closed":
        raise ValueError("not a closed leaf piece: %r" % piece.get("label"))
    source = piece.get("mesh_size_cm") or [100.0, 100.0, 100.0]
    scale = [1.0 if abs(float(source[i])) <= 1.0e-9 else float(piece["size_cm"][i]) / float(source[i]) for i in range(3)]
    return {"location": [float(v) for v in piece["location_cm"]], "rotation": [0.0, 0.0, 0.0], "scale": scale}


def leaf_verdict(live, piece, root_label):
    """live: {"parent": label, "location": [..], "rotation": [roll, pitch, yaw], "scale": [..]} (relative).
    Returns (verdict, reasons): CLOSED / NOT_CLOSED / NOT_ON_ROOT."""
    want = expected_closed(piece)
    reasons = []
    if live.get("parent") != root_label:
        return "NOT_ON_ROOT", ["parent %r, want %r" % (live.get("parent"), root_label)]
    dl = max(abs(float(a) - float(b)) for a, b in zip(live["location"], want["location"]))
    dr = max(abs(((float(a) - float(b)) + 180.0) % 360.0 - 180.0) for a, b in zip(live["rotation"], want["rotation"]))
    ds = max(abs(float(a) - float(b)) for a, b in zip(live["scale"], want["scale"]))
    if dl > TOL_CM:
        reasons.append("location off by %.3f cm" % dl)
    if dr > TOL_DEG:
        reasons.append("rotation off by %.4f deg (an open swing?)" % dr)
    if ds > TOL_SCALE:
        reasons.append("scale off by %.6f" % ds)
    return ("NOT_CLOSED" if reasons else "CLOSED"), reasons


def _stop(run, reason):
    unreal.log_error("LEAF_CLOSED_CHECK_STOPPED|run=%s|reason=%s" % (run, reason))
    raise RuntimeError(reason)


def _census():
    return {"content": sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}


def main():
    run = str(globals().get("LEAF_CHECK_RUN_ID") or datetime.datetime.now().strftime("LEAF-%Y%m%d-%H%M%S"))
    scenes = [int(s) for s in globals().get("LEAF_CHECK_SCENES", [1, 2, 4, 5, 6])]
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        _stop(run, "PIE_OR_SIE_ACTIVE")                     # never end PIE; refuse
    world = editor.get_editor_world()
    if world is None or str(world.get_outermost().get_name()) != EXPECTED_WORLD:
        _stop(run, "WRONG_WORLD")
    here = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
    with open(os.path.join(here, DOORS_RECORD), "r", encoding="utf-8") as handle:
        doors = json.load(handle)
    census0 = _census()
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    index = {}
    for a in actors:
        index.setdefault(str(a.get_actor_label()), []).append(a)
    show = unreal.load_asset(SHOW_PATH)
    cues = {str(c.get_editor_property("label")): c for c in show.get_editor_property("cues")}
    rows, open_ones = [], []
    for n in scenes:
        plan = [r for r in doors["plan"]["scenes"] if int(r["scene"]) == n]
        if len(plan) != 1:
            _stop(run, "DOORS_ROW|scene=%d" % n)
        leaf_piece = [p for p in plan[0]["pieces"] if p["role"] == "leaf"][0]
        hits = index.get(leaf_piece["label"], [])
        row = {"scene": n, "leaf": leaf_piece["label"], "expected": expected_closed(leaf_piece)}
        if len(hits) != 1:
            row.update({"verdict": "MISSING", "reasons": ["%d actors labelled %s" % (len(hits), leaf_piece["label"])]})
        else:
            leaf = hits[0]
            rc = leaf.root_component                                   # scene_exit_block.py:1027
            loc = rc.get_editor_property("relative_location")
            rot = rc.get_editor_property("relative_rotation")          # [inf] name; set by fit_transition_drapes.py
            scl = rc.get_editor_property("relative_scale3d")
            parent = leaf.get_attach_parent_actor()
            live = {"parent": str(parent.get_actor_label()) if parent is not None else None,
                    "location": [float(loc.x), float(loc.y), float(loc.z)],
                    "rotation": [float(rot.roll), float(rot.pitch), float(rot.yaw)],
                    "scale": [float(scl.x), float(scl.y), float(scl.z)],
                    "mobility": str(rc.get_editor_property("mobility"))}
            verdict, reasons = leaf_verdict(live, leaf_piece, plan[0]["root_label"])
            row.update({"live": live, "verdict": verdict, "reasons": reasons})
        cue = cues.get("Scene %d — External Sound" % n)
        seq = cue.get_editor_property("scene").get_editor_property("sequence") if cue is not None else None
        row["leaf_bound_in_scene"] = bool(seq is not None and any(
            str(b.get_display_name()) == leaf_piece["label"] for b in seq.get_bindings()))
        row["exit_block_record_present"] = os.path.isfile(os.path.join(here, "scene_exit_block_record_S%d.json" % n))
        if row["verdict"] != "CLOSED":
            open_ones.append(n)
        rows.append(row)
    if _census() != census0:
        _stop(run, "CHECK_DIRTIED|before=%r|after=%r" % (census0, _census()))
    out = os.path.join(here, "leaf_closed_check.json")
    with open(out, "w", encoding="utf-8") as handle:
        json.dump({"run": run, "scenes": scenes, "rows": rows, "census": census0}, handle, indent=1, default=str)
    summary = ";".join("S%d=%s%s" % (r["scene"], r["verdict"], ",bound" if r["leaf_bound_in_scene"] else "") for r in rows)
    if open_ones:
        unreal.log_error("LEAF_CLOSED_CHECK_NOT_CLOSED|run=%s|scenes=%s|%s|report=%s" % (run, open_ones, summary, out))
        return
    unreal.log("LEAF_CLOSED_CHECK_OK|run=%s|scenes=%s|%s|mutated=0|report=%s" % (run, scenes, summary, out))


if unreal is not None:
    main()
