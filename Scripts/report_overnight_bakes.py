"""Judge baked curtains against the 30 Sep acceptance test, offline, so a number decides what is placed.

    python Scripts/report_overnight_bakes.py [--ref final2_stage_v2] [--sheet a,b] id [id ...]

Gary is away for twelve hours. His brief: "the correct outcome for the curtains ... in terms of structured hanging
profile, the good fall we already got, ideally a couple of versions". The Conductor's test has three parts, and ALL
must pass before anything is placed:
  1. STILL: still_window_max_mm < STILL_LIMIT_MM over the hold window before anything moves. The traveller must also
     pass at the END, so its open stacks can be held. settle_to_2mm_s separates "never settles" from "the window
     opened too early".
  2. HANG: the bake's own hang_profile.pass. That means flare at most 1.15 at the Opening's width, and fold count kept
     at least 0.75 and depth kept at least 0.5 at 75/50/25% of the height, against the heading's.
  3. PILE, the approved fall preserved: height, depth, width, layers and fold size each within PILE_TOL of the
     reference. The reference is final2 (Gary: "the animation, the feel, looks good") for full-width Opening drapes; a
     strip is judged against its own strip control.
The fall timing (top below 1.8 m and 1.35 m) and the landing rebound are reported alongside, since they are what
"reads heavy" is made of. Writes <OUT>/acceptance_report.md, plus a side-by-side sheet for --sheet a,b.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Saved" / "CodexSoftGoods" / "DropBake"
STILL_LIMIT_MM = 2.0
PILE_TOL = 0.25                      # provisional: each pile number within +-25% of the reference's
PILE_KEYS = ("height_m", "depth_m", "width_m", "layers", "fold_size_m")
FPS = 30.0


def load(drop_id):
    p = OUT / f"{drop_id}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def fall_timing(d):
    top, com = d.get("top_z", []), d.get("com_z", [])
    first = d["release_frame"] - 1
    out = {}
    for label, h in (("top_below_1.8m_s", 1.8), ("top_below_1.35m_s", 1.35)):
        hit = next((i for i, z in enumerate(top) if z < h), None)
        out[label] = round((first + hit - d["release_frame"]) / FPS, 2) if hit is not None else None
    if com:
        low = next((i for i in range(1, len(com) - 1) if com[i] <= com[i - 1] and com[i + 1] > com[i] + 1e-4), None)
        low = low if low is not None else min(range(len(com)), key=lambda i: com[i])
        out["landing_at_s"] = round((first + low - d["release_frame"]) / FPS, 2)
        out["landing_rebound_m"] = round(max(com[low:low + 90]) - com[low], 3)
    return out


def pile(d):
    return d["checkpoints"][str(d["frames"])]


def judge_drape(d, ref):
    still = d.get("still_window_max_mm")
    hp = d.get("hang_profile") or {}
    verdict = {"still": still is not None and still < STILL_LIMIT_MM, "hang": bool(hp.get("pass"))}
    # BULGE (30 Sep): the flare compares only hem with heading, so a curtain held at both ends that BARRELS out at
    # mid-height (the hem guide on sw_b5_g07) read 1.00. Use the widest sampled row instead, converted to the Opening
    # width the same way as the flare.
    rows = hp.get("rows", {})
    if rows:
        extra = max(r["width_m"] for r in rows.values()) - rows["heading"]["width_m"]
        hp["bulge_at_opening_width"] = round((17.77 + max(0.0, extra)) / 17.77, 3)
        verdict["hang"] = verdict["hang"] and hp["bulge_at_opening_width"] <= 1.15
    ratios = {}
    if ref is not None:
        p, r = pile(d), pile(ref)
        for k in PILE_KEYS:
            if p.get(k) is not None and r.get(k):
                ratios[k] = round(p[k] / r[k], 2)
        verdict["pile"] = bool(ratios) and all(abs(v - 1.0) <= PILE_TOL for v in ratios.values())
    else:
        verdict["pile"] = None
    if d.get("collider_origin_cm"):
        verdict["site"] = site_ok(d)
    verdict["ALL"] = verdict["still"] and verdict["hang"] and all(v is not False for v in verdict.values())
    return verdict, ratios


def site_ok(d):
    """A passage backcloth has no pile reference (a different site), so its pile is checked against the site: it must
    stay short of the hinge (the static floor ends there), inside the passage floor's width, and on the floor."""
    spec = json.loads((ROOT / d["colliders"].split("|")[0]).read_text(encoding="utf-8"))
    o = d["collider_origin_cm"]
    hinge_y = (spec["key_lines_world_x"]["hinge_static_floor_ends"] - o[0]) / 100.0
    floor = next(b for b in spec["boxes"] if b["name"].startswith("Passage floor boards"))
    half = min(abs(floor["min_cm"][1] - o[1]), abs(floor["max_cm"][1] - o[1])) / 100.0
    worst = {"y_max_m": None, "abs_x_max_m": None, "z_min_m": None}
    for cp in d["checkpoints"].values():
        a = cp["aabb_m"]
        worst["y_max_m"] = max(worst["y_max_m"] or -1e9, a["y"][1])
        worst["abs_x_max_m"] = max(worst["abs_x_max_m"] or 0.0, abs(a["x"][0]), abs(a["x"][1]))
        worst["z_min_m"] = min(worst["z_min_m"] if worst["z_min_m"] is not None else 1e9, a["z"][0])
    d["_site"] = {"hinge_y_m": hinge_y, "floor_half_width_m": half, **worst}
    return worst["y_max_m"] < hinge_y - 0.5 and worst["abs_x_max_m"] < half and worst["z_min_m"] > -0.05


