"""Q14c-A read-only live diff for the active TOPPLE-20261007-114412 rows.

Loads the Show and inspects every recorded chain-A row.  The recorded APPLY file
contains hashes, so its exact after-state is reconstructed in free-standing
Unreal structs from the recorded originals plus the matching topple plan.  No
asset is modified and nothing is saved.
"""
import datetime
import hashlib
import json
import os
import runpy

import unreal


RUN = datetime.datetime.now().strftime("Q14C-A-%Y%m%d-%H%M%S")
EXPECTED_APPLY = "TOPPLE-20261007-114412"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"


def fail(reason):
    unreal.log_error("Q14C_FIELD_DIFF_STOPPED|run=%s|reason=%s" % (RUN, reason))
    raise RuntimeError(reason)


def read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def guid_text(value):
    return str(unreal.GuidLibrary.conv_guid_to_string(value)).replace("-", "").upper()


def curve_prop(side):
    return {"L": "left_normalized_curve", "R": "right_normalized_curve", "T": "top_normalized_curve"}[side]


def import_curve(text, label):
    curve = unreal.RuntimeFloatCurve()
    if not curve.import_text(text):
        fail("CURVE_IMPORT_FALSE %s" % label)
    return curve


def reconstruct_after(original_text, plan_row):
    mech = unreal.InfinityMechanismMotion()
    if not mech.import_text(original_text) or mech.export_text() != original_text:
        fail("ORIGINAL_MECH_IMPORT_MISMATCH %s" % plan_row["label"])
    setting = plan_row["set"]
    mech.set_editor_property(
        "playback_mode", getattr(unreal.InfinityMotionPlaybackMode, setting["playback_mode"])
    )
    mech.set_editor_property("phase_offset_cycles", float(setting["phase_offset_cycles"]))
    if plan_row["action"] == "chain":
        mech.set_editor_property("kind", getattr(unreal.InfinityMechanismKind, setting["kind"]))
        mech.set_editor_property(
            "phase_origin", getattr(unreal.InfinityMotionPhaseOrigin, setting["phase_origin"])
        )
        mech.set_editor_property("cycle_rate_hz", float(setting["cycle_rate_hz"]))
        mech.set_editor_property("max_angle_deg", float(setting["max_angle_deg"]))
        mech.set_editor_property(
            curve_prop(plan_row["side"]), import_curve(plan_row["curve_text"], plan_row["label"])
        )
        mech.set_editor_property(
            curve_prop(plan_row["other_side"]),
            import_curve(plan_row["other_curve_text"], plan_row["label"]),
        )
        if setting.get("top_follows_mechanism") is False:
            mech.set_editor_property("top_follows_mechanism", False)
    return mech.export_text()


def field_map(core, text):
    return {name: value for name, value in core["fields"](text)}


