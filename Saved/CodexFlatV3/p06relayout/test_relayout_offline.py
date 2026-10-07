"""Offline harness for relayout_core.py + relayout_apply.py orchestration (system Python; no Unreal).

  python test_relayout_offline.py            -> prints PASS/FAIL per check, writes test_relayout_offline_report.json

A FakeOps stands in for UnrealOps. It holds a fake Show (217 foreign cues, the 64 recorded P06 rows from
../topple/topple_measurements.json, 3 trailing scene cues), emulates the compiler's run rule (maximal ENABLED run,
settings matched by exact First/Last guid -- InfinityStageCompiler.cpp:81-89, :200-246) and exports struct-like text
that topple_core.fields parses. Every gate gets a NEGATIVE control (a fault injected -> the named refusal) next to the
POSITIVE run. What this harness cannot prove [inf]: that the Unreal Python property names / import_text / set_panel
behave as the fake does -- the live DRY + APPLY read-backs exist for that.
"""
import copy
import importlib.util
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOPPLE = os.path.normpath(os.path.join(HERE, "..", "topple"))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


core = _load("rl_core_t", os.path.join(HERE, "relayout_core.py"))
tc = _load("tc_core_t", os.path.join(TOPPLE, "topple_core.py"))
ra = _load("rl_apply_t", os.path.join(HERE, "relayout_apply.py"))
mp = _load("rl_make_plan_t", os.path.join(HERE, "make_plan.py"))

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


# =====================================================================================================================
# Fake Show / editor
# =====================================================================================================================

WIDTH = {}


def mesh_width(path):
    if path is None:
        return 0.0
    name = path.rsplit("/", 1)[-1]
    for k, d in core.DESIGNS.items():
        if d["width_cm"] and d["slug"] in name:
            return float(d["width_cm"])
    return 600.0


def ftext(v):
    return repr(float(v))


