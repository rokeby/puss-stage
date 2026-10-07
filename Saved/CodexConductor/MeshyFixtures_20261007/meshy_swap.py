"""Meshy fixtures SWAP, one passage per run: COUNT (offline) / DRY / APPLY / REVERT (editor, via meshy_swap_run.py).

Gary 6-7 Oct: "Keep the lights where I put them ... the meshies are coming in to replace the cubes"; dead bulbs still
look like bulbs and glow minimally; housings may sit on the rig and overlap. Needs meshy_import_record.json at status
saved_readback_verified. NO LIGHT ROW IS EVER WRITTEN: every light's transform, aim and settings stay byte-for-byte
(the scope check refuses any light-row difference).

WHAT IT CHANGES
 1 Bulbs (Show rows). Every enabled-or-not PROP row "<score label>_BODY" whose mesh is the engine Sphere or an
   SM_PB_Bulb_* Sphere duplicate (metadata PussBodySource, lighting_scores_apply.py:1392-1396), paired by label with
   exactly one LIGHT row "<same label minus _BODY>" on the same cue, gets:
     mesh   = SM_Bulb_<V> (plain spheres: the fixture's own faint MI_<V>_Glow on slot 0), or a derived
              Fixtures/Derived/SM_FX_<V>_<hash> = SM_Bulb_<V> with slot 0 = the body's EXISTING MI_PB_Bulb_* (keeps its
              colour, DIM / MATCH_LIGHT level and the Body follow-light wiring, which drives slot 0's "Intensity")
     V      = bulb_variant(light GUID, bulb_seed, bulb_pool): ONE sha256 per light (no random stream)
     transform = body's own rotation; uniform scale (MATCH_SPHERE: the old glass diameter / the bulb's glass width,
              clamped 0.75..4); location so the bulb's GLASS CENTRE sits on the paired light's origin
              (bulb_anchor LIGHT) or on the old glass centre (BODY).
   Its "<label>_CAP" Cylinder row (lighting_scores_apply.py:696-725) is disabled (enabled=False): the Meshy bulb has a
   real screw cap. SM_Lamp_Wall / SM_Lamp_Ceiling bodies are fixtures already and are left alone.
 2 Housings (the Structure actor, NOT Show rows). The C++ fits ONE structure-wide FInfinityStageFixtureSettings.BodyMesh
   behind every enabled Station light, practical bulbs included (InfinityStageStructureActor.cpp:138-176, 1818-1830;
   .h:396-416). So the swap sets, per passage: BodyMesh = the lantern of the passage's majority housed role (rule table
   meshy_common.ROLE_LANTERN; or args "housing"), BodySizeCm = the lantern's own bounds x housing_scale (uniform: no
   squash), BodyMaterial = None (a non-null one overrides every slot, cpp:775-780). The light sits on the bounds front
   face, so the lens lands lens_offset_cm from the light origin (Fresnel: 2.4 cm behind, 6.4 cm below; the DRY prints
   the figure for the chosen lantern). Per-light lanterns by role, an exact lens-at-origin placement, and keeping
   lanterns off practical bulbs all need a C++ change (a per-role mesh rule + lens anchor on FInfinityStageFixtureSettings
   or an opt-out on the attachment); "housing": "OFF" skips this half.

MODES (args file meshy_swap_args.json; passage is required)
  COUNT  offline: python meshy_swap.py [args.json] -> meshy_swap_counts.json from the newest on-disk row snapshots
         (p0N_rig_pattern_record.json after_cue_rows, 6 Oct 22:3x; P05: lighting_scores_record_P05.json 6 Oct 02:32).
  DRY    read-only; plans from LIVE rows + live mesh bounds/slot-0/metadata; prints plan_sha256 (APPLY must quote it),
         counts, variants, skips, anchor warnings, housing choice + lens offset, foreign records. Census/rows unchanged.
  APPLY  confirm "APPLY MESHYSWAP P0N" + plan_sha256 (+ optional expected_bulbs / expected_caps pins) + ack_records.
         Record FIRST (exclusive; before rows + structure fixture state), Backups/PreMeshySwapP0N-<run>, derived meshes
         CREATE-ONLY (saved, census back to clean), row writes, scope check (only planned fields on planned GUIDs;
         every other row and cue identical; export of every other cue + passage settings identical), structure write +
         read-back, materialize passage + re-fit structure, verify spawned bulb meshes/scales/offsets and the housing
         ISM (mesh, instance count unchanged, uniform scale), narrow save (Show + level only), read back.
  REVERT confirm "REVERT MESHYSWAP P0N": live target rows must equal the record's after rows (no drift), writes back
         the before mesh / transform / enabled on exactly the recorded GUIDs, restores the structure's three fixture
         fields, materializes, saves narrow, reads back == before. Derived meshes are left on disk (unreferenced).
Markers: MESHYSWAP_<MODE>_OK|run=<id>|passage=..|...; any stop MESHYSWAP_STOPPED|run=<id>|...

Proof tiers (AGENTS.md), per claim -- see also meshy_common.py's header:
* declaration-proven: listed above with file:line; FTransform translation/rotation setters as written live by
  p04_window_shadows.py:1614-1619; attachment "mesh" set from a loaded asset as lighting_looks_apply.py:1563.
* measured: helpers reused unchanged from live-proven tools (lighting_looks_apply.py _set_pair_attachments :1292,
  _backup :1616, _save_narrow :1657; lighting_scores_apply.py _materialize_passage :2879, scan_foreign_records :1969,
  read_extensions :879); row shapes and pairing from the 6 Oct records (meshy_common.py).
* inferred (the first DRY/APPLY confirms or stops on each): transform.set_editor_property("scale3d", ..) round-trips;
  FInfinityStageFixtureSettings python names body_mesh / body_size_cm / body_material (body_size_cm is read live by
  p03_housing_drop.py:759; the other two by the same reflection rule); a TSoftObjectPtr<UStaticMesh> struct field
  accepts a loaded asset like the attachment's "mesh"; EditorAssetLibrary.get_metadata_tag on SM_PB_Bulb_* returns the
  PussBodySource written at creation; spawned prop actors carry the tag "InfinityStage.Attachment.<cue>|<guid>"
  (InfinityStagePassageActor.cpp:972-975 says so; read back here); a translucent glass slot does not shadow the
  practical's point light differently from today's opaque sphere (look item, not gated).
"""
from __future__ import annotations

