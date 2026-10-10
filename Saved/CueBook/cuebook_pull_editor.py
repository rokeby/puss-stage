"""Pull or import the Puss Cue Book from inside Unreal Editor.

Online use reads CUEBOOK_PASS from Saved/CueBook/cuebook_pass.txt. This module never
creates that file and redacts its contents from all subprocess output before logging.

Optional PIE console alias:
    py Saved/CueBook/cuebook_pull_editor.py
    py Saved/CueBook/cuebook_pull_editor.py export "C:/path/cuebook-backup.json"
"""

from __future__ import annotations

import csv
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, Optional

try:
    import unreal
except ImportError:  # Offline harness injects its fake module.
    unreal = None


PASS_RELATIVE = os.path.join("Saved", "CueBook", "cuebook_pass.txt")
SYNC_RELATIVE = os.path.join("Tools", "CueSheet", "cue_sync.py")
REPORT_RELATIVE = os.path.join("Docs", "CueSheet", "web_report.md")
WORKING_RELATIVE = os.path.join("Docs", "CueSheet", "working.csv")
SURTITLE_RELOAD_COMMAND = "InfinityStage.Surtitles.Reload"


@dataclass
class SyncResult:
    ok: bool
    mode: str
    rows_changed: int = 0
    conflicts: int = 0
    report_path: str = ""
    message: str = ""
    cue_director_reload: str = "next PIE (or F5 in PIE)"
    surtitles_reload: str = "next PIE"


def _project_dir(unreal_module=None) -> str:
    module = unreal_module or unreal
    if module is None:
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.abspath(module.Paths.project_dir())


def _python_executable(project_dir: str, unreal_module=None) -> str:
    module = unreal_module or unreal
    if module is not None:
        candidate = os.path.join(
            module.Paths.engine_dir(), "Binaries", "ThirdParty", "Python3", "Win64", "python.exe"
        )
        if os.path.isfile(candidate):
            return candidate
    if os.path.basename(sys.executable).lower().startswith("python"):
        return sys.executable
    raise RuntimeError("Could not find Unreal's bundled python.exe")


