"""P06 REALISM v2 IMPORT KIT -- Unreal entry (7 Oct, offline-written, NEVER RUN IN UNREAL BY ITS AUTHOR).

Run ONLY through p06_import_run.py (purges the Saved module cache, then runs this file) with p06_import_args.json:

  DRY        {"mode": "DRY", "confirm": "DRY P06IMPORT"}                                       read-only, CLEAN census
             file gates (hashes, sidecars, validation, mi_params, edge probes), every target path FREE, parents exist,
             the live P06 reference (MI parents, mesh slots 2/3, collision count, texture profiles) = the configured
             precedent, the reused aged Common set present + profiled, the read APIs exercised on the reference mesh,
             free RAM.  -> p06_import_dry_<run>.json + p06_import_dry_LATEST.json, prints each batch's APPLY confirm.
             Marker FLATV3_P06IMPORT_DRY_OK|run=..|wings=15|packages=105|hash=..
  APPLY k    {"mode": "APPLY", "batch": k, "confirm": "APPLY P06IMPORT BATCH k #<hash8>"}      creates + saves batch k
             ONE batch (<= 3 wings, 21 packages) per MCP call.  CREATE-ONLY: refuses if any target exists.
             Marker FLATV3_P06IMPORT_APPLY_OK|run=..|batch=k|wings=..|saved=21 -- only after the asserted read-back.
  VERIFY     {"mode": "VERIFY", "confirm": "VERIFY P06IMPORT"}                                  read-only, all 15
             FLATV3_P06IMPORT_VERIFY_OK|run=..|wings=15  or  FLATV3_P06IMPORT_VERIFY_INCOMPLETE|run=..|ok=..|missing=..
  UNDO_LIST  {"mode": "UNDO_LIST", "confirm": "UNDO_LIST P06IMPORT"}  writes p06_import_undo_list.json: the packages
             of every SAVED batch in a reference-safe delete order + how.  It deletes NOTHING (manual undo only).
             Offline twin: python p06_import.py --undo-list
Failure: FLATV3_P06IMPORT_STOPPED|run=..|batch=..|reason=..  + p06_import_<mode>[_b<k>]_<run>_FAILURE.json.
  An APPLY failure BEFORE the save leaves this batch's new packages unsaved in memory: nothing is on disk, nothing is
  deleted or reloaded here (memory ue58-reimport-revert-by-reload-fails) -- the record says "Don't-Save editor
  restart".  A failure DURING the save lists exactly what reached disk (the undo list covers it).

Tiers per claim: [decl] / [prec] / [meas] / [inf] as in p06_import_core.py.  Precedent calls are cited per function.
No unreal object lives in a module global (memory puss-mcp-python-crashes-the-editor); the slot_a library is loaded
by path under a private name, never via sys.modules.
"""
import ast
import datetime
import importlib.util
import json
import os
import sys
import types

try:
    import unreal
except ModuleNotFoundError:  # offline harness / --undo-list
    unreal = None

ARGS_NAME = "p06_import_args.json"
LEDGER_NAME = "p06_import_ledger.json"
DRY_LATEST = "p06_import_dry_LATEST.json"


def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                            "CodexFlatV3", "p06import")
    return os.path.dirname(os.path.abspath(__file__))


