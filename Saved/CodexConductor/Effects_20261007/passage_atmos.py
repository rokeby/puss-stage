"""PASSAGE ATMOS: DRY / APPLY / REVERT. Roll the P03 beam look (bench winner GSB = soft-slat gobo light function +
noise-volume beam boxes) out to another Passage, re-using the live-proven P03 tool UNCHANGED as its core.

Gary 7 Oct effects list, item 3: "beam texture / motes ... applied only to P03 so far - plan a rollout". The P03 run
(p03_atmos.py, APPLY 20261006-233515, commit 8bcf377) is the precedent; this wrapper is OFFLINE-WRITTEN, NEVER RUN IN
UNREAL (7 Oct). Its first live step is a DRY.

HOW (no copy of the core): the core file ../p03_atmos.py is loaded as a PRIVATE module object (never registered in
sys.modules, so a later P03 run still gets a pristine module; memory ue58-python-stale-module-cache) and re-pointed:
  PASSAGE / MARK / CONFIRM_TOKEN / ACTOR_TAG = "<Pnn>" / "<Pnn>ATMOS"; RECORD_PATH, report_path() and backup_prefix()
  -> this folder and Pre<Pnn>Atmos; MI_SMOKE -> a per-passage name (smoke is OFF by default here anyway);
  beam_rows() -> the core's rows FILTERED to the chosen bays (args beam_bays | beam_stride/beam_phase), capped by
  max_beams (perf guard: every chosen beam adds one Volume-domain noise box);
  _tagged_leftovers() -> only THIS passage's actors, or BeamLook/SmokeTest actors that carry no <Pnn>ATMOS tag at all
  (the core's own version counts P03's live boxes as leftovers and would refuse every other passage's APPLY:
  p03_atmos.py:1092-1094, :1514).
The core's SHA-256 is pinned (CORE_SHA256); any edit to p03_atmos.py refuses with CORE_DRIFT until this wrapper and
its harness are re-reviewed. Every P03 string literal in the core is classified by the harness (re-pointed here, or
text-only), so a new hard-coded P03 path in a later core cannot slip through.

ROLLOUT DEFAULTS (params; any core param may still be given): the P03-specific fog cut is OFF (vs_scale,
medium_scale, lfv_extinction_scale = 1.0 -> no targets, core plan_fog/plan_lfv skip scale 1.0), smoke OFF; beam look
+ noise boxes ON with the core's GSB defaults (gobo "slats", lf_conflict "carry_flicker"). reuse_existing_assets is
REQUIRED true: the BeamLook masters already exist from the P03 run, and the core refuses to overwrite.

Proof tiers (AGENTS.md), per claim:
* declaration-proven / precedent: core behaviour as documented in p03_atmos.py:1-76 (its own tiers); passage_config
  generalises to P01..P06 (p01_rig_pattern.py:140-157); core leftover gate p03_atmos.py:1092-1094 + :1514; core
  check_params forbids unknown keys (p03_atmos.py:230-233), hence wrapper keys are stripped before it.
* measured (offline, 7 Oct): beam counts per passage from lighting_scores_record_P0n.json after_rows: P01 28 (no LF),
  P02 12 (no LF), P04 5 (1 Fault flicker), P05 51 (no LF), P06 17 (15 Buzz flicker) - records predate Gary's hand
  edits (Docs/Conductor/LIGHTING_DRIFT_2026-10-06.md), the tool reads the LIVE Show.
* inferred (the first live DRY confirms): that the private-module load behaves like the runpy load the P03 runner
  uses (same file, same globals; the core's main guard needs P03ATMOS_ARGS, which is never set here); that existing
  BeamLook assets pass the core's existing_ok read-back with default params (they were built with them).

Args (passage_atmos_args.json via passage_atmos_run.py):
 {"mode": "DRY"|"APPLY"|"REVERT", "passage": "P01", "confirm": "<MODE> P01ATMOS",
  "beam_bays": [20] | null, "beam_stride": 4, "beam_phase": 0, "max_beams": 8,
  "params": {...core params...}, "ack_records": [...], "expected": {...}, "reuse_existing_assets": true}
Markers: the core's, prefixed <Pnn>ATMOS (e.g. P01ATMOS_DRY_OK|run=..); wrapper stops PASSAGEATMOS_STOPPED|<reason>.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.dirname(HERE)                                   # Saved/CodexConductor
CORE_PATH = os.path.join(CORE_DIR, "p03_atmos.py")
CORE_SHA256 = "127c2b40cdce293abc9188acb60c54817d91ccebb26fdb88a4f66eb19ace40f5"   # p03_atmos.py as of 8bcf377
ROLLOUT_PASSAGES = ("P01", "P02", "P04", "P05", "P06")             # P03 is owned by p03_atmos.py itself
WRAPPER_KEYS = ("passage", "beam_bays", "beam_stride", "beam_phase", "max_beams")
ROLLOUT_PARAMS = {"vs_scale": 1.0, "medium_scale": 1.0, "lfv_extinction_scale": 1.0, "smoke": False,
                  "beam_look": True, "noise_boxes": True}
MAX_BEAMS_DEFAULT = 8
ATMOS_TAG_RX = re.compile(r"^P0[1-6]ATMOS$")


class PassageAtmosError(RuntimeError):
    """Deliberate fail-closed stop."""


def require(condition, message):
    if not condition:
        raise PassageAtmosError(str(message))


# ------------------------------------------------------------------ pure
def check_wrapper_args(raw):
    raw = dict(raw or {})
    passage = raw.get("passage")
    require(passage in ROLLOUT_PASSAGES, "PASSAGE_INVALID|%r|valid=%s (P03 uses p03_atmos.py)"
            % (passage, ",".join(ROLLOUT_PASSAGES)))
    bays = raw.get("beam_bays")
    require(bays is None or (isinstance(bays, list) and bays and len(set(bays)) == len(bays)
                             and all(isinstance(b, int) and not isinstance(b, bool) and b > 0 for b in bays)),
            "BEAM_BAYS_INVALID|%r" % (bays,))
    stride, phase = raw.get("beam_stride", 1), raw.get("beam_phase", 0)
    for k, v, lo in (("beam_stride", stride, 1), ("beam_phase", phase, 0)):
        require(isinstance(v, int) and not isinstance(v, bool) and v >= lo, "%s_INVALID|%r" % (k.upper(), v))
    require(phase < stride, "BEAM_PHASE_GE_STRIDE|%d>=%d" % (phase, stride))
    require(bays is None or (stride == 1 and phase == 0), "BEAM_BAYS_AND_STRIDE|give one selection rule")
    cap = raw.get("max_beams", MAX_BEAMS_DEFAULT)
    require(isinstance(cap, int) and not isinstance(cap, bool) and 1 <= cap <= 64, "MAX_BEAMS_INVALID|%r" % (cap,))
    params = dict(ROLLOUT_PARAMS)
    params.update(raw.get("params") or {})
    core_args = {k: v for k, v in raw.items() if k not in WRAPPER_KEYS}
    core_args["params"] = params
    if str(raw.get("mode", "DRY")).upper() == "APPLY":
        require(raw.get("reuse_existing_assets") is True,
                "REUSE_REQUIRED|the BeamLook assets exist from the P03 run; set reuse_existing_assets true")
    return passage, {"bays": bays, "stride": stride, "phase": phase, "max": cap}, core_args


def select_beams(rows, sel):
    """rows: core beam_rows output (show order). Keep the chosen bays; refuse unknown bays and over-cap selections."""
    by_bay = {}
    for r in rows:
        by_bay.setdefault(int(r["bay"]), []).append(r)
    if sel["bays"] is not None:
        unknown = sorted(set(sel["bays"]) - set(by_bay))
        require(not unknown, "BEAM_BAY_NOT_FOUND|%s|beam bays=%s" % (unknown, sorted(by_bay)))
        keep = set(sel["bays"])
        out = [r for r in rows if int(r["bay"]) in keep]
    else:
        order = sorted(by_bay)
        keep = set(order[sel["phase"]::sel["stride"]])
        out = [r for r in rows if int(r["bay"]) in keep]
    require(out, "NO_BEAMS_SELECTED")
    require(len(out) <= sel["max"], "TOO_MANY_BEAMS|%d>%d|each adds a Volume noise box; raise max_beams knowingly"
            % (len(out), sel["max"]))
    return out


def leftovers_from(actors, actor_tag, beamlook_tag, smoke_tag):
    """actors: [(label, [tags])]. A leftover is THIS passage's tagged actor, or an orphan BeamLook/SmokeTest actor
    (no <Pnn>ATMOS tag). Another passage's live, recorded boxes are not leftovers."""
    out = []
    for label, tags in actors:
        tags = [str(t) for t in tags]
        mine = actor_tag in tags
        fx = beamlook_tag in tags or smoke_tag in tags
        owned = any(ATMOS_TAG_RX.match(t) for t in tags)
        if mine or (fx and not owned):
            out.append(label)
    return sorted(out)


