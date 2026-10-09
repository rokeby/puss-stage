"""Offline +/- controls for pack_rig_flipbook.py (synthetic frames; writes only to a temp dir)."""
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
import pack_rig_flipbook as pk  # noqa: E402

R = []


def check(name, ok, detail=""):
    R.append((name, bool(ok), detail))


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
# -control: a non-square frame must be refused
bad = tmp / "bad"
bad.mkdir()
Image.new("L", (100, 80), 255).save(bad / "f0000.png")
try:
    pk.pack(bad, tmp / "out_bad", "B", 8, preview=False)
    check("P08 -control non-square frame refused", False, "accepted")
except SystemExit as exc:
    check("P08 -control non-square frame refused", "not square" in str(exc), str(exc))
# -control: an empty folder must be refused
try:
    pk.pack(tmp / "nothing", tmp / "o2", "E", 8, preview=False)
    check("P09 -control empty folder refused", False, "accepted")
except SystemExit as exc:
    check("P09 -control empty folder refused", "no frames" in str(exc), str(exc))

passed = sum(ok for _, ok, _ in R)
for n, ok, d in R:
    if not ok:
        print("FAIL", n, d)
print("PACK_HARNESS|pass=%d|fail=%d" % (passed, len(R) - passed))
sys.exit(0 if passed == len(R) else 1)
