"""CHOREO SONG MARKERS REFRESH: replace the song markers ("bar n" / "§ <label>") in each Passage's Choreo after the
walking music changed (Cameron, 5 Oct). Offline-written 5 Oct, NEVER RUN IN UNREAL. Harness:
test_choreo_song_markers_refresh.py (system Python, no Unreal).

Tiers per claim: [decl] declaration-proven (header/source we can read, file:line), [prec] in-repo precedent call
(cited), [meas] an earlier run's read-back record (cited), [inf] inferred (why stated).

WHAT A SONG MARKER IS (the exact pattern choreo_tool writes; nothing else is ever removed)
  * choreo_tool._song_markers labels every 4th non-Rejected beat (sorted by time) "bar %d" with d = index//4 + 1 >= 1,
    and every non-Rejected major change "§ " + (str(label) or "change")  [decl Saved/CodexCueing/choreo_tool.py:114-124].
  * It keeps markers with 0 <= t <= Passage length + 30 s [decl choreo_tool.py:148, TAIL_SECONDS :32], and writes each
    as a MovieSceneMarkedFrame with ONLY frame_number and label set (frame = round(s * master ticks/s)), via
    sequence.add_marked_frame [decl choreo_tool.py:189-196], whose deprecated form takes TickResolution
    [decl UE_5.8 MovieSceneSequenceExtensions.h:550]. So a song marker has comment "", use_custom_color False,
    determinism fence False, inclusive False [decl MovieSceneMarkedFrame.h:37-61 defaults; inf: default-constructed].
  * Classification (classify(), in this order):
      GO   - matches the transport's GO parser (copied from cue_list_tool.py:27, InfinityStageGoCues::ParseMarkerLabel)
             -> KEPT, whatever else it contains ("GO 12 bar crossing" is a GO marker).
      KEEP - label listed in args.declared_keep -> KEPT.
      SONG - label EXACTLY ^bar [1-9][0-9]*$ or ^§ <body>$ with body in args.change_bodies, AND all non-label fields
             at the choreo_tool defaults -> removed and replaced.
      AMBIGUOUS - anything else that looks like a song marker (word "bar" in any case, the "§" sign, "bar" prefix,
             a song-pattern label with a comment / custom colour / fence) -> the whole run REFUSES.
      OTHER - everything else (VampStart, curtain marks, notes) -> KEPT.
  * Extra identity check: the old song markers must equal, frame for frame, choreo_tool's recompute from the OLD song
    analysis (args.old_analysis, the _superseded_20261005 JSON) or from the still-linked MusicMap (walking swap kept it:
    walking_music_swap_record_*.json args.analysis_map_policy "keep" [meas]); else OLD_SONG_MARKERS_UNEXPLAINED.

WHERE THE NEW MARKERS COME FROM
  * The rail's MusicMap still describes the OLD song [meas walking_music_swap_record_P0*.json rail_after.analysis_map ==
    rail_before.analysis_map], so this tool does NOT read the map for the new markers: it feeds the NEW analysis JSON
    to choreo_tool's own _plan/_song_markers through a proxy that replaces only that rail's analysis_map. The JSON is
    turned into map-shaped markers the way the importer does: time, label (default "Major change suggestion"), state
    Suggested for a freshly-fingerprinted map [decl InfinityStageMusicAnalysisImporter.cpp:77-91, 160, 212-213].
  * Guards: JSON passage == n, JSON source.sha256 == the walking record's imported sha256 for Passage n, live rail guid
    and sound == the record's rail / rail_after.sound, every JSON proposal state "Suggested".

Modes (choreo_song_markers_refresh_run.py <- choreo_song_markers_refresh_args.json, confirm "<MODE> SONGMARKERS"):
  DRY    read-only; choreo_song_markers_refresh_dry.json; CHOREO_SONG_MARKERS_DRY_OK|run=..|per=..
  APPLY  guards (world, no PIE, Sequencer closed, clean census, no record covering the set) -> plan every Passage first
         (any refusal stops before a write) -> backup the Choreo .uassets (sha-checked) -> EXCLUSIVE record of every
         marker (all fields) -> per Choreo: delete song markers high index first, verifying the marker at each index
         before deleting and judging by re-listing -> add the new markers (TickResolution) -> read back: kept markers
         identical (all fields), song markers == plan -> census dirty <= the Choreos -> save ONLY those -> read back
         again -> census clean -> CHOREO_SONG_MARKERS_APPLY_OK|run=..|per=..
  REVERT remove exactly the recorded new song markers (refuse on drift), re-add every recorded old song marker with all
         its fields, same gates; record renamed .reverted-<run>; CHOREO_SONG_MARKERS_REVERT_OK|run=..|per=..
  Failure: CHOREO_SONG_MARKERS_STOPPED|run=..|reason=..  A failure after the first delete leaves UNSAVED in-memory
         changes: restart the editor with Don't Save (nothing was saved) - never Save All.
Never: Save All, level save, reload, open/scrub Sequencer, end PIE, touch a GO / non-song marker, keep unreal objects in
module globals. Importing without `unreal` runs nothing.
"""
import collections
import datetime
import hashlib
import json
import os
import re
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None


