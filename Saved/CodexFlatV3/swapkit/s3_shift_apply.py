"""AS-IS binding: P03 inner-shift apply."""
from pathlib import Path
import runpy
HERE = Path(__file__).resolve().parent
runpy.run_path(str(HERE / "shift_apply.py"), run_name="__main__",
               init_globals={"FLATV3_CONFIG": str(HERE / "run_shift_p03.json")})
