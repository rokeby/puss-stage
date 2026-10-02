"""No-edit binding: p06_import.py with run_p06.json."""
from pathlib import Path
import runpy

HERE = Path(__file__).resolve().parent
runpy.run_path(str(HERE / "p06_import.py"), run_name="__main__",
               init_globals={"FLATV3_CONFIG": str(HERE / "run_p06.json")})
