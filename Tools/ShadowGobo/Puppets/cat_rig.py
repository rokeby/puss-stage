"""Jointed cut-paper shadow puppet: Puss, a large tomcat in left-facing profile.

The construction deliberately follows ``boy_rig.py``: every part owns an outline
and local knife cuts, poses only transform those local parts, and the assembled
shadow is the product of the individual transmissions.  Cuts therefore disappear
when another piece of card passes in front of them, as they do in a real puppet.

    python cat_rig.py <out_dir>

Outputs are review material only.  No handheld wobble is baked into the GIF.
"""
from __future__ import annotations

import argparse
import copy
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).parent))
from puppet_cut import chain, punch, slit  # noqa: E402


# -------------------------------------------------------------------------------------------------
# Gary's look controls.  Geometry, joint angles, render values and pose choices are deliberately
# collected in plain dictionaries here rather than hidden in drawing code.

LOOK = {
    "ink_rgb": (24, 22, 25),
    "cool_rgb": (196, 228, 236),
    "warm_rgb": (236, 178, 168),
    "shadow_blur": 1.15,
    "rod_width": 5.0,
    "whisker_width": 3.2,
    "cut_margin": 6.0,
    "supersample": 3,
}

CLI_DEFAULTS = {
    "fps": 8,
    "hold_frames": 8,
    "move_frames": 3,
    "shadow_blur": LOOK["shadow_blur"],
    "rod_width": LOOK["rod_width"],
    "whisker_width": LOOK["whisker_width"],
}

RIG = {
    "root": (560.0, 760.0),
    "neck": (-62.0, -402.0),
    "shoulder": (-116.0, -300.0),
    "tail_base": (150.0, -112.0),
    "head_scale": (1.25, 1.23),
    "upper_leg_length": 178.0,
    "paw_length": 170.0,
    "tail_lengths": (180.0, 190.0, 340.0),
    # A tomcat's tail is a solid card silhouette, not a pair of stroked rails.
    # The 88-unit root is broader than the front leg at its shoulder; the
    # 42-unit tip retains 47.7% of that weight before its rounded cap.
    "tail_widths": ((88.0, 80.0), (82.0, 66.0), (68.0, 42.0)),
}

VIEW = {"x0": 105.0, "y0": 25.0, "scale": 0.86, "w": 710, "h": 840}
FACE_VIEW = {"x0": 175.0, "y0": 35.0, "scale": 1.0, "w": 430, "h": 410}

BODY_SHAPE = {
    "start": (-70.0, -420.0),
    "segments": [
        ((18, -446), (112, -402), (152, -318)),
        ((222, -265), (252, -112), (211, 16)),
        ((223, 73), (197, 116), (151, 128)),                  # rounded sitting thigh
        ((113, 143), (62, 149), (19, 140)),                   # grounded hind paw
        ((-9, 134), (-24, 119), (-18, 103)),
        ((-8, 88), (24, 82), (55, 79)),                       # paw-to-belly notch
        ((17, 67), (-22, 39), (-42, 0)),
        ((-90, -8), (-132, -42), (-148, -96)),
        ((-172, -168), (-168, -270), (-126, -338)),
        ((-105, -380), (-88, -410), (-70, -420)),
    ],
}

EAR_OUTLINES = {
    # The forward ear is torn: the inward nick is part of the outline, not a cut that could sever card.
    "up": [(56, -120), (48, -212), (12, -174), (-15, -230), (-31, -190),
           (-46, -203), (-72, -158), (-92, -145)],
    "flat": [(56, -120), (72, -159), (16, -149), (-16, -170), (-43, -154),
             (-57, -166), (-82, -150), (-92, -145)],
    "one_swivelled": [(56, -120), (47, -210), (10, -171), (-22, -177), (-50, -145),
                      (-68, -163), (-86, -148), (-92, -145)],
}