def _load_core(here):
    spec = importlib.util.spec_from_file_location("p06_import_core_live", os.path.join(here, "p06_import_core.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_json(path, doc):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True, default=str)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    with open(path, "r", encoding="utf-8") as fh:   # read back (setters and writers can lie)
        if json.load(fh) != json.loads(json.dumps(doc, sort_keys=True, default=str)):
            raise RuntimeError("JSON_READBACK %s" % path)
    return path


def _read_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# =====================================================================================================================
# Unreal access (the harness replaces this class with a fake)
# =====================================================================================================================

class UnrealOps:
    def __init__(self, core):
        self.core = core
        self._lib = None
        self._created = []

    # ---- library: slot_a_import.py as a library, its trailing main() stripped (swapkit/p06_import.py:31-45 [prec])
    def lib(self):
        if self._lib is None:
            saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
            path = os.path.join(saved, "CodexFlatV3", "slot_a_import.py")
            with open(path, "r", encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), filename=path)
            tree.body = [n for n in tree.body if not (
                isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and
                isinstance(n.value.func, ast.Name) and n.value.func.id == "main")]
            mod = types.ModuleType("flatv3_slot_a_p06import_lib")
            mod.__file__ = path
            exec(compile(tree, path, "exec"), mod.__dict__)
            mod.RUN = "P06IMPORT_LIBRARY_ONLY"
            self._lib = mod
        return self._lib

    # ---- context
    def log(self, msg):
        unreal.log(msg)

    def log_error(self, msg):
        unreal.log_error(msg)

    def project_dir(self):
        return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())

    def guard_context(self):
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        if editor.get_game_world() is not None:
            raise self.core.PlanError("PIE_OR_SIE_ACTIVE (refused; this tool never ends PIE)")
        world = editor.get_editor_world()
        name = world.get_outermost().get_name() if world else None
        if name != self.core.WORLD_PATH:
            raise self.core.PlanError("WRONG_WORLD %s" % name)

    def census(self):
        names = lambda ps: sorted(str(p.get_name()).split(".", 1)[0] for p in ps)  # noqa: E731
        return {"content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
                "maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}

    def free_ram_gb(self):
        import ctypes

        class MemStatus(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        st = MemStatus()
        st.dwLength = ctypes.sizeof(MemStatus)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            raise RuntimeError("RAM_READ_FAILED")
        return st.ullAvailPhys / float(1 << 30)

    def asset_exists(self, path):
        return bool(unreal.EditorAssetLibrary.does_asset_exist(path))

    def package_on_disk(self, path):
        content = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir())
        return os.path.isfile(os.path.join(content, path[len("/Game/"):].replace("/", os.sep) + ".uasset"))

    def _load(self, path, kind=None):
        v = unreal.EditorAssetLibrary.load_asset(path)
        if v is None or (kind is not None and not isinstance(v, kind)):
            raise RuntimeError("LOAD_FAIL|%s" % path)
        return v

    @staticmethod
    def _pkg(obj):
        return None if obj is None else str(obj.get_path_name()).split(".", 1)[0]

    def _slots(self, mesh):
        return [[str(s.get_editor_property("material_slot_name")), self._pkg(s.get_editor_property("material_interface"))]
                for s in mesh.get_editor_property("static_materials")]

    def _collision(self, mesh):
        sub = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
        return int(sub.get_simple_collision_count(mesh))          # StaticMeshEditorSubsystem.h:259 [decl]

    def _tex_props(self, tex):
        return {p: str(tex.get_editor_property(p)) for p in self.core.TEXTURE_CMP}

    def _edge_geometry(self, mesh):
        """edge_rollout_core.edge_geometry [prec, ran 6 Oct EDGE_ROLLOUT]."""
        sub = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
        out = []
        for lod in range(int(mesh.get_num_lods())):
            ranges = {}
            for section in range(64):
                slot = int(sub.get_lod_material_slot(mesh, lod, section))
                if slot < 0:
                    break
                if slot not in (0, 3):
                    continue
                verts = list(unreal.ProceduralMeshLibrary.get_section_from_static_mesh(mesh, lod, section)[0])
                if not verts:
                    continue
                xs = [float(v.x) for v in verts]
                r = ranges.setdefault(slot, [1e9, -1e9])
                r[0], r[1] = min(r[0], min(xs)), max(r[1], max(xs))
            out.append({"lod": lod, "front_x": ranges.get(0), "edge_x": ranges.get(3)})
        return out

    def _folder(self, folder):
        if not unreal.EditorAssetLibrary.does_directory_exist(folder):
            return set()
        return set(str(p).split(".", 1)[0] for p in
                   unreal.EditorAssetLibrary.list_assets(folder, recursive=False, include_folder=False))

    # ---- DRY reads: the precedent's live state + an exercise of every read API the APPLY gates use
    def reference_state(self):
        core, pilot = self.core, self.lib().pilot
        ref = core.REFERENCE
        mesh = self._load(ref["mesh"], unreal.StaticMesh)
        geom = self._edge_geometry(mesh)
        dyn = pilot.dynamic_lod(mesh, 0)
        state = {"mesh_slots": self._slots(mesh), "collision_count": self._collision(mesh),
                 "num_lods": int(mesh.get_num_lods()), "edge_geometry": geom,
                 "socket_names": sorted(pilot.socket_report(mesh)), "lod0_triangles": int(dyn["triangles"]),
                 "Front_parent": self._pkg(self._load(ref["Front"]).get_editor_property("parent")),
                 "Flap_parent": self._pkg(self._load(ref["Flap"]).get_editor_property("parent")),
                 "textures": {k: self._tex_props(self._load(p, unreal.Texture2D)) for k, p in ref["textures"].items()},
                 "texture_kind_errors": {},
                 "parents_exist": {p: self.asset_exists(p) for p in sorted(core.PARENTS.values())}}
        for k, p in ref["textures"].items():     # the reference must itself pass the kind rule we will assert
            try:
                pilot.verify_texture(self._load(p, unreal.Texture2D), core.TEXTURE_KINDS[k])
            except Exception as exc:  # noqa: BLE001 -- becomes a DRY refusal
                state["texture_kind_errors"][k] = str(exc)[:300]
        return state

    def common_aged_state(self):
        pilot = self.lib().pilot
        out = {}
        for name in self.core.COMMON_AGED:
            path = "%s/%s" % (self.core.AGED_COMMON_ROOT, name)
            out[name] = pilot.verify_texture(self._load(path, unreal.Texture2D), pilot.texture_kind(name, "aged"))
        return out

    # ---- APPLY
    def created_packages(self):
        return list(self._created)

    def _write_sockets(self, mesh, rows):
        """hf_workflow._sockets_from_sidecar [prec, ran FV3HF-20261006-P06]: update a socket Interchange made, else
        add one; modify() first."""
        mesh.modify()
        for name in sorted(rows):
            row = rows[name]
            sock = mesh.find_socket(name)
            new = sock is None
            if new:
                sock = unreal.StaticMeshSocket(outer=mesh)
            else:
                sock.modify()
            rot = row["relative_rotation_deg"]
            sock.set_editor_property("socket_name", name)
            sock.set_editor_property("relative_location", unreal.Vector(*[float(v) for v in row["relative_location_cm"]]))
            sock.set_editor_property("relative_rotation", unreal.Rotator(roll=float(rot["roll"]), pitch=float(rot["pitch"]),
                                                                         yaw=float(rot["yaw"])))
            if new:
                mesh.add_socket(sock)

    def _geometry(self, mesh, w, socket_rows):
        """slot_a_import.verify_flat_general [prec, ran FV3P06I-20261002-04] with two measured changes (core._wing):
        socket names from the sidecar (= baked poles), pivot Z at half the manifest height.  Plus the edge-v3 geometry
        gate, the manifest-height gate and the collision count."""
        core, sa = self.core, self.lib()
        pilot = sa.pilot
        exp = w["expected"]
        slots = [s[0] for s in self._slots(mesh)]
        if slots != list(core.SLOTS):
            raise RuntimeError("SLOT_ORDER_FAIL|%s|%s" % (w["asset"], slots))
        lods = int(mesh.get_num_lods())
        if lods != 2:
            raise RuntimeError("LOD_COUNT_FAIL|%s|%d (FBX LodGroup not honoured?)" % (w["asset"], lods))
        box = mesh.get_bounding_box()
        mn = [float(box.min.x), float(box.min.y), float(box.min.z)]
        mx = [float(box.max.x), float(box.max.y), float(box.max.z)]
        if any(abs(a - b) > core.BOUNDS_TOL_CM for a, b in zip(mn + mx, exp["bounds_cm"]["min"] + exp["bounds_cm"]["max"])):
            raise RuntimeError("BOUNDS_MISMATCH|%s|%s|%s" % (w["asset"], [mn, mx], exp["bounds_cm"]))
        if not core.side_extension_ok(w["side"], mn, mx):
            raise RuntimeError("SIDE_EXTENSION_FAIL|%s|%s" % (w["asset"], [mn[1], mx[1]]))
        hg = core.height_gate({"min": mn, "max": mx}, w["height_cm"], exp["pole"])
        if hg:
            raise RuntimeError("%s|%s" % (hg, w["asset"]))
        sockets = sa.verify_socket_rows(mesh, socket_rows)
        if sorted(sockets) != sorted(exp["sockets"]):
            raise RuntimeError("SOCKET_NAMES_FAIL|%s|%s" % (w["asset"], sorted(sockets)))
        hinge, pivot = sockets["SOCKET_Hinge"], sockets["SOCKET_Pivot"]
        if max(abs(v) for v in hinge["location_cm"]) > 1.0 or abs(hinge["local_x_axis"][1]) < 0.99:
            raise RuntimeError("HINGE_SOCKET_FAIL|%s|%s" % (w["asset"], hinge))
        if abs(pivot["location_cm"][0]) > 1.0 or abs(pivot["location_cm"][2] - w["height_cm"] * 0.5) > core.PIVOT_TOL_CM \
                or pivot["local_x_axis"][2] < 0.99:
            raise RuntimeError("PIVOT_SOCKET_FAIL|%s|%s" % (w["asset"], pivot))
        poles = sorted(n for n in sockets if n.startswith("SOCKET_Pole_"))
        sections = {}
        for lod in (0, 1):
            _, by_slot = pilot.lod_section_slots(mesh, lod)
            front = pilot.section_uv0(mesh, lod, by_slot[0]) if 0 in by_slot else None
            flap = pilot.section_uv0(mesh, lod, by_slot[1]) if 1 in by_slot else None
            if front is None or front["du_dY"] <= 0.0 or front["dv_dZ"] >= 0.0:   # V runs DOWN (ue58-fbx-import-traps)
                raise RuntimeError("FRONT_UV0_SIGN_FAIL|%s|lod%d|%s" % (w["asset"], lod, front))
            if front["normal"][0] > -0.99 or abs(front["normal"][1]) > 0.02 or abs(front["normal"][2]) > 0.02:
                raise RuntimeError("FRONT_NORMAL_FAIL|%s|lod%d|%s" % (w["asset"], lod, front["normal"]))
            if lod == 0 and (flap is None or flap["du_dY"] <= 0.0 or flap["dv_dZ"] >= 0.0):
                raise RuntimeError("FLAP_UV0_SIGN_FAIL|%s|%s" % (w["asset"], flap))
            if lod == 1 and flap is not None:
                raise RuntimeError("LOD1_FLAP_SURVIVED|%s" % w["asset"])
            dyn = pilot.dynamic_lod(mesh, lod)
            want = int(exp["triangles"]["lod%d" % lod])
            if abs(int(dyn["triangles"]) - want) > 1:      # slot_a's measured +-1 cross-importer variance [prec]
                raise RuntimeError("TRIANGLE_COUNT_FAIL|%s|lod%d|%d|%d" % (w["asset"], lod, dyn["triangles"], want))
            raw_timber = dyn["_raw"][2]
            feet = [float(p.y) for c, p in zip(raw_timber["colors"], raw_timber["positions"])
                    if float(c.r) > 0.99 and float(p.z) < -90.0]
            if not feet:
                raise RuntimeError("BAKED_POLE_FOOT_VERTICES_MISSING|%s|lod%d" % (w["asset"], lod))
            for name in poles:
                y = sockets[name]["location_cm"][1]
                if y < min(feet) - 2.0 or y > max(feet) + 2.0:
                    raise RuntimeError("POLE_SOCKET_OUTSIDE_FOOT_RANGE|%s|lod%d|%s|%g" % (w["asset"], lod, name, y))
            sections[str(lod)] = {"Front": front, "Flap": flap, "triangles": int(dyn["triangles"]),
                                  "pole_foot_y_range_cm": [min(feet), max(feet)]}
        if bool(mesh.get_editor_property("nanite_settings").get_editor_property("enabled")):
            raise RuntimeError("NANITE_ENABLED|%s" % w["asset"])
        geom = self._edge_geometry(mesh)
        ok, why = core.edge_geometry_ok(geom)
        if not ok:
            raise RuntimeError("EDGE_GEOMETRY_FAIL|%s|%s" % (w["asset"], why))
        return {"bounds_cm": {"min": mn, "max": mx}, "num_lods": lods, "slots": slots, "sockets": sockets,
                "sections": sections, "edge_geometry": geom}

    def _check_textures(self, w, ref):
        pilot = self.lib().pilot
        out = {}
        for key, kind in self.core.TEXTURE_KINDS.items():
            tex = self._load(w["destinations"][key], unreal.Texture2D)
            props = self._tex_props(tex)
            if props != ref["textures"][key]:
                raise RuntimeError("TEXTURE_PROFILE_VS_REFERENCE|%s|%s|%s" % (key, props, ref["textures"][key]))
            out[key] = dict(pilot.verify_texture(tex, kind), props=props)
        return out

    def _check_materials(self, w, ref, mesh):
        sa, core, d = self.lib(), self.core, w["destinations"]
        skin_paths = {k: d[k] for k in ("SkinColor", "SkinMask", "SkinNormal")}
        inst = {s: sa.verify_instance(self._load(d[s], unreal.MaterialInstanceConstant), d[s], core.PARENTS[s],
                                      skin_paths, w["expected"]["scalars"]) for s in ("Front", "Flap")}
        mats = [s[1] for s in self._slots(mesh)]
        if mats != w["expected"]["slot_materials"]:
            raise RuntimeError("SLOT_MATERIAL_READBACK_FAIL|%s|%s" % (w["asset"], mats))
        coll = self._collision(mesh)
        if coll != ref["collision_count"]:
            raise RuntimeError("COLLISION_VS_REFERENCE|%s|%d|%d" % (w["asset"], coll, ref["collision_count"]))
        return {"instances": inst, "slot_materials": mats, "collision_count": coll}

    def import_wing(self, w, ref):
        """slot_a_import.import_asset [prec] with the hf_workflow socket/texture-profile refinements [prec]."""
        core, sa = self.core, self.lib()
        pilot = sa.pilot
        d, src = w["destinations"], w["sources"]
        folders = sorted({p.rsplit("/", 1)[0] for p in w["packages"]})
        before = {f: self._folder(f) for f in folders}
        mesh = sa.import_one(src["fbx"]["abs"], d["mesh"], pilot.fbx_options(True))
        self._created.append(d["mesh"])
        if not isinstance(mesh, unreal.StaticMesh):
            raise RuntimeError("MESH_CLASS_FAIL|%s" % d["mesh"])
        mesh.modify()
        nanite = mesh.get_editor_property("nanite_settings")
        nanite.set_editor_property("enabled", False)
        mesh.set_editor_property("nanite_settings", nanite)
        socket_rows = sa.socket_payload(src["socket"]["abs"], w["asset"])
        imported = pilot.socket_report(mesh)
        if not set(imported) <= set(socket_rows):
            raise RuntimeError("UNEXPECTED_IMPORTED_SOCKETS|%s|%s" % (w["asset"], sorted(imported)))
        self._write_sockets(mesh, socket_rows)
        textures = {}
        for key, kind in core.TEXTURE_KINDS.items():
            tex = sa.import_one(src[key]["abs"], d[key])
            self._created.append(d[key])
            if not isinstance(tex, unreal.Texture2D):
                raise RuntimeError("TEXTURE_CLASS_FAIL|%s" % d[key])
            pilot.configure_texture(tex, kind)                     # modify() + profile [prec]
            reft = self._load(core.REFERENCE["textures"][key], unreal.Texture2D)
            for prop in core.COPY_FROM_REFERENCE:                  # hf_workflow._copy_texture_settings [prec]
                tex.set_editor_property(prop, reft.get_editor_property(prop))
            textures[key] = tex
        skin = {k: textures[k] for k in ("SkinColor", "SkinMask", "SkinNormal")}
        for slot in ("Front", "Flap"):
            sa.create_instance(d[slot], core.PARENTS[slot], skin, w["expected"]["scalars"])
            self._created.append(d[slot])
        mesh.modify()
        mesh.set_material(0, self._load(d["Front"]))                # slot_a_import.py:518-521 [prec]
        mesh.set_material(1, self._load(d["Flap"]))
        mesh.set_material(2, self._load(core.PARENTS["Timber"]))
        mesh.set_material(3, self._load(core.PARENTS["Edge"]))
        report = {"textures": self._check_textures(w, ref), "geometry": self._geometry(mesh, w, socket_rows),
                  "materials": self._check_materials(w, ref, mesh), "sockets_imported_by_interchange": sorted(imported)}
        after = set()
        for f in folders:
            after |= self._folder(f) - before[f]
        strays = sorted(after - set(w["packages"]))
        if strays:   # never deleted here: the census guard would refuse them anyway; Don't-Save restart clears them
            raise RuntimeError("STRAY_ASSETS_CREATED|%s|%s" % (w["asset"], strays))
        return report

    def save_package(self, path):
        return bool(unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False))

    def readback_wing(self, w, ref):
        mesh = self._load(w["destinations"]["mesh"], unreal.StaticMesh)
        rows = self.lib().socket_payload(w["sources"]["socket"]["abs"], w["asset"])
        return {"textures": self._check_textures(w, ref), "geometry": self._geometry(mesh, w, rows),
                "materials": self._check_materials(w, ref, mesh)}

    def collect_garbage(self):
        unreal.SystemLibrary.collect_garbage()


