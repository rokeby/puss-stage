"""MRQ video fallbacks for Scenes S1-S6 (7 Oct 2026, offline-written, NOT RUN in Unreal).

Plan: Docs/Conductor/MRQ_VIDEO_FALLBACKS_PLAN_2026-10-07.md. Gary 7 Oct: "those scenes as videos ready to trigger",
deadline Sun 11 Oct lunchtime; one clip per Scene, 1920x1080 @ 25 fps, a SEPARATE WAV per Scene.

DESIGN (why it renders the MASTER, not LS_DevScene_0N):
  - S3's root has a Cinematic Shot track (Shots [-1, 1454), s3_narration_remove_record.json). MRQ treats a top-level
    shot track as its shot list, so a direct render of LS_DevScene_03 risks covering only that shot [inf: MRQ shot
    semantics, not verifiable from 5.8 headers]. The Master's Scene track is a plain UMovieSceneSubTrack subclass
    (MovieSceneInfinitySceneTrack.h) [decl], so through the Master every Scene renders as one continuous range.
  - The live show plays every Scene THROUGH the 25 fps Master; S3 (authored 24 fps) is resampled by the sub-section
    exactly as it is live. Rendering the Master at 25 fps reproduces that timing, with no frame-rate override.
  - Each job renders [scene_start - preroll, scene_end) on the Master. The preroll frames (the end of the preceding
    Passage) let the Passage track's per-frame hooks run as live (camera rig, Arrival pre-drives
    MovieSceneInfinityPassageTrack.cpp:241-245 [decl]), keep GeometryCache decode continuous (stale-frame trap), and warm
    Lumen/VSM/TSR/Niagara/cloth. mrq_post.py drops them; the WAV is trimmed by the same sample count.

MODES (args mrq_fallbacks_args.json, runner mrq_fallbacks_run.py, request mrq_fallbacks_request.json):
  PLAN        offline only (python mrq_fallbacks.py PLAN [facts.json]): jobs from a facts file. No unreal.
  SURVEY      READ-ONLY in the editor: Master scene sections, Scene sequences, markers, audio (depth 4), transport-clocked
              actors (strobe/sweep), PPV exposure modes, streaming levels, ShowRoot flags, editor scalability, MRQ
              classes. Plain property reads only (never a SequencerTools bound-object query; memory crash #5).
              Census before == after is ASSERTED. Writes mrq_survey_<run>.json.  Marker MRQFB_SURVEY_OK|run=..
  DRY         SURVEY + plan_jobs + gates + a TRANSIENT config probe per tier (real setters + read-back, no package)
              -> mrq_dry_<run>.json (jobs, command lines, estimates). No asset/level writes; census asserted.
              Marker MRQFB_DRY_OK|run=..|jobs=..
  BUILD       CREATE-ONLY: one MoviePipelinePrimaryConfig per job under ASSET_FOLDER (refuses if ANY target exists;
              all-or-nothing preflight). confirm "BUILD MRQFB" + decided_by. Saves only the new config packages,
              reads every setting back, asserts census after == census before. Writes mrq_jobs_built_<run>.json and
              mrq_jobs_built.json (the launcher's input). Marker MRQFB_BUILD_OK|run=..|configs=..
  RENDER_PIE  NOT RECOMMENDED (in-editor PIE executor; editor memory + Cue Desk PIE hook). confirm "RENDER_PIE MRQFB",
              cue_desk_closed_ack true, no PIE active, census clean. Starts a TRANSIENT queue (the user's MRQ queue
              is not touched). Marker MRQFB_RENDER_PIE_STARTED|run=..  Completion = frame count on disk (mrq_post.py).
  The PREFERRED render is the command line, editor CLOSED: mrq_render.ps1 (reads mrq_jobs_built.json).

Never stops PIE, never quits the editor, never saves a level, never touches the Show/Master/Scene sequences.
Markers: MRQFB_<MODE>_OK|run=..  MRQFB_STOPPED|run=..|reason=..
"""
import datetime
import json
import os
import re
import sys

try:
    import unreal
except ImportError:  # offline harness / PLAN
    unreal = None

TOOL = "mrq_fallbacks"
MARK = "MRQFB"
HERE = os.path.dirname(os.path.abspath(__file__))

PROJECT_DIR = "E:/PussStage"
UPROJECT = PROJECT_DIR + "/PussStage.uproject"
EDITOR_CMD = "D:/Unreal Engine/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe"
MAP = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
SCENE_SEQ = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_%02d"
ASSET_FOLDER = "/Game/ZZ_Render/MRQFallbacks"
RENDER_ROOT = "E:/PussStage/Renders/Fallbacks"
SCENES = (1, 2, 3, 4, 5, 6)
OUTPUT_FPS = (25, 1)
RESOLUTION = (1920, 1080)
AUDIO_SR = 48000                      # Config/DefaultEngine.ini AudioSampleRate=48000 [decl]
DEFAULT_PREROLL = 50                  # 2.0 s of the preceding Passage
PREROLL_BY_SCENE = {3: 125}           # S3: 5 s (live Chaos sack cloth + waves foam need settling) [inf]
MIN_TAIL_FRACTION = 0.25              # a last chunk shorter than this x chunk_frames merges into the previous one
# The arguments MRQ's own new-process executor adds (binary-proven: UTF-16 literal in
# UnrealEditor-MovieRenderPipelineCore.dll, read 7 Oct). -deterministicaudio is what makes the .wav output valid.
MRQ_PROCESS_ARGS = ["-NoLoadingScreen", "-FixedSeed", "-log", "-Unattended", "-MRQInstance", "-deterministicaudio",
                    "-audiomixer", "-AudioCallbackBufferFrameSize=32", "-AudioNumBuffersToEnqueue=2"]
WINDOW_ARGS = ["-windowed", "-ResX=1280", "-ResY=720", "-nosplash", "-stdout", "-FullStdOutLogOutput"]
# Console variables applied in EVERY tier (names binary-proven in the installed DLLs, 7 Oct):
#  InfinityStage.DirectorHud: -1 auto = ON in PIE (InfinityStageDirectorHud.cpp:28-32 [decl]) -> force off.
#  r.SkyLight.RealTimeReflectionCapture.TimeSlice: her streamed levels bring SkyLights (conductor log, probe_sky);
#  time-sliced recapture lags a level becoming visible by several frames [inf] -> capture every frame.
BASE_CVARS = (("InfinityStage.DirectorHud", 0.0), ("r.SkyLight.RealTimeReflectionCapture.TimeSlice", 0.0))
SCALABILITY_CVARS = ("sg.ResolutionQuality", "sg.ViewDistanceQuality", "sg.AntiAliasingQuality", "sg.ShadowQuality",
                     "sg.GlobalIlluminationQuality", "sg.ReflectionQuality", "sg.PostProcessQuality",
                     "sg.TextureQuality", "sg.EffectsQuality", "sg.FoliageQuality", "sg.ShadingQuality")
