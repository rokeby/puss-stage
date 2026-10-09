"""Offline harness for P01 FLOOR (p01_floor_common.py + the p01_floor.py orchestrator on a FAKE editor backend).
Every positive check has a control that must FAIL the same predicate, so a check that cannot fail is caught.

  python test_p01_floor.py   -> PASS/FAIL lines, P01FLOOR_HARNESS_OK|passed=N|failed=0 (exit 0) or exit 1;
                                writes harness_result.json
Rows are the real P01 snapshot (meshy_swap_record_P01 after_rows + note-lamp flash fields) with the offline panel
spans (COUNT inputs). The fake backend keeps an in-memory Show and an on-disk copy, materializes lanterns / lines /
actors from the rows with the same formulas, and can inject faults (an extra row written, a setter that changes
intensity, an actor spawned 3 cm up, a drifted row). Nothing here imports unreal.
"""
import copy
import json
import math
import os
import runpy
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
P = runpy.run_path(os.path.join(HERE, "p01_floor.py"), run_name="_p01floor_test")["run"].__globals__  # live module dict
P["_load_all"]()
F, FF, MS = P["F"], P["FF"], P["MS"]
RESULTS = []
SHOW = "/Game/Fake/Show"
WORLD = "/Game/Fake/World"


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), str(detail)[:400]))


def raises(fn, needle):
    try:
        fn()
    except Exception as error:  # noqa: BLE001
        return needle in str(error)
    return False


def args_for(mode, **kw):
    raw = {"mode": mode}
    raw.update(kw)
    return P["check_args"](raw)


# ---------------------------------------------------------------------------------------------------------------- data
OFF = P["OfflineBackend"]()
BASE = OFF.read_state(args_for("COUNT"))
BEFORE_ALL = {c["guid"]: c["attachments"] for c in BASE["all_cues"]}
PLAN = P["build_plan"](BASE, args_for("COUNT"))                                   # default: STRUCTURE_CAN
LAMP = P["build_plan"](BASE, args_for("COUNT", uplight_body="LAMP_ON_FLOOR"))     # the earlier domestic-lamp option
ROWS = {r["guid"]: r for rs in BEFORE_ALL.values() for r in rs}


def changes(plan, what=None):
    return [(t, c) for t in plan["targets"] for c in t["changes"] if what is None or c["what"] == what]


def mutate(plan, what, fn, index=0):
    p = copy.deepcopy(plan)
    t, c = changes(p, what)[index]
    fn(c, t, p)
    return p


def codes(plan):
    return {b[0] for b in F.plan_checks(plan, BEFORE_ALL)}


# ---------------------------------------------------------------- A: the plan (pure)
cnt = PLAN["counts"]
check("A1 counts: 47 dead bulbs (+47 lights off), 40 uplights (28 CLAMP + 12 PRACTICAL_L), 7 glimmers and 1 working "
      "bulb LEFT, 174 rows, nothing refused",
      cnt["dead_bulbs"] == 47 and cnt["by_kind"].get("DEAD_LIGHT_DISABLED") == 47 and cnt["uplights"] == 40
      and sum(1 for u in PLAN["uplights"] if u["role"] == "PRACTICAL_CLAMP") == 28
      and sum(1 for u in PLAN["uplights"] if u["role"] == "PRACTICAL_L") == 12
      and cnt["glimmers_left"] == 7 and cnt["working_left"] == 1 and cnt["rows"] == 174 and cnt["refused"] == 0, cnt)
check("A1 the clean plan passes every check", not PLAN["checks"], PLAN["checks"][:3])
check("A1- control: dead_lumens_max 400 would also take the 300 lm B04 bulb (it is LEFT only by the threshold)",
      P["build_plan"](BASE, args_for("COUNT", dead_lumens_max=400.0))["counts"]["dead_bulbs"] == 48)

# A2 floor contact
worst = 0.0
for t, c in changes(PLAN) + changes(LAMP, "UPLIGHT_BODY_TO_FLOOR"):
    if c["what"] in ("DEAD_LIGHT_DISABLED", "UPLIGHT_BODY_HIDDEN"):
        continue
    ctx = PLAN["ctx"][t["cue_guid"]]
    if c["what"] == "DEAD_BULB_TO_FLOOR":
        geo = F.bulb_geometry(c["after"]["relative_transform"], c["meta"])
    elif c["what"] == "UPLIGHT_BODY_TO_FLOOR":
        geo = F.box_geometry(c["after"]["relative_transform"], c["meta"])
    else:
        geo = F.lantern_geometry(c["after"]["relative_transform"], ctx["pair_world"], ctx["across_world"], PLAN["lantern"])
    worst = max(worst, abs(geo["support_z"] - c["meta"]["floor_z"]))
check("A2 every moved support (bulb cap rim, lamp body bottom face, lantern bounds) is on its floor within 1 cm "
      "(worst %.2e cm)" % worst, worst <= 1.0, worst)
floating = mutate(LAMP, "UPLIGHT_BODY_TO_FLOOR", lambda c, t, p: c["after"]["relative_transform"]["location"].__setitem__(2, c["after"]["relative_transform"]["location"][2] + 5.0))
check("A2- control: a lamp body left 5 cm up is caught (FLOATING)",
      "FLOATING" in {b[0] for b in F.plan_checks(floating, BEFORE_ALL)})
floating_bulb = mutate(PLAN, "DEAD_BULB_TO_FLOOR", lambda c, t, p: c["after"]["relative_transform"].__setitem__("location", copy.deepcopy(ROWS[c["guid"]]["relative_transform"]["location"])), 3)
check("A2- control: a dead bulb left at its old height is caught (FLOATING)", "FLOATING" in codes(floating_bulb))
sunk = mutate(PLAN, "UPLIGHT_LIGHT_TO_FLOOR", lambda c, t, p: c["after"]["relative_transform"]["location"].__setitem__(2, c["after"]["relative_transform"]["location"][2] - 4.0))
check("A2- control: a lantern pushed 4 cm into the floor is caught (SUNK_IN_FLOOR)", "SUNK_IN_FLOOR" in codes(sunk))

