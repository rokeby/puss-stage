"""Name-keyed diff of two s3_seq_sem.py models. Usage: python sem_diff.py a.json b.json"""
import json
import sys
from collections import defaultdict

a, b = (json.load(open(x)) for x in sys.argv[1:3])


def strip(s):
    s = dict(s)
    s.pop("export", None)
    return s


def key_tracks(m):
    out = defaultdict(list)
    for t in m["tracks"]:
        out[(t.get("guid"), t["cls"], str(t["prop"]))].append(t)
    return out


print("MOVIE a", a["movie"])
print("MOVIE b", b["movie"])
ba, bb = {v["full"] for v in a["bindings"].values()}, {v["full"] for v in b["bindings"].values()}
print("BINDINGS removed:", sorted(ba - bb))
print("BINDINGS added:", sorted(bb - ba))
A, B = key_tracks(a), key_tracks(b)
for k in sorted(set(A) | set(B), key=str):
    ta, tb = A.get(k, []), B.get(k, [])
    if not ta:
        for t in tb:
            print("TRACK ADDED", k, t["owner"], json.dumps([[s["range"], s["props"]] for s in t["sections"]])[:900])
        continue
    if not tb:
        for t in ta:
            print("TRACK REMOVED", k, t["owner"], json.dumps([[s["range"], s["props"]] for s in t["sections"]])[:900])
        continue
    if len(ta) != len(tb):
        print("TRACK COUNT", k, len(ta), len(tb))
    for x, y in zip(ta, tb):
        if x["owner"] != y["owner"]:
            print("OWNER RENAMED", k, x["owner"], "->", y["owner"])
        if x["track_props"] != y["track_props"]:
            print("TRACKPROPS", k, json.dumps(x["track_props"])[:300], "->", json.dumps(y["track_props"])[:300])
        sa, sb = x["sections"], y["sections"]
        if len(sa) != len(sb):
            print("SECTIONS COUNT", k, len(sa), len(sb))
        for i, (s1, s2) in enumerate(zip(sa, sb)):
            if s1["range"] != s2["range"]:
                print("RANGE", k, i, s1["range"], "->", s2["range"])
            p1, p2 = s1["props"], s2["props"]
            for pk in sorted(set(p1) | set(p2)):
                if p1.get(pk) != p2.get(pk):
                    print("PROP", k, i, pk, "\n    was", json.dumps(p1.get(pk))[:700], "\n    now",
                          json.dumps(p2.get(pk))[:700])
        for s in sb[len(sa):]:
            print("SECTION ADDED", k, s["range"], json.dumps(s["props"])[:600])
        for s in sa[len(sb):]:
            print("SECTION REMOVED", k, s["range"], json.dumps(s["props"])[:600])
ma, mb = a.get("marked") or [], b.get("marked") or []
print("MARKED a n=%s b n=%s" % (len(ma) if isinstance(ma, list) else ma, len(mb) if isinstance(mb, list) else mb))
if isinstance(ma, list) and isinstance(mb, list):
    fa = [(m.get("FrameNumber"), m.get("Label")) for m in ma]
    fb = [(m.get("FrameNumber"), m.get("Label")) for m in mb]
    print("  removed:", [x for x in fa if x not in fb])
    print("  added:", [x for x in fb if x not in fa])
