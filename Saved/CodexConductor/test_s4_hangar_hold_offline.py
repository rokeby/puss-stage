"""Offline harness for s4_hangar_hold.py (now scenes 1-4) pure functions (no Unreal). Each positive check has a negative control that
must FAIL the same check. Run: python Saved/CodexConductor/test_s4_hangar_hold_offline.py
Numbers: fold [0, 775), S4 playback [0, 4890) [meas klara_reveal_record_S4.json plan.lattice.facts / timeline];
tick 24000 at 25 fps -> 960 ticks/frame; lattice fly Z 2900 -> 1700 at 379 frames [meas hangar_resize_s4_record.json
key_plan]. Root pitch keys -90 -> 0 are SYNTHETIC."""
import copy
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import s4_hangar_hold as H  # noqa: E402  (import without unreal must run nothing)

TPF = 960
FOLD = {"range": [0, 775], "start_offset_tick": 0, "play_rate": 1.0}
PLAY = [0, 4890]
RISE_END = 775 * TPF


def chans(**over):
    c = {n: {"keys": [], "default": 1.0 if n.startswith("Scale") else 0.0} for n in H.CHANNELS}
    for k, v in over.items():
        c[k.replace("_", ".")] = v
    return c


def movers():
    return [
        {"binding": "S4 Hangar Root", "sections": [{"blend": "UNSET", "channels": chans(
            Rotation_Y={"keys": [[-141 * TPF, -90.0], [99 * TPF, 0.0]], "default": -90.0})}]},
        {"binding": "S4 Hangar Lattice Fly", "sections": [{"blend": "ABSOLUTE", "channels": chans(
            Location_X={"keys": [], "default": 3000.0},
            Location_Z={"keys": [[0, 2900.0], [259 * TPF, 2900.0], [379 * TPF, 1700.0]], "default": 2900.0})}]},
    ]


def refuses(fn, *a):
    try:
        fn(*a)
    except H.PlanError as exc:
        return str(exc)
    return None


class Plan(unittest.TestCase):
    def test_landed_values_and_range(self):
        p = H.plan_holds(FOLD, PLAY, TPF, RISE_END, movers())
        self.assertEqual(p["range"], [775, 4890])
        v = {t["binding"]: t["values"] for t in p["targets"]}
        self.assertEqual(v["S4 Hangar Root"]["Rotation.Y"], 0.0)          # landed, not REST -90
        self.assertEqual(v["S4 Hangar Lattice Fly"]["Location.Z"], 1700.0)
        self.assertEqual(v["S4 Hangar Lattice Fly"]["Location.X"], 3000.0)  # unkeyed -> default
        self.assertEqual(v["S4 Hangar Root"]["Scale.X"], 1.0)
        # control: a planner that used the FIRST key (REST) would differ
        self.assertNotEqual(v["S4 Hangar Root"]["Rotation.Y"], movers()[0]["sections"][0]["channels"]["Rotation.Y"]["keys"][0][1])

    def test_unsorted_keys_use_latest_time(self):
        m = movers()
        m[0]["sections"][0]["channels"]["Rotation.Y"]["keys"].reverse()
        self.assertEqual(H.plan_holds(FOLD, PLAY, TPF, RISE_END, m)["targets"][0]["values"]["Rotation.Y"], 0.0)

    def test_refusals(self):
        cases = {
            "FOLD_NOT_AT_ZERO": (dict(FOLD, range=[5, 775]), PLAY, RISE_END, movers()),
            "FOLD_START_OFFSET": (dict(FOLD, start_offset_tick=960), PLAY, RISE_END, movers()),
            "FOLD_PLAY_RATE": (dict(FOLD, play_rate=2.0), PLAY, RISE_END, movers()),
            "FOLD_NOT_WHOLE_RISE": (FOLD, PLAY, RISE_END + TPF, movers()),
            "NOTHING_UNCOVERED": (FOLD, [0, 775], RISE_END, movers()),
            "NO_TRANSFORM_MOVERS": (FOLD, PLAY, RISE_END, []),
        }
        for want, (f, pl, re_, mv) in cases.items():
            self.assertIn(want, refuses(H.plan_holds, f, pl, TPF, re_, mv) or "", want)
        m = movers(); m[1]["sections"][0]["blend"] = "ADDITIVE"
        self.assertIn("MOVER_NOT_ABSOLUTE", refuses(H.plan_holds, FOLD, PLAY, TPF, RISE_END, m))
        m = movers(); m[0]["sections"].append(copy.deepcopy(m[0]["sections"][0]))
        self.assertIn("MOVER_SECTIONS", refuses(H.plan_holds, FOLD, PLAY, TPF, RISE_END, m))
        m = movers(); m[0]["sections"][0]["channels"]["Rotation.Y"]["keys"].append([800 * TPF, 5.0])
        self.assertIn("KEY_AFTER_RISE_END", refuses(H.plan_holds, FOLD, PLAY, TPF, RISE_END, m))
        m = movers(); m[0]["sections"][0]["channels"]["Location.Z"] = {"keys": [], "default": None}
        self.assertIn("CHANNEL_UNKEYED_NO_DEFAULT", refuses(H.plan_holds, FOLD, PLAY, TPF, RISE_END, m))
        m = movers(); del m[0]["sections"][0]["channels"]["Scale.Z"]
        self.assertIn("MOVER_CHANNELS_MISSING", refuses(H.plan_holds, FOLD, PLAY, TPF, RISE_END, m))
        m = movers() + [movers()[0]]
        self.assertIn("DUPLICATE_MOVER", refuses(H.plan_holds, FOLD, PLAY, TPF, RISE_END, m))
        # control: the clean case refuses nothing
        self.assertIsNone(refuses(H.plan_holds, FOLD, PLAY, TPF, RISE_END, movers()))


