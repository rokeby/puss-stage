"""OFFLINE harness for s3_props_ue.py (pure planning, gates, ops round trip, texture prep) with +/- controls.
    python test_s3_props.py        -> prints PASS/FAIL per check, writes test_s3_props_report.json, exit 1 on any FAIL.
Live inputs used read-only: probe_s3_clam_rock.json (7 Oct), CodexMocap/clam_sequence_routing.json (12 Sep),
CodexStructure/s3_cast_reveal_record.json (1 Oct), the five prop manifests / FBX / PNG headers."""
import copy
import io
import json
import os
import runpy
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
T = runpy.run_path(os.path.join(HERE, "s3_props_ue.py"))
M = runpy.run_path(os.path.join(HERE, "fbx_top_measure.py"))
PlanError = T["PlanError"]
CC = os.path.dirname(HERE)
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append({"check": name, "ok": bool(cond), "detail": str(detail)[:400]})
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  " + str(detail)[:400]))


def refuses(fn, needle):
    try:
        fn()
    except PlanError as exc:
        return needle in str(exc), str(exc)
    return False, "did not refuse"


# ------------------------------------------------------------------ A. table vs manifests / files
for name, row in T["PROPS"].items():
    p = T["prop_paths"](name)
    man = json.load(open(p["manifest"], encoding="utf-8"))
    size, min_z, slots = T["manifest_expect"](man)
    check("A.manifest_matches_table|" + name, T["near"](size, row["size_cm"], 0.011) and abs(min_z - row["min_z_cm"]) < 0.011
          and slots == 1, (size, min_z, slots))
    check("A.fbx_exists|" + name, os.path.isfile(p["fbx"]), p["fbx"])
    for role in T["TEX_ROLES"]:
        f = p["tex"][role]["file"]
        if name == "GraniteMillstone" and role == "BaseColor":
            ok, msg = refuses(lambda: T["tex_source_check"](name, role), "TEX_SOURCE_MISSING") if not os.path.isfile(f) \
                else (T["tex_source_check"](name, role)["w"] == 8192, "prepared")
            check("A.millstone_8k_source_gate(missing until PREP, or 8192 after)", ok, msg)
        else:
            r = T["tex_source_check"](name, role)
            check("A.tex_source_ok|%s|%s" % (name, role), r["w"] == r["h"] == 4096, r)

# 12K source must be refused by the IMPORT_TEX gate (- control)
saved = dict(T["PROPS"]["GraniteMillstone"]["tex_src"])
T["PROPS"]["GraniteMillstone"]["tex_src"]["BaseColor"] = "Export/T_GraniteMillstone_BaseColor.png"
ok, msg = refuses(lambda: T["tex_source_check"]("GraniteMillstone", "BaseColor"), "TEX_DIM")
check("A.12k_basecolor_refused(-)", ok, msg)
T["PROPS"]["GraniteMillstone"]["tex_src"].clear()
T["PROPS"]["GraniteMillstone"]["tex_src"].update(saved)

# PNG header reader vs PIL
from PIL import Image  # noqa: E402
Image.MAX_IMAGE_PIXELS = None
for name in T["PROPS"]:
    f = T["DERIVED"] + "%s/Export/T_%s_Roughness.png" % (name, name)
    w, h, d, c = T["png_ihdr"](f)
    with Image.open(f) as im:
        check("A.png_ihdr_matches_PIL|" + name, (w, h) == im.size and d == 8, ((w, h), im.size, d, c))

# ------------------------------------------------------------------ B. bounds gate per prop
for name, row in T["PROPS"].items():
    size, mz = row["size_cm"], row["min_z_cm"]
    good = T["expected_bounds"](size, mz)
    check("B.exact_bounds_pass(+)|" + name, T["bounds_check"](good, size, mz) == [], T["bounds_check"](good, size, mz))
    jitter = {"min": [v - 0.1 for v in good["min"]], "max": [v + 0.1 for v in good["max"]]}
    check("B.small_jitter_pass(+)|" + name, T["bounds_check"](jitter, size, mz) == [])
    big = {k: [v * 100.0 for v in good[k]] for k in good}
    f = T["bounds_check"](big, size, mz)
    check("B.100x_refused(-)|" + name, f and (f[0].startswith("SCALE_100X") or (mz < 0 and f)), f[:2])
    small = {k: [v * 0.01 for v in good[k]] for k in good}
    check("B.0.01x_refused(-)|" + name, bool(T["bounds_check"](small, size, mz)))
    rot = {"min": [good["min"][0], good["min"][2] - (size[2] / 2.0 + mz), -size[1] / 2.0],
           "max": [good["max"][0], good["max"][2] - (size[2] / 2.0 + mz), size[1] / 2.0]}   # pitched 90 (Y<->Z)
    f = T["bounds_check"](rot, size, mz)
    check("B.pitched90_refused(-)|" + name, bool(f), f[:2])
    swap = {"min": [good["min"][1], good["min"][0], good["min"][2]], "max": [good["max"][1], good["max"][0], good["max"][2]]}
    f = T["bounds_check"](swap, size, mz)
    detectable = abs(size[0] - size[1]) > T["bounds_tol"](size)[0]
    check("B.yaw90_swap_%s|%s" % ("refused(-)" if detectable else "UNDETECTABLE(known: |dx-dy| <= tol)", name),
          bool(f) == detectable, (f[:1], size))
# the -30 cm pivot case
ss = T["PROPS"]["HoledStandingStone"]
wrong_pivot = T["expected_bounds"](ss["size_cm"], 0.0)
f = T["bounds_check"](wrong_pivot, ss["size_cm"], ss["min_z_cm"])
check("B.standing_stone_pivot_at_base_refused(-)", bool(f) and any("MIN_Z" in x for x in f), f[:2])
check("B.standing_stone_pivot_sand_line_pass(+)", T["bounds_check"](T["expected_bounds"](ss["size_cm"], -30.0),
                                                                   ss["size_cm"], -30.0) == [])

# ------------------------------------------------------------------ B2. FBX geometry (the actual import input)
for name in T["PROPS"]:
    try:
        r = M["measure"](name)
        man_size = T["PROPS"][name]["size_cm"]
        ok = T["near"](r["size_cm_file_axes"], man_size, 0.15) and abs(r["peak_height_cm"] - man_size[2]) < 0.01
        check("B2.fbx_geometry_matches_manifest|" + name, ok, (r["size_cm_file_axes"], man_size))
    except Exception as exc:  # noqa: BLE001
        check("B2.fbx_geometry_matches_manifest|" + name, False, repr(exc))
mill = json.load(open(os.path.join(HERE, "s3_millstone_fbx_measure.json"), encoding="utf-8"))
axis_top = mill["radial_upper_surface_cm"]["rows"][0][1]
check("B2.top_offset_default_matches_fbx_axis_top", abs(T["APPLY_DEFAULTS"]["top_offset_cm"] - axis_top) < 0.1,
      (T["APPLY_DEFAULTS"]["top_offset_cm"], axis_top))

# ------------------------------------------------------------------ C. material graph
check("C.graph_spec_clean(+)", T["graph_problems"]() == [], T["graph_problems"]())
orig_spec = T["graph_spec"]


def bad_spec():
    n, e, p = orig_spec()
    n["Orphan"] = ("scalar", 1.0)
    return n, e, p


T["graph_problems"].__globals__["graph_spec"] = bad_spec
check("C.graph_orphan_detected(-)", any("UNUSED_NODE|Orphan" in x for x in T["graph_problems"]()))
T["graph_problems"].__globals__["graph_spec"] = orig_spec
re = T["rough_eval"]
check("C.rough_override_off_multiplies", abs(re(0.40, 1.95, -1.0) - 0.78) < 1e-9)
check("C.rough_override_on_replaces", abs(re(0.40, 1.95, 0.78) - 0.78) < 1e-9 and abs(re(0.9, 1.0, 0.2) - 0.2) < 1e-9)
check("C.rough_clamped", re(0.9, 2.0, -1.0) == 1.0)
check("C.legbone_median_to_0.78", abs(0.40 * T["PROPS"]["HominidLegBone"]["mi_scalars"]["RoughnessMultiplier"] - 0.78) < 1e-9)
check("C.tex_roles", T["TEX_ROLES"]["N"][1:4] == ("TC_NORMALMAP", False, False) and
      T["TEX_ROLES"]["BaseColor"][1:3] == ("TC_DEFAULT", True) and T["TEX_ROLES"]["Roughness"][1:3] == ("TC_MASKS", False))

# ------------------------------------------------------------------ D. gates
check("D.dirty_census_refuses(-)", refuses(lambda: T["gate_census"]({"content": ["/Game/X"], "maps": []}, "APPLY"),
                                           "DIRTY_BEFORE")[0])
check("D.dirty_map_refuses_import(-)", refuses(lambda: T["gate_census"]({"content": [], "maps": ["/Game/M"]},
                                                                         "IMPORT_MESH"), "DIRTY_BEFORE")[0])
check("D.dry_tolerates_dirty(+)", T["gate_census"]({"content": ["/Game/X"], "maps": []}, "DRY") is False)
check("D.clean_census_ok(+)", T["gate_census"]({"content": [], "maps": []}, "APPLY") is True)
check("D.confirm_required(-)", refuses(lambda: T["check_mode"]({"mode": "APPLY"}, False, False), "CONFIRM_MISSING")[0])
check("D.apply_twice_refused(-)", refuses(lambda: T["check_mode"]({"mode": "APPLY", "confirm": "APPLY S3PROPS"}, True, False),
                                          "ALREADY_APPLIED")[0])
check("D.revert_without_record_refused(-)", refuses(lambda: T["check_mode"]({"mode": "REVERT", "confirm": "REVERT S3PROPS"},
                                                                             False, False), "NO_APPLY_RECORD")[0])
check("D.import_unknown_prop_refused(-)", refuses(lambda: T["check_mode"](
    {"mode": "IMPORT_MESH", "confirm": "IMPORT_MESH S3PROPS", "prop": "Nope"}, False, False), "PROP")[0])

# ------------------------------------------------------------------ E. APPLY plan from the live probe
probe = {r["label"]: r for r in json.load(open(os.path.join(CC, "probe_s3_clam_rock.json"), encoding="utf-8"))}
routing = json.load(open(os.path.join(os.path.dirname(CC), "CodexMocap", "clam_sequence_routing.json"), encoding="utf-8"))
clams_seq = [s for s in routing if s["path"] == "/Game/Scenes/LS_Clams"][0]
seq_tracks = {b["name"]: b["tracks"] for b in clams_seq["bindings"]}
reveal_rec = json.load(open(os.path.join(os.path.dirname(CC), "CodexStructure", "s3_cast_reveal_record.json"), encoding="utf-8"))
ped_guid = [b for b in reveal_rec["bindings"] if b["label"] == "tg0pfjxda_tier_0"][0]["binding_guid"]
PED_PATH = WORLD_PFX = T["WORLD"] + ".L_InfinityStage_V1VerticalSlice:PersistentLevel.StaticMeshActor_4"


def base_state(keyed=True):
    clams = []
    for lab, obj in (("source_Anim", "SkeletalMeshActor_1"), ("Clam_with_Pearl_Clam_with_Pearl_0", "StaticMeshActor_6")):
        r = probe[lab]
        cx = [(r["min"][i] + r["max"][i]) / 2 for i in range(3)]
        tracks = {"/Game/Scenes/LS_Clams": seq_tracks[lab] if keyed else ["MovieSceneSkeletalAnimationTrack"],
                  "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03": None,
                  T["RISE"]: ["MovieSceneVisibilityTrack"]}
        clams.append({"label": lab, "object_path": "PersistentLevel." + obj, "location": cx,
                      "aabb_world": {"min": r["min"], "max": r["max"]}, "parent": r["parent"], "tracks": tracks})
    p = probe["Clam_Pedastal"]
    return {"root": {"world": {"location": list(T["ROOT_LANDED_WORLD"]), "rotation": [0, 0, 0], "scale": [1, 1, 1]}},
            "pedestal": {"label": "Clam_Pedastal", "object_name": "StaticMeshActor_4", "object_path": PED_PATH,
                         "parent": None, "aabb_world": {"min": p["min"], "max": p["max"]}, "mobility": "STATIC",
                         "actor_hidden": True, "comp_visible": True, "comp_hidden_in_game": False},
            "temp_actors": [], "label_count": {"S3 Granite Millstone": 0}, "assets": {"mesh": True, "mi": True},
            "clams": clams,
            "rise": {"pedestal_binding": {"guid": ped_guid, "resolved": [PED_PATH], "visibility_sections": [
                {"range_s": [0.0, 37.2], "completion_mode": "RESTORE_STATE", "channels": 1,
                 "keys": [[0, False], [111, True]], "fps": 24.0}]}},
            "floors": [{"label": "S3 Beach V2 Sand Floor", "visible": True, "kind": "mesh",
                        "samples_z": [9.8, 10.4, 11.0, 11.5, 12.0, 12.6, 13.1]},
                       {"label": "S3 Hangar Deck", "visible": True, "kind": "box", "samples_z": [-5.0]}]}


st = base_state(keyed=True)
plan = T["plan_apply"](st, {})
check("E.xy_is_pedestal_centre", T["near"](plan["location"][:2], [14421.79, 159999.34], 0.01), plan["location"])
check("E.floor_is_sand_median_minus_2", plan["floor"]["label"] == "S3 Beach V2 Sand Floor" and
      abs(plan["location"][2] - (11.5 - 2.0)) < 1e-9, plan["floor"])
check("E.top_z", abs(plan["top_z"] - (9.5 + 128.6)) < 1e-9, plan["top_z"])
check("E.keyed_clams_skipped(-)", plan["clams"]["action"] == "SKIPPED_KEYED" and
      all(c["after_location"] == c["before_location"] for c in plan["clams"]["rows"]), plan["clams"]["action"])
check("E.keyed_verdicts", [c["verdict"] for c in plan["clams"]["rows"]] == ["KEYED", "KEYED"])
check("E.not_attached_and_revealed", plan["actor_hidden_in_game"] and plan["reveal"]["copy_from_guid"] == ped_guid)
check("E.pedestal_after_hidden", plan["pedestal"]["after"] == {"actor_hidden": True, "comp_visible": False,
                                                               "comp_hidden_in_game": True})
check("E.inside_stone_reported", all(c["inside_stone_cm"] > 0 for c in plan["clams"]["rows"]),
      [(c["label"], c["inside_stone_cm"], c["top_above_stone_cm"]) for c in plan["clams"]["rows"]])
st_u = base_state(keyed=False)
pu = T["plan_apply"](st_u, {})
dz = pu["top_z"] - min(c["bottom_z"] for c in pu["clams"]["rows"])
check("E.unkeyed_clams_moved(+)", pu["clams"]["action"] == "MOVE" and abs(pu["clams"]["delta_z"] - round(dz, 3)) < 1e-9 and
      all(abs(c["after_location"][2] - c["before_location"][2] - dz) < 1e-9 for c in pu["clams"]["rows"]), pu["clams"]["delta_z"])
check("E.unkeyed_lowest_bottom_on_top", abs(min(c["bottom_z"] for c in pu["clams"]["rows"]) + dz - pu["top_z"]) < 1e-9)
st_x = base_state(keyed=False)
st_x["clams"][0]["tracks"]["/Game/Scenes/LS_Clams"] = "UNREAD"
check("E.unreadable_sequence_fails_closed(-)", T["plan_apply"](st_x, {})["clams"]["action"] == "SKIPPED_KEYED")
st_n = base_state(keyed=False)
st_n["clams"][1]["tracks"] = {}
check("E.no_track_data_fails_closed(-)", T["plan_apply"](st_n, {})["clams"]["action"] == "SKIPPED_KEYED")
check("E.reseat_never(+)", T["plan_apply"](base_state(False), {"reseat_clams": "never"})["clams"]["action"] == "SKIPPED_BY_ARGS")


def mut(fn):
    s = base_state()
    fn(s)
    return s


neg = [
    ("root_not_landed", lambda s: s["root"]["world"].update(location=[11421.97, 160000.0, -3620.0]), "ROOT_NOT_LANDED"),
    ("temp_actor", lambda s: s.update(temp_actors=["ZZ_Bench"]), "TEMP_ACTORS_PRESENT"),
    ("label_exists", lambda s: s["label_count"].update({"S3 Granite Millstone": 1}), "LABEL_EXISTS"),
    ("assets_missing", lambda s: s["assets"].update(mi=False), "ASSETS_MISSING"),
    ("pedestal_renamed_object", lambda s: s["pedestal"].update(object_name="StaticMeshActor_9"), "PEDESTAL_OBJECT"),
    ("no_reveal_binding", lambda s: s["rise"].update(pedestal_binding=None), "PEDESTAL_REVEAL_BINDING"),
    ("floor_spread", lambda s: s["floors"][0].update(samples_z=[5, 8, 11, 14, 20]), "FLOOR_SPREAD"),
    ("floor_unmeasured", lambda s: s.update(floors=[{"label": "S3 Beach V2 Sand Floor", "visible": True,
                                                    "kind": "mesh", "samples_z": [12.0]}]), "FLOOR_UNMEASURED"),
    ("clam_missing", lambda s: s["clams"].pop(), "CLAM_MISSING"),
]
for nm, fn, needle in neg:
    ok, msg = refuses(lambda fn=fn: T["plan_apply"](mut(fn), {}), needle)
    check("E.refuse_%s(-)" % nm, ok, msg)
ok, msg = refuses(lambda: T["plan_apply"](base_state(), {"xy_world": [11300.0, 160000.0]}), "GUARD_LOCAL_BOX")
check("E.refuse_outside_landed_box(-)", ok, msg)
check("E.spread_accepted_by_flag(+)", T["plan_apply"](mut(lambda s: s["floors"][0].update(samples_z=[5, 8, 11, 14, 20])),
                                                      {"accept_floor_spread": True})["floor"]["spread"] == 15)
check("E.hidden_sand_falls_to_deck", T["plan_apply"](mut(lambda s: s["floors"][0].update(visible=False)), {})["floor"]["label"]
      == "S3 Hangar Deck")
ok, msg = refuses(lambda: T["plan_apply"](base_state(), {"prop": "HominidJaw"}), "APPLY_IS_MILLSTONE_ONLY")
check("E.apply_refuses_other_props(-)", ok, msg)

# ------------------------------------------------------------------ F. ops round trip (revert exact)
def world_from(state):
    w = {state["pedestal"]["object_path"]: {"label": "Clam_Pedastal", "location": [0, 0, 0],
                                            "flags": {k: state["pedestal"][k] for k in ("actor_hidden", "comp_visible",
                                                                                        "comp_hidden_in_game")}}}
    for c in state["clams"]:
        w[c["object_path"]] = {"label": c["label"], "location": list(c["location"]), "flags": {}}
    w["__bindings__"] = {ped_guid: PED_PATH}
    return w


for keyed in (True, False):
    s = base_state(keyed)
    pl = T["plan_apply"](s, {})
    w0 = world_from(s)
    w1 = T["simulate"](w0, T["apply_ops"](pl))
    path = "PersistentLevel.NEW_" + pl["label"]
    rec = {"plan": json.loads(json.dumps(pl)), "actor_path": path, "reveal_binding_guid": "GUID_" + pl["label"]}
    check("F.apply_effects|keyed=%s" % keyed, path in w1 and w1[PED_PATH]["flags"] == pl["pedestal"]["after"] and
          w1["__bindings__"].get(rec["reveal_binding_guid"]) == path)
    w2 = T["simulate"](w1, T["revert_ops"](rec))
    check("F.revert_exact(+)|keyed=%s" % keyed, w2 == w0, json.dumps(w2)[:300])
    bad = copy.deepcopy(rec)
    bad["plan"]["pedestal"]["before"]["comp_visible"] = False
    check("F.tampered_record_detected(-)|keyed=%s" % keyed, T["simulate"](w1, T["revert_ops"](bad)) != w0)
    wrong = copy.deepcopy(rec)
    wrong["actor_path"] = "PersistentLevel.SomeoneElse"
    ok, msg = refuses(lambda: T["simulate"](w1, T["revert_ops"](wrong)), "SIM_BINDING_MISMATCH")
    check("F.revert_refuses_foreign_binding(-)|keyed=%s" % keyed, ok, msg)

# ------------------------------------------------------------------ G. PLACE plan
root = {"location": list(T["ROOT_LANDED_WORLD"]), "rotation": [0, 0, 0], "scale": [1, 1, 1]}
pst = {"root": {"world": root}, "temp_actors": [], "label_count": {},
       "assets_by_prop": {n: {"mesh": True, "mi": True} for n in T["PROPS"]},
       "rise": base_state()["rise"],
       "floors_by_label": {"S3 Holed Stone": [{"label": "S", "visible": True, "kind": "mesh", "samples_z": [10, 11, 12]}],
                           "S3 Jaw 01": [{"label": "S", "visible": True, "kind": "mesh", "samples_z": [12, 12.5, 13]}]}}
pp = T["plan_place"](pst, [{"prop": "HoledStandingStone", "label": "S3 Holed Stone", "xy_root_local": [5000.0, 600.0],
                            "burial_cm": 0.0},
                           {"prop": "HominidJaw", "label": "S3 Jaw 01", "xy_root_local": [2900.0, 120.0], "burial_cm": 3.0,
                            "yaw_deg": 35.0}])
check("G.standing_stone_pivot_on_surface_30cm_buried", abs(pp[0]["location"][2] - 11.0) < 1e-9 and
      abs(pp[0]["buried_cm"] - 30.0) < 1e-9 and abs(pp[0]["world_box"]["min"][2] - (11.0 - 30.0)) < 1e-9, pp[0]["location"])
check("G.root_local_xy", T["near"](pp[0]["location"][:2], [11421.97275 + 5000.0, 160600.0], 1e-6))
check("G.jaw_part_buried", abs(pp[1]["location"][2] - 9.5) < 1e-9 and pp[1]["buried_cm"] == 3.0)
ok, msg = refuses(lambda: T["plan_place"](pst, []), "NO_PLACEMENTS")
check("G.empty_placements_refused(-)", ok, msg)
ok, msg = refuses(lambda: T["plan_place"](pst, [{"prop": "HominidJaw", "label": "S3 Jaw 01", "xy_root_local": [9000, 0]}]),
                  "GUARD_LOCAL_BOX")
check("G.outside_box_refused(-)", ok, msg)
check("G.placements_template_empty", json.load(open(os.path.join(HERE, "s3_props_placements.json")))["placements"] == [])

# ------------------------------------------------------------------ H. texture prep (synthetic)
tmp = tempfile.mkdtemp(prefix="s3props_")
from PIL import PngImagePlugin  # noqa: E402
cases = {"srgb": {"pnginfo": (b"sRGB", bytes([0]))}, "gamma": {"pnginfo": (b"gAMA", struct.pack(">I", 45455))},
         "none": {}, "icc": {"icc": True}}
for nm, spec in cases.items():
    src = os.path.join(tmp, "src_%s.png" % nm)
    im = Image.new("RGB", (96, 96), (200, 120, 40))
    kw = {}
    if "pnginfo" in spec:
        pi = PngImagePlugin.PngInfo()
        pi.add(*spec["pnginfo"])
        kw["pnginfo"] = pi
    if spec.get("icc"):
        from PIL import ImageCms
        kw["icc_profile"] = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    im.save(src, **kw)
    sinfo = Image.open(src).info
    rec = T["prep_texture"](src, os.path.join(tmp, "out", "dst_%s.png" % nm), 64)
    out = Image.open(rec["dst"])
    check("H.prep_dims_mode(+)|" + nm, out.size == (64, 64) and out.mode == "RGB", (out.size, out.mode))
    check("H.prep_chunks_preserved(+)|" + nm, out.info.get("srgb") == sinfo.get("srgb") and
          out.info.get("icc_profile") == sinfo.get("icc_profile") and
          (("gamma" in out.info) == ("gamma" in sinfo)), (sinfo.keys(), out.info.keys()))
    out.close()
# - control: a plain PIL save DROPS the sRGB chunk (so the preserve step is load-bearing)
plain = os.path.join(tmp, "plain.png")
Image.open(os.path.join(tmp, "src_srgb.png")).resize((64, 64)).save(plain)
check("H.plain_save_drops_srgb(-control)", "srgb" not in Image.open(plain).info)
check("H.real_basecolor_has_no_colour_chunks(info)", not any(k in Image.open(
    T["DERIVED"] + "GraniteMillstone/Export/T_GraniteMillstone_N.png").info for k in ("srgb", "gamma", "icc_profile")))
ok, msg = refuses(lambda: T["prep_texture"](os.path.join(tmp, "src_none.png"), os.path.join(tmp, "out", "x.png"), 64)
                  if False else T["png_ihdr"](os.path.join(HERE, "s3_props_args.json")), "NOT_PNG")
check("H.ihdr_rejects_non_png(-)", ok, msg)

# ================================================================== I. PearlClam (7 Oct evening)
import math  # noqa: E402

G = T["plan_clam"].__globals__          # the tool's live module globals (T is a copy)
man = json.load(open(T["CLAM_MANIFEST"], encoding="utf-8"))
CP = T["CLAM_PARTS"]

# I1. table == manifest; table == FBX vertices (the exact import input)
check("I1.table_matches_manifest(+)", T["clam_manifest_problems"](man) == [], T["clam_manifest_problems"](man))
bad_man = copy.deepcopy(man)
bad_man["parts"]["SM_PearlClam_Lid"]["bounds_cm_relative_to_pivot"]["min_cm"][1] = -90.0
check("I1.manifest_drift_detected(-)", any("BOUNDS|Lid" in x for x in T["clam_manifest_problems"](bad_man)))
bad_man = copy.deepcopy(man)
bad_man["parts"]["SM_PearlClam_Mantle"].pop("breathing")
check("I1.mantle_vc_flag_drift_detected(-)", any("VC_FLAG|Mantle" in x for x in T["clam_manifest_problems"](bad_man)))
import numpy as np  # noqa: E402
fbx_rows = {}
for part in T["CLAM_PART_ORDER"]:
    path = T["CLAM_DIR"] + "SM_PearlClam_%s.fbx" % part
    fb = M["parse"](path)
    geos = [g for g in fb["geometries"] if "vertices" in g]
    v = geos[0]["vertices"] * 100.0
    rot = fb["models"][0].get("Lcl Rotation")
    fbx_rows[part] = {"min": v.min(0).tolist(), "max": v.max(0).tolist(), "centroid": v.mean(0).tolist(), "n": len(v),
                      "unit": fb["global"].get("UnitScaleFactor"), "rot": rot}
    check("I1.fbx_one_geometry_z_up_cm|" + part, len(geos) == 1 and fb["global"].get("UnitScaleFactor") == 100.0 and
          abs(rot[0] + 90.0) < 0.01, (len(geos), fb["global"], rot))
    check("I1.fbx_bounds_match_table|" + part, T["near"](fbx_rows[part]["min"], CP[part]["min_b"], 0.01) and
          T["near"](fbx_rows[part]["max"], CP[part]["max_b"], 0.01), (fbx_rows[part]["min"], fbx_rows[part]["max"]))
    check("I1.fbx_centroid_match_table|" + part, T["near"](fbx_rows[part]["centroid"], CP[part]["centroid_b"], 0.01),
          fbx_rows[part]["centroid"])
# vertex colours present on the mantle only (raw FBX LayerElementColor)
_nodes = M["_nodes"]


def fbx_has_colors(path):
    buf = memoryview(open(path, "rb").read())
    wide = struct.unpack_from("<I", buf, 23)[0] >= 7500
    found = []

    def walk(a, b, names):
        for n, p, (x, y) in _nodes(buf, a, b, wide):
            if n == "Colors" and names and names[-1] == "LayerElementColor":
                c = np.asarray(p[0]).reshape(-1, 4)
                found.append([float(c[:, 0].min()), float(c[:, 0].max()), float(c[:, 1].max())])
            if n in ("Objects", "Geometry", "LayerElementColor"):
                walk(x, y, names + [n])
    walk(27, len(buf), [])
    return found


for part in T["CLAM_PART_ORDER"]:
    cols = fbx_has_colors(T["CLAM_DIR"] + "SM_PearlClam_%s.fbx" % part)
    if CP[part]["vc"]:
        check("I1.fbx_vertex_colours_BreathMask_R|" + part, bool(cols) and cols[0][0] == 0.0 and cols[0][1] > 0.99 and
              cols[0][2] == 0.0, cols)
    else:
        check("I1.fbx_colours_%s_imported_IGNORE|%s" % ("LipGrad_present(info)" if cols else "absent", part),
              T["clam_vc_option"](part) == "IVCIO_IGNORE", cols)
