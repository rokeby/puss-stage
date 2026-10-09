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


# ---------------------------------------------------------------------------------------------------------------------
# NON-TRANSFORM ("hold": "FLOAT") extension, 7 Oct evening. First: the transform path is bit-identical to 4e1e703.
# ---------------------------------------------------------------------------------------------------------------------
import ast         # noqa: E402
import hashlib     # noqa: E402
import subprocess  # noqa: E402

FROZEN_COMMIT = "4e1e7035e16cec555d7482888030e1edd9213655"      # last commit of s4_hangar_hold.py before the extension
# sha256 of transform_fingerprint() computed with the UNEDITED module at FROZEN_COMMIT (7 Oct, before any edit).
FROZEN_TRANSFORM_SHA = "e40026d86a3decdb6c029c4c77ad5289b569ff51f0c183ba255e84594ed215eb"


def transform_fingerprint(mod):
    """Every transform-path pure output on fixed inputs (the fixtures above), serialised. Frozen above."""
    out = {}
    out["plan_s4"] = mod.plan_holds(FOLD, PLAY, TPF, RISE_END, movers())
    for n, fx in SCENE_FIX.items():
        f = {"range": fx["fold"], "start_offset_tick": 0, "play_rate": 1.0, "active": True}
        out["plan_s%d" % n] = mod.plan_holds(f, fx["play"], fx["tpf"], fx["fold"][1] * fx["tpf"],
                                             scene_movers(n, fx["tpf"], root_z=-120.0 if n == 3 else 0.0))
    ref = []
    m = movers(); m[0]["sections"][0]["channels"]["Rotation.Y"]["keys"].append([800 * TPF, 5.0])
    for args in [(dict(FOLD, range=[5, 775]), PLAY, TPF, RISE_END, movers()),
                 (FOLD, [0, 775], TPF, RISE_END, movers()), (FOLD, PLAY, TPF, RISE_END, m),
                 (FOLD, PLAY, TPF, RISE_END + 1, movers())]:
        try:
            mod.plan_holds(*args); ref.append(None)
        except mod.PlanError as e:
            ref.append(str(e))
    out["refusals"] = ref
    rows = S1KlaraCoexistence().rows() + [{"binding": "S1 Hangar Root", "tracks": [
        {"name": "Transform", "transform": True, "sections": [{"range": [5000, 6000], "blend": "ABSOLUTE"}]}]}]
    out["conflicts"] = mod.scene_conflicts(S1KlaraCoexistence.LABELS, rows, [775, 6176], "S1 Hangar Hold")
    out["names"] = [mod.names(n) for n in (1, 2, 3, 4)]
    out["survey"] = [mod.survey_row(4, PLAY, [{"range": [0, 775]}], 25.0), mod.survey_row(6, PLAY, [], 25.0)]
    a = {"mode": "APPLY", "scene": 3, "confirm": "APPLY S3HOLD", "completion": "KEEP_STATE", "decided_by": "x"}
    out["args"] = [mod.validate_args(a), mod.validate_args(dict(a, confirm="APPLY S4HOLD")),
                   mod.validate_args(dict(a, scene=6))]
    vals = {c: float(i) for i, c in enumerate(mod.CHANNELS)}
    out["readback"] = mod.readback_diff({"range": [1, 2], "completion": "KEEP_STATE", "values": vals},
                                        {"range": [1, 3], "completion": "KEEP_STATE",
                                         "values": dict(vals, **{"Rotation.Y": 9.0}), "n_keys": 2})
    out["landed"] = [mod.landed_value([[5, 1.0], [1, 2.0]], None), mod.landed_value([], 3.5)]
    out["channel_base"] = mod.channel_base("Location.Y_183")
    out["record_scene"] = [mod.record_scene({}), mod.record_scene({"scene": 2})]
    return hashlib.sha256(json.dumps(out, sort_keys=True).encode("utf-8")).hexdigest()


def _frozen_source():
    try:
        return subprocess.run(["git", "show", FROZEN_COMMIT + ":Saved/CodexConductor/s4_hangar_hold.py"], cwd=HERE,
                              capture_output=True, check=True).stdout.decode("utf-8")
    except Exception:  # noqa: BLE001
        return None


