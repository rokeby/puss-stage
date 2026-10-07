"""Offline dump of a LevelSequence .uasset (UE5 1018) using the KlaraIngest minimal reader. Read-only.
Usage: python s3_seq_dump.py <uasset> <out.json>"""
import hashlib, json, os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "KlaraIngest"))
import test_klara_void_s6_offline as V  # noqa

def times_of(v):
    """Native channel prefix: pre u8, post u8, Times(elemsize, n, int32[])."""
    try:
        r = V.R(v, 2)
        es = r.i32(); n = r.i32()
        if es != 4 or n < 0 or n > 200000:
            return None
        return [r.i32() for _ in range(n)]
    except Exception:
        return None

def bool_vals(v, n):
    # after times: Values (elemsize, n, bool as ...)
    try:
        r = V.R(v, 2); r.i32(); nt = r.i32(); r.o += 4 * nt
        es, nv = r.i32(), r.i32()
        vals = []
        for _ in range(nv):
            vals.append(v[r.o:r.o+es].hex()); r.o += es
        tail = v[r.o:].hex()
        return {"es": es, "vals": vals, "tail": tail}
    except Exception as e:
        return {"err": str(e)}

def dump(path):
    p = V.Package(path)
    out = []
    for i in range(1, len(p.exports) + 1):
        c = p.cls(i)
        row = {"i": i, "path": p.path(i), "cls": c, "props": {}}
        try:
            tags = p.props(i)
        except Exception as e:
            row["err"] = repr(e); out.append(row); continue
        for t in tags:
            k = t["name"] + ("[%d]" % t["index"] if t["index"] else "")
            v = t["value"]; ty = t["type"]
            if t["name"] in ("SectionRange", "PlaybackRange", "SelectionRange"):
                val = V.frange(v)
            elif "Channel" in ty:
                tm = times_of(v)
                val = {"type": ty.split("(")[-1].rstrip(")"), "n": None if tm is None else len(tm),
                       "span": None if not tm else [tm[0], tm[-1]], "times": tm if tm and len(tm) <= 12 else None,
                       "sha": hashlib.sha1(v).hexdigest()[:12]}
                if "Bool" in ty or "Byte" in ty or "Integer" in ty:
                    val["vals"] = bool_vals(v, tm)
            elif ty.startswith("ObjectProperty") or ty.startswith("SoftObjectProperty"):
                idx = struct.unpack_from("<i", v, 0)[0]
                try:
                    val = p.path(idx) if idx else None
                except Exception:
                    val = v.hex()
            elif ty.startswith("IntProperty"):
                val = struct.unpack("<i", v[:4])[0]
            elif ty.startswith("FloatProperty"):
                val = struct.unpack("<f", v[:4])[0]
            elif ty.startswith("DoubleProperty"):
                val = struct.unpack("<d", v[:8])[0]
            elif ty.startswith("BoolProperty"):
                val = True  # serialised value lives in flags in new format; presence noted
                val = {"flags": t["flags"], "raw": v.hex()}
            elif ty.startswith("NameProperty") or ty.startswith("EnumProperty") or ty.startswith("ByteProperty"):
                try:
                    val = p.fname(V.R(v)) if len(v) >= 8 else v.hex()
                except Exception:
                    val = v.hex()
            elif ty.startswith("StrProperty"):
                val = V.R(v).fstr()
            elif ty.startswith("ArrayProperty(ObjectProperty") :
                n = struct.unpack_from("<i", v, 0)[0]
                val = [p.path(struct.unpack_from("<i", v, 4 + 4*k)[0]) for k in range(n)]
            elif ty.startswith("StructProperty") and len(v) <= 400:
                try:
                    sub = p.tags(v, top=False)
                    val = {"type": ty, "sub": {s["name"]: (s["value"].hex() if len(s["value"]) <= 32 else hashlib.sha1(s["value"]).hexdigest()[:12]) for s in sub}, "raw": v.hex() if len(v) <= 64 else None}
                except Exception:
                    val = {"type": ty, "raw": v.hex()}
            else:
                val = {"type": ty, "len": len(v), "sha": hashlib.sha1(v).hexdigest()[:12]}
            row["props"][k] = val
        out.append(row)
    return {"file": path, "sha256": hashlib.sha256(p.b).hexdigest(), "names": len(p.names), "exports": len(p.exports), "rows": out}

if __name__ == "__main__":
    d = dump(sys.argv[1])
    json.dump(d, open(sys.argv[2], "w"), indent=1, default=str)
    print("ok", sys.argv[2], d["exports"])
