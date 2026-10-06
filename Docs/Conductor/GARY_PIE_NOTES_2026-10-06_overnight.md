# Overnight plan — 6 Oct (Gary's answers ~00:40–00:55, his own session with the conductor)

- **Look applies:** "Apply all, stills for the morning" — every lighting change goes in tonight (each reversible, one REVERT per passage); stills for review.
- **P06 wings:** "Swap tonight with ceramic towers" — routed to Wings & Textures (they write the swap; conductor runs DRY/stills/APPLY).
- **C++ tonight (if ready by build time):** club "mover" spots (P05); bulb glass follows its light — per bulb STABLE / SLIGHT flicker / FAIL
  ("a flickering and dying bulb, not all bulbs! some should flicker only slightly and others be stable").
- **Rain:** "Prototype rain tonight" — P04, bench only, stills; nothing saved into the show.
- **Song markers:** refresh to Cameron's tracks (bar/§ grid for timing camera moves; GO markers untouched).
- **Tubes:** everywhere, low glow, 20% blinking; light only from fence-top rows outside P02.
- **Build:** yes — HUD (bay/cue/sequence), hold-Left rewind, light events, tubes, hangar-snap diagnostic/fix (+ movers, bulb glass).
- **P06 music:** the current Into Void track.

Editor order: S3 backdrop+marble -> S1 extend 245 s + narration after voices -> song markers -> P06 tail -> Opening -> P02 straighten (+handoffs, route actors)
-> retime P02–P05 -> P03 floor -> P06 wing swap (W&T) -> lighting P01–P06 (stills each) -> tests -> build -> reopen -> tubes -> rain bench
-> fog bench (after midnight) -> stills of every passage.

## Timing (Gary ~01:30): "transport gets confused or frustrated by something to do with sound or passage or sequence timing being out of sync"
- **Measured tonight:** the managed Master's section boundaries are NOT exactly the compiled Show segments — P06's end was 2 ticks
  SHORT before the rebuild (50603057 vs 50603059) and 2 ticks LONG after it (50973621 vs 50973619); Scene 6 started 2 ticks early.
  It tripped the P06 tool twice (Don't-Save restarts). A boundary frame can therefore belong to P06 by one clock and to Scene 6 by the
  other — a plausible contributor to "arrive at the hangar, camera snaps after a pause". Routed to the C++ build pass: find the rounding,
  check which clock the transport/CueDesk/Pilot uses, check audio pause/resume, fix if proven, else a cvar-gated two-clock logger.

## Overnight log (conductor)
- 01:18 **S3** backdrop restored (squashed by the 3 Oct far-wall rescale) + 8 marble tiles to 28.8 m (S3BWM-20261006-011800).
- 01:19 **S1** extended to 245 s (cuts cover, handoffs unmoved, Master match) + narration after Animal_Voices_1, 208.64–243.64 s.
- 01:19 **Song markers** refreshed (P01 35→28, P02 24→23, P03 16→17, P04 15→16, P05 90→16; no GO markers present).
- 01:24 **P06** +15.44 s → 126.0 s (two Don't-Save restarts first: the tool read section ranges as float seconds — a ~2-tick READ
  error, NOT Master drift; corrected by the C++ agent's float32 round-trip proof; gates now tolerate 8 ticks).
- 01:32 **Opening** applied: strobe on the 36.2 s entry, swivel 43.8–50 s, smooth rise to the curtain, warmers off (their live
  cones were 14.9/15.9, not the 33 recorded on 4 Oct — the cone write is parked as moot).
- 01:43 **P02 straighten HELD** for a supervised session: with the DOCK anchor P02's mouth moves 97 m / −66°, stranding the I1
  sleight mouth camera, the I1 stalls camera, the S2 handoff cameras, the car light and the lantern (no re-place tool for the I1 sleight).
- 01:46 **Retime P03 180→42.24 s (~262 cm/s), P04 180→50.40 s (~214 cm/s)**; tests green. **P05 refused**: 93 bays in 44 s =
  1070 cm/s and a tail shorter than the settle — needs Gary's call (keep long, loop/extend the song, or cut bays). P02 waits for its straighten.
- 01:47 **P04 back curtain** lead after the retime = 3.87 s (needs ~2.2 s) — left as is; restoring 5.0 s is one APPLY (−1.13 s) if wanted.
- 01:47 **P03 floor STOPPED (nothing saved)**: Ground off also blanked the Structure **Fixtures** and **Gridiron** layers. Parked;
  P02's floor step has the same flaw. Needs a different method (hide only the board layers, or bury them).
- 01:50 Build started with 7 held patches (LE, HD, RW, SD, TU, BG, MV).