TIERS = {
    # P = "PIE-match": what the live show draws (TSR, project scalability copied from the editor), fast. The safety net.
    "P": {"label": "PIE-match", "temporal_samples": 1, "spatial_samples": 1, "override_aa": False, "aa_method": None,
          "render_warmup": 16, "engine_warmup": 0, "render_warmup_frames": True, "cinematic_quality": False,
          "high_quality_shadows": False, "use_lod_zero": False, "copy_editor_scalability": True,
          "chunk_frames": 0, "wav": True, "est_s_per_frame": (0.15, 0.4, 1.0)},
    # C = "Cinematic": MRQ accumulation AA (8 temporal samples), cinematic scalability. Chunked so a crash costs one
    # chunk. Video only: the Scene's audio master is the P render's WAV (same Master range, same clock).
    "C": {"label": "Cinematic", "temporal_samples": 8, "spatial_samples": 1, "override_aa": True, "aa_method": "AAM_NONE",
          "render_warmup": 8, "engine_warmup": 0, "render_warmup_frames": True, "cinematic_quality": True,
          "high_quality_shadows": True, "use_lod_zero": True, "copy_editor_scalability": False,
          "chunk_frames": 1500, "wav": False, "est_s_per_frame": (1.0, 2.0, 4.0)},
}
PNG_MB_PER_FRAME = 3.5                # 1080p 8-bit RGB PNG, conservative [inf]
_RUN = [None]


class PlanError(Exception):
    pass


# ---------------------------------------------------------------------------------------------------------------- pure
def rate(fr):
    """(num, den) or {"numerator", "denominator"} -> float fps."""
    if isinstance(fr, dict):
        return float(fr["numerator"]) / float(fr["denominator"])
    return float(fr[0]) / float(fr[1])


def preroll_for(n, args):
    table = dict(PREROLL_BY_SCENE)
    for k, v in (args.get("preroll_by_scene") or {}).items():
        table[int(k)] = int(v)
    return int(table.get(int(n), int(args.get("preroll_frames", DEFAULT_PREROLL))))


def split_chunks(start, end, chunk_frames, min_tail_fraction=MIN_TAIL_FRACTION):
    """[start, end) -> contiguous [a, b) pieces of <= chunk_frames; a short tail merges into the previous piece."""
    if end <= start:
        raise PlanError("EMPTY_RANGE|%d|%d" % (start, end))
    if not chunk_frames or chunk_frames <= 0 or end - start <= chunk_frames:
        return [[start, end]]
    pieces = []
    a = start
    while a < end:
        b = min(a + chunk_frames, end)
        pieces.append([a, b])
        a = b
    if len(pieces) > 1 and (pieces[-1][1] - pieces[-1][0]) < chunk_frames * min_tail_fraction:
        tail = pieces.pop()
        pieces[-1][1] = tail[1]
    return pieces


def audio_samples(frames, fps, sr=AUDIO_SR):
    """Exact sample count for a whole number of frames; refuses a non-integer (a trim would drift)."""
    per = sr / float(fps)
    if abs(per - round(per)) > 1e-9:          # per-FRAME integrality: any chunk/trim boundary must land on a sample
        raise PlanError("AUDIO_SAMPLES_NOT_INTEGER|frames=%d|fps=%s|sr=%d" % (frames, fps, sr))
    return int(frames) * int(round(per))


def check_scene(n, sf, master):
    """Gates for one Scene's facts. Returns a list of refusal strings (empty = OK)."""
    bad = []
    secs = sf.get("master_sections") or []
    if len(secs) != 1:
        return ["S%d_MASTER_SECTIONS|%d" % (n, len(secs))]
    s = secs[0]
    if not s.get("active", True):
        bad.append("S%d_SECTION_INACTIVE" % n)
    if abs(float(s.get("play_rate", 1.0)) - 1.0) > 1e-9 or not s.get("play_rate_read", True):
        bad.append("S%d_PLAY_RATE|%s" % (n, s.get("play_rate")))
    if int(s.get("start_offset_tick", 0)) != 0:
        bad.append("S%d_START_OFFSET|%s" % (n, s.get("start_offset_tick")))
    inner = sf.get("inner") or {}
    if not inner.get("playback") or not inner.get("display_rate"):
        bad.append("S%d_NO_INNER" % n)
        return bad
    if int(inner["playback"][0]) != 0:
        bad.append("S%d_INNER_START|%s" % (n, inner["playback"][0]))
    m_fps = rate(master["display_rate"])
    inner_s = (int(inner["playback"][1]) - int(inner["playback"][0])) / rate(inner["display_rate"])
    outer_s = (int(s["end"]) - int(s["start"])) / m_fps
    if abs(inner_s - outer_s) > 1.0 / m_fps + 1e-9:
        bad.append("S%d_LENGTH_MISMATCH|inner_s=%.4f|master_s=%.4f" % (n, inner_s, outer_s))
    if int(s["start"]) < int(master["playback"][0]) or int(s["end"]) > int(master["playback"][1]):
        bad.append("S%d_OUTSIDE_MASTER_PLAYBACK" % n)
    return bad


def job_name(n, tier, version, chunk=None):
    base = "S%d_%s_%s" % (n, tier, version)
    return base if chunk is None else "%s_k%02d" % (base, chunk)


def check_paths(args):
    bad = []
    folder = args.get("asset_folder", ASSET_FOLDER)
    if not folder.startswith("/Game/ZZ_Render/"):
        bad.append("ASSET_FOLDER_NOT_ZZ_RENDER|%s" % folder)
    root = args.get("render_root", RENDER_ROOT).replace("\\", "/")
    if not root.lower().startswith((PROJECT_DIR + "/Renders/").lower()):
        bad.append("RENDER_ROOT_OUTSIDE_PROJECT_RENDERS|%s" % root)
    if not re.match(r"^v\d{2}$", str(args.get("version", "v01"))):
        bad.append("VERSION_FORMAT|%s" % args.get("version"))
    for t in args.get("tiers", ["P"]):
        if t not in TIERS:
            bad.append("UNKNOWN_TIER|%s" % t)
    return bad