# =====================================================================================================================
# Orchestration (pure Python over an ops object; the harness drives these with a fake)
# =====================================================================================================================

def _stop(ops, core, run, reason, batch=None):
    ops.log_error("%s_STOPPED|run=%s|batch=%s|reason=%s" % (core.MARK, run, batch if batch is not None else "-",
                                                            str(reason)[:600]))
    raise core.PlanError(reason)


def _guard_start(ops, core, run, batch=None):
    try:
        ops.guard_context()
    except core.PlanError as exc:
        _stop(ops, core, run, str(exc), batch)
    c = ops.census()
    if c != {"content": [], "maps": []}:
        _stop(ops, core, run, "DIRTY_CENSUS (another stream's unsaved work? refused) %s" % json.dumps(c), batch)


def _plan(ops, core, run, batch=None):
    plan = core.build_plan(ops.project_dir())
    if plan["refusals"]:
        _stop(ops, core, run, "PLAN_FILE_GATES %s" % plan["refusals"][:6], batch)
    return plan


def _reference_refusals(core, ref):
    out = []
    for p, ok in ref["parents_exist"].items():
        if not ok:
            out.append("PARENT_MISSING %s" % p)
    if ref["Front_parent"] != core.PARENTS["Front"] or ref["Flap_parent"] != core.PARENTS["Flap"]:
        out.append("REFERENCE_MI_PARENT %s/%s != configured %s/%s (the precedent moved: re-decide PARENTS)" % (
            ref["Front_parent"], ref["Flap_parent"], core.PARENTS["Front"], core.PARENTS["Flap"]))
    slots = ref["mesh_slots"]
    if [s[0] for s in slots] != list(core.SLOTS):
        out.append("REFERENCE_SLOT_NAMES %s" % slots)
    elif slots[2][1] != core.PARENTS["Timber"] or slots[3][1] != core.PARENTS["Edge"]:
        out.append("REFERENCE_TIMBER_EDGE %s/%s != configured %s/%s" % (slots[2][1], slots[3][1], core.PARENTS["Timber"],
                                                                        core.PARENTS["Edge"]))
    for k, err in sorted(ref.get("texture_kind_errors", {}).items()):
        out.append("REFERENCE_TEXTURE_KIND %s %s" % (k, err))
    ok, why = core.edge_geometry_ok(ref["edge_geometry"])
    if not ok:
        out.append("REFERENCE_EDGE_GEOMETRY %s (the read API or the gate is wrong)" % why)
    if ref["num_lods"] != 2:
        out.append("REFERENCE_LODS %s" % ref["num_lods"])
    return out


