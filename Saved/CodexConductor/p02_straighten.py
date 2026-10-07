"""P02 straighten (Gary 5 Oct: "also please straighten that passage"; reverses the earlier keep-the-curve call. He also
said curves should stay restorable, so REVERT puts the exact authored spline back). Written offline 5 Oct, NOT RUN.
Scope addition (Gary ~15:30): "P02 also needs waxed floor to be in shot and the slatted stage floor removed".

WHERE THE CURVE LIVES [declaration-proven]: not in the Show. It is the Passage ACTOR's Route spline plus its
bAutoFitStraightRoute flag (InfinityStagePassageActor.h:69,78), saved in the LEVEL. With Auto Fit on, MaterializePassage
replaces the spline with two Linear points (0,0,0) -> (TotalDistanceCm,0,0) in the route's local frame
(InfinityStagePassageActor.cpp:782-821); Auto Fit off keeps the hand-shaped spline (P02 today: probe_routes.json,
measured 5 Oct 08:37: auto_fit false, 3 points, 13582.6 cm, start yaw +22.91, end yaw 0). The Passage DISTANCE is the
compiled TotalDistanceCm from the Show (GetRouteLengthStatus, .cpp:1158-1180) and does not change.

ANCHORS (the APPLY arg "anchor"; a structural/look choice, so it is never defaulted):
  START  keep the actor transform: the straight route runs from P02's current start along the actor's +X. The camera's
         end view moves (it now stops 1725 cm before the curve's end, on the bend), so the Scene 2 hangar dock moves:
         this needs a re-dock tool, and APPLY refuses until one is registered (REDOCK_TOOL below).
  DOCK   move/turn the Passage actor so the straight route's camera END VIEW lands on the S2 hangar dock
         (hangar_s2_record.json). The hangar stays put; P02's mouth moves instead (a cloth match cut, no hangar).
Both anchors turn/move P02's mouth and re-lay the whole lane, so the S1 Exit handoff and every hand-placed actor along
the old route are follow-ons (APPLY needs them acked in followons_ack).

FLOOR STEP (on by default, "floor_step": false skips it; recorded for REVERT):
  - Structure 02 Ground.bEnabled -> false. Removes the boards (slats), chariot slots, steel grooves, understage, the
    FORESTAGE boards and the STAGE FRONT (InfinityStageStructureActor.cpp:510-513,1348,1370) [declaration-proven].
    FloorHeightCm is kept; wings never read it (only StructureActor.cpp uses it) [declaration-proven by grep].
  - Walnut slabs "Passage 02 - Floor Near/Left/Right/Far": coverage of the straight route +- wing zone + margin is
    computed; the slabs are moved only if a gap lies OUTSIDE the S2 hangar pit (the hole the four slabs frame). A gap
    inside the pit is the hangar's own floor and is reported, not filled.
  - "floor_material": "KEEP" (default) | "WALNUT" | "P01". 10:35's p02_floor_walnut APPLY set MI_Floor_DarkWet (P01's
    slab material, read live), replacing walnut herringbone [measured: log P02_FLOOR_DRY_OK walnut=MI_Floor_DarkWet].
    Which one is "waxed" is Gary's call; KEEP changes nothing.

Args p02_straighten_args.json (or P02STRAIGHT_ARGS from p02_straighten_run.py):
  {"mode": "DRY"|"APPLY"|"REVERT", "confirm": "<MODE> P02STRAIGHT", "anchor": "START"|"DOCK",
   "floor_step": true, "floor_material": "KEEP", "floor_margin_cm": 500, "followons_ack": [..], "redock_ack": ".."}
APPLY: guards (no PIE, clean census, record absent) -> exclusive fsynced record + Show .uasset + level .umap backup into
Backups/PreP02Straighten-<run> -> ground off -> slabs -> auto fit on (+ actor move for DOCK) -> MaterializePassage (P02
only) -> MaterializeStructure (Structure 02 only) -> IsStructureCurrent -> measured end view vs dock -> census = Show +
level only -> save those -> read back -> census clean -> P02_STRAIGHTEN_APPLY_OK|run=..
REVERT: restores flag, exact spline points/tangents/types, actor transform, Ground struct (export_text), slabs; same
materialize/save/read-back chain; marker P02_STRAIGHTEN_REVERT_OK.
"""
import datetime
import json
import math
import os
import shutil

try:
    import unreal
except ImportError:  # offline harness
    unreal = None

