"""Offline positive/negative harness for the pure Variant B contract and editor-tool safety surface."""
import ast, importlib.util, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("vbcore", os.path.join(HERE, "s2k_variantB_mis_core.py"))
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)
R = []
def check(name, ok): R.append({"check": name, "ok": bool(ok)})

rows = C.rows(); check("POS exactly six unique owned targets", len(rows) == 6 and len({r["target"] for r in rows}) == 6)
check("POS Front and Flap for all three owners", {(r["owner"], r["slot"]) for r in rows} == {(o,s) for o in C.OWNERS for s in ("Front","Flap")})
check("POS destination is KlaraS2 Materials only", all(r["target"].startswith(C.DEST + "/") for r in rows))
check("NEG Klara packages are never targets", all(not r["target"].startswith(("/Game/WetGround/", "/Game/KK_")) for r in rows))
check("POS DRY needs no confirm", C.validate_args({"mode":"DRY"}) == [])
check("NEG APPLY bad confirm refused", "CONFIRM" in C.validate_args({"mode":"APPLY","confirm":"x","decided_by":"Gary"}))
check("NEG write without decision refused", "DECIDED_BY" in C.validate_args({"mode":"REVERT","confirm":"REVERT S2KVARIANTB"}))
state = {r["target"]:{"parent":C.EXPECTED_PARENT,"PaperMap":r["skin"],"UsePaperMap":True,"UseAlphaCutout":False} for r in rows}
check("POS saved state contract", C.state_problems(state) == [])
bad = json.loads(json.dumps(state)); bad[rows[0]["target"]]["PaperMap"] = "/Game/Wrong"
check("NEG wrong PaperMap caught", any(x.startswith("PAPERMAP") for x in C.state_problems(bad)))
bad = dict(state); bad.pop(rows[0]["target"])
check("NEG missing package caught", "TARGET_SET" in C.state_problems(bad))
src = open(os.path.join(HERE,"s2k_variantB_mis.py"),encoding="utf-8").read(); tree=ast.parse(src)
check("POS no Save All or map save", not any(x in src for x in ("save_dirty_packages","save_map","save_all")))
check("POS source and parent constants are never write targets", "set_material_instance_parent(mi, parent)" in src and "delete_asset(C.SOURCE_MI)" not in src)
out={"passed":sum(x["ok"] for x in R),"failed":sum(not x["ok"] for x in R),"results":R,
     "tier":"measured offline pure-contract and static checks; Unreal behavior unproven"}
json.dump(out,open(os.path.join(HERE,"test_s2k_variantB_mis_offline_report.json"),"w"),indent=2)
print("TOTAL %d passed, %d failed"%(out["passed"],out["failed"])); sys.exit(0 if not out["failed"] else 1)
