"""P02 floor: boards off ONLY (Gary 6 Oct: P02 floor "not walnut shiny"; chose "Boards off now only").
Written offline 6 Oct, NOT RUN. Modelled on p03_floor.py (applied 6 Oct, run P03FLOOR-20261006-124934).

What it does: Structure 02's Ground.bEnabled -> False, MaterializeStructure, save the level. Nothing else.
  - Ground off removes boards, chariot slots, steel grooves, understage, the FORESTAGE boards and the STAGE FRONT
    (InfinityStageStructureActor.cpp :510-512 BoardMesh/UnderstageMesh only loaded with Ground on, :584 BuildGround
    skipped, :1342-1348/:1369 forestage + stage front need BoardMesh/Ground) = Gary's "remove everything" (5 Oct, P02+P03).
  - FloorHeightCm is KEPT (fence base, piers, ground cloths read it; p03_floor.py docstring lines).
  - The four walnut slabs "Passage 02 - Floor Near/Left/Right/Far" are NOT moved, rescaled or re-materialled. Walnut
    went on at WALNUT-20261006-112225 (floor_walnut_material_record.json); the slabs were raised to top +0.5 cm at
    P02FL-20261005-103517 (p02_floor_walnut_record.json). This tool ASSERTS that state and refuses if it differs.
  - P02 is NOT straightened (the route stays curved; p02_straighten.py is held).

Coverage (DRY and APPLY): every walking-floor point the boards covered must now lie on a slab or inside the S2 hangar
pit (the hole the four slabs frame around the dock, hangar_s2_record.json "dock"). Points = the route centreline every
100 cm + every INSTANCE ORIGIN of the walking board layers (Ground, Grooves, Forestage). Stage front and understage
are reported, not gated (not walking floor; P03 precedent). Any gap OUTSIDE the pit refuses APPLY; the DRY then
reports a proposed slab growth (report only: this tool never moves a slab; that needs its own review/Gary).

Layers: every structure layer other than the vanishing ones keeps the same instance counts and INSTANCE-TRANSFORM
bounds (comp_bounds: instance origins, NOT the cached component Bounds, which read all-zero right after
MaterializeStructure: the 6 Oct 01:47 P03 false alarm). Passage components / attached actors (wings) unchanged.

Interplay: refuses (APPLY and REVERT; DRY lists it as a live blocker) while Saved/CodexConductor/p02_straighten_record.json
exists (an active straighten; its floor step also turns Ground off and records the Ground struct for its own REVERT).

Args p02_floor_args.json {"mode": "DRY"|"APPLY"|"REVERT", "confirm": "<MODE> P02FLOOR"}.
APPLY: guards (no PIE, right world, clean census, no ZZ_/TEMP actors, Sequencer closed, no straighten record, no own
  record) -> plan (any problem refuses) -> record (exclusive, fsync, read back) + umap backup Backups/PreP02Floor-<run>
  (sha checked) -> Ground.enabled False (other Ground fields read back unchanged) -> MaterializeStructure ->
  IsStructureCurrent -> layers + wings + slabs unchanged -> census = level only -> save level -> census clean ->
  umap changed on disk -> Ground read back off -> record "applied" -> P02_FLOOR_APPLY_OK|run=..
REVERT: record "applied", Ground still off, slabs as recorded -> Ground.enabled True -> materialize -> current ->
  layers restored (surviving exact; board layout differences noted) -> wings/slabs unchanged -> save level only ->
  record renamed .reverted-<run> -> P02_FLOOR_REVERT_OK|run=..
A failure after the backup: NOTHING is saved; restart the editor with Don't Save.
Marker prefix P02_FLOOR_ is shared with p02_floor_walnut.py (5 Oct, run ids P02FL-...); this tool's run ids are
P02FLOOR-...: parse by run id (memory puss-log-markers-run-id).

Planning functions are Unreal-free for test_p02_floor.py. No UE objects at module level (memory: MCP crashes).
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
HANGAR_REL = ("Saved", "CodexStructure", "hangar_s2_record.json")
STRAIGHTEN_REC = "p02_straighten_record.json"
STRUCTURE = "Infinity Stage - Structure 02"
PASSAGE_PREFIX = "Passage 02"
SLABS = ("Passage 02 - Floor Near", "Passage 02 - Floor Left", "Passage 02 - Floor Right", "Passage 02 - Floor Far")
FRAME_SLAB = SLABS[0]
CUBE = "/Engine/BasicShapes/Cube"
WALNUT = ("/Game/EnvironmentPacks/4K_WoodFlooring_Vol_02/Materials/M_Walnut_Hrrngbn_02_Mat_Inst_Dup."
          "M_Walnut_Hrrngbn_02_Mat_Inst_Dup")

LIFT_CM = 0.5                  # slab top above the boards' top (p02_floor_walnut target_top 0.5)
TOP_TOL = 0.05
THICK_CM, THICK_TOL = 1.0, 0.05
ROUTE_Z_TOL = 0.5
ROUTE_STEP_CM = 100.0
LAYER_TOL = 0.05
WING_Z_TOL = 0.01
SLAB_TOL = 1e-3
GAP_LIST_MAX = 40

GROUND_TAGS = ("InfinityStage.Structure.Ground", "InfinityStage.Structure.Grooves", "InfinityStage.Structure.Understage")
PORTAL_BOARD_NAMES = ("StructureForestage", "StructureStageFront")
NOT_WALKING = ("InfinityStage.Structure.Understage", "StructureStageFront")
GROUND_FIELDS = ("enabled", "floor_height_cm", "board_thickness_cm", "apron_cm", "cut_chariot_slots",
                 "steel_grooves", "understage", "understage_depth_cm")
PORTAL_FIELDS = ("enabled", "forestage_depth_cm", "stage_front", "float_trough", "offset_from_first_station_cm")


class P02FloorError(RuntimeError):
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


def slab_rect(label, loc, yaw, ext_own):
    """Oriented rect from box_extents taken in the slab's OWN frame (origin loc, yaw)."""
    f = frame_of(loc[0], loc[1], 0.0, yaw)
    cx, cy = (ext_own["x"][0] + ext_own["x"][1]) / 2.0, (ext_own["y"][0] + ext_own["y"][1]) / 2.0
    wx, wy, _ = from_frame(f, cx, cy, 0.0)
    return {"label": label, "c": [wx, wy], "yaw": float(yaw),
            "half": [(ext_own["x"][1] - ext_own["x"][0]) / 2.0, (ext_own["y"][1] - ext_own["y"][0]) / 2.0]}