def run_dry(ops, core, args, run, here):
    _guard_start(ops, core, run)
    plan = core.build_plan(ops.project_dir())
    refusals = list(plan["refusals"])
    existing = sorted(p for w in plan["wings"].values() for p in w["packages"] if ops.asset_exists(p))
    if existing:
        refusals.append("CREATE_ONLY_TARGETS_EXIST %d %s" % (len(existing), existing[:5]))
    ref = ops.reference_state()
    refusals += _reference_refusals(core, ref)
    try:
        aged = ops.common_aged_state()
    except Exception as exc:   # noqa: BLE001 -- recorded as a refusal, the DRY still writes its record
        aged = None
        refusals.append("AGED_COMMON_NOT_READY %s" % exc)
    ram = ops.free_ram_gb()
    if ram < float(args.get("min_free_ram_gb") or core.MIN_FREE_RAM_GB):
        refusals.append("LOW_RAM %.1f GB free" % ram)
    if ops.census() != {"content": [], "maps": []}:
        refusals.append("DRY_DIRTIED_THE_EDITOR %s" % ops.census())
    tokens = {str(b["batch"]): core.confirm_for("APPLY", plan, b["batch"]) for b in plan["batches"]}
    doc = {"run_id": run, "mode": "DRY", "status": "PASS" if not refusals else "REFUSED", "refusals": refusals,
           "inputs_hash": plan["inputs_hash"], "reference": ref, "aged_common": aged, "free_ram_gb": round(ram, 2),
           "batches": plan["batches"], "apply_confirms": tokens,
           "wings": {k: {"owner": w["owner"], "asset": w["asset"], "destinations": w["destinations"],
                         "notes": w.get("notes", [])} for k, w in plan["wings"].items()},
           "utc": datetime.datetime.utcnow().isoformat() + "Z"}
    _write_json(os.path.join(here, "p06_import_dry_%s.json" % run), doc)
    _write_json(os.path.join(here, DRY_LATEST), doc)
    if refusals:
        _stop(ops, core, run, "DRY_REFUSED %d: %s" % (len(refusals), refusals[:6]))
    ops.log("%s_DRY_OK|run=%s|wings=%d|packages=%d|hash=%s|ram_gb=%.1f" % (
        core.MARK, run, len(plan["wings"]), plan["package_count"], plan["inputs_hash"][:8], ram))
    for k in sorted(tokens, key=int):
        ops.log("%s_DRY_CONFIRM|run=%s|batch=%s|confirm=%s" % (core.MARK, run, k, tokens[k]))
    return doc


