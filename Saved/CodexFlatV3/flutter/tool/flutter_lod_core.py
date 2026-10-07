"""Pure planning logic for flutter_lod.py (no Unreal import; the offline harness drives it directly).

OFFLINE-AUTHORED 7 Oct 2026; NOT YET RUN IN UNREAL.

Gary 7 Oct (his own answers), P04 / P05 / P06 wings only:
  (1) stronger flutter  - Flap MI scalar overrides FlutterAmpCm 3 -> 6, FlutterHz 0.7 -> 0.9
      (FlutterMaxCm stays 6 = the master's MaxWorldPositionOffsetDisplacement, so no WPO override;
       build_billboard_master.py:54, 189, 263, 489-491 [declaration-proven: script text])
  (2) flaps seen further - LOD1 screen size ~0.75 -> 0.3 on the P04-P06 Flat V3 wing meshes
      (flaps exist only in LOD0: FlatV3Spec "LOD1 beyond ~15 m"; the tool re-checks per mesh)

Sharing rule (the brief): a Flap MI is written ONLY when nothing outside P04-P06 can see the change:
  * no wing panel outside the target Passages (any cue, enabled or not, any slot, mesh default or
    MaterialOverrides) uses it, nor any material whose PARENT CHAIN contains it;
  * no excluded panel inside the target Passages (fences, non-Flat-V3) uses it;
  * the asset-registry referencer closure (MI -> meshes / child MIs -> ...) reaches no map other than
    the show level, and no asset other than the Show, except args.allow_referencers;
  * it is not a library parent under /Game/Scenes/Wings/PaintedSurface/ (MI_Billboard_Flap, _v4 ...).
  A mesh shared the same way is LOD-changed only with args.include_shared_meshes = true.
"""
from __future__ import annotations

import hashlib
import json
import math
import re

MARK = "FLATV3_FLUTTERLOD"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"            # topple_core.py:37 [precedent, ran]
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"   # gloss4_core.py:39 [precedent, ran]
EXTERNAL_ACTOR_ROOTS = ("/Game/__ExternalActors__/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice/",
                        "/Game/__ExternalObjects__/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice/")
LIBRARY_ROOTS = ("/Game/Scenes/Wings/PaintedSurface/",)   # shared Billboard parents: never written by this tool
FLUTTER_NAMES = ("FlutterAmpCm", "FlutterHz", "FlutterMaxCm")
FLUTTER_SWITCH = "Flutter"                                 # build_billboard_master.py:526, 547
FLAP_SLOT = "Flap"
TOL = 1e-4
MODES = ("DRY", "APPLY", "REVERT")
APPROVED = {"FlutterAmpCm": 6.0, "FlutterHz": 0.9, "lod1_screen_size": 0.3}   # Gary 7 Oct

DEFAULT_ARGS = {
    "mode": "DRY",
    "confirm": "DRY FLUTTERLOD",
    "run_id": None,
    "decided_by": "",
    # label -> pinned GUID (both must match the Show; GUIDs from saved records, see flutter_lod_args.json)
    "target_passages": {"Passage 4": "0067B5F57142956FB5B80EA31B1210B5",
                        "Passage 5": "3B27C331B54325A469AE8A818B9049F9",
                        "Passage 6": "9BFC29C45D47911FF7836BB8537230D2"},
    "values": {"FlutterAmpCm": 6.0, "FlutterHz": 0.9},
    "expect_flutter_max_cm": 6.0,
    "lod1_screen_size": 0.3,
    "expect_lod1_range": [0.4, 1.5],
    "include_shared_meshes": False,
    "mesh_include_regex": r"^SM_FlatV3_",
    "mesh_exclude_regex": r"(?i)fence",
    "allow_referencers": [],
    "mesh_batch_size": 8,
    "referencer_depth": 3,
}


class PlanError(RuntimeError):
    pass


def require(cond, reason, detail=""):
    if not cond:
        raise PlanError("%s%s" % (reason, ("|" + str(detail)) if detail != "" else ""))


def pkg(path):
    """'/Game/A/B.B' or "Class'/Game/A/B.B'" -> '/Game/A/B'."""
    if path is None:
        return None
    m = re.search(r"(/Game/[^\"'.,)\s]+)", str(path))
    return m.group(1) if m else None


def basename(path):
    return str(path).rsplit("/", 1)[-1]


def close(a, b, tol=TOL):
    return a is not None and b is not None and abs(float(a) - float(b)) <= tol


def sizes_equal(a, b, tol=TOL):
    return a is not None and b is not None and len(a) == len(b) and all(close(x, y, tol) for x, y in zip(a, b))


