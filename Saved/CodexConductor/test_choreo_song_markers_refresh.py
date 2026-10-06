"""Offline harness for choreo_song_markers_refresh.py (system Python, no Unreal). Every gate has a failing control.

Fixture data, cited (the live DRY re-reads all of it):
  Passage lengths P1 96.336, P2-P4 180.0, P5 186.364 s and old marker counts P1 35, P2 24, P3 16, P4 15, P5 90:
      Saved/CodexCueing/choreo_report_choreo-apply-3.json length_s / marker_count [meas 4 Oct]
  offset 0 (source_in 0, rail_offset 0): walking_music_swap_dry.json rows/*/passage/offset and walking records
      rail_after.source_in [meas 5 Oct]
  Tick 24000/s: rail fade 24000 frames = 1 s in walking_music_swap_record_*.json [meas]
choreo_tool.py is the REAL file (loaded the tool's way), driven with fake unreal objects.
Run: python test_choreo_song_markers_refresh.py -> CHOREO_SONG_MARKERS_HARNESS|tests=..|checks=..|failed=..
"""
import copy
import importlib.util
import json
import os
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(os.path.dirname(HERE))
spec = importlib.util.spec_from_file_location("choreo_song_markers_refresh", os.path.join(HERE, "choreo_song_markers_refresh.py"))
sm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sm)
assert sm.unreal is None, "harness must run without Unreal"
CHOREO_TOOL = os.path.join(PROJECT, "Saved", "CodexCueing", "choreo_tool.py")
NS = sm.load_choreo_tool(CHOREO_TOOL)
with open(os.path.join(HERE, sm.ARGS_NAME), encoding="utf-8") as _h:
    ARGS = json.load(_h)
BODIES = list(ARGS["change_bodies"])
TICK = 24000.0
LENGTH = {"1": 96.33604431152344, "2": 180.0, "3": 180.0, "4": 180.0, "5": 186.3636474609375}
OLD_COUNT = {"1": 35, "2": 24, "3": 16, "4": 15, "5": 90}

CHECKS = {"n": 0, "failed": []}
TESTS = []


def check(cond, what):
    CHECKS["n"] += 1
    if not cond:
        CHECKS["failed"].append(what)


def test(fn):
    TESTS.append(fn)
    return fn


def raises(fn, prefix):
    try:
        fn()
    except sm.PlanError as exc:
        return str(exc).startswith(prefix)
    return False


def load_json(rel):
    with open(os.path.join(PROJECT, rel), encoding="utf-8") as handle:
        return json.load(handle)


# --------------------------------------------------------------------------------------------- fake unreal objects
class O(object):
    def __init__(self, **p):
        self.p = p

    def get_editor_property(self, name):
        return self.p[name]


class Guid(object):
    def __init__(self, s):
        self.s = s


class State(object):
    def __init__(self, s):
        self.s = s

    def __str__(self):
        return self.s


class Frame(object):
    def __init__(self, value):
        self.value = value


class Rate(object):
    def __init__(self, n, d=1):
        self.numerator, self.denominator = n, d


class Section(object):
    def __init__(self, guid, start, end):
        self.guid, self.start, self.end = guid, start, end

    def get_editor_property(self, name):
        assert name == "block_guid"
        return self.guid

    def get_start_frame_seconds(self):
        return self.start

    def get_end_frame_seconds(self):
        return self.end


class Track(object):
    def __init__(self, sections):
        self.sections = sections

    def get_sections(self):
        return self.sections


class Master(object):
    def __init__(self, sections):
        self.track = Track(sections)

    def find_tracks_by_exact_type(self, kind):
        return [self.track]

    def get_tick_resolution(self):
        return Rate(24000)

    def get_display_rate(self):
        return Rate(30)


class FakeUnreal(object):
    class GuidLibrary(object):
        @staticmethod
        def conv_guid_to_string(g):
            return g.s

    class InfinityMusicProposalState(object):
        REJECTED = State("InfinityMusicProposalState.REJECTED")
        SUGGESTED = State("InfinityMusicProposalState.SUGGESTED")

    MovieSceneInfinityPassageTrack = object()


