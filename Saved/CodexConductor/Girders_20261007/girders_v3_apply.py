"""Girders v3, step 2 of 2: "v3 at double section" on the six Structures (written 7 Oct 2026, NOT RUN).

Gary, 7 Oct (own words): "v3 at double section" = the v3 meshes AND the doubled section settings on all six
Structures. He accepted that it re-hangs the TOP lamps.
  Gridiron:  beam_mesh SM_UP_PlateGirder -> SM_UP_PlateGirder_v3, beam_width_cm 40 -> 80, beam_depth_cm 90 -> 180
  Underpass: column_mesh SM_UP_LacedColumn -> _v3, knee_mesh SM_UP_KneeBracket -> _v3,
             column_width_cm 60 -> 120, column_depth_cm 40 -> 80
Materials, heights, outsets, knee size, deck, fence and tubes are NOT written.

WHERE THE SETTINGS LIVE (declaration-proven): FInfinityStageGridironSettings Gridiron and
FInfinityStageUnderpassSettings Underpass are UPROPERTYs of AInfinityStageStructureActor
(Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageStructureActor.h:976, :991), i.e. LEVEL data,
not Show data. So the narrow save is the LEVEL only (as underpass_rig_apply / underpass_phase_b_apply); the census
gate refuses if the Show (or anything but the level) is dirty, so the Show provably is not written.

Args girders_v3_apply_args.json (missing file = DRY):
  {"mode": "DRY"|"APPLY"|"REVERT", "confirm": "<MODE> GIRDERSV3",
   "structures": null (= all six) | [labels], "allow_board_drift": false,
   "expected_lines": null | {label: int}   (optional pin copied from the DRY's predicted window),
   "revert_record": "girders_v3_originals_<run>.json" (REVERT)}
DRY     read-only, all six rows: from-state check (v1 meshes, 40x90, 60x40), portal pins, live soft-pointer
        cross-check, line window, clearance hits, the 30 cm column/cross-girder gap before/after, column stretch,
        what else moves. Census must stay clean. Marker GIRDERSV3_DRY_OK (+ one GIRDERSV3_DRY_ROW per target).
APPLY   guards -> originals JSON (fsync, read back) -> Backups/PreGirdersV3-YYYYMMDD-HHMM umap copy (sha256) ->
        per Structure: modify(), write the 7 fields, READ BACK, MaterializeStructure, census (strict counts identical,
        hanging lines inside the predicted window), components render v3 + unchanged materials, MEASURED instance
        sections (gridiron 80x180, columns 120x80), portal still renders its pinned timber -> dirty scope == level
        only -> save level -> census clean -> read back after save. Any problem: originals restored IN MEMORY, NOT
        saved, status REFUSED_UNSAVED -> Don't-Save restart (never reload the open level from Python).
REVERT  restores the recorded 7 fields exactly, re-fits, requires every count == the recorded before, saves level.

Proof tiers (AGENTS.md), per claim:
* declaration-proven (InfinityStageStructureActor.h / .cpp at HEAD d574091):
  - field names: Gridiron BeamMesh/BeamWidthCm/BeamDepthCm h:83-105; Underpass ColumnWidthCm/ColumnDepthCm
    h:588-591, ColumnMesh h:616, KneeMesh h:634, ColumnOutsetCm h:579, DeckHeightCm h:583, PierHeightCm h:599.
  - hanging line top GridTop = HeightCm + 1.5 x BeamDepthCm (cpp:1843), line only if 1 <= drop <= MaxDropCm
    (cpp:1846): 90 -> 180 raises GridTop 135 cm.
  - cross girder spans GridHalfWidthCm*2 at HeightCm, section BeamWidth x BeamDepth (cpp:1105-1128); column line =
    GetFloorHalfSpanCm (== GridHalfWidthCm when > 0, cpp:1409-1411) + ColumnOutsetCm (cpp:1889); so the clear gap
    between a cross girder's end and the column's inner face = ColumnOutsetCm - ColumnWidthCm/2 = 60 - 30 = 30 cm,
    and 60 - 60 = 0 at 120 wide (the 30 cm gap Gary named).
  - deck half span = column line + ColumnWidthCm/2 (cpp:1899): the deck widens 30 cm per side; catwalk rails follow
    (cpp:2026). Knee centre = column line + (ColumnDepthCm + KneeSizeCm)/2 along the route (cpp:1982): knees move
    20 cm along the route; knee Y = the mesh's own (cpp:1985): 10 -> 20 cm.
  - fence and tube rows use the column LINE, not the width (cpp:2149, 943): they do not move; FenceInsetCm 75
    (h:874) still clears the 60 cm half-column by 15 cm.
  - portal carried-forward rails keep the GRIDIRON's section (cpp:1654-1677): they become 80 x 180 timber on any
    Structure whose portal extends the gridiron; portal lines' top is GridTop (cpp:1687) and rises 135 cm.
  - EndInsetCm = max(PierSizeCm, ColumnDepthCm)/2 (cpp:1902): 140 vs 80, unchanged.
  - every instance is FitMeshToTimber(bounds) (cpp:183-196): scale = size / mesh bounds, which the measured
    section check below inverts.
* measured (offline, 7 Oct): all six Structures carry Phase A (underpass_rig_applied_index.json: 3 APPLIED runs
  cover 01-06) and Phase B (underpass_phase_b_record_0[1-6].json, none reverted); the v1 girder/knee/column bounds
  100x40x90 / 120x10x120 / 500x60x40 (underpass_kit_import_last.json).
* inferred (the live DRY confirms each): every Structure is still at the Phase A/B from-state (DRY refuses
  otherwise); soft pointers resolve once the v1 assets are loaded (cross-checked against the live components);
  get_instance_transform(i, False) scale is component-local (a component with non-unit relative scale would fail
  the measured section check, loudly, not silently).
Every UE object lives inside a function (re-run crash rule); no helper imports (stale module cache rule).
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
WORLD_FILE = "Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
MESH = "/Game/InfinityStage/RigAtmos/Underpass/Meshes/"
LABELS = tuple(f"Infinity Stage - Structure {i:02d}" for i in range(1, 7))
ARGS_FILE = "girders_v3_apply_args.json"
IMPORT_RECORD = "girders_v3_import_last.json"
INDEX = "girders_v3_applied_index.json"

# (struct, field): (from, to). Mesh values are package paths.
PLAN = {
    ("gridiron", "beam_mesh"): (MESH + "SM_UP_PlateGirder", MESH + "SM_UP_PlateGirder_v3"),
    ("gridiron", "beam_width_cm"): (40.0, 80.0),
    ("gridiron", "beam_depth_cm"): (90.0, 180.0),
    ("underpass", "column_mesh"): (MESH + "SM_UP_LacedColumn", MESH + "SM_UP_LacedColumn_v3"),
    ("underpass", "knee_mesh"): (MESH + "SM_UP_KneeBracket", MESH + "SM_UP_KneeBracket_v3"),
    ("underpass", "column_width_cm"): (60.0, 120.0),
    ("underpass", "column_depth_cm"): (40.0, 80.0),
}
# read for the report / predictions, never written
CONTEXT = {
    "gridiron": ("material", "height_cm", "enabled", "section_variation", "twist_degrees", "cross_beam_every"),
    "underpass": ("enabled", "columns", "knees", "column_material", "knee_material", "column_outset_cm",
                  "deck_height_cm", "pier_height_cm", "pier_size_cm", "knee_size_cm"),
}
COUNTS = ("station_count", "cross_beam_count", "rail_segment_count", "board_count", "slot_count",
          "groove_piece_count", "cloth_count", "portal_piece_count", "fixture_body_count", "hanging_line_count",
          "underpass_column_count", "underpass_pier_count", "underpass_knee_count", "underpass_deck_count",
          "underpass_catwalk_count", "underpass_tube_count", "underpass_tube_light_count",
          "underpass_fence_panel_count", "underpass_fence_overlay_count")
STRICT = tuple(k for k in COUNTS if k not in ("board_count", "hanging_line_count"))
TAG = {"grid": "InfinityStage.Structure.Gridiron", "columns": "InfinityStage.Structure.Underpass.Columns",
       "knees": "InfinityStage.Structure.Underpass.Knees", "fixtures": "InfinityStage.Structure.Fixtures",
       "lines": "InfinityStage.Structure.Lines", "portal": "InfinityStage.Structure.Portal"}
SECTION_TOL_CM = 0.5
V3_COLUMN_LENGTH_CM = 1880.0  # build_manifest.json column_spec.L


class GirdersError(RuntimeError):
    pass


# ============================================================================ pure logic (harness-tested)
def target_values() -> dict:
    return {k: v[1] for k, v in PLAN.items()}


def from_values() -> dict:
    return {k: v[0] for k, v in PLAN.items()}


def key(k) -> str:
    return f"{k[0]}.{k[1]}"


def values_match(actual: dict, expected: dict) -> list:
    """actual/expected keyed by (struct, field). Floats to 1e-4, paths exact."""
    bad = []
    for k, e in expected.items():
        a = actual.get(k)
        if isinstance(e, float) or isinstance(a, float):
            if a is None or e is None or abs(float(a) - float(e)) > 1e-4:
                bad.append(f"{key(k)}: {a} != {e}")
        elif a != e:
            bad.append(f"{key(k)}: {a} != {e}")
    return bad


def from_state_problems(snap: dict) -> list:
    """The v3 swap is planned against the Phase A/B v1 state; anything else is refused, not overwritten."""
    probs = values_match(snap["fields"], from_values())
    ctx = snap["context"]
    if not ctx["gridiron.enabled"]:
        probs.append("gridiron disabled")
    if not ctx["underpass.enabled"]:
        probs.append("underpass disabled")
    if abs(float(ctx["gridiron.section_variation"])) > 1e-6:
        probs.append(f"section_variation {ctx['gridiron.section_variation']} != 0 (Phase A)")
    return probs


def line_window(old_lines: int, line_drops, housing_old_drops, max_drop: float, depth_old: float, depth_new: float):
    """Copied from ../underpass_rig_apply.py:168-179 (live-run 5 Oct). Hanging-line count after a depth change."""
    delta = 1.5 * (depth_new - depth_old)
    lost = sum(1 for d in line_drops if d + delta > max_drop or d + delta < 1.0)
    gains = sum(1 for d in housing_old_drops if not (1.0 <= d <= max_drop) and 1.0 <= d + delta <= max_drop)
    lo = old_lines - lost
    return lo, lo + gains, {"grid_top_shift_cm": delta, "lost": lost, "possible_gains": gains,
                            "lines_measured": len(line_drops), "lines_reported": old_lines}


def clearance(housings, depth_old, depth_new, body_h):
    """Copied from ../underpass_rig_apply.py:445-455. Housings the new girder band (crosses +-D/2 about cross_z,
    rails up to cross_z + 1.5 D) reaches that the old band did not: the TOP lamps that must be re-hung."""
    hits = []
    for hx, hy, hz, cz in housings:
        lo_h, hi_h = hz - body_h / 2, hz + body_h / 2
        old_lo, old_hi = cz - depth_old / 2, cz + 1.5 * depth_old
        new_lo, new_hi = cz - depth_new / 2, cz + 1.5 * depth_new
        if hi_h > new_lo and lo_h < new_hi and not (hi_h > old_lo and lo_h < old_hi):
            hits.append([round(hx), round(hy), round(hz)])
    return hits


def geometry_moves(ctx: dict, portal: dict, floor_height_cm: float) -> dict:
    """What else moves, from the formulas cited in the module docstring (cm)."""
    outset = float(ctx["underpass.column_outset_cm"])
    w0, w1 = PLAN[("underpass", "column_width_cm")]
    d0, d1 = PLAN[("underpass", "column_depth_cm")]
    b0, b1 = PLAN[("gridiron", "beam_depth_cm")]
    col_h = float(ctx["underpass.deck_height_cm"]) - floor_height_cm - float(ctx["underpass.pier_height_cm"])
    return {
        "cross_girder_to_column_gap_cm": [outset - w0 / 2, outset - w1 / 2],
        "grid_top_shift_cm": 1.5 * (b1 - b0),
        "cross_band_rel_cm": [[float(ctx["gridiron.height_cm"]) - b0 / 2, float(ctx["gridiron.height_cm"]) + 1.5 * b0],
                              [float(ctx["gridiron.height_cm"]) - b1 / 2, float(ctx["gridiron.height_cm"]) + 1.5 * b1]],
        "deck_half_span_grows_cm": (w1 - w0) / 2,
        "knee_shift_along_route_cm": (d1 - d0) / 2,
        "column_height_cm": col_h,
        "column_mesh_x_scale": [col_h / 500.0, col_h / V3_COLUMN_LENGTH_CM],
        "portal_carried_rails_section_cm": ([[40.0, b0], [80.0, b1]]
                                            if portal.get("enabled") and portal.get("extend_gridiron") else None),
    }


def census_problems(before: dict, after: dict, window, allow_board_drift: bool, pinned_lines=None):
    problems, findings = [], []
    for k in STRICT:
        if before.get(k) != after.get(k):
            problems.append(f"{k} {before.get(k)} -> {after.get(k)}")
    if before.get("board_count") != after.get("board_count"):
        msg = f"board_count {before.get('board_count')} -> {after.get('board_count')}"
        (findings if allow_board_drift else problems).append(msg)
    lo, hi = window
    lines = after.get("hanging_line_count")
    if lines is None or not (lo <= lines <= hi):
        problems.append(f"hanging_line_count {before.get('hanging_line_count')} -> {lines} outside predicted [{lo}, {hi}]")
    elif pinned_lines is not None and lines != pinned_lines:
        problems.append(f"hanging_line_count {lines} != pinned expected_lines {pinned_lines}")
    elif lines != before.get("hanging_line_count"):
        findings.append(f"hanging_line_count {before.get('hanging_line_count')} -> {lines} (inside [{lo}, {hi}])")
    if not after.get("current"):
        problems.append("IsStructureCurrent() false after the re-fit")
    return problems, findings


def section_problems(scales, mesh_size, want_y, want_z, what):
    """MEASURED: each instance's local scale x mesh bounds must equal the set section (FitMeshToTimber)."""
    if not scales:
        return [f"{what}: no instances"]
    worst = max(max(abs(sy * mesh_size[1] - want_y), abs(sz * mesh_size[2] - want_z)) for _, sy, sz in scales)
    return [f"{what}: section off by {worst:.2f} cm from {want_y} x {want_z}"] if worst > SECTION_TOL_CM else []


