"""Offline positive/negative harness for Job 97.  Does not import Unreal."""
import copy
import json
import os
import sys
import tempfile

HERE = os.path.dirname(__file__)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import e18_nap_revision as e18


def actor(label, **extra):
    row = {"label": label, "location": [0.0, 0.0, 100.0], "rotation": [0.0, -5.0, 0.0],
           "actor_hidden_in_game": False}
    row.update(extra)
    return row


def spot_rows(counts=(0, 2, 2, 2, 2)):
    rows = []
    for n in e18.AUDIT_ORDER:
        count = counts[n - 1]
        spots = []
        for name in e18.SPOT_NAMES[:count]:
            spots.append({"name": name, "binding_guid": ("%032X" % (n * 10 + len(spots))), "end": 1837,
                          "intensity_at_end": 0.0, "spawned_at_end": False,
                          "intensity_keys": [[0, 0.0], [187, 7482.0], [1700, 0.0]],
                          "spawn_keys": [[150, True], [1701, False]]})
        rows.append({"interaction": n, "sequence": e18.INTERACTION_PATHS[n], "count": count, "spots": spots})
    return rows


def snapshot():
    return {
        "cue": {"guid": e18.NAP_GUID, "label": e18.OLD_LABEL, "type": "SEQUENCE"},
        "segment": {"guid": e18.NAP_GUID, "label": e18.OLD_LABEL, "type": "SEQUENCE",
                    "start": 35775360, "end": 36279360},
        "tick_resolution": 24000.0,
        "markers": [[0, "InfinityStage.VampStart"], [500, "GO 45 PASS " + e18.OLD_LABEL],
                    [500, "InfinityStage.VampEnd"]],
        "loop_frames": 500, "total_frames": 525, "fps": 25,
        "actors": [
            actor(e18.CAT_LABEL, visible=True, visibility_keys=[[0, True], [525, True]]),
            actor(e18.CAMERA_LABEL, z_keys=[[0, 155.0], [525, 159.0]], roll_keys=[[0, 0.0], [525, 0.0]]),
            actor(e18.LIGHT_LABELS[0], intensity=280.0), actor(e18.LIGHT_LABELS[1], intensity=140.0),
        ],
        "spots": spot_rows(),
    }


class FakeBackend(object):
    def __init__(self, state=None):
        self.state = copy.deepcopy(state or snapshot())
        self.dirty = {"content": [], "maps": []}
        self.logs, self.stops = [], []
        self.args = None

    def log(self, text): self.logs.append(text)
    def stop(self, text): self.stops.append(text)
    def census(self): return copy.deepcopy(self.dirty)
    def preflight(self, args):
        self.args = args
        if self.dirty != {"content": [], "maps": []}: raise e18.PlanError("DIRTY")
    def inspect(self, unused_args): return copy.deepcopy(self.state)
    def backup(self, run, packages, prefix):
        return {"root": "Backups/%s-%s" % (prefix, run),
                "files": [{"package": p, "source": p, "backup": "backup/" + p} for p in packages]}
    def apply(self, plan):
        self.state["cue"]["label"] = e18.NEW_LABEL
        self.state["segment"]["label"] = e18.NEW_LABEL
        self.state["markers"] = sorted([[f, plan["marker"]["new"] if label == plan["marker"]["old"] else label]
                                         for f, label in self.state["markers"]])
        actors = {x["label"]: x for x in self.state["actors"]}
        actors[e18.CAT_LABEL].update(visible=False, actor_hidden_in_game=True,
                                     visibility_keys=[[0, False], [525, False]])
        actors[e18.CAMERA_LABEL]["z_keys"] = copy.deepcopy(plan["camera"]["z_keys"])
        actors[e18.CAMERA_LABEL]["roll_keys"] = copy.deepcopy(plan["camera"]["roll_keys"])
        for label, value in plan["lights"].items(): actors[label]["intensity"] = value
        for row in self.state["spots"]:
            for spot in row["spots"]:
                spot["intensity_at_end"], spot["spawned_at_end"] = 0.0, False
                spot["intensity_keys"].append([spot["end"], 0.0])
                spot["spawn_keys"].append([spot["end"], False])
        self.dirty = {"content": sorted(p for p in plan["named_packages"] if p != e18.LEVEL),
                      "maps": [e18.LEVEL]}
    def save(self, packages):
        got = sorted(self.dirty["content"] + self.dirty["maps"])
        if got != sorted(packages): raise e18.PlanError("SAVE_SCOPE")
        self.dirty = {"content": [], "maps": []}
        return list(packages)
    def revert(self, record):
        self.state = copy.deepcopy(record["snapshot_before"])
        plan = record["plan"]
        self.dirty = {"content": sorted(p for p in plan["named_packages"] if p != e18.LEVEL),
                      "maps": [e18.LEVEL]}
        return {"restored_packages": list(plan["named_packages"])}


