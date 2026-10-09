# PG7c shadow props Gary-notes report

[measured] The table is read from the offline APPLY output; each demo uses the current 0.5625 Puss framing and knee crop imported from `build_boy_puss_composite.py`. `Tools/ShadowGobo/Puppets/props.py:544`

| Demo | Frames | Unique cells | Grid | Min feature | GIF |
|---|---:|---:|---:|---:|---:|
| bucket | 100 | 49 | 7x7 | 7.37 px | 1.33 MB |
| page | 100 | 70 | 9x8 | 4.66 px | 1.47 MB |
| turnip | 100 | 7 | 3x3 | 9.53 px | 1.11 MB |
| pearl | 100 | 58 | 8x8 | 2.41 px | 1.02 MB |
| crown | 100 | 64 | 8x8 | 5.31 px | 0.91 MB |
| boots | 100 | 68 | 9x8 | 3.32 px | 1.34 MB |

[measured] Every demo has `curtain_preview_defocus025.gif` and `frame_strip_6.png` beside it. `Tools/ShadowGobo/Puppets/props.py:521`
[measured] Bucket pour gate: 31 required frames; minimum 1661 water-on-light pixels at 480 px; maximum pail/boy overlap 0 pixels; all pass=True. Per-frame evidence: `clip_prop_bucket/pour_visibility_per_frame.json`. `Tools/ShadowGobo/Puppets/props.py:455`
[measured] Shorter falls and fewer droplets reduce unique cells directly; static holds already de-duplicate to one cell. `Tools/ShadowGobo/Puppets/props.py:293`
[inferred] Gary should confirm the page spelling (default `Cagliuso`; his note said `Camuso`) and visually approve the scroll, fat turnip, lip-origin pail pour, pearl gleam, and Puss-sized baby booties before Unreal application. `Tools/ShadowGobo/Puppets/props.py:46`
