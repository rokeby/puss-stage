"""READ-ONLY lighting drift report: every scores after-row vs the live Show, classified by who changed it.

Why. lighting_scores_apply.py REVERT refuses REVERT_CURRENT_STATE_DRIFT at the FIRST target cue whose live
attachment rows differ from the record's after_rows (lighting_scores_apply.py:2291-2292, inside _mutate_revert
:2279). On 6 Oct both P01 and P02 refused, so nobody can see how much else has drifted behind the first cue.
This tool walks EVERY target of EVERY active lighting_scores_record_P0N.json and reports all of it.

Same definition of drift (no copy). The comparison is the scores tool's own: it is loaded from
lighting_scores_apply.py (main() guard stripped, as rig_lamp_drop.py:722-735 does), then its own
load_p04_tool() (lighting_scores_apply.py:245) supplies the P04 tool, whose
_require_attachment_rows_equal(actual, expected, message) (lighting_looks_apply.py:1277-1280) calls
S.state_differences(expected, actual) (_infinity_attachment_state.py:131-156) on rows from
_attachment_rows -> S.attachment_state (lighting_looks_apply.py:1265-1270, _infinity_attachment_state.py:104-129).
The live cue is resolved with the scores tool's own _current_target (lighting_scores_apply.py:1871-1880),
which REVERT also uses first, so an index/label drift refusal is reported exactly as REVERT would raise it.
The per-cue verdict is the exception that _require_attachment_rows_equal itself raises (or not).

Attribution (only for reporting; never changes the verdict). Each differing FIELD of each differing light is
compared with the attachment-state snapshots in the other tools' records:
  * any non-terminal Saved/CodexConductor/*record*.json holding attachment rows (dicts with guid + lighting /
    relative_transform) under a key containing "before"/"original" or "after" (rig_lamp_drop_record_*,
    p03_housing_drop_record, lighting_events_revert_record, lighting_looks_revert_record, other passages'
    score records). A field is EXPLAINED by record R when R.after[field] == live and R.before[field] !=
    R.after[field] (R wrote it); "chain_exact" when also R.before[field] == the scores after value.
    If R.before == R.after == live, R did NOT write it, but the value already existed when R ran: noted as
    present_at=<R.run>, which dates the change, and the field stays UNKNOWN.
  * opening_sequence_record.json: only the planner's WARMER_WRITE_PATHS (opening_sequence_plan.py:62) on the
    labels in warmers_attachment_original, compared with opening_sequence_report_apply.json
    house_warmer_write.targets (the last APPLY's targets) and .changes (what that run actually wrote).
  * p04_strobe_halo: writes three UPROPERTYs on ONE level actor (p04_strobe_halo.py:1-8, 40-42), never a Show
    attachment; its p04_strobe_halo_*.json files are text-scanned for the GUID anyway.
  * any other active record that merely NAMES the GUID (scores' own scan_foreign_records,
    lighting_scores_apply.py:1667-1696) and models no field: OTHER_RECORD:<file> (write not modelled).
  * otherwise UNKNOWN (likely hand edit).

READ-ONLY: no setter, no modify(), no save, no backup, no record written. The only writes are this tool's
report JSON + markdown under Saved/CodexConductor/. Dirty census and a hash of every WingPair row are taken
before and after and must be equal. Success marker: LIGHTING_DRIFT_REPORT_OK|run=<id> (only after both
asserts and the report write). Stop marker: LIGHTING_DRIFT_REPORT_STOPPED|run=<id>|<reason>.

Proof tiers (AGENTS.md): the comparator identity is declaration-proven (the file:line above; we call the
functions, not a copy). Attribution is a heuristic over records: a record-explained field is
"record-proven" (the record's own before/after snapshot shows the write), an opening field written by the
last APPLY is record-proven, an opening field that only equals the target is INFERRED, and UNKNOWN means no
record models it; that it is a hand edit is INFERRED (Gary's editor tuning is the only other writer known).
"""
from __future__ import annotations

