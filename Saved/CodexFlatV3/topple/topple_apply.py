"""P06 STILL + CHAIN (7 Oct, offline-written, NEVER RUN BY ITS AUTHOR; DRY first ran live as TOPPLE-20261007-022206).

Gary 7 Oct (his own answers): "all of p06 can stand still leaving eerie silence except maybe one wing somewhere still
sliding towards the back"; the fall "just before sun goes dusk and be dusk lit" / "Middle, still lit"; "Keep going with
6". Variant C: a domino chain falling AWAY from the camera.

Run only through topple_run.py (purges cached Saved modules, then runs this file) with topple_args.json:
  DRY     {"mode": "DRY", "confirm": "DRY TOPPLE P06"}                                          read-only, CLEAN census
          FIRST every Passage's MechanismSound set -> topple_mechanism_sounds_<run>.json, then P06 ->
          topple_measurements.json (+ topple_dry_<run>.json). FLATV3_TOPPLE_MECHSOUND_DONE / FLATV3_TOPPLE_DRY_OK|run=..
  offline python make_keys.py --slam-s <P06 s> [...]   -> topple_plan.json (STILL + CHAIN) + the exact APPLY confirm
  APPLY   {"mode": "APPLY", "confirm": "APPLY TOPPLE <token>", "decided_by": "Gary ..."} (+ "pose_probe": false to
          skip the in-editor pose probe; + "ack_next_row_intersection": true for --end floor)   Show + level write
  REVERT  {"mode": "REVERT", "confirm": "REVERT TOPPLE <apply run id>"}   restores every written row from the originals
          (FIELD-SCOPED since 7 Oct: only Mechanism + LocalOverrideMask are restored and compared; see run_revert)
One APPLY carries both parts (make_keys --parts still,chain | still | chain); a second APPLY is refused until REVERT,
so REVERT always undoes exactly one APPLY.
Markers: FLATV3_TOPPLE_<MODE>_OK|run=<id>|..  /  FLATV3_TOPPLE_STOPPED|run=<id>|reason=..   (parse by run id)

Tiers per claim: [decl] header/source we can read (cited), [bin] installed DLL strings, [prec] in-repo precedent call,
[meas] read back from a live run (cited), [inf] inferred (why).

STILL: PlaybackMode=Static, PhaseOffsetCycles=0 on every P06 row except the keeper and the chain rows. Static evaluates
  each side's curve at Phase = PhaseOffsetCycles (+ the section's Wing.PhaseBiasCycles), no time term [decl
  InfinityStagePassageActor.cpp:1410-1428]; the curve value is then the slide / angle fraction (:1459-1475). So
  "Static" alone is NOT rest: the live rows carry offsets like 0.333 on the undulation curve, i.e. a held 75 % slide
  [meas: hermite on the live exports of TOPPLE-20261007-022206; engine eval == our Hermite within 9e-8 in its
  api_probe]. Offset 0 gives curve(0) = 0 on the preset curve (keys 0/0.25/0.5/0.75/1 -> 0/.5/1/.5/0 [decl
  InfinityStageShowAsset.cpp:22-29]); APPLY reads curve(0) back from the engine for L, R and Top, then proves rest in
  the level: after materialize it evaluates the mechanisms at segment-relative frames and requires every STILL panel
  within 0.5 cm of its BaseWorldTransform, re-materializes, and requires every P06 panel at rest before saving.
  Curves and Kind are left untouched (REVERT is a pure restore). Wing.PhaseBiasCycles is measured neutral in DRY.
CHAIN (falling side only): Kind=Topple, OneShot, PhaseOrigin=PassFrame (no absolute Master frame is authored; the
  conductor: P02 was retimed 7 Oct so P06 moved 132 s), CycleRateHz, PhaseOffsetCycles, MaxAngleDeg=-90 (negative =
  away [decl Types.h:665-674]), the side's NormalizedCurve keys (cubic; RCTM_Break at impacts, RCTM_User elsewhere),
  the OTHER side's curve set to an explicit zero curve (Kind/PlaybackMode are per row [decl Types.h:647-674], so it
  would otherwise topple along its old undulation), bTopFollowsMechanism=false with a Top [decl .cpp:155-165,
  :1436-1448]. The pose probe also checks the falling side: at rest one second before the creak, and after rest
  tilted by its solved final angle with its top moved AWAY along the route (the sign of MaxAngleDeg, measured).
  LocalOverrideMask unchanged by default (MechanismPhase only affects ContinuousLoop under the live pattern [decl
  .cpp:1412-1417]; MechanismRate has no reader in plugin source); "override_flags": true ORs both bits in.
HOW THE CURVE IS WRITTEN: EditorCurveData is UPROPERTY() without Edit/BP [decl CurveFloat.h:16-17] -> StructBase
  .import_text on a new RuntimeFloatCurve [bin PythonScriptPlugin.dll], then set_editor_property. DRY's api_probe
  measured it live (TOPPLE-20261007-022206: round trip exact, engine vs Hermite 9.3e-8, mech round trip equal).
SAFETY (house pattern: p6_ceiling_off.py [prec, ran 4 Oct], curtain_image.py, p06_sunset.py [prec, ran 7 Oct]):
  no PIE (never ends it); expected world; census CLEAN at start in every mode; no ZZ_ actors before a save; the plan's
  inputs_hash (every P06 row's mechanism + the chain's measured geometry + route law + modulation) == live; originals
  JSON fsynced and logged BEFORE any change; Backups/PreP06Topple-<stamp> copies of the Show .uasset and level .umap;
  every field read back; non-target cues byte-identical; targets unchanged outside the planned fields; only the P06
  Passage actor materialized; dirty set within {Show, level}; save those two only (never Save All); read back after
  save; success marker last. No unreal objects in module globals; never reload the level; no Sequencer open/scrub
  (the Master is only loaded to read its P06 section's channels and start time).
"""
import datetime
import hashlib
import importlib.util
import json
import math
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None

ARGS_NAME = "topple_args.json"
MEAS_NAME = "topple_measurements.json"
PLAN_NAME = "topple_plan.json"
ACTIVE_NAME = "topple_originals_ACTIVE.json"


def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                            "CodexFlatV3", "topple")
    return os.path.dirname(os.path.abspath(__file__))


def _load_core():
    """Loaded by path under a private name and NOT registered in sys.modules: never stale (memory
    ue58-python-stale-module-cache)."""
    spec = importlib.util.spec_from_file_location("topple_core_live", os.path.join(_here(), "topple_core.py"))
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
# Unreal access (everything that touches `unreal` lives here; the harness replaces this class)
# =====================================================================================================================

