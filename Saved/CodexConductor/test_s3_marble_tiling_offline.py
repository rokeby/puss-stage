"""Offline harness for s3_marble_tiling_material.py + s3_marble_tiling_apply.py (no Unreal).

Every check has a NEGATIVE CONTROL that must fail; a harness whose controls pass proves nothing.
Synthetic geometry mirrors the S3 liners: base cube scale (60, 0.01, 6.05) (hp_marble_probe.json), z -5..600,
four upper tiles per side stacked to 3000 with alternate tiles mirrored in Z (s3_backwall_marble.py plan_tiles).
Run: python Saved/CodexConductor/test_s3_marble_tiling_offline.py   -> exit 0 and S3_MARBLE_TILING_OFFLINE_OK
"""
import copy
import importlib.util
import json
import math
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name):
    spec = importlib.util.spec_from_file_location("_t_" + name, os.path.join(HERE, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M = load("s3_marble_tiling_material")
A = load("s3_marble_tiling_apply")
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append({"check": name, "pass": bool(cond), "detail": str(detail)[:300]})


def raises(fn, *a, contains=None):
    try:
        fn(*a)
    except Exception as exc:  # noqa: BLE001
        return contains is None or contains in str(exc)
    return False


# ------------------------------------------------------------------------------------------- synthetic S3 walls
X0, Y_IN = 3500.0, 995.0
BASE_H, TOP = 605.0, 3000.0


def make_rows(mirror=True, alt_decomp=False):
    rows = []
    for side, y in (("L", -Y_IN), ("R", Y_IN)):
        rows.append({"label": A.LINERS[side], "tags": [], "class": "StaticMeshActor",
                     "object_path": "/W.PersistentLevel.%s0" % side, "mesh": A.CUBE, "num_slots": 1,
                     "materials": [M.OLD_MI], "overrides": [M.OLD_MI], "parent_label": "S3 Hangar Wall",
                     "world": {"location": [X0, y, -5.0 + BASE_H / 2], "rotation": [0.0, 0.0, 0.0],
                               "scale": [60.0, 0.01, BASE_H / 100.0]}})
        span = TOP - (BASE_H - 5.0)
        th = span / 4
        for k in range(1, 5):
            sz = th / 100.0 * (-1.0 if (mirror and k % 2 == 1) else 1.0)
            world = {"location": [X0, y, BASE_H - 5.0 + (k - 0.5) * th], "rotation": [0.0, 0.0, 0.0],
                     "scale": [60.0, 0.01, sz]}
            if alt_decomp and sz < 0:   # same matrix: roll 180 with Y negated instead of Z
                world = {"location": world["location"], "rotation": [180.0, 0.0, 0.0],
                         "scale": [60.0, -0.01, -sz]}
            rows.append({"label": "%s Upper %d" % (A.LINERS[side], k), "tags": [A.TILE_TAG],
                         "class": "StaticMeshActor", "object_path": "/W.PersistentLevel.%s%d" % (side, k),
                         "mesh": A.CUBE, "num_slots": 1, "materials": [M.OLD_MI], "overrides": [M.OLD_MI],
                         "parent_label": "S3 Hangar Wall", "world": world})
    return rows


def matvec(m, v):
    return [sum(m[i][j] * v[j] for j in range(3)) for i in range(3)]


def rot_pitch(deg):
    """Rotation about world Y (the box 'rotates up as one thing', hinged at the mouth)."""
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]]


IDENT = [[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]]


def eval_point(row, local_cm_u, local_cm_v, params, hangar=(IDENT, [0.0, 0.0, 0.0]), face_sign=1.0):
    """Material inputs for a point on the inner (+/-Y) face of `row`, at offsets (u, v) cm from its pivot along
    world X / Z in the LANDED pose, then moved rigidly by the hangar transform (R, t)."""
    R, t = hangar
    loc = row["world"]["location"]
    p_landed = [loc[0] + local_cm_u, loc[1], loc[2] + local_cm_v]
    au, av = M.local_axes_world(row["world"])
    p = [a + b for a, b in zip(matvec(R, p_landed), t)]
    op = [a + b for a, b in zip(matvec(R, loc), t)]
    n = matvec(R, [0.0, face_sign, 0.0])
    return M.coords_reference(p, n, [p[i] - op[i] for i in range(3)], matvec(R, au), matvec(R, av), params)