import ast
import copy
import datetime
import glob
import hashlib
import json
import os
import types

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # offline harness import
    unreal = None


HERE = os.path.dirname(os.path.abspath(__file__))
SCORES_TOOL_PATH = os.path.join(HERE, "lighting_scores_apply.py")
OPENING_RECORD = "opening_sequence_record.json"
OPENING_REPORT = "opening_sequence_report_apply.json"
OPENING_PLAN = "opening_sequence_plan.py"
# Mirror of opening_sequence_plan.WARMER_WRITE_PATHS (opening_sequence_plan.py:62); load_opening_info()
# re-reads the planner source and refuses if it changed.
WARMER_WRITE_FIELDS = ("enabled", "lighting.inner_cone_angle_degrees")
PASSAGES = ("P01", "P02", "P03", "P04", "P05", "P06")
ACTIVE_STATUS = "saved_readback_verified"   # REVERT refuses any other (lighting_scores_apply.py:2225)
UNKNOWN = "UNKNOWN (likely hand edit)"
EXPECTED_CLASSES = {"RIG_LAMP_DROP", "P03_HOUSING_DROP"}  # TOP lamp z lowered under the girder (Gary 5 Oct)
MISSING = object()
REPORT_JSON = os.path.join(HERE, "lighting_drift_report.json")


class DriftReportError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise DriftReportError(message)


# --------------------------------------------------------------------------
# Loading the scores tool (its main() guard stripped) and through it the P04 tool.
# --------------------------------------------------------------------------
def _is_main_guard(node):
    if not isinstance(node, ast.If) or node.orelse or len(node.body) != 1:
        return False
    test = node.test
    if not (isinstance(test, ast.Compare) and isinstance(test.left, ast.Name) and test.left.id == "unreal"
            and len(test.ops) == 1 and isinstance(test.ops[0], ast.IsNot)
            and isinstance(test.comparators[0], ast.Constant) and test.comparators[0].value is None):
        return False
    stmt = node.body[0]
    return (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Name) and stmt.value.func.id == "main"
            and not stmt.value.args and not stmt.value.keywords)


def _top_level_inert(node, index):
    if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef, ast.Assign, ast.AnnAssign)):
        return True
    if isinstance(node, ast.Expr):  # only the module docstring
        return index == 0 and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
    if isinstance(node, ast.Try):
        inner = list(node.body) + [s for h in node.handlers for s in h.body] + list(node.orelse) + list(node.finalbody)
        return all(isinstance(s, (ast.Import, ast.ImportFrom, ast.Assign)) for s in inner)
    return False


def load_without_main(path, module_name):
    with open(path, "rb") as handle:
        raw = handle.read()
    tree = ast.parse(raw.decode("utf-8"), filename=path)
    require(tree.body and _is_main_guard(tree.body[-1])
            and sum(1 for n in tree.body if _is_main_guard(n)) == 1, "MAIN_GUARD_SHAPE|" + path)
    for index, node in enumerate(tree.body[:-1]):
        require(_top_level_inert(node, index), "TOP_LEVEL_SIDE_EFFECT|%s|line=%d" % (path, getattr(node, "lineno", -1)))
    tree.body = tree.body[:-1]
    module = types.ModuleType(module_name)
    module.__file__ = path
    exec(compile(tree, path, "exec"), module.__dict__)  # noqa: S102 - reviewed project file
    module.SOURCE_SHA256 = hashlib.sha256(raw).hexdigest()
    return module


SCORES_REQUIRED = ("load_p04_tool", "_current_target", "_record_path", "scan_foreign_records")
TOOL_REQUIRED = ("_attachment_rows", "_require_attachment_rows_equal", "_state_differences", "_dirty_census",
                 "_all_pair_rows", "_rows_hash", "_guid_text", "SHOW_PATH")


