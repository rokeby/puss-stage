"""Fence stack to 7.5 m + tubes dimmer (Gary 6 Oct, PIE): the fence-top tubes are "too low and too bright. The fence
needs raising to about 7.5m", "7.5m on all passages"; he chose "Stack it" (real 3 m FenceBay panels stacked in rows,
not one panel stretched 2.5x) and "Glow halved, light 1/4": TubeGlowLevel 0.15 -> 0.07, TubeLightIntensity x 0.25.
Blinking is untouched.

NEEDS THE FS BUILD (held patch Scripts/patches/2026-10-06_FS_fence_stack.patch): EInfinityFenceHeightMode::Stack,
FInfinityStageUnderpassSettings::bFenceStackCutTopRow, FInfinityStageFenceVariant::bGroundRowOnly and the actor's
UnderpassFenceRowCount / UnderpassFenceStackTopCm exist only after it. Without them APPLY / REVERT stop
BUILD_MISSING_FS before touching anything; DRY reports it as a live blocker.

Per structure (all six by default) APPLY writes exactly these Underpass fields, recording every BEFORE value:
  fence_height_mode = STACK, fence_height_cm = 750, fence_stack_cut_top_row = (args "top_row" == "cut"),
  tube_glow_level = 0.07, tube_light_intensity = 0.25 x the live value.
Stack rows (C++ AInfinityStageStructureActor::PlanFenceStack, mirrored by plan_stack below): the row is the tallest built
bay (SM_FenceBay_short_open, 302.68 cm, FV3FBS-20261005-01). "cut" (default): 2 whole rows + a 144.65 cm top row
Z-scaled to 0.478, top exactly 750. "whole": round(750 / 302.68) = 2 rows, top 605.35, nothing scaled. Doors (variant D)
only on the ground row. The fence-top tubes ride the built top (+ TubeFenceTopRaiseCm); with the fence OFF they read
FenceHeightCm (750) as before, so on a fence-less Passage the tubes rise to 750 + raise with no fence under them.

Args fence_stack_750_args.json {"mode": "DRY"|"APPLY"|"REVERT", "confirm": "<MODE> FENCE750",
  "top_row": "cut"|"whole", "structures": [...labels], "height_cm": 750, "glow": 0.07, "light_factor": 0.25}.
APPLY: guards (args, no PIE, right world, clean census, no ZZ_/TEMP bench actors, Sequencer closed, FS fields present,
  no record, no structure already Stack) -> record (exclusive create, fsync, read back) + umap backup
  Backups/PreFence750-<run>/ (sha checked) -> per structure: set, read back, MaterializeStructure, IsStructureCurrent,
  layer check BY INSTANCE TRANSFORMS (never get_component_bounds: it reads zero right after a materialize, the
  6 Oct 01:47 false alarm): every non-fence non-tube layer identical; fence ground row = the old panels exactly,
  rows above at k x row with the planned Z scale, N x rows panels; every tube and tube light unmoved or moved up by
  exactly the fence-top delta; every tube light at the new intensity; the C++ row count / top = plan_stack's
  -> census = the level only -> save the level -> census clean -> umap changed on disk -> fields read back
  -> record state "applied" -> FENCE750_APPLY_OK|run=..
REVERT: record state "applied" and every structure still as applied; restores every recorded field, re-materializes,
  checks the fence and tube layers are back to the recorded BEFORE instances and the other layers unchanged, saves the
  level only, renames the record -> FENCE750_REVERT_OK|run=..
A failure after the backup: NOTHING is saved; restart the editor with Don't Save (record + backup stand).

Planning and checking functions are Unreal-free for test_fence_stack_750.py. No UE objects at module level.
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
STRUCTURES = ["Infinity Stage - Structure 0%d" % n for n in range(1, 7)]
CONFIRM_TAIL = "FENCE750"
DEFAULTS = {"mode": "DRY", "top_row": "cut", "structures": list(STRUCTURES), "height_cm": 750.0, "glow": 0.07,
            "light_factor": 0.25}
MIN_CUT_FRACTION = 0.25          # FInfinityStageUnderpassSettings::FenceStackMinCutFraction
FS_UNDERPASS_FIELDS = ("fence_stack_cut_top_row",)
FS_ACTOR_FIELDS = ("underpass_fence_row_count", "underpass_fence_stack_top_cm")
WRITTEN = ("fence_height_mode", "fence_height_cm", "fence_stack_cut_top_row", "tube_glow_level", "tube_light_intensity")
VARIANTS = ("fence_variant_a", "fence_variant_b", "fence_variant_c", "fence_variant_d")
TAG_FENCE_PANEL = "InfinityStage.Structure.Underpass.Fence."
TAG_FENCE_OVERLAY = "InfinityStage.Structure.Underpass.FenceOverlay."
TAG_TUBES = "InfinityStage.Structure.Underpass.Tubes"
TAG_TUBE_LIGHTS = "InfinityStage.Structure.Underpass.TubeLights"
POS_TOL = 0.5                    # cm
SCALE_TOL = 1e-3
ROT_TOL = 1e-4
FIELD_TOL = 1e-3
# Clearance references (offline records; DRY re-reads the gridiron live).
TOP_LAMP_RECORDS = "rig_lamp_drop_record_%s.json"     # after_target_rows[*].relative_transform.location
CAR_PATHS = {"P02": {"tool": "place_p02_car_light.py:19-20", "lateral_cm": 2400.0, "z_cm": 90.0},
             "P06": {"tool": "place_p06_car_light.py:34-35", "lateral_cm": 2400.0, "z_cm": 90.0}}


class Fence750Error(RuntimeError):
    pass


# ============================================================================ pure planning (no unreal)
def plan_stack(intended_cm, row_cm, cut_top_row):
    """Mirror of AInfinityStageStructureActor::PlanFenceStack (the FS patch). Returns rows, row, top_row, top."""
    row = max(1.0, row_cm if math.isfinite(row_cm) else 1.0)
    intended = max(1.0, intended_cm if math.isfinite(intended_cm) else 1.0)
    top_row = row
    if not cut_top_row:
        rows = max(1, int(math.floor(intended / row + 0.5)))   # FMath::RoundToInt32 = floor(x + 0.5)
    else:
        whole = int(math.floor(intended / row))
        rest = intended - row * whole
        if whole == 0:
            rows, top_row = 1, intended
        elif rest >= row * MIN_CUT_FRACTION:
            rows, top_row = whole + 1, rest
        else:
            rows = whole
    return {"rows": rows, "row_cm": row, "top_row_cm": top_row, "top_cm": row * (rows - 1) + top_row}


def enum_name(v):
    """'<InfinityFenceHeightMode.NATIVE: 0>' / 'InfinityFenceHeightMode.NATIVE' / 'NATIVE' -> 'NATIVE'."""
    s = str(getattr(v, "name", None) or v)
    s = s.strip("<>").split(":")[0]
    return s.split(".")[-1].strip().upper()


def same_val(got, want):
    if isinstance(want, bool) or isinstance(got, bool):
        return bool(got) == bool(want)
    if isinstance(want, (int, float)) and isinstance(got, (int, float)):
        return abs(float(got) - float(want)) <= FIELD_TOL * max(1.0, abs(float(want)))
    return got == want


def quat_same(a, b):
    return abs(abs(sum(x * y for x, y in zip(a, b))) - 1.0) <= ROT_TOL


def xf_same(a, b, dz=0.0, sz=None):
    """a, b: {"loc", "quat", "scale"}; b expected = a moved up dz, Z scale multiplied by sz (None = same)."""
    if any(abs(b["loc"][i] - a["loc"][i] - (dz if i == 2 else 0.0)) > POS_TOL for i in range(3)):
        return False
    if not quat_same(a["quat"], b["quat"]):
        return False
    want_z = a["scale"][2] * sz if sz is not None else a["scale"][2]
    return (abs(b["scale"][0] - a["scale"][0]) <= SCALE_TOL and abs(b["scale"][1] - a["scale"][1]) <= SCALE_TOL
            and abs(b["scale"][2] - want_z) <= SCALE_TOL)


def layer_key(name, tags):
    """A rebuilt component may get another _N suffix (MakeUniqueObjectName, InfinityStageStructureActor.cpp:766)."""
    return re.sub(r"_\d+$", "", str(name)) + "|" + ",".join(sorted(str(t) for t in tags))


def xy_key(e):
    return (int(round(e["loc"][0])), int(round(e["loc"][1])))


def key_index(entries, what, problems):
    out = {}
    for e in entries:
        k = xy_key(e)
        if k in out:
            problems.append("%s: two instances at plan %s (cannot pair by XY)" % (what, k))
            return None
        out[k] = e
    return out


def check_others(before, after):
    """Every non-fence, non-tube layer: same names, same counts, same transforms (as sorted lists)."""
    p = []
    if sorted(before) != sorted(after):
        return ["other layers: %s -> %s" % (sorted(before), sorted(after))]
    for name in before:
        a = sorted(before[name], key=lambda e: tuple(round(v, 2) for v in e["loc"]))
        b = sorted(after[name], key=lambda e: tuple(round(v, 2) for v in e["loc"]))
        if len(a) != len(b):
            p.append("%s: %d -> %d instances" % (name, len(a), len(b)))
            continue
        bad = sum(1 for x, y in zip(a, b) if not xf_same(x, y))
        if bad:
            p.append("%s: %d instances moved" % (name, bad))
    return p


def check_fence(before_panels, after_panels, plan):
    """before: the unstacked (one-row) panels; after: the stacked panels; all fence-panel layers together.
    Each entry {"loc", "quat", "scale", "minz", "variant"}. Row k bottom = row 0 bottom + k x row; the last row's Z
    scale is top_row / row (cut) or 1; the ground row is the old panel exactly (same variant); no door above row 0."""
    p = []
    rows, row, top_row = plan["rows"], plan["row_cm"], plan["top_row_cm"]
    if len(after_panels) != len(before_panels) * rows:
        p.append("fence: %d panels after, want %d x %d rows" % (len(after_panels), len(before_panels), rows))
    base = key_index(before_panels, "fence before", p)
    if base is None:
        return p
    seen = {}
    for e in after_panels:
        k = xy_key(e)
        b = base.get(k)
        if b is None:
            p.append("fence: panel at %s has no ground-row partner" % (k,))
            continue
        # origin = bottom - minz * scale_z, so dz = k*row - minz*scale0*(s_k - 1), s_k the row's Z scale factor.
        matched = None
        for r in range(rows):
            s = (top_row / row) if r == rows - 1 else 1.0
            dz = row * r - b["minz"] * b["scale"][2] * (s - 1.0)
            if xf_same(b, e, dz, s):
                matched = r
                break
        if matched is None:
            p.append("fence: panel at %s z %.2f scale %.4f fits no row" % (k, e["loc"][2], e["scale"][2]))
            continue
        if matched == 0 and e["variant"] != b["variant"]:
            p.append("fence: ground row re-rolled at %s (%s -> %s)" % (k, b["variant"], e["variant"]))
        if matched > 0 and e["variant"] == "D":
            p.append("fence: a door (D) in row %d at %s" % (matched, k))
        if matched in seen.setdefault(k, set()):
            p.append("fence: two panels in row %d at %s" % (matched, k))
        seen[k].add(matched)
    full = set(range(rows))
    short = [k for k in base if seen.get(k) != full]
    if short:
        p.append("fence: %d tiles without exactly rows 0..%d (first %s)" % (len(short), rows - 1, short[0]))
    return p[:12]


def check_moved(before, after, dz, what):
    """Every tube (or tube light) unmoved or moved up by exactly dz; counts equal; returns (problems, moved)."""
    p = []
    if len(before) != len(after):
        return ["%s: %d -> %d" % (what, len(before), len(after))], 0
    if dz == 0.0:
        return check_others({what: before}, {what: after}), 0
    base = key_index(before, what + " before", p)
    if base is None:
        return p, 0
    moved = 0
    for e in after:
        b = base.get(xy_key(e))
        if b is None:
            p.append("%s: %s has no partner" % (what, xy_key(e)))
        elif xf_same(b, e, 0.0):
            pass
        elif xf_same(b, e, dz):
            moved += 1
        else:
            p.append("%s at %s: z %.2f -> %.2f (want +0 or +%.2f)" % (what, xy_key(e), b["loc"][2], e["loc"][2], dz))
    return p[:12], moved


def built_row_cm(variants, fence_on, underpass_on):
    """The tallest built bay: the C++ rule (mesh set and finite weight > 0, fence and underpass on)."""
    if not (fence_on and underpass_on):
        return 0.0
    hs = [v["mesh_z"] for v in variants.values()
          if v["mesh"] and v["mesh_z"] is not None and math.isfinite(v["weight"]) and v["weight"] > 0.0]
    return max(hs) if hs else 0.0


def predict(before, args):
    """What APPLY will set and build for one structure, from its BEFORE read."""
    cut = str(args["top_row"]).lower() == "cut"
    height = float(args["height_cm"])
    row_cm = built_row_cm(before["variants"], before["fence"], before["underpass_enabled"])
    plan = plan_stack(height, row_cm, cut) if row_cm > 0.0 else None
    old_top = max(1.0, float(before["fence_height_cm"]))
    new_top = plan["top_cm"] if plan else max(1.0, height)
    tubes_on = before["underpass_enabled"] and before["tubes"] and before["tube_fence_top_rows"]
    return {"targets": {"fence_height_mode": "STACK", "fence_height_cm": height, "fence_stack_cut_top_row": cut,
                        "tube_glow_level": float(args["glow"]),
                        "tube_light_intensity": float(before["tube_light_intensity"]) * float(args["light_factor"])},
            "plan": plan, "old_top_cm": old_top, "new_top_cm": new_top,
            "tube_dz_cm": (new_top - old_top) if tubes_on else 0.0,
            "whole_rows_alternative": plan_stack(height, row_cm, False) if row_cm > 0.0 else None,
            "overlay_variants": [k[-1].upper() for k, v in before["variants"].items() if v["overlay"] and v["mesh"]]}


def clearance(before, pred, lamps):
    """Station-frame heights above the station line (the floor at FloorHeightCm) and lateral lines."""
    floor, base = before["floor_height_cm"], before["fence_base_cm"]
    fence_top = floor + base + pred["new_top_cm"]
    tube_z = fence_top + before["tube_fence_top_raise_cm"]
    girder_under = before["gridiron_height_cm"] - before["beam_depth_cm"] / 2.0
    fence_line = before["grid_half_width_cm"] + before["column_outset_cm"] - before["fence_inset_cm"]
    out = {"fence_top_cm": round(fence_top, 2), "tube_centre_cm": round(tube_z, 2),
           "girder_underside_cm": round(girder_under, 2), "fence_to_girder_cm": round(girder_under - fence_top, 2),
           "tube_top_to_girder_cm": round(girder_under - tube_z - before["tube_diameter_cm"] / 2.0, 2),
           "deck_underside_cm": before["deck_height_cm"], "fence_line_lateral_cm": round(fence_line, 1)}
    if lamps and "error" not in lamps:
        out["top_lamps"] = {"source": lamps["source"], "lateral_cm": lamps["lateral"], "z_cm": lamps["z"],
                            "housing_top_max_cm": round(girder_under - 5.0, 2),
                            "tube_to_lamp_vertical_cm": round(min(lamps["z"]) - tube_z, 2),
                            "fence_to_lamp_lateral_cm": round(fence_line - max(lamps["lateral"]), 1)}
    elif lamps:
        out["top_lamps"] = lamps
    return out


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
        self.run = datetime.datetime.now().strftime("FENCE750-%Y%m%d-%H%M%S")
        self.record = os.path.join(self.here, "fence_stack_750_record.json")
        self.umap = os.path.join(self.repo, *UMAP_REL)
        self.past_backup = False

    def log(self, msg):
        self.u.log(msg)

    def fail(self, msg):
        tail = "|NOTHING SAVED; restart the editor with Don't Save" if self.past_backup else ""
        self.u.log_error("FENCE750_FAILED|run=%s|mode=%s|%s%s" % (self.run, self.mode, msg, tail))
        raise Fence750Error("FENCE750_FAILED|run=%s|%s" % (self.run, msg))


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


def find_structures(c, actors, labels):
    out = {}
    for label in labels:
        hits = [a for a in actors if str(a.get_actor_label()) == label and isinstance(a, c.u.InfinityStageStructureActor)]
        if len(hits) != 1:
            c.fail("STRUCTURE_COUNT|%s|%d" % (label, len(hits)))
        out[label] = hits[0]
    return out


def fs_missing(c, s):
    """The FS build's fields, probed read-only. Returns the first missing name or None."""
    under = s.get_editor_property("underpass")
    for k in FS_UNDERPASS_FIELDS:
        try:
            under.get_editor_property(k)
        except Exception:  # noqa: BLE001
            return "underpass." + k
    for k in FS_ACTOR_FIELDS:
        try:
            s.get_editor_property(k)
        except Exception:  # noqa: BLE001
            return k
    try:
        under.get_editor_property(VARIANTS[3]).get_editor_property("ground_row_only")
    except Exception:  # noqa: BLE001
        return "fence_variant.ground_row_only"
    if not hasattr(c.u.InfinityFenceHeightMode, "STACK"):
        return "InfinityFenceHeightMode.STACK"
    return None


