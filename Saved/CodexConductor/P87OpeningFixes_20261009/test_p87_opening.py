"""Offline +/- harness for P87.  No Unreal or Blender."""
from __future__ import annotations

import copy
import json
import os
import tempfile

import p87_opening_common as C
import p87_opening_fixes as T


PASS = 0
FAIL = 0


def check(name, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
    else:
        FAIL += 1
        print("FAIL|" + name)


def rejects(name, fn, text):
    try:
        fn()
    except Exception as error:  # deliberate negative control
        check(name, text in str(error))
    else:
        check(name, False)


def live_fixture():
    bulbs = []
    for i in range(8):
        bulbs.append({"id": "BULB-%02d" % i, "wing_location": [500.0 + i * 400.0, (-1) ** i * 720.0, 0.0],
                      "floor_z_cm": 0.0, "side_sign": (-1) ** i})
    return {
        "show_path": "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show",
        "level_path": "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice",
        "sequence_path": "/Game/InfinityStage/Interactions/LS_Opening_Curtain_Baked",
        "clock": {"status": "UNRESOLVED", "gary_note": "00:37:50", "opening_fps": 25.0,
                  "opening_frames": [0, 2409], "master_section": "LIVE_DRY_REQUIRED"},
        "camera_end_pose": {"location": [0.0, 0.0, 150.0], "rotation": [0.0, 0.0, 0.0],
                            "focal_mm": 25.0, "focus_cm": 600.0},
        "curtain_sections": [{"role": "HOLD", "start": 0, "end": 1900},
                             {"role": "FALL", "start": 1900, "end": 2150},
                             {"role": "FALL", "start": 2200, "end": 2400}],
        "bulbs": bulbs,
    }


class FakeBackend:
    def __init__(self, live=None):
        self.live = copy.deepcopy(live or live_fixture())
        self.state = {p.lower(): {"legacy": p} for p in C.PARTS}
        self.initial = copy.deepcopy(self.state)
        self.dirty = {"content": [], "maps": []}
        self.foreign = []
        self.saved = False
        self.logs = []
        self.backups = []

    def context(self):
        return {"pie": False, "sequencer_open": False,
                "world": "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice",
                "dirty": copy.deepcopy(self.dirty)}

    def snapshot(self, parts):
        return {"live": copy.deepcopy(self.live),
                "owned": {p.lower(): copy.deepcopy(self.state[p.lower()]) for p in parts},
                "packages": [self.live["show_path"], self.live["sequence_path"], self.live["level_path"]]}

    def foreign_records(self, parts):
        return copy.deepcopy(self.foreign)

    def previews(self, plan, run):
        return {"timeline": "offline-preview-%s.png" % run, "stage_front": "offline-front-%s.png" % run}

    def backup(self, label, packages):
        row = {"folder": "Backups/" + label, "packages": list(packages), "hash_verified": True}
        self.backups.append(row)
        return row

    def apply(self, plan):
        self.state = C.apply_model(self.state, plan)
        self.dirty = {"content": [self.live["show_path"], self.live["sequence_path"]],
                      "maps": [self.live["level_path"]]}

    def owned_state(self, parts):
        return {p.lower(): copy.deepcopy(self.state[p.lower()]) for p in parts}

    def restore(self, state):
        for key, value in state.items():
            self.state[key] = copy.deepcopy(value)
        self.dirty = {"content": [self.live["show_path"], self.live["sequence_path"]],
                      "maps": [self.live["level_path"]]}

    def assert_plan(self, after, plan):
        for p in plan["parts"]:
            if after[p.lower()] != plan[p.lower()]:
                raise C.P87Error("PLAN_READBACK|" + p)

    def save_named(self, packages):
        if packages != [self.live["show_path"], self.live["sequence_path"], self.live["level_path"]]:
            raise C.P87Error("SAVE_SCOPE")
        self.dirty = {"content": [], "maps": []}
        self.saved = True

    def readback(self, parts):
        return self.owned_state(parts)

    @staticmethod
    def assert_equivalent(a, b):
        if a != b:
            raise C.P87Error("READBACK")

    def log(self, line): self.logs.append(line)
    def log_error(self, line): self.logs.append(line)


def request(mode, frame=950, parts=None):
    return {"mode": mode, "confirm": "%s P87" % mode, "run_id": "HARNESS-" + mode,
            "args": {"first_flurry_frame": frame, "parts": parts or list(C.PARTS)}}


def main():
    # Args negative controls.
    rejects("unknown arg", lambda: C.merge_args({"surprise": 1}), "UNKNOWN_ARGS")
    rejects("duplicate parts", lambda: C.merge_args({"parts": ["CAMERA", "CAMERA"]}), "PARTS")
    rejects("bad part", lambda: C.merge_args({"parts": ["FIRE"]}), "PARTS")
    rejects("empty parts", lambda: C.merge_args({"parts": []}), "PARTS")
    rejects("apply frame absent", lambda: C.merge_args({}, True), "FIRST_FLURRY_UNPINNED")
    rejects("frame outside", lambda: C.merge_args({"first_flurry_frame": 3000}), "FIRST_FLURRY_FRAME")
    rejects("bulb band reversed", lambda: C.merge_args({"bulb_front_min_cm": 200, "bulb_front_max_cm": 100}), "BULB_FRONT_BAND")
    rejects("uplight count cap", lambda: C.merge_args({"uplight_count": 30}), "ARG_uplight_count")
    rejects("uplight lumens cap", lambda: C.merge_args({"uplight_lumens": 9000}), "ARG_uplight_lumens")
    rejects("uplight shadows", lambda: C.merge_args({"uplight_cast_shadows": True}), "UPLIGHT_SHADOWS")
    rejects("mesh path", lambda: C.merge_args({"uplight_mesh": "Engine/Thing"}), "UPLIGHT_MESH")

    p = C.merge_args({"first_flurry_frame": 950}, True)
    live = live_fixture()
    plan = C.build_plan(p, live)
    check("single fall", plan["curtain"]["fall_count"] == 1)
    check("second fall recorded", len(plan["curtain"]["deactivated_sections"]) == 2)
    check("pile holds to end", plan["curtain"]["sections"][-1]["end"] == 2409)
    check("camera holds to fall", plan["camera"]["hold_end_frame"] == 950)
    check("camera end pose exact", plan["camera"]["keys"][-1] == dict({"frame": 2409}, **live["camera_end_pose"]))
    check("camera slow", plan["camera"]["move_seconds"] > 50.0)
    check("uplights after flash", all(r["intensity_keys"][1] == [950, 0.0] for r in plan["uplights"]["rows"]))
    check("uplight count", len(plan["uplights"]["rows"]) == 6)
    check("no new caster", plan["uplights"]["new_shadow_casters"] == 0)
    check("one model", len({r["mesh"] for r in plan["uplights"]["rows"]}) == 1)
    check("bulb count", len(plan["bulbs"]["rows"]) == len(live["bulbs"]))
    check("bulb clear", min(r["wing_clearance_cm"] for r in plan["bulbs"]["rows"]) >= p["bulb_wing_clearance_cm"])
    check("catfloor trace", all(r["trace"]["channel"] == "ECC_CAT_FLOOR" for r in plan["bulbs"]["rows"]))
    check("deterministic scatter", C.bulb_scatter_plan(p, live["bulbs"]) == C.bulb_scatter_plan(p, list(reversed(live["bulbs"]))))
    p2 = C.merge_args({"first_flurry_frame": 950, "bulb_yaw_deg": 5}, True)
    a, b = C.bulb_scatter_plan(p, live["bulbs"])["rows"], C.bulb_scatter_plan(p2, live["bulbs"])["rows"]
    check("single draw isolation", all(x["location_xy_proposal"] == y["location_xy_proposal"] for x, y in zip(a, b)))
    check("digest stable", C.digest(plan) == C.digest(copy.deepcopy(plan)))

    # Clock ambiguity is safe: DRY plans blocked pieces, APPLY refuses.
    unresolved = C.build_plan(C.merge_args({}), live)
    check("dry unresolved curtain", unresolved["curtain"]["status"] == "blocked_on_clock")
    check("dry unresolved camera", unresolved["camera"]["status"] == "blocked_on_clock")
    check("dry unresolved uplights", unresolved["uplights"]["status"] == "blocked_on_clock")

    # Transaction +/- controls.
    with tempfile.TemporaryDirectory() as td:
        record = os.path.join(td, "record.json")
        backend = FakeBackend()
        rejects("bad confirm", lambda: T.run(dict(request("DRY"), confirm="YES"), backend, record, td), "CONFIRM")
        backend.dirty = {"content": ["/Game/Foreign"], "maps": []}
        rejects("dirty preflight", lambda: T.run(request("DRY"), backend, record, td), "DIRTY_CENSUS")
        backend.dirty = {"content": [], "maps": []}
        dry, dry_line = T.run(request("DRY", None), backend, record, td)
        check("dry no mutation", backend.state == backend.initial and not dry["mutated"])
        check("dry blocks clock", not dry["apply_ready"] and "apply_ready=0" in dry_line)
        backend.foreign = ["foreign_record.json"]
        rejects("foreign record", lambda: T.run(request("APPLY"), backend, record, td), "FOREIGN_ACTIVE_RECORDS")
        backend.foreign = []
        applied, apply_line = T.run(request("APPLY"), backend, record, td)
        check("apply marker", "P87_OPENING_FIXES_APPLY_OK" in apply_line)
        check("record verified", json.load(open(record, encoding="utf-8"))["status"] == "saved_readback_verified")
        check("backup before change", len(backend.backups) == 1 and backend.backups[0]["hash_verified"])
        check("exact save census", backend.dirty == {"content": [], "maps": []})
        rejects("second apply", lambda: T.run(request("APPLY"), backend, record, td), "ACTIVE_RECORD")
        backend.state["camera"]["foreign_edit"] = 1
        rejects("revert drift", lambda: T.run(request("REVERT"), backend, record, td), "REVERT_DRIFT")
        del backend.state["camera"]["foreign_edit"]
        reverted, revert_line = T.run(request("REVERT"), backend, record, td)
        check("revert marker", "P87_OPENING_FIXES_REVERT_OK" in revert_line)
        check("revert exact", backend.state == backend.initial)
        check("record archived", not os.path.exists(record) and os.path.exists(reverted["record_archived"]))
        check("two backups", len(backend.backups) == 2)

    total = PASS + FAIL
    print("P87_HARNESS_RESULT|pass=%d|fail=%d|total=%d|negative=17|positive=%d" % (PASS, FAIL, total, total - 17))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
