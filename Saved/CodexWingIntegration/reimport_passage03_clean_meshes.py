"""Force-reimport the 18 Passage 3 static meshes from the clean rebuild.

wing_integration_common.import_mesh_tasks only imports assets that do not yet
exist (replace_existing=False), so running the normal Passage 3 import over an
already-populated content root re-runs the material wiring but leaves the old
geometry in place. This replaces the mesh geometry explicitly, then hands back to
the shared module to redo texture settings, material instances and slot
assignments.

Source: DerivedAssets/GeneratedWingsV2_Passage03_Clean
Target: /Game/Wings/Passage03_ShrineToForgetting/StaticMeshes
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
CLEAN_SOURCE = wing_integration_common.PROJECT_ROOT / "DerivedAssets/GeneratedWingsV2_Passage03_Clean"
if not CLEAN_SOURCE.is_dir():
    raise RuntimeError(f"Clean source root missing: {CLEAN_SOURCE}")
config["source_root"] = CLEAN_SOURCE

wing_integration_common.validate_editor_state(require_clean=True)
wing_integration_common.validate_pipeline_report(config)

mesh_root = f"{config['content_root']}/StaticMeshes"
asset_tools = unreal.AssetToolsHelpers.get_asset_tools()


def source_of(package):
    """Absolute source file currently recorded on a Static Mesh, or ''."""
    mesh = unreal.load_asset(package)
    data = mesh.get_editor_property("asset_import_data")
    try:
        return str(data.get_first_filename())
    except Exception:
        return ""


records = []
for start in range(0, len(config["assets"]), 6):
    batch = config["assets"][start : start + 6]
    tasks = []
    options = wing_integration_common.make_fbx_options()
    for asset_name in batch:
        fbx = CLEAN_SOURCE / asset_name / f"SM_{asset_name}.fbx"
        if not fbx.is_file():
            raise RuntimeError(f"Missing clean FBX: {fbx}")
        package = f"{mesh_root}/SM_{asset_name}"
        records.append({
            "asset": asset_name,
            "source_before": source_of(package),
            "expected_source": str(fbx),
        })
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", str(fbx))
        task.set_editor_property("destination_path", mesh_root)
        task.set_editor_property("destination_name", f"SM_{asset_name}")
        task.set_editor_property("automated", True)
        task.set_editor_property("replace_existing", True)
        task.set_editor_property("replace_existing_settings", True)
        task.set_editor_property("save", True)
        task.set_editor_property("options", options)
        tasks.append(task)
    asset_tools.import_asset_tasks(tasks)
    unreal.log(f"P03_CLEAN_REIMPORT_PROGRESS|meshes={len(tasks)}")
    del tasks

unreal.EditorAssetLibrary.save_directory(mesh_root, only_if_is_dirty=False, recursive=True)

replaced = 0
for record in records:
    package = f"{mesh_root}/SM_{record['asset']}"
    record["source_after"] = source_of(package)
    record["replaced"] = os.path.normpath(record["source_after"]) == os.path.normpath(
        record["expected_source"]
    )
    if record["replaced"]:
        replaced += 1

payload = {
    "status": "ok" if replaced == len(records) else "error",
    "mesh_count": len(records),
    "replaced": replaced,
    "records": records,
}
output = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexWingIntegration",
    "reimport_passage03_clean_meshes.json",
)
with open(output, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)

unreal.log(
    f"P03_CLEAN_MESH_REIMPORT|meshes={len(records)}|replaced={replaced}"
    f"|status={payload['status']}"
)
if replaced != len(records):
    raise RuntimeError(f"Only {replaced}/{len(records)} meshes reimported from the clean batch")
