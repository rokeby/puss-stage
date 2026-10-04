"""Remove the never-saved MI copy left in memory by marble APPLY run 124451 (4 Oct).

Refuses unless the census is exactly that one new package, its .uasset is not on
disk (never saved), and the level is clean. Only then deletes the in-memory copy
and archives the unapplied record so the tool can run again. Read the parameter
names of the source MI on the way (read-only) so the re-run can be checked.
"""
import json
import os

import unreal

COPY = "/Game/InfinityStage/Dev/Materials/MI_S3_Marble_Heavy_Daylight"
COPY_FILE = "E:/PussStage/Content/InfinityStage/Dev/Materials/MI_S3_Marble_Heavy_Daylight.uasset"
RECORD = "E:/PussStage/Saved/CodexConductor/s3_marble_tune_record.json"


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def stop(msg):
    unreal.log_error("S3_MARBLE_CLEANUP_STOPPED|" + msg)
    raise RuntimeError(msg)


if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None:
    stop("PIE_ACTIVE")
if census() != {"content": [COPY], "maps": []}:
    stop("UNEXPECTED_CENSUS|" + json.dumps(census()))
if os.path.exists(COPY_FILE):
    stop("COPY_ON_DISK")
record = json.load(open(RECORD, encoding="utf-8"))
if record.get("applied") or record.get("run") not in ("124451", 124451):
    stop("RECORD_STATE|run=%s|applied=%s" % (record.get("run"), record.get("applied")))
source = unreal.EditorAssetLibrary.load_asset(record["plan"]["source"])
names = [str(n) for n in unreal.MaterialEditingLibrary.get_scalar_parameter_names(source)]
if not unreal.EditorAssetLibrary.delete_asset(COPY):
    stop("DELETE_FAILED")
if census() != {"content": [], "maps": []}:
    stop("POST_DELETE_DIRTY|" + json.dumps(census()))
os.replace(RECORD, RECORD + ".failed-124451")
unreal.log("S3_MARBLE_CLEANUP_OK|copy_removed=1|census_clean=1|record_archived=1|source_scalars=%s"
           % ",".join(sorted(names)))
