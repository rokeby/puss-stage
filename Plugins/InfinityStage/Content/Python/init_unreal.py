"""Infinity Stage editor Python startup hooks."""

import os
import sys

import unreal


def _register_cue_book_menu():
    script_dir = os.path.join(unreal.Paths.project_saved_dir(), "CueBook")
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    menus = unreal.ToolMenus.get()
    main_menu = menus.find_menu("LevelEditor.MainMenu")
    if main_menu is None:
        unreal.log_warning("PUSS_CUEBOOK_MENU_SKIPPED: LevelEditor.MainMenu was not found")
        return

    puss_menu = main_menu.add_sub_menu(
        main_menu.get_name(),
        "Puss",
        "Puss.MainMenu",
        "Puss",
        "Puss show tools",
    )

    pull = unreal.ToolMenuEntry(
        name="Puss.PullCueBook",
        type=unreal.MultiBlockType.MENU_ENTRY,
    )
    pull.set_label("Pull Cue Book")
    pull.set_tool_tip("Download, merge, render, and reload the online Cue Book")
    pull.set_string_command(
        unreal.ToolMenuStringCommandType.PYTHON,
        "",
        "import cuebook_pull_editor; cuebook_pull_editor.run_pull()",
    )
    puss_menu.add_menu_entry("CueBook", pull)

    export = unreal.ToolMenuEntry(
        name="Puss.ExportCueBookBackup",
        type=unreal.MultiBlockType.MENU_ENTRY,
    )
    export.set_label("Export from Cue Book backup...")
    export.set_tool_tip("Choose a downloaded Cue Book JSON backup and export it into the show")
    export.set_string_command(
        unreal.ToolMenuStringCommandType.PYTHON,
        "",
        "import cuebook_pull_editor; cuebook_pull_editor.run_export_from_dialog()",
    )
    puss_menu.add_menu_entry("CueBook", export)
    menus.refresh_all_widgets()
    unreal.log("PUSS_CUEBOOK_MENU_READY")


_register_cue_book_menu()