def in_rect(r, x, y):
    lx, ly, _ = to_frame(frame_of(r["c"][0], r["c"][1], 0.0, r["yaw"]), x, y, 0.0)
    return abs(lx) <= r["half"][0] and abs(ly) <= r["half"][1]


def rect_corners(r):
    f = frame_of(r["c"][0], r["c"][1], 0.0, r["yaw"])
    return [from_frame(f, u * r["half"][0], w * r["half"][1], 0.0)[:2] for u, w in ((1, 1), (1, -1), (-1, -1), (-1, 1))]


def hangar_hole(dock, rects):
    """The S2 pit the four slabs frame, in the dock frame (port of p02_straighten.py:172-188): x from the far edge of
    the slab holding the dock to the slab straddling y=0 beyond it; |y| to the nearer inner side edge. None when the
    slabs do not frame a hole around the dock."""
    spans = []
    for r in rects:
        cs = [to_frame(dock, x, y, 0.0) for x, y in rect_corners(r)]
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
    return {"x0": x0, "x1": min(s[1] for s in far), "half_y": min(min(-s[4] for s in left), min(s[3] for s in right)),
            "near": near[0][0]}


def in_hole(dock, hole, x, y):
    if hole is None:
        return False
    lx, ly, _ = to_frame(dock, x, y, 0.0)
    return hole["x0"] < lx < hole["x1"] and abs(ly) < hole["half_y"]


def classify(points, rects, dock, hole):
    """points [(source, x, y)] -> {"by_source": {src: {slab|PIT|GAP: n}}, "gaps": [(src, x, y)], "pit": n}."""
    by, gaps, pit = {}, [], 0
    for src, x, y in points:
        hit = next((r["label"] for r in rects if in_rect(r, x, y)), None)
        if hit is None:
            if in_hole(dock, hole, x, y):
                hit, pit = "PIT", pit + 1
            else:
                hit = "GAP"
                gaps.append((src, round(x, 1), round(y, 1)))
        d = by.setdefault(src, {})
        d[hit] = d.get(hit, 0) + 1
    return {"by_source": by, "gaps": gaps, "pit": pit}


def rects_overlap(a, b):
    """Separating-axis test for two oriented rects."""
    ca, cb = rect_corners(a), rect_corners(b)
    for r in (a, b):
        for ang in (r["yaw"], r["yaw"] + 90.0):
            ax = (math.cos(math.radians(ang)), math.sin(math.radians(ang)))
            pa = [p[0] * ax[0] + p[1] * ax[1] for p in ca]
            pb = [p[0] * ax[0] + p[1] * ax[1] for p in cb]
            if max(pa) <= min(pb) or max(pb) <= min(pa):
                return False
    return True