HERE = "E:/PussStage/Saved/CodexConductor/"
ARGS_NAME = "p02_straighten_args.json"
REC = HERE + "p02_straighten_record.json"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
SHOW_UASSET = "E:/PussStage/Content/InfinityStage/Dev/DA_InfinityStage_V1Show.uasset"
PASSAGE_PREFIX = "Passage 02"
STRUCTURE = "Infinity Stage - Structure 02"
SLABS = ("Passage 02 - Floor Near", "Passage 02 - Floor Left", "Passage 02 - Floor Right", "Passage 02 - Floor Far")
P01_SLAB = "Passage 01 - Opening Floor"
WALNUT = "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_02/Materials/M_Walnut_Hrrngbn_02_Mat_Inst_Dup.M_Walnut_Hrrngbn_02_Mat_Inst_Dup"
HANGAR_REC = "E:/PussStage/Saved/CodexStructure/hangar_s2_record.json"
S2_ENTRY = ("Scene 2 ", "Entry Handoff Camera")
S1_EXIT = ("Scene 1 ", "Exit Handoff Camera")
# The S2 re-dock (START anchor) is the per-hangar chain in Docs/HangarExitCost_2026-09-30.md:59-60 (un-nest, Arrival
# revert, hangar revert, hangar_build.py at the new Entry camera, Arrival, nest). No single tool does it yet; when one
# exists it must live here and declare REDOCK_FOR = "P02STRAIGHT". Until then START refuses.
REDOCK_TOOL = "E:/PussStage/Saved/CodexStructure/s2_hangar_redock_after_p02.py"
REDOCK_MARK = 'REDOCK_FOR = "P02STRAIGHT"'
REDOCK_ACK = "S2 REDOCK FOLLOWS"
TOL_CM, TOL_DEG = 25.0, 0.5
ROUTE_RADIUS_CM = 4000.0
FOLLOWON_TEXT = {
    "S2_REDOCK": "re-dock the S2 hangar at the new Entry camera: " + REDOCK_TOOL,
    "MATCH_HANDOFFS": "MatchNamedSceneHandoffs(show, [Scene 1, Scene 2], 2) (InfinityStageCameraPilotLibrary.h:115); "
                      "writes the level and those Scenes' sequences, so it is its own run",
    "ROUTE_ACTORS": "re-place the hand-placed actors along P02's old route (listed in the DRY: mouth lantern, stalls "
                    "camera, car light...); they were composed against the curve and do not follow it",
}
RUN = datetime.datetime.now().strftime("P02STR-%Y%m%d-%H%M%S")


# ---------------------------------------------------------------- pure geometry (harness-tested, no Unreal) ----------
def wrap(deg):
    return (deg + 180.0) % 360.0 - 180.0


def _persistent_actors():
    """Only actors in the open persistent level. Klara's streamed levels (Japanese_Alley, L_Animals, L_KK_children)
    sit on/near the route and must never travel with P02 (measured 7 Oct: 198 'unclassified' route actors, all in
    /Game/Japanese_Alley/Maps/Japanese_Alley; probe_p02_unclassified_levels.py)."""
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    persistent = world.get_outermost().get_name()
    return [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
            if a.get_outermost().get_name() == persistent]


def xf(loc, yaw):
    return {"loc": [float(loc[0]), float(loc[1]), float(loc[2])], "yaw": float(yaw)}


def compose(parent, child):
    """parent * child for planar frames (yaw about Z, translation); z adds."""
    c, s = math.cos(math.radians(parent["yaw"])), math.sin(math.radians(parent["yaw"]))
    x, y, z = child["loc"]
    p = parent["loc"]
    return xf([p[0] + c * x - s * y, p[1] + s * x + c * y, p[2] + z], wrap(parent["yaw"] + child["yaw"]))


def inverse(frame):
    c, s = math.cos(math.radians(-frame["yaw"])), math.sin(math.radians(-frame["yaw"]))
    x, y, z = frame["loc"]
    return xf([-(c * x - s * y), -(s * x + c * y), -z], wrap(-frame["yaw"]))


def delta(a, b):
    return {"xy_cm": math.hypot(a["loc"][0] - b["loc"][0], a["loc"][1] - b["loc"][1]),
            "z_cm": a["loc"][2] - b["loc"][2], "yaw_deg": wrap(a["yaw"] - b["yaw"])}


def moves(d, tol_cm=TOL_CM, tol_deg=TOL_DEG):
    return d["xy_cm"] > tol_cm or abs(d["yaw_deg"]) > tol_deg


def straight_route(actor, route_rel, length_cm):
    """Auto Fit's straight route: local (0,0,0) -> (L,0,0) [InfinityStagePassageActor.cpp:817-818]."""
    start = compose(actor, route_rel)
    return {"start": start, "end": compose(start, xf([length_cm, 0, 0], 0)), "length_cm": length_cm}


def frame_at(start, d_cm):
    return compose(start, xf([d_cm, 0, 0], 0))


def camera_rel(old_frame_at_end, camera_end):
    """Camera end view in the route frame at the end distance (offsets are route-relative: CameraRig.cpp:834-857)."""
    return compose(inverse(old_frame_at_end), camera_end)


def predict_camera(new_start, d_end, rel):
    return compose(frame_at(new_start, d_end), rel)


def solve_dock_anchor(dock_view, rel, d_end, route_rel, actor_z):
    """Actor transform whose straight route puts the camera end view on dock_view (planar; z kept)."""
    frame_end = compose(dock_view, inverse(rel))
    start = compose(frame_end, xf([-d_end, 0, 0], 0))
    actor = compose(start, inverse(route_rel))
    actor["loc"][2] = actor_z
    return actor


# ---------------------------------------------------------------- floor coverage -------------------------------------
def slab_rect(label, loc, yaw, scale, mesh_extent_cm=50.0):
    """Engine Cube = 100 cm, centred; half sizes = scale * 50 [mesh 'Cube': probe_mouth_surfaces.json]."""
    return {"label": label, "loc": [float(loc[0]), float(loc[1])], "yaw": float(yaw),
            "half": [abs(scale[0]) * mesh_extent_cm, abs(scale[1]) * mesh_extent_cm]}


def to_frame(frame, p):
    c, s = math.cos(math.radians(frame["yaw"])), math.sin(math.radians(frame["yaw"]))
    dx, dy = p[0] - frame["loc"][0], p[1] - frame["loc"][1]
    return (c * dx + s * dy, -s * dx + c * dy)


def in_slab(rect, p, margin=0.0):
    lx, ly = to_frame({"loc": rect["loc"], "yaw": rect["yaw"]}, p)
    return abs(lx) <= rect["half"][0] + margin and abs(ly) <= rect["half"][1] + margin


def rect_corners(rect):
    out = []
    for u, w in ((1, 1), (1, -1), (-1, -1), (-1, 1)):
        f = compose(xf([rect["loc"][0], rect["loc"][1], 0], rect["yaw"]), xf([u * rect["half"][0], w * rect["half"][1], 0], 0))
        out.append((f["loc"][0], f["loc"][1]))
    return out