import ast
import copy
import datetime
import hashlib
import json
import os
import re
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
COMMON_PATH = os.path.join(HERE, "meshy_common.py")
IMPORT_RECORD_PATH = os.path.join(HERE, "meshy_import_record.json")
SCORES_TOOL_PATH = os.path.join(CONDUCTOR, "lighting_scores_apply.py")
COUNTS_PATH = os.path.join(HERE, "meshy_swap_counts.json")
MARK = "MESHYSWAP"
VALID_MODES = ("COUNT", "DRY", "APPLY", "REVERT")
PASSAGES = ("P01", "P02", "P03", "P04", "P05", "P06")
FIXTURE_TAG = "InfinityStage.Structure.Fixtures"      # InfinityStageStructureActor.cpp:24 (p03_housing_drop.py:105)
FIXTURE_OTHER_FIELDS = ("enabled", "hang_from_grid", "line_thickness_cm", "max_drop_cm", "line_mesh", "line_material")
PLACE_TOL_CM = 0.5

EXTRA_DEFAULTS = {"passage": None, "plan_sha256": None, "expected_bulbs": None, "expected_caps": None,
                  "ack_records": [], "allow_dirty": []}

C = None   # the pure namespace (meshy_common), loaded fresh per run; never a UE object


def load_common():
    return types.SimpleNamespace(**runpy.run_path(COMMON_PATH, run_name="_meshy_common_for_swap"))


def require(condition, message):
    C.require(condition, message)


def record_path(passage):
    return os.path.join(HERE, "meshy_swap_record_%s.json" % passage)


def report_path(mode, passage, run):
    return os.path.join(HERE, "meshy_swap_report_%s_%s_%s.json" % (passage, mode, run))


def passage_names(passage):
    key = str(passage or "").upper()
    require(key in PASSAGES, "PASSAGE_INVALID|%s" % passage)
    n = int(key[1:])
    return {"key": key, "number": n, "structure_label": "Infinity Stage - Structure %02d" % n,
            "actor_prefix": "Passage %02d" % n}


def check_args(raw, common):
    raw = dict(raw or {})
    allowed = set(common.SWAP_DEFAULTS) | set(EXTRA_DEFAULTS) | {"mode", "confirm"}
    unknown = sorted(set(raw) - allowed)
    common.require(not unknown, "ARGS_UNKNOWN|%s" % unknown)
    mode = str(raw.get("mode", "DRY")).upper()
    common.require(mode in VALID_MODES, "MODE_INVALID|" + mode)
    out = copy.deepcopy(common.SWAP_DEFAULTS)
    out.update(copy.deepcopy(EXTRA_DEFAULTS))
    out.update({k: copy.deepcopy(v) for k, v in raw.items() if k in allowed})
    out["mode"] = mode
    passage = str(out["passage"] or "").upper()
    common.require(passage in PASSAGES or (mode == "COUNT" and out["passage"] in (None, "ALL")),
                   "PASSAGE_INVALID|%s" % out["passage"])
    out["passage"] = passage if passage in PASSAGES else "ALL"
    if mode in ("APPLY", "REVERT"):
        common.require(raw.get("confirm") == "%s %s %s" % (mode, MARK, passage),
                       "CONFIRM_MISSING|need='%s %s %s'" % (mode, MARK, passage))
    if mode == "APPLY":
        common.require(isinstance(out["plan_sha256"], str) and len(out["plan_sha256"]) == 64,
                       "APPLY_NEEDS_PLAN_SHA256 (copy it from the DRY report)")
    pool = out["bulb_pool"]
    common.require(isinstance(pool, list) and pool and set(pool) <= set(common.BULBS) and len(set(pool)) == len(pool),
                   "BULB_POOL_INVALID")
    common.require(out["bulb_anchor"] in ("LIGHT", "BODY"), "BULB_ANCHOR_INVALID")
    common.require(out["bulb_scale"] in ("MATCH_SPHERE", "REAL") or (isinstance(out["bulb_scale"], (int, float))
                   and not isinstance(out["bulb_scale"], bool) and 0.25 <= out["bulb_scale"] <= 6.0), "BULB_SCALE_INVALID")
    lo, hi = out["bulb_scale_clamp"]
    common.require(0.1 <= float(lo) <= float(hi) <= 10.0, "BULB_SCALE_CLAMP_INVALID")
    common.require(isinstance(out["disable_caps"], bool), "DISABLE_CAPS_INVALID")
    common.require(out["housing"] in ("AUTO", "OFF") or out["housing"] in common.LANTERNS, "HOUSING_INVALID")
    common.housing_size({"size": [1.0, 1.0, 1.0]}, out["housing_scale"])   # range check
    for key in ("expected_bulbs", "expected_caps"):
        common.require(out[key] is None or (isinstance(out[key], int) and not isinstance(out[key], bool) and out[key] >= 0),
                       key.upper() + "_INVALID")
    for key in ("ack_records", "allow_dirty"):
        common.require(isinstance(out[key], list) and all(isinstance(v, str) for v in out[key]), key.upper() + "_INVALID")
    if out["label_regex"] is not None:
        re.compile(out["label_regex"])
    return out


def planner_opts(args):
    return {k: args[k] for k in C.SWAP_DEFAULTS}


def check_pins(plan, args):
    for key, field in (("expected_bulbs", "bulbs"), ("expected_caps", "caps")):
        if args[key] is not None:
            require(plan["counts"][field] == args[key], "PIN_%s|plan=%d|pinned=%d" % (field.upper(), plan["counts"][field],
                                                                                  args[key]))


