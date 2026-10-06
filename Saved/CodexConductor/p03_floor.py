"""P03 floor (Gary 5 Oct ~15:35: "P03 has the same issue as P02": the waxed floor in shot, the slatted stage floor removed).

The slats are Structure 03's Ground boards (FInfinityStageGroundSettings, InfinityStageStructureActor.h:113-207).
Turning Ground.bEnabled off also removes, in the same materialize (InfinityStageStructureActor.cpp):
  :510-512  BoardMesh / UnderstageMesh are only loaded when Ground is on -> no boards, grooves, understage;
  :584      BuildGround (boards, chariot slots, steel grooves :1178, understage slabs :1248-1272) is skipped;
  :1342-1348, :1369  the portal's FORESTAGE boards and the STAGE FRONT need BoardMesh/Ground -> gone too
                     (portal timbers and the float trough stay; the trough still sits at FloorHeightCm).
FloorHeightCm is KEPT: the underpass fence base (:822), piers (:1762, :1823) and ground cloths (:1644) use it.
The cat floor trace never hits boards (CatFloor defaults to Ignore, Config/DefaultEngine.ini:105-110; slabs opt in).

APPLY (args p03_floor_args.json {"mode": "DRY"|"APPLY"|"REVERT", "confirm": "<MODE> P03FLOOR",
"floor_material": optional object path}):
  guards (args, no PIE, right world, clean census, no ZZ_/TEMP bench actors, Sequencer closed)
  -> plan (same as DRY; any problem refuses) -> record (exclusive create, fsync, read back) + umap backup
     Backups/PreP03Floor-<run>/ (sha checked)
  -> Ground.enabled = False (FloorHeightCm read back unchanged) -> MaterializeStructure -> IsStructureCurrent
  -> layer check: every surviving structure layer identical (count + bounds), the board layers gone,
     the Passage's own components / attached actors (wings) unchanged in bottom z
  -> "Passage 03 - Floor" moved/scaled to cover the route + the boards' footprint (apron, full width, + margin;
     from the lip exactly; never shrinks, never crosses the S3 hinge = "S3 Hangar Root"), top = board top + 0.5 cm,
     every slot = args "floor_material" (default WALNUT, the walnut herringbone MI; NOT copied from P01)
  -> read back -> census = level only -> save level -> census clean -> record state "applied"
  -> P03_FLOOR_APPLY_OK|run=..
REVERT: needs record state "applied" and the live state still as applied; re-enables Ground, re-materializes,
  checks current + layers back, restores the slab transform and override materials exactly, saves the level only.
A failure after the backup: NOTHING is saved; restart the editor with Don't Save.
Curved route: one slab cannot follow it; DRY reports a proposed tiling (tag P03Floor.Extra); APPLY refuses.

Planning functions are Unreal-free for test_p03_floor.py. No UE objects at module level (memory: MCP crashes).
"""
from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
import re
import shutil

WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP_REL = ("Content", "InfinityStage", "Dev", "Maps", "L_InfinityStage_V1VerticalSlice.umap")
STRUCTURE = "Infinity Stage - Structure 03"
SLAB = "Passage 03 - Floor"
P01_SLAB = "Passage 01 - Opening Floor"
HINGE_ROOT = "S3 Hangar Root"
EXTRA_TAG = "P03Floor.Extra"
CUBE = "/Engine/BasicShapes/Cube"
# Gary's "waxed shiny floor" = the walnut herringbone, set EXPLICITLY (args "floor_material" overrides). Not copied from
# P01: P01's slab has been MI_Floor_DarkWet since floor_dark_wet APPLY 01:55 (floor_dark_wet_record.json; P02 DRY log line
# P02_FLOOR_DRY_OK ... walnut=[MI_Floor_DarkWet]).
WALNUT = ("/Game/EnvironmentPacks/4K_WoodFlooring_Vol_02/Materials/M_Walnut_Hrrngbn_02_Mat_Inst_Dup."
          "M_Walnut_Hrrngbn_02_Mat_Inst_Dup")

LIFT_CM = 0.5                  # slab top above the boards' top (as p02_floor_walnut / floor_dark_wet)
RAISE_RANGE = (-0.05, 10.0)    # target_top - current top; 0 = already raised (floor_dark_wet, 01:55)
THICK_CM, THICK_TOL = 1.0, 0.05
ROUTE_Z_TOL, ROUTE_Y_TOL = 0.5, 1.0
HINGE_TOL = 1.0
MARGIN_CM = 50.0               # beyond the boards' footprint, each side
LAYER_TOL = 0.05
WING_Z_TOL = 0.01
READBACK_TOL = 0.05
TILE_CM = 1000.0

GROUND_TAGS = ("InfinityStage.Structure.Ground", "InfinityStage.Structure.Grooves", "InfinityStage.Structure.Understage")
PORTAL_BOARD_NAMES = ("StructureForestage", "StructureStageFront")
GROUND_FIELDS = ("enabled", "floor_height_cm", "board_thickness_cm", "apron_cm", "cut_chariot_slots",
                 "steel_grooves", "understage", "understage_depth_cm")
PORTAL_FIELDS = ("enabled", "forestage_depth_cm", "stage_front", "float_trough", "offset_from_first_station_cm")


class P03FloorError(RuntimeError):
    pass


# ============================================================================ pure planning (no unreal)
def frame_of(ox, oy, oz, yaw):
    return {"o": (float(ox), float(oy), float(oz)), "yaw": float(yaw)}