def plan_jobs(facts, args):
    """facts (SURVEY shape) + args -> {"jobs", "refusals", "scenes", "totals"}. Pure; the harness drives it."""
    refusals = list(check_paths(args))
    master = facts["master"]
    m_fps = rate(master["display_rate"])
    if abs(m_fps - rate(OUTPUT_FPS)) > 1e-9:
        refusals.append("MASTER_RATE|%s (output is 25 fps; the custom range is in Master display frames)" % m_fps)
    version = str(args.get("version", "v01"))
    root = args.get("render_root", RENDER_ROOT).replace("\\", "/")
    folder = args.get("asset_folder", ASSET_FOLDER)
    tiers = list(args.get("tiers", ["P"]))
    jobs, scenes = [], {}
    for n in [int(x) for x in args.get("scenes", SCENES)]:
        sf = (facts.get("scenes") or {}).get(str(n))
        if sf is None:
            refusals.append("S%d_NO_FACTS" % n)
            continue
        bad = check_scene(n, sf, master)
        if bad:
            refusals.extend(bad)
            continue
        sec = sf["master_sections"][0]
        s0, s1 = int(sec["start"]), int(sec["end"])
        want_pre = preroll_for(n, args)
        pre = min(want_pre, s0 - int(master["playback"][0]))
        inner = sf["inner"]
        scenes[str(n)] = {
            "scene": n, "sequence": sf.get("sequence", SCENE_SEQ % n), "master_range": [s0, s1],
            "frames": s1 - s0, "seconds": (s1 - s0) / m_fps, "preroll_frames": pre, "preroll_wanted": want_pre,
            "inner_playback": inner["playback"], "inner_fps": rate(inner["display_rate"]),
            "audio_trim_samples": audio_samples(pre, m_fps), "audio_samples": audio_samples(s1 - s0, m_fps),
            "markers_video_s": [[mk[0], round(float(mk[1]) / rate(inner["display_rate"]), 4)]
                                for mk in (sf.get("markers") or [])],
        }
        for tier in tiers:
            spec = TIERS[tier]
            for k, (a, b) in enumerate(split_chunks(s0, s1, int(spec["chunk_frames"]))):
                chunked = spec["chunk_frames"] > 0 and (s1 - s0) > spec["chunk_frames"]
                kk = k if chunked else None
                cpre = min(want_pre, a - int(master["playback"][0]))
                name = job_name(n, tier, version, kk)
                out_dir = "%s/S%d/%s_%s/%s" % (root, n, tier, version, "frames" if kk is None else "frames_k%02d" % kk)
                jobs.append({
                    "name": name, "scene": n, "tier": tier, "version": version, "chunk": kk,
                    "config_asset": "%s/MRQC_FB_%s" % (folder, name),
                    "keep_range": [a, b], "render_range": [a - cpre, b], "preroll_frames": cpre,
                    "render_frames": b - (a - cpre), "keep_frames": b - a,
                    "output_dir": out_dir,
                    "file_name_format": "PussFB_%s.{frame_number}" % name,
                    "wav": bool(spec["wav"]) and kk is None,
                    "wav_name": "PussFB_%s_raw" % name,
                    "est_hours": [round((b - (a - cpre)) * x / 3600.0, 2) for x in spec["est_s_per_frame"]],
                    "est_disk_gb": round((b - (a - cpre)) * PNG_MB_PER_FRAME / 1024.0, 1),
                })
    for tj in args.get("test_jobs") or []:
        n, secs_req = int(tj["scene"]), float(tj["seconds"])
        sc = scenes.get(str(n))
        if sc is None:
            refusals.append("TEST_SCENE_NOT_PLANNED|S%d" % n)
            continue
        s0, s1 = sc["master_range"]
        keep = int(round(secs_req * m_fps))
        if keep <= 0 or keep > s1 - s0:
            refusals.append("TEST_LENGTH|S%d|%d" % (n, keep))
            continue
        pre = sc["preroll_frames"]
        for tier in tiers:
            spec = TIERS[tier]
            name = "%s_t%d" % (job_name(n, tier, version), int(secs_req))
            jobs.append({
                "name": name, "scene": n, "tier": tier, "version": version, "chunk": None, "test": True,
                "config_asset": "%s/MRQC_FB_%s" % (folder, name),
                "keep_range": [s0, s0 + keep], "render_range": [s0 - pre, s0 + keep], "preroll_frames": pre,
                "render_frames": keep + pre, "keep_frames": keep,
                "output_dir": "%s/S%d/%s_%s_t%d/frames" % (root, n, tier, version, int(secs_req)),
                "file_name_format": "PussFB_%s.{frame_number}" % name, "wav": True,
                "wav_name": "PussFB_%s_raw" % name,
                "est_hours": [round((keep + pre) * x / 3600.0, 2) for x in spec["est_s_per_frame"]],
                "est_disk_gb": round((keep + pre) * PNG_MB_PER_FRAME / 1024.0, 1),
            })
    names = [j["name"] for j in jobs]
    if len(set(names)) != len(names):
        refusals.append("DUPLICATE_JOB_NAMES")
    totals = {"scene_frames": sum(v["frames"] for v in scenes.values()),
              "scene_seconds": round(sum(v["seconds"] for v in scenes.values()), 3),
              "render_frames": {t: sum(j["render_frames"] for j in jobs if j["tier"] == t) for t in tiers},
              "est_hours": {t: [round(sum(j["est_hours"][i] for j in jobs if j["tier"] == t), 2) for i in range(3)]
                            for t in tiers},
              "est_disk_gb": {t: round(sum(j["est_disk_gb"] for j in jobs if j["tier"] == t), 1) for t in tiers}}
    return {"jobs": jobs, "refusals": refusals, "scenes": scenes, "totals": totals}


def settings_spec(job, scalability=None):
    """The exact MRQ settings for one job (pure). BUILD applies this and reads every entry back."""
    t = TIERS[job["tier"]]
    a, b = job["render_range"]
    cvars = [list(c) for c in BASE_CVARS]
    if t["copy_editor_scalability"]:
        if not scalability:
            raise PlanError("NO_EDITOR_SCALABILITY (tier P copies the editor's sg.* so -game matches PIE)")
        for name in SCALABILITY_CVARS:
            if name not in scalability:
                raise PlanError("SCALABILITY_MISSING|%s" % name)
            cvars.append([name, float(scalability[name])])
    spec = {
        "output": {"output_directory": job["output_dir"], "file_name_format": job["file_name_format"],
                   "output_resolution": list(RESOLUTION), "use_custom_frame_rate": True,
                   "output_frame_rate": list(OUTPUT_FPS), "override_existing_output": True,
                   "use_custom_playback_range": True, "custom_start_frame": int(a), "custom_end_frame": int(b),
                   "zero_pad_frame_numbers": 6, "auto_version": False, "handle_frame_count": 0,
                   "output_frame_step": 1},
        "aa": {"spatial_sample_count": t["spatial_samples"], "temporal_sample_count": t["temporal_samples"],
               "override_anti_aliasing": t["override_aa"], "aa_method": t["aa_method"],
               "render_warm_up_count": t["render_warmup"], "engine_warm_up_count": t["engine_warmup"],
               "use_camera_cut_for_warm_up": False, "render_warm_up_frames": t["render_warmup_frames"]},
        "game": {"cinematic_quality_settings": t["cinematic_quality"], "use_high_quality_shadows":
                 t["high_quality_shadows"], "use_lod_zero": t["use_lod_zero"], "flush_streaming_managers": True,
                 "texture_streaming": "FULLY_LOAD", "game_mode_override": None},
        "cvars": cvars,
        "png": {"write_alpha": False},
        "wav": {"file_name_format_override": job["wav_name"]} if job["wav"] else None,
        "deferred_pass": True,
    }
    return spec


