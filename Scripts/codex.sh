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
#   Scripts/codex.sh --review                   # code review of the current diff
#
# Read-only is the default deliberately: Claude streams are doing guarded,
# backed-up work in this repo, and an unsupervised agent editing the same files
# is how two careful processes produce one broken tree.
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
case "${1:-}" in
  --write)    SANDBOX="workspace-write"; shift ;;
  --worktree) SANDBOX="workspace-write"; MODE="--worktree"; shift ;;
  --review)   shift; exec "$EXE" exec review -C "$REPO" "$@" ;;
  --raw)      shift; exec "$EXE" "$@" ;;
esac

if [ $# -eq 0 ]; then
  echo "usage: Scripts/codex.sh [--write|--worktree|--review|--raw] \"prompt\"" >&2
  exit 2
fi

echo "codex $( "$EXE" --version 2>/dev/null )  |  sandbox=$SANDBOX  |  cwd=$REPO" >&2
exec "$EXE" exec -C "$REPO" -s "$SANDBOX" ${MODE:+$MODE} "$@"