def load_args(path: str) -> dict:
    a = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {"mode": "DRY"}
    a["mode"] = str(a.get("mode", "DRY")).upper()
    if a["mode"] not in ("DRY", "APPLY", "REVERT"):
        raise GirdersError(f"unknown mode {a['mode']}")
    if a["mode"] != "DRY" and a.get("confirm") != f"{a['mode']} GIRDERSV3":
        raise GirdersError(f"confirm must be '{a['mode']} GIRDERSV3'")
    s = a.get("structures") or list(LABELS)
    bad = [x for x in s if x not in LABELS]
    if bad or len(set(s)) != len(s):
        raise GirdersError(f"structures must be distinct labels from {LABELS}: {s}")
    a["structures"] = s
    if a["mode"] == "REVERT" and not a.get("revert_record"):
        raise GirdersError("revert_record not set")
    return a


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ============================================================================ editor adapters
def _u():
    import unreal  # noqa: PLC0415  (the harness injects a fake)
    return unreal


def _pk(p) -> str:
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s.split(".")[0]


def _obj_path(o):
    return o.get_path_name().split(".")[0] if o is not None else None


def _plain(v):
    if isinstance(v, bool):
        return bool(v)
    if isinstance(v, int):
        return int(v)
    if isinstance(v, float):
        return float(v)
    return _obj_path(v)


