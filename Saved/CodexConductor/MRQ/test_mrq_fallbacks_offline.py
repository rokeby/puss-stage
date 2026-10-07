"""Offline harness for mrq_fallbacks.py + mrq_post.py (pure Python, no unreal, no ffmpeg calls).
Run: python test_mrq_fallbacks_offline.py

Fixture (INFERRED layout; the live DRY reads the real one): Scene lengths are the 7 Oct 13:13 measured playbacks
(Saved/CodexConductor/scene_exposure_weight_read.json: S1 6176@25, S2 2025@25, S3 6240@24, S4 4890@25, S5 1225@25,
S6 5489@25); Master section starts are synthetic (ordered, with Passages between). Every gate has a passing case and a
failing control. Prints PASS/FAIL per case and a summary; exits non-zero on any failure.
"""
import ast
import copy
import json
import os
import re
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mrq_fallbacks as F  # noqa: E402
import mrq_post as P  # noqa: E402

assert F.unreal is None, "harness must run with unreal absent"
RESULTS = []

LENGTHS = {1: (6176, 25), 2: (2025, 25), 3: (6240, 24), 4: (4890, 25), 5: (1225, 25), 6: (5489, 25)}
STARTS = {1: 4818, 2: 15000, 3: 21000, 4: 33000, 5: 43000, 6: 50000}


def master_frames(n):
    f, r = LENGTHS[n]
    return int(round(f / float(r) * 25))


def fixture():
    scenes = {}
    for n in range(1, 7):
        s0 = STARTS[n]
        f, r = LENGTHS[n]
        scenes[str(n)] = {"sequence": F.SCENE_SEQ % n,
                          "master_sections": [{"track_class": "MovieSceneInfinitySceneTrack", "start": s0,
                                               "end": s0 + master_frames(n), "active": True, "play_rate": 1.0,
                                               "play_rate_read": True, "start_offset_tick": 0}],
                          "inner": {"playback": [0, f], "display_rate": [r, 1]},
                          "markers": [["S%d mark" % n, 240]], "audio": []}
    scenes["3"]["markers"] = [["InfinityStage.VampStart", 3480], ["S3 7 Finish / out", 5520]]
    return {"master": {"display_rate": [25, 1], "tick_rate": [24000, 1], "playback": [0, 60000]}, "scenes": scenes}


ARGS = {"tiers": ["P", "C"], "version": "v01", "scenes": [1, 2, 3, 4, 5, 6], "test_jobs": [{"scene": 5, "seconds": 10}]}
SCAL = {k: 3 for k in F.SCALABILITY_CVARS}


def case(name):
    def wrap(fn):
        try:
            fn()
            RESULTS.append((name, True, ""))
        except Exception as error:  # noqa: BLE001
            RESULTS.append((name, False, "%s: %s\n%s" % (type(error).__name__, error, traceback.format_exc())))
        return fn
    return wrap


def refused(plan, pat):
    return any(re.search(pat, r) for r in plan["refusals"])


@case("nominal: no refusals, 6 Scenes, 26305 Scene frames at 25 fps")
def _():
    plan = F.plan_jobs(fixture(), ARGS)
    assert plan["refusals"] == [], plan["refusals"]
    assert sorted(plan["scenes"]) == [str(n) for n in range(1, 7)]
    assert plan["totals"]["scene_frames"] == 6176 + 2025 + 6500 + 4890 + 1225 + 5489 == 26305, plan["totals"]
    assert abs(plan["totals"]["scene_seconds"] - 1052.2) < 1e-6, plan["totals"]


@case("S3: 6240 frames @24 render as 6500 Master frames @25 = 260.0 s (no frame-rate override)")
def _():
    sc = F.plan_jobs(fixture(), ARGS)["scenes"]["3"]
    assert sc["frames"] == 6500 and abs(sc["seconds"] - 260.0) < 1e-9 and sc["inner_fps"] == 24.0, sc
    assert sc["markers_video_s"][0] == ["InfinityStage.VampStart", 145.0], sc["markers_video_s"]


@case("preroll: 50 frames (S3 125) before every kept range; P job = Scene + preroll")
def _():
    plan = F.plan_jobs(fixture(), ARGS)
    for j in plan["jobs"]:
        want = 125 if j["scene"] == 3 else 50
        assert j["preroll_frames"] == want, j
        assert j["render_range"][0] == j["keep_range"][0] - want and j["render_range"][1] == j["keep_range"][1], j
    p = [j for j in plan["jobs"] if j["name"] == "S5_P_v01"][0]
    assert p["render_frames"] == 1225 + 50 and p["wav"] is True, p


