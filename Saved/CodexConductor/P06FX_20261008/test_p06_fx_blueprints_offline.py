"""Offline positive/negative harness for default Effect Blueprint authoring."""
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import p06_fx_blueprints as B  # noqa: E402

R = []


def check(name, condition): R.append(bool(condition)); print(("PASS " if condition else "FAIL ") + name)


def raises(fn, token):
    try: fn()
    except Exception as exc: return token in str(exc)
    return False


a = B.C.D.validate_blueprints({})
check("args +: defaults DRY and fire light off", a["mode"] == "DRY" and a["fire_particle_light_enabled"] is False)
check("args -: APPLY needs exact confirm", raises(lambda: B.C.D.validate_blueprints({"mode": "APPLY"}), "CONFIRM"))
check("args +: APPLY confirm", B.C.D.validate_blueprints({"mode": "APPLY", "confirm": "APPLY P06FXBPS"})["mode"] == "APPLY")
check("args -: REVERT requires delete acknowledgement", raises(lambda: B.C.D.validate_blueprints(
    {"mode": "REVERT", "confirm": "REVERT P06FXBPS DELETE CREATED ASSETS"}), "DELETE_ACK"))
check("args +: explicit destructive REVERT", B.C.D.validate_blueprints(
    {"mode": "REVERT", "confirm": "REVERT P06FXBPS DELETE CREATED ASSETS", "allow_permanent_asset_delete": True})["mode"] == "REVERT")
check("args -: unknown type", raises(lambda: B.C.D.validate_blueprints({"types": ["Rain"]}), "TYPES"))

rows = B.rows_for(a)
check("plan +: all six default classes", [r["name"] for r in rows] == list(B.C.D.EFFECT_SPECS))
check("plan +: Fire and WingBurn use private no-light template", all(r["template"] == B.C.D.FIRE_NO_LIGHT
      for r in rows if r["name"] in ("FireBasket", "WingBurn")))
lit = B.rows_for(B.C.D.validate_blueprints({"fire_particle_light_enabled": True}))
check("plan -control: opt-in light uses source P_Fire", all(r["template"] == B.C.D.FIRE_SOURCE
      for r in lit if r["name"] in ("FireBasket", "WingBurn")))

assets = [{"path": (B.C.D.FIRE_SOURCE if r["template"] == B.C.D.FIRE_NO_LIGHT else r["template"]), "class": "ParticleSystem"}
          for r in rows]
probe = {"census_equal": True, "cascade_render": {"confirmed": True}, "particle_assets": assets,
         "fire_particle_light": {"readable": True, "modules": [{"spawn_fraction": 1.0}]}}
check("gate +: clean inventory/render/light-module probe", not B.gate(probe, rows, False))
bad = dict(probe, cascade_render={"confirmed": False})
check("gate -: unconfirmed renderer", "CASCADE_RENDER_UNPROVEN" in B.gate(bad, rows, False))
bad = dict(probe, fire_particle_light={"readable": False, "modules": []})
check("gate -: cannot safely disable fire light", "FIRE_LIGHT_MODULE_UNREADABLE" in B.gate(bad, rows, False))

cpp = (ROOT / "Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageEffectSource.cpp").read_text(encoding="utf-8")
paths = set(p.split(".", 1)[0] for p in re.findall(r'TEXT\("(/Game/Scenes/Effects/BP_Effect_\w+\.\w+)"\)', cpp))
check("contract +: all six BP paths match C++ resolver", {r["bp"] for r in rows} <= paths)
check("contract -control: misspelt path absent", "/Game/Scenes/Effects/BP_Effect_Fire" not in paths)
src = (HERE / "p06_fx_blueprints.py").read_text(encoding="utf-8")
check("safety +: record written before private fire mutation",
      src.index("C.write_json(RECORD, record, exclusive=True)")
      < src.index('record["fire_light_readback"] = _create_no_light_fire()'))
check("safety +: source fire is duplicated, never edited", "duplicate_asset(C.D.FIRE_SOURCE, C.D.FIRE_NO_LIGHT)" in src)
check("safety +: SpawnFraction and HQ/shadow flags disabled/read back", all(x in src for x in (
    '"spawn_fraction", 0.0', '"high_quality_lights", False', '"shadow_casting_lights", False', "_fire_light_readback")))
check("safety +: no Save All/map save", "save_dirty_packages" not in src and "save_current_level" not in src)
check("safety +: REVERT deletes only recorded existing targets after backup",
      'claimed = list(record.get("created", []))' in src
      and 'created = [p for p in claimed if unreal.EditorAssetLibrary.does_asset_exist(p)]' in src
      and 'C.backup("PreP06FxBlueprintsRevert"' in src and "for path in reversed(created)" in src)
runner = (HERE / "p06_fx_blueprints_run.py").read_text(encoding="utf-8")
check("runner +: implementation executes exactly once", runner.count("module.main()") == 1
      and '__name__ == "__main__"' in src)

failed = len(R) - sum(R)
print("P06FXBPS_HARNESS|pass=%d|fail=%d" % (sum(R), failed))
sys.exit(1 if failed else 0)