def check_import_record(record, plan):
    require(record is not None, "IMPORT_RECORD_ABSENT|" + IMPORT_RECORD_PATH)
    needed = {b["variant"] for t in plan["targets"] for b in t["bulbs"]}
    if plan["housing"]["mode"] != "OFF":
        needed.add(plan["housing"]["lantern"])
    done = {n for n, b in record.get("fixtures", {}).items() if b.get("status") == "saved_readback_verified"}
    missing = sorted(needed - done)
    require(not missing, "FIXTURES_NOT_IMPORTED|%s" % missing)
    return sorted(needed)


def check_apply_gate(path, unacked):
    require(not os.path.exists(path), "ACTIVE_RECORD_EXISTS|" + path)
    require(not unacked, "FOREIGN_ACTIVE_RECORDS_OVERLAP|" + ";".join(unacked))


def check_record(record, passage):
    require(record.get("passage") == passage, "RECORD_PASSAGE_MISMATCH")
    require(record.get("status") == "saved_readback_verified", "REVERT_RECORD_STATUS|%s" % record.get("status"))
    for key in ("before_rows", "after_rows", "structure_before", "plan"):
        require(key in record, "REVERT_RECORD_FIELD_MISSING|" + key)


def scan_foreign_text(roots, needles, exclude=()):
    """Active *record*.json files that mention a needle (structure label for the housing half)."""
    excluded = {os.path.normcase(os.path.abspath(p)) for p in exclude}
    hits = []
    for root in roots:
        for dirpath, unused, files in os.walk(root):
            for name in sorted(files):
                if "record" not in name or not name.endswith(".json"):
                    continue
                path = os.path.join(dirpath, name)
                if os.path.normcase(os.path.abspath(path)) in excluded:
                    continue
                try:
                    with open(path, encoding="utf-8", errors="replace") as handle:
                        text = handle.read()
                    status = str(json.loads(text).get("status", "")).lower()
                except (OSError, ValueError, AttributeError):
                    continue
                if status in ("reverted", "failed_rolled_back_in_memory", "stale", "superseded"):
                    continue
                found = sorted(n for n in needles if n in text)
                if found:
                    hits.append({"path": path, "status": status or None, "needles": found})
    return hits


# --------------------------------------------------------------------------------------------------------------
# COUNT (offline)
# --------------------------------------------------------------------------------------------------------------
def count_offline(args, table=None):
    table = table or C.load_fixture_table(check_files=False)
    passages = PASSAGES if args["passage"] == "ALL" else (args["passage"],)
    out = {"inferred": "offline snapshots, sphere bounds assumed -50..50; the live DRY re-reads every row and mesh",
           "passages": {}}
    for p in passages:
        cues, source = C.snapshot_cues(p, CONDUCTOR)
        plan = C.plan_passage(p, cues, C.offline_mesh_info(cues), table, planner_opts(args))
        skipped = {}
        for s in plan["skipped"]:
            skipped[s["why"]] = skipped.get(s["why"], 0) + 1
        scales = [b["scale"] for t in plan["targets"] for b in t["bulbs"]]
        out["passages"][p] = {"source": source, "counts": plan["counts"], "variants": plan["variants"],
                              "skipped_by_reason": skipped, "derived_meshes": len(plan["derived_meshes"]),
                              "bulb_scale_range": [min(scales), max(scales)] if scales else None,
                              "housing": plan["housing"]}
    with open(COUNTS_PATH, "w", encoding="utf-8") as handle:
        json.dump(out, handle, indent=2, sort_keys=True)
    return out


# --------------------------------------------------------------------------------------------------------------
# Module loading of the live-proven tools (copied from p04_window_shadows.py:1398-1469).
# --------------------------------------------------------------------------------------------------------------
_SAFE_CALLS = {"os.path.join", "os.path.dirname", "os.path.abspath", "os.path.normcase",
               "os.path.normpath", "re.compile", "tuple", "frozenset", "set", "dict", "list",
               "_load_attachment_state"}


def _dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        inner = _dotted(node.value)
        return None if inner is None else inner + "." + node.attr
    return None


def _is_main_guard(node):
    return (isinstance(node, ast.If) and not node.orelse and len(node.body) == 1
            and isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "unreal" and len(node.test.ops) == 1
            and isinstance(node.test.ops[0], ast.IsNot)
            and isinstance(node.test.comparators[0], ast.Constant) and node.test.comparators[0].value is None
            and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Call)
            and _dotted(node.body[0].value.func) == "main"
            and not node.body[0].value.args and not node.body[0].value.keywords)


def _top_level_ok(node, index):
    if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef)):
        return True
    if isinstance(node, ast.Expr):
        return index == 0 and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        return node.value is None or all(_dotted(c.func) in _SAFE_CALLS
                                         for c in ast.walk(node.value) if isinstance(c, ast.Call))
    if isinstance(node, ast.Try):
        inner = list(node.body) + [s for h in node.handlers for s in h.body] + list(node.orelse) + list(node.finalbody)
        return all(isinstance(s, (ast.Import, ast.ImportFrom))
                   or (isinstance(s, ast.Assign) and isinstance(s.value, ast.Constant)) for s in inner)
    return False


def load_without_main(path, module_name):
    with open(path, "rb") as handle:
        raw = handle.read()
    tree = ast.parse(raw.decode("utf-8"), filename=path)
    require(tree.body and _is_main_guard(tree.body[-1])
            and sum(1 for n in tree.body if _is_main_guard(n)) == 1, "MAIN_GUARD_SHAPE|" + path)
    for index, node in enumerate(tree.body[:-1]):
        require(_top_level_ok(node, index), "TOP_LEVEL_SIDE_EFFECT|%s|line=%d" % (path, getattr(node, "lineno", -1)))
    tree.body = tree.body[:-1]
    module = types.ModuleType(module_name)
    module.__file__ = path
    exec(compile(tree, path, "exec"), module.__dict__)  # noqa: S102 - reviewed project file
    module.SOURCE_SHA256 = hashlib.sha256(raw).hexdigest()
    return module


