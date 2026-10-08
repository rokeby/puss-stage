"""KLARA PREROLL S4 (v5, 7-8 Oct): her characters' animation PRE-ROLLS over the whole dark glide so no static asset
is ever lit (Gary 8 Oct P8 brief); a HARD CUT enters her first shot, where her animation restarts at her frame.
Offline-written, NEVER RUN IN UNREAL by its author. Harness: test_klara_reveal_v5_offline.py (pure parts).

What it writes (Show-side, our assets only; her LS, her level and her BP are never touched):
  - a DUPLICATE of the hookin copy (LS_Children_S4Hangar) at a NEW path (args dup_path), STRIPPED to character
    animation: every ROOT track removed (camera cut, audio, ...), every camera binding (cut-referenced + children),
    every light binding (Intensity/LightColor tracks, LightComponent children, her light labels) and every ORPHAN
    child (parent possessable missing = the 5 L_Animals LightComponent0 bindings [meas test_klara_reveal_offline.py
    S4Bytes.test_orphan_light_components_point_into_l_animals]) removed; kept tracks must be one of KEEP_TRACK_CLASSES;
  - ONE new sub track 'Klara Preroll - S4' in LS_DevScene_04 with ONE section [P0, C) playing the duplicate from her
    frame preroll_her_start (start_frame_offset in her TICKS: the unit APPLY's SLOT_MAPPING_READBACK proved live for
    the reveal slot [meas klara_reveal_record_S4.json slot offset 4800 = 6 x 800]).
The main slot is NOT touched: it keeps her cut frame at C (the restart).

Traps addressed (S4_ENTRY_INVESTIGATION_2026-10-07.md section D):
  1. nested cuts outrank root cuts [memory puss-camera-handover-facts]: the duplicate's camera-cut track is REMOVED
     (and every section of it if remove_track leaves it), read back to zero cut sections;
  2. bindings must resolve in the show level: L_Animals-bound orphans and every light/camera binding stripped; after
     APPLY run SceneCutBindingsResolve + check_scene_cut_bindings; the DRY lists kept names not found as labels in her
     level (the pendulum's 'Pendulum' display name is expected there [meas klara_reveal_dry_S4.json:308]);
  3. the boundary at C: pre-roll [P0, C) exclusive, main slot from C; completion RESTORE_STATE (args); PIE stills at
     C-1, C, C+1 must show no level/T pose (GeometryCache: re-pose before capture, memory ue58-geometrycache-...);
  4. keys are ABSOLUTE [memory puss-passage-keys-absolute]: the duplicate carries the copy's world keys at APPLY time;
     the record stores a key fingerprint and DRY reports PREROLL_KEYS_STALE if the copy is ever re-shifted (a reveal
     REVERT/re-APPLY moves the copy, not the duplicate). ORDER: this REVERT before klara_reveal REVERT (klara_reveal
     REVERT refuses PREROLL_APPLIED while this record is applied); this APPLY after klara_reveal v5 APPLY.

Modes (klara_preroll_s4_run.py <- klara_preroll_s4_args.json; confirm "<MODE> KLARAPREROLL"):
  PROBE  PIE/read-only, gated to the live Scene 4 segment -> KLARAPREROLL_PROBE_OK|run=..|answer=..
  DRY    read-only -> klara_preroll_dry_S4.json; KLARAPREROLL_DRY_OK|run=..|apply_ready=..
  APPLY  gates -> backup -> exclusive record -> duplicate -> strip -> read back -> sub track + section -> mapping read
         back -> census -> save LS_DevScene_04 + duplicate -> read back -> KLARAPREROLL_APPLY_OK|run=..
  REVERT drift check -> backup -> remove our track -> save; leaves the unreferenced duplicate on disk (permanent
         deletion needs Gary's explicit approval) -> KLARAPREROLL_REVERT_OK|run=..
  PREROLL OFF (7 Oct evening: klara_reveal v5 strike_lights "none" -> preroll "off" by default): when the APPLIED v5
         reveal record's plan.preroll.mode is "off", DRY logs KLARAPREROLL_SKIPPED|run=..|reason=PREROLL_OFF (never
         DRY_OK) and APPLY stops KLARAPREROLL_STOPPED|..|PREROLL_OFF; REVERT is unaffected (preroll_off_gate).
Never: Save All, reload a level, open/scrub Sequencer, save her levels, end PIE; no unreal objects in module globals.
Tiers: [decl] header/source, [prec] in-repo precedent, [meas] record/bytes, [inf] inferred (probed in the DRY api table).
"""
import datetime
import hashlib
import json
import math
import os
import re
import shutil
import time

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None

TOOL = "klara_preroll_s4"
CONFIRM_WORD = "KLARAPREROLL"
MODES = ("PROBE", "DRY", "APPLY", "REVERT")
ARGS_NAME = "klara_preroll_s4_args.json"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HER_LEVELS = ("/Game/KK_S1_Animals/L_Animals", "/Game/L_KK_children", "/Game/Japanese_Alley/Maps/Japanese_Alley")
KEEP_TRACK_CLASSES = ("MovieScene3DTransformTrack", "MovieSceneSkeletalAnimationTrack",
                      "MovieSceneControlRigParameterTrack", "MovieSceneGeometryCacheTrack",
                      "MovieSceneObjectPropertyTrack", "MovieSceneVisibilityTrack")
LIGHT_PROPS = ("Intensity", "LightColor", "AttenuationRadius", "Temperature", "IndirectLightingIntensity",
               "VolumetricScatteringIntensity", "SourceRadius", "OuterConeAngle", "InnerConeAngle")
CAMERA_PROPS = ("CurrentFocalLength", "ManualFocusDistance", "FocusSettings.ManualFocusDistance", "CurrentAperture",
                "FieldOfView")
LIGHT_CHILD_NAMES = ("LightComponent0", "LightComponent")
CAMERA_CHILD_NAMES = ("CameraComponent",)
MOTION_TRACK_CLASSES = ("MovieSceneSkeletalAnimationTrack", "MovieSceneControlRigParameterTrack",
                        "MovieSceneGeometryCacheTrack")


class PlanError(Exception):
    pass


# =====================================================================================================================
# Pure (harness-tested)
# =====================================================================================================================