def hangar_hole(dock, rects):
    """The pit the four slabs frame, in the dock frame: x from the slab holding the dock (its far edge) to the slab
    straddling y=0 beyond it; |y| up to the nearer inner side edge. None when the slabs do not frame a hole."""
    spans = []
    for r in rects:
        cs = [to_frame(dock, c) for c in rect_corners(r)]
        spans.append((r["label"], min(c[0] for c in cs), max(c[0] for c in cs), min(c[1] for c in cs), max(c[1] for c in cs)))
    near = [s for s in spans if s[1] <= 0.0 <= s[2] and s[3] <= 0.0 <= s[4]]
    if len(near) != 1:
        return None
    x0 = near[0][2]
    far = [s for s in spans if s[1] > x0 and s[3] < 0.0 < s[4]]
    left = [s for s in spans if s is not near[0] and s[4] < 0.0 and s[2] > x0]
    right = [s for s in spans if s is not near[0] and s[3] > 0.0 and s[2] > x0]
    if not (far and left and right):
        return None
    return {"x0": x0, "x1": min(s[1] for s in far), "half_y": min(min(-s[4] for s in left), min(s[3] for s in right))}


def in_hole(dock, hole, p):
    lx, ly = to_frame(dock, p)
    return hole is not None and hole["x0"] < lx < hole["x1"] and abs(ly) < hole["half_y"]


def route_samples(start, length_cm, apron_cm, half_width_cm, step_cm=250.0):
    pts = []
    n = int(math.ceil((length_cm + 2 * apron_cm) / step_cm))
    lat_n = max(2, int(math.ceil(2 * half_width_cm / step_cm)))
    for i in range(n + 1):
        d = -apron_cm + (length_cm + 2 * apron_cm) * i / n
        for j in range(lat_n + 1):
            f = compose(start, xf([d, -half_width_cm + 2 * half_width_cm * j / lat_n, 0], 0))
            pts.append((round(f["loc"][0], 1), round(f["loc"][1], 1), round(d, 1)))
    return pts


def coverage(rects, samples, dock, hole):
    covered, pit, gaps = 0, [], []
    for p in samples:
        if any(in_slab(r, p) for r in rects):
            covered += 1
        elif in_hole(dock, hole, p):
            pit.append(p)
        else:
            gaps.append(p)
    return {"samples": len(samples), "covered": covered, "in_pit": len(pit), "gaps": gaps,
            "pit_max_d_cm": max((p[2] for p in pit), default=None), "pit_min_d_cm": min((p[2] for p in pit), default=None)}


def rects_overlap(a, b):
    """Separating-axis test for two rotated rectangles."""
    ca, cb = rect_corners(a), rect_corners(b)
    for r in (a, b):
        for ang in (r["yaw"], r["yaw"] + 90.0):
            ax = (math.cos(math.radians(ang)), math.sin(math.radians(ang)))
            pa = [c[0] * ax[0] + c[1] * ax[1] for c in ca]
            pb = [c[0] * ax[0] + c[1] * ax[1] for c in cb]
            if max(pa) <= min(pb) or max(pb) <= min(pa):
                return False
    return True


def hole_rect(dock, hole):
    mid = compose(dock, xf([(hole["x0"] + hole["x1"]) / 2.0, 0, 0], 0))
    return {"label": "S2 pit", "loc": mid["loc"][:2], "yaw": dock["yaw"],
            "half": [(hole["x1"] - hole["x0"]) / 2.0, hole["half_y"]]}


def fit_slab(rect, points, dock, hole):
    """Grow rect (in its own frame, never shrinking) to contain points. Refuses (None, why) if the result would
    cover the hangar pit."""
    lo = [-rect["half"][0], -rect["half"][1]]
    hi = [rect["half"][0], rect["half"][1]]
    for p in points:
        lx, ly = to_frame({"loc": rect["loc"], "yaw": rect["yaw"]}, p)
        lo, hi = [min(lo[0], lx), min(lo[1], ly)], [max(hi[0], lx), max(hi[1], ly)]
    centre = compose(xf([rect["loc"][0], rect["loc"][1], 0], rect["yaw"]), xf([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, 0], 0))
    new = {"label": rect["label"], "loc": centre["loc"][:2], "yaw": rect["yaw"],
           "half": [(hi[0] - lo[0]) / 2.0, (hi[1] - lo[1]) / 2.0]}
    if hole is not None and rects_overlap(new, hole_rect(dock, hole)):
        return None, "FIT_WOULD_COVER_PIT|" + rect["label"]
    return new, None


def floor_plan(rects, samples, dock, hole):
    """None-change when the slabs already cover everything outside the pit; else grow the slab nearest each gap."""
    cov = coverage(rects, samples, dock, hole)
    if not cov["gaps"]:
        return {"coverage": cov, "moves": {}, "refusal": None}
    by = {}
    for p in cov["gaps"]:
        best = min(rects, key=lambda r: math.hypot(r["loc"][0] - p[0], r["loc"][1] - p[1]) - max(r["half"]))
        by.setdefault(best["label"], []).append(p)
    moves_ = {}
    for label, pts in by.items():
        new, why = fit_slab(next(r for r in rects if r["label"] == label), pts, dock, hole)
        if why:
            return {"coverage": cov, "moves": {}, "refusal": why}
        moves_[label] = new
    return {"coverage": cov, "moves": moves_, "refusal": None}