RESULTS = []
POSITIVE = 0
NEGATIVE = 0


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))


base = snapshot()
plan = e18.build_plan(base, {})
preview = e18.write_preview(plan, os.path.join(HERE, "e18_nap_revision_preview_default.png"))
check("P1 recorded GUID and exact Gary label", plan["cue"]["guid"] == e18.NAP_GUID and
      plan["cue"]["new_label"] == e18.NEW_LABEL)
check("P1 marker renamed at same vamp frame", plan["marker"]["frame"] == 500 and plan["marker"]["new"].startswith("GO 45 PASS "))
check("P1 I4 audited first and absent I1 retained", plan["spot_audit_order"][0] == 4 and
      [x["count"] for x in plan["spots_before"] if x["interaction"] == 1] == [0])
check("P1 camera loop closes value and tiny roll", plan["camera"]["z_keys"][0][1] == plan["camera"]["z_keys"][-2][1] and
      plan["camera"]["roll_keys"][0][1] == plan["camera"]["roll_keys"][-2][1])
check("P1 cat hidden and ambience dim", plan["cat_visibility"]["visible"] is False and max(plan["lights"].values()) <= 18.0)
check("P1 analytical PNG written", open(preview, "rb").read(8) == b"\x89PNG\r\n\x1a\n" and os.path.getsize(preview) > 1000)
POSITIVE += 1

scratch = tempfile.mkdtemp(prefix="e18_harness_")  # intentionally retained; no permanent deletion
backend = FakeBackend(base)
dry_raw = {"mode": "DRY", "run_id": "H-DRY", "confirm": "DRY E18 H-DRY", "params": {}}
e18.main(dry_raw, backend=backend, root=scratch)
apply_raw = {"mode": "APPLY", "run_id": "H-APPLY", "confirm": "APPLY E18 H-APPLY", "params": {}}
record = e18.main(apply_raw, backend=backend, root=scratch)
check("P2 APPLY semantic read-back", e18.verify_after(record["plan"], backend.inspect({})) == [])
check("P2 targeted save returns clean census", backend.census() == {"content": [], "maps": []})
check("P2 record reaches saved_readback_verified", record["status"] == "saved_readback_verified")
POSITIVE += 1

revert_raw = {"mode": "REVERT", "run_id": "H-REVERT", "source_run_id": "H-APPLY",
              "confirm": "REVERT E18 H-APPLY", "params": {}}
e18.main(revert_raw, backend=backend, root=scratch)
check("P3 REVERT restores exact semantic snapshot", e18.digest(backend.state) == e18.digest(base))
check("P3 REVERT targeted save returns clean census", backend.census() == {"content": [], "maps": []})
POSITIVE += 1


def refuses(name, mutate, token):
    global NEGATIVE
    state, args = snapshot(), {}
    mutate(state, args)
    try:
        e18.build_plan(state, args)
        check(name, False, "did not refuse")
    except e18.PlanError as exc:
        check(name, token in str(exc), str(exc))
    NEGATIVE += 1


