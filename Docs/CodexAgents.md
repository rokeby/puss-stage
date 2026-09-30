# Running Codex agents in PussStage

Set up 30 September 2026. Gary has a Codex Pro subscription and the CLI is
already installed and authenticated — **nothing needed installing.** What was
missing was a way to *invoke* it, and one real bug.

## Quick use

```bash
Scripts/codex.sh "your prompt"              # READ-ONLY (default)
Scripts/codex.sh --write "your prompt"      # may edit the working tree
Scripts/codex.sh --worktree "your prompt"   # writes, but in its own git worktree
Scripts/codex.sh --review                   # code review of the current diff
Scripts/codex.sh --raw <anything>           # pass straight through to codex
```

Verified working: a read-only run read `AGENTS.md` and answered correctly.

## Why a wrapper rather than a path

**Codex is not on PATH**, in Bash or PowerShell, and its binary lives in a
**hash-named directory that changes on update**:
`%LOCALAPPDATA%\OpenAI\Codex\bin\<hash>\codex.exe` (there are already two such
directories). `Scripts/codex.sh` discovers the newest one, so an update does not
silently break every caller.

If it ever fails to find it:
```powershell
Get-ChildItem $env:LOCALAPPDATA\OpenAI\Codex -Recurse -Filter codex.exe
```

## READ-ONLY IS THE DEFAULT, DELIBERATELY

Claude streams are doing guarded, backed-up work in this repo — dry runs,
external transform records, named reverts, `git apply --check`ed patches held
out of the working tree. **An unsupervised agent editing the same files is how
two careful processes produce one broken tree.**

- `--write` opts into `workspace-write`.
- `--worktree` is better than `--write` for anything substantial: Codex works in
  its own git worktree, so nothing it does can collide with a stream mid-task.
- `--dangerously-bypass-approvals-and-sandbox` exists. Do not use it here.

## THE BUG THAT WAS FIXED

`.codex/config.toml` pointed Codex's Unreal MCP at **`127.0.0.1:8000`**.

**That is MHFat's editor. PussStage is 8010.** A Codex agent run in this folder
would have driven **the wrong project's Unreal**. It was a leftover from when
8000 was the proven address (the backups from 14–25 Sep still say so).

Now `8010`, matching `Saved/CodexMocap/mcp_request.py`, which is the route every
Claude stream uses and which has always been correct. Previous file kept as
`.codex/config.toml.bak-20260930`.

## What Codex already picks up

- **`AGENTS.md`** at the repo root — Codex's own convention, and it is already
  the project's briefing document. A Codex agent gets the same entry points,
  version-control rules and safety rules every Claude stream does.
- **`.codex/config.toml`** — the Unreal MCP server, now on the right port.

## Known cosmetic issue

Console output mojibakes em-dashes (`—` renders as `鈥?`) because the Windows
console is reading UTF-8 as CP936. **The model reads the file correctly**; only
the echoed terminal output is affected. If it becomes annoying, `chcp 65001`
before the call.

## Fitting Codex alongside the Claude streams

The standing rules apply to any agent in this repo, not just Claude ones:

- **Never commit another stream's files.**
- **Back up to `Backups/Pre<Thing>-YYYYMMDD-HHMM` before mutating Show data, the
  level, or C++.** Git does not cover the Show asset or the level.
- **Never Save All.**
- **The editor is exclusive** — one process authoring at a time. If a Codex agent
  is going to drive Unreal over MCP, it needs the slot like everyone else.
- **The build gate is machine-wide**: any open UE editor blocks any build.

## RELIABILITY, MEASURED ON 30 SEP

**Codex was not dependable on this run, and both failure modes matter.**

1. **"Selected model is at capacity."** Hit twice: once drafting the Arrival C++
   from a settled design (it read the headers and wrote nothing, and the stream
   wrote it by hand instead), once on a source audit. **So Codex is not a
   substitute for a stream on anything on the critical path.** Use it where a
   failure costs nothing and can simply be redone.
2. **A read-only agent cannot write its own report.** Asking one to "write your
   findings to <path>" under the default `read-only` sandbox makes it stop and ask
   for write access. **Have it PRINT the findings and capture stdout instead** —
   that keeps the run read-only and still gets the deliverable:

   ```bash
   Scripts/codex.sh "…PRINT your findings as your final message…" > out.log
   ```

   Only reach for `--write` or `--worktree` when the agent genuinely has to change
   the repo.

**What it did do well:** a read-only run answered a question about `AGENTS.md`
correctly and quickly, and picked up the project's briefing without being told —
because `AGENTS.md` is Codex's own convention and this repo already had one.
