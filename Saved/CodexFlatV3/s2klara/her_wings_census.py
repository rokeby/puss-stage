"""Offline, read-only census of Klara's S2 wings (8 Oct, F12). System Python only: no Unreal, no MCP, writes only
her_wings_census.json next to this file. Reuses the minimal UE5 (1018) package reader from
Saved/CodexConductor/KlaraIngest/test_klara_void_s6_offline.py (class Package) - imported, not modified.

Reads: Content/Japanese_Alley/Maps/Japanese_Alley.umap (actors + their StaticMeshComponent mesh/transform/materials),
Content/KK_S2_Shrine/LS_NEW_SHRINE.uasset (which actors her sequence binds/animates)."""
import importlib.util
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RDR = os.path.join(PROJECT, "Saved", "CodexConductor", "KlaraIngest", "test_klara_void_s6_offline.py")
UMAP = os.path.join(PROJECT, "Content", "Japanese_Alley", "Maps", "Japanese_Alley.umap")
LS = os.path.join(PROJECT, "Content", "KK_S2_Shrine", "LS_NEW_SHRINE.uasset")

spec = importlib.util.spec_from_file_location("pkgreader", RDR)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
Package, R = m.Package, m.R

KEYS = ("wing", "mudtower", "hay", "slimy", "moss", "rope", "shrine")


def objref(p, v):
    i = struct.unpack_from("<i", v, 0)[0]
    return p.path(i) if i else None


def comp_info(p, ci):
    out = {}
    for t in p.props(ci):
        n = t["name"]
        v = t["value"]
        if n == "StaticMesh":
            out["mesh"] = objref(p, v)
        elif n in ("RelativeLocation", "RelativeScale3D"):
            out[n] = [round(x, 2) for x in struct.unpack_from("<ddd", v, 0)]
        elif n == "RelativeRotation":
            out[n] = [round(x, 3) for x in struct.unpack_from("<ddd", v, 0)]  # pitch, yaw, roll
        elif n == "OverrideMaterials":
            c = struct.unpack_from("<i", v, 0)[0]
            out[n] = [objref(p, v[4 + 4 * k:]) for k in range(c)]
        elif n in ("bVisible", "bHiddenInGame", "CastShadow", "Mobility", "AttachParent"):
            out[n] = v.hex() if n != "AttachParent" else objref(p, v)
    return out


def main():
    p = Package(UMAP)
    rows = []
    for i in range(1, len(p.exports) + 1):
        cls = p.cls(i)
        if cls not in ("StaticMeshComponent",):
            continue
        info = comp_info(p, i)
        mesh = info.get("mesh") or ""
        owner = p.path(p.exports[i - 1]["outer"]) if p.exports[i - 1]["outer"] else None
        if not any(k in mesh.lower() for k in KEYS) and not any(k in (owner or "").lower() for k in KEYS):
            continue
        # actor-level props (bHidden, label not saved in cooked? editor packages keep ActorLabel)
        aprops = {}
        oi = p.exports[i - 1]["outer"]
        if oi > 0:
            for t in p.props(oi):
                if t["name"] == "ActorLabel":
                    aprops["label"] = R(t["value"]).fstr()
                elif t["name"] in ("bHidden", "bHiddenEd"):
                    aprops[t["name"]] = t["value"].hex() if t["value"] else "flag:%d" % t["flags"]
                elif t["name"] == "Tags":
                    aprops["tags_bytes"] = len(t["value"])
        rows.append({"export": i, "component": p.path(i), "actor": owner, "actor_class": p.cls(oi) if oi > 0 else None,
                     **aprops, **info})
    # her sequence: possessable names
    seq = {}
    try:
        q = Package(LS)
        names = set()
        for i in range(1, len(q.exports) + 1):
            if q.cls(i) == "MovieScene":
                for t in q.props(i):
                    if t["name"] == "PlaybackRange":
                        seq["playback_tick"] = m.frange(t["value"])
        her = m  # noqa
        seq["names_with_wing"] = sorted({n for n in q.names if "ing" in n.lower() and "_" in n and "Wing" in n
                                         or "ceiling" in n.lower()})
        seq["package_name"] = q.name
    except Exception as e:  # report, do not guess
        seq["error"] = repr(e)
    out = {"tool": "her_wings_census", "umap": UMAP, "ls": LS, "n_exports": len(p.exports), "rows": rows, "seq": seq}
    json.dump(out, open(os.path.join(HERE, "her_wings_census.json"), "w"), indent=1)
    for r in rows:
        print(r["actor"], r.get("label"), r.get("actor_class"), r.get("mesh"), r.get("RelativeLocation"),
              r.get("RelativeRotation"), r.get("RelativeScale3D"), r.get("OverrideMaterials"),
              {k: r[k] for k in ("bHidden", "bVisible", "bHiddenInGame", "AttachParent") if k in r})
    print("rows", len(rows), "seq", json.dumps(seq)[:600])


if __name__ == "__main__":
    main()
