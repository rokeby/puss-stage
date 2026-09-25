import json
from pathlib import Path
import subprocess


PROJECT_ROOT = Path("/Users/zhexi-mbp-22/Documents/Unreal Projects/PussStage")
SOURCE_ROOT = (
    PROJECT_ROOT
    / "DerivedAssets/Passage05BirdToMountainBatch/GeneratedWingsV2_Clean"
)
BLENDER = Path("/Applications/Blender v5-2.app/Contents/MacOS/Blender")
VALIDATOR = PROJECT_ROOT / "Tools/WingCutoutPipeline/validate_fbx.py"
OUTPUT = SOURCE_ROOT / "clean_fbx_validation_report.json"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    pipeline = json.loads((SOURCE_ROOT / "wing_pipeline_report.json").read_text())
    results = pipeline.get("results", [])
    require(len(results) == 22, f"Expected 22 pipeline results, found {len(results)}")
    require(all(item.get("status") == "ok" for item in results), "Pipeline contains failures")
    require(
        all(
            item.get("thickness_cm") == 10.0
            and item.get("height_m") == 2.0
            and item.get("final_height_m") == 10.0
            and item.get("ue_panel_scale") == 5.0
            and item.get("ue_yaw_deg") == 90.0
            and item.get("mesh_cleanup", {}).get("triangles_only") is True
            and item.get("mesh_cleanup", {}).get("non_manifold_edges") == 0
            and item.get("mesh_cleanup", {}).get("degenerate_triangles") == 0
            for item in results
        ),
        "Pipeline clean V2 contract failed",
    )

    validations = []
    for item in sorted(results, key=lambda value: value["asset_name"]):
        command = [
            str(BLENDER),
            "--background",
            "--factory-startup",
            "--python",
            str(VALIDATOR),
            "--",
            "--fbx",
            item["fbx"],
            "--height-m",
            "2",
            "--panel-scale",
            "5",
            "--thickness-m",
            "0.10",
            "--thickness-axis",
            "x",
        ]
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        marker = next(
            (
                line.removeprefix("WING_FBX_VALIDATION ")
                for line in completed.stdout.splitlines()
                if line.startswith("WING_FBX_VALIDATION ")
            ),
            None,
        )
        require(marker is not None, f"Validation marker missing: {item['asset_name']}")
        validation = json.loads(marker)
        require(completed.returncode == 0, f"Validator failed: {item['asset_name']}")
        require(validation.get("status") == "ok", f"Invalid FBX: {item['asset_name']}")
        validations.append(validation)
        print(f"CLEAN_FBX_OK|{item['asset_name']}")

    OUTPUT.write_text(
        json.dumps(
            {
                "status": "ok",
                "profile": {
                    "height_m": 2.0,
                    "ue_panel_scale": 5.0,
                    "final_height_m": 10.0,
                    "thickness_cm": 10.0,
                    "ue_yaw_deg": 90.0,
                },
                "validated_fbx_count": len(validations),
                "validations": validations,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"P05_CLEAN_FBX_BATCH_VALIDATE_SUCCESS|count={len(validations)}|report={OUTPUT}")


main()
