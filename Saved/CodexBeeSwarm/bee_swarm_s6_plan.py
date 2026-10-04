"""S6 placement PLAN for the bee swarm. READ-ONLY: reads the Show, writes a JSON plan.

It never mutates the Show or the level. The S6 write itself is a Show-authoritative
attachment edit and needs Gary's own yes (creative placement) plus the conductor's
backup/apply route (as fx_candle_s6.py did for the candle).

What it reads (measured when run):
  * the Show's cue labelled ANCHOR_CUE_LABEL ('P06 Wing 055': the candle's anchor,
    per fx_candle_s6_apply_response_20261003_slot.json);
  * the candle Effect attachment labelled 'FX TEST - S6 Candle' on that cue: its
    anchor and RelativeTransform (fx_candle_s6.py placed it at (3390, 0, 110):
    P06 tail 390 cm + half the 60 m S6 depth; 110 cm table height);
  * whether a swarm attachment already exists (label SWARM_LABEL).

What it proposes (INFERRED, for Gary):
  * a Prop attachment on the same cue, same anchor, ActorClass
    /Script/InfinityStage.InfinityStageBeeSwarmActor, label SWARM_LABEL;
  * RelativeTransform = candle location with Z = SWARM_CENTRE_ABOVE_FLOOR_CM (150):
    the default 140 cm half-height then spans 10-290 cm above the floor, the GO1
    lens (~55 cm) sits inside the box, and the target band (+/-63 cm about 150 cm)
    keeps the cloud round the old lady's hands / the candle;
  * no per-instance overrides (a Show attachment re-materialises from class
    defaults; the v3 defaults ARE the tuned S6 values).
Marker: BEE_SWARM_S6_PLAN|run=...|cue=...|candle_rel=...|proposed_rel=...|existing_swarm=...
"""
from __future__ import annotations

import importlib.util
import json
import os

try:
    import unreal  # type: ignore
except ModuleNotFoundError:
    unreal = None


def _load_common():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_bs_common.py")
    spec = importlib.util.spec_from_file_location("_bs_common_s6", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


C = _load_common()
ANCHOR_CUE_LABEL = "P06 Wing 055"
CANDLE_LABEL = "FX TEST - S6 Candle"
SWARM_LABEL = "FX TEST - S6 Bee Swarm"
SWARM_CENTRE_ABOVE_FLOOR_CM = 150.0


def propose(candle_location):
    """Pure: the proposed swarm relative location from the candle's."""
    return [float(candle_location[0]), float(candle_location[1]), SWARM_CENTRE_ABOVE_FLOOR_CM]


def main():
    C.require(unreal is not None, "UNREAL_MODULE_REQUIRED")
    run = C.stamp_now()
    report_path = os.path.join(C.saved_dir(unreal), "bee_swarm_s6_plan.json")
    report = {"ok": False, "run": run}
    try:
        census_before = C.dirty_census(unreal)
        show = unreal.EditorAssetLibrary.load_asset(C.SHOW_PATH)
        C.require(show is not None, "SHOW_MISSING|" + C.SHOW_PATH)
        cues = list(show.get_editor_property("cues"))
        matches = [c for c in cues if str(c.get_editor_property("label")) == ANCHOR_CUE_LABEL]
        C.require(len(matches) == 1, "ANCHOR_CUE_COUNT|%d" % len(matches))
        pair = matches[0].get_editor_property("wing_pair")
        attachments = list(pair.get_editor_property("attachments"))
        candles = [a for a in attachments if str(a.get_editor_property("label")) == CANDLE_LABEL]
        C.require(len(candles) == 1, "CANDLE_ATTACHMENT_COUNT|%d" % len(candles))
        candle = candles[0]
        xf = candle.get_editor_property("relative_transform")
        loc = [float(xf.translation.x), float(xf.translation.y), float(xf.translation.z)]
        existing = [str(a.get_editor_property("label")) for a in attachments
                    if str(a.get_editor_property("label")) == SWARM_LABEL]
        swarm_class = unreal.load_class(None, C.SWARM_ACTOR_CLASS)
        report.update({
            "ok": True,
            "cue": ANCHOR_CUE_LABEL,
            "candle": {"label": CANDLE_LABEL, "anchor": str(candle.get_editor_property("anchor")),
                       "relative_location": loc},
            "proposal": {"label": SWARM_LABEL, "kind": "Prop", "actor_class": C.SWARM_ACTOR_CLASS,
                         "anchor": str(candle.get_editor_property("anchor")),
                         "relative_location": propose(loc), "rotation": [0, 0, 0], "scale": [1, 1, 1]},
            "swarm_class_loaded": swarm_class is not None,
            "existing_swarm_attachments": existing,
            "census_before": census_before,
        })
        C.require(C.dirty_census(unreal) == census_before, "PLAN_DIRTIED_PACKAGES")
        C.write_json(report_path, report)
        unreal.log("BEE_SWARM_S6_PLAN|run=%s|cue=%s|candle_rel=%s|proposed_rel=%s|class_loaded=%s|existing_swarm=%d|report=%s"
                   % (run, ANCHOR_CUE_LABEL, json.dumps(loc), json.dumps(propose(loc)),
                      swarm_class is not None, len(existing), report_path))
    except Exception as error:  # noqa: BLE001
        report["error"] = str(error)
        C.write_json(report_path, report)
        unreal.log_error("BEE_SWARM_S6_PLAN_STOPPED|run=%s|%s" % (run, error))
        raise


if __name__ == "__main__":
    main()
