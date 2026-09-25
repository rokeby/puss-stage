# Opening curtain and viewport transport — 14 September 2026

The opening now establishes Passage 1's starting camera before revealing it. Its curtain is placed in the foreground, sized from that camera's lens, and despawns at the opening boundary. PIE keyboard controls use the same Show transport as the Cue Desk.

## Operator behavior

- A normal PIE start with the production Show's Auto Play enabled plays the opening, then holds at Passage 1. The authored timing remains: closed 0–2 seconds, rising 2–6, open 6–15, ready hold at 15.
- Click the PIE game viewport to give it keyboard focus. **Space** plays/holds the current segment; **Right Arrow** advances to the next segment; **Left Arrow** goes to the preceding segment. A new Passage is held; entering a Scene or SEQ starts it. Use Space to GO from the Passage 1 ready hold.
- **PIE Starts At Playhead** now respects the Show's Auto Play setting after seeking. Previously the seek always paused, even when Auto Play was enabled.
- Starting bounded playback reclaims the current shot after Sequencer starts. This prevents the previous camera from being restored immediately after a jump or Next Segment command.
- The Passage evaluation template rejects swept evaluation times at or beyond its exclusive end. The runtime trace showed an outgoing Passage claiming its camera on the first Scene tick; this guard prevents that delayed takeover.

## Scope

Runtime changes are in the Show Root, Transport Controller and Show Game Mode. The Show Game Mode now supplies a Player Controller with viewport keyboard bindings. Explicit sequence Camera Cuts remain authoritative over the opening's default Passage camera. The Cue Desk startup handler preserves autoplay after a rehearsal seek.

Only `LS_Opening_Curtain` was changed as an authored asset. Its distance is 100 cm instead of 1500 cm. Mesh scale and open/closed offsets were calculated from Passage 1's 25 mm lens, 23.76 mm sensor width and the mesh bounds, with 20% coverage margin. Its spawn section is bounded to frames 0–375. The sequence still runs at 25 fps and no Master retiming was required.

The user's saved level, `LS_DevScene_03` and `LS_Clams` are preserved against the checkpoint taken after the user closed Unreal. Interaction 1's 0.61 curtain keys are unchanged; its test still expects 1.0. This repair does not certify the other curtain transitions' coverage.

## Evidence

Evidence is under `Saved/CodexSceneTransitions/`: `opening_asset_result.json`, `opening_verification.json`, the three `Opening_*_After.png` game-viewport captures, `opening_transition_regression.json`, and `opening_final_audit.json`. Final build/test logs are `Saved/Logs/OpeningPlayback-Boundary-*`.

The opening's closed, rising and revealed frames were rendered and inspected. The automatic stop at tick 360001 is one Show tick (about 42 microseconds) past the exact boundary and remained stationary during the ready hold. Space resumed Passage 1; advancing to Scene 1 started playback and retained its camera across subsequent world ticks. All six Passage-to-Scene transitions and Scene-end holds passed again; 165 Shore body/cloth samples passed through the one Show player. The full suite is 43/44, with only the existing Interaction 1 curtain-value assertion failing. Final audit: `opening_final_audit.json`.

Backup: `Backups/PreOpeningPlayback-20260914-155406`, including source, original curtain assets, the user's saved checkpoint and the opening asset immediately before authoring.

An uninterrupted Passage 3 tail → Scene 3 run also reached `ClamCam1` at 30.016 seconds into the Scene; the game-viewport capture was inspected. Evidence: `opening_shore_render.json` and `OpeningRepair_Scene3_Shore_From_Show.png`. Saved Unreal readback finished with zero dirty packages.
