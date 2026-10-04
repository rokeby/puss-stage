"""OFFLINE comparer: light_guid_audit_<stamp>.json against every known baseline.

Usage (plain Python, no Unreal):
    python light_guid_audit_compare.py [dump.json]   # default: newest audit dump
    python light_guid_audit_compare.py --chain        # baseline-only checks, no dump
    python light_guid_audit_compare.py --selftest     # +/- controls

Baselines (each says what it covers; anything else is NOT COVERED):
  LL_HASH      every saved lighting_looks revert record (12:30..20:11 local, 3 Oct):
               sha256 over the full attachment_state rows of EVERY cue except
               P04 Wing 001-006, recomputed from the dump. All fields, all kinds,
               GUIDs and counts. Binary verdict: cannot say WHICH cue differs.
  LL_TARGETS   live lighting_looks_revert_record.json: P04 Wing 001-006
               after_rows (in-plan expected state, full fields).
  PF_P05_1131  swapkit pf_preflight_FV3PF-20261003-04.json (11:31 local, before
               the candle and before any lighting-looks apply): P05 cues
               idx 122-214, full attachment export text (all fields).
  CANDLE_1138  fx_candle_s6_record.json: scratch P06 Wing 054 full rows before
               the 11:38 apply; target P06 Wing 055 rows before + the 2 minted
               GUIDs expected after.
  FB_DRY_2056  fence fb_dry_FV3FB-20261003-02.json (20:56 local, after my last
               apply, before the other stream's unsaved mint): attachment GUID
               lists (all kinds) for every Wing Pair, keyed by LABEL (labels
               that repeat in the Show, e.g. P05, are reported AMBIGUOUS).
"""
from __future__ import annotations

import copy
import glob
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SAVED = os.path.dirname(HERE)
LL_RECORD_GLOB = os.path.join(HERE, "lighting_looks_revert_record.json*")
LL_LIVE_RECORD = os.path.join(HERE, "lighting_looks_revert_record.json")
LL_FAILED_1206 = os.path.join(HERE, "lighting_looks_revert_record.json.failed-20261003-120646")
PF_P05 = os.path.join(SAVED, "CodexFlatV3", "swapkit", "pf_preflight_FV3PF-20261003-04.json")
CANDLE = os.path.join(HERE, "fx_candle_s6_record.json")
FB_DRY = os.path.join(SAVED, "CodexFlatV3", "fence", "fb_dry_FV3FB-20261003-02.json")


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _canonical(value):  # identical to lighting_looks_apply._canonical
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _state_hash(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _fingerprint(state):  # identical to fx_candle_s6._attachment_fingerprint
    return json.dumps(state, sort_keys=True, separators=(",", ":"))


def diff(before, after, path=""):
    if isinstance(before, dict) and isinstance(after, dict):
        out = []
        for key in sorted(set(before) | set(after)):
            child = "%s.%s" % (path, key) if path else str(key)
            if key not in before or key not in after:
                out.append(child)
            else:
                out.extend(diff(before[key], after[key], child))
        return out
    if isinstance(before, list) and isinstance(after, list):
        out = []
        for i in range(max(len(before), len(after))):
            child = "%s[%d]" % (path, i)
            if i >= len(before) or i >= len(after):
                out.append(child)
            else:
                out.extend(diff(before[i], after[i], child))
        return out
    return [] if before == after else [path or "<value>"]


# ---------------------------------------------------------------- export text
def parse_export(text):
    """Parse UE struct export text into nested dict/list/str."""
    value, pos = _parse_value(text, 0)
    return value


def _parse_value(s, i):
    if i < len(s) and s[i] == "(":
        return _parse_group(s, i)
    if i < len(s) and s[i] == '"':
        j = i + 1
        while j < len(s) and s[j] != '"':
            j += 2 if s[j] == "\\" else 1
        return s[i:j + 1], j + 1
    depth, j, quoted = 0, i, False
    while j < len(s):
        c = s[j]
        if quoted:
            if c == "\\":
                j += 1
            elif c == '"':
                quoted = False
        elif c == '"':
            quoted = True
        elif c == "(":
            depth += 1
        elif c == ")":
            if depth == 0:
                break
            depth -= 1
        elif c == "," and depth == 0:
            break
        j += 1
    return s[i:j], j


def _parse_group(s, i):
    i += 1
    items, keyed = [], True
    while i < len(s) and s[i] != ")":
        m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)=", s[i:])
        if m and not s[i:].startswith("INVTEXT") and s[i + m.end() - 1] == "=":
            key = m.group(1)
            value, i = _parse_value(s, i + m.end())
            items.append((key, value))
        else:
            value, i = _parse_value(s, i)
            items.append((None, value))
            keyed = False
        if i < len(s) and s[i] == ",":
            i += 1
    i += 1
    if keyed and items:
        return {k: v for k, v in items}, i
    return [v for _, v in items], i


