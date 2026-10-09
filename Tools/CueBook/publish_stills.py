"""Publish a passed Cue Book capture run into the static site.

Modes:
  python Tools/CueBook/publish_stills.py DRY <run-dir>
  python Tools/CueBook/publish_stills.py APPLY <run-dir> --confirm APPLY_CUEBOOK_STILLS_PUBLISH
  python Tools/CueBook/publish_stills.py REVERT <backup-dir> --confirm REVERT_CUEBOOK_STILLS_PUBLISH

APPLY never deletes a still.  Every target that already exists is moved into
``Backups/PreCueBookStills-<run>/site/`` before the replacement is written.
REVERT likewise moves the published files into a fresh revert backup before it
restores those originals.
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import re
import shutil

from PIL import Image, ImageOps


APPLY_CONFIRM = "APPLY_CUEBOOK_STILLS_PUBLISH"
REVERT_CONFIRM = "REVERT_CUEBOOK_STILLS_PUBLISH"
MANIFEST_NAME = "cuebook_stills_manifest.json"
EMPTY_CENSUS = {"maps": [], "content": []}


class PublishRefused(RuntimeError):
    pass


def utc_stamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")


def utc_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def write_verified(path, data):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    if json.loads(path.read_text(encoding="utf-8")) != data:
        raise PublishRefused("CUEBOOK_STILLS_PUBLISH_READBACK|%s" % path)


def _inside(path, root):
    path, root = pathlib.Path(path).resolve(), pathlib.Path(root).resolve()
    return path == root or root in path.parents


def _source_path(value, run_dir):
    path = pathlib.Path(value)
    if not path.is_absolute():
        path = pathlib.Path(run_dir) / path
    path = path.resolve()
    if not _inside(path, run_dir) or not path.is_file() or path.suffix.lower() != ".png":
        raise PublishRefused("CUEBOOK_STILLS_PUBLISH_BAD_SOURCE|%s" % path)
    return path


def build_publish_plan(run_dir, site_dir):
    run_dir, site_dir = pathlib.Path(run_dir).resolve(), pathlib.Path(site_dir).resolve()
    source_manifest = run_dir / MANIFEST_NAME
    if not source_manifest.is_file():
        raise PublishRefused("CUEBOOK_STILLS_PUBLISH_NO_MANIFEST|%s" % source_manifest)
    run = json.loads(source_manifest.read_text(encoding="utf-8"))
    if run.get("status") not in ("passed", "partial"):
        raise PublishRefused("CUEBOOK_STILLS_PUBLISH_RUN_NOT_PASSED|%s" % run.get("status"))
    run_id = str(run.get("run_id", ""))
    if re.fullmatch(r"CBSTILLS-[A-Za-z0-9_-]+", run_id) is None:
        raise PublishRefused("CUEBOOK_STILLS_PUBLISH_BAD_RUN|%s" % run_id)
    captures = run.get("captures")
    if not isinstance(captures, list):
        raise PublishRefused("CUEBOOK_STILLS_PUBLISH_BAD_CAPTURES")
    jobs, seen = [], set()
    skipped = run.get("skipped", []) or []
    if not isinstance(skipped, list) or any(not isinstance(row, dict) for row in skipped):
        raise PublishRefused("CUEBOOK_STILLS_PUBLISH_BAD_SKIPPED")
    out = {"schema_version": 1, "run_id": run_id, "published": None, "segments": {}, "cues": {},
           "skipped": skipped}
    for capture in captures:
        kind = capture.get("kind")
        key = str(capture.get("segment_key") if kind == "segment" else capture.get("cue_key", ""))
        if kind == "segment":
            if re.fullmatch(r"(?:P\d{2}|S\d+|I\d+|Opening|Closing)", key) is None:
                raise PublishRefused("CUEBOOK_STILLS_PUBLISH_BAD_SEGMENT|%s" % key)
            rel = pathlib.PurePosixPath("stills") / (key + ".jpg")
            bucket = out["segments"]
        elif kind == "cue":
            if re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{1,63}", key) is None:
                raise PublishRefused("CUEBOOK_STILLS_PUBLISH_BAD_CUE|%s" % key)
            rel = pathlib.PurePosixPath("stills") / "cue" / (key + ".jpg")
            bucket = out["cues"]
        else:
            raise PublishRefused("CUEBOOK_STILLS_PUBLISH_BAD_KIND|%r" % kind)
        identity = (kind, key)
        if identity in seen:
            raise PublishRefused("CUEBOOK_STILLS_PUBLISH_DUPLICATE|%s|%s" % identity)
        seen.add(identity)
        source = _source_path(capture.get("path", ""), run_dir)
        entry = {"file": rel.as_posix(), "unreal_id": str(capture.get("unreal_id", "")),
                 "master_frame": int(capture["master_frame"]), "captured": capture.get("captured")}
        bucket[key] = entry
        jobs.append({"kind": kind, "key": key, "source": source,
                     "relative": rel.as_posix(), "target": site_dir / pathlib.Path(*rel.parts)})
    targets = [job["relative"] for job in jobs] + ["stills.json"]
    return {"run_id": run_id, "run_dir": run_dir, "site_dir": site_dir,
            "source_manifest": source_manifest, "jobs": jobs, "targets": targets, "manifest": out}


def _render_jpeg(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        height = max(1, int(round(image.height * (1280.0 / image.width))))
        image = image.resize((1280, height), Image.Resampling.LANCZOS)
        image.save(target, format="JPEG", quality=82, optimize=True)
    with Image.open(target) as check:
        if check.format != "JPEG" or check.width != 1280:
            raise PublishRefused("CUEBOOK_STILLS_PUBLISH_JPEG_READBACK|%s" % target)


def _move_if_present(source, target):
    source, target = pathlib.Path(source), pathlib.Path(target)
    if not source.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise PublishRefused("CUEBOOK_STILLS_PUBLISH_BACKUP_COLLISION|%s" % target)
    shutil.move(str(source), str(target))
    return True


def apply_publish(plan, backups_root, confirm):
    if confirm != APPLY_CONFIRM:
        raise PublishRefused("CUEBOOK_STILLS_PUBLISH_REFUSED|reason=confirm")
    backups_root = pathlib.Path(backups_root).resolve()
    backup = backups_root / ("PreCueBookStills-%s" % plan["run_id"])
    if backup.exists():
        raise PublishRefused("CUEBOOK_STILLS_PUBLISH_REFUSED|reason=backup_exists|path=%s" % backup)
    backup.mkdir(parents=True, exist_ok=False)
    record_path = backup / "record.json"
    existed = {relative: (plan["site_dir"] / pathlib.Path(*pathlib.PurePosixPath(relative).parts)).exists()
               for relative in plan["targets"]}
    record = {"schema_version": 1, "run_id": plan["run_id"], "mode": "APPLY",
              "source_manifest": plan["source_manifest"].as_posix(), "site_dir": plan["site_dir"].as_posix(),
              "backup_dir": backup.as_posix(), "targets": plan["targets"], "existed": existed,
              "census_before": EMPTY_CENSUS, "saved_packages": [], "started_utc": utc_iso(), "status": "backed_up"}
    write_verified(record_path, record)
    moved, written = [], []
    try:
        for relative in plan["targets"]:
            target = plan["site_dir"] / pathlib.Path(*pathlib.PurePosixPath(relative).parts)
            if _move_if_present(target, backup / "site" / pathlib.Path(*pathlib.PurePosixPath(relative).parts)):
                moved.append(relative)
        for job in plan["jobs"]:
            _render_jpeg(job["source"], job["target"])
            written.append(job["relative"])
        manifest = dict(plan["manifest"])
        manifest["published"] = utc_iso()
        write_verified(plan["site_dir"] / "stills.json", manifest)
        written.append("stills.json")
    except Exception:
        failed = backup / "failed_new"
        for relative in written:
            target = plan["site_dir"] / pathlib.Path(*pathlib.PurePosixPath(relative).parts)
            _move_if_present(target, failed / pathlib.Path(*pathlib.PurePosixPath(relative).parts))
        for relative in reversed(moved):
            old = backup / "site" / pathlib.Path(*pathlib.PurePosixPath(relative).parts)
            _move_if_present(old, plan["site_dir"] / pathlib.Path(*pathlib.PurePosixPath(relative).parts))
        raise
    record.update(status="passed", moved_existing=moved, written=written,
                  census_after=EMPTY_CENSUS, finished_utc=utc_iso())
    write_verified(record_path, record)
    check = json.loads((plan["site_dir"] / "stills.json").read_text(encoding="utf-8"))
    if check != manifest:
        raise PublishRefused("CUEBOOK_STILLS_PUBLISH_MANIFEST_READBACK")
    return record, manifest


def revert_publish(backup_dir, backups_root, confirm):
    if confirm != REVERT_CONFIRM:
        raise PublishRefused("CUEBOOK_STILLS_PUBLISH_REVERT_REFUSED|reason=confirm")
    backup_dir = pathlib.Path(backup_dir).resolve()
    record_path = backup_dir / "record.json"
    if not record_path.is_file():
        raise PublishRefused("CUEBOOK_STILLS_PUBLISH_REVERT_REFUSED|reason=no_record")
    applied = json.loads(record_path.read_text(encoding="utf-8"))
    if applied.get("mode") != "APPLY" or applied.get("status") != "passed":
        raise PublishRefused("CUEBOOK_STILLS_PUBLISH_REVERT_REFUSED|reason=record_not_passed")
    site_dir = pathlib.Path(applied["site_dir"]).resolve()
    revert_id = "%s-%s" % (applied["run_id"], utc_stamp())
    revert_backup = pathlib.Path(backups_root).resolve() / ("PreCueBookStillsRevert-%s" % revert_id)
    if revert_backup.exists():
        raise PublishRefused("CUEBOOK_STILLS_PUBLISH_REVERT_REFUSED|reason=backup_exists")
    revert_backup.mkdir(parents=True, exist_ok=False)
    record = {"schema_version": 1, "run_id": revert_id, "mode": "REVERT",
              "apply_record": record_path.as_posix(), "site_dir": site_dir.as_posix(),
              "targets": list(applied["targets"]), "census_before": EMPTY_CENSUS,
              "saved_packages": [], "started_utc": utc_iso(), "status": "backed_up"}
    write_verified(revert_backup / "record.json", record)
    restored, moved_current = [], []
    for relative in applied["targets"]:
        parts = pathlib.PurePosixPath(relative).parts
        current = site_dir / pathlib.Path(*parts)
        if _move_if_present(current, revert_backup / "published" / pathlib.Path(*parts)):
            moved_current.append(relative)
        old = backup_dir / "site" / pathlib.Path(*parts)
        if _move_if_present(old, current):
            restored.append(relative)
    record.update(status="passed", moved_published=moved_current, restored=restored,
                  census_after=EMPTY_CENSUS, finished_utc=utc_iso())
    write_verified(revert_backup / "record.json", record)
    return record


def project_root():
    return pathlib.Path(__file__).resolve().parents[2]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("DRY", "APPLY", "REVERT"))
    parser.add_argument("path")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--site-dir")
    parser.add_argument("--backups-root")
    args = parser.parse_args(argv)
    root = project_root()
    site = pathlib.Path(args.site_dir) if args.site_dir else root / "Tools" / "CueBook" / "site"
    backups = pathlib.Path(args.backups_root) if args.backups_root else root / "Backups"
    if args.mode == "REVERT":
        record = revert_publish(args.path, backups, args.confirm)
        print("CUEBOOK_STILLS_PUBLISH_REVERT_OK|run=%s|backup=%s" %
              (record["run_id"], pathlib.Path(backups).resolve().as_posix()))
        return 0
    plan = build_publish_plan(args.path, site)
    replacements = sum((plan["site_dir"] / pathlib.Path(*pathlib.PurePosixPath(p).parts)).exists()
                       for p in plan["targets"])
    if args.mode == "DRY":
        print("CUEBOOK_STILLS_PUBLISH_DRY_OK|run=%s|segments=%d|cues=%d|targets=%d|replacements=%d" %
              (plan["run_id"], len(plan["manifest"]["segments"]), len(plan["manifest"]["cues"]),
               len(plan["targets"]), replacements))
        return 0
    record, manifest = apply_publish(plan, backups, args.confirm)
    print("CUEBOOK_STILLS_PUBLISH_OK|run=%s|segments=%d|cues=%d|backup=%s" %
          (plan["run_id"], len(manifest["segments"]), len(manifest["cues"]), record["backup_dir"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
