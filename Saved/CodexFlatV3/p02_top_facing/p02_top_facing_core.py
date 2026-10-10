"""Pure contracts for Job 106: turn only the 23 P02 Top panels around stage UP.

No Unreal import.  The live driver changes only WingPair.Top.FacingPolicy from
AUTO_BY_ROLE to ROTATE180_AROUND_UP.  Image flip and LocalTransform are controls.
"""
import hashlib
import json


MARK = "P02_TOP_FACING"
PASSAGE = "P02"
EXPECTED_TOPS = 23
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
WORLD_PATH = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
MASTER_PATH = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
SHOW_FILE_REL = "Content/InfinityStage/Dev/DA_InfinityStage_V1Show.uasset"
UMAP_FILE_REL = "Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
AUTO = "AUTO_BY_ROLE"
ROTATE = "ROTATE180_AROUND_UP"
SIDE_FIELD = {"L": "Left", "R": "Right", "T": "Top"}
SIDE_PROP = {"L": "left", "R": "right", "T": "top"}
PASSAGES = {PASSAGE: {"guid": "7FF34BBDA744E406C264A7B7E4DD61D9", "actor_prefix": "Passage 02"}}


class PlanError(Exception):
    pass


def require(condition, reason):
    if not condition:
        raise PlanError(reason)