def load_modules(scores_path=SCORES_TOOL_PATH):
    scores = load_without_main(scores_path, "_lighting_scores_for_drift_report")
    missing = [n for n in SCORES_REQUIRED if not callable(getattr(scores, n, None))]
    require(not missing, "SCORES_API_DRIFT|" + ",".join(missing))
    tool = scores.load_p04_tool()
    missing = [n for n in TOOL_REQUIRED if not hasattr(tool, n)]
    require(not missing, "P04_TOOL_API_DRIFT|" + ",".join(missing))
    return scores, tool


# --------------------------------------------------------------------------
# Pure helpers (offline-tested).
# --------------------------------------------------------------------------
def _tokens(path):
    out = []
    for part in path.split("."):
        while "[" in part:
            head, rest = part.split("[", 1)
            if head:
                out.append(head)
            index, part = rest.split("]", 1)
            out.append(int(index))
        if part:
            out.append(part)
    return out


def get_path(value, path):
    for token in _tokens(path):
        if isinstance(token, int):
            if not isinstance(value, list) or token >= len(value):
                return MISSING
            value = value[token]
        else:
            if not isinstance(value, dict) or token not in value:
                return MISSING
            value = value[token]
    return value


def field_of(path):
    """'lighting.color[2]' -> 'lighting.color'; 'relative_transform.location[2]' keeps the component."""
    if path.startswith("relative_transform.location[") or path.startswith("relative_transform.scale["):
        return path
    while path.endswith("]") and "[" in path:
        path = path[: path.rfind("[")]
    return path


def changed_fields(differences):
    seen = []
    for diff in differences:
        field = field_of(diff["path"])
        if field not in seen:
            seen.append(field)
    return seen


def revert_verdict(tool, after_rows, current_rows, message):
    """Exactly REVERT's check (lighting_scores_apply.py:2291-2292): the tool's own raise, or None."""
    try:
        tool._require_attachment_rows_equal(current_rows, after_rows, message)
    except Exception as error:  # noqa: BLE001 - the tool's own refusal is the verdict
        return str(error)
    return None


def diff_target(tool, after_rows, current_rows):
    positional = tool._state_differences(after_rows, current_rows)  # same call order as the tool
    after_by = {str(r["guid"]): r for r in after_rows}
    current_by = {str(r["guid"]): r for r in current_rows}
    by_guid = {}
    for guid in [str(r["guid"]) for r in after_rows]:
        if guid in current_by:
            diffs = tool._state_differences(after_by[guid], current_by[guid])
            if diffs:
                by_guid[guid] = diffs
    after_order = [str(r["guid"]) for r in after_rows]
    current_order = [str(r["guid"]) for r in current_rows]
    return {
        "positional_difference_count": len(positional),
        "positional_first": positional[:3],
        "by_guid": by_guid,
        "removed_guids": [g for g in after_order if g not in current_by],
        "added_guids": [g for g in current_order if g not in after_by],
        "order_changed": ([g for g in after_order if g in current_by]
                          != [g for g in current_order if g in after_by]),
    }


def record_class(path):
    base = os.path.basename(path).lower()
    if base.startswith("opening_sequence"):
        return "OPENING_SEQUENCE_WARMERS"
    if base.startswith("rig_lamp_drop"):
        return "RIG_LAMP_DROP"
    if base.startswith("p03_housing_drop"):
        return "P03_HOUSING_DROP"
    if base.startswith("lighting_events"):
        return "LIGHTING_EVENTS"
    if base.startswith("p04_strobe_halo"):
        return "P04_STROBE_HALO"
    return "OTHER_RECORD:" + os.path.basename(path)


def index_record_snapshots(data):
    """{GUID: {'before': row, 'after': row}} from any attachment rows under before/original/after keys."""
    out = {}

    def walk(node, role):
        if isinstance(node, dict):
            if isinstance(node.get("guid"), str) and ("lighting" in node or "relative_transform" in node):
                if role:
                    out.setdefault(node["guid"].replace("-", "").upper(), {}).setdefault(role, node)
                return
            for key, child in node.items():
                lowered = str(key).lower()
                child_role = role
                if "after" in lowered:
                    child_role = "after"
                elif "before" in lowered or "original" in lowered:
                    child_role = "before"
                walk(child, child_role)
        elif isinstance(node, list):
            for child in node:
                walk(child, role)

    walk(data, None)
    return out


