"""Offline harness for RZSWAP (system Python; no Unreal).

  python test_rzswap_offline.py   -> PASS/FAIL per check, writes test_rzswap_offline_report.json

The fake Show is built from REAL cue export texts (the 64 P06 cue texts the relayout saved before its APPLY,
p06relayout/relayout_originals_P06RL-20261007-081048.json [meas]), so the struct-text parser, the blanking of the
written panel fields and the byte-identity checks run on the real text format.  The fake treats 14 of those cues as
"passage P02"; panel geometry is self-consistent (side bounds = mesh zero bounds + local y; world inner edge = local
inner + a per-row offset), so a correct swap keeps every world inner edge and a mirrored one moves it.
What it CANNOT prove [inf]: common.side_bounds / set_panel / panel_plain on live structs, the passage actor's world
transforms, the Master pin reads, what the editor marks dirty -- the live DRY reads them and APPLY asserts each.
"""
import copy
import importlib.util
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


core = _load("rzswap_core_t", os.path.join(HERE, "rzswap_core.py"))
app = _load("rzswap_app_t", os.path.join(HERE, "rzswap.py"))
tc = _load("topple_core_rzswap_t", os.path.join(HERE, "..", "topple", "topple_core.py"))
msp = _load("make_swap_plan_t", os.path.join(HERE, "make_swap_plan.py"))
REAL = json.load(open(os.path.join(HERE, "..", "p06relayout", "relayout_originals_P06RL-20261007-081048.json"),
                      encoding="utf-8"))["p06_cue_texts"]
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append({"check": name, "pass": bool(cond), "detail": str(detail)[:300]})
    print("%s  %s %s" % ("PASS" if cond else "FAIL", name, ("" if cond else str(detail)[:300])))


def expect_stop(name, fn, token):
    try:
        fn()
    except core.PlanError as exc:
        check(name, token in str(exc), exc)
        return str(exc)
    check(name, False, "did not stop (wanted %s)" % token)
    return None


def norm(g):
    return str(g).replace("-", "").upper()


# =====================================================================================================================
# Panel text <-> plain (the real export format)
# =====================================================================================================================

POLICY = {"PreserveAsset": "InfinityPanelFacingPolicy.PRESERVE_ASSET", "AutoByRole": "InfinityPanelFacingPolicy.AUTO_BY_ROLE",
          "Rotate180AroundUp": "InfinityPanelFacingPolicy.ROTATE180_AROUND_UP"}


def _num(v):
    return float(str(v).strip())


def plain_from_text(pt):
    mesh = tc.get_field(pt, "Mesh")
    mesh = None if not mesh or mesh in ('""', "None") else mesh.strip('"').split(".", 1)[0]
    lt = tc.get_field(pt, "LocalTransform")
    tr = tc.get_field(lt, "Translation")
    sc = tc.get_field(lt, "Scale3D")
    q = tc.get_field(lt, "Rotation")
    rot = [0.0, 0.0, 0.0] if abs(_num(tc.get_field(q, "W")) - 1.0) < 1e-6 else [99.0, 0.0, 0.0]
    mo = tc.get_field(pt, "MaterialOverrides")
    return {"mesh": mesh, "material_overrides": [] if not mo else [mo],
            "local_transform": {"location": [_num(tc.get_field(tr, k)) for k in "XYZ"], "rotation": rot,
                                "scale": [_num(tc.get_field(sc, k)) for k in "XYZ"]},
            "facing_policy": POLICY.get(tc.get_field(pt, "FacingPolicy"), tc.get_field(pt, "FacingPolicy")),
            "flip_image_horizontally": tc.get_field(pt, "bFlipImageHorizontally") == "True"}


def text_from_plain(old_pt, plain):
    name = plain["mesh"].rsplit("/", 1)[-1]
    loc = plain["local_transform"]["location"]
    lt = "(Rotation=(X=0.000000,Y=0.000000,Z=0.000000,W=1.000000),Translation=(X=%.6f,Y=%.6f,Z=%.6f)," \
         "Scale3D=(X=1.000000,Y=1.000000,Z=1.000000))" % tuple(loc)
    pol = [k for k, v in POLICY.items() if v.endswith(plain["facing_policy"].split(".")[-1])][0]
    t = tc.replace_field(old_pt, "Mesh", '"%s.%s"' % (plain["mesh"], name))
    t = tc.replace_field(t, "MaterialOverrides", "")
    t = tc.replace_field(t, "LocalTransform", lt)
    t = tc.replace_field(t, "FacingPolicy", pol)
    return tc.replace_field(t, "bFlipImageHorizontally", "True" if plain["flip_image_horizontally"] else "False")


def zero_bounds(mesh, side=None):
    """Self-consistent fake geometry: width from the name; built-L meshes extend +Y, built-R -Y (Unreal frame)."""
    w = 300.0 + (sum(map(ord, mesh or "")) % 400)
    n = mesh or ""
    right = n.endswith(("_R", "_R_t5p", "_R_t5j")) or "_R_v" in n or "_R_" in n.rsplit("/", 1)[-1][-12:]
    return {"min_y_cm": -w, "max_y_cm": 0.0} if right else {"min_y_cm": 0.0, "max_y_cm": w}


def bounds_of(plain):
    z = zero_bounds(plain["mesh"])
    y = plain["local_transform"]["location"][1]
    return {"min_y_cm": z["min_y_cm"] + y, "max_y_cm": z["max_y_cm"] + y}


# =====================================================================================================================
# Fake editor
# =====================================================================================================================

P = "P02"
FIRST, N = 20, 14                    # fake P02 = REAL[20:34]
V2 = "/Game/Scenes/Wings/Passage02_AnimalsToShrineV2/StaticMeshes/SM_P02_SET03_%s"
REALISM = {"L": ["/Game/Scenes/Wings/FlatV3/Realism/T5P/SM_FlatV3_P02_real_91_fern_L_t5p",
                 "/Game/Scenes/Wings/FlatV3/Realism/T5J/SM_FlatV3_P02_real_92_rock_L_t5j"],
           "R": ["/Game/Scenes/Wings/FlatV3/Realism/T5P/SM_FlatV3_P02_real_93_hut_R_t5p"]}