SCORES_REQUIRED = ("load_p04_tool", "_materialize_passage", "_count_passage_actors", "scan_foreign_records",
                   "read_extensions")
TOOL_REQUIRED = ("S", "_state_differences", "_guid_text", "_write_json", "_read_json", "_dirty_census", "_backup",
                 "_save_narrow", "_pair_attachments", "_set_pair_attachments", "_attachment_rows", "SHOW_PATH",
                 "EXPECTED_WORLD", "EXPECTED_PROJECT", "_asset_id")


def load_modules():
    scores = load_without_main(SCORES_TOOL_PATH, "_lighting_scores_for_meshy_swap")
    missing = [n for n in SCORES_REQUIRED if not callable(getattr(scores, n, None))]
    require(not missing, "SCORES_API_DRIFT|" + ",".join(missing))
    tool = scores.load_p04_tool()
    missing = [n for n in TOOL_REQUIRED if not hasattr(tool, n)]
    require(not missing, "P04_TOOL_API_DRIFT|" + ",".join(missing))
    return scores, tool


# --------------------------------------------------------------------------------------------------------------
# Unreal runtime (never executed offline). No UE object is kept in a global.
# --------------------------------------------------------------------------------------------------------------
def _log(text):
    unreal.log(text)


def _vec(v):
    return [float(v.x), float(v.y), float(v.z)]


def _ctx_facts(tool):
    project = os.path.normcase(os.path.normpath(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))).rstrip("\\/")
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor) if world is not None else []
    return {"project_ok": project == tool.EXPECTED_PROJECT.rstrip("\\/"),
            "world": tool._asset_id(world) if world is not None else None,
            "world_ok": world is not None and tool._asset_id(world) == tool.EXPECTED_WORLD,
            "pie": editor.get_game_world() is not None,
            "sequencer_open": library is not None and library.get_current_level_sequence() is not None,
            "census": tool._dirty_census(),
            "zz_actors": sorted(a.get_actor_label() for a in actors if a.get_actor_label().startswith("ZZ_"))}


def check_context(ctx, mode, allow_dirty, show_path, world_path):
    """p04_window_shadows.py:1349-1363."""
    require(ctx.get("project_ok", True), "WRONG_PROJECT")
    require(ctx.get("world_ok", True), "WRONG_WORLD|" + str(ctx.get("world")))
    if mode == "DRY":
        return
    require(not ctx.get("pie"), "PIE_OR_SIE_ACTIVE")
    require(not ctx.get("sequencer_open"), "SEQUENCER_IS_OPEN")
    require(not ctx.get("zz_actors"), "STRAY_ZZ_ACTORS|" + ",".join(ctx.get("zz_actors") or []))
    allowed = set(allow_dirty or [])
    require(allowed <= {show_path, world_path}, "ALLOW_DIRTY_OUT_OF_SCOPE|%s" % sorted(allowed))
    census = ctx.get("census") or {}
    dirty = set(census.get("content") or []) | set(census.get("maps") or [])
    require(dirty <= allowed, "DIRTY_BEFORE|census=" + C.canonical(census))


def _find_structure(show, names):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    found = [a for a in subsystem.get_all_level_actors()
             if a.get_class().get_name() == "InfinityStageStructureActor"
             and a.get_actor_label() == names["structure_label"]]
    require(len(found) == 1, "STRUCTURE_COUNT|label=%s|count=%d" % (names["structure_label"], len(found)))
    passage = found[0].get_editor_property("passage")
    require(passage is not None and passage.get_actor_label().startswith(names["actor_prefix"]), "STRUCTURE_PASSAGE_WRONG")
    require(passage.get_editor_property("show_asset") == show, "STRUCTURE_SHOW_WRONG")
    return found[0]


def _fixture_component(structure):
    comps = [c for c in structure.get_editor_property("managed_components")
             if c and FIXTURE_TAG in [str(t) for t in c.get_editor_property("component_tags")]]
    require(len(comps) <= 1, "FIXTURE_COMPONENT_COUNT|%d" % len(comps))
    return comps[0] if comps else None


def _structure_state(tool, structure):
    fixtures = structure.get_editor_property("fixtures")
    state = {"body_mesh": C.asset_id(tool.S._object_path(fixtures.get_editor_property("body_mesh"))),
             "body_size_cm": _vec(fixtures.get_editor_property("body_size_cm")),
             "body_material": C.asset_id(tool.S._object_path(fixtures.get_editor_property("body_material"))),
             "other": {}, "fixture_body_count": int(structure.get_editor_property("fixture_body_count")),
             "current": bool(structure.is_structure_current())}
    for name in FIXTURE_OTHER_FIELDS:
        value = fixtures.get_editor_property(name)
        state["other"][name] = (C.asset_id(tool.S._object_path(value)) if name.endswith(("_mesh", "_material"))
                                else value if isinstance(value, (bool, int, float)) else str(value))
    comp = _fixture_component(structure)
    if comp is not None:
        n = int(comp.get_instance_count())
        scales = []
        for i in range(n):
            xf = comp.get_instance_transform(i, True)
            scales.append(_vec(xf.scale3d))
        state["ism"] = {"mesh": tool._asset_id(comp.get_editor_property("static_mesh")), "instances": n,
                        "scales": scales}
    else:
        state["ism"] = None
    return state


def _write_structure(structure, mesh, size, material):
    fixtures = structure.get_editor_property("fixtures")
    fixtures.set_editor_property("body_mesh", unreal.EditorAssetLibrary.load_asset(mesh) if mesh else None)
    fixtures.set_editor_property("body_size_cm", unreal.Vector(float(size[0]), float(size[1]), float(size[2])))
    fixtures.set_editor_property("body_material", unreal.EditorAssetLibrary.load_asset(material) if material else None)
    structure.modify()
    structure.set_editor_property("fixtures", fixtures)