def file_sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


# ------------------------------------------------------------------ core load + re-point
def load_core(passage, sel, core_path=CORE_PATH, expected_sha=CORE_SHA256):
    got = file_sha256(core_path)
    require(got == expected_sha, "CORE_DRIFT|%s|sha=%s|want=%s|re-review passage_atmos.py + harness"
            % (core_path, got, expected_sha))
    name = "_p03_atmos_core_for_%s_atmos" % passage.lower()
    spec = importlib.util.spec_from_file_location(name, core_path)
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)            # main guard needs P03ATMOS_ARGS in globals: never set -> nothing runs
    configure(core, passage, sel)
    return core


def configure(core, passage, sel):
    tag = "%sATMOS" % passage
    low = passage.lower()
    core.PASSAGE = passage
    core.MARK = tag
    core.CONFIRM_TOKEN = tag
    core.ACTOR_TAG = tag
    core.RECORD_PATH = os.path.join(HERE, "%s_atmos_record.json" % low)
    core.MI_SMOKE = core.ASSET_DIR + "/MI_Vol_SmokeTest_" + passage
    core.report_path = lambda mode, run, folder=None: os.path.join(
        folder or HERE, "%s_atmos_report_%s_%s.json" % (low, mode, run))
    core.backup_prefix = lambda revert=False: "Pre%sAtmos%s-" % (passage, "Revert" if revert else "")
    core_beam_rows = core.beam_rows
    core.beam_rows = lambda plain, p: select_beams(core_beam_rows(plain, p), sel)

    def _tagged_leftovers():
        actors = [(a.get_actor_label(), core._tag_strings(a)) for a in core._level_actors()]
        return leftovers_from(actors, core.ACTOR_TAG, core.BEAMLOOK_TAG, core.SMOKE_TAG)

    core._tagged_leftovers = _tagged_leftovers
    core.PASSAGE_ATMOS_SELECTION = dict(sel)
    return core


def run(raw):
    passage, sel, core_args = check_wrapper_args(raw)
    core = load_core(passage, sel)
    args = core.check_args(core_args)
    require(core.unreal is not None, "UNREAL_REQUIRED")
    return core._run(args)
