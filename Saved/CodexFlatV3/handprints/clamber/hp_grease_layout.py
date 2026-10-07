"""S3 hand-print GREASE SHEEN layer (Gary 7 Oct, 2nd pass).  OFFLINE; the output is DATA.

Gary on the first clamber composite: "these clamber patterns are much too regular, think of the smear, we're talking
reflective smear from earlier, the sheen not the stain".

So this table is NOT stain decals.  Every row is a grease decal for the marble-grime stream's roughness-led master
(bench graph M_ZZ_S3MG_GreaseDecal, s3mg_bench.py:413-465: Opacity = GreaseAtlas.R x GreaseGain, Roughness =
GreaseRoughMin + GreaseRoughRange x GreaseAtlas.G, Normal = print normal x NormalStrength, NO BaseColor).  The prints
read only where they break the marble's reflection.

What changes against hp_clamber_layout.py (same floor rule, same envelope, same frame, same exclusions):
  VOCABULARY  partial palms / fingers / tips / heels / half-hands = fixed sub-rects of the print elements; smears whole,
              head or tail.  Each (element, crop, flip, gain) is one material instance from a CAPPED POOL (config
              pool: 104 print + 40 smear entries, built by seeded draws, crops with no grease are redrawn).  Opacity
              varies through 3 GreaseGain levels baked in the pool (per-decal opacity would need one MI per decal).
  EVENTS      drag (dominant): 1-4 long smears, length x1.1-2.6 and width x0.8-1.35 (anisotropic), vertical +-12
              or diagonal 25-60 deg either way, up or down, overlapping, spread 6-40 cm;
              cloud: 5-16 partials scattered in a gaussian blob (r 18-70 cm), any rotation biased upright;
              wipe: 4-9 smear/heel pieces along a circular arc (r 40-130, span 50-150 deg), long axis on the tangent;
              stray: single random partial or smear, sparse; 12 % of strays are high outliers above the envelope
              (760-880 cm ceiling);
              scrabble ZONES (scheduled first): over every per-metre dune peak >= 0.6 x the wall max, 1-2 amorphous
              zones = union of 3-6 gaussian blobs, 22-55 overlapping partials/short smears rising 60-260 cm
              from the dune line.
  NO LADDERS  no event places a same-element sequence at a fixed step; positions are blob / arc / random draws.
  FLOOR       a decal whose lowest rotated extent would be < dune + 20 is REJECTED (not clamped: clamping would
              pile decals into a line); likewise above its ceiling.
RANDOMNESS: one rng.random() per statement; same seed + same inputs = same bytes.

  python hp_grease_layout.py [--out PATH] [--seed N] [--overwrite]
Marker: HP_GREASE_OK|L=<n>|R=<n>|pool=<n>|sha256=<sha> or HP_GREASE_FAIL|<reason>.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hp_clamber_layout as base  # noqa: E402  (Profile, extents, rel_height, span/int draws, inputs)

hp = base.hp
scr = base.scr
PROJECT = base.PROJECT
CONFIG = HERE / "hp_grease_config.json"
GREASE_ATLAS = PROJECT / "DerivedAssets/S3Marble/Grime_20261007/T_S3MG_GreaseAtlas.png"
OUT_DEFAULT = HERE / "placement_S03_grease.json"
SCHEMA = "hp_grease_placement/1"          # deliberately NOT hp_placement/1: the v3 stain placer refuses it
EPS = 0.01

span_draw, int_draw, rel_height, extents = base.span_draw, base.int_draw, base.rel_height, base.extents


class GreaseError(RuntimeError):
    pass


def pick_weighted(u, weights: dict):
    acc = 0.0
    total = sum(weights.values())
    for k in sorted(weights):
        acc += weights[k] / total
        if u < acc:
            return k
    return sorted(weights)[-1]


def crop_coverage(gmask, uv_rect, crop):
    u0, v0, us, vs = uv_rect
    cu0, cv0, cus, cvs = crop
    H, W = gmask.shape
    x0, x1 = int((u0 + cu0 * us) * W), int((u0 + (cu0 + cus) * us) * W)
    y0, y1 = int((v0 + cv0 * vs) * H), int((v0 + (cv0 + cvs) * vs) * H)
    region = gmask[y0:max(y1, y0 + 1), x0:max(x1, x0 + 1)]
    return float(region.mean()) if region.size else 0.0


def build_pool(rng, cfg, elements, gmask):
    pc = cfg["pool"]
    prints = sorted(e["id"] for e in elements.values() if e["kind"] == "print" and not e["child"])
    smears = sorted(e["id"] for e in elements.values() if e["kind"] == "smear")
    pool, seen = [], set()
    for kind, n, ids, crops, weights in (("print", pc["print_entries"], prints, pc["print_crops"], pc["print_crop_weights"]),
                                         ("smear", pc["smear_entries"], smears, pc["smear_crops"], pc["smear_crop_weights"])):
        made = tries = 0
        while made < n:
            tries += 1
            if tries > 50 * n:
                raise GreaseError("POOL_CANNOT_FILL|%s|%d/%d" % (kind, made, n))
            u = rng.random()
            eid = ids[hp.index_of(u, len(ids))]
            u = rng.random()
            cname = pick_weighted(u, weights)
            u = rng.random()
            flip = u < 0.5
            u = rng.random()
            gain = pc["gains"][hp.index_of(u, len(pc["gains"]))]
            key = (eid, cname, flip, gain)
            if key in seen:
                continue
            cov = crop_coverage(gmask, elements[eid]["uv_rect"], crops[cname])
            if cov < pc["min_crop_coverage"]:
                continue
            seen.add(key)
            g = int(round(gain * 100))
            pool.append({"kind": kind, "element": eid, "crop_name": cname, "crop": crops[cname], "flip": flip,
                         "gain": gain, "coverage": round(cov, 4),
                         "mi": "%s%s_%s_F%d_G%03d" % (cfg["material"]["mi_prefix"], eid, cname, 1 if flip else 0, g)})
            made += 1
    return pool


class Wall:
    def __init__(self, wall, boxes, prof, cfg, elements, drips):
        self.wall, self.boxes, self.prof, self.cfg, self.elements, self.drips = wall, boxes, prof, cfg, elements, drips
        m0, m1 = wall.get("along_margin_cm", [0.0, 0.0])
        self.a_lo, self.a_hi = m0, wall["length_cm"] - m1
        r0 = hp.decal_axes(wall["inward_normal"], 0.0)[2]
        self.s = 1.0 if hp.v_dot(r0, wall["along"]) > 0 else -1.0          # along = s * viewer-right
        self.kept = []
        self.rej = {"floor": 0, "ceiling": 0, "margin": 0, "practical": 0, "wave": 0, "backdrop": 0, "deck": 0}
        self.attempts = 0

    def line(self, a):
        """Dune line at a (clamped onto the wall; off-wall positions are rejected by add)."""
        return self.prof.line(hp.clamp(a, 0.0, self.wall["length_cm"] - 1.0))

    def add(self, entry, along, height, roll, sx, sy, event, kind, ceiling=None):
        """entry from the pool; sx/sy scale the CROPPED element width/height.  Reject (never clamp)."""
        self.attempts += 1
        e = self.elements[entry["element"]]
        cu0, cv0, cus, cvs = entry["crop"]
        w, h = e["width_cm"] * cus * sx, e["height_cm"] * cvs * sy
        if not (self.a_lo + w / 2.0 <= along <= self.a_hi - w / 2.0):
            self.rej["margin"] += 1
            return False
        pseudo = {"id": entry["element"], "grid_rect": e["grid_rect"], "width_cm": w, "height_cm": h}
        item = {"kind": entry["kind"], "child": False, "element": pseudo, "roll": scr.norm_roll(roll),
                "flip": entry["flip"], "w": w, "h": h, "along": along, "height": height, "cluster": None}
        row = hp.to_decal(self.wall, item)
        lo, hi, a0, a1 = extents(row)
        if lo < self.prof.dune_over(a0, a1) + self.prof.clear + self.cfg["face_strip_allowance_cm"]:
            self.rej["floor"] += 1
            return False
        top = ceiling if ceiling is not None else self.prof.top(row["along_cm"])
        if hi > min(top, self.cfg["global_ceiling_cm"]):
            self.rej["ceiling"] += 1
            return False
        hit = hp.excluded_by(row, self.boxes)
        if hit:
            self.rej[hit] += 1
            return False
        u0, v0, us, vs = e["uv_rect"]
        row.pop("decal_color", None)
        row.update({"event": event, "event_kind": kind, "outlier": ceiling is not None, "fade_screen_size": 0.0,
                    "crop_name": entry["crop_name"], "crop": entry["crop"], "gain": entry["gain"],
                    "material_instance": entry["mi"],
                    "grease_uv_rect": [round(u0 + cu0 * us, 8), round(v0 + cv0 * vs, 8), round(cus * us, 8),
                                       round(cvs * vs, 8)],
                    "dune_floor_cm": round(self.prof.dune_over(a0, a1), 3), "low_extent_cm": round(lo, 3),
                    "high_extent_cm": round(hi, 3), "ceiling_cm": round(min(top, self.cfg["global_ceiling_cm"]), 3),
                    "sort_order": 0 if entry["kind"] == "smear" else 1})
        self.kept.append(row)
        return True


def print_roll(rng, cfg):
    pr = cfg["print_roll"]
    u = rng.random()
    upright = u < pr["p_up"]
    u = rng.random()
    return span_draw(u, (-pr["up_deg"], pr["up_deg"])) if upright else span_draw(u, (-180.0, 180.0))


def generate_wall(rng, w: Wall, cfg, prints, smears, per_wall=None):
    prof = w.prof
    if per_wall:
        target = int(per_wall)
    else:
        u = rng.random()
        target = int_draw(u, cfg["count_per_wall"])
    counts = {"zone": 0, "drag": 0, "cloud": 0, "wipe": 0, "stray": 0}
    # scrabble zones over dune peaks (local maxima of the per-metre profile >= frac x wall max)
    zc = cfg["zones"]
    pm = prof.pm
    peaks = [i for i in range(len(pm)) if pm[i] >= zc["dune_frac_min"] * prof.dmax
             and pm[i] >= max(pm[max(0, i - 2):i + 3])]
    centres = []
    for i in peaks:
        u = rng.random()
        n = int_draw(u, zc["per_peak"])
        for _ in range(n):
            u = rng.random()
            centres.append(i * 100.0 + span_draw(u, (-80.0, 180.0)))
    u = rng.random()
    extra = int_draw(u, zc["extra_random"])
    for _ in range(extra):
        u = rng.random()
        centres.append(prof.along_from_u(u, w.a_lo, w.a_hi, 2.0, 0.0))
    n_event = 0
    for c in centres:
        n_event += 1
        counts["zone"] += 1
        zone(rng, w, cfg, c, "%s-Z%03d" % (w.wall["id"], n_event), prints, smears)
    ev = cfg["events"]
    while len(w.kept) < target:
        if w.attempts > cfg["max_attempts_per_wall"]:
            raise GreaseError("WALL_%s_CANNOT_REACH_COUNT|%d/%d" % (w.wall["id"], len(w.kept), target))
        n_event += 1
        event = "%s-E%04d" % (w.wall["id"], n_event)
        u = rng.random()
        kind = pick_weighted(u, ev)
        counts[kind] += 1
        u = rng.random()
        along = prof.along_from_u(u, w.a_lo, w.a_hi, cfg["along_weight"]["gamma"], cfg["along_weight"]["base"])
        span = max(0.0, prof.top(along) - prof.line(along))
        if kind == "drag":
            drag(rng, w, cfg, along, span, event, smears)
        elif kind == "cloud":
            cloud(rng, w, cfg, along, span, event, prints, smears)
        elif kind == "wipe":
            wipe(rng, w, cfg, along, span, event, prints, smears)
        else:
            stray(rng, w, cfg, along, span, event, prints, smears)
    return counts, target, len(peaks)


def pick(rng, pool):
    u = rng.random()
    return pool[hp.index_of(u, len(pool))]


def zone(rng, w, cfg, centre, event, prints, smears):
    zc = cfg["zones"]
    u = rng.random()
    nb = int_draw(u, zc["blobs"])
    u = rng.random()
    rise = span_draw(u, zc["rise_cm"])
    blobs = []
    for _ in range(nb):
        u = rng.random()
        da = span_draw(u, (-150.0, 150.0))
        u = rng.random()
        dz = span_draw(u, (0.0, rise))
        u = rng.random()
        r = span_draw(u, zc["blob_r_cm"])
        blobs.append((centre + da, dz, r))
    u = rng.random()
    n = int_draw(u, zc["decals"])
    for _ in range(n):
        u = rng.random()
        ba, bz, br = blobs[hp.index_of(u, len(blobs))]
        u = rng.random()
        rr = br * math.sqrt(-2.0 * math.log(max(1e-9, 1.0 - u))) * 0.6
        u = rng.random()
        th = 2.0 * math.pi * u
        a = ba + rr * math.cos(th)
        u = rng.random()
        if u < zc["p_smear"]:
            entry = pick(rng, smears)
            u = rng.random()
            roll = span_draw(u, (-60.0, 60.0)) + (180.0 if hp.index_of(u, 7) % 2 else 0.0)
            if w.drips[entry["element"]]:
                roll = span_draw(u, (-25.0, 25.0))
            u = rng.random()
            sx = span_draw(u, (0.7, 1.1))
            u = rng.random()
            sy = span_draw(u, (0.6, 1.3))
        else:
            entry = pick(rng, prints)
            roll = print_roll(rng, cfg)
            u = rng.random()
            sx = sy = span_draw(u, cfg["print_scale"])
        e = w.elements[entry["element"]]
        height = w.line(a) + max(0.0, bz + rr * math.sin(th)) + e["height_cm"] * entry["crop"][3] * sy / 2.0
        w.add(entry, a, height, roll, sx, sy, event, "zone")


def drag(rng, w, cfg, along, span, event, smears):
    dc = cfg["drag"]
    u_mix = rng.random()
    u_val = rng.random()
    rel = rel_height(u_mix, u_val, span, dc["lambda_cm"], dc["p_flat"])
    u = rng.random()
    n = int_draw(u, dc["per_event"])
    u = rng.random()
    vertical = u < dc["p_vertical"]
    u = rng.random()
    tilt = span_draw(u, (-dc["vertical_tilt_deg"], dc["vertical_tilt_deg"])) if vertical else \
        span_draw(u, dc["diagonal_tilt_deg"])
    u = rng.random()
    side = 1.0 if u < 0.5 else -1.0
    u = rng.random()
    flipdir = 180.0 if u < 0.5 else 0.0
    base_roll = flipdir + side * tilt
    for _ in range(n):
        entry = pick(rng, smears)
        e = w.elements[entry["element"]]
        u = rng.random()
        da = span_draw(u, (-dc["spread_cm"][1], dc["spread_cm"][1]))
        u = rng.random()
        dz = span_draw(u, dc["rise_cm"])
        u = rng.random()
        sy = span_draw(u, dc["length_scale"])
        u = rng.random()
        sx = span_draw(u, dc["width_scale"])
        u = rng.random()
        roll = base_roll + span_draw(u, (-dc["roll_jitter_deg"], dc["roll_jitter_deg"]))
        if w.drips[entry["element"]]:
            roll = hp.clamp(scr.norm_roll(roll - flipdir), -dc["drip_roll_deg"], dc["drip_roll_deg"])
        a = along + da
        height = w.line(a) + max(0.0, rel + dz) + e["height_cm"] * entry["crop"][3] * sy / 2.0
        w.add(entry, a, height, roll, sx, sy, event, "drag")


def cloud(rng, w, cfg, along, span, event, prints, smears):
    cc = cfg["cloud"]
    u_mix = rng.random()
    u_val = rng.random()
    rel = rel_height(u_mix, u_val, span, cc["lambda_cm"], cfg["drag"]["p_flat"])
    u = rng.random()
    n = int_draw(u, cc["decals"])
    u = rng.random()
    r = span_draw(u, cc["blob_r_cm"])
    for _ in range(n):
        u = rng.random()
        rr = r * math.sqrt(-2.0 * math.log(max(1e-9, 1.0 - u))) * 0.6
        u = rng.random()
        th = 2.0 * math.pi * u
        u = rng.random()
        if u < cc["p_smear"]:
            entry = pick(rng, smears)
            u = rng.random()
            roll = span_draw(u, (-180.0, 180.0))
            if w.drips[entry["element"]]:
                roll = span_draw(u, (-25.0, 25.0))
            sx = sy = 0.8
        else:
            entry = pick(rng, prints)
            roll = print_roll(rng, cfg)
            u = rng.random()
            sx = sy = span_draw(u, cfg["print_scale"])
        e = w.elements[entry["element"]]
        a = along + rr * math.cos(th)
        height = w.line(a) + max(0.0, rel + rr * math.sin(th)) + e["height_cm"] * entry["crop"][3] * sy / 2.0
        w.add(entry, a, height, roll, sx, sy, event, "cloud")


def wipe(rng, w, cfg, along, span, event, prints, smears):
    wc = cfg["wipe"]
    u_mix = rng.random()
    u_val = rng.random()
    rel = rel_height(u_mix, u_val, span, wc["lambda_cm"], cfg["drag"]["p_flat"])
    u = rng.random()
    n = int_draw(u, wc["pieces"])
    u = rng.random()
    R = span_draw(u, wc["radius_cm"])
    u = rng.random()
    spanang = math.radians(span_draw(u, wc["span_deg"]))
    u = rng.random()
    phi0 = 2.0 * math.pi * u
    step = spanang / max(1, n - 1)
    for k in range(n):
        phi = phi0 + k * step
        r_view, z = R * math.cos(phi), R * math.sin(phi)            # viewer-right / up, relative to the arc centre
        roll = math.degrees(math.atan2(-math.sin(phi), -math.cos(phi)))   # long axis (decal Y) on the tangent
        u = rng.random()
        if u < wc["p_heel"]:
            heels = [p for p in prints if p["crop_name"] == "heel"] or prints
            entry = pick(rng, heels)
            u = rng.random()
            sx = sy = span_draw(u, cfg["print_scale"])
        else:
            entry = pick(rng, smears)
            u = rng.random()
            sy = hp.clamp(R * step * 1.6 / w.elements[entry["element"]]["height_cm"], 0.35, 1.6)
            sx = span_draw(u, (0.7, 1.1))
            if w.drips[entry["element"]]:
                roll = hp.clamp(scr.norm_roll(roll), -25.0, 25.0)
        e = w.elements[entry["element"]]
        a = along + w.s * r_view
        height = w.line(a) + rel + R + z + e["height_cm"] * entry["crop"][3] * sy / 2.0
        w.add(entry, a, height, roll, sx, sy, event, "wipe")


def stray(rng, w, cfg, along, span, event, prints, smears):
    sc = cfg["stray"]
    u = rng.random()
    high = u < sc["p_above_envelope"]
    u = rng.random()
    use_smear = u < 0.4
    entry = pick(rng, smears if use_smear else prints)
    e = w.elements[entry["element"]]
    roll = print_roll(rng, cfg)
    if use_smear and w.drips[entry["element"]]:
        roll = hp.clamp(roll, -25.0, 25.0)
    u = rng.random()
    s = span_draw(u, cfg["print_scale"])
    ceiling = None
    if high:
        u = rng.random()
        ceiling = span_draw(u, sc["above_ceiling_cm"])
        u = rng.random()
        height = span_draw(u, (w.prof.top(along), ceiling))
    else:
        u = rng.random()
        height = w.line(along) + span_draw(u, (sc["rel_min_cm"], max(sc["rel_min_cm"], span)))
    w.add(entry, along, height, roll, s, s, event, "stray_high" if high else "stray", ceiling)


def build(cfg: dict, seed: int = None, per_wall=None) -> dict:
    seed = cfg["seed"] if seed is None else seed
    sets, dune = base.load_inputs(cfg)
    walls_doc, walls_sha, placeholder = hp.load_walls(base.WALLS, False)
    atlas_raw = base.ATLAS.read_bytes()
    atlas_doc = json.loads(atlas_raw.decode("utf-8"))
    elements = {e["id"]: e for e in atlas_doc["elements"]}
    drips = {k: v["drips"] for k, v in json.loads(base.DRIPS.read_text(encoding="utf-8"))["elements"].items()}
    boxes, excl_meta = hp.load_exclusions(base.EXCLUSIONS)
    gmask = np.asarray(Image.open(GREASE_ATLAS).convert("RGB"), np.float32)[..., 0] / 255.0
    rng = hp.Rng(seed)
    pool = build_pool(rng, cfg, elements, gmask)
    prints = [p for p in pool if p["kind"] == "print"]
    smears = [p for p in pool if p["kind"] == "smear"]
    walls = {w["id"]: w for w in walls_doc["walls"]}
    decals, per = [], {}
    for wid in cfg["walls"]:
        wall = walls[wid]
        knots = []
        for _ in range(int(math.ceil(wall["length_cm"] / cfg["envelope"]["noise_step_cm"])) + 2):
            u = rng.random()
            knots.append(u)
        prof = base.Profile(dune["wall_profile_max_per_metre_cm"][cfg["wall_dune_profile"][wid]], wall["length_cm"],
                            cfg, knots)
        w = Wall(wall, boxes.get(wid, []), prof, cfg, elements, drips)
        counts, target, n_peaks = generate_wall(rng, w, cfg, prints, smears, per_wall)
        rows = sorted(w.kept, key=lambda d: (d["along_cm"], d["height_cm"], d["material_instance"], d["roll_on_wall_deg"]))
        for n, row in enumerate(rows, 1):
            row["id"] = "HP_S03G_%s_%04d" % (wid, n)
            row["label"] = "HP_S03G %s %04d" % (wid, n)
        decals.extend(rows)
        his = [r["high_extent_cm"] for r in rows]
        kinds = {}
        for r in rows:
            kinds[r["event_kind"]] = kinds.get(r["event_kind"], 0) + 1
        per[wid] = {"count": len(rows), "target": target, "attempts": w.attempts, "rejected": w.rej,
                    "events": counts, "dune_peaks": n_peaks, "decals_by_kind": kinds,
                    "smear": sum(r["kind"] == "smear" for r in rows), "print_partial_or_full": sum(r["kind"] == "print" for r in rows),
                    "crops": {c: sum(r["crop_name"] == c for r in rows) for c in sorted({r["crop_name"] for r in rows})},
                    "gains": {str(g): sum(r["gain"] == g for r in rows) for g in cfg["pool"]["gains"]},
                    "highest_extent_by_150cm_band": [sum(lo <= h < lo + 150 for h in his) for lo in (0, 150, 300, 450, 600, 750)],
                    "highest_extent_cm": round(max(his), 1),
                    "lowest_extent_minus_dune_cm_min": round(min(r["low_extent_cm"] - r["dune_floor_cm"] for r in rows), 2),
                    "distinct_mis": len({r["material_instance"] for r in rows}),
                    "envelope_knots": [round(k, 6) for k in knots]}
    used = sorted({r["material_instance"] for r in decals})
    box = json.loads(json.dumps(walls_doc["landed_box_world_cm"]))
    box["max"][2] = float(cfg["marble_top_world_z_cm"])
    return {
        "schema": SCHEMA, "variant": "grease_sheen_dune_%s" % cfg["height_set"], "placeholder": placeholder,
        "seed": seed, "walls_file": base.WALLS.name, "walls_sha256": walls_sha,
        "atlas_file": base.ATLAS.name, "atlas_sha256": hashlib.sha256(atlas_raw).hexdigest(),
        "grease_atlas": str(GREASE_ATLAS.relative_to(PROJECT)).replace("\\", "/"),
        "grease_atlas_sha256": base.sha(GREASE_ATLAS), "smear_drips_sha256": base.sha(base.DRIPS),
        "config_file": CONFIG.name, "config_sha256": base.sha(CONFIG), "config": cfg,
        "dune": {"file": str(base.HEIGHT_SETS.relative_to(PROJECT)).replace("\\", "/"), "sha256": base.sha(base.HEIGHT_SETS),
                 "set": cfg["height_set"], "grid_sha256": dune["grid_sha256"]},
        "level": walls_doc.get("level"), "landed_box_world_cm": box,
        "material": cfg["material"],
        "mi_pool": pool, "mi_used": used,
        "tool": "Saved/CodexFlatV3/handprints/clamber/hp_grease_layout.py",
        "frame": "as build_handprint_placement.py; roll 0 = art upright; crop = sub-rect [u0,v0,us,vs] of the element",
        "exclusions": excl_meta, "stats": per, "decals": decals,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args(argv)
    if args.out.exists() and not args.overwrite:
        print("HP_GREASE_FAIL|OUTPUT_EXISTS|%s" % args.out, file=sys.stderr)
        return 2
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    try:
        doc = build(cfg, args.seed)
    except (GreaseError, base.ClamberError, hp.PlacementError) as exc:
        print("HP_GREASE_FAIL|%s" % exc, file=sys.stderr)
        return 2
    data = base.dumps(doc)
    args.out.write_bytes(data)
    print("HP_GREASE_OK|%s|pool=%d|used=%d|sha256=%s" % ("|".join("%s=%d" % (k, v["count"]) for k, v in doc["stats"].items()),
                                                      len(doc["mi_pool"]), len(doc["mi_used"]),
                                                      hashlib.sha256(data).hexdigest()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