fp = man["measured"]["bottom_footprint"]
vb = M["parse"](T["CLAM_DIR"] + "SM_PearlClam_Bottom.fbx")["geometries"][0]["vertices"] * 100.0
low = vb[vb[:, 2] <= 3.0]
check("I1.footprint_matches_fbx", T["near"]([np.ptp(low[:, 0]), np.ptp(low[:, 1])], fp["lowest3cm_span_cm"], 0.06) and
      T["near"](((low.max(0) + low.min(0)) / 2)[:2], fp["lowest3cm_centre_cm"], 0.06),
      ([np.ptp(low[:, 0]), np.ptp(low[:, 1])], ((low.max(0) + low.min(0)) / 2)[:2]))

# I2. textures: one source per role, IHDR dims == table
for s, roles in T["CLAM_TEX"].items():
    for role in roles:
        t = T["tex_target"]("PearlClam", s, role)
        r = T["tex_source_gate"](t)
        check("I2.tex_source_ok|%s_%s" % (s, role), r["w"] == r["h"] == roles[role], r)
t = T["tex_target"]("PearlClam", "Shell", "BaseColor")
check("I2.shell_basecolor_is_8192_and_not_the_white_original", t["dim"] == 8192 and t["file"].endswith(
    "T_PearlClam_Shell_BaseColor.png"), t)
tt = dict(t, dim=4096)
ok, msg = refuses(lambda: T["tex_source_gate"](tt), "TEX_DIM")
check("I2.wrong_dim_refused(-)", ok, msg)

# I3. Y-flip bounds gate + centroid handedness gate
for part in T["CLAM_PART_ORDER"]:
    e = T["clam_expected_ue"](part)
    good = {"min": e["min"], "max": e["max"]}
    check("I3.flipped_bounds_pass(+)|" + part, T["clam_bounds_check"](part, good) == [], T["clam_bounds_check"](part, good))
    j = {"min": [x - 0.1 for x in e["min"]], "max": [x + 0.1 for x in e["max"]]}
    check("I3.jitter_1mm_pass(+)|" + part, T["clam_bounds_check"](part, j) == [])
    big = {k: [x * 100 for x in good[k]] for k in good}
    f = T["clam_bounds_check"](part, big)
    check("I3.100x_refused(-)|" + part, f and f[0].startswith("SCALE_100X"), f[:1])
    u = T["clam_expected_ue"](part, flipped=False)
    f = T["clam_bounds_check"](part, {"min": u["min"], "max": u["max"]})
    if part == "Lid":
        check("I3.lid_unflipped_refused_Y_NOT_FLIPPED(-)", f and f[0].startswith("Y_NOT_FLIPPED"), f[:1])
    else:
        check("I3.unflipped_UNDETECTABLE_by_bounds(known: near-symmetric in Y)|" + part, f == [], f[:1])
    check("I3.centroid_pass(+)|" + part, T["clam_centroid_check"](part, e["centroid"]) == [])
    disc = T["centroid_discriminates"](part)
    mx = T["clam_expected_ue"](part, mirror_x=True)["centroid"]
    f = T["clam_centroid_check"](part, mx)
    check("I3.x_mirror_%s|%s" % ("refused_X_MIRRORED(-)" if disc["x"] else "UNDETECTABLE(symmetric)", part),
          (bool(f) and f[0].startswith("X_MIRRORED")) if disc["x"] else f == [], (disc, f[:1]))
    uy = u["centroid"]
    f = T["clam_centroid_check"](part, uy)
    check("I3.centroid_y_unflipped_%s|%s" % ("refused(-)" if disc["y"] else "UNDETECTABLE", part),
          bool(f) if disc["y"] else f == [], (disc, f[:1]))
check("I3.x_handedness_discriminated_by_bottom_lid_mantle",
      all(T["centroid_discriminates"](p)["x"] for p in ("Bottom", "Lid", "Mantle")))

# I4. relative transforms, lid pivot on the hinge, assembly
rel = T["clam_rel_transforms"](man)
check("I4.rel_lid_is_manifest_hinge_flipped", T["near"](rel["Lid"]["location"], [0.0, -47.86, 30.02], 1e-9), rel["Lid"])
check("I4.rel_pearl", T["near"](rel["Pearl"]["location"], [0.0, 0.0, 35.64], 1e-9) and
      T["near"](rel["Mantle"]["location"], [0, 0, 0], 1e-9) and all(r["rotation"] == [0, 0, 0] for r in rel.values()))
boxes = {p: {k: T["clam_expected_ue"](p)[k] for k in ("min", "max")} for p in CP}
check("I4.assembly_clean(+)", T["assembly_problems"](boxes, rel) == [], T["assembly_problems"](boxes, rel))
r_bad = copy.deepcopy(rel)
r_bad["Lid"]["location"][1] = 47.86                       # unflipped hinge: the lid hangs out in front
check("I4.unflipped_hinge_refused(-)", any(x.startswith("HINGE") for x in T["assembly_problems"](boxes, r_bad)),
      T["assembly_problems"](boxes, r_bad))
r_bad = copy.deepcopy(rel)
r_bad["Lid"]["location"][1] -= 1.5                        # pivot 1.5 cm off the hinge
check("I4.hinge_1.5cm_off_refused(-)", any(x.startswith("HINGE_BACK_EDGE") for x in T["assembly_problems"](boxes, r_bad)),
      T["assembly_problems"](boxes, r_bad))
r_bad = copy.deepcopy(rel)
r_bad["Lid"]["location"][1] -= 0.8                        # 0.8 cm: inside the 1 cm hinge gate
check("I4.hinge_0.8cm_off_passes(+, gate is 1 cm)", T["assembly_problems"](boxes, r_bad) == [])
r_bad = copy.deepcopy(rel)
r_bad["Pearl"]["location"][2] = 60.0
check("I4.pearl_above_mantle_refused(-)", any("PEARL" in x for x in T["assembly_problems"](boxes, r_bad)))
lid_unflipped = {k: T["clam_expected_ue"]("Lid", flipped=False)[k] for k in ("min", "max")}
check("I4.front_sign", T["lid_front_sign"](boxes["Lid"]) == 1 and T["lid_front_sign"](lid_unflipped) == -1)

# I5. opening sign: lid tip rises for the derived roll at any yaw; the opposite sign drops it (- control)
roll = T["lid_open_roll"](1, 80.0)
check("I5.open_roll_is_minus80", roll == -80.0, roll)
for yaw in (0.0, 37.0, 180.0, -110.0):
    root_tf = {"location": [14421.79, 159999.34, 121.97], "rotation": [0.0, 0.0, yaw], "scale": [1, 1, 1]}
    zc, zo = T["lid_tip_rise"](boxes["Lid"], rel["Lid"], root_tf, roll)
    check("I5.open_lifts_front(+)|yaw=%g" % yaw, zo - zc > 70.0, (zc, zo))
    zc2, zo2 = T["lid_tip_rise"](boxes["Lid"], rel["Lid"], root_tf, -roll)
    check("I5.wrong_sign_drops_front(-)|yaw=%g" % yaw, zo2 < zc2 - 50.0, (zc2, zo2))
# rot_matrix row Y for pure roll (the derivation the sign rests on)
m = T["rot_matrix"]([30.0, 0.0, 0.0])
check("I5.roll_maps_Y_to_(0,cos,-sin)", T["near"](m[1], [0.0, math.cos(math.radians(30)), -math.sin(math.radians(30))], 1e-12),
      m[1])
zc, zo = T["lid_tip_rise"](lid_unflipped, {"location": [0, 47.86, 30.02]}, {"location": [0, 0, 0], "rotation": [0, 0, 0],
                                                                             "scale": [1, 1, 1]},
                           T["lid_open_roll"](T["lid_front_sign"](lid_unflipped), 80.0))
check("I5.sign_follows_front_if_import_unflipped(+)", zo - zc > 70.0, (zc, zo))

# I6. cameras -> yaw (hinge away), footprint on the axis, seat
stone_xy = [14421.792356918335, 159999.3436307907]
# offline read of today's LS_DevScene_03 (S3Diag/ds03_now_sem.json): B06 = "Cine Camera Actor 4" keyed (14072.6,160990.6)
# -> (14866.2,160994.0); B05 = "Cine Camera Actor 3" (template not readable offline) -> 1 Oct shotlist pose used here.
b05 = [14121.973, 160000.0]
b06 = [[14072.59, 160990.62], [14866.15, 160994.03]]
yaw, chk = T["yaw_from_cameras"](stone_xy, [b05], 70.0)
fd = T["front_dir"](yaw)
v = [b05[0] - stone_xy[0], b05[1] - stone_xy[1]]
check("I6.single_camera_front_faces_it(+)", (fd[0] * v[0] + fd[1] * v[1]) / math.hypot(*v) > 0.999, (yaw, fd))
check("I6.hinge_away_from_camera(+)", (-fd[0] * v[0] - fd[1] * v[1]) < 0)
yaw_all, chk_all = T["yaw_from_cameras"](stone_xy, [b05] + b06, 70.0)
check("I6.b05_plus_moving_b06_within_70(info: offline poses)", max(chk_all["off_front_deg"]) <= 70.0,
      (round(yaw_all, 2), [round(x, 1) for x in chk_all["off_front_deg"]]))
ok, msg = refuses(lambda: T["yaw_from_cameras"](stone_xy, [b05] + b06, 45.0), "CAMERA_SPREAD")
check("I6.same_poses_spread_refused_at_45(-)", ok, msg)
yaw2, chk2 = T["yaw_from_cameras"](stone_xy, b06, 70.0)
check("I6.b06_only_yaw", all(o <= 70.0 for o in chk2["off_front_deg"]), (yaw2, chk2))
ok, msg = refuses(lambda: T["yaw_from_cameras"](stone_xy, [[stone_xy[0] + 1000, stone_xy[1]], [stone_xy[0] - 1000, stone_xy[1]]],
                                                 180.0), "CAMERA_BEARINGS_CANCEL")
check("I6.opposed_cameras_refused(-)", ok, msg)
ok, msg = refuses(lambda: T["yaw_from_cameras"](stone_xy, [], 70.0), "NO_CAMERA_SAMPLES")
check("I6.no_samples_refused(-)", ok, msg)
meas = json.load(open(os.path.join(HERE, "s3_millstone_fbx_measure.json"), encoding="utf-8"))
seat, seat_r = T["seat_offset_from_measure"](meas, fp["lowest3cm_span_cm"])
check("I6.seat_is_highest_point_under_footprint", abs(seat - 128.970) < 0.01 and abs(seat_r - 32.38) < 0.05, (seat, seat_r))
for yaw in (0.0, 90.0, -137.5):
    rl = T["clam_root_location"]([stone_xy[0], stone_xy[1], -7.0], yaw, [-0.4, 3.4, 0.0], seat, 0.0)
    fw = T["tf_point"]({"location": rl, "rotation": [0, 0, yaw], "scale": [1, 1, 1]}, [-0.4, 3.4, 0.0])
    check("I6.footprint_on_stone_axis(+)|yaw=%g" % yaw, T["near"](fw[:2], stone_xy, 1e-6) and abs(rl[2] - (seat - 7.0)) < 1e-9,
          (rl, fw))


# I7. plan_clam end to end on a synthetic state (stone = today's apply record)
mill_rec = json.load(open(os.path.join(HERE, "s3_millstone_apply_record.json"), encoding="utf-8"))
REVEAL_SEC = mill_rec["plan"]["reveal"]["section"]


def clam_state():
    lab = {v: 0 for v in T["CLAM_LABELS"].values()}
    assets = {T["clam_mesh_path"](p): True for p in CP}
    assets.update({T["clam_mi_path"](k): True for k in T["CLAM_MATERIALS"]})
    stand = []
    for label, cls, comps in (("source_Anim", "SkeletalMeshActor", ["SkeletalMeshComponent0"]),
                              ("Clam_with_Pearl_Clam_with_Pearl_0", "StaticMeshActor", ["StaticMeshComponent0"])):
        stand.append({"label": label, "count": 1, "class": cls, "object_path": "PersistentLevel." + label,
                      "flags": {"actor_hidden": True, "components": {c: {"visible": True, "hidden_in_game": False}
                                                                     for c in comps}}})
    return {"root": {"world": {"location": list(T["ROOT_LANDED_WORLD"]), "rotation": [0, 0, 0], "scale": [1, 1, 1]}},
            "temp_actors": [], "label_count": lab, "assets": assets, "meshes": {},
            "stone": {"label": "S3 Granite Millstone", "object_path": mill_rec["actor_path"], "found": True,
                      "location": list(mill_rec["plan"]["location"]), "record_location": list(mill_rec["plan"]["location"]),
                      "rotation": [0.0, 0.0, 0.0],
                      "reveal_binding": {"guid": mill_rec["reveal_binding_guid"], "resolved": [mill_rec["actor_path"]],
                                         "visibility_sections": [REVEAL_SEC]}},
            "standins": stand,
            "cameras": {"ok": True, "rows": [{"beat": "B05", "samples": [{"location": b05 + [140.0]}]}]},
            "measure": meas}


cs = clam_state()
pl = T["plan_clam"](cs, {}, man)
check("I7.plan_ok_yaw_from_cameras", pl["yaw_source"] == "cameras" and abs(pl["yaw"] - 90.0) < 0.2, (pl["yaw"], pl["yaw_source"]))
check("I7.footprint_world_on_axis", T["near"](pl["footprint_world"][:2], stone_xy, 0.01), pl["footprint_world"])
check("I7.root_z_on_stone_top", abs(pl["root_location"][2] - (-7.0 + seat)) < 1e-9, pl["root_location"])
check("I7.lid_not_keyed_open_roll_exposed", pl["lid"]["keyed"] is False and pl["lid"]["open_relative_rotation_rpy"] == [-80.0, 0, 0])
check("I7.children_rel_and_parent", all(pl["parts"][p]["parent"] == "Bottom" and pl["parts"][p]["rel"] == rel[p]
                                        for p in ("Lid", "Mantle", "Pearl")) and pl["parts"]["Bottom"]["parent"] is None)
for p in ("Lid", "Mantle", "Pearl"):
    want = T["tf_point"]({"location": pl["root_location"], "rotation": [0, 0, pl["yaw"]], "scale": [1, 1, 1]}, rel[p]["location"])
    check("I7.child_world_eq_root_times_rel|" + p, T["near"](pl["parts"][p]["world_location"], want, 1e-9))
check("I7.slot_materials", pl["parts"]["Bottom"]["mis"] == {0: T["clam_mi_path"]("Shell"), 1: T["clam_mi_path"]("InteriorBottom")} and
      pl["parts"]["Lid"]["mis"] == {0: T["clam_mi_path"]("Shell"), 1: T["clam_mi_path"]("InteriorLid")} and
      pl["parts"]["Mantle"]["mis"] == {0: T["clam_mi_path"]("Mantle")} and pl["parts"]["Pearl"]["mis"] == {0: T["clam_mi_path"]("Pearl")})
check("I7.reveal_all_four_hidden", pl["reveal"]["targets"] == list(T["CLAM_PART_ORDER"]) and
      all(pl["parts"][p]["actor_hidden_in_game"] for p in CP) and pl["reveal"]["section"] == REVEAL_SEC)
check("I7.standins_hidden_component_level", all(r["after"]["actor_hidden"] == r["before"]["actor_hidden"] and
                                                all(not c["visible"] and c["hidden_in_game"] for c in r["after"]["components"].values())
                                                for r in pl["standins"]["rows"]))
pl_y = T["plan_clam"](clam_state(), {"yaw_deg": 12.5}, man)
check("I7.explicit_yaw_wins_and_reports_camera_angle", pl_y["yaw_source"] == "args" and pl_y["yaw"] == 12.5 and
      pl_y["camera_check"] and abs(pl_y["camera_check"][0] - 77.5) < 0.2, pl_y["camera_check"])
pl_r = T["plan_clam"](clam_state(), {"reveal_range_s": [0.0, 40.0]}, man)
check("I7.reveal_range_override(+)", pl_r["reveal"]["section"]["range_s"] == [0.0, 40.0] and pl_r["reveal"]["overrides"])
pl_root = T["plan_clam"](clam_state(), {"reveal_targets": "root"}, man)
check("I7.reveal_root_only_warns", pl_root["reveal"].get("warning") and not pl_root["parts"]["Lid"]["actor_hidden_in_game"])


def cmut(fn):
    s = clam_state()
    fn(s)
    return s


cneg = [
    ("cameras_unreadable_no_yaw", lambda s: s.update(cameras={"ok": False, "error": "NO_CUT_AT_BEAT"}), {}, "YAW_UNRESOLVED"),
    ("label_exists", lambda s: s["label_count"].update({"S3 PearlClam Lid": 1}), {}, "LABEL_EXISTS"),
    ("asset_missing", lambda s: s["assets"].update({T["clam_mi_path"]("Pearl"): False}), {}, "ASSETS_MISSING"),
    ("stone_moved", lambda s: s["stone"].update(location=[stone_xy[0] + 3, stone_xy[1], -7.0]), {}, "STONE_MOVED"),
    ("stone_missing", lambda s: s["stone"].update(found=False), {}, "STONE_MISSING"),
    ("root_not_landed", lambda s: s["root"]["world"].update(location=[11421.97, 160000.0, -3620.0]), {}, "ROOT_NOT_LANDED"),
    ("standin_missing", lambda s: s["standins"].pop(), {}, "STANDIN_MISSING"),
    ("reveal_source_gone", lambda s: s["stone"].update(reveal_binding=None), {}, "STONE_REVEAL_BINDING"),
    ("live_mesh_unflipped", lambda s: s["meshes"].update(Lid={"bounds": lid_unflipped, "slots": CP["Lid"]["slots"]}), {},
     "MESH_BOUNDS_DRIFT"),
    ("live_slots_swapped", lambda s: s["meshes"].update(Bottom={"bounds": boxes["Bottom"], "slots": CP["Bottom"]["slots"][::-1]}),
     {}, "MESH_SLOTS"),
    ("reveal_range_cuts_keys", lambda s: None, {"reveal_range_s": [0.0, 3.0]}, "REVEAL_RANGE_CUTS_KEYS"),
    ("outside_guard", lambda s: s["stone"].update(location=[11421.97 + 6100, 160000.0, -7.0],
                                                  record_location=[11421.97 + 6100, 160000.0, -7.0]), {}, "GUARD_LOCAL_BOX"),
]
for nm, fn, args_c, needle in cneg:
    ok, msg = refuses(lambda fn=fn, args_c=args_c: T["plan_clam"](cmut(fn), args_c, man), needle)
    check("I7.refuse_%s(-)" % nm, ok, msg)
check("I7.explicit_yaw_rescues_unreadable_cameras(+)", T["plan_clam"](cmut(lambda s: s.update(
    cameras={"ok": False, "error": "x"})), {"yaw_deg": 90.0}, man)["yaw"] == 90.0)

# I8. ops round trip: CLAM_APPLY -> CLAM_REVERT restores the world exactly
pl = T["plan_clam"](clam_state(), {}, man)
w0 = {r["object_path"]: {"label": r["label"], "flags": r["before"]} for r in pl["standins"]["rows"]}
w0["__bindings__"] = {mill_rec["reveal_binding_guid"]: mill_rec["actor_path"]}
w1 = T["clam_simulate"](w0, T["clam_apply_ops"](pl))
paths = {p: "PersistentLevel.NEW_" + pl["parts"][p]["label"] for p in CP}
rec = {"plan": json.loads(json.dumps(pl)), "actor_paths": paths, "reveal_binding_guids": {p: "GUID_" + p for p in CP}}
check("I8.apply_effects", all(paths[p] in w1 for p in CP) and all(w1[paths[p]]["parent"] == paths["Bottom"]
                                                                   for p in ("Lid", "Mantle", "Pearl")) and
      all(w1["__bindings__"].get("GUID_" + p) == paths[p] for p in CP) and
      all(w1[r["object_path"]]["flags"] == r["after"] for r in pl["standins"]["rows"]))
w2 = T["clam_simulate"](w1, T["clam_revert_ops"](rec))
check("I8.revert_exact(+)", w2 == w0, json.dumps(w2)[:300])
bad = copy.deepcopy(rec)
first = list(bad["plan"]["standins"]["rows"][0]["before"]["components"])[0]
bad["plan"]["standins"]["rows"][0]["before"]["components"][first]["hidden_in_game"] = True
check("I8.tampered_record_detected(-)", T["clam_simulate"](w1, T["clam_revert_ops"](bad)) != w0)
bad = copy.deepcopy(rec)
bad["actor_paths"]["Pearl"] = "PersistentLevel.SomeoneElse"
ok, msg = refuses(lambda: T["clam_simulate"](w1, T["clam_revert_ops"](bad)), "SIM_BINDING_MISMATCH")
check("I8.revert_refuses_foreign_binding(-)", ok, msg)
order = [o["part"] for o in T["clam_revert_ops"](rec) if o["op"] == "destroy"]
check("I8.root_destroyed_last", order[-1] == "Bottom", order)
ops_rev = T["clam_revert_ops"](rec)
ops_bad = [o for o in ops_rev if o["op"] != "destroy"] + sorted([o for o in ops_rev if o["op"] == "destroy"],
                                                                 key=lambda o: o["part"] != "Bottom")
ok, msg = refuses(lambda: T["clam_simulate"](w1, ops_bad), "SIM_DESTROY_HAS_CHILDREN")
check("I8.root_first_destroy_refused(-)", ok, msg)
check("I8.no_lid_keys_in_ops", not [o for o in T["clam_apply_ops"](pl) if o["op"] not in ("spawn", "add_reveal", "set_prim_flags")])

# I9. one-per-call imports, the VERIFY_TEX split, mode gates
CM = T["check_mode"]
ok, msg = refuses(lambda: CM({"mode": "IMPORT_TEX", "confirm": "IMPORT_TEX S3PROPS", "prop": "PearlClam", "tex_set": "Shell",
                              "textures": ["N", "Roughness"]}, True, False), "ONE_TEXTURE_PER_CALL")
check("I9.two_textures_refused(-)", ok, msg)
ok, msg = refuses(lambda: CM({"mode": "IMPORT_TEX", "confirm": "IMPORT_TEX S3PROPS", "prop": "GraniteMillstone",
                              "textures": None}, True, False), "ONE_TEXTURE_PER_CALL")
check("I9.all_textures_default_refused(-)", ok, msg)
check("I9.one_texture_ok(+)", CM({"mode": "IMPORT_TEX", "confirm": "IMPORT_TEX S3PROPS", "prop": "PearlClam", "tex_set": "Shell",
                                  "textures": ["BaseColor"]}, True, False) == "IMPORT_TEX")
ok, msg = refuses(lambda: CM({"mode": "IMPORT_MESH", "confirm": "IMPORT_MESH S3PROPS", "prop": "PearlClam"}, True, False),
                  "CLAM_PART")
check("I9.clam_mesh_needs_one_part(-)", ok, msg)
ok, msg = refuses(lambda: CM({"mode": "VERIFY_TEX", "confirm": "VERIFY_TEX S3PROPS"}, True, False, False), "NO_TEX_PENDING")
check("I9.verify_without_pending_refused(-)", ok, msg)
for md in ("IMPORT_MESH", "IMPORT_TEX", "BUILD_MAT", "CLAM_APPLY"):
    ok, msg = refuses(lambda md=md: CM({"mode": md, "confirm": "%s S3PROPS" % md, "prop": "PearlClam", "part": "Lid",
                                        "tex_set": "Shell", "textures": ["N"], "material": "Shell"}, True, False, True),
                      "TEX_PENDING")
    check("I9.%s_refused_while_pending(-)" % md, ok, msg)
check("I9.dry_allowed_while_pending(+)", CM({"mode": "CLAM_DRY"}, True, False, True) == "CLAM_DRY")
PA = "/Game/X/T_PearlClam_Shell_N"
check("I9.verify_census_exact(+)", T["gate_census"]({"content": [PA], "maps": []}, "VERIFY_TEX", PA) is False)
for nm, cen in (("extra_pkg", {"content": [PA, "/Game/Y"], "maps": []}), ("map_dirty", {"content": [PA], "maps": ["/Game/M"]}),
                ("clean", {"content": [], "maps": []})):
    ok, msg = refuses(lambda cen=cen: T["gate_census"](cen, "VERIFY_TEX", PA), "VERIFY_CENSUS")
    check("I9.verify_census_refuses_%s(-)" % nm, ok, msg)
ok, msg = refuses(lambda: CM({"mode": "CLAM_APPLY", "confirm": "CLAM_APPLY S3PROPS"}, False, False), "NO_STONE")
check("I9.clam_apply_needs_stone(-)", ok, msg)
ok, msg = refuses(lambda: CM({"mode": "CLAM_APPLY", "confirm": "CLAM_APPLY S3PROPS"}, True, False, False, True),
                  "CLAM_ALREADY_APPLIED")
check("I9.clam_apply_twice_refused(-)", ok, msg)
ok, msg = refuses(lambda: CM({"mode": "CLAM_REVERT", "confirm": "CLAM_REVERT S3PROPS"}, True, False), "NO_CLAM_RECORD")
check("I9.clam_revert_without_record_refused(-)", ok, msg)


# I9b. the split itself, against a fake editor: IMPORT_TEX never saves and never gates the size; VERIFY_TEX gates
#      the size (32x32 refused, nothing saved) and saves once it reads the real size.
class _Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeUnreal:
    def __init__(self, tmp):
        self.assets, self.dirty, self.saved, self.size_ready = set(), set(), [], False
        fu = self

        class Tex:
            def __init__(self, path):
                self.path, self.props = path, {"compression_settings": "TC_DEFAULT", "srgb": True, "flip_green_channel": False}

            def modify(self):
                fu.dirty.add(self.path)

            def set_editor_property(self, k, v):
                self.props[k] = v

            def get_editor_property(self, k):
                return self.props[k]

            def blueprint_get_size_x(self):
                return T["CLAM_TEX"]["Shell"]["N"] if fu.size_ready else 32

            blueprint_get_size_y = blueprint_get_size_x

        self.Texture2D = Tex
        self._tex = {}

        class Task:
            def __init__(self):
                self.p = {}

            def set_editor_property(self, k, v):
                self.p[k] = v

        self.AssetImportTask = Task

        def import_tasks(tasks):
            for t in tasks:
                path = t.p["destination_path"] + "/" + t.p["destination_name"]
                fu.assets.add(path)
                fu.dirty.add(path)
                fu._tex[path] = Tex(path)
        self.AssetToolsHelpers = _Obj(get_asset_tools=lambda: _Obj(import_asset_tasks=import_tasks))
        self.EditorAssetLibrary = _Obj(
            does_asset_exist=lambda p: p in fu.assets, does_directory_exist=lambda f: True,
            list_assets=lambda f, recursive=True: [a + "." + a.rsplit("/", 1)[1] for a in fu.assets if a.startswith(f)],
            save_asset=lambda p, only_if_is_dirty=False: (fu.saved.append(p), fu.dirty.discard(p), True)[2])
        self.load_asset = lambda p: fu._tex.get(p)
        self.TextureCompressionSettings = _Obj(TC_DEFAULT="TC_DEFAULT", TC_NORMALMAP="TC_NORMALMAP", TC_MASKS="TC_MASKS")
        pk = lambda n: _Obj(get_name=lambda: n)  # noqa: E731
        self.EditorLoadingAndSavingUtils = _Obj(get_dirty_content_packages=lambda: [pk(n) for n in sorted(fu.dirty)],
                                                get_dirty_map_packages=lambda: [])
        self.SystemLibrary = _Obj(collect_garbage=lambda: None)


