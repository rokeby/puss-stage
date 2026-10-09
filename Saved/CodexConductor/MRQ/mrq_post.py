"""Offline post-render tool for the MRQ Scene fallbacks (7 Oct 2026, offline-written, NOT RUN on real renders).
No Unreal. Needs ffmpeg/ffprobe (found 7 Oct: C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\WinGet\\Links, 9.0.2
gyan.dev full build, libx264 + prores_ks + h264_nvenc).

  python mrq_post.py encode  --scene 5 --tier P [--version v01] [--mux] [--test 10]
  python mrq_post.py qc      --scene 5 --tier P [--version v01] [--test 10]
  python mrq_post.py stale   [--scene 5]
  python mrq_post.py promote --scene 5 --tier P [--version v01] --by "<who approved>"

encode: drops the preroll (the end of the preceding Passage), assembles chunks (tier C), writes
        Renders/Fallbacks/S<n>/PussFB_S<n>_<tier>_<ver>.mp4  (H.264 High, 1920x1080, 25 fps CFR, BT.709 limited range,
        a keyframe every 25 frames so CD4 can seek/loop exactly), .wav (PCM 24-bit 48 kHz, trimmed by exactly the preroll
        samples; tier C takes the P render's WAV: same Master range, same clock), .json sidecar (frames, seconds,
        markers in VIDEO seconds, sha256), optional _muxed.mp4 (AAC 320k, convenience only: Gary asked for a separate WAV).
qc:     frame count, audio/video length match (<= 1 frame), black stretches, frame-to-frame luma jumps (streaming pops /
        stale cache candidates), washed-out share, clipping, silence, a contact sheet PNG. Writes ..._qc.json.
        It REPORTS; a human (Gary) judges darkness that is authored.
stale:  compares each take's deps_manifest (hashed by mrq_render.ps1 before the render) with the files now on disk.
promote: writes Renders/Fallbacks/current.json, the file the Cue Director (CD4) reads. Refuses without a qc.json whose
        hard checks passed, and without --by.
Markers: MRQPOST_<CMD>_OK|...  MRQPOST_FAILED|...
"""
import argparse
import datetime
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
JOBS_FILE = os.path.join(HERE, "mrq_jobs_built.json")
RENDER_ROOT = "E:/PussStage/Renders/Fallbacks"
FPS = 25
SR = 48000
LUMA_JUMP = 40.0          # YAVG step (8-bit, limited range) between consecutive frames flagged as a pop candidate
BLACK_YAVG = 20.0         # limited-range black is 16
BLACK_MIN_S = 0.5
WASHED_YAVG = 200.0


class PostError(Exception):
    pass


def tool(name):
    found = shutil.which(name)
    if found:
        return found
    cand = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links\%s.exe" % name)
    if os.path.exists(cand):
        return cand
    raise PostError("NO_%s (install or add to PATH)" % name.upper())


# ----------------------------------------------------------------------------------------------------- pure (harness)
def scene_jobs(built, scene, tier, version, test=None):
    """The built jobs that make up one deliverable, in keep-range order; asserts they tile the Scene exactly."""
    rows = [j for j in built["built"] if int(j["scene"]) == int(scene) and j["tier"] == tier and j["version"] == version
            and bool(j.get("test")) == bool(test)]
    if test:
        rows = [j for j in rows if j["name"].endswith("_t%d" % int(test))]
    if not rows:
        raise PostError("NO_JOBS|S%s|%s|%s|test=%s" % (scene, tier, version, test))
    rows.sort(key=lambda j: j["keep_range"][0])
    sc = built["scenes"][str(int(scene))]
    s0, s1 = sc["master_range"]
    if not test:
        if rows[0]["keep_range"][0] != s0 or rows[-1]["keep_range"][1] != s1:
            raise PostError("JOBS_DO_NOT_COVER_SCENE|%s..%s vs %s..%s" % (rows[0]["keep_range"][0],
                                                                       rows[-1]["keep_range"][1], s0, s1))
    for a, b in zip(rows, rows[1:]):
        if a["keep_range"][1] != b["keep_range"][0]:
            raise PostError("CHUNK_GAP_OR_OVERLAP|%s|%s" % (a["name"], b["name"]))
    return rows


