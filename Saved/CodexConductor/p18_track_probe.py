import unreal
seq = unreal.load_asset("/Game/InfinityStage/Dev/Sequences/LS_DevScene_01")
out = []
for b in seq.get_bindings():
    g = b.get_id().export_text()
    if g not in ("AEA1E44F405DFF48BF8BE1ADA5D7656B", "3FB7BB1849CFDB5B4E3CCB94EB3E417D"): continue
    for t in b.get_tracks():
        dn = None
        try: dn = str(t.get_editor_property("display_name"))
        except Exception as e: dn = "ERR %s" % e
        out.append((g[:6], str(t.get_name()), str(t.get_display_name()), dn, str(t.get_property_name()) if isinstance(t, unreal.MovieScenePropertyTrack) else "-", [(s.get_start_frame(), s.get_end_frame(), str(s.get_completion_mode())) for s in t.get_sections()]))
lib = unreal.EditorLoadingAndSavingUtils
unreal.log("P18PROBE_OK|%s|dirty=%s" % (out, [p.get_name() for p in lib.get_dirty_content_packages()] + [p.get_name() for p in lib.get_dirty_map_packages()]))