def _read_rows(path: str):
    if not os.path.isfile(path):
        return {}
    with open(path, newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    return {(row.get("Key") or "row:%d" % index): row for index, row in enumerate(rows)}


def _changed_row_count(before, after) -> int:
    return sum(1 for key in set(before) | set(after) if before.get(key) != after.get(key))


def _redact(text: str, secret: str) -> str:
    if not text:
        return ""
    return text.replace(secret, "[REDACTED]") if secret else text


def _parse_conflicts(output: str) -> int:
    matches = re.findall(r"CUE_SYNC_WEBPULL_OK[^\r\n]*\bconflicts=(\d+)", output)
    return int(matches[-1]) if matches else 0


def _pie_world(unreal_module):
    try:
        subsystem = unreal_module.get_editor_subsystem(unreal_module.UnrealEditorSubsystem)
        return subsystem.get_game_world()
    except Exception:
        return None


def _trigger_reloads(unreal_module):
    world = _pie_world(unreal_module)
    if world is None:
        return "next PIE", "next PIE (or F5 in PIE)"
    unreal_module.SystemLibrary.execute_console_command(world, SURTITLE_RELOAD_COMMAND)
    return "command sent in PIE", "F5 in PIE"


def _show(unreal_module, title: str, message: str):
    if unreal_module is None:
        return
    unreal_module.log("%s: %s" % (title, message.replace("\n", " | ")))
    unreal_module.EditorDialog.show_message(
        title, message, unreal_module.AppMsgType.OK, unreal_module.AppReturnType.OK
    )


def _default_runner(command, **kwargs):
    return subprocess.run(command, **kwargs)


def run_sync(
    mode="cuebook",
    backup_path=None,
    *,
    project_dir=None,
    unreal_module=None,
    runner: Optional[Callable] = None,
    python_executable=None,
    pass_path=None,
    show_dialog=True,
):
    """Run cue_sync and return a structured, already-redacted result."""
    module = unreal_module if unreal_module is not None else unreal
    root = os.path.abspath(project_dir or _project_dir(module))
    sync_path = os.path.join(root, SYNC_RELATIVE)
    report_path = os.path.join(root, REPORT_RELATIVE)
    working_path = os.path.join(root, WORKING_RELATIVE)
    secret = ""

    if mode not in ("cuebook", "export"):
        result = SyncResult(False, mode, report_path=report_path, message="Unknown Cue Book mode: %s" % mode)
        if show_dialog:
            _show(module, "Pull Cue Book", result.message)
        return result

    environment = os.environ.copy()
    command_args = [python_executable or _python_executable(root, module), sync_path, mode]
    if mode == "cuebook":
        local_pass = os.path.abspath(pass_path or os.path.join(root, PASS_RELATIVE))
        if not os.path.isfile(local_pass):
            message = "Cue Book passcode file is missing.\n\nCreate it yourself at:\n%s" % local_pass
            result = SyncResult(False, mode, report_path=report_path, message=message)
            if show_dialog:
                _show(module, "Pull Cue Book", message)
            return result
        with open(local_pass, encoding="utf-8-sig") as handle:
            secret = handle.read().strip()
        if not secret:
            message = "Cue Book passcode file is empty. Put the passcode in:\n%s" % local_pass
            result = SyncResult(False, mode, report_path=report_path, message=message)
            if show_dialog:
                _show(module, "Pull Cue Book", message)
            return result
        environment["CUEBOOK_PASS"] = secret
    else:
        if not backup_path:
            result = SyncResult(False, mode, report_path=report_path, message="No Cue Book backup JSON was selected.")
            if show_dialog:
                _show(module, "Export Cue Book Backup", result.message)
            return result
        command_args.append(os.path.abspath(backup_path))

    before = _read_rows(working_path)
    try:
        completed = (runner or _default_runner)(
            command_args,
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
    except Exception as error:
        message = _redact("Cue Book sync could not start: %s" % error, secret)
        result = SyncResult(False, mode, report_path=report_path, message=message)
        if show_dialog:
            _show(module, "Pull Cue Book", message)
        return result
    finally:
        environment.pop("CUEBOOK_PASS", None)

    output = _redact((completed.stdout or "") + "\n" + (completed.stderr or ""), secret)
    after = _read_rows(working_path)
    rows_changed = _changed_row_count(before, after)
    conflicts = _parse_conflicts(output)
    blocked = "CUE_SYNC_SURTITLES_UNREAL_EDITS" in output
    ok = completed.returncode == 0 and not blocked and (
        "CUE_SYNC_EXPORT_OK" in output or "CUE_SYNC_WEBPULL_OK" in output
    )

    if ok:
        surtitles, director = _trigger_reloads(module) if module is not None else ("not tested", "not tested")
        message = (
            "Cue Book updated.\nRows changed: %d\nConflicts: %d\nReport: %s\n"
            "Surtitles: %s\nCue Director: %s"
        ) % (rows_changed, conflicts, report_path, surtitles, director)
        result = SyncResult(True, mode, rows_changed, conflicts, report_path, message, director, surtitles)
    elif blocked:
        message = (
            "Cue Book export stopped safely because Unreal-side surtitle edits need importing first.\n"
            "No generated cue/surtitle files were overwritten.\n\nDetails:\n%s"
        ) % output.strip()
        result = SyncResult(False, mode, rows_changed, conflicts, report_path, message)
    else:
        detail = output.strip() or "cue_sync returned exit code %d" % completed.returncode
        result = SyncResult(
            False,
            mode,
            rows_changed,
            conflicts,
            report_path,
            "Cue Book update failed.\n\n%s" % detail,
        )

    if show_dialog:
        _show(module, "Pull Cue Book" if mode == "cuebook" else "Export Cue Book Backup", result.message)
    return result


def _choose_json_file():
    """Windows file dialog without adding a C++ editor dependency."""
    script = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "$d=New-Object System.Windows.Forms.OpenFileDialog;"
        "$d.Title='Choose a Cue Book backup';"
        "$d.Filter='Cue Book backup (*.json)|*.json|All files (*.*)|*.*';"
        "if($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){$d.FileName}"
    )
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-STA", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def run_pull():
    return run_sync("cuebook")


def run_export_from_dialog():
    selected = _choose_json_file()
    return run_sync("export", selected)


if __name__ == "__main__":
    requested = sys.argv[1].lower() if len(sys.argv) > 1 else "cuebook"
    if requested == "export":
        path = sys.argv[2] if len(sys.argv) > 2 else _choose_json_file()
        run_sync("export", path)
    else:
        run_sync("cuebook")
