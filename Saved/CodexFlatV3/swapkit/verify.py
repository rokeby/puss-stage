"""Read-only saved/read-back verification for a configured Flat V3 swap."""
import importlib
import json
import math
import os
import sys
import traceback

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import common as c
c = importlib.reload(c)
import shift_common as shift


GAP_TOLERANCE_CM = 2.0
INNER_EDGE_EPSILON_CM = 0.01
OUTER_REPORT_LIMIT_CM = 1500.0

SAMPLE_PHASES = (0.25, 0.5, 0.75)


def assert_clean(stage):
    actual = c.census()
    if actual != c.CLEAN:
        raise RuntimeError("VERIFY_%s_DIRTY|census=%s" %
                           (stage.upper(), json.dumps(actual, sort_keys=True)))
    return actual


def unwrap(value, count):
    if value is None:
        return None
    if isinstance(value, tuple) and len(value) == count + 1 and isinstance(value[0], bool):
        return value[1:] if value[0] else None
    return value


def vector_plain(value):
    return [float(value.x), float(value.y), float(value.z)]


def box_points(box):
    return [unreal.Vector(x, y, z) for x in (box.min.x, box.max.x)
            for y in (box.min.y, box.max.y) for z in (box.min.z, box.max.z)]


def bounds_in_frame(mesh, instance_transform, frame):
    points = [frame.inverse_transform_location(instance_transform.transform_location(point))
              for point in box_points(mesh.get_bounding_box())]
    return {"min": [min(getattr(point, axis) for point in points) for axis in ("x", "y", "z")],
            "max": [max(getattr(point, axis) for point in points) for axis in ("x", "y", "z")]}


def refs_for(actor, cue_guid):
    refs = [ref for ref in actor.get_editor_property("materialized_panels")
            if ref.get_editor_property("cue_guid").to_string() == cue_guid]
    result = {}
    for ref in refs:
        side_text = str(ref.get_editor_property("side")).upper()
        if "LEFT" in side_text:
            result.setdefault("left", []).append(ref)
        elif "RIGHT" in side_text:
            result.setdefault("right", []).append(ref)
    if sorted(result) != ["left", "right"] or any(len(values) != 1 for values in result.values()):
        raise RuntimeError("PLACED_REF_SCOPE_FAIL|guid=%s|sides=%s" %
                           (cue_guid, {key: len(values) for key, values in result.items()}))
    return {key: values[0] for key, values in result.items()}


def quat_tuple(rotation):
    return (float(rotation.x), float(rotation.y), float(rotation.z), float(rotation.w))


def quat_normalized(value):
    length = math.sqrt(sum(component * component for component in value))
    if length <= 0.0000001:
        raise RuntimeError("PAIR_FRAME_ZERO_QUATERNION")
    return tuple(component / length for component in value)


def quat_multiply(left, right):
    lx, ly, lz, lw = left
    rx, ry, rz, rw = right
    return quat_normalized((
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
        lw * rw - lx * rx - ly * ry - lz * rz,
    ))


def quat_inverse(value):
    x, y, z, w = quat_normalized(value)
    return (-x, -y, -z, w)


def quat_rotate(value, vector):
    x, y, z, w = quat_normalized(value)
    vx, vy, vz = vector
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return (vx + w * tx + (y * tz - z * ty),
            vy + w * ty + (z * tx - x * tz),
            vz + w * tz + (x * ty - y * tx))


def transform_parts(value):
    return {"location": (float(value.translation.x), float(value.translation.y),
                         float(value.translation.z)),
            "rotation": quat_tuple(value.rotation),
            "scale": (float(value.scale3d.x), float(value.scale3d.y),
                      float(value.scale3d.z))}


def compose_parts(left, right):
    """Match UE's Left * Right FTransform composition (Left is applied first)."""
    scaled_left = tuple(left["location"][axis] * right["scale"][axis]
                        for axis in range(3))
    rotated_left = quat_rotate(right["rotation"], scaled_left)
    return {
        "location": tuple(right["location"][axis] + rotated_left[axis]
                          for axis in range(3)),
        "rotation": quat_multiply(right["rotation"], left["rotation"]),
        "scale": tuple(left["scale"][axis] * right["scale"][axis]
                       for axis in range(3)),
    }