def _export_guid(text):
    m = re.search(r"AttachmentGuid=([0-9A-Fa-f]{32})", text or "")
    return m.group(1).upper() if m else None


# ---------------------------------------------------------------- baselines
def ll_hash_checks(dump):
    """Recompute lighting_looks' outside hash for every saved record."""
    rows_by_guid = {}
    for cue in dump["cues"]:
        rows_by_guid[cue["cue_guid"]] = [row["state"] for row in cue["attachments"]]
    results = []
    for path in sorted(glob.glob(LL_RECORD_GLOB)):
        record = _load(path)
        if record.get("status") != "saved_readback_verified":
            continue
        targets = set(record["plan"]["target_cue_guids"])
        recomputed = _state_hash({g: r for g, r in rows_by_guid.items() if g not in targets})
        results.append({"record": os.path.basename(path), "run": record["run"],
                        "expected": record["outside_before_hash"],
                        "recomputed": recomputed,
                        "match": recomputed == record["outside_before_hash"],
                        "excluded_targets": sorted(targets)})
    return results


def ll_target_checks(dump, by_guid):
    record = _load(LL_LIVE_RECORD)
    out = {}
    for target in record["plan"]["targets"]:
        cue = by_guid.get(target["cue_guid"])
        if cue is None:
            out[target["cue_guid"]] = {"verdict": "MISSING_IN_DUMP"}
            continue
        now = [row["state"] for row in cue["attachments"]]
        fields = diff(target["after_rows"], now)
        out[target["cue_guid"]] = {"verdict": "unchanged" if not fields else "changed",
                                   "fields": fields[:40], "field_count": len(fields),
                                   "baseline": "LL_TARGETS run=" + record["run"]}
    return out


def _export_compare(base_texts, now_texts):
    base_guids = [_export_guid(t) for t in base_texts]
    now_guids = [_export_guid(t) for t in now_texts]
    if base_texts == now_texts:
        return {"verdict": "unchanged"}
    detail = {"verdict": "changed", "count": [len(base_texts), len(now_texts)]}
    if base_guids != now_guids:
        detail["guids_removed"] = sorted(set(base_guids) - set(now_guids))
        detail["guids_added"] = sorted(set(now_guids) - set(base_guids))
        detail["guid_order_changed"] = (sorted(base_guids) == sorted(now_guids))
    fields = []
    now_by_guid = {g: t for g, t in zip(now_guids, now_texts)}
    for guid, text in zip(base_guids, base_texts):
        if guid in now_by_guid and now_by_guid[guid] != text:
            for f in diff(parse_export(text), parse_export(now_by_guid[guid])):
                fields.append("%s:%s" % (guid, f))
    detail["fields"] = fields[:60]
    detail["field_count"] = len(fields)
    return detail


def pf_p05_checks(by_guid):
    base = _load(PF_P05)
    out = {}
    for row in base["rows"]:
        cue = by_guid.get(row["cue_guid"])
        if cue is None:
            out[row["cue_guid"]] = {"verdict": "MISSING_IN_DUMP"}
            continue
        texts = [a["export_text"] for a in cue["attachments"]]
        result = _export_compare(row["pair_invariants"]["attachments"], texts)
        result["baseline"] = "PF_P05_1131"
        out[row["cue_guid"]] = result
    return out


def candle_checks(by_label_unique):
    record = _load(CANDLE)
    mint = record["guid_mint"]
    out = {}
    scratch = by_label_unique.get(mint["scratch_label"])
    if scratch is not None:
        before = mint["pair_diffs"]["scratch"]["before"]
        fields = diff(before, [row["state"] for row in scratch["attachments"]])
        out[scratch["cue_guid"]] = {"verdict": "unchanged" if not fields else "changed",
                                    "fields": fields[:40], "field_count": len(fields),
                                    "baseline": "CANDLE_1138 scratch-before"}
    target = by_label_unique.get(record["cue_label"])
    if target is not None and target["cue_guid"] == record["cue_guid"]:
        before = mint["pair_diffs"]["target"]["before"]
        now = [_fingerprint(row["state"]) for row in target["attachments"]]
        head_ok = now[:len(before)] == before
        tail = [row["state"]["guid"] for row in target["attachments"][len(before):]]
        expected_tail = [record["light_guid"], record["effect_guid"]]
        verdict = "unchanged" if head_ok and tail == expected_tail else "changed"
        changed_head = [i for i, (a, b) in enumerate(zip(before, now)) if a != b]
        out[target["cue_guid"]] = {"verdict": verdict, "pre_candle_rows_identical": head_ok,
                                   "changed_pre_candle_ordinals": changed_head,
                                   "count": [len(before) + 2, len(now)],
                                   "tail_guids": tail, "expected_tail": expected_tail,
                                   "baseline": "CANDLE_1138 target-before+2"}
    return out


