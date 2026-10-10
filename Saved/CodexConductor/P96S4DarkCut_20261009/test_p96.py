"""Offline positive/negative harness for Codex job 96.  No Unreal required."""
from __future__ import annotations

import copy
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p96_core as C  # noqa: E402


def target(group, label, rng, tracks=None):
    return {"group": group, "path": "/World/PersistentLevel/" + label.replace(" ", "_"),
            "label": label, "range": list(rng), "binding_guid": None,
            "visibility_tracks": list(tracks or [])}


def state():
    return {
        "world": C.WORLD, "scene": C.SCENE, "scene_end": 4890,
        "root_cuts": [
            {"section_index": 0, "range": [0, 119], "active": True,
             "binding_guid": "A", "camera": C.ENTRY},
            {"section_index": 1, "range": [119, 4865], "active": True,
             "binding_guid": "B", "camera": C.GLIDE},
            {"section_index": 2, "range": [4865, 4890], "active": True,
             "binding_guid": "C", "camera": C.EXIT},
        ],
        "nested_slots": [{"track_index": 2, "section_index": 0,
                          "track_class": "MovieSceneSubTrack", "range": [405, 4500],
                          "active": True, "sequence": C.COPY}],
        "cut_resolutions": [
            {"role": "root_entry", "resolved_count": 1},
            {"role": "root_exit", "resolved_count": 1},
            {"role": "klara_at_cut", "resolved_count": 1},
        ],
        "target_groups": {
            "p04_lights": [target("p04_lights", "P04 SCORE B01 TOP_L", [0, 4890]),
                           target("p04_lights", "P04 Strobe", [0, 4890])],
            "p04_darkness_extensions": [
                target("p04_darkness_extensions", "P04 SCORE B01 PRACTICAL_L_BODY", [0, 406])],
            "hangar_lights_and_emissives": [
                target("hangar_lights_and_emissives", "S4 Ghost Light", [0, 4890]),
                target("hangar_lights_and_emissives", "S4 Lattice Bulb 1-1", [0, 4890])],
            "klara_precut": [target("klara_precut", "SpotLight", [0, 405]),
                             target("klara_precut", "SkyLight", [0, 405])],
            "curtain": [target("curtain", C.CURTAIN, [405, 4890])],
        },
    }


class Positive(unittest.TestCase):
    def test_exact_plan(self):
        fixture = state()
        # One exact, already-working bHidden track is deduplicated.
        fixture["target_groups"]["p04_lights"][0]["visibility_tracks"] = [{
            "property": "bHidden", "sections": [{"range": [0, 4890], "default": False,
                                                   "keys": [], "completion": "RESTORE_STATE"}]}]
        # An inert legacy track is reported, not trusted as coverage.
        fixture["target_groups"]["klara_precut"][0]["visibility_tracks"] = [{
            "property": "bHiddenInGame", "sections": [{"range": [0, 405], "default": True,
                                                         "keys": [], "completion": "RESTORE_STATE"}]}]
        plan = C.plan_change(fixture)
        self.assertEqual(plan["cut_frame"], 405)
        self.assertEqual(plan["camera"]["entry_after_range"], [0, 405])
        self.assertFalse(plan["camera"]["glide_after_active"])
        self.assertEqual(plan["counts"], {"p04_lights": 2, "p04_darkness_extensions": 1,
                                           "hangar_lights_and_emissives": 2,
                                           "klara_precut": 2, "curtain": 1})
        self.assertEqual((plan["already_dark"], plan["to_add"]), (1, 7))
        self.assertEqual(len(plan["inert_tracks_reported"]), 1)

    def test_applied_projection_changes_only_two_camera_fields(self):
        fixture = state()
        plan = C.plan_change(fixture)
        after = C.applied_state(plan, fixture)
        self.assertEqual(after["root_cuts"][0]["range"], [0, 405])
        self.assertFalse(after["root_cuts"][1]["active"])
        self.assertEqual(after["root_cuts"][2], fixture["root_cuts"][2])
        self.assertEqual(after["nested_slots"], fixture["nested_slots"])

    def test_resume_keeps_applied_camera_and_adds_only_uncovered_targets(self):
        fixture = state()
        fixture["root_cuts"][0]["range"] = [0, 405]
        fixture["root_cuts"][1]["active"] = False
        for group, rows in fixture["target_groups"].items():
            if group == "p04_darkness_extensions":
                continue
            for row in rows:
                row["visibility_tracks"] = [{"property": "bHidden", "sections": [{
                    "range": row["range"], "default": False, "keys": [],
                    "completion": "RESTORE_STATE"}]}]
        plan = C.plan_change(fixture, camera_baseline="applied")
        self.assertEqual(plan["camera"]["action"], "keep_applied")
        self.assertEqual(plan["to_add"], 1)
        self.assertEqual([row["group"] for row in plan["visibility"] if row["action"] == "add"],
                         ["p04_darkness_extensions"])