class Survey(unittest.TestCase):
    def test_short_and_covers(self):
        r = H.survey_row(4, PLAY, [{"range": [0, 775]}], 25.0)
        self.assertEqual((r["verdict"], r["uncovered_frames"], r["uncovered_s"]), ("SHORT", 4115, 164.6))
        c = H.survey_row(5, [0, 1225], [{"range": [0, 1225]}], 25.0)
        self.assertEqual((c["verdict"], c["uncovered_frames"]), ("COVERS", 0))
        self.assertEqual(H.survey_row(6, PLAY, [], 25.0)["verdict"], "NO_RISE_SUBSECTION")
        # S1 now 247.04 s = 6176 frames vs fold 775 [meas hookin dry; conductor]
        self.assertEqual(H.survey_row(1, [0, 6176], [{"range": [0, 775]}], 25.0)["verdict"], "SHORT")


class Args(unittest.TestCase):
    def test_args(self):
        with open(os.path.join(HERE, "s4_hangar_hold_args.json"), encoding="utf-8") as h:
            a = json.load(h)
        self.assertEqual(H.validate_args(a), [])                       # shipped file: DRY, valid
        self.assertEqual(a["mode"], "DRY")
        a = dict(a, scene=4, decided_by="")       # shipped file carries Gary's words; checks below set their own
        for bad in (0, 5, 6, None, "x"):
            self.assertTrue([r for r in H.validate_args(dict(a, scene=bad)) if r.startswith("SCENE_NOT_IN")], bad)
        for n in (1, 2, 3):
            ok = dict(a, scene=n, mode="APPLY", confirm="APPLY S%dHOLD" % n, decided_by="x")
            self.assertEqual(H.validate_args(ok), [], n)
            self.assertEqual(H.validate_args(dict(ok, mode="REVERT", confirm="REVERT S%dHOLD" % n)), [], n)
            # control: S4's confirm cannot authorise another scene
            self.assertIn("CONFIRM", H.validate_args(dict(ok, confirm="APPLY S4HOLD")), n)
        self.assertIn("CONFIRM", H.validate_args(dict(a, mode="APPLY", decided_by="x")))
        self.assertIn("DECIDED_BY", H.validate_args(dict(a, mode="APPLY", confirm="APPLY S4HOLD")))
        self.assertEqual(H.validate_args(dict(a, mode="APPLY", confirm="APPLY S4HOLD", decided_by="x")), [])
        self.assertIn("CONFIRM", H.validate_args(dict(a, mode="REVERT", confirm="APPLY S4HOLD")))
        self.assertIn("COMPLETION", H.validate_args(dict(a, completion="WHATEVER")))


