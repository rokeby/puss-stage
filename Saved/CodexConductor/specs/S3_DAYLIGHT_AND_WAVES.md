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
