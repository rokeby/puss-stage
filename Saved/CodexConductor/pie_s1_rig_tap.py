"""READ-ONLY PIE tap: master frame + world transforms of every S1 hangar part (labels starting 'S1 Hangar'). PIE_S1RIG|json"""
import json, time
def main():
    import unreal
    w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    root = list(unreal.GameplayStatics.get_all_actors_of_class(w, unreal.InfinityStageShowRoot))[0]
    out = {"wall": round(time.time(), 2), "master": root.transport.get_current_master_frame().value}
    for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
        l = str(a.get_actor_label())
        if l.startswith("S1 Hangar") and ("Root" in l or "Roof" in l or "Lattice" in l or "Hinge" in l):
            p, r = a.get_actor_location(), a.get_actor_rotation()
            out[l] = [round(p.x), round(p.y), round(p.z), round(r.pitch, 1), round(r.yaw, 1), round(r.roll, 1)]
    unreal.log("PIE_S1RIG|" + json.dumps(out))
main()
