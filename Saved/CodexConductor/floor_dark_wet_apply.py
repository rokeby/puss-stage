"""Restore the dark glossy floor (Gary APPROVED, 5 Oct night; plan: Docs/Conductor/LOOK_DEPTH_PLAN_2026-10-05.md s2).

Supersedes Saved/CodexStructure/floors_above_boards_apply.py (never run: no revert record). That tool
targeted three slabs by OBJECT NAME (StaticMeshActor_0/_1/_7) at the 29 Sep pre-trim transforms, so
it would refuse on today's level (the slabs were trimmed lip->hinge on 30 Sep and P05's was renamed).
Kept from it: only-Z raise, record-before-mutation with fsync + read-back, level-only save, dirty/PIE/
bench refusals. New: exact LABEL targets, P03 (spawned 30 Sep), a new P04 slab, one shared MI.

WHAT IT DOES (APPLY)
  1. Raises four existing slabs so their top sits LIFT_CM above the structure boards' top:
       P01 "Passage 01 - Opening Floor"      P03 "Passage 03 - Floor"
       P05 "Passage 05 - Floor (oak)"        P06 "Passage 01 - Opening Floor2"
     Boards occupy [FloorHeightCm - BoardThicknessCm, FloorHeightCm] above the route line:
     InfinityStageStructureActor.h:130-131 ("Top of the boards relative to the route line", FloorHeightCm=0),
     :139-140 (BoardThicknessCm=5); InfinityStageStructureActor.cpp:722-725 (board centre at
     FloorHeightCm - Thickness*0.5, size Thickness) and :979-980 (forestage boards, same rule).
     So with route z 0 the boards fill z -5..0 and the slabs (top -5) sit flush under their bottom.
     Target top = route z + FloorHeightCm + LIFT_CM (= +0.5 today), both read LIVE per structure.
  2. Spawns one new 1 cm slab for P04 ("Passage 04 - Floor (dark wet)", tag RigAtmos.FloorDarkWet),
     a scaled /Engine/BasicShapes/Cube from P04's lip to its hangar hinge. The hinge is not on file:
     it is computed LIVE from the "S4 Hangar Root" (the hinge pivot, hangar_build.py:363-364), and must
     agree within 1 cm with the Entry Handoff Camera x + the S4 apron (hangar_s4_plan.json) and with
     P04's route end + apron (and the "S4 Hangar Apron" slab's far edge, if present).
  3. Creates ONE new asset MI_Floor_DarkWet (child of the walnut MI) and gives it to all five slabs.
     Never edits or deletes anything on an existing asset. Every parameter is gated on READ-BACK
     (UE 5.8 MaterialEditingLibrary setters can return False after a good set, or True after none).
  P02 is NOT touched (Gary: "Leave P02 for now"); its four slabs are recorded and checked unchanged.

MODES (global FLOOR_DW_MODE, set by the runners via runpy init_globals): DRY (default) | APPLY | REVERT
  DRY    every guard and number, writes floor_dark_wet_dry_<run>.json, mutates nothing.
  APPLY  guards -> originals JSON (fsync + read-back) -> Backups/PreFloorDarkWet-<run>/ (umap + JSON)
         -> MI (create, read back) -> slabs -> read-back -> dirty census (exactly the level + the new MI)
         -> save MI, save level -> dirty 0+0 -> record state "applied".
  REVERT restores each raised slab's recorded transform and material overrides, destroys ONLY the
         tagged P04 slab, keeps the MI, backs up first, saves the level only.
FLOOR_DW_ACK_BURIED: DRY lists actors standing on the OLD slab top (bottom within -6..-4 cm) inside a
slab's footprint, which the raise would bury; APPLY refuses unless this list equals that list exactly.

Never Save All; never reloads the level; no UE objects at module level (memory: MCP crashes).
Markers: FLOOR_DW_* with run=<id>. Failure marker FLOOR_DW_FAILED: after a failure past the backup,
do NOT save; restart the editor with Don't Save (memory: reimport/reload revert traps).
Planning functions are Unreal-free for test_floor_dark_wet_apply.py.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
import shutil
import sys

WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP_REL = ("Content", "InfinityStage", "Dev", "Maps", "L_InfinityStage_V1VerticalSlice.umap")
CUBE = "/Engine/BasicShapes/Cube"
PARENT = "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_02/Materials/M_Walnut_Hrrngbn_02_Mat_Inst_Dup"
MI_DIR, MI_NAME = "/Game/InfinityStage/RigAtmos", "MI_Floor_DarkWet"
MI_PATH = f"{MI_DIR}/{MI_NAME}"
MI_REL = ("Content", "InfinityStage", "RigAtmos", "MI_Floor_DarkWet.uasset")
TAG = "RigAtmos.FloorDarkWet"
P04_LABEL = "Passage 04 - Floor (dark wet)"
HANGAR_PLAN_REL = ("Saved", "CodexStructure", "hangar_s4_plan.json")

# Existing slabs. x/y = the slab's TRUE-corner extent in its passage's route-start frame (yaw only),
# from the last write records:
#   P01 plane_trim_record.json (30 Sep 07:27): x -150 .. hinge 29284.01, y +-10000.
#   P03 s3_pit_deck_record.json floor_after (1 Oct 12:30, S3_PIT_DECK_DONE 123004): loc x 5635.99,
#       scale x 115.72 -> x -150 .. 11421.97 (the S3 hinge). NOTE the plan's table (45,144) predates
#       this cut and is stale; y 159290 +- 26780 -> -27490 .. 26070.
#   P05 mouth_floor_p05_record.json (30 Sep 17:36): x -150 .. 47090.90, y -9690.02 .. 10309.98.
#   P06 mouth_floor_p06_record.json (30 Sep 17:36): x -150 .. 28140.28, y -10514.21 .. 9485.79.
SLABS = {
    "P01": {"label": "Passage 01 - Opening Floor", "structure": "Infinity Stage - Structure 01",
            "x": (-150.0, 29284.01), "y": (-10000.0, 10000.0)},
    "P03": {"label": "Passage 03 - Floor", "structure": "Infinity Stage - Structure 03",
            "x": (-150.0, 11421.97), "y": (-27490.0, 26070.0)},
    "P05": {"label": "Passage 05 - Floor (oak)", "structure": "Infinity Stage - Structure 05",
            "x": (-150.0, 47090.90), "y": (-9690.02, 10309.98)},
    "P06": {"label": "Passage 01 - Opening Floor2", "structure": "Infinity Stage - Structure 06",
            "x": (-150.0, 28140.28), "y": (-10514.21, 9485.79)},
}
P02_LABELS = ("Passage 02 - Floor Near", "Passage 02 - Floor Left", "Passage 02 - Floor Right", "Passage 02 - Floor Far")
P04 = {"structure": "Infinity Stage - Structure 04", "root": "S4 Hangar Root", "apron_actor": "S4 Hangar Apron",
       "camera": "Scene 4 — External Sound — Entry Handoff Camera", "half_width_cm": 10000.0}

OLD_TOP_CM, OLD_TOP_TOL = -5.0, 0.5
THICK_CM, THICK_TOL = 1.0, 0.05
EXTENT_TOL = 1.0
LIFT_CM = 0.5                 # slab top this far above the boards' top
RAISE_RANGE = (0.5, 10.0)     # sanity: target_top - old_top must fall in here
HINGE_TOL = 1.0
ROUTE_Z_TOL, ROUTE_Y_TOL = 0.5, 1.0
READBACK_TOL = 0.02
BURY_BAND = (-6.0, -4.0)      # actor bottoms standing on the OLD slab top

# MI_Floor_DarkWet. Names are binary-proven in M_Flooring_Mat.uasset / the walnut MI (strings); their
# wiring is NOT (inferred). Values: the look bench's floor_wet (LOOK_DEPTH_PLAN s6 :199).
MI_SCALARS = {"Roughness_Low": 0.02, "Roughness_High": 0.06, "Roughness_Add_Grunge": 0.6}
DARKEN = 0.35                 # multiplies the parent's wood colour vectors (rgb); alpha kept
DARKEN_VECTORS = ("Color_Wood_01", "Color_Wood_02", "Color_Wood_03", "Color_Wood_04")
MI_SWITCHES = {"Grunge ON": True, "Global Grunge ON": True}   # set only where they exist as static switches
MEL_API = ("get_scalar_parameter_names", "get_vector_parameter_names", "get_static_switch_parameter_names",
           "get_material_instance_scalar_parameter_value", "get_material_instance_vector_parameter_value",
           "get_material_instance_static_switch_parameter_value", "set_material_instance_scalar_parameter_value",
           "set_material_instance_vector_parameter_value", "set_material_instance_static_switch_parameter_value",
           "set_material_instance_parent", "update_material_instance")


class FloorError(RuntimeError):
    pass


# ============================================================================ pure planning (no unreal)
def frame_of(ox, oy, oz, yaw_deg):
    return {"o": (float(ox), float(oy), float(oz)), "yaw": float(yaw_deg)}


def to_frame(f, x, y, z):
    c, s = math.cos(math.radians(f["yaw"])), math.sin(math.radians(f["yaw"]))
    dx, dy, dz = x - f["o"][0], y - f["o"][1], z - f["o"][2]
    return (c * dx + s * dy, -s * dx + c * dy, dz)


def from_frame(f, x, y, z):
    c, s = math.cos(math.radians(f["yaw"])), math.sin(math.radians(f["yaw"]))
    return (f["o"][0] + c * x - s * y, f["o"][1] + s * x + c * y, f["o"][2] + z)


def yaw_diff(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


def box_extents(loc, rpy, scale, bbmin, bbmax, f):
    """True corners of a yaw-only box (mesh bounds x transform), x/y in frame f, z in WORLD.
    Returns None when the box is pitched or rolled (the raise math assumes a flat slab)."""
    roll, pitch, yaw = rpy
    if abs(roll) > 0.01 or abs(pitch) > 0.01:
        return None
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    xs, ys, zs = [], [], []
    for bx in (bbmin[0], bbmax[0]):
        for by in (bbmin[1], bbmax[1]):
            for bz in (bbmin[2], bbmax[2]):
                lx, ly, lz = bx * scale[0], by * scale[1], bz * scale[2]
                wx, wy, wz = loc[0] + c * lx - s * ly, loc[1] + s * lx + c * ly, loc[2] + lz
                fx, fy, _ = to_frame(f, wx, wy, wz)
                xs.append(fx)
                ys.append(fy)
                zs.append(wz)
    return {"x": (min(xs), max(xs)), "y": (min(ys), max(ys)), "top": max(zs), "bottom": min(zs),
            "thick": max(zs) - min(zs)}


def check_slab(key, spec, row):
    """row: count, is_cube, attached, children, rpy, frame_yaw, ext. Returns problems (empty = ok)."""
    p = []
    if row["count"] != 1:
        return [f"{key}: label '{spec['label']}' matches {row['count']} actors (need exactly 1)"]
    if not row["is_cube"]:
        p.append(f"{key}: mesh is not {CUBE}")
    if row["attached"]:
        p.append(f"{key}: attached to {row['attached']}")
    if row["children"]:
        p.append(f"{key}: carries attached actors {row['children'][:4]} (a raise would carry them)")
    e = row["ext"]
    if e is None:
        return p + [f"{key}: pitched/rolled {row['rpy']}"]
    if yaw_diff(row["rpy"][2], row["frame_yaw"]) > 0.01:
        p.append(f"{key}: yaw {row['rpy'][2]:.3f} vs route {row['frame_yaw']:.3f}")
    if abs(e["top"] - OLD_TOP_CM) > OLD_TOP_TOL:
        p.append(f"{key}: top {e['top']:.2f} not {OLD_TOP_CM}+-{OLD_TOP_TOL}")
    if abs(e["thick"] - THICK_CM) > THICK_TOL:
        p.append(f"{key}: thickness {e['thick']:.3f} not {THICK_CM}")
    for ax in ("x", "y"):
        for i in (0, 1):
            if abs(e[ax][i] - spec[ax][i]) > EXTENT_TOL:
                p.append(f"{key}: {ax}{'min' if i == 0 else 'max'} {e[ax][i]:.2f} vs expected {spec[ax][i]:.2f}")
    return p


def board_top(route_samples, floor_height_cm):
    """route_samples: [(fx, fy, z, pitch, roll)] along the route. -> (board_top_world_z, problems)."""
    if not route_samples:
        return None, ["no route samples"]
    z0 = route_samples[0][2]
    p = []
    dz = max(abs(s[2] - z0) for s in route_samples)
    if dz > ROUTE_Z_TOL:
        p.append(f"route not level: z varies {dz:.2f} cm")
    if max(max(abs(s[3]), abs(s[4])) for s in route_samples) > 0.05:
        p.append("route pitched/rolled")
    return z0 + floor_height_cm, p


def target_top(board_top_z):
    return board_top_z + LIFT_CM


def raise_z(loc_z, cur_top, tgt_top):
    return loc_z + (tgt_top - cur_top)


def hinge_agreement(cands, tol=HINGE_TOL):
    """cands: {name: x or None}; 'root' is authoritative (memory: compose against the LIVE root)."""
    if cands.get("root") is None:
        return None, ["S4 hinge: no live hangar root"]
    h = cands["root"]
    p = [f"S4 hinge: {k} {v:.2f} disagrees with root {h:.2f}" for k, v in cands.items()
         if v is not None and k != "root" and abs(v - h) > tol]
    if sum(1 for k, v in cands.items() if v is not None and k != "root") < 2:
        p.append("S4 hinge: fewer than two independent sources to confirm the root")
    return h, p


def plan_p04(f, lip, hinge, tgt_top, half_w):
    p = []
    if not hinge > lip + 1000.0:
        p.append(f"P04: hinge {hinge:.1f} not beyond lip {lip:.1f} + 10 m")
    cx = (lip + hinge) / 2.0
    wx, wy, _ = from_frame(f, cx, 0.0, 0.0)
    return {"loc": [wx, wy, tgt_top - THICK_CM / 2.0], "yaw": f["yaw"],
            "scale": [(hinge - lip) / 100.0, 2.0 * half_w / 100.0, THICK_CM / 100.0],
            "x": (lip, hinge), "y": (-half_w, half_w), "top": tgt_top}, p


def overlaps(a, b, inset=1.0):
    return a[0] + inset < b[1] and b[0] + inset < a[1]


def buried(rows, footprints, band=BURY_BAND):
    """rows: [(label, bottom, {key: (x0,x1,y0,y1) in that key's frame})]; footprints {key: (x, y)}."""
    out = []
    for label, bottom, fr in rows:
        if not (band[0] <= bottom <= band[1]):
            continue
        for k, (fx, fy) in footprints.items():
            r = fr.get(k)
            if r and overlaps((r[0], r[1]), fx) and overlaps((r[2], r[3]), fy):
                out.append(label)
                break
    return sorted(set(out))


def mi_plan(scalar_names, vector_names, switch_names, parent_vectors, parent_switches):
    p = [f"MI: parent lacks scalar '{n}'" for n in MI_SCALARS if n not in scalar_names]
    vecs = {}
    for n in DARKEN_VECTORS:
        if n in vector_names and n in parent_vectors:
            r, g, b, a = parent_vectors[n]
            vecs[n] = [r * DARKEN, g * DARKEN, b * DARKEN, a]
    if not vecs:
        p.append(f"MI: no wood colour vector to darken among {list(DARKEN_VECTORS)}")
    sw = {n: v for n, v in MI_SWITCHES.items() if n in switch_names}
    return {"scalars": dict(MI_SCALARS), "vectors": vecs, "switches": sw,
            "parent_switches": {n: parent_switches.get(n) for n in sw}}, p


def mi_mismatch(want, got):
    bad = []
    for n, v in want["scalars"].items():
        if got["scalars"].get(n) is None or abs(got["scalars"][n] - v) > 1e-4:
            bad.append(f"{n}={got['scalars'].get(n)} want {v}")
    for n, v in want["vectors"].items():
        g = got["vectors"].get(n)
        if g is None or any(abs(a - b) > 1e-4 for a, b in zip(g, v)):
            bad.append(f"{n}={g} want {v}")
    for n, v in want["switches"].items():
        if got["switches"].get(n) is not v:
            bad.append(f"{n}={got['switches'].get(n)} want {v}")
    if got.get("parent") != PARENT:
        bad.append(f"parent={got.get('parent')}")
    return bad


def dirty_problems(content, maps, allowed_content):
    p = []
    if sorted(content) != sorted(allowed_content):
        p.append(f"content dirty {sorted(content)} != allowed {sorted(allowed_content)}")
    if sorted(maps) != [WORLD]:
        p.append(f"map dirty {sorted(maps)} != [{WORLD}]")
    return p


def same_xf(a, b, tol=1e-3):
    return all(abs(x - y) <= tol for k in ("loc", "rot", "scale") for x, y in zip(a[k], b[k]))


def strip_none(lst):
    lst = list(lst)
    while lst and lst[-1] is None:
        lst.pop()
    return lst


# ============================================================================ editor adapters
def _u():
    import unreal  # noqa: PLC0415  (the harness injects a fake into sys.modules)
    return unreal


def _pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s.split(".")[0]


def _path(o):
    return None if o is None else o.get_path_name().split(".")[0]


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Ctx:
    def __init__(self, mode, ack):
        u = _u()
        self.u, self.mode, self.ack = u, mode, sorted(ack or [])
        self.repo = os.path.normpath(u.Paths.convert_relative_path_to_full(u.Paths.project_dir()))
        self.here = os.path.join(self.repo, "Saved", "CodexConductor")
        self.run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.record = os.path.join(self.here, "floor_dark_wet_record.json")
        self.catfloor_ok = True

    def log(self, msg):
        self.u.log(msg)

    def fail(self, msg):
        tail = "|NOT saved: do not save; restart the editor with Don't Save" if self.mode != "DRY" else ""
        self.u.log_error(f"FLOOR_DW_FAILED|run={self.run}|mode={self.mode}|{msg}{tail}")
        raise FloorError(f"FLOOR_DW_FAILED|run={self.run}|{msg}")

    def write_json(self, path, payload):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=1)
            fh.flush()
            os.fsync(fh.fileno())
        if json.load(open(path, encoding="utf-8")) != json.loads(json.dumps(payload)):
            self.fail(f"{os.path.basename(path)} did not read back")
        return path


def dirty(u):
    return (sorted(_pk(p) for p in u.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            sorted(_pk(p) for p in u.EditorLoadingAndSavingUtils.get_dirty_map_packages()))


def world_guards(c):
    u = c.u
    ed = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        c.fail("PIE active")
    world = ed.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != WORLD:
        c.fail(f"wrong world {world.get_path_name() if world else None}")
    return world


def blockers_live(c, actors):
    """What APPLY/REVERT refuse on besides the plan: dirty editor, Sequencer, bench actors, missing API."""
    u = c.u
    b = []
    d = dirty(u)
    if d != ([], []):
        b.append(f"editor dirty {d}")
    if u.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
        b.append("Sequencer is open")
    bench = [a.get_actor_label() for a in actors if a.get_actor_label().startswith(("ZZ_", "TEMP", "Temp"))]
    if bench:
        b.append(f"bench actors {bench[:6]}")
    missing = [n for n in MEL_API if not hasattr(u.MaterialEditingLibrary, n)]
    if missing:
        b.append(f"MaterialEditingLibrary lacks {missing}")
    return b


def all_actors(u, world):
    # GameplayStatics also lists transient bench actors (memory: puss-benches-are-level-activity)
    return list(u.GameplayStatics.get_all_actors_of_class(world, u.Actor))


def route_frame(c, s):
    u = c.u
    route = s.get_editor_property("passage").get_editor_property("route")
    length = float(route.get_spline_length())
    t0 = route.get_transform_at_distance_along_spline(0.0, u.SplineCoordinateSpace.WORLD, False)
    r0 = t0.rotation.rotator()
    f = frame_of(t0.translation.x, t0.translation.y, t0.translation.z, r0.yaw)
    samples = []
    n = max(2, int(length // 500.0) + 1)
    for i in range(n + 1):
        d = length * i / n
        t = route.get_transform_at_distance_along_spline(d, u.SplineCoordinateSpace.WORLD, False)
        r = t.rotation.rotator()
        fx, fy, _ = to_frame(f, t.translation.x, t.translation.y, t.translation.z)
        samples.append((fx, fy, t.translation.z, r.pitch, r.roll))
    return f, length, samples


def structure_facts(c, s):
    f, length, samples = route_frame(c, s)
    g = s.get_editor_property("ground")
    fh = float(g.get_editor_property("floor_height_cm"))
    bt = float(g.get_editor_property("board_thickness_cm"))
    top, probs = board_top(samples, fh)
    lip = -float(s.get_editor_property("portal").get_editor_property("forestage_depth_cm"))
    return {"frame": f, "route_len": length, "route_end_x": samples[-1][0], "route_max_dy": max(abs(x[1]) for x in samples),
            "floor_height_cm": fh, "board_thickness_cm": bt, "ground_on": bool(g.get_editor_property("enabled")),
            "board_top": top, "board_bottom": None if top is None else top - bt, "lip": lip, "problems": probs}


def xf_of(a):
    loc, rot, sc = a.get_actor_location(), a.get_actor_rotation(), a.get_actor_scale3d()
    return {"loc": [loc.x, loc.y, loc.z], "rot": [rot.roll, rot.pitch, rot.yaw], "scale": [sc.x, sc.y, sc.z]}


def overrides_of(a):
    return [_path(m) for m in a.static_mesh_component.get_editor_property("override_materials")]


def slab_geom(a, f):
    smc = a.static_mesh_component
    mesh = smc.get_editor_property("static_mesh")
    bb = mesh.get_bounding_box()
    wt = smc.get_world_transform()
    r = wt.rotation.rotator()
    ext = box_extents((wt.translation.x, wt.translation.y, wt.translation.z), (r.roll, r.pitch, r.yaw),
                      (wt.scale3d.x, wt.scale3d.y, wt.scale3d.z),
                      (bb.min.x, bb.min.y, bb.min.z), (bb.max.x, bb.max.y, bb.max.z), f)
    return mesh, (r.roll, r.pitch, r.yaw), ext


def aabb_in_frame(a, f):
    o, e = a.get_actor_bounds(False)
    pts = [to_frame(f, o.x + sx * e.x, o.y + sy * e.y, 0.0) for sx in (-1, 1) for sy in (-1, 1)]
    return (min(p[0] for p in pts), max(p[0] for p in pts), min(p[1] for p in pts), max(p[1] for p in pts)), o.z - e.z, e


def read_mi(c, mi, want=None):
    mel = c.u.MaterialEditingLibrary
    want = want or c.plan["mi"]
    got = {"parent": _path(mi.get_editor_property("parent")), "scalars": {}, "vectors": {}, "switches": {}}
    for n in want["scalars"]:
        got["scalars"][n] = float(mel.get_material_instance_scalar_parameter_value(mi, n))
    for n in want["vectors"]:
        v = mel.get_material_instance_vector_parameter_value(mi, n)
        got["vectors"][n] = [v.r, v.g, v.b, v.a]
    for n in want["switches"]:
        got["switches"][n] = bool(mel.get_material_instance_static_switch_parameter_value(mi, n))
    return got


# ============================================================================ the plan (shared by every mode)
def build_plan(c, world):
    u = c.u
    actors = all_actors(u, world)
    by_label = {}
    for a in actors:
        by_label.setdefault(a.get_actor_label(), []).append(a)
    problems, plan = [], {"run": c.run, "mode": c.mode, "slabs": {}, "p02": {}, "p04": None, "mi": None,
                          "structures": {}, "strips_left_at_old_top": [], "buried": [], "catfloor": {}}
    structures = {}
    for key, spec in list(SLABS.items()) + [("P04", {"structure": P04["structure"]})]:
        ss = [a for a in by_label.get(spec["structure"], []) if isinstance(a, u.InfinityStageStructureActor)]
        if len(ss) != 1:
            problems.append(f"{key}: structure '{spec['structure']}' x{len(ss)}")
            continue
        facts = structure_facts(c, ss[0])
        structures[key] = facts
        problems += [f"{key}: {p}" for p in facts["problems"]]
        plan["structures"][key] = {k: v for k, v in facts.items() if k != "problems"}
    actors_found = {}
    for key, spec in SLABS.items():
        hits = [a for a in by_label.get(spec["label"], []) if isinstance(a, u.StaticMeshActor)]
        others = len(by_label.get(spec["label"], [])) - len(hits)
        if key not in structures:
            continue
        f = structures[key]["frame"]
        row = {"count": len(hits) + others, "is_cube": False, "attached": None, "children": [], "rpy": None,
               "frame_yaw": f["yaw"], "ext": None}
        if len(hits) == 1 and not others:
            a = hits[0]
            mesh, rpy, ext = slab_geom(a, f)
            row.update(is_cube=_path(mesh) == CUBE, rpy=rpy, ext=ext,
                       attached=(a.get_attach_parent_actor().get_actor_label() if a.get_attach_parent_actor() else None),
                       children=[x.get_actor_label() for x in a.get_attached_actors()])
            actors_found[key] = a
        sp = check_slab(key, spec, row)
        problems += sp
        tgt = None if structures[key]["board_top"] is None else target_top(structures[key]["board_top"])
        entry = {"label": spec["label"], "check": sp or "ok", "target_top": tgt}
        if key in actors_found and row["ext"] is not None and tgt is not None:
            a = actors_found[key]
            entry.update(xf=xf_of(a), overrides=overrides_of(a), top=row["ext"]["top"],
                         x=list(row["ext"]["x"]), y=list(row["ext"]["y"]),
                         new_loc_z=raise_z(a.get_actor_location().z, row["ext"]["top"], tgt),
                         num_materials=int(a.static_mesh_component.get_num_materials()),
                         mobility=str(a.static_mesh_component.get_editor_property("mobility")),
                         folder=str(a.get_folder_path()))
            rise = tgt - row["ext"]["top"]
            if not (RAISE_RANGE[0] <= rise <= RAISE_RANGE[1]):
                problems.append(f"{key}: raise {rise:.2f} cm outside {RAISE_RANGE}")
            entry["raise_cm"] = rise
            try:
                entry["catfloor"] = str(a.static_mesh_component.get_collision_response_to_channel(
                    u.CollisionChannel.ECC_GAME_TRACE_CHANNEL1))
            except Exception as exc:  # report-only; APPLY then copies the collision profile alone
                entry["catfloor"] = f"unread: {exc}"
                c.catfloor_ok = False
        plan["slabs"][key] = entry
    # P02: recorded, never touched
    for lab in P02_LABELS:
        hits = by_label.get(lab, [])
        if len(hits) == 1:
            plan["p02"][lab] = {"xf": xf_of(hits[0]), "overrides": overrides_of(hits[0])}
        elif len(hits) > 1:
            problems.append(f"P02: '{lab}' x{len(hits)}")
    # P04
    if "P04" in structures:
        s4 = structures["P04"]
        f = s4["frame"]
        cands = {"root": None, "camera+apron": None, "route_end+apron": None, "apron_slab_far_edge": None}
        apron = None
        hp = os.path.join(c.repo, *HANGAR_PLAN_REL)
        if os.path.exists(hp):
            try:
                apron = float(json.load(open(hp, encoding="utf-8"))["hangar"]["apron"])
            except Exception as exc:
                problems.append(f"P04: hangar_s4_plan.json unreadable: {exc}")
        else:
            problems.append("P04: hangar_s4_plan.json missing")
        roots = by_label.get(P04["root"], [])
        if len(roots) == 1:
            rl = roots[0].get_actor_location()
            cands["root"] = to_frame(f, rl.x, rl.y, rl.z)[0]
            ryaw = roots[0].get_actor_rotation().yaw
            if yaw_diff(ryaw, f["yaw"]) > 0.1:
                problems.append(f"P04: hangar root yaw {ryaw:.2f} vs route {f['yaw']:.2f}")
        else:
            problems.append(f"P04: '{P04['root']}' x{len(roots)}")
        cams = by_label.get(P04["camera"], [])
        if len(cams) == 1 and apron is not None:
            cl = cams[0].get_actor_location()
            cands["camera+apron"] = to_frame(f, cl.x, cl.y, cl.z)[0] + apron
        if apron is not None:
            cands["route_end+apron"] = s4["route_end_x"] + apron
        aps = by_label.get(P04["apron_actor"], [])
        if len(aps) == 1:
            cands["apron_slab_far_edge"] = aabb_in_frame(aps[0], f)[0][1]
        hinge, hp_probs = hinge_agreement(cands)
        problems += hp_probs
        if s4["route_max_dy"] > ROUTE_Y_TOL:
            problems.append(f"P04: route not straight ({s4['route_max_dy']:.2f} cm off its start line)")
        existing = [a.get_actor_label() for a in actors if TAG in [str(t) for t in a.get_editor_property("tags")]]
        existing += [l for l in by_label if l == P04_LABEL and l not in existing]
        if hinge is not None and s4["board_top"] is not None:
            p4, pp = plan_p04(f, s4["lip"], hinge, target_top(s4["board_top"]), P04["half_width_cm"])
            problems += pp
            plan["p04"] = {"label": P04_LABEL, "hinge_sources": cands, "apron": apron, **p4, "existing": existing}
        if existing:
            problems.append(f"P04: slab already exists {existing} (REVERT first)")
    # pit strips etc. that share a slab's label prefix: reported, left where they are
    for key, spec in SLABS.items():
        for lab, hits in by_label.items():
            if lab.startswith(spec["label"] + " - ") and key in structures:
                for a in hits:
                    if isinstance(a, u.StaticMeshActor):
                        _, _, ext = slab_geom(a, structures[key]["frame"])
                        plan["strips_left_at_old_top"].append({"label": lab, "top": None if ext is None else round(ext["top"], 2)})
    # MI
    mel = u.MaterialEditingLibrary
    parent = u.load_asset(PARENT)
    if parent is None:
        problems.append(f"MI: parent {PARENT} does not load")
    elif all(hasattr(mel, n) for n in MEL_API):
        sn = [str(n) for n in mel.get_scalar_parameter_names(parent)]
        vn = [str(n) for n in mel.get_vector_parameter_names(parent)]
        wn = [str(n) for n in mel.get_static_switch_parameter_names(parent)]
        pv = {}
        for n in DARKEN_VECTORS:
            if n in vn:
                v = mel.get_material_instance_vector_parameter_value(parent, n)
                pv[n] = [v.r, v.g, v.b, v.a]
        ps = {n: bool(mel.get_material_instance_static_switch_parameter_value(parent, n)) for n in MI_SWITCHES if n in wn}
        mp, mprobs = mi_plan(sn, vn, wn, pv, ps)
        problems += mprobs
        if u.EditorAssetLibrary.does_asset_exist(MI_PATH):
            mi0 = u.load_asset(MI_PATH)
            diff = mi_mismatch(mp, read_mi(c, mi0, mp)) if mi0 is not None else ["does not load"]
            if diff:
                problems.append(f"MI: {MI_PATH} already exists and differs from the plan: {diff}")
        mp.update(parent_scalars={n: float(mel.get_material_instance_scalar_parameter_value(parent, n)) for n in MI_SCALARS if n in sn},
                  parent_vectors=pv, scalar_names=sn, vector_names=vn, switch_names=wn,
                  exists=bool(u.EditorAssetLibrary.does_asset_exist(MI_PATH)))
        plan["mi"] = mp
    # buried: actors standing on the OLD slab top inside a new footprint
    fps = {k: (tuple(v["x"]), tuple(v["y"])) for k, v in plan["slabs"].items() if "x" in v}
    if plan["p04"]:
        fps["P04"] = (tuple(plan["p04"]["x"]), tuple(plan["p04"]["y"]))
    skip_labels = {s["label"] for s in SLABS.values()} | {P04_LABEL} | set(P02_LABELS)
    skip_classes = tuple(getattr(u, n) for n in ("InfinityStageStructureActor", "InfinityStagePassageActor",
                                                 "PostProcessVolume", "CameraActor") if hasattr(u, n))
    rows = []
    for a in actors:
        lab = a.get_actor_label()
        if lab in skip_labels or any(lab.startswith(s["label"] + " - ") for s in SLABS.values()) or isinstance(a, skip_classes):
            continue
        bottom, e = None, None
        per = {}
        for k in fps:
            fk = structures["P04" if k == "P04" else k]["frame"]
            fr, bottom, e = aabb_in_frame(a, fk)
            per[k] = fr
        if e is None or (e.x ** 2 + e.y ** 2 + e.z ** 2) ** 0.5 < 1.0 or max(e.x, e.y) > 2.0e5:
            continue
        rows.append((lab, bottom, per))
    plan["buried"] = buried(rows, fps)
    if plan["buried"] and plan["buried"] != c.ack:
        problems.append(f"would bury {len(plan['buried'])} actors standing on the old slab top "
                        f"(ack with FLOOR_DW_ACK_BURIED = exactly this list): {plan['buried'][:12]}")
    plan["problems"] = problems
    c.plan = plan
    return actors, actors_found, structures, problems


# ============================================================================ phases
def phase_dry(c):
    u = c.u
    world = world_guards(c)
    before = dirty(u)
    actors, _, _, problems = build_plan(c, world)
    live = blockers_live(c, actors)
    if os.path.exists(c.record):
        live.append(f"record exists ({os.path.basename(c.record)}): applied and not reverted")
    if dirty(u) != before:
        c.fail(f"DRY dirtied {before} -> {dirty(u)}")
    report = dict(c.plan, live_blockers=live)
    p = c.write_json(os.path.join(c.here, f"floor_dark_wet_dry_{c.run}.json"), report)
    for k, v in c.plan["slabs"].items():
        c.log(f"FLOOR_DW_DRY_SLAB|run={c.run}|{k}|{v['label']}|check={v['check']}|top={v.get('top')}"
              f"|target_top={v.get('target_top')}|raise_cm={v.get('raise_cm')}|x={v.get('x')}|y={v.get('y')}"
              f"|materials={v.get('overrides')}|catfloor={v.get('catfloor')}")
    for k, s in c.plan["structures"].items():
        c.log(f"FLOOR_DW_DRY_BOARDS|run={c.run}|{k}|floor_height={s['floor_height_cm']}|board_thickness={s['board_thickness_cm']}"
              f"|board_top={s['board_top']}|board_bottom={s['board_bottom']}|lip={s['lip']}|route_end_x={s['route_end_x']:.2f}"
              f"|ground_on={s['ground_on']}")
    if c.plan["p04"]:
        q = c.plan["p04"]
        c.log(f"FLOOR_DW_DRY_P04|run={c.run}|hinge_sources={q['hinge_sources']}|x={q['x']}|y={q['y']}|loc={q['loc']}"
              f"|scale={q['scale']}|top={q['top']}|existing={q['existing']}")
    if c.plan["mi"]:
        m = c.plan["mi"]
        c.log(f"FLOOR_DW_DRY_MI|run={c.run}|exists={m['exists']}|scalars={m['scalars']}|parent_scalars={m['parent_scalars']}"
              f"|vectors={m['vectors']}|parent_vectors={m['parent_vectors']}|switches={m['switches']}"
              f"|parent_switches={m['parent_switches']}")
    c.log(f"FLOOR_DW_DRY_STRIPS|run={c.run}|left_at_old_top={c.plan['strips_left_at_old_top']}")
    c.log(f"FLOOR_DW_DRY_P02|run={c.run}|recorded={sorted(c.plan['p02'])}|untouched=1")
    c.log(f"FLOOR_DW_DRY_BURIED|run={c.run}|n={len(c.plan['buried'])}|{c.plan['buried']}")
    verdict = "FLOOR_DW_DRY_OK" if not (problems or live) else "FLOOR_DW_DRY_REFUSED"
    c.log(f"{verdict}|run={c.run}|apply_ready={int(not (problems or live))}|problems={problems}|live_blockers={live}"
          f"|mutated=0|report={p}")
    if problems or live:
        raise FloorError(f"{verdict}|run={c.run}|{problems + live}")
    return report


def _restore_stale_record(c, found):
    """A record left in state 'applying' means an APPLY failed before saving. If the live slabs equal its
    originals (the editor was restarted with Don't Save), archive it; otherwise refuse."""
    rec = json.load(open(c.record, encoding="utf-8"))
    if rec.get("state") != "applying":
        c.fail(f"record exists in state {rec.get('state')}: REVERT first")
    for key, o in rec["slabs"].items():
        a = found.get(key)
        if a is None or not same_xf(xf_of(a), o["xf"]) or strip_none(overrides_of(a)) != strip_none(o["overrides"]):
            c.fail(f"stale 'applying' record and {key} does not match its originals: restart with Don't Save first")
    os.replace(c.record, c.record.replace(".json", f".stale-{c.run}.json"))
    c.log(f"FLOOR_DW_STALE_RECORD_ARCHIVED|run={c.run}")


def phase_apply(c):
    u = c.u
    world = world_guards(c)
    actors, found, structures, problems = build_plan(c, world)
    live = blockers_live(c, actors)
    if problems or live:
        c.fail(f"refused: {problems + live}")
    if os.path.exists(c.record):
        _restore_stale_record(c, found)
    plan = c.plan
    # 1. originals, before anything changes
    rec = {"run": c.run, "state": "applying", "written": datetime.datetime.now().isoformat(timespec="seconds"),
           "slabs": {k: {"label": v["label"], "xf": v["xf"], "overrides": v["overrides"], "top": v["top"],
                         "target_top": v["target_top"], "new_loc_z": v["new_loc_z"]} for k, v in plan["slabs"].items()},
           "p02": plan["p02"], "p04": plan["p04"], "mi": {"path": MI_PATH, "existed": plan["mi"]["exists"],
                                                          "want": {k: plan["mi"][k] for k in ("scalars", "vectors", "switches")}},
           "board_reasoning": {k: {"floor_height_cm": s["floor_height_cm"], "board_thickness_cm": s["board_thickness_cm"],
                                   "board_top": s["board_top"]} for k, s in plan["structures"].items()}}
    c.write_json(c.record, rec)
    orig = c.write_json(os.path.join(c.here, f"floor_dark_wet_originals_{c.run}.json"), rec)
    c.log(f"FLOOR_DW_ORIGINALS_OK|run={c.run}|slabs={len(rec['slabs'])}|p02={len(rec['p02'])}|path={orig}")
    # 2. backup
    umap = os.path.join(c.repo, *UMAP_REL)
    backup = os.path.join(c.repo, "Backups", f"PreFloorDarkWet-{c.run}")
    os.makedirs(backup, exist_ok=True)
    shutil.copy2(umap, backup)
    shutil.copy2(orig, backup)
    pre_sha = _sha(umap)
    if _sha(os.path.join(backup, UMAP_REL[-1])) != pre_sha:
        c.fail("umap backup does not match the source")
    c.log(f"FLOOR_DW_BACKUP_OK|run={c.run}|{backup}")
    # 3. the material (before the level is touched, so a material failure leaves the level clean)
    mel, eal = u.MaterialEditingLibrary, u.EditorAssetLibrary
    want = plan["mi"]
    if want["exists"]:
        mi = u.load_asset(MI_PATH)
        bad = mi_mismatch(want, read_mi(c, mi)) if mi is not None else ["does not load"]
        if bad:
            c.fail(f"{MI_PATH} exists but differs: {bad} (never edits an existing asset)")
        created = False
    else:
        mi = u.AssetToolsHelpers.get_asset_tools().create_asset(MI_NAME, MI_DIR, u.MaterialInstanceConstant,
                                                                u.MaterialInstanceConstantFactoryNew())
        if mi is None:
            c.fail("create_asset returned None")
        mel.set_material_instance_parent(mi, u.load_asset(PARENT))
        for n, v in want["scalars"].items():
            mel.set_material_instance_scalar_parameter_value(mi, n, v)       # return value ignored: read back below
        for n, v in want["vectors"].items():
            mel.set_material_instance_vector_parameter_value(mi, n, u.LinearColor(*v))
        for n, v in want["switches"].items():
            mel.set_material_instance_static_switch_parameter_value(mi, n, v)
        mel.update_material_instance(mi)
        bad = mi_mismatch(want, read_mi(c, mi))
        if bad:
            c.fail(f"MI read-back: {bad}")
        created = True
    c.log(f"FLOOR_DW_MI_OK|run={c.run}|created={int(created)}|{MI_PATH}")
    # 4. the slabs
    for key, a in found.items():
        v = plan["slabs"][key]
        loc = a.get_actor_location()
        a.modify()
        a.set_actor_location(u.Vector(loc.x, loc.y, v["new_loc_z"]), False, False)
        smc = a.static_mesh_component
        for i in range(v["num_materials"]):
            smc.set_material(i, mi)
    q = plan["p04"]
    sub = u.get_editor_subsystem(u.EditorActorSubsystem)
    ref = found["P01"]
    p4 = sub.spawn_actor_from_class(u.StaticMeshActor, u.Vector(*q["loc"]), u.Rotator(roll=0.0, pitch=0.0, yaw=q["yaw"]))
    if p4 is None:
        c.fail("P04 spawn returned None")
    p4.set_actor_label(P04_LABEL)
    p4.set_editor_property("tags", [u.Name(TAG)])
    smc4 = p4.static_mesh_component
    smc4.set_mobility(ref.static_mesh_component.get_editor_property("mobility"))
    smc4.set_static_mesh(u.load_asset(CUBE))
    smc4.set_material(0, mi)
    smc4.set_collision_profile_name(ref.static_mesh_component.get_collision_profile_name())
    if c.catfloor_ok:
        smc4.set_collision_response_to_channel(u.CollisionChannel.ECC_GAME_TRACE_CHANNEL1,
                                               ref.static_mesh_component.get_collision_response_to_channel(
                                                   u.CollisionChannel.ECC_GAME_TRACE_CHANNEL1))
    p4.set_actor_scale3d(u.Vector(*q["scale"]))
    p4.set_folder_path(ref.get_folder_path())
    # 5. read back, before saving
    bad = []
    for key, a in found.items():
        v = plan["slabs"][key]
        _, _, ext = slab_geom(a, structures[key]["frame"])
        if ext is None or abs(ext["top"] - v["target_top"]) > READBACK_TOL:
            bad.append(f"{key} top {None if ext is None else round(ext['top'], 3)} want {v['target_top']}")
        elif any(abs(ext[ax][i] - v[ax][i]) > 0.05 for ax in ("x", "y") for i in (0, 1)):
            bad.append(f"{key} moved laterally")
        if any(_path(a.static_mesh_component.get_material(i)) != MI_PATH for i in range(v["num_materials"])):
            bad.append(f"{key} material not {MI_PATH}")
    mesh4, _, ext4 = slab_geom(p4, structures["P04"]["frame"])
    if _path(mesh4) != CUBE or ext4 is None or abs(ext4["top"] - q["top"]) > READBACK_TOL or \
            any(abs(ext4[ax][i] - q[ax][i]) > 0.5 for ax in ("x", "y") for i in (0, 1)) or \
            abs(ext4["thick"] - THICK_CM) > THICK_TOL:
        bad.append(f"P04 slab read-back {ext4}")
    if ext4 is not None and ext4["x"][1] > q["hinge_sources"]["root"] + 0.5:
        bad.append("P04 slab crosses the hinge into the hangar")
    if _path(smc4.get_material(0)) != MI_PATH or p4.get_actor_label() != P04_LABEL or \
            TAG not in [str(t) for t in p4.get_editor_property("tags")]:
        bad.append("P04 slab material/label/tag")
    by_label = {}
    for a in all_actors(u, world):
        by_label.setdefault(a.get_actor_label(), []).append(a)
    for lab, o in rec["p02"].items():
        hits = by_label.get(lab, [])
        if len(hits) != 1 or not same_xf(xf_of(hits[0]), o["xf"], 1e-6) or overrides_of(hits[0]) != o["overrides"]:
            bad.append(f"P02 changed: {lab}")
    bad += [f"bench actor {l}" for l in by_label if l.startswith(("ZZ_", "TEMP", "Temp"))]
    if mi_mismatch(want, read_mi(c, mi)):
        bad.append("MI changed after assignment")
    content, maps = dirty(u)
    bad += dirty_problems(content, maps, [MI_PATH] if created else [])
    if bad:
        c.fail(f"read-back: {bad}")
    # 6. save exactly the MI (if new) and the level
    if created and not eal.save_asset(MI_PATH, only_if_is_dirty=False):
        c.fail("MI save failed")
    if not u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level():
        c.fail("level save failed")
    after = dirty(u)
    if after != ([], []):
        c.fail(f"dirty after save {after}")
    if created and not os.path.exists(os.path.join(c.repo, *MI_REL)):
        c.fail("MI .uasset not on disk after save")
    if _sha(umap) == pre_sha:
        c.fail("umap unchanged on disk after save")
    rec.update(state="applied", applied=datetime.datetime.now().isoformat(timespec="seconds"), mi_created=created,
               backup=backup)
    c.write_json(c.record, rec)
    c.log(f"FLOOR_DW_APPLY_OK|run={c.run}|raised={sorted(found)}|p04={P04_LABEL}|x=[{q['x'][0]:.1f},{q['x'][1]:.1f}]"
          f"|top={q['top']}|mi={MI_PATH}|mi_created={int(created)}|p02_untouched=1|saved=level+{'MI' if created else 'none'}"
          f"|dirty_after=0+0|backup={backup}")
    return rec


def phase_revert(c):
    u = c.u
    world = world_guards(c)
    actors = all_actors(u, world)
    live = blockers_live(c, actors)
    live = [b for b in live if not b.startswith("MaterialEditingLibrary")]
    if live:
        c.fail(f"refused: {live}")
    if not os.path.exists(c.record):
        c.fail("NOTHING TO REVERT: no floor_dark_wet_record.json")
    rec = json.load(open(c.record, encoding="utf-8"))
    if rec.get("state") != "applied":
        c.fail(f"record state {rec.get('state')}: an APPLY that did not save is undone by a Don't-Save restart, not REVERT")
    by_label = {}
    for a in actors:
        by_label.setdefault(a.get_actor_label(), []).append(a)
    targets, problems = {}, []
    for key, o in rec["slabs"].items():
        hits = by_label.get(o["label"], [])
        if len(hits) != 1:
            problems.append(f"{key}: '{o['label']}' x{len(hits)}")
            continue
        cur = xf_of(hits[0])
        want_applied = dict(o["xf"], loc=[o["xf"]["loc"][0], o["xf"]["loc"][1], o["new_loc_z"]])
        if not same_xf(cur, want_applied, 0.05):
            problems.append(f"{key}: not in the applied state ({cur} vs {want_applied})")
        if any(_path(hits[0].static_mesh_component.get_material(i)) != MI_PATH
               for i in range(hits[0].static_mesh_component.get_num_materials())):
            problems.append(f"{key}: material is no longer {MI_PATH}")
        targets[key] = hits[0]
    p4s = by_label.get(P04_LABEL, [])
    tagged = [a for a in actors if TAG in [str(t) for t in a.get_editor_property("tags")]]
    if len(p4s) != 1 or len(tagged) != 1 or p4s[0] is not tagged[0]:
        problems.append(f"P04 slab: {len(p4s)} labelled, {len(tagged)} tagged (need the same one actor)")
    if problems:
        c.fail(f"refused: {problems}")
    umap = os.path.join(c.repo, *UMAP_REL)
    backup = os.path.join(c.repo, "Backups", f"PreFloorDarkWetRevert-{c.run}")
    os.makedirs(backup, exist_ok=True)
    shutil.copy2(umap, backup)
    shutil.copy2(c.record, backup)
    if _sha(os.path.join(backup, UMAP_REL[-1])) != _sha(umap):
        c.fail("umap backup does not match the source")
    for key, a in targets.items():
        o = rec["slabs"][key]["xf"]
        a.modify()
        a.set_actor_location(u.Vector(*o["loc"]), False, False)
        a.set_actor_rotation(u.Rotator(roll=o["rot"][0], pitch=o["rot"][1], yaw=o["rot"][2]), False)
        a.set_actor_scale3d(u.Vector(*o["scale"]))
        smc = a.static_mesh_component
        orig = rec["slabs"][key]["overrides"]
        for i in range(max(len(orig), smc.get_num_materials())):
            pth = orig[i] if i < len(orig) else None
            smc.set_material(i, u.load_asset(pth) if pth else None)
    sub = u.get_editor_subsystem(u.EditorActorSubsystem)
    if not sub.destroy_actor(p4s[0]):
        c.fail("destroy of the P04 slab returned False")
    bad = []
    now = {}
    for a in all_actors(u, world):
        now.setdefault(a.get_actor_label(), []).append(a)
    for key, a in targets.items():
        o = rec["slabs"][key]
        if not same_xf(xf_of(a), o["xf"]):
            bad.append(f"{key} transform {xf_of(a)} != {o['xf']}")
        if strip_none(overrides_of(a)) != strip_none(o["overrides"]):
            bad.append(f"{key} overrides {overrides_of(a)} != {o['overrides']}")
    if now.get(P04_LABEL) or any(TAG in [str(t) for t in a.get_editor_property("tags")] for v in now.values() for a in v):
        bad.append("P04 slab still present")
    for lab, o in rec["p02"].items():
        hits = now.get(lab, [])
        if len(hits) != 1 or not same_xf(xf_of(hits[0]), o["xf"], 1e-6):
            bad.append(f"P02 changed: {lab}")
    if not u.EditorAssetLibrary.does_asset_exist(MI_PATH):
        bad.append("MI missing (REVERT keeps it)")
    content, maps = dirty(u)
    bad += dirty_problems(content, maps, [])
    if bad:
        c.fail(f"revert read-back: {bad}")
    if not u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level():
        c.fail("level save failed")
    if dirty(u) != ([], []):
        c.fail(f"dirty after save {dirty(u)}")
    os.replace(c.record, c.record.replace(".json", f".reverted-{c.run}.json"))
    c.log(f"FLOOR_DW_REVERT_OK|run={c.run}|restored={sorted(targets)}|p04_destroyed=1|mi_kept={MI_PATH}"
          f"|saved=level|dirty_after=0+0|backup={backup}")
    return rec


def main(mode="DRY", ack=None):
    mode = str(mode).upper()
    phases = {"DRY": phase_dry, "APPLY": phase_apply, "REVERT": phase_revert}
    c = Ctx(mode, ack)
    if mode not in phases:
        c.fail(f"unknown mode {mode}")
    c.log(f"FLOOR_DW_START|run={c.run}|mode={mode}|ack_buried={len(c.ack)}")
    try:
        return phases[mode](c)
    except FloorError:
        raise
    except Exception as exc:  # an API surprise mid-phase still leaves a run-stamped failure marker
        c.fail(f"unexpected {type(exc).__name__}: {exc}")


if "unreal" in sys.modules and not getattr(sys.modules["unreal"], "_FLOOR_DW_FAKE", False):
    main(globals().get("FLOOR_DW_MODE", "DRY"), globals().get("FLOOR_DW_ACK_BURIED"))