def drape_lines(name, d, ref_name, ref):
    verdict, ratios = judge_drape(d, ref)
    hp = d.get("hang_profile") or {}
    rows = hp.get("rows", {})
    lines = [f"### {name}: {'PASS' if verdict['ALL'] else 'FAIL'}  (still {verdict['still']}, hang {verdict['hang']}, "
             f"pile {verdict['pile']})",
             f"- rest `{d.get('rest')}`, fold wavelength {d.get('fold_wavelength_m')} m, hem guide {d.get('hem_guide_weight')} "
             f"x {d.get('hem_guide_rows')} rows, bending {d.get('bend')}, track {d.get('track_m')} m, drop {d.get('drop_m')} m",
             f"- **still**: window max {d.get('still_window_max_mm')} mm/frame (mean {d.get('still_window_mean_mm')}); "
             f"under 2 mm from {d.get('settle_to_2mm_s')} s (reached: {d.get('settle_to_2mm_reached')})"]
    if rows:
        lines.append(f"- **hang**: bulge {hp.get('bulge_at_opening_width')} and flare {hp.get('flare_at_opening_width')} at the Opening width (edge spread "
                     f"{hp.get('edge_spread_m')} m); folds (count, depth m, kept) "
                     + "; ".join(f"{k} {v['folds']}, {v['mean_depth_m']}"
                                 + (f", {v.get('count_kept')}/{v.get('depth_kept')}" if 'count_kept' in v else "")
                                 for k, v in rows.items()))
    else:
        lines.append(f"- **hang**: no profile ({hp.get('skipped', 'not measured')})")
    p = pile(d)
    lines.append(f"- **pile**: height {p.get('height_m')}, depth {p.get('depth_m')}, width {p.get('width_m')}, "
                 f"layers {p.get('layers')}, fold size {p.get('fold_size_m')}; vs {ref_name}: {ratios}")
    lines.append(f"- **fall**: {fall_timing(d)}")
    if "_site" in d:
        lines.append(f"- **site**: {d['_site']} (pile must stay 0.5 m short of the hinge, inside the floor, above z -0.05)")
    return lines, verdict


def traveller_lines(name, d):
    hp = d.get("hang_profile") or {}
    still, end = d.get("still_window_max_mm"), d.get("end_still_max_mm")
    v = {"still": still is not None and still < STILL_LIMIT_MM, "end_still": end is not None and end < STILL_LIMIT_MM,
         "hang": bool(hp.get("pass")) if hp else None}
    if hp.get("halves"):                        # the same widest-row BULGE check as the drapes, per half
        extra = sum(max(0.0, max(r["width_m"] for r in h["rows"].values()) - h["rows"]["heading"]["width_m"])
                    for h in hp["halves"])
        hp["bulge"] = round((d["track_m"] + extra) / d["track_m"], 3)
        v["hang"] = v["hang"] and hp["bulge"] <= 1.15
    v["ALL"] = all(x is True for x in v.values())
    lines = [f"### {name} (traveller): {'PASS' if v['ALL'] else 'FAIL'}  {v}",
             f"- start `{d.get('start')}`, hem guide {d.get('hem_guide_weight')}; still {still} mm/frame "
             f"(under 2 mm from {d.get('settle_to_2mm_s')} s); END still {end} mm/frame",
             f"- hang: flare {hp.get('flare_ratio')}, bulge {hp.get('bulge')}, per half "
             + "; ".join(f"side {h['side']}: " + ", ".join(f"{k} {r['folds']}/{r['mean_depth_m']}" for k, r in h['rows'].items())
                         for h in hp.get("halves", [])),
             f"- design: stack {d.get('design_stack_width_per_side_m')} m per side, clear opening {d.get('design_clear_opening_m')} m; "
             f"opening {d.get('open_frames', 0) / FPS:.0f} s"]
    for f, cp in sorted(d["checkpoints"].items(), key=lambda kv: int(kv[0])):
        t = cp["traveller"]
        lines.append(f"- frame {f}: clear opening {t['clear_opening_all_m']} m; stacks L {t['left']['width_m']} x "
                     f"{t['left']['depth_p2_p98_m']} m, R {t['right']['width_m']} x {t['right']['depth_p2_p98_m']} m; "
                     f"hem min z {t['hem_min_z_m']}")
    return lines, v