tmp2 = tempfile.mkdtemp(prefix="s3clam_")
saved_g = {k: G[k] for k in ("unreal", "TEX_PENDING", "HERE")}
fake = FakeUnreal(tmp2)
G.update(unreal=fake, TEX_PENDING=os.path.join(tmp2, "pending.json"), HERE=tmp2 + "/")
try:
    args_t = {"prop": "PearlClam", "tex_set": "Shell", "textures": ["N"]}
    pend = T["run_import_tex"]("RUN1", args_t)
    asset = T["tex_target"]("PearlClam", "Shell", "N")["asset"]
    check("I9b.import_tex_no_save_pending_written(+)", fake.saved == [] and os.path.exists(G["TEX_PENDING"]) and
          pend["saved"] is False and fake.dirty == {asset} and pend["import"]["size_at_import_call"] == [32, 32],
          (fake.saved, pend["import"]))
    check("I9b.import_records_source_sha256", len(pend["source"]["sha256"]) == 64)
    ok, msg = refuses(lambda: T["run_verify_tex"]("RUN2", pend), "TEX_SIZE")
    check("I9b.verify_refuses_32x32_and_saves_nothing(-)", ok and fake.saved == [] and os.path.exists(G["TEX_PENDING"]), msg)
    fake.size_ready = True
    r = T["run_verify_tex"]("RUN3", pend)
    check("I9b.verify_saves_after_real_size(+)", fake.saved == [asset] and r["verified"]["size"] == [4096, 4096] and
          not os.path.exists(G["TEX_PENDING"]) and os.path.exists(G["HERE"] + "s3_props_import_tex_PearlClam_Shell_N.json"))
    ok, msg = refuses(lambda: T["run_import_tex"]("RUN4", args_t), "TEX_EXISTS")
    check("I9b.reimport_refused(-)", ok, msg)
finally:
    G.update(saved_g)

# I10. materials
mp = T["material_problems"]()
check("I10.all_material_specs_clean(+)", mp == {}, mp)
specs = T["material_specs"]()
bad = copy.deepcopy(specs)
bad[T["MASTER_BREATHE"]]["edges"] = [e for e in bad[T["MASTER_BREATHE"]]["edges"] if e[3] != "M"]
check("I10.breath_mask_unfed_detected(-)", any("CUSTOM_PIN_UNFED|BreathWPO.M" in x
                                               for x in T["material_problems"](bad).get(T["MASTER_BREATHE"], [])))
bad = copy.deepcopy(specs)
bad[T["PEARL_MASTER"]]["nodes"]["Orphan"] = ("scalar", 1.0)
bad[T["PEARL_MASTER"]]["scalars"]["Orphan"] = 1.0
check("I10.pearl_orphan_detected(-)", any("UNUSED_NODE|Orphan" in x for x in T["material_problems"](bad).get(T["PEARL_MASTER"], [])))
bad = copy.deepcopy(specs)
bad[T["MASTER"]]["props"].append(("RoughCalc", "", "MP_ROUGHNESS"))
check("I10.prop_set_twice_detected(-)", any("PROP_SET_TWICE" in x for x in T["material_problems"](bad).get(T["MASTER"], [])))
check("I10.no_clearcoat_pins", not any(p[2].startswith("MP_CUSTOM") or "CLEAR" in p[2] for s in specs.values() for p in s["props"]))
check("I10.m_s3prop_spec_unchanged", specs[T["MASTER"]]["props"] == T["graph_spec"]()[2] and specs[T["MASTER"]]["max_wpo"] is None)
be = T["breath_eval"]
check("I10.breath_zero_at_t0_amp_at_half_period", be(1.0, 1.0, 0.0, 5.0) == 0.0 and abs(be(1.0, 1.0, 2.5, 5.0) - 1.0) < 1e-12 and
      abs(be(1.0, 1.0, 5.0, 5.0)) < 1e-12)
check("I10.breath_masked_by_R", be(1.0, 0.0, 2.5, 5.0) == 0.0 and abs(be(1.0, 0.5, 2.5, 5.0) - 0.5) < 1e-12)
check("I10.breath_off_by_default", T["CLAM_MATERIALS"]["Mantle"]["scalars"]["BreathAmp"] == 0.0 and
      T["CLAM_MATERIALS"]["Pearl"]["scalars"]["BreathAmp"] == 0.0 and specs[T["MASTER_BREATHE"]]["scalars"]["BreathAmp"] == 0.0)
check("I10.max_wpo_covers_1cm_amp", specs[T["MASTER_BREATHE"]]["max_wpo"] >= 1.0 and specs[T["PEARL_MASTER"]]["max_wpo"] >= 1.0)
pv = specs[T["PEARL_MASTER"]]["vectors"]
c0 = T["pearl_color_eval"](pv["BaseColor"], pv["WarmTint"], pv["CoolTint"], 0.0, 1.0)
c1 = T["pearl_color_eval"](pv["BaseColor"], pv["WarmTint"], pv["CoolTint"], 1.0, 1.0)
check("I10.pearl_facing_warm_grazing_cool", c0[0] > c0[2] and c1[2] > c1[0] and
      T["pearl_color_eval"](pv["BaseColor"], pv["WarmTint"], pv["CoolTint"], 0.7, 0.0) == pv["BaseColor"][:3], (c0, c1))
check("I10.pearl_defaults", pv["BaseColor"][:3] == [0.86, 0.83, 0.78] and specs[T["PEARL_MASTER"]]["scalars"]["Roughness"] == 0.18
      and specs[T["PEARL_MASTER"]]["scalars"]["Specular"] == 0.55 and specs[T["PEARL_MASTER"]]["scalars"]["Glow"] == 0.0)
for k in ("InteriorBottom", "InteriorLid"):
    m = T["CLAM_MATERIALS"][k]
    check("I10.v2_interior_on_textured_master_roughness_from_map|" + k, m["master"] == T["MASTER"] and m["tex_set"] == k and
          T["rough_eval"](0.20, m["scalars"]["RoughnessMultiplier"], m["scalars"]["RoughnessOverride"]) == 0.20 and
          T["rough_eval"](0.40, m["scalars"]["RoughnessMultiplier"], m["scalars"]["RoughnessOverride"]) == 0.40)
check("I10.v2_untextured_interior_retired", "Interior" not in T["CLAM_MATERIALS"] and "MASTER_SOLID" not in T and
      "M_PearlClam_Interior" not in T["SLOT_TO_MATERIAL"])
check("I10.slot_map_covers_all_slots", {s for p in CP.values() for s in p["slots"]} == set(T["SLOT_TO_MATERIAL"]))

# I11. v2 (7 Oct 18:16): slot names per part, normals from the file, 8K allow-list
want_slots = {"Bottom": ["M_PearlClam_Shell", "M_PearlClam_InteriorBottom"], "Lid": ["M_PearlClam_Shell", "M_PearlClam_InteriorLid"],
              "Mantle": ["M_PearlClam_Mantle"], "Pearl": ["M_PearlClam_Pearl"]}
for part, sl in want_slots.items():
    check("I11.slot_table_v2|" + part, CP[part]["slots"] == sl and man["parts"]["SM_PearlClam_" + part]["slots"] == sl, CP[part]["slots"])
    st = clam_state()
    st["meshes"] = {p2: {"bounds": boxes[p2], "slots": want_slots[p2]} for p2 in CP}
    check("I11.live_slots_v2_pass(+)|" + part, T["plan_clam"](st, {}, man)["parts"][part]["slots"] == sl)
    wrongs = ([[x.replace("InteriorBottom", "Interior").replace("InteriorLid", "Interior") for x in sl], sl[::-1]]
              if len(sl) > 1 else [["M_Other"]])
    for wrong in wrongs:
        st = clam_state()
        st["meshes"] = {p2: {"bounds": boxes[p2], "slots": want_slots[p2]} for p2 in CP}
        st["meshes"][part]["slots"] = wrong
        ok, msg = refuses(lambda st=st: T["plan_clam"](st, {}, man), "MESH_SLOTS")
        check("I11.live_slots_wrong_refused(-)|%s|%s" % (part, wrong), ok, msg)
st = clam_state()
st["meshes"] = {p2: {"bounds": boxes[p2], "slots": want_slots[p2]} for p2 in CP}
st["meshes"]["Lid"]["slots"] = list(want_slots["Bottom"])          # bottom's interior on the lid
ok, msg = refuses(lambda: T["plan_clam"](st, {}, man), "MESH_SLOTS")
check("I11.lid_with_bottom_interior_refused(-)", ok, msg)
bad_man = copy.deepcopy(man)
bad_man["parts"]["SM_PearlClam_Lid"]["slots"] = ["M_PearlClam_Shell", "M_PearlClam_Interior"]
check("I11.manifest_v1_slots_refused(-)", any("SLOTS|Lid" in x for x in T["clam_manifest_problems"](bad_man)))
bad_man = copy.deepcopy(man)
bad_man["validation_reexport"]["SM_PearlClam_Bottom"]["custom_normals"] = False
check("I11.manifest_custom_normals_missing_refused(-)",
      any("CUSTOM_NORMALS_UNDECLARED|Bottom" in x for x in T["clam_manifest_problems"](bad_man)))


def fbx_normals_layer(path):
    buf = memoryview(open(path, "rb").read())
    wide = struct.unpack_from("<I", buf, 23)[0] >= 7500
    out = []

    def walk(a, b, names):
        for n, p, (x, y) in _nodes(buf, a, b, wide):
            if names and names[-1] == "LayerElementNormal" and n == "MappingInformationType":
                out.append(p[0].decode())
            if n in ("Objects", "Geometry", "LayerElementNormal"):
                walk(x, y, names + [n])
    walk(27, len(buf), [])
    return out


for part in ("Bottom", "Lid"):
    lay = fbx_normals_layer(T["CLAM_DIR"] + "SM_PearlClam_%s.fbx" % part)
    check("I11.fbx_has_per_corner_normals|" + part, lay == ["ByPolygonVertex"], lay)
for part in T["CLAM_PART_ORDER"]:
    rows = T["pipeline_wanted"](T["clam_vc_option"](part), CP[part]["custom_normals"])
    check("I11.pipeline_plan_clean(+)|" + part, T["pipeline_problems"](rows, part) == [], T["pipeline_problems"](rows, part))
    d = {(r[0], r[1]): r[2] for r in rows}
    if CP[part]["custom_normals"]:
        check("I11.normals_from_file_set|" + part, d[("common", "recompute_normals")] is False and
              d[("common", "use_mikk_t_space")] is True and d[("common", "recompute_tangents")] is True, d)
        bad_rows = [r if r[1] != "recompute_normals" else (r[0], r[1], True) for r in rows]
        check("I11.recompute_normals_on_refused(-)|" + part,
              any("RECOMPUTE_NORMALS_ON" in x for x in T["pipeline_problems"](bad_rows, part)))
        check("I11.normals_gate_pass(+)|" + part, T["normals_gate"](part, {"readable": True, "recompute_normals": False}) == [])
        check("I11.normals_gate_recomputed_refused(-)|" + part,
              bool(T["normals_gate"](part, {"readable": True, "recompute_normals": True})))
        check("I11.normals_gate_unreadable_refused(-)|" + part, bool(T["normals_gate"](part, {"readable": False, "error": "x"})))
        check("I11.normals_gate_unreadable_allowed_by_arg(+)|" + part,
              T["normals_gate"](part, {"readable": False}, allow_unreadable=True) == [])
    vc_bad = [r if r[1] != "vertex_color_import_option" else (r[0], r[1], "IVCIO_IGNORE" if CP[part]["vc"] else "IVCIO_REPLACE")
              for r in rows]
    check("I11.wrong_vc_option_refused(-)|" + part, any("VC_OPTION" in x for x in T["pipeline_problems"](vc_bad, part)))
check("I11.millstone_pipeline_unchanged", T["pipeline_wanted"]() == T["BASE_PIPELINE"] and
      ("common", "recompute_normals", False) in T["BASE_PIPELINE"])
ok, msg = refuses(lambda: T["pipeline_wanted"]("IVCIO_OVERRIDE"), "VC_OPTION")
check("I11.vc_override_refused(-)", ok, msg)
# 8K allow-list
for s_, roles in T["CLAM_TEX"].items():
    for role, dim in roles.items():
        t = T["tex_target"]("PearlClam", s_, role)
        allowed = ("PearlClam", t["label"]) in T["ALLOW_8K"]
        check("I11.dim_vs_allowlist|%s" % t["label"], (dim == 8192) == allowed, (dim, allowed))
for s_ in ("InteriorBottom", "InteriorLid"):
    for role in T["TEX_ROLES"]:
        t = T["tex_target"]("PearlClam", s_, role)
        r = T["tex_source_gate"](t)
        check("I11.v2_interior_tex_ok|%s" % t["label"], r["w"] == T["CLAM_TEX"][s_][role], r)
t = dict(T["tex_target"]("PearlClam", "InteriorBottom", "Roughness"))
t.update(file=T["CLAM_DIR"] + "T_PearlClam_InteriorBottom_N.png", dim=8192)      # an 8K file on a 4K-only role
ok, msg = refuses(lambda: T["tex_source_gate"](t), "TEX_8K_NOT_ALLOWED")
check("I11.8k_on_roughness_refused(-)", ok, msg)
t = dict(T["tex_target"]("PearlClam", "Shell", "N"))
t.update(file=T["CLAM_DIR"] + "T_PearlClam_InteriorLid_N.png", dim=8192)
ok, msg = refuses(lambda: T["tex_source_gate"](t), "TEX_8K_NOT_ALLOWED")
check("I11.8k_on_shell_N_refused(-)", ok, msg)
check("I11.millstone_8k_still_allowed(+)", T["tex_source_gate"](T["tex_target"]("GraniteMillstone", None, "BaseColor"))["w"] == 8192)
check("I11.shell_basecolor_final_on_disk_8192", T["tex_source_gate"](T["tex_target"]("PearlClam", "Shell", "BaseColor"))["w"] == 8192)
check("I11.material_keys", sorted(T["CLAM_MATERIALS"]) == ["InteriorBottom", "InteriorLid", "Mantle", "Pearl", "Shell"])

# ================================================================== J. Pearl v2 (7 Oct late)
V2 = T["PEARL_V2"]
R2 = T["CLAM_EXTRA_PARTS"][V2]
# J1. table == FBX vertices, table == manifest
fb = M["parse"](T["CLAM_DIR"] + "SM_PearlClam_Pearl_v2.fbx")
geos = [g for g in fb["geometries"] if "vertices" in g]
v2v = geos[0]["vertices"] * 100.0
check("J1.fbx_one_geometry_z_up_cm", len(geos) == 1 and fb["global"].get("UnitScaleFactor") == 100.0 and
      abs(fb["models"][0].get("Lcl Rotation")[0] + 90.0) < 0.01, (len(geos), fb["models"][0].get("Lcl Rotation")))
check("J1.fbx_bounds_match_table", T["near"](v2v.min(0).tolist(), R2["min_b"], 0.01) and
      T["near"](v2v.max(0).tolist(), R2["max_b"], 0.01), (v2v.min(0).tolist(), v2v.max(0).tolist()))
check("J1.fbx_centroid_match_table", T["near"](v2v.mean(0).tolist(), R2["centroid_b"], 0.01), v2v.mean(0).tolist())
check("J1.less_spherical_than_v1(info: x 17.87 vs y 18.0)", (R2["max_b"][1] - R2["min_b"][1]) - (R2["max_b"][0] - R2["min_b"][0]) > 0.1)
check("J1.manifest_v2_clean(+)", T["pearl_v2_manifest_problems"](man) == [], T["pearl_v2_manifest_problems"](man))
for nm, fn, needle in (("tris", lambda m: m["parts"]["SM_PearlClam_Pearl_v2"]["validation_blender_clean_reimport"].update(tris=1), "TRIS"),
                       ("rest_z_moved", lambda m: m["parts"]["SM_PearlClam_Pearl_v2"].update(place_at_cm=[0, 0, 36.0]), "REST_Z_MOVED"),
                       ("slots", lambda m: m["parts"]["SM_PearlClam_Pearl_v2"].update(slots=["M_X"]), "SLOTS"),
                       ("size", lambda m: m["parts"]["SM_PearlClam_Pearl_v2"]["validation_blender_clean_reimport"].update(
                           size_cm=[18.0, 18.0, 18.0]), "SIZE"),
                       ("missing", lambda m: m["parts"].pop("SM_PearlClam_Pearl_v2"), "MANIFEST_PART_MISSING")):
    bm = copy.deepcopy(man)
    fn(bm)
    check("J1.manifest_v2_%s_refused(-)" % nm, any(needle in x for x in T["pearl_v2_manifest_problems"](bm)),
          T["pearl_v2_manifest_problems"](bm))
check("J1.v1_tables_untouched", list(CP) == ["Bottom", "Lid", "Mantle", "Pearl"] and V2 not in T["CLAM_MATERIALS"] and
      "Nacre" not in T["TEX_ROLES"] and T["CLAM_PART_ORDER"] == ("Bottom", "Lid", "Mantle", "Pearl"))

# J2. bounds gate (Y flip, same logic as v1)
e2 = T["clam_expected_ue"](V2)
check("J2.flipped_bounds_pass(+)", T["clam_bounds_check"](V2, {"min": e2["min"], "max": e2["max"]}) == [])
check("J2.expected_is_y_flipped", T["near"](e2["centroid"], [-0.096, -0.089, 8.906], 1e-9), e2["centroid"])
f = T["clam_bounds_check"](V2, {k: [x * 100 for x in e2[k]] for k in ("min", "max")})
check("J2.100x_refused(-)", bool(f) and f[0].startswith("SCALE_100X"), f[:1])
f = T["clam_bounds_check"](V2, {"min": [-9.0, -9.0, 0.0], "max": [9.0, 9.0, 19.0]})
check("J2.1cm_tall_refused(-)", bool(f), f[:1])
check("J2.pivot_lowest_point", e2["min"][2] == 0.0)
check("J2.centroid_pass(+)", T["clam_centroid_check"](V2, e2["centroid"]) == [])
rows = T["pipeline_wanted"](T["clam_vc_option"](V2), R2["custom_normals"])
check("J2.pipeline_plan_clean(+)", T["pipeline_problems"](rows, V2) == [] and T["clam_vc_option"](V2) == "IVCIO_IGNORE",
      T["pipeline_problems"](rows, V2))
check("J2.mesh_path_new_asset", T["clam_mesh_path"](V2).endswith("/PearlClam/SM_PearlClam_Pearl_v2") and
      T["clam_mesh_path"](V2) != T["clam_mesh_path"]("Pearl"))
ok, msg = refuses(lambda: T["clam_part_row"]("Pearl_v3"), "CLAM_PART")
check("J2.unknown_part_refused(-)", ok, msg)

# J3. mode gates
for nm, a_, exp in (("import_mesh_v2", {"mode": "IMPORT_MESH", "confirm": "IMPORT_MESH S3PROPS", "prop": "PearlClam", "part": V2}, "IMPORT_MESH"),
                    ("import_tex_nacre", {"mode": "IMPORT_TEX", "confirm": "IMPORT_TEX S3PROPS", "prop": "PearlClam",
                                          "tex_set": "Pearl", "textures": ["Nacre"]}, "IMPORT_TEX"),
                    ("build_mat_v2", {"mode": "BUILD_MAT", "confirm": "BUILD_MAT S3PROPS", "prop": "PearlClam", "material": V2}, "BUILD_MAT"),
                    ("mat_check_no_confirm", {"mode": "PEARL_MAT_CHECK"}, "PEARL_MAT_CHECK")):
    check("J3.%s_ok(+)" % nm, CM(a_, True, False, False, True) == exp)
check("J3.mat_check_allowed_while_pending(+)", CM({"mode": "PEARL_MAT_CHECK"}, True, False, True, True) == "PEARL_MAT_CHECK")
check("J3.swap_ok(+)", CM({"mode": "PEARL_SWAP", "confirm": "PEARL_SWAP S3PROPS"}, True, False, False, True, False) == "PEARL_SWAP")
check("J3.unswap_ok(+)", CM({"mode": "PEARL_UNSWAP", "confirm": "PEARL_UNSWAP S3PROPS"}, True, False, False, True, True) == "PEARL_UNSWAP")
for nm, call, needle in (
        ("nacre_on_shell", lambda: CM({"mode": "IMPORT_TEX", "confirm": "IMPORT_TEX S3PROPS", "prop": "PearlClam", "tex_set": "Shell",
                                       "textures": ["Nacre"]}, True, False), "ROLE_NOT_IN_SET"),
        ("basecolor_on_pearl_set", lambda: CM({"mode": "IMPORT_TEX", "confirm": "IMPORT_TEX S3PROPS", "prop": "PearlClam",
                                               "tex_set": "Pearl", "textures": ["BaseColor"]}, True, False), "ROLE_NOT_IN_SET"),
        ("nacre_on_classic_prop", lambda: CM({"mode": "IMPORT_TEX", "confirm": "IMPORT_TEX S3PROPS", "prop": "HominidJaw",
                                              "textures": ["Nacre"]}, True, False), "ROLE"),
        ("unknown_material", lambda: CM({"mode": "BUILD_MAT", "confirm": "BUILD_MAT S3PROPS", "prop": "PearlClam",
                                         "material": "Pearl_v9"}, True, False), "CLAM_MATERIAL"),   # v3 is real since 7 Oct eve
        ("swap_confirm", lambda: CM({"mode": "PEARL_SWAP", "confirm": "PEARL_SWAP"}, True, False, False, True), "CONFIRM_MISSING"),
        ("swap_without_clam", lambda: CM({"mode": "PEARL_SWAP", "confirm": "PEARL_SWAP S3PROPS"}, True, False, False, False), "NO_CLAM_RECORD"),
        ("swap_twice", lambda: CM({"mode": "PEARL_SWAP", "confirm": "PEARL_SWAP S3PROPS"}, True, False, False, True, True),
         "PEARL_ALREADY_SWAPPED"),
        ("unswap_without_record", lambda: CM({"mode": "PEARL_UNSWAP", "confirm": "PEARL_UNSWAP S3PROPS"}, True, False, False, True, False),
         "NO_PEARL_SWAP_RECORD"),
        ("clam_revert_while_swapped", lambda: CM({"mode": "CLAM_REVERT", "confirm": "CLAM_REVERT S3PROPS"}, True, False, False, True, True),
         "PEARL_SWAPPED"),
        ("swap_while_tex_pending", lambda: CM({"mode": "PEARL_SWAP", "confirm": "PEARL_SWAP S3PROPS"}, True, False, True, True),
         "TEX_PENDING")):
    ok, msg = refuses(call, needle)
    check("J3.%s_refused(-)" % nm, ok, msg)

# J4. Nacre texture
tn = T["tex_target"]("PearlClam", "Pearl", "Nacre")
rn = T["tex_source_gate"](tn)
check("J4.nacre_source_2048(+)", tn["name"] == "T_PearlClam_Pearl_Nacre" and rn["w"] == rn["h"] == 2048 and
      tn["asset"].endswith("/PearlClam/T_PearlClam_Pearl_Nacre"), (tn, rn))
check("J4.nacre_linear_masks", T["ROLE_SPEC"]["Nacre"][1:5] == ("TC_MASKS", False, False, "SAMPLERTYPE_MASKS"))
ok, msg = refuses(lambda: T["tex_source_gate"](dict(tn, dim=4096)), "TEX_DIM")
check("J4.nacre_wrong_dim_refused(-)", ok, msg)
with Image.open(tn["file"]) as im:
    na = np.asarray(im).astype(float) / 255.0
grey = na.ndim == 2 or (np.abs(na[..., 0] - na[..., 1]).max() == 0 and np.abs(na[..., 0] - na[..., 2]).max() == 0)
pc = np.percentile(na[..., 0] if na.ndim == 3 else na, [5, 50, 95])
check("J4.nacre_grey_R_carries_it", grey, na.shape)
check("J4.nacre_percentiles_match_manifest", T["near"](pc.tolist(), [0.18, 0.44, 0.75], 0.01) and
      abs(pc[1] - T["NACRE_MEDIAN"]) < 0.01, pc.tolist())

# J5. material v2
specs = T["material_specs"]()
S2 = specs[T["PEARL_V2_MASTER"]]
S1 = specs[T["PEARL_MASTER"]]
check("J5.v2_spec_clean(+)", T["PEARL_V2_MASTER"] not in T["material_problems"]() and V2 not in T["material_problems"](),
      T["material_problems"]())
for nm, fn, needle in (
        ("orphan", lambda s: (s["nodes"].update(Orphan=("scalar", 1.0)), s["scalars"].update(Orphan=1.0)), "UNUSED_NODE|Orphan"),
        ("phase_nacre_unfed", lambda s: s.update(edges=[e for e in s["edges"] if not (e[2] == "IridPhase" and e[3] == "N")]),
         "CUSTOM_PIN_UNFED|IridPhase.N"),
        ("emissive_twice", lambda s: s["props"].append(("IridColor", "", "MP_EMISSIVE_COLOR")), "PROP_SET_TWICE"),
        ("no_wpo", lambda s: s.update(props=[p for p in s["props"] if p[2] != "MP_WORLD_POSITION_OFFSET"]), "PROPS")):
    bad = copy.deepcopy(specs)
    fn(bad[T["PEARL_V2_MASTER"]])
    got = T["material_problems"](bad).get(T["PEARL_V2_MASTER"], [])
    check("J5.%s_detected(-)" % nm, any(needle in x for x in got), got)
bad = copy.deepcopy(specs)
bad[T["PEARL_V2_MASTER"]]["tex_params"] = {"Nacre": "Roughness"}
check("J5.tex_set_role_mismatch_detected(-)", any("TEX_SET_ROLES" in x for x in T["material_problems"](bad).get(V2, [])),
      T["material_problems"](bad))
check("J5.wpo_parity_with_v1", S2["nodes"]["PearlWPO"] == S1["nodes"]["PearlWPO"] and
      [e for e in S2["edges"] if e[2] == "PearlWPO"] == [e for e in S1["edges"] if e[2] == "PearlWPO"] and
      S2["max_wpo"] == S1["max_wpo"] and S2["scalars"]["BreathAmp"] == 0.0 and S2["scalars"]["BreathPeriod"] == 5.0)
check("J5.mi_scalars_parity_with_v1", T["CLAM_EXTRA_MATERIALS"][V2]["scalars"] == T["CLAM_MATERIALS"]["Pearl"]["scalars"])
check("J5.v1_pearl_spec_unchanged", sorted(S1["nodes"]) == sorted(
    ["BaseColor", "WarmTint", "CoolTint", "GlowColor", "TintAmount", "Roughness", "Specular", "Glow", "BreathAmp",
     "BreathPeriod", "Fresnel", "Time", "PearlColor", "GlowEmissive", "PearlWPO"]) and S1["scalars"]["Roughness"] == 0.18)
check("J5.defaults", S2["vectors"]["BaseColor"][:3] == [0.86, 0.83, 0.78] and S2["scalars"]["Specular"] == 0.6 and
      S2["scalars"]["Roughness"] == 0.15 and S2["scalars"]["Glow"] == 0.0 and S2["tex_params"] == {"Nacre": "Nacre"})
check("J5.hlsl_reads_pixel_normal_and_camera", "Parameters.WorldNormal" in T["IRID_PHASE_CODE"] and
      "Parameters.CameraVector" in T["IRID_PHASE_CODE"])
check("J5.nacre_feeds_phase_and_roughness", ("Nacre", "R", "IridPhase", "N") in S2["edges"] and
      ("Nacre", "R", "PearlRough", "N") in S2["edges"])
sv, ss = S2["vectors"], S2["scalars"]
pal = [sv[k] for k in ("PaletteA", "PaletteB", "PaletteC", "PaletteD")]
col = lambda ndv, nac, st=ss["IridStrength"]: T["irid_color_eval"](sv["BaseColor"], *pal, T["irid_phase_eval"](  # noqa: E731
    ndv, ss["FresnelExponent"], ss["IridScale"], nac, ss["NacreScale"]), st)
check("J5.strength0_is_base_exactly(-control)", col(0.3, 0.6, 0.0) == sv["BaseColor"][:3], col(0.3, 0.6, 0.0))
facing, grazing = col(1.0, 0.44), col(0.05, 0.44)
check("J5.facing_vs_grazing_shift", max(abs(facing[i] - grazing[i]) for i in range(3)) > 0.08, (facing, grazing))
sweep = [T["irid_color_eval"](sv["BaseColor"], *pal, t / 20.0, ss["IridStrength"]) for t in range(21)]
check("J5.hue_rotates_over_phase(thin-film)", len({max(range(3), key=lambda i: c[i]) for c in sweep}) == 3,
      [max(range(3), key=lambda i: c[i]) for c in sweep])
check("J5.stays_pale(min channel > 0.5)", min(min(c) for c in sweep) > 0.5, min(min(c) for c in sweep))
check("J5.nacre_shifts_colour_at_facing", max(abs(col(1.0, 0.18)[i] - col(1.0, 0.75)[i]) for i in range(3)) > 0.03)
re2 = T["irid_rough_eval"]
check("J5.roughness_median_0.15_range_small", abs(re2(ss["Roughness"], 0.44, ss["RoughnessNacre"]) - 0.15) < 1e-9 and
      0.10 < re2(ss["Roughness"], 0.18, ss["RoughnessNacre"]) < re2(ss["Roughness"], 0.75, ss["RoughnessNacre"]) < 0.20)
