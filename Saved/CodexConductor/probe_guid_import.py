"""READ-ONLY: can import_text set InfinityCueAttachment.AttachmentGuid on a fresh in-memory struct? PROBE_GUIDIMPORT|.."""
import unreal
a = unreal.InfinityCueAttachment()
res = {}
for txt in ("(AttachmentGuid=8ED7907CA54D333F0D7BFDA27C421316)", "(AttachmentGuid=(A=-1898541953,B=1525431211,C=-1608819498,D=1043403542))"):
    b = unreal.InfinityCueAttachment()
    try:
        ok = b.import_text(txt)
        res[txt[:30]] = [ok, unreal.GuidLibrary.conv_guid_to_string(b.get_editor_property("attachment_guid"))]
    except Exception as e:
        res[txt[:30]] = repr(e)
res["export_sample"] = a.export_text()[:300]
unreal.log("PROBE_GUIDIMPORT|%s" % res)
