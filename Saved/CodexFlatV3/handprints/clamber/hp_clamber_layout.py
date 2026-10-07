"""S3 hand prints, CLAMBER layout (Gary 7 Oct).  OFFLINE; the output is DATA for hp_place_decals.py.

Gary, 7 Oct (his words): dunes set B (~2.4 m at the walls) "seems fine, but prints can go up higher than
only 20cm more, since the implication should be that people are trying to clamber out desperately".

Reads (never writes):
  hp_clamber_config.json (this folder)                       every knob, seed included
  Saved/CodexConductor/S3Shore/s3_shore_height_sets.json      set B per-metre dune max at each marble face
  DerivedAssets/FlatV3/HandPrints/walls_S03.json             wall frames (probe 6 Oct)
  DerivedAssets/FlatV3/HandPrints/atlas_job24d/atlas.json    elements + sizes
  Saved/CodexFlatV3/handprints/hp_mi_v3_worklist.json        the 178 element x flip v3 MIs that EXIST (no new MIs)
  DerivedAssets/FlatV3/HandPrints/smear_drips.json           which smears carry drips (Gary's +-30 deg rule)
  Saved/CodexFlatV3/handprints/hp_probe_walls_result.json    exclusions (practicals +30, waves, backdrop, deck)
Writes: placement_S03_clamber.json (schema hp_placement/1, the format hp_place_decals.py consumes).

Frame: walls_S03.json -- height_cm is above floor_z_cm (-5 world) = above the S3 floor top (root-local z 115),
which is the frame of s3_shore_height_sets.json; along_cm = root-local x (wall origin = root landed x).

Rules (all distances cm):
  FLOOR     every decal's LOWEST rotated extent >= max(per-metre dune max over the metres its along-extent
            touches, +-pad) + min_clearance (20).  Never a flat line: it follows the dune profile.
  LOWEST    scrabble events start 20-40 above that dune line (lowest_clearance_cm).
  DENSITY   event positions along the wall are weighted by the local dune height (people climbed the dunes
            to reach the wall); heights above the line are a truncated exponential (lambda 110) plus a 12 %
            flat share, so prints are densest just above the sand and thin upward.
  ENVELOPE  top(a) = clamp(line(a) + 190 + 260 * n(a), 360, 720), n = smooth seeded value noise (400 cm knots):
            ~5-7 m where the dunes are high.  Every non-outlier decal's highest extent <= top(a).
  OUTLIERS  2-4 desperate climbs per wall, at high-dune spots, may run above top(a) up to 780-900.
  KINDS     scrabble (5-10 overlapping prints in a ~70 cm patch right above the sand, +opt. drag),
            climb (alternating hands, 18-38 up per step, a per-climb lean), pair (same element unmirrored +
            mirrored, 38-60 apart), single, drag (smears: non-drip ones point UP, roll 180 +-4..22, or
            diagonal 180 +-22..48; drip smears stay within +-22 of upright; 35 % come as 2-3 parallel
            finger/hand drags).  Corners: 3-5 extra scrabble events in the last 30-450 cm before the far
            (backdrop) corner of each wall, where the dunes are deepest.
  KEEP-OUT  the far wall (backdrop mural + the closed door) gets NO prints; side-wall prints keep the wall's
            150 cm end margin (>= far_wall_clear_cm from the backdrop plane).  Practical lamps (+30) and the
            waves are skipped, as before.  Only existing v3 MIs; same atlas; element sizes x0.92-1.08.
  DUP       near-duplicate atlas groups stay >= 1.75 m apart between events (scramble rule).
RANDOMNESS: one rng.random() per statement (lint_one_draw.py); same seed + same inputs = same bytes.

  python hp_clamber_layout.py [--out PATH] [--seed N] [--overwrite]
Marker: HP_CLAMBER_OK|L=<n>|R=<n>|sha256=<table sha> or HP_CLAMBER_FAIL|<reason>.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[3]
TOOLS = PROJECT / "Tools/FlatV3/handprints"
sys.path.insert(0, str(TOOLS))
import build_handprint_placement as hp  # noqa: E402
import build_handprint_placement_scramble as scr  # noqa: E402

HP_DIR = PROJECT / "DerivedAssets/FlatV3/HandPrints"
CONFIG = HERE / "hp_clamber_config.json"
HEIGHT_SETS = PROJECT / "Saved/CodexConductor/S3Shore/s3_shore_height_sets.json"
WALLS = HP_DIR / "walls_S03.json"
ATLAS = HP_DIR / "atlas_job24d" / "atlas.json"
WORKLIST = PROJECT / "Saved/CodexFlatV3/handprints/hp_mi_v3_worklist.json"
DRIPS = HP_DIR / "smear_drips.json"
EXCLUSIONS = hp.PROBE_DEFAULT
OUT_DEFAULT = HERE / "placement_S03_clamber.json"
SCHEMA = "hp_placement/1"
EPS = 0.01


class ClamberError(RuntimeError):
    pass


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ----------------------------------------------------------------------------- pure maps (no draws)

def span_draw(u: float, lo_hi) -> float:
    return hp.lerp(u, lo_hi[0], lo_hi[1])


def int_draw(u: float, lo_hi) -> int:
    return int(lo_hi[0]) + hp.index_of(u, int(lo_hi[1]) - int(lo_hi[0]) + 1)


def rel_height(u_mix: float, u_val: float, span: float, lam: float, p_flat: float) -> float:
    """Height above the dune line: truncated exponential (dense low) plus a flat share."""
    if span <= 0.0:
        return 0.0
    if u_mix < p_flat:
        return u_val * span
    return -lam * math.log(1.0 - u_val * (1.0 - math.exp(-span / lam)))


class Profile:
    """Per-metre dune max at one marble face (set B) -> floor line, weights, envelope."""

    def __init__(self, per_metre, length_cm: float, cfg: dict, knots):
        if len(per_metre) * 100.0 < length_cm - 1e-6:
            raise ClamberError("DUNE_PROFILE_SHORT|%d" % len(per_metre))
        self.pm = [float(v) for v in per_metre]
        self.length = length_cm
        self.clear = float(cfg["min_clearance_cm"])
        self.pad = float(cfg["dune_extent_pad_cm"])
        env = cfg["envelope"]
        self.env = env
        self.knots = knots                     # value-noise knots, one per noise_step
        self.dmax = max(self.pm)

    def dune_over(self, a0: float, a1: float) -> float:
        """Max of the per-metre dune maxima over every metre touched by [a0, a1] (+-pad)."""
        i0 = max(0, int(math.floor((a0 - self.pad) / 100.0)))
        i1 = min(len(self.pm) - 1, int(math.floor((a1 + self.pad) / 100.0)))
        return max(self.pm[i0:i1 + 1])

    def line(self, a: float) -> float:
        return self.dune_over(a, a) + self.clear

    def noise(self, a: float) -> float:
        step = self.env["noise_step_cm"]
        t = a / step
        k = min(len(self.knots) - 2, max(0, int(math.floor(t))))
        f = t - k
        w = (1.0 - math.cos(math.pi * f)) / 2.0
        return self.knots[k] * (1.0 - w) + self.knots[k + 1] * w

    def top(self, a: float) -> float:
        e = self.env
        return hp.clamp(self.line(a) + e["reach_base_cm"] + e["reach_var_cm"] * self.noise(a),
                        e["min_top_cm"], e["max_top_cm"])

    def along_from_u(self, u: float, a_lo: float, a_hi: float, gamma: float, base: float, forbid=()) -> float:
        """Inverse CDF over 10 cm cells weighted base + (dune/dmax)^gamma (deterministic, no draw).
        Cells overlapping a forbid interval get weight 0."""
        cells, acc = [], 0.0
        a = a_lo
        while a < a_hi - 1e-9:
            b = min(a_hi, a + 10.0)
            blocked = any(a < f1 and b > f0 for f0, f1 in forbid)
            w = 0.0 if blocked else (base + (self.dune_over(a, b) / self.dmax) ** gamma) * (b - a)
            acc += w
            cells.append((acc, a, b))
            a = b
        target = u * acc
        prev = 0.0
        for cum, a0, b0 in cells:
            if target <= cum:
                f = 0.0 if cum <= prev else (target - prev) / (cum - prev)
                return a0 + f * (b0 - a0)
            prev = cum
        return a_hi


def extents(row):
    """(lowest, highest) height above floor and (along_min, along_max) of the rotated decal box."""
    ax, half = row["axes"], row["decal_size"]
    v = abs(ax["y"][2]) * half[1] + abs(ax["z"][2]) * half[2]
    h = abs(ax["y"][0]) * half[1] + abs(ax["z"][0]) * half[2]          # walls run along world X
    return row["height_cm"] - v, row["height_cm"] + v, row["along_cm"] - h, row["along_cm"] + h


# ----------------------------------------------------------------------------- one wall

class WallGen:
    def __init__(self, wall, boxes, prof: Profile, cfg: dict, pools, drips):
        self.wall, self.boxes, self.prof, self.cfg = wall, boxes, prof, cfg
        self.elements, self.prints, self.mirrorable, self.smears = pools
        self.drips = drips
        m0, m1 = wall.get("along_margin_cm", [0.0, 0.0])
        self.a_lo, self.a_hi = m0, wall["length_cm"] - m1
        self.kept, self.placed = [], []
        self.excluded = {k: 0 for k in hp.EXCLUSION_KINDS}
        self.attempts = self.no_room = self.dup_skipped = self.dup_reassigned = self.clamped_up = 0
        self.clamped_down = 0

    def lamp_windows(self):
        """Along intervals of the practical-lamp exclusion boxes, widened by the outlier climb's wander."""
        pad = self.cfg["outliers"]["lamp_pad_cm"]
        o = self.wall["origin_cm"][0]
        return sorted((b["min"][0] - o - pad, b["max"][0] - o + pad) for b in self.boxes if b["kind"] == "practical")

    # same event-aware duplicate rule as the scramble table
    def conflict(self, group, along, height, event):
        if not group:
            return False
        for g, a, h, ev in self.placed:
            if g == group and ev != event and math.hypot(along - a, height - h) < hp.DUP_MIN_DIST_CM + 25.0:
                return True
        return False

    def pick(self, candidates, u, along, height, event):
        start = hp.index_of(u, len(candidates))
        for k in range(len(candidates)):
            cand = candidates[(start + k) % len(candidates)]
            eid = cand[0] if isinstance(cand, tuple) else cand
            if not self.conflict(self.elements[eid].get("dup_group"), along, height, event):
                if k:
                    self.dup_reassigned += 1
                return cand
        return candidates[start]

    def add(self, item, event, kind, outlier_ceiling=None):
        """Fit the decal between the dune floor and its ceiling (clamp, no draw); exclusions; keep."""
        self.attempts += 1
        item = dict(item, along=hp.clamp(item["along"], self.a_lo, self.a_hi))
        row = hp.to_decal(self.wall, item)
        lo_ext, hi_ext, a0, a1 = extents(row)
        v = row["height_cm"] - lo_ext
        floor = self.prof.dune_over(a0, a1) + self.prof.clear
        ceiling = outlier_ceiling if outlier_ceiling is not None else self.prof.top(row["along_cm"])
        ceiling = min(ceiling, self.cfg["global_ceiling_cm"])
        lo, hi = floor + v + EPS, ceiling - v - EPS
        if lo > hi:
            self.no_room += 1
            return False
        h = hp.clamp(row["height_cm"], lo, hi)
        if abs(h - row["height_cm"]) > 1e-9:
            if h > row["height_cm"]:
                self.clamped_up += 1
            else:
                self.clamped_down += 1
            row = hp.to_decal(self.wall, dict(item, height=h))
        hit = hp.excluded_by(row, self.boxes)
        if hit:
            self.excluded[hit] += 1
            return False
        if self.conflict(item["element"].get("dup_group"), row["along_cm"], row["height_cm"], event):
            self.dup_skipped += 1
            return False
        lo_ext, hi_ext, a0, a1 = extents(row)
        row.update({"event": event, "event_kind": kind, "outlier": outlier_ceiling is not None,
                    "smear_direction": item.get("direction"), "fade_screen_size": 0.0,
                    "dune_floor_cm": round(self.prof.dune_over(a0, a1), 3),
                    "low_extent_cm": round(lo_ext, 3), "high_extent_cm": round(hi_ext, 3),
                    "ceiling_cm": round(ceiling, 3)})
        self.kept.append(row)
        group = item["element"].get("dup_group")
        if group:
            self.placed.append((group, row["along_cm"], row["height_cm"], event))
        return True

    def centre(self, along, rel, element, jitter):
        """Centre height for a decal whose lowest (unrotated) edge sits rel above the dune line."""
        return self.prof.line(along) + rel + element["height_cm"] * jitter / 2.0


