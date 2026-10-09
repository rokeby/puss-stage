"""Read-only binary-FBX UV audit. Pure Python + stdlib; never launches Blender/Unreal."""
from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import struct
import zlib


def _prop(buf, pos):
    kind = chr(buf[pos]); pos += 1
    scalar = {"Y": ("<h", 2), "C": ("<?", 1), "I": ("<i", 4), "F": ("<f", 4), "D": ("<d", 8), "L": ("<q", 8)}
    if kind in scalar:
        fmt, size = scalar[kind]
        return struct.unpack_from(fmt, buf, pos)[0], pos + size
    if kind in "fdlib":
        count, encoded, size = struct.unpack_from("<III", buf, pos); pos += 12
        raw = bytes(buf[pos:pos + size]); pos += size
        if encoded == 1:
            raw = zlib.decompress(raw)
        fmt = {"f": "f", "d": "d", "l": "q", "i": "i", "b": "B"}[kind]
        width = struct.calcsize("<" + fmt)
        return list(struct.unpack("<%d%s" % (count, fmt), raw[:count * width])), pos
    if kind in "SR":
        size = struct.unpack_from("<I", buf, pos)[0]; pos += 4
        return bytes(buf[pos:pos + size]), pos + size
    raise ValueError("FBX_PROP_TYPE|%s" % kind)


def _nodes(buf, pos, end, wide):
    fmt, head = ("<QQQB", 25) if wide else ("<IIIB", 13)
    while pos < end:
        endoff, count, _size, nlen = struct.unpack_from(fmt, buf, pos)
        if not endoff:
            return
        name = bytes(buf[pos + head:pos + head + nlen]).decode("ascii", "replace")
        p = pos + head + nlen; props = []
        for _ in range(count):
            value, p = _prop(buf, p); props.append(value)
        yield name, props, p, endoff
        pos = endoff


def _text(value):
    if isinstance(value, bytes):
        return value.split(b"\0")[0].decode("utf-8", "replace")
    return str(value)


def _children(buf, start, end, wide):
    return list(_nodes(buf, start, end, wide))


def _layer(buf, start, end, wide, name):
    out = {}
    for n, p, a, b in _nodes(buf, start, end, wide):
        if n == "MappingInformationType": out["mapping"] = _text(p[0])
        elif n == "ReferenceInformationType": out["reference"] = _text(p[0])
        elif n in ("UV", "UVIndex", "Materials"): out[n] = p[0]
    out["name"] = name
    return out


def parse_fbx(path):
    with open(path, "rb") as handle:
        buf = memoryview(handle.read())
    if bytes(buf[:20]) != b"Kaydara FBX Binary  ":
        raise ValueError("NOT_BINARY_FBX")
    version = struct.unpack_from("<I", buf, 23)[0]; wide = version >= 7500
    geometries = []
    for n, _p, a, b in _nodes(buf, 27, len(buf), wide):
        if n != "Objects": continue
        for n2, p2, a2, b2 in _nodes(buf, a, b, wide):
            if n2 != "Geometry": continue
            geo = {"id": int(p2[0]), "name": _text(p2[1]), "uv_layers": [], "materials": {}}
            for n3, p3, a3, b3 in _nodes(buf, a2, b2, wide):
                if n3 == "Vertices": geo["vertices"] = [float(x) for x in p3[0]]
                elif n3 == "PolygonVertexIndex": geo["indices"] = [int(x) for x in p3[0]]
                elif n3 == "LayerElementUV": geo["uv_layers"].append(_layer(buf, a3, b3, wide, "UV%s" % _text(p3[0])))
                elif n3 == "LayerElementMaterial": geo["materials"] = _layer(buf, a3, b3, wide, "Material")
            geometries.append(geo)
    return {"version": version, "bytes": os.path.getsize(path), "geometries": geometries}


def _solve4(rows, values):
    # Normal equations + pivoted Gauss-Jordan for affine least squares.
    mat = [[sum(r[i] * r[j] for r in rows) for j in range(4)] + [sum(r[i] * v for r, v in zip(rows, values))] for i in range(4)]
    for col in range(4):
        pivot = max(range(col, 4), key=lambda k: abs(mat[k][col]))
        if abs(mat[pivot][col]) < 1e-12: return None
        mat[col], mat[pivot] = mat[pivot], mat[col]
        scale = mat[col][col]; mat[col] = [x / scale for x in mat[col]]
        for row in range(4):
            if row == col: continue
            scale = mat[row][col]; mat[row] = [a - scale * b for a, b in zip(mat[row], mat[col])]
    return [mat[i][4] for i in range(4)]


def _fit(points, values):
    rows = [[p[0], p[1], p[2], 1.0] for p in points]; coef = _solve4(rows, values)
    if coef is None: return {"rank": "singular"}
    errors = [abs(sum(c * x for c, x in zip(coef, row)) - v) for row, v in zip(rows, values)]
    return {"coef_xyz1": coef, "max_abs_error": max(errors), "rms_error": math.sqrt(sum(e * e for e in errors) / len(errors))}


def _fit_yz(points, values):
    rows = [[p[1], p[2], 0.0, 1.0] for p in points]
    # Reuse the 4x4 solver with a fixed zero-X surrogate made independent by an identity row.
    mat_rows = [[r[0], r[1], 1.0] for r in rows]
    normal = [[sum(r[i] * r[j] for r in mat_rows) for j in range(3)] +
              [sum(r[i] * v for r, v in zip(mat_rows, values))] for i in range(3)]
    for col in range(3):
        pivot = max(range(col, 3), key=lambda k: abs(normal[k][col]))
        if abs(normal[pivot][col]) < 1e-12: return {"rank": "singular"}
        normal[col], normal[pivot] = normal[pivot], normal[col]
        scale = normal[col][col]; normal[col] = [x / scale for x in normal[col]]
        for row in range(3):
            if row == col: continue
            scale = normal[row][col]; normal[row] = [a - scale * b for a, b in zip(normal[row], normal[col])]
    coef = [normal[i][3] for i in range(3)]
    errors = [abs(coef[0] * p[1] + coef[1] * p[2] + coef[2] - v) for p, v in zip(points, values)]
    return {"coef_yz1": coef, "max_abs_error": max(errors), "rms_error": math.sqrt(sum(e * e for e in errors) / len(errors))}


