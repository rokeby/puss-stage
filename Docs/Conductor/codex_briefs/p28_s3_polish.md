# P28: S3 polish after Gary's recording "S03 v2" (9 Oct ~02:20), one tool with independent parts
Gary's words: (1) "the Fire light asset can come on together, slightly slowly at once, so it looks more intentional and not
random spawning"; (2) "At the very last shot, when things are dark, there's a cold light behind the second bunch of waves on
the left, that can be dimmed then too"; (3) "The dunes asset may not be casting shadows so sometimes shadows are cast on the
wall of floating people"; (4) "There are new Fab Fire assets": the project now has /Game/Stylish_Fire_VFX/Niagara/
NS_Stylish_Fire_1..4 (toon-style Niagara fires); no campfire base meshes are in the project yet.
Facts:
- S3 fires: Saved/CodexConductor/s3_fires.py (CLUSTERS ignite A/B/C at 230/260/290, RAMP 24, flicker keys every 2 frames on
  track "S3.Fire.Light"; emitter visibility track hidden until ignition), then s3_fire_look.py (lights x0.67, scale 0.5, smoke
  slot 2 -> M_FX_Invisible) and s3_fire_a_off.py (Fire A hidden + its visibility sections deactivated). Records:
  s3_fires_record.json, s3_fire_look_record.json, s3_fire_a_off_record.json.
- The last S3 shot is root cut "S3 Shot B11" [5181, 6253] (Scene frames @24, probe_s3_cuts.json). Wave lights: the six
  "S3 WaveV3 Ground Row N" rect lights (9000 K, behind each wave layer, S3Waves/s3_waves_v3_core.py:544-560) + "S3 WaveV3
  Warm Side"; their intensity tracks "S3.WavesV3.Light" (s3_rect_on_at.py). "Second bunch of waves on the left" = identify
  candidates (Ground Row 2/3/4 by position; camera B11 pose from LS_DevScene_03) and report; dim via intensity keys over
  B11 only, factor in args (default 0.25), ramp 24 frames.
- The dune: tag RigAtmos.S3ShoreGround StaticMeshActor (Saved/CodexConductor/S3Shore/s3_shore_ground_ue.py; set NO_COLLISION
  at :1374-1376). Check its cast_shadow / cast_dynamic_shadow / VSM settings in the tool's DRY; APPLY turns cast shadow ON
  (record old values).
Parts (args "parts": ["fires_together","b11_dim","dune_shadow","stylish_fire"]):
1. fires_together: B and C (A is off) ignite at the SAME frame (args, default 230) with a SLOW ramp (args, default 72 frames):
   time-shift each light's flicker keys and its emitter visibility key so ignition = the common frame, multiply the first
   ramp frames by a 0->1 envelope. Record every key moved. Ghost flame untouched.
2. b11_dim: as above.
3. dune_shadow: as above.
4. stylish_fire (DRY-only by default, a look call): plan swapping each fire's P_Fire Emitter for a NiagaraActor with
   NS_Stylish_Fire_N at the same transform (keep the old emitter hidden, not deleted), report the asset parameters exposed
   (user params) so Gary can choose. APPLY only with args "stylish_apply": true.
House rules apply (rule 9 especially). LS_DevScene_03 + map saves only. Harness with +/- controls.