class Readback(unittest.TestCase):
    def test_diff(self):
        vals = {c: float(i) for i, c in enumerate(H.CHANNELS)}
        want = {"range": [775, 4890], "completion": "KEEP_STATE", "values": vals}
        got = {"range": [775, 4890], "completion": "KEEP_STATE", "values": dict(vals), "n_keys": 0}
        self.assertEqual(H.readback_diff(want, got), [])
        for mut in (lambda g: g.update(range=[775, 4889]), lambda g: g.update(completion="RESTORE_STATE"),
                    lambda g: g.update(n_keys=1), lambda g: g["values"].update({"Rotation.Y": 0.5}),
                    lambda g: g["values"].pop("Scale.Z")):
            g = copy.deepcopy(got)
            mut(g)
            self.assertTrue(H.readback_diff(want, g), "mutation not caught")

    def test_channel_base(self):
        self.assertEqual(H.channel_base("Location.Y_183"), "Location.Y")
        self.assertEqual(H.channel_base("Rotation.Z"), "Rotation.Z")


# ---------------------------------------------------------------------------------------------------------------------
# Generalisation (7 Oct): S4 bit-identical names/record; S1/S2/S3 plans and traps.
# ---------------------------------------------------------------------------------------------------------------------

class S4Unchanged(unittest.TestCase):
    """names(4) must be the S4 tool's original literals (HEAD 73ed25f s4_hangar_hold.py:50-54, 190, 370, 434, 481,
    499) so the APPLIED record S4HOLD-20261007-102817 and its REVERT still resolve."""

    def test_names_4_are_original_literals(self):
        n = H.names(4)
        self.assertEqual(n["track"], "S4 Hangar Hold")
        self.assertEqual(n["bind_prefix"], "S4 Hangar Hold: ")
        self.assertEqual(n["record"], "s4_hangar_hold_record.json")
        self.assertEqual(n["mark"], "S4HOLD")
        self.assertEqual(n["backup_prefix"] + "R", "PreS4HangarHold-%s" % "R")
        self.assertEqual(n["out_prefix"] + "dry_R.json", "s4_hangar_hold_%s_%s.json" % ("dry", "R"))
        # control: another scene's names differ in every field
        n1 = H.names(1)
        self.assertTrue(all(n1[k] != n[k] for k in n), n1)

    def test_live_record_still_reverts(self):
        with open(os.path.join(HERE, H.names(4)["record"]), encoding="utf-8") as h:
            rec = json.load(h)
        self.assertTrue(rec["applied"])
        self.assertEqual(rec["run"], "S4HOLD-20261007-102817")
        self.assertNotIn("scene", rec)                    # predates the field ...
        self.assertEqual(H.record_scene(rec), 4)          # ... and still reads as S4
        self.assertNotEqual(H.record_scene(dict(rec, scene=1)), 4)   # control
        self.assertEqual(rec["plan"]["range"], [775, 4890])
        self.assertEqual(sorted(b["binding"] for b in rec["bindings"]),
                         ["S4 Hangar Lattice Fly", "S4 Hangar Roof Hinge", "S4 Hangar Root"])
        # its saved fold still passes the (now stricter) plan gate: active, 0, offset 0, rate 1, 775*960 ticks
        self.assertIsNone(refuses(H.plan_holds, rec["plan"]["fold"], PLAY, TPF, rec["plan"]["rise_end_tick"],
                                  movers()))

    def test_s4_plan_against_live_scene_rows(self):
        """S4's klara ADDITIVE Lattice Hold over [0, 4890] and its own applied hold tracks are not conflicts."""
        rows = [{"binding": "Klara Reveal - Lattice Hold: S4 Hangar Lattice Fly", "tracks": [
                    {"name": "Klara Reveal - Lattice Hold", "transform": True,
                     "sections": [{"range": [0, 4890], "blend": "ADDITIVE"}]},
                    {"name": "S4 Hangar Hold", "transform": True,
                     "sections": [{"range": [775, 4890], "blend": "ABSOLUTE"}]}]},
                {"binding": "S4 Hangar Hold: S4 Hangar Root", "tracks": [
                    {"name": "S4 Hangar Hold", "transform": True,
                     "sections": [{"range": [775, 4890], "blend": "ABSOLUTE"}]}]}]
        labels = ["S4 Hangar Roof Hinge", "S4 Hangar Lattice Fly", "S4 Hangar Root"]
        c, co = H.scene_conflicts(labels, rows, [775, 4890], "S4 Hangar Hold")
        self.assertEqual(c, [])
        self.assertEqual(len(co), 1)
        # control: under ANOTHER scene's track name, S4's own hold tracks would be conflicts
        self.assertEqual(len(H.scene_conflicts(labels, rows, [775, 4890], "S1 Hangar Hold")[0]), 2)