def read_written(under):
    out = {}
    for k in WRITTEN:
        try:
            v = under.get_editor_property(k)
        except Exception:  # noqa: BLE001  pre-FS build: the cut flag is absent
            out[k] = None
            continue
        out[k] = enum_name(v) if k == "fence_height_mode" else (bool(v) if isinstance(v, bool) else float(v))
    return out


def read_before(c, s):
    under = s.get_editor_property("underpass")
    grid = s.get_editor_property("gridiron")
    ground = s.get_editor_property("ground")
    variants = {}
    for k in VARIANTS:
        v = under.get_editor_property(k)
        mesh = v.get_editor_property("mesh")
        try:
            gro = bool(v.get_editor_property("ground_row_only"))
        except Exception:  # noqa: BLE001
            gro = None
        bb = mesh.get_bounding_box() if mesh else None
        variants[k] = {"mesh": _path(mesh), "mesh_z": (bb.max.z - bb.min.z) if bb else None,
                       "weight": float(v.get_editor_property("weight")), "overlay": _path(v.get_editor_property("overlay_mesh")),
                       "ground_row_only": gro}
    b = read_written(under)
    b.update({"underpass_enabled": bool(under.get_editor_property("enabled")), "fence": bool(under.get_editor_property("fence")),
              "fence_cast_shadow": bool(under.get_editor_property("fence_cast_shadow")),
              "fence_both_sides": bool(under.get_editor_property("fence_both_sides")),
              "fence_base_cm": float(under.get_editor_property("fence_base_cm")),
              "fence_inset_cm": float(under.get_editor_property("fence_inset_cm")),
              "column_outset_cm": float(under.get_editor_property("column_outset_cm")),
              "deck_height_cm": float(under.get_editor_property("deck_height_cm")),
              "tubes": bool(under.get_editor_property("tubes")),
              "tube_fence_top_rows": bool(under.get_editor_property("tube_fence_top_rows")),
              "tube_fence_top_raise_cm": float(under.get_editor_property("tube_fence_top_raise_cm")),
              "tube_diameter_cm": float(under.get_editor_property("tube_diameter_cm")),
              "tube_lights": bool(under.get_editor_property("tube_lights")),
              "tube_light_cast_shadow": bool(under.get_editor_property("tube_light_cast_shadow")),
              "tube_blink_fraction": float(under.get_editor_property("tube_blink_fraction")),
              "gridiron_height_cm": float(grid.get_editor_property("height_cm")),
              "beam_depth_cm": float(grid.get_editor_property("beam_depth_cm")),
              "floor_height_cm": float(ground.get_editor_property("floor_height_cm")),
              "grid_half_width_cm": float(s.get_editor_property("grid_half_width_cm")),
              "fence_panels": int(s.get_editor_property("underpass_fence_panel_count")),
              "fence_overlays": int(s.get_editor_property("underpass_fence_overlay_count")),
              "tube_count": int(s.get_editor_property("underpass_tube_count")),
              "tube_light_count": int(s.get_editor_property("underpass_tube_light_count")),
              "variants": variants})
    return b


