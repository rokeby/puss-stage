"""No-edit binding: shared revert.py with the bound P06 run config."""
from pathlib import Path
import runpy

HERE = Path(__file__).resolve().parent
runpy.run_path(str(HERE / "revert.py"), run_name="__main__",
               init_globals={"FLATV3_CONFIG": str(HERE / "run_p06.json")})
