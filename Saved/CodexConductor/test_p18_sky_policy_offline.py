"""Offline positive/negative controls for p18_sky_policy.py.

Also writes the policy preview PNG from the same declared defaults.  It does not
import Unreal, touch Content, or apply the held config patch.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

from PIL import Image, ImageDraw, ImageFont


HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
TARGET = HERE / "p18_sky_policy.py"
spec = importlib.util.spec_from_file_location("p18_sky_policy", TARGET)
P = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(P)

passed = 0
failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        passed += 1
    else:
        failed += 1
        print("FAIL|" + name)


def eq(name, got, want):
    check(name + "|got=%r|want=%r" % (got, want), got == want)


def refuses(name, raw, token):
    try:
        P.normalize_args(raw)
    except P.PlanError as exc:
        check(name, token in str(exc))
    else:
        check(name, False)


def args(scene, **overrides):
    row = {"mode": "DRY", "confirm": "DRY P18 SKY POLICY", "scene": scene}
    row.update(overrides)
    return row


# Positive policy controls.
a1 = P.normalize_args(args(1))
p1 = P.plan_from_args(a1)
eq("S1 target count", len(p1["targets"]), 1)
eq("S1 sky only", [r["kind"] for r in p1["targets"]], ["skylight"])
eq("S1 decision flag", p1["gary_to_decide"], "S1 DirectionalLight")
eq("S1 sequence", p1["sequence"], "/Game/InfinityStage/Dev/Sequences/LS_DevScene_01")
eq("S1 never save Klara", p1["never_save"][0], "/Game/KK_S1_Animals/L_Animals")

a4 = P.normalize_args(args(4))
p4 = P.plan_from_args(a4)
eq("S4 target count", len(p4["targets"]), 2)
eq("S4 sky and sun", [r["kind"] for r in p4["targets"]], ["skylight", "sun"])
eq("S4 sequence", p4["sequence"], "/Game/InfinityStage/Dev/Sequences/LS_DevScene_04")
check("S4 no open decision", p4["gary_to_decide"] is None)
eq("save only own sequence", p4["save_only"], [p4["sequence"]])
check("main map never saved", P.EXPECTED_WORLD in p4["never_save"])
check("digest stable", p4["digest"] == P.plan_from_args(a4)["digest"])

# Optional S1 sun path is supported but never the default.
p1_sun = P.plan_from_args(P.normalize_args(args(1, sun_off=True)))
eq("optional S1 sun", [r["kind"] for r in p1_sun["targets"]], ["skylight", "sun"])
check("optional S1 sun clears question", p1_sun["gary_to_decide"] is None)

# Exact confirmations.
for mode in P.MODES:
    eq("confirm " + mode, P.confirm_text(mode), mode + " P18 SKY POLICY")

# Negative argument controls.
refuses("unknown scene", args(2), "SCENE")
refuses("unknown arg", dict(args(4), surprise=True), "UNKNOWN_ARGS")
refuses("bad mode", dict(args(4), mode="WRITE"), "MODE")
refuses("non-bool sky", dict(args(4), skylight_off=1), "POLICY_FLAGS")
refuses("non-bool sun", dict(args(4), sun_off="yes"), "POLICY_FLAGS")
refuses("empty policy", dict(args(1), skylight_off=False, sun_off=False), "EMPTY_POLICY")

# Dirty census controls: sequence-only is accepted; maps or extras are refused.
eq("clean post-save", P.exact_dirty({"content": [], "maps": []}, []), [])
eq("exact sequence dirty", P.exact_dirty({"content": [p4["sequence"]], "maps": []}, [p4["sequence"]]), [])
check("extra content caught", bool(P.exact_dirty({"content": [p4["sequence"], "/Game/Other"], "maps": []},
                                                  [p4["sequence"]])))
check("Klara map dirt caught", any("MAPS_FORBIDDEN" in x for x in
                                    P.exact_dirty({"content": [p4["sequence"]],
                                                   "maps": [p4["klara_level_read_only"]]}, [p4["sequence"]])))
check("missing expected dirty caught", bool(P.exact_dirty({"content": [], "maps": []}, [p4["sequence"]])))

# Snapshot/diff and ownership controls.
eq("equal snapshots", P.state_diff({"a": 1}, {"a": 1}), [])
check("drift caught", bool(P.state_diff({"a": 2}, {"a": 1})))
expected = P._expected_after({
    "sequence": p4["sequence"], "playback": [0, 4900],
    "targets": [{"kind": r["kind"], "guid": r["guid"], "name": r["name"], "owned": []}
                for r in p4["targets"]],
})
eq("expected track per target", [len(r["owned"]) for r in expected["targets"]], [1, 1])
eq("full playback range", expected["targets"][0]["owned"][0]["sections"][0]["range"], [0, 4900])
check("visible default false means hidden", expected["targets"][0]["owned"][0]["sections"][0]["defaults"] == [False])
eq("visibility binds actor bHidden", expected["targets"][0]["owned"][0]["property"], "bHidden")
eq("restore state", expected["targets"][0]["owned"][0]["sections"][0]["completion"], "RESTORE_STATE")

# Source-level safety assertions catch accidental broadening of the live writer.
source = TARGET.read_text(encoding="utf-8")
check("no save map", "save_map(" not in source)
check("no save all", "save_all" not in source.lower())
check("no add possessable", "add_possessable" not in source)
check("no asset delete", "delete_asset" not in source)
check("temporary record precedes modify", source.index("_write_json(record_path, record, exclusive=True)") <
      source.index("sequence.modify()"))
check("map dirty hard gate", "DIRTY_MAPS_FORBIDDEN" in source)
check("success marker", "P18_SKY_POLICY_APPLY_OK" not in source and "%s_APPLY_OK" in source)

runner = (HERE / "p18_sky_policy_run.py").read_text(encoding="utf-8")
request = json.loads((HERE / "p18_sky_policy_request.json").read_text(encoding="utf-8"))
check("runner injects args", "P18_SKY_POLICY_ARGS" in runner)
eq("guarded route", request["arguments"]["tool_name"], "ExecuteProjectPythonFile")
eq("saved relative path", request["arguments"]["arguments"]["relativeSavedPath"],
   "CodexConductor/p18_sky_policy_run.py")

# Policy preview: diagram only, not a render or luma acceptance image.
preview = ROOT / "Docs" / "Conductor" / "Previews" / "P18_sky_policy_preview.png"
preview.parent.mkdir(parents=True, exist_ok=True)
img = Image.new("RGB", (1400, 720), "#111318")
draw = ImageDraw.Draw(img)
font_path = pathlib.Path("C:/Windows/Fonts/segoeui.ttf")
font = ImageFont.truetype(str(font_path), 22) if font_path.is_file() else ImageFont.load_default()
small = ImageFont.truetype(str(font_path), 18) if font_path.is_file() else font
title = ImageFont.truetype(str(font_path), 30) if font_path.is_file() else font
draw.text((54, 32), "P18 SKY POLICY - OFFLINE POLICY PREVIEW", fill="#f0e7d0", font=title)
draw.text((54, 68), "Diagram only. PIE luma and rendered acceptance remain conductor/Gary gates.",
          fill="#aeb7c7", font=small)
rows = [
    ("S1 ANIMALS", "SKYLIGHT OFF", "SUN KEPT", "GARY TO DECIDE", "#9a6b2f"),
    ("S2 SHRINE", "NO LIT SKY MEASURED", "NO SUN MEASURED", "POLICY: OFF", "#39424f"),
    ("S3 SHORE", "NO LIT SKY MEASURED", "NO SUN MEASURED", "POLICY: OFF", "#39424f"),
    ("S4 CHILDREN", "SKYLIGHT OFF", "SUN OFF", "DEFAULT APPLY", "#275c52"),
    ("S5 MOUNTAINS", "NO LIT SKY MEASURED", "NO SUN MEASURED", "POLICY: OFF", "#39424f"),
    ("P06 -> S6", "OUR KEYED SUNSET", "PERSISTENT SUN EXEMPT", "THEN DARK", "#74442d"),
]
for idx, row in enumerate(rows):
    y = 120 + idx * 88
    draw.rounded_rectangle((54, y, 1346, y + 66), radius=10, fill=row[4], outline="#d8c9a6", width=2)
    draw.text((74, y + 18), row[0], fill="white", font=small)
    draw.text((310, y + 18), row[1], fill="white", font=small)
    draw.text((650, y + 18), row[2], fill="white", font=small)
    draw.text((1010, y + 18), row[3], fill="#ffe2a8", font=small)
draw.text((54, 666), "Editor auto-hide is transient and does not define Play state.", fill="#aeb7c7", font=small)
img.save(preview)
check("preview exists", preview.is_file())
check("preview dimensions", Image.open(preview).size == (1400, 720))

print("P18_SKY_POLICY_TESTS|pass=%d|fail=%d|preview=%s" % (passed, failed, preview))
raise SystemExit(1 if failed else 0)
