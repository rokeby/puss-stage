"""Offline +/- harness for Job 106.  System Python only; never imports Unreal."""
import copy
import importlib.util
import json
import os
import sys
import tempfile


HERE = os.path.dirname(os.path.abspath(__file__))
RZSWAP = os.path.normpath(os.path.join(HERE, "..", "rzswap"))
TOPPLE = os.path.normpath(os.path.join(HERE, "..", "topple", "topple_core.py"))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = load("p02tf_core_test", os.path.join(HERE, "p02_top_facing_core.py"))
app = load("p02tf_app_test", os.path.join(HERE, "p02_top_facing.py"))
tc = load("p02tf_tc_test", TOPPLE)
RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append({"check": name, "pass": bool(condition), "detail": str(detail)[:400]})
    print("%s  %s%s" % ("PASS" if condition else "FAIL", name, "" if condition else " -- " + str(detail)[:400]))


def expect_stop(name, fn, token):
    try:
        fn()
    except core.PlanError as exc:
        check(name, token in str(exc), exc)
        return
    check(name, False, "did not stop")


def panel_text(i, side, policy="AutoByRole", flip=False):
    mesh = "/Game/Test/SM_P02_%02d_%s" % (i + 1, "C" if side == "T" else side)
    return ('(Mesh="%s.%s",MaterialOverrides=,LocalTransform=(Rotation=(X=0.000000,Y=0.000000,Z=1.000000,W=0.000000),'
            'Translation=(X=0.000000,Y=0.000000,Z=750.000000),Scale3D=(X=0.425959,Y=0.600000,Z=0.425959)),'
            'FacingPolicy=%s,bFlipImageHorizontally=%s,bCastShadow=True,bVisibleInMainPass=True,Collision=NoCollision)') % (
                mesh, mesh.rsplit("/", 1)[-1], policy, "True" if flip else "False")


def cue_text(i, top_policy="AutoByRole", top_flip=False):
    return ("(CueGuid=%032X,Type=WingPair,Label=P02 Wing %03d,bEnabled=True,WingPair=(Left=%s,Right=%s,"
            "bHasTop=True,Top=%s,IntervalToNext=(Value=48000),GapToNextCm=500.000000,"
            "Mechanism=(Kind=Slide,PlaybackMode=ContinuousLoop),LocalOverrideMask=0,Attachments=))") % (
                i + 1, i + 1, panel_text(i, "L"), panel_text(i, "R"), panel_text(i, "T", top_policy, top_flip))


def policy_from_text(cue):
    return core.policy_name(tc.get_field(core.panel_text(tc, cue), "FacingPolicy"))


