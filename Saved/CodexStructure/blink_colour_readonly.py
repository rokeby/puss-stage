"""Read-only: the light colour, temperature flag and units of P01's source lamp
and of the six blink spots (the captures show every pool red). Mutates nothing."""
import json
import os

import unreal


def main():
    show = unreal.EditorAssetLibrary.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
    out = []
    for cue in show.get_editor_property("cues"):
        for a in cue.get_editor_property("wing_pair").get_editor_property("attachments"):
            lab = str(a.get_editor_property("label"))
            if lab == "P01 Wing 041 Entry High -Y" or lab.endswith("Blink Spot"):
                L = a.get_editor_property("lighting")
                c = L.get_editor_property("color")
                out.append({"label": lab, "color": [c.r, c.g, c.b], "use_temperature": bool(L.get_editor_property("use_temperature")),
                            "kelvin": L.get_editor_property("temperature_kelvin"), "units": str(L.get_editor_property("intensity_units"))})
    json.dump(out, open(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                                     "CodexStructure", "blink_colour.json"), "w"), indent=1)
    unreal.log(f"BLINK_COLOUR_OK|lamps={len(out)}|mutated=0")


main()