def sha(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def policy_name(value):
    text = str(value).upper()
    compact = "".join(ch for ch in text if ch.isalnum())
    for name in (ROTATE, AUTO, "PRESERVE_ASSET"):
        if "".join(ch for ch in name if ch.isalnum()) in compact:
            return name
    return text


def face_delta(faces):
    require(faces and "front_s_cm" in faces and "back_s_cm" in faces, "ROUTE_FACES_MISSING")
    return float(faces["front_s_cm"]) - float(faces["back_s_cm"])


def face_sign(faces, epsilon=1e-4):
    delta = face_delta(faces)
    require(abs(delta) > epsilon, "FACING_SIGN_AMBIGUOUS %.6f" % delta)
    return 1 if delta > 0.0 else -1


def yaw_is_180(panel, tolerance=1e-3):
    try:
        yaw = float(panel["local_transform"]["rotation"][2])
    except (KeyError, TypeError, ValueError, IndexError):
        return False
    wrapped = ((yaw + 180.0) % 360.0) - 180.0
    return abs(abs(wrapped) - 180.0) <= tolerance


def state_for_hash(measurement):
    """Exact authoring state plus facing signs.  A fresh DRY is required after any P02 cue edit."""
    return {
        "passage": measurement.get("passage"),
        "passage_guid": measurement.get("passage_guid"),
        "materialized_count": measurement.get("materialized_count"),
        "settings": measurement.get("settings"),
        "rows": [
            {
                "cue_guid": row.get("cue_guid"),
                "label": row.get("label"),
                "show_index": row.get("show_index"),
                "has_top": row.get("has_top"),
                "text_sha": row.get("text_sha"),
                "panels": {side: row.get("sides", {}).get(side, {}).get("panel") for side in ("L", "R", "T")},
                "faces": {side: row.get("sides", {}).get(side, {}).get("route_faces_cm") for side in ("L", "R", "T")},
            }
            for row in measurement.get("rows", [])
        ],
    }


def make_dry(measurement, run_id):
    require(measurement.get("passage") == PASSAGE, "PASSAGE_NOT_P02")
    rows = measurement.get("rows", [])
    require(len(rows) == EXPECTED_TOPS, "P02_ROW_COUNT %d != %d" % (len(rows), EXPECTED_TOPS))
    require(measurement.get("materialized_count") == EXPECTED_TOPS,
            "MATERIALIZED_COUNT %s != %d" % (measurement.get("materialized_count"), EXPECTED_TOPS))
    targets = []
    for row in rows:
        require(row.get("has_top") and "T" in row.get("sides", {}), "ROW_HAS_NO_TOP %s" % row.get("label"))
        for side in ("L", "R", "T"):
            require(side in row["sides"], "SIDE_MISSING %s %s" % (row.get("label"), side))
        top = row["sides"]["T"]
        panel = top["panel"]
        require(policy_name(panel.get("facing_policy")) == AUTO,
                "TOP_POLICY_NOT_AUTO %s %s" % (row.get("label"), panel.get("facing_policy")))
        require(panel.get("flip_image_horizontally") is False, "TOP_IMAGE_FLIP_TRUE %s" % row.get("label"))
        require(yaw_is_180(panel), "TOP_LOCAL_YAW_NOT_180 %s %s" %
                (row.get("label"), panel.get("local_transform", {}).get("rotation")))
        lsign = face_sign(row["sides"]["L"].get("route_faces_cm"))
        rsign = face_sign(row["sides"]["R"].get("route_faces_cm"))
        tsign = face_sign(top.get("route_faces_cm"))
        require(lsign == -1 and rsign == -1, "LR_FACING_NOT_CORRIDOR %s L=%d R=%d" % (row.get("label"), lsign, rsign))
        require(tsign == 1, "TOP_ALREADY_MATCHES_LR %s sign=%d" % (row.get("label"), tsign))
        targets.append({
            "key": "%s|T" % row["cue_guid"], "cue_guid": row["cue_guid"], "show_index": row["show_index"],
            "label": row["label"], "before_policy": AUTO, "after_policy": ROTATE,
            "flip_image_horizontally": False,
            "local_transform": panel.get("local_transform"),
            "before_faces": top["route_faces_cm"], "before_sign": tsign,
            "lr_signs": {"L": lsign, "R": rsign}, "expected_after_sign": -1,
        })
    state = state_for_hash(measurement)
    state_hash = sha(state)
    return {"run_id": run_id, "mode": "DRY", "status": "PASS", "passage": PASSAGE,
            "target_count": len(targets), "targets": targets, "state": state, "state_hash": state_hash,
            "hash8": state_hash[:8]}


def confirm_for(mode, dry=None, originals=None):
    mode = str(mode).upper()
    if mode == "DRY":
        return "DRY P02 TOP FACING"
    if mode == "APPLY":
        require(dry is not None, "APPLY_NEEDS_DRY")
        return "APPLY P02 TOP FACING #%s" % dry["hash8"]
    if mode == "REVERT":
        require(originals is not None, "REVERT_NEEDS_ORIGINALS")
        return "REVERT P02 TOP FACING %s" % originals["run_id"]
    raise PlanError("MODE_INVALID %r" % mode)


def validate_args(args, dry=None, originals=None):
    mode = str(args.get("mode") or "").upper()
    require(mode in ("DRY", "APPLY", "REVERT"), "MODE_INVALID %r" % mode)
    require(args.get("passage") == PASSAGE, "PASSAGE_MUST_BE_P02")
    require(args.get("confirm") == confirm_for(mode, dry, originals), "CONFIRM_MISMATCH")
    if mode == "APPLY":
        require(str(args.get("decided_by") or "").strip(), "NOT_DECIDED")
        require(dry.get("status") == "PASS" and dry.get("target_count") == EXPECTED_TOPS, "DRY_NOT_APPROVABLE")
    return mode


def panel_text(tc, cue_text, side="T"):
    return tc.get_field(tc.get_field(cue_text, "WingPair"), SIDE_FIELD[side])


def without_facing(tc, panel):
    return tc.without_fields(panel, ["FacingPolicy"])


def verify_facing_only_texts(tc, before, after, target_indexes):
    bad = []
    if len(before) != len(after):
        return ["CUE_COUNT_CHANGED %d -> %d" % (len(before), len(after))]
    for i, (old, new) in enumerate(zip(before, after)):
        if i not in target_indexes:
            if old != new:
                bad.append("NON_TARGET_CUE_CHANGED index %d" % i)
            continue
        old_wp, new_wp = tc.get_field(old, "WingPair"), tc.get_field(new, "WingPair")
        if tc.without_fields(old_wp, ["Top"]) != tc.without_fields(new_wp, ["Top"]):
            bad.append("TARGET_CUE_CHANGED_OUTSIDE_TOP index %d" % i)
        old_top, new_top = panel_text(tc, old), panel_text(tc, new)
        if without_facing(tc, old_top) != without_facing(tc, new_top):
            bad.append("TOP_CHANGED_OUTSIDE_FACING index %d" % i)
        if policy_name(tc.get_field(old_top, "FacingPolicy")) == policy_name(tc.get_field(new_top, "FacingPolicy")):
            bad.append("TOP_FACING_UNCHANGED index %d" % i)
    return bad


def sign_readback(rows, expected_top_sign):
    probe, bad = [], []
    if len(rows) != EXPECTED_TOPS:
        bad.append("READBACK_ROW_COUNT %d" % len(rows))
    for row in rows:
        signs = {}
        try:
            signs = {s: face_sign(row["sides"][s].get("route_faces_cm")) for s in ("L", "R", "T")}
        except (KeyError, PlanError) as exc:
            bad.append("FACING_READBACK_MISSING %s %s" % (row.get("label"), exc))
            continue
        probe.append({"key": "%s|T" % row["cue_guid"], "label": row["label"], "signs": signs,
                      "top_faces": row["sides"]["T"]["route_faces_cm"], "matches_lr": signs["T"] == signs["L"] == signs["R"]})
        if signs["L"] != -1 or signs["R"] != -1:
            bad.append("LR_SIGN_CHANGED %s %s" % (row["label"], signs))
        if signs["T"] != expected_top_sign:
            bad.append("TOP_SIGN_WRONG %s %d want %d" % (row["label"], signs["T"], expected_top_sign))
    return probe, bad
