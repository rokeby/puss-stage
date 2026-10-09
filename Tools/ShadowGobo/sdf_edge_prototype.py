"""Prototype: hard-edge vs signed-distance-field (SDF) gobo cells, judged at real curtain magnification.

Renders one boy pose at 2048 px, builds cells four ways (hard 409 / hard 819 / SDF 819 / SDF 409), projects each
through the offline material twin (gobo_twin.light_function) at a high screen resolution, and crops the face.

SDF encoding (R): 0.5 at the silhouette edge, rising into light, falling into shadow:
    v = 0.5 + signed_distance_px / (2 * spread_px)        (signed distance > 0 inside the LIGHT)
G holds the same SDF with a wider spread, so the material's existing Defocus mix (lerp R -> G) softens the edge
coherently: both channels cross 0.5 at the same edge, G just ramps more slowly.

    python sdf_edge_prototype.py <out_dir>
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "Puppets"))
import gobo_twin as tw  # noqa: E402
import animated_gobo as ag  # noqa: E402  (gobo_twin puts Saved/CodexConductor on the path)
import boy_rig as b  # noqa: E402

HI = 2048
GUTTER = 8


def hires_frame():
    pose = b.P(**b.RUB_A, face=dict(b.SOB, eyes="shut", tears=[0.3]))
    cx, cy, size = 540.0, 560.0, 1450.0
    view = dict(x0=cx - size / 2, y0=cy - size / 2, scale=HI / size, w=HI, h=HI)
    return np.asarray(b.render_pose(pose, ss=2, view=view), dtype=np.float64) / 255.0  # 1 = light


def signed_distance(trans):
    light = trans > 0.5
    return ndimage.distance_transform_edt(light) - ndimage.distance_transform_edt(~light)  # hi-res px


def cell_hard(trans, cell):
    inner = cell - 2 * GUTTER
    im = Image.fromarray((trans * 255).astype(np.uint8)).resize((inner, inner), Image.LANCZOS)
    a = np.pad(np.asarray(im, dtype=np.float64) / 255.0, GUTTER, mode="edge")
    return a, a  # G = R (no blur): isolate edge quality


def cell_sdf(sd_hi, cell, spread=6.0, wide=4.0):
    inner = cell - 2 * GUTTER
    sd = np.asarray(Image.fromarray(sd_hi.astype(np.float32), mode="F").resize((inner, inner), Image.BILINEAR))
    sd = sd * (inner / float(HI))  # -> cell px
    r = np.clip(0.5 + sd / (2 * spread), 0, 1)
    g = np.clip(0.5 + sd / (2 * spread * wide), 0, 1)
    return np.pad(r, GUTTER, mode="edge"), np.pad(g, GUTTER, mode="edge")


def project(R, G, cell, defocus=0.0, px=1600, crop=(0.42, 0.22, 0.80, 0.60)):
    P = dict(ag.SCALAR_DEFAULTS)
    P.update({"Cols": 1.0, "Rows": 1.0, "Frames": 1.0, "GutterUV": GUTTER / float(cell), "CellUV": 1.0,
              "Scale": 0.7071, "BorderDepth": 1.0, "BorderAspect": 1.88, "HandAmp": 0.0, "Defocus": defocus,
              "BlurUV": 0.0})
    x0, y0, x1, y1 = crop
    sx = x0 + (x1 - x0) * (np.arange(px) + 0.5) / px
    sy = y0 + (y1 - y0) * (np.arange(px) + 0.5) / px
    SX, SY = np.meshgrid(sx, sy)
    UV = np.stack([1.0 - SY, SX], -1)
    lf = tw.light_function(R, G, P, UV, 0.0, 0.0, 0.0)
    img = (lf[..., None] * np.array([1.0, 0.77, 0.47]) * 0.95 + 0.03) ** (1 / 1.4)
    return Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))


def main(out):
    out.mkdir(parents=True, exist_ok=True)
    trans = hires_frame()
    sd = signed_distance(trans)
    variants = [("A hard edge, 409 px cell (current RT 4096)", *cell_hard(trans, 409), 409, 0.0),
                ("B hard edge, 819 px cell (8192)", *cell_hard(trans, 819), 819, 0.0),
                ("C distance field, 819 px cell", *cell_sdf(sd, 819), 819, 0.0),
                ("D distance field, 409 px cell", *cell_sdf(sd, 409), 409, 0.0),
                ("E distance field 819, Defocus 0.25", *cell_sdf(sd, 819), 819, 0.25),
                ("F distance field 819, Defocus 0.5", *cell_sdf(sd, 819), 819, 0.5)]
    tiles = []
    for name, R, G, cell, de in variants:
        im = project(R, G, cell, de, px=700)
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 360, 22], fill=(20, 20, 20))
        d.text((6, 5), name, fill=(255, 255, 255))
        tiles.append(im)
    w = tiles[0].width
    sheet = Image.new("RGB", (w * 3, w * 2))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % 3) * w, (i // 3) * w))
    sheet.save(out / "edge_compare.png")
    print("saved", out / "edge_compare.png")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
