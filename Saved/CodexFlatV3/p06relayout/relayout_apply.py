"""P06 RELAYOUT -- DRY / APPLY / REVERT (7 Oct, offline-written, NEVER RUN IN UNREAL BY ITS AUTHOR).

Run ONLY through relayout_run.py (purges cached Saved modules, then runs this file) with relayout_args.json:
  DRY     {"mode": "DRY", "confirm": "DRY P06RELAYOUT"}       read-only, CLEAN census. Measures P06 live, resolves every
          planned mesh against the editor, computes the inner-edge placements, inventories attachments / Master pins /
          Structure 06 / topple state -> relayout_plan.json (+ relayout_dry_<run>.json) and prints the APPLY confirm.
          FLATV3_P06RELAYOUT_DRY_OK|run=..  (gates may still fail: read "refusals")
  APPLY   {"mode": "APPLY", "confirm": "APPLY P06RELAYOUT <token>", "decided_by": "Gary ...",
           "attachments_ack": "DROPPED_ROWS_GO_DARK_KEPT_ROWS_MOVE", "structure_ack": "STRUCTURE_06_LEFT_STALE"}
          Show + level write. FLATV3_P06RELAYOUT_APPLY_OK|run=..
  REVERT  {"mode": "REVERT", "confirm": "REVERT P06RELAYOUT <apply run id>"}   exact restore of every P06 cue text and
          order + P06 settings. FLATV3_P06RELAYOUT_REVERT_OK|run=..
Markers: FLATV3_P06RELAYOUT_<MODE>_OK|run=<id>  /  FLATV3_P06RELAYOUT_STOPPED|run=<id>|reason=..  (parse by run id).

WHAT APPLY WRITES (only Show.Cues[first .. first+63] and P06's PassageSettings.LastCueGuid):
  * the 29 kept cues (relayout_core.LAYOUT) in plan order at the front of the old P06 index range, each with
    IntervalToNext = gap*96 ticks and GapToNextCm = gap (the LAST kept cue keeps its own unused values), and its
    swapped sides set to planned panels: new mesh, PRESERVE_ASSET, no flip, identity rotation/scale, local Y from
    the slot-D inner_edge rule (swapkit/dry.py:93-101, common.side_bounds [prec, ran 6 Oct FV3D]) -- the new mesh's
    inner edge lands on the OLD panel's inner edge, computed in the Unreal frame from live bounds (memory
    tk-lateral-shift-frame-mirrored), then MEASURED in the world after materialize (world-edge probe, +/- controls).
  * the 35 dropped cues, unchanged except bEnabled=false, behind them (the P06 range keeps its 64 indices, so every
    cue outside P06 keeps its index and text -- asserted byte-identical).
  * reconcile_passage_settings() then LastCueGuid = last kept cue, asserted [prec p6_workflow.py:768-774, ran 4 Oct].
  Mechanisms, LocalOverrideMask, labels, OccurrenceOffset, attachments, Top panels: never written (asserted by text).
NOT DONE (flagged): no Master rebuild (segment frames are asserted unchanged; the Master keeps no per-wing data for
  P06 unless a wing pin exists -- DRY refuses if one does); no Structure 06 materialize (conductor 7 Oct: Structure
  actors are out of scope tonight; its station signature goes stale, IsStructureCurrent() false [decl
  InfinityStageStructureActor.h:1122-1124, .cpp:358-365], and it keeps its last build until its owner
  re-materializes it -- structure_ack); no topple write.

SAFETY: no PIE (never ends it); expected world; census CLEAN at start; no ZZ_/TEMP actors; topple's
  topple_originals_ACTIVE.json must be ABSENT (its STILL REVERT compares whole cue texts by index and would fail after a
  relayout -- topple_apply.py:930-938; override "topple_active_ack" only if the topple owner retires it by hand);
  live plan inputs_hash == DRY plan; originals JSON (every P06 cue text + order + settings text) fsynced BEFORE any
  change; Backups/PreP06Relayout-<stamp> copies of the Show .uasset + level .umap (sha256-verified); read-back of every
  written field + every unwritten one by text; materialize ONLY the P06 Passage actor; dirty set within {Show, level};
  save those two only (never Save All); census clean after; re-read after save; success marker last. Any read-back
  failure restores the old cue list in memory and STOPS without saving (relaunch with Don't Save if told to).
  No unreal objects in module globals (everything inside functions / the ops object); never reloads the level; no
  Sequencer open/scrub (the Master asset is only loaded to read its P06 section's pin arrays).
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

ARGS_NAME = "relayout_args.json"
PLAN_NAME = "relayout_plan.json"
ACTIVE_NAME = "relayout_originals_ACTIVE.json"
TOPPLE_ACTIVE_REL = os.path.join("..", "topple", "topple_originals_ACTIVE.json")
EDGE_TOL_CM = 1.0
CONTROL_TOL_CM = 0.05


def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                            "CodexFlatV3", "p06relayout")
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
        json.dump(doc, fh, indent=1)
        fh.flush()
        if fsync:
            os.fsync(fh.fileno())
    os.replace(tmp, path)


def _read_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# =====================================================================================================================
# Cue-text comparisons (struct export text; parser = topple_core.fields [prec, measured live 7 Oct])
# =====================================================================================================================

def blank_kept(tc, cue_text, swapped_sides):
    wp = tc.get_field(cue_text, "WingPair")
    names = ["IntervalToNext", "GapToNextCm"] + [{"L": "Left", "R": "Right"}[s] for s in swapped_sides]
    return tc.replace_field(cue_text, "WingPair", tc.without_fields(wp, names))


def blank_enabled(tc, cue_text):
    return tc.without_fields(cue_text, ("bEnabled",))


def text_outside_mechanism(tc, cue_text):
    return tc.cue_text_outside_mechanism(cue_text)


# =====================================================================================================================
# Unreal access (everything that touches `unreal`; the harness replaces this class)
# =====================================================================================================================

class UnrealOps:
    def __init__(self, core, tc, here):
        self.core, self.tc, self.here = core, tc, here
        self._common = None

    # ---- logging / context
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
        pk = lambda p: str(p.get_path_name()).split(".")[0]
        return {"content": sorted(pk(p) for p in lib.get_dirty_content_packages()),
                "maps": sorted(pk(p) for p in lib.get_dirty_map_packages())}

    def zz_actors(self):
        actors = unreal.GameplayStatics.get_all_actors_of_class(self._world(), unreal.Actor)
        return sorted(str(a.get_actor_label()) for a in actors
                      if str(a.get_actor_label()).upper().startswith(("ZZ_", "TEMP")))

    def topple_active(self):
        p = os.path.normpath(os.path.join(self.here, TOPPLE_ACTIVE_REL))
        return _read_json(p) if os.path.exists(p) else None

    # ---- helpers
    def _guid(self, g):
        return str(unreal.GuidLibrary.conv_guid_to_string(g)).upper()

    def _show(self):
        show = unreal.EditorAssetLibrary.load_asset(self.core.SHOW_PATH)
        if show is None:
            raise self.core.PlanError("SHOW_LOAD_FAIL")
        return show

    def _swapkit(self):
        if self._common is None:   # swapkit/common.py by path (side_bounds, panel_plain, set_panel) [prec, ran 6 Oct]
            self._common = _load("swapkit_common_p06relayout",
                                 os.path.normpath(os.path.join(self.here, "..", "swapkit", "common.py")))
        return self._common

    def _p06_actor(self):
        hits = [a for a in unreal.GameplayStatics.get_all_actors_of_class(self._world(), unreal.InfinityStagePassageActor)
                if self._guid(a.get_editor_property("passage_guid")) == self.core.P06_GUID]
        if len(hits) != 1:
            raise self.core.PlanError("P06_ACTOR_COUNT %d" % len(hits))
        return hits[0]

    def _p06_settings(self, show):
        settings = list(show.get_editor_property("passage_settings"))
        idx = [i for i, s in enumerate(settings) if self._guid(s.get_editor_property("passage_guid")) == self.core.P06_GUID]
        if len(idx) != 1:
            raise self.core.PlanError("P06_SETTINGS_COUNT %d" % len(idx))
        return settings, idx[0]

    def _mesh_path(self, mesh):
        return None if mesh is None else str(mesh.get_path_name()).split(".")[0]

    # ---- reads
    def cue_texts(self):
        return [c.export_text() for c in self._show().get_editor_property("cues")]

    def settings_texts(self):
        return [s.export_text() for s in self._show().get_editor_property("passage_settings")]

    def read_p06(self):
        """Live P06 rows in compiled order + settings. Compiled order via get_wing_pair_cue_guids_in_passage
        [prec topple_apply.py:275, ran 7 Oct]."""
        show = self._show()
        settings, si = self._p06_settings(show)
        st = settings[si]
        guids = [self._guid(g) for g in show.get_wing_pair_cue_guids_in_passage(st.get_editor_property("passage_guid"))]
        cues = list(show.get_editor_property("cues"))
        index = {self._guid(c.get_editor_property("cue_guid")): i for i, c in enumerate(cues)}
        rows = []
        for g in guids:
            if g not in index:
                raise self.core.PlanError("P06_CUE_UNRESOLVED %s" % g)
            cue = cues[index[g]]
            pair = cue.get_editor_property("wing_pair")
            text = cue.export_text()
            atts = list(pair.get_editor_property("attachments"))
            rows.append({"cue_guid": g, "label": str(cue.get_editor_property("label")), "show_index": index[g],
                         "enabled": bool(cue.get_editor_property("enabled")),
                         "interval_ticks": int(pair.get_editor_property("interval_to_next").value),
                         "gap_cm": float(pair.get_editor_property("gap_to_next_cm")),
                         "L_mesh": self._mesh_path(pair.get_editor_property("left").get_editor_property("mesh")),
                         "R_mesh": self._mesh_path(pair.get_editor_property("right").get_editor_property("mesh")),
                         "L_panel": self._swapkit().panel_plain(pair.get_editor_property("left")),
                         "R_panel": self._swapkit().panel_plain(pair.get_editor_property("right")),
                         "mechanism_sha": _sha(pair.get_editor_property("mechanism").export_text()),
                         "attachments": [{"label": str(a.get_editor_property("label")), "kind": str(a.get_editor_property("kind"))}
                                         for a in atts],
                         "text_outside_mechanism_sha": _sha(text_outside_mechanism(self.tc, text))})
        sd = {"lead_in_frames": int(st.get_editor_property("lead_in_frames").value),
              "lead_in_distance_cm": float(st.get_editor_property("lead_in_distance_cm")),
              "tail_frames": int(st.get_editor_property("tail_frames").value),
              "tail_distance_cm": float(st.get_editor_property("tail_distance_cm")),
              "first_cue_guid": self._guid(st.get_editor_property("first_cue_guid")),
              "last_cue_guid": self._guid(st.get_editor_property("last_cue_guid"))}
        extra = {"label": str(st.get_editor_property("label")), "fit_mode": str(st.get_editor_property("fit_mode")),
                 "tick": float(show.get_editor_property("tick_resolution").numerator) /
                         float(show.get_editor_property("tick_resolution").denominator)}
        return rows, sd, extra

    def segments(self):
        """Compiled segments of the whole Show [prec p6_workflow.py:171-183, ran 4 Oct]."""
        transport = unreal.new_object(unreal.InfinityStageTransportController)
        if not bool(transport.build_segments(self._show())):
            raise self.core.PlanError("BUILD_SEGMENTS_FAIL")
        out = []
        for s in list(transport.get_editor_property("segments")):
            sf, ef = s.get_editor_property("start_frame"), s.get_editor_property("end_frame")
            out.append([str(s.get_editor_property("label")), int(getattr(sf, "value", sf)), int(getattr(ef, "value", ef))])
        return out

    def asset_exists(self, path):
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            return False
        return isinstance(unreal.EditorAssetLibrary.load_asset(path), unreal.StaticMesh)

    def placements(self, plan_rows, live_rows):
        """Planned panel dicts for every swapped side (slot-D inner_edge rule, live bounds, Unreal frame)."""
        common = self._swapkit()
        show = self._show()
        lib_ref = show.get_editor_property("wing_library")
        lib = unreal.EditorAssetLibrary.load_asset(common.asset_path(lib_ref)) if lib_ref else None
        if lib is None:
            raise self.core.PlanError("WING_LIBRARY_LOAD_FAIL")
        by_mesh = {}
        for e in lib.get_editor_property("entries"):
            m = common.asset_path(e.get_editor_property("mesh"))
            if m:
                by_mesh[m] = e
        live = {r["cue_guid"]: r for r in live_rows}
        out = {}
        for r in plan_rows:
            for side in ("L", "R"):
                s = r["sides"][side]
                if s["action"] != "swap":
                    continue
                old = common.side_bounds(live[r["cue_guid"]][side + "_panel"], by_mesh)
                zero = common.side_bounds(self.core.planned_panel(s["mesh"], 0.0), by_mesh)
                y = self.core.inner_edge_y(side, old, zero)
                planned = self.core.planned_panel(s["mesh"], y)
                new = common.side_bounds(planned, by_mesh)
                k = "max_y_cm" if side == "L" else "min_y_cm"
                if abs(new[k] - old[k]) > 0.01:
                    raise self.core.PlanError("INNER_EDGE_PLAN_FAIL %s %s %.3f %.3f" % (r["label"], side, old[k], new[k]))
                out["%s|%s" % (r["cue_guid"], side)] = {"panel": planned, "old_inner_local": old[k],
                                                        "new_inner_local": new[k], "old_bounds": old, "new_bounds": new}
        return out

    def master_p06_pins(self):
        """Plain property reads only (memory puss-mcp-python-crashes-the-editor #5): no SequencerTools."""
        master = unreal.EditorAssetLibrary.load_asset(self.core.MASTER_PATH)
        secs = [x for t in master.get_tracks() if "InfinityPassage" in t.get_class().get_name()
                for x in t.get_sections() if self._guid(x.get_editor_property("passage_guid")) == self.core.P06_GUID]
        if len(secs) != 1:
            raise self.core.PlanError("P06_SECTION_COUNT %d" % len(secs))
        wing = [self._guid(g) for g in secs[0].get_editor_property("pinned_wing_cue_guids")]
        rel = [int(getattr(f, "value", f)) for f in secs[0].get_editor_property("pinned_passage_frames")]
        return {"wing_pins": wing, "relative_pins": rel}

    def structure_06(self):
        hits = [a for a in unreal.GameplayStatics.get_all_actors_of_class(self._world(), unreal.InfinityStageStructureActor)
                if "06" in str(a.get_actor_label())]
        return [{"label": str(a.get_actor_label()), "current": bool(a.is_structure_current())} for a in hits]

    def world_edges(self, guids):
        """Route-relative lateral inner edge of every materialized L/R panel of the given cues (world, Unreal frame),
        the topple _side_measure corner method [prec topple_apply.py:205-218, ran 7 Oct]."""
        actor = self._p06_actor()
        spline = actor.get_editor_property("route")
        space = unreal.SplineCoordinateSpace.WORLD
        out = {}
        for ref in actor.get_editor_property("materialized_panels"):
            g = self._guid(ref.get_editor_property("cue_guid"))
            s = str(ref.get_editor_property("side")).upper()
            side = "L" if "LEFT" in s else "R" if "RIGHT" in s else None
            if g not in guids or side is None:
                continue
            base = ref.get_editor_property("base_world_transform")
            mesh = ref.get_editor_property("component").get_editor_property("static_mesh")
            box = mesh.get_bounding_box()
            lat, route = [], []
            for x in (box.min.x, box.max.x):
                for y in (box.min.y, box.max.y):
                    p = base.transform_location(unreal.Vector(x, y, box.min.z))
                    d = float(spline.get_distance_along_spline_at_location(p, space))
                    o = spline.get_location_at_distance_along_spline(d, space)
                    rv = spline.get_right_vector_at_distance_along_spline(d, space)
                    lat.append((p.x - o.x) * rv.x + (p.y - o.y) * rv.y + (p.z - o.z) * rv.z)
                    route.append(d)
            key = "%s|%s" % (g, side)
            if key in out:
                out[key]["error"] = "DUPLICATE_REF"
                continue
            out[key] = {"inner_cm": max(lat) if side == "L" else min(lat), "route_mid_cm": sum(route) / 4.0,
                        "mesh": self._mesh_path(mesh)}
        return out

    def materialized_count(self):
        return int(self._p06_actor().get_editor_property("materialized_wing_pair_count"))

    # ---- writes
    def write_layout(self, plan, placements):
        """The one Show write. Builds the new cue list in Python and sets it in one call."""
        common = self._swapkit()
        show = self._show()
        cues = list(show.get_editor_property("cues"))
        first = int(plan["first_show_index"])
        n_old = int(plan["count_old"])
        by = {self._guid(c.get_editor_property("cue_guid")): c for c in cues[first:first + n_old]}
        kept = []
        for r in plan["rows"]:
            cue = by[r["cue_guid"]]
            pair = cue.get_editor_property("wing_pair")
            if r["interval_ticks"] is not None:
                iv = pair.get_editor_property("interval_to_next")
                iv.set_editor_property("value", int(r["interval_ticks"]))
                pair.set_editor_property("interval_to_next", iv)
                pair.set_editor_property("gap_to_next_cm", float(r["gap_cm"]))
            for side, prop in (("L", "left"), ("R", "right")):
                if r["sides"][side]["action"] == "swap":
                    panel = pair.get_editor_property(prop)
                    common.set_panel(panel, placements["%s|%s" % (r["cue_guid"], side)]["panel"])
                    pair.set_editor_property(prop, panel)
            cue.set_editor_property("wing_pair", pair)
            kept.append(cue)
        dropped = []
        for d in plan["dropped"]:
            cue = by[d["cue_guid"]]
            cue.set_editor_property("enabled", False)
            dropped.append(cue)
        new = cues[:first] + kept + dropped + cues[first + n_old:]
        if len(new) != len(cues):
            raise self.core.PlanError("CUE_COUNT_WOULD_CHANGE")
        show.modify()
        show.set_editor_property("cues", new)
        show.reconcile_passage_settings()
        settings, si = self._p06_settings(show)
        st = settings[si]
        st.set_editor_property("last_cue_guid", kept[-1].get_editor_property("cue_guid"))
        settings[si] = st
        show.set_editor_property("passage_settings", settings)

    def restore(self, originals):
        """REVERT / in-memory rollback: every P06-range cue from its original export text, original order, and the
        original passage-settings texts. ShowCue/PassageSettings import_text = StructBase.import_text [bin
        PythonScriptPlugin.dll, measured on a mechanism struct by topple DRY 7 Oct]; whole-cue round trip is
        asserted here before anything is set."""
        show = self._show()
        cues = list(show.get_editor_property("cues"))
        first = int(originals["first_show_index"])
        restored = []
        for text in originals["p06_cue_texts"]:
            c = unreal.InfinityShowCue()
            if not c.import_text(text) or c.export_text() != text:
                raise self.core.PlanError("ORIGINAL_CUE_IMPORT_MISMATCH")
            restored.append(c)
        new = cues[:first] + restored + cues[first + len(restored):]
        sts = []
        for text in originals["settings_texts"]:
            s = unreal.InfinityPassageSettings()
            if not s.import_text(text) or s.export_text() != text:
                raise self.core.PlanError("ORIGINAL_SETTINGS_IMPORT_MISMATCH")
            sts.append(s)
        show.modify()
        show.set_editor_property("cues", new)
        show.set_editor_property("passage_settings", sts)

    def materialize(self):
        return bool(self._p06_actor().materialize_passage())

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

def _stop(ops, core, run, reason):
    ops.log_error("%s_STOPPED|run=%s|reason=%s" % (core.MARK, run, reason))
    raise core.PlanError(reason)


def _guard_start(ops, core, run):
    try:
        ops.guard_context()
    except core.PlanError as exc:
        _stop(ops, core, run, str(exc))
    c = ops.census()
    if c != {"content": [], "maps": []}:
        _stop(ops, core, run, "DIRTY_CENSUS (another stream's unsaved work? refused) %s" % json.dumps(c))
    if ops.zz_actors():
        _stop(ops, core, run, "ZZ_OR_TEMP_ACTORS_IN_LEVEL %s" % ops.zz_actors())


def _live_plan(ops, core, args):
    rows, settings, extra = ops.read_p06()
    roots = args.get("mesh_roots") or core.DEFAULT_MESH_ROOTS
    variants = tuple(args.get("variants") or core.DEFAULT_VARIANTS)
    plan = core.build_plan(rows, settings, exists=ops.asset_exists, roots=roots, variants=variants)
    return rows, settings, extra, plan


def _expected_pass(plan):
    return [(r["cue_guid"], r["pass_frame_rel"], r["station_cm"]) for r in plan["rows"]]


def run_dry(ops, core, args, run, here):
    _guard_start(ops, core, run)
    rows, settings, extra, plan = _live_plan(ops, core, args)
    ref = plan["refusals"]
    doc = {"run_id": run, "made": datetime.datetime.now().isoformat(timespec="seconds"), "passage": extra}
    if not ref:
        try:
            pl = ops.placements(plan["rows"], rows)
            plan["placements"] = pl
        except core.PlanError as exc:
            ref.append("PLACEMENT %s" % exc)
    pins = ops.master_p06_pins()
    moved = {r["cue_guid"] for r in plan.get("rows", [])} | {d["cue_guid"] for d in plan.get("dropped", [])}
    bad_pins = [g for g in pins["wing_pins"] if g in moved]
    if bad_pins:
        ref.append("MASTER_WING_PIN_ON_P06_ROW %s (the rebuild would drop it / the pin would move: re-plan)" % bad_pins)
    if pins["relative_pins"]:
        doc["relative_pins_note"] = "relative pins are frame-based and the P06 length is unchanged: unaffected [inf]"
    topple = ops.topple_active()
    if topple and args.get("topple_active_ack") != "TOPPLE_ACTIVE_RETIRED_BY_ITS_OWNER":
        ref.append("TOPPLE_ACTIVE_PRESENT %s: REVERT topple first (its REVERT reads whole cue texts by show index and "
                   "cannot run after a relayout); re-apply STILL + chain afterwards" % topple.get("run_id"))
    plan["attachments"] = {"kept": {r["cue_guid"]: next(x["attachments"] for x in rows if x["cue_guid"] == r["cue_guid"])
                                    for r in plan.get("rows", [])},
                           "dropped": {d["cue_guid"]: next(x["attachments"] for x in rows if x["cue_guid"] == d["cue_guid"])
                                       for d in plan.get("dropped", [])}}
    plan["attachment_counts"] = {"kept_rows": sum(len(v) for v in plan["attachments"]["kept"].values()),
                                 "dropped_rows": sum(len(v) for v in plan["attachments"]["dropped"].values())}
    plan["structure_06"] = ops.structure_06()
    plan["master_pins"] = pins
    plan["segments_before"] = ops.segments()
    plan["fit_mode"] = extra["fit_mode"]
    plan["dry_run_id"] = run
    plan["gates_ok"] = not ref
    end = ops.census()
    if end != {"content": [], "maps": []}:
        _stop(ops, core, run, "DRY_DIRTIED_SOMETHING %s (do not save; report)" % json.dumps(end))
    _write_json(os.path.join(here, "relayout_dry_%s.json" % run), dict(doc, plan=plan))
    _write_json(os.path.join(here, PLAN_NAME), plan)
    ops.log("%s_DRY_OK|run=%s|rows=%d->%d|swaps=%d|gates_ok=%s|refusals=%d|confirm=APPLY P06RELAYOUT %s" % (
        core.MARK, run, plan.get("count_old", 0), plan.get("count_new", 0), plan.get("swaps", 0), plan["gates_ok"],
        len(ref), plan.get("confirm_token")))
    for x in ref:
        ops.log("%s_DRY_REFUSAL|run=%s|%s" % (core.MARK, run, x))
    return plan


def _verify_written(ops, core, tc, plan, before_texts, after_texts, placements):
    """Every check that can be done from the Show alone. Returns a list of failures (empty = pass)."""
    bad = []
    first, n = int(plan["first_show_index"]), int(plan["count_old"])
    if len(after_texts) != len(before_texts):
        return ["CUE_COUNT_CHANGED"]
    for i, (a, b) in enumerate(zip(before_texts, after_texts)):
        if (i < first or i >= first + n) and a != b:
            bad.append("NON_P06_CUE_CHANGED index %d" % i)
    before_by = {}
    for t in before_texts[first:first + n]:
        g = tc.get_field(t, "CueGuid")
        before_by[g] = t
    norm = lambda g: str(g).replace("-", "").upper()
    before_by = {norm(k): v for k, v in before_by.items()}
    for k, r in enumerate(plan["rows"]):
        t = after_texts[first + k]
        if norm(tc.get_field(t, "CueGuid")) != r["cue_guid"]:
            bad.append("ORDER row %d is %s want %s" % (k, tc.get_field(t, "CueGuid"), r["cue_guid"]))
            continue
        sw = [s for s in ("L", "R") if r["sides"][s]["action"] == "swap"]
        if blank_kept(tc, t, sw) != blank_kept(tc, before_by[r["cue_guid"]], sw):
            bad.append("KEPT_ROW_CHANGED_OUTSIDE_PLAN %s" % r["label"])
    for j, d in enumerate(plan["dropped"]):
        t = after_texts[first + len(plan["rows"]) + j]
        if norm(tc.get_field(t, "CueGuid")) != d["cue_guid"]:
            bad.append("DROPPED_ORDER %d" % j)
            continue
        if blank_enabled(tc, t) != blank_enabled(tc, before_by[d["cue_guid"]]):
            bad.append("DROPPED_ROW_CHANGED_BEYOND_ENABLED %s" % d["label"])
        if str(tc.get_field(t, "bEnabled")).strip() not in ("False", "false"):
            bad.append("DROPPED_ROW_STILL_ENABLED %s" % d["label"])
    rows, settings, _ = ops.read_p06()
    if [r["cue_guid"] for r in rows] != [r["cue_guid"] for r in plan["rows"]]:
        bad.append("COMPILED_P06_ORDER_DIFFERS")
    else:
        for live, r in zip(rows, plan["rows"]):
            if r["interval_ticks"] is not None and (live["interval_ticks"] != r["interval_ticks"] or
                                                    abs(live["gap_cm"] - r["gap_cm"]) > 1e-6):
                bad.append("INTERVAL_GAP_READBACK %s %s/%s" % (r["label"], live["interval_ticks"], live["gap_cm"]))
            for side in ("L", "R"):
                if r["sides"][side]["action"] == "swap":
                    want = placements["%s|%s" % (r["cue_guid"], side)]["panel"]
                    if not ops_panel_matches(ops, live[side + "_panel"], want):
                        bad.append("PANEL_READBACK %s %s" % (r["label"], side))
    sb = plan["settings_before"]
    for k in ("lead_in_frames", "lead_in_distance_cm", "tail_frames", "tail_distance_cm", "first_cue_guid"):
        if settings[k] != sb[k]:
            bad.append("SETTINGS_%s_CHANGED" % k)
    if settings["last_cue_guid"] != plan["rows"][-1]["cue_guid"]:
        bad.append("LAST_CUE_GUID %s" % settings["last_cue_guid"])
    if ops.segments() != plan["segments_before"]:
        bad.append("COMPILED_SEGMENTS_CHANGED")
    return bad


def ops_panel_matches(ops, actual, expected):
    if hasattr(ops, "panel_matches"):
        return ops.panel_matches(actual, expected)
    return ops._swapkit().panel_matches(actual, expected)


def run_apply(ops, core, tc, args, plan, run, here):
    _guard_start(ops, core, run)
    if os.path.exists(os.path.join(here, ACTIVE_NAME)):
        _stop(ops, core, run, "UNREVERTED_APPLY_EXISTS %s (REVERT it first)" % _read_json(os.path.join(here, ACTIVE_NAME)))
    topple = ops.topple_active()
    if topple and args.get("topple_active_ack") != "TOPPLE_ACTIVE_RETIRED_BY_ITS_OWNER":
        _stop(ops, core, run, "TOPPLE_ACTIVE_PRESENT %s (REVERT topple first)" % topple.get("run_id"))
    rows, settings, extra, live = _live_plan(ops, core, args)
    if live["refusals"]:
        _stop(ops, core, run, "LIVE_PLAN_REFUSED %s" % live["refusals"][:4])
    if live["inputs_hash"] != plan["inputs_hash"]:
        _stop(ops, core, run, "PLAN_STALE (live P06 / asset resolution differs from relayout_plan.json: re-run DRY)")
    for r in plan["rows"]:
        for side in ("L", "R"):
            s = r["sides"][side]
            if s["action"] == "swap" and not ops.asset_exists(s["mesh"]):
                _stop(ops, core, run, "ASSET_MISSING %s" % s["mesh"])
    placements = ops.placements(plan["rows"], rows)
    if {k: v["panel"] for k, v in placements.items()} != {k: v["panel"] for k, v in plan["placements"].items()}:
        _stop(ops, core, run, "PLACEMENTS_DIFFER_FROM_DRY")
    pins = ops.master_p06_pins()
    if pins["wing_pins"] != plan["master_pins"]["wing_pins"] or [g for g in pins["wing_pins"]
                                                                  if g in set(live["old_order"])]:
        _stop(ops, core, run, "MASTER_WING_PINS %s" % pins)
    if ops.segments() != plan["segments_before"]:
        _stop(ops, core, run, "SEGMENTS_CHANGED_SINCE_DRY")
    guids = set(live["old_order"])
    edges_before = ops.world_edges(guids)
    before_texts = ops.cue_texts()
    first, n = int(plan["first_show_index"]), int(plan["count_old"])
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    backup_dir, backup_files = ops.backup("PreP06Relayout-%s" % stamp)
    orig_path = os.path.join(here, "relayout_originals_%s.json" % run)
    if os.path.exists(orig_path):
        _stop(ops, core, run, "ORIGINALS_EXIST %s" % orig_path)
    originals = {"run_id": run, "made": datetime.datetime.now().isoformat(timespec="seconds"), "backup_dir": backup_dir,
                 "backup_files": backup_files, "decided_by": args.get("decided_by"), "plan_inputs_hash": plan["inputs_hash"],
                 "first_show_index": first, "p06_cue_texts": before_texts[first:first + n],
                 "all_cue_texts_sha": _sha("\n".join(before_texts)), "settings_texts": ops.settings_texts(),
                 "edges_before": edges_before}
    _write_json(orig_path, originals, fsync=True)
    _write_json(os.path.join(here, ACTIVE_NAME), {"run_id": run, "originals": orig_path}, fsync=True)
    ops.log("%s_ORIGINALS|run=%s|path=%s|backup=%s" % (core.MARK, run, orig_path, backup_dir))

    def rollback(reason):
        try:
            ops.restore(originals)
            ok = ops.cue_texts() == before_texts
            if ok is True and not ops.materialize():   # put the level's P06 back on the restored rows too
                ok = "RESTORED_BUT_REMATERIALIZE_FAILED"
        except Exception as exc:  # noqa: BLE001
            ok = "RESTORE_RAISED %s" % exc
        _stop(ops, core, run, "%s | in-memory restore=%s | NOTHING SAVED: if restore is not True relaunch with Don't "
                              "Save; then delete %s (disk is unchanged)" % (reason, ok, ACTIVE_NAME))

    try:
        ops.write_layout(plan, placements)
    except Exception as exc:  # noqa: BLE001
        rollback("WRITE_RAISED %s" % exc)
    after_texts = ops.cue_texts()
    try:   # a read-back that RAISES must roll back exactly like one that fails
        bad = _verify_written(ops, core, tc, plan, before_texts, after_texts, placements)
    except Exception as exc:  # noqa: BLE001
        bad = ["READBACK_RAISED %s" % exc]
    st_after = ops.settings_texts()
    if len(st_after) != len(originals["settings_texts"]):
        bad.append("PASSAGE_SETTINGS_COUNT_CHANGED")
    else:
        p06_si = [i for i, t in enumerate(originals["settings_texts"])
                  if str(tc.get_field(t, "PassageGuid")).replace("-", "").upper() == core.P06_GUID]
        for i, (a, b) in enumerate(zip(originals["settings_texts"], st_after)):
            if i in p06_si:
                if tc.without_fields(a, ("LastCueGuid",)) != tc.without_fields(b, ("LastCueGuid",)):
                    bad.append("P06_SETTINGS_CHANGED_BEYOND_LAST_CUE")
            elif a != b:
                bad.append("OTHER_PASSAGE_SETTINGS_CHANGED index %d" % i)
    if bad:
        rollback("READBACK_FAILED %s" % bad[:6])
    try:
        if not ops.materialize():
            rollback("MATERIALIZE_FAILED")
        if ops.materialized_count() != len(plan["rows"]):
            rollback("MATERIALIZED_COUNT %d != %d" % (ops.materialized_count(), len(plan["rows"])))
        # world-edge probe: swapped sides keep their old inner edge (+/- EDGE_TOL); kept sides are the controls
        edges_after = ops.world_edges({r["cue_guid"] for r in plan["rows"]})
    except core.PlanError:
        raise
    except Exception as exc:  # noqa: BLE001
        rollback("MATERIALIZE_OR_PROBE_RAISED %s" % exc)
    probe, bad = [], []
    for r in plan["rows"]:
        for side in ("L", "R"):
            key = "%s|%s" % (r["cue_guid"], side)
            b, a = edges_before.get(key), edges_after.get(key)
            if not b or not a or "error" in a:
                bad.append("EDGE_MISSING %s" % key)
                continue
            d = a["inner_cm"] - b["inner_cm"]
            ctl = r["sides"][side]["action"] == "keep"
            probe.append({"key": key, "label": r["label"], "control": ctl, "inner_delta_cm": d,
                          "route_shift_cm": a["route_mid_cm"] - b["route_mid_cm"], "mesh": a["mesh"]})
            if abs(d) > (CONTROL_TOL_CM if ctl else EDGE_TOL_CM):
                bad.append("INNER_EDGE_MOVED %s %s %.2f cm%s" % (r["label"], side, d, " (CONTROL)" if ctl else ""))
    if bad:
        rollback("WORLD_EDGE_PROBE %s" % bad[:6])
    cen = ops.census()
    if not set(cen["content"]) <= {core.SHOW_PATH} or not set(cen["maps"]) <= {core.WORLD_PATH} \
            or core.SHOW_PATH not in cen["content"]:
        rollback("DIRTY_SCOPE %s (expected Show (+ level) only)" % json.dumps(cen))
    if ops.zz_actors():
        rollback("ZZ_ACTORS_APPEARED %s" % ops.zz_actors())
    if not ops.save_show():
        _stop(ops, core, run, "SHOW_SAVE_FALSE (Show dirty: relaunch with Don't Save; REVERT from %s)" % orig_path)
    if not ops.save_level():
        _stop(ops, core, run, "LEVEL_SAVE_FALSE (Show saved, level not: run REVERT)")
    cen = ops.census()
    if cen != {"content": [], "maps": []}:
        _stop(ops, core, run, "DIRTY_AFTER_SAVE %s" % json.dumps(cen))
    if ops.cue_texts() != after_texts:
        _stop(ops, core, run, "POST_SAVE_READBACK_DIFFERS")
    _write_json(os.path.join(here, "relayout_apply_%s.json" % run),
                {"run_id": run, "originals": orig_path, "backup_dir": backup_dir, "after_p06_texts_sha": _sha(
                    "\n".join(after_texts[first:first + n])), "edge_probe": probe, "census_after": cen,
                 "structure_06": ops.structure_06(), "saved": [core.SHOW_PATH, core.WORLD_PATH]})
    ops.log("%s_APPLY_OK|run=%s|rows=%d->%d|swaps=%d|edge_probe=%d sides (%d controls)|saved=show,level|census=clean|"
            "originals=%s" % (core.MARK, run, plan["count_old"], plan["count_new"], plan["swaps"], len(probe),
                              sum(p["control"] for p in probe), orig_path))
    return probe


def run_revert(ops, core, tc, args, orig, run, here):
    _guard_start(ops, core, run)
    topple = ops.topple_active()
    if topple:
        _stop(ops, core, run, "TOPPLE_ACTIVE_PRESENT %s (REVERT the chain/STILL first: this REVERT restores whole cue "
                              "texts, mechanisms included)" % topple.get("run_id"))
    apply_path = os.path.join(here, "relayout_apply_%s.json" % orig["run_id"])
    if not os.path.exists(apply_path):
        _stop(ops, core, run, "NO_APPLY_RECORD %s" % apply_path)
    applied = _read_json(apply_path)
    texts = ops.cue_texts()
    first, n = int(orig["first_show_index"]), len(orig["p06_cue_texts"])
    if _sha("\n".join(texts[first:first + n])) != applied["after_p06_texts_sha"]:
        _stop(ops, core, run, "DRIFT_SINCE_APPLY (P06 cues edited after APPLY; refused -- compare by hand)")
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    backup_dir, _ = ops.backup("PreP06RelayoutRevert-%s" % stamp)
    ops.log("%s_REVERT_BACKUP|run=%s|backup=%s" % (core.MARK, run, backup_dir))
    ops.restore(orig)
    now = ops.cue_texts()
    if _sha("\n".join(now)) != orig["all_cue_texts_sha"] or ops.settings_texts() != orig["settings_texts"]:
        _stop(ops, core, run, "REVERT_READBACK (Show dirty, unsaved: relaunch with Don't Save)")
    if not ops.materialize():
        _stop(ops, core, run, "MATERIALIZE_FAILED")
    c = ops.census()
    if not set(c["content"]) <= {core.SHOW_PATH} or not set(c["maps"]) <= {core.WORLD_PATH}:
        _stop(ops, core, run, "DIRTY_SCOPE %s" % json.dumps(c))
    if not ops.save_show() or not ops.save_level():
        _stop(ops, core, run, "SAVE_FALSE")
    if ops.census() != {"content": [], "maps": []}:
        _stop(ops, core, run, "DIRTY_AFTER_SAVE")
    if _sha("\n".join(ops.cue_texts())) != orig["all_cue_texts_sha"]:
        _stop(ops, core, run, "POST_SAVE_REVERT_READBACK")
    op = os.path.join(here, "relayout_originals_%s.json" % orig["run_id"])
    os.replace(op, op.replace(".json", "_reverted.json"))
    act = os.path.join(here, ACTIVE_NAME)
    if os.path.exists(act):
        os.remove(act)
    ops.log("%s_REVERT_OK|run=%s|reverted=%s|saved=show,level|census=clean" % (core.MARK, run, orig["run_id"]))


def main():
    here = _here()
    core = _load("relayout_core_live", os.path.join(here, "relayout_core.py"))
    tc = _load("topple_core_for_relayout", os.path.normpath(os.path.join(here, "..", "topple", "topple_core.py")))
    ops = UnrealOps(core, tc, here)
    run = datetime.datetime.now().strftime("P06RL-%Y%m%d-%H%M%S")
    try:
        args = _read_json(os.path.join(here, ARGS_NAME))
        mode = str(args.get("mode") or "").upper()
        plan = _read_json(os.path.join(here, PLAN_NAME)) if mode == "APPLY" else None
        orig = None
        if mode == "REVERT":
            act = os.path.join(here, ACTIVE_NAME)
            core.require(os.path.exists(act), "NO_ACTIVE_ORIGINALS %s" % act)
            orig = _read_json(_read_json(act)["originals"])
        core.validate_args(args, plan, orig)
    except (core.PlanError, OSError, ValueError, KeyError) as exc:
        _stop(ops, core, run, "ARGS|%s" % exc)
    if mode == "DRY":
        run_dry(ops, core, args, run, here)
    elif mode == "APPLY":
        run_apply(ops, core, tc, args, plan, run, here)
    else:
        run_revert(ops, core, tc, args, orig, run, here)


if unreal is not None:
    main()
