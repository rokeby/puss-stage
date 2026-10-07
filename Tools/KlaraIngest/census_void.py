"""Klara ingest census -- OFFLINE, READ-ONLY.

Computes the /Game dependency closure of Klara's three level sequences by
scanning raw package bytes (ASCII + UTF-16LE) for package-path strings, diffs
the closure against E:\\PussStage\\Content, and extracts best-effort sequence
facts. Reads C:\\KlaraIngest\\KK_Children_copy and E:\\PussStage; writes only to
E:\\PussStage\\Saved\\CodexConductor\\KlaraIngest\\.

Run:  python Tools/KlaraIngest/census.py
"""
import hashlib
import json
import os
import re
import shutil
import struct
import sys
from collections import Counter, defaultdict
from datetime import datetime

KLARA = r"C:\KlaraIngest\KK_Children_copy"
KCONTENT = os.path.join(KLARA, "Content")
OURS = r"E:\PussStage"
OCONTENT = os.path.join(OURS, "Content")
ENGINE_PLUGINS = r"D:\Unreal Engine\UE_5.8\Engine\Plugins"
OUT = os.path.join(OURS, r"Saved\CodexConductor\KlaraIngest\Void")

ROOTS = {
    "S6": "/Game/Void_content/LS_Void",
}
EXTS = (".uasset", ".umap")
COMPANIONS = (".uexp", ".ubulk", ".uptnl")

# A path string: '/' + mount + ('/' segment)+ ; not preceded by a path/drive char
PATH_RE_A = re.compile(rb"(?<![A-Za-z0-9_:/\.\\])/([A-Za-z][A-Za-z0-9_\-]*)((?:/[A-Za-z0-9_\-\.]+)+(?::[A-Za-z0-9_\-\.]+)*)")
PATH_RE_W = re.compile(r"(?<![A-Za-z0-9_:/\.\\])/([A-Za-z][A-Za-z0-9_\-]*)((?:/[A-Za-z0-9_\-\.]+)+(?::[A-Za-z0-9_\-\.]+)*)")
UTF16_RUN = re.compile(rb"(?:[\x20-\x7e]\x00){6,}")

# ---------------------------------------------------------------- file index
def build_index(content_root):
    idx = {}  # lower /Game path -> abs file
    for dp, _, fns in os.walk(content_root):
        for fn in fns:
            base, ext = os.path.splitext(fn)
            if ext.lower() in EXTS:
                rel = os.path.relpath(os.path.join(dp, base), content_root).replace("\\", "/")
                idx[("/Game/" + rel).lower()] = os.path.join(dp, fn)
    return idx


def extract_paths(data):
    found = set()
    for m in PATH_RE_A.finditer(data):
        found.add(m.group(0).decode("ascii", "replace"))
    for run in UTF16_RUN.finditer(data):
        s = run.group(0).decode("utf-16le", "replace")
        for m in PATH_RE_W.finditer(s):
            found.add(m.group(0))
    return found


def package_of(path):
    """'/Game/A/B.B:Sub' -> '/Game/A/B' ; returns (mount, package)."""
    p = path.split(":")[0]
    segs = p.split("/")
    last = segs[-1]
    if "." in last:
        segs[-1] = last.split(".")[0]
    pkg = "/".join(segs)
    mount = segs[1] if len(segs) > 1 else ""
    return mount, pkg


# ------------------------------------------------------------ name table
def parse_names(data):
    """Brute-force locate NameCount/NameOffset in the summary and parse names."""
    if len(data) < 64 or struct.unpack_from("<I", data, 0)[0] != 0x9E2A83C1:
        return None
    for i in range(4, min(len(data) - 8, 4096)):
        cnt, off = struct.unpack_from("<ii", data, i)
        if not (0 < cnt < 2_000_000 and 32 < off < len(data)):
            continue
        names = []
        pos = off
        ok = True
        for _ in range(cnt):
            if pos + 4 > len(data):
                ok = False; break
            n = struct.unpack_from("<i", data, pos)[0]; pos += 4
            if n > 0:
                if n > 4096 or pos + n > len(data) or data[pos + n - 1] != 0:
                    ok = False; break
                s = data[pos:pos + n - 1]
                try:
                    s = s.decode("latin-1")
                except Exception:
                    ok = False; break
                pos += n
            elif n < 0:
                n = -n
                if n > 4096 or pos + 2 * n > len(data):
                    ok = False; break
                s = data[pos:pos + 2 * n - 2].decode("utf-16le", "replace"); pos += 2 * n
            else:
                ok = False; break
            if any(ord(c) < 32 for c in s):
                ok = False; break
            names.append(s)
            pos += 4  # hash
        if ok and len(names) == cnt and cnt >= 3:
            return names
    return None


