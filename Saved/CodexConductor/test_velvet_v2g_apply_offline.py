"""Offline harness for velvet_v2g_apply.py (system Python; no Unreal, no MCP). Written 6 Oct 2026.

Drives the tool's real orchestration (execute / run_dry / run_apply / run_revert / run_verify) through a FAKE adapter
that models: spawnable-template GeometryCache components in six sequences, optional level actors, the asset-registry
referencers of GC_CurtainDrop_Opening, material instances with override flags, the dirty-package census, saves and an
event log (to prove ordering). Every gate is paired with a failing CONTROL that must be caught.

Checks (each PASS/FAIL line names the claim):
  static    no delete/destroy/remove calls, no Save All, no unreal import at module level, the Drop MI and the cache
            are never write targets, pinned V2G == velvet_v2_bench_variants.json, pinned parameter names ==
            velvet_v2_build.py SCALARS/VECTORS/TEX (parsed with ast, not imported);
  planning  canonical census -> 11 SWAP targets, digest stable; refusals for FOREIGN override, missing expected
            target, unhandled referencer, slot mismatch, variant drift, MI exists-different, dirty start, PIE,
            Sequencer open, ZZ_ actor, wrong confirm, digest drift, empty decided_by, existing record;
  record    written (O_EXCL) BEFORE the first mutation, holds every before value as asset paths; backups hold the level
            and every touched sequence;
  apply     saves exactly the MI + six sequences (no map unless a level target exists), read-back passes, Drop MI and
            the cache untouched; a setter that LIES (False after success) passes, one that silently FAILS is caught
            and nothing is saved; a foreign dirty package stops the save;
  revert    restores every override list EXACTLY (incl. [None] and [Drop MI] befores), skips targets already at
            before, refuses DRIFT, renames the record; partial-apply revert renames .unapplied and writes nothing;
  verify    passes after APPLY, fails before.
Run: python Saved/CodexConductor/test_velvet_v2g_apply_offline.py   (exit 0 only if every check passes)
"""
import ast
import copy
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL_PATH = os.path.join(HERE, "velvet_v2g_apply.py")
BUILDER = os.path.join(HERE, "velvet_v2_build.py")
VARIANTS = os.path.join(HERE, "velvet_v2_bench_variants.json")

spec = importlib.util.spec_from_file_location("velvet_v2g_apply_under_test", TOOL_PATH)
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)                      # no VV2G_ARGS global -> no autorun, no unreal import

RESULTS = []
TMP = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  -- %s" % (detail,)))


# ============================================================================ fake adapter
PARENT_VALUES = {"SheenAmount": 1.0, "RimLift": 0.35, "NapExponent": 3.0, "FoldDarken": 0.55, "Roughness": 0.88,
                 "Specular": 0.3, "PileNormalStrength": 0.6, "PileScale": 0.5, "CrushAmount": 0.35, "CrushScale": 0.6,
                 "CrushNormalStrength": 0.25, "PatternWidthM": 37.629, "DropM": 10.0}
PARENT_VECTORS = {"BaseColour": [0.07, 0.004, 0.012, 1.0], "SheenColour": [0.32, 0.03, 0.07, 1.0]}
DROP_VALUES = {"PatternWidthM": 37.629, "DropM": 10.0}
COMP = "GeometryCacheComponent0"