# A3 uplight pitch / aim
pitches = []
for t, c in changes(PLAN, "UPLIGHT_LIGHT_TO_FLOOR"):
    ctx = PLAN["ctx"][t["cue_guid"]]
    geo = F.lantern_geometry(c["after"]["relative_transform"], ctx["pair_world"], ctx["across_world"], PLAN["lantern"])
    pitches.append((geo["pitch_deg"], geo["throw_pair"][0]))
check("A3 all 40 uplights pitched 70-80 deg up toward the wing (+x): %.2f..%.2f deg"
      % (min(p for p, _ in pitches), max(p for p, _ in pitches)),
      len(pitches) == 40 and all(70.0 - 1e-6 <= p <= 80.0 + 1e-6 and x > 0 for p, x in pitches))


def repitch(c, t, p, deg=60.0):
    th = [math.cos(math.radians(deg)), 0.0, math.sin(math.radians(deg))]
    c["after"]["relative_transform"]["rotation_xyzw"] = F.canon_q(F.M.make_from_xz(th, [0.0, 0.0, 1.0]))


check("A3- control: a 60 deg uplight is caught (PITCH_OUT_OF_RANGE)", "PITCH_OUT_OF_RANGE" in codes(mutate(PLAN, "UPLIGHT_LIGHT_TO_FLOOR", repitch)))
check("A3- control: an uplight aimed away from the wing is caught (AIM_NOT_TOWARD_WING)",
      "AIM_NOT_TOWARD_WING" in codes(mutate(PLAN, "UPLIGHT_LIGHT_TO_FLOOR", lambda c, t, p: repitch(c, t, p, 105.0))))

# A4 intensity / colour unchanged
same = all(not F.M.row_differences({k: ROWS[c["guid"]]["lighting"][k] for k in ("intensity", "intensity_units", "color", "temperature_kelvin")},
                                   {k: c["after"]["lighting"][k] for k in ("intensity", "intensity_units", "color", "temperature_kelvin")})
           for t, c in changes(PLAN, "UPLIGHT_LIGHT_TO_FLOOR"))
check("A4 every uplight keeps intensity, units, colour, temperature", same and len(changes(PLAN, "UPLIGHT_LIGHT_TO_FLOOR")) == 40)
brighter = mutate(PLAN, "UPLIGHT_LIGHT_TO_FLOOR", lambda c, t, p: c["after"]["lighting"].__setitem__("intensity", c["after"]["lighting"]["intensity"] * 1.5))
check("A4- control: an intensity change is caught (LIGHT_SETTING_CHANGED + FIELD_OUT_OF_SCOPE)",
      {"LIGHT_SETTING_CHANGED", "FIELD_OUT_OF_SCOPE"} <= codes(brighter))
recol = mutate(PLAN, "UPLIGHT_LIGHT_TO_FLOOR", lambda c, t, p: c["after"]["lighting"].__setitem__("color", [0.2, 0.2, 1.0, 1.0]))
check("A4- control: a colour change is caught", "LIGHT_SETTING_CHANGED" in codes(recol))
check("A4b every uplight becomes a SPOT (a point light cannot be aimed); KEEP_POINT keeps the type",
      all(F.enum_name(c["after"]["lighting"]["type"]) == "SPOT" for t, c in changes(PLAN, "UPLIGHT_LIGHT_TO_FLOOR"))
      and all(F.enum_name(c["after"]["lighting"]["type"]) == "POINT"
              for t, c in changes(P["build_plan"](BASE, args_for("COUNT", uplight_type="KEEP_POINT")), "UPLIGHT_LIGHT_TO_FLOOR")))

# A5 dead lights disabled / lanterns
dead_ok = all(c["after"]["enabled"] is False and F.light_lumens(ROWS[c["guid"]]) == 0.0
              for t, c in changes(PLAN, "DEAD_LIGHT_DISABLED"))
check("A5 the 47 dead (0 lm) lights are disabled -> lanterns %d -> %d (predicted, 47 removed)"
      % (PLAN["predicted"]["lanterns_before_offline_count"], PLAN["predicted"]["lanterns_after_offline_count"]),
      dead_ok and PLAN["predicted"]["lanterns_before_offline_count"] == 284
      and PLAN["predicted"]["lanterns_after_offline_count"] == 237 and PLAN["predicted"]["housings_removed"] == 47)
check("A5- control: a dead light left enabled is caught",
      "DEAD_LIGHT_STILL_ENABLED" in codes(mutate(PLAN, "DEAD_LIGHT_DISABLED", lambda c, t, p: c["after"].__setitem__("enabled", True))))

# A6 glimmers untouched
glim = set()
for r in ROWS.values():
    if F.role_of_label(r["label"]).startswith("PRACTICAL_GLIMMER"):
        glim.add(r["guid"])
planned = {c["guid"] for t, c in changes(PLAN)}
after_all = F.expected_after(BEFORE_ALL, PLAN)
after_rows = {r["guid"]: r for rs in after_all.values() for r in rs}
doc_pairs = {"07C6C4424357A9334CDFE89FE9705D69", "5840444948F3C807A6FD6CB7516B2DA9", "A1D1D15D4FE4ADEE49A71191DAA38186",
             "A58CCA914DBF34233156BBAA90E5E65D", "004FA2164F0E970C46A12FB3F3D4B71D", "5CF2373946B9F1585CA8A7801664B103",
             "018DFE69422093E054846DAAA6F21FD2", "B584D98349AC5E222577678134845257", "EA1ABA8046A3C41FB5806490FC35B9B8",
             "84EFD359454695A0B54E36A3ACA13F15", "BB51E8BF4924A92DB6281B81CDB3868D", "9A56F2AE46B0A51F957402A20AE5E4A7",
             "AF0A1D63449177E73B7A9982AA5B9E9C", "72CDB22C4ECFCDE3B8FC258A27DB5456"}
