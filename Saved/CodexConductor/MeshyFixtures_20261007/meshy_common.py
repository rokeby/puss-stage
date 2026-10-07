"""Meshy fixtures: the PURE (no unreal) half shared by meshy_import.py and meshy_swap.py.

Loaded fresh on every editor run with runpy.run_path (never `import`ed), so an edited copy can never run stale
(memory ue58-python-stale-module-cache). Everything here runs offline and is exercised by test_meshy_fixtures.py.

Proof tiers (AGENTS.md), per claim:
* declaration-proven
  - a Prop attachment carries only a Mesh (TSoftObjectPtr<UStaticMesh>), no material field
    (Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageTypes.h:446-448); a mesh-only prop is spawned as an
    AStaticMeshActor and only gets SetStaticMesh (InfinityStagePassageActor.cpp:929-962), so a bulb's colour comes
    from its MESH ASSET's slot materials -> per-colour derived meshes (same reason as lighting_scores_apply.py:1168-1180);
  - the Bulb Body glass driver reads/creates its dynamic material on SLOT 0 only and drives scalar
    Body.IntensityParameter (default "Intensity") (InfinityStagePassageActor.cpp:1790-1812; InfinityStageBulbBody.h:46-48);
  - housings are NOT Show rows: one ISM instance per enabled, Light-kind, Station-anchored attachment of every
    WingPair cue at a station, PRACTICAL point lights included (InfinityStageStructureActor.cpp:138-176), all
    sharing ONE structure-wide FInfinityStageFixtureSettings.BodyMesh / BodySizeCm / BodyMaterial
    (InfinityStageStructureActor.h:396-416); each is fitted by BOUNDS: scale = BodySize / MeshBoundsSize per axis,
    bounds centre placed at LightWorld - Throw * BodySize.X/2, rotation MakeFromXZ(Throw, Up)
    (.cpp:183-196, 1818-1830); a non-null BodyMaterial overrides EVERY slot (.cpp:775-780); housings cast no
    shadow (.cpp:1858-1862); per-instance custom data = {FRand, BodySize.X, .Y, .Z} (.cpp:1831-1832);
  - M_UP_TubeEmissive multiplies by PerInstanceCustomData[3] (underpass_tubes_apply.py:8, :71-79), which on the
    fixture ISM is BodySize.Z -> it must NOT be the lantern lens parent (that is why M_Fixture_Glow exists).
* measured (offline, read here from files)
  - the 13 FBXs, their final bounds / slots / lens centroids / z_cut (DerivedAssets/Lighting/MeshyClean/
    cleanup_report.json, Blender re-import read-back per asset);
  - body/cap/light row shapes and labels ("P03 SCORE B01 P03_STIFF_BRIGHT PRACTICAL_BULB_DEAD_BODY", _CAP, light
    label = body label minus _BODY, body location == light location) from lighting_scores_record_P03.json and
    p0N_rig_pattern_record.json after_cue_rows (6 Oct).
* inferred (the live DRY confirms or refuses each)
  - an un-materialed engine Sphere / SM_PB_Bulb_* duplicate has bounds -50..50 cm (offline COUNT only; DRY reads
    every body mesh's bounds live and the plan uses those);
  - the role of a light is the label's last token prefix (TOP_L -> TOP) -- the scores tool's own convention
    (lighting_scores_apply.py expand_bay; p01_rig_pattern.py docstring "role = last token").
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
MESHY_ROOT = os.path.join(PROJECT, "DerivedAssets", "Lighting", "MeshyClean")
REPORT_PATH = os.path.join(MESHY_ROOT, "cleanup_report.json")

DEST_ROOT = "/Game/InfinityStage/Lighting/Fixtures"
MESH_DIR = DEST_ROOT + "/Meshes"
TEX_DIR = DEST_ROOT + "/Textures"
MAT_DIR = DEST_ROOT + "/Materials"
DERIVED_DIR = DEST_ROOT + "/Derived"
MASTERS = {"glow": MAT_DIR + "/M_Fixture_Glow", "lit": MAT_DIR + "/M_Fixture_Lit", "glass": MAT_DIR + "/M_Fixture_Glass"}

BULBS = ("SM_Bulb_A60_Clear", "SM_Bulb_A60_Frost", "SM_Bulb_A60_Opal", "SM_Bulb_A60_Worn",
         "SM_Bulb_C35_Clear", "SM_Bulb_G95_Clear", "SM_Bulb_ST64_Cage")
LANTERNS = ("SM_Lantern_Fresnel", "SM_Lantern_FresnelDoors", "SM_Lantern_Profile", "SM_Lantern_ParCan",
            "SM_Lantern_Birdie", "SM_Lantern_1950s")
# Import order: a lantern first (it has no glass slot, so its textures seed the masters' defaults; the glass master
# takes the first BULB's BaseColor when it is first needed), then the remaining lanterns, then the bulbs.
IMPORT_ORDER = LANTERNS + BULBS
TEXTURE_KINDS = ("BaseColor", "Normal", "Roughness", "Metallic")
BOUNDS_TOL_CM = 0.2

# ---- rule table ------------------------------------------------------------------------------------------------
# Housing lantern by light role. Today's C++ takes ONE BodyMesh per Structure (InfinityStageStructureActor.h:411), so
# the swap applies, per passage, the lantern of the passage's MAJORITY housed role (ties: ROLE_PRIORITY order);
# per-light variety by role needs a C++ change (see meshy_swap.py docstring).
ROLE_LANTERN = {
    "TOP": "SM_Lantern_Fresnel",          # grid wash, steep down-light
    "LOW_SIDE": "SM_Lantern_ParCan",      # boom / shin lamps
    "BEAM": "SM_Lantern_Profile",         # narrow shafts
    "UPLIGHT": "SM_Lantern_Birdie",       # floor birdies (P05)
    "FILL": "SM_Lantern_FresnelDoors",    # soft fill with doors (P05)
    "MOVER": "SM_Lantern_1950s",          # P05 movers
}
ROLE_PRIORITY = ("TOP", "LOW_SIDE", "BEAM", "FILL", "UPLIGHT", "MOVER")
KNOWN_ROLES = ("PRACTICAL", "LOW_SIDE", "UPLIGHT", "MOVER", "BEAM", "FILL", "TOP")   # matched longest-first
SPHERE_MESH = "/Engine/BasicShapes/Sphere"
PLAIN_SPHERE_BOUNDS = ([-50.0, -50.0, -50.0], [50.0, 50.0, 50.0])   # inferred (offline COUNT only)
ZERO_GUID = "0" * 32


class MeshyError(RuntimeError):
    """Deliberate fail-closed stop."""


def require(condition, message):
    if not condition:
        raise MeshyError(str(message))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def asset_id(path):
    """'/Game/A/B.B' or '/Game/A/B' -> '/Game/A/B'; None stays None."""
    if path in (None, "", "None"):
        return None
    return str(path).split(".", 1)[0]


def object_path(package):
    package = asset_id(package)
    return None if package is None else "%s.%s" % (package, package.rsplit("/", 1)[-1])


def enum_name(value):
    text = str(value)
    match = re.search(r"\.([A-Za-z0-9_]+)\s*:", text)
    return (match.group(1) if match else text.split(".")[-1]).strip("<> ").upper()


# ---- fixture table ---------------------------------------------------------------------------------------------
def mesh_path(name):
    return "%s/%s" % (MESH_DIR, name)


def texture_path(name, kind):
    return "%s/T_%s_%s" % (TEX_DIR, name, kind)


def mi_path(name, part):
    return "%s/MI_%s_%s" % (MAT_DIR, name, part)


def blender_to_ue_point(p):
    """Blender (right-handed) -> UE FBX import (left-handed): Y negated, X and Z unchanged."""
    return [float(p[0]), -float(p[1]), float(p[2])]


def blender_to_ue_bounds(lo, hi):
    """Bounds under the Y negation: min/max swap on Y only."""
    return [float(lo[0]), -float(hi[1]), float(lo[2])], [float(hi[0]), -float(lo[1]), float(hi[2])]


def load_fixture_table(report_path=REPORT_PATH, check_files=True):
    """{name: fixture} for exactly the 13 cleaned assets. check_files: every FBX matches its recorded sha256 and every
    texture exists (a re-export after the report is a refusal, not a silent import)."""
    with open(report_path, encoding="utf-8") as handle:
        report = json.load(handle)
    assets = report["assets"]
    require(set(assets) == set(BULBS) | set(LANTERNS), "FIXTURE_SET|%s" % sorted(assets))
    root = os.path.dirname(os.path.abspath(report_path))
    table = {}
    for name in IMPORT_ORDER:
        rec = assets[name]
        cls = rec["class"]
        require(cls == ("bulb" if name in BULBS else "housing"), "FIXTURE_CLASS|%s|%s" % (name, cls))
        fbx = os.path.join(root, name, name + ".fbx")
        textures = {kind: os.path.join(root, name, "T_%s_%s.png" % (name, kind)) for kind in TEXTURE_KINDS}
        if check_files:
            require(os.path.isfile(fbx), "FBX_MISSING|" + fbx)
            require(sha256_file(fbx) == rec["fbx_sha256"], "FBX_SHA_MISMATCH|" + name)
            for path in textures.values():
                require(os.path.isfile(path), "TEXTURE_MISSING|" + path)
        # The report is in BLENDER frame; UE's FBX import negates Y (right- to left-handed, X and Z unchanged), so a
        # Blender Y range [a, b] reads back in UE as [-b, -a]. Measured 7 Oct: SM_Bulb_A60_Opal (Y sum -0.32 cm)
        # read back Y [-2.869, 3.194] against Blender [-3.19, 2.87]; the 8 earlier imports passed only because their
        # |Y sum| <= 0.04 cm, under the 0.2 cm tolerance. Every fixture coordinate below is therefore UE frame.
        lo, hi = [list(map(float, v)) for v in rec["final_bounds_cm"]]
        lo, hi = blender_to_ue_bounds(lo, hi)
        size = [float(v) for v in rec["final_size_cm"]]
        slots = [s["name"] for s in sorted(rec["slots"], key=lambda s: s["index"])]
        fixture = {"name": name, "class": cls, "fbx": fbx, "fbx_sha256": rec["fbx_sha256"], "textures": textures,
                   "bounds_min": lo, "bounds_max": hi, "size": size, "slots": slots,
                   "lods": 1 if cls == "bulb" else 2, "warnings": list(rec.get("warnings") or []),
                   "mesh": mesh_path(name),
                   "texture_assets": {kind: texture_path(name, kind) for kind in TEXTURE_KINDS}}
        if cls == "bulb":
            z_cut = float(rec["classification"]["z_cut_cm"])
            require(lo[2] < z_cut < hi[2], "BULB_ZCUT|" + name)
            fixture["glass_centre"] = [(lo[0] + hi[0]) / 2.0, (lo[1] + hi[1]) / 2.0, (lo[2] + z_cut) / 2.0]
            fixture["glass_width"] = max(hi[0] - lo[0], hi[1] - lo[1])
            fixture["mis"] = {"Glow": mi_path(name, "Glow"), "Metal": mi_path(name, "Metal")}
            if len(slots) == 3:
                fixture["mis"]["Glass"] = mi_path(name, "Glass")
        else:
            lens = [float(v) for v in rec["classification"]["lens_centroid_cm"]]
            fixture["lens_centroid"] = blender_to_ue_point(lens)
            fixture["lens_diameter"] = float(rec["classification"]["lens_diameter_cm"])
            fixture["mis"] = {"Lens": mi_path(name, "Lens"), "Metal": mi_path(name, "Metal")}
        expected_suffixes = (["_Glow", "_Metal"] + (["_Glass"] if len(slots) == 3 else [])) if cls == "bulb" \
            else ["_Lens", "_Metal"]
        require([s.endswith(x) for s, x in zip(slots, expected_suffixes)] == [True] * len(expected_suffixes)
                and len(slots) == len(expected_suffixes), "REPORT_SLOT_ORDER|%s|%s" % (name, slots))
        fixture["slot_suffixes"] = expected_suffixes
        table[name] = fixture
    return table


def planned_assets(fixture):
    """Every package one fixture's import creates (masters excluded)."""
    return [fixture["mesh"]] + [fixture["texture_assets"][k] for k in TEXTURE_KINDS] + sorted(fixture["mis"].values())


