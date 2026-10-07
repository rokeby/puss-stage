"""Offline harness for s3mg_bench.py (no Unreal). Mocks only the math and the asset probes.
Run: python test_s3mg_offline.py  -> prints PASS/FAIL lines, writes test_s3mg_offline_report.json, exit 1 on any FAIL.
"""
import json
import math
import runpy
import sys
import types

import numpy as np

HERE = "E:/PussStage/Saved/CodexConductor/S3MarbleGrime/"
B = runpy.run_path(HERE + "s3mg_bench.py")
fails = []
passes = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else " | " + str(detail)))
    (passes if cond else fails).append(name)


# ---- mock UE math (rotator roll/pitch/yaw in degrees; X fwd, Y right, Z up)
class V:
    def __init__(self, x=0, y=0, z=0):
        self.x, self.y, self.z = float(x), float(y), float(z)

    def a(self):
        return np.array([self.x, self.y, self.z])


class Rot:
    def __init__(self, roll=0.0, pitch=0.0, yaw=0.0):
        self.roll, self.pitch, self.yaw = roll, pitch, yaw


def rmat(r):
    cr, sr = math.cos(math.radians(r.roll)), math.sin(math.radians(r.roll))
    cp, sp = math.cos(math.radians(r.pitch)), math.sin(math.radians(r.pitch))
    cy, sy = math.cos(math.radians(r.yaw)), math.sin(math.radians(r.yaw))
    x = np.array([cp * cy, cp * sy, sp])
    y = np.array([sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, -sr * cp])
    z = np.array([-(cr * sp * cy + sr * sy), cy * sr - cr * sp * sy, cr * cp])
    return np.stack([x, y, z], 1)          # columns = local axes in world (UE FRotationMatrix)


class T:
    def __init__(self, loc, rot, scale):
        self.loc, self.R = loc.a(), rmat(rot)


def to_rot(x, z):
    x = x / np.linalg.norm(x)
    y = np.cross(z, x)
    y /= np.linalg.norm(y)
    z = np.cross(x, y)
    pitch = math.degrees(math.atan2(x[2], math.hypot(x[0], x[1])))
    yaw = math.degrees(math.atan2(x[1], x[0]))
    sy_ = rmat(Rot(0, pitch, yaw))[:, 1]
    roll = math.degrees(math.atan2(np.dot(z, sy_), np.dot(y, sy_)))
    return Rot(roll, pitch, yaw)


ML = types.SimpleNamespace(
    inverse_transform_location=lambda t, p: V(*(t.R.T @ (p.a() - t.loc))),
    inverse_transform_direction=lambda t, d: V(*(t.R.T @ d.a())),
    transform_location=lambda t, p: V(*(t.R @ p.a() + t.loc)),
    transform_direction=lambda t, d: V(*(t.R @ d.a())),
    make_rot_from_xz=lambda x, z: to_rot(x.a(), z.a()))
U = types.SimpleNamespace(MathLibrary=ML, Vector=V, Rotator=Rot, Transform=T)

plan = json.load(open(HERE + "s3mg_bench_plan.json"))
landed = T(V(*B["ROOT_LANDED"]["loc"]), Rot(), V(1, 1, 1))

# 1) identity motion: lights at the plan, facing +Y (yaw 90)
for L in plan["lights"]:
    p, r = B["landed_to_now"](U, landed, landed, L["location"], L["x"], L["z"])
    check("light_identity_" + L["name"], np.allclose(p.a(), L["location"], atol=1e-6) and abs(r.yaw - 90) < 1e-6
          and abs(r.pitch) < 1e-6 and abs(r.roll) < 1e-6, (p.a(), vars(r)))

# 2) rigid motion: root sunk 3500 cm and yawed 12 deg -> the light keeps its ROOT-LOCAL pose
now = T(V(11421.97275, 160000.0, -3620.0), Rot(0, 0, 12), V(1, 1, 1))
L = plan["lights"][1]
p, r = B["landed_to_now"](U, landed, now, L["location"], L["x"], L["z"])
loc_local_landed = landed.R.T @ (np.array(L["location"]) - landed.loc)
loc_local_now = now.R.T @ (p.a() - now.loc)
check("light_rigid_local_pose", np.allclose(loc_local_landed, loc_local_now, atol=1e-6) and abs(r.yaw - 102) < 1e-6,
      (loc_local_landed, loc_local_now, vars(r)))

# 3) band via its print-decal anchor: identity -> plan; axes = decal convention (X into the wall = +Y)
b = plan["band"]
r0 = b["anchor"]["landed_rot"]
anc = T(V(*b["anchor"]["landed_loc"]), Rot(r0["roll"], r0["pitch"], r0["yaw"]), V(1, 1, 1))
p, r = B["landed_to_now"](U, anc, anc, b["location"], b["x"], b["z"])
check("band_identity", np.allclose(p.a(), b["location"], atol=1e-6), p.a())
check("band_axes_into_wall", np.allclose(rmat(r)[:, 0], [0, 1, 0], atol=1e-9) and np.allclose(rmat(r)[:, 2], b["z"], atol=1e-9),
      rmat(r))

# 4) the mock's rotator convention agrees with the placement tool's recorded axes (control for the mock itself)
pl = {d["label"]: d for d in json.load(open("E:/PussStage/DerivedAssets/FlatV3/HandPrints/placement_S03.json"))["decals"]}
d = pl[b["anchor"]["label"]]
R = rmat(Rot(d["rotation"]["roll"], d["rotation"]["pitch"], d["rotation"]["yaw"]))
check("mock_matches_placement_axes", np.allclose(R[:, 0], d["axes"]["x"], atol=1e-5)
      and np.allclose(R[:, 1], d["axes"]["y"], atol=1e-5) and np.allclose(R[:, 2], d["axes"]["z"], atol=1e-5),
      (R, d["axes"]))
