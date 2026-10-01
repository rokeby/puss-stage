"""Import the Scene 3 wave flats and Opal Beach skin (dry run by default).

The dedicated wrapper is the only way to enable apply.  Dry-run inventories
all sources, destinations, and required parents without mutating Unreal state.
"""
import datetime
import hashlib
import json
import os
import traceback

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
TARGET_ROOT = "/Game/Scenes/Wings/FlatV3/Scene3"
MESH_ROOT = TARGET_ROOT + "/StaticMeshes"
TEXTURE_ROOT = TARGET_ROOT + "/Textures"
INSTANCE_ROOT = TARGET_ROOT + "/Materials/Instances"
BACKDROP_MATERIAL_ROOT = TARGET_ROOT + "/Materials"

PARENTS = {
    "Front": "/Game/Scenes/Wings/PaintedSurface/Billboard/MI_Billboard_Front",
    "Flap": "/Game/Scenes/Wings/PaintedSurface/Billboard/MI_Billboard_Flap",
    # Revision 2: both slots temporarily use this master directly.  Do not
    # create an ad-hoc V3 master or a placeholder MI.
    "Timber": "/Game/Scenes/Wings/PaintedSurface/M_Wing_CanvasEdge_Master",
    "Edge": "/Game/Scenes/Wings/PaintedSurface/M_Wing_CanvasEdge_Master",
}
WAVE_NAMES = tuple(
    "S3_WaveRow%d_%s" % (row, half)
    for row in (1, 2, 3)
    for half in ("A", "B")
)
TEXTURE_KINDS = ("SkinColor", "SkinMask", "SkinNormal")
MI_SLOTS = ("Front", "Flap", "Timber", "Edge")
BACKDROP_NAME = "S3_OpalBeach_Backdrop"
BACKDROP_MI = TARGET_ROOT + "/Materials/MI_S3_OpalBeach_Backdrop"
BACKDROP_MESH = MESH_ROOT + "/SM_FlatV3_S3_Backdrop"