def mi_params(frame_vals=None, **over):
    p = {k: v[0] for k, v in M.SCALARS.items()}
    p.update(frame_vals or {})
    p.update(over)
    return p


def close(a, b, tol=1e-6):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


# ------------------------------------------------------------------------------------------------------ checks
def t_graph_spec():
    check("graph_spec_consistent", M.graph_spec_problems() == [], M.graph_spec_problems())
    saved = M.CODE_COORDS
    M.CODE_COORDS = saved.replace("pw.x += back * BackShift;", "").replace("43758.5453", "43758.0")
    probs = M.graph_spec_problems()
    M.CODE_COORDS = saved
    check("CONTROL_graph_spec_detects_unused_input_and_const_drift",
          any("INPUT_UNUSED|BackShift" in p for p in probs) and any("HLSL_CONST_DRIFT" in p for p in probs), probs)


def t_sampler():
    ok = (M.sampler_for("TextureCompressionSettings.TC_NORMALMAP", False) == "SAMPLERTYPE_NORMAL" and
          M.sampler_for("TC_DEFAULT", True) == "SAMPLERTYPE_COLOR" and
          M.sampler_for("TC_DEFAULT", False) == "SAMPLERTYPE_LINEAR_COLOR" and
          M.sampler_for("TC_GRAYSCALE", False) == "SAMPLERTYPE_LINEAR_GRAYSCALE" and
          M.sampler_for("TC_MASKS", False) == "SAMPLERTYPE_MASKS")
    check("sampler_mapping", ok)
    check("CONTROL_sampler_unknown_refuses", raises(M.sampler_for, "TC_HDR", False, contains="SAMPLER_UNMAPPED"))


def t_axes():
    x, y, z = M.rotator_axes([0, 0, 90])
    ok = close(x, [0, 1, 0]) and close(z, [0, 0, 1])
    x2, _, z2 = M.rotator_axes([0, 90, 0])
    ok = ok and close(x2, [0, 0, 1])
    worst = 0.0
    for rot in ([10, 20, 30], [-170, 45, 200], [180, 0, 0]):
        a = M.rotator_axes(rot)
        for i in range(3):
            for j in range(3):
                worst = max(worst, abs(M._dot(a[i], a[j]) - (1.0 if i == j else 0.0)))
    check("rotator_axes_known_and_orthonormal", ok and worst < 1e-9, worst)
    au1, av1 = M.local_axes_world({"rotation": [0, 0, 0], "scale": [60, 0.01, -6]})
    au2, av2 = M.local_axes_world({"rotation": [180, 0, 0], "scale": [60, -0.01, 6]})
    check("mirrored_decompositions_same_axes", close(au1, au2) and close(av1, av2), (au1, av1, au2, av2))
    au3, av3 = M.local_axes_world({"rotation": [0, 0, 0], "scale": [60, 0.01, 6]})
    check("CONTROL_mirror_flips_v_axis", not close(av1, av3), (av1, av3))


def t_targets():
    rows = make_rows()
    sel = A.select_targets(rows)
    check("select_10_targets", len(sel) == 10 and sum(r["role"] == "base" for r in sel) == 2, len(sel))
    check("CONTROL_nine_targets_refused",
          raises(A.select_targets, rows[:-1], contains="TARGET_COUNT"))
    extra = rows + [dict(rows[1], label="S3 Marble Inner Wall Left Upper 5", object_path="/W.x")]
    check("CONTROL_unexpected_tagged_refused", raises(A.select_targets, extra, contains="TAGGED_UNEXPECTED"))
    dup = rows + [dict(rows[0], object_path="/W.dup")]
    check("CONTROL_duplicate_base_refused", raises(A.select_targets, dup, contains="BASE_COUNT"))
    bad = copy.deepcopy(rows)
    bad[3]["mesh"] = "/Engine/BasicShapes/Plane"
    check("CONTROL_wrong_mesh_refused", raises(A.select_targets, bad, contains="MESH|"))


