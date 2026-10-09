"""Pure contract for the Klara S2 lacquered-wet Variant B MI creator."""
import hashlib
import json

TOOL = "s2k_variantB_mis"
MARK = "S2KVARB"
CONFIRM = "S2KVARIANTB"
MODES = ("DRY", "APPLY", "REVERT")
SOURCE_MI = "/Game/WetGround/MI_LacqueredPaper_Wet"
EXPECTED_PARENT = "/Game/WetGround/M_LacqueredPaper_Wet"
DEST = "/Game/Scenes/Wings/FlatV3/KlaraS2/Materials"
OWNERS = ("S2K_shrine_L", "S2K_shrine_R", "S2K_ceiling_C")
SKINS = {
    "S2K_shrine_L": "/Game/Scenes/Wings/FlatV3/Realism/Textures/S2K_shrine_L/T_S2K_shrine_L_SkinColor_o2",
    "S2K_shrine_R": "/Game/Scenes/Wings/FlatV3/Realism/Textures/S2K_shrine_R/T_S2K_shrine_R_SkinColor_o2",
    "S2K_ceiling_C": "/Game/Scenes/Wings/FlatV3/Realism/Textures/S2K_ceiling_C/T_S2K_ceiling_C_SkinColor_o2",
}


def rows():
    return [{"owner": owner, "slot": slot, "skin": SKINS[owner],
             "target": "%s/MI_S2K_%s_%s_LacqWet" % (DEST, owner, slot)}
            for owner in OWNERS for slot in ("Front", "Flap")]


def validate_args(args):
    mode = str(args.get("mode") or "").upper()
    out = []
    if mode not in MODES:
        out.append("MODE")
    if mode != "DRY" and args.get("confirm") != "%s %s" % (mode, CONFIRM):
        out.append("CONFIRM")
    if mode != "DRY" and not str(args.get("decided_by") or "").strip():
        out.append("DECIDED_BY")
    return out


def plan_digest(source_parent, source_values):
    payload = {"source": SOURCE_MI, "parent": source_parent, "source_values": source_values, "rows": rows(),
               "overrides": {"PaperMap": "row.skin", "UsePaperMap": True, "UseAlphaCutout": False}}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def state_problems(state, source_values=None):
    expected = {r["target"]: r for r in rows()}
    out = []
    if sorted(state) != sorted(expected):
        out.append("TARGET_SET")
    for path, row in expected.items():
        got = state.get(path) or {}
        if got.get("parent") != EXPECTED_PARENT:
            out.append("PARENT|" + path)
        if got.get("PaperMap") != row["skin"]:
            out.append("PAPERMAP|" + path)
        if got.get("UsePaperMap") is not True or got.get("UseAlphaCutout") is not False:
            out.append("SWITCHES|" + path)
        if source_values is not None:
            want = json.loads(json.dumps(source_values))
            want["texture"]["PaperMap"] = row["skin"]
            want["switch"]["UsePaperMap"] = True
            want["switch"]["UseAlphaCutout"] = False
            if got.get("values") != want:
                out.append("PARAMETERS|" + path)
    return out
