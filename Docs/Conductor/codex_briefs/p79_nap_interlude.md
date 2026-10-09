# P79 — "Nap" interlude after Scene 4: sleeping Puss, loops until GO (battery change) (Codex, offline; live by conductor)

Read `_house_rules.md` + known traps (str(FGuid) changes per call; channel names carry suffixes; BP subobject lists
repeat components; mechanism export_text gained SoundCues=). Offline only now.

## Gary, 9 Oct (his words)
"We will certainly need to change the battery of the dog halfway through the show … maybe after scene four … the dog can
take a nap after all this journeying and nap forever and ever until waking up later, and then we'll put Puss, in the video
and in the engine, in sleep mode, gently rising and falling, and we'll come in and change the battery of the dog. … its own
segment." Ends: LOOPS UNTIL GO. Place: "the clouds of P5 and S5 [could] actually be the dream … Puss could still be
running in the dream or simply be sleeping … a dream within a dream."

## Dedupe — reuse, don't rebuild
- Segment machinery: Interactions I1–I5 are segments between Scenes and Passages in the Master/Show (I2 tools:
  `Saved/CodexConductor/I2Order_20261008/`, job 24 `shrink_scene_playback.py`, managed-Master rebuild). Insert the Nap the
  same way, between S4 and P05; label agreed with the cueing stream ("Nap — battery change").
- Loop until GO: the transport already supports Vamp loops held until release (test `VampLoopsUntilRelease`, markers
  VampStart/VampEnd; S3 had vamp markers, see memory/records) and GO HOLD markers. Use authored markers, no C++.
- Sleeping Puss: the cat character (`CharBP_Cat_R`, AnimX clips; the 9 Oct cat silhouette catalogue
  `Saved/CodexConductor/CatSilhouettes_20261009/` lists 20 clips — find a sleep/lie/rest clip) and/or the shadow cat
  (`BP_InfinityStageShadowCat`; FT job 46 held cat-actions patch). "Gently rising and falling" = a slow breathing motion
  (loopable, seamless at the vamp boundary).
- Camera: the cat-is-the-camera rule applies to Passages, not Scenes/interludes; a slow, near-still framing on Puss.
- Video fallback: the Saturday filming tool (`Tools/Fallbacks/`) must film one loop of the Nap so the Cue Desk can play it.

## Build
1. DRY/APPLY/REVERT tool inserting the Nap segment after S4 (length = one seamless loop, args default 20 s) with VampStart/
   VampEnd around the loop and a GO HOLD to wake; downstream sections carried (patch K behaviour in source); exact census,
   targeted saves, read-back; SavedMasterMatchesShow + SceneCutBindingsResolve in the runbook.
2. The sleeping-Puss content: placement, the sleep/lie clip on loop, breathing (rise/fall amplitude + period args), dim
   warm/cool light (≤2 lights, no new shadow casters unless args), owned keys.
3. Transition plan into P05 as "the dream" (report options: fade-through, clouds rising, camera drift up) — plan only.
4. Harness +/- (loop seam continuity, vamp markers present, downstream timing unchanged, refuse if S4/P05 GUIDs drift).
Tiered report; deliver in your worktree; the conductor commits and runs it live.
