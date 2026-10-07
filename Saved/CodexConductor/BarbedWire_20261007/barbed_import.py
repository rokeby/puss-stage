"""Barbed-wire fence kit -> Unreal, NEW assets only (Gary 7 Oct, "Coil + strands"). PREPARED, NOT RUN.

Imports exactly the three approved, offline-validated FBXs (barbed_wire.py build+validate, validation.json PASS):
  SM_FenceBay_short_open_bwc      top-row bay: chain + rail + 101.6 mm post with Y-outriggers, 2 strands + concertina
  SM_FenceBay_short_door_gap_bw   door-gap bay, 4 strands (variant D's top-row mesh; D is ground-row-only in Stack,
                                  so it only shows on a one-row Native/Fit fence)
  SM_FencePost_short_bw           stand-alone post (line ends; FencePostJoints LineEnd)
and creates one material instance:
  MI_BarbedWire  parent = MI_FenceBay_Metal (inherits its galvanised-rust textures and ChainMasked=false; no
                 parameter is overridden, so it reads exactly as the metal until someone tunes it)
into /Game/InfinityStage/RigAtmos/FenceBay/{StaticMeshes,Materials}. Nothing existing is modified; no Show/level write.

Slot binding (slot names are the FBX's, checked in order):
  bays: [M_FenceChain_Masked, M_FenceMetal, M_BarbedWire] -> [MI_FenceBay_open, MI_FenceBay_Metal, MI_BarbedWire]
        (door_gap_bw uses MI_FenceBay_open too: its door is cut in geometry; MI_FenceBay_door_gap samples a raw-UV0
         mask - same reason as fbs_import.py:24-27)
  post: [M_FenceMetal] -> [MI_FenceBay_Metal]

UE 5.8 Interchange traps handled (memory ue58-fbx-import-traps): FbxImportUI is IGNORED by Interchange, so nothing
is trusted from options - the pilot fbx_options(True) is passed only because it measured 0 stray materials/textures
(4 Oct), and the folder is diffed before/after (never-saved strays deleted). LODs come from the FBX LodGroup node
(barbed_wire.py export_group): gate get_num_lods() == 3 and no stray *_LOD* asset. Handedness gate: the bays' Y
bounds must come out FLIPPED from Blender (Unreal +Y = walkway) - min -28.89 / max +29.54 cm, not the mirror - and
Y-centred like the live SM_FenceBay_short_open (the C++ fits panels by bounds). V-down gate: on the stand-alone post,
dV/dZ (from the tube's vertical triangle edges) must be negative and, when the live SM_FencePost_short's UVs are
readable, the SAME sign as it; if they are not, BW_IMPORT_REF_POST_UV_UNAVAILABLE is logged and the new post is
gated alone (a mirrored / upside-down V still fails).

Measured for barbed_apply.py (written to barbed_import_record.json): each bay's baked post axis (LOD0, metal slot,
endpoints of vertical edges, x < -100) and the stand-alone post's axis (LOD0, vertical edges, |x| < 15), in
mesh-local cm. Vertical edges, not a Z band: the posts are two-ring tubes with no vertices between base and top.

Args barbed_import_args.json {"mode": "DRY"|"IMPORT"|"REVERT", "confirm": "<MODE> BARBEDWIRE"}.
  DRY     read-only: hashes, targets free, MIs present, API probes, reference measurements. Marker BW_IMPORT_DRY_OK.
  IMPORT  guards (no PIE, census clean) -> import -> strays -> per-mesh gates -> MI -> bind -> read back -> census =
          only the 4 new packages -> save those 4 -> census clean -> files on disk -> record -> BW_IMPORT_OK.
          ANY failure after the import step: the new assets exist UNSAVED; save nothing, restart the editor with
          Don't Save (memory ue58-reimport-revert-by-reload-fails).
  REVERT  record state "imported"; refuses while any package outside the 4 references them (run barbed_apply REVERT
          first); deletes the 3 meshes then the MI; census clean -> BW_IMPORT_REVERT_OK.
Run via the guarded MCP route: barbed_import_request.json (ExecuteProjectPythonFile). Markers carry run=<id>.
"""
import datetime
import hashlib
import importlib.util
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
FBX_DIR = os.path.join(HERE, "fbx")
RECORD = os.path.join(HERE, "barbed_import_record.json")
ARGS = os.path.join(HERE, "barbed_import_args.json")
DEST = "/Game/InfinityStage/RigAtmos/FenceBay"
MESHES = DEST + "/StaticMeshes"
MATS = DEST + "/Materials"
MI_NAME = "MI_BarbedWire"
MI_PARENT = "MI_FenceBay_Metal"
BAY_SLOTS = ["M_FenceChain_Masked", "M_FenceMetal", "M_BarbedWire"]
TARGETS = {  # asset: (slot names, material instances, kind)
    "SM_FenceBay_short_open_bwc": (BAY_SLOTS, ["MI_FenceBay_open", "MI_FenceBay_Metal", MI_NAME], "bay"),
    "SM_FenceBay_short_door_gap_bw": (BAY_SLOTS, ["MI_FenceBay_open", "MI_FenceBay_Metal", MI_NAME], "bay"),
    "SM_FencePost_short_bw": (["M_FenceMetal"], ["MI_FenceBay_Metal"], "post"),
}
LODS = 3
TOL = 0.5  # cm
# Expected Unreal bounds (cm) = Blender bounds (validation.json) x 100 with Y negated.
BAY_X, BAY_Z = (-168.0, 168.0), (0.0, 302.6763)
BAY_Y_FLIPPED = (-28.890, 29.540)          # Blender y in [-0.29540, 0.28890]
POST_X, POST_Z = (-5.08, 5.08), (0.0, 297.99)
POST_Y_FLIPPED = (-20.631, 33.631)         # Blender y in [-0.33631, 0.20631]
REF_BAY = "SM_FenceBay_short_open"
REF_POST = "SM_FencePost_short"
CONFIRM_TAIL = "BARBEDWIRE"