TOOL = "choreo_song_markers_refresh"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"                 # choreo_tool.py:29
MASTER_PATH = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"   # choreo_tool.py:30
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"   # walking_music_swap.py:104
ARGS_NAME = "choreo_song_markers_refresh_args.json"
DRY_NAME = "choreo_song_markers_refresh_dry.json"
RECORD_PREFIX = "choreo_song_markers_refresh_record_"
WALK_RECORD_PREFIX = "walking_music_swap_record_"
CHOREO_TOOL_REL = os.path.join("CodexCueing", "choreo_tool.py")
PASSAGE_KEYS = ("1", "2", "3", "4", "5", "6")
SECTION = "§"

GO_RE = re.compile(r"^\s*GO\s+([0-9.]*[0-9][0-9.]*)(?:\s+(HOLD|PASS)\b)?\s*(.*)$")   # cue_list_tool.py:27
BAR_RE = re.compile(r"^bar ([1-9][0-9]*)$")                                          # choreo_tool.py:119
CHANGE_RE = re.compile(r"^§ (.+)$", re.DOTALL)                                  # choreo_tool.py:123-124
LOOKALIKE_RE = re.compile(r"(\bbar\b|^\s*bar|§)", re.IGNORECASE)
JSON_DEFAULT_LABELS = {"beatProposals": "Beat suggestion",
                       "majorChangeProposals": "Major change suggestion"}            # Importer.cpp:212-213
FIELDS = ("frame", "label", "comment", "color", "use_custom_color", "fence", "inclusive")
DEFAULTS = {"comment": "", "use_custom_color": False, "fence": False, "inclusive": False}


class PlanError(Exception):
    pass


# =====================================================================================================================
# Pure: choreo_tool loading, classification, maths, gates
# =====================================================================================================================

def load_choreo_tool(path):
    """choreo_tool definitions only (its trailing run() is cut), as curtain_sleight_diag_bindings.py:9-12 does."""
    with open(path, "r", encoding="utf-8") as handle:
        src = handle.read()
    cut = src.rindex("\nrun()")
    ns = {"__name__": "choreo_tool_lib", "__file__": path}
    exec(compile(src[:cut], "choreo_tool.py", "exec"), ns)
    for name in ("_plan", "_song_markers", "_passage_sections", "_gs", "BEATS_PER_BAR", "TAIL_SECONDS"):
        if name not in ns:
            raise PlanError("CHOREO_TOOL_CHANGED: %s missing" % name)
    if ns["BEATS_PER_BAR"] != 4 or ns["TAIL_SECONDS"] != 30.0:
        raise PlanError("CHOREO_TOOL_CHANGED: BEATS_PER_BAR=%r TAIL_SECONDS=%r" % (ns["BEATS_PER_BAR"], ns["TAIL_SECONDS"]))
    ns["__sha256__"] = hashlib.sha256(src.encode("utf-8")).hexdigest()
    return ns


def norm_marker(frame, label, comment="", color=(0.0, 0.0, 0.0, 0.0), use_custom_color=False, fence=False,
                inclusive=False):
    return {"frame": int(frame), "label": str(label), "comment": str(comment or ""),
            "color": [float(c) for c in color], "use_custom_color": bool(use_custom_color), "fence": bool(fence),
            "inclusive": bool(inclusive)}


def mkey(m):
    """Exact identity of a marker over every field (color floats compared exactly)."""
    return tuple(tuple(m[f]) if f == "color" else m[f] for f in FIELDS)


def ekey(m):
    """Effective identity: the colour counts only when the marker uses it (an unused CustomColor is invisible)."""
    return tuple((tuple(m["color"]) if m["use_custom_color"] else None) if f == "color" else m[f] for f in FIELDS)


def song_shape(m):
    """Song markers are compared on (frame, label) plus the default fields; color is irrelevant when not custom."""
    return (m["frame"], m["label"], m["comment"], m["use_custom_color"], m["fence"], m["inclusive"])


def classify(m, change_bodies, declared_keep=()):
    """-> (kind, reason); kind in go / keep / song / ambiguous / other."""
    label = m["label"]
    if GO_RE.match(label):
        return "go", "GO cue"
    if label in declared_keep:
        return "keep", "declared_keep"
    bar, change = BAR_RE.match(label), CHANGE_RE.match(label)
    if bar or change:
        if change and change.group(1) not in change_bodies:
            return "ambiguous", "section-sign label with an unknown body %r" % change.group(1)
        odd = [f for f, v in DEFAULTS.items() if m[f] != v]
        if odd:
            return "ambiguous", "song-pattern label with non-default %s" % ",".join(odd)
        return "song", "bar" if bar else "change"
    if LOOKALIKE_RE.search(label):
        return "ambiguous", "looks like a song marker but is not the exact choreo_tool pattern"
    return "other", "not a song marker"


def partition(markers, change_bodies, declared_keep=()):
    out = {"song": [], "kept": [], "ambiguous": []}
    for index, m in enumerate(markers):
        kind, why = classify(m, change_bodies, declared_keep)
        row = dict(m, index=index, kind=kind, why=why)
        out["song" if kind == "song" else "ambiguous" if kind == "ambiguous" else "kept"].append(row)
    return out


