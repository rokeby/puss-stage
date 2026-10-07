"""Probe after BW_APPLY_FAILED LAYERS (BWAPPLY-20261007-151052): are the six Structures CURRENT, and (optional) what does
a plain re-materialize of one Structure move, with NO field change.  Args probe_structure_current_args.json
{"run": "...", "rematerialize": null | "Infinity Stage - Structure 01"}.
- Phase 1 (read-only): is_structure_current() per Structure.
- Phase 2 (only if "rematerialize" names one): snapshot -> materialize_structure() -> snapshot -> per-layer diff
  (count, transforms changed, max translation delta cm).  DIRTIES THE LEVEL, NEVER SAVES: needs a Don't-Save restart.
Output probe_structure_current_<run>.json; markers BWPROBE_OK|run=.. / BWPROBE_FAILED|run=..|reason."""
import json
import runpy

HERE = "E:/PussStage/Saved/CodexConductor/BarbedWire_20261007/"


def main():
    import unreal
    args = json.load(open(HERE + "probe_structure_current_args.json", encoding="utf-8"))
    run = args["run"]
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    structs = {str(a.get_actor_label()): a for a in
               unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageStructureActor)}
    out = {"run": run, "current": {k: bool(v.is_structure_current()) for k, v in sorted(structs.items())}}
    target = args.get("rematerialize")
    if target:
        g = runpy.run_path(HERE + "barbed_apply.py", run_name="__probe__")

        class C:
            u = unreal

            def fail(self, msg):
                raise RuntimeError(msg)

            def log(self, msg):
                unreal.log(msg)
        c = C()
        s = structs[target]
        before = g["snapshot"](c, s)
        ok = bool(s.materialize_structure())
        after = g["snapshot"](c, s)
        diff = {}
        for key in sorted(set(before) | set(after)):
            b, a = before.get(key), after.get(key)
            if isinstance(b, list) and isinstance(a, list):
                b, a = {"all": b}, {"all": a}
            if isinstance(b, dict) and isinstance(a, dict):
                for layer in sorted(set(b) | set(a)):
                    lb, la = b.get(layer) or [], a.get(layer) or []
                    if lb != la:
                        d = {"before_n": len(lb), "after_n": len(la)}
                        try:
                            pairs = list(zip(lb, la))
                            d["changed"] = sum(1 for x, y in pairs if x != y)
                            d["max_dt_cm"] = max((max(abs(x["loc"][i] - y["loc"][i]) for i in range(3))
                                                  for x, y in pairs if isinstance(x, dict) and "loc" in x), default=None)
                            d["first_changed"] = next(([x, y] for x, y in pairs if x != y), None)
                            # order-independent: nearest after-instance for every before-instance (cm), and
                            # whether rotation/scale of that nearest one matches (1e-3)
                            def _near(x, pool):
                                best, bd = None, None
                                for y in pool:
                                    dd = max(abs(x["loc"][i] - y["loc"][i]) for i in range(3))
                                    if bd is None or dd < bd:
                                        best, bd = y, dd
                                return best, bd
                            worst, rot_bad = 0.0, 0
                            for x in lb:
                                y, dd = _near(x, la)
                                worst = max(worst, dd or 0.0)
                                if y is not None and any(abs(p - q) > 1e-3 for p, q in zip(x["quat"] + x["scale"], y["quat"] + y["scale"])):
                                    rot_bad += 1
                            d["unordered_max_nearest_cm"] = worst
                            d["unordered_rot_or_scale_mismatch"] = rot_bad
                        except Exception as exc:  # shape unknown: record only counts
                            d["note"] = repr(exc)[:120]
                        diff["%s/%s" % (key, layer)] = d
            elif b != a:
                diff[key] = {"before": str(b)[:200], "after": str(a)[:200]}
        out["rematerialize"] = {"target": target, "materialize_ok": ok, "current_after": bool(s.is_structure_current()),
                                "diff": diff, "snapshot_keys": sorted(before)}
    path = HERE + "probe_structure_current_%s.json" % run
    with open(path, "w", encoding="utf-8") as h:
        json.dump(out, h, indent=1, default=str)
    unreal.log("BWPROBE_OK|run=%s|current=%s|remat=%s|path=%s" % (
        run, json.dumps(out["current"]), bool(target), path))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("BWPROBE_FAILED|%r" % (exc,))