def item_for(element, flip, along, height, roll, jitter, kind, direction=None):
    return scr.item_for(element, flip, along, height, roll, jitter, kind, direction)


def generate_wall(rng, wall, boxes, prof: Profile, cfg, pools, drips, per_wall=None):
    g = WallGen(wall, boxes, prof, cfg, pools, drips)
    elements, prints, mirrorable, smears = pools
    ev_cfg = cfg["events"]
    order = ("scrabble", "climb", "pair", "single", "drag")
    cum = []
    acc = 0.0
    for k in order:
        acc += ev_cfg[k]
        cum.append((acc, k))
    if abs(acc - 1.0) > 1e-9:
        raise ClamberError("EVENT_SHARES_NOT_1|%.4f" % acc)
    if per_wall:
        target = int(per_wall)
    else:
        u = rng.random()
        target = int_draw(u, cfg["count_per_wall"])
    hcfg = cfg["height_profile"]
    aw = cfg["along_weight"]
    counts = {k: 0 for k in order}
    counts.update({"corner_scrabble": 0, "outlier_climb": 0})
    n_event = 0
    # scheduled events first: corner scrabbles, then the desperate outliers
    u = rng.random()
    n_corner = int_draw(u, cfg["corner"]["events_per_wall"])
    u = rng.random()
    n_out = int_draw(u, cfg["outliers"]["per_wall"])
    schedule = ["corner"] * n_corner + ["outlier"] * n_out
    while len(g.kept) < target:
        if g.attempts > cfg["max_attempts_per_wall"]:
            raise ClamberError("WALL_%s_CANNOT_REACH_COUNT|%d/%d" % (wall["id"], len(g.kept), target))
        n_event += 1
        event = "%s-E%04d" % (wall["id"], n_event)
        if schedule:
            kind = schedule.pop(0)
        else:
            u = rng.random()
            kind = next(k for edge, k in cum if u < edge or edge == cum[-1][0])
        if kind == "corner":
            u = rng.random()
            from_end = span_draw(u, cfg["corner"]["from_end_cm"])
            along = g.a_hi - from_end
            counts["corner_scrabble"] += 1
            scrabble(rng, g, along, event, "corner_scrabble")
            continue
        if kind == "outlier":
            u = rng.random()
            along = prof.along_from_u(u, g.a_lo, g.a_hi, cfg["outliers"]["dune_gamma"], 0.0, g.lamp_windows())
            counts["outlier_climb"] += 1
            outlier(rng, g, along, event)
            continue
        counts[kind] += 1
        u = rng.random()
        along = prof.along_from_u(u, g.a_lo, g.a_hi, aw["gamma"], aw["base"])
        span = max(0.0, prof.top(along) - prof.line(along))
        if kind == "scrabble":
            scrabble(rng, g, along, event, "scrabble")
        elif kind == "climb":
            climb(rng, g, along, span, event)
        elif kind == "pair":
            pc = cfg["pair"]
            u_mix = rng.random()
            u_val = rng.random()
            rel = rel_height(u_mix, u_val, span, hcfg["lambda_cm"], hcfg["p_flat"])
            u = rng.random()
            sep = span_draw(u, pc["separation_cm"])
            u = rng.random()
            dh = span_draw(u, (-pc["height_jitter_cm"], pc["height_jitter_cm"]))
            u = rng.random()
            roll = span_draw(u, (-pc["roll_deg"], pc["roll_deg"]))
            u = rng.random()
            jitter = span_draw(u, cfg["size_jitter"])
            u = rng.random()
            eid = g.pick(mirrorable, u, along, prof.line(along) + rel, event)
            e = elements[eid]
            height = g.centre(along, rel, e, jitter)
            g.add(item_for(e, False, along - sep / 2.0, height, roll, jitter, "print"), event, "pair")
            g.add(item_for(e, True, along + sep / 2.0, height + dh, -roll, jitter, "print"), event, "pair")
        elif kind == "single":
            u_mix = rng.random()
            u_val = rng.random()
            rel = rel_height(u_mix, u_val, span, hcfg["lambda_cm"], hcfg["p_flat"])
            u = rng.random()
            roll = span_draw(u, (-cfg["single"]["roll_deg"], cfg["single"]["roll_deg"]))
            u = rng.random()
            jitter = span_draw(u, cfg["size_jitter"])
            u = rng.random()
            eid, flip = g.pick(prints, u, along, prof.line(along) + rel, event)
            e = elements[eid]
            g.add(item_for(e, flip, along, g.centre(along, rel, e, jitter), roll, jitter, "print"), event, "single")
        else:
            dc = cfg["drag"]
            u_mix = rng.random()
            u_val = rng.random()
            rel = rel_height(u_mix, u_val, span, dc["lambda_cm"], hcfg["p_flat"])
            drag(rng, g, along, rel, event, "drag")
    return g, counts, target