def identity_parts(scale=(1.0, 1.0, 1.0)):
    return {"location": (0.0, 0.0, 0.0), "rotation": (0.0, 0.0, 0.0, 1.0),
            "scale": tuple(float(value) for value in scale)}


def resolved_panel_prefix(panel_record, library_by_mesh):
    """Rebuild Image * Facing * Local exactly as materialization declares it."""
    image = identity_parts((1.0, -1.0, 1.0) if panel_record["flip_image_horizontally"]
                           else (1.0, 1.0, 1.0))
    entry = library_by_mesh.get(panel_record["mesh"])
    rotate = "ROTATE180_AROUND_UP" in panel_record["facing_policy"].upper()
    if "AUTO_BY_ROLE" in panel_record["facing_policy"].upper() and entry is not None:
        rotate = "NEGATIVE_X" in str(entry.get_editor_property("front_axis")).upper()
    facing = transform_parts(unreal.Transform(
        rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=180.0 if rotate else 0.0)))
    if entry is not None:
        placement = entry.get_editor_property("placement_adjustment")
        placement_scale = placement.scale3d
        mirrored = float(placement_scale.x * placement_scale.y * placement_scale.z) < 0.0
        if not mirrored or bool(entry.get_editor_property("photographic_mirror_approved")):
            facing = compose_parts(transform_parts(placement), facing)
    local = transform_parts(c.transform_from_plain(panel_record["local_transform"]))
    return compose_parts(compose_parts(image, facing), local)


def invert_panel_frame(ref, panel_record, library_by_mesh):
    """Recover PairWorld from BaseWorld = Image * Facing * Local * PairWorld."""
    world = transform_parts(ref.get_editor_property("base_world_transform"))
    prefix = resolved_panel_prefix(panel_record, library_by_mesh)
    if any(abs(value) <= 0.0000001 for value in prefix["scale"]):
        raise RuntimeError("PAIR_FRAME_ZERO_PANEL_SCALE")
    pair_scale = tuple(world["scale"][axis] / prefix["scale"][axis]
                       for axis in range(3))
    pair_rotation = quat_multiply(world["rotation"], quat_inverse(prefix["rotation"]))
    scaled_prefix = tuple(prefix["location"][axis] * pair_scale[axis]
                          for axis in range(3))
    rotated_prefix = quat_rotate(pair_rotation, scaled_prefix)
    pair_location = tuple(world["location"][axis] - rotated_prefix[axis]
                          for axis in range(3))
    # UE 5.8: Transform(rotation=...) only accepts a Rotator (Quat raises in
    # KismetMathLibrary.MakeTransform). Build with identity, then assign the Quat
    # attribute directly so no Quat->Rotator precision loss enters the frame.
    frame = unreal.Transform(location=unreal.Vector(*pair_location),
                             rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0),
                             scale=unreal.Vector(*pair_scale))
    quat = unreal.Quat(*pair_rotation)
    try:
        frame.rotation = quat
    except Exception:
        frame = unreal.Transform(location=unreal.Vector(*pair_location),
                                 rotation=quat.rotator(), scale=unreal.Vector(*pair_scale))
    return frame


def frames_close(left, right, location_tolerance=0.05, scale_tolerance=0.0001,
                 quaternion_tolerance=0.000001):
    left_parts, right_parts = transform_parts(left), transform_parts(right)
    if any(abs(left_parts["location"][axis] - right_parts["location"][axis]) >
           location_tolerance for axis in range(3)):
        return False
    if any(abs(left_parts["scale"][axis] - right_parts["scale"][axis]) >
           scale_tolerance for axis in range(3)):
        return False
    dot = abs(sum(left_parts["rotation"][axis] * right_parts["rotation"][axis]
                  for axis in range(4)))
    return abs(1.0 - dot) <= quaternion_tolerance


def identity_rotation(rotation):
    return all(abs(((float(value) + 180.0) % 360.0) - 180.0) <= 0.001
               for value in rotation)


