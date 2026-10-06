"""Contact sheet + texture metric for a beam_texture_bench.py CAPTURE run (runs OUTSIDE Unreal, needs Pillow).

  python Saved/CodexConductor/beam_texture_bench_contact_sheet.py [run_dir]

One row per camera position (lamp ahead 450 / 250 / 50 cm), one column per variant (base, A, B, D, ALL). Per tile:
the variant letter and what it does, the still nearest the shot's median luma, the beam's core MASK outlined (dots),
and three numbers:
  tex   texture inside the mask = std of the high-passed luma (luma - box blur) / mean luma, measured on the MEAN of
        the shot's stills (temporal noise averages out; spatial texture stays), and its ratio to base's;
  beam  mean luma inside the mask (and its ratio to base's): a variant that kills the beam is not "more texture";
  ms    frame time p50 / p95 (editor tick deltas over time_seconds, no capture in flight) and the p50 delta to base.
Verdict "TEXTURED" when tex >= textured_ratio x base AND beam >= keep_brightness x base (beam_texture_bench.
texture_verdict). The base tile is the failing control: base vs itself = ratio 1.00 -> never TEXTURED.
Notes from the run's plan are printed on the tile (occlusion verdict, occluder shown, D escalated / no-op, beam
unstruck, beam not in shot, held failures). Writes beam_texture_bench_contact_sheet.png / .json into the run dir.
Never touches Unreal.
"""
import json
import pathlib
import statistics
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import beam_texture_bench as btb  # noqa: E402

SHEET_PNG = "beam_texture_bench_contact_sheet.png"
SHEET_JSON = "beam_texture_bench_contact_sheet.json"
TITLES = {"base": "unchanged", "A": "vol. shadows + occluder", "B": "noise fog volume",
          "BL": "fog clumps (LFV)", "D": "finer fog grid, g 0.7", "AB": "A + B (shadows + noise fog)", "ALL": "A + B + D"}


def load_luma(path, width):
    """-> rows of floats (Rec.709 on the stored sRGB values, as look_bench.png_luma), resized to `width`."""
    from PIL import Image
    with Image.open(path) as im:
        rgb = im.convert("RGB")
        h = max(1, int(round(rgb.height * width / float(rgb.width))))
        rgb = rgb.resize((int(width), h))
        data = list(rgb.getdata())
    w = int(width)
    flat = [0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b in data]
    return [flat[j * w:(j + 1) * w] for j in range(h)]


def mean_image(images):
    n = float(len(images))
    return [[sum(img[j][i] for img in images) / n for i in range(len(images[0][0]))] for j in range(len(images[0]))]


def flat_mean(rows):
    return sum(sum(r) for r in rows) / float(sum(len(r) for r in rows))


def shot_metric(paths, spec, p):
    width = int(p["analysis_width"])
    imgs = [load_luma(x, width) for x in paths]
    h = len(imgs[0])
    mask = btb.mask_grid(spec, width, h)
    blur = max(1, int(round(float(p["hp_blur_frac"]) * width)))
    mean = btb.texture_metric(mean_image(imgs), mask, blur)
    per = [btb.texture_metric(img, mask, blur) for img in imgs]
    lumas = [flat_mean(img) for img in imgs]
    med = statistics.median(lumas)
    pick = min(range(len(lumas)), key=lambda i: (abs(lumas[i] - med), i))
    return {"mean_image": mean, "per_still_hp_rel": [x["hp_rel"] for x in per], "frame_lumas": lumas,
            "pick": pick, "mask_px": sum(sum(1 for v in r if v) for r in mask), "blur_px": blur}


def notes_for(pos, v):
    plan = pos.get("plan") or {}
    out = []
    if not plan.get("struck", True):
        out.append("BEAM UNSTRUCK")
    if plan.get("mask_frac") is not None and plan["mask_frac"] < float((plan.get("params") or {}).get(
            "mask_min_frac", btb.DEFAULTS["mask_min_frac"])):
        out.append("beam not in shot")
    a = plan.get("A") or {}
    if v in ("A", "AB", "ALL"):
        out.append("occl %s%s" % (a.get("occlusion"), (" +%s" % a["occluder"]) if a.get("occluder") else ""))
    d = plan.get("D") or {}
    if v in ("D", "ALL") and d.get("escalated"):
        out.append("D past brief: " + ",".join(n.split(".")[-1] for n in d["escalated"]))
    if v in ("D", "ALL") and d.get("noop"):
        out.append("D no-op: " + ",".join(n.split(".")[-1] for n in d["noop"]))
    held = (pos.get("held") or {}).get(v)
    if held:
        out.append("HELD FAIL %d" % len(held))
    return out


def newest_run(root=btb.OUT_ROOT):
    runs = sorted(x for x in pathlib.Path(root).glob("BEAMTEX-*") if (x / btb.MANIFEST_NAME).is_file())
    if not runs:
        raise SystemExit("BEAM_TEXTURE_SHEET_FAILED|no run with a manifest under %s" % pathlib.Path(root).as_posix())
    return runs[-1]


