# Morning check: cueing (5 Oct, about 5 minutes)

**What's new since last night**
- Each Passage has a **Choreography** sequence: `/Game/InfinityStage/Choreo/LS_Choreo_Passage_1` to `_6`.
  - Open the Master and double-click a Choreo section to direct in it.
  - Its 0:00 is the Passage start.
  - Bar and section markers come from the song.
- **Scenes 1, 2, 4, 5 and 6 can now pause and hold at a GO.**
  - **Scene 3 (the cellist) still refuses both in performance mode.**
- **Cue markers:** `GO <number> <label>`, e.g. `GO 12 Warmers out`.
  - Upper-case GO and a number, or the marker is ignored.
  - Optional `HOLD` / `PASS` after the number.
  - Defaults: Scenes and sequences HOLD; Choreos PASS.
- **Stage lamps (Show lamps) can be keyed in Sequencer.**
  - A hand edit in Details still saves to the Show.
  - Settings that are keyed keep their authored value in the Show.

**The PIE check (you drive it; tell me "done" afterwards)**
1. In `LS_Opening_Curtain_Baked`, press **M** at about 5 s and rename the marker to `GO 1 test`. Don't save.
2. Start PIE from the beginning. At about 5 s it **holds**.
3. Press **→**. It plays on.
4. Press **←** back to the start and play. It holds again. Press **Space**. It plays on.
5. Back again, then **hold →** into the stop and release. It **stays held**. Press → to continue.
6. Hold → through a Scene with sound. It's **silent while held** and the sound returns at 1×.

**Cleanup:**
- Stop PIE yourself.
- Close the Opening in Sequencer.
- Right-click the asset → Asset Actions → **Reload**. This drops the test marker.

**Rules while directing**
- Put a cue's first key at least a frame **after** its GO marker.
- No HOLD inside a Vamp region (it's demoted to PASS).
- A GO right at a Scene's first frame doesn't stop on a jump into that Scene.
- Don't open a Choreo that has a Camera Cut track: the rebuild refuses to nest it, because it would take the cat's camera.