def hole_rect(dock, hole):
    cx, cy, _ = from_frame(dock, (hole["x0"] + hole["x1"]) / 2.0, 0.0, 0.0)
    return {"label": "S2 pit", "c": [cx, cy], "yaw": dock["yaw"], "half": [(hole["x1"] - hole["x0"]) / 2.0, hole["half_y"]]}


def propose_fits(rects, gaps, dock, hole):
    """REPORT ONLY (never applied by this tool): grow the slab nearest each gap (in its own frame, never shrinking)
    to contain it; flags a growth that would cover the pit. -> {label: {c, yaw, half, covers_pit}}."""
    by = {}
    for src, x, y in gaps:
        best = min(rects, key=lambda r: math.hypot(r["c"][0] - x, r["c"][1] - y) - max(r["half"]))
        by.setdefault(best["label"], []).append((x, y))
    out = {}
    for label, pts in by.items():
        r = next(q for q in rects if q["label"] == label)
        f = frame_of(r["c"][0], r["c"][1], 0.0, r["yaw"])
        lo, hi = [-r["half"][0], -r["half"][1]], [r["half"][0], r["half"][1]]
        for x, y in pts:
            lx, ly, _ = to_frame(f, x, y, 0.0)
            lo, hi = [min(lo[0], lx), min(lo[1], ly)], [max(hi[0], lx), max(hi[1], ly)]
        cx, cy, _ = from_frame(f, (lo[0] + hi[0]) / 2.0, (lo[1] + hi[1]) / 2.0, 0.0)
        new = {"label": label, "c": [cx, cy], "yaw": r["yaw"], "half": [(hi[0] - lo[0]) / 2.0, (hi[1] - lo[1]) / 2.0]}
        new["covers_pit"] = bool(hole is not None and rects_overlap(new, hole_rect(dock, hole)))
        new["points"] = len(pts)
        out[label] = new
    return out


def route_checks(samples):
    """samples [(x, y, z, pitch, roll)] -> (z0, problems). A curved route is EXPECTED here (P02 is not straightened)."""
    if len(samples) < 2:
        return None, ["route: fewer than 2 samples"]
    z0 = samples[0][2]
    p = []
    dz = max(abs(s[2] - z0) for s in samples)
    if dz > ROUTE_Z_TOL:
        p.append("route not level: z varies %.2f cm" % dz)
    if max(max(abs(s[3]), abs(s[4])) for s in samples) > 0.05:
        p.append("route pitched/rolled")
    return z0, p


def layer_base(name):
    return re.sub(r"_\d+$", "", str(name))


def split_key(k):
    name, tags = k.split("|", 1)
    return name, (tags.split(",") if tags else [])


def vanishes(name, tags):
    """True for the layers Ground.bEnabled=False removes (cpp :510-512, :584, :1348, :1369)."""
    return any(t in GROUND_TAGS for t in tags) or layer_base(name) in PORTAL_BOARD_NAMES


def walking(key):
    return vanishes(*split_key(key)) and not any(n in key for n in NOT_WALKING)


def layer_key(name, tags):
    return layer_base(name) + "|" + ",".join(sorted(str(t) for t in tags))


def compare_layers(before, after):
    """{key: [entry]} entry {"count", "b": [x0,x1,y0,y1,z0,z1] or None}. Surviving layers identical (count AND
    instance-transform bounds), vanishing layers empty, nothing new. -> problems."""
    p = []
    for k, ents in before.items():
        got = after.get(k, [])
        if vanishes(*split_key(k)):
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
            elif (e0["b"] is None) != (e1["b"] is None):
                p.append("%s: bounds %s -> %s" % (k, _r(e0["b"]), _r(e1["b"])))
            elif e0["b"] is not None and any(abs(a - b) > LAYER_TOL for a, b in zip(e0["b"], e1["b"])):
                p.append("%s: bounds %s -> %s" % (k, _r(e0["b"]), _r(e1["b"])))
    for k in after:
        if k not in before and sum(e["count"] for e in after[k]):
            p.append("%s: new layer after materialize" % k)
    return p


def compare_restored(before, after):
    """REVERT: every recorded layer back with the same component count; surviving layers exact; vanishing (board)
    layers may differ in layout -> notes. -> (problems, notes)."""
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
                (notes if vanishes(*split_key(k)) and e1["count"] > 0 else p).append(
                    "%s: %s -> %s" % (k, (e0["count"], _r(e0["b"])), (e1["count"], _r(e1["b"]))))
    for k in after:
        if k not in before and sum(e["count"] for e in after[k]):
            p.append("%s: new layer after re-enable" % k)
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


