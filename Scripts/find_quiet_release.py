"""Pick a release frame for a re-run of a drop bake from the bake's OWN pre-release motion series (30 Sep, bake B).

    python Scripts/find_quiet_release.py <bake_id> [--limit 1.5] [--window 30] [--earliest 240]

Why: the hang does not settle smoothly; it SURGES (final9: 2.0-2.9 mm/frame for 10-20 frames between quiet spells of
0.4-0.6, peaks decaying about 0.2 mm per 100 frames). The show freezes sample R-1, so the frozen pose must come from a
settled moment, and on a surging series those are the troughs. Before the release the solve does not depend on the
release frame (the rest switch, the hem-guide release and any damping change are all keyed AT the release), so a re-run
with an earlier release should repeat the pre-release frames exactly IF the solver is run-to-run deterministic (unproven:
the re-run tests it, see --compare below).

A candidate R' needs every frame of [R'-window, R'-1] under --limit (a margin below the 2.0 mm gate), R' <= the original
release, and R' >= --earliest (the drape must have formed). Among candidates the LOWEST window max wins (margin, in
case the re-run is not bit-identical), and among those within 0.1 mm of it the LATEST R' (the most settled history).
"Latest wins" alone picked final9's 416-445 at 1.49 mm when 412-441 held 0.71.
Prints QUIET_RELEASE|<R'>|window_max=<mm>|... or QUIET_RELEASE|none.

    python Scripts/find_quiet_release.py --compare <original_id> <rerun_id>

compares the two runs' still_mm over the re-run's pre-release frames, and prints DETERMINISM|identical|max_diff=0 or
DETERMINISM|differs|first_frame=<f>|max_diff=<mm>.
"""
import argparse
import json
from pathlib import Path

DROP = Path(__file__).resolve().parents[1] / "Saved" / "CodexSoftGoods" / "DropBake"


def series(bake_id):
    d = json.loads((DROP / f"{bake_id}.json").read_text(encoding="utf-8"))
    return d, {int(f): float(m) for f, m in d["still_mm"]}


def find(bake_id, limit, window, earliest):
    d, s = series(bake_id)
    release = int(d["release_frame"])
    cands = []
    for r in range(earliest, release + 1):
        frames = range(r - window, r)
        if all(f in s for f in frames):
            wmax = max(s[f] for f in frames)
            if wmax < limit:
                cands.append((r, wmax))
    best = None
    if cands:
        floor = min(w for _, w in cands)
        best = max((c for c in cands if c[1] <= floor + 0.1), key=lambda c: c[0])
    if best is None:
        print(f"QUIET_RELEASE|none|no {window}-frame window under {limit} mm between {earliest} and {release}")
        return
    r, wmax = best
    print(f"QUIET_RELEASE|{r}|window_max={wmax:.2f}|window={r - window}-{r - 1}|frozen_sample={r - 1}"
          f"|original_release={release}|original_window_max={d.get('still_window_max_mm')}")


def compare(original, rerun):
    _, a = series(original)
    d, b = series(rerun)
    release = int(d["release_frame"])
    frames = [f for f in sorted(b) if f < release and f in a]
    diffs = [(f, abs(a[f] - b[f])) for f in frames]
    worst = max((x for _, x in diffs), default=0.0)
    first = next((f for f, x in diffs if x > 0), None)
    print(f"DETERMINISM|{'identical' if first is None else 'differs'}|frames_compared={len(frames)}"
          f"|max_diff={worst:.3f}" + (f"|first_frame={first}" if first is not None else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="+")
    ap.add_argument("--limit", type=float, default=1.5)
    ap.add_argument("--window", type=int, default=30)
    ap.add_argument("--earliest", type=int, default=240)
    ap.add_argument("--compare", action="store_true")
    a = ap.parse_args()
    if a.compare:
        compare(a.ids[0], a.ids[1])
    else:
        find(a.ids[0], a.limit, a.window, a.earliest)


if __name__ == "__main__":
    main()