class FakeOps:
    def __init__(self):
        self.texts = list(REAL)
        self.settings = ["(PassageGuid=%s,Label=P02,FirstCueGuid=A,LastCueGuid=B)" % core.PASSAGES[P]["guid"]]
        self.logs, self.errors, self.events = [], [], []
        self.dirty = {"content": [], "maps": []}
        self.pie, self.zz = False, []
        self.pins, self.mech, self.atts = set(), {}, {}
        self.offsets = {}
        self.meshes = set(m for v in REALISM.values() for m in v)
        self.fault = None
        self.saved = []
        self.pristine = None
        self.backups = []
        # make two fake-passage sides V2 cards (as P02 Wing 003 is live) and give rows plain transforms
        for i in range(FIRST, FIRST + N):
            t = self.texts[i]
            for s in ("L", "R"):
                pt = core.panel_text(tc, t, s)
                pl = plain_from_text(pt)
                pl["local_transform"]["location"] = [0.0, pl["local_transform"]["location"][1], 0.0]
                if i in (FIRST + 4,):
                    pl["mesh"] = V2 % s
                    pl["facing_policy"] = POLICY["AutoByRole"]
                t = self._set_panel_text(t, s, text_from_plain(pt, pl) if pl["mesh"] else pt)
            self.texts[i] = tc.replace_field(t, "bEnabled", "True")
        self.thick = {}

    def _set_panel_text(self, t, s, pt):
        wp = tc.get_field(t, "WingPair")
        return tc.replace_field(t, "WingPair", tc.replace_field(wp, core.SIDE_FIELD[s], pt))

    def guid(self, i):
        return norm(tc.get_field(self.texts[i], "CueGuid"))

    def index(self):
        return {self.guid(i): i for i in range(len(self.texts))}

    # ---- context
    def log(self, m):
        self.logs.append(m)
        self.events.append(("log", m))

    def log_error(self, m):
        self.errors.append(m)
        self.events.append(("err", m))

    def project_dir(self):
        return PROJECT

    def guard_context(self):
        if self.pie:
            raise core.PlanError("PIE_OR_SIE_ACTIVE (refused; this tool never ends PIE)")

    def census(self):
        return copy.deepcopy(self.dirty)

    def zz_actors(self):
        return list(self.zz)

    # ---- reads
    def cue_texts(self):
        return list(self.texts)

    def settings_texts(self):
        return list(self.settings)

    def segments(self):
        return [["P02", 0, 1000]]

    def asset_is_mesh(self, p):
        return p in self.meshes or not p.startswith(core.REALISM_ROOT)

    def _plain(self, i, s):
        return plain_from_text(core.panel_text(tc, self.texts[i], s))

    def world_edges(self, P_, guids=None):
        out = {}
        for i in range(FIRST, FIRST + N):
            g = self.guid(i)
            for s in ("L", "R"):
                pl = self._plain(i, s)
                if not pl["mesh"]:
                    continue
                if self.fault == "world_mirrored" and core.REALISM_ROOT in pl["mesh"]:
                    pl["local_transform"]["location"][1] *= -1.0
                b = bounds_of(pl)
                inner = b["max_y_cm"] if s == "L" else b["min_y_cm"]
                out["%s|%s" % (g, s)] = {"inner_cm": inner + 1000.0 * (i - FIRST), "mesh": pl["mesh"]}
        return out

    def materialized_count(self, P_):
        return N

    def measure(self, P_, cand):
        rows = []
        edges = self.world_edges(P_)
        for o, i in enumerate(range(FIRST, FIRST + N)):
            t = self.texts[i]
            g = self.guid(i)
            row = {"ordinal": o, "cue_guid": g, "label": "P02 Wing %03d" % (o + 1), "show_index": i,
                   "enabled": True, "has_top": False, "interval_ticks": 48000, "gap_cm": 500.0,
                   "pass_frame_rel": 24000 + 48000 * o, "pass_s": 1.0 + 2.0 * o,
                   "mechanism": self.mech.get(o, {"kind": "InfinityMechanismKind.SLIDE",
                                                  "playback_mode": "InfinityMotionPlaybackMode.CONTINUOUS_LOOP"}),
                   "local_override_mask": 0, "master_pinned": g in self.pins, "attachments": self.atts.get(o, []),
                   "text_sha": core.sha_text(t), "panel_text_fields": {}, "sides": {}}
            for s in ("L", "R"):
                pl = self._plain(i, s)
                ob = bounds_of(pl) if pl["mesh"] else None
                th = self.thick.get((o, s), 10.0 if (pl["mesh"] or "").startswith("/Game/Scenes/Wings/Passage02") else 20.0)
                row["sides"][s] = {"panel": pl, "box_cm": None, "height_cm": 1000.0, "thickness_cm": th, "width_cm": 400.0,
                                   "old_bounds": ob, "attachment_refs_mesh": False,
                                   "edge_baseline": edges.get("%s|%s" % (g, s))}
                row["panel_text_fields"][s] = core.panel_text_fields(tc, t, s)
            rows.append(row)
        cands = {m: {"owner": m.rsplit("/", 1)[-1], "exists": m in self.meshes,
                     "zero_bounds": zero_bounds(m) if m in self.meshes else None} for m in sorted(cand)}
        return {"passage": P_, "passage_guid": core.PASSAGES[P_]["guid"], "actor_label": "Passage 02 - fake",
                "tick": 24000.0, "settings": {"label": "P02", "lead_in_frames": 24000, "lead_in_distance_cm": 0.0,
                                              "tail_frames": 0, "tail_distance_cm": 0.0,
                                              "first_cue_guid": rows[0]["cue_guid"], "last_cue_guid": rows[-1]["cue_guid"]},
                "rows": rows, "candidates": cands, "materialized_count": N, "edges": edges}

    def placements(self, P_, swaps):
        idx = self.index()
        out = {}
        for s in swaps:
            old = bounds_of(self._plain(idx[s["cue_guid"]], s["side"]))
            y = core.inner_edge_y(s["side"], old, zero_bounds(s["new_mesh"]))
            out[s["key"]] = core.planned_panel(s["new_mesh"], y + (5.0 if self.fault == "placement_drift" else 0.0))
        return out

    def live_panels(self, keys):
        idx = self.index()
        return {k: self._plain(idx[k.split("|")[0]], k.split("|")[1]) for k in keys if k.split("|")[0] in idx}

    # ---- writes
    def write_panels(self, panels):
        self.pristine = list(self.texts)
        idx = self.index()
        for k, rec in sorted(panels.items()):
            g, s = k.split("|")
            i = idx[g]
            rec = copy.deepcopy(rec)
            if self.fault == "mirrored":
                rec["local_transform"]["location"][1] *= -1.0
            if self.fault == "noop":
                continue
            pt = text_from_plain(core.panel_text(tc, self.texts[i], s), rec)
            if self.fault == "cast_shadow":
                pt = tc.replace_field(pt, "bCastShadow", "False")
            self.texts[i] = self._set_panel_text(self.texts[i], s, pt)
        if self.fault == "touch_other_cue":
            self.texts[0] = self.texts[0].replace("bEnabled=True", "bEnabled=False", 1) if "bEnabled=True" in self.texts[0] \
                else self.texts[0].replace("bEnabled=False", "bEnabled=True", 1)
        self.dirty["content"] = sorted(set(self.dirty["content"]) | {core.SHOW_PATH})
        self.events.append(("write", len(panels)))

    def restore_pristine(self):
        if self.pristine is None:
            return False
        self.texts = list(self.pristine)
        self.events.append(("restore", None))
        return True

    def materialize(self, P_):
        self.events.append(("materialize", P_))
        if self.fault == "materialize_false":
            return False
        self.dirty["maps"] = [core.WORLD_PATH]
        if self.fault == "foreign_dirty":
            self.dirty["content"] = sorted(set(self.dirty["content"]) | {"/Game/Someone/Else"})
        return True

    def backup(self, name):
        self.backups.append(name)
        return "Backups/" + name, ["a", "b"]

    def save_show(self):
        self.events.append(("save", "show"))
        self.saved.append("show")
        self.dirty["content"] = [c for c in self.dirty["content"] if c != core.SHOW_PATH]
        return True

    def save_level(self):
        self.events.append(("save", "level"))
        self.saved.append("level")
        self.dirty["maps"] = []
        return True


