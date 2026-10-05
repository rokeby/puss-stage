"""LOOK BENCH: a reversible, NON-SAVING, in-memory A/B of "look depth" on ONE
Passage bay (default P04 bay 4), for Gary's 5 Oct note that the passages read flat.
Plan and evidence: Docs/Conductor/LOOK_DEPTH_PLAN_2026-10-05.md.

WHERE IT RUNS: ONLY in a PIE game world. It refuses to arm without one, so every
change lands on PIE duplicates that die when PIE ends. It never begins or ends PIE
(memory: never end someone's PIE); the operator does both.

Toggles (any subset, each applied from the recorded base):
  shadows    cast_shadows + cast_volumetric_shadow ON for the bay's KEY lights
             (the SHADOW_KEYS_MAX brightest enabled spots in the bay)
  haze       Local Fog Volumes of VARIED density across the bay (thick upstage,
             thin near the camera), plus volumetric scattering raised on the bay's
             lights and one back-light beam thrown toward the camera path
             (haze only shows a shaft to a viewer the light travels toward)
  rake       a raking side-light pair at the corridor edges, grazing the wing faces
  floor      one dark glossy plane (walnut MI as a MID, roughness lowered) over the
             board floor, top +0.5 cm
  floor_wet  the floor plane, wetter (roughness near 0, grunge-driven roughness
             breakup) plus puddle discs (roughness 0): no new textures
  strobe     a ~1 Hz strobe low over the floor so its reflection reads
  edge       the bay's Flat V3 "Edge" slot swapped to a pale raw-board MID

Modes (BENCH_MODE, set through runpy init_globals):
  PROBE    read-only: resolves the bay, lights, edge slots, cvars; writes nothing
           to the world. Writes look_bench_probe_<run>.json.
  CAPTURE  for each state in BENCH_STATES: pose the bay, settle (texture
           streaming forced resident, exposure/Lumen/TSR settle delay), then a
           short in-motion clip of HighResShot frames while the transport plays;
           restores everything at the end and verifies it exactly.
  HOLD     apply BENCH_TOGGLES and hold them HOLD_SECONDS for a live look in the
           PIE viewport, then restore and verify.
  RESTORE  crash recovery: re-apply every value in the newest record file and
           destroy every ZZ_LOOKBENCH_ actor (GameplayStatics sweep, which sees
           transient actors).

Rules carried from memory, enforced here:
  - originals are READ, WRITTEN to a JSON file (flushed, fsynced, re-read and
    compared) and the path logged BEFORE the first change;
  - the bench announces its temps (ZZ_LOOKBENCH_* count, until when);
  - no save call exists in this file (the harness scans for one), and the
    editor-world dirty census must be unchanged at the end or the run fails;
  - Unreal objects live only inside the registered callback's closure; module
    globals hold plain data only;
  - spawned actors are destroyed by object reference in the same callback;
  - captures use NO exposure override (show exposure), and the success marker is
    printed only after asserted restore + census.
"""
from __future__ import annotations

import builtins
import datetime
import json
import math
import os
import pathlib
import time
import traceback

BASE = pathlib.Path("E:/PussStage/Saved/CodexConductor")
SPAWN_PREFIX = "ZZ_LOOKBENCH_"
HANDLE_NAME = "PUSS_LOOK_BENCH_HANDLE"
STATE_NAME = "PUSS_LOOK_BENCH_STATE"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
TICKS_PER_SECOND = 24000          # Master tick rate as used by lighting_looks_p04_driver.py
ALL_TOGGLES = ("shadows", "haze", "rake", "floor", "floor_wet", "strobe", "edge", "glint", "underpass")
LIGHT_FIELDS = ("cast_shadows", "cast_volumetric_shadow", "volumetric_scattering_intensity")
STREAM_CVAR = "r.Streaming.FullyLoadUsedTextures"

FLOOR_PARENT = "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_02/Materials/M_Walnut_Hrrngbn_02_Mat_Inst_Dup"
EDGE_PARENT = "/Engine/BasicShapes/BasicShapeMaterial"
CUBE = "/Engine/BasicShapes/Cube"
CYLINDER = "/Engine/BasicShapes/Cylinder"

DEFAULTS = {
    "passage": "P04",
    "bay": 4,
    "half_width_cm": 1450.0,        # P04 LOW_SIDE lamps stand at lane y +-1450 (PIE live_lights, 4 Oct)
    "shadow_keys_max": 4,
    "haze_densities": (0.10, 0.25, 0.55),   # near -> far: varied, thin where the camera is
    "haze_radius_cm": 700.0,
    "haze_height_falloff": 600.0,
    "haze_phase_g": 0.55,
    "haze_vsi": 2.5,                 # volumetric scattering on bay lights while hazed
    "beam_cd": 6000.0,
    "rake_cd": 2500.0,
    "rake_height_cm": 140.0,
    "rake_x_offset_cm": -80.0,       # toward the approaching camera from the bay centre
    "floor_scalars": {"Roughness_Low": 0.08, "Roughness_High": 0.22},
    "floor_wet_scalars": {"Roughness_Low": 0.02, "Roughness_High": 0.06, "Roughness_Add_Grunge": 0.6},
    "puddle_scalars": {"Roughness_Low": 0.0, "Roughness_High": 0.0},
    "puddles": ((-250.0, -400.0, 260.0), (120.0, 350.0, 340.0), (420.0, -120.0, 200.0),
                (-520.0, 600.0, 180.0), (650.0, 700.0, 240.0)),   # (dx, dy, diameter) in bay frame
    "strobe_hz": 1.0,
    "strobe_duty": 0.12,
    "strobe_cd": 12000.0,
    "edge_color": (0.62, 0.50, 0.36, 1.0),   # raw softwood / paper core
    "edge_max_components": 64,
    "lead_seconds": 4.0,
    "clip_seconds": 5.0,
    "clip_fps": 6.0,
    "settle_seconds": 4.0,
    "settle_ticks": 45,
    "hold_seconds": 120.0,
    "resolution": (1280, 720),
    # glint: a practical placed at the MIRROR position of one wing face for the camera route
    "glint_mesh_contains": "ruined_gallery_R_v3",   # W&T wet-paper test flat, P04 Wing 008 R
    "camera_height_cm": 150.0,       # [inf] cat-eye height; clip frames record the real camera location
    "glint_cam_distances": (1000.0, 800.0, 1200.0, 600.0, 1500.0, 1800.0, 400.0, 2200.0),
    "glint_light_dist_cm": 700.0,
    "glint_z_range": (40.0, 1100.0),
    "glint_cd": 1500.0,
    "glint_source_radius_cm": 2.0,   # small source = tight specular highlight
    # underpass: the Phase B mock bay of UNDERPASS_RIG_KIT_PLAN_2026-10-05.md section 4, as box
    # proxies (SM_UP_* are not imported yet)
    "underpass_column_outset_cm": 60.0,
    "underpass_deck_z_cm": 2000.0,
    "underpass_tie_every_cm": 45.0,
    "underpass_steel": (0.035, 0.045, 0.04, 1.0),
    "underpass_concrete": (0.18, 0.17, 0.16, 1.0),
    "underpass_shaft_cd": 8000.0,
}


