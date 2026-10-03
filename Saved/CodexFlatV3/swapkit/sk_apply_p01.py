"""Entry point for the P01 SK apply batch."""
import os
import runpy

runpy.run_path(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "sk_apply.py"),
    init_globals={"FLATV3_PASSAGE": "P01"}, run_name="__main__",
)
