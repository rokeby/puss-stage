"""Offline Python mirror of FInfinityStageBeeSwarmSimulation (held C++ patch).

Mirrors Scripts/patches/2026-10-04_BS_bee_swarm_sim.v3.patch,
Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageBeeSwarmSimulation.cpp,
statement by statement, so behaviour can be tuned without the editor.

Exactness, per part (see the runbook for the cross-check that MEASURES it):
  * FRandomStream is reproduced bit-for-bit from the UE 5.8 header
    (D:/Unreal Engine/UE_5.8/Engine/Source/Runtime/Core/Public/Math/RandomStream.h:
    Initialize 62-66, GetFraction 115-124, RandHelper 186-190, RandRange 209-214,
    FRandRange 221-224, MutateSeed 362-365).  Integer LCG: exact by construction.
  * float/double promotion follows the C++ (float parameters, double FVector).
  * cos/sqrt/log/exp come from numpy/libm, not MSVC's CRT, so trajectories are
    expected to agree to ~1e-9 cm at first and then diverge chaotically.  The
    PythonMirrorGolden automation test in the v3 patch checks the 1-second state.

The simulation is vectorised across bees; bees never interact, so per-bee order
inside a fixed step does not change results.  Every random draw happens in the
same order per stream as in the C++.
"""
from __future__ import annotations

import dataclasses
import math
import struct

import numpy as np

F32 = np.float32
UE_SMALL_NUMBER = 1.0e-8          # UnrealMathUtility: UE_SMALL_NUMBER (float 1e-8)
UE_DOUBLE_SMALL_NUMBER = 1.0e-8
UE_KINDA_SMALL_NUMBER = 1.0e-4
UE_PI_F32 = float(F32(3.1415926535897932))
MINIMUM_FIXED_STEP = float(F32(1.0 / 1000.0))
RIGHT = np.array([0.0, 1.0, 0.0])
UP = np.array([0.0, 0.0, 1.0])


def f32(value):
    return float(F32(value))


class RandomStream:
    """Bit-exact FRandomStream."""

    __slots__ = ("seed",)

    def __init__(self, seed=0):
        self.seed = int(seed) & 0xFFFFFFFF

    def initialize(self, seed):
        self.seed = int(seed) & 0xFFFFFFFF

    def _mutate(self):
        self.seed = (self.seed * 196314165 + 907633515) & 0xFFFFFFFF

    def frand(self):
        self._mutate()
        bits = 0x3F800000 | (self.seed >> 9)
        value = struct.unpack("<f", struct.pack("<I", bits))[0]
        return float(F32(F32(value) - F32(1.0)))

    def rand_helper(self, a):
        return int(math.trunc(float(F32(F32(self.frand()) * F32(a))))) if a > 0 else 0

    def rand_range_int(self, lo, hi):
        return lo + self.rand_helper((hi - lo) + 1)

    def frand_range(self, lo, hi):
        return lo + (hi - lo) * self.frand()


def random_range(stream, lo, hi):
    """FInfinityStageBeeSwarmSimulation::RandomRange: float args, float return."""
    lo32, hi32 = f32(lo), f32(hi)
    return f32(stream.frand_range(lo32, hi32))


def random_unit_vector(stream):
    z = float(random_range(stream, -1.0, 1.0))
    angle = float(random_range(stream, 0.0, f32(F32(2.0) * F32(UE_PI_F32))))
    radius = math.sqrt(max(0.0, 1.0 - z * z))
    return np.array([radius * math.cos(angle), radius * math.sin(angle), z])


def schedule_poisson(now, rate, stream):
    if rate <= UE_SMALL_NUMBER:
        return float("inf")
    draw = float(stream.frand())
    u = min(max(draw, 0.0), 1.0 - UE_DOUBLE_SMALL_NUMBER)
    return now - math.log(1.0 - u) / float(rate)