class Fake:
    def __init__(self, level_actor=False):
        self.root = tempfile.mkdtemp(prefix="vv2g_")
        TMP.append(self.root)
        self._here = os.path.join(self.root, "Saved", "CodexConductor")
        os.makedirs(self._here)
        shutil.copy2(VARIANTS, os.path.join(self._here, T.VARIANTS_NAME))
        self.pie = False
        self.world = T.EXPECTED_WORLD
        self.seq_open = False
        self.zz = []
        self.dirty_c, self.dirty_m = set(), set()
        self.events = []
        self.logs = []
        self.gc_materials = 1
        self.seqs = {}
        n = 0
        for pkg, name in T.EXPECTED_TEMPLATES:
            n += 1
            guid = "%032X" % n
            self.seqs.setdefault(pkg, {})[guid] = {"binding": name, "cache": T.GC_PATH, "overrides": [],
                                                   "class": "GeometryCacheActor"}
        self.level = {}
        if level_actor:
            self.level["/Game/X.L:PersistentLevel.GeometryCacheActor_7"] = {"label": "P01 End Drape (stand-in)",
                                                                            "cache": T.GC_PATH, "overrides": [None],
                                                                            "outer": T.EXPECTED_WORLD}
        self.extra_refs = {}                      # pkg -> classes
        self.mis = {T.MI_PARENT: {"parent": "/Game/Scenes/Curtain/Chaos/Materials/M_CurtainVelvet_v2",
                                  "own_s": {"PatternWidthM": 37.629, "DropM": 10.0}, "own_v": dict(PARENT_VECTORS)},
                    T.DROP_MI: {"parent": "/Game/Scenes/Curtain/Chaos/Materials/MI_CurtainVelvet_DeepRed",
                                "own_s": dict(DROP_VALUES), "own_v": {}}}
        self.faults = {}
        for pkg in list(self.seqs) + [T.EXPECTED_WORLD]:
            f = self.content_file(pkg, ".umap" if pkg == T.EXPECTED_WORLD else ".uasset")
            os.makedirs(os.path.dirname(f), exist_ok=True)
            with open(f, "wb") as h:
                h.write(b"x" * 64)

    # environment
    def here(self):
        return self._here

    def project_dir(self):
        return self.root

    def content_file(self, path, ext=".uasset"):
        return os.path.join(self.root, "Content", *path[len("/Game/"):].split("/")) + ext

    def log(self, m):
        self.logs.append(m)

    def log_error(self, m):
        self.logs.append(m)

    def event(self, name):
        self.events.append(name)

    def pie_active(self):
        return self.pie

    def world_path(self):
        return self.world

    def sequencer_open(self):
        return self.seq_open

    def zz_actors(self):
        return list(self.zz)

    def dirty(self):
        return {"content": sorted(self.dirty_c), "maps": sorted(self.dirty_m)}

    # discovery
    def referencers(self, pkg):
        assert pkg == T.GC_PATH
        refs = [p for p, b in self.seqs.items() if any(r["cache"] == T.GC_PATH for r in b.values())]
        if any(a["cache"] == T.GC_PATH for a in self.level.values()):
            refs.append(T.EXPECTED_WORLD)
        return sorted(refs + list(self.extra_refs))

    def package_classes(self, pkg):
        if pkg in self.extra_refs:
            return self.extra_refs[pkg]
        return ["World"] if pkg == T.EXPECTED_WORLD else ["LevelSequence"]

    def asset_exists(self, path):
        return path in self.mis

    def unloadable(self, paths):
        return [p for p in paths if p not in self.mis]

    def gc_slots(self):
        return self.gc_materials

    def drop_mapping(self):
        return dict(DROP_VALUES)

    def _row(self, base, data):
        slots = self.gc_materials
        ov = list(data["overrides"])
        eff = [(ov[i] if i < len(ov) and ov[i] is not None else T.DROP_MI) for i in range(slots)]
        row = dict(base)
        row.update({"component": COMP, "cache": data["cache"], "slots": slots,
                    "component_num_materials": data.get("num", slots), "overrides": ov, "effective": eff})
        return row

    def sequence_rows(self, pkg):
        rows = []
        for guid, b in self.seqs[pkg].items():
            if b["cache"] == T.GC_PATH:
                rows.append(self._row({"kind": "template", "package": pkg, "binding": b["binding"], "guid": guid,
                                       "template_class": b["class"]}, b))
        return rows, []

    def level_rows(self):
        rows = []
        for path, a in self.level.items():
            if a["cache"] == T.GC_PATH:
                rows.append(self._row({"kind": "level", "package": T.EXPECTED_WORLD, "actor_label": a["label"],
                                       "actor_path": path}, a))
        return rows, []

    def _data(self, t):
        if t["kind"] == "template":
            return self.seqs.get(t["package"], {}).get(t["guid"])
        return self.level.get(t["actor_path"])

    def read_row(self, t):
        d = self._data(t)
        if d is None:
            return None
        if t["kind"] == "template":
            return self._row({"kind": "template", "package": t["package"], "binding": d["binding"], "guid": t["guid"]}, d)
        return self._row({"kind": "level", "package": T.EXPECTED_WORLD, "actor_label": d["label"],
                          "actor_path": t["actor_path"]}, d)

    # writes
    def set_overrides(self, t, paths):
        self.events.append("set_overrides")
        for p in paths:
            assert p is None or p in self.mis, p
        assert t["package"] != T.GC_PATH
        key = T.target_key(t)
        if self.faults.get("silent_override_fail") == key:
            pass                                               # setter "succeeds" but writes nothing
        elif self.faults.get("override_wrong_count") == key:
            self._data(t)["overrides"] = list(paths) * 2
        else:
            self._data(t)["overrides"] = list(paths)
        (self.dirty_c if t["kind"] == "template" else self.dirty_m).add(t["package"])
        if self.faults.get("foreign_dirty"):
            self.dirty_c.add("/Game/Somebody/Else")
        return False if self.faults.get("setter_lies") else None

    def create_mi(self, path, parent, scalars, vectors):
        self.events.append("create_mi")
        assert path not in (T.DROP_MI, T.MI_PARENT, T.GC_PATH)
        assert path not in self.mis
        own_s = {k: v for k, v in scalars.items() if k != self.faults.get("mi_scalar_silent_fail")}
        self.mis[path] = {"parent": parent, "own_s": own_s, "own_v": {k: list(v) for k, v in vectors.items()}}
        self.dirty_c.add(path)

    def read_mi(self, path):
        mi = self.mis.get(path)
        if mi is None:
            return None
        par = self.mis.get(mi["parent"], {"own_s": {}, "own_v": {}})
        sc = {k: mi["own_s"].get(k, par["own_s"].get(k, PARENT_VALUES[k])) for k in T.PARAM_SCALARS}
        vc = {k: mi["own_v"].get(k, par["own_v"].get(k, PARENT_VECTORS[k])) for k in T.PARAM_VECTORS}
        ov = {k: (k in mi["own_s"] or k in mi["own_v"]) for k in T.PARAM_SCALARS + T.PARAM_VECTORS + T.PARAM_TEXTURES}
        return {"parent": mi["parent"], "scalars": sc, "vectors": vc, "overridden": ov}

    def save_asset(self, path):
        self.events.append("save:" + path)
        if self.faults.get("save_fail") == path:
            return False
        self.dirty_c.discard(path)
        return True

    def save_map(self, path):
        self.events.append("save_map:" + path)
        self.dirty_m.discard(path)
        return True

    def state(self):
        return copy.deepcopy({"seqs": self.seqs, "level": self.level})


