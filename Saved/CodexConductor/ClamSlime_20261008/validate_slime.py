"""OFFLINE geometric validation of SK_PearlClam_Slime (numpy + scipy; no Blender, no Unreal).

    python validate_slime.py                 # full: the design file + the Blender build dumps
    python validate_slime.py --design-only   # the design file only (build/slime_design.npz)
    python validate_slime.py --controls      # 4 negative controls, each must produce its named failure

Writes validate_slime_report.json and prints VALIDATE_SLIME_OK|... or VALIDATE_SLIME_FAILED|<named failures>.

Every number is [meas] against the shells read from the export FBX files (clam_geo.py) with exact point-to-triangle
distances and a ray-parity inside test (surface_dist.Solid; shells are closed meshes [meas]).  The posed slime is
linear-blend-skinned in numpy from the design's weights and bone matrices (the same arrays the Blender build keys),
and in full mode that numpy skinning is compared with Blender's own evaluation and with the RE-IMPORTED FBX.

LIGAMENT at every 2.5 deg from 0 to 55 (the design relaxes walls at every 5 deg, so half the tested angles are unseen):
  seam_lower / seam_upper  distance of each attachment-face vertex (w = 0 / w = 1) to the bottom / the lid at that
                           angle.  Target < 0.5 cm along the whole seam (the band never hovers off a shell).
  depth_bottom / depth_lid deepest ligament vertex INSIDE that shell (ray parity).  Target <= 0.5 cm: nothing
                           can come out through the far side of a wall thicker than 0.5 cm.  Also reported excluding
                           vertices that sit inside BOTH shells (the closed shells overlap each other at the seam).
  outside                  ligament vertices outside both shells (the visible part) and the slot it spans.
STRANDS (anim frames: every 2nd frame to 420, every 120th after, every break frame and the frame before it):
  depth per obstacle (bottom, lid at the frame's angle, mantle, live pearl) of every strand vertex except the
  meniscus FOOT (rings within FOOT_S of the anchor + the anchor cap: buried in the lip by design; reported apart).
  Neck radius on the frame before each break; tip separation 0.5 s after; upper-tip height over time.
ANIM: lid angle per frame vs clam_open.plan_keys (exact at every 6th frame of the opening, linear between).
BUILD (full mode): Blender rig == numpy LBS; FBX re-import == rig; re-imported lid angle at EVERY frame == plan.
"""
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/") + "/"
sys.path.insert(0, HERE)
import slime_design as d         # noqa: E402

BUILD_NPZ = HERE + "build/slime_build.npz"
BUILD_JSON = HERE + "build/slime_build.json"
REPORT = HERE + "validate_slime_report.json"
TARGET_SEAM = 0.5
TARGET_DEPTH = 0.5
ANGLES = tuple(2.5 * k for k in range(23))      # 0, 2.5, ... 55: twice as fine as the design's relaxation angles


def stats(a):
    a = np.asarray(a, float)
    if not len(a):
        return {"n": 0}
    return {"max": round(float(a.max()), 3), "p95": round(float(np.percentile(a, 95)), 3),
            "median": round(float(np.median(a)), 3), "n": int(len(a))}


def skin(D, frame_poses):
    """numpy LBS of the design vertices with the frame's bone pose matrices."""
    W, rest, V = D["weights"], D["rest"], D["verts"]
    vh = np.hstack([V, np.ones((len(V), 1))])
    out = np.zeros((len(V), 3))
    for j in range(W.shape[1]):
        m = W[:, j] > 0
        if m.any():
            M = frame_poses[j] @ np.linalg.inv(rest[j])
            out[m] += W[m, j, None] * (vh[m] @ M.T)[:, :3]
    return out


def lig_poses(D, deg):
    """Bone poses with only the hinge set (strand bones at rest): the ligament depends on the angle alone."""
    pm = d.pose_mats(deg, {})
    return np.array([pm[b] if b in pm else D["rest"][j] for j, b in enumerate(D["bones"])])


