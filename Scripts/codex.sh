#!/usr/bin/env bash
# Run a Codex agent against E:\PussStage.
#
# Codex is installed but NOT on PATH, and its binary lives in a hash-named
# directory that changes on update -- so this discovers the newest one rather
# than hardcoding a path.
#
#   Scripts/codex.sh "your prompt"              # READ-ONLY (default, safe)
#   Scripts/codex.sh --write "your prompt"      # may edit the working tree
#   Scripts/codex.sh --worktree "your prompt"   # writes, but in its own git worktree
#   Scripts/codex.sh --unreal "your prompt"     # may reach the Unreal MCP at 8010
#   Scripts/codex.sh --review                   # code review of the current diff
#   Scripts/codex.sh --raw <anything>           # pass straight through to codex
#
# Read-only is the default deliberately: Claude streams are doing guarded,
# backed-up work in this repo, and an unsupervised agent editing the same files
# is how two careful processes produce one broken tree.
#
# Every run writes the agent's final message to a file and prints the path, so
# a long run can be read while it is still going. Do NOT pipe this through
# `tail` or `head`: Codex's stdout buffers and the run then looks hung.
#
# See Docs/CodexDelegationPlan_2026-09-30.md for what to delegate and what not.
set -euo pipefail

BASE="/c/Users/Administrator/AppData/Local/OpenAI/Codex/bin"
EXE="$(ls -1dt "$BASE"/*/codex.exe 2>/dev/null | head -1 || true)"
if [ -z "$EXE" ]; then
  echo "codex.exe not found under $BASE" >&2
  echo "Codex may have been updated or moved. Search with:" >&2
  echo "  powershell -c \"Get-ChildItem \$env:LOCALAPPDATA\OpenAI\Codex -Recurse -Filter codex.exe\"" >&2
  exit 1
fi

REPO="E:\PussStage"
SANDBOX="read-only"
MODE=""
EXTRA=()

case "${1:-}" in
  --write)    SANDBOX="workspace-write"; shift ;;
  --worktree) SANDBOX="workspace-write"; MODE="--worktree"; shift ;;
  --unreal)
    # Two things are needed to reach the editor, and both are non-obvious.
    #
    # 1. NETWORK. The workspace-write sandbox blocks network by default, and the
    #    MCP endpoint is loopback HTTP. Without this, a working server looks dead.
    # 2. APPROVAL. `codex exec` is non-interactive, so its approval policy is
    #    `never` and a native MCP call is refused with
    #    "MCP tool call requires approval, but approval policy is never".
    #    --approve-for-me routes approvals through automatic review. It CANNOT be
    #    combined with -s, hence the unset below.
    #
    # Both routes to Unreal are proven working (30 Sep 2026): the native MCP
    # client, and `python Saved/CodexMocap/mcp_request.py`, which is the path every
    # Claude stream uses and which leaves a request JSON on disk for review.
    # Prefer the shell route for anything you may need to audit afterwards.
    SANDBOX=""
    EXTRA+=(--approve-for-me -c sandbox_workspace_write.network_access=true)
    shift ;;
  --review)   shift; exec "$EXE" exec review -C "$REPO" "$@" ;;
  --raw)      shift; exec "$EXE" "$@" ;;
esac

if [ $# -eq 0 ]; then
  echo "usage: Scripts/codex.sh [--write|--worktree|--unreal|--review|--raw] \"prompt\"" >&2
  exit 2
fi

STAMP="$(date +%Y%m%d-%H%M%S)"
OUTDIR="Saved/CodexRuns"
mkdir -p "$OUTDIR"
LAST="$OUTDIR/last-message-$STAMP.txt"

echo "codex $( "$EXE" --version 2>/dev/null )  |  sandbox=${SANDBOX:-approve-for-me}  |  cwd=$REPO" >&2
echo "final message -> $LAST" >&2

exec "$EXE" exec -C "$REPO" ${SANDBOX:+-s "$SANDBOX"} ${MODE:+$MODE} \
  "${EXTRA[@]+"${EXTRA[@]}"}" -o "$LAST" "$@"