class UnrealOps:
    def __init__(self, core):
        self.core = core

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
            raise self.core.PlanError("WRONG_WORLD: %s" % name)

    def census(self):
        lib = unreal.EditorLoadingAndSavingUtils
        pk = lambda p: str(p.get_path_name()).split(".")[0]
        return {"content": sorted(pk(p) for p in lib.get_dirty_content_packages()),
                "maps": sorted(pk(p) for p in lib.get_dirty_map_packages())}

    def zz_actors(self):
        # GameplayStatics also lists transient actors (memory puss-bench-originals-to-file)
        actors = unreal.GameplayStatics.get_all_actors_of_class(self._world(), unreal.Actor)
        return sorted(str(a.get_actor_label()) for a in actors
                      if str(a.get_actor_label()).upper().startswith(("ZZ_", "TEMP")))

    # ---- helpers
    def _guid(self, g):
        return str(unreal.GuidLibrary.conv_guid_to_string(g)).upper()

    def _show(self):
        show = unreal.EditorAssetLibrary.load_asset(self.core.SHOW_PATH)
        if show is None:
            raise self.core.PlanError("SHOW_LOAD_FAIL")
        return show

    def _p06_actor(self):
        hits = [a for a in unreal.GameplayStatics.get_all_actors_of_class(self._world(), unreal.InfinityStagePassageActor)
                if self._guid(a.get_editor_property("passage_guid")) == self.core.P06_GUID]
        if len(hits) != 1:
            raise self.core.PlanError("P06_ACTOR_COUNT: %d" % len(hits))
        return hits[0]

    def _curve_prop(self, side):
        return {"L": "left_normalized_curve", "R": "right_normalized_curve", "T": "top_normalized_curve"}[side]

    def _eval(self, curve, t):
        return float(unreal.MathLibrary.get_runtime_float_curve_value(curve, float(t), 0.0))

    def _flat(self, curve):
        return max(abs(self._eval(curve, i / 100.0)) for i in range(-10, 111)) <= self.core.FLAT_EPS

    def _vec(self, v):
        return [float(v.x), float(v.y), float(v.z)]

    def _side_measure(self, mesh, ref, spline):
        core = self.core
        base = ref.get_editor_property("base_world_transform")
        scale = base.scale3d
        sx, sy, sz = abs(float(scale.x)), abs(float(scale.y)), abs(float(scale.z))
        box = mesh.get_bounding_box()
        mn, mx = box.min, box.max
        ex, ey = (float(mx.x) - float(mn.x)) / 2.0, (float(mx.y) - float(mn.y)) / 2.0
        socket = mesh.find_socket("Hinge")
        if socket is not None:
            pivot = socket.get_editor_property("relative_location")
            axis_local = unreal.MathLibrary.get_forward_vector(socket.get_editor_property("relative_rotation"))
            axis_is_x = abs(float(axis_local.x)) >= abs(float(axis_local.y))
        else:  # PassageActor.cpp:187-198: bounds centre, Min.Z, the longer SCALED horizontal extent
            pivot = unreal.Vector((float(mn.x) + float(mx.x)) / 2.0, (float(mn.y) + float(mx.y)) / 2.0, float(mn.z))
            axis_is_x = ex * sx >= ey * sy
            axis_local = unreal.Vector(1.0, 0.0, 0.0) if axis_is_x else unreal.Vector(0.0, 1.0, 0.0)
        hinge_w = base.transform_location(pivot)
        axis_w = unreal.MathLibrary.transform_direction(base, axis_local)
        up_w = unreal.MathLibrary.transform_direction(base, unreal.Vector(0.0, 0.0, 1.0))
        nrm = lambda v: [c / max(1e-9, sum(x * x for x in v) ** 0.5) for c in v]
        axis_w, up_w = nrm(self._vec(axis_w)), nrm(self._vec(up_w))
        space = unreal.SplineCoordinateSpace.WORLD
        d = float(spline.get_distance_along_spline_at_location(hinge_w, space))
        tangent = nrm(self._vec(spline.get_direction_at_distance_along_spline(d, space)))
        right = self._vec(spline.get_right_vector_at_distance_along_spline(d, space))
        origin = self._vec(spline.get_location_at_distance_along_spline(d, space))
        corners = [base.transform_location(unreal.Vector(x, y, float(mn.z)))
                   for x in (float(mn.x), float(mx.x)) for y in (float(mn.y), float(mx.y))]
        lat = [sum((c - o) * r for c, o, r in zip(self._vec(p), origin, right)) for p in corners]
        route = [float(spline.get_distance_along_spline_at_location(p, space)) for p in corners]
        pivot_ref = ref.get_editor_property("mechanism_pivot_local")
        return {"materialized": True, "has_hinge_socket": socket is not None,
                "pivot_local": self._vec(pivot), "axis_local_is_x": bool(axis_is_x),
                "ref_pivot_local": self._vec(pivot_ref.translation),
                "height_cm": (float(mx.z) - float(pivot.z)) * sz,
                "thickness_cm": 2.0 * (ey * sy if axis_is_x else ex * sx),
                "width_cm": 2.0 * (ex * sx if axis_is_x else ey * sy),
                "hinge_world": self._vec(hinge_w), "hinge_route_cm": d,
                "hinge_lateral_cm": sum((c - o) * r for c, o, r in zip(self._vec(hinge_w), origin, right)),
                "lateral_min_cm": min(lat), "lateral_max_cm": max(lat),
                "route_extent_cm": max(route) - min(route),
                "axis_dot_tangent": sum(a * t for a, t in zip(axis_w, tangent)),
                "upright": up_w[2] > 0.99, "scale": [float(scale.x), float(scale.y), float(scale.z)]}

    # ---- every Passage's MechanismSound set (read-only; conductor 7 Oct: blocker for the morning build)
    def mechanism_sounds(self):
        """FInfinityMechanismSoundSet per Passage [decl InfinityStageTypes.h:395-426; per Passage :961] plus, per
        Passage, how many rows would be voiced: rows not muted (bMuteMechanismSound [decl :737-738]) whose
        mechanism is not Static. Each Passage is read in its own try so one bad row cannot hide the rest."""
        show = self._show()
        cues = list(show.get_editor_property("cues"))
        index = {self._guid(c.get_editor_property("cue_guid")): c for c in cues}
        out = []
        for ordinal, st in enumerate(show.get_editor_property("passage_settings")):
            row = {"ordinal": ordinal}
            try:
                row["label"] = str(st.get_editor_property("label"))
                row["passage_guid"] = self._guid(st.get_editor_property("passage_guid"))
                ms = st.get_editor_property("mechanism_sound")
                sounds = list(ms.get_editor_property("sounds"))
                row.update({"enabled": bool(ms.get_editor_property("enabled")), "sound_count": len(sounds),
                            "sounds": [None if s is None else str(s.get_path_name()).split(".")[0] for s in sounds],
                            "policy": str(ms.get_editor_property("policy")),
                            "gain": float(ms.get_editor_property("gain")),
                            "audible_radius_cm": float(ms.get_editor_property("audible_radius_cm")),
                            "movement_threshold": float(ms.get_editor_property("movement_threshold"))})
                guids = [self._guid(g) for g in show.get_wing_pair_cue_guids_in_passage(st.get_editor_property("passage_guid"))]
                muted = moving = moving_unmuted = 0
                for g in guids:
                    pair = index[g].get_editor_property("wing_pair")
                    m = bool(pair.get_editor_property("mute_mechanism_sound"))
                    mv = "STATIC" not in str(pair.get_editor_property("mechanism").get_editor_property(
                        "playback_mode")).upper()
                    muted += m
                    moving += mv
                    moving_unmuted += mv and not m
                row.update({"wing_rows": len(guids), "muted_rows": muted, "non_static_rows": moving,
                            "non_static_unmuted_rows": moving_unmuted,
                            "would_sound": bool(row["enabled"] and row["sound_count"] > 0 and moving_unmuted > 0)})
            except Exception as exc:  # noqa: BLE001  -- recorded per Passage, never swallowed silently
                row["error"] = "%s: %s" % (type(exc).__name__, exc)
            out.append(row)
        return out

    # ---- measurement (read-only)
    def measure(self):
        core = self.core
        show = self._show()
        settings = [s for s in show.get_editor_property("passage_settings")
                    if self._guid(s.get_editor_property("passage_guid")) == core.P06_GUID]
        if len(settings) != 1:
            raise core.PlanError("P06_SETTINGS_COUNT: %d" % len(settings))
        st = settings[0]
        label = str(st.get_editor_property("label"))
        tr = show.get_editor_property("tick_resolution")
        tick = float(tr.numerator) / float(tr.denominator)
        guids = [self._guid(g) for g in show.get_wing_pair_cue_guids_in_passage(st.get_editor_property("passage_guid"))]
        cues = list(show.get_editor_property("cues"))
        index = {self._guid(c.get_editor_property("cue_guid")): i for i, c in enumerate(cues)}
        missing = [g for g in guids if g not in index]
        if missing or not guids:
            raise core.PlanError("P06_CUES_UNRESOLVED: %s" % missing[:3])
        actor = self._p06_actor()
        spline = actor.get_editor_property("route")
        refs = {}
        for ref in actor.get_editor_property("materialized_panels"):
            side = str(ref.get_editor_property("side")).upper()
            key = (self._guid(ref.get_editor_property("cue_guid")), "L" if "LEFT" in side else "R" if "RIGHT" in side else "T")
            refs.setdefault(key, []).append(ref)
        rows, law_rows = [], []
        for ordinal, g in enumerate(guids):
            cue = cues[index[g]]
            pair = cue.get_editor_property("wing_pair")
            mech = pair.get_editor_property("mechanism")
            mech_text = mech.export_text()
            mask = int(pair.get_editor_property("local_override_mask"))
            playback = str(mech.get_editor_property("playback_mode"))
            offset = float(mech.get_editor_property("phase_offset_cycles"))
            law_rows.append((int(pair.get_editor_property("interval_to_next").value),
                             float(pair.get_editor_property("gap_to_next_cm"))))
            sides, curve_at0 = {}, {}
            for side, prop in (("L", "left"), ("R", "right")):
                panel = pair.get_editor_property(prop)
                mesh = panel.get_editor_property("mesh")
                curve = mech.get_editor_property(self._curve_prop(side))
                ctext = curve.export_text()
                entry = {"mesh": None if mesh is None else str(mesh.get_path_name()).split(".")[0],
                         "curve_export": ctext, "curve_keys": len(core.parse_curve_keys(ctext)),
                         "external_curve": core.external_curve(ctext), "curve_flat": self._flat(curve),
                         "value_at_offset": self._eval(curve, offset), "materialized": False}
                curve_at0[side] = self._eval(curve, 0.0)
                if mesh is not None:
                    hit = refs.get((g, side), [])
                    if len(hit) == 1:
                        entry.update(self._side_measure(mesh, hit[0], spline))
                    else:
                        entry["materialized_refs"] = len(hit)
                        entry.update({"height_cm": 0.0, "thickness_cm": 0.0, "axis_dot_tangent": 0.0,
                                      "has_hinge_socket": False, "hinge_route_cm": 0.0})
                sides[side] = entry
            top = mech.get_editor_property("top_normalized_curve")
            curve_at0["T"] = self._eval(top, 0.0)   # Static -> Phase = PhaseOffsetCycles (PassageActor.cpp:1424-1428)
            top_mesh = pair.get_editor_property("top").get_editor_property("mesh")
            rows.append({"ordinal": ordinal, "show_index": index[g], "cue_guid": g, "label": str(cue.get_editor_property("label")),
                         "enabled": bool(cue.get_editor_property("enabled")), "has_top": bool(pair.get_editor_property("has_top")),
                         "top_mesh": None if top_mesh is None else str(top_mesh.get_path_name()).split(".")[0],
                         "local_override_mask": mask, "curve_at0": curve_at0, "top_curve_export": top.export_text(), "mechanism_sha": _sha(mech_text + "|mask=%d" % mask),
                         "mechanism_export": mech_text,
                         "mechanism": {"kind": str(mech.get_editor_property("kind")), "playback_mode": playback,
                                       "phase_origin": str(mech.get_editor_property("phase_origin")),
                                       "cycle_rate_hz": float(mech.get_editor_property("cycle_rate_hz")),
                                       "phase_offset_cycles": offset,
                                       "max_angle_deg": float(mech.get_editor_property("max_angle_deg")),
                                       "inward_travel_cm": float(mech.get_editor_property("inward_travel_cm")),
                                       "top_follows_mechanism": bool(mech.get_editor_property("top_follows_mechanism")),
                                       "top_curve_flat": self._flat(top)},
                         "sides": sides, "interval_ticks": law_rows[-1][0], "gap_cm": law_rows[-1][1]})
        law = core.route_law(int(st.get_editor_property("lead_in_frames").value),
                             float(st.get_editor_property("lead_in_distance_cm")), law_rows,
                             int(st.get_editor_property("tail_frames").value),
                             float(st.get_editor_property("tail_distance_cm")))
        for r, (pf, d) in zip(rows, law["stations"]):
            r["pass_frame"], r["station_cm"] = pf, d
        return {"passage_guid": core.P06_GUID, "passage_label": label, "tick": tick, "law": law, "rows": rows,
                "live_phase_pattern": bool(st.get_editor_property("use_live_mechanism_phase_pattern")),
                "modulation": self._modulation(st), "route_length_cm": float(spline.get_spline_length())}

    def _modulation(self, settings):
        master = unreal.EditorAssetLibrary.load_asset(self.core.MASTER_PATH)
        out = {"section_found": False}
        if master is None:
            out["wing_modulation"] = "UNKNOWN_MASTER_MISSING"
            return out
        secs = [s for t in master.get_tracks() if "InfinityPassage" in t.get_class().get_name()
                for s in t.get_sections() if self._guid(s.get_editor_property("passage_guid")) == self.core.P06_GUID]
        if len(secs) != 1:
            out["wing_modulation"] = "UNKNOWN_SECTION_COUNT_%d" % len(secs)
            return out
        sec = secs[0]
        out["section_found"] = True
        chans = {}
        for ch in sec.get_all_channels():
            name = str(ch.get_editor_property("channel_name"))
            vals = [float(k.get_value()) for k in ch.get_keys()]
            chans[name] = {"keys": len(vals), "values": sorted(set(round(v, 6) for v in vals))[:8],
                           "default": float(ch.get_default()) if ch.has_default() else None}
        out["channels"] = {k: v for k, v in chans.items() if k.startswith("Wing.") or k in (
            "Camera.SpeedMultiplier", "Camera.LongitudinalOffsetCm")}
        try:
            out["pinned_frames"] = len(sec.get_editor_property("pinned_passage_frames"))
        except Exception as exc:  # noqa: BLE001  -- reported, and treated as unknown (refused) below
            out["pinned_frames"] = "UNREADABLE: %s" % exc
        neutral = {"Wing.InwardTravelScale": 1.0, "Wing.CycleRateScale": 1.0, "Wing.PhaseBiasCycles": 0.0}
        wing = [n for n, v in chans.items() if n in neutral and (v["keys"] or (
            v["default"] is not None and abs(v["default"] - neutral[n]) > 1e-9))]
        if len([n for n in chans if n in neutral]) != 3:
            wing.append("WING_CHANNELS_NOT_ALL_FOUND")
        out["wing_modulation"] = wing or False
        sp = chans.get("Camera.SpeedMultiplier", {"values": [], "keys": 0})
        out["speed_shaped"] = (len(sp["values"]) > 1) or not isinstance(out["pinned_frames"], int) or out["pinned_frames"] > 0
        lo = chans.get("Camera.LongitudinalOffsetCm", {"values": [], "default": None})
        out["longitudinal_offset"] = any(abs(v) > 1e-6 for v in lo["values"]) or (
            lo["default"] is not None and abs(lo["default"]) > 1e-6)
        return out

    # ---- API probe on FREE-STANDING structs (nothing in the Show or level is touched)
    def api_probe(self, live_mech_text):
        core = self.core
        fails, out = [], {}
        keys = core.plan_keys(core.PROBE_SOLVER_KEYS)
        c = unreal.RuntimeFloatCurve()
        ok = bool(c.import_text(core.curve_text(keys)))
        out["curve_import_returned"] = ok
        text = c.export_text()
        out["curve_export"] = text
        diffs = core.keys_match(keys, core.parse_curve_keys(text))
        out["curve_roundtrip_diffs"] = diffs
        errs = [abs(self._eval(c, ph) - core.hermite(keys, ph)) for ph in core.sample_phases(keys)]
        out["engine_vs_hermite_max_err"] = max(errs)
        m = unreal.InfinityMechanismMotion()
        out["mech_import_returned"] = bool(m.import_text(live_mech_text))
        out["mech_roundtrip_equal"] = m.export_text() == live_mech_text
        names = ("kind", "playback_mode", "cycle_rate_hz", "phase_origin", "phase_offset_cycles", "max_angle_deg",
                 "left_normalized_curve", "right_normalized_curve", "top_normalized_curve", "top_follows_mechanism")
        missing = []
        for n in names:
            try:
                m.get_editor_property(n)
            except Exception:  # noqa: BLE001
                missing.append(n)
        out["missing_properties"] = missing
        m.set_editor_property("left_normalized_curve", c)
        out["set_curve_readback_diffs"] = core.keys_match(keys, core.parse_curve_keys(
            m.get_editor_property("left_normalized_curve").export_text()))
        for cond, why in ((ok, "CURVE_IMPORT_FALSE"), (not diffs, "CURVE_ROUNDTRIP"),
                          (out["engine_vs_hermite_max_err"] <= core.EVAL_TOL, "ENGINE_EVAL_DIFFERS_FROM_HERMITE"),
                          (out["mech_import_returned"] and out["mech_roundtrip_equal"], "MECH_ROUNDTRIP"),
                          (not missing, "MISSING_PROPERTIES"), (not out["set_curve_readback_diffs"], "SET_CURVE_READBACK"),
                          ("EditorCurveData" in text, "EXPORT_LACKS_EditorCurveData")):
            if not cond:
                fails.append(why)
        out["failures"] = fails
        out["pass"] = not fails
        return out

    # ---- reads used by APPLY/REVERT read-back
    def cue_texts(self):
        return [c.export_text() for c in self._show().get_editor_property("cues")]

    def read_row(self, guid):
        cues = list(self._show().get_editor_property("cues"))
        hit = [c for c in cues if self._guid(c.get_editor_property("cue_guid")) == guid]
        if len(hit) != 1:
            raise self.core.PlanError("CUE_GUID_COUNT %s %d" % (guid, len(hit)))
        pair = hit[0].get_editor_property("wing_pair")
        mech = pair.get_editor_property("mechanism")
        return {"mech_text": mech.export_text(), "mask": int(pair.get_editor_property("local_override_mask")),
                "kind": str(mech.get_editor_property("kind")), "playback_mode": str(mech.get_editor_property("playback_mode")),
                "phase_origin": str(mech.get_editor_property("phase_origin")),
                "cycle_rate_hz": float(mech.get_editor_property("cycle_rate_hz")),
                "phase_offset_cycles": float(mech.get_editor_property("phase_offset_cycles")),
                "max_angle_deg": float(mech.get_editor_property("max_angle_deg")),
                "top_follows_mechanism": bool(mech.get_editor_property("top_follows_mechanism")),
                "has_top": bool(pair.get_editor_property("has_top")),
                "curves": {s: mech.get_editor_property(self._curve_prop(s)).export_text() for s in ("L", "R", "T")}}

    def curve_eval(self, guid, side, phases):
        cues = list(self._show().get_editor_property("cues"))
        cue = [c for c in cues if self._guid(c.get_editor_property("cue_guid")) == guid][0]
        curve = cue.get_editor_property("wing_pair").get_editor_property("mechanism").get_editor_property(
            self._curve_prop(side))
        return [self._eval(curve, p) for p in phases]

    # ---- writes
    def _enum(self, cls, name):
        return getattr(cls, name)

    def _import_curve(self, text, label):
        curve = unreal.RuntimeFloatCurve()
        if not curve.import_text(text):
            raise self.core.PlanError("CURVE_IMPORT_FALSE %s" % label)
        return curve

    def write_rows(self, plan_rows, override_bits):
        """plan_rows: action "still" (Static + PhaseOffsetCycles 0) or "chain" (topple fields, the side's keys, the
        other side's zero curve, bTopFollowsMechanism false with a Top). One modify + one set of the cue array."""
        core = self.core
        show = self._show()
        cues = list(show.get_editor_property("cues"))
        index = {self._guid(c.get_editor_property("cue_guid")): i for i, c in enumerate(cues)}
        for row in plan_rows:
            i = index[row["cue_guid"]]
            cue = cues[i]
            pair = cue.get_editor_property("wing_pair")
            mech = pair.get_editor_property("mechanism")
            s = row["set"]
            mech.set_editor_property("playback_mode", self._enum(unreal.InfinityMotionPlaybackMode, s["playback_mode"]))
            mech.set_editor_property("phase_offset_cycles", float(s["phase_offset_cycles"]))
            if row["action"] == "chain":
                mech.set_editor_property("kind", self._enum(unreal.InfinityMechanismKind, s["kind"]))
                mech.set_editor_property("phase_origin", self._enum(unreal.InfinityMotionPhaseOrigin, s["phase_origin"]))
                mech.set_editor_property("cycle_rate_hz", float(s["cycle_rate_hz"]))
                mech.set_editor_property("max_angle_deg", float(s["max_angle_deg"]))
                mech.set_editor_property(self._curve_prop(row["side"]), self._import_curve(row["curve_text"], row["label"]))
                mech.set_editor_property(self._curve_prop(row["other_side"]),
                                         self._import_curve(row["other_curve_text"], row["label"]))
                if s.get("top_follows_mechanism") is False:
                    mech.set_editor_property("top_follows_mechanism", False)
                if override_bits:
                    pair.set_editor_property("local_override_mask",
                                             int(pair.get_editor_property("local_override_mask")) | int(override_bits))
            pair.set_editor_property("mechanism", mech)
            cue.set_editor_property("wing_pair", pair)
            cues[i] = cue
        show.modify()
        show.set_editor_property("cues", cues)

    def restore_rows(self, orig_rows):
        core = self.core
        show = self._show()
        cues = list(show.get_editor_property("cues"))
        index = {self._guid(c.get_editor_property("cue_guid")): i for i, c in enumerate(cues)}
        for row in orig_rows:
            i = index[row["cue_guid"]]
            cue = cues[i]
            pair = cue.get_editor_property("wing_pair")
            mech = unreal.InfinityMechanismMotion()
            if not mech.import_text(row["mech_text"]) or mech.export_text() != row["mech_text"]:
                raise core.PlanError("ORIGINAL_MECH_IMPORT_MISMATCH %s" % row["label"])
            pair.set_editor_property("mechanism", mech)
            pair.set_editor_property("local_override_mask", int(row["mask"]))
            cue.set_editor_property("wing_pair", pair)
            cues[i] = cue
        show.modify()
        show.set_editor_property("cues", cues)

    def materialize(self):
        return bool(self._p06_actor().materialize_passage())

    def materialized_pivots(self, guids, side):
        out = {}
        for ref in self._p06_actor().get_editor_property("materialized_panels"):
            g = self._guid(ref.get_editor_property("cue_guid"))
            s = str(ref.get_editor_property("side")).upper()
            s = "L" if "LEFT" in s else "R" if "RIGHT" in s else "T"
            if g in guids and s == side:
                out.setdefault(g, []).append(self._vec(ref.get_editor_property("mechanism_pivot_local").translation))
        return out

    def _section_start_frame(self):
        """Absolute Master frame of the P06 section start: READ ONLY, drives the pose probe, never authored.
        get_start_frame_seconds as in p01_note_lamps.py:1098 [prec]."""
        master = unreal.EditorAssetLibrary.load_asset(self.core.MASTER_PATH)
        secs = [x for t in master.get_tracks() if "InfinityPassage" in t.get_class().get_name()
                for x in t.get_sections() if self._guid(x.get_editor_property("passage_guid")) == self.core.P06_GUID]
        if len(secs) != 1:
            raise self.core.PlanError("P06_SECTION_COUNT %d" % len(secs))
        tr = self._show().get_editor_property("tick_resolution")
        return int(round(float(secs[0].get_start_frame_seconds()) * float(tr.numerator) / float(tr.denominator)))

    def instance_state(self, guids):
        """Per "guid|side" panel: max corner deviation (cm) of the ISM instance from its rest BaseWorldTransform,
        tilt (deg) between their up axes, route-distance shift (cm) of the top centre. Points, not FTransform
        equality (mirrored ISM read-back, memory ue58-ism-readback-and-test-traps)."""
        actor = self._p06_actor()
        spline = actor.get_editor_property("route")
        space = unreal.SplineCoordinateSpace.WORLD
        out = {}
        for ref in actor.get_editor_property("materialized_panels"):
            g = self._guid(ref.get_editor_property("cue_guid"))
            if g not in guids:
                continue
            s = str(ref.get_editor_property("side")).upper()
            s = "L" if "LEFT" in s else "R" if "RIGHT" in s else "T"
            comp = ref.get_editor_property("component")
            idx = int(ref.get_editor_property("instance_index"))
            base = ref.get_editor_property("base_world_transform")
            inst = comp.get_instance_transform(idx, True)   # bool + one out param -> the out value only (memory)
            if inst is None:
                out["%s|%s" % (g, s)] = {"error": "GET_INSTANCE_TRANSFORM_NONE"}
                continue
            box = comp.get_editor_property("static_mesh").get_bounding_box()
            pts = [unreal.Vector(x, y, z) for x in (box.min.x, box.max.x) for y in (box.min.y, box.max.y)
                   for z in (box.min.z, box.max.z)]
            dev = max((base.transform_location(p) - inst.transform_location(p)).length() for p in pts)
            up_b = unreal.MathLibrary.transform_direction(base, unreal.Vector(0, 0, 1)).normal()
            up_i = unreal.MathLibrary.transform_direction(inst, unreal.Vector(0, 0, 1)).normal()
            dot = max(-1.0, min(1.0, float(up_b.dot(up_i))))
            top = unreal.Vector((box.min.x + box.max.x) / 2, (box.min.y + box.max.y) / 2, box.max.z)
            shift = float(spline.get_distance_along_spline_at_location(inst.transform_location(top), space)) - float(
                spline.get_distance_along_spline_at_location(base.transform_location(top), space))
            out["%s|%s" % (g, s)] = {"dev_cm": float(dev), "tilt_deg": math.degrees(math.acos(dot)),
                                     "top_route_shift_cm": shift}
        return out

    def pose_probe(self, guids, frames_rel):
        """EvaluateMechanismsAtMasterFrame [decl PassageActor.h:179] at segment-relative frames -> instance state per
        frame. The caller re-materializes afterwards to put every instance back at rest."""
        actor = self._p06_actor()
        start = self._section_start_frame()
        out = {}
        for f in frames_rel:
            ok = bool(actor.evaluate_mechanisms_at_master_frame(unreal.FrameNumber(int(start + int(f)))))
            out[str(int(f))] = {"evaluated": ok, "panels": self.instance_state(guids)}
        return out

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


