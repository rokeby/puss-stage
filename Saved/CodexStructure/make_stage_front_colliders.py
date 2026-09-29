"""File-side (system Python): write Docs/StageFrontColliders_2026-09-28.json, the
curtain bake's collider boxes for stage-front option A (Gary, 28 Sep), predicted
from the spec and the C++ settings. It's the single source of truth: the
post-build check compares the built geometry against this file.

v2 (28 Sep): the lower house floor wraps both sides of the mouth ("catch
everywhere"), with an end return at x 250 and side returns along the ground's
edge to x +1000. Adds the two station-1 float housings and the 16 lip-float
housings (Gary: footlights shadowless, buried by the overspill, judged in the
capture). Only ENABLED lamps get a housing, as in GatherFixturePlacements.
"""
import json
import math
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "..", "Docs", "StageFrontColliders_2026-09-28.json"))
T = 5.0                  # one board course: floors, fascia and returns
HOUSE_Z = -120.0         # house floor top
MOUTH_HALF = 1300.0      # raised mouth, lip to the first station
GROUND_HALF = 970.0      # P01's floor half-span (grid half-width) beyond the mouth
MOUTH_END = 250.0        # the first station
SIDES_TO = 1000.0        # house floor and ground side returns run upstage to here
HOUSE_HALF = 2000.0
HOUSE_FROM = -2600.0
HOUSING = (45.0, 32.0, 32.0)   # FInfinityStageFixtureSettings::BodySizeCm


def box(name, x0, x1, y0, y1, z0, z1, note=""):
    rec = {"name": name, "min_cm": [x0, y0, z0], "max_cm": [x1, y1, z1]}
    if note:
        rec["note"] = note
    return rec


def mirrored(name, x0, x1, y0, y1, z0, z1, note=""):
    """A box on the +Y side and its mirror on -Y."""
    return [box(f"{name} L", x0, x1, -y1, -y0, z0, z1, note), box(f"{name} R", x0, x1, y0, y1, z0, z1, note)]


def housing(name, source, yaw_deg, pitch_deg):
    """The structure pass's housing: 45 x 32 x 32 cm behind the source along its
    throw (BuildFixtures). Returned as an oriented box and its world AABB."""
    y, p = math.radians(yaw_deg), math.radians(pitch_deg)
    fwd = (math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p))
    right = (-math.sin(y), math.cos(y), 0.0)
    up = (-math.sin(p) * math.cos(y), -math.sin(p) * math.sin(y), math.cos(p))
    c = [source[i] - fwd[i] * HOUSING[0] * 0.5 for i in range(3)]
    half = [sum(abs(ax[i]) * h * 0.5 for ax, h in zip((fwd, right, up), HOUSING)) for i in range(3)]
    return {"name": name, "min_cm": [round(c[i] - half[i], 1) for i in range(3)],
            "max_cm": [round(c[i] + half[i], 1) for i in range(3)],
            "oriented": {"centre_cm": [round(v, 1) for v in c], "size_cm": list(HOUSING),
                         "yaw_deg": yaw_deg, "pitch_deg": round(pitch_deg, 3)}}


boxes = [
    box("Post L", -20, 20, -990, -950, 0, 1095),
    box("Post R", -20, 20, 950, 990, 0, 1095),
    box("Header", -20, 20, -990, 990, 1050, 1095, "not reached in the coarse run"),
    box("Trough", -150, -115, -950, 950, 0, 25),
    box("Stage floor: forestage and mouth", -150, MOUTH_END, -MOUTH_HALF, MOUTH_HALF, -T, 0),
    box("Stage floor: ground beyond the mouth", MOUTH_END, 5400, -GROUND_HALF, GROUND_HALF, -T, 0),
    box("Fascia: lip face", -150 - T, -150, -MOUTH_HALF, MOUTH_HALF, HOUSE_Z, 0),
    *mirrored("Mouth side return", -150, MOUTH_END, MOUTH_HALF, MOUTH_HALF + T, HOUSE_Z, 0),
    *mirrored("End return at the first station", MOUTH_END, MOUTH_END + T, GROUND_HALF, MOUTH_HALF, HOUSE_Z, 0),
    *mirrored("Ground side return", MOUTH_END, SIDES_TO, GROUND_HALF, GROUND_HALF + T, HOUSE_Z, 0),
    box("House floor: front", HOUSE_FROM, -150, -HOUSE_HALF, HOUSE_HALF, HOUSE_Z - T, HOUSE_Z),
    *mirrored("House floor: beside the mouth", -150, MOUTH_END, MOUTH_HALF, HOUSE_HALF, HOUSE_Z - T, HOUSE_Z),
    *mirrored("House floor: beside the ground", MOUTH_END, SIDES_TO, GROUND_HALF, HOUSE_HALF, HOUSE_Z - T, HOUSE_Z),
]

# Station 1's floats, authored 28 Sep (p01_warmer_plan.json): (310, +-710, 25),
# thrown 60 degrees inward and 5 up; both lit.
lamps = [housing("Station 1 float L housing", (310.0, -710.0, 25.0), 60.0, 5.0),
         housing("Station 1 float R housing", (310.0, 710.0, 25.0), -60.0, 5.0)]

# The lip floats as p01_lip_floats_plan_readonly.py will place them on the
# default 150 cm forestage: 15 cm upstage of the trough's back face (x -115),
# 30 cm up, 16 across +-825, aimed so the centre ray meets the cloth 110 cm up.
source_x, source_z, clearance = -100.0, 30.0, 100.0
pitch = math.degrees(math.atan2(110.0 - source_z, clearance))
for i in range(16):
    rng = random.Random(f"P01-lip-float-{i:02d}")
    if rng.random() < 1.0 / 12.0:
        continue                      # left dark: no housing is built for it
    lateral = -825.0 + i * (1650.0 / 15.0)
    lamps.append(housing(f"Lip {i + 1:02d} housing", (source_x, lateral, source_z), 0.0, pitch))

out = {"version": 2,
       "source": "Docs/StageFrontSpec_2026-09-28.md option A; predicted from the settings, NOT yet built",
       "units": "UE world cm, Passage 01; the curtain line and posts at x 0, the lip at x -150",
       "to_blender_m": "Bx = UE_Y/100, By = UE_X/100 (+y upstage), Bz = UE_Z/100. Mirror-symmetric in Y except the "
                       "lip-float housings, which follow a fixed seed; their Y is exact either way",
       "verify_after_build": "a read-only check compares the built portal and fixture instances with these boxes to 1 cm",
       "excluded": "Wing 001's painted cards (x ~250): a box over the card plane would hold cloth on transparent air; "
                   "they join once the footprint probe gives the opaque silhouette",
       "boxes": boxes, "lamp_housings": lamps}
with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(out, fh, indent=1)
print(f"boxes={len(boxes)} lamp_housings={len(lamps)} lip_pitch={pitch:.2f} -> {OUT}")