HEAD_SHAPE = {
    "back_start": (32.0, 42.0),
    "back_segments": [((79, 7), (94, -69), (62, -121))],
    "forehead_segments": [
        ((-115, -148), (-151, -137), (-166, -108)),
        ((-178, -103), (-196, -100), (-214, -90)),  # short cat nose, unique left-most point
        ((-210, -84), (-202, -78), (-191, -73)),
    ],
    "mouth_paths": {
        "closed": [(-197, -58), (-189, -49), (-197, -40), (-187, -31), (-169, -26),
                   (-177, -14), (-160, 2)],
        "meow": [(-199, -58), (-185, -49), (-160, -45), (-178, -24), (-151, -28),
                 (-169, -8), (-156, 5)],
    },
    "ruff": [(-177, 22), (-154, 18), (-166, 49), (-133, 39), (-145, 75),
             (-105, 58), (-96, 85), (-57, 61), (-35, 69)],
    "neck_segments": [((-1, 81), (24, 62), (32, 42))],
}

FRONT_LEG_SHAPES = {
    "upper": {
        "outline": [(-37, -14), (-50, 46), (-47, 115), (-39, 175), (-18, 194),
                    (2, 181), (21, 196), (42, 172), (47, 104), (45, 38), (31, -17),
                    (7, -34), (-19, -31)],
        "cuts": [slit((-18, 35), (-24, 77), (-20, 121), (-13, 158), 7)],
    },
    "paw": {
        "outline": [(-28, -10), (-32, 47), (-35, 104), (-49, 135), (-43, 166),
                    (-21, 180), (8, 181), (31, 169), (49, 151), (40, 133),
                    (25, 126), (29, 75), (25, 22), (17, -15), (-8, -25)],
        "cuts": [slit((-24, 145), (-7, 151), (11, 153), (30, 146), 6)],
    },
}

TAIL_SPECS = {
    "overlap": 28.0,
    "bows": (22.0, -25.0, 31.0),
    "samples": 28,
    "cap_samples": 10,
    "tip_bulge_amount": 0.16,
    "tip_bulge_centre": 0.78,
    "tip_bulge_spread": 0.13,
}

# Eye cut-outs are paired lobes so the vertical black pupil remains a bar of card.
EYE_CUTS = {
    "open": [
        slit((-147, -105), (-141, -114), (-130, -113), (-125, -103), 13),
        slit((-119, -103), (-113, -113), (-102, -112), (-96, -103), 13),
    ],
    "half": [slit((-148, -101), (-132, -94), (-113, -94), (-96, -101), 8)],
    "shut": [slit((-148, -101), (-132, -90), (-112, -90), (-96, -101), 6)],
    "wide": [
        slit((-145, -104), (-139, -116), (-130, -117), (-125, -103), 14),
        slit((-118, -103), (-113, -117), (-103, -115), (-97, -103), 14),
    ],
}

MOUTH_CUTS = {
    "closed": [slit((-177, -43), (-168, -38), (-158, -32), (-150, -25), 4)],
    "meow": [],
}

EAR_CUTS = {
    "up": [slit((-65, -145), (-56, -158), (-45, -171), (-34, -184), 5)],
    "flat": [],
    "one_swivelled": [],
}

HEAD_FIXED_CUTS = [
    slit((-125, -72), (-111, -58), (-101, -42), (-91, -23), 8),       # cheek scar
    slit((-103, 31), (-86, 42), (-67, 44), (-49, 37), 7),              # jowl/ruff grain
]

BODY_CUTS = [
    slit((-118, -310), (-81, -290), (-55, -250), (-43, -205), 8),      # heavy chest
    slit((102, -310), (137, -250), (155, -174), (151, -96), 8),        # haunch grain
    slit((169, -55), (145, -29), (126, -2), (115, 32), 6),
    slit((18, 119), (52, 128), (87, 128), (121, 119), 5),               # hind toes
]

JAW = {
    "outline": [(-12, -13), (-48, -20), (-81, -14), (-94, 2), (-83, 23),
                (-52, 36), (-16, 30), (7, 14), (10, -5)],
    "cuts": [
        [(-68, -10), (-56, -7), (-61, 8)],                              # fang cut-outs
        [(-37, -10), (-25, -7), (-31, 9)],
    ],
    "hinge": (-135.0, -19.0),
}

