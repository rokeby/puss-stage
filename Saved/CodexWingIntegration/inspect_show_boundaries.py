import json
import os

import unreal


SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"


def value_text(value):
    return str(value).replace("{", "").replace("}", "").lower()


show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
if show is None:
    raise RuntimeError("Show Asset did not load")
cues = list(show.get_editor_property("cues"))
passages = list(show.get_editor_property("passage_settings"))
payload = {
    "passages": [
        {
            "ordinal": index + 1,
            "label": str(passage.get_editor_property("label")),
            "guid": value_text(passage.get_editor_property("passage_guid")),
            "first": value_text(passage.get_editor_property("first_cue_guid")),
            "last": value_text(passage.get_editor_property("last_cue_guid")),
        }
        for index, passage in enumerate(passages)
    ],
    "cues": [
        {
            "index": index,
            "label": str(cue.get_editor_property("label")),
            "type": str(cue.get_editor_property("type")),
            "guid": value_text(cue.get_editor_property("cue_guid")),
        }
        for index, cue in enumerate(cues)
    ],
}
output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexWingIntegration",
    "inspect_show_boundaries.json",
)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)
unreal.log(
    f"PUSS_SHOW_BOUNDARY_INSPECT_SUCCESS|passages={len(passages)}|cues={len(cues)}"
)
