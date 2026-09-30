"""Summarise the 30 Sep overnight bakes against Gary's acceptance test, and compare the two drapes' weight (offline).

    python Scripts/report_overnight_bakes.py [drape_a] [drape_b] [traveller]

Defaults: final3_settled, final4_dense_pleats, final5_traveller (Saved/CodexSoftGoods/DropBake/<id>.json).

The ACCEPTANCE TEST (Gary, 30 Sep: "a still acceptable curtain that can be extended in its stillness for as long as I
need"): `still_window_max_mm`, the largest single-vertex move per frame over the second before anything moves, must be
under STILL_LIMIT_MM. The traveller must pass it again at the END (`end_still_max_mm`), so its open stacks can be held.
The settle curve (worst move per second from the end of the gather) shows whether a fail is converging or stuck.

THE WEIGHT QUESTION (does ~40% more pleats still read as the same weight?) is answered with numbers that depend on
weight, in addition to pictures:
  - fall timing: seconds from release until the TOP of the cloth passes 1.8 m and 1.35 m (eye height);
  - the landing: the centre-of-mass rebound after the first touchdown;
  - the pile: height, depth, width, layers (cloth area / footprint) and fold size.
The mass per square metre is identical by construction, so the fall should match. What can change is how heavy the
pleats LOOK: shallower folds read as thinner cloth. That is a judgement on the side-by-side sheet, flagged as such.
Writes <OUT>/overnight_report.md and <OUT>/overnight_compare_<a>_<b>.png.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Saved" / "CodexSoftGoods" / "DropBake"
STILL_LIMIT_MM = 2.0
FPS = 30.0
# The drop bake does not record CURTAIN_FOLD_WAVELENGTH; these are the launch values.
WAVELENGTH_M = {"final3_settled": 0.85, "final4_dense_pleats": 0.607}


def load(drop_id):
    p = OUT / f"{drop_id}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def verdict(mm):
    if mm is None:
        return "NOT MEASURED"
    return f"{mm:.2f} mm/frame, {'PASS' if mm < STILL_LIMIT_MM else 'FAIL'} (limit {STILL_LIMIT_MM})"


def settle_curve(series, start, end):
    """Worst move in each 30-frame second over [start, end): shows whether the settle converged."""
    out = []
    for s in range(start, end, 30):
        w = [m for f, m in series if s <= f < s + 30]
        if w:
            out.append(f"{(s - start) / FPS:.0f}s:{max(w):.1f}")
    return " ".join(out)


def fall_timing(d):
    """Seconds from release until the cloth's TOP passes 1.8 m and 1.35 m; COM rebound after the first minimum."""
    top, com = d.get("top_z", []), d.get("com_z", [])
    first = d["release_frame"] - 1                 # top_z/com_z start at RELEASE_FRAME - 1 (lift included)
    out = {}
    for label, h in (("top_below_1.8m_s", 1.8), ("top_below_1.35m_s", 1.35)):
        hit = next((i for i, z in enumerate(top) if z < h), None)
        out[label] = round((first + hit - d["release_frame"]) / FPS, 2) if hit is not None else None
    if com:
        # The LANDING is the first frame the centre of mass stops falling; the rebound is how far it rises in the
        # 3 s after (the "bounce" of 28 Sep). The global minimum is usually the last frame, as the pile keeps sinking.
        low = next((i for i in range(1, len(com) - 1) if com[i] <= com[i - 1] and com[i + 1] > com[i] + 1e-4), None)
        low = low if low is not None else min(range(len(com)), key=lambda i: com[i])
        out["com_landing_m"] = com[low]
        out["com_landing_at_s"] = round((first + low - d["release_frame"]) / FPS, 2)
        out["com_rebound_m"] = round(max(com[low:low + 90]) - com[low], 3)
        out["com_final_m"] = com[-1]
    return out


def drape_rows(d):
    final = d["checkpoints"][str(d["frames"])]
    hang = d["checkpoints"].get(str(d["release_frame"] - 1), {})
    rows = {"still (hold window)": verdict(d.get("still_window_max_mm")),
            "still mean": d.get("still_window_mean_mm"),
            "settle curve (worst mm per second after the gather)": settle_curve(d.get("still_mm", []), d["gather_frames"] if "gather_frames" in d else 61, d["release_frame"]) if d.get("still_mm") else None,
            "fold wavelength (m)": WAVELENGTH_M.get(d["id"], "0.85 unless set in the launch env"),
            "mass per vertex (kg)": d.get("mass_per_vertex"), "released": d.get("released"),
            "hang: hem spread y (m)": hang.get("aabb_m", {}).get("y"), "hang: x extent (m)": hang.get("aabb_m", {}).get("x"),
            "pile height P95 (m)": final.get("height_m"), "pile depth (m)": final.get("depth_m"),
            "pile width (m)": final.get("width_m"), "layers": final.get("layers"), "fold size (m)": final.get("fold_size_m"),
            "settled": d.get("settled")}
    rows.update(fall_timing(d))
    return rows