WHISKERS = {
    "roots": [(-190.0, -63.0), (-191.0, -52.0), (-184.0, -42.0)],
    "ends": [(-286.0, -92.0), (-294.0, -58.0), (-278.0, -24.0)],
}

REST = {
    "body_lean": 0.0,
    "body_scale": (1.0, 1.0),
    "neck": 0.0,
    "shoulder": 4.0,
    "wrist": -3.0,
    "paw_target": None,
    "tail": (88.0, 40.0, 75.0),
    "jaw": 0.0,
    "face": {"eyes": "open", "ears": "up", "mouth": "closed"},
    "rods": True,
}

POSE_TABLE = {
    "sit_upright": {},
    "sit_proud": {"body_lean": -8.0, "body_scale": (1.05, 1.06), "offset": (-8.0, -22.0),
                  "neck": -23.0, "shoulder": -7.0, "wrist": 1.0,
                  "tail": (-100.0, 20.0, 140.0),
                  "face": {"eyes": "half", "ears": "up"}},
    "loaf_hunched": {"body_lean": 8.0, "body_scale": (1.06, 0.72), "offset": (0.0, 34.0),
                      "neck": 10.0, "shoulder": 78.0, "wrist": -139.0,
                      "tail": (66.0, 57.0, 76.0), "face": {"eyes": "half", "ears": "one_swivelled"}},
    "sit_look_up": {"neck": -25.0, "face": {"eyes": "wide"}},
    "paw_lick": {"neck": 7.0, "paw_target": (-186.0, -35.0),
                 "face": {"eyes": "half", "mouth": "closed"}},
    "washing": {"body_lean": 5.0, "neck": 17.0, "paw_target": (-146.0, -83.0),
                "face": {"eyes": "shut", "ears": "one_swivelled"}},
    "meow": {"neck": -10.0, "jaw": 31.0,
             "face": {"eyes": "half", "ears": "up", "mouth": "meow"}},
    "tail_flick": {"tail": (115.0, -100.0, -100.0),
                   "face": {"eyes": "wide", "ears": "one_swivelled"}},
}

TAIL_FLICK_FRAMES = (
    {"tail": (115.0, -100.0, -100.0)},
    {"tail": (116.0, -102.0, -96.0)},
)

FACE_SHEET = [
    ("eyes open", {"face": {"eyes": "open"}}),
    ("eyes half", {"face": {"eyes": "half"}}),
    ("eyes shut", {"face": {"eyes": "shut"}}),
    ("eyes wide", {"face": {"eyes": "wide"}}),
    ("ears up", {"face": {"ears": "up"}}),
    ("ears flat", {"face": {"ears": "flat"}}),
    ("one swivelled", {"face": {"ears": "one_swivelled"}}),
    ("mouth closed", {"face": {"mouth": "closed"}}),
    ("meow + fangs", {"jaw": 31.0, "face": {"mouth": "meow"}}),
]


# -------------------------------------------------------------------------------------------------
# Local card parts

def body_part():
    return chain(BODY_SHAPE["start"], BODY_SHAPE["segments"]), copy.deepcopy(BODY_CUTS)


def head_outline(ears: str, mouth: str):
    pts = chain(HEAD_SHAPE["back_start"], HEAD_SHAPE["back_segments"])
    pts += [list(p) for p in EAR_OUTLINES[ears]][1:]
    pts += chain(EAR_OUTLINES[ears][-1], HEAD_SHAPE["forehead_segments"])[1:]
    pts += [list(p) for p in HEAD_SHAPE["mouth_paths"][mouth]]
    pts += [list(p) for p in HEAD_SHAPE["ruff"]]
    pts += chain(HEAD_SHAPE["ruff"][-1], HEAD_SHAPE["neck_segments"])[1:]
    return pts


def head_part(face):
    cuts = copy.deepcopy(HEAD_FIXED_CUTS)
    cuts += copy.deepcopy(EAR_CUTS[face["ears"]])
    cuts += copy.deepcopy(EYE_CUTS[face["eyes"]])
    cuts += copy.deepcopy(MOUTH_CUTS[face["mouth"]])
    return head_outline(face["ears"], face["mouth"]), cuts


