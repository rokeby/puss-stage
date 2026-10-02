"""Offline Baroque stage-reference cutter and Flat V3 batch orchestrator.

The source census is deliberately metadata-first.  Restricted records are kept
in the provenance report, but can never become build picks.  GPU phases obey the
shared ``DerivedAssets/FlatV3/Overnight/RUNNING.json`` courtesy marker.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import gc
import hashlib
import html
import inspect
import json
import math
import os
import re
import subprocess
import sys
import time
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


PROJECT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = Path(r"D:\PussStageSources\FlatV3")
TOOL_ROOT = Path(r"D:\PussStageTools\FlatV3")
VENV_PYTHON = TOOL_ROOT / "venv" / "Scripts" / "python.exe"
OUT = PROJECT / "DerivedAssets" / "FlatV3" / "Overnight" / "StageRefs"
SHEETS = OUT / "sheets"
ELEMENTS = OUT / "elements"
GPU_MARKER = PROJECT / "DerivedAssets" / "FlatV3" / "Overnight" / "RUNNING.json"
SAM_CHECKPOINT = TOOL_ROOT / "models" / "sam2.1_hiera_large.pt"
SAM_CONFIG = "configs/sam2.1/sam2.1_hiera_l.yaml"
DINO_REVISION = "12bdfa3120f3e7ec7b434d90674b3396eccf88eb"
DINO_SNAPSHOT = (
    TOOL_ROOT
    / "cache"
    / "huggingface"
    / "hub"
    / "models--IDEA-Research--grounding-dino-base"
    / "snapshots"
    / DINO_REVISION
)
SEGMENT_MAX = 1280
FONT = ImageFont.load_default()
SCHEMA = 1

STAGE_PATTERN = re.compile(
    r"(stage design|scenic design|theater set|theatre set|set design|bibiena|"
    r"juvarra|burnacini|torelli|silvestre|kusel|k[üu]sel|scenograph|"
    r"palace court|banquet hall|architectural fantasy|oval hall|columned hall|"
    r"tempietto|proscenium)",
    re.I,
)
PROMPT = (
    "theatrical scenery wing. painted stage flat. architectural facade. "
    "column and entablature. archway. balustrade. statue on a plinth. "
    "stage border. back shutter."
)


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temp, path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_token(value: str, fallback: str = "Anonymous") -> str:
    token = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    return token[:96] or fallback


def artist_token(artist: str) -> str:
    for name, token in (
        (r"Bibiena", "Bibiena"),
        (r"Juvarra", "Juvarra"),
        (r"Burnacini", "Burnacini"),
        (r"Torelli", "Torelli"),
        (r"Silvestre", "Silvestre"),
        (r"K[üu]s+el", "Kusel"),
        (r"K[üu]ssel", "Kusel"),
    ):
        if re.search(name, artist, re.I):
            return token
    if re.search(r"unknown|anonymous|follower", artist, re.I) or not artist.strip():
        return "Anonymous"
    words = re.findall(r"[A-Za-z]+", artist)
    return safe_token(words[-1] if words else "Anonymous")


def asset_sheet_token(sheet_token: str) -> str:
    """Keep FBX node names below the format's practical truncation boundary."""
    if len(sheet_token) <= 24:
        return sheet_token
    digest = hashlib.sha1(sheet_token.encode("utf-8")).hexdigest()[:7]
    if sheet_token.lower().startswith("smithsonian_"):
        numeric = re.findall(r"\d+", sheet_token)
        tail = numeric[-1][-8:] if numeric else sheet_token[-8:]
        return f"CH_{tail}_{digest}"
    return f"{sheet_token[:14]}_{digest}"


def source_original(metadata_path: Path) -> Path | None:
    originals = sorted(p for p in metadata_path.parent.glob("original.*") if p.is_file())
    return originals[0] if originals else None


def source_record(path: Path) -> dict[str, Any] | None:
    data = read_json(path)
    candidate = data.get("candidate_record", {})
    original = source_original(path)
    if original is None:
        return None
    group = path.relative_to(SOURCE_ROOT).parts[0]
    title = str(candidate.get("title", ""))
    artist = str(candidate.get("artist", ""))
    include = group == "REFERENCE" or bool(STAGE_PATTERN.search(f"{title} {artist}"))
    if not include:
        return None
    with Image.open(original) as image:
        size = [int(image.width), int(image.height)]
    licence = candidate.get(
        "license_text",
        candidate.get("licence_text", candidate.get("license", candidate.get("licence", "UNCLEAR"))),
    )
    return {
        "group": group,
        "directory": path.parent.name,
        "metadata_path": str(path),
        "original_path": str(original),
        "original_sha256": sha256(original),
        "pixel_size": size,
        "title": title,
        "artist": artist,
        "artist_token": artist_token(artist),
        "licence": licence or "UNCLEAR",
        "use_restriction": data.get("use_restriction"),
        "object_url": candidate.get("object_url"),
        "stage_like": bool(STAGE_PATTERN.search(f"{title} {artist}")),
    }


