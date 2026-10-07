"""Barbed wire on the fence's TOP ROW + line-end posts (Gary 7 Oct, "Coil + strands"). PREPARED, NOT RUN.

NEEDS, in this order:
  1. barbed_import.py IMPORT done (barbed_import_record.json state "imported"): SM_FenceBay_short_open_bwc,
     SM_FenceBay_short_door_gap_bw, SM_FencePost_short_bw, MI_BarbedWire, plus the measured post axes.
  1b. barbed_import.py IMPORT with {"set": "nw"} done (barbed_import_nw_record.json state "imported"):
     SM_FenceBay_short_open_nw, SM_FenceBay_short_door_gap_nw (barbed_nowire.py: the current bays minus the
     concertina, same X/Z bounds and Y centre, so every panel keeps its transform and the Stack rows their height).
  2. The BW build: held patch Scripts/patches/2026-10-07_fence_top_row_wire_and_posts.patch compiled.
     FInfinityStageFenceVariant::TopRowMesh, FInfinityStageUnderpassSettings::FencePostJoints / FencePostMesh /
     FencePostMaterial / FencePostOffsetCm, EInfinityFencePostJoints and the actor's UnderpassFenceTopRowPanelCount /
     UnderpassFencePostCount exist only after it. Without them DRY reports BUILD_MISSING_BW and APPLY/REVERT stop.

Why Mesh -> _nw AND TopRowMesh -> wire bay (Gary 7 Oct: "the wire only needs to appear at the top of the fence"): in
Stack mode the C++ repeats the variant's Mesh on every row (InfinityStageStructureActor.cpp BuildUnderpassFence), and
the CURRENT bays carry the concertina baked in (Tools/FlatV3/build_fence_bay.py coil()), so leaving Mesh alone showed
the coil at every row joint. Mesh becomes the no-wire twin (all rows plain); the patch draws TopRowMesh on the last
row only, from the SAME variant draw, so no tile re-rolls. The Stack row height is the tallest built Mesh's bounds Z
(cpp:596-602): the _nw bays keep 302.676 cm (a lifted copy of the rail holds the top), so rows, tubes and the
top-row fit are unchanged.

Per fenced structure APPLY writes exactly (recording every BEFORE value):
  fence_variant_X.mesh          = the no-wire twin of that variant's Mesh (NW_MAP; short_open -> _open_nw,
                                  short_door_gap -> _door_gap_nw)
  fence_variant_X.top_row_mesh  = the bw twin of that variant's Mesh (MESH_MAP; A/B/C short_open -> _open_bwc,
                                  D short_door_gap -> _door_gap_bw); a weighted variant on any other mesh -> refuse
                                  (variants with no mesh or weight <= 0 are left exactly as they are)
  fence_post_joints   = LINE_END   (one post per side at the line's far end; every other joint carries the bay's own post)
  fence_post_mesh     = SM_FencePost_short_bw;  fence_post_material = None (its own MI_FenceBay_Metal)
  fence_post_offset_cm = mirror of the bays' baked post, from the import's MEASURED axes (post_offset_cm below)
Weights, overlays, materials, heights, tubes: untouched.

Verification after MaterializeStructure, by instance transforms (never component bounds): every non-fence layer
identical (tubes, lights, columns...: the stack top is set by Mesh, so tubes must not move); every panel and overlay at
its old transform (0.5 cm: the bw and nw bays' bounds centre equals the plain bay's - import gates BAY_Y_CENTRE /
NW_Y_CENTRE); panels on the top row in FenceTopRow layers with the mapped wire mesh, every other panel on its _nw
twin, and NO lower-row panel on a wire-carrying mesh (bw/bwc or the old coil bay); top-row count = panels /
rows; posts = sides, each foot on a top-row panel's end joint; C++ counts agree. Then census = the level only -> save
the level -> census clean -> umap changed -> fields read back -> record "applied" -> BW_APPLY_OK|run=..
REVERT: record "applied" and live fields as applied -> restore recorded fields -> materialize -> every fence layer back to
the recorded BEFORE transforms and meshes, no posts, others identical -> save level -> record renamed -> BW_APPLY_REVERT_OK.
A failure after the backup: NOTHING is saved; restart the editor with Don't Save (record + backup stand).

Args barbed_apply_args.json {"mode": "DRY"|"APPLY"|"REVERT", "confirm": "<MODE> BARBEDAPPLY", "structures": [...]}.
Planning/checking helpers are Unreal-free (test_barbed_apply.py). No UE objects at module level.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
import shutil

WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP_REL = ("Content", "InfinityStage", "Dev", "Maps", "L_InfinityStage_V1VerticalSlice.umap")
STRUCTURES = ["Infinity Stage - Structure 0%d" % n for n in range(1, 7)]
CONFIRM_TAIL = "BARBEDAPPLY"
SM = "/Game/InfinityStage/RigAtmos/FenceBay/StaticMeshes/"
MESH_MAP = {SM + "SM_FenceBay_short_open": SM + "SM_FenceBay_short_open_bwc",
            SM + "SM_FenceBay_short_door_gap": SM + "SM_FenceBay_short_door_gap_bw"}
NW_MAP = {SM + "SM_FenceBay_short_open": SM + "SM_FenceBay_short_open_nw",
          SM + "SM_FenceBay_short_door_gap": SM + "SM_FenceBay_short_door_gap_nw"}
# Every mesh that draws wire: the bw twins AND the current bays (their concertina is baked in).
WIRE_MESHES = set(MESH_MAP) | set(MESH_MAP.values())
POST_MESH = SM + "SM_FencePost_short_bw"
VARIANTS = ("fence_variant_a", "fence_variant_b", "fence_variant_c", "fence_variant_d")
TAG_PANEL = "InfinityStage.Structure.Underpass.Fence."
TAG_OVERLAY = "InfinityStage.Structure.Underpass.FenceOverlay."
TAG_FENCE = "InfinityStage.Structure.Underpass.Fence"
TAG_TOP = "InfinityStage.Structure.Underpass.FenceTopRow"
TAG_POSTS = "InfinityStage.Structure.Underpass.FencePosts"
TAG_TUBE_LIGHTS = "InfinityStage.Structure.Underpass.TubeLights"
POS_TOL = 0.5      # cm
JOINT_TOL = 1.0    # cm (post foot vs the panel's end joint)
SCALE_TOL = 1e-4
QUAT_TOL = 1e-4
BW_PROBE_UNDERPASS = ("fence_post_joints", "fence_post_mesh", "fence_post_material", "fence_post_offset_cm")
BW_PROBE_ACTOR = ("underpass_fence_top_row_panel_count", "underpass_fence_post_count")


class BWApplyError(RuntimeError):
    pass


# ============================================================================ pure (no unreal)
def post_offset_cm(import_record):
    """FencePostOffsetCm from the import's measured axes, in the bays' frame (cm).

    The bay carries its post at its local -X end, d = axis_x - bounds_min_x inside the tile. The line-end post is
    its mirror: axis at joint - d (inside the last tile), on the bay post's own line (axis_y - bounds-centre y; the
    C++ puts the bay's bounds centre on the fence line). The stand-alone post's axis sits (px, py) off its pivot.
    """
    bay = import_record["readback"]["SM_FenceBay_short_open_bwc"]
    post = import_record["readback"]["SM_FencePost_short_bw"]
    bx, by = bay["post_axis_cm"][0], bay["post_axis_cm"][1]
    d = bx - bay["bounds_cm"]["min"][0]
    width = bay["bounds_cm"]["max"][0] - bay["bounds_cm"]["min"][0]
    if not (0.0 < d < 0.25 * width):
        raise BWApplyError("BAY_POST_NOT_AT_LOCAL_MINUS_X|d=%.3f" % d)
    px, py = post["post_axis_cm"][0], post["post_axis_cm"][1]
    return [-d - px, (by - bay["y_centre_cm"]) - py, 0.0]


def plan_targets(variants, offset):
    """variants: {key: {"mesh", "weight", "top_row_mesh"}} -> the fields APPLY writes, or raises.

    A built variant (mesh and weight > 0) gets Mesh = its no-wire twin and TopRowMesh = its wire twin; any other
    variant is written back exactly as it is."""
    t = {"fence_post_joints": "LINE_END", "fence_post_mesh": POST_MESH, "fence_post_material": None,
         "fence_post_offset_cm": [round(v, 4) for v in offset]}
    for k in VARIANTS:
        v = variants[k]
        if v["top_row_mesh"] is not None:
            raise BWApplyError("TOP_ROW_ALREADY_SET|%s=%s" % (k, v["top_row_mesh"]))
        if v["mesh"] is None or v["weight"] <= 0.0:
            t[k + ".mesh"] = v["mesh"]
            t[k + ".top_row_mesh"] = None
            continue
        if v["mesh"] not in MESH_MAP or v["mesh"] not in NW_MAP:
            raise BWApplyError("UNMAPPED_VARIANT_MESH|%s=%s" % (k, v["mesh"]))
        t[k + ".mesh"] = NW_MAP[v["mesh"]]
        t[k + ".top_row_mesh"] = MESH_MAP[v["mesh"]]
    return t


def qrot(q, v):
    """Rotate v by unit quaternion q = (x, y, z, w)."""
    x, y, z, w = q
    tx, ty, tz = 2 * (y * v[2] - z * v[1]), 2 * (z * v[0] - x * v[2]), 2 * (x * v[1] - y * v[0])
    return [v[0] + w * tx + (y * tz - z * ty), v[1] + w * ty + (z * tx - x * tz), v[2] + w * tz + (x * ty - y * tx)]


def to_world(xf, local):
    s = xf["scale"]
    r = qrot(xf["quat"], [local[0] * s[0], local[1] * s[1], local[2] * s[2]])
    return [xf["loc"][i] + r[i] for i in range(3)]


def dist(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def same_xf(a, b):
    return (dist(a["loc"], b["loc"]) <= POS_TOL and all(abs(a["scale"][i] - b["scale"][i]) <= SCALE_TOL for i in range(3))
            and abs(abs(sum(a["quat"][i] * b["quat"][i] for i in range(4))) - 1.0) <= QUAT_TOL)


def match(before, after, what):
    """Each `after` entry to a distinct `before` entry at the same transform. Returns (pairs, problems)."""
    free = list(range(len(before)))
    pairs, problems = [], []
    if len(before) != len(after):
        problems.append("%s count %d -> %d" % (what, len(before), len(after)))
    for j, a in enumerate(after):
        hit = next((i for i in free if same_xf(before[i], a)), None)
        if hit is None:
            problems.append("%s at %s has no old twin" % (what, [round(x, 1) for x in a["loc"]]))
            if len(problems) > 6:
                break
            continue
        free.remove(hit)
        pairs.append((hit, j))
    return pairs, problems


def check_others(before, after):
    """Non-fence layers: same keys, same instances in order."""
    p = []
    if sorted(before) != sorted(after):
        p.append("layers %s -> %s" % (sorted(set(before) - set(after)), sorted(set(after) - set(before))))
    for k in before:
        if k in after:
            b, a = before[k], after[k]
            if len(b) != len(a) or not all(same_xf(x, y) for x, y in zip(b, a)):
                p.append("layer %s changed (%d -> %d instances)" % (k, len(b), len(a)))
    return p


def check_apply(before, after, targets, rows, sides, offset, bounds):
    """before/after: snapshots; bounds: {mesh path: {"min","max"}} for the bw bays. Returns problems."""
    p = check_others(before["others"], after["others"])
    pairs, mp = match(before["panels"], after["panels"], "panel")
    p += mp
    tops = 0
    for i, j in pairs:
        b, a = before["panels"][i], after["panels"][j]
        if a["variant"] != b["variant"]:
            p.append("panel variant %s -> %s" % (b["variant"], a["variant"]))
        if a["top"]:
            tops += 1
            want = targets.get("fence_variant_%s.top_row_mesh" % a["variant"].lower())
            if a["mesh"] != want:
                p.append("top-row panel %s mesh %s, want %s" % (a["variant"], a["mesh"], want))
        else:
            # Gary 7 Oct: wire on the TOP row only. A lower-row panel on any wire-carrying mesh fails,
            # whatever the targets say; otherwise it must sit on its variant's planned Mesh (the _nw twin).
            if a["mesh"] in WIRE_MESHES:
                p.append("lower-row panel %s at z %.1f carries wire (%s)" % (a["variant"], a["loc"][2], a["mesh"]))
            want = targets.get("fence_variant_%s.mesh" % a["variant"].lower(), NW_MAP.get(b["mesh"]))
            if a["mesh"] != want:
                p.append("plain panel mesh %s -> %s, want %s" % (b["mesh"], a["mesh"], want))
    # The top row: above every plain panel at the same plan point.
    for a in after["panels"]:
        if a["top"]:
            below = [x for x in after["panels"] if not x["top"] and abs(x["loc"][0] - a["loc"][0]) < 1.0
                     and abs(x["loc"][1] - a["loc"][1]) < 1.0]
            if any(x["loc"][2] >= a["loc"][2] for x in below):
                p.append("top-row panel at %s is not the highest" % [round(v, 1) for v in a["loc"]])
                break
    if rows and len(before["panels"]) % rows == 0 and tops != len(before["panels"]) // rows:
        p.append("top-row panels %d, want %d / %d rows" % (tops, len(before["panels"]), rows))
    p += match(before["overlays"], after["overlays"], "overlay")[1]
    # Posts: one per side, each foot (location less its rotated offset) on a top-row panel's end joint.
    if len(after["posts"]) != sides:
        p.append("posts %d, want %d" % (len(after["posts"]), sides))
    for post in after["posts"]:
        foot = to_world(post, [-offset[0], -offset[1], -offset[2]])
        best = None
        for a in after["panels"]:
            if not a["top"] or a["mesh"] not in bounds:
                continue
            mn, mx = bounds[a["mesh"]]["min"], bounds[a["mesh"]]["max"]
            cy = (mn[1] + mx[1]) * 0.5
            for x in (mn[0], mx[0]):
                d = dist(foot, to_world(a, [x, cy, mn[2]]))
                best = d if best is None or d < best else best
        if best is None or best > JOINT_TOL:
            p.append("post foot %s is %s cm from any top-row end joint" % ([round(v, 1) for v in foot], best))
    return p, tops


def check_revert(recorded, after):
    """Back to the recorded BEFORE: panels/overlays at their transforms with their meshes, no posts, others same."""
    p = check_others(recorded["others"], after["others"])
    pairs, mp = match(recorded["panels"], after["panels"], "panel")
    p += mp
    for i, j in pairs:
        b, a = recorded["panels"][i], after["panels"][j]
        if a["mesh"] != b["mesh"] or a["variant"] != b["variant"] or a["top"]:
            p.append("panel %s/%s -> %s/%s top=%s" % (b["variant"], b["mesh"], a["variant"], a["mesh"], a["top"]))
            break
    p += match(recorded["overlays"], after["overlays"], "overlay")[1]
    if after["posts"]:
        p.append("%d posts left" % len(after["posts"]))
    return p


def same_val(got, want):
    if isinstance(want, list):
        return isinstance(got, list) and len(got) == len(want) and all(abs(g - w) <= 1e-3 for g, w in zip(got, want))
    if isinstance(want, float):
        return isinstance(got, (int, float)) and abs(got - want) <= 1e-3
    return got == want


# ============================================================================ unreal side
def _u():
    import unreal  # noqa: PLC0415
    return unreal


def _path(o):
    return None if o is None else o.get_path_name().split(".")[0]


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def enum_name(v):
    s = str(v)
    s = s.split(".")[-1] if "." in s else s
    return s.split(":")[0].strip("<> ").upper()


class Ctx:
    def __init__(self, mode):
        u = _u()
        self.u, self.mode = u, mode
        self.repo = os.path.normpath(u.Paths.convert_relative_path_to_full(u.Paths.project_dir()))
        self.here = os.path.join(self.repo, "Saved", "CodexConductor", "BarbedWire_20261007")
        self.run = datetime.datetime.now().strftime("BWAPPLY-%Y%m%d-%H%M%S")
        self.record = os.path.join(self.here, "barbed_apply_record.json")
        self.import_record = os.path.join(self.here, "barbed_import_record.json")
        self.import_nw_record = os.path.join(self.here, "barbed_import_nw_record.json")
        self.umap = os.path.join(self.repo, *UMAP_REL)
        self.past_backup = False

    def log(self, msg):
        self.u.log(msg)

    def fail(self, msg):
        tail = "|NOTHING SAVED; restart the editor with Don't Save" if self.past_backup else ""
        self.u.log_error("BW_APPLY_FAILED|run=%s|mode=%s|%s%s" % (self.run, self.mode, msg, tail))
        raise BWApplyError("BW_APPLY_FAILED|run=%s|%s" % (self.run, msg))


def write_json(c, path, payload, exclusive=False):
    tmp = path if exclusive else path + ".tmp"
    with open(tmp, "x" if exclusive else "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1)
        fh.flush()
        os.fsync(fh.fileno())
    if not exclusive:
        os.replace(tmp, path)
    if json.load(open(path, encoding="utf-8")) != json.loads(json.dumps(payload)):
        c.fail("%s did not read back" % os.path.basename(path))


def census(u):
    lib = u.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def guards(c, need_clean):
    u = c.u
    ed = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        c.fail("PIE_ACTIVE")  # refuses; never ends PIE
    world = ed.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != WORLD:
        c.fail("WRONG_WORLD|%s" % (world.get_path_name() if world else None))
    actors = list(u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors())
    if need_clean:
        d = census(u)
        if d != {"content": [], "maps": []}:
            c.fail("DIRTY_BEFORE|" + json.dumps(d))
        bench = [str(a.get_actor_label()) for a in actors if str(a.get_actor_label()).startswith(("ZZ_", "TEMP", "Temp"))]
        if bench:
            c.fail("BENCH_ACTORS|%s" % bench[:6])
        if u.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
            c.fail("SEQUENCER_OPEN")
    return world, actors


def find_structures(c, actors, labels):
    out = {}
    for label in labels:
        hits = [a for a in actors if str(a.get_actor_label()) == label and isinstance(a, c.u.InfinityStageStructureActor)]
        if len(hits) != 1:
            c.fail("STRUCTURE_COUNT|%s|%d" % (label, len(hits)))
        out[label] = hits[0]
    return out


def bw_missing(c, s):
    under = s.get_editor_property("underpass")
    for k in BW_PROBE_UNDERPASS:
        try:
            under.get_editor_property(k)
        except Exception:  # noqa: BLE001
            return "underpass." + k
    for k in BW_PROBE_ACTOR:
        try:
            s.get_editor_property(k)
        except Exception:  # noqa: BLE001
            return k
    try:
        under.get_editor_property(VARIANTS[0]).get_editor_property("top_row_mesh")
    except Exception:  # noqa: BLE001
        return "fence_variant.top_row_mesh"
    if not hasattr(getattr(c.u, "InfinityFencePostJoints", None), "LINE_END"):
        return "InfinityFencePostJoints.LINE_END"
    return None


def read_fields(c, s):
    """The fields APPLY writes, as plain values (paths, enum name, list)."""
    under = s.get_editor_property("underpass")
    o = under.get_editor_property("fence_post_offset_cm")
    out = {"fence_post_joints": enum_name(under.get_editor_property("fence_post_joints")),
           "fence_post_mesh": _path(under.get_editor_property("fence_post_mesh")),
           "fence_post_material": _path(under.get_editor_property("fence_post_material")),
           "fence_post_offset_cm": [float(o.x), float(o.y), float(o.z)]}
    for k in VARIANTS:
        v = under.get_editor_property(k)
        out[k + ".mesh"] = _path(v.get_editor_property("mesh"))
        out[k + ".top_row_mesh"] = _path(v.get_editor_property("top_row_mesh"))
    return out


def read_context(c, s):
    under = s.get_editor_property("underpass")
    variants = {}
    for k in VARIANTS:
        v = under.get_editor_property(k)
        variants[k] = {"mesh": _path(v.get_editor_property("mesh")), "weight": float(v.get_editor_property("weight")),
                       "top_row_mesh": _path(v.get_editor_property("top_row_mesh"))}
    return {"underpass_enabled": bool(under.get_editor_property("enabled")), "fence": bool(under.get_editor_property("fence")),
            "fence_height_mode": enum_name(under.get_editor_property("fence_height_mode")),
            "fence_both_sides": bool(under.get_editor_property("fence_both_sides")),
            "rows": int(s.get_editor_property("underpass_fence_row_count")),
            "panels": int(s.get_editor_property("underpass_fence_panel_count")), "variants": variants}


def _xf(t):
    q = t.rotation
    return {"loc": [t.translation.x, t.translation.y, t.translation.z], "quat": [q.x, q.y, q.z, q.w],
            "scale": [t.scale3d.x, t.scale3d.y, t.scale3d.z]}


def snapshot(c, s):
    """Every ISM layer's instances (get_instance_transform, world) and every tube light. Never cached bounds."""
    u = c.u
    snap = {"panels": [], "overlays": [], "posts": [], "others": {}}
    for comp in s.get_components_by_class(u.InstancedStaticMeshComponent):
        tags = [str(t) for t in comp.get_editor_property("component_tags")]
        mesh = _path(comp.get_editor_property("static_mesh"))
        ents = [_xf(comp.get_instance_transform(i, True)) for i in range(int(comp.get_instance_count()))]
        panel = [t for t in tags if t.startswith(TAG_PANEL)]
        if panel:
            for e in ents:
                e.update(variant=panel[0][len(TAG_PANEL):], mesh=mesh, top=TAG_TOP in tags)
            snap["panels"] += ents
        elif any(t.startswith(TAG_OVERLAY) for t in tags):
            snap["overlays"] += ents
        elif TAG_POSTS in tags:
            snap["posts"] += ents
        else:
            key = "%s|%s" % ("|".join(sorted(tags)), mesh)
            snap["others"].setdefault(key, []).extend(ents)
    for light in s.get_components_by_class(u.RectLightComponent):
        if TAG_TUBE_LIGHTS in [str(t) for t in light.get_editor_property("component_tags")]:
            loc = light.get_world_location()
            snap["others"].setdefault("tube_lights", []).append(
                {"loc": [loc.x, loc.y, loc.z], "quat": [0.0, 0.0, 0.0, 1.0],
                 "scale": [float(light.get_editor_property("intensity")), 1.0, 1.0]})  # intensity rides in scale[0]
    return snap