def run_apply(ops, core, args, plan, run, here, batch):
    _guard_start(ops, core, run, batch)
    dry = _read_json(os.path.join(here, DRY_LATEST))
    if not dry or dry.get("status") != "PASS":
        _stop(ops, core, run, "NO_PASSING_DRY (run DRY first)", batch)
    if dry["inputs_hash"] != plan["inputs_hash"]:
        _stop(ops, core, run, "PLAN_STALE dry %s now %s (sources or config changed: re-run DRY)" % (
            dry["inputs_hash"][:8], plan["inputs_hash"][:8]), batch)
    ledger_path = os.path.join(here, LEDGER_NAME)
    ledger = _read_json(ledger_path, {"batches": {}})
    if ledger["batches"].get(str(batch), {}).get("status") == "SAVED":
        _stop(ops, core, run, "BATCH_ALREADY_SAVED %d (run %s)" % (batch, ledger["batches"][str(batch)]["run_id"]), batch)
    b = plan["batches"][batch - 1]
    existing = [p for p in b["packages"] if ops.asset_exists(p)]
    if existing:
        _stop(ops, core, run, "CREATE_ONLY_TARGETS_EXIST %s" % existing, batch)
    ram0 = ops.free_ram_gb()
    if ram0 < float(args.get("min_free_ram_gb") or core.MIN_FREE_RAM_GB):
        _stop(ops, core, run, "LOW_RAM %.1f GB free (memory ue58-bulk-import-oom-crash)" % ram0, batch)
    ref = ops.reference_state()
    if json.loads(json.dumps(ref, sort_keys=True, default=str)) != dry["reference"]:
        _stop(ops, core, run, "REFERENCE_DRIFT_SINCE_DRY", batch)
    wings = [plan["wings"][str(p)] for p in b["picks"]]
    rec = {"run_id": run, "mode": "APPLY", "batch": batch, "picks": b["picks"], "owners": b["owners"],
           "planned": b["packages"], "ram_gb_before": round(ram0, 2), "inputs_hash": plan["inputs_hash"]}
    fail_path = os.path.join(here, "p06_import_apply_b%d_%s_FAILURE.json" % (batch, run))
    reports = {}
    try:
        for w in wings:
            reports[w["owner"]] = ops.import_wing(w, ref)
        c = ops.census()
        if not core.census_exact(c, b["packages"]):
            raise core.PlanError("DIRTY_SET_NOT_EXACT want %d batch packages, got %s" % (len(b["packages"]), c))
    except Exception as exc:  # noqa: BLE001
        rec.update({"status": "FAILED_UNSAVED", "reason": str(exc), "created_unsaved": ops.created_packages(),
                    "census": ops.census(), "saved": [],
                    "next": "NOTHING was saved or deleted. Restart the editor and answer Don't Save for these packages "
                            "(nothing of this batch is on disk); then DRY again. Never reload/delete them in-editor."})
        _write_json(fail_path, rec)
        _stop(ops, core, run, "IMPORT_GATE %s" % exc, batch)
    saved = []
    try:
        for p in sorted(b["packages"]):
            if not ops.save_package(p):
                raise core.PlanError("SAVE_FAIL %s" % p)
            saved.append(p)
        c = ops.census()
        if c["maps"] or not set(c["content"]) <= set(b["packages"]):
            raise core.PlanError("FOREIGN_DIRTY_AFTER_SAVE %s" % c)
        for p in c["content"]:             # settle pass inside the batch only (slot_a save_narrow [prec])
            if not ops.save_package(p):
                raise core.PlanError("SETTLE_SAVE_FAIL %s" % p)
        c = ops.census()
        if c != {"content": [], "maps": []}:
            raise core.PlanError("DIRTY_AFTER_SAVE %s" % c)
        missing = [p for p in b["packages"] if not ops.package_on_disk(p)]
        if missing:
            raise core.PlanError("NOT_ON_DISK_AFTER_SAVE %s" % missing)
        readback = {w["owner"]: ops.readback_wing(w, ref) for w in wings}
        if ops.census() != {"content": [], "maps": []}:
            raise core.PlanError("READBACK_DIRTIED %s" % ops.census())
    except Exception as exc:  # noqa: BLE001
        rec.update({"status": "FAILED_AFTER_SAVE" if saved else "FAILED_UNSAVED", "reason": str(exc), "saved": saved,
                    "census": ops.census(), "created_unsaved": [p for p in ops.created_packages() if p not in saved],
                    "next": "Saved packages are listed in 'saved' (UNDO_LIST covers them). Do not re-run this batch: "
                            "CREATE-ONLY will refuse while any of them exists."})
        ledger["batches"][str(batch)] = {"run_id": run, "status": rec["status"], "saved": saved}
        _write_json(ledger_path, ledger)
        _write_json(fail_path, rec)
        _stop(ops, core, run, "SAVE_OR_READBACK %s" % exc, batch)
    ops.collect_garbage()
    ram1 = ops.free_ram_gb()
    rec.update({"status": "SAVED", "saved": saved, "import_reports": reports, "readback": readback,
                "ram_gb_after_gc": round(ram1, 2), "census_after": ops.census()})
    ledger["batches"][str(batch)] = {"run_id": run, "status": "SAVED", "saved": saved, "owners": b["owners"]}
    out = _write_json(os.path.join(here, "p06_import_apply_b%d_%s.json" % (batch, run)), rec)
    _write_json(ledger_path, ledger)
    left = [x["batch"] for x in plan["batches"] if ledger["batches"].get(str(x["batch"]), {}).get("status") != "SAVED"]
    ops.log("%s_APPLY_OK|run=%s|batch=%d|wings=%s|saved=%d|remaining_batches=%s|ram_gb=%.1f|report=%s" % (
        core.MARK, run, batch, ",".join(b["owners"]), len(saved), left, ram1, out))
    return rec


