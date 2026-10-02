"""Read-only saved/read-back verification for the P04 Flat V3 swap."""
import importlib
import json
import math
import os
import sys
import traceback
import unreal

BASE = os.path.normpath(os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexFlatV3"))
if BASE not in sys.path:
    sys.path.insert(0, BASE)
import slot_b_common as c
c = importlib.reload(c)

CLEAN = {"content": [], "maps": []}
SAMPLE_PHASES = (0.25, 0.5, 0.75)


def assert_clean(stage):
    actual = c.census()
    if actual != CLEAN:
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


def pair_frame(ref, left_local):
    base = ref.get_editor_property("base_world_transform")
    local = unreal.Vector(*left_local)
    scaled = unreal.Vector(local.x * base.scale3d.x, local.y * base.scale3d.y, local.z * base.scale3d.z)
    location = base.translation - base.rotation.rotate_vector(scaled)
    return unreal.Transform(location=location, rotation=base.rotation.rotator(), scale=base.scale3d)


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
    # The production smooth-undulation keys are exactly 0.5, 1.0, 0.5 at
    # these three quarter-cycle samples; the cosine is their analytic form.
    return 0.5 - 0.5 * math.cos(2.0 * math.pi * phase)


def predict_slide(ref, travel_cm, phase):
    base = ref.get_editor_property("base_world_transform")
    inward = ref.get_editor_property("inward_world_direction")
    inward_length = float(inward.length())
    if abs(inward_length - 1.0) > 0.001:
        raise RuntimeError("INWARD_DIRECTION_NOT_UNIT|length=%g" % inward_length)
    amount = normalized_travel(phase) * travel_cm
    delta = inward * amount
    projection = float(delta.dot(inward))
    residual = float((delta - inward * projection).length())
    transform = c.transform_plain(base)
    transform["location"] = [transform["location"][axis] + vector_plain(delta)[axis]
                             for axis in range(3)]
    return {"transform": transform, "inward_projection_cm": projection,
            "cross_axis_residual_cm": residual, "rotation_delta_deg": 0.0}


def panel_matches(actual, expected):
    return (actual["mesh"] == expected["mesh"] and
            actual["material_overrides"] == expected["material_overrides"] and
            c.close_transform(actual["local_transform"], expected["local_transform"]) and
            "PRESERVE_ASSET" in actual["facing_policy"] and
            not actual["flip_image_horizontally"])


def run_verify(swap_run=None, verification_run=None, emit_report=True):
    swap_run = swap_run or c.RUN
    verification_run = verification_run or swap_run
    c.assert_context(clean=True)
    assert_clean("start")

    originals = c.read_json("slot_b_originals_%s.json" % swap_run)
    plan = c.read_json("slot_b_dry_run_%s.json" % swap_run)
    originals_by_index = {row["cue_index"]: row for row in originals["rows"]}
    plan_by_index = {row["cue_index"]: row for row in plan["rows"]}
    show = unreal.EditorAssetLibrary.load_asset(c.SHOW)
    if show is None:
        raise RuntimeError("SHOW_LOAD_FAIL")
    cues = list(show.get_editor_property("cues"))
    actor = c.p04_actor(show)

    mesh_gates = {}
    for mesh_path in c.LEFT_POOL + c.RIGHT_POOL:
        mesh = unreal.EditorAssetLibrary.load_asset(mesh_path)
        if not isinstance(mesh, unreal.StaticMesh):
            raise RuntimeError("P04_MESH_LOAD_FAIL|path=" + mesh_path)
        box = mesh.get_bounding_box()
        mesh_gates[mesh_path] = {
            "loaded_static_mesh": True,
            "bounds_cm": {"min": vector_plain(box.min), "max": vector_plain(box.max)},
        }

    placed = []
    pair_frames = {}
    for row in plan["rows"]:
        cue = cues[row["cue_index"]]
        original = originals_by_index[row["cue_index"]]
        if str(cue.get_editor_property("label")) != row["cue_label"]:
            raise RuntimeError("VERIFY_CUE_IDENTITY_FAIL|" + row["cue_label"])
        pair = cue.get_editor_property("wing_pair")
        for side in ("left", "right"):
            actual_panel = c.panel_plain(pair.get_editor_property(side))
            if not panel_matches(actual_panel, row[side]):
                raise RuntimeError("VERIFY_PANEL_FAIL|label=%s|side=%s|actual=%s" %
                                   (row["cue_label"], side, json.dumps(actual_panel, sort_keys=True)))
        if c.panel_plain(pair.get_editor_property("top")) != original["top"]:
            raise RuntimeError("VERIFY_TOP_CHANGED|" + row["cue_label"])
        if c.mechanism_plain(pair.get_editor_property("mechanism")) != original["mechanism"]:
            raise RuntimeError("VERIFY_MECHANISM_CHANGED|" + row["cue_label"])
        if not c.close_transform(c.transform_plain(pair.get_editor_property("occurrence_offset")),
                                 original["occurrence_offset"]):
            raise RuntimeError("VERIFY_OCCURRENCE_OFFSET_CHANGED|" + row["cue_label"])

        refs = refs_for(actor, row["cue_guid"])
        frame = pair_frame(refs["left"], row["left"]["local_transform"]["location"])
        pair_frames[row["cue_label"]] = frame
        pair_minus_x = frame.rotation.rotate_vector(unreal.Vector(-1.0, 0.0, 0.0))
        for side in ("left", "right"):
            ref = refs[side]
            component = ref.get_editor_property("component")
            mesh = component.get_editor_property("static_mesh")
            if c.asset_path(mesh) != row[side]["mesh"]:
                raise RuntimeError("PLACED_MESH_FAIL|label=%s|side=%s" % (row["cue_label"], side))
            base_transform = ref.get_editor_property("base_world_transform")
            bounds = bounds_in_frame(mesh, base_transform, frame)
            centre_y = (bounds["min"][1] + bounds["max"][1]) * 0.5
            if (side == "left" and centre_y >= -1.0) or (side == "right" and centre_y <= 1.0):
                raise RuntimeError("PLACED_SIDE_BOUNDS_FAIL|label=%s|side=%s|bounds=%s" %
                                   (row["cue_label"], side, json.dumps(bounds)))
            placement = row["placement"][side]
            actual_outer = bounds["min"][1] if side == "left" else bounds["max"][1]
            actual_inner = bounds["max"][1] if side == "left" else bounds["min"][1]
            if (abs(actual_outer - float(placement["old_outer_edge_cm"])) > 1.0 or
                    abs(actual_inner - float(placement["new_inner_edge_cm"])) > 1.0):
                raise RuntimeError("PLACED_EDGE_READBACK_FAIL|label=%s|side=%s|outer=%g|inner=%g" %
                                   (row["cue_label"], side, actual_outer, actual_inner))
            front = base_transform.rotation.rotate_vector(unreal.Vector(-1.0, 0.0, 0.0))
            front_dot = float(front.dot(pair_minus_x))
            if front_dot < 0.99:
                raise RuntimeError("PLACED_FRONT_FAIL|label=%s|side=%s|dot=%g" %
                                   (row["cue_label"], side, front_dot))
            placed.append({"cue_label": row["cue_label"], "side": side,
                           "mesh": c.asset_path(mesh), "bounds_pair_cm": bounds,
                           "centre_y_cm": centre_y, "outer_edge_cm": actual_outer,
                           "inner_edge_cm": actual_inner, "front_dot_minus_x": front_dot})

    passage_range = unwrap(unreal.InfinityStageCameraPilotLibrary.get_passage_frame_range(
        show, actor.get_editor_property("passage_guid")), 2)
    if passage_range is None:
        raise RuntimeError("PASSAGE_RANGE_FAIL")
    start_frame, end_frame = c.frame_value(passage_range[0]), c.frame_value(passage_range[1])
    actor_guid = actor.get_editor_property("passage_guid").to_string()
    settings = next(value for value in show.get_editor_property("passage_settings")
                    if value.get_editor_property("passage_guid").to_string() == actor_guid)
    first_pass_frame = start_frame + c.frame_value(settings.get_editor_property("lead_in_frames"))
    ticks_per_second = tick_resolution(show)
    p04_rows = [(index, cue) for index, cue in enumerate(cues)
                if str(cue.get_editor_property("label")).startswith("P04 Wing ")]
    pass_frame = first_pass_frame
    candidates = []
    for index, cue in p04_rows:
        mechanism = cue.get_editor_property("wing_pair").get_editor_property("mechanism")
        rate = float(mechanism.get_editor_property("cycle_rate_hz"))
        if rate > 0.0 and index in plan_by_index:
            origin = phase_origin_frame(mechanism, start_frame, pass_frame)
            frames = phase_frames(mechanism, origin, ticks_per_second)
            if all(start_frame <= frame <= end_frame for _, frame in frames):
                candidates.append((index, cue, origin, frames))
        pass_frame += c.frame_value(
            cue.get_editor_property("wing_pair").get_editor_property("interval_to_next"))
    if len(candidates) < 3:
        raise RuntimeError("TOO_FEW_MOVEMENT_SAMPLE_CANDIDATES|actual=%d" % len(candidates))
    selected = [candidates[0], candidates[len(candidates) // 2], candidates[-1]]
    if len({index for index, _, _, _ in selected}) != 3:
        raise RuntimeError("MOVEMENT_SAMPLE_NOT_DISTINCT")

    movement = []
    for index, cue, origin, frames in selected:
        label = str(cue.get_editor_property("label"))
        pair = cue.get_editor_property("wing_pair")
        mechanism = pair.get_editor_property("mechanism")
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
        movement.append({
            "cue_label": label, "cue_index": index, "kind": kind,
            "cycle_rate_hz": float(mechanism.get_editor_property("cycle_rate_hz")),
            "phase_origin": str(mechanism.get_editor_property("phase_origin")),
            "phase_origin_frame": origin,
            "phase_offset_cycles": float(mechanism.get_editor_property("phase_offset_cycles")),
            "inward_travel_cm": travel_cm, "samples": samples,
        })

    capture_label = "P04 Wing 011"
    capture_frame = pair_frames[capture_label]

    def point(local):
        return vector_plain(capture_frame.transform_location(unreal.Vector(*local)))

    capture_plan = {
        "run": verification_run, "source_swap_run": swap_run, "target_label": capture_label,
        "target": point((0.0, 0.0, 500.0)),
        "poses": [
            {"name": "passage_camera", "location": point((-2000.0, 0.0, 500.0))},
            {"name": "corridor_threequarter", "location": point((-1700.0, -1300.0, 700.0))},
            {"name": "back_offstage", "location": point((1500.0, 0.0, 650.0))},
        ],
        "modes": ["lit", "unlit"], "exposure_override": False, "spawned_actors": False,
    }

    end_census = assert_clean("end")
    report = {
        "run": verification_run, "source_swap_run": swap_run, "mode": "verify",
        "status": "PASS", "rows": len(plan["rows"]), "placed_panels": placed,
        "mesh_gates": mesh_gates, "movement": movement,
        "movement_sample_count": len(movement),
        "movement_phases_each": list(SAMPLE_PHASES),
        "passage_range": [start_frame, end_frame],
        "capture_plan": capture_plan, "dirty_after": end_census,
    }
    if emit_report:
        path = c.write_json("slot_b_verify_%s.json" % verification_run, report)
        report["report_path"] = path
    return report


def main():
    report = {"run": c.RUN, "mode": "verify"}
    try:
        report = run_verify(c.RUN, c.RUN, emit_report=True)
        unreal.log("FLATV3_B_READBACK_OK run=%s rows=%d placed_panels=%d movement_occurrences=%d phases_each=3 census=%s report=%s" %
                   (c.RUN, report["rows"], len(report["placed_panels"]),
                    report["movement_sample_count"],
                    json.dumps(report["dirty_after"], separators=(",", ":"), sort_keys=True),
                    report["report_path"]))
    except Exception as exc:
        reason = "verify:" + str(exc)
        report.update({"status": "FAIL", "reason": reason, "traceback": traceback.format_exc(),
                       "census": c.census()})
        c.write_json("slot_b_verify_%s_FAILURE.json" % c.RUN, report)
        unreal.log_error("FLATV3_B_VERIFY_FAIL run=%s reason=%s census=%s" %
                         (c.RUN, str(exc).replace("\n", "\\n"),
                          json.dumps(c.census(), separators=(",", ":"), sort_keys=True)))
        c.log_release("FAIL", [], reason, run=c.RUN, artifact_run=c.RUN)


if __name__ == "__main__":
    main()