def scrabble(rng, g: WallGen, along, event, kind):
    """Several overlapping prints right above the sand where someone fought for a hold."""
    sc = g.cfg["scrabble"]
    u = rng.random()
    n = int_draw(u, sc["prints"])
    u = rng.random()
    start = span_draw(u, sc["start_rel_cm"])
    for _ in range(n):
        u = rng.random()
        da = span_draw(u, (-sc["half_width_cm"], sc["half_width_cm"]))
        u = rng.random()
        rise = span_draw(u, sc["rise_cm"])
        u = rng.random()
        roll = span_draw(u, (-sc["roll_deg"], sc["roll_deg"]))
        u = rng.random()
        jitter = span_draw(u, g.cfg["size_jitter"])
        u = rng.random()
        eid, flip = g.pick(g.prints, u, along + da, g.prof.line(along + da) + start + rise, event)
        e = g.elements[eid]
        g.add(item_for(e, flip, along + da, g.centre(along + da, start + rise, e, jitter), roll, jitter, "print"),
              event, kind)
    u = rng.random()
    if u < sc["p_drag"]:
        u = rng.random()
        rel = span_draw(u, (start, start + sc["rise_cm"][1]))
        drag(rng, g, along, rel, event, kind)


def climb(rng, g: WallGen, along, span, event):
    cc = g.cfg["climb"]
    u = rng.random()
    steps = int_draw(u, cc["steps"])
    u_mix = rng.random()
    u_val = rng.random()
    rel = rel_height(u_mix, u_val, span, cc["start_lambda_cm"], g.cfg["height_profile"]["p_flat"])
    u = rng.random()
    lean = span_draw(u, cc["lean_cm"])
    u = rng.random()
    eid = g.pick(g.mirrorable, u, along, g.prof.line(along) + rel, event)
    u = rng.random()
    first_flip = u < 0.5
    e = g.elements[eid]
    lean_roll = -cc["lean_roll_deg"] * lean / max(abs(cc["lean_cm"][0]), abs(cc["lean_cm"][1]))
    for k in range(steps):
        u = rng.random()
        roll = span_draw(u, (-cc["roll_deg"], cc["roll_deg"])) + lean_roll
        u = rng.random()
        jitter = span_draw(u, g.cfg["size_jitter"])
        flip = first_flip != bool(k % 2)
        height = g.centre(along, rel, e, jitter)
        if height - e["height_cm"] * jitter / 2.0 > g.prof.top(along):
            break
        g.add(item_for(e, flip, along, height, roll, jitter, "print"), event, "climb")
        u = rng.random()
        rel += span_draw(u, cc["step_up_cm"])
        u = rng.random()
        along += span_draw(u, cc["step_along_cm"]) + lean


