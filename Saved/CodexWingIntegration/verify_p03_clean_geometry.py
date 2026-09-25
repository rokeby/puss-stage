"""Confirm the imported Passage 3 static meshes match the clean rebuild.

Compares each Static Mesh's LOD0 triangle count against the triangle count
recorded by the pipeline for the clean batch, and reports any horizontal image
flips left enabled on the Passage 3 cue rows. Writes verify_p03_clean_geometry.json.
"""

import importlib
import json
import os
from pathlib import Path
import sys

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wing_integration_common

importlib.reload(wing_integration_common)

config = wing_integration_common.config_for(3)
mesh_root = f"{config['content_root']}/StaticMeshes"
clean_root = wing_integration_common.PROJECT_ROOT / "DerivedAssets/GeneratedWingsV2_Passage03_Clean"

report = json.loads((clean_root / "wing_pipeline_report.json").read_text(encoding="utf-8"))
expected = {
    item["asset_name"]: item["mesh_cleanup"]["triangles"]
    for item in report["results"]
}

rows = []
mismatched = 0
for asset_name in config["assets"]:
    mesh = wing_integration_common.load_asset(
        f"{mesh_root}/SM_{asset_name}", unreal.StaticMesh
    )
    tris = int(mesh.get_num_triangles(0))
    verts = int(mesh.get_num_vertices(0))
    want = expected[asset_name]
    ok = tris == want
    if not ok:
        mismatched += 1
    rows.append({
        "asset": asset_name,
        "triangles_in_unreal": tris,
        "triangles_expected": want,
        "vertices_in_unreal": verts,
        "match": ok,
    })

show = wing_integration_common.load_asset(wing_integration_common.SHOW_PATH)
cues = list(show.get_editor_property("cues"))
flips = []
for index, cue in enumerate(cues):
    label = str(cue.get_editor_property("label"))
    if not label.startswith(config["label_prefix"]):
        continue
    pair = cue.get_editor_property("wing_pair")
    for role in ("left", "right", "top"):
        panel = pair.get_editor_property(role)
        if bool(panel.get_editor_property("flip_image_horizontally")):
            flips.append({"cue_index": index, "label": label, "role": role})

payload = {
    "status": "ok" if not mismatched and not flips else "error",
    "mesh_count": len(rows),
    "triangle_mismatches": mismatched,
    "image_flips_enabled": len(flips),
    "flips": flips,
    "meshes": rows,
}
output = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexWingIntegration",
    "verify_p03_clean_geometry.json",
)
with open(output, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)

unreal.log(
    "P03_CLEAN_GEOMETRY_VERIFY"
    f"|meshes={len(rows)}|triangle_mismatches={mismatched}|flips={len(flips)}"
    f"|status={payload['status']}"
)
