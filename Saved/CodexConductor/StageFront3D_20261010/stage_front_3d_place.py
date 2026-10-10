"""Guarded DRY/APPLY/VERIFY/REVERT placement for Job 131; never run by author."""
from __future__ import annotations

import datetime
import importlib.util
import json
import os
import shutil


HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
ARGS = os.path.join(HERE, "stage_front_3d_place_args.json")
RECORD = os.path.join(HERE, "stage_front_3d_place_record.json")


def _core():
    spec = importlib.util.spec_from_file_location("stage_front_3d_core", os.path.join(HERE, "stage_front_3d_core.py"))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


C = _core()


class ToolError(RuntimeError): pass


def _u():
    import unreal
    return unreal


def _pkg(value):
    if value is None: return None
    text = value.get_path_name() if hasattr(value, "get_path_name") else str(value)
    if "'" in text: text = text.split("'", 2)[1]
    return text.split(".", 1)[0]


def read(path):
    with open(path, encoding="utf-8") as handle: return json.load(handle)


def write(path, doc, exclusive=False):
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(doc, handle, indent=1, sort_keys=True); handle.flush(); os.fsync(handle.fileno())
    if read(path) != json.loads(json.dumps(doc)): raise ToolError("JSON_READBACK|" + path)


class Ctx:
    def __init__(self, mode):
        self.u = _u(); self.mode = mode; self.run = "SF3DP-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.past_write = False
    def require(self, value, text):
        if not value:
            suffix = "|NOTHING_ELSE_SAVED_USE_DONT_SAVE" if self.past_write else ""
            self.u.log_error("%s_PLACE_%s_FAILED|run=%s|%s%s" % (C.MARK, self.mode, self.run, text, suffix))
            raise ToolError(text)


def census(u):
    lib = u.EditorLoadingAndSavingUtils
    names = lambda rows: sorted({_pkg(x.get_name()) for x in rows})
    return {"content": names(lib.get_dirty_content_packages()), "maps": names(lib.get_dirty_map_packages())}


def actors(u):
    return list(u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors())


def tags(actor): return sorted(str(x) for x in actor.get_editor_property("tags"))


def state(c, rows=None):
    rows = actors(c.u) if rows is None else rows
    editor = c.u.get_editor_subsystem(c.u.UnrealEditorSubsystem); world = editor.get_editor_world()
    return {"world": world.get_outermost().get_name() if world else None,
            "pie": editor.get_game_world() is not None,
            "sequence": c.u.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None,
            "dirty": census(c.u), "tagged": sum(C.TAG in tags(x) for x in rows),
            "labels": {r["label"]: sum(str(x.get_actor_label()) == r["label"] for x in rows)
                       for r in C.build_plan(PROJECT)["actors"]},
            "parents": sum(str(x.get_actor_label()) == C.PARENT_LABEL for x in rows)}


def guard(c, mode, attach):
    got = state(c); problems = []
    if got["world"] != C.WORLD: problems.append("WRONG_WORLD|" + str(got["world"]))
    if got["pie"]: problems.append("PIE_OR_SIE_ACTIVE")
    if got["sequence"]: problems.append("SEQUENCER_OPEN")
    if got["dirty"] != {"content": [], "maps": []}: problems.append("DIRTY_AT_START|%s" % got["dirty"])
    if attach and got["parents"] != 1: problems.append("PARENT_COUNT|%d" % got["parents"])
    if mode == "APPLY" and (got["tagged"] or any(got["labels"].values())): problems.append("OWNED_ACTORS_EXIST")
    if mode in ("VERIFY", "REVERT") and (got["tagged"] != 8 or any(x != 1 for x in got["labels"].values())):
        problems.append("OWNED_ACTORS_NOT_EXACT|%s" % got)
    c.require(not problems, " ; ".join(problems)); return got


