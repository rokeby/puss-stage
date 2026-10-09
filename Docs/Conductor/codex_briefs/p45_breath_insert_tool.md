# P45 — `breath_insert.py`: authored breath, insert N s inside a Passage (Codex, offline build)

Read `_house_rules.md` first; every rule applies (worktree; NO Unreal, MCP, PIE or Blender; DRY/APPLY/REVERT with
confirm strings; record + Backups/Pre<Thing>-<run> before any change; exact census; save only named packages;
read back; success marker with run id; harness with -/+ controls; proof tiers with file:line; final message
< 700 words).

## Context
- Gary 9 Oct: the breath is AUTHORED, placed during rehearsal. Puss stops and looks around. Wings, squeaks and
  time-driven flicker keep running. The music truly pauses (tape-stop, silence, resume), and the show gets longer
  by D from that point.
- The design is already done: `Docs/Conductor/P36_BREATH_INSERT_TIME_REPORT.md`, especially "Recommended future
  Unreal tool: breath_insert.py" (Args / DRY / APPLY / REVERT) and the holder table above it. Build exactly that
  design.
- The audio side exists: `Tools/Breath/breath_audio.py` (its APPLY record supplies the exact delta).

## Build
`Saved/CodexConductor/BreathInsert_20261009/breath_insert.py`, plus args, request, runner and README, using the
project-Python MCP route conventions of the existing tools:
- `Saved/CodexConductor/I2SleightMoveIn_20261009/i2_sleight_move_in.py` is a recent, reviewed example of a
  sequence-key tool with a fake-Unreal harness;
- `Saved/CodexConductor/P01FloorPracticals_20261008/p01_floor.py` is an example of Show-row writes with
  materialize and narrow saves.

Requirements:
- **Pure planning, no `unreal`.** Given a snapshot (compiled Passage spans and pins, all 13 Passage channels' keys,
  root/binding tracks and cuts, Master markers, changed-Choreo contents, explicit mechanism origins, managed music
  sections, GO/At rows) plus F and D, it produces the exact edit list. Refusals:
  - any holder it cannot classify;
  - straddling sub-sections;
  - overlap with an existing breath;
  - D not equal to the audio record's delta in Show ticks.
- **Breath camera keys.** SpeedMultiplier 1→0 at F, 0 through F+D, back to 1, with ease frames. Yaw/Pitch look keys
  come from args (Gary's values, defaults 0). The bounding pins are the Wing cues before and after F, as the report
  recommends.
- **Live backend:** the editor calls, but only behind an injectable backend so the harness can run them on a fake.
- **Harness:**
  - negative controls: PIE running, dirty census, F outside the Passage, D mismatch, straddling section, existing
    breath, unknown holder, locked marker, wrong confirm;
  - positive: DRY → APPLY → REVERT round trip on a fake Master, with exact key read-back (float32 tolerance) and the
    later-Passage carry left to the rebuild (do NOT double-shift; patch-K behaviour is in source per the P36 report);
  - one end-to-end synthetic case: a breath at 40 % of a 90 s Passage, D = 6 s.
- **README:** the run order for a rehearsal slot, plus what Gary/Klara choose (music track, F, D, W, look shape).

Not run live. Report pass counts.