check("A6 the 7 glimmer pairs (14 rows, = FIXTURES_FOLLOW doc D2's P01 list) are not planned and stay identical",
      glim == doc_pairs and not (glim & planned)
      and all(not F.M.row_differences(ROWS[g], after_rows[g]) for g in glim), sorted(glim ^ doc_pairs)[:4])


gl_plan = copy.deepcopy(PLAN)
gl_light = next(r for r in ROWS.values() if r["guid"] in glim and F.is_kind(r, "LIGHT"))
gl_cue = next(g for g, rs in BEFORE_ALL.items() if any(r["guid"] == gl_light["guid"] for r in rs))
gl_t = next(t for t in gl_plan["targets"] if t["cue_guid"] == gl_cue)
gl_t["changes"].append({"guid": gl_light["guid"], "label": gl_light["label"], "what": "DEAD_LIGHT_DISABLED",
                        "after": dict(copy.deepcopy(gl_light), enabled=False), "meta": {"geom": None}})
check("A6- control: a plan that touches a glimmer row is caught (GLIMMER_TOUCHED)", "GLIMMER_TOUCHED" in codes(gl_plan))
check("A6b B04's 300 lm working bulb is LEFT and its rows are not planned",
      [x["cue"] for x in PLAN["left"] if x["why"].startswith("WORKING")] == ["P01 Wing 004"]
      and not ({x["body_guid"] for x in PLAN["left"] if x["why"].startswith("WORKING")} & planned))

# A7 inside the wing / lane / overlap
into_wing = mutate(LAMP, "UPLIGHT_BODY_TO_FLOOR", lambda c, t, p: c["after"]["relative_transform"]["location"].__setitem__(0, 0.0))
check("A7 no moved object's bounds come within 5 cm of its wing panel (clean plan)", "INSIDE_WING_PANEL" not in codes(PLAN))
check("A7- control: a lamp body placed inside its wing panel is caught (INSIDE_WING_PANEL)", "INSIDE_WING_PANEL" in codes(into_wing))
bulb_in = mutate(PLAN, "DEAD_BULB_TO_FLOOR", lambda c, t, p: c["after"]["relative_transform"]["location"].__setitem__(0, -8.0), 5)
check("A7- control: a dead bulb placed in the wing's thickness is caught", "INSIDE_WING_PANEL" in codes(bulb_in))
lane = mutate(PLAN, "DEAD_BULB_TO_FLOOR", lambda c, t, p: c["after"]["relative_transform"]["location"].__setitem__(1, 60.0))
check("A7- control: a bulb in the camera lane is caught (IN_CAMERA_LANE)", "IN_CAMERA_LANE" in codes(lane))


def body_on_light(c, t, p):
    light = next(x for x in t["changes"] if x["what"] == "UPLIGHT_LIGHT_TO_FLOOR")
    loc = c["after"]["relative_transform"]["location"]
    loc[0], loc[1] = light["after"]["relative_transform"]["location"][0], light["after"]["relative_transform"]["location"][1]


check("A7- control: a lamp body dropped onto its own lantern is caught (MOVED_OBJECTS_OVERLAP)",
      "MOVED_OBJECTS_OVERLAP" in codes(mutate(LAMP, "UPLIGHT_BODY_TO_FLOOR", body_on_light)))

# A8 determinism
check("A8 deterministic: the same inputs give the same plan sha",
      F.plan_sha(PLAN) == F.plan_sha(P["build_plan"](BASE, args_for("COUNT"))))
check("A8- control: another seed gives another plan", F.plan_sha(PLAN) != F.plan_sha(P["build_plan"](BASE, args_for("COUNT", seed="x"))))

# A9 bulbs stand on their caps, tilt <= 10
tilts = [F.bulb_geometry(c["after"]["relative_transform"], c["meta"])["tilt_deg"] for t, c in changes(PLAN, "DEAD_BULB_TO_FLOOR")]
check("A9 every dead bulb stands glass-up, tilted <= 10 deg (max %.2f)" % max(tilts), len(tilts) == 47 and max(tilts) <= 10.0 + 1e-6)
tilted = mutate(PLAN, "DEAD_BULB_TO_FLOOR", lambda c, t, p: c["after"]["relative_transform"].__setitem__(
    "rotation_xyzw", F.canon_q(F.FC.quat_mul(F.FC.quat_axis_angle([1, 0, 0], 25.0), c["after"]["relative_transform"]["rotation_xyzw"]))))
check("A9- control: a 25 deg extra tilt is caught", "BULB_TILT_OUT_OF_RANGE" in codes(tilted))

# A10 flash timing (InfinityStageLightDrama.cpp:62-80: D = camera - (wing + x) - offset)
flashes = [(t, c) for t, c in changes(PLAN, "UPLIGHT_LIGHT_TO_FLOOR") if c["meta"]["flash_lamp"]]
moved = [(t, c) for t, c in flashes if abs(c["meta"]["dx_cm"]) > 1e-9]
inv = 0.0
for t, c in moved:
    b = ROWS[c["guid"]]
    for o0, o1 in zip(b["lighting"]["drama"]["flash_camera_offsets_cm"], c["after"]["lighting"]["drama"]["flash_camera_offsets_cm"]):
        inv = max(inv, abs((b["relative_transform"]["location"][0] + o0) - (c["after"]["relative_transform"]["location"][0] + o1)))