# --------------------------------------------------------------------------
# pure helpers (no Unreal): tested offline by test_look_bench.py
# --------------------------------------------------------------------------

def utc_stamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")


def bay_prefixes(passage, bay):
    n = int(passage[1:])
    return ("P%02d Wing %03d " % (n, bay), "P%02d LOOK B%02d " % (n, bay))


def normalise_toggles(toggles):
    out = []
    for t in toggles:
        if t not in ALL_TOGGLES:
            raise ValueError("LOOK_BENCH_BAD_TOGGLE|" + str(t))
        if t not in out:
            out.append(t)
    if "floor_wet" in out and "floor" in out:
        out.remove("floor")          # wet is a floor variant, not a second plane
    return tuple(out)


def default_states(glint_available=True):
    states = [("base", ())]
    for t in ALL_TOGGLES:
        if t == "glint" and not glint_available:
            continue
        states.append((t, (t,)))
    if glint_available:
        states.append(("glint_wet", ("glint", "floor_wet")))
    states.append(("all", ("shadows", "haze", "rake", "floor_wet", "strobe", "edge", "underpass")
                   + (("glint",) if glint_available else ())))
    return states


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def _mul(a, k):
    return tuple(x * k for x in a)


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _unit(a):
    n = math.sqrt(_dot(a, a))
    if n < 1e-9:
        raise ValueError("zero vector")
    return _mul(a, 1.0 / n)


def glint_solution(face_point, face_normal, frame, p):
    """Place a light so its MIRROR reflection off the face reaches a camera on the
    route: L = P + d * reflect(v), with v = unit(C - P) and reflect(v) = 2(n.v)n - v.
    Cameras sit on the route line (bay-frame lateral 0) at camera_height_cm, at each
    candidate distance before the face; the first whose light lands in the height
    band and within the corridor + 6 m wins."""
    fwd3 = (frame["fwd"][0], frame["fwd"][1], 0.0)
    n = _unit(face_normal)
    if _dot(n, fwd3) > 0:                       # the face must look back at the approaching camera
        n = _mul(n, -1.0)
    ox, oy, _ = frame["origin"]
    along_face = (face_point[0] - ox) * fwd3[0] + (face_point[1] - oy) * fwd3[1]
    zlo, zhi = p["glint_z_range"]
    tried = []
    for dist in p["glint_cam_distances"]:
        s = along_face - dist
        cam = (ox + fwd3[0] * s, oy + fwd3[1] * s, float(p["camera_height_cm"]))
        v = _unit(_sub(cam, face_point))
        nv = _dot(n, v)
        if nv < 0.1:
            tried.append([dist, "grazing_or_behind"])
            continue
        r = _sub(_mul(n, 2.0 * nv), v)
        light = _add(face_point, _mul(r, float(p["glint_light_dist_cm"])))
        lat = -(light[0] - ox) * fwd3[1] + (light[1] - oy) * fwd3[0]
        if not (zlo <= light[2] <= zhi):
            tried.append([dist, "z %.0f" % light[2]])
            continue
        if abs(lat) > float(p["half_width_cm"]) + 600.0:
            tried.append([dist, "lateral %.0f" % lat])
            continue
        return {"light": light, "camera": cam, "camera_distance_cm": dist, "normal": n,
                "incidence_deg": math.degrees(math.acos(max(-1.0, min(1.0, nv)))), "tried": tried}
    return {"light": None, "tried": tried}


def centroid(points):
    if not points:
        return None
    n = float(len(points))
    return tuple(sum(p[i] for p in points) / n for i in range(3))


def bay_frame(here, before, after, half_width):
    """Origin at the bay centroid on the floor, fwd along the route (from the
    neighbours' centroids), right across it. Falls back to +X (P04 is straight)."""
    if here is None:
        raise RuntimeError("LOOK_BENCH_BAY_NOT_FOUND")
    a = before or here
    b = after or here
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length < 1.0:
        fwd = (1.0, 0.0)
        pitch = 0.0
    else:
        fwd = (dx / length, dy / length)
        pitch = length / (2.0 if (before and after) else 1.0)
    return {"origin": (here[0], here[1], 0.0), "fwd": fwd, "right": (-fwd[1], fwd[0]),
            "yaw_deg": math.degrees(math.atan2(fwd[1], fwd[0])),
            "pitch_cm": pitch, "half_width_cm": float(half_width)}


def to_world(frame, dx, dy, z):
    ox, oy, _ = frame["origin"]
    fx, fy = frame["fwd"]
    rx, ry = frame["right"]
    return (ox + fx * dx + rx * dy, oy + fy * dx + ry * dy, z)


def _box(label, centre, yaw, size_cm, color):
    return {"label": label, "kind": "mesh", "mesh": CUBE, "loc": centre, "yaw": yaw,
            "scale": tuple(v / 100.0 for v in size_cm),
            "material": {"mid_parent": EDGE_PARENT, "vectors": {"Color": tuple(color)}}}