# --------------------------------------------------------------------------------------------- args / confirm
def merged_args(raw):
    args = dict(DEFAULT_ARGS)
    unknown = sorted(set(raw) - set(DEFAULT_ARGS) - {"howto", "notes"})
    require(not unknown, "UNKNOWN_ARGS", json.dumps(unknown))
    args.update(raw)
    return args


def validate_args(args):
    mode = str(args.get("mode", "")).upper()
    require(mode in MODES, "BAD_MODE", mode)
    vals = args["values"]
    require(isinstance(vals, dict) and set(vals) <= {"FlutterAmpCm", "FlutterHz"} and vals, "BAD_VALUES", json.dumps(vals))
    for k, v in vals.items():
        require(isinstance(v, (int, float)) and math.isfinite(v) and v > 0, "BAD_VALUE", k)
    require(vals.get("FlutterHz", 1.0) <= 5.0, "HZ_OUT_OF_RANGE", vals.get("FlutterHz"))
    # amplitude above FlutterMaxCm would be clamped by the shader (build_billboard_master.py:189)
    require(vals.get("FlutterAmpCm", 0.0) <= float(args["expect_flutter_max_cm"]) + TOL, "AMP_ABOVE_MAX_CM",
            "%s > %s" % (vals.get("FlutterAmpCm"), args["expect_flutter_max_cm"]))
    lod1 = args["lod1_screen_size"]
    require(isinstance(lod1, (int, float)) and 0.0 < lod1 < 1.0, "BAD_LOD1", lod1)
    lo, hi = args["expect_lod1_range"]
    require(0.0 < lo < hi, "BAD_LOD1_RANGE", args["expect_lod1_range"])
    require(int(args["mesh_batch_size"]) >= 1, "BAD_BATCH")
    require(isinstance(args["target_passages"], dict) and args["target_passages"], "NO_TARGET_PASSAGES")
    re.compile(args["mesh_include_regex"])
    re.compile(args["mesh_exclude_regex"])
    if mode == "APPLY":
        require(str(args.get("decided_by") or "").strip(), "NOT_DECIDED", "decided_by is empty (an asset write)")
    return mode


def confirm_for(mode, plan=None, originals=None):
    if mode == "DRY":
        return "DRY FLUTTERLOD"
    if mode == "APPLY":
        require(plan is not None, "NO_PLAN")
        return "APPLY FLUTTERLOD %dMI %dMESH #%s" % (len(plan["mi_targets"]), len(plan["mesh_targets"]), plan["token"])
    require(originals is not None, "NO_ORIGINALS")
    return "REVERT FLUTTERLOD %s" % originals["run"]


# --------------------------------------------------------------------------------------------- show reading
def parse_panel_export(text):
    """FInfinityPanelDesign export text -> (mesh_pkg, [override pkg or None, ...]).
    Used because MaterialOverrides are TSoftObjectPtr (InfinityStageTypes.h:614 [declaration-proven]) and an
    unloaded soft pointer may read back as None through Python [inferred]; the text carries the path."""
    mesh = None
    m = re.search(r"\bMesh=([^,)]*)", text or "")
    if m:
        mesh = pkg(m.group(1))
    overrides = []
    m = re.search(r"\bMaterialOverrides=\(([^()]*)\)", text or "")
    if m and m.group(1).strip():
        overrides = [pkg(part) for part in m.group(1).split(",")]
    return mesh, overrides


def effective_slot_material(mesh_info, overrides, slot_index):
    """InfinityStagePassageActor.cpp:1110-1115 [declaration-proven: project source]: a non-null
    MaterialOverrides[i] replaces slot i; otherwise the mesh's own slot material renders."""
    if slot_index < len(overrides) and overrides[slot_index]:
        return overrides[slot_index], "override"
    return mesh_info["slots"][slot_index]["material"], "mesh_default"


def flap_index(mesh_info):
    names = [s["name"] for s in mesh_info.get("slots", [])]
    return names.index(FLAP_SLOT) if FLAP_SLOT in names else None


def panel_rows(show):
    """Flatten: one row per (cue, side) with its passage label (None = wing cue in no Passage)."""
    owner = {}
    for p in show["passages"]:
        for g in p["cue_guids"]:
            owner.setdefault(g, p["label"])
    rows = []
    for g, cue in show["cues"].items():
        for panel in cue["panels"]:
            rows.append({"cue_guid": g, "cue_label": cue["label"], "enabled": cue["enabled"],
                         "passage": owner.get(g), "side": panel["side"], "mesh": panel["mesh"],
                         "overrides": list(panel["overrides"])})
    return rows