def compare_slabs(before, after):
    """{label: {"xf", "overrides", "materials"}} -> problems (any slab moved/rescaled/re-materialled)."""
    p = []
    for k, s in before.items():
        a = after.get(k)
        if a is None:
            p.append("slab %s missing" % k)
            continue
        if not same_xf(s["xf"], a["xf"], SLAB_TOL):
            p.append("slab %s transform %s -> %s" % (k, s["xf"], a["xf"]))
        if strip_none(s["overrides"]) != strip_none(a["overrides"]) or s["materials"] != a["materials"]:
            p.append("slab %s materials %s -> %s" % (k, s["materials"], a["materials"]))
    return p


def poke_through(lay, slab_boxes, top):
    """Surviving layers whose instance-origin bounds cross the slab top inside a slab's footprint (frame AABBs).
    Origin bounds are coarse: a hit means 'look', not 'proven'. Report only."""
    out = []
    for k, ents in lay.items():
        if vanishes(*split_key(k)):
            continue
        for e in ents:
            b = e["b"]
            if not (b and e["count"]):
                continue
            for lab, r in slab_boxes.items():
                if b[4] < top < b[5] and b[0] < r["x"][1] and r["x"][0] < b[1] and b[2] < r["y"][1] and r["y"][0] < b[3]:
                    out.append({"layer": k, "slab": lab, "count": e["count"], "bounds": _r(b)})
    return out


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
        self.run = datetime.datetime.now().strftime("P02FLOOR-%Y%m%d-%H%M%S")
        self.record = os.path.join(self.here, "p02_floor_record.json")
        self.straighten_record = os.path.join(self.here, STRAIGHTEN_REC)
        self.hangar = os.path.join(self.repo, *HANGAR_REL)
        self.umap = os.path.join(self.repo, *UMAP_REL)
        self.past_backup = False

    def log(self, msg):
        self.u.log(msg)

    def fail(self, msg):
        tail = "|NOTHING SAVED; restart the editor with Don't Save" if self.past_backup else ""
        self.u.log_error("P02_FLOOR_FAILED|run=%s|mode=%s|%s%s" % (self.run, self.mode, msg, tail))
        raise P02FloorError("P02_FLOOR_FAILED|run=%s|%s" % (self.run, msg))


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
        if os.path.exists(c.straighten_record):
            c.fail("STRAIGHTEN_RECORD_ACTIVE|%s exists: p02_straighten owns Structure 02's Ground until it is reverted"
                   % STRAIGHTEN_REC)
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
        except Exception as exc:  # noqa: BLE001  report-only: a missing field never blocks
            out[n] = "unread: %s" % exc
    return out


def xf_of(a):
    loc, rot, sc = a.get_actor_location(), a.get_actor_rotation(), a.get_actor_scale3d()
    return {"loc": [loc.x, loc.y, loc.z], "rot": [rot.roll, rot.pitch, rot.yaw], "scale": [sc.x, sc.y, sc.z]}


def smc_of(a):
    return a.get_component_by_class(_u().StaticMeshComponent)


def slab_geom(a, f=None):
    """-> mesh, rpy, ext (in f, or in the slab's own frame when f is None), loc."""
    smc = smc_of(a)
    mesh = smc.get_editor_property("static_mesh")
    bb = mesh.get_bounding_box()
    wt = smc.get_world_transform()
    r = wt.rotation.rotator()
    loc = (wt.translation.x, wt.translation.y, wt.translation.z)
    if f is None:
        f = frame_of(loc[0], loc[1], 0.0, r.yaw)
    ext = box_extents(loc, (r.roll, r.pitch, r.yaw), (wt.scale3d.x, wt.scale3d.y, wt.scale3d.z),
                      (bb.min.x, bb.min.y, bb.min.z), (bb.max.x, bb.max.y, bb.max.z), f)
    return mesh, (r.roll, r.pitch, r.yaw), ext, loc


def materials(a):
    return [m.get_path_name() if m else None for m in smc_of(a).get_materials()]


def overrides(a):
    return [m.get_path_name() if m else None for m in smc_of(a).get_editor_property("override_materials")]


def slab_snap(a):
    return {"xf": xf_of(a), "overrides": overrides(a), "materials": materials(a)}


def inst_points(comp):
    """World instance origins, or None when the per-instance API is unavailable."""
    try:
        n = int(comp.get_instance_count())
        out = []
        for i in range(n):
            loc = comp.get_instance_transform(i, True).translation
            out.append((loc.x, loc.y, loc.z))
        return out
    except Exception:  # noqa: BLE001
        return None


