"""READ-ONLY (5 Oct): why REVERT says REVERT_LIVE_STATE_MISMATCH. Finds the candle's cue by GUID, snapshots there,
diffs against the record's expected. Changes nothing."""
import json
import os
import sys

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
sys.path.insert(0, HERE)
src = open(os.path.join(HERE, "fx_candle_s6.py"), encoding="utf-8").read()
ns = {"__name__": "fx_candle_s6_lib", "__file__": os.path.join(HERE, "fx_candle_s6.py")}
exec(compile(src, "fx_candle_s6.py", "exec"), ns)  # guarded main does not run under this __name__
rec = json.load(open(os.path.join(HERE, "fx_candle_s6_record.json"), encoding="utf-8"))
show = unreal.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
cues = list(show.get_editor_property("cues"))
idx = [i for i, c in enumerate(cues) if str(c.get_editor_property("cue_guid")).replace("-", "").upper()
       == rec["cue_guid"].replace("-", "").upper()]
out = {"record_index": rec["cue_index"], "live_indices": idx}
for i in sorted(set(idx + [int(rec["cue_index"]), 280])):
    try:
        snap = ns["_snapshot"](show, i, [rec["light_guid"], rec["effect_guid"]])
    except Exception as exc:  # noqa: BLE001
        snap = "ERR %s" % exc
    out["snap_%d" % i] = snap
    out["equal_%d" % i] = snap == rec["expected"]
out["expected"] = rec["expected"]
p = os.path.join(HERE, "fx_candle_s6_diag.json")
json.dump(out, open(p, "w", encoding="utf-8"), indent=1, default=str)
unreal.log("FX_CANDLE_DIAG|record_index=%s|live=%s|equal=%s|out=%s" % (rec["cue_index"], idx,
           {k: v for k, v in out.items() if k.startswith("equal_")}, p))