def resolve_passages(show, args):
    labels = {}
    for p in show["passages"]:
        labels.setdefault(p["label"], []).append(p)
    out = {}
    for label, guid in args["target_passages"].items():
        hits = labels.get(label, [])
        require(len(hits) == 1, "PASSAGE_LABEL_COUNT", "%s=%d" % (label, len(hits)))
        if guid:
            require(hits[0]["guid"] == str(guid).replace("-", "").upper(), "PASSAGE_GUID_MISMATCH",
                    "%s|%s|%s" % (label, hits[0]["guid"], guid))
        require(hits[0]["cue_guids"], "PASSAGE_HAS_NO_WING_CUES", label)
        out[label] = hits[0]["guid"]
    return out


def classify_panels(show, args):
    """-> target panel rows, excluded rows (inside targets), other rows (outside targets)."""
    targets = set(resolve_passages(show, args))
    inc, exc = re.compile(args["mesh_include_regex"]), re.compile(args["mesh_exclude_regex"])
    tgt, excluded, other = [], [], []
    for r in panel_rows(show):
        if r["passage"] not in targets:
            other.append(r)
            continue
        if not r["mesh"]:
            continue
        name = basename(r["mesh"])
        if not r["enabled"]:
            continue   # a disabled cue inside P04-P06 renders nothing now, and would only render inside P04-P06
        if not inc.search(name):
            r["why"] = "not_flatv3"
            excluded.append(r)
        elif exc.search(name):
            r["why"] = "excluded_by_regex"
            excluded.append(r)
        else:
            tgt.append(r)
    return tgt, excluded, other


def needed_assets(show, args):
    """First pass: the meshes whose slots the planner needs (every mesh on any wing panel)."""
    return sorted({r["mesh"] for r in panel_rows(show) if r["mesh"]})


def materials_of_rows(rows, meshes):
    """Every material any of these panels can render: all slot defaults of its mesh + every override."""
    out = {}
    for r in rows:
        info = meshes.get(r["mesh"]) if r["mesh"] else None
        mats = [o for o in r["overrides"] if o]
        if info and info.get("is_static_mesh"):
            mats += [s["material"] for s in info["slots"] if s["material"]]
        for m in mats:
            out.setdefault(m, set()).add("%s/%s/%s" % (r["passage"] or "<no passage>", r["cue_label"], r["side"]))
    return out


# --------------------------------------------------------------------------------------------- referencers
def referencer_closure(start, get_refs, get_class, depth, benign_meshes, benign_mis, allow):
    """BFS from `start` over referencers. Meshes/MIs are expanded (their users matter); a map other than the
    show level, or any other asset class except the Show, is FOREIGN. Returns {foreign:[...], unused:[...],
    errors:[...], visited:n}."""
    foreign, unused, errors = [], [], []
    seen, frontier = {start}, [(start, 0)]
    while frontier:
        node, d = frontier.pop(0)
        try:
            refs = sorted({pkg(r) or str(r) for r in (get_refs(node) or [])})
        except Exception as exc:  # noqa: BLE001  -- recorded, the caller refuses on errors
            errors.append("%s: %s" % (node, exc))
            continue
        for r in refs:
            if r in seen:
                continue
            seen.add(r)
            if r == SHOW_PATH or r == EXPECTED_WORLD or r in allow or r.startswith(EXTERNAL_ACTOR_ROOTS):
                continue
            try:
                cls = str(get_class(r) or "")
            except Exception as exc:  # noqa: BLE001
                errors.append("%s: class %s" % (r, exc))
                continue
            if cls == "StaticMesh":
                if r in benign_meshes:
                    continue
                unused.append(r)
            elif cls.startswith("MaterialInstance") or cls == "Material":
                if r in benign_mis:
                    continue
            elif cls == "World":
                foreign.append(r + " (World)")
                continue
            else:
                foreign.append("%s (%s)" % (r, cls or "?"))
                continue
            if d + 1 < depth:
                frontier.append((r, d + 1))
            else:
                foreign.append("%s (%s, depth limit: users unknown)" % (r, cls))
    return {"foreign": foreign, "unused_in_show": unused, "errors": errors, "visited": len(seen) - 1}


