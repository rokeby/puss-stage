"""Harness for breath_shift.py (offline; every file lives in a temp folder). Run: python Tools/CueSheet/test_breath_shift.py"""
import contextlib
import csv
import io
import json
import os
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cue_sync as CUE  # noqa: E402
import breath_shift as BS  # noqa: E402

FIELDS = ["Key", "Origin", "Video Cue", "Speaker: Klara", CUE.DIRECTOR, "At", "GO", "Pause possible"]


class BreathShiftHarness(unittest.TestCase):
    def sandbox(self, root):
        docs = root / "Docs" / "CueSheet"
        content = root / "Content" / "InfinityStage" / "CueSheet"
        docs.mkdir(parents=True)
        content.mkdir(parents=True)
        for name, value in {"ROOT": root, "DIR": docs, "WORKING": docs / "working.csv", "RENDER": docs / "PUSS_CUE_LIST.md",
                            "EXPORT": content / "Puss_Master_cue_sheet.csv", "WEB_BASELINE": docs / "web_baseline.json",
                            "SURTITLES_EXPORT": content / "Puss_Surtitles.csv",
                            "SEGMENT_MAP": root / "segment_map.json"}.items():
            setattr(CUE, name, str(value))
        BS.BREATHS = str(docs / "breaths")
        BS.CANDIDATES = str(docs / "breath_candidates.json")
        rows = [
            {"Key": "R1", "Video Cue": "Passage 2", "At": "5", "Speaker: Klara": "early line"},
            {"Key": "R2", "At": "1:14.5", "Pause possible": "yes", "Speaker: Klara": "rain"},
            {"Key": "R3", "At": "80", "GO": "20 PASS"},
            {"Key": "R4", "Video Cue": "Passage 3", "At": "90"},
        ]
        CUE.save_csv(CUE.WORKING, FIELDS, [dict({"Origin": "shared", CUE.DIRECTOR: ""}, **r) for r in rows])
        with open(CUE.SEGMENT_MAP, "w", encoding="utf-8") as handle:
            json.dump({"Passage 2": "P02", "Passage 3": "P03"}, handle)
        with open(CUE.SURTITLES_EXPORT, "w", encoding="utf-8", newline="") as handle:
            handle.write("Segment,In,Out,Speaker,Text,Notes,Key\r\n"
                         "P02,70,78,West,before the breath? no: after,,T1\r\n"
                         "P02,10,12,East,early,,T2\r\n"
                         "P03,80,,North,other passage,,T3\r\n")

    def run_quiet(self, fn, *args):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            result = fn(*args)
        return result, out.getvalue()

    def working(self):
        return {r["Key"]: r for r in CUE.load_csv(CUE.WORKING)[1]}

    def surtitles(self):
        with open(CUE.SURTITLES_EXPORT, encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def test_format_keeps_the_original_style(self):
        self.assertEqual(BS.fmt_like("1:14.5", 74.5 + 12), "1:26.5")
        self.assertEqual(BS.fmt_like("80", 92), "92")
        self.assertEqual(BS.fmt_like("7.25", 9.75), "9.75")

    def test_apply_moves_only_this_passage_at_or_after_f(self):
        with tempfile.TemporaryDirectory() as folder:
            self.sandbox(pathlib.Path(folder))
            path, out = self.run_quiet(BS.shift, "APPLY", "P02", "60", "12", "APPLY_BREATH_SHIFT")
            self.assertIn("BREATH_SHIFT_APPLY_OK", out)
            w = self.working()
            self.assertEqual(w["R1"]["At"], "5", "before F: unchanged")
            self.assertEqual(w["R2"]["At"], "1:26.5")
            self.assertEqual(w["R3"]["At"], "92")
            self.assertEqual(w["R3"]["GO"], "20 PASS", "the GO number travels with its At, unchanged")
            self.assertEqual(w["R4"]["At"], "90", "control: the next Passage is untouched")
            lines = {l["Key"]: l for l in self.surtitles()}
            self.assertEqual((lines["T1"]["In"], lines["T1"]["Out"]), ("82", "90"))
            self.assertEqual(lines["T2"]["In"], "10", "control: an early line stays")
            self.assertEqual(lines["T3"]["In"], "80", "control: another passage's line stays")
            record = json.load(open(path, encoding="utf-8"))
            self.assertEqual((len(record["cue_moves"]), len(record["line_moves"])), (2, 2))

    def test_revert_is_exact_and_refuses_after_an_edit(self):
        with tempfile.TemporaryDirectory() as folder:
            self.sandbox(pathlib.Path(folder))
            before_w = open(CUE.WORKING, encoding="utf-8").read()
            before_s = open(CUE.SURTITLES_EXPORT, encoding="utf-8").read()
            path, _ = self.run_quiet(BS.shift, "APPLY", "Passage 2", "1:00", "12", "APPLY_BREATH_SHIFT")
            _, out = self.run_quiet(BS.revert, path, "REVERT_BREATH_SHIFT")
            self.assertIn("BREATH_SHIFT_REVERT_OK", out)
            self.assertEqual(open(CUE.WORKING, encoding="utf-8").read(), before_w, "working.csv byte-identical")
            self.assertEqual([l["In"] for l in self.surtitles()], ["70", "10", "80"])
            # negative control: a second shift, then someone edits a moved cue; revert must refuse, change nothing
            path2, _ = self.run_quiet(BS.shift, "APPLY", "P02", "60", "12", "APPLY_BREATH_SHIFT")
            fields, rows = CUE.load_csv(CUE.WORKING)
            for r in rows:
                if r["Key"] == "R3":
                    r["At"] = "95"
            CUE.save_csv(CUE.WORKING, fields, rows)
            snapshot = open(CUE.WORKING, encoding="utf-8").read()
            with self.assertRaises(SystemExit) as stop:
                self.run_quiet(BS.revert, path2, "REVERT_BREATH_SHIFT")
            self.assertIn("BREATH_SHIFT_STOPPED", str(stop.exception))
            self.assertEqual(open(CUE.WORKING, encoding="utf-8").read(), snapshot, "refused revert wrote nothing")
            self.assertTrue(before_s)

    def test_negative_controls(self):
        with tempfile.TemporaryDirectory() as folder:
            self.sandbox(pathlib.Path(folder))
            snapshot = open(CUE.WORKING, encoding="utf-8").read()
            for args, why in ((("APPLY", "P02", "60", "12", None), "no confirm"),
                              (("APPLY", "Passage 9", "60", "12", "APPLY_BREATH_SHIFT"), "unknown passage"),
                              (("APPLY", "P02", "60", "-3", "APPLY_BREATH_SHIFT"), "negative D")):
                with self.subTest(why=why), self.assertRaises(SystemExit):
                    self.run_quiet(BS.shift, *args)
            _, out = self.run_quiet(BS.shift, "DRY", "P02", "60", "12")
            self.assertIn("BREATH_SHIFT_DRY_OK", out)
            self.assertEqual(open(CUE.WORKING, encoding="utf-8").read(), snapshot, "DRY and refusals write nothing")
            self.assertFalse(os.path.exists(BS.BREATHS), "no record for a refused or DRY shift")

    def test_candidates_lists_pause_points(self):
        with tempfile.TemporaryDirectory() as folder:
            self.sandbox(pathlib.Path(folder))
            out, text = self.run_quiet(BS.candidates)
            self.assertEqual([(c["key"], c["segment_key"], c["at_s"]) for c in out], [("R2", "P02", 74.5)])
            self.assertIn("BREATH_CANDIDATES_OK|n=1|passages=1", text)


if __name__ == "__main__":
    unittest.main(verbosity=1)