def census() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    holdings: list[dict[str, Any]] = []
    for path in SOURCE_ROOT.rglob("source.json"):
        with contextlib.suppress(Exception):
            record = source_record(path)
            if record:
                holdings.append(record)
    by_hash: dict[str, list[dict[str, Any]]] = {}
    for record in holdings:
        by_hash.setdefault(record["original_sha256"], []).append(record)
    sources: list[dict[str, Any]] = []
    for digest, copies in by_hash.items():
        copies.sort(key=lambda row: (row["group"] != "REFERENCE", row["group"], row["directory"]))
        chosen = dict(copies[0])
        restrictions = [row["use_restriction"] for row in copies if row.get("use_restriction")]
        chosen["use_restriction"] = restrictions[0] if restrictions else None
        chosen["holdings"] = [
            {key: row[key] for key in ("group", "directory", "metadata_path", "original_path")}
            for row in copies
        ]
        chosen["eligible"] = not bool(restrictions)
        chosen["sheet_token"] = safe_token(chosen["directory"])
        sources.append(chosen)
    sources.sort(key=lambda row: (not row["eligible"], row["artist_token"], row["sheet_token"]))
    payload = {
        "schema_version": SCHEMA,
        "generated": now(),
        "scope": "all unique REFERENCE originals plus named Baroque stage-design holdings in other groups",
        "dedupe": "SHA-256 of original bytes; REFERENCE holding preferred for path naming",
        "holding_count": len(holdings),
        "unique_original_count": len(sources),
        "eligible_count": sum(row["eligible"] for row in sources),
        "restricted_count": sum(not row["eligible"] for row in sources),
        "sources": sources,
    }
    atomic_json(OUT / "SOURCE_CENSUS.json", payload)
    return payload


def process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return ctypes.get_last_error() == 5
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def wait_for_gpu() -> dict[str, Any]:
    waited: str | None = None
    while GPU_MARKER.is_file():
        with contextlib.suppress(Exception):
            state = read_json(GPU_MARKER)
            owner = int(state.get("pid", 0))
            if state.get("status") == "running" and owner != os.getpid() and process_exists(owner):
                if waited is None:
                    waited = now()
                    print(f"FLAT_V3_GPU_WAIT owner_pid={owner}", flush=True)
                time.sleep(15)
                continue
        break
    return {"marker": str(GPU_MARKER), "waited_from": waited, "acquired": now()}


def mark_gpu(status: str, phase: str, **extra: Any) -> None:
    atomic_json(
        GPU_MARKER,
        {
            "started": extra.pop("started", now()),
            "pid": os.getpid(),
            "status": status,
            "batch_output": str(OUT),
            "phase": phase,
            **extra,
        },
    )


def read_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"))


def resize_fit(rgb: np.ndarray, max_side: int = SEGMENT_MAX) -> tuple[np.ndarray, float]:
    height, width = rgb.shape[:2]
    scale = min(1.0, max_side / max(width, height))
    if scale == 1.0:
        return rgb, 1.0
    return cv2.resize(rgb, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA), scale


def save_rgb(path: Path, rgb: np.ndarray, quality: int = 92) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb.astype(np.uint8), "RGB").save(path, quality=quality, subsampling=0)


