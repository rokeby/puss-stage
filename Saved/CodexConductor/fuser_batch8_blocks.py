"""Gary 5 Oct: his Fuser pipe takes 8 prompts per run, split on '~~'. Pack the no-image prompts (1_SOLO_no_reference.csv)
into blocks of 8 (each prompt keeps its internal §§ fields), plus a key mapping block/slot -> job, step, save_to."""
import csv, os, sys
Q = "DerivedAssets/FlatV3/FuserQueue"
SRC = os.path.join(Q, "1_SOLO_no_reference.csv")
rows = list(csv.DictReader(open(SRC, encoding="utf-8-sig")))
assert all(not r["image_to_load"].strip() for r in rows), "an image prompt in the no-reference CSV"
assert not any("~~" in r["prompt"] for r in rows), "a prompt already contains ~~"
blocks = [rows[i:i + 8] for i in range(0, len(rows), 8)]
out, key = [], ["block,slot,job,passage,step,save_to"]
for b, blk in enumerate(blocks, 1):
    out.append("=== BLOCK %d of %d (%d prompts) ===\n" % (b, len(blocks), len(blk)) + "\n~~\n".join(r["prompt"].strip() for r in blk))
    for s, r in enumerate(blk, 1):
        key.append('%d,%d,%s,%s,"%s",%s' % (b, s, r["job"], r["passage"], r["step"].replace('"', "'"), r["save_to"]))
open(os.path.join(Q, "BATCH8_no_reference_blocks.txt"), "w", encoding="utf-8").write("\n\n".join(out) + "\n")
open(os.path.join(Q, "BATCH8_no_reference_key.csv"), "w", encoding="utf-8-sig").write("\n".join(key) + "\n")
print("BATCH8_OK|prompts=%d|blocks=%s" % (len(rows), [len(b) for b in blocks]))
