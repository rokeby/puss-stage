"""Offline harness for fx_content_probe.py + the FX content inventory (no Unreal). Re-derives every binary-proven
inventory claim of EFFECTS_PLAN_2026-10-07.md from the package bytes, with - controls, and proves the probe is
read-only by AST (no save / spawn / set / destroy / PIE-end call). Run:
python Saved/CodexConductor/Effects_20261007/test_fx_content_probe_offline.py"""
import ast
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CONTENT = ROOT / "Content"
RESULTS = []


def check(name, cond):
    RESULTS.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name)


def names(rel):
    p = CONTENT / rel
    if not p.exists():
        return None
    return set(m.decode() for m in re.findall(rb"[\x20-\x7e]{6,}", p.read_bytes()))


EXPECT = {
    "Japanese_Alley/VFX/Rain2.uasset": ("ParticleSystem", ["ParticleModuleTypeDataGpu", "ParticleModuleAccelerationConstant",
                                                            "ParticleModuleSizeScaleBySpeed"]),
    "Japanese_Alley/VFX/Humo_Par.uasset": ("ParticleSystem", ["ParticleModuleSubUV", "ParticleModuleTypeDataGpu"]),
    "KK_S2_Shrine/StarterContent/Particles/P_Smoke.uasset": ("ParticleSystem", ["ParticleModuleSubUV"]),
    "KK_S2_Shrine/StarterContent/Particles/P_Fire.uasset": ("ParticleSystem", ["ParticleModuleLight"]),
    "KK_S2_Shrine/StarterContent/Particles/P_Steam_Lit.uasset": ("ParticleSystem", ["ParticleModuleAccelerationDrag"]),
    "KK_S2_Shrine/StarterContent/Particles/P_Ambient_Dust.uasset": ("ParticleSystem", ["ParticleModuleTypeDataGpu"]),
    "FX/NS_BeeSwarm.uasset": ("NiagaraSystem", ["NiagaraEmitter"]),
    "Scenes/Effects/BP_Effect_Candle.uasset": ("InfinityStageEffectSource", ["NiagaraComponent"]),
}
for rel, (cls, mods) in EXPECT.items():
    s = names(rel)
    check("inventory: %s is %s with %s" % (rel, cls, mods), s is not None and cls in s and all(m in s for m in mods))
s = names("KK_S2_Shrine/StarterContent/Particles/P_Smoke.uasset")
check("inventory -control: P_Smoke is NOT a NiagaraSystem (why the rain bench scan missed it)", "NiagaraSystem" not in s)
s = names("FX/NS_BeeSwarm.uasset")
check("inventory: Klara's NS_BeeSwarm exposes no User. parameter (spawn rate is a constant)",
      not any(x.startswith("User.") for x in s) and "Constants.Fountain.SpawnRate.SpawnRate" in s)
check("inventory -control: the C++ swarm reader name User.BeePositions is absent from Klara's system",
      not any("BeePositions" in x for x in s))
eff = CONTENT / "Scenes" / "Effects"
present = sorted(p.name for p in eff.glob("*.uasset"))
check("inventory: Scenes/Effects holds only the candle set (%s)" % present,
      present == ["BP_Effect_Candle.uasset", "MI_FX_CandleWax.uasset", "M_FX_CandleFlame.uasset", "M_FX_CandleWax.uasset"])
for t in ("HazePot", "SmokePot", "SteamKettle", "FireBasket", "WingBurn", "Motes"):
    check("inventory: BP_Effect_%s absent (C++ falls back to the greybox)" % t, not (eff / ("BP_Effect_%s.uasset" % t)).exists())
check("inventory: C++ swarm renderer Scenes/Effects/Swarm/NS_BeeSwarm absent", not (eff / "Swarm" / "NS_BeeSwarm.uasset").exists())
check("inventory -control: the existence test can say yes", (eff / "BP_Effect_Candle.uasset").exists())

# ---- probe is read-only (AST)
FORBIDDEN = {"save_asset", "save_map", "save_packages", "save_dirty_packages", "spawn_actor_from_class",
             "spawn_actor_from_object", "set_editor_property", "destroy_actor", "delete_asset", "end_play_map",
             "request_end_play_map", "load_map", "spawn_emitter_at_location", "spawn_system_at_location", "modify",
             "set_float_parameter", "set_variable_float", "editor_request_end_play"}


def called(src):
    out = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Call):
            f = node.func
            out.add(f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", ""))
    return out


src = (HERE / "fx_content_probe.py").read_text(encoding="utf-8")
bad = called(src) & FORBIDDEN
check("probe: calls nothing mutating (%s)" % sorted(bad), not bad)
check("probe -control: the scan catches an injected save", "save_asset" in called(
    src + "\nunreal.EditorAssetLibrary.save_asset('/Game/X')\n"))
check("probe: census compared before/after and marker only on equality",
      "census_equal" in src and src.rindex("CENSUS_CHANGED") < src.rindex("FXPROBE_OK|run"))
tree = ast.parse(src)
glob_calls = [n for n in tree.body if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call)
              and "load_asset" in ast.dump(n.value)]
check("probe: no unreal objects loaded into module globals", not glob_calls)
req = json.loads((HERE / "fx_content_probe_request.json").read_text(encoding="utf-8"))
check("request: ExecuteProjectPythonFile on the probe",
      req["arguments"]["arguments"]["relativeSavedPath"] == "CodexConductor/Effects_20261007/fx_content_probe.py")

failed = [n for n, ok in RESULTS if not ok]
print("\nFXPROBE_HARNESS|pass=%d|fail=%d" % (len(RESULTS) - len(failed), len(failed)))
sys.exit(1 if failed else 0)