def safe_normal(v, tolerance=UE_SMALL_NUMBER, fallback=None):
    sq = float(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if sq == 1.0:
        return v.copy()
    if sq < tolerance:
        return np.zeros(3) if fallback is None else np.array(fallback, dtype=float)
    return v * (1.0 / math.sqrt(sq))


def safe_normal_rows(v, tolerance=UE_SMALL_NUMBER):
    sq = np.einsum("ij,ij->i", v, v)
    out = np.zeros_like(v)
    ok = sq >= tolerance
    out[ok] = v[ok] / np.sqrt(sq[ok])[:, None]
    exact = sq == 1.0
    out[exact] = v[exact]
    return out


def clamped_to_max(v, max_size):
    if max_size < UE_KINDA_SMALL_NUMBER:
        return np.zeros(3)
    sq = float(np.dot(v, v))
    if sq > max_size * max_size:
        return v * (max_size / math.sqrt(sq))
    return v


def clamped_rows(v, max_size):
    sq = np.einsum("ij,ij->i", v, v)
    over = sq > max_size * max_size
    if np.any(over):
        v = v.copy()
        v[over] *= (max_size / np.sqrt(sq[over]))[:, None]
    return v


def curl_noise(p, t, scale, time_scale):
    """Vectorised CurlNoise; p is (N,3) or (3,)."""
    p = np.asarray(p, dtype=float) * float(scale)
    tt = t * float(time_scale)
    mix = 0.73
    if p.ndim == 1:
        c0 = math.cos(p[1] + mix * p[2] + tt * 1.11)
        c1 = math.cos(p[2] + mix * p[0] + tt * 0.89)
        c2 = math.cos(p[0] + mix * p[1] + tt * 1.23)
        return safe_normal(np.array([mix * c2 - c1, mix * c0 - c2, mix * c1 - c0]))
    c0 = np.cos(p[:, 1] + mix * p[:, 2] + tt * 1.11)
    c1 = np.cos(p[:, 2] + mix * p[:, 0] + tt * 0.89)
    c2 = np.cos(p[:, 0] + mix * p[:, 1] + tt * 1.23)
    return safe_normal_rows(np.stack([mix * c2 - c1, mix * c0 - c2, mix * c1 - c0], axis=1))


@dataclasses.dataclass
class Params:
    """FInfinityStageBeeSwarmParameters.  Defaults = v3 header defaults."""
    bee_count: int = 200
    seed: int = 0xBEE62026
    fixed_step_seconds: float = 1.0 / 120.0
    bounds_extent_cm: tuple = (600.0, 450.0, 140.0)
    target_wander_speed: float = 150.0
    target_jump_interval: tuple = (0.8, 2.6)
    orbit_radius_range: tuple = (30.0, 140.0)
    large_noise_scale: float = 0.003
    small_noise_scale: float = 0.09
    large_noise_accel: float = 220.0
    small_noise_accel: float = 1200.0
    dart_rate: float = 0.45
    dart_strength: float = 320.0
    drag: float = 1.6
    max_speed: float = 650.0
    camera_attract_weight: float = 0.9
    camera_repulsion_radius: float = 25.0
    flyby_rate: float = 0.8
    target_drag: float = 1.5          # v3 addition; 0 reproduces v2
    orbit_spring: float = 12.0        # v3: was the literal 4.0 in StepFixed
    orbit_tangential_accel: float = 240.0  # v3: was the literal 240.0 in StepFixed

    def as_cpp(self):
        """Field names as UPROPERTY names (for docs and the actor CDO)."""
        return {
            "BeeCount": self.bee_count,
            "Seed": self.seed,
            "FixedStepSeconds": self.fixed_step_seconds,
            "BoundsExtentCm": list(self.bounds_extent_cm),
            "TargetWanderSpeedCmPerSecond": self.target_wander_speed,
            "TargetJumpIntervalSeconds": list(self.target_jump_interval),
            "OrbitRadiusRangeCm": list(self.orbit_radius_range),
            "LargeNoiseScalePerCm": self.large_noise_scale,
            "SmallNoiseScalePerCm": self.small_noise_scale,
            "LargeNoiseAccelerationCmPerSecondSquared": self.large_noise_accel,
            "SmallNoiseAccelerationCmPerSecondSquared": self.small_noise_accel,
            "DartRatePerSecond": self.dart_rate,
            "DartStrengthCmPerSecond": self.dart_strength,
            "DragPerSecond": self.drag,
            "MaxSpeedCmPerSecond": self.max_speed,
            "CameraAttractWeight": self.camera_attract_weight,
            "CameraRepulsionRadiusCm": self.camera_repulsion_radius,
            "FlyByRatePerSecond": self.flyby_rate,
            "TargetDragPerSecond": self.target_drag,
            "OrbitSpringPerSecondSquared": self.orbit_spring,
            "OrbitTangentialAccelerationCmPerSecondSquared": self.orbit_tangential_accel,
        }


# The v2 header defaults, kept for comparison runs.
V2_DEFAULTS = Params(
    bounds_extent_cm=(600.0, 450.0, 300.0), target_wander_speed=180.0,
    target_jump_interval=(1.5, 4.5), orbit_radius_range=(35.0, 180.0),
    large_noise_accel=220.0, small_noise_accel=90.0, dart_rate=0.12,
    dart_strength=420.0, drag=1.6, max_speed=900.0, camera_attract_weight=0.08,
    camera_repulsion_radius=25.0, flyby_rate=0.35, target_drag=0.0, small_noise_scale=0.014,
    orbit_spring=4.0, orbit_tangential_accel=240.0)


class Simulation:
    def reset(self, params: Params, origin, camera):
        p = dataclasses.replace(params)
        p.bee_count = max(1, int(p.bee_count))
        p.fixed_step_seconds = f32(max(MINIMUM_FIXED_STEP, f32(p.fixed_step_seconds)))
        p.max_speed = f32(max(1.0, f32(p.max_speed)))
        ext = np.array([max(1.0, abs(float(v))) for v in p.bounds_extent_cm])
        p.bounds_extent_cm = tuple(ext)
        p.camera_repulsion_radius = f32(min(max(f32(p.camera_repulsion_radius), 0.0),
                                            f32(float(np.linalg.norm(ext)))))
        jx = max(0.01, float(p.target_jump_interval[0]))
        jy = max(jx, float(p.target_jump_interval[1]))
        p.target_jump_interval = (jx, jy)
        p.target_drag = max(0.0, float(p.target_drag))
        ox = max(f32(p.camera_repulsion_radius + F32(1.0)), float(p.orbit_radius_range[0]))
        oy = max(ox, float(p.orbit_radius_range[1]))
        p.orbit_radius_range = (ox, oy)
        for name in ("target_wander_speed", "large_noise_scale", "small_noise_scale",
                     "large_noise_accel", "small_noise_accel", "dart_rate", "dart_strength",
                     "drag", "camera_attract_weight", "flyby_rate", "target_drag",
                     "orbit_spring", "orbit_tangential_accel"):
            setattr(p, name, f32(getattr(p, name)))
        self.p = p
        self.ext = ext
        self.origin = np.array(origin, dtype=float)
        self.target = self.origin.copy()
        self.target_stream = RandomStream()
        self.target_stream.initialize(p.seed)
        direction = random_unit_vector(self.target_stream)
        self.target_velocity = direction * p.target_wander_speed
        self.sim_seconds = 0.0
        self.accumulator = 0.0
        self.next_jump = float(random_range(self.target_stream, jx, jy))
        self.next_flyby = schedule_poisson(0.0, p.flyby_rate, self.target_stream)
        self.last_camera = np.array(camera, dtype=float)
        self.has_camera = True
        n = p.bee_count
        self.pos = np.zeros((n, 3))
        self.vel = np.zeros((n, 3))
        self.axis = np.zeros((n, 3))
        self.radius = np.zeros(n)
        self.next_dart = np.zeros(n)
        self.streams = []
        cam = np.array(camera, dtype=float)
        for i in range(n):
            mixed = ((p.seed & 0xFFFFFFFF) ^ ((0x9E3779B9 * (i + 1)) & 0xFFFFFFFF)) & 0xFFFFFFFF
            s = RandomStream(mixed)
            self.streams.append(s)
            self.axis[i] = random_unit_vector(s)
            self.radius[i] = random_range(s, ox, oy)
            self.next_dart[i] = schedule_poisson(0.0, p.dart_rate, s)
            r0 = random_range(s, f32(F32(p.camera_repulsion_radius) + F32(5.0)), oy)
            d0 = random_unit_vector(s)
            v0 = random_unit_vector(s)
            frac = random_range(s, 0.1, 0.35)
            self.pos[i] = self.origin + d0 * r0
            self.vel[i] = v0 * frac * p.max_speed
            self.pos[i], self.vel[i] = self._resolve_one(self.pos[i], self.vel[i], cam, self.axis[i], 1.0)
        self.flyby_count = 0
        self.dart_count = 0
        self.jump_count = 0
        return self

    # -- constraints ---------------------------------------------------------
    def _bounds(self, scale):
        e = self.ext * scale
        return self.origin - e, self.origin + e

    def _constrain_rows(self, pos, vel, scale):
        lo, hi = self._bounds(scale)
        below = pos < lo
        above = pos > hi
        pos = np.where(below, lo, np.where(above, hi, pos))
        vel = np.where(below, np.abs(vel), np.where(above, -np.abs(vel), vel))
        return pos, vel

    def _resolve_one(self, pos, vel, cam, fallback, scale):
        pos, vel = self._constrain_rows(pos[None, :], vel[None, :], scale)
        pos, vel = pos[0], vel[0]
        r = float(self.p.camera_repulsion_radius)
        if r <= 0.0:
            return pos, vel
        frm = pos - cam
        if float(np.dot(frm, frm)) + UE_DOUBLE_SMALL_NUMBER >= r * r:
            return pos, vel
        lo, hi = self._bounds(scale)
        outward = safe_normal(frm, UE_DOUBLE_SMALL_NUMBER,
                              safe_normal(fallback, UE_DOUBLE_SMALL_NUMBER, UP))
        cand = cam + outward * r
        cand = np.minimum(np.maximum(cand, lo), hi)
        d = cand - cam
        if float(np.dot(d, d)) + UE_DOUBLE_SMALL_NUMBER < r * r:
            cand = np.where(np.abs(lo - cam) > np.abs(hi - cam), lo, hi)
        pos = cand
        final = safe_normal(pos - cam, UE_DOUBLE_SMALL_NUMBER, outward)
        inward = float(np.dot(vel, final))
        if inward < 0.0:
            vel = vel - final * inward
        return pos, vel

    def _resolve_rows(self, cam, scale=1.0):
        self.pos, self.vel = self._constrain_rows(self.pos, self.vel, scale)
        r = float(self.p.camera_repulsion_radius)
        if r <= 0.0:
            return
        frm = self.pos - cam
        inside = np.einsum("ij,ij->i", frm, frm) + UE_DOUBLE_SMALL_NUMBER < r * r
        for i in np.nonzero(inside)[0]:
            self.pos[i], self.vel[i] = self._resolve_one(self.pos[i], self.vel[i], cam, self.axis[i], scale)

    # -- stepping ------------------------------------------------------------
    def advance(self, dt, camera, cut=False):
        camera = np.array(camera, dtype=float)
        if not self.has_camera:
            self.last_camera = camera.copy()
            self.has_camera = True
        dt = float(max(F32(0.0), F32(dt)))
        step = float(self.p.fixed_step_seconds)
        acc0 = self.accumulator
        self.accumulator += dt
        step_time = step - acc0
        while self.accumulator + UE_DOUBLE_SMALL_NUMBER >= step:
            if cut or dt <= UE_SMALL_NUMBER:
                alpha = 1.0
            else:
                alpha = min(max(step_time / dt, 0.0), 1.0)
            a = camera if cut else self.last_camera
            step_cam = a + alpha * (camera - a)
            self._step(step, step_cam)
            self.accumulator -= step
            step_time += step
        self.accumulator = max(0.0, self.accumulator)
        self.last_camera = camera.copy()
        self._resolve_rows(camera)

    def _update_target(self, step):
        p = self.p
        noise = curl_noise(self.target, self.sim_seconds, f32(F32(p.large_noise_scale) * F32(0.35)), f32(0.21))
        self.target_velocity = self.target_velocity + (noise * p.target_wander_speed) * step
        if self.sim_seconds >= self.next_jump:
            jump = random_unit_vector(self.target_stream)
            self.target_velocity = self.target_velocity + jump * f32(F32(p.target_wander_speed) * F32(2.5))
            interval = random_range(self.target_stream, p.target_jump_interval[0], p.target_jump_interval[1])
            self.next_jump = self.sim_seconds + interval
            self.jump_count += 1
        # v3: the target decelerates between jumps (dart, then hover).
        self.target_velocity = self.target_velocity * float(np.exp(F32(-F32(p.target_drag) * F32(step))))
        self.target_velocity = clamped_to_max(self.target_velocity, f32(F32(p.target_wander_speed) * F32(3.0)))
        self.target = self.target + self.target_velocity * step
        tp, tv = self._constrain_rows(self.target[None, :], self.target_velocity[None, :], f32(0.45))
        self.target, self.target_velocity = tp[0], tv[0]

    def _inject_flyby(self, cam):
        n = self.pos.shape[0]
        i = self.target_stream.rand_range_int(0, n - 1)
        s = self.streams[i]
        radial = random_unit_vector(s)
        seed = random_unit_vector(s)
        tangent = safe_normal(np.cross(radial, seed))
        if np.all(np.abs(tangent) <= UE_KINDA_SMALL_NUMBER):
            tangent = safe_normal(np.cross(radial, UP), UE_DOUBLE_SMALL_NUMBER, RIGHT)
        p = self.p
        self.pos[i] = cam + radial * f32(F32(p.camera_repulsion_radius) + F32(20.0))
        self.vel[i] = safe_normal(tangent * f32(0.9) + radial * f32(0.1)) * f32(F32(p.max_speed) * F32(0.9))
        self.pos[i], self.vel[i] = self._resolve_one(self.pos[i], self.vel[i], cam, self.axis[i], 1.0)
        self.flyby_count += 1
        self.last_flyby_index = i

    def _step(self, step, cam):
        p = self.p
        self.sim_seconds += step
        self._update_target(step)
        if self.sim_seconds >= self.next_flyby:
            self._inject_flyby(cam)
            self.next_flyby = schedule_poisson(self.sim_seconds, p.flyby_rate, self.target_stream)
        drag = float(np.exp(F32(-F32(p.drag) * F32(step))))
        to_target = self.target - self.pos
        dist = np.maximum(1.0, np.sqrt(np.einsum("ij,ij->i", to_target, to_target)))
        direction = to_target / dist[:, None]
        tangent = safe_normal_rows(np.cross(self.axis, direction))
        near_zero = np.all(np.abs(tangent) <= UE_KINDA_SMALL_NUMBER, axis=1)
        for i in np.nonzero(near_zero)[0]:
            self.axis[i] = random_unit_vector(self.streams[i])
            tangent[i] = safe_normal(np.cross(self.axis[i], direction[i]), UE_DOUBLE_SMALL_NUMBER, RIGHT)
        acc = direction * ((dist - self.radius) * float(p.orbit_spring))[:, None]
        acc += tangent * float(p.orbit_tangential_accel)
        acc += curl_noise(self.pos, self.sim_seconds, p.large_noise_scale, f32(0.37)) * p.large_noise_accel
        acc += curl_noise(self.pos, self.sim_seconds, p.small_noise_scale, f32(1.31)) * p.small_noise_accel
        to_cam = cam - self.pos
        cd = np.sqrt(np.einsum("ij,ij->i", to_cam, to_cam))
        ok = cd > UE_DOUBLE_SMALL_NUMBER
        unit = np.zeros_like(to_cam)
        unit[ok] = to_cam[ok] / cd[ok][:, None]
        acc[ok] += unit[ok] * f32(F32(p.camera_attract_weight) * F32(300.0))
        rep = float(p.camera_repulsion_radius) * 2.0
        close = ok & (cd < rep)
        if np.any(close):
            acc[close] -= unit[close] * ((1.0 - cd[close] / max(1.0, rep)) * float(p.dart_strength))[:, None]
        darting = self.sim_seconds >= self.next_dart
        for i in np.nonzero(darting)[0]:
            self.vel[i] = self.vel[i] + random_unit_vector(self.streams[i]) * float(p.dart_strength)
            self.next_dart[i] = schedule_poisson(self.sim_seconds, p.dart_rate, self.streams[i])
            self.dart_count += 1
        self.vel = (self.vel + acc * step) * drag
        self.vel = clamped_rows(self.vel, float(p.max_speed))
        self.pos = self.pos + self.vel * step
        self._resolve_rows(cam)
