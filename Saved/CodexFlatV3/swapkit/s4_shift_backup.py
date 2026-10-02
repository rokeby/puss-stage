"""AS-IS binding: P04 inner-shift backup."""
from pathlib import Path
import runpy
HERE = Path(__file__).resolve().parent
runpy.run_path(str(HERE / "shift_backup.py"), run_name="__main__",
               init_globals={"FLATV3_CONFIG": str(HERE / "run_shift_p04.json")})