def _guard_start(ops, core, run, need_clean=True):
    try:
        ops.guard_context()
    except core.PlanError as exc:
        _stop(ops, core, run, str(exc))
    c = ops.census()
    if need_clean and c != {"content": [], "maps": []}:
        _stop(ops, core, run, "DIRTY_CENSUS (another stream's unsaved work? refused) %s" % json.dumps(c))


def run_dry(ops, core, args, run, here):
    _guard_start(ops, core, run)
    # FIRST: every Passage's mechanism-sound set, written to its own file before any P06 work can fail
    try:
        sounds = {"ok": True, "passages": ops.mechanism_sounds()}
    except Exception as exc:  # noqa: BLE001
        sounds = {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc), "passages": []}
    sounds["run_id"] = run
    sounds_path = os.path.join(here, "topple_mechanism_sounds_%s.json" % run)
    _write_json(sounds_path, sounds)
    for p in sounds["passages"]:
        ops.log("%s_MECHSOUND|run=%s|passage=%s|enabled=%s|sounds=%s|policy=%s|non_static_unmuted=%s|would_sound=%s%s" % (
            core.MARK, run, p.get("label"), p.get("enabled"), p.get("sound_count"), p.get("policy"),
            p.get("non_static_unmuted_rows"), p.get("would_sound"), "|error=" + p["error"] if "error" in p else ""))
    ops.log("%s_MECHSOUND_DONE|run=%s|ok=%s|passages=%d|errors=%d|path=%s" % (
        core.MARK, run, sounds["ok"], len(sounds["passages"]), sum("error" in p for p in sounds["passages"]), sounds_path))
    meas = ops.measure()
    meas = dict([("mechanism_sounds", sounds)] + list(meas.items()))
    if not meas["rows"]:
        _stop(ops, core, run, "P06_NO_ROWS")
    probe = ops.api_probe(meas["rows"][0]["mechanism_export"])
    tick = meas["tick"]
    keeper = core.default_keeper(meas["rows"], tick)
    keeper_guid = keeper["cue_guid"] if keeper else None
    wins, refusal_counts = core.eligible_windows(meas["rows"], core.N_ROWS, keeper_guid)
    still, still_ref = core.still_plan(meas["rows"], keeper_guid, set())
    meas.update({"run_id": run, "made": datetime.datetime.now().isoformat(timespec="seconds"), "api_probe": probe,
                 "proposed_keeper": None if keeper is None else {
                     "cue_guid": keeper_guid, "label": keeper["label"], "ordinal": keeper["ordinal"],
                     "pass_s": round(keeper["pass_frame"] / tick, 2)},
                 "candidates": wins, "eligible_windows": len(wins), "window_refusal_counts": refusal_counts,
                 "still_preview": {"counts": {a: sum(1 for x in still if x["action"] == a)
                                              for a in ("still", "already_still", "keep")}, "refusals": still_ref},
                 "table": [{"ordinal": r["ordinal"], "show_index": r["show_index"], "label": r["label"],
                            "L": r["sides"]["L"].get("mesh"), "R": r["sides"]["R"].get("mesh"),
                            "L_h_t_cm": [round(r["sides"]["L"].get("height_cm", 0), 1), round(r["sides"]["L"].get("thickness_cm", 0), 1)],
                            "R_h_t_cm": [round(r["sides"]["R"].get("height_cm", 0), 1), round(r["sides"]["R"].get("thickness_cm", 0), 1)],
                            "top": r["has_top"], "kind": r["mechanism"]["kind"], "playback": r["mechanism"]["playback_mode"],
                            "offset": r["mechanism"].get("phase_offset_cycles"), "curve_at0": r.get("curve_at0"),
                            "station_cm": round(r["station_cm"], 1), "pass_s": round(r["pass_frame"] / tick, 3)}
                           for r in meas["rows"]]})
    end = ops.census()
    meas["dry_ok"] = bool(probe["pass"]) and end == {"content": [], "maps": []}
    _write_json(os.path.join(here, "topple_dry_%s.json" % run), meas)
    _write_json(os.path.join(here, MEAS_NAME), meas)
    if end != {"content": [], "maps": []}:
        _stop(ops, core, run, "DRY_DIRTIED_SOMETHING %s (do not save; report)" % json.dumps(end))
    if not probe["pass"]:
        _stop(ops, core, run, "API_PROBE_FAILED %s (curve keys cannot be written from Python this way: STOP, see "
                              "topple_dry_%s.json api_probe)" % (probe["failures"], run))
    ops.log("%s_DRY_OK|run=%s|rows=%d|eligible_windows=%d|keeper=%s|still=%s|probe=PASS|path=%s" % (
        core.MARK, run, len(meas["rows"]), len(wins), None if keeper is None else keeper["label"],
        meas["still_preview"]["counts"], os.path.join(here, MEAS_NAME)))
    return meas