def _xf(t):
    q = t.rotation
    return {"loc": [t.translation.x, t.translation.y, t.translation.z], "quat": [q.x, q.y, q.z, q.w],
            "scale": [t.scale3d.x, t.scale3d.y, t.scale3d.z]}


def snapshot(c, s):
    """Every ISM layer's instances, read one by one (get_instance_transform, world). Never the cached bounds."""
    u = c.u
    snap = {"panels": [], "overlays": [], "tubes": [], "others": {}, "lights": []}
    for comp in s.get_components_by_class(u.InstancedStaticMeshComponent):
        tags = [str(t) for t in comp.get_editor_property("component_tags")]
        n = int(comp.get_instance_count())
        mesh = comp.get_editor_property("static_mesh")
        minz = mesh.get_bounding_box().min.z if mesh else 0.0
        ents = []
        for i in range(n):
            e = _xf(comp.get_instance_transform(i, True))
            e["minz"] = minz
            ents.append(e)
        panel = [t for t in tags if t.startswith(TAG_FENCE_PANEL)]
        if panel:
            for e in ents:
                e["variant"] = panel[0][len(TAG_FENCE_PANEL):]
            snap["panels"] += ents
        elif any(t.startswith(TAG_FENCE_OVERLAY) for t in tags):
            snap["overlays"] += ents
        elif TAG_TUBES in tags:
            snap["tubes"] += ents
        else:
            snap["others"].setdefault(layer_key(comp.get_name(), tags), []).extend(ents)
    for light in s.get_components_by_class(u.RectLightComponent):
        if TAG_TUBE_LIGHTS in [str(t) for t in light.get_editor_property("component_tags")]:
            loc = light.get_world_location()
            snap["lights"].append({"loc": [loc.x, loc.y, loc.z], "quat": [0.0, 0.0, 0.0, 1.0], "scale": [1.0, 1.0, 1.0],
                                   "intensity": float(light.get_editor_property("intensity"))})
    return snap