def rect_to_actor(new_rect, z, mesh_extent_cm=50.0):
    return {"loc": [new_rect["loc"][0], new_rect["loc"][1], z], "yaw": new_rect["yaw"],
            "scale_xy": [new_rect["half"][0] / mesh_extent_cm, new_rect["half"][1] / mesh_extent_cm]}


# ---------------------------------------------------------------- spline snapshot ------------------------------------
def snap_equal(a, b, tol=1e-3):
    """Exact-restore check on the recorded spline: point count, closed loop, types, and every vector within tol."""
    if a is None or b is None or len(a["points"]) != len(b["points"]) or a["closed"] != b["closed"]:
        return False
    for p, q in zip(a["points"], b["points"]):
        if p["type"] != q["type"]:
            return False
        for k in ("loc", "arrive", "leave", "rot", "scale"):
            if any(abs(x - y) > tol for x, y in zip(p[k], q[k])):
                return False
    return True


def ground_change_ok(before, after, expect_enabled):
    """Only 'enabled' may differ; floor_height_cm must be identical (wing/fixture/cloth heights read it)."""
    if after.get("enabled") != expect_enabled:
        return False
    return all(before[k] == after[k] for k in before if k != "enabled")


# ---------------------------------------------------------------- gates ----------------------------------------------
def followons_needed(facts, anchor):
    out = []
    if moves(facts["dock_delta"][anchor]):
        out.append("S2_REDOCK")
    if moves(facts["start_delta"][anchor]) or moves(facts["dock_delta"][anchor]):
        out.append("MATCH_HANDOFFS")
    if facts["mouth_actors"]:
        out.append("ROUTE_ACTORS")
    return out


def redock_registered(text):
    return text is not None and REDOCK_MARK in text


def refusals(mode, args, facts):
    out = []
    if mode not in ("DRY", "APPLY", "REVERT"):
        return ["MODE_UNKNOWN|" + mode]
    if mode != "DRY" and args.get("confirm") != "%s P02STRAIGHT" % mode:
        out.append("CONFIRM_MISSING|need='%s P02STRAIGHT'" % mode)
    if mode == "APPLY":
        anchor = str(args.get("anchor", "")).upper()
        if anchor not in ("START", "DOCK"):
            return out + ["ANCHOR_REQUIRED|START or DOCK (Gary's choice)"]
        if facts["record_exists"]:
            out.append("RECORD_EXISTS")
        if facts["already_straight"]:
            out.append("ALREADY_STRAIGHT")
        if facts["length_short"]:
            out.append("COMPILED_LENGTH_UNREADABLE")
        need = followons_needed(facts, anchor)
        if "S2_REDOCK" in need and not (redock_registered(facts.get("redock_tool_text"))
                                        and args.get("redock_ack") == REDOCK_ACK):
            out.append("DOCK_MOVES_NEEDS_REDOCK|delta=%s|tool=%s" % (json.dumps(facts["dock_delta"][anchor]), REDOCK_TOOL))
        missing = [f for f in need if f not in (args.get("followons_ack") or [])]
        if missing:
            out.append("FOLLOWONS_NOT_ACKED|" + ",".join(missing))
        if args.get("floor_step", True):
            fp = facts["floor"][anchor]
            if fp["refusal"]:
                out.append("FLOOR|" + fp["refusal"])
        if str(args.get("floor_material", "KEEP")).upper() not in ("KEEP", "WALNUT", "P01"):
            out.append("FLOOR_MATERIAL_UNKNOWN")
    if mode == "REVERT":
        if not facts["record_exists"]:
            out.append("NO_RECORD")
        elif facts["already_reverted"]:
            out.append("ALREADY_REVERTED")
    return out


# ---------------------------------------------------------------- Unreal side ----------------------------------------
def stop(msg):
    unreal.log_error("P02_STRAIGHTEN_FAILED|run=%s|%s" % (RUN, msg))
    raise RuntimeError(msg)


def log(tag, payload):
    unreal.log("P02_STRAIGHTEN_%s|run=%s|%s" % (tag, RUN, json.dumps(payload, default=str, sort_keys=True)))


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def v3(v):
    return [float(v.x), float(v.y), float(v.z)]


def u_xf(t):
    return xf(v3(t.translation), float(t.rotation.rotator().yaw))


def actor_xf(a):
    return xf(v3(a.get_actor_location()), float(a.get_actor_rotation().yaw))


def enum_name(e):
    return getattr(e, "name", str(e))


def spline_snap(sp):
    L = unreal.SplineCoordinateSpace.LOCAL
    pts = []
    for i in range(sp.get_number_of_spline_points()):
        r = sp.get_rotation_at_spline_point(i, L)
        pts.append({"loc": v3(sp.get_location_at_spline_point(i, L)),
                    "arrive": v3(sp.get_arrive_tangent_at_spline_point(i, L)),
                    "leave": v3(sp.get_leave_tangent_at_spline_point(i, L)),
                    "type": enum_name(sp.get_spline_point_type(i)),
                    "rot": [float(r.roll), float(r.pitch), float(r.yaw)],
                    "scale": v3(sp.get_scale_at_spline_point(i))})
    return {"points": pts, "closed": bool(sp.is_closed_loop()), "length_cm": float(sp.get_spline_length())}


def spline_restore(sp, snap):
    L = unreal.SplineCoordinateSpace.LOCAL
    sp.modify()
    sp.clear_spline_points(False)
    for p in snap["points"]:
        sp.add_spline_point(unreal.Vector(*p["loc"]), L, False)
    for i, p in enumerate(snap["points"]):
        sp.set_spline_point_type(i, getattr(unreal.SplinePointType, p["type"]), False)
        if p["type"] == "CURVE_CUSTOM_TANGENT":
            sp.set_tangents_at_spline_point(i, unreal.Vector(*p["arrive"]), unreal.Vector(*p["leave"]), L, False)
        sp.set_rotation_at_spline_point(i, unreal.Rotator(roll=p["rot"][0], pitch=p["rot"][1], yaw=p["rot"][2]), L, False)
        sp.set_scale_at_spline_point(i, unreal.Vector(*p["scale"]), False)
    sp.set_closed_loop(snap["closed"], False)
    sp.update_spline()