refuses("N1 GUID drift", lambda s, a: s["cue"].update(guid="A" * 32), "IDENTITY_DRIFT")
refuses("N2 old label drift", lambda s, a: s["cue"].update(label="other"), "IDENTITY_DRIFT")
refuses("N3 missing old marker", lambda s, a: s.update(markers=[x for x in s["markers"] if not x[1].startswith("GO")]), "MARKER_COUNT")
refuses("N4 duplicate new marker", lambda s, a: s["markers"].append([500, "GO 45 PASS " + e18.NEW_LABEL]), "ALREADY_EXISTS")
refuses("N5 GO off vamp end", lambda s, a: s["markers"].__setitem__(1, [499, s["markers"][1][1]]), "GO_NOT_AT_VAMP_END")
refuses("N6 actor set drift", lambda s, a: s["actors"].pop(), "ACTOR_SET")
refuses("N7 one shadow spot only", lambda s, a: s.update(spots=spot_rows((0, 2, 2, 1, 2))), "CARDINALITY")
refuses("N8 non-seamless period", lambda s, a: a.update(camera_breath_period_seconds=3.0), "NOT_SEAMLESS")
refuses("N9 invalid recorded GUID", lambda s, a: a.update(recorded_nap_guid="bad"), "GUID_INVALID")
refuses("N10 changed new label refused", lambda s, a: a.update(new_label="short"), "LABEL_CONTRACT")
refuses("N11 negative breath amplitude", lambda s, a: a.update(camera_breath_amplitude_cm=-1), "BREATH_ARGS")
refuses("N12 light set incomplete", lambda s, a: a.update(nap_light_intensities={e18.LIGHT_LABELS[0]: 1}), "LIGHT_LABEL_SET")
refuses("N13 Master range drift", lambda s, a: s["segment"].update(start=s["segment"]["start"] + 24), "MASTER_RANGE_DRIFT")

try:
    e18.main({"mode": "DRY", "run_id": "BAD", "confirm": "APPLY E18 BAD", "params": {}},
             backend=FakeBackend(), root=scratch)
    check("N14 confirm mismatch", False)
except e18.Stop as exc:
    check("N14 confirm mismatch", "CONFIRM_MISMATCH" in str(exc), str(exc))
NEGATIVE += 1

broken = copy.deepcopy(plan)
facts = copy.deepcopy(base)
facts["cue"]["label"] = e18.NEW_LABEL
facts["markers"][1][1] = plan["marker"]["new"]
facts["actors"][0].update(visible=False, actor_hidden_in_game=True)
facts["actors"][1]["z_keys"] = plan["camera"]["z_keys"]
facts["actors"][1]["roll_keys"] = plan["camera"]["roll_keys"]
facts["actors"][2]["intensity"] = plan["lights"][e18.LIGHT_LABELS[0]]
facts["actors"][3]["intensity"] = plan["lights"][e18.LIGHT_LABELS[1]]
facts["spots"][0]["spots"][0]["intensity_at_end"] = 1.0
facts["segment"]["label"] = e18.NEW_LABEL
check("N15 terminal light leak detected", any("INTENSITY" in x for x in e18.verify_after(plan, facts)))
NEGATIVE += 1

passed = sum(ok for _, ok, _ in RESULTS)
failed = [(name, detail) for name, ok, detail in RESULTS if not ok]
result = {"positive": "%d/3" % POSITIVE, "negative": "%d/15" % NEGATIVE,
          "checks_passed": passed, "checks_total": len(RESULTS), "failures": failed,
          "scratch_retained": scratch}
with open(os.path.join(HERE, "e18_harness_result.json"), "w", encoding="utf-8") as handle:
    json.dump(result, handle, indent=2, sort_keys=True)
    handle.write("\n")
for name, detail in failed:
    print("FAIL", name, detail)
print("E18_NAP_REVISION_HARNESS_%s|positive=%d/3|negative=%d/15|checks=%d/%d" %
      ("OK" if not failed else "FAIL", POSITIVE, NEGATIVE, passed, len(RESULTS)))
sys.exit(1 if failed else 0)