class Ctx:
    def __init__(self):
        u = _u()
        self.u = u
        self.repo = os.path.normpath(u.Paths.convert_relative_path_to_full(u.Paths.project_dir()))
        self.run = "GV3A-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

    def log(self, m):
        self.u.log(m)

    def fail(self, m):
        self.u.log_error(f"GIRDERSV3_FAILED|run={self.run}|{m}")
        raise GirdersError(f"GIRDERSV3_FAILED|run={self.run}|{m}")

    def write_json(self, name, payload):
        p = os.path.join(HERE, name)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=1)
            fh.flush()
            os.fsync(fh.fileno())
        if json.load(open(p, encoding="utf-8")) != json.loads(json.dumps(payload)):
            self.fail(f"{name} did not read back")
        return p


def dirty(u):
    lib = u.EditorLoadingAndSavingUtils
    return (sorted(_pk(p) for p in lib.get_dirty_content_packages()),
            sorted(_pk(p) for p in lib.get_dirty_map_packages()))


def guards(c: Ctx):
    u = c.u
    ed = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        c.fail("PIE active")
    world = ed.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != WORLD:
        c.fail(f"wrong world {world.get_path_name() if world else None}")
    if dirty(u) != ([], []):
        c.fail(f"editor dirty at start {dirty(u)}")
    return world


