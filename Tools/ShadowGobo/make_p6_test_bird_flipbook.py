#!/usr/bin/env python3
"""Generate the P6 24-frame hand-shadow bird test atlas with Pillow only.

White passes the light function and black blocks it.  The atlas is deliberately
small in time (3 seconds at 8 fps) but full-size in texture space (2048 square),
so the conductor can import it without first filming a take.

Run:
    python Tools/ShadowGobo/make_p6_test_bird_flipbook.py
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw


ATLAS_PX = 2048
COLS, ROWS = 6, 4
FRAMES = 24
FPS = 8.0
GUTTER = 8
OUT = Path(__file__).resolve().parent / "P6_TestBird"


def _frame(index: int, size: int) -> Image.Image:
    """A simple, readable hand-shadow bird: body, head/beak, rod and flapping wings."""
    hi = size * 3
    image = Image.new("L", (hi, hi), 255)
    draw = ImageDraw.Draw(image)
    phase = 2.0 * math.pi * index / FRAMES
    cx = hi * (0.48 + 0.035 * math.sin(phase))
    cy = hi * (0.50 + 0.018 * math.sin(phase * 2.0))
    flap = math.sin(phase * 2.0)

    # Visible operating rod: appropriate to the show's exposed-mechanism register.
    rod_w = max(3, int(hi * 0.012))
    draw.line((cx - hi * 0.02, cy + hi * 0.10, cx - hi * 0.20, hi * 0.98), fill=18, width=rod_w)
    draw.ellipse((cx - hi * 0.15, cy - hi * 0.095, cx + hi * 0.15, cy + hi * 0.095), fill=12)
    draw.ellipse((cx + hi * 0.08, cy - hi * 0.14, cx + hi * 0.23, cy + hi * 0.01), fill=12)
    draw.polygon([(cx + hi * 0.20, cy - hi * 0.09), (cx + hi * 0.34, cy - hi * 0.04),
                  (cx + hi * 0.20, cy + hi * 0.005)], fill=12)
    draw.ellipse((cx + hi * 0.165, cy - hi * 0.095, cx + hi * 0.182, cy - hi * 0.078), fill=245)

    lift = hi * (0.19 + 0.12 * flap)
    drop = hi * (0.13 - 0.07 * flap)
    draw.polygon([(cx - hi * 0.02, cy), (cx - hi * 0.32, cy - lift),
                  (cx - hi * 0.47, cy - lift * 0.58), (cx - hi * 0.21, cy + drop),
                  (cx, cy + hi * 0.06)], fill=12)
    draw.polygon([(cx + hi * 0.03, cy), (cx + hi * 0.16, cy - lift * 0.85),
                  (cx + hi * 0.29, cy - lift * 0.52), (cx + hi * 0.20, cy + drop * 0.85),
                  (cx, cy + hi * 0.06)], fill=12)
    return image.resize((size, size), Image.Resampling.LANCZOS)


def generate(out: Path = OUT) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    cell = ATLAS_PX // max(COLS, ROWS)
    inner = cell - 2 * GUTTER
    atlas = Image.new("L", (ATLAS_PX, ATLAS_PX), 0)
    frames = []
    for index in range(FRAMES):
        frame = _frame(index, inner)
        padded = Image.new("L", (cell, cell), 255)
        padded.paste(frame, (GUTTER, GUTTER))
        # Replicate the cell edge into its gutter.  The background is white, so
        # explicit replication and white padding are equivalent for this plate.
        col, row = index % COLS, index // COLS
        atlas.paste(padded, (col * cell, row * cell))
        frames.append(frame)

    atlas_name = f"T_Gobo_P6_TestBird_{COLS}x{ROWS}.png"
    atlas_path = out / atlas_name
    atlas.save(atlas_path, optimize=True)

    preview = [f.resize((320, 320), Image.Resampling.LANCZOS) for f in frames]
    preview[0].save(out / "preview.gif", save_all=True, append_images=preview[1:], loop=0,
                    duration=round(1000 / FPS), optimize=False)
    contact = Image.new("L", (COLS * 192, ROWS * 192), 64)
    for index, frame in enumerate(frames):
        contact.paste(frame.resize((192, 192), Image.Resampling.LANCZOS),
                      ((index % COLS) * 192, (index // COLS) * 192))
    contact.save(out / "contact.png", optimize=True)

    atlas_sha = hashlib.sha256(atlas_path.read_bytes()).hexdigest()
    manifest = {
        "schema_version": 1,
        "generator": "Tools/ShadowGobo/make_p6_test_bird_flipbook.py",
        "description": "24-frame hand-shadow bird with visible rod; white passes, black blocks",
        "take": {"fps": FPS, "frames_packed": FRAMES, "duration_s": FRAMES / FPS},
        "atlas": {"file": atlas_name, "px": [ATLAS_PX, ATLAS_PX], "cols": COLS, "rows": ROWS,
                  "cell_px": cell, "gutter_px": GUTTER, "order": "row-major from top-left"},
        "light_function_params": {
            "Cols": float(COLS), "Rows": float(ROWS), "Frames": float(FRAMES),
            "GutterUV": GUTTER / cell, "CellUV": cell / ATLAS_PX,
            "BlurUV": 0.00075, "Softness": 0.08, "Contrast": 1.35, "Depth": 1.0,
            "Scale": 1.0, "FlipU": 0.0, "FlipV": 0.0,
        },
        "texture_settings": {"compression": "TC_Grayscale", "sRGB": False,
                             "mip_gen": "NoMipmaps", "never_stream": True,
                             "filter": "Bilinear", "address": "Clamp"},
        "sha256": atlas_sha,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"P6_TEST_GOBO_OK|frames={FRAMES}|atlas={ATLAS_PX}|grid={COLS}x{ROWS}|cell={cell}|out={out}")
    return manifest


if __name__ == "__main__":
    generate()
