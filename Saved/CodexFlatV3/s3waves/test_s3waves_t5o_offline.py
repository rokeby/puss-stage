"""Offline harness for the S3 waves t5o tool: core planning, the real build/spacing inputs, and the UE tool's sequence
code paths against a FAKE unreal object model, each with +/- controls (a check that cannot fail is not a check).
Run: D:/PussStageTools/FlatV3/venv/Scripts/python.exe Saved/CodexFlatV3/s3waves/test_s3waves_t5o_offline.py
Writes test_s3waves_t5o_offline_report.json; prints S3T5O_HARNESS|pass=<n>|fail=<m>.
"""
import ast
import copy
import importlib.util
import json
import os
import sys
import traceback
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
S3W = PROJECT / "Saved" / "CodexConductor" / "S3Waves"
RESULTS = []


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


T = load("t5o_core_h", HERE / "s3waves_t5o_core.py")
V3 = load("v3_core_h", S3W / "s3_waves_v3_core.py")
TOOL = load("t5o_tool_h", HERE / "s3waves_t5o.py")


def check(name, fn):
    try:
        fn()
        RESULTS.append({"name": name, "pass": True})
    except Exception as exc:  # noqa: BLE001
        RESULTS.append({"name": name, "pass": False, "error": "%s: %s" % (type(exc).__name__, str(exc)[:300]),
                        "trace": traceback.format_exc()[-600:]})


def refuses(fn, token):
    try:
        fn()
    except T.PlanError as exc:
        assert token in str(exc), "refused with the wrong reason: %s (want %s)" % (exc, token)
        return
    raise AssertionError("did NOT refuse (want %s)" % token)


