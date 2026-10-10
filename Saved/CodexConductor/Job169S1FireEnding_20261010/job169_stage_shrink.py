"""Job 169 stage C: invoke the proven P24 shrink tool with a Job-169 record."""
import os

import unreal


HERE = os.path.dirname(os.path.abspath(__file__))
LEGACY = os.path.normpath(os.path.join(HERE, "..", "..", "CodexSoftGoods", "shrink_scene_playback.py"))
TAIL = "\nif unreal is not None:\n    main()"


def _load_legacy():
    with open(LEGACY, "r", encoding="utf-8") as handle:
        source = handle.read().rstrip()
    if not source.endswith(TAIL.strip()):
        raise RuntimeError("SHRINK_TOOL_SHAPE_CHANGED")
    source = source[:-len(TAIL.strip())]
    namespace = {"__name__": "job169_shrink_definitions", "__file__": LEGACY}
    exec(compile(source, LEGACY, "exec"), namespace)
    namespace["RECORD_NAME"] = "job169_s1_shrink_record.json"
    namespace["MARK"] = "JOB169_S1_SHRINK"
    return namespace


def run(args):
    namespace = _load_legacy()
    mode = str(args["mode"]).upper()
    shrink_args = {"mode": mode, "confirm": "%s SHRINK" % mode, "run_id": args["run_id"],
                   "cue_label": args["cue_label"], "new_end_frame": int(args["new_end_frame"])}
    problems = namespace["validate_args"](shrink_args)
    if problems:
        raise RuntimeError("SHRINK_ARGS|%s" % problems)
    result = {"DRY": namespace["run_dry"], "APPLY": namespace["run_apply"],
              "REVERT": namespace["run_revert"]}[mode](args["run_id"], shrink_args)
    unreal.log("JOB169_SHRINK_%s_OK|run=%s|cue=%s|end=%d|late_inventory=%s" %
               (mode, args["run_id"], args["cue_label"], args["new_end_frame"],
                result.get("report_path", "see-report")))
    return result