def to_frame(f, x, y, z):
    c, s = math.cos(math.radians(f["yaw"])), math.sin(math.radians(f["yaw"]))
    dx, dy = x - f["o"][0], y - f["o"][1]
    return (c * dx + s * dy, -s * dx + c * dy, z - f["o"][2])


def from_frame(f, x, y, z):
    c, s = math.cos(math.radians(f["yaw"])), math.sin(math.radians(f["yaw"]))
    return (f["o"][0] + c * x - s * y, f["o"][1] + s * x + c * y, f["o"][2] + z)


def yaw_diff(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


def aabb_in_frame(origin, extent, f):
    """World AABB (origin, half extent) -> [x0, x1, y0, y1, z0, z1]; x/y in frame f, z world."""
    pts = [to_frame(f, origin[0] + sx * extent[0], origin[1] + sy * extent[1], 0.0) for sx in (-1, 1) for sy in (-1, 1)]
    return [min(p[0] for p in pts), max(p[0] for p in pts), min(p[1] for p in pts), max(p[1] for p in pts),
            origin[2] - extent[2], origin[2] + extent[2]]


def box_extents(loc, rpy, scale, bbmin, bbmax, f):
    """Yaw-only box (mesh bounds x transform): x/y in frame f, z world. None if pitched/rolled."""
    roll, pitch, yaw = rpy
    if abs(roll) > 0.01 or abs(pitch) > 0.01:
        return None
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    xs, ys, zs = [], [], []
    for bx in (bbmin[0], bbmax[0]):
        for by in (bbmin[1], bbmax[1]):
            for bz in (bbmin[2], bbmax[2]):
                lx, ly, lz = bx * scale[0], by * scale[1], bz * scale[2]
                fx, fy, _ = to_frame(f, loc[0] + c * lx - s * ly, loc[1] + s * lx + c * ly, 0.0)
                xs.append(fx)
                ys.append(fy)
                zs.append(loc[2] + lz)
    return {"x": [min(xs), max(xs)], "y": [min(ys), max(ys)], "top": max(zs), "bottom": min(zs),
            "thick": max(zs) - min(zs)}


def route_checks(samples):
    """samples [(fx, fy, z, pitch, roll)] -> (z0, max_dy, curved, problems)."""
    if len(samples) < 2:
        return None, None, False, ["route: fewer than 2 samples"]
    z0 = samples[0][2]
    p = []
    dz = max(abs(s[2] - z0) for s in samples)
    if dz > ROUTE_Z_TOL:
        p.append("route not level: z varies %.2f cm" % dz)
    if max(max(abs(s[3]), abs(s[4])) for s in samples) > 0.05:
        p.append("route pitched/rolled")
    max_dy = max(abs(s[1]) for s in samples)
    return z0, max_dy, max_dy > ROUTE_Y_TOL, p


def layer_base(name):
    return re.sub(r"_\d+$", "", str(name))


def vanishes(name, tags):
    """True for the layers Ground.bEnabled=False removes (cpp :510-512, :584, :1348, :1369)."""
    return any(t in GROUND_TAGS for t in tags) or layer_base(name) in PORTAL_BOARD_NAMES


def layer_key(name, tags):
    return layer_base(name) + "|" + ",".join(sorted(str(t) for t in tags))


def required_rect(footprints, route_end_x, margin=MARGIN_CM):
    """footprints: frame rects [x0,x1,y0,y1] of the board layers that will vanish (Ground, Grooves, Forestage;
    the stage front's house floor and the understage are NOT walking floor). The boards already carry the Ground
    apron (cpp:1060-1061, clamped to the route, so never before x 0) and the forestage reaches the lip.
    x: from the lip exactly (no margin downstage: past the lip is the house / curtain spill), to the far end + margin.
    y: footprint + margin each side. Without boards (already off): the route only, y left to the current slab.
    -> {x:[..], y:[..] or None}."""
    xs0, xs1, ys0, ys1 = [0.0], [route_end_x], [], []
    for r in footprints:
        xs0.append(r[0])
        xs1.append(r[1] + margin)
        ys0.append(r[2] - margin)
        ys1.append(r[3] + margin)
    return {"x": [min(xs0), max(xs1)], "y": [min(ys0), max(ys1)] if ys0 else None}


def plan_slab(cur, req, hinge_x, tgt_top):
    """cur: current slab extents (box_extents); req: required_rect. Never shrinks; x1 = the hinge.
    -> (plan {x, y, top, thick}, problems)."""
    p = []
    if abs(cur["x"][1] - hinge_x) > HINGE_TOL:
        p.append("slab far edge %.2f is not on the S3 hinge %.2f (+-%.1f)" % (cur["x"][1], hinge_x, HINGE_TOL))
    if req["x"][1] > hinge_x + 0.5:
        p.append("route + apron reaches %.2f, past the S3 hinge %.2f: the hangar would be floored" % (req["x"][1], hinge_x))
    if abs(cur["thick"] - THICK_CM) > THICK_TOL:
        p.append("slab thickness %.3f not %.1f" % (cur["thick"], THICK_CM))
    rise = tgt_top - cur["top"]
    if not (RAISE_RANGE[0] <= rise <= RAISE_RANGE[1]):
        p.append("raise %.2f cm outside %s" % (rise, RAISE_RANGE))
    y = list(cur["y"]) if req["y"] is None else [min(cur["y"][0], req["y"][0]), max(cur["y"][1], req["y"][1])]
    return {"x": [min(cur["x"][0], req["x"][0]), hinge_x], "y": y, "top": tgt_top, "thick": cur["thick"],
            "raise_cm": rise}, p


def cube_xf(plan, f, bbmin, bbmax):
    """Location (world) + scale for a yaw-only mesh whose bounds are bbmin..bbmax to fill plan exactly."""
    size = [bbmax[i] - bbmin[i] for i in range(3)]
    scale = [(plan["x"][1] - plan["x"][0]) / size[0], (plan["y"][1] - plan["y"][0]) / size[1], plan["thick"] / size[2]]
    cl = [(bbmin[i] + bbmax[i]) / 2.0 * scale[i] for i in range(3)]          # local centre offset, scaled
    cx, cy = (plan["x"][0] + plan["x"][1]) / 2.0 - cl[0], (plan["y"][0] + plan["y"][1]) / 2.0 - cl[1]
    wx, wy, _ = from_frame(f, cx, cy, 0.0)
    return [wx, wy, plan["top"] - plan["thick"] / 2.0 - cl[2]], scale


def uncovered(route_pts, rect):
    """route_pts [(fx, fy)] every ~100 cm. -> cm of the route line off the rect."""
    if len(route_pts) < 2:
        return 0.0
    pts = list(route_pts)
    off = 0.0
    for i in range(len(pts) - 1):
        mx, my = (pts[i][0] + pts[i + 1][0]) / 2.0, (pts[i][1] + pts[i + 1][1]) / 2.0
        if not (rect["x"][0] <= mx <= rect["x"][1] and rect["y"][0] <= my <= rect["y"][1]):
            off += math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
    return off


def area_outside(req, cur):
    """m^2 of req not covered by cur (both axis rects in the same frame)."""
    if req["y"] is None:
        return 0.0
    def a(r):
        return max(0.0, r["x"][1] - r["x"][0]) * max(0.0, r["y"][1] - r["y"][0])
    inter = {"x": [max(req["x"][0], cur["x"][0]), min(req["x"][1], cur["x"][1])],
             "y": [max(req["y"][0], cur["y"][0]), min(req["y"][1], cur["y"][1])]}
    return (a(req) - a(inter)) / 1.0e4


def propose_tiles(world_samples, half_width_cm, tile_cm=TILE_CM):
    """Curved route: oriented 1 cm slabs along it, ~tile_cm each, 5% overlap. world_samples [(dist, x, y, yaw)]."""
    tiles, start = [], 0
    for i in range(1, len(world_samples)):
        if world_samples[i][0] - world_samples[start][0] >= tile_cm or i == len(world_samples) - 1:
            a, b = world_samples[start], world_samples[i]
            length = math.hypot(b[1] - a[1], b[2] - a[2]) * 1.05
            yaw = math.degrees(math.atan2(b[2] - a[2], b[1] - a[1]))
            tiles.append({"centre": [(a[1] + b[1]) / 2.0, (a[2] + b[2]) / 2.0], "yaw": yaw,
                          "size": [length, 2.0 * half_width_cm, THICK_CM], "tag": EXTRA_TAG})
            start = i
    return tiles


def poke_through(lay, rect, top):
    """Surviving layers (Ground off keeps them) whose bounds cross the new slab top inside its footprint.
    Component bounds are coarse (a whole layer's box): a hit means 'look', not 'proven'."""
    out = []
    for k, ents in lay.items():
        if vanishes(k.split("|")[0], k.split("|")[1].split(",") if k.split("|")[1] else []):
            continue
        for e in ents:
            b = e["b"]
            if b and e["count"] and b[4] < top < b[5] and b[0] < rect["x"][1] and rect["x"][0] < b[1]                     and b[2] < rect["y"][1] and rect["y"][0] < b[3]:
                out.append({"layer": k, "count": e["count"], "bounds": _r(b)})
    return out


def compare_layers(before, after):
    """{key: [entry]} entry {"count", "b": [x0,x1,y0,y1,z0,z1] or None}. Surviving layers identical, vanishing
    layers empty, nothing new. -> problems."""
    p = []
    for k, ents in before.items():
        gone = vanishes(k.split("|")[0], k.split("|")[1].split(",") if k.split("|")[1] else [])
        got = after.get(k, [])
        if gone:
            n = sum(e["count"] for e in got)
            if n:
                p.append("%s: still %d instances with Ground off" % (k, n))
            continue
        if len(got) != len(ents):
            p.append("%s: %d components -> %d" % (k, len(ents), len(got)))
            continue
        for e0, e1 in zip(sorted(ents, key=_ek), sorted(got, key=_ek)):
            if e0["count"] != e1["count"]:
                p.append("%s: %d -> %d instances" % (k, e0["count"], e1["count"]))
            elif e0["b"] is not None and e1["b"] is not None and any(abs(a - b) > LAYER_TOL for a, b in zip(e0["b"], e1["b"])):
                p.append("%s: bounds %s -> %s" % (k, _r(e0["b"]), _r(e1["b"])))
    for k in after:
        if k not in before and sum(e["count"] for e in after[k]):
            p.append("%s: new layer after materialize" % k)
    return p


def compare_restored(before, after):
    """REVERT: every recorded layer back with the same component count; instance counts / bounds reported,
    surviving layers exact. -> (problems, notes)."""
    p, notes = [], []
    for k, ents in before.items():
        got = after.get(k, [])
        if len(got) != len(ents):
            p.append("%s: %d components recorded, %d after re-enable" % (k, len(ents), len(got)))
            continue
        for e0, e1 in zip(sorted(ents, key=_ek), sorted(got, key=_ek)):
            same = e0["count"] == e1["count"] and (e0["b"] is None or e1["b"] is None
                                                   or all(abs(a - b) <= LAYER_TOL for a, b in zip(e0["b"], e1["b"])))
            if not same:
                gone = vanishes(k.split("|")[0], k.split("|")[1].split(",") if k.split("|")[1] else [])
                (notes if gone and e1["count"] > 0 else p).append("%s: %s -> %s" % (k, (e0["count"], _r(e0["b"])), (e1["count"], _r(e1["b"]))))
    return p, notes


def compare_wings(before, after):
    """{name: z0 or None}. -> problems (z0 moved, or a component appeared/disappeared)."""
    p = []
    for k, z in before.items():
        if k not in after:
            p.append("wing/passage piece %s disappeared" % k)
        elif z is not None and after[k] is not None and abs(z - after[k]) > WING_Z_TOL:
            p.append("wing/passage piece %s bottom %.3f -> %.3f" % (k, z, after[k]))
    p += ["wing/passage piece %s appeared" % k for k in after if k not in before]
    return p


def _ek(e):
    return (e["count"], tuple(round(v, 1) for v in (e["b"] or [])))


def _r(b):
    return None if b is None else [round(v, 2) for v in b]


def strip_none(lst):
    lst = list(lst)
    while lst and lst[-1] is None:
        lst.pop()
    return lst


def same_xf(a, b, tol):
    return all(abs(x - y) <= tol for k in ("loc", "rot", "scale") for x, y in zip(a[k], b[k]))


# ============================================================================ editor adapters
def _u():
    import unreal  # noqa: PLC0415  (the harness injects a fake into sys.modules)
    return unreal


def _path(o):
    return None if o is None else o.get_path_name().split(".")[0]


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Ctx:
    def __init__(self, mode):
        u = _u()
        self.u, self.mode = u, mode
        self.repo = os.path.normpath(u.Paths.convert_relative_path_to_full(u.Paths.project_dir()))
        self.here = os.path.join(self.repo, "Saved", "CodexConductor")
        self.run = datetime.datetime.now().strftime("P03FLOOR-%Y%m%d-%H%M%S")
        self.record = os.path.join(self.here, "p03_floor_record.json")
        self.umap = os.path.join(self.repo, *UMAP_REL)
        self.past_backup = False

    def log(self, msg):
        self.u.log(msg)

    def fail(self, msg):
        tail = "|NOTHING SAVED; restart the editor with Don't Save" if self.past_backup else ""
        self.u.log_error("P03_FLOOR_FAILED|run=%s|mode=%s|%s%s" % (self.run, self.mode, msg, tail))
        raise P03FloorError("P03_FLOOR_FAILED|run=%s|%s" % (self.run, msg))


def write_json(c, path, payload, exclusive=False):
    if exclusive:
        with open(path, "x", encoding="utf-8") as fh:      # exclusive: a second APPLY cannot overwrite it
            json.dump(payload, fh, indent=1)
            fh.flush()
            os.fsync(fh.fileno())
    else:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=1)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    if json.load(open(path, encoding="utf-8")) != json.loads(json.dumps(payload)):
        c.fail("%s did not read back" % os.path.basename(path))