def jaw_part():
    return copy.deepcopy(JAW["outline"]), copy.deepcopy(JAW["cuts"])


def upper_leg_part():
    d = FRONT_LEG_SHAPES["upper"]
    return copy.deepcopy(d["outline"]), copy.deepcopy(d["cuts"])


def paw_part():
    d = FRONT_LEG_SHAPES["paw"]
    return copy.deepcopy(d["outline"]), copy.deepcopy(d["cuts"])


def _bezier_point(points, amount):
    p0, p1, p2, p3 = (np.asarray(point, dtype=float) for point in points)
    inverse = 1.0 - amount
    return (inverse ** 3 * p0 + 3.0 * inverse ** 2 * amount * p1 +
            3.0 * inverse * amount ** 2 * p2 + amount ** 3 * p3)


def _bezier_tangent(points, amount):
    p0, p1, p2, p3 = (np.asarray(point, dtype=float) for point in points)
    inverse = 1.0 - amount
    tangent = (3.0 * inverse ** 2 * (p1 - p0) +
               6.0 * inverse * amount * (p2 - p1) +
               3.0 * amount ** 2 * (p3 - p2))
    return tangent / (np.linalg.norm(tangent) + 1e-12)


def _round_cap(center, tangent, radius, forward, samples):
    """A semicircle from one sleeve edge to the other, around ``center``."""
    angle = math.atan2(tangent[1], tangent[0])
    if forward:
        values = np.linspace(angle + math.pi / 2.0, angle - math.pi / 2.0, samples)
    else:
        values = np.linspace(angle - math.pi / 2.0, angle - 3.0 * math.pi / 2.0, samples)
    return [(center + radius * np.array([math.cos(value), math.sin(value)])).tolist()
            for value in values]


def tail_part(index):
    """A filled bowed card sleeve with rounded, overlapping joint ends."""
    length = RIG["tail_lengths"][index]
    w0, w1 = RIG["tail_widths"][index]
    ov = TAIL_SPECS["overlap"]
    bow = TAIL_SPECS["bows"][index]
    control = ((0.0, 0.0), (length * 0.28, bow), (length * 0.70, bow), (length, 0.0))
    amounts = np.linspace(0.0, 1.0, TAIL_SPECS["samples"])
    centers = [_bezier_point(control, amount) for amount in amounts]
    tangents = [_bezier_tangent(control, amount) for amount in amounts]
    centers[0] = centers[0] - tangents[0] * ov
    centers[-1] = centers[-1] + tangents[-1] * ov
    widths = np.linspace(w0, w1, len(centers))
    if index == 2:
        # A soft bushy swell before the rounded tip; the endpoint remains the
        # declared 42-unit width so the taper ratio is easy to audit.
        centre = TAIL_SPECS["tip_bulge_centre"]
        spread = TAIL_SPECS["tip_bulge_spread"]
        bell = np.exp(-0.5 * ((amounts - centre) / spread) ** 2)
        bell[-1] = 0.0
        widths *= 1.0 + TAIL_SPECS["tip_bulge_amount"] * bell
    normals = [np.array([-tangent[1], tangent[0]]) for tangent in tangents]
    left = [(center + normal * width / 2.0).tolist()
            for center, normal, width in zip(centers, normals, widths)]
    right = [(center - normal * width / 2.0).tolist()
             for center, normal, width in zip(centers, normals, widths)]
    end_cap = _round_cap(centers[-1], tangents[-1], w1 / 2.0, True,
                         TAIL_SPECS["cap_samples"])[1:-1]
    start_cap = _round_cap(centers[0], tangents[0], w0 / 2.0, False,
                           TAIL_SPECS["cap_samples"])[1:-1]
    outline = left + end_cap + list(reversed(right)) + start_cap

    # Deliberately no centre slit: a slit across the sleeve turns the silhouette
    # into two thin rails and makes the tail read as a hollow loop.
    return outline, []


# -------------------------------------------------------------------------------------------------
# Transforms and pose assembly

def rot(degrees):
    a = math.radians(degrees)
    return np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])