def comp_bounds(u, comp, pts=None):
    """AABB of the INSTANCE ORIGINS (world), not the component's cached Bounds: MaterializeStructure re-creates the
    components and the cached Bounds read all-zero in the same Python call (6 Oct 01:47 P03 false
    LAYERS_OR_WINGS_CHANGED). Same as p03_floor.py:446-466. -> (centre, half-extent) or None."""
    if pts is None:
        pts = inst_points(comp)
    if pts is not None:
        if not pts:
            return None
        lo = tuple(min(p[i] for p in pts) for i in range(3))
        hi = tuple(max(p[i] for p in pts) for i in range(3))
        return tuple((a + b) / 2 for a, b in zip(lo, hi)), tuple((b - a) / 2 for a, b in zip(lo, hi))
    try:  # non-instanced primitives (wings): cached bounds (MaterializeStructure does not rebuild them)
        o, e, _ = u.SystemLibrary.get_component_bounds(comp)
        return (o.x, o.y, o.z), (e.x, e.y, e.z)
    except Exception:  # noqa: BLE001  unreadable -> compared by count only
        return None


def layers(u, s, f, want_points=False):
    """-> {key: [{"count", "b", "name"}]} (+ {key: [(x, y)] or None} instance origins when want_points)."""
    out, pts = {}, {}
    for comp in s.get_components_by_class(u.InstancedStaticMeshComponent):
        tags = [str(t) for t in comp.get_editor_property("component_tags")]
        k = layer_key(comp.get_name(), tags)
        ip = inst_points(comp)
        b = comp_bounds(u, comp, ip)
        n = int(comp.get_instance_count())
        out.setdefault(k, []).append(
            {"count": n, "b": None if (b is None or n == 0) else aabb_in_frame(b[0], b[1], f), "name": str(comp.get_name())})
        if want_points:
            if ip is None:
                pts[k] = None
            elif pts.get(k, []) is not None:
                pts.setdefault(k, []).extend((p[0], p[1]) for p in ip)
    return (out, pts) if want_points else out


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


def find_targets(c, actors):
    u = c.u
    st = [a for a in actors if str(a.get_actor_label()) == STRUCTURE and isinstance(a, u.InfinityStageStructureActor)]
    if len(st) != 1:
        c.fail("STRUCTURE_COUNT|%d" % len(st))
    named = {}
    for a in actors:
        named.setdefault(str(a.get_actor_label()), []).append(a)
    counts = {l: len(named.get(l, [])) for l in SLABS}
    if any(v != 1 for v in counts.values()):
        c.fail("LABEL_COUNTS|%s" % counts)
    s = st[0]
    passage = s.get_editor_property("passage")
    if passage is None or not str(passage.get_actor_label()).startswith(PASSAGE_PREFIX):
        c.fail("PASSAGE|%s" % (passage.get_actor_label() if passage else None))
    return s, passage, {l: named[l][0] for l in SLABS}