@case("tier C chunks tile each Scene exactly (no gap/overlap), <= 1.25 x chunk, no WAV")
def _():
    plan = F.plan_jobs(fixture(), ARGS)
    for n in range(1, 7):
        cj = sorted([j for j in plan["jobs"] if j["scene"] == n and j["tier"] == "C" and not j.get("test")],
                    key=lambda j: j["keep_range"][0])
        s0, s1 = plan["scenes"][str(n)]["master_range"]
        assert cj[0]["keep_range"][0] == s0 and cj[-1]["keep_range"][1] == s1, (n, cj[0], cj[-1])
        for a, b in zip(cj, cj[1:]):
            assert a["keep_range"][1] == b["keep_range"][0], (a["name"], b["name"])
        assert all(j["keep_frames"] <= 1500 * 1.25 for j in cj), [j["keep_frames"] for j in cj]
        assert not any(j["wav"] for j in cj)
        assert len(set(j["output_dir"] for j in cj)) == len(cj), "chunks must not share a frames folder"


@case("audio trims are exact samples (1920 per frame at 48 kHz / 25 fps)")
def _():
    sc = F.plan_jobs(fixture(), ARGS)["scenes"]["5"]
    assert sc["audio_trim_samples"] == 96000 and sc["audio_samples"] == 1225 * 1920, sc


@case("control: non-integer samples per frame refuses")
def _():
    try:
        F.audio_samples(50, 25.0, sr=44056)
    except F.PlanError as exc:
        assert "AUDIO_SAMPLES_NOT_INTEGER" in str(exc)
        return
    raise AssertionError("no refusal")


@case("control: a Scene with no Master section is refused, the others still plan")
def _():
    fx = fixture()
    fx["scenes"]["2"]["master_sections"] = []
    plan = F.plan_jobs(fx, ARGS)
    assert refused(plan, r"^S2_MASTER_SECTIONS\|0$") and "2" not in plan["scenes"] and "3" in plan["scenes"]


@case("control: duplicate Master sections for one Scene refuse")
def _():
    fx = fixture()
    fx["scenes"]["4"]["master_sections"].append(copy.deepcopy(fx["scenes"]["4"]["master_sections"][0]))
    assert refused(F.plan_jobs(fx, ARGS), r"^S4_MASTER_SECTIONS\|2$")


@case("control: play rate 1.04 / unread play rate / start offset refuse")
def _():
    for key, val, pat in (("play_rate", 1.04, "S1_PLAY_RATE"), ("play_rate_read", False, "S1_PLAY_RATE"),
                          ("start_offset_tick", 960, "S1_START_OFFSET")):
        fx = fixture()
        fx["scenes"]["1"]["master_sections"][0][key] = val
        assert refused(F.plan_jobs(fx, ARGS), pat), key


@case("control: S3 inner rate read as 25 (length mismatch vs the Master section) refuses")
def _():
    fx = fixture()
    fx["scenes"]["3"]["inner"]["display_rate"] = [25, 1]
    assert refused(F.plan_jobs(fx, ARGS), r"^S3_LENGTH_MISMATCH")


@case("control: a 24 fps Master refuses (custom range is in Master display frames)")
def _():
    fx = fixture()
    fx["master"]["display_rate"] = [24, 1]
    assert refused(F.plan_jobs(fx, ARGS), r"^MASTER_RATE")


@case("preroll clamps at the Master start and records it")
def _():
    fx = fixture()
    fx["scenes"]["1"]["master_sections"][0]["start"] = 20
    fx["scenes"]["1"]["master_sections"][0]["end"] = 20 + 6176
    plan = F.plan_jobs(fx, ARGS)
    sc = plan["scenes"]["1"]
    assert sc["preroll_frames"] == 20 and sc["preroll_wanted"] == 50, sc
    assert [j for j in plan["jobs"] if j["name"] == "S1_P_v01"][0]["render_range"][0] == 0


@case("control: paths/version/tier gates")
def _():
    for over, pat in (({"asset_folder": "/Game/InfinityStage/X"}, "ASSET_FOLDER_NOT_ZZ_RENDER"),
                      ({"render_root": "D:/Renders"}, "RENDER_ROOT_OUTSIDE"), ({"version": "v1"}, "VERSION_FORMAT"),
                      ({"tiers": ["P", "X"]}, "UNKNOWN_TIER")):
        a = dict(ARGS, **over)
        if "X" in a.get("tiers", []):
            try:
                F.plan_jobs(fixture(), a)
            except KeyError:
                pass
            assert any(pat in r for r in F.check_paths(a)), over
        else:
            assert refused(F.plan_jobs(fixture(), a), pat), over
    assert F.check_paths(ARGS) == []


