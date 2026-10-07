"""Flutter + LOD1 tool for the P04 / P05 / P06 Flat V3 wings (Gary 7 Oct). Modes DRY / APPLY / REVERT.

OFFLINE-AUTHORED 7 Oct 2026; NOT YET RUN IN UNREAL. Editor open on the show level, NO PIE, guarded loopback MCP
route via flutter_lod_run.py (purges the Saved module cache first). Args: flutter_lod_args.json (same folder).

  DRY    read-only. Resolves the meshes the Show's ENABLED wing-pair cues in Passage 4/5/6 currently use, each
         mesh's effective Flap MI (MaterialOverrides win, PassageActor.cpp:1110-1115), the MI parent chain and
         FlutterAmpCm/Hz/MaxCm, the mesh LOD screen sizes and LOD section slots; classifies shared MIs/meshes;
         writes flutter_lod_plan.json + flutter_lod_dry_<run>.json and logs the exact APPLY confirm.
  APPLY  re-resolves (must reproduce the DRY token), writes flutter_lod_originals_ACTIVE.json (read back, path
         logged) BEFORE any change; MIs: modify() + scalar setters + update, read back; meshes in batches:
         modify() + StaticMeshEditorSubsystem.set_lod_screen_sizes (LOD0 and LOD2+ kept), read back; census
         guard per batch (gained == exactly the batch, maps unchanged); saves only the batch; census back to the
         start state; read back after save; collect_garbage between mesh batches.
  REVERT from the ACTIVE originals, field by field (override present/absent + value per name; screen sizes per
         LOD); refuses on drift before writing anything; archives the originals file.
Markers: FLATV3_FLUTTERLOD_{DRY,APPLY,REVERT}_OK|run=..  failure: FLATV3_FLUTTERLOD_FAILED|run=.. +
flutter_lod_<mode>_<run>_FAILURE.json. No Unreal object lives in a module global.
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import os
import pathlib
import re
import time
import traceback

try:
    import unreal
except ImportError:          # offline harness
    unreal = None

HERE = pathlib.Path(globals().get("__file__") or "E:/PussStage/Saved/CodexFlatV3/flutter/tool/flutter_lod.py").resolve().parent
ARGS = HERE / "flutter_lod_args.json"
PLAN = HERE / "flutter_lod_plan.json"
ORIGINALS = HERE / "flutter_lod_originals_ACTIVE.json"


def load_core(here=None):
    """Fresh module object every run (memory ue58-python-stale-module-cache)."""
    here = pathlib.Path(here or HERE)
    spec = importlib.util.spec_from_file_location("_flutter_lod_core_%d" % int(time.time() * 1e6), here / "flutter_lod_core.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_verified(C, path, data):
    text = json.dumps(data, indent=1, sort_keys=True, default=str)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    C.require(json.loads(pathlib.Path(path).read_text(encoding="utf-8")) == json.loads(text), "JSON_READBACK", str(path))


class Ops:
    """Every Unreal call lives here (the harness passes a fake `u`)."""

    def __init__(self, u, C):
        self.u, self.C = u, C

    # ---- basics
    def log(self, msg):
        self.u.log(msg)

    def apath(self, obj):
        return None if obj is None else str(obj.get_path_name()).split(".", 1)[0]

    def guid(self, g):
        return str(self.u.GuidLibrary.conv_guid_to_string(g)).replace("-", "").upper()   # floorgap_engine.py:71

    def editor_ready(self):
        sub = self.u.get_editor_subsystem(self.u.UnrealEditorSubsystem)
        world = sub.get_editor_world()
        self.C.require(world is not None, "NO_EDITOR_WORLD")
        name = str(world.get_outermost().get_name())
        self.C.require(name == self.C.EXPECTED_WORLD, "WRONG_WORLD", name)
        self.C.require(sub.get_game_world() is None, "PIE_OR_SIE_ACTIVE")

    def census(self):
        lib = self.u.EditorLoadingAndSavingUtils
        names = lambda ps: sorted(str(p.get_name()).split(".", 1)[0] for p in ps)  # noqa: E731
        return {"content": names(lib.get_dirty_content_packages()), "maps": names(lib.get_dirty_map_packages())}

    def load(self, path):
        return self.u.EditorAssetLibrary.load_asset(path)

    def gc(self):
        self.u.SystemLibrary.collect_garbage()

    def save(self, path):
        self.C.require(bool(self.u.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)), "SAVE_FAILED", path)

    # ---- Show
    def read_show(self):
        show = self.load(self.C.SHOW_PATH)
        self.C.require(show is not None, "SHOW_LOAD_FAIL")
        passages = []
        for st in show.get_editor_property("passage_settings"):
            g = st.get_editor_property("passage_guid")
            passages.append({"label": str(st.get_editor_property("label")), "guid": self.guid(g),
                             "cue_guids": [self.guid(x) for x in show.get_wing_pair_cue_guids_in_passage(g)]})
        cues = {}
        for cue in show.get_editor_property("cues"):
            if cue.get_editor_property("type") != self.u.InfinityCueType.WING_PAIR:   # floorgap_engine.py:100
                continue
            pair = cue.get_editor_property("wing_pair")
            sides = [("L", "left"), ("R", "right")] + ([("T", "top")] if bool(pair.get_editor_property("has_top")) else [])
            panels = []
            for side, prop in sides:
                panel = pair.get_editor_property(prop)
                text_mesh, text_ovr = self.C.parse_panel_export(panel.export_text())
                obj_mesh = self.apath(panel.get_editor_property("mesh"))
                obj_ovr = [self.apath(m) for m in panel.get_editor_property("material_overrides")]
                mesh = obj_mesh or text_mesh
                self.C.require(obj_mesh is None or text_mesh is None or obj_mesh == text_mesh, "MESH_PARSE_MISMATCH",
                               "%s|%s" % (obj_mesh, text_mesh))
                # positional list from the text; any loaded object must agree with it
                ovr = text_ovr if len(text_ovr) >= len(obj_ovr) else obj_ovr
                for i, o in enumerate(obj_ovr):
                    self.C.require(o is None or (i < len(ovr) and ovr[i] == o), "OVERRIDE_PARSE_MISMATCH",
                                   "%s|%s" % (obj_ovr, text_ovr))
                panels.append({"side": side, "mesh": mesh, "overrides": ovr})
            cues[self.guid(cue.get_editor_property("cue_guid"))] = {
                "label": str(cue.get_editor_property("label")), "enabled": bool(cue.get_editor_property("enabled")),
                "panels": panels}
        return {"passages": passages, "cues": cues}

    # ---- meshes
    def _sme(self):
        return self.u.get_editor_subsystem(self.u.StaticMeshEditorSubsystem)

    def screen_sizes(self, mesh):
        primary = [float(x) for x in self._sme().get_lod_screen_sizes(mesh)]   # StaticMeshEditorSubsystem.h:168
        try:      # phase1_import.py:613 [precedent, ran 1 Oct: read [2.0, 0.75]]
            alt = [float(x) for x in self.u.EditorStaticMeshLibrary.get_lod_screen_sizes(mesh)]
        except Exception:  # noqa: BLE001  -- the deprecated library may be absent; primary still read
            alt = None
        return primary, alt

    def lod_slots(self, mesh, lod):
        sme, out = self._sme(), []
        for section in range(64):                                             # phase1_import.py:340-347
            slot = int(sme.get_lod_material_slot(mesh, lod, section))
            if slot < 0:
                break
            out.append(slot)
        return out

    def mesh_info(self, path, full=True):
        m = self.load(path)
        if m is None:
            return {"exists": False}
        if not isinstance(m, self.u.StaticMesh):
            return {"exists": True, "is_static_mesh": False}
        info = {"exists": True, "is_static_mesh": True,
                "slots": [{"name": str(r.get_editor_property("material_slot_name")),
                           "material": self.apath(r.get_editor_property("material_interface"))}
                          for r in m.get_editor_property("static_materials")]}
        if not full:
            return info
        n = int(m.get_num_lods())
        primary, alt = self.screen_sizes(m)
        try:
            auto = bool(m.get_editor_property("auto_compute_lod_screen_size"))
        except Exception as exc:  # noqa: BLE001  -- UPROPERTY() without Edit flags (StaticMesh.h:720-722): may be hidden
            auto = "unreadable: %s" % type(exc).__name__
        info.update({"lod_count": n, "screen_sizes": primary, "screen_sizes_alt": alt, "auto_compute": auto,
                     "nanite": bool(m.get_editor_property("nanite_settings").get_editor_property("enabled")),
                     "lod_slots": {str(lod): self.lod_slots(m, lod) for lod in range(n)}})
        return info

    def mesh_state(self, path):
        m = self.load(path)
        sizes, alt = self.screen_sizes(m)
        return {"screen_sizes": sizes, "screen_sizes_alt": alt, "lod_count": int(m.get_num_lods()),
                "slots": [self.apath(r.get_editor_property("material_interface")) for r in m.get_editor_property("static_materials")],
                "nanite": bool(m.get_editor_property("nanite_settings").get_editor_property("enabled"))}

    def set_screen_sizes(self, path, sizes):
        m = self.load(path)
        m.modify()
        self._sme().set_lod_screen_sizes(m, [float(x) for x in sizes])    # return value not trusted: read back

    # ---- material instances
    def parent_chain(self, path):
        chain, seen = [], set()
        obj = self.load(path)
        while obj is not None and self.apath(obj) not in seen:
            p = self.apath(obj)
            chain.append(p)
            seen.add(p)
            try:
                obj = obj.get_editor_property("parent") if isinstance(obj, self.u.MaterialInstance) else None
            except Exception:  # noqa: BLE001
                obj = None
        return chain

    def scalar_overrides(self, mi):
        out = {}
        for v in mi.get_editor_property("scalar_parameter_values"):
            name = str(v.get_editor_property("parameter_info").get_editor_property("name"))
            out[name] = round(float(v.get_editor_property("parameter_value")), 6)
        return out

    def mi_fixed(self, mi):
        """Everything a flutter write must NOT change."""
        mel = self.u.MaterialEditingLibrary
        ov = self.scalar_overrides(mi)
        return {"parent": self.apath(mi.get_editor_property("parent")),
                "other_scalar_overrides": {k: v for k, v in ov.items() if k not in self.C.FLUTTER_NAMES},
                "vector_overrides": len(mi.get_editor_property("vector_parameter_values")),
                "texture_overrides": sorted([str(v.get_editor_property("parameter_info").get_editor_property("name")),
                                             self.apath(v.get_editor_property("parameter_value"))]
                                            for v in mi.get_editor_property("texture_parameter_values")),
                "static_switches": {str(n): bool(mel.get_material_instance_static_switch_parameter_value(mi, n))
                                    for n in mel.get_static_switch_parameter_names(mi)}}

    def mi_effective(self, mi):
        mel = self.u.MaterialEditingLibrary
        return {n: round(float(mel.get_material_instance_scalar_parameter_value(mi, n)), 6) for n in self.C.FLUTTER_NAMES}

    def mi_info(self, path):
        mi = self.load(path)
        if mi is None:
            return {"exists": False}
        if not isinstance(mi, self.u.MaterialInstanceConstant):
            return {"exists": True, "is_mic": False}
        mel = self.u.MaterialEditingLibrary
        names = sorted(str(n) for n in mel.get_scalar_parameter_names(mi))
        switch = None
        if self.C.FLUTTER_SWITCH in [str(n) for n in mel.get_static_switch_parameter_names(mi)]:
            switch = bool(mel.get_material_instance_static_switch_parameter_value(mi, self.C.FLUTTER_SWITCH))
        ov = self.scalar_overrides(mi)
        return {"exists": True, "is_mic": True, "parent_chain": self.parent_chain(path), "scalar_names": names,
                "effective": self.mi_effective(mi) if set(self.C.FLUTTER_NAMES) <= set(names) else {},
                "overrides": {n: ov.get(n) for n in self.C.FLUTTER_NAMES}, "flutter_switch": switch,
                "fixed": self.mi_fixed(mi)}

    def master_max_wpo(self, chain):
        try:
            root = self.load(chain[-1])
            return float(root.get_editor_property("max_world_position_offset_displacement"))
        except Exception as exc:  # noqa: BLE001  -- reported only
            return "unreadable: %s" % exc

    def set_mi_values(self, path, values):
        mel = self.u.MaterialEditingLibrary
        mi = self.load(path)
        mi.modify()
        for name, value in values.items():
            mel.set_material_instance_scalar_parameter_value(mi, name, float(value))   # return value not trusted
        mel.update_material_instance(mi)

    def restore_mi(self, path, orig_overrides, names):
        """Restore the override LIST for `names` only: originally-absent entries are removed, values restored
        (gloss4_wax_core.py:154-169 pattern); every other entry is kept untouched."""
        mel = self.u.MaterialEditingLibrary
        mi = self.load(path)
        mi.modify()
        live = list(mi.get_editor_property("scalar_parameter_values"))
        kept, present = [], set()
        for entry in live:
            name = str(entry.get_editor_property("parameter_info").get_editor_property("name"))
            if name in names:
                if orig_overrides.get(name) is None:
                    continue
                entry.set_editor_property("parameter_value", float(orig_overrides[name]))
                present.add(name)
            kept.append(entry)
        mi.set_editor_property("scalar_parameter_values", kept)
        for name in names:      # originally overridden but the entry vanished since: set it back
            if orig_overrides.get(name) is not None and name not in present:
                mel.set_material_instance_scalar_parameter_value(mi, name, float(orig_overrides[name]))
        mel.update_material_instance(mi)

    # ---- asset registry
    def _registry(self):
        return self.u.AssetRegistryHelpers.get_asset_registry()

    def referencers(self, package):            # velvet_v2g_apply.py:667-674 [precedent]
        opts = self.u.AssetRegistryDependencyOptions()
        for prop, val in (("include_hard_package_references", True), ("include_soft_package_references", True)):
            try:
                opts.set_editor_property(prop, val)
            except Exception:  # noqa: BLE001
                pass
        return [str(x) for x in (self._registry().get_referencers(package, opts) or [])]

    def package_class(self, package):
        out = [str(ad.asset_class_path.asset_name) for ad in (self._registry().get_assets_by_package_name(package) or [])]
        if not out:
            return ""
        return out[0] if len(set(out)) == 1 else ("World" if "World" in out else out[0])


# ===================================================================================================== flow
def resolve(ops, C, args):
    """Read-only: everything DRY reports and APPLY re-checks. Returns (plan, snapshot)."""
    show = ops.read_show()
    tgt_rows, excl_rows, other_rows = C.classify_panels(show, args)
    meshes = {}
    for path in sorted({r["mesh"] for r in tgt_rows}):
        meshes[path] = ops.mesh_info(path, full=True)
    for path in sorted({r["mesh"] for r in excl_rows + other_rows if r["mesh"]} - set(meshes)):
        meshes[path] = ops.mesh_info(path, full=False)        # slots only (sharing)
    # candidate Flap MIs (effective per target panel)
    cand = set()
    for r in tgt_rows:
        info = meshes.get(r["mesh"], {})
        if info.get("is_static_mesh"):
            fi = C.flap_index(info)
            if fi is not None:
                mat, _src = C.effective_slot_material(info, r["overrides"], fi)
                if mat:
                    cand.add(mat)
    mis = {p: ops.mi_info(p) for p in sorted(cand)}
    chains = {}
    for rows in (other_rows, excl_rows):
        for mat in C.materials_of_rows(rows, meshes):
            if mat not in chains:
                chains[mat] = ops.parent_chain(mat)
    # referencer closures (registry), benign = target meshes / candidate MIs
    tgt_meshes = {r["mesh"] for r in tgt_rows}
    allow = set(args["allow_referencers"])
    refs = {}
    for p in sorted(cand) + sorted(tgt_meshes):
        refs[p] = C.referencer_closure(p, ops.referencers, ops.package_class, int(args["referencer_depth"]),
                                       tgt_meshes, cand, allow)
    master = None
    for info in mis.values():
        if info.get("parent_chain"):
            master = ops.master_max_wpo(info["parent_chain"])
            break
    plan = C.build_plan(show, meshes, mis, chains, refs, args, master_wpo=master)
    plan["mi_fixed"] = {t["path"]: mis[t["path"]]["fixed"] for t in plan["mi_targets"]}
    return plan


def finish_batch(ops, C, paths, before):
    """Census guard (gained == exactly `paths`, maps unchanged), save only `paths`, census back to start."""
    mid = ops.census()
    gained = sorted(set(mid["content"]) - set(before["content"]))
    C.require(gained == sorted(paths), "CENSUS_GAINED_NOT_EXACTLY_TARGETS",
              json.dumps({"extra": sorted(set(gained) - set(paths)), "missing": sorted(set(paths) - set(gained))}))
    C.require(mid["maps"] == before["maps"], "MAP_CENSUS_CHANGED", json.dumps([before["maps"], mid["maps"]]))
    for p in paths:
        ops.save(p)
    after = ops.census()
    C.require(after == before, "CENSUS_AFTER_SAVE", json.dumps([before, after]))
    return {"gained": gained, "after_equals_start": True}


def check_mi(ops, C, path, values, fixed, stage, max_cm):
    mi = ops.load(path)
    eff = ops.mi_effective(mi)
    bad = {n: [eff.get(n), v] for n, v in values.items() if not C.close(eff.get(n), v)}
    C.require(not bad, "MI_VALUE_READBACK_" + stage, "%s|%s" % (path, json.dumps(bad)))
    C.require(C.close(eff.get("FlutterMaxCm"), max_cm), "MI_MAX_CM_CHANGED_" + stage, "%s|%s" % (path, eff.get("FlutterMaxCm")))
    ov = ops.scalar_overrides(mi)
    C.require(all(n in ov and C.close(ov[n], v) for n, v in values.items()), "MI_OVERRIDE_READBACK_" + stage,
              "%s|%s" % (path, json.dumps(ov)))
    now_fixed = ops.mi_fixed(mi)
    C.require(now_fixed == fixed, "MI_FIXED_STATE_CHANGED_" + stage, "%s|%s" % (path, json.dumps([fixed, now_fixed])[:500]))
    return eff


def check_mesh(ops, C, row, want, stage):
    st = ops.mesh_state(row["path"])
    C.require(C.sizes_equal(st["screen_sizes"], want), "LOD_READBACK_" + stage,
              "%s|want=%s|got=%s" % (row["path"], want, st["screen_sizes"]))
    if st["screen_sizes_alt"] is not None:
        C.require(C.sizes_equal(st["screen_sizes_alt"], want), "LOD_ALT_READBACK_" + stage,
                  "%s|%s" % (row["path"], st["screen_sizes_alt"]))
    C.require(st["lod_count"] == row["lod_count"], "LOD_COUNT_CHANGED_" + stage, row["path"])
    C.require(not st["nanite"], "NANITE_CHANGED_" + stage, row["path"])
    return st


def do_dry(ops, C, args, run):
    ops.editor_ready()
    before = ops.census()
    plan = resolve(ops, C, args)
    C.require(ops.census() == before, "DRY_DIRTIED", json.dumps([before, ops.census()]))
    plan.update({"run": run, "mode": "DRY", "census": before, "apply_confirm": C.confirm_for("APPLY", plan),
                 "taken": datetime.datetime.now().isoformat()})
    out = HERE / ("flutter_lod_dry_%s.json" % run)
    write_verified(C, out, plan)
    write_verified(C, PLAN, plan)
    ops.log("%s_DRY_OK|run=%s|mi_targets=%d|mi_refused=%d|mi_already=%d|mesh_targets=%d|mesh_refused=%d|"
            "mesh_shared_skipped=%d|mesh_already=%d|lod1=%s|confirm=%s|file=%s" % (
                C.MARK, run, len(plan["mi_targets"]), len(plan["mi_refused"]), len(plan["mi_already"]),
                len(plan["mesh_targets"]), len(plan["mesh_refused"]), len(plan["mesh_shared_skipped"]),
                len(plan["mesh_already"]), json.dumps(plan["lod1_histogram"], sort_keys=True), plan["apply_confirm"],
                out.as_posix()))
    return plan


def _rollback_batch(ops, C, kind, rows, values=None):
    """Best effort, IN MEMORY, nothing saved: put a failed batch back to its originals and read it back.
    The packages stay DIRTY either way: the operator restarts the editor choosing Don't Save for them
    (REVERT refuses dirty targets), so the on-disk state is the pre-batch state."""
    done, verified = [], True
    for row in rows:
        try:
            if kind == "mi":
                ops.restore_mi(row["path"], row["overrides"], list(values))
                ok = not C.override_state_matches(row["overrides"], ops.scalar_overrides(ops.load(row["path"])), list(values))
            else:
                ops.set_screen_sizes(row["path"], row["screen_sizes"])
                ok = C.sizes_equal(ops.mesh_state(row["path"])["screen_sizes"], row["screen_sizes"])
            verified = verified and ok
            done.append("%s:%s" % (row["path"].rsplit("/", 1)[-1], "ok" if ok else "MISMATCH"))
        except Exception as exc:  # noqa: BLE001  -- reported in the failure
            verified = False
            done.append("%s: ROLLBACK_FAILED %s" % (row["path"], exc))
    return {"verified": verified, "items": done,
            "operator": "unsaved and dirty: restart the editor choosing Don't Save for these packages, then REVERT "
                        "(earlier saved batches) or re-DRY"}


def do_apply(ops, C, args, run):
    ops.editor_ready()
    C.require(not ORIGINALS.exists(), "ORIGINALS_ACTIVE_EXISTS_REVERT_FIRST", ORIGINALS.as_posix())
    before = ops.census()
    plan = resolve(ops, C, args)
    want = C.confirm_for("APPLY", plan)
    C.require(str(args.get("confirm")) == want, "CONFIRM_MISMATCH", "expected '%s' (state since DRY?)" % want)
    C.require(plan["mi_targets"] or plan["mesh_targets"], "NOTHING_TO_DO")
    paths = [t["path"] for t in plan["mi_targets"]] + [t["path"] for t in plan["mesh_targets"]]
    dirty = sorted(set(before["content"]) & set(paths))
    C.require(not dirty, "TARGET_DIRTY_AT_START", json.dumps(dirty))
    C.require(ops.census() == before, "RESOLVE_DIRTIED")
    originals = {"run": run, "taken": datetime.datetime.now().isoformat(), "decided_by": args["decided_by"],
                 "values": plan["values"], "lod1_screen_size": plan["lod1_screen_size"], "token": plan["token"],
                 "census_at_capture": before, "mi": plan["mi_targets"], "mi_fixed": plan["mi_fixed"],
                 "mesh": plan["mesh_targets"], "progress": []}
    write_verified(C, ORIGINALS, originals)
    write_verified(C, HERE / ("flutter_lod_originals_%s.json" % run), originals)
    ops.log("%s_ORIGINALS_WRITTEN|run=%s|mi=%d|mesh=%d|file=%s" % (C.MARK, run, len(plan["mi_targets"]),
                                                                    len(plan["mesh_targets"]), ORIGINALS.as_posix()))
    values = plan["values"]
    record = {"run": run, "mode": "APPLY", "batches": []}
    # ---- MIs (one batch)
    mi_rows = plan["mi_targets"]
    if mi_rows:
        try:
            for row in mi_rows:
                ops.set_mi_values(row["path"], values)
                check_mi(ops, C, row["path"], values, plan["mi_fixed"][row["path"]], "SET", row["effective"]["FlutterMaxCm"])
            guard = finish_batch(ops, C, [r["path"] for r in mi_rows], before)
        except Exception as exc:
            rb = _rollback_batch(ops, C, "mi", mi_rows, values)
            raise C.PlanError("MI_BATCH_FAILED_NOTHING_SAVED|%s|rollback=%s" % (exc, json.dumps(rb)[:600]))
        for row in mi_rows:
            check_mi(ops, C, row["path"], values, plan["mi_fixed"][row["path"]], "SAVED", row["effective"]["FlutterMaxCm"])
        record["batches"].append({"kind": "mi", "paths": [r["path"] for r in mi_rows], "guard": guard})
        originals["progress"].append({"kind": "mi", "saved": [r["path"] for r in mi_rows]})
        write_verified(C, ORIGINALS, originals)
    # ---- meshes (batched)
    for i, batch in enumerate(C.batches(plan["mesh_targets"], args["mesh_batch_size"])):
        try:
            for row in batch:
                ops.set_screen_sizes(row["path"], row["new_sizes"])
                check_mesh(ops, C, row, row["new_sizes"], "SET")
            guard = finish_batch(ops, C, [r["path"] for r in batch], before)
        except Exception as exc:
            rb = _rollback_batch(ops, C, "mesh", batch)
            raise C.PlanError("MESH_BATCH_%d_FAILED_UNSAVED (earlier batches SAVED: REVERT after a Don't-Save restart)|%s|"
                              "rollback=%s" % (i, exc, json.dumps(rb)[:600]))
        for row in batch:
            check_mesh(ops, C, row, row["new_sizes"], "SAVED")
        record["batches"].append({"kind": "mesh", "index": i, "paths": [r["path"] for r in batch], "guard": guard})
        originals["progress"].append({"kind": "mesh", "index": i, "saved": [r["path"] for r in batch]})
        write_verified(C, ORIGINALS, originals)
        ops.log("%s_APPLY_BATCH|run=%s|batch=%d|meshes=%d" % (C.MARK, run, i, len(batch)))
        ops.gc()
    C.require(ops.census() == before, "CENSUS_END", json.dumps([before, ops.census()]))
    record.update({"status": "PASS", "census_before": before, "census_after": ops.census(),
                   "originals": ORIGINALS.as_posix(), "mi": len(mi_rows), "mesh": len(plan["mesh_targets"])})
    out = HERE / ("flutter_lod_apply_%s.json" % run)
    write_verified(C, out, record)
    ops.log("%s_APPLY_OK|run=%s|mi=%d|mesh=%d|census_unchanged=1|file=%s" % (
        C.MARK, run, len(mi_rows), len(plan["mesh_targets"]), out.as_posix()))
    return record


def do_revert(ops, C, args, run):
    ops.editor_ready()
    C.require(ORIGINALS.exists(), "NO_ACTIVE_ORIGINALS", ORIGINALS.as_posix())
    orig = json.loads(ORIGINALS.read_text(encoding="utf-8"))
    want = C.confirm_for("REVERT", originals=orig)
    C.require(str(args.get("confirm")) == want, "CONFIRM_MISMATCH", "expected '%s'" % want)
    values = orig["values"]
    before = ops.census()
    paths = [r["path"] for r in orig["mi"]] + [r["path"] for r in orig["mesh"]]
    dirty = sorted(set(before["content"]) & set(paths))
    C.require(not dirty, "TARGET_DIRTY_AT_START", json.dumps(dirty))
    # decide everything BEFORE writing anything (drift refuses the whole revert)
    mi_do, mesh_do, skipped = [], [], []
    for row in orig["mi"]:
        act = C.mi_revert_action(row, ops.mi_effective(ops.load(row["path"])), values)
        (mi_do if act == "restore" else skipped).append(row)
    for row in orig["mesh"]:
        act = C.mesh_revert_action(row, ops.mesh_state(row["path"])["screen_sizes"])
        (mesh_do if act == "restore" else skipped).append(row)
    record = {"run": run, "mode": "REVERT", "apply_run": orig["run"], "skipped_already_original": [r["path"] for r in skipped],
              "batches": []}
    names = list(values)
    if mi_do:
        for row in mi_do:
            ops.restore_mi(row["path"], row["overrides"], names)
            mi = ops.load(row["path"])
            bad = C.override_state_matches(row["overrides"], ops.scalar_overrides(mi), names)
            C.require(not bad, "REVERT_OVERRIDE_READBACK", "%s|%s" % (row["path"], json.dumps(bad)))
            eff = ops.mi_effective(mi)
            C.require(all(C.close(eff[n], row["effective"][n]) for n in C.FLUTTER_NAMES), "REVERT_EFFECTIVE_READBACK",
                      "%s|%s|%s" % (row["path"], eff, row["effective"]))
            C.require(ops.mi_fixed(mi) == orig["mi_fixed"][row["path"]], "REVERT_FIXED_STATE_CHANGED", row["path"])
        record["batches"].append({"kind": "mi", "paths": [r["path"] for r in mi_do],
                                  "guard": finish_batch(ops, C, [r["path"] for r in mi_do], before)})
        for row in mi_do:
            eff = ops.mi_effective(ops.load(row["path"]))
            C.require(all(C.close(eff[n], row["effective"][n]) for n in C.FLUTTER_NAMES), "REVERT_SAVED_READBACK", row["path"])
    for i, batch in enumerate(C.batches(mesh_do, orig.get("mesh_batch_size", args["mesh_batch_size"]))):
        for row in batch:
            ops.set_screen_sizes(row["path"], row["screen_sizes"])
            check_mesh(ops, C, row, row["screen_sizes"], "REVERT")
        record["batches"].append({"kind": "mesh", "index": i, "paths": [r["path"] for r in batch],
                                  "guard": finish_batch(ops, C, [r["path"] for r in batch], before)})
        for row in batch:
            check_mesh(ops, C, row, row["screen_sizes"], "REVERT_SAVED")
        ops.gc()
    archived = HERE / ("flutter_lod_originals_reverted_%s.json" % run)
    ORIGINALS.rename(archived)
    record.update({"status": "PASS", "census_before": before, "census_after": ops.census(),
                   "originals_archived": archived.as_posix()})
    out = HERE / ("flutter_lod_revert_%s.json" % run)
    write_verified(C, out, record)
    ops.log("%s_REVERT_OK|run=%s|mi=%d|mesh=%d|skipped=%d|census_unchanged=1|file=%s" % (
        C.MARK, run, len(mi_do), len(mesh_do), len(skipped), out.as_posix()))
    return record


def main(u=None, here=None, args_path=None):
    u = u or unreal
    C = load_core(here)
    mode, run = "UNKNOWN", None
    try:
        raw = json.loads(pathlib.Path(args_path or ARGS).read_text(encoding="utf-8"))
        args = C.merged_args(raw)
        mode = C.validate_args(args)
        run = args.get("run_id") or "FLUTTERLOD-%s-%s" % (mode, datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
        if mode == "DRY":
            C.require(str(args.get("confirm")) == C.confirm_for("DRY"), "CONFIRM_MISMATCH", "expected 'DRY FLUTTERLOD'")
        ops = Ops(u, C)
        ops.log("%s_START|run=%s|mode=%s" % (C.MARK, run, mode))
        return {"DRY": do_dry, "APPLY": do_apply, "REVERT": do_revert}[mode](ops, C, args, run)
    except Exception as exc:
        run = run or "FLUTTERLOD-%s-%s" % (mode, datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
        try:
            write_verified(C, HERE / ("flutter_lod_%s_%s_FAILURE.json" % (mode.lower(), run)),
                           {"status": "FAIL", "run": run, "mode": mode, "error": str(exc), "trace": traceback.format_exc()})
        except Exception:  # noqa: BLE001
            pass
        u.log_error("%s_FAILED|run=%s|mode=%s|reason=%s" % (C.MARK, run, mode, re.sub(r"\s+", " ", str(exc))[:400]))
        raise


if unreal is not None and not globals().get("FLUTTERLOD_IMPORT_ONLY"):
    main()
