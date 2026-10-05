"""Offline harness for opening_own_rail.py (system Python, no Unreal). Every gate has a failing control.

Fixture data, cited (the live DRY re-reads all of it):
  Opening cue 5674D113..., P01 659D5386..., rail 2E86171B... 'Passage 1 Music' SW_P01_IntroWalking; Opening START on
  2E86, P01 SILENCE on 2E86; six rails P1-P6; Opening 0-96.36 s, P01 96.36-192.696 s; Master Opening music section =
  SW_P01_IntroWalking, no P01 section   [meas opening_readback_OPRB-20261005-143737.json]
  P01 original START 2E86 offset 0      [meas opening_sequence_record.json original.music.p01]
  Fades 1 s / 1 s, tick 24000/s         [decl dev-fixture defaults InfinityStageDevFixtureBuilder.cpp:330, 352-356;
                                          the live fades are UNKNOWN - the DRY reports them]
  WAV sha256 / duration: the real file, read here.
Run: python test_opening_own_rail.py -> OPENING_OWN_RAIL_HARNESS|tests=..|checks=..|failed=..
"""
import copy
import importlib.util
import json
import os
import sys
import tempfile
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("opening_own_rail", os.path.join(HERE, "opening_own_rail.py"))
orl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orl)
assert orl.unreal is None, "harness must run without Unreal"
WM = orl.WM
PROJECT = os.path.dirname(os.path.dirname(HERE))
with open(os.path.join(HERE, "opening_own_rail_args.json"), encoding="utf-8") as _h:
    ARGS = json.load(_h)
with open(os.path.join(HERE, "opening_sequence_record.json"), encoding="utf-8") as _h:
    OPENING_RECORD = json.load(_h)

CHECKS = {"n": 0, "failed": []}
TESTS = []
TICK = 24000.0
SHARED = "2E86171B614D036D59FEDCB9C6C5788A"
OPEN_GUID = "5674D1134EC0FFE62815588E1E88F9FF"
P01_GUID = "659D5386D64DA7742A351B9499ECCE4C"
OPEN_LABEL = "Opening — Curtain"
NEW_SOUND = orl.ASSET_PATH
OLD_P01_SOUND = "/Game/InfinityStage/Audio/Passages/SW_P01_IntroWalking"
RAIL_GUIDS = [SHARED, "74C172D76E4F4E5FAB02E1B20F5A3911", "39146A0581471F2D744691A7AB6F2150",
              "1F78FB563A43A46BE0768D9B4D22C603", "2F86E6BD6344E909346E77AC7FCBF838", "C441C6E2434BFA7017A66290203C7957"]


def check(cond, what):
    CHECKS["n"] += 1
    if not cond:
        CHECKS["failed"].append(what)


def test(fn):
    TESTS.append(fn)
    return fn


def has(items, prefix):
    return any(str(i).startswith(prefix) for i in items)


def args(**kw):
    a = copy.deepcopy(ARGS)
    a.update(kw)
    return a


def mint():
    return uuid.uuid4().hex.upper()


# ------------------------------------------------------------------------------------------------ fake Show
def rail(guid, n):
    return {"guid": guid, "label": "Passage %d Music" % n, "sound": "/Game/InfinityStage/Audio/Passages/SW_P0%d" % n
            if n != 1 else OLD_P01_SOUND, "source_in": 0, "source_out": 0, "fade_in": 24000, "fade_out": 24000,
            "analysis_map": "/Game/InfinityStage/MusicAnalysis/MM_P0%d_Analysis" % n, "fingerprint": "md5-%d" % n}