def _segments(src):
    t = ast.parse(src)
    funcs = {n.name: ast.get_source_segment(src, n) for n in t.body if isinstance(n, ast.FunctionDef)}
    consts = {ast.get_source_segment(src, n) for n in t.body if isinstance(n, (ast.Assign, ast.ClassDef))}
    return funcs, consts


class TransformBitIdentical(unittest.TestCase):
    def test_frozen_fingerprint(self):
        self.assertEqual(transform_fingerprint(H), FROZEN_TRANSFORM_SHA)

    def test_fingerprint_can_fail(self):
        """control: a one-value change in a transform output changes the hash."""
        orig = H.landed_value
        try:
            H.landed_value = lambda keys, default: orig(keys, default) + (1e-9 if keys else 0.0)
            self.assertNotEqual(transform_fingerprint(H), FROZEN_TRANSFORM_SHA)
        finally:
            H.landed_value = orig

    def test_source_identical_to_frozen_commit(self):
        old = _frozen_source()
        if old is None:
            self.skipTest("git show %s unavailable" % FROZEN_COMMIT)
        with open(os.path.join(HERE, "s4_hangar_hold.py"), encoding="utf-8") as h:
            new = h.read()
        of, oc = _segments(old)
        nf, nc = _segments(new)
        self.assertEqual(len(of), 33)                                  # 4e1e703 has 33 top-level functions
        for name, seg in of.items():
            if name == "main":
                continue
            self.assertEqual(nf.get(name), seg, name)                       # every old function, verbatim
        self.assertEqual(nf["main_transform"].split("\n", 1)[1], of["main"].split("\n", 1)[1])   # old main body
        self.assertTrue(oc <= nc, oc - nc)                                   # every old constant/class, verbatim
        # control: the new dispatcher is NOT the old main, and a changed function would be caught
        self.assertNotEqual(nf["main"], of["main"])
        self.assertNotEqual(nf["plan_nontransform"], of.get("plan_holds"))


# --- float fixtures: S3 numbers [meas scene_exposure_weight_read.json; hangar_light_keys_probe.json]; tick 24000/s
SEC = 24000
F3 = {"tpf": 1000, "rise_end": 744000, "hold": [744, 6240]}
CONST = "RichCurveExtrapolation.RCCE_CONSTANT"


def frow(binding, keys, parent=None, prop="Intensity", default=None, rng=(0, 930000), extrap=CONST, cls=None,
         blend="UNSET", active=True, nsec=1, nch=1):
    sec = {"range_tick": list(rng), "active": active, "blend": blend, "completion": "RESTORE_STATE",
           "channels": [{"keys": [list(k) for k in keys], "default": default, "post_extrap": extrap}
                        for _ in range(nch)]}
    return {"binding": binding, "parent": parent, "binding_guid": "G-" + binding + (parent or ""),
            "track_class": cls or "MovieSceneFloatTrack", "property_name": prop, "property_path": prop,
            "sections": [copy.deepcopy(sec) for _ in range(nsec)]}


def s3_rows():
    return [
        frow("S3 Hangar Pinned Exposure", [[-176 * 1000, 0.0], [124 * 1000, 1.0]], prop="BlendWeight"),
        frow("LightComponent0", [[-140800, 0.0], [99200, 20.0]], parent="S3 Lattice Glow 1-1"),
        frow("LightComponent0", [[0, 0.0], [240000, 0.0], [252000, 10000.0]], parent="S3 Uplight 1"),
        frow("LightComponent0", [], parent="S3 Practical Unkeyed", default=7.5),
        {"binding": "P03 End Drape (stand-in)", "parent": None, "binding_guid": "G-drape",
         "track_class": "MovieSceneGeometryCacheTrack", "property_name": None, "property_path": None,
         "sections": [{"range_tick": [-168000, 96000], "active": True, "blend": None, "completion": "KEEP_STATE",
                       "params": {"start_frame_offset": 23200, "end_frame_offset": 0, "play_rate": 1.0,
                                  "reverse": False}}]},
        frow("Shore02_F52 Clam", [[0, True], [200000, False]], prop="bHiddenInGame", extrap=None,
             cls="MovieSceneVisibilityTrack"),
        frow("Some Light", [[0, 1.0]], prop="LightColor", cls="MovieSceneColorTrack"),
    ]