def tile(path, w=640):
    if not path.exists():
        im = Image.new("RGB", (w, w * 9 // 16), (60, 60, 60))
        ImageDraw.Draw(im).text((10, 10), f"missing: {path.name}", fill="white")
        return im
    im = Image.open(path).convert("RGB")
    return im.resize((w, int(im.height * w / im.width)))


def compare_sheet(a, b, da, db):
    font = ImageFont.load_default(size=18)
    rows = [("hang, front", f"{a}_hangfront.png", f"{b}_hangfront.png"), ("hang, 3/4", f"{a}_hang34.png", f"{b}_hang34.png")]
    rows += [(f"{dt:.1f} s after release", None, dt) for dt in (0.5, 1.0, 1.5, 2.0, 3.0, 5.0)]
    rows += [("pile, 3/4", f"{a}_34.png", f"{b}_34.png"), ("pile, side", f"{a}_side.png", f"{b}_side.png"),
             ("pile, front", f"{a}_front.png", f"{b}_front.png")]
    tiles = []
    for label, pa, pb in rows:
        if pa is None:
            ims = []
            for i, d in ((a, da), (b, db)):
                n = int(round(d["release_frame"] + pb * FPS)) - (d.get("show_start") or 1)
                ims.append(tile(OUT / f"{i}_clip_34" / f"f{n:04d}.png"))
        else:
            ims = [tile(OUT / pa), tile(OUT / pb)]
        tiles.append((label, ims))
    h = sum(max(im.height for im in ims) + 30 for _, ims in tiles) + 40
    sheet = Image.new("RGB", (1290, h), "white")
    dr = ImageDraw.Draw(sheet)
    dr.text((10, 8), f"LEFT {a}    RIGHT {b}", fill="black", font=font)
    y = 40
    for label, ims in tiles:
        dr.text((10, y), label, fill="black", font=font)
        y += 26
        for k, im in enumerate(ims):
            sheet.paste(im, (k * 650, y))
        y += max(im.height for im in ims) + 4
    path = OUT / f"compare_{a}_{b}.png"
    sheet.save(path)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="+")
    ap.add_argument("--ref", default="final2_stage_v2", help="pile reference for full-width drapes")
    ap.add_argument("--strip-ref", default="sw_b5_g0", help="pile reference for strip bakes (track under 17 m)")
    ap.add_argument("--sheet", default="", help="a,b: write a side-by-side sheet")
    args = ap.parse_args()
    ref, strip_ref = load(args.ref), load(args.strip_ref)
    head = ["# Curtain acceptance (30 Sep)", "",
            f"Targets: still < {STILL_LIMIT_MM} mm/frame; hang = flare AND bulge (widest row) at most 1.15, fold count kept at least 0.75 and depth "
            f"kept at least 0.5 at 75/50/25% height; pile within +-{int(PILE_TOL * 100)}% of the reference on "
            f"{', '.join(PILE_KEYS)}.", ""]
    body, summary, verdicts = [], [], {}
    for i in args.ids:
        d = load(i)
        if d is None:
            body += [f"### {i}: not landed", ""]
            summary.append(f"| {i} | not landed | |")
            continue
        if d.get("kind") == "traveller":
            ls, v = traveller_lines(i, d)
        else:
            strip = (d.get("track_m") or 17.77) < 17.0 and not d.get("collider_origin_cm")
            rname, r = (args.strip_ref, strip_ref) if strip else (args.ref, ref)
            if d.get("collider_origin_cm"):          # a passage backcloth: a different site, so no pile reference
                rname, r = "none (different site)", None
            ls, v = drape_lines(i, d, rname, r)
        body += ls + [""]
        verdicts[i] = v
        summary.append(f"| {i} | {'PASS' if v['ALL'] else 'FAIL'} | "
                       + ", ".join(f"{k}={val}" for k, val in v.items() if k != "ALL") + " |")
    lines = head + ["| bake | verdict | criteria |", "|---|---|---|"] + summary + [""] + body
    if args.sheet:
        a, b = args.sheet.split(",")
        if load(a) and load(b):
            lines.append(f"Sheet: {compare_sheet(a, b, load(a), load(b))}")
    # Machine-readable verdicts, merged into earlier runs: the import script refuses any bake not marked ALL here.
    vpath = OUT / "acceptance.json"
    merged = json.loads(vpath.read_text(encoding="utf-8")) if vpath.exists() else {}
    merged.update({k: {kk: vv for kk, vv in v.items()} for k, v in verdicts.items()})
    vpath.write_text(json.dumps(merged, indent=1), encoding="utf-8")
    report = OUT / "acceptance_report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"REPORT|{report}")


if __name__ == "__main__":
    main()