def run_verify(ops, core, args, run, here):
    _guard_start(ops, core, run)
    plan = _plan(ops, core, run)
    ref = ops.reference_state()
    refs = _reference_refusals(core, ref)
    if refs:
        _stop(ops, core, run, "REFERENCE %s" % refs)
    ok, missing, partial, failed = [], [], [], {}
    details = {}
    for k, w in sorted(plan["wings"].items(), key=lambda kv: int(kv[0])):
        there = [p for p in w["packages"] if ops.asset_exists(p)]
        if not there:
            missing.append(w["owner"])
            continue
        if len(there) != len(w["packages"]):
            partial.append(w["owner"])
            continue
        try:
            details[w["owner"]] = ops.readback_wing(w, ref)
            ok.append(w["owner"])
        except Exception as exc:  # noqa: BLE001
            failed[w["owner"]] = str(exc)
    c = ops.census()
    if c != {"content": [], "maps": []}:
        failed["_census"] = "VERIFY_DIRTIED %s" % c
    doc = {"run_id": run, "mode": "VERIFY", "ok": ok, "missing": missing, "partial": partial, "failed": failed,
           "details": details, "status": "PASS" if len(ok) == len(plan["wings"]) and not failed else "INCOMPLETE"}
    out = _write_json(os.path.join(here, "p06_import_verify_%s.json" % run), doc)
    if doc["status"] == "PASS":
        ops.log("%s_VERIFY_OK|run=%s|wings=%d|report=%s" % (core.MARK, run, len(ok), out))
    else:
        ops.log_error("%s_VERIFY_INCOMPLETE|run=%s|ok=%d|missing=%d|partial=%s|failed=%s|report=%s" % (
            core.MARK, run, len(ok), len(missing), partial, sorted(failed), out))
    return doc