def scene_movers(n, tpf, root_z=0.0, fly_from=2900.0, fly_to=1700.0):
    """Root / Roof Hinge / Lattice Fly as hangar_build.py:498-501 keys them. Values SYNTHETIC except where noted."""
    P = "S%d" % n
    return [
        {"binding": P + " Hangar Root", "sections": [{"blend": "UNSET", "channels": chans(
            Location_Z={"keys": [], "default": root_z},
            Rotation_Y={"keys": [[0, -90.0], [500 * tpf, -90.0], [700 * tpf, 0.0]], "default": -90.0})}]},
        {"binding": P + " Hangar Roof Hinge", "sections": [{"blend": "UNSET", "channels": chans(
            Location_Z={"keys": [], "default": 3000.0},
            Rotation_Y={"keys": [[0, -90.0], [600 * tpf, -90.0], [740 * tpf, 0.0]], "default": -90.0})}]},
        {"binding": P + " Hangar Lattice Fly", "sections": [{"blend": "ABSOLUTE", "channels": chans(
            Location_Z={"keys": [[0, fly_from], [259 * tpf, fly_from], [379 * tpf, fly_to]], "default": fly_from})}]},
    ]


# [meas] S4HOLD DRY 102800 survey: S1 [0,6176) fold [0,775); S2 [0,2025) fold [0,775); S3 [0,6240) fold [0,744).
# Ticks/frame: 24000 tick resolution [inf, as S4's 960 @25 fps]; S3 6240 frames / 260 s = 24 fps -> 1000.
SCENE_FIX = {
    1: {"tpf": 960, "fold": [0, 775], "play": [0, 6176]},
    2: {"tpf": 960, "fold": [0, 775], "play": [0, 2025]},
    3: {"tpf": 1000, "fold": [0, 744], "play": [0, 6240]},
}


