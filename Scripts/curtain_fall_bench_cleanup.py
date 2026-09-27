"""Remove any ZZ_TEMP_SoftGoods* / ZZ_TransientCapture_SoftGoods* actors a fall bench left behind."""
import unreal

ss = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
gone = []
for a in ss.get_all_level_actors():
    label = a.get_actor_label()
    if label.startswith(("ZZ_TEMP_SoftGoods", "ZZ_TransientCapture_SoftGoods")):
        ss.destroy_actor(a)
        gone.append(label)
unreal.log(f"PUSS_SOFTGOODS_FALL_BENCH_CLEANUP_SUCCESS|removed={len(gone)}|{gone}")
