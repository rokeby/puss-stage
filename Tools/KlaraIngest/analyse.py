"""Second pass over census_report.json -- OFFLINE, READ-ONLY on both projects.

Adds: unresolved-ref classification, audio facts (asset-registry tags), sequence
playback range / frame rates (decoded tagged properties), bound actor paths,
then writes census_report.json (augmented) and census_report.md.
Run after census.py:  python Tools/KlaraIngest/analyse.py
"""
import json
import os
import re
import struct
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from census import KCONTENT, OUT, ROOTS, build_index, parse_names, package_of  # noqa: E402

REP = os.path.join(OUT, "census_report.json")


def read_type(d, N, q):
    idx, _num, cnt = struct.unpack_from("<iii", d, q); q += 12
    node = [N[idx] if 0 <= idx < len(N) else idx]
    for _ in range(cnt):
        c, q = read_type(d, N, q); node.append(c)
    return node, q


def decode_tag(d, N, name):
    """First occurrence of tagged property `name` whose type parses as a struct."""
    if name not in N:
        return None
    pat = struct.pack("<ii", N.index(name), 0)
    p = 0
    while True:
        p = d.find(pat, p)
        if p < 0:
            return None
        try:
            t, q = read_type(d, N, p + 8)
            size = struct.unpack_from("<i", d, q)[0]
            flags = d[q + 4]
            val = d[q + 5:q + 5 + size]
            if t and t[0] == "StructProperty":
                return {"offset": p, "type": t, "size": size, "flags": flags, "val": val, "valpos": q + 5}
        except Exception:
            pass
        p += 1


def decode_framerate(d, N, name):
    t = decode_tag(d, N, name)
    if not t:
        return None
    r = t["valpos"]; out = {"Numerator": None, "Denominator": 1}
    for _ in range(4):
        nm = N[struct.unpack_from("<i", d, r)[0]]
        if nm == "None":
            break
        _tt, r2 = read_type(d, N, r + 8)
        sz = struct.unpack_from("<i", d, r2)[0]
        val = d[r2 + 5:r2 + 5 + sz]
        if sz == 4:
            out[nm] = struct.unpack("<i", val)[0]
        r = r2 + 5 + sz
    return out


def decode_range(d, N, name):
    t = decode_tag(d, N, name)
    if not t or t["size"] != 10:
        return None
    lt, lv, ut, uv = struct.unpack("<BiBi", t["val"])
    kinds = {0: "Exclusive", 1: "Inclusive", 2: "Open"}
    return {"lower": lv, "lower_type": kinds.get(lt, lt), "upper": uv, "upper_type": kinds.get(ut, ut)}


def strings(d, rx):
    ss = [m.group(0).decode() for m in re.finditer(rb"[\x20-\x7e]{4,}", d)]
    ss += [m.group(0).decode("utf-16le") for m in re.finditer(rb"(?:[\x20-\x7e]\x00){4,}", d)]
    return sorted({s for s in ss if re.search(rx, s)})


def registry_tags(d, keys):
    out = {}
    for k in keys:
        for m in re.finditer(re.escape(k.encode()) + rb"\x00(.{4})", d, re.S):
            n = struct.unpack("<i", m.group(1))[0]
            if 1 < n < 64:
                v = d[m.end():m.end() + n - 1]
                if re.fullmatch(rb"[0-9.\-]+", v) and d[m.end() + n - 1] == 0:
                    out[k] = v.decode("ascii")
                    break
    src = re.search(rb'"RelativeFilename" : "([^"]+)"', d)
    if src:
        out["SourceFile"] = src.group(1).decode("latin-1")
    return out