def place(poly, rotation, translation):
    points = np.asarray(poly, dtype=float)
    return (points @ rotation.T + np.asarray(translation, dtype=float)).tolist()


def angle_of(vector):
    """Absolute rotation taking local +y onto ``vector``."""
    x, y = vector
    return math.degrees(math.atan2(-x, y))


def front_leg_ik(shoulder, target):
    """Two-link IK, choosing the left/forward elbow so a raised paw reads in negative space."""
    s = np.asarray(shoulder, dtype=float)
    t = np.asarray(target, dtype=float)
    upper, lower = RIG["upper_leg_length"], RIG["paw_length"]
    delta = t - s
    raw_distance = np.linalg.norm(delta)
    distance = min(max(raw_distance, abs(upper - lower) + 1.0), upper + lower - 1.0)
    direction = delta / (raw_distance + 1e-9)
    cosine = (upper * upper + distance * distance - lower * lower) / (2 * upper * distance)
    elbow_angle = math.acos(max(-1.0, min(1.0, cosine)))
    candidates = []
    for sign in (-1.0, 1.0):
        c, sn = math.cos(sign * elbow_angle), math.sin(sign * elbow_angle)
        upper_dir = np.array([direction[0] * c - direction[1] * sn,
                              direction[0] * sn + direction[1] * c])
        elbow = s + upper_dir * upper
        candidates.append((elbow[0], upper_dir, elbow))
    _, upper_dir, elbow = min(candidates, key=lambda item: item[0])
    return angle_of(upper_dir), angle_of(t - elbow)


def make_pose(name_or_changes="sit_upright", **changes):
    pose = copy.deepcopy(REST)
    if isinstance(name_or_changes, str):
        update = copy.deepcopy(POSE_TABLE[name_or_changes])
        pose["name"] = name_or_changes
    else:
        update = copy.deepcopy(name_or_changes)
        pose["name"] = "custom"
    update.update(copy.deepcopy(changes))
    face = copy.deepcopy(pose["face"])
    face.update(update.pop("face", {}))
    pose.update(update)
    pose["face"] = face
    return pose


