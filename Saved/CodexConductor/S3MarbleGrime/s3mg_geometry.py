"""S3 marble grime prep (OFFLINE, 7 Oct): camera -> wall geometry + mirror-angle light for variant C.

Inputs (read-only):
  PassageStills manifests (S3 main camera pose = still i=0, frac 0.3, seconds_into_passage 78):
    Saved/CodexConductor/PassageStills/PSTILLS-S3-20261007-173228-floathold/passage_stills_manifest.json
    Saved/CodexConductor/PassageStills/PSTILLS-S3-20261007-144232-held/passage_stills_manifest.json
  DerivedAssets/FlatV3/HandPrints/walls_S03.json   (wall planes, probe 6 Oct)
  DerivedAssets/FlatV3/HandPrints/placement_S03.json (449 decals as placed, run 115927)
Output: DerivedAssets/S3Marble/Grime_20261007/geometry.json

Camera model: UE rotator (yaw about Z, pitch about Y, roll 0), horizontal FOV, aspect 16:9.
Mirror light: for a target wall point P seen from camera C, the light that reflects into the
camera at P lies on the line from the camera's mirror image C' (through the wall plane) through P,
continued INTO the room.  The light plane is chosen behind the camera (y < C.y) so it is off-frame.
"""
import json
import math
import os

import numpy as np

ROOT = "E:/PussStage"
OUT = ROOT + "/DerivedAssets/S3Marble/Grime_20261007"
MANIFESTS = [ROOT + "/Saved/CodexConductor/PassageStills/PSTILLS-S3-20261007-173228-floathold/passage_stills_manifest.json",
             ROOT + "/Saved/CodexConductor/PassageStills/PSTILLS-S3-20261007-144232-held/passage_stills_manifest.json"]
WALLS = ROOT + "/DerivedAssets/FlatV3/HandPrints/walls_S03.json"
PLACEMENT = ROOT + "/DerivedAssets/FlatV3/HandPrints/placement_S03.json"
RES = (1600, 900)


def cam_basis(rot):
    y, p = math.radians(rot["yaw"]), math.radians(rot["pitch"])
    fwd = np.array([math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p)])
    right = np.array([-math.sin(y), math.cos(y), 0.0])
    up = np.cross(right, fwd)          # UE is left-handed in display; this gives +Z-ish up for pitch 0
    up = up / np.linalg.norm(up)
    if up[2] < 0:
        up = -up
    return fwd, right, up


def pixel_ray(pose, px, py, res=RES):
    fwd, right, up = cam_basis(pose["rot"])
    th = math.tan(math.radians(pose["fov_deg"]) / 2)
    tv = th / pose["aspect"]
    sx = (2 * (px + 0.5) / res[0] - 1) * th
    sy = (1 - 2 * (py + 0.5) / res[1]) * tv
    d = fwd + sx * right + sy * up
    return d / np.linalg.norm(d)


def project(pose, P, res=RES):
    fwd, right, up = cam_basis(pose["rot"])
    C = np.array(pose["loc"], float)
    v = np.asarray(P, float) - C
    z = v @ fwd
    th = math.tan(math.radians(pose["fov_deg"]) / 2)
    tv = th / pose["aspect"]
    sx = (v @ right) / z / th
    sy = (v @ up) / z / tv
    return ((sx + 1) / 2 * res[0] - 0.5, (1 - sy) / 2 * res[1] - 0.5, z)


def hit_plane_y(C, d, y):
    t = (y - C[1]) / d[1]
    return C + t * d, t


