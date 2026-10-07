"""Semantic offline dump of a LevelSequence (UE5 1018) -> name-keyed model independent of FName/export indices.
Read-only (opens the .uasset for reading only). Reuses the KlaraIngest minimal reader
(Saved/CodexConductor/KlaraIngest/test_klara_void_s6_offline.py). Usage: python s3_seq_sem.py <uasset> <out.json>"""
import hashlib
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "KlaraIngest"))
import test_klara_void_s6_offline as V  # noqa: E402


def h(b):
    return hashlib.sha1(b).hexdigest()[:12]


def read_tag(p, r):
    nm = p.fname(r)
    if nm == "None":
        return None
    t = p.typename(r)
    size = r.i32()
    fl = r.raw(1)[0]
    ai = r.i32() if fl & 1 else 0
    if fl & 2:
        r.raw(16)
    if fl & 4:
        ext = r.raw(1)[0]
        if ext & 2:
            r.raw(2)
    return nm, t, fl, ai, r.raw(size)


def tags_until_none(p, data, off=0):
    r = V.R(data, off)
    out = []
    while True:
        tg = read_tag(p, r)
        if tg is None:
            return out, r.o
        out.append(tg)


def channel(v, ty):
    try:
        r = V.R(v, 2)
        es = r.i32()
        n = r.i32()
        if es != 4 or not (0 <= n < 500000):
            raise ValueError
        times = [r.i32() for _ in range(n)]
        ves, nv = r.i32(), r.i32()
        vals = []
        for _ in range(nv):
            raw = v[r.o:r.o + ves]
            r.o += ves
            if "Double" in ty:
                vals.append(round(struct.unpack_from("<d", raw)[0], 4))
            elif "Float" in ty:
                vals.append(round(struct.unpack_from("<f", raw)[0], 4))
            else:
                vals.append(raw.hex())
        rest = v[r.o:]
        return {"n": n, "t": [times[0], times[-1]] if times else None,
                "times_h": h(struct.pack("<%di" % n, *times)), "vals_h": h(json.dumps(vals).encode()),
                "first": vals[0] if vals else None, "last": vals[-1] if vals else None,
                "tail": rest.hex() if len(rest) <= 24 else h(rest),
                "times": times if n <= 16 else None, "vals": vals if n <= 16 else None}
    except Exception:
        return {"opaque": h(v), "len": len(v), "hex": v.hex() if len(v) <= 200 else None}


def dec(p, ty, v, fl=0):
    try:
        if ty.startswith("IntProperty"):
            return struct.unpack("<i", v[:4])[0]
        if ty.startswith("FloatProperty"):
            return round(struct.unpack("<f", v[:4])[0], 5)
        if ty.startswith("DoubleProperty"):
            return round(struct.unpack("<d", v[:8])[0], 5)
        if ty.startswith("BoolProperty"):
            return {"boolflags": fl}
        if ty.startswith(("NameProperty", "EnumProperty")):
            return p.fname(V.R(v))
        if ty.startswith("ByteProperty"):
            return p.fname(V.R(v)) if len(v) == 8 else v[0]
        if ty.startswith("StrProperty"):
            return V.R(v).fstr()
        if ty.startswith(("ObjectProperty", "SoftObjectProperty")):
            i = struct.unpack_from("<i", v, 0)[0]
            return p.path(i) if i else None
        if "Channel" in ty and ty.startswith("StructProperty"):
            return {"chan": channel(v, ty)}
        if ty.startswith("StructProperty(Guid"):
            return v.hex()
        if ty.startswith("StructProperty(FrameNumber"):
            return struct.unpack("<i", v[:4])[0]
        if ty.startswith("StructProperty("):
            tg, end = tags_until_none(p, v)
            if end != len(v):
                return {"opaque": h(v), "hex": v.hex() if len(v) <= 64 else None}
            return {t[0] + ("[%d]" % t[3] if t[3] else ""): dec(p, t[1], t[4], t[2]) for t in tg}
        if ty.startswith("ArrayProperty("):
            n = struct.unpack_from("<i", v, 0)[0]
            inner = ty[len("ArrayProperty("):-1]
            if inner.startswith("ObjectProperty"):
                return [p.path(struct.unpack_from("<i", v, 4 + 4 * k)[0]) for k in range(n)]
            if inner.startswith("StructProperty("):
                out, o = [], 4
                for _ in range(n):
                    tg, o = tags_until_none(p, v, o)
                    out.append({t[0] + ("[%d]" % t[3] if t[3] else ""): dec(p, t[1], t[4], t[2]) for t in tg})
                return out if o == len(v) else {"opaque": h(v), "n": n}
            if inner.startswith("NameProperty"):
                r = V.R(v, 4)
                return [p.fname(r) for _ in range(n)]
            return {"opaque": h(v), "n": n}
    except Exception as e:
        return {"err": repr(e)[:80], "opaque": h(v)}
    return {"opaque": h(v), "type": ty}