# ------------------------------------------------------------- closure
def closure(root_pkg, idx, cache, expand_maps=True):
    seen = {}
    unresolved = defaultdict(set)   # pkg -> referrers
    other_mounts = defaultdict(set)  # full path -> referrers
    suffix_candidates = defaultdict(set)
    stack = [root_pkg]
    edges = defaultdict(set)
    while stack:
        pkg = stack.pop()
        if pkg.lower() in seen:
            continue
        f = idx.get(pkg.lower())
        if f is None:
            continue
        seen[pkg.lower()] = f
        if f.lower().endswith(".umap") and not expand_maps and pkg.lower() != root_pkg.lower():
            continue
        refs = cache_refs(f, cache)
        for r in refs:
            mount, rp = package_of(r)
            if mount == "Game":
                if rp.lower() == pkg.lower():
                    continue
                if rp.lower() in idx:
                    edges[pkg].add(rp)
                    if rp.lower() not in seen:
                        stack.append(rp)
                else:
                    # FName number-suffix: '/Game/X/Bar_1' is stored as '/Game/X/Bar' + number
                    d, b = rp.rsplit("/", 1)
                    sib = [k for k in idx if k.startswith((d + "/" + b + "_").lower())
                           and re.fullmatch(r"\d+", k[len(d) + len(b) + 2:])]
                    if sib:
                        for k in sib:
                            suffix_candidates[k].add(pkg)
                            edges[pkg].add(k)
                            if k not in seen:
                                stack.append(k)
                    else:
                        unresolved[rp].add(pkg)
            else:
                other_mounts[r].add(pkg)
    return seen, unresolved, other_mounts, suffix_candidates, edges


def cache_refs(f, cache):
    if f not in cache:
        data = open(f, "rb").read()
        refs = extract_paths(data)
        for comp in COMPANIONS:
            cf = os.path.splitext(f)[0] + comp
            if os.path.exists(cf):
                refs |= extract_paths(open(cf, "rb").read())
        cache[f] = refs
    return cache[f]


def files_for(absf):
    out = [absf]
    for comp in COMPANIONS:
        cf = os.path.splitext(absf)[0] + comp
        if os.path.exists(cf):
            out.append(cf)
    return out


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------- plugins
def plugin_index():
    plug = {}  # name -> {path, modules, enabled_by_default, content}
    mod2plug = {}
    for base in (ENGINE_PLUGINS, os.path.join(OURS, "Plugins"), os.path.join(KLARA, "Plugins")):
        if not os.path.isdir(base):
            continue
        for dp, dns, fns in os.walk(base):
            for fn in fns:
                if fn.endswith(".uplugin"):
                    p = os.path.join(dp, fn)
                    try:
                        j = json.load(open(p, encoding="utf-8-sig"))
                    except Exception:
                        j = {}
                    name = fn[:-8]
                    mods = [m.get("Name") for m in j.get("Modules", [])]
                    plug.setdefault(name, {"uplugin": p, "modules": mods,
                                           "enabled_by_default": bool(j.get("EnabledByDefault", False)),
                                           "can_contain_content": bool(j.get("CanContainContent", False))})
                    for m in mods:
                        mod2plug.setdefault(m, name)
            if "Source" in dns:
                dns.remove("Source")
            for skip in ("Content", "Binaries", "Intermediate", "Resources", "Shaders"):
                if skip in dns:
                    dns.remove(skip)
    return plug, mod2plug


def uproject_plugins(p):
    j = json.load(open(p, encoding="utf-8-sig"))
    return {x["Name"]: x.get("Enabled", True) for x in j.get("Plugins", [])}


# ------------------------------------------------------------- audio / sequence facts
def wav_duration(data):
    out = []
    for m in re.finditer(rb"RIFF....WAVE", data, re.S):
        s = m.start()
        pos = s + 12
        fmt = None
        while pos + 8 <= len(data):
            cid = data[pos:pos + 4]; sz = struct.unpack_from("<I", data, pos + 4)[0]
            if cid == b"fmt ":
                fmt = struct.unpack_from("<HHIIHH", data, pos + 8)
            if cid == b"data":
                if fmt:
                    ch, sr, bps = fmt[1], fmt[2], fmt[5]
                    if sr and ch and bps:
                        out.append({"channels": ch, "sample_rate": sr, "bits": bps,
                                    "data_bytes": sz, "seconds": round(sz / (sr * ch * bps / 8), 3)})
                break
            pos += 8 + sz + (sz & 1)
            if sz > len(data):
                break
    return out


