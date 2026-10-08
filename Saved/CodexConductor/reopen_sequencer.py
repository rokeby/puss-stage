"""Re-open a Level Sequence in Sequencer (after close_sequencer.py). Args reopen_sequencer_args.json {"path": ...}. REOPEN_SEQ_OK / _FAILED."""
import json
def main():
    import unreal
    p = json.load(open("E:/PussStage/Saved/CodexConductor/reopen_sequencer_args.json"))["path"]
    seq = unreal.load_asset(p)
    ok = unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
    unreal.log("REOPEN_SEQ_OK|%s|%s" % (p, ok))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("REOPEN_SEQ_FAILED|%r" % (exc,))
