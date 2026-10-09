"""P01 FLOOR practicals -- Gary 8 Oct: "floor uplights for the domestic lamps please" (F1 + decision).
Ops: FLOOR (P01 default; any passage via "passage") and ADD_UPLIGHTS (proposal only: COUNT / DRY). Default
uplight_body STRUCTURE_CAN: the domestic body row is disabled and the Structure lantern is the floor uplight (see
p01_floor_common.FLOOR_DEFAULTS for why BIRDIE_BODY is refused). Offline: COUNT (python p01_floor.py [args.json]). Editor: DRY / APPLY / REVERT via
p01_floor_run.py (ExecuteProjectPythonFile, request p01_floor_request.json). What a plan changes, row by row, and every
proof tier for the maths: p01_floor_common.py's docstring.

This EXTENDS FixturesFollow RELOCATE with a FLOOR mode without editing it: fixtures_common.py (maths, scope, revert)
is loaded with runpy, and fixtures_follow.py's runtime helpers (_runtime_plain, _stations, _pair_worlds, _grid,
_body_mesh_bounds, _floor_tops, _follow_state, _require_body_readback, load_meshy_swap) are loaded from its AST WITHOUT
its two trailing guards, exactly as fixtures_follow.py itself loads meshy_swap.py (fixtures_follow.py:102-131).

MODES
  COUNT   offline: snapshot rows (FixturesFollow fixtures_common.snapshot_passage = meshy_swap_record_P01 after_rows,
          run 20261007-082523) + note-lamp flash fields (p01_note_lamps_record.json, run 20261007-160203) + panel spans
          from Saved/CodexFlatV3 (hf_preflight y + GAP_AUDIT width; x from edge_x_probe). Plan, counts, per-item CSV,
          PNG maps. Writes nothing in Unreal.
  DRY     editor, read-only: every live read APPLY uses (rows + flash fields, stations, live pair frames via
          GetAttachmentAnchorWorldTransform cross-checked with OccurrenceOffset*StationWorld, materialized panel ISM
          bounds, floor actors, lamp mesh bounds, the lantern, the housing ISM, the spawned-actor index), plan_sha256,
          checks, foreign records, PNG if matplotlib exists in the editor (else run p01_floor_preview.py on the report).
          Census and rows proven unchanged.
  APPLY   confirm "APPLY P01FLOOR" + plan_sha256 (+ expected_rows pin) + ack_records verbatim. Refuses: an active
          p01_floor_record.json (no re-APPLY over a record), an active FixturesFollow RELOCATE record for P01, any plan
          check, unacknowledged foreign records, a TOPPLE/TURN mechanism on a target cue unless accept_mechanism_risk.
          Backups/PreP01Floor-<run> (Show + level) and the record (before rows) BEFORE the first write; writes only the
          planned fields on the planned GUIDs; scope check (every other row and field identical, Body extension fields
          identical, export of every other cue + passage settings identical) with in-memory rollback; materialize
          Passage 01 + re-fit Structure 01; lanterns = before - disabled, every lantern on its light (8-corner gap
          <= 0.5 cm), hanging lines = before + predicted delta, every moved actor where planned; any failure there ->
          rows rolled back + re-materialized, NOTHING SAVED; narrow save (Show + level only); read back from the saved
          asset; P01FLOOR_APPLY_OK only after all of that.
  REVERT  confirm "REVERT P01FLOOR". Live target cues must equal the record's after rows (REVERT_DRIFT otherwise),
          writes the before values of exactly the recorded fields, same verify/save/read-back chain, lantern count back
          to the recorded before, record archived .reverted-<run>.
Markers  P01FLOOR_<MODE>_OK|run=..; any stop P01FLOOR_STOPPED|run=..|..|NOTHING SAVED (when nothing was saved).

Proof tiers (beyond p01_floor_common.py):
* declaration-proven: Station-anchored lights keep Light Drama (InfinityStagePassageActor.cpp:1864-1866) and Movers
  (:1916-1917); the anchor is never written here (scope check). GetAttachmentAnchorWorldTransform returns the pair root
  for a Station row (:2137-2139) and is BlueprintCallable (InfinityStagePassageActor.h:150-153); MaterializedPanels is
  BlueprintReadOnly with Component / InstanceIndex / Side (InfinityStagePassageActor.h:25-41, :90-91).
* measured (by earlier live runs of the same calls): materialized_panels / base_world_transform reads (p02_straighten.py:
  550, fx_wingburn_test.py:249); get_attachment_anchor_world_transform (lighting_events_apply.py:1048);
  ISM get_instance_transform(i, True) (meshy_swap.py:404); lighting "type" set via _enum_member
  (lighting_looks_apply.py:1488); drama flash_camera_offsets_cm set (p01_note_lamps.py:1149); row write pattern
  (meshy_swap.py:524-535); _backup / _save_narrow (lighting_looks_apply.py:1616, :1657); _materialize_passage
  (lighting_scores_apply.py:2879).
* inferred (each gated in DRY, before any write): FixturesFollow's never-run reads (gather_stations shape,
  occurrence_offset, gridiron/grid_half_width_cm names, its fixtures_follow.py header); wing_pair.mechanism names
  (kind / max_angle_deg / inward_travel_cm, report-only, unreadable -> "UNREADABLE" and the APPLY needs
  accept_mechanism_risk); InfinityStageLightType member SPOT (the enum, InfinityStageTypes.h:166).
"""
from __future__ import annotations

import ast
import copy
import csv
import datetime
import hashlib
import json
import math
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
COMMON_PATH = os.path.join(HERE, "p01_floor_common.py")
PREVIEW_PATH = os.path.join(HERE, "p01_floor_preview.py")
FIXFOLLOW_PATH = os.path.join(CONDUCTOR, "FixturesFollow", "fixtures_follow.py")
NOTE_LAMPS_RECORD = os.path.join(CONDUCTOR, "p01_note_lamps_record.json")
FLATV3 = os.path.join(SAVED, "CodexFlatV3")
MARK = "FLOOR"           # pre-args stops only; every run marks <PASSAGE>FLOOR / <PASSAGE>ADDUP
OPS = ("FLOOR", "ADD_UPLIGHTS")


def mark(passage, op="FLOOR"):
    return "%s%s" % (passage, "FLOOR" if op == "FLOOR" else "ADDUP")


def relocate_record_for(passage):
    return os.path.join(CONDUCTOR, "FixturesFollow", "fixfollow_relocate_record_%s.json" % passage)
MODES = ("COUNT", "DRY", "APPLY", "REVERT")
PLACE_TOL_CM = 0.5
AIM_TOL_DEG = 0.5
EXTRA = {"plan_sha256": None, "expected_rows": None, "ack_records": [], "allow_dirty": [],
         "accept_mechanism_risk": False}

F = None    # p01_floor_common namespace (fresh per run)
FF = None   # fixtures_follow.py definitions (no guards)
MS = None   # meshy_swap.py definitions (runtime helpers)


def load_common():
    return types.SimpleNamespace(**runpy.run_path(COMMON_PATH, run_name="_p01_floor_common"))


