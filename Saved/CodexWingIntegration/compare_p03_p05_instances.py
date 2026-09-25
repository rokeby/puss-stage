"""Compare Passage 3 and Passage 5 wing material instance parameters.

Passage 5 was rebuilt with Bump Offset disabled (HeightRatio 0.0) as an
art-direction override. Passage 3 still uses HeightRatio 0.004. Bump Offset on a
thin masked panel is a plausible cause of a "glitchy" look that mesh geometry
cannot explain, so this dumps both for comparison.
"""

import json
import os

import unreal

ROOTS = {
    "P03": "/Game/Wings/Passage03_ShrineToForgetting/Materials/Instances",
    "P05": "/Game/Wings/Passage05_BirdToMountain/Materials/Instances",
}

payload = {}
for code, root in ROOTS.items():
    entries = {}
    for package in unreal.EditorAssetLibrary.list_assets(root, recursive=True, include_folder=False):
        instance = unreal.EditorAssetLibrary.load_asset(package)
        if not isinstance(instance, unreal.MaterialInstanceConstant):
            continue
        scalars = {}
        for item in instance.get_editor_property("scalar_parameter_values"):
            info = item.get_editor_property("parameter_info")
            scalars[str(info.get_editor_property("name"))] = round(
                float(item.get_editor_property("parameter_value")), 6
            )
        parent = instance.get_editor_property("parent")
        overrides = instance.get_editor_property("base_property_overrides")
        entries[package.split("/")[-1].split(".")[0]] = {
            "parent": parent.get_path_name() if parent else None,
            "scalars": scalars,
            "blend_mode": str(overrides.get_editor_property("blend_mode")),
            "override_blend_mode": bool(overrides.get_editor_property("override_blend_mode")),
            "two_sided": bool(overrides.get_editor_property("two_sided")),
            "override_two_sided": bool(overrides.get_editor_property("override_two_sided")),
            "opacity_mask_clip_value": round(
                float(overrides.get_editor_property("opacity_mask_clip_value")), 6
            ),
        }
    payload[code] = entries

summary = {}
for code, entries in payload.items():
    heights = sorted({e["scalars"].get("HeightRatio") for e in entries.values()})
    summary[code] = {
        "instances": len(entries),
        "distinct_HeightRatio": heights,
        "distinct_parents": sorted({e["parent"] for e in entries.values()}),
        "distinct_blend_modes": sorted({e["blend_mode"] for e in entries.values()}),
        "distinct_two_sided": sorted({e["two_sided"] for e in entries.values()}),
    }

output = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexWingIntegration",
    "compare_p03_p05_instances.json",
)
with open(output, "w", encoding="utf-8") as handle:
    json.dump({"summary": summary, "detail": payload}, handle, indent=2, sort_keys=True)

unreal.log("P03_P05_INSTANCE_COMPARE|" + json.dumps(summary))
