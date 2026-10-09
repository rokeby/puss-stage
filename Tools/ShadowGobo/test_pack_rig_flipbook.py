"""Offline +/- controls for pack_rig_flipbook.py (synthetic frames; writes only to a temp dir)."""
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).parent))
import pack_rig_flipbook as pk  # noqa: E402

R = []


def check(name, ok, detail="", kind="positive"):
    R.append((kind, name, bool(ok), detail))


def legacy_atlas(cells, atlas_px, gutter_px, blur_frac):
    """The pre-SDF hard-mode implementation, retained only as a byte regression oracle."""
    budget = pk.atlas_budget(len(cells), atlas_px)
    cols, cell_px = budget["cols"], budget["cell_px"]
    inner = cell_px - 2 * gutter_px
    sigma = max(0.5, blur_frac * inner)
    pad = int(np.ceil(3 * sigma))
    atlas = np.zeros((atlas_px, atlas_px, 3), dtype=np.uint8)
    atlas[..., 0] = atlas[..., 1] = 255
    for index, image in enumerate(cells):
        sharp = np.asarray(image.resize((inner, inner), Image.LANCZOS), dtype=np.uint8)
        padded = np.pad(sharp, pad, mode="edge")
        blur = np.asarray(Image.fromarray(padded).filter(ImageFilter.GaussianBlur(sigma)))[pad:-pad, pad:-pad]
        for channel, content in ((0, sharp), (1, blur)):
            tile = np.pad(content, gutter_px, mode="edge")
            row, column = divmod(index, cols)
            atlas[row * cell_px:(row + 1) * cell_px,
                  column * cell_px:(column + 1) * cell_px, channel] = tile
    return atlas


def edge_crossings(values, level=127.5):
    values = np.asarray(values, dtype=float)
    result = []
    for index in range(len(values) - 1):
        a, b = values[index] - level, values[index + 1] - level
        if a == 0:
            result.append(index + 0.5)
        elif a * b < 0:
            result.append(index + 0.5 + (-a / (b - a)))
    return result


tmp = Path(tempfile.mkdtemp(prefix="pack_test_"))
frames = tmp / "frames"
frames.mkdir()
# 10 frames at 8 fps: A A A B B A C C C A  -> 3 unique cells; events A,B,A,C,A
seq = "AAABBACCCA"
shapes = {"A": (40, 40, 90, 90), "B": (60, 30, 110, 80), "C": (20, 70, 70, 120)}
for i, ch in enumerate(seq):
    im = Image.new("L", (128, 128), 255)
    ImageDraw.Draw(im).ellipse(shapes[ch], fill=0)
    im.save(frames / ("f%04d.png" % i))
m = pk.pack(frames, tmp / "out", "T", 8, atlas_px=1024, gutter_px=8, blur_frac=0.03, preview=False)
check("P01 holds and repeats de-duplicated to 3 cells", m["take"]["frames_packed"] == 3, m["take"])
check("P02 schedule replays A,B,A,C,A at the right times",
      m["schedule"] == [[0.0, 0], [0.375, 1], [0.625, 0], [0.75, 2], [1.125, 0]], m["schedule"])
atlas = np.asarray(Image.open(tmp / "out" / m["atlas"]["file"]).convert("RGB")).astype(int)
cell, g = m["atlas"]["cell_px"], m["atlas"]["gutter_px"]
r_tile, g_tile = atlas[:cell, :cell, 0], atlas[:cell, :cell, 1]
check("P03 R is a hard silhouette (mostly 0/255)", ((r_tile < 8) | (r_tile > 247)).mean() > 0.97)
check("P04 G is blurred (many mid-greys) - control for P03", ((g_tile > 40) & (g_tile < 215)).mean() > 0.05)
check("P05 gutter replicates the cell edge (no bleed)", np.array_equal(r_tile[:g, g:-g], np.repeat(r_tile[g:g + 1, g:-g], g, 0)))
check("P06 unused cells pass light (255)", atlas[-1, -1, 0] == 255 and atlas[-1, -1, 1] == 255)
check("P07 manifest names the atlas file it wrote and its sha", (tmp / "out" / m["atlas"]["file"]).is_file()
      and len(m["sha256"]) == 64)
check("P10 manifest declares display fps", m["display_fps"] == 8.0, m.get("display_fps"))
budget_196 = pk.atlas_budget(196, 8192)
budget_197 = pk.atlas_budget(197, 8192)
check("P11 8192 supports about 200 cells at at least 560 px",
      budget_196["cols"] == 14 and budget_196["cell_px"] >= 560, budget_196)
check("P12 8192 support boundary is explicit",
      budget_197["cols"] == 15 and budget_197["cell_px"] < 560, budget_197)
legacy = legacy_atlas([Image.open(frames / ("f%04d.png" % seq.index(ch))).convert("L")
                       for ch in "ABC"], 1024, 8, 0.03)
legacy_path = tmp / "legacy_hard.png"
Image.fromarray(legacy, "RGB").save(legacy_path)
check("P13 hard mode atlas is byte-identical to the pre-SDF implementation",
      (tmp / "out" / m["atlas"]["file"]).read_bytes() == legacy_path.read_bytes())

