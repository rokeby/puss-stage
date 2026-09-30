"""Read-only probe: can a GeometryCache asset name the Alembic it was imported from (so a bake's
own DropBake/<bake_id>.json can be found from the placed cache)? Mutates nothing."""
import unreal


def main():
    rows = []
    for path in unreal.EditorAssetLibrary.list_assets("/Game", recursive=True, include_folder=False):
        data = unreal.EditorAssetLibrary.find_asset_data(path)
        if str(data.asset_class_path.asset_name) != "GeometryCache":
            continue
        gc = unreal.load_asset(path)
        try:
            aid = gc.get_editor_property("asset_import_data")
            files = list(aid.extract_filenames()) if aid else []
        except Exception as exc:  # noqa: BLE001
            files = [f"ERR {exc}"]
        rows.append(f"{path.split('.')[0]} <- {files[:1]}")
    unreal.log("GC_IMPORT_SOURCE|" + " || ".join(rows[:12]))


main()