class FakeOps:
    def __init__(self):
        self.texts = [cue_text(i) for i in range(core.EXPECTED_TOPS)] + [cue_text(90).replace("P02 Wing", "P03 Control")]
        self.pristine = None
        self.dirty = copy.deepcopy(app.CLEAN)
        self.logs, self.errors, self.events, self.backups = [], [], [], []
        self.fault = None
        self.pie = False

    def log(self, message):
        self.logs.append(message)

    def log_error(self, message):
        self.errors.append(message)

    def guard_context(self):
        if self.pie:
            raise core.PlanError("PIE_OR_SIE_ACTIVE")

    def census(self):
        return copy.deepcopy(self.dirty)

    def zz_actors(self):
        return ["ZZ_Bad"] if self.fault == "zz" else []

    def cue_texts(self):
        return list(self.texts)

    def settings_texts(self):
        return ["(PassageGuid=%s,Label=P02)" % core.PASSAGES["P02"]["guid"]]

    def segments(self):
        return [["P02", 0, 1000]]

    def _guid(self, i):
        return "%032X" % (i + 1)

    def _plain(self, i, side):
        text = core.panel_text(tc, self.texts[i], side)
        return {"mesh": tc.get_field(text, "Mesh").strip('"').split(".", 1)[0], "material_overrides": [],
                "local_transform": {"location": [0.0, 0.0, 750.0], "rotation": [0.0, 0.0, 180.0],
                                    "scale": [0.425959, 0.6, 0.425959]},
                "facing_policy": policy_from_text(self.texts[i]) if side == "T" else core.AUTO,
                "flip_image_horizontally": tc.get_field(text, "bFlipImageHorizontally") == "True"}

    def measure(self, passage, candidates):
        rows = []
        for i, cue in enumerate(self.texts[:core.EXPECTED_TOPS]):
            sides = {}
            for side in ("L", "R", "T"):
                sign = -1 if side != "T" or policy_from_text(cue) == core.ROTATE else 1
                if self.fault == "top_sign_does_not_flip" and side == "T":
                    sign = 1
                faces = {"front_s_cm": i * 500.0 + (10.0 if sign > 0 else 0.0),
                         "back_s_cm": i * 500.0 + (0.0 if sign > 0 else 10.0)}
                sides[side] = {"panel": self._plain(i, side), "route_faces_cm": faces}
            rows.append({"ordinal": i, "cue_guid": self._guid(i), "label": "P02 Wing %03d" % (i + 1),
                         "show_index": i, "has_top": True, "text_sha": core.sha(cue), "sides": sides})
        return {"passage": passage, "passage_guid": core.PASSAGES[passage]["guid"],
                "materialized_count": len(rows), "settings": {"label": "P02", "first_cue_guid": self._guid(0),
                "last_cue_guid": self._guid(len(rows) - 1)}, "rows": rows}

    def live_panels(self, keys):
        return {key: self._plain(int(key.split("|")[0], 16) - 1, "T") for key in keys}

    def write_top_policies(self, policies):
        self.pristine = list(self.texts)
        for key, policy in policies.items():
            i = int(key.split("|")[0], 16) - 1
            top = core.panel_text(tc, self.texts[i])
            value = "Rotate180AroundUp" if policy == core.ROTATE else "AutoByRole"
            top = tc.replace_field(top, "FacingPolicy", value)
            if self.fault == "image_flip":
                top = tc.replace_field(top, "bFlipImageHorizontally", "True")
            wp = tc.get_field(self.texts[i], "WingPair")
            self.texts[i] = tc.replace_field(self.texts[i], "WingPair", tc.replace_field(wp, "Top", top))
        if self.fault == "other_passage":
            self.texts[-1] = self.texts[-1].replace("GapToNextCm=500.000000", "GapToNextCm=501.000000")
        self.dirty["content"] = [core.SHOW_PATH]
        self.events.append(("write", len(policies)))

    def restore_pristine(self):
        if self.pristine is None:
            return False
        self.texts = list(self.pristine)
        return True

    def materialize(self, passage):
        self.events.append(("materialize", passage))
        if self.fault == "materialize_false":
            return False
        self.dirty["maps"] = [core.WORLD_PATH]
        if self.fault == "foreign_dirty":
            self.dirty["content"].append("/Game/Other/Dirty")
        return True

    def materialized_count(self, passage):
        return core.EXPECTED_TOPS

    def backup(self, name):
        self.backups.append(name)
        return "Backups/" + name, ["show", "level"]

    def save_show(self):
        self.events.append(("save", "show"))
        self.dirty["content"] = [x for x in self.dirty["content"] if x != core.SHOW_PATH]
        return True

    def save_level(self):
        self.events.append(("save", "level"))
        self.dirty["maps"] = []
        return True


