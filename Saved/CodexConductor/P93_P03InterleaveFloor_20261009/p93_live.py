"""Codex job 93: guarded P03 wing-pair interleave and dark-wet floor material.

Modes are independent by operation:
  {"operation":"WINGS","mode":"DRY","confirm":"DRY P93WINGS"}
  {"operation":"WINGS","mode":"APPLY","confirm":"APPLY P93WINGS <DRY token>"}
  {"operation":"WINGS","mode":"REVERT","confirm":"REVERT P93WINGS <apply run id>"}
  {"operation":"FLOOR","mode":"DRY","confirm":"DRY P93FLOOR"}
  {"operation":"FLOOR","mode":"APPLY","confirm":"APPLY P93FLOOR <DRY token>"}
  {"operation":"FLOOR","mode":"REVERT","confirm":"REVERT P93FLOOR <apply run id>"}

Offline-authored; never run here. The conductor runs DRY then APPLY separately. Each APPLY/REVERT requires a clean
editor, creates a sha256-verified Backups/PreP93... folder before mutation, records exact pre-state, saves only named
packages, reads back after save, and requires a clean final census. No Save All. No deletion.
"""
import datetime
import hashlib
import importlib.util
import json
import os
import shutil

try:
    import unreal
except ImportError:
    unreal = None

HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = os.path.join(HERE, "p93_args.json")


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