def lamp_band(c, label):
    """TOP lamp station-frame (lateral, z) from the rig_lamp_drop record for this Passage, or None."""
    path = os.path.join(c.here, TOP_LAMP_RECORDS % ("P0" + label[-1]))
    if not os.path.exists(path):
        return None
    try:
        rows = json.load(open(path, encoding="utf-8"))["after_target_rows"].values()
        locs = [r["relative_transform"]["location"] for r in rows]
        return {"source": os.path.basename(path), "lateral": sorted({round(abs(l[1]), 1) for l in locs}),
                "z": [min(l[2] for l in locs), max(l[2] for l in locs)]}
    except Exception as exc:  # noqa: BLE001  report-only
        return {"source": os.path.basename(path), "error": str(exc)}


def set_fields(c, s, t):
    u = c.u
    under = s.get_editor_property("underpass")
    for k, v in t.items():
        if k == "fence_height_mode":
            v = getattr(u.InfinityFenceHeightMode, v)
        under.set_editor_property(k, v)
    s.modify()
    s.set_editor_property("underpass", under)
    back = read_written(s.get_editor_property("underpass"))
    bad = {k: (back[k], t[k]) for k in t if not same_val(back[k], t[k])}
    if bad:
        c.fail("READBACK|%s|%s" % (s.get_actor_label(), json.dumps(bad, default=str)))


