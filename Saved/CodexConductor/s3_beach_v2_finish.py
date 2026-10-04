"""FINISH for S3 beach v2 run 124209 (4 Oct).

The APPLY saved the level with v2 in place, then stopped on POST_SAVE_DIRTY: the
level save left exactly one Megascans MI dirty (engine side effect). This script:
backs up that MI's .uasset, saves only it, requires a clean census, reads the v2
actors and figure feet back from the live level, then commits the pending record.
It refuses on any other dirty package, PIE, or a record that is not the pending one.
"""
import datetime
import json
import os
import shutil

import unreal

BASE = "E:/PussStage/Saved/CodexConductor"
PENDING = BASE + "/s3_beach_place_record.json.v2-pending"
RECORD = BASE + "/s3_beach_place_record.json"
MI = "/Game/EnvironmentPacks/Megascans_2K/Surface/01_Soil_Sand_pjuuz0/01_Soil_Sand_pjuuz0_2K_inst"
MI_FILE = "E:/PussStage/Content/EnvironmentPacks/Megascans_2K/Surface/01_Soil_Sand_pjuuz0/01_Soil_Sand_pjuuz0_2K_inst.uasset"
TAG = "RigAtmos.S3BeachV2"
RUN = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def stop(msg):
    unreal.log_error("S3_BEACH_V2_FINISH_STOPPED|run=%s|%s" % (RUN, msg))
    raise RuntimeError(msg)


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if editor.get_game_world() is not None:
    stop("PIE_ACTIVE")
if not os.path.isfile(PENDING) or os.path.exists(RECORD) and json.load(open(RECORD)).get("version") == 2:
    stop("RECORD_STATE")
record = json.load(open(PENDING, encoding="utf-8"))
if str(record.get("run")) != "124209" or record.get("applied"):
    stop("PENDING_NOT_RUN_124209|run=%s" % record.get("run"))
before = census()
if before != {"content": [MI], "maps": []}:
    stop("UNEXPECTED_DIRTY|census=" + json.dumps(before))
backup_dir = "E:/PussStage/Backups/PreS3BeachMISave-" + RUN
os.makedirs(backup_dir)
shutil.copy2(MI_FILE, backup_dir + "/" + os.path.basename(MI_FILE))
if not unreal.EditorAssetLibrary.save_asset(MI, only_if_is_dirty=True):
    stop("MI_SAVE_FAILED")
after = census()
if after != {"content": [], "maps": []}:
    stop("POST_MI_SAVE_DIRTY|census=" + json.dumps(after))

world = editor.get_editor_world()
actors = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
          if TAG in [str(t) for t in a.tags]]
plan = record["plan"]
spawned = {row["label"] for row in plan["props"]} | {plan["sand"]["label"]}
live = {str(a.get_actor_label()) for a in actors}
if not spawned or live != spawned:
    stop("V2_ACTORS_READBACK|record=%d|live=%d" % (len(spawned), len(live)))
feet = []
for row in record.get("figures", []):
    hit = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
           if str(a.get_path_name()) == row.get("actor_path")]
    if len(hit) != 1:
        stop("FIGURE_MISSING|" + str(row.get("label")))
    z = hit[0].get_actor_location().z
    want = row["before_transform"]["location"][2] + row["raise_cm"]
    if abs(z - want) > 0.5:
        stop("FIGURE_Z_READBACK|%s|live=%.2f|want=%s" % (row.get("label"), z, want))
    feet.append(row.get("label"))

record["spawned"] = [{"label": str(a.get_actor_label()), "object_path": str(a.get_path_name())}
                     for a in actors]
record["applied"] = True
record["finished_by"] = {"run": RUN, "mi_saved": MI, "mi_backup": backup_dir,
                         "reason": "POST_SAVE_DIRTY engine side effect on level save"}
with open(PENDING, "w", encoding="utf-8") as handle:
    json.dump(record, handle, indent=2)
os.replace(PENDING, RECORD)
unreal.log("S3_BEACH_V2_FINISH_OK|run=%s|v2_actors=%d|figures=%d|mi_saved=1|census_clean=1|record_committed=1"
           % (RUN, len(live), len(feet)))
