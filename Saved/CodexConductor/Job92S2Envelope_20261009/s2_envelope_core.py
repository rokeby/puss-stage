"""Pure planning helpers for Codex job 92.  No Unreal import."""
import hashlib
import json
import math


def enum_name(value):
    """UE 5.8 enums stringify as '<E.V: n>'; return the stable member name."""
    text = str(value)
    if text.startswith("<") and ":" in text:
        text = text[1:text.index(":")]
    return text.rsplit(".", 1)[-1].strip(">")


def round_up(value, quantum):
    return math.ceil(float(value) / float(quantum)) * float(quantum)


def proposal(bounds, margin_side=300.0, margin_top=300.0, quantum=100.0,
             min_half_width=2500.0, min_height=4500.0, min_lattice=2800.0):
    """bounds are hangar-root-local cm: {min:[x,y,z], max:[x,y,z]}."""
    half_w = round_up(max(abs(bounds["min"][1]), abs(bounds["max"][1])) + margin_side, quantum)
    height = round_up(bounds["max"][2] + margin_top, quantum)
    lattice = round_up(bounds["max"][2] + margin_top, quantum)
    return {"half_width_cm": max(min_half_width, half_w),
            "height_cm": max(min_height, height),
            "lattice_landed_z_cm": max(min_lattice, lattice),
            "content_clearance_side_cm": margin_side,
            "content_clearance_top_cm": margin_top}


def rig_clear(bounds, landed_z, rest_z, height, top_margin=300.0, roof_margin=200.0,
              rail_top_offset=51.0):
    return (bounds["max"][2] <= landed_z - top_margin and
            rest_z + rail_top_offset <= height - roof_margin)


def contains(bounds, half_width, height, margin_side=0.0, margin_top=0.0):
    return (bounds["min"][1] >= -half_width + margin_side and
            bounds["max"][1] <= half_width - margin_side and
            bounds["max"][2] <= height - margin_top and bounds["min"][2] >= -5.0)


def remap_value(value, old_landed, old_rest, new_landed, new_rest, tol=0.01):
    if abs(float(value) - old_landed) <= tol:
        return float(new_landed)
    if abs(float(value) - old_rest) <= tol:
        return float(new_rest)
    raise ValueError("unmapped lattice Z %.6f" % float(value))


def target_actor(row, old, new):
    """Return root-local location and actor scale.  Labels select dimensions, never array order."""
    label = row["label"]
    loc = list(row["root_local"])
    scale = list(row["scale"])
    wr = new["half_width_cm"] / old["half_width_cm"]
    hr = new["height_cm"] / old["height_cm"]
    loc[1] *= wr
    wall_t = float(old.get("wall_thickness_cm", 50.0))
    door_w = float(old.get("door_width_cm", 300.0))

    if label in ("S2 Hangar Left Wall Hinge", "S2 Hangar Left Wall"):
        loc[1] = -(new["half_width_cm"] + wall_t / 2.0)
    elif label in ("S2 Hangar Right Wall Hinge", "S2 Hangar Right Wall"):
        loc[1] = new["half_width_cm"] + wall_t / 2.0
    elif label in ("S2 Hangar Far Wall Left of Exit", "S2 Hangar Far Wall Right of Exit"):
        sign = -1.0 if "Left" in label else 1.0
        old_side = old["half_width_cm"] + wall_t - door_w / 2.0
        new_side = new["half_width_cm"] + wall_t - door_w / 2.0
        loc[1] = sign * (new["half_width_cm"] + wall_t + door_w / 2.0) / 2.0
        scale[1] *= new_side / old_side

    if label in ("S2 Hangar Left Wall", "S2 Hangar Right Wall"):
        loc[2] += (new["height_cm"] - old["height_cm"]) / 2.0
        scale[2] *= hr
    elif label == "S2 Hangar Far Wall Above Exit":
        door_h = float(old.get("door_height_cm", 450.0))
        loc[2] += (new["height_cm"] - old["height_cm"]) / 2.0
        scale[2] *= ((new["height_cm"] - door_h) / (old["height_cm"] - door_h))
        scale[1] *= ((new["half_width_cm"] + wall_t) / (old["half_width_cm"] + wall_t))
    elif label == "S2 Hangar Roof Hinge":
        loc[2] += new["height_cm"] - old["height_cm"]
    elif label == "S2 Hangar Pinned Exposure":
        loc[2] += (new["height_cm"] - old["height_cm"]) / 2.0
        scale[1] *= wr
        scale[2] *= hr
    elif label == "S2 Hangar Lattice Fly":
        loc[2] = float(new["lattice_landed_z_cm"])

    width_mesh = ("Hangar Floor" in label or label == "S2 Hangar Apron" or
                  label == "S2 Hangar Roof" or "Lattice Beam" in label)
    if width_mesh:
        scale[1] *= wr
    return {"root_local": loc, "scale": scale}


def plan_digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