core = load_module("p93_core_live", os.path.join(HERE, "p93_core.py"))


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, value):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def digest_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class Ops:
    def __init__(self):
        self.editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)

    def log(self, value):
        unreal.log(value)

    def fail(self, run, reason):
        unreal.log_error("P93_P03_FAILED|run=%s|%s" % (run, reason))
        raise core.GateError(reason)

    def guid(self, value):
        # str(FGuid) changes per call in UE 5.8; the library conversion is the only identity used.
        return core.normalize_guid(unreal.GuidLibrary.conv_guid_to_string(value))

    def context(self):
        if self.editor.get_game_world() is not None:
            raise core.GateError("PIE_OR_SIE_ACTIVE")
        world = self.editor.get_editor_world()
        name = str(world.get_outermost().get_name()) if world else None
        if name != core.WORLD_PATH:
            raise core.GateError("WRONG_WORLD %s" % name)

    def census(self):
        lib = unreal.EditorLoadingAndSavingUtils
        def package_name(value):
            for accessor in ("get_path_name", "get_name"):
                fn = getattr(value, accessor, None)
                if fn:
                    return str(fn()).split(".")[0]
            return str(value).split(".")[0]
        return {
            "content": sorted(package_name(x) for x in lib.get_dirty_content_packages()),
            "maps": sorted(package_name(x) for x in lib.get_dirty_map_packages()),
        }

    def project_dir(self):
        return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())

    def show(self):
        value = unreal.EditorAssetLibrary.load_asset(core.SHOW_PATH)
        if value is None:
            raise core.GateError("SHOW_LOAD_FAILED")
        return value

    def p03_settings(self, show):
        settings = list(show.get_editor_property("passage_settings"))
        matches = [(i, s) for i, s in enumerate(settings) if str(s.get_editor_property("label")) == core.P03_LABEL]
        if len(matches) != 1:
            raise core.GateError("P03_SETTINGS_COUNT %d" % len(matches))
        return settings, matches[0][0], matches[0][1]

    def actor_for_passage(self, passage_guid):
        world = self.editor.get_editor_world()
        actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStagePassageActor)
        matches = [a for a in actors if self.guid(a.get_editor_property("passage_guid")) == passage_guid]
        if len(matches) != 1:
            raise core.GateError("P03_ACTOR_COUNT %d" % len(matches))
        return matches[0]

    @staticmethod
    def mesh_path(mesh):
        return None if mesh is None else str(mesh.get_path_name()).split(".")[0]

    def read_wings(self):
        show = self.show()
        settings, _, st = self.p03_settings(show)
        passage_guid = self.guid(st.get_editor_property("passage_guid"))
        compiled = [self.guid(g) for g in show.get_wing_pair_cue_guids_in_passage(
            st.get_editor_property("passage_guid"))]
        cues = list(show.get_editor_property("cues"))
        index = {self.guid(c.get_editor_property("cue_guid")): i for i, c in enumerate(cues)}
        rows = []
        for guid in compiled:
            if guid not in index:
                raise core.GateError("COMPILED_CUE_UNRESOLVED %s" % guid)
            cue = cues[index[guid]]
            pair = cue.get_editor_property("wing_pair")
            interval = pair.get_editor_property("interval_to_next")
            attachments = list(pair.get_editor_property("attachments"))
            rows.append({
                "cue_guid": guid,
                "label": str(cue.get_editor_property("label")),
                "type": core.enum_name(cue.get_editor_property("type")),
                "enabled": bool(cue.get_editor_property("enabled")),
                "show_index": index[guid],
                "interval_ticks": int(interval.value),
                "gap_cm": float(pair.get_editor_property("gap_to_next_cm")),
                "L_mesh": self.mesh_path(pair.get_editor_property("left").get_editor_property("mesh")),
                "R_mesh": self.mesh_path(pair.get_editor_property("right").get_editor_property("mesh")),
                "mechanism_sha": core.sha(pair.get_editor_property("mechanism").export_text()),
                "attachments_sha": core.sha([a.export_text() for a in attachments]),
                "cue_text": cue.export_text(),
            })
        if [r["show_index"] for r in rows] != list(range(rows[0]["show_index"], rows[0]["show_index"] + len(rows))):
            raise core.GateError("P03_NOT_CONTIGUOUS")
        meta = {
            "passage_guid": passage_guid,
            "first_cue_guid": self.guid(st.get_editor_property("first_cue_guid")),
            "last_cue_guid": self.guid(st.get_editor_property("last_cue_guid")),
            "first_show_index": rows[0]["show_index"],
            "settings_count": len(settings),
        }
        return rows, meta

    def write_wings(self, plan):
        show = self.show()
        cues = list(show.get_editor_property("cues"))
        first = min(r["show_index"] for r in self.read_wings()[0])
        live = {self.guid(c.get_editor_property("cue_guid")): c for c in cues[first:first + 21]}
        ordered = []
        for row in plan["rows"]:
            cue = live[row["cue_guid"]]
            pair = cue.get_editor_property("wing_pair")
            interval = pair.get_editor_property("interval_to_next")
            interval.set_editor_property("value", int(row["interval_ticks"]))
            pair.set_editor_property("interval_to_next", interval)
            pair.set_editor_property("gap_to_next_cm", float(row["gap_cm"]))
            cue.set_editor_property("wing_pair", pair)
            ordered.append(cue)
        new_cues = cues[:first] + ordered + cues[first + 21:]
        core.require(len(new_cues) == len(cues), "CUE_COUNT_WOULD_CHANGE")
        show.modify()
        show.set_editor_property("cues", new_cues)
        # First and last remain the same by design. Do not write engine-minted identity fields.

    def restore_wing_order_and_slots(self, record):
        show = self.show()
        cues = list(show.get_editor_property("cues"))
        first = int(record["meta"]["first_show_index"])
        live = {self.guid(c.get_editor_property("cue_guid")): c for c in cues[first:first + 21]}
        restored = []
        for ordinal, guid in enumerate(record["plan"]["before_guids"]):
            cue = live[guid]
            pair = cue.get_editor_property("wing_pair")
            slot = record["original_slots_by_guid"][guid]
            interval = pair.get_editor_property("interval_to_next")
            interval.set_editor_property("value", int(slot["interval_ticks"]))
            pair.set_editor_property("interval_to_next", interval)
            pair.set_editor_property("gap_to_next_cm", float(slot["gap_cm"]))
            cue.set_editor_property("wing_pair", pair)
            restored.append(cue)
        show.modify()
        show.set_editor_property("cues", cues[:first] + restored + cues[first + 21:])

    def materialize(self, passage_guid):
        actor = self.actor_for_passage(passage_guid)
        if not bool(actor.materialize_passage()):
            raise core.GateError("MATERIALIZE_FALSE")
        return int(actor.get_editor_property("materialized_wing_pair_count"))

    def floor(self):
        actors = unreal.GameplayStatics.get_all_actors_of_class(self.editor.get_editor_world(), unreal.Actor)
        matches = [a for a in actors if str(a.get_actor_label()) == core.FLOOR_LABEL]
        if len(matches) != 1:
            raise core.GateError("FLOOR_ACTOR_COUNT %d" % len(matches))
        actor = matches[0]
        comps = list(actor.get_components_by_class(unreal.StaticMeshComponent))
        if len(comps) != 1:
            raise core.GateError("FLOOR_COMPONENT_COUNT %d" % len(comps))
        comp = comps[0]
        material = comp.get_material(0)
        path = None if material is None else str(material.get_path_name())
        # SceneComponent exposes this as an accessor in UE Python, not an editor property.
        transform = comp.get_relative_transform().export_text()
        return actor, comp, core.floor_plan(path, transform, str(comp.get_path_name()))

    def set_floor_material(self, path):
        actor, comp, before = self.floor()
        material = unreal.EditorAssetLibrary.load_asset(path.split(".")[0])
        if material is None:
            raise core.GateError("MATERIAL_LOAD_FAILED %s" % path)
        actor.modify(); comp.modify(); comp.set_material(0, material)
        _, _, after = self.floor()
        if after["before_material"].split(".")[0] != path.split(".")[0]:
            raise core.GateError("FLOOR_IN_MEMORY_READBACK")
        if after["transform_sha"] != before["transform_sha"]:
            raise core.GateError("FLOOR_TRANSFORM_CHANGED")
        return after

    def backup(self, name, include_show):
        root = self.project_dir()
        dest = os.path.join(root, "Backups", name)
        if os.path.exists(dest):
            raise core.GateError("BACKUP_EXISTS %s" % dest)
        os.makedirs(dest)
        rels = [core.WORLD_FILE_REL]
        if include_show:
            rels.insert(0, core.SHOW_FILE_REL)
        files = []
        for rel in rels:
            src = os.path.join(root, *rel.split("/"))
            dst = os.path.join(dest, os.path.basename(src))
            shutil.copy2(src, dst)
            if digest_file(src) != digest_file(dst):
                raise core.GateError("BACKUP_HASH_MISMATCH %s" % rel)
            files.append({"source": src, "copy": dst, "sha256": digest_file(dst)})
        write_json(os.path.join(dest, "manifest.json"), {"files": files})
        return dest, files

    def save_wings(self):
        if not unreal.EditorAssetLibrary.save_asset(core.SHOW_PATH, only_if_is_dirty=False):
            raise core.GateError("SAVE_SHOW_FALSE")
        if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
            raise core.GateError("SAVE_LEVEL_FALSE")

    def save_floor(self):
        if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
            raise core.GateError("SAVE_LEVEL_FALSE")


