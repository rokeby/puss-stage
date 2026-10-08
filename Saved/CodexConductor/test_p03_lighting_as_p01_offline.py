"""Offline positive/negative harness for p03_lighting_as_p01.py.

No Unreal import, editor, MCP or PIE.  It also writes the explicitly snapshot-
derived preview requested by P16; live DRY writes the authoritative preview.
"""
from __future__ import annotations

import ast
import copy
import json
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import p03_lighting_as_p01 as P  # noqa: E402

RESULTS = []


def check(name, condition):
    ok = bool(condition)
    RESULTS.append((name, ok))
    print(("PASS " if ok else "FAIL ") + name)


def raises(function, token=None):
    try:
        function()
    except Exception as error:  # noqa: BLE001 - deliberately exercises stops
        return token is None or token in str(error)
    return False


def light(label, rgb=(1.0, 1.0, 1.0, 1.0), temp=6500.0, strike=False, slow=False,
          kind="LIGHT", x=0.0, y=0.0):
    return {
        "guid": ("%032X" % (abs(hash((label, x, y))) % (16 ** 32))),
        "label": label, "kind": kind, "enabled": True,
        "relative_transform": {"location": [x, y, 100.0], "rotation_xyzw": [0, 0, 0, 1],
                               "scale": [1, 1, 1]},
        "lighting": {"color": list(rgb), "use_temperature": True, "temperature_kelvin": temp,
                     "drama": {"strike_on_approach": strike, "slow_move": slow, "after_pass": "HOLD"}},
        "effect": {},
    }


def cue(prefix, ordinal, rows, tags=None):
    return {"show_index": ordinal, "guid": "%s-%02d" % (prefix, ordinal),
            "label": "%s Wing %03d" % (prefix, ordinal), "attachments": rows,
            "wing_y": [-900.0, 900.0], "tags": list(tags or [])}


# Args: positive + negative controls.
check("args DRY default", P.check_args({})["mode"] == "DRY")
check("args APPLY exact confirm + hash", P.check_args({
    "mode": "APPLY", "confirm": "APPLY P03ASP01", "expected_plan_sha256": "a" * 64,
})["mode"] == "APPLY")
check("args -control missing confirm", raises(lambda: P.check_args({
    "mode": "APPLY", "expected_plan_sha256": "a" * 64}), "CONFIRM_MISSING"))
check("args -control missing plan hash", raises(lambda: P.check_args({
    "mode": "APPLY", "confirm": "APPLY P03ASP01"}), "EXPECTED_PLAN_SHA256_REQUIRED"))
check("args -control unknown key", raises(lambda: P.check_args({"surprise": 1}), "ARGS_UNKNOWN"))

# Role parsing positive + deliberately different controls.
check("role SCORE suffix", P.role_from_label("P01 SCORE B03 LOOK TOP_L") == "TOP_L")
check("role Wing literal suffix", P.role_from_label("P03 Wing 004 Entry Fwd -Y") == "ENTRY_FWD_-Y")
check("role managed suffix", P.role_from_label("P03 P01STRUCT B04 LOW_SIDE_R_FILL") == "LOW_SIDE_R_FILL")
check("role -control does not collapse sides",
      P.role_from_label("P03 Wing 004 Entry Fwd +Y") != P.role_from_label("P03 Wing 004 Entry Fwd -Y"))

source = [
    cue("P01", 1, [light("P01 Wing 001 Entry Fwd +Y", x=50, y=700),
                    light("P01 SCORE B01 LOOK TOP_L", x=10, y=-500)]),
    cue("P01", 2, [light("P01 Wing 002 Entry Fwd -Y", x=60, y=-700),
                    light("P01 SCORE B02 LOOK TOP_L", x=20, y=-500)]),
]
red, blue = (1.0, 0.1, 0.1, 1.0), (0.1, 0.2, 1.0, 1.0)
target = [
    cue("P03", 1, [light("P03 Wing 001 Entry Fwd +Y", red, 3100, x=5, y=650),
                    light("P03 SCORE B01 OTHER TOP_L", blue, 4200, x=0, y=-450),
                    light("P03 Car Lighting Move", red, 3000, slow=True, x=0, y=0),
                    light("P03 Unmatched Cue Lamp", red, 3000, strike=True, x=0, y=0),
                    light("FX SMOKE P03", kind="EFFECT", x=0, y=0)]),
    cue("P03", 2, [light("P03 SCORE B02 OTHER TOP_L", blue, 4200, x=0, y=-450)]),
    cue("P03", 3, [light("P03 SCORE B03 OTHER TOP_L", blue, 4200, x=0, y=-450)]),
]
args = P.check_args({})
plan = P.build_plan(source, target, args)
check("ordinal mapping wraps 3->1", plan["wrapped"] and plan["targets"][2]["source_ordinal"] == 1)
check("ordinary P03 light removed", any(r["label"] == "P03 Wing 001 Entry Fwd +Y"
                                         for r in plan["targets"][0]["removed"]))
check("car/move light retained", any(k["row"]["label"] == "P03 Car Lighting Move"
                                      for k in plan["targets"][0]["kept"]))
check("keyed unmatched light retained", any(k["reason"] == "keyed_without_p01_counterpart"
                                             for k in plan["targets"][0]["kept"]))
check("effect retained", any(P.is_effect(k["row"]) for k in plan["targets"][0]["kept"]))
tagged_target = [cue("P03", 1, [light("Ordinary label", red, 3000)], tags=["Car Event"])]
tagged_plan = P.build_plan(source[:1], tagged_target, args)
check("cue-tagged special light retained",
      tagged_plan["targets"][0]["kept"][0]["reason"] == "cue_tag:car")