def dry(f, **extra):
    args = {"mode": "DRY"}
    args.update(extra)
    st, rep = T.execute(f, args)
    return st, rep


def apply_args(f, **extra):
    st, rep = dry(f)
    args = {"mode": "APPLY", "confirm": "APPLY V2G", "decided_by": "Gary 7 Oct (test)",
            "dry_digest": rep["plan_digest"] if isinstance(rep, dict) else None, "run_id": "TEST-APPLY"}
    args.update(extra)
    return args


def record_path(f):
    return os.path.join(f.here(), T.RECORD_NAME)


# ============================================================================ tests
def test_static():
    src = open(TOOL_PATH, encoding="utf-8").read()
    tree = ast.parse(src)

    def banned(text):
        calls = [n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
                 for n in ast.walk(ast.parse(text)) if isinstance(n, ast.Call)]
        return [c for c in calls if re.search(r"(delete|destroy|remove|rmtree|unlink|save_dirty|save_packages)",
                                              c or "", re.I)]
    bad = banned(src)
    check("STATIC: no delete/destroy/remove/rmtree/unlink/Save-All calls", not bad, bad)
    check("CONTROL static: the same scan catches a planted delete_asset / destroy_actor",
          len(banned(src + chr(10) + "unreal.EditorAssetLibrary.delete_asset('x')" + chr(10)
                     + "actor.destroy_actor()" + chr(10))) == 2)
    top_imports = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))
                   and any("unreal" in (a.name or "") for a in n.names)]
    check("STATIC: no module-level unreal import", not top_imports)
    check("STATIC: autorun only with VV2G_ARGS", 'globals().get("VV2G_ARGS") is not None' in src)
    # the Drop MI / cache are never passed to a write
    writes = re.findall(r"(create_mi|set_overrides|save_asset)\(([^)]*)\)", src)
    check("STATIC: no write call names DROP_MI or GC_PATH", not any("DROP_MI" in a or "GC_PATH" in a for _, a in writes),
          writes)
    # pinned values vs the variants file
    doc = json.load(open(VARIANTS, encoding="utf-8"))
    check("VARIANT: pinned V2G equals velvet_v2_bench_variants.json", T.variant_problems(doc) == [],
          T.variant_problems(doc))
    bad_doc = copy.deepcopy(doc)
    bad_doc["variants"]["V2G"]["scalars"]["Roughness"] = 0.8
    check("CONTROL variant: a drifted Roughness is caught", T.variant_problems(bad_doc) != [])
    bad_doc = copy.deepcopy(doc)
    bad_doc["variants"]["V2G"]["vectors"]["SheenColour"] = [0.7, 0.2, 0.18]
    check("CONTROL variant: a 3-component vector is caught", T.variant_problems(bad_doc) != [])
    # parameter names vs the builder (parsed, not imported)
    btree = ast.parse(open(BUILDER, encoding="utf-8").read())
    consts = {}
    for n in btree.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) \
                and n.targets[0].id in ("SCALARS", "VECTORS", "TEX") and isinstance(n.value, ast.Dict):
            consts[n.targets[0].id] = [k.value for k in n.value.keys]
    ok = (sorted(consts.get("SCALARS", [])) == sorted(T.PARAM_SCALARS)
          and sorted(consts.get("VECTORS", [])) == sorted(T.PARAM_VECTORS)
          and sorted(consts.get("TEX", [])) == sorted(T.PARAM_TEXTURES))
    check("PARAMS: pinned names == velvet_v2_build.py SCALARS/VECTORS/TEX", ok, consts)
    mutated = ast.parse(open(BUILDER, encoding="utf-8").read().replace('"CrushNormalStrength": (', '"CrushNormalStr": ('))
    mc = [k.value for n in mutated.body if isinstance(n, ast.Assign) and len(n.targets) == 1
          and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "SCALARS" for k in n.value.keys]
    check("CONTROL params: a renamed builder parameter is caught by the same comparison",
          mc and sorted(mc) != sorted(T.PARAM_SCALARS))
    check("PARAMS: V2G keys and Drop-inherited keys are disjoint",
          not (set(T.INHERITED_FROM_DROP) & (set(T.V2G_SCALARS) | set(T.V2G_VECTORS))))