def require_clean(ops):
    census = ops.census()
    core.require(census == {"content": [], "maps": []}, "DIRTY_AT_START %s" % census)
    return census


def wing_paths():
    return (os.path.join(HERE, "p93_wings_dry_latest.json"), os.path.join(HERE, "p93_wings_active.json"))


def floor_paths():
    return (os.path.join(HERE, "p93_floor_dry_latest.json"), os.path.join(HERE, "p93_floor_active.json"))


def dry_wings(ops, run, args):
    before = require_clean(ops)
    core.require(args.get("confirm") == "DRY P93WINGS", "CONFIRM")
    rows, meta = ops.read_wings()
    plan = core.build_relayout(rows)
    report = {"run_id": run, "operation": "WINGS", "mode": "DRY", "dirty_before": before,
              "dirty_after": ops.census(), "meta": meta, "plan": plan}
    path, _ = wing_paths(); write_json(path, report)
    if plan["refusals"]:
        ops.fail(run, "WINGS_DRY_REFUSED %s" % plan["refusals"])
    ops.log("P93_P03_WINGS_DRY_OK|run=%s|cues=21|old=3|newer=18|old_target_ordinals=1,8,15|"
            "dirty=0+0|mutated=0|confirm=APPLY P93WINGS %s|report=%s" %
            (run, plan["confirm_token"], path))


