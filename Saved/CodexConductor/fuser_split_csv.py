"""Split the Fuser prompt rows into three working sheets (Gary 5 Oct):
 1_SOLO_no_reference.csv      paste into a solo text-only recipe, one row = one image
 2_EDITS_of_existing_wings.csv  each row = one existing wing image + its prompt (grouped by job)
 3_PAIRS_chained.csv          a -> b pairs: a (text or style ref) then b fed with a's output
Only jobs >= MIN_JOB (default 26, tonight's) unless --all."""
import csv
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2] / "DerivedAssets" / "FlatV3" / "FuserQueue"
MIN_JOB = 0 if "--all" in sys.argv else 26
rows = list(csv.DictReader(open(ROOT / "ALL_PROMPTS.csv", encoding="utf-8-sig")))
style_ref = {}
for d in ROOT.iterdir():
    s = d / "SLOTS.md"
    if s.is_file():
        txt = s.read_text(encoding="utf-8")
        m = (re.search(r"Style reference[^:]*:\s*([^\s)]+)", txt)
             or re.search(r"(?m)^Image node:\s*([^\s)]+)", txt))
        if m:
            style_ref[d.name] = m.group(1).rstrip(".")
solo, edits, pairs = [], [], []
for r in rows:
    if int(r["job"][:2]) < MIN_JOB:
        continue
    sub, img, line = r["subjob"], r["image_input"], r["one_line_prompt"]
    out = {"job": r["job"], "passage": r["passage"], "step": sub, "image_to_load": "", "prompt": line, "save_to": r["save_to"]}
    chained = "a's output" in sub or "output from sub-job" in line or "from sub-job a" in line
    pair_job = any(x["job"] == r["job"] and "a's output" in x["subjob"] for x in rows)
    if chained or "style reference" in sub.lower() or (pair_job and sub.startswith("a")):
        out["image_to_load"] = ("OUTPUT OF STEP a" if chained else
                                (img.split(":", 1)[1].strip() if img.startswith("Image node:") and "reference" not in img
                                 else style_ref.get(r["job"], "none (text only)")))
        pairs.append(out)
    elif img.startswith("Image node:") and "reference" not in img:
        out["image_to_load"] = img.split(":", 1)[1].strip()
        edits.append(out)
    elif line.startswith("no input image"):
        solo.append(out)
    else:
        out["image_to_load"] = style_ref.get(r["job"], img or "see SLOTS.md")
        edits.append(out)
cols = ["job", "passage", "step", "image_to_load", "prompt", "save_to"]
for name, data, key in (("1_SOLO_no_reference.csv", solo, None), ("2_EDITS_of_existing_wings.csv", edits, None),
                        ("3_PAIRS_chained.csv", pairs, None)):
    data.sort(key=lambda x: (x["job"], x["step"]))
    with open(ROOT / name, "w", encoding="utf-8-sig", newline="") as h:
        w = csv.DictWriter(h, fieldnames=cols)
        w.writeheader()
        w.writerows(data)
print("SPLIT_OK|solo=%d|edits=%d|pairs=%d" % (len(solo), len(edits), len(pairs)))