def _check_structure(got, want_mesh, want_size, want_material, other_before):
    require(got["body_mesh"] == C.asset_id(want_mesh), "STRUCTURE_MESH_READBACK|%s" % got["body_mesh"])
    require(all(abs(a - b) <= 1.0e-3 for a, b in zip(got["body_size_cm"], want_size)), "STRUCTURE_SIZE_READBACK|%s"
            % got["body_size_cm"])
    require(got["body_material"] == C.asset_id(want_material), "STRUCTURE_MATERIAL_READBACK|%s" % got["body_material"])
    require(got["other"] == other_before, "STRUCTURE_OTHER_FIXTURE_FIELDS_CHANGED|%s" % C.canonical(got["other"]))


def _rows(scores, tool, attachments):
    out = []
    for attachment, row in zip(attachments, tool._attachment_rows(attachments)):
        row["ext"] = scores.read_extensions(tool, attachment)
        out.append(row)
    return out


def _runtime_plain(scores, tool, show):
    cues = []
    for index, cue in enumerate(show.get_editor_property("cues")):
        cues.append({"show_index": index, "guid": tool._guid_text(cue.get_editor_property("cue_guid")),
                     "label": str(cue.get_editor_property("label")),
                     "attachments": _rows(scores, tool, tool._pair_attachments(cue))})
    return cues


def _all_rows(cues):
    return {c["guid"]: c["attachments"] for c in cues}


def _export_hash(tool, show, skip_guids):
    texts = []
    for cue in show.get_editor_property("cues"):
        if tool._guid_text(cue.get_editor_property("cue_guid")) in skip_guids:
            continue
        texts.append(str(cue.export_text()))
    for row in show.get_editor_property("passage_settings"):
        texts.append(str(row.export_text()))
    return C.sha256_text("\n".join(texts))


def _mesh_info(tool, cues):
    eal = unreal.EditorAssetLibrary
    info = {}
    for cue in cues:
        for row in cue["attachments"]:
            path = C.asset_id(row.get("mesh"))
            if path is None or path in info or not C.is_kind(row, "PROP"):
                continue
            mesh = eal.load_asset(path)
            require(mesh is not None, "BODY_MESH_LOAD|" + path)
            box = mesh.get_bounding_box()
            slot0 = mesh.get_material(0)
            source = None
            if path.startswith("/Game/"):
                tag = eal.get_metadata_tag(mesh, "PussBodySource")
                source = C.asset_id(str(tag)) if tag else None
            info[path] = {"bounds": (_vec(box.min), _vec(box.max)), "slot0": tool._asset_id(slot0) if slot0 else None,
                          "source": source}
    return info


def _ensure_derived(derived):
    """CREATE-ONLY derived bulbs. An existing one is reused only if it already holds exactly the planned slot 0 and
    source metadata (read back), never edited. Each created package is saved at once."""
    eal = unreal.EditorAssetLibrary
    created, reused = [], []
    for path, spec in sorted(derived.items()):
        if eal.does_asset_exist(path):
            mesh = eal.load_asset(path)
            got = (C.asset_id(str(eal.get_metadata_tag(mesh, "PussFixtureSource"))),
                   C.asset_id(mesh.get_material(0).get_path_name() if mesh.get_material(0) else None))
            require(got == (spec["source"], spec["slot0"]), "DERIVED_EXISTS_DIFFERENT|%s|%s" % (path, got))
            reused.append(path)
            continue
        mesh = eal.duplicate_asset(spec["source"], path)
        require(mesh is not None, "DERIVED_DUPLICATE_FAILED|" + path)
        mesh.modify()
        mesh.set_material(0, eal.load_asset(spec["slot0"]))
        eal.set_metadata_tag(mesh, "PussFixtureSource", spec["source"])
        got = C.asset_id(mesh.get_material(0).get_path_name() if mesh.get_material(0) else None)
        require(got == spec["slot0"], "DERIVED_SLOT0_READBACK|%s|%s" % (path, got))
        require(eal.save_asset(path, only_if_is_dirty=False), "DERIVED_SAVE_FAILED|" + path)
        created.append(path)
    return created, reused


def _write_rows(tool, show, target, values):
    """values: {guid: row} (the planned or the recorded-before row) -> writes mesh, translation, rotation, scale and
    enabled on exactly those GUIDs of this cue. Returns the original attachment list (for rollback)."""
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
        mesh = C.asset_id(row["mesh"])
        attachment.set_editor_property("mesh", unreal.EditorAssetLibrary.load_asset(mesh) if mesh else None)
        t = row["relative_transform"]
        xf = attachment.get_editor_property("relative_transform")
        xf.set_editor_property("translation", unreal.Vector(*[float(v) for v in t["location"]]))
        xf.set_editor_property("rotation", unreal.Quat(*[float(v) for v in t["rotation_xyzw"]]))
        xf.set_editor_property("scale3d", unreal.Vector(*[float(v) for v in t["scale"]]))
        attachment.set_editor_property("relative_transform", xf)
        attachment.set_editor_property("enabled", bool(row["enabled"]))
    require(seen == len(values), "ROW_GUIDS_MISSING|%s|%d/%d" % (target["cue_label"], seen, len(values)))
    tool._set_pair_attachments(show, index, attachments)
    return index, original


def _attachment_actor_index():
    """{"<cue>|<guid>": [actors]} from the materialization tags (InfinityStagePassageActor.cpp:972-975)."""
    index = {}
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in subsystem.get_all_level_actors():
        for tag in actor.get_editor_property("tags"):
            text = str(tag)
            if text.startswith("InfinityStage.Attachment."):
                index.setdefault(text[len("InfinityStage.Attachment."):], []).append(actor)
    return index


