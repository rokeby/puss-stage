"""Read-only: which actors carry a Go1RemoteReceiverComponent? (30 Sep, before retiring Saved/Go1Move.)
Success marker: PUSS_GO1_RECEIVER_HOST"""
import unreal


def main():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    hosts = []
    for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
        for component in actor.get_components_by_class(unreal.Go1RemoteReceiverComponent):
            hosts.append("%s (%s) port=%s" % (actor.get_actor_label(), actor.get_class().get_name(),
                                               component.get_editor_property("listen_port")))
    unreal.log("PUSS_GO1_RECEIVER_HOST|count=%d|%s" % (len(hosts), hosts))


main()