check("A10 11 flash lamps among the uplights; the %d that move along x keep every flash at the same camera distance "
      "(x + offset invariant, worst %.4f cm)" % (len(moved), inv), len(flashes) == 11 and len(moved) == 5 and inv < 0.01)
nocomp = P["build_plan"](BASE, args_for("COUNT", flash_timing="NONE"))
shift = max(abs(c["meta"]["dx_cm"]) for t, c in changes(nocomp, "UPLIGHT_LIGHT_TO_FLOOR") if c["meta"]["flash_lamp"])
check("A10- control: flash_timing NONE leaves the offsets, so a flash moves by up to %.1f cm (%.2f s at 250 cm/s)"
      % (shift, shift / 250.0), shift > 20.0 and not any(c["meta"]["flash_compensated"] for t, c in changes(nocomp, "UPLIGHT_LIGHT_TO_FLOOR")))

# A11 Station anchor kept (drama + movers gate, InfinityStagePassageActor.cpp:1864-1866, :1916-1917)
check("A11 every moved light stays STATION-anchored (Light Drama and Movers still run)",
      all(F.enum_name(c["after"]["anchor"]) == "STATION" for t, c in changes(PLAN) if F.is_kind(c["after"], "LIGHT")))
check("A11- control: re-anchoring an uplight to a panel is caught (FIELD_OUT_OF_SCOPE)",
      "FIELD_OUT_OF_SCOPE" in codes(mutate(PLAN, "UPLIGHT_LIGHT_TO_FLOOR",
                                           lambda c, t, p: c["after"].__setitem__("anchor", "<InfinityAttachmentAnchor.LEFT_PANEL: 1>"))))

# A12 hanging lines
check("A12 no lantern gains a hanging line (drop > MaxDropCm 900 on the floor)", PLAN["predicted"]["hanging_line_delta"] == 0)
hung = mutate(PLAN, "UPLIGHT_LIGHT_TO_FLOOR", lambda c, t, p: c["after"]["relative_transform"]["location"].__setitem__(2, 700.0))
check("A12- control: a lantern lifted to 7 m would get a line (NEW_HANGING_LINE)", "NEW_HANGING_LINE" in codes(hung))

# A13 cans report (C): report only
cc = PLAN["cans_counts"]
check("A13 (C) 108 LOW_SIDE/BEAM cans listed (80 LOW_SIDE + 28 BEAM_R; 84 at |y| > 1130 cm, as the F1 report), none planned",
      cc["total"] == 108 and cc["by_role"] == {"BEAM_R": 28, "LOW_SIDE_L_KEY": 40, "LOW_SIDE_R_FILL": 40}
      and cc["abs_y_gt_1130"] == 84 and not ({c["light_guid"] for c in PLAN["cans_report"]} & planned))

# A14 scope helper: only the allowed fields differ on planned rows; every other row identical
fields = {c["what"]: set() for t, c in changes(PLAN)}
for t, c in changes(PLAN):
    fields[c["what"]] |= set(P["fields_for"](c, ROWS[c["guid"]]))
probs = F.scope_problems(BEFORE_ALL, after_all)
check("A14 fields written: dead light {enabled}; bulbs {relative_transform}; domestic bodies {enabled}; uplights {relative_transform, lighting.type, "
      "lighting.drama.flash_camera_offsets_cm}; 174 rows differ, no other row",
      fields == {"DEAD_LIGHT_DISABLED": {"enabled"}, "DEAD_BULB_TO_FLOOR": {"relative_transform"},
                 "UPLIGHT_BODY_HIDDEN": {"enabled"},
                 "UPLIGHT_LIGHT_TO_FLOOR": {"relative_transform", "lighting.type", "lighting.drama.flash_camera_offsets_cm"}}
      and len(probs) == 174 and {p["guid"] for p in probs} == planned, fields)


# ---------------------------------------------------------------- D: theatre lanterns, not domestic lamps (Gary 8 Oct, 2nd)
hidden = changes(PLAN, "UPLIGHT_BODY_HIDDEN")
check("D1 STRUCTURE_CAN (default): the 40 domestic SM_Lamp_* bodies are disabled, none moved; every uplight's floor "
      "lantern is the Structure's %s with its front (+X) on the light's throw" % PLAN["lantern"]["name"],
      len(hidden) == 40 and all(c["after"]["enabled"] is False and F.mesh_name(ROWS[c["guid"]]["mesh"]) in ("SM_Lamp_Wall", "SM_Lamp_Ceiling")
                                for t, c in hidden)
      and all(u["meta"]["lantern"]["mesh"] == "SM_Lantern_Fresnel" and u["meta"]["lantern"]["throw_pair"][2] > 0.9
              and "lens_pair" in u["meta"]["lantern"] for u in PLAN["uplights"]))
lens_ok = all(u["meta"]["lantern"]["lens_pair"][2] > u["light_after"]["location"][2] - 10.0 for u in PLAN["uplights"])
check("D1 the lens sits at the light (within the lantern's lens offset), facing up into the wing", lens_ok)
check("D1- control: a domestic body left visible is caught (DOMESTIC_BODY_STILL_VISIBLE)",
      "DOMESTIC_BODY_STILL_VISIBLE" in codes(mutate(PLAN, "UPLIGHT_BODY_HIDDEN", lambda c, t, p: c["after"].__setitem__("enabled", True))))
n_lan = PLAN["predicted"]["lanterns_after_offline_count"]
per_light = {}
after_cues = [dict(c, attachments=after_all[c["guid"]]) for c in BASE["cues"]]
for pl in F.housings(after_cues, BASE["ctx_by_cue"]):
    per_light[pl["guid"]] = per_light.get(pl["guid"], 0) + 1