class FakeShow(object):
    """Same interface as opening_own_rail._LiveShow. Knobs simulate faults for the failing controls."""

    def __init__(self, mint_extra_cue=False, no_mint=False, insert_front=False, drop_binding=None, remove_wrong=False):
        self.rails = [rail(g, i + 1) for i, g in enumerate(RAIL_GUIDS)]
        self.cues = [{"label": OPEN_LABEL, "guid": OPEN_GUID, "occ": "0" * 32, "type": "SEQUENCE",
                      "music": orl.binding("<InfinityMusicBindingMode.START: 0>", SHARED)},
                     {"label": "Scene 1 — External Sound", "guid": "AA" * 16, "occ": "0" * 32, "type": "SCENE",
                      "music": orl.binding("SILENCE", orl.ZERO_GUID)},
                     {"label": "Pair 1", "guid": "BB" * 16, "occ": "CC" * 16, "type": "WING_PAIR",
                      "music": orl.binding("SILENCE", orl.ZERO_GUID)},
                     {"label": "Pair X (unminted occurrence of a non-wing cue)", "guid": "DD" * 16, "occ": "0" * 32,
                      "type": "SCENE", "music": orl.binding("SILENCE", orl.ZERO_GUID)}]
        self.passages = [{"label": "Passage %d" % (i + 1), "guid": (P01_GUID if i == 0 else ("%02d" % i) * 16),
                          "music": orl.binding("SILENCE" if i == 0 else "START", RAIL_GUIDS[i])} for i in range(6)]
        self.show_guid = "EE" * 16
        self.knobs = dict(mint_extra_cue=mint_extra_cue, no_mint=no_mint, insert_front=insert_front,
                          drop_binding=drop_binding, remove_wrong=remove_wrong)

    def read(self):
        bindings = [{"owner": p["label"], "mode": p["music"]["mode"], "rail": p["music"]["rail"],
                     "secondary": p["music"]["secondary"]} for p in self.passages]
        bindings += [{"owner": "cue:" + c["label"], "mode": c["music"]["mode"], "rail": c["music"]["rail"],
                      "secondary": c["music"]["secondary"]} for c in self.cues if c["type"] != "WING_PAIR"]
        return copy.deepcopy({
            "rails": self.rails, "opening": self.cues[0]["music"], "p01": self.passages[0]["music"],
            "opening_cue_guid": self.cues[0]["guid"], "p01_guid": self.passages[0]["guid"], "bindings": bindings,
            "ids": {"show": self.show_guid, "cues": [c["guid"] for c in self.cues],
                    "occurrences": [c["occ"] for c in self.cues], "passages": [p["guid"] for p in self.passages],
                    "rails": [r["guid"] for r in self.rails]}})

    def append_rail(self, desc):
        r = dict(copy.deepcopy(desc), guid=orl.ZERO_GUID)
        if self.knobs["insert_front"]:
            self.rails.insert(0, r)
        else:
            self.rails.append(r)

    def ensure_stable_ids(self):                       # InfinityStageShowAsset.cpp:91-124
        if self.knobs["no_mint"]:
            return
        for r in self.rails:
            if r["guid"] == orl.ZERO_GUID:
                r["guid"] = mint()
        for c in self.cues:
            if c["type"] == "WING_PAIR" and c["occ"] == orl.ZERO_GUID:
                c["occ"] = mint()
        if self.knobs["mint_extra_cue"]:
            self.cues[3]["guid"] = mint()

    def remove_rail(self, index, guid):
        if self.knobs["remove_wrong"]:
            index = index - 1
        if self.rails[index]["guid"] != guid and not self.knobs["remove_wrong"]:
            raise RuntimeError("REMOVE_RAIL_MISMATCH")
        del self.rails[index]

    def write_binding(self, which, state):
        if self.knobs["drop_binding"] == which:
            return
        target = self.cues[0] if which == "opening" else self.passages[0]
        target["music"] = copy.deepcopy(state)


def wav_dur():
    return orl.check_input(ARGS, PROJECT)[0]["duration_s"]


def make_plan(show, a=None, p01_orig=None):
    a = a or args()
    live = show.read()
    return orl.plan_own_rail(live, a, wav_dur(), TICK,
                             orl.original_p01(OPENING_RECORD) if p01_orig is None else p01_orig)