def _live_window(core, meas, plan):
    c = plan.get("chain")
    keeper = (plan.get("keeper") or {}).get("cue_guid")
    if not c:
        return None, keeper
    start = [r["cue_guid"] for r in meas["rows"]].index(c["rows"][0]["cue_guid"])
    return core.window_report(meas["rows"], start, c["side"], c["n"], keeper), keeper


def _check_rows(ops, core, write_rows, before_rows, override_bits):
    """Read back every planned field + the engine's own curve evaluation. [] = good."""
    bad = []
    for row in write_rows:
        live = ops.read_row(row["cue_guid"])
        before = before_rows[row["cue_guid"]]
        s = row["set"]
        if s["playback_mode"] not in str(live["playback_mode"]).upper():
            bad.append("%s playback_mode=%s want %s" % (row["label"], live["playback_mode"], s["playback_mode"]))
        if abs(float(live["phase_offset_cycles"]) - float(s["phase_offset_cycles"])) > 1e-9 * max(
                1.0, abs(float(s["phase_offset_cycles"]))):
            bad.append("%s phase_offset_cycles=%r want %r" % (row["label"], live["phase_offset_cycles"],
                                                               s["phase_offset_cycles"]))
        if core.mechanism_outside_planned(live["mech_text"], row["action"]) != core.mechanism_outside_planned(
                before["mech_text"], row["action"]):
            bad.append("%s MECHANISM_CHANGED_OUTSIDE_PLAN" % row["label"])
        if row["action"] == "still":
            if live["mask"] != before["mask"]:
                bad.append("%s mask changed" % row["label"])
            for side in ("L", "R", "T"):
                v = ops.curve_eval(row["cue_guid"], side, [0.0])[0]
                if abs(v) > core.FLAT_EPS:
                    bad.append("%s STILL_NOT_AT_REST %s curve(0)=%.5f" % (row["label"], side, v))
            continue
        for f, want in (("kind", s["kind"]), ("phase_origin", s["phase_origin"])):
            if want not in str(live[f]).upper():
                bad.append("%s %s=%s want %s" % (row["label"], f, live[f], want))
        for f in ("cycle_rate_hz", "max_angle_deg"):
            if abs(float(live[f]) - float(s[f])) > 1e-9 * max(1.0, abs(float(s[f]))):
                bad.append("%s %s=%r want %r" % (row["label"], f, live[f], s[f]))
        if s.get("top_follows_mechanism") is False and live["top_follows_mechanism"]:
            bad.append("%s top_follows_mechanism still True" % row["label"])
        if live["mask"] != (before["mask"] | override_bits):
            bad.append("%s mask %d want %d" % (row["label"], live["mask"], before["mask"] | override_bits))
        bad += ["%s %s" % (row["label"], d) for d in core.keys_match(row["keys"], core.parse_curve_keys(live["curves"][row["side"]]))]
        bad += ["%s other %s" % (row["label"], d) for d in core.keys_match(row["other_keys"], core.parse_curve_keys(
            live["curves"][row["other_side"]]))]
        if live["curves"]["T"] != before["curves"]["T"]:
            bad.append("%s TOP_CURVE_CHANGED" % row["label"])
        phases = [p for p, _ in row["samples"]]
        got = ops.curve_eval(row["cue_guid"], row["side"], phases)
        err = max(abs(g - v) for g, (_, v) in zip(got, row["samples"]))
        if err > core.EVAL_TOL:
            bad.append("%s ENGINE_EVAL_ERR %.5f" % (row["label"], err))
    return bad