def main():
    saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
    top = os.path.join(saved, "CodexFlatV3", "topple")
    here = os.path.join(saved, "CodexFlatV3", "q14")
    core = runpy.run_path(os.path.join(top, "topple_core.py"))

    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        fail("PIE_OR_SIE_ACTIVE")
    world = editor.get_editor_world()
    world_name = str(world.get_outermost().get_name()) if world else None
    if world_name != EXPECTED_WORLD:
        fail("WRONG_WORLD %s" % world_name)

    lib = unreal.EditorLoadingAndSavingUtils
    package_name = lambda p: str(p.get_path_name()).split(".", 1)[0]
    census_before = {
        "content": sorted(package_name(p) for p in lib.get_dirty_content_packages()),
        "maps": sorted(package_name(p) for p in lib.get_dirty_map_packages()),
        "pie": False,
    }

    originals_path = os.path.join(top, "topple_originals_%s.json" % EXPECTED_APPLY)
    apply_path = os.path.join(top, "topple_apply_%s.json" % EXPECTED_APPLY)
    plan_path = os.path.join(top, "topple_plan.json")
    originals = read_json(originals_path)
    applied = read_json(apply_path)
    plan = read_json(plan_path)
    if originals.get("run_id") != EXPECTED_APPLY:
        fail("ORIGINALS_RUN_MISMATCH")
    if originals.get("plan_inputs_hash") != plan.get("inputs_hash"):
        fail("PLAN_INPUTS_HASH_MISMATCH")

    plan_rows = [row for row in plan.get("still", []) if row.get("action") == "still"]
    plan_rows += list((plan.get("chain") or {"rows": []})["rows"])
    plan_by_guid = {row["cue_guid"]: row for row in plan_rows}
    original_by_guid = {row["cue_guid"]: row for row in originals["rows"]}
    if set(plan_by_guid) != set(original_by_guid):
        fail("PLAN_ORIGINAL_GUID_SET_MISMATCH")

    show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
    if show is None:
        fail("SHOW_LOAD_FAIL")
    live_by_guid = {}
    for cue in show.get_editor_property("cues"):
        guid = guid_text(cue.get_editor_property("cue_guid"))
        if guid in original_by_guid:
            if guid in live_by_guid:
                fail("CUE_GUID_NOT_UNIQUE %s" % guid)
            live_by_guid[guid] = cue
    if set(live_by_guid) != set(original_by_guid):
        fail("TARGET_CUE_SET_MISMATCH missing=%s" % sorted(set(original_by_guid) - set(live_by_guid)))

    rows = []
    changed_fields = []
    mask_drift_rows = []
    for original in originals["rows"]:
        guid = original["cue_guid"]
        plan_row = plan_by_guid[guid]
        expected_text = reconstruct_after(original["mech_text"], plan_row)
        expected_hash = sha(expected_text)
        recorded_hash = applied["after_mech_sha"].get(guid)
        if expected_hash != recorded_hash:
            fail("RECONSTRUCTED_AFTER_HASH_MISMATCH %s got=%s recorded=%s" % (
                original["label"], expected_hash, recorded_hash
            ))

        pair = live_by_guid[guid].get_editor_property("wing_pair")
        live_mech = pair.get_editor_property("mechanism")
        live_text = live_mech.export_text()
        expected_fields = field_map(core, expected_text)
        live_fields = field_map(core, live_text)
        names = list(expected_fields)
        names += [name for name in live_fields if name not in expected_fields]
        diffs = []
        for name in names:
            old = expected_fields.get(name)
            new = live_fields.get(name)
            if old != new:
                item = {"field": name, "old_apply_after": old, "new_live": new}
                diffs.append(item)
                changed_fields.append({"cue_guid": guid, "label": original["label"], **item})

        live_mask = int(pair.get_editor_property("local_override_mask"))
        expected_mask = applied.get("after_mask", {}).get(guid)
        if expected_mask is None:
            expected_mask = int(original["mask"]) | (
                int(originals.get("override_bits") or 0) if original["action"] == "chain" else 0
            )
        if live_mask != int(expected_mask):
            mask_drift_rows.append({
                "cue_guid": guid,
                "label": original["label"],
                "old_apply_after": int(expected_mask),
                "new_live": live_mask,
            })
        rows.append({
            "cue_guid": guid,
            "label": original["label"],
            "action": original["action"],
            "mechanism_matches_apply_after": live_text == expected_text,
            "local_override_mask": {
                "old_apply_after": int(expected_mask),
                "new_live": live_mask,
                "changed": live_mask != int(expected_mask),
            },
            "field_diffs": diffs,
            "expected_after_fields": expected_fields,
            "live_fields": live_fields,
        })

    census_after = {
        "content": sorted(package_name(p) for p in lib.get_dirty_content_packages()),
        "maps": sorted(package_name(p) for p in lib.get_dirty_map_packages()),
        "pie": editor.get_game_world() is not None,
    }
    if census_after != census_before:
        fail("PROBE_CHANGED_CENSUS before=%s after=%s" % (census_before, census_after))

    result = {
        "run_id": RUN,
        "tier": "measured",
        "mode": "READ_ONLY",
        "source_apply_run": EXPECTED_APPLY,
        "world": world_name,
        "census_before": census_before,
        "census_after": census_after,
        "rows_checked": len(rows),
        "mechanism_drift_rows": sum(1 for row in rows if row["field_diffs"]),
        "mask_drift_rows": len(mask_drift_rows),
        "changed_fields": changed_fields,
        "mask_drifts": mask_drift_rows,
        "rows": rows,
    }
    out_path = os.path.join(here, "q14c_field_diff_%s.json" % RUN)
    with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=2, sort_keys=False)
        handle.write("\n")
    unreal.log(
        "Q14C_FIELD_DIFF_OK|run=%s|rows=%d|mechanism_drift_rows=%d|changed_fields=%d|mask_drift_rows=%d|output=%s"
        % (RUN, len(rows), result["mechanism_drift_rows"], len(changed_fields), len(mask_drift_rows), out_path)
    )


main()
