"""AS-IS binding: queue SavedMasterMatchesShow for FV3S2-20261002-01."""
import sys as _fv3_sys, os as _fv3_os
if __name__ == "__main__":
    # purge this folder's cached modules: the editor's Python keeps modules across
    # scripts, so a stale verify/common ran (P06, 2 Oct). Entry scripts only.
    _fv3_here = _fv3_os.path.dirname(_fv3_os.path.abspath(__file__))
    for _fv3_name, _fv3_mod in list(_fv3_sys.modules.items()):
        _fv3_file = getattr(_fv3_mod, "__file__", None) or ""
        if (_fv3_name != "__main__" and _fv3_file and
                _fv3_os.path.dirname(_fv3_os.path.abspath(_fv3_file)) == _fv3_here):
            del _fv3_sys.modules[_fv3_name]
from pathlib import Path
import runpy
TARGET = Path(__file__).resolve().parents[1] / "slot_v_queue_test.py"
runpy.run_path(str(TARGET), run_name="__main__",
               init_globals={"FLATV3_V_RUN": "FV3S2-20261002-01"})