def test_dry():
    f = Fake()
    before = f.state()
    st, rep = dry(f)
    check("DRY: status DRY with no refusals", st == "DRY" and rep["refusals"] == [], (st, rep.get("refusals")))
    check("DRY: 11 targets, all SWAP, each listed with its current overrides and effective material",
          len(rep["targets"]) == 11 and all(t["state"] == "SWAP" and t["overrides"] == [] and
                                            t["effective"] == [T.DROP_MI] for t in rep["targets"]), rep["counts"])
    check("DRY: touched = the six sequences, no map", rep["touched"] == {
        "content": sorted({p for p, _ in T.EXPECTED_TEMPLATES}), "maps": []}, rep["touched"])
    check("DRY: mutated nothing (state, dirty, no write events)", f.state() == before and not f.events
          and f.dirty() == {"content": [], "maps": []})
    check("DRY: report files written", os.path.isfile(os.path.join(f.here(), T.DRY_NAME)))
    check("DRY: marker VV2G_DRY_OK", any(m.startswith("VV2G_DRY_OK|") for m in f.logs), f.logs)
    _, rep2 = dry(Fake())
    check("DRY: digest stable across identical censuses", rep2["plan_digest"] == rep["plan_digest"])

    # controls: each must turn into a refusal
    def refused(mutate, code):
        g = Fake()
        mutate(g)
        st, r = dry(g)
        hit = st == "DRY" and any(x.startswith(code) for x in r["refusals"])
        if st == "STOPPED":
            hit = code in r
        check("CONTROL DRY: %s is refused" % code, hit, (st, r if st == "STOPPED" else r["refusals"]))
    first = T.EXPECTED_TEMPLATES[0][0]
    refused(lambda g: next(iter(g.seqs[first].values())).update(overrides=["/Game/Curtain/MI_CurtainImage_P01"]),
            "FOREIGN_OVERRIDE")
    i3 = "%s/%s" % (T.SEQ_DIR, T.INTERACTION_SEQS[3])
    refused(lambda g: [g.seqs[i3].pop(k) for k, v in list(g.seqs[i3].items()) if v["binding"] == T.HANGAR_DRAPE],
            "EXPECTED_TARGET_MISSING")
    refused(lambda g: g.extra_refs.update({"/Game/Bench/L_MaterialBench": ["World"]}), "UNHANDLED_REFERENCER")
    refused(lambda g: next(iter(g.seqs[first].values())).update(num=2), "SLOT_MISMATCH")
    refused(lambda g: g.mis.update({T.MI_V2G: {"parent": T.MI_PARENT, "own_s": {"Roughness": 0.5}, "own_v": {}}}),
            "MI_EXISTS_DIFFERENT")
    def drift(g):
        d = json.load(open(VARIANTS, encoding="utf-8"))
        d["variants"]["V2G"]["scalars"]["RimLift"] = 0.3
        json.dump(d, open(os.path.join(g.here(), T.VARIANTS_NAME), "w", encoding="utf-8"))
    refused(drift, "VARIANT_DRIFT")
    refused(lambda g: setattr(g, "pie", True), "GATES")
    refused(lambda g: setattr(g, "seq_open", True), "GATES")
    refused(lambda g: g.zz.append("ZZ_MaterialBench_Drape"), "GATES")
    refused(lambda g: setattr(g, "world", "/Game/Other"), "GATES")
    # an ignored referencer passes, with its reason in notes
    g = Fake()
    g.extra_refs["/Game/Bench/L_MaterialBench"] = ["World"]
    st, r = dry(g, ignore_referencers={"/Game/Bench/L_MaterialBench": "bench map, not shown"})
    check("DRY: an ignored referencer is a note, not a refusal",
          r["refusals"] == [] and any(n.startswith("UNHANDLED_IGNORED") for n in r["notes"]), r["refusals"])
    # a pre-existing Drop-MI override is SWAP (replaceable)
    g = Fake()
    next(iter(g.seqs[first].values()))["overrides"] = [T.DROP_MI]
    st, r = dry(g)
    check("DRY: a [Drop MI] override is SWAP", r["refusals"] == [] and r["counts"]["SWAP"] == 11)


