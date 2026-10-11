# House rules (every Codex brief, 8 Oct 2026 overnight)
1. You run in a git WORKTREE. Never write the main tree E:\PussStage. Never git stash, never commit -a. Commit your work in your worktree branch with explicit paths.
2. NO Unreal editor access, NO MCP calls, NO PIE, NEVER start/stop/quit/restart the editor or Blender GUI. Offline only (Python/numpy/PIL is fine). Do not run Blender at all unless the brief says so.
3. Tools must have DRY/APPLY/REVERT modes with confirm strings, a record + Backups/Pre<Thing>-<run> BEFORE any change, an exact dirty-package census, save only named packages, read back, and a success marker with a run id — the conductor runs them later.
4. UE 5.8 traps: never delete nodes on existing materials; values read in the same call as an import/build lie; delete markers by find_marked_frame_by_label; float channel read-back tolerance ~1e-4; set_collision_profile_name("NoCollision") with set_collision_enabled; in PIE use unreal.load_asset.
5. Every tool ships with an offline harness with NEGATIVE and POSITIVE controls; report pass counts.
6. Mark every claim: declaration-proven / binary-proven / measured / inferred, with file:line. Unmarked reports are rejected.
7. Look/creative values are Gary's: put them in args with defaults; produce preview images; apply nothing.
8. Final message: what you built (paths, commit hash in your worktree), how to run it (ordered), harness results, open questions. Under 700 words.
9. NEW TRAPS (8-9 Oct, all measured live; respect them in every tool):
   - Visibility tracks: bind AActor::bHidden ("bHidden","bHidden"); the bool channel stores VISIBLE (True = shown). Tracks bound to "bHiddenInGame" are INERT on actors (MovieScenePropertyTrack.h:53-56; PIE probe PIES2VIS-185717).
   - seq.add_possessable(actor) on an actor ALREADY bound in that sequence returns the EXISTING binding; set_display_name then renames it. Look up existing bindings first and add tracks to them.
   - channel.evaluate_keys(range, rate): build the range with sequence.make_range(start, duration) (display rate). A default SequencerScriptingRange() is 60000 fps and returns ~1 value for ~2000 frames. Assert the count.
   - Channel values are float32 in practice: read back numerically (0.01 cm / 0.001 deg), never by hashing rounded values.
   - New visibility/property tracks get UE default names ("Visibility"), not your display name; match by class + property.
10. Before any `--unreal` attempt, run `python Scripts/ue58_api_preflight.py <tool-directory>` and clear every DENY finding.
