"""N-slab domino chain with MEASURED per-row heights, per-gap spacing and per-contact thickness (offline, numpy).

Extends DerivedAssets/FlatV3/Review_2026-10-07/p06_plan/topple/topple_solver.py (7 Oct, loaded by path, unchanged):
its Params, fit_keys, frame_fraction, slab_poly3d and model constants are reused; Chain and simulate are re-stated
here because the original takes ONE spacing and ONE thickness [decl topple_solver.py:48-49, :93, :186-187].

Changes against the original model (all [inf] -- planar rigid slabs, as before):
  * gap k (hinge k -> hinge k+1, along the route) is its own s_k; the contact relation becomes
        H_k sin(theta_k - phi) = s_k cos(phi) - c_k,   c_k = (t_k + t_{k+1}) / 2
    which reduces to the original H sin(theta - phi) = s cos(phi) - t when all thicknesses are equal.
  * end = "braced": the next same-side row (standing, held static by STILL) stops the last slab -- the original's
    last_fixed branch (wall restitution 0.22, rest after the second knock) with that row's own gap and thickness.
    end = "floor": the last slab slams the floor at 90 deg (it then lies THROUGH any standing panel within its height).
"""
import importlib.util
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SOLVER = os.path.join(PROJECT, "DerivedAssets", "FlatV3", "Review_2026-10-07", "p06_plan", "topple", "topple_solver.py")


def load_solver(path=SOLVER):
    name = "topple_solver_chain"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod          # @dataclass needs the module registered
    spec.loader.exec_module(mod)
    return mod


ts = load_solver()
G = ts.G


def leaner(phi, H, s, c):
    return phi + math.asin(max(-1.0, min(1.0, (s * math.cos(phi) - c) / H)))


def contact(H, s, c):
    return math.asin(max(-1.0, min(1.0, (s - c) / H)))


class ChainV:
    """heights[k], gaps[k] (k -> k+1, len n-1, plus the brace gap if braced), contact c[k] likewise."""

    def __init__(self, p, gaps, cs):
        self.p, self.gaps, self.cs = p, list(gaps), list(cs)
        self.H = list(p.heights)
        self.m = [p.mass * h for h in self.H]
        self.I = [mi * h * h / 3.0 for mi, h in zip(self.m, self.H)]

    def angles(self, lead, phi):
        q = [0.0] * (lead + 1)
        q[lead] = phi
        for k in range(lead - 1, -1, -1):
            q[k] = leaner(q[k + 1], self.H[k], self.gaps[k], self.cs[k])
        return q

    def jac(self, lead, phi, h=1e-6):
        return (np.array(self.angles(lead, phi + h)) - np.array(self.angles(lead, phi - h))) / (2 * h)

    def mass(self, lead, phi):
        J = self.jac(lead, phi)
        return float(np.sum(np.array(self.I[:lead + 1]) * J * J))

    def accel(self, lead, phi, w):
        J = self.jac(lead, phi)
        q = self.angles(lead, phi)
        M = float(np.sum(np.array(self.I[:lead + 1]) * J * J))
        h = 1e-5
        dM = (self.mass(lead, phi + h) - self.mass(lead, phi - h)) / (2 * h)
        Gt = sum(self.m[k] * G * self.H[k] / 2 * math.sin(q[k]) * J[k] for k in range(lead + 1))
        return (Gt - 0.5 * dM * w * w - self.p.damping * M * w) / M


