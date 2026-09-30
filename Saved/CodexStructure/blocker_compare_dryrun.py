"""Validation harness for the blocker-gap fix (30 Sep): dry-run hangar_build.py AND a draft (the mode file
names it; default hangar_build_draft.py, copied into Saved/ for the run) for all six Scenes with each
record's own HANGAR_PARAMS (Scene 4: defaults), and compare the blocker lists. Dry runs only: the builder
returns before any mutation.
FALSIFIABLE (the adversarial review's point, 30 Sep): each scene's plan file is DELETED before its run and
must exist after it (so a builder that throws early cannot be judged on an old plan); a missing script, any
error, a sky blocker, or any blocker the prediction does not allow makes it FAIL. The prediction, made
before the draft existed: every scene clean under both builders (S1/S5/S6 planes trimmed, S2/S3 landscapes
allowed by label, S4 a void), the sky never appears, and any NEW blocker is a previously skipped large
actor, named here for review (so it FAILS until judged). Writes blocker_compare.json. Lean: main()."""
import json
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
MODE = os.path.join(HERE, "blocker_compare_mode.json")
DRAFT = json.load(open(MODE, encoding="utf-8")).get("draft", "hangar_build_draft.py") if os.path.exists(MODE) else "hangar_build_draft.py"
SCRIPTS = ("hangar_build.py", DRAFT)


def main():
    out, failures = {}, []
    for script in SCRIPTS:
        path = os.path.join(HERE, script)
        if not os.path.exists(path):
            failures.append(f"{script} missing")
            continue
        out[script] = {}
        for n in range(1, 7):
            rec_path = os.path.join(HERE, f"hangar_s{n}_record.json")
            params = json.load(open(rec_path, encoding="utf-8"))["hangar"] if os.path.exists(rec_path) else {"scene": 4}
            plan_path = os.path.join(HERE, f"hangar_s{n}_plan.json")
            if os.path.exists(plan_path):
                os.remove(plan_path)
            try:
                runpy.run_path(path, init_globals={"HANGAR_PARAMS": params})
            except Exception as exc:  # noqa: BLE001
                out[script][n] = {"error": str(exc)[:300]}
                failures.append(f"{script} S{n} raised: {str(exc)[:120]}")
                continue
            if not os.path.exists(plan_path):
                out[script][n] = {"error": "no plan written"}
                failures.append(f"{script} S{n} wrote no plan")
                continue
            plan = json.load(open(plan_path, encoding="utf-8"))
            out[script][n] = {"blockers": plan["blockers"], "problems": plan["problems"],
                              "unchecked_large_no_collision": plan.get("unchecked_large_no_collision")}
    diff = {}
    if all(isinstance(out.get(s), dict) and len(out[s]) == 6 for s in SCRIPTS):
        old, new = out[SCRIPTS[0]], out[SCRIPTS[1]]
        for n in range(1, 7):
            if "blockers" not in old[n] or "blockers" not in new[n]:
                continue
            ob, nb = set(old[n]["blockers"]), set(new[n]["blockers"])
            label = lambda b: b.split(" (")[0]
            diff[n] = {"only_old": sorted(ob - nb), "only_new": sorted(nb - ob),
                       "sky_in_new": any("Sun Moon" in b or "CelestialRig" in b or "SkySphere" in b for b in nb)}
            if diff[n]["sky_in_new"]:
                failures.append(f"S{n}: the sky appears as a blocker")
            if nb:
                failures.append(f"S{n}: draft blockers (prediction: none) -> {sorted(set(map(label, nb)))}")
            if ob:
                failures.append(f"S{n}: current-builder blockers (prediction: none) -> {sorted(set(map(label, ob)))}")
            if old[n]["problems"] != new[n]["problems"]:
                failures.append(f"S{n}: analytic problems differ between builders")
    out["diff"], out["failures"] = diff, failures
    json.dump(out, open(os.path.join(HERE, "blocker_compare.json"), "w"), indent=1, default=str)
    dirty = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()), len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
    verdict = "BLOCKER_COMPARE_PASS" if not failures else "BLOCKER_COMPARE_FAIL"
    unreal.log(f"{verdict}|draft={DRAFT}|failures={len(failures)}|dirty_after={dirty[0]}+{dirty[1]}|" + " || ".join(failures[:12]))


main()