def check_import_readback(fixture, rb, tol=BOUNDS_TOL_CM):
    """Gates after an import (README 'Gates to run after import'). rb = {"class", "num_lods", "bounds_min",
    "bounds_max", "slot_names", "nanite_enabled", "new_assets", "stray_assets"}. Returns a list of failure codes;
    empty = pass. Bounds are compared per axis, min AND max, so swapped axes and a flipped X (beam sign: every lantern
    is asymmetric in X by >= 0.54 cm, check lens_sign_provable) both fail."""
    fails = []
    if rb.get("class") != "StaticMesh":
        fails.append("CLASS|%s" % rb.get("class"))
    if rb.get("num_lods") != fixture["lods"]:
        fails.append("LODS|want=%d|got=%s" % (fixture["lods"], rb.get("num_lods")))
    for label, want, got in (("MIN", fixture["bounds_min"], rb.get("bounds_min")),
                             ("MAX", fixture["bounds_max"], rb.get("bounds_max"))):
        if not isinstance(got, (list, tuple)) or len(got) != 3 or any(abs(a - b) > tol for a, b in zip(want, got)):
            fails.append("BOUNDS_%s|want=%s|got=%s" % (label, want, got))
    names = list(rb.get("slot_names") or [])
    if len(names) != len(fixture["slot_suffixes"]) or not all(
            str(n).endswith(x) for n, x in zip(names, fixture["slot_suffixes"])):
        fails.append("SLOTS|want=%s|got=%s" % (fixture["slot_suffixes"], names))
    if rb.get("nanite_enabled"):
        fails.append("NANITE_ON")
    lod_strays = [p for p in rb.get("new_assets", []) if re.search(r"_LOD\d+$|_LODGroup$", str(p))]
    if lod_strays:
        fails.append("LOD_SPLIT_ASSETS|%s" % lod_strays)
    return fails