def make_designs(ops, dry, imported=True):
    out = []
    for s, ms in REALISM.items():
        for m in ms:
            out.append({"owner": m.rsplit("/", 1)[-1][len("SM_FlatV3_"):-4], "side": s, "mount": "wing", "passage": P,
                        "mesh": m, "height_cm": 1200.0, "width_cm": 500.0, "skin_png": None, "imported": imported,
                        "exists": dry["candidates"].get(m, {}).get("exists", False),
                        "zero_bounds": dry["candidates"].get(m, {}).get("zero_bounds")})
    return out


CANDS = {m: m.rsplit("/", 1)[-1] for v in REALISM.values() for m in v}
PROTECT = {"P02": {"sides": [], "families": []}}


def do_dry(ops, d, run="RZSW-T-DRY"):
    args = {"mode": "DRY", "passage": P, "confirm": "DRY RZSWAP P02", "manifests": []}
    return app.run_dry(ops, core, args, run, d, CANDS)


def do_plan(ops, d, dry, opts=None, protect=None):
    plan = core.make_plan(dry, make_designs(ops, dry), protect or PROTECT, opts or {})
    with open(os.path.join(d, "rzswap_plan_P02.json"), "w", encoding="utf-8") as fh:
        json.dump(plan, fh)
    return plan


def do_apply(ops, d, plan, run="RZSW-T-APPLY", decided="Gary test"):
    args = {"mode": "APPLY", "passage": P, "confirm": plan["confirm"], "decided_by": decided}
    core.validate_args(args, plan)
    return app.run_apply(ops, core, tc, args, plan, run, d)


def do_revert(ops, d, run="RZSW-T-REV"):
    act = app._read_json(os.path.join(d, app.active_name(P)))
    orig = app._read_json(act["originals"])
    args = {"mode": "REVERT", "passage": P, "confirm": "REVERT RZSWAP P02 %s" % orig["run_id"]}
    core.validate_args(args, None, orig)
    return app.run_revert(ops, core, tc, args, orig, run, d)


def fresh(tmp):
    return FakeOps(), tempfile.mkdtemp(prefix="rzsw_", dir=tmp)


def synth_dry(rows_spec, cands=None):
    """Tiny pure DRY doc: rows_spec = [(L_mesh, R_mesh), ...]."""
    rows = []
    for o, (lm, rm) in enumerate(rows_spec):
        r = {"ordinal": o, "cue_guid": "G%02d" % o, "label": "P02 Wing %03d" % (o + 1), "show_index": o, "enabled": True,
             "pass_s": float(o), "mechanism": {"kind": "SLIDE", "playback_mode": "CONTINUOUS_LOOP"},
             "master_pinned": False, "attachments": [], "sides": {}}
        for s, m in (("L", lm), ("R", rm)):
            th = 10.0 if m and not m.startswith(core.V3_ROOT) else 20.0
            r["sides"][s] = {"panel": core.planned_panel(m, 0.0) if m else core.planned_panel(None, 0.0),
                             "thickness_cm": th, "height_cm": 1000.0, "old_bounds": zero_bounds(m) if m else None,
                             "edge_baseline": {"inner_cm": 0.0}}
        rows.append(r)
    return {"mode": "DRY", "status": "PASS", "run_id": "SYN", "passage": P, "passage_guid": core.PASSAGES[P]["guid"],
            "rows": rows, "candidates": cands or {}, "settings": {"first_cue_guid": "G00", "last_cue_guid": "G%02d" % (len(rows) - 1)}}


def syn_designs(n_l=3, n_r=2, imported=True, exists=True):
    out = []
    for s, n in (("L", n_l), ("R", n_r)):
        for k in range(n):
            m = "/Game/Scenes/Wings/FlatV3/Realism/T5P/SM_FlatV3_P02_real_%d%d_d_%s_t5p" % (k, ord(s), s)
            out.append({"owner": "P02_real_%d%d_d_%s" % (k, ord(s), s), "side": s, "mount": "wing", "passage": P, "mesh": m,
                        "height_cm": 1200.0, "imported": imported, "exists": exists, "zero_bounds": zero_bounds(m)})
    return out


