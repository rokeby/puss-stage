"""RZIMPORT -- Unreal entry (7 Oct, offline-written, NEVER RUN IN UNREAL BY ITS AUTHOR).  Generalises the P06 kit
Saved/CodexFlatV3/p06import/p06_import.py (ran live 7 Oct, DRY/5 APPLY batches/VERIFY all PASS [meas its records]).

Run ONLY through rzimport_run.py (purges the Saved module cache, then runs this file) with rzimport_args.json:

  DRY        {"mode": "DRY", "confirm": "DRY RZIMPORT", "manifests": [..]}            read-only, CLEAN census
             file gates, every target FREE, parents exist, the live P06 reference (MI parents, slots 2/3, collision,
             texture profiles) = the configured precedent, aged Common present + profiled, free RAM.
             -> rzimport_dry_<run>.json + rzimport_dry_<hash8>_LATEST.json; logs each batch's APPLY confirm.
             Marker FLATV3_RZIMPORT_DRY_OK|run=..|plan=<hash8>|wings=..|packages=..
  APPLY k    {"mode": "APPLY", "batch": k, "confirm": "APPLY RZIMPORT BATCH k #<hash8>", "manifests": [..]}
             ONE batch (<= 3 entries, <= 21 packages) per MCP call, CREATE-ONLY.
             Marker FLATV3_RZIMPORT_APPLY_OK|run=..|plan=..|batch=k|owners=..|saved=.. -- only after asserted read-back.
  VERIFY     {"mode": "VERIFY", "confirm": "VERIFY RZIMPORT", "manifests": [..]}          read-only, all entries
             FLATV3_RZIMPORT_VERIFY_OK|run=..|plan=..|wings=N  or  FLATV3_RZIMPORT_VERIFY_INCOMPLETE|..
  UNDO_LIST  {"mode": "UNDO_LIST", "confirm": "UNDO_LIST RZIMPORT", "manifests": [..]}  deletes NOTHING.
Failure: FLATV3_RZIMPORT_STOPPED|run=..|plan=..|batch=..|reason=..  + rzimport_<mode>[_b<k>]_<run>_FAILURE.json.
  An APPLY failure BEFORE the save leaves this batch's new packages unsaved in memory: nothing is deleted or reloaded
  here (memory ue58-reimport-revert-by-reload-fails) -- the record says "Don't-Save editor restart".

Mount-aware mesh gate: measurement here (_measure), decision in rzimport_core.geometry_verdict (pure, harness-tested).
Wing measurement = slot_a_import.verify_flat_general's reads [prec, ran FV3P06I-20261002-04 + P06IMP 7 Oct];
top-border measurement = the same reads minus the pole-foot scan (slot_a_import.verify_top :352-399 [decl]).
No unreal object lives in a module global (memory puss-mcp-python-crashes-the-editor).
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

ARGS_NAME = "rzimport_args.json"


def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                            "CodexFlatV3", "rzimport")
    return os.path.dirname(os.path.abspath(__file__))


def _load_core(here):
    spec = importlib.util.spec_from_file_location("rzimport_core_live", os.path.join(here, "rzimport_core.py"))
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
    with open(path, "r", encoding="utf-8") as fh:
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

    def lib(self):
        """slot_a_import.py as a library, its trailing main() stripped (p06_import.py:91-105 [prec, ran 7 Oct])."""
        if self._lib is None:
            saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
            path = os.path.join(saved, "CodexFlatV3", "slot_a_import.py")
            with open(path, "r", encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), filename=path)
            tree.body = [n for n in tree.body if not (
                isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and
                isinstance(n.value.func, ast.Name) and n.value.func.id == "main")]
            mod = types.ModuleType("flatv3_slot_a_rzimport_lib")
            mod.__file__ = path
            exec(compile(tree, path, "exec"), mod.__dict__)
            mod.RUN = "RZIMPORT_LIBRARY_ONLY"
            self._lib = mod
        return self._lib

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
        """edge_rollout_core.edge_geometry [prec, ran 6 Oct EDGE_ROLLOUT; and P06IMP 7 Oct]."""
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

    # ---- DRY reads (identical to the P06 kit: the reference is the same live P06 asset set)
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
        for k, p in ref["textures"].items():
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
        """hf_workflow._sockets_from_sidecar [prec, ran FV3HF-20261006-P06; P06IMP 7 Oct]. rows {} (top border) =
        nothing written."""
        if not rows:
            return
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

    def _measure(self, mesh, w, socket_rows):
        """Every read slot_a verify_flat_general / verify_top make, as plain data for core.geometry_verdict."""
        sa = self.lib()
        pilot = sa.pilot
        box = mesh.get_bounding_box()
        sockets = sa.verify_socket_rows(mesh, socket_rows)   # names + locations + rotations vs the sidecar [prec]
        m = {"slots": [s[0] for s in self._slots(mesh)], "num_lods": int(mesh.get_num_lods()),
             "bounds_cm": {"min": [float(box.min.x), float(box.min.y), float(box.min.z)],
                           "max": [float(box.max.x), float(box.max.y), float(box.max.z)]},
             "sockets": {k: {"location_cm": v["location_cm"], "local_x_axis": v["local_x_axis"]}
                         for k, v in sockets.items()},
             "nanite": bool(mesh.get_editor_property("nanite_settings").get_editor_property("enabled")),
             "lods": {}, "edge_geometry": self._edge_geometry(mesh)}
        for lod in (0, 1):
            if lod >= m["num_lods"]:
                continue
            _, by_slot = pilot.lod_section_slots(mesh, lod)
            front = pilot.section_uv0(mesh, lod, by_slot[0]) if 0 in by_slot else None
            flap = pilot.section_uv0(mesh, lod, by_slot[1]) if 1 in by_slot else None
            dyn = pilot.dynamic_lod(mesh, lod)
            feet = None
            if w["mount"] == "wing":
                raw_timber = dyn["_raw"][2]
                feet = [float(p.y) for c, p in zip(raw_timber["colors"], raw_timber["positions"])
                        if float(c.r) > 0.99 and float(p.z) < -90.0]
            m["lods"][str(lod)] = {"front": front, "flap": flap, "triangles": int(dyn["triangles"]), "foot_y": feet}
        return m

    def _geometry(self, mesh, w, socket_rows):
        m = self._measure(mesh, w, socket_rows)
        bad = self.core.geometry_verdict(w, m)
        if bad:
            raise RuntimeError("GEOMETRY_GATE|" + " ; ".join(bad[:6]))
        return m

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
        """slot_a_import.import_asset [prec] + hf_workflow socket/texture-profile refinements [prec]; = the P06 kit's
        import_wing (p06_import.py:349-397, ran 7 Oct) with the mount-aware gate."""
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
            pilot.configure_texture(tex, kind)
            reft = self._load(core.REFERENCE["textures"][key], unreal.Texture2D)
            for prop in core.COPY_FROM_REFERENCE:
                tex.set_editor_property(prop, reft.get_editor_property(prop))
            textures[key] = tex
        skin = {k: textures[k] for k in ("SkinColor", "SkinMask", "SkinNormal")}
        for slot in ("Front", "Flap"):
            sa.create_instance(d[slot], core.PARENTS[slot], skin, w["expected"]["scalars"])
            self._created.append(d[slot])
        mesh.modify()
        mesh.set_material(0, self._load(d["Front"]))
        mesh.set_material(1, self._load(d["Flap"]))
        mesh.set_material(2, self._load(core.PARENTS["Timber"]))
        mesh.set_material(3, self._load(core.PARENTS["Edge"]))
        report = {"textures": self._check_textures(w, ref), "geometry": self._geometry(mesh, w, socket_rows),
                  "materials": self._check_materials(w, ref, mesh), "sockets_imported_by_interchange": sorted(imported)}
        after = set()
        for f in folders:
            after |= self._folder(f) - before[f]
        strays = sorted(after - set(w["packages"]))
        if strays:
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
# Orchestration (pure Python over an ops object; the harness drives these with a fake) -- p06_import.py:416-630
# =====================================================================================================================

def _stop(ops, core, run, reason, batch=None, plan=None):
    ops.log_error("%s_STOPPED|run=%s|plan=%s|batch=%s|reason=%s" % (
        core.MARK, run, plan["hash8"] if plan else "-", batch if batch is not None else "-", str(reason)[:600]))
    raise core.PlanError(reason)


def _guard_start(ops, core, run, batch=None, plan=None):
    try:
        ops.guard_context()
    except core.PlanError as exc:
        _stop(ops, core, run, str(exc), batch, plan)
    c = ops.census()
    if c != {"content": [], "maps": []}:
        _stop(ops, core, run, "DIRTY_CENSUS (another stream's unsaved work? refused) %s" % json.dumps(c), batch, plan)


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
    plan = core.build_plan(ops.project_dir(), args["manifests"])
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
           "inputs_hash": plan["inputs_hash"], "manifests": plan["manifests"], "reference": ref, "aged_common": aged,
           "free_ram_gb": round(ram, 2), "batches": plan["batches"], "apply_confirms": tokens,
           "wings": {k: {"owner": w["owner"], "asset": w["asset"], "mount": w["mount"], "passage": w["passage"],
                         "height_cm": w["height_cm"], "destinations": w["destinations"], "notes": w.get("notes", [])}
                     for k, w in plan["wings"].items()},
           "utc": datetime.datetime.utcnow().isoformat() + "Z"}
    _write_json(os.path.join(here, "rzimport_dry_%s.json" % run), doc)
    _write_json(os.path.join(here, core.dry_latest_name(plan)), doc)
    if refusals:
        _stop(ops, core, run, "DRY_REFUSED %d: %s" % (len(refusals), refusals[:6]), plan=plan)
    ops.log("%s_DRY_OK|run=%s|plan=%s|wings=%d|packages=%d|mounts=%s|ram_gb=%.1f" % (
        core.MARK, run, plan["hash8"], len(plan["wings"]), plan["package_count"], ",".join(plan["mounts"]), ram))
    for k in sorted(tokens, key=int):
        ops.log("%s_DRY_CONFIRM|run=%s|plan=%s|batch=%s|confirm=%s" % (core.MARK, run, plan["hash8"], k, tokens[k]))
    return doc


def run_apply(ops, core, args, plan, run, here, batch):
    _guard_start(ops, core, run, batch, plan)
    dry = _read_json(os.path.join(here, core.dry_latest_name(plan)))
    if not dry or dry.get("status") != "PASS":
        _stop(ops, core, run, "NO_PASSING_DRY for plan %s (run DRY first)" % plan["hash8"], batch, plan)
    if dry["inputs_hash"] != plan["inputs_hash"]:
        _stop(ops, core, run, "PLAN_STALE dry %s now %s (re-run DRY)" % (dry["inputs_hash"][:8], plan["hash8"]), batch, plan)
    ledger_path = os.path.join(here, core.ledger_name(plan))
    ledger = _read_json(ledger_path, {"plan": plan["inputs_hash"], "batches": {}})
    if ledger["batches"].get(str(batch), {}).get("status") == "SAVED":
        _stop(ops, core, run, "BATCH_ALREADY_SAVED %d (run %s)" % (batch, ledger["batches"][str(batch)]["run_id"]), batch, plan)
    b = plan["batches"][batch - 1]
    existing = [p for p in b["packages"] if ops.asset_exists(p)]
    if existing:
        _stop(ops, core, run, "CREATE_ONLY_TARGETS_EXIST %s" % existing, batch, plan)
    ram0 = ops.free_ram_gb()
    if ram0 < float(args.get("min_free_ram_gb") or core.MIN_FREE_RAM_GB):
        _stop(ops, core, run, "LOW_RAM %.1f GB free (memory ue58-bulk-import-oom-crash)" % ram0, batch, plan)
    ref = ops.reference_state()
    if json.loads(json.dumps(ref, sort_keys=True, default=str)) != dry["reference"]:
        _stop(ops, core, run, "REFERENCE_DRIFT_SINCE_DRY", batch, plan)
    wings = [plan["wings"][o] for o in b["owners"]]
    rec = {"run_id": run, "mode": "APPLY", "plan": plan["inputs_hash"], "batch": batch, "owners": b["owners"],
           "planned": b["packages"], "ram_gb_before": round(ram0, 2)}
    fail_path = os.path.join(here, "rzimport_apply_b%d_%s_FAILURE.json" % (batch, run))
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
        _stop(ops, core, run, "IMPORT_GATE %s" % exc, batch, plan)
    saved = []
    try:
        for p in sorted(b["packages"]):
            if not ops.save_package(p):
                raise core.PlanError("SAVE_FAIL %s" % p)
            saved.append(p)
        c = ops.census()
        if c["maps"] or not set(c["content"]) <= set(b["packages"]):
            raise core.PlanError("FOREIGN_DIRTY_AFTER_SAVE %s" % c)
        for p in c["content"]:
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
        _stop(ops, core, run, "SAVE_OR_READBACK %s" % exc, batch, plan)
    ops.collect_garbage()
    ram1 = ops.free_ram_gb()
    rec.update({"status": "SAVED", "saved": saved, "import_reports": reports, "readback": readback,
                "ram_gb_after_gc": round(ram1, 2), "census_after": ops.census()})
    ledger["batches"][str(batch)] = {"run_id": run, "status": "SAVED", "saved": saved, "owners": b["owners"]}
    out = _write_json(os.path.join(here, "rzimport_apply_b%d_%s.json" % (batch, run)), rec)
    _write_json(ledger_path, ledger)
    left = [x["batch"] for x in plan["batches"] if ledger["batches"].get(str(x["batch"]), {}).get("status") != "SAVED"]
    ops.log("%s_APPLY_OK|run=%s|plan=%s|batch=%d|owners=%s|saved=%d|remaining_batches=%s|ram_gb=%.1f|report=%s" % (
        core.MARK, run, plan["hash8"], batch, ",".join(b["owners"]), len(saved), left, ram1, out))
    return rec


def run_verify(ops, core, args, run, here):
    _guard_start(ops, core, run)
    plan = core.build_plan(ops.project_dir(), args["manifests"])
    real = [r for r in plan["refusals"] if not r.startswith("DESTINATION_CLASH_WITH_P06_IMPORT")]
    if real:
        _stop(ops, core, run, "PLAN_FILE_GATES %s" % real[:6], plan=plan)
    ref = ops.reference_state()
    refs = _reference_refusals(core, ref)
    if refs:
        _stop(ops, core, run, "REFERENCE %s" % refs, plan=plan)
    ok, missing, partial, failed, details = [], [], [], {}, {}
    for k, w in sorted(plan["wings"].items()):
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
    doc = {"run_id": run, "mode": "VERIFY", "plan": plan["inputs_hash"], "manifests": plan["manifests"], "ok": ok,
           "missing": missing, "partial": partial, "failed": failed, "details": details,
           "mesh_paths": {o: plan["wings"][o]["destinations"]["mesh"] for o in ok},
           "status": "PASS" if len(ok) == len(plan["wings"]) and not failed else "INCOMPLETE"}
    out = _write_json(os.path.join(here, "rzimport_verify_%s.json" % run), doc)
    _write_json(os.path.join(here, "rzimport_verify_%s_LATEST.json" % plan["hash8"]), doc)
    if doc["status"] == "PASS":
        ops.log("%s_VERIFY_OK|run=%s|plan=%s|wings=%d|report=%s" % (core.MARK, run, plan["hash8"], len(ok), out))
    else:
        ops.log_error("%s_VERIFY_INCOMPLETE|run=%s|plan=%s|ok=%d|missing=%d|partial=%s|failed=%s|report=%s" % (
            core.MARK, run, plan["hash8"], len(ok), len(missing), partial, sorted(failed), out))
    return doc


def run_undo_list(core, project, here, log, manifests):
    plan = core.build_plan(project, manifests)
    ledger = _read_json(os.path.join(here, core.ledger_name(plan)), {"batches": {}})
    doc = core.undo_list(plan, ledger)
    for k, v in ledger["batches"].items():
        if v.get("status") == "FAILED_AFTER_SAVE":
            doc["batches"].append({"batch": int(k), "partial_save": True, "delete_in_order": v.get("saved", [])})
    out = _write_json(os.path.join(here, "rzimport_undo_list_%s.json" % plan["hash8"]), doc)
    n = sum(len(b["delete_in_order"]) for b in doc["batches"])
    log("%s_UNDO_LIST|plan=%s|packages=%d|batches=%s|auto_delete=False|file=%s" % (
        core.MARK, plan["hash8"], n, [b["batch"] for b in doc["batches"]], out))
    return doc


def main():
    here = _here()
    core = _load_core(here)
    ops = UnrealOps(core)
    run = datetime.datetime.now().strftime("RZIMP-%Y%m%d-%H%M%S")
    batch, plan = None, None
    try:
        args = _read_json(os.path.join(here, ARGS_NAME))
        if not isinstance(args, dict):
            raise core.PlanError("ARGS_MISSING %s" % ARGS_NAME)
        run = str(args.get("run_id") or run)
        mode = str(args.get("mode") or "").upper()
        if mode == "APPLY":
            plan = core.build_plan(ops.project_dir(), args.get("manifests") or [])
        mode, batch = core.validate_args(args, plan)
    except (core.PlanError, OSError, ValueError, KeyError) as exc:
        _stop(ops, core, run, "ARGS|%s" % exc, batch, plan)
    try:
        if mode == "DRY":
            run_dry(ops, core, args, run, here)
        elif mode == "APPLY":
            if plan["refusals"]:
                _stop(ops, core, run, "PLAN_FILE_GATES %s" % plan["refusals"][:6], batch, plan)
            run_apply(ops, core, args, plan, run, here, batch)
        elif mode == "VERIFY":
            run_verify(ops, core, args, run, here)
        else:
            run_undo_list(core, ops.project_dir(), here, ops.log, args["manifests"])
    except core.PlanError:
        raise                                   # already logged as STOPPED
    except Exception as exc:                    # noqa: BLE001 -- an unexpected API error is a STOP, never a pass
        _stop(ops, core, run, "UNEXPECTED %s: %s" % (type(exc).__name__, exc), batch, plan)


if unreal is not None:
    main()
elif __name__ == "__main__" and "--undo-list" in sys.argv:
    _h = _here()
    _c = _load_core(_h)
    _a = _read_json(os.path.join(_h, ARGS_NAME))
    run_undo_list(_c, os.path.abspath(os.path.join(_h, "..", "..", "..")), _h, print, _a["manifests"])