def lens_sign_provable(fixture, tol=BOUNDS_TOL_CM):
    """A 180-degree yaw or an X mirror maps [min,max] -> [-max,-min]; the bounds gate sees it iff |min+max| > 2 tol."""
    return abs(fixture["bounds_min"][0] + fixture["bounds_max"][0]) > 2.0 * tol


def lens_front_gap_cm(fixture):
    """+X distance from the lens centroid to the bounds front face (the face the structure puts at the light)."""
    return fixture["bounds_max"][0] - fixture["lens_centroid"][0]


# ---- labels, roles, rows ---------------------------------------------------------------------------------------
def score_label_regex(passage):
    return r"^%s SCORE B\d{2} " % passage


def role_of(label):
    token = str(label).strip().split(" ")[-1] if str(label).strip() else ""
    for role in sorted(KNOWN_ROLES, key=len, reverse=True):
        if token == role or token.startswith(role + "_"):
            return role
    return "OTHER"


def is_kind(row, kind):
    return enum_name(row.get("kind")) == kind


def is_station(row):
    return enum_name(row.get("anchor")) == "STATION"


def bulb_variant(light_guid, seed, pool):
    """ONE sha256 per light (no random stream, no draw order): the same GUID+seed+pool always gives the same bulb."""
    require(pool and len(set(pool)) == len(pool) and set(pool) <= set(BULBS), "BULB_POOL|%s" % (pool,))
    digest = hashlib.sha256(("MESHYBULB|%s|%s" % (seed, str(light_guid).upper())).encode("utf-8")).hexdigest()
    return list(pool)[int(digest[:8], 16) % len(pool)]


