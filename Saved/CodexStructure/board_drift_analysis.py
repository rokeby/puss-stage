"""OFFLINE (plain Python, not Unreal): explain the 29 Sep board-count drift.

Re-lays every ground lane from board_dump.json exactly as
AInfinityStageStructureActor::BuildGround does. The seed is
HashCombineFast(HashCombineFast(CityHash64(PassageGuid), BoardLane=4), Lane), and
FRandomStream is its LCG with 23-bit fractions, both per the UE 5.8 headers. The
lane loop is done twice, once for each order in which the compiler may evaluate
the two draws of
    Stream.FRandRange(Min, Max) * Stream.FRandRange(0.2, 1.0)
(C++ leaves the evaluation order of the operands of * unspecified). Start, end and
the slot cuts are read off the current boards (a slot leaves an 8 cm gap; the next
board starts at cut + half slot).
"""
import json
import math
import os
import sys

M32, M64 = 0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF
K2 = 0x9AE16A3B2F90404F
OLD = {"Infinity Stage - Structure 01": 7170, "Infinity Stage - Structure 02": 2615, "Infinity Stage - Structure 04": 2915,
       "Infinity Stage - Structure 05": 6381, "Infinity Stage - Structure 06": 7068}


def rot(v, s):
    return v if s == 0 else ((v >> s) | (v << (64 - s))) & M64


def city64_16(b):   # CityHash64 (v1.1 HashLen0to16) for a 16-byte key
    mul = (K2 + 32) & M64
    a = (int.from_bytes(b[0:8], "little") + K2) & M64
    bb = int.from_bytes(b[8:16], "little")
    c = (rot(bb, 37) * mul + a) & M64
    d = ((rot(a, 25) + bb) * mul) & M64
    x = ((c ^ d) * mul) & M64
    x ^= x >> 47
    y = ((d ^ x) * mul) & M64
    y ^= y >> 47
    return (y * mul) & M64


def hcf(a, b):
    return (a ^ ((b + 0x9E3779B9 + (a << 6) + (a >> 2)) & M32)) & M32


def guid_bytes(s):
    return b"".join(int(s[i:i + 8], 16).to_bytes(4, "little") for i in range(0, 32, 8))


def lay(seed, start, end, cuts, order, g):
    s = [seed]

    def frand():
        s[0] = (s[0] * 196314165 + 907633515) & M32
        return (s[0] >> 9) / 8388608.0

    def rr(a, b):
        return a + (b - a) * frand()

    mn = max(20.0, min(g["min_board_length_cm"], g["max_board_length_cm"]))
    mx = max(mn, g["max_board_length_cm"])
    gap, half = max(0.0, g["board_gap_cm"]), max(1.0, g["slot_width_cm"]) * 0.5
    if order == "left-first":
        x = rr(mn, mx)
        y = rr(0.2, 1.0)
    else:
        y = rr(0.2, 1.0)
        x = rr(mn, mx)
    nxt, frm, ci, out = x * y, start, 0, []
    while frm < end - 1.0:
        while ci < len(cuts) and cuts[ci] + half <= frm:
            ci += 1
        to = min(frm + nxt, end)
        nf = to + gap
        if ci < len(cuts) and cuts[ci] - half < to:
            to, nf = cuts[ci] - half, cuts[ci] + half
            ci += 1
        if to - frm >= 1.0:
            out.append((frm, to, frand()))
        frm = nf
        nxt = rr(mn, mx)
    return out


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    dump = json.load(open(os.path.join(here, "board_dump.json")))
    report = {}
    for label, st in dump.items():
        g = st["ground"]
        width, gap = max(4.0, g["board_width_cm"]), max(0.0, g["board_gap_cm"])
        pitch, half = width + gap, max(1.0, g["slot_width_cm"]) * 0.5
        lanes_n = max(1, math.floor((st["grid_half_width_cm"] * 2.0 + gap) / pitch))
        first = -(lanes_n * pitch - gap) * 0.5 + width * 0.5
        lanes = {}
        for d, lat, tone, length, _w, _t in st["boards"]:
            lanes.setdefault(round((lat - first) / pitch), []).append((d - length / 2, d + length / 2, tone))
        for v in lanes.values():
            v.sort()
        start = min(v[0][0] for v in lanes.values())
        end = max(v[-1][1] for v in lanes.values())
        gh = city64_16(guid_bytes(st["passage_guid"])) & M32
        base = hcf(gh, 4)
        totals = {"left-first": 0, "right-first": 0}
        match = {"left-first": 0, "right-first": 0}
        lane_diff = {}
        for lane, boards in sorted(lanes.items()):
            cuts = [b[0] - half for a, b in zip(boards, boards[1:]) if b[0] - a[1] > 1.5]
            seed = hcf(base, lane & M32)
            for order in totals:
                sim = lay(seed, start, end, cuts, order, g)
                totals[order] += len(sim)
                same = len(sim) == len(boards) and all(abs(p[0] - q[0]) < 0.05 and abs(p[1] - q[1]) < 0.05 and abs(p[2] - q[2]) < 1e-6
                                                       for p, q in zip(sim, boards))
                match[order] += same
            lane_diff[lane] = None
        report[label] = {"lanes": len(lanes), "actual": len(st["boards"]), "old": OLD.get(label),
                         "simulated": totals, "lanes_reproduced_exactly": match, "start_cm": round(start, 2), "end_cm": round(end, 2),
                         "route_length_cm": round(st["route_length_cm"], 2)}
        print(label[-12:], json.dumps(report[label]))
    json.dump(report, open(os.path.join(here, "board_drift_analysis.json"), "w"), indent=1)


if __name__ == "__main__":
    sys.exit(main())