def load_foreign_records(root, exclude, terminal):
    """[{path, class, status, run, snapshots}] for every non-terminal *record*.json except ``exclude``."""
    excluded = {os.path.normcase(os.path.abspath(p)) for p in exclude}
    out = []
    for path in sorted(glob.glob(os.path.join(root, "*record*.json"))):
        if os.path.normcase(os.path.abspath(path)) in excluded:
            continue
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        status = str(data.get("status", "")).lower()
        if status in terminal:
            continue
        snaps = index_record_snapshots(data)
        if os.path.basename(path) == OPENING_RECORD:
            snaps = {}  # warmers_attachment_original is the PRE-first-write state; modelled by load_opening_info
        if snaps:
            out.append({"path": path, "class": record_class(path), "status": status or None,
                        "run": data.get("run"), "snapshots": snaps})
    return out


def load_opening_info(root):
    """{GUID: {label, fields, targets, changes, run}} for the opening tool's two house warmers, or {}."""
    record_path = os.path.join(root, OPENING_RECORD)
    if not os.path.isfile(record_path):
        return {}
    plan_path = os.path.join(root, OPENING_PLAN)
    if os.path.isfile(plan_path):
        with open(plan_path, encoding="utf-8") as handle:
            source = handle.read()
        require('WARMER_WRITE_PATHS = (("enabled",), ("lighting", "inner_cone_angle_degrees"))' in source,
                "OPENING_WARMER_WRITE_PATHS_CHANGED|re-read opening_sequence_plan.py:62")
    with open(record_path, encoding="utf-8") as handle:
        record = json.load(handle)
    report = {}
    report_path = os.path.join(root, OPENING_REPORT)
    if os.path.isfile(report_path):
        with open(report_path, encoding="utf-8") as handle:
            report = json.load(handle)
    write = report.get("house_warmer_write") or {}
    targets = write.get("targets") or {}
    changes = set(write.get("changes") or [])
    out = {}
    for label, row in (record.get("warmers_attachment_original") or {}).items():
        guid = str(row.get("guid", "")).replace("-", "").upper()
        tgt = targets.get(label) or {}
        out[guid] = {
            "label": label, "fields": list(WARMER_WRITE_FIELDS), "record_status": record.get("status"),
            "report_run": report.get("run"),
            "targets": {"enabled": tgt.get("enabled", MISSING),
                        "lighting.inner_cone_angle_degrees": tgt.get("inner_cone_angle_degrees", MISSING)},
            "written_by_last_run": {f for f in WARMER_WRITE_FIELDS if "%s:%s" % (label, f) in changes},
        }
    return out


def text_mentions(path, guids):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            text = handle.read().upper().replace("-", "")
    except OSError:
        return []
    return [g for g in guids if g in text]


def mentions_by_guid(hits, modelled_paths):
    """{GUID: [paths]} from text hits, minus records whose writes are modelled field-by-field (a modelled
    record that does not explain a field must not 'explain' it by merely naming the GUID)."""
    modelled = {os.path.normcase(os.path.abspath(p)) for p in modelled_paths}
    out = {}
    for hit in hits:
        if os.path.normcase(os.path.abspath(hit["path"])) in modelled:
            continue
        for guid in hit["guids"]:
            out.setdefault(guid, []).append(hit["path"])
    return out


def _same(a, b):
    return a is not MISSING and b is not MISSING and a == b