def set_fields(c, s, t):
    u = c.u
    under = s.get_editor_property("underpass")
    for k in VARIANTS:
        v = under.get_editor_property(k)
        mesh = t[k + ".mesh"]
        v.set_editor_property("mesh", u.load_asset(mesh) if mesh else None)
        mp = t[k + ".top_row_mesh"]
        v.set_editor_property("top_row_mesh", u.load_asset(mp) if mp else None)
        under.set_editor_property(k, v)
    under.set_editor_property("fence_post_joints", getattr(u.InfinityFencePostJoints, t["fence_post_joints"]))
    under.set_editor_property("fence_post_mesh", u.load_asset(t["fence_post_mesh"]) if t["fence_post_mesh"] else None)
    under.set_editor_property("fence_post_material",
                              u.load_asset(t["fence_post_material"]) if t["fence_post_material"] else None)
    o = t["fence_post_offset_cm"]
    under.set_editor_property("fence_post_offset_cm", u.Vector(o[0], o[1], o[2]))
    s.modify()
    s.set_editor_property("underpass", under)
    back = read_fields(c, s)
    bad = {k: (back[k], t[k]) for k in t if not same_val(back[k], t[k])}
    if bad:
        c.fail("READBACK|%s|%s" % (s.get_actor_label(), json.dumps(bad, default=str)))