# ------------------------------------------------------------------------------------------------ args + input
@test
def args_and_input():
    check(orl.validate_args(args()) == [], "shipped args (DRY) validate: %r" % orl.validate_args(args()))
    check(has(orl.validate_args(args(mode="APPLY")), "NOT_DECIDED"), "APPLY with empty decided_by refused")
    check(orl.validate_args(args(mode="APPLY", decided_by="Gary")) == [], "APPLY with decided_by validates")
    check(has(orl.validate_args(args(mode="GO")), "MODE_INVALID"), "bad mode refused")
    check(has(orl.validate_args(args(asset_path="/Game/InfinityStage/Audio/Passages/SW_P01_IntroWalking")),
              "ASSET_PATH_INVALID"), "asset path pinned (never overwrites an existing wave)")
    check(has(orl.validate_args(args(shared_rail_guid="2e86")), "GUID_INVALID_SHARED"), "short guid refused")
    check(has(orl.validate_args(args(opening_cue_guid=orl.ZERO_GUID)), "GUID_INVALID_OPENING"), "zero guid refused")
    check(has(orl.validate_args(args(opening_offset_frames=-1)), "OPENING_OFFSET_INVALID"), "negative offset refused")
    f, r = orl.check_input(args(), PROJECT)
    check(r == [] and f["channels"] == 2 and f["rate"] == 44100 and f["sample_width"] == 3,
          "real WAV matches args (24-bit 44.1k stereo): %r %r" % (r, f and {k: f[k] for k in ("rate", "channels")}))
    check(abs(f["duration_s"] - 95.504) < 0.001, "sketch 2 is 95.504 s: %r" % f["duration_s"])
    check(has(orl.check_input(args(sha256="0" * 64), PROJECT)[1], "WAV_SHA_MISMATCH"), "sha control")
    check(has(orl.check_input(args(duration_s=96.36), PROJECT)[1], "WAV_DURATION_MISMATCH"), "duration control")
    check(has(orl.check_input(args(wav="DerivedAssets/nope.wav"), PROJECT)[1], "WAV_MISSING"), "missing control")


@test
def wav_parser_vs_stdlib():
    """The own RIFF parser (UE's Python 3.11 wave rejects EXTENSIBLE) must agree with system-Python wave."""
    import struct
    import wave
    path = os.path.join(PROJECT, *ARGS["wav"].split("/"))
    mine = orl.wav_header_facts(path)
    if sys.version_info >= (3, 12):
        ref = WM["wav_facts"](path)
        check(all(mine[k] == ref[k] for k in ("sha256", "channels", "rate", "sample_width", "frames")),
              "parser == stdlib wave on the real 24-bit EXTENSIBLE file: %r vs %r" % (mine, ref))
    with open(path, "rb") as h:
        head = h.read(64)
    i = head.find(b"fmt ")
    check(struct.unpack("<H", head[i + 8:i + 10])[0] == 0xFFFE, "input is WAVE_FORMAT_EXTENSIBLE (why the parser)")
    d = tempfile.mkdtemp()
    p16 = os.path.join(d, "pcm16.wav")
    w = wave.open(p16, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000)
    w.writeframes(b"\x00\x00" * 4800); w.close()
    f16 = orl.wav_header_facts(p16)
    check(f16["frames"] == 4800 and f16["sample_width"] == 2 and abs(f16["duration_s"] - 0.1) < 1e-9,
          "plain PCM16 parsed: %r" % f16)
    with open(path, "rb") as h:
        raw = bytearray(h.read(4096))
    j = raw.find(b"fmt ")
    raw[j + 8 + 24:j + 8 + 26] = struct.pack("<H", 3)                    # IEEE float subformat
    pf = os.path.join(d, "float.wav")
    with open(pf, "wb") as h:
        h.write(bytes(raw))
    try:
        orl.wav_header_facts(pf)
        check(False, "non-PCM subformat must be refused")
    except orl.PlanError as exc:
        check("WAV_NOT_PCM" in str(exc), "non-PCM refused: %s" % exc)
    with open(os.path.join(d, "junk.wav"), "wb") as h:
        h.write(b"not a wav at all")
    check(has(orl.check_input(args(wav="junk.wav"), d)[1], "WAV_UNREADABLE"), "junk refused")


@test
def p01_original_from_record():
    o = orl.original_p01(OPENING_RECORD)
    check(o == {"mode": "START", "rail": SHARED, "offset": 0}, "4 Oct original P01 = START 2E86 0: %r" % o)
    check(orl.original_p01({"original": {}}) is None, "missing original -> None")


