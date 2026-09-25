"""Read-only scene/cloth inventory for the user's six-character placement request."""
import json
import os
import pathlib
import unreal

ROOT = pathlib.Path('E:/PussStage')
FOLDER = ROOT / 'Saved/CodexMocap'
EXPECTED_WORLD = '/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice'


def path_of(value):
    return value.get_path_name() if isinstance(value, unreal.Object) else str(value)


def property_values(obj, names):
    result = {}
    for name in names:
        try:
            result[name] = path_of(obj.get_editor_property(name))
        except Exception:
            pass
    return result


def actor_record(actor):
    components = []
    for component in actor.get_components_by_class(unreal.ActorComponent):
        data = {'name': component.get_name(), 'class': component.get_class().get_name(),
                'path': component.get_path_name()}
        data.update(property_values(component, ['skeletal_mesh', 'skeletal_mesh_asset', 'static_mesh',
            'cloth_asset', 'physics_asset_override', 'animation_mode', 'animation_data',
            'anim_class', 'leader_pose_component', 'override_materials', 'collision_enabled',
            'collision_profile_name', 'relative_location', 'relative_rotation', 'relative_scale3d',
            'attach_parent', 'attach_socket_name', 'visible', 'hidden_in_game']))
        if hasattr(component, 'get_skeletal_mesh_asset'):
            mesh = component.get_skeletal_mesh_asset()
            if mesh:
                data['mesh'] = mesh.get_path_name()
                data['mesh_settings'] = property_values(mesh, ['skeleton', 'physics_asset'])
        if hasattr(component, 'get_materials'):
            data['materials'] = [path_of(m) for m in component.get_materials()]
        components.append(data)
    location = actor.get_actor_location()
    return {'label': actor.get_actor_label(), 'path': actor.get_path_name(),
            'class': actor.get_class().get_path_name(),
            'location': [location.x, location.y, location.z],
            'transform': str(actor.get_actor_transform()), 'components': components,
            'properties': property_values(actor, ['tags', 'hidden', 'attach_parent_actor'])}


def run():
    actual = pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
    assert actual == ROOT.resolve()
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    assert not editor.get_game_world(), 'Read the editor setup outside PIE'
    world = editor.get_editor_world()
    assert world.get_path_name().split('.')[0] == EXPECTED_WORLD, world.get_path_name()
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    terms = ('clam', 'ortalan', 'ortolan', 'manny', 'mannequin', 'shore', 'cloth', 'sheet')
    records = []
    for actor in actors:
        signature = (actor.get_actor_label() + ' ' + actor.get_class().get_path_name()).lower()
        meshes = actor.get_components_by_class(unreal.SkeletalMeshComponent)
        if meshes or any(term in signature for term in terms):
            records.append(actor_record(actor))
    assets = []
    for path in ['/Game/Scenes/LS_Clams', '/Game/Scenes/BP_OrtalanSheet',
                 '/Game/Scenes/CA__OrtolanSheets', '/Game/Scenes/SM_OrtalanSheet',
                 '/Game/Scenes/LS_OrtalanSheetSway']:
        asset = unreal.load_asset(path)
        if not asset:
            assets.append({'path': path, 'exists': False})
            continue
        entry = {'path': asset.get_path_name(), 'class': asset.get_class().get_name(),
                 'properties': property_values(asset, ['physics_asset', 'skeleton', 'dataflow_asset',
                     'materials', 'preview_mesh', 'preview_animation'])}
        if isinstance(asset, unreal.LevelSequence):
            entry['display_rate'] = str(asset.get_display_rate())
            entry['bindings'] = []
            for binding in asset.get_bindings():
                tracks = []
                for track in binding.get_tracks():
                    tracks.append({'class': track.get_class().get_name(), 'name': track.get_name(),
                                   'sections': [{'class': section.get_class().get_name(),
                                       'properties': property_values(section, ['params', 'sub_sequence'])}
                                       for section in track.get_sections()]})
                entry['bindings'].append({'name': str(binding.get_name()),
                                          'id': str(binding.get_id()), 'tracks': tracks})
        assets.append(entry)
    report = {'pid': os.getpid(), 'world': world.get_path_name(), 'mode': 'read_only',
              'actors': records, 'assets': assets,
              'dirty_content': [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
              'dirty_maps': [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}
    (FOLDER / 'clam_setup_inventory.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    unreal.log('CLAM_SETUP_READ_ONLY_INSPECT_SUCCESS|actors=' + str(len(records)))
    return report


if __name__ == '__main__':
    run()
