"""Fixtures FOLLOW / SCALE / RELOCATE, one passage per run.
Offline: COUNT (python fixtures_follow.py [args.json]). Editor: DRY / APPLY / REVERT via fixtures_follow_run.py.

Gary 7 Oct: (1) bare bulbs OUT of the cans, on the ground and hanging, for reflections; (2) bulbs and parcans ~3x;
(3) he aims the lights by hand (as P01 on 6 Oct) and the cans must follow. Plus (conductor relay): remove every
PRACTICAL_GLIMMER light + GLIMMER_BODY + GLIMMER_CAP and put a bare bulb in each spot.

OPS (args "op")
  FOLLOW    Housings are a pure function of the Show (fixtures_common.py header, cpp:142-180, 1920-1955), so there is
            no housing data to author: FOLLOW re-fits the Structure (materialize_structure) and PROVES each housing
            instance now equals the C++ formula applied to its light's CURRENT Show transform (8-corner gap <= 0.5 cm,
            same index order as GatherFixturePlacements), IsStructureCurrent true, Show rows byte-identical (FOLLOW
            never writes a row). DRY lists every stale housing with its aim error in degrees. No stale housing ->
            FIXFOLLOW_FOLLOW_NOOP (never the OK marker). REVERT is refused by design (nothing authored; restore the
            backup or re-aim the light).
  SCALE     Housings: Structure Fixtures.BodySizeCm = lantern bounds x (current scale x housing_factor), mesh and
            material untouched (the C++ fits by bounds, so the lens offset scales with it: Fresnel -2.4/-6.4 cm at 1x
            -> -7.1/-19.2 cm at 3x). Bulbs: every Meshy bulb PROP row (SM_Bulb_* / SM_FX_Bulb_*) scale x bulb_factor
            ABOUT ITS GLASS CENTRE (the glass stays where it is). Refuses when the live scale is not the expected one
            (no double apply) and when a RELOCATE record is active (scaling a relocated bulb would lift it off the
            floor and break its cord). DRY reports housings that would interpenetrate their station's crossbeam/rails.
  RELOCATE  Moves the dim/dead Meshy bulbs out of the cans (fixtures_common.relocate_plan): HANG (glass 2.2-6.5 m, under
            the bay's crossbeam, a cord up to the crossbeam underside) or GROUND (lying / standing on the floor read
            live from the floor actors' bounds), deterministic per GUID; the paired dim light is DISABLED (ground) or
            re-kinded to the cord PROP (hang, when there is no spare *_CAP row) -> its housing disappears (only enabled
            LIGHT rows get one, cpp:162-166). WORKING practicals (> working_lumens, P02 PRACTICAL_R x12 at 800 lm, one
            P01 at 300 lm) stay in their lanterns. Glimmer: *PRACTICAL_GLIMMER_BODY -> a bare bulb at the glimmer
            light's spot, the glimmer LIGHT row becomes its cord (HANG_AT_SPOT) or is disabled (GROUND_UNDER_SPOT);
            *GLIMMER*_CAP -> disabled. Cord mesh = a create-only derived copy of the Structure's own hanging-line mesh
             with its line material on slot 0 (meshy_swap._ensure_derived), so cords match the housing lines. Its
             glow_mode makes each relocated body an emissive filament with an optional transient dim point light;
             cord_sway_mode links hanging bodies to their cord and enables continuous GUID-phased sine sway in game.

MODES  COUNT offline (snapshot rows, see fixtures_common.snapshot_passage); DRY read-only, prints plan_sha256;
       APPLY needs confirm "APPLY FIXFOLLOW <OP> P0N" + plan_sha256 + ack_records; REVERT confirm "REVERT FIXFOLLOW <OP>
       P0N". Record FIRST (exclusive), Backups/PreFixFollow<Op>P0N-<run>, in-memory rollback on any scope failure,
       materialize passage + structure, verify spawned actors / ISM, narrow save (Show + level only), read back.
Markers FIXFOLLOW_<OP>_<MODE>_OK|run=..; FIXFOLLOW_FOLLOW_NOOP|run=..; any stop FIXFOLLOW_STOPPED|run=..|..

Proof tiers: see fixtures_common.py header. Additionally:
* declaration-proven: meshy_swap.py helpers reused unchanged (they are live-proven by its APPLY runs 20261007-0825..
  0829: _find_structure, _structure_state, _write_structure, _check_structure, _runtime_plain, _export_hash,
  _ensure_derived, _attachment_actor_index, check_context); _set_pair_attachments / _backup / _save_narrow from
  lighting_looks_apply.py:1292, 1616, 1657; _materialize_passage lighting_scores_apply.py:2879-2896.
* inferred (each is gated: a wrong guess stops the run before any write, or the read-back fails it):
  - python names: structure.gather_stations() returns (ok, stations, error) or (stations, error) (handled as in
    Girders_20261007/girders_v3_apply.py:550); FInfinityStructureStation.cue_guid / station_world; cue.wing_pair
    .occurrence_offset; structure "grid_half_width_cm" (read live by fence_stack_750.py:439) and "gridiron" struct
    height_cm / beam_depth_cm / beam_width_cm; fixtures line_mesh / line_material (read by meshy_swap FIXTURE_OTHER_FIELDS);
  - attachment "kind" is writable from Python (EditAnywhere BlueprintReadWrite, InfinityStageTypes.h:445-446; set on a
    NEW struct by lighting_looks_apply._make_prop:1559 -- never yet on an existing row; the scope read-back proves it);
  - a re-kinded LIGHT->PROP row with a mesh spawns a StaticMeshActor (the prop path, InfinityStagePassageActor.cpp:
    978-1001) and its leftover Lighting struct is ignored; verified after materialize by the spawned-actor check.
"""
from __future__ import annotations

import ast
import copy
import datetime
import hashlib
import json
import os
import runpy
import sys
import types

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # offline COUNT / harness
    unreal = None

HERE = os.path.dirname(os.path.abspath(__file__))
CONDUCTOR = os.path.dirname(HERE)
SAVED = os.path.dirname(CONDUCTOR)
COMMON_PATH = os.path.join(HERE, "fixtures_common.py")
MESHY_SWAP_PATH = os.path.join(CONDUCTOR, "MeshyFixtures_20261007", "meshy_swap.py")
MARK = "FIXFOLLOW"
OPS = ("FOLLOW", "SCALE", "RELOCATE")
MODES = ("COUNT", "DRY", "APPLY", "REVERT")
PLACE_TOL_CM = 0.5
EXTRA = {"op": None, "passage": None, "plan_sha256": None, "expected_rows": None, "ack_records": [], "allow_dirty": [],
         "floor_label_regex": r"Floor"}