def census(u):
    lib = u.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def guards(c, need_clean):
    u = c.u
    ed = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        c.fail("PIE_ACTIVE")
    world = ed.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != WORLD:
        c.fail("WRONG_WORLD|%s" % (world.get_path_name() if world else None))
    actors = list(u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors())
    if need_clean:
        d = census(u)
        if d != {"content": [], "maps": []}:
            c.fail("DIRTY_BEFORE|" + json.dumps(d))
        bench = [str(a.get_actor_label()) for a in actors if str(a.get_actor_label()).startswith(("ZZ_", "TEMP", "Temp"))]
        if bench:
            c.fail("BENCH_ACTORS|%s" % bench[:6])
        if u.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
            c.fail("SEQUENCER_OPEN")
    return ed, world, actors


def struct_fields(s, names):
    out = {}
    for n in names:
        try:
            v = s.get_editor_property(n)
            out[n] = v if isinstance(v, (bool, int, float, str)) or v is None else str(v)
        except Exception as exc:  # report-only: a missing field never blocks
            out[n] = "unread: %s" % exc
    return out


def xf_of(a):
    loc, rot, sc = a.get_actor_location(), a.get_actor_rotation(), a.get_actor_scale3d()
    return {"loc": [loc.x, loc.y, loc.z], "rot": [rot.roll, rot.pitch, rot.yaw], "scale": [sc.x, sc.y, sc.z]}


