def main():
    import unreal, json
    seq = unreal.load_asset("/Game/InfinityStage/Dev/Sequences/LS_DevScene_03")
    out = []
    for b in seq.get_bindings():
        for t in b.get_tracks():
            if str(t.get_display_name()) == "S3.Flame":
                p = b.get_parent()
                out.append([str(b.get_display_name()), str(p.get_display_name()) if p is not None and p.is_valid() else None])
    unreal.log("PROBE_FLAME_OK|" + json.dumps(out))
main()
