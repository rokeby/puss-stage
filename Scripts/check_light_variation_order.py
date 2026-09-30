"""Offline, read-only (29 Sep): did any SAVED light come through UInfinityStageShowAsset::ReplicateLightAttachmentsWithVariation,
and if so, which argument-evaluation order produced it? Input: Saved/CodexSoftGoods/wingpair_lights.json (from
Saved/CodexSoftGoods/dump_wingpair_lights.py).

The function draws three jitters as FVector(...) arguments and three more as FRotator(...) arguments. C++ leaves argument
order unspecified, so the order is the compiler's choice. This reproduces UE 5.8 exactly:
  seed   = uint32(CityHash64(FGuid bytes)) ^ Variation.Seed        (Guid.h: GetTypeHash; the Cue Desk uses Seed 0)
  FRand  = LCG seed*196314165 + 907633515, then float(0x3F800000 | seed >> 9) - 1   (RandomStream.h)
  range  = Min + (Max - Min) * FRand, in double (FVector::FReal)
and for each cue asks: does some OTHER cue's light list plus this cue's simulated translation jitter reproduce this cue's
saved translations? It tests left-to-right (X,Y,Z) and right-to-left (Z,Y,X) orders at the default 25 cm jitter.
"""
import json
import struct
import sys
from pathlib import Path

M64 = (1 << 64) - 1
K2 = 0x9AE16A3B2F90404F
ROOT = Path(__file__).resolve().parents[1]


def rot(v, s):
    return v if s == 0 else ((v >> s) | (v << (64 - s))) & M64


def hash_len16(u, v, mul):
    a = ((u ^ v) * mul) & M64
    a ^= a >> 47
    b = ((v ^ a) * mul) & M64
    b ^= b >> 47
    return (b * mul) & M64


def city_hash64_16(data):
    """CityHash64 for a 16-byte input (the HashLen0to16 branch, len >= 8)."""
    n = len(data)
    mul = (K2 + n * 2) & M64
    a = (struct.unpack_from("<Q", data, 0)[0] + K2) & M64
    b = struct.unpack_from("<Q", data, n - 8)[0]
    c = (rot(b, 37) * mul + a) & M64
    d = ((rot(a, 25) + b) * mul) & M64
    return hash_len16(c, d, mul)


def guid_bytes(hex32):
    return b"".join(struct.pack("<I", int(hex32[i:i + 8], 16)) for i in range(0, 32, 8))


class Stream:
    def __init__(self, seed):
        self.s = seed & 0xFFFFFFFF

    def frand(self):
        self.s = (self.s * 196314165 + 907633515) & 0xFFFFFFFF
        return struct.unpack("<f", struct.pack("<I", 0x3F800000 | (self.s >> 9)))[0] - 1.0

    def range(self, lo, hi):
        return lo + (hi - lo) * self.frand()


def simulated_translation_jitter(cue_guid, count, order, p=25.0, seed=0):
    st = Stream(city_hash64_16(guid_bytes(cue_guid)) ^ seed)
    out = []
    for _ in range(count):
        d = [st.range(-p, p) for _ in range(3)]          # the FVector draws, in draw order
        [st.range(-3.0, 3.0) for _ in range(3)]           # the FRotator draws (consumed)
        st.range(0.8, 1.2)                                # the intensity draw (its own statement)
        out.append(d if order == "LTR" else d[::-1])
    return out


def main():
    data = json.loads((ROOT / "Saved" / "CodexSoftGoods" / "wingpair_lights.json").read_text(encoding="utf-8"))
    cues = data["cues"]
    by_count = {}
    for c in cues:
        by_count.setdefault(len(c["lights"]), []).append(c)
    exact_copies, matches = 0, {"LTR": [], "RTL": []}
    for c in cues:
        peers = [o for o in by_count[len(c["lights"])] if o is not c]
        if any(all(abs(a - b) < 1e-4 for la, lb in zip(c["lights"], o["lights"]) for a, b in zip(la["t"], lb["t"]))
               for o in peers):
            exact_copies += 1
        for order in ("LTR", "RTL"):
            jit = simulated_translation_jitter(c["guid"], len(c["lights"]), order)
            for o in peers:
                if all(abs(la["t"][k] - (lb["t"][k] + j[k])) < 1e-2
                       for la, lb, j in zip(c["lights"], o["lights"], jit) for k in range(3)):
                    matches[order].append((c["label"], o["label"]))
                    break
    print(f"wing pairs with lights: {len(cues)}; lights: {sum(len(c['lights']) for c in cues)}")
    print(f"cues whose lights EXACTLY copy another cue's (plain replication): {exact_copies}")
    for order, rows in matches.items():
        print(f"cues reproduced as a jittered copy with {order} order: {len(rows)}  e.g. {rows[:3]}")
    if not matches["LTR"] and not matches["RTL"]:
        print("VERDICT: no saved light reproduces as a variation copy in either order, so applying a pinned order re-rolls nothing.")
    elif matches["LTR"] and not matches["RTL"]:
        print("VERDICT: saved data was generated LEFT-TO-RIGHT; pin X,Y,Z / Pitch,Yaw,Roll in that order.")
    elif matches["RTL"] and not matches["LTR"]:
        print("VERDICT: saved data was generated RIGHT-TO-LEFT; pin Z,Y,X / Roll,Yaw,Pitch in that order.")
    else:
        print("VERDICT: BOTH orders appear, so different binaries generated different cues. Pin per history, and ask.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