def main():
    # The supplied live DRY is the offline acceptance fixture.
    evidence_path = os.path.normpath(os.path.join(HERE, "..", "rzswap", "rzswap_dry_P02_RZSW-20261009-194606.json"))
    evidence = json.load(open(evidence_path, encoding="utf-8"))
    dry_evidence = core.make_dry(evidence, "RZSW-20261009-194606")
    check("E1 measured-record fixture: exactly 23 P02 Top targets", dry_evidence["target_count"] == 23)
    check("E2 measured-record fixture: 23/23 Top signs oppose 23/23 L/R signs",
          all(t["before_sign"] == 1 and t["lr_signs"] == {"L": -1, "R": -1} for t in dry_evidence["targets"]))
    check("E3 declaration control: no image flip and authored transforms retained in every planned row",
          all(not t["flip_image_horizontally"] and t["local_transform"] for t in dry_evidence["targets"]))

    # Pure +/- controls.
    fake = FakeOps()
    dry = core.make_dry(fake.measure("P02", {}), "TEST-DRY")
    check("P1 POS synthetic DRY passes all 23", dry["target_count"] == 23 and dry["status"] == "PASS")
    bad_count = fake.measure("P02", {}); bad_count["rows"].pop()
    expect_stop("N1 NEG 22 rows refused", lambda: core.make_dry(bad_count, "BAD"), "P02_ROW_COUNT")
    bad_flip = fake.measure("P02", {}); bad_flip["rows"][0]["sides"]["T"]["panel"]["flip_image_horizontally"] = True
    expect_stop("N2 NEG pre-existing Top image flip refused", lambda: core.make_dry(bad_flip, "BAD"), "TOP_IMAGE_FLIP_TRUE")
    bad_policy = fake.measure("P02", {}); bad_policy["rows"][0]["sides"]["T"]["panel"]["facing_policy"] = core.ROTATE
    expect_stop("N3 NEG non-AUTO Top refused", lambda: core.make_dry(bad_policy, "BAD"), "TOP_POLICY_NOT_AUTO")
    bad_yaw = fake.measure("P02", {}); bad_yaw["rows"][0]["sides"]["T"]["panel"]["local_transform"]["rotation"][2] = 0.0
    expect_stop("N4 NEG Top without approved local yaw 180 refused", lambda: core.make_dry(bad_yaw, "BAD"), "TOP_LOCAL_YAW_NOT_180")
    bad_lr = fake.measure("P02", {}); bad_lr["rows"][0]["sides"]["L"]["route_faces_cm"] = {"front_s_cm": 10, "back_s_cm": 0}
    expect_stop("N5 NEG L/R corridor convention mismatch refused", lambda: core.make_dry(bad_lr, "BAD"), "LR_FACING_NOT_CORRIDOR")
    expect_stop("N6 NEG APPLY confirm must carry fresh DRY hash",
                lambda: core.validate_args({"mode": "APPLY", "passage": "P02", "confirm": "wrong", "decided_by": "Gary"}, dry),
                "CONFIRM_MISMATCH")

    before = fake.cue_texts(); fake.write_top_policies({t["key"]: core.ROTATE for t in dry["targets"]}); after = fake.cue_texts()
    check("P2 POS text verifier accepts FacingPolicy-only edits", not core.verify_facing_only_texts(tc, before, after, set(range(23))))
    changed = list(after); top = core.panel_text(tc, changed[0]); top = tc.replace_field(top, "bFlipImageHorizontally", "True")
    wp = tc.get_field(changed[0], "WingPair"); changed[0] = tc.replace_field(changed[0], "WingPair", tc.replace_field(wp, "Top", top))
    check("N7 NEG text verifier catches image-flip drift",
          any("TOP_CHANGED_OUTSIDE_FACING" in x for x in core.verify_facing_only_texts(tc, before, changed, set(range(23)))))

    with tempfile.TemporaryDirectory() as temp:
        # Full positive DRY -> APPLY -> read-back -> REVERT.
        ops = FakeOps()
        dry = app.run_dry(ops, core, "P02TF-DRY", temp)
        check("P3 POS DRY writes named + LATEST records and does not mutate", os.path.exists(os.path.join(temp, "p02_top_facing_dry_P02TF-DRY.json")) and not ops.events)
        apply_args = {"mode": "APPLY", "passage": "P02", "confirm": core.confirm_for("APPLY", dry=dry), "decided_by": "Gary approved E9"}
        core.validate_args(apply_args, dry)
        applied = app.run_apply(ops, core, tc, apply_args, dry, "P02TF-APPLY", temp)
        check("P4 POS APPLY writes 23 FacingPolicy fields and records 23/23 matching L/R signs",
              applied["written_count"] == 23 and all(x["matches_lr"] for x in applied["facing_probe_after_save"]))
        check("P5 POS backup precedes write; materialize precedes targeted saves", ops.backups[0].startswith("PreP02TopFacing-") and
              ops.events.index(("materialize", "P02")) < ops.events.index(("save", "show")) < ops.events.index(("save", "level")))
        check("P6 POS all Tops rotate, flips remain false, no transforms changed",
              all(policy_from_text(c) == core.ROTATE and not ops._plain(i, "T")["flip_image_horizontally"]
                  for i, c in enumerate(ops.texts[:core.EXPECTED_TOPS])))
        active = json.load(open(os.path.join(temp, "p02_top_facing_ACTIVE.json"), encoding="utf-8"))
        originals = json.load(open(active["originals"], encoding="utf-8")); originals["_path"] = active["originals"]
        revert_args = {"mode": "REVERT", "passage": "P02", "confirm": core.confirm_for("REVERT", originals=originals)}
        core.validate_args(revert_args, originals=originals)
        reverted = app.run_revert(ops, core, tc, revert_args, originals, "P02TF-REVERT", temp)
        check("P7 POS REVERT records 23/23 original opposite signs", reverted["written_count"] == 23 and
              all(x["signs"]["T"] == 1 for x in reverted["facing_probe_after_save"]))
        check("P8 POS REVERT retires records without permanent deletion",
              not os.path.exists(os.path.join(temp, "p02_top_facing_ACTIVE.json")) and
              os.path.exists(os.path.join(temp, "p02_top_facing_ACTIVE_reverted_P02TF-REVERT.json")))

    # Full negative controls use independent temp roots.
    with tempfile.TemporaryDirectory() as temp:
        ops = FakeOps(); ops.dirty["content"] = ["/Game/Other/Dirty"]
        expect_stop("N8 NEG dirty census blocks DRY", lambda: app.run_dry(ops, core, "BAD", temp), "DIRTY_CENSUS")
    with tempfile.TemporaryDirectory() as temp:
        ops = FakeOps(); dry = core.make_dry(ops.measure("P02", {}), "D")
        ops.texts[0] = ops.texts[0].replace("GapToNextCm=500.000000", "GapToNextCm=501.000000")
        args = {"mode": "APPLY", "passage": "P02", "confirm": core.confirm_for("APPLY", dry=dry), "decided_by": "Gary"}
        expect_stop("N8 NEG any P02 cue edit stales the DRY before backup/write", lambda: app.run_apply(ops, core, tc, args, dry, "BAD", temp), "DRY_STALE")
        check("N8 NEG no backup and no write", not ops.backups and not ops.events)
    with tempfile.TemporaryDirectory() as temp:
        ops = FakeOps(); ops.fault = "image_flip"; dry = core.make_dry(ops.measure("P02", {}), "D")
        args = {"mode": "APPLY", "passage": "P02", "confirm": core.confirm_for("APPLY", dry=dry), "decided_by": "Gary"}
        expect_stop("N9 NEG accidental image flip rolls back before save", lambda: app.run_apply(ops, core, tc, args, dry, "BAD", temp), "TOP_CHANGED_OUTSIDE_FACING")
        check("N9 NEG no save occurred", not any(e[0] == "save" for e in ops.events))
        check("N9 NEG failed records retained but ACTIVE pointer retired after exact rollback",
              not os.path.exists(os.path.join(temp, "p02_top_facing_ACTIVE.json")) and
              os.path.exists(os.path.join(temp, "p02_top_facing_ACTIVE_failed_BAD.json")))
    with tempfile.TemporaryDirectory() as temp:
        ops = FakeOps(); ops.fault = "other_passage"; dry = core.make_dry(ops.measure("P02", {}), "D")
        args = {"mode": "APPLY", "passage": "P02", "confirm": core.confirm_for("APPLY", dry=dry), "decided_by": "Gary"}
        expect_stop("N10 NEG any non-target/other-passage cue mutation rolls back", lambda: app.run_apply(ops, core, tc, args, dry, "BAD", temp), "NON_TARGET_CUE_CHANGED")
        check("N10 NEG no save occurred", not any(e[0] == "save" for e in ops.events))
    with tempfile.TemporaryDirectory() as temp:
        ops = FakeOps(); dry = core.make_dry(ops.measure("P02", {}), "D"); ops.fault = "top_sign_does_not_flip"
        args = {"mode": "APPLY", "passage": "P02", "confirm": core.confirm_for("APPLY", dry=dry), "decided_by": "Gary"}
        expect_stop("N11 NEG materialized Top sign failing to match L/R rolls back", lambda: app.run_apply(ops, core, tc, args, dry, "BAD", temp), "FACING_SIGN_READBACK")
        check("N11 NEG no save occurred", not any(e[0] == "save" for e in ops.events))
    with tempfile.TemporaryDirectory() as temp:
        ops = FakeOps(); dry = core.make_dry(ops.measure("P02", {}), "D"); ops.fault = "foreign_dirty"
        args = {"mode": "APPLY", "passage": "P02", "confirm": core.confirm_for("APPLY", dry=dry), "decided_by": "Gary"}
        expect_stop("N12 NEG foreign dirty package blocks targeted saves", lambda: app.run_apply(ops, core, tc, args, dry, "BAD", temp), "DIRTY_SCOPE")
        check("N12 NEG no save occurred", not any(e[0] == "save" for e in ops.events))

    # Static shipping checks.
    import ast
    source = open(os.path.join(HERE, "p02_top_facing.py"), encoding="utf-8").read()
    check("S1 live files parse as Python 3.11", all(ast.parse(open(os.path.join(HERE, name), encoding="utf-8").read(), feature_version=(3, 11))
          for name in ("p02_top_facing.py", "p02_top_facing_core.py", "p02_top_facing_run.py")))
    check("S2 sole panel property setter is facing_policy", source.count('panel.set_editor_property("facing_policy"') == 1 and
          'set_editor_property("local_transform"' not in source and 'set_editor_property("flip_image_horizontally"' not in source)
    check("S3 no Save All / asset delete / package reload / image or UV mutation", not any(token in source for token in
          ("save_dirty_packages", "SaveAll", "delete_asset", "reload_packages", "set_uv", "image_horizontally\", ")))
    request = json.load(open(os.path.join(HERE, "p02_top_facing_request.json"), encoding="utf-8"))
    check("S4 request uses guarded project-Python route", request["arguments"]["tool_name"] == "ExecuteProjectPythonFile" and
          request["arguments"]["arguments"]["relativeSavedPath"] == "CodexFlatV3/p02_top_facing/p02_top_facing_run.py")
    args = json.load(open(os.path.join(HERE, "p02_top_facing_args.json"), encoding="utf-8"))
    check("S5 shipped args are read-only DRY", core.validate_args(args) == "DRY")

    report = {"passed": sum(x["pass"] for x in RESULTS), "failed": sum(not x["pass"] for x in RESULTS), "checks": RESULTS}
    with open(os.path.join(HERE, "test_p02_top_facing_offline_report.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1)
    print("RESULT %d passed, %d failed" % (report["passed"], report["failed"]))
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