def derived_mesh_path(variant, slot0_mi):
    key = canonical({"variant": variant, "slot0": asset_id(slot0_mi)})
    return "%s/SM_FX_%s_%s" % (DERIVED_DIR, variant[len("SM_"):], hashlib.sha1(key.encode()).hexdigest()[:8])


# ---- quaternion maths (FTransform semantics, as p04_window_shadows.py:246-330) ----------------------------------
def quat_rotate(q, v):
    x, y, z, w = q
    tx = 2.0 * (y * v[2] - z * v[1])
    ty = 2.0 * (z * v[0] - x * v[2])
    tz = 2.0 * (x * v[1] - y * v[0])
    return [v[0] + w * tx + (y * tz - z * ty), v[1] + w * ty + (z * tx - x * tz), v[2] + w * tz + (x * ty - y * tx)]


def quat_from_basis(fx, fy, fz):
    """Rotation whose columns are the unit axes fx, fy, fz."""
    m00, m11, m22 = fx[0], fy[1], fz[2]
    trace = m00 + m11 + m22
    if trace > 0.0:
        s = 0.5 / math.sqrt(trace + 1.0)
        return [(fy[2] - fz[1]) * s, (fz[0] - fx[2]) * s, (fx[1] - fy[0]) * s, 0.25 / s]
    if m00 > m11 and m00 > m22:
        s = 2.0 * math.sqrt(1.0 + m00 - m11 - m22)
        return [0.25 * s, (fy[0] + fx[1]) / s, (fz[0] + fx[2]) / s, (fy[2] - fz[1]) / s]
    if m11 > m22:
        s = 2.0 * math.sqrt(1.0 + m11 - m00 - m22)
        return [(fy[0] + fx[1]) / s, 0.25 * s, (fz[1] + fy[2]) / s, (fz[0] - fx[2]) / s]
    s = 2.0 * math.sqrt(1.0 + m22 - m00 - m11)
    return [(fz[0] + fx[2]) / s, (fz[1] + fy[2]) / s, 0.25 * s, (fx[1] - fy[0]) / s]


def _norm(v):
    n = math.sqrt(sum(c * c for c in v))
    return [c / n for c in v]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def make_from_xz(x_axis, z_hint):
    """FRotationMatrix::MakeFromXZ: X exact, Z as close to the hint as possible."""
    fx = _norm(x_axis)
    fy = _norm(_cross(z_hint, fx))
    fz = _cross(fx, fy)
    return quat_from_basis(fx, fy, fz)


