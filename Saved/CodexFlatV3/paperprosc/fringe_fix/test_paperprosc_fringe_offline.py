"""Positive/negative offline harness for pixel repair and Unreal-tool contract."""
import ast
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, filename))
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value); return value


F = module("fringe_fix", "fix_paperprosc_fringe.py")
C = module("fringe_core", "paperprosc_fringe_core.py")
results = []


def check(name, condition):
    results.append({"check": name, "ok": bool(condition)})


rgba = np.zeros((96, 96, 4), dtype=np.uint8)
rgba[16:80, 16:80] = (180, 80, 60, 255)
rgba[16:20, 16:80, :3] = (30, 220, 20)
rgba[76:80, 16:80, :3] = (30, 220, 20)
rgba[16:80, 16:20, :3] = (30, 220, 20)
rgba[16:80, 76:80, :3] = (30, 220, 20)
fixed, counts = F.repair_rgba(rgba, 8, 10, 0, 8)
inside = fixed[:, :, 3] > 0
green_excess = fixed[:, :, 1].astype(int) - np.maximum(fixed[:, :, 0], fixed[:, :, 2]).astype(int)
check("POS green rim clamped", int(green_excess[inside].max()) <= 0)
check("POS opaque interior preserved", np.array_equal(fixed[40:56, 40:56], rgba[40:56, 40:56]))
check("POS default alpha byte-identical", np.array_equal(fixed[:, :, 3], rgba[:, :, 3]))
check("POS transparent padding receives colour", np.count_nonzero(fixed[:, :, :3][~inside]) > 0)
check("POS operation counts nonzero", counts["despilled_texels"] > 0 and counts["padded_transparent_texels"] > 0)
eroded, _ = F.repair_rgba(rgba, 8, 10, 1, 8)
check("POS optional one-pixel erosion works", np.count_nonzero(eroded[:, :, 3]) < np.count_nonzero(rgba[:, :, 3]))
try:
    F.repair_rgba(np.zeros((8, 8, 3), np.uint8))
    bad_rgba_refused = False
except ValueError:
    bad_rgba_refused = True
check("NEG non-RGBA refused", bad_rgba_refused)
try:
    F.repair_rgba(rgba, -1, 2, 0, 8)
    negative_refused = False
except ValueError:
    negative_refused = True
check("NEG negative parameters refused", negative_refused)

check("POS DRY needs no confirm", C.validate_args({"mode": "DRY"}, "12345678") == [])
check("NEG IMPORT wrong confirm refused", "CONFIRM" in C.validate_args({"mode": "IMPORT", "confirm": "x", "decided_by": "Gary"}, "12345678"))
check("NEG IMPORT without decision refused", "DECIDED_BY" in C.validate_args({"mode": "IMPORT", "confirm": "IMPORT PAPERPROSC FRINGE 12345678"}, "12345678"))
check("POS exact IMPORT confirm accepted", C.validate_args({"mode": "IMPORT", "confirm": "IMPORT PAPERPROSC FRINGE 12345678", "decided_by": "Gary"}, "12345678") == [])
check("POS exactly three new texture targets", len({row["new"] for row in C.ROWS.values()}) == 3)
check("POS exactly six MI targets", len({mi for row in C.ROWS.values() for mi in row["mis"]}) == 6)
check("NEG old and new assets disjoint", not ({row["old"] for row in C.ROWS.values()} & {row["new"] for row in C.ROWS.values()}))

source = open(os.path.join(HERE, "paperprosc_fringe_import.py"), encoding="utf-8").read()
ast.parse(source)
check("POS no Save All", all(token not in source for token in ("save_dirty_packages", "save_all", "save_map")))
check("POS no permanent asset deletion", "delete_asset" not in source and "os.remove" not in source)
check("POS exact dirty census gates present", source.count("DIRTY_SCOPE") >= 2 and "DIRTY_BEFORE" in source)
check("POS read-back gates both mutation modes", "READBACK" in source and "REVERT_READBACK" in source)
check("POS texture settings and source are read back", "TEXTURE_READBACK" in source and "texture_readback=texture_state" in source)
check("POS UE5.8 texture settings verified before save", "post_edit_change" not in source and
      "TEXTURE_SETTINGS_PRE_SAVE" in source and "TEXTURE_SOURCE_PRE_SAVE" in source and
      source.index("new.set_editor_property") < source.index("new.modify()") < source.index("save_only(expected_dirty)"))
check("POS backups precede Unreal mutation calls", source.index("backup_path = backup(run, original_packages") < source.index("made = import_textures(plan)"))

manifest_path = os.path.join(HERE, "fringe_fix_manifest.json")
if os.path.isfile(manifest_path):
    manifest = json.load(open(manifest_path, encoding="utf-8"))
    plan = C.build_plan(HERE, manifest)
    check("POS generated manifest passes import plan", len(plan["rows"]) == 3 and len(plan["digest8"]) == 8)
    check("POS generated outputs are new filenames", all("_FringeFix_v1.png" in row["png"] for row in plan["rows"]))
    check("POS measured fringe removed", all(row["after"]["green_excess_gt_20_texels"] == 0 for row in manifest["rows"]))
    check("POS global keyed residue reduced to negligible", sum(row["after"]["global_green_excess_gt_20_texels"] for row in manifest["rows"]) <= 44)
    alpha_equal = all(np.array_equal(
        np.asarray(Image.open(row["source"]).convert("RGBA"))[:, :, 3],
        np.asarray(Image.open(row["output"]).convert("RGBA"))[:, :, 3],
    ) for row in manifest["rows"])
    check("POS generated alpha byte-identical to sources", alpha_equal)
    check("POS immutable source hashes still match manifest", all(F.sha256(Path(row["source"])) == row["source_sha256"] for row in manifest["rows"]))
else:
    check("POS generated manifest passes import plan", False)
    check("POS generated outputs are new filenames", False)
    check("POS measured fringe removed", False)
    check("POS global keyed residue reduced to negligible", False)
    check("POS generated alpha byte-identical to sources", False)
    check("POS immutable source hashes still match manifest", False)

report = {
    "passed": sum(x["ok"] for x in results),
    "failed": sum(not x["ok"] for x in results),
    "results": results,
    "tier": "measured offline pixel, pure-contract, generated-output and static safety checks; Unreal behavior unproven",
}
path = os.path.join(HERE, "test_paperprosc_fringe_offline_report.json")
with open(path, "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2); handle.write("\n")
print("PAPERPROSC_FRINGE_HARNESS|passed=%d|failed=%d|report=%s" % (report["passed"], report["failed"], path))
sys.exit(0 if report["failed"] == 0 else 1)