def t_plan():
    rows = A.select_targets(make_rows())
    plan, children = A.plan_assignment(rows, "world", "APPLY")
    check("plan_world_all_to_MI", all(p["to"] == M.MI for p in plan) and children == {}, len(plan))
    plan_o, ch = A.plan_assignment(rows, "object", "APPLY")
    check("plan_object_10_children", len(ch) == 10 and len({p["to"] for p in plan_o}) == 10, sorted(ch))
    foreign = copy.deepcopy(rows)
    foreign[4]["materials"] = ["/Game/Other/MI_X"]
    check("CONTROL_foreign_material_refused", raises(A.plan_assignment, foreign, "world", "APPLY",
                                                     contains="NOT_ON_OLD_MI"))
    done = copy.deepcopy(rows)
    for r in done:
        r["materials"] = [M.MI]
    check("CONTROL_already_applied_refused", raises(A.plan_assignment, done, "world", "APPLY",
                                                    contains="ALREADY_ON_NEW_MATERIAL"))
    check("dry_does_not_refuse_foreign", len(A.plan_assignment(foreign, "world", "DRY")[0]) == 10)


def t_frame_params():
    rows = A.select_targets(make_rows())
    fp = M.object_frame_params(rows)
    mir = [r["label"] for r in rows if r["role"] == "upper" and r["world"]["scale"][2] < 0]
    check("mirrored_tiles_get_vsign_minus", all(fp[l]["VSign"] == -1.0 for l in mir) and
          all(fp[r["label"]]["VSign"] == 1.0 for r in rows if r["label"] not in mir), mir)
    rows_alt = A.select_targets(make_rows(alt_decomp=True))
    fp_alt = M.object_frame_params(rows_alt)
    check("frame_params_independent_of_decomposition",
          all(close([fp[k][p] for p in M.FRAME_PARAMS], [fp_alt[k][p] for p in M.FRAME_PARAMS]) for k in fp))
    off = copy.deepcopy(rows)
    off[2]["world"]["location"][1] += 3.0
    check("CONTROL_noncoplanar_refused", raises(M.object_frame_params, off, contains="NOT_COPLANAR"))
    tilt = copy.deepcopy(rows)
    tilt[2]["world"]["rotation"] = [0.0, 0.0, 5.0]
    check("CONTROL_nonparallel_refused", raises(M.object_frame_params, tilt, contains="AXES_NOT_PARALLEL"))


def seam_mismatch(rows, frame_params, frame, hangar=(IDENT, [0.0, 0.0, 0.0])):
    """Max |uvA difference| across every liner/tile and tile/tile seam, sampled along the wall."""
    worst = 0.0
    for side in "LR":
        stack = sorted([r for r in rows if r["side"] == side], key=lambda r: r["world"]["location"][2])
        for lo, hi in zip(stack, stack[1:]):
            seam_z = (lo["world"]["location"][2] + abs(lo["world"]["scale"][2]) * 50.0)
            for u in (-2900.0, -1234.5, 0.0, 777.7, 2950.0):
                pl = mi_params(frame_params.get(lo["label"]), ObjectRelative=1.0 if frame == "object" else 0.0)
                ph = mi_params(frame_params.get(hi["label"]), ObjectRelative=1.0 if frame == "object" else 0.0)
                fs = 1.0 if side == "L" else -1.0
                a = eval_point(lo, u, seam_z - lo["world"]["location"][2], pl, hangar, fs)
                b = eval_point(hi, u, seam_z - hi["world"]["location"][2], ph, hangar, fs)
                worst = max(worst, max(abs(x - y) for x, y in zip(a[0] + a[1], b[0] + b[1])), abs(a[2] - b[2]))
    return worst


def t_continuity_and_rigidity():
    rows = A.select_targets(make_rows())
    fp = M.object_frame_params(rows)
    check("world_frame_seams_continuous_landed", seam_mismatch(rows, {}, "world") < 1e-6,
          seam_mismatch(rows, {}, "world"))
    check("object_frame_seams_continuous_landed", seam_mismatch(rows, fp, "object") < 1e-6,
          seam_mismatch(rows, fp, "object"))
    broken = copy.deepcopy(fp)
    for k, v in broken.items():
        v["VSign"] = 1.0
    check("CONTROL_object_frame_without_vsign_breaks_seams", seam_mismatch(rows, broken, "object") > 1e-3,
          seam_mismatch(rows, broken, "object"))
    mid = (rot_pitch(-60.0), [0.0, 0.0, -1800.0])          # a pose half-way through the rise
    check("object_frame_seams_continuous_mid_rise", seam_mismatch(rows, fp, "object", mid) < 1e-6,
          seam_mismatch(rows, fp, "object", mid))
    # rigidity: the same material point (e.g. under a hand print) keeps its uv while the box moves
    base = rows[0]
    po = mi_params(fp[base["label"]])
    pw = mi_params({}, ObjectRelative=0.0)
    still_o = eval_point(base, 1200.0, 100.0, po)
    moved_o = eval_point(base, 1200.0, 100.0, po, mid)
    check("object_frame_rigid_through_rise", close(still_o[0] + still_o[1], moved_o[0] + moved_o[1], 1e-6),
          (still_o, moved_o))
    still_w = eval_point(base, 1200.0, 100.0, pw, face_sign=1.0)
    moved_w = eval_point(base, 1200.0, 100.0, pw, mid, face_sign=1.0)
    swim_cm = max(abs(a - b) for a, b in zip(still_w[0], moved_w[0])) * M.SCALARS["RepeatCm"][0]
    check("MEASURED_world_frame_swims_during_rise(control: detector sees motion)", swim_cm > 50.0,
          "uvA moves %.0f cm-equivalent at a mid-rise pose" % swim_cm)
    RESULTS[-1]["swim_cm"] = round(swim_cm, 1)