POSE_TOL_CM = 0.5
TILT_TOL_DEG = 1.5


def _probe_frames(plan):
    seg = plan["inputs"]["segment_end"]
    tick = plan["inputs"]["tick"]
    frames = {"mid": seg // 2, "early": seg // 10, "late": (seg * 9) // 10}
    c = plan.get("chain")
    if c:
        tm = c["timing"]
        frames["pre_creak"] = max(0, int(tm["creak_frame_rel"] - tick))
        frames["after_rest"] = min(seg, int(tm["rest_s"] * tick + tick / 2))
    return frames


def _judge_pose(plan, probe, still_guids, frames):
    """STILL rows (all sides) at rest in every frame; chain falling side at rest before the creak and tilted by its
    final angle, top moved AWAY along the route, after rest; chain other side at rest throughout. Keeper unchecked."""
    bad = []
    chain = plan.get("chain") or {"rows": []}
    final = {r["cue_guid"]: (r["side"], abs(r["final_deg"])) for r in chain["rows"]}
    for name, f in frames.items():
        st = probe[str(int(f))]
        if not st["evaluated"]:
            bad.append("EVALUATE_FALSE at %s (frame %d outside the P06 segment?)" % (name, f))
            continue
        for key, v in st["panels"].items():
            g, side = key.split("|")
            if "error" in v:
                bad.append("%s %s %s" % (name, key, v["error"]))
                continue
            if g in still_guids or (g in final and side != final[g][0]):
                if v["dev_cm"] > POSE_TOL_CM:
                    bad.append("%s NOT_AT_REST %s dev %.2f cm" % (name, key, v["dev_cm"]))
            elif g in final:
                if name == "pre_creak" and v["dev_cm"] > POSE_TOL_CM:
                    bad.append("pre_creak CHAIN_MOVED_EARLY %s dev %.2f cm" % (key, v["dev_cm"]))
                if name == "after_rest":
                    if abs(v["tilt_deg"] - final[g][1]) > TILT_TOL_DEG:
                        bad.append("after_rest CHAIN_TILT %s %.1f want %.1f deg" % (key, v["tilt_deg"], final[g][1]))
                    if v["top_route_shift_cm"] <= 0:
                        bad.append("after_rest CHAIN_FELL_TOWARD_CAMERA %s shift %.0f cm" % (key, v["top_route_shift_cm"]))
    return bad


def run_apply(ops, core, args, plan, run, here):
    _guard_start(ops, core, run)
    if ops.zz_actors():
        _stop(ops, core, run, "ZZ_OR_TEMP_ACTORS_IN_LEVEL %s (another stream's bench; a level save would keep it)"
              % ops.zz_actors())
    if os.path.exists(os.path.join(here, ACTIVE_NAME)):
        _stop(ops, core, run, "UNREVERTED_APPLY_EXISTS %s (REVERT it first)" % _read_json(os.path.join(here, ACTIVE_NAME)))
    meas = ops.measure()
    win, keeper = _live_window(core, meas, plan)
    if win is not None and win["refusals"]:
        _stop(ops, core, run, "WINDOW_REFUSED_LIVE %s" % win["refusals"])
    live_inputs = core.inputs_for(meas, win, keeper)
    if core.inputs_hash(live_inputs) != plan["inputs_hash"]:
        _stop(ops, core, run, "PLAN_STALE: live measurement hash differs from topple_plan.json (re-run DRY + make_keys)")
    if any(meas["modulation"].get(k) for k in ("wing_modulation", "speed_shaped", "longitudinal_offset")):
        _stop(ops, core, run, "MODULATION_LIVE %s" % json.dumps(meas["modulation"]))
    still_live, still_ref = (core.still_plan(meas["rows"], keeper, {r["cue_guid"] for r in (plan.get("chain") or {"rows": []})["rows"]})
                             if "still" in plan["parts"] else ([], []))
    if still_ref:
        _stop(ops, core, run, "STILL_REFUSED_LIVE %s" % still_ref[:4])
    if [(x["cue_guid"], x["action"]) for x in still_live] != [(x["cue_guid"], x["action"]) for x in plan["still"]]:
        _stop(ops, core, run, "STILL_PLAN_DIFFERS_LIVE")
    probe = ops.api_probe(meas["rows"][0]["mechanism_export"])
    if not probe["pass"]:
        _stop(ops, core, run, "API_PROBE_FAILED %s" % probe["failures"])
    write = [x for x in plan["still"] if x["action"] == "still"] + list((plan.get("chain") or {"rows": []})["rows"])
    if not write:
        ops.log("%s_APPLY_NOOP|run=%s|nothing to write" % (core.MARK, run))
        return {}
    guids = [r["cue_guid"] for r in write]
    by_guid = {r["cue_guid"]: r for r in meas["rows"]}
    bits = (core.OVERRIDE_MECHANISM_RATE | core.OVERRIDE_MECHANISM_PHASE) if args.get("override_flags") else 0
    texts_before = ops.cue_texts()
    before_rows = {g: ops.read_row(g) for g in guids}
    for r in write:   # the read-back comparison must be computable BEFORE anything is written
        core.cue_text_outside_mechanism(texts_before[by_guid[r["cue_guid"]]["show_index"]])
        core.mechanism_outside_planned(before_rows[r["cue_guid"]]["mech_text"], r["action"])
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    backup_dir, backup_files = ops.backup("PreP06Topple-%s" % stamp)
    orig_path = os.path.join(here, "topple_originals_%s.json" % run)
    if os.path.exists(orig_path):
        _stop(ops, core, run, "ORIGINALS_EXIST %s" % orig_path)
    originals = {"run_id": run, "made": datetime.datetime.now().isoformat(timespec="seconds"),
                 "backup_dir": backup_dir, "backup_files": backup_files, "parts": plan["parts"],
                 "plan_inputs_hash": plan["inputs_hash"], "decided_by": args.get("decided_by"), "override_bits": bits,
                 "rows": [{"cue_guid": g, "label": by_guid[g]["label"], "show_index": by_guid[g]["show_index"],
                           "action": r["action"], "mech_text": before_rows[g]["mech_text"], "mask": before_rows[g]["mask"],
                           "cue_text": texts_before[by_guid[g]["show_index"]]} for g, r in zip(guids, write)]}
    _write_json(orig_path, originals, fsync=True)
    _write_json(os.path.join(here, ACTIVE_NAME), {"run_id": run, "originals": orig_path}, fsync=True)
    ops.log("%s_ORIGINALS|run=%s|path=%s|backup=%s|rows=%d" % (core.MARK, run, orig_path, backup_dir, len(write)))
    ops.write_rows(write, bits)
    texts_after = ops.cue_texts()
    bad = []
    if len(texts_after) != len(texts_before):
        bad.append("CUE_COUNT_CHANGED")
    targets = {by_guid[g]["show_index"] for g in guids}
    for i, (a, b) in enumerate(zip(texts_before, texts_after)):
        if i in targets:
            if core.cue_text_outside_mechanism(a) != core.cue_text_outside_mechanism(b):
                bad.append("TARGET_CUE_CHANGED_OUTSIDE_MECHANISM index %d" % i)
        elif a != b:
            bad.append("NONTARGET_CUE_CHANGED index %d" % i)
    bad += _check_rows(ops, core, write, before_rows, bits)
    if bad:
        try:
            ops.restore_rows(originals["rows"])
            now = ops.cue_texts()
            restored = all(now[r["show_index"]] == r["cue_text"] for r in originals["rows"])
        except Exception as exc:  # noqa: BLE001
            restored = "RESTORE_RAISED %s" % exc
        _stop(ops, core, run, "READBACK_FAILED %s | in-memory restore=%s | NOTHING SAVED: the Show package is dirty; "
                              "do not save it -- relaunch with Don't Save, then rename %s (disk is unchanged)"
              % (bad[:6], restored, ACTIVE_NAME))
    if not ops.materialize():
        _stop(ops, core, run, "MATERIALIZE_FAILED (Show dirty, unsaved: relaunch with Don't Save)")
    c = plan.get("chain")
    if c:
        pivots = ops.materialized_pivots({r["cue_guid"] for r in c["rows"]}, c["side"])
        for r in c["rows"]:
            want = by_guid[r["cue_guid"]]["sides"][c["side"]]["pivot_local"]
            got = pivots.get(r["cue_guid"], [])
            if len(got) != 1 or max(abs(a - b) for a, b in zip(got[0], want)) > 0.01:
                _stop(ops, core, run, "PIVOT_READBACK %s got %s want %s" % (r["label"], got, want))
    p06 = {r["cue_guid"] for r in meas["rows"]}
    still_guids = {x["cue_guid"] for x in plan["still"] if x["action"] in ("still", "already_still")}
    pose = {}
    if args.get("pose_probe", True):
        frames = _probe_frames(plan)
        pose = ops.pose_probe(p06, sorted(set(frames.values())))
        bad = _judge_pose(plan, pose, still_guids, frames)
        if not ops.materialize():
            _stop(ops, core, run, "REMATERIALIZE_AFTER_PROBE_FAILED")
        if bad:
            _stop(ops, core, run, "POSE_PROBE_FAILED %s (Show dirty, unsaved: relaunch with Don't Save)" % bad[:6])
    rest = ops.instance_state(p06)
    off = [k for k, v in rest.items() if "error" in v or v["dev_cm"] > POSE_TOL_CM]
    if off:
        _stop(ops, core, run, "MATERIALIZED_NOT_AT_REST %s" % off[:6])
    cen = ops.census()
    if not set(cen["content"]) <= {core.SHOW_PATH} or not set(cen["maps"]) <= {core.WORLD_PATH} \
            or core.SHOW_PATH not in cen["content"]:
        _stop(ops, core, run, "DIRTY_SCOPE %s (expected Show (+ level) only)" % json.dumps(cen))
    if ops.zz_actors():
        _stop(ops, core, run, "ZZ_ACTORS_APPEARED %s" % ops.zz_actors())
    if not ops.save_show():
        _stop(ops, core, run, "SHOW_SAVE_FALSE")
    if not ops.save_level():
        _stop(ops, core, run, "LEVEL_SAVE_FALSE")
    cen = ops.census()
    if cen != {"content": [], "maps": []}:
        _stop(ops, core, run, "DIRTY_AFTER_SAVE %s" % json.dumps(cen))
    bad = _check_rows(ops, core, write, before_rows, bits)
    if bad:
        _stop(ops, core, run, "POST_SAVE_READBACK %s" % bad[:6])
    after = {g: _sha(ops.read_row(g)["mech_text"]) for g in guids}
    after_mask = {g: int(ops.read_row(g)["mask"]) for g in guids}   # REVERT's DRIFT check (field-scoped, 7 Oct)
    _write_json(os.path.join(here, "topple_apply_%s.json" % run),
                {"run_id": run, "originals": orig_path, "backup_dir": backup_dir, "parts": plan["parts"],
                 "rows": [r["label"] for r in write], "after_mech_sha": after, "after_mask": after_mask,
                 "census_after": cen,
                 "pose_probe": pose, "rest_after_materialize": rest,
                 "chain_timing": (c or {}).get("timing"), "saved": [core.SHOW_PATH, core.WORLD_PATH]})
    ops.log("%s_APPLY_OK|run=%s|parts=%s|still=%d|chain=%s|saved=show,level|census=clean|originals=%s" % (
        core.MARK, run, "+".join(plan["parts"]), sum(1 for r in write if r["action"] == "still"),
        "none" if not c else "%s:%s" % (c["side"], ",".join(r["label"] for r in c["rows"])), orig_path))
    return after


def _cue_guid_of(core, cue_text):
    return str(core.get_field(cue_text, "CueGuid") or "").replace("-", "").upper()


def _guid_index(ops, core, run, texts):
    index = {}
    for i, t in enumerate(texts):
        g = _cue_guid_of(core, t)
        if g in index:
            _stop(ops, core, run, "CUE_GUID_NOT_UNIQUE %s (indices %d, %d)" % (g, index[g], i))
        index[g] = i
    return index


def _expected_after_mask(orig_doc, applied, row):
    """APPLY's after-state mask: recorded since 7 Oct ("after_mask"); for older records derived from what APPLY
    writes (still rows: mask untouched; chain rows: mask | override_bits -- write_rows above)."""
    rec = applied.get("after_mask")
    if rec is not None:
        return rec.get(row["cue_guid"])
    bits = int(orig_doc.get("override_bits") or 0)
    return int(row["mask"]) | (bits if row.get("action") == "chain" else 0)


def _revert_scope_check(ops, core, orig_doc, pre_texts, pre_index, now_texts):
    """FIELD-SCOPED read-back (7 Oct, after TOPPLE-20261007-080745 stopped on a whole-text compare): per target row
    mechanism text + mask == the originals AND the cue text outside WingPair.Mechanism/LocalOverrideMask == its
    PRE-REVERT text (only the restored fields changed; other streams' later edits -- lights, attachments -- survive);
    every non-target cue byte-identical to its pre-revert text; same cue count and order. [] = good."""
    if len(now_texts) != len(pre_texts):
        return ["CUE_COUNT_CHANGED %d -> %d" % (len(pre_texts), len(now_texts))]
    if [_cue_guid_of(core, t) for t in now_texts] != [_cue_guid_of(core, t) for t in pre_texts]:
        return ["CUE_ORDER_CHANGED"]
    bad = []
    targets = {pre_index[r["cue_guid"]]: r for r in orig_doc["rows"]}
    for i, (a, b) in enumerate(zip(pre_texts, now_texts)):
        if i in targets:
            if core.cue_text_outside_mechanism(a) != core.cue_text_outside_mechanism(b):
                bad.append("TARGET_CHANGED_OUTSIDE_MECHANISM %s index %d" % (targets[i]["label"], i))
        elif a != b:
            bad.append("NONTARGET_CUE_CHANGED index %d" % i)
    for r in orig_doc["rows"]:
        live = ops.read_row(r["cue_guid"])
        if live["mech_text"] != r["mech_text"]:
            bad.append("TARGET_MECHANISM_NOT_RESTORED %s" % r["label"])
        if int(live["mask"]) != int(r["mask"]):
            bad.append("TARGET_MASK_NOT_RESTORED %s %d want %d" % (r["label"], int(live["mask"]), int(r["mask"])))
    return bad


def run_revert(ops, core, args, orig_doc, run, here):
    """FIELD-SCOPED REVERT (7 Oct). Refuses: DRIFT_SINCE_APPLY (a target's mechanism text or mask differs from APPLY's
    after-state), TARGET_CUE_GONE / CUE_GUID_NOT_UNIQUE, REVERT_READBACK (anything other than a target's mechanism +
    mask changed, or the restore did not land). Accepts: any later edit OUTSIDE the targets' WingPair.Mechanism /
    LocalOverrideMask (lights, attachments, panels, cue order by another tool): kept as it is in memory now. Rows are
    found by CueGuid, never by the originals' show_index (a relayout may have moved them)."""
    _guard_start(ops, core, run)
    if ops.zz_actors():
        _stop(ops, core, run, "ZZ_OR_TEMP_ACTORS_IN_LEVEL %s" % ops.zz_actors())
    apply_path = os.path.join(here, "topple_apply_%s.json" % orig_doc["run_id"])
    if not os.path.exists(apply_path):
        _stop(ops, core, run, "NO_APPLY_RECORD %s (apply never finished: compare the live rows by hand)" % apply_path)
    applied = _read_json(apply_path)
    pre_texts = ops.cue_texts()                     # in-memory snapshot BEFORE anything is written
    pre_index = _guid_index(ops, core, run, pre_texts)
    for row in orig_doc["rows"]:
        if row["cue_guid"] not in pre_index:
            _stop(ops, core, run, "TARGET_CUE_GONE %s %s" % (row["label"], row["cue_guid"]))
        live = ops.read_row(row["cue_guid"])
        if _sha(live["mech_text"]) != applied["after_mech_sha"].get(row["cue_guid"]):
            _stop(ops, core, run, "DRIFT_SINCE_APPLY %s mechanism (someone edited the row's mechanism after APPLY; "
                                  "refused)" % row["label"])
        want_mask = _expected_after_mask(orig_doc, applied, row)
        if want_mask is None or int(live["mask"]) != int(want_mask):
            _stop(ops, core, run, "DRIFT_SINCE_APPLY %s LocalOverrideMask %d want %s (refused)" % (
                row["label"], int(live["mask"]), want_mask))
        core.cue_text_outside_mechanism(pre_texts[pre_index[row["cue_guid"]]])   # computable BEFORE any write
    foreign = [r["label"] for r in orig_doc["rows"] if "cue_text" in r and core.cue_text_outside_mechanism(
        r["cue_text"]) != core.cue_text_outside_mechanism(pre_texts[pre_index[r["cue_guid"]]])]
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    backup_dir, _ = ops.backup("PreP06ToppleRevert-%s" % stamp)
    ops.log("%s_REVERT_BACKUP|run=%s|backup=%s|foreign_edits_kept=%d%s" % (
        core.MARK, run, backup_dir, len(foreign), ("|rows=" + ",".join(foreign[:8])) if foreign else ""))
    ops.restore_rows(orig_doc["rows"])
    bad = _revert_scope_check(ops, core, orig_doc, pre_texts, pre_index, ops.cue_texts())
    if bad:
        _stop(ops, core, run, "REVERT_READBACK %s (Show dirty, unsaved: relaunch with Don't Save)" % bad[:6])
    if not ops.materialize():
        _stop(ops, core, run, "MATERIALIZE_FAILED")
    c = ops.census()
    if not set(c["content"]) <= {core.SHOW_PATH} or not set(c["maps"]) <= {core.WORLD_PATH}:
        _stop(ops, core, run, "DIRTY_SCOPE %s" % json.dumps(c))
    if not ops.save_show() or not ops.save_level():
        _stop(ops, core, run, "SAVE_FALSE")
    if ops.census() != {"content": [], "maps": []}:
        _stop(ops, core, run, "DIRTY_AFTER_SAVE")
    bad = _revert_scope_check(ops, core, orig_doc, pre_texts, pre_index, ops.cue_texts())
    if bad:
        _stop(ops, core, run, "POST_SAVE_REVERT_READBACK %s" % bad[:6])
    orig_path = os.path.join(here, "topple_originals_%s.json" % orig_doc["run_id"])
    os.replace(orig_path, orig_path.replace(".json", "_reverted.json"))
    active = os.path.join(here, ACTIVE_NAME)
    if os.path.exists(active):
        # Preserve the pointer as evidence.  Project rule: no permanent deletion;
        # a later APPLY only checks the exact ACTIVE name, so an archive is safe.
        os.replace(active, active + ".reverted-" + run)
    ops.log("%s_REVERT_OK|run=%s|reverted=%s|rows=%d|foreign_edits_kept=%d|saved=show,level|census=clean" % (
        core.MARK, run, orig_doc["run_id"], len(orig_doc["rows"]), len(foreign)))


def main():
    here = _here()
    core = _load_core()
    ops = UnrealOps(core)
    run = datetime.datetime.now().strftime("TOPPLE-%Y%m%d-%H%M%S")
    try:
        args = _read_json(os.path.join(here, ARGS_NAME))
        run = str(args.get("run_id") or run)
        mode = str(args.get("mode") or "").upper()
        plan = _read_json(os.path.join(here, PLAN_NAME)) if mode == "APPLY" else None
        orig_doc = None
        if mode == "REVERT":
            active = os.path.join(here, ACTIVE_NAME)
            core.require(os.path.exists(active), "NO_ACTIVE_ORIGINALS (%s)" % active)
            orig_doc = _read_json(_read_json(active)["originals"])
        core.validate_args(args, plan, orig_doc)
    except (core.PlanError, OSError, ValueError, KeyError) as exc:
        _stop(ops, core, run, "ARGS|%s" % exc)
    if mode == "DRY":
        run_dry(ops, core, args, run, here)
    elif mode == "APPLY":
        run_apply(ops, core, args, plan, run, here)
    else:
        run_revert(ops, core, args, orig_doc, run, here)


if unreal is not None:
    main()
