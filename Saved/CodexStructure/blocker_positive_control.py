"""Read-only positive control for the blocker-gap draft (30 Sep): dry-run Scene 2 with its landscape REMOVED
from the allow list, under the current builder and the draft; both must report the landscape (the draft
via its trace path). Dry runs only; plan file deleted before each run and required after."""
import json
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")


def main():
    params = json.load(open(os.path.join(HERE, "hangar_s2_record.json"), encoding="utf-8"))["hangar"]
    params = dict(params, allow=[a for a in params.get("allow", []) if "Landscape" not in a])
    rows = []
    for script in ("hangar_build.py", "hangar_build_draft.py"):
        plan_path = os.path.join(HERE, "hangar_s2_plan.json")
        if os.path.exists(plan_path):
            os.remove(plan_path)
        runpy.run_path(os.path.join(HERE, script), init_globals={"HANGAR_PARAMS": params})
        blockers = json.load(open(plan_path, encoding="utf-8"))["blockers"]
        rows.append(f"{script}: {len(blockers)} -> {blockers[:3]}")
    unreal.log("BLOCKER_POSITIVE|allow=" + json.dumps(params["allow"]) + " || " + " || ".join(rows))


main()