def apply_wings(ops, run, args):
    require_clean(ops)
    dry_path, active_path = wing_paths()
    core.require(os.path.exists(dry_path), "NO_WINGS_DRY")
    if os.path.exists(active_path):
        core.require(read_json(active_path).get("state") == "REVERTED", "WINGS_ACTIVE_RECORD_EXISTS")
    dry = read_json(dry_path); plan = dry["plan"]
    core.require(args.get("confirm") == "APPLY P93WINGS " + plan["confirm_token"], "CONFIRM")
    rows, meta = ops.read_wings()
    fresh = core.build_relayout(rows)
    core.require(fresh["inputs_hash"] == plan["inputs_hash"], "LIVE_DRIFT_SINCE_DRY")
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup, files = ops.backup("PreP93P03Wings-%s" % stamp, True)
    record = {"schema": 1, "run_id": run, "state": "APPLYING", "backup": backup, "backup_files": files,
              "meta": meta, "plan": plan,
              "original_cue_text_by_guid": {core.normalize_guid(r["cue_guid"]): r["cue_text"] for r in rows},
              "original_slots_by_guid": {core.normalize_guid(r["cue_guid"]): {
                  "interval_ticks": r["interval_ticks"], "gap_cm": r["gap_cm"]} for r in rows}}
    record_path = os.path.join(HERE, "p93_wings_record_%s.json" % run)
    write_json(record_path, record); write_json(active_path, {"run_id": run, "record": record_path, "state": "APPLYING"})
    ops.write_wings(plan)
    count = ops.materialize(meta["passage_guid"])
    core.require(count == 21, "MATERIALIZED_COUNT %d" % count)
    allowed = {"content": [core.SHOW_PATH], "maps": [core.WORLD_PATH]}
    core.require(ops.census() == allowed, "DIRTY_SCOPE %s" % ops.census())
    bad = core.validate_relayout_readback(ops.read_wings()[0], plan)
    core.require(not bad, "IN_MEMORY_READBACK %s" % bad)
    ops.save_wings()
    core.require(ops.census() == {"content": [], "maps": []}, "DIRTY_AFTER_SAVE %s" % ops.census())
    bad = core.validate_relayout_readback(ops.read_wings()[0], plan)
    core.require(not bad, "POST_SAVE_READBACK %s" % bad)
    record["state"] = "APPLIED"; record["materialized_count"] = count; record["dirty_after"] = ops.census()
    write_json(record_path, record); write_json(active_path, {"run_id": run, "record": record_path, "state": "APPLIED"})
    ops.log("P93_P03_WINGS_APPLY_OK|run=%s|cues=21|old_ordinals=1,8,15|materialized=21|"
            "saved=show,level|dirty_after=0+0|backup=%s|record=%s" % (run, backup, record_path))