def test_apply_happy():
    f = Fake()
    pre = f.state()
    args = apply_args(f)
    st, out = T.execute(f, args)
    check("APPLY: status APPLIED", st == "APPLIED", (st, out, f.logs[-2:]))
    if st != "APPLIED":
        return None, None
    ev = f.events
    first_write = min(i for i, e in enumerate(ev) if e in ("create_mi", "set_overrides"))
    check("RECORD: written before the first mutation", "record_written" in ev and ev.index("record_written") < first_write, ev)
    rec = json.load(open(record_path(f), encoding="utf-8"))
    check("RECORD: applied=true, 11 targets, before=[] / after=[MI_V2G] for each",
          rec["applied"] and len(rec["targets"]) == 11 and all(t["before"] == [] and t["after"] == [T.MI_V2G]
                                                               for t in rec["targets"]))
    check("RECORD: effective_before recorded as asset paths", all(t["effective_before"] == [T.DROP_MI] for t in rec["targets"]))
    names = sorted(os.path.basename(p) for p in rec["backup_files"])
    want = sorted([os.path.basename(T.EXPECTED_WORLD) + ".umap"] +
                  [os.path.basename(p) + ".uasset" for p in {p for p, _ in T.EXPECTED_TEMPLATES}])
    check("BACKUP: level + the six sequences, sizes copied", names == want and
          all(os.path.getsize(p) == 64 for p in rec["backup_files"]), names)
    saved = sorted(e.split(":", 1)[1] for e in ev if e.startswith("save:"))
    check("SAVE: exactly the MI + six sequences; no map save",
          saved == sorted([T.MI_V2G] + list({p for p, _ in T.EXPECTED_TEMPLATES}))
          and not any(e.startswith("save_map") for e in ev), saved)
    check("SAVE: census clean after", f.dirty() == {"content": [], "maps": []})
    check("APPLY: every template reads [MI_V2G]", all(b["overrides"] == [T.MI_V2G] for s in f.seqs.values()
                                                      for b in s.values()))
    check("APPLY: Drop MI untouched", f.mis[T.DROP_MI]["own_s"] == DROP_VALUES and f.mis[T.DROP_MI]["own_v"] == {})
    mi = f.read_mi(T.MI_V2G)
    check("MI: read-back passes (values, parent, override flags, inherited PatternWidthM/DropM)",
          T.mi_readback_problems(mi, DROP_VALUES) == [], T.mi_readback_problems(mi, DROP_VALUES))
    check("MI: PatternWidthM/DropM inherited, not overridden",
          not mi["overridden"]["PatternWidthM"] and not mi["overridden"]["DropM"])
    check("APPLY: marker VV2G_APPLY_OK", any(m.startswith("VV2G_APPLY_OK|") for m in f.logs))
    st2, _ = T.execute(f, {"mode": "VERIFY", "run_id": "TEST-VERIFY"})
    check("VERIFY: passes after APPLY", st2 == "VERIFY", f.logs[-1])
    st3, msg = T.execute(f, dict(args, run_id="TEST-APPLY2"))
    check("CONTROL apply: a second APPLY with a record present is refused",
          st3 == "STOPPED" and "RECORD_EXISTS" in msg, msg)
    return f, pre


