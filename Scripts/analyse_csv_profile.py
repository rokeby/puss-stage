"""Split a CsvProfiler capture's slow frames by thread and rank what grows on them (29 Sep stutter hunt). Reads only.

    python Scripts/analyse_csv_profile.py [path/to/Profile(...).csv]      (default: the newest in Saved/Profiling/CSV)

Prints: frames, slow (> 40 ms) vs fast (<= 25 ms) medians for FrameTime / Game / Render / RHI / GPU, the columns that
GROW most on slow frames, and the onsets of slow-frame clusters with the gaps between them. On 29 Sep this showed the
GPU flat (~15 ms) while every CPU thread's scopes inflated together on spike frames.
"""
import csv
import glob
import os
import statistics
import sys


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else max(glob.glob("Saved/Profiling/CSV/*.csv"), key=os.path.getmtime)
    rows = list(csv.reader(open(path, encoding="utf-8", errors="replace")))
    head = rows[0]
    data = [r for r in rows[1:] if len(r) >= len(head) - 2]

    def col(j):
        out = []
        for r in data:
            try:
                out.append(float(r[j]))
            except (ValueError, IndexError):
                out.append(float("nan"))
        return out

    ft = col(head.index("FrameTime"))
    slow = [i for i, v in enumerate(ft) if v == v and v > 40]
    fast = [i for i, v in enumerate(ft) if v == v and v <= 25]
    print(f"{os.path.basename(path)}: {len(ft)} frames, {len(slow)} over 40 ms, {len(fast)} at or under 25 ms")
    for name in ("FrameTime", "GameThreadTime", "RenderThreadTime", "RHIThreadTime", "GPUTime"):
        if name in head:
            v = col(head.index(name))
            s = [v[i] for i in slow if v[i] == v[i]]
            n = [v[i] for i in fast if v[i] == v[i]]
            if s and n:
                print(f"  {name:18} fast {statistics.median(n):7.2f}  SLOW {statistics.median(s):7.2f}  max {max(s):7.2f}")
    growth = []
    for j, name in enumerate(head):
        if not name or name == "EVENTS" or name.startswith(("CsvProfiler/", "Memory", "System")):
            continue
        v = col(j)
        s = [v[i] for i in slow if v[i] == v[i]]
        n = [v[i] for i in fast if v[i] == v[i]]
        if len(s) >= 5 and len(n) >= 5:
            growth.append((statistics.median(s) - statistics.median(n), name, statistics.median(n), statistics.median(s), max(s)))
    print("  grows most on slow frames:")
    for d, name, mf, ms, mx in sorted(growth, reverse=True)[:14]:
        print(f"    +{d:7.2f}  {name:58} fast {mf:7.2f} slow {ms:7.2f} max {mx:7.2f}")
    t, onsets, last = 0.0, [], -10
    for i, v in enumerate(ft):
        if v == v and v > 40 and i - last > 3:
            onsets.append(round(t / 1000, 2))
        if v == v and v > 40:
            last = i
        t += v if v == v else 0
    print("  cluster onsets (s):", onsets, "gaps:", [round(b - a, 2) for a, b in zip(onsets, onsets[1:])])


if __name__ == "__main__":
    main()