def classify_bindings(rows, light_names, cut_guids):
    """rows = [{"guid", "name", "parent" (guid or None), "cls" (possessed class name or None), "tracks": [{"cls",
    "prop"}]}] -> {"keep": [guid], "remove": [{"guid", "name", "why"}], "refusals": []}.
    camera: a cut-referenced binding, a CameraComponent child or a lens-property track; light: an Intensity/LightColor
    (etc.) track, a LightComponent child, a light class or a label in light_names; orphan: parent guid not among the
    rows (S4: the five L_Animals LightComponent0 [meas]); children of a removed binding go with it."""
    by = {r["guid"]: r for r in rows}
    cut_guids = set(cut_guids or [])
    light_names = set(light_names or [])
    why = {}
    for r in rows:
        props = {t.get("prop") for t in r.get("tracks") or []}
        cls = str(r.get("cls") or "")
        if r["guid"] in cut_guids or r["name"] in CAMERA_CHILD_NAMES or props & set(CAMERA_PROPS) or "Camera" in cls:
            why[r["guid"]] = "camera"
        elif props & set(LIGHT_PROPS) or r["name"] in LIGHT_CHILD_NAMES or r["name"] in light_names or "Light" in cls:
            why[r["guid"]] = "light"
        elif r.get("parent") and r["parent"] not in by:
            why[r["guid"]] = "orphan (parent binding absent: resolves outside the show level's S4 set)"
    changed = True
    while changed:                                         # a removed parent takes its children
        changed = False
        for r in rows:
            if r["guid"] not in why and r.get("parent") in why:
                why[r["guid"]] = "child of removed %s (%s)" % (by[r["parent"]]["name"], why[r["parent"]])
                changed = True
    keep = [r["guid"] for r in rows if r["guid"] not in why]
    refusals = []
    for g in keep:
        bad = sorted({t["cls"] for t in by[g].get("tracks") or [] if t["cls"] not in KEEP_TRACK_CLASSES})
        if bad:
            refusals.append("KEPT_TRACK_CLASS_UNEXPECTED: %s %s (review; not in %s)" % (by[g]["name"], bad,
                                                                                       KEEP_TRACK_CLASSES))
    remove = [{"guid": r["guid"], "name": r["name"], "why": why[r["guid"]]} for r in rows if r["guid"] in why]
    # children before parents (prec klara_reveal.revert_actions ordering)
    depth = lambda g: 0 if not by.get(g, {}).get("parent") or by[g]["parent"] not in by else 1 + depth(by[g]["parent"])
    remove.sort(key=lambda x: (-depth(x["guid"]), x["name"]))
    return {"keep": keep, "remove": remove, "refusals": refusals}


def preroll_plan(reveal_rec, her_range, her_tpf, scene_tpf):
    """From an APPLIED v5 klara_reveal record -> {"range": [P0, C), "her_frame_start", "offset_ticks", "cut"}."""
    r = []
    if not reveal_rec or not reveal_rec.get("applied"):
        return {"refusals": ["REVEAL_NOT_APPLIED: run klara_reveal v5 APPLY first"]}
    plan = reveal_rec.get("plan") or {}
    pr = plan.get("preroll")
    if plan.get("version") == 5 and pr and pr.get("mode") == "off":
        return {"refusals": ["PREROLL_OFF: the applied v5 plan has no pre-roll (%s)" % pr.get("note")], "skip": True}
    if plan.get("version") != 5 or not pr:
        return {"refusals": ["REVEAL_NOT_V5: record plan version %r, preroll %s" % (plan.get("version"), bool(pr))]}
    P0, C = int(pr["range"][0]), int(pr["range"][1])
    cut = int(plan["timeline"]["cut"])
    if C != cut:
        r.append("PREROLL_END_NOT_THE_CUT: %d vs cut %d" % (C, cut))
    if not P0 < C:
        r.append("PREROLL_EMPTY: [%d, %d)" % (P0, C))
    fs = pr.get("first_strike")
    if fs is not None and P0 > int(fs):
        r.append("PREROLL_AFTER_FIRST_STRIKE: %d > %d" % (P0, fs))
    h0 = int(pr["her_frame_start"])
    if not (int(her_range[0]) <= h0 < int(her_range[1])):
        r.append("PREROLL_HER_START_OUTSIDE: %d not in %s" % (h0, her_range))
    off = (h0 - int(her_range[0])) * int(round(float(her_tpf)))
    if int(pr.get("start_offset_ticks", off)) != off:
        r.append("PREROLL_OFFSET_MISMATCH: record %r vs %d" % (pr.get("start_offset_ticks"), off))
    h1 = int(pr.get("her_frame_end", h0 + int(round((C - P0) * float(scene_tpf) / float(her_tpf)))))
    if not h0 < h1 <= int(her_range[1]):
        r.append("PREROLL_HER_END_OUTSIDE: %d not in (%d, %d]" % (h1, h0, int(her_range[1])))
    return {"refusals": r, "range": [P0, C], "her_frame_start": h0, "her_frame_end": h1,
            "offset_ticks": off, "cut": cut, "first_strike": fs}


def preroll_off_gate(mode, reveal_rec):
    """7 Oct evening (Gary: "we just arrive in the dark" -> klara_reveal v5 strike_lights none, preroll off): when the
    APPLIED v5 reveal record carries preroll mode "off" there is nothing to write. -> None (proceed) or
    ("SKIP", reason) for DRY (logs KLARAPREROLL_SKIPPED, never DRY_OK) or ("STOP", reason) for APPLY (KLARAPREROLL_STOPPED).
    REVERT is never gated here: an earlier applied pre-roll must stay revertable."""
    m = str(mode or "").upper()
    if m == "REVERT":
        return None
    pp = preroll_plan(reveal_rec, [0, 1], 1.0, 1.0)
    if not pp.get("skip"):
        return None
    reason = "PREROLL_OFF|" + " || ".join(pp["refusals"])
    return ("SKIP", reason) if m == "DRY" else ("STOP", reason)


def key_fingerprint(rows):
    """rows = [{"binding", "channel", "keys": [[t, v]], "default"}] -> sha256 of the rounded values (0.01 cm)."""
    h = hashlib.sha256()
    for r in sorted(rows, key=lambda x: (x["binding"], x["channel"])):
        h.update(("%s|%s|%s|%s;" % (r["binding"], r["channel"], [[int(t), round(float(v), 2)] for t, v in r["keys"]],
                                    None if r.get("default") is None else round(float(r["default"]), 2))).encode())
    return h.hexdigest()


def ticks_from_seconds(sec, tick_res, what="TIME"):
    """Recover an exact tick from UE's float32 seconds getter when precision permits.
    Ported from the S1 8 Oct live fix: integer frame getters floor sub-frame bounds."""
    x = abs(float(sec))
    if x:
        _m, e = math.frexp(x)
        if 2.0 ** (e - 25) * float(tick_res) >= 0.5:
            raise PlanError("SECONDS_PRECISION: %s %r x %s" % (what, sec, tick_res))
    return int(round(float(sec) * float(tick_res)))


