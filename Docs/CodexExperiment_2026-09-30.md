# Today as a Codex experiment

Gary, 30 September 2026: shift large amounts of actual coding work, and any
expensive work that does not need judgement, onto Codex — and treat today as an
experiment in doing so.

This document is the experiment's design, its live state, and the place its
result gets written. It is meant to be read at the end of the day and answer one
question: **what can this project safely stop paying Claude to do?**

---

## 1. The selection rule

The wrong question is "is this task hard?" Codex is capable. The right question
is **"if it is confidently wrong, how long before we find out, and what does it
cost?"**

So tasks are chosen by their **verification cost**, not their difficulty:

| Output shape | Verification | Delegate? |
| --- | --- | --- |
| A patch that must compile and pass the suite | The build and the suite say so | **Yes** |
| A finding citing `file:line` | Spot-check three citations | **Yes** |
| A script producing a number we can cross-check | Run it against a known case | **Yes** |
| A list of untested hypotheses | Each carries its own test | **Yes** |
| A judgement about how something looks | Nothing checks it | **No** |
| A Show asset or level mutation | Backup, dry run, read-back, revert | **No** |
| Anything on today's critical path | A capacity failure costs the day | **No** |

The failure mode to design against is not "Codex cannot do it". It is **Codex
producing something plausible that nobody can cheaply check** — which moves the
cost from doing to verifying and saves nothing.

## 2. What is running today

Launched about 10:20, all read-only, all printing to stdout, logs under
`Saved/CodexRuns/`.

| # | Task | Why it qualifies | How it gets judged |
| --- | --- | --- | --- |
| **A** | Audit `PussProjectTaskTracker.md` against source | Pure grep over a document already known to be stale. Nobody is blocked on it. A wrong answer costs a spot-check. | Every EXISTS must cite `file:line`. Spot-check three. Any UNCLEAR must say what was searched. |
| **B** | Landscape-hole investigation for S2/S3 | Currently blocked on nobody owning those environments. A written investigation makes the ownership decision cheap. Read-only. | Must distinguish what it read from what it inferred, and flag where UE 5.8's missing private `.cpp` makes behaviour unverifiable. |
| **D** | Adversarial review of today's commits | Machine-adjacent, and the repo took about twenty commits today from four streams. | Each finding cites `file:line` and is checkable in a minute. Praise is explicitly not the output. |
| **E** | Stutter: tested vs untested hypotheses, plus the cheapest decisive test for each | The most Claude-expensive open problem in the project, and still unsolved. Its output is a list of tests, each of which validates itself. | The report must separate "ruled out by measurement" from "not observed". If it blurs those, it is worthless and that itself is a result. |