def pose_parts(pose):
    """Return ``(name, outline, cuts, z)`` world parts plus rods and whiskers."""
    root = np.asarray(RIG["root"], dtype=float) + np.asarray(pose.get("offset", (0.0, 0.0)))
    body_angle = pose["body_lean"]
    body_rotation = rot(body_angle)
    body_scale = np.diag(pose["body_scale"])
    body_matrix = body_rotation @ body_scale
    body_world = lambda p: np.asarray(p, dtype=float) @ body_matrix.T + root  # noqa: E731

    parts = []

    # Tail is behind the haunch and is a true three-link chain.
    tail_pivot = body_world(RIG["tail_base"])
    cumulative = body_angle
    tail_tip = tail_pivot
    for index, relative_angle in enumerate(pose["tail"]):
        cumulative += relative_angle
        rotation = rot(cumulative)
        outline, cuts = tail_part(index)
        parts.append((f"tail_{index + 1}", place(outline, rotation, tail_pivot),
                      [place(cut, rotation, tail_pivot) for cut in cuts], index))
        tail_pivot = tail_pivot + np.array([RIG["tail_lengths"][index], 0.0]) @ rotation.T
        tail_tip = tail_pivot

    outline, cuts = body_part()
    parts.append(("body", place(outline, body_matrix, root),
                  [place(cut, body_matrix, root) for cut in cuts], 4))

    neck = body_world(RIG["neck"])
    head_rotation = rot(body_angle + pose["neck"])
    head_matrix = head_rotation @ np.diag(RIG["head_scale"])
    outline, cuts = head_part(pose["face"])
    parts.append(("head", place(outline, head_matrix, neck),
                  [place(cut, head_matrix, neck) for cut in cuts], 7))

    if pose["face"]["mouth"] == "meow":
        hinge = np.asarray(JAW["hinge"], dtype=float) @ head_matrix.T + neck
        jaw_rotation = rot(body_angle + pose["neck"] + pose["jaw"]) @ np.diag(RIG["head_scale"])
        outline, cuts = jaw_part()
        parts.append(("lower_jaw", place(outline, jaw_rotation, hinge),
                      [place(cut, jaw_rotation, hinge) for cut in cuts], 8))

    shoulder = body_world(RIG["shoulder"])
    shoulder_absolute = body_angle + pose["shoulder"]
    wrist_relative = pose["wrist"]
    if pose.get("paw_target") is not None:
        target = np.asarray(pose["paw_target"], dtype=float) @ head_matrix.T + neck
        shoulder_absolute, lower_absolute = front_leg_ik(shoulder, target)
        wrist_relative = lower_absolute - shoulder_absolute
    upper_rotation = rot(shoulder_absolute)
    outline, cuts = upper_leg_part()
    parts.append(("front_leg", place(outline, upper_rotation, shoulder),
                  [place(cut, upper_rotation, shoulder) for cut in cuts], 6))
    wrist = shoulder + np.array([0.0, RIG["upper_leg_length"]]) @ upper_rotation.T
    paw_rotation = rot(shoulder_absolute + wrist_relative)
    outline, cuts = paw_part()
    parts.append(("front_paw", place(outline, paw_rotation, wrist),
                  [place(cut, paw_rotation, wrist) for cut in cuts], 9))
    paw_tip = wrist + np.array([0.0, RIG["paw_length"]]) @ paw_rotation.T

    whiskers = []
    for start, end in zip(WHISKERS["roots"], WHISKERS["ends"]):
        whiskers.append([place([start], head_matrix, neck)[0], place([end], head_matrix, neck)[0]])

    rods = []
    if pose.get("rods", True):
        body_rod_start = body_world((78.0, -30.0))
        rods.append([body_rod_start.tolist(), (body_rod_start + np.array([35.0, 390.0])).tolist()])
        rods.append([paw_tip.tolist(), (paw_tip + np.array([-20.0, 315.0])).tolist()])
        rods.append([tail_tip.tolist(), (tail_tip + np.array([85.0, 260.0])).tolist()])
    return sorted(parts, key=lambda item: item[3]), rods, whiskers


def tail_tip_for_pose(pose):
    """Return the centre of the final tail joint for silhouette controls."""
    root = np.asarray(RIG["root"], dtype=float) + np.asarray(pose.get("offset", (0.0, 0.0)))
    body_matrix = rot(pose["body_lean"]) @ np.diag(pose["body_scale"])
    pivot = np.asarray(RIG["tail_base"], dtype=float) @ body_matrix.T + root
    cumulative = pose["body_lean"]
    for length, relative_angle in zip(RIG["tail_lengths"], pose["tail"]):
        cumulative += relative_angle
        pivot = pivot + np.array([length, 0.0]) @ rot(cumulative).T
    return pivot


# -------------------------------------------------------------------------------------------------
# Rendering and SVG

def _image_points(poly, view, ss):
    scale = view["scale"] * ss
    return [((x - view["x0"]) * scale, (y - view["y0"]) * scale) for x, y in poly]


def render_parts(parts, rods=(), whiskers=(), *, view=VIEW, ss=None,
                 rod_width=None, whisker_width=None):
    """Multiply per-part transmissions.  This is intentionally not a painter's cut pass."""
    ss = LOOK["supersample"] if ss is None else ss
    rod_width = LOOK["rod_width"] if rod_width is None else rod_width
    whisker_width = LOOK["whisker_width"] if whisker_width is None else whisker_width
    width, height = int(view["w"] * ss), int(view["h"] * ss)
    transmission = np.ones((height, width), dtype=np.float64)
    for _name, outline, cuts, _z in parts:
        mask = Image.new("L", (width, height), 255)
        draw = ImageDraw.Draw(mask)
        draw.polygon(_image_points(outline, view, ss), fill=0)
        for cut in cuts:
            draw.polygon(_image_points(cut, view, ss), fill=255)
        transmission *= np.asarray(mask, dtype=np.float64) / 255.0

    wires = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(wires)
    scale = view["scale"] * ss
    for line in rods:
        draw.line(_image_points(line, view, ss), fill=0,
                  width=max(1, int(round(rod_width * scale))))
    for line in whiskers:
        draw.line(_image_points(line, view, ss), fill=0,
                  width=max(1, int(round(whisker_width * scale))))
    transmission *= np.asarray(wires, dtype=np.float64) / 255.0
    return Image.fromarray((transmission * 255.0).astype(np.uint8)).resize(
        (view["w"], view["h"]), Image.Resampling.LANCZOS)


