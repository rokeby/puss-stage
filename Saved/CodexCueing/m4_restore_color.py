"""Puts House L's Show Color back to White in memory (M4 revert failed), verifies the
Lighting text equals the pre-probe text, and reports dirty packages. Saves nothing."""
ATTACHMENT_GUID = "24F0FC454E591513FB387DBE58E881DC"
BEFORE_COLOR = (1.0, 1.0, 1.0, 1.0)


def run():
    import unreal
    show = unreal.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
    cues = show.get_editor_property("cues")
    hit = None
    for ci in range(len(cues)):
        cue = cues[ci]
        wing = cue.get_editor_property("wing_pair")
        attachments = wing.get_editor_property("attachments")
        for ai in range(len(attachments)):
            att = attachments[ai]
            if unreal.GuidLibrary.conv_guid_to_string(att.get_editor_property("attachment_guid")).upper().replace("-", "") != ATTACHMENT_GUID:
                continue
            lighting = att.get_editor_property("lighting")
            lighting.set_editor_property("color", unreal.LinearColor(*BEFORE_COLOR))
            att.set_editor_property("lighting", lighting)
            attachments[ai] = att
            wing.set_editor_property("attachments", attachments)
            cue.set_editor_property("wing_pair", wing)
            cues[ci] = cue
            hit = (ci, ai)
    if hit is None:
        raise RuntimeError("attachment not found")
    show.modify()
    show.set_editor_property("cues", cues)
    lighting = show.get_editor_property("cues")[hit[0]].get_editor_property("wing_pair").get_editor_property("attachments")[hit[1]].get_editor_property("lighting")
    text = lighting.export_text()
    ok = "Color=(R=1.000000,G=1.000000,B=1.000000,A=1.000000)" in text and "Intensity=1740.000000" in text
    content = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    maps = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    unreal.log("M4_RESTORE|ok=%s|lighting=%s|dirty_content=%s|dirty_maps=%s" % (ok, text[:160], content, maps))
    if not ok:
        raise RuntimeError("restore did not take")


run()