up_guids = {c["guid"] for t, c in changes(PLAN, "UPLIGHT_LIGHT_TO_FLOOR")}
extra_meshes = [r for rs in after_all.values() for r in rs if r["enabled"] and F.is_kind(r, "PROP")
                and (F.mesh_name(r.get("mesh")) or "").startswith("SM_Lantern_")]
check("D2 no double housing: each uplight has exactly ONE lantern (the Structure's), no lantern PROP body exists, "
      "lanterns %d (= 284 - 47 dead)" % n_lan,
      all(per_light.get(g) == 1 for g in up_guids) and not extra_meshes and n_lan == 237)
check("D2- control: BIRDIE_BODY is refused with the source reason (no per-attachment housing opt-out)",
      raises(lambda: args_for("COUNT", uplight_body="BIRDIE_BODY"), "BIRDIE_BODY_NEEDS_CPP"))
check("D3 LAMP_ON_FLOOR (alternative) still plans the domestic lamp beside its lantern, all checks clean",
      not F.plan_checks(LAMP, BEFORE_ALL) and len(changes(LAMP, "UPLIGHT_BODY_TO_FLOOR")) == 40)

ADD = P["build_add_plan"](BASE, args_for("COUNT", op="ADD_UPLIGHTS"))
add_geo = []
for t, c in changes(ADD, "ADD_UPLIGHT"):
    ctx = ADD["ctx"][t["cue_guid"]]
    add_geo.append(F.lantern_geometry(c["after"]["relative_transform"], ctx["pair_world"], ctx["across_world"], ADD["lantern"]))
check("E1 ADD_UPLIGHTS P01 proposes 96 (48 bays x 2 sides): every lantern on the floor, 70-80 deg into the wing face, "
      "out of the panel and the lane, all checks clean",
      ADD["counts"]["proposed_uplights"] == 96 and not ADD["checks"]
      and all(abs(g["support_z"] - c["meta"]["floor_z"]) <= 1.0 and 70 - 1e-6 <= g["pitch_deg"] <= 80 + 1e-6
              for g, (t, c) in zip(add_geo, changes(ADD, "ADD_UPLIGHT"))))
bad_add = copy.deepcopy(ADD)
changes(bad_add, "ADD_UPLIGHT")[0][1]["after"]["relative_transform"]["location"][0] = 0.0
check("E1- control: a proposed uplight moved into its wing panel is caught", any(b[0] == "INSIDE_WING_PANEL" for b in F.add_plan_checks(bad_add)))
check("E2- control: ADD_UPLIGHTS cannot APPLY (proposal only)",
      raises(lambda: args_for("APPLY", op="ADD_UPLIGHTS", confirm="APPLY P01FLOOR", plan_sha256="0" * 64), "ADD_UPLIGHTS_IS_PROPOSAL_ONLY"))
st5 = P["OfflineBackend"]().read_state(args_for("COUNT", op="ADD_UPLIGHTS", passage="P05"))
add5 = P["build_add_plan"](st5, args_for("COUNT", op="ADD_UPLIGHTS", passage="P05"))
add5b = P["build_add_plan"](st5, args_for("COUNT", op="ADD_UPLIGHTS", passage="P05", add_skip_sides_with_uplights=False))
check("E3 a passage that already has floor uplights (P05) skips those sides (%d skipped, %d proposed), checks clean"
      % (add5["counts"]["sides_skipped"], add5["counts"]["proposed_uplights"]),
      add5["counts"]["sides_skipped"] > 0 and not add5["checks"])
check("E3- control: with skipping off it proposes more", add5b["counts"]["proposed_uplights"] > add5["counts"]["proposed_uplights"])