def section_ticks(bounds, tick_res, tpf, what="SECTION"):
    """bounds [(display frame, seconds), ...] -> exact ticks, allowing sub-frame bounds."""
    out = []
    for frame, sec in bounds:
        tick = ticks_from_seconds(sec, tick_res, what)
        if tick // int(tpf) != int(frame):
            raise PlanError("%s_TICK_XCHECK: %s s -> %d ticks -> frame %d; getter %s" %
                            (what, sec, tick, tick // int(tpf), frame))
        out.append(tick)
    return out


def coverage_gaps(ranges, wanted):
    """Uncovered half-open tick ranges after merging overlapping/adjacent ranges."""
    lo, hi = int(wanted[0]), int(wanted[1])
    rows = sorted([max(lo, int(a)), min(hi, int(b))] for a, b in ranges if int(a) < hi and int(b) > lo)
    gaps, at = [], lo
    for a, b in rows:
        if a > at:
            gaps.append([at, a])
        at = max(at, b)
    if at < hi:
        gaps.append([at, hi])
    return gaps


def normalize_pkg(path):
    return re.sub(r"UEDPIE_[0-9]+_", "", str(path or "").split(".")[0].split(":")[0])


def match_actor(cands, label, name, her_level):
    """S1 live-fix policy: label then name, restricted to Klara's streamed level."""
    short = str(her_level).rsplit("/", 1)[-1]
    def in_level(c):
        p = normalize_pkg(c.get("level_pkg"))
        return "path" if p == her_level else ("short" if p.rsplit("/", 1)[-1] == short else None)
    lab = [c for c in cands if c.get("label") == label and in_level(c)]
    nam = [c for c in cands if name and c.get("name") == name and in_level(c)]
    pick, how = (lab[0], "label") if len(lab) == 1 else ((nam[0], "name") if len(lab) == 0 and len(nam) == 1 else (None, None))
    return {"found": pick is not None, "idx": pick.get("idx") if pick else None, "matched_by": how,
            "level_match": in_level(pick) if pick else None, "label_hits_in_level": len(lab),
            "name_hits_in_level": len(nam)}


def probe_gate(master_frame, seg_start, seg_end, scene_frame, windows, filled, burst, cut):
    """Port of the S1 live fix: never sample a numerically matching frame outside Scene 4."""
    if master_frame is None or seg_start is None or not (int(seg_start) <= float(master_frame) < int(seg_end)):
        return None, "NOT_IN_SCENE"
    for w in windows:
        if filled.get(w, 0) >= int(burst):
            continue
        hi = min(w + 2.0, float(cut)) if w < cut else w + 2.0
        if w <= scene_frame < hi:
            return w, None
    return None, "NO_WINDOW"


def _pose_delta(a, b):
    """Maximum numeric leaf delta; incompatible pose structures are different."""
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return float("inf")
        return max((_pose_delta(a[k], b[k]) for k in a), default=0.0)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            return float("inf")
        return max((_pose_delta(x, y) for x, y in zip(a, b)), default=0.0)
    try:
        return abs(float(a) - float(b))
    except (TypeError, ValueError):
        return 0.0 if a == b else float("inf")


def classify_probe(samples, tol=1e-5):
    """Per subject/window MOVING when sampled bone/component values differ beyond tol."""
    groups = {}
    for row in samples:
        groups.setdefault((row.get("subject"), row.get("window")), []).append(row)
    answers = {}
    for key, rows in groups.items():
        vals = [r.get("pose") for r in rows if r.get("found") and r.get("pose")]
        moving = len(vals) >= 2 and any(_pose_delta(vals[0], v) > float(tol) for v in vals[1:])
        answers["%s@%s" % key] = "MOVING" if moving else ("STATIC" if vals else "UNCLEAR")
    overall = "MOVING" if answers and all(v == "MOVING" for v in answers.values()) else \
        ("STATIC_OR_UNCLEAR" if answers else "NO_SAMPLES")
    return {"answer": overall, "answers": answers, "tolerance_note": tol}


def motion_coverage_signature(report):
    """Semantic duplicate/read-back comparison: binding GUIDs are object identity, not coverage."""
    rows = []
    for row in (report or {}).get("bindings") or []:
        rows.append({k: v for k, v in row.items() if k != "guid"})
    return sorted(rows, key=lambda x: json.dumps(x, sort_keys=True))


def validate_args(a):
    r = []
    if str(a.get("mode") or "").upper() not in MODES:
        r.append("MODE_INVALID: %r" % a.get("mode"))
    for k in ("scene_sequence", "copy", "dup_path", "track_name", "reveal_record", "her_level"):
        if not a.get(k):
            r.append("MISSING_%s" % k.upper())
    if a.get("dup_path") and a.get("copy") and a["dup_path"] == a["copy"]:
        r.append("DUP_PATH_IS_THE_COPY")
    if "Master" in str(a.get("scene_sequence", "")):
        r.append("TARGET_IS_THE_MASTER")
    if a.get("completion") not in ("RESTORE_STATE", "KEEP_STATE"):
        r.append("COMPLETION_INVALID: %r" % a.get("completion"))
    if str(a.get("mode") or "").upper() == "PROBE":
        p = a.get("probe") or {}
        if not p.get("subjects") or not p.get("scene_label"):
            r.append("PROBE_CONFIG")
    return r


def live_gates(state):
    r = []
    mode = str(state.get("mode") or "").upper()
    if mode != "DRY" and state.get("confirm") != "%s %s" % (mode, CONFIRM_WORD):
        r.append("CONFIRM_MISMATCH: %r" % state.get("confirm"))
    if state.get("pie"):
        r.append("PIE_OR_SIE_ACTIVE (refused; never ends PIE)")
    if state.get("wrong_world"):
        r.append("WRONG_WORLD: %s" % state["wrong_world"])
    if state.get("sequencer_open"):
        r.append("SEQUENCER_OPEN: %s" % state["sequencer_open"])
    c = state.get("census") or {}
    if c.get("content") or c.get("maps"):
        r.append("DIRTY_CENSUS: %s" % json.dumps(c, sort_keys=True))
    if mode == "APPLY" and not str(state.get("decided_by") or "").strip():
        r.append("NOT_DECIDED: args decided_by is empty")
    if mode == "APPLY" and state.get("record_exists"):
        r.append("RECORD_EXISTS: %s (REVERT first)" % state["record_exists"])
    if mode == "REVERT" and not state.get("record_applied"):
        r.append("NO_APPLIED_RECORD")
    return r


def write_record_exclusive(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "w", encoding="utf-8") as h:
        json.dump(data, h, indent=1, sort_keys=True, default=str)
        h.flush()
        os.fsync(h.fileno())


def update_record(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as h:
        json.dump(data, h, indent=1, sort_keys=True, default=str)
        h.flush()
        os.fsync(h.fileno())
    os.replace(tmp, path)


def load_json(path):
    with open(path, "r", encoding="utf-8") as h:
        return json.load(h)


# =====================================================================================================================
# Live (Unreal). Every unreal handle is a local.
# =====================================================================================================================

def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                            "CodexConductor", "KlaraIngest")
    return os.path.dirname(os.path.abspath(__file__))


def _project():
    return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())


def _file(path, ext):
    return os.path.join(_project(), "Content", *path[len("/Game/"):].split("/")) + ext


def _stop(run, reason):
    unreal.log_error("KLARAPREROLL_STOPPED|run=%s|reason=%s" % (run, reason))
    raise RuntimeError(reason)


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_map_packages())}


def _path(obj):
    return obj.get_path_name().split(".")[0] if obj is not None else None


def _rate(fr):
    return float(fr.numerator) / float(fr.denominator)


def _gs(g):
    return unreal.GuidLibrary.conv_guid_to_string(g)          # memory: never compare Guid structs with ==


