"""READ-ONLY PIE probe: why is P02's second half black? (7 Oct). Runs INSIDE the conductor's own PIE
(conductor_pie_begin.py first). Never starts/ends PIE, never quits, never saves, never spawns, never sets a light
or volume property. The only state it touches is the Master transport: it scrubs to each probe frame (the same
ScrubToMasterFrame route passage_stills.py uses) and scrubs back to the frame it found at the end.

Per fraction of the "Passage 2" segment (default 0.4 = lit control, 0.6, 0.8 = black):
  scrub -> wait SETTLE_S -> re-scrub (a jump's first frame can be stale) -> wait SETTLE_S -> READ:
  * camera pose (PlayerCameraManager) + the view target's CameraComponent post-process exposure overrides;
  * camera route distance = local X in the Passage 02 actor frame (route is straight since P02STR-20261007-015540,
    spline points (0,0,0)->(11857.8,0,0) in p02_straighten_record.json after.spline; checked live: spline points);
  * EVERY light component on Passage 02's ManagedAttachmentActors within [-AHEAD_BEHIND_CM, AHEAD_CM] along the
    route of the camera: label, route distance, along/lateral vs camera, is_visible, intensity, units, attenuation,
    cast_shadows, forward vector, "faces_corridor" (forward has a component toward the route axis), and the Show's
    EXPECTED drama scale computed offline from p02_rig_pattern_record.json after_cue_rows (+ p02_brighten_record.json
    after values) with the same formula as InfinityStageLightDrama.cpp:24-60 (stutter ignored);
    MISMATCH rows = expected lit but component invisible/zero, or expected dark but visible;
  * Structure lights (InfinityStageStructureActor light components) within RADIUS_CM: count visible / total;
  * every PostProcessVolume: label, enabled, unbound, blend_weight, priority, camera inside (EncompassesPoint, else
    AABB), auto-exposure overrides;
  * every ExponentialHeightFog: density, second density, volumetric fog.
Decision rule (printed as VERDICT): many MISMATCH rows -> drama/state bug (hyp a); lights visible at authored
intensity but camera inside a bounded PPV with weight > 0 and pinned EV -> exposure (hyp c); lamps visible, as
expected, but few within reach / not facing the corridor -> score + rig-pattern design (hyp d).

Markers: PROBE_P02_LIGHTS_START|run=..  PROBE_P02_LIGHTS_FRAME|run=..|f=..|..  PROBE_P02_LIGHTS_OK|run=..|path=..
         PROBE_P02_LIGHTS_FAILED|run=..|reason=..
Unreal objects are fetched fresh inside functions; module globals hold plain data only.
"""
from __future__ import annotations

import builtins
import datetime
import json
import math
import pathlib
import re
import time
import traceback

import unreal

BASE = pathlib.Path("E:/PussStage/Saved/CodexConductor")
OUT_DIR = BASE / "ProbeP02Lights"
FRACTIONS = [0.4, 0.6, 0.8]
SEGMENT_LABEL = "Passage 2"
PASSAGE_LABEL_RE = re.compile(r"Passage 02")
SETTLE_S = 1.5
AHEAD_CM = 4000.0
AHEAD_BEHIND_CM = 1500.0
RADIUS_CM = 5000.0
HANDLE_NAME = "PUSS_P02LIGHTS_HANDLE"
RUN_ID = "P02LIGHTS-" + datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")


def _log(msg):
    unreal.log(msg)


def _fail(reason):
    unreal.log_error("PROBE_P02_LIGHTS_FAILED|run=%s|reason=%s" % (RUN_ID, reason))


# ---- offline expectations (plain data) ------------------------------------------------------------
def _enum_name(v):
    s = str(v)
    m = re.search(r"\.([A-Z_]+):", s)
    return m.group(1) if m else s


def load_expected():
    rig = json.loads((BASE / "p02_rig_pattern_record.json").read_text(encoding="utf-8"))
    exp = {}
    for rows in rig["after_cue_rows"].values():
        for r in rows:
            if "LIGHT" not in str(r.get("kind")):
                continue
            L = r["lighting"]
            D = L["drama"]
            exp[r["label"]] = {"guid": r["guid"], "enabled": r["enabled"], "intensity": L["intensity"],
                               "units": _enum_name(L["intensity_units"]), "strike": bool(D["strike_on_approach"]),
                               "strike_cm": D["strike_distance_cm"], "ramp_cm": D["strike_ramp_cm"],
                               "unstruck": D["unstruck_intensity_scale"], "after_pass": _enum_name(D["after_pass"]),
                               "after_cm": D["after_pass_distance_cm"], "decay_cm": D["decay_distance_cm"]}
    try:
        br = json.loads((BASE / "p02_brighten_record.json").read_text(encoding="utf-8"))
        if br.get("status") == "saved_readback_verified":
            for t in br["plan"]["targets"]:
                if t["attachment_label"] in exp:
                    exp[t["attachment_label"]]["intensity"] = t["after"]
                    exp[t["attachment_label"]]["brightened"] = True
    except Exception:
        pass
    return exp


