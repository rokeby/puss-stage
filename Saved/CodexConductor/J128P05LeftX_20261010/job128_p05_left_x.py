"""Job 128: guarded DRY/APPLY/REVERT for P05 left-panel local-X stagger.

Run only through job128_run.py inside the intended open UE 5.8 editor.
This file was written and tested offline; its author did not run Unreal.
"""
from __future__ import annotations

import copy
import datetime
import hashlib
import json
import os
import shutil

import job128_core as core

MARK = "JOB128_P05_LEFT_X"
HERE = os.path.dirname(os.path.abspath(__file__))
ARGS_PATH = os.path.join(HERE, "job128_args.json")
RECORD_PATH = os.path.join(HERE, "job128_record.json")
CLEAN = {"content": [], "maps": []}


def u():
    import unreal
    return unreal


def require(value, message):
    core.require(value, message)


def write_json(path, value):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def run_id(prefix="J128"):
    return "%s-%s" % (prefix, datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))


def census():
    unreal = u()
    names = lambda xs: sorted(str(x.get_name()).split(".", 1)[0] for x in xs)
    return {"content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}


def context():
    unreal = u()
    project = os.path.normcase(os.path.normpath(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))).rstrip("\\/")
    require(project == os.path.normcase(os.path.normpath("E:/PussStage")), "WRONG_PROJECT|" + project)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    actual = world.get_outermost().get_name() if world else None
    require(actual == core.WORLD, "WRONG_WORLD|" + str(actual))
    require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE")
    require(census() == CLEAN, "DIRTY_AT_START|" + json.dumps(census(), sort_keys=True))
    show = unreal.load_asset(core.SHOW)
    require(show is not None, "SHOW_LOAD_FAIL")
    actors = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
              if a.get_class().get_name() == "InfinityStagePassageActor"
              and str(a.get_actor_label()).startswith("Passage 05")
              and a.get_editor_property("show_asset") == show]
    require(len(actors) == 1, "P05_ACTOR_COUNT|%d" % len(actors))
    return project, world, show, actors[0]


def guid(value):
    unreal = u()
    try:
        return unreal.GuidLibrary.conv_guid_to_string(value).replace("-", "")
    except Exception:
        return value.to_string().replace("-", "")


def vec(v):
    return [float(v.x), float(v.y), float(v.z)]


def transform_plain(t):
    r = t.rotation.rotator()
    return {"location": vec(t.translation), "rotation": [float(r.roll), float(r.pitch), float(r.yaw)],
            "scale": vec(t.scale3d)}


def transform_from_plain(value):
    unreal = u()
    return unreal.Transform(location=unreal.Vector(*value["location"]),
                            rotation=unreal.Rotator(roll=value["rotation"][0],
                                                    pitch=value["rotation"][1], yaw=value["rotation"][2]),
                            scale=unreal.Vector(*value["scale"]))


def export(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [export(x) for x in value]
    if hasattr(value, "export_text"):
        return value.export_text()
    if hasattr(value, "to_string"):
        return value.to_string()
    return str(value)


def panel_snapshot(panel):
    local = transform_plain(panel.get_editor_property("local_transform"))
    return {"local_transform": local, "full_export": export(panel)}


def cue_snapshot(cue):
    pair = cue.get_editor_property("wing_pair")
    return {"cue_guid": guid(cue.get_editor_property("cue_guid")),
            "cue_label": str(cue.get_editor_property("label")),
            "cue_export": export(cue), "left": panel_snapshot(pair.get_editor_property("left")),
            "right": panel_snapshot(pair.get_editor_property("right"))}


def p05_cues(show):
    rows = [(i, cue) for i, cue in enumerate(show.get_editor_property("cues"))
            if str(cue.get_editor_property("label")).startswith("P05 Wing ")]
    require(len(rows) == core.COUNT, "P05_COUNT|expected=93|actual=%d" % len(rows))
    return rows


def instance_transform(ref):
    comp = ref.get_editor_property("component")
    value = comp.get_instance_transform(int(ref.get_editor_property("instance_index")), True)
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], bool):
        require(value[0], "INSTANCE_TRANSFORM_FAIL")
        value = value[1]
    return value