def render_pose(pose, *, view=VIEW, ss=None, rod_width=None, whisker_width=None):
    parts, rods, whiskers = pose_parts(pose)
    return render_parts(parts, rods, whiskers, view=view, ss=ss,
                        rod_width=rod_width, whisker_width=whisker_width)


def projected(image, blur=None):
    blur = LOOK["shadow_blur"] if blur is None else blur
    shadow = np.asarray(image.filter(ImageFilter.GaussianBlur(blur)), dtype=np.float64) / 255.0
    height, width = shadow.shape
    x = np.linspace(0.0, 1.0, width)[None, :, None]
    background = np.asarray(LOOK["cool_rgb"]) * (1.0 - x) + np.asarray(LOOK["warm_rgb"]) * x
    background = np.repeat(background, height, axis=0)
    result = background * shadow[..., None] + np.asarray(LOOK["ink_rgb"]) * (1.0 - shadow[..., None])
    return Image.fromarray(result.clip(0, 255).astype(np.uint8))


def svg_for_pose(pose, rod_width=None, whisker_width=None):
    rod_width = LOOK["rod_width"] if rod_width is None else rod_width
    whisker_width = LOOK["whisker_width"] if whisker_width is None else whisker_width
    parts, rods, whiskers = pose_parts(pose)

    def path_data(poly):
        return "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in poly) + " Z"

    lines = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="100 60 830 900" width="230mm" height="250mm">']
    for name, outline, cuts, _z in parts:
        data = path_data(outline) + " " + " ".join(path_data(cut) for cut in cuts)
        lines.append(f'  <path id="{name}" fill="#000" fill-rule="evenodd" d="{data}"/>')
    for index, line in enumerate(whiskers):
        points = " ".join(f"{x:.2f},{y:.2f}" for x, y in line)
        lines.append(f'  <polyline id="whisker_{index + 1}" fill="none" stroke="#000" '
                     f'stroke-width="{whisker_width:.2f}" stroke-linecap="round" points="{points}"/>')
    for index, line in enumerate(rods):
        points = " ".join(f"{x:.2f},{y:.2f}" for x, y in line)
        lines.append(f'  <polyline id="rod_{index + 1}" fill="none" stroke="#000" '
                     f'stroke-width="{rod_width:.2f}" points="{points}"/>')
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


# -------------------------------------------------------------------------------------------------
# Sheets and stepped motion (no handheld wobble)

def _label(image, text):
    ImageDraw.Draw(image).text((12, 10), text, fill=(42, 40, 42))
    return image