check("J5.rough_code_uses_median", ("%.2f" % T["NACRE_MEDIAN"]) in T["IRID_ROUGH_CODE"])

# J6. swap plan against the REAL apply record (read-only)
crec = json.load(open(T["CLAM_RECORD"], encoding="utf-8"))
v1m, v1i = T["clam_mesh_path"]("Pearl"), T["clam_mi_path"]("Pearl")
v2m, v2i = T["clam_mesh_path"](V2), T["clam_mi_path"](V2)
pp_ = crec["plan"]["parts"]["Pearl"]


def pearl_live():
    return {"count": 1, "label": "S3 PearlClam Pearl", "object_path": crec["actor_paths"]["Pearl"],
            "parent_path": crec["actor_paths"]["Bottom"], "mesh": v1m, "materials": [v1i], "override_materials": [v1i],
            "rel": copy.deepcopy(pp_["rel"]), "world": {"location": pp_["world_location"], "rotation": pp_["world_rotation"],
                                                         "scale": [1.0, 1.0, 1.0]},
            "hidden": True, "wpo_eval": True, "assets": {v2m: True, v2i: True}, "v2_slots": ["M_PearlClam_Pearl"],
            "tracks": {s: (["MovieSceneVisibilityTrack"] if s == T["RISE"] else None) for s in T["CLAM_SEQUENCES"]}}


check("J6.record_is_todays_apply", crec["run"] == "S3PROPS-20261007-183435" and pp_["label"] == "S3 PearlClam Pearl", crec["run"])
sp = T["pearl_swap_plan"](crec, pearl_live())
check("J6.plan_ok(+)", sp["after"]["mesh"] == v2m and sp["after"]["materials"] == [v2i] and sp["before"]["mesh"] == v1m and
      sp["before"]["materials"] == [v1i] and sp["after"]["rel"] == sp["before"]["rel"] and sp["after"]["world"] == sp["before"]["world"])
for nm, fn, needle in (
        ("count", lambda L: L.update(count=2), "PEARL_COUNT"),
        ("label", lambda L: L.update(label="S3 PearlClam Lid"), "PEARL_LABEL"),
        ("path", lambda L: L.update(object_path="X"), "PEARL_PATH"),
        ("parent", lambda L: L.update(parent_path=None), "PEARL_PARENT"),
        ("already_v2", lambda L: L.update(mesh=v2m), "PEARL_MESH_NOT_V1"),
        ("material_not_v1", lambda L: L.update(materials=["/Game/X/MI_Y"]), "PEARL_MATERIALS_NOT_V1"),
        ("overrides", lambda L: L.update(override_materials=[]), "PEARL_OVERRIDES"),
        ("v2_mi_missing", lambda L: L["assets"].update({v2i: False}), "V2_ASSETS_MISSING"),
        ("v2_slots", lambda L: L.update(v2_slots=["M_Other"]), "V2_SLOTS"),
        ("rel_drift_0.1cm", lambda L: L["rel"]["location"].__setitem__(2, L["rel"]["location"][2] + 0.1), "PEARL_REL_DRIFT"),
        ("wpo_off", lambda L: L.update(wpo_eval=False), "PEARL_WPO_EVAL_OFF"),
        ("tracks_unread", lambda L: L["tracks"].update({T["SCENE3"]: "UNREAD"}), "PEARL_TRACKS_UNREAD"),
        ("material_track", lambda L: L["tracks"].update({T["SCENE3"]: ["MovieSceneComponentMaterialTrack"]}),
         "PEARL_MATERIAL_TRACKS")):
    L = pearl_live()
    fn(L)
    ok, msg = refuses(lambda L=L: T["pearl_swap_plan"](crec, L), needle)
    check("J6.%s_refused(-)" % nm, ok, msg)
L = pearl_live()
L["tracks"][T["SCENE3"]] = ["MovieSceneComponentMaterialTrack"]
check("J6.material_track_allowed_by_arg(+)", T["pearl_swap_plan"](crec, L, {"allow_material_tracks": True})["material_tracks"] ==
      ["MovieSceneComponentMaterialTrack"])
L = pearl_live()
L["rel"]["location"][2] += 0.01
check("J6.rel_0.01cm_within_tol(+)", T["pearl_swap_plan"](crec, L)["after"]["rel"]["location"][2] == L["rel"]["location"][2])
nr = dict(crec, applied=False)
ok, msg = refuses(lambda: T["pearl_swap_plan"](nr, pearl_live()), "CLAM_RECORD_NOT_APPLIED")
check("J6.unapplied_clam_record_refused(-)", ok, msg)

# J7. ops round trip + read-back gate
w0 = {sp["object_path"]: copy.deepcopy(sp["before"])}
w1 = T["pearl_simulate"](w0, T["pearl_swap_ops"](sp))
check("J7.swap_effect", T["pearl_state_problems"](w1[sp["object_path"]], sp["after"]) == [],
      T["pearl_state_problems"](w1[sp["object_path"]], sp["after"]))
check("J7.swapped_differs_from_before(-)", bool(T["pearl_state_problems"](w1[sp["object_path"]], sp["before"])))
srec = {"plan": json.loads(json.dumps(sp))}
w2 = T["pearl_simulate"](w1, T["pearl_unswap_ops"](srec))
check("J7.unswap_exact(+)", w2 == w0, json.dumps(w2)[:300])
bad = copy.deepcopy(srec)
bad["plan"]["before"]["mesh"] = "/Game/Other/SM_X"
check("J7.tampered_record_detected(-)", T["pearl_simulate"](w1, T["pearl_unswap_ops"](bad)) != w0)
bad = copy.deepcopy(srec)
bad["plan"]["object_path"] = "PersistentLevel.SomeoneElse"
ok, msg = refuses(lambda: T["pearl_simulate"](w1, T["pearl_unswap_ops"](bad)), "SIM_PEARL_TARGET")
check("J7.foreign_target_refused(-)", ok, msg)
dl = copy.deepcopy(sp["after"])
dl["rel"]["location"][2] += 0.1
check("J7.readback_rel_drift_detected(-)", any("REL_LOCATION" in x for x in T["pearl_state_problems"](dl, sp["after"])))
dl = copy.deepcopy(sp["after"])
dl["world"]["rotation"][2] += 360.0
check("J7.readback_yaw_wrap_ok(+)", T["pearl_state_problems"](dl, sp["after"]) == [])
dl = copy.deepcopy(sp["after"])
dl["hidden"] = False
check("J7.readback_hidden_flip_detected(-)", any("HIDDEN" in x for x in T["pearl_state_problems"](dl, sp["after"])))
# (until 7 Oct 19:27 this also asserted the record did not exist; PEARL_SWAP S3PROPS-20261007-192700 ran and wrote it
#  [meas: the record on disk, saved+applied], so existence is now reported, not gated)
check("J7.swap_record_path_separate", T["PEARL_SWAP_RECORD"] != T["CLAM_RECORD"],
      "pearl swap record on disk: %s" % os.path.exists(T["PEARL_SWAP_RECORD"]))

# J8. compile log scan
CL = T["compile_log_problems"]
nm2 = ["M_PearlClam_Pearl_v2", "MI_PearlClam_Pearl_v2"]
lines = ["LogMaterial: Warning: Failed to compile Material /Game/X/PearlClam/M_PearlClam_Pearl_v2.M_PearlClam_Pearl_v2 for "
         "platform PCD3D_SM6, Default Material will be used in game.\n"]
check("J8.named_failure_caught(-)", CL(lines, nm2)[0] != [], CL(lines, nm2))
check("J8.own_markers_ignored(+)", CL(["LogPython: S3PROPS_BUILD_MAT_OK|run=x|mi=/Game/X/MI_PearlClam_Pearl_v2 error\n"], nm2) == ([], []))
n_, u_ = CL(["LogMaterial: Warning: Failed to compile Material /Game/Other/M_Z for platform SM6\n"], nm2)
check("J8.unrelated_failure_unattributed_only", n_ == [] and len(u_) == 1, (n_, u_))
check("J8.clean_log(+)", CL(["LogMaterial: Display: Compiling M_PearlClam_Pearl_v2\n"], nm2) == ([], []))
check("J8.hlsl_error_line_caught(-)", CL(["/Game/X/M_PearlClam_Pearl_v2: [SM6] (12,3): error X3004: undeclared identifier\n"],
                                           nm2)[0] != [])

# ================================================================== K. clam looks (7 Oct evening): Pearl_v3 / Shell_v2 / Mantle_v2
LOOKS = T["CLAM_LOOK_MATERIALS"]
P3, SH2, MA2 = T["PEARL_V3"], T["SHELL_V2"], T["MANTLE_V2"]
specs = T["material_specs"]()
SP3, SSH, SMA = specs[T["PEARL_V3_MASTER"]], specs[T["SHELL_V2_MASTER"]], specs[T["MANTLE_V2_MASTER"]]
SBR, SV2 = specs[T["MASTER_BREATHE"]], specs[T["PEARL_V2_MASTER"]]
mp = T["material_problems"]()
# K1. specs + tables
check("K1.look_specs_clean(+)", not any(k in mp for k in (T["PEARL_V3_MASTER"], T["SHELL_V2_MASTER"], T["MANTLE_V2_MASTER"])
                                        + LOOKS), mp)
check("K1.look_table_clean(+)", T["look_table_problems"]() == [], T["look_table_problems"]())
check("K1.shading_models", SP3["shading_model"] == "MSM_SUBSURFACE" and SMA["shading_model"] == "MSM_SUBSURFACE" and
      SSH["shading_model"] == "MSM_DEFAULT_LIT")
check("K1.subsurface_pins_wired", all(("MP_SUBSURFACE_COLOR" in {p[2] for p in s["props"]} and
                                       "MP_OPACITY" in {p[2] for p in s["props"]}) for s in (SP3, SMA)) and
      not ({"MP_SUBSURFACE_COLOR", "MP_OPACITY"} & {p[2] for p in SSH["props"]}))
check("K1.no_clearcoat", not any("CLEAR" in p[2] or "CUSTOM_DATA" in p[2] for s in (SP3, SSH, SMA) for p in s["props"]) and
      all(s["shading_model"] != "MSM_CLEAR_COAT" for s in (SP3, SSH, SMA)))
old_masters = {T["MASTER"], T["MASTER_BREATHE"], T["PEARL_MASTER"], T["PEARL_V2_MASTER"]}
rows_ = {k: T["CLAM_EXTRA_MATERIALS"][k] for k in LOOKS}
check("K1.new_masters_and_mis_only", all(r["master"] not in old_masters and r["master_create_only"] for r in rows_.values()) and
      len({r["mi"] for r in rows_.values()} | {m["mi"] for m in T["CLAM_MATERIALS"].values()} |
          {T["CLAM_EXTRA_MATERIALS"][T["PEARL_V2"]]["mi"]}) == 9, rows_)
check("K1.mesh_tables_untouched", list(CP) == ["Bottom", "Lid", "Mantle", "Pearl"] and
      sorted(T["CLAM_EXTRA_PARTS"]) == [T["PEARL_V2"]] and not any(k in T["CLAM_MATERIALS"] for k in LOOKS))
check("K1.shell_reuses_shell_textures", SSH["tex_params"] == T["MASTER_TEX_PARAMS"] and rows_[SH2]["tex_set"] == "Shell" and
      SMA["tex_params"] == T["MASTER_TEX_PARAMS"] and rows_[MA2]["tex_set"] == "Mantle" and SP3["tex_params"] == {"Nacre": "Nacre"})
check("K1.shell_normal_feeds_normal_and_ridges", ("Normal", "RGB", "ShellRough", "NM") in SSH["edges"] and
      ("Normal", "RGB", "MP_NORMAL") in SSH["props"])
check("K1.pearl_v3_mesh_stays_v2", T["CLAM_LOOKS"][P3]["mesh_part"] == {"Pearl": T["PEARL_V2"]})
check("K1.shell_swap_both_actors_slot0", T["CLAM_LOOKS"][SH2]["targets"] == {"Bottom": 0, "Lid": 0} and
      CP["Bottom"]["slots"][0] == CP["Lid"]["slots"][0] == "M_PearlClam_Shell")
# K2. breathing WPO parity (node specs incl. code strings, edges, defaults, max WPO)
sub = T["_subgraph"]
check("K2.pearl_v3_wpo_identical_to_v2(+)", sub(SP3, "PearlWPO") == sub(SV2, "PearlWPO") and
      SP3["nodes"]["PearlWPO"][1][0] == T["PEARL_BREATH_CODE"] and SP3["max_wpo"] == SV2["max_wpo"] and
      all(SP3["scalars"][k] == SV2["scalars"][k] for k in ("BreathAmp", "BreathPeriod")), sub(SP3, "PearlWPO"))
check("K2.mantle_v2_wpo_identical_to_breathe(+)", sub(SMA, "BreathWPO") == sub(SBR, "BreathWPO") and
      SMA["nodes"]["BreathWPO"][1][0] == T["BREATH_CODE"] and ("VColor", "R", "BreathWPO", "M") in SMA["edges"] and
      SMA["max_wpo"] == SBR["max_wpo"] and all(SMA["scalars"][k] == SBR["scalars"][k] for k in ("BreathAmp", "BreathPeriod")))
check("K2.wpo_wired_to_wpo_pin", ("PearlWPO", "", "MP_WORLD_POSITION_OFFSET") in SP3["props"] and
      ("BreathWPO", "", "MP_WORLD_POSITION_OFFSET") in SMA["props"] and SSH["max_wpo"] is None)
bad = copy.deepcopy(SMA)
bad["nodes"]["BreathWPO"] = ("custom", (T["BREATH_CODE"].replace("0.5 - 0.5", "0.5 - 0.6"), ["M", "A", "T", "P"], "F3"))
check("K2.parity_check_can_fail(-control: one changed constant)", sub(bad, "BreathWPO") != sub(SBR, "BreathWPO"))
bad = copy.deepcopy(SMA)
bad["edges"] = [e for e in bad["edges"] if e != ("VColor", "R", "BreathWPO", "M")] + [("VColor", "G", "BreathWPO", "M")]
check("K2.mask_channel_change_detected(-control)", sub(bad, "BreathWPO") != sub(SBR, "BreathWPO"))
# - controls: every custom pin of every new master, unfed one at a time, must be named
for path in (T["PEARL_V3_MASTER"], T["SHELL_V2_MASTER"], T["MANTLE_V2_MASTER"]):
    s0 = specs[path]
    custom_edges = [e for e in s0["edges"] if s0["nodes"][e[2]][0] == "custom"]
    caught = []
    for e in custom_edges:
        b = copy.deepcopy(specs)
        b[path]["edges"] = [x for x in b[path]["edges"] if x != e]
        caught.append(any(("CUSTOM_PIN_UNFED|%s.%s" % (e[2], e[3])) in x for x in T["material_problems"](b).get(path, [])))
    check("K2.unfed_pin_detected_each(-)|" + path.rsplit("/", 1)[1], len(caught) >= 5 and all(caught), (len(caught), caught))
for nm, fn, needle, path in (
        ("subsurface_on_defaultlit", lambda s: s.update(shading_model="MSM_DEFAULT_LIT"), "SUBSURFACE_PINS", T["PEARL_V3_MASTER"]),
        ("subsurface_without_opacity", lambda s: (s.update(props=[p for p in s["props"] if p[2] != "MP_OPACITY"]),
                                                  s["want_props"].discard("MP_OPACITY")), "SUBSURFACE_PINS", T["MANTLE_V2_MASTER"]),
        ("clearcoat_model", lambda s: s.update(shading_model="MSM_CLEAR_COAT"), "SHADING_MODEL", T["SHELL_V2_MASTER"]),
        ("orphan", lambda s: (s["nodes"].update(Orphan=("scalar", 1.0)), s["scalars"].update(Orphan=1.0)), "UNUSED_NODE|Orphan",
         T["SHELL_V2_MASTER"]),
        ("unused_custom_pin", lambda s: s["nodes"].update(WetColor=("custom", (T["MANTLE_COLOR_CODE"].replace("1.0 + S", "1.0"),
                                                                               ["B", "D", "S"], "F3"))),
         "CUSTOM_PIN_UNUSED|WetColor.S", T["MANTLE_V2_MASTER"]),
        ("opacity_twice", lambda s: s["props"].append(("Specular", "", "MP_OPACITY")), "PROP_SET_TWICE", T["PEARL_V3_MASTER"])):
    b = copy.deepcopy(specs)
    fn(b[path])
    got = T["material_problems"](b).get(path, [])
    check("K2.%s_detected(-)" % nm, any(needle in x for x in got), got)
# K3. Python mirrors of the HLSL (look behaviour)
v, s_ = SP3["vectors"], SP3["scalars"]
pal3 = [v[k] for k in ("PaletteA", "PaletteB", "PaletteC", "PaletteD")]
ph = lambda ndv, nac=0.44: T["irid_phase_eval"](ndv, s_["FresnelExponent"], s_["IridScale"], nac, s_["NacreScale"])  # noqa: E731
surf = lambda ndv: T["irid_color_eval"](v["BaseColor"], *pal3, ph(ndv), s_["IridStrength"])  # noqa: E731
subs = lambda ndv: T["irid_color_eval"](v["SubsurfaceBase"], *pal3, ph(ndv), s_["SubsurfaceIrid"])  # noqa: E731
sw = [T["irid_color_eval"](v["SubsurfaceBase"], *pal3, t / 20.0, s_["SubsurfaceIrid"]) for t in range(21)]
check("K3.v3_surface_iridescence_faint", max(abs(surf(n)[i] - v["BaseColor"][i]) for n in (1.0, 0.5, 0.05) for i in range(3)) < 0.05)
check("K3.v3_subsurface_carries_the_hue_cycle", len({max(range(3), key=lambda i: c[i]) for c in sw}) == 3 and
      max(abs(subs(1.0)[i] - subs(0.05)[i]) for i in range(3)) > 3 * max(abs(surf(1.0)[i] - surf(0.05)[i]) for i in range(3)))
gl = lambda ndv, g=0.1: T["inner_glow_eval"](ndv, s_["GlowFresnelExponent"], s_["GlowFalloff"], g, v["GlowColor"], subs(ndv),  # noqa: E731
                                             s_["GlowIrid"])
check("K3.v3_glow_centre_not_rim", sum(gl(1.0)) > 5 * sum(gl(0.05)) and sum(gl(0.0)) < 1e-9 and sum(gl(1.0)) > 0, (gl(1.0), gl(0.05)))
check("K3.v3_glow_zero_when_off(-control)", gl(1.0, 0.0) == [0.0, 0.0, 0.0])
check("K3.v3_glaze_roughness", all(0.08 <= T["irid_rough_eval"](s_["Roughness"], n, s_["RoughnessNacre"]) <= 0.12
                                   for n in (0.18, 0.44, 0.75)) and s_["Specular"] == 0.6 and s_["SubsurfaceAmount"] == 0.6)
check("K3.v3_mi_glow_gentle", rows_[P3]["scalars"] == {"Glow": 0.1} and SP3["scalars"]["Glow"] == 0.0)
sh = SSH["scalars"]
sre = lambda r, nz=1.0: T["shell_rough_eval"](r, nz, sh["ShellThreshold"], sh["ShellContrast"], sh["RidgeFromNormal"],  # noqa: E731
                                              sh["GlossRough"], sh["RidgeRough"])
check("K3.shell_two_levels", abs(sre(0.80) - sh["GlossRough"]) < 1e-12 and abs(sre(1.0) - sh["RidgeRough"]) < 1e-12 and
      abs(sre(0.80, 0.96) - sh["RidgeRough"]) < 1e-12 and 0.5 < sre(0.80, 0.97) < 0.7, (sre(0.80), sre(1.0), sre(0.80, 0.97)))
with Image.open(T["CLAM_DIR"] + "T_PearlClam_Shell_Roughness.png") as im:
    ra = np.asarray(im)
ra = (ra[..., 0] if ra.ndim == 3 else ra)[::4, ::4].astype(float) / 255.0
ra = ra[ra < 0.99]                                       # the 1.0 gutter (7.7 % of texels) excluded
rr = np.vectorize(sre)(ra)
gloss_share, rough_share = float((rr < 0.35).mean()), float((rr > 0.55).mean())
check("K3.shell_mostly_wet_gloss_some_chalk(measured map)", 0.45 < gloss_share < 0.85 and 0.08 < rough_share < 0.45,
      (round(gloss_share, 3), round(rough_share, 3), np.percentile(ra, [5, 50, 95]).round(3).tolist()))
with Image.open(T["CLAM_DIR"] + "T_PearlClam_Shell_N.png") as im:
    na = np.asarray(im)[::4, ::4, :3].astype(float) / 255.0 * 2.0 - 1.0
nz = np.sqrt(np.clip(1.0 - na[..., 0] ** 2 - na[..., 1] ** 2, 0.0, 1.0))          # == UnpackNormalMap (Common.ush:1708)
ridge_share = float(((1.0 - nz) * sh["RidgeFromNormal"] >= 0.5).mean())
check("K3.shell_normal_ridges_sparse(measured map)", 0.003 < ridge_share < 0.15, round(ridge_share, 4))
ms_, mv_ = SMA["scalars"], SMA["vectors"]
mc0 = [0.6, 0.35, 0.4]
mc = T["mantle_color_eval"](mc0, ms_["WetDarken"], ms_["WetSaturation"])
lum = lambda c: 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]  # noqa: E731
check("K3.mantle_wet_darker_and_richer", lum(mc) < lum(mc0) and (max(mc) - min(mc)) / max(mc) > (max(mc0) - min(mc0)) / max(mc0))
check("K3.mantle_colour_identity_when_off(-control)", T["mantle_color_eval"](mc0, 0.0, 0.0) == [T["_sat"](x) for x in mc0])
wp0 = [14424.4, 159997.1, 157.6]
mre = lambda r, wa=ms_["WetAmount"], ga=ms_["GlistenAmount"], t=0.0, wp=wp0, gv=ms_["GlistenSpeed"]: T["mantle_rough_eval"](  # noqa: E731
    r, ms_["WetRough"], wa, ga, ms_["GlistenScale"], gv, wp, t)
check("K3.mantle_wet_film_exact", abs(mre(0.32, 1.0, 0.0) - ms_["WetRough"]) < 1e-12 and abs(mre(0.32, 0.0, 0.0) - 0.32) < 1e-12)
noise = [T["glisten_noise_eval"]([wp0[0] + dx, wp0[1] + dx * 0.7, wp0[2]], ms_["GlistenScale"], t, ms_["GlistenSpeed"])
         for dx in range(0, 200, 3) for t in (0.0, 7.0, 21.0)]
check("K3.glisten_noise_in_0_1_and_varies", 0.0 <= min(noise) and max(noise) <= 1.0 and max(noise) - min(noise) > 0.6,
      (min(noise), max(noise)))
vals = [mre(0.32, wp=[wp0[0] + dx, wp0[1], wp0[2]]) for dx in range(0, 120, 2)]
check("K3.mantle_rough_wet_glistening", 0.04 < min(vals) and max(vals) < 0.2 and max(vals) - min(vals) > 0.05,
      (round(min(vals), 3), round(max(vals), 3)))
check("K3.glisten_moves_with_time_static_at_speed0", mre(0.32, t=5.0) != mre(0.32, t=0.0) and
      mre(0.32, t=5.0, gv=0.0) == mre(0.32, t=0.0, gv=0.0))
check("K3.glisten_off_is_flat(-control)", len({round(mre(0.32, ga=0.0, wp=[wp0[0] + dx, wp0[1], wp0[2]]), 12)
                                               for dx in range(0, 60, 3)}) == 1)
check("K3.mantle_defaults", ms_["Specular"] == 0.7 and ms_["WetRough"] == 0.05 and mv_["SubsurfaceColor"][0] >
      mv_["SubsurfaceColor"][2] > mv_["SubsurfaceColor"][1] * 0.95)
# K4. breathing scalars copied from the replaced MI (ClamBreath planned values: mantle 0.8/6, pearl 0.35/6)
lms = T["look_mi_scalars"]
check("K4.pearl_v3_inherits_breath(+)", lms(P3, {"BreathAmp": 0.35, "BreathPeriod": 6.0}) ==
      {"Glow": 0.1, "BreathAmp": 0.35, "BreathPeriod": 6.0})
check("K4.mantle_v2_inherits_breath(+)", lms(MA2, {"BreathAmp": 0.8, "BreathPeriod": 6.0}) == {"BreathAmp": 0.8, "BreathPeriod": 6.0})
check("K4.shell_no_breath(+)", lms(SH2) == {})
check("K4.breath_sources", rows_[P3]["breath_from"] == T["PEARL_V2"] and rows_[MA2]["breath_from"] == "Mantle" and
      rows_[SH2]["breath_from"] is None)
for nm, call, needle in (("unread", lambda: lms(MA2, {"BreathAmp": 0.8}), "BREATH_SOURCE_UNREAD"),
                         ("none", lambda: lms(P3, None), "BREATH_SOURCE_UNREAD"),
                         ("amp_over_max_wpo", lambda: lms(MA2, {"BreathAmp": 9.0, "BreathPeriod": 6.0}), "BREATH_SOURCE_RANGE"),
                         ("nan", lambda: lms(MA2, {"BreathAmp": float("nan"), "BreathPeriod": 6.0}), "BREATH_SOURCE_RANGE"),
                         ("shell_given_breath", lambda: lms(SH2, {"BreathAmp": 0.1, "BreathPeriod": 5.0}), "BREATH_NOT_EXPECTED")):
    ok, msg = refuses(call, needle)
    check("K4.%s_refused(-)" % nm, ok, msg)
# K5. mode gates
LS = lambda **k: dict({"mode": "CLAM_LOOK_SWAP", "confirm": "CLAM_LOOK_SWAP S3PROPS"}, **k)  # noqa: E731
LU = lambda **k: dict({"mode": "CLAM_LOOK_UNSWAP", "confirm": "CLAM_LOOK_UNSWAP S3PROPS"}, **k)  # noqa: E731
for k in LOOKS:
    check("K5.build_mat_ok(+)|" + k, CM({"mode": "BUILD_MAT", "confirm": "BUILD_MAT S3PROPS", "prop": "PearlClam", "material": k},
                                        True, False, False, True) == "BUILD_MAT")
    check("K5.mat_check_ok_no_confirm(+)|" + k, CM({"mode": "CLAM_LOOK_MAT_CHECK", "material": k}, True, False) == "CLAM_LOOK_MAT_CHECK")
check("K5.mat_check_while_tex_pending(+)", CM({"mode": "CLAM_LOOK_MAT_CHECK", "material": SH2}, True, False, True) ==
      "CLAM_LOOK_MAT_CHECK")
check("K5.swap_shell_ok(+)", CM(LS(look=SH2), True, False, False, True, False, []) == "CLAM_LOOK_SWAP")
check("K5.swap_pearl_v3_after_v2_ok(+)", CM(LS(look=P3), True, False, False, True, True, [SH2]) == "CLAM_LOOK_SWAP")
check("K5.unswap_ok(+)", CM(LU(look=MA2), True, False, False, True, False, [MA2]) == "CLAM_LOOK_UNSWAP")
check("K5.pearl_unswap_ok_with_shell_look_only(+)", CM({"mode": "PEARL_UNSWAP", "confirm": "PEARL_UNSWAP S3PROPS"},
                                                       True, False, False, True, True, [SH2]) == "PEARL_UNSWAP")
