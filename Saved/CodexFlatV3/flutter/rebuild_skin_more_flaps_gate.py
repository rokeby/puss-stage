"""OFFLINE gate: re-run build_skin.build for ONE live _o2 skin with the SAME args/seed into this folder,
(a) unchanged  -> textures must be bit-identical to the live _o2 files and flaps.json identical (positive control);
(b) max flaps N -> textures must STILL be bit-identical; only flaps.json may differ.
flap_descriptors draws no RNG (build_skin.py:622-686) and runs after build_torn_peels (build_skin.py:795-801), so
(b) should not re-roll the skin. This script proves or refutes that. Writes only under Saved/CodexFlatV3/flutter/."""
import hashlib, json, sys, shutil
from argparse import Namespace
from pathlib import Path
sys.path.insert(0, r"E:\PussStage\Tools\FlatV3")
import build_skin as bs

N = int(sys.argv[1]) if len(sys.argv) > 1 else 12
ST = Path(r"E:\PussStage\DerivedAssets\FlatV3\Realism_20261007\P04_gothic_blasted_trees\13_gothic_arch_ruin\stage1\P04_real_13_gothic_arch_ruin_R")
OWNER = ST.name
LIVE = ST / "skin_v3"
OUT = Path(r"E:\PussStage\Saved\CodexFlatV3\flutter\skin_gate")
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()

def args_for(out):
    old = json.loads((ST / "skin" / f"{OWNER}_skin_manifest.json").read_text(encoding="utf-8"))
    return Namespace(  # = rz2_build_one.py:146-161
        mask=Path(old["inputs"]["mask"]), art=Path(old["inputs"]["art"]), older_poster=Path(old["inputs"]["older_poster"]),
        paper_displacement=Path(old["inputs"]["paper_displacement"]), paper_roughness=Path(old["inputs"]["paper_roughness"]),
        texture_root=Path(r"E:\PussStage"), aged_output=out / "aged_unused", stencil_text=old["asset"],
        height_cm=float(old["panel_size_cm"][1]), width_cm=float(old["panel_size_cm"][0]),
        color_width=int(old["textures"]["SkinColor"]["size_px"][0]), color_height=int(old["textures"]["SkinColor"]["size_px"][1]),
        asset_name=old["asset"], output=out, diagnostics_output=None, seed=int(old["deterministic_seed"]),
        peel_percent=float(old["peel"]["target_percent"]), peel_profile="pilot-isotropic",
        substrate_profile=old["front_colour"]["substrate_profile"], texture_suffix="_o2", skip_aged_textures=True)

def compare(out):
    rows = {}
    for p in sorted(LIVE.glob("T_*_o2.png")):
        q = out / p.name
        rows[p.name] = q.is_file() and sha(p) == sha(q)
    return rows

orig = bs.flap_descriptors
def patched(peeled, seam, pw, ph, name):
    import numpy as np, cv2, math
    # identical body to build_skin.flap_descriptors with candidates[:5] -> [:N] and the 3..6 check lifted
    src = orig.__code__
    return _n(peeled, seam, pw, ph, name)

def _n(peeled, seam, pw, ph, name):
    saved_cap = N
    import types
    code = Path(bs.__file__).read_text(encoding="utf-8")
    start = code.index("def flap_descriptors(")
    end = code.index("\ndef age_colour(")
    body = code[start:end].replace("candidates[:5]", f"candidates[:{saved_cap}]").replace(
        "if not (3 <= len(result) <= 6):", f"if not (3 <= len(result) <= {saved_cap}):")
    ns = dict(bs.__dict__)
    exec(compile(body, "flap_descriptors_N", "exec"), ns)
    return ns["flap_descriptors"](peeled, seam, pw, ph, name)

report = {"owner": OWNER, "n": N}
for tag, fn in (("A_unchanged", orig), ("B_maxflaps", _n)):
    out = OUT / tag
    if out.exists(): shutil.rmtree(out)
    out.mkdir(parents=True)
    bs.flap_descriptors = fn
    bs.build(args_for(out))
    bs.flap_descriptors = orig
    flaps = json.loads((out / f"{OWNER}_flaps.json").read_text())["flaps"]
    live_flaps = json.loads((LIVE / f"{OWNER}_flaps.json").read_text())["flaps"]
    report[tag] = {"textures_bit_identical": compare(out), "flap_count": len(flaps),
                   "first5_equal_live": flaps[:5] == live_flaps[:5] if tag == "B_maxflaps" else flaps == live_flaps}
    print(tag, json.dumps(report[tag]))
(OUT / "skin_gate_report.json").write_text(json.dumps(report, indent=1))