def expected_scale(e, ahead_cm):
    """InfinityStageLightDrama.cpp:24-60 without the ignition stutter (it only dips during the ramp)."""
    if not e or not e["strike"]:
        return 1.0
    unst = min(max(float(e["unstruck"]), 0.0), 1.0)
    start = max(0.0, float(e["strike_cm"]))
    level = unst
    if ahead_cm <= start:
        p = min(max((start - ahead_cm) / max(1.0, float(e["ramp_cm"])), 0.0), 1.0)
        level = unst + (1.0 - unst) * (p * p * (3 - 2 * p))
    past = -ahead_cm - max(0.0, float(e["after_cm"]))
    if past > 0.0:
        if e["after_pass"] == "EXTINGUISH":
            level = unst
        elif e["after_pass"] == "DECAY":
            f = min(max(past / max(1.0, float(e["decay_cm"])), 0.0), 1.0)
            level = level + (unst - level) * f
    return level


# ---- live reads (Unreal objects only inside these functions) ----------------------------------------
def game_world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


def show_root(world):
    roots = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot))
    if len(roots) != 1 or not roots[0].sequence_player:
        raise RuntimeError("show_roots=%d" % len(roots))
    return roots[0]


def segment(world):
    segs = [s for s in list(show_root(world).transport.segments)
            if s.type == unreal.InfinityCueType.WING_PAIR and str(s.label) == SEGMENT_LABEL]
    if len(segs) != 1:
        raise RuntimeError("segments named %s: %d" % (SEGMENT_LABEL, len(segs)))
    return int(segs[0].start_frame.value), int(segs[0].end_frame.value)


def scrub(world, frame):
    root = show_root(world)
    root.sequence_player.pause()
    return str(root.transport.scrub_to_master_frame(unreal.FrameNumber(int(frame))))


def cur_frame(world):
    return int(show_root(world).transport.get_current_master_frame().value)


def _v(vec):
    return [round(float(vec.x), 1), round(float(vec.y), 1), round(float(vec.z), 1)]


def _get(obj, name, default=None):
    try:
        return obj.get_editor_property(name)
    except Exception:
        return default


def _visible(comp):
    try:
        return bool(comp.is_visible())
    except Exception:
        return _get(comp, "visible")


def exposure_of(settings):
    out = {}
    for n in ("auto_exposure_method", "auto_exposure_min_brightness", "auto_exposure_max_brightness",
              "auto_exposure_bias"):
        if _get(settings, "override_" + n):
            out[n] = str(_get(settings, n))
    return out