def jload(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


PLAN = jload(S3W / "build_plan_B.json")
REPORT = jload(PROJECT / "DerivedAssets/FlatV3/Scene3/WavesV3_t5o/build_report_t5o.json")
APPLY_V3 = jload(S3W / "s3_waves_v3_apply_record.json")
MOTION_PLAN = jload(S3W / "s3_waves_v3_motion_plan.json")
ROWS = T.piece_rows(PLAN, REPORT, APPLY_V3)
STATE = {"fps": 24.0, "playback": [0, 6240], "strike": {"frame": 240}}
NO_REC = {"apply": False, "applied": False}


# ------------------------------------------------------------------------------------------------ modes
def t_modes():
    assert T.check_mode({"mode": "DRY"}, False, NO_REC) == "DRY"
    refuses(lambda: T.check_mode({"mode": "APPLY"}, False, NO_REC), "CONFIRM_MISSING")
    assert T.check_mode({"mode": "APPLY", "confirm": "APPLY S3T5O"}, False, NO_REC) == "APPLY"
    refuses(lambda: T.check_mode({"mode": "APPLY", "confirm": "APPLY S3T5O"}, False, {"apply": True, "applied": True}),
            "ALREADY_APPLIED")
    refuses(lambda: T.check_mode({"mode": "REVERT", "confirm": "REVERT S3T5O"}, False, NO_REC), "NO_APPLY_RECORD")
    refuses(lambda: T.check_mode({"mode": "IMPORT", "confirm": "IMPORT S3T5O", "pieces": ["a", "b", "c", "d"]}, False,
                                 NO_REC), "BATCH")
    assert T.check_mode({"mode": "IMPORT", "confirm": "IMPORT S3T5O", "pieces": ["a", "b", "c"]}, False, NO_REC)
    refuses(lambda: T.check_mode({"mode": "IMPORT", "confirm": "IMPORT S3T5O", "pieces": []}, False, NO_REC), "BATCH")
    refuses(lambda: T.check_mode({"mode": "MATS", "confirm": "MATS S3T5O", "pieces": list("abcde")}, False, NO_REC),
            "BATCH")
    refuses(lambda: T.check_mode({"mode": "IMPORT", "confirm": "IMPORT S3T5O", "pieces": ["a", "a"]}, False, NO_REC),
            "BATCH_DUPLICATES")
    refuses(lambda: T.check_mode({"mode": "MI", "confirm": "MI S3T5O"}, False, {"apply": True, "applied": True}),
            "ASSET_WRITE_WHILE_APPLIED")
    refuses(lambda: T.check_mode({"mode": "DRY"}, True, NO_REC), "PIE_ACTIVE")
    refuses(lambda: T.check_mode({"mode": "BOGUS"}, False, NO_REC), "MODE")


# ------------------------------------------------------------------------------------------------ build inputs
def t_build_report():
    assert REPORT.get("all_pass") is True and len(REPORT["pieces"]) == 12
    for s, r in REPORT["pieces"].items():
        assert r["G0_live_inputs"]["pass"] and r["G0_live_inputs"]["live_fbx_sha_matches_import_record"], s
        v = r["G2_validation"]
        assert v["pass"] and v["checks_passed"] == v["checks_total"] == 27, (s, v["checks_passed"])
        assert abs(v["board_thickness"]["measured_edge_slot_m"] - 0.05) < 0.0015, s
        for lod, e in r["G3_edge"]["lods"].items():
            assert e["edge_inward_area_fraction"] == 0.0 and e["front_x"] == [-15.0, -15.0], (s, lod)
            assert e["edge_x"] == [-15.0, -10.0], (s, lod, e["edge_x"])
        for lod, g in r["G4_uv0_registration"]["lods"].items():
            assert g["Front_identical"] and g["Flap_identical"], (s, lod)
            assert g["triangles_live"] == g["triangles_new"], (s, lod)
        assert r["geometry_profile"]["name"] == "thick5" and abs(r["geometry_profile"]["board_thickness_cm"] - 5) < 1e-9
        assert Path(r["out_dir"]).is_dir()


def t_piece_rows_negative():
    bad = copy.deepcopy(REPORT)
    k = sorted(bad["pieces"])[3]
    bad["pieces"][k]["G3_edge"]["pass"] = False
    refuses(lambda: T.piece_rows(PLAN, bad, APPLY_V3), "T5O_GATE")
    bad2 = copy.deepcopy(REPORT)
    bad2["pieces"][k]["mount_local_live"] = [1.0, 2.0, 3.0]
    refuses(lambda: T.piece_rows(PLAN, bad2, APPLY_V3), "MOUNT_DRIFT")
    rec = copy.deepcopy(APPLY_V3)
    rec["created"] = rec["created"][1:]
    refuses(lambda: T.piece_rows(PLAN, REPORT, rec), "NO_LIVE_ACTOR")


def t_mi_edge_matches_probe():
    plan = T.mi_plan()
    assert plan["parent"] == T.EDGE_V3_MASTER and plan["path"].endswith("/MI_WaveEdge_SeaPaint")
    # thick5 Edge spans x -15..-10 in all 12 probes -> centre -12.5, half 2.5
    for r in REPORT["pieces"].values():
        e = r["G3_edge"]["lods"]["LOD0"]["edge_x"]
        assert abs(0.5 * (e[0] + e[1]) - plan["scalars"]["EdgeCentreXCm"]) < 1e-6
        assert abs(0.5 * (e[1] - e[0]) - plan["scalars"]["HalfThicknessCm"]) < 1e-6
    sampled = jload(HERE / "edge_sea_colour.json")["mi_vectors_linear"]
    for k, v in sampled.items():
        assert T.near(plan["vectors"][k], v, 1e-4), (k, v)
    refuses(lambda: T.mi_plan(scalars={"EdgeCentreXCm": 0.0, "HalfThicknessCm": 2.5}), "MI_EDGE_GEOMETRY")
    refuses(lambda: T.mi_plan(vectors={"TimberLight": (1.5, 0, 0)}), "MI_VECTOR_RANGE")
    refuses(lambda: T.mi_plan(vectors={"BaseColor": (0.1, 0.1, 0.1)}), "MI_VECTOR_NAMES")


def t_slot_plan():
    r = ROWS[0]
    sp = T.slot_plan(r)
    assert sp[0].endswith("_Front") and sp[1].endswith("_Flap") and sp[2] == T.TIMBER_V1 and sp[3] == T.MI_EDGE
    assert r["mesh"].endswith("_t5o") and not r["live_mesh"].endswith("_t5o")


# ------------------------------------------------------------------------------------------------ layout + path
def t_layout():
    lay = T.plan_layout(ROWS)
    for p in lay["pieces"]:
        assert p["inside_band"], p
    pp = [g for g in lay["pairs"] if g["kind"] == "P1_P2"]
    assert len(pp) == 6 and all(g["pitch_new"] >= 17.0 and g["clear_new"] > 3.0 for g in pp)
    assert all(g["clear_old_if_t5o"] < 0 for g in pp), "control: t5o meshes at the OLD x must collide"
    for g in lay["layer_gaps"]:
        extra = g["clear_new"] - g["clear_old_live"]
        assert 10.0 <= extra <= 20.0, (g, extra)          # Gary: ~+10-20 cm more depth between layers


def t_layout_negative():
    old = {r["suffix"]: r["mount_local"][0] for r in ROWS}
    refuses(lambda: T.plan_layout(ROWS, old), "OUTSIDE_BAND")      # live L1P1 front 3634.1 < flat band 3639 [meas]
    clash = dict(T.NEW_X)
    clash["S3_WaveV3_L2SwellNear_P1"] = clash["S3_WaveV3_L1Breakers_P2"] + 10.0
    refuses(lambda: T.plan_layout(ROWS, clash), "INTERPENETRATION_AT_REST")
    out = dict(T.NEW_X)
    out["S3_WaveV3_L2SwellNear_P2"] = 3746.0
    refuses(lambda: T.plan_layout(ROWS, out), "OUTSIDE_BAND")
    tight = dict(T.NEW_X)
    tight["S3_WaveV3_L1Breakers_P2"] = tight["S3_WaveV3_L1Breakers_P1"] + 16.5
    refuses(lambda: T.plan_layout(ROWS, tight), "P1P2_PITCH")


def t_path():
    p_old = V3.plan_motion(STATE, ROWS, MOTION_PLAN)
    p_new = V3.plan_motion(STATE, T.shifted_rows(ROWS), MOTION_PLAN)
    r = T.path_clearance(p_old, p_new, ROWS)
    assert r["frames_checked"] == 2002 and r["first"] == 239 and r["last"] == 6240
    assert r["min_x_clearance_yz_overlapping"]["cm"] > 3.0 and r["x_extent_drift_max_cm"] < 1e-6
    # -: the same meshes at the old x collide on the path
    refuses(lambda: T.path_clearance(p_old, p_old, ROWS, new_x={x["suffix"]: x["mount_local"][0] for x in ROWS}),
            "PATH_INTERPENETRATION")
    # -: a Y change sneaking into the shifted keys is caught
    bad = copy.deepcopy(p_new)
    bad["pieces"][0]["keys"][10]["location"][1] += 0.5
    refuses(lambda: T.path_clearance(p_old, bad, ROWS), "NON_X_CHANNEL_CHANGED")
    # -: an x shift that is not dx is caught
    bad2 = copy.deepcopy(p_new)
    bad2["pieces"][3]["keys"][5]["location"][0] += 1.0
    refuses(lambda: T.path_clearance(p_old, bad2, ROWS), "KEY_DX")


def t_live_x_keys_rule():
    """The v3 motion keys put EVERY Location.X key at the rest x (roll-only rotation): proven on the formula here,
    re-read live by DRY/APPLY."""
    p_old = V3.plan_motion(STATE, ROWS, MOTION_PLAN)
    for p, r in zip(sorted(p_old["pieces"], key=lambda q: q["suffix"]), sorted(ROWS, key=lambda q: q["suffix"])):
        xs = {round(k["location"][0], 9) for k in p["keys"]}
        assert xs == {r["mount_local"][0]}, (p["suffix"], list(xs)[:3])


# ------------------------------------------------------------------------------------------------ keys
def t_keys():
    orig = [[239, 3650.0], [240, 3650.0], [243, 3650.0]]
    new = T.shift_x_keys(orig, 3650.0, 6.0)
    assert new == [[239, 3656.0], [240, 3656.0], [243, 3656.0]]
    refuses(lambda: T.shift_x_keys([[239, 3650.0], [240, 3651.0]], 3650.0, 6.0), "X_KEY_NOT_REST")
    refuses(lambda: T.shift_x_keys([], 3650.0, 6.0), "NO_X_KEYS")
    refuses(lambda: T.shift_x_keys([[240, 3650.0], [239, 3650.0]], 3650.0, 6.0), "X_KEY_FRAMES_UNSORTED")
    assert T.revert_x_keys(new, orig, 6.0) == orig
    refuses(lambda: T.revert_x_keys([[239, 3656.0], [240, 3657.0], [243, 3656.0]], orig, 6.0), "REVERT_X_DRIFT")
    refuses(lambda: T.revert_x_keys(new[:2], orig, 6.0), "REVERT_X_FRAMES_CHANGED")


# ------------------------------------------------------------------------------------------------ fingerprint (pure)
def _fp():
    return {"SEQ": {"struct": "sequence", "fps": [24, 1], "playback": [0, 6240]},
            "B:A/T0:MovieScene3DTransformTrack:S3.WavesV3.Motion/S0/C0:Location.X": {"n": 3, "sha": "x0", "interp": "i",
                                                                                     "default": None},
            "B:A/T0:MovieScene3DTransformTrack:S3.WavesV3.Motion/S0/C1:Location.Y": {"n": 3, "sha": "y0", "interp": "i",
                                                                                     "default": None},
            "B:F/T0:MovieSceneFloatTrack:S3.Fire.Light/S0/C0:": {"n": 4, "sha": "f0", "interp": "j", "default": 0.0}}


def t_fingerprint_diff():
    xp = "B:A/T0:MovieScene3DTransformTrack:S3.WavesV3.Motion/S0/C0:Location.X"
    b, a = _fp(), _fp()
    a[xp] = dict(a[xp], sha="x1")
    assert T.fingerprint_diff(b, a, {xp: "x1"}) == []
    assert [v["why"] for v in T.fingerprint_diff(b, a, {xp: "x2"})] == ["ALLOWED_CHANNEL_NOT_AS_PLANNED"]
    c = copy.deepcopy(a)
    c["B:F/T0:MovieSceneFloatTrack:S3.Fire.Light/S0/C0:"]["sha"] = "f1"          # a foreign (fire) key changed
    assert [v["why"] for v in T.fingerprint_diff(b, c, {xp: "x1"})] == ["CHANGED"]
    d = copy.deepcopy(a)
    d["B:A/T0:MovieScene3DTransformTrack:S3.WavesV3.Motion/S0/C1:Location.Y"]["sha"] = "y1"
    assert [v["why"] for v in T.fingerprint_diff(b, d, {xp: "x1"})] == ["CHANGED"]
    e = copy.deepcopy(a)
    e["B:Z"] = {"struct": "binding"}
    assert [v["why"] for v in T.fingerprint_diff(b, e, {xp: "x1"})] == ["ADDED"]
    f = copy.deepcopy(a)
    f[xp]["interp"] = "cubic"
    assert [v["why"] for v in T.fingerprint_diff(b, f, {xp: "x1"})] == ["ALLOWED_CHANNEL_META_CHANGED"]
    g = copy.deepcopy(a)
    del g["SEQ"]
    assert [v["why"] for v in T.fingerprint_diff(b, g, {xp: "x1"})] == ["REMOVED"]
    rep = T.expected_tracks_report(["S3.Fire.Light", "S3.WavesV3.Motion"])
    assert rep["present"] == ["S3.Fire.Light"] and rep["blocking"] is False


def t_census_scope():
    assert T.apply_scope({"content": [T.ROOT_SEQ], "maps": [T.WORLD]})
    refuses(lambda: T.apply_scope({"content": [T.ROOT_SEQ], "maps": []}), "LEVEL_NOT_DIRTY")
    refuses(lambda: T.apply_scope({"content": [T.ROOT_SEQ], "maps": [T.WORLD, "/Game/Klara/L_Klara_S3"]}),
            "FOREIGN_MAP_DIRTY")
    refuses(lambda: T.apply_scope({"content": [T.ROOT_SEQ, "/Game/X"], "maps": [T.WORLD]}), "CONTENT_SCOPE")
    assert T.census_scope_ok({"content": ["/a"], "maps": []}, ["/a"], [])
    assert not T.census_scope_ok({"content": ["/a", "/b"], "maps": []}, ["/a"], [])


# ------------------------------------------------------------------------------------------------ apply / revert plans
def _live_from_rows(rows):
    live = {}
    p_old = {p["suffix"]: p for p in V3.plan_motion(STATE, rows, MOTION_PLAN)["pieces"]}
    for i, r in enumerate(rows):
        g = "G%02d" % i
        live[r["suffix"]] = {"label_count": 1, "actor_path": r["actor_path"], "parent_label": T.ROOT_LABEL,
                             "mesh": r["live_mesh"], "relative": {"location": list(r["mount_local"])},
                             "binding_guid": g, "motion_tracks": [T.MOTION_TRACK],
                             "x_keys": [[k["frame"], k["location"][0]] for k in p_old[r["suffix"]]["keys"]],
                             "x_channel_path": T.x_channel_path(g, 0, 0, 0)}
    return live


def t_plan_apply():
    lay = T.plan_layout(ROWS)
    live = _live_from_rows(ROWS)
    plan = T.plan_apply(ROWS, live, lay)
    assert len(plan["ops"]) == 12 and len(plan["allowed"]) == 12
    for op in plan["ops"]:
        assert op["relative_location"]["after"][0] == T.NEW_X[op["suffix"]]
        assert op["relative_location"]["after"][1:] == op["relative_location"]["before"][1:]
        assert op["mesh"]["after"].endswith("_t5o") and op["x_keys"]["count"] == 2002
    for mut, tok in ((lambda L: L.update(mesh="/Game/Other"), "MESH_NOT_LIVE_V3"),
                     (lambda L: L.update(parent_label="Nope"), "PARENT"),
                     (lambda L: L.update(label_count=2), "LABEL_COUNT"),
                     (lambda L: L.update(motion_tracks=[T.MOTION_TRACK, "Extra"]), "MOTION_TRACKS"),
                     (lambda L: L.update(binding_guid=None), "NO_MOTION_BINDING"),
                     (lambda L: L["x_keys"][7].__setitem__(1, L["x_keys"][7][1] + 1.0), "X_KEY_NOT_REST"),
                     (lambda L: L["relative"].update(location=[1.0, 2.0, 3.0]), "RELATIVE")):
        bad = copy.deepcopy(live)
        mut(bad[ROWS[2]["suffix"]])
        refuses(lambda: T.plan_apply(ROWS, bad, lay), tok)
    # revert plan from the applied state
    orig = T.originals_from_live(ROWS, live)
    rec = {"plan": plan}
    applied = copy.deepcopy(live)
    for op in plan["ops"]:
        L = applied[op["suffix"]]
        L["mesh"] = op["mesh"]["after"]
        L["relative"]["location"] = op["relative_location"]["after"]
        L["x_keys"] = [[f, v + op["dx"]] for f, v in L["x_keys"]]
    rp = T.revert_plan(rec, orig, applied)
    for op in rp["ops"]:
        o = orig["pieces"][op["suffix"]]
        assert op["mesh"] == o["mesh"] and op["x_keys"] == o["x_keys"]
        assert rp["allowed"][o["x_channel_path"]] == T.value_sha(o["x_keys"])
    drift = copy.deepcopy(applied)
    drift[ROWS[0]["suffix"]]["mesh"] = ROWS[0]["live_mesh"]
    refuses(lambda: T.revert_plan(rec, orig, drift), "REVERT_MESH_DRIFT")
    drift2 = copy.deepcopy(applied)
    drift2[ROWS[1]["suffix"]]["x_keys"][0][1] += 2.0
    refuses(lambda: T.revert_plan(rec, orig, drift2), "REVERT_X_DRIFT")


# ------------------------------------------------------------------------------------------------ UE code vs fake unreal
class FakeGuid:
    def __init__(self, s):
        self.s = s


class FakeTime:
    def __init__(self, f):
        self.frame_number = types.SimpleNamespace(value=f)


class FakeKey:
    def __init__(self, f, v):
        self.f, self.v = f, v

    def get_time(self, time_unit=None):
        return FakeTime(self.f)

    def get_value(self):
        return self.v

    def set_value(self, v):
        self.v = v

    def get_interpolation_mode(self):
        return "RCIM_LINEAR"

    def get_tangent_mode(self):
        return "RCTM_AUTO"


class FakeChannel:
    def __init__(self, name, keys, default=None):
        self.name, self.keys, self.default = name, [FakeKey(f, v) for f, v in keys], default

    def get_name(self):
        return self.name

    def get_keys(self):
        return list(self.keys)

    def has_default(self):
        return self.default is not None

    def get_default(self):
        return self.default


class FakeClass:
    def __init__(self, n):
        self.n = n

    def get_name(self):
        return self.n


class FakeSection:
    def __init__(self, chans, rng=(239, 6241)):
        self.chans, self.rng = chans, rng

    def get_all_channels(self):
        return list(self.chans)

    def get_class(self):
        return FakeClass("MovieScene3DTransformSection")

    def get_start_frame(self):
        return self.rng[0]

    def get_end_frame(self):
        return self.rng[1]

    def has_start_frame(self):
        return True

    def has_end_frame(self):
        return True

    def is_active(self):
        return True


class FakeTrack:
    def __init__(self, cls, name, sections, prop=None):
        self.cls, self.name, self.sections, self.prop = cls, name, sections, prop

    def get_class(self):
        return FakeClass(self.cls)

    def get_display_name(self):
        return self.name

    def get_sections(self):
        return list(self.sections)

    def get_property_name(self):
        if self.prop is None:
            raise AttributeError("no property")
        return self.prop


class FakeBinding:
    def __init__(self, guid, name, tracks, children=()):
        self.guid, self.name, self.tracks, self.children = guid, name, tracks, list(children)

    def get_id(self):
        return FakeGuid(self.guid)

    def get_display_name(self):
        return self.name

    def get_tracks(self):
        return list(self.tracks)

    def get_child_possessables(self):
        return list(self.children)

    def get_parent(self):
        return None


class FakeSeq:
    def __init__(self, bindings, tracks):
        self.bindings, self.tracks = bindings, tracks

    def get_bindings(self):
        return list(self.bindings)

    def get_tracks(self):
        return list(self.tracks)

    def get_display_rate(self):
        return types.SimpleNamespace(numerator=24, denominator=1)

    def get_playback_start(self):
        return 0

    def get_playback_end(self):
        return 6240


def _fake_unreal():
    return types.SimpleNamespace(
        GuidLibrary=types.SimpleNamespace(conv_guid_to_string=lambda g: g.s),
        MovieSceneTimeUnit=types.SimpleNamespace(DISPLAY_RATE="DISPLAY_RATE"))


def _fake_seq():
    frames = list(range(239, 260, 3))
    wave = FakeBinding("WAVE1", "S3 WaveV3 L1Breakers P1", [FakeTrack(
        "MovieScene3DTransformTrack", T.MOTION_TRACK,
        [FakeSection([FakeChannel("Location.X_183", [(f, 3650.0) for f in frames]),
                      FakeChannel("Location.Y_184", [(f, 0.1 * f) for f in frames]),
                      FakeChannel("Location.Z_185", [(f, 95.0) for f in frames])])])])
    fire_comp = FakeBinding("FIREC", "LightComponent0", [FakeTrack(
        "MovieSceneFloatTrack", "S3.Fire.Light", [FakeSection([FakeChannel("", [(0, 0.0), (240, 5.0)], 0.0)])],
        prop="Intensity")])
    fire = FakeBinding("FIRE", "S3 Fire 1", [FakeTrack("MovieSceneVisibilityTrack", "S3.Fire.Visible",
                                                       [FakeSection([FakeChannel("", [(0, False), (240, True)])])])],
                       children=[fire_comp])
    cut = FakeTrack("MovieSceneCameraCutTrack", "Camera Cuts", [FakeSection([])])
    return FakeSeq([wave, fire], [cut])


def t_ue_fingerprint_and_x_write():
    TOOL.unreal = _fake_unreal()
    try:
        seq = _fake_seq()
        before, names = TOOL._fingerprint(T, seq)
        assert "S3.Fire.Light" in names and "S3.Fire.Visible" in names
        b, ti, _s, ci, ch, tnames = TOOL._motion_channel(T, seq, "WAVE1")
        xp = T.x_channel_path("WAVE1", ti, 0, ci)
        assert xp in before, (xp, sorted(before)[:6])
        orig = TOOL._keys(ch)
        want = T.shift_x_keys(orig, 3650.0, 6.0)
        n = TOOL._set_x_keys(T, seq, "WAVE1", want, "wave")
        assert n == len(orig)
        after, _ = TOOL._fingerprint(T, seq)
        assert T.fingerprint_diff(before, after, {xp: T.value_sha(want)}) == []       # +: only X, as planned
        assert T.fingerprint_diff(before, after, {}) != []                              # -: X change is visible
        # -: a foreign (fire, child possessable) key change is caught
        seq.bindings[1].children[0].tracks[0].sections[0].chans[0].keys[1].v = 6.0
        after2, _ = TOOL._fingerprint(T, seq)
        v = T.fingerprint_diff(before, after2, {xp: T.value_sha(want)})
        assert len(v) == 1 and "S3.Fire.Light" in v[0]["path"], v
        # -: a Y key nudge on the wave binding is caught
        seq2 = _fake_seq()
        b2, _f = TOOL._fingerprint(T, seq2)
        TOOL._set_x_keys(T, seq2, "WAVE1", want, "wave")
        seq2.bindings[0].tracks[0].sections[0].chans[1].keys[0].v += 0.01
        a2, _f = TOOL._fingerprint(T, seq2)
        assert [x["why"] for x in T.fingerprint_diff(b2, a2, {xp: T.value_sha(want)})] == ["CHANGED"]
        # -: a frame mismatch refuses the write
        try:
            TOOL._set_x_keys(T, _fake_seq(), "WAVE1", want[:-1], "wave")
            raise AssertionError("frame mismatch accepted")
        except RuntimeError as exc:
            assert "X_KEY_FRAMES" in str(exc)
        # -: a second motion track refuses
        seq3 = _fake_seq()
        seq3.bindings[0].tracks.append(FakeTrack("MovieScene3DTransformTrack", T.MOTION_TRACK, [FakeSection([])]))
        refuses(lambda: TOOL._motion_channel(T, seq3, "WAVE1"), "MOTION_TRACK")
    finally:
        TOOL.unreal = None


# ------------------------------------------------------------------------------------------------ static safety
def t_static_tool():
    full = (HERE / "s3waves_t5o.py").read_text(encoding="utf-8")
    tree = ast.parse(full)
    doc = ast.get_docstring(tree, clean=False)
    src = full.replace(doc, "") if doc else full                # code only: the docstring may NAME forbidden calls
    for node in tree.body:                                    # no unreal calls at module level
        if isinstance(node, (ast.Expr, ast.Assign)):
            assert "unreal." not in ast.unparse(node), ast.unparse(node)[:120]
    for bad in ("get_bound_objects(", "load_level(", "load_map(", "save_dirty_packages", "save_all", "build_skin",
                "replace_existing\", True", "delete_asset", "reimport", "EditorLevelLibrary.save_current_level"):
        assert bad not in src, bad
    assert "W._guard(T, world, need_clean=mode not in T.READ_ONLY)" in src     # PIE / world / Sequencer closed
    assert src.index("W._write(ORIGINALS") < src.index("_apply_ops(T, W, world, seq, plan[\"ops\"]")
    assert src.index("T.apply_scope(W._census())") < src.index("W._save(T, world, [T.ROOT_SEQ], map_expected=True)")
    req = jload(HERE / "s3waves_t5o_request.json")
    a = req["arguments"]
    assert a["toolset_name"] == "MCPBlueprintsGenerator.MCPBlueprintsGeneratorToolset"
    assert a["tool_name"] == "ExecuteProjectPythonFile"
    assert (PROJECT / "Saved" / a["arguments"]["relativeSavedPath"]).is_file()
    run = (HERE / "s3waves_t5o_run.py").read_text(encoding="utf-8")
    assert run.index('run_path("E:/PussStage/Saved/CodexConductor/purge_saved_module_cache.py")') <         run.index('run_path("E:/PussStage/Saved/CodexFlatV3/s3waves/s3waves_t5o.py")["main"]()')
    args = jload(HERE / "s3waves_t5o_args.json")
    assert args["mode"] == "DRY", "the checked-in args must be the read-only DRY"


def t_static_v3_guard_has_sequencer_check():
    src = (S3W / "s3_waves_v3_ue.py").read_text(encoding="utf-8")
    assert "get_current_level_sequence() is not None" in src and "SEQUENCER_IS_OPEN" in src
    assert "ZZ_ACTORS_PRESENT" in src and "DIRTY_SCOPE" in src


def main():
    for name, fn in [(k, v) for k, v in globals().items() if k.startswith("t_") and callable(v)]:
        check(name, fn)
    rep = {"pass": sum(r["pass"] for r in RESULTS), "fail": sum(not r["pass"] for r in RESULTS), "results": RESULTS}
    (HERE / "test_s3waves_t5o_offline_report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    for r in RESULTS:
        if not r["pass"]:
            print("FAIL", r["name"], r["error"])
    print("S3T5O_HARNESS|pass=%d|fail=%d" % (rep["pass"], rep["fail"]))
    sys.exit(1 if rep["fail"] else 0)


if __name__ == "__main__":
    main()