def world_box(ref, transform):
    unreal = u()
    comp = ref.get_editor_property("component")
    mesh = comp.get_editor_property("static_mesh")
    require(isinstance(mesh, unreal.StaticMesh), "STATIC_MESH_MISSING")
    box = mesh.get_bounding_box()
    points = [transform.transform_location(unreal.Vector(x, y, z))
              for x in (box.min.x, box.max.x) for y in (box.min.y, box.max.y) for z in (box.min.z, box.max.z)]
    return {"min": [min(getattr(p, a) for p in points) for a in "xyz"],
            "max": [max(getattr(p, a) for p in points) for a in "xyz"],
            "mesh": str(mesh.get_path_name()).split(".", 1)[0]}


def refs_by_guid(actor):
    out = {}
    for ref in actor.get_editor_property("materialized_panels"):
        key = guid(ref.get_editor_property("cue_guid"))
        side = str(ref.get_editor_property("side")).upper()
        if "LEFT" in side:
            name = "left"
        elif "RIGHT" in side:
            name = "right"
        else:
            continue
        out.setdefault(key, {}).setdefault(name, []).append(ref)
    return out


def authority_fingerprints(show, actor):
    cues = list(show.get_editor_property("cues"))
    non_p05 = [export(c) for c in cues if not str(c.get_editor_property("label")).startswith("P05 Wing ")]
    p05_right = [export(c.get_editor_property("wing_pair").get_editor_property("right"))
                 for _, c in p05_cues(show)]
    other_refs = []
    for a in u().get_editor_subsystem(u().EditorActorSubsystem).get_all_level_actors():
        if a.get_class().get_name() != "InfinityStagePassageActor" or a == actor:
            continue
        other_refs.append([str(a.get_actor_label()), export(a.get_editor_property("materialized_panels"))])
    return {"non_p05_show_sha256": core.stable_hash(non_p05),
            "p05_right_sha256": core.stable_hash(p05_right),
            "other_passage_refs_sha256": core.stable_hash(sorted(other_refs, key=lambda x: x[0]))}


def live_rows(show, actor):
    refs = refs_by_guid(actor)
    rows = []
    for index, cue in p05_cues(show):
        key = guid(cue.get_editor_property("cue_guid"))
        require(key in refs and all(len(refs[key].get(s, [])) == 1 for s in ("left", "right")),
                "MATERIALIZED_REF_SCOPE|index=%d|guid=%s" % (index, key))
        pair = cue.get_editor_property("wing_pair")
        left, right = pair.get_editor_property("left"), pair.get_editor_property("right")
        lr, rr = refs[key]["left"][0], refs[key]["right"][0]
        lt, rt = instance_transform(lr), instance_transform(rr)
        rows.append({"cue_index": index, "cue_guid": key, "cue_label": str(cue.get_editor_property("label")),
                     "left_local": transform_plain(left.get_editor_property("local_transform")),
                     "right_local": transform_plain(right.get_editor_property("local_transform")),
                     "left_world_transform": transform_plain(lt), "right_world_transform": transform_plain(rt),
                     "left_box": world_box(lr, lt), "right_box": world_box(rr, rt),
                     "left_inward": vec(lr.get_editor_property("inward_world_direction")),
                     "right_inward": vec(rr.get_editor_property("inward_world_direction")),
                     "before_cue": cue_snapshot(cue)})
    return rows