def read_state(world, expected):
    snap = {"frame": cur_frame(world)}
    cam = unreal.GameplayStatics.get_player_camera_manager(world, 0)
    cl, cr = cam.get_camera_location(), cam.get_camera_rotation()
    snap["camera"] = {"loc": _v(cl), "yaw": round(float(cr.yaw), 2), "pitch": round(float(cr.pitch), 2)}
    try:
        vt = cam.get_view_target()
        cc = vt.get_component_by_class(unreal.CameraComponent) if vt else None
        if cc:
            snap["camera"]["view_target"] = str(vt.get_actor_label())
            snap["camera"]["pp_blend_weight"] = _get(cc, "post_process_blend_weight")
            snap["camera"]["pp_exposure"] = exposure_of(_get(cc, "post_process_settings"))
    except Exception:
        snap["camera"]["view_target_error"] = traceback.format_exc(limit=1)

    passages = [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStagePassageActor)
                if PASSAGE_LABEL_RE.search(str(a.get_actor_label()))]
    if len(passages) != 1:
        raise RuntimeError("Passage 02 actors in PIE: %d" % len(passages))
    pa = passages[0]
    xf = pa.get_actor_transform()
    route = _get(pa, "route")
    spline_pts = []
    if route is not None:
        for i in range(route.get_number_of_spline_points()):
            spline_pts.append(_v(route.get_location_at_spline_point(i, unreal.SplineCoordinateSpace.LOCAL)))
    snap["route"] = {"actor_loc": _v(pa.get_actor_location()), "actor_yaw": round(float(pa.get_actor_rotation().yaw), 3),
                     "spline_local": spline_pts}
    straight = len(spline_pts) == 2 and all(abs(p[1]) < 1 and abs(p[2]) < 1 for p in spline_pts)
    snap["route"]["straight_local_x"] = straight

    def local(loc):
        p = unreal.MathLibrary.inverse_transform_location(xf, loc)
        return float(p.x), float(p.y), float(p.z)

    cam_d, cam_lat, _ = local(cl)
    snap["camera"]["route_distance_cm"] = round(cam_d, 1)
    snap["camera"]["route_lateral_cm"] = round(cam_lat, 1)

    lamps, mismatches = [], []
    for actor in list(_get(pa, "managed_attachment_actors", []) or []):
        if actor is None:
            continue
        comps = list(actor.get_components_by_class(unreal.LightComponent))
        if not comps:
            continue
        label = str(actor.get_actor_label())
        for comp in comps:
            wl = comp.get_world_location()
            d, lat, z = local(wl)
            ahead = d - cam_d
            if ahead < -AHEAD_BEHIND_CM or ahead > AHEAD_CM:
                continue
            fwd = comp.get_forward_vector()
            fl = unreal.MathLibrary.inverse_transform_direction(xf, fwd)
            toward_axis = (-lat) * float(fl.y) > 0 if abs(lat) > 1 else True
            vis = _visible(comp)
            inten = _get(comp, "intensity")
            e = expected.get(label)
            exp_scale = expected_scale(e, ahead) if e else None
            row = {"label": label, "component": comp.get_name(), "class": comp.get_class().get_name(),
                   "route_d": round(d, 1), "ahead": round(ahead, 1), "lat": round(lat, 1), "z": round(z, 1),
                   "visible": vis, "intensity": None if inten is None else round(float(inten), 3),
                   "units": str(_get(comp, "intensity_units")), "atten": _get(comp, "attenuation_radius"),
                   "shadows": _get(comp, "cast_shadows"), "fwd_local": [round(float(fl.x), 2), round(float(fl.y), 2),
                                                                         round(float(fl.z), 2)],
                   "faces_corridor": toward_axis}
            if e:
                row["exp"] = {"intensity": e["intensity"], "scale": round(exp_scale, 3), "strike": e["strike"],
                              "after_pass": e["after_pass"], "enabled": e["enabled"],
                              "brightened": bool(e.get("brightened"))}
                exp_lit = e["enabled"] and e["intensity"] * exp_scale > 1e-3
                live_lit = bool(vis) and inten is not None and float(inten) > 1e-3
                if exp_lit != live_lit or (live_lit and abs(float(inten) - e["intensity"] * exp_scale) >
                                           max(1.0, 0.05 * e["intensity"] * exp_scale)):
                    row["MISMATCH"] = True
                    mismatches.append(label)
            lamps.append(row)
    lamps.sort(key=lambda r: r["ahead"])
    snap["lamps"] = lamps
    snap["lamp_counts"] = {"in_window": len(lamps), "visible": sum(1 for r in lamps if r["visible"]),
                           "visible_facing_corridor": sum(1 for r in lamps if r["visible"] and r["faces_corridor"]),
                           "inside_lateral_900": sum(1 for r in lamps if r["visible"] and abs(r["lat"]) < 900),
                           "mismatch": len(mismatches)}
    snap["mismatches"] = mismatches

    struct = {"total": 0, "visible": 0}
    for sa in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageStructureActor):
        for comp in sa.get_components_by_class(unreal.LightComponent):
            loc = comp.get_world_location()
            if math.dist(_v(loc), _v(cl)) <= RADIUS_CM:
                struct["total"] += 1
                struct["visible"] += 1 if _visible(comp) else 0
    snap["structure_lights_within_radius"] = struct

    ppvs = []
    for v in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.PostProcessVolume):
        inside = None
        try:
            r = v.encompasses_point(cl, 0.0)
            inside = bool(r[0] if isinstance(r, tuple) else r)
        except Exception:
            try:
                o, ext = v.get_actor_bounds(False)
                inside = all(abs(getattr(cl, a) - getattr(o, a)) <= getattr(ext, a) for a in ("x", "y", "z"))
                inside = "aabb:%s" % inside
            except Exception:
                inside = "unknown"
        ppvs.append({"label": str(v.get_actor_label()), "enabled": _get(v, "enabled"), "unbound": _get(v, "unbound"),
                     "blend_weight": _get(v, "blend_weight"), "priority": _get(v, "priority"),
                     "camera_inside": inside, "exposure": exposure_of(_get(v, "settings"))})
    snap["ppv"] = ppvs
    fogs = []
    for f in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ExponentialHeightFog):
        c = f.get_component_by_class(unreal.ExponentialHeightFogComponent)
        if c:
            fogs.append({"label": str(f.get_actor_label()), "density": _get(c, "fog_density"),
                         "second": _get(c, "second_fog_density"), "volumetric": _get(c, "volumetric_fog"),
                         "visible": _visible(c)})
    snap["fog"] = fogs
    return snap