def _verify_spawned(plan, table):
    """Measured after materialize: each bulb actor carries the planned mesh and scale, and with anchor LIGHT its
    location sits |R * (s * glass_centre)| from the paired light actor (the glass centre lands on the light)."""
    bad, checked = [], 0
    index = _attachment_actor_index()
    for t in plan["targets"]:
        for b in t["bulbs"]:
            actors = index.get("%s|%s" % (t["cue_guid"], b["guid"]), [])
            if len(actors) != 1:
                bad.append({"guid": b["guid"], "problem": "ACTOR_COUNT_%d" % len(actors)})
                continue
            actor = actors[0]
            comp = actor.get_editor_property("static_mesh_component")
            mesh = C.asset_id(comp.get_editor_property("static_mesh").get_path_name()) if comp else None
            scale = _vec(actor.get_actor_scale3d())
            if mesh != C.asset_id(b["mesh_after"]) or any(abs(s - b["scale"]) > 1.0e-3 for s in scale):
                bad.append({"guid": b["guid"], "problem": "MESH_OR_SCALE", "mesh": mesh, "scale": scale})
                continue
            if plan["opts"]["bulb_anchor"] == "LIGHT":
                lights = index.get("%s|%s" % (t["cue_guid"], b["light_guid"]), [])
                if len(lights) == 1:
                    gap = sum((a - c) ** 2 for a, c in zip(_vec(actor.get_actor_location()),
                                                         _vec(lights[0].get_actor_location()))) ** 0.5
                    want = b["scale"] * sum(c * c for c in table[b["variant"]]["glass_centre"]) ** 0.5
                    if abs(gap - want) > PLACE_TOL_CM:
                        bad.append({"guid": b["guid"], "problem": "GLASS_NOT_ON_LIGHT", "gap": gap, "want": want})
                        continue
            checked += 1
    require(not bad, "SPAWNED_BULBS|%s" % C.canonical(bad)[:2500])
    return checked


def _verify_housing(state, plan, before):
    h = plan["housing"]
    if h["mode"] == "OFF":
        return None
    ism = state["ism"]
    require(ism is not None and ism["mesh"] == h["mesh"], "HOUSING_ISM_MESH|%s" % (ism and ism["mesh"]))
    require(ism["instances"] == before["fixture_body_count"] == state["fixture_body_count"],
            "HOUSING_COUNT|before=%d|after=%d|ism=%d" % (before["fixture_body_count"], state["fixture_body_count"],
                                                          ism["instances"]))
    s = float(plan["opts"]["housing_scale"])
    off = [sc for sc in ism["scales"] if any(abs(v - s) > 1.0e-3 for v in sc)]
    require(not off, "HOUSING_SCALE_NOT_UNIFORM|%s" % off[:5])
    require(state["current"], "STRUCTURE_NOT_CURRENT_AFTER_REFIT")
    return {"instances": ism["instances"], "scale": s}


def _live_plan(scores, tool, show, names, args, table):
    structure = _find_structure(show, names)
    passage = structure.get_editor_property("passage")
    bays = {tool._guid_text(g) for g in show.get_wing_pair_cue_guids_in_passage(passage.get_editor_property("passage_guid"))}
    all_cues = _runtime_plain(scores, tool, show)
    cues = [c for c in all_cues if c["guid"] in bays]
    require(cues, "NO_PASSAGE_CUES|" + names["key"])
    plan = C.plan_passage(names["key"], cues, _mesh_info(tool, cues), table, planner_opts(args))
    plan["structure_before"] = _structure_state(tool, structure)
    plan["structure_before"].pop("ism", None)      # instance scales are re-read, not part of the sha
    return structure, all_cues, plan


