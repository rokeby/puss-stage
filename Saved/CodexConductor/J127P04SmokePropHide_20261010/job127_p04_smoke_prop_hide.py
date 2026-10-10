"""Job 127: hide only the P04 final-wing smoke-pot apparatus; keep smoke alive.

Offline-authored.  Run later through ExecuteProjectPythonFile in the Puss editor.
DRY resolves the current Show attachment and persistent actor by label + identity
tag + final-wing station/world proximity. APPLY records the actor/component state,
backs up and saves only the persistent map, then reads it back. REVERT restores the
recorded state and again saves only that map.

The smoke and grey apparatus share BP_Effect_SmokePot_C. Actor bHidden therefore
must remain unchanged. Apparatus receives visible=False and hidden_in_game=True.
Its instance mesh is also cleared because AInfinityStageEffectSource::BeginPlay ->
ApplySettings reasserts Apparatus visibility; without the null mesh the prop would
return in PIE. REVERT restores the recorded mesh and both flags.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
import shutil

try:
    import unreal
except ImportError:  # offline harness
    unreal = None

WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
UMAP_REL = ("Content", "InfinityStage", "Dev", "Maps", "L_InfinityStage_V1VerticalSlice.umap")
TARGET_LABEL = "FX SMOKE P04 B18 L"
TARGET_PREFIX = "FX SMOKE P04 "
TARGET_CLASS = "BP_Effect_SmokePot_C"
APPARATUS_NAME = "Apparatus"
PLUME_NAME = "PlumeFX"
IDENTITY_PREFIX = "InfinityStage.Attachment."
MARK = "JOB127_P04_SMOKE_PROP_HIDE"
MODES = ("DRY", "APPLY", "REVERT")
CONFIRMS = {
    "DRY": "DRY JOB127 P04 SMOKE PROP",
    "APPLY": "APPLY JOB127 HIDE P04 SMOKE PROP",
    "REVERT": "REVERT JOB127 RESTORE P04 SMOKE PROP",
}


class Refused(RuntimeError):
    pass


def _req(condition, message):
    if not condition:
        raise Refused(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def parse_identity_tag(text):
    text = str(text)
    if not text.startswith(IDENTITY_PREFIX):
        return None
    pieces = text[len(IDENTITY_PREFIX):].split("|")
    if len(pieces) != 2:
        return None
    cue, attachment = (x.replace("-", "").upper() for x in pieces)
    if len(cue) != 32 or len(attachment) != 32:
        return None
    if any(c not in "0123456789ABCDEF" for c in cue + attachment):
        return None
    return cue, attachment


def bay_ordinal(label):
    parts = str(label).split()
    for part in parts:
        if len(part) == 3 and part.startswith("B") and part[1:].isdigit():
            return int(part[1:])
    raise Refused("LABEL_HAS_NO_BAY|%s" % label)


def choose_candidate(rows, expected_label, final_ordinal, max_gap):
    """Pure fail-closed selector used by the offline +/- harness."""
    smoke = [r for r in rows if str(r.get("label", "")).startswith(TARGET_PREFIX)]
    _req(smoke, "NO_P04_SMOKE_ACTORS")
    _req(len({r["label"] for r in smoke}) == len(smoke), "DUPLICATE_P04_SMOKE_LABEL")
    latest = max(bay_ordinal(r["label"]) for r in smoke)
    hits = [r for r in smoke if r["label"] == expected_label]
    _req(len(hits) == 1, "TARGET_LABEL_COUNT|%s|%d" % (expected_label, len(hits)))
    row = hits[0]
    ordinal = bay_ordinal(row["label"])
    _req(ordinal == latest, "TARGET_NOT_LATEST_SMOKE|target=%d|latest=%d" % (ordinal, latest))
    _req(0 <= final_ordinal - ordinal <= max_gap,
         "FINAL_WING_GAP|target=%d|final=%d|max=%d" % (ordinal, final_ordinal, max_gap))
    _req(row.get("class") == TARGET_CLASS, "TARGET_CLASS|%s" % row.get("class"))
    _req(row.get("identity") is not None, "TARGET_IDENTITY_TAG_MISSING")
    _req(int(row.get("apparatus_count", 0)) == 1, "APPARATUS_COUNT|%s" % row.get("apparatus_count"))
    _req(int(row.get("plume_count", 0)) >= 1, "PLUME_COUNT|%s" % row.get("plume_count"))
    return row


def _path(value):
    return value.get_path_name() if value is not None and hasattr(value, "get_path_name") else None


def _prop(value, name, default=None):
    try:
        return value.get_editor_property(name)
    except Exception:
        return default


def _guid(value):
    for name in ("to_string", "ToString"):
        fn = getattr(value, name, None)
        if callable(fn):
            try:
                return str(fn()).replace("-", "").upper()
            except Exception:
                pass
    return str(value).replace("-", "").replace("{", "").replace("}", "").upper()


def _v3(value):
    return [float(value.x), float(value.y), float(value.z)]


def _distance(a, b):
    return math.sqrt(sum((float(a[i]) - float(b[i])) ** 2 for i in range(3)))


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def _write_json(path, value, exclusive=False):
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    with open(path, encoding="utf-8") as handle:
        _req(digest(json.load(handle)) == digest(value), "JSON_READBACK_MISMATCH|%s" % path)


def _require_context():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    _req(editor.get_game_world() is None, "PIE_OR_SIE_RUNNING")
    world = editor.get_editor_world()
    got = world.get_outermost().get_name() if world else None
    _req(got == WORLD, "WRONG_WORLD|%s" % got)
    return world


def _backup(run, stem, record_path=None):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    source = os.path.join(project, *UMAP_REL)
    _req(os.path.isfile(source), "MAP_FILE_MISSING|%s" % source)
    root = os.path.join(project, "Backups", "%s-%s" % (stem, run))
    os.makedirs(root)
    target = os.path.join(root, os.path.basename(source))
    shutil.copy2(source, target)
    if record_path and os.path.isfile(record_path):
        shutil.copy2(record_path, root)
    _req(os.path.getsize(source) == os.path.getsize(target), "BACKUP_SIZE_MISMATCH")
    return {"root": root, "source": source, "copy": target, "bytes": os.path.getsize(target)}


def _save_map_only():
    before = _census()
    _req(not before["content"] and before["maps"] == [WORLD],
         "DIRTY_SCOPE_BEFORE_SAVE|%s|NOTHING_SAVED_DONT_SAVE_RESTART" % json.dumps(before))
    ok = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    _req(ok, "LEVEL_SAVE_FAILED")
    after = _census()
    _req(after == {"content": [], "maps": []}, "DIRTY_AFTER_SAVE|%s" % json.dumps(after))
    return before, after


def _show_plan(args):
    show = unreal.load_asset(SHOW)
    _req(show is not None, "SHOW_LOAD_FAILED")
    settings = {str(x.get_editor_property("label")): x for x in show.get_editor_property("passage_settings")}
    _req("Passage 4" in settings, "P04_SETTINGS_MISSING")
    cue_guids = list(show.get_wing_pair_cue_guids_in_passage(settings["Passage 4"].get_editor_property("passage_guid")))
    cue_text = [_guid(x) for x in cue_guids]
    _req(cue_text, "P04_HAS_NO_WINGS")
    cues = list(show.get_editor_property("cues"))
    by_guid = {_guid(c.get_editor_property("cue_guid")): c for c in cues}
    final_cue = cue_text[-1]
    target_rows = []
    for ordinal, cue_guid in enumerate(cue_text, start=1):
        cue = by_guid.get(cue_guid)
        _req(cue is not None, "P04_CUE_MISSING|%s" % cue_guid)
        pair = cue.get_editor_property("wing_pair")
        for attachment in pair.get_editor_property("attachments"):
            label = str(attachment.get_editor_property("label"))
            if label.startswith(TARGET_PREFIX):
                target_rows.append({"label": label, "ordinal": ordinal, "cue_guid": cue_guid,
                                    "attachment_guid": _guid(attachment.get_editor_property("attachment_guid"))})
    hits = [r for r in target_rows if r["label"] == args["target_label"]]
    _req(len(hits) == 1, "SHOW_TARGET_COUNT|%d" % len(hits))
    target = hits[0]
    _req(target["ordinal"] == max(r["ordinal"] for r in target_rows), "SHOW_TARGET_NOT_LATEST_SMOKE")
    gap = len(cue_text) - target["ordinal"]
    _req(0 <= gap <= int(args["max_final_wing_gap"]), "SHOW_FINAL_WING_GAP|%d" % gap)
    return {"final_ordinal": len(cue_text), "final_cue_guid": final_cue,
            "target": target, "p04_smoke_attachments": target_rows, "gap_bays": gap}


def _components(actor):
    apparatus = [x for x in actor.get_components_by_class(unreal.StaticMeshComponent)
                 if str(x.get_name()) == APPARATUS_NAME]
    plumes = [x for x in actor.get_components_by_class(unreal.ParticleSystemComponent)
              if str(x.get_name()) == PLUME_NAME]
    return apparatus, plumes


def _component_snapshot(component):
    mesh = _prop(component, "static_mesh")
    return {"path": _path(component), "name": str(component.get_name()),
            "visible": bool(_prop(component, "visible")),
            "hidden_in_game": bool(_prop(component, "hidden_in_game")),
            "static_mesh": _path(mesh)}


def _plume_snapshot(component):
    return {"path": _path(component), "name": str(component.get_name()),
            "visible": bool(_prop(component, "visible")),
            "hidden_in_game": bool(_prop(component, "hidden_in_game")),
            "template": _path(_prop(component, "template")),
            "auto_activate": bool(_prop(component, "auto_activate"))}


def _actor_row(actor, show_plan):
    tags = sorted(str(x) for x in list(_prop(actor, "tags", ()) or ()))
    identities = [parse_identity_tag(x) for x in tags]
    identities = [x for x in identities if x is not None]
    wanted = (show_plan["target"]["cue_guid"], show_plan["target"]["attachment_guid"])
    apparatus, plumes = _components(actor)
    return {"label": str(actor.get_actor_label()), "path": _path(actor),
            "class": actor.get_class().get_name(), "level": actor.get_outermost().get_name(),
            "location": _v3(actor.get_actor_location()), "tags": tags,
            "identity": wanted if wanted in identities else None,
            "all_identities": identities, "apparatus_count": len(apparatus), "plume_count": len(plumes),
            "actor_hidden": bool(_prop(actor, "hidden")),
            "apparatus": [_component_snapshot(x) for x in apparatus],
            "plumes": [_plume_snapshot(x) for x in plumes]}


def _resolve(args):
    show_plan = _show_plan(args)
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    smoke_actors = [a for a in actors if str(a.get_actor_label()).startswith(TARGET_PREFIX)]
    rows = [_actor_row(a, show_plan) for a in smoke_actors]
    chosen = choose_candidate(rows, args["target_label"], show_plan["final_ordinal"],
                              int(args["max_final_wing_gap"]))
    _req(chosen["level"] == WORLD, "TARGET_NOT_PERSISTENT|%s" % chosen["level"])
    final_refs = []
    for actor in actors:
        tags = [parse_identity_tag(x) for x in list(_prop(actor, "tags", ()) or ())]
        if any(x is not None and x[0] == show_plan["final_cue_guid"] for x in tags):
            final_refs.append({"path": _path(actor), "label": str(actor.get_actor_label()),
                               "location": _v3(actor.get_actor_location())})
    _req(final_refs, "FINAL_WING_MATERIALIZED_REFERENCE_MISSING")
    nearest = min(final_refs, key=lambda r: _distance(chosen["location"], r["location"]))
    world_distance = _distance(chosen["location"], nearest["location"])
    _req(world_distance <= float(args["max_final_wing_world_distance_cm"]),
         "FINAL_WING_WORLD_DISTANCE|%.3f|max=%.3f" %
         (world_distance, float(args["max_final_wing_world_distance_cm"])))
    chosen["final_wing_nearest_reference"] = nearest
    chosen["final_wing_world_distance_cm"] = world_distance
    actor = next(a for a in smoke_actors if _path(a) == chosen["path"])
    apparatus, plumes = _components(actor)
    return {"world": WORLD, "show": SHOW, "resolution": chosen, "show_plan": show_plan,
            "same_actor_prop_and_fx": True, "mutation_scope": "Apparatus component only",
            "actor_bHidden_policy": "UNCHANGED because actor also owns PlumeFX",
            "apply_component_state": {"visible": False, "hidden_in_game": True, "static_mesh": None},
            "save_allowlist": [WORLD]}, actor, apparatus[0], plumes


def _find_actor_by_path(path):
    hits = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
            if _path(a) == path]
    _req(len(hits) == 1, "RECORDED_ACTOR_PATH_COUNT|%d" % len(hits))
    return hits[0]


def _set_component(component, visible, hidden_in_game, mesh_path):
    mesh = unreal.load_asset(mesh_path) if mesh_path else None
    if mesh_path:
        _req(mesh is not None, "RECORDED_MESH_LOAD_FAILED|%s" % mesh_path)
    component.set_visibility(bool(visible), False)
    component.set_hidden_in_game(bool(hidden_in_game), False)
    component.set_editor_property("static_mesh", mesh)


def _assert_state(actor, apparatus, plumes, wanted, old_actor_hidden, old_plumes):
    got = _component_snapshot(apparatus)
    _req(got["visible"] == wanted["visible"], "APPARATUS_VISIBLE_READBACK|%s" % got)
    _req(got["hidden_in_game"] == wanted["hidden_in_game"], "APPARATUS_HIDDEN_READBACK|%s" % got)
    _req(got["static_mesh"] == wanted["static_mesh"], "APPARATUS_MESH_READBACK|%s" % got)
    _req(bool(_prop(actor, "hidden")) == old_actor_hidden, "ACTOR_bHidden_CHANGED")
    now_plumes = [_plume_snapshot(x) for x in plumes]
    _req(now_plumes == old_plumes, "PLUMEFX_CHANGED|before=%s|after=%s" %
         (json.dumps(old_plumes), json.dumps(now_plumes)))
    return {"actor_bHidden": bool(_prop(actor, "hidden")), "apparatus": got, "plumes": now_plumes}


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    args_path = os.path.join(here, "job127_args.json")
    record_path = os.path.join(here, "job127_record.json")
    with open(args_path, encoding="utf-8") as handle:
        args = json.load(handle)
    mode = str(args.get("mode", "DRY")).upper()
    run = "JOB127-%s" % datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    _req(mode in MODES, "BAD_MODE|%s" % mode)
    _req(str(args.get("confirm", "")) == CONFIRMS[mode], "CONFIRM_REQUIRED|%s" % CONFIRMS[mode])
    _req(args.get("target_label") == TARGET_LABEL, "TARGET_LABEL_LOCK|%s" % args.get("target_label"))
    _require_context()
    initial = _census()
    _req(initial == {"content": [], "maps": []}, "DIRTY_AT_START|%s" % json.dumps(initial))

    if mode == "REVERT":
        _req(os.path.isfile(record_path), "REVERT_RECORD_MISSING")
        with open(record_path, encoding="utf-8") as handle:
            record = json.load(handle)
        _req(record.get("state") == "applied" and record.get("world") == WORLD, "REVERT_RECORD_CONTEXT")
        actor = _find_actor_by_path(record["actor_path"])
        apparatus, plumes = _components(actor)
        _req(len(apparatus) == 1 and _path(apparatus[0]) == record["apparatus_before"]["path"],
             "REVERT_APPARATUS_IDENTITY")
        _assert_state(actor, apparatus[0], plumes, record["apparatus_applied"],
                      record["actor_bHidden_before"], record["plumes_before"])
        backup = _backup(run, "PreJ127SmokePropRevert", record_path)
        old = record["apparatus_before"]
        _set_component(apparatus[0], old["visible"], old["hidden_in_game"], old["static_mesh"])
        readback = _assert_state(actor, apparatus[0], plumes, old,
                                 record["actor_bHidden_before"], record["plumes_before"])
        before_save, final = _save_map_only()
        readback = _assert_state(actor, apparatus[0], plumes, old,
                                 record["actor_bHidden_before"], record["plumes_before"])
        archived = record_path + ".reverted-" + run
        record.update({"state": "reverted", "revert_run": run, "revert_backup": backup,
                       "revert_census_before_save": before_save, "revert_census_after": final,
                       "revert_readback": readback})
        _write_json(record_path, record)
        os.rename(record_path, archived)
        unreal.log("%s_REVERT_OK|run=%s|actor=%s|component=%s|saved=%s|show_saved=0|plume_unchanged=1|backup=%s|record=%s|census_after=%s" %
                   (MARK, run, _path(actor), _path(apparatus[0]), WORLD, backup["root"], archived, json.dumps(final)))
        return

    _req(not os.path.exists(record_path), "ACTIVE_RECORD_EXISTS")
    plan, actor, apparatus, plumes = _resolve(args)
    plan["plan_sha256"] = digest(plan)
    if mode == "DRY":
        final = _census()
        _req(final == initial, "DRY_DIRTIED_PACKAGES|before=%s|after=%s" % (initial, final))
        report = os.path.join(here, "job127_dry_%s.json" % run)
        _write_json(report, {"run": run, "mode": mode, "census_before": initial,
                             "census_after": final, "plan": plan}, True)
        unreal.log("%s_DRY_OK|run=%s|mutated=0|target=%s|bay_gap=%d|world_distance_cm=%.3f|same_actor=1|actor_bHidden=UNCHANGED|component_only=1|plan_sha256=%s|report=%s" %
                   (MARK, run, _path(actor), plan["show_plan"]["gap_bays"],
                    plan["resolution"]["final_wing_world_distance_cm"], plan["plan_sha256"], report))
        return

    _req(str(args.get("plan_sha256", "")) == plan["plan_sha256"],
         "PLAN_DIGEST_MISMATCH|expected=%s" % plan["plan_sha256"])
    _req(bool(args.get("ack_clear_apparatus_mesh_for_pie", False)),
         "ACK_CLEAR_APPARATUS_MESH_FOR_PIE_REQUIRED")
    backup = _backup(run, "PreJ127SmokeProp")
    before = _component_snapshot(apparatus)
    plume_before = [_plume_snapshot(x) for x in plumes]
    actor_hidden_before = bool(_prop(actor, "hidden"))
    record = {"schema": 1, "job": 127, "run": run, "state": "prepared", "world": WORLD,
              "show_read_only": SHOW, "backup": backup, "plan": plan, "actor_path": _path(actor),
              "actor_label": str(actor.get_actor_label()), "actor_bHidden_before": actor_hidden_before,
              "apparatus_before": before, "apparatus_applied": dict(plan["apply_component_state"], path=before["path"], name=before["name"]),
              "plumes_before": plume_before}
    _write_json(record_path, record, True)
    _set_component(apparatus, False, True, None)
    readback = _assert_state(actor, apparatus, plumes, record["apparatus_applied"],
                             actor_hidden_before, plume_before)
    record["state"] = "save_attempted"
    record["pre_save_readback"] = readback
    _write_json(record_path, record)
    before_save, final = _save_map_only()
    readback = _assert_state(actor, apparatus, plumes, record["apparatus_applied"],
                             actor_hidden_before, plume_before)
    record.update({"state": "applied", "census_before_save": before_save,
                   "post_save_census": final, "post_save_readback": readback})
    _write_json(record_path, record)
    unreal.log("%s_APPLY_OK|run=%s|actor=%s|component=%s|actor_bHidden_unchanged=1|visible=0|hidden_in_game=1|mesh_cleared_for_pie=1|plume_unchanged=1|saved=%s|show_saved=0|backup=%s|record=%s|census_after=%s" %
               (MARK, run, _path(actor), _path(apparatus), WORLD, backup["root"], record_path, json.dumps(final)))


if unreal is not None:
    try:
        main()
    except Exception as exc:
        unreal.log_error("%s_FAILED|%r" % (MARK, exc))
        raise
