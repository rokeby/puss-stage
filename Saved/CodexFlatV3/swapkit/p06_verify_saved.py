"""No-edit binding: shared saved-state verifier with the bound P06 config."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
# The editor's Python keeps modules across scripts: purge this folder's cached
# modules so the on-disk code runs (P06 verify ran a stale verify.py, 2 Oct).
for _name, _mod in list(sys.modules.items()):
    _file = getattr(_mod, "__file__", None) or ""
    if _file and Path(_file).resolve().parent == HERE:
        del sys.modules[_name]
import verify_saved
import p06_support

p06_support.install(verify_saved.c)
p06_support.install(verify_saved.verifier.c)
verify_saved.main(str(HERE / "run_p06.json"))