def strip_index(rows):
    return [{f: r[f] for f in FIELDS} for r in rows]


def same_multiset(a, b, key=mkey):
    return collections.Counter(key(x) for x in a) == collections.Counter(key(x) for x in b)


def span(rows):
    frames = [r["frame"] for r in rows]
    return {"count": len(rows), "first": min(frames) if frames else None, "last": max(frames) if frames else None}


# ------------------------------------------------------------------------- JSON -> map-shaped proxy for choreo_tool

class _Obj(object):
    """Minimal get_editor_property shim."""

    def __init__(self, **props):
        self._p = props

    def get_editor_property(self, name):
        return self._p[name]


class _Frame(object):
    def __init__(self, value):
        self.value = value


def json_analysis_refusals(analysis, key, sha256):
    r = []
    if str(analysis.get("passage")) != str(key):
        r.append("ANALYSIS_PASSAGE: file says %r, want %s" % (analysis.get("passage"), key))
    got = (analysis.get("source") or {}).get("sha256")
    if got != sha256:
        r.append("ANALYSIS_SHA: %s vs walking record %s" % (got, sha256))
    if (analysis.get("safety") or {}).get("cueScoreMutated") is not False:
        r.append("ANALYSIS_UNSAFE: safety.cueScoreMutated is not false (importer refuses it, Importer.cpp:127-131)")
    for field in JSON_DEFAULT_LABELS:
        states = set(str(p.get("state")) for p in analysis.get(field) or [])
        if states - {"Suggested"}:
            r.append("ANALYSIS_STATE: %s has %s (a fresh import makes every marker Suggested)" % (field, sorted(states)))
    return r


def json_map_proxy(analysis, suggested_state):
    """The NEW analysis JSON shaped like UInfinityStageMusicMapAsset as choreo_tool reads it [decl Importer.cpp:77-91]."""
    def markers(field):
        out = []
        for p in analysis.get(field) or []:
            label = p["label"] if isinstance(p.get("label"), str) else JSON_DEFAULT_LABELS[field]
            out.append(_Obj(time_seconds=float(p["timeSeconds"]), label=label, state=suggested_state))
        return out
    return _Obj(beat_proposals=markers("beatProposals"), major_change_proposals=markers("majorChangeProposals"))


class _RailProxy(object):
    def __init__(self, rail, amap):
        self._rail, self._amap = rail, amap

    def get_editor_property(self, name):
        return self._amap if name == "analysis_map" else self._rail.get_editor_property(name)


class _ShowProxy(object):
    """Delegates to the live Show; only rail `rail_guid`'s analysis_map is replaced."""

    def __init__(self, show, rail_guid, amap, gs):
        self._show, self._rail_guid, self._amap, self._gs = show, rail_guid, amap, gs

    def get_editor_property(self, name):
        value = self._show.get_editor_property(name)
        if name == "music_rails":
            return [(_RailProxy(r, self._amap) if self._gs(r.get_editor_property("rail_guid")) == self._rail_guid else r)
                    for r in value]
        return value


def plan_markers(ns, ue, show, master, label, master_tick_rate, amap_override=None, rail_guid=None):
    """choreo_tool's own _plan for one Passage -> (marker dicts with choreo_tool's frames, row). amap_override swaps in
    a map proxy for that rail only. Frames: int(round(seconds * ticks/s)) [decl choreo_tool.py:189-192]."""
    source = show if amap_override is None else _ShowProxy(show, rail_guid, amap_override, lambda g: ns["_gs"](ue, g))
    rows, _ = ns["_plan"](ue, source, master, [label])
    if len(rows) != 1:
        raise PlanError("PLAN_ROWS: %s gave %d rows" % (label, len(rows)))
    row = rows[0]
    out = [norm_marker(int(round(seconds * master_tick_rate)), text) for seconds, text in row["markers"]]
    return out, row


def change_bodies_of(markers):
    return sorted(set(CHANGE_RE.match(m["label"]).group(1) for m in markers if CHANGE_RE.match(m["label"])))


def plan_refusals(part, new_markers, old_expected_sets, choreo_path):
    """Pure refusals for one Choreo's plan."""
    r = []
    if not choreo_path:
        r.append("NO_CHOREO")
    if part["ambiguous"]:
        r.append("AMBIGUOUS: %s" % "; ".join("[%d] %r (%s)" % (a["index"], a["label"], a["why"]) for a in part["ambiguous"]))
    old = strip_index(part["song"])
    if not any(same_multiset(old, exp, song_shape) for exp in old_expected_sets.values() if exp is not None):
        r.append("OLD_SONG_MARKERS_UNEXPLAINED: %d song markers match neither %s" % (len(old), sorted(old_expected_sets)))
    if same_multiset(old, new_markers, song_shape):
        r.append("NOOP: the Choreo already carries the new song markers (NOOP is not success)")
    for m in new_markers:
        if BAR_RE.match(m["label"]) is None and CHANGE_RE.match(m["label"]) is None:
            r.append("NEW_LABEL_NOT_SONG_PATTERN: %r" % m["label"])
    return r