# ---------------------------------------------------------------- B: the orchestrator on a fake editor
class FakeBackend:
    def __init__(self, state, faults=(), foreign=None, mechanisms=None):
        self.base = state
        self.mem = copy.deepcopy({c["guid"]: c["attachments"] for c in state["all_cues"]})
        self.disk = copy.deepcopy(self.mem)
        self.faults = set(faults)
        self.foreign_hits = foreign or []
        self.mechanisms = mechanisms or {}
        self.logs = []
        self.n = 0
        self.mat = None
        self.materialize()
        self.disk_mat = copy.deepcopy(self.mat)
        self.map_dirty = False

    def now(self):
        self.n += 1
        return "FAKE-%03d" % self.n

    def log(self, text):
        self.logs.append(text)

    def log_error(self, text):
        self.logs.append(text)

    def census(self):
        dirty = F.canonical(self.mem) != F.canonical(self.disk)
        return {"content": [SHOW] if dirty else [], "maps": [WORLD] if (dirty or self.map_dirty) else []}

    def context(self):
        return {"project_ok": True, "world_ok": True, "pie": False, "sequencer_open": False, "census": self.census(),
                "zz_actors": []}

    def check_context(self, ctx, mode, allow_dirty):
        MS.check_context(ctx, mode, allow_dirty, SHOW, WORLD)

    def _cues(self):
        return [dict(c, attachments=copy.deepcopy(self.mem[c["guid"]])) for c in self.base["cues"]]

    def read_state(self, args):
        st = dict(self.base)
        cues = self._cues()
        st["all_cues"] = cues
        st["cues"] = cues
        st["structure"] = {"fixture_body_count": self.mat["lanterns"], "hanging_line_count": self.mat["lines"],
                           "current": True}
        st["mechanisms"] = self.mechanisms
        return st

    def rows_now(self):
        return copy.deepcopy(self.mem)

    def readback_rows(self):
        return copy.deepcopy(self.disk)

    def export_hash(self, skip, readback=False):
        src = self.disk if readback else self.mem
        return F.sha({g: r for g, r in src.items() if g not in set(skip)})

    def foreign(self, guids, exclude):
        return list(self.foreign_hits)

    def backup(self, prefix, run_id):
        return {"root": "FAKE/Backups/%s%s" % (prefix, run_id)}

    def write_rows(self, target, values):
        rows = self.mem[target["cue_guid"]]
        original = copy.deepcopy(rows)
        seen = 0
        for r in rows:
            if r["guid"] not in values:
                continue
            src, fields = values[r["guid"]]
            seen += 1
            for f in fields:
                F.set_path(r, f, copy.deepcopy(F.get_path(src, f)))
            if "intensity_lie" in self.faults and F.is_kind(r, "LIGHT") and "lighting.type" in fields:
                r["lighting"]["intensity"] = r["lighting"]["intensity"] * 1.1
        if "extra_row_change" in self.faults:
            victim = next(r for r in rows if r["guid"] not in values and F.is_kind(r, "LIGHT"))
            victim["enabled"] = not victim["enabled"]
        require_ = F.require
        require_(seen == len(values), "ROW_GUIDS_MISSING")
        return (target["cue_guid"], original)

    def rollback(self, tokens):
        for g, original in reversed(tokens):
            self.mem[g] = original

    def materialize(self):
        cues = self._cues()
        ctx = self.base["ctx_by_cue"]
        pl = F.housings(cues, ctx)
        lines = 0
        for c in cues:
            for r in c["attachments"]:
                if F.is_kind(r, "LIGHT") and r["enabled"] and F.is_station(r):
                    lines += int(F.line_after(r["relative_transform"], True, ctx[c["guid"]], self.base["lantern"], self.base["grid"]))
        actors = {}
        for c in cues:
            w = ctx[c["guid"]]["pair_world"]
            for r in c["attachments"]:
                if not r["enabled"]:
                    continue
                loc = F.xf_point(w, r["relative_transform"]["location"])
                if "spawn_float" in self.faults and r["label"].endswith("_BODY") and "PRACTICAL" in r["label"]:
                    loc = [loc[0], loc[1], loc[2] + 3.0]
                if F.is_kind(r, "LIGHT"):
                    cls = {"SPOT": "SpotLight", "POINT": "PointLight", "RECT": "RectLight"}[F.enum_name(r["lighting"]["type"])]
                    fwd = F.quat_rotate(F.xf_compose(r["relative_transform"], w)["rotation_xyzw"], [1.0, 0.0, 0.0])
                    actors["%s|%s" % (c["guid"], r["guid"])] = [{"loc": loc, "cls": cls, "fwd": fwd}]
                elif r.get("mesh"):
                    actors["%s|%s" % (c["guid"], r["guid"])] = [{"loc": loc, "cls": "StaticMeshActor", "mesh": F.asset_id(r["mesh"])}]
        self.mat = {"lanterns": len(pl), "lines": lines, "actors": actors}
        self.map_dirty = True
        return {"passage": "Passage 01 (fake)", "structure": "Infinity Stage - Structure 01 (fake)"}

    def structure_now(self):
        return {"fixture_body_count": self.mat["lanterns"], "hanging_line_count": self.mat["lines"], "current": True}

    def housing_check(self):
        n = len(F.housings(self._cues(), self.base["ctx_by_cue"]))
        return {"count": n, "ism_count": self.mat["lanterns"], "stale": 0, "count_matches": n == self.mat["lanterns"]}

    def verify_spawned(self, plan):
        bad, ok = [], 0
        for t in plan["targets"]:
            w = plan["ctx"][t["cue_guid"]]["pair_world"]
            for c in t["changes"]:
                acts = self.mat["actors"].get("%s|%s" % (t["cue_guid"], c["guid"]), [])
                if not c["after"]["enabled"]:
                    if acts:
                        bad.append((c["label"], "DISABLED_HAS_ACTOR"))
                    ok += not acts
                    continue
                if len(acts) != 1:
                    bad.append((c["label"], "COUNT"))
                    continue
                want = F.xf_point(w, c["after"]["relative_transform"]["location"])
                if F.FC.dist(want, acts[0]["loc"]) > P["PLACE_TOL_CM"]:
                    bad.append((c["label"], "PLACE"))
                    continue
                ok += 1
        F.require(not bad, "SPAWNED|%s" % bad[:4])
        return ok

    def save_narrow(self):
        c = self.census()
        F.require(set(c["content"]) <= {SHOW} and set(c["maps"]) <= {WORLD}, "OUT_OF_SCOPE_DIRTY")
        self.disk = copy.deepcopy(self.mem)
        self.disk_mat = copy.deepcopy(self.mat)
        self.map_dirty = False


def run_fake(be, tmp, mode, **kw):
    a = args_for(mode, **kw)
    return P["run"](a, be, out_dir=tmp, relocate_record=os.path.join(tmp, "fixfollow_relocate_record_P01.json"))