def pair_frame(actor, cue, refs, pair, row, library_by_mesh):
    """Use an exposed PairWorld when available, otherwise invert complete panel prefixes."""
    derived = {side: invert_panel_frame(
        refs[side], c.panel_plain(pair.get_editor_property(side)), library_by_mesh)
        for side in ("left", "right")}

    direct = None
    resolver = getattr(actor, "get_cue_placement_transforms", None)
    if callable(resolver):
        resolved = unwrap(resolver(cue.get_editor_property("cue_guid")), 2)
        if resolved is not None and len(resolved) == 2:
            direct = resolved[1]

    source = None
    if direct is not None:
        frame = direct
        source = "actor_pair_transform"
    else:
        frame = None
        for side in ("left", "right"):
            panel_record = c.panel_plain(pair.get_editor_property(side))
            if (side in row["changed_sides"] and
                    "PRESERVE_ASSET" in panel_record["facing_policy"].upper() and
                    identity_rotation(panel_record["local_transform"]["rotation"])):
                frame = derived[side]
                source = "changed_%s_preserve_identity_local_rotation" % side
                break
        if frame is None:
            frame = derived["left"]
            source = "left_full_panel_inversion"

    for side, side_frame in derived.items():
        if not frames_close(frame, side_frame):
            raise RuntimeError("PAIR_FRAME_REF_DISAGREEMENT|label=%s|source=%s|side=%s" %
                               (row["cue_label"], source, side))
    return frame, source


def tick_resolution(show):
    rate = show.get_editor_property("tick_resolution")
    numerator = float(getattr(rate, "numerator", 48000.0))
    denominator = float(getattr(rate, "denominator", 1.0))
    if denominator == 0.0 or numerator <= 0.0:
        raise RuntimeError("INVALID_TICK_RESOLUTION")
    return numerator / denominator


def phase_origin_frame(mechanism, passage_start, pass_frame):
    origin_kind = str(mechanism.get_editor_property("phase_origin")).upper()
    if "PASS_FRAME" in origin_kind:
        return pass_frame
    if "EXPLICIT_FRAME" in origin_kind:
        return c.frame_value(mechanism.get_editor_property("explicit_origin_frame"))
    return passage_start


def phase_frames(mechanism, origin_frame, ticks_per_second):
    rate = float(mechanism.get_editor_property("cycle_rate_hz"))
    if rate <= 0.0:
        raise RuntimeError("NONPOSITIVE_CYCLE_RATE")
    offset = float(mechanism.get_editor_property("phase_offset_cycles"))
    return [(phase, origin_frame + int(round(((phase - offset) / rate) * ticks_per_second)))
            for phase in SAMPLE_PHASES]


def normalized_travel(phase):
    return 0.5 - 0.5 * math.cos(2.0 * math.pi * phase)


def predict_slide(ref, travel_cm, phase):
    base = ref.get_editor_property("base_world_transform")
    inward = ref.get_editor_property("inward_world_direction")
    inward_length = float(inward.length())
    if abs(inward_length - 1.0) > 0.001:
        raise RuntimeError("INWARD_DIRECTION_NOT_UNIT|length=%g" % inward_length)
    delta = inward * (normalized_travel(phase) * travel_cm)
    projection = float(delta.dot(inward))
    residual = float((delta - inward * projection).length())
    transform = c.transform_plain(base)
    transform["location"] = [transform["location"][axis] + vector_plain(delta)[axis]
                             for axis in range(3)]
    return {"transform": transform, "inward_projection_cm": projection,
            "cross_axis_residual_cm": residual, "rotation_delta_deg": 0.0}