# ------------------------------------------------------------------------------------------------ plan
@test
def plan_happy():
    plan, r = make_plan(FakeShow())
    check(r == [], "fixture plans: %r" % r)
    check(plan["index"] == 6, "appended AFTER the six Passage rails: %r" % plan["index"])
    nr = plan["new_rail"]
    check(nr["source_out"] == 2292088, "SourceOut = 95.503673 s x 24000 = 2292088: %r" % nr["source_out"])
    check(nr["source_in"] == 0 and nr["analysis_map"] is None and nr["sound"] == NEW_SOUND and
          nr["label"] == "Opening (Cameron sketch 2)", "rail fields: %r" % nr)
    check(nr["fade_in"] == 24000 and nr["fade_out"] == 24000, "fades copied from rail 2E86")
    check(plan["opening_after"]["mode"] == "START" and plan["opening_after"]["rail"] == "<NEW>" and
          plan["opening_after"]["offset"] == 0, "Opening re-pointed to the new rail: %r" % plan["opening_after"])
    check(plan["p01_after"] == orl.binding("START", SHARED, 0), "P01 back to START on 2E86: %r" % plan["p01_after"])
    s = FakeShow()
    s.rails[0]["fade_in"], s.rails[0]["fade_out"] = 0, 12000
    p2, _ = make_plan(s)
    check(p2["new_rail"]["fade_in"] == 0 and p2["new_rail"]["fade_out"] == 12000, "fades follow the live rail")


@test
def plan_refusals():
    def refused(show, prefix, a=None, p01_orig=None):
        plan, r = make_plan(show, a, p01_orig)
        check(plan is None and has(r, prefix), "%s refused: %r" % (prefix, r))
    s = FakeShow(); s.cues[0]["music"]["mode"] = "SILENCE"; refused(s, "OPENING_NOT_START")
    s = FakeShow(); s.cues[0]["music"]["rail"] = RAIL_GUIDS[1]; refused(s, "OPENING_RAIL_UNEXPECTED")
    s = FakeShow(); s.passages[0]["music"]["mode"] = "START"; refused(s, "P01_NOT_SILENT_ON_SHARED_RAIL")
    s = FakeShow(); s.passages[0]["music"]["rail"] = RAIL_GUIDS[1]; refused(s, "P01_NOT_SILENT_ON_SHARED_RAIL")
    s = FakeShow(); s.rails[0]["guid"] = mint(); refused(s, "SHARED_RAIL_MISSING")
    s = FakeShow(); s.cues[1]["music"] = orl.binding("START", SHARED); refused(s, "SHARED_RAIL_OTHER_USERS")
    s = FakeShow(); s.rails.append(dict(rail(mint(), 7), label="Opening (Cameron sketch 2)"))
    refused(s, "RAIL_LABEL_EXISTS")
    s = FakeShow(); del s.rails[5]; s.passages[5]["music"]["mode"] = "SILENCE"; refused(s, "RAILS_BELOW_PASSAGE_SLOTS")
    s = FakeShow(); s.rails[3]["guid"] = orl.ZERO_GUID; refused(s, "EXISTING_RAIL_GUIDS_INVALID")
    s = FakeShow(); s.rails[3]["guid"] = s.rails[2]["guid"]; refused(s, "EXISTING_RAIL_GUIDS_INVALID")
    s = FakeShow(); s.cues[2]["guid"] = orl.ZERO_GUID; refused(s, "EXISTING_CUES_GUID_ZERO")
    s = FakeShow(); s.cues[0]["guid"] = mint(); refused(s, "OPENING_CUE_GUID_MISMATCH")
    s = FakeShow(); s.passages[0]["guid"] = mint(); refused(s, "P01_GUID_MISMATCH")
    refused(FakeShow(), "P01_ORIGINAL_NOT_START_ON_SHARED", p01_orig={"mode": "SILENCE", "rail": SHARED, "offset": 0})
    plan, r = orl.plan_own_rail(FakeShow().read(), args(), wav_dur(), TICK, None)
    check(plan is None and has(r, "P01_ORIGINAL_UNKNOWN"), "unknown original refused")


