# PIE test list, 5 Oct (everything new since last night)

Play from the start, or use **PIE Starts At Playhead** to jump to a Passage. Note what you see beside each line.
Nothing here needs saving. If you change something, save only the Show and the level (never Save All).
If you edit a Choreo while testing, close it in Sequencer before handing back (opening the Master dirties the map).

## 0. Cueing check (5 min, from this morning)
- [ ] `Docs/Conductor/CUEING_MORNING_CHECKLIST_2026-10-05.md`: GO hold / → / Space / ← and the held silence.

## 1. Opening → P01: "full, rich, theatrical"
- [ ] Dark walk-in, then the hallway ping-on ahead of the camera, then warm pools. Too many dark GAP bays for "full"?
- [ ] **Iron girders and the rig** overhead. Do they read, and is the deck (20 m) ever seen?
- [ ] **TOP lamps now hang just under the girders** (about 1.3 m lower than before). Are the lamp bodies visibly
      clamped under the steel (not floating), and do their pools still land where you want?
- [ ] **Dark wet floor:** reflections and puddles. Is there a step at the hangar pit edge (5.5 cm)?

## 2. P02: the breakdown
- [ ] **Bays 1–11:** stage rig working, theatrical and lurid pops. Bay ~8 has a very heavy acid-green haze; too much?
- [ ] **Bays 12–19:** stage lights blink harder, dim, and go out behind the camera; colour drifts cold.
- [ ] **Office tubes** (bays 12–19 only): four rows under the deck, some dead, a hum flicker, cold-green tint.
      Too bright or too dim? Want them earlier or later?
- [ ] **Car light** ("P02 Car Light (trial, Gary to tune)", house left near bay 15). It passes every 11 s ± 4 s.
      **Known to be far too bright** (it floods the frame white). Tune it in Details while PIE runs, then copy the values:
      `Peak Intensity` (try 2500), `Outer Cone Degrees`, `Attenuation Radius`, `Start/End Offset`, `Arc Control Offset`.
- [ ] **Pause** (the interlock or a GO hold): does the car freeze? **Scrub** back: does it follow?
- [ ] **Bays 20–23 shrine:** keep the mystic look, or go cold too?
- [ ] P02's route still **curves** (you chose to keep it). Does the rig follow the curve cleanly?

## 3. P03
- [ ] **Rig Slash breakups**: the 14 slash lamps are 20 cm lower. Do the slashes still cut through the gaps?
- [ ] Iron girders and the rig. The TOP lamps are under the girders.

## 4. P04
- [ ] **CV12B gallery wings** (W&T's curved recut): first look on stage.
- [ ] Tune-4 beams (deliberately intermittent), the lens flare at its default, and the **default strobe**
      ("P04 Strobe (default, Gary to place)", 1 s with a ghost). Move it where you want it.
- [ ] **Bays 1–6 look lamps:** being re-hung under the girders now (see the note below). Check they still light the bays as approved.

## 5. P05
- [ ] **The full underpass rig**: laced columns, piers, knees, deck. Your "good to start tweaking" baseline.
- [ ] **The dark "cubes"** along the horizon are the score's lamp bodies (clamps, ceiling lamps, dead bulbs).
      Keep them, restyle them, or remove them?
- [ ] **The black jagged shape** inside the clouds (10% and 30% frames): is this the "strange artifact"?

## 6. P06
- [ ] Grand gold failing bay by bay; black-mode bays 2–10; the void. **The candle is gone.**
- [ ] At ~10% the frame was blown white by a bright doorway. Expected dark there. What is it?

## 7. Interaction 1 curtain sleight
- [ ] The curtain falls, then the shadow-play hold "GO 10" at about 7:50 (→ to continue).

## 8. Performance (optional, 2 min)
- [ ] Console `stat unit` (then `t.MaxFPS 0` to uncap; set it back to `t.MaxFPS 60` afterwards). Read the frame
      times in P02 bays 12–19 (tubes plus car) and mid-P05 (full rig). Tell me the GPU ms.

**When you're done:** stop PIE yourself, then tell me "done" and anything you changed, so I can read it back.

### Note: lamp re-hang (running while you read this)
Gary, 5 Oct: "rehang to correct physical position on girders and same for all lamps". The score TOP lamps in all six
Passages already hang clamped just under the girder (top of housing ≈ 5 cm below the steel, directly under the cross
beam). The remaining lamps inside the girder band are being moved the same way: P04's 12 look lamps (bays 1–6) and 2 in P05.
The tools refuse while PIE runs, so this happens only while the editor is free.
