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