def main():
    rep = json.load(open(REP, encoding="utf-8"))
    kidx = build_index(KCONTENT)
    kdirs = set()
    for dp, _, _ in os.walk(KCONTENT):
        kdirs.add(("/Game/" + os.path.relpath(dp, KCONTENT).replace("\\", "/")).lower())
    name_cache = {}

    def names_of(pkg):
        f = kidx.get(pkg.lower())
        if not f:
            return set()
        if f not in name_cache:
            name_cache[f] = set(parse_names(open(f, "rb").read()) or [])
        return name_cache[f]

    # ---------------- unresolved classification
    for scene, r in rep["roots"].items():
        cls = {}
        for u, refs in r["unresolved_game_refs_full"].items():
            tail = u[len("/Game/"):].lower()
            moved = [k for k in kidx if k.endswith("/" + tail)]
            mdir = [k for k in kdirs if k.endswith("/" + tail)]
            in_nt = [x for x in refs if u in names_of(x)]
            if moved or mdir:
                kind = "STALE_PATH_OF_MOVED_ASSET (current copy exists)"
            elif u.lower() in kdirs:
                kind = "FOLDER_STRING"
            else:
                kind = "MISSING"
            cls[u] = {"kind": kind, "in_referrer_name_table": bool(in_nt),
                      "current_location": (moved or mdir)[:2], "referrers": refs[:4]}
        r["unresolved_classified"] = cls
        r["unresolved_counts"] = dict(Counter(v["kind"] + (" / in-name-table" if v["in_referrer_name_table"] else " / string-only")
                                              for v in cls.values()))

    # ---------------- sequence facts
    for scene, root in ROOTS.items():
        f = kidx[root.lower()]
        d = open(f, "rb").read()
        N = parse_names(d)
        tick = decode_framerate(d, N, "TickResolution")
        disp = decode_framerate(d, N, "DisplayRate")
        rng = decode_range(d, N, "PlaybackRange")
        sf = rep["sequence_facts"][scene]
        sf.pop("frame_rate_pair_candidates", None); sf.pop("property_name_hits", None)
        sf["tick_resolution"] = tick
        sf["display_rate"] = disp
        sf["playback_range_ticks"] = rng
        if tick and tick["Numerator"] and rng:
            tr = tick["Numerator"] / tick["Denominator"]
            sf["playback_range_seconds"] = [round(rng["lower"] / tr, 3), round(rng["upper"] / tr, 3)]
            sf["duration_seconds"] = round((rng["upper"] - rng["lower"]) / tr, 3)
        sf["bound_actor_paths"] = strings(d, r"PersistentLevel\.")
        sf["level_context_strings"] = strings(d, r"^/Game/.*(L_|Map|Alley)")
        sf["track_classes"] = sorted(n for n in N if re.fullmatch(r"MovieScene\w*(Track|Section)", n))
        # audio: every SoundWave in the full closure, plus direct refs
        audio = []
        for pkg in rep["roots"][scene]["packages_full_closure"]:
            af = kidx.get(pkg)
            if not af or os.path.getsize(af) < 1000:
                continue
            ad = open(af, "rb").read()
            an = parse_names(ad) or []
            if "SoundWave" not in an and "SoundCue" not in an and "MetaSoundSource" not in an:
                continue
            if "SoundWave" not in an[:]:
                pass
            if not any(x in an for x in ("SampleRate", "Duration", "SoundCue", "MetaSoundSource")):
                continue
            t = registry_tags(ad, ["Duration", "SampleRate", "NumChannels", "TotalSamples"])
            audio.append({"package": os.path.splitext(os.path.relpath(af, KCONTENT))[0].replace("\\", "/"),
                          "bytes": os.path.getsize(af),
                          "class": "SoundWave" if "SoundWave" in an else ("SoundCue" if "SoundCue" in an else "MetaSoundSource"),
                          "direct_ref_of_sequence": any(package_of(x)[1].lower() == pkg for x in rep["roots"][scene]["direct_refs_of_root"]),
                          **t})
        sf["audio"] = audio
        sf["direct_game_packages"] = sorted({package_of(x)[1] for x in rep["roots"][scene]["direct_refs_of_root"]
                                            if x.startswith("/Game/")} - {root})
        sf.pop("direct_assets", None); sf.pop("audio_assets", None)
    plugins_effective(rep)
    collisions_ours(rep)
    json.dump(rep, open(REP, "w", encoding="utf-8"), indent=1)
    write_md(rep)
    print("OK analyse")


