# PG7b shadow props revision report

[measured] The table is read from the offline APPLY output; each demo uses the current 0.5625 Puss framing and knee crop imported from `build_boy_puss_composite.py`. `Tools/ShadowGobo/Puppets/props.py`

| Demo | Frames | Unique cells | Grid | Min feature | GIF |
|---|---:|---:|---:|---:|---:|
| bucket | 100 | 49 | 7x7 | 6.63 px | 1.32 MB |
| page | 100 | 70 | 9x8 | 4.66 px | 1.42 MB |
| turnip | 100 | 13 | 4x4 | 7.13 px | 1.47 MB |
| pearl | 100 | 58 | 8x8 | 2.41 px | 1.01 MB |
| crown | 100 | 64 | 8x8 | 5.31 px | 0.91 MB |
| boots | 100 | 68 | 9x8 | 3.32 px | 1.42 MB |

[measured] Every demo has `curtain_preview_defocus025.gif` and `frame_strip_6.png` beside it. `Tools/ShadowGobo/Puppets/props.py`
[measured] Bucket pour gate: 31 required frames; minimum 1577 water-on-light pixels at 480 px; maximum pail/boy overlap 0 pixels; all pass=True. Per-frame evidence: `clip_prop_bucket/pour_visibility_per_frame.json`. `Tools/ShadowGobo/Puppets/props.py`
[measured] Shorter falls and fewer droplets reduce unique cells directly; static holds already de-duplicate to one cell. `Tools/ShadowGobo/Puppets/props.py`
[inferred] Gary should decide whether the Cagliuso word remains and visually approve the revised bucket staging, turnip, pearl gleam, and Puss-sized cavalier boots before Unreal application. `Tools/ShadowGobo/Puppets/props.py`