def structures_by_label(c: Ctx, world):
    u = c.u
    actors = list(u.GameplayStatics.get_all_actors_of_class(world, u.Actor))
    bench = [a.get_actor_label() for a in actors if a.get_actor_label().startswith(("ZZ_", "TEMP", "Temp"))]
    if bench:
        c.fail(f"bench actors in the level: {bench}")
    found = {a.get_actor_label(): a for a in actors if isinstance(a, u.InfinityStageStructureActor)}
    if sorted(found) != sorted(LABELS):
        c.fail(f"structure actors {sorted(found)} != {list(LABELS)}")
    return found


def load_assets(c: Ctx, paths):
    """Loading the meshes first makes the soft pointers resolvable (a None read-back otherwise means unloaded)."""
    for p in paths:
        if c.u.EditorAssetLibrary.load_asset(p) is None:
            c.fail(f"{p} does not load")


def snapshot(s) -> dict:
    """Plain values only (never UE wrappers)."""
    structs = {n: s.get_editor_property(n) for n in ("gridiron", "underpass")}
    fields = {k: _plain(structs[k[0]].get_editor_property(k[1])) for k in PLAN}
    context = {f"{n}.{f}": _plain(structs[n].get_editor_property(f)) for n, fs in CONTEXT.items() for f in fs}
    return {"fields": fields, "context": context}


def fields_json(fields: dict) -> dict:
    return {key(k): v for k, v in fields.items()}


def fields_from_json(d: dict) -> dict:
    return {tuple(k.split(".", 1)): v for k, v in d.items()}


def counts(s) -> dict:
    out = {k: int(s.get_editor_property(k)) for k in COUNTS}
    out["current"] = bool(s.is_structure_current())
    out["grid_half_width_cm"] = float(s.get_editor_property("grid_half_width_cm"))
    return out