def package_file(project, package):
    stem = os.path.join(project, "Content", *package[len("/Game/"):].split("/"))
    for ext in (".uasset", ".umap"):
        if os.path.isfile(stem + ext):
            return stem + ext
    raise core.GateError("PACKAGE_FILE_MISSING|" + package)


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def backup(project, run, prefix):
    root = os.path.join(project, "Backups", "%s-%s" % (prefix, run))
    os.makedirs(root, exist_ok=False)
    rows = []
    for package in (core.SHOW, core.WORLD):
        source = package_file(project, package)
        dest = os.path.join(root, package[len("/Game/"):].replace("/", os.sep) + os.path.splitext(source)[1])
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(source, dest)
        require(sha_file(source) == sha_file(dest), "BACKUP_HASH_MISMATCH|" + package)
        rows.append({"package": package, "source": source, "backup": dest, "sha256": sha_file(dest)})
    return {"root": root, "files": rows}


def save_narrow():
    unreal = u()
    dirty = census()
    require(set(dirty["content"]) <= {core.SHOW} and set(dirty["maps"]) <= {core.WORLD},
            "OUT_OF_SCOPE_DIRTY|" + json.dumps(dirty, sort_keys=True))
    require(core.SHOW in dirty["content"], "SHOW_NOT_DIRTY")
    require(core.WORLD in dirty["maps"], "LEVEL_NOT_DIRTY")
    require(unreal.EditorAssetLibrary.save_asset(core.SHOW, only_if_is_dirty=False), "SHOW_SAVE_FAIL")
    require(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "LEVEL_SAVE_FAIL")
    require(census() == CLEAN, "DIRTY_AFTER_SAVE|" + json.dumps(census(), sort_keys=True))


def set_left_x(show, plans, expected_rows):
    cues = list(show.get_editor_property("cues"))
    by_key = {(r["cue_index"], r["cue_guid"]): r for r in expected_rows}
    for plan in plans:
        index, key = int(plan["cue_index"]), str(plan["cue_guid"])
        cue = cues[index]
        require(guid(cue.get_editor_property("cue_guid")) == key, "CUE_IDENTITY_DRIFT")
        before = by_key[(index, key)]["before_cue"]
        pair = cue.get_editor_property("wing_pair")
        left = pair.get_editor_property("left")
        actual = transform_plain(left.get_editor_property("local_transform"))
        require(actual == before["left"]["local_transform"], "LEFT_TRANSFORM_DRIFT|" + key)
        target = copy.deepcopy(actual)
        target["location"][0] = float(plan["after_left_local_x_cm"])
        require(core.x_only_changed(actual, target) or abs(target["location"][0] - actual["location"][0]) <= 1e-6,
                "NON_X_MUTATION")
        left.set_editor_property("local_transform", transform_from_plain(target))
        pair.set_editor_property("left", left)
        cue.set_editor_property("wing_pair", pair)
        cues[index] = cue
    show.set_editor_property("cues", cues)


def restore_left_x(show, record):
    cues = list(show.get_editor_property("cues"))
    for row in record["baseline_rows"]:
        index, key = int(row["cue_index"]), str(row["cue_guid"])
        cue = cues[index]
        require(guid(cue.get_editor_property("cue_guid")) == key, "REVERT_IDENTITY_DRIFT")
        pair = cue.get_editor_property("wing_pair")
        left = pair.get_editor_property("left")
        current = transform_plain(left.get_editor_property("local_transform"))
        applied = next(x for x in record["plan"]["rows"] if x["cue_guid"] == key)
        require(abs(current["location"][0] - float(applied["after_left_local_x_cm"])) <= 0.001,
                "REVERT_OWNED_X_DRIFT|" + key)
        current["location"][0] = float(row["left_local"]["location"][0])
        left.set_editor_property("local_transform", transform_from_plain(current))
        pair.set_editor_property("left", left); cue.set_editor_property("wing_pair", pair); cues[index] = cue
    show.set_editor_property("cues", cues)


