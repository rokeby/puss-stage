# P02 integration seam

The active P02 builder is in the main asset tree, not this git worktree:
`E:/PussStage/DerivedAssets/FlatV3/Overnight/P02Industrial/build_p02_industrial.py`.
Do not copy or replace that builder. After the Blender bake releases, import
`chainlink_weave.py` beside it and route only the chain-link construction call
through `dispatch_p02_chainlink`:

```python
result = chainlink_weave.dispatch_p02_chainlink(
    params["fence"],
    legacy_builder=lambda _p: mod.build_fence(params),
    weave_builder=lambda _p: build_fence_with_p57_weave(mod, params),
)
```

`build_fence_with_p57_weave` should retain the existing P02 posts, rails, tarp,
concertina wire, sockets, four-slot ordering, UV contracts, right-side mirror,
and FBX validation. Replace only the old `chain_strip_prototype`/linked-instance
block with `build_blender_lods`, using a `WeaveConfig` whose width and height are
read from that asset's fence parameters. The option is exactly
`params["fence"]["chainlink"] = "weave"`; absent, `"off"`, and `"legacy"` all
call the original builder object verbatim.

The industrial material coordinate remains
`/Game/Scenes/Wings/PaintedSurface/Industrial/M_Wing_IndustrialTiling_Master`.
Chain-link is tubular geometry, so the Wing V2 10 cm slab-thickness rule does
not apply; the surrounding P02 asset must retain its existing V2 slot, handedness,
socket, UV, and re-import gates.

No Blender or Unreal execution is authorized by this note.
