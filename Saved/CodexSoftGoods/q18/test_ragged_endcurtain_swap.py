"""Offline positive and negative controls for q18/ragged_endcurtain_swap.py."""
from __future__ import annotations

import copy
import importlib.util
import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location(
    "q18_ragged_endcurtain_swap", os.path.join(HERE, "ragged_endcurtain_swap.py")
)
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)

passed = []
failed = []
positive_count = 0
negative_count = 0


def check(name, fn, polarity):
    global positive_count, negative_count
    positive_count += int(polarity == "positive")
    negative_count += int(polarity == "negative")
    try:
        fn()
        passed.append(name)
    except Exception as exc:  # noqa: BLE001 - harness reports every control.
        failed.append((name, repr(exc)))


def rejects(name, fn, text):
    def body():
        try:
            fn()
        except MOD.PlanError as exc:
            assert text in str(exc), (text, str(exc))
            return
        raise AssertionError("did not reject")

    check(name, body, "negative")


def snapshot(passage="P02", cache=MOD.SOURCE_CACHE):
    spec = MOD.PASSAGES[passage]
    return {
        "actor_label": spec["actor"],
        "actor_path": "/Game/Test.Test:PersistentLevel." + spec["actor"],
        "transform": {
            "location": [100.0, 200.0, 300.0],
            "rotation": [0.0, 0.0, 22.908],
            "scale": [1.0, 1.0, 1.0],
        },
        "component": {
            "cache": cache,
            "manual_tick": True,
            "running": True,
            "looping": False,
            "override_materials": [spec["material"]],
            "resolved_materials": [spec["material"]],
            "material_parameters": [{
                "path": spec["material"],
                "image_texture": "/Game/InfinityStage/Curtains/Image/Textures/T_Test",
                "planar_scalars": {
                    "PlanarMapping": 1.0,
                    "PlanarY0Cm": -940.0,
                    "PlanarWidthCm": 1880.0,
                    "PlanarTopZCm": 1020.0,
                    "PlanarHeightCm": 1000.0,
                    "PlanarMinZCm": -100000.0,
                },
            }],
        },
        "sequence": spec["sequence"],
        "binding_guid": "0123456789ABCDEF0123456789ABCDEF",
        "binding_label": spec["actor"],
        "sections": [{
            "asset": cache,
            "range": [-177, 124],
            "start_frame_offset": 23200,
            "end_frame_offset": 0,
            "play_rate": 1.0,
            "completion_mode": "KEEP_STATE",
            "reverse": False,
            "looping": False,
        }],
    }


def expected_swap(passage="P02"):
    return MOD.build_expected(snapshot(passage), MOD.PASSAGES[passage], MOD.SOURCE_CACHE, MOD.TARGET_CACHE)


check("POS validate P02 DRY", lambda: MOD.validate_args({
    "mode": "DRY", "passage": "P02", "confirm": "DRY_RAGGED_ENDCURTAIN_P02_ONLY"
}), "positive")
check("POS validate P03 APPLY", lambda: MOD.validate_args({
    "mode": "APPLY", "passage": "P03", "confirm": "APPLY_RAGGED_ENDCURTAIN_P03_ONLY", "decided_by": "Gary"
}), "positive")
check("POS cache frame ranges", lambda: MOD.validate_cache_frame_ranges((450, 780), (450, 1080)), "positive")
check("POS clean initial census", lambda: MOD.validate_census({"content": [], "maps": []}), "positive")
check("POS exact mutation census", lambda: MOD.validate_census(
    {"content": [MOD.PASSAGES["P02"]["sequence"]], "maps": [MOD.EXPECTED_WORLD]},
    [MOD.PASSAGES["P02"]["sequence"]], [MOD.EXPECTED_WORLD]
), "positive")
check("POS swaps only two asset fields", lambda: (
    (lambda before, after: (
        (_ for _ in ()).throw(AssertionError("wrong component cache"))
        if after["component"]["cache"] != MOD.TARGET_CACHE else None,
        (_ for _ in ()).throw(AssertionError("wrong section cache"))
        if after["sections"][0]["asset"] != MOD.TARGET_CACHE else None,
        (_ for _ in ()).throw(AssertionError("preservation failure"))
        if dict(after, component=dict(after["component"], cache=MOD.SOURCE_CACHE),
                sections=[dict(after["sections"][0], asset=MOD.SOURCE_CACHE)]) != before else None
    ))(snapshot(), expected_swap())
), "positive")
check("POS input remains unmodified", lambda: (
    (lambda source: (
        MOD.build_expected(source, MOD.PASSAGES["P02"], MOD.SOURCE_CACHE, MOD.TARGET_CACHE),
        (_ for _ in ()).throw(AssertionError("input mutated")) if source != snapshot() else None
    ))(snapshot())
), "positive")
check("POS numeric readback tolerance", lambda: (
    (lambda got, want: (
        got["transform"]["location"].__setitem__(0, got["transform"]["location"][0] + 0.009),
        got["transform"]["rotation"].__setitem__(2, got["transform"]["rotation"][2] + 0.0009),
        (_ for _ in ()).throw(AssertionError(MOD.snapshot_differences(got, want)))
        if MOD.snapshot_differences(got, want) else None
    ))(copy.deepcopy(expected_swap()), expected_swap())
), "positive")
check("POS revert restores two fields", lambda: (
    (lambda before, after: (
        (lambda restored: (
            (_ for _ in ()).throw(AssertionError(restored)) if restored != before else None
        ))(MOD.build_revert_expected(after, {"before": before, "expected_after": after}))
    ))(snapshot(), expected_swap())
), "positive")
check("POS enum helper", lambda: (
    (_ for _ in ()).throw(AssertionError("enum"))
    if not MOD._enum_is("<MovieSceneCompletionMode.KEEP_STATE: 0>", "KEEP_STATE") else None
), "positive")