def classify_field(guid, field, recorded, current, foreign, opening, mentions):
    """One differing field -> {class, tier, evidence[], notes[]}."""
    evidence, notes = [], []
    info = opening.get(guid)
    if info and field in info["fields"]:
        target = info["targets"].get(field, MISSING)
        if _same(target, current):
            written = field in info["written_by_last_run"]
            evidence.append({"class": "OPENING_SEQUENCE_WARMERS", "record": OPENING_RECORD,
                             "run": info["report_run"],
                             "tier": "record-proven (written by the last opening APPLY)" if written else
                             "inferred (equals the opening APPLY target; not written by its last run)"})
        elif target is not MISSING:
            notes.append("opening write path, but live %r != opening target %r" % (current, target))
        else:
            evidence.append({"class": "OPENING_SEQUENCE_WARMERS", "record": OPENING_RECORD, "run": None,
                             "tier": "inferred (opening write path; no apply target to compare)"})
    for rec in foreign:
        snap = rec["snapshots"].get(guid)
        if not snap or "after" not in snap:
            continue
        a = get_path(snap["after"], field)
        b = get_path(snap["before"], field) if "before" in snap else MISSING
        if not _same(a, current):
            if "before" in snap and b is not MISSING and a is not MISSING and a != b:
                notes.append("%s wrote %r but live is %r (changed after %s)"
                             % (os.path.basename(rec["path"]), a, current, rec["run"]))
            continue
        if field == "guid" and "before" not in snap:
            evidence.append({"class": rec["class"], "record": os.path.basename(rec["path"]), "run": rec["run"],
                             "chain_exact": True, "tier": "record-proven (row only in the record's after rows)"})
        elif "before" in snap and b is not MISSING and b != a:
            evidence.append({"class": rec["class"], "record": os.path.basename(rec["path"]), "run": rec["run"],
                             "chain_exact": _same(b, recorded),
                             "tier": "record-proven (record before->after wrote this value)"})
        elif "before" in snap and b is not MISSING:
            notes.append("present_at=%s (%s saw it already, did not write it)"
                         % (rec["run"], os.path.basename(rec["path"])))
        else:
            evidence.append({"class": rec["class"], "record": os.path.basename(rec["path"]), "run": rec["run"],
                             "chain_exact": False, "tier": "inferred (matches an after snapshot; no before)"})
    if evidence:
        evidence.sort(key=lambda e: (not e.get("chain_exact", False), e["tier"].startswith("inferred")))
        return {"class": evidence[0]["class"], "tier": evidence[0]["tier"], "evidence": evidence, "notes": notes}
    named = mentions.get(guid) or []
    if named:
        return {"class": record_class(named[0]), "tier": "inferred (record names the GUID; field write not modelled)",
                "evidence": [{"record": os.path.basename(p)} for p in named], "notes": notes}
    return {"class": UNKNOWN, "tier": "inferred (no record models this write)", "evidence": [], "notes": notes}


def light_class(field_rows):
    classes = [row["class"] for row in field_rows]
    if UNKNOWN in classes:
        return UNKNOWN
    return "+".join(sorted(set(classes)))


def slot_map(target):
    fixtures = {f["label"]: f for f in target.get("fixtures", [])}
    out = {}
    for added in target.get("added", []):
        fx = fixtures.get(added["label"]) or {}
        out[str(added["guid"])] = {"slot": fx.get("slot", "?"), "role": fx.get("role")}
    for guid in target.get("retained_guids", []):
        out.setdefault(str(guid), {"slot": "RETAINED (pre-score, kept lit)", "role": None})
    return out