def traveller_rows(d):
    rows = {"still (hold window, before opening)": verdict(d.get("still_window_max_mm")),
            "still (END window, open stacks)": verdict(d.get("end_still_max_mm")),
            "settle curve before opening": settle_curve(d.get("move_mm", []), d["gather_frames"] + 1, d["open_start"]),
            "settle curve after opening": settle_curve(d.get("move_mm", []), d["open_end"], d["frames"] + 1),
            "opening": f"frames {d['open_start']}-{d['open_end']} ({d['open_frames'] / FPS:.0f} s)",
            "design stack per side / clear opening (m)": f"{d['design_stack_width_per_side_m']} / {d['design_clear_opening_m']}",
            "hem floor contact frames": d.get("hem_floor_contact_frames"), "rig limits": d.get("rig_limits")}
    for f, cp in sorted(d["checkpoints"].items(), key=lambda kv: int(kv[0])):
        t = cp["traveller"]
        rows[f"frame {f}"] = (f"clear opening {t['clear_opening_all_m']} m (heading {t['clear_opening_heading_m']}); "
                              f"stacks L {t['left']['width_m']} x {t['left']['depth_p2_p98_m']} m, "
                              f"R {t['right']['width_m']} x {t['right']['depth_p2_p98_m']} m; hem min z {t['hem_min_z_m']}")
    return rows


def tile(path, w=640):
    if not path.exists():
        im = Image.new("RGB", (w, w * 9 // 16), (60, 60, 60))
        ImageDraw.Draw(im).text((10, 10), f"missing: {path.name}", fill="white")
        return im
    im = Image.open(path).convert("RGB")
    return im.resize((w, int(im.height * w / im.width)))


def compare_sheet(a, b, da, db):
    """Side by side: a on the left, b on the right; the hang, the fall at matched times after release, the pile."""
    font = ImageFont.load_default(size=18)
    rows = [("hang (before release)", f"{a}_hang34.png", f"{b}_hang34.png")]
    for dt in (0.5, 1.0, 1.5, 2.0, 3.0, 5.0):
        rows.append((f"{dt:.1f} s after release", None, dt))
    rows += [("pile, 3/4", f"{a}_34.png", f"{b}_34.png"), ("pile, side", f"{a}_side.png", f"{b}_side.png"),
             ("pile, front", f"{a}_front.png", f"{b}_front.png")]
    tiles = []
    for label, pa, pb in rows:
        if pa is None:                              # a clip frame at release + dt (clip starts at CLIP_START, step 1)
            ims = []
            for i, d in ((a, da), (b, db)):
                start = d.get("show_start") or 1
                n = int(round(d["release_frame"] + pb * FPS)) - start
                ims.append(tile(OUT / f"{i}_clip_34" / f"f{n:04d}.png"))
        else:
            ims = [tile(OUT / pa), tile(OUT / pb)]
        tiles.append((label, ims))
    h = sum(max(im.height for im in ims) + 30 for _, ims in tiles) + 40
    sheet = Image.new("RGB", (1280 + 10, h), "white")
    dr = ImageDraw.Draw(sheet)
    dr.text((10, 8), f"LEFT {a}    RIGHT {b}", fill="black", font=font)
    y = 40
    for label, ims in tiles:
        dr.text((10, y), label, fill="black", font=font)
        y += 26
        for k, im in enumerate(ims):
            sheet.paste(im, (k * 650, y))
        y += max(im.height for im in ims) + 4
    path = OUT / f"overnight_compare_{a}_{b}.png"
    sheet.save(path)
    return path


def main():
    a, b, t = (sys.argv[1:4] + ["final3_settled", "final4_dense_pleats", "final5_traveller"][len(sys.argv[1:4]):])
    lines = ["# Overnight bakes, 30 Sep", "", f"Acceptance: still_window_max_mm < {STILL_LIMIT_MM} mm/frame.", ""]
    da, db, dt = load(a), load(b), load(t)
    for name, d, fn in ((a, da, drape_rows), (b, db, drape_rows), (t, dt, traveller_rows)):
        lines.append(f"## {name}")
        if d is None:
            lines += ["not landed yet", ""]
            continue
        for k, v in fn(d).items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")
    if da and db:
        lines.append(f"Compare sheet: {compare_sheet(a, b, da, db)}")
    report = OUT / "overnight_report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"REPORT|{report}")


if __name__ == "__main__":
    main()
