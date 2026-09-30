# Moving work to Codex — the plan

Written 30 September 2026, after Gary asked for much more work to go to Codex,
including direct file editing and driving Unreal over MCP, because Claude usage
is tight.

Everything below marked **PROVEN** was executed today and its result read back.
Everything marked **UNTESTED** is a proposal. Do not treat the two the same.

---

## 1. The headline: the Unreal route already works, and it is not native MCP

**PROVEN today.** A Codex agent reached PussStage's Unreal editor and listed its
full toolset, using the same transport every Claude stream uses:

```bash
Scripts/codex.sh --unreal "…run: python Saved/CodexMocap/mcp_request.py tools/list…"
```

`--unreal` is new, added today, and it exists because two settings are needed and
both are non-obvious:

- **`network_access=true`.** Codex's `workspace-write` sandbox blocks network by
  default, and the MCP endpoint is loopback HTTP. Without this the call fails and
  the failure looks like a dead server.
- **`-o <file>`.** See §5 — piping Codex's stdout through `tail` buffers
  everything until exit, so a long run looks hung.

### Why NOT the native MCP client

**PROVEN today:** Codex sees the server (`unreal_mcp`, exposing `call_tool`,
`describe_toolset`, `list_toolsets`) and then refuses to call it:

```
MCP tool call requires approval, but approval policy is never
```

`codex exec` is non-interactive, so its approval policy defaults to `never` and
there is nobody to approve. **Gary has reached Puss MCP from Codex before — in an
interactive session, where he could approve the call himself.** That is the
difference, and it is worth writing down because the natural conclusion from the
error is "the MCP is broken", which it is not. `--approve-for-me` exists and
**PROVEN: `--approve-for-me` clears it.** It sets approval to `on-request` and
routes each request through automatic review, and the call then reaches Unreal —
`mcp: unreal-mcp/list_toolsets (completed)`, returning the real toolset list.
**It cannot be combined with `-s`**, which the CLI rejects outright, so the new
`--unreal` mode passes `--approve-for-me` instead of a sandbox flag.

**So both routes work. Prefer the shell route** for anything that may need
auditing afterwards, because:

- it is **the same path the Claude streams use**, so behaviour is identical and
  one fix serves everyone;
- every call is a **request JSON on disk** under `Saved/Codex*/`, so what an agent
  did to the editor is reviewable and revertable after the fact;
- the project's guarded tool (`ExecuteProjectPythonFile`, restricted to `Saved/`)
  is reached the same way regardless.

---

## 2. What to give Codex, in order of how safe it is

### Tier A — read-only analysis. Start here, no approval needed.

Failure costs nothing and the output is a report. This is where Codex has
already been useful.

- Source audits: "does X exist in the plugin, and where"
- Cross-checking a document's claims against code (the project's standing rule is
  *grep before implementing anything a document says is missing*)
- Reading logs and summarising failures
- Diff review of an uncommitted change (`--review`)
- Answering "which stream owns this file"

```bash
Scripts/codex.sh "…PRINT your findings as your final message…" > out.log
```

**A read-only agent cannot write its own report** — it stops and asks for write
access. Have it print, and capture stdout.

### Tier B — file edits in an isolated worktree. Safe by construction.

`--worktree` gives Codex its own git worktree, so nothing it does can collide
with a stream mid-task. This is the right default for any real editing job.

- Writing new standalone scripts under `Saved/Codex*/`
- Mechanical refactors with a test to prove them
- Documentation written from source
- Drafting a C++ patch **as a patch file** (see the held-patch rule below)

Review the worktree's diff before merging anything. The agent's own claim that
it worked is not evidence.

### Tier C — direct edits to the working tree. Needs a named owner and a reason.

`--write` edits the shared tree. **The tree is shared across every stream, and a
build compiles whatever is on disk**, so an uncommitted edit is not "held" — it
ships in whoever builds next, under their name.

Only use `--write` when:
1. the files belong to no active stream, or their stream has agreed; and
2. the change is committed or reverted in the same sitting.

Otherwise use `--worktree`.

### Tier D — driving Unreal. Read-only first, and never unsupervised.

