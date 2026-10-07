"""Offline harness for fx_effect_bps.py (no Unreal): args, plan, probe gate, C++ path contract, source guards.
Each property has a + case and a - control. Run: python Saved/CodexConductor/Effects_20261007/test_fx_effect_bps_offline.py"""
import ast
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import fx_effect_bps as B  # noqa: E402

RESULTS = []


def check(name, cond):
    RESULTS.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name)


def raises(fn, token=None):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        return token is None or token in str(exc)
    return False


check("args: DRY default", B.check_args({})["mode"] == "DRY")
check("args -: APPLY without confirm", raises(lambda: B.check_args({"mode": "APPLY"}), "CONFIRM_MISSING"))
check("args: APPLY with confirm", B.check_args({"mode": "APPLY", "confirm": "APPLY FXEFFECTBPS"})["mode"] == "APPLY")
check("args -: unknown type", raises(lambda: B.check_args({"types": ["Rain"]}), "TYPES"))
check("args: P_Smoke allowed as SmokePot alternative", B.check_args(
    {"templates": {"SmokePot": "/Game/KK_S2_Shrine/StarterContent/Particles/P_Smoke"}})["mode"] == "DRY")
check("args -: arbitrary template refused", raises(lambda: B.check_args(
    {"templates": {"SmokePot": "/Game/KK_S2_Shrine/StarterContent/Particles/P_Fire"}}), "TEMPLATE_NOT_ALLOWED"))
rows = B.plan(B.check_args({}))
check("plan: two rows, Humo_Par + P_Ambient_Dust", [r["template"].rsplit("/", 1)[-1] for r in rows]
      == ["Humo_Par", "P_Ambient_Dust"])

# C++ contract: the BP paths are exactly what InfinityStageEffectSource.cpp resolves
cpp = (ROOT / "Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageEffectSource.cpp").read_text(encoding="utf-8")
cpp_paths = set(p.split(".", 1)[0] for p in re.findall(r'TEXT\("(/Game/Scenes/Effects/BP_Effect_\w+\.\w+)"\)', cpp))
check("contract: every BP path is a C++ default class path", {r["bp"] for r in rows} <= cpp_paths)
check("contract -control: a misspelt path is not", "/Game/Scenes/Effects/BP_Effect_Smoke" not in cpp_paths)
check("contract: C++ gates every UFXSystemComponent (Cascade included)", "TInlineComponentArray<UFXSystemComponent*>" in cpp)

GOOD = {"census_equal": True, "apis": {"Emitter": True},
        "cascade": [{"path": r["template"], "exists": True, "class": "ParticleSystem"} for r in rows]}
check("gate: a clean probe passes", B.probe_gate(GOOD, rows) == [])
check("gate -: no probe", B.probe_gate(None, rows) and "PROBE_MISSING" in B.probe_gate(None, rows)[0])
bad = json.loads(json.dumps(GOOD))
bad["cascade"][0]["class"] = "Object"
check("gate -: template not a ParticleSystem", any("TEMPLATE_NOT_PROVEN" in x for x in B.probe_gate(bad, rows)))
bad = dict(GOOD, census_equal=False)
check("gate -: dirty probe", "PROBE_NOT_CLEAN" in B.probe_gate(bad, rows))

src = (HERE / "fx_effect_bps.py").read_text(encoding="utf-8")
tree = ast.parse(src)
check("source: auto_activate False set and read back", src.count('"auto_activate", False') == 1
      and 'got["auto_activate"] is False' in src)
check("source: APPLY refuses existing targets and needs a clean census",
      "TARGET_EXISTS" in src and "DIRTY_BEFORE" in src)
check("source: no level/map save, no Save All", not re.search(r"save_map|save_dirty_packages|save_packages\(", src))
check("source -control: the regex catches save_map", re.search(r"save_map", "x.save_map(w)") is not None)
check("source: REVERT deletes only recorded, unreferenced assets",
      'for path in rec["created"]' in src and "REFERENCED" in src)
glob_loads = [n for n in tree.body if isinstance(n, ast.Assign) and "load_asset" in ast.dump(n)]
check("source: no unreal objects in module globals", not glob_loads)
for name in ("fx_effect_bps.py", "fx_effect_bps_run.py"):
    try:
        ast.parse((HERE / name).read_text(encoding="utf-8"))
        ok = True
    except SyntaxError:
        ok = False
    check("ast.parse %s" % name, ok)
req = json.loads((HERE / "fx_effect_bps_request.json").read_text(encoding="utf-8"))
check("request: runner path", req["arguments"]["arguments"]["relativeSavedPath"]
      == "CodexConductor/Effects_20261007/fx_effect_bps_run.py")
check("args file: DRY", B.check_args(json.loads((HERE / "fx_effect_bps_args.json").read_text()))["mode"] == "DRY")

failed = [n for n, ok in RESULTS if not ok]
print("\nFXEFFECTBPS_HARNESS|pass=%d|fail=%d" % (len(RESULTS) - len(failed), len(failed)))
sys.exit(1 if failed else 0)
