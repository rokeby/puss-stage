"""Job 183: deterministic DRY/APPLY/read-back trim of P02's level-owned haze and beams."""
import hashlib
import json
import os
import unreal

ROOT = "E:/PussStage/Saved/CodexConductor"
ARGS_PATH = ROOT + "/job183_p02_level_trim_args.json"
OUT_PATH = ROOT + "/job183_p02_level_trim_result.json"
ASSET = "/Game/Japanese_Alley/Maps/Japanese_Alley"
PREFIX = ASSET + ".Japanese_Alley:PersistentLevel."
KEEP_SPOTS = {"Spot_shrine", "K_shrine_spot_3", "SpotLight3"}


def scalar(obj, prop):
    return float(obj.get_editor_property(prop))


def census():
    rows = []
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    for actor in actors:
        path = str(actor.get_path_name())
        if not path.startswith(PREFIX):
            continue
        label = str(actor.get_actor_label())
        cls = actor.get_class().get_name()
        loc = actor.get_actor_location()
        if not (-1500.0 <= loc.x <= 30000.0 and 77000.0 <= loc.y <= 83000.0 and -1000.0 <= loc.z <= 5000.0):
            continue
        if cls == "ExponentialHeightFog":
            comps = actor.get_components_by_class(unreal.ExponentialHeightFogComponent)
            if len(comps) != 1:
                raise RuntimeError("FOG_COMPONENT_COUNT|%d" % len(comps))
            component = comps[0]
            rows.append({"kind": "fog", "label": label, "path": path,
                         "fog_density": scalar(component, "fog_density")})
        elif cls in ("SpotLight", "RectLight"):
            comps = actor.get_components_by_class(unreal.LightComponent)
            if len(comps) != 1:
                raise RuntimeError("LIGHT_COMPONENT_COUNT|%s|%d" % (label, len(comps)))
            component = comps[0]
            rows.append({"kind": "spot" if cls == "SpotLight" else "rig",
                         "label": label, "path": path,
                         "intensity": scalar(component, "intensity"),
                         "volumetric_scattering_intensity": scalar(component, "volumetric_scattering_intensity")})
    return sorted(rows, key=lambda row: row["path"])


def planned(before):
    after = []
    for row in before:
        row = dict(row)
        if row["kind"] == "fog":
            row["fog_density"] = round(row["fog_density"] * 0.5, 9)
        elif row["kind"] == "spot":
            row["intensity"] = 20.0 if row["label"] in KEEP_SPOTS else 0.0
            row["volumetric_scattering_intensity"] = 0.0
        elif row["kind"] == "rig":
            row["intensity"] = min(row["intensity"], 35.0)
            row["volumetric_scattering_intensity"] = 0.0
        after.append(row)
    return after


def digest(rows):
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


with open(ARGS_PATH, "r", encoding="utf-8") as handle:
    args = json.load(handle)
mode = str(args.get("mode", "DRY")).upper()
if mode not in ("DRY", "APPLY", "VERIFY"):
    raise RuntimeError("BAD_MODE|%s" % mode)
if unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor():
    raise RuntimeError("PIE_ACTIVE")

before = census()
fog_count = sum(row["kind"] == "fog" for row in before)
spot_count = sum(row["kind"] == "spot" for row in before)
rig_count = sum(row["kind"] == "rig" for row in before)
if (fog_count, spot_count, rig_count) != (1, 12, 11):
    raise RuntimeError("AUTHORITY_COUNT_MISMATCH|fog=%d|spot=%d|rig=%d" % (fog_count, spot_count, rig_count))
prior_dry = None
if mode == "VERIFY":
    with open(OUT_PATH, "r", encoding="utf-8") as handle:
        prior_dry = json.load(handle)
    if prior_dry.get("mode") != "DRY":
        raise RuntimeError("VERIFY_REQUIRES_DRY_RECORD")
    after_plan = prior_dry["planned_after"]
    plan_hash = str(prior_dry["plan_hash"])
else:
    after_plan = planned(before)
    plan_hash = digest(after_plan)

result = {"mode": mode, "asset": ASSET, "authority": "level-owned-not-show-attachments",
          "before": before, "planned_after": after_plan, "plan_hash": plan_hash,
          "counts": {"fog": fog_count, "spots": spot_count, "rig": rig_count},
          "rule": {"haze": "density*0.5", "ordinary_spots": "9 off",
                   "shrine_spots": "3 at intensity 20", "rect_rig": "11 capped at intensity 35",
                   "all_target_volumetric_scattering": 0.0}}

if mode == "APPLY":
    expected = str(args.get("expected_plan_hash", ""))
    if expected != plan_hash:
        raise RuntimeError("PLAN_HASH_MISMATCH|expected=%s|actual=%s" % (expected, plan_hash))
    by_path = {str(actor.get_path_name()): actor for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()}
    for target in after_plan:
        actor = by_path[target["path"]]
        if target["kind"] == "fog":
            component = actor.get_components_by_class(unreal.ExponentialHeightFogComponent)[0]
            component.set_editor_property("fog_density", target["fog_density"])
        else:
            component = actor.get_components_by_class(unreal.LightComponent)[0]
            component.set_editor_property("intensity", target["intensity"])
            component.set_editor_property("volumetric_scattering_intensity", target["volumetric_scattering_intensity"])
        actor.modify()
        component.modify()
    if not unreal.EditorAssetLibrary.save_asset(ASSET, only_if_is_dirty=False):
        raise RuntimeError("SAVE_FAILED|%s" % ASSET)
    readback = census()
    result["readback"] = readback
    result["readback_hash"] = digest(readback)
    if result["readback_hash"] != plan_hash:
        raise RuntimeError("READBACK_MISMATCH|planned=%s|actual=%s" % (plan_hash, result["readback_hash"]))
elif mode == "VERIFY":
    expected = str(args.get("expected_plan_hash", ""))
    if expected != plan_hash:
        raise RuntimeError("PLAN_HASH_MISMATCH|expected=%s|actual=%s" % (expected, plan_hash))
    if len(before) != len(after_plan):
        raise RuntimeError("READBACK_COUNT_MISMATCH")
    mismatches = []
    for actual, target in zip(before, after_plan):
        if actual["path"] != target["path"] or actual["kind"] != target["kind"]:
            mismatches.append({"path": actual["path"], "reason": "identity"})
            continue
        props = ("fog_density",) if actual["kind"] == "fog" else ("intensity", "volumetric_scattering_intensity")
        for prop in props:
            if abs(float(actual[prop]) - float(target[prop])) > 1.0e-6:
                mismatches.append({"path": actual["path"], "property": prop,
                                   "expected": target[prop], "actual": actual[prop]})
    result["readback"] = before
    result["readback_tolerance"] = 1.0e-6
    result["mismatches"] = mismatches
    if mismatches:
        raise RuntimeError("TOLERANT_READBACK_MISMATCH|count=%d" % len(mismatches))
    result["status"] = "saved_readback_verified"

with open(OUT_PATH, "w", encoding="utf-8") as handle:
    json.dump(result, handle, indent=2, sort_keys=True)
unreal.log("JOB183_P02_LEVEL_TRIM_%s_OK|plan_hash=%s|fog=%d|spots=%d|rig=%d|path=%s" %
           (mode, plan_hash, fog_count, spot_count, rig_count, OUT_PATH))