def fit_mesh_to_timber(bounds_min, bounds_max, centre_world, rotation, size_cm):
    """InfinityStageStructureActor.cpp:183-196 in Python: (location, rotation, scale)."""
    mesh_size = [b - a for a, b in zip(bounds_min, bounds_max)]
    scale = [s / m if m > 1.0e-4 else 1.0 for s, m in zip(size_cm, mesh_size)]
    centre = [(a + b) / 2.0 for a, b in zip(bounds_min, bounds_max)]
    offset = quat_rotate(rotation, [c * s for c, s in zip(centre, scale)])
    return [c - o for c, o in zip(centre_world, offset)], rotation, scale


def housing_world(fixture, size_cm, light_location, throw):
    """Where the C++ puts the housing for one light (cpp:1821-1830), and where the lens lands."""
    rotation = make_from_xz(throw, [0.0, 0.0, 1.0])
    body_centre = [p - t * size_cm[0] * 0.5 for p, t in zip(light_location, _norm(throw))]
    location, rotation, scale = fit_mesh_to_timber(fixture["bounds_min"], fixture["bounds_max"], body_centre,
                                                   rotation, size_cm)
    lens = fixture.get("lens_centroid")
    lens_world = None
    if lens is not None:
        lens_world = [l + r for l, r in zip(location, quat_rotate(rotation, [c * s for c, s in zip(lens, scale)]))]
    return {"location": location, "rotation": rotation, "scale": scale, "lens_world": lens_world}


def housing_size(fixture, scale):
    require(isinstance(scale, (int, float)) and 0.25 <= float(scale) <= 4.0, "HOUSING_SCALE_RANGE|%r" % (scale,))
    return [round(float(scale) * s, 4) for s in fixture["size"]]


def lens_offset_local(fixture, scale):
    """Lens centroid minus the light origin, in the housing frame (x = along the throw, z = up), for uniform scale:
    the light sits on the bounds front face at the bounds' Y/Z centre (cpp:1829 + :194)."""
    lo, hi, lens = fixture["bounds_min"], fixture["bounds_max"], fixture["lens_centroid"]
    origin = [hi[0], (lo[1] + hi[1]) / 2.0, (lo[2] + hi[2]) / 2.0]
    return [round(float(scale) * (a - b), 3) for a, b in zip(lens, origin)]


def choose_lantern(role_counts, override=None):
    if override not in (None, "AUTO"):
        require(override in LANTERNS, "HOUSING_LANTERN_UNKNOWN|%s" % override)
        return override, "override"
    housed = {r: n for r, n in role_counts.items() if r in ROLE_LANTERN and n > 0}
    require(housed, "NO_HOUSED_ROLE|%s" % canonical(role_counts))
    top = max(housed.values())
    role = next(r for r in ROLE_PRIORITY if housed.get(r) == top)
    return ROLE_LANTERN[role], "majority:%s=%d" % (role, top)


# ---- bulb placement --------------------------------------------------------------------------------------------
def bulb_scale(mode, old_diameter_cm, glass_width_cm, clamp):
    if isinstance(mode, (int, float)) and not isinstance(mode, bool):
        s = float(mode)
    elif mode == "REAL":
        s = 1.0
    elif mode == "MATCH_SPHERE":
        require(old_diameter_cm > 0.0 and glass_width_cm > 0.0, "BULB_SCALE_INPUT")
        s = old_diameter_cm / glass_width_cm
    else:
        raise MeshyError("BULB_SCALE_MODE|%r" % (mode,))
    lo, hi = clamp
    return round(min(hi, max(lo, s)), 4)


def old_glass(body_row, bounds):
    """Old body's glass centre (cue-relative) and visible diameter from its mesh bounds and the row's transform."""
    t = body_row["relative_transform"]
    lo, hi = bounds
    centre_local = [(a + b) / 2.0 * s for a, b, s in zip(lo, hi, t["scale"])]
    centre = [l + r for l, r in zip(t["location"], quat_rotate(t["rotation_xyzw"], centre_local))]
    diameter = max((hi[0] - lo[0]) * abs(t["scale"][0]), (hi[1] - lo[1]) * abs(t["scale"][1]))
    return centre, diameter


def bulb_transform(body_row, target_centre, fixture, scale):
    """Keep the body's rotation; uniform scale; put the bulb's glass centre on target_centre (cue-relative)."""
    rot = list(body_row["relative_transform"]["rotation_xyzw"])
    offset = quat_rotate(rot, [c * scale for c in fixture["glass_centre"]])
    location = [round(t - o, 4) for t, o in zip(target_centre, offset)]
    return {"location": location, "rotation_xyzw": rot, "scale": [scale, scale, scale]}