def plugins_effective(rep):
    """PussStage effective plugin set = uproject Enabled + project Plugins + EnabledByDefault + transitive .uplugin deps."""
    from census import plugin_index, uproject_plugins, OURS
    plug, mod2 = plugin_index()
    deps = {}
    for n, p in plug.items():
        try:
            j = json.load(open(p["uplugin"], encoding="utf-8-sig"))
        except Exception:
            j = {}
        deps[n] = [d["Name"] for d in j.get("Plugins", []) if d.get("Enabled", True)]
    seed = {k for k, v in uproject_plugins(os.path.join(OURS, "PussStage.uproject")).items() if v}
    seed |= set(os.listdir(os.path.join(OURS, "Plugins")))
    seed |= {n for n, p in plug.items() if p["enabled_by_default"]}
    eff, st = set(), list(seed)
    while st:
        x = st.pop()
        if x not in eff:
            eff.add(x); st += deps.get(x, [])
    for m in rep["script_modules"]:
        pl = m["plugin"]
        m["status"] = ("engine/core module" if pl is None else
                       "enabled in PussStage (direct, default or via dependency)" if pl in eff else
                       "PLUGIN NOT ENABLED IN PUSSSTAGE")
    real, noise = [], []
    for m in rep["non_game_mounts"]:
        if m["mount"] == "Engine" or m["mount"] in plug:
            m["status"] = "engine content" if m["mount"] == "Engine" else (
                "enabled in PussStage (direct, default or via dependency)" if m["mount"] in eff else "PLUGIN NOT ENABLED IN PUSSSTAGE")
            real.append(m)
        else:
            m["status"] = "no engine/project plugin of this name: byte noise or authoring-path metadata (inferred)"
            noise.append(m)
    rep["non_game_mounts"] = real
    rep["non_game_mount_noise"] = [{"mount": m["mount"], "distinct_paths": m["distinct_paths"], "examples": m["examples"][:2]} for m in noise]
    up = rep["uproject_plugins"]
    up["pussstage_effective"] = sorted(eff)
    up["klara_enabled_not_effective_in_pussstage"] = sorted(k for k, v in up["klara"].items() if v and k not in eff)


def collisions_ours(rep):
    from census import parse_names, OCONTENT
    refp = os.path.join(OUT, "our_referrers.json")
    refs = json.load(open(refp)) if os.path.exists(refp) else {"per_colliding_package": {}}
    for d in rep["collision_diff"]["files"]:
        if d["class"] != "COLLIDES":
            continue
        of = os.path.join(OCONTENT, d["rel"])
        n = parse_names(open(of, "rb").read()) or []
        d["ours_is_redirector"] = "ObjectRedirector" in n
        pkg = "/Game/" + os.path.splitext(d["rel"])[0]
        if d["ours_is_redirector"]:
            d["ours_redirects_to"] = [x for x in n if x.startswith("/Game/") and x != pkg][:1]
        d["our_packages_referencing_this_path"] = refs["per_colliding_package"].get(pkg, [])


def gb(n):
    return f"{n / 1e9:.2f} GB" if n >= 1e8 else f"{n / 1e6:.1f} MB"