def dry(run, show, actor):
    before_fp = authority_fingerprints(show, actor)
    rows = live_rows(show, actor)
    signs = core.choose_sign(rows)
    require(census() == CLEAN, "DRY_DIRTIED_EDITOR")
    chosen = signs["chosen"]
    doc = {"version": 1, "mode": "DRY", "run": run, "status": "PASS", "authority": core.SHOW,
           "passage_actor": str(actor.get_actor_label()), "recorded_sign_evidence": core.recorded_sign_evidence(),
           "chosen_plan": chosen, "rejected_plus_plan_summary": {k: signs["rejected"][k] for k in
               ("sign", "relation", "minimum_gap_before_cm", "minimum_gap_after_cm", "overlap_count_after")},
           "authority_fingerprints": before_fp, "baseline_rows": rows, "dirty_after": census()}
    doc["review_sha256"] = core.stable_hash({"plan": chosen, "fingerprints": before_fp})
    doc["confirm"] = "APPLY JOB128 " + doc["review_sha256"][:16]
    path = os.path.join(HERE, "job128_dry_latest.json")
    write_json(path, doc)
    u().log("%s_DRY_OK|run=%s|rows=93|min_before=%.3f|min_after=%.3f|confirm='%s'|report=%s" %
            (MARK, run, chosen["minimum_gap_before_cm"], chosen["minimum_gap_after_cm"], doc["confirm"], path))
    return doc


def apply(run, args, project, show, actor):
    require(os.path.isfile(os.path.join(HERE, "job128_dry_latest.json")), "DRY_REQUIRED")
    dry_doc = read_json(os.path.join(HERE, "job128_dry_latest.json"))
    require(args.get("confirm") == dry_doc.get("confirm"), "CONFIRM_MISMATCH|need=" + str(dry_doc.get("confirm")))
    require(not os.path.exists(RECORD_PATH), "ACTIVE_RECORD_EXISTS|REVERT_FIRST")
    rows = live_rows(show, actor)
    signs = core.choose_sign(rows)
    fp = authority_fingerprints(show, actor)
    review = core.stable_hash({"plan": signs["chosen"], "fingerprints": fp})
    require(review == dry_doc["review_sha256"], "DRY_DRIFT|rerun DRY")
    b = backup(project, run, "PreP05LeftLocalX")
    record = {"version": 1, "status": "WRITING", "apply_run": run, "backup": b,
              "plan": signs["chosen"], "baseline_rows": rows, "before_fingerprints": fp,
              "dry_review_sha256": review}
    with open(RECORD_PATH, "x", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, sort_keys=True, default=str); handle.write("\n")
    set_left_x(show, signs["chosen"]["rows"], rows)
    require(authority_fingerprints(show, actor)["p05_right_sha256"] == fp["p05_right_sha256"], "RIGHT_WINGS_CHANGED")
    require(authority_fingerprints(show, actor)["non_p05_show_sha256"] == fp["non_p05_show_sha256"], "OTHER_PASSAGES_SHOW_CHANGED")
    require(bool(actor.materialize_passage()), "P05_MATERIALIZE_FAIL")
    save_narrow()
    after_rows = live_rows(show, actor)
    # Current local relation already equals target, so delta is zero; verify geometry directly.
    require(all(abs(r["left_local"]["location"][0] - r["right_local"]["location"][0] + 20.0) <= 0.001
                for r in after_rows), "SAVED_RELATION_READBACK_FAIL")
    after_fp = authority_fingerprints(show, actor)
    untouched = core.untouched_refusals(fp, after_fp)
    require(not untouched, "UNTOUCHED_INVARIANT_FAIL|" + json.dumps(untouched))
    gaps = [core.aabb_gap(r["left_box"], r["right_box"]) for r in after_rows]
    require(min(gaps) > 1e-4, "SAVED_OVERLAP_REMAINS")
    record.update({"status": "APPLIED", "after_fingerprints": after_fp,
                   "saved_readback": {"row_count": len(after_rows), "minimum_gap_cm": min(gaps),
                                      "right_untouched": True, "other_passages_untouched": True},
                   "saved_packages": [core.SHOW, core.WORLD], "dirty_after": census()})
    write_json(RECORD_PATH, record)
    report = os.path.join(HERE, "job128_apply_%s.json" % run); write_json(report, record)
    u().log("%s_APPLY_OK|run=%s|rows=93|min_gap=%.3f|saved=Show+level|record=%s" %
            (MARK, run, min(gaps), RECORD_PATH))


