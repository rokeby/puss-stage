"""READ-ONLY: after the failed REVERT TOPPLE-20261007-080745, compare the in-memory Show with the STILL originals.
Per target row: mechanism text + mask restored? and where the rest of the cue text differs (expected: light edits
made by dead_bulbs_warm after the STILL apply). Writes diag_revert_state.json. Marker TOPPLE_RECOVER_DIAG_OK."""
import json, os, difflib
import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexFlatV3", "topple")
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"

def strip_mech(t):
    i = t.find("Mechanism=(")
    if i < 0:
        return t
    j = i + len("Mechanism=("); depth = 1
    while depth and j < len(t):
        depth += {"(": 1, ")": -1}.get(t[j], 0); j += 1
    return t[:i] + "Mechanism=<>" + t[j:]

orig = json.load(open(os.path.join(HERE, "topple_originals_TOPPLE-20261007-024333.json"), encoding="utf-8"))
cues = list(unreal.EditorAssetLibrary.load_asset(SHOW).get_editor_property("cues"))
gid = lambda c: str(unreal.GuidLibrary.conv_guid_to_string(c.get_editor_property("cue_guid"))).upper()
by = {gid(c): (i, c) for i, c in enumerate(cues)}
rows = []
for r in orig["rows"]:
    i, c = by[r["cue_guid"]]
    pair = c.get_editor_property("wing_pair")
    mech_ok = pair.get_editor_property("mechanism").export_text() == r["mech_text"]
    mask_ok = int(pair.get_editor_property("local_override_mask")) == int(r["mask"])
    a, b = strip_mech(r["cue_text"]), strip_mech(c.export_text())
    diffs = []
    if a != b:
        sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op != "equal":
                diffs.append({"op": op, "orig": a[max(0, i1 - 60):i2 + 20][:240], "live": b[max(0, j1 - 60):j2 + 20][:240]})
    rows.append({"label": r["label"], "index_now": i, "index_orig": r["show_index"], "mech_ok": mech_ok, "mask_ok": mask_ok,
                 "rest_equal": a == b, "n_diffs": len(diffs), "diffs": diffs[:4]})
lib = unreal.EditorLoadingAndSavingUtils
census = {"content": sorted(str(p.get_path_name()) for p in lib.get_dirty_content_packages()),
          "maps": sorted(str(p.get_path_name()) for p in lib.get_dirty_map_packages())}
out = {"rows": rows, "census": census, "n_cues": len(cues)}
json.dump(out, open(os.path.join(HERE, "recover", "diag_revert_state.json"), "w", encoding="utf-8"), indent=1)
unreal.log("TOPPLE_RECOVER_DIAG_OK|mech_ok=%d/%d|mask_ok=%d|rest_equal=%d|census=%s" % (
    sum(r["mech_ok"] for r in rows), len(rows), sum(r["mask_ok"] for r in rows), sum(r["rest_equal"] for r in rows), json.dumps(census)))
