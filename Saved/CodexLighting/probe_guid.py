import unreal
out = {}
g = unreal.GuidLibrary.new_guid()
for how, fn in [("kwargs", lambda: unreal.InfinityCueAttachment(attachment_guid=g)),
                ("positional", lambda: unreal.InfinityCueAttachment(g)),
                ("set_editor_properties", lambda: (lambda a: (a.set_editor_properties({"attachment_guid": g}), a)[1])(unreal.InfinityCueAttachment()))]:
    try:
        a = fn(); out[how] = str(a.get_editor_property("attachment_guid")) == str(g)
    except Exception as exc:
        out[how] = f"ERR {type(exc).__name__}: {str(exc)[:120]}"
unreal.log("PUSS_GUID_PROBE|" + str(out))