def map_backup(c, label, facts):
    source = os.path.join(PROJECT, "Content", *C.MAP_RELATIVE.split("/"))
    c.require(os.path.isfile(source), "MAP_BACKUP_SOURCE_MISSING|" + source)
    root = os.path.join(PROJECT, "Backups", "Pre%s-%s" % (label, c.run)); os.makedirs(root, exist_ok=False)
    dest = os.path.join(root, "Content", *C.MAP_RELATIVE.split("/")); os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copy2(source, dest); c.require(os.path.getsize(source) == os.path.getsize(dest), "BACKUP_READBACK")
    write(os.path.join(root, "prestate.json"), {"run": c.run, "map": C.WORLD,
          "dirty_before": census(c.u), "copy": os.path.relpath(dest, root).replace("\\", "/"), "facts": facts}, exclusive=True)
    return root


def loaded_assets(c, plan):
    eal = c.u.EditorAssetLibrary; output = {}
    for row in plan["actors"]:
        if row["piece"] in output: continue
        mesh = eal.load_asset(row["mesh"]); mi = eal.load_asset(row["material"])
        c.require(isinstance(mesh, c.u.StaticMesh), "MESH_MISSING_OR_CLASS|" + row["mesh"])
        c.require(isinstance(mi, c.u.MaterialInstanceConstant), "MI_MISSING_OR_CLASS|" + row["material"])
        slots = [_pkg(x.get_editor_property("material_interface")) for x in mesh.get_editor_property("static_materials")]
        c.require(slots == [row["material"]], "MESH_MATERIALS|%s|%s" % (row["mesh"], slots))
        output[row["piece"]] = mesh
    return output


def actor_row(actor):
    comp = actor.get_editor_property("static_mesh_component")
    loc, rot, scale = actor.get_actor_location(), actor.get_actor_rotation(), actor.get_actor_scale3d()
    parent = actor.get_attach_parent_actor()
    return {"object_path": str(actor.get_path_name()), "label": str(actor.get_actor_label()), "folder": str(actor.get_folder_path()),
            "tags": tags(actor), "parent_label": str(parent.get_actor_label()) if parent else None,
            "mesh": _pkg(comp.get_editor_property("static_mesh")),
            "materials": [_pkg(comp.get_material(i)) for i in range(comp.get_num_materials())],
            "location_cm": [float(loc.x), float(loc.y), float(loc.z)],
            "rotation_rpy_deg": [float(rot.roll), float(rot.pitch), float(rot.yaw)],
            "scale": [float(scale.x), float(scale.y), float(scale.z)],
            "mobility": str(comp.get_editor_property("mobility")),
            "collision_profile": str(comp.get_collision_profile_name()),
            "collision_enabled": str(comp.get_collision_enabled()), "cast_shadow": bool(comp.get_editor_property("cast_shadow"))}


def near(a, b, tolerance): return len(a) == len(b) and all(abs(float(x)-float(y)) <= tolerance for x, y in zip(a, b))
def enum_is(value, tail): return tail in str(value).upper()


def validate_readback(c, plan, current, attach):
    by_label = {}; [by_label.setdefault(str(x.get_actor_label()), []).append(x) for x in current]
    output, problems = {}, []
    for row in plan["actors"]:
        hits = by_label.get(row["label"], [])
        if len(hits) != 1: problems.append("LABEL_COUNT|%s|%d" % (row["label"], len(hits))); continue
        got = actor_row(hits[0]); output[row["label"]] = got
        if got["folder"] != C.FOLDER: problems.append("FOLDER|" + row["label"])
        if got["tags"] != sorted(row["tags"]): problems.append("TAGS|" + row["label"])
        if got["mesh"] != row["mesh"]: problems.append("MESH|" + row["label"])
        if got["materials"] != [row["material"]]: problems.append("MATERIAL|" + row["label"])
        if not near(got["location_cm"], row["location_cm"], .5): problems.append("LOCATION|" + row["label"])
        if not near(got["rotation_rpy_deg"], row["rotation_rpy_deg"], .001): problems.append("ROTATION|" + row["label"])
        if not near(got["scale"], row["scale"], 1e-6): problems.append("SCALE|" + row["label"])
        if got["parent_label"] != (C.PARENT_LABEL if attach else None): problems.append("PARENT|" + row["label"])
        if not enum_is(got["mobility"], "STATIC"): problems.append("MOBILITY|" + row["label"])
        if got["collision_profile"].lower() != "nocollision" or not enum_is(got["collision_enabled"], "NO_COLLISION"):
            problems.append("COLLISION|" + row["label"])
        if not got["cast_shadow"]: problems.append("SHADOW|" + row["label"])
    c.require(not problems, "READBACK|%s" % problems); return output