def fb_dry_checks(dump):
    base = _load(FB_DRY)["before_attachment_guids"]
    label_counts = {}
    for cue in dump["cues"]:
        label_counts[cue["label"]] = label_counts.get(cue["label"], 0) + 1
    out = {}
    for cue in dump["cues"]:
        if cue["label"] not in base:
            continue
        if label_counts[cue["label"]] > 1:
            out[cue["cue_guid"]] = {"verdict": "AMBIGUOUS_LABEL", "baseline": "FB_DRY_2056"}
            continue
        now = [row["state"]["guid"] for row in cue["attachments"]]
        then = base[cue["label"]]
        detail = {"verdict": "unchanged" if now == then else "changed",
                  "baseline": "FB_DRY_2056 (GUID lists only)"}
        if now != then:
            detail.update({"count": [len(then), len(now)],
                           "guids_removed": sorted(set(then) - set(now)),
                           "guids_added": sorted(set(now) - set(then))})
        out[cue["cue_guid"]] = detail
    return out


def chain_checks():
    """Dump-independent: do the records agree with each other?"""
    out = {}
    records = [p for p in sorted(glob.glob(LL_RECORD_GLOB))
               if _load(p).get("status") == "saved_readback_verified"]
    hashes = {}
    first_before = None
    for path in records:
        record = _load(path)
        hashes[record["run"]] = record["outside_before_hash"]
        before = {t["cue_guid"]: t["before_rows"] for t in record["plan"]["targets"]}
        if first_before is None:
            first_before = before
        out.setdefault("target_before_rows_equal_first", {})[record["run"]] = (before == first_before)
    out["outside_before_hash_by_run"] = hashes
    out["outside_before_hash_constant"] = len(set(hashes.values())) == 1
    if os.path.exists(LL_FAILED_1206) and first_before:
        failed = _load(LL_FAILED_1206)
        out["failed_1206_vs_first_saved_before"] = {
            t["cue_label"]: [r["guid"] for r in t["before_rows"]] ==
                            [r["guid"] for r in first_before[t["cue_guid"]]]
            for t in failed["plan"]["targets"]}
    return out


def compare(dump):
    by_guid = {cue["cue_guid"]: cue for cue in dump["cues"]}
    labels = {}
    for cue in dump["cues"]:
        labels.setdefault(cue["label"], []).append(cue)
    by_label_unique = {k: v[0] for k, v in labels.items() if len(v) == 1}
    duplicate_guids = sorted(g for g in by_guid
                             if sum(1 for c in dump["cues"] if c["cue_guid"] == g) > 1)

    hash_results = ll_hash_checks(dump)
    hash_ok = bool(hash_results) and all(r["match"] for r in hash_results)
    hash_scope = set(by_guid) - set(hash_results[0]["excluded_targets"]) if hash_results else set()
    per_baseline = {
        "LL_TARGETS": ll_target_checks(dump, by_guid),
        "PF_P05_1131": pf_p05_checks(by_guid),
        "CANDLE_1138": candle_checks(by_label_unique),
        "FB_DRY_2056": fb_dry_checks(dump),
    }
    per_cue = []
    for cue in dump["cues"]:
        verdicts = {}
        if cue["cue_guid"] in hash_scope:
            verdicts["LL_HASH"] = ("unchanged (whole-scope hash matched)" if hash_ok else
                                   "IN_SCOPE_OF_MISMATCHED_HASH (not localizable)")
        for name, results in per_baseline.items():
            if cue["cue_guid"] in results:
                verdicts[name] = results[cue["cue_guid"]]
        flat = [v if isinstance(v, str) else v["verdict"] for v in verdicts.values()]
        if not verdicts:
            overall = "NOT_COVERED"
        elif any(v.startswith("changed") or v.startswith("IN_SCOPE_OF_MISMATCHED") or
                 v == "MISSING_IN_DUMP" for v in flat):
            overall = "CHANGED_OR_SUSPECT"
        elif all(v == "AMBIGUOUS_LABEL" for v in flat):
            overall = "NOT_COVERED (label ambiguous)"
        else:
            overall = "UNCHANGED"
        per_cue.append({"index": cue["index"], "label": cue["label"],
                        "cue_guid": cue["cue_guid"], "light_count": cue["light_count"],
                        "overall": overall, "verdicts": verdicts})
    summary = {}
    for row in per_cue:
        summary[row["overall"]] = summary.get(row["overall"], 0) + 1
    return {"dump_run": dump.get("run"), "dump_saved_state": dump.get("saved_state"),
            "dump_show_dirty_at_start": dump.get("show_dirty_at_start"),
            "duplicate_cue_guids": duplicate_guids,
            "ll_hash": hash_results, "ll_hash_all_match": hash_ok,
            "summary": summary, "per_cue": per_cue, "chain": chain_checks()}


