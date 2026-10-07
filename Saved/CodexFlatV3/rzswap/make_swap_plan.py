"""RZSWAP offline planner (7 Oct, offline; no Unreal).  DRY measurement + realism manifests + rzimport VERIFY records +
rzswap_protect.json -> rzswap_plan_<P>.json (what APPLY applies; its hash is in the APPLY confirm) + rzswap_sheet_<P>.png
(the passage as a strip: every row at its pass time, current vs proposed panel per side, protections marked) for Gary.

  python make_swap_plan.py P02 [--dry rzswap_dry_P02_LATEST.json] [--manifests a.json b.json] [--pair-mode side|row]
                               [--max-swaps N] [--end-rows 1] [--exclude "P02 Wing 007|L" ...]
  python make_swap_plan.py P02 --preview-gap-audit      PREVIEW ONLY from the 6 Oct 21:54 GAP_AUDIT snapshot (no live
                               bounds / pass times / mechanisms; designs assumed imported): never appliable.

Tiers: the plan's numbers come from the DRY [meas live at DRY time]; thumbnails are the manifests' SkinColor PNGs
(proposed) and the newest matching T_<owner>_SkinColor*.png under DerivedAssets/FlatV3 (current) -- the latter is a
NAME MATCH [inf: the PNG is the skin the live mesh was built from only if nobody re-skinned it under another name].
"""
import argparse
import datetime
import glob
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


core = _load("rzswap_core_plan", os.path.join(HERE, "rzswap_core.py"))
rzc = _load("rzimport_core_plan", os.path.join(HERE, "..", "rzimport", "rzimport_core.py"))


