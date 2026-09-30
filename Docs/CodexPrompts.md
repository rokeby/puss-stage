# Codex prompt shapes that worked

Six delegated runs on 30 September 2026, six usable results. They were not
usable because the tasks were easy — one of them overturned two of this
project's standing conclusions. They were usable because of how they were asked.

Copy these. The rule they all share is now in `AGENTS.md`, so a Codex agent
inherits it without being told; these add the task-specific half.

---

## The shape

1. **State the task's own constraint before the task.** "Do not drive the
   editor." "Change exactly one file." "Do not run any project Python that
   writes." An agent that knows the boundary works inside it; one that discovers
   it stops and asks.
2. **Say what the WRONG answer looks like**, where you know. The blocker fix said
   *deleting the size skip is wrong, it would flag the sky on every build* — an
   agent cannot infer that the sky sphere has a 4.7e7 cm extent.
3. **Point at a reference implementation in the tree.** "The 5×5 trace grid in
   `hangar_ground_survey_readonly.py`, tested this morning."
4. **Name the evidence limit.** "That engine install has headers and shaders but
   no private `.cpp`, so behaviour cannot be verified from source — say so
   wherever your answer depends on behaviour you could not read."
5. **Ask for what it found NOTHING in**, not just its hits. A review that names
   the 32 clean commits makes its 21 findings mean something.
6. **Say what the deliverable IS.** "The diff is the deliverable." "PRINT your
   findings as your final message." A read-only agent asked to write a file stops
   and asks for write access.

---

## 1. Adversarial review of the day's commits — run this before every build window

The highest-value run of the six. Found a live P0 (an acceptance gate that did
not gate), and four false claims in this project's own documentation.

> Adversarial review of the commits made today on master. Run
> `git log --since="00:00" --oneline`, then review each diff. Look for:
> correctness bugs; anything contradicting a rule in `AGENTS.md`; anything that
> would fail **silently** rather than loudly; a default or constant that still
> encodes a value from something that no longer exists; a check that verifies
> everything **except** the thing that could be wrong; a script that computes a
> critical value and never asserts it; a success marker emitted regardless of
> whether its safety condition held. Be skeptical and specific, cite
> `file:line`, and do **not** praise anything — praise is not the output. Name
> the commits you found **nothing** in, so the findings mean something. PRINT
> findings ranked most severe first. Change no files.

The last four criteria came from faults this project actually shipped. Add to
that list whenever a new class is found; it is a record of how we go wrong.

## 2. Auditing our own certainty

> Read every account of `<the open problem>` in `<docs>` and `<logs>`. Report:
> (1) every hypothesis that has been **tested**, with how it was ruled out and a
> citation; (2) every hypothesis **not** tested, including ones nobody has
> written down; (3) for each untested one, the **cheapest decisive test**, and
> what result would confirm versus refute it. Be rigorous about the difference
> between "ruled out by measurement" and "not observed" — they are not the same
> and the distinction matters more than the list. Rank the untested by likelihood
> divided by cost to test.

That last instruction is what made it valuable: it came back with two of our
"ruled out" claims demoted, one of them measured by a method that could not
have seen what it was excluding.

## 3. Auditing a document against source

> Audit `<document>` against the SOURCE. For every row it lists as outstanding,
> determine from the code whether the feature already exists. For each: the
> claim, a verdict of EXISTS / ABSENT / PARTIAL / UNCLEAR, and for EXISTS or
> PARTIAL the exact `file:line`. Do not guess. If you cannot find evidence either
> way, say UNCLEAR and state exactly what you searched for.

Fourteen honest UNCLEARs out of 28 rows. That is the right answer for saved
asset state and visual acceptance, neither of which lives in source.

## 4. An engine-API investigation

> Read-only, print only, change nothing. PROBLEM: `<the measured behaviour>`.
> QUESTION: `<what we need to know>`. Report: the relevant APIs with signatures
> and declared purpose; whether each is reachable from Python or Blueprint
> (`UFUNCTION`/`UPROPERTY`), since a script-reachable fix is far cheaper; any
> relevant cvars; and your assessment of whether `<our proposed workaround>` is
> the right fix or a band-aid with a proper API available. Search
> `D:/Unreal Engine/UE_5.8`. That install has headers and shaders but **no
> private `.cpp`**, so mark clearly which claims are declaration-proven versus
> inferred.

Twice this closed a question rather than answering it: the landscape holes
**cannot be scripted** (two calls carry no `UFUNCTION`), and **no API** completes
the GeometryCache seek-to-present chain, so the workaround is the fix.

## 5. A code change — `--worktree`, and the owner reviews the diff

> Edit exactly ONE file: `<path>`. Change nothing else. THE FAULT: `<what is
> wrong and why the obvious fix is wrong>`. THE FIX REQUIRED: `<numbered>`. The
> reference implementation is already in this repo: `<path>`. Everything else
> unchanged: `<the invariants>`. Match the file's existing comment density and
> idiom — do not add explanatory comments it would not have written itself. Read
> `<both files>` in full before editing. AS YOUR FINAL MESSAGE print (a) the
> complete unified diff, and (b) what you were unsure about and how you resolved
> it. The owner will read the diff and accept, amend or bin it, so the diff is
> the deliverable.

It passed its owner's pre-registered test **and** still had a real design flaw
that no test could see — it routed large actors to a trace, and Structures are
large, ISM-based and have no collision, so a trace cannot see them. **Delegable
with review, not unreviewed.**

---

## Running them

```bash
Scripts/codex.sh "…"                  # read-only, the default
Scripts/codex.sh --worktree "…"       # edits, isolated from the shared tree
Scripts/codex.sh --unreal "…"         # may reach the editor's MCP on 8010
```

Six ran concurrently with no capacity failure. Every run appends to
`Saved/CodexRuns/ledger.tsv` — start, mode, seconds, exit, bytes, and whether it
produced nothing — so reliability accumulates without anyone remembering to
record it.

**Never pipe a run through `tail` or `head`.** stdout buffers and the run looks
hung. Read `Saved/CodexRuns/run_*.log` while it works.
