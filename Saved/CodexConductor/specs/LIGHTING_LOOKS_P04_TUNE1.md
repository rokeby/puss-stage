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