# ---- passage plan ----------------------------------------------------------------------------------------------
SWAP_DEFAULTS = {
    "bulb_pool": list(BULBS),
    "bulb_seed": "20261007",
    "bulb_anchor": "LIGHT",            # LIGHT: glass centre on the paired light's origin; BODY: on the old glass centre
    "bulb_scale": "MATCH_SPHERE",      # MATCH_SPHERE | REAL | a number
    "bulb_scale_clamp": [0.75, 4.0],
    "disable_caps": True,              # the Meshy bulb has its own screw cap: the old Cylinder cap row is disabled
    "label_regex": None,               # None = score_label_regex(passage)
    "housing": "AUTO",                 # AUTO (majority role) | OFF | a SM_Lantern_* name
    "housing_scale": 1.0,
    "anchor_warn_cm": 1.0,
}


def plan_passage(passage, cues, mesh_info, table, opts):
    """Pure planner. cues: [{"guid","label","show_index","attachments":[rows]}] (rows = attachment_state + optional
    "ext"); mesh_info: {mesh asset id: {"bounds": (min,max), "slot0": mi asset id|None, "source": str|None}};
    table: load_fixture_table(); opts: SWAP_DEFAULTS + args. Returns the plan dict (no unreal)."""
    label_re = re.compile(opts.get("label_regex") or score_label_regex(passage))
    pool = list(opts["bulb_pool"])
    targets, skipped, role_counts, practical_housed = [], [], {}, 0
    variants, derived = {}, {}
    for cue in cues:
        rows = cue["attachments"]
        by_label = {}
        for row in rows:
            by_label.setdefault(row["label"], []).append(row)
        bulbs, caps = [], []
        for row in rows:
            if is_kind(row, "LIGHT") and row["enabled"] and is_station(row):
                role = role_of(row["label"])
                role_counts[role] = role_counts.get(role, 0) + 1
                practical_housed += role == "PRACTICAL"
        for body in rows:
            if not (is_kind(body, "PROP") and body["label"].endswith("_BODY") and label_re.search(body["label"])):
                continue
            mesh = asset_id(body.get("mesh"))
            info = mesh_info.get(mesh)
            why = None
            if mesh is None or info is None:
                why = "BODY_MESH_UNKNOWN"
            elif mesh.startswith(DEST_ROOT + "/"):
                why = "ALREADY_FIXTURE"
            elif not (mesh == SPHERE_MESH or info.get("source") == SPHERE_MESH):
                why = "NOT_A_SPHERE_BULB"          # SM_Lamp_Wall / SM_Lamp_Ceiling fixtures are kept
            lights = [r for r in by_label.get(body["label"][:-len("_BODY")], []) if is_kind(r, "LIGHT")]
            if why is None and len(lights) != 1:
                why = "PAIRED_LIGHT_COUNT_%d" % len(lights)
            if why is None:
                light = lights[0]
                pair_guid = ((body.get("ext") or {}).get("body") or {}).get("light_attachment_guid")
                if pair_guid not in (None, ZERO_GUID, light["guid"]):
                    why = "BODY_FOLLOWS_ANOTHER_LIGHT"
                elif enum_name(light["anchor"]) != enum_name(body["anchor"]):
                    why = "ANCHOR_DIFFERS"
            if why is not None:
                skipped.append({"cue": cue["label"], "guid": body["guid"], "label": body["label"], "mesh": mesh,
                                "why": why})
                continue
            variant = bulb_variant(light["guid"], opts["bulb_seed"], pool)
            fixture = table[variant]
            centre, diameter = old_glass(body, info["bounds"])
            target = list(light["relative_transform"]["location"]) if opts["bulb_anchor"] == "LIGHT" else centre
            scale = bulb_scale(opts["bulb_scale"], diameter, fixture["glass_width"], opts["bulb_scale_clamp"])
            slot0 = info.get("slot0")
            if mesh == SPHERE_MESH or slot0 is None or not str(slot0).startswith("/Game/"):
                new_mesh = fixture["mesh"]       # its own faint MI_<V>_Glow (dead bulbs glow minimally)
            else:
                new_mesh = derived_mesh_path(variant, slot0)
                derived.setdefault(new_mesh, {"variant": variant, "source": fixture["mesh"], "slot0": asset_id(slot0)})
                require(derived[new_mesh] == {"variant": variant, "source": fixture["mesh"], "slot0": asset_id(slot0)},
                        "DERIVED_NAME_COLLISION|" + new_mesh)
            after = copy.deepcopy(body)
            after.pop("ext", None)
            after["mesh"] = object_path(new_mesh)
            after["relative_transform"] = bulb_transform(body, target, fixture, scale)
            gap = math.sqrt(sum((a - b) ** 2 for a, b in zip(centre, light["relative_transform"]["location"])))
            bulbs.append({"guid": body["guid"], "label": body["label"], "light_guid": light["guid"],
                          "variant": variant, "mesh_before": mesh, "mesh_after": new_mesh, "scale": scale,
                          "old_diameter_cm": round(diameter, 3), "body_to_light_cm": round(gap, 3),
                          "anchor_warning": gap > float(opts["anchor_warn_cm"]), "after": after})
            variants[variant] = variants.get(variant, 0) + 1
            cap_rows = [r for r in by_label.get(body["label"][:-len("_BODY")] + "_CAP", []) if is_kind(r, "PROP")]
            if opts["disable_caps"]:
                for cap in cap_rows:
                    if cap["enabled"]:
                        cap_after = copy.deepcopy(cap)
                        cap_after.pop("ext", None)
                        cap_after["enabled"] = False
                        caps.append({"guid": cap["guid"], "label": cap["label"], "after": cap_after})
        if bulbs or caps:
            targets.append({"cue_guid": cue["guid"], "cue_label": cue["label"], "show_index": cue.get("show_index"),
                            "bulbs": bulbs, "caps": caps})
    housing = {"mode": "OFF"}
    if opts["housing"] != "OFF":
        lantern, why = choose_lantern(role_counts, opts["housing"])
        fixture = table[lantern]
        housing = {"mode": "STRUCTURE", "lantern": lantern, "mesh": fixture["mesh"], "chosen_by": why,
                   "body_size_cm": housing_size(fixture, opts["housing_scale"]),
                   "body_material": None, "lens_offset_cm": lens_offset_local(fixture, opts["housing_scale"]),
                   "housed_role_counts": dict(sorted(role_counts.items())),
                   "practical_bulbs_that_get_a_lantern": practical_housed}
    plan = {"passage": passage, "opts": {k: opts[k] for k in sorted(SWAP_DEFAULTS)}, "targets": targets,
            "skipped": skipped, "derived_meshes": dict(sorted(derived.items())), "variants": dict(sorted(variants.items())),
            "counts": {"cues": len(targets), "bulbs": sum(len(t["bulbs"]) for t in targets),
                       "caps": sum(len(t["caps"]) for t in targets), "skipped": len(skipped),
                       "anchor_warnings": sum(b["anchor_warning"] for t in targets for b in t["bulbs"])},
            "housing": housing}
    return plan


