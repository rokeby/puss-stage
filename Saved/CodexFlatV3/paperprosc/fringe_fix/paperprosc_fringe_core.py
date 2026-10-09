"""Pure contract for the paper-proscenium new-texture import and MI swap."""
import hashlib
import json
import os

MARK = "PAPERPROSC_FRINGE"
MODES = ("DRY", "IMPORT", "REVERT")
OWNERS = ("PRO_side_L", "PRO_side_R", "PRO_valance_C")
ROWS = {
    "PRO_side_L": {
        "old": "/Game/Scenes/Wings/FlatV3/Realism/Textures/PRO_side_L/T_PaperProsc_Side_L_SkinColor",
        "new": "/Game/Scenes/Wings/FlatV3/Realism/Textures/PRO_side_L/T_PaperProsc_Side_L_SkinColor_FringeFix_v1",
        "mis": (
            "/Game/Scenes/Wings/FlatV3/Realism/Materials/Instances/MI_FlatV3_PRO_side_L_Front",
            "/Game/Scenes/Wings/FlatV3/Realism/Materials/Instances/MI_FlatV3_PRO_side_L_Flap",
        ),
    },
    "PRO_side_R": {
        "old": "/Game/Scenes/Wings/FlatV3/Realism/Textures/PRO_side_R/T_PaperProsc_Side_R_SkinColor",
        "new": "/Game/Scenes/Wings/FlatV3/Realism/Textures/PRO_side_R/T_PaperProsc_Side_R_SkinColor_FringeFix_v1",
        "mis": (
            "/Game/Scenes/Wings/FlatV3/Realism/Materials/Instances/MI_FlatV3_PRO_side_R_Front",
            "/Game/Scenes/Wings/FlatV3/Realism/Materials/Instances/MI_FlatV3_PRO_side_R_Flap",
        ),
    },
    "PRO_valance_C": {
        "old": "/Game/Scenes/Wings/FlatV3/Realism/Textures/PRO_valance_C/T_PaperProsc_Valance_C_SkinColor",
        "new": "/Game/Scenes/Wings/FlatV3/Realism/Textures/PRO_valance_C/T_PaperProsc_Valance_C_SkinColor_FringeFix_v1",
        "mis": (
            "/Game/Scenes/Wings/FlatV3/Realism/Materials/Instances/MI_FlatV3_PRO_valance_C_Front",
            "/Game/Scenes/Wings/FlatV3/Realism/Materials/Instances/MI_FlatV3_PRO_valance_C_Flap",
        ),
    },
}


def sha_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def build_plan(here, manifest):
    by_owner = {row["owner"]: row for row in manifest.get("rows", [])}
    if sorted(by_owner) != sorted(OWNERS):
        raise ValueError("MANIFEST_OWNER_SET")
    rows = []
    for owner in OWNERS:
        contract = ROWS[owner]
        row = by_owner[owner]
        source = os.path.join(here, "textures", os.path.basename(row["output"]))
        if not os.path.isfile(source):
            raise ValueError("PNG_MISSING|" + source)
        if sha_file(source) != row.get("output_sha256"):
            raise ValueError("PNG_HASH|" + owner)
        if tuple(row.get("size_px") or ()) != (2048, 4096):
            raise ValueError("PNG_SIZE|" + owner)
        rows.append({
            "owner": owner,
            "png": source.replace("\\", "/"),
            "png_sha256": row["output_sha256"],
            "old": contract["old"],
            "new": contract["new"],
            "mis": list(contract["mis"]),
        })
    payload = {"rows": rows, "policy": "create three new textures; swap SkinColor on six existing MIs"}
    payload["digest"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    payload["digest8"] = payload["digest"][:8]
    return payload


def validate_args(args, digest8=None):
    mode = str(args.get("mode") or "").upper()
    bad = []
    if mode not in MODES:
        bad.append("MODE")
    if mode in ("IMPORT", "REVERT"):
        expected = "%s PAPERPROSC FRINGE %s" % (mode, digest8)
        if args.get("confirm") != expected:
            bad.append("CONFIRM")
        if not str(args.get("decided_by") or "").strip():
            bad.append("DECIDED_BY")
    return bad


def desired_mi_state(plan, use_new):
    return {
        mi: (row["new"] if use_new else row["old"])
        for row in plan["rows"] for mi in row["mis"]
    }


def state_problems(plan, textures_present, mi_state, use_new):
    problems = []
    expected_textures = {row["new"] for row in plan["rows"]}
    if use_new and set(textures_present) != expected_textures:
        problems.append("NEW_TEXTURE_SET")
    expected_mis = desired_mi_state(plan, use_new)
    if mi_state != expected_mis:
        problems.append("MI_SKINCOLOR_STATE")
    return problems