def test_revert(f, pre):
    if f is None:
        check("REVERT: skipped (apply failed)", False)
        return
    # drift control first: someone changes one target
    key_pkg = T.EXPECTED_TEMPLATES[2][0]
    guid, b = next(iter(f.seqs[key_pkg].items()))
    b["overrides"] = ["/Game/Somebody/MI_Other"]
    f.mis["/Game/Somebody/MI_Other"] = {"parent": T.MI_PARENT, "own_s": {}, "own_v": {}}
    n_events = len(f.events)
    st, msg = T.execute(f, {"mode": "REVERT", "confirm": "REVERT V2G", "run_id": "TEST-REV-DRIFT"})
    check("CONTROL revert: DRIFT is refused and nothing is written", st == "STOPPED" and "DRIFT" in msg
          and len(f.events) == n_events, msg)
    b["overrides"] = [T.MI_V2G]
    st, msg = T.execute(f, {"mode": "REVERT", "confirm": "nope", "run_id": "TEST-REV-CONF"})
    check("CONTROL revert: wrong confirm is refused", st == "STOPPED" and "CONFIRM" in msg, msg)
    st, out = T.execute(f, {"mode": "REVERT", "confirm": "REVERT V2G", "run_id": "TEST-REV"})
    check("REVERT: status REVERTED", st == "REVERTED", (st, out))
    check("REVERT: every override list restored EXACTLY to the pre-apply state", f.state() == pre)
    check("REVERT: MI left in place (never deleted)", T.MI_V2G in f.mis)
    check("REVERT: record renamed .reverted-<run>", not os.path.exists(record_path(f)) and
          os.path.exists(record_path(f) + ".reverted-TEST-REV"))
    check("REVERT: census clean", f.dirty() == {"content": [], "maps": []})
    st, msg = T.execute(f, {"mode": "REVERT", "confirm": "REVERT V2G", "run_id": "TEST-REV2"})
    check("CONTROL revert: no record -> refused", st == "STOPPED" and "NO_RECORD" in msg, msg)
    # re-apply after revert: MI exists and matches -> reused, not re-created
    n_create = f.events.count("create_mi")
    st, out = T.execute(f, apply_args(f, run_id="TEST-REAPPLY"))
    check("RE-APPLY: MI reused (not re-created), targets swapped", st == "APPLIED" and f.events.count("create_mi") == n_create
          and T.MI_V2G not in [e.split(":", 1)[1] for e in f.events[-8:] if e.startswith("save:")], (st, out))