def verify_build(c, s, label, before_snap, pred, intensity):
    """Instance-transform readback after a materialize, against the snapshot taken before any write."""
    after = snapshot(c, s)
    p = check_others(before_snap["others"], after["others"])
    plan = pred["plan"]
    if plan:
        rows = int(s.get_editor_property("underpass_fence_row_count"))
        top = float(s.get_editor_property("underpass_fence_stack_top_cm"))
        if rows != plan["rows"] or abs(top - plan["top_cm"]) > 0.01:
            p.append("C++ plan rows=%d top=%.2f, Python plan rows=%d top=%.2f" % (rows, top, plan["rows"], plan["top_cm"]))
        p += check_fence(before_snap["panels"], after["panels"], plan)
        with_overlay = sum(1 for e in after["panels"] if e["variant"] in pred["overlay_variants"])
        if len(after["overlays"]) != with_overlay:
            p.append("overlays %d, panels with an overlay %d" % (len(after["overlays"]), with_overlay))
    elif after["panels"] or before_snap["panels"]:
        p.append("fence panels %d -> %d with no fence built" % (len(before_snap["panels"]), len(after["panels"])))
    tp, moved_t = check_moved(before_snap["tubes"], after["tubes"], pred["tube_dz_cm"], "tubes")
    lp, moved_l = check_moved(before_snap["lights"], after["lights"], pred["tube_dz_cm"], "tube lights")
    p += tp + lp
    if pred["tube_dz_cm"] and before_snap["tubes"] and moved_t == 0:
        p.append("fence-top tubes did not move (want +%.2f)" % pred["tube_dz_cm"])
    off = [e["intensity"] for e in after["lights"] if not same_val(e["intensity"], intensity)]
    if off:
        p.append("%d tube lights not at %.3f (e.g. %.3f)" % (len(off), intensity, off[0]))
    if p:
        c.fail("LAYERS|%s|%s" % (label, p[:12]))
    return {"panels": len(after["panels"]), "overlays": len(after["overlays"]), "tubes": len(after["tubes"]),
            "tubes_moved": moved_t, "lights": len(after["lights"]), "lights_moved": moved_l,
            "rows": plan["rows"] if plan else 0}


