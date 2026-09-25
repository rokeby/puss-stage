"""Build contact sheets and a first-pass silhouette edge report for assigned Wings."""

from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "Saved" / "CodexWingHandedness" / "assigned_wings.json"
OUT = ROOT / "Saved" / "CodexWingHandedness" / "visual_review"
LEGACY_ROOT = Path(
    r"G:\Shared drives\GZZ Studio Drive\Projects\2026. SHS 3 Evenings\Stage Materials\v1\PNG Images"
)
_legacy_index = None


def normalized_name(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def legacy_index():
    global _legacy_index
    if _legacy_index is None:
        _legacy_index = {}
        if LEGACY_ROOT.is_dir():
            for path in LEGACY_ROOT.rglob("*.png"):
                _legacy_index.setdefault(normalized_name(path.stem), []).append(path)
    return _legacy_index


def source_for(passage: int, mesh_path: str) -> Path | None:
    name = mesh_path.rsplit("/", 1)[-1].removeprefix("SM_")
    if name.startswith("P02_SET"):
        set_number = name.split("_", 2)[1].removeprefix("SET")
        return (
            ROOT
            / "DerivedAssets/GeneratedConcepts/Passage02Forest/"
            "RousseauApprovedIndividualSequenceV5/chroma"
            / f"set_{set_number}"
            / f"{name}.png"
        )
    if name.startswith("P03_"):
        return (
            ROOT
            / "DerivedAssets/GeneratedWingsV2_Passage03_Clean"
            / name
            / "Textures"
            / f"{name}.png"
        )
    if name.startswith("CloudRef"):
        return ROOT / "DerivedAssets/Passage05BirdToMountainBatch/Input" / f"{name}.png"
    stage_opening = ROOT / "DerivedAssets/StageOpeningV2Batch/Input" / f"{name}.png"
    if stage_opening.is_file():
        return stage_opening
    stage_opening_hyphen = (
        ROOT / "DerivedAssets/StageOpeningV2Batch/Input" / f"{name.replace('_rococo_painterly', '-rococo-painterly')}.png"
    )
    if stage_opening_hyphen.is_file():
        return stage_opening_hyphen
    known = {
        "L_bones": ROOT / "DerivedAssets/PendingGoogleDrive/ShoreOfBones_2026-07-25/L_bones/Textures/L_bones.png",
        "S2_L_Wing_Shrine": ROOT / "DerivedAssets/PendingGoogleDrive/S2_Shrine/New_2026-07-24/S2_L_Wing_Shrine/S2_L_Wing_Shrine/Textures/S2_L_Wing_Shrine.png",
        "L_Wing_2_Animals": ROOT / "Klara Scenes WIP/1. Animals by the lake/L_Wing_2_Animals.png",
        "R_Pillar1_bw": ROOT / "Klara Scenes WIP/1. Animals by the lake/R_Pillar1_bw.png",
    }
    if name in known and known[name].is_file():
        return known[name]
    normalized = normalized_name(name)
    candidates = []
    for path in (ROOT / "DerivedAssets").rglob("*.png"):
        stem = normalized_name(path.stem)
        if stem == normalized and not path.stem.endswith(("_N", "_H")):
            candidates.append(path)
    if candidates:
        candidates.sort(key=lambda path: ("textures" not in str(path).lower(), len(str(path))))
        return candidates[0]
    drive_candidates = legacy_index().get(normalized, [])
    if drive_candidates:
        return sorted(drive_candidates, key=lambda path: len(str(path)))[0]
    return None


def alpha_mask(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    if image.mode == "RGBA" and rgba.getchannel("A").getextrema() != (255, 255):
        return rgba.getchannel("A").point(lambda value: 255 if value >= 24 else 0)
    pixels = rgba.load()
    mask = Image.new("L", rgba.size, 0)
    target = mask.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            red, green, blue, _ = pixels[x, y]
            magenta = red > 115 and blue > 105 and green < 115 and green < min(red, blue) * 0.68
            target[x, y] = 0 if magenta else 255
    return mask


def edge_measure(mask: Image.Image) -> dict:
    bbox = mask.getbbox()
    if not bbox:
        return {"edge": "unknown", "confidence": 0.0}
    x0, y0, x1, y1 = bbox
    width = max(1, x1 - x0)
    lefts = []
    rights = []
    pix = mask.load()
    for y in range(y0, y1):
        occupied = [x for x in range(x0, x1) if pix[x, y] > 0]
        if occupied:
            lefts.append(occupied[0])
            rights.append(occupied[-1])
    bin_width = max(2, round(width * 0.018))

    def straight_score(values):
        counts = {}
        for value in values:
            bucket = round(value / bin_width)
            counts[bucket] = counts.get(bucket, 0) + 1
        return max(counts.values(), default=0) / max(1, len(values))

    left_score = straight_score(lefts)
    right_score = straight_score(rights)
    margin = abs(left_score - right_score)
    if margin < 0.075:
        edge = "even"
    else:
        edge = "left" if left_score > right_score else "right"
    return {
        "edge": edge,
        "confidence": round(margin, 3),
        "left_straight_score": round(left_score, 3),
        "right_straight_score": round(right_score, 3),
        "bbox": [x0, y0, x1, y1],
    }


def display_tile(path: Path, title: str, edge: str, flips: str) -> Image.Image:
    original = Image.open(path).convert("RGBA")
    mask = alpha_mask(original)
    original.putalpha(mask)
    bbox = mask.getbbox() or (0, 0, original.width, original.height)
    cropped = original.crop(bbox)
    canvas = Image.new("RGBA", (360, 430), (48, 48, 48, 255))
    checker = Image.new("RGBA", canvas.size, (70, 70, 70, 255))
    draw_checker = ImageDraw.Draw(checker)
    for y in range(0, 360, 24):
        for x in range(0, 360, 24):
            if (x // 24 + y // 24) % 2:
                draw_checker.rectangle((x, y, x + 23, y + 23), fill=(90, 90, 90, 255))
    canvas.alpha_composite(checker)
    preview = ImageOps.contain(cropped, (330, 340), Image.Resampling.LANCZOS)
    canvas.alpha_composite(preview, ((360 - preview.width) // 2, 10 + (340 - preview.height) // 2))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 360, 359, 429), fill=(25, 25, 25, 255))
    draw.text((8, 366), title[:48], fill="white")
    draw.text((8, 388), f"source flat edge: {edge}", fill=(255, 220, 90))
    draw.text((8, 407), f"assigned flips: {flips}", fill=(180, 220, 255))
    return canvas.convert("RGB")


data = json.loads(AUDIT.read_text(encoding="utf-8"))
OUT.mkdir(parents=True, exist_ok=True)
report = []

for passage in range(1, 7):
    rows = [row for row in data["rows"] if row["passage"] == passage]
    uses = {}
    for row in rows:
        for side in ("left", "right"):
            mesh = row[side]["mesh"]
            uses.setdefault((side, mesh), set()).add(row[side]["flip_image_horizontally"])
    tiles = []
    for side, mesh in sorted(uses):
        source = source_for(passage, mesh)
        entry = {
            "passage": passage,
            "side": side,
            "mesh": mesh,
            "flips": sorted(uses[(side, mesh)]),
            "source": str(source) if source and source.is_file() else None,
        }
        if source and source.is_file():
            image = Image.open(source)
            measure = edge_measure(alpha_mask(image))
            entry.update(measure)
            flip_text = "/".join("on" if value else "off" for value in entry["flips"])
            tiles.append(display_tile(source, f"{side.upper()} {mesh.rsplit('/', 1)[-1]}", measure["edge"], flip_text))
        else:
            entry.update({"edge": "unavailable", "confidence": 0.0})
        report.append(entry)
    if tiles:
        columns = 4
        rows_count = math.ceil(len(tiles) / columns)
        sheet = Image.new("RGB", (columns * 360, rows_count * 430), (16, 16, 16))
        for index, tile in enumerate(tiles):
            sheet.paste(tile, ((index % columns) * 360, (index // columns) * 430))
        sheet.save(OUT / f"passage_{passage:02d}_source_edges.jpg", quality=92)

(OUT / "source_edge_report.json").write_text(
    json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
)
print(json.dumps({
    "entries": len(report),
    "sources_found": sum(item["source"] is not None for item in report),
    "sheets": sorted(path.name for path in OUT.glob("*.jpg")),
}, indent=2))