def save_map(c):
    c.require(census(c.u) == {"content": [], "maps": [C.WORLD]}, "DIRTY_SET_NOT_EXACT|%s" % census(c.u))
    world = c.u.get_editor_subsystem(c.u.UnrealEditorSubsystem).get_editor_world()
    c.require(c.u.EditorLoadingAndSavingUtils.save_map(world, C.WORLD), "MAP_SAVE_FAILED")
    c.require(census(c.u) == {"content": [], "maps": []}, "POST_SAVE_DIRTY|%s" % census(c.u))


def run_dry(c, plan, values):
    before = guard(c, "DRY", values["attach"]); eal = c.u.EditorAssetLibrary
    missing = sorted({x[k] for x in plan["actors"] for k in ("mesh", "material") if not eal.does_asset_exist(x[k])})
    c.require(census(c.u) == before["dirty"], "DRY_DIRTIED")
    c.u.log("%s_PLACE_DRY_%s|run=%s|actors=8|mutated=0|missing=%s|attach=%d|folder=%s|tag=%s" %
            (C.MARK, "OK" if not missing else "REFUSED", c.run, missing, values["attach"], C.FOLDER, C.TAG))


def run_apply(c, plan, values):
    current = actors(c.u); guard(c, "APPLY", values["attach"]); meshes = loaded_assets(c, plan)
    backup_dir = map_backup(c, "StageFront3DPlace", {"plan_hash": plan["hash"], "actors": plan["actors"]})
    record = {"schema": 1, "run": c.run, "world": C.WORLD, "tag": C.TAG, "plan": plan, "plan_hash": plan["hash"],
              "backup": backup_dir, "applied": False, "verified": False, "actors": {}}
    write(RECORD, record, exclusive=True)
    subsystem = c.u.get_editor_subsystem(c.u.EditorActorSubsystem)
    parents = [x for x in current if str(x.get_actor_label()) == C.PARENT_LABEL]; parent = parents[0] if values["attach"] else None
    for row in plan["actors"]:
        roll, pitch, yaw = row["rotation_rpy_deg"]
        actor = subsystem.spawn_actor_from_class(c.u.StaticMeshActor, c.u.Vector(*row["location_cm"]),
                c.u.Rotator(roll=roll, pitch=pitch, yaw=yaw)); c.require(actor is not None, "SPAWN|" + row["label"])
        c.past_write = True; actor.modify(); actor.set_actor_label(row["label"]); actor.set_folder_path(c.u.Name(C.FOLDER))
        actor.set_editor_property("tags", [c.u.Name(x) for x in row["tags"]]); actor.set_actor_scale3d(c.u.Vector(*row["scale"]))
        comp = actor.get_editor_property("static_mesh_component"); comp.modify(); comp.set_mobility(c.u.ComponentMobility.STATIC)
        comp.set_static_mesh(meshes[row["piece"]]); comp.set_collision_profile_name("NoCollision")
        comp.set_collision_enabled(c.u.CollisionEnabled.NO_COLLISION); comp.set_cast_shadow(True)
        if parent:
            rule = c.u.AttachmentRule.KEEP_WORLD; actor.attach_to_actor(parent, c.u.Name(""), rule, rule, rule, False)
    record["actors"] = validate_readback(c, plan, actors(c.u), values["attach"]); write(RECORD, record)
    save_map(c); record.update({"applied": True, "saved_census": census(c.u)}); write(RECORD, record)
    c.u.log("%s_PLACE_APPLY_SAVED|run=%s|actors=8|folder=%s|tag=%s|attach=KEEP_WORLD|verify=pending|backup=%s" %
            (C.MARK, c.run, C.FOLDER, C.TAG, backup_dir))