ORIGINAL = F.canonical({c["guid"]: c["attachments"] for c in BASE["all_cues"]})
with tempfile.TemporaryDirectory() as tmp:
    be = FakeBackend(BASE)
    dry = run_fake(be, tmp, "DRY")
    sha = dry["plan_sha256"]
    check("B1 DRY on the fake editor: OK marker, census and rows unchanged, same row changes as COUNT",
          dry["ok"] and any(l.startswith("P01FLOOR_DRY_OK") for l in be.logs) and F.canonical(be.disk) == ORIGINAL
          and be.census() == {"content": [], "maps": []} and F.canonical(dry["plan"]["targets"]) == F.canonical(PLAN["targets"]))
    check("B2- control: APPLY without the exact confirm is refused",
          raises(lambda: args_for("APPLY", plan_sha256=sha), "CONFIRM_MISSING"))
    check("B2- control: APPLY with a stale plan sha is refused, nothing written",
          raises(lambda: run_fake(be, tmp, "APPLY", confirm="APPLY P01FLOOR", plan_sha256="0" * 64), "PLAN_SHA_MISMATCH")
          and F.canonical(be.disk) == ORIGINAL and not os.path.exists(os.path.join(tmp, "p01_floor_record.json")))
    check("B2- control: a row-count pin that does not match is refused",
          raises(lambda: run_fake(be, tmp, "APPLY", confirm="APPLY P01FLOOR", plan_sha256=sha, expected_rows=173), "PIN_ROWS"))
    open(os.path.join(tmp, "fixfollow_relocate_record_P01.json"), "w").write("{}")
    check("B2- control: an active FixturesFollow RELOCATE record for P01 blocks the APPLY",
          raises(lambda: run_fake(be, tmp, "APPLY", confirm="APPLY P01FLOOR", plan_sha256=sha), "FIXFOLLOW_RELOCATE_ACTIVE"))
    os.remove(os.path.join(tmp, "fixfollow_relocate_record_P01.json"))
    be_f = FakeBackend(BASE, foreign=[{"path": "X/meshy_swap_record_P01.json"}])
    check("B2- control: an unacknowledged foreign record blocks the APPLY",
          raises(lambda: run_fake(be_f, tmp, "APPLY", confirm="APPLY P01FLOOR", plan_sha256=sha), "FOREIGN_ACTIVE_RECORDS_OVERLAP"))
    tgt = PLAN["targets"][0]["cue_guid"]
    be_m = FakeBackend(BASE, mechanisms={tgt: {"kind": "<InfinityMechanismKind.TOPPLE: 1>", "max_angle_deg": 90.0}})
    sha_m = run_fake(be_m, tmp, "DRY")["plan_sha256"]
    check("B2- control: a TOPPLE mechanism on a target cue blocks the APPLY unless accept_mechanism_risk",
          raises(lambda: run_fake(be_m, tmp, "APPLY", confirm="APPLY P01FLOOR", plan_sha256=sha_m), "MECHANISM_RISK"))

    # APPLY
    rep = run_fake(be, tmp, "APPLY", confirm="APPLY P01FLOOR", plan_sha256=sha, expected_rows=174)
    rpath = os.path.join(tmp, "p01_floor_record.json")
    rec = json.load(open(rpath, encoding="utf-8"))
    check("B3c APPLY record carries acked_overlap (Conductor 5's ack condition, 8 Oct)", isinstance(rec.get("acked_overlap"), dict))
    # positive: an ACKED foreign record that mentions two of our rows + one foreign row lists exactly our two
    _ours = sorted(planned)[:2]
    _tmp_a = tempfile.mkdtemp()
    be_a = FakeBackend(BASE, foreign=[{"path": "X/meshy_swap_record_P01.json", "guids": _ours + ["NOT_OURS_GUID"]}])
    run_fake(be_a, _tmp_a, "APPLY", confirm="APPLY P01FLOOR", plan_sha256=sha, expected_rows=174,
             ack_records=["X/meshy_swap_record_P01.json"])
    _rec_a = json.load(open(os.path.join(_tmp_a, "p01_floor_record.json"), encoding="utf-8"))
    _ov = (_rec_a.get("acked_overlap") or {}).get("X/meshy_swap_record_P01.json", {})
    check("B3d acked_overlap lists exactly the acked record's rows that WE changed (2), never its other rows",
          sorted(_ov.get("rows_we_changed", [])) == _ours, _ov)
    want = F.expected_after(json.loads(ORIGINAL), PLAN)
    disk_probs = F.scope_problems(json.loads(ORIGINAL), be.disk)
    check("B3 APPLY: record saved_readback_verified, saved rows == planned rows exactly, only the 174 planned rows "
          "differ, lanterns 284 -> 237, hanging lines unchanged (%s)" % be.disk_mat["lines"],
          rep["ok"] and rec["status"] == "saved_readback_verified" and not F.scope_problems(want, be.disk)
          and len(disk_probs) == 174 and {p["guid"] for p in disk_probs} == planned
          and be.disk_mat["lanterns"] == 237 and be.disk_mat["lines"] == FakeBackend(BASE).mat["lines"]
          and rec["backup"]["root"].endswith("PreP01Floor-" + rep["run"]))
    check("B3 the record was written BEFORE the first row write (record-first) and carries every target cue's before rows",
          any(l.startswith("P01FLOOR_RECORD_WRITTEN") for l in be.logs)
          and be.logs.index(next(l for l in be.logs if l.startswith("P01FLOOR_RECORD_WRITTEN")))
          < be.logs.index(next(l for l in be.logs if l.startswith("P01FLOOR_APPLY_OK")))
          and set(rec["before_rows"]) == {t["cue_guid"] for t in PLAN["targets"]})
    spot_ok = all(a["cls"] == "SpotLight" for t, c in changes(PLAN, "UPLIGHT_LIGHT_TO_FLOOR")
                  for a in be.disk_mat["actors"]["%s|%s" % (t["cue_guid"], c["guid"])])
    gone = all("%s|%s" % (t["cue_guid"], c["guid"]) not in be.disk_mat["actors"] for t, c in changes(PLAN, "DEAD_LIGHT_DISABLED"))
    check("B3 after materialize: 40 SpotLight uplight actors, no actor for the 47 disabled lights", spot_ok and gone)
    disk_after_apply = F.canonical(be.disk)
    post = run_fake(be, tmp, "DRY")
    check("B4 a DRY after the APPLY plans nothing (every row already in place: the plan is idempotent)",
          post["ok"] and post["plan"]["counts"]["rows"] == 0 and post["plan"]["counts"]["already_in_place"] == 127)
    check("B4- control: re-APPLY over the active record is refused (ACTIVE_RECORD_EXISTS) with the current sha too, "
          "and writes nothing",
          raises(lambda: run_fake(be, tmp, "APPLY", confirm="APPLY P01FLOOR", plan_sha256=post["plan_sha256"]),
                 "ACTIVE_RECORD_EXISTS")
          and raises(lambda: run_fake(be, tmp, "APPLY", confirm="APPLY P01FLOOR", plan_sha256=sha), "ACTIVE_RECORD_EXISTS")
          and F.canonical(be.disk) == disk_after_apply)

    # REVERT
    rv = run_fake(be, tmp, "REVERT", confirm="REVERT P01FLOOR")
    check("B5 REVERT: the saved Show is bit-identical to before the APPLY, lanterns back to 284, record archived",
          rv["ok"] and F.canonical(be.disk) == ORIGINAL and be.disk_mat["lanterns"] == 284
          and not os.path.exists(rpath) and any(n.startswith("p01_floor_record.json.reverted-") for n in os.listdir(tmp)))
    check("B5- control: a second REVERT has no record to revert", raises(lambda: run_fake(be, tmp, "REVERT", confirm="REVERT P01FLOOR"),
                                                                         "REVERT_RECORD_ABSENT"))

    # REVERT drift
    rep2 = run_fake(be, tmp, "APPLY", confirm="APPLY P01FLOOR", plan_sha256=sha)
    t0, c0 = changes(PLAN, "UPLIGHT_LIGHT_TO_FLOOR")[0]
    for store in (be.mem, be.disk):
        r = next(r for r in store[t0["cue_guid"]] if r["guid"] == c0["guid"])
        r["relative_transform"]["location"][2] += 12.0           # Gary nudged one lamp by hand after the APPLY
    drifted = F.canonical(be.disk)
    check("B6- control: REVERT over a drifted target row is refused (REVERT_DRIFT) and writes nothing",
          raises(lambda: run_fake(be, tmp, "REVERT", confirm="REVERT P01FLOOR"), "REVERT_DRIFT") and F.canonical(be.disk) == drifted)
    for store in (be.mem, be.disk):
        r = next(r for r in store[t0["cue_guid"]] if r["guid"] == c0["guid"])
        r["relative_transform"]["location"][2] -= 12.0
    check("B6 after the drift is undone the REVERT restores the original exactly",
          run_fake(be, tmp, "REVERT", confirm="REVERT P01FLOOR")["ok"] and F.canonical(be.disk) == ORIGINAL)

    # injected faults
    for fault, needle, title in (("extra_row_change", "SCOPE_CHANGED", "a light row OUTSIDE the plan changed by the write"),
                                 ("intensity_lie", "SCOPE_CHANGED", "a write that changes an uplight's intensity"),
                                 ("spawn_float", "SPAWNED", "a body actor left 3 cm up after materialize")):
        bf = FakeBackend(BASE, faults=[fault])
        sub = os.path.join(tmp, fault)
        os.makedirs(sub)
        ok = raises(lambda: run_fake(bf, sub, "APPLY", confirm="APPLY P01FLOOR", plan_sha256=sha), needle)
        check("B7- control: %s -> %s, rolled back in memory, NOTHING saved, record .failed" % (title, needle),
              ok and F.canonical(bf.disk) == ORIGINAL and F.canonical(bf.mem) == ORIGINAL
              and not os.path.exists(os.path.join(sub, "p01_floor_record.json"))
              and any(n.startswith("p01_floor_record.json.failed-") for n in os.listdir(sub))
              and any("NOTHING SAVED" in l for l in bf.logs))

