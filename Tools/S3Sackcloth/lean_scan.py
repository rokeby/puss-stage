"""Blender headless: per-figure lean over the anim (head vs pelvis horizontal), torso pitch, head->spine_05 in the head
bone frame. Offline measurement for s3_sack_livecloth v2 pins. Usage: blender -b --factory-startup --python lean_scan.py -- <fig> <out.json>"""
import bpy, json, math, sys
from mathutils import Matrix, Vector

fig, out = sys.argv[sys.argv.index("--") + 1:][:2]
man = json.load(open("E:/PussStage/DerivedAssets/S3Sackcloth/bodies/export_manifest.json"))
row = [r for r in man["figures"] if r["id"] == fig][0]
fps = float(row["anim_fps_n_over_len"])
sc = bpy.context.scene
sc.render.fps = max(1, int(round(fps)))
sc.render.fps_base = sc.render.fps / fps
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
o0 = set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=row["anim_fbx"]["file"], use_anim=True, ignore_leaf_bones=False, automatic_bone_orientation=False)
arms = [o for o in bpy.data.objects if o not in o0 and o.type == "ARMATURE"]
assert len(arms) == 1, arms
C = arms[0]
act = C.animation_data.action
f0, f1 = act.frame_range
pb = C.pose.bones


def W(name, tail=False):
    b = pb[name]
    return C.matrix_world @ (b.tail if tail else b.head)


sc.frame_set(int(f0 + row["pose_source_seconds"] * fps))
hz = W("head").z
scale = 0.01 if hz > 20 else 1.0
want = row["pose_head_cm"][2] / 100.0
rows = []
step = 6
f = int(f0)
while f <= f1:
    sc.frame_set(f)
    t = (f - f0) / fps
    P = {n: W(n) * scale for n in ("pelvis", "spine_03", "spine_05", "neck_01", "head")}
    P["head_tail"] = W("head", True) * scale
    hm = (C.matrix_world @ pb["head"].matrix)
    rot = hm.to_3x3().normalized()
    lean = Vector((P["head"].x - P["pelvis"].x, P["head"].y - P["pelvis"].y))
    tors = P["neck_01"] - P["pelvis"]
    tilt = math.degrees(math.acos(max(-1, min(1, tors.normalized().z))))
    s5_local = rot.inverted() @ (P["spine_05"] - P["head"])
    s5_world = P["spine_05"] - P["head"]
    rows.append({"t": round(t, 3), "lean_m": round(lean.length, 4), "torso_tilt_deg": round(tilt, 2),
                 "head_z": round(P["head"].z, 4), "pelvis_z": round(P["pelvis"].z, 4),
                 "spine05_minus_head_world": [round(c, 4) for c in s5_world],
                 "spine05_in_head_local": [round(c, 4) for c in s5_local],
                 "head_up_world": [round(c, 4) for c in (rot @ Vector((0, 1, 0)))]})
    f += step
s0 = row["section_start_s"]
s1 = s0 + row["section_source_duration_s"]
win = [r for r in rows if s0 <= r["t"] <= s1]


def stats(rs, k):
    v = sorted(r[k] for r in rs)
    return {"min": v[0], "p50": v[len(v) // 2], "p90": v[int(0.9 * (len(v) - 1))], "max": v[-1]}


def spread(rs, k):
    import statistics
    xs = [r[k] for r in rs]
    return [round(statistics.pstdev([x[i] for x in xs]), 4) for i in range(3)], [round(statistics.mean([x[i] for x in xs]), 4) for i in range(3)]


res = {"figure": fig, "scale": scale, "pose_head_z_check": [round(hz * scale, 4), want], "frames": len(rows),
       "window_s": [s0, s1], "window_frames": len(win),
       "window": {k: stats(win, k) for k in ("lean_m", "torso_tilt_deg", "head_z")},
       "whole": {k: stats(rows, k) for k in ("lean_m", "torso_tilt_deg")},
       "window_spine05_in_head_local_sd_mean": spread(win, "spine05_in_head_local"),
       "window_spine05_minus_head_world_sd_mean": spread(win, "spine05_minus_head_world"),
       "rows": rows}
json.dump(res, open(out, "w"), indent=1)
print("LEANSCAN_OK", fig, json.dumps({k: res[k] for k in ("pose_head_z_check", "window_s", "window", "whole")}))
