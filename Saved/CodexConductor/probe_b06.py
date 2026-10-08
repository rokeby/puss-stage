"""READ-ONLY: S3 Shot B06 transform keys (all channels, values) + its cut; Clam_with_Pearl visibility tracks in rise and scene;
B07 VampOrbit first/mid keys. Marker PROBE_B06_OK."""
import json
def main():
    import unreal
    out = {}
    for sp in ("/Game/InfinityStage/Dev/Sequences/LS_DevScene_03", "/Game/InfinityStage/RigAtmos/LS_S3_HangarRise"):
        seq = unreal.load_asset(sp)
        for b in seq.get_bindings():
            nm = str(b.get_display_name())
            if nm not in ("S3 Shot B06", "S3 Shot B07") and "Clam_with_Pearl" not in nm:
                continue
            for t in b.get_tracks():
                for s in t.get_sections():
                    for ch in s.get_all_channels():
                        try:
                            ks = [(int(k.get_time().frame_number.value), round(float(k.get_value()), 3)) for k in ch.get_keys()]
                        except Exception:
                            continue
                        dflt = None
                        try:
                            dflt = ch.get_default() if ch.has_default() else None
                        except Exception:
                            pass
                        key = "%s|%s|%s|%s" % (sp.split("/")[-1], nm, t.get_display_name(), ch.get_name())
                        out[key] = {"n": len(ks), "keys": ks if len(ks) < 8 else ks[:3] + ks[len(ks)//2:len(ks)//2+1] + ks[-3:], "default": dflt}
    unreal.log("PROBE_B06_OK|" + json.dumps(out, default=str))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("PROBE_B06_FAILED|%r" % (exc,))