def analyse_target(tool, target, current_rows, foreign, opening, mentions, resolve_error=None):
    label = target["cue_label"]
    verdict = resolve_error or revert_verdict(
        tool, target["after_rows"], current_rows, "REVERT_CURRENT_STATE_DRIFT|cue=" + label)
    diff = diff_target(tool, target["after_rows"], current_rows)
    after_by = {str(r["guid"]): r for r in target["after_rows"]}
    current_by = {str(r["guid"]): r for r in current_rows}
    slots = slot_map(target)
    lights = []
    for guid, diffs in diff["by_guid"].items():
        fields = []
        for field in changed_fields(diffs):
            old, new = get_path(after_by[guid], field), get_path(current_by[guid], field)
            row = classify_field(guid, field, old, new, foreign, opening, mentions)
            row.update({"field": field, "old": None if old is MISSING else old, "new": None if new is MISSING else new})
            fields.append(row)
        slot = slots.get(guid, {"slot": "PRE-SCORE (disabled by the score)", "role": None})
        lights.append({"guid": guid, "label": after_by[guid]["label"], "kind": after_by[guid].get("kind"),
                       "slot": slot["slot"], "role": slot["role"], "class": light_class(fields),
                       "fields": fields})
    for guid in diff["removed_guids"]:
        lights.append({"guid": guid, "label": after_by[guid]["label"], "slot": slots.get(guid, {}).get("slot"),
                       "class": UNKNOWN, "fields": [{"field": "<row removed>", "class": UNKNOWN,
                                                     "old": "present", "new": "absent",
                                                     "tier": "inferred", "evidence": [], "notes": []}]})
    for guid in diff["added_guids"]:
        row = classify_field(guid, "guid", MISSING, guid, foreign, opening, mentions)
        row.update({"field": "<row added>", "old": "absent", "new": current_by[guid]["label"]})
        lights.append({"guid": guid, "label": current_by[guid]["label"], "slot": "NEW (not in record)",
                       "class": light_class([row]), "fields": [row]})
    consistent = (verdict is None) == (diff["positional_difference_count"] == 0) or bool(resolve_error)
    return {"cue_label": label, "cue_guid": target["cue_guid"], "show_index": target["show_index"],
            "revert_verdict": verdict, "drift": verdict is not None, "resolve_error": resolve_error,
            "order_changed": diff["order_changed"], "positional_difference_count": diff["positional_difference_count"],
            "comparator_consistent": consistent, "lights": lights}


def summarise_passage(passage, record_status, cues):
    counts, field_counts = {}, {}
    for cue in cues:
        for light in cue["lights"]:
            counts[light["class"]] = counts.get(light["class"], 0) + 1
            for field in light["fields"]:
                field_counts[field["class"]] = field_counts.get(field["class"], 0) + 1
    first = next((c for c in cues if c["drift"]), None)
    return {"passage": passage, "record_status": record_status, "targets": len(cues),
            "drifted_cues": sum(1 for c in cues if c["drift"]),
            "revert_would_stop_at": None if first is None else first["revert_verdict"].split("|differences=")[0],
            "lights_by_class": dict(sorted(counts.items())), "fields_by_class": dict(sorted(field_counts.items())),
            "expected_only": bool(counts) and set(counts) <= EXPECTED_CLASSES,
            "cues": cues}


def _fmt(value):
    if isinstance(value, float):
        return "%.4g" % value
    if isinstance(value, list):
        return "[" + ", ".join(_fmt(v) for v in value) + "]"
    if isinstance(value, str) and value.startswith("<") and ": " in value:
        return value.split(".")[-1].split(":")[0]  # '<InfinityStageLightType.SPOT: 0>' -> 'SPOT'
    return str(value)


