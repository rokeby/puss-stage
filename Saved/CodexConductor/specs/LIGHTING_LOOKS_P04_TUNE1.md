# Lighting looks tune 1 (Gary, 3 Oct, his own words in the Conductor 4 session, on the P04 prototype video):
# "moody should have more partial lighting, not everything needs to be visible all the time but a variation in what is
# visible and how visible as we move gives some mystery while blackness gets dissolved into muddiness rather than mystery in
# these images. 5-6 are nice but could be less warm or more varied between warm and cool, could also bring in more colour
# spaces." Conductor's read (agreed by Gary): industrial reads heavy red-orange, not sodium; all looks too warm.
Change lighting_looks.json recipes (tool: Saved/CodexConductor/lighting_looks_apply.py; it REVERTs then re-APPLYs):
- MOODY: no black mud. PARTIAL pools that change as we move: per bay, light only part of a wing (a slot/blade from a low side
  light on one edge, alternating sides bay to bay), one cool moonlight-blue rim (6500-8000 K, low) from the far tree, a warm
  practical as the brightest point; something always readable in frame but never all of it. Add a low cool ambient floor
  (very dim, via the side light's spill, not a fill) so darks read as deep blue-black, not muddy brown.
- INDUSTRIAL: true sodium (~1900-2100 K, slightly yellow, less saturated), one flickering cold-white tube (5000 K) as contrast,
  a beam through the gap; less red.
- THEATRICAL: split warm/cool: warm key (3200 K) from one side, cool fill or back (steel blue / lavender gel) from the other;
  and a saturated colour accent per bay (one gel per bay from a varied palette: magenta, cyan, amber, green), so 5 and 6 differ.
Keep shadow casters <= 43 in P04. DRY/APPLY (it reverts the current looks first), read-back, both tests, landed STATUS, then
re-record the same P04 bays 1-6 video + 6 stills (same method) for Gary. Rules as before (PIE off first, never end anyone's
PIE, never quit, never Save All, purge modules, backups, stop on first failure; no restarts). Commit nothing.

## Next (tune 2, after tune 1's recording; Gary 3 Oct: "practicals was a nice idea")
More PRACTICALS in every look: visible motivated sources on the lighting trees and fence: bare bulbs on cords, cage work
lamps, an old tube, a desk/clamp lamp; 1-3 per bay, small, each with its own light (shadowless, short attenuation), some
flickering, some dead (off) for rhythm. In MOODY they are the main sources; in THEATRICAL accents.

## TUNE 2 (Gary 3 Oct, his answer: "Fix moody + add practicals"). Tune 1 left MOODY almost unchanged (stills
## LightingLooks/20261003_172218: bays 1-2 still mostly black): find out WHY first (read back the moody fixtures' live intensity,
## attenuation, aim vs the wing positions; are the blades/rim actually hitting a wing? units: candela vs lumens?), then fix so that
## in each moody bay a PART of a wing is clearly lit (a blade on one edge, alternating sides), a cool rim reads, and darks are
## blue-black, not mud. Then PRACTICALS in all looks (1-3 per bay: bare bulbs on cords, caged work lamps, a tube, a clamp lamp; each
## a small visible emissive mesh (engine basic shapes + an emissive MI is fine) with its own shadowless short light; some flicker,
## one dead per look). Shadow casters <= 43. Revert-then-apply, read-back, both tests, landed STATUS, re-record the same video + 6
## stills.

## TUNE 3 (Gary 3 Oct, his answers in the Conductor 4 session, on tune 2's video LightingLooks/20261003_210954):
- MOODY: "Like bay 2, is good, darker recesses could be darker but lit floor is good". Bay 1 to match bay 2's balance (partial,
  legible, lit floor pool); recesses darker in both (reduce spill/ambient in the depths; keep the floor pool and the edge blade).
- INDUSTRIAL: "Pull bay 3 down, fix bay 4 hue". Bay 3 about -40% (no wash), bay 4 sodium yellow-orange WITHOUT pink (check gel/temp
  mixing with the theatrical accents bleeding over), the tube stays as the cold contrast.
- THEATRICAL: "could have more light beams cast across floor and more shadow between bays, where I will also later place objects,
  currently theatrical's wings are quite flat and unvaried in lighting". So: hard-edged beams/shafts raking ACROSS the floor
  (low-angle spots or gobo slashes, haze-visible); DARK GAPS between bays (light pools stop short of the bay boundary); wings
  modelled, not flat (light from one side and a grazing angle, gradients top-to-bottom, a cutter/barn-door edge across part of a wing,
  the accent gel only on part of the surface).
Keep shadow casters <= 43. Revert-then-apply, read-back, both tests, landed STATUS, re-record the same video + 6 stills.

## TUNE 4 (queued; Gary 3 Oct: "Occasional lights that move towards the camera and cause glare and lens flare could be nice too")
An EVENT, not a look: occasionally (about 1 per 4-6 bays, varied) a light SWEEPS toward the lens: a moving-head spot or a
follow spot panning across the corridor and briefly into camera, or a work lamp swung on a cord. Keyed by camera distance like the
looks (rotation/pan keys on the fixture), with a short peak of glare: check the passage camera's post-process (Bloom, Lens Flares
intensity/threshold/bokeh) actually produces lens flare from an in-frame bright source (read the PPV/camera settings; enable
modestly if off; report the values), and haze so the beam reads. Rare and brief, never a wash. One instance in P04 bays 1-6
first, recorded for Gary.

## FLASH EVENTS + A BLACK PASSAGE (Gary 3 Oct, noted for tune 4+): "total almost blackened darkness works really well if we can do
## flash, like a polaroid flash effect, and maybe we can use infrequent bright blinking lights in a fairly dark part of a passage,
## in moody at least, and also think about making one passage basically black, perhaps p04, while introducing trickling sequences
## of bright flashes to show architecture and texture"
- POLAROID FLASH: a near-instant, very bright, cool-white burst from AT/near the camera (a point/spot light parented to the
  camera, ~1-2 frame attack, ~0.2-0.4 s decay), so everything in front is suddenly revealed with hard frontal light and black
  shadows, then gone; optional short exposure lag (no auto-exposure pumping: fixed exposure). Event, keyed by camera distance.
- INFREQUENT BLINKERS: in moody bays, single bright practicals that blink rarely and irregularly (seeded, never periodic).
- THE BLACK PASSAGE (candidate P04, Gary's call): base look ~black (only a floor-edge glimmer), revealed by TRICKLING SEQUENCES
  of flashes: bursts of 2-5 flashes at irregular intervals, some from the camera, some from fixtures deeper in the bays (so
  architecture and texture show from different angles), with long dark gaps. Prototype on P04 bays 1-6 after tune 3/4 for Gary.