@case("split_chunks: tail merge, exact multiple, short range, empty refuses")
def _():
    assert F.split_chunks(0, 3100, 1500) == [[0, 1500], [1500, 3100]]
    assert F.split_chunks(0, 3000, 1500) == [[0, 1500], [1500, 3000]]
    assert F.split_chunks(0, 3600, 1500) == [[0, 1500], [1500, 3000], [3000, 3600]]
    assert F.split_chunks(10, 900, 1500) == [[10, 900]]
    assert F.split_chunks(0, 5000, 0) == [[0, 5000]]
    try:
        F.split_chunks(5, 5, 1500)
    except F.PlanError:
        return
    raise AssertionError("empty range not refused")


@case("settings P: DirectorHud 0 + SkyLight timeslice + 11 sg.* copied; validate passes")
def _():
    j = [j for j in F.plan_jobs(fixture(), ARGS)["jobs"] if j["name"] == "S5_P_v01"][0]
    sp = F.settings_spec(j, SCAL)
    assert F.validate_spec(sp) == [], F.validate_spec(sp)
    names = [c[0] for c in sp["cvars"]]
    assert names[:2] == ["InfinityStage.DirectorHud", "r.SkyLight.RealTimeReflectionCapture.TimeSlice"], names
    assert len(names) == 2 + len(F.SCALABILITY_CVARS)
    assert sp["output"]["custom_start_frame"] == j["render_range"][0] and sp["output"]["custom_end_frame"] == j["render_range"][1]
    assert sp["aa"]["temporal_sample_count"] == 1 and sp["wav"]["file_name_format_override"] == "PussFB_S5_P_v01_raw"


@case("settings C: TS 8 + AA none + cinematic; no WAV; validate passes")
def _():
    j = [j for j in F.plan_jobs(fixture(), ARGS)["jobs"] if j["tier"] == "C" and j["scene"] == 3][0]
    sp = F.settings_spec(j)
    assert F.validate_spec(sp) == [] and sp["aa"]["temporal_sample_count"] == 8 and sp["aa"]["aa_method"] == "AAM_NONE"
    assert sp["game"]["cinematic_quality_settings"] is True and sp["wav"] is None


@case("controls: validate_spec catches each broken invariant")
def _():
    j = [j for j in F.plan_jobs(fixture(), ARGS)["jobs"] if j["name"] == "S5_P_v01"][0]
    base = F.settings_spec(j, SCAL)
    muts = [
        (lambda s: s.__setitem__("cvars", [c for c in s["cvars"] if c[0] != "InfinityStage.DirectorHud"]), "CVAR_MISSING"),
        (lambda s: s["cvars"].__setitem__(0, ["InfinityStage.DirectorHud", 1.0]), "CVAR_MISSING"),
        (lambda s: s["output"].__setitem__("output_resolution", [3840, 2160]), "RESOLUTION"),
        (lambda s: s["output"].__setitem__("output_frame_rate", [24, 1]), "FRAME_RATE"),
        (lambda s: s["output"].__setitem__("custom_end_frame", s["output"]["custom_start_frame"]), "RANGE"),
        (lambda s: s["output"].__setitem__("file_name_format", "PussFB"), "FILE_FORMAT_NO_FRAME_TOKEN"),
        (lambda s: s["output"].__setitem__("output_directory", "C:/Temp/x"), "OUTPUT_OUTSIDE_RENDERS"),
        (lambda s: s["aa"].update(temporal_sample_count=8, aa_method=None), "TS_WITH_ENGINE_AA"),
        (lambda s: s.__setitem__("deferred_pass", False), "NO_DEFERRED_PASS"),
        (lambda s: s["game"].__setitem__("game_mode_override", "/Script/InfinityStage.InfinityStageShowGameMode"),
         "GAME_MODE_OVERRIDE_SET"),
    ]
    for mut, pat in muts:
        s = copy.deepcopy(base)
        mut(s)
        assert any(b.startswith(pat) for b in F.validate_spec(s)), (pat, F.validate_spec(s))