for nm, call, needle in (
        ("clam_revert_with_look_record", lambda: CM({"mode": "CLAM_REVERT", "confirm": "CLAM_REVERT S3PROPS"}, True, False, False,
                                                    True, False, [SH2]), "LOOK_SWAPPED"),
        ("pearl_unswap_with_v3", lambda: CM({"mode": "PEARL_UNSWAP", "confirm": "PEARL_UNSWAP S3PROPS"}, True, False, False, True,
                                            True, [P3]), "PEARL_LOOK_SWAPPED"),
        ("pearl_swap_with_v3", lambda: CM({"mode": "PEARL_SWAP", "confirm": "PEARL_SWAP S3PROPS"}, True, False, False, True,
                                          False, [P3]), "PEARL_LOOK_SWAPPED"),
        ("swap_twice", lambda: CM(LS(look=MA2), True, False, False, True, False, [MA2]), "LOOK_ALREADY_SWAPPED"),
        ("unswap_without_record", lambda: CM(LU(look=SH2), True, False, False, True, False, [MA2]), "NO_LOOK_SWAP_RECORD"),
        ("unknown_look", lambda: CM(LS(look="Shell_v9"), True, False, False, True), "LOOK|"),
        ("no_look_arg", lambda: CM(LS(), True, False, False, True), "LOOK|"),
        ("v3_before_v2", lambda: CM(LS(look=P3), True, False, False, True, False, []), "PEARL_V3_NEEDS_V2"),
        ("swap_without_clam", lambda: CM(LS(look=SH2), True, False, False, False), "NO_CLAM_RECORD"),
        ("swap_confirm", lambda: CM({"mode": "CLAM_LOOK_SWAP", "confirm": "CLAM_LOOK_SWAP", "look": SH2}, True, False, False, True),
         "CONFIRM_MISSING"),
        ("swap_while_tex_pending", lambda: CM(LS(look=SH2), True, False, True, True), "TEX_PENDING"),
        ("mat_check_unknown", lambda: CM({"mode": "CLAM_LOOK_MAT_CHECK", "material": "Pearl_v2"}, True, False), "LOOK_MATERIAL"),
        ("record_names_unknown", lambda: CM(LU(look=SH2), True, False, False, True, False, ["Shell_v9"]), "LOOK_RECORDS_UNKNOWN")):
    ok, msg = refuses(call, needle)
    check("K5.%s_refused(-)" % nm, ok, msg)
check("K5.record_paths_per_look", len({T["look_record_path"](k) for k in LOOKS}) == 3 and
      all(T["look_record_path"](k) not in (T["CLAM_RECORD"], T["PEARL_SWAP_RECORD"]) for k in LOOKS))
check("K5.read_only_mode", "CLAM_LOOK_MAT_CHECK" in T["READ_ONLY_MODES"] and "CLAM_LOOK_SWAP" not in T["READ_ONLY_MODES"])
# K6. swap plans against the REAL clam apply record (pearl already on v2: PEARL_SWAP S3PROPS-20261007-192700)
MI = T["clam_mi_path"]
cur_mi = {"Bottom": [MI("Shell"), MI("InteriorBottom")], "Lid": [MI("Shell"), MI("InteriorLid")], "Mantle": [MI("Mantle")],
          "Pearl": [MI(T["PEARL_V2"])]}
cur_mesh = {"Bottom": T["clam_mesh_path"]("Bottom"), "Lid": T["clam_mesh_path"]("Lid"), "Mantle": T["clam_mesh_path"]("Mantle"),
            "Pearl": T["clam_mesh_path"](T["PEARL_V2"])}


def look_actor(part):
    pr = crec["plan"]["parts"][part]
    return {"count": 1, "label": T["CLAM_LABELS"][part], "object_path": crec["actor_paths"][part],
            "parent_path": crec["actor_paths"]["Bottom"] if part != "Bottom" else None, "mesh": cur_mesh[part],
            "materials": list(cur_mi[part]), "override_materials": list(cur_mi[part]), "rel": copy.deepcopy(pr["rel"]),
            "world": {"location": list(pr["world_location"]), "rotation": list(pr["world_rotation"]), "scale": [1.0, 1.0, 1.0]},
            "hidden": True, "wpo_eval": True}


def look_live(look):
    row = T["CLAM_LOOKS"][look]
    old, new = MI(row["from_material"]), MI(look)
    return {"actors": {p: look_actor(p) for p in row["targets"]},
            "tracks": {p: {s: (["MovieSceneVisibilityTrack"] if s == T["RISE"] else None) for s in T["CLAM_SEQUENCES"]}
                       for p in row["targets"]},
            "assets": {old: True, new: True, T["CLAM_EXTRA_MATERIALS"][look]["master"]: True},
            "mesh_slots": {T["clam_mesh_path"]("Bottom"): list(CP["Bottom"]["slots"]), T["clam_mesh_path"]("Lid"): list(CP["Lid"]["slots"]),
                           T["clam_mesh_path"]("Mantle"): list(CP["Mantle"]["slots"]),
                           T["clam_mesh_path"](T["PEARL_V2"]): list(T["CLAM_EXTRA_PARTS"][T["PEARL_V2"]]["slots"])},
            "breath": ({old: {"BreathAmp": 0.35, "BreathPeriod": 6.0}, new: {"BreathAmp": 0.35, "BreathPeriod": 6.0}}
                       if row["breathes"] else {})}


LP = T["clam_look_swap_plan"]
plans = {}
for k in LOOKS:
    plans[k] = LP(k, crec, look_live(k))
    pl_ = plans[k]
    only_slot = all([i for i in range(len(t["before"]["materials"])) if t["before"]["materials"][i] != t["after"]["materials"][i]]
                    == [t["slot"]] for t in pl_["targets"])
    check("K6.plan_ok(+)|" + k, only_slot and pl_["new_mi"] == MI(k) and
          all(t["before"]["materials"][t["slot"]] == pl_["old_mi"] and t["after"]["materials"][t["slot"]] == MI(k)
              for t in pl_["targets"]), [(t["part"], t["slot"]) for t in pl_["targets"]])
check("K6.shell_targets_bottom_and_lid_slot0", [(t["part"], t["slot"]) for t in plans[SH2]["targets"]] == [("Bottom", 0), ("Lid", 0)]
      and all(t["after"]["materials"][1] == t["before"]["materials"][1] for t in plans[SH2]["targets"]))
check("K6.pearl_v3_replaces_v2_mi_keeps_v2_mesh", plans[P3]["old_mi"] == MI(T["PEARL_V2"]) and
      plans[P3]["targets"][0]["after"]["mesh"] == T["clam_mesh_path"](T["PEARL_V2"]))
check("K6.transforms_untouched_by_plan", all(t["after"]["rel"] == t["before"]["rel"] and t["after"]["world"] == t["before"]["world"]
                                             for pl_ in plans.values() for t in pl_["targets"]))
for nm, look, fn, needle in (
        ("wrong_slot_index_live", SH2, lambda L: L["mesh_slots"].update({T["clam_mesh_path"]("Lid"): CP["Lid"]["slots"][::-1]}),
         "LOOK_SLOT_INDEX"),
        ("pearl_still_v1_mi", P3, lambda L: L["actors"]["Pearl"].update(materials=[MI("Pearl")], override_materials=[MI("Pearl")]),
         "LOOK_MATERIAL_NOT_CURRENT"),
        ("pearl_still_v1_mesh", P3, lambda L: L["actors"]["Pearl"].update(mesh=T["clam_mesh_path"]("Pearl")), "LOOK_MESH"),
        ("no_explicit_override", MA2, lambda L: L["actors"]["Mantle"].update(override_materials=[]), "LOOK_OVERRIDE"),
        ("count", SH2, lambda L: L["actors"]["Lid"].update(count=2), "LOOK_COUNT"),
        ("path", MA2, lambda L: L["actors"]["Mantle"].update(object_path="X"), "LOOK_PATH"),
        ("parent", SH2, lambda L: L["actors"]["Lid"].update(parent_path=None), "LOOK_PARENT"),
        ("already_on", SH2, lambda L: L["actors"]["Bottom"].update(materials=[MI("Shell"), MI(SH2)]), "LOOK_ALREADY_ON"),
        ("assets_missing", MA2, lambda L: L["assets"].update({MI(MA2): False}), "LOOK_ASSETS_MISSING"),
        ("breath_mismatch", MA2, lambda L: L["breath"][MI(MA2)].update(BreathAmp=0.0), "LOOK_BREATH_MISMATCH"),
        ("breath_unread", P3, lambda L: L["breath"].pop(MI(P3)), "LOOK_BREATH_UNREAD"),
        ("wpo_off_breathing", MA2, lambda L: L["actors"]["Mantle"].update(wpo_eval=False), "LOOK_WPO_EVAL_OFF"),
        ("material_track", SH2, lambda L: L["tracks"]["Lid"].update({T["SCENE3"]: ["MovieSceneComponentMaterialTrack"]}),
         "LOOK_MATERIAL_TRACKS"),
        ("tracks_unread", P3, lambda L: L["tracks"]["Pearl"].update({T["SCENE3"]: "UNREAD"}), "LOOK_TRACKS_UNREAD")):
    L = look_live(look)
    fn(L)
    ok, msg = refuses(lambda L=L, look=look: LP(look, crec, L), needle)
    check("K6.%s_refused(-)" % nm, ok, msg)
saved_t = copy.deepcopy(T["CLAM_LOOKS"][SH2]["targets"])
T["CLAM_LOOKS"][SH2]["targets"]["Bottom"] = 1                      # the shared table object: a wrong slot index in the table
try:
    ok, msg = refuses(lambda: LP(SH2, crec, look_live(SH2)), "LOOK_SLOT_INDEX")
    check("K6.wrong_slot_index_table_refused(-)", ok and any("LOOK_SLOT_INDEX|Shell_v2|Bottom" in x for x in T["look_table_problems"]()),
          msg)
finally:
    T["CLAM_LOOKS"][SH2]["targets"].clear()
    T["CLAM_LOOKS"][SH2]["targets"].update(saved_t)
check("K6.table_restored", T["look_table_problems"]() == [])
L = look_live(MA2)
L["breath"][MI(MA2)]["BreathAmp"] = 0.0
check("K6.breath_change_allowed_by_arg(+)", LP(MA2, crec, L, {"allow_breath_change": True})["breath"]["new"]["BreathAmp"] == 0.0)
L = look_live(SH2)
L["actors"]["Bottom"]["wpo_eval"] = False
check("K6.shell_ignores_wpo_flag(+, not breathing)", LP(SH2, crec, L)["targets"][0]["part"] == "Bottom")
ok, msg = refuses(lambda: LP(SH2, dict(crec, applied=False), look_live(SH2)), "CLAM_RECORD_NOT_APPLIED")
check("K6.unapplied_clam_record_refused(-)", ok, msg)
# K7. ops round trip, drift, wrong slot, tampered record
for k in LOOKS:
    pl_ = plans[k]
    w0 = {t["object_path"]: copy.deepcopy(t["before"]) for t in pl_["targets"]}
    w1 = T["clam_look_simulate"](w0, T["clam_look_swap_ops"](pl_))
    live1 = {t["part"]: dict(w1[t["object_path"]], count=1) for t in pl_["targets"]}
    check("K7.swap_effect(+)|" + k, T["clam_look_state_problems"](live1, pl_["targets"], "after") == [],
          T["clam_look_state_problems"](live1, pl_["targets"], "after"))
    check("K7.swapped_differs_from_before(-)|" + k, bool(T["clam_look_state_problems"](live1, pl_["targets"], "before")))
    rec_ = {"plan": json.loads(json.dumps(pl_))}
    w2 = T["clam_look_simulate"](w1, T["clam_look_unswap_ops"](rec_))
    check("K7.unswap_exact(+)|" + k, w2 == w0, json.dumps(w2)[:300])
pl_ = plans[SH2]
w0 = {t["object_path"]: copy.deepcopy(t["before"]) for t in pl_["targets"]}
w1 = T["clam_look_simulate"](w0, T["clam_look_swap_ops"](pl_))
drift = {t["part"]: dict(copy.deepcopy(w1[t["object_path"]]), count=1) for t in pl_["targets"]}
drift["Lid"]["materials"][0] = drift["Lid"]["override_materials"][0] = "/Game/Someone/MI_Else"
check("K7.unswap_with_material_drift_refused(-)", any(x.startswith("Lid|MATERIALS") for x in
                                                      T["clam_look_state_problems"](drift, pl_["targets"], "after")))
drift = {t["part"]: dict(copy.deepcopy(w1[t["object_path"]]), count=1) for t in pl_["targets"]}
drift["Bottom"]["hidden"] = False
check("K7.unswap_with_flag_drift_refused(-)", any(x.startswith("Bottom|HIDDEN") for x in
                                                  T["clam_look_state_problems"](drift, pl_["targets"], "after")))
check("K7.missing_actor_refused(-)", any(x.startswith("COUNT|Lid") for x in
                                         T["clam_look_state_problems"]({"Bottom": drift["Bottom"]}, pl_["targets"], "after")))
bad_ops = T["clam_look_swap_ops"](pl_)
bad_ops[0]["slot"] = 1                                             # a swap applied to the WRONG slot (interior)
wb = T["clam_look_simulate"](w0, bad_ops)
lb = {t["part"]: dict(wb[t["object_path"]], count=1) for t in pl_["targets"]}
check("K7.wrong_slot_swap_caught_by_readback(-)", any(x.startswith("Bottom|MATERIALS") for x in
                                                      T["clam_look_state_problems"](lb, pl_["targets"], "after")))
bad = {"plan": json.loads(json.dumps(pl_))}
bad["plan"]["targets"][0]["before"]["materials"][0] = "/Game/Other/MI_X"
ok, msg = refuses(lambda: T["clam_look_unswap_ops"](bad), "UNSWAP_OVERRIDE")
check("K7.tampered_before_refused(-)", ok, msg)
bad = {"plan": json.loads(json.dumps(pl_))}
bad["plan"]["targets"][1]["object_path"] = "PersistentLevel.SomeoneElse"
ok, msg = refuses(lambda: T["clam_look_simulate"](w1, T["clam_look_unswap_ops"](bad)), "SIM_LOOK_TARGET")
check("K7.foreign_target_refused(-)", ok, msg)
# K8. connected-property read-back gate (pure)
PRB = T["prop_readback_problems"]


def rb_rows(spec, made):
    out = {}
    for s0, o, prop in spec["props"]:
        kind, v0 = spec["nodes"][s0]
        out[prop] = {"path": made[s0], "output": o if o != "RGB" else "", "class": "MaterialExpressionCustom" if kind == "custom"
                     else "MaterialExpressionX", "param": s0 if kind in ("scalar", "vector", "texture") else None,
                     "code": v0[0] if kind == "custom" else None}
    return out


for path in (T["PEARL_V3_MASTER"], T["SHELL_V2_MASTER"], T["MANTLE_V2_MASTER"]):
    s0 = specs[path]
    made = {k: "/Fake.%s" % k for k in s0["nodes"]}
    nm0 = path.rsplit("/", 1)[1]
    check("K8.readback_clean(+)|" + nm0, PRB(rb_rows(s0, made), s0, made) == [] and PRB(rb_rows(s0, made), s0) == [])
    r = rb_rows(s0, made)
    r["MP_OPACITY" if "MP_OPACITY" in r else "MP_SPECULAR"]["path"] = "/Fake.Other"
    check("K8.readback_wrong_node(-)|" + nm0, any(x.startswith("PROP_NODE") for x in PRB(r, s0, made)), PRB(r, s0, made))
    r = rb_rows(s0, made)
    r["MP_ROUGHNESS"]["path"] = None
    check("K8.readback_unconnected(-)|" + nm0, "PROP_UNCONNECTED|MP_ROUGHNESS" in PRB(r, s0, made))
    none = {p[2]: {"path": None} for p in s0["props"]}
    check("K8.readback_unavailable_refused(-)|" + nm0, PRB(none, s0, made)[0].startswith("PROP_READBACK_UNAVAILABLE") and
          PRB(none, s0, made, True) == [])
r = rb_rows(SMA, {k: "/Fake.%s" % k for k in SMA["nodes"]})
r["MP_ROUGHNESS"]["code"] = "return 0.5;"
check("K8.custom_code_mismatch(-)", any(x.startswith("PROP_CUSTOM") for x in PRB(r, SMA)))
r = rb_rows(SMA, {k: "/Fake.%s" % k for k in SMA["nodes"]})
r["MP_OPACITY"]["param"] = "Specular"
check("K8.param_mismatch(-)", any(x.startswith("PROP_PARAM|MP_OPACITY") for x in PRB(r, SMA)))
r = rb_rows(SMA, {k: "/Fake.%s" % k for k in SMA["nodes"]})
r["MP_NORMAL"]["output"] = "R"
check("K8.texture_output_mismatch(-)", any(x.startswith("PROP_OUTPUT|MP_NORMAL") for x in PRB(r, SMA)))
# K10. compile-log scan for the new names; our new markers ignored
CL = T["compile_log_problems"]
for k in LOOKS:
    names = [T["CLAM_EXTRA_MATERIALS"][k]["master"].rsplit("/", 1)[1], T["CLAM_EXTRA_MATERIALS"][k]["mi"]]
    ln = "LogMaterial: Warning: Failed to compile Material %s.%s for platform PCD3D_SM6\n" % (
        T["CLAM_EXTRA_MATERIALS"][k]["master"], names[0])
    check("K10.named_failure_caught(-)|" + k, CL([ln], names)[0] != [])
    check("K10.own_markers_ignored(+)|" + k, CL(["LogPython: S3CLAMLOOK_SWAP_OK|run=x|mi=%s error\n" % names[1]], names) == ([], []))


# K9. BUILD_MAT end to end against a FAKE editor (create-only gate, shading model, every node kind incl. WorldPosition,
#     subsurface pins, property read-back, inherited breath, census-exact save).  Proves the glue's logic, not UE.
class _FObj:
    def __init__(self, path=None, cls="Object"):
        self.path, self.cls, self.props = path, cls, {}

    def get_path_name(self):
        return self.path + "." + self.path.rsplit("/", 1)[1] if self.path and "/" in self.path else str(self.path)

    def get_class(self):
        return _Obj(get_name=lambda: self.cls)

    def set_editor_property(self, k, v):
        self.props[k] = v

    def get_editor_property(self, k):
        if k not in self.props:
            raise AttributeError(k)
        return self.props[k]

    def modify(self):
        pass


class FakeEd:
    def __init__(self, existing=(), fail_prop=None, readback="exact", breath_src=None):
        fe = self
        self.assets, self.dirty, self.saved, self.mats = set(existing), set(), [], {}
        self.fail_prop, self.readback = fail_prop, readback
        self.breath_src = breath_src or {"BreathAmp": 0.35, "BreathPeriod": 6.0}
        names = lambda *ns: _Obj(**{n: n for n in ns})  # noqa: E731
        self.MaterialShadingModel = names("MSM_DEFAULT_LIT", "MSM_SUBSURFACE")
        self.BlendMode = names("BLEND_OPAQUE")
        self.MaterialSamplerType = names("SAMPLERTYPE_COLOR", "SAMPLERTYPE_NORMAL", "SAMPLERTYPE_MASKS")
        self.CustomMaterialOutputType = names("CMOT_FLOAT1", "CMOT_FLOAT3")
        self.MaterialProperty = names(*sorted({p[2] for s in specs.values() for p in s["props"]}))

        def mk(nm, base=_FObj):
            return type(nm, (base,), {})
        self.Material = mk("Material")
        self.MaterialInstanceConstant = mk("MaterialInstanceConstant")
        self.Texture2D = mk("Texture2D")
        for nm in ("TextureSampleParameter2D", "ScalarParameter", "VectorParameter", "Time", "VertexColor", "WorldPosition",
                   "Fresnel", "Custom"):
            setattr(self, "MaterialExpression" + nm, mk("MaterialExpression" + nm))
        self.MaterialFactoryNew = self.MaterialInstanceConstantFactoryNew = lambda: None
        self.CustomInput = lambda: _FObj("ci")
        self.LinearColor = lambda r, g, b, a: _Obj(r=r, g=g, b=b, a=a)

        def create_asset(name, folder, cls, _f):
            path = folder + "/" + name
            o = cls(path, cls.__name__)
            o.nodes, o.links, o.mprops, o.parent_, o.sc, o.vc, o.tx = [], [], {}, None, {}, {}, {}
            fe.assets.add(path)
            fe.dirty.add(path)
            fe.mats[path] = o
            return o
        self.AssetToolsHelpers = _Obj(get_asset_tools=lambda: _Obj(create_asset=create_asset))
        self.EditorAssetLibrary = _Obj(does_asset_exist=lambda p: p in fe.assets,
                                       save_asset=lambda p, only_if_is_dirty=False: (fe.saved.append(p), fe.dirty.discard(p), True)[2])
        pk = lambda n: _Obj(get_name=lambda: n)  # noqa: E731
        self.EditorLoadingAndSavingUtils = _Obj(get_dirty_content_packages=lambda: [pk(n) for n in sorted(fe.dirty)],
                                                get_dirty_map_packages=lambda: [])
        self.SystemLibrary = _Obj(collect_garbage=lambda: None)

        def load_asset(p):
            if p in fe.mats:
                return fe.mats[p]
            if "/T_PearlClam_" in p:
                t = fe.Texture2D(p, "Texture2D")
                lab = p.rsplit("/T_PearlClam_", 1)[1]
                tex_set, suffix = lab.split("_", 1)
                role = {"BaseColor": "BaseColor", "N": "N", "Roughness": "Roughness", "Nacre": "Nacre"}[suffix]
                t.props.update(compression_settings=T["ROLE_SPEC"][role][1], srgb=T["ROLE_SPEC"][role][2])
                d = T["CLAM_TEX"][tex_set][role]
                t.blueprint_get_size_x = t.blueprint_get_size_y = lambda d=d: d
                return t
            if p in (MI(T["PEARL_V2"]), MI("Mantle")):
                o = _FObj(p, "MaterialInstanceConstant")
                o.sc = dict(fe.breath_src)
                return o
            return None
        self.load_asset = load_asset

        def cme(mat, cls, x, y):
            n = cls("%s:%s_%d" % (mat.path, cls.__name__, len(mat.nodes)), cls.__name__)
            mat.nodes.append(n)
            return n

        def params(mat, cls):
            return [n.props["parameter_name"] for n in mat.nodes if n.cls == cls]

        def cmp_(node, o, mp):
            if mp == fe.fail_prop:
                return False
            mat = fe.mats[node.path.split(":")[0]]
            mat.mprops[mp] = (node, o)
            return True

        def in_node(mat, mp):
            if fe.readback == "none":
                return None
            n = mat.mprops.get(mp, (None, ""))[0]
            if fe.readback == "wrong" and mp == "MP_OPACITY":
                return mat.nodes[0]
            return n

        def mi_scalar(mi, k):
            if k in mi.sc:
                return mi.sc[k]
            par = mi.parent_
            return [n.props["default_value"] for n in par.nodes if n.cls == "MaterialExpressionScalarParameter"
                    and n.props["parameter_name"] == k][0]

        def mi_vector(mi, k):
            if k in mi.vc:
                return mi.vc[k]
            return [n.props["default_value"] for n in mi.parent_.nodes if n.cls == "MaterialExpressionVectorParameter"
                    and n.props["parameter_name"] == k][0]

        def set_parent(mi, mat):
            mi.parent_ = mat
            mi.props["parent"] = mat
        self.MaterialEditingLibrary = _Obj(
            create_material_expression=cme,
            connect_material_expressions=lambda a, o, b, pin: (fe.mats[a.path.split(":")[0]].links.append((a, o, b, pin)), True)[1],
            connect_material_property=cmp_, recompile_material=lambda m: None,
            get_material_property_input_node=in_node,
            get_material_property_input_node_output_name=lambda mat, mp: "" if mat.mprops.get(mp, (0, ""))[1] == "RGB"
            else mat.mprops.get(mp, (0, ""))[1],
            get_texture_parameter_names=lambda m: params(m, "MaterialExpressionTextureSampleParameter2D"),
            get_scalar_parameter_names=lambda m: params(m, "MaterialExpressionScalarParameter"),
            get_vector_parameter_names=lambda m: params(m, "MaterialExpressionVectorParameter"),
            set_material_instance_parent=set_parent,
            set_material_instance_texture_parameter_value=lambda mi, k, t: mi.tx.__setitem__(k, t),
            set_material_instance_scalar_parameter_value=lambda mi, k, v: mi.sc.__setitem__(k, v),
            set_material_instance_vector_parameter_value=lambda mi, k, v: mi.vc.__setitem__(k, v),
            update_material_instance=lambda mi: None,
            get_material_instance_texture_parameter_value=lambda mi, k: mi.tx.get(k),
            get_material_instance_scalar_parameter_value=mi_scalar,
            get_material_instance_vector_parameter_value=mi_vector)


def fake_build(key, args=None, **kw):
    tmpb = tempfile.mkdtemp(prefix="s3look_")
    fe = FakeEd(**kw)
    keep = {k: G[k] for k in ("unreal", "HERE")}
    G.update(unreal=fe, HERE=tmpb + "/")
    try:
        try:
            return fe, T["run_build_clam_mat"]("RUNB", key, args or {}), None
        except PlanError as exc:
            return fe, None, str(exc)
    finally:
        G.update(keep)


for k in LOOKS:
    m_ = T["CLAM_EXTRA_MATERIALS"][k]
    s0 = specs[m_["master"]]
    fe, rec_, err = fake_build(k, breath_src={"BreathAmp": 0.8, "BreathPeriod": 6.0})
    mat = fe.mats.get(m_["master"])
    ok = rec_ is not None and mat is not None
    check("K9.build_ok(+)|" + k, ok and sorted(fe.saved) == sorted([m_["master"], MI(k)]) and not fe.dirty, err or fe.saved)
    if not ok:
        continue
    kinds = sorted(n.cls for n in mat.nodes)
    check("K9.node_count_and_kinds|" + k, len(mat.nodes) == len(s0["nodes"]) and
          (("MaterialExpressionWorldPosition" in kinds) == (k == MA2)), kinds)
    check("K9.shading_model_set|" + k, mat.props["shading_model"] == s0["shading_model"])
    check("K9.props_connected|" + k, sorted(mat.mprops) == sorted(s0["want_props"]), sorted(mat.mprops))
    check("K9.links_count|" + k, len(mat.links) == len(s0["edges"]))
    want_b = {"BreathAmp": 0.8, "BreathPeriod": 6.0} if m_["breath_from"] else {}
    check("K9.mi_breath_inherited_and_read_back|" + k, all(abs(rec_["scalars"][q] - want_b[q]) < 1e-9 for q in want_b) and
          rec_["breath_inherited"] == (want_b or None) and rec_["shading_model"] == s0["shading_model"] and
          (k != P3 or rec_["scalars"]["Glow"] == 0.1), rec_)
for nm, kw, args_, needle in (
        ("master_exists", {"existing": [T["PEARL_V3_MASTER"]]}, None, "LOOK_MASTER_EXISTS"),
        ("mi_exists", {"existing": [MI(SH2)]}, None, "MI_EXISTS"),
        ("connect_subsurface_false", {"fail_prop": "MP_SUBSURFACE_COLOR"}, None, "PROP|MP_SUBSURFACE_COLOR"),
        ("connect_opacity_false", {"fail_prop": "MP_OPACITY"}, None, "PROP|MP_OPACITY"),
        ("readback_wrong_node", {"readback": "wrong"}, None, "PROP_READBACK"),
        ("readback_unavailable", {"readback": "none"}, None, "PROP_READBACK_UNAVAILABLE"),
        ("breath_source_out_of_range", {"breath_src": {"BreathAmp": 7.0, "BreathPeriod": 6.0}}, None, "BREATH_SOURCE_RANGE")):
    key = SH2 if nm == "mi_exists" else (MA2 if "opacity" in nm or "range" in nm else P3)
    fe, rec_, err = fake_build(key, args_, **kw)
    check("K9.%s_refused_nothing_saved(-)" % nm, rec_ is None and err and needle in err and fe.saved == [], (err, fe.saved))
fe, rec_, err = fake_build(SH2, {"allow_prop_readback_unavailable": True}, readback="none")
check("K9.readback_unavailable_allowed_by_arg(+)", rec_ is not None and sorted(fe.saved) == sorted([T["SHELL_V2_MASTER"], MI(SH2)]), err)

# ================================================================== L. pearl fade twin (8 Oct): Pearl_Fade / Pearl_Dither + twin
PF, PD = T["PEARL_FADE"], T["PEARL_DITHER"]
SPF, SPD = specs[T["PEARL_FADE_MASTER"]], specs[T["PEARL_DITHER_MASTER"]]
# L1. tables + lint
check("L1.twin_specs_clean(+)", not any(k in mp for k in (T["PEARL_FADE_MASTER"], T["PEARL_DITHER_MASTER"], PF, PD)), mp)
check("L1.twin_table_clean(+)", T["twin_table_problems"]() == [], T["twin_table_problems"]())
check("L1.looks_untouched", T["CLAM_LOOK_MATERIALS"] == (P3, SH2, MA2) and
      sorted(T["CLAM_LOOKS"]) == sorted(LOOKS + (T["PEARL_V3_GO"],)) and                    # + the 8 Oct MI-only look (M.)
      T["CLAM_MAT_CHECK_MATERIALS"] == (P3, SH2, MA2, PF, PD, T["PEARL_V3_GO"]))
