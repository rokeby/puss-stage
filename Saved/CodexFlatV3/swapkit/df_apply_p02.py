"""Entry point for the P02 DF apply batch."""
import os
import runpy

runpy.run_path(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "df_apply.py"),
    init_globals={"FLATV3_PASSAGE": "P02"}, run_name="__main__",
)

