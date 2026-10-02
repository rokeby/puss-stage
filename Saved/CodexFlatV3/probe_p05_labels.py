"""Read-only: list P05/P01 cue labels, indices, kinds; no edits."""
import json, collections, unreal
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
show = unreal.EditorAssetLibrary.load_asset(SHOW)
cues = list(show.get_editor_property("cues"))
out = {}
for p in ("P05 Wing ", "P01 Wing ", "P03 Wing ", "P02 Wing "):
    rows = []
    for i, cue in enumerate(cues):
        lab = str(cue.get_editor_property("label"))
        if lab.startswith(p):
            pair = cue.get_editor_property("wing_pair")
            left = pair.get_editor_property("left").get_editor_property("mesh")
            rows.append([i, lab, str(cue.get_editor_property("cue_guid").to_string()),
                         left.get_path_name() if left else None])
    c = collections.Counter(r[1] for r in rows)
    out[p.strip()] = {"count": len(rows), "dupes": {k: [r[0] for r in rows if r[1] == k] for k, v in c.items() if v > 1},
                      "rows": rows}
path = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()) + "CodexFlatV3/probe_p05_labels_out.json"
open(path, "w").write(json.dumps(out, indent=1))
unreal.log("FLATV3_PROBE_LABELS_OK path=" + path + " " + json.dumps({k: (v["count"], list(v["dupes"])) for k, v in out.items()}))