The editor is **exclusive**: one process authoring at a time. A Codex agent needs
the slot like everyone else, and the conductor allocates it.

- **Read-only inspection** (world state, actor properties, sequence contents):
  suitable for Codex now, via the shell route, with the script restricted to
  `Saved/` and asserting the expected world before it does anything.
- **Mutations** (Show asset, level, sequences): **not delegated to Codex.** These
  need a backup, a dry run, an external record, a named revert and a read-back,
  and they are the one class where a confident wrong answer is expensive and slow
  to detect. They also frequently need Gary.

---

## 3. The safety protocol, unchanged for any agent

These are the project's existing rules. They are not new for Codex; they are the
reason `Scripts/codex.sh` defaults to read-only.

- **Never commit another stream's files.**
- **Back up before mutating** the Show asset, the level, or C++, to
  `Backups/Pre<Thing>-YYYYMMDD-HHMM`. Git does not cover the Show asset or the
  level.
- **Never Save All.** Save only the affected asset and level.
- **Hold C++ as a patch file** in `Scripts/patches/`, working copy restored to
  HEAD, and verify the patch re-applies. Never leave a "held" edit on disk.
- **The build gate is machine-wide.** Any open UE editor in any project blocks
  any build. Negotiate the window; do not just call the build.
- **Assert the expected world** before any script touches the editor. Two
  projects serve MCP on this machine: PussStage 8010, MHFat 8000.
- **Verify by read-back, not by exit code.** For a build, check the new code's own
  UTF-16 marker in the DLL. For an edit, read the saved state back.
- `--dangerously-bypass-approvals-and-sandbox` exists. **It is not used here.**

---

## 4. What stays with Claude

Not out of preference — these are the things where Codex's known failure modes
are expensive.

- **Anything on the critical path.** Codex hit "selected model is at capacity"
  twice on 30 Sep, once mid-way through drafting C++ from a settled design. A
  stream then wrote it by hand. Use Codex where a failure means "redo it", never
  where it means "the morning is gone".
- **Show asset and level mutations**, for the reasons in Tier D.
- **Decisions and sequencing** — who gets the editor, what goes to Gary, whether
  a result is trustworthy.
- **Anything a stream owns and is mid-task on.**

---

## 5. Operating notes, learned today

- **Never pipe a Codex run through `tail` or `head`.** stdout buffers and the run
  looks hung until it exits. Use `-o <file>` for the final message and `--json`
  for the event stream.
- **`--approve-for-me` cannot be combined with `-s`.** The CLI rejects it.
- **Model and effort come from `~/.codex/config.toml`** (`gpt-5.6-sol`, reasoning
  effort high). `-m` overrides per run, which is the lever when a model is at
  capacity.
- **`resume` and `fork`** exist on `codex exec` — a long investigation can be
  continued rather than restarted.
- **`--output-schema <FILE>`** forces the final message into a JSON shape. Worth
  using for anything whose result gets parsed rather than read.
- **Console mojibake** (`—` as `鈥?`) is the Windows console reading UTF-8 as
  CP936. The model reads files correctly; only the echo is affected. `chcp 65001`
  first if it matters.
- **`AGENTS.md` is picked up automatically** — Codex's own convention, and this
  repo already had one, so a Codex agent gets the same briefing every Claude
  stream does.

---

## 6. Concrete first batch

Ordered so the first failures cost nothing.

1. **Audit `Docs/PussProjectTaskTracker.md` against source.** Its rows are known
   to describe features that already exist. Read-only, high value, pure grep
   work, and nobody is blocked on it.
2. **Read-only Unreal inventory.** Via the proven shell route: list what is
   actually in the level against what the documents claim. This exercises the
   Unreal path on something that cannot break.
3. **Write the S2/S3 landscape-hole investigation** — what the mechanism is, what
   it would touch, what it risks. Read-only. It is currently blocked on nobody
   owning those environments, and a written investigation makes the ownership
   decision cheap.
4. **Draft the acceptance-test addition for hung width against track width** as a
   patch in a worktree. Soft goods reviews before it goes near the tree.
5. **`--review` the day's commits.** Free, and it is the use Codex is built for.