UE = FakeUnreal()
SUG, REJ = UE.InfinityMusicProposalState.SUGGESTED, UE.InfinityMusicProposalState.REJECTED


def ue_map(analysis, rejected_times=()):
    """UE-shaped map as the IMPORTER builds it (independent of sm.json_map_proxy): time, label|default, state."""
    def rows(field, default):
        return [O(time_seconds=p["timeSeconds"], label=p.get("label", default),
                  state=REJ if p["timeSeconds"] in rejected_times else SUG) for p in analysis.get(field, [])]
    return O(beat_proposals=rows("beatProposals", "Beat suggestion"),
             major_change_proposals=rows("majorChangeProposals", "Major change suggestion"))


def world(amap, length, source_in=0, rail_offset=0, label="Passage 2", start=429.016):
    rail = O(rail_guid=Guid("RAIL"), analysis_map=amap, source_in_frame=Frame(source_in))
    music = O(primary_rail_guid=Guid("RAIL"), rail_offset_frames=Frame(rail_offset))
    settings = O(passage_guid=Guid("PG"), label=label, choreography=True, music=music)
    show = O(tick_resolution=Rate(24000), passage_settings=[settings], music_rails=[O(rail_guid=Guid("OTHER"),
             analysis_map=None, source_in_frame=Frame(0)), rail])
    return show, Master([Section(Guid("PG"), start, start + length)])


