"""Grease v2 step 1 (OFFLINE): reproduce the two LIVE textures bit-for-bit from their builders, read-only.

  T_HP_S03_GreaseAtlas  <- DerivedAssets/S3Marble/Grime_20261007/T_S3MG_GreaseAtlas.png (sha pinned by the importer,
                           hp_grease_assets.py:45-46,170) built by s3mg_build_textures.py:237-258.  The RNG stream is
                           replayed in the builder's exact order (main():188-199 splats, then 242/245) WITHOUT writing
                           any of the builder's outputs.
  PrintNormal           <- DerivedAssets/FlatV3/HandPrints/atlas_job24d/T_S03_HandPrints_Normal.png (hp_grease_assets.py:51)
                           built by Tools/FlatV3/handprints/build_handprint_atlas.py:610-617 (aux = 4096*0.25 = 1024,
                           BOX resize of alpha, gaussian 1.5, height_to_normal(strength 2.0) :503-507, to_u8 :145-146).
Also saves the pre-quantisation float fields the v2 builder needs (alpha 4096, breakup) to an .npz in this folder.
Writes only Saved/CodexConductor/GreaseV2_20261008/repro_v1_report.json and repro_fields.npz.
"""
import hashlib
import importlib.util
import json
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ROOT = "E:/PussStage"
HERE = ROOT + "/Saved/CodexConductor/GreaseV2_20261008"
LIVE_ATLAS = ROOT + "/DerivedAssets/S3Marble/Grime_20261007/T_S3MG_GreaseAtlas.png"
LIVE_ATLAS_SHA = "8f85307b26db11725f31c8427381af46b5b4ea5507f6f50473d052333a553599"
LIVE_NORMAL = ROOT + "/DerivedAssets/FlatV3/HandPrints/atlas_job24d/T_S03_HandPrints_Normal.png"
LIVE_NORMAL_SHA = "d4d88af04c6efe564af2f7f248d77bd7028a6d8c9b7f3606fec0c9eca92dbf3b"   # atlas.json outputs
BASE = ROOT + "/DerivedAssets/FlatV3/HandPrints/atlas_job24d/T_S03_HandPrints_BaseColor.png"


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def load_builder():
    spec = importlib.util.spec_from_file_location(
        "s3mg_build_textures", ROOT + "/Saved/CodexConductor/S3MarbleGrime/s3mg_build_textures.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)          # module level only sets constants and rng = default_rng(SEED); main() not run
    return m


def repro_atlas():
    b = load_builder()
    layers = [b.photo_layers(i) for i in range(1, 5)]
    # replay the three tile splats of main() (lines 196-199) purely to advance the shared rng identically
    b.splat_tile(layers, "grease", (b.TILE, b.TILE), 26, (520, 520), amp=(0.25, 0.6))
    b.splat_tile(layers, "dark", (b.TILE, b.TILE), 18, (520, 520), amp=(0.2, 0.5))
    b.splat_tile(layers, "scratch", (b.TILE, b.TILE), 60, (600, 600), combine="max", amp=(0.5, 1.0))
    at = Image.open(b.ATLAS)
    alpha = np.asarray(at.getchannel("A")).astype(np.float32) / 255.0
    core = ndi.gaussian_filter(alpha, 3.0)
    bloom = ndi.gaussian_filter(alpha, 14.0)
    gtex = b.splat_tile(layers, "grease", alpha.shape, 90, (700, 700), amp=(0.6, 1.0))
    breakup = 0.55 + 0.45 * ndi.gaussian_filter(gtex, 2.0)
    drop = ndi.gaussian_filter(b.rng.random((alpha.shape[0] // 32, alpha.shape[1] // 32)).astype(np.float32), 1.0)
    drop = np.kron(drop, np.ones((32, 32), np.float32))[:alpha.shape[0], :alpha.shape[1]]
    drop = ndi.gaussian_filter(drop, 12)
    drop = np.clip((drop - drop.min()) / (drop.max() - drop.min()) * 1.6 - 0.15, 0, 1)
    grease_op = np.clip((0.85 * core + 0.35 * bloom) * breakup * (0.35 + 0.65 * drop), 0, 1)
    height = ndi.gaussian_filter(alpha * breakup, 4.0)
    albedo_w = np.clip(core ** 1.5 * 0.6 * breakup, 0, 1)
    ga = np.stack([grease_op, height, albedo_w], -1)
    ga = np.asarray(Image.fromarray((ga * 255).astype(np.uint8), "RGB").resize((2048, 2048), Image.LANCZOS))
    return ga, alpha, breakup, grease_op


def repro_normal():
    a = np.asarray(Image.open(BASE).getchannel("A"), dtype=np.uint8)
    atlas_a = a.astype(np.float64) / 255.0      # INFERRED equal to the builder's float alpha only after to_u8 round trip
    aux = 1024
    a_aux = np.asarray(Image.fromarray(atlas_a.astype(np.float32), mode="F").resize((aux, aux), Image.BOX),
                       dtype=np.float64)
    h = ndi.gaussian_filter(a_aux, sigma=1.5)
    dy, dx = np.gradient(h)
    n = np.stack([-dx * 2.0, -dy * 2.0, np.ones_like(h)], axis=-1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    n = n * 0.5 + 0.5
    return np.clip(np.floor(np.clip(n, 0, 1) * 255.0 + 0.5), 0, 255).astype(np.uint8)


def diff(a, b):
    d = np.abs(a.astype(np.int16) - b.astype(np.int16))
    return {"identical": bool((d == 0).all()), "max_abs": int(d.max()),
            "per_channel_identical": [bool((d[..., c] == 0).all()) for c in range(d.shape[-1])],
            "pixels_differing": int((d.max(-1) > 0).sum()), "mean_abs": round(float(d.mean()), 6)}


def main():
    rep = {"live_atlas_sha_ok": sha(LIVE_ATLAS) == LIVE_ATLAS_SHA, "live_normal_sha_ok": sha(LIVE_NORMAL) == LIVE_NORMAL_SHA}
    live = np.asarray(Image.open(LIVE_ATLAS).convert("RGB"))
    ga, alpha, breakup, gop = repro_atlas()
    rep["atlas_repro_vs_live"] = diff(ga, live)
    livn = np.asarray(Image.open(LIVE_NORMAL).convert("RGB"))
    rep["normal_repro_vs_live"] = diff(repro_normal(), livn)
    np.savez_compressed(HERE + "/repro_fields.npz", alpha=alpha, breakup=breakup.astype(np.float32))
    json.dump(rep, open(HERE + "/repro_v1_report.json", "w"), indent=1)
    print(json.dumps(rep, indent=1))
    ok = rep["live_atlas_sha_ok"] and rep["live_normal_sha_ok"] and rep["atlas_repro_vs_live"]["identical"] \
        and rep["normal_repro_vs_live"]["max_abs"] <= 1
    # normal: <= 1 LSB is expected (the builder fed its pre-quantisation float alpha; only the u8 PNG alpha is on disk)
    print("GV2_REPRO_V1_" + ("MATCH" if ok else "MISMATCH"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