def comps(s, tag):
    return [x for x in s.get_editor_property("managed_components")
            if x and tag in [str(t) for t in x.get_editor_property("component_tags")]]


def render_state(s) -> dict:
    out = {}
    for part in ("grid", "columns", "knees"):
        cs = comps(s, TAG[part])
        out[part] = None if len(cs) != 1 else {
            "mesh": _obj_path(cs[0].get_editor_property("static_mesh")),
            "material": _obj_path(cs[0].get_material(0)), "instances": int(cs[0].get_instance_count())}
    return out


def soft_ptr_problems(snap, live) -> list:
    """A soft pointer can read None when unloaded: cross-check against what the components render."""
    f = snap["fields"]
    want = {"grid": f[("gridiron", "beam_mesh")], "columns": f[("underpass", "column_mesh")],
            "knees": f[("underpass", "knee_mesh")]}
    return [f"{p}: snapshot {w} != component {(live[p] or {}).get('mesh')}" for p, w in want.items()
            if live[p] is None or live[p]["mesh"] != w]


def portal_info(s) -> dict:
    p = s.get_editor_property("portal")
    out = {"enabled": bool(p.get_editor_property("enabled"))}
    try:
        out["extend_gridiron"] = bool(p.get_editor_property("extend_gridiron"))
    except Exception:  # noqa: BLE001
        out["extend_gridiron"] = None
    for k in ("portal_mesh", "portal_material"):
        try:
            out[k] = _obj_path(p.get_editor_property(k))
        except Exception:  # noqa: BLE001  (held patch not built)
            out[k] = "ABSENT"
    return out


def portal_live(s):
    for x in comps(s, TAG["portal"]):
        name = str(x.get_name())
        if name.startswith("StructurePortal") and not name.startswith("StructurePortalLines"):
            return {"mesh": _obj_path(x.get_editor_property("static_mesh")), "material": _obj_path(x.get_material(0))}
    return None


def portal_problem(portal, live):
    """An enabled portal must already be pinned (Phase A did this), else swapping BeamMesh turns it into v3 iron."""
    if not portal["enabled"]:
        return None
    if portal["portal_mesh"] in (None, "ABSENT"):
        return f"portal enabled but portal_mesh is {portal['portal_mesh']}: the girder swap would reach the portal"
    if live is None or live["mesh"] != portal["portal_mesh"]:
        return f"portal renders {live} but is pinned to {portal['portal_mesh']}"
    return None


def line_inputs(s, depth_old):
    """Copied from ../underpass_rig_apply.py:406-442: drops of existing lines; each housing's old drop."""
    fixtures = s.get_editor_property("fixtures")
    max_drop = float(fixtures.get_editor_property("max_drop_cm"))
    body_h = float(fixtures.get_editor_property("body_size_cm").z)
    drops = []
    for x in comps(s, TAG["lines"]):
        box = x.get_editor_property("static_mesh").get_bounding_box()
        size_x = float(box.max.x - box.min.x)
        for i in range(int(x.get_instance_count())):
            drops.append(float(x.get_instance_transform(i, True).scale3d.x) * size_x)
    grid_pts = []
    for x in comps(s, TAG["grid"]):
        for i in range(int(x.get_instance_count())):
            t = x.get_instance_transform(i, True).translation
            grid_pts.append((float(t.x), float(t.y), float(t.z)))
    housing_drops, housings = [], []
    for x in comps(s, TAG["fixtures"]):
        for i in range(int(x.get_instance_count())):
            t = x.get_instance_transform(i, True).translation
            hx, hy, hz = float(t.x), float(t.y), float(t.z)
            near = [p for p in grid_pts if (p[0] - hx) ** 2 + (p[1] - hy) ** 2 <= 600.0 ** 2]
            if not near:
                continue
            cz = min(p[2] for p in near)
            housing_drops.append(cz + 1.5 * depth_old - (hz + body_h * 0.5))
            housings.append((hx, hy, hz, cz))
    return {"max_drop": max_drop, "body_h": body_h, "line_drops": drops, "housing_drops": housing_drops,
            "housings": housings}


def instance_scales(s, tag):
    out = []
    for x in comps(s, tag):
        for i in range(int(x.get_instance_count())):
            sc = x.get_instance_transform(i, False).scale3d
            out.append((float(sc.x), float(sc.y), float(sc.z)))
    return out


def mesh_size(c: Ctx, path):
    b = c.u.EditorAssetLibrary.load_asset(path).get_bounding_box()
    return (float(b.max.x - b.min.x), float(b.max.y - b.min.y), float(b.max.z - b.min.z))