@case("control: tier P without editor scalability refuses (PlanError)")
def _():
    j = [j for j in F.plan_jobs(fixture(), ARGS)["jobs"] if j["name"] == "S5_P_v01"][0]
    for scal in (None, {k: 3 for k in F.SCALABILITY_CVARS[:-1]}):
        try:
            F.settings_spec(j, scal)
        except F.PlanError:
            continue
        raise AssertionError("no refusal for %s" % scal)


@case("command line: -game, Master object path, config object path, MRQ process args, quoted exe")
def _():
    j = [j for j in F.plan_jobs(fixture(), ARGS)["jobs"] if j["name"] == "S5_P_v01"][0]
    argv = F.command_line(j)
    s = F.quote_argv(argv)
    assert argv[0].endswith("UnrealEditor-Cmd.exe") and argv[2] == F.MAP and "-game" in argv
    assert '-LevelSequence="/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master.LS_InfinityStage_V1Master"' in argv
    assert '-MoviePipelineConfig="/Game/ZZ_Render/MRQFallbacks/MRQC_FB_S5_P_v01.MRQC_FB_S5_P_v01"' in argv
    for need in ("-deterministicaudio", "-audiomixer", "-MRQInstance", "-Unattended", "-NoLoadingScreen"):
        assert need in argv, need
    assert s.startswith('"D:\\Unreal Engine\\UE_5.8\\Engine\\Binaries\\Win64\\UnrealEditor-Cmd.exe" '), s[:80]
    toks = re.findall(r'"[^"]*"|\S+', s)
    assert all(" " not in t or t.startswith('"') or '="' in t for t in toks), toks


@case("test jobs: S5 first 10 s = 250 kept + 50 preroll, WAV on both tiers; control: too long refuses")
def _():
    plan = F.plan_jobs(fixture(), ARGS)
    t = [j for j in plan["jobs"] if j.get("test")]
    assert sorted(j["name"] for j in t) == ["S5_C_v01_t10", "S5_P_v01_t10"], [j["name"] for j in t]
    for j in t:
        assert j["keep_frames"] == 250 and j["render_frames"] == 300 and j["wav"] and j["output_dir"].endswith("_t10/frames")
    bad = F.plan_jobs(fixture(), dict(ARGS, test_jobs=[{"scene": 5, "seconds": 60}]))
    assert refused(bad, r"^TEST_LENGTH\|S5")
    names = [j["name"] for j in plan["jobs"]]
    assert len(names) == len(set(names))


@case("gates: ShowRoot autoplay / legacy camera curtain refuse; clocked actors / adaptive PPV / active click warn; controls quiet")
def _():
    fx = fixture()
    plan = F.plan_jobs(fx, ARGS)
    fx.update({"show_cues": [{"label": "Opening", "type": "InfinityCueType.SEQUENCE", "curtain_mode": "OPENING_REVEAL",
                              "sequence_owns_curtain": True},
                             {"label": "Passage 1", "type": "InfinityCueType.WING_PAIR", "curtain_mode": "OPENING_REVEAL",
                              "sequence_owns_curtain": False},
                             {"label": "Scene 3", "type": "InfinityCueType.SCENE", "curtain_mode": "NONE",
                              "sequence_owns_curtain": False}],
               "show_root": {"count": 1, "auto_play": False, "master_sequence": F.MASTER},
               "mrq_classes": {"MoviePipelineWaveOutput": True},
               "clocked_actors": [{"class": "InfinityStageStrobeLight", "label": "P04 Strobe", "segments": [["g", "Passage 4"]]}],
               "ppvs": [{"label": "pinned", "enabled": True, "override_auto_exposure_min_brightness": True,
                         "auto_exposure_min_brightness": -3.0, "auto_exposure_max_brightness": -3.0}]})
    fx["scenes"]["1"]["audio"] = [{"sound": "/Game/KK_S1_Animals/Animals_Project_CLICK.Animals_Project_CLICK",
                                   "section_active": False, "track_eval_disabled": False}]
    r, w = F.gates(fx, plan)
    assert r == [] and w == [], (r, w)
    fx2 = copy.deepcopy(fx)
    fx2["show_root"]["auto_play"] = True
    fx2["clocked_actors"].append({"class": "InfinityStageSweepLight", "label": "S3 sweep", "segments": [["g", "Scene 3 Shore"]]})
    fx2["clocked_actors"].append({"class": "InfinityStageSweepLight", "label": "all", "segments": []})
    fx2["ppvs"][0]["auto_exposure_max_brightness"] = 2.0
    fx2["scenes"]["1"]["audio"][0]["section_active"] = True
    fx2["mrq_classes"]["MoviePipelineWaveOutput"] = False
    r2, w2 = F.gates(fx2, plan)
    assert any(x.startswith("SHOW_ROOT_AUTOPLAY") for x in r2) and "NO_WAVE_OUTPUT_CLASS" in r2, r2
    assert sum(1 for x in w2 if x.startswith("TRANSPORT_CLOCKED_ACTOR")) == 2, w2
    assert any(x.startswith("PPV_ADAPTIVE_EXPOSURE") for x in w2) and any(x.startswith("CLICK_TRACK_ACTIVE") for x in w2), w2
    fx3 = copy.deepcopy(fx)
    fx3["show_root"] = {"count": 2}
    assert any(x.startswith("SHOW_ROOTS") for x in F.gates(fx3, plan)[0])
    fx4 = copy.deepcopy(fx)
    fx4["show_cues"][0]["sequence_owns_curtain"] = False      # control: a camera-following legacy curtain
    assert any(x.startswith("LEGACY_CAMERA_CURTAIN|Opening") for x in F.gates(fx4, plan)[0]), F.gates(fx4, plan)[0]
    fx5 = copy.deepcopy(fx)
    fx5["show_cues"][2] = {"label": "Scene 3", "type": "InfinityCueType.SCENE", "curtain_err": "x"}
    assert any(x.startswith("CUE_CURTAIN_UNREAD") for x in F.gates(fx5, plan)[0])
    fx6 = copy.deepcopy(fx)
    del fx6["show_cues"]
    assert "SHOW_CUES_UNREAD" in F.gates(fx6, plan)[1]