def load_import(c):
    if not os.path.exists(c.import_record):
        c.fail("IMPORT_NOT_DONE|run barbed_import.py IMPORT first")
    rec = json.load(open(c.import_record, encoding="utf-8"))
    if rec.get("state") != "imported":
        c.fail("IMPORT_RECORD_STATE|%s" % rec.get("state"))
    if not os.path.exists(c.import_nw_record):
        c.fail("IMPORT_NW_NOT_DONE|run barbed_import.py IMPORT with set nw first")
    nw = json.load(open(c.import_nw_record, encoding="utf-8"))
    if nw.get("state") != "imported" or nw.get("set") != "nw":
        c.fail("IMPORT_NW_RECORD_STATE|%s" % nw.get("state"))
    for p in list(MESH_MAP.values()) + list(NW_MAP.values()) + [POST_MESH]:
        if not c.u.EditorAssetLibrary.does_asset_exist(p):
            c.fail("ASSET_MISSING|" + p)
    bounds = {SM + n: rec["readback"][n]["bounds_cm"] for n in ("SM_FenceBay_short_open_bwc", "SM_FenceBay_short_door_gap_bw")}
    return rec, post_offset_cm(rec), bounds


def _backup(c, tag):
    backup = os.path.join(c.repo, "Backups", "%s-%s" % (tag, c.run))
    os.makedirs(backup)
    c.past_backup = True
    shutil.copy2(c.umap, backup)
    shutil.copy2(c.record, backup)
    pre = _sha(c.umap)
    if _sha(os.path.join(backup, UMAP_REL[-1])) != pre:
        c.fail("BACKUP_MISMATCH")
    c.log("BW_APPLY_BACKUP_OK|run=%s|%s" % (c.run, backup))
    return backup, pre