def _prop(t):
    try:
        return str(t.get_property_name())
    except Exception:  # noqa: BLE001 - not a property track
        return None


def _binding_rows(seq):
    rows = []
    for b in seq.get_bindings():
        par = b.get_parent()
        pg = _gs(par.get_id()) if (par is not None and hasattr(par, "is_valid") and par.is_valid()) else None
        try:
            pc = unreal.MovieSceneBindingExtensions.get_possessed_object_class(b)   # decl MovieSceneBindingExtensions.h:181
            cls = pc.get_name() if pc is not None else None
        except Exception:  # noqa: BLE001 - classification falls back to names/tracks
            cls = None
        rows.append({"guid": _gs(b.get_id()), "name": str(b.get_display_name()), "parent": pg, "cls": cls,
                     "tracks": [{"cls": t.get_class().get_name(), "prop": _prop(t),
                                 "name": str(t.get_display_name())} for t in b.get_tracks()]})
    return rows


def _cut_guids(seq):
    out = []
    for t in seq.get_tracks():
        if isinstance(t, unreal.MovieSceneCameraCutTrack):
            for s in t.get_sections():
                out.append(_gs(s.get_camera_binding_id().get_editor_property("guid")))
    return out


def _level_actors(world, pkg):          # klara_hookin.py:816-820 [prec]
    for lv in unreal.EditorLevelUtils.get_levels(world):
        if lv.get_outer() is not None and _path(lv.get_outer()) == pkg:
            acts = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
            return [a for a in acts if a.get_level() == lv]
    return []


def _light_names(world, pkg):
    names = set()
    for a in _level_actors(world, pkg):
        if a.get_component_by_class(unreal.LightComponent) is not None:
            names.add(str(a.get_actor_label()))
            names.add(str(a.get_name()))
    return names


def _transform_rows(seq, guids=None):
    """Location/Rotation keys of every 3DTransform section on the given bindings (fingerprint of absolute keys)."""
    rows = []
    for b in seq.get_bindings():
        if guids is not None and _gs(b.get_id()) not in guids:
            continue
        for t in b.get_tracks():
            if isinstance(t, unreal.MovieScene3DTransformTrack):
                for si, s in enumerate(t.get_sections()):
                    for c in s.get_all_channels():
                        nm = str(c.channel_name) if hasattr(c, "channel_name") else str(c.get_name())
                        if not (nm.startswith("Location") or nm.startswith("Rotation")):
                            continue
                        rows.append({"binding": "%s#%d" % (b.get_display_name(), si), "channel": nm,
                                     "keys": [[int(k.get_time().frame_number.value), float(k.get_value())]
                                              for k in c.get_keys()],
                                     "default": float(c.get_default()) if c.has_default() else None})
    return rows


def _tpf(seq):
    q = _rate(seq.get_tick_resolution()) / _rate(seq.get_display_rate())
    if abs(q - round(q)) > 1e-9:
        raise PlanError("TICKS_PER_FRAME_NOT_INTEGER: %r" % q)
    return int(round(q))


def _section_ticks(s, tick_res, tpf, what):
    if not (s.has_start_frame() and s.has_end_frame()):
        raise PlanError("%s_UNBOUNDED" % what)
    return section_ticks([(s.get_start_frame(), s.get_start_frame_seconds()),
                          (s.get_end_frame(), s.get_end_frame_seconds())], tick_res, tpf, what)


def _motion_coverage(seq, keep_guids, pp):
    """Exact-tick coverage for every kept binding that owns a motion track. A gap can expose
    a bind/static pose, so it is an APPLY refusal. S4 intentionally restarts at the cut;
    S1's phase-alignment extension is therefore not applicable here."""
    if pp.get("refusals") or pp.get("skip"):
        return {"wanted_tick": None, "bindings": [], "refusals": []}
    tick_res, tpf = _rate(seq.get_tick_resolution()), _tpf(seq)
    wanted = [int(pp["her_frame_start"]) * tpf, int(pp["her_frame_end"]) * tpf]
    out, refusals = [], []
    for b in seq.get_bindings():
        guid = _gs(b.get_id())
        if guid not in keep_guids:
            continue
        ranges, classes = [], []
        for t in b.get_tracks():
            cls = t.get_class().get_name()
            if cls not in MOTION_TRACK_CLASSES:
                continue
            classes.append(cls)
            for i, s in enumerate(t.get_sections()):
                try:
                    ranges.append(_section_ticks(s, tick_res, tpf, "%s/%s/%d" %
                                                 (b.get_display_name(), cls, i)))
                except PlanError as exc:
                    refusals.append(str(exc))
        if not classes:
            continue
        gaps = coverage_gaps(ranges, wanted)
        row = {"binding": str(b.get_display_name()), "guid": guid, "classes": sorted(set(classes)),
               "ranges_tick": ranges, "wanted_tick": wanted, "gaps_tick": gaps}
        out.append(row)
        if gaps:
            refusals.append("MOTION_GAP: %s %s" % (b.get_display_name(), gaps))
    if not out:
        refusals.append("NO_KEPT_MOTION_TRACKS")
    return {"wanted_tick": wanted, "bindings": out, "refusals": refusals,
            "loop_alignment": "NOT_APPLICABLE: S4 intentionally restarts at the hard cut; exact coverage is required"}


def _our_track(seq, name):
    return [t for t in seq.get_tracks() if isinstance(t, unreal.MovieSceneSubTrack) and str(t.get_display_name()) == name]


def _api_table():
    rows = []

    def probe(api, tier, fn):
        try:
            res = fn()
            rows.append({"api": api, "tier": tier, "ok": bool(res), "result": repr(res)[:160]})
        except Exception as exc:  # noqa: BLE001 - a probe failure is a finding
            rows.append({"api": api, "tier": tier, "ok": False, "result": "%s: %s" % (type(exc).__name__, exc)})

    u = unreal
    probe("EditorAssetLibrary.duplicate_asset/find_package_referencers_for_asset",
          "decl EditorAssetLibrary.h:175,281; no permanent delete in REVERT",
          lambda: [hasattr(u.EditorAssetLibrary, n) for n in ("duplicate_asset",
                                                               "find_package_referencers_for_asset")])
    probe("MovieSceneBindingExtensions.get_possessed_object_class", "decl MovieSceneBindingExtensions.h:181",
          lambda: hasattr(u.MovieSceneBindingExtensions, "get_possessed_object_class"))
    probe("MovieSceneSequence.remove_track (root + camera cut)", "inf; memory: returns lie -> read back",
          lambda: hasattr(u.MovieSceneSequenceExtensions, "remove_track"))
    probe("MovieSceneBindingProxy.remove", "prec klara_hookin.py:1282", lambda: hasattr(u.MovieSceneBindingProxy, "remove"))
    probe("MovieSceneSectionExtensions.get_parent_sequence_frame", "prec klara_reveal.py SLOT_MAPPING_READBACK (live OK)",
          lambda: hasattr(u.MovieSceneSectionExtensions, "get_parent_sequence_frame"))
    probe("MovieSceneSectionExtensions.get_start_frame_seconds/get_end_frame_seconds",
          "decl MovieSceneSectionExtensions.h:54,81; S1 8 Oct live fix",
          lambda: [hasattr(u.MovieSceneSectionExtensions, n) for n in
                   ("get_start_frame_seconds", "get_end_frame_seconds")])
    probe("MovieSceneSubSection.set_sequence", "decl MovieSceneSubSection.h:161-162 [prec klara_hookin.py:1063]",
          lambda: hasattr(u.MovieSceneSubSection, "set_sequence"))
    return rows