def run_verify(c, plan, values, record):
    guard(c, "VERIFY", values["attach"]); c.require(record.get("applied") and record.get("plan_hash") == plan["hash"], "RECORD_OR_PLAN_DRIFT")
    got = validate_readback(c, plan, actors(c.u), values["attach"]); c.require(census(c.u) == {"content": [], "maps": []}, "VERIFY_DIRTIED")
    record.update({"verified": True, "verify_run": c.run, "verified_readback": got}); write(RECORD, record)
    c.u.log("%s_PLACE_VERIFY_OK|run=%s|apply_run=%s|actors=8|transforms=8|materials=8|dirty=0" % (C.MARK, c.run, record["run"]))


def run_revert(c, plan, values, record):
    guard(c, "REVERT", values["attach"]); c.require(record.get("applied") and record.get("plan_hash") == plan["hash"], "RECORD_OR_PLAN_DRIFT")
    current = validate_readback(c, plan, actors(c.u), values["attach"])
    c.require(all(current[k]["object_path"] == record["actors"][k]["object_path"] for k in current), "OWNERSHIP_PATH_DRIFT")
    backup_dir = map_backup(c, "StageFront3DPlaceRevert", {"apply_run": record["run"], "actors": current})
    revert_path = os.path.join(HERE, "stage_front_3d_place_revert_%s.json" % c.run)
    revert = {"schema": 1, "run": c.run, "apply_run": record["run"], "backup": backup_dir, "reverted": False}
    write(revert_path, revert, exclusive=True)
    subsystem = c.u.get_editor_subsystem(c.u.EditorActorSubsystem); targets = [x for x in actors(c.u) if C.TAG in tags(x)]
    c.require(len(targets) == 8, "TAG_COUNT|%d" % len(targets))
    for actor in targets: actor.modify(); c.require(subsystem.destroy_actor(actor), "DESTROY|" + str(actor.get_actor_label())); c.past_write = True
    c.require(not [x for x in actors(c.u) if C.TAG in tags(x)], "REVERT_SURVIVORS"); save_map(c)
    archived = RECORD + ".reverted-" + c.run; os.replace(RECORD, archived)
    revert.update({"reverted": True, "archived_apply_record": archived, "saved_census": census(c.u)}); write(revert_path, revert)
    c.u.log("%s_PLACE_REVERT_OK|run=%s|apply_run=%s|actors=0|backup=%s" % (C.MARK, c.run, record["run"], backup_dir))


def main():
    args = read(ARGS); record = read(RECORD) if os.path.isfile(RECORD) else None
    mode, values = C.validate_place_args(args, record); c = Ctx(mode); base = C.build_plan(PROJECT)
    plan = {"world": C.WORLD, "folder": C.FOLDER, "tag": C.TAG, "parent": C.PARENT_LABEL,
            "attach": values["attach"], "actors": base["actors"]}
    plan["hash"] = C.canonical_hash(plan)
    c.u.log("%s_PLACE_START|run=%s|mode=%s" % (C.MARK, c.run, mode))
    if mode == "DRY": run_dry(c, plan, values)
    elif mode == "APPLY": run_apply(c, plan, values)
    elif mode == "VERIFY": run_verify(c, plan, values, record)
    else: run_revert(c, plan, values, record)


if __name__ != "__stage_front_3d_offline__": main()