def hand_markers(analysis, length, offset_s=0.0):
    """Independent re-derivation from the choreo_tool docstring (bars every 4 sorted beats, changes, window)."""
    beats = sorted(p["timeSeconds"] for p in analysis["beatProposals"])
    out = [(t - offset_s, "bar %d" % (i // 4 + 1)) for i, t in enumerate(beats) if i % 4 == 0]
    out += [(p["timeSeconds"] - offset_s, "§ " + (p.get("label") or "change")) for p in analysis["majorChangeProposals"]]
    return [(int(round(t * TICK)), l) for t, l in out if 0.0 <= t <= length + 30.0]


def frames_via_create_choreo(row):
    """Run choreo_tool._create_choreo itself on a fake asset tool; capture the marked frames it adds."""
    added = []

    class Seq(object):
        def __getattr__(self, name):
            if name == "add_marked_frame":
                return lambda mf: added.append((mf.v["frame_number"].value, mf.v["label"]))
            return lambda *a, **k: None

    class MF(object):
        def __init__(self):
            self.v = {}

        def set_editor_property(self, k, v):
            self.v[k] = v

    class U(object):
        class EditorAssetLibrary(object):
            does_asset_exist = staticmethod(lambda p: False)

        class AssetToolsHelpers(object):
            @staticmethod
            def get_asset_tools():
                return O.__new__(type("T", (), {"create_asset": lambda self, *a: Seq()}))

        LevelSequence = LevelSequenceFactoryNew = object
        FrameNumber = Frame
        MovieSceneMarkedFrame = MF

    U.LevelSequenceFactoryNew = lambda: None
    NS["_create_choreo"](U, row, Master([]))
    return added


NEW_FIX = {"passage": 2, "source": {"sha256": "abc"}, "safety": {"cueScoreMutated": False},
           "beatProposals": [{"timeSeconds": t, "state": "Suggested"} for t in
                             (5.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 30.9, 31.0, 31.5)],
           "majorChangeProposals": [{"timeSeconds": 3.2, "label": "Major change suggestion", "state": "Suggested"},
                                    {"timeSeconds": 0.1, "label": "", "state": "Suggested"},
                                    {"timeSeconds": 99.0, "label": "Major change suggestion", "state": "Suggested"}]}


# --------------------------------------------------------------------------------------------------- classification
def mk(frame, label, **kw):
    return sm.norm_marker(frame, label, **kw)


SONG = ["bar 1", "bar 12", "bar 109", "§ Major change suggestion", "§ change"]
GO = ["GO 12 bar crossing", "GO 3 HOLD § cue", "GO 4 PASS bar 2", "GO 1.5 lights"]
OTHER = ["InfinityStage.VampStart", "curtain in", "crossbar", "Embargo"]
AMBIG = ["Bar 3", "bar 03", "bar 0", "bar 3 ", " bar 3", "bar 3 crossing", "bars", "bar", "§change",
         "§ Something else", "go 12 bar", "the bar", "GO bar 3", "bar\t3"]


def classification_failures(classify):
    bad = []
    for l in SONG:
        if classify(mk(0, l), BODIES, ())[0] != "song":
            bad.append(("song", l))
    for l in GO:
        if classify(mk(0, l), BODIES, ())[0] != "go":
            bad.append(("go", l))
    for l in OTHER:
        if classify(mk(0, l), BODIES, ())[0] != "other":
            bad.append(("other", l))
    for l in AMBIG:
        if classify(mk(0, l), BODIES, ())[0] != "ambiguous":
            bad.append(("ambiguous", l))
    for kw in ({"comment": "Gary"}, {"use_custom_color": True}, {"fence": True}, {"inclusive": True}):
        if classify(mk(0, "bar 3", **kw), BODIES, ())[0] != "ambiguous":
            bad.append(("nondefault", kw))
    if classify(mk(0, "Bar fight"), BODIES, ("Bar fight",))[0] != "keep":
        bad.append(("declared", "Bar fight"))
    return bad


@test
def classification():
    got = classification_failures(sm.classify)
    check(got == [], "classifier: %r" % got)
    # failing control: walking_music_swap.py:117's prefix test as a remover would delete GO/look-alikes
    naive = lambda m, b, k: (("song", "") if m["label"].startswith(("bar ", "§ ")) else ("other", ""))
    nb = classification_failures(naive)
    check(("ambiguous", "bar 3 crossing") in nb and ("ambiguous", "Bar 3") in nb and len(nb) > 5,
          "control: naive prefix classifier must fail: %r" % nb)
    # failing control: without the GO rule the look-alike GO cue would be refused/removed, not kept
    no_go = lambda m, b, k: ("ambiguous", "") if sm.LOOKALIKE_RE.search(m["label"]) and not sm.BAR_RE.match(m["label"]) \
        else sm.classify(m, b, k)
    check(("go", "GO 12 bar crossing") in classification_failures(no_go), "control: GO rule is load-bearing")


@test
def labels_written_by_choreo_tool_are_song():
    """Every label the real choreo_tool produces from the real analyses classifies as song (no false 'ambiguous')."""
    for k in LENGTH:
        for rel in (ARGS["analysis"][k], ARGS["old_analysis"][k]):
            a = load_json(rel)
            show, master = world(ue_map(a), LENGTH[k])
            rows, _ = NS["_plan"](UE, show, master, ["Passage 2"])
            kinds = set(sm.classify(mk(0, l), BODIES)[0] for _, l in rows[0]["markers"])
            check(kinds == {"song"}, "P%s %s kinds %r" % (k, rel, kinds))


# ---------------------------------------------------------------------------------------------------------- maths
@test
def new_marker_maths_match_choreo_tool():
    for source_in, rail_offset, length in ((0, 0, 180.0), (12000, 24000, 180.0), (0, 0, 1.2), (0, -48000, 2.0)):
        offset_s = (source_in + rail_offset) / TICK
        show, master = world(ue_map(NEW_FIX), length, source_in, rail_offset)
        # ours: proxy over a show whose linked map is something else entirely
        stale_show, _ = world(ue_map({"beatProposals": [{"timeSeconds": 7.0}], "majorChangeProposals": []}), length,
                              source_in, rail_offset)
        ours, _ = sm.plan_markers(NS, UE, stale_show, master, "Passage 2", TICK, sm.json_map_proxy(NEW_FIX, SUG), "RAIL")
        rows, _ = NS["_plan"](UE, show, master, ["Passage 2"])
        theirs = frames_via_create_choreo(rows[0])
        hand = hand_markers(NEW_FIX, length, offset_s)
        got = [(m["frame"], m["label"]) for m in ours]
        check(got == theirs, "vs _create_choreo (in=%d off=%d len=%s): %r != %r" % (source_in, rail_offset, length, got, theirs))
        check(got == hand, "vs hand maths (in=%d off=%d len=%s): %r != %r" % (source_in, rail_offset, length, got, hand))
        check(all(m == sm.norm_marker(m["frame"], m["label"]) for m in ours), "new markers carry only frame+label")
    # failing controls: the proxy is load-bearing, and the hand maths can tell an off-by-one bar numbering
    show, master = world(ue_map({"beatProposals": [{"timeSeconds": 7.0}], "majorChangeProposals": []}), 180.0)
    stale, _ = sm.plan_markers(NS, UE, show, master, "Passage 2", TICK)
    check([(m["frame"], m["label"]) for m in stale] != hand_markers(NEW_FIX, 180.0), "control: linked map != new JSON")
    wrong = [(f, l.replace("bar 1", "bar 0")) for f, l in hand_markers(NEW_FIX, 180.0)]
    check(wrong != hand_markers(NEW_FIX, 180.0), "control: bar numbering is checked")
    # a Rejected beat in a UE map is skipped by choreo_tool; our JSON path refuses non-Suggested states instead
    bad = copy.deepcopy(NEW_FIX)
    bad["beatProposals"][0]["state"] = "Rejected"
    check(any(r.startswith("ANALYSIS_STATE") for r in sm.json_analysis_refusals(bad, "2", "abc")), "control: Rejected state refused")
    check(sm.json_analysis_refusals(NEW_FIX, "2", "abc") == [], "fixture JSON accepted")
    check(any(r.startswith("ANALYSIS_SHA") for r in sm.json_analysis_refusals(NEW_FIX, "2", "zzz")), "control: sha")
    check(any(r.startswith("ANALYSIS_PASSAGE") for r in sm.json_analysis_refusals(NEW_FIX, "3", "abc")), "control: passage")


@test
def real_old_analyses_reproduce_measured_counts():
    """choreo_tool on the superseded JSONs reproduces apply-3's marker_count (identity check is meaningful)."""
    for k, n in OLD_COUNT.items():
        a = load_json(ARGS["old_analysis"][k])
        show, master = world(ue_map(a), LENGTH[k])
        got, _ = sm.plan_markers(NS, UE, show, master, "Passage 2", TICK, sm.json_map_proxy(a, SUG), "RAIL")
        check(len(got) == n, "P%s old recompute %d != measured %d" % (k, len(got), n))
    # control: the new song does NOT reproduce the old counts
    a = load_json(ARGS["analysis"]["5"])
    show, master = world(ue_map(a), LENGTH["5"])
    got, _ = sm.plan_markers(NS, UE, show, master, "Passage 2", TICK, sm.json_map_proxy(a, SUG), "RAIL")
    check(len(got) != OLD_COUNT["5"], "control: new P5 count differs from old")


EXPECTED = {}


@test
def real_new_counts_and_walking_records():
    for k in LENGTH:
        a = load_json(ARGS["analysis"][k])
        walk = sm.walking_facts(HERE, k)
        check(sm.json_analysis_refusals(a, k, walk["sha256"]) == [], "P%s new JSON vs walking record: %r"
              % (k, sm.json_analysis_refusals(a, k, walk["sha256"])))
        show, master = world(ue_map(a), LENGTH[k])
        new, _ = sm.plan_markers(NS, UE, show, master, "Passage 2", TICK, sm.json_map_proxy(a, SUG), "RAIL")
        old_a = load_json(ARGS["old_analysis"][k])
        old, _ = sm.plan_markers(NS, UE, show, master, "Passage 2", TICK, sm.json_map_proxy(old_a, SUG), "RAIL")
        EXPECTED[k] = {"old": sm.span(old), "new": sm.span(new),
                       "new_bars": sum(1 for m in new if m["label"].startswith("bar ")),
                       "new_changes": sum(1 for m in new if m["label"].startswith("§ "))}
        check(not sm.same_multiset(old, new, sm.song_shape), "P%s new differs from old" % k)
    check(raises(lambda: sm.walking_facts(HERE, "6"), "WALK_RECORD"), "control: P06 has no swap record -> refused")


# ------------------------------------------------------------------------------------------- fake sequence adapters
class FakeSeq(object):
    def __init__(self, markers, lie_delete=False, shift_delete=0, mutate_on_add=False, sort_on_add=False):
        self.m = [dict(x) for x in markers]
        self.lie_delete, self.shift_delete = lie_delete, shift_delete
        self.mutate_on_add, self.sort_on_add = mutate_on_add, sort_on_add

    def list(self):
        return [copy.deepcopy(x) for x in self.m]

    def delete(self, index):
        if self.lie_delete:
            return
        i = min(index + self.shift_delete, len(self.m) - 1)
        del self.m[i]

    def add(self, marker):
        self.m.append(dict(marker))
        if self.mutate_on_add:
            for x in self.m:
                if x["label"].startswith("GO"):
                    x["comment"] = "touched"
        if self.sort_on_add:
            self.m.sort(key=lambda x: x["frame"])


def fixture_choreo():
    a = load_json(ARGS["old_analysis"]["3"])
    show, master = world(ue_map(a), LENGTH["3"])
    old, _ = sm.plan_markers(NS, UE, show, master, "Passage 2", TICK, sm.json_map_proxy(a, SUG), "RAIL")
    n = load_json(ARGS["analysis"]["3"])
    new, _ = sm.plan_markers(NS, UE, show, master, "Passage 2", TICK, sm.json_map_proxy(n, SUG), "RAIL")
    kept = [mk(240000, "GO 12 bar crossing", color=(1.0, 0.5, 0.0, 1.0), use_custom_color=True),
            mk(120000, "GO 3 HOLD wing reveal", comment="Gary 5 Oct"),
            mk(48000, "InfinityStage.VampStart"), mk(48000, "GO 4 PASS", fence=True, inclusive=True)]
    before = old[:5] + [kept[0]] + old[5:] + kept[1:]
    part = sm.partition(before, BODIES)
    row = {"choreo": "/Game/InfinityStage/Choreo/LS_Choreo_Passage_3", "before": before,
           "old_song": sm.strip_index(part["song"]), "kept": sm.strip_index(part["kept"]), "new_song": new}
    return row, part


@test
def plan_refusals_gate():
    row, part = fixture_choreo()
    check(part["ambiguous"] == [] and len(part["kept"]) == 4 and len(part["song"]) == OLD_COUNT["3"], "fixture partition")
    exp = {"old_analysis": row["old_song"]}
    check(sm.plan_refusals(part, row["new_song"], exp, row["choreo"]) == [], "clean plan accepted: %r"
          % sm.plan_refusals(part, row["new_song"], exp, row["choreo"]))
    amb = sm.partition(row["before"] + [mk(5, "Bar 3")], BODIES)
    check(any(r.startswith("AMBIGUOUS") for r in sm.plan_refusals(amb, row["new_song"], exp, row["choreo"])), "control: ambiguous")
    moved = sm.partition([dict(m, frame=m["frame"] + 1) if m["label"] == "bar 2" else m for m in row["before"]], BODIES)
    check(any(r.startswith("OLD_SONG_MARKERS_UNEXPLAINED") for r in sm.plan_refusals(moved, row["new_song"], exp, row["choreo"])),
          "control: a hand-moved bar marker is unexplained")
    check(any(r.startswith("NOOP") for r in sm.plan_refusals(part, row["old_song"], exp, row["choreo"])), "control: NOOP")
    check(any(r.startswith("NO_CHOREO") for r in sm.plan_refusals(part, row["new_song"], exp, None)), "control: no choreo")


@test
def apply_keeps_non_song_markers():
    row, _ = fixture_choreo()
    seq = FakeSeq(row["before"])
    after = sm.apply_one(seq, row, BODIES)
    check(sm.verify_after(after, row["kept"], row["new_song"], BODIES) == [], "apply verified")
    kept_after = [m for m in after if sm.classify(m, BODIES)[0] != "song"]
    check([sm.mkey(m) for m in kept_after] == [sm.mkey(m) for m in row["kept"]], "kept identical, every field, same order")
    check(sum(1 for m in after if sm.classify(m, BODIES)[0] == "song") == len(row["new_song"]), "song count == plan")
    # failing controls
    check(raises(lambda: sm.apply_one(FakeSeq(row["before"], lie_delete=True), row, BODIES), "REMOVE_INDEX_MOVED")
          or raises(lambda: sm.apply_one(FakeSeq(row["before"], lie_delete=True), row, BODIES), "REMOVE_RELIST_MISMATCH"),
          "control: a lying delete is caught by re-listing")
    check(raises(lambda: sm.apply_one(FakeSeq(row["before"], shift_delete=1), row, BODIES), "REMOVE_"),
          "control: a delete that hits the wrong index is caught")
    check(raises(lambda: sm.apply_one(FakeSeq(row["before"], mutate_on_add=True), row, BODIES), "READBACK: KEPT_CHANGED"),
          "control: a kept GO marker changed by the write is caught")
    check(raises(lambda: sm.apply_one(FakeSeq(row["before"], sort_on_add=True), row, BODIES), "READBACK: KEPT_REORDERED"),
          "control: reordering kept markers is caught")
    drift = FakeSeq(row["before"] + [mk(1, "GO 99 late")])
    check(raises(lambda: sm.apply_one(drift, row, BODIES), "DRIFT_SINCE_PLAN"), "control: drift between plan and write")
    short = dict(row, new_song=row["new_song"][:-1])
    check(sm.verify_after(after, short["kept"], short["new_song"], BODIES) != [], "control: song count mismatch caught")


@test
def revert_exact():
    row, _ = fixture_choreo()
    seq = FakeSeq(row["before"])
    sm.apply_one(seq, row, BODIES)
    after, identical = sm.revert_one(seq, row, BODIES)
    check(identical, "revert restores the exact multiset of every marker field")
    check(sm.same_multiset(after, row["before"]), "revert full-key multiset == before")
    # a GO marker added after APPLY survives revert untouched (and identical_to_before is honestly False)
    seq2 = FakeSeq(row["before"])
    sm.apply_one(seq2, row, BODIES)
    seq2.m.append(mk(7, "GO 50 added later"))
    after2, identical2 = sm.revert_one(seq2, row, BODIES)
    check(not identical2 and any(m["label"] == "GO 50 added later" for m in after2)
          and sm.same_multiset([m for m in after2 if m["label"] != "GO 50 added later"], row["before"]),
          "revert keeps later GO marker, restores the rest")
    # failing controls
    seq3 = FakeSeq(row["before"])
    sm.apply_one(seq3, row, BODIES)
    seq3.m = [dict(m, frame=m["frame"] + 1) if m["label"] == "bar 3" else m for m in seq3.m]
    check(raises(lambda: sm.revert_one(seq3, row, BODIES), "REVERT_DRIFT"), "control: hand-moved new marker -> drift")
    seq4 = FakeSeq(row["before"])
    sm.apply_one(seq4, row, BODIES)
    seq4.lie_delete = True
    check(raises(lambda: sm.revert_one(seq4, row, BODIES), "REMOVE_"), "control: lying delete in revert")
    seq5 = FakeSeq(row["before"])
    sm.apply_one(seq5, row, BODIES)
    tampered = dict(row, old_song=row["old_song"][1:])
    _, ident5 = sm.revert_one(seq5, tampered, BODIES)
    check(not ident5, "control: an incomplete record cannot claim identical_to_before")


# ---------------------------------------------------------------------------------------------- gates and plumbing
@test
def live_gates():
    ok = {"mode": "APPLY", "confirm": "APPLY SONGMARKERS", "census": {"content": [], "maps": []}}
    check(sm.live_gates(ok) == [], "clean APPLY state passes")
    check(sm.live_gates({"mode": "DRY", "confirm": "DRY SONGMARKERS"}) == [], "clean DRY passes")
    for bad, prefix in ((dict(ok, confirm="DRY SONGMARKERS"), "CONFIRM_MISMATCH"), (dict(ok, pie=True), "PIE_OR_SIE"),
                        (dict(ok, sequencer_open=True), "SEQUENCER_IS_OPEN"),
                        (dict(ok, census={"content": ["/Game/X"], "maps": []}), "DIRTY_CENSUS"),
                        (dict(ok, census={"content": [], "maps": ["/Game/M"]}), "DIRTY_CENSUS"),
                        (dict(ok, wrong_world="/Game/Other"), "WRONG_WORLD"),
                        (dict(ok, overlapping_records=["r.json"]), "RECORD_COVERS_TARGET"),
                        ({"mode": "REVERT", "confirm": "REVERT SONGMARKERS"}, "NO_APPLIED_RECORD"),
                        (dict(ok, mode="FIX", confirm="FIX SONGMARKERS"), "MODE_INVALID")):
        check(any(r.startswith(prefix) for r in sm.live_gates(bad)), "control: %s" % prefix)
    check(sm.census_gate({"content": ["/Game/C"], "maps": []}, ["/Game/C"]) == [], "census within allowed")
    check(sm.census_gate({"content": ["/Game/C", "/Game/Show"], "maps": []}, ["/Game/C"]) != [], "control: stray dirty")
    check(sm.census_gate({"content": [], "maps": ["/Game/Map"]}, []) != [], "control: map dirty")


@test
def args_and_records():
    check(sm.validate_args(ARGS) == [], "shipped args valid: %r" % sm.validate_args(ARGS))
    check(ARGS["confirm"] == "%s SONGMARKERS" % ARGS["mode"], "shipped confirm matches mode")
    check(sm.validate_args(dict(ARGS, passages=["1", "7"])) != [], "control: bad passage")
    check(sm.validate_args(dict(ARGS, passages=["6"])) != [], "control: passage without new analysis")
    check(sm.record_name(["5", "1", "2"]) == "choreo_song_markers_refresh_record_P01-P02-P05.json", "record name")
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, sm.record_name(["1"]))
        sm.write_record_exclusive(p, {"a": "§ x"})
        try:
            sm.write_record_exclusive(p, {"a": 2})
            second = True
        except FileExistsError:
            second = False
        check(not second, "control: record is create-only")
        check(sm.records_covering(tmp, ["1", "2"]) == [os.path.basename(p)], "overlap found")
        check(sm.records_covering(tmp, ["3"]) == [], "no overlap")
        with open(p, encoding="utf-8") as h:
            check(json.load(h)["a"] == "§ x", "record keeps the section sign (utf-8)")
    check(NS["__sha256__"] and callable(NS["_plan"]), "choreo_tool loaded without running")
    with tempfile.TemporaryDirectory() as tmp:
        with open(CHOREO_TOOL, encoding="utf-8") as h:
            src = h.read().replace("BEATS_PER_BAR = 4", "BEATS_PER_BAR = 3")
        p = os.path.join(tmp, "choreo_tool.py")
        with open(p, "w", encoding="utf-8") as h:
            h.write(src)
        check(raises(lambda: sm.load_choreo_tool(p), "CHOREO_TOOL_CHANGED"), "control: changed choreo_tool refused")


def main():
    for fn in TESTS:
        before = len(CHECKS["failed"])
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            CHECKS["failed"].append("%s raised %r" % (fn.__name__, exc))
        print("%-45s %s" % (fn.__name__, "ok" if len(CHECKS["failed"]) == before else "FAIL"))
    for f in CHECKS["failed"]:
        print("  FAILED:", f)
    for k in sorted(EXPECTED):
        print("EXPECTED P%s %s" % (k, json.dumps(EXPECTED[k], sort_keys=True)))
    print("CHOREO_SONG_MARKERS_HARNESS|tests=%d|checks=%d|failed=%d" % (len(TESTS), CHECKS["n"], len(CHECKS["failed"])))
    return 1 if CHECKS["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