# ---------------------------------------------------------------- self-test
def selftest():
    failures = []
    pf = _load(PF_P05)
    rows = pf["rows"][:3]
    fake = {"run": "selftest", "cues": []}
    for i, row in enumerate(rows):
        fake["cues"].append({"index": row["cue_index"], "label": row["cue_label"] + "#",
                             "cue_guid": row["cue_guid"], "light_count": 0,
                             "attachments": [{"state": {"guid": _export_guid(t)}, "export_text": t}
                                             for t in row["pair_invariants"]["attachments"]]})
    by_guid = {c["cue_guid"]: c for c in fake["cues"]}
    res = pf_p05_checks(by_guid)
    if any(res[c["cue_guid"]]["verdict"] != "unchanged" for c in fake["cues"]):
        failures.append("positive control: identical P05 export text not 'unchanged'")
    mutated = copy.deepcopy(fake)
    t0 = mutated["cues"][0]["attachments"][0]["export_text"]
    t0b = re.sub(r"Intensity=[0-9.]+", "Intensity=99.000000", t0, count=1)
    t0b = re.sub(r"AttachmentGuid=[0-9A-F]{32}", "AttachmentGuid=" + "AB" * 16, t0b, count=1)
    mutated["cues"][0]["attachments"][0]["export_text"] = t0b
    mutated["cues"][1]["attachments"].append(copy.deepcopy(mutated["cues"][1]["attachments"][0]))
    res = pf_p05_checks({c["cue_guid"]: c for c in mutated["cues"]})
    r0 = res[mutated["cues"][0]["cue_guid"]]
    if r0["verdict"] != "changed" or "AB" * 16 not in r0.get("guids_added", []):
        failures.append("negative control: re-minted GUID not reported")
    r1 = res[mutated["cues"][1]["cue_guid"]]
    if r1["verdict"] != "changed" or r1["count"][1] != r1["count"][0] + 1:
        failures.append("negative control: added attachment not reported")
    parsed = parse_export(t0)
    parsed_b = parse_export(re.sub(r"Intensity=[0-9.]+", "Intensity=99.000000", t0, count=1))
    if diff(parsed, parsed_b) != ["Lighting.Intensity"]:
        failures.append("parser: intensity edit not localized: %s" % diff(parsed, parsed_b))
    # Hash control: a one-field edit in a non-target cue must flip the hash.
    a = {"G1": [{"guid": "X", "lighting": {"intensity": 1.0}}]}
    b = copy.deepcopy(a)
    b["G1"][0]["lighting"]["intensity"] = 1.0000001
    if _state_hash(a) == _state_hash(b):
        failures.append("hash control: edit did not change hash")
    print("SELFTEST", "PASS" if not failures else "FAIL", failures)
    return not failures


def _newest_dump():
    paths = [p for p in glob.glob(os.path.join(HERE, "light_guid_audit_2*.json"))
             if not p.endswith(("_STOPPED.json", "_compare.json"))]
    if not paths:
        raise SystemExit("no light_guid_audit_<stamp>.json dump found in " + HERE)
    return max(paths, key=os.path.getmtime)


def main(argv):
    if "--selftest" in argv:
        return 0 if selftest() else 1
    if "--chain" in argv:
        print(json.dumps(chain_checks(), indent=1))
        return 0
    path = argv[1] if len(argv) > 1 else _newest_dump()
    dump = _load(path)
    if not dump.get("ok"):
        raise SystemExit("dump is not ok: " + str(dump.get("error")))
    result = compare(dump)
    out = path[:-5] + "_compare.json"
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=1, sort_keys=True)
    print("dump:", path, "saved_state:", result["dump_saved_state"])
    print("LL_HASH all match:", result["ll_hash_all_match"],
          "(%d records)" % len(result["ll_hash"]))
    print("summary:", result["summary"])
    for row in result["per_cue"]:
        if row["overall"].startswith("CHANGED"):
            print("  CHANGED/SUSPECT idx=%d %s %s" % (row["index"], row["label"], row["cue_guid"]))
    print("report:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