# --------------------------------------------------------------------------------------------- plan
def build_plan(show, meshes, mis, chains, refs, args, master_wpo=None):
    """show: read_show(); meshes: {pkg: mesh_info}; mis: {pkg: mi_info} for every target Flap MI candidate;
    chains: {material pkg: [pkg, parent, ...]} for every material in other/excluded rows; refs: {pkg: closure}."""
    tgt_rows, excl_rows, other_rows = classify_panels(show, args)
    lod1 = float(args["lod1_screen_size"])
    lo, hi = args["expect_lod1_range"]
    vals = {k: float(v) for k, v in args["values"].items()}

    # who outside can see a material (directly or as an ancestor of what they render)
    outside = {}
    for label, rows in (("other", other_rows), ("excluded", excl_rows)):
        for mat, users in materials_of_rows(rows, meshes).items():
            for anc in chains.get(mat, [mat]):
                outside.setdefault(anc, set()).update("%s:%s" % (label, u) for u in users)
    mesh_outside = {}
    for label, rows in (("other", other_rows), ("excluded", excl_rows)):
        for r in rows:
            if r["mesh"]:
                mesh_outside.setdefault(r["mesh"], set()).add("%s:%s/%s/%s" % (
                    label, r["passage"] or "<no passage>", r["cue_label"], r["side"]))

    # target panels -> candidate meshes and effective Flap MIs
    cand_mesh, cand_mi, skipped_panels = {}, {}, []
    for r in tgt_rows:
        info = meshes.get(r["mesh"], {})
        if not info.get("exists") or not info.get("is_static_mesh"):
            skipped_panels.append(dict(r, why="mesh_missing_or_not_static_mesh"))
            continue
        fi = flap_index(info)
        if fi is None:
            skipped_panels.append(dict(r, why="no_flap_slot"))
            continue
        mi, source = effective_slot_material(info, r["overrides"], fi)
        use = "%s/%s/%s" % (r["passage"], r["cue_label"], r["side"])
        cand_mesh.setdefault(r["mesh"], {"uses": [], "flap_index": fi})["uses"].append(use)
        if mi:
            cand_mi.setdefault(mi, {"uses": [], "sources": set()})
            cand_mi[mi]["uses"].append(use)
            cand_mi[mi]["sources"].add(source)
        else:
            skipped_panels.append(dict(r, why="flap_slot_has_no_material"))

    mi_targets, mi_refused, mi_already = [], [], []
    for path in sorted(cand_mi):
        info = mis.get(path, {})
        reasons = []
        if not info.get("is_mic"):
            reasons.append("not_material_instance_constant")
        if path.startswith(LIBRARY_ROOTS):
            reasons.append("library_parent_mi")
        if path in outside:
            reasons.append("shared_outside_targets: " + "; ".join(sorted(outside[path])[:6]))
        missing = [n for n in FLUTTER_NAMES if n not in info.get("scalar_names", [])]
        if missing:
            reasons.append("missing_params: %s" % missing)
        if info.get("flutter_switch") is not True:
            reasons.append("flutter_switch_not_on: %s" % info.get("flutter_switch"))
        eff = info.get("effective", {})
        if not missing and not close(eff.get("FlutterMaxCm"), args["expect_flutter_max_cm"]):
            reasons.append("flutter_max_cm_is_%s_not_%s" % (eff.get("FlutterMaxCm"), args["expect_flutter_max_cm"]))
        ref = refs.get(path, {"errors": ["no referencer read"]})
        if ref.get("errors"):
            reasons.append("referencers_unreadable: %s" % ref["errors"][:2])
        if ref.get("foreign"):
            reasons.append("foreign_referencers: %s" % ref["foreign"][:6])
        row = {"path": path, "uses": cand_mi[path]["uses"], "sources": sorted(cand_mi[path]["sources"]),
               "parent_chain": info.get("parent_chain"), "effective": eff,
               "overrides": {n: info.get("overrides", {}).get(n) for n in FLUTTER_NAMES},
               "unused_mesh_referencers": ref.get("unused_in_show", [])}
        if reasons:
            mi_refused.append(dict(row, reasons=reasons))
        elif all(close(eff.get(k), v) for k, v in vals.items()):
            mi_already.append(row)
        else:
            mi_targets.append(dict(row, set=vals))

    mesh_targets, mesh_refused, mesh_already, mesh_shared_skipped = [], [], [], []
    for path in sorted(cand_mesh):
        info = meshes[path]
        fi = cand_mesh[path]["flap_index"]
        sizes, alt = info.get("screen_sizes"), info.get("screen_sizes_alt")
        reasons = []
        if info.get("nanite"):
            reasons.append("nanite_enabled (LOD screen sizes do not drive Nanite)")
        n = int(info.get("lod_count") or 0)
        if n < 2:
            reasons.append("lod_count_%d" % n)
        if not sizes or len(sizes) != n:
            reasons.append("screen_sizes_unreadable: %s" % sizes)
        elif alt is not None and not sizes_equal(sizes, alt):
            reasons.append("screen_size_readers_disagree: %s vs %s" % (sizes, alt))
        lod_slots = info.get("lod_slots", {})
        if fi not in lod_slots.get("0", []):
            reasons.append("no_flap_section_in_lod0")
        if n >= 2 and fi in lod_slots.get("1", []):
            reasons.append("flap_survives_in_lod1 (LOD change not needed)")
        if sizes and len(sizes) == n and n >= 2:
            if not (lo <= sizes[1] <= hi) and sizes[1] > lod1 + TOL:
                reasons.append("lod1_%s_outside_expected_%s" % (sizes[1], [lo, hi]))
            if n > 2 and sizes[2] >= lod1 - TOL:
                reasons.append("lod2_%s_not_below_new_lod1" % sizes[2])
            if sizes[0] <= lod1 + TOL:
                reasons.append("lod0_%s_not_above_new_lod1" % sizes[0])
        ref = refs.get(path, {"errors": ["no referencer read"]})
        if ref.get("errors"):
            reasons.append("referencers_unreadable: %s" % ref["errors"][:2])
        shared = sorted(mesh_outside.get(path, set())) + ["registry:" + f for f in ref.get("foreign", [])]
        row = {"path": path, "uses": cand_mesh[path]["uses"], "lod_count": n, "screen_sizes": sizes,
               "flap_slot_index": fi, "lod_slots": lod_slots, "shared_with": shared,
               "auto_compute_lod_screen_size": info.get("auto_compute")}
        if reasons:
            mesh_refused.append(dict(row, reasons=reasons))
        elif sizes[1] <= lod1 + TOL:
            mesh_already.append(row)
        elif shared and not args["include_shared_meshes"]:
            mesh_shared_skipped.append(row)
        else:
            new = list(sizes)
            new[1] = lod1
            mesh_targets.append(dict(row, new_sizes=new))

    plan = {"target_passages": resolve_passages(show, args), "values": vals, "lod1_screen_size": lod1,
            "include_shared_meshes": bool(args["include_shared_meshes"]), "master_max_wpo_cm": master_wpo,
            "mi_targets": mi_targets, "mi_refused": mi_refused, "mi_already": mi_already,
            "mesh_targets": mesh_targets, "mesh_refused": mesh_refused, "mesh_already": mesh_already,
            "mesh_shared_skipped": mesh_shared_skipped,
            "panels": {"target": len(tgt_rows), "excluded": [dict(r) for r in excl_rows],
                       "skipped": skipped_panels, "outside_rows": len(other_rows)},
            "lod1_histogram": histogram([m["screen_sizes"][1] for m in mesh_targets + mesh_refused + mesh_already
                                         + mesh_shared_skipped if m["screen_sizes"] and len(m["screen_sizes"]) > 1])}
    plan["token"] = token(plan)
    return plan