class Negative(unittest.TestCase):
    def reject(self, text, mutate):
        fixture = state()
        mutate(fixture)
        with self.assertRaisesRegex(C.PlanError, text):
            C.plan_change(fixture)

    def test_wrong_world(self):
        self.reject("WORLD", lambda x: x.update(world="/Game/Wrong"))

    def test_scene_end_drift(self):
        self.reject("SCENE_OR_END", lambda x: x.update(scene_end=4891))

    def test_cut_frame_drift(self):
        self.reject("CUT_FRAME", lambda x: x["nested_slots"][0].update(range=[406, 4500]))

    def test_root_cut_baseline_drift(self):
        self.reject("ROOT_CUT_BASELINE", lambda x: x["root_cuts"][1].update(active=False))

    def test_unresolved_cut_binding(self):
        self.reject("CUT_BINDING_UNRESOLVED",
                    lambda x: x["cut_resolutions"][2].update(resolved_count=0))

    def test_missing_p04_lights(self):
        self.reject("P04_LIGHTS_EMPTY", lambda x: x["target_groups"].update(p04_lights=[]))

    def test_missing_darkness_extensions(self):
        self.reject("P04_DARKNESS_EXTENSIONS_EMPTY",
                    lambda x: x["target_groups"].update(p04_darkness_extensions=[]))

    def test_duplicate_curtain(self):
        self.reject("CURTAIN_COUNT", lambda x: x["target_groups"]["curtain"].append(
            target("curtain", "P04 Backcloth duplicate", [405, 4890])))

    def test_actor_in_two_groups(self):
        def mutate(x):
            x["target_groups"]["curtain"][0]["path"] = x["target_groups"]["p04_lights"][0]["path"]
        self.reject("TARGET_DUPLICATE", mutate)

    def test_conflicting_working_visibility(self):
        def mutate(x):
            x["target_groups"]["curtain"][0]["visibility_tracks"] = [{
                "property": "bHidden", "sections": [{"range": [405, 4890], "default": True,
                                                       "keys": [], "completion": "RESTORE_STATE"}]}]
        self.reject("VISIBILITY_CONFLICT", mutate)


class Traps(unittest.TestCase):
    def test_enum_wrapper_normalises(self):
        self.assertEqual(C.enum_name("<MovieSceneCompletionMode.RESTORE_STATE: 1>"), "RESTORE_STATE")

    def test_channel_suffix_normalises(self):
        self.assertEqual(C.channel_base("Visibility_17"), "Visibility")

    def test_darkness_extension_rules(self):
        self.assertTrue(C.is_darkness_extension("P04 PRACTICAL_L_BODY", passage_descendant=True))
        self.assertTrue(C.is_darkness_extension("P04 mesh", emissive_material=True,
                                                passage_descendant=True))
        self.assertTrue(C.is_darkness_extension("Arrival fixture", has_light=True,
                                                arrival_driven=True))
        self.assertFalse(C.is_darkness_extension("P04 TOP_L", has_light=True,
                                                 passage_descendant=True))
        self.assertFalse(C.is_darkness_extension("Foreign bulb", passage_descendant=False))

    def test_shipped_args_are_dry(self):
        args = json.load(open(os.path.join(HERE, "p96_args.json"), encoding="utf-8"))
        self.assertEqual((args["mode"], args["confirm"], args["decided_by"]), ("DRY", "", ""))

    def test_static_safety_surface(self):
        source = open(os.path.join(HERE, "p96_editor.py"), encoding="utf-8").read()
        self.assertIn("GuidLibrary.conv_guid_to_string", source)
        self.assertIn('set_property_name_and_path("bHidden", "bHidden")', source)
        self.assertIn("RESUME P96 S4 DARK CUT", source)
        self.assertIn("pre_scene_float_drives", source)
        self.assertNotIn("save_all", source.lower())
        self.assertNotIn("delete_asset", source)
        self.assertNotIn("os.remove", source)
        self.assertNotIn('set_editor_property("cue_guid"', source)
        self.assertNotIn("set_light_color(", source)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    failures = len(result.failures) + len(result.errors)
    print("P96_HARNESS_%s|passed=%d|total=%d|positive=3|negative=10|trap=5" %
          ("OK" if not failures else "FAILED", result.testsRun - failures, result.testsRun))
    raise SystemExit(1 if failures else 0)