P4_BODY_DEFAULTS = (
    ("emit_point_light", False), ("point_light_lumens", 24.0),
    ("point_light_attenuation_radius_cm", 450.0), ("point_light_source_radius_cm", 8.0),
    ("point_light_soft_source_radius_cm", 18.0), ("point_light_temperature_kelvin", 2200.0),
    ("swing_on_cord", False), ("cord_attachment_guid", "0" * 32),
    ("swing_yaw_amplitude_degrees", 2.5), ("swing_pitch_amplitude_degrees", 1.5),
    ("swing_period_seconds", 7.0), ("sway_seed", 0),
)
GLOW_BODY_FIELDS = ("follow_light", "light_attachment_guid", "intensity_parameter", "full_intensity", "flicker",
                    "seed", "slight_depth", "flicker_rate_hz", "flicker_also_drives_light")

F = None    # fixtures_common namespace, loaded fresh per run; never a UE object
MS = None   # meshy_swap definitions (runtime helpers), loaded fresh per run


def load_common():
    return types.SimpleNamespace(**runpy.run_path(COMMON_PATH, run_name="_fixtures_common"))


def load_meshy_swap(path=MESHY_SWAP_PATH):
    """meshy_swap.py's definitions WITHOUT its two trailing guards (`if __name__ == ...: count_cli()` and
    `if unreal is not None: main()`); refuses any other top-level statement that could run code."""
    with open(path, "rb") as handle:
        raw = handle.read()
    tree = ast.parse(raw.decode("utf-8"), filename=path)
    body = []
    for node in tree.body:
        if isinstance(node, ast.If):
            text = ast.unparse(node.test)
            calls = [ast.unparse(n.value.func) for n in node.body if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)]
            if text in ("unreal is not None", "__name__ == '__main__' and unreal is None") and calls in (["main"], ["count_cli"]) \
                    and len(node.body) == 1:
                continue
            raise RuntimeError("MESHY_SWAP_TOP_LEVEL_IF|line=%d|%s" % (node.lineno, text))
        if isinstance(node, (ast.Expr,)) and not (isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
            raise RuntimeError("MESHY_SWAP_TOP_LEVEL_EXPR|line=%d" % node.lineno)
        body.append(node)
    tree.body = body
    module = types.ModuleType("_meshy_swap_for_fixfollow")
    module.__file__ = path
    exec(compile(tree, path, "exec"), module.__dict__)  # noqa: S102 - reviewed project file
    module.C = module.load_common()
    module.SOURCE_SHA256 = hashlib.sha256(raw).hexdigest()
    for name in ("_find_structure", "_structure_state", "_write_structure", "_check_structure", "_runtime_plain",
                 "_all_rows", "_export_hash", "_ensure_derived", "_attachment_actor_index", "check_context", "_ctx_facts",
                 "load_modules", "scan_foreign_text"):
        if not callable(getattr(module, name, None)):
            raise RuntimeError("MESHY_SWAP_API_DRIFT|" + name)
    return module


def require(condition, message):
    F.require(condition, message)


def record_path(op, passage):
    return os.path.join(HERE, "fixfollow_%s_record_%s.json" % (op.lower(), passage))


def report_path(op, mode, passage, run):
    return os.path.join(HERE, "fixfollow_%s_report_%s_%s_%s.json" % (op.lower(), passage, mode, run))


def defaults_for(op):
    if op == "SCALE":
        return copy.deepcopy(F.SCALE_DEFAULTS)
    if op == "RELOCATE":
        return copy.deepcopy(F.RELOCATE_DEFAULTS)
    return {}


def check_args(raw):
    raw = dict(raw or {})
    op = str(raw.get("op", "")).upper()
    require(op in OPS, "OP_INVALID|%s" % raw.get("op"))
    out = defaults_for(op)
    out.update(copy.deepcopy(EXTRA))
    allowed = set(out) | {"mode", "confirm"}
    unknown = sorted(set(raw) - allowed)
    require(not unknown, "ARGS_UNKNOWN|%s" % unknown)
    for k, v in raw.items():
        if k == "grid":
            out["grid"].update(v)
        else:
            out[k] = copy.deepcopy(v)
    out["op"] = op
    out["mode"] = str(raw.get("mode", "DRY")).upper()
    require(out["mode"] in MODES, "MODE_INVALID|%s" % out["mode"])
    passage = str(out["passage"] or "").upper()
    require(passage in F.PASSAGES or (out["mode"] == "COUNT" and passage in ("", "ALL")), "PASSAGE_INVALID|%s" % out["passage"])
    out["passage"] = passage if passage in F.PASSAGES else "ALL"
    if out["mode"] in ("APPLY", "REVERT"):
        want = "%s %s %s %s" % (out["mode"], MARK, op, passage)
        require(raw.get("confirm") == want, "CONFIRM_MISSING|need='%s'" % want)
    if out["mode"] == "APPLY":
        require(isinstance(out["plan_sha256"], str) and len(out["plan_sha256"]) == 64, "APPLY_NEEDS_PLAN_SHA256")
    if op == "FOLLOW":
        require(out["mode"] != "REVERT", "FOLLOW_REVERT_NOT_APPLICABLE|FOLLOW authors nothing: housings are derived from "
                "the lights. Re-aim the light (or restore the Show backup) and run FOLLOW again.")
    if op == "SCALE":
        for k in ("housing_factor", "bulb_factor"):
            require(isinstance(out[k], (int, float)) and 0.25 <= float(out[k]) <= 4.0, k.upper() + "_RANGE")
    if op == "RELOCATE":
        require(out["paired_light"] in ("DISABLE", "KEEP"), "PAIRED_LIGHT_INVALID")
        require(out["glimmer"] in ("HANG_AT_SPOT", "GROUND_UNDER_SPOT", "OFF"), "GLIMMER_MODE_INVALID")
        require(out["glimmer_mesh"] in ("PASSAGE_DERIVED", "FIXTURE"), "GLIMMER_MESH_INVALID")
        require(out["glow_mode"] in ("FILAMENT_AND_POINT", "EMISSIVE_ONLY", "OFF"), "GLOW_MODE_INVALID")
        require(out["glow_flicker"] in ("STABLE", "SLIGHT", "FAIL"), "GLOW_FLICKER_INVALID")
        require(out["cord_sway_mode"] in ("DETERMINISTIC_SINE", "STATIC"), "CORD_SWAY_MODE_INVALID")
        require(0.0 <= float(out["hang_fraction"]) <= 1.0, "HANG_FRACTION_RANGE")
        require(0.0 <= float(out["point_light_lumens"]) <= 250.0, "POINT_LIGHT_LUMENS_RANGE")
        require(0.25 <= float(out["sway_period_seconds"]), "SWAY_PERIOD_RANGE")
        require(0.0 <= float(out["sway_yaw_amplitude_degrees"]) <= 20.0, "SWAY_YAW_RANGE")
        require(0.0 <= float(out["sway_pitch_amplitude_degrees"]) <= 20.0, "SWAY_PITCH_RANGE")
    for k in ("ack_records", "allow_dirty"):
        require(isinstance(out[k], list) and all(isinstance(v, str) for v in out[k]), k.upper() + "_INVALID")
    return out


def plan_opts(args):
    return {k: args[k] for k in defaults_for(args["op"])}


# ---------------------------------------------------------------------------------------------------------------
# COUNT (offline)
# ---------------------------------------------------------------------------------------------------------------
def count_offline(args):
    table = F.M.load_fixture_table(check_files=False)
    passages = F.PASSAGES if args["passage"] == "ALL" else (args["passage"],)
    out = {"op": args["op"], "inferred": "offline snapshot rows (fixtures_common.snapshot_passage); pair frame taken as "
           "the world frame; grid half width %s; the live DRY re-reads everything" % F.RELOCATE_DEFAULTS["grid"]["half_width_cm"],
           "passages": {}}
    for p in passages:
        cues, meta = F.snapshot_passage(p)
        h = meta["meshy_housing"]
        row = {"cues": len(cues), "snapshot": {"meshy_run": meta["meshy_run"], "scores_run": meta["scores_run"]}}
        if args["op"] in ("FOLLOW", "SCALE"):
            fixture = table[h["lantern"]]
            ident = F.xf([0, 0, 0], [0, 0, 0, 1])
            placements = F.follow_placements(cues, {c["guid"]: ident for c in cues}, {c["guid"]: [0.0, 1.0, 0.0] for c in cues})
            grid = dict(F.RELOCATE_DEFAULTS["grid"])
            boxes = {c["guid"]: F.grid_boxes(ident, grid) + [
                {"name": "rails_long", "box": F.obb([0.0, s * grid["half_width_cm"], grid["height_cm"] + grid["beam_depth_cm"]],
                                                     [0, 0, 0, 1], [1500.0, grid["beam_width_cm"] / 2, grid["beam_depth_cm"] / 2])}
                for s in (-1.0, 1.0)] for c in cues}
            sizes = {"now": h["body_size_cm"], "x3": F.M.housing_size(fixture, 3.0)}
            row["housed_lights"] = len(placements)
            row["girder_hits"] = {k: len(F.girder_report(placements, boxes, fixture["bounds_min"], fixture["bounds_max"], v))
                                  for k, v in sizes.items()}
            if args["op"] == "SCALE":
                plan = F.scale_plan(p, cues, table, meta["derived_index"], {"lantern": h["lantern"], "body_size_cm":
                                                                            h["body_size_cm"]}, plan_opts(args))
                row.update({"counts": plan["counts"], "housing": plan["housing"]})
        else:
            plan = F.relocate_plan(p, cues, table, meta["derived_index"], plan_opts(args))
            row.update({"counts": plan["counts"], "glimmers": plan["glimmers"], "working": plan["working_practicals"]})
        out["passages"][p] = row
    path = os.path.join(HERE, "fixfollow_%s_counts.json" % args["op"].lower())
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(out, handle, indent=1, sort_keys=True)
    return out, path


# ---------------------------------------------------------------------------------------------------------------
# Unreal runtime (never executed offline). No UE object in a global; everything inside functions.
# ---------------------------------------------------------------------------------------------------------------
def _log(text):
    unreal.log(text)


def _v(v):
    return [float(v.x), float(v.y), float(v.z)]


def _t(transform):
    r = transform.rotation
    return F.xf(_v(transform.translation), [float(r.x), float(r.y), float(r.z), float(r.w)], _v(transform.scale3d))


def _parse_guid(tool, text):
    res = unreal.GuidLibrary.parse_string_to_guid(str(text))
    guid, ok = (res if isinstance(res, tuple) else (res, True))
    require(ok and tool._guid_text(guid) == str(text), "GUID_PARSE|" + str(text))
    return guid


def _runtime_plain(scores, tool, show):
    """Meshy runtime rows plus the P4-only bulb practical/sway fields. Kept local so older score tools do not start
    authoring these defaults on unrelated rows."""
    plain = MS._runtime_plain(scores, tool, show)
    for cue_plain, cue in zip(plain, show.get_editor_property("cues")):
        attachments = tool._pair_attachments(cue)
        require(len(cue_plain["attachments"]) == len(attachments), "RUNTIME_ROWS_COUNT")
        for row, attachment in zip(cue_plain["attachments"], attachments):
            body_struct = attachment.get_editor_property("body")
            body = row.setdefault("ext", {}).setdefault("body", {})
            for name, default in P4_BODY_DEFAULTS:
                value = body_struct.get_editor_property(name)
                if name == "cord_attachment_guid":
                    body[name] = tool._guid_text(value)
                elif isinstance(default, bool):
                    body[name] = bool(value)
                elif isinstance(default, int):
                    body[name] = int(value)
                else:
                    body[name] = float(value)
    return plain


def _require_body_readback(want_all, got_all, side):
    """The shared row comparator intentionally ignores ``ext``. Prove every legacy glow and P4 practical/sway Body
    field separately, for all rows, so both intended writes and out-of-scope extension drift are visible."""
    bad = []
    fields = GLOW_BODY_FIELDS + tuple(name for name, unused in P4_BODY_DEFAULTS)
    for cue_guid, want_rows in want_all.items():
        got_rows = {row["guid"]: row for row in got_all.get(cue_guid, [])}
        for want in want_rows:
            got = got_rows.get(want["guid"])
            wb = ((want.get("ext") or {}).get("body") or {})
            gb = (((got or {}).get("ext") or {}).get("body") or {})
            for name in fields:
                if name not in wb:
                    continue
                a, b = wb[name], gb.get(name)
                if isinstance(a, (bool, str)):
                    ok = a == b
                elif isinstance(a, (int, float)):
                    ok = b is not None and abs(float(a) - float(b)) <= 1.0e-5 * max(1.0, abs(float(a)))
                else:
                    ok = a == b
                if not ok:
                    bad.append({"cue": cue_guid, "guid": want["guid"], "field": name, "want": a, "got": b})
    require(not bad, "BODY_READBACK|side=%s|count=%d|%s" % (side, len(bad), F.canonical(bad)[:3000]))


def _stations(structure, tool):
    res = structure.gather_stations()
    if isinstance(res, tuple):
        oks = [x for x in res if isinstance(x, bool)]
        require(not oks or oks[0], "GATHER_STATIONS_FAILED|%s" % (res,))
        lists = [x for x in res if isinstance(x, (list, unreal.Array))]
        require(len(lists) == 1, "GATHER_STATIONS_SHAPE|%s" % type(res))
        stations = list(lists[0])
    else:
        stations = list(res or [])
    out = []
    for st in stations:
        out.append({"cue_guid": tool._guid_text(st.get_editor_property("cue_guid")),
                    "station_world": _t(st.get_editor_property("station_world"))})
    require(out, "NO_STATIONS")
    return out


def _pair_worlds(show, tool, stations):
    """{cue_guid: pair world} = OccurrenceOffset * StationWorld (cpp:159), plus the station across axis."""
    offsets = {}
    for cue in show.get_editor_property("cues"):
        g = tool._guid_text(cue.get_editor_property("cue_guid"))
        offsets[g] = _t(cue.get_editor_property("wing_pair").get_editor_property("occurrence_offset"))
    worlds, acrosses, order = {}, {}, []
    for st in stations:
        g = st["cue_guid"]
        require(g in offsets, "STATION_CUE_NOT_IN_SHOW|" + g)
        worlds[g] = F.xf_compose(offsets[g], st["station_world"])
        acrosses[g] = F.axes(st["station_world"]["rotation_xyzw"])[1]
        order.append(g)
    return worlds, acrosses, order


def _grid(structure):
    g = structure.get_editor_property("gridiron")
    return {"height_cm": float(g.get_editor_property("height_cm")),
            "beam_depth_cm": float(g.get_editor_property("beam_depth_cm")),
            "beam_width_cm": float(g.get_editor_property("beam_width_cm")),
            "half_width_cm": float(structure.get_editor_property("grid_half_width_cm")),
            "enabled": bool(g.get_editor_property("enabled"))}


def _ism_transforms(structure):
    comp = MS._fixture_component(structure)
    if comp is None:
        return []
    return [_t(comp.get_instance_transform(i, True)) for i in range(int(comp.get_instance_count()))]


def _body_mesh_bounds(structure):
    mesh = structure.get_editor_property("fixtures").get_editor_property("body_mesh")
    if hasattr(mesh, "load_synchronous"):
        mesh = mesh.load_synchronous()
    require(mesh is not None, "BODY_MESH_NONE")
    box = mesh.get_bounding_box()
    return (_v(box.min), _v(box.max)), [float(v) for v in _v(structure.get_editor_property("fixtures").get_editor_property("body_size_cm"))]


def _follow_state(show, tool, structure, all_cues):
    stations = _stations(structure, tool)
    worlds, acrosses, order = _pair_worlds(show, tool, stations)
    by_guid = {c["guid"]: c for c in all_cues}
    cues_in_order = [by_guid[g] for g in order if g in by_guid]
    placements = F.follow_placements(cues_in_order, worlds, acrosses)
    bounds, size = _body_mesh_bounds(structure)
    plan = F.follow_plan(placements, _ism_transforms(structure), bounds, size, PLACE_TOL_CM)
    return stations, worlds, placements, bounds, size, plan


def _write_rows_full(tool, show, target, values):
    """As meshy_swap._write_rows plus KIND (RELOCATE re-kinds a retired light into its cord). values {guid: row}."""
    cues = list(show.get_editor_property("cues"))
    hits = [i for i, c in enumerate(cues) if tool._guid_text(c.get_editor_property("cue_guid")) == target["cue_guid"]]
    require(len(hits) == 1, "CUE_RESOLVE|%s|%d" % (target["cue_guid"], len(hits)))
    index = hits[0]
    require(str(cues[index].get_editor_property("label")) == target["cue_label"], "CUE_LABEL_DRIFT|" + target["cue_guid"])
    original = tool._pair_attachments(cues[index])
    attachments = tool._pair_attachments(cues[index])
    seen = 0
    for attachment in attachments:
        guid = tool._guid_text(attachment.get_editor_property("attachment_guid"))
        if guid not in values:
            continue
        row = values[guid]
        seen += 1
        attachment.set_editor_property("kind", tool._enum_member(unreal.InfinityAttachmentKind, F.enum_name(row["kind"])))
        mesh = F.asset_id(row.get("mesh"))
        attachment.set_editor_property("mesh", unreal.EditorAssetLibrary.load_asset(mesh) if mesh else None)
        t = row["relative_transform"]
        x = attachment.get_editor_property("relative_transform")
        x.set_editor_property("translation", unreal.Vector(*[float(v) for v in t["location"]]))
        x.set_editor_property("rotation", unreal.Quat(*[float(v) for v in t["rotation_xyzw"]]))
        x.set_editor_property("scale3d", unreal.Vector(*[float(v) for v in t["scale"]]))
        attachment.set_editor_property("relative_transform", x)
        attachment.set_editor_property("enabled", bool(row["enabled"]))
        body_values = ((row.get("ext") or {}).get("body") or {})
        if "emit_point_light" in body_values:
            body = attachment.get_editor_property("body")
            for name in GLOW_BODY_FIELDS:
                value = body_values[name]
                if name == "light_attachment_guid":
                    value = _parse_guid(tool, value)
                elif name == "flicker":
                    value = tool._enum_member(unreal.InfinityBulbBodyFlicker, F.enum_name(value))
                elif name == "intensity_parameter":
                    value = unreal.Name(value)
                body.set_editor_property(name, value)
            for name, unused in P4_BODY_DEFAULTS:
                value = body_values[name]
                if name == "cord_attachment_guid":
                    value = _parse_guid(tool, value)
                body.set_editor_property(name, value)
            attachment.set_editor_property("body", body)
    require(seen == len(values), "ROW_GUIDS_MISSING|%s|%d/%d" % (target["cue_label"], seen, len(values)))
    tool._set_pair_attachments(show, index, attachments)
    return index, original


def _floor_tops(regex):
    """[(xmin, xmax, ymin, ymax, ztop, label)] of level actors whose label matches regex (AABBs: plain bounds reads)."""
    import re as _re
    pat = _re.compile(regex)
    out = []
    for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        label = a.get_actor_label()
        if not pat.search(label):
            continue
        origin, extent = a.get_actor_bounds(False)
        o, e = _v(origin), _v(extent)
        out.append((o[0] - e[0], o[0] + e[0], o[1] - e[1], o[1] + e[1], o[2] + e[2], label))
    return out


def _floor_z_by_spot(plan, worlds, floors):
    """For each GROUND bulb: the highest floor top under its world XY within 150 cm of the pair origin's height,
    expressed in pair-frame z (pair frames must be upright: refuses otherwise). Missing -> not in the map + listed."""
    out, missing = {}, []
    for t in plan["targets"]:
        w = worlds[t["cue_guid"]]
        up = F.axes(w["rotation_xyzw"])[2]
        for c in t["changes"]:
            if not c["what"].startswith(("BULB_GROUND", "GLIMMER_TO_BULB_GROUND")):
                continue
            require(up[2] > 0.999, "PAIR_FRAME_NOT_UPRIGHT|%s" % t["cue_label"])
            p = F.xf_point(w, [c["glass"][0], c["glass"][1], 0.0])
            tops = [f[4] for f in floors if f[0] <= p[0] <= f[1] and f[2] <= p[1] <= f[3] and abs(f[4] - p[2]) <= 150.0]
            if tops:
                out[c["guid"]] = round(max(tops) - p[2], 3)
            else:
                missing.append({"cue": t["cue_label"], "label": c["label"], "world_xy": [round(p[0], 1), round(p[1], 1)]})
    return out, missing


def _cord_mesh(structure):
    """The Structure's hanging-line mesh, with its line material baked onto slot 0 of a create-only derived copy when a
    line material is set (a Prop row carries no material, InfinityStageTypes.h:458-459)."""
    fx = structure.get_editor_property("fixtures")
    mesh = fx.get_editor_property("line_mesh")
    mat = fx.get_editor_property("line_material")
    mesh = mesh.load_synchronous() if hasattr(mesh, "load_synchronous") else mesh
    mat = mat.load_synchronous() if hasattr(mat, "load_synchronous") else mat
    require(mesh is not None, "LINE_MESH_NONE")
    src = F.asset_id(mesh.get_path_name())
    box = mesh.get_bounding_box()
    bounds = (_v(box.min), _v(box.max))
    if mat is None:
        return src, bounds, {}
    slot0 = F.asset_id(mat.get_path_name())
    key = F.canonical({"cord": src, "slot0": slot0})
    path = "%s/SM_FX_Cord_%s" % (F.M.DERIVED_DIR, hashlib.sha1(key.encode()).hexdigest()[:8])
    return path, bounds, {path: {"variant": "CORD", "source": src, "slot0": slot0}}


def _verify_rows_spawned(plan, worlds, tool):
    """After materialize: each changed row that is an enabled PROP has exactly one actor whose world location equals
    pair_world * row (0.5 cm) and whose mesh is the planned mesh; each row now disabled or no longer a LIGHT has no
    light actor."""
    index = MS._attachment_actor_index()
    bad, checked = [], 0
    for t in plan["targets"]:
        w = worlds[t["cue_guid"]]
        for c in t["changes"]:
            row = c["after"]
            actors = index.get("%s|%s" % (t["cue_guid"], c["guid"]), [])
            if not row["enabled"]:
                if actors:
                    bad.append({"label": c["label"], "problem": "DISABLED_ROW_HAS_ACTOR_%d" % len(actors)})
                continue
            if F.enum_name(row["kind"]) != "PROP":
                continue
            if len(actors) != 1:
                bad.append({"label": c["label"], "problem": "ACTOR_COUNT_%d" % len(actors)})
                continue
            a = actors[0]
            if a.get_class().get_name() != "StaticMeshActor":
                bad.append({"label": c["label"], "problem": "NOT_A_MESH_ACTOR|%s" % a.get_class().get_name()})
                continue
            want = F.xf_point(w, row["relative_transform"]["location"])
            got = _v(a.get_actor_location())
            comp = a.get_editor_property("static_mesh_component")
            mesh = F.asset_id(comp.get_editor_property("static_mesh").get_path_name()) if comp else None
            if F.dist(want, got) > PLACE_TOL_CM or mesh != F.asset_id(row["mesh"]):
                bad.append({"label": c["label"], "problem": "PLACE_OR_MESH", "want": want, "got": got, "mesh": mesh})
                continue
            checked += 1
    require(not bad, "SPAWNED_ROWS|%s" % F.canonical(bad)[:2500])
    return checked


def _housings_removed(plan, before_rows):
    """Enabled STATION LIGHT rows the plan turns off or re-kinds: each loses its housing (cpp:162-166)."""
    n = 0
    rows = {r["guid"]: r for rs in before_rows.values() for r in rs}
    for t in plan["targets"]:
        for c in t["changes"]:
            b = rows[c["guid"]]
            was = F.is_kind(b, "LIGHT") and b["enabled"] and F.is_station(b)
            now = F.enum_name(c["after"]["kind"]) == "LIGHT" and c["after"]["enabled"] and F.is_station(c["after"])
            n += was and not now
    return n


def _foreign(scores, roots, guids, rpath, structure_label):
    hits = scores.scan_foreign_records(roots, guids, exclude=[rpath])
    hits += MS.scan_foreign_text(roots, [structure_label], exclude=[rpath])
    return hits


def _finish(report, op, mode, passage, run, extra):
    report.update({"ok": True})
    path = report_path(op, mode, passage, run)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1, sort_keys=True, default=str)
    _log("%s_%s_%s_OK|run=%s|passage=%s|%s|report=%s" % (MARK, op, mode, run, passage, extra, path))
    return report