check("L1.blend_shading_tlm", SPF["blend_mode"] == "BLEND_TRANSLUCENT" and SPF["shading_model"] == "MSM_DEFAULT_LIT" and
      SPF["translucency_lighting_mode"] == "TLM_SURFACE_PER_PIXEL_LIGHTING" and SPD["blend_mode"] == "BLEND_MASKED" and
      SPD["shading_model"] == "MSM_SUBSURFACE" and "translucency_lighting_mode" not in SPD and "blend_mode" not in SP3)
check("L1.twin_masters_not_nanite_usage", SPF["used_with_nanite"] is False and SPD["used_with_nanite"] is False)
check("L1.new_assets_only", {T["PEARL_FADE_MASTER"], T["PEARL_DITHER_MASTER"]}.isdisjoint(old_masters | {
    T["PEARL_V3_MASTER"], T["SHELL_V2_MASTER"], T["MANTLE_V2_MASTER"]}) and
      len({T["CLAM_EXTRA_MATERIALS"][k]["mi"] for k in (PF, PD)} | {r["mi"] for r in rows_.values()}) == 5)
# L2. v3 identity of the shared pieces (both twins are built FROM the v3 spec)
for nm, s_, extra_nodes in (("dither", SPD, {"Fade", "FadeDither", "GlowFade"}),
                            ("fade", SPF, {"Fade", "BaseOpacity", "FadeBase", "FadeOpacity", "GlowFade"})):
    check("L2.%s_every_v3_node_unchanged(+)" % nm, all(s_["nodes"].get(k) == v for k, v in SP3["nodes"].items()) and
          set(s_["nodes"]) - set(SP3["nodes"]) == extra_nodes, sorted(set(s_["nodes"]) - set(SP3["nodes"])))
    check("L2.%s_every_v3_edge_present(+)" % nm, set(SP3["edges"]) <= set(s_["edges"]) and
          all(e[2] in extra_nodes for e in set(s_["edges"]) - set(SP3["edges"])), sorted(set(s_["edges"]) - set(SP3["edges"])))
    check("L2.%s_breath_wpo_identical_to_v3_and_v2(+)" % nm, sub(s_, "PearlWPO") == sub(SP3, "PearlWPO") == sub(SV2, "PearlWPO")
          and ("PearlWPO", "", "MP_WORLD_POSITION_OFFSET") in s_["props"] and s_["max_wpo"] == SP3["max_wpo"])
    check("L2.%s_v3_params_and_defaults(+)" % nm, all(s_["scalars"][k] == v for k, v in SP3["scalars"].items()) and
          s_["vectors"] == SP3["vectors"] and s_["tex_params"] == SP3["tex_params"] and s_["scalars"]["Fade"] == 1.0)
    check("L2.%s_glow_subgraph_is_v3(+)" % nm, sub(s_, "InnerGlow") == sub(SP3, "InnerGlow") and
          ("GlowFade", "", "MP_EMISSIVE_COLOR") in s_["props"] and ("InnerGlow", "", "GlowFade", "E") in s_["edges"] and
          ("Fade", "", "GlowFade", "F") in s_["edges"])
pd3 = {p[2]: p for p in SP3["props"]}
pdd = {p[2]: p for p in SPD["props"]}
check("L2.dither_props_v3_except_emissive_plus_mask(+)", {k for k in pd3 if pd3[k] != pdd.get(k)} == {"MP_EMISSIVE_COLOR"} and
      set(pdd) - set(pd3) == {"MP_OPACITY_MASK"} and pdd["MP_OPACITY_MASK"] == ("FadeDither", "", "MP_OPACITY_MASK") and
      pdd["MP_OPACITY"] == ("SubsurfaceAmount", "", "MP_OPACITY") and ("Fade", "", "FadeDither", "F") in SPD["edges"], pdd)
pdf = {p[2]: p for p in SPF["props"]}
check("L2.fade_props(+)", {k for k in pd3 if pd3[k] == pdf.get(k)} == {"MP_ROUGHNESS", "MP_SPECULAR", "MP_WORLD_POSITION_OFFSET"}
      and "MP_SUBSURFACE_COLOR" not in pdf and pdf["MP_BASE_COLOR"][0] == "FadeBase" and pdf["MP_OPACITY"][0] == "FadeOpacity" and
      {("IridSurface", "", "FadeBase", "S"), ("IridSubsurface", "", "FadeBase", "U"), ("SubsurfaceAmount", "", "FadeBase", "K"),
       ("Fade", "", "FadeOpacity", "F"), ("BaseOpacity", "", "FadeOpacity", "O")} <= set(SPF["edges"]), pdf)
check("L2.fade_base_uses_v3_subgraphs(+)", sub(SPF, "IridSurface") == sub(SP3, "IridSurface") and
      sub(SPF, "IridSubsurface") == sub(SP3, "IridSubsurface"))
check("L2.v3_spec_not_mutated_by_twin_build", T["material_specs"]()[T["PEARL_V3_MASTER"]] == SP3 and
      "Fade" not in SP3["nodes"] and ("InnerGlow", "", "MP_EMISSIVE_COLOR") in SP3["props"])
check("L2.fade_wiring_reaches_opacity_and_emissive(+)", T["fade_wiring_problems"](SPF) == [] and T["fade_wiring_problems"](SPD) == [])
# L3. lint negatives
for nm, path, fn, needle in (
        ("opacity_on_opaque_defaultlit", T["SHELL_V2_MASTER"], lambda s: (s["props"].append(("Specular", "", "MP_OPACITY")),
                                                                          s["want_props"].add("MP_OPACITY")), "OPACITY_NOT_TRANSPARENCY"),
        ("mask_on_translucent", T["PEARL_FADE_MASTER"], lambda s: (s["props"].append(("Fade", "", "MP_OPACITY_MASK")),
                                                                   s["want_props"].add("MP_OPACITY_MASK")), "OPACITY_MASK_BLEND"),
        ("mask_on_opaque_v3", T["PEARL_V3_MASTER"], lambda s: (s["props"].append(("Glow", "", "MP_OPACITY_MASK")),
                                                               s["want_props"].add("MP_OPACITY_MASK")), "OPACITY_MASK_BLEND"),
        ("masked_without_mask", T["PEARL_DITHER_MASTER"], lambda s: (s.update(props=[p for p in s["props"] if p[2] != "MP_OPACITY_MASK"]),
                                                                    s["want_props"].discard("MP_OPACITY_MASK")), "OPACITY_MASK_BLEND"),
        ("subsurface_on_translucent", T["PEARL_FADE_MASTER"], lambda s: s.update(shading_model="MSM_SUBSURFACE"),
         "TRANSLUCENT_SUBSURFACE"),
        ("subsurface_pin_on_translucent", T["PEARL_FADE_MASTER"], lambda s: (s["props"].append(("IridSubsurface", "", "MP_SUBSURFACE_COLOR")),
                                                                            s["want_props"].add("MP_SUBSURFACE_COLOR")), "TRANSLUCENT_SUBSURFACE"),
        ("translucent_without_opacity", T["PEARL_FADE_MASTER"], lambda s: (s.update(props=[p for p in s["props"] if p[2] != "MP_OPACITY"]),
                                                                          s["want_props"].discard("MP_OPACITY")), "TRANSLUCENT_NO_OPACITY"),
        ("bad_tlm", T["PEARL_FADE_MASTER"], lambda s: s.update(translucency_lighting_mode="TLM_FORWARD"), "TLM|"),
        ("tlm_on_masked", T["PEARL_DITHER_MASTER"], lambda s: s.update(translucency_lighting_mode="TLM_SURFACE"), "TLM_ON_NON_TRANSLUCENT"),
        ("bad_blend", T["PEARL_DITHER_MASTER"], lambda s: s.update(blend_mode="BLEND_ADDITIVE"), "BLEND_MODE|"),
        ("fade_default_zero", T["PEARL_FADE_MASTER"], lambda s: (s["nodes"].update(Fade=("scalar", 0.0)), s["scalars"].update(Fade=0.0)),
         "FADE_DEFAULT"),
        ("dither_fade_pin_unfed", T["PEARL_DITHER_MASTER"], lambda s: s.update(edges=[e for e in s["edges"] if e != ("Fade", "", "FadeDither", "F")]),
         "CUSTOM_PIN_UNFED|FadeDither.F"),
        ("dither_fade_not_wired", T["PEARL_DITHER_MASTER"], lambda s: s.update(edges=[e for e in s["edges"] if e != ("Fade", "", "FadeDither", "F")]),
         "FADE_NOT_WIRED|MP_OPACITY_MASK"),
        ("fade_opacity_pin_unfed", T["PEARL_FADE_MASTER"], lambda s: s.update(edges=[e for e in s["edges"] if e != ("Fade", "", "FadeOpacity", "F")]),
         "CUSTOM_PIN_UNFED|FadeOpacity.F"),
        ("glow_fade_pin_unfed", T["PEARL_FADE_MASTER"], lambda s: s.update(edges=[e for e in s["edges"] if e != ("Fade", "", "GlowFade", "F")]),
         "FADE_NOT_WIRED|MP_EMISSIVE_COLOR"),
        ("emissive_bypasses_fade", T["PEARL_DITHER_MASTER"], lambda s: s.update(props=[("InnerGlow", "", p) if p == "MP_EMISSIVE_COLOR" else (a_, o, p)
                                                                                     for a_, o, p in s["props"]]), "FADE_NOT_WIRED|MP_EMISSIVE_COLOR")):
    b = copy.deepcopy(specs)
    fn(b[path])
    got = T["material_problems"](b).get(path, [])
    check("L3.%s_detected(-)" % nm, any(needle in x for x in got), got)
check("L3.v3_subsurface_on_defaultlit_still_caught(-)", any("SUBSURFACE_PINS" in x for x in
                                                            T["material_problems"]({**specs, T["PEARL_V3_MASTER"]: dict(SP3, shading_model="MSM_DEFAULT_LIT")})
                                                            .get(T["PEARL_V3_MASTER"], [])))
# L4. Python mirrors: dither coverage == Fade (any clip in (0,1]), temporal averaging, translucent opacity, glow x Fade
DE = T["dither_eval"]
W_ = 96
cov = lambda f, fr=0: sum(DE(f, x, y, fr) for x in range(W_) for y in range(W_)) / float(W_ * W_)  # noqa: E731
covs = {f: cov(f) for f in (0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0)}
check("L4.dither_endpoints_exact(+)", covs[0.0] == 0.0 and covs[1.0] == 1.0, covs)
check("L4.dither_coverage_tracks_fade(+)", all(abs(covs[f] - f) < 0.03 for f in covs), covs)
check("L4.dither_monotone(+)", all(DE(0.3, x, y, 5) <= DE(0.6, x, y, 5) for x in range(40) for y in range(40)))
tmean = [sum(DE(0.5, x, y, fr) for fr in range(64)) / 64.0 for x in range(24) for y in range(24)]
check("L4.dither_temporal_mean_per_pixel_near_fade", max(abs(t - 0.5) for t in tmean) < 0.2 and
      abs(sum(tmean) / len(tmean) - 0.5) < 0.03, (min(tmean), max(tmean)))
check("L4.dither_pattern_moves_per_frame", any(DE(0.5, x, 3, 0) != DE(0.5, x, 3, 1) for x in range(64)))
check("L4.dither_custom_reads_documented_inputs", "Parameters.SvPosition" in T["DITHER_CODE"] and
      "View.StateFrameIndex" in T["DITHER_CODE"] and "? 1.0 : 0.0" in T["DITHER_CODE"])
check("L4.fade_opacity", T["fade_opacity_eval"](1.0, 1.0) == 1.0 and T["fade_opacity_eval"](0.0, 1.0) == 0.0 and
      T["fade_opacity_eval"](0.5, 0.8) == 0.4 and T["fade_opacity_eval"](1.7, 1.0) == 1.0)
check("L4.glow_fades_with_pearl", T["glow_fade_eval"]([2.0, 1.0, 0.5], 0.0) == [0.0, 0.0, 0.0] and
      T["glow_fade_eval"]([2.0, 1.0, 0.5], 1.0) == [2.0, 1.0, 0.5])
fb = T["fade_base_eval"]
check("L4.fade_base_blend", fb([0.9, 0.87, 0.82], [0.6, 0.9, 0.7], 0.0) == [0.9, 0.87, 0.82] and
      fb([0.9, 0.87, 0.82], [0.6, 0.9, 0.7], 1.0) == [0.6, 0.9, 0.7])
# L5. copy-from-live plan: the values the owning session measured on MI_PearlClam_Pearl_v3 (build record + breath 1.5/6)
v3b = json.load(open(T["HERE"] + "s3_props_build_mat_PearlClam_Pearl_v3.json", encoding="utf-8"))
v3sw = json.load(open(T["look_record_path"](P3), encoding="utf-8"))
check("L5.live_v3_records(measured by the owning session)", v3sw["run"] == "S3PROPS-20261007-220156" and v3sw["applied"] and
      v3b["scalars"]["BreathAmp"] == 1.5 and v3b["scalars"]["BreathPeriod"] == 6.0, (v3sw["run"], v3b["scalars"].get("BreathAmp")))
NACRE = T["tex_target"]("PearlClam", "Pearl", "Nacre")["asset"]
v3_live = {"mi": MI(P3), "parent": T["PEARL_V3_MASTER"], "scalars": dict(v3b["scalars"], Glow=0.42),     # Glow tuned live
           "vectors": dict(v3b["vectors"], GlowColor=[1.0, 0.8, 0.7, 1.0]), "textures": {"Nacre": NACRE}}
LCV = T["look_copy_values"]
for k in (PF, PD):
    cp = LCV(k, copy.deepcopy(v3_live))
    new = T["CLAM_EXTRA_MATERIALS"][k]["scalars"]
    check("L5.copy_every_v3_value(+)|" + k, all(cp["scalars"][q] == float(v) for q, v in v3_live["scalars"].items()) and
          cp["vectors"] == v3_live["vectors"] and {q: cp["scalars"][q] for q in new} == new and cp["scalars"]["Fade"] == 1.0 and
          set(cp["scalars"]) == set(specs[T["CLAM_EXTRA_MATERIALS"][k]["master"]]["scalars"]), cp["scalars"])
check("L5.fade_has_base_opacity_1", LCV(PF, copy.deepcopy(v3_live))["scalars"]["BaseOpacity"] == 1.0)
for nm, fn, needle in (
        ("wrong_parent", lambda s: s.update(parent=T["PEARL_V2_MASTER"]), "COPY_SOURCE_PARENT"),
        ("scalar_unread", lambda s: s["scalars"].pop("GlowIrid"), "COPY_SCALARS_UNREAD"),
        ("vector_unread", lambda s: s["vectors"].pop("PaletteD"), "COPY_VECTORS_UNREAD"),
        ("nan", lambda s: s["scalars"].update(Glow=float("nan")), "COPY_SCALAR_VALUE"),
        ("texture_differs", lambda s: s["textures"].update(Nacre="/Game/X/T_Other"), "COPY_TEXTURE_DIFFERS"),
        ("breath_range", lambda s: s["scalars"].update(BreathAmp=9.0), "BREATH_SOURCE_RANGE"),
        ("wrong_source", lambda s: s.update(mi=MI(T["PEARL_V2"])), "COPY_SOURCE|")):
    src_ = copy.deepcopy(v3_live)
    fn(src_)
    ok, msg = refuses(lambda src_=src_: LCV(PD, src_), needle)
    check("L5.copy_%s_refused(-)" % nm, ok, msg)
saved_row = copy.deepcopy(T["CLAM_EXTRA_MATERIALS"][PF])
T["CLAM_EXTRA_MATERIALS"][PF]["scalars"]["Glow"] = 0.0
try:
    ok, msg = refuses(lambda: LCV(PF, copy.deepcopy(v3_live)), "COPY_ROW_OVERRIDES")
    check("L5.row_overriding_a_copied_value_refused(-)", ok and any("TWIN_NEW_SCALARS" in x for x in T["twin_table_problems"]()), msg)
finally:
    T["CLAM_EXTRA_MATERIALS"][PF].clear()
    T["CLAM_EXTRA_MATERIALS"][PF].update(saved_row)
check("L5.table_restored", T["twin_table_problems"]() == [])
# L6. mode gates
TW = lambda mode, **k: dict({"mode": mode, "confirm": "%s S3PROPS" % mode}, **k)  # noqa: E731
for k in (PF, PD):
    check("L6.build_mat_ok(+)|" + k, CM({"mode": "BUILD_MAT", "confirm": "BUILD_MAT S3PROPS", "prop": "PearlClam", "material": k},
                                        True, False, False, True) == "BUILD_MAT")
    check("L6.mat_check_ok(+)|" + k, CM({"mode": "CLAM_LOOK_MAT_CHECK", "material": k}, True, False) == "CLAM_LOOK_MAT_CHECK")
check("L6.twin_ok(+)", CM(TW("CLAM_PEARL_TWIN"), True, False, False, True, True, [P3]) == "CLAM_PEARL_TWIN")
check("L6.twin_dither_ok(+)", CM(TW("CLAM_PEARL_TWIN", twin={"twin_material": PD}), True, False, False, True, True, [P3]) ==
      "CLAM_PEARL_TWIN")
check("L6.set_material_ok(+)", CM(TW("CLAM_PEARL_TWIN_SET_MATERIAL", twin={"twin_material": PD}), True, False, False, True, True,
                                  [P3], True) == "CLAM_PEARL_TWIN_SET_MATERIAL")
check("L6.twin_revert_ok(+)", CM(TW("CLAM_PEARL_TWIN_REVERT"), True, False, False, True, True, [P3], True) == "CLAM_PEARL_TWIN_REVERT")
check("L6.look_unswap_v3_with_twin_ok(+)", CM(LU(look=P3), True, False, False, True, True, [P3], True) == "CLAM_LOOK_UNSWAP")
for nm, call, needle in (
        ("twin_twice", lambda: CM(TW("CLAM_PEARL_TWIN"), True, False, False, True, True, [P3], True), "TWIN_ALREADY"),
        ("twin_without_clam", lambda: CM(TW("CLAM_PEARL_TWIN"), True, False, False, False), "NO_CLAM_RECORD"),
        ("twin_bad_material", lambda: CM(TW("CLAM_PEARL_TWIN", twin={"twin_material": "Pearl_v3"}), True, False, False, True), "TWIN_MATERIAL"),
        ("twin_confirm", lambda: CM({"mode": "CLAM_PEARL_TWIN", "confirm": "CLAM_PEARL_TWIN"}, True, False, False, True), "CONFIRM_MISSING"),
        ("clam_revert_with_twin", lambda: CM(TW("CLAM_REVERT"), True, False, False, True, False, [], True), "TWIN_EXISTS"),
        ("pearl_swap_with_twin", lambda: CM(TW("PEARL_SWAP"), True, False, False, True, False, [], True), "TWIN_EXISTS"),
        ("pearl_unswap_with_twin", lambda: CM(TW("PEARL_UNSWAP"), True, False, False, True, True, [], True), "TWIN_EXISTS"),
        ("set_material_no_twin", lambda: CM(TW("CLAM_PEARL_TWIN_SET_MATERIAL"), True, False, False, True, True, [P3]), "NO_TWIN_RECORD"),
        ("revert_no_twin", lambda: CM(TW("CLAM_PEARL_TWIN_REVERT"), True, False, False, True, True, [P3]), "NO_TWIN_RECORD"),
        ("twin_while_tex_pending", lambda: CM(TW("CLAM_PEARL_TWIN"), True, False, True, True), "TEX_PENDING"),
        ("mat_check_unknown", lambda: CM({"mode": "CLAM_LOOK_MAT_CHECK", "material": "Pearl_v4"}, True, False), "LOOK_MATERIAL")):
    ok, msg = refuses(call, needle)
    check("L6.%s_refused(-)" % nm, ok, msg)
check("L6.twin_record_path_distinct", T["TWIN_RECORD"] not in {T["CLAM_RECORD"], T["PEARL_SWAP_RECORD"]} |
      {T["look_record_path"](k) for k in LOOKS})
# L7. twin plan against the REAL clam apply record + the live pearl as the v3 swap read it back
pearl_live = dict(copy.deepcopy(v3sw["after_readback"]["Pearl"]) if "after_readback" in v3sw and "Pearl" in v3sw["after_readback"]
                  else copy.deepcopy(v3sw["plan"]["targets"][0]["after"]),
                  count=1, folder="RigAtmos/S3Props/PearlClam", tags=["RigAtmos.S3Props"], mobility="MOVABLE",
                  cast_shadow=True, disallow_nanite=False)
check("L7.live_pearl_is_v2_mesh_v3_mi(measured)", pearl_live["mesh"] == T["clam_mesh_path"](T["PEARL_V2"]) and
      pearl_live["materials"] == [MI(P3)] and pearl_live["object_path"] == crec["actor_paths"]["Pearl"], pearl_live["materials"])
GLOW0 = {"count": 1, "parent_path": crec["actor_paths"]["Pearl"]}


def twin_live(**over):
    L = {"pearl": copy.deepcopy(pearl_live), "root": {"count": 1, "object_path": crec["actor_paths"]["Bottom"]}, "twins": [],
         "glow": dict(GLOW0), "assets": {p: True for k in (PF, PD) for p in (MI(k), T["CLAM_EXTRA_MATERIALS"][k]["master"])},
         "breath": {MI(P3): {"BreathAmp": 1.5, "BreathPeriod": 6.0}, MI(PF): {"BreathAmp": 1.5, "BreathPeriod": 6.0},
                    MI(PD): {"BreathAmp": 1.5, "BreathPeriod": 6.0}}}
    L.update(over)
    return L


TP = T["twin_plan"]
tp = TP(crec, twin_live())
ex = tp["expect"]
check("L7.twin_plan_ok(+)", ex["label"] == "S3 PearlClam Pearl Fade" and ex["tags"] == ["S3PearlFadeTwin"] and
      ex["materials"] == [MI(PF)] and ex["mesh"] == pearl_live["mesh"] and ex["parent_path"] == crec["actor_paths"]["Bottom"] and
      ex["hidden"] is True and ex["mobility"] == "MOVABLE" and ex["disallow_nanite"] is True and ex["cast_shadow"] is False and
      ex["folder"] == pearl_live["folder"], ex)
check("L7.twin_rel_equals_pearl_rel(+)", ex["rel"] == pearl_live["rel"] and tp["op"]["world"] == pearl_live["world"],
      (ex["rel"], pearl_live["rel"]))
check("L7.dither_twin_casts_shadow(+)", TP(crec, twin_live(), {"twin_material": PD})["expect"]["cast_shadow"] is True and
      TP(crec, twin_live(), {"twin_material": PD, "cast_shadow": False})["expect"]["cast_shadow"] is False)
st = T["twin_simulate"](tp["op"])
check("L7.spawn_readback_clean(+)", T["twin_state_problems"](st, ex) == [], T["twin_state_problems"](st, ex))
for nm, fn, needle in (("wrong_parent", lambda s: s.update(parent_path=crec["actor_paths"]["Lid"]), "PARENT_PATH"),
                       ("rel_off", lambda s: s["rel"]["location"].__setitem__(2, s["rel"]["location"][2] + 0.2), "REL|"),
                       ("not_hidden", lambda s: s.update(hidden=False), "HIDDEN"),
                       ("nanite_unread", lambda s: s.update(disallow_nanite="UNREAD"), "DISALLOW_NANITE"),
                       ("wrong_mi", lambda s: s.update(materials=[MI(P3)]), "MATERIALS"),
                       ("untagged", lambda s: s.update(tags=[]), "TAGS")):
    s2 = copy.deepcopy(st)
    fn(s2)
    got = T["twin_state_problems"](s2, ex)
    check("L7.readback_%s_caught(-)" % nm, any(needle in x for x in got), got)
check("L7.untouched_clean(+)", T["twin_untouched_problems"](tp, copy.deepcopy(pearl_live), dict(GLOW0)) == [])
p2 = dict(copy.deepcopy(pearl_live), materials=[MI(PF)])
check("L7.pearl_touched_caught(-)", any("PEARL_TOUCHED|materials" in x for x in T["twin_untouched_problems"](tp, p2, dict(GLOW0))))
check("L7.glow_detached_caught(-)", any("GLOW_TOUCHED" in x for x in
                                        T["twin_untouched_problems"](tp, copy.deepcopy(pearl_live), {"count": 1, "parent_path": None})))
for nm, L, args_, needle in (
        ("twin_exists_live", twin_live(twins=[dict(st)]), None, "TWIN_EXISTS_LIVE"),
        ("material_not_built", twin_live(assets={MI(PD): True}), None, "TWIN_MATERIAL_MISSING"),
        ("dither_not_built", twin_live(assets={MI(PF): True, T["PEARL_FADE_MASTER"]: True}), {"twin_material": PD}, "TWIN_MATERIAL_MISSING"),
        ("pearl_wrong_parent", twin_live(pearl=dict(copy.deepcopy(pearl_live), parent_path=crec["actor_paths"]["Lid"])), None,
         "TWIN_PEARL_PARENT"),
        ("pearl_v1_mesh", twin_live(pearl=dict(copy.deepcopy(pearl_live), mesh=T["clam_mesh_path"]("Pearl"))), None, "TWIN_MESH"),
        ("pearl_missing", twin_live(pearl={"count": 0}), None, "TWIN_PEARL_COUNT"),
        ("root_wrong", twin_live(root={"count": 1, "object_path": "X"}), None, "TWIN_ROOT"),
        ("breath_mismatch", twin_live(breath={MI(P3): {"BreathAmp": 1.5, "BreathPeriod": 6.0},
                                              MI(PF): {"BreathAmp": 0.35, "BreathPeriod": 6.0}}), None, "TWIN_BREATH_MISMATCH"),
        ("breath_unread", twin_live(breath={}), None, "TWIN_BREATH_UNREAD"),
        ("bad_material_arg", twin_live(), {"twin_material": "Pearl_v3"}, "TWIN_MATERIAL|")):
    ok, msg = refuses(lambda L=L, a_=args_: TP(crec, L, a_), needle)
    check("L7.twin_%s_refused(-)" % nm, ok, msg)
ok, msg = refuses(lambda: TP(dict(crec, applied=False), twin_live()), "CLAM_RECORD_NOT_APPLIED")
check("L7.twin_unapplied_clam_refused(-)", ok, msg)
check("L7.breath_change_allowed_by_arg(+)", TP(crec, twin_live(breath={MI(P3): {"BreathAmp": 1.5, "BreathPeriod": 6.0},
                                                                     MI(PF): {"BreathAmp": 0.35, "BreathPeriod": 6.0}}),
                                               {"allow_breath_change": True})["mi"] == MI(PF))
# L8. SET_MATERIAL + REVERT plans
trec = {"applied": True, "saved": True, "object_path": st["object_path"], "expect": copy.deepcopy(ex), "pending_set": None}
SMP = T["twin_set_material_plan"]
sp = SMP(trec, twin_live(twins=[dict(st, hidden=False)]), {"twin_material": PD})       # hidden drift (sequence keys it): allowed
check("L8.set_material_ok(+)", sp["old_mi"] == MI(PF) and sp["new_mi"] == MI(PD) and sp["after"]["materials"] == [MI(PD)] and
      sp["after"]["cast_shadow"] is True and {k for k in T["TWIN_STATE_KEYS"] if sp["after"][k] != ex[k]} ==
      {"materials", "override_materials", "cast_shadow"}, sp["after"])