def smc_of(a):
    return a.get_component_by_class(_u().StaticMeshComponent)


def slab_geom(a, f):
    smc = smc_of(a)
    mesh = smc.get_editor_property("static_mesh")
    bb = mesh.get_bounding_box()
    wt = smc.get_world_transform()
    r = wt.rotation.rotator()
    bbmin, bbmax = (bb.min.x, bb.min.y, bb.min.z), (bb.max.x, bb.max.y, bb.max.z)
    ext = box_extents((wt.translation.x, wt.translation.y, wt.translation.z), (r.roll, r.pitch, r.yaw),
                      (wt.scale3d.x, wt.scale3d.y, wt.scale3d.z), bbmin, bbmax, f)
    return mesh, (r.roll, r.pitch, r.yaw), ext, bbmin, bbmax


def materials(a):
    smc = smc_of(a)
    return [m.get_path_name() if m else None for m in smc.get_materials()]


def overrides(a):
    return [m.get_path_name() if m else None for m in smc_of(a).get_editor_property("override_materials")]


def comp_bounds(u, comp):
    """AABB of the INSTANCE ORIGINS (world), not the component's cached Bounds: MaterializeStructure re-creates the
    components and the cached Bounds read all-zero in the same Python call (6 Oct 01:47 false LAYERS_OR_WINGS_CHANGED;
    the log showed every layer rebuilt with identical counts). Returned as (centre, half-extent) like before."""
    try:
        n = int(comp.get_instance_count())
        if n == 0:
            return None
        xs, ys, zs = [], [], []
        for i in range(n):
            t = comp.get_instance_transform(i, True)
            loc = t.translation
            xs.append(loc.x); ys.append(loc.y); zs.append(loc.z)
        lo, hi = (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))
        return tuple((a + b) / 2 for a, b in zip(lo, hi)), tuple((b - a) / 2 for a, b in zip(lo, hi))
    except Exception:  # noqa: BLE001  no per-instance API (offline fake) -> the old cached-bounds read
        try:
            o, e, _ = u.SystemLibrary.get_component_bounds(comp)
            return (o.x, o.y, o.z), (e.x, e.y, e.z)
        except Exception:  # noqa: BLE001  unreadable -> compared by count only
            return None