def verdict(snaps):
    out = []
    for s in snaps:
        c = s.get("lamp_counts", {})
        pinned = [p["label"] for p in s.get("ppv", []) if p["camera_inside"] in (True, "aabb:True")
                  and not p["unbound"] and (p["blend_weight"] or 0) > 0 and p["exposure"]]
        if c.get("mismatch", 0) >= 3:
            v = "A_DRAMA_STATE(%d mismatches)" % c["mismatch"]
        elif pinned:
            v = "C_BOUNDED_PPV(%s)" % ",".join(pinned)
        else:
            v = "D_DESIGN(visible=%d facing=%d inside900=%d)" % (c.get("visible", 0), c.get("visible_facing_corridor", 0),
                                                                c.get("inside_lateral_900", 0))
        out.append("f=%s:%s" % (s.get("fraction"), v))
    return out


def arm():
    world = game_world()
    if world is None:
        _fail("no_pie (start conductor_pie_begin.py first)")
        return
    handles = [n for n in dir(builtins) if n.startswith("PUSS_") and n.endswith("_HANDLE")]
    if handles:
        _fail("tick_armed:" + ",".join(handles))
        return
    world_name = world.get_path_name()
    expected = load_expected()
    start, end = segment(world)
    original = cur_frame(world)
    plan = [{"fraction": f, "frame": int(round(start + f * (end - start)))} for f in FRACTIONS]
    _log("PROBE_P02_LIGHTS_START|run=%s|segment=%d-%d|original=%d|expected_rows=%d" % (
        RUN_ID, start, end, original, len(expected)))
    st = {"i": 0, "phase": "scrub1", "t": time.monotonic(), "snaps": [], "inside": False, "done": False}

    def finish(reason=None):
        st["done"] = True
        restore = None
        try:
            w = game_world()
            if w is not None and w.get_path_name() == world_name:
                restore = {"result": scrub(w, original), "landed": cur_frame(w), "frame": original}
        except Exception:
            restore = {"error": traceback.format_exc(limit=2)}
        try:
            unreal.unregister_slate_post_tick_callback(getattr(builtins, HANDLE_NAME))
        except Exception:
            pass
        if hasattr(builtins, HANDLE_NAME):
            delattr(builtins, HANDLE_NAME)
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / (RUN_ID + ".json")
        doc = {"run": RUN_ID, "segment": [start, end], "original_frame": original, "restore": restore,
               "plan": plan, "snaps": st["snaps"], "verdict": verdict(st["snaps"]), "error": reason}
        path.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
        back = json.loads(path.read_text(encoding="utf-8"))
        if reason or back.get("run") != RUN_ID or len(back["snaps"]) != len(plan):
            _fail("%s|path=%s" % (reason or "incomplete", path.as_posix()))
        else:
            _log("PROBE_P02_LIGHTS_OK|run=%s|verdict=%s|path=%s" % (RUN_ID, ";".join(doc["verdict"]), path.as_posix()))

    def tick(_dt=0.0):
        if st["inside"] or st["done"]:
            return
        st["inside"] = True
        try:
            w = game_world()
            if w is None or w.get_path_name() != world_name:
                finish("pie_ended")
                return
            item = plan[st["i"]]
            now = time.monotonic()
            if st["phase"] == "scrub1":
                item["scrub1"] = scrub(w, item["frame"])
                st["phase"], st["t"] = "scrub2", now
            elif st["phase"] == "scrub2" and now - st["t"] >= SETTLE_S:
                item["scrub2"] = scrub(w, item["frame"])
                st["phase"], st["t"] = "read", now
            elif st["phase"] == "read" and now - st["t"] >= SETTLE_S:
                snap = read_state(w, expected)
                snap["fraction"] = item["fraction"]
                snap["target_frame"] = item["frame"]
                st["snaps"].append(snap)
                c = snap["lamp_counts"]
                _log("PROBE_P02_LIGHTS_FRAME|run=%s|f=%s|frame=%d|cam_d=%.0f|lamps=%d|visible=%d|mismatch=%d|ppv_inside=%s" % (
                    RUN_ID, item["fraction"], snap["frame"], snap["camera"]["route_distance_cm"], c["in_window"],
                    c["visible"], c["mismatch"],
                    [p["label"] for p in snap["ppv"] if p["camera_inside"] in (True, "aabb:True")]))
                st["i"] += 1
                st["phase"] = "scrub1"
                if st["i"] >= len(plan):
                    finish()
        except Exception:
            finish("exception:" + traceback.format_exc(limit=3).replace("\n", " | "))
        finally:
            st["inside"] = False

    setattr(builtins, HANDLE_NAME, unreal.register_slate_post_tick_callback(tick))


try:
    arm()
except Exception:
    _fail("arm_exception:" + traceback.format_exc(limit=3).replace("\n", " | "))