def validate_spec(spec):
    """Invariants every config must hold (the harness's negative controls break each one)."""
    bad = []
    names = [c[0] for c in spec["cvars"]]
    for need, val in BASE_CVARS:
        if need not in names or [c for c in spec["cvars"] if c[0] == need][0][1] != val:
            bad.append("CVAR_MISSING|%s" % need)
    o = spec["output"]
    if o["output_resolution"] != list(RESOLUTION):
        bad.append("RESOLUTION|%s" % o["output_resolution"])
    if o["output_frame_rate"] != list(OUTPUT_FPS) or not o["use_custom_frame_rate"]:
        bad.append("FRAME_RATE")
    if not o["use_custom_playback_range"] or o["custom_end_frame"] <= o["custom_start_frame"]:
        bad.append("RANGE")
    if "{frame_number}" not in o["file_name_format"]:
        bad.append("FILE_FORMAT_NO_FRAME_TOKEN")
    if not o["output_directory"].replace("\\", "/").lower().startswith((PROJECT_DIR + "/Renders/").lower()):
        bad.append("OUTPUT_OUTSIDE_RENDERS")
    if spec["aa"]["temporal_sample_count"] > 1 and spec["aa"]["aa_method"] != "AAM_NONE":
        bad.append("TS_WITH_ENGINE_AA")
    if not spec["deferred_pass"]:
        bad.append("NO_DEFERRED_PASS")
    if spec["game"]["game_mode_override"] is not None:
        bad.append("GAME_MODE_OVERRIDE_SET (keep MRQ's AMoviePipelineGameMode: no HUD/pawn/input)")
    return bad


def win(p):
    return p.replace("/", "\\")


def command_line(job, args=None):
    """argv list for one job: editor CLOSED, one render at a time. Form A: -LevelSequence=<Master> + config."""
    args = args or {}
    master = args.get("master", MASTER)
    seq_obj = "%s.%s" % (master, master.rsplit("/", 1)[1])
    cfg = job["config_asset"]
    cfg_obj = "%s.%s" % (cfg, cfg.rsplit("/", 1)[1])
    log = "%s/S%d/%s_%s/logs/%s.log" % (args.get("render_root", RENDER_ROOT), job["scene"], job["tier"],
                                         job["version"], job["name"])
    argv = [win(args.get("editor_cmd", EDITOR_CMD)), win(args.get("uproject", UPROJECT)), args.get("map", MAP), "-game",
            '-LevelSequence="%s"' % seq_obj, '-MoviePipelineConfig="%s"' % cfg_obj] + MRQ_PROCESS_ARGS + WINDOW_ARGS + \
        ['-abslog="%s"' % win(log)]
    return argv


def quote_argv(argv):
    out = []
    for a in argv:
        out.append('"%s"' % a if (" " in a and not a.startswith("-")) else a)
    return " ".join(out)


# -------------------------------------------------------------------------------------------------------------- unreal
def _log(msg):
    if unreal:
        unreal.log(msg)
    else:
        print(msg)


def _stop(reason):
    if unreal:
        unreal.log_error("%s_STOPPED|run=%s|reason=%s" % (MARK, _RUN[0], reason))
    raise RuntimeError(reason)


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return sorted(p.get_path_name().split(".")[0] for p in
                  list(lib.get_dirty_content_packages()) + list(lib.get_dirty_map_packages()))


def _pie_active():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None


def _editor_world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


def _gs(g):
    return unreal.GuidLibrary.conv_guid_to_string(g)


def _fr(fr):
    return [int(fr.numerator), int(fr.denominator)]


def _try(obj, *names):
    for nm in names:
        try:
            return obj.get_editor_property(nm), nm
        except Exception:  # noqa: BLE001
            continue
    return None, None


def _play_rate(sec):
    p = sec.get_editor_property("parameters")      # prec s4_hangar_hold.py:320-331 (5.8 time-warp struct)
    try:
        ts = p.get_editor_property("time_scale")
        r = float(ts) if isinstance(ts, (int, float)) else float(ts.get_editor_property("play_rate"))
        ok = True
    except Exception:  # noqa: BLE001
        r, ok = 1.0, False
    try:
        off = int(p.get_editor_property("start_frame_offset").value)
    except Exception:  # noqa: BLE001
        off = 0
    return r, ok, off


def _walk_audio(seq, offset_s, depth, path, rows, deps):
    """Every audio section to depth 4 with outer-time placement (prec s1_audio_probe.py:19-50). Plain reads."""
    deps.add(seq.get_path_name().split(".")[0])
    r = seq.get_display_rate()
    fps = float(r.numerator) / float(r.denominator)
    tracks = [(t, "") for t in seq.get_tracks()]
    for b in seq.get_bindings():
        tracks += [(t, str(b.get_display_name())) for t in b.get_tracks()]
    for t, owner in tracks:
        cls = t.get_class().get_name()
        for s in t.get_sections():
            try:
                st = s.get_start_frame() / fps if s.has_start_frame() else None
                en = s.get_end_frame() / fps if s.has_end_frame() else None
            except Exception:  # noqa: BLE001
                st, en = None, None
            if isinstance(s, unreal.MovieSceneAudioSection):
                snd = s.get_sound()
                if snd:
                    deps.add(snd.get_path_name().split(".")[0])
                rows.append({"path": path, "track": str(t.get_display_name()), "owner": owner, "cls": cls,
                             "sound": snd.get_path_name() if snd else None,
                             "sound_s": float(snd.get_editor_property("duration")) if snd else None,
                             "start_s": (offset_s + st) if st is not None else None,
                             "end_s": (offset_s + en) if en is not None else None,
                             "section_active": bool(s.is_active()),
                             "track_eval_disabled": bool(t.is_eval_disabled()) if hasattr(t, "is_eval_disabled")
                             else None})
            elif isinstance(s, unreal.MovieSceneSubSection) and depth < 4 and st is not None:
                sub = s.get_sequence()
                if sub is not None:
                    _walk_audio(sub, offset_s + st, depth + 1, path + " > " + sub.get_name(), rows, deps)


