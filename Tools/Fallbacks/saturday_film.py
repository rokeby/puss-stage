"""Resumable post/build driver used by saturday_night_film.ps1.

This module never opens Unreal itself.  The PowerShell entry point performs the
live Master DRY/BUILD first, then this driver renders each baked job, encodes,
QCs and promotes only hard-QC-passing Scene deliveries.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys


SCENES = tuple(range(1, 7))
TIERS = ("P", "C")


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=1)
    os.replace(temp, path)


def delivery_key(scene: int, tier: str) -> str:
    return "S%d/%s" % (int(scene), tier)


def jobs_for(built, scene: int, tier: str, version: str):
    rows = [j for j in built.get("built", []) if int(j.get("scene", 0)) == int(scene)
            and j.get("tier") == tier and j.get("version") == version and not j.get("test")]
    rows.sort(key=lambda row: row["keep_range"][0])
    return rows


def validate_built_matrix(built, scenes=SCENES, tiers=TIERS, version="v01"):
    """Require every Scene/tier and exact contiguous coverage of the live-read Scene range."""
    bad = []
    for scene in scenes:
        scene_row = (built.get("scenes") or {}).get(str(scene))
        if not scene_row:
            bad.append("MISSING_SCENE|S%d" % scene)
            continue
        want = list(scene_row.get("master_range") or [])
        for tier in tiers:
            rows = jobs_for(built, scene, tier, version)
            if not rows:
                bad.append("MISSING_DELIVERY|S%d|%s" % (scene, tier))
                continue
            if list(rows[0]["keep_range"])[0] != want[0] or list(rows[-1]["keep_range"])[1] != want[1]:
                bad.append("COVERAGE|S%d|%s" % (scene, tier))
            for left, right in zip(rows, rows[1:]):
                if left["keep_range"][1] != right["keep_range"][0]:
                    bad.append("GAP_OR_OVERLAP|%s|%s" % (left["name"], right["name"]))
    return bad


def stage_done(checkpoint, key: str, stage: str) -> bool:
    return bool(((checkpoint.get("deliveries") or {}).get(key) or {}).get(stage))


def mark(checkpoint, key: str, stage: str, detail=None):
    row = checkpoint.setdefault("deliveries", {}).setdefault(key, {})
    row[stage] = {"utc": dt.datetime.now(dt.timezone.utc).isoformat(), "detail": detail or {}}


def planned_actions(built, checkpoint, scene: int, tier: str, version: str):
    """Pure resume planner: completed stages are absent from the returned action list."""
    key = delivery_key(scene, tier)
    actions = []
    for job in jobs_for(built, scene, tier, version):
        stage = "render:%s" % job["name"]
        if not stage_done(checkpoint, key, stage):
            actions.append(("render", job["name"]))
    for stage in ("encode", "qc", "promote"):
        if not stage_done(checkpoint, key, stage):
            actions.append((stage, key))
    return actions


def cd4_schema_errors(registry):
    """Mirror the subset CD4 reads: scenes.S<n>, video, frames and fps."""
    bad = []
    if not isinstance(registry, dict) or registry.get("schema") != 1:
        return ["SCHEMA"]
    scenes = registry.get("scenes")
    if not isinstance(scenes, dict):
        return ["SCENES"]
    for key, row in scenes.items():
        if key not in {"S%d" % n for n in SCENES}:
            bad.append("KEY|%s" % key)
        elif not isinstance(row, dict) or not row.get("video"):
            bad.append("VIDEO|%s" % key)
        elif not isinstance(row.get("frames"), int) or row["frames"] <= 0:
            bad.append("FRAMES|%s" % key)
        elif not isinstance(row.get("fps"), (int, float)) or row["fps"] <= 0:
            bad.append("FPS|%s" % key)
    return bad


class RealInvoker:
    def __init__(self, project: Path, run_id: str, approved_by: str):
        self.project = project
        self.run_id = run_id
        self.approved_by = approved_by
        self.mrq = project / "Saved" / "CodexConductor" / "MRQ"
        self.root = project / "Renders" / "Fallbacks"
        self.log_root = self.root / "_Saturday" / run_id

    def __call__(self, action, scene, tier, version, value):
        self.log_root.mkdir(parents=True, exist_ok=True)
        stem = "PussFB_S%d_%s_%s" % (scene, tier, version)
        scene_root = self.root / ("S%d" % scene)
        if action == "encode":
            expected = [scene_root / (stem + ext) for ext in (".mp4", ".wav", ".json")]
            if all(path.exists() for path in expected):
                return True, {"recovered_existing": [str(path) for path in expected]}
            stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            for path in expected:
                if path.exists():
                    path.rename(path.with_name(path.name + ".partial-" + self.run_id + "-" + stamp))
        if action == "qc":
            qc_path = scene_root / (stem + "_qc.json")
            if qc_path.exists():
                qc = load_json(qc_path)
                detail = {"recovered_existing": str(qc_path), "qc": str(qc_path),
                          "hard_fail": qc.get("hard_fail", []), "soft": qc.get("soft", []),
                          "frozen": qc.get("frozen_stretches_s", []),
                          "black": (qc.get("luma") or {}).get("black_stretches_s", [])}
                return bool(qc.get("ok")), detail
        if action == "promote":
            current = self.root / "current.json"
            if current.exists():
                row = (load_json(current).get("scenes") or {}).get("S%d" % scene, {})
                if row.get("video") == "S%d/%s.mp4" % (scene, stem):
                    return True, {"recovered_existing": str(current)}
        if action == "render":
            argv = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                    str(self.mrq / "mrq_render.ps1"), "-Job", value,
                    "-JobsFile", str(self.mrq / "mrq_jobs_built.json"), "-MoveAside"]
        else:
            argv = [sys.executable, str(self.mrq / "mrq_post.py"), action,
                    "--scene", str(scene), "--tier", tier, "--version", version]
            if action == "promote":
                argv += ["--by", self.approved_by]
        result = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace")
        log = self.log_root / ("S%d.log" % scene)
        with log.open("a", encoding="utf-8") as handle:
            handle.write("\n[%s] %s\n%s\n%s\n" %
                         (dt.datetime.now(dt.timezone.utc).isoformat(), " ".join(argv), result.stdout, result.stderr))
        detail = {"returncode": result.returncode, "last_line": (result.stdout.strip().splitlines() or [""])[-1]}
        if result.returncode != 0:
            return False, detail
        if action == "qc":
            qc_path = self.root / ("S%d" % scene) / (stem + "_qc.json")
            if not qc_path.exists():
                return False, dict(detail, reason="QC_JSON_MISSING")
            qc = load_json(qc_path)
            detail.update({"qc": str(qc_path), "hard_fail": qc.get("hard_fail", []),
                           "soft": qc.get("soft", []), "frozen": qc.get("frozen_stretches_s", []),
                           "black": (qc.get("luma") or {}).get("black_stretches_s", [])})
            if not qc.get("ok"):
                return False, detail
        return True, detail


def execute_delivery(built, checkpoint, scene, tier, version, invoke, save):
    """Run one Scene/tier. A failed action ends this delivery; promote is unreachable after QC failure."""
    key = delivery_key(scene, tier)
    for action, value in planned_actions(built, checkpoint, scene, tier, version):
        ok, detail = invoke(action, scene, tier, version, value)
        if not ok:
            checkpoint.setdefault("failures", []).append({"delivery": key, "action": action, "detail": detail})
            save(checkpoint)
            return False
        stage = "render:%s" % value if action == "render" else action
        mark(checkpoint, key, stage, detail)
        save(checkpoint)
    return stage_done(checkpoint, key, "promote")


def write_human_report(path: Path, run_id: str, checkpoint, version: str, tiers):
    lines = ["# Saturday Scene filming result — %s" % run_id, "",
             "Version `%s`; tiers `%s`. Machine QC is not visual acceptance." % (version, ", ".join(tiers)), "",
             "## Deliveries", ""]
    for scene in SCENES:
        for tier in tiers:
            key = delivery_key(scene, tier)
            row = (checkpoint.get("deliveries") or {}).get(key, {})
            status = "PROMOTED" if row.get("promote") else "FAILED / INCOMPLETE"
            qc = (row.get("qc") or {}).get("detail", {})
            lines.append("- %s: %s; soft=%d; frozen=%d; black=%d" %
                         (key, status, len(qc.get("soft", [])), len(qc.get("frozen", [])), len(qc.get("black", []))))
    lines += ["", "## Morning eyeball", "",
              "Check every contact sheet and clip for intended darkness, static-but-authored shots, sky/exposure, streamed sets, camera cuts, cloth/foam motion, HUD absence, and sound sync. Raw renders were retained.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--project", type=Path, default=Path(r"E:\PussStage"))
    p.add_argument("--run-id", required=True)
    p.add_argument("--version", default="v01")
    p.add_argument("--tiers", nargs="+", choices=TIERS, default=list(TIERS))
    p.add_argument("--approved-by", default="Saturday unattended hard QC")
    args = p.parse_args(argv)
    jobs_file = args.project / "Saved" / "CodexConductor" / "MRQ" / "mrq_jobs_built.json"
    built = load_json(jobs_file)
    bad = validate_built_matrix(built, tiers=args.tiers, version=args.version)
    if bad:
        print("SATFILM_FAILED|run=%s|reason=BUILT_MATRIX|%s" % (args.run_id, ";".join(bad)))
        return 2
    state_root = args.project / "Renders" / "Fallbacks" / "_Saturday" / args.run_id
    checkpoint_path = state_root / "checkpoint.json"
    checkpoint = load_json(checkpoint_path) if checkpoint_path.exists() else {
        "run_id": args.run_id, "version": args.version, "tiers": args.tiers, "deliveries": {}, "failures": []}
    save = lambda state: atomic_json(checkpoint_path, state)
    save(checkpoint)
    invoke = RealInvoker(args.project, args.run_id, args.approved_by)
    for scene in SCENES:
        p_ok = True
        for tier in args.tiers:
            if tier == "C" and "P" in args.tiers and not p_ok:
                checkpoint.setdefault("failures", []).append(
                    {"delivery": delivery_key(scene, tier), "action": "skip", "detail": {"reason": "P_FAILED"}})
                save(checkpoint)
                continue
            ok = execute_delivery(built, checkpoint, scene, tier, args.version, invoke, save)
            if tier == "P":
                p_ok = ok
    summary = {"run_id": args.run_id, "version": args.version, "tiers": args.tiers,
               "promoted": [k for k, v in checkpoint.get("deliveries", {}).items() if v.get("promote")],
               "failures": checkpoint.get("failures", []),
               "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
               "checkpoint": str(checkpoint_path)}
    summary_path = state_root / "summary.json"
    report_path = state_root / "REPORT.md"
    atomic_json(summary_path, summary)
    write_human_report(report_path, args.run_id, checkpoint, args.version, args.tiers)
    expected = len(SCENES) * len(args.tiers)
    print("SATFILM_APPLY_COMPLETE|run=%s|deliveries_ok=%d/%d|failed=%d|summary=%s|report=%s" %
          (args.run_id, len(summary["promoted"]), expected, len(summary["failures"]), summary_path, report_path))
    return 0 if len(summary["promoted"]) == expected else 3


if __name__ == "__main__":
    raise SystemExit(main())
