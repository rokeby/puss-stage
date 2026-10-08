# P21c: S3 crowd: work WITH the five originals' existing Transform tracks (teleport keys)
Live DRY P21B-DRY-20261008-2 (8 Oct, conductor) [measured]:
- actors_found=5, duplicates=15, clusters=3, live_cut_layout=OK, baseline_gate=OK, writes=0;
- existing_transform_tracks = all five (Shore01_M56, Shore02_F52, Shore03_M59, Shore04_F55, Shore06_F25), so APPLY
  raises EXISTING_ACTOR_TRANSFORM_TRACKS_REQUIRE_REPLAN (Saved/CodexConductor/s3_crowd_structure.py:620).
Those tracks hold Gary's figure placement + the TELEPORT at LS_Clams 1461/1462 (Scene = LS_Clams - 22; Gary: "the point is
to teleport them when camera's distracted"); read their keys live in DRY and report them.
Job (offline; the conductor runs it):
1. NEVER delete or overwrite the existing keys. Cluster A = the five originals WHERE THE SEQUENCE PUTS THEM: evaluate
   their keyed positions in each crowd window (establishing 360-552, frenzy, choir 2828+) and build cluster A around
   those positions. The copies in clusters B and C get their own fresh Transform tracks.
2. The coherence sway on the originals goes in as a NEW ADDITIVE section on their existing Transform track (blend type
   ADDITIVE, roll only, as s3_handheld.py did on B06), so the absolute keys are untouched.
   - Verify the 5.8 Python API for additive sections live (get_blend_type returns an enum; s3_handheld detection uses
     the "ADDITIVE" substring).
   - REVERT removes only our additive sections.
3. If a cluster-A figure's keyed path crosses a camera path, or it teleports INSIDE a crowd window, report it in DRY.
4. Replace the line-620 refusal with: refuse only if an existing transform track has keys INSIDE our crowd windows that
   our additive sway would fight (report frame ranges), or carries an additive section we didn't create.
5. Update the harness (-/+ controls) and the report. Keep every 5.8 fix already in the file (TimeWarpVariant play rate,
   Weight_0 crossfades, transport clock, presence census, root-frame cuts).
Deliver Docs/Conductor/P21C_CROWD_TRANSFORMS_2026-10-08.md.
