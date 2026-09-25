"""Reimport the Passage 3 wings from the 17 August 2026 clean rebuild.

The 14 August batch under DerivedAssets/GeneratedWingsV2_Passage03 exports
untriangulated n-gons, so Blender and Unreal triangulate the concave silhouettes
differently and the panels render glitched. This points the existing, tested
Passage 3 import at DerivedAssets/GeneratedWingsV2_Passage03_Clean instead.

Only the source folder changes. Content paths, FBX options, texture settings and
material instance parameters stay exactly as wing_integration_common defines them.
"""

import importlib
from pathlib import Path
import sys

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wing_integration_common

importlib.reload(wing_integration_common)

CLEAN_SOURCE = wing_integration_common.PROJECT_ROOT / "DerivedAssets/GeneratedWingsV2_Passage03_Clean"

if not CLEAN_SOURCE.is_dir():
    raise RuntimeError(f"Clean source root missing: {CLEAN_SOURCE}")

wing_integration_common.CONFIGS[3]["source_root"] = CLEAN_SOURCE
unreal.log(f"P03_V2_CLEAN_SOURCE_OVERRIDE|source_root={CLEAN_SOURCE}")

wing_integration_common.import_assets(3)

unreal.log("P03_V2_CLEAN_REIMPORT_SUCCESS")