def write_fields(c: Ctx, s, values: dict):
    """values keyed by (struct, field); struct copy -> set -> write back -> READ BACK (setters can lie)."""
    u = c.u
    s.modify()
    for struct in ("gridiron", "underpass"):
        mine = {k[1]: v for k, v in values.items() if k[0] == struct}
        if not mine:
            continue
        st = s.get_editor_property(struct)
        for f, v in mine.items():
            if f.endswith("_mesh"):
                obj = u.EditorAssetLibrary.load_asset(v) if v else None
                if v and obj is None:
                    c.fail(f"{v} does not load")
                st.set_editor_property(f, obj)
            else:
                st.set_editor_property(f, float(v))
        s.set_editor_property(struct, st)
    bad = values_match(snapshot(s)["fields"], values)
    if bad:
        raise GirdersError(f"{s.get_actor_label()} read-back: {bad}")


def row_for(c: Ctx, s, label):
    snap = snapshot(s)
    live = render_state(s)
    portal = portal_info(s)
    floor = float(s.get_editor_property("ground").get_editor_property("floor_height_cm"))
    before = counts(s)
    depth_old = float(snap["fields"][("gridiron", "beam_depth_cm")])
    li = line_inputs(s, depth_old)
    lo, hi, detail = line_window(before["hanging_line_count"], li["line_drops"], li["housing_drops"],
                                 li["max_drop"], depth_old, PLAN[("gridiron", "beam_depth_cm")][1])
    return {"snapshot": {"fields": fields_json(snap["fields"]), "context": snap["context"]},
            "from_state_problems": from_state_problems(snap), "soft_ptr_problems": soft_ptr_problems(snap, live),
            "portal": portal, "portal_live": portal_live(s), "portal_problem": portal_problem(portal, portal_live(s)),
            "render_before": live, "before": before, "line_window": [lo, hi], "line_detail": detail,
            "clearance_hits_new_band": clearance(li["housings"], depth_old, PLAN[("gridiron", "beam_depth_cm")][1],
                                                 li["body_h"]),
            "moves": geometry_moves(snap["context"], portal, floor), "floor_height_cm": floor}


def refusals(row) -> list:
    return row["from_state_problems"] + row["soft_ptr_problems"] + ([row["portal_problem"]] if row["portal_problem"] else []) \
        + ([] if row["before"]["current"] else ["not current before the swap (re-fit it first, separately)"])


def import_ok(c: Ctx):
    p = os.path.join(HERE, IMPORT_RECORD)
    if not os.path.exists(p) or json.load(open(p, encoding="utf-8")).get("status") != "PASS":
        c.fail(f"no PASS {IMPORT_RECORD} (run girders_v3_import.py IMPORT for all three first)")
    for k, (_, to) in PLAN.items():
        if k[1].endswith("_mesh") and not c.u.EditorAssetLibrary.does_asset_exist(to):
            c.fail(f"{to} missing")


# ============================================================================ phases
def phase_dry(c: Ctx, args):
    u = c.u
    world = guards(c)
    found = structures_by_label(c, world)
    load_assets(c, [v[0] for k, v in PLAN.items() if k[1].endswith("_mesh")])
    v3_present = {v[1]: bool(u.EditorAssetLibrary.does_asset_exist(v[1])) for k, v in PLAN.items() if k[1].endswith("_mesh")}
    report = {"run": c.run, "mode": "DRY", "targets": args["structures"], "v3_assets": v3_present,
              "import_record_pass": os.path.exists(os.path.join(HERE, IMPORT_RECORD)) and
              json.load(open(os.path.join(HERE, IMPORT_RECORD), encoding="utf-8")).get("status") == "PASS",
              "would_set": fields_json(target_values()), "structures": {}, "mutated": 0}
    for label in LABELS:
        row = row_for(c, found[label], label)
        row["targeted"] = label in args["structures"]
        row["refusals"] = refusals(row)
        report["structures"][label] = row
    if dirty(u) != ([], []):
        c.fail(f"DRY dirtied {dirty(u)}")
    p = c.write_json(f"girders_v3_dry_{c.run}.json", report)
    refused = {t: report["structures"][t]["refusals"] for t in args["structures"] if report["structures"][t]["refusals"]}
    c.log(f"GIRDERSV3_DRY_OK|run={c.run}|targets={len(args['structures'])}|refused={sorted(refused)}"
          f"|v3_assets={all(v3_present.values())}|import_pass={report['import_record_pass']}|mutated=0|report={p}")
    for t in args["structures"]:
        r = report["structures"][t]
        c.log(f"GIRDERSV3_DRY_ROW|run={c.run}|{t}|refusals={r['refusals']}"
              f"|lines={r['before']['hanging_line_count']}->[{r['line_window'][0]},{r['line_window'][1]}]"
              f"|clearance_hits={len(r['clearance_hits_new_band'])}|gap={r['moves']['cross_girder_to_column_gap_cm']}"
              f"|col_scale_x={[round(x, 3) for x in r['moves']['column_mesh_x_scale']]}"
              f"|portal_rails={r['moves']['portal_carried_rails_section_cm']}")
    return report


