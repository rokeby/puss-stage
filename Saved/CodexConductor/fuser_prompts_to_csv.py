"""Collect every Fuser prompt in DerivedAssets/FlatV3/FuserQueue/*/(SLOTS|VARIANTS).md into one CSV.

One row = one paste into Fuser's Text Split node (the ONE-LINE value, with its §§ slots).
Read-only on the queue; writes only the CSV given by --out (default: FuserQueue/ALL_PROMPTS.csv).
Usage: python fuser_prompts_to_csv.py [--out PATH]
"""
import argparse
import csv
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2] / "DerivedAssets" / "FlatV3" / "FuserQueue"


def parse_md(path):
    """Yield (subjob_header, image_note, one_line) for each '## ...' block with a ONE-LINE value."""
    text = path.read_text(encoding="utf-8")
    blocks = re.split(r"(?m)^## ", text)
    for block in blocks[1:]:
        header, _, body = block.partition("\n")
        # Two layouts: "ONE-LINE:" then the value on the next line, or "ONE-LINE `§§`: value" inline.
        m = (re.search(r"(?m)^ONE-LINE:\s*\n(.+)$", body)
             or re.search(r"(?m)^ONE-LINE[^:\n]*:\s*(\S.+)$", body)
             # VARIANTS.md layout: a bare line carrying the six-field value (5 separators).
             or re.search(r"(?m)^(?!.*Text Split)(.*(?:§§.*){5})$", body))
        if not m:
            continue
        image = ""
        im = re.search(r"\((Image node[^)]*)\)", header) or re.search(r"(?m)^(Image node[^\n]*)", body)
        if im:
            image = im.group(1).strip()
        yield header.strip(), image, m.group(1).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "ALL_PROMPTS.csv"))
    args = ap.parse_args()
    queue = json.loads((ROOT / "queue.json").read_text(encoding="utf-8"))
    jobs = {j["id"]: j for j in (queue if isinstance(queue, list) else queue.get("jobs", []))}
    rows = []
    for job_dir in sorted(p for p in ROOT.iterdir() if p.is_dir() and re.match(r"\d\d_", p.name)):
        meta = jobs.get(job_dir.name, {})
        parts = job_dir.name.split("_", 2)
        for md in ("SLOTS.md", "VARIANTS.md"):
            path = job_dir / md
            if not path.is_file():
                continue
            for header, image, one_line in parse_md(path):
                rows.append({
                    "passage": parts[1] if len(parts) > 1 else "",
                    "job": job_dir.name,
                    "priority": meta.get("priority", ""),
                    "status": meta.get("status", ""),
                    "recipe_type": meta.get("type", ""),
                    "source_file": md,
                    "subjob": header,
                    "image_input": image,
                    "one_line_prompt": one_line,
                    "expected_outputs": " ".join(meta.get("outputs", [])),
                    "save_to": str((job_dir / "results").relative_to(ROOT.parent.parent.parent)),
                })
    out = pathlib.Path(args.out)
    with out.open("w", encoding="utf-8-sig", newline="") as handle:  # BOM so Excel/Sheets read § correctly
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print("FUSER_CSV_OK|rows=%d|jobs=%d|out=%s" % (len(rows), len({r['job'] for r in rows}), out))


if __name__ == "__main__":
    main()
