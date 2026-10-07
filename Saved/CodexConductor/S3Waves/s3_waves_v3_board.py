"""Labelled 2x4 board of the perspective previews (offline). Writes waves_v3/previews/BOARD_persp_A_vs_B.png"""
from pathlib import Path
import cv2
import numpy as np
P = Path(__file__).resolve().parents[3] / "DerivedAssets" / "FlatV3" / "Scene3" / "waves_v3" / "previews"
SHOTS = [("B09_axis", "B09 axis, 35 mm, eye 1.75 m"), ("B02_wide", "B02 wide, 35 mm, eye 1.75 m"),
         ("B05_tele", "B05 tele, 85 mm, eye 1.45 m"), ("B04_main", "B04 'main' (brief pose), 35 mm, eye 1.25 m")]
NOTE = {"A": "A  woodblock / low sea - cool key + ground rows + haze", "B": "B  scroll / raked sea - nocturne key + WARM side option + haze"}
rows = []
for v in "AB":
    tiles = []
    for shot, lab in SHOTS:
        im = cv2.resize(cv2.imread(str(P / ("persp_%s_%s.png" % (v, shot)))), (800, 450), interpolation=cv2.INTER_AREA)
        for col, th in ((0, 3), (235, 1)):
            cv2.putText(im, "%s | %s" % (v, lab), (12, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (col,) * 3, th, cv2.LINE_AA)
        tiles.append(im)
    head = np.full((40, 3200, 3), 28, np.uint8)
    cv2.putText(head, NOTE[v], (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (235, 235, 235), 1, cv2.LINE_AA)
    rows += [head, np.hstack(tiles)]
cv2.imwrite(str(P / "BOARD_persp_A_vs_B.png"), np.vstack(rows))
print(P / "BOARD_persp_A_vs_B.png")
