"""Independent read-only Job 198 verification of the installed S6 warp."""
import importlib.util
import json
import os
import sys

import unreal


HERE = os.path.dirname(os.path.abspath(__file__))
RUN = "J198-WARP-READBACK-A1"
SOURCE = os.path.join(HERE, "records", "job190_J190-J198-WARP-A2_apply.json")
RESULT = os.path.join(HERE, "job198_warp_readback_result.json")


def write(value):
    with open(RESULT, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)


for name in ("job190_s6_warp_pp", "job190_core"):
    sys.modules.pop(name, None)
spec = importlib.util.spec_from_file_location(
    "job190_s6_warp_pp", os.path.join(HERE, "job190_s6_warp_pp.py"))
tool = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = tool
spec.loader.exec_module(tool)

source = tool.read_json(SOURCE)
if source.get("status") != "APPLIED_AND_READ_BACK":
    raise RuntimeError("JOB198_READBACK_SOURCE_NOT_APPLIED")
if source.get("args", {}).get("move_in") != "off":
    raise RuntimeError("JOB198_READBACK_SOURCE_NOT_WARP_ONLY")

ctx = tool.find_context(RUN)
snap = tool.snapshot(ctx)
track = tool.verify_score_track(ctx["s6"], source["plan"])
errors = []
if not tool.material_state_valid(snap["assets"]):
    errors.append("material fingerprint")
if snap["volume"].get("actor_count") != 1 or snap["volume"].get("binding_count") != 1:
    errors.append("volume or binding count")
if snap["camera_channels"] != source["before"]["camera_channels"]:
    errors.append("Master camera changed despite move_in off")
if snap["route"]["first_camera_transform"]["channels"] != source["before"]["route"]["first_camera_transform"]["channels"]:
    errors.append("nested camera changed")
if snap["dirty"] != {"content": [], "maps": []}:
    errors.append("dirty census")

result = {
    "schema": 1,
    "run": RUN,
    "source": SOURCE,
    "status": "passed" if not errors else "failed",
    "errors": errors,
    "move_in": source["args"]["move_in"],
    "named_saves": source["save_packages"],
    "score_key_count": sum(len(value) for value in source["plan"]["score_keys"].values()),
    "score_track": track,
    "volume": snap["volume"],
    "assets": snap["assets"],
    "p06_end": snap["p06_end"],
    "nested_first_camera": snap["route"]["first_camera_transform"],
    "predicted_seam": tool.transform_delta(
        snap["p06_end"]["transform"], snap["route"]["first_camera_transform"]["pose"]),
    "dirty": snap["dirty"],
}
write(result)
if errors:
    raise RuntimeError("JOB198_WARP_READBACK_FAILED|%r" % errors)
unreal.log(
    "JOB198_WARP_READBACK_OK|run=%s|move_in=off|score_keys=%d|volume=1|binding=1|"
    "master_camera=unchanged|nested_camera=unchanged|dirty_maps=0|dirty_content=0|result=%s"
    % (RUN, result["score_key_count"], RESULT)
)
