# PG7d carved page lettering report

[measured] The table is read from the offline APPLY output; each demo uses the current 0.5625 Puss framing and knee crop imported from `build_boy_puss_composite.py`. `Tools/ShadowGobo/Puppets/props.py:640`

| Demo | Frames | Unique cells | Grid | Min feature | GIF |
|---|---:|---:|---:|---:|---:|
| bucket | 100 | 49 | 7x7 | 7.37 px | 1.33 MB |
| page | 100 | 70 | 9x8 | 2.25 px | 1.61 MB |
| turnip | 100 | 7 | 3x3 | 9.53 px | 1.11 MB |
| pearl | 100 | 58 | 8x8 | 2.41 px | 1.02 MB |
| crown | 100 | 64 | 8x8 | 5.31 px | 0.91 MB |
| boots | 100 | 68 | 9x8 | 3.32 px | 1.34 MB |

[measured] The page demo has `curtain_preview_defocus025.gif` and `frame_strip_6.png`; its atlas is SDF 8192 and the preview uses BlurUV 0. `Tools/ShadowGobo/Puppets/prop_demos/clip_prop_page/atlas/manifest.json:14` `Tools/ShadowGobo/Puppets/prop_demos/clip_prop_page/atlas/manifest.json:49`
[measured] Carved page: angle -18.0 degrees, diagonal fill 0.85, narrowest wedge middle 2.253 px, page size 0.34 boy height. `Tools/ShadowGobo/Puppets/props.py:294`
[declaration-proven] The default `page_font` is None; the generated page SVG therefore uses closed polygons rather than a font reference. `Tools/ShadowGobo/Puppets/props.py:55`
[measured] The offline controls verify separate cut-outs, the requested principal-axis angle, a six-unit card margin, no font open, and all earlier prop checks. `Tools/ShadowGobo/Puppets/test_props_offline.py:45`
[inferred] Gary should visually approve the larger page scale (0.28 to 0.34 boy height), carved treatment, and spelling `Cagliuso`. `Tools/ShadowGobo/Puppets/props.py:53`