def _gather(args, world, run):
    seq = unreal.load_asset(args["scene_sequence"])
    copy = unreal.load_asset(args["copy"])
    if seq is None or copy is None:
        raise PlanError("ASSETS: scene %s copy %s" % (seq is not None, copy is not None))
    rp = os.path.join(_here(), args["reveal_record"])
    rec = load_json(rp) if os.path.exists(rp) else None
    her_range = [int(copy.get_playback_start()), int(copy.get_playback_end())]
    her_tpf = _rate(copy.get_tick_resolution()) / _rate(copy.get_display_rate())
    pp = preroll_plan(rec, her_range, her_tpf, _rate(seq.get_tick_resolution()) / _rate(seq.get_display_rate()))
    rows = _binding_rows(copy)
    cls = classify_bindings(rows, _light_names(world, args["her_level"]), _cut_guids(copy))
    motion = _motion_coverage(copy, set(cls["keep"]), pp)
    names = set()
    for a in _level_actors(world, args["her_level"]):
        names.update([str(a.get_actor_label()), str(a.get_name())])
    by = {r["guid"]: r for r in rows}
    kept_unresolved = sorted(by[g]["name"] for g in cls["keep"] if not by[g]["parent"] and by[g]["name"] not in names)
    root_tracks = [{"cls": t.get_class().get_name(), "name": str(t.get_display_name())} for t in copy.get_tracks()]
    facts = {"plan": pp, "her_range": her_range, "her_tpf": her_tpf, "classify": cls, "motion_coverage": motion,
             "rows": [{k: v for k, v in r.items()} for r in rows], "kept_unresolved_by_label": kept_unresolved,
             "copy_root_tracks": root_tracks, "copy_cut_guids": _cut_guids(copy),
             "copy_fingerprint": key_fingerprint(_transform_rows(copy, set(cls["keep"]))),
             "dup_exists": bool(unreal.EditorAssetLibrary.does_asset_exist(args["dup_path"])),
             "our_tracks": len(_our_track(seq, args["track_name"]))}
    return facts, seq, copy