def ground_fields(g):
    return {"enabled": bool(g.get_editor_property("enabled")),
            "floor_height_cm": float(g.get_editor_property("floor_height_cm")),
            "apron_cm": float(g.get_editor_property("apron_cm")),
            "cut_chariot_slots": bool(g.get_editor_property("cut_chariot_slots"))}


def unwrap_tuple(res, want_type=None):
    if isinstance(res, tuple):
        if res and isinstance(res[0], bool):
            if not res[0]:
                return None
            res = res[1:]
        if want_type is not None:
            return next((r for r in res if isinstance(r, want_type)), None)
        return res
    return res


def slab_snap(a):
    c = a.get_component_by_class(unreal.StaticMeshComponent)
    s = a.get_actor_scale3d()
    return {"label": str(a.get_actor_label()), "loc": v3(a.get_actor_location()),
            "rot": [float(a.get_actor_rotation().roll), float(a.get_actor_rotation().pitch), float(a.get_actor_rotation().yaw)],
            "scale": v3(s), "hidden": bool(a.get_editor_property("hidden")),
            "hidden_in_editor": bool(a.is_temporarily_hidden_in_editor()),
            "materials": [m.get_path_name() if m else None for m in c.get_materials()],
            "mesh": c.get_editor_property("static_mesh").get_path_name() if c.get_editor_property("static_mesh") else None}


def slab_apply(a, s):
    a.modify()
    a.set_actor_location_and_rotation(unreal.Vector(*s["loc"]),
                                      unreal.Rotator(roll=s["rot"][0], pitch=s["rot"][1], yaw=s["rot"][2]), False, False)
    a.set_actor_scale3d(unreal.Vector(*s["scale"]))
    a.set_editor_property("hidden", s["hidden"])
    a.set_actor_hidden_in_game(s["hidden"])
    c = a.get_component_by_class(unreal.StaticMeshComponent)
    for i, m in enumerate(s["materials"][:c.get_num_materials()]):
        c.set_material(i, unreal.load_asset(m) if m else None)


def slab_matches(a, s, tol=0.05):
    g = slab_snap(a)
    return (all(abs(x - y) <= tol for k in ("loc", "scale") for x, y in zip(g[k], s[k]))
            and abs(wrap(g["rot"][2] - s["rot"][2])) <= 0.01 and g["hidden"] == s["hidden"]
            and g["materials"][:len(s["materials"])] == s["materials"][:len(g["materials"])])


def read_world(args):
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        stop("PIE_ACTIVE")
    world = ed.get_editor_world()
    if not world.get_path_name().startswith(WORLD + "."):
        stop("WRONG_WORLD|" + world.get_path_name())
    show = unreal.EditorAssetLibrary.load_asset(SHOW)
    acts = _persistent_actors()
    passages = [a for a in acts if a.get_class().get_name() == "InfinityStagePassageActor"
                and str(a.get_actor_label()).startswith(PASSAGE_PREFIX) and a.get_editor_property("show_asset") == show]
    structs = [a for a in acts if a.get_class().get_name() == "InfinityStageStructureActor"
               and passages and a.get_editor_property("passage") == passages[0]]
    rigs = [a for a in acts if a.get_class().get_name() == "InfinityStageCameraRig"
            and passages and a.get_editor_property("passage_actor") == passages[0]]
    slabs = {l: [a for a in acts if str(a.get_actor_label()) == l] for l in SLABS + (P01_SLAB,)}
    cams = {k: [a for a in acts if str(a.get_actor_label()).startswith(p) and s in str(a.get_actor_label())]
            for k, (p, s) in (("s2_entry", S2_ENTRY), ("s1_exit", S1_EXIT))}
    counts = {"passage": len(passages), "structure": len(structs), "rig": len(rigs),
              "slabs": {k: len(v) for k, v in slabs.items()}, "cams": {k: len(v) for k, v in cams.items()}}
    if (len(passages) != 1 or len(structs) != 1 or len(rigs) != 1 or any(len(v) != 1 for v in slabs.values())
            or any(len(v) != 1 for v in cams.values())):
        stop("COUNTS|" + json.dumps(counts))
    if len(structs) == 1 and str(structs[0].get_actor_label()) != STRUCTURE:
        stop("STRUCTURE_LABEL|" + str(structs[0].get_actor_label()))
    return ed, world, show, acts, passages[0], structs[0], rigs[0], {k: v[0] for k, v in slabs.items()}, \
        {k: v[0] for k, v in cams.items()}


def camera_view(rig, frame):
    t = unwrap_tuple(rig.get_camera_view_at_master_frame(unreal.FrameNumber(int(frame))), unreal.Transform)
    return u_xf(t) if t is not None else None


