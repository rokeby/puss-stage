"""Offline positive/negative harness for Cue Book At/GO merge, render, and export."""
import contextlib
import csv
import importlib.util
import io
import json
import pathlib
import tempfile
import unittest


HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("cue_sync_under_test", HERE / "cue_sync.py")
CUE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CUE)


class CueBookExportHarness(unittest.TestCase):
    def test_at_parse_table(self):
        for text, expected in (("74.5", 74.5), ("1:14.5", 74.5), ("0:01:14.5", 74.5),
                               ("00:01:14:12", 74.48)):
            self.assertAlmostEqual(CUE.parse_cue_time(text), expected, places=8, msg=text)

    def test_bad_at_strings_rejected(self):
        for text in ("", "tomorrow", "-0.1", "1::2", "00:00:00:25", "1:2:3:4:5"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                CUE.parse_cue_time(text)

    def test_go_parser(self):
        self.assertEqual(CUE.parse_go("20 PASS"), ("20", "PASS", "20 PASS"))
        self.assertEqual(CUE.parse_go("3.5 HOLD"), ("3.5", "HOLD", "3.5 HOLD"))
        self.assertEqual(CUE.parse_go("7"), ("7", None, "7"))
        for text in ("GO 2", "2 pass", "two HOLD", "2 WAIT", "2."):
            with self.subTest(text=text), self.assertRaises(ValueError):
                CUE.parse_go(text)

    def test_negative_go_without_at_is_refused(self):
        with self.assertRaisesRegex(ValueError, "GO has no At"):
            CUE.validate_cuebook_docs([{"key": "R1", "go": "2 HOLD"}])

    def test_web_merge_carries_at_and_go(self):
        empty = {field: "" for field in CUE.WEB_FIELDS}
        baseline = {"rows": {"R1": dict(empty)}, "web_keys": {}}
        work = [{"Key": "R1", "Origin": "shared", "At": "", "GO": "", CUE.DIRECTOR: ""}]
        docs = [{"key": "R1", "ord": 1, "at": "1:14.5", "go": "20 PASS", "cut": False}]
        merged, new_base, log, conflicts = CUE.web_merge(baseline, docs, work)
        self.assertEqual((merged[0]["At"], merged[0]["GO"]), ("1:14.5", "20 PASS"))
        self.assertEqual((new_base["rows"]["R1"]["at"], new_base["rows"]["R1"]["go"]),
                         ("1:14.5", "20 PASS"))
        self.assertEqual((len(log), conflicts), (2, []))

    def _sandbox(self, root):
        docs = root / "Docs" / "CueSheet"
        content = root / "Content" / "InfinityStage" / "CueSheet"
        docs.mkdir(parents=True)
        content.mkdir(parents=True)
        CUE.ROOT = str(root)
        CUE.DIR = str(docs)
        CUE.WORKING = str(docs / "working.csv")
        CUE.SNAPSHOT = str(docs / "shared_snapshot.csv")
        CUE.REPORT = str(docs / "sync_report.md")
        CUE.RENDER = str(docs / "PUSS_CUE_LIST.md")
        CUE.EXPORT = str(content / "Puss_Master_cue_sheet.csv")
        CUE.WEB_BASELINE = str(docs / "web_baseline.json")
        CUE.WEB_REPORT = str(docs / "web_report.md")
        CUE.SURTITLES_EXPORT = str(content / "Puss_Surtitles.csv")
        CUE.SURTITLES_BASE = str(docs / "surtitles_base.csv")
        CUE.SEGMENT_MAP = str(root / "Tools" / "CueBook" / "segment_map.json")
        fields = ["Key", "Origin", "#", "Light", "Video Cue", "Speaker: Klara", "Notes", CUE.DIRECTOR]
        rows = [{"Key": "R1", "Origin": "shared", "#": "1", "Light": "warm, then dark",
                 "Video Cue": "Passage 1", "Speaker: Klara": "café \"line\"", "Notes": "keep\nline break",
                 CUE.DIRECTOR: "director"}]
        CUE.save_csv(CUE.WORKING, fields, rows)
        blank = {field: "" for field in CUE.WEB_FIELDS}
        blank.update({"light": "warm, then dark", "videoCue": "Passage 1", "klara": "café \"line\"",
                      "notes": "keep\nline break", "cut": False})
        pathlib.Path(CUE.WEB_BASELINE).write_text(json.dumps({"rows": {"R1": blank}, "web_keys": {}}),
                                                 encoding="utf-8")
        cue = {field: "" for field in CUE.WEB_FIELDS}
        cue.update({"key": "R1", "ord": 10, "light": "warm, then dark", "videoCue": "Passage 1",
                    "klara": "café \"line\"", "notes": "keep\nline break", "at": "1:14.5", "go": "20 PASS",
                    "cut": False})
        source = root / "cuebook.json"
        source.write_text(json.dumps({"app": "puss-cue-book", "cues": [cue]}, ensure_ascii=False), encoding="utf-8")
        return source, fields, rows[0]

    def test_export_appends_columns_and_byte_preserves_old_cells(self):
        with tempfile.TemporaryDirectory() as folder:
            source, old_fields, old_row = self._sandbox(pathlib.Path(folder))
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                result = CUE.cuebook_export(str(source))
            fields, rows = CUE.load_csv(CUE.WORKING)
            self.assertEqual(fields[-3:], ["At", "GO", "Pause possible"])
            for field in old_fields:
                self.assertEqual(rows[0].get(field, "").encode("utf-8"), old_row.get(field, "").encode("utf-8"),
                                 msg="old column changed: %s" % field)
            self.assertEqual((rows[0]["At"], rows[0]["GO"]), ("1:14.5", "20 PASS"))
            with open(CUE.EXPORT, encoding="utf-8", newline="") as handle:
                export_rows = list(csv.reader(handle))
            self.assertEqual(export_rows[0][-3:], ["At", "GO", "Pause possible"])
            self.assertEqual(export_rows[2][-3:-1], ["1:14.5", "20 PASS"])
            self.assertIn("CUE_SYNC_EXPORT_OK|cues=1|surtitles=0|changed_files=", stdout.getvalue())
            self.assertIn("Docs/CueSheet/working.csv", result["changed_files"])

    def test_export_is_byte_stable_on_second_run(self):
        with tempfile.TemporaryDirectory() as folder:
            source, _fields, _row = self._sandbox(pathlib.Path(folder))
            with contextlib.redirect_stdout(io.StringIO()):
                CUE.cuebook_export(str(source))
            paths = [CUE.WORKING, CUE.WEB_BASELINE, CUE.WEB_REPORT, CUE.RENDER, CUE.EXPORT]
            before = {path: pathlib.Path(path).read_bytes() for path in paths}
            with contextlib.redirect_stdout(io.StringIO()):
                result = CUE.cuebook_export(str(source))
            self.assertEqual(result["changed_files"], [])
            self.assertEqual(before, {path: pathlib.Path(path).read_bytes() for path in paths})

    def test_surtitle_csv_round_trip_matches_branch_parser_rules(self):
        lines = [
            {"key": "TABC1", "ord": 10, "segment": "S5", "in": "1:14.5", "out": "1:16",
             "speaker": "Mountain, left", "text": "A quoted \"rumble\"\nsecond line", "notes": ""},
            {"key": "", "ord": 20, "segment": "S5", "in": "00:01:16:12", "out": "",
             "speaker": "", "text": "", "notes": "clear"},
        ]
        text = CUE.surtitles_csv(lines, {"S5"})
        rows, warnings = CUE.parse_surtitles_csv("ignored preamble\r\n" + text)
        self.assertEqual(warnings, [])
        self.assertEqual(rows[0]["text"], lines[0]["text"])
        self.assertEqual(rows[0]["speaker"], "Mountain, left")
        self.assertEqual(rows[1]["text"], "")
        self.assertEqual(rows[1]["key"], "")
        self.assertTrue(all(len(row) == 7 for row in csv.reader(io.StringIO(text))))

    def test_surtitle_negative_bad_times_and_unknown_segment(self):
        base = {"key": "TABC1", "segment": "S5", "in": "1", "out": "", "text": "hello"}
        for patch in ({"in": "-1"}, {"in": "00:00:00:25"}, {"out": "0.5"}):
            line = dict(base, **patch)
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                CUE.surtitles_csv([line], {"S5"})
        with self.assertRaisesRegex(ValueError, "unknown surtitle segment"):
            CUE.surtitles_csv([dict(base, segment="S99")], {"S5"})

    def test_export_writes_surtitles_and_base_byte_stably(self):
        with tempfile.TemporaryDirectory() as folder:
            source, _fields, _row = self._sandbox(pathlib.Path(folder))
            payload = json.loads(source.read_text(encoding="utf-8"))
            payload["surtitles"] = [{"key": "TABC1", "ord": 10, "segment": "Passage 1", "in": "1",
                                      "out": "", "speaker": "", "text": "Hello", "notes": "", "cut": False}]
            source.write_text(json.dumps(payload), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                result = CUE.cuebook_export(str(source))
            self.assertEqual(result["surtitles"], 1)
            self.assertIn("Content/InfinityStage/CueSheet/Puss_Surtitles.csv", result["changed_files"])
            self.assertEqual(pathlib.Path(CUE.SURTITLES_EXPORT).read_bytes(), pathlib.Path(CUE.SURTITLES_BASE).read_bytes())
            before = pathlib.Path(CUE.SURTITLES_EXPORT).read_bytes()
            with contextlib.redirect_stdout(io.StringIO()):
                second = CUE.cuebook_export(str(source))
            self.assertEqual(second["changed_files"], [])
            self.assertEqual(pathlib.Path(CUE.SURTITLES_EXPORT).read_bytes(), before)

    def test_unreal_time_nudge_refuses_overwrite_and_returns_change(self):
        with tempfile.TemporaryDirectory() as folder:
            source, _fields, _row = self._sandbox(pathlib.Path(folder))
            payload = json.loads(source.read_text(encoding="utf-8"))
            payload["surtitles"] = [{"key": "TABC1", "ord": 10, "segment": "Passage 1", "in": "1",
                                      "out": "", "speaker": "", "text": "Hello", "notes": "", "cut": False}]
            source.write_text(json.dumps(payload), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                CUE.cuebook_export(str(source))
            live = pathlib.Path(CUE.SURTITLES_EXPORT)
            external = live.read_text(encoding="utf-8").replace("Passage 1,1,", "Passage 1,1.25,")
            live.write_text(external, encoding="utf-8", newline="")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                result = CUE.cuebook_export(str(source))
            self.assertTrue(result["blocked"])
            self.assertIn("CUE_SYNC_SURTITLES_UNREAL_EDITS|n=1|file=", stdout.getvalue())
            self.assertEqual(live.read_text(encoding="utf-8"), external)
            changes = json.loads((pathlib.Path(CUE.ROOT) / result["changes_file"]).read_text(encoding="utf-8"))
            self.assertEqual(changes["changes"], [{"key": "TABC1", "field": "in", "from": "1", "to": "1.25"}])

    def test_existing_unbased_unreal_row_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            source, _fields, _row = self._sandbox(pathlib.Path(folder))
            payload = json.loads(source.read_text(encoding="utf-8"))
            payload["surtitles"] = []
            source.write_text(json.dumps(payload), encoding="utf-8")
            live = pathlib.Path(CUE.SURTITLES_EXPORT)
            live.parent.mkdir(parents=True, exist_ok=True)
            original = "Segment,In,Out,Speaker,Text,Notes,Key\r\nPassage 1,2,,,From Unreal,,\r\n"
            live.write_text(original, encoding="utf-8", newline="")
            original_bytes = live.read_bytes()
            with contextlib.redirect_stdout(io.StringIO()):
                result = CUE.cuebook_export(str(source))
            self.assertTrue(result["blocked"])
            self.assertEqual(live.read_bytes(), original_bytes)
            changes = json.loads((pathlib.Path(CUE.ROOT) / result["changes_file"]).read_text(encoding="utf-8"))
            self.assertEqual(len(changes["adds"]), 1)

    def test_both_side_edit_is_emitted_with_conflict_base(self):
        base = "Segment,In,Out,Speaker,Text,Notes,Key\r\nS5,1,,,Hello,,TABC1\r\n"
        live = base.replace("S5,1,", "S5,1.25,")
        current = [{"key": "TABC1", "segment": "S5", "in": "1.5", "out": "", "speaker": "",
                    "text": "Hello", "notes": "", "cut": False}]
        changes, adds = CUE.unreal_surtitle_changes(base, live, current)
        self.assertEqual(adds, [])
        self.assertEqual(changes, [{"key": "TABC1", "field": "in", "from": "1", "to": "1.25"}])
        self.assertNotEqual(current[0]["in"], changes[0]["from"])

    def test_existing_selftest_remains_23_of_23(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = CUE.selftest()
        self.assertEqual(code, 0)
        self.assertIn("CUE_SYNC_SELFTEST_OK 23/23", output.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
