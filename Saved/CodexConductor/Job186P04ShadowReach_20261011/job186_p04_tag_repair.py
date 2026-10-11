"""Job 186: rematerialize P04 attachments from the Show to mint stable tags.

DRY is read-only. APPLY calls the native Show materializer; it never writes tags
directly. The Show and persistent map are backed up before the level mutation,
only the map is saved, and the saved actor identities are read back against the
current enabled P04 light attachment GUIDs in the Show.

Exact reversal of a materialization means restoring the backed-up map package.
That cannot safely happen while its world is loaded, so REVERT only prepares and
logs the editor-closed restore command implemented by job186_restore_backup.ps1.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import shutil

try:
    import unreal  # type: ignore
except ImportError:  # offline harness
    unreal = None


HERE = os.path.dirname(os.path.abspath(__file__))
MARK = "JOB186_P04_TAG_REPAIR"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
WORLD_PATH = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
TAG_PREFIX = "InfinityStage.Attachment."
RECORD = os.path.join(HERE, "job186_p04_tag_repair_record.json")
CONFIRM = {
    "APPLY": "APPLY JOB186 REMATERIALIZE P04 ATTACHMENTS FROM SHOW",
    "REVERT": "PREPARE JOB186 P04 MAP BACKUP RESTORE",
}


class Job186Error(RuntimeError):
    pass


def require(value, message):
    if not value:
        raise Job186Error(str(message))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def guid_text(value):
    if unreal is not None:
        try:
            return str(unreal.GuidLibrary.conv_guid_to_string(value)).upper()
        except Exception:
            pass
    return re.sub(r"[^0-9A-F]", "", str(value).upper())


def enum_name(value):
    text = str(value).upper()
    for candidate in ("WINGPAIR", "WING_PAIR", "LIGHT"):
        if re.search(r"(?:^|[.<_])%s(?:[: >]|$)" % candidate, text):
            return candidate
    return text.rsplit(".", 1)[-1].split(":", 1)[0].strip(" <>_")


def parse_identity_tag_text(tag):
    text = str(tag)
    if not text.startswith(TAG_PREFIX) or "|" not in text:
        return None
    cue, attachment = text[len(TAG_PREFIX):].split("|", 1)
    cue, attachment = guid_text(cue), guid_text(attachment)
    if len(cue) != 32 or len(attachment) != 32:
        return None
    return cue, attachment


def managed_identity_tag_text(tag):
    """Parse our tag namespace, refusing malformed identities by name."""
    text = str(tag)
    parsed = parse_identity_tag_text(text)
    if text.startswith(TAG_PREFIX):
        require(parsed is not None, "MALFORMED_IDENTITY_TAG|" + text)
    return parsed


def identity_tag(cue, attachment):
    return TAG_PREFIX + guid_text(cue) + "|" + guid_text(attachment)


def plan_from_rows(expected_light_ids, managed_rows):
    expected = sorted(set(expected_light_ids))
    require(len(expected) == len(expected_light_ids), "SHOW_LIGHT_ID_DUPLICATE")
    actual = []
    missing_tag = []
    stale_tag = []
    duplicate_tag = []
    seen = set()
    for row in managed_rows:
        if not row.get("has_light"):
            continue
        identity = row.get("identity")
        if identity is None:
            missing_tag.append(row["label"])
            continue
        tag = identity_tag(identity[0], identity[1])
        if tag in seen:
            duplicate_tag.append(tag)
        seen.add(tag)
        actual.append(tag)
        if tag not in expected:
            stale_tag.append(tag)
    actual = sorted(actual)
    missing_show = sorted(set(expected) - set(actual))
    extra_live = sorted(set(actual) - set(expected))
    needs_repair = bool(missing_tag or stale_tag or duplicate_tag or missing_show or extra_live)
    digest_payload = {
        "expected_light_ids": expected,
        "managed_light_rows": [{"label": r["label"], "path": r.get("path"),
                                "identity": r.get("identity"), "has_light": bool(r.get("has_light"))}
                               for r in managed_rows],
    }
    return {
        "expected_light_ids": expected,
        "expected_light_count": len(expected),
        "managed_count": len(managed_rows),
        "managed_light_count": sum(bool(r.get("has_light")) for r in managed_rows),
        "tagged_light_count": len(actual),
        "missing_tag_labels": sorted(missing_tag),
        "stale_tags": sorted(stale_tag),
        "duplicate_tags": sorted(duplicate_tag),
        "missing_show_identities": missing_show,
        "extra_live_identities": extra_live,
        "needs_repair": needs_repair,
        "plan_sha256": hashlib.sha256(canonical(digest_payload).encode("utf-8")).hexdigest(),
    }


def validate_readback(expected_light_ids, managed_rows):
    plan = plan_from_rows(expected_light_ids, managed_rows)
    require(not plan["needs_repair"], "TAG_READBACK_MISMATCH|" + canonical({
        key: plan[key] for key in ("missing_tag_labels", "stale_tags", "duplicate_tags",
                                  "missing_show_identities", "extra_live_identities")
    })[:6000])
    require(plan["tagged_light_count"] == plan["expected_light_count"], "TAG_READBACK_COUNT")
    return plan


def check_args(raw):
    raw = dict(raw or {})
    mode = str(raw.get("mode", "DRY")).upper()
    require(mode in ("DRY", "APPLY", "REVERT"), "MODE_INVALID|" + mode)
    if mode != "DRY":
        require(raw.get("confirm") == CONFIRM[mode], "CONFIRM_MISSING|need=" + CONFIRM[mode])
    if mode == "APPLY":
        require(re.fullmatch(r"[0-9a-f]{64}", str(raw.get("expected_plan_sha256", ""))),
                "EXPECTED_PLAN_SHA256_REQUIRED")
        require(isinstance(raw.get("expected_light_count"), int), "EXPECTED_LIGHT_COUNT_REQUIRED")
    return {"mode": mode, "confirm": raw.get("confirm"),
            "expected_plan_sha256": str(raw.get("expected_plan_sha256", "")),
            "expected_light_count": raw.get("expected_light_count")}


def asset_id(obj):
    path = str(obj.get_path_name()).split(":", 1)[0]
    leaf = path.rsplit("/", 1)[-1]
    return path[:-len(leaf) - 1] + "/" + leaf.split(".", 1)[0] if "." in leaf else path


def dirty_census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def world_guard():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    require(world is not None and asset_id(world) == WORLD_PATH,
            "WORLD_MISMATCH|" + (world.get_path_name() if world else "None"))
    require(editor.get_game_world() is None, "PIE_OR_SIMULATE")
    seq = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    require(seq is None or seq.get_current_level_sequence() is None, "SEQUENCER_IS_OPEN")
    require(dirty_census() == {"content": [], "maps": []},
            "DIRTY_BEFORE|" + canonical(dirty_census()))
    return world


def find_p04(world, show):
    hits = []
    for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
        label = str(actor.get_actor_label())
        try:
            owned_show = actor.get_editor_property("show_asset")
            panels = actor.get_editor_property("materialized_panels")
        except Exception:
            continue
        if re.search(r"Passage\s+0?4(?:\D|$)", label, re.I) and owned_show == show and panels is not None:
            hits.append(actor)
    require(len(hits) == 1, "P04_PASSAGE_COUNT|%d" % len(hits))
    return hits[0]


def light_components(actor):
    for name in ("LightComponentBase", "LightComponent"):
        cls = getattr(unreal, name, None)
        if cls is not None:
            values = list(actor.get_components_by_class(cls))
            if values:
                return values
    return []


def expected_show_light_ids(show, passage):
    cue_ids = {guid_text(ref.get_editor_property("cue_guid"))
               for ref in passage.get_editor_property("materialized_panels")}
    require(cue_ids, "P04_MATERIALIZED_CUES_EMPTY")
    out = []
    for cue in show.get_editor_property("cues"):
        cue_id = guid_text(cue.get_editor_property("cue_guid"))
        if cue_id not in cue_ids:
            continue
        pair = cue.get_editor_property("wing_pair")
        for attachment in pair.get_editor_property("attachments"):
            if bool(attachment.get_editor_property("enabled")) and enum_name(
                    attachment.get_editor_property("kind")) == "LIGHT":
                out.append(identity_tag(cue_id, attachment.get_editor_property("attachment_guid")))
    require(out, "P04_SHOW_LIGHTS_EMPTY")
    return sorted(out)


def managed_rows(passage):
    rows = []
    for actor in passage.get_editor_property("managed_attachment_actors"):
        if actor is None:
            continue
        identities = [parsed for parsed in (managed_identity_tag_text(tag) for tag in actor.tags)
                      if parsed]
        require(len(identities) <= 1, "MULTIPLE_IDENTITY_TAGS|" + actor.get_actor_label())
        rows.append({"label": str(actor.get_actor_label()), "path": str(actor.get_path_name()),
                     "identity": identities[0] if identities else None,
                     "has_light": bool(light_components(actor))})
    rows.sort(key=lambda row: (row["label"], row["path"]))
    return rows


def gather():
    world = world_guard()
    show = unreal.load_asset(SHOW_PATH)
    require(show is not None, "SHOW_MISSING")
    passage = find_p04(world, show)
    expected = expected_show_light_ids(show, passage)
    rows = managed_rows(passage)
    return {"world": world, "show": show, "passage": passage,
            "expected": expected, "rows": rows, "plan": plan_from_rows(expected, rows)}


def package_file(package_path, content_dir):
    base = os.path.normpath(os.path.join(content_dir, package_path[len("/Game/"):].replace("/", os.sep)))
    for ext in (".uasset", ".umap"):
        if os.path.isfile(base + ext):
            return base + ext
    raise Job186Error("PACKAGE_FILE_MISSING|" + package_path)


def file_sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def backup_packages(run_id):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    content = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir())
    root = os.path.join(project, "Backups", "PreJob186P04AttachmentTags-" + run_id)
    os.makedirs(root, exist_ok=False)
    rows = []
    for package in (SHOW_PATH, WORLD_PATH):
        source = package_file(package, content)
        relative = package[len("/Game/"):].replace("/", os.sep) + os.path.splitext(source)[1]
        destination = os.path.join(root, relative)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(source, destination)
        require(file_sha(source) == file_sha(destination), "BACKUP_HASH_MISMATCH|" + package)
        rows.append({"package": package, "source": source, "backup": destination,
                     "bytes": os.path.getsize(source), "sha256": file_sha(source)})
    return {"root": root, "packages": rows}


def write_json(path, value):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)


def report_path(mode, run_id):
    return os.path.join(HERE, "job186_p04_tag_repair_%s_%s.json" % (mode, run_id))


def run(raw):
    require(unreal is not None, "UNREAL_MODULE_REQUIRED")
    args = check_args(raw)
    mode = args["mode"]
    run_id = "J186P04TAG-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    report = {"schema_version": 1, "run": run_id, "mode": mode, "ok": False, "saved": False}
    try:
        if mode == "REVERT":
            world_guard()
            require(os.path.isfile(RECORD), "ACTIVE_RECORD_MISSING")
            record = json.load(open(RECORD, encoding="utf-8"))
            require(record.get("status") == "saved_readback_verified", "ACTIVE_RECORD_STATUS")
            command = "powershell -File Saved/CodexConductor/Job186P04ShadowReach_20261011/job186_restore_backup.ps1 -BackupRoot \"%s\" -Confirm \"RESTORE JOB186 P04 MAP BACKUP\"" % record["backup"]["root"]
            report.update({"ok": True, "saved": False, "restore_requires_editor_closed": True,
                           "backup": record["backup"], "restore_command": command})
            write_json(report_path(mode, run_id), report)
            unreal.log("%s_REVERT_READY|run=%s|NOTHING_SAVED|editor_closed_required=1|backup=%s" %
                       (MARK, run_id, record["backup"]["root"]))
            return report

        live = gather()
        report.update({"dirty_before": {"content": [], "maps": []}, "plan": live["plan"]})
        if mode == "DRY":
            require(dirty_census() == {"content": [], "maps": []}, "DRY_DIRTY_CHANGED")
            report["ok"] = True
            write_json(report_path(mode, run_id), report)
            unreal.log("%s_DRY_OK|run=%s|expected_lights=%d|managed_lights=%d|tagged_lights=%d|needs_repair=%d|plan_sha256=%s|NOTHING_SAVED" %
                       (MARK, run_id, live["plan"]["expected_light_count"],
                        live["plan"]["managed_light_count"], live["plan"]["tagged_light_count"],
                        int(live["plan"]["needs_repair"]), live["plan"]["plan_sha256"]))
            return report

        require(args["expected_plan_sha256"] == live["plan"]["plan_sha256"], "PLAN_DRIFT")
        require(args["expected_light_count"] == live["plan"]["expected_light_count"],
                "EXPECTED_LIGHT_COUNT_DRIFT")
        if not live["plan"]["needs_repair"]:
            report.update({"ok": True, "no_op": True})
            write_json(report_path(mode, run_id), report)
            unreal.log("%s_APPLY_OK|run=%s|NO_OP|readback=1|nothing_saved=1" % (MARK, run_id))
            return report
        require(not os.path.exists(RECORD), "ACTIVE_RECORD_EXISTS")
        backup = backup_packages(run_id)
        record = {"schema_version": 1, "run": run_id, "status": "prepared", "backup": backup,
                  "plan": live["plan"], "restore_script": "job186_restore_backup.ps1"}
        write_json(RECORD, record)
        live["passage"].modify()
        placed = int(live["passage"].materialize_attachments())
        post_rows = managed_rows(live["passage"])
        verified = validate_readback(live["expected"], post_rows)
        census = dirty_census()
        require(census["content"] == [] and set(census["maps"]) == {WORLD_PATH},
                "DIRTY_AFTER_MATERIALIZE|" + canonical(census))
        require(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(),
                "LEVEL_SAVE_FAILED")
        report["saved"] = True
        require(dirty_census() == {"content": [], "maps": []}, "DIRTY_AFTER_SAVE")
        fresh = gather()
        saved_readback = validate_readback(fresh["expected"], fresh["rows"])
        show_backup = next(row for row in backup["packages"] if row["package"] == SHOW_PATH)
        require(file_sha(show_backup["source"]) == show_backup["sha256"], "SHOW_CHANGED_ON_DISK")
        record.update({"status": "saved_readback_verified", "placed_attachments": placed,
                       "verified": verified, "saved_readback": saved_readback,
                       "saved_packages": [WORLD_PATH], "show_saved": False,
                       "final_census": {"content": [], "maps": []}})
        write_json(RECORD, record)
        report.update({"ok": True, "backup": backup, "placed_attachments": placed,
                       "readback": saved_readback, "saved_packages": [WORLD_PATH],
                       "show_saved": False, "record": RECORD})
        write_json(report_path(mode, run_id), report)
        unreal.log("%s_APPLY_OK|run=%s|expected_lights=%d|tagged_lights=%d|placed=%d|show_saved=0|map_saved=1|readback=1|dirty=0+0|record=%s" %
                   (MARK, run_id, len(live["expected"]), saved_readback["tagged_light_count"],
                    placed, RECORD))
        return report
    except Exception as error:
        report["error"] = "%s: %s" % (type(error).__name__, error)
        try:
            write_json(report_path(mode, run_id), report)
        except Exception:
            pass
        unreal.log_error("%s_STOPPED|run=%s|mode=%s|saved=%d|%s%s" %
                         (MARK, run_id, mode, int(report["saved"]), report["error"],
                          "" if report["saved"] else "|NOTHING_SAVED"))
        raise


def main():
    return run(globals().get("JOB186_P04_TAG_ARGS"))


if __name__ == "__main__":
    main()
