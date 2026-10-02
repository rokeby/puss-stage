"""Pre-cleanup Flat V3 importer failure boundary, retained as a negative control."""
import unreal


def run(planted_import):
    final_status = "FAIL"
    try:
        planted_import()
    except Exception as exc:
        unreal.log_error("FLATV3_P02_IMPORT_FAIL run=OLD reason=%s" % exc)
        raise
    finally:
        unreal.log("FLATV3_SLOT_RELEASED run=OLD status=%s" % final_status)