def revert(run, args, project, show, actor):
    require(os.path.isfile(RECORD_PATH), "NO_ACTIVE_RECORD")
    record = read_json(RECORD_PATH)
    require(record.get("status") == "APPLIED", "RECORD_NOT_APPLIED")
    need = "REVERT JOB128 " + record["apply_run"]
    require(args.get("confirm") == need, "CONFIRM_MISMATCH|need=" + need)
    current_fp = authority_fingerprints(show, actor)
    require(current_fp["p05_right_sha256"] == record["before_fingerprints"]["p05_right_sha256"], "RIGHT_WING_DRIFT")
    require(current_fp["non_p05_show_sha256"] == record["before_fingerprints"]["non_p05_show_sha256"], "OTHER_PASSAGE_DRIFT")
    require(current_fp["other_passage_refs_sha256"] == record["after_fingerprints"]["other_passage_refs_sha256"],
            "OTHER_PASSAGE_LEVEL_DRIFT")
    b = backup(project, run, "PreP05LeftLocalXRevert")
    restore_left_x(show, record)
    require(bool(actor.materialize_passage()), "P05_MATERIALIZE_FAIL")
    save_narrow()
    after_rows = live_rows(show, actor)
    baseline = {(r["cue_index"], r["cue_guid"]): r for r in record["baseline_rows"]}
    for row in after_rows:
        old = baseline[(row["cue_index"], row["cue_guid"])]
        require(abs(row["left_local"]["location"][0] - old["left_local"]["location"][0]) <= 0.001,
                "REVERT_X_READBACK_FAIL|" + row["cue_guid"])
    fp = authority_fingerprints(show, actor)
    untouched = core.untouched_refusals(record["before_fingerprints"], fp)
    require(not untouched, "UNTOUCHED_INVARIANT_FAIL_REVERT|" + json.dumps(untouched))
    record.update({"status": "REVERTED", "revert_run": run, "revert_backup": b,
                   "revert_fingerprints": fp, "dirty_after_revert": census()})
    archived = RECORD_PATH.replace(".json", ".reverted-%s.json" % run)
    write_json(archived, record)
    os.replace(RECORD_PATH, RECORD_PATH + ".consumed-%s" % run)
    u().log("%s_REVERT_OK|run=%s|apply_run=%s|rows=93|archive=%s" %
            (MARK, run, record["apply_run"], archived))


def main(raw=None):
    args = dict(raw or read_json(ARGS_PATH))
    mode = str(args.get("mode", "DRY")).upper()
    require(mode in ("DRY", "APPLY", "REVERT"), "MODE_INVALID|" + mode)
    if mode == "DRY":
        require(args.get("confirm") == "DRY JOB128", "CONFIRM_MISMATCH|need=DRY JOB128")
    run = run_id()
    try:
        project, _world, show, actor = context()
        if mode == "DRY":
            dry(run, show, actor)
        elif mode == "APPLY":
            apply(run, args, project, show, actor)
        else:
            revert(run, args, project, show, actor)
    except Exception as exc:
        u().log_error("%s_STOPPED|run=%s|mode=%s|reason=%s|census=%s" %
                      (MARK, run, mode, str(exc).replace("\n", "\\n"), json.dumps(census(), sort_keys=True)))
        raise


if __name__ == "__job128_runner__":
    main(globals().get("JOB128_ARGS"))