def survey(args):
    """READ-ONLY facts. Returns the facts dict (SURVEY shape consumed by plan_jobs)."""
    facts = {"run": _RUN[0], "tool": TOOL, "master": {}, "scenes": {}, "deps": {}, "clocked_actors": [],
             "ppvs": [], "streaming": [], "show_root": {}, "scalability": {}, "mrq_classes": {}, "notes": []}
    for nm in ("MoviePipelinePrimaryConfig", "MoviePipelineOutputSetting", "MoviePipelineDeferredPassBase",
               "MoviePipelineImageSequenceOutput_PNG", "MoviePipelineWaveOutput", "MoviePipelineAntiAliasingSetting",
               "MoviePipelineGameOverrideSetting", "MoviePipelineConsoleVariableSetting", "MoviePipelineQueue",
               "MoviePipelineExecutorJob", "MoviePipelinePIEExecutor", "MoviePipelineQueueSubsystem",
               "MoviePipelineEditorBlueprintLibrary", "MoviePipelinePrimaryConfigFactory",
               "MoviePipelineMP4EncoderOutput", "MoviePipelineAppleProResOutput", "MoviePipelineAvidDNxOutput"):
        facts["mrq_classes"][nm] = hasattr(unreal, nm)
    master = unreal.load_asset(MASTER)
    if master is None:
        _stop("NO_MASTER|%s" % MASTER)
    facts["master"] = {"path": MASTER, "display_rate": _fr(master.get_display_rate()),
                       "tick_rate": _fr(master.get_tick_resolution()),
                       "playback": [int(master.get_playback_start()), int(master.get_playback_end())]}
    deps_all = {MASTER, SHOW, MAP}
    per_scene_sections = {n: [] for n in SCENES}
    for t in master.get_tracks():
        cname = t.get_class().get_name()
        if not isinstance(t, unreal.MovieSceneSubTrack):
            continue
        for s in t.get_sections():
            sub = s.get_sequence()
            if sub is None:
                continue
            path = sub.get_path_name().split(".")[0]
            m = re.search(r"/LS_DevScene_0(\d)$", path)
            if not m:
                continue
            r, ok, off = _play_rate(s)
            per_scene_sections[int(m.group(1))].append({
                "track_class": cname, "start": int(s.get_start_frame()), "end": int(s.get_end_frame()),
                "active": bool(s.is_active()), "play_rate": r, "play_rate_read": ok, "start_offset_tick": off})
    for n in SCENES:
        seq = unreal.load_asset(SCENE_SEQ % n)
        row = {"sequence": SCENE_SEQ % n, "master_sections": per_scene_sections[n]}
        if seq is None:
            row["inner"] = None
            facts["scenes"][str(n)] = row
            continue
        row["inner"] = {"playback": [int(seq.get_playback_start()), int(seq.get_playback_end())],
                        "display_rate": _fr(seq.get_display_rate())}
        try:
            raw = seq.get_marked_frames_from_sequence(unreal.MovieSceneTimeUnit.DISPLAY_RATE)  # curtain_sleight:1298
            row["markers"] = [[str(mk.get_editor_property("label")), int(mk.get_editor_property("frame_number").value)]
                              for mk in raw]
        except Exception as exc:  # noqa: BLE001
            row["markers"] = []
            row["markers_err"] = repr(exc)
        audio, deps = [], set()
        _walk_audio(seq, 0.0, 0, seq.get_name(), audio, deps)
        row["audio"] = audio
        facts["deps"][str(n)] = sorted(deps)
        deps_all |= deps
        facts["scenes"][str(n)] = row
    # Master-level audio overlapping each Scene (music track etc.)
    m_audio, m_deps = [], set()
    for t in master.get_tracks():
        if isinstance(t, unreal.MovieSceneSubTrack):
            continue
        for s in t.get_sections():
            if isinstance(s, unreal.MovieSceneAudioSection):
                snd = s.get_sound()
                m_audio.append({"track": str(t.get_display_name()), "cls": t.get_class().get_name(),
                                "sound": snd.get_path_name() if snd else None,
                                "start": int(s.get_start_frame()) if s.has_start_frame() else None,
                                "end": int(s.get_end_frame()) if s.has_end_frame() else None,
                                "section_active": bool(s.is_active())})
    facts["master_audio"] = m_audio
    # Show segment labels by guid (for the clocked-actor census)
    labels = {}
    show = unreal.load_asset(SHOW)
    facts["show_cues"] = []
    if show is not None:
        for c in show.get_editor_property("cues"):
            try:
                labels[_gs(c.get_editor_property("cue_guid"))] = str(c.get_editor_property("label"))
            except Exception:  # noqa: BLE001
                pass
            row = {"label": str(c.get_editor_property("label")), "type": str(c.get_editor_property("type"))}
            try:
                sc = c.get_editor_property("scene")
                row["curtain_mode"] = str(sc.get_editor_property("curtain_mode")).split(".")[-1]
                row["sequence_owns_curtain"] = bool(sc.get_editor_property("sequence_owns_curtain"))
            except Exception as exc:  # noqa: BLE001
                row["curtain_err"] = repr(exc)
            facts["show_cues"].append(row)
    world = _editor_world()
    for cls_name in ("InfinityStageStrobeLight", "InfinityStageSweepLight"):
        cls = getattr(unreal, cls_name, None)
        if cls is None:
            facts["notes"].append("NO_PY_CLASS|%s" % cls_name)
            continue
        for a in unreal.GameplayStatics.get_all_actors_of_class(world, cls):
            guids, _ = _try(a, "active_segment_guids")
            guid_s = [_gs(g) for g in (guids or [])]
            enabled, _ = _try(a, "strobe_enabled", "b_strobe_enabled", "sweep_enabled", "enabled")
            loc = a.get_actor_location()
            facts["clocked_actors"].append({"class": cls_name, "label": str(a.get_actor_label()),
                                            "level": a.get_outermost().get_name(), "enabled": enabled,
                                            "segments": [[g, labels.get(g, "?")] for g in guid_s],
                                            "loc": [round(loc.x), round(loc.y), round(loc.z)]})
    for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.PostProcessVolume):
        st = a.get_editor_property("settings")
        row = {"label": str(a.get_actor_label()), "level": a.get_outermost().get_name(),
               "unbound": bool(a.get_editor_property("unbound")), "priority": float(a.get_editor_property("priority")),
               "blend_weight": float(a.get_editor_property("blend_weight")),
               "enabled": bool(a.get_editor_property("enabled"))}
        for k in ("override_auto_exposure_method", "auto_exposure_method", "override_auto_exposure_min_brightness",
                  "auto_exposure_min_brightness", "override_auto_exposure_max_brightness",
                  "auto_exposure_max_brightness", "override_auto_exposure_bias", "auto_exposure_bias"):
            try:
                v = st.get_editor_property(k)
                row[k] = str(v) if not isinstance(v, (int, float, bool)) else v
            except Exception:  # noqa: BLE001
                row[k] = None
        facts["ppvs"].append(row)
    for lv in unreal.EditorLevelUtils.get_levels(world):
        pkg = lv.get_outermost().get_name()
        rec = {"package": pkg}
        try:
            ls = unreal.GameplayStatics.get_streaming_level(world, unreal.Name(pkg.rsplit("/", 1)[1]))
            if ls is not None:
                rec["class"] = ls.get_class().get_name()
                for k in ("initially_loaded", "initially_visible"):
                    v, _ = _try(ls, k)
                    rec[k] = v
        except Exception as exc:  # noqa: BLE001
            rec["err"] = repr(exc)
        facts["streaming"].append(rec)
        deps_all.add(pkg)
    roots = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot))
    facts["show_root"]["count"] = len(roots)
    if len(roots) == 1:
        root = roots[0]
        pb, _ = _try(root, "playback_settings")
        auto, auto_name = (_try(pb, "auto_play", "b_auto_play") if pb is not None else (None, None))
        prep, _ = _try(root, "prepare_on_begin_play", "b_prepare_on_begin_play")
        ms, _ = _try(root, "master_sequence")
        tr, _ = _try(root, "transport")
        pm, _ = _try(tr, "performance_mode") if tr is not None else (None, None)
        facts["show_root"].update({"label": str(root.get_actor_label()), "auto_play": auto, "auto_play_prop": auto_name,
                                   "prepare_on_begin_play": prep,
                                   "master_sequence": ms.get_path_name().split(".")[0] if ms else None,
                                   "performance_mode": pm})
    for name in SCALABILITY_CVARS:
        try:
            facts["scalability"][name] = int(unreal.SystemLibrary.get_console_variable_int_value(name))
        except Exception:  # noqa: BLE001
            pass
    facts["deps"]["all"] = sorted(deps_all)
    return facts


