"""READ-ONLY: LS_DevScene_03 'Hangar Fold' sub-section timing params + ghost keys exact. Marker PROBE_S3_FOLD_OK."""
import json
def main():
    import unreal
    seq = unreal.load_asset("/Game/InfinityStage/Dev/Sequences/LS_DevScene_03")
    out = {}
    for mt in seq.get_tracks():
        if str(mt.get_display_name()) not in ("Hangar Fold", "Shots"):
            continue
        for s in mt.get_sections():
            d = {"range": [s.get_start_frame(), s.get_end_frame()]}
            for prop in ("parameters",):
                try:
                    p = s.get_editor_property(prop)
                    d["time_scale"] = str(p.get_editor_property("time_scale"))
                    d["start_frame_offset"] = str(p.get_editor_property("start_frame_offset"))
                    d["end_frame_offset"] = str(p.get_editor_property("end_frame_offset"))
                except Exception as e:
                    d["err"] = repr(e)
            out[str(mt.get_display_name())] = d
    for b in seq.get_bindings():
        for t in b.get_tracks():
            if str(t.get_display_name()) == "S3.Opening.Ghost":
                for s in t.get_sections():
                    out["ghost"] = [(k.get_time().frame_number.value, k.get_time().sub_frame, k.get_value()) for k in s.get_all_channels()[0].get_keys()]
    unreal.log("PROBE_S3_FOLD_OK|" + json.dumps(out, default=str))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("PROBE_S3_FOLD_FAILED|%r" % (exc,))
