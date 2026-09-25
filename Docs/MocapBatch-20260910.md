# Mocap batch — 10 September 2026

**Status:** Queue finished.

Updated: 2026-09-11T03:19:35.712930+00:00.

Approved template: `/Game/Metahuman/Shore1`. The original short test is retained.

Output root: `/Game/Metahuman/FullTakes_20260910`.

| Take | Full video frames | State | Frames with body data |
| --- | ---: | --- | ---: |
| shoreguy1 | 2636 | verified | 2636 |
| shoreguy12 | 2639 | verified | 2639 |
| shoreguy3 | 2649 | verified | 2649 |
| shoreguy4 | 3560 | verified | 3560 |
| shoreguy5 | 2593 | verified | 2593 |
| shoreguy6 | 2743 | verified | 2743 |
| child1 | 6172 | verified | 6172 |
| child2 | 5414 | verified | 5414 |

Each take gets a full-length Performance asset in `Performances` and a raw performer-skeleton Animation Sequence in `RawAnimations`.

`verified` means the saved Performance and animation packages were reloaded from disk, the agreed solve settings matched, body-frame coverage survived reloading, all five processing stages completed, and the export has the full sample count with changing body poses.

Full-range Capture Data copies reference the same ingested images without the shorter audio tracks. The original ingests, audio, and source videos are retained.

The queue finished in the Unreal Editor and released its sleep-prevention setting and restored background CPU throttling. The final audit found no dirty content or map packages. Unreal then closed normally for the authorized [Creator setup and restart](MetaHumanCreatorRestart-20260910.md).

Backup: `E:/PussStage/Backups/PreMocapFullBatch-20260910-173855`.

Detailed status: [batch_status.json](../Saved/CodexMocap/batch_status.json). Per-take read-back reports: `Saved/CodexMocap/Verification/`.

**Final audit:** Passed.

[Final saved-state checks](../Saved/CodexMocap/batch_final_audit.json).

Rendered review of the full takes, cleanup, final MetaHuman casting and scene placement remain separate steps.
