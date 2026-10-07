"""OFFLINE: measure a prop FBX's geometry (minimal binary FBX 7.x parser + numpy).  No Blender, no Unreal.

    python fbx_top_measure.py [Name]        (default GraniteMillstone)

Writes s3_millstone_fbx_measure.json (or s3_prop_fbx_measure_<Name>.json): per-axis extents in cm, the up axis,
the upper-surface height map (2 cm cells, max height per cell), the flat top plateau at several tolerances, and the
support fraction / overhang of a ~1 m clam disc centred on the axis.  The FBX is the exact file IMPORT reads, so
these numbers are [meas] for the import INPUT (not for what Unreal makes of it: that is the IMPORT bounds gate)."""
import json
import os
import struct
import sys
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/") + "/"
DERIVED = "E:/PussStage/DerivedAssets/"


def _read_prop(buf, pos):
    t = chr(buf[pos])
    pos += 1
    scal = {"Y": ("<h", 2), "C": ("<?", 1), "I": ("<i", 4), "F": ("<f", 4), "D": ("<d", 8), "L": ("<q", 8)}
    if t in scal:
        fmt, n = scal[t]
        return struct.unpack_from(fmt, buf, pos)[0], pos + n
    if t in "fdlib":
        n, enc, clen = struct.unpack_from("<III", buf, pos)
        pos += 12
        raw = bytes(buf[pos:pos + clen])
        pos += clen
        if enc == 1:
            raw = zlib.decompress(raw)
        dt = {"f": "<f4", "d": "<f8", "l": "<i8", "i": "<i4", "b": "u1"}[t]
        return np.frombuffer(raw, dtype=dt, count=n), pos
    if t in "SR":
        n = struct.unpack_from("<I", buf, pos)[0]
        pos += 4
        return bytes(buf[pos:pos + n]), pos + n
    raise ValueError("FBX_PROP_TYPE|%r" % t)


def _nodes(buf, pos, end, wide):
    hdr, hsz = ("<QQQB", 25) if wide else ("<IIIB", 13)
    while pos < end:
        endoff, nprops, _plen, nlen = struct.unpack_from(hdr, buf, pos)
        if endoff == 0:
            return
        name = bytes(buf[pos + hsz:pos + hsz + nlen]).decode("ascii", "replace")
        p = pos + hsz + nlen
        props = []
        for _ in range(nprops):
            v, p = _read_prop(buf, p)
            props.append(v)
        yield name, props, (p, endoff)
        pos = endoff


def parse(path):
    with open(path, "rb") as f:
        buf = memoryview(f.read())
    if bytes(buf[:20]) != b"Kaydara FBX Binary  ":
        raise ValueError("NOT_BINARY_FBX")
    version = struct.unpack_from("<I", buf, 23)[0]
    wide = version >= 7500
    out = {"version": version, "geometries": [], "global": {}, "models": []}
    for name, _props, (a, b) in _nodes(buf, 27, len(buf), wide):
        if name == "GlobalSettings":
            for n2, _p2, (a2, b2) in _nodes(buf, a, b, wide):
                if n2 == "Properties70":
                    for n3, p3, _r in _nodes(buf, a2, b2, wide):
                        if n3 == "P" and p3:
                            key = p3[0].decode("ascii", "replace")
                            if key in ("UpAxis", "UpAxisSign", "FrontAxis", "FrontAxisSign", "CoordAxis",
                                       "CoordAxisSign", "UnitScaleFactor", "OriginalUnitScaleFactor"):
                                out["global"][key] = p3[-1]
        if name == "Objects":
            for n2, p2, (a2, b2) in _nodes(buf, a, b, wide):
                if n2 == "Geometry":
                    g = {}
                    for n3, p3, _r in _nodes(buf, a2, b2, wide):
                        if n3 == "Vertices":
                            g["vertices"] = np.asarray(p3[0], dtype=np.float64).reshape(-1, 3)
                        if n3 == "PolygonVertexIndex":
                            g["npolys"] = int((np.asarray(p3[0]) < 0).sum())
                    out["geometries"].append(g)
                if n2 == "Model":
                    m = {"name": p2[1].split(b"\x00")[0].decode("ascii", "replace") if len(p2) > 1 else "?"}
                    for n3, _p3, (a3, b3) in _nodes(buf, a2, b2, wide):
                        if n3 == "Properties70":
                            for n4, p4, _r in _nodes(buf, a3, b3, wide):
                                if n4 == "P" and p4 and p4[0] in (b"Lcl Translation", b"Lcl Rotation",
                                                                     b"Lcl Scaling", b"PreRotation"):
                                    m[p4[0].decode()] = [float(x) for x in p4[-3:]]
                    out["models"].append(m)
    return out


def manifest_size(man):
    v = man.get("validation_blender_clean_reimport") or man.get("validation", {}).get("measured_blender_clean_reimport")
    return [float(x) for x in v["size_cm"]], float(v["min_z_cm"])


