import sys, builtins, importlib
import unreal
folder='E:/PussStage/Saved/CodexMocap'
if folder not in sys.path:
    sys.path.insert(0,folder)
previous=getattr(builtins,'PUSS_MOCAP_BATCH',None)
assert previous is None or not previous.running, 'Batch already running'
batch_runner=importlib.reload(sys.modules['batch_runner']) if 'batch_runner' in sys.modules else importlib.import_module('batch_runner')
batch_runner.start()
if 'attach_verifier' in sys.modules:
    importlib.reload(sys.modules['attach_verifier'])
else:
    importlib.import_module('attach_verifier')
if 'attach_report' in sys.modules:
    importlib.reload(sys.modules['attach_report'])
else:
    importlib.import_module('attach_report')
import final_audit
final_audit.install()
unreal.log('MOCAP_BATCH_LAUNCH_SUCCESS|asynchronous_queue_registered')
