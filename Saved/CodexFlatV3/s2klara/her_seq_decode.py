"""Offline decode of Klara's LS_NEW_SHRINE transform keys for her wing bindings (read-only; reuses the S6 harness
reader via source substitution of the hardcoded LS_Void names). Writes her_seq_decode.json next to this file."""
import importlib.util, inspect, json, os, textwrap
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RDR = os.path.join(PROJECT, "Saved", "CodexConductor", "KlaraIngest", "test_klara_void_s6_offline.py")
spec = importlib.util.spec_from_file_location("pkgreader", RDR); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
src = inspect.getsource(m.derive_her).replace("LS_Void.MovieScene_0", "LS_NEW_SHRINE.MovieScene_0")
ns = dict(m.__dict__); ns["LS_VOID"] = os.path.join(PROJECT, "Content", "KK_S2_Shrine", "LS_NEW_SHRINE.uasset")
exec(textwrap.dedent(src), ns)
her = ns["derive_her"]()
TPF = 800  # ticks per display frame (24000/30)
rows = {}
for r in her["possessables"]:
    t = r.get("transform")
    if not t or "Wing" not in r["name"] and "wing" not in r["name"]:
        continue
    def summ(c):
        ks = c["keys"]
        if not ks: return {"n": 0, "default": c["default"]}
        return {"n": len(ks), "t0_s": ks[0]["t"] / 24000, "t1_s": ks[-1]["t"] / 24000, "v0": round(ks[0]["v"], 1),
                "v1": round(ks[-1]["v"], 1), "min": round(min(k["v"] for k in ks), 1), "max": round(max(k["v"] for k in ks), 1),
                "interp": sorted({k["interp"] for k in ks})}
    rows[r["name"]] = {k: summ(t[k]) for k in ("x", "y", "z", "roll", "pitch", "yaw")}
    rows[r["name"]]["tracks"] = r["tracks"]
out = {"playback_tick": her.get("playback_tick"), "cuts": her.get("cuts"), "wings": rows,
       "all_possessables": [r["name"] for r in her["possessables"]]}
json.dump(out, open(os.path.join(HERE, "her_seq_decode.json"), "w"), indent=1)
for n, r in sorted(rows.items()):
    print(n, "z:", r["z"], "| x:", {k: r["x"].get(k) for k in ("v0", "v1")}, "y:", {k: r["y"].get(k) for k in ("v0", "v1")}, "yaw:", r["yaw"].get("v0"), r["tracks"])
print(out["all_possessables"])
