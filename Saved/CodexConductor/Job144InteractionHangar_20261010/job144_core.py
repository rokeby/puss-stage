"""Pure planning helpers for Job 144.  This module imports no Unreal API."""
from __future__ import print_function

import copy
import hashlib
import json
import math
import re


class PlanError(ValueError):
    pass


DEFAULTS = {
    "interaction": 2,
    "dark_setup_frames": 75,
    "camera_settle_frames": 100,
    "shadow_fade_frames": 12,
    "shadow_end_lead_frames": 1,
    "scene_tail_black_frames": 25,
    "curtain_wall_gap_cm": 50.0,
    "curtain_width_cm": 480.0,
    "curtain_height_cm": 270.0,
    "curtain_frame_margin_cm": 20.0,
    "shadow_card_gap_cm": 2.0,
    "camera_focal_mm": 35.0,
    "camera_sensor_width_mm": 23.76,
    "camera_distance_override_cm": None,
    "camera_parent_runtime_world": None,
    "spot_side": "front",
    "spot_throw_cm": 3000.0,
    "spot_rear_min_clearance_cm": 3200.0,
    "spot_elevation_deg": 20.0,
    "spot_intensity_cd": 7482.804063965048,
    "spot_kelvin": 2800.0,
    "spot_attenuation_radius_cm": 4500.0,
    "spot_outer_cone_deg": 3.433630362450522,
    "spot_inner_cone_deg": 2.9185858080829434,
    "spot_source_radius_cm": 2.0,
    "hide_actor_labels": [],
    "hide_actor_paths": [],
    "hide_actor_tags": [],
    "visibility_conflict_policy": "SAFE_SKIP",
    "approved_shadow_source_labels": [],
    "approved_inventory_digest": "",
    "wall_label": "AUTO",
    "keep_label_regex": [
        r"^S[23] Hangar (Root|.*Wall|Roof|Floor|Lattice)",
        r"Sleight|Curtain|Drape|Camera|Shadow|Puppet|Gobo|Boy|Cat|Transition",
    ],
}