def t_tiling_and_breakup():
    rows = A.select_targets(make_rows())
    base = rows[0]
    p = mi_params({}, ObjectRelative=0.0)
    a = eval_point(base, 100.0, 50.0, p)[0]
    b = eval_point(base, 100.0 + 150.0, 50.0, p)[0]
    check("repeat_150cm_is_one_uv", abs((b[0] - a[0]) - 1.0) < 1e-9 and abs(b[1] - a[1]) < 1e-9, (a, b))
    p3 = mi_params({}, ObjectRelative=0.0, RepeatCm=300.0)
    c = eval_point(base, 100.0, 50.0, p3)[0]
    d = eval_point(base, 250.0, 50.0, p3)[0]
    check("CONTROL_repeat_param_changes_period", abs((d[0] - c[0]) - 0.5) < 1e-9, (c, d))
    aniso = (abs(eval_point(base, 0, 150.0, p)[0][1] - eval_point(base, 0, 0, p)[0][1]),
             abs(eval_point(base, 150.0, 0, p)[0][0] - eval_point(base, 0, 0, p)[0][0]))
    check("isotropic_cm_per_uv (old atlas was ~10:1)", abs(aniso[0] - aniso[1]) < 1e-9, aniso)
    blends = [eval_point(base, u, v, p)[2] for u in range(-2900, 2901, 97) for v in range(-300, 301, 61)]
    check("breakup_blend_in_range_and_varies", min(blends) >= 0.0 and max(blends) <= 1.0 and
          statistics.pstdev(blends) > 0.15, (min(blends), max(blends), statistics.pstdev(blends)))
    step = max(abs(eval_point(base, u, 0, p)[2] - eval_point(base, u + 1.0, 0, p)[2]) for u in range(-2900, 2900, 53))
    check("breakup_blend_smooth_per_cm", step < 0.05, step)
    # continuity across noise cell 0 and the 289-cell wrap (wrapping before the +1 corner tore it; found 6 Oct)
    ncm = M.SCALARS["BreakupNoiseCm"][0]
    po = mi_params({"ObjectRelative": 1.0, "USign": 1.0, "VSign": 1.0, "UOffsetCm": 0.0, "VOffsetCm": 0.0})
    jumps = []
    for u0 in (0.0, 289.0 * ncm, -289.0 * ncm, 289.0 * ncm / 2.03):
        for v0 in (0.0, 289.0 * ncm):
            vals = [eval_point(base, u0 + du, v0 - base["world"]["location"][2] + 0.0, po)[2]
                    for du in (-0.02, -0.01, 0.0, 0.01, 0.02)]
            jumps.append(max(abs(a - b) for a, b in zip(vals, vals[1:])))
    check("breakup_noise_continuous_at_cell0_and_wrap", max(jumps) < 1e-3, max(jumps))
    p0 = mi_params({}, ObjectRelative=0.0, BreakupAmount=0.0)
    check("CONTROL_breakup_amount_zero_is_single_sample",
          max(eval_point(base, u, 0, p0)[2] for u in range(-2900, 2900, 53)) == 0.0)
    left = eval_point(rows[0], 500.0, 100.0, p, face_sign=1.0)[0]
    right = eval_point(rows[5] if rows[5]["side"] == "R" else rows[1], 500.0, 100.0, p, face_sign=-1.0)[0]
    check("facing_walls_not_mirror_twins (BackFaceShiftCm)", not close(left, right, 1e-3), (left, right))