def histogram(values):
    out = {}
    for v in values:
        k = "%.3f" % v
        out[k] = out.get(k, 0) + 1
    return out


def token(plan):
    basis = {"mi": [[t["path"], t["effective"], t["overrides"]] for t in plan["mi_targets"]],
             "mesh": [[t["path"], t["screen_sizes"]] for t in plan["mesh_targets"]],
             "values": plan["values"], "lod1": plan["lod1_screen_size"], "shared": plan["include_shared_meshes"]}
    text = json.dumps(basis, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]


def batches(items, size):
    size = max(1, int(size))
    return [items[i:i + size] for i in range(0, len(items), size)]


# --------------------------------------------------------------------------------------------- revert decisions
def mi_revert_action(orig_row, now_effective, values):
    """'restore' if the planned values are live, 'skip' if the originals are live, else PlanError (drift)."""
    names = list(values)
    if all(close(now_effective.get(n), values[n]) for n in names):
        return "restore"
    if all(close(now_effective.get(n), orig_row["effective"].get(n)) for n in names):
        return "skip"
    raise PlanError("MI_DRIFT_SINCE_APPLY|%s|now=%s" % (orig_row["path"], json.dumps(now_effective)))


def mesh_revert_action(orig_row, now_sizes):
    if sizes_equal(now_sizes, orig_row["new_sizes"]):
        return "restore"
    if sizes_equal(now_sizes, orig_row["screen_sizes"]):
        return "skip"
    raise PlanError("MESH_DRIFT_SINCE_APPLY|%s|now=%s" % (orig_row["path"], now_sizes))


def override_state_matches(orig_overrides, now_overrides, names):
    """Field by field: each flutter name is overridden with the same value, or absent, exactly as before."""
    bad = {}
    for n in names:
        a, b = orig_overrides.get(n), now_overrides.get(n)
        if (a is None) != (b is None) or (a is not None and not close(a, b)):
            bad[n] = [a, b]
    return bad
