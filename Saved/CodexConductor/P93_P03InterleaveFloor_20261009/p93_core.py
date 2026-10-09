"""Pure planning and validation for Codex job 93.  No Unreal import."""
import hashlib
import json


MARK = "P93_P03"
OLD_LABELS = ("P03 Wing 001", "P03 Wing 003", "P03 Wing 002")
OLD_GUIDS = (
    "B8AE7B1FDF410C9B9F2A83BDA94DA489",
    "0ED8CD9770436E3F130C8D85C3637BE2",
    "C82F2CC5BD4EF34E9C3BDFACB10C35CB",
)
OLD_MESH_ROOT = "/Game/Scenes/Wings/Passage03_ShrineToForgetting/StaticMeshes/SM_P03_"
TARGET_ORDINALS = (1, 8, 15)  # one-based; six newer rows between each old square pair
P03_LABEL = "Passage 3"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
WORLD_PATH = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_FILE_REL = "Content/InfinityStage/Dev/DA_InfinityStage_V1Show.uasset"
WORLD_FILE_REL = "Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
FLOOR_LABEL = "Passage 03 - Floor"
FLOOR_TARGET = "/Game/InfinityStage/RigAtmos/MI_Floor_DarkWet"
FLOOR_OLD_EXPECTED_TOKEN = "M_Walnut_Hrrngbn_02_Mat_Inst_Dup"


class GateError(Exception):
    pass


def require(condition, reason):
    if not condition:
        raise GateError(reason)


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(value):
    if not isinstance(value, str):
        value = canonical_json(value)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_guid(value):
    return str(value).replace("-", "").replace("{", "").replace("}", "").upper()


def enum_name(value):
    """UE 5.8 str(enum) may be '<InfinityCueType.WING_PAIR: 0>' or 'E.V'."""
    text = str(value).strip().strip("<>")
    text = text.split(":", 1)[0]
    return text.rsplit(".", 1)[-1].upper()


def build_relayout(rows):
    """Return a deterministic 21-row plan. Row dictionaries are plain live census records."""
    require(len(rows) == 21, "P03_CUE_COUNT expected=21 got=%d" % len(rows))
    guids = [normalize_guid(r["cue_guid"]) for r in rows]
    require(len(set(guids)) == len(guids), "DUPLICATE_CUE_GUID")
    require(all(enum_name(r["type"]) == "WING_PAIR" for r in rows), "NON_WINGPAIR_IN_P03")
    require(all(bool(r["enabled"]) for r in rows), "DISABLED_P03_ROW")

    old = []
    newer = []
    refusals = []
    for row in rows:
        both_old = all(str(row.get(side + "_mesh") or "").startswith(OLD_MESH_ROOT) for side in ("L", "R"))
        if row["label"] in OLD_LABELS or normalize_guid(row["cue_guid"]) in OLD_GUIDS or both_old:
            old.append(row)
            if not both_old:
                refusals.append("OLD_ROW_MESH_DRIFT %s" % row["label"])
        else:
            newer.append(row)
    if tuple(r["label"] for r in old) != OLD_LABELS:
        refusals.append("OLD_ROW_IDENTITY_OR_ORDER got=%s" % [r["label"] for r in old])
    if tuple(normalize_guid(r["cue_guid"]) for r in old) != OLD_GUIDS:
        refusals.append("OLD_ROW_GUID_DRIFT got=%s" % [normalize_guid(r["cue_guid"]) for r in old])
    if len(newer) != 18:
        refusals.append("NEWER_ROW_COUNT expected=18 got=%d" % len(newer))

    proposed = []
    if not refusals:
        chunks = (newer[0:6], newer[6:12], newer[12:18])
        for legacy, chunk in zip(old, chunks):
            proposed.append(legacy)
            proposed.extend(chunk)
    if proposed:
        require([i + 1 for i, r in enumerate(proposed) if r["label"] in OLD_LABELS] == list(TARGET_ORDINALS),
                "TARGET_ORDINAL_INTERNAL_ERROR")
        require(set(normalize_guid(r["cue_guid"]) for r in proposed) == set(guids), "CUE_SET_CHANGED")

    # Slot timing is copied by ordinal, so compiled pass frames and stations do not change.
    slots = [{"interval_ticks": int(r["interval_ticks"]), "gap_cm": float(r["gap_cm"])} for r in rows]
    plan_rows = []
    for i, row in enumerate(proposed):
        plan_rows.append({
            "new_ordinal": i + 1,
            "old_ordinal": guids.index(normalize_guid(row["cue_guid"])) + 1,
            "cue_guid": normalize_guid(row["cue_guid"]),
            "label": row["label"],
            "L_mesh": row["L_mesh"],
            "R_mesh": row["R_mesh"],
            "interval_ticks": slots[i]["interval_ticks"],
            "gap_cm": slots[i]["gap_cm"],
            "mechanism_sha": row["mechanism_sha"],
            "attachments_sha": row["attachments_sha"],
        })
    plan = {
        "schema": 1,
        "refusals": refusals,
        "count": len(rows),
        "old_square_count": len(old),
        "newer_count": len(newer),
        "target_ordinals": list(TARGET_ORDINALS),
        "before_guids": guids,
        "after_guids": [normalize_guid(r["cue_guid"]) for r in proposed],
        "slot_timing": slots,
        "rows": plan_rows,
    }
    plan["inputs_hash"] = sha({
        "rows": [{k: r[k] for k in ("cue_guid", "label", "type", "enabled", "interval_ticks", "gap_cm",
                                             "L_mesh", "R_mesh", "mechanism_sha", "attachments_sha")}
                 for r in rows],
        "target_ordinals": list(TARGET_ORDINALS),
    })
    plan["confirm_token"] = plan["inputs_hash"][:12].upper()
    return plan