class FakeOps:
    def __init__(self, meas, exists=None):
        self.logs, self.errors = [], []
        self.saved = []
        self.dirty = {"content": [], "maps": []}
        self.pie = False
        self.zz = []
        self.topple = None
        self.pins = {"wing_pins": [], "relative_pins": []}
        self.exists_fn = exists or mp.sim_exists
        self.bug = None
        self.materialized = 64
        self.written = False
        cues = [{"guid": "F%031d" % i, "label": "Other %d" % i, "enabled": True, "wp": False} for i in range(217)]
        for r in meas["rows"]:
            pan = {}
            for s in ("L", "R"):
                sd = r["sides"][s]
                inner = sd["lateral_max_cm"] if s == "L" else sd["lateral_min_cm"]
                pan[s] = {"mesh": sd["mesh"], "material_overrides": [],
                          "local_transform": {"location": [0.0, float(inner), 0.0], "rotation": [0.0, 0.0, 0.0],
                                              "scale": [1.0, 1.0, 1.0]},
                          "facing_policy": "AUTO_BY_ROLE", "flip_image_horizontally": False}
            cues.append({"guid": r["cue_guid"], "label": r["label"], "enabled": True, "wp": True,
                         "interval": int(r["interval_ticks"]), "gap": float(r["gap_cm"]),
                         "L": pan["L"], "R": pan["R"], "mech": r["mechanism_export"][:80], "mask": 0,
                         "atts": ["Light %s" % r["label"]]})
        cues += [{"guid": "E%031d" % i, "label": "Scene %d" % i, "enabled": True, "wp": False} for i in range(3)]
        self.cues = cues
        pts = meas["law"]["points"]
        self.settings = [{"guid": "A" * 32, "first": "F" + "0" * 31, "last": "F" + "0" * 31, "lead_f": 0, "lead_cm": 0.0,
                          "tail_f": 0, "tail_cm": 0.0},
                         {"guid": core.P06_GUID, "first": meas["rows"][0]["cue_guid"], "last": meas["rows"][-1]["cue_guid"],
                          "lead_f": int(pts[1][0]), "lead_cm": float(pts[1][1]),
                          "tail_f": int(pts[-1][0] - pts[-2][0]), "tail_cm": float(pts[-1][1] - pts[-2][1])}]
        self.texts = {}

    # ---- text
    def _ptext(self, p):
        return "(Mesh=\"%s\",Y=%s,Facing=%s,Flip=%s)" % (p["mesh"], ftext(p["local_transform"]["location"][1]),
                                                         p["facing_policy"], p["flip_image_horizontally"])

    def _ctext(self, c):
        if not c["wp"]:
            return "(CueGuid=%s,Label=\"%s\",bEnabled=%s)" % (c["guid"], c["label"], "True" if c["enabled"] else "False")
        return ("(CueGuid=%s,Label=\"%s\",bEnabled=%s,WingPair=(Left=%s,Right=%s,IntervalToNext=(Value=%d),"
                "GapToNextCm=%s,Mechanism=(Kind=%s),LocalOverrideMask=%d,Attachments=(\"%s\")))" % (
                    c["guid"], c["label"], "True" if c["enabled"] else "False", self._ptext(c["L"]), self._ptext(c["R"]),
                    c["interval"], ftext(c["gap"]), c["mech"].replace("(", "[").replace(")", "]").replace(",", ";"),
                    c["mask"], ";".join(c["atts"])))

    def _stext(self, s):
        return ("(PassageGuid=%s,FirstCueGuid=%s,LastCueGuid=%s,LeadInFrames=(Value=%d),LeadInDistanceCm=%s,"
                "TailFrames=(Value=%d),TailDistanceCm=%s)" % (s["guid"], s["first"], s["last"], s["lead_f"],
                                                             ftext(s["lead_cm"]), s["tail_f"], ftext(s["tail_cm"])))

    def cue_texts(self):
        out = []
        for c in self.cues:
            t = self._ctext(c)
            self.texts[t] = copy.deepcopy(c)
            out.append(t)
        return out

    def settings_texts(self):
        out = []
        for s in self.settings:
            t = self._stext(s)
            self.texts[t] = copy.deepcopy(s)
            out.append(t)
        return out

    # ---- context
    def log(self, m):
        self.logs.append(m)

    def log_error(self, m):
        self.errors.append(m)

    def guard_context(self):
        if self.pie:
            raise core.PlanError("PIE_OR_SIE_ACTIVE (refused; this tool never ends PIE)")

    def census(self):
        return copy.deepcopy(self.dirty)

    def zz_actors(self):
        return list(self.zz)

    def topple_active(self):
        return self.topple

    # ---- compiler emulation
    def _runs(self):
        runs, i = [], 0
        while i < len(self.cues):
            c = self.cues[i]
            if not c["enabled"] or not c["wp"]:
                i += 1
                continue
            j = i
            while j + 1 < len(self.cues) and self.cues[j + 1]["enabled"] and self.cues[j + 1]["wp"]:
                j += 1
            runs.append((i, j))
            i = j + 1
        return runs

    def _p06_run(self):
        st = self.settings[1]
        for i, j in self._runs():
            if self.cues[i]["guid"] == st["first"] and self.cues[j]["guid"] == st["last"]:
                return i, j
        raise core.PlanError("FAKE_COMPILER: P06 settings match no run (First/Last exact match failed)")

    def read_p06(self):
        i, j = self._p06_run()
        rows = []
        for k in range(i, j + 1):
            c = self.cues[k]
            t = self._ctext(c)
            rows.append({"cue_guid": c["guid"], "label": c["label"], "show_index": k, "enabled": c["enabled"],
                         "interval_ticks": c["interval"], "gap_cm": c["gap"], "L_mesh": c["L"]["mesh"],
                         "R_mesh": c["R"]["mesh"], "L_panel": copy.deepcopy(c["L"]), "R_panel": copy.deepcopy(c["R"]),
                         "mechanism_sha": c["mech"], "attachments": [{"label": a, "kind": "LIGHT"} for a in c["atts"]],
                         "text_outside_mechanism_sha": ra._sha(tc.cue_text_outside_mechanism(t))})
        st = self.settings[1]
        sd = {"lead_in_frames": st["lead_f"], "lead_in_distance_cm": st["lead_cm"], "tail_frames": st["tail_f"],
              "tail_distance_cm": st["tail_cm"], "first_cue_guid": st["first"], "last_cue_guid": st["last"]}
        return rows, sd, {"label": "Passage 6", "fit_mode": "MUSIC_LOCKED_DERIVE_COUNT", "tick": 24000.0}

    def segments(self):
        out, cur = [], 0
        for i, j in self._runs():
            if i < 217:
                continue
            st = self.settings[1]
            if not (self.cues[i]["guid"] == st["first"] and self.cues[j]["guid"] == st["last"]):
                out.append(["UNMATCHED_RUN", i, j])
                continue
            length = st["lead_f"] + sum(self.cues[k]["interval"] for k in range(i, j)) + st["tail_f"]
            out.append(["Passage 6", 1000, 1000 + length])
        if self.bug == "segments" and self.written:
            out.append(["EXTRA", 0, 1])
        return out

    def asset_exists(self, path):
        return self.exists_fn(path)

    def _bounds(self, panel, side):
        y = panel["local_transform"]["location"][1]
        w = mesh_width(panel["mesh"])
        return {"min_y_cm": y - w, "max_y_cm": y} if side == "L" else {"min_y_cm": y, "max_y_cm": y + w}

    def placements(self, plan_rows, live_rows):
        live = {r["cue_guid"]: r for r in live_rows}
        out = {}
        for r in plan_rows:
            for side in ("L", "R"):
                s = r["sides"][side]
                if s["action"] != "swap":
                    continue
                old = self._bounds(live[r["cue_guid"]][side + "_panel"], side)
                zero = self._bounds(core.planned_panel(s["mesh"], 0.0), side)
                y = core.inner_edge_y(side, old, zero)
                p = core.planned_panel(s["mesh"], y)
                out["%s|%s" % (r["cue_guid"], side)] = {"panel": p}
        return out

    def panel_matches(self, a, e):
        return a["mesh"] == e["mesh"] and abs(a["local_transform"]["location"][1] - e["local_transform"]["location"][1]) < 1e-3 \
            and a["flip_image_horizontally"] == e["flip_image_horizontally"] and a["facing_policy"] == e["facing_policy"]

    def master_p06_pins(self):
        return copy.deepcopy(self.pins)

    def structure_06(self):
        return [{"label": "Infinity Stage - Structure 06", "current": self.materialized == 64}]

    def world_edges(self, guids):
        i, j = self._p06_run()
        out = {}
        for k in range(i, j + 1):
            c = self.cues[k]
            if c["guid"] not in guids:
                continue
            for s in ("L", "R"):
                b = self._bounds(c[s], s)
                if self.bug == "mirror" and "_real_" in str(c[s]["mesh"]):   # world frame mirrored vs the Show's frame
                    b = {"min_y_cm": -b["max_y_cm"], "max_y_cm": -b["min_y_cm"]}
                out["%s|%s" % (c["guid"], s)] = {"inner_cm": b["max_y_cm"] if s == "L" else b["min_y_cm"],
                                                 "route_mid_cm": float(k), "mesh": c[s]["mesh"]}
        return out

    def materialized_count(self):
        return self.materialized

    # ---- writes
    def write_layout(self, plan, placements):
        first, n = plan["first_show_index"], plan["count_old"]
        by = {c["guid"]: c for c in self.cues[first:first + n]}
        kept = []
        for r in plan["rows"]:
            c = copy.deepcopy(by[r["cue_guid"]])
            if r["interval_ticks"] is not None:
                c["interval"], c["gap"] = int(r["interval_ticks"]), float(r["gap_cm"])
            for s in ("L", "R"):
                if r["sides"][s]["action"] == "swap":
                    c[s] = copy.deepcopy(placements["%s|%s" % (r["cue_guid"], s)]["panel"])
            if self.bug == "mechanism" and r["role"] == "chain3":
                c["mech"] = c["mech"] + "X"
            kept.append(c)
        dropped = []
        for d in plan["dropped"]:
            c = copy.deepcopy(by[d["cue_guid"]])
            c["enabled"] = False
            dropped.append(c)
        if self.bug == "interleave":
            kept, dropped = kept[:5] + dropped[:1] + kept[5:], dropped[1:]
        self.cues = self.cues[:first] + kept + dropped + self.cues[first + n:]
        # reconcile + explicit LastCueGuid
        self.settings[1]["last"] = kept[-1]["guid"]
        self.written = True
        self.dirty = {"content": [core.SHOW_PATH], "maps": []}

    def restore(self, originals):
        first = originals["first_show_index"]
        rest = [copy.deepcopy(self.texts[t]) for t in originals["p06_cue_texts"]]
        self.cues = self.cues[:first] + rest + self.cues[first + len(rest):]
        self.settings = [copy.deepcopy(self.texts[t]) for t in originals["settings_texts"]]
        self.dirty = {"content": [core.SHOW_PATH], "maps": []}

    def materialize(self):
        i, j = self._p06_run()
        self.materialized = j - i + 1
        self.dirty["maps"] = [core.WORLD_PATH]
        return True

    def backup(self, name):
        return os.path.join(tempfile.gettempdir(), name), ["show", "umap"]

    def save_show(self):
        self.saved.append("show")
        self.dirty["content"] = []
        return True

    def save_level(self):
        self.saved.append("level")
        self.dirty["maps"] = []
        return True


