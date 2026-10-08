"""READ-ONLY: transform tracks on the 5 Shore hero bindings in LS_Clams AND LS_DevScene_03 / LS_S3_HangarRise (by display
name match), with section blend, range, Location.X/Y default + keys.  PROBE_HEROTR_OK / _FAILED."""
import json


def main():
    import unreal as u
    out = {}
    for path in ["/Game/Scenes/LS_Clams", "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03", "/Game/InfinityStage/RigAtmos/LS_S3_HangarRise"]:
        seq = u.load_asset(path)
        for b in seq.get_bindings():
            n = str(b.get_display_name())
            if "Shore0" not in n or "Crowd" in n: continue
            for t in b.get_tracks():
                if not isinstance(t, u.MovieScene3DTransformTrack): continue
                for s in t.get_sections():
                    bt = s.get_blend_type()
                    v = str(bt.get_editor_property("blend_type")) if bt.get_editor_property("is_valid") else "UNSET"
                    ch = {str(c.get_name()).split("_")[0]: c for c in s.get_all_channels()}
                    row = {"seq": path.split("/")[-1], "binding": n, "guid": b.get_id().export_text(), "track": str(t.get_display_name()), "blend": v,
                           "range": [int(s.get_start_frame()) if s.has_start_frame() else None, int(s.get_end_frame()) if s.has_end_frame() else None]}
                    for k in ("Location.X", "Location.Y"):
                        c = ch[k]
                        row[k] = {"default": float(c.get_default()) if c.has_default() else None, "keys": [[int(x.get_time().frame_number.value), round(float(x.get_value()), 1)] for x in c.get_keys()][:4], "n": len(c.get_keys())}
                    out.setdefault(n, []).append(row)
    json.dump(out, open("E:/PussStage/Saved/CodexConductor/probe_hero_tracks.json", "w"), indent=1)
    u.log("PROBE_HEROTR_OK|n=%d" % len(out))


try:
    main()
except Exception as exc:  # noqa: BLE001
    import unreal
    unreal.log_error("PROBE_HEROTR_FAILED|%r" % (exc,))