def simulate(p, gaps, cs, braced):
    """Mirror of topple_solver.simulate [decl topple_solver.py:117-245] with per-gap contact and a braced end."""
    ch = ChainV(p, gaps, cs)
    n, dt = p.n, p.dt
    rec_t, rec_q, rec_w, events = [], [], [], []

    def record(t, lead, phi, w):
        q = ch.angles(lead, phi) + [0.0] * (n - lead - 1)
        J = list(ch.jac(lead, phi)) + [0.0] * (n - lead - 1)
        rec_t.append(t)
        rec_q.append(q[:n])
        rec_w.append([j * w for j in J[:n]])

    ck, t = p.creak, 0.0
    ang = om = 0.0
    while t < ck[-1][0]:
        for (t0, a0), (t1, a1) in zip(ck[:-1], ck[1:]):
            if t0 <= t < t1:
                u = (t - t0) / (t1 - t0)
                ang = math.radians(a0 + (a1 - a0) * u * u * (3 - 2 * u))
                om = math.radians((a1 - a0) * 6 * u * (1 - u) / (t1 - t0))
                break
        rec_t.append(t)
        rec_q.append([ang] + [0.0] * (n - 1))
        rec_w.append([om] + [0.0] * (n - 1))
        t += dt
    events.append({"t": t, "type": "release", "slab": 0, "deg": p.release_deg})
    lead, phi, w = 0, math.radians(p.release_deg), math.radians(p.release_omega_dps)
    snagged, floor_hits, wall_hits = False, 0, 0
    floor = math.radians(p.floor_deg)
    resting, rest_t = False, None

    def rk4(lead, phi, w):
        k1p, k1w = w, ch.accel(lead, phi, w)
        k2p, k2w = w + 0.5 * dt * k1w, ch.accel(lead, phi + 0.5 * dt * k1p, w + 0.5 * dt * k1w)
        k3p, k3w = w + 0.5 * dt * k2w, ch.accel(lead, phi + 0.5 * dt * k2p, w + 0.5 * dt * k2w)
        k4p, k4w = w + dt * k3w, ch.accel(lead, phi + dt * k3p, w + dt * k3w)
        return (phi + dt / 6 * (k1p + 2 * k2p + 2 * k3p + k4p), w + dt / 6 * (k1w + 2 * k2w + 2 * k3w + k4w))

    while t < 60.0:
        record(t, lead, phi, w)
        if resting:
            if t >= rest_t + p.hold_after_rest:
                break
            t += dt
            continue
        phi_n, w_n = rk4(lead, phi, w)
        t += dt
        if not snagged and lead == 0 and phi_n >= math.radians(p.snag_deg):
            snagged = True
            w_n *= p.snag_factor
            events.append({"t": t, "type": "snag", "slab": 0, "deg": math.degrees(phi_n)})
        has_next = lead + 1 < n or (braced and lead + 1 == n)
        if has_next and w_n > 0:
            th_c = contact(ch.H[lead], ch.gaps[lead], ch.cs[lead])
            if phi_n >= th_c:
                if lead + 1 < n:
                    J_old = np.array(list(ch.jac(lead, th_c)) + [0.0])
                    J_new = ch.jac(lead + 1, 0.0)
                    Iv = np.array(ch.I[:lead + 2])
                    w_new = float(np.sum(Iv * J_new * J_old) * w_n / np.sum(Iv * J_new * J_new)) * (1.0 - p.domino_loss)
                    lost = 1 - (np.sum(Iv * J_new * J_new) * w_new ** 2) / (np.sum(Iv * J_old * J_old) * w_n ** 2)
                    events.append({"t": t, "type": "domino", "slab": lead, "hits": lead + 1,
                                   "contact_deg": math.degrees(th_c), "omega_before_dps": math.degrees(w_n),
                                   "omega_after_dps": math.degrees(w_new), "energy_lost_frac": float(lost)})
                    lead, phi, w = lead + 1, 0.0, w_new
                    continue
                wall_hits += 1
                w_b = -p.wall_e * w_n
                events.append({"t": t, "type": "wall", "slab": lead, "n": wall_hits, "contact_deg": math.degrees(th_c),
                               "omega_before_dps": math.degrees(w_n), "omega_after_dps": math.degrees(w_b)})
                phi, w = th_c, w_b
                if abs(math.degrees(w_b)) < 2.0 or wall_hits >= 3:
                    w, resting, rest_t = 0.0, True, t
                    events.append({"t": t, "type": "rest", "slab": lead, "deg": math.degrees(phi)})
                continue
        if phi_n >= floor and w_n > 0:
            floor_hits += 1
            e = p.floor_e[floor_hits - 1] if floor_hits <= len(p.floor_e) else 0.0
            w_b = -e * w_n
            events.append({"t": t, "type": "floor", "slab": lead, "n": floor_hits,
                           "omega_before_dps": math.degrees(w_n), "omega_after_dps": math.degrees(w_b)})
            phi, w = floor, w_b
            if e == 0.0 or abs(math.degrees(w_b)) < 1.0:
                w, resting, rest_t = 0.0, True, t
                events.append({"t": t, "type": "rest", "slab": lead, "deg": p.floor_deg})
            continue
        phi, w = phi_n, w_n
    T = np.array(rec_t)
    Q = np.degrees(np.array(rec_q))
    W = np.degrees(np.array(rec_w))
    for e in [e for e in events if e["type"] in ("floor", "wall")]:
        i0 = np.searchsorted(T, e["t"])
        seg = Q[i0:i0 + int(1.5 / dt), e["slab"]]
        if len(seg):
            ref = p.floor_deg if e["type"] == "floor" else Q[i0, e["slab"]]
            e["rebound_deg"] = float(ref - seg.min()) if e["omega_after_dps"] < 0 else 0.0
    return T, Q, W, events, ch


