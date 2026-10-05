"""Contact sheet for a p02_fog_bench.py CAPTURE run (runs OUTSIDE Unreal, needs Pillow).

  python Saved/CodexConductor/p02_fog_bench_contact_sheet.py [run_dir]

One row per camera position, one column per variant (base, A, B, C, D, E, ALL). Each tile is labelled with its
variant LETTER, what the variant does, the position, and which of the shot's stills was picked: P02's HUM / FAULT
flicker changes the picture between stills, so the tile shows the still whose mean luma (Rec.709 on the stored
sRGB values, as look_bench.png_luma) is nearest the shot's median. No-op notes from the run's plan (no beam in
view, D already locked, E floor without a roughness scalar, ...) are printed on the tile. Writes
p02_fog_bench_contact_sheet.png and p02_fog_bench_contact_sheet.json into the run dir. Never touches Unreal.
"""
import json
import pathlib
import statistics
import sys

OUT_ROOT = pathlib.Path("E:/PussStage/Saved/CodexConductor/P02FogBench")
MANIFEST_NAME = "p02_fog_bench_manifest.json"
SHEET_PNG = "p02_fog_bench_contact_sheet.png"
SHEET_JSON = "p02_fog_bench_contact_sheet.json"
ORDER = ("base", "A", "B", "C", "D", "E", "ALL")
TITLES = {"base": "base (unchanged)", "A": "A  haze only on hero beams", "B": "B  low ground mist",
          "C": "C  raked wings, light/dark layers", "D": "D  exposure locked", "E": "E  reflectivity",
          "ALL": "A+B+C+D+E"}


def mean_luma(path):
    from PIL import Image
    with Image.open(path) as im:
        rgb = im.convert("RGB")
        r, g, b = (statistics.fmean(ch.getdata()) for ch in rgb.split())
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def pick_still(paths):
    """-> (index, lumas, median). The still nearest the median of the shot's lumas."""
    lumas = [mean_luma(p) for p in paths]
    med = statistics.median(lumas)
    idx = min(range(len(lumas)), key=lambda i: (abs(lumas[i] - med), i))
    return idx, lumas, med


def notes_for(plan, variant):
    plan = plan or {}
    out = []
    if variant in ("A", "ALL") and (plan.get("A") or {}).get("no_beam_in_view"):
        out.append("no BEAM in view: every lamp's haze zeroed")
    if variant in ("C", "ALL") and (plan.get("C") or {}).get("noop"):
        out.append("C no-op: no LOW_SIDE lamp")
    d = plan.get("D") or {}
    if variant in ("D", "ALL") and d.get("locked"):
        out.append("D: base already locked at EV %s" % d.get("min"))
    if variant in ("D", "ALL") and d.get("manual"):
        out.append("D no-op: manual exposure")
    if variant in ("E", "ALL") and not (plan.get("E") or {}).get("floor_mids"):
        out.append("E floor: no roughness scalar")
    w = plan.get("walnut") or {}
    if variant in ("E", "ALL") and w and not w.get("applied"):
        out.append("E ran BEFORE the walnut floor")
    return out


def newest_run(root=OUT_ROOT):
    runs = sorted(p for p in pathlib.Path(root).glob("P02FOG-*") if (p / MANIFEST_NAME).is_file())
    if not runs:
        raise SystemExit("P02_FOG_SHEET_FAILED|no run with a manifest under %s" % pathlib.Path(root).as_posix())
    return runs[-1]


def build_sheet(run_dir, thumb_w=480):
    from PIL import Image, ImageDraw, ImageFont
    run_dir = pathlib.Path(run_dir)
    man = json.loads((run_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    variants = [v for v in ORDER if v in (man.get("params") or {}).get("variants", ORDER)]
    positions = man["positions"]
    thumb_h = int(round(thumb_w * 9 / 16))
    bar = 58
    pad = 8
    head = 34
    W = pad + len(variants) * (thumb_w + pad)
    H = head + len(positions) * (thumb_h + bar + pad) + pad
    sheet = Image.new("RGB", (W, H), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 15)
        big = ImageFont.truetype("arialbd.ttf", 22)
    except Exception:
        font = big = ImageFont.load_default()
    draw.text((pad, 8), "P02 fog bench  %s  status=%s" % (man.get("run_id"), man.get("status")), fill=(235, 235, 235),
              font=font)
    tiles, missing = [], []
    for r, pos in enumerate(positions):
        y0 = head + r * (thumb_h + bar + pad)
        for c, v in enumerate(variants):
            x0 = pad + c * (thumb_w + pad)
            shot = (pos.get("shots") or {}).get(v) or {"stills": []}
            paths = [s["path"] for s in shot["stills"] if pathlib.Path(s["path"]).is_file()]
            tile = {"position": pos["name"], "bay": pos.get("bay"), "variant": v, "letter": v,
                    "title": TITLES[v], "notes": notes_for(pos.get("plan"), v)}
            if paths:
                idx, lumas, med = pick_still(paths)
                with Image.open(paths[idx]) as im:
                    sheet.paste(im.convert("RGB").resize((thumb_w, thumb_h)), (x0, y0 + bar))
                tile.update(pick=paths[idx], pick_index=idx, lumas=[round(x, 2) for x in lumas],
                            median=round(med, 2))
                sub = "%s  pick %d/%d  luma %.1f (median %.1f)" % (pos["name"], idx, len(paths), lumas[idx], med)
            else:
                draw.rectangle((x0, y0 + bar, x0 + thumb_w, y0 + bar + thumb_h), fill=(70, 20, 20))
                draw.text((x0 + 12, y0 + bar + 12), "MISSING", fill=(255, 200, 200), font=big)
                tile.update(pick=None, missing=True)
                missing.append("%s/%s" % (pos["name"], v))
                sub = "%s  no still" % pos["name"]
            draw.text((x0, y0 + 2), v, fill=(255, 210, 90), font=big)
            draw.text((x0 + 60, y0 + 6), TITLES[v], fill=(235, 235, 235), font=font)
            draw.text((x0, y0 + 26), sub, fill=(190, 190, 190), font=font)
            if tile["notes"]:
                draw.text((x0, y0 + 42), "; ".join(tile["notes"])[:70], fill=(255, 150, 120), font=font)
            tiles.append(tile)
    out_png = run_dir / SHEET_PNG
    sheet.save(out_png)
    out = {"run": man.get("run_id"), "sheet": out_png.as_posix(), "variants": variants,
           "positions": [p["name"] for p in positions], "tiles": tiles, "missing": missing}
    (run_dir / SHEET_JSON).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("P02_FOG_SHEET_%s|run=%s|tiles=%d|missing=%d|sheet=%s" % (
        "OK" if not missing else "INCOMPLETE", man.get("run_id"), len(tiles), len(missing), out_png.as_posix()))
    return out


if __name__ == "__main__":
    build_sheet(pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else newest_run())