def revert_wings(ops, run, args):
    require_clean(ops)
    _, active_path = wing_paths(); core.require(os.path.exists(active_path), "NO_WINGS_ACTIVE")
    active = read_json(active_path); record = read_json(active["record"])
    core.require(active.get("state") == "APPLIED", "ACTIVE_NOT_APPLIED")
    core.require(args.get("confirm") == "REVERT P93WINGS " + record["run_id"], "CONFIRM")
    rows, meta = ops.read_wings()
    bad = core.validate_applied_owned(rows, record["plan"])
    core.require(not bad, "OWNED_DRIFT_SINCE_APPLY %s" % bad)
    core.require(meta["passage_guid"] == record["meta"]["passage_guid"], "PASSAGE_GUID_DRIFT")
    foreign_before = {r["cue_guid"]: {k: r[k] for k in ("label", "L_mesh", "R_mesh", "mechanism_sha", "attachments_sha")}
                      for r in rows}
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup, files = ops.backup("PreP93P03WingsRevert-%s" % stamp, True)
    ops.restore_wing_order_and_slots(record)
    count = ops.materialize(meta["passage_guid"]); core.require(count == 21, "MATERIALIZED_COUNT %d" % count)
    core.require(ops.census() == {"content": [core.SHOW_PATH], "maps": [core.WORLD_PATH]},
                 "DIRTY_SCOPE %s" % ops.census())
    now = ops.read_wings()[0]
    core.require([core.normalize_guid(r["cue_guid"]) for r in now] == record["plan"]["before_guids"], "REVERT_ORDER")
    core.require({r["cue_guid"]: {k: r[k] for k in ("label", "L_mesh", "R_mesh", "mechanism_sha", "attachments_sha")}
                  for r in now} == foreign_before, "REVERT_CHANGED_FOREIGN_FIELDS")
    for r in now:
        want = record["original_slots_by_guid"][r["cue_guid"]]
        core.require(int(r["interval_ticks"]) == int(want["interval_ticks"]) and
                     abs(float(r["gap_cm"]) - float(want["gap_cm"])) <= 1e-4,
                     "REVERT_SLOT_READBACK %s" % r["cue_guid"][:8])
    ops.save_wings(); core.require(ops.census() == {"content": [], "maps": []}, "DIRTY_AFTER_SAVE")
    now = ops.read_wings()[0]
    core.require([core.normalize_guid(r["cue_guid"]) for r in now] == record["plan"]["before_guids"], "POST_SAVE_REVERT")
    core.require({r["cue_guid"]: {k: r[k] for k in ("label", "L_mesh", "R_mesh", "mechanism_sha", "attachments_sha")}
                  for r in now} == foreign_before, "POST_SAVE_CHANGED_FOREIGN_FIELDS")
    revert_path = os.path.join(HERE, "p93_wings_revert_%s.json" % run)
    write_json(revert_path, {"run_id": run, "reverted_run": record["run_id"], "backup": backup,
                             "backup_files": files, "dirty_after": ops.census()})
    active["state"] = "REVERTED"; active["revert_record"] = revert_path; write_json(active_path, active)
    ops.log("P93_P03_WINGS_REVERT_OK|run=%s|reverted=%s|materialized=21|saved=show,level|"
            "dirty_after=0+0|backup=%s|record=%s" % (run, record["run_id"], backup, revert_path))


def dry_floor(ops, run, args):
    before = require_clean(ops); core.require(args.get("confirm") == "DRY P93FLOOR", "CONFIRM")
    _, _, plan = ops.floor(); plan["confirm_token"] = core.floor_token(plan)
    report = {"run_id": run, "operation": "FLOOR", "mode": "DRY", "dirty_before": before,
              "dirty_after": ops.census(), "plan": plan}
    path, _ = floor_paths(); write_json(path, report)
    core.require(plan["expected_walnut"] or plan["already_target"], "UNEXPECTED_SOURCE_MATERIAL %s" % plan["before_material"])
    ops.log("P93_P03_FLOOR_DRY_OK|run=%s|actors=1|components=1|slots=1|already_target=%s|"
            "dirty=0+0|mutated=0|confirm=APPLY P93FLOOR %s|report=%s" %
            (run, plan["already_target"], plan["confirm_token"], path))