def pose_sheet(out_dir, blur, rod_width, whisker_width):
    tile_size = (VIEW["w"], VIEW["h"])
    sheet = Image.new("RGB", (tile_size[0] * 4, tile_size[1] * 2), "white")
    for index, name in enumerate(POSE_TABLE):
        image = projected(render_pose(make_pose(name), rod_width=rod_width,
                                      whisker_width=whisker_width), blur)
        _label(image, name.replace("_", " "))
        sheet.paste(image, ((index % 4) * tile_size[0], (index // 4) * tile_size[1]))
    sheet.save(out_dir / "cat_poses.png")


def face_sheet(out_dir, blur, rod_width, whisker_width):
    sheet = Image.new("RGB", (FACE_VIEW["w"] * 5, FACE_VIEW["h"] * 2), "white")
    for index, (label, changes) in enumerate(FACE_SHEET):
        pose = make_pose(changes)
        image = projected(render_pose(pose, view=FACE_VIEW, rod_width=rod_width,
                                      whisker_width=whisker_width), blur * 0.7)
        _label(image, label)
        sheet.paste(image, ((index % 5) * FACE_VIEW["w"], (index // 5) * FACE_VIEW["h"]))
    sheet.save(out_dir / "cat_faces.png")


def interpolate_pose(a, b, amount):
    result = copy.deepcopy(a)
    for key in ("body_lean", "neck", "shoulder", "wrist", "jaw"):
        result[key] = a[key] + (b[key] - a[key]) * amount
    result["tail"] = tuple(x + (y - x) * amount for x, y in zip(a["tail"], b["tail"]))
    # Replacement parts and IK targets swap once, like a puppeteer replacing card.
    if amount >= 0.5:
        result["face"] = copy.deepcopy(b["face"])
        result["paw_target"] = copy.deepcopy(b["paw_target"])
    return result


def stepped_demo_poses(hold_frames=8, move_frames=3):
    names = ("sit_upright", "sit_look_up", "meow", "washing", "sit_upright")
    keys = [make_pose(name) for name in names]
    frames = [copy.deepcopy(keys[0]) for _ in range(hold_frames)]
    for start, end in zip(keys, keys[1:]):
        for step in range(1, move_frames + 1):
            frames.append(interpolate_pose(start, end, step / (move_frames + 1)))
        frames.extend(copy.deepcopy(end) for _ in range(hold_frames))
    return frames


def gif_frame_durations(frame_count, fps):
    """Quantize to GIF's 10 ms clock while preserving the requested total runtime."""
    tick_ms = 10
    durations = []
    previous_ticks = 0
    for frame_index in range(frame_count):
        target_ticks = round((frame_index + 1) * 1000.0 / fps / tick_ms)
        durations.append((target_ticks - previous_ticks) * tick_ms)
        previous_ticks = target_ticks
    return durations


def write_outputs(out_dir, *, fps=CLI_DEFAULTS["fps"], hold_frames=CLI_DEFAULTS["hold_frames"],
                  move_frames=CLI_DEFAULTS["move_frames"], shadow_blur=CLI_DEFAULTS["shadow_blur"],
                  rod_width=CLI_DEFAULTS["rod_width"], whisker_width=CLI_DEFAULTS["whisker_width"]):
    out_dir.mkdir(parents=True, exist_ok=True)
    pose_sheet(out_dir, shadow_blur, rod_width, whisker_width)
    face_sheet(out_dir, shadow_blur, rod_width, whisker_width)
    for name in POSE_TABLE:
        (out_dir / f"cat_{name}.svg").write_text(
            svg_for_pose(make_pose(name), rod_width, whisker_width), encoding="utf-8")
    frames = [projected(render_pose(pose, rod_width=rod_width, whisker_width=whisker_width), shadow_blur)
              for pose in stepped_demo_poses(hold_frames, move_frames)]
    small = [frame.resize((355, 400), Image.Resampling.LANCZOS) for frame in frames]
    small[0].save(out_dir / "cat_demo.gif", save_all=True, append_images=small[1:],
                  duration=gif_frame_durations(len(small), fps), loop=0, disposal=2, optimize=False)
    return {"poses": len(POSE_TABLE), "faces": len(FACE_SHEET), "gif_frames": len(frames)}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--fps", type=int, default=CLI_DEFAULTS["fps"])
    parser.add_argument("--hold-frames", type=int, default=CLI_DEFAULTS["hold_frames"])
    parser.add_argument("--move-frames", type=int, default=CLI_DEFAULTS["move_frames"])
    parser.add_argument("--shadow-blur", type=float, default=CLI_DEFAULTS["shadow_blur"])
    parser.add_argument("--rod-width", type=float, default=CLI_DEFAULTS["rod_width"])
    parser.add_argument("--whisker-width", type=float, default=CLI_DEFAULTS["whisker_width"])
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()
    result = write_outputs(args.out_dir, fps=args.fps, hold_frames=args.hold_frames,
                           move_frames=args.move_frames, shadow_blur=args.shadow_blur,
                           rod_width=args.rod_width, whisker_width=args.whisker_width)
    print(f"CAT_RIG_OK poses={result['poses']} faces={result['faces']} "
          f"gif_frames={result['gif_frames']} out={args.out_dir}")