def _check_after(c: Ctx, s, label, row, record, after):
    """Everything that must hold after the re-fit (no save yet). Returns problems, findings."""
    problems, findings = census_problems(row["before"], after, row["line_window"], bool(record["allow_board_drift"]),
                                         (record.get("expected_lines") or {}).get(label))
    live = render_state(s)
    tv = target_values()
    want_mesh = {"grid": tv[("gridiron", "beam_mesh")], "columns": tv[("underpass", "column_mesh")],
                 "knees": tv[("underpass", "knee_mesh")]}
    for part, mesh in want_mesh.items():
        b, a = row["render_before"][part], live[part]
        if a is None:
            problems.append(f"{part}: component missing after re-fit")
            continue
        if a["mesh"] != mesh:
            problems.append(f"{part}: renders {a['mesh']} != {mesh}")
        if b and a["material"] != b["material"]:
            problems.append(f"{part}: material {b['material']} -> {a['material']} (must not change)")
    problems += section_problems(instance_scales(s, TAG["grid"]), mesh_size(c, tv[("gridiron", "beam_mesh")]),
                                 tv[("gridiron", "beam_width_cm")], tv[("gridiron", "beam_depth_cm")], "gridiron")
    problems += section_problems(instance_scales(s, TAG["columns"]), mesh_size(c, tv[("underpass", "column_mesh")]),
                                 tv[("underpass", "column_width_cm")], tv[("underpass", "column_depth_cm")], "columns")
    if row["portal"]["enabled"]:
        pl = portal_live(s)
        if pl != row["portal_live"]:
            problems.append(f"portal renders {pl} after the swap != before {row['portal_live']}")
    return problems, findings


def phase_apply(c: Ctx, args):
    u = c.u
    world = guards(c)
    found = structures_by_label(c, world)
    import_ok(c)
    load_assets(c, [v[i] for k, v in PLAN.items() if k[1].endswith("_mesh") for i in (0, 1)])
    targets = args["structures"]
    record = {"run": c.run, "status": "ORIGINALS_WRITTEN", "world": WORLD, "gary": "7 Oct: 'v3 at double section'",
              "plan": fields_json(target_values()), "allow_board_drift": bool(args.get("allow_board_drift")),
              "expected_lines": args.get("expected_lines"), "structures": {}}
    for label in targets:
        row = row_for(c, found[label], label)
        why = refusals(row)
        if why:
            c.fail(f"{label}: {why}")
        record["structures"][label] = row
    # 1) originals BEFORE anything changes
    orig = f"girders_v3_originals_{c.run}.json"
    c.write_json(orig, record)
    c.log(f"GIRDERSV3_ORIGINALS_OK|run={c.run}|structures={targets}|path={os.path.join(HERE, orig)}")
    # 2) level snapshot BEFORE anything changes (clean level: disk == memory)
    bdir = os.path.join(c.repo, "Backups", "PreGirdersV3-" + datetime.datetime.now().strftime("%Y%m%d-%H%M"))
    src, dst = os.path.join(c.repo, WORLD_FILE), os.path.join(bdir, WORLD_FILE)
    os.makedirs(os.path.dirname(dst), exist_ok=False)
    shutil.copy2(src, dst)
    if sha256_file(src) != sha256_file(dst):
        c.fail("level backup sha256 mismatch")
    record["backup"] = os.path.relpath(dst, c.repo).replace("\\", "/")
    c.write_json(orig, record)
    # 3) mutate, re-fit, check
    problems, findings, after_all = [], [], {}
    try:
        for label in targets:
            s = found[label]
            write_fields(c, s, target_values())
            if not s.materialize_structure():
                problems.append(f"{label}: MaterializeStructure returned false")
                continue
            after = counts(s)
            after_all[label] = after
            p, f = _check_after(c, s, label, record["structures"][label], record, after)
            problems += [f"{label}: {x}" for x in p]
            findings += [f"{label}: {x}" for x in f]
        con, maps = dirty(u)
        if con or maps != [WORLD]:
            problems.append(f"dirty scope content={con} maps={maps} (only the level may be dirty)")
    except Exception as exc:  # noqa: BLE001  (restore before failing)
        problems.append(f"exception {exc}")
    if problems:
        for label in targets:  # originals back IN MEMORY; level stays dirty and UNSAVED
            try:
                write_fields(c, found[label], fields_from_json(record["structures"][label]["snapshot"]["fields"]))
                found[label].materialize_structure()
            except Exception:  # noqa: BLE001
                pass
        record["status"] = "REFUSED_UNSAVED"
        record["problems"] = problems
        c.write_json(orig, record)
        c.fail(f"NOT saved; originals restored in memory; Don't-Save restart required: {problems}")
    if not u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level():
        c.fail("level save failed (level dirty: Don't-Save restart)")
    if dirty(u) != ([], []):
        c.fail(f"dirty after save {dirty(u)}")
    # 4) read back after save
    again = structures_by_label(c, u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world())
    for label in targets:
        bad = values_match(snapshot(again[label])["fields"], target_values())
        if bad or not again[label].is_structure_current():
            c.fail(f"{label}: saved read-back {bad} current={again[label].is_structure_current()}")
    record.update({"status": "APPLIED", "after": after_all, "findings": findings})
    c.write_json(orig, record)
    ip = os.path.join(HERE, INDEX)
    idx = json.load(open(ip, encoding="utf-8")) if os.path.exists(ip) else {"runs": []}
    idx["runs"].append({"run": c.run, "structures": targets, "status": "APPLIED", "originals": orig})
    c.write_json(INDEX, idx)
    summary = ";".join(f"{t[-2:]}:lines={record['structures'][t]['before']['hanging_line_count']}->"
                       f"{after_all[t]['hanging_line_count']},hits={len(record['structures'][t]['clearance_hits_new_band'])}"
                       for t in targets)
    c.log(f"GIRDERSV3_APPLY_OK|run={c.run}|{summary}|findings={len(findings)}|level_saved=1|dirty_after=0+0"
          f"|originals={orig}|backup={record['backup']}")
    return record


