"""Remove the Chaos curtain development preview ("CurtainChaos Preview", BP_CurtainChaos at x=5400) from the level.

Approved 29 Sep by the conductor under Gary's delegation (reversible, backed up, not creative: a dev leftover wired to
nothing, hanging behind the wings and simulating ~15k cloth vertices every frame). Guarded one-shot:
- expected world, no PIE, NOTHING dirty (so the level save cannot carry anyone else's changes);
- exactly one actor labelled "CurtainChaos Preview", class BP_CurtainChaos_C, at x ~ 5400;
- copies the level .umap to Backups/PreRemovePreview-<ts>/ BEFORE any change (the revert);
- destroys it, saves ONLY the level, reads back: gone, exactly one actor fewer, nothing dirty.
"""
import datetime
import json
import os
import shutil

import unreal

LABEL = "CurtainChaos Preview"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
UMAP = os.path.join(PROJECT, "Content", "InfinityStage", "Dev", "Maps", "L_InfinityStage_V1VerticalSlice.umap")
LOG = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods", "remove_curtain_preview.json")
report = {"ok": False}


def finish(msg):
    report["message"] = msg
    with open(LOG, "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1, default=str)
    unreal.log(("PUSS_SOFTGOODS_PREVIEW_REMOVED|" if report["ok"] else "PUSS_SOFTGOODS_PREVIEW_REFUSED|") + msg)


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
ss = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
dirty = sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + \
    sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
if world.get_outermost().get_name() != EXPECTED_WORLD or editor.get_game_world() is not None:
    finish(f"unsafe editor state: world={world.get_outermost().get_name()} pie={editor.get_game_world()}")
elif dirty:
    finish(f"refusing: dirty packages {dirty}")
else:
    actors = ss.get_all_level_actors()
    hits = [a for a in actors if a.get_actor_label() == LABEL]
    if len(hits) != 1 or hits[0].get_class().get_name() != "BP_CurtainChaos_C" or abs(hits[0].get_actor_location().x - 5400) > 50:
        finish(f"refusing: expected one BP_CurtainChaos_C '{LABEL}' at x~5400, found "
               f"{[(a.get_class().get_name(), a.get_actor_location().x) for a in hits]}")
    else:
        a = hits[0]
        loc, rot = a.get_actor_location(), a.get_actor_rotation()
        report["removed"] = {"label": LABEL, "class": a.get_class().get_path_name(), "location": [loc.x, loc.y, loc.z],
                             "rotation": [rot.roll, rot.pitch, rot.yaw]}
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_dir = os.path.join(PROJECT, "Backups", f"PreRemovePreview-{ts}")
        os.makedirs(backup_dir, exist_ok=True)
        shutil.copy2(UMAP, backup_dir)
        report["backup"] = os.path.join(backup_dir, os.path.basename(UMAP))
        n_before = len(actors)
        ss.destroy_actor(a)
        saved = unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD)
        after = ss.get_all_level_actors()
        dirty_after = sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + \
            sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
        report.update({"saved": saved, "actors_before": n_before, "actors_after": len(after),
                       "still_present": any(x.get_actor_label() == LABEL for x in after), "dirty_after": dirty_after})
        report["ok"] = bool(saved) and not report["still_present"] and len(after) == n_before - 1 and not dirty_after
        finish(f"saved={saved}|actors {n_before}->{len(after)}|dirty_after={dirty_after}|backup={report['backup']}")
