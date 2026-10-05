"""READ-ONLY diagnosis after PRESAVE_SNAPSHOT_MISMATCH (5 Oct): dump live vs expected binding rows for I1."""
import json
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
src = open(os.path.join(HERE, "curtain_sleight.py"), encoding="utf-8").read()
cut = src.rindex("if unreal is not None:")
ns = {"__name__": "curtain_sleight_lib", "__file__": os.path.join(HERE, "curtain_sleight.py")}
exec(compile(src[:cut], "curtain_sleight.py", "exec"), ns)  # definitions only, main() not run
rec = json.load(open(os.path.join(HERE, "curtain_sleight_record_I1.json"), encoding="utf-8"))
seq = unreal.load_asset(rec["sequence"])
live = ns["_snapshot"](seq, 1)
guids = rec.get("binding_guids") or {}
expected = ns["apply_model"](rec["snapshot_before"], rec["plan"], guids)
lb = {b["guid"]: b for b in live["bindings"]}
eb = {b["guid"]: b for b in expected["bindings"]}
out = {"only_live": [lb[g] for g in lb if g not in eb], "only_expected": [eb[g] for g in eb if g not in lb],
       "differ": [{"guid": g, "live": lb[g], "expected": eb[g]} for g in lb if g in eb and lb[g] != eb[g]]}
path = os.path.join(HERE, "curtain_sleight_diag_bindings.json")
json.dump(out, open(path, "w", encoding="utf-8"), indent=1, default=str)
unreal.log("CURTAIN_SLEIGHT_DIAG|only_live=%d|only_expected=%d|differ=%d|out=%s"
           % (len(out["only_live"]), len(out["only_expected"]), len(out["differ"]), path))
