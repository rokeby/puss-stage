"""Read-only: list spawn-capable Python APIs available in this editor (5 Oct)."""
import unreal
hits = []
for cls_name in ("GameplayStatics", "EditorLevelLibrary", "EditorActorSubsystem", "World", "SystemLibrary"):
    cls = getattr(unreal, cls_name, None)
    if cls is None:
        continue
    for n in dir(cls):
        if "spawn" in n.lower():
            hits.append("%s.%s" % (cls_name, n))
unreal.log("SPAWN_API_PROBE|" + ";".join(hits))