def main(design_only=False, mutate=None, report=REPORT):
    t0 = time.time()
    fails = []
    D = d.load_design()
    if mutate is not None:
        mutate(D)
    sol = d.solids_map()
    B, to_b = sol["bottom"]
    L, to_l = sol["lid"]
    rep = {"targets_cm": {"seam": TARGET_SEAM, "depth": TARGET_DEPTH}, "design": d.DESIGN_NPZ}

    # sanity of the distance + inside machinery (positive / negative controls)
    probes = np.array([[0.0, 0.0, -3.0], [0.0, 0.0, 30.0], [0.0, 60.0, 15.0], [0.0, -47.0, 20.0]])
    ins = B.inside(probes)
    rep["inside_controls_bottom"] = {"below": bool(ins[0]), "cavity": bool(ins[1]), "behind": bool(ins[2]),
                                     "front_wall": bool(ins[3])}
    if list(ins) != [False, False, False, True]:
        fails.append("INSIDE_TEST_CONTROLS|%s" % list(ins))
    from surface_dist import closest_on_tris
    rng = np.random.default_rng(7)
    q = B.v[rng.choice(len(B.v), 5)] + rng.normal(0, 1.0, (5, 3))
    ud, _s, _c = B.dist(q)
    brute = [float(np.linalg.norm(closest_on_tris(p, B.v[B.t[:, 0]], B.v[B.t[:, 1]], B.v[B.t[:, 2]]) - p,
                                  axis=1).min()) for p in q]
    rep["closest_vs_bruteforce_cm"] = float(np.abs(np.array(brute) - ud).max())
    if rep["closest_vs_bruteforce_cm"] > 1e-9:
        fails.append("CLOSEST_INEXACT|%s" % rep["closest_vs_bruteforce_cm"])

    # ------------------------------------------------------------------ anim curve
    planned, _allk, roll = d.lid_curve()
    ang = D["angles"]
    pk = dict(planned)
    six = list(range(0, d.OPEN_END - d.OPEN_START + 1, 6))
    bad6 = [i for i in six if pk.get(d.OPEN_START + i) is None or -ang[i] != pk[d.OPEN_START + i]]
    lin = max(abs(-ang[i] - roll(d.OPEN_START + i)) for i in range(len(ang)))
    rep["anim"] = {"frames": int(len(ang)), "every_6th_exactly_plan_keys": not bad6, "checked_6th": len(six),
                   "max_dev_from_live_linear_curve_deg": lin,
                   "angle_at_frame": {str(i): round(float(ang[i]), 4) for i in (0, 6, 75, 150, 225, 294, 300, len(ang) - 1)}}
    lid_j = D["bones"].index("lid")
    pose_angle = [-np.degrees(np.arctan2(D["poses"][i, lid_j, 2, 1], D["poses"][i, lid_j, 1, 1])) for i in range(len(ang))]
    rep["anim"]["lid_bone_pose_vs_angle_max_deg"] = float(np.abs(np.array(pose_angle) - ang).max())
    if bad6 or lin > 1e-12 or abs(ang[300] - 55.0) > 1e-12 or abs(ang[-1] - 55.0) > 1e-12 or \
            rep["anim"]["lid_bone_pose_vs_angle_max_deg"] > 1e-9 or len(ang) != d.ANIM_LAST + 1:
        fails.append("ANIM_CURVE|bad6=%s|lin=%s" % (bad6[:3], lin))

    # ------------------------------------------------------------------ ligament
    lig = D["part"] == 0
    lw = D["lig_w"]
    lower, upper = lig & (lw == 0.0), lig & (lw == 1.0)
    info = json.load(open(d.DESIGN_JSON, encoding="utf-8"))
    rep["ligament"] = {"x_span_cm": info["ligament"]["x_span_cm"], "stations": info["ligament"]["stations"],
                       "vertices": int(lig.sum()), "angles": {}}
    for deg in ANGLES:
        P = skin(D, lig_poses(D, deg))
        ul, _sl, _ = B.dist(P[lower])
        uu, _su, _ = L.dist(to_l(P[upper], deg))
        PL = P[lig]                                   # every ligament vertex, end-cap centres included
        db, dl = B.depth(PL), L.depth(to_l(PL, deg))
        both = (db > 0) & (dl > 0)
        seam_b = P[lower]
        slot = np.linalg.norm(P[upper] - seam_b, axis=1) if lower.sum() == upper.sum() else np.array([np.nan])
        row = {"seam_lower_to_bottom": stats(ul), "seam_upper_to_lid": stats(uu),
               "depth_bottom_cm": round(float(db.max()), 3), "depth_lid_cm": round(float(dl.max()), 3),
               "depth_bottom_excl_both_cm": round(float(db[~both].max()), 3),
               "depth_lid_excl_both_cm": round(float(dl[~both].max()), 3),
               "vertices_inside_both_shells": int(both.sum()),
               "vertices_outside_both": int(((db == 0) & (dl == 0)).sum()),
               "attachment_face_pair_distance_cm": stats(slot)}
        rep["ligament"]["angles"]["%g" % deg] = row
        for k, lim, tag in (("seam_lower_to_bottom", TARGET_SEAM, "SEAM_LOWER"), ("seam_upper_to_lid", TARGET_SEAM, "SEAM_UPPER")):
            if row[k]["max"] >= lim:
                fails.append("%s|%g|%s" % (tag, deg, row[k]["max"]))
        for k, tag in (("depth_bottom_excl_both_cm", "DEPTH_BOTTOM"), ("depth_lid_excl_both_cm", "DEPTH_LID")):
            if row[k] > TARGET_DEPTH:
                fails.append("%s|%g|%s" % (tag, deg, row[k]))
        print("ligament %4.1f deg %s" % (deg, json.dumps(row)))

    # ------------------------------------------------------------------ strands
    tag = D["strand_tag"]
    foot = D["foot"].astype(bool)
    strand = D["part"] == 1
    body = strand & ~foot
    which = tag[:, 0]
    bf = [int(x) for x in D["break_frames"]]
    sample = sorted(set(list(range(0, 420, 2)) + list(range(420, len(ang), 120)) + [len(ang) - 1] +
                    [b - 1 for b in bf] + bf))
    nst = len(d.STRANDS)
    depth = {k: np.zeros(nst) for k in sol}
    where = {k: [None] * nst for k in sol}
    foot_depth = {k: np.zeros(nst) for k in ("bottom", "lid")}
    for i in sample:
        P = skin(D, D["poses"][i])
        for name, (S, tl) in sol.items():
            dep = S.depth(tl(P[body], ang[i]))
            wb = which[body]
            for si in range(nst):
                v = float(dep[wb == si].max())
                if v > depth[name][si]:
                    depth[name][si], where[name][si] = v, {"frame": i, "deg": round(float(ang[i]), 2)}
            if name in foot_depth:
                fd = S.depth(tl(P[strand & foot], ang[i]))
                wf = which[strand & foot]
                for si in range(nst):
                    foot_depth[name][si] = max(foot_depth[name][si], float(fd[wf == si].max()))
    necks, seps, lengths, radius, tipz = [], [], [], [], []
    bj = {b: j for j, b in enumerate(D["bones"])}
    for si in range(nst):
        b = bf[si]

        def rad(i, bone):
            return float(np.linalg.norm(D["poses"][i, bj[bone], :3, 0])) * d.STRAND_REST_RADIUS

        def pos(i, bone):
            return D["poses"][i, bj[bone], :3, 3]
        last = d.STRAND_STATIONS - 1
        necks.append(round(min(rad(b - 1, d.bone_name(si, h, last - 1)) for h in ("lo", "up")), 4))
        k = min(len(ang) - 1, b + d.FPS // 2)
        seps.append(round(float(np.linalg.norm(pos(k, d.bone_name(si, "up", last)) - pos(k, d.bone_name(si, "lo", last)))), 2))
        lengths.append(round(float(np.linalg.norm(pos(b - 1, d.bone_name(si, "up", 0)) - pos(b - 1, d.bone_name(si, "lo", 0)))), 2))
        # body radius where the strand is drawn out but the neck has not formed yet: the frame at HALF its break angle
        fh = int(np.nonzero(ang >= 0.5 * d.STRANDS[si]["break_deg"])[0][0])
        radius.append([round(min(rad(fh, d.bone_name(si, h, kk)) for h in ("lo", "up") for kk in (1, 2, 3)), 3),
                       round(max(rad(fh, d.bone_name(si, h, kk)) for h in ("lo", "up") for kk in (0, 1, 2, 3)), 3)])
        tipz.append([round(float(pos(j, d.bone_name(si, "up", last))[2]), 2)
                     for j in (b, min(len(ang) - 1, b + 12), min(len(ang) - 1, b + 48), len(ang) - 1)])
    rep["strands"] = {
        "x_cm": [s["x"] for s in d.STRANDS], "break_deg_design": [s["break_deg"] for s in d.STRANDS],
        "break_frame_anim": bf, "break_frame_scene": [d.OPEN_START + b for b in bf],
        "angle_at_break_frame_deg": [round(float(ang[b]), 3) for b in bf],
        "depth_cm_excl_foot": {k: [round(float(x), 3) for x in v] for k, v in depth.items()},
        "depth_where": where, "foot_depth_cm (buried by design)": {k: [round(float(x), 3) for x in v] for k, v in foot_depth.items()},
        "neck_radius_frame_before_break_cm": necks, "tip_separation_0p5s_after_break_cm": seps,
        "length_frame_before_break_cm": lengths, "body_radius_at_half_break_angle_min_max_cm": radius,
        "upper_tip_z_at_break_+0.5s_+2s_end": tipz, "sampled_frames": len(sample),
        "anchors_and_droops": info["anchors"]}
    for name in depth:
        for si in range(nst):
            if depth[name][si] > TARGET_DEPTH:
                fails.append("STRAND_DEPTH|%s|s%d|%.3f" % (name, si, depth[name][si]))
    if any(n > 0.1 for n in necks):
        fails.append("NECK_NOT_THIN|%s" % necks)
    if any(s < 2.0 for s in seps):
        fails.append("HALVES_NOT_PARTED|%s" % seps)
    if any(not (8.0 - 1e-9 <= ang[b] <= 30.0 + 0.5) for b in bf):
        fails.append("BREAK_ANGLES_OUT_OF_8_30|%s" % [float(ang[b]) for b in bf])
    if any(r[0] < 0.3 - 1e-6 or r[1] > 1.2 + 1e-6 for r in radius):
        fails.append("BODY_RADIUS_OUT_OF_0p3_1p2|%s" % radius)

    # ------------------------------------------------------------------ build cross-checks
    if not design_only:
        if not os.path.exists(BUILD_NPZ):
            fails.append("NO_BUILD|%s" % BUILD_NPZ)
        else:
            z = np.load(BUILD_NPZ)
            bjs = json.load(open(BUILD_JSON, encoding="utf-8"))
            c = {"rest_verts_vs_design_cm": float(np.abs(z["rest_cm"] - D["verts"]).max())}
            for key, label in (("rig_cm", "blender_rig_vs_numpy_lbs_cm"), ("reimport_cm", "fbx_reimport_vs_numpy_lbs_cm")):
                c[label] = max(float(np.abs(z[key][j] - skin(D, D["poses"][int(f)])).max())
                               for j, f in enumerate(z["frames"]))
            lid_re = z["reimport_lid_deg"]
            c["reimport_lid_frames"] = int(len(lid_re))
            c["reimport_lid_vs_plan_max_deg"] = float(np.abs(lid_re - ang).max()) if len(lid_re) == len(ang) else None
            c["blender_checks_all_true"] = all(bool(v) for v in bjs["checks"].values())
            c["sample_frames"] = [int(x) for x in z["frames"]]
            rep["build"] = c
            if c["rest_verts_vs_design_cm"] > 1e-4:
                fails.append("BUILD_REST|%s" % c["rest_verts_vs_design_cm"])
            if c["blender_rig_vs_numpy_lbs_cm"] > 0.01:
                fails.append("SKIN_CROSSCHECK|%s" % c["blender_rig_vs_numpy_lbs_cm"])
            if c["fbx_reimport_vs_numpy_lbs_cm"] > 0.02:
                fails.append("FBX_ROUNDTRIP|%s" % c["fbx_reimport_vs_numpy_lbs_cm"])
            if c["reimport_lid_vs_plan_max_deg"] is None or c["reimport_lid_vs_plan_max_deg"] > 1e-3:
                fails.append("FBX_LID_CURVE|%s" % c["reimport_lid_vs_plan_max_deg"])
            if not c["blender_checks_all_true"]:
                fails.append("BLENDER_CHECKS|%s" % [k for k, v in bjs["checks"].items() if not v])
    rep["failures"] = fails
    rep["seconds"] = round(time.time() - t0, 1)
    with open(report, "w", encoding="utf-8") as h:
        json.dump(rep, h, indent=1, default=str)
    if mutate is not None:
        return fails
    Lg = rep["ligament"]["angles"]
    summary = "seam_max=%s|lig_depth_max=%s (excl both-shell overlap %s)|strand_depth_max=%s|breaks_deg=%s" % (
        max(max(r["seam_lower_to_bottom"]["max"], r["seam_upper_to_lid"]["max"]) for r in Lg.values()),
        max(max(r["depth_bottom_cm"], r["depth_lid_cm"]) for r in Lg.values()),
        max(max(r["depth_bottom_excl_both_cm"], r["depth_lid_excl_both_cm"]) for r in Lg.values()),
        round(max(float(v.max()) for v in depth.values()), 3), rep["strands"]["angle_at_break_frame_deg"])
    if fails:
        print("VALIDATE_SLIME_FAILED|%s|%s" % (fails, summary))
        return 1
    print("VALIDATE_SLIME_OK|mode=%s|%s|report=%s" % ("design" if design_only else "full", summary, REPORT))
    return 0


def _m_upper_to_root(D):
    """- control: the lid attachment face loses its lid weight (skinned to root) -> must FAIL SEAM_UPPER."""
    j0, j1 = D["bones"].index("root"), D["bones"].index("lid")
    m = (D["part"] == 0) & (D["lig_w"] == 1.0)
    D["weights"][m, j1], D["weights"][m, j0] = 0.0, 1.0


def _m_sink(D):
    """- control: the ligament pushed 2 cm down into the bottom -> must FAIL DEPTH_BOTTOM."""
    D["verts"][D["part"] == 0, 2] -= 2.0


def _m_curve(D):
    """- control: the lid angle at anim frame 150 off by 0.5 deg -> must FAIL ANIM_CURVE."""
    D["angles"][150] += 0.5


def _m_strand_into_bottom(D):
    """- control: every strand bone pose dropped 3 cm -> must FAIL STRAND_DEPTH (bottom)."""
    for j, b in enumerate(D["bones"]):
        if b.startswith("s"):
            D["poses"][:, j, 2, 3] -= 3.0


CONTROLS = [("UPPER_FACE_ON_ROOT", _m_upper_to_root, "SEAM_UPPER|"), ("LIGAMENT_SUNK_2CM", _m_sink, "DEPTH_BOTTOM|"),
            ("CURVE_OFF_0P5DEG", _m_curve, "ANIM_CURVE|"), ("STRANDS_DROPPED_3CM", _m_strand_into_bottom,
                                                              "STRAND_DEPTH|bottom")]


def controls():
    """Each negative control must produce its named failure (a verifier that cannot fail proves nothing)."""
    out, ok = {}, True
    for name, fn, want in CONTROLS:
        f = main(design_only=True, mutate=fn, report=HERE + "validate_slime_control_%s.json" % name)
        hit = any(x.startswith(want) for x in f)
        out[name] = {"expected": want, "caught": hit, "failures": f[:4]}
        ok &= hit
        print("CONTROL %s caught=%s %s" % (name, hit, f[:2]))
    with open(HERE + "validate_slime_controls.json", "w", encoding="utf-8") as h:
        json.dump(out, h, indent=1)
    print("VALIDATE_SLIME_CONTROLS_%s|%d/%d caught" % ("OK" if ok else "FAILED", sum(v["caught"] for v in out.values()),
                                                       len(out)))
    return 0 if ok else 1


if __name__ == "__main__":
    if "--controls" in sys.argv:
        sys.exit(controls())
    sys.exit(main(design_only="--design-only" in sys.argv))