def plan_spawns(frame, toggles, p, glint=None):
    """Plain spawn specs. Labels all start with SPAWN_PREFIX."""
    specs = []
    yaw = frame["yaw_deg"]
    pitch_cm = max(frame["pitch_cm"], 600.0)
    hw = frame["half_width_cm"]
    if "haze" in toggles:
        dens = p["haze_densities"]
        for i, d in enumerate(dens):
            dx = (-0.5 + i / max(1, len(dens) - 1)) * pitch_cm   # near -> far
            specs.append({"label": SPAWN_PREFIX + "HAZE_%d" % i, "kind": "fog",
                          "loc": to_world(frame, dx, 0.0, 250.0), "yaw": yaw,
                          "radius_cm": p["haze_radius_cm"], "density": d,
                          "height_falloff": p["haze_height_falloff"], "phase_g": p["haze_phase_g"]})
        specs.append({"label": SPAWN_PREFIX + "BEAM_BACK", "kind": "spot",
                      "loc": to_world(frame, 0.9 * pitch_cm, 0.15 * hw, 1100.0),
                      "rot": {"yaw": yaw + 180.0, "pitch": -28.0}, "cd": p["beam_cd"],
                      "color": (0.75, 0.85, 1.0), "inner": 6.0, "outer": 14.0,
                      "radius": 3000.0, "shadows": False, "vsi": 4.0})
    if "rake" in toggles:
        for side, sign, color in (("L", -1.0, (1.0, 0.82, 0.62)), ("R", 1.0, (0.62, 0.75, 1.0))):
            specs.append({"label": SPAWN_PREFIX + "RAKE_" + side, "kind": "spot",
                          "loc": to_world(frame, p["rake_x_offset_cm"], sign * (hw + 150.0),
                                          p["rake_height_cm"]),
                          "rot": {"yaw": yaw + (90.0 if sign < 0 else -90.0), "pitch": 6.0},
                          "cd": p["rake_cd"], "color": color, "inner": 8.0, "outer": 22.0,
                          "radius": 2.5 * hw, "shadows": True, "vsi": 1.5})
    floor = "floor_wet" if "floor_wet" in toggles else ("floor" if "floor" in toggles else None)
    if floor:
        length = 2.0 * pitch_cm
        specs.append({"label": SPAWN_PREFIX + "FLOOR", "kind": "mesh", "mesh": CUBE,
                      "loc": to_world(frame, 0.0, 0.0, 0.0), "yaw": yaw,
                      "scale": (length / 100.0, 2.0 * hw / 100.0, 0.01),
                      "material": {"mid_parent": FLOOR_PARENT,
                                   "scalars": dict(p["floor_wet_scalars"] if floor == "floor_wet"
                                                   else p["floor_scalars"])}})
        if floor == "floor_wet":
            for i, (dx, dy, diam) in enumerate(p["puddles"]):
                specs.append({"label": SPAWN_PREFIX + "PUDDLE_%d" % i, "kind": "mesh", "mesh": CYLINDER,
                              "loc": to_world(frame, dx, dy, 0.6), "yaw": yaw,
                              "scale": (diam / 100.0, 0.7 * diam / 100.0, 0.001),
                              "material": {"mid_parent": FLOOR_PARENT, "scalars": dict(p["puddle_scalars"])}})
    if "strobe" in toggles:
        specs.append({"label": SPAWN_PREFIX + "STROBE", "kind": "spot",
                      "loc": to_world(frame, 150.0, -0.6 * hw, 220.0),
                      "rot": {"yaw": yaw + 60.0, "pitch": -50.0}, "cd": p["strobe_cd"],
                      "color": (0.9, 0.95, 1.0), "inner": 20.0, "outer": 40.0, "radius": 1500.0,
                      "shadows": False, "vsi": 1.0, "strobe": True})
    if "glint" in toggles:
        if not glint or not glint.get("light"):
            raise RuntimeError("LOOK_BENCH_GLINT_UNRESOLVED|no mirror position for this bay")
        specs.append({"label": SPAWN_PREFIX + "GLINT", "kind": "point", "loc": tuple(glint["light"]),
                      "cd": p["glint_cd"], "color": (1.0, 0.9, 0.75), "radius": 2.5 * p["glint_light_dist_cm"],
                      "source_radius": p["glint_source_radius_cm"], "shadows": False, "vsi": 0.5})
        specs.append(_box(SPAWN_PREFIX + "GLINT_BULB", tuple(glint["light"]), yaw, (6.0, 6.0, 9.0),
                          (8.0, 6.5, 4.5, 1.0)))
    if "underpass" in toggles:
        steel, concrete = p["underpass_steel"], p["underpass_concrete"]
        deck_z = float(p["underpass_deck_z_cm"])
        col_y = hw + float(p["underpass_column_outset_cm"])
        for side, sign in (("L", -1.0), ("R", 1.0)):
            specs.append(_box(SPAWN_PREFIX + "UP_PIER_" + side, to_world(frame, 0.0, sign * col_y, 60.0), yaw,
                              (140.0, 140.0, 120.0), concrete))
            specs.append(_box(SPAWN_PREFIX + "UP_COLUMN_" + side,
                              to_world(frame, 0.0, sign * col_y, 120.0 + (deck_z - 120.0) / 2.0), yaw,
                              (40.0, 60.0, deck_z - 120.0), steel))
            for k, dx in (("A", -70.0), ("B", 70.0)):
                specs.append(_box(SPAWN_PREFIX + "UP_KNEE_%s_%s" % (side, k),
                                  to_world(frame, dx, sign * (col_y - 60.0), deck_z - 80.0), yaw,
                                  (120.0, 2.0, 120.0), steel))
        length = max(frame["pitch_cm"], 500.0)
        for side, sign in (("L", -1.0), ("R", 1.0)):
            specs.append(_box(SPAWN_PREFIX + "UP_STRINGER_" + side, to_world(frame, 0.0, sign * 250.0, deck_z),
                              yaw, (length, 30.0, 30.0), steel))
        ties = int(length // float(p["underpass_tie_every_cm"]))
        for i in range(ties):
            dx = -length / 2.0 + (i + 0.5) * float(p["underpass_tie_every_cm"])
            specs.append(_box(SPAWN_PREFIX + "UP_TIE_%02d" % i, to_world(frame, dx, 0.0, deck_z + 21.0), yaw,
                              (20.0, 2.0 * col_y, 12.0), steel))
        specs.append({"label": SPAWN_PREFIX + "UP_SHAFT", "kind": "spot",
                      "loc": to_world(frame, 0.0, 0.0, deck_z + 400.0), "rot": {"yaw": yaw, "pitch": -90.0},
                      "cd": p["underpass_shaft_cd"], "color": (0.85, 0.9, 1.0), "inner": 18.0, "outer": 34.0,
                      "radius": deck_z + 800.0, "shadows": True, "vsi": 3.0})
    return specs


def plan_light_changes(lights, toggles, p):
    """lights: {id: {"label", "type", "intensity", "visible", fields...}} -> [(id, field, value)]."""
    changes = []
    if "shadows" in toggles:
        keys = sorted((lid for lid, row in lights.items()
                       if row.get("visible") and row.get("type") == "spot" and row.get("intensity", 0) > 0),
                      key=lambda lid: (-lights[lid]["intensity"], lights[lid]["label"]))
        for lid in keys[:int(p["shadow_keys_max"])]:
            changes.append((lid, "cast_shadows", True))
            changes.append((lid, "cast_volumetric_shadow", True))
    if "haze" in toggles:
        for lid in sorted(lights):
            if lights[lid].get("visible"):
                changes.append((lid, "volumetric_scattering_intensity",
                                max(float(lights[lid]["volumetric_scattering_intensity"]), float(p["haze_vsi"]))))
    return changes


def strobe_on(now, start, hz, duty):
    phase = ((now - start) * hz) % 1.0
    return phase < duty


def write_record_verified(path, data, log):
    """Write, flush, fsync, re-read and compare BEFORE anything changes."""
    path = pathlib.Path(path)
    text = json.dumps(data, indent=1, sort_keys=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    back = json.loads(path.read_text(encoding="utf-8"))
    if back != json.loads(text):
        raise RuntimeError("LOOK_BENCH_RECORD_READBACK_MISMATCH|" + str(path))
    log("LOOK_BENCH_ORIGINALS_WRITTEN|path=%s" % path.as_posix())
    return path


class LookBench:
    """Engine-free bench logic. `adapter` supplies every world operation; the
    Unreal adapter is defined in make_unreal_adapter(), a fake in the harness."""

    def __init__(self, adapter, record_path, params=None, run_id=None):
        self.a = adapter
        self.p = dict(DEFAULTS)
        self.p.update(params or {})
        self.record_path = pathlib.Path(record_path)
        self.run_id = run_id or utc_stamp()
        self.record = None
        self.spawned = []           # adapter handles, destroyed by reference
        self.strobe = None
        self.strobe_start = 0.0
        self.applied = ()
        self.mid_readback = {}

    # ---- prepare: read, write originals, announce. Nothing changes here. ----
    def prepare(self):
        if self.a.world_kind() != "game":
            raise RuntimeError("LOOK_BENCH_NEEDS_PIE|the bench only runs on a PIE game world")
        leftovers = self.a.bench_actor_labels(SPAWN_PREFIX)
        if leftovers:
            raise RuntimeError("LOOK_BENCH_LEFTOVERS|%d|run RESTORE first" % len(leftovers))
        passage, bay = self.p["passage"], int(self.p["bay"])
        ids = self.a.find_lights(bay_prefixes(passage, bay))
        if not ids:
            raise RuntimeError("LOOK_BENCH_NO_BAY_LIGHTS|%s bay %d" % (passage, bay))
        lights = {lid: self.a.read_light(lid) for lid in ids}
        here = centroid([lights[l]["location"] for l in ids])
        before = centroid([self.a.read_light(l)["location"]
                           for l in self.a.find_lights(bay_prefixes(passage, bay - 1))]) if bay > 1 else None
        after = centroid([self.a.read_light(l)["location"]
                          for l in self.a.find_lights(bay_prefixes(passage, bay + 1))])
        frame = bay_frame(here, before, after, self.p["half_width_cm"])
        box = {"frame": frame, "half_len_cm": max(frame["pitch_cm"], 600.0), "half_width_cm": frame["half_width_cm"]}
        edges = self.a.edge_slots(box)
        face = self.a.wing_face(self.p["glint_mesh_contains"], frame) if hasattr(self.a, "wing_face") else None
        glint = None
        if face:
            glint = glint_solution(tuple(face["point"]), tuple(face["normal"]), frame, self.p)
            glint = {k: (list(v) if isinstance(v, tuple) else v) for k, v in glint.items()}
            glint["face"] = face
        if len(edges) > int(self.p["edge_max_components"]):
            raise RuntimeError("LOOK_BENCH_TOO_MANY_EDGE_SLOTS|%d" % len(edges))
        census = self.a.census()
        self.record = {
            "run": self.run_id, "written_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "world": self.a.world_name(), "passage": passage, "bay": bay,
            "params": {k: (list(v) if isinstance(v, tuple) else v) for k, v in self.p.items()},
            "frame": {k: (list(v) if isinstance(v, tuple) else v) for k, v in frame.items()},
            "lights": {lid: {k: lights[lid][k] for k in ("label",) + LIGHT_FIELDS} for lid in ids},
            "light_meta": {lid: {"type": lights[lid]["type"], "intensity": lights[lid]["intensity"],
                                 "visible": lights[lid]["visible"]} for lid in ids},
            "edge_slots": edges,
            "cvars": {STREAM_CVAR: self.a.get_cvar(STREAM_CVAR)},
            "census_before": census,
            "spawn_prefix": SPAWN_PREFIX,
            "glint": glint,
            "planned_spawns": [s["label"] for s in plan_spawns(
                frame, tuple(t for t in ALL_TOGGLES if t != "glint" or (glint and glint.get("light"))),
                self.p, glint)],
        }
        write_record_verified(self.record_path, self.record, self.a.log)
        self.a.note("record_written")
        n = len(self.record["planned_spawns"])
        self.a.log("LOOK_BENCH_ANNOUNCE|run=%s|world=PIE|%s bay %d|up to %d %s* actors (PIE world only) "
                   "for this run; restore at end|record=%s" % (self.run_id, passage, bay, n, SPAWN_PREFIX,
                                                               self.record_path.as_posix()))
        return self.record

    def _lights(self):
        out = {}
        for lid, row in self.record["lights"].items():
            meta = self.record["light_meta"][lid]
            out[lid] = dict(row, **meta)
        return out

    # ---- state changes ----
    def to_base(self):
        for handle in list(self.spawned):
            self.a.destroy(handle)
            self.spawned.remove(handle)
        self.strobe = None
        for lid, row in self.record["lights"].items():
            for field in LIGHT_FIELDS:
                if self.a.read_light(lid)[field] != row[field]:
                    self.a.set_light(lid, field, row[field])
        for slot in self.record["edge_slots"]:
            if self.a.slot_material(slot["id"], slot["slot"]) != slot["material"]:
                self.a.set_slot_material(slot["id"], slot["slot"], {"path": slot["material"]})
        self.applied = ()

    def apply(self, toggles, now=0.0):
        if self.record is None or not self.record_path.is_file():
            raise RuntimeError("LOOK_BENCH_NO_RECORD|originals must be on disk before any change")
        toggles = normalise_toggles(toggles)
        self.to_base()
        for lid, field, value in plan_light_changes(self._lights(), toggles, self.p):
            self.a.set_light(lid, field, value)
        frame = dict(self.record["frame"])
        frame["origin"] = tuple(frame["origin"])
        frame["fwd"] = tuple(frame["fwd"])
        frame["right"] = tuple(frame["right"])
        for spec in plan_spawns(frame, toggles, self.p, self.record.get("glint")):
            handle = self.a.spawn(spec)
            self.spawned.append(handle)
            if spec.get("strobe"):
                self.strobe = (handle, spec["cd"])
                self.strobe_start = now
            if "material" in spec and spec["material"].get("scalars"):
                self.mid_readback[spec["label"]] = self.a.material_readback(handle)
        if "edge" in toggles:
            for slot in self.record["edge_slots"]:
                self.a.set_slot_material(slot["id"], slot["slot"],
                                         {"mid_parent": EDGE_PARENT,
                                          "vectors": {"Color": tuple(self.p["edge_color"])}})
        self.applied = toggles
        self.a.log("LOOK_BENCH_STATE|run=%s|toggles=%s|spawned=%d" % (self.run_id, ",".join(toggles) or "base",
                                                                    len(self.spawned)))

    def tick(self, now):
        if self.strobe:
            handle, cd = self.strobe
            self.a.set_spawn_intensity(handle, cd if strobe_on(now, self.strobe_start, self.p["strobe_hz"],
                                                               self.p["strobe_duty"]) else 0.0)

    # ---- restore + exact verification ----
    def restore(self):
        self.to_base()
        problems = self.verify()
        if self.record:
            want = self.record["cvars"][STREAM_CVAR]
            if self.a.get_cvar(STREAM_CVAR) != want:
                self.a.set_cvar(STREAM_CVAR, want)
            if self.a.get_cvar(STREAM_CVAR) != want:
                problems.append("cvar %s" % STREAM_CVAR)
        return problems

    def verify(self):
        problems = []
        for lid, row in self.record["lights"].items():
            now = self.a.read_light(lid)
            for field in LIGHT_FIELDS:
                if now[field] != row[field]:
                    problems.append("%s %s %r != %r" % (row["label"], field, now[field], row[field]))
        for slot in self.record["edge_slots"]:
            got = self.a.slot_material(slot["id"], slot["slot"])
            if got != slot["material"]:
                problems.append("edge %s[%d] %s != %s" % (slot["id"], slot["slot"], got, slot["material"]))
        left = self.a.bench_actor_labels(SPAWN_PREFIX)
        if left:
            problems.append("leftover actors %s" % ",".join(sorted(left)))
        return problems


def restore_from_record(adapter, record_path):
    """RESTORE mode: crash recovery from the file alone."""
    record = json.loads(pathlib.Path(record_path).read_text(encoding="utf-8"))
    for handle in adapter.bench_actor_handles(SPAWN_PREFIX):
        adapter.destroy(handle)
    bench = LookBench(adapter, record_path, record.get("params"), record.get("run"))
    bench.record = record
    return bench.restore()


def frame_stats(deltas):
    """Editor tick deltas (s) -> ms stats. Includes Slate/editor cost; compare states, not absolutes."""
    ms = sorted(1000.0 * d for d in deltas if d > 0)
    if not ms:
        return {"n": 0}
    pick = lambda q: ms[min(len(ms) - 1, int(q * (len(ms) - 1) + 0.5))]
    return {"n": len(ms), "mean": sum(ms) / len(ms), "p50": pick(0.5), "p95": pick(0.95), "max": ms[-1],
            "over_40ms": sum(1 for m in ms if m > 40.0)}


def clip_plan(pass_frame, p):
    start = int(pass_frame - p["lead_seconds"] * TICKS_PER_SECOND)
    end = int(start + p["clip_seconds"] * TICKS_PER_SECOND)
    step = int(TICKS_PER_SECOND / float(p["clip_fps"]))
    return {"start": start, "end": end, "step": step,
            "frames_expected": int(math.ceil((end - start) / float(step)))}


# --------------------------------------------------------------------------
# Unreal side. Everything below runs only inside the editor.
# --------------------------------------------------------------------------

def make_unreal_adapter(unreal):
    """Return an adapter whose UE references live in this closure only."""
    editor_sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor_sub.get_game_world()
    handles = {}
    events = []

    def all_actors():
        return list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))

    def get(key):
        obj = handles.get(key)
        if obj is None:                      # RESTORE mode: a fresh adapter resolves by path
            obj = unreal.find_object(None, key.split(":", 1)[-1] if key.startswith(("spawn:", "sweep:")) else key)
            if obj is None:
                raise RuntimeError("LOOK_BENCH_UNRESOLVED|" + key)
            handles[key] = obj
        return obj

    def comp_of(actor):
        comps = list(actor.get_components_by_class(unreal.LightComponent))
        return comps[0] if len(comps) == 1 else None

    class A:
        def world_kind(self):
            return "game" if world is not None else None

        def world_name(self):
            return world.get_path_name() if world else None

        def note(self, event):
            events.append(event)

        def log(self, message):
            unreal.log(message)

        def census(self):
            maps = sorted(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
            content = sorted(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
            return {"maps": maps, "content": content}

        def find_lights(self, prefixes):
            ids = []
            for actor in all_actors():
                label = actor.get_actor_label()
                if label.startswith(tuple(prefixes)) and comp_of(actor) is not None:
                    lid = actor.get_path_name()
                    handles[lid] = actor
                    ids.append(lid)
            return sorted(ids)

        def read_light(self, lid):
            actor = get(lid)
            comp = comp_of(actor)
            loc = actor.get_actor_location()
            kind = ("spot" if isinstance(comp, unreal.SpotLightComponent) else
                    "rect" if isinstance(comp, unreal.RectLightComponent) else
                    "point" if isinstance(comp, unreal.PointLightComponent) else "other")
            return {"label": actor.get_actor_label(), "type": kind,
                    "location": (float(loc.x), float(loc.y), float(loc.z)),
                    "intensity": float(comp.get_editor_property("intensity")),
                    "visible": bool(comp.is_visible()),
                    "cast_shadows": bool(comp.get_editor_property("cast_shadows")),
                    "cast_volumetric_shadow": bool(comp.get_editor_property("cast_volumetric_shadow")),
                    "volumetric_scattering_intensity": float(
                        comp.get_editor_property("volumetric_scattering_intensity"))}

        def set_light(self, lid, field, value):
            events.append(("set_light", lid, field))
            comp = comp_of(get(lid))
            # UFUNCTION setters only: they mark render state, not the package.
            if field == "cast_shadows":
                comp.set_cast_shadows(bool(value))
            elif field == "cast_volumetric_shadow":
                comp.set_cast_volumetric_shadow(bool(value))
            elif field == "volumetric_scattering_intensity":
                comp.set_volumetric_scattering_intensity(float(value))
            else:
                raise RuntimeError("LOOK_BENCH_FIELD|" + field)

        def edge_slots(self, box):
            frame = box["frame"]
            ox, oy, _ = frame["origin"]
            fx, fy = frame["fwd"]
            rows = []
            for actor in all_actors():
                if actor.get_actor_label().startswith(SPAWN_PREFIX):
                    continue
                for comp in actor.get_components_by_class(unreal.StaticMeshComponent):
                    idx = comp.get_material_index("Edge")
                    if idx < 0:
                        continue
                    origin, _extent, _radius = unreal.SystemLibrary.get_component_bounds(comp)
                    dx, dy = origin.x - ox, origin.y - oy
                    along, across = dx * fx + dy * fy, -dx * fy + dy * fx
                    if abs(along) > box["half_len_cm"] or abs(across) > box["half_width_cm"] + 400.0:
                        continue
                    cid = comp.get_path_name()
                    handles[cid] = comp
                    mat = comp.get_material(idx)
                    rows.append({"id": cid, "slot": int(idx), "material": mat.get_path_name() if mat else None})
            return sorted(rows, key=lambda r: (r["id"], r["slot"]))

        def wing_face(self, contains, frame):
            """Front-face centre and normal of the instance nearest the bay of a flat whose
            mesh path contains `contains`. Flat V3 fronts face local -X (FlatV3Spec:179-180)."""
            ox, oy, _ = frame["origin"]
            best = None
            for actor in all_actors():
                for comp in actor.get_components_by_class(unreal.StaticMeshComponent):
                    mesh = comp.get_editor_property("static_mesh")
                    if mesh is None or contains not in mesh.get_path_name():
                        continue
                    xforms = []
                    if isinstance(comp, unreal.InstancedStaticMeshComponent):
                        for i in range(comp.get_instance_count()):
                            got = comp.get_instance_transform(i, True)
                            xforms.append(got[-1] if isinstance(got, tuple) else got)
                    else:
                        xforms.append(comp.get_world_transform())
                    bounds = mesh.get_bounds()
                    o, e = bounds.origin, bounds.box_extent
                    local = unreal.Vector(o.x - e.x, o.y, o.z)
                    for xf in xforms:
                        pt = unreal.MathLibrary.transform_location(xf, local)
                        d = math.hypot(pt.x - ox, pt.y - oy)
                        if best is None or d < best[0]:
                            nrm = unreal.MathLibrary.transform_direction(xf, unreal.Vector(-1.0, 0.0, 0.0))
                            best = (d, {"point": [float(pt.x), float(pt.y), float(pt.z)],
                                        "normal": [float(nrm.x), float(nrm.y), float(nrm.z)],
                                        "mesh": mesh.get_path_name(), "component": comp.get_path_name(),
                                        "distance_from_bay_cm": float(d)})
            if best is None or best[0] > 3000.0:
                return None
            return best[1]

        def camera_location(self):
            cam = unreal.GameplayStatics.get_player_camera_manager(world, 0)
            loc = cam.get_camera_location() if cam else None
            return [float(loc.x), float(loc.y), float(loc.z)] if loc else None

        def slot_material(self, cid, slot):
            mat = get(cid).get_material(slot)
            return mat.get_path_name() if mat else None

        def _material(self, spec):
            if "path" in spec:
                return unreal.load_object(None, spec["path"]) if spec["path"] else None
            parent = unreal.load_object(None, spec["mid_parent"])
            mid = unreal.KismetMaterialLibrary.create_dynamic_material_instance(world, parent)
            for name, value in spec.get("scalars", {}).items():
                mid.set_scalar_parameter_value(name, float(value))
            for name, value in spec.get("vectors", {}).items():
                mid.set_vector_parameter_value(name, unreal.LinearColor(*value))
            return mid

        def set_slot_material(self, cid, slot, spec):
            events.append(("set_slot", cid, slot))
            get(cid).set_material(slot, self._material(spec))

        def spawn(self, spec):
            events.append(("spawn", spec["label"]))
            loc = unreal.Vector(*spec["loc"])
            if spec["kind"] == "spot":
                rot = unreal.Rotator(roll=0.0, pitch=spec["rot"]["pitch"], yaw=spec["rot"]["yaw"])
                cls = unreal.SpotLight
            elif spec["kind"] == "point":
                rot = unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0)
                cls = unreal.PointLight
            elif spec["kind"] == "fog":
                rot = unreal.Rotator(roll=0.0, pitch=0.0, yaw=spec["yaw"])
                cls = unreal.LocalFogVolume
            else:
                rot = unreal.Rotator(roll=0.0, pitch=0.0, yaw=spec["yaw"])
                cls = unreal.StaticMeshActor
            transform = unreal.Transform(location=loc, rotation=rot)
            actor = unreal.GameplayStatics.begin_deferred_actor_spawn_from_class(
                world, cls, transform, unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN, None)
            actor = unreal.GameplayStatics.finish_spawning_actor(actor, transform)
            if actor.get_world() != world:
                actor.destroy_actor()
                raise RuntimeError("LOOK_BENCH_SPAWN_NOT_IN_PIE|" + spec["label"])
            actor.set_actor_label(spec["label"], False)
            if spec["kind"] == "spot":
                comp = actor.get_component_by_class(unreal.SpotLightComponent)
                comp.set_mobility(unreal.ComponentMobility.MOVABLE)
                comp.set_intensity_units(unreal.LightUnits.CANDELAS)
                comp.set_intensity(float(spec["cd"]))
                comp.set_light_color(unreal.LinearColor(*spec["color"], 1.0), True)
                comp.set_inner_cone_angle(float(spec["inner"]))
                comp.set_outer_cone_angle(float(spec["outer"]))
                comp.set_attenuation_radius(float(spec["radius"]))
                comp.set_cast_shadows(bool(spec["shadows"]))
                comp.set_volumetric_scattering_intensity(float(spec["vsi"]))
            elif spec["kind"] == "point":
                comp = actor.get_component_by_class(unreal.PointLightComponent)
                comp.set_mobility(unreal.ComponentMobility.MOVABLE)
                comp.set_intensity_units(unreal.LightUnits.CANDELAS)
                comp.set_intensity(float(spec["cd"]))
                comp.set_light_color(unreal.LinearColor(*spec["color"], 1.0), True)
                comp.set_attenuation_radius(float(spec["radius"]))
                comp.set_source_radius(float(spec["source_radius"]))
                comp.set_cast_shadows(bool(spec["shadows"]))
                comp.set_volumetric_scattering_intensity(float(spec["vsi"]))
            elif spec["kind"] == "fog":
                comp = actor.get_component_by_class(unreal.LocalFogVolumeComponent)
                scale = float(spec["radius_cm"]) / 500.0     # GetBaseVolumeSize() = 500 (LocalFogVolumeComponent.h:74-76)
                actor.set_actor_scale3d(unreal.Vector(scale, scale, scale * 0.6))
                comp.set_radial_fog_extinction(float(spec["density"]))
                comp.set_height_fog_extinction(float(spec["density"]))
                comp.set_height_fog_falloff(float(spec["height_falloff"]))
                comp.set_fog_phase_g(float(spec["phase_g"]))
            else:
                comp = actor.static_mesh_component
                comp.set_mobility(unreal.ComponentMobility.MOVABLE)
                comp.set_static_mesh(unreal.load_object(None, spec["mesh"]))
                actor.set_actor_scale3d(unreal.Vector(*spec["scale"]))
                comp.set_material(0, self._material(spec["material"]))
            handle = "spawn:" + spec["label"]
            handles[handle] = actor
            return handle

        def material_readback(self, handle):
            actor = handles[handle]
            comp = actor.static_mesh_component
            mid = comp.get_material(0)
            out = {}
            for name in ("Roughness_Low", "Roughness_High", "Roughness_Add_Grunge"):
                try:
                    out[name] = float(mid.get_scalar_parameter_value(name))
                except Exception as exc:          # parameter absent on this parent
                    out[name] = "ERR " + repr(exc)
            return out

        def set_spawn_intensity(self, handle, value):
            handles[handle].get_component_by_class(unreal.SpotLightComponent).set_intensity(float(value))

        def destroy(self, handle):
            actor = handles.pop(handle)
            actor.destroy_actor()

        def bench_actor_labels(self, prefix):
            return sorted(a.get_actor_label() for a in all_actors() if a.get_actor_label().startswith(prefix))

        def bench_actor_handles(self, prefix):
            out = []
            for actor in all_actors():
                if actor.get_actor_label().startswith(prefix):
                    key = "sweep:" + actor.get_path_name()
                    handles[key] = actor
                    out.append(key)
            return out

        def get_cvar(self, name):
            return int(unreal.SystemLibrary.get_console_variable_int_value(name))

        def set_cvar(self, name, value):
            unreal.SystemLibrary.execute_console_command(world, "%s %s" % (name, value))

        def console(self, command):
            unreal.SystemLibrary.execute_console_command(world, command)

        def show_root(self):
            roots = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot))
            if len(roots) != 1 or not roots[0].sequence_player:
                raise RuntimeError("LOOK_BENCH_NO_SHOW_ROOT")
            return roots[0]

        def bay_pass_frame(self, passage, bay):
            """Same derivation as lighting_looks_p04_driver.build_plan, for any bay."""
            n = int(passage[1:])
            label = "Passage %d" % n
            root = self.show_root()
            segs = [s for s in root.transport.segments
                    if s.type == unreal.InfinityCueType.WING_PAIR and str(s.label) == label]
            if len(segs) != 1:
                raise RuntimeError("LOOK_BENCH_SEGMENT|" + label)
            show = unreal.load_asset(SHOW_PATH)
            rows = [r for r in show.get_editor_property("passage_settings")
                    if str(r.get_editor_property("label")) == label]
            if len(rows) != 1:
                raise RuntimeError("LOOK_BENCH_SETTINGS|" + label)
            g = lambda v: str(unreal.GuidLibrary.conv_guid_to_string(v)).replace("-", "").upper()
            cues = list(show.get_editor_property("cues"))
            first = [i for i, c in enumerate(cues) if g(c.get_editor_property("cue_guid")) ==
                     g(rows[0].get_editor_property("first_cue_guid"))]
            if len(first) != 1:
                raise RuntimeError("LOOK_BENCH_FIRST_CUE")
            frame = segs[0].start_frame.value + int(rows[0].get_editor_property("lead_in_frames").value)
            for ordinal in range(bay - 1):
                cue = cues[first[0] + ordinal]
                frame += int(cue.get_editor_property("wing_pair").get_editor_property("interval_to_next").value)
            expect = "P%02d Wing %03d" % (n, bay)
            if str(cues[first[0] + bay - 1].get_editor_property("label")) != expect:
                raise RuntimeError("LOOK_BENCH_BAY_LABEL|" + expect)
            return frame, segs[0].start_frame.value, segs[0].end_frame.value

        def transport_scrub(self, frame):
            root = self.show_root()
            root.sequence_player.pause()
            root.transport.scrub_to_master_frame(unreal.FrameNumber(int(frame)))

        def transport_play(self):
            root = self.show_root()
            root.sequence_player.set_play_rate(1.0)
            root.transport.play_forward_to_boundary()

        def transport_pause(self):
            self.show_root().sequence_player.pause()

        def transport_frame(self):
            return int(self.show_root().transport.get_current_master_frame().value)

    adapter = A()
    adapter.events = events
    return adapter