def t_noise_wrap_control():
    """Rebuild coords_reference with the 6 Oct bug (wrap the lattice BEFORE adding the +1 corner) and require the
    continuity checks to catch it."""
    import re
    import types
    src = open(os.path.join(HERE, "s3_marble_tiling_material.py"), encoding="utf-8").read()
    bug = re.sub(r"i1 = \[i0\[0\] \+ 1\.0, i0\[1\] \+ 1\.0\]\n(\s+)i0 = (\[v - 289.*?\n)\s+i1 = \[v - 289.*?\n",
                 lambda m: "i0 = " + m.group(2) + m.group(1) + "i1 = [i0[0] + 1.0, i0[1] + 1.0]\n", src)
    mod = types.ModuleType("_buggy_noise")
    exec(compile(bug, "_buggy_noise", "exec"), mod.__dict__)
    good, n0 = M.coords_reference, len(RESULTS)
    M.coords_reference = mod.coords_reference
    try:
        t_tiling_and_breakup()
        t_continuity_and_rigidity()
    finally:
        M.coords_reference = good
    caught = {r["check"] for r in RESULTS[n0:] if not r["pass"]}
    del RESULTS[n0:]
    check("CONTROL_buggy_noise_wrap_is_caught", bug != src and "breakup_noise_continuous_at_cell0_and_wrap" in caught,
          sorted(caught))


def t_mode_and_census():
    check("dry_needs_no_confirm", A.check_mode({"mode": "DRY"}, False)[0] == "DRY")
    check("verify_needs_no_confirm", A.check_mode({"mode": "VERIFY"}, True)[0] == "VERIFY")
    check("apply_with_confirm", A.check_mode({"mode": "APPLY", "confirm": "APPLY S3MARBLE"}, False)[0] == "APPLY")
    check("CONTROL_apply_without_confirm", raises(A.check_mode, {"mode": "APPLY"}, False, contains="CONFIRM"))
    check("CONTROL_build_wrong_word", raises(A.check_mode, {"mode": "BUILD", "confirm": "BUILD MARBLE"}, False,
                                             contains="CONFIRM"))
    check("CONTROL_apply_twice", raises(A.check_mode, {"mode": "APPLY", "confirm": "APPLY S3MARBLE"}, True,
                                        contains="ALREADY_APPLIED"))
    check("CONTROL_revert_without_record", raises(A.check_mode, {"mode": "REVERT", "confirm": "REVERT S3MARBLE"},
                                                  False, contains="NO_RECORD"))
    check("CONTROL_bad_frame", raises(A.check_mode, {"mode": "DRY", "frame": "uv"}, False, contains="FRAME"))
    check("CONTROL_custom_source_needs_textures",
          raises(A.check_mode, {"mode": "DRY", "source": "custom"}, False, contains="TEXTURES_MISSING"))
    created = [M.MASTER, M.MI]
    check("census_apply_level_plus_created", A.census_ok({"maps": [A.WORLD], "content": list(reversed(created))},
                                                         "APPLY", created))
    check("census_apply_level_only_when_prebuilt", A.census_ok({"maps": [A.WORLD], "content": []}, "APPLY", []))
    check("CONTROL_census_foreign_package", not A.census_ok({"maps": [A.WORLD], "content": created + ["/Game/X"]},
                                                            "APPLY", created))
    check("CONTROL_census_build_must_not_dirty_level", not A.census_ok({"maps": [A.WORLD], "content": created},
                                                                       "BUILD", created))
    check("CONTROL_census_apply_missing_level", not A.census_ok({"maps": [], "content": []}, "APPLY", []))