def _run(args):
    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    mode, names = args["mode"], passage_names(args["passage"])
    rpath = record_path(names["key"])
    report = {"ok": False, "mode": mode, "run": run, "passage": names["key"], "args": args, "saved": False}
    tool = None
    try:
        require(mode != "COUNT", "COUNT_IS_OFFLINE_ONLY")
        scores, tool = load_modules()
        ctx = _ctx_facts(tool)
        report["context"] = ctx
        check_context(ctx, mode, args["allow_dirty"], tool.SHOW_PATH, tool.EXPECTED_WORLD)
        census_before = ctx["census"]
        show = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
        require(show is not None, "SHOW_ASSET_MISSING")
        table = C.load_fixture_table(check_files=False)
        roots = [os.path.join(SAVED, n) for n in sorted(os.listdir(SAVED)) if n.startswith("Codex")]

        if mode in ("DRY", "APPLY"):
            structure, all_cues, plan = _live_plan(scores, tool, show, names, args, table)
            sha = C.plan_sha(plan)
            imp = tool._read_json(IMPORT_RECORD_PATH) if os.path.isfile(IMPORT_RECORD_PATH) else None
            report["fixtures_needed"] = check_import_record(imp, plan) if mode == "APPLY" else None
            targets = {t["cue_guid"] for t in plan["targets"]}
            guids = sorted(targets | {r["guid"] for t in plan["targets"] for r in t["bulbs"] + t["caps"]})
            foreign = scores.scan_foreign_records(roots, guids, exclude=[rpath])
            if plan["housing"]["mode"] != "OFF":
                foreign += scan_foreign_text(roots, [names["structure_label"]], exclude=[rpath])
            unacked = C.check_ack(foreign, args["ack_records"])
            report.update({"plan": plan, "plan_sha256": sha, "foreign_records": foreign,
                           "unacknowledged_foreign_records": unacked,
                           "active_record": rpath if os.path.exists(rpath) else None})
            before_all = _all_rows(all_cues)
            if mode == "DRY":
                try:
                    report["fixtures_needed"] = check_import_record(imp, plan)
                except Exception as error:  # noqa: BLE001 - reported, not fatal for a DRY
                    report["import_gate"] = str(error)
                require(tool._dirty_census() == census_before, "DRY_CENSUS_CHANGED")
                require(C.canonical(_all_rows(_runtime_plain(scores, tool, show))) == C.canonical(before_all),
                        "DRY_SHOW_ROWS_CHANGED")
                report.update({"ok": True, "mutated": False})
                path = report_path(mode, names["key"], run)
                tool._write_json(path, report)
                h = plan["housing"]
                _log("%s_DRY_OK|run=%s|passage=%s|plan_sha256=%s|cues=%d|bulbs=%d|caps=%d|skipped=%d|anchor_warn=%d"
                     "|derived=%d|variants=%s|housing=%s|lens_offset_cm=%s|practicals_housed=%s|import_gate=%s"
                     "|foreign=%d|unacked=%d|mutated=0|report=%s"
                     % (MARK, run, names["key"], sha, plan["counts"]["cues"], plan["counts"]["bulbs"],
                        plan["counts"]["caps"], plan["counts"]["skipped"], plan["counts"]["anchor_warnings"],
                        len(plan["derived_meshes"]), C.canonical(plan["variants"]), h.get("lantern", "OFF"),
                        h.get("lens_offset_cm"), h.get("practical_bulbs_that_get_a_lantern"),
                        report.get("import_gate", "ok"), len(foreign), len(unacked), path))
                return report

            require(sha == args["plan_sha256"], "PLAN_SHA_MISMATCH|live=%s|args=%s" % (sha, args["plan_sha256"]))
            check_pins(plan, args)
            check_apply_gate(rpath, unacked)
            texts_hash = _export_hash(tool, show, targets)
            backup = tool._backup("PreMeshySwap%s-" % names["key"], run)
            record = {"schema_version": 1, "status": "prepared", "run": run, "passage": names["key"], "backup": backup,
                      "args": args, "plan_sha256": sha, "plan": plan, "export_hash_before": texts_hash,
                      "before_rows": {g: before_all[g] for g in sorted(targets)},
                      "structure_before": plan["structure_before"], "acknowledged_records": list(args["ack_records"]),
                      "derived_created": [], "derived_reused": []}
            tool._write_json(rpath, record, exclusive=True)
            _log("%s_RECORD_WRITTEN|run=%s|path=%s" % (MARK, run, rpath))
            created, reused = _ensure_derived(plan["derived_meshes"])
            record.update({"derived_created": created, "derived_reused": reused})
            tool._write_json(rpath, record)
            require(tool._dirty_census() == census_before, "DERIVED_LEFT_DIRTY|%s" % C.canonical(tool._dirty_census()))
            want_all = C.expected_after(before_all, plan)
            originals, structure_written = [], False
            try:
                for t in plan["targets"]:
                    values = {b["guid"]: b["after"] for b in t["bulbs"]}
                    values.update({c["guid"]: c["after"] for c in t["caps"]})
                    originals.append(_write_rows(tool, show, t, values))
                after_all = _all_rows(_runtime_plain(scores, tool, show))
                C.check_scope(want_all, after_all, "after")
                require(_export_hash(tool, show, targets) == texts_hash, "EXPORT_OUTSIDE_SCOPE_CHANGED")
                h = plan["housing"]
                if h["mode"] != "OFF":
                    structure_written = True
                    _write_structure(structure, h["mesh"], h["body_size_cm"], None)
                    _check_structure(_structure_state(tool, structure), h["mesh"], h["body_size_cm"], None,
                                     plan["structure_before"]["other"])
            except Exception:
                for index, original in originals:
                    tool._set_pair_attachments(show, index, original)
                if structure_written:
                    sb = plan["structure_before"]
                    _write_structure(structure, sb["body_mesh"], sb["body_size_cm"], sb["body_material"])
                C.check_scope(before_all, _all_rows(_runtime_plain(scores, tool, show)), "before")
                record["status"] = "failed_rolled_back_in_memory"
                tool._write_json(rpath, record)
                os.rename(rpath, rpath + ".failed-" + run)
                raise
            record.update({"status": "mutated_verified", "after_rows": {g: after_all[g] for g in sorted(targets)}})
            tool._write_json(rpath, record)
            materialized = scores._materialize_passage(show, names["actor_prefix"])
            require(materialized.get("structure") == names["structure_label"], "STRUCTURE_NOT_REFIT|%s" % materialized)
            state = _structure_state(tool, structure)
            housing = _verify_housing(state, plan, plan["structure_before"])
            spawned = _verify_spawned(plan, table)
            tool._save_narrow()
            report["saved"] = True
            readback = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
            read_all = _all_rows(_runtime_plain(scores, tool, readback))
            C.check_scope(want_all, read_all, "readback")
            require(_export_hash(tool, readback, targets) == texts_hash, "READBACK_EXPORT_OUTSIDE_SCOPE_CHANGED")
            if plan["housing"]["mode"] != "OFF":
                _check_structure(_structure_state(tool, structure), plan["housing"]["mesh"],
                                 plan["housing"]["body_size_cm"], None, plan["structure_before"]["other"])
            record.update({"status": "saved_readback_verified", "materialized": materialized,
                           "after_rows": {g: read_all[g] for g in sorted(targets)}, "structure_after": state,
                           "spawned_verified": spawned, "housing_verified": housing,
                           "saved_census": tool._dirty_census()})
            tool._write_json(rpath, record)
            report.update({"ok": True, "backup": backup, "record": rpath})
            tool._write_json(report_path(mode, names["key"], run), report)
            _log("%s_APPLY_OK|run=%s|passage=%s|plan_sha256=%s|bulbs=%d|caps=%d|derived_created=%d|spawned_ok=%d"
                 "|housing=%s|show_saved=1|level_saved=1|readback=1|record=%s"
                 % (MARK, run, names["key"], sha, plan["counts"]["bulbs"], plan["counts"]["caps"], len(created),
                    spawned, plan["housing"].get("lantern", "OFF"), rpath))
            return report

        # REVERT
        require(os.path.isfile(rpath), "REVERT_RECORD_ABSENT|" + rpath)
        record = tool._read_json(rpath)
        check_record(record, names["key"])
        structure = _find_structure(show, names)
        live_all = _all_rows(_runtime_plain(scores, tool, show))
        model = C.revert_model(record, live_all)
        plan = record["plan"]
        targets = set(record["before_rows"])
        guids = sorted(targets | {r["guid"] for t in plan["targets"] for r in t["bulbs"] + t["caps"]})
        foreign = scores.scan_foreign_records(roots, guids, exclude=[rpath])
        if plan["housing"]["mode"] != "OFF":
            foreign += scan_foreign_text(roots, [names["structure_label"]], exclude=[rpath])
        unacked = C.check_ack(foreign, args["ack_records"])
        report.update({"foreign_records": foreign, "unacknowledged_foreign_records": unacked})
        require(not unacked, "FOREIGN_ACTIVE_RECORDS_OVERLAP|" + ";".join(unacked))
        sb = record["structure_before"]
        if plan["housing"]["mode"] != "OFF":
            live_state = _structure_state(tool, structure)
            _check_structure(live_state, plan["housing"]["mesh"], plan["housing"]["body_size_cm"], None, sb["other"])
        texts_hash = _export_hash(tool, show, targets)
        backup = tool._backup("PreMeshySwap%sRevert-" % names["key"], run)
        originals, structure_written = [], False
        try:
            for t in plan["targets"]:
                before_by_guid = {r["guid"]: r for r in record["before_rows"][t["cue_guid"]]}
                values = {g: before_by_guid[g] for g in [b["guid"] for b in t["bulbs"]] + [c["guid"] for c in t["caps"]]}
                originals.append(_write_rows(tool, show, t, values))
            after_all = _all_rows(_runtime_plain(scores, tool, show))
            C.check_scope(model, after_all, "revert")
            require(_export_hash(tool, show, targets) == texts_hash, "REVERT_EXPORT_OUTSIDE_SCOPE_CHANGED")
            if plan["housing"]["mode"] != "OFF":
                structure_written = True
                _write_structure(structure, sb["body_mesh"], sb["body_size_cm"], sb["body_material"])
                _check_structure(_structure_state(tool, structure), sb["body_mesh"], sb["body_size_cm"],
                                 sb["body_material"], sb["other"])
        except Exception:
            for index, original in originals:
                tool._set_pair_attachments(show, index, original)
            if structure_written:
                h = plan["housing"]
                _write_structure(structure, h["mesh"], h["body_size_cm"], None)
            raise
        materialized = scores._materialize_passage(show, names["actor_prefix"])
        tool._save_narrow()
        report["saved"] = True
        readback = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
        C.check_scope(model, _all_rows(_runtime_plain(scores, tool, readback)), "revert_readback")
        require(_export_hash(tool, readback, targets) == texts_hash, "REVERT_READBACK_EXPORT_CHANGED")
        state = _structure_state(tool, structure)
        require(state["fixture_body_count"] == sb["fixture_body_count"], "REVERT_HOUSING_COUNT|%d|%d"
                % (state["fixture_body_count"], sb["fixture_body_count"]))
        archived = rpath + ".reverted-" + run
        record.update({"status": "reverted", "reverted_run": run, "revert_materialized": materialized})
        tool._write_json(rpath, record)
        os.rename(rpath, archived)
        report.update({"ok": True, "backup": backup, "record_archived": archived,
                       "derived_left_on_disk": record.get("derived_created", [])})
        tool._write_json(report_path(mode, names["key"], run), report)
        _log("%s_REVERT_OK|run=%s|passage=%s|rows=%d|housing_restored=%s|show_saved=1|level_saved=1|readback=1|archived=%s"
             % (MARK, run, names["key"], len(guids) - len(targets), plan["housing"]["mode"] != "OFF", archived))
        return report
    except Exception as error:  # noqa: BLE001 - a report and a marker for every stop
        report["error"] = "%s: %s" % (type(error).__name__, error)
        if tool is not None:
            try:
                report["census"] = tool._dirty_census()
            except Exception:  # noqa: BLE001
                pass
        with open(report_path(mode, names["key"], run), "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True, default=str)
        unreal.log_error("%s_STOPPED|run=%s|mode=%s|passage=%s|saved=%d|%s%s"
                         % (MARK, run, mode, names["key"], int(report["saved"]), report["error"][:1500],
                            "" if report["saved"] else "|NOTHING SAVED"))
        raise


def main():
    global C
    C = load_common()
    require(unreal is not None, "UNREAL_REQUIRED")
    try:
        args = check_args(globals().get("MESHYSWAP_ARGS"), C)
    except Exception as error:  # noqa: BLE001
        unreal.log_error("%s_STOPPED|run=none|ARGS|%s: %s|NOTHING SAVED" % (MARK, type(error).__name__, error))
        raise
    return _run(args)


def count_cli(argv=None):
    """Offline COUNT: python meshy_swap.py [args.json]."""
    global C
    C = load_common()
    argv = list(sys.argv[1:] if argv is None else argv)
    raw = {"mode": "COUNT", "passage": "ALL"}
    if argv:
        with open(argv[0], encoding="utf-8") as handle:
            raw = json.load(handle)
    require(str(raw.get("mode", "COUNT")).upper() == "COUNT", "OFFLINE_RUNS_COUNT_ONLY")
    out = count_offline(check_args(raw, C))
    for p, row in out["passages"].items():
        h = row["housing"]
        print("%s_COUNT|%s|bulbs=%d|caps=%d|skipped=%s|variants=%s|scale=%s|housing=%s(%s)|housed=%s|practicals_housed=%s"
              % (MARK, p, row["counts"]["bulbs"], row["counts"]["caps"], C.canonical(row["skipped_by_reason"]),
                 C.canonical(row["variants"]), row["bulb_scale_range"], h.get("lantern", "OFF"), h.get("chosen_by"),
                 C.canonical(h.get("housed_role_counts")), h.get("practical_bulbs_that_get_a_lantern")))
    print("%s_COUNT_OK|written=%s" % (MARK, COUNTS_PATH))
    return out


if __name__ == "__main__" and unreal is None:
    count_cli()


if unreal is not None:
    main()