def live_gates(state):
    """Refusals from editor state (pure)."""
    r = []
    mode = str(state.get("mode") or "").upper()
    if mode not in ("DRY", "APPLY", "REVERT"):
        r.append("MODE_INVALID: %r" % state.get("mode"))
    if state.get("confirm") != "%s SONGMARKERS" % mode:
        r.append("CONFIRM_MISMATCH: %r, want %r" % (state.get("confirm"), "%s SONGMARKERS" % mode))
    if state.get("wrong_world"):
        r.append("WRONG_WORLD: %s" % state["wrong_world"])
    if state.get("pie"):
        r.append("PIE_OR_SIE_ACTIVE (refused; never ends PIE)")
    if state.get("sequencer_open"):
        r.append("SEQUENCER_IS_OPEN (an open Sequencer evaluates and dirties the map)")
    census = state.get("census") or {}
    if census.get("content") or census.get("maps"):
        r.append("DIRTY_CENSUS: %s" % json.dumps(census, sort_keys=True))
    if mode == "APPLY" and state.get("overlapping_records"):
        r.append("RECORD_COVERS_TARGET: %s (REVERT that set first)" % state["overlapping_records"])
    if mode == "REVERT" and not state.get("record_applied"):
        r.append("NO_APPLIED_RECORD for this passage set")
    return r


def validate_args(args):
    r = []
    mode = str(args.get("mode") or "").upper()
    if mode not in ("DRY", "APPLY", "REVERT"):
        r.append("MODE_INVALID: %r" % args.get("mode"))
    keys = [str(k) for k in args.get("passages") or []]
    if not keys or any(k not in PASSAGE_KEYS for k in keys) or len(set(keys)) != len(keys):
        r.append("PASSAGES_INVALID: %r" % args.get("passages"))
    for k in keys:
        if k not in (args.get("analysis") or {}):
            r.append("NO_NEW_ANALYSIS for Passage %s" % k)
    if not args.get("change_bodies"):
        r.append("CHANGE_BODIES_EMPTY")
    return r


def census_gate(census, allowed):
    out = []
    stray = sorted(set(census.get("content") or []) - set(allowed))
    if stray:
        out.append("UNEXPECTED_DIRTY: %s" % stray)
    if census.get("maps"):
        out.append("MAP_DIRTY: %s" % census["maps"])
    return out


def record_name(keys):
    return RECORD_PREFIX + "-".join("P%02d" % int(k) for k in sorted(keys, key=int)) + ".json"


def records_covering(folder, keys, prefix=RECORD_PREFIX):
    """Live (non-archived) record files whose passage set overlaps keys."""
    want, hits = set("P%02d" % int(k) for k in keys), []
    for name in sorted(os.listdir(folder)):
        if name.startswith(prefix) and name.endswith(".json"):
            if set(name[len(prefix):-5].split("-")) & want:
                hits.append(name)
    return hits


def walking_facts(folder, key):
    """(record name, rail guid, sound after, imported sha256) for Passage key from exactly one APPLIED swap record."""
    hits = records_covering(folder, [key], WALK_RECORD_PREFIX)
    if len(hits) != 1:
        raise PlanError("WALK_RECORD: Passage %s is covered by %d walking-music records %s (P06 is not swapped yet)"
                        % (key, len(hits), hits))
    with open(os.path.join(folder, hits[0]), "r", encoding="utf-8") as handle:
        rec = json.load(handle)
    p = (rec.get("passages") or {}).get(key)
    if not rec.get("applied") or not p:
        raise PlanError("WALK_RECORD_NOT_APPLIED: %s for Passage %s" % (hits[0], key))
    return {"record": hits[0], "rail": p["rail"], "sound": p["rail_after"]["sound"], "sha256": p["import"]["sha256"]}