def frame_map(rows):
    """[(output_index, job_name, frames_dir, master_frame)] for every kept frame, in order."""
    out, i = [], 0
    for j in rows:
        for f in range(j["keep_range"][0], j["keep_range"][1]):
            out.append((i, j["name"], j["output_dir"], f))
            i += 1
    return out


def png_name(job, master_frame):
    stem = job["file_name_format"].replace("{frame_number}", "%06d" % master_frame)
    return "%s/%s.png" % (job["output_dir"], stem)


def audio_trim(job_for_audio, keep_range, fps=FPS, sr=SR):
    """(start_sample, n_samples) to cut the deliverable out of the audio job's raw WAV."""
    ra = job_for_audio["render_range"][0]
    if keep_range[0] < ra or keep_range[1] > job_for_audio["render_range"][1]:
        raise PostError("AUDIO_JOB_DOES_NOT_COVER|%s|%s" % (job_for_audio["render_range"], keep_range))
    per = sr / float(fps)
    if abs(per - round(per)) > 1e-9:
        raise PostError("SAMPLES_PER_FRAME_NOT_INTEGER|%s" % per)
    per = int(round(per))
    return (keep_range[0] - ra) * per, (keep_range[1] - keep_range[0]) * per


def ffmpeg_video_args(ffmpeg, pattern, start_number, frames, out_mp4, crf=14):
    return [ffmpeg, "-hide_banner", "-y", "-framerate", str(FPS), "-start_number", str(start_number), "-i", pattern,
            "-frames:v", str(frames),
            "-vf", "scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p",
            "-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-profile:v", "high",
            "-x264-params", "keyint=%d:min-keyint=%d:scenecut=0" % (FPS, FPS),
            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv",
            "-r", str(FPS), "-movflags", "+faststart", "-an", out_mp4]


def ffmpeg_audio_args(ffmpeg, raw_wav, start_sample, n_samples, out_wav):
    return [ffmpeg, "-hide_banner", "-y", "-i", raw_wav,
            "-af", "atrim=start_sample=%d:end_sample=%d,asetpts=PTS-STARTPTS" % (start_sample, start_sample + n_samples),
            "-c:a", "pcm_s24le", "-ar", str(SR), out_wav]


def parse_signalstats(text):
    """ffmpeg metadata=print output -> list of YAVG floats in frame order."""
    return [float(m.group(1)) for m in re.finditer(r"lavfi\.signalstats\.YAVG=([0-9.]+)", text)]


def parse_freezedetect(text):
    """ffmpeg freezedetect output -> candidate frozen stretches in seconds."""
    starts = [float(x) for x in re.findall(r"freeze_start:\s*([0-9.]+)", text)]
    durations = [float(x) for x in re.findall(r"freeze_duration:\s*([0-9.]+)", text)]
    ends = [float(x) for x in re.findall(r"freeze_end:\s*([0-9.]+)", text)]
    out = []
    for i, start in enumerate(starts):
        duration = durations[i] if i < len(durations) else None
        end = ends[i] if i < len(ends) else (start + duration if duration is not None else None)
        out.append({"start_s": round(start, 3), "end_s": round(end, 3) if end is not None else None,
                    "duration_s": round(duration, 3) if duration is not None else None})
    return out


def luma_findings(yavg, fps=FPS):
    """Pure QC over per-frame luma: black stretches, jumps, washed share, summary."""
    if not yavg:
        return {"frames": 0}
    black, run = [], None
    for i, y in enumerate(yavg + [999.0]):
        if y < BLACK_YAVG and run is None:
            run = i
        elif y >= BLACK_YAVG and run is not None:
            if (i - run) / float(fps) >= BLACK_MIN_S:
                black.append([round(run / float(fps), 2), round(i / float(fps), 2)])
            run = None
    jumps = [[round(i / float(fps), 2), round(yavg[i] - yavg[i - 1], 1)] for i in range(1, len(yavg))
             if abs(yavg[i] - yavg[i - 1]) >= LUMA_JUMP]
    srt = sorted(yavg)
    return {"frames": len(yavg), "mean": round(sum(yavg) / len(yavg), 1), "p5": srt[int(0.05 * (len(srt) - 1))],
            "p95": srt[int(0.95 * (len(srt) - 1))], "black_stretches_s": black, "luma_jumps": jumps[:200],
            "luma_jump_count": len(jumps), "washed_share": round(sum(1 for y in yavg if y >= WASHED_YAVG) / len(yavg), 4),
            "first_frame_black": yavg[0] < BLACK_YAVG}