**Deliberately NOT delegated today:** the backcloth integration (critical path,
and Rig is ready), the cloth acceptance decisions (judgement), anything that
writes to the Show asset or the level, and the lattice fade (Gary's call).

**Pending a stream's consent:** the 10 km gap in Rig's builder blocker test. It
is Rig's file, so Codex may draft it in a worktree only if Rig agrees — a stream's
files are not delegable by the conductor.

## 3. What Claude keeps doing today

Naming this matters as much as the delegation, because the saving comes from
Claude doing **less of the wrong thing**, not less work.

- **Deciding and sequencing** — who gets the editor, what reaches Gary, whether a
  result is trustworthy.
- **Judging** — every cloth verdict today turned on whether a number meant what it
  appeared to mean.
- **Talking to Gary.**
- **Anything on the critical path**, because a capacity failure there costs hours.

And the expensive Claude habits worth cutting regardless of Codex:

- Reading long logs in full when a `grep` answers the question.
- Re-verifying something a stream already verified and reported with evidence.
- Writing a long message where a short one does the same work. Several of today's
  peer messages were longer than the findings they acknowledged.

## 4. How today's result gets scored

At end of day, for each task: **did it produce something usable, and what did
verification cost?** Three outcomes, written down honestly:

- **USABLE** — the output was correct and checking it was cheap. Delegate this
  class permanently.
- **USABLE BUT EXPENSIVE** — correct, but verification cost as much as doing it.
  Delegate only when Claude is otherwise busy.
- **NOT USABLE** — wrong, or unverifiable. Record *why*, because the reason
  generalises further than the task.

Also recorded: **capacity failures**. Codex hit "selected model is at capacity"
twice on 30 Sep. Four concurrent runs is itself a test of whether that is a
throughput limit or bad luck.

## 5. Results

*To be filled in as each run lands. Nothing here yet.*

| # | Outcome | Verification cost | Note |
| --- | --- | --- | --- |
| A | **USABLE** | ~2 min, 3 spot-checks, all passed | See below. |
| B | **USABLE** | ~2 min, header checks | See below. |
| D | **USABLE — highest value of the five** | ~10 min for the P0 and my four | 21 findings, one P0 live. See below. |
| E | **USABLE — best of the five** | ~3 min, citations verified in the raw logs | See below. |


### A — task-tracker audit: USABLE

**Output:** all 28 outstanding rows, each with a verdict and, for EXISTS or
PARTIAL, an exact `file:line`. Full report:
`Saved/CodexRuns/last-message-20260930-100735.txt`.

**Verification:** three citations spot-checked, all correct.
- `InfinityStage.uplugin:4` → `0.15.0-container-look`. **The row asking to load
  `0.6.0-wing-modulation` is stale by nine minor versions.**
- `SInfinityStageCueDesk.cpp:5563` → `It->Transport->bPerformanceMode =
  !bRehearsalTransport;`, verbatim.
- MIDI ABSENT → the only hits repo-wide are `.pdb` and `.obj` build artifacts.
  **Right, and right for the stated reason**: it scoped itself to non-generated
  text source and said so at the top. A naive grep gets this wrong.

**Why it qualifies as usable, beyond being correct:** it kept "source proves
implementation" separate from "source cannot prove live acceptance", on every row,
without being asked twice. Fourteen rows came back UNCLEAR, each naming exactly
what was searched — which is the honest answer for saved Show state, visual
acceptance and audio approval, none of which live in source. **An agent that
returned 28 confident verdicts would have been useless.**

**Three genuine ABSENTs worth someone's attention**, each from an exhaustive
scoped search: the MIDI review/import layer, spline/route visualization with
clearance validation, and artist-authored groups plus the Operator workspace.

**The generalisable lesson:** this task was delegable because its output is
*citations*. Checking three of them took two minutes and covers the method, not
just those three rows. Any task whose output can be spot-checked this way is
safe to hand over.

### E — the stutter: USABLE, and it corrected our own records

Report: `Saved/CodexRuns/last-message-20260930-100748.txt`.

**It defined its evidence terms before using them** — ruled out by intervention,
confirmed contributor not root, **not observed**, insufficiently documented — and
then applied them strictly enough to disagree with the handover.

**Two corrections, both verified in the raw logs:**

1. **"All eight timers ruled out" was wrong.** The `ListTimers` census logs
   `------- 1 Active Timers -------` and `1 Total Timers`: a single 0.1 s
   GameState timer, with no disable A/B. Corrected in the handover.
2. **"No other process bursts" cannot mean what we took it to mean.** Every
   process was sampled at **250 ms**; the spikes are **40–100 ms**. The method
   cannot see a burst that starts and ends inside one sample. It rules out a
   sustained competing load and nothing more. **We spent days treating a
   methodologically blind result as an exclusion.**

It also demoted fog, the Go1 socket and the AI recorder from "ruled out" to
**provisionally excluded**, because no surviving raw A/B says how each was
disabled or reports a before/after rate — which is fair, and checkable.

**Then it ranked 19 untested hypotheses by likelihood over test cost**, each with
a confirm/refute criterion and a common baseline: A/B/A, 60 s, camera parked, PIE
off, **count cluster starts rather than slow frames**, and require a 90% reduction
twice with the reversal restoring them. Top of its list is the one thing we
deferred: **re-record under Ultimate Performance while the machine is idle**,
then a WPR trace with context switches, DPC/ISR and hard faults — which is
precisely the instrument that would see the burst the 250 ms sampling could not.

**Verification cost: three minutes**, because every claim carried a log line and
the two that mattered were checkable by reading them.

**This is the strongest argument for delegation in the whole experiment.** The
task was expensive, open-ended and had defeated four streams over several days —
and the useful output was not a solution but *an audit of our own certainty*,
which is exactly the kind of work that needs fresh eyes and no memory of having
been confident.

### B — landscape holes: USABLE, and it changes what the job IS

Report: `Saved/CodexRuns/last-message-20260930-100735.txt`.

**The decision-relevant finding: this cannot be scripted from stock Unreal
Python.** `FLandscapeEditDataInterface::SetAlphaData` and `ALandscape::CreateLayer`
are both plain `LANDSCAPE_API` with **no `UFUNCTION` macro**, verified in the
headers. So the S2/S3 landscape holes are an **editor-mode manual job or a C++
helper**, not a script — which is a different task, with a different owner, from
the one we had been discussing.

Also useful: **component deletion is far too coarse** — the components are
63–67 m wide, against a hangar footprint. And **eight skeletal actors are standing
on landscapes at P3**, which is the site where a bad edit is most visible.

**It stated its own source limitation before using it**, unprompted: the
Landscape, LandscapeEditor and LandscapePatch trees have headers and zero `.cpp`,
so API existence and shader maths are source-proven while editor stroke
behaviour, undo, and which packages get dirtied are not. It then marked which of
its own claims fell on which side of that line, and flagged that its Python
spellings were derived from reflected declarations and never executed.

**Verification cost: two minutes**, two header greps and a `find`.

**The pattern across A, B and E:** all three were usable because each drew a line
between what it could prove and what it could not, and put the line where a
reader could check it. That is the property to select for.

### D — adversarial review of the day's commits: the highest-value run

Report: `Saved/CodexRuns/last-message-20260930-100748.txt`. **21 findings with
line citations, across ~50 commits, and it named the 32 commits it found nothing
in** — which is what makes the 21 mean something.

**One P0, live, and it would have fired at 15:30.** The new human pile-approval
gate did not gate: `verdict["pile"] = None`, and `ALL` was computed as *nothing
is `False`* — so `None` passed, and the importer proceeds on `ALL`. **A bake
would have imported without Gary's approval**, on the one criterion we had just
proved was measuring noise. Verified in the code, fixed and tested the same hour:
pending now FAILS, missing metrics are reported rather than skipped.

**Four findings were the conductor's own**, and each was a claim I had made
confidently:
- `.codex/config.toml`, holding the port fix I was pleased to have found, **was
  gitignored** — so a fresh checkout never received the fix my own documentation
  said was in the repo.
- My stdin fix closed stdin **only on the default path**, leaving `--review` and
  `--raw` hanging exactly as that commit's message described.
- The handover still said **"nothing is placed"** after `final11` went in, and
  still listed three stutter hypotheses as ruled out after I had demoted them
  elsewhere.
- I had written that the backcloth's timing chain was **immutable**. It was not —
  the cache filename selects a mutable bake JSON. Now bound by SHA-256.

**The recurring class, worth more than any single finding: scripts that compute
the critical value and never assert it**, or emit a success marker regardless of
whether restoration failed. At least six findings are that shape. Work that looks
verified because a number was printed next to it.

**Verification cost: about ten minutes** for the P0 and my four. The rest went to
their owners with citations attached.

**This is the run that changes what I would delegate.** A, B and E were research.
D was *review of our own work by something with no memory of having done it* —
and it found, in one pass, faults that four careful streams had walked past all
day. That is the highest-leverage use of a second agent in this project.