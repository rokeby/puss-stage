"""Shadow-puppet video -> stop-motion gobo flipbook for an Unreal light function (offline: ffmpeg + numpy + Pillow).

Written 6 Oct 2026 for Gary: "cheap stop motion animated gobos in front of lights that are made from basic iphone videos
of the shadow puppets being puppeted live". Pipeline and Unreal side: Docs/ShadowGoboPipeline_2026-10-06.md.
Shoot spec (still valid): Docs/ShadowPuppetCaptureSpec.md.

    python Tools/ShadowGobo/make_gobo_flipbook.py --input take03.mov --start 4.0 --duration 15 --crop 1080:1080:420:0
    python Tools/ShadowGobo/make_gobo_flipbook.py --input take03.mov --dry-run          # the plan only, writes nothing
    python Tools/ShadowGobo/make_gobo_flipbook.py --self-test                          # synthetic video, +/- controls

WHAT IT DOES
  1. ffmpeg decodes [start, start + duration], crops (W:H:X:Y, or "square" = the centred square), resamples to --fps
     (6-12 = the stop-motion step; ffmpeg's fps filter drops/holds frames, so a variable-frame-rate iPhone file comes out
     constant), scales to a working square and converts to grey. Phone rotation metadata is applied by ffmpeg.
  2. Flat field: a CLEAN PLATE (the bright sheet with no puppet) is estimated per pixel, either from --plate-seconds of
     empty sheet filmed before the take (best), or as the --plate-percentile of the whole take, then blurred into a smooth
     illumination field. Each frame is divided by it, so a hot-spot centre and dark corners both read 1.0 ("sheet").
  3. ONE threshold for the whole take (Otsu on all frames, or --threshold): one value, so the matte never flickers.
     White = light passes (the sheet); black = blocked (the puppet). --invert swaps them.
  4. 3x3 median (grain), then an optional --feather px soft edge.
  5. Packs the frames row-major from the top-left into a square atlas of --atlas px (grid auto = the smallest square
     that holds them, or --grid CxR). Every cell keeps a --gutter of edge-replicated pixels so bilinear sampling at the
     cell border never bleeds into the next frame.
  6. Writes atlas PNG (8-bit grey), preview.gif at the playback rate, contact.png, optional per-frame masks (--frames-dir,
     for the MediaTexture / Img Media comparison route), and manifest.json with the light-function parameters.

Exit code 0 only when every step succeeded. Markers on stdout: GOBO_FLIPBOOK_PLAN | GOBO_FLIPBOOK_OK | GOBO_FLIPBOOK_FAILED |
GOBO_SELFTEST_OK | GOBO_SELFTEST_FAILED.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUT_ROOT = REPO / "DerivedAssets" / "ShadowGobo"
WORK_PX = 768                       # working square before the final per-cell resize


class GoboError(RuntimeError):
    pass


# ----------------------------------------------------------------------------------------------------------- ffmpeg
def tool(name):
    path = shutil.which(name)
    if not path:
        raise GoboError(f"{name} not found on PATH (winget install Gyan.FFmpeg)")
    return path


def probe(video):
    out = subprocess.run([tool("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate,avg_frame_rate,codec_name,pix_fmt,color_transfer:"
                          "stream_side_data=rotation:format=duration", "-of", "json", str(video)],
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise GoboError(f"ffprobe failed: {out.stderr.strip()}")
    info = json.loads(out.stdout)
    s = info["streams"][0]
    rot = 0
    for sd in s.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(sd["rotation"])
    w, h = int(s["width"]), int(s["height"])
    if rot % 180:                    # ffmpeg autorotates, so the decoded frame is the displayed one
        w, h = h, w
    return {"width": w, "height": h, "rotation": rot, "codec": s.get("codec_name"), "pix_fmt": s.get("pix_fmt"),
            "color_transfer": s.get("color_transfer"), "avg_frame_rate": s.get("avg_frame_rate"),
            "duration_s": float(info.get("format", {}).get("duration", 0.0) or 0.0)}


def crop_filter(crop, w, h):
    if not crop:
        return None, (w, h)
    if crop == "square":
        side = min(w, h)
        return f"crop={side}:{side}:{(w - side) // 2}:{(h - side) // 2}", (side, side)
    parts = [int(p) for p in crop.split(":")]
    if len(parts) != 4:
        raise GoboError(f"--crop must be W:H:X:Y or 'square', got {crop!r}")
    cw, ch, cx, cy = parts
    if cw <= 0 or ch <= 0 or cx < 0 or cy < 0 or cx + cw > w or cy + ch > h:
        raise GoboError(f"--crop {crop} falls outside the {w}x{h} frame")
    return f"crop={cw}:{ch}:{cx}:{cy}", (cw, ch)


def ffmpeg_cmd(video, start, duration, crop_vf, fps):
    # Scale the crop to fit the working square and pad with WHITE (= sheet = light passes), so a non-square crop is
    # letterboxed into light, not into a hard black frame edge.
    vf = [v for v in (crop_vf,) if v]
    vf += [f"fps={fps}", f"scale={WORK_PX}:{WORK_PX}:force_original_aspect_ratio=decrease:flags=area",
           f"pad={WORK_PX}:{WORK_PX}:(ow-iw)/2:(oh-ih)/2:color=white", "format=gray"]
    cmd = [tool("ffmpeg"), "-v", "error", "-nostdin"]
    if start:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(video)]
    if duration:
        cmd += ["-t", f"{duration:.3f}"]
    cmd += ["-an", "-vf", ",".join(vf), "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    return cmd


def decode(video, start, duration, crop_vf, fps):
    cmd = ffmpeg_cmd(video, start, duration, crop_vf, fps)
    out = subprocess.run(cmd, capture_output=True)
    if out.returncode != 0:
        raise GoboError(f"ffmpeg failed: {out.stderr.decode(errors='replace').strip()}")
    frame = WORK_PX * WORK_PX
    n = len(out.stdout) // frame
    if n == 0:
        raise GoboError("ffmpeg produced no frames (check --start/--duration)")
    return np.frombuffer(out.stdout[: n * frame], dtype=np.uint8).reshape(n, WORK_PX, WORK_PX).astype(np.float32) / 255.0


# ------------------------------------------------------------------------------------------------------ image maths
def box_blur(img, r):
    """Separable box blur of radius r (edge-replicated); three passes approximate a Gaussian."""
    if r < 1:
        return img
    out = img
    for _ in range(3):
        for axis in (0, 1):
            pad = [(0, 0), (0, 0)]
            pad[axis] = (r + 1, r)
            p = np.pad(out, pad, mode="edge")
            c = np.cumsum(p, axis=axis, dtype=np.float64)
            hi = np.take(c, np.arange(2 * r + 1, c.shape[axis]), axis=axis)
            lo = np.take(c, np.arange(0, c.shape[axis] - 2 * r - 1), axis=axis)
            out = ((hi - lo) / (2 * r + 1)).astype(np.float32)
    return out


def median3(img):
    p = np.pad(img, 1, mode="edge")
    h, w = img.shape
    stack = np.stack([p[y:y + h, x:x + w] for y in range(3) for x in range(3)])
    return np.median(stack, axis=0)


def otsu(values, bins=256):
    hist, edges = np.histogram(np.clip(values, 0.0, 1.0), bins=bins, range=(0.0, 1.0))
    hist = hist.astype(np.float64)
    mids = (edges[:-1] + edges[1:]) / 2
    w0 = np.cumsum(hist)
    w1 = w0[-1] - w0
    m0 = np.cumsum(hist * mids)
    mu0 = m0 / np.maximum(w0, 1)
    mu1 = (m0[-1] - m0) / np.maximum(w1, 1)
    between = w0 * w1 * (mu0 - mu1) ** 2
    return float(mids[int(np.argmax(between))])


def clean_plate(frames, plate_frames, percentile):
    src = plate_frames if plate_frames is not None and len(plate_frames) else frames
    step = max(1, len(src) // 64)             # a percentile over at most ~64 frames: memory, not accuracy
    plate = np.percentile(src[::step], percentile if plate_frames is None else 50, axis=0).astype(np.float32)
    return box_blur(plate, WORK_PX // 24)     # an illumination FIELD: no puppet edges, no grain


# --------------------------------------------------------------------------------------------------------- pipeline
def plan(args, info):
    crop_vf, (cw, ch) = crop_filter(args.crop, info["width"], info["height"])
    dur = args.duration or max(0.0, info["duration_s"] - (args.start or 0.0))
    n_est = int(math.floor(dur * args.fps + 1e-6)) if dur else None
    grid = parse_grid(args.grid, n_est or 1)
    cell = args.atlas // max(grid)
    capacity = grid[0] * grid[1]
    warnings = []
    if info.get("color_transfer") in ("arib-std-b67", "smpte2084"):
        warnings.append(f"HDR video ({info['color_transfer']}): film with HDR Video OFF; the threshold still works, but "
                        "the grey levels are not the sheet's")
    if n_est and n_est > capacity:
        warnings.append(f"{n_est} frames > {capacity} cells: the take will be TRUNCATED to {capacity / args.fps:.1f} s")
    if cell < 256:
        warnings.append(f"{cell} px cells are soft for a 6 m spot; raise --atlas to 8192 or lower --fps")
    if args.gutter * 4 > cell:
        warnings.append(f"gutter {args.gutter} px is large for {cell} px cells")
    return {"crop_vf": crop_vf, "crop_px": [cw, ch], "duration_s": round(dur, 3), "frames_est": n_est,
            "grid": list(grid), "cell_px": cell, "capacity": capacity, "warnings": warnings}


def parse_grid(spec, n):
    if spec and spec != "auto":
        c, r = (int(v) for v in spec.lower().split("x"))
        return c, r
    side = max(1, math.ceil(math.sqrt(n)))
    return side, side


def build(args, out_dir, info, p):
    frames = decode(args.input, args.start, args.duration, p["crop_vf"], args.fps)
    plate_frames = None
    if args.plate_seconds:
        plate_frames = decode(args.input, args.plate_start, args.plate_seconds, p["crop_vf"], args.fps)
    if args.no_flatfield:
        norm = frames
        plate_note = "none (control)"
    else:
        plate = clean_plate(frames, plate_frames, args.plate_percentile)
        norm = np.clip(frames / np.maximum(plate, 1e-3)[None], 0.0, 1.0)
        plate_note = (f"empty sheet {args.plate_start}+{args.plate_seconds}s, median" if plate_frames is not None
                      else f"take p{args.plate_percentile:g}")
    thr = otsu(norm[:, ::4, ::4].ravel()) if args.threshold == "auto" else float(args.threshold)
    n = len(frames)
    grid = parse_grid(args.grid, n)
    cols, rows = grid
    capacity = cols * rows
    truncated = max(0, n - capacity)
    n = min(n, capacity)
    cell = args.atlas // max(cols, rows)
    inner = cell - 2 * args.gutter
    if inner < 16:
        raise GoboError(f"cell {cell} px leaves {inner} px inside the gutter")
    # The atlas is exactly --atlas px square (a power of two); cells are floor(atlas / max(cols, rows)) px, so a grid
    # that does not divide it leaves an unused black strip at the right/bottom. The material steps by GoboCellUV.
    atlas = np.zeros((args.atlas, args.atlas), dtype=np.uint8)            # unused cells black (never sampled)
    masks, area = [], []
    for i in range(n):
        m = (median3(norm[i]) > thr).astype(np.float32)
        if args.invert:
            m = 1.0 - m
        if args.feather:
            m = box_blur(m, max(1, int(round(args.feather * WORK_PX / inner))))
        img = Image.fromarray((m * 255.0 + 0.5).astype(np.uint8)).resize((inner, inner), Image.LANCZOS)
        a = np.pad(np.asarray(img), args.gutter, mode="edge")
        r_, c_ = divmod(i, cols)
        atlas[r_ * cell:(r_ + 1) * cell, c_ * cell:(c_ + 1) * cell] = a
        masks.append(np.asarray(img))
        area.append(float((np.asarray(img) < 128).mean()))
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.name or Path(args.input).stem
    atlas_path = out_dir / f"T_Gobo_{stem}_{cols}x{rows}.png"
    Image.fromarray(atlas).save(atlas_path, optimize=True)
    preview = [Image.fromarray(mk).resize((256, 256), Image.BILINEAR) for mk in masks]
    preview[0].save(out_dir / "preview.gif", save_all=True, append_images=preview[1:], loop=0,
                    duration=int(round(1000 / args.fps)))
    thumbs = [Image.fromarray(mk).resize((96, 96), Image.BILINEAR) for mk in masks[:: max(1, n // 24)][:24]]
    sheet = Image.new("L", (96 * 6, 96 * math.ceil(len(thumbs) / 6)), 64)
    for k, t in enumerate(thumbs):
        sheet.paste(t, ((k % 6) * 96, (k // 6) * 96))
    sheet.save(out_dir / "contact.png")
    if args.frames_dir:
        fd = out_dir / "frames"
        fd.mkdir(exist_ok=True)
        for i, mk in enumerate(masks):
            Image.fromarray(mk).save(fd / f"gobo_{i:04d}.png")
    sha = hashlib.sha256()
    with open(args.input, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            sha.update(chunk)
    manifest = {
        "made": datetime.datetime.now().isoformat(timespec="seconds"), "tool": "Tools/ShadowGobo/make_gobo_flipbook.py",
        "source": {"path": str(args.input), "sha256": sha.hexdigest(), **info},
        "take": {"start_s": args.start, "duration_s": args.duration, "crop": args.crop, "fps": args.fps,
                 "frames_decoded": len(frames), "frames_packed": n, "frames_truncated": truncated},
        "matte": {"flat_field": plate_note, "threshold": round(thr, 4), "threshold_mode": args.threshold,
                  "invert": args.invert, "feather_px": args.feather, "blocked_area_min": round(min(area), 4),
                  "blocked_area_max": round(max(area), 4), "white_means": "light passes (sheet)"},
        "atlas": {"file": atlas_path.name, "px": [args.atlas, args.atlas], "cols": cols, "rows": rows, "cell_px": cell,
                  "gutter_px": args.gutter, "order": "row-major from the top-left (UE UV origin)"},
        # The MI parameters of M_LF_ShadowGobo (Docs/ShadowGoboPipeline_2026-10-06.md "The material").
        "light_function_params": {"GoboCols": cols, "GoboRows": rows, "GoboFrames": n, "GoboFPS": args.fps,
                                  "GoboGutterUV": round(args.gutter / cell, 6), "GoboCellUV": round(cell / args.atlas, 8),
                                  "GoboLoop": 1.0},
        "texture_settings": {"compression": "TC_Grayscale (or TC_Alphaless BC4)", "sRGB": False,
                             "mip_gen": "NoMipmaps", "never_stream": True, "filter": "Bilinear", "address": "Clamp"},
        "outputs": sorted(p_.name for p_ in out_dir.iterdir()),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest, masks


# -------------------------------------------------------------------------------------------------------- self-test
def synth_video(path, seconds=4.0, fps=30, w=640, h=360, seed=7):
    """A phone-like take of a backlit sheet: hot-spot centre / dark corners, grain, and a cat-head silhouette on a rod
    crossing left to right with a bob. 8-bit H.264, as an iPhone 'Most Compatible' file would decode."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r2 = ((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2
    sheet = 235.0 - 95.0 * np.clip(r2 / 2.0, 0, 1)         # 235 centre -> ~140 in the corners: over a stop of falloff
    cmd = [tool("ffmpeg"), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{w}x{h}", "-r", str(fps),
           "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", str(path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    n = int(seconds * fps)
    for i in range(n):
        t = i / (n - 1)
        cx, cy = 140 + t * (w - 280), h * 0.48 + 12 * math.sin(t * 6 * math.pi)
        head = (xx - cx) ** 2 + (yy - cy) ** 2 < 45 ** 2
        ear_l = (yy < cy - 25) & (yy > cy - 80) & (np.abs(xx - (cx - 28)) < (yy - (cy - 80)) * 0.4)
        ear_r = (yy < cy - 25) & (yy > cy - 80) & (np.abs(xx - (cx + 28)) < (yy - (cy - 80)) * 0.4)
        rod = (np.abs(xx - cx) < 3) & (yy > cy)
        img = sheet.copy()
        img[head | ear_l | ear_r | rod] = 28.0
        img += rng.normal(0, 6, size=img.shape)
        proc.stdin.write(np.clip(img, 0, 255).astype(np.uint8).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise GoboError(f"synthetic encode failed: {proc.stderr.read().decode(errors='replace')}")
    return {"frames": n, "fps": fps, "size": [w, h], "crop": f"{h}:{h}:{(w - h) // 2}:0"}


def self_test(args):
    root = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="gobo_selftest_"))
    root.mkdir(parents=True, exist_ok=True)
    video = root / "synthetic_take.mp4"
    syn = synth_video(video)
    checks, ok = [], True

    def check(name, cond, detail):
        nonlocal ok
        ok = ok and bool(cond)
        checks.append({"check": name, "pass": bool(cond), "detail": detail})

    def run(sub, **over):
        a = argparse.Namespace(**{**vars(args), "input": str(video), "start": 0.0, "duration": 0.0, "crop": "square",
                                  "fps": 8.0, "atlas": 2048, "grid": "auto", "gutter": 4, "threshold": "auto",
                                  "invert": False, "feather": 0.0, "plate_seconds": 0.0, "plate_start": 0.0,
                                  "plate_percentile": 90.0, "no_flatfield": False, "frames_dir": False,
                                  "name": sub, **over})
        info = probe(video)
        return build(a, root / sub, info, plan(a, info))

    # + : the default pipeline
    man, masks = run("plus")
    n_exp = int(syn["frames"] / syn["fps"] * 8)
    check("frame count = duration x fps (+-1)", abs(man["take"]["frames_packed"] - n_exp) <= 1,
          f"{man['take']['frames_packed']} vs {n_exp}")
    check("atlas is 2048 square", man["atlas"]["px"] == [2048, 2048], man["atlas"]["px"])
    binary = np.mean([((m < 8) | (m > 247)).mean() for m in masks])
    check("matte is hard (>= 97% of pixels at 0 or 255 per frame)", binary >= 0.97, round(float(binary), 4))
    corners = np.mean([np.concatenate([m[:6, :6].ravel(), m[:6, -6:].ravel(), m[-6:, :6].ravel(), m[-6:, -6:].ravel()]).mean()
                       for m in masks])
    check("dark corners of the sheet read as LIGHT after the flat field", corners > 240, round(float(corners), 1))
    xs = []
    for m in masks:
        ys_, xs_ = np.nonzero(m < 128)
        xs.append(float(xs_.mean()) if len(xs_) else float("nan"))
    moves = np.diff([x for x in xs if not math.isnan(x)])
    check("puppet crosses left to right (centroid rises every frame)", len(moves) > 3 and (moves > 0).mean() > 0.9,
          [round(x, 1) for x in xs[:6]])
    a_lo, a_hi = man["matte"]["blocked_area_min"], man["matte"]["blocked_area_max"]
    check("puppet area plausible (1%..30% of the cell)", 0.01 <= a_lo and a_hi <= 0.30, [a_lo, a_hi])
    atlas = np.asarray(Image.open(root / "plus" / man["atlas"]["file"]))
    c = man["atlas"]["cell_px"]
    g = man["atlas"]["gutter_px"]
    edge_equal = all(np.array_equal(atlas[r * c:(r + 1) * c, k * c:(k + 1) * c][g, :],
                                    atlas[r * c:(r + 1) * c, k * c:(k + 1) * c][0, :])
                     for r in range(man["atlas"]["rows"]) for k in range(man["atlas"]["cols"])
                     if r * man["atlas"]["cols"] + k < man["take"]["frames_packed"])
    check("every used cell's gutter replicates its edge (no bleed)", edge_equal, f"gutter {g}px")
    # - : the control. Without the flat field and at a fixed threshold, the dark corners must FAIL the corner check,
    # so the check above can fail and the flat field is what makes it pass.
    man_c, masks_c = run("minus_no_flatfield", no_flatfield=True, threshold="0.75")
    corners_c = np.mean([np.concatenate([m[:6, :6].ravel(), m[-6:, -6:].ravel()]).mean() for m in masks_c])
    check("CONTROL: without the flat field the corners go BLACK", corners_c < 128, round(float(corners_c), 1))
    report = {"ok": ok, "root": str(root), "synthetic": syn, "checks": checks}
    (root / "selftest_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    for row in checks:
        print(f"  [{'PASS' if row['pass'] else 'FAIL'}] {row['check']}: {row['detail']}")
    print(f"{'GOBO_SELFTEST_OK' if ok else 'GOBO_SELFTEST_FAILED'}|checks={len(checks)}|root={root}")
    return 0 if ok else 1


# ------------------------------------------------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--input", help="the phone video (.mov/.mp4)")
    ap.add_argument("--out", help=f"output folder (default {DEFAULT_OUT_ROOT}/<name>)")
    ap.add_argument("--name", help="asset stem (default: the video's stem)")
    ap.add_argument("--start", type=float, default=0.0, help="take start, s")
    ap.add_argument("--duration", type=float, default=0.0, help="take length, s (0 = to the end)")
    ap.add_argument("--crop", default="square", help="W:H:X:Y in displayed pixels, 'square' (centred), or '' for none")
    ap.add_argument("--fps", type=float, default=8.0, help="stop-motion rate, 6-12")
    ap.add_argument("--atlas", type=int, default=4096, help="atlas size px (4096 or 8192)")
    ap.add_argument("--grid", default="auto", help="CxR, or auto (smallest square)")
    ap.add_argument("--gutter", type=int, default=4, help="edge-replicated px around every cell")
    ap.add_argument("--threshold", default="auto", help="auto (Otsu, one value for the take) or 0..1 of the sheet level")
    ap.add_argument("--invert", action="store_true", help="white puppet = light (a 'light puppet')")
    ap.add_argument("--feather", type=float, default=1.0, help="soft edge, px of the final cell")
    ap.add_argument("--plate-seconds", type=float, default=0.0, help="seconds of EMPTY sheet to use as the clean plate")
    ap.add_argument("--plate-start", type=float, default=0.0, help="where that empty sheet starts, s")
    ap.add_argument("--plate-percentile", type=float, default=90.0, help="without an empty sheet: per-pixel percentile")
    ap.add_argument("--no-flatfield", action="store_true", help="skip the clean plate (control only)")
    ap.add_argument("--frames-dir", action="store_true", help="also write per-frame PNG masks (Img Media route)")
    ap.add_argument("--dry-run", action="store_true", help="probe and print the plan; write nothing")
    ap.add_argument("--self-test", action="store_true", help="synthetic take, full pipeline, +/- controls")
    args = ap.parse_args(argv)
    try:
        if args.self_test:
            return self_test(args)
        if not args.input:
            ap.error("--input is required (or --self-test)")
        if not 1.0 <= args.fps <= 30.0:
            raise GoboError("--fps must be 1..30 (6-12 is the stop-motion range)")
        info = probe(args.input)
        p = plan(args, info)
        out_dir = Path(args.out) if args.out else DEFAULT_OUT_ROOT / (args.name or Path(args.input).stem)
        print("GOBO_FLIPBOOK_PLAN|" + json.dumps({"source": info, **p, "out": str(out_dir),
                                                  "ffmpeg": " ".join(ffmpeg_cmd(args.input, args.start, args.duration,
                                                                                p["crop_vf"], args.fps))}))
        if args.dry_run:
            return 0
        manifest, _ = build(args, out_dir, info, p)
        print(f"GOBO_FLIPBOOK_OK|frames={manifest['take']['frames_packed']}|grid={manifest['atlas']['cols']}x"
              f"{manifest['atlas']['rows']}|cell={manifest['atlas']['cell_px']}|threshold={manifest['matte']['threshold']}"
              f"|truncated={manifest['take']['frames_truncated']}|out={out_dir}")
        return 0
    except GoboError as exc:
        print(f"GOBO_FLIPBOOK_FAILED|{exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