rejects("NEG wrong actor label", lambda: MOD.build_expected(
    dict(snapshot(), actor_label="P02 End Drape WRONG"), MOD.PASSAGES["P02"], MOD.SOURCE_CACHE, MOD.TARGET_CACHE
), "ACTOR_LABEL")
rejects("NEG two sections bound", lambda: (
    (lambda value: MOD.build_expected(value, MOD.PASSAGES["P02"], MOD.SOURCE_CACHE, MOD.TARGET_CACHE))(
        (lambda value: (value["sections"].append(copy.deepcopy(value["sections"][0])), value)[1])(snapshot())
    )
), "GC_SECTION_COUNT")
rejects("NEG MI override lost", lambda: (
    (lambda value: MOD.build_expected(value, MOD.PASSAGES["P02"], MOD.SOURCE_CACHE, MOD.TARGET_CACHE))(
        (lambda value: (value["component"].update(override_materials=[]), value)[1])(snapshot())
    )
), "MI_OVERRIDE_LOST")
rejects("NEG MI no longer resolves", lambda: (
    (lambda value: MOD.build_expected(value, MOD.PASSAGES["P02"], MOD.SOURCE_CACHE, MOD.TARGET_CACHE))(
        (lambda value: (value["component"].update(resolved_materials=[]), value)[1])(snapshot())
    )
), "MI_RESOLVED_MISMATCH")
rejects("NEG playback flags drift", lambda: (
    (lambda value: MOD.build_expected(value, MOD.PASSAGES["P02"], MOD.SOURCE_CACHE, MOD.TARGET_CACHE))(
        (lambda value: (value["component"].update(running=False), value)[1])(snapshot())
    )
), "COMPONENT_PLAYBACK_FLAGS")
rejects("NEG offset changed", lambda: (
    (lambda want, got: (
        (_ for _ in ()).throw(MOD.PlanError("READBACK: " + " | ".join(MOD.snapshot_differences(got, want))))
        if MOD.snapshot_differences(got, want) else None
    ))(expected_swap(), (lambda value: (value["sections"][0].update(start_frame_offset=23201), value)[1])(
        copy.deepcopy(expected_swap())
    ))
), "start_frame_offset")
rejects("NEG foreign dirty package", lambda: MOD.validate_census(
    {"content": [MOD.PASSAGES["P02"]["sequence"], "/Game/Foreign"], "maps": [MOD.EXPECTED_WORLD]},
    [MOD.PASSAGES["P02"]["sequence"]], [MOD.EXPECTED_WORLD]
), "DIRTY_CENSUS")
rejects("NEG cache frame range mismatch", lambda: MOD.validate_cache_frame_ranges((450, 780), (450, 1079)),
        "CACHE_FRAME_RANGE_TARGET")
rejects("NEG component no-op", lambda: MOD.build_expected(
    snapshot(cache=MOD.TARGET_CACHE), MOD.PASSAGES["P02"], MOD.SOURCE_CACHE, MOD.TARGET_CACHE
), "NOOP_COMPONENT")
rejects("NEG bad confirm", lambda: MOD.validate_args({
    "mode": "APPLY", "passage": "P02", "confirm": "APPLY", "decided_by": "Gary"
}), "CONFIRM_MISMATCH")
rejects("NEG apply decision missing", lambda: MOD.validate_args({
    "mode": "APPLY", "passage": "P02", "confirm": "APPLY_RAGGED_ENDCURTAIN_P02_ONLY"
}), "DECIDED_BY_REQUIRED")
rejects("NEG wrong passage", lambda: MOD.validate_args({
    "mode": "DRY", "passage": "P04", "confirm": "DRY_RAGGED_ENDCURTAIN_P04_ONLY"
}), "PASSAGE_INVALID")
rejects("NEG revert drift", lambda: MOD.build_revert_expected(
    (lambda value: (value["component"].update(running=False), value)[1])(copy.deepcopy(expected_swap())),
    {"before": snapshot(), "expected_after": expected_swap()}
), "STATE_DRIFTED")

for name in passed:
    print("PASS|" + name)
for name, detail in failed:
    print("FAIL|%s|%s" % (name, detail))
print("Q18_OFFLINE_HARNESS|passed=%d|failed=%d|positive=%d|negative=%d" %
      (len(passed), len(failed), positive_count, negative_count))
raise SystemExit(1 if failed else 0)
