# Sound delivery list

**For:** Cameron · **Task:** D.3 / D.4 · Drafted 22 August 2026

Nine stems are missing. Lengths matter as much as mixes — see the warning at the
bottom, it is the one thing that can cost re-doing work.

## Delivered

| Stem | Length | Where |
| --- | ---: | --- |
| `Intro_WalkingMusic_1.wav` | 1:36 | `Sound/InfinityStage Passages/` |
| `WalkingMusic_2.wav` | 0:47 | " |
| `WalkingMusic_3.wav` | 0:44 | " |
| `WalkingMusic_4.wav` | 0:43 | " |
| `WalkingMusic_5_with_Tennis_Ball_Moment.wav` | 3:06 | " |
| `WalkingMusic_6_into_void.wav` | 1:51 | " |
| `Shrine_Scene.wav` | 2:30 | `Sound/Scenes/` |
| `School_Scene.wav` | 2:37 | " |
| `Mountain_Scene.wav` | 2:32 | " |
| `The_Void_Scene.wav` | 2:35 | " |

## Missing — the nine

| # | Stem | For | Suggested length | Notes |
| --- | --- | --- | --- | --- |
| 1 | Scene 1 — Animals | Scene cue 3 | ~2:30 | Matches the four delivered scene stems |
| 2 | Scene 3 — Shore of Forgetting / Clam | Scene cue 9 | ~2:30 | " |
| 3 | Opening — curtain | Cue 1 | **Gary to specify** | Proscenium reveal; drives the curtain speed |
| 4 | Interaction 1 — washing the boy | Cue 4 | **Gary to specify** | |
| 5 | Interaction 2 — turnips | Cue 7 | **Gary to specify** | |
| 6 | Interaction 3 — forgets his name | Cue 10 | **Gary to specify** | |
| 7 | Interaction 4 — gets a name | Cue 13 | **Gary to specify** | |
| 8 | Interaction 5 — becomes King | Cue 16 | **Gary to specify** | |
| 9 | Closing — sweeping up | Cue 19 | **Gary to specify** | |

The five interactions are short shadow-play scenes behind a closed curtain, built
from one shared template — so they probably want a **common musical identity**
with five variations rather than five unrelated cues. Worth deciding as a set.

## Format

- **RIFF WAV.** The analyzer reads WAV only — MP3 or FLAC are rejected outright.
- 44.1 kHz, stereo, Float32 interleaved matches what is already in the project.
- One file per cue, named for the cue, no spaces preferred.

## The length warning

**Lock stem lengths before Gary does the passage aesthetic work.**

Passage wing count is *derived from music duration* — the Show is set to
`MusicLockedDeriveCount`. Changing a rail's length after its wings are authored
re-fits the whole passage: wing spacing changes, and the timing of everything
placed along it moves with it.

So a later "I trimmed eight seconds" is not a mix note, it is a structural change
that costs a re-authoring pass. Deliver final lengths, or flag explicitly that a
stem is still provisional so nobody builds on it.

Scene stems are safer — Scenes take their length from their own sequence — but
the same logic applies once a scene is animated to the audio.

## Also useful

`Sound Effects/Theatre Winches Pulleys (placeholders)` already holds `Winch_1`–`4`.
Those are the starting point for the **wing mechanism sound set** (D.5): the
squeaks and rumbles the moving wings make. Timing is derived automatically from
each wing's mechanism data, so what's needed is a *bucket of takes*, not anything
timed to picture — variations in effort, length and character.