def stable(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def digest(value):
    return hashlib.sha256(stable(value).encode("utf-8")).hexdigest()


def canonical_name(value):
    return re.sub(r"\s*(?:\(\d+\)|_\d+|\s+\d+)$", "", str(value).strip())


def channel_name(value):
    return re.sub(r"_\d+$", "", str(value))


def merged_params(raw):
    out = copy.deepcopy(DEFAULTS)
    out.update(copy.deepcopy(raw or {}))
    out["interaction"] = int(out["interaction"])
    if out["interaction"] not in (2, 3):
        raise PlanError("INTERACTION_MUST_BE_2_OR_3")
    for key in ("dark_setup_frames", "camera_settle_frames", "shadow_fade_frames",
                "shadow_end_lead_frames", "scene_tail_black_frames"):
        out[key] = int(out[key])
        if out[key] < 1:
            raise PlanError("POSITIVE_FRAME_VALUE|%s" % key)
    for key in ("curtain_wall_gap_cm", "curtain_width_cm", "curtain_height_cm",
                "curtain_frame_margin_cm", "shadow_card_gap_cm", "camera_focal_mm", "camera_sensor_width_mm",
                "spot_throw_cm", "spot_rear_min_clearance_cm", "spot_elevation_deg",
                "spot_intensity_cd", "spot_kelvin", "spot_attenuation_radius_cm",
                "spot_outer_cone_deg", "spot_inner_cone_deg", "spot_source_radius_cm"):
        out[key] = float(out[key])
    if out["camera_distance_override_cm"] is not None:
        out["camera_distance_override_cm"] = float(out["camera_distance_override_cm"])
    parent_world = out.get("camera_parent_runtime_world")
    if parent_world is not None:
        if not isinstance(parent_world, dict) or not str(parent_world.get("label", "")).strip():
            raise PlanError("CAMERA_PARENT_RUNTIME_LABEL")
        for key in ("location", "rotation"):
            values = parent_world.get(key)
            if not isinstance(values, list) or len(values) != 3:
                raise PlanError("CAMERA_PARENT_RUNTIME_%s" % key.upper())
            parent_world[key] = [float(x) for x in values]
        parent_world["label"] = str(parent_world["label"])
    if out["spot_side"] not in ("front", "rear"):
        raise PlanError("SPOT_SIDE|%s" % out["spot_side"])
    out["visibility_conflict_policy"] = str(out["visibility_conflict_policy"]).upper()
    if out["visibility_conflict_policy"] not in ("SAFE_SKIP", "REUSE_EXISTING"):
        raise PlanError("VISIBILITY_CONFLICT_POLICY|%s" % out["visibility_conflict_policy"])
    out["hide_actor_labels"] = sorted(set(str(x) for x in out["hide_actor_labels"]))
    out["hide_actor_paths"] = sorted(set(str(x) for x in out["hide_actor_paths"]))
    out["hide_actor_tags"] = sorted(set(str(x) for x in out["hide_actor_tags"]))
    out["approved_shadow_source_labels"] = sorted(set(str(x) for x in out["approved_shadow_source_labels"]))
    out["keep_label_regex"] = [str(x) for x in out["keep_label_regex"]]
    return out


def interp(keys, frame, default=0.0):
    rows = sorted([[int(x[0]), float(x[1])] for x in keys])
    if not rows:
        return float(default)
    if frame <= rows[0][0]:
        return rows[0][1]
    if frame >= rows[-1][0]:
        return rows[-1][1]
    for left, right in zip(rows, rows[1:]):
        if left[0] <= frame <= right[0]:
            if left[0] == right[0]:
                return right[1]
            t = (frame - left[0]) / float(right[0] - left[0])
            return left[1] + (right[1] - left[1]) * t
    return rows[-1][1]


def smoothstep(value):
    t = max(0.0, min(1.0, float(value)))
    return t * t * (3.0 - 2.0 * t)


def angle_lerp(left, right, value):
    delta = (float(right) - float(left) + 180.0) % 360.0 - 180.0
    return float(left) + delta * value


def camera_distance(params):
    if params.get("camera_distance_override_cm") is not None:
        return float(params["camera_distance_override_cm"])
    half = 0.5 * (params["curtain_width_cm"] + 2.0 * params["curtain_frame_margin_cm"])
    fov = 2.0 * math.atan(params["camera_sensor_width_mm"] / (2.0 * params["camera_focal_mm"]))
    return half / math.tan(fov / 2.0)


def _unit_yaw(yaw):
    angle = math.radians(float(yaw))
    return [math.cos(angle), math.sin(angle), 0.0]


def _add(a, b, scale=1.0):
    return [float(a[i]) + float(b[i]) * float(scale) for i in range(3)]


def look_rotation(origin, target):
    delta = [float(target[i]) - float(origin[i]) for i in range(3)]
    horizontal = math.hypot(delta[0], delta[1])
    return {"roll": 0.0, "pitch": math.degrees(math.atan2(delta[2], horizontal)),
            "yaw": math.degrees(math.atan2(delta[1], delta[0]))}


def select_back_wall(walls, wall_label="AUTO"):
    if wall_label != "AUTO":
        rows = [r for r in walls if r["label"] == wall_label]
        if len(rows) != 1:
            raise PlanError("BACK_WALL_LABEL_COUNT|%s|%d" % (wall_label, len(rows)))
        return rows[0]
    if not walls:
        raise PlanError("NO_BACK_WALL_CANDIDATES")
    # Live inventory supplies root-local centre X.  The farthest positive X is
    # the back wall; ties are refused rather than guessed.
    ordered = sorted(walls, key=lambda r: float(r["root_local_center"][0]), reverse=True)
    if len(ordered) > 1 and abs(float(ordered[0]["root_local_center"][0]) -
                                float(ordered[1]["root_local_center"][0])) < 1.0:
        raise PlanError("BACK_WALL_AMBIGUOUS|%s|%s" % (ordered[0]["label"], ordered[1]["label"]))
    return ordered[0]


def inventory_plan(actor_rows, params):
    by_path = {}
    by_label = {}
    for row in actor_rows:
        path = row.get("path")
        if not path or path in by_path:
            raise PlanError("ACTOR_PATHS_NOT_UNIQUE|%s" % path)
        by_path[path] = row
        by_label.setdefault(row["label"], []).append(row)
    selected = {}
    missing_paths = [x for x in params["hide_actor_paths"] if x not in by_path]
    if missing_paths:
        raise PlanError("HIDE_PATHS_MISSING|%s" % missing_paths)
    for path in params["hide_actor_paths"]:
        selected[path] = by_path[path]
    for label in params["hide_actor_labels"]:
        rows = by_label.get(label, [])
        if len(rows) != 1:
            raise PlanError("HIDE_LABEL_NOT_UNIQUE|%s|%d|%s" %
                            (label, len(rows), sorted(r.get("path") for r in rows)))
        selected[rows[0]["path"]] = rows[0]
    for tag in params["hide_actor_tags"]:
        rows = [r for r in actor_rows if tag in r.get("tags", [])]
        if not rows:
            raise PlanError("HIDE_TAG_MISSING|%s" % tag)
        for row in rows:
            selected[row["path"]] = row
    bad = []
    for row in selected.values():
        if any(re.search(pattern, row["label"], re.I) for pattern in params["keep_label_regex"]):
            bad.append({"path": row["path"], "label": row["label"]})
    if bad:
        raise PlanError("HIDE_LIST_CONTAINS_INFRASTRUCTURE|%s" % bad)
    candidates = [r for r in actor_rows if r.get("scene_candidate") and not
                  any(re.search(pattern, r["label"], re.I) for pattern in params["keep_label_regex"])]
    census = {"all": actor_rows, "candidate_hide": candidates,
              "approved_hide": [selected[x] for x in sorted(selected)]}
    census["digest"] = digest({"all": [[r.get("path"), r["label"], r.get("outer_level"), r.get("class")]
                                         for r in actor_rows],
                                "candidate": [[r.get("path"), r["label"]] for r in candidates]})
    return census


def visibility_keys(start, end):
    if end <= start + 1:
        raise PlanError("VISIBILITY_RANGE_TOO_SHORT")
    # MovieSceneVisibilityTrack's bool channel stores VISIBLE state even though
    # the property is AActor::bHidden: False means hidden.
    return [[int(start), False], [int(end) - 1, False], [int(end), True]]


def merge_visibility_keys(existing, start, end):
    """Replace only this interaction span and preserve keys outside it."""
    wanted = visibility_keys(start, end)
    outside = [[int(frame), bool(value)] for frame, value in existing
               if int(frame) < int(start) or int(frame) > int(end)]
    return sorted(outside + wanted, key=lambda row: int(row[0]))


def merge_camera(keys, start, settle, hold_end, target, rotation=False):
    if not (start < settle < hold_end):
        raise PlanError("CAMERA_FRAME_ORDER")
    initial = interp(keys, start)
    out = [[f, v] for f, v in keys if int(f) < start or int(f) >= hold_end]
    for frame in range(start, settle + 1):
        t = smoothstep((frame - start) / float(settle - start))
        value = angle_lerp(initial, target, t) if rotation else initial + (target - initial) * t
        out.append([frame, value])
    out.append([hold_end - 1, float(target)])
    return sorted(out, key=lambda x: int(x[0]))


def offset_curtain(keys, begin, end, delta):
    out = []
    for frame, value in keys:
        out.append([int(frame), float(value) + (float(delta) if begin <= int(frame) < end else 0.0)])
    if not any(begin <= int(f) < end for f, _ in keys):
        out.extend([[begin, interp(keys, begin) + delta], [end - 1, interp(keys, end - 1) + delta]])
    return sorted(out, key=lambda x: int(x[0]))


def validate_cuts(cuts, bindings, world_labels):
    by_guid = {r["guid"]: r for r in bindings}
    rows = []
    for cut in cuts:
        if not cut.get("active", True):
            continue
        binding = by_guid.get(cut["guid"])
        if binding is None:
            raise PlanError("CUT_BINDING_MISSING|%s" % cut["guid"])
        name = canonical_name(binding["name"])
        if not binding.get("spawnable"):
            count = sum(1 for x in world_labels if canonical_name(x) == name)
            if count != 1:
                raise PlanError("CUT_NOT_RESOLVED_IN_SHOW_LEVEL|%s|%d" % (name, count))
        rows.append({"range": cut["range"], "guid": cut["guid"], "binding": name,
                     "resolution": "spawnable" if binding.get("spawnable") else "one_show_level_actor"})
    if not rows:
        raise PlanError("NO_ACTIVE_CAMERA_CUTS")
    return rows


def make_plan(snapshot, params):
    params = merged_params(params)
    if snapshot.get("fade_tracks", {"interaction": 0, "scene": 0}) != {"interaction": 0, "scene": 0}:
        raise PlanError("FADE_TRACK_CONFLICT|%s" % snapshot.get("fade_tracks"))
    start, end = [int(x) for x in snapshot["playback"]]
    sleight = int(snapshot["markers"]["CST sleight"])
    hung = int(snapshot["markers"]["CST curtain hung"])
    settle = start + params["camera_settle_frames"]
    # Job 89/Gary: the curtain must already be hung before the shadow spot
    # begins to reveal it.
    reveal = max(settle, start + params["dark_setup_frames"], hung + 1)
    shadow_end = sleight - params["shadow_end_lead_frames"]
    if not (start < hung <= reveal < shadow_end < sleight < end):
        raise PlanError("BEAT_ORDER|%s" % [start, hung, reveal, shadow_end, sleight, end])

    wall = select_back_wall(snapshot["wall_candidates"], params["wall_label"])
    wall_normal = wall.get("interior_normal") or [-x for x in _unit_yaw(snapshot["curtain_pose"]["yaw"])]
    wall_point = wall["interior_point"]
    curtain = copy.deepcopy(snapshot["curtain_pose"])
    curtain["loc"] = _add(wall_point, wall_normal, params["curtain_wall_gap_cm"])
    curtain["loc"][2] = float(wall["bounds_min"][2])

    forward = _unit_yaw(curtain["yaw"])
    centre = _add(curtain["loc"], [0.0, 0.0, 1.0], params["curtain_height_cm"] * 0.5)
    cam_dist = camera_distance(params)
    camera_loc = _add(centre, forward, -cam_dist)
    camera_rot = look_rotation(camera_loc, centre)
    target_world = {"loc": camera_loc, "roll": camera_rot["roll"],
                    "pitch": camera_rot["pitch"], "yaw": camera_rot["yaw"]}

    if params["spot_side"] == "rear":
        clearance = float(wall.get("rear_clearance_cm", 0.0))
        if clearance < params["spot_rear_min_clearance_cm"]:
            raise PlanError("REAR_THROW_CLEARANCE|have=%.1f|need=%.1f" %
                            (clearance, params["spot_rear_min_clearance_cm"]))
        spot_loc = _add(centre, forward, params["spot_throw_cm"])
    else:
        spot_loc = _add(centre, forward, -params["spot_throw_cm"])
    spot_rot = look_rotation(spot_loc, centre)

    half_cone = math.radians(params["spot_outer_cone_deg"])
    lit_diameter = 2.0 * params["spot_throw_cm"] * math.tan(half_cone)
    warnings = []
    # The established I2/I3 device is a circular 360 cm pool within a wider
    # 480 cm curtain/card, not a full-width wash.  Height is the hard coverage
    # gate; horizontal negative space is intentional.
    required_diameter = params["curtain_height_cm"]
    if lit_diameter + 1.0e-4 < required_diameter:
        warnings.append("SPOT_DIAMETER_SHORT|lit=%.1f|required=%.1f" % (lit_diameter, required_diameter))
    if cam_dist < 100.0:
        warnings.append("CAMERA_TOO_CLOSE|%.1f" % cam_dist)
    if params["spot_attenuation_radius_cm"] < params["spot_throw_cm"]:
        warnings.append("SPOT_RADIUS_SHORT|radius=%.1f|throw=%.1f" %
                        (params["spot_attenuation_radius_cm"], params["spot_throw_cm"]))
    missing_shadow = [x for x in params["approved_shadow_source_labels"] if x not in snapshot["puppet_bindings"]]
    if missing_shadow:
        raise PlanError("SHADOW_SOURCE_LABELS_MISSING|%s" % missing_shadow)
    if not params["approved_shadow_source_labels"]:
        warnings.append("SHADOW_SOURCE_NOT_APPROVED|review puppet_bindings; this staging tool does not invent a performance")

    # Job 173 proved that merely approving a card label is insufficient: both
    # cards were still keyed not to spawn and retained their old-stage pose.
    # Make the approved source an explicit, reversible part of this plan.
    binding_by_name = {canonical_name(row["name"]): row for row in snapshot["bindings"]}
    source_loc = _add(centre, forward, -params["shadow_card_gap_cm"])
    source_pose = {"Location.X": source_loc[0], "Location.Y": source_loc[1], "Location.Z": source_loc[2],
                   "Rotation.X": curtain["roll"], "Rotation.Y": curtain["pitch"],
                   "Rotation.Z": curtain["yaw"]}
    shadow_sources = []
    for label in params["approved_shadow_source_labels"]:
        binding = binding_by_name.get(canonical_name(label))
        if binding is None:
            raise PlanError("SHADOW_SOURCE_BINDING_MISSING|%s" % label)
        if not binding.get("spawnable"):
            raise PlanError("SHADOW_SOURCE_NOT_SPAWNABLE|%s" % label)
        spawn_tracks = [track for track in binding.get("tracks", [])
                        if track.get("class") == "MovieSceneSpawnTrack"]
        transform_tracks = [track for track in binding.get("tracks", [])
                            if track.get("class") == "MovieScene3DTransformTrack"]
        if len(spawn_tracks) != 1 or len(spawn_tracks[0].get("sections", [])) != 1:
            raise PlanError("SHADOW_SOURCE_SPAWN_TRACK|%s" % label)
        if len(transform_tracks) != 1 or len(transform_tracks[0].get("sections", [])) != 1:
            raise PlanError("SHADOW_SOURCE_TRANSFORM_TRACK|%s" % label)
        shadow_sources.append({"label": label, "guid": binding["guid"], "pose": copy.deepcopy(source_pose),
                               "spawn_keys": [[max(start, reveal - 25), True], [sleight + 1, False]]})

    inventory = inventory_plan(snapshot["actors"], params)
    existing_by_guid = {row["guid"]: row for row in snapshot["bindings"]}
    visibility_actors = []
    visibility_conflicts = []
    for actor_row in inventory["approved_hide"]:
        action_row = copy.deepcopy(actor_row)
        conflicts = []
        for guid in actor_row.get("sequence_binding_guids", []):
            binding = existing_by_guid.get(guid)
            if binding:
                for track in binding.get("tracks", []):
                    if track.get("class") == "MovieSceneVisibilityTrack":
                        conflicts.append({"guid": guid, "binding": binding.get("name"),
                                          "track_index": int(track.get("track_index", 0)),
                                          "property": track.get("property"),
                                          "sections": copy.deepcopy(track.get("sections", []))})
        if conflicts:
            conflict = {"path": actor_row["path"], "label": actor_row["label"],
                        "policy": params["visibility_conflict_policy"], "tracks": conflicts}
            if params["visibility_conflict_policy"] == "SAFE_SKIP":
                conflict["action"] = "SKIP_ACTOR_AND_REPORT"
                visibility_conflicts.append(conflict)
                continue
            if len(conflicts) != 1 or len(conflicts[0]["sections"]) != 1 or \
                    len(conflicts[0]["sections"][0].get("channels", [])) != 1:
                raise PlanError("VISIBILITY_TRACK_REUSE_AMBIGUOUS|%s|%s" %
                                (actor_row["path"], stable(conflicts)))
            track = conflicts[0]
            if track.get("property") not in ("bHidden", ""):
                raise PlanError("VISIBILITY_TRACK_REUSE_PROPERTY|%s|%s" %
                                (actor_row["path"], track.get("property")))
            section = track["sections"][0]
            channel = section["channels"][0]
            action_row["visibility_action"] = "REUSE_EXISTING"
            action_row["visibility_locator"] = [track["guid"], track["track_index"],
                                                  int(section.get("section_index", 0)),
                                                  int(channel.get("channel_index", 0))]
            action_row["visibility_keys"] = merge_visibility_keys(channel.get("keys", []), start, end)
            action_row["visibility_section_range"] = [
                min(int(section["range"][0]), start), max(int(section["range"][1]), end + 1)]
            conflict["action"] = "REUSE_AND_EXTEND_EXISTING_TRACK"
            visibility_conflicts.append(conflict)
        else:
            action_row["visibility_action"] = "CREATE_TRACK"
        visibility_actors.append(action_row)
    cuts = validate_cuts(snapshot["cuts"], snapshot["bindings"], snapshot["world_labels"])
    shadow_frame = (reveal + shadow_end) // 2
    shadow_cuts = [row for row in cuts
                   if int(row["range"][0]) <= shadow_frame < int(row["range"][1])]
    if len(shadow_cuts) != 1:
        raise PlanError("SHADOW_CAMERA_CUT_COUNT|frame=%d|count=%d" % (shadow_frame, len(shadow_cuts)))
    if inventory["approved_hide"] and params["approved_inventory_digest"] != inventory["digest"]:
        raise PlanError("INVENTORY_DIGEST_NOT_APPROVED|%s" % inventory["digest"])

    spot_fade_end = reveal + params["shadow_fade_frames"]
    if spot_fade_end >= shadow_end:
        raise PlanError("SHADOW_WINDOW_TOO_SHORT")
    plan = {
        "interaction": params["interaction"], "sequence": snapshot["sequence"],
        "scene_wrapper": snapshot["scene_wrapper"], "playback": [start, end],
        "beats": {"hung": hung, "camera_settle": settle, "reveal": reveal,
                  "spot_fade_end": spot_fade_end, "shadow_end": shadow_end, "sleight": sleight},
        "wall": wall, "curtain_target": curtain, "camera_target_world": target_world,
        "camera_distance_cm": cam_dist,
        "spot": {"name": "Job144 I%d Shadow Spot" % params["interaction"], "side": params["spot_side"],
                 "loc": spot_loc, "roll": spot_rot["roll"], "pitch": spot_rot["pitch"], "yaw": spot_rot["yaw"],
                 "intensity_keys": [[start, 0.0], [reveal, 0.0], [spot_fade_end, params["spot_intensity_cd"]],
                                    [shadow_end, params["spot_intensity_cd"]], [sleight, 0.0]],
                 "spawn_keys": [[max(start, reveal - 25), True], [sleight + 1, False]],
                 "lit_diameter_cm": lit_diameter},
        "blackout_keys": [[start, 1.0], [settle, 1.0], [reveal, 0.0]],
        "scene_tail_black_keys": [[int(snapshot["scene_playback"][1]) - params["scene_tail_black_frames"], 0.0],
                                  [int(snapshot["scene_playback"][1]) - 1, 1.0]],
        "visibility": {"property": "bHidden", "path": "bHidden", "channel_semantics": "VISIBLE",
                       "policy": params["visibility_conflict_policy"],
                       "keys": visibility_keys(start, end), "actors": visibility_actors,
                       "conflicts": visibility_conflicts,
                       "skipped": [row for row in visibility_conflicts
                                   if row["action"] == "SKIP_ACTOR_AND_REPORT"]},
        "inventory": inventory, "cut_resolution": cuts, "shadow_frame": shadow_frame,
        "shadow_camera": shadow_cuts[0], "puppet_bindings": snapshot["puppet_bindings"],
        "approved_shadow_sources": params["approved_shadow_source_labels"],
        "shadow_sources": shadow_sources,
        "existing_tools": snapshot.get("existing_tools", {}), "warnings": warnings, "params": params,
        "save_packages": sorted([snapshot["sequence"], snapshot["scene_wrapper"]]),
    }
    plan["digest"] = digest(plan)
    return plan
