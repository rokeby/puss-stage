"""Validation harness for the blocker-gap fix (30 Sep): dry-run hangar_build.py AND the Codex draft
(hangar_build_draft.py, copied into Saved/ for the run) for all six Scenes with each record's own
HANGAR_PARAMS (Scene 4: defaults), and diff the blocker lists. Dry runs only: the builder returns
before any mutation (it writes hangar_sN_plan.json, read back straight after each run).
Predicted before running (conductor, 30 Sep): S1, S5, S6 clean (planes trimmed); S2, S3 clean
(their landscapes are allowed by label); S4 clean; the sky sphere must NOT appear; any NEW blocker
must be a large actor the old test skipped, and is named. Writes blocker_compare.json. Lean: main()."""
import json
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
SCRIPTS = ("hangar_build.py", "hangar_build_draft.py")


def main():
    out = {}
    for script in SCRIPTS:
        path = os.path.join(HERE, script)
        if not os.path.exists(path):
            out[script] = "missing"
            continue
        out[script] = {}
        for n in range(1, 7):
            rec_path = os.path.join(HERE, f"hangar_s{n}_record.json")
            params = json.load(open(rec_path, encoding="utf-8"))["hangar"] if os.path.exists(rec_path) else {"scene": 4}
            try:
                runpy.run_path(path, init_globals={"HANGAR_PARAMS": params})
                plan = json.load(open(os.path.join(HERE, f"hangar_s{n}_plan.json"), encoding="utf-8"))
                out[script][n] = {"blockers": plan["blockers"], "problems": plan["problems"]}
            except Exception as exc:  # noqa: BLE001
                out[script][n] = {"error": str(exc)[:300]}
    old, new = out.get(SCRIPTS[0]), out.get(SCRIPTS[1])
    diff = {}
    if isinstance(old, dict) and isinstance(new, dict):
        for n in range(1, 7):
            ob = set(old[n].get("blockers", [])) if "blockers" in old[n] else None
            nb = set(new[n].get("blockers", [])) if "blockers" in new[n] else None
            diff[n] = {"only_old": sorted(ob - nb) if ob is not None and nb is not None else None,
                       "only_new": sorted(nb - ob) if ob is not None and nb is not None else None,
                       "sky_in_new": any("Sun Moon" in b or "SkySphere" in b for b in (nb or []))}
    out["diff"] = diff
    json.dump(out, open(os.path.join(HERE, "blocker_compare.json"), "w"), indent=1, default=str)
    dirty = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()), len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
    unreal.log(f"BLOCKER_COMPARE_OK|scripts={[s for s in SCRIPTS if isinstance(out.get(s), dict)]}|dirty_after={dirty[0]}+{dirty[1]}")


main()
