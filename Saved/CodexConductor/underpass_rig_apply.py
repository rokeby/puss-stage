"""Underpass rig kit, Steps 1 + 3/4: FBX import and Phase A apply (NOT RUN; written 5 Oct 2026).

Blueprint: Docs/Conductor/UNDERPASS_RIG_KIT_PLAN_2026-10-05.md sections 3-4.
Gary, 5 Oct: every Passage's rig becomes underpass iron EXCEPT the Opening/P01 stage PORTAL
(it becomes a baroque stage front later).

PORTALS STAY TIMBER (Gary, 5 Oct). At HEAD 4123f35 the portal has no mesh/material of its own
(declaration-proven): InfinityStageStructureActor.cpp:400-404 loads Gridiron.BeamMesh whenever
Portal.bEnabled; cpp:468-477 builds the portal from *BeamMesh and Gridiron.Material;
FInfinityStagePortalSettings (h:272-365) has no mesh/material. The held patch
Scripts/patches/2026-10-05_PM_portal_own_mesh.patch adds Portal.PortalMesh / Portal.PortalMaterial
(null = the gridiron's, independently per slot). So, for every target whose Portal is enabled:
  - the properties are ABSENT (patch not built): REFUSE (the swap would turn the portal iron).
    The old "portal_iron_ack" opt-in is retired; a mode file that still LISTS a label is refused.
  - else, BEFORE the gridiron swap, PIN Portal.PortalMesh/PortalMaterial to what the portal
    renders today (the gridiron's current timber mesh; its material, or - when the gridiron
    material is null - the material the live portal component renders, refused for multi-slot
    meshes because one override repaints every slot, cpp:549-555). A slot already pinned is left
    alone. The pins and the slots' original values go in the originals JSON BEFORE any change.
  - after the re-fit the portal timber component must still render the pinned mesh/material
    (else nothing is saved). REVERT puts the slots back to their recorded originals (null).
Note (declaration-proven, cpp:1129-1151): the portal's carried-forward grid rails stay pinned
timber but keep the GRIDIRON's section (BeamWidthCm/BeamDepthCm -> 40 x 90 after Phase A) and
height - a timber/iron meeting above the curtain that Gary has not yet seen.

Modes, from Saved/CodexConductor/underpass_rig_mode.json (missing file = DRY):
  DRY     read-only: guards, refusals, originals preview, clearance list, hanging-line window.
  IMPORT  import DerivedAssets/UnderpassKit/FBX/*.fbx to /Game/InfinityStage/RigAtmos/Underpass/Meshes
          (Interchange: options set anyway, folder diffed before/after, never-saved strays deleted,
          1-LOD gate, bounds/axis gate vs kit_manifest.json, Nanite off, modify() before setters),
          saves ONLY the imported meshes.
  APPLY   Phase A on mode["structures"]: originals JSON (fsync, read back) and a Backups/ umap copy
          BEFORE any change; set Gridiron BeamMesh=SM_UP_PlateGirder, Material=MI_UP_Steel_Green,
          BeamWidthCm 40, BeamDepthCm 90, SectionVariation 0, TwistDegrees 0, bCastShadow True;
          Materialize Structure; assert counts + IsStructureCurrent; save the LEVEL only; read back.
  REVERT  restore the originals record named by mode["revert_record"]; re-fit; save level only.
Prototype gate: the first APPLY must be exactly ["Infinity Stage - Structure 05"]; any other
set needs a P05 APPLIED record AND mode["prototype_signed_off"] == true (set after Gary's look).

Census rule (APPLY): stations, cross beams, rails, slots, cloths, portal pieces and housings must be
IDENTICAL. Boards must be identical unless mode["allow_board_drift"] (known 29 Sep drift, reported).
Hanging lines may legitimately change: their top is GridTop = Height + 1.5 x BeamDepth (cpp:1314),
so 34 -> 90 cm raises it 84 cm and a lamp whose drop then exceeds Fixtures.MaxDropCm loses its
line (cpp:1316-1320). DRY predicts a window [old - lost, old - lost + possible_gains] from the live
line/housing instances; APPLY refuses to save outside it.

Markers (all carry run=<id>): UNDERPASS_RIG_DRY_OK, UNDERPASS_KIT_IMPORT_OK, UNDERPASS_RIG_ORIGINALS_OK,
UNDERPASS_RIG_APPLY_OK, UNDERPASS_RIG_REVERT_OK, UNDERPASS_RIG_FAILED, UNDERPASS_RIG_NOOP.
Every UE object lives inside a function; nothing UE-owned at module level (re-run crash rule).
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import sys

WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
WORLD_FILE = "Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
DEST_ROOT = "/Game/InfinityStage/RigAtmos/Underpass"
MESH_DIR = DEST_ROOT + "/Meshes"
GIRDER = MESH_DIR + "/SM_UP_PlateGirder"
MI_GREEN = DEST_ROOT + "/Materials/MI_UP_Steel_Green"
STRUCTURE_LABEL = "Infinity Stage - Structure {:02d}"
P05 = STRUCTURE_LABEL.format(5)
P01 = STRUCTURE_LABEL.format(1)
EXPECTED_STRUCTURES = 6
PHASE_A = {"beam_width_cm": 40.0, "beam_depth_cm": 90.0, "section_variation": 0.0, "twist_degrees": 0.0,
           "cast_shadow": True}
GRID_FIELDS = ("beam_mesh", "material", "beam_width_cm", "beam_depth_cm", "section_variation", "twist_degrees",
               "cast_shadow", "height_cm", "enabled", "overhang_cm", "cross_beam_every")
COUNTS = ("station_count", "cross_beam_count", "rail_segment_count", "board_count", "slot_count",
          "groove_piece_count", "cloth_count", "portal_piece_count", "fixture_body_count", "hanging_line_count")
STRICT = ("station_count", "cross_beam_count", "rail_segment_count", "slot_count", "groove_piece_count",
          "cloth_count", "portal_piece_count", "fixture_body_count")
TAG_GRID = "InfinityStage.Structure.Gridiron"
TAG_LINES = "InfinityStage.Structure.Lines"
TAG_FIXTURES = "InfinityStage.Structure.Fixtures"
TAG_PORTAL = "InfinityStage.Structure.Portal"
# The held C++ change's properties (FInfinityStagePortalSettings::PortalMesh / PortalMaterial).
PORTAL_MESH_PROP = "portal_mesh"
PORTAL_MATERIAL_PROP = "portal_material"
PORTAL_PATCH = "Scripts/patches/2026-10-05_PM_portal_own_mesh.patch"


class RigError(RuntimeError):
    pass


# ============================================================================ pure logic (harness-tested)
def passage_number(label: str):
    prefix = "Infinity Stage - Structure "
    if not label.startswith(prefix):
        return None
    tail = label[len(prefix):]
    return int(tail) if tail.isdigit() else None


def refusal_for(label: str, portal_enabled: bool, portal_has_own_mesh: bool) -> str | None:
    """None = may apply (an enabled portal is then pinned). Else the reason it must not."""
    n = passage_number(label)
    if n is None:
        return f"{label}: not a Passage structure label"
    if portal_enabled and not portal_has_own_mesh:
        return (f"{label}: Portal enabled but FInfinityStagePortalSettings has no {PORTAL_MESH_PROP}/"
                f"{PORTAL_MATERIAL_PROP} (patch {PORTAL_PATCH} not built), so the swap would turn the "
                "portal iron (cpp:400-404, 468-477). Build the patch first")
    return None


def plan_portal_pin(portal: dict, grid: dict, live: dict | None) -> tuple[dict | None, str | None]:
    """What to pin so the portal keeps rendering what it renders now.
    portal: portal_info(); grid: grid_snapshot(); live: portal_timber_live() or None.
    Returns (plan, None) or (None, refusal). plan = {"original": slot values now,
    "set": slots to write (may be empty), "expect": {"mesh", "material"} the portal must render}."""
    if not portal.get("enabled"):
        return {"original": None, "set": {}, "expect": None}, None
    if not portal.get("has_own_mesh"):
        return None, "portal pin properties absent (patch not built)"
    if live is None:
        return None, "portal enabled but no portal timber component (re-fit the structure first, separately)"
    cur_mesh, cur_mat = portal.get(PORTAL_MESH_PROP), portal.get(PORTAL_MATERIAL_PROP)
    plan = {"original": {PORTAL_MESH_PROP: cur_mesh, PORTAL_MATERIAL_PROP: cur_mat}, "set": {}, "expect": {}}
    # mesh: null today = the gridiron's beam mesh, and the live component must agree (a soft pointer
    # whose target is unloaded reads back None: never overwrite a pin we could not read)
    want_mesh = cur_mesh if cur_mesh is not None else grid.get("beam_mesh")
    if live.get("mesh") != want_mesh:
        return None, (f"portal renders mesh {live.get('mesh')} but its slot reads {cur_mesh} and the gridiron's is "
                      f"{grid.get('beam_mesh')} (unreadable pin or stale build)")
    if cur_mesh is None:
        if want_mesh is None:
            return None, "gridiron beam_mesh read back None: nothing to pin the portal to"
        plan["set"][PORTAL_MESH_PROP] = want_mesh
    # material: null today = the gridiron's material; null there too = the mesh's own (no override)
    if cur_mat is not None:
        want_mat = cur_mat
    elif grid.get("material") is not None:
        want_mat = grid["material"]
        plan["set"][PORTAL_MATERIAL_PROP] = want_mat
    else:
        # pinning the mesh's own material as an override is faithful only for a one-slot mesh
        if int(live.get("slots", 0)) != 1:
            return None, (f"gridiron material is null and the portal mesh has {live.get('slots')} slots: one "
                          "PortalMaterial override would repaint every slot (cpp:549-555)")
        want_mat = live.get("material")
        if want_mat is None:
            return None, "portal renders no material and the gridiron's is null: nothing to pin"
        plan["set"][PORTAL_MATERIAL_PROP] = want_mat
    if live.get("material") != want_mat:
        return None, (f"portal renders material {live.get('material')} but expected {want_mat} "
                      "(unreadable pin or stale build)")
    plan["expect"] = {"mesh": want_mesh, "material": want_mat}
    return plan, None


def prototype_gate(structures, mode: dict, p05_applied: bool) -> str | None:
    if list(structures) == [P05]:
        return None
    if not p05_applied:
        return "prototype gate: APPLY Structure 05 alone first (no APPLIED P05 record found)"
    if not mode.get("prototype_signed_off"):
        return "prototype gate: set prototype_signed_off=true only after Gary has judged the P05 look"
    return None


def line_window(old_lines: int, line_drops, housing_old_drops, max_drop: float, depth_old: float,
                depth_new: float):
    """Predict the hanging-line count after a beam-depth change.
    line_drops: current drop (cm) of each existing fixture line.
    housing_old_drops: for every housing, GridTop_old - housing top (cm), lateral not known.
    Returns (lo, hi, detail)."""
    delta = 1.5 * (depth_new - depth_old)
    lost = sum(1 for d in line_drops if d + delta > max_drop or d + delta < 1.0)
    gains = sum(1 for d in housing_old_drops if not (1.0 <= d <= max_drop) and 1.0 <= d + delta <= max_drop)
    lo = old_lines - lost
    return lo, lo + gains, {"grid_top_shift_cm": delta, "lost": lost, "possible_gains": gains,
                            "lines_measured": len(line_drops), "lines_reported": old_lines}


def census_problems(before: dict, after: dict, window, allow_board_drift: bool):
    problems, findings = [], []
    for key in STRICT:
        if before.get(key) != after.get(key):
            problems.append(f"{key} {before.get(key)} -> {after.get(key)}")
    if before.get("board_count") != after.get("board_count"):
        msg = f"board_count {before.get('board_count')} -> {after.get('board_count')}"
        (findings if allow_board_drift else problems).append(msg)
    lo, hi = window
    lines = after.get("hanging_line_count")
    if lines is None or not (lo <= lines <= hi):
        problems.append(f"hanging_line_count {before.get('hanging_line_count')} -> {lines} outside predicted [{lo}, {hi}]")
    elif lines != before.get("hanging_line_count"):
        findings.append(f"hanging_line_count {before.get('hanging_line_count')} -> {lines} (inside predicted [{lo}, {hi}])")
    if not after.get("current"):
        problems.append("IsStructureCurrent() false after the re-fit")
    return problems, findings


def grid_matches(actual: dict, expected: dict, keys) -> list:
    bad = []
    for k in keys:
        a, e = actual.get(k), expected.get(k)
        if isinstance(e, float) or isinstance(a, float):
            if a is None or e is None or abs(float(a) - float(e)) > 1e-4:
                bad.append(f"{k}: {a} != {e}")
        elif a != e:
            bad.append(f"{k}: {a} != {e}")
    return bad


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ============================================================================ editor adapters
def _u():
    import unreal  # noqa: PLC0415  (harness injects a fake into sys.modules)
    return unreal


class Ctx:
    def __init__(self):
        u = _u()
        self.u = u
        self.repo = os.path.normpath(u.Paths.convert_relative_path_to_full(u.Paths.project_dir()))
        self.here = os.path.join(self.repo, "Saved", "CodexConductor")
        self.run = "UPRIG-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        mode_path = os.path.join(self.here, "underpass_rig_mode.json")
        self.mode = json.load(open(mode_path, encoding="utf-8")) if os.path.exists(mode_path) else {"mode": "DRY"}
        self.mode.setdefault("structures", [P05])

    def path(self, name):
        return os.path.join(self.here, name)

    def log(self, msg):
        self.u.log(msg)

    def fail(self, msg):
        self.u.log_error(f"UNDERPASS_RIG_FAILED|run={self.run}|{msg}")
        raise RigError(f"UNDERPASS_RIG_FAILED|run={self.run}|{msg}")

    def write_json(self, name, payload):
        p = self.path(name)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=1)
            fh.flush()
            os.fsync(fh.fileno())
        if json.load(open(p, encoding="utf-8")) != json.loads(json.dumps(payload)):
            self.fail(f"{name} did not read back")
        return p


def _pk(p) -> str:
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s.split(".")[0]


def _obj_path(o):
    if o is None:
        return None
    return o.get_path_name().split(".")[0]


def dirty(u):
    return (sorted(_pk(p) for p in u.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            sorted(_pk(p) for p in u.EditorLoadingAndSavingUtils.get_dirty_map_packages()))


def guards(c: Ctx, need_world=True):
    u = c.u
    ed = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        c.fail("PIE active")
    world = ed.get_editor_world()
    if need_world and (world is None or world.get_path_name().split(".", 1)[0] != WORLD):
        c.fail(f"wrong world {world.get_path_name() if world else None}")
    if dirty(u) != ([], []):
        c.fail(f"editor dirty at start {dirty(u)}")
    return world


def all_actors(u, world):
    # GameplayStatics also lists transient bench actors (memory puss-bench-originals-to-file)
    return list(u.GameplayStatics.get_all_actors_of_class(world, u.Actor))


def structures_by_label(c: Ctx, world):
    u = c.u
    actors = all_actors(u, world)
    bench = [a.get_actor_label() for a in actors if a.get_actor_label().startswith(("ZZ_", "TEMP", "Temp"))]
    if bench:
        c.fail(f"bench actors in the level: {bench}")
    found = {a.get_actor_label(): a for a in actors if isinstance(a, u.InfinityStageStructureActor)}
    if len(found) != EXPECTED_STRUCTURES:
        c.fail(f"{len(found)} structure actors, expected {EXPECTED_STRUCTURES}: {sorted(found)}")
    return found


def grid_snapshot(s) -> dict:
    """Plain values only (never UE wrappers: memory puss-python-api-gotchas)."""
    g = s.get_editor_property("gridiron")
    out = {}
    for k in GRID_FIELDS:
        v = g.get_editor_property(k)
        if k in ("beam_mesh", "material"):
            out[k] = _obj_path(v)
        elif isinstance(v, bool):
            out[k] = bool(v)
        elif isinstance(v, int):
            out[k] = int(v)
        else:
            out[k] = float(v)
    return out


def counts(s) -> dict:
    out = {k: int(s.get_editor_property(k)) for k in COUNTS}
    out["current"] = bool(s.is_structure_current())
    out["grid_half_width_cm"] = float(s.get_editor_property("grid_half_width_cm"))
    total = 0
    for comp in s.get_editor_property("managed_components"):
        if comp:
            total += int(comp.get_instance_count())
    out["instances"] = total
    return out


def components_with_tag(s, tag):
    return [c for c in s.get_editor_property("managed_components")
            if c and tag in [str(t) for t in c.get_editor_property("component_tags")]]


def soft_ptr_check(s, snap) -> str | None:
    """A TSoftObjectPtr read can come back None when its target is not loaded. Cross-check the
    snapshot against what the live gridiron component actually renders with."""
    comps = components_with_tag(s, TAG_GRID)
    if not snap.get("enabled"):
        return None
    if len(comps) != 1:
        return f"{len(comps)} gridiron components (expected 1)"
    comp = comps[0]
    mesh = comp.get_editor_property("static_mesh")
    if _obj_path(mesh) != snap["beam_mesh"]:
        return f"snapshot beam_mesh {snap['beam_mesh']} != component mesh {_obj_path(mesh)}"
    live = _obj_path(comp.get_material(0))
    if snap["material"] is None:
        own = _obj_path(mesh.get_material(0)) if mesh else None
        if live != own:
            return f"snapshot material None but the component renders {live} (unresolved soft pointer?)"
    elif live != snap["material"]:
        return f"snapshot material {snap['material']} != component material {live}"
    return None


def portal_info(s) -> dict:
    """Plain values: enabled, whether the pin properties exist, and their current values (paths)."""
    p = s.get_editor_property("portal")
    out = {"enabled": bool(p.get_editor_property("enabled")), "has_own_mesh": True}
    for k in (PORTAL_MESH_PROP, PORTAL_MATERIAL_PROP):
        try:
            out[k] = _obj_path(p.get_editor_property(k))
        except Exception:  # noqa: BLE001  property absent before the held C++ patch is built
            out["has_own_mesh"] = False
            out[k] = None
    return out


def portal_timber_live(s) -> dict | None:
    """What the portal timber component (posts, header, trough, nosing, carried grid) renders.
    cpp:1170-1171 names it StructurePortal; the lines component is StructurePortalLines."""
    for comp in components_with_tag(s, TAG_PORTAL):
        name = str(comp.get_name())
        if name.startswith("StructurePortal") and not name.startswith("StructurePortalLines"):
            mesh = comp.get_editor_property("static_mesh")
            slots = len(list(mesh.get_editor_property("static_materials"))) if mesh else 0
            return {"mesh": _obj_path(mesh), "material": _obj_path(comp.get_material(0)), "slots": slots,
                    "instances": int(comp.get_instance_count())}
    return None


def _set_portal_pins(c: Ctx, s, values: dict):
    """values: {portal_mesh|portal_material: asset path or None}. Struct copy, write back, read back."""
    u = c.u
    if not values:
        return
    s.modify()
    p = s.get_editor_property("portal")
    for k, v in values.items():
        obj = u.EditorAssetLibrary.load_asset(v) if v else None
        if v and obj is None:
            c.fail(f"{v} does not load")
        p.set_editor_property(k, obj)
    s.set_editor_property("portal", p)
    now = portal_info(s)
    bad = [f"{k}: {now.get(k)} != {v}" for k, v in values.items() if now.get(k) != v]
    if bad:
        c.fail(f"{s.get_actor_label()} portal pin read-back: {bad}")


def line_inputs(c: Ctx, s, depth_old):
    """Measured inputs for line_window: drops of existing fixture lines, and each housing's
    old drop to the grid top (nearest-lowest gridiron instance = its cross beam)."""
    u = c.u
    fixtures = s.get_editor_property("fixtures")
    max_drop = float(fixtures.get_editor_property("max_drop_cm"))
    body = fixtures.get_editor_property("body_size_cm")
    body_h = float(body.z)
    drops = []
    for comp in components_with_tag(s, TAG_LINES):
        mesh = comp.get_editor_property("static_mesh")
        box = mesh.get_bounding_box()
        size_x = float(box.max.x - box.min.x)
        for i in range(int(comp.get_instance_count())):
            xf = comp.get_instance_transform(i, True)
            if xf is None:
                c.fail(f"line instance {i} transform did not read")
            drops.append(float(xf.scale3d.x) * size_x)
    grid_pts = []
    for comp in components_with_tag(s, TAG_GRID):
        for i in range(int(comp.get_instance_count())):
            xf = comp.get_instance_transform(i, True)
            grid_pts.append((float(xf.translation.x), float(xf.translation.y), float(xf.translation.z)))
    housing_drops, housings = [], []
    for comp in components_with_tag(s, TAG_FIXTURES):
        for i in range(int(comp.get_instance_count())):
            xf = comp.get_instance_transform(i, True)
            hx, hy, hz = float(xf.translation.x), float(xf.translation.y), float(xf.translation.z)
            near = [p for p in grid_pts if (p[0] - hx) ** 2 + (p[1] - hy) ** 2 <= 600.0 ** 2]
            if not near:
                continue
            cross_z = min(p[2] for p in near)
            top = hz + body_h * 0.5  # Cube body: bounds centre == instance location (FitMeshToTimber)
            housing_drops.append(cross_z + 1.5 * depth_old - top)
            housings.append((hx, hy, hz, cross_z))
    return {"max_drop": max_drop, "body_h": body_h, "line_drops": drops, "housing_drops": housing_drops,
            "housings": housings}


def clearance(inputs, depth_old, depth_new, body_h):
    """Housings that the deeper girder band reaches but the old band did not (finding, not a gate).
    Band per station: crosses centred at cross_z (+-D/2), rails centred at cross_z + D (+-D/2)."""
    hits = []
    for hx, hy, hz, cz in inputs["housings"]:
        lo_h, hi_h = hz - body_h / 2, hz + body_h / 2
        old_lo, old_hi = cz - depth_old / 2, cz + 1.5 * depth_old
        new_lo, new_hi = cz - depth_new / 2, cz + 1.5 * depth_new
        if hi_h > new_lo and lo_h < new_hi and not (hi_h > old_lo and lo_h < old_hi):
            hits.append([round(hx), round(hy), round(hz)])
    return hits


# ============================================================================ phases
def phase_dry(c: Ctx):
    u = c.u
    world = guards(c)
    found = structures_by_label(c, world)
    report = {"run": c.run, "mode": "DRY", "structures": {}, "mutated": 0}
    p05_applied = _p05_applied(c)
    gate = prototype_gate(c.mode["structures"], c.mode, p05_applied)
    report["prototype_gate"] = gate or "ok"
    kit = {"girder_exists": bool(u.EditorAssetLibrary.does_asset_exist(GIRDER)),
           "mi_exists": bool(u.EditorAssetLibrary.does_asset_exist(MI_GREEN))}
    report["kit"] = kit
    for label in sorted(found):
        s = found[label]
        portal = portal_info(s)
        snap = grid_snapshot(s)
        refusal = refusal_for(label, portal["enabled"], portal["has_own_mesh"])
        pin, pin_refusal = (None, None) if refusal else plan_portal_pin(portal, snap, portal_timber_live(s))
        row = {"targeted": label in c.mode["structures"], "portal": portal, "gridiron": snap, "counts": counts(s),
               "snapshot_check": soft_ptr_check(s, snap) or "ok",
               "refusal": refusal or (f"{label}: {pin_refusal}" if pin_refusal else None),
               "portal_pin": pin}
        if row["targeted"]:
            li = line_inputs(c, s, snap["beam_depth_cm"])
            lo, hi, detail = line_window(row["counts"]["hanging_line_count"], li["line_drops"], li["housing_drops"],
                                         li["max_drop"], snap["beam_depth_cm"], PHASE_A["beam_depth_cm"])
            row["line_window"] = [lo, hi]
            row["line_detail"] = detail
            row["clearance_new_band_housings"] = clearance(li, snap["beam_depth_cm"], PHASE_A["beam_depth_cm"],
                                                           li["body_h"])
            row["would_set"] = {"beam_mesh": GIRDER, "material": MI_GREEN, **PHASE_A}
        report["structures"][label] = row
    if dirty(u) != ([], []):
        c.fail(f"DRY dirtied {dirty(u)}")
    p = c.write_json(f"underpass_rig_dry_{c.run}.json", report)
    targets = c.mode["structures"]
    refused = {t: report["structures"].get(t, {}).get("refusal") for t in targets}
    c.log(f"UNDERPASS_RIG_DRY_OK|run={c.run}|targets={targets}|refused={ {k: bool(v) for k, v in refused.items()} }"
          f"|prototype_gate={'ok' if not gate else 'BLOCKED'}|kit={kit}|mutated=0|report={p}")
    for t in targets:
        r = report["structures"].get(t)
        if r and r.get("line_window"):
            c.log(f"UNDERPASS_RIG_DRY_ROW|run={c.run}|{t}|portal={r['portal']}|refusal={r['refusal']}"
                  f"|portal_pin_set={(r.get('portal_pin') or {}).get('set')}"
                  f"|lines={r['counts']['hanging_line_count']}->[{r['line_window'][0]},{r['line_window'][1]}]"
                  f"|clearance_hits={len(r['clearance_new_band_housings'])}")
    return report


def _fbx_options(u):
    o = u.FbxImportUI()
    o.set_editor_property("import_mesh", True)
    o.set_editor_property("import_as_skeletal", False)
    o.set_editor_property("import_materials", False)
    o.set_editor_property("import_textures", False)
    o.set_editor_property("import_animations", False)
    st = o.get_editor_property("static_mesh_import_data")
    st.set_editor_property("combine_meshes", False)
    st.set_editor_property("import_mesh_lods", False)
    return o


def phase_import(c: Ctx):
    u = c.u
    guards(c, need_world=False)
    manifest_path = os.path.join(c.repo, "DerivedAssets", "UnderpassKit", "kit_manifest.json")
    manifest = json.load(open(manifest_path, encoding="utf-8"))
    if manifest.get("status") != "PASS":
        c.fail("kit_manifest.json is not PASS: run Tools/UnderpassKit/build_underpass_kit.py")
    rows = {r["name"]: r for r in manifest["modules"]}
    wanted = c.mode.get("import_modules") or sorted(rows)
    expected = [f"{MESH_DIR}/{n}" for n in wanted]
    for n in wanted:
        fbx = os.path.join(c.repo, rows[n]["fbx"])
        if sha256_file(fbx) != rows[n]["sha256"]:
            c.fail(f"{n}: FBX sha256 differs from the gated manifest")
    clash = [p for p in expected if u.EditorAssetLibrary.does_asset_exist(p)]
    if clash:
        c.fail(f"import targets exist (replace_existing is off): {clash}")
    before = set(_pk(p) for p in u.EditorAssetLibrary.list_assets(DEST_ROOT, True, False)) \
        if u.EditorAssetLibrary.does_directory_exist(DEST_ROOT) else set()
    tasks = []
    for n in wanted:
        t = u.AssetImportTask()
        t.set_editor_property("filename", os.path.join(c.repo, rows[n]["fbx"]))
        t.set_editor_property("destination_path", MESH_DIR)
        t.set_editor_property("automated", True)
        t.set_editor_property("replace_existing", False)
        t.set_editor_property("save", False)
        t.set_editor_property("options", _fbx_options(u))  # ignored by Interchange; set anyway (memory)
        tasks.append(t)
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    after = set(_pk(p) for p in u.EditorAssetLibrary.list_assets(DEST_ROOT, True, False))
    new = after - before
    strays = sorted(new - set(expected))
    for p in strays:  # never saved: created by this import only
        if not u.EditorAssetLibrary.delete_asset(p):
            c.fail(f"could not delete stray {p}")
    left = sorted((set(_pk(p) for p in u.EditorAssetLibrary.list_assets(DEST_ROOT, True, False)) - before)
                  - set(expected))
    if left:
        c.fail(f"strays survived: {left}")
    missing = sorted(set(expected) - new)
    if missing:
        c.fail(f"not imported: {missing}")
    lod_assets = sorted(p for p in after if "_LOD" in p.rsplit("/", 1)[-1].upper())
    if lod_assets:
        c.fail(f"LOD-split assets present: {lod_assets}")
    readback = {}
    for n, path in zip(wanted, expected):
        m = u.EditorAssetLibrary.load_asset(path)
        if not isinstance(m, u.StaticMesh):
            c.fail(f"{path} is not a StaticMesh")
        lods = int(m.get_num_lods())
        if lods != 1:
            c.fail(f"{n}: {lods} LODs")
        box = m.get_bounding_box()
        size = [float(box.max.x - box.min.x), float(box.max.y - box.min.y), float(box.max.z - box.min.z)]
        exp = rows[n]["bounds_cm"]
        if any(abs(a - b) > 0.2 for a, b in zip(size, exp)):
            c.fail(f"{n}: bounds {size} != manifest {exp} (axis wrong? fix the EXPORT, never rotate in UE)")
        slots = list(m.get_editor_property("static_materials"))
        if len(slots) != 1:
            c.fail(f"{n}: {len(slots)} material slots")
        ns = m.get_editor_property("nanite_settings")
        if bool(ns.get_editor_property("enabled")):
            m.modify()
            ns.set_editor_property("enabled", False)
            m.set_editor_property("nanite_settings", ns)
            if bool(m.get_editor_property("nanite_settings").get_editor_property("enabled")):
                c.fail(f"{n}: Nanite still on after set")
        readback[n] = {"path": path, "lods": lods, "bounds_cm": [round(x, 3) for x in size], "slots": len(slots),
                       "nanite": False}
    con, maps = dirty(u)
    if maps or not set(con) <= set(expected):
        c.fail(f"dirty scope before save content={con} maps={maps}")
    for path in expected:
        if not u.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
            c.fail(f"save {path}")
    if dirty(u) != ([], []):
        c.fail(f"dirty after save {dirty(u)}")
    rec = {"run": c.run, "status": "PASS", "imported": readback, "strays_deleted": strays,
           "manifest_sha": sha256_file(manifest_path)}
    p = c.write_json(f"underpass_kit_import_{c.run}.json", rec)
    c.write_json("underpass_kit_import_last.json", rec)
    c.log(f"UNDERPASS_KIT_IMPORT_OK|run={c.run}|meshes={len(readback)}|strays={len(strays)}->0|report={p}")
    return rec


def _p05_applied(c: Ctx) -> bool:
    p = c.path("underpass_rig_applied_index.json")
    if not os.path.exists(p):
        return False
    idx = json.load(open(p, encoding="utf-8"))
    return any(P05 in r.get("structures", []) and r.get("status") == "APPLIED" for r in idx.get("runs", []))


def _set_grid(c: Ctx, s, values: dict):
    """values: plain dict of GRID_FIELDS subset; beam_mesh/material as asset paths (None allowed for material)."""
    u = c.u
    s.modify()
    g = s.get_editor_property("gridiron")
    for k, v in values.items():
        if k in ("beam_mesh", "material"):
            obj = u.EditorAssetLibrary.load_asset(v) if v else None
            if v and obj is None:
                c.fail(f"{v} does not load")
            g.set_editor_property(k, obj)
        else:
            g.set_editor_property(k, v)
    s.set_editor_property("gridiron", g)
    bad = grid_matches(grid_snapshot(s), values, values.keys())
    if bad:
        c.fail(f"{s.get_actor_label()} gridiron read-back: {bad}")


def phase_apply(c: Ctx):
    u = c.u
    world = guards(c)
    found = structures_by_label(c, world)
    targets = list(c.mode["structures"])
    if not targets:
        c.log(f"UNDERPASS_RIG_NOOP|run={c.run}|no structures listed")
        return None
    gate = prototype_gate(targets, c.mode, _p05_applied(c))
    if gate:
        c.fail(gate)
    if c.mode.get("portal_iron_ack"):  # an empty list (the shipped mode file) asks for nothing
        c.fail("portal_iron_ack is retired: portals are pinned timber, never turned iron (Gary, 5 Oct); "
               "remove the key from the mode file")
    imp = c.path("underpass_kit_import_last.json")
    if not os.path.exists(imp) or json.load(open(imp, encoding="utf-8")).get("status") != "PASS":
        c.fail("no PASS kit import record (run IMPORT first)")
    for p in (GIRDER, MI_GREEN):
        if not u.EditorAssetLibrary.does_asset_exist(p):
            c.fail(f"{p} missing")
    record = {"run": c.run, "status": "ORIGINALS_WRITTEN", "written": datetime.datetime.now().isoformat(timespec="seconds"),
              "world": WORLD, "phase_a": {"beam_mesh": GIRDER, "material": MI_GREEN, **PHASE_A}, "structures": {}}
    for label in targets:
        if label not in found:
            c.fail(f"{label} not in level")
        s = found[label]
        portal = portal_info(s)
        why = refusal_for(label, portal["enabled"], portal["has_own_mesh"])
        if why:
            c.fail(why)
        before = counts(s)
        if not before["current"]:
            c.fail(f"{label} is not current before the swap (re-fit it first, separately)")
        snap = grid_snapshot(s)
        bad = soft_ptr_check(s, snap)
        if bad:
            c.fail(f"{label}: originals snapshot not trustworthy: {bad}")
        pin, why = plan_portal_pin(portal, snap, portal_timber_live(s))
        if why:
            c.fail(f"{label}: {why}")
        li = line_inputs(c, s, snap["beam_depth_cm"])
        lo, hi, detail = line_window(before["hanging_line_count"], li["line_drops"], li["housing_drops"],
                                     li["max_drop"], snap["beam_depth_cm"], PHASE_A["beam_depth_cm"])
        record["structures"][label] = {"original_gridiron": snap, "before": before, "portal": portal,
                                       "portal_pin": pin, "line_window": [lo, hi], "line_detail": detail}
    # 1) originals to disk BEFORE anything changes
    orig_name = f"underpass_rig_originals_{c.run}.json"
    orig_path = c.write_json(orig_name, record)
    c.log(f"UNDERPASS_RIG_ORIGINALS_OK|run={c.run}|structures={targets}|path={orig_path}")
    # 2) level snapshot BEFORE anything changes (level is clean, so disk == memory)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    tag = "".join(f"P{passage_number(t):02d}" for t in targets)
    bdir = os.path.join(c.repo, "Backups", f"PreUnderpass{tag}-{stamp}")
    src = os.path.join(c.repo, WORLD_FILE)
    dst = os.path.join(bdir, WORLD_FILE)
    os.makedirs(os.path.dirname(dst), exist_ok=False)
    shutil.copy2(src, dst)
    if sha256_file(src) != sha256_file(dst):
        c.fail("level backup sha256 mismatch")
    record["backup"] = os.path.relpath(dst, c.repo).replace("\\", "/")
    c.write_json(orig_name, record)
    # 3) mutate, re-fit, census
    problems, findings, after_all = [], [], {}
    try:
        for label in targets:
            s = found[label]
            pin = record["structures"][label]["portal_pin"]
            _set_portal_pins(c, s, pin["set"])  # BEFORE the swap: the portal keeps today's timber
            _set_grid(c, s, {"beam_mesh": GIRDER, "material": MI_GREEN, **PHASE_A})
            if not s.materialize_structure():
                problems.append(f"{label}: MaterializeStructure returned false (previous build kept)")
                continue
            if pin["expect"]:
                live = portal_timber_live(s)
                if live is None or live["mesh"] != pin["expect"]["mesh"] or live["material"] != pin["expect"]["material"]:
                    problems.append(f"{label}: portal timber after the swap renders {live} != pinned {pin['expect']}")
            after = counts(s)
            after_all[label] = after
            prob, find = census_problems(record["structures"][label]["before"], after,
                                         record["structures"][label]["line_window"],
                                         bool(c.mode.get("allow_board_drift")))
            problems += [f"{label}: {p}" for p in prob]
            findings += [f"{label}: {f}" for f in find]
            grid = components_with_tag(s, TAG_GRID)
            exp_inst = after["cross_beam_count"] + after["rail_segment_count"]
            if len(grid) != 1:
                problems.append(f"{label}: {len(grid)} gridiron components")
            else:
                comp = grid[0]
                if _obj_path(comp.get_editor_property("static_mesh")) != GIRDER:
                    problems.append(f"{label}: gridiron component mesh is not the girder")
                if _obj_path(comp.get_material(0)) != MI_GREEN:
                    problems.append(f"{label}: gridiron component material is not {MI_GREEN}")
                if int(comp.get_instance_count()) != exp_inst:
                    problems.append(f"{label}: gridiron instances {comp.get_instance_count()} != {exp_inst}")
        con, maps = dirty(u)
        if con or maps != [WORLD]:
            problems.append(f"dirty scope content={con} maps={maps}")
    except Exception as exc:  # noqa: BLE001  (RigError included: restore before failing)
        problems.append(f"exception {exc}")
    if problems:
        # put the originals back in memory so the editor shows the old rig; the level stays
        # DIRTY and UNSAVED: the conductor does a Don't-Save restart (never reload from Python)
        for label in targets:
            try:
                pin = record["structures"][label]["portal_pin"]
                if pin["set"]:
                    _set_portal_pins(c, found[label], {k: pin["original"][k] for k in pin["set"]})
                _set_grid(c, found[label], record["structures"][label]["original_gridiron"])
                found[label].materialize_structure()
            except Exception:  # noqa: BLE001
                pass
        record["status"] = "REFUSED_UNSAVED"
        record["problems"] = problems
        c.write_json(orig_name, record)
        c.fail(f"NOT saved; originals restored in memory; Don't-Save restart required: {problems}")
    if not u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level():
        c.fail("level save failed (level dirty: Don't-Save restart)")
    if dirty(u) != ([], []):
        c.fail(f"dirty after save {dirty(u)}")
    # 4) read back after save
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    again = structures_by_label(c, world)
    for label in targets:
        s = again[label]
        bad = grid_matches(grid_snapshot(s), {"beam_mesh": GIRDER, "material": MI_GREEN, **PHASE_A},
                           ["beam_mesh", "material", *PHASE_A])
        pin = record["structures"][label]["portal_pin"]
        now = portal_info(s)
        bad += [f"portal {k}: {now.get(k)} != {v}" for k, v in pin["set"].items() if now.get(k) != v]
        if bad or not s.is_structure_current():
            c.fail(f"{label}: saved read-back {bad} current={s.is_structure_current()}")
    record["status"] = "APPLIED"
    record["after"] = after_all
    record["findings"] = findings
    c.write_json(orig_name, record)
    idx_path = c.path("underpass_rig_applied_index.json")
    idx = json.load(open(idx_path, encoding="utf-8")) if os.path.exists(idx_path) else {"runs": []}
    idx["runs"].append({"run": c.run, "structures": targets, "status": "APPLIED", "originals": orig_name})
    c.write_json("underpass_rig_applied_index.json", idx)
    summary = ";".join(f"{t}:cross={after_all[t]['cross_beam_count']},rails={after_all[t]['rail_segment_count']},"
                       f"lines={record['structures'][t]['before']['hanging_line_count']}->{after_all[t]['hanging_line_count']},"
                       f"instances={record['structures'][t]['before']['instances']}->{after_all[t]['instances']}"
                       for t in targets)
    c.log(f"UNDERPASS_RIG_APPLY_OK|run={c.run}|{summary}|findings={len(findings)}|level_saved=1|dirty_after=0+0"
          f"|originals={orig_name}|backup={record['backup']}")
    return record


def phase_revert(c: Ctx):
    u = c.u
    name = c.mode.get("revert_record")
    if not name:
        c.fail("revert_record not set in the mode file")
    rec = json.load(open(c.path(name), encoding="utf-8"))
    if rec.get("status") != "APPLIED":
        c.fail(f"{name} status {rec.get('status')} (only an APPLIED record is reverted; REFUSED_UNSAVED = restart)")
    world = guards(c)
    found = structures_by_label(c, world)
    problems = []
    for label, row in rec["structures"].items():
        s = found[label]
        pin = row.get("portal_pin") or {"set": {}}
        if pin["set"]:
            if not portal_info(s)["has_own_mesh"]:
                c.fail(f"{label}: record pinned the portal but the pin properties are absent (older C++ loaded?)")
            _set_portal_pins(c, s, {k: pin["original"][k] for k in pin["set"]})  # back to null
        _set_grid(c, s, row["original_gridiron"])
        if not s.materialize_structure():
            problems.append(f"{label}: re-fit failed")
            continue
        now = counts(s)
        for k in (*STRICT, "board_count", "hanging_line_count"):
            if now[k] != row["before"][k]:
                problems.append(f"{label}: {k} {now[k]} != original {row['before'][k]}")
        if not now["current"]:
            problems.append(f"{label}: not current after revert")
        if pin["set"]:
            live = portal_timber_live(s)
            if live is None or live["mesh"] != pin["expect"]["mesh"] or live["material"] != pin["expect"]["material"]:
                problems.append(f"{label}: reverted portal renders {live} != original {pin['expect']}")
    con, maps = dirty(u)
    if con or maps != [WORLD]:
        problems.append(f"dirty scope content={con} maps={maps}")
    if problems:
        c.fail(f"REVERT not saved (Don't-Save restart, then restore {rec.get('backup')}): {problems}")
    if not u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level():
        c.fail("level save failed")
    if dirty(u) != ([], []):
        c.fail(f"dirty after save {dirty(u)}")
    rec["status"] = "REVERTED"
    rec["reverted_by"] = c.run
    c.write_json(name, rec)
    idx_path = c.path("underpass_rig_applied_index.json")
    if os.path.exists(idx_path):
        idx = json.load(open(idx_path, encoding="utf-8"))
        for r in idx["runs"]:
            if r.get("originals") == name:
                r["status"] = "REVERTED"
        c.write_json("underpass_rig_applied_index.json", idx)
    c.log(f"UNDERPASS_RIG_REVERT_OK|run={c.run}|structures={sorted(rec['structures'])}|level_saved=1|dirty_after=0+0")
    return rec


def main():
    c = Ctx()
    mode = str(c.mode.get("mode", "DRY")).upper()
    phases = {"DRY": phase_dry, "IMPORT": phase_import, "APPLY": phase_apply, "REVERT": phase_revert}
    if mode not in phases:
        c.fail(f"unknown mode {mode}")
    c.log(f"UNDERPASS_RIG_START|run={c.run}|mode={mode}|structures={c.mode.get('structures')}")
    return phases[mode](c)


if __name__ == "__main__" or "unreal" in sys.modules and not getattr(sys.modules.get("unreal"), "_UNDERPASS_FAKE", False):
    main()
