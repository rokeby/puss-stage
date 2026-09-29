"""Read the editor log and tabulate every `stat dumpframe` after the cloth-gate markers (29 Sep).

    python Scripts/parse_cloth_dumps.py [Saved/Logs/PussStage.log]

For each dump: the most recent PUSS_SOFTGOODS_CLOTH_GATE state marker before it (baseline / suspended / disabled /
restored), FChaosClothComponentEndTickFunction_ExecuteTick (ms, count), its CPU Stall - Wait For Event child, and
World Tick Time: the same lines the conductor's 12:54 measurement named. Reads only.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "Saved" / "Logs" / "PussStage.log"
STAT = re.compile(r"LogStats:\s+([\d.]+)ms \(\s*(\d+)\)\s+-\s+(.*)$")


def main():
    lines = LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    state, rows, current = "no marker", [], None
    for line in lines:
        if "PUSS_SOFTGOODS_CLOTH_GATE|" in line:
            parts = line.split("PUSS_SOFTGOODS_CLOTH_GATE|", 1)[1].split("|")
            mode, comps = parts[0], parts[-1]
            if mode.startswith("set_") or state == "no marker":
                state = {"set_suspend": "suspended", "set_disable": "disabled", "set_restore": "restored"}.get(mode, "baseline")
            state_detail = comps[:120]
            continue
        if "Cmd: stat dumpframe" in line:
            current = {"state": state, "cloth_ms": None, "cloth_n": None, "stall_ms": None, "world_tick_ms": None}
            rows.append(current)
            continue
        m = STAT.search(line)
        if not m or current is None:
            continue
        ms, n, name = float(m.group(1)), int(m.group(2)), m.group(3)
        if name.startswith("FChaosClothComponentEndTickFunction") and current["cloth_ms"] is None:
            current["cloth_ms"], current["cloth_n"] = ms, n
        elif name.startswith("CPU Stall - Wait For Event") and current["cloth_ms"] is not None and current["stall_ms"] is None:
            current["stall_ms"] = ms
        elif name.startswith("World Tick Time") and current["world_tick_ms"] is None:
            current["world_tick_ms"] = ms
    print(f"{'state':<11} {'cloth end-tick ms':>18} {'(n)':>5} {'stall ms':>9} {'world tick ms':>14}")
    for r in rows:
        cloth = f"{r['cloth_ms']:.3f}" if r["cloth_ms"] is not None else "absent (<1 ms)"
        print(f"{r['state']:<11} {cloth:>18} {str(r['cloth_n'] or ''):>5} {str(r['stall_ms'] or ''):>9} {str(r['world_tick_ms'] or ''):>14}")


if __name__ == "__main__":
    main()
