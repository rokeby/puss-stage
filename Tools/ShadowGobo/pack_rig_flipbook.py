"""Pack rendered puppet frames into a gobo flipbook atlas for animated_gobo.py.

Input: a folder of equally sized square PNG frames (white = light passes, black = blocked), rendered at a fixed fps
(e.g. by Tools/ShadowGobo/Puppets/boy_rig.py render_clip).  Identical frames (holds, repeated poses) are packed ONCE;
the manifest's "schedule" ([[seconds, cell], ...]) replays them, which animated_gobo.py keys as CONSTANT (stepped)
MPC Frame keys.

Hard-mode atlas channels: R = the sharp frame, G = the same frame pre-blurred (defocus), B = 0.  SDF mode instead
stores signed distance in R and the same zero crossing with a wider spread in G.  Each cell carries an edge-replicated
gutter so bilinear taps never read the neighbouring cell.

    python pack_rig_flipbook.py <frames_dir> <out_dir> --name boy_rub --fps 25 [--atlas 8192] [--sdf]
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage


MIN_SDF_RENDER_SCALE = 2.0


def atlas_budget(cell_count, atlas_px):
    if cell_count < 1:
        raise ValueError("cell_count must be positive")
    cols = int(math.ceil(math.sqrt(cell_count)))
    rows = int(math.ceil(cell_count / float(cols)))
    return {"atlas_px": int(atlas_px), "cells": int(cell_count), "cols": cols, "rows": rows,
            "cell_px": int(atlas_px) // cols}


def signed_distance(transmission):
    """Signed pixel distance, positive in light, measured at the source resolution."""
    light = np.asarray(transmission) > 127
    return ndimage.distance_transform_edt(light) - ndimage.distance_transform_edt(~light)


def sdf_channels(image, inner_px, spread=6.0, wide=4.0):
    """Encode an oversampled transmission image as narrow/wide SDF channels."""
    if spread <= 0:
        raise ValueError("spread must be positive")
    if wide < 1:
        raise ValueError("wide must be at least 1")
    required = int(math.ceil(MIN_SDF_RENDER_SCALE * inner_px))
    if image.width < required or image.height < required:
        raise SystemExit("SDF source must be rendered at least 2x the cell inner size (%dx%d required, got %dx%d)" %
                         (required, required, image.width, image.height))
    sd_source = signed_distance(np.asarray(image.convert("L"), dtype=np.uint8))
    sd_cell = np.asarray(Image.fromarray(sd_source.astype(np.float32), mode="F").resize(
        (inner_px, inner_px), Image.BILINEAR), dtype=np.float64)
    sd_cell *= inner_px / float(image.width)
    narrow = np.clip(0.5 + sd_cell / (2.0 * spread), 0.0, 1.0)
    broad = np.clip(0.5 + sd_cell / (2.0 * spread * wide), 0.0, 1.0)
    return (np.rint(narrow * 255.0).astype(np.uint8),
            np.rint(broad * 255.0).astype(np.uint8))


def feature_width_warning(width_px, minimum_px=2.0, label="feature"):
    """Return a stable warning string when an intended feature is below the cell-space floor."""
    if width_px + 1e-9 < minimum_px:
        return "MIN_FEATURE_WIDTH|%s=%.3fpx|required=%.3fpx" % (label, width_px, minimum_px)
    return None


def pack(frames_dir, out_dir, name, fps, atlas_px=4096, gutter_px=8, blur_frac=0.012, preview=True,
         sdf=False, spread=6.0, wide=4.0):
    files = sorted(Path(frames_dir).glob("*.png"))
    if not files:
        raise SystemExit("no frames in %s" % frames_dir)
    cells, index, schedule = [], {}, []
    for i, f in enumerate(files):
        im = Image.open(f).convert("L")
        if im.size[0] != im.size[1]:
            raise SystemExit("frame %s is not square: %s" % (f.name, im.size))
        key = hashlib.sha256(im.tobytes()).hexdigest()
        if key not in index:
            index[key] = len(cells)
            cells.append(im)
        cell = index[key]
        if not schedule or schedule[-1][1] != cell:
            schedule.append([round(i / float(fps), 6), cell])
    n = len(cells)
    budget = atlas_budget(n, atlas_px)
    cols, rows, cell_px = budget["cols"], budget["rows"], budget["cell_px"]
    if rows * cell_px > atlas_px:
        raise SystemExit("grid does not fit")
    inner = cell_px - 2 * gutter_px
    if inner < 1:
        raise SystemExit("gutter leaves no cell interior")
    sigma = max(0.5, blur_frac * inner)
    pad = int(math.ceil(3 * sigma))
    atlas = np.zeros((atlas_px, atlas_px, 3), dtype=np.uint8)
    atlas[..., 0] = atlas[..., 1] = 255  # unused cells pass light
    for c, im in enumerate(cells):
        if sdf:
            channel_images = sdf_channels(im, inner, spread, wide)
        else:
            sharp = np.asarray(im.resize((inner, inner), Image.LANCZOS), dtype=np.uint8)
            padded = np.pad(sharp, pad, mode="edge")
            blur = np.asarray(Image.fromarray(padded).filter(ImageFilter.GaussianBlur(sigma)))[pad:-pad, pad:-pad]
            channel_images = sharp, blur
        for ch, img in enumerate(channel_images):
            tile = np.pad(img, gutter_px, mode="edge")
            r, q = divmod(c, cols)
            atlas[r * cell_px:(r + 1) * cell_px, q * cell_px:(q + 1) * cell_px, ch] = tile
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    atlas_name = "T_Gobo_%s_%dx%d.png" % (name, cols, rows)
    Image.fromarray(atlas, "RGB").save(out / atlas_name)
    sha = hashlib.sha256((out / atlas_name).read_bytes()).hexdigest()
    duration = len(files) / float(fps)
    channels = ({"R": "SDF: 0.5 + signed_distance_px / (2 * %.3f), positive in light" % spread,
                 "G": "SDF: 0.5 + signed_distance_px / (2 * %.3f * %.3f), same 0.5 edge" % (spread, wide),
                 "B": "unused"}
                if sdf else
                {"R": "sharp", "G": "blur sigma %.2f px" % sigma, "B": "unused"})
    light_params = {"Cols": float(cols), "Rows": float(rows), "Frames": float(n),
                    "GutterUV": gutter_px / float(cell_px), "CellUV": cell_px / float(atlas_px)}
    if sdf:
        light_params["Softness"] = 0.02
        # The material's 5-tap BlurUV is in ATLAS uv (0.00075 = ~6 px at 8192): averaged across a distance field it
        # closes slits narrower than ~2 taps.  Distance-field edges need no tap blur (measured 9 Oct, sdf_proto/
        # pg4_check_zoom_blur0.png): defocus comes from the G channel instead.
        light_params["BlurUV"] = 0.0
    atlas_manifest = {"file": atlas_name, "px": [atlas_px, atlas_px], "cols": cols, "rows": rows,
                      "cell_px": cell_px, "gutter_px": gutter_px,
                      "order": "row-major from the top-left", "channels": channels}
    manifest = {
        "schema_version": 3, "generator": "Tools/ShadowGobo/pack_rig_flipbook.py", "name": name,
        "display_fps": float(fps),
        "take": {"fps": float(fps), "frames_packed": n, "frames_rendered": len(files), "duration_s": duration},
        "atlas": atlas_manifest,
        "light_function_params": light_params,
        "schedule": schedule,
        "cell_budget": {str(size): atlas_budget(n, size) for size in (4096, 8192)},
        "texture_settings": {"compression": "TC_BC7", "sRGB": False, "mip_gen": "NoMipmaps", "never_stream": True,
                             "filter": "Bilinear", "address": "Clamp"},
        "sha256": sha,
    }
    if sdf:
        manifest["atlas"]["inner_px"] = inner
        manifest["atlas"]["encoding"] = {
            "type": "signed_distance", "edge": 0.5, "positive": "light",
            "spread_px": float(spread), "wide_multiplier": float(wide),
            "minimum_source_scale": MIN_SDF_RENDER_SCALE,
            "source_px": list(cells[0].size),
        }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if preview:
        thumbs = [c.resize((160, 160)) for c in cells]
        sheet = Image.new("L", (160 * cols, 160 * rows), 128)
        for c, t in enumerate(thumbs):
            sheet.paste(t, ((c % cols) * 160, (c // cols) * 160))
        sheet.save(out / "cells_contact.png")
    return manifest


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("frames_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--name", required=True)
    ap.add_argument("--fps", type=float, required=True)
    ap.add_argument("--atlas", type=int, default=4096)
    ap.add_argument("--gutter", type=int, default=8)
    ap.add_argument("--blur", type=float, default=0.012)
    ap.add_argument("--sdf", action="store_true")
    ap.add_argument("--spread", type=float, default=6.0)
    ap.add_argument("--wide", type=float, default=4.0)
    a = ap.parse_args()
    m = pack(a.frames_dir, a.out_dir, a.name, a.fps, a.atlas, a.gutter, a.blur,
             sdf=a.sdf, spread=a.spread, wide=a.wide)
    print("PACKED|cells=%d|rendered=%d|grid=%dx%d|cell_px=%d|schedule_events=%d|atlas=%s" % (
        m["take"]["frames_packed"], m["take"]["frames_rendered"], m["atlas"]["cols"], m["atlas"]["rows"],
        m["atlas"]["cell_px"], len(m["schedule"]), m["atlas"]["file"]))