def run_dry(args, run, world):
    facts, seq, _copy = _gather(args, world, run)
    refusals = list(facts["plan"].get("refusals") or []) + list(facts["classify"]["refusals"]) + \
        list(facts["motion_coverage"].get("refusals") or [])
    warnings = []
    rp = os.path.join(_here(), "klara_preroll_record_S4.json")
    applied = os.path.exists(rp) and load_json(rp).get("applied")
    if applied:
        rec = load_json(rp)
        dup = unreal.load_asset(args["dup_path"])
        fp_dup = key_fingerprint(_transform_rows(dup)) if dup is not None else None
        if fp_dup != rec.get("dup_fingerprint") or facts["copy_fingerprint"] != rec.get("copy_fingerprint"):
            refusals.append("PREROLL_KEYS_STALE: copy/duplicate keys changed since APPLY (keys are absolute: the copy "
                            "was re-shifted?) -> REVERT this, then re-APPLY")
        warnings.append("ALREADY_APPLIED: %s" % rp)
    else:
        if facts["dup_exists"]:
            refusals.append("DUP_EXISTS: %s (a failed run? inspect, delete by hand)" % args["dup_path"])
        if facts["our_tracks"]:
            refusals.append("TRACK_EXISTS: %r in %s" % (args["track_name"], args["scene_sequence"]))
    if facts["kept_unresolved_by_label"]:
        warnings.append("KEPT_NAMES_NOT_LEVEL_LABELS: %s (expected: 'Pendulum' [meas klara_reveal_dry_S4.json:308]; "
                        "SceneCutBindingsResolve + PIE decide)" % facts["kept_unresolved_by_label"])
    report = {"tool": TOOL, "run": run, "args": args, "api_table": _api_table(), "facts": facts,
              "refusals": refusals, "warnings": warnings, "apply_ready": not refusals and not applied, "census": _census()}
    out = os.path.join(_here(), "klara_preroll_dry_S4.json")
    with open(out, "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1, sort_keys=True, default=str)
    for r in report["api_table"]:
        unreal.log("KLARAPREROLL_API|run=%s|ok=%d|%s|%s|%s" % (run, int(r["ok"]), r["api"], r["tier"], r["result"]))
    unreal.log("KLARAPREROLL_PLAN|run=%s|%s" % (run, json.dumps(facts["plan"])))
    for r in facts["classify"]["remove"]:
        unreal.log("KLARAPREROLL_REMOVE|run=%s|%s|%s" % (run, r["name"], r["why"]))
    by = {r["guid"]: r for r in facts["rows"]}
    for g in facts["classify"]["keep"]:
        unreal.log("KLARAPREROLL_KEEP|run=%s|%s|%s" % (run, by[g]["name"], [t["cls"] for t in by[g]["tracks"]]))
    unreal.log("KLARAPREROLL_ROOT_TRACKS_REMOVED|run=%s|%s" % (run, facts["copy_root_tracks"]))
    for t in refusals:
        unreal.log_warning("KLARAPREROLL_REFUSAL|run=%s|%s" % (run, t))
    for t in warnings:
        unreal.log("KLARAPREROLL_WARNING|run=%s|%s" % (run, t))
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|" + json.dumps(_census()))
    unreal.log("KLARAPREROLL_DRY_OK|run=%s|mutated=0|apply_ready=%d|refusals=%d|warnings=%d|report=%s"
               % (run, int(report["apply_ready"]), len(refusals), len(warnings), out))


def _strip(dup, light_names, run):
    """Remove every root track (camera cut included) and every non-character binding; read everything back."""
    rows = _binding_rows(dup)
    cls_ = classify_bindings(rows, set(light_names), _cut_guids(dup))
    if cls_["refusals"]:
        _stop(run, "STRIP_REFUSED|%s|NOTHING SAVED; Don't-Save restart" % cls_["refusals"])
    for t in list(dup.get_tracks()):
        dup.remove_track(t)                        # return value ignored (memory: return values lie): read back below
    for t in list(dup.get_tracks()):               # 5.8: the camera cut track may survive remove_track [inf]
        if isinstance(t, unreal.MovieSceneCameraCutTrack):
            for s in list(t.get_sections()):
                t.remove_section(s)
    gone = {r["guid"] for r in cls_["remove"]}
    for r in cls_["remove"]:                       # children first (classify_bindings order)
        for b in dup.get_bindings():
            if _gs(b.get_id()) == r["guid"]:
                b.remove()                                                # prec klara_hookin.py:1282
    left_root = [t.get_class().get_name() for t in dup.get_tracks()
                 if not (isinstance(t, unreal.MovieSceneCameraCutTrack) and not list(t.get_sections()))]
    cut_secs = _cut_guids(dup)
    after = _binding_rows(dup)
    still = [r["name"] for r in after if r["guid"] in gone]
    kept = sorted(r["guid"] for r in after)
    bad_cls = sorted({t["cls"] for r in after for t in r["tracks"] if t["cls"] not in KEEP_TRACK_CLASSES})
    if left_root or cut_secs or still or kept != sorted(cls_["keep"]) or bad_cls:
        _stop(run, "STRIP_READBACK|root %s cuts %s still %s kept %d/%d classes %s|NOTHING SAVED; Don't-Save restart"
              % (left_root, cut_secs, still, len(kept), len(cls_["keep"]), bad_cls))
    return cls_


def run_apply(args, run, world):
    facts, seq, copy = _gather(args, world, run)
    pp = facts["plan"]
    bad = list(pp.get("refusals") or []) + list(facts["classify"]["refusals"]) + \
        list(facts["motion_coverage"].get("refusals") or [])
    if facts["dup_exists"]:
        bad.append("DUP_EXISTS: %s" % args["dup_path"])
    if facts["our_tracks"]:
        bad.append("TRACK_EXISTS: %r" % args["track_name"])
    if bad:
        _stop(run, "PLAN_REFUSED|" + " || ".join(bad))
    rpath = os.path.join(_here(), "klara_preroll_record_S4.json")
    folder = os.path.join(_project(), "Backups", "PreKlaraPreroll-S4-%s" % run)
    os.makedirs(folder, exist_ok=False)
    manifest = []
    for src in (_file(args["scene_sequence"], ".uasset"), _file(args["copy"], ".uasset")):
        dst = os.path.join(folder, os.path.basename(src))
        shutil.copy2(src, dst)
        hs = [hashlib.sha256(open(x, "rb").read()).hexdigest() for x in (src, dst)]
        if hs[0] != hs[1]:
            _stop(run, "BACKUP_HASH|" + src)
        manifest.append({"source": src, "sha256": hs[1]})
    rec = {"schema": 1, "tool": TOOL, "run": run, "applied": False, "backup": folder, "manifest": manifest,
           "decided_by": args.get("decided_by"), "written": datetime.datetime.now().isoformat(timespec="seconds"),
           "args": args, "plan": pp, "classify": facts["classify"], "copy_fingerprint": facts["copy_fingerprint"],
           "before": {"scene_tracks": [str(t.get_display_name()) for t in seq.get_tracks()]}}
    write_record_exclusive(rpath, rec)
    dup = unreal.EditorAssetLibrary.duplicate_asset(args["copy"], args["dup_path"])          # [prec] hookin
    if dup is None or not unreal.EditorAssetLibrary.does_asset_exist(args["dup_path"]):
        _stop(run, "DUPLICATE_FAILED|%s|NOTHING SAVED; Don't-Save restart" % args["dup_path"])
    rec["dup_created"] = True
    update_record(rpath, rec)
    cls_ = _strip(dup, sorted(_light_names(world, args["her_level"])), run)
    dup_motion = _motion_coverage(dup, set(cls_["keep"]), pp)
    changed = motion_coverage_signature(dup_motion) != motion_coverage_signature(facts["motion_coverage"])
    if dup_motion["refusals"] or changed:
        _stop(run, "DUP_MOTION_COVERAGE|refusals=%s|changed=%s|NOTHING SAVED; Don't-Save restart" %
              (dup_motion["refusals"], changed))
    rec["dup_fingerprint"] = key_fingerprint(_transform_rows(dup))
    if rec["dup_fingerprint"] != facts["copy_fingerprint"]:
        _stop(run, "DUP_KEYS_DIFFER_FROM_COPY|NOTHING SAVED; Don't-Save restart")
    # the sub track + section [P0, C) from her frame H0
    trk = seq.add_track(unreal.MovieSceneSubTrack)
    trk.set_display_name(args["track_name"])
    sec = trk.add_section()
    sec.set_sequence(dup)                                                 # decl MovieSceneSubSection.h:161-162
    sec.set_range(int(pp["range"][0]), int(pp["range"][1]))
    prm = sec.get_editor_property("parameters")                           # struct copy: set back [prec hookin]
    prm.set_editor_property("start_frame_offset", unreal.FrameNumber(int(pp["offset_ticks"])))
    sec.set_editor_property("parameters", prm)
    sec.set_completion_mode(getattr(unreal.MovieSceneCompletionMode, args.get("completion", "RESTORE_STATE")))
    off = int(sec.get_editor_property("parameters").get_editor_property("start_frame_offset").value)
    mapped = int(unreal.MovieSceneSectionExtensions.get_parent_sequence_frame(sec, int(pp["her_frame_start"]), seq))
    got = [int(sec.get_start_frame()), int(sec.get_end_frame())]
    scene_tpf = _tpf(seq)
    got_ticks = _section_ticks(sec, _rate(seq.get_tick_resolution()), scene_tpf, "PREROLL_SUBSECTION")
    want_ticks = [int(pp["range"][0]) * scene_tpf, int(pp["range"][1]) * scene_tpf]
    if off != int(pp["offset_ticks"]) or mapped != int(pp["range"][0]) or got != list(pp["range"]) or \
            got_ticks != want_ticks or \
            _path(sec.get_sequence()) != args["dup_path"]:
        _stop(run, "SECTION_READBACK|offset %d want %d|her %d -> %d want %d|range %s ticks %s want %s/%s|NOTHING SAVED; "
                   "Don't-Save restart" % (off, pp["offset_ticks"], pp["her_frame_start"], mapped, pp["range"][0], got,
                                           got_ticks, pp["range"], want_ticks))
    # the main slot must be untouched (her cut frame at C)
    slot = [s for t in seq.get_tracks() if isinstance(t, unreal.MovieSceneSubTrack) for s in t.get_sections()
            if s.get_sequence() is not None and _path(s.get_sequence()) == args["copy"]]
    if len(slot) != 1 or int(slot[0].get_start_frame()) != int(pp["cut"]):
        _stop(run, "MAIN_SLOT_NOT_AT_CUT|%s|NOTHING SAVED; Don't-Save restart" %
              [[int(s.get_start_frame()), int(s.get_end_frame())] for s in slot])
    c = _census()
    if sorted(c["content"]) != sorted([args["scene_sequence"], args["dup_path"]]) or c["maps"]:
        _stop(run, "CENSUS|%s|NOTHING SAVED; Don't-Save restart (backup %s; her maps are never saved here)"
              % (json.dumps(c), folder))
    for p in (args["scene_sequence"], args["dup_path"]):
        if not unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False):
            _stop(run, "SAVE_FAILED|%s" % p)
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_SAVE|%s" % json.dumps(_census()))
    seq2 = unreal.load_asset(args["scene_sequence"])
    t2 = _our_track(seq2, args["track_name"])
    s2 = [s for t in t2 for s in t.get_sections()]
    if len(t2) != 1 or len(s2) != 1 or [int(s2[0].get_start_frame()), int(s2[0].get_end_frame())] != list(pp["range"]):
        _stop(run, "POST_SAVE_READBACK|%d tracks %d sections" % (len(t2), len(s2)))
    rec.update(applied=True, classify=cls_, motion_coverage=dup_motion,
               section={"range": got, "range_ticks": got_ticks, "offset_ticks": off, "mapped_her_start": mapped,
                        "completion": args.get("completion", "RESTORE_STATE")})
    update_record(rpath, rec)
    unreal.log("KLARAPREROLL_APPLY_OK|run=%s|range=%s|her_start=%d|kept=%d|removed=%d|backup=%s|record=%s|next="
               "rebuild_managed_master + SavedMasterMatchesShow + SceneCutBindingsResolve + live check_scene_cut_bindings"
               " + PIE stills C-1/C/C+1" % (run, got, pp["her_frame_start"], len(cls_["keep"]), len(cls_["remove"]),
                                            folder, rpath))


