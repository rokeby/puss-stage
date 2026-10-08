"""OFFLINE (numpy only, no Blender, no Unreal): the PearlClam shells in the shared ASSEMBLY frame (Blender cm, Z up,
front = -Y, hinge = +Y), read straight from the export FBX files the UE meshes were imported from.

  bottom(): verts (N,3) cm, tris (M,3)            -- SM_PearlClam_Bottom.fbx (pivot = assembly origin)
  lid(deg): verts (N,3) cm, tris (M,3)            -- SM_PearlClam_Lid.fbx (hinge-relative), placed at PIVOT and rotated
                                                     by -deg about +X (Blender), which LIFTS the front tip
                                                     (hinge_render.py does exactly this; clam_open.py open roll = -deg)

Reading: binary FBX 7.4 via the parser in ../S3Millstone/fbx_top_measure.py (imported, not edited).  The geometry is
stored in the Blender frame in METRES (UnitScaleFactor 100, Model Lcl Rotation (-90,0,0) turns it Y-up)
[meas: parse() of both files, 8 Oct; fbx_top_measure.py:113-121 documents the same for the millstone].
Cache: the parsed arrays go to the scratch cache dir (CACHE) as .npy; they are regenerated if missing.
"""
import os
import struct
import sys
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/") + "/"
EXPORT = "E:/PussStage/DerivedAssets/PearlClam/Export/"
PIVOT = np.array([0.0, 47.86, 30.02])          # manifest parts.SM_PearlClam_Lid.place_at_cm [decl]
CACHE = os.environ.get("CLAMSLIME_CACHE", HERE + "_cache/")

sys.path.insert(0, HERE + "../S3Millstone")
import fbx_top_measure as _ftm                 # noqa: E402  (parse helpers, read-only use)


def parse_mesh(path):
    """-> (verts (N,3) file units, polygon index array, global settings, model rows) for a single-geometry FBX."""
    with open(path, "rb") as f:
        buf = memoryview(f.read())
    version = struct.unpack_from("<I", buf, 23)[0]
    wide = version >= 7500
    verts, pvi = None, None
    for name, _p, (a, b) in _ftm._nodes(buf, 27, len(buf), wide):
        if name != "Objects":
            continue
        for n2, _p2, (a2, b2) in _ftm._nodes(buf, a, b, wide):
            if n2 != "Geometry":
                continue
            for n3, p3, _r in _ftm._nodes(buf, a2, b2, wide):
                if n3 == "Vertices" and verts is None:
                    verts = np.asarray(p3[0], dtype=np.float64).reshape(-1, 3)
                if n3 == "PolygonVertexIndex" and pvi is None:
                    pvi = np.asarray(p3[0], dtype=np.int64)
    meta = _ftm.parse(path)
    return verts, pvi, meta["global"], meta["models"]


def triangulate(pvi):
    ends = np.nonzero(pvi < 0)[0]
    starts = np.concatenate([[0], ends[:-1] + 1])
    idx = pvi.copy()
    idx[ends] = -idx[ends] - 1
    sizes = ends - starts + 1
    if np.all(sizes == 3):
        return idx.reshape(-1, 3)
    out = []
    for s, n in zip(starts, sizes):                 # fan (only reached for non-tri meshes)
        for k in range(1, n - 1):
            out.append((idx[s], idx[s + k], idx[s + k + 1]))
    return np.asarray(out, dtype=np.int64)


def _load(part):
    os.makedirs(CACHE, exist_ok=True)
    fv, ft = CACHE + "%s_v.npy" % part, CACHE + "%s_t.npy" % part
    src = EXPORT + "SM_PearlClam_%s.fbx" % part
    stamp = CACHE + "%s.stamp" % part
    key = "%d|%d" % (os.path.getsize(src), int(os.path.getmtime(src)))
    if os.path.exists(fv) and os.path.exists(ft) and os.path.exists(stamp) and open(stamp).read() == key:
        return np.load(fv), np.load(ft)
    v, pvi, glob, models = parse_mesh(src)
    assert float(glob.get("UnitScaleFactor", 0)) == 100.0, glob            # metres in the file
    rot = models[0].get("Lcl Rotation", [0, 0, 0])
    assert abs(rot[0] + 90.0) < 0.01 and abs(rot[1]) < 0.01 and abs(rot[2]) < 0.01, rot
    v = v * 100.0                                                           # -> cm, Blender frame
    t = triangulate(pvi)
    np.save(fv, v)
    np.save(ft, t)
    open(stamp, "w").write(key)
    return v, t


def rot_x(deg):
    a = np.radians(deg)
    c, s = np.cos(a), np.sin(a)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])


def lid_world(v_rel, deg):
    """Lid hinge-relative verts -> assembly frame at opening angle `deg` (rotation -deg about +X through PIVOT)."""
    return v_rel @ rot_x(-deg).T + PIVOT


def bottom():
    return _load("Bottom")


def lid(deg=0.0):
    v, t = _load("Lid")
    return lid_world(v, deg), t


def lid_rel():
    return _load("Lid")


def mantle():
    """Mantle at the assembly origin (manifest place_at_cm [0,0,0])."""
    return _load("Mantle")


def pearl():
    """The live pearl mesh SM_PearlClam_Pearl_v2 at its live relative location (0, 0, 35.64) cm
    [decl ../S3Millstone/s3_pearlclam_apply_record.json plan.parts.Pearl.rel; the PEARL_SWAP kept the transform]."""
    v, t = _load("Pearl_v2")
    return v + np.array([0.0, 0.0, 35.64]), t


def vertex_normals(v, t):
    fn = np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]])        # area-weighted
    n = np.zeros_like(v)
    for k in range(3):
        np.add.at(n, t[:, k], fn)
    ln = np.linalg.norm(n, axis=1)
    ln[ln == 0] = 1.0
    return n / ln[:, None]


if __name__ == "__main__":
    bv, bt = bottom()
    lv, lt = lid(0.0)
    print("bottom", bv.shape, bt.shape, bv.min(0).round(2), bv.max(0).round(2))
    print("lid@0", lv.shape, lt.shape, lv.min(0).round(2), lv.max(0).round(2))