class BWError(RuntimeError):
    pass


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _pkg(value):
    text = value if isinstance(value, str) else value.get_path_name()
    return text.split(".")[0]


def least_squares(xs, ys):
    n = float(len(xs))
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 1e-9:
        raise BWError("LSQ_DEGENERATE")
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx


def axis_from(points, zlo=20.0, zhi=250.0, xpred=lambda x: True):
    """Mean x/y of the vertices in a Z band and an X predicate: a round tube's axis."""
    sel = [(p[0], p[1]) for p in points if zlo < p[2] < zhi and xpred(p[0])]
    if len(sel) < 6:
        raise BWError("AXIS_TOO_FEW_VERTICES|%d" % len(sel))
    return [sum(p[0] for p in sel) / len(sel), sum(p[1] for p in sel) / len(sel), len(sel)]


# The posts are two-ring tubes (base ring + top ring, no vertices between: barbed_wire.py tube();
# live SM_FencePost_short is a Blender primitive cylinder, same topology), so a Z-band vertex filter
# finds NOTHING (live DRY 7 Oct: POST_UV_FEW|SM_FencePost_short|0). Measure along the tube's
# vertical triangle EDGES instead: |dz| >= 50 cm and horizontal drift <= 1 cm.
VERT_MIN_DZ = 50.0
VERT_MAX_DH = 1.0