st_d = T["twin_simulate"](dict(sp["after"], op="spawn_twin"))
sb = SMP(dict(trec, expect=sp["after"]), twin_live(twins=[dict(st_d, object_path=st["object_path"])]), {"twin_material": PF})
check("L8.set_material_back_to_fade(+)", sb["after"] == ex, sb["after"])
for nm, rec_, L, args_, needle in (
        ("no_twin", trec, twin_live(), {"twin_material": PD}, "TWIN_MISSING"),
        ("mi_not_built", trec, twin_live(twins=[dict(st)], assets={MI(PF): True}), {"twin_material": PD}, "TWIN_MATERIAL_MISSING"),
        ("not_tagged", trec, twin_live(twins=[dict(st, tags=[])]), {"twin_material": PD}, "TWIN_NOT_TAGGED"),
        ("relabelled", trec, twin_live(twins=[dict(st, label="S3 PearlClam Pearl")]), {"twin_material": PD}, "TWIN_NOT_TAGGED"),
        ("other_actor", trec, twin_live(twins=[dict(st, object_path="PersistentLevel.Other")]), {"twin_material": PD}, "TWIN_PATH"),
        ("two_twins", trec, twin_live(twins=[dict(st), dict(st, object_path="B")]), {"twin_material": PD}, "TWIN_COUNT"),
        ("already_on", trec, twin_live(twins=[dict(st)]), {"twin_material": PF}, "TWIN_MATERIAL_ALREADY"),
        ("drift_parent", trec, twin_live(twins=[dict(st, parent_path=None)]), {"twin_material": PD}, "TWIN_DRIFT"),
        ("pending", dict(trec, pending_set={"run": "x"}), twin_live(twins=[dict(st)]), {"twin_material": PD}, "TWIN_PENDING"),
        ("breath_mismatch", trec, twin_live(twins=[dict(st)], breath={MI(PF): {"BreathAmp": 1.5, "BreathPeriod": 6.0},
                                                                      MI(PD): {"BreathAmp": 0.0, "BreathPeriod": 6.0}}),
         {"twin_material": PD}, "TWIN_BREATH_MISMATCH")):
    ok, msg = refuses(lambda r=rec_, L=L, a_=args_: SMP(r, L, a_), needle)
    check("L8.set_material_%s_refused(-)" % nm, ok, msg)
TRP = T["twin_revert_plan"]
unbound = {p: None for p in T["CLAM_SEQUENCES"]}
rp = TRP(trec, twin_live(twins=[dict(st, hidden=False)], twin_tracks=unbound))
check("L8.revert_ok(+)", rp == {"op": "destroy_twin", "object_path": st["object_path"], "label": T["TWIN_LABEL"], "bound": []}, rp)
bound = dict(unbound, **{T["SCENE3"]: ["MovieSceneVisibilityTrack", "MovieSceneComponentMaterialTrack"]})
for nm, L, args_, needle in (("bound", twin_live(twins=[dict(st)], twin_tracks=bound), None, "TWIN_BOUND"),
                             ("tracks_unread", twin_live(twins=[dict(st)], twin_tracks=dict(unbound, **{T["SCENE3"]: "UNREAD"})), None,
                              "TWIN_TRACKS_UNREAD"),
                             ("not_tagged", twin_live(twins=[dict(st, tags=[])], twin_tracks=unbound), None, "TWIN_NOT_TAGGED"),
                             ("no_twin", twin_live(twin_tracks=unbound), None, "TWIN_MISSING"),
                             ("wrong_parent", twin_live(twins=[dict(st, parent_path="X")], twin_tracks=unbound), None, "TWIN_PARENT")):
    ok, msg = refuses(lambda L=L, a_=args_: TRP(trec, L, a_), needle)
    check("L8.revert_%s_refused(-)" % nm, ok, msg)
check("L8.revert_bound_allowed_by_arg(+)", TRP(trec, twin_live(twins=[dict(st)], twin_tracks=bound),
                                               {"allow_bound_revert": True})["bound"] == [T["SCENE3"]])


# L9. BUILD_MAT end to end (FAKE editor): create-only, blend / TLM / clip read back, every v3 value copied from the live MI
def fake_build_twin(key, args=None, v3mi=None, clip=0.3333, **kw):
    tmpb = tempfile.mkdtemp(prefix="s3twin_")
    fe = FakeEd(**kw)
    fe.BlendMode = _Obj(**{n: n for n in T["BLEND_MODES"]})
    fe.TranslucencyLightingMode = _Obj(**{n: n for n in T["TLM_MODES"]})
    src = copy.deepcopy(v3mi if v3mi is not None else v3_live)
    o = _FObj(MI(P3), "MaterialInstanceConstant")
    o.sc = dict(src["scalars"])
    o.vc = {k: _Obj(r=v[0], g=v[1], b=v[2], a=v[3]) for k, v in src["vectors"].items()}
    o.tx = {k: _FObj(v, "Texture2D") for k, v in src["textures"].items()}
    o.props["parent"] = _FObj(src["parent"], "Material")
    base_load = fe.load_asset
    fe.load_asset = lambda p: o if p == MI(P3) else base_load(p)
    base_create = fe.AssetToolsHelpers.get_asset_tools().create_asset

    def create(name, folder, cls, f):
        a_ = base_create(name, folder, cls, f)
        if cls is fe.Material and clip is not None:
            a_.props["opacity_mask_clip_value"] = clip
        return a_
    fe.AssetToolsHelpers = _Obj(get_asset_tools=lambda: _Obj(create_asset=create))
    keep = {k: G[k] for k in ("unreal", "HERE")}
    G.update(unreal=fe, HERE=tmpb + "/")
    try:
        try:
            return fe, T["run_build_clam_mat"]("RUNT", key, args or {}), None
        except PlanError as exc:
            return fe, None, str(exc)
    finally:
        G.update(keep)


for k, s_ in ((PF, SPF), (PD, SPD)):
    m_ = T["CLAM_EXTRA_MATERIALS"][k]
    fe, rec_, err = fake_build_twin(k)
    mat = fe.mats.get(m_["master"])
    ok = rec_ is not None and mat is not None
    check("L9.build_ok(+)|" + k, ok and sorted(fe.saved) == sorted([m_["master"], MI(k)]) and not fe.dirty, err or fe.saved)
    if not ok:
        continue
    check("L9.material_flags_set|" + k, mat.props["blend_mode"] == s_["blend_mode"] and mat.props["shading_model"] ==
          s_["shading_model"] and mat.props["used_with_nanite"] is False and
          mat.props.get("translucency_lighting_mode") == s_.get("translucency_lighting_mode") and
          mat.props.get("dither_opacity_mask", None) == (False if k == PD else None), mat.props)
    check("L9.nodes_links_props|" + k, len(mat.nodes) == len(s_["nodes"]) and len(mat.links) == len(s_["edges"]) and
          sorted(mat.mprops) == sorted(s_["want_props"]), sorted(mat.mprops))
    check("L9.mi_values_copied_from_live_v3(+)|" + k, all(abs(rec_["scalars"][q] - float(v)) < 1e-9 for q, v in v3_live["scalars"].items())
          and rec_["vectors"] == v3_live["vectors"] and rec_["scalars"]["Fade"] == 1.0 and rec_["scalars"]["Glow"] == 0.42 and
          rec_["copied_from"]["mi"] == MI(P3) and rec_["breath_inherited"] == {"BreathAmp": 1.5, "BreathPeriod": 6.0}, rec_["scalars"])
    check("L9.readback_recorded|" + k, rec_["material_readback"]["blend_mode"] == s_["blend_mode"] and
          rec_["material_readback"]["opacity_mask_clip_value"] == 0.3333 and rec_["blend_mode"] == s_["blend_mode"], rec_["material_readback"])
fe, rec_, err = fake_build_twin(PF, {"translucency_lighting_mode": "TLM_SURFACE"})
check("L9.tlm_arg_used_and_recorded(+)", rec_ is not None and rec_["translucency_lighting_mode"] == "TLM_SURFACE" and
      fe.mats[T["PEARL_FADE_MASTER"]].props["translucency_lighting_mode"] == "TLM_SURFACE", err)
for nm, key, args_, kw, needle in (
        ("fade_master_exists", PF, None, {"existing": [T["PEARL_FADE_MASTER"]]}, "LOOK_MASTER_EXISTS"),
        ("dither_master_exists", PD, None, {"existing": [T["PEARL_DITHER_MASTER"]]}, "LOOK_MASTER_EXISTS"),
        ("dither_mi_exists", PD, None, {"existing": [MI(PD)]}, "MI_EXISTS"),
        ("tlm_arg_on_masked", PD, {"translucency_lighting_mode": "TLM_SURFACE"}, {}, "TLM_ARG"),
        ("tlm_arg_unknown", PF, {"translucency_lighting_mode": "TLM_NOPE"}, {}, "TLM_ARG"),
        ("source_parent_wrong", PF, None, {"v3mi": dict(copy.deepcopy(v3_live), parent=T["PEARL_V2_MASTER"])}, "COPY_SOURCE_PARENT"),
        ("clip_out_of_range", PD, None, {"clip": 0.0}, "MASTER_CLIP_VALUE"),
        ("clip_unreadable", PF, None, {"clip": None}, "MASTER_PROP_UNREADABLE"),
        ("connect_mask_false", PD, None, {"fail_prop": "MP_OPACITY_MASK"}, "PROP|MP_OPACITY_MASK"),
        ("connect_opacity_false", PF, None, {"fail_prop": "MP_OPACITY"}, "PROP|MP_OPACITY")):
    fe, rec_, err = fake_build_twin(key, args_, **kw)
    check("L9.%s_refused_nothing_saved(-)" % nm, rec_ is None and err and needle in err and fe.saved == [], (err, fe.saved))
fe, rec_, err = fake_build_twin(PF, None, readback="wrong")
check("L9.readback_wrong_node_refused(-)", rec_ is None and err and "PROP_READBACK" in err and fe.saved == [], err)

# ================================================================== M. Pearl v3 GreenOrange (8 Oct): MI-only look + twin sync
GO = T["PEARL_V3_GO"]
V3M = T["PEARL_V3_MASTER"]
GOROW = T["CLAM_EXTRA_MATERIALS"][GO]
GOD = T["GREEN_ORANGE_DEFAULTS"]
# M1. tables + lint
check("M1.variant_table_clean(+)", T["variant_table_problems"]() == [] and T["look_table_problems"]() == [] and
      T["twin_sync_param_problems"]() == [] and GO not in T["material_problems"](), (T["variant_table_problems"](),
                                                                                     T["look_table_problems"]()))
check("M1.mi_only_row_on_live_v3_master", GOROW["mi_only"] and not GOROW.get("master_create_only") and GOROW["master"] == V3M and
      GOROW["copy_from"] == P3 and GOROW["breath_from"] == P3 and GOROW["mi"] == "MI_PearlClam_Pearl_v3_GreenOrange" and
      GOROW["scalars"] == {} and GOROW["vectors"] == {} and set(specs) == set(T["material_specs"]()), GOROW)
check("M1.no_new_master_spec", V3M in specs and not any("GreenOrange" in p for p in T["material_specs"]()))
check("M1.look_row_chain", T["CLAM_LOOKS"][GO]["from_material"] == P3 and T["CLAM_LOOKS"][GO]["requires_look"] == P3 and
      T["CLAM_LOOKS"][GO]["targets"] == T["CLAM_LOOKS"][P3]["targets"] == {"Pearl": 0} and T["CLAM_LOOKS"][GO]["glow_check"] and
      T["look_record_path"](GO) not in {T["look_record_path"](k) for k in LOOKS} | {T["TWIN_RECORD"], T["TWIN_SYNC_RECORD"]})
check("M1.sync_params_equal_variant_overrides", set(T["TWIN_SYNC_SCALARS"]) == set(GOD["scalars"]) and
      set(T["TWIN_SYNC_VECTORS"]) == set(GOD["vectors"]) and not set(T["TWIN_SYNC_FORBIDDEN"]) & (set(GOD["scalars"]) | set(GOD["vectors"])))
check("M1.defaults_as_briefed", GOD["scalars"] == {"IridStrength": 0.45, "SubsurfaceIrid": 0.45, "FresnelExponent": 2.0, "Glow": 0.03,
                                                    "GlowIrid": 0.0} and GOD["vectors"]["PaletteB"][:3] == [-0.22, 0.10, 0.10] and
      GOD["vectors"]["PaletteA"][:3] == [0.72, 0.74, 0.48] and GOD["vectors"]["SubsurfaceBase"][:3] == [0.92, 0.91, 0.87] and
      GOD["vectors"]["GlowColor"][:3] == [1.0, 0.97, 0.92] and GOD["vectors"]["PaletteC"][:3] == [1.0, 1.0, 1.0] and
      GOD["vectors"]["PaletteD"][:3] == [0.0, 0.0, 0.0])
saved_ov = copy.deepcopy(GOROW["overrides"])
GOROW["overrides"]["scalars"]["BreathAmp"] = 0.0
try:
    check("M1.override_of_breath_in_table_caught(-)", any("VARIANT_OVERRIDE_FORBIDDEN" in x for x in T["variant_table_problems"]()),
          T["variant_table_problems"]())
finally:
    GOROW["overrides"].clear()
    GOROW["overrides"].update(saved_ov)
GOROW["master"] = T["PEARL_V2_MASTER"]
try:
    check("M1.variant_on_other_master_caught(-)", any("VARIANT_ROW" in x for x in T["variant_table_problems"]()))
finally:
    GOROW["master"] = V3M
check("M1.tables_restored", T["variant_table_problems"]() == [])
# M2. palette mirror (IRID_COLOR_CODE): endpoints green / orange; negative PB component survives to the saturate
PAL_A, PAL_B = GOD["vectors"]["PaletteA"], GOD["vectors"]["PaletteB"]
ends = T["palette_endpoints"](PAL_A, PAL_B)
r3 = lambda v: [round(x, 4) for x in v]  # noqa: E731
print("INFO M2 palette endpoints: cos=+1 %s (green)  cos=-1 %s (orange)" % (r3(ends["cos_plus"]), r3(ends["cos_minus"])))
check("M2.cos_plus_is_green(+)", T["near"](ends["cos_plus"], [0.50, 0.84, 0.58], 1e-9) and
      ends["cos_plus"][1] > ends["cos_plus"][2] > ends["cos_plus"][0], ends)
check("M2.cos_minus_is_orange(+)", T["near"](ends["cos_minus"], [0.94, 0.64, 0.38], 1e-9) and
      ends["cos_minus"][0] > ends["cos_minus"][1] > ends["cos_minus"][2], ends)
PE = T["palette_eval"]
check("M2.palette_eval_matches_endpoints(+)", T["near"](PE(PAL_A, PAL_B, [1, 1, 1], [0, 0, 0], 0.0), ends["cos_plus"], 1e-9) and
      T["near"](PE(PAL_A, PAL_B, [1, 1, 1], [0, 0, 0], 0.5), ends["cos_minus"], 1e-9) and
      T["near"](PE(PAL_A, PAL_B, [1, 1, 1], [0, 0, 0], 1.0), ends["cos_plus"], 1e-9))
check("M2.code_saturates_after_the_sum(decl: IRID_COLOR_CODE)", T["IRID_COLOR_CODE"].startswith(
    "float3 pal = saturate(PA.rgb + PB.rgb * cos(6.2831853 * (PC.rgb * P + PD.rgb)));") and "saturate(PB" not in T["IRID_COLOR_CODE"])
clamped = T["palette_endpoints"](PAL_A, [max(0.0, x) for x in PAL_B])
check("M2.negative_red_is_needed(-control: PB clamped to >= 0 loses the green end)", not T["near"](clamped["cos_plus"], ends["cos_plus"], 0.05)
      and clamped["cos_plus"][0] > 0.7, clamped)
check("M2.all_endpoints_in_gamut(no saturate clipping at the defaults)", all(0.0 < x < 1.0 for v in ends.values() for x in v), ends)
# where the copied v3 phase lands: phase = fresnel^E * IridScale + nacre * NacreScale (IRID_PHASE_CODE)
v3s_ = v3_live["scalars"]
sweep = []
for nm, ndv, nac in (("facing_nacre_p5", 1.0, 0.18), ("facing_nacre_p50", 1.0, 0.44), ("facing_nacre_p95", 1.0, 0.75),
                     ("mid_ndotv_0.5", 0.5, 0.44), ("rim_ndotv_0.1", 0.1, 0.44)):
    ph = T["irid_phase_eval"](ndv, GOD["scalars"]["FresnelExponent"], v3s_["IridScale"], nac, v3s_["NacreScale"])
    pal = PE(PAL_A, PAL_B, [1, 1, 1], [0, 0, 0], ph)
    surf = T["irid_color_eval"](v3_live["vectors"]["BaseColor"], PAL_A, PAL_B, [1, 1, 1], [0, 0, 0], ph, GOD["scalars"]["IridStrength"])
    sweep.append((nm, round(ph, 3), r3(pal), r3(surf)))
print("INFO M2 phase sweep (IridScale %.2f, NacreScale %.2f copied from live v3): %s" % (v3s_["IridScale"], v3s_["NacreScale"], sweep))
check("M2.sweep_spans_green_and_orange(inf: on-screen look unproven)", any(s[2][1] > s[2][0] for s in sweep) and
      any(s[2][0] > s[2][1] for s in sweep), sweep)
gmax = max(max(T["inner_glow_eval"](1.0, v3s_["GlowFresnelExponent"], v3s_["GlowFalloff"], GOD["scalars"]["Glow"],
                                    GOD["vectors"]["GlowColor"], [1, 1, 1], GOD["scalars"]["GlowIrid"])),
           max(T["inner_glow_eval"](0.3, v3s_["GlowFresnelExponent"], v3s_["GlowFalloff"], GOD["scalars"]["Glow"],
                                    GOD["vectors"]["GlowColor"], [1, 1, 1], GOD["scalars"]["GlowIrid"])))
check("M2.emissive_is_slight_and_uncoloured(+)", gmax <= 0.03 + 1e-12 and GOD["scalars"]["GlowIrid"] == 0.0, gmax)
# M3. copy-from-live plan (MI_PearlClam_Pearl_v3 as the owning session recorded it, Glow tuned live to 0.42)
MVV = T["mi_variant_values"]
vv = MVV(GO, copy.deepcopy(v3_live))
not_over = set(SP3["scalars"]) - set(GOD["scalars"])
check("M3.every_non_override_value_copied(+)", all(vv["scalars"][k] == float(v3_live["scalars"][k]) for k in not_over) and
      all(vv["vectors"][k] == v3_live["vectors"][k] for k in set(SP3["vectors"]) - set(GOD["vectors"])) and
      set(vv["scalars"]) == set(SP3["scalars"]) and set(vv["vectors"]) == set(SP3["vectors"]), sorted(not_over))
check("M3.overrides_applied(+)", all(vv["scalars"][k] == v for k, v in GOD["scalars"].items()) and
      all(vv["vectors"][k] == v for k, v in GOD["vectors"].items()) and vv["scalars"]["Glow"] == 0.03, vv["overrides"])
check("M3.breath_copied_unchanged(+)", vv["breath"] == {"BreathAmp": 1.5, "BreathPeriod": 6.0} and
      vv["scalars"]["BreathAmp"] == v3_live["scalars"]["BreathAmp"], vv["breath"])
check("M3.changed_list", set(vv["changed"]) <= set(GOD["scalars"]) | set(GOD["vectors"]) and "Glow" in vv["changed"] and
      "PaletteB" in vv["changed"] and vv["parent"] == V3M, vv["changed"])
vv2 = MVV(GO, copy.deepcopy(v3_live), {"variant": {"scalars": {"IridStrength": 0.5}, "vectors": {"PaletteD": [0.0, 0.05, 0.0]}}})
check("M3.arg_overrides_each_value(+)", vv2["scalars"]["IridStrength"] == 0.5 and vv2["vectors"]["PaletteD"] == [0.0, 0.05, 0.0, 1.0]
      and vv2["scalars"]["Glow"] == 0.03, (vv2["scalars"]["IridStrength"], vv2["vectors"]["PaletteD"]))
check("M3.bright_glow_allowed_by_arg(+)", MVV(GO, copy.deepcopy(v3_live), {"variant": {"scalars": {"Glow": 0.5}},
                                                                         "allow_glow_above_max": True})["scalars"]["Glow"] == 0.5)
for nm, src_fn, args_, needle in (
        ("wrong_parent", lambda s: s.update(parent=T["PEARL_V2_MASTER"]), None, "COPY_SOURCE_PARENT"),
        ("wrong_source_mi", lambda s: s.update(mi=MI(T["PEARL_V2"])), None, "COPY_SOURCE|"),
        ("source_scalar_unread", lambda s: s["scalars"].pop("IridScale"), None, "COPY_SCALARS_UNREAD"),
        ("source_texture_differs", lambda s: s["textures"].update(Nacre="/Game/X/T_Other"), None, "COPY_TEXTURE_DIFFERS"),
        ("override_breath", None, {"variant": {"scalars": {"BreathAmp": 0.0}}}, "VARIANT_FORBIDDEN"),
        ("override_fade", None, {"variant": {"scalars": {"Fade": 0.5}}}, "VARIANT_PARAM_UNKNOWN"),
        ("override_unknown", None, {"variant": {"vectors": {"PaletteE": [0, 0, 0]}}}, "VARIANT_PARAM_UNKNOWN"),
        ("glow_not_slight", None, {"variant": {"scalars": {"Glow": 0.5}}}, "VARIANT_GLOW_NOT_SLIGHT"),
        ("glow_negative", None, {"variant": {"scalars": {"Glow": -0.1}}, "allow_glow_above_max": True}, "VARIANT_GLOW_NOT_SLIGHT"),
        ("strength_range", None, {"variant": {"scalars": {"IridStrength": 1.5}}}, "VARIANT_SCALAR_RANGE"),
        ("fresnel_zero", None, {"variant": {"scalars": {"FresnelExponent": 0.0}}}, "VARIANT_SCALAR_RANGE"),
        ("nan", None, {"variant": {"scalars": {"SubsurfaceIrid": float("nan")}}}, "VARIANT_SCALAR_VALUE"),
        ("colour_range", None, {"variant": {"vectors": {"SubsurfaceBase": [1.2, 0.9, 0.9]}}}, "VARIANT_COLOUR_RANGE"),
        ("vector_shape", None, {"variant": {"vectors": {"PaletteA": [0.7, 0.7]}}}, "VARIANT_VECTOR_SHAPE"),
        ("bad_arg_shape", None, {"variant": {"colours": {}}}, "VARIANT_ARG")):
    src_ = copy.deepcopy(v3_live)
    if src_fn:
        src_fn(src_)
    ok, msg = refuses(lambda src_=src_, a_=args_: MVV(GO, src_, a_), needle)
    check("M3.%s_refused(-)" % nm, ok, msg)
ok, msg = refuses(lambda: MVV(P3, copy.deepcopy(v3_live)), "NOT_AN_MI_VARIANT")
check("M3.non_variant_key_refused(-)", ok, msg)


# M4. BUILD_MAT end to end (FAKE editor holding the LIVE v3 master + MI): MI-only, nothing else created or saved
def fake_v3_env(v3mi=None, existing=(), with_master=True):
    fe = FakeEd(existing=existing)
    fe.BlendMode = _Obj(**{n: n for n in T["BLEND_MODES"]})
    fe.TranslucencyLightingMode = _Obj(**{n: n for n in T["TLM_MODES"]})
    fe.log = lambda s: None
    base_create = fe.AssetToolsHelpers.get_asset_tools().create_asset

    def create(name, folder, cls, f):
        a_ = base_create(name, folder, cls, f)
        if cls is fe.Material:
            a_.props["opacity_mask_clip_value"] = 0.3333
        return a_
    fe.AssetToolsHelpers = _Obj(get_asset_tools=lambda: _Obj(create_asset=create))
    keep = {k: G[k] for k in ("unreal", "HERE")}
    G.update(unreal=fe)
    try:
        if with_master:
            T["_build_material"](V3M, SP3, {"Nacre": fe.load_asset(NACRE)})
        src = copy.deepcopy(v3mi if v3mi is not None else v3_live)
        o = fe.MaterialInstanceConstant(MI(P3), "MaterialInstanceConstant")
        o.sc = dict(src["scalars"])
        o.vc = {k: _Obj(r=v[0], g=v[1], b=v[2], a=v[3]) for k, v in src["vectors"].items()}
        o.tx = {k: _FObj(v, "Texture2D") for k, v in src["textures"].items()}
        par = fe.mats.get(src["parent"]) or _FObj(src["parent"], "Material")
        o.parent_, o.props["parent"] = par, par
        fe.mats[MI(P3)] = o
        fe.assets.add(MI(P3))
    finally:
        G.update(keep)
    fe.dirty.clear()
    fe.saved.clear()
    return fe


def fake_build_go(fe, args=None):
    tmpb = tempfile.mkdtemp(prefix="s3go_")
    keep = {k: G[k] for k in ("unreal", "HERE")}
    G.update(unreal=fe, HERE=tmpb + "/")
    try:
        try:
            return T["run_build_clam_mat"]("RUNGO", GO, args or {}), None
        except PlanError as exc:
            return None, str(exc)
    finally:
        G.update(keep)


fe = fake_v3_env()
n_mats0 = len(fe.mats)
rec_, err = fake_build_go(fe)
gmi = fe.mats.get(MI(GO))
check("M4.build_ok_mi_only(+)", rec_ is not None and fe.saved == [MI(GO)] and not fe.dirty and len(fe.mats) == n_mats0 + 1 and
      rec_["master_created"] is False and rec_["mi_only"] is True, err or fe.saved)
if rec_ is not None:
    check("M4.parent_is_the_live_v3_master(+)", gmi.props["parent"] is fe.mats[V3M] and rec_["master"] == V3M and
          rec_["copied_from"]["parent"] == V3M)
    check("M4.every_value_read_back(+)", all(abs(rec_["scalars"][k] - vv["scalars"][k]) < 1e-9 for k in SP3["scalars"]) and
          all(T["near"](rec_["vectors"][k], vv["vectors"][k], 1e-9) for k in SP3["vectors"]) and
          rec_["vectors"]["PaletteB"][0] == -0.22, rec_["vectors"]["PaletteB"])
    check("M4.record_fields", rec_["palette_endpoints"] == ends and rec_["breath_inherited"] == {"BreathAmp": 1.5, "BreathPeriod": 6.0}
          and rec_["overrides"] == vv["overrides"] and gmi.tx.get("Nacre") is not None)
    check("M4.master_not_touched(+)", V3M not in fe.saved and len(fe.mats[V3M].nodes) == len(SP3["nodes"]))
fe = fake_v3_env(existing=[MI(GO)])
rec_, err = fake_build_go(fe)
check("M4.build_over_existing_mi_refused_nothing_saved(-)", rec_ is None and "MI_EXISTS" in (err or "") and fe.saved == [], err)
fe = fake_v3_env(with_master=False)
rec_, err = fake_build_go(fe)
check("M4.master_missing_refused_never_created(-)", rec_ is None and "VARIANT_MASTER_MISSING" in (err or "") and fe.saved == [] and
      V3M not in fe.mats, err)
fe = fake_v3_env(v3mi=dict(copy.deepcopy(v3_live), parent=T["PEARL_V2_MASTER"]))
rec_, err = fake_build_go(fe)
check("M4.wrong_parent_refused_nothing_saved(-)", rec_ is None and "COPY_SOURCE_PARENT" in (err or "") and fe.saved == [], err)
fe = fake_v3_env()
_vset = fe.MaterialEditingLibrary.set_material_instance_vector_parameter_value
fe.MaterialEditingLibrary.set_material_instance_vector_parameter_value = lambda mi, k, v: _vset(
    mi, k, _Obj(r=max(0.0, v.r), g=max(0.0, v.g), b=max(0.0, v.b), a=v.a))     # a setter that clamps negatives
rec_, err = fake_build_go(fe)
check("M4.clamped_negative_palette_caught_nothing_saved(-)", rec_ is None and "MI_VECTORS" in (err or "") and fe.saved == [], err)
fe = fake_v3_env()
rec_, err = fake_build_go(fe, {"variant": {"scalars": {"Glow": 0.6}}})
check("M4.bright_glow_refused_nothing_created(-)", rec_ is None and "VARIANT_GLOW_NOT_SLIGHT" in (err or "") and fe.saved == [] and
      MI(GO) not in fe.mats, err)
# M5. mode gates (swap chain, unswap ordering, twin interaction, sync)
SY, SYR = "CLAM_PEARL_TWIN_SYNC", "CLAM_PEARL_TWIN_SYNC_REVERT"
check("M5.build_mat_ok(+)", CM({"mode": "BUILD_MAT", "confirm": "BUILD_MAT S3PROPS", "prop": "PearlClam", "material": GO},
                               True, False, False, True) == "BUILD_MAT")