def run_verify(config_path=None, swap_run=None, verification_run=None,
               emit_report=True, require_token=True):
    config = c.load_config(config_path)
    swap_run = swap_run or config["run_id"]
    verification_run = verification_run or swap_run
    c.assert_context(config, clean=True)
    assert_clean("start")
    originals = c.read_json(config, "preflight", run=swap_run)
    plan = c.read_json(config, "dry_run", run=swap_run)
    if plan.get("lateral_mode", "backbone") != config["lateral_mode"]:
        raise RuntimeError("VERIFY_LATERAL_MODE_MISMATCH|config=%s|plan=%s" %
                           (config["lateral_mode"],
                            plan.get("lateral_mode", "backbone")))
    configured_keep = sorted((entry["cue_guid"], entry["side"], entry["reason"])
                             for entry in config["keep_old_sides"])
    planned_keep = sorted((entry["cue_guid"], entry["side"], entry["reason"])
                          for entry in plan.get("kept_old_sides", []))
    if planned_keep != configured_keep:
        raise RuntimeError("VERIFY_KEEP_OLD_SIDES_MISMATCH")
    originals_by_guid = {row["cue_guid"]: row for row in originals["rows"]}
    plan_by_guid = {row["cue_guid"]: row for row in plan["rows"]}
    show = unreal.EditorAssetLibrary.load_asset(c.SHOW)
    if show is None:
        raise RuntimeError("SHOW_LOAD_FAIL")
    cues = list(show.get_editor_property("cues"))
    actor = c.passage_actor(config, show)
    library_ref = show.get_editor_property("wing_library")
    library_path = c.asset_path(library_ref)
    library = unreal.EditorAssetLibrary.load_asset(library_path) if library_path else None
    if library is None:
        raise RuntimeError("WING_LIBRARY_LOAD_FAIL|path=" + str(library_path))
    library_by_mesh = {}
    for entry in library.get_editor_property("entries"):
        entry_mesh = c.asset_path(entry.get_editor_property("mesh"))
        if entry_mesh:
            library_by_mesh[entry_mesh] = entry

    mesh_gates = {}
    for mesh_path in sorted({row[side]["mesh"] for row in plan["rows"]
                             for side in row["changed_sides"] if row[side]["mesh"] is not None}):
        mesh = unreal.EditorAssetLibrary.load_asset(mesh_path)
        if not isinstance(mesh, unreal.StaticMesh):
            raise RuntimeError("MESH_LOAD_FAIL|path=" + mesh_path)
        box = mesh.get_bounding_box()
        mesh_gates[mesh_path] = {"loaded_static_mesh": True,
                                 "bounds_cm": {"min": vector_plain(box.min),
                                               "max": vector_plain(box.max)}}

    placed = []
    gap_rows = []
    outer_edge_rows = []
    pair_frames = {}
    pair_frame_sources = {}
    for row in plan["rows"]:
        cue = cues[row["cue_index"]]
        original = originals_by_guid[row["cue_guid"]]
        c.assert_occurrence(cue, row["cue_index"], row,
                            config["passage_label_prefix"], "VERIFY_CUE_IDENTITY_FAIL")
        pair = cue.get_editor_property("wing_pair")
        kept_sides = {entry["side"] for entry in row.get("kept_old_sides", [])}
        for side in ("left", "right", "top"):
            actual_panel = c.panel_plain(pair.get_editor_property(side))
            expected_panel = row[side] if side in row["changed_sides"] else original[side]
            if not c.panel_matches(actual_panel, expected_panel):
                error = ("VERIFY_KEPT_OLD_SIDE_CHANGED" if side in kept_sides
                         else "VERIFY_PANEL_FAIL")
                raise RuntimeError("%s|label=%s|side=%s|actual=%s" %
                                   (error, row["cue_label"], side,
                                    json.dumps(actual_panel, sort_keys=True)))
        if c.mechanism_plain(pair.get_editor_property("mechanism")) != original["mechanism"]:
            raise RuntimeError("VERIFY_MECHANISM_CHANGED|" + row["cue_label"])
        if not c.close_transform(c.transform_plain(pair.get_editor_property("occurrence_offset")),
                                 original["occurrence_offset"]):
            raise RuntimeError("VERIFY_OCCURRENCE_OFFSET_CHANGED|" + row["cue_label"])
        refs = refs_for(actor, row["cue_guid"])
        frame, frame_source = pair_frame(actor, cue, refs, pair, row, library_by_mesh)
        pair_frames[row["cue_guid"]] = frame
        pair_frame_sources[row["cue_guid"]] = frame_source
        pair_minus_x = frame.rotation.rotate_vector(unreal.Vector(-1.0, 0.0, 0.0))
        world_edges = {}
        for side in ("left", "right"):
            ref = refs[side]
            component = ref.get_editor_property("component")
            mesh = component.get_editor_property("static_mesh")
            if c.asset_path(mesh) != row[side]["mesh"]:
                raise RuntimeError("PLACED_MESH_FAIL|label=%s|side=%s" % (row["cue_label"], side))
            base_transform = ref.get_editor_property("base_world_transform")
            bounds = bounds_in_frame(mesh, base_transform, frame)
            centre_y = (bounds["min"][1] + bounds["max"][1]) * 0.5
            actual_outer = bounds["min"][1] if side == "left" else bounds["max"][1]
            actual_inner = bounds["max"][1] if side == "left" else bounds["min"][1]
            world_edges[side] = {"outer_edge_cm": actual_outer,
                                 "inner_edge_cm": actual_inner}
            if side not in row["changed_sides"]:
                continue
            # Side test on the BACKBONE (outer) edge, not the centre: P05 clouds are
            # authored overlapping the centreline (old right at cue 125 spans y -205..205),
            # so a centre test fails faithful swaps. Exact plan edges are checked below.
            backbone_y = bounds["min"][1] if side == "left" else bounds["max"][1]
            if (side == "left" and backbone_y >= -1.0) or (side == "right" and backbone_y <= 1.0):
                raise RuntimeError("PLACED_SIDE_BOUNDS_FAIL|label=%s|side=%s|bounds=%s" %
                                   (row["cue_label"], side, json.dumps(bounds)))
            placement = row["placement"][side]
            expected_outer = float(placement.get(
                "new_outer_edge_cm", placement["old_outer_edge_cm"]))
            if (abs(actual_outer - expected_outer) > 1.0 or
                    abs(actual_inner - float(placement["new_inner_edge_cm"])) > 1.0):
                raise RuntimeError("PLACED_EDGE_READBACK_FAIL|label=%s|side=%s|outer=%g|inner=%g" %
                                   (row["cue_label"], side, actual_outer, actual_inner))
            old_inner = float(placement["old_inner_edge_cm"])
            onstage = max(0.0, (actual_inner - old_inner) if side == "left"
                          else (old_inner - actual_inner))
            if config["lateral_mode"] == "inner_edge" and onstage > INNER_EDGE_EPSILON_CM:
                raise RuntimeError(
                    "VERIFY_INNER_EDGE_ONSTAGE_FAIL|label=%s|side=%s|old=%g|actual=%g" %
                    (row["cue_label"], side, old_inner, actual_inner))
            front = base_transform.rotation.rotate_vector(unreal.Vector(-1.0, 0.0, 0.0))
            front_dot = float(front.dot(pair_minus_x))
            if front_dot < 0.99:
                raise RuntimeError("PLACED_FRONT_FAIL|label=%s|side=%s|dot=%g" %
                                   (row["cue_label"], side, front_dot))
            placed.append({"cue_label": row["cue_label"], "side": side,
                           "mesh": c.asset_path(mesh), "bounds_pair_cm": bounds,
                           "centre_y_cm": centre_y, "outer_edge_cm": actual_outer,
                           "inner_edge_cm": actual_inner, "front_dot_minus_x": front_dot})
        old_gap = float(row.get("centre_gap", {}).get(
            "gap_old_cm", shift.centre_gap_cm(
                c.side_bounds(original["left"], library_by_mesh)["max_y_cm"],
                c.side_bounds(original["right"], library_by_mesh)["min_y_cm"])))
        new_gap = shift.centre_gap_cm(world_edges["left"]["inner_edge_cm"],
                                      world_edges["right"]["inner_edge_cm"])
        lateral_changed = [side for side in row["changed_sides"]
                           if side in ("left", "right")]
        gap_rows.append({"cue_guid": row["cue_guid"], "cue_index": row["cue_index"],
                         "cue_label": row["cue_label"], "shifted_sides": lateral_changed,
                         "gap_old_cm": old_gap, "gap_new_cm": new_gap})
        max_outer = max(abs(world_edges[side]["outer_edge_cm"])
                        for side in ("left", "right"))
        outer_edge_rows.append({"cue_guid": row["cue_guid"],
                                "cue_index": row["cue_index"],
                                "cue_label": row["cue_label"],
                                "max_abs_outer_edge_cm": max_outer,
                                "beyond_1500_cm": max_outer > OUTER_REPORT_LIMIT_CM,
                                "sides": world_edges})

    gap_gate = shift.minimum_gap_gate(gap_rows, GAP_TOLERANCE_CM, config["passage"])

    passage_range = unwrap(unreal.InfinityStageCameraPilotLibrary.get_passage_frame_range(
        show, actor.get_editor_property("passage_guid")), 2)
    if passage_range is None:
        raise RuntimeError("PASSAGE_RANGE_FAIL")
    start_frame, end_frame = c.frame_value(passage_range[0]), c.frame_value(passage_range[1])
    actor_guid = actor.get_editor_property("passage_guid").to_string()
    settings = next(value for value in show.get_editor_property("passage_settings")
                    if value.get_editor_property("passage_guid").to_string() == actor_guid)
    pass_frame = start_frame + c.frame_value(settings.get_editor_property("lead_in_frames"))
    ticks_per_second = tick_resolution(show)
    passage_rows = [(index, cue) for index, cue in enumerate(cues)
                    if str(cue.get_editor_property("label")).startswith(config["passage_label_prefix"])]
    candidates = []
    for index, cue in passage_rows:
        mechanism = cue.get_editor_property("wing_pair").get_editor_property("mechanism")
        rate = float(mechanism.get_editor_property("cycle_rate_hz"))
        guid = c.cue_guid(cue)
        if rate > 0.0 and guid in plan_by_guid:
            c.assert_occurrence(cue, index, plan_by_guid[guid],
                                config["passage_label_prefix"], "VERIFY_MOVEMENT_IDENTITY_FAIL")
            origin = phase_origin_frame(mechanism, start_frame, pass_frame)
            frames = phase_frames(mechanism, origin, ticks_per_second)
            if all(start_frame <= frame <= end_frame for _, frame in frames):
                candidates.append((index, cue, origin, frames))
        pass_frame += c.frame_value(
            cue.get_editor_property("wing_pair").get_editor_property("interval_to_next"))
    min_samples = int(config.get("min_movement_samples", 3))
    if len(candidates) < min_samples:
        raise RuntimeError("TOO_FEW_MOVEMENT_SAMPLE_CANDIDATES|actual=%d|required=%d" %
                           (len(candidates), min_samples))
    # Explicit per-passage minimum (config "min_movement_samples", default 3); P01 has
    # only one in-range moving occurrence. Distinct picks; never more than available.
    picks = sorted({0, len(candidates) // 2, len(candidates) - 1})
    selected = [candidates[i] for i in picks]
    if len({index for index, _, _, _ in selected}) != len(picks):
        raise RuntimeError("MOVEMENT_SAMPLE_NOT_DISTINCT")
    movement = []
    for index, cue, origin, frames in selected:
        label = str(cue.get_editor_property("label"))
        mechanism = cue.get_editor_property("wing_pair").get_editor_property("mechanism")
        kind = str(mechanism.get_editor_property("kind"))
        if "SLIDE" not in kind.upper():
            raise RuntimeError("MOVEMENT_KIND_NOT_SLIDE|label=%s|kind=%s" % (label, kind))
        travel_cm = float(mechanism.get_editor_property("inward_travel_cm"))
        refs = refs_for(actor, cue.get_editor_property("cue_guid").to_string())
        samples = []
        for phase, frame_number in frames:
            panels = {side: predict_slide(ref, travel_cm, phase) for side, ref in refs.items()}
            samples.append({"phase": phase, "master_frame": frame_number, "panels": panels})
        for side in ("left", "right"):
            projections = [sample["panels"][side]["inward_projection_cm"] for sample in samples]
            residuals = [sample["panels"][side]["cross_axis_residual_cm"] for sample in samples]
            rotations = [sample["panels"][side]["rotation_delta_deg"] for sample in samples]
            if max(projections) - min(projections) < 20.0:
                raise RuntimeError("MOVEMENT_TRAVEL_GATE_FAIL|label=%s|side=%s" % (label, side))
            if max(residuals) > 0.001:
                raise RuntimeError("MOVEMENT_CROSS_AXIS_GATE_FAIL|label=%s|side=%s" % (label, side))
            if max(rotations) > 0.0:
                raise RuntimeError("MOVEMENT_ROTATION_GATE_FAIL|label=%s|side=%s" % (label, side))
        movement.append({"cue_label": label, "cue_index": index, "kind": kind,
                         "phase_origin_frame": origin, "samples": samples})

    capture_label = config.get("capture_label", plan["rows"][len(plan["rows"]) // 2]["cue_label"])
    capture_rows = sorted((row for row in plan["rows"]
                           if row["cue_label"] == capture_label),
                          key=lambda row: row["cue_index"])
    if not capture_rows:
        raise RuntimeError("CAPTURE_LABEL_NOT_PLANNED|" + capture_label)
    capture_row = capture_rows[0]
    capture_guid = capture_row["cue_guid"]
    capture_frame = pair_frames[capture_guid]
    def point(local):
        return vector_plain(capture_frame.transform_location(unreal.Vector(*local)))
    capture_plan = {"run": verification_run, "source_swap_run": swap_run,
                    "target_index": capture_row["cue_index"],
                    "target_guid": capture_guid, "target_label": capture_label,
                    "selection": "first matching label by cue_index",
                    "target": point((0.0, 0.0, 500.0)),
                    "poses": [
                        {"name": "passage_camera", "location": point((-2000.0, 0.0, 500.0))},
                        {"name": "corridor_threequarter", "location": point((-1700.0, -1300.0, 700.0))},
                        {"name": "back_offstage", "location": point((1500.0, 0.0, 650.0))}],
                    "modes": ["lit", "unlit"], "exposure_override": False,
                    "spawned_actors": False}
    if require_token and not c.log_has(config["verify_token"]):
        raise RuntimeError("VERIFY_TOKEN_NOT_FOUND|" + config["verify_token"])
    end_census = assert_clean("end")
    report = {"run": verification_run, "source_swap_run": swap_run, "mode": "verify",
              "status": "PASS", "rows": len(plan["rows"]),
              "lateral_mode": config["lateral_mode"], "placed_panels": placed,
              "centre_gap_gate": gap_gate,
              "outer_edge_rows": outer_edge_rows,
              "outer_report_limit_cm": OUTER_REPORT_LIMIT_CM,
              "outer_beyond_limit": [row for row in outer_edge_rows
                                     if row["beyond_1500_cm"]],
              "kept_old_sides": plan.get("kept_old_sides", []),
              "mesh_gates": mesh_gates, "movement": movement,
              "pair_frame_sources": pair_frame_sources,
              "movement_sample_count": len(movement),
              "movement_phases_each": list(SAMPLE_PHASES),
              "passage_range": [start_frame, end_frame], "capture_plan": capture_plan,
              "verify_token": config["verify_token"], "dirty_after": end_census}
    if emit_report:
        report["report_path"] = c.write_json(config, "verify", report, run=verification_run)
    return report


def main(config_path=None):
    config = c.load_config(config_path)
    try:
        report = run_verify(config["_path"], config["run_id"], config["run_id"], True, True)
        unreal.log("%s run=%s rows=%d placed_panels=%d movement_occurrences=%d phases_each=3 census=%s report=%s" %
                   (c.marker(config, "READBACK_OK"), config["run_id"], report["rows"],
                    len(report["placed_panels"]), report["movement_sample_count"],
                    json.dumps(report["dirty_after"], separators=(",", ":"), sort_keys=True),
                    report["report_path"]))
        unreal.log(config["success_marker"] + " run=" + config["run_id"])
        c.log_release(config, "OK", [], run=config["run_id"], artifact_run=config["run_id"])
        return report
    except Exception as exc:
        reason = "verify:" + str(exc)
        c.write_json(config, "verify", {"run": config["run_id"], "mode": "verify",
                     "status": "FAIL", "reason": reason, "traceback": traceback.format_exc(),
                     "census": c.census()}, failure=True)
        unreal.log_error("%s run=%s reason=%s census=%s" %
                         (c.marker(config, "VERIFY_FAIL"), config["run_id"],
                          str(exc).replace("\n", "\\n"),
                          json.dumps(c.census(), separators=(",", ":"), sort_keys=True)))
        c.log_release(config, "FAIL", [], reason, run=config["run_id"],
                      artifact_run=config["run_id"])
        raise


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))