def arm(unreal, mode, toggles, states, params):
    if hasattr(builtins, HANDLE_NAME):
        raise RuntimeError("LOOK_BENCH_ALREADY_ARMED")
    adapter = make_unreal_adapter(unreal)
    if adapter.world_kind() != "game":
        raise RuntimeError("LOOK_BENCH_NEEDS_PIE|start PIE first (the bench never starts or ends it)")
    run_id = utc_stamp()
    run_dir = BASE / "LookBench" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    bench = LookBench(adapter, run_dir / "look_bench_originals.json", params, run_id)
    bench.prepare()
    p = bench.p
    if states is None:
        states = default_states(bool(bench.record.get("glint") and bench.record["glint"].get("light")))
    st = {"run": run_id, "mode": mode, "run_dir": run_dir.as_posix(), "phase": "start", "index": 0,
          "states": [[n, list(t)] for n, t in states], "clips": [], "errors": [], "ticks": 0}
    setattr(builtins, STATE_NAME, st)
    if mode == "CAPTURE":
        pass_frame, seg_start, seg_end = adapter.bay_pass_frame(p["passage"], int(p["bay"]))
        st["clip"] = clip_plan(pass_frame, p)
        if st["clip"]["start"] < seg_start or st["clip"]["end"] > seg_end:
            raise RuntimeError("LOOK_BENCH_CLIP_OUTSIDE_PASSAGE")

    def persist():
        (run_dir / "look_bench_result.json").write_text(json.dumps(st, indent=1), encoding="utf-8")

    def finish():
        st["phase"] = "finishing"
        try:
            problems = bench.restore()
        except Exception:
            problems = ["restore raised: " + traceback.format_exc()]
        census = adapter.census()
        st["restore_problems"] = problems
        st["census_after"] = census
        if census != bench.record["census_before"]:
            problems.append("editor census changed %r -> %r" % (bench.record["census_before"], census))
        st["mid_readback"] = bench.mid_readback
        st["phase"] = "done"
        st["ok"] = not problems and not st["errors"]
        persist()
        unreal.unregister_slate_post_tick_callback(getattr(builtins, HANDLE_NAME))
        delattr(builtins, HANDLE_NAME)
        if st["ok"]:
            unreal.log("LOOK_BENCH_OK|run=%s|mode=%s|states=%d|run_dir=%s" % (run_id, mode, len(states),
                                                                           run_dir.as_posix()))
        else:
            unreal.log_error("LOOK_BENCH_FAILED|run=%s|problems=%r|errors=%d" % (run_id, problems,
                                                                             len(st["errors"])))

    def tick(_delta):
        if st.get("inside") or st["phase"] in ("done", "finishing"):
            return
        st["inside"] = True
        try:
            now = time.monotonic()
            if adapter.world_kind() != "game":
                raise RuntimeError("LOOK_BENCH_PIE_ENDED")
            bench.tick(now)
            st["ticks"] += 1
            if mode == "HOLD":
                if st["phase"] == "start":
                    bench.apply(toggles, now)
                    st["phase"], st["until"] = "hold", now + float(p["hold_seconds"])
                elif now >= st["until"]:
                    finish()
                return
            # CAPTURE
            clip = st["clip"]
            if st["phase"] == "start":
                if st["index"] >= len(states):
                    finish()
                    return
                name, tset = states[st["index"]]
                adapter.set_cvar(STREAM_CVAR, 1)
                bench.apply(tset, now)
                adapter.transport_scrub(clip["start"])
                st.update(phase="settle", t0=now, settle_ticks=0, reposed=False)
                return
            if st["phase"] == "settle":
                st["settle_ticks"] += 1
                half = float(p["settle_seconds"]) / 2.0
                if not st["reposed"] and now - st["t0"] >= half:
                    adapter.transport_scrub(clip["start"])     # re-pose: a jump's first frame is stale
                    st["reposed"] = True
                    st["deltas"] = []
                elif st["reposed"]:
                    st["deltas"].append(float(_delta))        # static-pose frame time with this state on
                if now - st["t0"] < float(p["settle_seconds"]) or st["settle_ticks"] < int(p["settle_ticks"]):
                    return
                name, _ = states[st["index"]]
                st["current"] = {"state": name, "frames": [], "dir": (run_dir / name).as_posix(),
                                 "frame_ms": frame_stats(st.pop("deltas", []))}
                pathlib.Path(st["current"]["dir"]).mkdir(parents=True, exist_ok=True)
                st["next"] = clip["start"]
                adapter.transport_play()
                st["phase"] = "clip"
                return
            if st["phase"] == "clip":
                frame = adapter.transport_frame()
                if frame >= clip["end"]:
                    adapter.transport_pause()
                    st["clips"].append(st.pop("current"))
                    st["index"] += 1
                    st["phase"] = "start"
                    persist()
                    return
                if frame >= st["next"]:
                    cur = st["current"]
                    path = pathlib.Path(cur["dir"]) / ("frame_%04d.png" % len(cur["frames"]))
                    w, h = p["resolution"]
                    adapter.console('HighResShot %dx%d filename="%s"' % (w, h, path.as_posix()))
                    cur["frames"].append({"master_frame": frame, "path": path.as_posix(),
                                          "camera": adapter.camera_location(),
                                          "strobe_on": bool(bench.strobe and strobe_on(
                                              now, bench.strobe_start, p["strobe_hz"], p["strobe_duty"]))})
                    st["next"] = frame + clip["step"]
        except Exception:
            st["errors"].append(traceback.format_exc())
            try:
                finish()
            except Exception:
                st["errors"].append(traceback.format_exc())
                persist()
                if hasattr(builtins, HANDLE_NAME):
                    unreal.unregister_slate_post_tick_callback(getattr(builtins, HANDLE_NAME))
                    delattr(builtins, HANDLE_NAME)
        finally:
            st["inside"] = False

    persist()
    setattr(builtins, HANDLE_NAME, unreal.register_slate_post_tick_callback(tick))
    unreal.log("LOOK_BENCH_ARMED|run=%s|mode=%s|run_dir=%s" % (run_id, mode, run_dir.as_posix()))
    return run_dir


