"""Offline positive/negative harness for the read-only FX probe."""
import ast
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p06_fx_probe as P  # noqa: E402

R = []


def check(name, condition):
    R.append(bool(condition)); print(("PASS " if condition else "FAIL ") + name)


class PathPart:
    def __init__(self, name): self.asset_name = name


class Asset:
    def __init__(self, cls, path):
        self.asset_class_path = PathPart(cls); self.package_name = path; self.asset_name = path.rsplit("/", 1)[-1]


rows = P.particle_rows([Asset("Texture2D", "/Game/T"), Asset("ParticleSystem", "/Game/P"),
                        Asset("NiagaraSystem", "/Game/N"), Asset("NiagaraEmitter", "/Game/E")])
check("inventory +: all three particle asset classes", [r["class"] for r in rows] == ["NiagaraEmitter", "NiagaraSystem", "ParticleSystem"])
check("inventory -: unrelated Texture2D omitted", all(r["path"] != "/Game/T" for r in rows))

good = {"run_id": "P04RAINPIE-20261007-063520", "errors": [], "problems": [],
        "analysis": {"verdict": {"rain": "RENDERS", "valid_stills": 1},
                     "rows": [{"valid": True, "rain_attributable": True,
                               "seen": {"ctrl": True, "rain": True, "rain_noparticles": False}}]}}
ev = P.render_evidence("dummy", exists=lambda _: True, loader=lambda _: good,
                       hasher=lambda _: "fixture-sha256")
check("render +: controlled particles-off evidence confirms", ev["confirmed"])
bad = {**good, "analysis": {"verdict": {"rain": "RENDERS", "valid_stills": 1},
                             "rows": [{"valid": True, "rain_attributable": True,
                                       "seen": {"ctrl": True, "rain": True, "rain_noparticles": True}}]}}
check("render -: particles-off still visible refuses",
      not P.render_evidence("dummy", lambda _: True, lambda _: bad,
                            lambda _: "fixture-sha256")["confirmed"])
check("render -: missing manifest refuses", not P.render_evidence("dummy", lambda _: False)["confirmed"])

src = (HERE / "p06_fx_probe.py").read_text(encoding="utf-8")
calls = {n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
         for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call)}
forbidden = {"save_asset", "save_loaded_asset", "save_current_level", "set_editor_property", "delete_asset",
             "spawn_actor_from_class", "spawn_emitter_at_location", "spawn_system_at_location", "end_play_map"}
check("source +: probe has no mutating calls", not (calls & forbidden))
check("source -control: AST detector catches injected save", "save_asset" in {n.func.attr for n in ast.walk(ast.parse(
    src + "\nunreal.EditorAssetLibrary.save_asset('/Game/X')\n")) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)})
check("source +: scans /Game recursively and writes census comparison", 'get_assets_by_path("/Game", recursive=True' in src and '"census_equal"' in src)
check("source +: marker only after render and census requirements", src.index('C.require(report["census_equal"]') < src.index("P06FXPROBE_OK"))

failed = len(R) - sum(R)
print("P06FXPROBE_HARNESS|pass=%d|fail=%d" % (sum(R), failed))
sys.exit(1 if failed else 0)