def plan3(rows=None, kinds=("float",)):
    return H.plan_nontransform(F3["hold"], F3["rise_end"], s3_rows() if rows is None else rows, list(kinds))


class FloatPlan(unittest.TestCase):
    def test_values_after_last_key(self):
        p = plan3()
        v = {t["id"]: t for t in p["targets"]}
        self.assertEqual(p["range"], [744, 6240])
        self.assertEqual(len(p["targets"]), 4)
        self.assertEqual(p["refused"], [])
        self.assertEqual(v["-/S3 Hangar Pinned Exposure/BlendWeight"]["value"], 1.0)       # the S3 white fault
        self.assertEqual(v["S3 Lattice Glow 1-1/LightComponent0/Intensity"]["value"], 20.0)
        self.assertEqual(v["S3 Uplight 1/LightComponent0/Intensity"]["value"], 10000.0)
        u = v["S3 Practical Unkeyed/LightComponent0/Intensity"]
        self.assertEqual((u["value"], u["source"], u["last_key_tick"]), (7.5, "default", None))   # no keys -> default
        # control: the FIRST key (the pre-rise 0.0) would have been the white-out value
        self.assertNotEqual(v["-/S3 Hangar Pinned Exposure/BlendWeight"]["value"], 0.0)

    def test_unsorted_keys_and_negative_last_key(self):
        r = s3_rows()[:1]
        r[0]["sections"][0]["channels"][0]["keys"].reverse()
        self.assertEqual(plan3(r)["targets"][0]["value"], 1.0)
        r = [frow("Pre", [[-50000, 0.0], [-10000, 3.0]])]                 # all keys before the fold: held, flagged
        t = plan3(r)["targets"][0]
        self.assertEqual((t["value"], t["last_key_before_fold"]), (3.0, True))

    def test_last_key_boundary(self):
        ok = [frow("L", [[0, 0.0], [F3["rise_end"], 5.0]])]
        self.assertEqual(plan3(ok)["targets"][0]["value"], 5.0)              # control: AT the fold end is inside
        late = [frow("L", [[0, 0.0], [F3["rise_end"] + 1, 5.0]])]
        p = plan3(late)
        self.assertEqual(p["targets"], [])
        self.assertIn("LAST_KEY_AFTER_FOLD_END", p["refused"][0]["reason"])
        self.assertIn("REFUSED_TRACKS|1", H.float_apply_gate(dict(p, conflicts=[], identity_mismatch=[])))

    def test_refusals(self):
        cases = {
            "POST_EXTRAP_NOT_CONSTANT": frow("A", [[0, 1.0]], extrap="RichCurveExtrapolation.RCCE_LINEAR"),
            "POST_EXTRAP_UNREAD": frow("A", [[0, 1.0]], extrap=None),
            "SECTION_ENDS_BEFORE_FOLD_END": frow("A", [[0, 1.0]], rng=(0, 700000)),
            "SECTION_STARTS_AFTER_FOLD_END": frow("A", [[0, 1.0]], rng=(744000, None)),
            "SECTIONS|2": frow("A", [[0, 1.0]], nsec=2),
            "CHANNELS|2": frow("A", [[0, 1.0]], nch=2),
            "BLEND_NOT_ABSOLUTE|ADDITIVE": frow("A", [[0, 1.0]], blend="ADDITIVE"),
            "SECTION_INACTIVE": frow("A", [[0, 1.0]], active=False),
            "CHANNEL_UNKEYED_NO_DEFAULT": frow("A", [], default=None),
            "NO_PROPERTY_PATH": frow("A", [[0, 1.0]], prop=None),
        }
        for want, row in cases.items():
            p = plan3([row])
            self.assertEqual(p["targets"], [], want)
            self.assertIn(want, p["refused"][0]["reason"], want)
        # open-ended sections cover the fold end; ABSOLUTE is accepted (controls)
        self.assertEqual(len(plan3([frow("A", [[0, 1.0]], rng=(None, None), blend="ABSOLUTE")])["targets"]), 1)
        d = plan3([frow("A", [[0, 1.0]]), frow("A", [[0, 2.0]])])
        self.assertEqual((len(d["targets"]), d["refused"][0]["reason"]), (1, "DUPLICATE_TARGET"))
        with self.assertRaises(H.PlanError):
            plan3(kinds=("float", "colour"))
        with self.assertRaises(H.PlanError):
            plan3(kinds=())

    def test_listing_gc_visibility_other(self):
        p = plan3()
        lst = {x["id"]: x for x in p["listed"]}
        gc = lst["-/P03 End Drape (stand-in)/MovieSceneGeometryCacheTrack"]
        self.assertEqual(gc["kind"], "geometry_cache")
        self.assertTrue(gc["meaning"].startswith("NOT HELD"))
        vis = lst["-/Shore02_F52 Clam/bHiddenInGame"]
        self.assertIn("would hold False", vis["meaning"])
        self.assertIn("UNSUPPORTED", lst["-/Some Light/LightColor"]["meaning"])
        self.assertFalse(any(t["kind"] == "geometry_cache" for t in p["targets"]))   # caches are never held
        # opt-in: visibility is held with its last value; GC still listed
        q = plan3(kinds=("float", "visibility"))
        vt = [t for t in q["targets"] if t["kind"] == "visibility"]
        self.assertEqual((len(vt), vt[0]["value"]), (1, False))
        self.assertTrue(H.visibility_channel_value(vt[0]))  # legacy hidden=False -> new visible=True
        self.assertFalse(H.visibility_channel_value(dict(vt[0], value=True)))
        self.assertTrue(any(x["kind"] == "geometry_cache" for x in q["listed"]))
        with self.assertRaises(H.PlanError):
            plan3(kinds=("geometry_cache",))

    def test_norm_extrap(self):
        for v in ("RichCurveExtrapolation.RCCE_CONSTANT", "<RichCurveExtrapolation.RCCE_CONSTANT: 3>", "RCCE_Constant"):
            self.assertEqual(H.norm_extrap(v), "RCCE_CONSTANT", v)
        self.assertEqual(H.norm_extrap("RCCE_Cycle"), "RCCE_CYCLE")
        self.assertIsNone(H.norm_extrap(None))

    def test_gate(self):
        p = dict(plan3(), conflicts=[], identity_mismatch=[])
        self.assertEqual(H.float_apply_gate(p), [])                                       # control
        self.assertIn("SCENE_CONFLICTS|1", H.float_apply_gate(dict(p, conflicts=["x"])))
        self.assertIn("IDENTITY_MISMATCH|1", H.float_apply_gate(dict(p, identity_mismatch=["x"])))
        self.assertIn("NO_TARGETS", H.float_apply_gate(dict(p, targets=[])))


