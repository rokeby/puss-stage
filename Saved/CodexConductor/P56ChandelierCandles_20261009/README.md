# P56 chandelier candle flames

Offline-built Unreal project-Python tool. It is intentionally not live-tested in
this job. The create-only target is `/Game/Scenes/Effects/BP_Effect_ChandelierCandle`;
the source candle and Stylish Fire assets are never edited.

## Conductor order

1. Replace `actor_label` and `socket_json` in `p56_chandelier_candles_args.json`.
2. Set `mode` to `DRY`, leave `confirm` empty, then submit
   `p56_chandelier_candles_request.json` through the guarded project-Python MCP route.
3. Inspect `P56_CHANDELIER_DRY_OK`, including the complete socket list and counts.
4. Set `mode` to `APPLY` and `confirm` to `APPLY P56CHANDELIER`; submit again.
5. Require `P56_CHANDELIER_APPLY_OK`, a clean census, the originals JSON, backup,
   selective saves, and asserted live read-back.
6. Set `mode` to `READBACK`, clear `confirm`, submit in a fresh call, and require
   `P56_CHANDELIER_READBACK_OK|state=applied`.
7. For the reversible check, set `mode` to `REVERT` and `confirm` to
   `REVERT P56CHANDELIER`; submit and require `P56_CHANDELIER_REVERT_OK`.
8. Set `mode` to `READBACK`, clear `confirm`, submit once more, and require
   `P56_CHANDELIER_READBACK_OK|state=reverted|actors=0`.

REVERT removes only the tagged level actors. It deliberately preserves the
created child Blueprint: deleting a `.uasset` is a permanent deletion and is not
authorized by this job. The pre-change level backup makes the actor removal
recoverable.