SKIP = {"EvaluationField", "EvaluationFieldGuid", "Signature", "EvaluationFieldVersion", "EaseInFunction",
        "EaseOutFunction"}


class Model:
    def __init__(self, path):
        self.p = p = V.Package(path)
        self.by_path = {p.path(i): i for i in range(1, len(p.exports) + 1)}

    def props(self, i):
        p = self.p
        e = p.exports[i - 1]
        data = p.b[e["so"]:e["so"] + e["ss"]]
        r = V.R(data)
        ctl = r.raw(1)[0]
        if ctl & 2:
            r.raw(1)
        out = {}
        while r.o < len(data):
            tg = read_tag(p, r)
            if tg is None:
                break
            if tg[0] in SKIP:
                continue
            k = tg[0] + ("[%d]" % tg[3] if tg[3] else "")
            if tg[0] in ("SectionRange", "PlaybackRange"):
                out[k] = V.frange(tg[4])
            else:
                out[k] = dec(p, tg[1], tg[4], tg[2])
        return out

    def track(self, ti, owner):
        p = self.p
        i = self.by_path[ti]
        tp = self.props(i)
        secs = []
        for sp in tp.get("Sections", []) or []:
            si = self.by_path[sp]
            sprops = self.props(si)
            ea = sprops.pop("Easing", None)
            if isinstance(ea, dict):
                sprops["Easing"] = {k: v for k, v in ea.items() if k not in ("EaseIn", "EaseOut")}
            secs.append({"cls": p.cls(si), "range": sprops.pop("SectionRange", None), "props": sprops, "export": sp})
        pb = tp.get("PropertyBinding", {})
        return {"owner": owner, "cls": p.cls(i), "prop": pb.get("PropertyPath") if isinstance(pb, dict) else None,
                "sections": secs, "export": ti,
                "track_props": {k: v for k, v in tp.items() if k not in ("Sections", "PropertyBinding")}}

    def build(self):
        p = self.p
        ms = [i for i in range(1, len(p.exports) + 1) if p.cls(i) == "MovieScene"][0]
        M = self.props(ms)
        names = {}
        for row in M.get("Possessables", []) or []:
            names[row.get("Guid")] = {"name": row.get("Name"), "kind": "poss", "parent": row.get("ParentGuid")}
        sp = M.get("Spawnables", [])
        for row in sp if isinstance(sp, list) else []:
            names[row.get("Guid")] = {"name": row.get("Name"), "kind": "spawn", "template": row.get("ObjectTemplate")}

        def gname(g):
            n = names.get(g)
            if not n:
                return "?" + str(g)[:8]
            par = n.get("parent")
            pn = names.get(par, {}).get("name") if par and par != "00" * 16 else None
            return (str(pn) + "/" if pn else "") + str(n["name"])

        tracks = []
        for b in M.get("ObjectBindings", []) or []:
            g = b.get("ObjectGuid")
            for ti in b.get("Tracks", []) or []:
                tracks.append(dict(self.track(ti, gname(g)), guid=g))
        for k in ("Tracks", "CameraCutTrack"):
            v = M.get(k)
            for ti in (v if isinstance(v, list) else [v] if v else []):
                tracks.append(dict(self.track(ti, "<master>"), guid="master"))
        movie = {k: M.get(k) for k in ("PlaybackRange", "TickResolution", "DisplayRate", "EvaluationType",
                                       "ClockSource")}
        return {"file": self.p and "", "sha256": hashlib.sha256(p.b).hexdigest(), "movie": movie,
                "bindings": {g: dict(names[g], full=gname(g)) for g in names},
                "marked": M.get("MarkedFrames"), "tracks": tracks}


if __name__ == "__main__":
    m = Model(sys.argv[1]).build()
    m["file"] = sys.argv[1]
    with open(sys.argv[2], "w") as f:
        json.dump(m, f, indent=1, default=str)
    print("ok", len(m["tracks"]), "tracks", len(m["bindings"]), "bindings")
