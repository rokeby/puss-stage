"""Offline harness for fx_smoke_place.py (no Unreal): args, bay choice, pair-space geometry, plan, leftovers, revert
gate, C++ contracts and source guards. Each property has a + case and a - control.
Run: python Saved/CodexConductor/Effects_20261007/test_fx_smoke_place_offline.py"""
import ast
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import fx_smoke_place as F  # noqa: E402

RESULTS = []


def check(name, cond):
    RESULTS.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name)


def raises(fn, token=None):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        return token is None or token in str(exc)
    return False


# ---------------------------------------------------------------- args
A = F.check_args({})
check("args: DRY default, P01/P03/P04", A["mode"] == "DRY" and sorted(A["passages"]) == ["P01", "P03", "P04"])
check("args: P03 default bays are its Breath beam bays 8/13/18", A["passages"]["P03"]["bays"] == [8, 13, 18])
check("args -: APPLY without confirm", raises(lambda: F.check_args({"mode": "APPLY"}), "CONFIRM_MISSING"))
check("args -: APPLY with the wrong token", raises(lambda: F.check_args({"mode": "APPLY", "confirm": "APPLY FXEFFECTBPS"}),
                                                   "CONFIRM_MISSING"))
check("args: APPLY with confirm", F.check_args({"mode": "APPLY", "confirm": "APPLY FXSMOKE"})["mode"] == "APPLY")
check("args: REVERT with confirm", F.check_args({"mode": "REVERT", "confirm": "REVERT FXSMOKE"})["mode"] == "REVERT")
check("args -: bays AND count", raises(lambda: F.check_args({"passages": {"P03": {"bays": [1], "count": 1}}}),
                                       "BAYS_XOR_COUNT"))
check("args -: 5 pots in one passage", raises(lambda: F.check_args({"passages": {"P03": {"count": 5}}}),
                                              "TOO_MANY_IN_PASSAGE"))
check("args -: P07", raises(lambda: F.check_args({"passages": {"P07": {"count": 1}}}), "PASSAGE_KEY"))
check("args -: bay 0", raises(lambda: F.check_args({"passages": {"P03": {"bays": [0]}}}), "BAYS"))
check("args -: sides list of wrong length", raises(
    lambda: F.check_args({"passages": {"P03": {"bays": [1, 2], "sides": ["L"]}}}), "SIDES"))
check("args: explicit sides list", F.check_args({"passages": {"P03": {"bays": [1, 2], "sides": ["R", "R"]}}})
      ["passages"]["P03"]["sides"] == ["R", "R"])
check("args -: unknown key", raises(lambda: F.check_args({"bays": [1]}), "UNKNOWN_ARGS"))
check("args -: offstage 900 cm", raises(lambda: F.check_args({"offstage_cm": 900}), "OFFSTAGE_RANGE"))
check("args -: feeds_local_medium not bool", raises(lambda: F.check_args({"feeds_local_medium": 1}),
                                                    "FEEDS_LOCAL_MEDIUM_BOOL"))
check("args: smoke medium off by default (Gary: P03 too foggy)", A["feeds_local_medium"] is False)
check("args: lower-case p03 normalised", "P03" in F.check_args({"passages": {"p03": {"count": 1}}})["passages"])

# ---------------------------------------------------------------- bays
check("spread: 21 bays x3 -> 4, 11, 18", F.spread_ordinals(21, 3) == [4, 11, 18])
check("spread: 48 bays x3 -> 9, 25, 41", F.spread_ordinals(48, 3) == [9, 25, 41])
check("spread -: more pots than bays", raises(lambda: F.spread_ordinals(2, 3), "COUNT_EXCEEDS_BAYS"))
check("sides: alternate L,R,L", F.side_list("alternate", 3) == ["L", "R", "L"])


# ---------------------------------------------------------------- geometry
def box(cy, half_w, half_d=5.0, h=600.0, cx=0.0):
    return [[cx + sx * half_d, cy + sy * half_w, z] for sx in (-1, 1) for sy in (-1, 1) for z in (0.0, h)]


LEFT = box(-972.6, 200.0)      # P04 Wing 001 left pivot y (lighting_looks_top_probe.json) with a 4 m wide flat
RIGHT = box(932.1, 200.0)
check("edge: left flat inner edge = 772.6", abs(F.inner_edge(LEFT, -1) - 772.6) < 1e-6)
check("edge: right flat inner edge = 732.1", abs(F.inner_edge(RIGHT, 1) - 732.1) < 1e-6)
check("edge -: left flat read as right (sign convention broken)", raises(lambda: F.inner_edge(LEFT, 1),
                                                                         "PANEL_STRADDLES_CENTRE"))