class FloatSceneConflicts(unittest.TestCase):
    OWN = "S3 Hangar Float Hold"

    def targets(self):
        return plan3()["targets"]

    def test_conflicts_and_coexisting(self):
        rows = [
            {"binding": "LightComponent0", "parent": "S3 Lattice Glow 1-1", "tracks": [
                {"name": "Intensity", "class": "MovieSceneFloatTrack", "property_path": "Intensity",
                 "sections": [{"range": [3000, 4000]}]},
                {"name": "LightColor", "class": "MovieSceneColorTrack", "property_path": "LightColor",
                 "sections": [{"range": [0, 6240]}]}]},
            {"binding": "Wave: S3 Hangar Pinned Exposure", "parent": None, "tracks": [
                {"name": "BlendWeight", "class": "MovieSceneFloatTrack", "property_path": "BlendWeight",
                 "sections": [{"range": [0, 744]}]}]},                     # ends AT the fold end: no overlap
            {"binding": "LightComponent0", "parent": "S3 Somebody Else", "tracks": [
                {"name": "Intensity", "class": "MovieSceneFloatTrack", "property_path": "Intensity",
                 "sections": [{"range": [0, 9000]}]}]},                    # other parent: not ours
        ]
        c, co = H.float_scene_conflicts(self.targets(), rows, [744, 6240], self.OWN)
        self.assertEqual(len(c), 1)
        self.assertIn("S3 Lattice Glow 1-1/LightComponent0/Intensity", c[0])
        self.assertEqual(len(co), 2)                                          # colour + the non-overlapping weight
        rows[1]["tracks"][0]["sections"][0]["range"] = [0, 745]               # control: one frame of overlap
        self.assertEqual(len(H.float_scene_conflicts(self.targets(), rows, [744, 6240], self.OWN)[0]), 2)

    def test_own_leftover_is_conflict(self):
        rows = [{"binding": "S3 Hangar Float Hold: S3 Hangar Pinned Exposure", "parent": None, "tracks": [
            {"name": self.OWN, "class": "MovieSceneFloatTrack", "property_path": "BlendWeight",
             "sections": [{"range": [744, 6240]}]}]}]
        c, _ = H.float_scene_conflicts(self.targets(), rows, [744, 6240], self.OWN)
        self.assertTrue(c and c[0].startswith("OWN_TRACK_ALREADY_PRESENT"))
        # control: the transform hold's tracks on the movers never match a float target
        rows = [{"binding": "S3 Hangar Hold: S3 Hangar Root", "parent": None, "tracks": [
            {"name": "S3 Hangar Hold", "class": "MovieScene3DTransformTrack", "property_path": "Transform",
             "sections": [{"range": [744, 6240]}]}]}]
        self.assertEqual(H.float_scene_conflicts(self.targets(), rows, [744, 6240], self.OWN), ([], []))