def write_record_exclusive(path, data):
    """Create-only, fsynced BEFORE any mutation [prec walking_music_swap.py:476-482]."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())


def update_record(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


# ------------------------------------------------------------------------------------- marker editing (adapter-based)
# adapter: list() -> [marker dict] in array order (frames in TICKS); delete(index); add(marker dict).
# Pure over the adapter so the harness drives it with a fake that can lie.

def remove_exact(adapter, targets):
    """Delete exactly the markers in `targets` (dicts, multiset), high index first. Before each delete the marker at the
    index is re-checked; afterwards the result is judged by re-listing, never by the delete call."""
    before = adapter.list()
    want = collections.Counter(mkey(t) for t in targets)
    picked, seen = [], collections.Counter()
    for index, m in enumerate(before):
        k = mkey(m)
        if seen[k] < want[k]:
            seen[k] += 1
            picked.append(index)
    if seen != want:
        raise PlanError("REMOVE_TARGETS_MISSING: %d of %d present" % (sum(seen.values()), sum(want.values())))
    for index in sorted(picked, reverse=True):
        now = adapter.list()
        if index >= len(now) or mkey(now[index]) != mkey(before[index]):
            raise PlanError("REMOVE_INDEX_MOVED: marker %d is no longer %r" % (index, before[index]["label"]))
        adapter.delete(index)
    after = adapter.list()
    expected = [m for i, m in enumerate(before) if i not in set(picked)]
    if [mkey(m) for m in after] != [mkey(m) for m in expected]:
        raise PlanError("REMOVE_RELIST_MISMATCH: %d markers listed, %d expected (a delete call lied?)"
                        % (len(after), len(expected)))
    return after


def add_all(adapter, markers):
    for m in markers:
        adapter.add(m)
    return adapter.list()


def apply_one(adapter, plan_row, change_bodies, declared_keep=()):
    """Remove the planned old song markers, add the new ones, verify. -> list after. Raises PlanError."""
    listed = adapter.list()
    if [mkey(m) for m in listed] != [mkey(m) for m in plan_row["before"]]:
        raise PlanError("DRIFT_SINCE_PLAN: %s markers changed between plan and write" % plan_row["choreo"])
    remove_exact(adapter, plan_row["old_song"])
    mid = partition(adapter.list(), change_bodies, declared_keep)
    if mid["song"] or mid["ambiguous"] or not same_multiset(strip_index(mid["kept"]), plan_row["kept"]):
        raise PlanError("AFTER_REMOVE: song=%d ambiguous=%d kept_ok=%s" % (len(mid["song"]), len(mid["ambiguous"]),
                        same_multiset(strip_index(mid["kept"]), plan_row["kept"])))
    after = add_all(adapter, plan_row["new_song"])
    errs = verify_after(after, plan_row["kept"], plan_row["new_song"], change_bodies, declared_keep)
    if errs:
        raise PlanError("READBACK: " + " || ".join(errs))
    return after


def verify_after(listed, kept, song, change_bodies, declared_keep=()):
    """Kept markers identical over every field (multiset, and in their original relative order); song markers == plan."""
    part = partition(listed, change_bodies, declared_keep)
    errs = []
    got_kept = strip_index(part["kept"])
    if not same_multiset(got_kept, kept):
        errs.append("KEPT_CHANGED: %d listed vs %d recorded" % (len(got_kept), len(kept)))
    elif [mkey(m) for m in got_kept] != [mkey(m) for m in kept]:
        errs.append("KEPT_REORDERED")
    if part["ambiguous"]:
        errs.append("AMBIGUOUS_AFTER: %r" % [a["label"] for a in part["ambiguous"]])
    if not same_multiset(strip_index(part["song"]), song, song_shape):
        errs.append("SONG_NOT_AS_PLANNED: %d listed vs %d planned" % (len(part["song"]), len(song)))
    return errs


def revert_one(adapter, rec_row, change_bodies, declared_keep=()):
    """Remove exactly the recorded new song markers and re-add the recorded old ones (all fields). Non-song markers
    present now (incl. any added since APPLY) are untouched. Refuses on drift."""
    now = partition(adapter.list(), change_bodies, declared_keep)
    if now["ambiguous"]:
        raise PlanError("REVERT_AMBIGUOUS: %r" % [a["label"] for a in now["ambiguous"]])
    if not same_multiset(strip_index(now["song"]), rec_row["new_song"], song_shape):
        raise PlanError("REVERT_DRIFT: song markers differ from what APPLY wrote (%d now, %d recorded)"
                        % (len(now["song"]), len(rec_row["new_song"])))
    kept_now = strip_index(now["kept"])
    remove_exact(adapter, strip_index(now["song"]))
    after = add_all(adapter, rec_row["old_song"])
    part = partition(after, change_bodies, declared_keep)
    if [mkey(m) for m in strip_index(part["kept"])] != [mkey(m) for m in kept_now]:
        raise PlanError("REVERT_KEPT_CHANGED")
    if not same_multiset(strip_index(part["song"]), rec_row["old_song"], song_shape):
        raise PlanError("REVERT_SONG_NOT_RESTORED")
    return after, same_multiset(after, rec_row["before"], ekey)


# =====================================================================================================================
# Live (Unreal) side. Every unreal handle is a local or an adapter attribute.
# =====================================================================================================================

def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
    return os.path.dirname(os.path.abspath(__file__))


def _project():
    if unreal is not None:
        return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.dirname(os.path.dirname(_here()))


def _abs(rel):
    return rel if os.path.isabs(rel) else os.path.join(_project(), rel)


def _stop(run, reason):
    unreal.log_error("CHOREO_SONG_MARKERS_STOPPED|run=%s|reason=%s" % (run, reason))
    raise RuntimeError(reason)


def _census():
    return {"content": sorted(p.get_path_name().split(".")[0]
                              for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name().split(".")[0]
                           for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}


def _path(obj):
    return obj.get_path_name().split(".")[0] if obj is not None else None


def _content_file(path):
    return os.path.join(_project(), "Content", *path[len("/Game/"):].split("/")) + ".uasset"


def _loaded(value):
    if value is not None and hasattr(value, "load_synchronous"):   # choreo_tool.py:101-103
        value = value.load_synchronous()
    return value


class _LiveSeq(object):
    """Marked-frame adapter. TickResolution explicitly [decl MovieSceneSequenceExtensions.h:532, 546;
    prec repair_curtain_marker_time_units.py:44-48 read TICK_RESOLUTION values 72000.. = ticks, meas its json]."""

    def __init__(self, seq):
        self.seq = seq
        self.unit = unreal.MovieSceneTimeUnit.TICK_RESOLUTION

    @staticmethod
    def _get(m, prop, default):
        try:
            return m.get_editor_property(prop)
        except Exception:  # noqa: BLE001
            return default

    def list(self):
        out = []
        for m in unreal.MovieSceneSequenceExtensions.get_marked_frames_from_sequence(self.seq, self.unit):
            c = self._get(m, "custom_color", None)
            out.append(norm_marker(m.get_editor_property("frame_number").value, m.get_editor_property("label"),
                                   self._get(m, "comment", ""),
                                   (c.r, c.g, c.b, c.a) if c is not None else (0.0, 0.0, 0.0, 0.0),
                                   self._get(m, "use_custom_color", False), self._get(m, "is_determinism_fence", False),
                                   self._get(m, "is_inclusive_time", False)))
        return out

    def delete(self, index):
        self.seq.delete_marked_frame(int(index))

    def add(self, m):
        mf = unreal.MovieSceneMarkedFrame()
        mf.set_editor_property("frame_number", unreal.FrameNumber(int(m["frame"])))
        mf.set_editor_property("label", m["label"])
        for key, prop, value in (("comment", "comment", m["comment"]),
                                 ("use_custom_color", "use_custom_color", m["use_custom_color"]),
                                 ("fence", "is_determinism_fence", m["fence"]),
                                 ("inclusive", "is_inclusive_time", m["inclusive"])):
            if value != DEFAULTS[key]:
                mf.set_editor_property(prop, value)       # raises -> stop: a recorded non-default must be restored
        if m["use_custom_color"]:
            mf.set_editor_property("custom_color", unreal.LinearColor(*m["color"]))
        unreal.MovieSceneSequenceExtensions.add_marked_frame_to_sequence(self.seq, mf, self.unit)


def _gather(args, run, ns):
    """Read-only: per Passage, the Choreo, its marker partition, the old recomputes and the new plan."""
    show, master = unreal.load_asset(SHOW_PATH), unreal.load_asset(MASTER_PATH)
    if show is None or master is None:
        raise PlanError("SHOW_OR_MASTER_DID_NOT_LOAD")
    gs = lambda g: ns["_gs"](unreal, g)
    mt = master.get_tick_resolution()
    master_tick = float(mt.numerator) / float(mt.denominator)
    st = show.get_editor_property("tick_resolution")
    if float(st.numerator) / float(st.denominator) != master_tick:
        raise PlanError("TICK_MISMATCH: Show %s/%s vs Master %s/%s" % (st.numerator, st.denominator, mt.numerator,
                                                                         mt.denominator))
    rails = {gs(r.get_editor_property("rail_guid")): r for r in show.get_editor_property("music_rails")}
    settings_by_label = collections.defaultdict(list)
    for s in show.get_editor_property("passage_settings"):
        settings_by_label[str(s.get_editor_property("label"))].append(s)
    bodies, keep = list(args["change_bodies"]), list(args.get("declared_keep") or [])
    rows, refusals = [], []
    for key in [str(k) for k in args["passages"]]:
        label = "Passage %s" % key
        row = {"passage": key, "label": label, "refusals": []}
        rows.append(row)
        try:
            hits = settings_by_label.get(label, [])
            if len(hits) != 1:
                raise PlanError("PASSAGE_COUNT: %d settings labelled %r" % (len(hits), label))
            settings = hits[0]
            seq = _loaded(settings.get_editor_property("choreography"))
            row["choreo"] = _path(seq)
            if seq is None:
                raise PlanError("NO_CHOREO: %s has no Choreography" % label)
            ct = seq.get_tick_resolution()
            if float(ct.numerator) / float(ct.denominator) != master_tick:
                raise PlanError("CHOREO_TICK_MISMATCH: %s" % row["choreo"])
            if seq.are_marked_frames_locked():
                raise PlanError("MARKERS_LOCKED: %s (unlock in Sequencer first; refused rather than override)"
                                % row["choreo"])
            walk = walking_facts(_here(), key)
            music = settings.get_editor_property("music")
            rail_guid = gs(music.get_editor_property("primary_rail_guid"))
            rail = rails.get(rail_guid)
            sound = _path(_loaded(rail.get_editor_property("sound"))) if rail is not None else None
            row["rail"] = {"guid": rail_guid, "sound": sound,
                           "source_in": int(rail.get_editor_property("source_in_frame").value) if rail else None,
                           "rail_offset": int(music.get_editor_property("rail_offset_frames").value),
                           "walking_record": walk["record"]}
            if rail_guid != walk["rail"] or sound != walk["sound"]:
                raise PlanError("RAIL_NOT_AS_SWAPPED: live %s %s vs record %s %s" % (rail_guid, sound, walk["rail"],
                                                                                    walk["sound"]))
            amap = _loaded(rail.get_editor_property("analysis_map"))
            row["linked_map"] = {"path": _path(amap),
                                 "source_sha256": str(amap.get_editor_property("source_sha256")) if amap else None,
                                 "is_new_song": bool(amap) and str(amap.get_editor_property("source_sha256")) == walk["sha256"]}
            with open(_abs(args["analysis"][key]), "r", encoding="utf-8") as handle:
                new_json = json.load(handle)
            bad = json_analysis_refusals(new_json, key, walk["sha256"])
            if bad:
                raise PlanError(" || ".join(bad))
            suggested = unreal.InfinityMusicProposalState.SUGGESTED
            new, prow = plan_markers(ns, unreal, show, master, label, master_tick, json_map_proxy(new_json, suggested),
                                     rail_guid)
            row["music_note"] = prow["music"]
            expected = {}
            if amap is not None:
                expected["linked_map"], _ = plan_markers(ns, unreal, show, master, label, master_tick)
            old_rel = (args.get("old_analysis") or {}).get(key)
            if old_rel:
                with open(_abs(old_rel), "r", encoding="utf-8") as handle:
                    old_json = json.load(handle)
                expected["old_analysis"], _ = plan_markers(ns, unreal, show, master, label, master_tick,
                                                           json_map_proxy(old_json, suggested), rail_guid)
            before = _LiveSeq(seq).list()
            part = partition(before, bodies + change_bodies_of(new), keep)
            old = strip_index(part["song"])
            row.update({
                "before": before, "old_song": old, "kept": strip_index(part["kept"]), "new_song": new,
                "ambiguous": [{"index": a["index"], "label": a["label"], "why": a["why"]} for a in part["ambiguous"]],
                "old": span(old), "new": span(new),
                "kept_labels": [(m["frame"], m["label"], m["kind"]) for m in part["kept"]],
                "old_matches": {k: same_multiset(old, v, song_shape) for k, v in expected.items()},
            })
            row["refusals"] = plan_refusals(part, new, expected, row["choreo"])
            for m in new:
                if classify(m, bodies + change_bodies_of(new), keep)[0] != "song":
                    row["refusals"].append("NEW_MARKER_NOT_CLASSIFIED_SONG: %r" % m["label"])
        except PlanError as exc:
            row["refusals"].append(str(exc))
        refusals += ["P%s %s" % (key, r) for r in row["refusals"]]
    return rows, refusals, master_tick


def _per(rows, field_old="old", field_new="new"):
    return ",".join("P%s:%d>%d+keep%d" % (r["passage"], r[field_old]["count"], r[field_new]["count"], len(r["kept"]))
                    for r in rows)


def _backup(run, suffix, paths):
    folder = os.path.join(_project(), "Backups", "PreChoreoSongMarkers%s-%s" % (suffix, run))
    os.makedirs(folder, exist_ok=False)
    manifest = []
    for path in paths:
        src = _content_file(path)
        dst = os.path.join(folder, os.path.basename(src))
        shutil.copy2(src, dst)
        digest = [hashlib.sha256(open(x, "rb").read()).hexdigest() for x in (src, dst)]
        if digest[0] != digest[1]:
            _stop(run, "BACKUP_HASH_MISMATCH|" + src)
        manifest.append({"asset": path, "source": src, "backup": dst, "sha256": digest[1]})
    with open(os.path.join(folder, "manifest.json"), "x", encoding="utf-8") as handle:
        json.dump({"run": run, "files": manifest}, handle, indent=1)
    return folder


def _save_and_check(run, paths):
    bad = census_gate(_census(), paths)
    if bad:
        _stop(run, "CENSUS_BEFORE_SAVE|" + " || ".join(bad))
    for path in paths:
        if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
            _stop(run, "SAVE_FAILED|" + path)
    after = _census()
    if after["content"] or after["maps"]:
        _stop(run, "DIRTY_AFTER_SAVE|" + json.dumps(after, sort_keys=True))


def run_dry(args, run, ns):
    rows, refusals, tick = _gather(args, run, ns)
    out = {"tool": TOOL, "run": run, "mode": "DRY", "choreo_tool_sha256": ns["__sha256__"], "master_tick": tick,
           "apply_ready": not refusals, "refusals": refusals,
           "rows": [{k: v for k, v in r.items() if k not in ("before", "old_song", "kept", "new_song")} for r in rows],
           "new_markers": {r["passage"]: [(m["frame"], m["label"]) for m in r.get("new_song", [])] for r in rows}}
    path = os.path.join(_here(), DRY_NAME)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(out, handle, indent=1, sort_keys=True, ensure_ascii=False)
    for r in rows:
        unreal.log("CHOREO_SONG_MARKERS_DRY_ROW|run=%s|P%s|choreo=%s|old=%s|new=%s|kept=%s|old_matches=%s|refusals=%d"
                   % (run, r["passage"], r.get("choreo"), r.get("old"), r.get("new"), r.get("kept_labels"),
                      r.get("old_matches"), len(r["refusals"])))
    if refusals:
        _stop(run, "DRY_REFUSED|" + " || ".join(refusals) + "|report=" + path)
    unreal.log("CHOREO_SONG_MARKERS_DRY_OK|run=%s|per=%s|report=%s" % (run, _per(rows), path))


def run_apply(args, run, ns):
    keys = [str(k) for k in args["passages"]]
    rows, refusals, tick = _gather(args, run, ns)
    if refusals:
        _stop(run, "PLAN_REFUSED|" + " || ".join(refusals))
    paths = [r["choreo"] for r in rows]
    if len(set(paths)) != len(paths):
        _stop(run, "CHOREO_SHARED|%s" % paths)
    backup = _backup(run, "", paths)
    rp = os.path.join(_here(), record_name(keys))
    record = {"tool": TOOL, "run": run, "applied": False, "backup": backup, "choreo_tool_sha256": ns["__sha256__"],
              "args": args, "master_tick": tick,
              "passages": {r["passage"]: {k: r[k] for k in ("choreo", "before", "old_song", "kept", "new_song", "rail",
                                                             "linked_map", "old_matches", "music_note")} for r in rows}}
    write_record_exclusive(rp, record)
    bodies, keep = list(args["change_bodies"]), list(args.get("declared_keep") or [])
    for r in rows:
        seq = unreal.load_asset(r["choreo"])
        try:
            apply_one(_LiveSeq(seq), r, bodies + change_bodies_of(r["new_song"]), keep)
        except PlanError as exc:
            _stop(run, "APPLY_P%s|%s|UNSAVED changes in memory: restart the editor with Don't Save" % (r["passage"], exc))
    _save_and_check(run, paths)
    for r in rows:   # read back again from the saved objects
        errs = verify_after(_LiveSeq(unreal.load_asset(r["choreo"])).list(), r["kept"], r["new_song"],
                            bodies + change_bodies_of(r["new_song"]), keep)
        if errs:
            _stop(run, "READBACK_AFTER_SAVE_P%s|%s" % (r["passage"], " || ".join(errs)))
    record["applied"] = True
    update_record(rp, record)
    unreal.log("CHOREO_SONG_MARKERS_APPLY_OK|run=%s|per=%s|backup=%s|record=%s" % (run, _per(rows), backup, rp))


def run_revert(args, run, ns):
    keys = [str(k) for k in args["passages"]]
    rp = os.path.join(_here(), record_name(keys))
    with open(rp, "r", encoding="utf-8") as handle:
        record = json.load(handle)
    bodies = list(record["args"]["change_bodies"])
    keep = list(record["args"].get("declared_keep") or [])
    paths = [record["passages"][k]["choreo"] for k in keys]
    backup = _backup(run, "Revert", paths)
    exact, revert_bodies, kept_before_revert = {}, {}, {}
    for k in keys:
        rec = record["passages"][k]
        b = revert_bodies[k] = bodies + change_bodies_of(rec["new_song"]) + change_bodies_of(rec["old_song"])
        seq = unreal.load_asset(rec["choreo"])
        kept_before_revert[k] = strip_index(partition(_LiveSeq(seq).list(), b, keep)["kept"])
        try:
            _, exact[k] = revert_one(_LiveSeq(seq), rec, b, keep)
        except PlanError as exc:
            _stop(run, "REVERT_P%s|%s|UNSAVED changes in memory: restart the editor with Don't Save" % (k, exc))
    _save_and_check(run, paths)
    for k in keys:   # read back again from the saved objects
        rec = record["passages"][k]
        part = partition(_LiveSeq(unreal.load_asset(rec["choreo"])).list(), revert_bodies[k], keep)
        if part["ambiguous"] or not same_multiset(strip_index(part["song"]), rec["old_song"], song_shape)                 or [mkey(m) for m in strip_index(part["kept"])] != [mkey(m) for m in kept_before_revert[k]]:
            _stop(run, "REVERT_READBACK_P%s" % k)
    archived = rp + ".reverted-" + run
    os.rename(rp, archived)
    unreal.log("CHOREO_SONG_MARKERS_REVERT_OK|run=%s|per=%s|identical_to_before=%s|backup=%s|record=%s"
               % (run, ",".join("P%s:%d" % (k, len(record["passages"][k]["old_song"])) for k in keys),
                  ",".join("P%s:%s" % (k, exact[k]) for k in keys), backup, archived))


def main():
    args = globals().get("SONGMARKER_ARGS")
    if args is None:
        with open(os.path.join(_here(), ARGS_NAME), "r", encoding="utf-8") as handle:
            args = json.load(handle)
    run = str(args.get("run_id") or datetime.datetime.now().strftime("SONGMK-%Y%m%d-%H%M%S"))
    mode = str(args.get("mode") or "").upper()
    bad = validate_args(args)
    if bad:
        _stop(run, "ARGS|" + " || ".join(bad))
    keys = [str(k) for k in args["passages"]]
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    world_name = str(world.get_outermost().get_name()) if world is not None else None
    rp = os.path.join(_here(), record_name(keys))
    applied = False
    if os.path.exists(rp):
        with open(rp, "r", encoding="utf-8") as handle:
            applied = bool(json.load(handle).get("applied"))
    state = {"mode": mode, "confirm": args.get("confirm"), "pie": editor.get_game_world() is not None,
             "wrong_world": None if world_name == EXPECTED_WORLD else str(world_name),
             "sequencer_open": unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None,
             "census": _census(), "overlapping_records": records_covering(_here(), keys), "record_applied": applied}
    early = live_gates(state)
    if early:
        _stop(run, "REFUSED|" + " || ".join(early))
    try:
        ns = load_choreo_tool(os.path.join(_here(), os.pardir, CHOREO_TOOL_REL))
        if mode == "REVERT":
            run_revert(args, run, ns)
        elif mode == "APPLY":
            run_apply(args, run, ns)
        else:
            run_dry(args, run, ns)
    except PlanError as exc:
        _stop(run, "PLAN_REFUSED|" + str(exc))


if unreal is not None:
    main()