def gather(args, w):
    ed, world, show, acts, p, st, rig, slabs, cams = w
    route = p.get_editor_property("route")
    W = unreal.SplineCoordinateSpace.WORLD
    snap_len = float(route.get_spline_length())
    ok_len = unwrap_tuple(p.get_route_length_status())
    required = float(ok_len[0]) if ok_len else None
    guid = p.get_editor_property("passage_guid")
    fr = unwrap_tuple(unreal.InfinityStageCameraPilotLibrary.get_passage_frame_range(show, guid))
    if not fr:
        stop("FRAME_RANGE_UNREADABLE")
    start_f, end_f = int(fr[0]), int(fr[1])
    s2 = actor_xf(cams["s2_entry"])
    s1 = actor_xf(cams["s1_exit"])
    # Which sampled frame IS the S2 Entry camera (the builder copies the view at the segment's EndFrame,
    # SceneHandoffBuilder.cpp:226,416); measured here rather than assumed.
    cand = {f: camera_view(rig, f) for f in (end_f, end_f - 1)}
    if not any(cand.values()):
        stop("CAMERA_END_VIEW_UNREADABLE")
    end_frame = min((f for f in cand if cand[f]), key=lambda f: delta(cand[f], s2)["xy_cm"] + abs(delta(cand[f], s2)["yaw_deg"]))
    cam_end = cand[end_frame]
    cam_start = camera_view(rig, start_f)
    if cam_start is None or required is None:
        stop("CAMERA_START_OR_LENGTH_UNREADABLE")
    hangar = json.load(open(HANGAR_REC, encoding="utf-8"))["dock"]
    dock = xf([hangar["loc"][0], hangar["loc"][1], cam_end["loc"][2]], hangar["yaw"])
    route_world = u_xf(route.get_world_transform())
    actor = actor_xf(p)
    route_rel = compose(inverse(actor), route_world)
    d_end = required
    old_end_frame = u_xf(route.get_transform_at_distance_along_spline(d_end, W, False))
    old_start_frame = u_xf(route.get_transform_at_distance_along_spline(0.0, W, False))
    rel_end = camera_rel(old_end_frame, cam_end)
    rel_start = camera_rel(old_start_frame, cam_start)
    preds = {}
    for anchor in ("START", "DOCK"):
        a_xf = actor if anchor == "START" else solve_dock_anchor(dock, rel_end, d_end, route_rel, actor["loc"][2])
        sr = straight_route(a_xf, route_rel, required)
        preds[anchor] = {"actor": a_xf, "route": sr, "cam_end": predict_camera(sr["start"], d_end, rel_end),
                         "cam_start": predict_camera(sr["start"], 0.0, rel_start)}
    # Wing zone half width from the materialized panels (lateral distance to the old route).
    half_w = 0.0
    for ref in p.get_editor_property("materialized_panels"):
        loc = ref.get_editor_property("base_world_transform").translation
        q = route.find_location_closest_to_world_location(loc, W)
        half_w = max(half_w, math.hypot(loc.x - q.x, loc.y - q.y))
    margin = float(args.get("floor_margin_cm", 500.0))
    ground = st.get_editor_property("ground")
    rects = [slab_rect(l, slab_snap(slabs[l])["loc"], slab_snap(slabs[l])["rot"][2], slab_snap(slabs[l])["scale"])
             for l in SLABS]
    hole = hangar_hole(dock, rects)
    floor = {}
    for anchor in ("START", "DOCK"):
        samples = route_samples(preds[anchor]["route"]["start"], required, float(ground.get_editor_property("apron_cm")),
                                half_w + margin)
        floor[anchor] = floor_plan(rects, samples, dock, hole)
    # Hand-placed level actors along the OLD route (e.g. "P02 Car Light", the mouth lantern, the stalls camera): they
    # were composed against the curve and do not follow it. The S2 hangar (RigAtmos.Scene2*) is excluded: it is the dock.
    mouth = []
    managed = set(p.get_editor_property("managed_attachment_actors"))
    old_pts = [route.get_location_at_distance_along_spline(snap_len * i / 40.0, W) for i in range(41)]
    for a in acts:
        if a in (p, st, rig) or a in managed or a.get_attach_parent_actor() is not None:
            continue
        if a.get_class().get_name() in ("InfinityStagePassageActor", "InfinityStageStructureActor", "InfinityStageCameraRig"):
            continue
        if str(a.get_actor_label()) in SLABS or any(str(t).startswith("RigAtmos.Scene2") for t in a.tags):
            continue
        l = a.get_actor_location()
        if any(math.hypot(l.x - q.x, l.y - q.y) < ROUTE_RADIUS_CM for q in old_pts):
            mouth.append(str(a.get_actor_label()))
    snap = spline_snap(route)
    redock_text = open(REDOCK_TOOL, encoding="utf-8").read() if os.path.exists(REDOCK_TOOL) else None
    rec = json.load(open(REC, encoding="utf-8")) if os.path.exists(REC) else None
    return {
        "required_cm": required, "length_short": required is None, "frames": [start_f, end_f], "end_frame_used": end_frame,
        "auto_fit": bool(p.get_editor_property("auto_fit_straight_route")), "spline": snap, "actor": actor,
        "route_rel": route_rel, "cam_end": cam_end, "cam_start": cam_start, "s2_entry": s2, "s1_exit": s1, "dock": dock,
        "cam_end_vs_s2_entry": delta(cam_end, s2), "cam_end_vs_dock": delta(cam_end, dock),
        "rel_end": rel_end, "rel_start": rel_start, "preds": preds,
        "dock_delta": {k: delta(v["cam_end"], dock) for k, v in preds.items()},
        "start_delta": {k: delta(v["cam_start"], cam_start) for k, v in preds.items()},
        "end_route_delta": {k: delta(v["route"]["end"], u_xf(route.get_transform_at_distance_along_spline(
            snap["length_cm"], W, False))) for k, v in preds.items()},
        "half_wing_cm": half_w, "hole": hole, "floor": floor, "mouth_actors": sorted(mouth),
        "ground": ground_fields(ground), "ground_text": ground.export_text(),
        "slabs": {l: slab_snap(slabs[l]) for l in SLABS + (P01_SLAB,)},
        "already_straight": bool(p.get_editor_property("auto_fit_straight_route")) and len(snap["points"]) == 2,
        "record_exists": rec is not None, "record": rec,
        "already_reverted": bool(rec) and not bool(p.get_editor_property("auto_fit_straight_route"))
        and snap_equal(snap, rec["before"]["spline"]),
        "redock_tool_text": redock_text, "census": census(),
    }