def t_hp():
    hp = [{"object_path": "/W.HP%d" % i, "parent_label": "S3 Marble Inner Wall Left", "label": "HP %d" % i,
           "location": [3000.0 + i, -994.0, 120.0 + i % 7], "rotation": [0.0, 0.0, 90.0], "scale": [1.0, 1.0, 1.0]}
          for i in range(A.HP_EXPECTED)]
    same = list(reversed(copy.deepcopy(hp)))
    check("hp_digest_order_independent", A.hp_digest(hp) == A.hp_digest(same) and not A.hp_diff(hp, same))
    moved = copy.deepcopy(hp)
    moved[200]["location"][2] += 0.1
    check("CONTROL_hp_moved_0p1cm_detected", A.hp_diff(hp, moved) == ["MOVED|/W.HP200"] and
          A.hp_digest(hp) != A.hp_digest(moved), A.hp_diff(hp, moved))
    reparent = copy.deepcopy(hp)
    reparent[5]["parent_label"] = None
    check("CONTROL_hp_detached_detected", A.hp_diff(hp, reparent) == ["MOVED|/W.HP5"])
    check("CONTROL_hp_missing_detected", A.hp_diff(hp, hp[:-1]) == ["PRESENCE|/W.HP%d" % (A.HP_EXPECTED - 1)])
    check("CONTROL_hp_count_gate", raises(A._hp_gate, hp[:-1], contains="HP_COUNT") and not raises(A._hp_gate, hp))


def t_log_scan():
    log = "\n".join([
        "LogMaterial: Error: [SM6] M_S3_MarbleTiling: old failure from yesterday",
        "LogPython: S3_MARBLE_TILING_START|run=S3MT-1|mode=BUILD|frame=world",
        "LogShaderCompilers: Warning: something else",
        "LogPython: S3_MARBLE_TILING_BUILD_OK|run=S3MT-1|{}",
    ])
    check("log_scan_clean_after_marker", A.M.compile_errors_since(log, A.COMPILE_MARKER) == [])
    bad = log + "\nLogMaterial: Error: Failed to compile Material /Game/InfinityStage/Dev/Materials/M_S3_MarbleTiling"
    check("CONTROL_log_scan_finds_error_after_marker", len(A.M.compile_errors_since(bad, A.COMPILE_MARKER)) == 1)
    check("CONTROL_log_scan_no_marker_is_unknown", A.M.compile_errors_since("nothing here", A.COMPILE_MARKER) is None)
    other = log.replace("mode=BUILD", "mode=DRY")
    check("CONTROL_log_scan_ignores_dry_start", A.M.compile_errors_since(other, A.COMPILE_MARKER) is None)


def t_probe_fact():
    """The measured mis-scale, from the live probe file (Wings & Textures)."""
    path = os.path.join(HERE, "..", "CodexFlatV3", "handprints", "hp_marble_probe.json")
    probe = json.load(open(path, encoding="utf-8"))
    import re
    s = [float(v) for v in re.findall(r"[xyz]: (-?[0-9.]+)", probe["actor_scale"])]
    w, h = s[0] * 100.0, s[2] * 100.0
    tex = probe["textures"]["BaseColorTexture"][1]
    check("probe_old_anisotropy_measured", abs((tex / h) / (tex / w) - w / h) < 1e-9 and w / h > 9.0,
          "old: %.2f px/cm across vs %.2f px/cm up = %.1f:1" % (tex / w, tex / h, w / h))
    check("probe_parent_is_megascans_base", probe["parent"].endswith("M_MS_Base"), probe["parent"])
    check("probe_look_matches_fallback", all(abs(probe["scalars"][k] - M.LOOK_FALLBACK[k]) < 1e-4
                                             for k in M.LOOK_FALLBACK), probe["scalars"])


def main():
    for t in (t_graph_spec, t_sampler, t_axes, t_targets, t_plan, t_frame_params, t_continuity_and_rigidity,
              t_tiling_and_breakup, t_noise_wrap_control, t_mode_and_census, t_hp, t_log_scan, t_probe_fact):
        try:
            t()
        except Exception as exc:  # noqa: BLE001
            RESULTS.append({"check": t.__name__ + "_CRASHED", "pass": False, "detail": repr(exc)})
    fails = [r for r in RESULTS if not r["pass"]]
    controls = [r for r in RESULTS if r["check"].startswith("CONTROL_")]
    out = {"checks": len(RESULTS), "failed": len(fails), "controls": len(controls), "results": RESULTS}
    with open(os.path.join(HERE, "test_s3_marble_tiling_offline_report.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=1)
    for r in RESULTS:
        print(("PASS " if r["pass"] else "FAIL ") + r["check"] + ("  " + r["detail"] if r["detail"] else ""))
    print(("S3_MARBLE_TILING_OFFLINE_OK" if not fails else "S3_MARBLE_TILING_OFFLINE_FAILED") +
          "|checks=%d|failed=%d|controls=%d" % (len(RESULTS), len(fails), len(controls)))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