def audit(path):
    parsed = parse_fbx(path); rows = []
    for geo in parsed["geometries"]:
        verts = [geo["vertices"][i:i + 3] for i in range(0, len(geo.get("vertices", [])), 3)]
        polyverts = []; polygons = []; current = []
        for raw in geo.get("indices", []):
            idx = -raw - 1 if raw < 0 else raw; current.append(idx)
            if raw < 0: polygons.append(current); current = []
        polyverts = [i for poly in polygons for i in poly]
        poly_ids = [poly_id for poly_id, poly in enumerate(polygons) for _ in poly]
        mat = geo.get("materials", {}); mats = list(mat.get("Materials", []))
        layer = geo.get("uv_layers", [{}])[0]; uv = list(layer.get("UV", [])); uv_idx = list(layer.get("UVIndex", []))
        samples = []
        for pvi, vi in enumerate(polyverts):
            ui = uv_idx[pvi] if layer.get("reference") == "IndexToDirect" else pvi
            if 2 * ui + 1 >= len(uv): continue
            poly = poly_ids[pvi]
            mi = mats[poly] if mat.get("mapping") == "ByPolygon" and poly < len(mats) else (mats[0] if mats else 0)
            samples.append((mi, verts[vi], [uv[2 * ui], uv[2 * ui + 1]]))
        for mi in sorted(set(s[0] for s in samples)):
            group = [s for s in samples if s[0] == mi]; points = [s[1] for s in group]
            u = [s[2][0] for s in group]; v = [s[2][1] for s in group]
            rows.append({"geometry": geo["name"], "material_index": mi, "samples": len(group),
                         "uv0_range": [[min(u), max(u)], [min(v), max(v)]],
                         "u_linear_yz": _fit_yz(points, u), "v_linear_yz": _fit_yz(points, v),
                         "u_affine_xyz": _fit(points, u), "v_affine_xyz": _fit(points, v)})
    return {"mode": "DRY", "run": "FBXUV-DRY-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"), "marker": "FBXUV_DRY_OK", "source": os.path.normpath(path), "fbx_version": parsed["version"], "fbx_bytes": parsed["bytes"], "sections": rows,
            "criterion": "For a Flat V3 face, UV is planar iff both YZ linear fits have max_abs_error <= 1e-5"}


def winding_audit(path, material_index=3):
    """Measure polygon winding against the mesh centroid for the named material section."""
    parsed = parse_fbx(path); out = []
    for geo in parsed["geometries"]:
        verts = [geo["vertices"][i:i + 3] for i in range(0, len(geo.get("vertices", [])), 3)]
        centre = [sum(v[k] for v in verts) / len(verts) for k in range(3)]
        mats = list(geo.get("materials", {}).get("Materials", [])); polygons = []; current = []
        for raw in geo.get("indices", []):
            current.append(-raw - 1 if raw < 0 else raw)
            if raw < 0: polygons.append(current); current = []
        dots = []
        for poly_id, poly in enumerate(polygons):
            mi = mats[poly_id] if geo.get("materials", {}).get("mapping") == "ByPolygon" and poly_id < len(mats) else (mats[0] if mats else 0)
            if mi != material_index or len(poly) < 3: continue
            a, b, c = (verts[poly[i]] for i in range(3)); ab = [b[i] - a[i] for i in range(3)]; ac = [c[i] - a[i] for i in range(3)]
            normal = [ab[1]*ac[2]-ab[2]*ac[1], ab[2]*ac[0]-ab[0]*ac[2], ab[0]*ac[1]-ab[1]*ac[0]]
            face = [sum(verts[j][i] for j in poly) / len(poly) for i in range(3)]
            dots.append(sum(normal[i] * (face[i] - centre[i]) for i in range(3)))
        nonzero = [d for d in dots if abs(d) > 1e-9]
        out.append({"geometry": geo["name"], "material_index": material_index, "polygons": len(dots), "nondegenerate": len(nonzero),
                    "outward": sum(d > 0 for d in nonzero), "inward": sum(d < 0 for d in nonzero),
                    "verdict": "outward" if nonzero and all(d > 0 for d in nonzero) else "inward" if nonzero and all(d < 0 for d in nonzero) else "mixed_or_unclear"})
    return {"mode": "DRY", "run": "FBXWIND-DRY-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"), "marker": "FBXWIND_DRY_OK", "source": os.path.normpath(path), "sections": out,
            "criterion": "geometric winding is outward when cross(edge01,edge02) dot (face_centroid-mesh_centroid) is positive for every nondegenerate material polygon"}


def main(argv=None):
    parser = argparse.ArgumentParser(); parser.add_argument("fbx"); parser.add_argument("--mode", default="DRY", choices=("DRY", "APPLY", "REVERT")); parser.add_argument("--out"); parser.add_argument("--winding-material", type=int)
    args = parser.parse_args(argv)
    if args.mode != "DRY": raise SystemExit("READ_ONLY_AUDIT_REQUIRES_DRY")
    result = winding_audit(args.fbx, args.winding_material) if args.winding_material is not None else audit(args.fbx)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle: json.dump(result, handle, indent=2)
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__": main()
