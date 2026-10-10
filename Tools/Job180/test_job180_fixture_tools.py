"""Offline positive/negative controls for job 180's two Unreal Python tools."""

import importlib.util
import json
import pathlib
import sys
import tempfile
import types
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
SUPPRESS = ROOT / "Saved/CodexStructure/job180_suppress_p06_fixture_body.py"
FIXTURES = ROOT / "Plugins/InfinityStage/Content/Python/infinity_stage_fixture_tools.py"
INIT = ROOT / "Plugins/InfinityStage/Content/Python/init_unreal.py"


class Struct:
    def __init__(self, **values):
        self.values = values

    def get_editor_property(self, name):
        return self.values[name]

    def set_editor_property(self, name, value):
        self.values[name] = value


class Passage:
    def __init__(self, label="Passage 06 - Fixed Wings"):
        self.label = label
        self.managed = []

    def get_actor_label(self):
        return self.label

    def get_editor_property(self, name):
        if name == "managed_attachment_actors":
            return self.managed
        raise KeyError(name)


class Structure:
    def __init__(self, passage, bodies=8, succeeds=True):
        self.passage = passage
        self.bodies = bodies
        self.succeeds = succeeds
        self.rebuilds = 0

    def get_actor_label(self):
        return "Structure 06"

    def get_editor_property(self, name):
        if name == "passage":
            return self.passage
        if name == "fixture_body_count":
            return self.bodies
        raise KeyError(name)

    def rebuild_fixtures_only(self):
        self.rebuilds += 1
        return self.succeeds


class Selected:
    def __init__(self, parent, is_light=True):
        self.parent = parent
        self.is_light = is_light

    def get_attach_parent_actor(self):
        return self.parent

    def get_component_by_class(self, component_class):
        return object() if self.is_light else None


class ActorSubsystem:
    def __init__(self, selected=None, actors=None):
        self.selected = selected or []
        self.actors = actors or []

    def get_selected_level_actors(self):
        return self.selected

    def get_all_level_actors(self):
        return self.actors


class EditorSubsystem:
    def __init__(self, game_world=None):
        self.game_world = game_world

    def get_game_world(self):
        return self.game_world


class MenuEntry:
    def __init__(self, name, type):
        self.name = name
        self.type = type
        self.label = ""
        self.command = ""

    def set_label(self, value):
        self.label = value

    def set_tool_tip(self, value):
        self.tooltip = value

    def set_string_command(self, command_type, custom_type, command):
        self.command = command


class Menu:
    def __init__(self, name="LevelEditor.MainMenu"):
        self.name = name
        self.entries = []

    def get_name(self):
        return self.name

    def add_sub_menu(self, *args):
        return self

    def add_menu_entry(self, section, entry):
        self.entries.append((section, entry))


class Menus:
    def __init__(self):
        self.menu = Menu()

    def find_menu(self, name):
        return self.menu

    def refresh_all_widgets(self):
        pass


def fake_unreal(project_dir):
    module = types.ModuleType("unreal")
    module.InfinityStagePassageActor = Passage
    module.InfinityStageStructureActor = Structure
    module.LightComponentBase = type("LightComponentBase", (), {})
    module.UnrealEditorSubsystem = type("UnrealEditorSubsystem", (), {})
    module.EditorActorSubsystem = type("EditorActorSubsystem", (), {})
    module.LevelEditorSubsystem = type("LevelEditorSubsystem", (), {})
    module.GuidLibrary = type("GuidLibrary", (), {"conv_guid_to_string": staticmethod(str)})
    module.Paths = type("Paths", (), {
        "project_dir": staticmethod(lambda: str(project_dir)),
        "project_saved_dir": staticmethod(lambda: str(project_dir / "Saved")),
        "project_content_dir": staticmethod(lambda: str(project_dir / "Content")),
    })
    module.MultiBlockType = type("MultiBlockType", (), {"MENU_ENTRY": 1})
    module.ToolMenuStringCommandType = type("ToolMenuStringCommandType", (), {"PYTHON": 1})
    module.ToolMenuEntry = MenuEntry
    module._menus = Menus()
    module.ToolMenus = type("ToolMenus", (), {"get": staticmethod(lambda: module._menus)})
    module.logs = []
    module.errors = []
    module.log = module.logs.append
    module.log_error = module.errors.append
    return module