def save_rgba(path: Path, rgb: np.ndarray, alpha: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rgba = np.dstack((rgb.astype(np.uint8), alpha.astype(np.uint8)))
    Image.fromarray(rgba, "RGBA").save(path, compress_level=4)


def overlay(rgb: np.ndarray, mask: np.ndarray, color: tuple[int, int, int]) -> np.ndarray:
    result = rgb.astype(np.float32).copy()
    tint = np.asarray(color, np.float32)
    result[mask] = result[mask] * 0.48 + tint * 0.52
    return np.clip(result, 0, 255).astype(np.uint8)


def labelled(image: np.ndarray, text: str, width: int = 390, height: int = 300) -> Image.Image:
    canvas = Image.new("RGB", (width, height + 42), (28, 30, 34))
    item = Image.fromarray(image.astype(np.uint8), "RGB")
    item.thumbnail((width - 12, height - 12), Image.Resampling.LANCZOS)
    canvas.paste(item, ((width - item.width) // 2, (height - item.height) // 2))
    ImageDraw.Draw(canvas).text((8, height + 8), text[:118], fill=(235, 235, 235), font=FONT)
    return canvas


def contact_sheet(entries: list[tuple[str, np.ndarray]], path: Path, cols: int = 3) -> None:
    cards = [labelled(image, label) for label, image in entries]
    rows = math.ceil(len(cards) / cols)
    sheet = Image.new("RGB", (390 * cols, 342 * rows), (22, 24, 27))
    for index, card in enumerate(cards):
        sheet.paste(card, ((index % cols) * 390, (index // cols) * 342))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, quality=90, subsampling=0)


def post_process_grounding(processor: Any, outputs: Any, input_ids: torch.Tensor, size: tuple[int, int]) -> Any:
    function = processor.post_process_grounded_object_detection
    params = inspect.signature(function).parameters
    kwargs: dict[str, Any] = {
        "outputs": outputs,
        "input_ids": input_ids,
        "target_sizes": [size],
        "text_threshold": 0.14,
    }
    if "box_threshold" in params:
        kwargs["box_threshold"] = 0.14
    else:
        kwargs["threshold"] = 0.14
    return function(**kwargs)[0]


def mask_features(mask: np.ndarray) -> dict[str, float | list[int]]:
    ys, xs = np.where(mask)
    if not len(xs):
        return {"area_fraction": 0.0, "bbox": [0, 0, 0, 0], "cx": 0.5, "cy": 0.5, "wf": 0.0, "hf": 0.0}
    height, width = mask.shape
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
    return {
        "area_fraction": float(mask.mean()),
        "bbox": [x0, y0, x1, y1],
        "cx": float(xs.mean() / width),
        "cy": float(ys.mean() / height),
        "wf": float((x1 - x0) / width),
        "hf": float((y1 - y0) / height),
    }


def mask_iou(left: np.ndarray, right: np.ndarray) -> float:
    union = np.logical_or(left, right).sum()
    return float(np.logical_and(left, right).sum() / union) if union else 0.0


def candidate_quality(candidate: dict[str, Any]) -> float:
    feature = candidate["feature"]
    area = float(feature["area_fraction"])
    fill = area / max(0.001, float(feature["wf"]) * float(feature["hf"]))
    aspect_bonus = min(1.0, float(feature["hf"]) / max(0.06, float(feature["wf"])))
    return (
        0.45 * float(candidate.get("model_score", 0.5))
        + 0.24 * min(1.0, area / 0.18)
        + 0.18 * min(1.0, fill / 0.65)
        + 0.13 * aspect_bonus
    )


def choose_candidates(candidates: list[dict[str, Any]], stage_like: bool) -> list[dict[str, Any]]:
    valid = []
    for candidate in candidates:
        feature = candidate["feature"]
        if not (0.008 <= feature["area_fraction"] <= 0.68):
            continue
        if feature["hf"] < 0.18 or feature["wf"] < 0.055:
            continue
        candidate["quality"] = candidate_quality(candidate)
        valid.append(candidate)
    valid.sort(key=lambda row: row["quality"], reverse=True)
    deduped: list[dict[str, Any]] = []
    for candidate in valid:
        if all(mask_iou(candidate["mask"], prior["mask"]) < 0.68 for prior in deduped):
            deduped.append(candidate)
        if len(deduped) >= 32:
            break

    limits = {"L": 2 if stage_like else 1, "R": 2 if stage_like else 1, "C": 1}
    selected: list[dict[str, Any]] = []
    for side in ("L", "R", "C"):
        ranked: list[tuple[float, dict[str, Any]]] = []
        for candidate in deduped:
            feature = candidate["feature"]
            cx, cy, wf, hf = feature["cx"], feature["cy"], feature["wf"], feature["hf"]
            if side == "L" and cx >= 0.53:
                continue
            if side == "R" and cx <= 0.47:
                continue
            if side == "C" and not (wf >= 0.34 and (cy <= 0.58 or hf >= 0.45)):
                continue
            side_bonus = (0.5 - cx) if side == "L" else (cx - 0.5) if side == "R" else 0.25 * wf
            vertical_bonus = 0.12 * min(1.0, hf / max(0.08, wf)) if side != "C" else 0.12 * min(1.0, wf / max(0.08, hf))
            ranked.append((candidate["quality"] + 0.25 * side_bonus + vertical_bonus, candidate))
        ranked.sort(key=lambda item: item[0], reverse=True)
        for _, candidate in ranked:
            if any(mask_iou(candidate["mask"], prior["mask"]) > 0.48 for prior in selected):
                continue
            chosen = dict(candidate)
            chosen["side"] = side
            selected.append(chosen)
            if sum(row["side"] == side for row in selected) >= limits[side]:
                break
    return selected


def propose() -> dict[str, Any]:
    from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

    payload = read_json(OUT / "SOURCE_CENSUS.json") if (OUT / "SOURCE_CENSUS.json").is_file() else census()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for the declared offline SAM/Grounding DINO proposal phase")
    gate = wait_for_gpu()
    started = now()
    mark_gpu("running", "stage_refs_proposals", started=started, gpu_gate=gate)
    results: list[dict[str, Any]] = []
    fatal: str | None = None
    try:
        setup = time.perf_counter()
        sam = build_sam2(SAM_CONFIG, str(SAM_CHECKPOINT), device="cuda")
        auto = SAM2AutomaticMaskGenerator(
            sam,
            points_per_side=20,
            points_per_batch=64,
            pred_iou_thresh=0.72,
            stability_score_thresh=0.84,
            crop_n_layers=0,
            min_mask_region_area=220,
        )
        predictor = SAM2ImagePredictor(sam)
        processor = AutoProcessor.from_pretrained(
            str(DINO_SNAPSHOT), local_files_only=True
        )
        dino = AutoModelForZeroShotObjectDetection.from_pretrained(
            str(DINO_SNAPSHOT), local_files_only=True
        ).to("cuda").eval()
        setup_seconds = round(time.perf_counter() - setup, 3)
        for ordinal, source in enumerate(payload["sources"], 1):
            sheet_dir = SHEETS / source["sheet_token"]
            sheet_dir.mkdir(parents=True, exist_ok=True)
            if not source["eligible"]:
                results.append({**source, "status": "excluded_use_restriction", "proposal_count": 0})
                continue
            print(f"STAGE_REFS_PROPOSE {ordinal}/{len(payload['sources'])} {source['sheet_token']}", flush=True)
            try:
                full = read_rgb(Path(source["original_path"]))
                seg, scale = resize_fit(full)
                save_rgb(sheet_dir / "source_preview.jpg", seg)
                with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
                    auto_records = auto.generate(seg)
                candidates: list[dict[str, Any]] = []
                for index, record in enumerate(sorted(auto_records, key=lambda row: float(row["predicted_iou"]), reverse=True)[:90]):
                    mask = record["segmentation"].astype(bool)
                    candidates.append(
                        {
                            "id": f"sam_{index:02d}",
                            "kind": "sam_auto",
                            "model_score": float(record["predicted_iou"]),
                            "mask": mask,
                            "feature": mask_features(mask),
                        }
                    )
                batch = processor(images=Image.fromarray(seg), text=PROMPT, return_tensors="pt")
                cuda_batch = {key: value.to("cuda") for key, value in batch.items()}
                with torch.inference_mode():
                    dino_output = dino(**cuda_batch)
                grounded = post_process_grounding(
                    processor, dino_output, cuda_batch["input_ids"], (seg.shape[0], seg.shape[1])
                )
                boxes = grounded["boxes"].detach().cpu().numpy()
                scores = grounded["scores"].detach().cpu().numpy()
                labels = [str(value) for value in grounded.get("labels", [])]
                predictor.set_image(seg)
                boxed = seg.copy()
                for index, (box, score) in enumerate(zip(boxes[:24], scores[:24])):
                    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
                        masks, sam_scores, _ = predictor.predict(
                            point_coords=None,
                            point_labels=None,
                            box=box.astype(np.float32),
                            multimask_output=True,
                        )
                    best = int(np.argmax(sam_scores))
                    mask = masks[best].astype(bool)
                    candidates.append(
                        {
                            "id": f"dino_sam_{index:02d}",
                            "kind": "dino_sam",
                            "model_score": float(score),
                            "sam_score": float(sam_scores[best]),
                            "label": labels[index] if index < len(labels) else "",
                            "mask": mask,
                            "feature": mask_features(mask),
                        }
                    )
                    x0, y0, x1, y1 = box.round().astype(int)
                    cv2.rectangle(boxed, (x0, y0), (x1, y1), (220, 50, 50), 3)
                    cv2.putText(boxed, f"{index}:{score:.2f}", (x0, max(18, y0 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (220, 50, 50), 2)
                save_rgb(sheet_dir / "grounding_dino_boxes.jpg", boxed)
                selected = choose_candidates(candidates, bool(source["stage_like"]))
                entries: list[tuple[str, np.ndarray]] = [("source sheet", seg), ("Grounding DINO proposals", boxed)]
                decisions = []
                for number, candidate in enumerate(selected, 1):
                    mask_name = f"chosen_{number:02d}_{candidate['side']}_{candidate['id']}.png"
                    Image.fromarray((candidate["mask"] * 255).astype(np.uint8), "L").save(sheet_dir / mask_name)
                    entries.append((f"CHOSEN {number} {candidate['side']} {candidate['id']} q={candidate['quality']:.3f}", overlay(seg, candidate["mask"], (240, 62, 82))))
                    overlap = max(
                        (
                            mask_iou(candidate["mask"], other["mask"])
                            for other in candidates
                            if other["id"] != candidate["id"]
                        ),
                        default=0.0,
                    )
                    decisions.append(
                        {
                            "number": number,
                            "side": candidate["side"],
                            "candidate_id": candidate["id"],
                            "candidate_kind": candidate["kind"],
                            "model_label": candidate.get("label"),
                            "model_score": round(float(candidate.get("model_score", 0)), 6),
                            "quality": round(float(candidate["quality"]), 6),
                            "feature": candidate["feature"],
                            "mask_file": mask_name,
                            "busy_overlap": overlap > 0.72,
                            "selection_method": "deterministic side/shape ranking over SAM and Grounding DINO proposals; retained in contact sheet for review",
                        }
                    )
                alternatives = sorted(candidates, key=candidate_quality, reverse=True)[: max(0, 10 - len(selected))]
                for candidate in alternatives:
                    entries.append((f"ALT {candidate['id']} {candidate['kind']} q={candidate_quality(candidate):.3f}", overlay(seg, candidate["mask"], (40, 180, 210))))
                contact_sheet(entries, sheet_dir / "PROPOSALS_CONTACT_SHEET.jpg")
                decision_payload = {
                    "source": source,
                    "segmentation_size_px": [int(seg.shape[1]), int(seg.shape[0])],
                    "segmentation_scale": scale,
                    "sam_raw_count": len(auto_records),
                    "grounding_dino_box_count": len(boxes),
                    "grounding_dino_prompt": PROMPT,
                    "selected": decisions,
                }
                atomic_json(sheet_dir / "proposals.json", decision_payload)
                results.append({**source, "status": "proposed" if decisions else "no_passing_proposal", "proposal_count": len(decisions), "sheet_dir": str(sheet_dir)})
                del full, seg, candidates, selected, cuda_batch, dino_output
                gc.collect()
                torch.cuda.empty_cache()
            except Exception as exc:
                results.append({**source, "status": "proposal_failed", "proposal_count": 0, "reason": f"{type(exc).__name__}: {exc}"})
        del predictor, auto, sam, dino, processor
        gc.collect()
        torch.cuda.empty_cache()
        manifest = {
            "schema_version": SCHEMA,
            "started": started,
            "finished": now(),
            "status": "complete_with_failures" if any(row["status"] in {"proposal_failed", "no_passing_proposal"} for row in results) else "complete",
            "offline": True,
            "network_used": False,
            "model_setup_seconds": setup_seconds,
            "sam_checkpoint": str(SAM_CHECKPOINT),
            "grounding_dino_revision": DINO_REVISION,
            "grounding_dino_snapshot": str(DINO_SNAPSHOT),
            "gpu_gate": gate,
            "sources": results,
        }
        atomic_json(OUT / "PROPOSALS.json", manifest)
        return manifest
    except Exception as exc:
        fatal = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        mark_gpu("done" if fatal is None else "fatal", "stage_refs_proposals", started=started, finished=now(), fatal=fatal)


def smooth_jigsaw(mask: np.ndarray, target_height_cm: float) -> tuple[np.ndarray, dict[str, Any]]:
    ys, _ = np.where(mask)
    if not len(ys):
        return mask, {"pass": False, "reason": "empty mask"}
    px_per_cm = max(0.01, (int(ys.max()) - int(ys.min()) + 1) / target_height_cm)
    minimum_px = max(1, round(3.0 * px_per_cm))
    opened = ndimage.binary_opening(mask, structure=np.ones((minimum_px, minimum_px), bool)) if minimum_px > 1 else mask
    closed = ndimage.binary_closing(opened, structure=np.ones((minimum_px, minimum_px), bool)) if minimum_px > 1 else opened
    sigma = max(0.55, 0.75 * px_per_cm)
    smooth = ndimage.gaussian_filter(closed.astype(np.float32), sigma=sigma) >= 0.5
    labels, count = ndimage.label(smooth)
    if count:
        sizes = ndimage.sum(smooth, labels, range(1, count + 1))
        smooth = labels == (int(np.argmax(sizes)) + 1)
    return smooth, {
        "pass": bool(smooth.any()),
        "minimum_feature_cm": 3.0,
        "minimum_feature_px": minimum_px,
        "smoothing_sigma_px": round(float(sigma), 4),
        "foreground_percent": round(float(smooth.mean() * 100), 5),
    }


def envelope_quad(mask: np.ndarray) -> np.ndarray:
    ys, xs = np.where(mask)
    if not len(xs):
        raise ValueError("empty mask")
    y0, y1 = np.quantile(ys, [0.03, 0.97])
    height = max(8.0, y1 - y0)
    bands = [(y0, y0 + 0.18 * height), (y1 - 0.18 * height, y1)]
    pairs = []
    for low, high in bands:
        band_x = xs[(ys >= low) & (ys <= high)]
        if len(band_x) < 20:
            band_x = xs
        pairs.append((float(np.quantile(band_x, 0.04)), float(np.quantile(band_x, 0.96))))
    return np.asarray(
        [[pairs[0][0], y0], [pairs[0][1], y0], [pairs[1][1], y1], [pairs[1][0], y1]],
        dtype=np.float32,
    )


def residual_skew(rgb: np.ndarray, alpha: np.ndarray) -> dict[str, Any]:
    grey = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(grey, 55, 145)
    edges[alpha < 128] = 0
    minimum = max(24, round(min(rgb.shape[:2]) * 0.08))
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=35, minLineLength=minimum, maxLineGap=12)
    deviations: list[float] = []
    if lines is not None:
        for x0, y0, x1, y1 in lines[:, 0]:
            angle = abs(math.degrees(math.atan2(y1 - y0, x1 - x0))) % 180.0
            deviations.append(min(angle, abs(90.0 - angle), abs(180.0 - angle)))
    value = float(np.median(deviations)) if deviations else float("nan")
    return {
        "residual_skew_degrees_median": None if math.isnan(value) else round(value, 4),
        "hough_line_count": len(deviations),
        "pass_le_5_degrees": bool(deviations and value <= 5.0),
    }


def rectify(rgb: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    quad = envelope_quad(mask)
    top = np.linalg.norm(quad[1] - quad[0])
    bottom = np.linalg.norm(quad[2] - quad[3])
    left = np.linalg.norm(quad[3] - quad[0])
    right = np.linalg.norm(quad[2] - quad[1])
    width = max(64, round((top + bottom) * 0.5))
    height = max(96, round((left + right) * 0.5))
    destination = np.asarray([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], np.float32)
    transform = cv2.getPerspectiveTransform(quad, destination)
    warped_rgb = cv2.warpPerspective(rgb, transform, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    warped_mask = cv2.warpPerspective(mask.astype(np.uint8) * 255, transform, (width, height), flags=cv2.INTER_NEAREST)
    # Keep transparent breathing room around the rectified outline.  A robust
    # envelope can legitimately touch all four destination edges, but the Flat
    # V3 embedded-alpha preflight requires both foreground and background.
    pad = max(4, round(max(width, height) * 0.035))
    padded_rgb = cv2.copyMakeBorder(warped_rgb, pad, pad, pad, pad, cv2.BORDER_REPLICATE)
    padded_mask = cv2.copyMakeBorder(warped_mask, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)
    skew = residual_skew(padded_rgb, padded_mask)
    stats = {
        "method": "homography from robust upper/lower mask-envelope quadrilateral to a frontal rectangle",
        "source_quad_xy": [[round(float(x), 3), round(float(y), 3)] for x, y in quad],
        "rectified_content_size_px": [width, height],
        "transparent_padding_px": pad,
        "output_size_px": [int(padded_rgb.shape[1]), int(padded_rgb.shape[0])],
        "top_bottom_width_ratio_before": round(float(top / max(1.0, bottom)), 6),
        **skew,
    }
    return padded_rgb, padded_mask, stats


def prepare() -> dict[str, Any]:
    census_payload = read_json(OUT / "SOURCE_CENSUS.json")
    proposals = read_json(OUT / "PROPOSALS.json")
    proposal_map = {row["original_sha256"]: row for row in proposals["sources"]}
    elements: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for source in census_payload["sources"]:
        if not source["eligible"]:
            failures.append({"sheet": source["sheet_token"], "tier": "declaration-proven", "reason": f"excluded use_restriction: {source['use_restriction']}"})
            continue
        result = proposal_map.get(source["original_sha256"], {})
        if result.get("status") != "proposed":
            failures.append({"sheet": source["sheet_token"], "tier": "measured", "reason": result.get("reason", result.get("status", "no proposal record"))})
            continue
        sheet_dir = Path(result["sheet_dir"])
        proposal_data = read_json(sheet_dir / "proposals.json")
        full = read_rgb(Path(source["original_path"]))
        seg_w, seg_h = proposal_data["segmentation_size_px"]
        for selection in proposal_data["selected"]:
            number = int(selection["number"])
            side = selection["side"]
            mask_small = np.asarray(Image.open(sheet_dir / selection["mask_file"]).convert("L")) >= 128
            mask = cv2.resize(mask_small.astype(np.uint8), (full.shape[1], full.shape[0]), interpolation=cv2.INTER_NEAREST).astype(bool)
            mask, jigsaw = smooth_jigsaw(mask, 1000.0)
            if not jigsaw["pass"]:
                failures.append({"sheet": source["sheet_token"], "element": number, "tier": "measured", "reason": "empty after jigsaw"})
                continue
            try:
                frontal_rgb, frontal_alpha, rectification = rectify(full, mask)
            except Exception as exc:
                failures.append({"sheet": source["sheet_token"], "element": number, "tier": "measured", "reason": f"rectification failed: {type(exc).__name__}: {exc}"})
                continue
            short_sheet = asset_sheet_token(source["sheet_token"])
            suffix = safe_token(f"REF_{source['artist_token']}_{short_sheet}_{number:02d}_{side}")
            element_dir = ELEMENTS / suffix
            rgba_path = element_dir / f"{suffix}.png"
            save_rgba(rgba_path, frontal_rgb, frontal_alpha)
            busy = bool(selection.get("busy_overlap")) or not rectification["pass_le_5_degrees"]
            record = {
                "asset_suffix": suffix,
                "asset_name": f"SM_FlatV3_{suffix}",
                "sheet": source["sheet_token"],
                "source": source,
                "element_number": number,
                "side": side,
                "rgba_path": str(rgba_path),
                "jigsaw": jigsaw,
                "rectification": rectification,
                "busy_overlap_hand_fix": busy,
                "selection": selection,
            }
            atomic_json(element_dir / "element.json", record)
            elements.append(record)
        del full
    build_picks = []
    for element in elements:
        relative = Path(element["rgba_path"]).relative_to(PROJECT).as_posix()
        side = element["side"]
        build_picks.append(
            {
                "canonical_path": relative,
                "source_kind": "rectified_baroque_stage_reference_cutout",
                "source_pixel_size": element["rectification"]["output_size_px"],
                "source_has_alpha": True,
                "source_sha256": sha256(Path(element["rgba_path"])),
                "flat_type": "top/border C" if side == "C" else "wing L/R",
                "target_height_cm": 1000.0,
                "target_height_status": "Gary 2 Oct: wings 1000 cm; borders encoded C",
                "side": side,
                "passage": "REF",
                "mesh_being_replaced": None,
                "alpha_mode": "embedded_alpha",
                "asset_suffix": element["asset_suffix"],
                "build_authorized": True,
                "flags": {
                    "busy_overlap_hand_fix": element["busy_overlap_hand_fix"],
                    "residual_skew_degrees": element["rectification"]["residual_skew_degrees_median"],
                    "ink_on_aged_paper": True,
                    "fuser_colouring": False,
                },
                "source_authority": {
                    "source_json": element["source"]["metadata_path"],
                    "licence": element["source"]["licence"],
                    "use_restriction": element["source"]["use_restriction"],
                    "original_sha256": element["source"]["original_sha256"],
                },
            }
        )
    picks_payload = {
        "schema_version": SCHEMA,
        "batch_label": "Flat V3 Baroque stage-reference individual flats",
        "authority": ["Gary, 2 Oct: make wing cutouts from all those stage design references"],
        "expected_asset_count": len(build_picks),
        "expected_asset_names": [f"SM_FlatV3_{pick['asset_suffix']}" for pick in build_picks],
        "build_picks": build_picks,
    }
    atomic_json(OUT / "BUILD_PICKS.json", picks_payload)
    provenance = {
        "schema_version": SCHEMA,
        "generated": now(),
        "default_medium": "ink on aged paper",
        "source_count": len(census_payload["sources"]),
        "eligible_source_count": census_payload["eligible_count"],
        "restricted_source_count": census_payload["restricted_count"],
        "element_count": len(elements),
        "sources": census_payload["sources"],
        "elements": elements,
        "failures": failures,
    }
    atomic_json(OUT / "provenance.json", provenance)
    return provenance


def compact_existing_names() -> dict[str, Any]:
    """Rewrite manifests to compact asset names without recomputing image data."""
    provenance = read_json(OUT / "provenance.json")
    by_legacy: dict[str, str] = {}
    for element in provenance["elements"]:
        legacy = element["asset_suffix"]
        compact = safe_token(
            f"REF_{element['source']['artist_token']}_{asset_sheet_token(element['sheet'])}_"
            f"{int(element['element_number']):02d}_{element['side']}"
        )
        element["legacy_asset_suffix"] = legacy
        element["asset_suffix"] = compact
        element["asset_name"] = f"SM_FlatV3_{compact}"
        by_legacy[legacy] = compact
        element_path = Path(element["rgba_path"]).parent / "element.json"
        atomic_json(element_path, element)
    picks = read_json(OUT / "BUILD_PICKS.json")
    for pick in picks["build_picks"]:
        legacy = pick["asset_suffix"]
        pick["legacy_asset_suffix"] = legacy
        pick["asset_suffix"] = by_legacy[legacy]
    picks["expected_asset_names"] = [
        f"SM_FlatV3_{pick['asset_suffix']}" for pick in picks["build_picks"]
    ]
    atomic_json(OUT / "BUILD_PICKS.json", picks)
    atomic_json(OUT / "provenance.json", provenance)
    return {
        "elements": len(provenance["elements"]),
        "maximum_asset_name_length": max(len(row["asset_name"]) for row in provenance["elements"]),
    }


def run_batch() -> int:
    command = [
        str(VENV_PYTHON),
        str(PROJECT / "Tools" / "FlatV3" / "batch_build.py"),
        "--picks",
        str(OUT / "BUILD_PICKS.json"),
        "--output",
        str(OUT),
    ]
    return subprocess.run(command, cwd=PROJECT, check=False).returncode


def image_thumb(path: Path, size: tuple[int, int] = (420, 320)) -> Image.Image:
    with Image.open(path) as source:
        rgba = source.convert("RGBA")
        background = Image.new("RGBA", rgba.size, (214, 200, 170, 255))
        background.alpha_composite(rgba)
        image = background.convert("RGB")
    image.thumbnail(size, Image.Resampling.LANCZOS)
    return image


def build_failure_detail(status: dict[str, Any]) -> str | None:
    """Return the measured inner gate failure instead of the subprocess wrapper."""
    if status.get("status") == "built":
        return None

    suffix = status.get("asset_suffix")
    if suffix:
        validation_path = OUT / "flats" / suffix / "validation.json"
        if validation_path.is_file():
            validation = read_json(validation_path)
            checks = validation.get("checks", validation)
            failed_gates = [
                name
                for name, value in checks.items()
                if isinstance(value, dict) and value.get("pass") is False
            ]
            if failed_gates:
                return "FBX validation gate(s) failed: " + ", ".join(failed_gates)

    log_path = Path(status["log"]) if status.get("log") else None
    if log_path and log_path.is_file():
        for line in reversed(log_path.read_text(encoding="utf-8", errors="replace").splitlines()):
            match = re.match(r"^(?:RuntimeError|ValueError|AssertionError|MemoryError):\s*(.+)$", line.strip())
            if not match:
                continue
            detail = match.group(1)
            if detail.startswith("Command failed with exit code"):
                continue
            if detail.startswith("FBX validation failed"):
                continue
            return detail

    return status.get("reason") or status.get("status")


def finalize() -> dict[str, Any]:
    provenance = read_json(OUT / "provenance.json")
    batch = read_json(OUT / "MANIFEST.json") if (OUT / "MANIFEST.json").is_file() else {"items": []}
    statuses = {row.get("asset_suffix"): row for row in batch.get("items", [])}
    elements = provenance["elements"]
    for element in elements:
        status = statuses.get(element["asset_suffix"], {})
        element["build_status"] = status.get("status", "not_run")
        element["build_failure"] = build_failure_detail(status)
        element["validation_pass"] = status.get("validation_pass", False)
        element["fbx"] = status.get("fbx")

    passing = [row for row in elements if row["build_status"] == "built" and row["validation_pass"]]
    ranked = sorted(
        passing,
        key=lambda row: (
            row["busy_overlap_hand_fix"],
            -(row["selection"].get("quality") or 0),
            row["rectification"].get("residual_skew_degrees_median") or 999,
        ),
    )
    fuser = {row["asset_suffix"] for row in ranked[: min(10, len(ranked))]}
    for row in elements:
        row["fuser_colouring_candidate"] = row["asset_suffix"] in fuser

    counts: dict[str, dict[str, int]] = {}
    for source in provenance["sources"]:
        counts[source["sheet_token"]] = {"selected": 0, "built": 0, "failed": 0, "hand_fix": 0}
    for row in elements:
        count = counts[row["sheet"]]
        count["selected"] += 1
        if row["build_status"] == "built":
            count["built"] += 1
        else:
            count["failed"] += 1
        if row["busy_overlap_hand_fix"]:
            count["hand_fix"] += 1

    failures = list(provenance.get("failures", []))
    for row in elements:
        if row["build_status"] != "built":
            failures.append({"sheet": row["sheet"], "element": row["element_number"], "tier": "measured", "reason": row["build_failure"] or row["build_status"]})
    lines = [
        "# Flat V3 stage-reference failures and hand-fix queue",
        "",
        "Claims are tagged per the project evidence convention.",
        "",
        "## Failures / exclusions",
        "",
    ]
    if failures:
        for failure in failures:
            lines.append(f"- **{failure.get('tier', 'measured')}:** `{failure.get('sheet')}`" + (f" element {failure['element']}" if failure.get("element") else "") + f" — {failure.get('reason')}.")
    else:
        lines.append("- **measured:** none.")
    lines += ["", "## Busy architecture overlaps needing a hand fix", ""]
    hand = [row for row in elements if row["busy_overlap_hand_fix"]]
    if hand:
        for row in hand:
            residual = row["rectification"].get("residual_skew_degrees_median")
            residual_text = f"{residual} degrees" if residual is not None else "UNCLEAR (no stable Hough-line estimate)"
            lines.append(f"- **measured:** `{row['asset_name']}` — residual skew {residual_text} and/or competing architectural masks overlap.")
    else:
        lines.append("- **measured:** none flagged by the overlap/skew gate.")
    (OUT / "FAILURES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    cards: list[dict[str, str]] = []
    rows_images: list[Image.Image] = []
    for row in elements:
        source = Path(row["source"]["original_path"])
        element_path = Path(row["rgba_path"])
        cards.append(
            {
                "asset": row["asset_name"],
                "sheet": row["sheet"],
                "source": source.as_posix(),
                "element": element_path.relative_to(OUT).as_posix(),
                "status": row["build_status"],
                "skew": str(row["rectification"].get("residual_skew_degrees_median")),
                "hand_fix": str(row["busy_overlap_hand_fix"]),
                "fuser": str(row["fuser_colouring_candidate"]),
            }
        )
        canvas = Image.new("RGB", (960, 390), (30, 32, 35))
        left = image_thumb(source, (430, 330))
        right = image_thumb(element_path, (430, 330))
        canvas.paste(left, ((450 - left.width) // 2, 12 + (330 - left.height) // 2))
        canvas.paste(right, (490 + (450 - right.width) // 2, 12 + (330 - right.height) // 2))
        caption = f"{row['asset_name']} | {row['build_status']} | skew={row['rectification'].get('residual_skew_degrees_median')}° | hand-fix={row['busy_overlap_hand_fix']} | Fuser={row['fuser_colouring_candidate']}"
        ImageDraw.Draw(canvas).text((14, 354), caption[:150], fill=(238, 238, 238), font=FONT)
        rows_images.append(canvas)
    if rows_images:
        combined = Image.new("RGB", (960, 390 * len(rows_images)), (22, 24, 27))
        for index, row_image in enumerate(rows_images):
            combined.paste(row_image, (0, index * 390))
        combined.save(OUT / "CONTACT_SHEET.jpg", quality=90, subsampling=0)
    html_cards = []
    for card in cards:
        html_cards.append(
            "<article><h3>" + html.escape(card["asset"]) + "</h3>"
            + "<div><img src='" + html.escape(Path(card["source"]).as_uri()) + "'><img src='" + html.escape(card["element"]) + "'></div>"
            + "<p>status=" + html.escape(card["status"]) + " · residual skew=" + html.escape(card["skew"]) + "° · hand fix=" + html.escape(card["hand_fix"]) + " · Fuser candidate=" + html.escape(card["fuser"]) + "</p></article>"
        )
    document = """<!doctype html><meta charset='utf-8'><title>Flat V3 StageRefs</title><style>body{background:#181a1e;color:#eee;font:14px system-ui;margin:24px}article{border-top:1px solid #555;padding:18px 0}img{width:46%;height:360px;object-fit:contain;background:#d6c8aa;margin-right:2%}p{color:#ccc}</style><h1>Flat V3 Baroque stage-reference elements</h1><p>Each rectified element is shown beside its complete source sheet. Default medium: ink on aged paper.</p>""" + "".join(html_cards)
    (OUT / "CONTACT_SHEET.html").write_text(document, encoding="utf-8")

    provenance["elements"] = elements
    provenance["counts_per_sheet"] = counts
    provenance["fuser_colouring_candidates"] = sorted(fuser)
    measured_residuals = sorted(
        float(row["rectification"]["residual_skew_degrees_median"])
        for row in elements
        if row["rectification"].get("residual_skew_degrees_median") is not None
    )
    residual_summary = {
        "estimated_elements": len(measured_residuals),
        "unestimated_elements": len(elements) - len(measured_residuals),
        "minimum": round(min(measured_residuals), 4) if measured_residuals else None,
        "mean": round(float(np.mean(measured_residuals)), 4) if measured_residuals else None,
        "median": round(float(np.median(measured_residuals)), 4) if measured_residuals else None,
        "maximum": round(max(measured_residuals), 4) if measured_residuals else None,
        "pass_le_5_degrees": sum(value <= 5.0 for value in measured_residuals),
        "over_5_degrees": sum(value > 5.0 for value in measured_residuals),
    }
    passing_hand = [row for row in passing if row["busy_overlap_hand_fix"]]
    provenance["batch_summary"] = {
        "built": len(passing),
        "failed": len(elements) - len(passing),
        "passing_hand_fix_flags": len(passing_hand),
        "passing_without_hand_fix": len(passing) - len(passing_hand),
        "residual_skew_degrees": residual_summary,
        "batch_status": batch.get("status", "not_run"),
    }
    atomic_json(OUT / "provenance.json", provenance)
    summary = {
        "eligible_sources": provenance["eligible_source_count"],
        "restricted_sources": provenance["restricted_source_count"],
        "selected_elements": len(elements),
        "passing_flats": len(passing),
        "failed_elements": len(elements) - len(passing),
        "hand_fix_flags": len(hand),
        "passing_hand_fix_flags": len(passing_hand),
        "passing_without_hand_fix": len(passing) - len(passing_hand),
        "residual_skew_degrees": residual_summary,
        "fuser_candidates": len(fuser),
        "counts_per_sheet": counts,
    }
    atomic_json(OUT / "SUMMARY.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("census", "propose", "prepare", "compact", "build", "finalize", "all"), default="all")
    args = parser.parse_args()
    if args.phase in {"census", "all"}:
        result = census()
        print(json.dumps({"phase": "census", "eligible": result["eligible_count"], "restricted": result["restricted_count"]}), flush=True)
    if args.phase in {"propose", "all"}:
        result = propose()
        print(json.dumps({"phase": "propose", "status": result["status"]}), flush=True)
    if args.phase in {"prepare", "all"}:
        result = prepare()
        print(json.dumps({"phase": "prepare", "elements": result["element_count"]}), flush=True)
    if args.phase == "compact":
        result = compact_existing_names()
        print(json.dumps({"phase": "compact", **result}), flush=True)
    batch_code = 0
    if args.phase in {"build", "all"}:
        batch_code = run_batch()
        print(json.dumps({"phase": "build", "exit_code": batch_code}), flush=True)
    if args.phase in {"finalize", "all"}:
        result = finalize()
        print(json.dumps({"phase": "finalize", **result}), flush=True)
    return batch_code


if __name__ == "__main__":
    raise SystemExit(main())