def test_revert_exact_mixed_befores():
    f = Fake()
    pkgs = list(f.seqs)
    g0 = next(iter(f.seqs[pkgs[0]].values()))
    g0["overrides"] = [None]
    g1 = next(iter(f.seqs[pkgs[1]].values()))
    g1["overrides"] = [T.DROP_MI]
    pre = f.state()
    st, _ = T.execute(f, apply_args(f, run_id="TEST-MIX"))
    check("MIXED: APPLY over [None] and [Drop MI] befores", st == "APPLIED" and g0["overrides"] == [T.MI_V2G]
          and g1["overrides"] == [T.MI_V2G])
    # one target reverted by hand to its before: REVERT skips it
    g1["overrides"] = [T.DROP_MI]
    st, out = T.execute(f, {"mode": "REVERT", "confirm": "REVERT V2G", "run_id": "TEST-MIXREV"})
    check("MIXED: REVERT restores [None] and [Drop MI] exactly, skips the hand-reverted one",
          st == "REVERTED" and f.state() == pre and len(out["skipped"]) == 1 and len(out["restored"]) == 10,
          (st, out if isinstance(out, str) else (out["skipped"], len(out["restored"]))))


def test_apply_faults():
    def run_fault(setup, extra=None):
        f = Fake()
        args = apply_args(f, **(extra or {}))
        setup(f)
        st, msg = T.execute(f, args)
        return f, st, msg

    key0 = T.target_key({"kind": "template", "package": T.EXPECTED_TEMPLATES[0][0], "guid": "%032X" % 1,
                         "component": COMP})
    f, st, msg = run_fault(lambda g: g.faults.update(silent_override_fail=key0))
    check("CONTROL apply: a silently failing override setter is caught, NOTHING saved",
          st == "FAILED" and "READBACK_BEFORE_SAVE" in msg and not any(e.startswith("save") for e in f.events), msg)
    check("CONTROL apply: the failed run leaves a record (applied=false) for REVERT",
          os.path.isfile(record_path(f)) and not json.load(open(record_path(f), encoding="utf-8"))["applied"])
    f, st, msg = run_fault(lambda g: g.faults.update(override_wrong_count=key0))
    check("CONTROL apply: a wrong slot count read back is caught", st == "FAILED" and "OVERRIDES" in msg, msg)
    f, st, msg = run_fault(lambda g: g.faults.update(setter_lies=True))
    check("APPLY: a setter that returns False after success still PASSES (gate = read-back)", st == "APPLIED", msg)
    f, st, msg = run_fault(lambda g: g.faults.update(mi_scalar_silent_fail="CrushScale"))
    check("CONTROL apply: an MI scalar setter that silently fails is caught before any override, NOTHING saved",
          st == "FAILED" and "MI_READBACK" in msg and "set_overrides" not in f.events
          and not any(e.startswith("save") for e in f.events), msg)
    f, st, msg = run_fault(lambda g: g.faults.update(foreign_dirty=True))
    check("CONTROL apply: a foreign dirty package stops the save", st == "FAILED" and "UNEXPECTED_DIRTY" in msg
          and not any(e.startswith("save") for e in f.events), msg)
    f, st, msg = run_fault(lambda g: g.faults.update(save_fail=T.EXPECTED_TEMPLATES[0][0]))
    check("CONTROL apply: a failed save reports PARTIAL_SAVE", st == "PARTIAL_SAVE", msg)
    f, st, msg = run_fault(lambda g: None, {"dry_digest": "0000000000000000"})
    check("CONTROL apply: digest drift since DRY is refused, nothing written",
          st == "STOPPED" and "PLAN_CHANGED_SINCE_DRY" in msg and not f.events and not os.path.exists(record_path(f)), msg)
    f, st, msg = run_fault(lambda g: None, {"confirm": "APPLY"})
    check("CONTROL apply: wrong confirm is refused", st == "STOPPED" and "CONFIRM" in msg, msg)
    f, st, msg = run_fault(lambda g: None, {"decided_by": " "})
    check("CONTROL apply: empty decided_by is refused", st == "STOPPED" and "NOT_DECIDED" in msg, msg)
    f, st, msg = run_fault(lambda g: g.dirty_c.add("/Game/Pending/Thing"))
    check("CONTROL apply: dirty census at start is refused", st == "STOPPED" and "DIRTY_AT_START" in msg, msg)
    f, st, msg = run_fault(lambda g: next(iter(g.seqs[T.OPENING_SEQ].values())).update(
        overrides=["/Game/Curtain/MI_CurtainImage_P01"]))
    check("CONTROL apply: a FOREIGN override appearing after DRY is refused, nothing written",
          st == "STOPPED" and "FOREIGN_OVERRIDE" in msg and not f.events, msg)
    # revert after a failed apply (Don't-Save restart modelled as: live state == before)
    f, st, msg = run_fault(lambda g: g.faults.update(silent_override_fail=key0))
    for s in f.seqs.values():
        for b in s.values():
            b["overrides"] = []
    f.dirty_c.clear()
    f.dirty_m.clear()
    n = len(f.events)
    st, out = T.execute(f, {"mode": "REVERT", "confirm": "REVERT V2G", "run_id": "TEST-UNAPPLIED"})
    check("REVERT after failed APPLY: nothing written, record renamed .unapplied",
          st == "REVERTED" and len(f.events) == n and os.path.exists(record_path(f) + ".unapplied-TEST-UNAPPLIED"), (st, out))