# ------------------------------------------------------------------------------------------------ apply core
@test
def apply_appends_mints_repoints():
    s = FakeShow()
    before = s.read()
    plan, _ = make_plan(s)
    new, after, f = orl.apply_core(s, plan)
    check(f == [], "apply_core clean: %r" % f)
    check(new and new != orl.ZERO_GUID and new not in RAIL_GUIDS and len(new) == 32, "new GUID minted: %r" % new)
    check(after["rails"][:6] == before["rails"], "the six Passage rails untouched (incl. 2E86)")
    check(after["rails"][6]["guid"] == new and after["rails"][6]["sound"] == NEW_SOUND, "new rail at index 6")
    check(after["opening"]["rail"] == new and after["opening"]["mode"] == "START", "Opening plays the new rail")
    check(after["p01"] == orl.binding("START", SHARED, 0), "P01 restored: %r" % after["p01"])
    check(after["ids"]["cues"] == before["ids"]["cues"] and after["ids"]["passages"] == before["ids"]["passages"],
          "no other identity changed")
    # walking_music_swap's own plan now accepts P01 (and refused it before): the point of this tool.
    wpass = {"1": {"label": "Passage 1", "guid": P01_GUID, "mode": after["p01"]["mode"], "rail": SHARED}}
    rails = {r["guid"]: r for r in after["rails"]}
    wplan, wr = WM["rail_plan"](wpass, after["bindings"], rails, ["1"], "refuse")
    check(wr == [] and wplan["1"]["rail"] == SHARED and not wplan["1"]["set_start"],
          "walking_music_swap P01 plans after APPLY with silence_policy 'refuse': %r" % wr)
    b = FakeShow().read()
    bpass = {"1": {"label": "Passage 1", "guid": P01_GUID, "mode": b["p01"]["mode"], "rail": SHARED}}
    _p, br = WM["rail_plan"](bpass, b["bindings"], {r["guid"]: r for r in b["rails"]}, ["1"], "set_start")
    check(has(br, "P1_RAIL_SHARED"), "control: before APPLY walking_music_swap refuses P01 RAIL_SHARED: %r" % br)


@test
def apply_controls():
    s = FakeShow(mint_extra_cue=True); plan, _ = make_plan(s)
    check(has(orl.apply_core(s, plan)[2], "IDS_CHANGED: cues"), "extra mint caught")
    s = FakeShow(no_mint=True); plan, _ = make_plan(s)
    f = orl.apply_core(s, plan)[2]
    check(has(f, "NEW_RAIL_NOT_MINTED"), "missing mint caught: %r" % f)
    check(s.cues[0]["music"]["rail"] == SHARED, "nothing re-pointed after a failed mint")
    s = FakeShow(insert_front=True); plan, _ = make_plan(s)
    f = orl.apply_core(s, plan)[2]
    check(has(f, "RAIL_GUIDS_CHANGED") and has(f, "RAIL_0_CHANGED"), "insert-at-front (Passage index) caught: %r" % f)
    s = FakeShow(drop_binding="opening"); plan, _ = make_plan(s)
    check(has(orl.apply_core(s, plan)[2], "OPENING_BINDING"), "dropped Opening write caught")
    s = FakeShow(drop_binding="p01"); plan, _ = make_plan(s)
    check(has(orl.apply_core(s, plan)[2], "P01_BINDING"), "dropped P01 write caught")
    nr = make_plan(FakeShow())[0]["new_rail"]
    before = FakeShow().read()["rails"]
    after = before + [dict(nr, guid=mint(), source_out=0)]
    check(has(orl.rails_gate(before, after, nr), "NEW_RAIL_SOURCE_OUT"), "wrong SourceOut caught")
    after = before + [dict(nr, guid=mint(), fade_in=0)]
    check(has(orl.rails_gate(before, after, nr), "NEW_RAIL_FADE_IN"), "uncopied fade caught")
    after = before + [dict(nr, guid=mint(), analysis_map="/Game/X")]
    check(has(orl.rails_gate(before, after, nr), "NEW_RAIL_ANALYSIS_MAP"), "AnalysisMap must be None")
    old_new = before[0]["guid"]
    _n, f = orl.ids_gate({"rails": [r["guid"] for r in before]}, {"rails": [r["guid"] for r in before] + [old_new]})
    check(has(f, "NEW_RAIL_GUID_REUSED"), "reused GUID caught")


# ------------------------------------------------------------------------------------------------ length + Master
SEGS = [{"label": OPEN_LABEL, "start": 0, "end": 2312640}, {"label": "Passage 1", "start": 2312640, "end": 4624705},
        {"label": "Scene 1 — External Sound", "start": 4624705, "end": 9683905}]


@test
def unchanged_length_gate():
    check(WM["length_gate"](SEGS, copy.deepcopy(SEGS)) == [], "identical segments pass")
    a = copy.deepcopy(SEGS); a[0]["end"] += 1; a[1]["start"] += 1; a[1]["end"] += 1; a[2]["start"] += 1
    a[2]["end"] += 1
    f = WM["length_gate"](SEGS, a)
    check(has(f, "LENGTH_MOVED") and has(f, "START_MOVED"), "one-tick retime caught: %r" % f)
    a = copy.deepcopy(SEGS)[:2]
    check(has(WM["length_gate"](SEGS, a), "SEGMENT_SET_CHANGED"), "lost segment caught")