class FloatSeparateFromTransform(unittest.TestCase):
    def test_names_disjoint(self):
        for n in H.SCENES:
            f, t = H.fnames(n), H.names(n)
            self.assertTrue(all(f[k] != t[k] for k in t), n)
            # the transform REVERT's leftover test (startswith bind_prefix; track name) never sees float bindings
            self.assertFalse((f["bind_prefix"] + "X").startswith(t["bind_prefix"]), n)
            self.assertFalse((t["bind_prefix"] + "X").startswith(f["bind_prefix"]), n)
            self.assertNotEqual(f["track"], t["track"])
        self.assertEqual(H.fnames(3)["record"], "s3_hangar_float_hold_record.json")
        self.assertFalse(os.path.exists(os.path.join(HERE, H.fnames(3)["record"])))   # nothing applied yet

    def test_args(self):
        a = {"mode": "APPLY", "scene": 3, "hold": "FLOAT", "confirm": "APPLY S3FLOATHOLD", "completion": "KEEP_STATE",
             "decided_by": "x"}
        self.assertEqual(H.validate_float_args(a), [])
        self.assertIn("CONFIRM", H.validate_float_args(dict(a, confirm="APPLY S3HOLD")))       # transform confirm
        self.assertIn("CONFIRM", H.validate_args(dict(a, confirm="APPLY S3FLOATHOLD")))        # and vice versa
        self.assertIn("CONFIRM", H.validate_float_args(dict(a, confirm="APPLY S4FLOATHOLD")))
        self.assertEqual(H.validate_float_args(dict(a, mode="REVERT", confirm="REVERT S3FLOATHOLD")), [])
        self.assertIn("DECIDED_BY", H.validate_float_args(dict(a, decided_by=" ")))
        self.assertIn("HOLD_KINDS", H.validate_float_args(dict(a, hold_kinds=["geometry_cache"])))
        self.assertIn("HOLD_KINDS", H.validate_float_args(dict(a, hold_kinds=[])))
        self.assertEqual(H.validate_float_args(dict(a, hold_kinds=["float", "visibility"])), [])
        pr = {"mode": "PIEPROBE", "scene": 4, "completion": "KEEP_STATE"}
        self.assertIn("PROBE_PHASE", H.validate_float_args(pr))
        self.assertIn("MASTER_FRAME", H.validate_float_args(dict(pr, probe_phase="scrub")))
        self.assertEqual(H.validate_float_args(dict(pr, probe_phase="scrub", master_frame=29226625)), [])
        self.assertEqual(H.validate_float_args(dict(pr, probe_phase="read")), [])
        self.assertIn("SCENE_NOT_IN_(1, 2, 3, 4)", H.validate_float_args(dict(a, scene=5)))
        with open(os.path.join(HERE, "s4_hangar_hold_args.json"), encoding="utf-8") as h:
            shipped = json.load(h)
        self.assertEqual((shipped["mode"], shipped["hold"]), ("DRY", "FLOAT"))
        self.assertEqual(H.validate_float_args(shipped), [])

    def test_dispatch(self):
        calls = []
        of, ot = H.main_float, H.main_transform
        try:
            H.main_float = lambda a: calls.append("float")
            H.main_transform = lambda a: calls.append("transform")
            H.main({"hold": "FLOAT"}); H.main({"hold": "float"}); H.main({}); H.main({"hold": "TRANSFORM"})
        finally:
            H.main_float, H.main_transform = of, ot
        self.assertEqual(calls, ["float", "float", "transform", "transform"])