def test_level_target():
    f = Fake(level_actor=True)
    pre = f.state()
    st, rep = dry(f)
    check("LEVEL: DRY lists the level actor and touches the map",
          st == "DRY" and rep["refusals"] == [] and rep["touched"]["maps"] == [T.EXPECTED_WORLD]
          and any(t["kind"] == "level" and t["overrides"] == [None] for t in rep["targets"]), rep.get("refusals"))
    st, out = T.execute(f, apply_args(f, run_id="TEST-LEVEL"))
    check("LEVEL: APPLY saves the map once and the actor reads [MI_V2G]",
          st == "APPLIED" and f.events.count("save_map:" + T.EXPECTED_WORLD) == 1
          and all(a["overrides"] == [T.MI_V2G] for a in f.level.values()), (st, out))
    st, out = T.execute(f, {"mode": "REVERT", "confirm": "REVERT V2G", "run_id": "TEST-LEVELREV"})
    check("LEVEL: REVERT restores the actor's [None] exactly", st == "REVERTED" and f.state() == pre, (st, out))


def test_verify_before():
    f = Fake()
    st, msg = T.execute(f, {"mode": "VERIFY", "run_id": "TEST-V0"})
    check("CONTROL verify: fails before APPLY", st == "STOPPED" and "VERIFY_FAILED" in msg, msg)


def test_pure_revert_plan():
    rec = {"targets": [{"key": "a", "before": [], "after": [T.MI_V2G]}, {"key": "b", "before": [None], "after": [T.MI_V2G]}]}
    acts, refs = T.revert_plan(rec, {"a": {"overrides": [T.MI_V2G]}, "b": {"overrides": [None]}})
    check("PURE revert_plan: RESTORE + SKIP", [a for a, _ in acts] == ["RESTORE", "SKIP"] and not refs)
    acts, refs = T.revert_plan(rec, {"a": {"overrides": [T.MI_V2G]}, "b": None})
    check("CONTROL revert_plan: a vanished target is refused", refs and refs[0].startswith("TARGET_GONE"))
    check("CONTROL classify: [] vs [None] vs [Drop] vs foreign",
          [T.classify({"slots": 1, "overrides": o}) for o in ([], [None], [T.DROP_MI], ["/Game/X"], [T.MI_V2G])]
          == ["SWAP", "SWAP", "SWAP", "FOREIGN", "ALREADY"])


def main():
    test_static()
    test_dry()
    f, pre = test_apply_happy()
    test_revert(f, pre)
    test_revert_exact_mixed_befores()
    test_apply_faults()
    test_level_target()
    test_verify_before()
    test_pure_revert_plan()
    for t in TMP:
        shutil.rmtree(t, ignore_errors=True)
    passed = sum(1 for _, ok in RESULTS if ok)
    controls = [r for r in RESULTS if r[0].startswith("CONTROL")]
    print("\nHARNESS: %d passed, %d failed of %d (failing controls caught: %d/%d)"
          % (passed, len(RESULTS) - passed, len(RESULTS), sum(1 for _, ok in controls if ok), len(controls)))
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