INTERESTING_NAME_RE = re.compile(
    r"(MovieScene|Track|Section|Binding|Camera|CineCamera|MetaHuman|BP_|SK_|Sound|Audio|Anim|"
    r"TickResolution|DisplayRate|PlaybackRange|Possessable|Spawnable|Level|Fade|Subtitle)", re.I)


def frame_rate_candidates(data, names):
    res = {}
    if not names:
        return res
    for key in ("TickResolution", "DisplayRate", "PlaybackRange", "SelectionRange", "WorkingRange", "ViewRange"):
        if key not in names:
            continue
        ni = names.index(key)
        pat = struct.pack("<ii", ni, 0)
        hits = []
        for m in re.finditer(re.escape(pat), data):
            window = data[m.start() + 8:m.start() + 8 + 96]
            ints = [struct.unpack_from("<i", window, k)[0] for k in range(0, len(window) - 3, 1)]
            hits.append({"offset": m.start(), "window_hex": window[:64].hex()})
        res[key] = {"name_index": ni, "occurrences": len(hits), "first": hits[:3]}
    return res


def scan_rates(data):
    """Find (num,den) int pairs that look like FFrameRate values."""
    nums = {24000, 30000, 60000, 48000, 90000, 120000, 24, 25, 30, 48, 50, 60, 120, 240}
    c = Counter()
    for m in re.finditer(rb"(?=(.{4})(\x01\x00\x00\x00|\xe9\x03\x00\x00))", data, re.S):
        n = struct.unpack("<i", m.group(1))[0]
        if n in nums:
            d = struct.unpack("<i", m.group(2))[0]
            c[f"{n}/{d}"] += 1
    return dict(c.most_common(10))


