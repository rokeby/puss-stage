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
                                         "material": "Pearl_v3"}, True, False), "CLAM_MATERIAL"),
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
check("J7.swap_record_path_separate", T["PEARL_SWAP_RECORD"] != T["CLAM_RECORD"] and not os.path.exists(T["PEARL_SWAP_RECORD"]))

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