def write_md(rep):
    L = []
    cd = rep["collision_diff"]; s = cd["summary"]
    L.append("# Klara ingest census (offline, read-only)\n")
    L.append(f"Generated {rep['generated']} by `Tools/KlaraIngest/census.py` + `analyse.py`. Source: `{rep['klara_content']}`; target: `{rep['our_content']}`.\n")
    L.append("Proof tiers: **measured** = the scripts read the bytes and the number/string is in the JSON; **inferred** = interpretation the scan cannot verify (no Unreal was run).\n")
    L.append("Method (limits): raw byte scan of each package for `/Mount/...` strings (ASCII + UTF-16LE), soft refs treated as hard, recursion to closure. Conservative: strings in metadata (import paths, thumbnails) also count, so closure may be a superset (inferred). FName number-suffix siblings (`X_1` stored as `X`+number) were included when the base had no file.\n")
    L.append("## Per scene\n")
    for scene, r in rep["roots"].items():
        sf = rep["sequence_facts"][scene]
        a = r["sequence_closure_maps_not_expanded"]; b = r["full_closure_maps_expanded"]
        L.append(f"### {scene}: `{r['root']}`\n")
        L.append(f"- Maps the sequence mentions (measured, string in LS): {', '.join('`'+m+'`' for m in r['maps_mentioned_by_root_sequence']) or 'none'}; bound actors: {len(sf['bound_actor_paths'])} `PersistentLevel.*` paths, so its possessables resolve into a level (inferred from UniversalObjectLocator strings).")
        L.append(f"- Sequence-only closure (maps not expanded): {a['packages']} packages, {gb(a['bytes'])} (measured).")
        L.append(f"- Full closure (maps expanded): {b['packages']} packages, {gb(b['bytes'])}; level-only packages: {len(r['level_only_packages'])} (measured).")
        L.append("- Top folders (full): " + "; ".join(f"`{k}` {gb(v)}" for k, v in b["top_folders_by_bytes"][:6]))
        if sf.get("duration_seconds") is not None:
            L.append(f"- Playback range {sf['playback_range_seconds'][0]} s to {sf['playback_range_seconds'][1]} s = **{sf['duration_seconds']} s**; tick {sf['tick_resolution']['Numerator']}/{sf['tick_resolution']['Denominator']}, display {sf['display_rate']['Numerator']}/{sf['display_rate']['Denominator']} fps (measured, decoded tagged properties; Denominator defaulted to 1 when the tag was absent).")
        else:
            L.append("- Playback range: UNCLEAR (could not decode).")
        L.append(f"- Track/section classes (measured, name table): {', '.join(x.replace('MovieScene','') for x in sf['track_classes'])}")
        L.append(f"- Bound actors (measured strings): {', '.join(x.replace('PersistentLevel.','') for x in sf['bound_actor_paths'])}")
        if sf["audio"]:
            L.append("- Audio in closure (measured, asset-registry tags):")
            for au in sf["audio"]:
                L.append(f"  - `{au['package']}` {au.get('Duration','?')} s, {au.get('SampleRate','?')} Hz, {au.get('NumChannels','?')} ch{' (direct ref of sequence)' if au['direct_ref_of_sequence'] else ''}; source `{au.get('SourceFile','?')}`")
        uc = r["unresolved_counts"]
        L.append(f"- Unresolved /Game refs: {sum(uc.values())} — " + "; ".join(f"{k}: {v}" for k, v in uc.items()))
        miss = [u for u, v in r["unresolved_classified"].items() if v["kind"] == "MISSING"]
        if miss:
            L.append("  - MISSING: " + ", ".join(f"`{m}`" for m in miss[:30]))
        L.append("")
    L.append("## Collision diff (union of full closures)\n")
    for c in ("NEW", "IDENTICAL", "COLLIDES"):
        L.append(f"- **{c}**: {s[c]['files']} files, {gb(s[c]['bytes'])} (of which in a sequence-only closure: {s[c]['files_sequence_closure_only']} files, {gb(s[c]['bytes_sequence_closure_only'])}) — measured, SHA-256.")
    L.append(f"- E: free {gb(cd['e_free_bytes'])}; NEW bytes are {cd['new_bytes_vs_free_ratio']*100:.1f}% of it (measured).\n")
    L.append("### COLLIDES (need Gary's decision: keep ours / take Klara's / import under a new root)\n")
    L.append("| path | Klara bytes | ours bytes | Klara mtime | ours mtime | in sequence closure |")
    L.append("|---|---|---|---|---|---|")
    for d in cd["files"]:
        if d["class"] == "COLLIDES":
            L.append(f"| `{d['rel']}` | {d['bytes']} | {d.get('ours_bytes')} | {d['klara_mtime']} | {d.get('ours_mtime')} | {d['in_sequence_closure']} |")
    L.append("\nOur side (measured: our package name tables; referrers from `Tools/KlaraIngest/our_referrers.py`, first 8 MB of every package in our Content, ASCII+UTF-16):\n")
    for d in cd["files"]:
        if d["class"] == "COLLIDES":
            what = ("our file is an ObjectRedirector -> `" + (d.get("ours_redirects_to") or ["?"])[0] + "`") if d.get("ours_is_redirector") else "our file is a real asset"
            rf = d.get("our_packages_referencing_this_path", [])
            L.append(f"- `{d['rel']}`: {what}; our packages naming this path: {len(rf)} ({', '.join(rf[:3])})")
    L.append("\n## Plugins / modules\n")
    up = rep["uproject_plugins"]
    L.append("- Klara enables, PussStage does not even via dependencies (declaration-proven, both .uproject files + engine .uplugin EnabledByDefault/Plugins deps): " + ", ".join(up["klara_enabled_not_effective_in_pussstage"]))
    nm = [m for m in rep["script_modules"] if m["status"].startswith("PLUGIN NOT")]
    L.append("- `/Script/` modules referenced by the closure whose plugin PussStage does not enable (measured string + declaration): " + (", ".join(f"{m['module']} ({m['plugin']})" for m in nm) or "none"))
    L.append("- Non-/Game content mounts referenced: " + "; ".join(f"`/{m['mount']}/` ({m['distinct_paths']}, {m['status']})" for m in rep["non_game_mounts"]) + f". Plus {len(rep.get('non_game_mount_noise', []))} pseudo-mounts with no plugin of that name (byte noise, or MetaHuman authoring paths like `/Lookdev_UHM/`, `/CharacterParts/` — inferred harmless, UNCLEAR without Unreal).")
    L.append("\n## Risks\n")
    L.append("- The scan is conservative; a few closure members may come only from metadata strings (inferred). Unreal's own reference viewer / migrate would be the authority.")
    L.append("- Level-bound possessables: copying the LS without its map leaves bindings unresolved; the bindings name actors by `PersistentLevel.<name>` in Klara's map, which will not exist in our Scene levels (inferred).")
    L.append("- COLLIDES files would overwrite ours on a blind copy; copy must skip or redirect them. 21 of 25 are our ObjectRedirectors (KK_S1_Animals -> /Game/Scenes/...) that our StageTest external actors and /Game/Scenes skeleton/physics assets still name: overwriting them with Klara's real assets would silently re-point those references to Klara's copies (inferred). 4 are real KK_S2_Shrine assets used by KK_Main_S2_Shrine / BPs (measured referrers).")
    L.append("- S2: LS_NEW_SHRINE is a 5 s, single-CineCamera shot (camera cut + transform + float tracks) bound into Klara's `/Game/Japanese_Alley/Maps/Japanese_Alley`, not into any KK_S2_Shrine level; it references no KK_S2_Shrine asset itself (measured). Everything else in its closure comes via that map (Japanese_Alley materials 0.6 GB, Turnips 0.2 GB).")
    L.append("- S1 names `/Game/KK_S1_Animals/LS_Animals` (no such file in Klara's Content; string-only, likely the pre-duplicate name) (measured absence; meaning inferred). LS_Children also names `/Game/KK_S1_Animals/L_Animals` alongside `/Game/L_KK_children` (measured); which bindings resolve there is UNCLEAR offline.")
    L.append("- Referrer counts for FName-suffixed names (e.g. `SM_Leaf_1`, stored as `SM_Leaf`+number) undercount (method limit).")
    L.append("- Klara's Content has no `__ExternalActors__` folder, so her maps are not OFPA; the map .umap holds its actors (measured absence).")
    open(os.path.join(OUT, "census_report.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