def validate_relayout_readback(rows, plan):
    bad = []
    if len(rows) != 21:
        return ["COUNT %d" % len(rows)]
    if [normalize_guid(r["cue_guid"]) for r in rows] != plan["after_guids"]:
        bad.append("ORDER")
    by = {normalize_guid(r["cue_guid"]): r for r in rows}
    for want in plan["rows"]:
        got = by.get(want["cue_guid"])
        if got is None:
            bad.append("MISSING %s" % want["cue_guid"][:8]); continue
        for key in ("label", "L_mesh", "R_mesh", "mechanism_sha", "attachments_sha"):
            if got[key] != want[key]:
                bad.append("%s %s" % (want["cue_guid"][:8], key))
        slot = plan["slot_timing"][want["new_ordinal"] - 1]
        if int(got["interval_ticks"]) != int(slot["interval_ticks"]):
            bad.append("%s interval" % want["cue_guid"][:8])
        if abs(float(got["gap_cm"]) - float(slot["gap_cm"])) > 1e-4:
            bad.append("%s gap" % want["cue_guid"][:8])
    return bad


def validate_applied_owned(rows, plan):
    """Fields owned by the relayout only: cue order and per-cue slot timing."""
    if len(rows) != 21:
        return ["COUNT %d" % len(rows)]
    bad = []
    if [normalize_guid(r["cue_guid"]) for r in rows] != plan["after_guids"]:
        bad.append("ORDER")
    for got, want in zip(rows, plan["rows"]):
        if int(got["interval_ticks"]) != int(want["interval_ticks"]):
            bad.append("%s interval" % want["cue_guid"][:8])
        if abs(float(got["gap_cm"]) - float(want["gap_cm"])) > 1e-4:
            bad.append("%s gap" % want["cue_guid"][:8])
    return bad


def floor_plan(current_material, transform_text, component_path):
    require(current_material is not None, "FLOOR_SLOT0_NULL")
    return {
        "schema": 1,
        "actor_label": FLOOR_LABEL,
        "component_path": component_path,
        "before_material": current_material,
        "target_material": FLOOR_TARGET,
        "transform_sha": sha(transform_text),
        "already_target": current_material.split(".")[0] == FLOOR_TARGET,
        "expected_walnut": FLOOR_OLD_EXPECTED_TOKEN in current_material,
    }


def floor_token(plan):
    return sha(plan)[:12].upper()