def run_undo_list(core, project, here, log):
    plan = core.build_plan(project)
    ledger = _read_json(os.path.join(here, LEDGER_NAME), {"batches": {}})
    doc = core.undo_list(plan, ledger)
    for k, v in ledger["batches"].items():
        if v.get("status") == "FAILED_AFTER_SAVE":
            doc["batches"].append({"batch": int(k), "partial_save": True, "delete_in_order": v.get("saved", [])})
    out = _write_json(os.path.join(here, "p06_import_undo_list.json"), doc)
    n = sum(len(b["delete_in_order"]) for b in doc["batches"])
    log("%s_UNDO_LIST|packages=%d|batches=%s|auto_delete=False|file=%s" % (core.MARK, n,
                                                                           [b["batch"] for b in doc["batches"]], out))
    return doc


def main():
    here = _here()
    core = _load_core(here)
    ops = UnrealOps(core)
    run = datetime.datetime.now().strftime("P06IMP-%Y%m%d-%H%M%S")
    batch = None
    try:
        args = _read_json(os.path.join(here, ARGS_NAME))
        if not isinstance(args, dict):
            raise core.PlanError("ARGS_MISSING %s" % ARGS_NAME)
        run = str(args.get("run_id") or run)
        mode = str(args.get("mode") or "").upper()
        plan = core.build_plan(ops.project_dir()) if mode == "APPLY" else None
        mode, batch = core.validate_args(args, plan)
    except (core.PlanError, OSError, ValueError, KeyError) as exc:
        _stop(ops, core, run, "ARGS|%s" % exc, batch)
    try:
        if mode == "DRY":
            run_dry(ops, core, args, run, here)
        elif mode == "APPLY":
            if plan["refusals"]:
                _stop(ops, core, run, "PLAN_FILE_GATES %s" % plan["refusals"][:6], batch)
            run_apply(ops, core, args, plan, run, here, batch)
        elif mode == "VERIFY":
            run_verify(ops, core, args, run, here)
        else:
            run_undo_list(core, ops.project_dir(), here, ops.log)
    except core.PlanError:
        raise                                   # already logged as STOPPED
    except Exception as exc:                    # noqa: BLE001 -- an unexpected API error is a STOP, never a pass
        _stop(ops, core, run, "UNEXPECTED %s: %s" % (type(exc).__name__, exc), batch)


if unreal is not None:
    main()
elif __name__ == "__main__" and "--undo-list" in sys.argv:
    _h = _here()
    _c = _load_core(_h)
    run_undo_list(_c, os.path.abspath(os.path.join(_h, "..", "..", "..")), _h, print)