def hard_checks(expect_frames, video_frames, video_s, audio_s, fps=FPS, audio_required=True, audio_present=True):
    bad = []
    if video_frames != expect_frames:
        bad.append("FRAME_COUNT|%s!=%s" % (video_frames, expect_frames))
    if audio_s is not None and abs(audio_s - expect_frames / float(fps)) > 1.0 / fps:
        bad.append("AUDIO_LENGTH|%.4f vs %.4f" % (audio_s, expect_frames / float(fps)))
    if video_s is not None and abs(video_s - expect_frames / float(fps)) > 1.0 / fps:
        bad.append("VIDEO_LENGTH|%.4f" % video_s)
    if audio_required and not audio_present:
        bad.append("AUDIO_MISSING")
    return bad


def validate_cd4_registry(registry):
    """Validate the exact schema subset consumed by CD4's ParseRegistry."""
    bad = []
    if not isinstance(registry, dict):
        return ["ROOT_NOT_OBJECT"]
    if registry.get("schema") != 1:
        bad.append("SCHEMA|%r" % registry.get("schema"))
    scenes = registry.get("scenes")
    if not isinstance(scenes, dict):
        return bad + ["SCENES_NOT_OBJECT"]
    for key, row in scenes.items():
        if not re.match(r"^S[1-6]$", str(key)):
            bad.append("SCENE_KEY|%s" % key)
            continue
        if not isinstance(row, dict):
            bad.append("SCENE_NOT_OBJECT|%s" % key)
            continue
        if not isinstance(row.get("video"), str) or not row.get("video"):
            bad.append("VIDEO|%s" % key)
        if not isinstance(row.get("frames"), int) or row.get("frames", 0) <= 0:
            bad.append("FRAMES|%s" % key)
        if not isinstance(row.get("fps"), (int, float)) or row.get("fps", 0) <= 0:
            bad.append("FPS|%s" % key)
    return bad


def merge_registry(registry, scene_key, entry):
    """Return a merged schema-1 registry without discarding another Scene."""
    out = json.loads(json.dumps(registry or {}))
    out.setdefault("schema", 1)
    out.setdefault("scenes", {})
    out["scenes"][scene_key] = entry
    bad = validate_cd4_registry(out)
    if bad:
        raise PostError("CD4_SCHEMA|%s" % ";".join(bad))
    return out


def stale_diff(manifest, current):
    """manifest [{"file","sha256"}], current {file: sha256 or None} -> list of changed/missing files."""
    out = []
    for row in manifest:
        now = current.get(row["file"])
        if now is None:
            out.append(["MISSING", row["file"]])
        elif now != row["sha256"]:
            out.append(["CHANGED", row["file"]])
    return out


def deliverable_stem(scene, tier, version, test=None):
    return "PussFB_S%d_%s_%s%s" % (int(scene), tier, version, ("_t%d" % int(test)) if test else "")


# ------------------------------------------------------------------------------------------------------------ actions
def _load_built():
    if not os.path.exists(JOBS_FILE):
        raise PostError("NO_JOBS_FILE|%s" % JOBS_FILE)
    with open(JOBS_FILE, "r", encoding="utf-8") as h:
        return json.load(h)


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _run(argv):
    r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise PostError("CMD_FAILED|%s|%s" % (os.path.basename(argv[0]), r.stderr[-800:]))
    return r


def _probe(path):
    r = _run([tool("ffprobe"), "-v", "error", "-show_streams", "-show_format", "-count_frames", "-of", "json", path])
    return json.loads(r.stdout)


def _out_dir(scene):
    return "%s/S%d" % (RENDER_ROOT, int(scene))