def built_fixture():
    plan = F.plan_jobs(fixture(), ARGS)
    return {"built": plan["jobs"], "scenes": plan["scenes"]}


@case("post: scene_jobs tiles P and C; frame_map length = Scene frames; png names zero-padded 6")
def _():
    b = built_fixture()
    for tier in ("P", "C"):
        rows = P.scene_jobs(b, 3, tier, "v01")
        fm = P.frame_map(rows)
        assert len(fm) == 6500 and fm[0][3] == STARTS[3] and fm[-1][3] == STARTS[3] + 6499, (tier, len(fm))
    j = P.scene_jobs(b, 5, "P", "v01")[0]
    assert P.png_name(j, 43000).endswith("/frames/PussFB_S5_P_v01.043000.png"), P.png_name(j, 43000)
    t = P.scene_jobs(b, 5, "P", "v01", test=10)
    assert len(t) == 1 and len(P.frame_map(t)) == 250


@case("post control: a chunk gap / missing chunk is refused")
def _():
    b = built_fixture()
    b2 = copy.deepcopy(b)
    c = [j for j in b2["built"] if j["scene"] == 1 and j["tier"] == "C"]
    c[1]["keep_range"][0] += 1
    try:
        P.scene_jobs(b2, 1, "C", "v01")
    except P.PostError as exc:
        assert "CHUNK_GAP" in str(exc)
    else:
        raise AssertionError("gap not refused")
    b3 = copy.deepcopy(b)
    b3["built"] = [j for j in b3["built"] if not (j["scene"] == 1 and j["tier"] == "C" and j["chunk"] == 0)]
    try:
        P.scene_jobs(b3, 1, "C", "v01")
    except P.PostError as exc:
        assert "DO_NOT_COVER" in str(exc)
    else:
        raise AssertionError("missing first chunk not refused")


@case("post: audio trim from the P WAV for a C deliverable; control: uncovered range refuses")
def _():
    b = built_fixture()
    pj = P.scene_jobs(b, 3, "P", "v01")[0]
    s0, s1 = b["scenes"]["3"]["master_range"]
    assert P.audio_trim(pj, [s0, s1]) == (125 * 1920, 6500 * 1920)
    try:
        P.audio_trim(pj, [s0 - 200, s1])
    except P.PostError:
        return
    raise AssertionError("uncovered audio range not refused")


@case("post: ffmpeg argument lists (start number, frame count, keyframe every 25, exact atrim)")
def _():
    v = P.ffmpeg_video_args("ffmpeg", "x.%06d.png", 43000, 1225, "o.mp4")
    assert v[v.index("-start_number") + 1] == "43000" and v[v.index("-frames:v") + 1] == "1225"
    assert "keyint=25:min-keyint=25:scenecut=0" in v and "-an" in v and v[v.index("-r") + 1] == "25"
    a = P.ffmpeg_audio_args("ffmpeg", "raw.wav", 96000, 1225 * 1920, "o.wav")
    assert "atrim=start_sample=96000:end_sample=%d,asetpts=PTS-STARTPTS" % (96000 + 1225 * 1920) in a


