"""Cueing T1b: read-only cue list and lint. Writes nothing to any asset.

Run inside the editor via the guarded MCP route (relativeSavedPath
"CodexCueing/cue_list_tool.py"). It walks the Master and every sequence nested in
it, collects marked frames labelled "GO <number> [HOLD|PASS] <label>", resolves
each to absolute Master seconds, and writes Saved/CodexCueing/cue_list_<run>.json
plus a plain-text cue sheet next to it, for the operator until the Cue List panel
(B1) exists.

Lint (each a WARN line, never a failure):
  - duplicate GO numbers;
  - an audio section that runs across a HOLD (it stops while the show holds:
    make that sound a level actor the sequence switches on, or use a Vamp).
Bindings are deliberately NOT resolved (GetBoundObjects has crashed the editor).

Marker: CUE_LIST_OK|run=<id>|cues=<n>|warnings=<n>|report=<path>.
Never: Save All, reload the level, end PIE, or keep unreal objects in module globals.
"""
import json
import os
import re

MASTER_PATH = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
# Mirrors the transport's parser (InfinityStageGoCues::ParseMarkerLabel): upper-case GO,
# a numeric cue number, optional upper-case HOLD/PASS.
GO_RE = re.compile(r"^\s*GO\s+([0-9.]*[0-9][0-9.]*)(?:\s+(HOLD|PASS)\b)?\s*(.*)$")
NEAR_MISS_RE = re.compile(r"^\s*go\b", re.IGNORECASE)


def _rate(frame_rate):
    return float(frame_rate.numerator) / float(frame_rate.denominator)


def _walk(unreal, sequence, outer_start_s, kind, depth, visited, out):
    """outer_start_s: Master seconds where this sequence's playback start plays."""
    if sequence is None or depth > 8 or sequence.get_path_name() in visited:
        return
    visited.add(sequence.get_path_name())
    tick_rate = _rate(sequence.get_tick_resolution())
    playback_start_s = sequence.get_playback_start_seconds()
    to_master = lambda inner_s: outer_start_s + (inner_s - playback_start_s)

    vamp_starts, vamp_ends = [], []
    for marked in sequence.get_marked_frames():
        label = str(marked.get_editor_property("label"))
        inner_s = marked.get_editor_property("frame_number").value / tick_rate
        if label.strip().lower() == "infinitystage.vampstart":
            vamp_starts.append(to_master(inner_s))
        elif label.strip().lower() == "infinitystage.vampend":
            vamp_ends.append(to_master(inner_s))
    for start, end in zip(sorted(vamp_starts), sorted(vamp_ends)):
        out["vamps"].append({"sequence": sequence.get_name(), "start_s": start, "end_s": end})

    for marked in sequence.get_marked_frames():
        label = str(marked.get_editor_property("label"))
        match = GO_RE.match(label)
        if not match:
            if NEAR_MISS_RE.match(label):
                out["warnings"].append("NOT_A_GO '%s' in %s: the transport ignores it (needs upper-case GO and a cue number)"
                                       % (label, sequence.get_name()))
            continue
        inner_s = marked.get_editor_property("frame_number").value / tick_rate
        mode = (match.group(2) or ("PASS" if kind == "choreo" else "HOLD")).upper()
        out["cues"].append({
            "number": match.group(1), "mode": mode, "label": match.group(3).strip(),
            "master_s": round(to_master(inner_s), 3), "sequence": sequence.get_name(), "kind": kind,
        })

    for track in sequence.get_tracks():
        if isinstance(track, unreal.MovieSceneAudioTrack):
            for section in track.get_sections():
                out["audio"].append({
                    "sequence": sequence.get_name(),
                    "start_s": to_master(section.get_start_frame_seconds()),
                    "end_s": to_master(section.get_end_frame_seconds()),
                })
        if isinstance(track, unreal.MovieSceneSubTrack):
            child_kind = "choreo" if type(track).__name__ == "MovieSceneInfinityChoreoTrack" else "scene"
            for section in track.get_sections():
                child = section.get_sequence()
                if child is not None:
                    _walk(unreal, child, to_master(section.get_start_frame_seconds()),
                          child_kind, depth + 1, visited, out)


def run():
    import unreal

    project_dir = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    import datetime
    run_id = "cuelist-%s" % datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    report_path = os.path.join(project_dir, "Saved", "CodexCueing", "cue_list_%s.json" % run_id)
    sheet_path = report_path.replace(".json", ".txt")
    out = {"run": run_id, "cues": [], "audio": [], "vamps": [], "warnings": []}
    try:
        master = unreal.load_asset(MASTER_PATH)
        if master is None:
            raise RuntimeError("Master failed to load")
        _walk(unreal, master, master.get_playback_start_seconds(), "master", 0, set(), out)
        out["cues"].sort(key=lambda c: c["master_s"])

        seen = {}
        for cue in out["cues"]:
            if cue["number"] in seen:
                out["warnings"].append("DUPLICATE_GO number=%s at %.3f s and %.3f s" % (cue["number"], seen[cue["number"]], cue["master_s"]))
            seen[cue["number"]] = cue["master_s"]
        for cue in out["cues"]:
            if cue["mode"] != "HOLD":
                continue
            for vamp in out["vamps"]:
                if vamp["start_s"] <= cue["master_s"] <= vamp["end_s"]:
                    out["warnings"].append(
                        "HOLD_IN_VAMP go=%s at %.3f s inside a vamp in %s: the transport lists it as PASS"
                        % (cue["number"], cue["master_s"], vamp["sequence"]))
            for audio in out["audio"]:
                if audio["start_s"] < cue["master_s"] < audio["end_s"]:
                    out["warnings"].append(
                        "AUDIO_ACROSS_HOLD go=%s at %.3f s: audio in %s (%.3f-%.3f s) stops while the show holds"
                        % (cue["number"], cue["master_s"], audio["sequence"], audio["start_s"], audio["end_s"]))

        lines = ["CUE SHEET  run=%s  (%d cues)" % (run_id, len(out["cues"])), ""]
        for cue in out["cues"]:
            minutes, seconds = divmod(cue["master_s"], 60.0)
            lines.append("GO %-6s %-4s %3d:%06.3f  %-28s %s"
                         % (cue["number"], cue["mode"], int(minutes), seconds, cue["sequence"], cue["label"]))
        if out["warnings"]:
            lines += ["", "WARNINGS"] + ["  " + w for w in out["warnings"]]
        with open(sheet_path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        for warning in out["warnings"]:
            unreal.log_warning("CUE_LIST_WARN|run=%s|%s" % (run_id, warning))
        unreal.log("CUE_LIST_OK|run=%s|cues=%d|warnings=%d|report=%s|sheet=%s"
                   % (run_id, len(out["cues"]), len(out["warnings"]), report_path, sheet_path))
    except Exception as error:
        out["error"] = str(error)
        unreal.log_error("CUE_LIST_STOPPED|run=%s|reason=%s" % (run_id, error))
        raise
    finally:
        with open(report_path, "w", encoding="utf-8") as handle:
            json.dump(out, handle, indent=2, default=str)


run()