def main():
    poses = []
    for m in MANIFESTS:
        man = json.load(open(m))
        for s in man["stills"]:
            if s.get("pose"):
                poses.append({"run": man["run_id"], "i": s["i"], "fraction": s["fraction"],
                              "seconds_into_passage": s.get("seconds_into_passage"), "file_exists": s.get("exists"),
                              "luma": s.get("luma"), **s["pose"]})
    main_pose = [p for p in poses if p["run"].endswith("floathold") and p["i"] == 0][0]
    walls = {w["id"]: w for w in json.load(open(WALLS))["walls"]}
    wR = walls["R"]
    wall_y = wR["origin_cm"][1]                     # 160999 (inner face, inward normal -Y)
    floor_z = wR["floor_z_cm"]
    C = np.array(main_pose["loc"], float)

    # frame corners / centre on the wall plane
    pts = {}
    for name, (px, py) in {"tl": (0, 0), "tr": (1599, 0), "bl": (0, 899), "br": (1599, 899), "c": (800, 450),
                           "top_c": (800, 0)}.items():
        d = pixel_ray(main_pose, px, py)
        P, t = hit_plane_y(C, d, wall_y)
        pts[name] = {"px": [px, py], "wall_xz": [round(P[0], 1), round(P[2], 1)], "dist_cm": round(t, 1)}
    # predicted floor/wall junction row at the frame centre column: project (x_c, wall_y, floor_z)
    xc = pts["c"]["wall_xz"][0]
    junction = project(main_pose, [xc, wall_y, floor_z])
    top_liner = project(main_pose, [xc, wall_y, 600.0])

    # decals on R visible in frame
    dec = json.load(open(PLACEMENT))["decals"]
    vis = []
    for d in dec:
        if d["wall"] != "R":
            continue
        u, v, z = project(main_pose, d["location"])
        if z > 0 and -50 <= u <= 1650 and -50 <= v <= 950:
            vis.append({"id": d["id"], "label": d["label"], "kind": d["kind"], "mi": d["material_instance"],
                        "element": d["element_id"], "flip": d["flip"], "loc": d["location"],
                        "size_cm": d["size_cm"], "roll_on_wall_deg": d["roll_on_wall_deg"],
                        "px": [round(u, 1), round(v, 1)]})
    xs = [v_["loc"][0] for v_ in vis]
    zs = [v_["loc"][2] for v_ in vis]

    # bench patch on the wall: the decal band inside the frame, padded 50 cm
    patch = {"x": [min(xs) - 50, max(xs) + 50], "z": [max(0.0, min(zs) - 50), min(600.0, max(zs) + 50)]}
    # mirror light: camera mirror image C' through y = wall_y
    Cm = C.copy()
    Cm[1] = 2 * wall_y - C[1]
    light_plane_y = 159060.0     # 60 cm off the LEFT liner face (159001), behind the camera (C.y = 159250)
    corners = []
    for px_ in (patch["x"][0], patch["x"][1]):
        for pz in (patch["z"][0], patch["z"][1]):
            P = np.array([px_, wall_y, pz])
            s = (light_plane_y - Cm[1]) / (P[1] - Cm[1])
            corners.append((Cm + s * (P - Cm)).tolist())
    corners = np.array(corners)
    # light centred on the reflection of the band centre (the densest print height), also behind the camera
    Pc = np.array([(patch["x"][0] + patch["x"][1]) / 2, wall_y, float(np.median(zs))])
    s_c = (light_plane_y - Cm[1]) / (Pc[1] - Cm[1])
    Lc = Cm + s_c * (Pc - Cm)
    # check: incidence angle at Pc, and that the light is outside the camera frustum
    d_in = (Pc - C) / np.linalg.norm(Pc - C)
    inc_deg = math.degrees(math.acos(abs(d_in[1])))
    lu, lv, lz = project(main_pose, Lc)
    # three strips whose reflections land at three x positions across the frame's print band
    # (structured "windows" read as glisten better than one uniform band; each strip is narrow and bright)
    strips = []
    frame_x = sorted([pts["tl"]["wall_xz"][0], pts["tr"]["wall_xz"][0]])
    for k, fx in enumerate(np.linspace(frame_x[0] + 0.2 * (frame_x[1] - frame_x[0]),
                                       frame_x[1] - 0.2 * (frame_x[1] - frame_x[0]), 3)):
        Pk = np.array([fx, wall_y, float(np.median(zs))])
        sk = (light_plane_y - Cm[1]) / (Pk[1] - Cm[1])
        Lk = Cm + sk * (Pk - Cm)
        strips.append({"name": "ZZ_S3MG_MirrorStrip_%d" % k, "reflects_at_wall_cm": Pk.round(1).tolist(),
                       "location_cm": Lk.round(1).tolist(), "rotation": {"pitch": 0.0, "yaw": 90.0, "roll": 0.0},
                       "source_width_cm": 300.0, "source_height_cm": 120.0,
                       "reflection_size_on_wall_cm": [round(300.0 / sk, 1), round(120.0 / sk, 1)],
                       "outside_frame_px": [round(v_, 1) for v_ in project(main_pose, Lk)[:2]]})
    full_w = float(corners[:, 0].max() - corners[:, 0].min())
    full_h = float(corners[:, 2].max() - corners[:, 2].min())
    # proposal: a STRIP (not the whole mirror rectangle): narrow and bright -> high spec/diffuse ratio,
    # its reflection is a band the prints cross.  Width = mirror width (covers the band's length).
    strip = {"width_cm": round(min(full_w, 2000.0), 1), "height_cm": 120.0}
    # rotation: the rect light emits along its local +X; face +Y (toward the R wall) => yaw 90
    light = {
        "type": "RectLight",
        "location_cm": [round(float(Lc[0]), 1), round(float(Lc[1]), 1), round(float(Lc[2]), 1)],
        "rotation": {"pitch": 0.0, "yaw": 90.0, "roll": 0.0},
        "source_width_cm": strip["width_cm"], "source_height_cm": strip["height_cm"],
        "barn_door_angle_deg": 20.0, "barn_door_length_cm": 40.0,
        "diffuse_scale_proposal": 0.15, "specular_scale": 1.0,
        "mirror_rect_full_cm": [round(full_w, 1), round(full_h, 1)],
        "mirror_rect_corners_cm": np.round(corners, 1).tolist(),
        "projected_px": [round(lu, 1), round(lv, 1)], "outside_frame": not (0 <= lu < 1600 and 0 <= lv < 900 and lz > 0),
        "strips_proposal": strips,
        "incidence_deg_at_band_centre": round(inc_deg, 2),
        "band_centre_on_wall_cm": Pc.round(1).tolist(),
        "dist_light_to_wall_cm": round(wall_y - light_plane_y, 1),
        "dist_camera_to_wall_cm": round(wall_y - C[1], 1),
        "magnification_wall_to_light": round(float(s_c), 3),
    }
    out = {"tool": "s3mg_geometry.py", "main_pose": main_pose, "all_poses": poses,
           "wall": {"id": "R", "plane_y_cm": wall_y, "inward_normal": wR["inward_normal"], "floor_z_cm": floor_z,
                    "liner_actor": "S3 Marble Inner Wall Right (StaticMeshActor_350)",
                    "liner_mi": "/Game/InfinityStage/Dev/Materials/MI_S3_Marble_Tiling_Daylight_R0",
                    "attach_actor": wR["attach_actor_label"]},
           "frame_on_wall": pts,
           "check_junction_row_px": round(junction[1], 1), "check_liner_top_row_px": round(top_liner[1], 1),
           "visible_R_decals": len(vis), "decals": vis, "bench_patch_cm": patch, "mirror_light": light}
    os.makedirs(OUT, exist_ok=True)
    json.dump(out, open(OUT + "/geometry.json", "w"), indent=1)
    print(json.dumps({k: out[k] for k in ("frame_on_wall", "check_junction_row_px", "check_liner_top_row_px",
                                         "visible_R_decals", "bench_patch_cm", "mirror_light")}, indent=1))


if __name__ == "__main__":
    main()