class FloatReadbackAndRevert(unittest.TestCase):
    def want(self, **o):
        return dict({"range": [744, 6240], "completion": "KEEP_STATE", "value": 10000.0, "kind": "float",
                     "property_path": "Intensity", "display": "S3 Hangar Float Hold"}, **o)

    def got(self, **o):
        return dict({"range": [744, 6240], "completion": "KEEP_STATE", "value": 10000.0004, "kind": "float",
                     "property_path": "Intensity", "display": "S3 Hangar Float Hold", "n_keys": 0,
                     "blend": "ABSOLUTE"}, **o)

    def test_diff(self):
        self.assertEqual(H.float_readback_diff(self.want(), self.got()), [])          # float32 tolerance
        for bad in (dict(range=[744, 6239]), dict(completion="RESTORE_STATE"), dict(value=10000.5), dict(n_keys=1),
                    dict(blend="ADDITIVE"), dict(display="Intensity"), dict(property_path="BlendWeight"),
                    dict(value=None)):
            self.assertTrue(H.float_readback_diff(self.want(), self.got(**bad)), bad)
        vw = self.want(kind="visibility", value=True, property_path="bHidden")
        self.assertEqual(H.float_readback_diff(vw, self.got(kind="visibility", value=True, blend=None,
                                                            property_path="bHidden")), [])
        self.assertTrue(H.float_readback_diff(vw, self.got(kind="visibility", value=False,
                                                           property_path="bHidden")))

    def test_revert_order_children_first(self):
        created = [{"guid": "P1", "child": False}, {"guid": "C1", "child": True}, {"guid": "A", "child": False},
                   {"guid": "C2", "child": True}]
        self.assertEqual(H.revert_order(created), ["C1", "C2", "P1", "A"])

    def test_snake(self):
        self.assertEqual([H._snake(x) for x in ("BlendWeight", "Intensity", "bHiddenInGame")],
                         ["blend_weight", "intensity", "hidden_in_game"])


class LiveInventory(unittest.TestCase):
    """[meas] the 7 Oct transform DRY/APPLY outputs list every non-transform rise track; every class must classify."""
    FILES = {1: "s1_hangar_hold_dry_S1HOLD-20261007-103941.json", 2: "s2_hangar_hold_dry_S2HOLD-20261007-103951.json",
             3: "s3_hangar_hold_dry_S3HOLD-20261007-104002.json", 4: "s4_hangar_hold_dry_S4HOLD-20261007-102800.json"}
    WANT = {1: {"float": 42, "geometry_cache": 1}, 2: {"float": 42, "geometry_cache": 1},
            3: {"float": 50, "visibility": 9, "geometry_cache": 1}, 4: {"float": 42, "geometry_cache": 1}}

    def test_inventory(self):
        for n, f in self.FILES.items():
            with open(os.path.join(HERE, f), encoding="utf-8") as h:
                tracks = json.load(h)["plan"]["not_held_rise_tracks"]
            got = {}
            for x in tracks:
                k = H.track_kind(x.rsplit("/", 1)[1])
                got[k] = got.get(k, 0) + 1
            self.assertEqual(got, self.WANT[n], n)
            self.assertNotIn("other", got, n)
            print("INVENTORY S%d %s" % (n, got))


if __name__ == "__main__":
    unittest.main(verbosity=1)