def load(name, path, unreal_module):
    sys.modules["unreal"] = unreal_module
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_show(label="P06 EVT B02 BLACK F00 CAMERA"):
    attachment = Struct(
        label=label,
        kind="InfinityAttachmentKind.LIGHT",
        enabled=True,
        anchor="InfinityAttachmentAnchor.STATION",
        attachment_guid="GUID-180",
        suppress_fixture_body=False,
    )
    pair = Struct(attachments=[attachment])
    cue = Struct(label="P06 Wing 002", wing_pair=pair)
    return Struct(cues=[cue]), attachment


class Job180ToolsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.unreal = fake_unreal(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_suppression_nested_write_and_identity(self):
        tool = load("job180_suppress_test", SUPPRESS, self.unreal)
        show, attachment = make_show()
        target = tool.find_target(show)
        self.assertEqual(target["attachment_guid"], "GUID-180")
        self.assertFalse(target["suppressed"])
        tool.set_target_suppressed(show, target, True)
        self.assertTrue(attachment.get_editor_property("suppress_fixture_body"))
        self.assertTrue(tool.find_target(show)["suppressed"])

    def test_duplicate_target_and_wrong_confirm_refuse(self):
        tool = load("job180_suppress_negative", SUPPRESS, self.unreal)
        show, _ = make_show()
        duplicate, _ = make_show()
        show.values["cues"].extend(duplicate.values["cues"])
        with self.assertRaisesRegex(tool.Job180Refused, "TARGET_COUNT"):
            tool.find_target(show)
        with self.assertRaisesRegex(tool.Job180Refused, "CONFIRM_REQUIRED"):
            tool._desired_for_mode("APPLY", "WRONG", "")

    def test_revert_requires_matching_apply_record(self):
        tool = load("job180_suppress_revert", SUPPRESS, self.unreal)
        source = self.root / "apply.json"
        source.write_text(json.dumps({
            "job": 180,
            "mode": "APPLY",
            "run_id": "J180-POSITIVE",
            "before_suppressed": False,
        }), encoding="utf-8")
        desired, resolved = tool._desired_for_mode(
            "REVERT", "REVERT_JOB180_P06_FIXTURE_SUPPRESSION:J180-POSITIVE", str(source))
        self.assertFalse(desired)
        self.assertEqual(pathlib.Path(resolved), source)

    def test_selected_passage_rebuild_positive_and_pie_negative(self):
        passage = Passage()
        selected = Selected(passage)
        passage.managed.append(selected)
        structure = Structure(passage, bodies=7)
        actor_subsystem = ActorSubsystem([selected], [passage, structure])
        editor_subsystem = EditorSubsystem()
        self.unreal.get_editor_subsystem = lambda cls: (
            editor_subsystem if cls is self.unreal.UnrealEditorSubsystem else actor_subsystem)
        helper = load("job180_fixture_helper", FIXTURES, self.unreal)
        self.assertTrue(helper.rebuild_selected_passage_fixtures())
        self.assertEqual(structure.rebuilds, 1)
        self.assertTrue(any("INFINITY_STAGE_FIXTURES_REBUILT" in line for line in self.unreal.logs))

        editor_subsystem.game_world = object()
        self.assertFalse(helper.rebuild_selected_passage_fixtures())
        self.assertEqual(structure.rebuilds, 1)
        self.assertTrue(any("PIE/SIE is active" in line for line in self.unreal.errors))

    def test_selected_non_light_attachment_is_rejected(self):
        passage = Passage()
        selected = Selected(passage, is_light=False)
        passage.managed.append(selected)
        structure = Structure(passage)
        actor_subsystem = ActorSubsystem([selected], [passage, structure])
        editor_subsystem = EditorSubsystem()
        self.unreal.get_editor_subsystem = lambda cls: (
            editor_subsystem if cls is self.unreal.UnrealEditorSubsystem else actor_subsystem)
        helper = load("job180_fixture_helper_non_light", FIXTURES, self.unreal)
        self.assertFalse(helper.rebuild_selected_passage_fixtures())
        self.assertEqual(structure.rebuilds, 0)
        self.assertTrue(any("Select exactly one" in line for line in self.unreal.errors))

    def test_startup_registers_fallback_menu(self):
        load("job180_init_unreal", INIT, self.unreal)
        entries = [entry for _, entry in self.unreal._menus.menu.entries]
        rebuild = [entry for entry in entries if entry.name == "Puss.RebuildPassageFixtures"]
        self.assertEqual(len(rebuild), 1)
        self.assertEqual(rebuild[0].label, "Rebuild Passage Fixtures")
        self.assertIn("rebuild_selected_passage_fixtures", rebuild[0].command)


if __name__ == "__main__":
    unittest.main(verbosity=2)
