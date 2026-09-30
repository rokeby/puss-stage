"""Read-only: the v2 box's LANDED numbers (root at pitch 0), for Look & camera.
Every hangar actor is expressed in the root's frame and placed at the landed
root (pivot, rotation 0), so nothing needs to move. Also reads Scene 4's cut
times. Mutates nothing. Lean: all work in main()."""
import unreal

TAG = "RigAtmos.Scene4Hangar"
SCENE4 = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_04"
CAM = unreal.Vector(10668.5, 240000.0, 180.0)


def main():
    c0 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m0 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    mine = {a.get_actor_label(): a for a in sub.get_all_level_actors() if TAG in [str(t) for t in a.get_editor_property("tags")]}
    root = mine["S4 Hangar Root"]
    rt = root.get_actor_transform()
    pivot = rt.translation
    unreal.log(f"S4_NUM|root|pivot=({pivot.x:.1f},{pivot.y:.1f},{pivot.z:.1f})|rot={root.get_actor_rotation()}")
    for label in sorted(mine):
        a = mine[label]
        if a == root:
            continue
        lo, ext = a.get_actor_bounds(False)
        pts = []
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    w = unreal.Vector(lo.x + sx * ext.x, lo.y + sy * ext.y, lo.z + sz * ext.z)
                    r = rt.inverse_transform_location(w)
                    pts.append((pivot.x + r.x - CAM.x, pivot.y + r.y - CAM.y, pivot.z + r.z))
        mn = [min(p[i] for p in pts) for i in range(3)]
        mx = [max(p[i] for p in pts) for i in range(3)]
        c = rt.inverse_transform_location(a.get_actor_location())
        unreal.log(f"S4_NUM|{label}|centre_rel_cam=({pivot.x + c.x - CAM.x:.0f},{pivot.y + c.y - CAM.y:.0f},{pivot.z + c.z:.0f})"
                   f"|bounds_x={mn[0]:.0f}..{mx[0]:.0f}|y={mn[1]:.0f}..{mx[1]:.0f}|z={mn[2]:.0f}..{mx[2]:.0f}")
    scene = unreal.load_asset(SCENE4)
    for t in scene.find_tracks_by_type(unreal.MovieSceneCameraCutTrack):
        for s in t.get_sections():
            unreal.log(f"S4_NUM|cut|{s.get_start_frame_seconds():.3f}..{s.get_end_frame_seconds():.3f}")
    unreal.log(f"S4_NUM|scene_end={scene.get_playback_end_seconds():.3f}")
    c1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    unreal.log(f"S4_NUM_OK|dirty_before={c0}+{m0}|dirty_after={c1}+{m1}")


main()
