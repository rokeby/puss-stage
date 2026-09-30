"""READ-ONLY (30 Sep, Look & camera's question): each Scene cue's Entry/Exit handoff hold and its sequence's rates.
Scene 1's rematch put the Exit at 375 of 5270 (25 fps): the builder's ExitStart = SceneEnd - hold implies a 195.8 s hold.
Logs PUSS_SOFTGOODS_HOLDS|... Nothing is modified. Crash rules: everything inside main()."""
import unreal


def main():
    show = unreal.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
    t = show.get_editor_property("tick_resolution")
    rows = [f"show_ticks={t.numerator}/{t.denominator}"]
    for c in show.get_editor_property("cues"):
        if str(c.get_editor_property("type")) != str(unreal.InfinityCueType.SCENE):
            continue
        sc = c.get_editor_property("scene")
        seq = sc.get_editor_property("sequence")
        vals = {}
        for k in ("entry_handoff_hold_frames", "exit_handoff_hold_frames"):
            try:
                vals[k] = sc.get_editor_property(k).value
            except Exception as e:  # noqa: BLE001
                vals[k] = f"n/a ({e})"
        tr = seq.get_tick_resolution() if seq else None
        dr = seq.get_display_rate() if seq else None
        rows.append(f"{c.get_editor_property('label')}: {vals} seq_ticks={tr.numerator if tr else None} "
                    f"display={dr.numerator if dr else None}/{dr.denominator if dr else None}")
    del show
    unreal.log("PUSS_SOFTGOODS_HOLDS|" + " || ".join(rows))


main()