def render_markdown(report):
    lines = ["# Lighting drift: scores records vs live Show (%s)" % report["run"], "",
             "Generated read-only by `Saved/CodexConductor/lighting_drift_report.py` (run `%s`). "
             "Drift = the scores REVERT's own comparison (`_require_attachment_rows_equal`, "
             "lighting_looks_apply.py:1277); every target cue is checked, not just the first. "
             "Classes are attributed from other tools' records; UNKNOWN is *inferred* to be a hand edit." % report["run"],
             "", "Census before == after: %s. Full JSON: `Saved/CodexConductor/lighting_drift_report.json`."
             % report["census_equal"], ""]
    for p in report["passages"]:
        lines.append("## %s" % p["passage"])
        if p.get("skipped"):
            lines += ["", "Skipped: %s" % p["skipped"], ""]
            continue
        lines += ["", "- targets %d, drifted cues %d; REVERT would stop at: `%s`"
                  % (p["targets"], p["drifted_cues"], p["revert_would_stop_at"]),
                  "- lights by class: %s" % (", ".join("%s %d" % kv for kv in p["lights_by_class"].items()) or "none"),
                  "- fields by class: %s" % (", ".join("%s %d" % kv for kv in p["fields_by_class"].items()) or "none"),
                  ""]
        hand = [(c, l) for c in p["cues"] for l in c["lights"] if l["class"] == UNKNOWN]
        other = [(c, l) for c in p["cues"] for l in c["lights"]
                 if l["class"] != UNKNOWN and l["class"] not in EXPECTED_CLASSES]
        for title, rows in (("Hand edits (UNKNOWN, inferred)", hand), ("Other attributed changes", other)):
            if not rows:
                continue
            lines += ["**%s**" % title, "", "| cue | light | slot | field: old -> new (field class if different) |",
                      "|---|---|---|---|"]
            for cue, light in rows:
                cells = "<br>".join("%s: %s -> %s%s" % (f["field"], _fmt(f["old"]), _fmt(f["new"]),
                                                         "" if f["class"] == light["class"] else " (%s)" % f["class"])
                                    for f in light["fields"])
                lines.append("| %s | %s | %s | %s |" % (cue["cue_label"], light["label"], light["slot"], cells))
            lines.append("")
        odd = [c["cue_label"] for c in p["cues"] if c["order_changed"] or c["resolve_error"]
               or not c["comparator_consistent"]]
        if odd:
            lines += ["Structural/resolve notes: " + ", ".join(odd), ""]
    return "\n".join(lines) + "\n"


SOURCE_FORBIDDEN = ("set_editor_property", "modify", "save_", "_save_narrow", "_backup", "_set_pair_attachments",
                    "delete", "rename", "materialize")