def outlier(rng, g: WallGen, along, event):
    """A desperate climb that keeps going above the envelope, up to its own ceiling."""
    oc = g.cfg["outliers"]
    u = rng.random()
    ceiling = span_draw(u, oc["ceiling_cm"])
    rel = max(0.0, g.prof.top(along) - g.prof.line(along) - oc["start_below_top_cm"])
    u = rng.random()
    eid = g.pick(g.mirrorable, u, along, g.prof.line(along) + rel, event)
    u = rng.random()
    first_flip = u < 0.5
    e = g.elements[eid]
    k = 0
    while True:
        u = rng.random()
        roll = span_draw(u, (-oc["roll_deg"], oc["roll_deg"]))
        u = rng.random()
        jitter = span_draw(u, g.cfg["size_jitter"])
        height = g.centre(along, rel, e, jitter)
        if height + e["height_cm"] * jitter / 2.0 > ceiling or k > 40:
            break
        g.add(item_for(e, first_flip != bool(k % 2), along, height, roll, jitter, "print"), event,
              "outlier_climb", outlier_ceiling=ceiling)
        k += 1
        u = rng.random()
        rel += span_draw(u, oc["step_up_cm"])
        u = rng.random()
        along += span_draw(u, oc["step_along_cm"])


def drag(rng, g: WallGen, along, rel, event, kind):
    """Smear(s): non-drip drags point UP (roll 180 +- tilt) or diagonal; drip smears stay near upright."""
    dc = g.cfg["drag"]
    u = rng.random()
    sid = g.pick(g.smears, u, along, g.prof.line(along) + rel, event)
    e = g.elements[sid]
    u = rng.random()
    jitter = span_draw(u, g.cfg["size_jitter"])
    u = rng.random()
    side = 1.0 if u < 0.5 else -1.0
    if g.drips[sid]:
        u = rng.random()
        direction, roll = "down_drips", span_draw(u, (-dc["drip_roll_deg"], dc["drip_roll_deg"]))
    else:
        u = rng.random()
        direction = "up" if u < dc["p_up"] else "diagonal"
        u = rng.random()
        tilt = span_draw(u, dc["up_tilt_deg"] if direction == "up" else dc["diagonal_tilt_deg"])
        roll = scr.norm_roll(180.0 + side * tilt)
    u = rng.random()
    grouped = u < dc["p_group"]
    u = rng.random()
    extra = int_draw(u, dc["group_extra"]) if grouped else 0
    u = rng.random()
    spacing = span_draw(u, dc["group_spacing_cm"])
    for j in range(extra + 1):
        u = rng.random()
        rj = 0.0 if j == 0 else span_draw(u, (-dc["group_roll_jitter_deg"], dc["group_roll_jitter_deg"]))
        a = along + j * spacing
        r = roll + rj
        if direction == "down_drips":
            r = hp.clamp(r, -dc["drip_roll_deg"], dc["drip_roll_deg"])
        g.add(item_for(e, False, a, g.centre(a, rel, e, jitter), scr.norm_roll(r), jitter, "smear", direction),
              event, kind)