def phase_revert(c: Ctx, args):
    u = c.u
    name = args["revert_record"]
    rec = json.load(open(os.path.join(HERE, name), encoding="utf-8"))
    if rec.get("status") != "APPLIED":
        c.fail(f"{name} status {rec.get('status')} (only APPLIED is reverted; REFUSED_UNSAVED = Don't-Save restart)")
    world = guards(c)
    found = structures_by_label(c, world)
    load_assets(c, [v[i] for k, v in PLAN.items() if k[1].endswith("_mesh") for i in (0, 1)])
    drift = {label: values_match(snapshot(found[label])["fields"], target_values()) for label in rec["structures"]}
    drift = {k: v for k, v in drift.items() if v}
    if drift:  # checked for ALL before the first write: a refusal leaves the level untouched
        c.fail(f"no longer at the applied state {drift}; refusing to overwrite a later edit")
    problems = []
    for label, row in rec["structures"].items():
        s = found[label]
        try:
            write_fields(c, s, fields_from_json(row["snapshot"]["fields"]))
        except GirdersError as exc:
            problems.append(str(exc))
            continue
        if not s.materialize_structure():
            problems.append(f"{label}: re-fit failed")
            continue
        now = counts(s)
        for k in COUNTS:
            if now[k] != row["before"][k]:
                problems.append(f"{label}: {k} {now[k]} != original {row['before'][k]}")
        if not now["current"]:
            problems.append(f"{label}: not current after revert")
        live = render_state(s)
        for part in ("grid", "columns", "knees"):
            if live[part] != row["render_before"][part]:
                problems.append(f"{label}: {part} renders {live[part]} != original {row['render_before'][part]}")
    con, maps = dirty(u)
    if con or maps != [WORLD]:
        problems.append(f"dirty scope content={con} maps={maps}")
    if problems:
        c.fail(f"REVERT not saved (Don't-Save restart, then restore {rec.get('backup')}): {problems}")
    if not u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level():
        c.fail("level save failed")
    if dirty(u) != ([], []):
        c.fail(f"dirty after save {dirty(u)}")
    for label, row in rec["structures"].items():
        bad = values_match(snapshot(found[label])["fields"], fields_from_json(row["snapshot"]["fields"]))
        if bad:
            c.fail(f"{label}: reverted read-back {bad}")
    rec.update({"status": "REVERTED", "reverted_by": c.run})
    c.write_json(name, rec)
    ip = os.path.join(HERE, INDEX)
    if os.path.exists(ip):
        idx = json.load(open(ip, encoding="utf-8"))
        for r in idx["runs"]:
            if r.get("originals") == name:
                r["status"] = "REVERTED"
        c.write_json(INDEX, idx)
    c.log(f"GIRDERSV3_REVERT_OK|run={c.run}|structures={sorted(rec['structures'])}|level_saved=1|dirty_after=0+0")
    return rec


def main():
    c = Ctx()
    try:
        args = load_args(os.path.join(HERE, ARGS_FILE))
    except GirdersError as exc:
        c.fail(str(exc))
    c.log(f"GIRDERSV3_START|run={c.run}|mode={args['mode']}|structures={args['structures']}")
    return {"DRY": phase_dry, "APPLY": phase_apply, "REVERT": phase_revert}[args["mode"]](c, args)


if __name__ == "__main__" or "unreal" in sys.modules and not getattr(sys.modules.get("unreal"), "_GIRDERS_FAKE", False):
    main()