def forbidden_calls(path=None):
    """Self-audit: attribute/name calls in THIS file that could write. Must return [] (harness asserts)."""
    with open(path or os.path.abspath(__file__), encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            if any(bad in name for bad in SOURCE_FORBIDDEN):
                hits.append("%s:%d" % (name, node.lineno))
    return hits


# --------------------------------------------------------------------------
# Unreal runtime (never executed offline). No UE object is kept in a global.
# --------------------------------------------------------------------------
def _fallback_target(tool, show, target):
    for cue in show.get_editor_property("cues"):
        if tool._guid_text(cue.get_editor_property("cue_guid")) == target["cue_guid"]:
            return list(cue.get_editor_property("wing_pair").get_editor_property("attachments"))
    return None


def _write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _run(run):
    scores, tool = load_modules()
    census_before = tool._dirty_census()
    show = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
    require(show is not None, "SHOW_ASSET_MISSING")
    rows_hash_before = tool._rows_hash(tool._all_pair_rows(show))
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    terminal = set(scores.TERMINAL_STATUSES)
    opening = load_opening_info(HERE)
    all_foreign = load_foreign_records(HERE, [], terminal)  # parsed once; each passage drops its own record
    report = {"run": run, "read_only": True, "census_before": census_before,
              "pie_active": editor.get_game_world() is not None,
              "scores_tool_sha256": scores.SOURCE_SHA256, "p04_tool_sha256": tool.SCORES_SOURCE_SHA256,
              "opening_warmers": {g: {"label": i["label"], "targets": {k: (None if v is MISSING else v)
                                                                       for k, v in i["targets"].items()},
                                      "written_by_last_run": sorted(i["written_by_last_run"]),
                                      "report_run": i["report_run"]} for g, i in opening.items()},
              "passages": []}
    for passage in PASSAGES:
        record_path = scores._record_path(passage)
        if not os.path.isfile(record_path):
            report["passages"].append({"passage": passage, "skipped": "no active record"})
            continue
        with open(record_path, encoding="utf-8") as handle:
            record = json.load(handle)
        if record.get("status") != ACTIVE_STATUS:
            report["passages"].append({"passage": passage, "skipped": "record status %s" % record.get("status")})
            continue
        plan = record["plan"]
        if record.get("passage") != passage:  # REVERT_RECORD_PASSAGE (lighting_scores_apply.py:2226)
            report["passages"].append({"passage": passage, "skipped": "record passage %s" % record.get("passage")})
            continue
        own = os.path.normcase(os.path.abspath(record_path))
        foreign = [r for r in all_foreign if os.path.normcase(os.path.abspath(r["path"])) != own]
        guids = sorted({str(r["guid"]) for t in plan["targets"] for r in t["after_rows"]})
        hits = scores.scan_foreign_records([HERE], guids, exclude=[record_path])
        hits += [{"path": p, "guids": text_mentions(p, guids)}
                 for p in sorted(glob.glob(os.path.join(HERE, "p04_strobe_halo_*.json")))]
        mentions = mentions_by_guid(hits, [r["path"] for r in foreign] + [os.path.join(HERE, OPENING_RECORD)])
        cues = []
        for target in plan["targets"]:
            resolve_error = None
            try:
                unused_index, attachments = scores._current_target(tool, show, target)
            except Exception as error:  # noqa: BLE001 - REVERT would stop here with this exact message
                resolve_error = str(error)
                attachments = _fallback_target(tool, show, target)
            if attachments is None:
                cues.append({"cue_label": target["cue_label"], "cue_guid": target["cue_guid"], "drift": True,
                             "revert_verdict": resolve_error, "resolve_error": resolve_error, "lights": [],
                             "order_changed": False, "comparator_consistent": True})
                continue
            current_rows = tool._attachment_rows(attachments)
            cues.append(analyse_target(tool, target, current_rows, foreign, opening, mentions, resolve_error))
        summary = summarise_passage(passage, record.get("status"), cues)
        summary["record_run"] = record.get("run")
        summary["foreign_records_with_rows"] = [os.path.basename(r["path"]) for r in foreign]
        report["passages"].append(summary)
    rows_hash_after = tool._rows_hash(tool._all_pair_rows(show))
    census_after = tool._dirty_census()
    report.update({"census_after": census_after, "census_equal": census_after == census_before,
                   "pair_rows_hash_before": rows_hash_before, "pair_rows_hash_after": rows_hash_after})
    require(census_after == census_before, "CENSUS_CHANGED|before=%s|after=%s" % (census_before, census_after))
    require(rows_hash_after == rows_hash_before, "SHOW_ROWS_CHANGED_DURING_READ")
    md_path = os.path.join(HERE, "LIGHTING_DRIFT_%s.md" % datetime.date.today().isoformat())
    with open(REPORT_JSON, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1, sort_keys=True, default=str)
    _write_text(md_path, render_markdown(report))
    report["markdown"] = md_path
    return report


def main():
    require(unreal is not None, "UNREAL_REQUIRED")
    run = "DRIFT-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    try:
        report = _run(run)
    except Exception as error:  # noqa: BLE001
        unreal.log_error("LIGHTING_DRIFT_REPORT_STOPPED|run=%s|%s: %s" % (run, type(error).__name__, error))
        raise
    parts = []
    for p in report["passages"]:
        if p.get("skipped"):
            parts.append("%s=skip" % p["passage"])
        else:
            parts.append("%s=%d/%d:unknown%d" % (p["passage"], p["drifted_cues"], p["targets"],
                                                p["lights_by_class"].get(UNKNOWN, 0)))
    unreal.log("LIGHTING_DRIFT_REPORT_OK|run=%s|census_equal=1|rows_hash_equal=1|%s|json=%s|md=%s|mutated=0"
               % (run, ",".join(parts), REPORT_JSON, report["markdown"]))


if unreal is not None:
    main()
