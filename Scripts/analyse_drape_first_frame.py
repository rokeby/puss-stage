"""Read a drape_first_frame_<density>.json run and its screenshots, and name the first tick at which the drape is DRAWN.

    python Scripts/analyse_drape_first_frame.py dense sparse

The PIE harness (Saved/CodexSoftGoods/drape_first_frame_test.py) issues `shot` at chosen ticks after the Interaction's
first frame. The screenshots land in Saved/Screenshots/WindowsEditor/ as numbered ScreenShotNNNNN.png. The newest
len(shots) files written within a minute of the run's JSON are matched to shots_at_k, in order.
"Drawn": the fraction of curtain-red pixels in the central 60% of the frame (R > 1.5 G, R > 1.5 B, R > 20) is at
least half that of the tick-20 reference. The pre-registered reading is in the harness's docstring: drawn at tick 0 or
1 means no fault; later than tick 2 confirms; a DIFFERENT first tick between dense and sparse means the instrument is
in the answer.
"""
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "Saved" / "CodexSoftGoods"
SHOT_DIR = ROOT / "Saved" / "Screenshots" / "WindowsEditor"


def red_fraction(path):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    im = im.crop((int(w * 0.2), int(h * 0.2), int(w * 0.8), int(h * 0.8))).resize((240, 135))
    px = list(im.getdata())
    return sum(1 for r, g, b in px if r > 20 and r > 1.5 * g and r > 1.5 * b) / len(px)


def analyse(density):
    run = RUN_DIR / f"drape_first_frame_{density}.json"
    d = json.loads(run.read_text(encoding="utf-8"))
    t = run.stat().st_mtime
    shots = sorted((p for p in SHOT_DIR.glob("ScreenShot*.png") if abs(p.stat().st_mtime - t) < 60),
                   key=lambda p: p.name)[-len(d["shots_at_k"]):]
    if len(shots) != len(d["shots_at_k"]):
        return {"density": density, "error": f"found {len(shots)} screenshots for {len(d['shots_at_k'])} shots"}
    frac = {k: round(red_fraction(p), 3) for k, p in zip(d["shots_at_k"], shots)}
    ref = frac.get(20) or max(frac.values())
    drawn = sorted(k for k, f in frac.items() if ref and f >= 0.5 * ref)
    first_exists = next((r["k"] for r in d["rows"] if r["k"] is not None and r["drape_exists"]), None)
    dts = [r["dt_ms"] for r in d["rows"] if r["k"] is not None and r["k"] <= 8]
    return {"density": density, "red_fraction_by_k": frac, "first_drawn_k": drawn[0] if drawn else None,
            "first_actor_exists_k": first_exists, "frame_ms_k0_8": dts, "files": [p.name for p in shots],
            "note": d.get("note")}


def main():
    results = [analyse(x) for x in (sys.argv[1:] or ["dense", "sparse"])]
    for r in results:
        print(json.dumps(r))
    firsts = [r.get("first_drawn_k") for r in results if "error" not in r]
    if len(firsts) == 2 and firsts[0] != firsts[1]:
        print("VERDICT: the first-drawn tick DIFFERS between densities: the instrument is in the answer. Report that, not a count.")
    elif firsts and firsts[0] is not None:
        k = firsts[0]
        print("VERDICT: " + ("NO FAULT (drawn by tick 1)" if k <= 1 else "CONFIRMED (drawn later than tick 2)" if k > 2
                             else "BORDERLINE (tick 2)") + f"; first drawn at tick {k}")


if __name__ == "__main__":
    main()
