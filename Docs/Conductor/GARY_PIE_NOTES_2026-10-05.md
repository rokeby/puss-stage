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
