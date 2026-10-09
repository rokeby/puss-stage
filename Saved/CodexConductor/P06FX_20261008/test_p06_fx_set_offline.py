"""Offline positive/negative harness for the first P06 FX set."""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p06_fx_set as S  # noqa: E402

R = []


def check(name, condition): R.append(bool(condition)); print(("PASS " if condition else "FAIL ") + name)


def raises(fn, token):
    try: fn()
    except Exception as exc: return token in str(exc)
    return False


a = S.C.D.validate_set({})
check("args +: three defaults and held candle/smoke", len(a["placements"]) == 3 and not a["include_candle"] and not a["include_smoke"])
check("args +: exact current cue identities", [p["cue_label"] for p in a["placements"]] ==
      ["P06 Wing 052", "P06 Wing 044", "P06 Wing 049"])
check("args -: candle cannot silently return", raises(lambda: S.C.D.validate_set({"include_candle": True}), "CANDLE_HELD"))
check("args -: smoke remains held", raises(lambda: S.C.D.validate_set({"include_smoke": True}), "SMOKE_HELD"))
bad = [dict(a["placements"][0], cue_guid="0" * 32)] + a["placements"][1:]
check("args -: relayout GUID drift", raises(lambda: S.C.D.validate_set({"placements": bad}), "GUID_DRIFT"))
bad = [dict(a["placements"][0], output=1.5)] + a["placements"][1:]
check("args -: output bounded", raises(lambda: S.C.D.validate_set({"placements": bad}), "OUTPUT"))
check("args -: APPLY needs confirm", raises(lambda: S.C.D.validate_set({"mode": "APPLY"}), "CONFIRM"))
check("args +: APPLY confirm", S.C.D.validate_set({"mode": "APPLY", "confirm": "APPLY P06FXSET"})["mode"] == "APPLY")

assets = {S.C.D.EFFECT_SPECS[n]["bp"]: True for n in ("Motes", "FireBasket", "WingBurn")}
bpr = {"status": "applied", "args": {"fire_particle_light_enabled": False}}
mir = {"status": "applied"}
check("gate +: BPs, no-light fire, and live child MIs", not S.dependency_gate(a, assets, bpr, mir, True))
bad = dict(assets); bad[S.C.D.EFFECT_SPECS["FireBasket"]["bp"]] = False
check("gate -: Fire BP missing", any("BP_MISSING|FireBasket" in x for x in S.dependency_gate(a, bad, bpr, mir, True)))
check("gate -: particle light opt-in blocks placement", "FIRE_PARTICLE_LIGHT_NOT_OFF" in S.dependency_gate(
    a, assets, {"status": "applied", "args": {"fire_particle_light_enabled": True}}, mir, True))
check("gate -: live MI readback required", "WING_MI_LIVE_READBACK" in S.dependency_gate(a, assets, bpr, mir, False))
check("gate -: live BP and no-light readback required",
      "BP_LIVE_READBACK" in S.dependency_gate(a, assets, bpr, mir, True, False))
check("label +: ownership prefix deterministic", S.label_for(a["placements"][0]) == "P06 FX 20261008 - motes_69_83")

src = (HERE / "p06_fx_set.py").read_text(encoding="utf-8")
check("safety +: record before first add",
      src.index("C.write_json(RECORD, record, exclusive=True)")
      < src.index("_add(show, placement, claim_guid)")
      and src.index("claim_guid(text)") < src.index("_configure(show, placement, text)"))
check("safety +: only Show+level are saved", "C.save_show_level()" in src and "save_dirty_packages" not in src)
check("safety +: exact dirty package census", '{"content": [C.D.SHOW], "maps": [C.D.EXPECTED_WORLD]}' in src)
check("safety +: materialize and saved/actor read-back", all(x in src for x in ("materialize_passage()", "saved == expected", "set(actors) == set(record[\"guids\"])")))
check("safety +: REVERT removes only recorded GUIDs", "_remove(show, guids)" in src and "FOREIGN_GUID" in src)
check("safety +: no foreign bee/car/sequence mutation", all(x not in src for x in ("LS_P06_BeeGlints", "P06 Car Light", "MovieScene")))
check("safety +: foreign attachments compared before/after", "FOREIGN_ATTACHMENT_DRIFT" in src
      and "REVERT_FOREIGN_ATTACHMENT_DRIFT" in src)
runner = (HERE / "p06_fx_set_run.py").read_text(encoding="utf-8")
check("runner +: implementation executes exactly once", runner.count("module.main()") == 1
      and '__name__ == "__main__"' in src)

# 9 Oct conductor: wing burn held -> MI record only required when a WingBurn placement exists (+/- controls).
try:
    import copy as _copy
    _args = _copy.deepcopy(S.C.D.validate_set({}))
    _nob = dict(_args, placements=[p for p in _args["placements"] if p["type"] != "WingBurn"])
    _ex = {S.C.D.EFFECT_SPECS[n]["bp"]: True for n in ("Motes", "FireBasket", "WingBurn")}
    _bpr = {"status": "applied", "args": {"fire_particle_light_enabled": False}}
    check("gate +: no WingBurn placement -> MI record not required", "WING_MI_RECORD_NOT_APPLIED" not in S.dependency_gate(_nob, _ex, _bpr, None, False))
    check("gate -: WingBurn placement still requires the MI record", "WING_MI_RECORD_NOT_APPLIED" in S.dependency_gate(_args, _ex, _bpr, None, False))
except Exception as _e:  # noqa: BLE001
    check("gate controls ran: %r" % (_e,), False)

failed = len(R) - sum(R)
print("P06FXSET_HARNESS|pass=%d|fail=%d" % (sum(R), failed))
sys.exit(1 if failed else 0)