check("edge -: a flat straddling the centre", raises(lambda: F.inner_edge(box(100.0, 300.0), 1),
                                                     "PANEL_STRADDLES_CENTRE"))
check("edge -: 7 corners", raises(lambda: F.inner_edge(LEFT[:7], -1), "CORNERS"))
tl = F.pot_transform(0.0, 772.6, -1, A)
tr = F.pot_transform(0.0, 732.1, 1, A)
check("pot: left pot offstage of the edge (y=-812.6), yaw +90 (aims at the centre)",
      abs(tl["location"][1] + 812.6) < 1e-6 and tl["yaw"] == 90.0)
check("pot: right pot offstage of the edge (y=+772.1), yaw -90", abs(tr["location"][1] - 772.1) < 1e-6
      and tr["yaw"] == -90.0)
check("pot: behind the flat along +X by along_cm", tl["location"][0] == 80.0 and tl["location"][2] == 0.0)
check("pot -control: offstage 0 puts it ON the edge, not in the corridor", abs(abs(F.pot_transform(
    0.0, 772.6, -1, dict(A, offstage_cm=0.0))["location"][1]) - 772.6) < 1e-9)


def fake_live(n_bays, label_prefix):
    return {"passage_guid": "G", "bays": [{"ordinal": i, "cue_guid": "%s%02d" % (label_prefix, i),
                                           "label": "%s Wing %03d" % (label_prefix, i),
                                           "L": {"x": 0.0, "corners": LEFT}, "R": {"x": 0.0, "corners": RIGHT}}
                                          for i in range(1, n_bays + 1)]}


LIVE = {"P01": fake_live(48, "P01"), "P03": fake_live(21, "P03"), "P04": fake_live(21, "P04")}
rows = F.plan_rows(A, LIVE)
check("plan: 9 pots (3 per passage)", len(rows) == 9)
check("plan: P03 on bays 8/13/18, L R L", [(r["ordinal"], r["side"]) for r in rows if r["passage"] == "P03"]
      == [(8, "L"), (13, "R"), (18, "L")])
check("plan: labels FX SMOKE Pnn Bxx S", rows[0]["label"] == "FX SMOKE P01 B09 L")
check("plan: every pot behind its flat (|y| > inner edge)", all(abs(r["location"][1]) > r["inner_edge_cm"]
                                                                for r in rows))
check("plan -: bay past the passage end", raises(lambda: F.plan_rows(
    F.check_args({"passages": {"P03": {"bays": [22]}}}), LIVE), "BAY_OUT_OF_RANGE"))
check("plan -: passage not in the live Show", raises(lambda: F.plan_rows(
    F.check_args({"passages": {"P05": {"count": 1}}}), LIVE), "PASSAGE_NOT_LIVE"))

# ---------------------------------------------------------------- leftovers / revert gate
check("leftovers: our labels found", F.leftovers(["P03 SCORE B08 TOP_L", "FX SMOKE P03 B08 L"]) == ["FX SMOKE P03 B08 L"])
check("leftovers -control: candle / score labels ignored", F.leftovers(["FX TEST - S6 Candle", "P03 Smoke Test 1"]) == [])
STATE = {"guid": "AB", "label": "FX SMOKE P03 B08 L", "kind": "EFFECT", "relative_transform": {"location": [80.0, -812.6, 0.0]},
         "effect": {"output": 0.5}}
REC = {"status": "applied", "added": [{"guid": "AB", "label": STATE["label"], "cue_guid": "C", "expected": STATE}]}
moved = json.loads(json.dumps(STATE))
moved["relative_transform"]["location"][0] = 300.0
renamed = dict(STATE, label="something else")
check("revert: unchanged live state passes", F.revert_gate(REC, {"AB": STATE}, False)[0])
check("revert -: Gary moved it, no accept_drift", not F.revert_gate(REC, {"AB": moved}, False)[0])
check("revert: Gary moved it, accept_drift", F.revert_gate(REC, {"AB": moved}, True)[0])
check("revert -: identity changed even with accept_drift", not F.revert_gate(REC, {"AB": renamed}, True)[0])
check("revert -: guid missing", not F.revert_gate(REC, {"AB": None}, True)[0])
check("revert -: record not applied", raises(lambda: F.revert_gate(dict(REC, status="prepared"), {"AB": STATE}, True),
                                             "REVERT_RECORD_NOT_APPLIED"))

