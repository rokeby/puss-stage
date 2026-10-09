"""P44 per-item dispatcher; all mutation remains in the reviewed owner tools.

Items: F4, F5, I1, I3, I4, I5. Each supports DRY/APPLY/REVERT and requires
``<MODE> P44 <ITEM>``. The called owner tool performs its own clean-editor,
backup, transaction-record, named-save, read-back, and drift guards.
"""
import importlib.util
import json
import os
import runpy

try:
    import unreal
except ModuleNotFoundError:  # offline harness
    unreal = None


ITEMS = ("F4", "F5", "I1", "I3", "I4", "I5")
MODES = ("DRY", "APPLY", "REVERT")


class ActionError(RuntimeError):
    pass


def normalize_action(raw):
    item = str(raw.get("item") or "").upper()
    mode = str(raw.get("mode") or "").upper()
    run_id = str(raw.get("run_id") or "").strip()
    if item not in ITEMS:
        raise ActionError("ITEM|%r" % item)
    if mode not in MODES:
        raise ActionError("MODE|%r" % mode)
    expected = "%s P44 %s" % (mode, item)
    if str(raw.get("confirm") or "") != expected:
        raise ActionError("CONFIRM_MISMATCH|want=%r" % expected)
    if not run_id or run_id.endswith("SET-UNIQUE-ID") or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in run_id):
        raise ActionError("RUN_ID_REQUIRED")
    return {"item": item, "mode": mode, "confirm": expected, "run_id": run_id}


def dispatch_spec(action, root):
    """Pure dispatch description used by the offline +/- harness."""
    item, mode = action["item"], action["mode"]
    if item == "F4":
        return {"owner": os.path.join(root, "KlaraIngest", "vis_fix.py"),
                "owner_confirm": "%s VISFIX" % mode, "tag": "S1"}
    if item == "F5":
        return {"owner": os.path.join(root, "S1RigFade_20261009", "s1_rig_fade.py"),
                "owner_confirm": "%s S1RIGFADE" % mode}
    return {"owner": os.path.join(root, "interaction_shadow_transition.py"),
            "owner_confirm": "%s %s" % (mode, item), "interaction": int(item[1:])}


def _load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _run_f4(action, root):
    raw = _load_json(os.path.join(root, "KlaraIngest", "vis_fix_args_S1.json"))
    raw.update({"mode": action["mode"], "confirm": "%s VISFIX" % action["mode"], "run": action["run_id"]})
    runpy.run_path(os.path.join(root, "KlaraIngest", "vis_fix.py"), run_name="__p44_f4__",
                   init_globals={"VIS_FIX_ARGS": raw})


def _run_f5(action, root):
    folder = os.path.join(root, "S1RigFade_20261009")
    raw = _load_json(os.path.join(folder, "s1_rig_fade_args.json"))
    raw.update({"mode": action["mode"], "confirm": "%s S1RIGFADE" % action["mode"],
                "run_id": action["run_id"]})
    path = os.path.join(folder, "s1_rig_fade.py")
    spec = importlib.util.spec_from_file_location("p44_s1_rig_fade_fresh", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main(raw)


def _run_interaction(action, root):
    args = _load_json(os.path.join(root, "interaction_shadow_transition_args.json"))
    params = dict(args["interactions"][action["item"]])
    params["reference_interaction"] = int(args["reference_interaction"])
    path = os.path.join(root, "interaction_shadow_transition.py")
    runpy.run_path(path, run_name="__p44_%s__" % action["item"].lower(), init_globals={
        "IST_INTERACTION": int(action["item"][1:]), "IST_MODE": action["mode"],
        "IST_CONFIRM": "%s %s" % (action["mode"], action["item"]),
        "IST_PARAMS": params, "IST_RUN_ID": action["run_id"]})


def run(raw):
    if unreal is None:
        raise ActionError("UNREAL_REQUIRED")
    action = normalize_action(raw)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec = dispatch_spec(action, root)
    if not os.path.isfile(spec["owner"]):
        raise ActionError("OWNER_TOOL_MISSING|%s" % spec["owner"])
    unreal.log("P44_DISPATCH|run=%s|item=%s|mode=%s|owner=%s" %
               (action["run_id"], action["item"], action["mode"], spec["owner"]))
    if action["item"] == "F4":
        _run_f4(action, root)
    elif action["item"] == "F5":
        _run_f5(action, root)
    else:
        _run_interaction(action, root)


if unreal is not None:
    run(dict(globals().get("P44_ACTION_ARGS") or {}))