def collect(c, structures, args):
    rows = {}
    for label, s in structures.items():
        b = read_before(c, s)
        pred = predict(b, args)
        rows[label] = {"before": b, "pred": pred, "clearance": clearance(b, pred, lamp_band(c, label))}
    return rows


# ============================================================================ phases
def phase_dry(c, args):
    u = c.u
    _, _, actors = guards(c, need_clean=False)
    before = census(u)
    structures = find_structures(c, actors, args["structures"])
    missing = fs_missing(c, list(structures.values())[0])
    rows = collect(c, structures, args)
    if census(u) != before:
        c.fail("DRY dirtied %s -> %s" % (before, census(u)))
    live = []
    if missing:
        live.append("BUILD_MISSING_FS|%s: build 2026-10-06_FS_fence_stack.patch first" % missing)
    if before != {"content": [], "maps": []}:
        live.append("editor dirty %s" % json.dumps(before))
    if os.path.exists(c.record):
        live.append("record exists (applied, not reverted)")
    stacked = [k for k, r in rows.items() if r["before"]["fence_height_mode"] == "STACK"]
    if stacked:
        live.append("ALREADY_STACK|%s" % stacked)
    for label, r in rows.items():
        b, pr, cl = r["before"], r["pred"], r["clearance"]
        c.log("FENCE750_DRY_ROW|run=%s|%s|fence=%s|panels=%d|mode=%s|height=%.1f|plan=%s|whole_alt=%s|old_top=%.2f"
              "|new_top=%.2f|tube_dz=%.2f|glow %.3f->%.3f|light %.1f->%.1f lm|lights=%d|fence_shadow=%s|clearance=%s"
              % (c.run, label, b["fence"], b["fence_panels"], b["fence_height_mode"], b["fence_height_cm"],
                 json.dumps(pr["plan"]), json.dumps(pr["whole_rows_alternative"]), pr["old_top_cm"], pr["new_top_cm"],
                 pr["tube_dz_cm"], b["tube_glow_level"], pr["targets"]["tube_glow_level"], b["tube_light_intensity"],
                 pr["targets"]["tube_light_intensity"], b["tube_light_count"], b["fence_cast_shadow"], json.dumps(cl)))
    cars = {}
    for p, car in CAR_PATHS.items():
        r = rows.get("Infinity Stage - Structure 0" + p[-1])
        if r:
            plan = r["pred"]["plan"]
            cars[p] = dict(car, fence_built=bool(plan),
                           lateral_gap_to_fence_cm=round(car["lateral_cm"] - r["clearance"]["fence_line_lateral_cm"], 1),
                           beam_meets="the ground row only (z %.0f < row %.1f)" % (car["z_cm"], plan["row_cm"])
                           if plan else "no fence in this Passage")
    report = {"run": c.run, "args": args, "rows": rows, "cars": cars, "live_blockers": live}
    path = os.path.join(c.here, "fence_stack_750_dry_%s.json" % c.run)
    write_json(c, path, report)
    ok = not live
    c.log("FENCE750_DRY_%s|run=%s|apply_ready=%d|structures=%d|fenced=%s|cars=%s|live_blockers=%s|mutated=0|report=%s"
          % ("OK" if ok else "REFUSED", c.run, int(ok), len(rows), [k for k, r in rows.items() if r["pred"]["plan"]],
             json.dumps(cars), live, path))
    return report


