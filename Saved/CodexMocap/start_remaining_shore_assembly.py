import sys
import importlib
folder = 'E:/PussStage/Saved/CodexMocap'
if folder not in sys.path:
    sys.path.insert(0, folder)
import assemble_shore_cast
importlib.reload(assemble_shore_cast)
assemble_shore_cast.start(limit=6)
