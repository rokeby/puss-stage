"""Girders v3, step 1 of 2: import the three v3 FBX as NEW assets (written 7 Oct 2026, NOT RUN).

Gary, 7 Oct (own words): "v3 at double section". This step only creates
/Game/InfinityStage/RigAtmos/Underpass/Meshes/SM_UP_{LacedColumn,PlateGirder,KneeBracket}_v3; no existing asset, no
level, no Show is touched. Step 2 (girders_v3_apply.py) points the six Structures at them.

Args girders_v3_import_args.json (missing file = DRY):
  {"mode": "DRY"|"IMPORT", "confirm": "IMPORT GIRDERSV3" (IMPORT only),
   "modules": null | ["SM_UP_LacedColumn_v3", ...]   (subset = batch across several MCP calls)}
DRY     read-only: manifest/harness PASS, FBX sha256 == manifest, targets absent, v1 slots readable, v1 UV0 V-sign
        (POSITIVE CONTROL: v1 renders correctly in the show, so the check must read it as V-down), census clean.
IMPORT  per module, ONE import task per import_asset_tasks call (batch-safe; memory ue58-bulk-import-oom-crash):
        options set anyway (Interchange ignores FbxImportUI: memory ue58-fbx-import-traps), folder diffed
        before/after, never-saved strays deleted; gates: StaticMesh, 1 LOD and no *_LOD* asset (LodGroup split),
        bounds == harness bounds (0.2 cm), tris == build_manifest blender_tris, UV0 V runs DOWN on vertical faces
        (up == 0, down > 0), slot count == v1's; then modify() -> Nanite off -> slots copied from the v1 asset
        (material_interface + material_slot_name) -> READ BACK. Any gate failure deletes THIS RUN's never-saved
        new assets and stops (nothing saved). Saves ONLY the new packages; census must be clean after.
No REVERT mode on purpose: the _v3 assets are new and inert until step 2 references them; removing them is a
by-hand Content Browser delete AFTER girders_v3_apply REVERT (this tool never deletes a saved asset).

Proof tiers (AGENTS.md), per claim:
* declaration-proven: UStaticMesh::GetNumTriangles(int32) is BlueprintPure (UE_5.8 Engine/Classes/Engine/
  StaticMesh.h:2152-2153); StaticMaterials has BlueprintGetter/Setter (StaticMesh.h:1095-1096);
  FStaticMaterial.MaterialInterface / MaterialSlotName are BlueprintReadWrite (StaticMesh.h:506-511);
  EditorAssetLibrary LoadAsset/DoesAssetExist/DeleteAsset/SaveAsset/ListAssets (EditorScriptingUtilities
  EditorAssetLibrary.h:37,70,144,281,328).
* measured (offline, 7 Oct): FBX sha256 == build_manifest.json for all three (sha256sum); harness_result.json PASS,
  v3 bounds 1880x60x40 / 100x40x90 / 120x20x120, negatives failed as expected.
* copied from live-run tools (inferred to behave the same here): import task/strays/LOD/Nanite flow from
  ../underpass_rig_apply.py:507-604 (UNDERPASS_KIT_IMPORT_OK 5 Oct, underpass_kit_import_last.json); mesh
  description walk (PolygonID / get_polygon_vertex_instances / get_vertex_instance_uv) from
  ../s3_flats_import.py:375-397.
* inferred (the first live run confirms): Interchange keeps one triangle per Blender triangle (tri gate exact);
  UE stores V as 1 - Blender v, so the harness's "V down" (computed on 1 - v) reads as negative dV/dZ in UE.
Markers (run=<id> on every line): GIRDERSV3_IMPORT_DRY_OK, GIRDERSV3_IMPORT_OK, GIRDERSV3_IMPORT_FAILED.
Every UE object lives inside a function (re-run crash rule); no helper imports (stale module cache rule).
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MESH_DIR = "/Game/InfinityStage/RigAtmos/Underpass/Meshes"
MODULES = {  # new asset name -> the v1 asset whose slots it copies
    "SM_UP_LacedColumn_v3": "SM_UP_LacedColumn",
    "SM_UP_PlateGirder_v3": "SM_UP_PlateGirder",
    "SM_UP_KneeBracket_v3": "SM_UP_KneeBracket",
}
BOUNDS_TOL_CM = 0.2
CONFIRM = "IMPORT GIRDERSV3"
ARGS_FILE = "girders_v3_import_args.json"
VERTICAL_NZ = 0.1     # harness_v3.py:218 (|n.z| < 0.1 = vertical face)
MIN_DZ_CM = 0.5       # harness_v3.py:221


class ImportError_(RuntimeError):
    pass


# ============================================================================ pure logic (harness-tested)
def expected_rows(manifest: dict, harness: dict) -> dict:
    """{name: {"fbx", "sha256", "tris", "bounds_cm"}} from the two offline gates; refuses unless both PASS."""
    if harness.get("status") != "PASS" or harness.get("negatives_failed_as_expected") is not True:
        raise ImportError_("harness_result.json is not PASS with failing negatives")
    out = {}
    for name in MODULES:
        m = manifest["modules"].get(name)
        h = harness["v3"].get(name)
        if not m or not h or h.get("status") != "PASS":
            raise ImportError_(f"{name}: missing or not PASS in manifest/harness")
        if m.get("open_parts") != 0:
            raise ImportError_(f"{name}: open_parts {m.get('open_parts')}")
        out[name] = {"fbx": m["fbx"], "sha256": m["sha256"], "tris": int(m["blender_tris"]),
                     "bounds_cm": [float(x) for x in h["bounds_cm"]]}
    return out


def bounds_problem(size, expected, tol=BOUNDS_TOL_CM):
    if any(abs(float(a) - float(b)) > tol for a, b in zip(size, expected)):
        return f"bounds {[round(float(s), 3) for s in size]} != {expected} (axis wrong? fix the EXPORT, never rotate in UE)"
    return None


def v_sign(polygons) -> dict:
    """polygons: [[(x, y, z), (u, v)], ...] per polygon, UE space, UE-stored UV0.
    Vertical face (|n.z| < 0.1) spanning >= 0.5 cm of Z: 'down' if cov(z, v) < 0 (V runs DOWN in Unreal)."""
    down = up = 0
    for poly in polygons:
        pts = [p for p, _ in poly]
        if len(pts) < 3:
            continue
        ax, ay, az = (pts[1][i] - pts[0][i] for i in range(3))
        bx, by, bz = (pts[2][i] - pts[0][i] for i in range(3))
        nx, ny, nz = ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx
        ln = (nx * nx + ny * ny + nz * nz) ** 0.5
        if ln < 1e-9 or abs(nz / ln) >= VERTICAL_NZ:
            continue
        zs = [p[2] for p in pts]
        if max(zs) - min(zs) < MIN_DZ_CM:
            continue
        vs = [uv[1] for _, uv in poly]
        mz, mv = sum(zs) / len(zs), sum(vs) / len(vs)
        if sum((z - mz) * (v - mv) for z, v in zip(zs, vs)) < 0:
            down += 1
        else:
            up += 1
    return {"down": down, "up": up, "ok": up == 0 and down > 0}


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_args(path: str) -> dict:
    if not os.path.exists(path):
        return {"mode": "DRY"}
    a = json.load(open(path, encoding="utf-8"))
    mode = str(a.get("mode", "DRY")).upper()
    if mode not in ("DRY", "IMPORT"):
        raise ImportError_(f"unknown mode {mode}")
    a["mode"] = mode
    if mode == "IMPORT" and a.get("confirm") != CONFIRM:
        raise ImportError_(f"confirm must be {CONFIRM!r}")
    mods = a.get("modules")
    if mods is not None:
        bad = [m for m in mods if m not in MODULES]
        if bad or not mods:
            raise ImportError_(f"modules must be a non-empty subset of {sorted(MODULES)}: {mods}")
    return a


# ============================================================================ editor adapters
def _u():
    import unreal  # noqa: PLC0415  (the harness injects a fake into sys.modules)
    return unreal


def _pk(p) -> str:
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s.split(".")[0]


def _obj_path(o):
    return o.get_path_name().split(".")[0] if o is not None else None


class Ctx:
    def __init__(self):
        self.u = _u()
        self.run = "GV3I-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.created = []  # never-saved assets THIS run made (deleted on a failed gate)

    def log(self, m):
        self.u.log(m)

    def fail(self, m):
        self.u.log_error(f"GIRDERSV3_IMPORT_FAILED|run={self.run}|{m}")
        raise ImportError_(f"GIRDERSV3_IMPORT_FAILED|run={self.run}|{m}")

    def write_json(self, name, payload):
        p = os.path.join(HERE, name)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=1)
            fh.flush()
            os.fsync(fh.fileno())
        if json.load(open(p, encoding="utf-8")) != json.loads(json.dumps(payload)):
            self.fail(f"{name} did not read back")
        return p


def dirty(u):
    lib = u.EditorLoadingAndSavingUtils
    return (sorted(_pk(p) for p in lib.get_dirty_content_packages()),
            sorted(_pk(p) for p in lib.get_dirty_map_packages()))


def guards(c: Ctx):
    u = c.u
    if u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world() is not None:
        c.fail("PIE active")
    if dirty(u) != ([], []):
        c.fail(f"editor dirty at start {dirty(u)}")


def slots_of(mesh) -> list:
    out = []
    for s in list(mesh.get_editor_property("static_materials")):
        out.append({"name": str(s.get_editor_property("material_slot_name")),
                    "material": _obj_path(s.get_editor_property("material_interface"))})
    return out


def mesh_polygons(u, mesh):
    """UV0 per polygon, UE space (s3_flats_import.py:375-397 pattern)."""
    desc = mesh.get_static_mesh_description(0)
    if desc is None:
        raise ImportError_(f"no mesh description for {_obj_path(mesh)}")
    method = getattr(desc, "get_polygon_vertex_instances", None)
    if method is None:
        raise ImportError_("NO_POLYGON_VERTEX_INSTANCE_API")
    polys = []
    for index in range(desc.get_polygon_count()):
        poly = []
        for vi in list(method(u.PolygonID(index))):
            p = desc.get_vertex_position(desc.get_vertex_instance_vertex(vi))
            uv = desc.get_vertex_instance_uv(vi, 0)
            poly.append(((float(p.x), float(p.y), float(p.z)), (float(uv.x), float(uv.y))))
        polys.append(poly)
    return polys


def size_of(mesh):
    b = mesh.get_bounding_box()
    return [float(b.max.x - b.min.x), float(b.max.y - b.min.y), float(b.max.z - b.min.z)]


def _fbx_options(u):
    o = u.FbxImportUI()
    o.set_editor_property("import_mesh", True)
    o.set_editor_property("import_as_skeletal", False)
    o.set_editor_property("import_materials", False)
    o.set_editor_property("import_textures", False)
    o.set_editor_property("import_animations", False)
    st = o.get_editor_property("static_mesh_import_data")
    st.set_editor_property("combine_meshes", False)
    st.set_editor_property("import_mesh_lods", False)
    return o


def listing(u):
    if not u.EditorAssetLibrary.does_directory_exist(MESH_DIR):
        return set()
    return set(_pk(p) for p in u.EditorAssetLibrary.list_assets(MESH_DIR, True, False))


def read_v1(c: Ctx, wanted):
    u = c.u
    out = {}
    for name in wanted:
        path = f"{MESH_DIR}/{MODULES[name]}"
        m = u.EditorAssetLibrary.load_asset(path)
        if not isinstance(m, u.StaticMesh):
            c.fail(f"v1 {path} does not load as a StaticMesh")
        out[name] = {"path": path, "slots": slots_of(m)}
        if not out[name]["slots"]:
            c.fail(f"v1 {path} has no material slots")
    return out


def _cleanup(c: Ctx):
    u = c.u
    for p in list(c.created):
        u.EditorAssetLibrary.delete_asset(p)  # never saved: created by this run only
    left = [p for p in c.created if u.EditorAssetLibrary.does_asset_exist(p)]
    c.created = []
    return left


# ============================================================================ phases
def phase_dry(c: Ctx, rows, wanted):
    u = c.u
    guards(c)
    report = {"run": c.run, "mode": "DRY", "modules": {}, "mutated": 0}
    v1 = read_v1(c, wanted)
    for name in wanted:
        r = rows[name]
        fbx = os.path.join(HERE, "FBX", r["fbx"])
        target = f"{MESH_DIR}/{name}"
        v1_mesh = u.EditorAssetLibrary.load_asset(v1[name]["path"])
        control = v_sign(mesh_polygons(u, v1_mesh))
        report["modules"][name] = {
            "fbx_exists": os.path.exists(fbx),
            "sha_ok": os.path.exists(fbx) and sha256_file(fbx) == r["sha256"],
            "target_exists": bool(u.EditorAssetLibrary.does_asset_exist(target)),
            "expect": r, "v1": v1[name], "v1_uv_control": control}
    if dirty(u) != ([], []):
        c.fail(f"DRY dirtied {dirty(u)}")
    p = c.write_json(f"girders_v3_import_dry_{c.run}.json", report)
    bad = {n: k for n, row in report["modules"].items()
           for k in ("fbx_exists", "sha_ok") if not row[k]}
    clash = [n for n, row in report["modules"].items() if row["target_exists"]]
    control_bad = [n for n, row in report["modules"].items() if not row["v1_uv_control"]["ok"]]
    if bad or clash or control_bad:
        c.fail(f"DRY refused: fbx/sha {bad} existing targets {clash} v1 UV control not V-down {control_bad} (report {p})")
    c.log(f"GIRDERSV3_IMPORT_DRY_OK|run={c.run}|modules={wanted}|targets_absent=1|sha_ok=1"
          f"|v1_uv_control={ {n: report['modules'][n]['v1_uv_control'] for n in wanted} }|mutated=0|report={p}")
    return report


def gate_one(c: Ctx, name, row, v1_slots):
    u = c.u
    path = f"{MESH_DIR}/{name}"
    m = u.EditorAssetLibrary.load_asset(path)
    if not isinstance(m, u.StaticMesh):
        return None, [f"{path} is not a StaticMesh"], {}
    probs = []
    lods = int(m.get_num_lods())
    if lods != 1:
        probs.append(f"{lods} LODs")
    size = size_of(m)
    bp = bounds_problem(size, row["bounds_cm"])
    if bp:
        probs.append(bp)
    tris = int(m.get_num_triangles(0))
    if tris != row["tris"]:
        probs.append(f"tris {tris} != manifest {row['tris']}")
    slots = slots_of(m)
    if len(slots) != len(v1_slots):
        probs.append(f"{len(slots)} slots != v1 {len(v1_slots)}")
    uv = v_sign(mesh_polygons(u, m))
    if not uv["ok"]:
        probs.append(f"UV0 V not down: {uv} (fix the EXPORT)")
    return m, probs, {"lods": lods, "bounds_cm": [round(x, 3) for x in size], "tris": tris, "uv0": uv,
                      "imported_slots": slots}


def phase_import(c: Ctx, rows, wanted):
    u = c.u
    guards(c)
    v1 = read_v1(c, wanted)
    expected = {n: f"{MESH_DIR}/{n}" for n in wanted}
    clash = [p for p in expected.values() if u.EditorAssetLibrary.does_asset_exist(p)]
    if clash:
        c.fail(f"targets exist (never replace in place: memory ue58-reimport-revert-by-reload-fails): {clash}")
    for n in wanted:
        if sha256_file(os.path.join(HERE, "FBX", rows[n]["fbx"])) != rows[n]["sha256"]:
            c.fail(f"{n}: FBX sha256 differs from build_manifest.json")
    readback, strays_deleted = {}, []
    try:
        for n in wanted:  # one task per call: a crash or failure costs one mesh, and nothing is saved
            before = listing(u)
            t = u.AssetImportTask()
            t.set_editor_property("filename", os.path.join(HERE, "FBX", rows[n]["fbx"]))
            t.set_editor_property("destination_path", MESH_DIR)
            t.set_editor_property("destination_name", n)
            t.set_editor_property("automated", True)
            t.set_editor_property("replace_existing", False)
            t.set_editor_property("save", False)
            t.set_editor_property("options", _fbx_options(u))  # ignored by Interchange; set anyway (memory)
            u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([t])
            new = listing(u) - before
            c.created += sorted(new)
            strays = sorted(p for p in new if p != expected[n])
            for p in strays:
                if not u.EditorAssetLibrary.delete_asset(p):
                    raise ImportError_(f"could not delete stray {p}")
                c.created.remove(p)
                strays_deleted.append(p)
            if expected[n] not in new:
                raise ImportError_(f"{n}: not imported (new={sorted(new)})")
            lod_assets = sorted(p for p in listing(u) if "_LOD" in p.rsplit("/", 1)[-1].upper())
            if lod_assets:
                raise ImportError_(f"LOD-split assets present: {lod_assets}")
            m, probs, facts = gate_one(c, n, rows[n], v1[n]["slots"])
            if probs:
                raise ImportError_(f"{n}: {probs}")
            # modify() BEFORE setters (memory ue58-fbx-import-traps); setters can lie: read back
            m.modify()
            ns = m.get_editor_property("nanite_settings")
            ns.set_editor_property("enabled", False)
            m.set_editor_property("nanite_settings", ns)
            if bool(m.get_editor_property("nanite_settings").get_editor_property("enabled")):
                raise ImportError_(f"{n}: Nanite still on after set")
            mats = list(m.get_editor_property("static_materials"))
            for i, want in enumerate(v1[n]["slots"]):
                mi = u.EditorAssetLibrary.load_asset(want["material"]) if want["material"] else None
                if want["material"] and mi is None:
                    raise ImportError_(f"v1 slot material {want['material']} does not load")
                mats[i].set_editor_property("material_interface", mi)
                mats[i].set_editor_property("material_slot_name", want["name"])
            m.set_editor_property("static_materials", mats)
            now = slots_of(m)
            if now != v1[n]["slots"]:
                raise ImportError_(f"{n}: slots read back {now} != v1 {v1[n]['slots']}")
            facts.update({"path": expected[n], "slots": now, "nanite": False})
            readback[n] = facts
            c.log(f"GIRDERSV3_IMPORT_GATED|run={c.run}|{n}|{json.dumps(facts['uv0'])}|tris={facts['tris']}"
                  f"|bounds={facts['bounds_cm']}")
        con, maps = dirty(u)
        if maps or not set(con) <= set(expected.values()):
            raise ImportError_(f"dirty scope before save content={con} maps={maps}")
    except Exception as exc:  # noqa: BLE001  (nothing saved yet: remove this run's assets, then stop)
        left = _cleanup(c)
        c.fail(f"NOTHING SAVED; this run's new assets deleted (left={left}): {exc}")
    for n, p in expected.items():
        if not u.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False):
            c.fail(f"save {p} failed (unsaved new asset left: Don't-Save restart)")
    c.created = []
    if dirty(u) != ([], []):
        c.fail(f"dirty after save {dirty(u)}")
    # read back the saved state (in-memory object after save; inferred == disk, as underpass_rig_apply)
    for n, p in expected.items():
        m = u.EditorAssetLibrary.load_asset(p)
        again = {"lods": int(m.get_num_lods()), "tris": int(m.get_num_triangles(0)), "slots": slots_of(m),
                 "nanite": bool(m.get_editor_property("nanite_settings").get_editor_property("enabled"))}
        if (again["lods"], again["tris"], again["slots"], again["nanite"]) != \
                (1, rows[n]["tris"], v1[n]["slots"], False) or bounds_problem(size_of(m), rows[n]["bounds_cm"]):
            c.fail(f"{n}: saved read-back {again}")
    rec = {"run": c.run, "status": "PASS", "imported": readback, "strays_deleted": strays_deleted,
           "manifest_sha": sha256_file(os.path.join(HERE, "build_manifest.json"))}
    p = c.write_json(f"girders_v3_import_{c.run}.json", rec)
    last = os.path.join(HERE, "girders_v3_import_last.json")
    merged = json.load(open(last, encoding="utf-8")) if os.path.exists(last) else {"status": "PARTIAL", "imported": {}}
    merged["imported"].update(readback)
    merged["runs"] = merged.get("runs", []) + [c.run]
    merged["status"] = "PASS" if set(merged["imported"]) == set(MODULES) else "PARTIAL"
    c.write_json("girders_v3_import_last.json", merged)
    c.log(f"GIRDERSV3_IMPORT_OK|run={c.run}|meshes={sorted(readback)}|strays={len(strays_deleted)}->0"
          f"|all_three={merged['status']}|saved_only_new=1|dirty_after=0+0|report={p}")
    return rec


def main():
    c = Ctx()
    try:
        args = load_args(os.path.join(HERE, ARGS_FILE))
        rows = expected_rows(json.load(open(os.path.join(HERE, "build_manifest.json"), encoding="utf-8")),
                             json.load(open(os.path.join(HERE, "harness_result.json"), encoding="utf-8")))
    except ImportError_ as exc:
        c.fail(str(exc))
    wanted = list(args.get("modules") or MODULES)
    c.log(f"GIRDERSV3_IMPORT_START|run={c.run}|mode={args['mode']}|modules={wanted}")
    return (phase_dry if args["mode"] == "DRY" else phase_import)(c, rows, wanted)


if __name__ == "__main__" or "unreal" in sys.modules and not getattr(sys.modules.get("unreal"), "_GIRDERS_FAKE", False):
    main()
