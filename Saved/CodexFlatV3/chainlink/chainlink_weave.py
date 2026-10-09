"""Deterministic procedural chain-link fabric with an optional Blender wrapper.

The geometry core imports only numpy.  Blender is imported lazily by
``build_blender_lods`` so the offline harness can run in ordinary CPython.
Coordinates are metres in (depth X, panel-width Y, height Z).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


HERE = Path(__file__).resolve().parent
OUTPUTS = HERE / "previews"
RECORD = HERE / "chainlink_weave_record.json"
CONFIRM_APPLY = "APPLY P57 CHAINLINK"
CONFIRM_REVERT = "REVERT P57 CHAINLINK"
INDUSTRIAL_MASTER = "/Game/Scenes/Wings/PaintedSurface/Industrial/M_Wing_IndustrialTiling_Master"


@dataclass(frozen=True)
class WeaveConfig:
    width_m: float = 3.36
    height_m: float = 3.02676
    diamond_m: float = 0.25
    wire_diameter_m: float = 0.008
    tube_sides: int = 4
    samples_per_half_diamond: int = 2
    seed: int = 5709
    bend_m: float = 0.008
    lean_m: float = 0.015
    weave_depth_m: float = 0.011
    slack_probability: float = 0.10
    broken_probability: float = 0.15
    triangle_budget: int = 20_000

    def checked(self) -> "WeaveConfig":
        if self.width_m <= self.diamond_m or self.height_m <= self.diamond_m:
            raise ValueError("panel must span more than one diamond")
        if not 0.04 <= self.diamond_m <= 0.40:
            raise ValueError("diamond_m must be in 0.04..0.40 m")
        if not 0.002 <= self.wire_diameter_m <= 0.025:
            raise ValueError("wire_diameter_m must be in 0.002..0.025 m")
        if not 4 <= self.tube_sides <= 8:
            raise ValueError("tube_sides must be in 4..8")
        if not 1 <= self.samples_per_half_diamond <= 4:
            raise ValueError("samples_per_half_diamond must be in 1..4")
        if self.triangle_budget <= 0:
            raise ValueError("triangle_budget must be positive")
        return self


@dataclass
class Picket:
    index: int
    polylines: list[np.ndarray]
    slack: bool
    broken: bool


@dataclass
class Weave:
    config: WeaveConfig
    pickets: list[Picket]
    knuckles: list[dict]
    draws: int
    triangles: int


class ScalarRng:
    """Records that each authored random value consumes exactly one draw."""

    def __init__(self, seed: int):
        self.rng = np.random.default_rng(seed)
        self.draws = 0

    def uniform(self, low: float = 0.0, high: float = 1.0) -> float:
        self.draws += 1
        return float(self.rng.uniform(low, high))


def _subdivide(points: np.ndarray, samples: int) -> np.ndarray:
    out = []
    for a, b in zip(points[:-1], points[1:]):
        for j in range(samples):
            out.append(a + (b - a) * (j / samples))
    out.append(points[-1])
    return np.asarray(out, dtype=np.float64)


def _split_broken(points: np.ndarray, broken: bool, picket_index: int) -> list[np.ndarray]:
    if not broken or len(points) < 10:
        return [points]
    # Remove one deterministic segment near mid-height and curl both free ends.
    cut = len(points) // 2 + ((picket_index % 3) - 1)
    left, right = points[:cut].copy(), points[cut + 1 :].copy()
    left[-1, 0] += 0.025
    left[-1, 1] -= 0.018
    right[0, 0] -= 0.022
    right[0, 1] += 0.015
    return [part for part in (left, right) if len(part) >= 2]


def tube_triangles(polylines: Iterable[np.ndarray], sides: int) -> int:
    total = 0
    for points in polylines:
        segments = max(0, len(points) - 1)
        total += segments * sides * 2
        if segments:
            total += 2 * (sides - 2)
    return total


def build_weave(config: WeaveConfig = WeaveConfig()) -> Weave:
    cfg = config.checked()
    rng = ScalarRng(cfg.seed)
    half = cfg.diamond_m * 0.5
    z0, z1 = 0.04, cfg.height_m - 0.04
    rows = max(4, int(round((z1 - z0) / half)))
    z_nodes = np.linspace(z0, z1, rows + 1)
    picket_count = max(4, int(math.floor(cfg.width_m / cfg.diamond_m)))
    side_margin = (cfg.width_m - (picket_count - 1) * cfg.diamond_m) * 0.5
    centres = side_margin + np.arange(picket_count, dtype=np.float64) * cfg.diamond_m

    # Shared node offsets keep projected knuckles joined while preserving
    # deterministic, locally imperfect diamonds.
    shared: dict[tuple[int, int], tuple[float, float]] = {}
    raw_nodes: list[np.ndarray] = []
    selectors: list[tuple[float, float, float, float]] = []
    for i, centre in enumerate(centres):
        selectors.append((
            rng.uniform(-cfg.lean_m, cfg.lean_m),
            rng.uniform(-cfg.bend_m, cfg.bend_m),
            rng.uniform(),
            rng.uniform(),
        ))
        nodes = []
        for k, z in enumerate(z_nodes):
            direction = 1.0 if (i + k) % 2 == 0 else -1.0
            y = centre + direction * half
            node_key = (int(round(y / half)), k)
            if node_key not in shared:
                shared[node_key] = (
                    rng.uniform(-cfg.bend_m, cfg.bend_m),
                    rng.uniform(-cfg.bend_m * 0.55, cfg.bend_m * 0.55),
                )
            jy, jz = shared[node_key]
            x = cfg.weave_depth_m if (i + k // 2) % 2 == 0 else -cfg.weave_depth_m
            nodes.append((x, y + jy, z + jz))
        raw_nodes.append(np.asarray(nodes, dtype=np.float64))

    pickets: list[Picket] = []
    for i, raw in enumerate(raw_nodes):
        nodes = raw.copy()
        lean, bow, slack_score, broken_score = selectors[i]
        t = np.linspace(0.0, 1.0, len(nodes))
        nodes[:, 1] += lean * (t - 0.5) + bow * np.sin(math.pi * t)
        slack = slack_score < cfg.slack_probability
        broken = broken_score < cfg.broken_probability
        if slack:
            nodes[:, 1] += cfg.diamond_m * 0.055 * np.sin(math.pi * t)
            nodes[:, 2] -= cfg.diamond_m * 0.085 * np.sin(math.pi * t) ** 2
        # Knuckled selvage: ends curl back into the panel rather than ending as
        # clean cut verticals. Interior lattice nodes stay untouched.
        bottom = nodes[0].copy()
        bottom[0], bottom[1], bottom[2] = 0.0, bottom[1] + (-1 if i % 2 else 1) * 0.035, 0.0
        top = nodes[-1].copy()
        top[0], top[1], top[2] = 0.0, top[1] + (1 if i % 2 else -1) * 0.035, cfg.height_m
        sampled = _subdivide(np.vstack((bottom, nodes, top)), cfg.samples_per_half_diamond)
        pickets.append(Picket(i, _split_broken(sampled, broken, i), slack, broken))

    knuckles = []
    for i in range(picket_count - 1):
        a, b = raw_nodes[i], raw_nodes[i + 1]
        for ka, pa in enumerate(a):
            distances = np.linalg.norm(b[:, 1:3] - pa[1:3], axis=1)
            kb = int(np.argmin(distances))
            if distances[kb] <= 1e-9:
                knuckles.append({
                    "pickets": [i, i + 1],
                    "row": ka,
                    "projected_yz": [float(pa[1]), float(pa[2])],
                    "depth_separation_m": float(abs(pa[0] - b[kb, 0])),
                })

    triangles = tube_triangles(
        (line for picket in pickets for line in picket.polylines), cfg.tube_sides
    )
    if triangles > cfg.triangle_budget:
        raise ValueError(f"TRI_BUDGET_REFUSED|triangles={triangles}|budget={cfg.triangle_budget}")
    return Weave(cfg, pickets, knuckles, rng.draws, triangles)


def build_lods(config: WeaveConfig = WeaveConfig()) -> dict[str, object]:
    lod0 = build_weave(config)
    lod1_cfg = replace(
        config,
        diamond_m=min(0.40, config.diamond_m * 1.6),
        tube_sides=4,
        samples_per_half_diamond=1,
        bend_m=config.bend_m * 0.6,
        broken_probability=0.0,
        slack_probability=config.slack_probability * 0.5,
    )
    lod1 = build_weave(lod1_cfg)
    return {
        "lod0": lod0,
        "lod1": lod1,
        "lod2": {"construction": "masked_card", "triangles": 2, "cast_shadow": False},
    }


def validate_interlocks(weave: Weave) -> dict[str, object]:
    minimum = weave.config.wire_diameter_m * 1.8
    bad_depth = [k for k in weave.knuckles if k["depth_separation_m"] < minimum]
    projected = {}
    non_knuckle_duplicates = []
    for picket in weave.pickets:
        for line in picket.polylines:
            for p in line:
                key = (round(float(p[1]), 7), round(float(p[2]), 7))
                prior = projected.get(key)
                if prior is not None and prior[0] != picket.index:
                    depth = abs(float(p[0]) - prior[1])
                    if depth < minimum:
                        non_knuckle_duplicates.append((prior[0], picket.index, key, depth))
                else:
                    projected[key] = (picket.index, float(p[0]))
    return {
        "ok": bool(weave.knuckles) and not bad_depth and not non_knuckle_duplicates,
        "knuckle_count": len(weave.knuckles),
        "minimum_required_depth_m": minimum,
        "minimum_measured_depth_m": min((k["depth_separation_m"] for k in weave.knuckles), default=0.0),
        "bad_knuckles": len(bad_depth),
        "non_knuckle_intersections": len(non_knuckle_duplicates),
    }


def deterministic_digest(weave: Weave) -> str:
    digest = hashlib.sha256()
    digest.update(json.dumps(asdict(weave.config), sort_keys=True).encode())
    for picket in weave.pickets:
        for line in picket.polylines:
            digest.update(np.asarray(line, dtype="<f8").tobytes())
    return digest.hexdigest()


def dispatch_p02_chainlink(
    params: dict,
    legacy_builder: Callable[[dict], object],
    weave_builder: Callable[[dict], object],
) -> object:
    """P02 integration seam; absence/off calls the legacy builder verbatim."""
    option = params.get("chainlink", "legacy")
    if option in (None, "off", "legacy"):
        return legacy_builder(params)
    if option == "weave":
        return weave_builder(params)
    raise ValueError(f"unsupported chainlink option: {option!r}")


def _map_point(point: np.ndarray, width: int, height: int, margin: int) -> tuple[int, int]:
    y = margin + point[1] / 3.36 * (width - 2 * margin)
    z = height - margin - point[2] / 3.02676 * (height - 2 * margin)
    return int(round(y)), int(round(z))


def render_raking_shadow(weave: Weave, path: Path, size=(1400, 1000)) -> None:
    scale = 2
    image = Image.new("RGB", (size[0] * scale, size[1] * scale), (224, 218, 199))
    draw = ImageDraw.Draw(image)
    margin = 70 * scale
    # Raking shadow: depth and height both displace the projection. This keeps
    # the alternating over/under crimp visible in the cast silhouette.
    for picket in weave.pickets:
        for line in picket.polylines:
            shadow = line.copy()
            shadow[:, 1] += 0.12 * shadow[:, 2] + 5.5 * shadow[:, 0]
            shadow[:, 2] *= 0.82
            points = [_map_point(p, size[0] * scale, size[1] * scale, margin) for p in shadow]
            draw.line(points, fill=(55, 48, 40), width=5 * scale, joint="curve")
    image = image.filter(ImageFilter.GaussianBlur(radius=0.7 * scale))
    image.resize(size, Image.Resampling.LANCZOS).save(path)


def render_topdown(weave: Weave, path: Path, size=(1400, 650)) -> None:
    scale = 2
    image = Image.new("RGB", (size[0] * scale, size[1] * scale), (25, 29, 31))
    draw = ImageDraw.Draw(image)
    margin = 70 * scale
    z_mid = weave.config.height_m * 0.52
    z_band = weave.config.diamond_m * 0.72
    for picket in weave.pickets:
        for line in picket.polylines:
            keep = line[np.abs(line[:, 2] - z_mid) <= z_band]
            if len(keep) < 2:
                continue
            points = []
            for p in keep:
                px = margin + p[1] / weave.config.width_m * (size[0] * scale - 2 * margin)
                py = size[1] * scale * 0.5 - p[0] / 0.06 * (size[1] * scale * 0.34)
                points.append((int(px), int(py)))
            draw.line(points, fill=(190, 201, 197), width=7 * scale, joint="curve")
    draw.line((margin, size[1] * scale * 0.5, size[0] * scale - margin, size[1] * scale * 0.5), fill=(82, 90, 91), width=1 * scale)
    image.resize(size, Image.Resampling.LANCZOS).save(path)


def _ensure_outputs(mode: str, confirm: str, run_id: str) -> dict:
    lods = build_lods()
    lod0: Weave = lods["lod0"]
    validation = validate_interlocks(lod0)
    planned = [OUTPUTS / "chainlink_topdown.png", OUTPUTS / "chainlink_raking_shadow.png"]
    record = {
        "run_id": run_id,
        "mode": mode,
        "material_coordinate": INDUSTRIAL_MASTER,
        "config": asdict(lod0.config),
        "triangles": {"lod0": lod0.triangles, "lod1": lods["lod1"].triangles, "lod2": 2},
        "pickets": len(lod0.pickets),
        "slack": sum(p.slack for p in lod0.pickets),
        "broken": sum(p.broken for p in lod0.pickets),
        "random_scalar_draws": lod0.draws,
        "digest": deterministic_digest(lod0),
        "interlocks": validation,
        "dirty_packages": [],
        "named_saves": [str(p.relative_to(HERE)) for p in planned] + [RECORD.name],
    }
    if mode == "DRY":
        return record
    if mode == "APPLY":
        if confirm != CONFIRM_APPLY:
            raise ValueError(f"confirmation must be {CONFIRM_APPLY!r}")
        backup = HERE / "Backups" / f"PreProceduralChainlink-{run_id}"
        backup.mkdir(parents=True, exist_ok=False)
        for target in planned + [RECORD]:
            if target.exists():
                shutil.copy2(target, backup / target.name)
        OUTPUTS.mkdir(parents=True, exist_ok=True)
        render_topdown(lod0, planned[0])
        render_raking_shadow(lod0, planned[1])
        record["backup"] = str(backup.relative_to(HERE))
        record["readback"] = {p.name: {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in planned}
        RECORD.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        return record
    if mode == "REVERT":
        if confirm != CONFIRM_REVERT:
            raise ValueError(f"confirmation must be {CONFIRM_REVERT!r}")
        backup = HERE / "Backups" / f"PreProceduralChainlink-{run_id}"
        if not backup.is_dir():
            raise ValueError(f"backup not found: {backup}")
        for target in planned + [RECORD]:
            saved = backup / target.name
            if saved.exists():
                shutil.copy2(saved, target)
            elif target.exists():
                # Preserve newly generated files rather than permanently deleting.
                reverted = backup / (target.name + ".generated")
                shutil.move(str(target), str(reverted))
        record["reverted_from"] = str(backup.relative_to(HERE))
        return record
    raise ValueError(mode)


def build_blender_lods(config: WeaveConfig = WeaveConfig(), collection=None):
    """Thin post-bake Blender adapter; not executed or tested in this brief.

    Curves use poly splines with zero bevel subdivisions. The caller supplies
    the already-created galvanised material (an MI using INDUSTRIAL_MASTER after
    FBX import) and performs its existing Flat V3 slot/UV/export validation.
    """
    import bpy  # type: ignore

    lods = build_lods(config)
    collection = collection or bpy.context.collection
    created = {}
    for lod_name in ("lod0", "lod1"):
        weave: Weave = lods[lod_name]
        objects = []
        for picket in weave.pickets:
            for part_i, points in enumerate(picket.polylines):
                curve = bpy.data.curves.new(f"P57_{lod_name}_P{picket.index:02d}_{part_i}_Curve", "CURVE")
                curve.dimensions = "3D"
                curve.resolution_u = 1
                curve.resolution_v = 0
                curve.bevel_depth = weave.config.wire_diameter_m * 0.5
                curve.bevel_resolution = 0
                curve.bevel_resolution = 0
                curve.resolution_v = 0
                spline = curve.splines.new("POLY")
                spline.points.add(len(points) - 1)
                for point, co in zip(spline.points, points):
                    point.co = (float(co[0]), float(co[1]), float(co[2]), 1.0)
                obj = bpy.data.objects.new(curve.name.removesuffix("_Curve"), curve)
                obj["part_category"] = "chain_zigzag_wire"
                obj["p57_seed"] = weave.config.seed
                collection.objects.link(obj)
                objects.append(obj)
        created[lod_name] = objects
    created["lod2_spec"] = lods["lod2"]
    return created


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("DRY", "APPLY", "REVERT"), required=True)
    parser.add_argument("--confirm", default="")
    parser.add_argument("--run-id", default="P57-20261009-01")
    args = parser.parse_args()
    record = _ensure_outputs(args.mode, args.confirm, args.run_id)
    print(json.dumps(record, indent=2))
    if args.mode == "APPLY":
        print(f"P57_CHAINLINK_SUCCESS|run={args.run_id}|lod0={record['triangles']['lod0']}|interlocks={record['interlocks']['knuckle_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
