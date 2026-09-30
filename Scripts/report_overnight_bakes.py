"""Judge baked curtains against the 30 Sep acceptance test, offline, so a number decides what is placed.

    python Scripts/report_overnight_bakes.py [--ref final2_stage_v2] [--sheet a,b] id [id ...]

Gary is away for twelve hours. His brief: "the correct outcome for the curtains ... in terms of structured hanging
profile, the good fall we already got, ideally a couple of versions". The Conductor's test has three parts, and ALL
must pass before anything is placed:
  1. STILL: still_window_max_mm < STILL_LIMIT_MM over the hold window before anything moves. The traveller must also
     pass at the END, so its open stacks can be held. settle_to_2mm_s separates "never settles" from "the window
     opened too early".
     WHICH FRAMES the limit bounds: exactly those the audience sees move between the frozen hold and the release. The
     HOLD shows the cache's first sample frozen (zero motion by construction), then the window (show_start to release)
     plays. The settle BEFORE show_start is never exported, so a restless settle there (still_mm before show_start)
     is diagnostic only. It is not on screen.
  2. HANG: the bake's own hang_profile.pass. That means flare at most 1.15 at the Opening's width, and fold count kept
     at least 0.75 and depth kept at least 0.5 at 75/50/25% of the height, against the heading's.
  3. PILE, the approved fall preserved: height, depth, width, layers and fold size each within PILE_TOL of the
     reference. The reference is final2 (Gary: "the animation, the feel, looks good") for full-width Opening drapes; a
     strip is judged against its own strip control.
The fall timing (top below 1.8 m and 1.35 m) and the landing rebound are reported alongside, since they are what
"reads heavy" is made of.

WHY 2 mm/frame. The Opening's stalls camera is 14 m from the cloth, with a 15 mm lens on Super 35 (79 deg across), so at
1920 px one pixel is about 1.2 cm of cloth.
  - 2 mm/frame is about 1/6 px per frame. A one-tick HOLD frozen on the first sample, then released into motion that
    slow, has no visible seam, and a whole second of it drifts under 5 px.
  - final2, which Gary called "weirdly bouncy", moved about 8 mm/frame (24 cm of hem drift in its last second): 0.7 px
    per frame, 20 px of swim.
  - sw_b5_pswitch's slowly GROWING 2-3 mm/frame is marginal. It was caught only because it was measured, and on a
    projected shadow play it would be the screen swimming under the puppet. Writes <OUT>/acceptance_report.md, plus a side-by-side sheet for --sheet a,b.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Saved" / "CodexSoftGoods" / "DropBake"
STILL_LIMIT_MM = 2.0
# PER-SITE STILLNESS LIMIT (30 Sep, after Look & camera: P04's passage camera is 35 mm, not the stalls' 15 mm). The
# standard is PIXELS, not millimetres: 2 mm/frame at the stalls (15 mm on 23.76 mm Super 35, 14 m, 1920 px) is
# STD_PX_PER_FRAME. Each site's limit in mm/frame is derived from the lens that SEES that cloth, and the distance at the
# seam:
#   - Opening and the five transition drapes: their own stalls cameras (15 mm, 14 m; L&C copied the Opening's).
#   - The P04 backcloth: the passage camera, 35 mm, closing from 10 m to 7.5 m over the last second (the worst case is
#     taken).
# A number derived in one context must not be carried into another.
FILMBACK_W_MM, IMAGE_W_PX = 23.76, 1920
SITE_VIEW = {"stalls": (15.0, 14.0), "P04_passage": (35.0, 7.5)}   # (lens mm, distance m at the seam, worst case)


def mm_per_px(site):
    lens, dist = SITE_VIEW[site]
    return dist * FILMBACK_W_MM / lens / IMAGE_W_PX * 1000.0       # 2 d tan(hfov/2) / px, since tan(hfov/2) = w/(2 f)


STD_PX_PER_FRAME = STILL_LIMIT_MM / mm_per_px("stalls")          # about 0.173 px/frame: the stalls' 2 mm, in pixels


def derived_still_limit_mm(site):
    return round(STD_PX_PER_FRAME * mm_per_px(site), 2)
PILE_TOL = 0.25                      # provisional: each pile number within +-25% of the reference's
PILE_KEYS = ("height_m", "depth_m", "width_m", "layers", "fold_size_m")
P01_OPENING_M, COVERAGE_GAP_MAX_M = 19.0, 0.2       # post inner faces at +-9.5 m; all six portals identical (Rig, 30 Sep)
POST_CLEARANCE_MIN_M = 0.03                          # the widest hung row must not run into a post
FPS = 30.0


BLENDER = r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"


MASK_COLLIDERS = None     # set by --mask-colliders: the CURRENT built stage, if it differs from the bake's own file


def mask_top(d):
    """TOP MASKED (30 Sep, required with the Conductor's agreement): no ray from the stalls eye through the portal opening
    may pass OVER the drape top and reach the Passage. The header underside is 10.50 m, and the pleats can put the top
    behind the header's back face, leaving a comb of notches (final9: 21 of them, bright at the Opening). The ray test
    (Scripts/mask_raycast_stalls.py) runs on the bake's own .abc at the frozen sample (release - 1). Its result is re-used
    only when it was made from these exact .abc bytes. Returns (verdict, summary); None when it cannot be measured."""
    abc = OUT / f"{d['id']}.abc"
    if not abc.exists() or not d.get("release_frame"):
        return None, "not measured (no .abc or no release frame)"
    frame = int(d["release_frame"]) - 1
    out_id = f"mask_{d['id']}_f{frame}"
    # The rays are cast against the stage AS BUILT (a border added after the bake masks it too), so a result is re-used
    # only for the same .abc bytes AND the same stage file bytes. Keyed on the .abc alone, a border added later would
    # have left the stale FAIL standing (the Conductor's caution, 30 Sep).
    stage = MASK_COLLIDERS or d.get("colliders") or "Docs/StageFrontColliders_2026-09-28.json|v2"
    # LF-normalised: equals git's blob hash, and a CRLF checkout (autocrlf) is not a stage change.
    stage_digest = hashlib.sha256((ROOT / stage.split("|")[0]).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    mpath, digest = OUT / f"{out_id}.json", sha256_file(abc)
    m = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else {}
    if m.get("abc_sha256") != digest or m.get("colliders_sha256") != stage_digest or m.get("colliders") != stage             or m.get("extra_boxes"):
        env = dict(os.environ, PUSS_PROJECT_ROOT=str(ROOT), ABC=str(abc), MASK_FRAME=str(frame), OUT_ID=out_id,
                   MASK_STEP="2", COLLIDERS=stage)
        for k in ("MASK_EXTRA_BOXES", "MASK_Z_OFFSET_M"):      # never judge against a what-if
            env.pop(k, None)
        # A failed run must not leave the OLD result standing in for a new one (30 Sep: an env crash did exactly that).
        mpath.unlink(missing_ok=True)
        subprocess.run([BLENDER, "-b", "--factory-startup", "-t", "4", "--python",
                        str(ROOT / "Scripts" / "mask_raycast_stalls.py")], env=env, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not mpath.exists():
            return None, "ray test failed to run"
        m = json.loads(mpath.read_text(encoding="utf-8"))
        m["abc_sha256"] = digest
        m.pop("all_unmasked", None)                 # keep the verdict file small; re-run for the picture
        mpath.write_text(json.dumps(m, indent=1), encoding="utf-8")
    reg = m.get("by_region") or {}
    d["_mask_stage"] = {"colliders": stage, "sha256": stage_digest}
    return reg.get("top", 1) == 0, (f"frame {frame}: {reg.get('top')} rays over the top (rows {m.get('top_rows_px')}, "
                                    f"z at the curtain line {m.get('top_z_at_line_m')} m); side {reg.get('side')}, "
                                    f"bottom {reg.get('bottom')}, interior {reg.get('interior')} (step 2 px)")


def stage_clear(d):
    """STAGE CLEARANCE (30 Sep, approved by the Conductor): the cache against the stage AS BUILT, every exported frame
    (Scripts/stage_clearance_cache.py). Non-contact boxes (posts, header, border) must hold ZERO cloth vertices; contact
    boxes (floors, lip, fascia, returns, lamp housings as exact oriented boxes) must not be penetrated deeper than the
    cloth's 1 cm collision margin, and the measured depth is recorded so a change shows as a number moving. The same
    re-use key and fail-closed order as mask_top. final13 vs v4: clear, worst 0.12 cm into the stage floor."""
    abc = OUT / f"{d['id']}.abc"
    if not abc.exists():
        return None, "not measured (no .abc)"
    stage = MASK_COLLIDERS or d.get("colliders") or "Docs/StageFrontColliders_2026-09-28.json|v2"
    stage_digest = hashlib.sha256((ROOT / stage.split("|")[0]).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    out_id = f"clear_{d['id']}"
    cpath, digest = OUT / f"{out_id}.json", sha256_file(abc)
    c = json.loads(cpath.read_text(encoding="utf-8")) if cpath.exists() else {}
    if c.get("abc_sha256") != digest or c.get("colliders_sha256") != stage_digest or c.get("colliders") != stage:
        env = dict(os.environ, PUSS_PROJECT_ROOT=str(ROOT), ABC=str(abc), OUT_ID=out_id, COLLIDERS=stage)
        for k in ("CLEAR_FRAMES", "CLEAR_CONTACT_MAX_CM", "CLEAR_PROBE_FOOTPRINT"):     # never judge a what-if
            env.pop(k, None)
        cpath.unlink(missing_ok=True)                                          # invalidate BEFORE computing
        subprocess.run([BLENDER, "-b", "--factory-startup", "-t", "4", "--python",
                        str(ROOT / "Scripts" / "stage_clearance_cache.py")], env=env, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not cpath.exists():
            return None, "clearance test failed to run"
        c = json.loads(cpath.read_text(encoding="utf-8"))
        c["abc_sha256"] = digest
        cpath.write_text(json.dumps(c, indent=1), encoding="utf-8")
    worst = c.get("contact_worst") or {}
    return c.get("clear") is True, (f"frames {c.get('frames')}: non-contact hits {list(c.get('non_contact_hits') or {})}; "
                                    f"deepest contact {worst.get('max_depth_cm')} cm into {worst.get('box')} at frame "
                                    f"{worst.get('frame')} (limit {c.get('contact_max_cm')} cm)")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


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
        # A SOFT TAIL (the Conductor, 30 Sep): Rig sizes the Scene 4 section to the cache's duration, so a pile still
        # creeping at the end becomes a visible hold at the boundary. COM settled = first frame from which it moves
        # under 0.5 mm per frame for the rest of the cache.
        last_moving = max((i for i in range(1, len(com)) if abs(com[i] - com[i - 1]) >= 0.0005), default=0)
        out["com_settled_at_s"] = round((first + last_moving - d["release_frame"]) / FPS, 2)
        out["cache_ends_at_s"] = round((d["frames"] - d["release_frame"]) / FPS, 2)
    return out


def pile(d):
    return d["checkpoints"][str(d["frames"])]


def judge_drape(d, ref):
    still = d.get("still_window_max_mm")
    hp = d.get("hang_profile") or {}
    site = "P04_passage" if d.get("collider_origin_cm") else "stalls"
    limit = derived_still_limit_mm(site)
    # AT REST (30 Sep): every site now HOLDS the frame one before the release, so nothing moves on screen before the
    # fall, and no lens can see a seam. What remains is whether the FROZEN frame reads as a curtain AT REST, not one
    # arrested mid-sway (final2's frame 149 billowed past a post).
    # WHY NO LENS ENTERS: not "because the frame is frozen" (a frozen frame shows zero motion at any threshold). The
    # gate measures whether the SOURCE sample comes from a SETTLED moment of the simulation, a pose-quality property
    # of the cache, and the window's motion is the evidence of that.
    # THE 2 mm IS INHERITED, NOT DERIVED: it was the stalls pixel standard (0.173 px at 15 mm and 14 m) and is kept as a
    # reasonable proxy for "settled". A derivation on its own terms would bound the frozen pose's distance from the
    # equilibrium pose (e.g. net drift over a longer settle), which is not yet measured. The per-site seam limit is
    # kept as INFORMATION, for any site still holding the first sample (legacy).
    d["_still_limit"] = {"gate": "at rest (hold at release): window max < 2.0 mm/frame",
                         "legacy_seam_if_held_at_first_sample": {"site_view": site, "lens_mm_distance_m": SITE_VIEW[site],
                                                                 "limit_mm_per_frame": limit,
                                                                 "would_pass": still is not None and still < limit}}
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
        missing = [k for k in PILE_KEYS if k not in ratios]
        if missing:
            ratios["_missing"] = missing                   # a missing metric is reported, never silently skipped
        # 30 Sep noise floor (Docs/Conductor/PREREG_SWITCH_AMOUNT_2026-09-30.md): a seed change alone moved fold size
        # 28%, width 18% and layers 17%. Single-run pile numbers are too noisy to gate on, so the pile verdict is "look"
        # (None) unless a person's approval is recorded (--pile-approved). The ratios are shown as context only.
        verdict["pile"] = None
        verdict["pile_within_25pct_single_run"] = (not missing) and all(abs(ratios[k] - 1.0) <= PILE_TOL for k in PILE_KEYS)
    else:
        verdict["pile"] = None
    if d.get("collider_origin_cm"):
        verdict["site"] = site_ok(d)
    # COVERAGE (30 Sep, Gary: "the curtain blocks only about 80% of the stage, light leaks past both sides"). A curtain's
    # job is to MASK. At P01 the opening between the post faces is P01_OPENING_M; the gap per side is taken at the
    # NARROWEST hung row, since a leak anywhere shows. The target is provisional: posts on the curtain line make about
    # 10 cm the least achievable, so at most 0.2 m per side.
    if rows and not d.get("collider_origin_cm") and (d.get("track_m") or 0) >= 17.0:
        gap = round((P01_OPENING_M - min(r["width_m"] for r in rows.values())) / 2.0, 3)
        # ...and not TOO wide. All six portals are the same 19.0 m (Rig, 30 Sep), so the ~10 cm left at an 18.8 m track
        # is the tolerance at six sites. The WIDEST hung row must keep POST_CLEARANCE_MIN_M from each post face.
        clearance = round((P01_OPENING_M - max(r["width_m"] for r in rows.values())) / 2.0, 3)
        hp["coverage_gap_per_side_m"], hp["post_clearance_per_side_m"] = gap, clearance
        verdict["coverage"] = gap <= COVERAGE_GAP_MAX_M and clearance >= POST_CLEARANCE_MIN_M
    # FAIL CLOSED (30 Sep, the Conductor, from the adversarial review): ALL requires every REQUIRED criterion to be
    # explicitly True. Pending (None) FAILS. It used to be "not False", so a pile still awaiting Gary's eye passed and
    # the bake would have imported itself.
    # Required: still and hang, always. Then the PILE (a person's recorded approval) for a P01-reference drape, or the
    # SITE check at a passage end (where the pile has no reference). Plus COVERAGE wherever it was measured.
    if not d.get("collider_origin_cm") and (d.get("track_m") or 0) >= 17.0:
        verdict["top_masked"], d["_mask"] = mask_top(d)
        # The stage the rays were cast against, so the import can refuse a PASS judged against a stage that has since
        # changed (a border moved or removed): the verdict is bound to the stage bytes as well as the bake's.
        verdict["mask_stage"] = d.get("_mask_stage")
        verdict["stage_clear"], d["_clear"] = stage_clear(d)
    required = ["still", "hang", "site" if d.get("collider_origin_cm") else "pile"]
    if "coverage" in verdict:
        required.append("coverage")
    if "top_masked" in verdict:
        required.append("top_masked")
    if "stage_clear" in verdict:
        required.append("stage_clear")
    verdict["required"] = required
    verdict["ALL"] = all(verdict.get(k) is True for k in required)
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
    # MARGINS (the Conductor, 30 Sep): which criteria pass comfortably and which scrape. A marginal one shows up in
    # Rig's integration as a bad frame, so say so in advance.
    margins = {"hinge_m": round(hinge_y - 0.5 - worst["y_max_m"], 3), "boards_m": round(half - worst["abs_x_max_m"], 3),
               "floor_m": round(worst["z_min_m"] + 0.05, 3)}
    d["_site"] = {"hinge_y_m": hinge_y, "floor_half_width_m": half, **worst, "margins": margins,
                  "tight": [k for k, v in margins.items() if 0 <= v < 0.25]}
    return all(v > 0 for v in margins.values())


def drape_lines(name, d, ref_name, ref):
    verdict, ratios = judge_drape(d, ref)
    hp = d.get("hang_profile") or {}
    rows = hp.get("rows", {})
    lines = [f"### {name}: {'PASS' if verdict['ALL'] else 'FAIL'}  (still {verdict['still']}, hang {verdict['hang']}, "
             f"pile {verdict['pile']})",
             f"- rest `{d.get('rest')}`, fold wavelength {d.get('fold_wavelength_m')} m, hem guide {d.get('hem_guide_weight')} "
             f"x {d.get('hem_guide_rows')} rows, bending {d.get('bend')}, track {d.get('track_m')} m, drop {d.get('drop_m')} m",
             f"- **still limit for this site**: {d['_still_limit']}",
             f"- **still**: window max {d.get('still_window_max_mm')} mm/frame (mean {d.get('still_window_mean_mm')}); "
             f"under 2 mm from {d.get('settle_to_2mm_s')} s (reached: {d.get('settle_to_2mm_reached')})"]
    if rows:
        if "coverage_gap_per_side_m" in hp:
            lines.append(f"- **coverage**: narrowest hung row leaves {hp['coverage_gap_per_side_m']} m to each post face (at most "
                         f"{COVERAGE_GAP_MAX_M}); widest keeps {hp['post_clearance_per_side_m']} m clear (at least "
                         f"{POST_CLEARANCE_MIN_M}). The opening is {P01_OPENING_M} m, the same at all six portals.")
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
    if "_clear" in d:
        lines.append(f"- **stage clear** (cache vs the stage as built): {d['_clear']}")
    if "_mask" in d:
        lines.append(f"- **top masked** (stalls ray test): {d['_mask']}")
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
    v["required"] = ["still", "end_still", "hang"]
    v["ALL"] = all(v.get(k) is True for k in v["required"])            # fail closed: a missing profile FAILS
    lines = [f"### {name} (traveller): {'PASS' if v['ALL'] else 'FAIL'}  {v}",
             f"- start `{d.get('start')}`, hem guide {d.get('hem_guide_weight')}; still {still} mm/frame "
             f"(under 2 mm from {d.get('settle_to_2mm_s')} s); END still {end} mm/frame",
             f"- hang: flare {hp.get('flare_ratio')}, bulge {hp.get('bulge')}, per half "
             + "; ".join(f"side {h['side']}: " + ", ".join(f"{k} {r['folds']}/{r['mean_depth_m']}" for k, r in h['rows'].items())
                         for h in hp.get("halves", [])),
             f"- design: stack {d.get('design_stack_width_per_side_m')} m per side, clear opening {d.get('design_clear_opening_m')} m; "
             f"opening {d.get('open_frames', 0) / FPS:.0f} s"]
    if (d.get("settle_air_damping") or 1.0) != 1.0:
        # Say it plainly (the Conductor, 30 Sep): a still END here is DAMPED, not a natural settle. A real curtain's
        # stacks keep some residual life; if Gary wants them alive, TRAVELLER_SETTLE_AIR_DAMPING=1 is the knob.
        lines.append(f"- **END stillness is DAMPED**, not settled: air damping x{d['settle_air_damping']} from the end of the "
                     f"opening. Don't compare it with a real curtain's residual life. The knob is TRAVELLER_SETTLE_AIR_DAMPING.")
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
    # A NAMED override, not a looser number (30 Sep: Gary, having SEEN the piles, "all actually look usable as piles").
    # "id=who, when, what they saw" marks that bake's PILE criterion passed by a person's eye. It is recorded in
    # acceptance.json with the reason, and it never touches stillness or the hang.
    ap.add_argument("--pile-approved", action="append", default=[], metavar="ID=REASON")
    ap.add_argument("--mask-colliders", default="", help="path|option of the CURRENT built stage for the top-masked ray "
                    "test, when it is a different file or version from the one the bake simulated against")
    args = ap.parse_args()
    global MASK_COLLIDERS
    MASK_COLLIDERS = args.mask_colliders or None
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
            approvals = dict(a.split("=", 1) for a in args.pile_approved)
            if i in approvals and v.get("pile") is not True:
                v["pile"] = True
                v["pile_override"] = approvals[i]
                v["ALL"] = all(v.get(k) is True for k in v["required"])      # the same fail-closed rule
                ls.append(f"- **pile PASSED BY RECORDED OVERRIDE** (the reason says what was and was not seen): {approvals[i]}")
                ls[0] = ls[0].replace(": FAIL", ": PASS" if v["ALL"] else ": FAIL").replace("pile False", "pile True (override)").replace("pile None", "pile True (override)")
        body += ls + [""]
        # BIND THE VERDICT TO THE BYTES: the import refuses unless the bake JSON and .abc still hash to what was judged,
        # so re-using a bake id can never import an untested replacement under a stale pass.
        v["artifacts"] = {name: sha256_file(OUT / name) for name in (f"{i}.json", f"{i}.abc") if (OUT / name).exists()}
        verdicts[i] = v
        summary.append(f"| {i} | {'PASS' if v['ALL'] else 'FAIL'} | "
                       + ", ".join(f"{k}={val}" for k, val in v.items()
                                   if k not in ("ALL", "pile_override", "artifacts", "required", "mask_stage")) + " |")
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