V3 = "/Game/Scenes/Wings/FlatV3/Passage02/StaticMeshes/T5P/SM_FlatV3_P02_SET%02d_%s_t5p"
IND = "/Game/Scenes/Wings/FlatV3/Passage02/StaticMeshes/SM_FlatV3_P02_IND_FenceTarp_%s"


def main():
    tmp = tempfile.mkdtemp(prefix="rzswap_t_").replace("\\", "/")
    try:
        return _main(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _main(tmp):
    # ---------------------------------------------------------------- T: real export text
    t0 = REAL[0]
    check("T1 MEAS real cue text: the Left panel carries every written field name (Mesh, MaterialOverrides, "
          "LocalTransform, FacingPolicy, bFlipImageHorizontally) + bCastShadow",
          set(core.WRITTEN_PANEL_FIELDS) | {"bCastShadow"} <= set(core.panel_text_fields(tc, t0, "L")),
          core.panel_text_fields(tc, t0, "L"))
    pt = core.panel_text(tc, t0, "L")
    swapped = tc.replace_field(tc.get_field(t0, "WingPair"), "Left", tc.replace_field(pt, "Mesh", '"/Game/X.X"'))
    t1 = tc.replace_field(t0, "WingPair", swapped)
    check("T2 POS verify_texts: a Mesh change on the target panel only -> no failure",
          core.verify_texts(tc, [t0, REAL[1]], [t1, REAL[1]], {0: ["L"]}) == [])
    t2 = tc.replace_field(t1, "WingPair", tc.replace_field(tc.get_field(t1, "WingPair"), "Left",
                                                         tc.replace_field(core.panel_text(tc, t1, "L"), "bCastShadow", "False")))
    check("T3 NEG ... plus bCastShadow flipped -> UNWRITTEN_PANEL_FIELD_CHANGED",
          any("UNWRITTEN_PANEL_FIELD_CHANGED" in b for b in core.verify_texts(tc, [t0], [t2], {0: ["L"]})))
    t3 = tc.replace_field(t1, "WingPair", tc.replace_field(tc.get_field(t1, "WingPair"), "GapToNextCm", "123.000000"))
    check("T4 NEG ... plus a gap edit on the same cue -> TARGET_CUE_CHANGED_OUTSIDE_PANELS",
          any("TARGET_CUE_CHANGED_OUTSIDE_PANELS" in b for b in core.verify_texts(tc, [t0], [t3], {0: ["L"]})))
    check("T5 NEG a non-target cue changed by one byte -> NON_TARGET_CUE_CHANGED",
          any("NON_TARGET_CUE_CHANGED" in b for b in core.verify_texts(tc, [t0, REAL[1]], [t1, REAL[1] + " "], {0: ["L"]})))
    check("T6 NEG the Right panel changed while only L is the target -> TARGET_CUE_CHANGED_OUTSIDE_PANELS",
          any("OUTSIDE_PANELS" in b for b in core.verify_texts(tc, [t0], [tc.replace_field(t1, "WingPair", tc.replace_field(
              tc.get_field(t1, "WingPair"), "Right", tc.replace_field(core.panel_text(tc, t1, "R"), "Mesh", '"/Game/Y.Y"')))],
              {0: ["L"]})))
    # ---------------------------------------------------------------- C: classification
    check("C1 family_of strips side/variant tokens", core.family_of(V3 % (1, "L")) == "P02_SET01" and
          core.family_of(V2 % "R") == "P02_SET03" and core.family_of(IND % "L") == "P02_IND_FenceTarp")
    check("C2 classify: V2 card / V3 / IND / realism / thick legacy / empty",
          core.classify(V2 % "L", 10.0) == "V2_CARD" and core.classify(V3 % (1, "L"), 20) == "V3" and
          core.classify(IND % "L", 90) == "IND_3D" and core.classify(REALISM["L"][0], 20) == "REALISM" and
          core.classify("/Game/Props/SM_CeramicTotem_01_L", 60.0) == "LEGACY_THICK_OR_UNMEASURED" and
          core.classify(None, None) == "EMPTY")
    check("C3 special mechanism: Topple / CameraGust / OneShot are special, Slide loop is not",
          core.special_mechanism({"kind": "InfinityMechanismKind.TOPPLE", "playback_mode": "x"}) and
          core.special_mechanism({"kind": "InfinityMechanismKind.SLIDE", "playback_mode": "InfinityMotionPlaybackMode.CAMERA_GUST"}) and
          core.special_mechanism({"kind": "SLIDE", "playback_mode": "ONE_SHOT"}) and
          not core.special_mechanism({"kind": "InfinityMechanismKind.SLIDE", "playback_mode": "InfinityMotionPlaybackMode.CONTINUOUS_LOOP"}))
    check("C4 effect sides from labels ('FX SMOKE P03 B08 L' -> L; no suffix -> both; lights ignored)",
          core.effect_sides([{"kind": "InfinityAttachmentKind.EFFECT", "label": "FX SMOKE P03 B08 L"}]) == {"L"} and
          core.effect_sides([{"kind": "EFFECT", "label": "FX"}]) == {"L", "R"} and
          core.effect_sides([{"kind": "LIGHT", "label": "x L"}]) == set())
    # ---------------------------------------------------------------- S: scoring / assignment (pure)
    spec = [(V3 % (1, "L"), V3 % (1, "R")), (V3 % (2, "L"), V3 % (2, "R")), (V2 % "L", V2 % "R"), (V3 % (2, "L"), V3 % (3, "R")),
            (IND % "L", IND % "R"), (V3 % (4, "L"), V3 % (4, "R")), (V3 % (1, "L"), V3 % (1, "R")), (V3 % (5, "L"), V3 % (5, "R")),
            (V3 % (6, "L"), V3 % (6, "R"))]
    dry = synth_dry(spec)
    facts = {f["key"]: f for f in core.side_facts(dry, PROTECT, {})}
    check("S1 END rows protected (first and last)", "END_ROW" in facts["G00|L"]["protected"][0] and
          any("END_ROW" in p for p in facts["G08|R"]["protected"]))
    check("S2 IND 3D protected", "IND_3D" in facts["G04|L"]["protected"])
    check("S3 score: V2 card 1000+ > repeated family (SET02 rows 1+3 adjacent? no: 2 apart) > single",
          facts["G02|L"]["score"] >= 1000 and facts["G01|L"]["score"] == 100 and facts["G05|L"]["score"] == 0,
          (facts["G02|L"]["score"], facts["G01|L"]["score"], facts["G05|L"]["score"]))
    check("S4 score: adjacent same family on the same side +50 (SET02 L rows 1 and 3 are not adjacent; SET01 0/6 not)",
          facts["G03|L"]["adjacent_same_family"] is False)
    dry_adj = synth_dry([(V3 % (9, "L"), V3 % (9, "R")), (V3 % (7, "L"), V3 % (8, "R")), (V3 % (7, "L"), V3 % (9, "R")),
                         (V3 % (6, "L"), V3 % (6, "R"))])
    fa = {f["key"]: f for f in core.side_facts(dry_adj, PROTECT, {})}
    check("S5 adjacent same-family rows score +50 on that side only", fa["G01|L"]["adjacent_same_family"] and
          fa["G01|L"]["score"] == 150 and not fa["G01|R"]["adjacent_same_family"], (fa["G01|L"]["score"], fa["G01|R"]["score"]))
    plan = core.make_plan(dry, syn_designs(3, 2), PROTECT)
    sw = {s["key"]: s for s in plan["swaps"]}
    check("S6 POS plan gates ok; V2 card sides go first", plan["gates_ok"] and "G02|L" in sw and "G02|R" in sw, plan["refusals"])
    uses = {}
    for s in plan["swaps"]:
        uses[s["new_mesh"]] = uses.get(s["new_mesh"], 0) + 1
    check("S7 each design at most 2x", max(uses.values()) <= 2, uses)
    by = {(s["ordinal"], s["side"]): s["new_mesh"] for s in plan["swaps"]}
    check("S8 never the same design on the same side of adjacent rows",
          not any(by.get((o + 1, sd)) == m for (o, sd), m in by.items()), by)
    check("S9 side = built side (an L design never on R)", all(s["new_mesh"].endswith("_%s_t5p" % s["side"]) for s in plan["swaps"]))
    check("S10 protected sides never in the plan", not any(k in sw for k in ("G00|L", "G00|R", "G08|L", "G08|R", "G04|L", "G04|R")))
    check("S11 placement: new inner edge == old inner edge (pure)", all(abs(s["new_inner_cm"] - s["old_inner_cm"]) < 1e-9
                                                                       for s in plan["swaps"]))
    p_none = core.make_plan(dry, syn_designs(3, 2, imported=False), PROTECT)
    check("S12 NEG designs not verified-imported -> NO_SWAPS, all listed unusable",
          not p_none["gates_ok"] and "NO_SWAPS" in p_none["refusals"][0] and
          all("NOT_VERIFIED_IMPORTED" in " ".join(v) for v in p_none["designs_unusable"].values()))
    p_nx = core.make_plan(dry, syn_designs(3, 2, exists=False), PROTECT)
    check("S13 NEG designs not live in the editor (DRY) -> unusable", not p_nx["gates_ok"] and
          all("NOT_IN_EDITOR" in " ".join(v) for v in p_nx["designs_unusable"].values()))
    p_ex = core.make_plan(dry, syn_designs(3, 2), PROTECT, {"exclude": ["P02 Wing 003|L"]})
    check("S14 exclude a reviewed side -> it drops out, hash changes", "G02|L" not in {s["key"] for s in p_ex["swaps"]} and
          p_ex["inputs_hash"] != plan["inputs_hash"])
    p_max = core.make_plan(dry, syn_designs(3, 2), PROTECT, {"max_swaps": 2})
    check("S15 max_swaps caps the plan (the 2 highest scores: the V2 card pair)", len(p_max["swaps"]) == 2 and
          {s["key"] for s in p_max["swaps"]} == {"G02|L", "G02|R"}, [s["key"] for s in p_max["swaps"]])
    p_row = core.make_plan(dry, syn_designs(3, 1), PROTECT, {"pair_mode": "row"})
    rows_sw = {}
    for s in p_row["swaps"]:
        rows_sw.setdefault(s["cue_guid"], []).append(s["side"])
    check("S16 pair_mode row: every swapped row has both sides; no MIXED flag", p_row["swaps"] and
          all(sorted(v) == ["L", "R"] for v in rows_sw.values()) and not any("MIXED" in f for f in p_row["flags"]), rows_sw)
    p_side = core.make_plan(dry, syn_designs(3, 1), PROTECT)
    check("S17 pair_mode side with fewer R designs -> MIXED_PAIR_ROWS flagged for Gary (P02)",
          any("MIXED_PAIR_ROWS" in f for f in p_side["flags"]), p_side["flags"])
    prot = {"P02": {"sides": [{"cue_guid": "G02", "side": "L", "label": "P02 Wing 003", "reason": "keep", "source": "rec"}],
                    "families": [{"family": "P02_SET02", "source": "rec2"}]}}
    p_prot = core.make_plan(dry, syn_designs(3, 2), prot)
    k = {s["key"] for s in p_prot["swaps"]}
    check("S18 record-protected side + record-protected family never swapped", "G02|L" not in k and "G01|L" not in k and
          "G03|L" not in k and "G02|R" in k, sorted(k))
    prot_stale = {"P02": {"sides": [{"cue_guid": "G02", "side": "L", "label": "P02 Wing 999", "source": "rec"}]}}
    f_stale = {f["key"]: f for f in core.side_facts(dry, prot_stale, {})}
    check("S19 a protect record whose label no longer matches is reported STALE (still protected)",
          any("PROTECT_RECORD_STALE" in p for p in f_stale["G02|L"]["protected"]))
    dry_pin = copy.deepcopy(dry)
    dry_pin["rows"][2]["master_pinned"] = True
    dry_pin["rows"][5]["mechanism"] = {"kind": "InfinityMechanismKind.TOPPLE", "playback_mode": "STATIC"}
    dry_pin["rows"][6]["attachments"] = [{"kind": "InfinityAttachmentKind.EFFECT", "label": "FX SMOKE P02 B07 R"}]
    dry_pin["rows"][7]["sides"]["L"]["attachment_refs_mesh"] = True
    dry_pin["rows"][1]["sides"]["L"]["panel"]["local_transform"]["location"][2] = -5.0
    fp = {f["key"]: f for f in core.side_facts(dry_pin, PROTECT, {})}
    check("S20 Master pin / topple row / EFFECT side / mesh-keyed attachment / non-plain old transform all protected",
          not fp["G02|L"]["eligible"] and not fp["G05|R"]["eligible"] and not fp["G06|R"]["eligible"] and
          fp["G06|L"]["eligible"] and not fp["G07|L"]["eligible"] and not fp["G01|L"]["eligible"] and fp["G01|R"]["eligible"])
    dry_real = synth_dry([(V3 % (1, "L"), V3 % (1, "R")), (REALISM["L"][0], V3 % (2, "R")), (V3 % (3, "L"), V3 % (3, "R")),
                          (V3 % (4, "L"), V3 % (4, "R")), (REALISM["L"][0], V3 % (5, "R")), (V3 % (6, "L"), V3 % (6, "R"))])
    des = [{"owner": "fern", "side": "L", "mount": "wing", "passage": P, "mesh": REALISM["L"][0], "height_cm": 1200,
            "imported": True, "exists": True, "zero_bounds": zero_bounds(REALISM["L"][0])}]
    p_st = core.make_plan(dry_real, des, PROTECT)
    check("S21 realism already standing counts toward 2x (fern stands twice -> no more fern)", not p_st["swaps"])
    check("S22 plan hash depends on the DRY state (a panel change re-hashes)", core.state_hash(dry) != core.state_hash(dry_pin))
    # ---------------------------------------------------------------- A: args
    expect_stop("A1 NEG passage P06", lambda: core.validate_args({"mode": "DRY", "passage": "P06", "confirm": "x", "manifests": []}),
                "PASSAGE_INVALID")
    expect_stop("A2 NEG APPLY without decided_by", lambda: core.validate_args(
        {"mode": "APPLY", "passage": P, "confirm": plan["confirm"]}, plan), "NOT_DECIDED")
    expect_stop("A3 NEG APPLY with an old plan's confirm", lambda: core.validate_args(
        {"mode": "APPLY", "passage": P, "confirm": p_ex["confirm"], "decided_by": "G"}, plan), "CONFIRM_MISMATCH")
    expect_stop("A4 NEG APPLY of a plan with refusals", lambda: core.validate_args(
        {"mode": "APPLY", "passage": P, "confirm": p_none["confirm"], "decided_by": "G"}, p_none), "PLAN_GATES_FAILED")
    expect_stop("A5 NEG APPLY of a P03 plan as P02", lambda: core.validate_args(
        {"mode": "APPLY", "passage": "P03", "confirm": "x", "decided_by": "G"}, plan), "PLAN_PASSAGE_MISMATCH")
    # ---------------------------------------------------------------- D/X/Y: orchestration on the fake (real texts)
    ops, d = fresh(tmp)
    ops.dirty["content"] = ["/Game/Other"]
    expect_stop("D1 NEG dirty census at DRY", lambda: do_dry(ops, d), "DIRTY_CENSUS")
    ops, d = fresh(tmp)
    ops.zz = ["ZZ_bench"]
    expect_stop("D2 NEG ZZ_ bench actor in the level", lambda: do_dry(ops, d), "ZZ_OR_TEMP")
    ops, d = fresh(tmp)
    ops.pie = True
    expect_stop("D3 NEG PIE running", lambda: do_dry(ops, d), "PIE_OR_SIE_ACTIVE")
    ops, d = fresh(tmp)
    dry = do_dry(ops, d)
    check("D4 POS DRY marker + LATEST record; measures 14 rows, 3 live candidates; nothing written",
          any(m.startswith("FLATV3_RZSWAP_DRY_OK|run=RZSW-T-DRY|passage=P02|rows=14|candidates_live=3/3") for m in ops.logs) and
          os.path.isfile(os.path.join(d, "rzswap_dry_P02_LATEST.json")) and not any(e[0] == "write" for e in ops.events),
          ops.logs[-1:])
    plan = do_plan(ops, d, dry)
    check("D5 POS plan on the fake: swaps found, V2 card row (W005) swapped first", plan["gates_ok"] and plan["swaps"] and
          plan["swaps"] and any(s["label"] == "P02 Wing 005" for s in plan["swaps"]), (plan["refusals"], len(plan["swaps"])))
    # APPLY negatives
    ops2, d2 = fresh(tmp)
    dry2 = do_dry(ops2, d2)
    plan2 = do_plan(ops2, d2, dry2)
    i = FIRST + 7
    ops2.texts[i] = ops2._set_panel_text(ops2.texts[i], "L", text_from_plain(core.panel_text(tc, ops2.texts[i], "L"), dict(
        plain_from_text(core.panel_text(tc, ops2.texts[i], "L")), mesh=V3 % (11, "L"))))
    expect_stop("X1 NEG a panel changed after the DRY -> PLAN_STALE, nothing written", lambda: do_apply(ops2, d2, plan2), "PLAN_STALE")
    check("X1 NEG ... no backup, no write", not ops2.backups and not any(e[0] == "write" for e in ops2.events))
    ops2, d2 = fresh(tmp)
    dry2 = do_dry(ops2, d2)
    plan2 = do_plan(ops2, d2, dry2)
    ops2.texts[FIRST + 3] = ops2.texts[FIRST + 3].replace("Label=", "Label= ", 1) if "Label=" in ops2.texts[FIRST + 3] else ops2.texts[FIRST + 3]
    rec_ok = True
    try:
        do_apply(ops2, d2, plan2, run="RZSW-T-LIGHTEDIT")
    except core.PlanError as exc:
        rec_ok = str(exc)
    check("X2 POS a light/label edit by another stream since DRY does NOT stale the plan (state hash = swap-relevant only)",
          rec_ok is True, rec_ok)
    ops2, d2 = fresh(tmp)
    dry2 = do_dry(ops2, d2)
    plan2 = do_plan(ops2, d2, dry2)
    ops2.meshes.discard(plan2["swaps"][0]["new_mesh"])
    expect_stop("X3 NEG a planned mesh gone at APPLY -> CANDIDATE_CHANGED_SINCE_DRY", lambda: do_apply(ops2, d2, plan2), "CANDIDATE_CHANGED_SINCE_DRY")
    for fault, token, label in (("placement_drift", "PLACEMENT_DIFFERS_FROM_PLAN", "live placement differs from plan"),):
        ops2, d2 = fresh(tmp)
        dry2 = do_dry(ops2, d2)
        plan2 = do_plan(ops2, d2, dry2)
        ops2.fault = fault
        expect_stop("X4 NEG %s -> %s" % (label, token), lambda: do_apply(ops2, d2, plan2), token)
        check("X4 NEG ... before backup/originals", not ops2.backups)
    for fault, token, label in (("noop", "READBACK_FAILED", "the write did nothing"),
                                ("cast_shadow", "UNWRITTEN_PANEL_FIELD_CHANGED", "the write flipped bCastShadow"),
                                ("touch_other_cue", "NON_TARGET_CUE_CHANGED", "another cue changed in the write"),
                                ("mirrored", "WRITTEN_PANEL_READBACK", "the Show got a mirrored y (read-back of the written field)"),
                                ("world_mirrored", "WORLD_EDGE_PROBE", "the WORLD lands mirrored though the Show reads right (TK-style frame error)"),
                                ("materialize_false", "MATERIALIZE_FAILED", "materialize returns False"),
                                ("foreign_dirty", "DIRTY_SCOPE", "a foreign package dirtied")):
        ops2, d2 = fresh(tmp)
        dry2 = do_dry(ops2, d2)
        plan2 = do_plan(ops2, d2, dry2)
        before = list(ops2.texts)
        ops2.fault = fault
        expect_stop("X5 NEG %s -> %s" % (label, token), lambda: do_apply(ops2, d2, plan2), token)
        check("X5 NEG ... nothing saved; in-memory restore exact; originals written BEFORE the write",
              not ops2.saved and ops2.texts == before and
              any(("restore=True" in e or "RESTORED_BUT_REMATERIALIZE_FAILED" in e) for e in ops2.errors[-1:]) and
              os.path.isfile(os.path.join(d2, "rzswap_originals_P02_RZSW-T-APPLY.json")), ops2.errors[-1:])
    ops2, d2 = fresh(tmp)
    dry2 = do_dry(ops2, d2)
    plan2 = do_plan(ops2, d2, dry2)
    do_apply(ops2, d2, plan2)
    expect_stop("X6 NEG second APPLY while ACTIVE originals exist", lambda: do_apply(ops2, d2, plan2, run="RZSW-T-APPLY2"),
                "UNREVERTED_APPLY_EXISTS")
    # APPLY positive
    ops, d = fresh(tmp)
    dry = do_dry(ops, d)
    plan = do_plan(ops, d, dry)
    before = list(ops.texts)
    rec = do_apply(ops, d, plan)
    ev = [e[0] for e in ops.events]
    ok_i = max(i for i, e in enumerate(ops.events) if e[0] == "log" and "APPLY_OK" in e[1])
    check("Y1 POS APPLY_OK marker after write, materialize, both saves", ok_i > max(i for i, e in enumerate(ops.events) if e[0] == "save")
          and "write" in ev and "materialize" in ev and ops.saved == ["show", "level"])
    check("Y1 POS backup PreRZSwapP02-<stamp> taken before the write", ops.backups and ops.backups[0].startswith("PreRZSwapP02-")
          and ev.index("write") > 0)
    tg = {}
    idx = {norm(tc.get_field(t, "CueGuid")): i for i, t in enumerate(before)}
    for s in plan["swaps"]:
        tg.setdefault(idx[s["cue_guid"]], []).append(s["side"])
    check("Y2 POS only the target panels changed (every other cue byte-identical, unwritten panel fields identical)",
          core.verify_texts(tc, before, ops.texts, tg) == [] and before != ops.texts)
    check("Y3 POS world-edge probe: swapped deltas ~0, controls ~0, all %d sides probed" % (2 * N),
          len(rec["edge_probe"]) == 2 * N and max(abs(p["inner_delta_cm"]) for p in rec["edge_probe"]) < 1e-6)
    check("Y4 POS ACTIVE pointer + originals hold every swapped side's original panel",
          os.path.isfile(os.path.join(d, app.active_name(P))) and
          len(app._read_json(os.path.join(d, "rzswap_originals_P02_RZSW-T-APPLY.json"))["swaps"]) == len(plan["swaps"]))
    # REVERT
    applied_texts = list(ops.texts)
    j = FIRST + 2                         # another stream edits a light on a TARGET cue after APPLY
    tgt_i = idx[plan["swaps"][0]["cue_guid"]]
    ops.texts[tgt_i] = tc.replace_field(ops.texts[tgt_i], "WingPair", tc.replace_field(
        tc.get_field(ops.texts[tgt_i], "WingPair"), "bMuteMechanismSound", "True"))
    light_edited = ops.texts[tgt_i]
    do_revert(ops, d)
    check("Y5 POS REVERT succeeds although another stream edited the target cue after APPLY (written fields only)",
          any(m.startswith("FLATV3_RZSWAP_REVERT_OK|run=RZSW-T-REV|passage=P02") for m in ops.logs), ops.errors[-1:])
    check("Y6 POS ... the reverted panels equal the originals; the foreign edit SURVIVES; every other cue == pre-APPLY",
          all(core.panel_matches(plain_from_text(core.panel_text(tc, ops.texts[idx[s["cue_guid"]]], s["side"])),
                                 plain_from_text(core.panel_text(tc, before[idx[s["cue_guid"]]], s["side"]))) for s in plan["swaps"])
          and tc.get_field(tc.get_field(ops.texts[tgt_i], "WingPair"), "bMuteMechanismSound") == "True"
          and all(ops.texts[i] == before[i] for i in range(len(before)) if i not in tg))
    check("Y7 POS ... ACTIVE removed, originals renamed _reverted, revert backup taken",
          not os.path.exists(os.path.join(d, app.active_name(P))) and
          os.path.isfile(os.path.join(d, "rzswap_originals_P02_RZSW-T-APPLY_reverted.json")) and
          ops.backups[-1].startswith("PreRZSwapRevertP02-"))
    # REVERT negatives
    ops3, d3 = fresh(tmp)
    dry3 = do_dry(ops3, d3)
    plan3 = do_plan(ops3, d3, dry3)
    do_apply(ops3, d3, plan3)
    k0 = plan3["swaps"][0]
    i0 = ops3.index()[k0["cue_guid"]]
    ops3.texts[i0] = ops3._set_panel_text(ops3.texts[i0], k0["side"], text_from_plain(
        core.panel_text(tc, ops3.texts[i0], k0["side"]), dict(plain_from_text(core.panel_text(tc, ops3.texts[i0], k0["side"])),
                                                              mesh=V3 % (12, k0["side"]))))
    expect_stop("R1 NEG someone re-wrote a panel this tool wrote -> DRIFT_SINCE_APPLY, nothing written",
                lambda: do_revert(ops3, d3), "DRIFT_SINCE_APPLY")
    check("R1 NEG ... ACTIVE kept", os.path.exists(os.path.join(d3, app.active_name(P))))
    ops3, d3 = fresh(tmp)
    dry3 = do_dry(ops3, d3)
    plan3 = do_plan(ops3, d3, dry3)
    do_apply(ops3, d3, plan3)
    pre = list(ops3.texts)
    ops3.fault = "cast_shadow"
    expect_stop("R2 NEG revert write flips an unwritten field -> REVERT_READBACK, restore, nothing saved",
                lambda: do_revert(ops3, d3), "REVERT_READBACK")
    check("R2 NEG ... in-memory restore exact, no new save", ops3.texts == pre and ops3.saved == ["show", "level"])
    expect_stop("R3 NEG REVERT confirm of another run", lambda: core.validate_args(
        {"mode": "REVERT", "passage": P, "confirm": "REVERT RZSWAP P02 OTHER"}, None, {"run_id": "RZSW-X"}), "CONFIRM_MISMATCH")
    # ---------------------------------------------------------------- P: real-data preview (GAP_AUDIT snapshot)
    pv = msp.main(["P02", "--preview-gap-audit", "--out-dir", tmp, "--no-sheet"])
    keys = {s["label"] + "|" + s["side"] for s in pv["swaps"]}
    pf = {f["label"] + "|" + f["side"]: f for f in pv["facts"]}
    check("P1 PREVIEW P02 (6 Oct snapshot): never appliable", not pv["gates_ok"] and
          any("PREVIEW_NOT_APPLIABLE" in r for r in pv["refusals"]))
    check("P2 PREVIEW P02: Wing 003 (record keep_old, V2) protected; every IND side protected; first/last rows protected",
          any("RECORD_KEEP" in p for p in pf["P02 Wing 003|L"]["protected"]) and
          all(not f["eligible"] for f in pv["facts"] if f["class"] == "IND_3D") and
          any("END_ROW" in p for p in pf["P02 Wing 001|L"]["protected"]) and
          any("END_ROW" in p for p in pf["P02 Wing 023|R"]["protected"]))
    check("P3 PREVIEW P02: swaps only on L (both v1 realism designs are L-built), each design <= 2x, no adjacency",
          all(k.endswith("|L") for k in keys) and all(v <= 2 for v in pv["design_uses"].values()), sorted(keys))
    pv3 = msp.main(["P03", "--preview-gap-audit", "--out-dir", tmp, "--no-sheet"])
    p3 = {f["label"] + "|" + f["side"]: f for f in pv3["facts"]}
    check("P4 PREVIEW P03: the 4 kept convent rows (7 sides) and the 3 pyre families protected by record",
          sum(1 for f in pv3["facts"] if any("RECORD_KEEP" in p for p in f["protected"])) == 7 and
          all(any("RECORD_FAMILY" in p for p in f["protected"]) for f in pv3["facts"] if (f["family"] or "").startswith("P03_pyre")))
    # ---------------------------------------------------------------- static
    import ast
    src = open(os.path.join(HERE, "rzswap.py"), encoding="utf-8").read()
    check("Z1 no delete / reload / Save All / import_text in the live tool", not any(t in src for t in (
        "delete_asset", "reload_packages", "save_dirty_packages", "save_all", "SaveAll", "import_text")))
    tree = ast.parse(src)
    check("Z2 no unreal object in a module global",
          not [n.lineno for n in tree.body if isinstance(n, ast.Assign) and "unreal." in ast.unparse(n.value)])
    check("Z3 live files parse as Python 3.11", all(ast.parse(open(os.path.join(HERE, f), encoding="utf-8").read(),
                                                             feature_version=(3, 11)) for f in ("rzswap.py", "rzswap_core.py", "rzswap_run.py")))
    run_src = open(os.path.join(HERE, "rzswap_run.py"), encoding="utf-8").read()
    check("Z4 runner purges the Saved module cache first", run_src.index("purge_saved_module_cache") < run_src.index("rzswap.py\""))
    req = json.load(open(os.path.join(HERE, "rzswap_request.json"), encoding="utf-8"))
    check("Z5 request = guarded loopback route, our runner", req["arguments"]["tool_name"] == "ExecuteProjectPythonFile" and
          req["arguments"]["arguments"]["relativeSavedPath"] == "CodexFlatV3/rzswap/rzswap_run.py")
    args = json.load(open(os.path.join(HERE, "rzswap_args.json"), encoding="utf-8"))
    check("Z6 shipped args = DRY (read-only)", args["mode"] == "DRY" and core.validate_args(args)[0] == "DRY")
    check("Z7 the write sets only panels (write_panels is the only Show write; no interval/gap/settings setter)",
          src.count('set_editor_property("cues"') == 2 and "interval_to_next\", " not in src.split("def write_panels")[1].split("def restore_pristine")[0]
          and "passage_settings\"," not in src)
    rep = {"checks": RESULTS, "passed": sum(r["pass"] for r in RESULTS), "failed": sum(not r["pass"] for r in RESULTS)}
    with open(os.path.join(HERE, "test_rzswap_offline_report.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=1)
    print("RESULT %d passed, %d failed" % (rep["passed"], rep["failed"]))
    return 0 if rep["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