def run_revert(args, run, world):
    rpath = os.path.join(_here(), "klara_preroll_record_S4.json")
    rec = load_json(rpath)
    seq = unreal.load_asset(args["scene_sequence"])
    ours = _our_track(seq, args["track_name"])
    secs = [s for t in ours for s in t.get_sections()]
    if len(ours) != 1 or len(secs) != 1 or _path(secs[0].get_sequence()) != args["dup_path"] or \
            [int(secs[0].get_start_frame()), int(secs[0].get_end_frame())] != list(rec["section"]["range"]):
        _stop(run, "STATE_DRIFTED|%d tracks %d sections|nothing changed (restore from %s)" % (len(ours), len(secs),
                                                                                           rec.get("backup")))
    folder = os.path.join(_project(), "Backups", "PreKlaraPrerollRevert-S4-%s" % run)
    os.makedirs(folder, exist_ok=False)
    for src in (_file(args["scene_sequence"], ".uasset"), _file(args["dup_path"], ".uasset")):
        if os.path.exists(src):
            shutil.copy2(src, folder)
    seq.remove_track(ours[0])                     # return value ignored: read back
    if _our_track(seq, args["track_name"]):
        _stop(run, "REMOVE_TRACK_READBACK|NOTHING SAVED; Don't-Save restart")
    if [str(t.get_display_name()) for t in seq.get_tracks()] != rec["before"]["scene_tracks"]:
        _stop(run, "SCENE_TRACKS_READBACK|%s vs %s|NOTHING SAVED; Don't-Save restart"
              % ([str(t.get_display_name()) for t in seq.get_tracks()], rec["before"]["scene_tracks"]))
    c = _census()
    if c["content"] != [args["scene_sequence"]] or c["maps"]:
        _stop(run, "CENSUS|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(c))
    if not unreal.EditorAssetLibrary.save_asset(args["scene_sequence"], only_if_is_dirty=False):
        _stop(run, "SAVE_FAILED|%s" % args["scene_sequence"])
    refs = [str(x) for x in unreal.EditorAssetLibrary.find_package_referencers_for_asset(args["dup_path"], False)]
    if refs:
        _stop(run, "DUP_STILL_REFERENCED|%s|LS_DevScene_04 saved without the track; duplicate kept" % refs)
    on_disk = bool(unreal.EditorAssetLibrary.does_asset_exist(args["dup_path"]))
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_REVERT|%s" % json.dumps(_census()))
    os.rename(rpath, rpath + ".reverted-" + run)
    unreal.log("KLARAPREROLL_REVERT_OK|run=%s|removed_track=%s|dup_left_on_disk=%s|exists=%d|backup=%s|next=klara_reveal "
               "REVERT may now run; permanent deletion requires Gary's explicit approval"
               % (run, args["track_name"], args["dup_path"], int(on_disk), folder))


def _pick_bones(names):
    low = [(n, n.lower()) for n in names]
    out = []
    for words in (("head",), ("pelvis", "hip", "spine"), ("root",)):
        hit = [n for n, low_name in low if any(w in low_name for w in words)]
        if hit and hit[0] not in out:
            out.append(hit[0])
    if names and names[len(names) // 2] not in out:
        out.append(names[len(names) // 2])
    return out[:3]


def _actor_candidates(world):
    acts = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))
    kept, rows = [], []
    for a in acts:
        comps = list(a.get_components_by_class(unreal.SkeletalMeshComponent))
        if not comps:
            continue
        lv = a.get_level()
        rows.append({"idx": len(kept), "label": str(a.get_actor_label()), "name": str(a.get_name()),
                     "path": str(a.get_path_name()), "level_pkg": _path(lv.get_outermost()) if lv is not None else None,
                     "components": [str(c.get_name()) for c in comps]})
        kept.append(a)
    return kept, rows


def run_probe(args, run):
    """PIE/read-only. Every sample is gated to the live Scene 4 transport segment.
    The callback holds plain Python data and resolves actors/components afresh per tick."""
    pa = dict({"scene_label": "Scene 4", "frames": [], "burst": 3, "timeout_s": 900.0,
               "master_tick_res": 24000.0, "scene_fps": 25.0, "not_in_scene_log_s": 5.0},
              **(args.get("probe") or {}))
    rec_path = os.path.join(_here(), args["reveal_record"])
    rec = load_json(rec_path) if os.path.exists(rec_path) else None
    plan = (rec or {}).get("plan") or {}
    pr = plan.get("preroll") or {}
    if not rec or not rec.get("applied") or plan.get("version") != 5 or not pr.get("range"):
        _stop(run, "PROBE_NEEDS_APPLIED_V5_PREROLL_PLAN|%s" % rec_path)
    p0, cut = [int(x) for x in pr["range"]]
    frames = sorted(float(x) for x in (pa.get("frames") or
                    [p0, p0 + max(1, (cut - p0) // 2), max(p0, cut - 2)]))
    subjects = {k: dict(v) for k, v in pa["subjects"].items()}
    st = {"handle": None, "samples": [], "filled": {w: 0 for w in frames}, "t0": time.time(), "done": False,
          "out": os.path.join(_here(), "klara_preroll_probe_S4_%s.json" % run), "candidates": None,
          "segment": None, "not_in_scene_ticks": 0, "last_nis_log": None}

    def finish(status):
        if st["done"]:
            return
        st["done"] = True
        try:
            unreal.unregister_slate_post_tick_callback(st["handle"])
        except Exception:  # noqa: BLE001
            pass
        verdict = classify_probe(st["samples"])
        with open(st["out"], "w", encoding="utf-8") as h:
            json.dump({"tool": TOOL, "run": run, "status": status, "samples": st["samples"], "verdict": verdict,
                       "frames": frames, "cut": cut, "segment": st["segment"], "candidates": st["candidates"],
                       "filled": {str(k): v for k, v in st["filled"].items()}}, h, indent=1, sort_keys=True, default=str)
        if status == "complete" and verdict["answer"] == "MOVING":
            unreal.log("KLARAPREROLL_PROBE_OK|run=%s|answer=%s|answers=%s|file=%s" %
                       (run, verdict["answer"], json.dumps(verdict["answers"], sort_keys=True), st["out"]))
        else:
            unreal.log_error("KLARAPREROLL_PROBE_FAILED|run=%s|status=%s|answer=%s|filled=%s|file=%s" %
                             (run, status, verdict["answer"], st["filled"], st["out"]))

    def scene_time(world):
        roots = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot))
        if len(roots) != 1:
            return None, "SHOW_ROOTS_%d" % len(roots)
        tr = roots[0].transport
        segs = [s for s in list(tr.segments) if s.type == unreal.InfinityCueType.SCENE and
                (str(s.label) == pa["scene_label"] or str(s.label).startswith(pa["scene_label"] + " "))]
        if len(segs) != 1:
            return None, "SCENE_SEGMENTS_%d" % len(segs)
        mf = float(tr.get_current_master_frame().value)
        a, b = int(segs[0].start_frame.value), int(segs[0].end_frame.value)
        sf = (mf - a) / float(pa["master_tick_res"]) * float(pa["scene_fps"])
        return {"mf": mf, "sf": sf, "start": a, "end": b}, None

    def sample(world, timing, window):
        acts, cands = _actor_candidates(world)
        if st["candidates"] is None:
            st["candidates"] = cands
            for c in cands:
                unreal.log("KLARAPREROLL_PROBE_CANDIDATE|run=%s|%s" % (run, json.dumps(c, sort_keys=True)))
        for subject, cfg in sorted(subjects.items()):
            match = match_actor(cands, cfg["actor_label"], cfg.get("actor_name"), args["her_level"])
            row = {"subject": subject, "window": window, "scene_frame": timing["sf"],
                   "master_frame": timing["mf"], "found": match["found"], "match": match, "pose": None}
            if match["found"]:
                actor = acts[match["idx"]]
                comps = list(actor.get_components_by_class(unreal.SkeletalMeshComponent))
                wanted = cfg.get("component")
                comps = [c for c in comps if wanted is None or str(c.get_name()) == wanted]
                if len(comps) == 1:
                    comp = comps[0]
                    names = [str(comp.get_bone_name(i)) for i in range(int(comp.get_num_bones()))]
                    pose = {}
                    for bone in _pick_bones(names):
                        tf = comp.get_socket_transform(bone, unreal.RelativeTransformSpace.RTS_COMPONENT)
                        q, v = tf.rotation, tf.translation
                        pose[bone] = [float(v.x), float(v.y), float(v.z), float(q.x), float(q.y), float(q.z), float(q.w)]
                    row["pose"], row["component"] = pose, str(comp.get_name())
                else:
                    row["component_error"] = "COUNT_%d want=%r candidates=%s" % (
                        len(comps), wanted, [str(c.get_name()) for c in actor.get_components_by_class(
                            unreal.SkeletalMeshComponent)])
            st["samples"].append(row)
            unreal.log("KLARAPREROLL_PROBE_SAMPLE|run=%s|%s" % (run, json.dumps(row, default=str)))

    def tick(_dt):
        try:
            world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
            if world is None:
                return finish("pie_ended")
            if time.time() - st["t0"] > float(pa["timeout_s"]):
                return finish("timeout")
            timing, err = scene_time(world)
            if timing is None:
                return finish("no_time_" + err)
            st["segment"] = [timing["start"], timing["end"]]
            window, why = probe_gate(timing["mf"], timing["start"], timing["end"], timing["sf"], frames, st["filled"],
                                     pa["burst"], cut)
            if window is None:
                if why == "NOT_IN_SCENE":
                    st["not_in_scene_ticks"] += 1
                    now = time.time()
                    if st["last_nis_log"] is None or now - st["last_nis_log"] >= float(pa["not_in_scene_log_s"]):
                        st["last_nis_log"] = now
                        unreal.log("KLARAPREROLL_PROBE_NOT_IN_SCENE|run=%s|master=%d|segment=%s|waiting" %
                                   (run, int(timing["mf"]), st["segment"]))
                return None
            sample(world, timing, window)
            st["filled"][window] += 1
            if all(v >= int(pa["burst"]) for v in st["filled"].values()):
                finish("complete")
        except Exception as exc:  # noqa: BLE001
            unreal.log_error("KLARAPREROLL_PROBE_ERROR|run=%s|%s: %s" % (run, type(exc).__name__, exc))
            finish("error")
        return None

    st["handle"] = unreal.register_slate_post_tick_callback(tick)
    unreal.log("KLARAPREROLL_PROBE_ARMED|run=%s|frames=%s|burst=%d|read_only=1|segment=%s|file=%s" %
               (run, frames, int(pa["burst"]), pa["scene_label"], st["out"]))


def main():
    args = globals().get("KLARAPREROLL_ARGS")
    if args is None:
        args = load_json(os.path.join(_here(), ARGS_NAME))
    run = str(args.get("run_id") or datetime.datetime.now().strftime("KLARAPREROLL-%Y%m%d-%H%M%S"))
    mode = str(args.get("mode") or "").upper()
    bad = validate_args(args)
    if bad:
        _stop(run, "ARGS|" + " || ".join(bad))
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    pie = ed.get_game_world() is not None
    if mode == "PROBE":
        if not pie:
            _stop(run, "PROBE_NEEDS_PIE")
        return run_probe(args, run)
    world = None if pie else ed.get_editor_world()
    wname = str(world.get_outermost().get_name()) if world is not None else None
    rpath = os.path.join(_here(), "klara_preroll_record_S4.json")
    cur = None if pie else unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
    state = {"mode": mode, "confirm": args.get("confirm"), "pie": pie,
             "wrong_world": None if wname == EXPECTED_WORLD else str(wname),
             "sequencer_open": _path(cur) if cur is not None else None, "census": _census(),
             "decided_by": args.get("decided_by"), "record_exists": rpath if os.path.exists(rpath) else None,
             "record_applied": os.path.exists(rpath) and bool(load_json(rpath).get("applied"))}
    cur = None
    early = live_gates(state)
    if early:
        _stop(run, "REFUSED|" + " || ".join(early))
    rv_path = os.path.join(_here(), args["reveal_record"])
    off = preroll_off_gate(mode, load_json(rv_path) if os.path.exists(rv_path) else None)
    if off is not None and off[0] == "SKIP":          # DRY: nothing to plan, nothing read beyond the record
        unreal.log_warning("KLARAPREROLL_SKIPPED|run=%s|mode=%s|reason=%s|mutated=0" % (run, mode, off[1]))
        return
    if off is not None:
        _stop(run, off[1] + "|nothing changed")
    try:
        {"DRY": run_dry, "APPLY": run_apply, "REVERT": run_revert}[mode](args, run, world)
    except PlanError as exc:
        _stop(run, "PLAN|" + str(exc))


if unreal is not None:
    main()
