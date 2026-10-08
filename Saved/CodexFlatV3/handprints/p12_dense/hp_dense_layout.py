"""Build the deterministic P12 B06-only desperate handprint placement table (offline)."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLAMBER = HERE.parent / "clamber"
sys.path.insert(0, str(HERE))
import hp_dense_core as core  # noqa: E402
PROJECT = HERE.parents[3]
CONFIG = HERE / "hp_dense_config.json"
SOURCE = CLAMBER / "placement_S03_grease.json"
OUT_DEFAULT = HERE / "placement_S03_dense.json"


class BuildError(RuntimeError):
    pass


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def draw_span(rng, span):
    u = rng.random()
    return span[0] + (span[1] - span[0]) * u


def draw_int(rng, span):
    u = rng.random()
    return int(span[0] + math.floor(u * (span[1] - span[0] + 1)))


def choose(rng, rows):
    u = rng.random()
    return rows[min(len(rows) - 1, int(u * len(rows)))]


def selected_pool(source, cfg):
    # The original generator's auxiliary atlas/exclusion files are not present in this worktree.  Use its measured,
    # already-validated rows as geometry/material templates; this keeps the generated tool self-contained.
    by_mi = {}
    for row in source["decals"]:
        by_mi.setdefault(row["material_instance"], row)
    prints = sorted((r for r in by_mi.values() if r["kind"] == "print"), key=lambda r: r["material_instance"])
    smears = sorted((r for r in by_mi.values() if r["kind"] == "smear"), key=lambda r: r["material_instance"])
    return prints[:cfg["pool"]["print_entries"]], smears[:cfg["pool"]["smear_entries"]]


def norm_angle(value):
    return ((value + 180.0) % 360.0) - 180.0


def nearest_floor(source_rows, along):
    return min(source_rows, key=lambda r: abs(r["along_cm"] - along))["dune_floor_cm"]


def make_row(template, along, height, roll, sx, sy, event, kind, floor):
    width = template["size_cm"][0] * sx
    tall = template["size_cm"][1] * sy
    theta = math.radians(roll)
    half_a = (abs(math.cos(theta)) * width + abs(math.sin(theta)) * tall) * 0.5
    half_h = (abs(math.sin(theta)) * width + abs(math.cos(theta)) * tall) * 0.5
    actor_roll = norm_angle(90.0 - roll)
    ar = math.radians(actor_roll)
    row = {k: json.loads(json.dumps(v)) for k, v in template.items()
           if k not in ("id", "label", "core_label", "event", "event_kind", "location", "rotation", "axes",
                        "size_cm", "decal_size", "along_cm", "height_cm", "low_extent_cm", "high_extent_cm",
                        "along_extent_cm", "dune_floor_cm", "ceiling_cm", "outlier")}
    row.update({
        "wall": "R", "attach_actor_label": "S3 Hangar Right Wall", "event": event, "event_kind": kind,
        "along_cm": round(along, 3), "height_cm": round(height, 3),
        "along_extent_cm": [round(along - half_a, 3), round(along + half_a, 3)],
        "low_extent_cm": round(height - half_h, 3), "high_extent_cm": round(height + half_h, 3),
        "dune_floor_cm": round(floor, 3), "ceiling_cm": 850.0, "outlier": False,
        "size_cm": [round(width, 3), round(tall, 3)],
        "decal_size": [8.0, round(tall * 0.5, 3), round(width * 0.5, 3)],
        "roll_on_wall_deg": round(norm_angle(roll), 4),
        "rotation": {"pitch": 0.0, "roll": round(actor_roll, 5), "yaw": 90.0},
        "location": [round(11421.973 + along, 3), 160999.0, round(-5.0 + height, 3)],
        "axes": {"x": [0.0, 1.0, 0.0],
                 "y": [round(-math.cos(ar), 6), 0.0, round(-math.sin(ar), 6)],
                 "z": [round(-math.sin(ar), 6), 0.0, round(math.cos(ar), 6)]},
        "fade_screen_size": 0.0, "sort_order": 0 if template["kind"] == "smear" else 1,
    })
    return row


def build(cfg, seed=None, density=None, band=None, dark_preset=None):
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    seed = cfg["seed"] if seed is None else seed
    density = cfg["density"] if density is None else density
    if density <= 0:
        raise BuildError("DENSITY_MUST_BE_POSITIVE")
    use_band = json.loads(json.dumps(cfg["band"]))
    if band is not None:
        use_band["along_cm"] = [float(band[0]), float(band[1])]
    alo, ahi = use_band["along_cm"]
    zlo, zhi = use_band["height_cm"]
    if not (0 <= alo < ahi <= 6000 and 0 <= zlo < zhi <= 880.0):
        raise BuildError("BAD_BAND")
    preset_name = cfg["dark_preset"] if dark_preset is None else dark_preset
    if preset_name not in cfg["dark_presets"]:
        raise BuildError("UNKNOWN_DARK_PRESET|" + preset_name)
    dark = json.loads(json.dumps(cfg["dark_presets"][preset_name]))
    old = [r for r in source["decals"] if r["wall"] == cfg["wall"] and alo <= r["along_cm"] <= ahi]
    target = round(len(old) * density)
    if target < 1:
        raise BuildError("EMPTY_SOURCE_BAND")

    rng = random.Random(seed)
    prints, smears = selected_pool(source, cfg)
    kept = []
    rejected = {"band": 0, "floor": 0}

    def add(entry, along, height, roll, sx, sy, event, kind):
        if len(kept) >= target:
            return False
        floor = nearest_floor(old, along)
        row = make_row(entry, along, height, roll, sx, sy, event, kind, floor)
        a0, a1 = row["along_extent_cm"]
        lo, hi = row["low_extent_cm"], row["high_extent_cm"]
        if a0 < alo or a1 > ahi or lo < zlo or hi > zhi:
            rejected["band"] += 1
            return False
        if lo < floor + 24.0:
            rejected["floor"] += 1
            return False
        row["along_extent_cm"] = [round(a0, 3), round(a1, 3)]
        row["dark_preset"] = preset_name
        suffix = row["material_instance"][len(cfg["material"]["sheen_prefix"]):]
        row["dark_material_instance"] = cfg["material"]["dark_prefix"] + suffix
        kept.append(row)
        return True

    event_index = 0
    attempts = 0
    while len(kept) < target and attempts < target * 80:
        attempts += 1
        event_index += 1
        event = "B06-T%03d" % event_index
        half_margin = 70.0
        start_a = draw_span(rng, (alo + half_margin, ahi - half_margin))
        floor = nearest_floor(old, start_a) + 24.0
        start_h = floor + draw_span(rng, (35.0, 105.0))

        # Dense, overlapping base cluster: bodies below, hands searching for purchase above.
        cluster_n = draw_int(rng, cfg["cluster"]["marks"])
        cluster_r = draw_span(rng, cfg["cluster"]["radius_cm"])
        for ci in range(cluster_n):
            da = draw_span(rng, (-cluster_r, cluster_r))
            dh = draw_span(rng, (-0.45 * cluster_r, 0.8 * cluster_r))
            u = rng.random()
            entry = choose(rng, smears if u < cfg["cluster"]["smear_probability"] else prints)
            scale = draw_span(rng, cfg["trail"]["print_scale"])
            roll = draw_span(rng, (-180.0, 180.0))
            add(entry, start_a + da, start_h + dh, roll, scale, scale, event, "cluster")

        steps = draw_int(rng, cfg["trail"]["steps"])
        along = start_a
        height = start_h
        for step in range(steps):
            rise = draw_span(rng, cfg["trail"]["rise_cm"])
            height += rise
            drift = draw_span(rng, cfg["trail"]["drift_cm"])
            along += drift
            pair_span = draw_span(rng, cfg["trail"]["pair_half_span_cm"])
            for hand in (-1, 1):
                hand_a = along + hand * pair_span
                hand_h = height + (7.0 if hand == 1 and step % 2 else -4.0)
                entry = choose(rng, prints)
                scale = draw_span(rng, cfg["trail"]["print_scale"])
                roll = draw_span(rng, cfg["trail"]["print_roll_deg"])
                add(entry, hand_a, hand_h, roll, scale, scale, event, "reach_pair")
                scratches = draw_int(rng, cfg["trail"]["scratch_per_hand"])
                for scratch in range(scratches):
                    scratch_entry = choose(rng, smears)
                    drop = draw_span(rng, cfg["trail"]["scratch_drop_cm"])
                    jitter = draw_span(rng, (-7.0, 7.0))
                    width = draw_span(rng, cfg["trail"]["scratch_width_scale"])
                    length = draw_span(rng, cfg["trail"]["scratch_length_scale"])
                    scratch_roll = draw_span(rng, cfg["trail"]["scratch_roll_deg"])
                    add(scratch_entry, hand_a + jitter, hand_h - drop, scratch_roll, width, length,
                        event, "finger_scratch")
            u = rng.random()
            if u < cfg["drag"]["probability_per_step"]:
                drag_entry = choose(rng, smears)
                drop = draw_span(rng, cfg["drag"]["drop_cm"])
                width = draw_span(rng, cfg["drag"]["width_scale"])
                length = draw_span(rng, cfg["drag"]["length_scale"])
                roll = draw_span(rng, cfg["trail"]["scratch_roll_deg"])
                add(drag_entry, along, height - drop, roll, width, length, event, "drag_smear")
    if len(kept) != target:
        raise BuildError("TARGET_NOT_REACHED|%d|%d|attempts=%d" % (len(kept), target, attempts))

    rows = sorted(kept, key=lambda r: (r["along_cm"], r["height_cm"], r["event"], r["event_kind"]))
    for i, row in enumerate(rows, 1):
        row["id"] = "HP_S03D_R_%04d" % i
        row["label"] = "HP_S03D R %04d" % i
        row["core_label"] = "HP_S03D_CORE R %04d" % i
    used = sorted({r["material_instance"] for r in rows})
    pool_by_name = {p["material_instance"]: p for p in prints + smears}
    worklist = []
    for sheen_name in used:
        suffix = sheen_name[len(cfg["material"]["sheen_prefix"]):]
        p = pool_by_name[sheen_name]
        worklist.append({"sheen": sheen_name,
                         "source_tint": cfg["material"]["source_tint_prefix"] + suffix,
                         "dark": cfg["material"]["dark_prefix"] + suffix,
                         "kind": p["kind"], "element": p["element_id"], "crop": p["crop_name"], "flip": p["flip"]})
    kinds = {k: sum(r["event_kind"] == k for r in rows) for k in sorted({r["event_kind"] for r in rows})}
    doc = {
        "schema": core.SCHEMA, "variant": "p12_b06_dense_desperate", "placeholder": source["placeholder"],
        "level": core.LEVEL, "seed": seed, "density": density, "band": use_band,
        "source_table": str(SOURCE.relative_to(PROJECT)).replace("\\", "/"), "source_sha256": sha(SOURCE),
        "source_band_count": len(old), "target_count": target,
        "camera_evidence": {"sequence": "LS_DevScene_03", "shot": "S3 Shot B06", "frames": [3000, 3480],
                            "world_x_cm": [14072.5889, 14866.1523], "world_y_cm": [160976.0312, 160994.0312],
                            "world_z_cm": [188.8662, 220.1756], "tier": "binary-proven offline dump"},
        "walls_file": source["walls_file"], "walls_sha256": source["walls_sha256"],
        "landed_box_world_cm": source["landed_box_world_cm"], "exclusions": source["exclusions"],
        "exclusion_limit": "source table metadata retained; obstacle boxes unavailable in this worktree, so new overlap is inferred until editor DRY/read-back",
        "dune": source["dune"],
        "config_file": CONFIG.name, "config_sha256": sha(CONFIG), "config": cfg,
        "material": dict(cfg["material"], dark_preset=preset_name, dark_parameters=dark),
        "dark_mi_worklist": worklist, "mi_used": used,
        "stats": {"count": len(rows), "events": event_index, "by_kind": kinds,
                  "distinct_sheen_mis": len(used), "rejected": rejected, "attempts": attempts},
        "tool": "Saved/CodexFlatV3/handprints/p12_dense/hp_dense_layout.py", "decals": rows,
    }
    core.validate_table(doc)
    return doc


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--density", type=float)
    ap.add_argument("--band", nargs=2, type=float, metavar=("ALONG_MIN", "ALONG_MAX"))
    ap.add_argument("--dark-preset")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args(argv)
    if args.out.exists() and not args.overwrite:
        print("P12_DENSE_FAIL|OUTPUT_EXISTS|%s" % args.out, file=sys.stderr)
        return 2
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    try:
        doc = build(cfg, args.seed, args.density, args.band, args.dark_preset)
    except Exception as exc:
        print("P12_DENSE_FAIL|%s" % exc, file=sys.stderr)
        return 2
    data = (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode("utf-8")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(data)
    print("P12_DENSE_OK|count=%d|source=%d|density=%.3f|band=%.1f..%.1f|sha256=%s" %
          (len(doc["decals"]), doc["source_band_count"], doc["density"], doc["band"]["along_cm"][0],
           doc["band"]["along_cm"][1], hashlib.sha256(data).hexdigest()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
