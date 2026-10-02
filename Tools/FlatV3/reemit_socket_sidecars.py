"""Re-emit Slot A socket JSON only; never rebuild meshes or invoke Unreal."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from socket_contract import discover_slot_a_rows


PROJECT = Path(__file__).resolve().parents[2]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    rows = discover_slot_a_rows(PROJECT)
    if len(rows) != 35:
        raise RuntimeError(f"Slot A inventory changed: expected 35 built flats, found {len(rows)}")
    report_rows = []
    for row in rows:
        path = row["sidecar_path"]
        before = path.read_bytes()
        after = (json.dumps(row["expected"], indent=2) + "\n").encode("utf-8")
        changed = before != after
        if not args.dry_run:
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_bytes(after)
            os.replace(temporary, path)
        report_rows.append({
            "asset": row["asset"],
            "passage": row["passage"],
            "path": str(path),
            "changed": changed,
            "before_sha256": digest(before),
            "after_sha256": digest(after),
            "socket_names": [socket["name"] for socket in row["expected"]["sockets"]],
        })

    report = {
        "schema_version": 1,
        "mode": "dry-run" if args.dry_run else "write",
        "mesh_files_touched": 0,
        "sidecars_seen": len(report_rows),
        "sidecars_changed": sum(item["changed"] for item in report_rows),
        "items": report_rows,
    }
    if args.report:
        report_path = args.report if args.report.is_absolute() else PROJECT / args.report
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "mode", "mesh_files_touched", "sidecars_seen", "sidecars_changed"
    )}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
