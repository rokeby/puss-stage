"""RZSWAP -- DRY / APPLY / REVERT for P02 / P03 realism mesh swaps (7 Oct, offline-written, NEVER RUN IN UNREAL BY ITS
AUTHOR).  Pure decisions live in rzswap_core.py; the plan is made OFFLINE by make_swap_plan.py from a DRY.

Run ONLY through rzswap_run.py (purges cached Saved modules, then runs this file) with rzswap_args.json:
  DRY     {"mode": "DRY", "passage": "P02", "confirm": "DRY RZSWAP P02", "manifests": [<IMPORT_MANIFEST_v2_*.json>]}
          read-only, CLEAN census.  Measures every row of the passage (label, cue guid, enabled, mechanism kind /
          playback, Master pins, attachments, per side: panel, mesh, live box -> height / thickness, inner/outer local
          bounds via common.side_bounds, world inner edge), the passage settings (first/last cue, lead-in, tick ->
          pass times), and every realism candidate mesh of that passage (exists, live zero bounds).
          -> rzswap_dry_<P>_<run>.json + rzswap_dry_<P>_LATEST.json.  FLATV3_RZSWAP_DRY_OK|run=..|passage=..|state=..
  (offline) python make_swap_plan.py P02  -> rzswap_plan_P02.json + rzswap_sheet_P02.png (Gary reviews) + confirm
  APPLY   {"mode": "APPLY", "passage": "P02", "confirm": "APPLY RZSWAP P02 #<hash8>", "decided_by": "Gary ..."}
          Show + level write.  FLATV3_RZSWAP_APPLY_OK|run=..|passage=..|swaps=..
  REVERT  {"mode": "REVERT", "passage": "P02", "confirm": "REVERT RZSWAP P02 <apply run id>"}
          restores ONLY the written panels from the originals; compares ONLY the written fields.
          FLATV3_RZSWAP_REVERT_OK|run=..|passage=..
Markers: FLATV3_RZSWAP_<MODE>_OK|run=<id>|passage=<P> / FLATV3_RZSWAP_STOPPED|run=<id>|passage=<P>|reason=..

APPLY order (relayout_apply.run_apply [prec, ran P06RL-20261007-081048], minus every timing / order / settings write):
  guards (no PIE, expected world, census CLEAN, no ZZ_/TEMP actors, no ACTIVE originals for the passage) -> live
  re-measure: state hash == the plan's DRY state hash (else PLAN_STALE) -> every new mesh live -> placements
  recomputed live == plan (0.01 cm) -> world edges BEFORE -> Backups/PreRZSwap<P>-YYYYMMDD-HHMM (Show .uasset + level
  .umap, sha256-verified) -> originals file (every target side's panel + every cue text, fsynced) + ACTIVE pointer ->
  ONE cues write (only target Left/Right panels via common.set_panel) -> read-back: every written field == plan, every
  non-target cue byte-identical, target cues identical outside the target panels, target panels identical outside the
  written fields, all passage-settings texts identical, compiled segments identical -> materialize THAT passage only
  -> materialized count unchanged -> world-edge probe (swapped <= 1 cm, controls <= 0.05 cm, prediction 0) -> dirty set
  within {Show, level} -> save Show, save level -> census clean -> re-read texts == after -> record -> marker.
  Any failure before the save: the pristine cue array is set back in memory, the passage re-materialized, STOP, nothing
  saved (relaunch with Don't Save if the restore did not read back exact).  Never reloads the level, never Save All.
REVERT: guards -> ACTIVE originals + APPLY record -> drift check on the WRITTEN FIELDS ONLY (live target panels ==
  APPLY's written panels; another stream may have edited lights on these cues -- whole-cue compares are never used)
  -> Backups/PreRZSwapRevert<P>-stamp -> set the original panels back (common.set_panel) -> read-back: target panels ==
  originals (written fields, 0.001 tol), everything else byte-identical to its PRE-REVERT text (in-script) ->
  materialize -> world-edge probe (reverted sides back on their original inner edge within 1 cm; others 0.05) ->
  save Show + level -> census clean -> originals renamed _reverted, ACTIVE removed -> marker.
No unreal objects in module globals; never ends PIE; no Sequencer helpers (Master pins by plain property reads).
"""
import datetime
import hashlib
import importlib.util
import json
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:   # offline harness
    unreal = None

ARGS_NAME = "rzswap_args.json"


def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                            "CodexFlatV3", "rzswap")
    return os.path.dirname(os.path.abspath(__file__))