# ------------------------------------------------------------- main
def main():
    os.makedirs(OUT, exist_ok=True)
    kidx = build_index(KCONTENT)
    oidx = build_index(OCONTENT)
    cache = {}
    report = {"generated": datetime.now().isoformat(timespec="seconds"),
              "klara_content": KCONTENT, "our_content": OCONTENT,
              "method": "raw byte scan (ASCII + UTF-16LE) of each package (+companions) for /Mount/... strings; "
                        "'/Game/X/Y[.Obj[:Sub]]' -> Content/X/Y.uasset|.umap; recursion to closure; soft refs treated as hard; "
                        "unresolved base names retried as FName number-suffix siblings (Y_N).",
              "roots": {}}
    plug, mod2plug = plugin_index()
    ours_up = uproject_plugins(os.path.join(OURS, "PussStage.uproject"))
    klara_up = uproject_plugins(os.path.join(KLARA, "KK_Children.uproject"))
    our_proj_plugins = set(os.listdir(os.path.join(OURS, "Plugins")))

    union_seq, union_full = {}, {}
    all_other = defaultdict(set)
    for scene, root in ROOTS.items():
        rf = kidx.get(root.lower())
        if not rf:
            report["roots"][scene] = {"root": root, "error": "root file not found"}
            continue
        seq_seen, seq_unres, seq_other, seq_suf, _ = closure(root, kidx, cache, expand_maps=False)
        full_seen, full_unres, full_other, full_suf, edges = closure(root, kidx, cache, expand_maps=True)
        root_refs = sorted(cache_refs(rf, cache))
        maps_mentioned = sorted({package_of(r)[1] for r in root_refs
                                 if package_of(r)[0] == "Game" and kidx.get(package_of(r)[1].lower(), "").lower().endswith(".umap")})
        maps_in_closure = sorted(p for p, f in seq_seen.items() if f.lower().endswith(".umap"))
        level_only = sorted(set(full_seen) - set(seq_seen))
        def stats(seen):
            files = []
            for p, f in seen.items():
                files += files_for(f)
            by = Counter()
            tot = 0
            for f in files:
                sz = os.path.getsize(f); tot += sz
                rel = os.path.relpath(f, KCONTENT).replace("\\", "/")
                top = "/".join(rel.split("/")[:2]) if "/" in rel else "(root)"
                by[top] += sz
            return {"packages": len(seen), "files": len(files), "bytes": tot,
                    "top_folders_by_bytes": [[k, v] for k, v in by.most_common(15)]}
        # also the map(s) mentioned: closure of each map on its own
        map_closures = {}
        for mp in set(maps_mentioned) | ({"/Game/L_KK_children"} if scene == "S4" else set()):
            ms, mu, mo, msuf, _ = closure(mp, kidx, cache, expand_maps=True)
            map_closures[mp] = {"mentioned_by_sequence": mp in maps_mentioned, **stats(ms),
                                "unresolved": sorted(mu)}
        for p, f in seq_seen.items():
            union_seq[p] = f
        for p, f in full_seen.items():
            union_full[p] = f
        for k, v in full_other.items():
            all_other[k] |= v
        report["roots"][scene] = {
            "root": root, "root_file": rf,
            "maps_mentioned_by_root_sequence": maps_mentioned,
            "maps_in_sequence_closure_not_expanded": maps_in_closure,
            "sequence_closure_maps_not_expanded": stats(seq_seen),
            "full_closure_maps_expanded": stats(full_seen),
            "level_only_packages": level_only,
            "map_closures": map_closures,
            "packages_sequence_closure": sorted(seq_seen),
            "packages_full_closure": sorted(full_seen),
            "unresolved_game_refs_full": {k: sorted(v) for k, v in sorted(full_unres.items())},
            "unresolved_game_refs_sequence_only": sorted(seq_unres),
            "number_suffix_candidates_included": {k: sorted(v) for k, v in sorted(full_suf.items())},
            "direct_refs_of_root": root_refs,
            "non_game_refs_full": {k: sorted(v)[:5] for k, v in sorted(full_other.items())},
        }

    # ----- mounts / modules
    mounts = Counter(); scripts = Counter()
    for r in all_other:
        m = package_of(r)[0]
        mounts[m] += 1
        if m == "Script":
            scripts[r.split("/")[2].split(".")[0]] += 1
    ours_enabled = {k for k, v in ours_up.items() if v} | our_proj_plugins
    module_report = []
    for mod, n in sorted(scripts.items()):
        p = mod2plug.get(mod)
        if p is None:
            status = "engine/core module (no .uplugin declares it)"
        elif p in ours_enabled:
            status = "plugin enabled in PussStage.uproject / project Plugins"
        elif plug.get(p, {}).get("enabled_by_default"):
            status = "plugin EnabledByDefault (not listed in either uproject)"
        else:
            status = "PLUGIN NOT ENABLED IN PUSSSTAGE"
        module_report.append({"module": mod, "refs": n, "plugin": p, "klara_uproject_enables": klara_up.get(p) if p else None,
                              "status": status})
    mount_report = []
    for m, n in mounts.most_common():
        if m in ("Game", "Script"):
            continue
        p = plug.get(m)
        if m == "Engine":
            status = "engine content"
        elif p is None:
            status = "no plugin of this name found (path noise or missing plugin)"
        elif m in ours_enabled:
            status = "plugin enabled in PussStage"
        elif p.get("enabled_by_default"):
            status = "plugin EnabledByDefault"
        else:
            status = "PLUGIN NOT ENABLED IN PUSSSTAGE"
        mount_report.append({"mount": m, "distinct_paths": n, "status": status,
                             "examples": sorted(r for r in all_other if package_of(r)[0] == m)[:8]})
    report["non_game_mounts"] = mount_report
    report["script_modules"] = module_report
    report["uproject_plugins"] = {"pussstage": ours_up, "pussstage_project_plugins_folder": sorted(our_proj_plugins),
                                  "klara": klara_up,
                                  "klara_enabled_not_in_pussstage": sorted(k for k, v in klara_up.items() if v and k not in ours_enabled
                                                                          and not plug.get(k, {}).get("enabled_by_default"))}

    # ----- TASK 2 collision diff over union (full closure)
    diff = []
    for p, f in sorted(union_full.items()):
        for kf in files_for(f):
            rel = os.path.relpath(kf, KCONTENT)
            of = os.path.join(OCONTENT, rel)
            ks = os.path.getsize(kf)
            ent = {"rel": rel.replace("\\", "/"), "package": p, "bytes": ks,
                   "in_sequence_closure": p in union_seq,
                   "klara_mtime": datetime.fromtimestamp(os.path.getmtime(kf)).isoformat(timespec="seconds")}
            if not os.path.exists(of):
                ent["class"] = "NEW"
                # case-insensitive / other-extension clash (e.g. .umap vs .uasset same package)
                alt = oidx.get(p.lower())
                if alt:
                    ent["class"] = "COLLIDES"
                    ent["note"] = "same package name, different extension in ours: " + alt
                    ent["ours_bytes"] = os.path.getsize(alt)
                    ent["ours_mtime"] = datetime.fromtimestamp(os.path.getmtime(alt)).isoformat(timespec="seconds")
            else:
                os_ = os.path.getsize(of)
                same = (os_ == ks) and sha256(of) == sha256(kf)
                ent["class"] = "IDENTICAL" if same else "COLLIDES"
                ent["ours_bytes"] = os_
                ent["ours_mtime"] = datetime.fromtimestamp(os.path.getmtime(of)).isoformat(timespec="seconds")
            diff.append(ent)
    summ = {}
    for c in ("NEW", "IDENTICAL", "COLLIDES"):
        sel = [d for d in diff if d["class"] == c]
        summ[c] = {"files": len(sel), "bytes": sum(d["bytes"] for d in sel),
                   "files_sequence_closure_only": sum(1 for d in sel if d["in_sequence_closure"]),
                   "bytes_sequence_closure_only": sum(d["bytes"] for d in sel if d["in_sequence_closure"])}
    du = shutil.disk_usage("E:\\")
    report["collision_diff"] = {"summary": summ, "files": diff,
                                "e_free_bytes": du.free, "e_total_bytes": du.total,
                                "new_bytes_vs_free_ratio": round(summ["NEW"]["bytes"] / du.free, 4)}
    report["union"] = {"sequence_closure_packages": len(union_seq), "full_closure_packages": len(union_full)}

    # ----- TASK 3 sequence facts
    facts = {}
    for scene, root in ROOTS.items():
        rf = kidx.get(root.lower())
        if not rf:
            continue
        data = open(rf, "rb").read()
        names = parse_names(data)
        sounds = []
        for r in sorted(cache_refs(rf, cache)):
            mount, rp = package_of(r)
            if mount != "Game":
                continue
            f = kidx.get(rp.lower())
            if not f:
                continue
            d2 = open(f, "rb").read(2_000_000) if os.path.getsize(f) < 400_000_000 else b""
            d2 = open(f, "rb").read()
            n2 = parse_names(d2) or []
            cls = [n for n in n2 if n in ("SoundWave", "SoundCue", "MetaSoundSource", "SoundBase", "LevelSequence",
                                          "CineCameraActor", "SkeletalMesh", "AnimSequence", "Blueprint", "World",
                                          "MediaPlayer", "FileMediaSource", "GeometryCache", "StaticMesh",
                                          "MaterialInstanceConstant", "Material", "Texture2D", "NiagaraSystem")]
            ent = {"package": rp, "file": os.path.relpath(f, KCONTENT), "classes_in_name_table": cls}
            if "SoundWave" in cls or "SoundCue" in cls or "MetaSoundSource" in cls:
                ent["embedded_wav"] = wav_duration(d2)
                srcs = sorted({m.group(0).decode("latin-1") for m in re.finditer(rb"[A-Za-z]:[/\\][^\x00\"]{3,200}?\.(?:wav|WAV|mp3|ogg|flac)", d2)})
                ent["source_file_strings"] = srcs[:5]
                sounds.append(ent)
            facts.setdefault(scene, {}).setdefault("direct_assets", []).append(ent)
        interesting = sorted({n for n in (names or []) if INTERESTING_NAME_RE.search(n)})
        facts.setdefault(scene, {}).update({
            "name_table_parsed": names is not None,
            "name_count": len(names) if names else None,
            "interesting_names": interesting[:400],
            "audio_assets": sounds,
            "property_name_hits": frame_rate_candidates(data, names),
            "frame_rate_pair_candidates": scan_rates(data),
        })
        if names:
            open(os.path.join(OUT, f"names_{scene}.txt"), "w", encoding="utf-8").write("\n".join(names))
    report["sequence_facts"] = facts

    with open(os.path.join(OUT, "census_report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    print("WROTE", os.path.join(OUT, "census_report.json"))
    for scene, r in report["roots"].items():
        print(scene, r.get("sequence_closure_maps_not_expanded", {}).get("packages"),
              r.get("full_closure_maps_expanded", {}).get("packages"),
              r.get("full_closure_maps_expanded", {}).get("bytes"), r.get("maps_mentioned_by_root_sequence"))
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