def _save(c, world, pre_sha):
    u = c.u
    d = census(u)
    if d["content"] or d["maps"] != [WORLD]:
        c.fail("DIRTY_SCOPE|%s" % json.dumps(d))
    if not u.EditorLoadingAndSavingUtils.save_map(world, WORLD):
        c.fail("SAVE_FAILED")
    if census(u) != {"content": [], "maps": []}:
        c.fail("POST_SAVE_DIRTY|%s" % json.dumps(census(u)))
    if _sha(c.umap) == pre_sha:
        c.fail("UMAP_UNCHANGED_ON_DISK")


def collect(c, structures, offset):
    rows, skipped = {}, {}
    for label, s in structures.items():
        ctx = read_context(c, s)
        if not (ctx["underpass_enabled"] and ctx["fence"] and ctx["panels"] > 0):
            skipped[label] = "no fence built"
            continue
        rows[label] = {"ctx": ctx, "before": read_fields(c, s), "targets": plan_targets(ctx["variants"], offset)}
    return rows, skipped


def phase_dry(c, args):
    u = c.u
    _, actors = guards(c, need_clean=False)
    before = census(u)
    structures = find_structures(c, actors, args["structures"])
    live = []
    missing = bw_missing(c, list(structures.values())[0])
    if missing:
        live.append("BUILD_MISSING_BW|%s: build 2026-10-07_fence_top_row_wire_and_posts.patch first" % missing)
    try:
        _, offset, _ = load_import(c)
    except BWApplyError as exc:
        live.append(str(exc))
        offset = None
    rows, skipped = ({}, {})
    if not missing and offset is not None:
        rows, skipped = collect(c, structures, offset)
    if census(u) != before:
        c.fail("DRY dirtied %s -> %s" % (before, census(u)))
    if before != {"content": [], "maps": []}:
        live.append("editor dirty %s" % json.dumps(before))
    if os.path.exists(c.record):
        live.append("record exists (applied, not reverted)")
    for label, r in rows.items():
        c.log("BW_APPLY_DRY_ROW|run=%s|%s|mode=%s|rows=%d|panels=%d|before=%s|targets=%s"
              % (c.run, label, r["ctx"]["fence_height_mode"], r["ctx"]["rows"], r["ctx"]["panels"],
                 json.dumps(r["before"]), json.dumps(r["targets"])))
    ok = not live
    c.log("BW_APPLY_DRY_%s|run=%s|apply_ready=%d|fenced=%s|skipped=%s|offset=%s|live_blockers=%s|mutated=0"
          % ("OK" if ok else "REFUSED", c.run, int(ok), sorted(rows), skipped, offset, live))


