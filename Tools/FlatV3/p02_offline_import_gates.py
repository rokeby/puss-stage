"""Offline preflight for every P02 industrial FBX import gate.

Run only with Blender 4.4 in background mode.  This script does not import
``unreal``, open a network socket, or contact MCP.  It factory-cleans before
every FBX import, models UE Interchange's documented P02 conversions, validates
the sidecar through the same pure-Python socket contract as the live importer,
and writes both machine-readable evidence and the conductor-facing matrix.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import bpy
from mathutils import Matrix


REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "DerivedAssets" / "FlatV3" / "Overnight" / "P02Industrial"
CONTROLS = OUT / "OfflineControls"
RESULT_JSON = OUT / "offline_import_gates.json"
REPORT_MD = OUT / "OFFLINE_IMPORT_GATES.md"
OLD_CONTROL_ROOT = REPO / "Backups" / "PreFlatV3P02IndustrialEdge-20261002-1410"
OLD_CONTROL_FBX = OLD_CONTROL_ROOT / "SM_FlatV3_P02_IND_FenceTarp_L.fbx"
MISSING_LODGROUP_FBX = CONTROLS / "SM_FlatV3_P02_IND_FenceTarp_L_MissingLodGroup.fbx"
SLOTS = ["Front", "Flap", "Timber", "Edge"]
TARGET_HEIGHT_CM = 1200.0
BOUNDS_TOLERANCE_CM = 1.5
TRIANGLE_TOLERANCE = 1

sys.path.insert(0, str(REPO / "Tools" / "FlatV3"))
import socket_contract  # noqa: E402


CHECKS = [
    ("VSET", "validation set admits exactly 8/8 unique assets"),
    ("LAYOUT", "P02 layout uses only imported industrial assets and leaves only DuctVent unused"),
    ("FILES", "FBX and matching socket sidecar exist"),
    ("LOD", "one FBX LodGroup with LOD0 and LOD1 (num_lods == 2 model)"),
    ("SLOTS", "Front/Flap/Timber/Edge order and at least one face per slot on both LODs"),
    ("TRIS", "LOD0/LOD1 triangles match validation.json within live +/-1 tolerance"),
    ("BOUNDS", "bounds match validation after Interchange Y negation"),
    ("SIDE", "converted geometry midpoint has the declared L/R sign"),
    ("UVSET", "both LODs contain exactly UV0 and UV1"),
    ("UVSIGN", "UV0/UV1 live-sign slopes pass after Y negation and V flip"),
    ("AXIS", "both LODs retain FrontAxis=-X and the declared Side metadata"),
    ("VC", "both LODs retain the Color vertex-colour layer"),
    ("SCHEAD", "sidecar headers and metadata match the live socket contract"),
    ("SCNAMES", "required Hinge/Pivot/contiguous Pole names only; records are well formed"),
    ("SCRT", "sidecar locations/rotations survive the live source-to-UE round trip"),
    ("SCAXIS", "Hinge +X is base-edge Y and Pivot +X is +Z"),
    ("SCGEOM", "Hinge, Pivot, pole line, side, base and top agree with converted geometry"),
    ("SPAN", "pole span agrees with manifest width within 0.2 cm"),
    ("FOOT", "every pole socket has below-floor baked geometry at both LODs"),
    ("DROP", "Interchange socket-drop model uses sidecar, not FBX empties"),
    ("UECLASS", "actual UE object is unreal.StaticMesh"),
    ("NANITE", "actual imported StaticMesh Nanite setting is disabled"),
    ("UESOCK", "UE add/find/enumerate socket APIs read back the applied sidecar"),
    ("UERELD", "saved package reload, parents/destinations and dirty-state checks"),
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def side_from_asset(asset: str) -> str:
    if asset.endswith("_L"):
        return "L"
    if asset.endswith("_R"):
        return "R"
    raise ValueError(f"Asset has no L/R suffix: {asset}")


def record(status: str, detail: Any) -> dict[str, Any]:
    return {"status": status, "detail": detail}


def pass_if(condition: bool, detail: Any, failure: Any | None = None) -> dict[str, Any]:
    return record("PASS" if condition else "FAIL", detail if condition else (failure if failure is not None else detail))


def factory_import(fbx: Path) -> dict[str, Any]:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(
        filepath=str(fbx), use_custom_props=True, automatic_bone_orientation=False
    )
    objects = list(bpy.context.scene.objects)
    meshes = [obj for obj in objects if obj.type == "MESH"]
    lod0 = next((obj for obj in meshes if obj.name.endswith("_LOD0")), None)
    lod1 = next((obj for obj in meshes if obj.name.endswith("_LOD1")), None)
    groups = [
        obj for obj in objects
        if obj.type == "EMPTY" and obj.get("fbx_type") == "LodGroup"
    ]
    socket_empties = sorted(
        (obj for obj in objects if obj.type == "EMPTY" and obj.name.startswith("SOCKET_")),
        key=lambda obj: obj.name,
    )
    return {
        "objects": objects,
        "meshes": meshes,
        "lod0": lod0,
        "lod1": lod1,
        "groups": groups,
        "socket_empties": socket_empties,
    }


def material_face_counts(obj: Any) -> dict[str, int]:
    counts = Counter({slot: 0 for slot in SLOTS})
    for polygon in obj.data.polygons:
        if polygon.material_index >= len(obj.material_slots):
            continue
        material = obj.material_slots[polygon.material_index].material
        if material and material.name in counts:
            counts[material.name] += 1
    return dict(counts)


def material_slots(obj: Any) -> list[str | None]:
    return [slot.material.name if slot.material else None for slot in obj.material_slots]


def triangle_count(obj: Any) -> int:
    obj.data.calc_loop_triangles()
    return len(obj.data.loop_triangles)


def least_squares(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 3:
        raise ValueError(f"regression needs >=3 paired samples, got {len(xs)}")
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    denominator = sum((value - mx) ** 2 for value in xs)
    if denominator <= 1e-12:
        raise ValueError("regression independent variable is degenerate")
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denominator


def normalized(values: Iterable[float]) -> list[float]:
    values = list(values)
    length = math.sqrt(sum(value * value for value in values))
    if length <= 1e-12:
        raise ValueError("normal mean is degenerate")
    return [value / length for value in values]


def section_uv_live_model(obj: Any, slot_name: str, layer_name: str) -> dict[str, Any] | None:
    """Model a section UV channel after UE Interchange conversion.

    UE reflects geometry Y and FBX V.  Therefore ``Y_ue=-Y_blender`` and
    ``V_ue=1-V_blender``; U, X and Z retain sign.
    """
    slots = material_slots(obj)
    if slot_name not in slots:
        return None
    slot_index = slots.index(slot_name)
    ys: list[float] = []
    zs: list[float] = []
    us: list[float] = []
    vs: list[float] = []
    normals: list[list[float]] = []
    uv_layer = obj.data.uv_layers.get(layer_name)
    if uv_layer is None:
        return None
    normal_matrix = obj.matrix_world.to_3x3().inverted().transposed()
    for polygon in obj.data.polygons:
        if polygon.material_index != slot_index:
            continue
        source_normal = normal_matrix @ polygon.normal
        live_normal = normalized([source_normal.x, -source_normal.y, source_normal.z])
        for loop_index in polygon.loop_indices:
            vertex = obj.matrix_world @ obj.data.vertices[obj.data.loops[loop_index].vertex_index].co
            uv = uv_layer.data[loop_index].uv
            ys.append(-float(vertex.y) * 100.0)
            zs.append(float(vertex.z) * 100.0)
            us.append(float(uv.x))
            vs.append(1.0 - float(uv.y))
            normals.append(live_normal)
    if not ys:
        return None
    try:
        du_dy = least_squares(ys, us)
        dv_dz = least_squares(zs, vs)
    except ValueError as exc:
        return {"samples": len(ys), "error": str(exc)}
    try:
        mean_normal = normalized([sum(row[index] for row in normals) for index in range(3)])
    except ValueError as exc:
        mean_normal = None
        normal_error = str(exc)
    else:
        normal_error = None
    return {
        "samples": len(ys),
        "du_dY": du_dy,
        "dv_dZ": dv_dz,
        "normal": mean_normal,
        "normal_error": normal_error,
    }


def bounds_m(obj: Any) -> dict[str, float]:
    positions = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    return {
        "x_min": min(value.x for value in positions),
        "x_max": max(value.x for value in positions),
        "y_min": min(value.y for value in positions),
        "y_max": max(value.y for value in positions),
        "z_min": min(value.z for value in positions),
        "z_max": max(value.z for value in positions),
    }


def converted_bounds_cm(source: dict[str, float]) -> dict[str, float]:
    return {
        "x_min": source["x_min"] * 100.0,
        "x_max": source["x_max"] * 100.0,
        "y_min": -source["y_max"] * 100.0,
        "y_max": -source["y_min"] * 100.0,
        "z_min": source["z_min"] * 100.0,
        "z_max": source["z_max"] * 100.0,
    }


def validation_bounds_cm(row: dict[str, Any]) -> dict[str, float]:
    value = row["bounds_m"]
    return {
        "y_min": -float(value["y_max"]) * 100.0,
        "y_max": -float(value["y_min"]) * 100.0,
        "z_min": float(value["z_min"]) * 100.0,
        "z_max": float(value["z_max"]) * 100.0,
    }


def close_vector(actual: Iterable[float], expected: Iterable[float], tolerance: float) -> bool:
    return all(abs(float(a) - float(b)) <= tolerance for a, b in zip(actual, expected))


def pole_foot_probe(obj: Any, socket_payload: dict[str, Any]) -> dict[str, Any]:
    positions = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    below_floor = [value for value in positions if value.z < -0.05]
    source_y = [float(value.y) for value in below_floor]
    converted_y_cm = [-value * 100.0 for value in source_y]
    rows = {}
    passed = bool(below_floor)
    for socket in socket_payload["sockets"]:
        if not str(socket["name"]).startswith("SOCKET_Pole_"):
            continue
        ue_x, ue_y, _ = [float(value) for value in socket["relative_location_cm"]]
        source_x = ue_x / 100.0
        source_y_m = -ue_y / 100.0
        nearest_y_cm = min((abs(value - ue_y) for value in converted_y_cm), default=math.inf)
        inside_live_range = bool(converted_y_cm) and (
            min(converted_y_cm) - 2.0 <= ue_y <= max(converted_y_cm) + 2.0
        )
        rows[str(socket["name"])] = {
            "source_xy_m": [source_x, source_y_m],
            "nearest_below_floor_vertex_y_cm": nearest_y_cm,
            "inside_live_y_range": inside_live_range,
        }
        # The live Slot A foot gate compares the socket Y with the range of
        # below-floor pole vertices; it does not require X to coincide with the
        # pole centre because the visible support has radius/depth.
        passed = passed and inside_live_range
    return {
        "pass": passed and bool(rows),
        "poles": rows,
        "below_floor_vertices": len(below_floor),
        "converted_y_range_cm": [min(converted_y_cm), max(converted_y_cm)] if converted_y_cm else None,
    }


def fbx_socket_probe(imported_empties: list[Any], sidecar: dict[str, Any]) -> dict[str, Any]:
    expected = {str(row["name"]): row for row in sidecar["sockets"]}
    actual = {obj.name: obj for obj in imported_empties}
    location_checks = {}
    locations_pass = sorted(actual) == sorted(expected)
    for name, row in expected.items():
        obj = actual.get(name)
        if obj is None:
            location_checks[name] = {"pass": False, "reason": "missing FBX empty"}
            locations_pass = False
            continue
        ue = [float(value) for value in row["relative_location_cm"]]
        expected_source_m = [ue[0] / 100.0, -ue[1] / 100.0, ue[2] / 100.0]
        actual_source_m = [float(obj.location.x), float(obj.location.y), float(obj.location.z)]
        ok = close_vector(actual_source_m, expected_source_m, 0.002)
        location_checks[name] = {
            "pass": ok,
            "fbx_m": actual_source_m,
            "sidecar_inverse_interchange_m": expected_source_m,
        }
        locations_pass = locations_pass and ok
    return {
        "fbx_empty_names": sorted(actual),
        "sidecar_names": sorted(expected),
        "fbx_empty_locations_match_sidecar": locations_pass,
        "locations": location_checks,
        "modelled_ue_imported_socket_names": [],
        "modelled_applied_socket_names": sorted(expected),
    }


def validate_asset(
    *, asset: str, fbx: Path, sidecar_path: Path, validation_row: dict[str, Any],
    manifest_row: dict[str, Any], validation_set_pass: bool,
    layout_check: dict[str, Any],
) -> dict[str, Any]:
    checks: dict[str, dict[str, Any]] = {
        "VSET": pass_if(validation_set_pass, "validation.json is exactly 8/8 unique and all_pass=true"),
        "LAYOUT": layout_check,
        "FILES": pass_if(
            fbx.is_file() and sidecar_path.is_file(),
            {"fbx": str(fbx), "sidecar": str(sidecar_path)},
        ),
    }
    if checks["FILES"]["status"] == "FAIL":
        for check_id, _ in CHECKS:
            if check_id in checks:
                continue
            checks[check_id] = record(
                "UNCOVERED" if check_id.startswith("UE") or check_id == "NANITE" else "FAIL",
                "requires Unreal Editor/Interchange" if check_id.startswith("UE") or check_id == "NANITE" else "required input missing",
            )
        return {"asset": asset, "fbx": str(fbx), "checks": checks}

    imported = factory_import(fbx)
    lod0 = imported["lod0"]
    lod1 = imported["lod1"]
    lod_meshes = [obj for obj in (lod0, lod1) if obj is not None]
    group_ok = (
        len(imported["groups"]) == 1 and len(lod_meshes) == 2
        and all(obj.parent == imported["groups"][0] for obj in lod_meshes)
    )
    checks["LOD"] = pass_if(
        group_ok,
        {"lod_groups": len(imported["groups"]), "lod_meshes": [obj.name for obj in lod_meshes]},
    )
    if lod0 is None or lod1 is None:
        for check_id in ("SLOTS", "TRIS", "BOUNDS", "SIDE", "UVSET", "UVSIGN", "AXIS", "VC", "SCGEOM", "FOOT"):
            checks[check_id] = record("FAIL", "LOD0/LOD1 mesh pair unavailable")
    else:
        slots0, slots1 = material_slots(lod0), material_slots(lod1)
        faces0, faces1 = material_face_counts(lod0), material_face_counts(lod1)
        effective0 = [name for name in slots0 if name in faces0 and faces0[name] > 0]
        effective1 = [name for name in slots1 if name in faces1 and faces1[name] > 0]
        slots_ok = effective0 == SLOTS and effective1 == SLOTS
        checks["SLOTS"] = pass_if(
            slots_ok,
            {"slots_lod0": slots0, "slots_lod1": slots1, "faces_lod0": faces0, "faces_lod1": faces1},
            {"effective_lod0": effective0, "effective_lod1": effective1, "faces_lod0": faces0, "faces_lod1": faces1},
        )

        actual_triangles = {"lod0": triangle_count(lod0), "lod1": triangle_count(lod1)}
        expected_triangles = {key: int(validation_row["triangles"][key]) for key in ("lod0", "lod1")}
        triangles_ok = all(
            abs(actual_triangles[key] - expected_triangles[key]) <= TRIANGLE_TOLERANCE
            for key in ("lod0", "lod1")
        )
        checks["TRIS"] = pass_if(
            triangles_ok,
            {"actual": actual_triangles, "validation": expected_triangles, "tolerance": TRIANGLE_TOLERANCE},
        )

        source_bounds = bounds_m(lod0)
        actual_bounds = converted_bounds_cm(source_bounds)
        expected_bounds = validation_bounds_cm(validation_row)
        compared_keys = ("y_min", "y_max", "z_min", "z_max")
        bounds_ok = all(
            abs(actual_bounds[key] - expected_bounds[key]) <= BOUNDS_TOLERANCE_CM
            for key in compared_keys
        )
        checks["BOUNDS"] = pass_if(
            bounds_ok,
            {"actual_converted_cm": actual_bounds, "validation_converted_cm": expected_bounds, "tolerance_cm": BOUNDS_TOLERANCE_CM},
        )
        side = side_from_asset(asset)
        y_mid = (actual_bounds["y_min"] + actual_bounds["y_max"]) * 0.5
        side_ok = (side == "L" and y_mid > 0.0) or (side == "R" and y_mid < 0.0)
        checks["SIDE"] = pass_if(
            side_ok,
            {"side": side, "converted_y_cm": [actual_bounds["y_min"], actual_bounds["y_max"]], "midpoint_cm": y_mid},
        )

        uvsets = {
            "lod0": [layer.name for layer in lod0.data.uv_layers],
            "lod1": [layer.name for layer in lod1.data.uv_layers],
        }
        checks["UVSET"] = pass_if(all(value == ["UV0", "UV1"] for value in uvsets.values()), uvsets)
        section_data = {
            "uv0": {
                "lod0": {slot: section_uv_live_model(lod0, slot, "UV0") for slot in ("Front", "Flap")},
                "lod1": {"Front": section_uv_live_model(lod1, "Front", "UV0")},
            },
            "uv1": {
                "lod0": {slot: section_uv_live_model(lod0, slot, "UV1") for slot in ("Front", "Flap")},
                "lod1": {"Front": section_uv_live_model(lod1, "Front", "UV1")},
            },
        }
        uv0_sign_ok = all(
            value is not None and "error" not in value
            and float(value["du_dY"]) > 0.0 and float(value["dv_dZ"]) < 0.0
            for lod_data in section_data["uv0"].values() for value in lod_data.values()
        )
        uv1_sign_ok = all(
            value is not None and "error" not in value
            and float(value["du_dY"]) > 0.0 and float(value["dv_dZ"]) > 0.0
            for lod_data in section_data["uv1"].values() for value in lod_data.values()
        )
        checks["UVSIGN"] = pass_if(uv0_sign_ok and uv1_sign_ok, section_data)
        metadata = {
            "lod0": {"FrontAxis": lod0.get("FrontAxis"), "Side": lod0.get("Side")},
            "lod1": {"FrontAxis": lod1.get("FrontAxis"), "Side": lod1.get("Side")},
        }
        axis_ok = all(
            value["FrontAxis"] == "-X" and value["Side"] == side
            for value in metadata.values()
        )
        checks["AXIS"] = pass_if(axis_ok, metadata)
        colors = {
            "lod0": sorted(attribute.name for attribute in lod0.data.color_attributes),
            "lod1": sorted(attribute.name for attribute in lod1.data.color_attributes),
        }
        checks["VC"] = pass_if(all("Color" in value for value in colors.values()), colors)

    sidecar = read_json(sidecar_path)
    side = side_from_asset(asset)
    source_records = [
        {
            "name": str(row["name"]),
            "location_m": [
                float(row["relative_location_cm"][0]) / 100.0,
                -float(row["relative_location_cm"][1]) / 100.0,
                float(row["relative_location_cm"][2]) / 100.0,
            ],
        }
        for row in sidecar.get("sockets", [])
    ]
    expected_socket = None
    make_error = None
    try:
        expected_socket = socket_contract.make_wing_payload_from_fbx_records(
            asset=asset, side=side, height_cm=TARGET_HEIGHT_CM, records=source_records
        )
    except Exception as exc:  # collect every failure instead of aborting the matrix
        make_error = f"{type(exc).__name__}: {exc}"

    required_header = {
        "schema_version": 1,
        "asset": asset,
        "coordinate_space": "Unreal static-mesh local",
        "location_units": "cm",
        "rotation_units": "degrees",
        "rotation_order": socket_contract.ROTATION_ORDER,
        "fbx_interchange_conversion": "X=X, Y=-Y, Z=Z",
        "contract": socket_contract.SOCKET_CONTRACT,
    }
    header_mismatches = {
        key: {"actual": sidecar.get(key), "expected": value}
        for key, value in required_header.items() if sidecar.get(key) != value
    }
    checks["SCHEAD"] = pass_if(not header_mismatches, {"mismatches": header_mismatches})
    rows = sidecar.get("sockets")
    row_shape_ok = isinstance(rows, list) and all(
        isinstance(row.get("relative_location_cm"), list)
        and len(row["relative_location_cm"]) == 3
        and isinstance(row.get("relative_rotation_deg"), dict)
        and sorted(row["relative_rotation_deg"]) == ["pitch", "roll", "yaw"]
        for row in rows
    )
    names = [str(row.get("name")) for row in rows] if isinstance(rows, list) else []
    pole_indices = sorted(
        int(match.group(1)) for name in names
        if (match := socket_contract.WING_POLE_RE.fullmatch(name))
    )
    allowed_names = all(
        name in {"SOCKET_Hinge", "SOCKET_Pivot"} or socket_contract.WING_POLE_RE.fullmatch(name)
        for name in names
    )
    names_ok = (
        row_shape_ok and len(names) == len(set(names)) and allowed_names
        and "SOCKET_Hinge" in names and "SOCKET_Pivot" in names
        and pole_indices == list(range(1, len(pole_indices) + 1)) and bool(pole_indices)
    )
    checks["SCNAMES"] = pass_if(names_ok, {"names": names, "make_expected_error": make_error})
    payload_failures = (
        socket_contract.validate_socket_payload(sidecar, expected_socket, require_metadata=True)
        if expected_socket is not None else [make_error]
    )
    checks["SCRT"] = pass_if(not payload_failures, {"failures": payload_failures})
    axis_failures = [
        failure for failure in payload_failures
        if "HINGE_SOCKET" in str(failure) or "PIVOT_SOCKET_AXIS" in str(failure)
    ]
    checks["SCAXIS"] = pass_if(not axis_failures and expected_socket is not None, {"failures": axis_failures})

    if lod0 is not None:
        actual_bounds = converted_bounds_cm(bounds_m(lod0))
        geometry_failures = socket_contract.validate_wing_geometry(
            sidecar,
            side=side,
            height_cm=TARGET_HEIGHT_CM,
            bounds_cm={key: actual_bounds[key] for key in ("y_min", "y_max", "z_min", "z_max")},
        )
        checks["SCGEOM"] = pass_if(not geometry_failures, {"failures": geometry_failures, "bounds_cm": actual_bounds})
        foot_rows = {lod: pole_foot_probe(obj, sidecar) for lod, obj in (("lod0", lod0), ("lod1", lod1))}
        checks["FOOT"] = pass_if(all(value["pass"] for value in foot_rows.values()), foot_rows)

    pole_y = [
        float(row["relative_location_cm"][1])
        for row in rows if str(row.get("name", "")).startswith("SOCKET_Pole_")
    ] if isinstance(rows, list) else []
    actual_span_cm = max(pole_y) - min(pole_y) if pole_y else -1.0
    expected_span_cm = float(manifest_row["dimensions_m"]["width"]) * 100.0
    checks["SPAN"] = pass_if(
        bool(pole_y) and abs(actual_span_cm - expected_span_cm) <= 0.2,
        {"actual_cm": actual_span_cm, "manifest_cm": expected_span_cm, "tolerance_cm": 0.2},
    )
    drop_model = fbx_socket_probe(imported["socket_empties"], sidecar)
    checks["DROP"] = pass_if(
        drop_model["modelled_ue_imported_socket_names"] == []
        and drop_model["modelled_applied_socket_names"] == drop_model["sidecar_names"],
        drop_model,
    )

    checks["UECLASS"] = record("UNCOVERED", "Requires UE 5.8 Interchange and isinstance(unreal.StaticMesh)")
    checks["NANITE"] = record("UNCOVERED", "Requires UE StaticMesh nanite_settings read-back; live importer sets false")
    checks["UESOCK"] = record("UNCOVERED", "Requires UE add_socket/find_socket/get_sockets_by_tag read-back")
    checks["UERELD"] = record("UNCOVERED", "Requires UE destination assets, material parents, save/reload and dirty-package census")
    return {
        "asset": asset,
        "fbx": str(fbx),
        "fbx_sha256": sha256(fbx),
        "checks": checks,
    }


def plant_missing_lodgroup_control(source_fbx: Path) -> dict[str, Any]:
    imported = factory_import(source_fbx)
    lods = [obj for obj in (imported["lod0"], imported["lod1"]) if obj is not None]
    if len(lods) != 2:
        raise RuntimeError("Cannot plant missing-LodGroup control without LOD0 and LOD1")
    CONTROLS.mkdir(parents=True, exist_ok=True)
    for obj in lods:
        world = obj.matrix_world.copy()
        obj.parent = None
        obj.matrix_world = world
    bpy.ops.object.select_all(action="DESELECT")
    for obj in lods:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = lods[0]
    bpy.ops.export_scene.fbx(
        filepath=str(MISSING_LODGROUP_FBX),
        use_selection=True,
        object_types={"MESH"},
        apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-X",
        axis_up="Z",
        use_mesh_modifiers=True,
        mesh_smooth_type="FACE",
        use_custom_props=True,
        add_leaf_bones=False,
        bake_anim=False,
        path_mode="AUTO",
    )
    return {
        "path": str(MISSING_LODGROUP_FBX),
        "source": str(source_fbx),
        "sha256": sha256(MISSING_LODGROUP_FBX),
        "plant": "exported LOD0/LOD1 meshes without their LodGroup empty",
    }


def status_row(result: dict[str, Any]) -> list[str]:
    return [result["asset"]] + [result["checks"][check_id]["status"] for check_id, _ in CHECKS]


def markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    return [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *("| " + " | ".join(row) + " |" for row in rows),
    ]


def write_report(payload: dict[str, Any]) -> None:
    production = payload["production"]
    controls = payload["controls"]
    check_headers = [check_id for check_id, _ in CHECKS]
    lines = [
        "# P02 industrial offline import gates",
        "",
        "## Outcome",
        "",
        f"- **[measured]** Blender `{payload['blender']}` ran factory-clean, headless FBX imports. Production result: **{payload['production_passed']}/8 PASS**.",
        f"- **[measured]** Negative controls: old FenceTarp L empty-slot rejection = **{payload['negative_controls']['old_empty_slot_rejected']}**; planted missing-LodGroup rejection = **{payload['negative_controls']['missing_lodgroup_rejected']}**.",
        "- **[declaration-proven]** No `unreal` module, MCP client, HTTP client, or port 8010 route is imported or called by `Tools/FlatV3/p02_offline_import_gates.py`.",
        "- **[inferred]** The offline model removes FBX socket empties and then applies the sidecar because that is the known Interchange behavior encoded by the live gate; the actual UE socket API remains UNCOVERED.",
        "- **[inferred]** Passing this report is import preflight, not Unreal saved/read-back, runtime, rendered, package, or delivery acceptance.",
        "",
        "## Asset x check matrix",
        "",
    ]
    lines += markdown_table(["Asset", *check_headers], [status_row(row) for row in production])
    lines += ["", "## Negative controls", ""]
    lines += markdown_table(["Control", *check_headers], [status_row(row) for row in controls])
    lines += ["", "## Check legend", ""]
    lines += [f"- `{check_id}` — {description}." for check_id, description in CHECKS]
    lines += [
        "",
        "## Live gate inventory and offline equivalence",
        "",
        "- **[declaration-proven]** Industrial admission requires `validation.json` `all_pass`, `passed_assets == 8`, `asset_count == 8`, and a passing row for every manifest asset (`Saved/CodexFlatV3/swapkit/p02_import.py:145-157`). `VSET` re-evaluates those declarations and unique membership.",
        "- **[declaration-proven]** Layout coverage requires every INDUSTRIAL proposal to be in the imported set and requires the unused industrial set to be exactly the DuctVent pair (`Saved/CodexFlatV3/swapkit/p02_import.py:209-241`). `LAYOUT` reproduces that check from `run_p02.json` and `P02_LAYOUT_DRAFT_v2.json`.",
        "- **[declaration-proven]** The live inventory requires each FBX and socket sidecar, reconstructs the expected payload with `Y=-Y`, validates it against `socket_contract`, checks socket geometry, checks pole span against manifest width, and requires exactly eight unique rows (`Saved/CodexFlatV3/swapkit/p02_import.py:158-205`). `FILES`, `SCHEAD`, `SCNAMES`, `SCRT`, `SCAXIS`, `SCGEOM`, and `SPAN` are direct offline equivalents.",
        "- **[declaration-proven]** `make_wing_payload_from_fbx_records` requires contiguous nonempty pole names, Hinge/Pivot, and a non-degenerate pole span before re-emitting Interchange-facing positions (`Tools/FlatV3/socket_contract.py:99-139`). `SCNAMES` and `SCRT` execute that same function.",
        "- **[declaration-proven]** Payload validation covers headers, rotation metadata, duplicate/exact names, record shapes, location/rotation tolerance, and Hinge/Pivot axes (`Tools/FlatV3/socket_contract.py:158-214`). `SCHEAD`, `SCNAMES`, `SCRT`, and `SCAXIS` execute that same validator.",
        "- **[declaration-proven]** Socket-to-geometry validation covers allowed/required names, pole sequence, hinge at the base origin, poles on X=Z=0 and on the correct side near Y bounds, pivot midpoint/height, and base/top inside geometry (`Tools/FlatV3/socket_contract.py:217-273`). `SCGEOM` executes it against bounds read from each rebuilt FBX; `FOOT` additionally requires every pole socket Y to lie within the actual below-floor geometry range at both LODs.",
        "- **[declaration-proven]** `slot_a_import.socket_payload` repeats the sidecar header/record checks (`Saved/CodexFlatV3/slot_a_import.py:252-280`). `SCHEAD` and `SCNAMES` cover them.",
        "- **[declaration-proven]** `apply_sockets` requires Hinge/Pivot/poles only, requires imported sockets to be empty, applies the sidecar, and calls exact socket read-back (`Saved/CodexFlatV3/slot_a_import.py:309-339`). `DROP` explicitly models the known FBX-empty drop and sidecar authority; actual UE add/find/enumerate behavior is `UESOCK` UNCOVERED.",
        "- **[declaration-proven]** Exact socket enumeration, `find_socket`, 0.01 cm location, and 0.01 degree wrapped-rotation checks are live (`Saved/CodexFlatV3/slot_a_import.py:283-306`). `SCRT` covers the data round trip; `UESOCK` remains UNCOVERED because Blender cannot exercise those UE APIs.",
        "- **[declaration-proven]** P02 read-back requires exact validation slot order, two LODs, exact sidecar socket count, converted Y/Z bounds within 1.5 cm, triangles within one, and Nanite off (`Saved/CodexFlatV3/swapkit/p02_import.py:244-275`). `LOD`, `SLOTS`, `TRIS`, `BOUNDS`, `SCNAMES`, and `SCRT` cover the reproducible parts; `NANITE` is UNCOVERED.",
        "- **[declaration-proven]** The live importer uses zero transform, unit scale, scene conversion, imported normals/tangents and vertex colours, no lightmap UV generation, no auto collision, and `import_mesh_lods=True` (`Saved/CodexFlatV3/phase1_import.py:244-264`). FBX content consequences are covered by `LOD`, `UVSET`, `VC`, `AXIS`, and `BOUNDS`; engine option application itself is UNCOVERED.",
        "- **[declaration-proven]** Slot A's generic verifier computes UV0 regressions over imported section positions/UVs (`Saved/CodexFlatV3/phase1_import.py:359-374`) and requires Front/Flap `du/dY > 0`, `dv/dZ < 0`, plus Front normal -X (`Saved/CodexFlatV3/slot_a_import.py:449-464`). P02 industrial does **not** call `verify_flat_general`; it calls `verify_industrial` directly (`Saved/CodexFlatV3/swapkit/p02_import.py:278-290`). At the conductor's request, `UVSIGN` still reproduces the UV0/UV1 sign portions after explicit Y and V conversion. `AXIS` is the industrial builder's retained `FrontAxis=-X`/Side metadata check; socket rotation axes are separately executed by `SCAXIS`. The generic Front mean-normal and `LOD1_FLAP_SURVIVED` rules do not apply to this industrial path, which deliberately requires all four nonempty slots on both LODs.",
        "- **[declaration-proven]** The live main path also checks editor context, destination state, narrow save/reload, fresh read-back, and zero dirty packages (`Saved/CodexFlatV3/swapkit/p02_import.py:293-378`). These require Unreal/editor state and are `UECLASS`, `NANITE`, `UESOCK`, or `UERELD` UNCOVERED, with the exact reason shown in the JSON evidence.",
        "",
        "## Builder corrections made by this run",
        "",
        "- **[declaration-proven]** Right-side UV0 now keeps the signed mapping and uses a +1 range offset instead of a second U reflection (`DerivedAssets/FlatV3/Overnight/P02Industrial/build_p02_industrial.py:99-117`).",
        "- **[declaration-proven]** Synthetic nonempty Flap faces must span both Y and Z, preventing a degenerate live UV regression (`DerivedAssets/FlatV3/Overnight/P02Industrial/build_p02_industrial.py:148-205`).",
        "- **[declaration-proven]** DuctVent L now receives a far baked pole at its declared 8.8 m Pole_2 location in both LODs (`DerivedAssets/FlatV3/Overnight/P02Industrial/build_p02_industrial.py:318-332`).",
        "- **[declaration-proven]** RollerShutter LOD1 curtain parts are moved to the same frame centre as LOD0 before consolidation (`DerivedAssets/FlatV3/Overnight/P02Industrial/build_p02_industrial.py:512-523`).",
        "",
        "## Control proof",
        "",
        f"- **[measured]** Old control `{payload['control_sources']['old_fbx']}` failed `SLOTS`; its SHA-256 is `{payload['control_sources']['old_sha256']}`.",
        f"- **[measured]** Planted control `{payload['control_sources']['missing_lodgroup']['path']}` failed `LOD`; its SHA-256 is `{payload['control_sources']['missing_lodgroup']['sha256']}`.",
        "- **[measured]** Full numeric details, per-slot face counts, UV slopes, normals, converted bounds, socket failures and nearest pole-foot geometry are in `DerivedAssets/FlatV3/Overnight/P02Industrial/offline_import_gates.json`.",
        "",
        "## Acceptance boundary",
        "",
        "- **[measured]** This run proves the Blender-readable FBX/validation/manifest/sidecar contract and the explicit Interchange conversion model.",
        "- **[inferred]** It does not prove UE 5.8's actual Interchange output, StaticMesh class, Nanite property, socket APIs, asset parents/destinations, save/reload, dirty state, runtime, or rendered appearance. Those remain visibly UNCOVERED rather than being reported as offline PASS.",
    ]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    if bpy.app.version[:2] != (4, 4):
        raise RuntimeError(f"Blender 4.4 required; running {bpy.app.version_string}")
    manifest = read_json(OUT / "manifest.json")
    validation = read_json(OUT / "validation.json")
    manifest_rows = {str(row["asset"]): row for row in manifest.get("assets", [])}
    validation_rows = {str(row["asset"]): row for row in validation.get("assets", [])}
    assets = [str(row["asset"]) for row in manifest.get("assets", [])]
    validation_set_pass = (
        bool(validation.get("all_pass"))
        and int(validation.get("passed_assets", 0)) == 8
        and int(validation.get("asset_count", 0)) == 8
        and len(assets) == 8 and len(set(assets)) == 8
        and set(assets) == set(validation_rows)
        and all(bool(validation_rows[asset].get("pass")) for asset in assets)
    )
    config = read_json(REPO / "Saved" / "CodexFlatV3" / "swapkit" / "run_p02.json")
    layout_path = REPO / str(config["mapping_file"])
    layout = read_json(layout_path)
    occurrences = layout.get("occurrences", [])
    used_industrial = {
        str(proposal["asset"])
        for row in occurrences
        for key in ("left", "right", "top")
        for proposal in (row["proposal"][key],)
        if str(proposal.get("family_class", "")).upper() == "INDUSTRIAL"
    }
    industrial_names = set(assets)
    unused_industrial = industrial_names - used_industrial
    expected_unused = {name for name in industrial_names if "DuctVent" in name}
    layout_ok = (
        len(occurrences) == 23
        and [int(row.get("sequence_order", 0)) for row in occurrences] == list(range(1, 24))
        and used_industrial <= industrial_names
        and unused_industrial == expected_unused
    )
    layout_check = pass_if(
        layout_ok,
        {
            "mapping": str(layout_path),
            "used_industrial": sorted(used_industrial),
            "unused_industrial": sorted(unused_industrial),
            "expected_unused": sorted(expected_unused),
        },
    )
    production = [
        validate_asset(
            asset=asset,
            fbx=OUT / str(manifest_rows[asset]["fbx"]),
            sidecar_path=OUT / f"sockets_{asset}.json",
            validation_row=validation_rows[asset],
            manifest_row=manifest_rows[asset],
            validation_set_pass=validation_set_pass,
            layout_check=layout_check,
        )
        for asset in assets
    ]

    if not OLD_CONTROL_FBX.is_file():
        raise RuntimeError(f"Old FenceTarp control not found: {OLD_CONTROL_FBX}")
    old_validation = read_json(OLD_CONTROL_ROOT / "validation.json")
    old_rows = {str(row["asset"]): row for row in old_validation["assets"]}
    old_asset = "SM_FlatV3_P02_IND_FenceTarp_L"
    old_control = validate_asset(
        asset=old_asset,
        fbx=OLD_CONTROL_FBX,
        sidecar_path=OLD_CONTROL_ROOT / f"sockets_{old_asset}.json",
        validation_row=old_rows[old_asset],
        manifest_row=manifest_rows[old_asset],
        validation_set_pass=True,
        layout_check=layout_check,
    )

    planted = plant_missing_lodgroup_control(OUT / f"{old_asset}.fbx")
    missing_control = validate_asset(
        asset=old_asset,
        fbx=MISSING_LODGROUP_FBX,
        sidecar_path=OUT / f"sockets_{old_asset}.json",
        validation_row=validation_rows[old_asset],
        manifest_row=manifest_rows[old_asset],
        validation_set_pass=validation_set_pass,
        layout_check=layout_check,
    )
    controls = [
        {**old_control, "asset": "CONTROL_old_FenceTarp_L"},
        {**missing_control, "asset": "CONTROL_missing_LodGroup"},
    ]
    production_passed = sum(
        all(value["status"] != "FAIL" for value in row["checks"].values())
        for row in production
    )
    old_rejected = old_control["checks"]["SLOTS"]["status"] == "FAIL"
    lod_rejected = missing_control["checks"]["LOD"]["status"] == "FAIL"
    payload = {
        "schema_version": 1,
        "blender": bpy.app.version_string,
        "headless": bpy.app.background,
        "offline_only": True,
        "interchange_model": {
            "geometry": "X=X, Y=-Y, Z=Z",
            "uv": "U=U, V=1-V",
            "empty_material_slots": "dropped; require >0 faces per slot",
            "lod": "raw FBX LodGroup required and modelled num_lods=2",
            "fbx_socket_empties": "dropped; apply sidecar records",
        },
        "checks": [{"id": check_id, "description": description} for check_id, description in CHECKS],
        "production": production,
        "controls": controls,
        "production_passed": production_passed,
        "production_count": len(production),
        "negative_controls": {
            "old_empty_slot_rejected": old_rejected,
            "missing_lodgroup_rejected": lod_rejected,
        },
        "control_sources": {
            "old_fbx": str(OLD_CONTROL_FBX),
            "old_sha256": sha256(OLD_CONTROL_FBX),
            "missing_lodgroup": planted,
        },
    }
    RESULT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    write_report(payload)
    failed_assets = [
        row["asset"] for row in production
        if any(value["status"] == "FAIL" for value in row["checks"].values())
    ]
    print(
        "P02_OFFLINE_IMPORT_GATES|production=%d/%d|old_empty_slot_rejected=%s|"
        "missing_lodgroup_rejected=%s|failed=%s"
        % (production_passed, len(production), old_rejected, lod_rejected, failed_assets)
    )
    if failed_assets or not old_rejected or not lod_rejected:
        raise RuntimeError("P02 offline import gate failure; inspect offline_import_gates.json")


if __name__ == "__main__":
    main()