# SDF +controls: a high-resolution synthetic disc crosses 0.5 at the analytic edge, and R/G share it.
source_px, inner = 512, 240
y, x = np.mgrid[:source_px, :source_px]
disc = ((((x + 0.5) - source_px / 2.0) ** 2 + ((y + 0.5) - source_px / 2.0) ** 2) <= 100.0 ** 2)
disc_image = Image.fromarray((disc * 255).astype(np.uint8), "L")
sdf_r, sdf_g = pk.sdf_channels(disc_image, inner, spread=6.0, wide=4.0)
r_edges = edge_crossings(sdf_r[inner // 2])
g_edges = edge_crossings(sdf_g[inner // 2])
expected = [inner * (source_px / 2.0 - 100.0) / source_px,
            inner * (source_px / 2.0 + 100.0) / source_px]
check("P14 SDF disc 0.5 contour is within 0.5 px of the silhouette edge",
      len(r_edges) == 2 and max(abs(a - b) for a, b in zip(r_edges, expected)) <= 0.5,
      {"crossings": r_edges, "expected": expected})
check("P15 narrow and wide SDF channels share the 0.5 edge",
      len(r_edges) == len(g_edges) == 2 and max(abs(a - b) for a, b in zip(r_edges, g_edges)) <= 0.05,
      {"R": r_edges, "G": g_edges})

# A two-cell-pixel blocked line retains two continuous crossings after SDF downsampling.
line_source = np.full((480, 480), 255, dtype=np.uint8)
line_source[:, 238:242] = 0
line_r, _line_g = pk.sdf_channels(Image.fromarray(line_source, "L"), 240)
line_edges = [edge_crossings(row) for row in line_r]
check("P16 2 px thin line keeps a continuous 0.5 contour",
      all(len(edges) == 2 and abs((edges[1] - edges[0]) - 2.0) <= 0.1 for edges in line_edges),
      line_edges[120])

# -control: a one-pixel source line at 2x is only 0.5 cell px and must emit the minimum-width warning.
subpixel_source = np.full((480, 480), 255, dtype=np.uint8)
subpixel_source[:, 240:241] = 0
measured_subpixel_width = int(np.count_nonzero(subpixel_source[240] < 128)) / 2.0
warning = pk.feature_width_warning(measured_subpixel_width, label="synthetic_line")
check("P17 -control 0.5 px line fails the min-width warning", warning is not None and "0.500px" in warning,
      warning, kind="negative")
# -control: a non-square frame must be refused
bad = tmp / "bad"
bad.mkdir()
Image.new("L", (100, 80), 255).save(bad / "f0000.png")
try:
    pk.pack(bad, tmp / "out_bad", "B", 8, preview=False)
    check("P08 -control non-square frame refused", False, "accepted", kind="negative")
except SystemExit as exc:
    check("P08 -control non-square frame refused", "not square" in str(exc), str(exc), kind="negative")
# -control: an empty folder must be refused
try:
    pk.pack(tmp / "nothing", tmp / "o2", "E", 8, preview=False)
    check("P09 -control empty folder refused", False, "accepted", kind="negative")
except SystemExit as exc:
    check("P09 -control empty folder refused", "no frames" in str(exc), str(exc), kind="negative")

# -control: SDF packing refuses a source rendered at only the cell's 1x inner size.
one_x = tmp / "one_x"
one_x.mkdir()
Image.new("L", (240, 240), 255).save(one_x / "f0000.png")
try:
    pk.pack(one_x, tmp / "out_one_x", "OneX", 8, atlas_px=256, gutter_px=8,
            preview=False, sdf=True)
    check("P18 -control 1x SDF source refused", False, "accepted", kind="negative")
except SystemExit as exc:
    check("P18 -control 1x SDF source refused", "at least 2x" in str(exc), str(exc), kind="negative")

# SDF atlases must not use the material's 5-tap BlurUV (atlas-uv taps average a distance field across a slit).
two_x = tmp / "two_x"
two_x.mkdir()
src = Image.new("L", (480, 480), 0)
ImageDraw.Draw(src).rectangle((236, 60, 244, 420), fill=255)     # an 8 px light slit at 2x = 4 px in the cell
src.save(two_x / "f0000.png")
sm = pk.pack(two_x, tmp / "out_two_x", "TwoX", 8, atlas_px=256, gutter_px=8, preview=False, sdf=True)
check("P19 SDF manifest disables the 5-tap BlurUV", sm["light_function_params"].get("BlurUV") == 0.0,
      sm["light_function_params"])
_r, _g = pk.sdf_channels(src, 240)
row = np.asarray(_r, dtype=float)[120]
row = row / 255.0 if row.max() > 1.0 else row   # sdf_channels returns 8-bit values
centre = int(np.argmax(row))
check("P20 a 4 px SDF slit is light at its centre with no tap blur", row[centre] > 0.5, float(row[centre]))
taps = (row[centre] + row[centre - 6] + row[centre + 6] + row[centre] + row[centre]) / 5.0   # L/R taps 6 px out
check("P21 -control: 6 px atlas-uv taps (BlurUV 0.00075 at 8192) close the slit", taps < 0.5, float(taps),
      kind="negative")

passed = sum(ok for _, _, ok, _ in R)
for kind, n, ok, d in R:
    if not ok:
        print("FAIL", kind, n, d)
positive = [item for item in R if item[0] == "positive"]
negative = [item for item in R if item[0] == "negative"]
print("PACK_HARNESS|positive=%d/%d|negative=%d/%d|total=%d/%d" % (
    sum(ok for _kind, _name, ok, _detail in positive), len(positive),
    sum(ok for _kind, _name, ok, _detail in negative), len(negative), passed, len(R)))
sys.exit(0 if passed == len(R) else 1)
