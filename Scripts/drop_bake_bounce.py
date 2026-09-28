"""Quantify the landing bounce of drop-bake runs from their per-frame centre of mass and top (metres).

    python Scripts/drop_bake_bounce.py bt0_base bta_self15 ...
    python Scripts/drop_bake_bounce.py --ref bt0_base --until 146 bt2_dampramp_collapse

--ref/--until: the DESCENT check. The largest COM difference from the reference run up to frame --until
(the frame a keyed change begins). A fix that changes nothing but the defect must leave the fall identical.

For each run: the collapse minimum of the centre of mass (after the fall), the REBOUND = how far the
centre of mass and the top rise after that minimum, when, and the final (settled) values. A heavy
landing thumps and stays down; the 28 Sep "bounce" was the pile re-inflating after the collapse.
"""
import json
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parents[1] / "Saved" / "CodexSoftGoods" / "DropBake"
args = sys.argv[1:]
REF, UNTIL = None, None
if "--ref" in args:
    i = args.index("--ref"); REF = args[i + 1]; del args[i:i + 2]
if "--until" in args:
    i = args.index("--until"); UNTIL = int(args[i + 1]); del args[i:i + 2]
ref = json.loads((DIR / f"{REF}.json").read_text(encoding="utf-8")) if REF else None
print(f"{'run':16s} ratio  com_min  at_s  com_rise  top_min  top_rise  rise_at_s  final_com final_top")
for run in args:
    d = json.loads((DIR / f"{run}.json").read_text(encoding="utf-8"))
    com, top = d["com_z"], d["top_z"]
    t = [(i - 1) / 30.0 for i in range(len(com))]        # index 0 = RELEASE_FRAME - 1
    # The collapse minimum: the first local minimum after the curtain is down (com below 0.5 m).
    down = next((i for i, c in enumerate(com) if c < 0.5), None)
    if down is None:
        print(f"{run:16s} never came down")
        continue
    j = down
    while j + 1 < len(com) and com[j + 1] <= com[j]:
        j += 1
    rise_i = max(range(j, len(com)), key=lambda k: com[k])
    # The top's collapse minimum is the one BEFORE the rebound peak (the settled end can sit lower still, which
    # made a global minimum report no rise at all, 28 Sep); the rise is measured over the next 1.5 s.
    tj = min(range(down, rise_i + 1), key=lambda k: top[k])
    top_rise = max(top[tj:tj + 45]) - top[tj]
    print(f"{run:16s} {d.get('self_dist_edge_ratio', 0):5.2f}  {com[j]:6.3f}  {t[j]:4.2f}  {com[rise_i] - com[j]:7.3f}   "
          f"{top[tj]:6.2f}  {top_rise:7.2f}    {t[rise_i]:5.2f}     {com[-1]:6.3f}   {top[-1]:6.2f}")
    if ref and UNTIL:
        n = UNTIL - (d["release_frame"] - 1)                     # com_z[0] is RELEASE_FRAME - 1
        diff = max(abs(a - b) for a, b in zip(com[:n], ref["com_z"][:n]))
        print(f"{'':16s} descent vs {REF} up to frame {UNTIL}: max |dCOM| = {diff:.4f} m")
