import unreal
out = []
try:
    seq = unreal.load_asset("/Game/Scenes/LS_Clams")
    for b in seq.get_bindings():
        for t in b.get_tracks():
            if t.get_class().get_name() == "MovieSceneSkeletalAnimationTrack":
                s = t.get_sections()[0]
                p = s.get_editor_property("params")
                pr = p.get_editor_property("play_rate")
                info = {"binding": str(b.get_display_name()), "type": type(pr).__name__,
                        "methods": [m for m in dir(pr) if not m.startswith("_")][:50], "str": str(pr)[:200]}
                for m in ("get_constant", "to_fixed_play_rate", "get_fixed_play_rate", "export_text"):
                    if hasattr(pr, m):
                        try: info[m] = str(getattr(pr, m)())[:200]
                        except Exception as e: info[m] = "ERR %r" % e
                out.append(info)
                break
        if out: break
except Exception as e:
    out.append("ERR %r" % e)
unreal.log("PROBE_PLAYRATE|%s" % out)
