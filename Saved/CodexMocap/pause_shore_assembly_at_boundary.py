"""Pause the existing callback queue only after its active character finishes."""
import builtins
import gc
import inspect
import types
import unreal
import assemble_shore_cast as assembly

callbacks = [obj for obj in gc.get_objects() if isinstance(obj, types.FunctionType)
             and obj.__module__ == 'assemble_shore_cast' and obj.__name__ == 'tick']
active = []
for callback in callbacks:
    cells = inspect.getclosurevars(callback).nonlocals
    if 'handle' in cells and 'state' in cells and 'queue' in cells:
        active.append(cells)
assert len(active) == 1, 'Expected exactly one active assembly queue: ' + str(len(active))
original = active[0]

def pause_when_idle(delta):
    if original['state']['busy']:
        return
    unreal.unregister_slate_post_tick_callback(original['handle'])
    unreal.unregister_slate_post_tick_callback(builtins.PUSS_SHORE_PAUSE_HANDLE)
    builtins.PUSS_SHORE_ASSEMBLY_RUNNING = False
    original['state'].update(state='paused_for_memory_check', busy=False)
    assembly.write('shore_assembly_status.json', original['state'])
    unreal.SystemLibrary.collect_garbage()
    unreal.log('SHORE_ASSEMBLY_PAUSED_AT_SAFE_BOUNDARY|completed=' + str(original['state']['completed']))

builtins.PUSS_SHORE_PAUSE_HANDLE = unreal.register_slate_post_tick_callback(pause_when_idle)
unreal.log('SHORE_ASSEMBLY_BOUNDARY_PAUSE_REQUESTED')
