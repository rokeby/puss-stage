"""Read-only editor harvest of SM_S3_ShoreGround_B vertex colour G.

UE 5.8 exposes mesh-description positions/UVs but not vertex-instance colour values to Python.  DRY therefore exports
an ASCII FBX with vertex colours to project Saved/, parses LayerElementColor, aligns FBX axes to the manifest bounds,
and writes a gzip JSON sample table for the next offline field rebuild.  It never edits or saves a package.
"""
import datetime
import gzip
import hashlib
import itertools
import json
import os
import re

try:
    import unreal
except ImportError:  # offline parser harness
    unreal = None

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.L_InfinityStage_V1VerticalSlice"
MESH = "/Game/InfinityStage/Dev/Generated/S3Shore/SM_S3_ShoreGround_B"
MANIFEST = os.path.join(PROJECT, "DerivedAssets", "S3Shore", "SM_S3_ShoreGround_manifest.json")


def _req(cond, message):
    if not cond:
        raise RuntimeError(message)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _numbers(text):
    return [float(x) for x in re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[Ee][-+]?\d+)?", text)]


def _array(text, name, start=0, end=None):
    end = len(text) if end is None else end
    match = re.search(r"\b" + re.escape(name) + r"\s*:\s*\*\d+\s*\{\s*a\s*:\s*", text[start:end])
    if not match:
        raise ValueError("FBX_ARRAY_MISSING|" + name)
    a = start + match.end()
    b = text.find("}", a, end)
    if b < 0:
        raise ValueError("FBX_ARRAY_UNCLOSED|" + name)
    return _numbers(text[a:b])


def parse_ascii_fbx(text):
    """Return control-point positions and averaged RGBA per control point."""
    verts = _array(text, "Vertices")
    poly_raw = _array(text, "PolygonVertexIndex")
    _req(len(verts) % 3 == 0, "FBX_VERTEX_ARITY")
    positions = [verts[i:i + 3] for i in range(0, len(verts), 3)]
    poly = [(-int(v) - 1) if v < 0 else int(v) for v in poly_raw]
    _req(poly and max(poly) < len(positions), "FBX_POLYGON_INDEX")
    begin = text.find("LayerElementColor:")
    _req(begin >= 0, "FBX_LAYER_COLOR_MISSING")
    candidates = [p for p in (text.find("\n\tLayerElement", begin + 1), text.find("\n\tLayer:", begin + 1)) if p >= 0]
    end = min(candidates) if candidates else len(text)
    block = text[begin:end]
    mm = re.search(r'MappingInformationType\s*:\s*"([^"]+)"', block)
    rr = re.search(r'ReferenceInformationType\s*:\s*"([^"]+)"', block)
    _req(mm and rr, "FBX_COLOR_MAPPING_MISSING")
    mapping, reference = mm.group(1), rr.group(1)
    colors_flat = _array(text, "Colors", begin, end)
    _req(len(colors_flat) % 4 == 0, "FBX_COLOR_ARITY")
    direct = [colors_flat[i:i + 4] for i in range(0, len(colors_flat), 4)]
    indices = [int(v) for v in _array(text, "ColorIndex", begin, end)] if "ColorIndex:" in block else []

    def direct_index(element):
        if reference == "Direct":
            return element
        if reference in ("IndexToDirect", "Index"):
            _req(element < len(indices), "FBX_COLOR_INDEX_COUNT")
            return indices[element]
        raise ValueError("FBX_COLOR_REFERENCE|" + reference)

    sums = [[0.0, 0.0, 0.0, 0.0] for _ in positions]
    counts = [0] * len(positions)
    for corner, cp in enumerate(poly):
        if mapping == "ByPolygonVertex":
            element = corner
        elif mapping in ("ByVertice", "ByVertex"):
            element = cp
        elif mapping == "AllSame":
            element = 0
        else:
            raise ValueError("FBX_COLOR_MAPPING|" + mapping)
        di = direct_index(element)
        _req(0 <= di < len(direct), "FBX_COLOR_DIRECT_INDEX")
        for c in range(4):
            sums[cp][c] += direct[di][c]
        counts[cp] += 1
    rows = []
    for cp, pos in enumerate(positions):
        _req(counts[cp] > 0, "FBX_UNUSED_CONTROL_POINT|%d" % cp)
        rows.append({"control_point": cp, "fbx_position_cm": pos,
                     "rgba": [v / counts[cp] for v in sums[cp]], "corner_samples": counts[cp]})
    return {"mapping": mapping, "reference": reference, "control_points": len(rows),
            "polygon_vertices": len(poly), "rows": rows}