def floor_targets(args, facts, anchor):
    """Slab end states for APPLY: moved rects (if any) and the material choice."""
    out = {}
    mat = str(args.get("floor_material", "KEEP")).upper()
    p01 = facts["slabs"][P01_SLAB]["materials"]
    for l in SLABS:
        s = json.loads(json.dumps(facts["slabs"][l]))
        mv = facts["floor"][anchor]["moves"].get(l)
        if mv:
            a = rect_to_actor(mv, s["loc"][2])
            s["loc"] = a["loc"]
            s["scale"] = [a["scale_xy"][0], a["scale_xy"][1], s["scale"][2]]
        if mat == "WALNUT":
            s["materials"] = [WALNUT] * len(s["materials"])
        elif mat == "P01":
            s["materials"] = [p01[0]] * len(s["materials"])
        out[l] = s
    return out


def save_and_verify(ed, world):
    dirty = census()
    if set(dirty["content"]) - {SHOW} or dirty["maps"] != [WORLD]:
        stop("DIRTY_SCOPE|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(dirty))
    if SHOW in dirty["content"] and not unreal.EditorAssetLibrary.save_asset(SHOW, only_if_is_dirty=True):
        stop("SHOW_SAVE_FAILED")
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, WORLD):
        stop("SAVE_FAILED")
    if census() != {"content": [], "maps": []}:
        stop("POST_SAVE_DIRTY|" + json.dumps(census()))
    return dirty


def write_record(obj, exclusive):
    with open(REC, "x" if exclusive else "w", encoding="utf-8") as h:
        json.dump(obj, h, indent=1, default=str)
        h.flush()
        os.fsync(h.fileno())