def jload(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _abs(rel):
    return rel if os.path.isabs(rel) else os.path.join(PROJECT, rel)


# =====================================================================================================================
# Designs
# =====================================================================================================================

def imported_owners(verify_paths):
    """Owners some rzimport VERIFY read back OK (ok list), with the mesh path it read."""
    out = {}
    for p in verify_paths:
        try:
            d = jload(p)
        except (OSError, ValueError):
            continue
        for o in d.get("ok", []):
            out[o] = (d.get("mesh_paths") or {}).get(o)
    return out


def designs_for(P, manifests, dry, verified):
    out = []
    for rel in manifests:
        m = jload(_abs(rel))
        for e in m.get("meshes", []):
            if e.get("intended_passage") != P:
                continue
            asset = str(e["asset"])
            variant = asset.rsplit("_", 1)[-1]
            if variant not in rzc.MESH_FOLDERS:
                continue
            owner = asset[len("SM_FlatV3_"):-len("_" + variant)]
            mesh = "%s/%s" % (rzc.MESH_FOLDERS[variant], asset)
            c = (dry.get("candidates") or {}).get(mesh, {})
            vm = verified.get(owner, "MISSING")
            out.append({"owner": owner, "side": e.get("side"), "mount": e.get("mount") or "wing", "passage": P,
                        "mesh": mesh, "height_cm": float(e.get("height_cm") or 0.0),
                        "width_cm": round(float((e.get("dimensions_m") or {}).get("width") or 0.0) * 100.0, 1),
                        "skin_png": (e.get("textures") or {}).get("SkinColor", {}).get("path"),
                        "imported": vm != "MISSING" and (vm is None or vm == mesh),
                        "exists": bool(c.get("exists")), "zero_bounds": c.get("zero_bounds"), "manifest": rel})
    return out


# =====================================================================================================================
# Foreign records naming the target cues (informational: a WHOLE-TEXT revert elsewhere would clash with our panels)
# =====================================================================================================================

def foreign_records(guids, days=3.0):
    hits = []
    now = datetime.datetime.now().timestamp()
    for p in glob.glob(os.path.join(PROJECT, "Saved", "Codex*", "**", "*.json"), recursive=True):
        if os.path.dirname(os.path.abspath(p)) == HERE:
            continue
        try:
            st = os.stat(p)
            if now - st.st_mtime > days * 86400 or st.st_size > 8 << 20:
                continue
            with open(p, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        named = sorted(g for g in guids if g in text)
        if named and ("ACTIVE" in os.path.basename(p) or "originals" in os.path.basename(p) or "record" in os.path.basename(p)):
            hits.append({"path": os.path.relpath(p, PROJECT).replace("\\", "/"), "cues": len(named)})
    return sorted(hits, key=lambda h: h["path"])


# =====================================================================================================================
# Preview DRY from the GAP_AUDIT snapshot (never appliable)
# =====================================================================================================================

def preview_dry(P):
    ga = jload(os.path.join(PROJECT, "Saved", "CodexFlatV3", "floorgap", "GAP_AUDIT.json"))
    sides = [s for s in ga["sides"] if s["passage"] == P]
    by = {}
    for s in sides:
        by.setdefault(s["cue_guid"], {"label": s["cue"], "sides": {}})["sides"]["L" if s["side"] == "left" else "R"] = s
    rows = sorted(by.items(), key=lambda kv: int(re.findall(r"\d+", kv[1]["label"])[-1]))
    out = []
    for o, (g, r) in enumerate(rows):
        row = {"ordinal": o, "cue_guid": g, "label": r["label"], "show_index": o, "enabled": True, "has_top": False,
               "pass_s": None, "mechanism": {"kind": "SLIDE (unmeasured)", "playback_mode": "?"}, "master_pinned": False,
               "attachments": [], "sides": {}}
        for s in ("L", "R"):
            x = r["sides"].get(s, {})
            mesh = x.get("mesh")
            thick = None if (not mesh or mesh.startswith(core.V3_ROOT)) else 10.0     # [inf] legacy = 10 cm card
            row["sides"][s] = {"panel": core.planned_panel(mesh, 0.0), "thickness_cm": thick, "height_cm": None,
                               "old_bounds": {"min_y_cm": 0.0, "max_y_cm": 500.0} if s == "L" else
                               {"min_y_cm": -500.0, "max_y_cm": 0.0}, "edge_baseline": {"inner_cm": 0.0}}
        out.append(row)
    for i, r in enumerate(out):
        r["pass_s"] = float(i)          # ordinal stands in for the pass time in a preview
    return {"mode": "PREVIEW", "status": "PASS", "run_id": "PREVIEW-GAP_AUDIT-20261006-2154", "passage": P,
            "passage_guid": core.PASSAGES[P]["guid"], "rows": out, "candidates": {},
            "settings": {"first_cue_guid": out[0]["cue_guid"], "last_cue_guid": out[-1]["cue_guid"]}}


# =====================================================================================================================
# Contact sheet
# =====================================================================================================================

_INDEX = None


def skin_index():
    global _INDEX
    if _INDEX is None:
        _INDEX = {}
        for root, _dirs, files in os.walk(os.path.join(PROJECT, "DerivedAssets", "FlatV3")):
            for f in files:
                if "_SkinColor" in f and f.endswith(".png") and "diff" not in f:
                    _INDEX.setdefault(f.split("_SkinColor", 1)[0], []).append(os.path.join(root, f))
    return _INDEX


def current_png(mesh):
    n = core.mesh_name(mesh)
    if not n:
        return None
    for p in ("SM_FlatV3_", "SM_"):
        if n.startswith(p):
            n = n[len(p):]
            break
    n = re.sub(r"_t5[pij]$", "", n)
    cands = skin_index().get("T_" + n, [])
    if not cands:
        return None
    rank = lambda p: (0 if p.endswith("_o2p.png") else 1 if p.endswith("_o2.png") else 2, -os.path.getmtime(p))  # noqa: E731
    return sorted(cands, key=rank)[0]


def thumb(path, size, cache):
    from PIL import Image
    if not path or not os.path.isfile(_abs(path)):
        return None
    key = (path, size)
    if key not in cache:
        try:
            im = Image.open(_abs(path))
            im.draft("RGB", size)
            im = im.convert("RGBA")
            im.thumbnail(size)
            cache[key] = im
        except OSError:
            cache[key] = None
    return cache[key]


def contact_sheet(plan, dry, out_png):
    from PIL import Image, ImageDraw, ImageFont
    TW, TH, PAD, HEAD = 118, 168, 6, 54
    rows = dry["rows"]
    facts = {f["key"]: f for f in plan["facts"]}
    swaps = {s["key"]: s for s in plan["swaps"]}
    colw = TW * 2 + PAD * 3
    per = 12                                   # rows per band (the strip wraps)
    bands = max(1, (len(rows) + per - 1) // per)
    bandh = 2 * (TH + 34 + PAD) + 40
    W = PAD + min(len(rows), per) * colw
    H = 22 + bands * bandh + 70
    img = Image.new("RGB", (W, H), (34, 34, 38))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 13)
        small = ImageFont.truetype("arial.ttf", 11)
    except OSError:
        font = small = ImageFont.load_default()
    cache = {}
    title = "%s  %s  plan #%s  DRY %s  swaps %d  pair_mode %s  (top: L, bottom: R; each cell = CURRENT | PROPOSED)" % (
        plan["passage"], "PREVIEW - NOT APPLIABLE" if dry.get("mode") == "PREVIEW" else "", plan["hash8"],
        plan["dry_run_id"], len(plan["swaps"]), plan["pair_mode"])
    d.text((PAD, 4), title, fill=(240, 240, 240), font=font)
    for i, r in enumerate(rows):
        x0 = PAD + (i % per) * colw
        by = 22 + (i // per) * bandh
        ps = r.get("pass_s")
        d.text((x0, by), "%s" % r["label"].replace("Wing ", "W"), fill=(250, 220, 120), font=font)
        d.text((x0, by + 15), ("%.1f s" % ps) if ps is not None and dry.get("mode") != "PREVIEW" else "#%d" % (i + 1),
               fill=(200, 200, 200), font=small)
        for k, s in enumerate(("L", "R")):
            y0 = by + 32 + k * (TH + 34 + PAD)
            key = "%s|%s" % (r["cue_guid"], s)
            f = facts.get(key, {})
            sw = swaps.get(key)
            cur = thumb(current_png(r["sides"][s]["panel"]["mesh"]), (TW, TH), cache)
            new = thumb(sw["new_skin_png"], (TW, TH), cache) if sw else None
            for j, (im, label) in enumerate(((cur, "current"), (new, "proposed"))):
                bx = x0 + j * (TW + PAD)
                col = (60, 60, 66) if j == 0 or sw else (44, 44, 48)
                d.rectangle([bx, y0, bx + TW, y0 + TH], fill=col)
                if im is not None:
                    img.paste(im, (bx + (TW - im.width) // 2, y0 + TH - im.height), im)
                elif j == 0:
                    d.text((bx + 4, y0 + 4), (core.mesh_name(r["sides"][s]["panel"]["mesh"]) or "-")[:40],
                           fill=(170, 170, 170), font=small)
                if j == 1 and sw:
                    d.rectangle([bx, y0, bx + TW, y0 + TH], outline=(90, 220, 110), width=3)
            tag = ("SWAP %s" % sw["new_owner"].split("_real_", 1)[-1]) if sw else \
                  ("KEEP " + f["protected"][0].split(" ")[0]) if f.get("protected") else "eligible (no design left)"
            colr = (90, 220, 110) if sw else (230, 110, 100) if f.get("protected") else (170, 170, 170)
            d.text((x0, y0 + TH + 3), "%s %s" % (s, tag[:34]), fill=colr, font=small)
            d.text((x0, y0 + TH + 17), "%s s%s" % (f.get("class", "?"), f.get("score", "")), fill=(150, 150, 150), font=small)
    yb = H - 62
    for n, fl in enumerate((plan["flags"] + plan["refusals"])[:4]):
        d.text((PAD, yb + n * 14), fl[:260], fill=(230, 180, 90), font=small)
    img.save(out_png)
    return out_png


# =====================================================================================================================

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("passage", choices=sorted(core.PASSAGES))
    ap.add_argument("--dry")
    ap.add_argument("--manifests", nargs="*")
    ap.add_argument("--verify", nargs="*")
    ap.add_argument("--protect", default=os.path.join(HERE, "rzswap_protect.json"))
    ap.add_argument("--pair-mode", default="side", choices=("side", "row"))
    ap.add_argument("--max-swaps", type=int)
    ap.add_argument("--end-rows", type=int, default=1)
    ap.add_argument("--exclude", nargs="*", default=[])
    ap.add_argument("--out-dir", default=HERE)
    ap.add_argument("--preview-gap-audit", action="store_true")
    ap.add_argument("--no-sheet", action="store_true")
    a = ap.parse_args(argv)
    P = a.passage
    protect = jload(a.protect)
    opts = {"pair_mode": a.pair_mode, "end_rows": a.end_rows, "exclude": sorted(a.exclude)}
    if a.max_swaps is not None:
        opts["max_swaps"] = a.max_swaps
    if a.preview_gap_audit:
        dry = preview_dry(P)
        manifests = a.manifests or sorted(glob.glob(os.path.join(PROJECT, "DerivedAssets", "FlatV3", "Realism_20261007", "**",
                                                                 "IMPORT_MANIFEST*.json"), recursive=True))
        designs = designs_for(P, manifests, dry, {})
        for dsg in designs:              # PREVIEW: pretend imported + live, with a 500 cm wide zero box
            dsg.update({"imported": True, "exists": True,
                        "zero_bounds": {"min_y_cm": 0.0, "max_y_cm": 500.0} if dsg["side"] == "L" else
                        {"min_y_cm": -500.0, "max_y_cm": 0.0}})
        dry_for_plan = dict(dry, mode="DRY")
        plan = core.make_plan(dry_for_plan, designs, protect, opts)
        plan["refusals"].append("PREVIEW_NOT_APPLIABLE (GAP_AUDIT snapshot 6 Oct 21:54; run the live DRY)")
        plan["gates_ok"] = False
        tag = "%s_PREVIEW" % P
    else:
        dry_path = a.dry or os.path.join(HERE, "rzswap_dry_%s_LATEST.json" % P)
        dry = jload(dry_path)
        core.require(dry.get("passage") == P, "DRY_IS_FOR %s" % dry.get("passage"))
        manifests = a.manifests or dry.get("manifests") or []
        verify = a.verify if a.verify is not None else glob.glob(os.path.join(HERE, "..", "rzimport", "rzimport_verify_*_LATEST.json"))
        designs = designs_for(P, manifests, dry, imported_owners(verify))
        plan = core.make_plan(dry, designs, protect, opts)
        tag = P
    plan["made"] = datetime.datetime.now().isoformat(timespec="seconds")
    plan["manifests"] = manifests
    plan["foreign_records_naming_target_cues"] = foreign_records({s["cue_guid"] for s in plan["swaps"]})
    if plan["foreign_records_naming_target_cues"]:
        plan["flags"].append("FOREIGN_RECORDS name %d target cues' files (lights etc.; rzswap's REVERT compares only "
                             "its own panels, but a WHOLE-TEXT revert elsewhere would undo/clash): %s" % (
                                 len(plan["foreign_records_naming_target_cues"]),
                                 [h["path"] for h in plan["foreign_records_naming_target_cues"]][:6]))
    out_json = os.path.join(a.out_dir, "rzswap_plan_%s.json" % tag)
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=1, default=str)
    sheet = None if a.no_sheet else contact_sheet(plan, dry, os.path.join(a.out_dir, "rzswap_sheet_%s.png" % tag))
    print("RZSWAP_PLAN|passage=%s|swaps=%d|gates_ok=%s|hash=%s|confirm=%s|plan=%s|sheet=%s" % (
        P, len(plan["swaps"]), plan["gates_ok"], plan["hash8"], plan["confirm"], out_json, sheet))
    for s in plan["swaps"]:
        print("  %-14s %s  %-28s -> %-44s score %4d  y %.1f" % (s["label"], s["side"], (core.mesh_name(s["old_panel"]["mesh"]) or "")[:28],
                                                                s["new_owner"], s["score"],
                                                                s["planned_panel"]["local_transform"]["location"][1]))
    for x in plan["flags"]:
        print("  FLAG " + x[:300])
    for x in plan["refusals"]:
        print("  REFUSAL " + x[:300])
    return plan


if __name__ == "__main__":
    main()
    sys.exit(0)