def plan_sha(plan):
    return sha256_text(canonical(plan))


# ---- scope / revert (pure) -------------------------------------------------------------------------------------
LOC_TOL_CM = 1.0e-3
REL_TOL = 1.0e-5


def _close(a, b, key):
    if isinstance(a, bool) or isinstance(b, bool) or a is None or b is None or isinstance(a, str) or isinstance(b, str):
        if key in ("mesh", "actor_class") or (isinstance(a, str) and a.startswith("/")):
            return asset_id(a) == asset_id(b)
        if isinstance(a, str) and isinstance(b, str) and ("<" in a or "<" in b):
            return enum_name(a) == enum_name(b)
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        tol = LOC_TOL_CM if key == "location" else REL_TOL * max(1.0, abs(float(a)))
        return abs(float(a) - float(b)) <= tol
    return a == b


def row_differences(want, got, path="", key=None):
    """Tolerant field diff (asset paths by package, enums by name, floats to float32-ish tolerance)."""
    out = []
    if isinstance(want, dict) and isinstance(got, dict):
        for k in sorted(set(want) | set(got)):
            if k == "ext":
                continue
            if k not in want or k not in got:
                out.append({"path": path + "." + k, "want": want.get(k), "got": got.get(k)})
            else:
                out.extend(row_differences(want[k], got[k], path + "." + k, k))
    elif isinstance(want, list) and isinstance(got, list):
        if len(want) != len(got):
            out.append({"path": path, "want": want, "got": got})
        else:
            for i, (a, b) in enumerate(zip(want, got)):
                out.extend(row_differences(a, b, "%s[%d]" % (path, i), key))
    elif not _close(want, got, key):
        out.append({"path": path, "want": want, "got": got})
    return out


def expected_after(before_all, plan):
    """before_all {cue_guid: rows} -> the rows the plan must leave (only planned rows change, in place)."""
    result = copy.deepcopy(before_all)
    for t in plan["targets"]:
        repl = {b["guid"]: b["after"] for b in t["bulbs"]}
        repl.update({c["guid"]: c["after"] for c in t["caps"]})
        rows = result[t["cue_guid"]]
        hit = 0
        for i, row in enumerate(rows):
            if row["guid"] in repl:
                ext = row.get("ext")
                rows[i] = copy.deepcopy(repl[row["guid"]])
                if ext is not None:
                    rows[i]["ext"] = ext
                hit += 1
        require(hit == len(repl), "PLAN_GUIDS_NOT_IN_CUE|%s|%d/%d" % (t["cue_guid"], hit, len(repl)))
    return result