def _backup(c, tag):
    backup = os.path.join(c.repo, "Backups", "%s-%s" % (tag, c.run))
    os.makedirs(backup)
    c.past_backup = True
    shutil.copy2(c.umap, backup)
    shutil.copy2(c.record, backup)
    pre = _sha(c.umap)
    if _sha(os.path.join(backup, UMAP_REL[-1])) != pre:
        c.fail("BACKUP_MISMATCH")
    c.log("FENCE750_BACKUP_OK|run=%s|%s" % (c.run, backup))
    return backup, pre


def _save(c, world, pre_sha):
    u = c.u
    d = census(u)
    if d["content"] or d["maps"] != [WORLD]:
        c.fail("DIRTY_SCOPE|%s" % json.dumps(d))
    if not u.EditorLoadingAndSavingUtils.save_map(world, WORLD):
        c.fail("SAVE_FAILED")
    if census(u) != {"content": [], "maps": []}:
        c.fail("POST_SAVE_DIRTY|%s" % json.dumps(census(u)))
    if _sha(c.umap) == pre_sha:
        c.fail("UMAP_UNCHANGED_ON_DISK")


def phase_apply(c, args):
    _, world, actors = guards(c, need_clean=True)
    structures = find_structures(c, actors, args["structures"])
    missing = fs_missing(c, list(structures.values())[0])
    if missing:
        c.fail("BUILD_MISSING_FS|%s: build 2026-10-06_FS_fence_stack.patch first" % missing)
    if os.path.exists(c.record):
        c.fail("RECORD_EXISTS|REVERT first (or, for a failed APPLY, Don't-Save restart then archive the record)")
    rows = collect(c, structures, args)
    stacked = [k for k, r in rows.items() if r["before"]["fence_height_mode"] == "STACK"]
    if stacked:
        c.fail("ALREADY_STACK|%s" % stacked)
    snaps = {label: snapshot(c, s) for label, s in structures.items()}
    rec = {"run": c.run, "state": "applying", "written": datetime.datetime.now().isoformat(timespec="seconds"),
           "args": args, "before": {k: {f: r["before"][f] for f in WRITTEN} for k, r in rows.items()},
           "read": {k: r["before"] for k, r in rows.items()}, "pred": {k: r["pred"] for k, r in rows.items()},
           "snap": {k: {"panels": v["panels"], "overlays": v["overlays"], "tubes": v["tubes"], "lights": v["lights"]}
                    for k, v in snaps.items()}}
    write_json(c, c.record, rec, exclusive=True)
    backup, pre_sha = _backup(c, "PreFence750")
    built = {}
    for label, s in structures.items():
        pred = rows[label]["pred"]
        set_fields(c, s, pred["targets"])
        if not s.materialize_structure():
            c.fail("MATERIALIZE_FAILED|%s" % label)
        if not s.is_structure_current():
            c.fail("NOT_CURRENT|%s" % label)
        built[label] = verify_build(c, s, label, snaps[label], pred, pred["targets"]["tube_light_intensity"])
        c.log("FENCE750_BUILT|run=%s|%s|%s" % (c.run, label, json.dumps(built[label])))
    _save(c, world, pre_sha)
    back = {label: read_written(s.get_editor_property("underpass")) for label, s in structures.items()}
    bad = {label: back[label] for label in back
           if any(not same_val(back[label][k], rows[label]["pred"]["targets"][k]) for k in WRITTEN)}
    if bad:
        c.fail("SAVED_READBACK|%s" % json.dumps(bad))
    rec.update(state="applied", applied=datetime.datetime.now().isoformat(timespec="seconds"), backup=backup,
               after=back, built=built)
    write_json(c, c.record, rec)
    c.log("FENCE750_APPLY_OK|run=%s|structures=%d|built=%s|level_saved=1|dirty_after=0+0|backup=%s"
          % (c.run, len(built), json.dumps(built), backup))
    return rec


