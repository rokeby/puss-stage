"""Thin guarded-loopback runner for p93_live.py. Configure p93_args.json first."""
import os
import runpy

HERE = os.path.dirname(os.path.abspath(__file__))
runpy.run_path(os.path.join(HERE, "p93_live.py"), run_name="__p93_live__")