class PerScene(unittest.TestCase):
    def fold(self, n, **over):
        return dict({"range": SCENE_FIX[n]["fold"], "start_offset_tick": 0, "play_rate": 1.0, "active": True}, **over)

    def test_ranges_and_landed(self):
        want = {1: [775, 6176], 2: [775, 2025], 3: [744, 6240]}
        for n, fx in SCENE_FIX.items():
            tpf = fx["tpf"]
            p = H.plan_holds(self.fold(n), fx["play"], tpf, fx["fold"][1] * tpf,
                             scene_movers(n, tpf, root_z=-120.0 if n == 3 else 0.0))
            self.assertEqual(p["range"], want[n], n)
            v = {t["binding"]: t["values"] for t in p["targets"]}
            self.assertEqual(v["S%d Hangar Root" % n]["Rotation.Y"], 0.0, n)       # landed, not REST -90
            self.assertEqual(v["S%d Hangar Roof Hinge" % n]["Rotation.Y"], 0.0, n)
            self.assertEqual(v["S%d Hangar Lattice Fly" % n]["Location.Z"], 1700.0, n)
            self.assertEqual(len(p["targets"]), 3, n)

    def test_s3_hinge_below_zero_is_read_not_assumed(self):
        """S3 hinge_z -120 [decl hangar_s3_record.json hangar.hinge_z]: the held Root Z is the rise's value."""
        fx = SCENE_FIX[3]
        p = H.plan_holds(self.fold(3), fx["play"], 1000, 744000, scene_movers(3, 1000, root_z=-120.0))
        self.assertEqual(p["targets"][0]["values"]["Location.Z"], -120.0)
        # control: an S4-shaped Root (Z 0) gives a different hold - the value is data, not a constant
        p0 = H.plan_holds(self.fold(3), fx["play"], 1000, 744000, scene_movers(3, 1000, root_z=0.0))
        self.assertNotEqual(p0["targets"][0]["values"]["Location.Z"], -120.0)

    def test_s3_fold_must_be_its_own_rise(self):
        """S3 runs 24 fps: fold 744 x 1000 = 744000 = the rise. An S4-shaped fold (775) at 24 fps is not 1:1."""
        fx = SCENE_FIX[3]
        self.assertIsNone(refuses(H.plan_holds, self.fold(3), fx["play"], 1000, 744000, scene_movers(3, 1000)))
        self.assertIn("FOLD_NOT_WHOLE_RISE", refuses(H.plan_holds, self.fold(3, range=[0, 775]), fx["play"], 1000,
                                                      744000, scene_movers(3, 1000)))
        self.assertIn("FOLD_NOT_WHOLE_RISE", refuses(H.plan_holds, self.fold(3), fx["play"], 960, 744000,
                                                      scene_movers(3, 1000)))

    def test_refusals_per_scene(self):
        for n, fx in SCENE_FIX.items():
            tpf, rend = fx["tpf"], fx["fold"][1] * fx["tpf"]
            mv = scene_movers(n, tpf)
            self.assertIsNone(refuses(H.plan_holds, self.fold(n), fx["play"], tpf, rend, mv), n)      # control
            self.assertIn("FOLD_NOT_AT_ZERO", refuses(H.plan_holds, self.fold(n, range=[10, fx["fold"][1]]),
                                                      fx["play"], tpf, rend, mv), n)
            self.assertIn("FOLD_START_OFFSET", refuses(H.plan_holds, self.fold(n, start_offset_tick=tpf),
                                                       fx["play"], tpf, rend, mv), n)
            self.assertIn("FOLD_PLAY_RATE", refuses(H.plan_holds, self.fold(n, play_rate=0.5), fx["play"], tpf,
                                                    rend, mv), n)
            self.assertIn("FOLD_INACTIVE", refuses(H.plan_holds, self.fold(n, active=False), fx["play"], tpf,
                                                   rend, mv), n)
            self.assertIn("NOTHING_UNCOVERED", refuses(H.plan_holds, self.fold(n), fx["fold"], tpf, rend, mv), n)
            m = scene_movers(n, tpf)
            m[0]["sections"][0]["channels"]["Rotation.Y"]["keys"].append([rend + tpf, 5.0])
            self.assertIn("KEY_AFTER_RISE_END", refuses(H.plan_holds, self.fold(n), fx["play"], tpf, rend, m), n)

    def test_s6_inactive_fold_refused(self):
        """S6 fold is inactive [meas S4HOLD DRY 102800 survey]; validate_args refuses scene 6 as well."""
        f6 = {"range": [0, 775], "start_offset_tick": 0, "play_rate": 1.0, "active": False}
        self.assertIn("FOLD_INACTIVE", refuses(H.plan_holds, f6, [0, 5489], TPF, RISE_END, movers()))