# ---------------------------------------------------------------- C: loader + backend contract
src = open(P["FIXFOLLOW_PATH"], encoding="utf-8").read()
with tempfile.TemporaryDirectory() as tmp:
    bad = os.path.join(tmp, "fixtures_follow_bad.py")
    open(bad, "w", encoding="utf-8").write(src.replace("\ndef load_common():", "\nprint('side effect')\n\ndef load_common():", 1))
    check("C1 fixtures_follow.py loads without running main()/count_cli()", callable(FF._follow_state) and FF.F is F.FC)
    check("C1- control: a copy with an extra top-level call is refused",
          raises(lambda: P["load_without_guards"](bad, "_x", {"__name__ == '__main__' and unreal is None": "count_cli",
                                                               "unreal is not None": "main"}), "TOP_LEVEL_EXPR"))
live_methods = {n for n in dir(P["LiveBackend"]) if not n.startswith("_")}
fake_methods = {n for n in dir(FakeBackend) if not n.startswith("_")}
check("C2 the fake backend implements exactly the live backend's interface", live_methods == fake_methods,
      sorted(live_methods ^ fake_methods))
check("C3 offline COUNT can never write: any write call on the offline backend is refused",
      raises(lambda: OFF.write_rows(None, {}), "OFFLINE_BACKEND_HAS_NO_WRITE_ROWS"))

passed = sum(1 for r in RESULTS if r[1])
failed = [r for r in RESULTS if not r[1]]
for name, ok, detail in RESULTS:
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else "  :: " + detail))
with open(os.path.join(HERE, "harness_result.json"), "w", encoding="utf-8") as handle:
    json.dump({"passed": passed, "failed": [r[0] for r in failed], "checks": [{"name": r[0], "ok": r[1]} for r in RESULTS]},
              handle, indent=1)
if failed:
    print("P01FLOOR_HARNESS_FAILED|passed=%d|failed=%d" % (passed, len(failed)))
    sys.exit(1)
print("P01FLOOR_HARNESS_OK|passed=%d|failed=0" % passed)
