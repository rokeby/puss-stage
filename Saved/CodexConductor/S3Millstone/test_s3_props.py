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
