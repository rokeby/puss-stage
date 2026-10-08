"""READ-ONLY: every Intensity key in LS_S3_HangarRise and LS_DevScene_03, grouped by owning actor label.
Writes probe_s3_light_keys.json; marker PROBE_S3_LIGHT_KEYS_OK|run=.. / PROBE_S3_LIGHT_KEYS_FAILED. No modify, no save."""
import json
import time

OUT = "E:/PussStage/Saved/CodexConductor/probe_s3_light_keys.json"
SEQS = ["/Game/InfinityStage/RigAtmos/LS_S3_HangarRise", "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"]


def main():
    import unreal
    run = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    lib = unreal.EditorLoadingAndSavingUtils
    c0 = (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    out = {}
    for sp in SEQS:
        seq = unreal.load_asset(sp)
        rows = []
        for b in seq.get_bindings():
            par = b.get_parent()
            owner = str(par.get_display_name()) if par and par.is_valid() else ""
            for t in b.get_tracks():
                if "ntensity" not in str(t.get_display_name()):
                    continue
                for s in t.get_sections():
                    rng = [s.get_start_frame() if s.has_start_frame() else None, s.get_end_frame() if s.has_end_frame() else None]
                    for ch in s.get_all_channels():
                        keys = [(k.get_time().frame_number.value, round(k.get_value(), 3)) for k in ch.get_keys()]
                        dflt = None
                        try:
                            dflt = ch.get_default() if ch.has_default() else None
                        except Exception:
                            pass
                        rows.append({"owner": owner, "binding": str(b.get_display_name()), "range": rng,
                                     "n": len(keys), "first": keys[:3], "last": keys[-3:], "default": dflt})
        out[sp] = rows
    c1 = (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    json.dump({"run": run, "seqs": out, "census_before": c0, "census_after": c1}, open(OUT, "w"), indent=1)
    unreal.log("PROBE_S3_LIGHT_KEYS_OK|run=%s|%s|census_unchanged=%s" % (run, {k: len(v) for k, v in out.items()}, c0 == c1))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("PROBE_S3_LIGHT_KEYS_FAILED|%r" % (exc,))
