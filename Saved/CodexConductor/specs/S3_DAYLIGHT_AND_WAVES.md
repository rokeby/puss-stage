# S3 daylight pass + wave split (Gary, 3 Oct, his own words/answers in the Conductor 4 session).
Gary: "the lighting is much too strong and white, it should feel like daylight but the marble walls should feel physical and
materially real and heavy and visible"; "as long as the waves are layered in a way that covers the horizontal, each wave doesn't
need to be the entire width"; answers: daylight pass NOW; "Split rows into overlapping pieces".
## A. S3 daylight (tool Saved/CodexConductor/s3_daylight_apply.py, DRY/APPLY/REVERT)
Read first: the S3 lights (Saved/CodexStructure/s3_strike_record.json light_specs: 6 S3 Strike lights; the S3 hangar rig; the
hangar timing strike at +10 s, built 98be9ad: keep the TIMING, change intensities only), the marble liners
(Saved/CodexConductor/s3_walls_marble.py record) and their material, the S3 exposure/PPV (s3_strike_record exposure section).
Do: cut the 6 strike lights and rig spill to ~30-50% of today; one soft DIRECTIONAL daylight key (a rect light or a large spot from
high and to one side, ~5600-6000 K) that RAKES along the marble side walls so veining/relief read; cooler, low fill from the other
side; a FIXED exposure for S3 (no auto-adapt flooding) chosen so the brightest marble sits below clipping; check the marble MI's
roughness/normal so it reads heavy (if the liner material is flat, add a normal/roughness response in a COPY MI; never edit shared
masters; never delete nodes on pre-existing assets). Light changes keyed through the existing system where keys exist (the strike
ramps): scale values, keep times. Backups, census, narrow saves, read-back, SavedMasterMatchesShow + SceneCutBindingsResolve singly,
landed STATUS. PIE stills: S3 at B02 and B03 (+2 s) and a close view of one marble wall, messages off/restored, own PIE only.
## B. Wave split (tool Saved/CodexConductor/s3_wave_split_apply.py, DRY/APPLY/REVERT)
Each of the 3 rows (6 actors `S3 Wave Row{1,2,3} {A,B}`, attached to S3 Hangar Root, transform tracks in LS_DevScene_03 from the
wave slides) becomes 2-3 pieces at ~40-60% width each, at slightly staggered depths (+/-20-40 cm) so they overlap and the horizon
stays covered across the slide travel (+/-100 cm), each with its own slide phase. Reuse the current wave meshes (new actors =
duplicates of the row actors with a scale or a cropped UV is acceptable; prefer duplicating the A/B actors and offsetting, no new
art). Preserve: the 15 s period, the vamp-loop seam (frames 3480/4200 equal), the strike-gated start. Compose against the LIVE
landed root with an inside-box guard (memory puss-level-saved-landed-frame-trap). Revert = remove the added actors and restore the
6 originals + their tracks exactly. Backups, census, narrow saves, read-back, both tests.
THIS PASS: write both tools + harnesses offline (no Unreal). Commit nothing. Final message SHORT; tags per AGENTS.md.

## Revision (Gary 3 Oct, his answers): "Real beach + marble fix"; wave split "Yes"
Stills S3Daylight/20261003_221136: B02 reads as daylight; B03 is a dark brown frame (camera inside/behind something: find out);
the marble close-up is blown cream; the beach reads as dark flat discs on the herringbone parquet.
C. BEACH v2 (s3_beach_place.py v2: revert the 9 draft actors, then place): a SAND FLOOR LAYER covering the diorama area over the
   parquet: a shaped, gently undulating mesh (a few cm up to ~20 cm high, soft edges feathering to the parquet at the area edge;
   a subdivided plane deformed by noise is fine) with a sand/shingle surface material from the Megascans surfaces already in Content
   (inventory s3_beach_asset_inventory.json); Megascans rocks EMBEDDED (sunk 20-40% into the sand, scaled varied), a few seaweed
   clumps; the ring of figures standing ON the sand (their feet at the sand surface: report any feet buried or floating);
   nothing within 1.5 m of a shot camera; inside-box guard; live landed root.
D. MARBLE: the liners must read as heavy marble under the daylight: reduce their exposure by material (albedo/roughness: marble
   roughness ~0.25-0.4 with veining visible), or the key's intensity on the walls, so the brightest wall pixel is below clipping
   in PIE; a COPY MI only. Report the before/after wall luminance from a PIE still.
E. B03: diagnose the dark frame (camera inside geometry? wrong camera? a black stand-in?) and report; fix only if it's a placement
   artefact of the beach/daylight work, else report for Gary.
B. WAVE SPLIT: the APPLY failed on unsupported StaticMeshActor.is_hidden(): use the supported visibility API (e.g.
   get_editor_property('hidden') / is_hidden_ed() / root component visibility; check the 5.8 Python API) and re-run.
THIS PASS: offline code + harness only for B, C, D (no Unreal). Commit nothing.
