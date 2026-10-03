"""Build the deterministic Scene 3 exit-door texture crop.

The backdrop is a 20 x 30 m plane whose imported UV0 runs U toward Unreal +Y
and V down.  The closed leaf is the doorway minus the existing 1 cm seam, so
the texture crop is taken from the leaf's 299 x 449 cm visible footprint, not
from the nominal 300 x 450 cm opening.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image


PROJECT_DIR = Path(__file__).resolve().parents[2]
BACKDROP_DIR = PROJECT_DIR / "DerivedAssets" / "FlatV3" / "Scene3" / "backdrop"
TEXTURE_DIR = BACKDROP_DIR / "textures"
OUTPUT_DIR = BACKDROP_DIR / "exit_door_crop"
VALIDATION_PATH = BACKDROP_DIR / "SM_FlatV3_S3_Backdrop_validation.json"
MANIFEST_PATH = OUTPUT_DIR / "s3_exit_door_crop_manifest.json"

BACKDROP_SIZE_CM = (2000.0, 3000.0)
BACKDROP_BOTTOM_Z_CM = -5.0
LEAF_CENTER_YZ_CM = (0.0, 225.0)
LEAF_SIZE_YZ_CM = (299.0, 449.0)
OUTPUT_SIZE_PX = (1024, 2048)

SOURCES = {
    "SkinColor": TEXTURE_DIR / "T_S3_OpalBeach_Backdrop_SkinColor.png",
    "SkinMask": TEXTURE_DIR / "T_S3_OpalBeach_Backdrop_SkinMask.png",
    "SkinNormal": TEXTURE_DIR / "T_S3_OpalBeach_Backdrop_SkinNormal.png",
}
OUTPUTS = {
    kind: OUTPUT_DIR / ("T_S3_OpalBeach_ExitDoor_%s.png" % kind)
    for kind in SOURCES
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def leaf_uv_rect() -> list[float]:
    half_y = LEAF_SIZE_YZ_CM[0] * 0.5
    half_z = LEAF_SIZE_YZ_CM[1] * 0.5
    y0 = LEAF_CENTER_YZ_CM[0] - half_y
    y1 = LEAF_CENTER_YZ_CM[0] + half_y
    z0 = LEAF_CENTER_YZ_CM[1] - half_z
    z1 = LEAF_CENTER_YZ_CM[1] + half_z
    u0 = (y0 + BACKDROP_SIZE_CM[0] * 0.5) / BACKDROP_SIZE_CM[0]
    u1 = (y1 + BACKDROP_SIZE_CM[0] * 0.5) / BACKDROP_SIZE_CM[0]
    v_top = 1.0 - (z1 - BACKDROP_BOTTOM_Z_CM) / BACKDROP_SIZE_CM[1]
    v_bottom = 1.0 - (z0 - BACKDROP_BOTTOM_Z_CM) / BACKDROP_SIZE_CM[1]
    return [u0, v_top, u1, v_bottom]


def validate_backdrop_mesh() -> dict:
    validation = json.loads(VALIDATION_PATH.read_text(encoding="utf-8"))
    handedness = validation["checks"]["unreal_axis_handedness"]
    vertical = validation["checks"]["raw_fbx_vertical_uv"]
    normal = validation["checks"]["simulated_unreal_normal"]["value"]
    bounds = validation["checks"]["bottom_centre_origin"]["bounds_m"]
    if (
        validation.get("pass") is not True
        or abs(float(handedness["du_d_unreal_y_per_m"]) - 0.05) > 1.0e-12
        or abs(float(vertical["dv_dz_per_m"]) - (1.0 / 30.0)) > 1.0e-12
        or [float(value) for value in normal] != [-1.0, 0.0, 0.0]
        or [float(bounds["min"][1]), float(bounds["max"][1])] != [-10.0, 10.0]
        or [float(bounds["min"][2]), float(bounds["max"][2])] != [0.0, 30.0]
    ):
        raise RuntimeError("S3 backdrop mesh validation no longer matches the crop contract")
    return {
        "bounds_y_cm": [-1000.0, 1000.0],
        "bounds_z_cm": [0.0, 3000.0],
        "du_dY": 0.0005,
        "dv_dZ": -1.0 / 3000.0,
        "normal": [-1.0, 0.0, 0.0],
    }


def main() -> int:
    mesh = validate_backdrop_mesh()
    rect = leaf_uv_rect()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    textures = {}
    for kind, source in SOURCES.items():
        if not source.is_file():
            raise RuntimeError("missing source texture: %s" % source)
        with Image.open(source) as image:
            width, height = image.size
            source_box = (
                rect[0] * width,
                rect[1] * height,
                rect[2] * width,
                rect[3] * height,
            )
            cropped = image.transform(
                OUTPUT_SIZE_PX,
                Image.Transform.EXTENT,
                source_box,
                # Pillow's EXTENT transform supports bicubic, not Lanczos.
                # EXTENT is required here because the exact UV boundaries land
                # between source pixels.
                resample=Image.Resampling.BICUBIC,
            )
            cropped.save(OUTPUTS[kind], optimize=True)
        textures[kind] = {
            "source": str(source),
            "source_size_px": [width, height],
            "source_sha256": sha256(source),
            "source_box_px_left_top_right_bottom": list(source_box),
            "output": str(OUTPUTS[kind]),
            "output_size_px": list(OUTPUT_SIZE_PX),
            "output_sha256": sha256(OUTPUTS[kind]),
        }

    opening_rect = [
        0.425,
        1.0 - (450.0 - BACKDROP_BOTTOM_Z_CM) / 3000.0,
        0.575,
        1.0 - (0.0 - BACKDROP_BOTTOM_Z_CM) / 3000.0,
    ]
    manifest = {
        "schema_version": 1,
        "proof": {
            "declaration_proven": [
                "S3 backdrop placed landed at dock (6497, 0, -5) cm.",
                "Door opening is centred, 300 x 450 cm; the visible leaf keeps the 1 cm seam.",
            ],
            "measured": [
                "Import run 190842 read back du/dY=0.0005, dv/dZ=-0.000333333333 and normal=-X.",
                "The source mesh validation records Y=-1000..1000 cm and Z=0..3000 cm.",
            ],
            "inferred": [],
        },
        "backdrop": {
            "mesh": "/Game/Scenes/Wings/FlatV3/Scene3/StaticMeshes/SM_FlatV3_S3_Backdrop",
            "material": "/Game/Scenes/Wings/FlatV3/Scene3/Materials/MI_S3_OpalBeach_Backdrop",
            "landed_dock_location_cm": [6497.0, 0.0, BACKDROP_BOTTOM_Z_CM],
            "mesh_readback": mesh,
            "import_verify_run": "190842",
        },
        "opening": {
            "center_yz_cm": [0.0, 225.0],
            "size_yz_cm": [300.0, 450.0],
            "uv_rect_left_top_right_bottom": opening_rect,
        },
        "leaf": {
            "center_yz_cm": list(LEAF_CENTER_YZ_CM),
            "size_yz_cm": list(LEAF_SIZE_YZ_CM),
            "uv_rect_left_top_right_bottom": rect,
            "uv_scale": [rect[2] - rect[0], rect[3] - rect[1]],
            "uv_offset": rect[:2],
        },
        "output_material": {
            "asset": "/Game/Scenes/Wings/FlatV3/Scene3/Materials/MI_S3_OpalBeach_ExitDoor",
            "parent": "/Game/Scenes/Wings/FlatV3/Scene3/Materials/MI_S3_OpalBeach_Backdrop",
        },
        "textures": textures,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        "S3_EXIT_CROP_BUILD_OK|uv=%.9f,%.9f,%.9f,%.9f|size=299x449cm|textures=3"
        % tuple(rect)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