# ---------------------------------------------------------------- C++ contracts
src_dir = ROOT / "Plugins/InfinityStage/Source/InfinityStage"
lib_h = (src_dir / "Public/InfinityStageEffectLibrary.h").read_text(encoding="utf-8")
eff_cpp = (src_dir / "Private/InfinityStageEffectSource.cpp").read_text(encoding="utf-8")
pas_cpp = (src_dir / "Private/InfinityStagePassageActor.cpp").read_text(encoding="utf-8")
types_h = (src_dir / "Public/InfinityStageTypes.h").read_text(encoding="utf-8")
sig = re.search(r"static FGuid AddEffectAttachment\(([^)]*)\)", lib_h)
check("contract: AddEffectAttachment(Show, CueGuid, Type, Anchor, RelativeTransform, Label)", sig is not None and
      [w.split()[-1].lstrip("*") for w in sig.group(1).split(",")] ==
      ["Show", "CueGuid", "Type", "Anchor", "RelativeTransform", "Label"])
check("contract: Smoke default class path == SMOKE_BP",
      'Smoke:\n        return TEXT("%s.BP_Effect_SmokePot_C")' % F.SMOKE_BP in eff_cpp.replace("\r\n", "\n"))
check("contract -control: Haze path is not the smoke BP", 'TEXT("%s.BP_Effect_HazePot_C")' % F.SMOKE_BP not in eff_cpp)
check("contract: empty Effect class -> ResolveDefaultClass", "!SpawnClass && Attachment.Kind == EInfinityAttachmentKind::Effect"
      in pas_cpp and "ResolveDefaultClass(Attachment.Effect)" in pas_cpp)
check("contract: identity tag prefix", 'TEXT("InfinityStage.Attachment.%s|%s")' in pas_cpp
      and F.TAG_PREFIX == "InfinityStage.Attachment.")
check("contract: Station anchor exists", re.search(r"enum class EInfinityAttachmentAnchor[^}]*\bStation,", types_h, re.S))
check("contract: all FX systems gated by distance", "TInlineComponentArray<UFXSystemComponent*>" in eff_cpp)
engine_psc = pathlib.Path("D:/Unreal Engine/UE_5.8/Engine/Source/Runtime/Engine/Classes/Particles/ParticleSystemComponent.h")
if engine_psc.is_file():
    check("contract: Cascade PSC is a UFXSystemComponent (UE 5.8 header)",
          "class UParticleSystemComponent : public UFXSystemComponent" in engine_psc.read_text(encoding="utf-8", errors="replace"))
dll = ROOT / "Plugins/InfinityStage/Binaries/Win64/UnrealEditor-InfinityStage.dll"
if dll.is_file():
    blob = dll.read_bytes()
    check("binary: AddEffectAttachment in the installed DLL", b"AddEffectAttachment" in blob)
    check("binary -control: a made-up name is not", b"AddSmokePotAttachment" not in blob)
rec = json.loads((HERE / "fx_effect_bps_record.json").read_text(encoding="utf-8"))
check("measured: BP_Effect_SmokePot was created with PlumeFX = the expected template",
      rec["readback"].get(F.SMOKE_BP, {}).get("template") == F.DEFAULT_TEMPLATE
      and F.SMOKE_BP in rec["created"])

# ---------------------------------------------------------------- source guards
src = (HERE / "fx_smoke_place.py").read_text(encoding="utf-8")
tree = ast.parse(src)
calls = {n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
         for n in ast.walk(tree) if isinstance(n, ast.Call)}
check("guard: no Save All / dirty-package save", not ({"save_dirty_packages", "save_packages", "save_all"} & calls)
      and "save_dirty" not in src)
check("guard: no asset delete, no level load", not ({"delete_asset", "load_level", "load_map"} & calls))
check("guard: no PIE start/stop", "request_end_play" not in src and "request_begin_play" not in src)
check("guard -control: the scan sees the narrow save", "save_show_and_level" in calls)
body = src[src.index("def main():"):]
order = [body.index(t) for t in ('"PreFxSmoke-"', "C.write_json(RECORD, record, exclusive=True)", "_add_one(show",
                                 "_materialize(show, {r[\"passage\"] for r in rows})", "C.save_show_and_level(unreal)\n        phase",
                                 'queue_saved_master_test(unreal, world, "FXSMOKE"')]
check("guard: backup -> record -> add -> materialize -> save -> saved-master test", order == sorted(order))
check("guard: census asserted before each save", body.count("APPLY_DIRTY_SCOPE") == 1 and body.count("REVERT_DIRTY_SCOPE") == 1)
module_level_unreal = [n for n in tree.body if isinstance(n, ast.Assign) and "unreal." in ast.unparse(n.value)]
check("guard: no Unreal object in a module global (crash memory)", not module_level_unreal)
check("guard: DRY asserts the census unchanged", "DRY_CHANGED_CENSUS" in body)

failed = [n for n, ok in RESULTS if not ok]
print("\n%d/%d passed" % (len(RESULTS) - len(failed), len(RESULTS)))
sys.exit(1 if failed else 0)
