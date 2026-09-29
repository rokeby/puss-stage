"""Read-only: log the Python signatures of the reload/unload helpers. Mutates nothing."""
import unreal
for name in ("reload_packages", "unload_packages", "load_map", "new_blank_map"):
    fn = getattr(unreal.EditorLoadingAndSavingUtils, name, None)
    unreal.log(f"API_DOC|{name}|{(fn.__doc__ or '').strip()[:900] if fn else 'missing'}")
unreal.log(f"API_DOC|ReloadMode|{[m for m in dir(unreal) if 'ReloadPackages' in m or 'InteractionMode' in m]}")