def cmd_encode(a):
    built = _load_built()
    rows = scene_jobs(built, a.scene, a.tier, a.version, a.test)
    ff = tool("ffmpeg")
    stem = deliverable_stem(a.scene, a.tier, a.version, a.test)
    od = _out_dir(a.scene)
    os.makedirs(od, exist_ok=True)
    mp4, wav = "%s/%s.mp4" % (od, stem), "%s/%s.wav" % (od, stem)
    for p in (mp4, wav):
        if os.path.exists(p) and not a.overwrite:
            raise PostError("EXISTS|%s (use --overwrite or bump the version)" % p)
    fm = frame_map(rows)
    by_name = {j["name"]: j for j in rows}
    missing = [png_name(by_name[n], f) for (_, n, _, f) in fm if not os.path.exists(png_name(by_name[n], f))]
    if missing:
        raise PostError("MISSING_FRAMES|%d|first=%s" % (len(missing), missing[:3]))
    if len(rows) == 1:
        j = rows[0]
        pattern = "%s/%s.png" % (j["output_dir"], j["file_name_format"].replace("{frame_number}", "%06d"))
        _run(ffmpeg_video_args(ff, pattern, j["keep_range"][0], len(fm), mp4, a.crf))
    else:  # chunks: hard links into one numbered staging folder (same drive, no copy)
        stage = "%s/_stage_%s" % (od, stem)
        if os.path.exists(stage):
            raise PostError("STAGE_EXISTS|%s (remove the old link folder first; links only, frames are elsewhere)" % stage)
        os.makedirs(stage)
        for (i, n, _, f) in fm:
            os.link(png_name(by_name[n], f), "%s/%06d.png" % (stage, i))
        _run(ffmpeg_video_args(ff, stage + "/%06d.png", 0, len(fm), mp4, a.crf))
    # audio: the tier's own WAV if it has one, else the P render of the same Scene/version
    audio_rows = [j for j in rows if j.get("wav")]
    if audio_rows:
        aj = audio_rows[0]
    else:
        aj = scene_jobs(built, a.scene, "P", a.version, a.test)[0]
    raws = glob.glob("%s/*.wav" % aj["output_dir"])
    if len(raws) != 1:
        raise PostError("RAW_WAV|%s|%d found" % (aj["output_dir"], len(raws)))
    pr = _probe(raws[0])
    sr = int(pr["streams"][0]["sample_rate"])
    if sr != SR:
        raise PostError("RAW_WAV_RATE|%d (expected %d; recompute the trim before encoding)" % (sr, SR))
    keep = [rows[0]["keep_range"][0], rows[-1]["keep_range"][1]]
    s_start, s_n = audio_trim(aj, keep)
    _run(ffmpeg_audio_args(ff, raws[0], s_start, s_n, wav))
    if a.mux:
        _run([ff, "-hide_banner", "-y", "-i", mp4, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
              "-b:a", "320k", "-movflags", "+faststart", "%s/%s_muxed.mp4" % (od, stem)])
    sc = built["scenes"][str(int(a.scene))]
    side = {"stem": stem, "scene": int(a.scene), "tier": a.tier, "version": a.version, "test_seconds": a.test,
            "fps": FPS, "frames": len(fm), "seconds": len(fm) / float(FPS), "master_keep_range": keep,
            "audio_samples": s_n, "audio_sr": SR, "audio_from_job": aj["name"], "audio_required": True,
            "markers_video_s": sc.get("markers_video_s", []), "jobs": [j["name"] for j in rows],
            "files": {"mp4": mp4, "wav": wav}, "sha256": {"mp4": _sha(mp4), "wav": _sha(wav)},
            "encoded_utc": datetime.datetime.utcnow().isoformat() + "Z"}
    with open("%s/%s.json" % (od, stem), "w", encoding="utf-8") as h:
        json.dump(side, h, indent=1)
    print("MRQPOST_ENCODE_OK|stem=%s|frames=%d|mp4=%s|wav=%s" % (stem, len(fm), mp4, wav))


