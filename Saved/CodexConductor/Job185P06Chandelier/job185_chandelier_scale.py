from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import unreal

WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
PREFIX = "P56_P75_P06_Chandelier_Body_Candle_"
FLAME_NAME = "ChandelierFlameFX"
FLAME_ASSET = "/Game/Stylish_Fire_VFX/Niagara/NS_Stylish_Fire_1"
LIGHT_TAG = "JOB182_P06_CHANDELIER_LIGHT"
HERE = os.path.dirname(__file__)
ARGS = os.path.join(HERE, "args.json")
REPORT = os.path.join(HERE, "latest_report.json")


def require(value, message):
    if not value:
        raise RuntimeError(message)


def aid(value):
    if value is None:
        return None
    text = str(value.get_path_name() if hasattr(value, "get_path_name") else value)
    return text.split(".", 1)[0]


def vec(value):
    return [float(value.x), float(value.y), float(value.z)]


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {
        "content": sorted(aid(x) for x in lib.get_dirty_content_packages()),
        "maps": sorted(aid(x) for x in lib.get_dirty_map_packages()),
    }


def package_file():
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()).rstrip("/\\")
    return os.path.join(project, "Content", "InfinityStage", "Dev", "Maps", "L_InfinityStage_V1VerticalSlice.umap")


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def backup(run):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()).rstrip("/\\")
    root = os.path.join(project, "Backups", "PreJob185P06Chandelier-" + run)
    os.makedirs(root, exist_ok=False)
    source = package_file()
    destination = os.path.join(root, "L_InfinityStage_V1VerticalSlice.umap")
    shutil.copy2(source, destination)
    require(digest(source) == digest(destination), "BACKUP_HASH")
    return {"root": root, "file": destination, "bytes": os.path.getsize(source), "sha256": digest(source)}


def find_scope():
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    candles = sorted([a for a in actors if str(a.get_actor_label()).startswith(PREFIX)], key=lambda a: str(a.get_actor_label()))
    require(len(candles) == 44, "CANDLE_COUNT|%d" % len(candles))
    rows = []
    for actor in candles:
        label = str(actor.get_actor_label())
        require(label.endswith("_Flame"), "CANDLE_LABEL|" + label)
        comps = [c for c in actor.get_components_by_class(unreal.NiagaraComponent)
                 if str(c.get_name()) == FLAME_NAME and aid(c.get_asset()) == FLAME_ASSET]
        require(len(comps) == 1, "FLAME_COMPONENT_COUNT|%s|%d" % (label, len(comps)))
        rows.append({"label": label, "actor_scale": vec(actor.get_actor_scale3d()),
                     "component_scale": vec(comps[0].get_world_scale()),
                     "sprite_scale": float(actor.get_editor_property("sprite_scale"))})
    lights = [a for a in actors if LIGHT_TAG in {str(t) for t in a.get_editor_property("tags")}]
    require(len(lights) == 9, "JOB182_LIGHT_COUNT|%d" % len(lights))
    return candles, rows, sorted(str(a.get_actor_label()) for a in lights)


def main():
    with open(ARGS, encoding="utf-8") as handle:
        args = json.load(handle)
    mode = str(args["mode"]).upper()
    require(mode in ("PROBE", "APPLY", "READBACK"), "MODE")
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    require(editor.get_game_world() is None, "PIE_ACTIVE")
    require(aid(editor.get_editor_world()) == WORLD, "WRONG_WORLD")
    require(census() == {"content": [], "maps": []}, "PRE_DIRTY|" + json.dumps(census(), sort_keys=True))
    candles, before, light_labels = find_scope()
    run = "J185-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_row = None
    if mode == "APPLY":
        require(args.get("confirm") == "APPLY JOB185 CHANDELIER SCALE", "CONFIRM")
        target = float(args["uniform_scale"])
        require(0.005 <= target <= 0.25, "SCALE_RANGE")
        backup_row = backup(run)
        for actor in candles:
            # UE 5.8 accepts set_actor_scale3d without dirtying an attached
            # child actor. modify() is required so the level-only save can
            # persist and verify this transform change.
            actor.modify()
            actor.set_actor_scale3d(unreal.Vector(target, target, target))
            # BP_Effect_ChandelierCandle exposes SpriteScale as the authored
            # Niagara-size control. The Niagara graph uses no-scale owner
            # matrices, so transform scale alone does not shrink its sprites.
            actor.set_editor_property("sprite_scale", target)
        require(census() == {"content": [], "maps": [WORLD]}, "DIRTY_SCOPE|" + json.dumps(census(), sort_keys=True))
        require(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "SAVE_LEVEL")
        require(census() == {"content": [], "maps": []}, "POST_DIRTY")
    _, after, light_labels_after = find_scope()
    require(light_labels_after == light_labels, "JOB182_LIGHT_DRIFT")
    if mode in ("APPLY", "READBACK"):
        want = float(args["uniform_scale"])
        require(all(max(abs(v - want) for v in row["actor_scale"]) < 0.0001 for row in after), "SCALE_READBACK")
        require(all(abs(row["sprite_scale"] - want) < 0.0001 for row in after), "SPRITE_SCALE_READBACK")
    result = {"ok": True, "mode": mode, "run": run, "before": before, "after": after,
              "job182_lights": light_labels_after, "backup": backup_row, "dirty_after": census()}
    with open(REPORT, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
    unreal.log("JOB185_CHANDELIER_%s_OK|run=%s|candles=44|lights=9|actor_scale=%s|sprite_scale=%.4f|saved=%d|dirty=0+0" %
               (mode, run, after[0]["actor_scale"], after[0]["sprite_scale"], 1 if mode == "APPLY" else 0))


main()