def gates(facts, plan):
    """Live gates beyond plan_jobs: refusals + warnings."""
    refuse, warn = list(plan["refusals"]), []
    sr = facts.get("show_root", {})
    if sr.get("count") != 1:
        refuse.append("SHOW_ROOTS|%s" % sr.get("count"))
    if sr.get("auto_play") is True:
        refuse.append("SHOW_ROOT_AUTOPLAY (its own Master player would PLAY the Opening/P01 during the render and the "
                      "transport would claim the view at the P01 crossing; needs a decision before rendering)")
    if sr.get("auto_play") is None:
        warn.append("SHOW_ROOT_AUTOPLAY_UNREAD (inferred false = C++ default, InfinityStageShowRoot.cpp:18)")
    # The ShowRoot spawns a camera-FOLLOWING legacy curtain if any non-Passage cue has a curtain mode it does not own
    # (InfinityStageShowRoot.cpp:177-205, CurtainRig.h:41 bFollowPlayerCamera=true) [decl]. Its state comes from the
    # ShowRoot transport's frame, i.e. frame 0 (the Opening) during an MRQ render: a closed curtain over every frame.
    cues = facts.get("show_cues")
    if cues is None:
        warn.append("SHOW_CUES_UNREAD")
    else:
        for c in cues:
            if "curtain_err" in c:
                refuse.append("CUE_CURTAIN_UNREAD|%s" % c["label"])
            elif "WING" not in c.get("type", "").upper() and c.get("curtain_mode", "NONE").upper() != "NONE" and                     not c.get("sequence_owns_curtain"):
                refuse.append("LEGACY_CAMERA_CURTAIN|%s|%s (would cover the render; sequence must own it)" %
                              (c["label"], c.get("curtain_mode")))
    if sr.get("master_sequence") not in (None, MASTER):
        refuse.append("SHOW_ROOT_MASTER_MISMATCH|%s" % sr.get("master_sequence"))
    scene_labels = set()
    for n, sc in (facts.get("scenes") or {}).items():
        scene_labels.add("S%s" % n)
    for a in facts.get("clocked_actors", []):
        segs = [s[1] for s in a["segments"]]
        if not segs or any(re.search(r"\bS(cene)?\s*\d", s or "") for s in segs):
            warn.append("TRANSPORT_CLOCKED_ACTOR|%s|%s|segments=%s (reads the ShowRoot transport frame, which is "
                        "frame 0 during an MRQ render: frozen/inactive in the video)" % (a["class"], a["label"], segs))
    for p in facts.get("ppvs", []):
        if not p.get("enabled"):
            continue
        mn, mx = p.get("auto_exposure_min_brightness"), p.get("auto_exposure_max_brightness")
        if p.get("override_auto_exposure_min_brightness") and isinstance(mn, (int, float)) and \
                isinstance(mx, (int, float)) and abs(mn - mx) > 1e-6:
            warn.append("PPV_ADAPTIVE_EXPOSURE|%s|min=%s|max=%s (adapts over frames; preroll covers 2 s)" %
                        (p["label"], mn, mx))
    for n, sc in (facts.get("scenes") or {}).items():
        for a in sc.get("audio", []):
            if a.get("section_active") and not a.get("track_eval_disabled") and a.get("sound") and \
                    "CLICK" in a["sound"].upper():
                warn.append("CLICK_TRACK_ACTIVE|S%s|%s (would be in the WAV)" % (n, a["sound"]))
    if not facts.get("mrq_classes", {}).get("MoviePipelineWaveOutput"):
        refuse.append("NO_WAVE_OUTPUT_CLASS")
    return refuse, warn


def _apply_and_verify(cfg, spec):
    """Apply a settings spec to a MoviePipelinePrimaryConfig; return a mismatch list from an immediate read-back."""
    mism = []

    def setp(obj, k, v):
        obj.set_editor_property(k, v)

    o = cfg.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
    so = spec["output"]
    setp(o, "output_directory", unreal.DirectoryPath(so["output_directory"]))
    setp(o, "file_name_format", so["file_name_format"])
    setp(o, "output_resolution", unreal.IntPoint(*so["output_resolution"]))
    setp(o, "use_custom_frame_rate", True)
    setp(o, "output_frame_rate", unreal.FrameRate(*so["output_frame_rate"]))
    for k in ("override_existing_output", "use_custom_playback_range", "custom_start_frame", "custom_end_frame",
              "zero_pad_frame_numbers", "auto_version", "handle_frame_count", "output_frame_step"):
        setp(o, k, so[k])
    cfg.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase)
    png = cfg.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_PNG)
    setp(png, "write_alpha", False)
    if spec["wav"]:
        w = cfg.find_or_add_setting_by_class(unreal.MoviePipelineWaveOutput)
        setp(w, "file_name_format_override", spec["wav"]["file_name_format_override"])
    aa = cfg.find_or_add_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
    sa = spec["aa"]
    for k in ("spatial_sample_count", "temporal_sample_count", "override_anti_aliasing", "render_warm_up_count",
              "engine_warm_up_count", "use_camera_cut_for_warm_up", "render_warm_up_frames"):
        setp(aa, k, sa[k])
    if sa["aa_method"]:
        setp(aa, "anti_aliasing_method", getattr(unreal.AntiAliasingMethod, sa["aa_method"]))
    g = cfg.find_or_add_setting_by_class(unreal.MoviePipelineGameOverrideSetting)
    sg = spec["game"]
    for k in ("cinematic_quality_settings", "use_high_quality_shadows", "use_lod_zero", "flush_streaming_managers"):
        setp(g, k, sg[k])
    setp(g, "texture_streaming", getattr(unreal.MoviePipelineTextureStreamingMethod, sg["texture_streaming"]))
    cv = cfg.find_or_add_setting_by_class(unreal.MoviePipelineConsoleVariableSetting)
    for name, val in spec["cvars"]:
        if not cv.add_or_update_console_variable(name, float(val)):
            mism.append("CVAR_SET_RETURNED_FALSE|%s (setters lie: verified below)" % name)
    # read back (assert, don't print)
    mism = [m for m in mism if not m.startswith("CVAR_SET_RETURNED_FALSE")]  # judged by the read below instead
    o2 = cfg.find_setting_by_class(unreal.MoviePipelineOutputSetting)
    if o2.get_editor_property("output_directory").path.replace("\\", "/") != so["output_directory"]:
        mism.append("OUTPUT_DIRECTORY")
    for k in ("file_name_format", "use_custom_playback_range", "custom_start_frame", "custom_end_frame",
              "override_existing_output", "auto_version"):
        if o2.get_editor_property(k) != so[k]:
            mism.append("OUTPUT_%s|%s" % (k, o2.get_editor_property(k)))
    res = o2.get_editor_property("output_resolution")
    if [res.x, res.y] != so["output_resolution"]:
        mism.append("RESOLUTION")
    fr = o2.get_editor_property("output_frame_rate")
    if [fr.numerator, fr.denominator] != so["output_frame_rate"] or not o2.get_editor_property("use_custom_frame_rate"):
        mism.append("FRAME_RATE")
    aa2 = cfg.find_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
    for k in ("temporal_sample_count", "spatial_sample_count", "override_anti_aliasing", "render_warm_up_count"):
        if aa2.get_editor_property(k) != sa[k]:
            mism.append("AA_%s" % k)
    have = {}
    for e in cfg.find_setting_by_class(unreal.MoviePipelineConsoleVariableSetting).get_console_variables():
        try:
            have[str(e.get_editor_property("name"))] = float(e.get_editor_property("value"))
        except Exception:  # noqa: BLE001
            pass
    for name, val in spec["cvars"]:
        if name not in have or abs(have[name] - float(val)) > 1e-6:
            mism.append("CVAR|%s|%s" % (name, have.get(name)))
    for cls in (unreal.MoviePipelineDeferredPassBase, unreal.MoviePipelineImageSequenceOutput_PNG):
        if cfg.find_setting_by_class(cls) is None:
            mism.append("MISSING_SETTING|%s" % cls.__name__)
    if spec["wav"] and cfg.find_setting_by_class(unreal.MoviePipelineWaveOutput) is None:
        mism.append("MISSING_SETTING|WaveOutput")
    return mism


