"""Read-only P02 Show attachment census for Job 181 trim diagnosis."""
import importlib.util
import json
import os

import unreal


ROOT = "E:/PussStage/Saved/CodexFlatV3/p02lighting"
path = os.path.join(ROOT, "p02_trim.py")
spec = importlib.util.spec_from_file_location("job181_p02_trim_probe_module", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
show = unreal.EditorAssetLibrary.load_asset(module.C.SHOW_PATH)
rows, passage_guid = module.p02_rows(show)
flat = []
for ordinal, cue in enumerate(rows, 1):
    for attachment in cue["attachments"]:
        flat.append({
            "ordinal": ordinal,
            "guid": attachment["guid"],
            "label": attachment["label"],
            "kind": attachment["kind"],
            "enabled": attachment["enabled"],
            "effect": attachment["effect"],
            "lighting": attachment["lighting"],
        })
out = {
    "passage_guid": passage_guid,
    "cue_count": len(rows),
    "attachment_count": len(flat),
    "kinds": {},
    "rows": flat,
}
for row in flat:
    key = module.enum_token(row["kind"])
    out["kinds"][key] = out["kinds"].get(key, 0) + 1
dest = "E:/PussStage/Saved/CodexConductor/job181_p02_attachment_probe.json"
with open(dest, "w", encoding="utf-8") as handle:
    json.dump(out, handle, indent=2, sort_keys=True)
unreal.log("JOB181_P02_ATTACHMENT_PROBE_OK|cues=%d|attachments=%d|kinds=%s|out=%s" %
           (len(rows), len(flat), json.dumps(out["kinds"], sort_keys=True), dest))