def align_to_expected(rows, expected):
    """Infer FBX axis permutation/sign from the manifest's deliberately asymmetric local bounds."""
    raw = [r["fbx_position_cm"] for r in rows]
    raw_min = [min(v[i] for v in raw) for i in range(3)]
    raw_max = [max(v[i] for v in raw) for i in range(3)]
    want_min, want_max = expected["min"], expected["max"]
    best = None
    for perm in itertools.permutations(range(3)):
        for signs in itertools.product((-1.0, 1.0), repeat=3):
            got_min = []
            got_max = []
            for i in range(3):
                a, b = signs[i] * raw_min[perm[i]], signs[i] * raw_max[perm[i]]
                got_min.append(min(a, b)); got_max.append(max(a, b))
            err = max(abs(got_min[i] - want_min[i]) for i in range(3))
            err = max(err, max(abs(got_max[i] - want_max[i]) for i in range(3)))
            cand = (err, perm, signs, got_min, got_max)
            if best is None or cand < best:
                best = cand
    _req(best[0] <= 2.0, "FBX_AXIS_BOUNDS|error_cm=%.3f|got=%s/%s|want=%s/%s" %
         (best[0], best[3], best[4], want_min, want_max))
    _, perm, signs, got_min, got_max = best
    for row in rows:
        p = row.pop("fbx_position_cm")
        row["local_cm"] = [signs[i] * p[perm[i]] for i in range(3)]
        row["g"] = row["rgba"][1]
    return {"permutation": list(perm), "signs": list(signs), "max_bounds_error_cm": round(best[0], 4),
            "mapped_bounds": {"min": got_min, "max": got_max}}


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(str(p.get_name()) for p in lib.get_dirty_content_packages()),
            "maps": sorted(str(p.get_name()) for p in lib.get_dirty_map_packages())}


def _fbx_options():
    opts = unreal.FbxExportOption()
    wanted = {"ascii": True, "force_front_x_axis": False, "vertex_color": True, "level_of_detail": False,
              "collision": False, "export_morph_targets": False, "export_preview_mesh": False,
              "map_skeletal_motion_to_root": False, "export_local_time": True}
    for key, value in wanted.items():
        opts.set_editor_property(key, value)
    got = {k: bool(opts.get_editor_property(k)) for k in wanted}
    _req(got == wanted, "FBX_OPTION_READBACK|wanted=%s|got=%s" % (wanted, got))
    return opts, got


def _export_ascii(mesh, path):
    task = unreal.AssetExportTask()
    for key, value in {"object": mesh, "filename": path, "automated": True, "prompt": False,
                       "replace_identical": True, "selected": False, "exporter": unreal.StaticMeshExporterFBX(),
                       "options": _fbx_options()[0]}.items():
        task.set_editor_property(key, value)
    ok = unreal.Exporter.run_asset_export_task(task)
    errors = [str(e) for e in task.get_editor_property("errors")]
    _req(ok and not errors and os.path.isfile(path), "FBX_EXPORT|ok=%s|errors=%s" % (ok, errors))
    with open(path, "rb") as src:
        _req(not src.read(32).startswith(b"Kaydara FBX Binary"), "FBX_NOT_ASCII")


def run_dry(run):
    _req(unreal is not None, "UNREAL_REQUIRED")
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    _req(str(world.get_path_name()).startswith(WORLD), "WRONG_WORLD|" + str(world.get_path_name()))
    before = _census()
    mesh = unreal.load_asset(MESH)
    _req(mesh is not None and isinstance(mesh, unreal.StaticMesh), "MESH_MISSING|" + MESH)
    _req(unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem).has_vertex_colors(mesh), "VERTEX_COLORS_MISSING")
    out_dir = os.path.join(HERE, "WetPaintReads", run)
    os.makedirs(out_dir)
    fbx = os.path.join(out_dir, "SM_S3_ShoreGround_B_vertex_g_ascii.fbx")
    _export_ascii(mesh, fbx)
    with open(fbx, "r", encoding="utf-8", errors="strict") as src:
        parsed = parse_ascii_fbx(src.read())
    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    axis = align_to_expected(parsed["rows"], manifest["expected_ue_local_bounds_cm"])
    samples = {"schema": "s3_shore_wet_paint_samples/1", "run": run, "asset": MESH,
               "source_fbx_sha256": sha256(fbx), "axis_map": axis, "mapping": parsed["mapping"],
               "reference": parsed["reference"], "rows": parsed["rows"]}
    samples_path = os.path.join(out_dir, "vertex_g_samples.json.gz")
    with gzip.open(samples_path, "wt", encoding="utf-8") as dst:
        json.dump(samples, dst, separators=(",", ":"))
    after = _census()
    _req(after == before, "DIRTY_PACKAGE_DELTA|before=%s|after=%s" % (before, after))
    g = [r["g"] for r in parsed["rows"]]
    report = {"schema": "s3_shore_wet_paint_read/1", "run": run,
              "utc": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"), "asset": MESH,
              "fbx": fbx.replace("\\", "/"), "fbx_sha256": sha256(fbx),
              "samples": samples_path.replace("\\", "/"), "samples_sha256": sha256(samples_path),
              "control_points": parsed["control_points"], "polygon_vertices": parsed["polygon_vertices"],
              "g_min_max_mean": [min(g), max(g), sum(g) / len(g)], "axis_map": axis,
              "dirty_packages_before": before, "dirty_packages_after": after}
    report_path = os.path.join(out_dir, "read_report.json")
    with open(report_path, "w", encoding="utf-8") as dst:
        json.dump(report, dst, indent=1)
        dst.flush(); os.fsync(dst.fileno())
    return report
