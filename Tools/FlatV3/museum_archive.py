"""Offline museum-archive cutter and Flat V3 batch orchestrator.

This job is the post-StageRefs museum pass requested on 2 October 2026.  It
uses the score table as the selection authority, excludes restricted records,
deduplicates originals by SHA-256, and skips every source sheet already present
in the completed StageRefs census.  Tree/landscape masks use the accepted A2
sky-subtraction idea; substantial see-through holes are explicitly restored
after physical-scale curve smoothing.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import gc
import hashlib
import html
import json
import math
import os
import re
import shutil
import subprocess
import time
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_DATASETS_OFFLINE", "1")

import cv2
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage
from scipy.signal import savgol_filter
from shapely.geometry import Polygon
from skimage import measure, morphology

import stage_refs as shared


Image.MAX_IMAGE_PIXELS = None
PROJECT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = Path(r"D:\PussStageSources\FlatV3")
TOOL_ROOT = Path(r"D:\PussStageTools\FlatV3")
VENV_PYTHON = TOOL_ROOT / "venv" / "Scripts" / "python.exe"
OUT = PROJECT / "DerivedAssets" / "FlatV3" / "Overnight" / "Museum"
SHEETS = OUT / "sheets"
ELEMENTS = OUT / "elements"
GPU_MARKER = PROJECT / "DerivedAssets" / "FlatV3" / "Overnight" / "RUNNING.json"
SCORES_PATH = PROJECT / "DerivedAssets" / "FlatV3" / "Sourcing" / "scores.json"
BY_PASSAGE_PATH = PROJECT / "DerivedAssets" / "FlatV3" / "Sourcing" / "BY_PASSAGE.md"
STAGE_CENSUS_PATH = PROJECT / "DerivedAssets" / "FlatV3" / "Overnight" / "StageRefs" / "SOURCE_CENSUS.json"
SAM_CHECKPOINT = TOOL_ROOT / "models" / "sam2.1_hiera_large.pt"
SAM_CONFIG = "configs/sam2.1/sam2.1_hiera_l.yaml"
DINO_REVISION = "12bdfa3120f3e7ec7b434d90674b3396eccf88eb"
DINO_SNAPSHOT = (
    TOOL_ROOT / "cache" / "huggingface" / "hub"
    / "models--IDEA-Research--grounding-dino-base" / "snapshots" / DINO_REVISION
)
SEGMENT_MAX = 1280
FONT = ImageFont.load_default()
SCHEMA = 1

NAMED_ARCHITECTURE = (
    "bibiena", "monsu", "desiderio", "de nom", "hubert robert", "salvator rosa",
    "pannini", "panini", "piranesi", "saenredam", "de witte", "robert adam",
    "gothic", "colosseum", "ruin", "church", "cathedral", "palace", "arcade",
    "archway", "architecture", "architectural", "tracery", "protestant",
)
TREE_TERMS = (
    "tree", "trees", "forest", "wood", "oak", "willow", "landscape", "rock",
    "crag", "cliff", "foliage", "ruisdael", "rosa", "kobell", "rousseau",
)
CLOUD_TERMS = ("cloud", "clouds", "sky", "luftstudie")
SEA_TERMS = ("sea row", "rough sea", "high seas", "marine", "wave", "squall")
SEA_EXCEPTION_IDS = {
    "RIJKS-200108359",  # Willem van de Velde II
    "RIJKS-200108177",  # Ludolf Bakhuysen
    "SMK-KMS2057",      # Ludolf Bakhuizen
}

# The semantic proposal is only a candidate, not artistic acceptance. These
# sheets were inspected in their proposal contact sheets on 2 October and the
# selected mask was found to be a negative space, page-sized field, tiny stray
# fragment, filled tracery, or sky/ship mass rather than a usable wing element.
# Retain their draft/provenance, but do not spend a V3 build on them.
MANUAL_HAND_FIX_REASONS = {
    "SMK-KKSgb7529": "selected the dark arch opening rather than Robert Adam's architectural mass",
    "COMMONS-21864224": "selected a tiny upper-left fragment instead of Piranesi's Giant Wheel mass",
    "COMMONS-22491821": "selected a tiny upper-left fragment instead of the Imaginary Prison mass",
    "COMMONS-60849979": "selected a small upper field instead of Hubert Robert's arcade mass",
    "COMMONS-60878064": "Gothic tracery openings were filled by the automatic mask",
    "COMMONS-60887317": "Gothic panel openings were filled by the automatic mask",
    "SMK-KMS3123": "selected the sky opening rather than the Colosseum masonry",
    "SMK-KKSgb9845_27": "selected the rectangular engraved page rather than an isolated Piranesi mass",
    "COMMONS-76942217": "selected an arch opening and sky rather than the Gijsels architecture",
    "COMMONS-60866091": "Gothic tracery openings were filled by the automatic mask",
    "COMMONS-15396645": "selected sky/background around the Pannini ruins rather than the ruins",
    "RIJKS-200108359": "selected sky and ship rather than a clean van de Velde sea-row silhouette",
    "RIJKS-200108177": "selected sky and ships rather than a clean Bakhuysen sea-row silhouette",
    "SMK-KMS2057": "selected sky and ships rather than a clean Bakhuizen sea-row silhouette",
}


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_token(value: str, fallback: str = "Anonymous", limit: int = 64) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    token = re.sub(r"[^A-Za-z0-9]+", "_", ascii_value).strip("_")
    return (token or fallback)[:limit]


def artist_token(value: str) -> str:
    for pattern, token in (
        (r"Bibiena", "Bibiena"), (r"Piranesi", "Piranesi"),
        (r"Saenredam", "Saenredam"), (r"de Witte", "DeWitte"),
        (r"Hubert Robert", "Robert"), (r"Salvator Rosa", "Rosa"),
        (r"Pann?ini", "Pannini"), (r"Ruisdael", "Ruisdael"),
        (r"Bakhu[iy]zen", "Bakhuysen"), (r"van de Velde", "VanDeVelde"),
        (r"Robert Adam", "Adam"), (r"Denis", "Denis"),
    ):
        if re.search(pattern, value, re.I):
            return token
    if re.search(r"unknown|anonymous", value, re.I) or not value.strip():
        return "Anonymous"
    words = re.findall(r"[A-Za-z]+", unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii"))
    return safe_token(words[-1] if words else "Anonymous", limit=28)


def source_original(metadata_path: Path) -> Path | None:
    originals = sorted(path for path in metadata_path.parent.glob("original.*") if path.is_file())
    return originals[0] if originals else None


def score_qualifies(candidate: dict[str, Any]) -> bool:
    usable = str(candidate.get("usable_as", "")).lower()
    wing_form = candidate.get("wing_form", 0)
    return isinstance(wing_form, (int, float)) and wing_form >= 2 and ("wing" in usable or "border" in usable)


def licence_from(metadata: dict[str, Any]) -> str:
    candidate = metadata.get("candidate_record", {})
    return str(candidate.get("license_text") or candidate.get("licence_text") or candidate.get("license") or candidate.get("licence") or "UNCLEAR")


def category_for(candidate: dict[str, Any]) -> str:
    text = " ".join(str(candidate.get(key, "")) for key in ("title", "artist", "usable_as")).lower()
    if "sea row" in str(candidate.get("usable_as", "")).lower() or any(term in text for term in SEA_TERMS):
        return "sea"
    if "border" in str(candidate.get("usable_as", "")).lower() or any(term in text for term in CLOUD_TERMS):
        return "cloud"
    if any(term in text for term in ("botanical", "plant", "fern", "bamboo", "arter", "vascular", "wicker", "briar")):
        return "botanical"
    if any(term in text for term in NAMED_ARCHITECTURE):
        return "architecture"
    if any(term in text for term in TREE_TERMS):
        return "landscape"
    return "painted_mass"


def priority_for(candidate: dict[str, Any], category: str) -> tuple[int, int]:
    text = " ".join(str(candidate.get(key, "")) for key in ("title", "artist")).lower()
    named = any(term in text for term in NAMED_ARCHITECTURE)
    if category == "architecture" and named:
        return (0, -int(candidate.get("wing_form", 0)))
    if category == "architecture":
        return (1, -int(candidate.get("wing_form", 0)))
    if category in {"landscape", "cloud", "sea"}:
        return (2, -int(candidate.get("wing_form", 0)))
    return (3, -int(candidate.get("wing_form", 0)))


def assign_passage(candidate: dict[str, Any], category: str) -> tuple[str, str]:
    text = " ".join(str(candidate.get(key, "")) for key in ("id", "title", "artist")).lower()
    candidate_id = str(candidate.get("id", ""))
    if candidate_id in {"SMK-KKSgb7080", "SMITHSONIAN-chndm_1931-86-54"}:
        return "P06", "grand palace / court architecture card"
    if candidate_id == "COMMONS-76942217":
        return "P01", "warm foliage alternating with classical architecture"
    if category == "cloud":
        return "P05", "cloud mass / border card"
    if category == "sea":
        return "P03", "sea row for the Protestant-convent-to-shore passage"
    if any(term in text for term in ("saenredam", "de witte", "protestant", "wicker man", "colosseum")):
        return "P03", "cool Protestant interior / stone / shore-cult card"
    if any(term in text for term in ("hubert robert", "salvator rosa", "pannini", "panini", "gothic", "tracery", "church", "cathedral", "ruin")):
        return "P04", "ruins and churches card"
    if "piranesi" in text and any(term in text for term in ("giant wheel", "imaginary prison")):
        return "P02", "mystical mechanical ruin near the shrine"
    if category == "architecture":
        if any(term in text for term in ("palace", "stair", "isle enchantee", "chinoiserie", "pavilion")):
            return "P06", "grand architecture / chinoiserie card"
        return "P04", "architectural ruin / church card"
    if category == "botanical":
        return "P02", "shrine-path botanical / branching mass"
    if any(term in text for term in ("villa", "classical", "arcade", "willow", "ruisdael", "oak")):
        return "P01", "warm foliage / classical entry card"
    fits = candidate.get("fit") or {}
    scores = {key: int(value.get("score", 0)) for key, value in fits.items() if isinstance(value, dict)}
    if scores:
        best = max(scores, key=lambda key: (scores[key], -int(key[1:]) if key[1:].isdigit() else 0))
        return best, "highest passage-fit score from scores.json"
    return "P02", "fallback for an organic museum mass"


def census() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    score_payload = read_json(SCORES_PATH)
    candidates = score_payload["candidates"]
    score_order = {row["id"]: index for index, row in enumerate(candidates)}
    candidate_map = {row["id"]: row for row in candidates}
    holdings: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for metadata_path in SOURCE_ROOT.rglob("source.json"):
        with contextlib.suppress(Exception):
            metadata = read_json(metadata_path)
            candidate = metadata.get("candidate_record", {})
            candidate_id = candidate.get("id")
            if not candidate_id:
                continue
            original = source_original(metadata_path)
            holdings[candidate_id].append(
                {
                    "metadata_path": str(metadata_path),
                    "group": metadata_path.relative_to(SOURCE_ROOT).parts[0],
                    "directory": metadata_path.parent.name,
                    "original_path": str(original) if original else None,
                    "use_restriction": metadata.get("use_restriction"),
                    "licence": licence_from(metadata),
                    "credit_line": candidate.get("credit_line"),
                    "attribution_required": bool(candidate.get("attribution_required")),
                    "object_url": candidate.get("object_url"),
                    "source_record": candidate,
                }
            )
    stage_payload = read_json(STAGE_CENSUS_PATH)
    stage_hashes = {row["original_sha256"] for row in stage_payload["sources"]}
    selected_ids = {row["id"] for row in candidates if score_qualifies(row)} | SEA_EXCEPTION_IDS
    records: list[dict[str, Any]] = []
    for candidate_id in sorted(selected_ids, key=lambda value: score_order.get(value, 999999)):
        candidate = candidate_map.get(candidate_id)
        if candidate is None:
            records.append({"candidate_id": candidate_id, "status": "missing_score_record", "selection_basis": "named sea exception"})
            continue
        strict = score_qualifies(candidate)
        source_options = sorted(
            holdings.get(candidate_id, []),
            key=lambda row: (bool(row.get("use_restriction")), row["group"] == "REFERENCE", row["group"], row["directory"]),
        )
        category = category_for(candidate)
        passage, passage_reason = assign_passage(candidate, category)
        base = {
            "candidate_id": candidate_id,
            "score_order": score_order[candidate_id],
            "candidate": candidate,
            "strict_score_qualified": strict,
            "selection_basis": "wing/border and wing_form >= 2" if strict else "explicit Bakhuysen/van de Velde sea-row priority exception",
            "category": category,
            "passage": passage,
            "passage_reason": passage_reason,
            "priority": list(priority_for(candidate, category)),
        }
        if not source_options:
            records.append({**base, "status": "missing_downloaded_source"})
            continue
        chosen = source_options[0]
        record = {**base, **chosen, "holdings": [{key: row.get(key) for key in ("group", "directory", "metadata_path", "original_path", "use_restriction")} for row in source_options]}
        if chosen.get("use_restriction"):
            record["status"] = "excluded_use_restriction"
        elif not chosen.get("original_path"):
            record["status"] = "missing_original"
        else:
            original = Path(chosen["original_path"])
            record["original_sha256"] = sha256(original)
            with Image.open(original) as image:
                record["pixel_size"] = [int(image.width), int(image.height)]
            if record["original_sha256"] in stage_hashes:
                record["status"] = "skipped_already_covered_by_stagerefs"
            else:
                record["status"] = "eligible"
                record["sheet_token"] = safe_token(f"{candidate_id}_{record['original_sha256'][:8]}", limit=90)
        records.append(record)
    eligible = sorted(
        [row for row in records if row["status"] == "eligible"],
        key=lambda row: (tuple(row["priority"]), row["score_order"], row["candidate_id"]),
    )
    status_counts: dict[str, int] = defaultdict(int)
    for row in records:
        status_counts[row["status"]] += 1
    payload = {
        "schema_version": SCHEMA,
        "generated": now(),
        "authority": "Gary, 2 Oct: bulk-cut good wings from the museum archive cheaply",
        "offline": True,
        "network_used": False,
        "selection_rule": "all scores.json candidates whose usable_as contains wing or border and wing_form >= 2, plus three explicitly named Bakhuysen/van de Velde sea-row exceptions",
        "stage_skip_authority": str(STAGE_CENSUS_PATH),
        "score_authority": str(SCORES_PATH),
        "passage_context": str(BY_PASSAGE_PATH),
        "status_counts": dict(sorted(status_counts.items())),
        "eligible_count": len(eligible),
        "eligible_sources": eligible,
        "all_records": records,
    }
    atomic_json(OUT / "MUSEUM_CENSUS.json", payload)
    return payload


def read_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"))


def resize_fit(rgb: np.ndarray, maximum: int = SEGMENT_MAX) -> tuple[np.ndarray, float]:
    height, width = rgb.shape[:2]
    scale = min(1.0, maximum / max(width, height))
    if scale == 1.0:
        return rgb.copy(), 1.0
    return cv2.resize(rgb, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA), scale


def save_rgb(path: Path, rgb: np.ndarray, quality: int = 92) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb.astype(np.uint8), "RGB").save(path, quality=quality, subsampling=0)


def save_mask(path: Path, mask: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(mask.astype(np.uint8) * 255, "L").save(path)


def save_rgba(path: Path, rgb: np.ndarray, alpha: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.dstack((rgb.astype(np.uint8), alpha.astype(np.uint8))), "RGBA").save(path, compress_level=4)


def overlay(rgb: np.ndarray, mask: np.ndarray, colour: tuple[int, int, int]) -> np.ndarray:
    result = rgb.astype(np.float32).copy()
    result[mask] = result[mask] * 0.48 + np.asarray(colour, np.float32) * 0.52
    return np.clip(result, 0, 255).astype(np.uint8)


def mask_features(mask: np.ndarray) -> dict[str, Any]:
    return shared.mask_features(mask)


def largest_component(mask: np.ndarray) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    if count <= 1:
        return mask.astype(bool)
    index = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return labels == index


def keep_sky_components(mask: np.ndarray) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    kept = np.zeros_like(mask, dtype=bool)
    height, width = mask.shape
    for index in range(1, count):
        x, y, component_width, _, area = stats[index]
        touches_open_boundary = y <= 3 or ((x <= 3 or x + component_width >= width - 3) and y < int(height * 0.76))
        if area >= 80 and touches_open_boundary:
            kept[labels == index] = True
    return kept


def colour_luminance_sky(rgb: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    red, green, blue = (rgb[:, :, index].astype(np.int16) for index in range(3))
    light = lab[:, :, 0]
    saturation = hsv[:, :, 1]
    blue_grey = (blue >= green - 24) & (blue >= red - 72)
    seed = ((light >= 158) & (saturation <= 118)) | ((light >= 104) & (saturation <= 148) & blue_grey)
    seed[int(rgb.shape[0] * 0.82):] = False
    seed = cv2.morphologyEx(seed.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)
    seed = cv2.morphologyEx(seed.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8)).astype(bool)
    seed = keep_sky_components(seed)
    return seed, {
        "method": "A2 colour/luminance sky seed",
        "seed_pixels": int(seed.sum()),
        "lab_light_thresholds": [104, 158],
        "hsv_saturation_thresholds": [148, 118],
    }


def prompt_for(category: str) -> str:
    prompts = {
        "architecture": "architectural mass. archway. colonnade. ruined church. stone structure. palace facade. sky.",
        "cloud": "cloud mass. cloud bank. storm cloud. sky.",
        "sea": "ocean wave crest. rough sea. breaking wave. sky.",
        "botanical": "plant mass. tree-like branching mass. botanical specimen. wicker structure. sky.",
        "landscape": "tree mass. forest edge. oak tree. rock mass. ruined structure. sky.",
        "painted_mass": "painted scenery mass. tree. rock. architecture. sky.",
    }
    return prompts[category]


def candidate_quality(candidate: dict[str, Any]) -> float:
    feature = candidate["feature"]
    area = float(feature["area_fraction"])
    fill = area / max(0.001, float(feature["wf"]) * float(feature["hf"]))
    aspect = min(1.0, float(feature["hf"]) / max(0.06, float(feature["wf"])))
    edge = abs(float(feature["cx"]) - 0.5) * 2.0
    return (
        0.42 * float(candidate.get("model_score", 0.5))
        + 0.22 * min(1.0, area / 0.18)
        + 0.16 * min(1.0, fill / 0.65)
        + 0.12 * aspect
        + 0.08 * edge
    )


def choose_one(candidates: list[dict[str, Any]], category: str) -> dict[str, Any] | None:
    valid: list[dict[str, Any]] = []
    for candidate in candidates:
        feature = candidate["feature"]
        if not (0.006 <= feature["area_fraction"] <= 0.70):
            continue
        if feature["hf"] < 0.16 or feature["wf"] < 0.045:
            continue
        row = dict(candidate)
        row["quality"] = candidate_quality(row)
        valid.append(row)
    valid.sort(key=lambda row: row["quality"], reverse=True)
    deduped: list[dict[str, Any]] = []
    for candidate in valid:
        if all(shared.mask_iou(candidate["mask"], prior["mask"]) < 0.72 for prior in deduped):
            deduped.append(candidate)
        if len(deduped) >= 32:
            break
    if not deduped:
        return None
    if category in {"cloud", "sea"}:
        wide = sorted(deduped, key=lambda row: row["quality"] + 0.18 * float(row["feature"]["wf"]), reverse=True)
        chosen = dict(wide[0])
        chosen["side"] = "C"
    else:
        side_ranked = sorted(
            deduped,
            key=lambda row: row["quality"] + 0.16 * abs(float(row["feature"]["cx"]) - 0.5) + 0.08 * min(1.0, float(row["feature"]["hf"]) / max(0.08, float(row["feature"]["wf"]))),
            reverse=True,
        )
        chosen = dict(side_ranked[0])
        chosen["side"] = "L" if float(chosen["feature"]["cx"]) <= 0.5 else "R"
    overlaps = sorted(
        [shared.mask_iou(chosen["mask"], other["mask"]) for other in candidates if other["id"] != chosen["id"]],
        reverse=True,
    )
    chosen["maximum_other_mask_iou"] = overlaps[0] if overlaps else 0.0
    feature = chosen["feature"]
    chosen["bbox_fill_fraction"] = float(feature["area_fraction"]) / max(0.001, float(feature["wf"]) * float(feature["hf"]))
    return chosen


def propose() -> dict[str, Any]:
    from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

    payload = read_json(OUT / "MUSEUM_CENSUS.json") if (OUT / "MUSEUM_CENSUS.json").is_file() else census()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for the offline museum proposal phase")
    gate = shared.wait_for_gpu()
    started = now()
    shared.mark_gpu("running", "museum_archive_proposals", started=started, gpu_gate=gate, output=str(OUT))
    results: list[dict[str, Any]] = []
    fatal: str | None = None
    try:
        setup_started = time.perf_counter()
        sam = build_sam2(SAM_CONFIG, str(SAM_CHECKPOINT), device="cuda")
        automatic = SAM2AutomaticMaskGenerator(
            sam, points_per_side=20, points_per_batch=64, pred_iou_thresh=0.72,
            stability_score_thresh=0.84, crop_n_layers=0, min_mask_region_area=220,
        )
        predictor = SAM2ImagePredictor(sam)
        processor = AutoProcessor.from_pretrained(str(DINO_SNAPSHOT), local_files_only=True)
        dino = AutoModelForZeroShotObjectDetection.from_pretrained(str(DINO_SNAPSHOT), local_files_only=True).to("cuda").eval()
        setup_seconds = round(time.perf_counter() - setup_started, 3)
        sources = payload["eligible_sources"]
        for ordinal, source in enumerate(sources, 1):
            token = source["sheet_token"]
            sheet_dir = SHEETS / token
            sheet_dir.mkdir(parents=True, exist_ok=True)
            print(f"MUSEUM_PROPOSE {ordinal}/{len(sources)} {token}", flush=True)
            try:
                full = read_rgb(Path(source["original_path"]))
                segmented, scale = resize_fit(full)
                save_rgb(sheet_dir / "source_preview.jpg", segmented)
                with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
                    auto_records = automatic.generate(segmented)
                candidates: list[dict[str, Any]] = []
                for index, record in enumerate(sorted(auto_records, key=lambda row: float(row["predicted_iou"]), reverse=True)[:90]):
                    mask = record["segmentation"].astype(bool)
                    candidates.append({
                        "id": f"sam_{index:02d}", "kind": "sam_auto",
                        "model_score": float(record["predicted_iou"]), "mask": mask,
                        "feature": mask_features(mask),
                    })
                prompt = prompt_for(source["category"])
                batch = processor(images=Image.fromarray(segmented), text=prompt, return_tensors="pt")
                cuda_batch = {key: value.to("cuda") for key, value in batch.items()}
                with torch.inference_mode():
                    output = dino(**cuda_batch)
                grounded = shared.post_process_grounding(processor, output, cuda_batch["input_ids"], (segmented.shape[0], segmented.shape[1]))
                boxes = grounded["boxes"].detach().cpu().numpy()
                scores = grounded["scores"].detach().cpu().numpy()
                labels = [str(value) for value in grounded.get("labels", [])]
                predictor.set_image(segmented)
                boxed = segmented.copy()
                colour_seed, sky_metrics = colour_luminance_sky(segmented)
                accepted_sky: list[np.ndarray] = []
                for index, (box, score) in enumerate(zip(boxes[:28], scores[:28])):
                    label = labels[index] if index < len(labels) else ""
                    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
                        masks, sam_scores, _ = predictor.predict(box=box.astype(np.float32), multimask_output=True)
                    if "sky" in label.lower():
                        ranked = []
                        for mask_index, mask in enumerate(masks.astype(bool)):
                            intersection = int(np.logical_and(mask, colour_seed).sum())
                            precision = intersection / max(1, int(mask.sum()))
                            coverage = intersection / max(1, int(colour_seed.sum()))
                            ranked.append((0.72 * precision + 0.28 * min(1.0, coverage * 3.0), mask_index, precision, intersection))
                        _, best, precision, intersection = max(ranked)
                        if precision >= 0.18 and intersection >= 250:
                            accepted_sky.append(masks[best].astype(bool))
                    else:
                        best = int(np.argmax(sam_scores))
                        mask = masks[best].astype(bool)
                        candidates.append({
                            "id": f"dino_sam_{index:02d}", "kind": "dino_sam",
                            "model_score": float(score), "sam_score": float(sam_scores[best]),
                            "label": label, "mask": mask, "feature": mask_features(mask),
                        })
                    x0, y0, x1, y1 = box.round().astype(int)
                    cv2.rectangle(boxed, (x0, y0), (x1, y1), (220, 50, 50), 3)
                    cv2.putText(boxed, f"{index}:{score:.2f} {label[:22]}", (x0, max(18, y0 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (220, 50, 50), 2)
                save_rgb(sheet_dir / "grounding_dino_boxes.jpg", boxed)
                sky_union = np.logical_or.reduce(accepted_sky) if accepted_sky else np.zeros_like(colour_seed)
                lab = cv2.cvtColor(segmented, cv2.COLOR_RGB2LAB)
                hsv = cv2.cvtColor(segmented, cv2.COLOR_RGB2HSV)
                red, _, blue = (segmented[:, :, index].astype(np.int16) for index in range(3))
                loose_sky = (lab[:, :, 0] >= 94) & (hsv[:, :, 1] <= 178) & (blue >= red - 88)
                refined_sky = colour_seed | (sky_union & loose_sky)
                refined_sky = cv2.morphologyEx(refined_sky.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8)).astype(bool)
                refined_sky = morphology.remove_small_objects(refined_sky, min_size=90)
                save_mask(sheet_dir / "a2_sky_mask.png", refined_sky)
                selected = choose_one(candidates, source["category"])
                entries: list[tuple[str, np.ndarray]] = [("SOURCE", segmented), ("DINO BOXES", boxed)]
                decision = None
                if selected is not None:
                    mask_name = f"chosen_01_{selected['side']}_{selected['id']}.png"
                    save_mask(sheet_dir / mask_name, selected["mask"])
                    entries.append((f"CHOSEN {selected['side']} {selected['id']} q={selected['quality']:.3f}", overlay(segmented, selected["mask"], (240, 62, 82))))
                    decision = {
                        "number": 1, "side": selected["side"], "candidate_id": selected["id"],
                        "candidate_kind": selected["kind"], "model_label": selected.get("label"),
                        "model_score": round(float(selected.get("model_score", 0)), 6),
                        "quality": round(float(selected["quality"]), 6),
                        "feature": selected["feature"], "bbox_fill_fraction": round(float(selected["bbox_fill_fraction"]), 6),
                        "maximum_other_mask_iou": round(float(selected["maximum_other_mask_iou"]), 6),
                        "mask_file": mask_name,
                        "selection_method": "deterministic one-element museum ranking over local SAM and Grounding DINO proposals",
                    }
                alternatives = sorted(candidates, key=candidate_quality, reverse=True)[:8]
                for candidate in alternatives:
                    if selected is not None and candidate["id"] == selected["id"]:
                        continue
                    entries.append((f"ALT {candidate['id']} {candidate['kind']} q={candidate_quality(candidate):.3f}", overlay(segmented, candidate["mask"], (40, 180, 210))))
                entries.append(("A2 SKY MASK", overlay(segmented, refined_sky, (50, 210, 255))))
                shared.contact_sheet(entries, sheet_dir / "PROPOSALS_CONTACT_SHEET.jpg")
                proposal_data = {
                    "source": source,
                    "segmentation_size_px": [int(segmented.shape[1]), int(segmented.shape[0])],
                    "segmentation_scale": scale,
                    "prompt": prompt,
                    "sam_raw_count": len(auto_records),
                    "grounding_dino_box_count": len(boxes),
                    "sky": {**sky_metrics, "sam_accepted_count": len(accepted_sky), "refined_sky_pixels": int(refined_sky.sum())},
                    "selected": [decision] if decision else [],
                }
                atomic_json(sheet_dir / "proposals.json", proposal_data)
                results.append({
                    "candidate_id": source["candidate_id"], "sheet_token": token,
                    "status": "proposed" if decision else "no_passing_proposal",
                    "proposal_count": 1 if decision else 0, "sheet_dir": str(sheet_dir),
                })
                del full, segmented, candidates, cuda_batch, output
                gc.collect()
                torch.cuda.empty_cache()
            except Exception as exc:
                results.append({
                    "candidate_id": source["candidate_id"], "sheet_token": token,
                    "status": "proposal_failed", "proposal_count": 0,
                    "reason": f"{type(exc).__name__}: {exc}",
                })
        del predictor, automatic, sam, dino, processor
        gc.collect()
        torch.cuda.empty_cache()
        manifest = {
            "schema_version": SCHEMA, "started": started, "finished": now(),
            "status": "complete_with_failures" if any(row["status"] != "proposed" for row in results) else "complete",
            "offline": True, "network_used": False, "model_setup_seconds": setup_seconds,
            "sam_checkpoint": str(SAM_CHECKPOINT), "grounding_dino_revision": DINO_REVISION,
            "gpu_gate": gate, "sources": results,
        }
        atomic_json(OUT / "PROPOSALS.json", manifest)
        return manifest
    except Exception as exc:
        fatal = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        shared.mark_gpu("done" if fatal is None else "fatal", "museum_archive_proposals", started=started, finished=now(), fatal=fatal, output=str(OUT))


def contour_float(mask: np.ndarray) -> np.ndarray:
    contours = measure.find_contours(mask.astype(np.uint8), 0.5, fully_connected="high")
    if not contours:
        raise RuntimeError("No contour found")
    line = max(contours, key=lambda points: len(points))
    return np.column_stack([line[:, 1], line[:, 0]])


def resample_closed(points: np.ndarray, spacing_px: float) -> np.ndarray:
    closed = np.vstack([points, points[0]])
    lengths = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    cumulative = np.concatenate([[0.0], np.cumsum(lengths)])
    samples = np.arange(0.0, cumulative[-1], max(0.5, spacing_px))
    return np.column_stack((np.interp(samples, cumulative, closed[:, 0]), np.interp(samples, cumulative, closed[:, 1])))


def simplify_curve(points: np.ndarray, tolerance_px: float) -> np.ndarray:
    polygon = Polygon(points)
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    if polygon.geom_type == "MultiPolygon":
        polygon = max(polygon.geoms, key=lambda geometry: geometry.area)
    simplified = polygon.simplify(tolerance_px, preserve_topology=True)
    return np.asarray(simplified.exterior.coords[:-1], dtype=np.float64)


def odd_window(requested: int, count: int) -> int:
    maximum = count if count % 2 == 1 else count - 1
    value = min(maximum, max(5, requested + (requested % 2 == 0)))
    return max(3, value)


def interior_holes(mask: np.ndarray, minimum_area: int) -> tuple[np.ndarray, int]:
    filled = ndimage.binary_fill_holes(mask)
    holes = filled & ~mask
    labels, count = ndimage.label(holes)
    kept = np.zeros_like(mask, dtype=bool)
    kept_count = 0
    for index in range(1, count + 1):
        component = labels == index
        if int(component.sum()) >= minimum_area:
            kept |= component
            kept_count += 1
    return kept, kept_count


def a2_curve_smooth_with_holes(raw: np.ndarray, sky: np.ndarray, target_height_cm: float) -> tuple[np.ndarray, dict[str, Any]]:
    ys, _ = np.where(raw)
    if not len(ys):
        raise RuntimeError("empty raw mask")
    height_px = int(ys.max() - ys.min() + 1)
    cm_per_px = target_height_cm / max(1, height_px)
    feature_px = max(3, round(3.0 / cm_per_px))
    if feature_px % 2 == 0:
        feature_px += 1
    minimum_hole_area = max(24, feature_px * feature_px)
    holes, hole_count = interior_holes(raw, minimum_hole_area)
    exterior = ndimage.binary_fill_holes(raw)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (feature_px, feature_px))
    physical = cv2.morphologyEx(exterior.astype(np.uint8), cv2.MORPH_CLOSE, kernel)
    physical = cv2.morphologyEx(physical, cv2.MORPH_OPEN, kernel).astype(bool)
    distance = ndimage.distance_transform_edt(physical) - ndimage.distance_transform_edt(~physical)
    sigma_px = max(1.0, 2.2 / cm_per_px)
    raster = ndimage.gaussian_filter(distance, sigma=sigma_px) >= 0.0
    clearance_px = max(1, round(3.0 / cm_per_px))
    sky_clearance = cv2.dilate(sky.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * clearance_px + 1, 2 * clearance_px + 1))).astype(bool)
    raster &= ~sky_clearance
    raster = largest_component(raster)
    dense = resample_closed(contour_float(raster), max(0.75, 0.75 / cm_per_px))
    window = odd_window(round((18.0 / cm_per_px) / max(0.75, 0.75 / cm_per_px)), len(dense))
    if len(dense) >= 5 and window >= 5:
        dense = np.column_stack((savgol_filter(dense[:, 0], window, 3, mode="wrap"), savgol_filter(dense[:, 1], window, 3, mode="wrap")))
    curve = simplify_curve(dense, max(0.5, 0.55 / cm_per_px))
    vector = np.zeros_like(raw, dtype=np.uint8)
    cv2.fillPoly(vector, [np.round(curve).astype(np.int32)], 1)
    final = largest_component(vector.astype(bool) & ~sky)
    # Reapply substantial original see-through openings after exterior smoothing.
    holes = cv2.morphologyEx(holes.astype(np.uint8), cv2.MORPH_OPEN, kernel).astype(bool)
    final &= ~holes
    final = largest_component(final)
    return final, {
        "pass": bool(final.any()),
        "method": "A2 sky subtraction plus physical-scale signed-distance/Savitzky-Golay exterior; substantial source holes restored",
        "target_height_cm": target_height_cm,
        "geometry_height_px": height_px,
        "cm_per_source_pixel": round(cm_per_px, 6),
        "jigsaw_min_feature_cm": 3.0,
        "jigsaw_kernel_px": feature_px,
        "signed_distance_gaussian_sigma_px": round(sigma_px, 4),
        "preserved_hole_count": hole_count,
        "preserved_hole_minimum_area_px": minimum_hole_area,
        "before_area_px": int(raw.sum()),
        "after_area_px": int(final.sum()),
    }


def add_backbone(mask: np.ndarray, rgb: np.ndarray, side: str) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    if side not in {"L", "R"}:
        return mask, rgb, {"applied": False, "reason": "C element"}
    output = mask.copy()
    art = rgb.copy()
    ys = np.flatnonzero(np.any(mask, axis=1))
    if not len(ys):
        return output, art, {"applied": False, "reason": "empty"}
    row_edges = []
    for y in ys:
        xs = np.flatnonzero(mask[y])
        row_edges.append(int(xs.min() if side == "L" else xs.max()))
    fixed = int(np.quantile(row_edges, 0.08 if side == "L" else 0.92))
    added = np.zeros_like(mask, dtype=bool)
    maximum_gap = max(8, round(mask.shape[1] * 0.22))
    for y, edge in zip(ys, row_edges):
        if side == "L" and edge >= fixed and edge - fixed <= maximum_gap:
            added[y, fixed:edge + 1] = True
            art[y, fixed:edge] = art[y, edge]
        elif side == "R" and edge <= fixed and fixed - edge <= maximum_gap:
            added[y, edge:fixed + 1] = True
            art[y, edge + 1:fixed + 1] = art[y, edge]
    output |= added
    return output, art, {
        "applied": True, "side": side, "backbone_x": fixed,
        "maximum_fill_gap_px": maximum_gap, "added_pixels": int((added & ~mask).sum()),
        "art_extension": "nearest foreground row pixel replicated across newly solid backbone strip",
    }


def crop_masked(rgb: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray, list[int]]:
    ys, xs = np.where(mask)
    if not len(xs):
        raise RuntimeError("empty mask before crop")
    pad = max(8, round(max(int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)) * 0.035))
    x0, y0 = max(0, int(xs.min()) - pad), max(0, int(ys.min()) - pad)
    x1, y1 = min(mask.shape[1], int(xs.max()) + pad + 1), min(mask.shape[0], int(ys.max()) + pad + 1)
    return rgb[y0:y1, x0:x1], mask[y0:y1, x0:x1], [x0, y0, x1, y1]


def prepare() -> dict[str, Any]:
    census_payload = read_json(OUT / "MUSEUM_CENSUS.json")
    proposal_payload = read_json(OUT / "PROPOSALS.json")
    proposal_map = {row["sheet_token"]: row for row in proposal_payload["sources"]}
    elements: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    counters: dict[tuple[str, str], int] = defaultdict(int)
    for source in census_payload["eligible_sources"]:
        token = source["sheet_token"]
        status = proposal_map.get(token, {})
        if status.get("status") != "proposed":
            failures.append({"candidate_id": source["candidate_id"], "sheet": token, "tier": "measured", "reason": status.get("reason", status.get("status", "no proposal"))})
            continue
        sheet_dir = Path(status["sheet_dir"])
        proposal = read_json(sheet_dir / "proposals.json")
        selection = proposal["selected"][0]
        visual_review_reason = MANUAL_HAND_FIX_REASONS.get(source["candidate_id"])
        if visual_review_reason is not None:
            artist = artist_token(str(source["candidate"].get("artist", "")))
            counter_key = (source["passage"], artist)
            counters[counter_key] += 1
            number = counters[counter_key]
            suffix = safe_token(f"MUS_{source['passage']}_{artist}_{number:02d}_{selection['side']}", limit=72)
            busy_overlap = bool(
                int(source["candidate"].get("cutout_difficulty", 0)) >= 3
                or 0.45 <= float(selection["maximum_other_mask_iou"]) <= 0.82
            )
            record = {
                "asset_suffix": suffix, "asset_name": f"SM_FlatV3_{suffix}",
                "candidate_id": source["candidate_id"], "sheet": token, "source": source,
                "element_number": 1, "side": selection["side"], "passage": source["passage"],
                "category": source["category"],
                "target_height_cm": 120.0 if source["category"] == "sea" else 1000.0,
                "rgba_path": str(sheet_dir / "PROPOSALS_CONTACT_SHEET.jpg"),
                "crop_source_xyxy": None, "selection": selection,
                "jigsaw": {"pass": False, "preserved_hole_count": 0, "method": "not run; held by measured visual-review gate"},
                "backbone": {"applied": False, "reason": "not run; hand fix required"},
                "a2_sky_subtraction_applied": False, "sky_pixels_removed": 0,
                "busy_overlap_hand_fix_flag": busy_overlap,
                "visual_review_hand_fix_reason": visual_review_reason,
                "hand_fix_required_before_build": True, "build_authorized": False,
                "contact_image_kind": "proposal sheet retained in place of a rejected full-resolution cut",
            }
            elements.append(record)
            failures.append({
                "candidate_id": source["candidate_id"], "sheet": token, "element": suffix,
                "tier": "measured", "reason": f"{visual_review_reason}; contact sheet retained for a hand silhouette fix",
            })
            continue
        full = read_rgb(Path(source["original_path"]))
        small_mask = np.asarray(Image.open(sheet_dir / selection["mask_file"]).convert("L")) >= 128
        mask = cv2.resize(small_mask.astype(np.uint8), (full.shape[1], full.shape[0]), interpolation=cv2.INTER_NEAREST).astype(bool)
        small_sky = np.asarray(Image.open(sheet_dir / "a2_sky_mask.png").convert("L")) >= 128
        sky_probability = cv2.resize(small_sky.astype(np.float32), (full.shape[1], full.shape[0]), interpolation=cv2.INTER_CUBIC)
        sky_full = ndimage.gaussian_filter(sky_probability, sigma=2.0) >= 0.50
        applies_a2_sky = source["category"] == "landscape"
        raw = mask & ~sky_full if applies_a2_sky else mask
        target_height = 120.0 if source["category"] == "sea" else 1000.0
        try:
            if source["category"] in {"landscape", "cloud", "painted_mass"}:
                geometry, jigsaw = a2_curve_smooth_with_holes(raw, sky_full if applies_a2_sky else np.zeros_like(raw), target_height)
            else:
                geometry, jigsaw = shared.smooth_jigsaw(raw, target_height)
                filled = ndimage.binary_fill_holes(raw)
                source_holes = filled & ~raw
                labels, count = ndimage.label(source_holes)
                retained_holes = 0
                minimum = max(24, int(raw.sum() * 0.0002))
                for index in range(1, count + 1):
                    component = labels == index
                    if int(component.sum()) >= minimum:
                        geometry &= ~component
                        retained_holes += 1
                jigsaw["preserved_hole_count"] = retained_holes
                jigsaw["method"] = "physical-scale jigsaw smoothing with substantial source holes restored"
            if not jigsaw.get("pass") or not geometry.any():
                raise RuntimeError("empty after jigsaw")
            geometry, art, backbone = add_backbone(geometry, full, selection["side"])
            crop_rgb, crop_mask, crop_box = crop_masked(art, geometry)
            alpha = crop_mask.astype(np.uint8) * 255
            category = source["category"]
            feature = selection["feature"]
            severe = bool(
                selection["quality"] < 0.52
                or float(feature["area_fraction"]) > 0.68
                or float(selection["bbox_fill_fraction"]) < 0.10
                or (category == "architecture" and float(feature["area_fraction"]) < 0.04)
            )
            busy_overlap = bool(
                int(source["candidate"].get("cutout_difficulty", 0)) >= 3
                or 0.45 <= float(selection["maximum_other_mask_iou"]) <= 0.82
            )
            hand_fix_required = severe
            artist = artist_token(str(source["candidate"].get("artist", "")))
            counter_key = (source["passage"], artist)
            counters[counter_key] += 1
            number = counters[counter_key]
            suffix = safe_token(f"MUS_{source['passage']}_{artist}_{number:02d}_{selection['side']}", limit=72)
            element_dir = ELEMENTS / suffix
            rgba_path = element_dir / f"{suffix}.png"
            save_rgba(rgba_path, crop_rgb, alpha)
            record = {
                "asset_suffix": suffix, "asset_name": f"SM_FlatV3_{suffix}",
                "candidate_id": source["candidate_id"], "sheet": token, "source": source,
                "element_number": 1, "side": selection["side"], "passage": source["passage"],
                "category": category, "target_height_cm": target_height,
                "rgba_path": str(rgba_path), "crop_source_xyxy": crop_box,
                "selection": selection, "jigsaw": jigsaw, "backbone": backbone,
                "a2_sky_subtraction_applied": applies_a2_sky,
                "sky_pixels_removed": int(np.logical_and(mask, sky_full).sum()) if applies_a2_sky else 0,
                "busy_overlap_hand_fix_flag": busy_overlap,
                "visual_review_hand_fix_reason": None,
                "hand_fix_required_before_build": hand_fix_required,
                "build_authorized": not hand_fix_required,
            }
            atomic_json(element_dir / "element.json", record)
            elements.append(record)
            if hand_fix_required:
                reason = "automatic cut failed the severe ambiguity/coverage gate"
                failures.append({"candidate_id": source["candidate_id"], "sheet": token, "element": suffix, "tier": "measured", "reason": f"{reason}; contact sheet retained for a hand silhouette fix"})
        except Exception as exc:
            failures.append({"candidate_id": source["candidate_id"], "sheet": token, "tier": "measured", "reason": f"prepare failed: {type(exc).__name__}: {exc}"})
        del full
    build_picks = []
    for element in elements:
        if not element["build_authorized"]:
            continue
        source = element["source"]
        relative = Path(element["rgba_path"]).relative_to(PROJECT).as_posix()
        side = element["side"]
        manual_flag = None
        if element["busy_overlap_hand_fix_flag"]:
            manual_flag = f"{element['asset_name']}: busy overlap flagged for close silhouette review; V3 gates passed only the generated geometry, not artistic acceptance"
        build_picks.append({
            "canonical_path": relative,
            "source_kind": "museum_archive_A2_sky_or_semantic_SAM_cutout",
            "source_pixel_size": [int(Image.open(element["rgba_path"]).width), int(Image.open(element["rgba_path"]).height)],
            "source_has_alpha": True,
            "source_sha256": sha256(Path(element["rgba_path"])),
            "flat_type": "sea row / top-border C" if element["category"] == "sea" else "top/border C" if side == "C" else "wing L/R",
            "target_height_cm": element["target_height_cm"],
            "target_height_status": "1000 cm museum wing/border; 120 cm explicit sea-row exception",
            "side": side, "passage": element["passage"], "mesh_being_replaced": None,
            "alpha_mode": "embedded_alpha", "asset_suffix": element["asset_suffix"],
            "build_authorized": True,
            "flags": {
                "busy_overlap_hand_fix": element["busy_overlap_hand_fix_flag"],
                "manual_review_flag": manual_flag,
                "a2_sky_subtraction": element["a2_sky_subtraction_applied"],
                "preserved_hole_count": element["jigsaw"].get("preserved_hole_count", 0),
                "museum_archive": True,
            },
            "source_authority": {
                "candidate_id": source["candidate_id"], "source_json": source["metadata_path"],
                "licence": source["licence"], "credit_line": source.get("credit_line"),
                "attribution_required": source.get("attribution_required"),
                "use_restriction": source.get("use_restriction"), "original_sha256": source["original_sha256"],
            },
        })
    picks_payload = {
        "schema_version": SCHEMA,
        "batch_label": "Flat V3 museum-archive wings and borders",
        "authority": ["Gary, 2 Oct: we need all the good wings we can get cheaply"],
        "selection_summary": {"build_ready_with_embedded_alpha": len(build_picks)},
        "expected_asset_count": len(build_picks),
        "expected_asset_names": [f"SM_FlatV3_{pick['asset_suffix']}" for pick in build_picks],
        "build_picks": build_picks,
    }
    atomic_json(OUT / "BUILD_PICKS.json", picks_payload)
    provenance = {
        "schema_version": SCHEMA, "generated": now(), "offline": True, "network_used": False,
        "selection_rule": census_payload["selection_rule"],
        "score_authority": census_payload["score_authority"],
        "stage_skip_authority": census_payload["stage_skip_authority"],
        "all_source_records": census_payload["all_records"],
        "eligible_source_count": census_payload["eligible_count"],
        "prepared_element_count": len(elements), "scheduled_build_count": len(build_picks),
        "elements": elements, "failures": failures,
        "marlia_cc_by_credit_if_used": "sailko, Villa reale di marlia, teatro di verzura 00.JPG, self-photographed, CC BY 2.5",
        "marlia_used_in_this_batch": any(row["candidate_id"] == "COMMONS-4351390" and row.get("status") == "eligible" for row in census_payload["all_records"]),
    }
    atomic_json(OUT / "provenance.json", provenance)
    return provenance


def run_batch(preflight: bool = False) -> int:
    command = [
        str(VENV_PYTHON), str(PROJECT / "Tools" / "FlatV3" / "batch_build.py"),
        "--picks", str(OUT / "BUILD_PICKS.json"), "--output", str(OUT),
    ]
    if preflight:
        command.append("--preflight")
    return subprocess.run(command, cwd=PROJECT, check=False).returncode


def cap_pending_sources(max_long_side: int = 4096) -> dict[str, Any]:
    """Bound only failed/unbuilt rasters before their mandatory 2x upscale.

    Completed flats retain their exact source hashes.  Museum originals and
    proposal masks are never modified; only generated RGBA build inputs are
    resized, with the old/new dimensions and hashes recorded.
    """
    picks_path = OUT / "BUILD_PICKS.json"
    payload = read_json(picks_path)
    changes: list[dict[str, Any]] = []
    for pick in payload["build_picks"]:
        suffix = pick["asset_suffix"]
        status_path = OUT / "flats" / suffix / "status.json"
        if status_path.is_file() and read_json(status_path).get("status") == "built":
            continue
        source_path = PROJECT / pick["canonical_path"]
        with Image.open(source_path) as opened:
            rgba = opened.convert("RGBA")
            old_size = [rgba.width, rgba.height]
            old_hash = sha256(source_path)
            longest = max(rgba.size)
            if longest <= max_long_side:
                continue
            scale = max_long_side / float(longest)
            new_size = [max(1, round(rgba.width * scale)), max(1, round(rgba.height * scale))]
            resized = rgba.resize(tuple(new_size), Image.Resampling.LANCZOS)
        temporary = source_path.with_suffix(".cap.tmp.png")
        resized.save(temporary, optimize=True)
        os.replace(temporary, source_path)
        new_hash = sha256(source_path)
        pick["source_pixel_size"] = new_size
        pick["source_sha256"] = new_hash
        pick.setdefault("flags", {})["pre_upscale_source_cap"] = {
            "maximum_long_side_px": max_long_side,
            "old_size_px": old_size,
            "new_size_px": new_size,
            "old_sha256": old_hash,
            "reason": "avoid excessive memory/pagefile use before the required true 2x upscale",
        }
        changes.append({
            "asset_suffix": suffix, "old_size_px": old_size, "new_size_px": new_size,
            "old_sha256": old_hash, "new_sha256": new_hash,
        })
    atomic_json(picks_path, payload)
    result = {
        "schema_version": SCHEMA, "generated": now(), "max_long_side_px": max_long_side,
        "changed_count": len(changes), "changes": changes,
        "completed_flats_untouched": True, "museum_originals_untouched": True,
    }
    atomic_json(OUT / "SOURCE_CAPS.json", result)
    return result


def recover_exited_gpu_marker() -> dict[str, Any]:
    """Mark a Windows process-object zombie interrupted, never a live owner."""
    state = read_json(GPU_MARKER)
    owner = int(state.get("pid", 0))
    if state.get("status") != "running" or owner <= 0:
        return {"changed": False, "reason": "marker is not running", "state": state}
    if os.name != "nt":
        return {"changed": False, "reason": "Windows-only exited-object check", "state": state}
    import ctypes

    handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, owner)
    if not handle:
        return {"changed": False, "reason": "owner process cannot be opened", "state": state}
    exit_code = ctypes.c_ulong()
    try:
        if not ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return {"changed": False, "reason": "owner exit code cannot be read", "state": state}
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)
    if exit_code.value == 259:
        return {"changed": False, "reason": "owner is STILL_ACTIVE", "state": state}
    recovered = {
        **state, "status": "interrupted", "recovered": now(),
        "measured_owner_exit_code": int(exit_code.value),
        "recovery_reason": "Windows retained an openable exited process object; courtesy wait would not clear",
    }
    atomic_json(GPU_MARKER, recovered)
    return {"changed": True, "owner_pid": owner, "owner_exit_code": int(exit_code.value)}


def prepare_targeted_resume() -> dict[str, Any]:
    """Create a complete status census and target only non-passing flats."""
    picks_payload = read_json(OUT / "BUILD_PICKS.json")
    statuses: list[dict[str, Any]] = []
    targets: list[str] = []
    for pick in picks_payload["build_picks"]:
        suffix = pick["asset_suffix"]
        folder = OUT / "flats" / suffix
        status_path = folder / "status.json"
        validation_path = folder / "validation.json"
        status = read_json(status_path) if status_path.is_file() else {}
        validation = read_json(validation_path) if validation_path.is_file() else {}
        fbx_path = folder / f"SM_FlatV3_{suffix}.fbx"
        measured_pass = bool(validation.get("pass")) and fbx_path.is_file()
        if status.get("status") == "built" or measured_pass:
            if measured_pass and status.get("status") != "built":
                status.update({
                    "schema_version": SCHEMA, "asset_name": f"SM_FlatV3_{suffix}",
                    "asset_suffix": suffix, "passage": pick.get("passage"),
                    "source": str(PROJECT / pick["canonical_path"]), "status": "built",
                    "validation_pass": True, "fbx": str(fbx_path), "recovered": now(),
                    "recovery_reason": "existing FBX and validation.json measured pass after interrupted duplicate run",
                })
                atomic_json(status_path, status)
            statuses.append(status)
            continue
        pick["peel_percent"] = 4.0
        pick.setdefault("flags", {})["resume_peel_percent"] = {
            "value": 4.0, "approved_range": [4.0, 6.0],
            "reason": "lowest approved pilot peel coverage for sparse museum silhouettes",
        }
        targets.append(suffix)
        placeholder = {
            **status, "schema_version": SCHEMA, "asset_name": f"SM_FlatV3_{suffix}",
            "asset_suffix": suffix, "passage": pick.get("passage"),
            "source": str(PROJECT / pick["canonical_path"]), "status": "not_run",
            "validation_pass": False, "resume_target": True,
        }
        folder.mkdir(parents=True, exist_ok=True)
        atomic_json(status_path, placeholder)
        statuses.append(placeholder)
    atomic_json(OUT / "BUILD_PICKS.json", picks_payload)
    manifest_path = OUT / "MANIFEST.json"
    manifest = read_json(manifest_path) if manifest_path.is_file() else {"schema_version": SCHEMA}
    manifest.update({
        "status": "interrupted_resume_prepared", "items": statuses,
        "scheduled_asset_count": len(statuses),
        "built_count": sum(row.get("status") == "built" for row in statuses),
        "failure_count": sum(row.get("status") == "failed" for row in statuses),
        "resume_targets": targets, "resume_prepared": now(),
    })
    atomic_json(manifest_path, manifest)
    result = {
        "schema_version": SCHEMA, "generated": now(), "built_preserved": manifest["built_count"],
        "target_count": len(targets), "targets": targets,
        "peel_percent_for_targets": 4.0,
    }
    atomic_json(OUT / "RESUME_CENSUS.json", result)
    return result


def run_targeted_resume() -> int:
    targets = read_json(OUT / "RESUME_CENSUS.json")["targets"]
    command = [
        str(VENV_PYTHON), str(PROJECT / "Tools" / "FlatV3" / "batch_build.py"),
        "--picks", str(OUT / "BUILD_PICKS.json"), "--output", str(OUT),
    ]
    for target in targets:
        command += ["--repair", target]
    return subprocess.run(command, cwd=PROJECT, check=False).returncode


def build_failure_detail(status: dict[str, Any]) -> str | None:
    if status.get("status") == "built":
        return None
    suffix = status.get("asset_suffix")
    if suffix:
        validation_path = OUT / "flats" / suffix / "validation.json"
        if validation_path.is_file():
            validation = read_json(validation_path)
            checks = validation.get("checks", validation)
            failed = [name for name, value in checks.items() if isinstance(value, dict) and value.get("pass") is False]
            if failed:
                return "FBX validation gate(s) failed: " + ", ".join(failed)
    log_path = Path(status["log"]) if status.get("log") else None
    if log_path and log_path.is_file():
        for line in reversed(log_path.read_text(encoding="utf-8", errors="replace").splitlines()):
            match = re.match(r"^(?:RuntimeError|ValueError|AssertionError|MemoryError):\s*(.+)$", line.strip())
            if match and not match.group(1).startswith(("Command failed with exit code", "FBX validation failed")):
                return match.group(1)
    return status.get("reason") or status.get("status")


def image_thumb(path: Path, size: tuple[int, int] = (430, 330), rgba_on_paper: bool = False) -> Image.Image:
    with Image.open(path) as source:
        if rgba_on_paper:
            rgba = source.convert("RGBA")
            paper = Image.new("RGBA", rgba.size, (214, 200, 170, 255))
            paper.alpha_composite(rgba)
            image = paper.convert("RGB")
        else:
            image = source.convert("RGB")
    image.thumbnail(size, Image.Resampling.LANCZOS)
    return image


def finalize() -> dict[str, Any]:
    provenance = read_json(OUT / "provenance.json")
    batch = read_json(OUT / "MANIFEST.json") if (OUT / "MANIFEST.json").is_file() else {"items": [], "status": "not_run"}
    statuses = {row.get("asset_suffix"): row for row in batch.get("items", [])}
    elements = provenance["elements"]
    for element in elements:
        if not element["build_authorized"]:
            element["build_status"] = "hand_fix_required"
            element["build_failure"] = "automatic silhouette was not authorized for V3 build"
            element["validation_pass"] = False
            continue
        status = statuses.get(element["asset_suffix"], {})
        element["build_status"] = status.get("status", "not_run")
        element["build_failure"] = build_failure_detail(status)
        element["validation_pass"] = bool(status.get("validation_pass", False))
        element["fbx"] = status.get("fbx")
    passing = [row for row in elements if row["build_status"] == "built" and row["validation_pass"]]
    failures = list(provenance.get("failures", []))
    for record in provenance["all_source_records"]:
        if record["status"] != "eligible":
            failures.append({
                "candidate_id": record["candidate_id"], "tier": "declaration-proven" if record["status"] == "excluded_use_restriction" else "measured",
                "reason": record["status"] + (f": {record.get('use_restriction')}" if record.get("use_restriction") else ""),
            })
    for row in elements:
        if row["build_authorized"] and row["build_status"] != "built":
            failures.append({"candidate_id": row["candidate_id"], "sheet": row["sheet"], "element": row["asset_suffix"], "tier": "measured", "reason": row["build_failure"] or row["build_status"]})
    lines = [
        "# Flat V3 museum archive failures and hand-fix queue", "",
        "Claims are tagged per the project evidence convention.", "", "## Failures / exclusions", "",
    ]
    if failures:
        for failure in failures:
            subject = failure.get("element") or failure.get("sheet") or failure.get("candidate_id")
            lines.append(f"- **{failure.get('tier', 'measured')}:** `{subject}` — {failure.get('reason')}.")
    else:
        lines.append("- **measured:** none.")
    lines += ["", "## Busy overlaps / close silhouette review", ""]
    hand = [row for row in elements if row["busy_overlap_hand_fix_flag"]]
    if hand:
        for row in hand:
            lines.append(f"- **inferred:** `{row['asset_name']}` — source score or proposal overlap marks this as busy; inspect its source/cut pair before production acceptance.")
    else:
        lines.append("- **measured:** none flagged by the deterministic overlap gate.")
    (OUT / "FAILURES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    cards: list[dict[str, str]] = []
    passage_rows: list[Image.Image] = []
    for passage in ("P01", "P02", "P03", "P04", "P05", "P06"):
        group = [row for row in elements if row["passage"] == passage]
        if not group:
            continue
        header = Image.new("RGB", (960, 72), (62, 48, 36))
        ImageDraw.Draw(header).text((20, 24), f"{passage} — {len(group)} museum element(s)", fill=(245, 236, 214), font=FONT)
        passage_rows.append(header)
        for row in group:
            source_path = Path(row["source"]["original_path"])
            element_path = Path(row["rgba_path"])
            canvas = Image.new("RGB", (960, 390), (30, 32, 35))
            left = image_thumb(source_path)
            right = image_thumb(element_path, rgba_on_paper=True)
            canvas.paste(left, ((450 - left.width) // 2, 12 + (330 - left.height) // 2))
            canvas.paste(right, (490 + (450 - right.width) // 2, 12 + (330 - right.height) // 2))
            caption = f"{row['asset_name']} | {row['build_status']} | holes={row['jigsaw'].get('preserved_hole_count', 0)} | busy={row['busy_overlap_hand_fix_flag']}"
            ImageDraw.Draw(canvas).text((14, 354), caption[:155], fill=(238, 238, 238), font=FONT)
            passage_rows.append(canvas)
            cards.append({
                "passage": passage, "asset": row["asset_name"], "status": row["build_status"],
                "source": source_path.as_uri(), "element": element_path.relative_to(OUT).as_posix(),
                "licence": str(row["source"]["licence"]), "credit": str(row["source"].get("credit_line") or ""),
                "busy": str(row["busy_overlap_hand_fix_flag"]),
            })
    if passage_rows:
        height = sum(image.height for image in passage_rows)
        combined = Image.new("RGB", (960, height), (22, 24, 27))
        y = 0
        for row in passage_rows:
            combined.paste(row, (0, y))
            y += row.height
        combined.save(OUT / "CONTACT_SHEET.jpg", quality=90, subsampling=0)
    html_parts = [
        "<!doctype html><meta charset='utf-8'><title>Flat V3 Museum</title>",
        "<style>body{background:#181a1e;color:#eee;font:14px system-ui;margin:24px}section{margin-top:34px}article{border-top:1px solid #555;padding:18px 0}img{width:46%;height:360px;object-fit:contain;background:#d6c8aa;margin-right:2%}p{color:#ccc}</style>",
        "<h1>Flat V3 museum-archive elements</h1><p>Grouped by passage; every cut is shown beside its complete source.</p>",
    ]
    for passage in ("P01", "P02", "P03", "P04", "P05", "P06"):
        group = [card for card in cards if card["passage"] == passage]
        if not group:
            continue
        html_parts.append(f"<section><h2>{passage}</h2>")
        for card in group:
            html_parts.append(
                "<article><h3>" + html.escape(card["asset"]) + "</h3><div>"
                + "<img src='" + html.escape(card["source"]) + "'><img src='" + html.escape(card["element"]) + "'></div>"
                + "<p>status=" + html.escape(card["status"]) + " · busy=" + html.escape(card["busy"])
                + " · licence=" + html.escape(card["licence"]) + (" · credit=" + html.escape(card["credit"]) if card["credit"] else "") + "</p></article>"
            )
        html_parts.append("</section>")
    (OUT / "CONTACT_SHEET.html").write_text("".join(html_parts), encoding="utf-8")

    by_passage = {passage: {"prepared": 0, "built": 0, "failed_or_handfix": 0} for passage in ("P01", "P02", "P03", "P04", "P05", "P06")}
    for row in elements:
        bucket = by_passage[row["passage"]]
        bucket["prepared"] += 1
        if row in passing:
            bucket["built"] += 1
        else:
            bucket["failed_or_handfix"] += 1
    summary = {
        "eligible_sources": provenance["eligible_source_count"],
        "prepared_elements": len(elements), "scheduled_builds": provenance["scheduled_build_count"],
        "passing_flats": len(passing), "failed_or_handfix_elements": len(elements) - len(passing),
        "busy_overlap_flags": len(hand), "batch_status": batch.get("status", "not_run"),
        "by_passage": by_passage,
        "free_space_gib_after": round(shutil.disk_usage(PROJECT).free / (1024 ** 3), 3),
    }
    provenance["elements"] = elements
    provenance["batch_summary"] = summary
    atomic_json(OUT / "provenance.json", provenance)
    atomic_json(OUT / "SUMMARY.json", summary)
    summary_lines = [
        "# Flat V3 museum archive summary", "", f"Updated: {now()}", "",
        f"- **measured:** {summary['eligible_sources']} eligible source sheets after rights and StageRefs dedupe.",
        f"- **measured:** {summary['prepared_elements']} elements prepared; {summary['passing_flats']} V3 flats passed all batch gates.",
        f"- **measured:** {summary['failed_or_handfix_elements']} failed or were held for hand silhouette work; see `FAILURES.md`.",
        f"- **measured:** {summary['busy_overlap_flags']} busy-overlap/close-review flags.",
        f"- **measured:** E: free space after finalization: {summary['free_space_gib_after']} GiB.",
        "- **inferred / not claimed:** no Unreal import, Show assignment, rendered in-show acceptance, or human art-direction acceptance was performed.",
    ]
    (OUT / "SUMMARY.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("census", "propose", "prepare", "cap-pending", "recover-stale-marker", "prepare-resume", "resume", "preflight", "build", "finalize", "all"), default="all")
    args = parser.parse_args()
    if args.phase in {"census", "all"}:
        result = census()
        print(json.dumps({"phase": "census", "eligible": result["eligible_count"], "status_counts": result["status_counts"]}), flush=True)
    if args.phase in {"propose", "all"}:
        result = propose()
        print(json.dumps({"phase": "propose", "status": result["status"]}), flush=True)
    if args.phase in {"prepare", "all"}:
        result = prepare()
        print(json.dumps({"phase": "prepare", "elements": result["prepared_element_count"], "scheduled": result["scheduled_build_count"]}), flush=True)
    if args.phase == "cap-pending":
        result = cap_pending_sources()
        print(json.dumps({"phase": "cap-pending", "changed": result["changed_count"]}), flush=True)
    if args.phase == "recover-stale-marker":
        result = recover_exited_gpu_marker()
        print(json.dumps({"phase": "recover-stale-marker", **result}), flush=True)
    if args.phase == "prepare-resume":
        result = prepare_targeted_resume()
        print(json.dumps({"phase": "prepare-resume", "built_preserved": result["built_preserved"], "targets": result["target_count"]}), flush=True)
    if args.phase == "resume":
        code = run_targeted_resume()
        print(json.dumps({"phase": "resume", "exit_code": code}), flush=True)
        return code
    if args.phase == "preflight":
        code = run_batch(preflight=True)
        print(json.dumps({"phase": "preflight", "exit_code": code}), flush=True)
        return code
    batch_code = 0
    if args.phase in {"build", "all"}:
        free_gib = shutil.disk_usage(PROJECT).free / (1024 ** 3)
        scheduled = read_json(OUT / "BUILD_PICKS.json").get("expected_asset_count", 0)
        estimated_gib = 0.13 * float(scheduled) + 2.0
        if free_gib < estimated_gib:
            raise RuntimeError(f"STOP: estimated {estimated_gib:.2f} GiB required for {scheduled} assets, only {free_gib:.2f} GiB free on E:")
        batch_code = run_batch()
        print(json.dumps({"phase": "build", "exit_code": batch_code}), flush=True)
    if args.phase in {"finalize", "all"}:
        result = finalize()
        print(json.dumps({"phase": "finalize", **result}), flush=True)
    return batch_code


if __name__ == "__main__":
    raise SystemExit(main())