def build_sheet(run_dir, thumb_w=480):
    from PIL import Image, ImageDraw, ImageFont
    run_dir = pathlib.Path(run_dir)
    man = json.loads((run_dir / btb.MANIFEST_NAME).read_text(encoding="utf-8"))
    p = dict(btb.DEFAULTS)
    p.update(man.get("params") or {})
    variants = [v for v in btb.ORDER if v in p.get("variants", btb.DEFAULT_VARIANTS)]
    positions = man["positions"]
    thumb_h = int(round(thumb_w * 9 / 16))
    bar, pad, head = 94, 8, 34
    chars = max(12, int(thumb_w / 7.6))
    W = pad + len(variants) * (thumb_w + pad)
    H = head + len(positions) * (thumb_h + bar + pad) + pad
    sheet = Image.new("RGB", (W, H), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 14)
        big = ImageFont.truetype("arialbd.ttf", 22)
    except Exception:
        font = big = ImageFont.load_default()
    beam = (man.get("beam") or {}).get("label", "?")
    draw.text((pad, 8), "Beam texture bench  %s  %s  status=%s" % (man.get("run_id"), beam, man.get("status")),
              fill=(235, 235, 235), font=font)
    tiles, missing, verdicts = [], [], {}
    for r, pos in enumerate(positions):
        y0 = head + r * (thumb_h + bar + pad)
        spec = (pos.get("plan") or {}).get("mask")
        base_m, base_t = None, (pos.get("timings") or {}).get("base") or {}
        for c, v in enumerate(variants):
            x0 = pad + c * (thumb_w + pad)
            shot = (pos.get("shots") or {}).get(v) or {"stills": []}
            paths = [s["path"] for s in shot["stills"] if pathlib.Path(s["path"]).is_file()]
            tile = {"position": pos["name"], "ahead_cm": pos.get("ahead_cm"), "variant": v, "title": TITLES[v],
                    "notes": notes_for(pos, v), "timing": (pos.get("timings") or {}).get(v)}
            if paths and spec:
                m = shot_metric(paths, spec, p)
                if v == "base":
                    base_m = m["mean_image"]
                verdict = btb.texture_verdict(base_m, m["mean_image"], p) if base_m else {"textured": None,
                                                                                          "why": "no base"}
                with Image.open(paths[m["pick"]]) as im:
                    tim = im.convert("RGB").resize((thumb_w, thumb_h))
                sheet.paste(tim, (x0, y0 + bar))
                sx, sy = thumb_w / float(spec["w"]), thumb_h / float(spec["h"])
                for (dx, dy, dr) in spec["discs"][::2]:
                    cx, cy, rr = dx * sx, dy * sy, max(1.0, dr * sx)
                    if -rr <= cx <= thumb_w + rr and -rr <= cy <= thumb_h + rr:
                        draw.ellipse((x0 + cx - rr, y0 + bar + cy - rr, x0 + cx + rr, y0 + bar + cy + rr),
                                     outline=(90, 200, 255))
                tile.update(pick=paths[m["pick"]], metric=m["mean_image"], per_still_hp_rel=m["per_still_hp_rel"],
                            mask_px=m["mask_px"], verdict=verdict)
                mi = m["mean_image"]
                tex = "tex %.3f" % mi["hp_rel"] if mi.get("n") else "tex n/a"
                if verdict.get("ratio") is not None:
                    tex += " (x%.2f)  beam %.0f (x%.2f)" % (verdict["ratio"], mi["mean"], verdict["kept"])
                tag = {True: "TEXTURED", False: "no", None: "-"}[verdict.get("textured")]
                if v == "base":
                    tag = "control"
                line2 = "%s  %s" % (tex, tag)
            else:
                draw.rectangle((x0, y0 + bar, x0 + thumb_w, y0 + bar + thumb_h), fill=(70, 20, 20))
                draw.text((x0 + 12, y0 + bar + 12), "MISSING", fill=(255, 200, 200), font=big)
                tile.update(pick=None, missing=True)
                missing.append("%s/%s" % (pos["name"], v))
                line2 = "no still"
            tm = tile["timing"] or {}
            ms = "ms p50 %.1f p95 %.1f" % (tm["p50"], tm["p95"]) if tm.get("n") else "ms n/a"
            if tm.get("n") and base_t.get("n") and v != "base":
                ms += " (%+.1f)" % (tm["p50"] - base_t["p50"])
            draw.text((x0, y0 + 2), v, fill=(255, 210, 90), font=big)
            draw.text((x0 + 56, y0 + 6), TITLES[v][:max(4, chars - 8)],
                      fill=(235, 235, 235), font=font)
            draw.text((x0, y0 + 26), ("%s  lamp %.0f cm ahead" % (pos["name"], float(pos.get("ahead_cm") or 0)))[:chars],
                      fill=(200, 200, 200), font=font)
            draw.text((x0, y0 + 42), line2[:chars], fill=(190, 230, 190), font=font)
            draw.text((x0, y0 + 58), ms[:chars], fill=(190, 190, 190), font=font)
            if tile["notes"]:
                draw.text((x0, y0 + 74), "; ".join(tile["notes"])[:chars], fill=(255, 150, 120), font=font)
            tiles.append(tile)
            verdicts.setdefault(v, []).append(tile.get("verdict", {}).get("textured"))
    out_png = run_dir / SHEET_PNG
    sheet.save(out_png)
    summary = {v: {"textured_positions": sum(1 for x in vs if x), "of": len(vs)} for v, vs in verdicts.items()}
    out = {"run": man.get("run_id"), "sheet": out_png.as_posix(), "variants": variants,
           "positions": [x["name"] for x in positions], "tiles": tiles, "missing": missing, "summary": summary,
           "occlusion": [(x["name"], ((x.get("plan") or {}).get("behind_wing") or {})) for x in positions]}
    (run_dir / SHEET_JSON).write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print("BEAM_TEXTURE_SHEET_%s|run=%s|tiles=%d|missing=%d|summary=%s|sheet=%s" % (
        "OK" if not missing else "INCOMPLETE", man.get("run_id"), len(tiles), len(missing),
        json.dumps(summary, sort_keys=True), out_png.as_posix()))
    return out


if __name__ == "__main__":
    build_sheet(pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else newest_run())