def load_without_guards(path, module_name, guards):
    """A project tool's definitions without its trailing `if ...: main()` / `count_cli()` guards; any other top-level
    statement that could run code is refused (same rule as fixtures_follow.load_meshy_swap)."""
    with open(path, "rb") as handle:
        raw = handle.read()
    tree = ast.parse(raw.decode("utf-8"), filename=path)
    body = []
    for node in tree.body:
        if isinstance(node, ast.If):
            text = ast.unparse(node.test)
            calls = [ast.unparse(n.value.func) for n in node.body if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)]
            if text in guards and len(node.body) == 1 and calls == [guards[text]]:
                continue
            raise RuntimeError("TOP_LEVEL_IF|%s|line=%d|%s" % (path, node.lineno, text))
        if isinstance(node, ast.Expr) and not (isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
            raise RuntimeError("TOP_LEVEL_EXPR|%s|line=%d" % (path, node.lineno))
        body.append(node)
    tree.body = body
    module = types.ModuleType(module_name)
    module.__file__ = path
    exec(compile(tree, path, "exec"), module.__dict__)  # noqa: S102 - reviewed project file
    module.SOURCE_SHA256 = hashlib.sha256(raw).hexdigest()
    return module


def load_fixfollow(common):
    ff = load_without_guards(FIXFOLLOW_PATH, "_fixtures_follow_for_p01floor",
                             {"__name__ == '__main__' and unreal is None": "count_cli", "unreal is not None": "main"})
    for name in ("_runtime_plain", "_stations", "_pair_worlds", "_grid", "_body_mesh_bounds", "_floor_tops",
                 "_follow_state", "_require_body_readback", "load_meshy_swap", "_t", "_v"):
        if not callable(getattr(ff, name, None)):
            raise RuntimeError("FIXFOLLOW_API_DRIFT|" + name)
    ff.F = common.FC
    return ff


def require(condition, message):
    F.require(condition, message)


def check_args(raw):
    raw = dict(raw or {})
    out = copy.deepcopy(F.FLOOR_DEFAULTS)
    out.update(copy.deepcopy(EXTRA))
    allowed = set(out) | {"mode", "confirm", "passage", "op"}
    unknown = sorted(set(raw) - allowed)
    require(not unknown, "ARGS_UNKNOWN|%s" % unknown)
    for k, v in raw.items():
        out[k] = copy.deepcopy(v)
    out["passage"] = str(raw.get("passage", "P01")).upper()
    require(out["passage"] in F.FC.PASSAGES, "PASSAGE_INVALID|%s" % out["passage"])
    out["op"] = str(raw.get("op", "FLOOR")).upper()
    require(out["op"] in OPS, "OP_INVALID|%s" % out["op"])
    out["mode"] = str(raw.get("mode", "DRY")).upper()
    require(out["mode"] in MODES, "MODE_INVALID|%s" % out["mode"])
    if out["op"] == "ADD_UPLIGHTS":
        require(out["mode"] in ("COUNT", "DRY"), "ADD_UPLIGHTS_IS_PROPOSAL_ONLY|COUNT or DRY (no APPLY yet)")
    if out["mode"] in ("APPLY", "REVERT"):
        want = "%s %s" % (out["mode"], mark(out["passage"]))
        require(raw.get("confirm") == want, "CONFIRM_MISSING|need='%s'" % want)
    if out["mode"] == "APPLY":
        require(isinstance(out["plan_sha256"], str) and len(out["plan_sha256"]) == 64, "APPLY_NEEDS_PLAN_SHA256")
    for k in ("ack_records", "allow_dirty"):
        require(isinstance(out[k], list) and all(isinstance(v, str) for v in out[k]), k.upper() + "_INVALID")
    F.check_opts(plan_opts(out))
    return out


def plan_opts(args):
    return {k: args[k] for k in F.FLOOR_DEFAULTS}


# ---------------------------------------------------------------------------------------------------------------
# pure orchestration helpers
# ---------------------------------------------------------------------------------------------------------------
def write_json(path, value, exclusive=False):
    """Record-safe write: exclusive create when asked, else temp + fsync + replace."""
    text = json.dumps(value, indent=1, sort_keys=True, default=str)
    if exclusive:
        with open(path, "x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        return
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def floor_lookup(plan0, floor_tops):
    """Per moved item: the highest floor-actor top under the item's planned spot (world XY) within 150 cm of the panel
    foot, in pair-frame z, with its disagreement against the panel foot. No floor actor -> the panel foot (listed)."""
    out = {}
    for t in plan0["targets"]:
        ctx = plan0["ctx"][t["cue_guid"]]
        w = ctx["pair_world"]
        up = F.quat_rotate(w["rotation_xyzw"], [0.0, 0.0, 1.0])
        require(up[2] > 0.999, "PAIR_FRAME_NOT_UPRIGHT|%s" % t["cue_label"])
        for c in t["changes"]:
            if c["what"] not in ("DEAD_BULB_TO_FLOOR", "UPLIGHT_BODY_TO_FLOOR", "UPLIGHT_LIGHT_TO_FLOOR", "ADD_UPLIGHT"):
                continue
            foot = float(c["meta"]["floor_z"])
            loc = c["after"]["relative_transform"]["location"]
            p = F.xf_point(w, [loc[0], loc[1], foot])
            tops = [(fl[4], fl[5]) for fl in floor_tops if fl[0] <= p[0] <= fl[1] and fl[2] <= p[1] <= fl[3]
                    and abs(fl[4] - p[2]) <= 150.0]
            if tops:
                ztop, label = max(tops)
                z = foot + (ztop - p[2])
                out[c["guid"]] = {"z": round(z, 4), "source": "FLOOR_ACTOR:%s" % label, "disagree_cm": round(z - foot, 4)}
            else:
                out[c["guid"]] = {"z": foot, "source": "PANEL_FOOT(no floor actor under the spot)", "disagree_cm": None}
    return out


def floor_by_body(plan0, floors):
    """FLOOR plans key the floor by BODY guid (the light of an uplight shares its body's floor): a light's floor
    (STRUCTURE_CAN, body hidden) is re-keyed to its paired body."""
    out = dict(floors)
    for u in plan0["uplights"]:
        if u["light_guid"] in floors and u["body_guid"] not in out:
            out[u["body_guid"]] = floors[u["light_guid"]]
    return out


def build_add_plan(state, args):
    opts = plan_opts(args)
    plan0 = F.add_uplights_plan(state["cues"], state["ctx_by_cue"], state["lantern"], state["grid"], opts, args["passage"])
    floors = floor_lookup(plan0, state["floor_tops"])
    plan = F.add_uplights_plan(state["cues"], state["ctx_by_cue"], state["lantern"], state["grid"], opts, args["passage"],
                               floor_by_guid=floors)
    plan["checks"] = [list(b) for b in F.add_plan_checks(plan)]
    n = plan["counts"]["proposed_uplights"]
    lb = state["structure"].get("fixture_body_count")
    plan["predicted"] = {"lanterns_added": n, "lanterns": [lb, None if lb is None else lb + n],
                         "note": "every proposed Station LIGHT gets the Structure lantern (cpp:164-176): that lantern is "
                                 "the uplight's body (%s)" % state["lantern"].get("name")}
    plan["structure_before"] = state["structure"]
    plan["live_checks"] = state.get("live_checks", {})
    return plan


def build_plan(state, args):
    opts = plan_opts(args)
    cues = state["cues"]
    common = dict(mesh_bounds=state["mesh_bounds"], table=state["table"], caps=state["caps"], lantern=state["lantern"],
                  grid=state["grid"], opts=opts, derived_index=state["derived_index"])
    plan0 = F.floor_plan(cues, state["ctx_by_cue"], passage=args["passage"], **common)
    floors = floor_by_body(plan0, floor_lookup(plan0, state["floor_tops"]))
    plan = F.floor_plan(cues, state["ctx_by_cue"], floor_by_guid=floors, passage=args["passage"], **common)
    before_all = {c["guid"]: c["attachments"] for c in state["all_cues"]}
    plan["checks"] = [list(b) for b in F.plan_checks(plan, before_all)]
    pred = F.predict_structure(plan, before_all)
    n_before = len(F.housings(cues, state["ctx_by_cue"]))
    after_all = F.expected_after(before_all, plan)
    after_cues = [dict(c, attachments=after_all[c["guid"]]) for c in cues]
    n_after = len(F.housings(after_cues, state["ctx_by_cue"]))
    plan["predicted"] = dict(pred, lanterns_before_offline_count=n_before, lanterns_after_offline_count=n_after)
    plan["structure_before"] = state["structure"]
    plan["cans_report"] = F.cans_report(cues, state["ctx_by_cue"], state["lantern"])
    plan["cans_counts"] = {"total": len(plan["cans_report"]),
                           "by_role": _count(plan["cans_report"], "role"),
                           "outboard_of_panel": sum(1 for c in plan["cans_report"] if c["outboard_of_panel"]),
                           "abs_y_gt_1130": sum(1 for c in plan["cans_report"] if c["abs_y_gt_1130"])}
    targets = {t["cue_guid"] for t in plan["targets"]}
    mech = {g: m for g, m in state.get("mechanisms", {}).items() if g in targets}
    plan["mechanisms"] = mech
    # Slide moves a side panel along y and Trap along z: the floor items stand in FRONT (-x) of the panel, so neither
    # sweeps them. Topple / Turn rotate the panel out of its plane and can (InfinityStageTypes.h:579-588, :675-679).
    plan["mechanism_risks"] = sorted(g for g, m in mech.items()
                                     if F.enum_name(m.get("kind", "UNREADABLE")) in ("TOPPLE", "TURN", "UNREADABLE"))
    plan["live_checks"] = state.get("live_checks", {})
    return plan


def _count(rows, key):
    out = {}
    for r in rows:
        out[r[key]] = out.get(r[key], 0) + 1
    return dict(sorted(out.items()))


def fields_for(change, before_row):
    out = []
    for path in F.ALLOWED_PATHS[change["what"]]:
        if F.M.row_differences({"v": F.get_path(before_row, path)}, {"v": F.get_path(change["after"], path)}):
            out.append(path)
    return out


def write_values(plan, rows_by_guid, source):
    """{cue_guid: {guid: (row, fields)}} -- source 'after' (APPLY) or a {guid: row} map (REVERT before rows)."""
    out = {}
    for t in plan["targets"]:
        vals = {}
        for c in t["changes"]:
            before = rows_by_guid[c["guid"]]
            fields = fields_for(c, before)
            require(fields, "CHANGE_WITHOUT_FIELDS|%s" % c["label"])
            vals[c["guid"]] = (c["after"] if source == "after" else source[c["guid"]], fields)
        out[t["cue_guid"]] = vals
    return out


def flash_report(plan):
    rows = []
    for u in plan["uplights"]:
        if u["meta"]["flash_lamp"]:
            rows.append({"cue": u["cue"], "light": u["light_label"], "dx_cm": u["meta"]["dx_cm"],
                         "shift_s_at_250cm_s_if_uncompensated": round(abs(u["meta"]["dx_cm"]) / 250.0, 3),
                         "compensated": u["meta"]["flash_compensated"]})
    return rows


def write_outputs(plan, mode, run, out_dir, stem="p01_floor"):
    """Plan JSON (in the report), per-item CSV, PNG maps (matplotlib if present)."""
    csv_path = os.path.join(out_dir, "%s_items_%s_%s.csv" % (stem, mode, run))
    rows = F.item_table(plan) if plan["op"] == "FLOOR" else [
        {"cue": t["cue_label"], "label": c["label"], "side": c["meta"]["side"], "pitch_deg": c["meta"]["pitch_deg"],
         "light_xyz": [round(v, 2) for v in c["after"]["relative_transform"]["location"]],
         "lumens": c["after"]["lighting"]["intensity"], "color": c["after"]["lighting"]["color"],
         "floor_z": round(c["meta"]["floor_z"], 3), "floor_source": c["meta"]["floor_source"],
         "panel_y_span": c["meta"]["panel_y_span"], "lantern": c["meta"]["lantern"]}
        for t in plan["targets"] for c in t["changes"]]
    with open(csv_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else ["cue"])
        writer.writeheader()
        for r in rows:
            writer.writerow({k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in r.items()})
    pngs, why = [], None
    try:
        preview = runpy.run_path(PREVIEW_PATH, run_name="_p01_floor_preview")
        pngs = preview["render"](plan, out_dir, "%s_%s" % (mode, run), stem)
    except ImportError as error:   # matplotlib absent (the editor's Python): run p01_floor_preview.py on the report
        why = "PREVIEW_DEFERRED|%s" % error
    return {"csv": csv_path, "png": pngs, "preview_note": why}


# ---------------------------------------------------------------------------------------------------------------
# the orchestrator (backend-agnostic: the live editor backend, the offline COUNT backend, the harness fake)
# ---------------------------------------------------------------------------------------------------------------
def run(args, be, out_dir=HERE, relocate_record=None):
    run_id = be.now()
    mode, passage, op = args["mode"], args["passage"], args["op"]
    MARK = mark(passage, op)
    relocate_record = relocate_record or relocate_record_for(passage)
    stem = "%s_%s" % (passage.lower(), "floor" if op == "FLOOR" else "addup")
    rpath = os.path.join(out_dir, "%s_floor_record.json" % passage.lower())
    report = {"ok": False, "op": op, "mode": mode, "run": run_id, "passage": passage, "args": args, "saved": False}
    report_path = os.path.join(out_dir, "%s_report_%s_%s.json" % (stem, mode, run_id))

    def finish(extra):
        report["ok"] = True
        write_json(report_path, report)
        be.log("%s_%s_OK|run=%s|passage=%s|%s|report=%s" % (MARK, mode, run_id, passage, extra, report_path))
        return report

    try:
        ctx = be.context()
        report["context"] = ctx
        be.check_context(ctx, mode, args["allow_dirty"])
        census_before = be.census()
        state = be.read_state(args)
        before_all = {c["guid"]: c["attachments"] for c in state["all_cues"]}
        if op == "ADD_UPLIGHTS":                       # proposal only (check_args refuses APPLY / REVERT)
            plan = build_add_plan(state, args)
            sha = F.plan_sha(plan)
            report.update({"plan": plan, "plan_sha256": sha})
            report["outputs"] = write_outputs(plan, mode, run_id, out_dir, stem)
            if mode == "DRY":
                require(be.census() == census_before, "DRY_CENSUS_CHANGED")
                require(F.canonical(be.rows_now()) == F.canonical(before_all), "DRY_SHOW_ROWS_CHANGED")
            require(not plan["checks"], "PLAN_CHECKS|%s" % plan["checks"][:6])
            return finish("plan_sha256=%s|proposed_uplights=%d|bays=%d|sides_skipped=%d|lantern=%s|lanterns=%s->%s|"
                          "checks=0|proposal_only=1|mutated=0"
                          % (sha, plan["counts"]["proposed_uplights"], plan["counts"]["cues"],
                             plan["counts"]["sides_skipped"], state["lantern"].get("name"),
                             plan["predicted"]["lanterns"][0], plan["predicted"]["lanterns"][1]))
        if mode in ("COUNT", "DRY", "APPLY"):
            plan = build_plan(state, args)
            sha = F.plan_sha(plan)
            nrows = plan["counts"]["rows"]
            targets = sorted({t["cue_guid"] for t in plan["targets"]})
            guids = sorted(set(targets) | {c["guid"] for t in plan["targets"] for c in t["changes"]})
            foreign = be.foreign(guids, [rpath])
            unacked = sorted({h["path"] for h in foreign} - set(args["ack_records"]))
            relocate_active = os.path.exists(relocate_record)
            report.update({"plan": plan, "plan_sha256": sha, "foreign_records": foreign,
                           "unacknowledged_foreign_records": unacked, "relocate_record_active": relocate_active,
                           "flash": flash_report(plan)})
            summary = ("plan_sha256=%s|rows=%d|dead=%d|uplights=%d|glimmers_left=%d|working_left=%d|refused=%d|"
                       "checks=%d|lanterns=%s->%s|line_delta=%d|cans_low_side_beam=%d|unacked=%d|mech_risks=%d"
                       % (sha, nrows, plan["counts"]["dead_bulbs"], plan["counts"]["uplights"],
                          plan["counts"]["glimmers_left"], plan["counts"]["working_left"], plan["counts"]["refused"],
                          len(plan["checks"]), plan["structure_before"].get("fixture_body_count"),
                          (plan["structure_before"].get("fixture_body_count") or 0) - plan["predicted"]["housings_removed"],
                          plan["predicted"]["hanging_line_delta"], plan["cans_counts"]["total"], len(unacked),
                          len(plan["mechanism_risks"])))
            if mode in ("COUNT", "DRY"):
                report["outputs"] = write_outputs(plan, mode, run_id, out_dir, stem)
                if mode == "DRY":
                    require(be.census() == census_before, "DRY_CENSUS_CHANGED")
                    require(F.canonical(be.rows_now()) == F.canonical(before_all), "DRY_SHOW_ROWS_CHANGED")
                require(not plan["checks"], "PLAN_CHECKS|%s" % plan["checks"][:6])
                require(not plan["refused"], "PLAN_REFUSED_ITEMS|%s" % F.canonical(plan["refused"])[:1500])
                return finish(summary + "|mutated=0")

            # ------------------------------------------------------------------ APPLY
            require(not os.path.exists(rpath), "ACTIVE_RECORD_EXISTS|%s (REVERT it first; no re-APPLY over a record)" % rpath)
            require(sha == args["plan_sha256"], "PLAN_SHA_MISMATCH|live=%s|args=%s" % (sha, args["plan_sha256"]))
            if args["expected_rows"] is not None:
                require(nrows == int(args["expected_rows"]), "PIN_ROWS|plan=%d|pinned=%s" % (nrows, args["expected_rows"]))
            require(nrows > 0, "NOTHING_TO_DO")
            require(not plan["checks"], "PLAN_CHECKS|%s" % plan["checks"][:6])
            require(not plan["refused"], "PLAN_REFUSED_ITEMS|%d" % len(plan["refused"]))
            require(not relocate_active, "FIXFOLLOW_RELOCATE_ACTIVE_FOR_%s|%s" % (passage, relocate_record))
            require(not unacked, "FOREIGN_ACTIVE_RECORDS_OVERLAP|" + ";".join(unacked))
            require(not plan["mechanism_risks"] or args["accept_mechanism_risk"],
                    "MECHANISM_RISK|%s (a toppling/turning panel can sweep floor items; accept_mechanism_risk)"
                    % plan["mechanism_risks"][:6])
            rows_by_guid = {r["guid"]: r for rs in before_all.values() for r in rs}
            values = write_values(plan, rows_by_guid, "after")
            export_before = be.export_hash(targets)
            backup = be.backup("Pre%sFloor-" % passage, run_id)
            record = {"schema_version": 1, "status": "prepared", "op": "FLOOR", "run": run_id, "passage": passage,
                      "backup": backup, "args": args, "plan_sha256": sha, "plan": plan,
                      "fields": {g: {k: v[1] for k, v in vals.items()} for g, vals in values.items()},
                      "before_rows": {g: before_all[g] for g in targets}, "export_hash_before": export_before,
                      "structure_before": plan["structure_before"], "acknowledged_records": list(args["ack_records"])}
            # Conductor 5's condition for acking (8 Oct): per acknowledged record, exactly which of OUR changed rows (row
            # GUIDs) and cues it also mentions, so a later REVERT of that tool can see our drift on its rows.
            changed_rows = {rg for vals in values.values() for rg in vals}
            changed_cues = set(values)
            record["acked_overlap"] = {
                h["path"]: {"rows_we_changed": sorted(set(h.get("guids") or []) & changed_rows),
                            "cues_we_touched": sorted(set(h.get("guids") or []) & changed_cues),
                            "structure_level": bool(h.get("needles")), "status": h.get("status")}
                for h in foreign if h["path"] in set(args["ack_records"])}
            write_json(rpath, record, exclusive=True)
            be.log("%s_RECORD_WRITTEN|run=%s|path=%s" % (MARK, run_id, rpath))
            want_all = F.expected_after(before_all, plan)
            tokens = []

            def rollback(rematerialize):
                be.rollback(tokens)
                if rematerialize:
                    be.materialize()
                back = be.rows_now()
                F.check_scope(before_all, back, "rollback")
                FF._require_body_readback(before_all, back, "rollback")

            try:
                for t in plan["targets"]:
                    tokens.append(be.write_rows(t, values[t["cue_guid"]]))
                live = be.rows_now()
                F.check_scope(want_all, live, "after")
                FF._require_body_readback(want_all, live, "after")
                require(be.export_hash(targets) == export_before, "EXPORT_OUTSIDE_SCOPE_CHANGED")
            except Exception:
                rollback(False)
                record["status"] = "failed_rolled_back_in_memory"
                write_json(rpath, record)
                os.replace(rpath, rpath + ".failed-" + run_id)
                raise
            record.update({"status": "mutated_verified", "after_rows": {g: live[g] for g in targets}})
            write_json(rpath, record)
            try:
                materialized = be.materialize()
                st = be.structure_now()
                want_lanterns = plan["structure_before"]["fixture_body_count"] - plan["predicted"]["housings_removed"]
                require(st["fixture_body_count"] == want_lanterns,
                        "LANTERN_COUNT|want=%d|got=%d" % (want_lanterns, st["fixture_body_count"]))
                hc = be.housing_check()
                require(hc["count_matches"] and hc["stale"] == 0, "LANTERNS_NOT_ON_LIGHTS|%s" % F.canonical(hc)[:400])
                if plan["structure_before"].get("hanging_line_count") is not None:
                    want_lines = plan["structure_before"]["hanging_line_count"] + plan["predicted"]["hanging_line_delta"]
                    require(st["hanging_line_count"] == want_lines,
                            "HANGING_LINES|want=%d|got=%s" % (want_lines, st["hanging_line_count"]))
                require(st.get("current", True), "STRUCTURE_NOT_CURRENT_AFTER_REFIT")
                spawned = be.verify_spawned(plan)
            except Exception:
                rollback(True)
                record["status"] = "failed_rolled_back_in_memory"
                write_json(rpath, record)
                os.replace(rpath, rpath + ".failed-" + run_id)
                raise
            be.save_narrow()
            report["saved"] = True
            read = be.readback_rows()
            F.check_scope(want_all, read, "readback")
            FF._require_body_readback(want_all, read, "readback")
            require(be.export_hash(targets, readback=True) == export_before, "READBACK_EXPORT_OUTSIDE_SCOPE_CHANGED")
            record.update({"status": "saved_readback_verified", "materialized": materialized, "structure_after": st,
                           "housing_check_after": hc, "spawned_verified": spawned,
                           "after_rows": {g: read[g] for g in targets}, "saved_census": be.census()})
            write_json(rpath, record)
            report.update({"backup": backup, "record": rpath})
            return finish("plan_sha256=%s|rows=%d|lanterns=%d|lines=%s|spawned_ok=%d|show_saved=1|level_saved=1|"
                          "readback=1|record=%s" % (sha, nrows, st["fixture_body_count"], st.get("hanging_line_count"),
                                                     spawned, rpath))

        # ---------------------------------------------------------------------- REVERT
        require(os.path.isfile(rpath), "REVERT_RECORD_ABSENT|" + rpath)
        with open(rpath, encoding="utf-8") as handle:
            record = json.load(handle)
        require(record.get("status") == "saved_readback_verified" and record.get("op") == "FLOOR"
                and record.get("passage") == passage, "REVERT_RECORD_STATE|%s" % record.get("status"))
        model = F.revert_model(record, before_all)          # REVERT_DRIFT when a target cue moved since APPLY
        plan = record["plan"]
        targets = sorted(record["before_rows"])
        guids = sorted(set(targets) | {c["guid"] for t in plan["targets"] for c in t["changes"]})
        unacked = sorted({h["path"] for h in be.foreign(guids, [rpath])} - set(args["ack_records"]))
        require(not unacked, "FOREIGN_ACTIVE_RECORDS_OVERLAP|" + ";".join(unacked))
        before_by_guid = {r["guid"]: r for rs in record["before_rows"].values() for r in rs}
        values = {}
        for t in plan["targets"]:
            values[t["cue_guid"]] = {g: (before_by_guid[g], fields) for g, fields in record["fields"][t["cue_guid"]].items()}
        export_before = be.export_hash(targets)
        backup = be.backup("Pre%sFloorRevert-" % passage, run_id)
        tokens = []
        try:
            for t in plan["targets"]:
                tokens.append(be.write_rows(t, values[t["cue_guid"]]))
            live = be.rows_now()
            F.check_scope(model, live, "revert")
            FF._require_body_readback(model, live, "revert")
            require(be.export_hash(targets) == export_before, "REVERT_EXPORT_OUTSIDE_SCOPE_CHANGED")
        except Exception:
            be.rollback(tokens)
            raise
        try:
            materialized = be.materialize()
            st = be.structure_now()
            require(st["fixture_body_count"] == record["structure_before"]["fixture_body_count"],
                    "REVERT_LANTERN_COUNT|%d|%d" % (st["fixture_body_count"], record["structure_before"]["fixture_body_count"]))
            hc = be.housing_check()
            require(hc["count_matches"] and hc["stale"] == 0, "REVERT_LANTERNS_NOT_ON_LIGHTS")
            if record["structure_before"].get("hanging_line_count") is not None:
                require(st["hanging_line_count"] == record["structure_before"]["hanging_line_count"], "REVERT_HANGING_LINES")
        except Exception:
            be.rollback(tokens)
            be.materialize()
            raise
        be.save_narrow()
        report["saved"] = True
        read = be.readback_rows()
        F.check_scope(model, read, "revert_readback")
        FF._require_body_readback(model, read, "revert_readback")
        archived = rpath + ".reverted-" + run_id
        record.update({"status": "reverted", "reverted_run": run_id, "revert_materialized": materialized,
                       "revert_backup": backup})
        write_json(rpath, record)
        os.replace(rpath, archived)
        report.update({"backup": backup, "record_archived": archived})
        return finish("rows=%d|lanterns=%d|show_saved=1|level_saved=1|readback=1|archived=%s"
                      % (sum(len(v) for v in values.values()), st["fixture_body_count"], archived))
    except Exception as error:  # noqa: BLE001 - a report and a marker for every stop
        report["error"] = "%s: %s" % (type(error).__name__, error)
        try:
            report["census"] = be.census()
        except Exception:  # noqa: BLE001
            pass
        write_json(report_path, report)
        be.log_error("%s_STOPPED|run=%s|mode=%s|saved=%d|%s%s" % (MARK, run_id, mode, int(report["saved"]),
                                                                   report["error"][:1500],
                                                                   "" if report["saved"] else "|NOTHING SAVED"))
        raise


# ---------------------------------------------------------------------------------------------------------------
# OFFLINE backend (COUNT): snapshot rows + saved FlatV3 panel data; read-only
# ---------------------------------------------------------------------------------------------------------------
LAMP_BOUNDS_OFFLINE = {   # inferred: sizes measured (lighting_looks_practical_asset_probe.json), pivots assumed
    "/Game/KK_S2_Shrine/StarterContent/Props/SM_Lamp_Ceiling": [[-22.0, -22.0, -133.53076], [22.0, 22.0, 0.0]],
    "/Game/KK_S2_Shrine/StarterContent/Props/SM_Lamp_Wall": [[-18.37481, -18.30908, -14.70929], [0.0, 18.30908, 14.70929]],
}
PANEL_X_OFFLINE = None


def offline_panels(bay_guids, passage="P01"):
    """Pair-frame panel AABBs from Saved/CodexFlatV3 (measured offline): y from hf_preflight local_transform, width
    from GAP_AUDIT front_width_cm (left = -y: [y, y+w]; right: [y-w, y]); x from edge_x_probe (Flap x_min .. Timber
    x_max over P01's FBXs); z 0 .. 900 (height not needed). Sides with no V3 record: the same side's median span
    (inferred; the live DRY reads every panel's ISM bounds)."""
    import glob
    pres = sorted(glob.glob(os.path.join(FLATV3, "swapkit", "hf_preflight_FV3HF-*-%s.json" % passage)))
    pre = json.load(open(pres[-1], encoding="utf-8")) if pres else {"rows": []}
    gap = json.load(open(os.path.join(FLATV3, "floorgap", "GAP_AUDIT.json"), encoding="utf-8"))
    probe = json.load(open(os.path.join(FLATV3, "edge", "edge_x_probe_t5j_all.json"), encoding="utf-8"))
    xs_lo, xs_hi = [], []
    for entry in probe:
        if "/%s/" % passage not in entry["fbx"]:
            continue
        for obj in entry["objects"].values():
            for slot in obj["slots"].values():
                xs_lo.append(slot["x_min"])
                xs_hi.append(slot["x_max"])
    x_lo, x_hi = (min(xs_lo), max(xs_hi)) if xs_lo else (-16.05, 3.8)    # P01 values when a passage has no probe
    widths = {(s["cue_guid"], s["side"]): s["front_width_cm"] for s in gap["sides"]
              if s.get("passage") == passage and s.get("front_width_cm") is not None}
    spans = {}
    for r in pre["rows"]:
        y = float(r["original"]["local_transform"]["location"][1])
        w = widths.get((r["cue_guid"], r["side"]))
        if w is None:
            continue
        spans[(r["cue_guid"], r["side"])] = ([y, y + w] if r["side"] == "left" else [y - w, y], "FLATV3_RECORDS")
    med = {}
    for side in ("left", "right"):
        vals = sorted(v[0] for k, v in spans.items() if k[1] == side)
        med[side] = vals[len(vals) // 2] if vals else ([-1000.0, -500.0] if side == "left" else [500.0, 1000.0])
    out = {}
    for g in bay_guids:
        panels = []
        for side in ("left", "right"):
            span, source = spans.get((g, side), (med[side], "OFFLINE_MEDIAN_FALLBACK"))
            panels.append({"side": side, "min": [x_lo, min(span), 0.0], "max": [x_hi, max(span), 900.0], "source": source})
        out[g] = panels
    return out, {"x_range": [x_lo, x_hi]}


def merge_flash(cues, path=NOTE_LAMPS_RECORD):
    """The swap snapshot predates the note lamps: put their drama_after flash fields on those 29 light rows."""
    rec = json.load(open(path, encoding="utf-8"))
    by_guid = {t["attachment_guid"]: t["drama_after"] for t in rec["plan"]["targets"]}
    hit = 0
    for c in cues:
        for r in c["attachments"]:
            d = by_guid.get(r["guid"])
            if d is not None:
                r.setdefault("lighting", {}).setdefault("drama", {}).update(copy.deepcopy(d))
                hit += 1
    return hit, rec.get("run")



def _plain_rows(scores, tool, show):
    """FF._runtime_plain, falling back to meshy_swap's plain rows on a build without the held P4 bulb-body fields
    (emit_point_light, ...) [meas 8 Oct live DRY: "Failed to find property"]. This tool never writes those fields."""
    try:
        return FF._runtime_plain(scores, tool, show)
    except Exception as exc:  # noqa: BLE001
        if "Failed to find property" not in str(exc):
            raise
        return MS._runtime_plain(scores, tool, show)

class OfflineBackend:
    """COUNT: everything from files. Never writes; any write call is a bug."""

    def __init__(self):
        self.logs = []

    def now(self):
        return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

    def log(self, text):
        self.logs.append(text)
        print(text)

    def log_error(self, text):
        self.logs.append(text)
        print(text)

    def context(self):
        return {"offline": True}

    def check_context(self, ctx, mode, allow_dirty):
        require(mode == "COUNT", "OFFLINE_RUNS_COUNT_ONLY")

    def census(self):
        return {"content": [], "maps": []}

    def read_state(self, args):
        passage = args["passage"]
        cues, meta = F.FC.snapshot_passage(passage)
        by_guid = {c["guid"]: c for c in cues}
        flash_hits, note_run = 0, None
        if passage == "P01":           # the note-lamp record holds the P01 route order and the flash fields
            note = json.load(open(NOTE_LAMPS_RECORD, encoding="utf-8"))
            bay_guids = [w["cue_guid"] for w in note["plan"]["route"]["wings"]]
            route_cm = {w["cue_guid"]: w["distance_cm"] for w in note["plan"]["route"]["wings"]}
        else:                          # snapshot order (show index); WingPair bays only (they carry attachments)
            bay_guids = [c["guid"] for c in cues]
            route_cm = {g: None for g in bay_guids}
        require(all(g in by_guid for g in bay_guids), "OFFLINE_BAY_MISSING")
        cues = [copy.deepcopy(by_guid[g]) for g in bay_guids]
        if passage == "P01":
            flash_hits, note_run = merge_flash(cues)
        panels, pmeta = offline_panels(bay_guids, passage)
        ident = F.xf([0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0])
        ctx_by_cue = {g: {"pair_world": ident, "station_world": ident, "across_world": [0.0, 1.0, 0.0],
                          "panels": panels[g], "route_cm": route_cm[g]} for g in bay_guids}
        swap = json.load(open(os.path.join(F.FC.MESHY_DIR, "meshy_swap_record_%s.json" % passage), encoding="utf-8"))
        sa = swap["structure_after"]
        table = F.M.load_fixture_table(check_files=False)
        lantern_name = sa["body_mesh"].rsplit("/", 1)[-1]
        lantern = {"name": lantern_name, "bounds": [table[lantern_name]["bounds_min"], table[lantern_name]["bounds_max"]],
                   "body_size": sa["body_size_cm"], "lens_centroid": table[lantern_name].get("lens_centroid")}
        other = swap["structure_before"]["other"]
        grid = {"height_cm": 1150.0, "beam_depth_cm": 180.0, "half_width_cm": 1350.0,
                "max_drop_cm": float(other["max_drop_cm"]),
                "lines_enabled": bool(other["enabled"] and other["hang_from_grid"] and other["line_mesh"])}
        self.state = {"all_cues": cues, "cues": cues, "ctx_by_cue": ctx_by_cue, "mesh_bounds": dict(LAMP_BOUNDS_OFFLINE),
                      "table": table, "caps": F.load_cap_radii(), "lantern": lantern, "grid": grid,
                      "derived_index": meta["derived_index"],
                      "floor_tops": [(-1.0e7, 1.0e7, -1.0e7, 1.0e7, 0.5, "OFFLINE_ASSUMED_FLOOR_TOP(GAP_AUDIT 0.5 cm)")],
                      "structure": {"fixture_body_count": int(sa["fixture_body_count"]), "hanging_line_count": None,
                                    "body_mesh": sa["body_mesh"], "source": "meshy_swap_record_%s structure_after" % passage},
                      "mechanisms": {}, "live_checks": {
                          "offline": True, "rows": "%s after_rows run %s" % (meta.get("meshy_run") and "meshy_swap_record_" + passage, swap.get("run")),
                          "flash_fields_from": "p01_note_lamps_record run %s (%d rows)" % (note_run, flash_hits),
                          "panels": "Saved/CodexFlatV3 hf_preflight + GAP_AUDIT + edge_x_probe x=%s" % pmeta["x_range"],
                          "pair_frames": "identity (inferred)", "lamp_bounds": "inferred pivots, measured sizes",
                          "grid": "v3 1150/180, half width 1350 (FixturesFollow defaults), max_drop %s" % other["max_drop_cm"]}}
        return self.state

    def rows_now(self):
        return {c["guid"]: c["attachments"] for c in self.state["all_cues"]}

    def foreign(self, guids, exclude):
        roots = [os.path.join(SAVED, n) for n in sorted(os.listdir(SAVED)) if n.startswith("Codex")]
        return scan_foreign_records(roots, guids, exclude)

    def __getattr__(self, name):
        raise RuntimeError("OFFLINE_BACKEND_HAS_NO_%s (COUNT never writes)" % name.upper())


TERMINAL = ("reverted", "failed_rolled_back_in_memory", "stale", "superseded", "rolled_back", "failed")


def scan_foreign_records(roots, guids, exclude=()):
    """Active *record*.json files that mention a target GUID (lighting_scores_apply.scan_foreign_records logic, pure)."""
    import glob
    wanted = {str(g).upper() for g in guids}
    excluded = {os.path.normcase(os.path.abspath(p)) for p in exclude}
    hits = []
    for root in roots:
        for path in sorted(glob.glob(os.path.join(root, "**", "*record*.json"), recursive=True)):
            if os.path.normcase(os.path.abspath(path)) in excluded or not path.endswith(".json"):
                continue
            try:
                text = open(path, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            try:
                status = str(json.loads(text).get("status", "")).lower()
            except (ValueError, AttributeError):
                status = ""
            if status in TERMINAL:
                continue
            compact = text.upper().replace("-", "")
            found = sorted(g for g in wanted if g in compact)
            if found:
                hits.append({"path": path, "status": status or None, "guid_count": len(found)})
    return hits


# ---------------------------------------------------------------------------------------------------------------
# LIVE backend (Unreal only; never executed offline). No UE object in a module global.
# ---------------------------------------------------------------------------------------------------------------
class LiveBackend:
    def __init__(self, passage="P01"):
        self.scores, self.tool = MS.load_modules()
        self.names = MS.passage_names(passage)
        self.show = None
        self.structure = None
        self.passage_actor = None
        self.has_flash = None
        self.state = None

    def now(self):
        return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

    def log(self, text):
        unreal.log(text)

    def log_error(self, text):
        unreal.log_error(text)

    def context(self):
        return MS._ctx_facts(self.tool)

    def check_context(self, ctx, mode, allow_dirty):
        require(mode != "COUNT", "COUNT_IS_OFFLINE_ONLY")
        MS.check_context(ctx, mode, allow_dirty, self.tool.SHOW_PATH, self.tool.EXPECTED_WORLD)

    def census(self):
        return self.tool._dirty_census()

    # ---- reads
    def _probe_flash(self):
        drama = unreal.InfinityStageLightDrama()
        try:
            for name in ("flash", "flash_camera_offsets_cm", "flash_attack_cm", "flash_decay_cm", "flash_rest_scale"):
                drama.get_editor_property(name)
            return True
        except Exception:  # noqa: BLE001 - absent on an unpatched build
            return False

    def _cues(self, show):
        # FF._runtime_plain also reads the P4 bulb-practical body fields (emit_point_light, ...) from a HELD C++ patch;
        # on a build without them it raises "Failed to find property" [meas 8 Oct live DRY]. This tool never writes those
        # fields, so fall back to meshy_swap's plain runtime rows (the base FF itself wraps) when they are absent.
        cues = _plain_rows(self.scores, self.tool, show)
        if self.has_flash:
            for cue_plain, cue in zip(cues, show.get_editor_property("cues")):
                for row, att in zip(cue_plain["attachments"], self.tool._pair_attachments(cue)):
                    drama = att.get_editor_property("lighting").get_editor_property("drama")
                    row["lighting"]["drama"].update({
                        "flash": bool(drama.get_editor_property("flash")),
                        "flash_camera_offsets_cm": [float(v) for v in drama.get_editor_property("flash_camera_offsets_cm")],
                        "flash_attack_cm": float(drama.get_editor_property("flash_attack_cm")),
                        "flash_decay_cm": float(drama.get_editor_property("flash_decay_cm")),
                        "flash_rest_scale": float(drama.get_editor_property("flash_rest_scale"))})
        return cues

    def _guid(self, text):
        res = unreal.GuidLibrary.parse_string_to_guid(str(text))
        guid, ok = (res if isinstance(res, tuple) else (res, True))
        require(ok and self.tool._guid_text(guid) == str(text), "GUID_PARSE|" + str(text))
        return guid

    def _anchor_world(self, cue):
        """The live pair root, exactly as materialize composes it, via the first Station row on the cue."""
        for row in cue["attachments"]:
            if F.is_station(row):
                res = self.passage_actor.get_attachment_anchor_world_transform(self._guid(cue["guid"]), self._guid(row["guid"]))
                ok, t = (res if isinstance(res, tuple) else (True, res))
                require(ok and t is not None, "ANCHOR_WORLD_FAILED|%s" % cue["label"])
                return FF._t(t)
        raise F.FloorError("NO_STATION_ROW|%s" % cue["label"])

    def read_state(self, args):
        self.show = unreal.EditorAssetLibrary.load_asset(self.tool.SHOW_PATH)
        require(self.show is not None, "SHOW_ASSET_MISSING")
        self.structure = MS._find_structure(self.show, self.names)
        self.passage_actor = self.structure.get_editor_property("passage")
        self.has_flash = self._probe_flash()
        all_cues = self._cues(self.show)
        bay_guids = [self.tool._guid_text(g) for g in self.show.get_wing_pair_cue_guids_in_passage(
            self.passage_actor.get_editor_property("passage_guid"))]
        by_guid = {c["guid"]: c for c in all_cues}
        require(bay_guids and all(g in by_guid for g in bay_guids), "BAYS_UNRESOLVED")
        cues = [by_guid[g] for g in bay_guids]
        stations = FF._stations(self.structure, self.tool)
        worlds_ff, acrosses, order = FF._pair_worlds(self.show, self.tool, stations)
        station_by_cue = {s["cue_guid"]: s["station_world"] for s in stations}
        live_checks = {"has_flash_fields": self.has_flash, "pair_frame_mismatch": []}
        ctx_by_cue = {}
        for cue in cues:
            g = cue["guid"]
            require(g in worlds_ff and g in station_by_cue, "BAY_HAS_NO_STATION|%s" % cue["label"])
            pw = self._anchor_world(cue)
            gap = F.FC.corner_gap(pw, worlds_ff[g], [-100.0] * 3, [100.0] * 3)
            if gap > PLACE_TOL_CM:
                live_checks["pair_frame_mismatch"].append({"cue": cue["label"], "corner_gap_cm": round(gap, 3)})
            ctx_by_cue[g] = {"pair_world": pw, "station_world": station_by_cue[g], "across_world": acrosses[g],
                             "panels": []}
        require(not live_checks["pair_frame_mismatch"], "PAIR_FRAME_MISMATCH|%s" % live_checks["pair_frame_mismatch"][:4])
        for ref in self.passage_actor.get_editor_property("materialized_panels"):
            g = self.tool._guid_text(ref.get_editor_property("cue_guid"))
            if g not in ctx_by_cue:
                continue
            comp = ref.get_editor_property("component")
            idx = int(ref.get_editor_property("instance_index"))
            require(comp is not None and idx >= 0, "PANEL_REF_EMPTY|%s" % g)
            mesh = comp.get_editor_property("static_mesh")
            box = mesh.get_bounding_box()
            inst = FF._t(comp.get_instance_transform(idx, True))
            pts = [F.to_pair(ctx_by_cue[g]["pair_world"], p) for p in F.corners_of(inst, FF._v(box.min), FF._v(box.max))]
            lo, hi = F.aabb(pts)
            ctx_by_cue[g]["panels"].append({"side": str(ref.get_editor_property("side")), "min": lo, "max": hi,
                                            "mesh": F.asset_id(mesh.get_path_name()), "source": "LIVE_ISM_BOUNDS"})
        mechanisms = {}
        for cue in self.show.get_editor_property("cues"):
            g = self.tool._guid_text(cue.get_editor_property("cue_guid"))
            if g not in ctx_by_cue:
                continue
            try:
                mech = cue.get_editor_property("wing_pair").get_editor_property("mechanism")
                mechanisms[g] = {"kind": str(mech.get_editor_property("kind")),
                                 "max_angle_deg": float(mech.get_editor_property("max_angle_deg")),
                                 "inward_travel_cm": float(mech.get_editor_property("inward_travel_cm"))}
            except Exception as error:  # noqa: BLE001 - report-only read (inferred names)
                mechanisms[g] = {"kind": "UNREADABLE", "error": str(error)[:200]}
        mesh_info = MS._mesh_info(self.tool, cues)
        mesh_bounds = {p: [list(v["bounds"][0]), list(v["bounds"][1])] for p, v in mesh_info.items()}
        (lo, hi), size = FF._body_mesh_bounds(self.structure)
        sstate = MS._structure_state(self.tool, self.structure)
        grid = FF._grid(self.structure)
        other = sstate["other"]
        grid.update({"max_drop_cm": float(other["max_drop_cm"]),
                     "lines_enabled": bool(other["enabled"] and other["hang_from_grid"] and other["line_mesh"]
                                           and grid.get("enabled", True))})
        derived = {}
        for p in F.FC.PASSAGES:
            rp = os.path.join(F.FC.MESHY_DIR, "meshy_swap_record_%s.json" % p)
            if os.path.isfile(rp):
                derived.update(json.load(open(rp, encoding="utf-8"))["plan"].get("derived_meshes", {}))
        hc = self.housing_check()
        live_checks["housing_before"] = hc
        live_checks["spawned_before"] = self._spawn_census(cues)
        self.state = {"all_cues": all_cues, "cues": cues, "ctx_by_cue": ctx_by_cue, "mesh_bounds": mesh_bounds,
                      "table": F.M.load_fixture_table(check_files=False), "caps": F.load_cap_radii(),
                      "lantern": {"name": F.mesh_name(sstate["body_mesh"]), "path": sstate["body_mesh"],
                                  "bounds": [lo, hi], "body_size": size,
                                  "lens_centroid": (F.M.load_fixture_table(check_files=False).get(
                                      F.mesh_name(sstate["body_mesh"])) or {}).get("lens_centroid")}, "grid": grid,
                      "derived_index": derived, "floor_tops": FF._floor_tops(args["floor_label_regex"]),
                      "structure": {"fixture_body_count": sstate["fixture_body_count"], "current": sstate["current"],
                                    "hanging_line_count": int(self.structure.get_editor_property("hanging_line_count")),
                                    "body_mesh": sstate["body_mesh"], "other": other},
                      "mechanisms": mechanisms, "live_checks": live_checks}
        return self.state

    def _spawn_census(self, cues):
        index = MS._attachment_actor_index()
        n = sum(len(index.get("%s|%s" % (c["guid"], r["guid"]), [])) for c in cues for r in c["attachments"]
                if r["enabled"] and F.role_of_label(r["label"]).startswith("PRACTICAL"))
        return {"practical_actors": n}

    def rows_now(self):
        return MS._all_rows(self._cues(self.show))

    def readback_rows(self):
        show = unreal.EditorAssetLibrary.load_asset(self.tool.SHOW_PATH)
        return MS._all_rows(self._cues(show))

    def export_hash(self, skip, readback=False):
        show = unreal.EditorAssetLibrary.load_asset(self.tool.SHOW_PATH) if readback else self.show
        return MS._export_hash(self.tool, show, set(skip))

    def foreign(self, guids, exclude):
        roots = [os.path.join(SAVED, n) for n in sorted(os.listdir(SAVED)) if n.startswith("Codex")]
        hits = self.scores.scan_foreign_records(roots, guids, exclude=exclude)
        hits += MS.scan_foreign_text(roots, [self.names["structure_label"]], exclude=exclude)
        return hits

    # ---- writes
    def backup(self, prefix, run_id):
        return self.tool._backup(prefix, run_id)

    def write_rows(self, target, values):
        """Only the listed fields of exactly these GUIDs (patterns: meshy_swap.py:524-535, lighting_looks_apply.py:1488,
        p01_note_lamps.py:1139-1154). Returns (cue index, original attachments) for rollback."""
        cues = list(self.show.get_editor_property("cues"))
        hits = [i for i, c in enumerate(cues) if self.tool._guid_text(c.get_editor_property("cue_guid")) == target["cue_guid"]]
        require(len(hits) == 1, "CUE_RESOLVE|%s|%d" % (target["cue_guid"], len(hits)))
        index = hits[0]
        require(str(cues[index].get_editor_property("label")) == target["cue_label"], "CUE_LABEL_DRIFT|" + target["cue_guid"])
        original = self.tool._pair_attachments(cues[index])
        attachments = self.tool._pair_attachments(cues[index])
        seen = 0
        for att in attachments:
            g = self.tool._guid_text(att.get_editor_property("attachment_guid"))
            if g not in values:
                continue
            row, fields = values[g]
            seen += 1
            for field in fields:
                if field == "relative_transform":
                    t = row["relative_transform"]
                    x = att.get_editor_property("relative_transform")
                    x.set_editor_property("translation", unreal.Vector(*[float(v) for v in t["location"]]))
                    x.set_editor_property("rotation", unreal.Quat(*[float(v) for v in t["rotation_xyzw"]]))
                    x.set_editor_property("scale3d", unreal.Vector(*[float(v) for v in t["scale"]]))
                    att.set_editor_property("relative_transform", x)
                elif field == "enabled":
                    att.set_editor_property("enabled", bool(row["enabled"]))
                elif field == "lighting.type":
                    lighting = att.get_editor_property("lighting")
                    lighting.set_editor_property("type", self.tool._enum_member(unreal.InfinityStageLightType,
                                                                                F.enum_name(row["lighting"]["type"])))
                    att.set_editor_property("lighting", lighting)
                elif field == "lighting.drama.flash_camera_offsets_cm":
                    require(self.has_flash, "FLASH_FIELDS_ABSENT")
                    lighting = att.get_editor_property("lighting")
                    drama = lighting.get_editor_property("drama")
                    drama.set_editor_property("flash_camera_offsets_cm",
                                              [float(v) for v in row["lighting"]["drama"]["flash_camera_offsets_cm"]])
                    lighting.set_editor_property("drama", drama)
                    att.set_editor_property("lighting", lighting)
                else:
                    raise F.FloorError("FIELD_NOT_WRITABLE|" + field)
        require(seen == len(values), "ROW_GUIDS_MISSING|%s|%d/%d" % (target["cue_label"], seen, len(values)))
        self.tool._set_pair_attachments(self.show, index, attachments)
        return index, original

    def rollback(self, tokens):
        for index, original in reversed(tokens):
            self.tool._set_pair_attachments(self.show, index, original)

    def materialize(self):
        return self.scores._materialize_passage(self.show, self.names["actor_prefix"])

    def structure_now(self):
        return {"fixture_body_count": int(self.structure.get_editor_property("fixture_body_count")),
                "hanging_line_count": int(self.structure.get_editor_property("hanging_line_count")),
                "current": bool(self.structure.is_structure_current())}

    def housing_check(self):
        _, _, _, _, _, plan = FF._follow_state(self.show, self.tool, self.structure,
                                               _plain_rows(self.scores, self.tool, self.show))
        return {"count": plan["count"], "ism_count": plan["ism_count"], "stale": plan["stale"],
                "count_matches": plan["count_matches"]}

    def verify_spawned(self, plan):
        index = MS._attachment_actor_index()
        bad, checked = [], 0
        for t in plan["targets"]:
            w = plan["ctx"][t["cue_guid"]]["pair_world"]
            for c in t["changes"]:
                row = c["after"]
                actors = index.get("%s|%s" % (t["cue_guid"], c["guid"]), [])
                if not row["enabled"]:          # disabled dead light / hidden domestic body: no actor
                    if actors:
                        bad.append({"label": c["label"], "problem": "DISABLED_ROW_HAS_ACTOR_%d" % len(actors)})
                    else:
                        checked += 1
                    continue
                if len(actors) != 1:
                    bad.append({"label": c["label"], "problem": "ACTOR_COUNT_%d" % len(actors)})
                    continue
                a = actors[0]
                want = F.xf_point(w, row["relative_transform"]["location"])
                got = FF._v(a.get_actor_location())
                if F.FC.dist(want, got) > PLACE_TOL_CM:
                    bad.append({"label": c["label"], "problem": "PLACE", "want": want, "got": got})
                    continue
                if c["what"] == "UPLIGHT_LIGHT_TO_FLOOR":
                    want_class = {"SPOT": "SpotLight", "POINT": "PointLight", "RECT": "RectLight"}[F.enum_name(row["lighting"]["type"])]
                    throw = F.quat_rotate(F.xf_compose(row["relative_transform"], w)["rotation_xyzw"], [1.0, 0.0, 0.0])
                    fwd = FF._v(a.get_actor_forward_vector())
                    err = math.degrees(math.acos(max(-1.0, min(1.0, F.FC.dot(F.FC.norm(fwd), F.FC.norm(throw))))))
                    if a.get_class().get_name() != want_class or err > AIM_TOL_DEG:
                        bad.append({"label": c["label"], "problem": "LIGHT_CLASS_OR_AIM", "class": a.get_class().get_name(),
                                    "aim_err_deg": err})
                        continue
                else:
                    comp = a.get_editor_property("static_mesh_component") if a.get_class().get_name() == "StaticMeshActor" else None
                    mesh = F.asset_id(comp.get_editor_property("static_mesh").get_path_name()) if comp else None
                    if mesh != F.asset_id(row.get("mesh")):
                        bad.append({"label": c["label"], "problem": "MESH", "mesh": mesh})
                        continue
                checked += 1
        require(not bad, "SPAWNED|%s" % F.canonical(bad)[:2500])
        return checked

    def save_narrow(self):
        self.tool._save_narrow()


# ---------------------------------------------------------------------------------------------------------------
def _load_all():
    global F, FF, MS
    F = load_common()
    FF = load_fixfollow(F)
    MS = FF.load_meshy_swap()
    FF.MS = MS


def main():
    _load_all()
    require(unreal is not None, "UNREAL_REQUIRED")
    try:
        args = check_args(globals().get("P01FLOOR_ARGS"))
        require(args["mode"] != "COUNT", "COUNT_IS_OFFLINE_ONLY")
        be = LiveBackend(args["passage"])
    except Exception as error:  # noqa: BLE001
        unreal.log_error("%s_STOPPED|run=none|ARGS|%s: %s|NOTHING SAVED" % (MARK, type(error).__name__, error))
        raise
    return run(args, be)


def count_cli(argv=None):
    _load_all()
    argv = list(sys.argv[1:] if argv is None else argv)
    raw = {"mode": "COUNT"}
    if argv:
        with open(argv[0], encoding="utf-8") as handle:
            raw = json.load(handle)
        raw["mode"] = "COUNT"
        raw.pop("confirm", None)
    args = check_args(raw)
    return run(args, OfflineBackend())


if __name__ == "__main__" and unreal is None:
    count_cli()


if unreal is not None:
    main()