def _export(cfg, folder, name):
    lib = unreal.MoviePipelineEditorBlueprintLibrary
    res = lib.export_config_to_asset(cfg, folder, name, True)
    # 5.8 Python: a bool UFUNCTION with out-params returns the outs tuple, or None when false (memory puss-mcp-from-bash)
    if res is None:
        return None, "export_config_to_asset returned None"
    if isinstance(res, tuple):
        asset = [x for x in res if isinstance(x, unreal.MoviePipelinePrimaryConfig)]
        err = [str(x) for x in res if not isinstance(x, (bool, unreal.MoviePipelinePrimaryConfig))]
        return (asset[0] if asset else None), ";".join(err)
    return None, "unexpected return %r" % (res,)


def _write_json(name, obj):
    p = os.path.join(HERE, name)
    with open(p, "w", encoding="utf-8") as h:
        json.dump(obj, h, indent=1, default=str)
    return p.replace("\\", "/")


def _sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _deps_files(deps):
    files = []
    for pkg in deps:
        if not pkg.startswith("/Game/"):
            continue
        base = PROJECT_DIR + "/Content/" + pkg[len("/Game/"):]
        for ext in (".uasset", ".umap"):
            if os.path.exists(base + ext):
                files.append(base + ext)
    return sorted(set(files))