# =====================================================================================================================
# Tests
# =====================================================================================================================

def fresh(meas, **kw):
    ops = FakeOps(meas, **kw)
    d = tempfile.mkdtemp(prefix="p06rl_")
    return ops, d


def dry(ops, d, args=None):
    a = {"mode": "DRY", "confirm": "DRY P06RELAYOUT"}
    a.update(args or {})
    return ra.run_dry(ops, core, a, "P06RL-TEST-DRY", d)


def apply_args(plan, **kw):
    a = {"mode": "APPLY", "confirm": "APPLY P06RELAYOUT " + plan["confirm_token"], "decided_by": "test",
         "attachments_ack": "DROPPED_ROWS_GO_DARK_KEPT_ROWS_MOVE", "structure_ack": "STRUCTURE_06_LEFT_STALE"}
    a.update(kw)
    return a


def main():
    with open(os.path.join(TOPPLE, "topple_measurements.json"), "r", encoding="utf-8") as fh:
        meas = json.load(fh)

    # ---- T1 compiler facts the design rests on (fake compiler mirrors InfinityStageCompiler.cpp:200-246)
    ops, d = fresh(meas)
    ops.cues[217 + 10]["enabled"] = False
    check("T1 NEG disabling a row IN PLACE splits P06 (why rows are moved, not disabled in place)",
          len([r for r in ops._runs() if r[0] >= 217]) == 2 and ["UNMATCHED_RUN", 228, 280] in ops.segments(),
          ops._runs()[-2:])
    ops, d = fresh(meas)
    check("T1 POS live P06 is one run of 64", ops._p06_run() == (217, 280))

    # ---- T2 plan gates (pure)
    rows, sd, _ = ops.read_p06()
    plan = core.build_plan(rows, sd, exists=mp.sim_exists)
    check("T2 POS plan gates pass", not plan["refusals"], plan["refusals"])
    check("T2 POS 64 -> 29 rows, 35 dropped, keeper kept", plan["count_new"] == 29 and len(plan["dropped"]) == 35 and
          core.KEEPER_GUID in plan["new_order"][:29])
    check("T2 POS duration unchanged (segment end rel 3024027)", plan["segment_end_rel"] == 3024027, plan["segment_end_rel"])
    check("T2 POS camera law within 0.5 cm of the old law", plan["camera_law_max_dev_cm"] < 0.5, plan["camera_law_max_dev_cm"])
    check("T2 POS every interval = gap * 96", all(r["interval_ticks"] == r["gap_cm"] * 96 for r in plan["rows"][:-1]))
    check("T2 POS no cut design and no IND piece in the chain", all(
        not core.is_cut(r["sides"][s].get("mesh")) for r in plan["rows"] for s in ("L", "R")) and all(
        not core.is_ind(r["sides"]["L"]["mesh"]) for r in plan["rows"] if r["role"] in core.CHAIN_ROLES))
    check("T2 POS handedness: every swapped mesh name carries its slot side", all(
        ("_%s_t5" % s) in r["sides"][s]["mesh"] for r in plan["rows"] for s in ("L", "R") if r["sides"][s]["action"] == "swap"))
    check("T2 POS every IND row that blocked the old chain region is gone from 9.6-13.4 m... (no IND inside chain span)",
          not [r for r in plan["rows"] if 10450 <= r["station_cm"] <= 12950 and
               any(core.is_ind(r["sides"][s]["mesh"]) for s in ("L", "R"))])
    lay = copy.deepcopy(core.LAYOUT)
    lay[3]["station_cm"] = 2951
    p2 = core.build_plan(rows, sd, layout=lay, exists=mp.sim_exists)
    check("T2 NEG moving one station by 1 cm keeps the sum (still passes) -- control", not p2["refusals"], p2["refusals"])
    lay = copy.deepcopy(core.LAYOUT)
    lay[-1]["station_cm"] = 27200
    p2 = core.build_plan(rows, sd, layout=lay, exists=mp.sim_exists)
    check("T2 NEG last station moved -> ENDPOINT + duration refusal", any("ENDPOINT" in x for x in p2["refusals"]) and
          any("INTERVAL_SUM" in x for x in p2["refusals"]), p2["refusals"])
    lay = copy.deepcopy(core.LAYOUT)
    lay[0]["L"] = [core.KEEP]
    p2 = core.build_plan(rows, sd, layout=lay, exists=mp.sim_exists)
    check("T2 NEG KEEP on a grand_pavilion side -> CUT_DESIGN_STILL_STANDING",
          any("CUT_DESIGN_STILL_STANDING" in x for x in p2["refusals"]), p2["refusals"])
    lay = copy.deepcopy(core.LAYOUT)
    lay[2]["L"] = ["2"]          # pink was BUILT R
    p2 = core.build_plan(rows, sd, layout=lay, exists=mp.sim_exists)
    check("T2 NEG R-built design in an L slot never resolves (no flip)",
          any("NO_ASSET" in x and "BUILT_FOR_R" in x for x in p2["refusals"]), p2["refusals"])
    p2 = core.build_plan(rows, sd, exists=lambda p: False)
    check("T2 NEG no assets imported -> NO_ASSET refusals", sum("NO_ASSET" in x for x in p2["refusals"]) > 20)
    lay = [x for x in core.LAYOUT if x["role"] != "keeper"]
    lay[-2]["station_cm"] = lay[-2]["station_cm"]
    p2 = core.build_plan(rows, sd, layout=lay, exists=mp.sim_exists)
    check("T2 NEG keeper dropped -> KEEPER_DROPPED", any("KEEPER_DROPPED" in x for x in p2["refusals"]), p2["refusals"])
    lay = copy.deepcopy(core.LAYOUT)
    lay[17]["L"] = ["33"]
    p2 = core.build_plan(rows, sd, layout=lay, exists=mp.sim_exists)
    check("T2 NEG keeper mesh change refused", any("KEEPER_MESH_CHANGE" in x for x in p2["refusals"]), p2["refusals"])
    lay = copy.deepcopy(core.LAYOUT)
    lay[13], lay[16] = lay[16], lay[13]
    p2 = core.build_plan(rows, sd, layout=lay, exists=mp.sim_exists)
    check("T2 NEG chain order broken / not consecutive refused", any("CHAIN" in x or "STATIONS" in x for x in p2["refusals"]),
          p2["refusals"])
    only_j = lambda p: "/T5J/" in p and mp.sim_exists(p.replace("_t5j", "_t5p").replace("/T5J/", "/T5P/")) or \
        (p.endswith("_t5j") and "7_draped_marble" in p)
    p2 = core.build_plan(rows, sd, exists=lambda p: mp.sim_exists(p) and "/T5J/" in p)
    check("T2 POS t5j fallback resolves when only T5J was imported", not p2["refusals"] and all(
        "/T5J/" in r["sides"][s]["mesh"] for r in p2["rows"] for s in ("L", "R") if r["sides"][s]["action"] == "swap"),
        p2["refusals"])
    check("T2 POS a later rebuild of 29 (veil) is taken in chain5 if it lands L",
          core.build_plan(rows, sd, exists=lambda p: mp.sim_exists(p) or p.endswith("29_metal_panel_with_L_t5p")
                          )["rows"][14]["sides"]["L"]["design"] == "29")

    # ---- T3 args
    expect_stop("T3 NEG confirm mismatch", lambda: core.validate_args({"mode": "DRY", "confirm": "DRY"}), "CONFIRM_MISMATCH")
    pl = dict(plan, gates_ok=True)
    expect_stop("T3 NEG APPLY without decided_by", lambda: core.validate_args(
        dict(apply_args(pl), decided_by=""), pl), "NOT_DECIDED")
    expect_stop("T3 NEG APPLY without attachments ack", lambda: core.validate_args(
        dict(apply_args(pl), attachments_ack=None), pl), "ATTACHMENTS_NOT_ACKED")
    expect_stop("T3 NEG APPLY without structure ack", lambda: core.validate_args(
        dict(apply_args(pl), structure_ack=None), pl), "STRUCTURE_NOT_ACKED")
    expect_stop("T3 NEG APPLY on failed gates", lambda: core.validate_args(apply_args(dict(pl, gates_ok=False)),
                                                                          dict(pl, gates_ok=False)), "PLAN_GATES_FAILED")
    check("T3 POS APPLY args accepted", core.validate_args(apply_args(pl), pl) == "APPLY")

    # ---- T4 DRY
    ops, d = fresh(meas)
    ops.dirty = {"content": ["/Game/Other"], "maps": []}
    expect_stop("T4 NEG dirty census at start", lambda: dry(ops, d), "DIRTY_CENSUS")
    ops, d = fresh(meas)
    ops.pie = True
    expect_stop("T4 NEG PIE running", lambda: dry(ops, d), "PIE_OR_SIE_ACTIVE")
    ops, d = fresh(meas)
    ops.topple = {"run_id": "TOPPLE-20261007-024333"}
    p = dry(ops, d)
    check("T4 NEG topple ACTIVE present -> DRY gate fails", not p["gates_ok"] and any(
        "TOPPLE_ACTIVE_PRESENT" in x for x in p["refusals"]), p["refusals"])
    ops, d = fresh(meas)
    ops.pins = {"wing_pins": [meas["rows"][5]["cue_guid"]], "relative_pins": []}
    p = dry(ops, d)
    check("T4 NEG Master wing pin on a P06 row -> refusal", any("MASTER_WING_PIN" in x for x in p["refusals"]), p["refusals"])
    ops, d = fresh(meas)
    p = dry(ops, d)
    check("T4 POS DRY gates ok, placements for every swap", p["gates_ok"] and len(p["placements"]) == p["swaps"],
          p["refusals"])
    check("T4 POS DRY left the editor clean", ops.census() == {"content": [], "maps": []})
    check("T4 POS DRY inventories attachments (kept/dropped)", p["attachment_counts"] == {"kept_rows": 29, "dropped_rows": 35},
          p["attachment_counts"])
    check("T4 POS DRY marker", any("FLATV3_P06RELAYOUT_DRY_OK" in m for m in ops.logs))

    # ---- T5 APPLY negatives
    def apply_with(ops, d, plan, **kw):
        return ra.run_apply(ops, core, tc, apply_args(plan, **kw), plan, "P06RL-TEST-APPLY", d)

    ops, d = fresh(meas)
    p = dry(ops, d)
    ops.topple = {"run_id": "TOPPLE-X"}
    expect_stop("T5 NEG APPLY with topple ACTIVE", lambda: apply_with(ops, d, p), "TOPPLE_ACTIVE_PRESENT")
    ops, d = fresh(meas)
    p = dry(ops, d)
    ops.cues[217 + 40]["label"] = "edited after DRY"
    expect_stop("T5 NEG live P06 edited after DRY -> PLAN_STALE", lambda: apply_with(ops, d, p), "PLAN_STALE")
    ops, d = fresh(meas)
    p = dry(ops, d)
    ops.cues[217 + 40]["mech"] += "STILL"
    try:
        apply_with(ops, d, p)
        ok = True
    except core.PlanError as exc:
        ok = str(exc)
    check("T5 POS a mechanism-only change after DRY (topple REVERT/STILL) does NOT stale the plan", ok is True, ok)
    ops, d = fresh(meas)
    p = dry(ops, d)
    ops.exists_fn = lambda path: mp.sim_exists(path) and "26_concrete" not in path
    expect_stop("T5 NEG asset deleted after DRY -> refused before any write", lambda: apply_with(ops, d, p), "LIVE_PLAN_REFUSED")
    check("T5 NEG ... and nothing written", ops.saved == [] and not os.path.exists(os.path.join(d, ra.ACTIVE_NAME)))
    for bug, token in (("mechanism", "KEPT_ROW_CHANGED_OUTSIDE_PLAN"), ("interleave", "READBACK_RAISED"),
                       ("mirror", "WORLD_EDGE_PROBE"), ("segments", "COMPILED_SEGMENTS_CHANGED")):
        ops, d = fresh(meas)
        p = dry(ops, d)
        before = ops.cue_texts()
        ops.bug = bug
        msg = expect_stop("T5 NEG injected write fault '%s' -> %s" % (bug, token), lambda: apply_with(ops, d, p), token)
        check("T5 NEG '%s' rolled back in memory, nothing saved" % bug,
              ops.saved == [] and ops.cue_texts() == before and msg is not None and "in-memory restore=True" in msg, msg)

    # ---- T6 APPLY positive + REVERT
    ops, d = fresh(meas)
    before = ops.cue_texts()
    before_set = ops.settings_texts()
    seg_before = ops.segments()
    p = dry(ops, d)
    probe = apply_with(ops, d, p)
    after = ops.cue_texts()
    rows2, sd2, _ = ops.read_p06()
    check("T6 POS APPLY marker + Show and level saved", any("APPLY_OK" in m for m in ops.logs) and ops.saved == ["show", "level"])
    check("T6 POS compiled P06 = 29 rows in plan order", [r["cue_guid"] for r in rows2] == p["new_order"][:29])
    check("T6 POS segments unchanged (whole show)", ops.segments() == seg_before)
    check("T6 POS non-P06 cues byte-identical", after[:217] == before[:217] and after[281:] == before[281:])
    check("T6 POS dropped cues disabled behind the run", all(not c["enabled"] for c in ops.cues[217 + 29:281]))
    check("T6 POS last cue guid = Wing 055", sd2["last_cue_guid"] == "07E24048F24647AA7D5992AB6A8A0770")
    check("T6 POS edge probe: swaps 0 cm, controls 0 cm", all(abs(x["inner_delta_cm"]) < 1e-6 for x in probe) and
          sum(x["control"] for x in probe) > 0, probe[:2])
    check("T6 POS keeper text unchanged except gap/interval",
          ra.blank_kept(tc, after[217 + 17], []) == ra.blank_kept(tc, [t for t in before if core.KEEPER_GUID in t][0], []))
    expect_stop("T6 NEG second APPLY refused while ACTIVE", lambda: apply_with(ops, d, p), "UNREVERTED_APPLY_EXISTS")
    orig = ra._read_json(ra._read_json(os.path.join(d, ra.ACTIVE_NAME))["originals"])
    ops.topple = {"run_id": "TOPPLE-CHAIN"}
    expect_stop("T6 NEG REVERT refused while topple ACTIVE", lambda: ra.run_revert(ops, core, tc, {}, orig, "R1", d),
                "TOPPLE_ACTIVE_PRESENT")
    ops.topple = None
    ops.cues[217 + 3]["label"] = "drift"
    expect_stop("T6 NEG REVERT refused on drift since APPLY", lambda: ra.run_revert(ops, core, tc, {}, orig, "R2", d),
                "DRIFT_SINCE_APPLY")
    ops.cues[217 + 3]["label"] = [x for x in p["rows"] if x["new_ordinal"] == 3][0]["label"]
    ops.saved = []
    ra.run_revert(ops, core, tc, {}, orig, "R3", d)
    check("T6 POS REVERT restores every cue text and settings exactly", ops.cue_texts() == before and
          ops.settings_texts() == before_set and ops.segments() == seg_before)
    check("T6 POS REVERT marker, ACTIVE removed", any("REVERT_OK" in m for m in ops.logs) and
          not os.path.exists(os.path.join(d, ra.ACTIVE_NAME)))

    # ---- T7 topple will find the chain on the planned layout (offline, both height readings)
    offline = mp.json.load(open(os.path.join(HERE, "relayout_plan_offline.json"), encoding="utf-8")) \
        if os.path.exists(os.path.join(HERE, "relayout_plan_offline.json")) else None
    check("T7 offline plan present (run make_plan.py first)", offline is not None)
    if offline:
        for hm in ("socket", "bounds"):
            c = offline["topple_offline_check"][hm]["make_keys"]
            ex = c["explicit"]
            check("T7 POS [%s] make_keys --keeper 17 --candidate 10: gates ok, braced on Wing 012" % hm,
                  ex.get("gates_ok") and ex.get("brace") == "P06 Wing 012" and ex.get("start_ordinal") == 10, ex)
            check("T7 POS [%s] final slam 37.0 s, lead 25-35 m" % hm,
                  abs(ex["final_impact_s"] - 37.0) < 0.05 and 25 <= ex["lead_m"] <= 35, (ex["final_impact_s"], ex["lead_m"]))
            check("T7 POS [%s] auto window picks the same chain" % hm, c["auto"].get("start_ordinal") == 10, c["auto"])
            check("T7 NEG [%s] WITHOUT --keeper, make_keys picks a chain row as keeper and refuses" % hm,
                  "CANDIDATE_NOT_ELIGIBLE" in str(c["default_keeper"].get("error")), c["default_keeper"])
    rep = {"checks": RESULTS, "passed": sum(r["pass"] for r in RESULTS), "failed": sum(not r["pass"] for r in RESULTS)}
    with open(os.path.join(HERE, "test_relayout_offline_report.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=1)
    print("RESULT %d passed, %d failed" % (rep["passed"], rep["failed"]))
    return 0 if rep["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