def _run(args):
    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    op, mode, passage = args["op"], args["mode"], args["passage"]
    names = MS.passage_names(passage)
    rpath = record_path(op, passage)
    report = {"ok": False, "op": op, "mode": mode, "run": run, "passage": passage, "args": args, "saved": False}
    tool = None
    try:
        require(mode != "COUNT", "COUNT_IS_OFFLINE_ONLY")
        scores, tool = MS.load_modules()
        ctx = MS._ctx_facts(tool)
        report["context"] = ctx
        MS.check_context(ctx, mode, args["allow_dirty"], tool.SHOW_PATH, tool.EXPECTED_WORLD)
        census_before = ctx["census"]
        show = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
        require(show is not None, "SHOW_ASSET_MISSING")
        structure = MS._find_structure(show, names)
        table = F.M.load_fixture_table(check_files=False)
        roots = [os.path.join(SAVED, n) for n in sorted(os.listdir(SAVED)) if n.startswith("Codex")]
        all_cues = _runtime_plain(scores, tool, show)
        before_all = MS._all_rows(all_cues)
        passage_actor = structure.get_editor_property("passage")
        bays = {tool._guid_text(g) for g in show.get_wing_pair_cue_guids_in_passage(passage_actor.get_editor_property("passage_guid"))}
        cues = [c for c in all_cues if c["guid"] in bays]
        require(cues, "NO_PASSAGE_CUES|" + passage)

        # ---------------------------------------------------------------- FOLLOW
        if op == "FOLLOW":
            stations, worlds, placements, bounds, size, fplan = _follow_state(show, tool, structure, all_cues)
            current = bool(structure.is_structure_current())
            fplan.update({"structure_current": current, "body_size_cm": size})
            sha = F.plan_sha({"passage": passage, "lights": [(r["guid"], r["predicted"]) for r in fplan["lights"]],
                              "ism_count": fplan["ism_count"]})
            report.update({"plan": fplan, "plan_sha256": sha})
            if mode == "DRY":
                require(tool._dirty_census() == census_before, "DRY_CENSUS_CHANGED")
                worst = sorted((r for r in fplan["lights"] if r.get("stale")), key=lambda r: -r["aim_error_deg"])[:8]
                return _finish(report, op, mode, passage, run,
                               "plan_sha256=%s|housed=%d|ism=%s|stale=%s|current=%s|worst=%s|mutated=0"
                               % (sha, fplan["count"], fplan["ism_count"], fplan["stale"], current,
                                  F.canonical([(r["label"], r["aim_error_deg"]) for r in worst])))
            require(sha == args["plan_sha256"], "PLAN_SHA_MISMATCH|live=%s|args=%s" % (sha, args["plan_sha256"]))
            if current and fplan["stale"] == 0 and fplan["count_matches"]:
                _log("%s_FOLLOW_NOOP|run=%s|passage=%s|housed=%d|stale=0|current=1|nothing written"
                     % (MARK, run, passage, fplan["count"]))
                report.update({"ok": True, "noop": True})
                return report
            require(not os.path.exists(rpath), "ACTIVE_RECORD_EXISTS|" + rpath)
            rows_hash = F.sha(before_all)
            backup = tool._backup("PreFixFollowFollow%s-" % passage, run)
            record = {"schema_version": 1, "status": "prepared", "op": op, "run": run, "passage": passage, "backup": backup,
                      "plan_sha256": sha, "rows_hash": rows_hash, "structure_before": MS._structure_state(tool, structure),
                      "stale_before": fplan["stale"], "current_before": current}
            tool._write_json(rpath, record, exclusive=True)
            require(bool(structure.materialize_structure()), "STRUCTURE_REFIT_FAILED")
            _, _, _, _, _, after = _follow_state(show, tool, structure, _runtime_plain(scores, tool, show))
            require(after["count_matches"], "HOUSING_COUNT|placements=%d|ism=%s" % (after["count"], after["ism_count"]))
            require(after["stale"] == 0, "HOUSINGS_STILL_STALE|%d" % after["stale"])
            require(bool(structure.is_structure_current()), "STRUCTURE_NOT_CURRENT_AFTER_REFIT")
            require(F.sha(MS._all_rows(_runtime_plain(scores, tool, show))) == rows_hash, "FOLLOW_CHANGED_SHOW_ROWS")
            tool._save_narrow()
            report["saved"] = True
            _, _, _, _, _, rb = _follow_state(show, tool, structure, _runtime_plain(scores, tool, show))
            require(rb["stale"] == 0 and rb["count_matches"], "READBACK_STALE|%s" % rb["stale"])
            record.update({"status": "saved_readback_verified", "structure_after": MS._structure_state(tool, structure),
                           "housings_verified": rb["count"]})
            tool._write_json(rpath, record)
            os.rename(rpath, rpath + ".done-" + run)   # FOLLOW leaves no active record: nothing to revert
            report.update({"backup": backup, "record": rpath + ".done-" + run})
            return _finish(report, op, mode, passage, run, "refit=1|housings=%d|was_stale=%d|show_saved=1|level_saved=1|readback=1"
                           % (rb["count"], fplan["stale"]))

        # ---------------------------------------------------------------- SCALE / RELOCATE plans
        derived_index = {}
        for p in F.PASSAGES:
            rp = os.path.join(F.MESHY_DIR, "meshy_swap_record_%s.json" % p)
            if os.path.isfile(rp):
                derived_index.update(tool._read_json(rp)["plan"].get("derived_meshes", {}))
        sstate = MS._structure_state(tool, structure)
        lines_before = int(structure.get_editor_property("hanging_line_count"))
        derived_new = {}
        stations = _stations(structure, tool)
        worlds, acrosses, order = _pair_worlds(show, tool, stations)
        grid = _grid(structure)
        if mode in ("DRY", "APPLY"):
            if op == "SCALE":
                lantern = sstate["body_mesh"].rsplit("/", 1)[-1]
                plan = F.scale_plan(passage, cues, table, derived_index, {"lantern": lantern, "body_size_cm": sstate["body_size_cm"]},
                                    plan_opts(args))
                plan["housing"]["body_material"] = sstate["body_material"]
                fixture = table[lantern]
                by_guid = {c["guid"]: c for c in all_cues}
                placements = F.follow_placements([by_guid[g] for g in order if g in by_guid], worlds, acrosses)
                boxes = {}
                for i, g in enumerate(order):
                    nxt = stations[i + 1]["station_world"] if i + 1 < len(stations) else None
                    prv = stations[i - 1]["station_world"] if i > 0 else None
                    boxes[g] = F.grid_boxes(stations[i]["station_world"], grid, nxt) + \
                        ([] if prv is None else [b for b in F.grid_boxes(prv, grid) if b["name"] == "crossbeam"])
                plan["girders"] = {"grid": grid,
                                   "hits_before": F.girder_report(placements, boxes, fixture["bounds_min"], fixture["bounds_max"],
                                                                  plan["housing"]["body_size_before"], args["girder_margin_cm"]),
                                   "hits_after": F.girder_report(placements, boxes, fixture["bounds_min"], fixture["bounds_max"],
                                                                 plan["housing"]["body_size_after"], args["girder_margin_cm"])}
            else:
                ropts = plan_opts(args)
                ropts["grid"] = {k: grid[k] for k in ("height_cm", "beam_depth_cm", "beam_width_cm", "half_width_cm")}
                cord_mesh, cord_bounds, derived_new = _cord_mesh(structure)
                plan0 = F.relocate_plan(passage, cues, table, derived_index, ropts, None, F.object_path(cord_mesh), cord_bounds)
                floor_z, missing = _floor_z_by_spot(plan0, worlds, _floor_tops(args["floor_label_regex"]))
                plan = F.relocate_plan(passage, cues, table, derived_index, ropts, floor_z, F.object_path(cord_mesh), cord_bounds)
                plan["floor_missing"] = missing
                plan["derived_cord"] = derived_new
                plan["checks"] = F.relocate_checks(plan, table)
                require(not plan["checks"], "RELOCATE_PLAN_CHECKS|%s" % plan["checks"][:5])
                plan["housings_removed"] = _housings_removed(plan, before_all)
            plan["structure_before"] = {k: v for k, v in sstate.items() if k != "ism"}
            sha = F.plan_sha(plan)
            targets = {t["cue_guid"] for t in plan["targets"]}
            guids = sorted(targets | {c["guid"] for t in plan["targets"] for c in t["changes"]})
            foreign = _foreign(scores, roots, guids, rpath, names["structure_label"])
            unacked = F.M.check_ack(foreign, args["ack_records"])
            nrows = sum(len(t["changes"]) for t in plan["targets"])
            report.update({"plan": plan, "plan_sha256": sha, "foreign_records": foreign, "unacknowledged_foreign_records": unacked})
            if mode == "DRY":
                require(tool._dirty_census() == census_before, "DRY_CENSUS_CHANGED")
                require(F.canonical(MS._all_rows(_runtime_plain(scores, tool, show))) == F.canonical(before_all),
                        "DRY_SHOW_ROWS_CHANGED")
                extra = ("plan_sha256=%s|rows=%d|unacked=%d|" % (sha, nrows, len(unacked)))
                if op == "SCALE":
                    extra += "housing=%s %s->%s|bulbs=%d|refused=%d|girder_hits_before=%d|after=%d|mutated=0" % (
                        plan["housing"]["lantern"], plan["housing"]["scale_before"], plan["housing"]["scale_after"],
                        plan["counts"]["bulbs"], plan["counts"]["refused"], len(plan["girders"]["hits_before"]),
                        len(plan["girders"]["hits_after"]))
                else:
                    extra += "by_kind=%s|working=%d|glimmer=%d|floor_missing=%d|housings_removed=%d|mutated=0" % (
                        F.canonical(plan["counts"]["by_kind"]), plan["counts"]["working"], plan["counts"]["glimmer_spots"],
                        len(plan["floor_missing"]), plan["housings_removed"])
                return _finish(report, op, mode, passage, run, extra)

            # ------------------------------------------------------------ APPLY
            require(sha == args["plan_sha256"], "PLAN_SHA_MISMATCH|live=%s|args=%s" % (sha, args["plan_sha256"]))
            if args["expected_rows"] is not None:
                require(nrows == int(args["expected_rows"]), "PIN_ROWS|plan=%d|pinned=%s" % (nrows, args["expected_rows"]))
            require(nrows > 0 or op == "SCALE", "NOTHING_TO_DO")
            require(not os.path.exists(rpath), "ACTIVE_RECORD_EXISTS|" + rpath)
            require(not unacked, "FOREIGN_ACTIVE_RECORDS_OVERLAP|" + ";".join(unacked))
            if op == "SCALE":
                require(not os.path.exists(record_path("RELOCATE", passage)),
                        "RELOCATE_ACTIVE|scale before relocating, or REVERT the relocation first")
            texts_hash = MS._export_hash(tool, show, targets)
            backup = tool._backup("PreFixFollow%s%s-" % (op.title(), passage), run)
            record = {"schema_version": 1, "status": "prepared", "op": op, "run": run, "passage": passage, "backup": backup,
                      "args": args, "plan_sha256": sha, "plan": plan, "export_hash_before": texts_hash,
                      "before_rows": {g: before_all[g] for g in sorted(targets)}, "structure_before": plan["structure_before"],
                      "acknowledged_records": list(args["ack_records"]), "derived_created": []}
            tool._write_json(rpath, record, exclusive=True)
            _log("%s_RECORD_WRITTEN|run=%s|path=%s" % (MARK, run, rpath))
            if derived_new:
                created, reused = MS._ensure_derived(derived_new)
                record.update({"derived_created": created, "derived_reused": reused})
                tool._write_json(rpath, record)
                require(tool._dirty_census() == census_before, "DERIVED_LEFT_DIRTY")
            want_all = F.expected_after(before_all, plan)
            originals, structure_written = [], False
            try:
                for t in plan["targets"]:
                    originals.append(_write_rows_full(tool, show, t, {c["guid"]: c["after"] for c in t["changes"]}))
                after_all = MS._all_rows(_runtime_plain(scores, tool, show))
                F.check_scope(want_all, after_all, "after")
                _require_body_readback(want_all, after_all, "after")
                require(MS._export_hash(tool, show, targets) == texts_hash, "EXPORT_OUTSIDE_SCOPE_CHANGED")
                if op == "SCALE":
                    h = plan["housing"]
                    structure_written = True
                    MS._write_structure(structure, h["mesh"], h["body_size_after"], h["body_material"])
                    MS._check_structure(MS._structure_state(tool, structure), h["mesh"], h["body_size_after"],
                                        h["body_material"], plan["structure_before"]["other"])
            except Exception:
                for index, original in originals:
                    tool._set_pair_attachments(show, index, original)
                if structure_written:
                    sb = plan["structure_before"]
                    MS._write_structure(structure, sb["body_mesh"], sb["body_size_cm"], sb["body_material"])
                F.check_scope(before_all, MS._all_rows(_runtime_plain(scores, tool, show)), "before")
                _require_body_readback(before_all, MS._all_rows(_runtime_plain(scores, tool, show)), "before")
                record["status"] = "failed_rolled_back_in_memory"
                tool._write_json(rpath, record)
                os.rename(rpath, rpath + ".failed-" + run)
                raise
            record.update({"status": "mutated_verified", "after_rows": {g: after_all[g] for g in sorted(targets)}})
            tool._write_json(rpath, record)
            materialized = scores._materialize_passage(show, names["actor_prefix"])
            require(materialized.get("structure") == names["structure_label"], "STRUCTURE_NOT_REFIT|%s" % materialized)
            state = MS._structure_state(tool, structure)
            require(state["current"], "STRUCTURE_NOT_CURRENT_AFTER_REFIT")
            if op == "SCALE":
                s = plan["housing"]["scale_after"]
                off = [sc for sc in (state["ism"] or {}).get("scales", []) if any(abs(v - s) > 1.0e-3 for v in sc)]
                require(state["ism"] and not off, "HOUSING_SCALE_READBACK|%s" % off[:4])
                require(state["fixture_body_count"] == plan["structure_before"]["fixture_body_count"], "HOUSING_COUNT_CHANGED")
            else:
                want_n = plan["structure_before"]["fixture_body_count"] - plan["housings_removed"]
                require(state["fixture_body_count"] == want_n, "HOUSING_COUNT|want=%d|got=%d" % (want_n, state["fixture_body_count"]))
            spawned = _verify_rows_spawned(plan, worlds, tool)
            record["hanging_lines"] = {"before": lines_before, "after": int(structure.get_editor_property("hanging_line_count"))}
            tool._write_json(rpath, record)
            tool._save_narrow()
            report["saved"] = True
            readback = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
            read_all = MS._all_rows(_runtime_plain(scores, tool, readback))
            F.check_scope(want_all, read_all, "readback")
            _require_body_readback(want_all, read_all, "readback")
            require(MS._export_hash(tool, readback, targets) == texts_hash, "READBACK_EXPORT_OUTSIDE_SCOPE_CHANGED")
            record.update({"status": "saved_readback_verified", "materialized": materialized, "structure_after": state,
                           "after_rows": {g: read_all[g] for g in sorted(targets)}, "spawned_verified": spawned,
                           "saved_census": tool._dirty_census()})
            tool._write_json(rpath, record)
            report.update({"backup": backup, "record": rpath})
            return _finish(report, op, mode, passage, run, "plan_sha256=%s|rows=%d|spawned_ok=%d|housings=%d|show_saved=1|"
                           "level_saved=1|readback=1|lines=%d->%d|record=%s" % (sha, nrows, spawned, state["fixture_body_count"],
                                                               record["hanging_lines"]["before"], record["hanging_lines"]["after"], rpath))

        # ---------------------------------------------------------------- REVERT (SCALE / RELOCATE)
        require(os.path.isfile(rpath), "REVERT_RECORD_ABSENT|" + rpath)
        record = tool._read_json(rpath)
        require(record.get("status") == "saved_readback_verified" and record.get("op") == op and record.get("passage") == passage,
                "REVERT_RECORD_STATE|%s" % record.get("status"))
        if op == "SCALE":
            require(not os.path.exists(record_path("RELOCATE", passage)), "RELOCATE_ACTIVE|revert the relocation first")
        model = F.revert_model(record, before_all)
        plan = record["plan"]
        targets = set(record["before_rows"])
        guids = sorted(targets | {c["guid"] for t in plan["targets"] for c in t["changes"]})
        unacked = F.M.check_ack(_foreign(scores, roots, guids, rpath, names["structure_label"]), args["ack_records"])
        require(not unacked, "FOREIGN_ACTIVE_RECORDS_OVERLAP|" + ";".join(unacked))
        sb = record["structure_before"]
        if op == "SCALE":
            h = plan["housing"]
            MS._check_structure(MS._structure_state(tool, structure), h["mesh"], h["body_size_after"], h["body_material"], sb["other"])
        texts_hash = MS._export_hash(tool, show, targets)
        backup = tool._backup("PreFixFollow%s%sRevert-" % (op.title(), passage), run)
        originals, structure_written = [], False
        try:
            for t in plan["targets"]:
                before_by_guid = {r["guid"]: r for r in record["before_rows"][t["cue_guid"]]}
                originals.append(_write_rows_full(tool, show, t, {c["guid"]: before_by_guid[c["guid"]] for c in t["changes"]}))
            revert_live = MS._all_rows(_runtime_plain(scores, tool, show))
            F.check_scope(model, revert_live, "revert")
            _require_body_readback(model, revert_live, "revert")
            require(MS._export_hash(tool, show, targets) == texts_hash, "REVERT_EXPORT_OUTSIDE_SCOPE_CHANGED")
            if op == "SCALE":
                structure_written = True
                MS._write_structure(structure, sb["body_mesh"], sb["body_size_cm"], sb["body_material"])
                MS._check_structure(MS._structure_state(tool, structure), sb["body_mesh"], sb["body_size_cm"],
                                    sb["body_material"], sb["other"])
        except Exception:
            for index, original in originals:
                tool._set_pair_attachments(show, index, original)
            if structure_written:
                h = plan["housing"]
                MS._write_structure(structure, h["mesh"], h["body_size_after"], h["body_material"])
            raise
        materialized = scores._materialize_passage(show, names["actor_prefix"])
        tool._save_narrow()
        report["saved"] = True
        readback = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
        revert_read = MS._all_rows(_runtime_plain(scores, tool, readback))
        F.check_scope(model, revert_read, "revert_readback")
        _require_body_readback(model, revert_read, "revert_readback")
        state = MS._structure_state(tool, structure)
        require(state["fixture_body_count"] == sb["fixture_body_count"], "REVERT_HOUSING_COUNT|%d|%d"
                % (state["fixture_body_count"], sb["fixture_body_count"]))
        archived = rpath + ".reverted-" + run
        record.update({"status": "reverted", "reverted_run": run, "revert_materialized": materialized})
        tool._write_json(rpath, record)
        os.rename(rpath, archived)
        report.update({"backup": backup, "record_archived": archived, "derived_left_on_disk": record.get("derived_created", [])})
        return _finish(report, op, mode, passage, run, "rows=%d|show_saved=1|level_saved=1|readback=1|archived=%s"
                       % (len(guids) - len(targets), archived))
    except Exception as error:  # noqa: BLE001 - a report and a marker for every stop
        report["error"] = "%s: %s" % (type(error).__name__, error)
        if tool is not None:
            try:
                report["census"] = tool._dirty_census()
            except Exception:  # noqa: BLE001
                pass
        with open(report_path(op, mode, passage, run), "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=1, sort_keys=True, default=str)
        unreal.log_error("%s_STOPPED|run=%s|op=%s|mode=%s|passage=%s|saved=%d|%s%s"
                         % (MARK, run, op, mode, passage, int(report["saved"]), report["error"][:1500],
                            "" if report["saved"] else "|NOTHING SAVED"))
        raise


def main():
    global F, MS
    F = load_common()
    require(unreal is not None, "UNREAL_REQUIRED")
    try:
        MS = load_meshy_swap()
        args = check_args(globals().get("FIXFOLLOW_ARGS"))
    except Exception as error:  # noqa: BLE001
        unreal.log_error("%s_STOPPED|run=none|ARGS|%s: %s|NOTHING SAVED" % (MARK, type(error).__name__, error))
        raise
    return _run(args)


def count_cli(argv=None):
    global F
    F = load_common()
    argv = list(sys.argv[1:] if argv is None else argv)
    raw = {"op": "RELOCATE", "mode": "COUNT", "passage": "ALL"}
    if argv:
        with open(argv[0], encoding="utf-8") as handle:
            raw = json.load(handle)
    args = check_args(raw)
    require(args["mode"] == "COUNT", "OFFLINE_RUNS_COUNT_ONLY")
    out, path = count_offline(args)
    for p, row in out["passages"].items():
        print("%s_%s_COUNT|%s|%s" % (MARK, args["op"], p, F.canonical({k: v for k, v in row.items()
                                                                       if k in ("counts", "housed_lights", "girder_hits", "cues")})))
    print("%s_COUNT_OK|written=%s" % (MARK, path))
    return out


if __name__ == "__main__" and unreal is None:
    count_cli()


if unreal is not None:
    main()