def music_rows(opening_sound, p01_sound):
    m = {OPEN_GUID: {"sound": opening_sound, "range_s": [0.0, 96.36]},
         "02" * 16: {"sound": "/Game/InfinityStage/Audio/Passages/SW_P02", "range_s": [490.816, 670.816]}}
    if p01_sound:
        m[P01_GUID] = {"sound": p01_sound, "range_s": [96.36, 192.696]}
    return m


SEG_S = {OPEN_LABEL: [0.0, 96.36], "Passage 1": [96.36, 192.696]}


@test
def master_music():
    before, after = music_rows(OLD_P01_SOUND, None), music_rows(NEW_SOUND, OLD_P01_SOUND)
    g = lambda b, a, wo=NEW_SOUND, wp=OLD_P01_SOUND: orl.master_music_gate(b, a, OPEN_GUID, P01_GUID, wo, wp, SEG_S,
                                                                            OPEN_LABEL, "Passage 1")
    check(g(before, after) == [], "APPLY music passes: %r" % g(before, after))
    check(has(g(before, music_rows(OLD_P01_SOUND, OLD_P01_SOUND)), "MASTER_OPENING_MUSIC"), "Opening still old")
    check(has(g(before, music_rows(NEW_SOUND, None)), "MASTER_P01_MUSIC"), "P01 section missing caught")
    a = music_rows(NEW_SOUND, OLD_P01_SOUND); a[OPEN_GUID]["range_s"] = [0.0, 95.52]
    check(has(g(before, a), "MASTER_OPENING_RANGE"), "Opening range off caught")
    a = music_rows(NEW_SOUND, OLD_P01_SOUND); a["02" * 16]["sound"] = "/Game/Other"
    check(has(g(before, a), "MASTER_MUSIC_OTHER_CHANGED"), "other Passage music change caught")
    a = music_rows(NEW_SOUND, OLD_P01_SOUND); del a["02" * 16]
    check(has(g(before, a), "MASTER_MUSIC_SET_CHANGED"), "lost section caught")
    # REVERT direction: Opening back to the 2E86 sound, P01 silent.
    check(g(after, before, OLD_P01_SOUND, None) == [], "REVERT music passes")
    check(has(g(after, music_rows(OLD_P01_SOUND, OLD_P01_SOUND), OLD_P01_SOUND, None), "MASTER_P01_MUSIC_PRESENT"),
          "REVERT: P01 still playing caught")


@test
def sync_gate_reused():
    rows = {OPEN_LABEL: [0.0, 96.36], "Passage 1": [96.36, 192.696]}
    check(WM["sync_gate"](rows, copy.deepcopy(rows)) == [], "in-sync Master passes")
    stale = {OPEN_LABEL: [0.0, 15.0], "Passage 1": [15.0, 111.336]}
    check(has(WM["sync_gate"](rows, stale), "MASTER_STALE"), "stale Master refused")


# ------------------------------------------------------------------------------------------------ revert
def applied_record(show):
    before = show.read()
    plan, _ = make_plan(show)
    new, after, f = orl.apply_core(show, plan)
    assert not f, f
    return {"args": args(), "plan": plan, "new_rail_guid": new,
            "before": {k: before[k] for k in ("rails", "opening", "p01", "ids")},
            "after": {k: after[k] for k in ("rails", "opening", "p01", "ids")}}, before


@test
def revert_exact():
    s = FakeShow()
    rec, before = applied_record(s)
    rec = json.loads(json.dumps(rec))                     # the record goes through JSON on disk
    f = orl.revert_core(s, rec)
    now = s.read()
    check(f == [], "revert clean: %r" % f)
    check(now == before, "REVERT restores rails, bindings, bindings list and every GUID exactly")


