"""Offline positive/negative harness for isolated WingBurn child MIs."""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p06_wingburn_mi as W  # noqa: E402

R = []


def check(name, condition): R.append(bool(condition)); print(("PASS " if condition else "FAIL ") + name)


def raises(fn, token):
    try: fn()
    except Exception as exc: return token in str(exc)
    return False


a = W.C.D.validate_wing_mi({})
check("args +: current relayout target, DRY", a["cue_label"] == "P06 Wing 044" and a["mode"] == "DRY")
check("args -: stale old Wing 032 refused", raises(lambda: W.C.D.validate_wing_mi({"cue_label": "P06 Wing 032"}), "CUE_LABEL"))
check("args -: GUID drift refused", raises(lambda: W.C.D.validate_wing_mi({"cue_guid": "0" * 32}), "GUID_DRIFT"))
check("args -: preview cannot pre-char", raises(lambda: W.C.D.validate_wing_mi({"burn_preview": 0.1}), "PREVIEW"))
check("args -: REVERT requires delete acknowledgement", raises(lambda: W.C.D.validate_wing_mi(
    {"mode": "REVERT", "confirm": "REVERT P06WINGBURNMI DELETE CREATED ASSETS"}), "DELETE_ACK"))
check("args +: explicit destructive REVERT", W.C.D.validate_wing_mi(
    {"mode": "REVERT", "confirm": "REVERT P06WINGBURNMI DELETE CREATED ASSETS", "allow_permanent_asset_delete": True})["mode"] == "REVERT")

slots = [{"slot": "Front", "material": "/Game/F", "master": next(iter(W.ALLOWED_MASTERS)), "burn_contract": True, "index": 0},
         {"slot": "Flap", "material": "/Game/L", "master": next(iter(W.ALLOWED_MASTERS)), "burn_contract": True, "index": 1}]
plan = W.plan_slots(slots, ["Front", "Flap"], "/Game/Child", "One")
check("plan +: two children parented to resolved per-flat MIs", [r["child"] for r in plan] ==
      ["/Game/Child/MI_One_Front", "/Game/Child/MI_One_Flap"] and [r["material"] for r in plan] == ["/Game/F", "/Game/L"])
check("plan -: missing slot", raises(lambda: W.plan_slots(slots[:1], ["Front", "Flap"], "/Game/C", "X"), "SLOT_MISSING"))
bad = [dict(slots[0], burn_contract=False), slots[1]]
check("plan -: master binary lacks burn contract", raises(lambda: W.plan_slots(bad, ["Front", "Flap"], "/Game/C", "X"), "BURN_CONTRACT"))
bad = [dict(slots[0], master="/Game/Wrong"), slots[1]]
check("plan -: wrong master chain", raises(lambda: W.plan_slots(bad, ["Front", "Flap"], "/Game/C", "X"), "MATERIAL_CHAIN"))
slope, intercept, residual = W.linear_fit([-100, 0, 100], [1, .5, 0])
check("UV +: exact planar fit", abs(slope + .005) < 1e-12 and abs(intercept - .5) < 1e-12 and residual == 0)
check("UV -: degenerate fit", raises(lambda: W.linear_fit([0, 0, 0], [0, .5, 1]), "FIT_DEGENERATE"))

src = (HERE / "p06_wingburn_mi.py").read_text(encoding="utf-8")
check("safety +: no material graph node deletion", "delete_material_expression" not in src and "delete_all_material_expressions" not in src)
check("safety +: record before child creation",
      src.index("C.write_json(RECORD, record, exclusive=True)")
      < src.index('record["child_readback"][row["child"]] = _create_child(row, uv, args)'))
check("safety +: backups Show/level/parents", 'C.backup("PreP06WingBurnMI"' in src and "parents" in src)
check("safety +: read-back after targeted child save", "save_loaded_asset(child" in src and "return _child_readback(row, uv)" in src)
check("safety +: exact Show+map dirty scope", '{"content": [C.D.SHOW], "maps": [C.D.EXPECTED_WORLD]}' in src)
check("safety +: REVERT restores slots before deleting recorded children", src.index("_assign(show, args, rows, restore=record") < src.index("for path in reversed(created)"))
runner = (HERE / "p06_wingburn_mi_run.py").read_text(encoding="utf-8")
check("runner +: implementation executes exactly once", runner.count("module.main()") == 1
      and '__name__ == "__main__"' in src)

failed = len(R) - sum(R)
print("P06WINGBURNMI_HARNESS|pass=%d|fail=%d" % (sum(R), failed))
sys.exit(1 if failed else 0)
