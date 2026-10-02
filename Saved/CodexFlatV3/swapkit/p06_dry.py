"""No-edit binding: shared dry.py plus the P06 mapping adapter."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dry
import p06_support

p06_support.install(dry.c)
dry.main(str(HERE / "run_p06.json"))
