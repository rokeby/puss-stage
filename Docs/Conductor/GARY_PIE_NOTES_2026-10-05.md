# Gary's PIE notes, 5 Oct (as he drops them; status per note)

1. **Waves in P01** (editor viewport screenshot): the 9 "S3 Wave Split" flats sit inside P01 at world x 3,665–5,335,
   y −500…500, which are exactly their recorded offsets relative to "S3 Hangar Root". Their attachment to the root has been lost
   [measured: probe_waves.json; cause inferred]. **Fix ready:** `Saved/CodexConductor/s3_wave_reattach.py` (DRY, then APPLY with
   a beach-landing gate). Runs when PIE is off. Owner: conductor.
2. **"There really doesn't look like there's a 5 cm edge on these wings"** (P01 PIE screenshot: the stone pillar wing
   on the left and the foliage wing behind it read paper-thin at a grazing angle). Routed to Wings & Textures, who own
   wing thickness (V2 = 10 cm explicit thickness; V3 = Front/Flap/Timber/Edge slots; the pipeline's 5 cm default is legacy).
   Status: asked W&T which profile these P01 wings were built with and whether the Edge slot renders.
3. On-screen in PIE: "RAY TRACING GEOMETRY – ALWAYS RESIDENT MEMORY EXCEEDS 20% OF THE BUDGET (97.6 MiB / 400 MiB)" and
   "GO1 NO DATA" (expected: the dog isn't connected). The ray-tracing line is a warning, not an error [inferred]; the
   new rig and tube ISMs add ray-tracing geometry. Worth a look if Lumen hardware RT is on.
4. **"Lots to do on P01 lighting but that's ok."** (Directing, his.)
5. **Stand-in curtain that falls at the end of the passage ("we had that once already").** Records: the transitions only
   ever had the velvet drape flying in and out with no fall (`Docs/ChaosClothCurtain.md:683-690`); a drape that falls at
   each passage end was listed as not built. Options put to Gary (stand-in drape falls / painted flat only / investigate);
   he dismissed the question for now. **Waiting.**
6. **Camera snap when the camera moves to the rising hangar rig** ("like a switch between two non-identically
   calibrated cameras"). The cat-bob pop was fixed by patch MR (cc1331e, 30 Sep). So this is something else, to be
   **measured** at the P01 crossing (height, FOV, roll, speed: Passage camera vs the Scene's Entry camera) when PIE is off.
7. **Girders visible, "nice"; might want them twice as thick and heavy later.** Noted, not actioned (BeamWidthCm 40 /
   BeamDepthCm 90 today; doubling re-hangs every TOP lamp again).
8. **"In the spaces between the girders the rig should still be lined with fencing?"** The FenceBay kit exists (W&T: open,
   tarp half/full/torn, door gap; placed in P04). The height question (ground to ~3 m / full height / options first)
   was put to Gary; he dismissed it for now. **Waiting.**