def phase_apply(c, args):
    world, actors = guards(c, need_clean=True)
    structures = find_structures(c, actors, args["structures"])
    missing = bw_missing(c, list(structures.values())[0])
    if missing:
        c.fail("BUILD_MISSING_BW|%s" % missing)
    if os.path.exists(c.record):
        c.fail("RECORD_EXISTS|REVERT first (or, for a failed APPLY, Don't-Save restart then archive the record)")
    _, offset, bounds = load_import(c)
    rows, skipped = collect(c, structures, offset)
    if not rows:
        c.fail("NOTHING_FENCED|%s" % skipped)
    snaps = {label: snapshot(c, structures[label]) for label in rows}
    rec = {"run": c.run, "state": "applying", "written": datetime.datetime.now().isoformat(timespec="seconds"),
           "args": args, "offset_cm": offset, "skipped": skipped,
           "before": {k: r["before"] for k, r in rows.items()}, "ctx": {k: r["ctx"] for k, r in rows.items()},
           "targets": {k: r["targets"] for k, r in rows.items()}, "snap": snaps}
    write_json(c, c.record, rec, exclusive=True)
    backup, pre_sha = _backup(c, "PreBarbedWire")
    built = {}
    for label, r in rows.items():
        s = structures[label]
        set_fields(c, s, r["targets"])
        if not s.materialize_structure():
            c.fail("MATERIALIZE_FAILED|%s" % label)
        if not s.is_structure_current():
            c.fail("NOT_CURRENT|%s" % label)
        after = snapshot(c, s)
        sides = 2 if r["ctx"]["fence_both_sides"] else 1
        rows_n = r["ctx"]["rows"] if r["ctx"]["fence_height_mode"] == "STACK" else 1
        p, tops = check_apply(snaps[label], after, r["targets"], rows_n, sides, offset, bounds)
        cpp_tops = int(s.get_editor_property("underpass_fence_top_row_panel_count"))
        cpp_posts = int(s.get_editor_property("underpass_fence_post_count"))
        if cpp_tops != tops or cpp_posts != len(after["posts"]):
            p.append("C++ counts top=%d posts=%d, read top=%d posts=%d" % (cpp_tops, cpp_posts, tops, len(after["posts"])))
        if p:
            c.fail("LAYERS|%s|%s" % (label, p[:12]))
        built[label] = {"panels": len(after["panels"]), "top_row": tops, "overlays": len(after["overlays"]),
                        "posts": len(after["posts"])}
        c.log("BW_APPLY_BUILT|run=%s|%s|%s" % (c.run, label, json.dumps(built[label])))
    _save(c, world, pre_sha)
    back = {label: read_fields(c, structures[label]) for label in rows}
    bad = {k: v for k, v in back.items() if any(not same_val(v[f], rows[k]["targets"][f]) for f in rows[k]["targets"])}
    if bad:
        c.fail("SAVED_READBACK|%s" % json.dumps(bad))
    rec.update(state="applied", applied=datetime.datetime.now().isoformat(timespec="seconds"), backup=backup,
               after=back, built=built)
    write_json(c, c.record, rec)
    c.log("BW_APPLY_OK|run=%s|structures=%d|built=%s|level_saved=1|dirty_after=0+0|backup=%s"
          % (c.run, len(built), json.dumps(built), backup))