def main():
    import unreal
    g = globals()
    mode = g.get("BENCH_MODE", "PROBE")
    params = dict(g.get("BENCH_PARAMS", {}))
    if mode == "RESTORE":
        record = g.get("BENCH_RECORD") or sorted((BASE / "LookBench").glob("*/look_bench_originals.json"))[-1]
        problems = restore_from_record(make_unreal_adapter(unreal), record)
        if problems:
            unreal.log_error("LOOK_BENCH_RESTORE_FAILED|%r" % problems)
        else:
            unreal.log("LOOK_BENCH_RESTORE_OK|record=%s" % pathlib.Path(record).as_posix())
        return
    if mode == "PROBE":
        adapter = make_unreal_adapter(unreal)
        if adapter.world_kind() != "game":
            raise RuntimeError("LOOK_BENCH_NEEDS_PIE")
        run_id = utc_stamp()
        out = BASE / ("look_bench_probe_%s.json" % run_id)
        bench = LookBench(adapter, out, params, run_id)
        bench.prepare()                       # reads + writes the file; changes nothing
        unreal.log("LOOK_BENCH_PROBE_OK|lights=%d|edge_slots=%d|path=%s" % (
            len(bench.record["lights"]), len(bench.record["edge_slots"]), out.as_posix()))
        return
    toggles = tuple(g.get("BENCH_TOGGLES", ("shadows", "haze", "rake", "floor_wet", "strobe", "edge")))
    states = g.get("BENCH_STATES")
    arm(unreal, mode, toggles, [(n, tuple(t)) for n, t in states] if states else None, params)


if __name__ == "__main__" or "BENCH_MODE" in globals():
    main()