class S1KlaraCoexistence(unittest.TestCase):
    """klara_reveal v3 in LS_DevScene_01: roof hidden [269, 5832] on 'S1 Hangar Roof' (visibility), ADDITIVE
    'Klara Reveal - Lattice Hold' on the Lattice Fly [record klara_reveal_record_S1.json lattice_cancel/hide;
    klara_reveal.py:2346-2353]. Track/section shapes here are SYNTHETIC from those."""
    LABELS = ["S1 Hangar Root", "S1 Hangar Roof Hinge", "S1 Hangar Lattice Fly"]
    HOLD = [775, 6176]

    def rows(self):
        return [
            {"binding": "S1 Hangar Roof", "tracks": [
                {"name": "Klara Reveal - Roof Hidden", "transform": False,
                 "sections": [{"range": [269, 5832], "blend": None}]}]},
            {"binding": "Klara Reveal - Lattice Hold: S1 Hangar Lattice Fly", "tracks": [
                {"name": "Klara Reveal - Lattice Hold", "transform": True,
                 "sections": [{"range": [0, 6176], "blend": "ADDITIVE"}]}]},
            {"binding": "S1 Hangar Roof Hinge", "tracks": [
                {"name": "Visibility", "transform": False, "sections": [{"range": [0, 6176], "blend": None}]}]},
        ]

    def test_reveal_is_not_fought(self):
        c, co = H.scene_conflicts(self.LABELS, self.rows(), self.HOLD, "S1 Hangar Hold")
        self.assertEqual(c, [])
        self.assertTrue(any("Lattice Hold" in x for x in co))
        self.assertFalse(any(x.startswith("S1 Hangar Roof/") for x in co))   # the Roof is not a mover: untouched
        self.assertNotIn("S1 Hangar Roof", self.LABELS)

    def test_absolute_overlap_is_refused(self):
        r = self.rows()
        r.append({"binding": "S1 Hangar Root", "tracks": [{"name": "Transform", "transform": True,
                                                           "sections": [{"range": [5000, 6000], "blend": "ABSOLUTE"}]}]})
        self.assertEqual(len(H.scene_conflicts(self.LABELS, r, self.HOLD, "S1 Hangar Hold")[0]), 1)
        r[-1]["tracks"][0]["sections"][0]["blend"] = None           # UNSET counts as absolute
        self.assertEqual(len(H.scene_conflicts(self.LABELS, r, self.HOLD, "S1 Hangar Hold")[0]), 1)
        r[-1]["tracks"][0]["sections"][0]["range"] = [None, None]   # open both ends overlaps
        self.assertEqual(len(H.scene_conflicts(self.LABELS, r, self.HOLD, "S1 Hangar Hold")[0]), 1)
        # controls: ending exactly at the fold end, or additive, does not overlap/fight
        r[-1]["tracks"][0]["sections"][0].update(range=[0, 775], blend="ABSOLUTE")
        self.assertEqual(H.scene_conflicts(self.LABELS, r, self.HOLD, "S1 Hangar Hold")[0], [])
        r[-1]["tracks"][0]["sections"][0].update(range=[0, 6176], blend="ADDITIVE")
        self.assertEqual(H.scene_conflicts(self.LABELS, r, self.HOLD, "S1 Hangar Hold")[0], [])

    def test_name_match_is_exact_suffix(self):
        """'S1 Hangar Root' must not match 'S1 Hangar Rooted Thing', 'XS1 Hangar Root' or 'S2 Hangar Root'."""
        r = [{"binding": n, "tracks": [{"name": "T", "transform": True,
                                        "sections": [{"range": [0, 9000], "blend": "ABSOLUTE"}]}]}
             for n in ("S1 Hangar Rooted Thing", "XS1 Hangar Root", "S2 Hangar Root")]
        self.assertEqual(H.scene_conflicts(self.LABELS, r, self.HOLD, "S1 Hangar Hold")[0], [])
        r.append({"binding": "Someone: S1 Hangar Root", "tracks": r[0]["tracks"]})                  # control
        self.assertEqual(len(H.scene_conflicts(self.LABELS, r, self.HOLD, "S1 Hangar Hold")[0]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=1)