@case("post QC: black stretch, luma jump, washed share; controls")
def _():
    y = [16.0] * 30 + [80.0] * 100 + [210.0] * 10 + [80.0] * 10
    f = P.luma_findings(y)
    assert f["black_stretches_s"] == [[0.0, 1.2]] and f["first_frame_black"], f
    assert f["luma_jump_count"] == 3 and abs(f["washed_share"] - 10 / 150.0) < 1e-3, f
    g = P.luma_findings([16.0] * 10 + [80.0] * 50)
    assert g["black_stretches_s"] == [] and g["luma_jump_count"] == 1, g
    txt = "frame:0\nlavfi.signalstats.YAVG=16.2\nframe:1\nlavfi.signalstats.YAVG=99.5\n"
    assert P.parse_signalstats(txt) == [16.2, 99.5]


@case("post: hard checks pass at exact length, fail at +2 frames / short audio")
def _():
    assert P.hard_checks(1225, 1225, 49.0, 49.0) == []
    assert P.hard_checks(1225, 1227, 49.08, 49.0)[0].startswith("FRAME_COUNT")
    assert any(x.startswith("AUDIO_LENGTH") for x in P.hard_checks(1225, 1225, 49.0, 48.5))


@case("post: stale_diff flags changed and missing files only")
def _():
    man = [{"file": "a", "sha256": "1"}, {"file": "b", "sha256": "2"}, {"file": "c", "sha256": "3"}]
    assert P.stale_diff(man, {"a": "1", "b": "9", "c": None}) == [["CHANGED", "b"], ["MISSING", "c"]]
    assert P.stale_diff(man, {"a": "1", "b": "2", "c": "3"}) == []


@case("static: no crash-pattern / write calls the tool must never make")
def _():
    src = open(os.path.join(HERE, "mrq_fallbacks.py"), encoding="utf-8").read()
    for bad in ("get_bound_objects", "reload_packages", "save_current_level", "save_dirty_packages", "save_map",
                "request_end_play", "end_play_map", "quit_editor", "delete_asset", "delete_directory", "SaveAll"):
        assert bad not in src, bad
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            assert "unreal." not in ast.unparse(node), "UE object at module level: %s" % ast.unparse(node)[:80]
    run = open(os.path.join(HERE, "mrq_fallbacks_run.py"), encoding="utf-8").read()
    assert "purge_saved_module_cache.py" in run and "MRQFB_ARGS" in run


@case("static: launcher is ASCII, never deletes, renames aside, asserts frames from disk")
def _():
    ps = open(os.path.join(HERE, "mrq_render.ps1"), "rb").read()
    assert all(b < 128 for b in ps), "non-ASCII byte in ps1 (PS 5.1 reads BOM-less files as ANSI)"
    s = ps.decode("ascii")
    assert "Remove-Item" not in s and "Rename-Item" in s and "UnrealEditor-Cmd" in s and "blender" in s
    assert "MRQFB_RENDER_OK" in s and "frames_wanted" in s and "MASTER_CHANGED_SINCE_BUILD" in s
    post = open(os.path.join(HERE, "mrq_post.py"), encoding="utf-8").read()
    assert "os.remove" not in post and "rmtree" not in post and "unlink" not in post


@case("args file: mode DRY, both tiers, the S5 10 s test job")
def _():
    a = json.load(open(os.path.join(HERE, "mrq_fallbacks_args.json"), encoding="utf-8"))
    assert a["mode"] == "DRY" and a["tiers"] == ["P", "C"] and a["test_jobs"] == [{"scene": 5, "seconds": 10}]
    req = json.load(open(os.path.join(HERE, "mrq_fallbacks_request.json"), encoding="utf-8"))
    assert req["arguments"]["arguments"]["relativeSavedPath"] == "CodexConductor/MRQ/mrq_fallbacks_run.py"


if __name__ == "__main__":
    ok = sum(1 for r in RESULTS if r[1])
    for name, passed, detail in RESULTS:
        print("%s  %s" % ("PASS" if passed else "FAIL", name))
        if not passed:
            print(detail)
    plan = F.plan_jobs(fixture(), ARGS)
    print("fixture totals:", json.dumps(plan["totals"]))
    print("SUMMARY %d/%d" % (ok, len(RESULTS)))
    sys.exit(0 if ok == len(RESULTS) else 1)