def layers(u, s, f):
    out = {}
    for comp in s.get_components_by_class(u.InstancedStaticMeshComponent):
        tags = [str(t) for t in comp.get_editor_property("component_tags")]
        b = comp_bounds(u, comp)
        n = int(comp.get_instance_count())
        out.setdefault(layer_key(comp.get_name(), tags), []).append(
            {"count": n, "b": None if (b is None or n == 0) else aabb_in_frame(b[0], b[1], f), "name": str(comp.get_name())})
    return out


def wing_bottoms(u, passage):
    """Bottom z of every primitive on the Passage actor and on actors attached to it (the wings)."""
    out = {}
    for comp in passage.get_components_by_class(u.PrimitiveComponent):
        b = comp_bounds(u, comp)
        out["P|" + str(comp.get_name())] = None if b is None else b[0][2] - b[1][2]
    for a in passage.get_attached_actors():
        o, e = a.get_actor_bounds(False)
        out["A|" + str(a.get_actor_label())] = o.z - e.z
    return out


# ============================================================================ the plan (every mode)
def build_plan(c, actors):
    u = c.u
    problems = []
    st = [a for a in actors if str(a.get_actor_label()) == STRUCTURE and isinstance(a, u.InfinityStageStructureActor)]
    if len(st) != 1:
        c.fail("STRUCTURE_COUNT|%d" % len(st))
    s = st[0]
    named = {}
    for a in actors:
        named.setdefault(str(a.get_actor_label()), []).append(a)
    counts = {l: len(named.get(l, [])) for l in (SLAB, P01_SLAB, HINGE_ROOT)}
    if any(v != 1 for v in counts.values()):
        c.fail("LABEL_COUNTS|%s" % counts)
    slab, p01, root = named[SLAB][0], named[P01_SLAB][0], named[HINGE_ROOT][0]
    passage = s.get_editor_property("passage")
    if passage is None or not str(passage.get_actor_label()).startswith("Passage 03"):
        c.fail("PASSAGE|%s" % (passage.get_actor_label() if passage else None))
    route = passage.get_editor_property("route")
    W = u.SplineCoordinateSpace.WORLD
    length = float(route.get_spline_length())
    t0 = route.get_transform_at_distance_along_spline(0.0, W, False)
    f = frame_of(t0.translation.x, t0.translation.y, t0.translation.z, t0.rotation.rotator().yaw)
    n = max(2, int(length // 100.0))
    samples, wsamples = [], []
    for i in range(n + 1):
        d = length * i / n
        t = route.get_transform_at_distance_along_spline(d, W, False)
        r = t.rotation.rotator()
        fx, fy, _ = to_frame(f, t.translation.x, t.translation.y, t.translation.z)
        samples.append((fx, fy, t.translation.z, r.pitch, r.roll))
        wsamples.append((d, t.translation.x, t.translation.y, r.yaw))
    z0, max_dy, curved, rp = route_checks(samples)
    problems += rp
    g = s.get_editor_property("ground")
    gf = struct_fields(g, GROUND_FIELDS)
    pf = struct_fields(s.get_editor_property("portal"), PORTAL_FIELDS)
    fh = float(g.get_editor_property("floor_height_cm"))
    board_top = z0 + fh
    tgt = board_top + LIFT_CM
    lay = layers(u, s, f)
    walk = [e["b"] for k, ents in lay.items() for e in ents
            if e["b"] is not None and e["count"] > 0 and vanishes(k.split("|")[0], k.split("|")[1].split(","))
            and "InfinityStage.Structure.Understage" not in k and not k.startswith("StructureStageFront")]
    removes = {k: {"components": len(v), "instances": sum(e["count"] for e in v), "rect": [_r(e["b"]) for e in v]}
               for k, v in lay.items() if vanishes(k.split("|")[0], k.split("|")[1].split(",") if k.split("|")[1] else [])}
    req = required_rect(walk, samples[-1][0])
    mesh, rpy, cur, bbmin, bbmax = slab_geom(slab, f)
    if _path(mesh) != CUBE:
        problems.append("slab mesh %s is not %s" % (_path(mesh), CUBE))
    if cur is None:
        c.fail("SLAB_PITCHED_OR_ROLLED|%s" % (rpy,))
    if yaw_diff(rpy[2], f["yaw"]) > 0.01:
        problems.append("slab yaw %.3f vs route %.3f" % (rpy[2], f["yaw"]))
    if slab.get_attached_actors():
        problems.append("slab carries attached actors %s" % [x.get_actor_label() for x in slab.get_attached_actors()][:4])
    rl = root.get_actor_location()
    hinge = to_frame(f, rl.x, rl.y, rl.z)[0]
    plan, pp = plan_slab(cur, req, hinge, tgt)
    problems += pp
    tiles = []
    if curved:
        tiles = propose_tiles(wsamples, max(abs(req["y"][0]), abs(req["y"][1])) if req["y"] else 1000.0)
        problems.append("ROUTE_CURVED|max_dy=%.1f cm: one slab cannot follow it; proposal = %d %s slabs (not built "
                        "by this tool; needs its own review)" % (max_dy, len(tiles), EXTRA_TAG))
    loc, scale = cube_xf(plan, f, bbmin, bbmax)
    walnut = [c.floor_material]
    if u.load_asset(c.floor_material) is None:
        problems.append("floor material %s does not load" % c.floor_material)
    route_pts = [(x[0], x[1]) for x in samples]
    rep = {"run": c.run, "mode": c.mode, "frame": f, "route_len": length, "route_end_x": samples[-1][0],
           "route_max_dy": max_dy, "curved": curved, "board_top": board_top, "target_top": tgt,
           "ground": gf, "portal": pf, "boards_on": bool(g.get_editor_property("enabled")),
           "removes": removes, "required": req, "hinge_x": hinge,
           "slab": {"label": SLAB, "xf": xf_of(slab), "overrides": overrides(slab), "materials": materials(slab),
                    "num_materials": int(smc_of(slab).get_num_materials()), "ext": cur},
           "uncovered_now_cm": uncovered(route_pts, cur),
           "uncovered_area_now_m2": area_outside(req, cur),
           "uncovered_after_cm": uncovered(route_pts, plan),
           "poke_through": poke_through(lay, plan, tgt), "p01_materials_info_only": materials(p01),
           "plan": dict(plan, loc=loc, scale=scale, rot=xf_of(slab)["rot"], materials=walnut),
           "proposed_tiles": tiles, "layers": lay,
           "wings": wing_bottoms(u, passage), "problems": problems}
    return rep, {"s": s, "slab": slab, "passage": passage, "f": f}


# ============================================================================ phases
def phase_dry(c):
    u = c.u
    _, _, actors = guards(c, need_clean=False)
    before = census(u)
    rep, _ = build_plan(c, actors)
    if census(u) != before:
        c.fail("DRY dirtied %s -> %s" % (before, census(u)))
    live = []
    if before != {"content": [], "maps": []}:
        live.append("editor dirty %s" % json.dumps(before))
    if os.path.exists(c.record):
        live.append("record exists (applied, not reverted)")
    rep["live_blockers"] = live
    path = os.path.join(c.here, "p03_floor_dry_%s.json" % c.run)
    write_json(c, path, rep)
    c.log("P03_FLOOR_DRY_BOARDS|run=%s|boards_on=%s|ground=%s|portal=%s" % (c.run, rep["boards_on"], json.dumps(rep["ground"]), json.dumps(rep["portal"])))
    c.log("P03_FLOOR_DRY_POKE|run=%s|surviving layers crossing the new top (coarse bounds)=%s|p01_now=%s"
          % (c.run, json.dumps(rep["poke_through"]), rep["p01_materials_info_only"]))
    c.log("P03_FLOOR_DRY_REMOVES|run=%s|%s" % (c.run, json.dumps({k: (v["components"], v["instances"]) for k, v in rep["removes"].items()})))
    c.log("P03_FLOOR_DRY_COVERAGE|run=%s|route_x=0..%.1f|route_max_dy=%.2f|apron=%s|slab_x=%s|slab_y=%s|slab_top=%.2f"
          "|required_x=%s|required_y=%s|hinge=%.2f|uncovered_route_now_cm=%.1f|uncovered_area_now_m2=%.2f"
          % (c.run, rep["route_end_x"], rep["route_max_dy"], rep["ground"].get("apron_cm"), _r(rep["slab"]["ext"]["x"]),
             _r(rep["slab"]["ext"]["y"]), rep["slab"]["ext"]["top"], _r(rep["required"]["x"]),
             _r(rep["required"]["y"]) if rep["required"]["y"] else None, rep["hinge_x"], rep["uncovered_now_cm"],
             rep["uncovered_area_now_m2"]))
    pl = rep["plan"]
    c.log("P03_FLOOR_DRY_PLAN|run=%s|x=%s|y=%s|top=%.2f|raise_cm=%.2f|loc=%s|scale=%s|materials_now=%s|materials_new=%s"
          "|uncovered_after_cm=%.1f" % (c.run, _r(pl["x"]), _r(pl["y"]), pl["top"], pl["raise_cm"], _r(pl["loc"]), _r(pl["scale"]),
                                        rep["slab"]["materials"], pl["materials"], rep["uncovered_after_cm"]))
    ok = not (rep["problems"] or live)
    c.log("P03_FLOOR_DRY_%s|run=%s|apply_ready=%d|problems=%s|live_blockers=%s|mutated=0|report=%s"
          % ("OK" if ok else "REFUSED", c.run, int(ok), rep["problems"], live, path))
    return rep


def phase_apply(c):
    u = c.u
    ed, world, actors = guards(c, need_clean=True)
    if os.path.exists(c.record):
        c.fail("RECORD_EXISTS|REVERT first (or, for a failed APPLY, Don't-Save restart then archive the record)")
    rep, h = build_plan(c, actors)
    if rep["problems"]:
        c.fail("REFUSED|%s" % rep["problems"])
    if not rep["boards_on"]:
        c.fail("BOARDS_ALREADY_OFF|nothing recorded to restore")
    s, slab, passage, f = h["s"], h["slab"], h["passage"], h["f"]
    rec = {"run": c.run, "state": "applying", "written": datetime.datetime.now().isoformat(timespec="seconds"),
           "ground": rep["ground"], "slab": rep["slab"], "plan": rep["plan"], "layers": rep["layers"],
           "wings": rep["wings"], "board_top": rep["board_top"], "target_top": rep["target_top"]}
    write_json(c, c.record, rec, exclusive=True)
    backup = os.path.join(c.repo, "Backups", "PreP03Floor-%s" % c.run)
    os.makedirs(backup)
    c.past_backup = True
    shutil.copy2(c.umap, backup)
    shutil.copy2(c.record, backup)
    pre_sha = _sha(c.umap)
    if _sha(os.path.join(backup, UMAP_REL[-1])) != pre_sha:
        c.fail("BACKUP_MISMATCH")
    c.log("P03_FLOOR_BACKUP_OK|run=%s|%s" % (c.run, backup))
    # 1. boards off, FloorHeightCm kept
    g = s.get_editor_property("ground")
    g.set_editor_property("enabled", False)
    s.modify()
    s.set_editor_property("ground", g)
    g2 = s.get_editor_property("ground")
    if g2.get_editor_property("enabled") or abs(float(g2.get_editor_property("floor_height_cm")) - rep["ground"]["floor_height_cm"]) > 1e-6:
        c.fail("GROUND_READBACK|enabled=%s|floor_height=%s" % (g2.get_editor_property("enabled"), g2.get_editor_property("floor_height_cm")))
    # 2. materialize
    if not s.materialize_structure():
        c.fail("MATERIALIZE_FAILED")
    if not s.is_structure_current():
        c.fail("NOT_CURRENT")
    lp = compare_layers(rep["layers"], layers(u, s, f))
    wp = compare_wings(rep["wings"], wing_bottoms(u, passage))
    if lp or wp:
        c.fail("LAYERS_OR_WINGS_CHANGED|%s" % (lp + wp))
    # 3. slab
    pl = rep["plan"]
    smc = smc_of(slab)
    slab.modify()
    slab.set_actor_location(u.Vector(*pl["loc"]), False, False)
    slab.set_actor_scale3d(u.Vector(*pl["scale"]))
    for i in range(rep["slab"]["num_materials"]):
        m = pl["materials"][min(i, len(pl["materials"]) - 1)]
        smc.set_material(i, u.load_asset(m) if m else None)
    # 4. read back
    _, rpy, ext, _, _ = slab_geom(slab, f)
    bad = []
    if ext is None or abs(ext["top"] - pl["top"]) > READBACK_TOL or \
            any(abs(ext[ax][i] - pl[ax][i]) > READBACK_TOL for ax in ("x", "y") for i in (0, 1)):
        bad.append("slab extents %s want x=%s y=%s top=%s" % (ext, pl["x"], pl["y"], pl["top"]))
    if yaw_diff(rpy[2], f["yaw"]) > 0.01:
        bad.append("slab yaw changed")
    want = [pl["materials"][min(i, len(pl["materials"]) - 1)] for i in range(rep["slab"]["num_materials"])]
    if materials(slab)[:len(want)] != want:
        bad.append("materials %s want %s" % (materials(slab), want))
    if bad:
        c.fail("READBACK|%s" % bad)
    # 5. save the level only
    d = census(u)
    if d["content"] or d["maps"] != [WORLD]:
        c.fail("DIRTY_SCOPE|%s" % json.dumps(d))
    if not u.EditorLoadingAndSavingUtils.save_map(world, WORLD):
        c.fail("SAVE_FAILED")
    if census(u) != {"content": [], "maps": []}:
        c.fail("POST_SAVE_DIRTY|%s" % json.dumps(census(u)))
    if _sha(c.umap) == pre_sha:
        c.fail("UMAP_UNCHANGED_ON_DISK")
    rec.update(state="applied", applied=datetime.datetime.now().isoformat(timespec="seconds"), backup=backup,
               after={"xf": xf_of(slab), "overrides": overrides(slab), "ext": ext})
    write_json(c, c.record, rec)
    c.log("P03_FLOOR_APPLY_OK|run=%s|boards_off=1|floor_height_kept=%s|slab_x=%s|slab_y=%s|top=%.2f|materials=%s"
          "|layers_ok=1|wings_ok=1|level_saved=1|dirty_after=0+0|backup=%s"
          % (c.run, rep["ground"]["floor_height_cm"], _r(ext["x"]), _r(ext["y"]), ext["top"], want, backup))
    return rec


def phase_revert(c):
    u = c.u
    ed, world, actors = guards(c, need_clean=True)
    if not os.path.exists(c.record):
        c.fail("NO_RECORD")
    rec = json.load(open(c.record, encoding="utf-8"))
    if rec.get("state") != "applied":
        c.fail("RECORD_STATE|%s: an APPLY that did not save is undone by a Don't-Save restart, not REVERT" % rec.get("state"))
    st = [a for a in actors if str(a.get_actor_label()) == STRUCTURE and isinstance(a, u.InfinityStageStructureActor)]
    sl = [a for a in actors if str(a.get_actor_label()) == SLAB]
    if len(st) != 1 or len(sl) != 1:
        c.fail("LABEL_COUNTS|structure=%d|slab=%d" % (len(st), len(sl)))
    s, slab = st[0], sl[0]
    if s.get_editor_property("ground").get_editor_property("enabled"):
        c.fail("NOT_APPLIED_STATE|boards are on")
    if not same_xf(xf_of(slab), rec["after"]["xf"], 0.05) or strip_none(overrides(slab)) != strip_none(rec["after"]["overrides"]):
        c.fail("NOT_APPLIED_STATE|slab %s vs applied %s" % (xf_of(slab), rec["after"]))
    passage = s.get_editor_property("passage")
    route = passage.get_editor_property("route")
    t0 = route.get_transform_at_distance_along_spline(0.0, u.SplineCoordinateSpace.WORLD, False)
    f = frame_of(t0.translation.x, t0.translation.y, t0.translation.z, t0.rotation.rotator().yaw)
    backup = os.path.join(c.repo, "Backups", "PreP03FloorRevert-%s" % c.run)
    os.makedirs(backup)
    c.past_backup = True
    shutil.copy2(c.umap, backup)
    shutil.copy2(c.record, backup)
    if _sha(os.path.join(backup, UMAP_REL[-1])) != _sha(c.umap):
        c.fail("BACKUP_MISMATCH")
    g = s.get_editor_property("ground")
    g.set_editor_property("enabled", bool(rec["ground"]["enabled"]))
    s.modify()
    s.set_editor_property("ground", g)
    if bool(s.get_editor_property("ground").get_editor_property("enabled")) != bool(rec["ground"]["enabled"]):
        c.fail("GROUND_READBACK")
    if not s.materialize_structure():
        c.fail("MATERIALIZE_FAILED")
    if not s.is_structure_current():
        c.fail("NOT_CURRENT")
    lp, notes = compare_restored(rec["layers"], layers(u, s, f))
    wp = compare_wings(rec["wings"], wing_bottoms(u, passage))
    if lp or wp:
        c.fail("LAYERS_NOT_RESTORED|%s" % (lp + wp))
    o = rec["slab"]["xf"]
    slab.modify()
    slab.set_actor_location(u.Vector(*o["loc"]), False, False)
    slab.set_actor_rotation(u.Rotator(roll=o["rot"][0], pitch=o["rot"][1], yaw=o["rot"][2]), False)
    slab.set_actor_scale3d(u.Vector(*o["scale"]))
    smc = smc_of(slab)
    orig = rec["slab"]["overrides"]
    for i in range(max(len(orig), smc.get_num_materials())):
        pth = orig[i] if i < len(orig) else None
        smc.set_material(i, u.load_asset(pth) if pth else None)
    bad = []
    if not same_xf(xf_of(slab), o, 1e-3):
        bad.append("transform %s != %s" % (xf_of(slab), o))
    if strip_none(overrides(slab)) != strip_none(orig):
        bad.append("overrides %s != %s" % (overrides(slab), orig))
    if materials(slab) != rec["slab"]["materials"]:
        bad.append("materials %s != %s" % (materials(slab), rec["slab"]["materials"]))
    if bad:
        c.fail("READBACK|%s" % bad)
    d = census(u)
    if d["content"] or d["maps"] != [WORLD]:
        c.fail("DIRTY_SCOPE|%s" % json.dumps(d))
    if not u.EditorLoadingAndSavingUtils.save_map(world, WORLD):
        c.fail("SAVE_FAILED")
    if census(u) != {"content": [], "maps": []}:
        c.fail("POST_SAVE_DIRTY|%s" % json.dumps(census(u)))
    os.replace(c.record, c.record.replace(".json", ".reverted-%s.json" % c.run))
    c.log("P03_FLOOR_REVERT_OK|run=%s|boards_on=1|slab_restored=1|board_layout_notes=%s|level_saved=1|dirty_after=0+0|backup=%s"
          % (c.run, notes, backup))
    return rec


def main(args=None):
    c = Ctx("DRY")
    if args is None:
        args = json.load(open(os.path.join(c.here, "p03_floor_args.json"), encoding="utf-8"))
    c.floor_material = str(args.get("floor_material") or WALNUT)
    mode = str(args.get("mode", "DRY")).upper()
    c.mode = mode
    phases = {"DRY": phase_dry, "APPLY": phase_apply, "REVERT": phase_revert}
    if mode not in phases:
        c.fail("UNKNOWN_MODE|%s" % mode)
    if mode != "DRY" and args.get("confirm") != "%s P03FLOOR" % mode:
        c.fail("CONFIRM_MISSING|want '%s P03FLOOR'" % mode)
    c.log("P03_FLOOR_START|run=%s|mode=%s" % (c.run, mode))
    try:
        return phases[mode](c)
    except P03FloorError:
        raise
    except Exception as exc:  # an API surprise still leaves a run-stamped failure marker
        c.fail("UNEXPECTED|%s: %s" % (type(exc).__name__, exc))


if __name__ == "__p03_floor_runner__":
    main()