def scope_problems(want_all, live_all):
    if set(want_all) != set(live_all):
        return [{"cue": "*", "problem": "CUE_SET_CHANGED"}]
    problems = []
    for cue_guid in sorted(want_all):
        want, live = want_all[cue_guid], live_all[cue_guid]
        if [r["guid"] for r in want] != [r["guid"] for r in live]:
            problems.append({"cue": cue_guid, "problem": "ROW_GUIDS_OR_ORDER"})
            continue
        for a, b in zip(want, live):
            d = row_differences(a, b)
            if d:
                problems.append({"cue": cue_guid, "guid": a["guid"], "label": a["label"], "differences": d[:12]})
    return problems


def check_scope(want_all, live_all, side):
    problems = scope_problems(want_all, live_all)
    require(not problems, "SCOPE_CHANGED|side=%s|count=%d|%s" % (side, len(problems), canonical(problems)[:3000]))


def revert_model(record, live_all):
    """Live target rows must equal the record's after rows (no drift since APPLY); result = the before rows."""
    for cue_guid, after_rows in record["after_rows"].items():
        live = live_all.get(cue_guid)
        require(live is not None, "CUE_GONE|" + cue_guid)
        drift = scope_problems({cue_guid: after_rows}, {cue_guid: live})
        require(not drift, "REVERT_DRIFT|%s|%s" % (cue_guid, canonical(drift)[:2000]))
    model = copy.deepcopy(live_all)
    for cue_guid, before_rows in record["before_rows"].items():
        model[cue_guid] = copy.deepcopy(before_rows)
    return model


def check_ack(foreign_hits, ack):
    unacked = sorted({h["path"] for h in foreign_hits} - set(ack))
    return unacked


# ---- offline snapshots (COUNT mode) ----------------------------------------------------------------------------
def snapshot_cues(passage, saved_conductor):
    """Latest passage-wide row snapshot on disk (6 Oct): p0N_rig_pattern_record.json after_cue_rows, or for P05 the
    lighting scores record's targets[].after_rows. Returns (cues, source)."""
    rig = os.path.join(saved_conductor, "%s_rig_pattern_record.json" % passage.lower())
    if os.path.isfile(rig):
        with open(rig, encoding="utf-8") as handle:
            rec = json.load(handle)
        labels = {}
        for t in rec.get("plan", {}).get("targets", []) or []:
            if isinstance(t, dict) and "cue_guid" in t:
                labels[t["cue_guid"]] = t.get("cue_label", t["cue_guid"])
        cues = [{"guid": g, "label": labels.get(g, g), "attachments": rows}
                for g, rows in sorted(rec["after_cue_rows"].items())]
        return cues, "%s (run %s, status %s)" % (os.path.basename(rig), rec.get("run"), rec.get("status"))
    scores = os.path.join(saved_conductor, "lighting_scores_record_%s.json" % passage)
    with open(scores, encoding="utf-8") as handle:
        rec = json.load(handle)
    cues = [{"guid": t["cue_guid"], "label": t["cue_label"], "attachments": t["after_rows"]}
            for t in rec["plan"]["targets"]]
    return cues, "%s (run %s, status %s)" % (os.path.basename(scores), rec.get("run"), rec.get("status"))


def offline_mesh_info(cues):
    """COUNT-mode stand-in for the live mesh read: spheres (engine or SM_PB_Bulb_* body duplicates) are -50..50 and
    sourced from the Sphere; SM_PB_Bulb_* used by a _CAP row is a Cylinder cap (inferred, the live DRY reads all)."""
    info = {}
    caps = {asset_id(r.get("mesh")) for c in cues for r in c["attachments"] if r["label"].endswith("_CAP")}
    for c in cues:
        for r in c["attachments"]:
            m = asset_id(r.get("mesh"))
            if m is None or m in info:
                continue
            if m == SPHERE_MESH:
                info[m] = {"bounds": PLAIN_SPHERE_BOUNDS, "slot0": None, "source": None}
            elif "/SM_PB_Bulb_" in m:
                info[m] = {"bounds": PLAIN_SPHERE_BOUNDS, "slot0": "/Game/OFFLINE_SLOT0_OF" + m[len("/Game"):],
                           "source": "/Engine/BasicShapes/Cylinder" if m in caps else SPHERE_MESH}
            else:
                info[m] = {"bounds": ([-10.0] * 3, [10.0] * 3), "slot0": None, "source": None}
    return info