def vertical_edges(pts, tris, xpred=lambda x: True, min_dz=VERT_MIN_DZ, max_dh=VERT_MAX_DH):
    """Triangle edges (lower, upper) of points (x, y, z, v) that run vertically, both ends passing xpred."""
    out = []
    for t in range(0, len(tris) - 2, 3):
        idx = (tris[t], tris[t + 1], tris[t + 2])
        for i, j in ((idx[0], idx[1]), (idx[1], idx[2]), (idx[2], idx[0])):
            p, q = pts[i], pts[j]
            if p[2] > q[2]:
                p, q = q, p
            dh = ((q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2) ** 0.5
            if q[2] - p[2] >= min_dz and dh <= max_dh and xpred(p[0]) and xpred(q[0]):
                out.append((p, q))
    return out


def edge_v_slope(pts, tris, xpred):
    """dV/dZ of the upright tube from its vertical edges; raises BWError (no log) if unmeasurable."""
    edges = vertical_edges(pts, tris, xpred)
    if len(edges) < 6:
        raise BWError("POST_UV_FEW|%d" % len(edges))
    slopes = [(q[3] - p[3]) / (q[2] - p[2]) for p, q in edges]
    if not (all(x < 0.0 for x in slopes) or all(x > 0.0 for x in slopes)):
        raise BWError("POST_UV_MIXED|n=%d|min=%.6g|max=%.6g" % (len(slopes), min(slopes), max(slopes)))
    return sum(slopes) / len(slopes)


def axis_from_edges(pts, tris, xpred):
    """Mean x/y of the vertical-edge endpoints: a round tube's axis (each ring angle counted equally)."""
    sel = [(e[0], e[1]) for pq in vertical_edges(pts, tris, xpred) for e in pq]
    if len(sel) < 6:
        raise BWError("AXIS_TOO_FEW_VERTICES|%d" % len(sel))
    return [sum(p[0] for p in sel) / len(sel), sum(p[1] for p in sel) / len(sel), len(sel)]


def post_v_verdict(slope, ref):
    """V must run DOWN (dV/dZ < 0) on the new post; when the live reference was readable it must agree."""
    if ref is None:
        return slope < 0.0, "live reference unavailable; new post checked alone against V-down"
    return slope < 0.0 and ref < 0.0, "same sign as live SM_FencePost_short"


def near(a, b, tol=TOL):
    return abs(a - b) <= tol


class Ctx:
    def __init__(self, mode):
        import unreal  # noqa: PLC0415  (no UE wrappers in module globals: memory puss-mcp-python-crashes-the-editor)
        self.u = unreal
        self.mode = mode
        self.run = datetime.datetime.now().strftime("BWIMP-%Y%m%d-%H%M%S")
        self.past_import = False

    def log(self, msg):
        self.u.log(msg)

    def fail(self, msg):
        tail = "|NOTHING SAVED; restart the editor with Don't Save" if self.past_import else ""
        self.u.log_error("BW_IMPORT_FAILED|run=%s|mode=%s|%s%s" % (self.run, self.mode, msg, tail))
        raise BWError("BW_IMPORT_FAILED|run=%s|%s" % (self.run, msg))

    def check(self, cond, msg):
        if not cond:
            self.fail(msg)


def census(u):
    lib = u.EditorLoadingAndSavingUtils
    return (sorted({_pkg(p.get_name()) for p in lib.get_dirty_content_packages()}),
            sorted({_pkg(p.get_name()) for p in lib.get_dirty_map_packages()}))


def folder(u, path):
    return {_pkg(str(p)) for p in u.EditorAssetLibrary.list_assets(path, recursive=False, include_folder=False)}


def bounds_cm(mesh):
    b = mesh.get_bounding_box()
    return {"min": [b.min.x, b.min.y, b.min.z], "max": [b.max.x, b.max.y, b.max.z]}


def section_data(u, mesh, lod, slot):
    """LOD `lod` (points (x, y, z, v), flat triangle indices) of the section drawing material slot `slot`.
    Raises BWError without logging; callers decide whether that is a failure."""
    sub = u.get_editor_subsystem(u.StaticMeshEditorSubsystem)
    for section in range(32):
        s = int(sub.get_lod_material_slot(mesh, lod, section))
        if s < 0:
            break
        if s == slot:
            sec = u.ProceduralMeshLibrary.get_section_from_static_mesh(mesh, lod, section)
            verts, tris, uvs = list(sec[0]), [int(i) for i in sec[1]], list(sec[3])
            if not verts or len(verts) != len(uvs) or not tris or len(tris) % 3:
                raise BWError("SECTION_ARRAYS|%s|slot=%d|v=%d|uv=%d|idx=%d"
                              % (mesh.get_name(), slot, len(verts), len(uvs), len(tris)))
            return [(float(v.x), float(v.y), float(v.z), float(t.y)) for v, t in zip(verts, uvs)], tris
    raise BWError("NO_SECTION_FOR_SLOT|%s|lod=%d|slot=%d" % (mesh.get_name(), lod, slot))


def _measure(c, what, fn, *a):
    try:
        return fn(*a)
    except BWError as e:
        c.fail("%s|%s" % (what, e))


def post_v_slope(c, mesh):
    pts, tris = _measure(c, mesh.get_name(), section_data, c.u, mesh, 0, 0)
    return _measure(c, mesh.get_name(), edge_v_slope, pts, tris, lambda x: abs(x) < 15.0)


def ref_post_v_slope(c, mesh):
    """Live reference post dV/dZ, or None (logged) if its UVs cannot be read; never fails the run."""
    try:
        pts, tris = section_data(c.u, mesh, 0, 0)
        return edge_v_slope(pts, tris, lambda x: abs(x) < 15.0)
    except BWError as e:
        c.log("BW_IMPORT_REF_POST_UV_UNAVAILABLE|run=%s|%s|%s|new post will be checked alone against V-down"
              % (c.run, mesh.get_name(), e))
        return None


def pilot(c):
    path = os.path.join(REPO, "Saved", "CodexFlatV3", "phase1_import.py")
    spec = importlib.util.spec_from_file_location("bw_flatv3_pilot_%s" % c.run.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # FLATV3_MODE unset -> helpers only (phase1_import.py:1182)
    c.check(callable(getattr(module, "fbx_options", None)) and callable(getattr(module, "import_task", None)),
            "PILOT_HELPERS_MISSING")
    return module


def preflight(c):
    """Everything DRY checks; IMPORT repeats it before touching anything. Returns facts for the record."""
    u = c.u
    ed = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    c.check(ed.get_game_world() is None, "PIE_ACTIVE")  # refuses; never ends PIE
    manifest = json.load(open(os.path.join(HERE, "build_manifest.json"), encoding="utf-8"))
    validation = json.load(open(os.path.join(HERE, "validation.json"), encoding="utf-8"))
    c.check(validation.get("status") == "PASS" and validation.get("negative_control", {}).get("ok") is True,
            "OFFLINE_VALIDATION_NOT_PASS")
    hashes = {row["asset"]: row["sha256"] for row in manifest["assets"]}
    passed = {row["asset"]: row["status"] == "PASS" and row.get("sha256_matches_build") is True
              for row in validation["assets"]}
    for name in TARGETS:
        fbx = os.path.join(FBX_DIR, name + ".fbx")
        c.check(os.path.isfile(fbx) and _sha(fbx) == hashes.get(name), "FBX_HASH|" + name)
        c.check(passed.get(name) is True, "FBX_NOT_VALIDATED|" + name)
    targets = [MESHES + "/" + n for n in TARGETS] + [MATS + "/" + MI_NAME]
    existing = [t for t in targets if u.EditorAssetLibrary.does_asset_exist(t)]
    for name, (_, instances, _) in TARGETS.items():
        for mi in set(instances) - {MI_NAME}:
            c.check(isinstance(u.EditorAssetLibrary.load_asset(MATS + "/" + mi), u.MaterialInterface), "MI_MISSING|" + mi)
    parent = u.EditorAssetLibrary.load_asset(MATS + "/" + MI_PARENT)
    c.check(isinstance(parent, u.MaterialInstanceConstant), "MI_PARENT_NOT_AN_MI|" + MI_PARENT)
    for api in ("ProceduralMeshLibrary", "StaticMeshEditorSubsystem", "MaterialEditingLibrary",
                "MaterialInstanceConstantFactoryNew"):
        c.check(hasattr(u, api), "API_MISSING|" + api)
    ref_bay = u.EditorAssetLibrary.load_asset(MESHES + "/" + REF_BAY)
    ref_post = u.EditorAssetLibrary.load_asset(MESHES + "/" + REF_POST)
    c.check(isinstance(ref_bay, u.StaticMesh) and isinstance(ref_post, u.StaticMesh), "REFERENCE_MESH_MISSING")
    rb = bounds_cm(ref_bay)
    facts = {"existing_targets": existing, "ref_bay_bounds_cm": rb,
             "ref_bay_y_centre_cm": (rb["min"][1] + rb["max"][1]) * 0.5,
             "ref_post_dv_dz": ref_post_v_slope(c, ref_post)}  # None = live comparison unavailable (logged)
    return targets, facts


def gate_mesh(c, name, mesh, facts):
    slots_expected, _, kind = TARGETS[name]
    c.check(isinstance(mesh, c.u.StaticMesh), "IMPORT_CLASS|" + name)
    c.check(mesh.get_num_lods() == LODS, "LOD_COUNT|%s|%d" % (name, mesh.get_num_lods()))
    slots = [str(s.get_editor_property("material_slot_name")) for s in mesh.get_editor_property("static_materials")]
    c.check(slots == slots_expected, "SLOT_NAMES|%s|%s" % (name, slots))
    b = bounds_cm(mesh)
    row = {"lods": mesh.get_num_lods(), "slots": slots, "bounds_cm": b}
    if kind == "bay":
        ok = (near(b["min"][0], BAY_X[0]) and near(b["max"][0], BAY_X[1]) and near(b["min"][2], BAY_Z[0])
              and near(b["max"][2], BAY_Z[1]))
        c.check(ok, "BAY_BOUNDS|%s|%s" % (name, b))
        c.check(near(b["min"][1], BAY_Y_FLIPPED[0], 0.2) and near(b["max"][1], BAY_Y_FLIPPED[1], 0.2),
                "BAY_HANDEDNESS|%s|y=%.3f..%.3f want %.3f..%.3f (mirrored = wire on the wrong side)"
                % (name, b["min"][1], b["max"][1], BAY_Y_FLIPPED[0], BAY_Y_FLIPPED[1]))
        yc = (b["min"][1] + b["max"][1]) * 0.5
        c.check(near(yc, facts["ref_bay_y_centre_cm"], 0.2), "BAY_Y_CENTRE|%s|%.3f vs live %.3f"
                % (name, yc, facts["ref_bay_y_centre_cm"]))
        pts, tris = _measure(c, name, section_data, c.u, mesh, 0, 1)
        axis = _measure(c, name, axis_from_edges, pts, tris, lambda x: x < -100.0)
        c.check(near(axis[0], BAY_X[0] + 5.08, 0.3), "BAY_POST_NOT_AT_LOCAL_MINUS_X|%s|%s" % (name, axis))
        row.update(post_axis_cm=axis, y_centre_cm=yc)
    else:
        ok = (near(b["min"][0], POST_X[0]) and near(b["max"][0], POST_X[1]) and near(b["min"][2], POST_Z[0])
              and near(b["max"][2], POST_Z[1]))
        c.check(ok, "POST_BOUNDS|%s|%s" % (name, b))
        c.check(near(b["min"][1], POST_Y_FLIPPED[0], 0.2) and near(b["max"][1], POST_Y_FLIPPED[1], 0.2),
                "POST_HANDEDNESS|%s|%s" % (name, b))
        slope = post_v_slope(c, mesh)
        ref = facts["ref_post_dv_dz"]
        ok, basis = post_v_verdict(slope, ref)
        c.check(ok, "POST_V_DIRECTION|dv/dz=%.6g ref=%s|%s (V must run down)" % (slope, ref, basis))
        pts, tris = _measure(c, name, section_data, c.u, mesh, 0, 0)
        axis = _measure(c, name, axis_from_edges, pts, tris, lambda x: abs(x) < 15.0)
        row.update(post_axis_cm=axis, dv_dz=slope, v_direction_basis=basis)
    return row


def phase_dry(c, _args):
    before = census(c.u)
    targets, facts = preflight(c)
    c.check(census(c.u) == before, "DRY_DIRTIED|%s" % (census(c.u),))
    blockers = []
    if facts["existing_targets"]:
        blockers.append("TARGETS_EXIST|%s" % facts["existing_targets"])
    if before != ([], []):
        blockers.append("EDITOR_DIRTY|%s" % (before,))
    if os.path.exists(RECORD):
        blockers.append("RECORD_EXISTS")
    c.log("BW_IMPORT_DRY_%s|run=%s|targets=%s|ref_post_dv_dz=%s|ref_bay_y_centre=%.3f|blockers=%s|mutated=0"
          % ("OK" if not blockers else "REFUSED", c.run, targets, facts["ref_post_dv_dz"], facts["ref_bay_y_centre_cm"],
             blockers))


def phase_import(c, _args):
    u = c.u
    c.check(census(u) == ([], []), "DIRTY_AT_START|%s" % (census(u),))
    c.check(not os.path.exists(RECORD), "RECORD_EXISTS|REVERT first")
    targets, facts = preflight(c)
    c.check(not facts["existing_targets"], "TARGETS_EXIST|%s" % facts["existing_targets"])
    helpers = pilot(c)
    mesh_paths = [MESHES + "/" + n for n in TARGETS]
    before = folder(u, MESHES)
    c.past_import = True
    for name in TARGETS:
        task = helpers.import_task(os.path.join(FBX_DIR, name + ".fbx"), MESHES + "/" + name, helpers.fbx_options(True))
        u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    strays = sorted(folder(u, MESHES) - before - set(mesh_paths))
    content_dir = u.Paths.convert_relative_path_to_full(u.Paths.project_content_dir())
    deleted = []
    for stray in strays:  # never-saved Interchange by-products only (an on-disk one stops the run)
        c.check(not os.path.exists(os.path.join(content_dir, stray[len("/Game/"):] + ".uasset")), "STRAY_ON_DISK|" + stray)
        c.check(u.EditorAssetLibrary.delete_asset(stray), "STRAY_DELETE|" + stray)
        deleted.append(stray)
    c.check(folder(u, MESHES) - before == set(mesh_paths), "IMPORT_CENSUS|%s" % sorted(folder(u, MESHES) - before))
    c.check(not [p for p in folder(u, MESHES) if "_LOD" in p.rsplit("/", 1)[-1] and p not in before], "LOD_SPLIT_STRAYS")

    readback = {}
    for name in TARGETS:
        readback[name] = gate_mesh(c, name, u.EditorAssetLibrary.load_asset(MESHES + "/" + name), facts)

    tools = u.AssetToolsHelpers.get_asset_tools()
    mi = tools.create_asset(MI_NAME, MATS, u.MaterialInstanceConstant, u.MaterialInstanceConstantFactoryNew())
    c.check(isinstance(mi, u.MaterialInstanceConstant), "MI_CREATE")
    parent = u.EditorAssetLibrary.load_asset(MATS + "/" + MI_PARENT)
    mi.modify()
    u.MaterialEditingLibrary.set_material_instance_parent(mi, parent)  # return value not trusted
    c.check(_pkg(mi.get_editor_property("parent")) == MATS + "/" + MI_PARENT, "MI_PARENT_READBACK")
    tex_names = [str(n) for n in u.MaterialEditingLibrary.get_texture_parameter_names(parent)]
    tex = {}
    for n in tex_names:
        mine = u.MaterialEditingLibrary.get_material_instance_texture_parameter_value(mi, n)
        theirs = u.MaterialEditingLibrary.get_material_instance_texture_parameter_value(parent, n)
        c.check(_pkg(mine) == _pkg(theirs) if theirs else mine is None, "MI_TEXTURE_INHERIT|%s" % n)
        tex[n] = _pkg(theirs) if theirs else None
    c.check(any(tex.values()), "MI_NO_TEXTURES_INHERITED|%s" % tex)

    for name, (_, instances, _) in TARGETS.items():
        mesh = u.EditorAssetLibrary.load_asset(MESHES + "/" + name)
        mesh.modify()
        for index, mi_name in enumerate(instances):
            mesh.set_material(index, u.EditorAssetLibrary.load_asset(MATS + "/" + mi_name))
        bound = [_pkg(s.get_editor_property("material_interface")) for s in mesh.get_editor_property("static_materials")]
        c.check(bound == [MATS + "/" + m for m in instances], "MATERIAL_READBACK|%s|%s" % (name, bound))
        readback[name]["materials"] = bound
        mesh = None

    content, maps = census(u)
    c.check(not maps and set(content) <= set(targets) and set(targets) <= set(content), "DIRTY_SCOPE|%s|%s" % (content, maps))
    for path in targets:
        c.check(u.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False), "SAVE_FAIL|" + path)
    c.check(census(u) == ([], []), "DIRTY_AFTER_SAVE|%s" % (census(u),))
    for path in targets:
        c.check(os.path.isfile(os.path.join(content_dir, path[len("/Game/"):] + ".uasset")), "NOT_ON_DISK|" + path)
        c.check(u.EditorAssetLibrary.does_asset_exist(path), "SAVED_READBACK|" + path)
    rec = {"run": c.run, "state": "imported", "written": datetime.datetime.now().isoformat(timespec="seconds"),
           "packages": targets, "strays_deleted": deleted, "mi": {"path": MATS + "/" + MI_NAME, "parent": MI_PARENT,
                                                                   "textures_inherited": tex},
           "facts": facts, "readback": readback}
    with open(RECORD, "x", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1)
        fh.flush()
        os.fsync(fh.fileno())
    c.log("BW_IMPORT_OK|run=%s|packages=%d|lods=%s|strays_deleted=%d|bay_post_axis=%s|post_axis=%s|record=%s"
          % (c.run, len(targets), [r["lods"] for r in readback.values()], len(deleted),
             readback["SM_FenceBay_short_open_bwc"]["post_axis_cm"][:2],
             readback["SM_FencePost_short_bw"]["post_axis_cm"][:2], RECORD))


def phase_revert(c, _args):
    u = c.u
    c.check(u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world() is None, "PIE_ACTIVE")
    c.check(census(u) == ([], []), "DIRTY_AT_START|%s" % (census(u),))
    c.check(os.path.exists(RECORD), "NO_RECORD")
    rec = json.load(open(RECORD, encoding="utf-8"))
    c.check(rec.get("state") == "imported", "RECORD_STATE|%s" % rec.get("state"))
    ours = set(rec["packages"])
    for path in ours:
        refs = {_pkg(str(r)) for r in u.EditorAssetLibrary.find_package_referencers_for_asset(path, False)}
        foreign = sorted(refs - ours)
        c.check(not foreign, "STILL_REFERENCED|%s|%s (run barbed_apply.py REVERT first)" % (path, foreign))
    order = [p for p in rec["packages"] if not p.endswith("/" + MI_NAME)] + [p for p in rec["packages"] if p.endswith("/" + MI_NAME)]
    for path in order:
        c.check(u.EditorAssetLibrary.delete_asset(path), "DELETE_FAIL|" + path)
        c.check(not u.EditorAssetLibrary.does_asset_exist(path), "STILL_EXISTS|" + path)
    c.check(census(u) == ([], []), "DIRTY_AFTER_REVERT|%s" % (census(u),))
    os.replace(RECORD, RECORD.replace(".json", ".reverted-%s.json" % c.run))
    c.log("BW_IMPORT_REVERT_OK|run=%s|deleted=%d" % (c.run, len(order)))


def main():
    args = json.load(open(ARGS, encoding="utf-8")) if os.path.exists(ARGS) else {}
    mode = str(args.get("mode", "DRY")).upper()
    c = Ctx(mode)
    phases = {"DRY": phase_dry, "IMPORT": phase_import, "REVERT": phase_revert}
    c.check(mode in phases, "UNKNOWN_MODE|%s" % mode)
    c.check(mode == "DRY" or args.get("confirm") == "%s %s" % (mode, CONFIRM_TAIL),
            "CONFIRM_MISSING|want '%s %s'" % (mode, CONFIRM_TAIL))
    c.log("BW_IMPORT_START|run=%s|mode=%s" % (c.run, mode))
    try:
        phases[mode](c, args)
    except BWError:
        raise
    except Exception as exc:  # an API surprise still leaves a run-stamped failure marker
        c.fail("UNEXPECTED|%s: %s" % (type(exc).__name__, exc))


if __name__ != "__bw_offline_test__":
    main()