def phase_revert(c, args):
    world, actors = guards(c, need_clean=True)
    if not os.path.exists(c.record):
        c.fail("NO_RECORD")
    rec = json.load(open(c.record, encoding="utf-8"))
    if rec.get("state") != "applied":
        c.fail("RECORD_STATE|%s: an APPLY that did not save is undone by a Don't-Save restart, not REVERT" % rec.get("state"))
    structures = find_structures(c, actors, list(rec["before"]))
    missing = bw_missing(c, list(structures.values())[0])
    if missing:
        c.fail("BUILD_MISSING_BW|%s" % missing)
    for label, s in structures.items():
        live = read_fields(c, s)
        if any(not same_val(live[k], rec["after"][label][k]) for k in rec["after"][label]):
            c.fail("NOT_APPLIED_STATE|%s|live %s vs applied %s" % (label, live, rec["after"][label]))
    backup, pre_sha = _backup(c, "PreBarbedWireRevert")
    for label, s in structures.items():
        set_fields(c, s, rec["before"][label])
        if not s.materialize_structure():
            c.fail("MATERIALIZE_FAILED|%s" % label)
        if not s.is_structure_current():
            c.fail("NOT_CURRENT|%s" % label)
        p = check_revert(rec["snap"][label], snapshot(c, s))
        if p:
            c.fail("NOT_RESTORED|%s|%s" % (label, p[:12]))
    _save(c, world, pre_sha)
    os.replace(c.record, c.record.replace(".json", ".reverted-%s.json" % c.run))
    c.log("BW_APPLY_REVERT_OK|run=%s|structures=%d|level_saved=1|dirty_after=0+0|backup=%s" % (c.run, len(structures), backup))


def main(args=None):
    c = Ctx("DRY")
    if args is None:
        path = os.path.join(c.here, "barbed_apply_args.json")
        args = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    a = {"mode": "DRY", "structures": list(STRUCTURES)}
    a.update(args)
    mode = str(a.get("mode", "DRY")).upper()
    c.mode = mode
    phases = {"DRY": phase_dry, "APPLY": phase_apply, "REVERT": phase_revert}
    if mode not in phases:
        c.fail("UNKNOWN_MODE|%s" % mode)
    if mode != "DRY" and a.get("confirm") != "%s %s" % (mode, CONFIRM_TAIL):
        c.fail("CONFIRM_MISSING|want '%s %s'" % (mode, CONFIRM_TAIL))
    c.log("BW_APPLY_START|run=%s|mode=%s" % (c.run, mode))
    try:
        phases[mode](c, a)
    except BWApplyError:
        raise
    except Exception as exc:  # an API surprise still leaves a run-stamped failure marker
        c.fail("UNEXPECTED|%s: %s" % (type(exc).__name__, exc))


if __name__ == "__barbed_apply_runner__":
    main()