def phase_revert(c, args):
    _, world, actors = guards(c, need_clean=True)
    if not os.path.exists(c.record):
        c.fail("NO_RECORD")
    rec = json.load(open(c.record, encoding="utf-8"))
    if rec.get("state") != "applied":
        c.fail("RECORD_STATE|%s: an APPLY that did not save is undone by a Don't-Save restart, not REVERT" % rec.get("state"))
    structures = find_structures(c, actors, list(rec["before"]))
    missing = fs_missing(c, list(structures.values())[0])
    if missing:
        c.fail("BUILD_MISSING_FS|%s" % missing)
    for label, s in structures.items():
        live = read_written(s.get_editor_property("underpass"))
        if any(not same_val(live[k], rec["after"][label][k]) for k in WRITTEN):
            c.fail("NOT_APPLIED_STATE|%s|live %s vs applied %s" % (label, live, rec["after"][label]))
    live_snaps = {label: snapshot(c, s) for label, s in structures.items()}
    backup, pre_sha = _backup(c, "PreFence750Revert")
    for label, s in structures.items():
        b = rec["before"][label]
        set_fields(c, s, {k: b[k] for k in WRITTEN if b[k] is not None})
        if not s.materialize_structure():
            c.fail("MATERIALIZE_FAILED|%s" % label)
        if not s.is_structure_current():
            c.fail("NOT_CURRENT|%s" % label)
        after = snapshot(c, s)
        p = check_others(live_snaps[label]["others"], after["others"])
        old = rec["snap"][label]
        for what in ("panels", "overlays", "tubes", "lights"):
            p += check_others({what: old[what]}, {what: after[what]})
        kv = {xy_key(e): e["variant"] for e in old["panels"]}
        p += ["panel at %s variant %s -> %s" % (xy_key(e), kv.get(xy_key(e)), e["variant"])
              for e in after["panels"] if kv.get(xy_key(e)) != e["variant"]][:3]
        off = [e["intensity"] for e in after["lights"] if not same_val(e["intensity"], b["tube_light_intensity"])]
        if off:
            p.append("%d tube lights not back at %.3f" % (len(off), b["tube_light_intensity"]))
        if p:
            c.fail("NOT_RESTORED|%s|%s" % (label, p[:12]))
    _save(c, world, pre_sha)
    os.replace(c.record, c.record.replace(".json", ".reverted-%s.json" % c.run))
    c.log("FENCE750_REVERT_OK|run=%s|structures=%d|level_saved=1|dirty_after=0+0|backup=%s" % (c.run, len(structures), backup))
    return rec


def main(args=None):
    c = Ctx("DRY")
    if args is None:
        path = os.path.join(c.here, "fence_stack_750_args.json")
        args = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    a = dict(DEFAULTS)
    a.update(args)
    mode = str(a.get("mode", "DRY")).upper()
    c.mode = mode
    phases = {"DRY": phase_dry, "APPLY": phase_apply, "REVERT": phase_revert}
    if mode not in phases:
        c.fail("UNKNOWN_MODE|%s" % mode)
    if str(a["top_row"]).lower() not in ("cut", "whole"):
        c.fail("TOP_ROW|%s: cut or whole" % a["top_row"])
    if mode != "DRY" and a.get("confirm") != "%s %s" % (mode, CONFIRM_TAIL):
        c.fail("CONFIRM_MISSING|want '%s %s'" % (mode, CONFIRM_TAIL))
    c.log("FENCE750_START|run=%s|mode=%s|top_row=%s" % (c.run, mode, a["top_row"]))
    try:
        return phases[mode](c, a)
    except Fence750Error:
        raise
    except Exception as exc:  # an API surprise still leaves a run-stamped failure marker
        c.fail("UNEXPECTED|%s: %s" % (type(exc).__name__, exc))


if __name__ == "__fence_stack_750_runner__":
    main()