# ----------------------------------------------------------------------------- build

def load_inputs(cfg):
    sets = json.loads(HEIGHT_SETS.read_text(encoding="utf-8"))
    s = sets["sets"][cfg["height_set"]]
    if s.get("checks_failures"):
        raise ClamberError("DUNE_SET_HAS_FAILURES|%s" % s["checks_failures"])
    return sets, s


def build(cfg: dict, seed: int = None, per_wall=None) -> dict:
    seed = cfg["seed"] if seed is None else seed
    sets, dune = load_inputs(cfg)
    walls_doc, walls_sha, placeholder = hp.load_walls(WALLS, False)
    if placeholder:
        raise ClamberError("WALLS_PLACEHOLDER")
    atlas_raw = ATLAS.read_bytes()
    atlas_doc = json.loads(atlas_raw.decode("utf-8"))
    work, elements, prints, mirrorable, smears = scr.load_pairs(WORKLIST, atlas_doc)
    drips = {k: v["drips"] for k, v in json.loads(DRIPS.read_text(encoding="utf-8"))["elements"].items()}
    boxes, excl_meta = hp.load_exclusions(EXCLUSIONS)
    rng = hp.Rng(seed)
    decals, per = [], {}
    walls = {w["id"]: w for w in walls_doc["walls"]}
    for wid in cfg["walls"]:
        wall = walls[wid]
        knots = []
        n_knots = int(math.ceil(wall["length_cm"] / cfg["envelope"]["noise_step_cm"])) + 2
        for _ in range(n_knots):
            u = rng.random()
            knots.append(u)
        prof = Profile(dune["wall_profile_max_per_metre_cm"][cfg["wall_dune_profile"][wid]], wall["length_cm"],
                       cfg, knots)
        g, counts, target = generate_wall(rng, wall, boxes.get(wid, []), prof, cfg,
                                          (elements, prints, mirrorable, smears), drips, per_wall)
        rows = sorted(g.kept, key=lambda d: (d["along_cm"], d["height_cm"], d["element_id"], d["roll_on_wall_deg"]))
        for n, row in enumerate(rows, 1):
            row["id"] = "HP_S03_%s_%04d" % (wid, n)
            row["label"] = "HP_S03 %s %04d" % (wid, n)
            row["material_instance"] = "MI_HP_S03_v3_%s_F%d" % (row["element_id"], 1 if row["flip"] else 0)
            row.pop("decal_color", None)
        decals.extend(rows)
        bands = {}
        for lo, hi in ((0, 100), (100, 200), (200, 300), (300, 400), (400, 500), (500, 600), (600, 700),
                       (700, 800), (800, 900)):
            bands["%d-%d" % (lo, hi)] = sum(1 for r in rows if lo <= r["height_cm"] < hi)
        rel = [r["low_extent_cm"] - (r["dune_floor_cm"] + cfg["min_clearance_cm"]) for r in rows]
        per[wid] = {"count": len(rows), "target": target, "attempts": g.attempts, "excluded": g.excluded,
                    "no_room": g.no_room, "clamped_up": g.clamped_up, "clamped_down": g.clamped_down,
                    "dup_reassigned": g.dup_reassigned, "dup_skipped": g.dup_skipped, "events_started": counts,
                    "print": sum(r["kind"] == "print" for r in rows), "smear": sum(r["kind"] == "smear" for r in rows),
                    "outlier_decals": sum(r["outlier"] for r in rows),
                    "centre_height_bands_above_floor": bands,
                    "above_dune_line_cm_p10_p50_p90": [round(sorted(rel)[int(q * (len(rel) - 1))], 1)
                                                       for q in (0.1, 0.5, 0.9)],
                    "highest_extent_cm": round(max(r["high_extent_cm"] for r in rows), 1),
                    "lowest_extent_minus_dune_cm_min": round(min(r["low_extent_cm"] - r["dune_floor_cm"]
                                                                 for r in rows), 2),
                    "envelope_top_cm_min_max": [round(min(prof.top(a) for a in range(int(g.a_lo), int(g.a_hi) + 1, 10)), 1),
                                                round(max(prof.top(a) for a in range(int(g.a_lo), int(g.a_hi) + 1, 10)), 1)],
                    "distinct_mis": len({(r["element_id"], r["flip"]) for r in rows}),
                    "envelope_knots": [round(k, 6) for k in knots]}
    box = json.loads(json.dumps(walls_doc["landed_box_world_cm"]))
    box["max"][2] = float(cfg["marble_top_world_z_cm"])
    return {
        "schema": SCHEMA, "variant": "clamber_dune_%s" % cfg["height_set"], "placeholder": placeholder, "seed": seed,
        "walls_file": WALLS.name, "walls_sha256": walls_sha, "walls_source": walls_doc.get("source"),
        "atlas_file": ATLAS.name, "atlas_sha256": hashlib.sha256(atlas_raw).hexdigest(),
        "worklist_sha256": sha(WORKLIST), "smear_drips_sha256": sha(DRIPS),
        "config_file": CONFIG.name, "config_sha256": sha(CONFIG), "config": cfg,
        "dune": {"file": str(HEIGHT_SETS.relative_to(PROJECT)).replace("\\", "/"), "sha256": sha(HEIGHT_SETS),
                 "set": cfg["height_set"], "grid_sha256": dune["grid_sha256"],
                 "measured_wall_max_cm": dune["measured_wall_max_cm"],
                 "frame": sets["frame"]},
        "level": walls_doc.get("level"),
        "landed_box_world_cm": box,
        "landed_box_note": "walls_S03 box with max z raised from 600 to the marble top 2880 "
                           "(s3_backwall_marble_record.json: Upper 4 tiles aabb max z 2880)",
        "tool": "Saved/CodexFlatV3/handprints/clamber/hp_clamber_layout.py",
        "frame": "as build_handprint_placement.py; roll 0 = art upright, 180 = upside down (drag runs up)",
        "exclusions": excl_meta, "stats": per, "decals": decals,
    }


def dumps(doc) -> bytes:
    return (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode("utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args(argv)
    if args.out.exists() and not args.overwrite:
        print("HP_CLAMBER_FAIL|OUTPUT_EXISTS|%s" % args.out, file=sys.stderr)
        return 2
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    try:
        doc = build(cfg, args.seed)
    except (ClamberError, hp.PlacementError) as exc:
        print("HP_CLAMBER_FAIL|%s" % exc, file=sys.stderr)
        return 2
    data = dumps(doc)
    args.out.write_bytes(data)
    print("HP_CLAMBER_OK|%s|sha256=%s|out=%s" % ("|".join("%s=%d" % (k, v["count"]) for k, v in doc["stats"].items()),
                                               hashlib.sha256(data).hexdigest(), args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
