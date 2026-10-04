"""Read-only: the Opening cue's type, sequence and ExternalSound."""


def run():
    import unreal
    show = unreal.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
    for cue in show.get_editor_property("cues"):
        if str(cue.get_editor_property("type")) == str(unreal.InfinityCueType.WING_PAIR):
            continue
        scene = cue.get_editor_property("scene")
        seq = scene.get_editor_property("sequence")
        unreal.log("CUEING_SEGMENT|label=%s|type=%s|sequence=%s|external=%s" % (
            cue.get_editor_property("label"), cue.get_editor_property("type"),
            seq.get_name() if seq else None, scene.get_editor_property("external_sound")))


run()