def run_chain(heights_m, hinge_m, thick_m, brace=None, direction=-1):
    """heights_m/hinge_m/thick_m per chain row (fall order = route order, away from the camera).
    brace = {"hinge_m", "thickness_m"} of the next same-side row for end="braced", or None for end="floor".
    Returns rows with normalised Show keys (topple_solver.run_variant format) + the raw arrays."""
    n = len(heights_m)
    gaps = [b - a for a, b in zip(hinge_m[:-1], hinge_m[1:])]
    cs = [(a + b) / 2.0 for a, b in zip(thick_m[:-1], thick_m[1:])]
    if brace is not None:
        gaps.append(brace["hinge_m"] - hinge_m[-1])
        cs.append((thick_m[-1] + brace["thickness_m"]) / 2.0)
    p = ts.Params(name="C_chain%d_live" % n, n=n, heights=list(heights_m), spacing=sum(gaps) / len(gaps),
                  thickness=max(thick_m), direction=direction, last_fixed=brace is not None)
    T, Q, W, events, ch = simulate(p, gaps, cs, brace is not None)
    t_end = float(T[-1])
    starts = [0.0] + [next(e["t"] for e in events if e["type"] == "domino" and e["hits"] == k) for k in range(1, n)]
    ev_times = [e["t"] for e in events] + [c[0] for c in p.creak]
    for e in events:
        if e["type"] in ("floor", "wall") and e.get("rebound_deg", 0) > 0:
            i0 = np.searchsorted(T, e["t"])
            seg = Q[i0:i0 + int(1.5 / p.dt), e["slab"]]
            ev_times.append(float(T[i0 + int(np.argmin(seg))]))
    max_angle = 90.0 * direction
    rows = []
    for k in range(n):
        keys, err = ts.fit_keys(T, Q[:, k], W[:, k], starts[k], t_end, ev_times)
        dur = t_end - starts[k]
        rows.append({"fall_order": k, "start_s": round(starts[k], 4), "duration_s": round(dur, 4),
                     "CycleRateHz": round(1.0 / dur, 6), "MaxAngleDeg": max_angle, "final_deg": round(float(Q[-1, k]), 3),
                     "fit_max_err_deg": round(err, 3),
                     "keys": [{"phase": round((kt - starts[k]) / dur, 6), "value": round(kv / abs(max_angle), 6),
                               "arrive_tangent": round(ka * dur / abs(max_angle), 6),
                               "leave_tangent": round(kl * dur / abs(max_angle), 6), "time_s": round(kt, 4),
                               "angle_deg": round(kv, 3)} for kt, kv, ka, kl in keys]})
    impacts = [e for e in events if e["type"] in ("floor", "wall") and e["slab"] == n - 1]
    return {"rows": rows, "events": events, "t_end": t_end, "T": T, "Q": Q, "gaps_m": gaps, "contact_c_m": cs,
            "final_impact_s": impacts[0]["t"] if impacts else None,
            "final_impact_type": impacts[0]["type"] if impacts else None,
            "contact_deg": [math.degrees(contact(h, s, c)) for h, s, c in zip(heights_m, gaps, cs)]}


def coverage(res, hinge_m, heights_m, lat_inner_m, lat_width_m, cam_m_at, t_from, t_to, step=1.0 / 24):
    """Share of the 16:9 frame (37.5 deg hfov, eye 1.8 m, looking down the route [decl README 0 of the p06 plan])
    covered by the chain slabs, camera at route metre cam_m_at(t) (t = seconds from the creak)."""
    T, Q = res["T"], res["Q"]
    out = []
    t = t_from
    while t <= t_to + 1e-9:
        i = min(len(T) - 1, int(np.searchsorted(T, t)))
        cam = cam_m_at(t)
        share = sum(ts.frame_fraction(ts.slab_poly3d(hinge_m[k], +1, Q[i, k], heights_m[k], y0=lat_inner_m[k],
                                                     width=lat_width_m[k]), cam) for k in range(len(hinge_m)))
        out.append((t, cam, share))
        t += step
    return out