def apply_floor(ops, run, args):
    require_clean(ops)
    dry_path, active_path = floor_paths(); core.require(os.path.exists(dry_path), "NO_FLOOR_DRY")
    if os.path.exists(active_path):
        core.require(read_json(active_path).get("state") == "REVERTED", "FLOOR_ACTIVE_RECORD_EXISTS")
    dry = read_json(dry_path); plan = dry["plan"]
    core.require(args.get("confirm") == "APPLY P93FLOOR " + plan["confirm_token"], "CONFIRM")
    _, _, fresh = ops.floor(); fresh["confirm_token"] = core.floor_token(fresh)
    core.require(fresh == plan, "LIVE_DRIFT_SINCE_DRY")
    core.require(not plan["already_target"], "ALREADY_TARGET_NO_APPLY_NEEDED")
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup, files = ops.backup("PreP93P03Floor-%s" % stamp, False)
    record_path = os.path.join(HERE, "p93_floor_record_%s.json" % run)
    record = {"schema": 1, "run_id": run, "state": "APPLYING", "plan": plan, "backup": backup,
              "backup_files": files}
    write_json(record_path, record); write_json(active_path, {"run_id": run, "record": record_path, "state": "APPLYING"})
    after = ops.set_floor_material(core.FLOOR_TARGET)
    core.require(ops.census() == {"content": [], "maps": [core.WORLD_PATH]}, "DIRTY_SCOPE %s" % ops.census())
    ops.save_floor(); core.require(ops.census() == {"content": [], "maps": []}, "DIRTY_AFTER_SAVE")
    _, _, saved = ops.floor()
    core.require(saved["before_material"].split(".")[0] == core.FLOOR_TARGET, "POST_SAVE_MATERIAL")
    core.require(saved["transform_sha"] == plan["transform_sha"], "POST_SAVE_TRANSFORM")
    record["state"] = "APPLIED"; record["after"] = after; record["dirty_after"] = ops.census()
    write_json(record_path, record); write_json(active_path, {"run_id": run, "record": record_path, "state": "APPLIED"})
    ops.log("P93_P03_FLOOR_APPLY_OK|run=%s|actors=1|components=1|slots=1|material=%s|"
            "saved=level|dirty_after=0+0|backup=%s|record=%s" %
            (run, core.FLOOR_TARGET, backup, record_path))


def revert_floor(ops, run, args):
    require_clean(ops)
    _, active_path = floor_paths(); core.require(os.path.exists(active_path), "NO_FLOOR_ACTIVE")
    active = read_json(active_path); record = read_json(active["record"])
    core.require(active.get("state") == "APPLIED", "ACTIVE_NOT_APPLIED")
    core.require(args.get("confirm") == "REVERT P93FLOOR " + record["run_id"], "CONFIRM")
    _, _, live = ops.floor()
    core.require(live["before_material"].split(".")[0] == core.FLOOR_TARGET, "OWNED_MATERIAL_DRIFT")
    core.require(live["transform_sha"] == record["plan"]["transform_sha"], "FOREIGN_TRANSFORM_DRIFT_REFUSED")
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup, files = ops.backup("PreP93P03FloorRevert-%s" % stamp, False)
    ops.set_floor_material(record["plan"]["before_material"])
    core.require(ops.census() == {"content": [], "maps": [core.WORLD_PATH]}, "DIRTY_SCOPE %s" % ops.census())
    ops.save_floor(); core.require(ops.census() == {"content": [], "maps": []}, "DIRTY_AFTER_SAVE")
    _, _, saved = ops.floor()
    core.require(saved["before_material"] == record["plan"]["before_material"], "POST_SAVE_REVERT_MATERIAL")
    revert_path = os.path.join(HERE, "p93_floor_revert_%s.json" % run)
    write_json(revert_path, {"run_id": run, "reverted_run": record["run_id"], "backup": backup,
                             "backup_files": files, "dirty_after": ops.census()})
    active["state"] = "REVERTED"; active["revert_record"] = revert_path; write_json(active_path, active)
    ops.log("P93_P03_FLOOR_REVERT_OK|run=%s|reverted=%s|saved=level|dirty_after=0+0|backup=%s|record=%s" %
            (run, record["run_id"], backup, revert_path))


def main():
    ops = Ops(); run = datetime.datetime.now().strftime("P93-%Y%m%d-%H%M%S")
    try:
        args = read_json(ARGS)
        operation = str(args.get("operation", "")).upper()
        mode = str(args.get("mode", "")).upper()
        ops.context()
        table = {("WINGS", "DRY"): dry_wings, ("WINGS", "APPLY"): apply_wings,
                 ("WINGS", "REVERT"): revert_wings, ("FLOOR", "DRY"): dry_floor,
                 ("FLOOR", "APPLY"): apply_floor, ("FLOOR", "REVERT"): revert_floor}
        core.require((operation, mode) in table, "ARGS operation=%s mode=%s" % (operation, mode))
        ops.log("P93_P03_START|run=%s|operation=%s|mode=%s|dirty=%s" % (run, operation, mode, ops.census()))
        table[(operation, mode)](ops, run, args)
    except Exception as exc:
        ops.fail(run, "%s: %s" % (type(exc).__name__, exc))


if unreal is not None:
    main()
