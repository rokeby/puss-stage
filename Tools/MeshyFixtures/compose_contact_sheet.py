"""Compose MeshyClean/contact_sheet.png from _renders (textured 3/4 view + slot map per asset) and merge the per-asset
records into cleanup_report.json. Plain Python (PIL), no Blender."""
import json, glob, os, datetime
from PIL import Image, ImageDraw, ImageFont
ROOT = r"E:\PussStage\DerivedAssets\Lighting\MeshyClean"
recs = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(ROOT, "SM_*", "*_record.json")))]
order = sorted(recs, key=lambda r: (r["class"] != "bulb", r["asset"]))
T = 300; cols = 4                         # 4 assets per row, each = textured + slot map
rows = (len(order) + cols - 1) // cols
W = Image.new("RGB", (cols * 2 * T, rows * (T + 46) + 40), (107, 107, 107))
D = ImageDraw.Draw(W)
try: F = ImageFont.truetype("arial.ttf", 15); Fs = ImageFont.truetype("arial.ttf", 12)
except Exception: F = Fs = ImageFont.load_default()
D.text((8, 10), "MeshyClean fixtures - left: base colour 3/4 ortho view; right: slot map (yellow 0 glow, grey-blue 1 metal, "
       "cyan 2 clear glass; x-ray) + pivot marker (red = +X beam, green = +Z). Red bar under each = 10 cm.", fill="white", font=Fs)
for i, r in enumerate(order):
    x = (i % cols) * 2 * T; y = 40 + (i // cols) * (T + 46)
    n = r["asset"]
    W.paste(Image.open(os.path.join(ROOT, "_renders", f"{n}_tex.png")).convert("RGB").resize((T, T)), (x, y))
    W.paste(Image.open(os.path.join(ROOT, "_renders", f"{n}_slots.png")).convert("RGB").resize((T, T)), (x + T, y))
    mk = r["renders"].get("pivot_marker_uv")
    if mk:
        P = lambda k: (x + T + mk[k][0] * T, y + (1 - mk[k][1]) * T)
        D.line([P("origin"), P("x_tip")], fill=(255, 30, 30), width=3)
        D.line([P("origin"), P("z_tip")], fill=(30, 220, 30), width=3)
        o = P("origin"); D.ellipse([o[0] - 4, o[1] - 4, o[0] + 4, o[1] + 4], outline="white", width=2)
    sz = r["final_size_cm"]
    D.text((x + 6, y + 4), n, fill="yellow", font=F)
    t2 = f"{sz[0]:.1f} x {sz[1]:.1f} x {sz[2]:.1f} cm | {r['tris']} tris" + (f" | LOD1 {r['lod1_tris']}" if r.get("lod1_tris") else "")
    D.text((x + 6, y + T + 4), t2, fill="white", font=Fs)
    D.text((x + 6, y + T + 22), "slots " + " / ".join(f"{s['index']}:{s['faces']}" for s in r["slots"]) +
           (f" | {len(r['warnings'])} warning(s)" if r["warnings"] else ""), fill=(255, 200, 120) if r["warnings"] else "white", font=Fs)
W.save(os.path.join(ROOT, "contact_sheet.png"))
report = {"generated": datetime.datetime.now().isoformat(timespec="seconds"),
          "script": "Tools/MeshyFixtures/build_meshy_fixtures.py (+ compose_contact_sheet.py)",
          "spec": "Docs/Conductor/MESHY_PROMPTS_BULB_HOUSING_2026-10-06.md (After Meshy)",
          "units": "cm in UE (Blender metres x 100); FBX_SCALE_UNITS, axis_forward=-X, axis_up=Z, Z up",
          "assets": {r["asset"]: r for r in order}}
json.dump(report, open(os.path.join(ROOT, "cleanup_report.json"), "w"), indent=1)
print("CONTACT_SHEET_OK", len(order))
