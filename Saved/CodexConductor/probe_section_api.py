import unreal
need = ["add_key","add_possessable","add_section","add_track","get_all_channels","get_bindings","get_camera_binding_id","get_display_name","get_end_frame","get_id","get_manual_ease_in","get_manual_ease_in_duration","get_manual_ease_out","get_manual_ease_out_duration","get_object_template","get_parent","get_row_index","get_sections","get_start_frame","get_tracks","is_active","remove_section","set_blend_type","set_camera_binding_id","set_display_name","set_is_active","set_manual_ease_in","set_manual_ease_in_duration","set_manual_ease_out","set_manual_ease_out_duration","set_range","set_row_index"]
seq = unreal.load_asset("/Game/Scenes/LS_Clams")
sec = trk = bnd = None
for b in seq.get_bindings():
    for t in b.get_tracks():
        if t.get_class().get_name() == "MovieSceneSkeletalAnimationTrack":
            bnd, trk, sec = b, t, t.get_sections()[0]; break
    if sec: break
objs = {"section": sec, "track": trk, "binding": bnd, "seq": seq}
res = {}
for m in need:
    res[m] = [k for k, o in objs.items() if hasattr(o, m)]
eas = sec.get_editor_property("easing")
res["easing_props"] = [x for x in dir(eas) if not x.startswith("_")][:30]
try:
    res["easing_dict"] = str(eas.to_dict())[:500]
except Exception as e:
    res["easing_dict"] = repr(e)
unreal.log("PROBE_SECAPI|%s" % res)
