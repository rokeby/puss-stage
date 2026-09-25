"""Resume scoped MetaHuman assembly, one character per editor callback."""
import builtins
import datetime
import json
import pathlib
import sys
import time
import traceback
import unreal

FOLDER = pathlib.Path('E:/PussStage/Saved/CodexMocap')
ROOT = '/Game/Metahuman/ShoreCast_20260910'
if str(FOLDER) not in sys.path:
    sys.path.insert(0, str(FOLDER))
import shore_character_authoring as author


def write(name, value):
    value['updated_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    (FOLDER / name).write_text(json.dumps(value, indent=2), encoding='utf-8')


def start(limit=6):
    author.subsystem()
    assert not getattr(builtins, 'PUSS_SHORE_RIG_RUNNING', False)
    assert not getattr(builtins, 'PUSS_SHORE_ASSEMBLY_RUNNING', False)
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
    dirty = unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
    assert not dirty, [str(p) for p in dirty]
    unreal.SystemLibrary.collect_garbage()
    brief = json.loads((FOLDER / 'shore_cast_brief.json').read_text(encoding='utf-8'))
    manifest_path = FOLDER / 'shore_cast_assets.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {'characters': []}
    completed = {p['id'] for p in manifest['characters']}
    queue = [p for p in brief['characters'][:limit] if p['id'] not in completed]
    state = {'state': 'scheduled', 'busy': False, 'completed': len(completed), 'target_count': limit}
    builtins.PUSS_SHORE_ASSEMBLY_RUNNING = True
    timer = {'next': time.monotonic() + 3.0}

    def tick(delta):
        if state['busy'] or time.monotonic() < timer['next']:
            return
        if not queue:
            unreal.unregister_slate_post_tick_callback(handle)
            builtins.PUSS_SHORE_ASSEMBLY_RUNNING = False
            state.update(state='complete', busy=False)
            write('shore_assembly_status.json', state)
            unreal.log('SHORE_CAST_ASSEMBLY_COMPLETE|count=' + str(len(manifest['characters'])))
            return
        person = queue.pop(0)
        state.update(state='opening_character', busy=True, character=person['id'])
        write('shore_assembly_status.json', state)
        character = None
        sub = None
        try:
            character = unreal.load_asset(ROOT + '/Characters/MHC_' + person['id'])
            assert isinstance(character, unreal.MetaHumanCharacter)
            sub = author.open_character(character)
            # The pilot's successful rig is retained. For other drafts request a new rig.
            if person['id'] != 'Shore01_M56':
                state['state'] = 'requesting_rig'
                write('shore_assembly_status.json', state)
                params = unreal.MetaHumanCharacterAutoRiggingRequestParams()
                params.blocking = True
                params.report_progress = False
                params.rig_type = unreal.MetaHumanRigType.JOINTS_ONLY
                sub.request_auto_rigging(character, params)
                assert unreal.EditorAssetLibrary.save_loaded_asset(character, only_if_is_dirty=False)
            if not character.get_editor_property('has_high_resolution_textures'):
                state['state'] = 'downloading_texture_sources'
                write('shore_assembly_status.json', state)
                params = unreal.MetaHumanCharacterTextureRequestParams()
                params.blocking = True
                params.report_progress = False
                sub.request_texture_sources(character, params)
                assert character.get_editor_property('has_high_resolution_textures'), 'Texture download did not complete'
                assert unreal.EditorAssetLibrary.save_loaded_asset(character, only_if_is_dirty=False)
            assert sub.can_build_meta_human(character, log_error=True), 'Character is not ready to assemble'
            state['state'] = 'assembling'
            write('shore_assembly_status.json', state)
            destination = ROOT + '/Assembled/' + person['id']
            assert not unreal.EditorAssetLibrary.list_assets(destination, recursive=True), 'Review existing build before overwriting: ' + destination
            params = unreal.MetaHumanCharacterEditorBuildParameters()
            params.pipeline_type = unreal.MetaHumanDefaultPipelineType.OPTIMIZED
            params.pipeline_quality = unreal.MetaHumanQualityLevel.MEDIUM
            params.absolute_build_path = destination
            params.common_folder_path = ROOT + '/Assembled/Common'
            params.enable_wardrobe_item_validation = True
            sub.build_meta_human(character, params)
            assert unreal.EditorAssetLibrary.save_loaded_asset(character, only_if_is_dirty=False)
            # The native builder creates packages in memory but does not save them.
            assert unreal.EditorAssetLibrary.save_directory(ROOT + '/Assembled', only_if_is_dirty=True, recursive=True)
            assets = []
            for path in unreal.EditorAssetLibrary.list_assets(destination, recursive=True, include_folder=False):
                data = unreal.EditorAssetLibrary.find_asset_data(path)
                assets.append({'path': path, 'class': str(data.asset_class_path.asset_name)})
            write('assembly_assets_' + person['id'] + '.json', {'assets': assets})
            blueprints = [a['path'] for a in assets if a['class'] == 'Blueprint' and '/BP_' in a['path']]
            bodies = [a['path'] for a in assets if a['class'] == 'SkeletalMesh' and ('/Body/' in a['path'] or '_body.' in a['path'].lower())]
            assert len(blueprints) == 1, blueprints
            assert len(bodies) == 1, bodies
            body = unreal.load_asset(bodies[0])
            assert body and body.get_editor_property('skeleton')
            for a in assets:
                assert unreal.EditorAssetLibrary.does_asset_exist(a['path']), a
                package = a['path'].split('.')[0]
                disk = pathlib.Path('E:/PussStage/Content') / (package[len('/Game/'):] + '.uasset')
                assert disk.is_file() and disk.stat().st_size > 0, str(disk)
            result = {**person, 'character': character.get_path_name(), 'blueprint': blueprints[0],
                      'body_mesh': bodies[0], 'skeleton': body.get_editor_property('skeleton').get_path_name(),
                      'asset_count': len(assets), 'pipeline': 'OPTIMIZED', 'quality': 'MEDIUM',
                      'has_high_resolution_textures': True, 'can_build': True,
                      'appearance_review': 'pending', 'motion_review': 'pending'}
            manifest['characters'].append(result)
            write('shore_cast_assets.json', manifest)
            state.update(state='character_assembled', completed=len(manifest['characters']))
            unreal.log('SHORE_CHARACTER_ASSEMBLED|' + json.dumps(result))
        except Exception as exc:
            state.update(state='attention_required', error=str(exc), traceback=traceback.format_exc())
            unreal.unregister_slate_post_tick_callback(handle)
            builtins.PUSS_SHORE_ASSEMBLY_RUNNING = False
            unreal.log_error('SHORE_CAST_ASSEMBLY_FAILED|' + str(exc))
        finally:
            if sub and character and sub.is_object_added_for_editing(character):
                sub.remove_object_to_edit(character)
            character = None
            sub = None
            # Release the discarded Creator previews between characters.
            unreal.SystemLibrary.collect_garbage()
            state['busy'] = False
            write('shore_assembly_status.json', state)
            timer['next'] = time.monotonic() + 3.0

    handle = unreal.register_slate_post_tick_callback(tick)
    write('shore_assembly_status.json', state)
    unreal.log('SHORE_CAST_ASSEMBLY_SCHEDULED|target=' + str(limit))