def measure(name="GraniteMillstone", clam_diam_cm=100.0):
    path = DERIVED + "%s/Export/SM_%s.fbx" % (name, name)
    man = json.load(open(DERIVED + "%s/Export/SM_%s_manifest.json" % (name, name), encoding="utf-8"))
    want, min_z = manifest_size(man)
    fb = parse(path)
    geos = [g for g in fb["geometries"] if "vertices" in g]
    if len(geos) != 1:
        raise ValueError("GEOMETRY_COUNT|%d" % len(geos))
    v = geos[0]["vertices"]
    # The geometry is stored in the source (Blender, Z-up) frame; the Model carries Lcl Rotation (-90,0,0) that
    # turns it Y-up (measured on SM_GraniteMillstone).  So height = geometry Z when that rotation is present.
    rot = (fb["models"][0].get("Lcl Rotation") if fb["models"] else None) or [0.0, 0.0, 0.0]
    if abs(rot[0] + 90.0) < 0.01 and abs(rot[1]) < 0.01 and abs(rot[2]) < 0.01:
        up = 2
    elif all(abs(x) < 0.01 for x in rot):
        up = int(fb["global"].get("UpAxis", 1))
    else:
        raise ValueError("MODEL_ROTATION_UNHANDLED|%s" % rot)
    size_raw = v.max(0) - v.min(0)
    k = size_raw[up] / want[2]                            # file units per cm, from the manifest height
    vc = v / k
    h = vc[:, up] - vc[:, up].min()                       # height above the lowest vertex, cm
    horiz = [i for i in range(3) if i != up]
    xy = vc[:, horiz] - (vc[:, horiz].max(0) + vc[:, horiz].min(0)) / 2.0
    r = np.hypot(xy[:, 0], xy[:, 1])
    axis = r < 15.0
    top_mid = float(np.median(h[axis]))
    res = {"name": name, "fbx": path, "fbx_bytes": os.path.getsize(path), "fbx_version": fb["version"],
           "global": fb["global"], "models": fb["models"], "vertices": int(len(v)), "polygons": geos[0].get("npolys"),
           "file_units_per_cm": float(k), "up_axis_index": up,
           "size_cm_file_axes": [float(s / k) for s in size_raw], "manifest_size_cm": want, "manifest_min_z_cm": min_z,
           "axis_r15_height_cm": [float(h[axis].min()), float(h[axis].max()), top_mid],
           "peak_height_cm": float(h.max())}
    cell = 2.0
    lo = xy.min(0)
    ij = np.floor((xy - lo) / cell).astype(np.int64)
    shape = ij.max(0) + 1
    zbuf = np.full(shape, -1e9)
    np.maximum.at(zbuf, (ij[:, 0], ij[:, 1]), h)
    occ = zbuf > -1e8
    gx = (np.arange(shape[0]) + 0.5) * cell + lo[0]
    gy = (np.arange(shape[1]) + 0.5) * cell + lo[1]
    GX, GY = np.meshgrid(gx, gy, indexing="ij")
    D = np.hypot(GX, GY)
    res["plateaus"] = {}
    for tol in (1.5, 3.0, 5.0, 10.0):
        flat = occ & (np.abs(zbuf - top_mid) <= tol)
        if flat.any():
            res["plateaus"]["within_%.1fcm_of_axis_top" % tol] = {
                "area_m2": float(flat.sum() * cell * cell / 1e4),
                "extent_cm_file_axes": [float(GX[flat].max() - GX[flat].min() + cell),
                                        float(GY[flat].max() - GY[flat].min() + cell)],
                "equiv_diam_cm": float(2.0 * np.sqrt(flat.sum() * cell * cell / np.pi)),
                "max_r_cm": float(D[flat].max())}
    for drop in (5.0, 10.0, 20.0):
        support = occ & (zbuf >= top_mid - drop)
        disc = D <= clam_diam_cm / 2.0
        res.setdefault("clam_disc", {})["support_within_%.0fcm_below_top" % drop] = {
            "diam_cm": clam_diam_cm, "supported_fraction": float((disc & support).sum() / max(disc.sum(), 1)),
            "overhang_area_m2": float((disc & ~support).sum() * cell * cell / 1e4),
            "support_radius_min_cm": float(_min_unsupported_radius(D, support, occ))}
    prof = []
    for rr in range(0, 80, 5):
        ring = occ & (np.abs(D - rr) < cell)
        vals = zbuf[ring]
        prof.append([rr, float(np.median(vals)) if len(vals) else None, float(vals.min()) if len(vals) else None,
                     float(vals.max()) if len(vals) else None])
    res["radial_upper_surface_cm"] = {"cols": ["r_cm", "median_h", "min_h", "max_h"], "rows": prof}
    res["base_band"] = {}
    low = h <= 2.6
    if low.any():
        res["base_band"] = {"lowest_2.6cm_extent_cm": [float(np.ptp(xy[low, 0])), float(np.ptp(xy[low, 1]))]}
    return res


def _min_unsupported_radius(D, support, occ):
    """Smallest radius at which a cell is NOT supported (inside the stone outline or beyond it)."""
    bad = ~support
    return D[bad].min() if bad.any() else float("inf")


if __name__ == "__main__":
    nm = sys.argv[1] if len(sys.argv) > 1 else "GraniteMillstone"
    out = measure(nm)
    path = HERE + ("s3_millstone_fbx_measure.json" if nm == "GraniteMillstone" else "s3_prop_fbx_measure_%s.json" % nm)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print(json.dumps({k: out[k] for k in ("vertices", "polygons", "global", "size_cm_file_axes", "axis_r15_height_cm",
                                          "peak_height_cm", "plateaus", "clam_disc", "base_band")}, indent=1))
    print("radial:", out["radial_upper_surface_cm"]["rows"])
    print("WROTE", path)