def package_census():
    def names(packages):
        return sorted(str(p.get_name()).split(".", 1)[0] for p in packages)
    return {
        "maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
        "content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    }


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def project_file(*parts):
    root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.normpath(os.path.join(root, *parts))


def build_inventory():
    wave_root = project_file("DerivedAssets", "FlatV3", "Scene3", "waves")
    backdrop_root = project_file("DerivedAssets", "FlatV3", "Scene3", "backdrop", "textures")
    sources = []
    destinations = []
    for name in WAVE_NAMES:
        folder = os.path.join(wave_root, name)
        mesh_name = "SM_FlatV3_" + name
        sources.append({"kind": "mesh", "owner": name,
                        "path": os.path.join(folder, mesh_name + ".fbx")})
        destinations.append({"kind": "mesh", "owner": name,
                             "path": MESH_ROOT + "/" + mesh_name})
        for texture_kind in TEXTURE_KINDS:
            texture_name = "T_%s_%s" % (name, texture_kind)
            sources.append({"kind": texture_kind, "owner": name,
                            "path": os.path.join(folder, texture_name + ".png")})
            destinations.append({"kind": "texture", "owner": name,
                                 "texture_kind": texture_kind,
                                 "path": "%s/%s/%s" % (TEXTURE_ROOT, name.replace("S3_", ""), texture_name)})
        sources.append({"kind": "mi_params", "owner": name,
                        "path": os.path.join(folder, name + "_mi_params.json")})
        for slot in ("Front", "Flap"):
            destinations.append({"kind": "material_instance", "owner": name,
                                 "slot": slot,
                                 "path": "%s/MI_%s_%s" % (INSTANCE_ROOT, name, slot)})

    for texture_kind in TEXTURE_KINDS:
        texture_name = "T_%s_%s" % (BACKDROP_NAME, texture_kind)
        sources.append({"kind": texture_kind, "owner": BACKDROP_NAME,
                        "path": os.path.join(backdrop_root, texture_name + ".png")})
        destinations.append({"kind": "texture", "owner": BACKDROP_NAME,
                             "texture_kind": texture_kind,
                             "path": TEXTURE_ROOT + "/" + texture_name})
    sources.append({"kind": "mi_params", "owner": BACKDROP_NAME,
                    "path": project_file("DerivedAssets", "FlatV3", "Scene3", "backdrop", "mi_params.json")})
    sources.append({"kind": "mesh", "owner": BACKDROP_NAME,
                    "path": project_file("DerivedAssets", "FlatV3", "Scene3", "backdrop",
                                         "SM_FlatV3_S3_Backdrop.fbx")})
    destinations.append({"kind": "material_instance", "owner": BACKDROP_NAME,
                         "slot": "Front", "path": BACKDROP_MI})
    destinations.append({"kind": "mesh", "owner": BACKDROP_NAME,
                         "path": BACKDROP_MESH})

    for row in sources:
        row["exists"] = os.path.isfile(row["path"])
        row["sha256"] = sha256_file(row["path"]) if row["exists"] else None
    for row in destinations:
        row["exists"] = bool(unreal.EditorAssetLibrary.does_asset_exist(row["path"]))
    parents = []
    for slot in MI_SLOTS:
        path = PARENTS[slot]
        parents.append({
            "slot": slot,
            "path": path,
            "exists": bool(path and unreal.EditorAssetLibrary.does_asset_exist(path)),
            "declared": path is not None,
        })
    return {"sources": sources, "destinations": destinations, "parents": parents}


def inventory_issues(inventory):
    issues = []
    missing_sources = [row["path"] for row in inventory["sources"] if not row["exists"]]
    existing_destinations = [row["path"] for row in inventory["destinations"] if row["exists"]]
    missing_parents = [row["slot"] for row in inventory["parents"] if not row["exists"]]
    if missing_sources:
        issues.append({"reason": "MISSING_SOURCES", "values": missing_sources})
    if existing_destinations:
        issues.append({"reason": "DESTINATIONS_EXIST", "values": existing_destinations})
    if missing_parents:
        issues.append({"reason": "MISSING_OR_UNSPECIFIED_PARENTS", "values": missing_parents})
    return issues


def log_inventory(run, inventory):
    for row in inventory["destinations"]:
        unreal.log("S3_FLATS_IMPORT_DEST|run=%s|exists=%d|kind=%s|path=%s" %
                   (run, int(row["exists"]), row["kind"], row["path"]))
    for row in inventory["sources"]:
        unreal.log("S3_FLATS_IMPORT_SOURCE|run=%s|exists=%d|sha256=%s|path=%s" %
                   (run, int(row["exists"]), row["sha256"] or "MISSING", row["path"]))
    for row in inventory["parents"]:
        unreal.log("S3_FLATS_IMPORT_PARENT|run=%s|slot=%s|exists=%d|path=%s" %
                   (run, row["slot"], int(row["exists"]), row["path"] or "UNSPECIFIED_IN_IMPORT_PLAN"))


def assert_context(run):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    world_path = world.get_outermost().get_name() if world else None
    if world_path != EXPECTED_WORLD:
        raise RuntimeError("WRONG_WORLD|world=%s" % world_path)
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE_OR_SIE_ACTIVE")
    census = package_census()
    if census["maps"] or census["content"]:
        raise RuntimeError("DIRTY_BEFORE|census=" + json.dumps(census, sort_keys=True))


def import_task(source, destination_path, destination_name, options=None):
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", source)
    task.set_editor_property("destination_path", destination_path)
    task.set_editor_property("destination_name", destination_name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", False)
    task.set_editor_property("save", False)
    if options is not None:
        task.set_editor_property("options", options)
    return task


def fbx_options():
    options = unreal.FbxImportUI()
    options.set_editor_property("import_mesh", True)
    options.set_editor_property("import_as_skeletal", False)
    options.set_editor_property("import_materials", False)
    options.set_editor_property("import_textures", False)
    options.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)
    data = options.get_editor_property("static_mesh_import_data")
    # UE 5.8: import_mesh_lods is not on FbxImportUI (run 172901); it lives on the mesh import data.
    data.set_editor_property("import_mesh_lods", True)
    data.set_editor_property("import_translation", unreal.Vector(0.0, 0.0, 0.0))
    data.set_editor_property("import_rotation", unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    data.set_editor_property("import_uniform_scale", 1.0)
    data.set_editor_property("combine_meshes", False)
    data.set_editor_property("generate_lightmap_u_vs", False)
    data.set_editor_property("auto_generate_collision", False)
    data.set_editor_property("convert_scene", True)
    data.set_editor_property("force_front_x_axis", False)
    data.set_editor_property("bake_pivot_in_vertex", False)
    data.set_editor_property("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS)
    data.set_editor_property("vertex_color_import_option", unreal.VertexColorImportOption.REPLACE)
    return options


def configure_texture(texture, kind):
    texture.modify()
    texture.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_FROM_TEXTURE_GROUP)
    if kind == "SkinColor":
        texture.set_editor_property("srgb", True)
        texture.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_BC7)
    elif kind == "SkinMask":
        texture.set_editor_property("srgb", False)
        texture.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
    elif kind == "SkinNormal":
        texture.set_editor_property("srgb", False)
        texture.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
        texture.set_editor_property("flip_green_channel", False)
    else:
        raise RuntimeError("unknown texture kind %s" % kind)


def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def make_instance(path, parent):
    folder, name = path.rsplit("/", 1)
    instance = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, folder, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    if not isinstance(instance, unreal.MaterialInstanceConstant):
        raise RuntimeError("MI_CREATE_FAILED|path=" + path)
    instance.modify()
    unreal.MaterialEditingLibrary.set_material_instance_parent(instance, parent)
    return instance


def set_skin(instance, textures, scalars):
    for parameter, texture in textures.items():
        unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(instance, parameter, texture)
    for parameter, value in scalars.items():
        unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(instance, parameter, float(value))
    unreal.MaterialEditingLibrary.update_material_instance(instance)


def uv_ranges(mesh, lod):
    desc = mesh.get_static_mesh_description(lod)
    if desc is None:
        raise RuntimeError("MESH_DESCRIPTION_MISSING|mesh=%s|lod=%d" % (mesh.get_path_name(), lod))
    result = []
    for channel in (0, 1):
        us, vs = [], []
        for index in range(desc.get_vertex_instance_count()):
            uv = desc.get_vertex_instance_uv(unreal.VertexInstanceID(index), channel)
            us.append(float(uv.x)); vs.append(float(uv.y))
        if not us:
            raise RuntimeError("UV_CHANNEL_EMPTY|mesh=%s|lod=%d|channel=%d" %
                               (mesh.get_path_name(), lod, channel))
        result.append({"u": [min(us), max(us)], "v": [min(vs), max(vs)]})
    return result


def front_direction(mesh):
    desc = mesh.get_static_mesh_description(0)
    normals = []
    for index in range(desc.get_polygon_count()):
        polygon = unreal.PolygonID(index)
        group = desc.get_polygon_polygon_group(polygon)
        if int(group.id_value) != 0:
            continue
        perimeter = list(_polygon_instances(desc, polygon))
        if len(perimeter) < 3:
            continue
        points = []
        for vertex_instance in perimeter[:3]:
            vertex = desc.get_vertex_instance_vertex(vertex_instance)
            points.append(desc.get_vertex_position(vertex))
        a = points[1] - points[0]
        b = points[2] - points[0]
        cross = a.cross(b)
        length = (cross.x * cross.x + cross.y * cross.y + cross.z * cross.z) ** 0.5
        if length <= 1e-9:
            continue
        normal = unreal.Vector(cross.x / length, cross.y / length, cross.z / length)
        normals.append(normal)
    if not normals:
        raise RuntimeError("FRONT_POLYGONS_MISSING|mesh=" + mesh.get_path_name())
    mean = unreal.Vector(sum(n.x for n in normals),
                         sum(n.y for n in normals),
                         sum(n.z for n in normals))
    length = (mean.x * mean.x + mean.y * mean.y + mean.z * mean.z) ** 0.5
    if length <= 1e-9:
        raise RuntimeError("FRONT_NORMAL_MEAN_DEGENERATE|mesh=" + mesh.get_path_name())
    mean = unreal.Vector(mean.x / length, mean.y / length, mean.z / length)
    return [float(mean.x), float(mean.y), float(mean.z)]


def static_mesh_socket_names(mesh):
    # The Sockets property is protected in UE 5.8 Python. FBX-imported sockets
    # have the default empty tag, so the public BlueprintPure query is the
    # read-only enumeration route for these newly imported meshes.
    return sorted(str(socket.get_editor_property("socket_name"))
                  for socket in mesh.get_sockets_by_tag(""))


def least_squares_slope(independent, dependent, label):
    if len(independent) != len(dependent) or len(independent) < 3:
        raise RuntimeError("REGRESSION_INPUT_INVALID|label=%s|count=%d" %
                           (label, len(independent)))
    mean_x = sum(independent) / len(independent)
    mean_y = sum(dependent) / len(dependent)
    denominator = sum((value - mean_x) ** 2 for value in independent)
    if denominator <= 1e-9:
        raise RuntimeError("REGRESSION_AXIS_DEGENERATE|label=" + label)
    return sum((x - mean_x) * (y - mean_y)
               for x, y in zip(independent, dependent)) / denominator


def wave_front_orientation(mesh):
    # Front section (slot 0) UV0 must run u -> +Y (screen-right from -X) and v DOWN (dv/dZ < 0),
    # like every upright wing in Unreal (Docs/WingMateriality.md:407). Run 181644 found the
    # backdrop V-up; W&T re-exported all flats (1 Oct). Both LODs.
    report = {}
    for lod in (0, 1):
        section = unreal.ProceduralMeshLibrary.get_section_from_static_mesh(mesh, lod, 0)
        vertices, uvs = section[0], section[3]
        if len(vertices) < 3 or len(vertices) != len(uvs):
            raise RuntimeError("WAVE_FRONT_READBACK_INVALID|mesh=%s|lod=%d" % (mesh.get_path_name(), lod))
        du_dy = least_squares_slope([float(p.y) for p in vertices], [float(uv.x) for uv in uvs], "du_dY")
        dv_dz = least_squares_slope([float(p.z) for p in vertices], [float(uv.y) for uv in uvs], "dv_dZ")
        report[lod] = {"du_dY": du_dy, "dv_dZ": dv_dz}
        if du_dy <= 0.0 or dv_dz >= 0.0:
            raise RuntimeError("WAVE_FRONT_UV_ORIENTATION_MISMATCH|mesh=%s|lod=%d|report=%s"
                               % (mesh.get_path_name(), lod, json.dumps(report[lod], sort_keys=True)))
    unreal.log("S3_WAVE_FRONT_UV|mesh=%s|%s" % (mesh.get_path_name(), json.dumps(report, sort_keys=True)))
    return report


def backdrop_handedness(mesh, validate=True):
    section = unreal.ProceduralMeshLibrary.get_section_from_static_mesh(mesh, 0, 0)
    if not isinstance(section, tuple) or len(section) < 5:
        raise RuntimeError("BACKDROP_SECTION_READBACK_INVALID|mesh=" + mesh.get_path_name())
    vertices, triangles, normals, uvs, tangents = section[:5]
    if len(vertices) < 3 or len(vertices) != len(uvs) or len(vertices) != len(normals):
        raise RuntimeError("BACKDROP_SECTION_ARRAY_MISMATCH|vertices=%d|uvs=%d|normals=%d" %
                           (len(vertices), len(uvs), len(normals)))
    ys = [float(point.y) for point in vertices]
    zs = [float(point.z) for point in vertices]
    us = [float(uv.x) for uv in uvs]
    vs = [float(uv.y) for uv in uvs]
    normal = [sum(float(value.x) for value in normals) / len(normals),
              sum(float(value.y) for value in normals) / len(normals),
              sum(float(value.z) for value in normals) / len(normals)]
    length = sum(value * value for value in normal) ** 0.5
    if length <= 1e-9:
        raise RuntimeError("BACKDROP_NORMAL_DEGENERATE")
    normal = [value / length for value in normal]
    report = {
        "bounds_y_cm": [min(ys), max(ys)],
        "bounds_z_cm": [min(zs), max(zs)],
        "du_dY": least_squares_slope(ys, us, "du_dY"),
        "dv_dZ": least_squares_slope(zs, vs, "dv_dZ"),
        "normal": normal,
        "vertices": len(vertices),
        "triangles": len(triangles) // 3,
    }
    if validate:
        if (abs(report["bounds_y_cm"][0] + 1000.0) > 1.0 or
                abs(report["bounds_y_cm"][1] - 1000.0) > 1.0 or
                abs(report["bounds_z_cm"][0]) > 1.0 or
                abs(report["bounds_z_cm"][1] - 3000.0) > 1.0):
            raise RuntimeError("BACKDROP_BOUNDS_MISMATCH|report=" +
                               json.dumps(report, sort_keys=True))
        if report["du_dY"] <= 0.0 or report["dv_dZ"] >= 0.0:
            raise RuntimeError("BACKDROP_UV_HANDEDNESS_MISMATCH|report=" +
                               json.dumps(report, sort_keys=True))
        if normal[0] > -0.99 or abs(normal[1]) > 0.02 or abs(normal[2]) > 0.02:
            raise RuntimeError("BACKDROP_NORMAL_MISMATCH|report=" +
                               json.dumps(report, sort_keys=True))
    return report


def verify_texture(texture, kind):
    if texture.get_editor_property("mip_gen_settings") == unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS:
        raise RuntimeError("NO_MIPS|texture=" + texture.get_path_name())
    expected_srgb = kind == "SkinColor"
    if bool(texture.get_editor_property("srgb")) != expected_srgb:
        raise RuntimeError("SRGB_MISMATCH|texture=" + texture.get_path_name())
    expected = {
        "SkinColor": unreal.TextureCompressionSettings.TC_BC7,
        "SkinMask": unreal.TextureCompressionSettings.TC_MASKS,
        "SkinNormal": unreal.TextureCompressionSettings.TC_NORMALMAP,
    }[kind]
    if texture.get_editor_property("compression_settings") != expected:
        raise RuntimeError("COMPRESSION_MISMATCH|texture=" + texture.get_path_name())
    if kind == "SkinNormal" and bool(texture.get_editor_property("flip_green_channel")):
        raise RuntimeError("NORMAL_GREEN_FLIPPED|texture=" + texture.get_path_name())


def _polygon_instances(desc, polygon):
    # UE 5.8 StaticMeshDescription has no get_polygon_perimeter_vertex_instances (probe 22:07).
    for name in ("get_polygon_vertex_instances", "get_polygon_perimeter_vertex_instances"):
        method = getattr(desc, name, None)
        if method is not None:
            return list(method(polygon))
    raise RuntimeError("NO_POLYGON_VERTEX_INSTANCE_API")


def verify_uv1_metres(mesh, lod):
    desc = mesh.get_static_mesh_description(lod)
    if desc is None:
        raise RuntimeError("MESH_DESCRIPTION_MISSING|mesh=%s|lod=%d" % (mesh.get_path_name(), lod))
    front_edges = 0
    worst = None
    for index in range(desc.get_polygon_count()):
        polygon = unreal.PolygonID(index)
        group = int(desc.get_polygon_polygon_group(polygon).id_value)
        perimeter = list(_polygon_instances(desc, polygon))
        for a, b in zip(perimeter, perimeter[1:] + perimeter[:1]):
            pa = desc.get_vertex_position(desc.get_vertex_instance_vertex(a))
            pb = desc.get_vertex_position(desc.get_vertex_instance_vertex(b))
            ua = desc.get_vertex_instance_uv(a, 1)
            ub = desc.get_vertex_instance_uv(b, 1)
            d_pos = ((pa.x - pb.x) ** 2 + (pa.y - pb.y) ** 2 + (pa.z - pb.z) ** 2) ** 0.5 / 100.0
            d_uv = ((ua.x - ub.x) ** 2 + (ua.y - ub.y) ** 2) ** 0.5
            excess = d_uv - d_pos
            if group == 0:
                front_edges += 1
                error = abs(excess)
            else:
                error = max(0.0, excess)
            if worst is None or error > worst[0]:
                worst = (error, group, index, d_pos, d_uv)
    if front_edges == 0:
        raise RuntimeError("UV1_NO_FRONT_EDGES|mesh=%s|lod=%d" % (mesh.get_path_name(), lod))
    if worst is not None and worst[0] > 0.005:
        raise RuntimeError("UV1_METRE_SCALE_MISMATCH|mesh=%s|lod=%d|worst_error_m=%.4f|slot_group=%d|polygon=%d|d_pos_m=%.4f|d_uv=%.4f"
                           % (mesh.get_path_name(), lod, worst[0], worst[1], worst[2], worst[3], worst[4]))
    unreal.log("S3_FLATS_UV1|mesh=%s|lod=%d|front_edges=%d|worst_error_m=%.5f"
               % (mesh.get_path_name(), lod, front_edges, worst[0] if worst else 0.0))


def verify_mesh(mesh, expected_dimensions_m):
    box = mesh.get_bounding_box()
    dimensions = [float(box.max.x - box.min.x), float(box.max.y - box.min.y), float(box.max.z - box.min.z)]
    expected = [float(value) * 100.0 for value in expected_dimensions_m]
    if any(abs(a - b) > 1.0 for a, b in zip(dimensions, expected)):
        raise RuntimeError("DIMENSIONS_MISMATCH|mesh=%s|actual=%s|expected=%s" %
                           (mesh.get_path_name(), dimensions, expected))
    if abs(float(box.min.z)) > 1.0 or abs(float(box.min.y + box.max.y)) > 2.0:
        raise RuntimeError("ORIGIN_MISMATCH|mesh=" + mesh.get_path_name())
    slots = [str(row.get_editor_property("material_slot_name"))
             for row in mesh.get_editor_property("static_materials")]
    if slots != list(MI_SLOTS):
        raise RuntimeError("SLOT_MISMATCH|mesh=%s|slots=%s" % (mesh.get_path_name(), slots))
    if unreal.EditorStaticMeshLibrary.get_lod_count(mesh) != 2:
        raise RuntimeError("LOD_COUNT_MISMATCH|mesh=" + mesh.get_path_name())
    # UV1 is a metre-space projection of position on every slot (W&T validation
    # "uv1_metres_all_slots", max error 0 m). A whole-mesh span check is wrong for a four-slot
    # board (run 180401: the edge faces lay their metre UVs along the width, v span 14.3 m).
    # Per edge instead: Front-slot (group 0, planar) |dUV1| == |dPos| within 0.5 cm; every slot
    # |dUV1| <= |dPos| + 0.5 cm. Catches 0-1-normalised or mis-scaled UV1.
    for lod in (0, 1):
        verify_uv1_metres(mesh, lod)
    wave_front_orientation(mesh)
    try:
        sockets = static_mesh_socket_names(mesh)
    except Exception as exc:
        raise RuntimeError("SOCKET_READBACK_UNAVAILABLE|mesh=%s|detail=%s" % (mesh.get_path_name(), exc))
    if sockets:
        raise RuntimeError("SOCKETS_PRESENT|mesh=%s|count=%d" % (mesh.get_path_name(), len(sockets)))
    direction = front_direction(mesh)
    if direction[0] > -0.99 or abs(direction[1]) > 0.02 or abs(direction[2]) > 0.02:
        raise RuntimeError("FRONT_DIRECTION_MISMATCH|mesh=%s|direction=%s" %
                           (mesh.get_path_name(), direction))
    settings = mesh.get_editor_property("nanite_settings")
    if bool(settings.get_editor_property("enabled")):
        raise RuntimeError("NANITE_ENABLED|mesh=" + mesh.get_path_name())
    return {"dimensions_cm": dimensions, "front_direction": direction, "uv_ranges": ranges}


def verify_backdrop_mesh(mesh):
    box = mesh.get_bounding_box()
    if (abs(float(box.min.y) + 1000.0) > 1.0 or abs(float(box.max.y) - 1000.0) > 1.0 or
            abs(float(box.min.z)) > 1.0 or abs(float(box.max.z) - 3000.0) > 1.0 or
            abs(float(box.min.x + box.max.x)) > 1.0):
        raise RuntimeError("BACKDROP_BOUNDS_MISMATCH|mesh=%s|bounds=%s" %
                           (mesh.get_path_name(), [vector for vector in
                                                  ([box.min.x, box.min.y, box.min.z],
                                                   [box.max.x, box.max.y, box.max.z])]))
    slots = [str(row.get_editor_property("material_slot_name"))
             for row in mesh.get_editor_property("static_materials")]
    if slots != ["Front"]:
        raise RuntimeError("BACKDROP_SLOT_MISMATCH|slots=" + json.dumps(slots))
    ranges = uv_ranges(mesh, 0)
    if (abs(ranges[0]["u"][0]) > 0.001 or abs(ranges[0]["u"][1] - 1.0) > 0.001 or
            abs(ranges[0]["v"][0]) > 0.001 or abs(ranges[0]["v"][1] - 1.0) > 0.001 or
            abs((ranges[1]["u"][1] - ranges[1]["u"][0]) - 20.0) > 0.02 or
            abs((ranges[1]["v"][1] - ranges[1]["v"][0]) - 30.0) > 0.02):
        raise RuntimeError("BACKDROP_UV_RANGE_MISMATCH|ranges=" + json.dumps(ranges))
    if static_mesh_socket_names(mesh):
        raise RuntimeError("BACKDROP_SOCKETS_PRESENT")
    settings = mesh.get_editor_property("nanite_settings")
    if bool(settings.get_editor_property("enabled")):
        raise RuntimeError("NANITE_ENABLED|mesh=" + mesh.get_path_name())
    return {"uv_ranges": ranges, "handedness": backdrop_handedness(mesh)}


def gate_imported_mesh_lods(run, destination_by):
    """Revision 3's immediate, pre-texture Interchange result gate."""
    expected_lods = {owner: 2 for owner in WAVE_NAMES}
    expected_lods[BACKDROP_NAME] = 1
    report = {}
    failures = []
    for owner in WAVE_NAMES + (BACKDROP_NAME,):
        path = destination_by[(owner, "mesh")]
        mesh = unreal.EditorAssetLibrary.load_asset(path)
        if not isinstance(mesh, unreal.StaticMesh):
            failures.append({"owner": owner, "path": path, "reason": "NOT_STATIC_MESH"})
            continue
        lods = int(mesh.get_num_lods())
        report[owner] = {"path": path, "lods": lods}
        if lods != expected_lods[owner]:
            failures.append({
                "owner": owner,
                "path": path,
                "reason": "LOD_COUNT_MISMATCH",
                "actual": lods,
                "expected": expected_lods[owner],
            })

    stray_lod_assets = []
    for asset_path in unreal.EditorAssetLibrary.list_assets(
            MESH_ROOT, recursive=True, include_folder=False):
        asset_name = str(asset_path).rsplit("/", 1)[-1].split(".", 1)[0]
        if asset_name.endswith(("_LOD0", "_LOD1")):
            stray_lod_assets.append(str(asset_path))
    stray_lod_assets.sort()
    if stray_lod_assets:
        failures.append({"reason": "STRAY_LOD_ASSETS", "values": stray_lod_assets})

    details = {
        "meshes": report,
        "stray_lod_assets": stray_lod_assets,
    }
    if failures:
        details["failures"] = failures
        unreal.log_error(
            "S3_FLATS_IMPORT_STOPPED|run=%s|reason=LOD_GATE|details=%s|census=%s" %
            (run, json.dumps(details, separators=(",", ":"), sort_keys=True),
             json.dumps(package_census(), separators=(",", ":"), sort_keys=True)))
        return False
    unreal.log("S3_FLATS_IMPORT_LOD_GATE|run=%s|meshes=7|wave_lods=2|backdrop_lods=1|stray_lod_assets=0" % run)
    return True


def asset_package(value):
    if value is None:
        return None
    return str(value.get_path_name()).split(".", 1)[0]


def serialized_texture_parameters(instance):
    return {
        str(value.get_editor_property("parameter_info").get_editor_property("name")):
        asset_package(value.get_editor_property("parameter_value"))
        for value in instance.get_editor_property("texture_parameter_values")
    }


def serialized_scalar_parameters(instance):
    return {
        str(value.get_editor_property("parameter_info").get_editor_property("name")):
        float(value.get_editor_property("parameter_value"))
        for value in instance.get_editor_property("scalar_parameter_values")
    }


def add_failure(failures, gate, asset, **details):
    row = {"gate": gate, "asset": asset}
    row.update(details)
    failures.append(row)


def paths_match(actual, expected):
    return actual == expected


def verify_existing_assets(run, inventory, emit_marker=True):
    """Read back every imported value without setters or saves; collect all failures."""
    failures = []
    before = package_census()
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    world_path = world.get_outermost().get_name() if world else None
    if world_path != EXPECTED_WORLD:
        add_failure(failures, "WORLD", EXPECTED_WORLD, actual=world_path)
    if editor.get_game_world() is not None:
        add_failure(failures, "PIE_OR_SIE", EXPECTED_WORLD, actual="ACTIVE")

    destination_by = {
        (row["owner"], row.get("texture_kind", row.get("slot", row["kind"]))): row["path"]
        for row in inventory["destinations"]
    }
    source_by = {(row["owner"], row["kind"]): row["path"] for row in inventory["sources"]}
    expected_paths = sorted(row["path"] for row in inventory["destinations"])
    validation = load_json(project_file(
        "DerivedAssets", "FlatV3", "Scene3", "waves", "validation_summary.json"))

    loaded_meshes = {}
    expected_lods = {owner: 2 for owner in WAVE_NAMES}
    expected_lods[BACKDROP_NAME] = 1
    for owner in WAVE_NAMES + (BACKDROP_NAME,):
        path = destination_by[(owner, "mesh")]
        asset = unreal.EditorAssetLibrary.load_asset(path)
        if not isinstance(asset, unreal.StaticMesh):
            add_failure(failures, "LOD_GATE", path, expected="StaticMesh", actual=type(asset).__name__)
            continue
        loaded_meshes[owner] = asset
        try:
            actual_lods = int(asset.get_num_lods())
            if actual_lods != expected_lods[owner]:
                add_failure(failures, "LOD_GATE", path,
                            expected=expected_lods[owner], actual=actual_lods)
        except Exception as exc:
            add_failure(failures, "LOD_GATE", path, exception=str(exc))

    try:
        stray_lod_assets = []
        for path in unreal.EditorAssetLibrary.list_assets(
                MESH_ROOT, recursive=True, include_folder=False):
            name = str(path).rsplit("/", 1)[-1].split(".", 1)[0]
            if name.endswith(("_LOD0", "_LOD1")):
                stray_lod_assets.append(str(path))
        if stray_lod_assets:
            add_failure(failures, "LOD_GATE_STRAY_ASSETS", MESH_ROOT,
                        actual=sorted(stray_lod_assets), expected=[])
    except Exception as exc:
        add_failure(failures, "LOD_GATE_STRAY_ASSETS", MESH_ROOT, exception=str(exc))

    for owner in WAVE_NAMES:
        mesh = loaded_meshes.get(owner)
        if mesh is None:
            continue
        path = destination_by[(owner, "mesh")]
        expected_dimensions = [
            float(value) * 100.0
            for value in validation["assets"][owner]["fbx_validation"]["dimensions_m"]
        ]
        try:
            box = mesh.get_bounding_box()
            actual_dimensions = [float(box.max.x - box.min.x),
                                 float(box.max.y - box.min.y),
                                 float(box.max.z - box.min.z)]
            if any(abs(actual - expected) > 1.0
                   for actual, expected in zip(actual_dimensions, expected_dimensions)):
                add_failure(failures, "DIMENSIONS", path,
                            expected=expected_dimensions, actual=actual_dimensions)
            origin_error = {
                "y_centre_cm": float(box.min.y + box.max.y),
                "z_min_cm": float(box.min.z),
            }
            if (abs(origin_error["y_centre_cm"]) > 2.0 or
                    abs(origin_error["z_min_cm"]) > 1.0):
                add_failure(failures, "ORIGIN", path,
                            expected={"y_centre_cm": 0.0, "z_min_cm": 0.0},
                            actual=origin_error)
        except Exception as exc:
            add_failure(failures, "DIMENSIONS_OR_ORIGIN", path, exception=str(exc))

        try:
            static_materials = list(mesh.get_editor_property("static_materials"))
            slots = [str(row.get_editor_property("material_slot_name"))
                     for row in static_materials]
            if slots != list(MI_SLOTS):
                add_failure(failures, "SLOTS", path, expected=list(MI_SLOTS), actual=slots)
            expected_materials = [
                destination_by[(owner, "Front")],
                destination_by[(owner, "Flap")],
                PARENTS["Timber"],
                PARENTS["Edge"],
            ]
            actual_materials = [asset_package(row.get_editor_property("material_interface"))
                                for row in static_materials]
            if actual_materials != expected_materials:
                add_failure(failures, "SLOT_MATERIALS", path,
                            expected=expected_materials, actual=actual_materials)
        except Exception as exc:
            add_failure(failures, "SLOTS", path, exception=str(exc))

        for lod in (0, 1):
            try:
                verify_uv1_metres(mesh, lod)
            except Exception as exc:
                add_failure(failures, "UV1", path, lod=lod, exception=str(exc))
        try:
            wave_front_orientation(mesh)
        except Exception as exc:
            add_failure(failures, "WAVE_FRONT_UV_ORIENTATION", path, exception=str(exc))

        try:
            sockets = static_mesh_socket_names(mesh)
            if sockets:
                add_failure(failures, "SOCKETS", path, expected=0, actual=len(sockets))
        except Exception as exc:
            add_failure(failures, "SOCKETS", path, exception=str(exc))

        try:
            expected_triangles = int(
                validation["assets"][owner]["fbx_validation"]["checks"]
                ["lod1_without_frame_hardware"]["lod1_triangles"])
            lod1 = mesh.get_static_mesh_description(1)
            if lod1 is None:
                raise RuntimeError("LOD1_MESH_DESCRIPTION_MISSING")
            actual_triangles = int(lod1.get_triangle_count())
            if actual_triangles != expected_triangles:
                add_failure(failures, "LOD1_BOARD_ONLY", path,
                            expected_triangles=expected_triangles,
                            actual_triangles=actual_triangles)
        except Exception as exc:
            add_failure(failures, "LOD1_BOARD_ONLY", path, exception=str(exc))

        try:
            direction = front_direction(mesh)
            if direction[0] > -0.99 or abs(direction[1]) > 0.02 or abs(direction[2]) > 0.02:
                add_failure(failures, "FRONT_DIRECTION", path,
                            expected=[-1.0, 0.0, 0.0], actual=direction)
        except Exception as exc:
            add_failure(failures, "FRONT_DIRECTION", path, exception=str(exc))

        try:
            if bool(mesh.get_editor_property("nanite_settings").get_editor_property("enabled")):
                add_failure(failures, "NANITE", path, expected=False, actual=True)
        except Exception as exc:
            add_failure(failures, "NANITE", path, exception=str(exc))

    backdrop_mesh = loaded_meshes.get(BACKDROP_NAME)
    if backdrop_mesh is not None:
        try:
            box = backdrop_mesh.get_bounding_box()
            actual = {
                "x_centre_cm": float(box.min.x + box.max.x),
                "y_min_cm": float(box.min.y),
                "y_max_cm": float(box.max.y),
                "z_min_cm": float(box.min.z),
                "z_max_cm": float(box.max.z),
            }
            if (abs(actual["x_centre_cm"]) > 1.0 or
                    abs(actual["y_min_cm"] + 1000.0) > 1.0 or
                    abs(actual["y_max_cm"] - 1000.0) > 1.0 or
                    abs(actual["z_min_cm"]) > 1.0 or
                    abs(actual["z_max_cm"] - 3000.0) > 1.0):
                add_failure(failures, "BACKDROP_DIMENSIONS_OR_ORIGIN", BACKDROP_MESH,
                            expected={"x_centre_cm": 0.0, "y_min_cm": -1000.0,
                                      "y_max_cm": 1000.0, "z_min_cm": 0.0,
                                      "z_max_cm": 3000.0}, actual=actual)
        except Exception as exc:
            add_failure(failures, "BACKDROP_DIMENSIONS_OR_ORIGIN", BACKDROP_MESH,
                        exception=str(exc))
        try:
            static_materials = list(backdrop_mesh.get_editor_property("static_materials"))
            slots = [str(row.get_editor_property("material_slot_name"))
                     for row in static_materials]
            if slots != ["Front"]:
                add_failure(failures, "SLOTS", BACKDROP_MESH,
                            expected=["Front"], actual=slots)
            actual_materials = [asset_package(row.get_editor_property("material_interface"))
                                for row in static_materials]
            if actual_materials != [BACKDROP_MI]:
                add_failure(failures, "SLOT_MATERIALS", BACKDROP_MESH,
                            expected=[BACKDROP_MI], actual=actual_materials)
        except Exception as exc:
            add_failure(failures, "SLOTS", BACKDROP_MESH, exception=str(exc))
        try:
            ranges = uv_ranges(backdrop_mesh, 0)
            if (abs(ranges[0]["u"][0]) > 0.001 or
                    abs(ranges[0]["u"][1] - 1.0) > 0.001 or
                    abs(ranges[0]["v"][0]) > 0.001 or
                    abs(ranges[0]["v"][1] - 1.0) > 0.001 or
                    abs((ranges[1]["u"][1] - ranges[1]["u"][0]) - 20.0) > 0.02 or
                    abs((ranges[1]["v"][1] - ranges[1]["v"][0]) - 30.0) > 0.02):
                add_failure(failures, "BACKDROP_UV", BACKDROP_MESH,
                            expected={"uv0": [[0.0, 1.0], [0.0, 1.0]],
                                      "uv1_span": [20.0, 30.0]}, actual=ranges)
        except Exception as exc:
            add_failure(failures, "BACKDROP_UV", BACKDROP_MESH, exception=str(exc))
        try:
            sockets = static_mesh_socket_names(backdrop_mesh)
            if sockets:
                add_failure(failures, "SOCKETS", BACKDROP_MESH,
                            expected=0, actual=len(sockets))
        except Exception as exc:
            add_failure(failures, "SOCKETS", BACKDROP_MESH, exception=str(exc))
        try:
            if bool(backdrop_mesh.get_editor_property("nanite_settings").get_editor_property("enabled")):
                add_failure(failures, "NANITE", BACKDROP_MESH,
                            expected=False, actual=True)
        except Exception as exc:
            add_failure(failures, "NANITE", BACKDROP_MESH, exception=str(exc))
        try:
            hand = backdrop_handedness(backdrop_mesh, validate=False)
            unreal.log("S3_BACKDROP_HANDEDNESS|run=%s|du_dY=%.9g|dv_dZ=%.9g|normal=%s" %
                       (run, hand["du_dY"], hand["dv_dZ"],
                        ",".join("%.6f" % value for value in hand["normal"])))
            if (abs(hand["bounds_y_cm"][0] + 1000.0) > 1.0 or
                    abs(hand["bounds_y_cm"][1] - 1000.0) > 1.0 or
                    abs(hand["bounds_z_cm"][0]) > 1.0 or
                    abs(hand["bounds_z_cm"][1] - 3000.0) > 1.0):
                add_failure(failures, "BACKDROP_SECTION_BOUNDS", BACKDROP_MESH,
                            expected={"bounds_y_cm": [-1000.0, 1000.0],
                                      "bounds_z_cm": [0.0, 3000.0]},
                            actual={"bounds_y_cm": hand["bounds_y_cm"],
                                    "bounds_z_cm": hand["bounds_z_cm"]})
            if hand["du_dY"] <= 0.0 or hand["dv_dZ"] >= 0.0:
                add_failure(failures, "BACKDROP_HANDEDNESS", BACKDROP_MESH,
                            expected={"du_dY": ">0", "dv_dZ": "<0"},
                            actual={"du_dY": hand["du_dY"], "dv_dZ": hand["dv_dZ"]})
            normal = hand["normal"]
            if normal[0] > -0.99 or abs(normal[1]) > 0.02 or abs(normal[2]) > 0.02:
                add_failure(failures, "FRONT_DIRECTION", BACKDROP_MESH,
                            expected=[-1.0, 0.0, 0.0], actual=normal)
        except Exception as exc:
            add_failure(failures, "BACKDROP_HANDEDNESS", BACKDROP_MESH, exception=str(exc))

    textures = {}
    for owner in WAVE_NAMES + (BACKDROP_NAME,):
        textures[owner] = {}
        for kind in TEXTURE_KINDS:
            path = destination_by[(owner, kind)]
            texture = unreal.EditorAssetLibrary.load_asset(path)
            if not isinstance(texture, unreal.Texture2D):
                add_failure(failures, "TEXTURE_CLASS", path,
                            expected="Texture2D", actual=type(texture).__name__)
                continue
            textures[owner][kind] = texture
            try:
                mip_setting = texture.get_editor_property("mip_gen_settings")
                if mip_setting == unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS:
                    add_failure(failures, "TEXTURE_MIPS", path,
                                expected="FULL", actual="NO_MIPMAPS")
                expected_srgb = kind == "SkinColor"
                actual_srgb = bool(texture.get_editor_property("srgb"))
                if actual_srgb != expected_srgb:
                    add_failure(failures, "TEXTURE_SRGB", path,
                                expected=expected_srgb, actual=actual_srgb)
                expected_compression = {
                    "SkinColor": unreal.TextureCompressionSettings.TC_BC7,
                    "SkinMask": unreal.TextureCompressionSettings.TC_MASKS,
                    "SkinNormal": unreal.TextureCompressionSettings.TC_NORMALMAP,
                }[kind]
                actual_compression = texture.get_editor_property("compression_settings")
                if actual_compression != expected_compression:
                    add_failure(failures, "TEXTURE_COMPRESSION", path,
                                expected=str(expected_compression), actual=str(actual_compression))
                if kind == "SkinNormal":
                    actual_flip = bool(texture.get_editor_property("flip_green_channel"))
                    if actual_flip:
                        add_failure(failures, "TEXTURE_NORMAL_GREEN", path,
                                    expected=False, actual=True)
            except Exception as exc:
                add_failure(failures, "TEXTURE_SETTINGS", path, exception=str(exc))

    for owner in WAVE_NAMES + (BACKDROP_NAME,):
        slots = ("Front", "Flap") if owner != BACKDROP_NAME else ("Front",)
        params = load_json(source_by[(owner, "mi_params")])
        expected_scalars = dict(params["scalar_parameters"])
        if owner == BACKDROP_NAME:
            expected_scalars.update({"PBacking": 0.55, "POlder": 0.0})
        expected_textures = {
            kind: destination_by[(owner, kind)] for kind in TEXTURE_KINDS
        }
        for slot in slots:
            path = destination_by[(owner, slot)] if owner != BACKDROP_NAME else BACKDROP_MI
            instance = unreal.EditorAssetLibrary.load_asset(path)
            if not isinstance(instance, unreal.MaterialInstanceConstant):
                add_failure(failures, "MI_CLASS", path,
                            expected="MaterialInstanceConstant", actual=type(instance).__name__)
                continue
            try:
                actual_parent = asset_package(instance.get_editor_property("parent"))
                expected_parent = PARENTS[slot]
                if not paths_match(actual_parent, expected_parent):
                    add_failure(failures, "MI_PARENT", path,
                                expected=expected_parent, actual=actual_parent)
            except Exception as exc:
                add_failure(failures, "MI_PARENT", path, exception=str(exc))
            try:
                actual_textures = serialized_texture_parameters(instance)
                if actual_textures != expected_textures:
                    add_failure(failures, "MI_TEXTURE_PARAMETERS", path,
                                expected=expected_textures, actual=actual_textures)
            except Exception as exc:
                add_failure(failures, "MI_TEXTURE_PARAMETERS", path, exception=str(exc))
            try:
                actual_scalars = serialized_scalar_parameters(instance)
                scalar_mismatches = {}
                if set(actual_scalars) != set(expected_scalars):
                    scalar_mismatches["keys"] = {
                        "expected": sorted(expected_scalars),
                        "actual": sorted(actual_scalars),
                    }
                for parameter, expected in expected_scalars.items():
                    actual = actual_scalars.get(parameter)
                    if actual is None or abs(float(actual) - float(expected)) > 0.0001:
                        scalar_mismatches[parameter] = {"expected": float(expected), "actual": actual}
                if scalar_mismatches:
                    add_failure(failures, "MI_SCALAR_PARAMETERS", path,
                                mismatches=scalar_mismatches)
            except Exception as exc:
                add_failure(failures, "MI_SCALAR_PARAMETERS", path, exception=str(exc))

    after = package_census()
    if after != before:
        add_failure(failures, "READ_ONLY_CENSUS_CHANGED", TARGET_ROOT,
                    expected=before, actual=after)
    passed = not failures
    if emit_marker:
        unreal.log("S3_FLATS_IMPORT_VERIFY|run=%s|pass=%s|failures=%s" %
                   (run, str(passed).lower(),
                    json.dumps(failures, separators=(",", ":"), sort_keys=True)))
    return passed, failures, expected_paths


def finish_import(run, inventory):
    passed, failures, expected_paths = verify_existing_assets(run, inventory, emit_marker=True)
    if not passed:
        unreal.log_error("S3_FLATS_IMPORT_FINISH_STOPPED|run=%s|reason=VERIFY_FAILED|failures=%s" %
                         (run, json.dumps(failures, separators=(",", ":"), sort_keys=True)))
        return
    before = package_census()
    if before["maps"] or before["content"] != expected_paths:
        unreal.log_error("S3_FLATS_IMPORT_FINISH_STOPPED|run=%s|reason=CENSUS_BEFORE|expected=%s|actual=%s" %
                         (run, json.dumps({"maps": [], "content": expected_paths},
                                          separators=(",", ":"), sort_keys=True),
                          json.dumps(before, separators=(",", ":"), sort_keys=True)))
        return
    for path in expected_paths:
        if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
            raise RuntimeError("SAVE_FAILED|path=" + path)
    after = package_census()
    if after["maps"] or after["content"]:
        raise RuntimeError("POST_FINISH_DIRTY|census=" + json.dumps(after, sort_keys=True))
    unreal.log("S3_FLATS_IMPORT_DONE|run=%s|finished|census=%s" %
               (run, json.dumps(after, separators=(",", ":"), sort_keys=True)))


def apply_import(run, inventory):
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    source_by = {(row["owner"], row["kind"]): row["path"] for row in inventory["sources"]}
    destination_by = {(row["owner"], row.get("texture_kind", row.get("slot", row["kind"]))): row["path"]
                      for row in inventory["destinations"]}
    # Build every mesh option BEFORE importing anything: run 172901 imported 21 textures, then
    # failed on an FBX option and left them unsaved in memory.
    fbx_options()
    # Revision 3: import all seven meshes first, then gate the exact Interchange
    # result before creating any texture or material-instance asset.
    mesh_tasks = []
    for owner in WAVE_NAMES + (BACKDROP_NAME,):
        destination = destination_by[(owner, "mesh")]
        folder, name = destination.rsplit("/", 1)
        mesh_tasks.append(import_task(source_by[(owner, "mesh")], folder, name, fbx_options()))
    asset_tools.import_asset_tasks(mesh_tasks)
    if not gate_imported_mesh_lods(run, destination_by):
        return

    # Mesh-level geometry gates BEFORE any texture or MI exists, so a failure leaves only the
    # seven meshes in memory (runs 180401 and 181644 left 41 packages behind).
    for owner in WAVE_NAMES:
        mesh = unreal.load_asset(destination_by[(owner, "mesh")])
        for lod in (0, 1):
            verify_uv1_metres(mesh, lod)
        wave_front_orientation(mesh)
    backdrop_handedness(unreal.load_asset(destination_by[(BACKDROP_NAME, "mesh")]))
    unreal.log("S3_FLATS_IMPORT_GEOMETRY_GATE|run=%s|pass=1" % run)

    texture_tasks = []
    for owner in WAVE_NAMES + (BACKDROP_NAME,):
        for kind in TEXTURE_KINDS:
            destination = destination_by[(owner, kind)]
            folder, name = destination.rsplit("/", 1)
            texture_tasks.append(import_task(source_by[(owner, kind)], folder, name))
    asset_tools.import_asset_tasks(texture_tasks)

    textures = {}
    for owner in WAVE_NAMES + (BACKDROP_NAME,):
        textures[owner] = {}
        for kind in TEXTURE_KINDS:
            path = destination_by[(owner, kind)]
            texture = unreal.EditorAssetLibrary.load_asset(path)
            if not isinstance(texture, unreal.Texture2D):
                raise RuntimeError("TEXTURE_IMPORT_FAILED|path=" + path)
            configure_texture(texture, kind)
            textures[owner][kind] = texture

    parent_assets = {slot: unreal.EditorAssetLibrary.load_asset(path) for slot, path in PARENTS.items()}
    instances = {}
    for owner in WAVE_NAMES:
        params = load_json(source_by[(owner, "mi_params")])
        instances[owner] = {}
        for slot in ("Front", "Flap"):
            path = destination_by[(owner, slot)]
            instance = make_instance(path, parent_assets[slot])
            set_skin(instance, textures[owner], params["scalar_parameters"])
            instances[owner][slot] = instance

    backdrop_params = load_json(source_by[(BACKDROP_NAME, "mi_params")])
    backdrop = make_instance(BACKDROP_MI, parent_assets["Front"])
    backdrop_scalars = dict(backdrop_params["scalar_parameters"])
    backdrop_scalars.update({"PBacking": 0.55, "POlder": 0.0})
    set_skin(backdrop, textures[BACKDROP_NAME], backdrop_scalars)

    validation = load_json(project_file("DerivedAssets", "FlatV3", "Scene3", "waves", "validation_summary.json"))
    mesh_reports = {}
    for owner in WAVE_NAMES:
        path = destination_by[(owner, "mesh")]
        mesh = unreal.EditorAssetLibrary.load_asset(path)
        if not isinstance(mesh, unreal.StaticMesh):
            raise RuntimeError("MESH_IMPORT_FAILED|path=" + path)
        mesh.modify()
        nanite = mesh.get_editor_property("nanite_settings")
        nanite.set_editor_property("enabled", False)
        mesh.set_editor_property("nanite_settings", nanite)
        for index, slot in enumerate(MI_SLOTS):
            material = instances[owner][slot] if slot in ("Front", "Flap") else parent_assets[slot]
            mesh.set_material(index, material)
        expected = validation["assets"][owner]["fbx_validation"]["dimensions_m"]
        mesh_reports[owner] = verify_mesh(mesh, expected)

    backdrop_mesh = unreal.EditorAssetLibrary.load_asset(BACKDROP_MESH)
    if not isinstance(backdrop_mesh, unreal.StaticMesh):
        raise RuntimeError("MESH_IMPORT_FAILED|path=" + BACKDROP_MESH)
    backdrop_mesh.modify()
    nanite = backdrop_mesh.get_editor_property("nanite_settings")
    nanite.set_editor_property("enabled", False)
    backdrop_mesh.set_editor_property("nanite_settings", nanite)
    backdrop_mesh.set_material(0, backdrop)
    mesh_reports[BACKDROP_NAME] = verify_backdrop_mesh(backdrop_mesh)
    hand = mesh_reports[BACKDROP_NAME]["handedness"]
    unreal.log("S3_BACKDROP_HANDEDNESS|run=%s|du_dY=%.9g|dv_dZ=%.9g|normal=%s" %
               (run, hand["du_dY"], hand["dv_dZ"],
                ",".join("%.6f" % value for value in hand["normal"])))

    for owner in WAVE_NAMES + (BACKDROP_NAME,):
        for kind in TEXTURE_KINDS:
            verify_texture(textures[owner][kind], kind)

    all_instances = [instances[owner][slot] for owner in WAVE_NAMES
                     for slot in ("Front", "Flap")] + [backdrop]
    for instance in all_instances:
        parent = instance.get_editor_property("parent")
        if parent is None:
            raise RuntimeError("MI_PARENT_MISSING|mi=" + instance.get_path_name())
    for parameter, expected in backdrop_scalars.items():
        actual = unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(backdrop, parameter)
        if abs(float(actual) - float(expected)) > 0.0001:
            raise RuntimeError("BACKDROP_SCALAR_MISMATCH|parameter=%s|actual=%s" % (parameter, actual))

    expected_paths = sorted(row["path"] for row in inventory["destinations"])
    for path in expected_paths:
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            raise RuntimeError("DESTINATION_MISSING_AFTER_IMPORT|path=" + path)
    for path in expected_paths:
        if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
            raise RuntimeError("SAVE_FAILED|path=" + path)
    census = package_census()
    if census["maps"] or census["content"]:
        raise RuntimeError("POST_SAVE_DIRTY|census=" + json.dumps(census, sort_keys=True))
    unreal.log("S3_FLATS_IMPORT_READBACK|run=%s|meshes=%s" %
               (run, json.dumps(mesh_reports, separators=(",", ":"), sort_keys=True)))
    unreal.log("S3_FLATS_IMPORT_DONE|run=%s|assets=%d|census=%s" %
               (run, len(expected_paths), json.dumps(census, separators=(",", ":"), sort_keys=True)))


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    apply = bool(globals().get("S3_FLATS_IMPORT_APPLY"))
    verify = bool(globals().get("S3_FLATS_IMPORT_VERIFY"))
    finish = bool(globals().get("S3_FLATS_IMPORT_FINISH"))
    try:
        if sum(int(value) for value in (apply, verify, finish)) > 1:
            raise RuntimeError("IMPORT_MODE_FLAGS_MUTUALLY_EXCLUSIVE")
        expected_revision = 3 if (verify or finish) else 2
        if globals().get("S3_FLATS_REVISION") != expected_revision:
            raise RuntimeError("REVISION_%d_WRAPPER_REQUIRED" % expected_revision)
        if verify or finish:
            inventory = build_inventory()
            if verify:
                verify_existing_assets(run, inventory, emit_marker=True)
            else:
                finish_import(run, inventory)
            return
        assert_context(run)
        fbx_options()  # pure object construction; proves every FBX option name in the dry run too
        inventory = build_inventory()
        log_inventory(run, inventory)
        issues = inventory_issues(inventory)
        summary = {
            "sources": len(inventory["sources"]),
            "destinations": len(inventory["destinations"]),
            "existing_destinations": sum(1 for row in inventory["destinations"] if row["exists"]),
            "missing_sources": sum(1 for row in inventory["sources"] if not row["exists"]),
            "missing_parents": [row["slot"] for row in inventory["parents"] if not row["exists"]],
        }
        unreal.log("S3_FLATS_IMPORT_INVENTORY|run=%s|%s" %
                   (run, json.dumps(summary, separators=(",", ":"), sort_keys=True)))
        if issues:
            unreal.log_error("S3_FLATS_IMPORT_%s_STOPPED|run=%s|mutated=0|issues=%s" %
                             ("APPLY" if apply else "DRY_RUN", run,
                              json.dumps(issues, separators=(",", ":"), sort_keys=True)))
            return
        if not apply:
            after = package_census()
            if after["maps"] or after["content"]:
                raise RuntimeError("DRY_RUN_DIRTIED_PACKAGES|census=" + json.dumps(after, sort_keys=True))
            unreal.log("S3_FLATS_IMPORT_DRY_RUN_OK|run=%s|mutated=0|sources=%d|destinations=%d|parents=%d" %
                       (run, summary["sources"], summary["destinations"], len(inventory["parents"])))
            return
        apply_import(run, inventory)
    except Exception:
        unreal.log_error("S3_FLATS_IMPORT_ERROR|run=%s|traceback=%s|census=%s" %
                         (run, traceback.format_exc().replace("\n", "\\n"),
                          json.dumps(package_census(), separators=(",", ":"), sort_keys=True)))


main()
