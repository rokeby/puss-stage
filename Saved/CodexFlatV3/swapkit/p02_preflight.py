"""No-edit binding: preflight.py with run_p02.json."""
from pathlib import Path
import runpy

HERE = Path(__file__).resolve().parent
runpy.run_path(str(HERE / "preflight.py"), run_name="__main__",
               init_globals={"FLATV3_CONFIG": str(HERE / "run_p02.json")})