def main():
    args = globals().get("P02STRAIGHT_ARGS")
    if args is None:
        args = json.load(open(HERE + ARGS_NAME, encoding="utf-8"))
    mode = str(args.get("mode", "DRY")).upper()
    w = read_world(args)
    ed, world, show, acts, p, st, rig, slabs, cams = w
    facts = gather(args, w)
    report = {k: v for k, v in facts.items() if k not in ("redock_tool_text", "record", "ground_text")}
    report["followons"] = {a: [(f, FOLLOWON_TEXT[f]) for f in followons_needed(facts, a)] for a in ("START", "DOCK")}
    report["redock_registered"] = redock_registered(facts["redock_tool_text"])
    log("FACTS", {k: report[k] for k in ("required_cm", "frames", "end_frame_used", "auto_fit", "actor", "route_rel",
                                         "cam_end", "s2_entry", "dock", "cam_end_vs_s2_entry", "rel_end", "half_wing_cm",
                                         "hole", "ground", "mouth_actors", "census")})
    log("SPLINE_NOW", facts["spline"])
    for a in ("START", "DOCK"):
        log("PLAN_" + a, {"actor": facts["preds"][a]["actor"], "route": facts["preds"][a]["route"],
                          "cam_end_pred": facts["preds"][a]["cam_end"], "dock_delta": facts["dock_delta"][a],
                          "start_delta": facts["start_delta"][a], "route_end_delta": facts["end_route_delta"][a],
                          "followons": report["followons"][a],
                          "floor": {"coverage": {k: v for k, v in facts["floor"][a]["coverage"].items() if k != "gaps"},
                                    "gaps": len(facts["floor"][a]["coverage"]["gaps"]),
                                    "moves": facts["floor"][a]["moves"], "refusal": facts["floor"][a]["refusal"]}})
    bad = refusals(mode, args, facts)
    if mode == "DRY":
        path = HERE + "p02_straighten_dry_%s.json" % RUN
        with open(path, "w", encoding="utf-8") as h:
            json.dump(report, h, indent=1, default=str)
        log("DRY_REFUSALS_IF_APPLY", {a: refusals("APPLY", dict(args, anchor=a, confirm="APPLY P02STRAIGHT"), facts)
                                      for a in ("START", "DOCK")})
        if census() != facts["census"]:
            stop("DRY_DIRTIED|" + json.dumps(census()))
        unreal.log("P02_STRAIGHTEN_DRY_OK|run=%s|report=%s" % (RUN, path))
        return
    if bad:
        stop("REFUSED|" + "|".join(bad))
    if facts["census"] != {"content": [], "maps": []}:
        stop("DIRTY_BEFORE|" + json.dumps(facts["census"]))
    route = p.get_editor_property("route")
    if mode == "APPLY":
        anchor = str(args["anchor"]).upper()
        pred = facts["preds"][anchor]
        floor_on = bool(args.get("floor_step", True))
        targets = floor_targets(args, facts, anchor) if floor_on else {}
        backup = "E:/PussStage/Backups/PreP02Straighten-" + RUN
        record = {"run": RUN, "status": "started", "anchor": anchor, "floor_step": floor_on, "backup": backup,
                  "before": {"auto_fit": facts["auto_fit"], "spline": facts["spline"], "actor": facts["actor"],
                             "actor_rot": [float(p.get_actor_rotation().roll), float(p.get_actor_rotation().pitch),
                                           float(p.get_actor_rotation().yaw)],
                             "ground_text": facts["ground_text"], "ground": facts["ground"],
                             "slabs": {l: facts["slabs"][l] for l in SLABS}},
                  "plan": {"actor": pred["actor"], "route": pred["route"], "cam_end_pred": pred["cam_end"],
                           "slabs": targets, "floor_material": str(args.get("floor_material", "KEEP")).upper()},
                  "followons": followons_needed(facts, anchor)}
        write_record(record, exclusive=True)
        os.makedirs(backup)
        shutil.copy2(UMAP, backup)
        shutil.copy2(SHOW_UASSET, backup)
        if floor_on:
            g = st.get_editor_property("ground")
            g.set_editor_property("enabled", False)
            st.modify()
            st.set_editor_property("ground", g)
            if not ground_change_ok(facts["ground"], ground_fields(st.get_editor_property("ground")), False):
                stop("GROUND_READBACK|NOTHING SAVED; Don't-Save restart")
            for l, s in targets.items():
                slab_apply(slabs[l], s)
                if not slab_matches(slabs[l], s):
                    stop("SLAB_READBACK|%s|NOTHING SAVED; Don't-Save restart" % l)
        p.modify()
        if anchor == "DOCK":
            a = pred["actor"]
            r0 = p.get_actor_rotation()
            p.set_actor_location_and_rotation(unreal.Vector(*a["loc"]),
                                              unreal.Rotator(roll=r0.roll, pitch=r0.pitch, yaw=a["yaw"]), False, False)
        p.set_editor_property("auto_fit_straight_route", True)
    else:
        rec = facts["record"]
        before = rec["before"]
        backup = "E:/PussStage/Backups/PreP02StraightenRevert-" + RUN
        os.makedirs(backup)
        shutil.copy2(UMAP, backup)
        shutil.copy2(SHOW_UASSET, backup)
        p.modify()
        p.set_editor_property("auto_fit_straight_route", False)
        ar = before["actor_rot"]
        p.set_actor_location_and_rotation(unreal.Vector(*before["actor"]["loc"]),
                                          unreal.Rotator(roll=ar[0], pitch=ar[1], yaw=ar[2]), False, False)
        spline_restore(route, before["spline"])
        if not snap_equal(spline_snap(route), before["spline"]):
            stop("SPLINE_RESTORE_READBACK|NOTHING SAVED; Don't-Save restart")
        if rec.get("floor_step"):
            g = st.get_editor_property("ground")
            g.import_text(before["ground_text"])
            st.modify()
            st.set_editor_property("ground", g)
            if st.get_editor_property("ground").export_text() != before["ground_text"]:
                stop("GROUND_RESTORE_READBACK|NOTHING SAVED; Don't-Save restart")
            for l, s in before["slabs"].items():
                slab_apply(slabs[l], s)
                if not slab_matches(slabs[l], s):
                    stop("SLAB_RESTORE_READBACK|%s|NOTHING SAVED; Don't-Save restart" % l)
    if not p.materialize_passage():
        stop("PASSAGE_MATERIALIZE_FAILED|NOTHING SAVED; Don't-Save restart")
    if not st.materialize_structure():
        stop("STRUCTURE_MATERIALIZE_FAILED|NOTHING SAVED; Don't-Save restart")
    if not st.is_structure_current():
        stop("STRUCTURE_NOT_CURRENT|NOTHING SAVED; Don't-Save restart")
    snap = spline_snap(route)
    end_view = camera_view(rig, facts["end_frame_used"])
    if mode == "APPLY":
        if len(snap["points"]) != 2 or abs(snap["length_cm"] - facts["required_cm"]) > 0.5:
            stop("STRAIGHT_READBACK|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(snap))
        measured = delta(end_view, facts["dock"])
        log("END_VIEW_MEASURED", {"end_view": end_view, "vs_dock": measured, "vs_pred": delta(end_view, pred["cam_end"])})
        if anchor == "DOCK" and moves(measured):
            stop("DOCK_MISSED|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(measured))
    else:
        if not snap_equal(snap, rec["before"]["spline"]):
            stop("SPLINE_AFTER_MATERIALIZE|NOTHING SAVED; Don't-Save restart")
        log("END_VIEW_MEASURED", {"end_view": end_view, "vs_before": delta(end_view, facts["cam_end"])})
    saved = save_and_verify(ed, world)
    # read back the saved state
    snap2 = spline_snap(p.get_editor_property("route"))
    auto = bool(p.get_editor_property("auto_fit_straight_route"))
    if mode == "APPLY":
        if not auto or len(snap2["points"]) != 2:
            stop("POST_SAVE_READBACK")
        if record["floor_step"] and st.get_editor_property("ground").get_editor_property("enabled"):
            stop("POST_SAVE_GROUND_READBACK")
        record.update({"status": "saved", "after": {"spline": snap2, "actor": actor_xf(p), "end_view": end_view},
                       "saved_census": saved})
        write_record(record, exclusive=False)
    else:
        if auto or not snap_equal(snap2, rec["before"]["spline"]):
            stop("POST_SAVE_READBACK")
        if rec.get("floor_step") and st.get_editor_property("ground").export_text() != rec["before"]["ground_text"]:
            stop("POST_SAVE_GROUND_READBACK")
        os.replace(REC, REC + ".reverted-" + RUN)
    if not st.is_structure_current() or census() != {"content": [], "maps": []}:
        stop("POST_SAVE_STATE")
    unreal.log("P02_STRAIGHTEN_%s_OK|run=%s|anchor=%s|show_saved=%d|level_saved=1|readback=1|dirty_after=0+0|followons=%s"
               % (mode, RUN, args.get("anchor", "-"), int(SHOW in saved["content"]),
                  ",".join(record["followons"]) if mode == "APPLY" else "MATCH_HANDOFFS"))


if unreal is not None:
    main()