def _load(name, path):
    """By path, private name, not registered in sys.modules: never stale (memory ue58-python-stale-module-cache)."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_json(path, doc, fsync=False):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, default=str)
        fh.flush()
        if fsync:
            os.fsync(fh.fileno())
    os.replace(tmp, path)
    return path


def _read_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def active_name(P):
    return "rzswap_originals_%s_ACTIVE.json" % P


def candidate_meshes(project, manifests, P, rzc):
    """Realism wing meshes intended for passage P, named exactly as rzimport creates them (rzimport_core.MESH_FOLDERS
    + asset -- the single source of truth)."""
    out = {}
    for rel in manifests:
        m = _read_json(os.path.join(project, rel))
        if not m:
            raise RuntimeError("MANIFEST_MISSING %s" % rel)
        for e in m.get("meshes", []):
            if e.get("intended_passage") != P or (e.get("mount") or "wing") != "wing":
                continue
            asset = str(e["asset"])
            variant = asset.rsplit("_", 1)[-1]
            if variant in rzc.MESH_FOLDERS:
                out["%s/%s" % (rzc.MESH_FOLDERS[variant], asset)] = asset[len("SM_FlatV3_"):-len("_" + variant)]
    return out


# =====================================================================================================================
# Unreal access (the harness replaces this class)
# =====================================================================================================================

class UnrealOps:
    def __init__(self, core, tc, here):
        self.core, self.tc, self.here = core, tc, here
        self._common = None
        self._pristine = None

    def log(self, msg):
        unreal.log(msg)

    def log_error(self, msg):
        unreal.log_error(msg)

    def project_dir(self):
        return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())

    def _world(self):
        return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()

    def guard_context(self):
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        if editor.get_game_world() is not None:
            raise self.core.PlanError("PIE_OR_SIE_ACTIVE (refused; this tool never ends PIE)")
        world = editor.get_editor_world()
        name = str(world.get_outermost().get_name()) if world else None
        if name != self.core.WORLD_PATH:
            raise self.core.PlanError("WRONG_WORLD %s" % name)

    def census(self):
        lib = unreal.EditorLoadingAndSavingUtils
        pk = lambda p: str(p.get_path_name()).split(".")[0]  # noqa: E731
        return {"content": sorted(pk(p) for p in lib.get_dirty_content_packages()),
                "maps": sorted(pk(p) for p in lib.get_dirty_map_packages())}

    def zz_actors(self):
        actors = unreal.GameplayStatics.get_all_actors_of_class(self._world(), unreal.Actor)
        return sorted(str(a.get_actor_label()) for a in actors
                      if str(a.get_actor_label()).upper().startswith(("ZZ_", "TEMP")))

    def _guid(self, g):
        return str(unreal.GuidLibrary.conv_guid_to_string(g)).upper()

    def _show(self):
        show = unreal.EditorAssetLibrary.load_asset(self.core.SHOW_PATH)
        if show is None:
            raise self.core.PlanError("SHOW_LOAD_FAIL")
        return show

    def _swapkit(self):
        if self._common is None:   # swapkit/common.py by path [prec: relayout_apply.py:171-175, ran 7 Oct]
            self._common = _load("swapkit_common_rzswap", os.path.normpath(os.path.join(self.here, "..", "swapkit", "common.py")))
        return self._common

    def _actor(self, P):
        guid = self.core.PASSAGES[P]["guid"]
        hits = [a for a in unreal.GameplayStatics.get_all_actors_of_class(self._world(), unreal.InfinityStagePassageActor)
                if self._guid(a.get_editor_property("passage_guid")) == guid]
        if len(hits) != 1:
            raise self.core.PlanError("PASSAGE_ACTOR_COUNT %s %d" % (P, len(hits)))
        if not str(hits[0].get_actor_label()).startswith(self.core.PASSAGES[P]["actor_prefix"]):
            raise self.core.PlanError("PASSAGE_ACTOR_LABEL %s %r" % (P, str(hits[0].get_actor_label())))
        return hits[0]

    def _settings(self, show, P):
        guid = self.core.PASSAGES[P]["guid"]
        settings = list(show.get_editor_property("passage_settings"))
        idx = [i for i, s in enumerate(settings) if self._guid(s.get_editor_property("passage_guid")) == guid]
        if len(idx) != 1:
            raise self.core.PlanError("PASSAGE_SETTINGS_COUNT %s %d" % (P, len(idx)))
        return settings[idx[0]]

    def _mesh_path(self, mesh):
        return None if mesh is None else str(mesh.get_path_name()).split(".")[0]

    def _library_by_mesh(self, show):
        common = self._swapkit()
        lib_ref = show.get_editor_property("wing_library")
        lib = unreal.EditorAssetLibrary.load_asset(common.asset_path(lib_ref)) if lib_ref else None
        if lib is None:
            raise self.core.PlanError("WING_LIBRARY_LOAD_FAIL")
        out = {}
        for e in lib.get_editor_property("entries"):
            m = common.asset_path(e.get_editor_property("mesh"))
            if m:
                out[m] = e
        return out

    def _box(self, path):
        mesh = unreal.EditorAssetLibrary.load_asset(path) if path else None
        if not isinstance(mesh, unreal.StaticMesh):
            return None
        b = mesh.get_bounding_box()
        return {"min": [float(b.min.x), float(b.min.y), float(b.min.z)], "max": [float(b.max.x), float(b.max.y), float(b.max.z)]}

    # ---- reads
    def cue_texts(self):
        return [c.export_text() for c in self._show().get_editor_property("cues")]

    def settings_texts(self):
        return [s.export_text() for s in self._show().get_editor_property("passage_settings")]

    def segments(self):
        """Compiled segments [prec relayout_apply.py:241-250, ran 7 Oct]."""
        transport = unreal.new_object(unreal.InfinityStageTransportController)
        if not bool(transport.build_segments(self._show())):
            raise self.core.PlanError("BUILD_SEGMENTS_FAIL")
        out = []
        for s in list(transport.get_editor_property("segments")):
            sf, ef = s.get_editor_property("start_frame"), s.get_editor_property("end_frame")
            out.append([str(s.get_editor_property("label")), int(getattr(sf, "value", sf)), int(getattr(ef, "value", ef))])
        return out

    def master_pins(self, P):
        """Plain property reads only (memory puss-mcp-python-crashes-the-editor #5) [prec relayout_apply.py:289-298]."""
        guid = self.core.PASSAGES[P]["guid"]
        master = unreal.EditorAssetLibrary.load_asset(self.core.MASTER_PATH)
        secs = [x for t in master.get_tracks() if "InfinityPassage" in t.get_class().get_name()
                for x in t.get_sections() if self._guid(x.get_editor_property("passage_guid")) == guid]
        if len(secs) != 1:
            raise self.core.PlanError("PASSAGE_SECTION_COUNT %s %d" % (P, len(secs)))
        return [self._guid(g) for g in secs[0].get_editor_property("pinned_wing_cue_guids")]

    def world_edges(self, P, guids=None):
        """Route-relative lateral inner edge of every materialized L/R panel (world, Unreal frame) -- the topple /
        relayout corner method [prec relayout_apply.py:305-336, ran 7 Oct]."""
        actor = self._actor(P)
        spline = actor.get_editor_property("route")
        space = unreal.SplineCoordinateSpace.WORLD
        out = {}
        for ref in actor.get_editor_property("materialized_panels"):
            g = self._guid(ref.get_editor_property("cue_guid"))
            s = str(ref.get_editor_property("side")).upper()
            side = "L" if "LEFT" in s else "R" if "RIGHT" in s else None
            if side is None or (guids is not None and g not in guids):
                continue
            base = ref.get_editor_property("base_world_transform")
            mesh = ref.get_editor_property("component").get_editor_property("static_mesh")
            box = mesh.get_bounding_box()
            lat = []
            for x in (box.min.x, box.max.x):
                for y in (box.min.y, box.max.y):
                    p = base.transform_location(unreal.Vector(x, y, box.min.z))
                    d = float(spline.get_distance_along_spline_at_location(p, space))
                    o = spline.get_location_at_distance_along_spline(d, space)
                    rv = spline.get_right_vector_at_distance_along_spline(d, space)
                    lat.append((p.x - o.x) * rv.x + (p.y - o.y) * rv.y + (p.z - o.z) * rv.z)
            key = "%s|%s" % (g, side)
            if key in out:
                out[key]["error"] = "DUPLICATE_REF"
                continue
            out[key] = {"inner_cm": max(lat) if side == "L" else min(lat), "mesh": self._mesh_path(mesh)}
        return out

    def materialized_count(self, P):
        return int(self._actor(P).get_editor_property("materialized_wing_pair_count"))

    def measure(self, P, cand_meshes):
        """Everything the plan depends on, as plain data.  Read-only."""
        core, tc, common = self.core, self.tc, self._swapkit()
        show = self._show()
        st = self._settings(show, P)
        tr = show.get_editor_property("tick_resolution")
        tick = float(tr.numerator) / float(tr.denominator)
        guids = [self._guid(g) for g in show.get_wing_pair_cue_guids_in_passage(st.get_editor_property("passage_guid"))]
        cues = list(show.get_editor_property("cues"))
        index = {self._guid(c.get_editor_property("cue_guid")): i for i, c in enumerate(cues)}
        by_mesh = self._library_by_mesh(show)
        pins = set(self.master_pins(P))
        edges = self.world_edges(P, set(guids))
        lead = int(st.get_editor_property("lead_in_frames").value)
        frame = lead
        rows = []
        for o, g in enumerate(guids):
            if g not in index:
                raise core.PlanError("CUE_UNRESOLVED %s" % g)
            cue = cues[index[g]]
            pair = cue.get_editor_property("wing_pair")
            mech = pair.get_editor_property("mechanism")
            atts = []
            for a in pair.get_editor_property("attachments"):
                atts.append({"label": str(a.get_editor_property("label")), "kind": str(a.get_editor_property("kind")),
                             "text": a.export_text()})
            text = cue.export_text()
            row = {"ordinal": o, "cue_guid": g, "label": str(cue.get_editor_property("label")), "show_index": index[g],
                   "enabled": bool(cue.get_editor_property("enabled")), "has_top": bool(pair.get_editor_property("has_top")),
                   "interval_ticks": int(pair.get_editor_property("interval_to_next").value),
                   "gap_cm": float(pair.get_editor_property("gap_to_next_cm")),
                   "pass_frame_rel": frame, "pass_s": frame / tick,
                   "mechanism": {"kind": str(mech.get_editor_property("kind")),
                                 "playback_mode": str(mech.get_editor_property("playback_mode"))},
                   "local_override_mask": int(pair.get_editor_property("local_override_mask")),
                   "master_pinned": g in pins,
                   "attachments": [{"label": a["label"], "kind": a["kind"]} for a in atts],
                   "text_sha": _sha(text), "panel_text_fields": {}, "sides": {}}
            frame += row["interval_ticks"]
            for s in ("L", "R"):
                panel = pair.get_editor_property(core.SIDE_PROP[s])
                plain = common.panel_plain(panel)
                box = self._box(plain["mesh"])
                try:
                    ob = common.side_bounds(plain, by_mesh)
                    old_bounds = {"min_y_cm": ob["min_y_cm"], "max_y_cm": ob["max_y_cm"], "facing": ob["facing"]}
                except Exception as exc:  # noqa: BLE001 -- recorded; the side is then not a candidate
                    old_bounds = None
                    plain["_bounds_error"] = str(exc)[:200]
                mesh = plain["mesh"]
                row["sides"][s] = {
                    "panel": {k: plain[k] for k in ("mesh", "material_overrides", "local_transform", "facing_policy",
                                                    "flip_image_horizontally")},
                    "box_cm": box,
                    "height_cm": box["max"][2] if box else None,
                    "thickness_cm": (box["max"][0] - box["min"][0]) if box else None,
                    "width_cm": (box["max"][1] - box["min"][1]) if box else None,
                    "old_bounds": old_bounds,
                    "attachment_refs_mesh": bool(mesh) and any(mesh in a["text"] for a in atts),
                    "edge_baseline": edges.get("%s|%s" % (g, s)),
                    "bounds_error": plain.get("_bounds_error")}
                row["panel_text_fields"][s] = [k for k, _ in tc.fields(tc.get_field(tc.get_field(text, "WingPair"),
                                                                                    core.SIDE_FIELD[s]))]
            rows.append(row)
        cands = {}
        for m, owner in sorted(cand_meshes.items()):
            ok = bool(unreal.EditorAssetLibrary.does_asset_exist(m)) and \
                isinstance(unreal.EditorAssetLibrary.load_asset(m), unreal.StaticMesh)
            zb = None
            if ok:
                z = common.side_bounds(core.planned_panel(m, 0.0), by_mesh)
                zb = {"min_y_cm": z["min_y_cm"], "max_y_cm": z["max_y_cm"], "facing": z["facing"]}
            cands[m] = {"owner": owner, "exists": ok, "zero_bounds": zb, "box_cm": self._box(m) if ok else None}
        settings = {"label": str(st.get_editor_property("label")), "lead_in_frames": lead,
                    "lead_in_distance_cm": float(st.get_editor_property("lead_in_distance_cm")),
                    "tail_frames": int(st.get_editor_property("tail_frames").value),
                    "tail_distance_cm": float(st.get_editor_property("tail_distance_cm")),
                    "first_cue_guid": self._guid(st.get_editor_property("first_cue_guid")),
                    "last_cue_guid": self._guid(st.get_editor_property("last_cue_guid"))}
        return {"passage": P, "passage_guid": core.PASSAGES[P]["guid"], "actor_label": str(self._actor(P).get_actor_label()),
                "tick": tick, "settings": settings, "rows": rows, "candidates": cands,
                "materialized_count": self.materialized_count(P), "edges": edges}

    def placements(self, P, swaps):
        """Planned panel per swap recomputed LIVE (relayout_apply.placements [prec, ran])."""
        common, core = self._swapkit(), self.core
        show = self._show()
        by_mesh = self._library_by_mesh(show)
        cues = list(show.get_editor_property("cues"))
        index = {self._guid(c.get_editor_property("cue_guid")): i for i, c in enumerate(cues)}
        out = {}
        for s in swaps:
            pair = cues[index[s["cue_guid"]]].get_editor_property("wing_pair")
            old = common.side_bounds(common.panel_plain(pair.get_editor_property(core.SIDE_PROP[s["side"]])), by_mesh)
            zero = common.side_bounds(core.planned_panel(s["new_mesh"], 0.0), by_mesh)
            y = core.inner_edge_y(s["side"], old, zero)
            planned = core.planned_panel(s["new_mesh"], y)
            new = common.side_bounds(planned, by_mesh)
            k = "max_y_cm" if s["side"] == "L" else "min_y_cm"
            if abs(new[k] - old[k]) > core.PLACE_TOL_CM:
                raise core.PlanError("INNER_EDGE_PLAN_FAIL %s %.3f %.3f" % (s["key"], old[k], new[k]))
            out[s["key"]] = planned
        return out

    def live_panels(self, keys):
        common, core = self._swapkit(), self.core
        cues = list(self._show().get_editor_property("cues"))
        index = {self._guid(c.get_editor_property("cue_guid")): i for i, c in enumerate(cues)}
        out = {}
        for k in keys:
            g, s = k.split("|")
            if g not in index:
                continue
            pair = cues[index[g]].get_editor_property("wing_pair")
            out[k] = common.panel_plain(pair.get_editor_property(core.SIDE_PROP[s]))
        return out

    def asset_is_mesh(self, path):
        return bool(unreal.EditorAssetLibrary.does_asset_exist(path)) and \
            isinstance(unreal.EditorAssetLibrary.load_asset(path), unreal.StaticMesh)

    # ---- writes
    def write_panels(self, panels_by_key):
        """The one Show write: only the target Left/Right panels, set via common.set_panel, the whole array set once
        (relayout_apply.write_layout pattern [prec, ran]).  A pristine copy of the array is kept for rollback."""
        common, core = self._swapkit(), self.core
        show = self._show()
        self._pristine = list(show.get_editor_property("cues"))
        work = list(show.get_editor_property("cues"))
        index = {self._guid(c.get_editor_property("cue_guid")): i for i, c in enumerate(work)}
        for k, rec in sorted(panels_by_key.items()):
            g, s = k.split("|")
            cue = work[index[g]]
            pair = cue.get_editor_property("wing_pair")
            panel = pair.get_editor_property(core.SIDE_PROP[s])
            common.set_panel(panel, rec)
            pair.set_editor_property(core.SIDE_PROP[s], panel)
            cue.set_editor_property("wing_pair", pair)
        if len(work) != len(self._pristine):
            raise core.PlanError("CUE_COUNT_WOULD_CHANGE")
        show.modify()
        show.set_editor_property("cues", work)

    def restore_pristine(self):
        if self._pristine is None:
            return False
        show = self._show()
        show.modify()
        show.set_editor_property("cues", self._pristine)
        return True

    def materialize(self, P):
        return bool(self._actor(P).materialize_passage())

    def backup(self, name):
        project = self.project_dir()
        dest = os.path.join(project, "Backups", name)
        if os.path.exists(dest):
            raise self.core.PlanError("BACKUP_DIR_EXISTS %s" % dest)
        os.makedirs(dest)
        out = []
        for rel in (self.core.SHOW_FILE_REL, self.core.UMAP_FILE_REL):
            src = os.path.join(project, *rel.split("/"))
            dst = os.path.join(dest, os.path.basename(src))
            shutil.copy2(src, dst)
            with open(src, "rb") as a, open(dst, "rb") as b:
                if hashlib.sha256(a.read()).digest() != hashlib.sha256(b.read()).digest():
                    raise self.core.PlanError("BACKUP_HASH_MISMATCH %s" % rel)
            out.append(dst)
        return dest, out

    def save_show(self):
        return bool(unreal.EditorAssetLibrary.save_asset(self.core.SHOW_PATH, only_if_is_dirty=False))

    def save_level(self):
        return bool(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level())


# =====================================================================================================================
# Orchestration (pure Python over an ops object; the harness drives these with a fake)
# =====================================================================================================================

CLEAN = {"content": [], "maps": []}


def _stop(ops, core, run, P, reason):
    ops.log_error("%s_STOPPED|run=%s|passage=%s|reason=%s" % (core.MARK, run, P, str(reason)[:700]))
    raise core.PlanError(reason)


def _guard_start(ops, core, run, P):
    try:
        ops.guard_context()
    except core.PlanError as exc:
        _stop(ops, core, run, P, str(exc))
    c = ops.census()
    if c != CLEAN:
        _stop(ops, core, run, P, "DIRTY_CENSUS (another stream's unsaved work? refused) %s" % json.dumps(c))
    if ops.zz_actors():
        _stop(ops, core, run, P, "ZZ_OR_TEMP_ACTORS_IN_LEVEL %s" % ops.zz_actors())


def dry_refusals(core, meas):
    ref = []
    if not meas["rows"]:
        ref.append("NO_ROWS")
    for r in meas["rows"]:
        for s in ("L", "R"):
            if "Mesh" not in r["panel_text_fields"].get(s, []):
                ref.append("PANEL_TEXT_HAS_NO_Mesh_FIELD %s %s %s (the read-back blanking would be blind)" % (
                    r["label"], s, r["panel_text_fields"].get(s)))
                break
    if meas["settings"]["first_cue_guid"] != (meas["rows"][0]["cue_guid"] if meas["rows"] else None):
        ref.append("FIRST_CUE_GUID_IS_NOT_THE_FIRST_ROW")
    if meas["settings"]["last_cue_guid"] != (meas["rows"][-1]["cue_guid"] if meas["rows"] else None):
        ref.append("LAST_CUE_GUID_IS_NOT_THE_LAST_ROW")
    return ref


def run_dry(ops, core, args, run, here, cand_meshes):
    P = args["passage"]
    _guard_start(ops, core, run, P)
    meas = ops.measure(P, cand_meshes)
    refusals = dry_refusals(core, meas)
    seg = ops.segments()
    end = ops.census()
    if end != CLEAN:
        _stop(ops, core, run, P, "DRY_DIRTIED_SOMETHING %s (do not save; report)" % json.dumps(end))
    doc = dict(meas, run_id=run, mode="DRY", status="PASS" if not refusals else "REFUSED", refusals=refusals,
               segments=seg, manifests=args.get("manifests"), made=datetime.datetime.now().isoformat(timespec="seconds"))
    doc["state_hash"] = core.state_hash(doc)
    _write_json(os.path.join(here, "rzswap_dry_%s_%s.json" % (P, run)), doc)
    _write_json(os.path.join(here, "rzswap_dry_%s_LATEST.json" % P), doc)
    live = sum(1 for c in meas["candidates"].values() if c["exists"])
    if refusals:
        _stop(ops, core, run, P, "DRY_REFUSED %s" % refusals[:4])
    ops.log("%s_DRY_OK|run=%s|passage=%s|rows=%d|candidates_live=%d/%d|state=%s|next=python make_swap_plan.py %s" % (
        core.MARK, run, P, len(meas["rows"]), live, len(meas["candidates"]), doc["state_hash"][:8], P))
    return doc


def _targets(plan, texts_index):
    out = {}
    for s in plan["swaps"]:
        out.setdefault(texts_index[s["cue_guid"]], []).append(s["side"])
    return out


def run_apply(ops, core, tc, args, plan, run, here):
    P = args["passage"]
    _guard_start(ops, core, run, P)
    if os.path.exists(os.path.join(here, active_name(P))):
        _stop(ops, core, run, P, "UNREVERTED_APPLY_EXISTS %s (REVERT it first)" % _read_json(os.path.join(here, active_name(P))))
    cand = {s["new_mesh"]: s["new_owner"] for s in plan["swaps"]}
    meas = ops.measure(P, cand)
    dry = _read_json(os.path.join(here, "rzswap_dry_%s_%s.json" % (P, plan["dry_run_id"])))
    if not dry:
        _stop(ops, core, run, P, "DRY_RECORD_MISSING %s" % plan["dry_run_id"])
    live_doc = dict(meas, candidates={m: dry["candidates"][m] for m in dry["candidates"]})
    for m in cand:                       # the candidates the plan uses must still read the same live
        if m not in dry["candidates"] or meas["candidates"].get(m, {}).get("zero_bounds") != dry["candidates"][m]["zero_bounds"]:
            _stop(ops, core, run, P, "CANDIDATE_CHANGED_SINCE_DRY %s" % m)
    if core.state_hash(live_doc) != plan["dry_state_hash"]:
        _stop(ops, core, run, P, "PLAN_STALE (the passage changed since DRY %s: re-run DRY + make_swap_plan)" % plan["dry_run_id"])
    for s in plan["swaps"]:
        if not ops.asset_is_mesh(s["new_mesh"]):
            _stop(ops, core, run, P, "ASSET_MISSING %s" % s["new_mesh"])
    live_place = ops.placements(P, plan["swaps"])
    for s in plan["swaps"]:
        if not core.panel_matches(live_place[s["key"]], s["planned_panel"]) or \
                abs(live_place[s["key"]]["local_transform"]["location"][1] - s["planned_panel"]["local_transform"]["location"][1]) > core.PLACE_TOL_CM:
            _stop(ops, core, run, P, "PLACEMENT_DIFFERS_FROM_PLAN %s" % s["key"])
    keys_all = ["%s|%s" % (r["cue_guid"], s) for r in meas["rows"] for s in ("L", "R")]
    swapped = {s["key"] for s in plan["swaps"]}
    edges_before = meas["edges"]
    seg_before = ops.segments()
    count_before = meas["materialized_count"]
    before_texts = ops.cue_texts()
    settings_before = ops.settings_texts()
    tindex = {r["cue_guid"]: r["show_index"] for r in meas["rows"]}
    targets = _targets(plan, tindex)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    backup_dir, backup_files = ops.backup("PreRZSwap%s-%s" % (P, stamp))
    orig_path = os.path.join(here, "rzswap_originals_%s_%s.json" % (P, run))
    if os.path.exists(orig_path):
        _stop(ops, core, run, P, "ORIGINALS_EXIST %s" % orig_path)
    old_panels = ops.live_panels(sorted(swapped))
    originals = {"run_id": run, "passage": P, "made": datetime.datetime.now().isoformat(timespec="seconds"),
                 "backup_dir": backup_dir, "backup_files": backup_files, "decided_by": args.get("decided_by"),
                 "plan_hash": plan["inputs_hash"], "dry_run_id": plan["dry_run_id"],
                 "swaps": [{"key": s["key"], "label": s["label"], "side": s["side"], "cue_guid": s["cue_guid"],
                            "show_index": tindex[s["cue_guid"]], "original_panel": old_panels[s["key"]],
                            "written_panel": s["planned_panel"], "edge_before": edges_before.get(s["key"])}
                           for s in plan["swaps"]],
                 "all_cue_texts": before_texts, "settings_texts": settings_before}
    _write_json(orig_path, originals, fsync=True)
    _write_json(os.path.join(here, active_name(P)), {"run_id": run, "originals": orig_path}, fsync=True)
    ops.log("%s_ORIGINALS|run=%s|passage=%s|path=%s|backup=%s" % (core.MARK, run, P, orig_path, backup_dir))

    def rollback(reason):
        try:
            ok = ops.restore_pristine() and ops.cue_texts() == before_texts
            if ok is True and not ops.materialize(P):
                ok = "RESTORED_BUT_REMATERIALIZE_FAILED"
        except Exception as exc:  # noqa: BLE001
            ok = "RESTORE_RAISED %s" % exc
        _stop(ops, core, run, P, "%s | in-memory restore=%s | NOTHING SAVED: if restore is not True relaunch with Don't "
                                 "Save; then delete %s (disk is unchanged)" % (reason, ok, active_name(P)))

    try:
        ops.write_panels({s["key"]: s["planned_panel"] for s in plan["swaps"]})
    except Exception as exc:  # noqa: BLE001
        rollback("WRITE_RAISED %s" % exc)
    try:
        after_texts = ops.cue_texts()
        bad = core.verify_texts(tc, before_texts, after_texts, targets)
        live = ops.live_panels(sorted(swapped))
        for s in plan["swaps"]:
            if not live.get(s["key"]) or not core.panel_matches(live[s["key"]], s["planned_panel"]):
                bad.append("WRITTEN_PANEL_READBACK %s" % s["key"])
        for i, sides in targets.items():
            for sd in sides:
                if core.panel_text(tc, before_texts[i], sd) == core.panel_text(tc, after_texts[i], sd):
                    bad.append("TARGET_PANEL_TEXT_UNCHANGED index %d %s (the write did nothing)" % (i, sd))
        if ops.settings_texts() != settings_before:
            bad.append("PASSAGE_SETTINGS_CHANGED")
        if ops.segments() != seg_before:
            bad.append("COMPILED_SEGMENTS_CHANGED")
    except Exception as exc:  # noqa: BLE001
        bad = ["READBACK_RAISED %s" % exc]
    if bad:
        rollback("READBACK_FAILED %s" % bad[:6])
    try:
        if not ops.materialize(P):
            rollback("MATERIALIZE_FAILED")
        if ops.materialized_count(P) != count_before:
            rollback("MATERIALIZED_COUNT %d != %d" % (ops.materialized_count(P), count_before))
        edges_after = ops.world_edges(P)
    except core.PlanError:
        raise
    except Exception as exc:  # noqa: BLE001
        rollback("MATERIALIZE_OR_PROBE_RAISED %s" % exc)
    probe, bad = core.edge_verdict(keys_all, swapped, edges_before, edges_after)
    if bad:
        rollback("WORLD_EDGE_PROBE %s" % bad[:6])
    cen = ops.census()
    if not set(cen["content"]) <= {core.SHOW_PATH} or not set(cen["maps"]) <= {core.WORLD_PATH} \
            or core.SHOW_PATH not in cen["content"]:
        rollback("DIRTY_SCOPE %s (expected Show (+ level) only)" % json.dumps(cen))
    if ops.zz_actors():
        rollback("ZZ_ACTORS_APPEARED %s" % ops.zz_actors())
    if not ops.save_show():
        _stop(ops, core, run, P, "SHOW_SAVE_FALSE (Show dirty: relaunch with Don't Save; nothing else saved)")
    if not ops.save_level():
        _stop(ops, core, run, P, "LEVEL_SAVE_FALSE (Show saved, level not: run REVERT)")
    cen = ops.census()
    if cen != CLEAN:
        _stop(ops, core, run, P, "DIRTY_AFTER_SAVE %s" % json.dumps(cen))
    if ops.cue_texts() != after_texts:
        _stop(ops, core, run, P, "POST_SAVE_READBACK_DIFFERS")
    rec = {"run_id": run, "passage": P, "originals": orig_path, "backup_dir": backup_dir, "plan_hash": plan["inputs_hash"],
           "written": {s["key"]: s["planned_panel"] for s in plan["swaps"]}, "edge_probe": probe, "census_after": cen,
           "saved": [core.SHOW_PATH, core.WORLD_PATH], "decided_by": args.get("decided_by")}
    _write_json(os.path.join(here, "rzswap_apply_%s_%s.json" % (P, run)), rec, fsync=True)
    ops.log("%s_APPLY_OK|run=%s|passage=%s|swaps=%d|edge_probe=%d sides (%d controls, max swapped delta %.4f cm)|"
            "saved=show,level|census=clean|originals=%s" % (
                core.MARK, run, P, len(plan["swaps"]), len(probe), sum(p["control"] for p in probe),
                max([abs(p["inner_delta_cm"]) for p in probe if not p["control"]] or [0.0]), orig_path))
    return rec


def run_revert(ops, core, tc, args, orig, run, here):
    P = args["passage"]
    _guard_start(ops, core, run, P)
    apply_path = os.path.join(here, "rzswap_apply_%s_%s.json" % (P, orig["run_id"]))
    applied = _read_json(apply_path)
    if not applied:
        _stop(ops, core, run, P, "NO_APPLY_RECORD %s" % apply_path)
    keys = sorted(applied["written"])
    live = ops.live_panels(keys)
    drift = core.revert_drift(live, applied["written"])
    if drift:
        _stop(ops, core, run, P, "%s -- refused: someone re-wrote a panel this tool wrote; compare by hand" % drift[:4])
    before_texts = ops.cue_texts()
    settings_before = ops.settings_texts()
    seg_before = ops.segments()
    edges_pre = ops.world_edges(P)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    backup_dir, _ = ops.backup("PreRZSwapRevert%s-%s" % (P, stamp))
    ops.log("%s_REVERT_BACKUP|run=%s|passage=%s|backup=%s" % (core.MARK, run, P, backup_dir))
    index = {}
    for i, t in enumerate(before_texts):
        index[str(tc.get_field(t, "CueGuid")).replace("-", "").upper()] = i
    targets = {}
    for s in orig["swaps"]:
        if s["cue_guid"] not in index:
            _stop(ops, core, run, P, "CUE_GONE %s" % s["cue_guid"])
        targets.setdefault(index[s["cue_guid"]], []).append(s["side"])
    try:
        ops.write_panels({s["key"]: s["original_panel"] for s in orig["swaps"]})
        after_texts = ops.cue_texts()
        bad = core.verify_texts(tc, before_texts, after_texts, targets)
        now = ops.live_panels(keys)
        for s in orig["swaps"]:
            if not now.get(s["key"]) or not core.panel_matches(now[s["key"]], s["original_panel"]):
                bad.append("REVERTED_PANEL_READBACK %s" % s["key"])
        if ops.settings_texts() != settings_before:
            bad.append("PASSAGE_SETTINGS_CHANGED")
        if ops.segments() != seg_before:
            bad.append("COMPILED_SEGMENTS_CHANGED")
    except Exception as exc:  # noqa: BLE001
        bad = ["REVERT_WRITE_OR_READBACK_RAISED %s" % exc]
    if bad:
        ok = ops.restore_pristine() and ops.cue_texts() == before_texts
        _stop(ops, core, run, P, "REVERT_READBACK %s | in-memory restore=%s | nothing saved (relaunch with Don't Save "
                                 "if restore is not True)" % (bad[:6], ok))
    if not ops.materialize(P):
        _stop(ops, core, run, P, "MATERIALIZE_FAILED (Show dirty, unsaved: relaunch with Don't Save)")
    edges_after = ops.world_edges(P)
    expect = {s["key"]: s["edge_before"]["inner_cm"] for s in orig["swaps"] if s.get("edge_before")}
    probe, bad = core.edge_verdict(sorted(edges_pre), set(expect), edges_pre, edges_after, expect=expect)
    if bad:
        _stop(ops, core, run, P, "REVERT_WORLD_EDGE_PROBE %s (Show dirty, unsaved: relaunch with Don't Save)" % bad[:6])
    c = ops.census()
    if not set(c["content"]) <= {core.SHOW_PATH} or not set(c["maps"]) <= {core.WORLD_PATH}:
        _stop(ops, core, run, P, "DIRTY_SCOPE %s" % json.dumps(c))
    if not ops.save_show() or not ops.save_level():
        _stop(ops, core, run, P, "SAVE_FALSE")
    if ops.census() != CLEAN:
        _stop(ops, core, run, P, "DIRTY_AFTER_SAVE")
    if ops.cue_texts() != after_texts:
        _stop(ops, core, run, P, "POST_SAVE_REVERT_READBACK")
    op = os.path.join(here, "rzswap_originals_%s_%s.json" % (P, orig["run_id"]))
    _write_json(os.path.join(here, "rzswap_revert_%s_%s.json" % (P, run)),
                {"run_id": run, "reverted": orig["run_id"], "backup_dir": backup_dir, "edge_probe": probe})
    os.replace(op, op.replace(".json", "_reverted.json"))
    act = os.path.join(here, active_name(P))
    if os.path.exists(act):
        os.remove(act)
    ops.log("%s_REVERT_OK|run=%s|passage=%s|reverted=%s|sides=%d|saved=show,level|census=clean" % (
        core.MARK, run, P, orig["run_id"], len(orig["swaps"])))


def main():
    here = _here()
    core = _load("rzswap_core_live", os.path.join(here, "rzswap_core.py"))
    tc = _load("topple_core_for_rzswap", os.path.normpath(os.path.join(here, "..", "topple", "topple_core.py")))
    rzc = _load("rzimport_core_for_rzswap", os.path.normpath(os.path.join(here, "..", "rzimport", "rzimport_core.py")))
    ops = UnrealOps(core, tc, here)
    run = datetime.datetime.now().strftime("RZSW-%Y%m%d-%H%M%S")
    P = "-"
    try:
        args = _read_json(os.path.join(here, ARGS_NAME))
        P = str(args.get("passage") or "-")
        mode = str(args.get("mode") or "").upper()
        plan = _read_json(os.path.join(here, args.get("plan") or "rzswap_plan_%s.json" % P)) if mode == "APPLY" else None
        orig = None
        if mode == "REVERT":
            act = os.path.join(here, active_name(P))
            core.require(os.path.exists(act), "NO_ACTIVE_ORIGINALS %s" % act)
            orig = _read_json(_read_json(act)["originals"])
        core.validate_args(args, plan, orig)
    except (core.PlanError, OSError, ValueError, KeyError) as exc:
        _stop(ops, core, run, P, "ARGS|%s" % exc)
    try:
        if mode == "DRY":
            run_dry(ops, core, args, run, here, candidate_meshes(ops.project_dir(), args["manifests"], P, rzc))
        elif mode == "APPLY":
            run_apply(ops, core, tc, args, plan, run, here)
        else:
            run_revert(ops, core, tc, args, orig, run, here)
    except core.PlanError:
        raise
    except Exception as exc:  # noqa: BLE001 -- an unexpected API error is a STOP, never a pass
        _stop(ops, core, run, P, "UNEXPECTED %s: %s" % (type(exc).__name__, exc))


if unreal is not None:
    main()