# ============================================================================ the plan (every mode)
def build_plan(c, actors):
    u = c.u
    problems = []
    s, passage, slabs = find_targets(c, actors)
    route = passage.get_editor_property("route")
    W = u.SplineCoordinateSpace.WORLD
    length = float(route.get_spline_length())
    n = max(2, int(length // ROUTE_STEP_CM))
    samples = []
    for i in range(n + 1):
        t = route.get_transform_at_distance_along_spline(length * i / n, W, False)
        r = t.rotation.rotator()
        samples.append((t.translation.x, t.translation.y, t.translation.z, r.pitch, r.roll))
    z0, rp = route_checks(samples)
    problems += rp
    g = s.get_editor_property("ground")
    gf = struct_fields(g, GROUND_FIELDS)
    pf = struct_fields(s.get_editor_property("portal"), PORTAL_FIELDS)
    fh = float(g.get_editor_property("floor_height_cm"))
    board_top = z0 + fh
    tgt_top = board_top + LIFT_CM
    # frame for every bounds comparison: the Near slab's (all four share its yaw today)
    _, rpy0, _, loc0 = slab_geom(slabs[FRAME_SLAB])
    f = frame_of(loc0[0], loc0[1], 0.0, rpy0[2])
    lay, pts = layers(u, s, f, want_points=True)
    # slabs: asserted as they are, never changed
    rects, boxes, srep = [], {}, {}
    for lab in SLABS:
        a = slabs[lab]
        mesh, rpy, own, loc = slab_geom(a)
        if own is None:
            c.fail("SLAB_PITCHED_OR_ROLLED|%s|%s" % (lab, rpy))
        _, _, inf, _ = slab_geom(a, f)
        rects.append(slab_rect(lab, loc, rpy[2], own))
        boxes[lab] = inf
        mats = materials(a)
        srep[lab] = dict(slab_snap(a), num_materials=int(smc_of(a).get_num_materials()), top=own["top"],
                         thick=own["thick"], rect=rects[-1])
        if _path(mesh) != CUBE:
            problems.append("%s mesh %s is not %s" % (lab, _path(mesh), CUBE))
        if abs(own["thick"] - THICK_CM) > THICK_TOL:
            problems.append("%s thickness %.3f not %.1f" % (lab, own["thick"], THICK_CM))
        if abs(own["top"] - tgt_top) > TOP_TOL:
            problems.append("%s top %.2f is not board top %.2f + %.1f: this tool does not move slabs"
                            % (lab, own["top"], board_top, LIFT_CM))
        if not mats or any(m != WALNUT for m in mats):
            problems.append("%s materials %s are not walnut (WALNUT-20261006-112225 state changed?): this tool does "
                            "not re-material slabs" % (lab, mats))
        if a.get_attached_actors():
            problems.append("%s carries attached actors" % lab)
    # the S2 pit (hangar dock from the hangar record)
    dock, hole = None, None
    try:
        dk = json.load(open(c.hangar, encoding="utf-8"))["dock"]
        dock = frame_of(dk["loc"][0], dk["loc"][1], 0.0, dk["yaw"])
        hole = hangar_hole(dock, rects)
    except Exception as exc:  # noqa: BLE001  no pit -> every uncovered point counts as a gap
        problems.append("hangar dock unreadable (%s): the S2 pit cannot be excluded" % exc)
    # coverage: route centreline + walking board instance origins; stage front / understage reported only
    walk_pts = [("route", x, y) for x, y, _, _, _ in samples]
    info_pts = []
    for k, p in pts.items():
        if not vanishes(*split_key(k)):
            continue
        if p is None:
            problems.append("%s: instance positions unreadable, coverage unproven" % k)
            continue
        (walk_pts if walking(k) else info_pts).extend((layer_base(split_key(k)[0]), x, y) for x, y in p)
    cov = classify(walk_pts, rects, dock, hole)
    cov_info = classify(info_pts, rects, dock, hole)
    fits = {}
    if cov["gaps"]:
        fits = propose_fits(rects, cov["gaps"], dock, hole)
        problems.append("COVERAGE_GAPS|%d walking-floor points outside every slab and the S2 pit (first %s); this "
                        "tool never moves slabs: proposed fits in the DRY report need review"
                        % (len(cov["gaps"]), cov["gaps"][:5]))
    removes = {k: {"components": len(v), "instances": sum(e["count"] for e in v)}
               for k, v in lay.items() if vanishes(*split_key(k))}
    rep = {"run": c.run, "mode": c.mode, "frame": f, "route_len": length, "route_samples": len(samples),
           "board_top": board_top, "target_top": tgt_top, "ground": gf, "portal": pf,
           "boards_on": bool(g.get_editor_property("enabled")), "removes": removes,
           "slabs": srep, "dock": dock, "pit": hole,
           "coverage": {"by_source": cov["by_source"], "pit": cov["pit"], "gaps": len(cov["gaps"]),
                        "gap_points": cov["gaps"][:GAP_LIST_MAX]},
           "coverage_info_not_gated": {"by_source": cov_info["by_source"], "gaps": len(cov_info["gaps"])},
           "proposed_fits_report_only": fits,
           "poke_through": poke_through(lay, boxes, tgt_top), "layers": lay,
           "wings": wing_bottoms(u, passage), "problems": problems}
    return rep, {"s": s, "slabs": slabs, "passage": passage, "f": f}


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
    if os.path.exists(c.straighten_record):
        live.append("STRAIGHTEN_RECORD_ACTIVE (%s)" % STRAIGHTEN_REC)
    if not rep["boards_on"]:
        live.append("boards already off: nothing to do")
    rep["live_blockers"] = live
    path = os.path.join(c.here, "p02_floor_dry_%s.json" % c.run)
    write_json(c, path, rep)
    c.log("P02_FLOOR_DRY_BOARDS|run=%s|boards_on=%s|ground=%s|portal=%s"
          % (c.run, rep["boards_on"], json.dumps(rep["ground"]), json.dumps(rep["portal"])))
    c.log("P02_FLOOR_DRY_REMOVES|run=%s|%s"
          % (c.run, json.dumps({k: (v["components"], v["instances"]) for k, v in rep["removes"].items()})))
    c.log("P02_FLOOR_DRY_SLABS|run=%s|board_top=%.2f|target_top=%.2f|%s"
          % (c.run, rep["board_top"], rep["target_top"],
             json.dumps({k: {"top": round(v["top"], 3), "materials": v["materials"]} for k, v in rep["slabs"].items()})))
    c.log("P02_FLOOR_DRY_COVERAGE|run=%s|route_len=%.1f|pit=%s|walking=%s|gaps=%d|info_not_gated=%s|fits=%s"
          % (c.run, rep["route_len"], json.dumps(rep["pit"]), json.dumps(rep["coverage"]["by_source"]),
             rep["coverage"]["gaps"], json.dumps(rep["coverage_info_not_gated"]),
             json.dumps({k: {"half": _r(v["half"]), "covers_pit": v["covers_pit"]} for k, v in rep["proposed_fits_report_only"].items()})))
    c.log("P02_FLOOR_DRY_POKE|run=%s|surviving layers crossing the slab top (coarse)=%s" % (c.run, json.dumps(rep["poke_through"])))
    ok = not (rep["problems"] or live)
    c.log("P02_FLOOR_DRY_%s|run=%s|apply_ready=%d|problems=%s|live_blockers=%s|mutated=0|report=%s"
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
    s, slabs, passage, f = h["s"], h["slabs"], h["passage"], h["f"]
    slabs_before = {l: {k: rep["slabs"][l][k] for k in ("xf", "overrides", "materials")} for l in SLABS}
    rec = {"run": c.run, "state": "applying", "written": datetime.datetime.now().isoformat(timespec="seconds"),
           "ground": rep["ground"], "slabs": slabs_before, "layers": rep["layers"], "wings": rep["wings"],
           "board_top": rep["board_top"], "coverage": rep["coverage"], "pit": rep["pit"]}
    write_json(c, c.record, rec, exclusive=True)
    backup = os.path.join(c.repo, "Backups", "PreP02Floor-%s" % c.run)
    os.makedirs(backup)
    c.past_backup = True
    shutil.copy2(c.umap, backup)
    shutil.copy2(c.record, backup)
    pre_sha = _sha(c.umap)
    if _sha(os.path.join(backup, UMAP_REL[-1])) != pre_sha:
        c.fail("BACKUP_MISMATCH")
    c.log("P02_FLOOR_BACKUP_OK|run=%s|%s" % (c.run, backup))
    # 1. boards off; every other Ground field (FloorHeightCm included) read back unchanged
    g = s.get_editor_property("ground")
    g.set_editor_property("enabled", False)
    s.modify()
    s.set_editor_property("ground", g)
    g2 = struct_fields(s.get_editor_property("ground"), GROUND_FIELDS)
    if g2.get("enabled") is not False or any(g2[k] != rep["ground"][k] for k in GROUND_FIELDS if k != "enabled"):
        c.fail("GROUND_READBACK|%s" % json.dumps(g2))
    # 2. materialize
    if not s.materialize_structure():
        c.fail("MATERIALIZE_FAILED")
    if not s.is_structure_current():
        c.fail("NOT_CURRENT")
    lp = compare_layers(rep["layers"], layers(u, s, f))
    wp = compare_wings(rep["wings"], wing_bottoms(u, passage))
    sp = compare_slabs(slabs_before, {l: slab_snap(a) for l, a in slabs.items()})
    if lp or wp or sp:
        c.fail("LAYERS_WINGS_OR_SLABS_CHANGED|%s" % (lp + wp + sp))
    # 3. save the level only
    d = census(u)
    if d["content"] or d["maps"] != [WORLD]:
        c.fail("DIRTY_SCOPE|%s" % json.dumps(d))
    if not u.EditorLoadingAndSavingUtils.save_map(world, WORLD):
        c.fail("SAVE_FAILED")
    if census(u) != {"content": [], "maps": []}:
        c.fail("POST_SAVE_DIRTY|%s" % json.dumps(census(u)))
    if _sha(c.umap) == pre_sha:
        c.fail("UMAP_UNCHANGED_ON_DISK")
    # 4. read back after save
    g3 = struct_fields(s.get_editor_property("ground"), GROUND_FIELDS)
    if g3.get("enabled") is not False or g3["floor_height_cm"] != rep["ground"]["floor_height_cm"]:
        c.fail("POST_SAVE_GROUND_READBACK|%s" % json.dumps(g3))
    sp2 = compare_slabs(slabs_before, {l: slab_snap(a) for l, a in slabs.items()})
    if sp2:
        c.fail("POST_SAVE_SLAB_READBACK|%s" % sp2)
    rec.update(state="applied", applied=datetime.datetime.now().isoformat(timespec="seconds"), backup=backup,
               after={"ground": g3})
    write_json(c, c.record, rec)
    c.log("P02_FLOOR_APPLY_OK|run=%s|boards_off=1|floor_height_kept=%s|slabs_unchanged=4|walnut=1|layers_ok=1|wings_ok=1"
          "|pit_points=%d|gaps=0|level_saved=1|dirty_after=0+0|backup=%s"
          % (c.run, rep["ground"]["floor_height_cm"], rep["coverage"]["pit"], backup))
    return rec


def phase_revert(c):
    u = c.u
    ed, world, actors = guards(c, need_clean=True)
    if not os.path.exists(c.record):
        c.fail("NO_RECORD")
    rec = json.load(open(c.record, encoding="utf-8"))
    if rec.get("state") != "applied":
        c.fail("RECORD_STATE|%s: an APPLY that did not save is undone by a Don't-Save restart, not REVERT" % rec.get("state"))
    s, passage, slabs = find_targets(c, actors)
    if s.get_editor_property("ground").get_editor_property("enabled"):
        c.fail("NOT_APPLIED_STATE|boards are on")
    sp = compare_slabs(rec["slabs"], {l: slab_snap(a) for l, a in slabs.items()})
    if sp:
        c.fail("NOT_APPLIED_STATE|%s" % sp)
    _, rpy0, _, loc0 = slab_geom(slabs[FRAME_SLAB])
    f = frame_of(loc0[0], loc0[1], 0.0, rpy0[2])
    backup = os.path.join(c.repo, "Backups", "PreP02FloorRevert-%s" % c.run)
    os.makedirs(backup)
    c.past_backup = True
    shutil.copy2(c.umap, backup)
    shutil.copy2(c.record, backup)
    pre_sha = _sha(c.umap)
    if _sha(os.path.join(backup, UMAP_REL[-1])) != pre_sha:
        c.fail("BACKUP_MISMATCH")
    g = s.get_editor_property("ground")
    g.set_editor_property("enabled", bool(rec["ground"]["enabled"]))
    s.modify()
    s.set_editor_property("ground", g)
    g2 = struct_fields(s.get_editor_property("ground"), GROUND_FIELDS)
    if g2 != rec["ground"]:
        c.fail("GROUND_READBACK|%s != %s" % (json.dumps(g2), json.dumps(rec["ground"])))
    if not s.materialize_structure():
        c.fail("MATERIALIZE_FAILED")
    if not s.is_structure_current():
        c.fail("NOT_CURRENT")
    lp, notes = compare_restored(rec["layers"], layers(u, s, f))
    wp = compare_wings(rec["wings"], wing_bottoms(u, passage))
    sp = compare_slabs(rec["slabs"], {l: slab_snap(a) for l, a in slabs.items()})
    if lp or wp or sp:
        c.fail("LAYERS_NOT_RESTORED|%s" % (lp + wp + sp))
    d = census(u)
    if d["content"] or d["maps"] != [WORLD]:
        c.fail("DIRTY_SCOPE|%s" % json.dumps(d))
    if not u.EditorLoadingAndSavingUtils.save_map(world, WORLD):
        c.fail("SAVE_FAILED")
    if census(u) != {"content": [], "maps": []}:
        c.fail("POST_SAVE_DIRTY|%s" % json.dumps(census(u)))
    if _sha(c.umap) == pre_sha:
        c.fail("UMAP_UNCHANGED_ON_DISK")
    if struct_fields(s.get_editor_property("ground"), GROUND_FIELDS) != rec["ground"]:
        c.fail("POST_SAVE_GROUND_READBACK")
    os.replace(c.record, c.record.replace(".json", ".reverted-%s.json" % c.run))
    c.log("P02_FLOOR_REVERT_OK|run=%s|boards_on=1|ground_exact=1|slabs_unchanged=4|board_layout_notes=%s|level_saved=1"
          "|dirty_after=0+0|backup=%s" % (c.run, notes, backup))
    return rec


def main(args=None):
    c = Ctx("DRY")
    if args is None:
        args = json.load(open(os.path.join(c.here, "p02_floor_args.json"), encoding="utf-8"))
    mode = str(args.get("mode", "DRY")).upper()
    c.mode = mode
    phases = {"DRY": phase_dry, "APPLY": phase_apply, "REVERT": phase_revert}
    if mode not in phases:
        c.fail("UNKNOWN_MODE|%s" % mode)
    if mode != "DRY" and args.get("confirm") != "%s P02FLOOR" % mode:
        c.fail("CONFIRM_MISSING|want '%s P02FLOOR'" % mode)
    c.log("P02_FLOOR_START|run=%s|mode=%s" % (c.run, mode))
    try:
        return phases[mode](c)
    except P02FloorError:
        raise
    except Exception as exc:  # noqa: BLE001  an API surprise still leaves a run-stamped failure marker
        c.fail("UNEXPECTED|%s: %s" % (type(exc).__name__, exc))


if __name__ == "__p02_floor_runner__":
    main()