def cmd_qc(a):
    stem = deliverable_stem(a.scene, a.tier, a.version, a.test)
    od = _out_dir(a.scene)
    with open("%s/%s.json" % (od, stem), "r", encoding="utf-8") as h:
        side = json.load(h)
    ff = tool("ffmpeg")
    pv = _probe(side["files"]["mp4"])
    vs = [s for s in pv["streams"] if s["codec_type"] == "video"][0]
    vframes = int(vs.get("nb_read_frames") or vs.get("nb_frames") or 0)
    vsec = float(pv["format"]["duration"])
    audio_present = os.path.isfile(side["files"].get("wav", ""))
    pa = _probe(side["files"]["wav"]) if audio_present else {"format": {"duration": None}}
    asec = float(pa["format"]["duration"]) if audio_present else None
    bad = hard_checks(side["frames"], vframes, vsec, asec,
                      audio_required=bool(side.get("audio_required", True)), audio_present=audio_present)
    if (int(vs["width"]), int(vs["height"])) != (1920, 1080):
        bad.append("RESOLUTION|%sx%s" % (vs["width"], vs["height"]))
    if vs.get("r_frame_rate") != "25/1":
        bad.append("FRAME_RATE|%s" % vs.get("r_frame_rate"))
    r = _run([ff, "-hide_banner", "-i", side["files"]["mp4"], "-vf", "signalstats,metadata=print:file=-", "-f", "null", "-"])
    luma = luma_findings(parse_signalstats(r.stdout + r.stderr))
    frozen_run = _run([ff, "-hide_banner", "-i", side["files"]["mp4"], "-vf", "freezedetect=n=-60dB:d=2", "-f", "null", "-"])
    frozen = parse_freezedetect(frozen_run.stdout + frozen_run.stderr)
    vd = _run([ff, "-hide_banner", "-i", side["files"]["wav"], "-af", "volumedetect", "-f", "null", "-"]).stderr if audio_present else ""
    mx = re.search(r"max_volume:\s*(-?[0-9.]+) dB", vd)
    mean = re.search(r"mean_volume:\s*(-?[0-9.]+) dB", vd)
    sil = _run([ff, "-hide_banner", "-i", side["files"]["wav"], "-af", "silencedetect=n=-60dB:d=2", "-f", "null", "-"]).stderr if audio_present else ""
    silences = re.findall(r"silence_start: ([0-9.]+)", sil)
    sheet = "%s/%s_sheet.png" % (od, stem)
    step = max(1, side["frames"] // 24)
    _run([ff, "-hide_banner", "-y", "-i", side["files"]["mp4"], "-vf",
          "select='not(mod(n\\,%d))',scale=480:-1,tile=4x6" % step, "-frames:v", "1", "-update", "1", sheet])
    soft = []
    if luma.get("first_frame_black"):
        soft.append("FIRST_FRAME_BLACK (authored dark entry, or a missing camera at the cut: compare a PIE still)")
    if luma.get("luma_jump_count"):
        soft.append("LUMA_JUMPS|%d (cuts are expected; check each against the Scene's cut list / PIE)" %
                    luma["luma_jump_count"])
    if luma.get("washed_share", 0) > 0.05:
        soft.append("WASHED_SHARE|%s (S3 white-out lesson: check the pinned exposure weight)" % luma["washed_share"])
    if frozen:
        soft.append("FROZEN_STRETCHES|%d (static staging may be authored; inspect the listed intervals)" % len(frozen))
    if mx and float(mx.group(1)) >= -0.1:
        soft.append("AUDIO_CLIPPING|max %s dB" % mx.group(1))
    if mean and float(mean.group(1)) < -60:
        soft.append("AUDIO_NEAR_SILENT|mean %s dB (S3 has no imported score; is that intended?)" % mean.group(1))
    qc = {"stem": stem, "hard_fail": bad, "soft": soft, "video_frames": vframes, "video_s": vsec, "audio_s": asec,
          "luma": luma, "frozen_stretches_s": frozen, "audio_present": audio_present,
          "audio_max_db": mx.group(1) if mx else None, "audio_mean_db": mean.group(1) if mean else None,
          "silence_starts_s": silences[:50], "sheet": sheet, "ok": not bad,
          "human_checklist": ["exposure vs a PIE still at entry+5 s / mid / exit-5 s", "her streamed sets present",
                              "no HUD / debug text", "camera = authored cut list", "GeometryCache cloth not frozen",
                              "audio in sync at a clap/strike marker", "no click track"],
          "qc_utc": datetime.datetime.utcnow().isoformat() + "Z"}
    with open("%s/%s_qc.json" % (od, stem), "w", encoding="utf-8") as h:
        json.dump(qc, h, indent=1)
    print("MRQPOST_QC_%s|stem=%s|hard=%d|soft=%d|sheet=%s" % ("OK" if not bad else "FAILED", stem, len(bad), len(soft),
                                                               sheet))


def cmd_stale(a):
    rows = []
    for mf in sorted(glob.glob("%s/S*/*/deps_manifest_*.json" % RENDER_ROOT)):
        if a.scene and "/S%d/" % a.scene not in mf.replace("\\", "/"):
            continue
        with open(mf, "r", encoding="utf-8-sig") as h:
            man = json.load(h)
        if isinstance(man, dict):
            man = [man]
        cur = {}
        for row in man:
            p = row["file"]
            cur[p] = _sha(p).lower() if os.path.exists(p) else None
        diff = stale_diff([{"file": r["file"], "sha256": r["sha256"].lower()} for r in man], cur)
        rows.append({"manifest": mf, "stale": bool(diff), "changed": diff})
        print("%s|%s|%s" % ("STALE" if diff else "FRESH", mf, "; ".join("%s %s" % (k, os.path.basename(f))
                                                                      for k, f in diff[:6])))
    print("MRQPOST_STALE_OK|manifests=%d|stale=%d" % (len(rows), sum(1 for r in rows if r["stale"])))


def cmd_promote(a):
    if not a.by:
        raise PostError("BY_EMPTY (who approved this clip?)")
    stem = deliverable_stem(a.scene, a.tier, a.version)
    od = _out_dir(a.scene)
    with open("%s/%s_qc.json" % (od, stem), "r", encoding="utf-8") as h:
        qc = json.load(h)
    if not qc.get("ok"):
        raise PostError("QC_NOT_OK|%s" % qc.get("hard_fail"))
    with open("%s/%s.json" % (od, stem), "r", encoding="utf-8") as h:
        side = json.load(h)
    for k in ("mp4", "wav"):
        if _sha(side["files"][k]) != side["sha256"][k]:
            raise PostError("SHA_CHANGED_SINCE_ENCODE|%s" % k)
    cur_p = "%s/current.json" % RENDER_ROOT
    cur = {}
    if os.path.exists(cur_p):
        with open(cur_p, "r", encoding="utf-8") as h:
            cur = json.load(h)
    prev = (cur.get("scenes") or {}).get("S%d" % a.scene)
    entry = {
        "video": os.path.relpath(side["files"]["mp4"], RENDER_ROOT).replace("\\", "/"),
        "audio": os.path.relpath(side["files"]["wav"], RENDER_ROOT).replace("\\", "/"),
        "sidecar": "S%d/%s.json" % (a.scene, stem), "frames": side["frames"], "seconds": side["seconds"],
        "fps": FPS, "tier": a.tier, "version": a.version, "sha256": side["sha256"],
        "markers_video_s": side.get("markers_video_s", []), "approved_by": a.by,
        "promoted_utc": datetime.datetime.utcnow().isoformat() + "Z", "previous": prev}
    cur = merge_registry(cur, "S%d" % a.scene, entry)
    tmp_p = cur_p + ".tmp"
    with open(tmp_p, "w", encoding="utf-8") as h:
        json.dump(cur, h, indent=1)
    os.replace(tmp_p, cur_p)
    print("MRQPOST_PROMOTE_OK|S%d|%s|by=%s|current=%s" % (a.scene, stem, a.by, cur_p))


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["encode", "qc", "stale", "promote"])
    p.add_argument("--scene", type=int)
    p.add_argument("--tier", default="P", choices=["P", "C"])
    p.add_argument("--version", default="v01")
    p.add_argument("--test", type=int, default=None)
    p.add_argument("--mux", action="store_true")
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--crf", type=int, default=14)
    p.add_argument("--by", default=None)
    a = p.parse_args(argv)
    try:
        {"encode": cmd_encode, "qc": cmd_qc, "stale": cmd_stale, "promote": cmd_promote}[a.cmd](a)
    except PostError as exc:
        print("MRQPOST_FAILED|%s|%s" % (a.cmd, exc))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