def main(args):
    mode = str(args.get("mode", "DRY")).upper()
    _RUN[0] = args.get("run_id") or datetime.datetime.now().strftime("MRQFB-%Y%m%d-%H%M%S")
    run = _RUN[0]
    if mode not in ("SURVEY", "DRY", "BUILD", "RENDER_PIE"):
        _stop("MODE|%s" % mode)
    if mode in ("BUILD", "RENDER_PIE"):
        want = "%s %s" % (mode, MARK)
        if args.get("confirm") != want:
            _stop("CONFIRM (want '%s')" % want)
        if not args.get("decided_by"):
            _stop("DECIDED_BY_EMPTY")
    if _pie_active():
        _stop("PIE_ACTIVE (this tool never starts or ends PIE; run when Gary is out of PIE)")
    before = _census()
    facts = survey(args)
    if _census() != before:
        _stop("SURVEY_DIRTIED|%s" % sorted(set(_census()) - set(before)))
    survey_path = _write_json("mrq_survey_%s.json" % run, facts)
    if mode == "SURVEY":
        _log("%s_SURVEY_OK|run=%s|scenes=%d|out=%s" % (MARK, run, len(facts["scenes"]), survey_path))
        return
    plan = plan_jobs(facts, args)
    refuse, warn = gates(facts, plan)
    specs = {}
    for j in plan["jobs"]:
        try:
            specs[j["name"]] = settings_spec(j, facts.get("scalability"))
            bad = validate_spec(specs[j["name"]])
            refuse.extend("%s|%s" % (j["name"], b) for b in bad)
        except PlanError as exc:
            refuse.append("%s|%s" % (j["name"], exc))
    for j in plan["jobs"]:
        j["argv"] = command_line(j, args)
        j["command_line"] = quote_argv(j["argv"])
        j["exists"] = bool(unreal.EditorAssetLibrary.does_asset_exist(j["config_asset"]))
    # Exercise the real setter/read-back path on TRANSIENT configs (one per tier; no package is created or dirtied),
    # so a 5.8 Python API-name surprise stops the DRY instead of the BUILD.
    probe = {}
    for tier in sorted(set(j["tier"] for j in plan["jobs"])):
        j0 = [j for j in plan["jobs"] if j["tier"] == tier and j["name"] in specs][:1]
        if not j0:
            continue
        try:
            cfg = unreal.new_object(unreal.MoviePipelinePrimaryConfig, unreal.get_transient_package())
            probe[tier] = _apply_and_verify(cfg, specs[j0[0]["name"]])
            cfg = None
        except Exception as exc:  # noqa: BLE001
            probe[tier] = ["EXCEPTION|%r" % (exc,)]
        refuse.extend("TRANSIENT_PROBE|%s|%s" % (tier, m) for m in probe[tier])
    if _census() != before:
        refuse.append("TRANSIENT_PROBE_DIRTIED|%s" % sorted(set(_census()) - set(before)))
    dry = {"run": run, "mode": mode, "args": args, "plan": plan, "refusals": refuse, "warnings": warn,
           "transient_probe": probe,
           "specs": specs, "survey": survey_path, "deps_files": {k: _deps_files(v) for k, v in facts["deps"].items()}}
    dry_path = _write_json("mrq_dry_%s.json" % run, dry)
    if refuse:
        _stop("REFUSED|%d|%s|out=%s" % (len(refuse), " ; ".join(refuse[:6]), dry_path))
    if mode == "DRY":
        _log("%s_DRY_OK|run=%s|jobs=%d|warnings=%d|out=%s" % (MARK, run, len(plan["jobs"]), len(warn), dry_path))
        return
    if mode == "BUILD":
        if before:
            _stop("DIRTY_AT_START|%s (BUILD saves only its own new packages; start clean)" % before[:8])
        existing = [j["config_asset"] for j in plan["jobs"] if j["exists"]]
        if existing:
            _stop("CREATE_ONLY_TARGETS_EXIST|%s (bump args.version)" % existing)
        built = []
        for j in plan["jobs"]:
            cfg = unreal.new_object(unreal.MoviePipelinePrimaryConfig, unreal.get_transient_package())
            mism = _apply_and_verify(cfg, specs[j["name"]])
            if mism:
                _stop("TRANSIENT_READBACK|%s|%s" % (j["name"], mism))
            name = j["config_asset"].rsplit("/", 1)[1]
            asset, err = _export(cfg, args.get("asset_folder", ASSET_FOLDER), name)
            cfg = None
            if asset is None:
                _stop("EXPORT_FAILED|%s|%s (configs built so far: %s)" % (name, err, [b["name"] for b in built]))
            loaded = unreal.load_asset(j["config_asset"])
            mism2 = _apply_check_only(loaded, specs[j["name"]])
            if mism2:
                _stop("ASSET_READBACK|%s|%s" % (name, mism2))
            disk = PROJECT_DIR + "/Content/" + j["config_asset"][len("/Game/"):] + ".uasset"
            if not os.path.exists(disk):
                _stop("NOT_ON_DISK|%s" % disk)
            built.append(dict(j, disk=disk))
            unreal.SystemLibrary.collect_garbage()
        after = _census()
        if after != before:
            _stop("CENSUS_CHANGED|%s" % sorted(set(after) ^ set(before)))
        master_file = PROJECT_DIR + "/Content/" + MASTER[len("/Game/"):] + ".uasset"
        rec = {"run": run, "decided_by": args.get("decided_by"), "built": built, "scenes": plan["scenes"],
               "deps_files": dry["deps_files"], "master_uasset": master_file, "master_sha256": _sha256(master_file),
               "dry": dry_path,
               "note": "Ranges are Master display frames baked into the configs. If the Master .uasset hash changes "
                       "(a rebuild/relength), mrq_render.ps1 refuses: re-run DRY, and BUILD a new version if ranges moved."}
        p1 = _write_json("mrq_jobs_built_%s.json" % run, rec)
        _write_json("mrq_jobs_built.json", rec)
        _log("%s_BUILD_OK|run=%s|configs=%d|out=%s" % (MARK, run, len(built), p1))
        return
    if mode == "RENDER_PIE":
        if not args.get("cue_desk_closed_ack"):
            _stop("CUE_DESK_ACK (the Cue Desk's PostPIEStarted hook jumps the ShowRoot to its playhead in MRQ's PIE "
                  "world: close the Cue Desk or park its playhead at 0, then set cue_desk_closed_ack true)")
        if before:
            _stop("DIRTY_AT_START|%s" % before[:8])
        names = set(args.get("render_jobs") or [])
        sel = [j for j in plan["jobs"] if j["name"] in names]
        if not sel or len(sel) != len(names):
            _stop("RENDER_JOBS|want=%s|found=%s" % (sorted(names), [j["name"] for j in sel]))
        missing = [j["config_asset"] for j in sel if not j["exists"]]
        if missing:
            _stop("NOT_BUILT|%s" % missing)
        queue = unreal.new_object(unreal.MoviePipelineQueue, unreal.get_transient_package())
        for j in sel:
            job = queue.allocate_new_job(unreal.MoviePipelineExecutorJob)
            job.set_editor_property("job_name", "PussFB_" + j["name"])
            job.set_editor_property("map", unreal.SoftObjectPath(MAP + "." + MAP.rsplit("/", 1)[1]))
            seq_path = unreal.SoftObjectPath(MASTER + "." + MASTER.rsplit("/", 1)[1])
            if hasattr(job, "set_sequence"):            # UMoviePipelineExecutorJob::SetSequence (MoviePipelineQueue.h:617)
                job.set_sequence(seq_path)
            else:
                job.set_editor_property("sequence", seq_path)
            job.set_configuration(unreal.load_asset(j["config_asset"]))
        subsys = unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem)
        subsys.render_queue_instance_with_executor(queue, unreal.MoviePipelinePIEExecutor)
        _log("%s_RENDER_PIE_STARTED|run=%s|jobs=%s (completion = frames on disk: mrq_post.py check)" %
             (MARK, run, ",".join(j["name"] for j in sel)))


def _apply_check_only(cfg, spec):
    """Read-back of a SAVED config (no writes): the subset of _apply_and_verify's checks."""
    if cfg is None:
        return ["LOAD_NONE"]
    mism = []
    o = cfg.find_setting_by_class(unreal.MoviePipelineOutputSetting)
    if o is None:
        return ["NO_OUTPUT_SETTING"]
    so = spec["output"]
    for k in ("file_name_format", "custom_start_frame", "custom_end_frame", "use_custom_playback_range"):
        if o.get_editor_property(k) != so[k]:
            mism.append("OUTPUT_%s" % k)
    if o.get_editor_property("output_directory").path.replace("\\", "/") != so["output_directory"]:
        mism.append("OUTPUT_DIRECTORY")
    aa = cfg.find_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
    if aa is None or aa.get_editor_property("temporal_sample_count") != spec["aa"]["temporal_sample_count"]:
        mism.append("AA")
    cv = cfg.find_setting_by_class(unreal.MoviePipelineConsoleVariableSetting)
    names = set()
    if cv is not None:
        for e in cv.get_console_variables():
            try:
                names.add(str(e.get_editor_property("name")))
            except Exception:  # noqa: BLE001
                pass
    for name, _ in spec["cvars"]:
        if name not in names:
            mism.append("CVAR|%s" % name)
    if spec["wav"] and cfg.find_setting_by_class(unreal.MoviePipelineWaveOutput) is None:
        mism.append("WAV")
    return mism


def _offline_plan(facts_path):
    with open(facts_path, "r", encoding="utf-8") as h:
        facts = json.load(h)
    args = {"tiers": ["P", "C"], "version": "v01"}
    plan = plan_jobs(facts, args)
    for j in plan["jobs"]:
        j["command_line"] = quote_argv(command_line(j))
    print(json.dumps({"refusals": plan["refusals"], "totals": plan["totals"],
                      "jobs": [[j["name"], j["render_range"], j["render_frames"], j["est_hours"]] for j in plan["jobs"]]},
                     indent=1))


if __name__ == "__main__" and unreal is None:
    if len(sys.argv) >= 3 and sys.argv[1].upper() == "PLAN":
        _offline_plan(sys.argv[2])
elif unreal is not None and "MRQFB_ARGS" in globals():
    try:
        main(globals()["MRQFB_ARGS"])
    except RuntimeError:
        pass
    except Exception as exc:  # noqa: BLE001
        unreal.log_error("%s_STOPPED|run=%s|reason=EXCEPTION|%r" % (MARK, _RUN[0], exc))