@test
def revert_controls():
    s = FakeShow(); rec, _ = applied_record(s)
    s.rails[0]["sound"] = "/Game/InfinityStage/Audio/PassageMusic/Cameron_20261005/SW_P01_Walking1_Cameron"
    f = orl.revert_core(s, rec)
    check(has(f, "STATE_DRIFTED: RAILS_CHANGED_SINCE_APPLY"), "walking swap on 2E86 blocks REVERT: %r" % f)
    check(s.cues[0]["music"]["rail"] == rec["new_rail_guid"], "nothing written on drift")
    s = FakeShow(); rec, _ = applied_record(s)
    s.cues[1]["music"] = orl.binding("START", rec["new_rail_guid"])
    check(has(orl.revert_core(s, rec), "STATE_DRIFTED: NEW_RAIL_REFERENCED_BY"), "other user of new rail blocks")
    s = FakeShow(); rec, _ = applied_record(s)
    s.cues[0]["music"]["offset"] = 240
    check(has(orl.revert_core(s, rec), "STATE_DRIFTED: OPENING_BINDING_CHANGED"), "hand-edited Opening blocks")
    s = FakeShow(); rec, _ = applied_record(s)
    s.knobs["remove_wrong"] = True
    check(has(orl.revert_core(s, rec), "REVERT_RAILS_NOT_EXACT"), "wrong rail removed caught")
    s = FakeShow(); rec, _ = applied_record(s)
    s.knobs["drop_binding"] = "p01"
    check(has(orl.revert_core(s, rec), "REVERT_P01_BINDING"), "P01 not restored caught")


# ------------------------------------------------------------------------------------------------ live gates, record
@test
def live_gate_controls():
    ok = {"mode": "APPLY", "confirm": "APPLY OPENINGRAIL", "census": {"content": [], "maps": []}, "world_ok": True}
    check(orl.live_gates(ok) == [], "clean APPLY state passes")
    for knob, prefix in ((dict(confirm="APPLY WALKING MUSIC"), "CONFIRM_MISMATCH"), (dict(pie=True), "PIE_OR_SIE"),
                         (dict(sequencer_open=True), "SEQUENCER_IS_OPEN"),
                         (dict(census={"content": ["/Game/X"], "maps": []}), "DIRTY_CENSUS"),
                         (dict(world_ok=False), "WRONG_WORLD"), (dict(record_exists=True), "RECORD_EXISTS"),
                         (dict(asset_exists=True), "ASSET_EXISTS")):
        check(has(orl.live_gates(dict(ok, **knob)), prefix), "%s refused" % prefix)
    rv = {"mode": "REVERT", "confirm": "REVERT OPENINGRAIL", "census": {}, "world_ok": True}
    check(has(orl.live_gates(rv), "NO_APPLIED_RECORD"), "REVERT without record refused")
    check(orl.live_gates(dict(rv, record_applied=True)) == [], "REVERT with record passes")
    check(has(WM["census_gate"]({"content": ["/Game/InfinityStage/Dev/Maps/X"], "maps": []},
                                [orl.SHOW_PATH, orl.MASTER_PATH, orl.ASSET_PATH]), "UNEXPECTED_DIRTY"),
          "census gate refuses a foreign dirty package")
    check(WM["census_gate"]({"content": [orl.SHOW_PATH, orl.ASSET_PATH], "maps": []},
                            [orl.SHOW_PATH, orl.MASTER_PATH, orl.ASSET_PATH]) == [], "expected dirty set passes")


@test
def record_exclusive():
    d = tempfile.mkdtemp()
    p = os.path.join(d, orl.RECORD_NAME)
    WM["write_record_exclusive"](p, {"a": 1})
    try:
        WM["write_record_exclusive"](p, {"a": 2})
        check(False, "second exclusive record must raise")
    except FileExistsError:
        check(True, "")
    with open(p, encoding="utf-8") as h:
        check(json.load(h) == {"a": 1}, "first record kept")


@test
def helper_tail_guard():
    check(len(WM["_sha256"]) == 64 and callable(WM["length_gate"]), "walking helpers loaded without main()")
    check(orl.MARK == "OPENING_OWN_RAIL" and orl.CONFIRM_WORD == "OPENINGRAIL", "marker/confirm words")


def main():
    for fn in TESTS:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            CHECKS["failed"].append("%s RAISED %r" % (fn.__name__, exc))
    for f in CHECKS["failed"]:
        print("FAIL:", f)
    print("OPENING_OWN_RAIL_HARNESS|tests=%d|checks=%d|failed=%d" % (len(TESTS), CHECKS["n"], len(CHECKS["failed"])))
    return 1 if CHECKS["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