# negative control: a wrong rotator must fail the same comparison
Rw = rmat(Rot(d["rotation"]["roll"] + 5, d["rotation"]["pitch"], d["rotation"]["yaw"]))
check("mock_negative_control", not np.allclose(Rw[:, 2], d["axes"]["z"], atol=1e-5))

# 5) plan content = Gary's pick
check("variant_C_three_3x1p2_strips_diffuse_0p1",
      len(plan["lights"]) == 3 and all(l["source_width"] == 300 and l["source_height"] == 120 for l in plan["lights"])
      and B["VARIANTS"]["C"]["lights"]["diffuse_scale"] == 0.10, plan["lights"])
check("stills_one_fraction", B["STILLS"]["fractions"] == [0.3])
check("tags_distinct_from_shore", B["TAG"] != "RigAtmos.S3ShoreGround"
      and not "ZZ_S3ShoreGroundBench".startswith(B["PREFIX"]))

# 6) assets idempotency (mock probes)
g = B["stage_assets"].__globals__
names = ("_u", "pie_world_or_none", "editor_world", "census", "texture_state", "master_state",
         "import_textures", "build_grease_master", "write_verified")
saved = {k: g[k] for k in names}
try:
    fake_u = types.SimpleNamespace(log=lambda *a: None,
                                   SystemLibrary=types.SimpleNamespace(collect_garbage=lambda: None))
    good_tex = {a: {"class": "Texture2D", "srgb": s, "compression": "TextureCompressionSettings." + c,
                    "size": [2048, 2048]} for f, (a, s, c) in B["TEXTURES"].items()}
    good_master = {"domain": "MaterialDomain.MD_DEFERRED_DECAL", "blend": "BlendMode.BLEND_TRANSLUCENT",
                   "scalars": sorted(B["MASTER_SCALARS"]), "textures": ["GreaseMask", "PrintNormal"]}
    created = []
    g.update(_u=lambda: fake_u, pie_world_or_none=lambda: None, editor_world=lambda: None, census=lambda: {},
             write_verified=lambda p, d: p,
             import_textures=lambda: created.append("t") or good_tex,
             build_grease_master=lambda: created.append("m") or good_master)
    g.update(texture_state=lambda a: good_tex[a], master_state=lambda: good_master)
    check("assets_reused_when_all_present", "REUSED" in B["stage_assets"]("S3MG-T1", {}) and not created)
    g.update(texture_state=lambda a: None, master_state=lambda: None)
    check("assets_created_when_none", "CREATED" in B["stage_assets"]("S3MG-T2", {}) and created == ["t", "m"])

    def expect_raise(name, token, **over):
        g.update(**over)
        try:
            B["stage_assets"]("S3MG-T", {})
            check(name, False, "no raise")
        except Exception as e:
            check(name, token in str(e), e)

    expect_raise("assets_partial_refused", "PARTIAL_ASSETS",
                 texture_state=lambda a: good_tex[a] if a.endswith("RoughGrime") else None, master_state=lambda: None)
    expect_raise("assets_mismatch_refused", "REUSE_MISMATCH",
                 texture_state=lambda a: good_tex[a], master_state=lambda: dict(good_master, scalars=["x"]))
    expect_raise("assets_wrong_srgb_refused", "REUSE_MISMATCH",
                 texture_state=lambda a: dict(good_tex[a], srgb=not good_tex[a]["srgb"]), master_state=lambda: good_master)
    expect_raise("assets_refuse_in_pie", "PIE_RUNNING", pie_world_or_none=lambda: object())
finally:
    g.update(saved)

# 7) runner control flow + request JSONs
src = open(HERE + "s3mg_run.py", encoding="utf-8").read().split('"""', 2)[2]   # code only, not the docstring
check("runner_single_ok_after_stage", src.count("_OK|") == 1 and src.index("_OK|run=") > src.index("run_stage\"](")
      and "except Exception" in src)
check("runner_rejects_placeholder_run", '"REPLACE" in run' in src)
check("runner_purges_cache", "purge_saved_module_cache.py" in src)
for st in ("assets", "verify_assets", "apply", "stills", "restore", "census"):
    req = json.load(open(HERE + "s3mg_%s_request.json" % st))
    check("request_" + st, req["arguments"]["tool_name"] == "ExecuteProjectPythonFile" and
          req["arguments"]["arguments"]["relativeSavedPath"] == "CodexConductor/S3MarbleGrime/s3mg_run_%s.py" % st)
    w = open(HERE + "s3mg_run_%s.py" % st, encoding="utf-8").read()
    check("wrapper_" + st, '"S3MG_STAGE": "%s"' % st in w)

# 8) forbidden calls absent from the bench
bsrc = open(HERE + "s3mg_bench.py", encoding="utf-8").read()
for bad in ("save_asset", "save_packages", "save_current_level", "save_map", "end_play", "request_end_play",
            "delete_material_expression", "delete_all_material_expressions", "load_map", "quit_editor",
            "EditorLevelLibrary", "set_level_viewport", "get_sequence_player", "k2_get_"):
    check("no_" + bad, bad not in bsrc)

print("SUMMARY %d passed, %d failed" % (len(passes), len(fails)))
json.dump({"passed": len(passes), "failed": fails}, open(HERE + "test_s3mg_offline_report.json", "w"), indent=1)
sys.exit(1 if fails else 0)