check("M5.mat_check_ok_read_only(+)", CM({"mode": "CLAM_LOOK_MAT_CHECK", "material": GO}, True, False) == "CLAM_LOOK_MAT_CHECK")
check("M5.swap_after_v3_ok(+)", CM(LS(look=GO), True, False, False, True, True, [P3]) == "CLAM_LOOK_SWAP")
check("M5.swap_not_blocked_by_twin(+)", CM(LS(look=GO), True, False, False, True, True, [P3], True) == "CLAM_LOOK_SWAP")
check("M5.unswap_ok(+)", CM(LU(look=GO), True, False, False, True, True, [P3, GO], True) == "CLAM_LOOK_UNSWAP")
check("M5.unswap_v3_after_variant_gone(+)", CM(LU(look=P3), True, False, False, True, True, [P3], True) == "CLAM_LOOK_UNSWAP")
check("M5.sync_ok(+)", CM(TW(SY), True, False, False, True, True, [P3, GO], True) == SY)
check("M5.sync_revert_ok(+)", CM(TW(SYR), True, False, False, True, True, [P3, GO], True, True) == SYR)
check("M5.sync_revert_ok_after_twin_reverted(+)", CM(TW(SYR), True, False, False, True, True, [P3, GO], False, True) == SYR)
check("M5.twin_revert_not_blocked_by_sync(+)", CM(TW("CLAM_PEARL_TWIN_REVERT"), True, False, False, True, True, [P3, GO], True, True)
      == "CLAM_PEARL_TWIN_REVERT")
for nm, call, needle in (
        ("swap_without_v3_record", lambda: CM(LS(look=GO), True, False, False, True, True, []), "LOOK_CHAIN"),
        ("swap_without_pearl_swap", lambda: CM(LS(look=GO), True, False, False, True, False, [P3]), "LOOK_CHAIN"),
        ("swap_twice", lambda: CM(LS(look=GO), True, False, False, True, True, [P3, GO]), "LOOK_ALREADY_SWAPPED"),
        ("unswap_v3_while_variant", lambda: CM(LU(look=P3), True, False, False, True, True, [P3, GO]), "LOOK_DEPENDENT_SWAPPED"),
        ("unswap_variant_while_synced", lambda: CM(LU(look=GO), True, False, False, True, True, [P3, GO], True, True), "TWIN_SYNCED"),
        ("clam_revert_with_variant", lambda: CM(TW("CLAM_REVERT"), True, False, False, True, False, [GO]), "LOOK_SWAPPED"),
        ("pearl_swap_with_variant", lambda: CM(TW("PEARL_SWAP"), True, False, False, True, False, [GO]), "PEARL_LOOK_SWAPPED"),
        ("pearl_unswap_with_variant", lambda: CM(TW("PEARL_UNSWAP"), True, False, False, True, True, [GO]), "PEARL_LOOK_SWAPPED"),
        ("sync_without_twin_record", lambda: CM(TW(SY), True, False, False, True, True, [P3, GO], False), "NO_TWIN_RECORD"),
        ("sync_twice", lambda: CM(TW(SY), True, False, False, True, True, [P3, GO], True, True), "TWIN_SYNC_ALREADY"),
        ("sync_without_clam", lambda: CM(TW(SY), True, False, False, False, True, [], True), "NO_CLAM_RECORD"),
        ("sync_confirm", lambda: CM({"mode": SY, "confirm": SY}, True, False, False, True, True, [P3, GO], True), "CONFIRM_MISSING"),
        ("sync_while_tex_pending", lambda: CM(TW(SY), True, False, True, True, True, [P3, GO], True), "TEX_PENDING"),
        ("sync_revert_without_record", lambda: CM(TW(SYR), True, False, False, True, True, [P3, GO], True, False), "NO_TWIN_SYNC_RECORD")):
    ok, msg = refuses(call, needle)
    check("M5.%s_refused(-)" % nm, ok, msg)
check("M5.sync_modes_write_modes", SY in T["MODES"] and SYR in T["MODES"] and SY not in T["READ_ONLY_MODES"] and
      SYR not in T["READ_ONLY_MODES"])
# M6. CLAM_LOOK_SWAP plan for the variant against the REAL clam record (pearl on v2 mesh + v3 MI), glow read back
LGO = look_live(GO)
LGO["actors"]["Pearl"].update(materials=[MI(P3)], override_materials=[MI(P3)])
LGO["glow"] = dict(GLOW0)
pgo = LP(GO, crec, copy.deepcopy(LGO))
tgo = pgo["targets"][0]
check("M6.plan_from_v3_to_variant(+)", pgo["old_mi"] == MI(P3) and pgo["new_mi"] == MI(GO) and pgo["master"] == V3M and
      [(t["part"], t["slot"]) for t in pgo["targets"]] == [("Pearl", 0)] and tgo["after"]["materials"] == [MI(GO)] and
      tgo["after"]["mesh"] == T["clam_mesh_path"](T["PEARL_V2"]) and tgo["after"]["rel"] == tgo["before"]["rel"], pgo["old_mi"])
check("M6.glow_recorded(+)", pgo["glow_before"] == GLOW0)
w0 = {tgo["object_path"]: copy.deepcopy(tgo["before"])}
w1 = T["clam_look_simulate"](w0, T["clam_look_swap_ops"](pgo))
w2 = T["clam_look_simulate"](w1, T["clam_look_unswap_ops"]({"plan": json.loads(json.dumps(pgo))}))
check("M6.swap_then_unswap_restores_v3_exactly(+)", w2 == w0 and w2[tgo["object_path"]]["materials"] == [MI(P3)] and
      T["clam_look_state_problems"]({"Pearl": dict(w1[tgo["object_path"]], count=1)}, pgo["targets"], "after") == [])
check("M6.glow_unchanged_passes(+)", T["look_glow_problems"](GLOW0, dict(GLOW0)) == [])
check("M6.glow_detached_caught(-)", T["look_glow_problems"](GLOW0, {"count": 1, "parent_path": None}) != [] and
      T["look_glow_problems"](GLOW0, {"count": 0, "parent_path": None}) != [])
check("M6.v3_look_has_no_glow_gate(+, unchanged behaviour)", "glow_before" not in plans[P3])
# the glue read-back (_look_check) with the actor + glow lookups faked: a detached glow fails the swap read-back
for nm, glow_now, want_ok in (("glow_kept_passes(+)", dict(GLOW0), True), ("glow_detached_fails(-)", {"count": 1, "parent_path": None}, False)):
    over_ = {"_index": lambda w: {}, "_look_actor_live": lambda w, i, part, with_tracks=True: dict(w1[tgo["object_path"]], count=1),
             "_glow_live": lambda w, g=glow_now: dict(g)}
    keep_ = {k: G[k] for k in over_}
    G.update(over_)
    try:
        try:
            G["_look_check"](None, GO, pgo["targets"], "after", pgo["glow_before"])
            got_ok, msg = True, ""
        except PlanError as exc:
            got_ok, msg = False, str(exc)
    finally:
        G.update(keep_)
    check("M6.look_check_" + nm, got_ok == want_ok and (want_ok or "GLOW_TOUCHED" in msg), msg)
for nm, fn, needle in (
        ("pearl_still_on_v2_mi", lambda L: L["actors"]["Pearl"].update(materials=[MI(T["PEARL_V2"])],
                                                                       override_materials=[MI(T["PEARL_V2"])]), "LOOK_MATERIAL_NOT_CURRENT"),
        ("glow_unread", lambda L: L.pop("glow"), "LOOK_GLOW_UNREAD"),
        ("variant_not_built", lambda L: L["assets"].update({MI(GO): False}), "LOOK_ASSETS_MISSING"),
        ("breath_mismatch", lambda L: L["breath"][MI(GO)].update(BreathAmp=0.0), "LOOK_BREATH_MISMATCH"),
        ("material_track", lambda L: L["tracks"]["Pearl"].update({T["SCENE3"]: ["MovieSceneComponentMaterialTrack"]}),
         "LOOK_MATERIAL_TRACKS"),
        ("already_on", lambda L: L["actors"]["Pearl"].update(materials=[MI(GO)], override_materials=[MI(GO)]), "LOOK_MATERIAL_NOT_CURRENT")):
    L = copy.deepcopy(LGO)
    fn(L)
    ok, msg = refuses(lambda L=L: LP(GO, crec, L), needle)
    check("M6.%s_refused(-)" % nm, ok, msg)
# the twin's own gates with the pearl on the variant: CLAM_PEARL_TWIN still plans (breath equal), the variant is not blocked
tp_go = TP(crec, twin_live(pearl=dict(copy.deepcopy(pearl_live), materials=[MI(GO)], override_materials=[MI(GO)]),
                           breath={MI(GO): {"BreathAmp": 1.5, "BreathPeriod": 6.0}, MI(PF): {"BreathAmp": 1.5, "BreathPeriod": 6.0},
                                   MI(PD): {"BreathAmp": 1.5, "BreathPeriod": 6.0}}))
check("M6.twin_plan_with_pearl_on_variant(+)", tp_go["breath"]["pearl_mi"] == MI(GO) and tp_go["mi"] == MI(PF))
# M7. TWIN_SYNC plan: pearl on the variant, twin MIs as BUILD_MAT made them (every v3 value copied)
TSP = T["twin_sync_plan"]
go_full = {"mi": MI(GO), "exists": True, "parent": V3M, "scalar_names": sorted(vv["scalars"]), "vector_names": sorted(vv["vectors"]),
           "scalars": dict(vv["scalars"]), "vectors": copy.deepcopy(vv["vectors"])}


def twin_target(key):
    cp = LCV(key, copy.deepcopy(v3_live))
    return {"mi": MI(key), "exists": True, "parent": T["CLAM_EXTRA_MATERIALS"][key]["master"], "scalar_names": sorted(cp["scalars"]),
            "vector_names": sorted(cp["vectors"]), "scalars": dict(cp["scalars"]), "vectors": copy.deepcopy(cp["vectors"])}


def sync_live(**over):
    L = {"pearl": {"count": 1, "label": T["CLAM_LABELS"]["Pearl"], "object_path": crec["actor_paths"]["Pearl"], "materials": [MI(GO)]},
         "source": copy.deepcopy(go_full), "targets": {MI(PF): twin_target(PF), MI(PD): twin_target(PD)}}
    L.update(over)
    return L


TREC = {"applied": True, "saved": True, "object_path": "PersistentLevel.StaticMeshActor_TWIN", "twin_material": PF}
spl = TSP(TREC, crec, sync_live())
sync_names = set(T["TWIN_SYNC_SCALARS"]) | set(T["TWIN_SYNC_VECTORS"])
for t in spl["targets"]:
    k = t["key"]
    check("M7.writes_are_the_changed_sync_params(+)|" + k, set(t["writes"]) == set(vv["changed"]) & sync_names and
          set(t["writes"]) | set(t["unchanged"]) == sync_names and t["skipped"] == [], (sorted(t["writes"]), t["skipped"]))
    check("M7.after_equals_source_on_synced(+)|" + k, all(T["_snap_close"](t["after"][("scalars" if p in T["TWIN_SYNC_SCALARS"] else "vectors")][p],
                                                                        go_full["scalars"].get(p, go_full["vectors"].get(p)))
                                                       for p in sync_names), t["writes"])
    rest = [p for p in t["before"]["scalars"] if p not in sync_names] + [p for p in t["before"]["vectors"] if p not in sync_names]
    check("M7.everything_else_untouched(+)|" + k, all(t["after"]["scalars"].get(p, t["after"]["vectors"].get(p)) ==
                                                     t["before"]["scalars"].get(p, t["before"]["vectors"].get(p)) for p in rest) and
          t["after"]["scalars"]["Fade"] == 1.0 and t["after"]["scalars"]["BreathAmp"] == 1.5 and
          set(t["untouched"]) == ({"Fade", "BaseOpacity", "BreathAmp", "BreathPeriod"} if k == PF else {"Fade", "BreathAmp", "BreathPeriod"}),
          t["untouched"])
MAPT = spl["mapping"]
print("INFO M7 sync mapping (param -> target param | v3 drives -> target drives):")
for k in (PF, PD):
    for p, r in MAPT[k].items():
        print("INFO   %-12s %-15s -> %-15s | %s -> %s" % (k, p, r["target_param"], ",".join(r["v3_drives"]), ",".join(r["target_drives"])))
check("M7.mapping_identity_on_both(+)", all(r["target_param"] == p and r["on_target_spec"] for k in (PF, PD) for p, r in MAPT[k].items()))
check("M7.fade_subsurface_goes_to_basecolor(decl: spec)", all("MP_BASE_COLOR" in MAPT[PF][p]["target_drives"] and
                                                              "MP_SUBSURFACE_COLOR" not in MAPT[PF][p]["target_drives"] and
                                                              "MP_SUBSURFACE_COLOR" in MAPT[PF][p]["v3_drives"]
                                                              for p in ("SubsurfaceIrid", "SubsurfaceBase")), MAPT[PF]["SubsurfaceIrid"])
check("M7.dither_drives_like_v3(decl: spec)", all(set(MAPT[PD][p]["target_drives"]) == set(MAPT[PD][p]["v3_drives"]) for p in MAPT[PD]),
      {p: (r["v3_drives"], r["target_drives"]) for p, r in MAPT[PD].items() if set(r["v3_drives"]) != set(r["target_drives"])})
check("M7.palette_reaches_fade_basecolor_and_emissive", set(MAPT[PF]["PaletteB"]["target_drives"]) >= {"MP_BASE_COLOR", "MP_EMISSIVE_COLOR"})
# skip path: a target that lacks a parameter (live names) is listed, not written
L = sync_live()
tf_ = L["targets"][MI(PF)]
for p in ("SubsurfaceIrid", "SubsurfaceBase"):
    for kk in ("scalars", "vectors"):
        tf_[kk].pop(p, None)
    tf_["scalar_names"] = sorted(tf_["scalars"])
    tf_["vector_names"] = sorted(tf_["vectors"])
sk = TSP(TREC, crec, L)["targets"][0]
check("M7.missing_param_skipped_and_listed(+)", sorted(s["param"] for s in sk["skipped"]) == ["SubsurfaceBase", "SubsurfaceIrid"] and
      not {"SubsurfaceBase", "SubsurfaceIrid"} & set(sk["writes"]), sk["skipped"])
# ops round trip: sync -> after on both, revert -> before EXACTLY; a forbidden op is refused
vals0 = {t["mi"]: copy.deepcopy(t["before"]) for t in spl["targets"]}
ops_ = T["twin_sync_ops"](spl, "to")
vals1 = T["twin_sync_simulate"](vals0, ops_)
check("M7.sync_effect(+)", all(T["twin_sync_state_problems"](vals1[t["mi"]], t["after"]) == [] for t in spl["targets"]) and
      not any(op["param"] in T["TWIN_SYNC_FORBIDDEN"] for op in ops_) and {op["mi"] for op in ops_} == {MI(PF), MI(PD)}, len(ops_))
rp_ = T["twin_sync_revert_plan"]({"applied": True, "saved": True, "plan": json.loads(json.dumps(spl))},
                                {"targets": {m_: dict(v, exists=True) for m_, v in vals1.items()}})
vals2 = T["twin_sync_simulate"](vals1, rp_["ops"])
check("M7.revert_exact(+)", vals2 == vals0, json.dumps(vals2)[:200])
check("M7.synced_differs_from_before(-)", any(T["twin_sync_state_problems"](vals1[t["mi"]], t["before"]) for t in spl["targets"]))
bad_ = json.loads(json.dumps(spl))
bad_["targets"][0]["writes"]["Fade"] = {"kind": "scalar", "from": 1.0, "to": 0.0}
ok, msg = refuses(lambda: T["twin_sync_ops"](bad_, "to"), "TWIN_SYNC_FORBIDDEN_WRITE")
check("M7.sync_op_touching_fade_refused(-)", ok, msg)
bad_ = json.loads(json.dumps(spl))
bad_["targets"][1]["writes"]["BreathAmp"] = {"kind": "scalar", "from": 1.5, "to": 0.0}
ok, msg = refuses(lambda: T["twin_sync_ops"](bad_, "to"), "TWIN_SYNC_FORBIDDEN_WRITE")
check("M7.sync_op_touching_breath_refused(-)", ok, msg)
wrong = T["twin_sync_simulate"](vals1, [{"op": "set_param", "mi": MI(PF), "kind": "scalar", "param": "Fade", "value": 0.0}])
check("M7.fade_change_caught_by_readback(-)", any("SCALARS|Fade" in x for x in T["twin_sync_state_problems"](wrong[MI(PF)],
                                                                                                         spl["targets"][0]["after"])))
for nm, val in (("Fade", ("IridStrength", "Fade")), ("BreathPeriod", ("IridStrength", "BreathPeriod"))):
    keep_ = G["TWIN_SYNC_SCALARS"]
    G["TWIN_SYNC_SCALARS"] = keep_ + val[1:]
    try:
        ok, msg = refuses(lambda: TSP(TREC, crec, sync_live()), "TWIN_SYNC_PARAMS")
        check("M7.sync_table_with_%s_refused(-)" % nm, ok and "TWIN_SYNC_FORBIDDEN_PARAM" in msg, msg)
    finally:
        G["TWIN_SYNC_SCALARS"] = keep_
check("M7.sync_table_restored", T["twin_sync_param_problems"]() == [])
for nm, rec_, L, needle in (
        ("twin_record_invalid", dict(TREC, saved=False), sync_live(), "TWIN_RECORD_INVALID"),
        ("clam_unapplied", TREC, sync_live(), "CLAM_RECORD_NOT_APPLIED"),
        ("pearl_missing", TREC, sync_live(pearl={"count": 0}), "TWIN_SYNC_PEARL"),
        ("source_is_twin_mi", TREC, sync_live(pearl=dict(sync_live()["pearl"], materials=[MI(PF)])), "TWIN_SYNC_SOURCE|"),
        ("source_read_other_mi", TREC, sync_live(source=dict(copy.deepcopy(go_full), mi=MI(P3))), "TWIN_SYNC_SOURCE_READ"),
        ("source_parent_v2", TREC, sync_live(source=dict(copy.deepcopy(go_full), parent=T["PEARL_V2_MASTER"])), "TWIN_SYNC_SOURCE_PARENT"),
        ("source_unread", TREC, sync_live(source=dict(copy.deepcopy(go_full), vectors={})), "TWIN_SYNC_SOURCE_UNREAD"),
        ("target_missing", TREC, sync_live(targets={MI(PF): twin_target(PF), MI(PD): {"exists": False}}), "TWIN_SYNC_TARGET_MISSING"),
        ("target_parent", TREC, sync_live(targets={MI(PF): dict(twin_target(PF), parent=V3M), MI(PD): twin_target(PD)}),
         "TWIN_SYNC_TARGET_PARENT"),
        ("target_unread", TREC, sync_live(targets={MI(PF): dict(twin_target(PF), scalar_names=[]), MI(PD): twin_target(PD)}),
         "TWIN_SYNC_TARGET_UNREAD"),
        ("noop_pearl_on_v3", TREC, sync_live(pearl=dict(sync_live()["pearl"], materials=[MI(P3)]),
                                             source={"mi": MI(P3), "exists": True, "parent": V3M,
                                                     "scalar_names": sorted(v3_live["scalars"]), "vector_names": sorted(v3_live["vectors"]),
                                                     "scalars": dict(v3_live["scalars"]), "vectors": copy.deepcopy(v3_live["vectors"])}),
         "TWIN_SYNC_NOOP")):
    cr_ = dict(crec, applied=False) if nm == "clam_unapplied" else crec
    ok, msg = refuses(lambda r=rec_, L=L, c=cr_: TSP(r, c, L), needle)
    check("M7.sync_%s_refused(-)" % nm, ok, msg)
srec = {"applied": True, "saved": True, "plan": json.loads(json.dumps(spl))}
for nm, fn, needle in (("synced_value_drift", lambda v: v[MI(PF)]["scalars"].update(Glow=0.2), "TWIN_SYNC_DRIFT"),
                       ("fade_drift", lambda v: v[MI(PD)]["scalars"].update(Fade=0.0), "TWIN_SYNC_DRIFT"),
                       ("unsynced_drift", lambda v: v[MI(PF)]["vectors"]["BaseColor"].__setitem__(0, 0.5), "TWIN_SYNC_DRIFT")):
    v_ = copy.deepcopy(vals1)
    fn(v_)
    ok, msg = refuses(lambda v_=v_: T["twin_sync_revert_plan"](srec, {"targets": {m_: dict(x, exists=True) for m_, x in v_.items()}}),
                      needle)
    check("M7.sync_revert_with_%s_refused(-)" % nm, ok, msg)
ok, msg = refuses(lambda: T["twin_sync_revert_plan"](dict(srec, saved=False), {"targets": {}}), "TWIN_SYNC_RECORD_INVALID")
check("M7.sync_revert_unsaved_record_refused(-)", ok, msg)


# M8. TWIN_SYNC + REVERT end to end (FAKE editor: v3 master/MI -> twin masters/MIs -> variant MI); only the actor lookup faked
def fake_sync_env(setter_lies=False):
    fe = fake_v3_env()
    tmpb = tempfile.mkdtemp(prefix="s3sync_")
    keep = {k: G[k] for k in ("unreal", "HERE")}
    G.update(unreal=fe, HERE=tmpb + "/")
    try:
        for k in (PF, PD):
            T["run_build_clam_mat"]("RUNT", k, {})
        T["run_build_clam_mat"]("RUNGO", GO, {})
    finally:
        G.update(keep)
    fe.dirty.clear()
    fe.saved.clear()
    mel = fe.MaterialEditingLibrary
    s0, v0 = mel.set_material_instance_scalar_parameter_value, mel.set_material_instance_vector_parameter_value

    def ss(mi, k, v):
        fe.dirty.add(mi.path)
        if not setter_lies:
            s0(mi, k, v)

    def vs(mi, k, v):
        fe.dirty.add(mi.path)
        if not setter_lies:
            v0(mi, k, v)
    mel.set_material_instance_scalar_parameter_value, mel.set_material_instance_vector_parameter_value = ss, vs
    proj = tmpb + "/proj/"
    for k in (PF, PD):                                       # stand-in .uasset files for the byte backup
        f = proj + "Content/" + MI(k)[len("/Game/"):] + ".uasset"
        os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f, "wb") as h:
            h.write(("fake uasset " + k).encode())
    with open(tmpb + "/twin.json", "w", encoding="utf-8") as h:
        json.dump(TREC, h)
    over = {"unreal": fe, "HERE": tmpb + "/", "PROJECT": proj, "TWIN_RECORD": tmpb + "/twin.json",
            "TWIN_SYNC_RECORD": tmpb + "/sync.json", "BACKUP_ROOT_TWIN_SYNC": tmpb + "/bk/PreS3PearlTwinSync-",
            "_twin_sync_live": lambda world: {"pearl": sync_live()["pearl"],
                                              "targets": {MI(k): G["_mi_full_values"](MI(k)) for k in (PF, PD)},
                                              "source": G["_mi_full_values"](MI(GO))}}
    os.makedirs(tmpb + "/bk")
    return fe, tmpb, over


def with_globals(over, fn):
    keep = {k: G[k] for k in over}
    G.update(over)
    try:
        try:
            return fn(), None
        except PlanError as exc:
            return None, str(exc)
    finally:
        G.update(keep)


fe, tmpb, over = fake_sync_env()
vals_mi = lambda k: {"scalars": dict(fe.mats[MI(k)].sc), "vectors": {q: [c.r, c.g, c.b, c.a] for q, c in fe.mats[MI(k)].vc.items()}}  # noqa: E731
orig = {k: vals_mi(k) for k in (PF, PD)}
check("M8.env_twins_carry_v3_values(+)", all(orig[k]["scalars"]["Glow"] == 0.42 and orig[k]["scalars"]["Fade"] == 1.0 for k in (PF, PD))
      and fe.mats[MI(GO)].sc["Glow"] == 0.03, orig[PF]["scalars"].get("Glow"))
r_, err = with_globals(over, lambda: G["run_clam_pearl_twin_sync"]("RUNS", {}, None))
now = {k: vals_mi(k) for k in (PF, PD)}
check("M8.sync_ok_saves_only_the_two_mis(+)", r_ is not None and sorted(fe.saved) == sorted([MI(PF), MI(PD)]) and not fe.dirty and
      os.path.exists(tmpb + "/sync.json"), err or fe.saved)
if r_ is not None:
    srec_ = json.load(open(tmpb + "/sync.json", encoding="utf-8"))
    check("M8.synced_values_equal_variant(+)", all(T["_snap_close"](now[k]["scalars"][p], vv["scalars"][p]) for k in (PF, PD)
                                                   for p in T["TWIN_SYNC_SCALARS"]) and
          all(T["near"](now[k]["vectors"][p], vv["vectors"][p], 1e-9) for k in (PF, PD) for p in T["TWIN_SYNC_VECTORS"]),
          now[PF]["scalars"].get("Glow"))
    check("M8.fade_baseopacity_breath_untouched(+)", all(now[k]["scalars"][p] == orig[k]["scalars"][p] for k in (PF, PD)
                                                         for p in T["TWIN_SYNC_FORBIDDEN"] if p in orig[k]["scalars"]) and
          now[PF]["scalars"]["BaseOpacity"] == 1.0, {k: {p: now[k]["scalars"].get(p) for p in T["TWIN_SYNC_FORBIDDEN"]} for k in (PF, PD)})
    check("M8.record_holds_originals_and_backup(+)", srec_["saved"] and srec_["applied"] and
          all(t["before"] == json.loads(json.dumps(orig[t["key"]])) for t in srec_["plan"]["targets"]) and
          sorted(os.listdir(r_["backup"])) == sorted(["MI_PearlClam_Pearl_Fade.uasset", "MI_PearlClam_Pearl_Dither.uasset", "sync.json"]),
          os.listdir(r_["backup"]))
    check("M8.skipped_none_on_built_twins(+)", r_["skipped"] == {PF: [], PD: []}, r_["skipped"])
    fe.saved.clear()
    r2_, err2 = with_globals(over, lambda: G["run_clam_pearl_twin_sync_revert"]("RUNR", None))
    back = {k: vals_mi(k) for k in (PF, PD)}
    check("M8.revert_exact_and_saved(+)", r2_ is not None and back == orig and sorted(fe.saved) == sorted([MI(PF), MI(PD)]) and
          not os.path.exists(tmpb + "/sync.json") and os.path.exists(tmpb + "/sync.json.reverted-RUNR"), err2)
fe, tmpb, over = fake_sync_env()
r_, err = with_globals(over, lambda: G["run_clam_pearl_twin_sync"]("RUNS", {}, None))
fe.saved.clear()
fe.mats[MI(PF)].sc["Glow"] = 0.25                                  # someone tuned the twin after the sync
r2_, err2 = with_globals(over, lambda: G["run_clam_pearl_twin_sync_revert"]("RUNR", None))
check("M8.revert_with_drift_refused_nothing_saved(-)", r_ is not None and r2_ is None and "TWIN_SYNC_DRIFT" in (err2 or "") and
      fe.saved == [] and os.path.exists(tmpb + "/sync.json"), err2)
fe, tmpb, over = fake_sync_env(setter_lies=True)
r_, err = with_globals(over, lambda: G["run_clam_pearl_twin_sync"]("RUNS", {}, None))
check("M8.lying_setter_caught_by_readback_nothing_saved(-)", r_ is None and "TWIN_SYNC_READBACK" in (err or "") and fe.saved == [], err)
fe, tmpb, over = fake_sync_env()
fe.dirty.add("/Game/Someone/Else")
r_, err = with_globals(over, lambda: G["run_clam_pearl_twin_sync"]("RUNS", {}, None))
check("M8.foreign_dirty_package_refused_nothing_saved(-)", r_ is None and "DIRTY_SCOPE" in (err or "") and fe.saved == [], err)

# ------------------------------------------------------------------ report
fails = [r for r in RESULTS if not r["ok"]]
rep = {"checks": len(RESULTS), "failed": len(fails), "fails": fails, "results": RESULTS,
       "millstone_top": {k: mill[k] for k in ("axis_r15_height_cm", "peak_height_cm", "plateaus", "clam_disc", "base_band")},
       "apply_plan_keyed_example": {"location": plan["location"], "top_z": plan["top_z"],
                                    "clams": [(c["label"], c["verdict"], c["inside_stone_cm"], c["top_above_stone_cm"])
                                              for c in plan["clams"]["rows"]]}}
with open(os.path.join(HERE, "test_s3_props_report.json"), "w", encoding="utf-8") as f:
    json.dump(rep, f, indent=1)
print("TOTAL %d  FAILED %d" % (len(RESULTS), len(fails)))
sys.exit(1 if fails else 0)
