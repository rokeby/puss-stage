# Job 100 ordered pipeline

The drive-curves JSON is an output, not an input that may be skipped. Run these
three stages in order:

1. With PIE stopped, Sequencer closed, and a clean editor, execute
   `sample_hands_request.json`. This is an editor-side read-only evaluation and
   must end with `S6_OLD_LADY_HAND_SAMPLE_OK`; it writes only
   `Saved/CodexConductor/S6OldLadySwarm/hand_samples.json`.
2. Outside Unreal, run:

   ```powershell
   python Tools/Mocap/s6_old_lady_swarm.py Saved/CodexConductor/S6OldLadySwarm/hand_samples.json --json DerivedAssets/S6OldLadySwarm/s6_old_lady_swarm_drive.json --png DerivedAssets/S6OldLadySwarm/s6_old_lady_swarm_curves.png
   ```

   Require `S6_SWARM_CURVES_OK` and review the PNG.
3. With PIE still stopped and the editor clean, execute
   `swarm_sequence_request.json` in DRY mode. Require
   `S6_SWARM_SEQUENCE_DRY_OK` before considering APPLY.

Offline order harness:
`python Saved/CodexConductor/S6OldLadySwarm/test_swarm_pipeline.py`.