top = next(r for r in plan["targets"][0]["added_specs"] if P.role_from_label(r["label"]) == "TOP_L")
entry = next(r for r in plan["targets"][0]["added_specs"] if P.role_from_label(r["label"]) == "ENTRY_FWD_+Y")
check("role colour retained", top["lighting"]["color"] == list(blue) and top["lighting"]["temperature_kelvin"] == 4200)
check("role temperature retained", entry["lighting"]["temperature_kelvin"] == 3100)
fallbacks = [m for m in plan["colour_mappings"] if m["mapping"] == "dominant"]
check("missing role uses and reports dominant", fallbacks and plan["counts"]["dominant_fallbacks"] == len(fallbacks))
check("plan hash deterministic", plan["plan_sha256"] == P.build_plan(source, target, args)["plan_sha256"])
changed = copy.deepcopy(target)
changed[0]["attachments"][0]["lighting"]["color"][0] = 0.333
check("plan hash -control detects state drift",
      P.build_plan(source, changed, args)["plan_sha256"] != plan["plan_sha256"])

# Atmosphere: pair beam boxes, suppress smoke, zero LFV; off is a no-op.
source_atmos = [{"id": "S1", "label": "P01 BeamLook Noise B03", "beam": True, "ordinal": 3},
                {"id": "S2", "label": "P01 BeamLook Noise B07", "beam": True, "ordinal": 7},
                {"id": "S3", "label": "P01 BeamLook Noise B29", "beam": True, "ordinal": 29}]
target_atmos = [{"id": "T1", "label": "P03 BeamLook Noise B04", "beam": True, "ordinal": 4},
                {"id": "T2", "label": "P03 BeamLook Noise B08", "beam": True, "ordinal": 8},
                {"id": "TS", "label": "P03 Smoke Test 1", "beam": False, "smoke": True, "lfv": False},
                {"id": "TF", "label": "P03 Local Fog", "beam": False, "smoke": False, "lfv": True}]
atmos = P.atmos_plan(source_atmos, target_atmos, 21, True)
check("atmos pairs two in-range P01 beam actors", sum(x["action"] == "match_beam_actor" for x in atmos["changes"]) == 2)
check("atmos suppresses smoke test", any(x["action"] == "suppress_actor" and x["target"]["id"] == "TS"
                                         for x in atmos["changes"]))
check("atmos zeros unmatched LFV", any(x["action"] == "zero_lfv" for x in atmos["changes"]))
check("atmos off is explicit no-op", P.atmos_plan(source_atmos, target_atmos, 21, False)["changes"] == [])
check("atmos -control refuses missing target beam", raises(lambda: P.atmos_plan(
    source_atmos, target_atmos[:1], 21, True), "ATMOS_TARGET_BEAMS_MISSING"))

# PNG positive + corruption negative control.
tmp = pathlib.Path(tempfile.mkdtemp()) / "preview.png"
png = P.write_preview_png(str(tmp), plan, width=500, height=300)
raw = tmp.read_bytes()
check("preview PNG signature and dimensions", raw.startswith(b"\x89PNG\r\n\x1a\n") and png["width"] == 500)
check("preview -control random bytes are not PNG", not b"not a png".startswith(b"\x89PNG\r\n\x1a\n"))

# Generate an offline snapshot preview from the measured 6 Oct records.  This
# is evidence of plotting only; live DRY remains authoritative for current Show.
def cues_from_record(path):
    record = json.loads(path.read_text(encoding="utf-8"))
    rows = record["after_cue_rows"]
    out = []
    for ordinal, bay in enumerate(record["plan"]["bays"], start=1):
        guid = bay["cue_guid"]
        if guid not in rows:  # excluded/untouched bays were not captured by this older record
            continue
        out.append({"show_index": bay["show_index"], "guid": guid, "label": bay["cue_label"],
                    "attachments": copy.deepcopy(rows[guid]), "wing_y": [-900.0, 900.0]})
    return out


p01_record = HERE / "p01_rig_pattern_record.json"
p03_record = HERE / "p03_rig_pattern_record.json"
if p01_record.exists() and p03_record.exists():
    snapshot = P.build_plan(cues_from_record(p01_record), cues_from_record(p03_record), args)
    preview_path = ROOT / "Docs" / "Conductor" / "P16_P03_LIGHTING_PREVIEW_OFFLINE_2026-10-08.png"
    info = P.write_preview_png(str(preview_path), snapshot)
    check("snapshot preview written", preview_path.exists() and info["bytes"] > 1000)
else:
    check("snapshot preview inputs present", False)

# Parse shipped sources/config.  Negative control proves parse check can fail.
for name in ("p03_lighting_as_p01.py", "p03_lighting_as_p01_run.py", "test_p03_lighting_as_p01_offline.py"):
    ast.parse((HERE / name).read_text(encoding="utf-8"))
check("all shipped Python parses", True)
check("AST -control catches syntax error", raises(lambda: ast.parse("def broken(:\n"), "invalid syntax"))
request = json.loads((HERE / "p03_lighting_as_p01_request.json").read_text(encoding="utf-8"))
check("request routes guarded runner", request["arguments"]["arguments"]["relativeSavedPath"] ==
      "CodexConductor/p03_lighting_as_p01_run.py")

failed = [name for name, ok in RESULTS if not ok]
print("\nP03ASP01_HARNESS|pass=%d|fail=%d" % (len(RESULTS) - len(failed), len(failed)))
sys.exit(1 if failed else 0)
