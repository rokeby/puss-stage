# Puss Cue Book

A web page where Klara, Cameron (and anyone with the passcode) can click through the cue list segment by
segment, with stills, and edit it. No accounts. Built 8 Oct 2026 for Gary.

- **Page:** `site/`, published on GitHub Pages from the repo `rokeby/puss-cue-book`.
- **Data:** a private Google Sheet on Gary's account, reached through `apps_script/Code.gs` (an Apps Script web
  app). The page holds no cue text, so the public page shows nothing without the passcode.
- **Into the project:** `python Tools/CueSheet/cue_sync.py cuebook` (with `CUEBOOK_PASS` set) downloads the list,
  keeps the download in `Docs/CueSheet/pulls/`, and merges it into `Docs/CueSheet/working.csv`. A field edited both
  on the page and in the working copy keeps the working copy and is listed in `Docs/CueSheet/web_report.md`.
- **Surtitles:** each segment has a light time-coded line view (In, Out, Speaker, Text, Notes). Empty Text with an
  In time is a clear-screen row. `cue_sync.py export <backup.json>` writes the Unreal CSV and merge base; if Unreal
  changed the CSV, export writes a previewable `kind: "changes"` file and refuses to overwrite that edit.
- **Order:** each cue can move one step or after a named cue key. Only that cue's fractional `ord` changes, and a
  stale move becomes a conflict. The header's read-only Running order view shows the complete show on one page.
- **Undo:** the header button (or Ctrl/Cmd+Z outside a typing field) reverses this viewer's cue and surtitle edits,
  adds, cuts/restores and moves. Undo uses the ordinary offline queue and base-value conflict checks; added rows are
  marked as cut, never deleted. The viewer's last 100 undo steps are kept in browser storage.
- **At / GO help:** cue editing keeps a short explanation under At, GO and Pause possible, with a `?` expansion for
  accepted time formats and the real HOLD/PASS/BREATH behaviour.
- **Dog directions:** optional physical action, operator GO1 mode and treadmill state share one Dog group. Mode and
  treadmill carry forward when omitted (inherited values are grey); action remains cue-specific. Gary and Stage
  manager prints include the dog line, and the Dog preset prints dog directions with cue context.
- **Print / PDF:** the header's **Print…** panel offers Full, Stage manager, Klara, Gary, Cameron, Lighting, Sound and
  Dog presets, an optional segment range and an include-cut control. Its preview is the print layout; use the
  browser print dialog's **Save as PDF**. The same definitions live in `site/print_presets.json` and drive the
  offline command: `python Tools/CueSheet/cue_sync.py print stage-manager --from "Passage 1" --to "Passage 2"`.
  Output goes to `Docs/CueSheet/print/` as a self-contained HTML file to open and print in any browser.
- **Stills:** `segment_map.json` is the ordered Cue Book-name to Show-key map. Cueing copies
  `unreal/cuebook_stills_driver.py` to `Saved/CodexCueing/`; the Conductor runs DRY and then confirmed APPLY inside
  an already-running PIE. The driver imports the Conductor's `scene_stills.py`, never starts or ends PIE, and emits
  `CUEBOOK_STILLS_OK|...` only after its capture manifests, frame restores, and package census pass. Publish the
  passed run offline with `python Tools/CueBook/publish_stills.py DRY <run-dir>`, then the same command with `APPLY`
  and `--confirm APPLY_CUEBOOK_STILLS_PUBLISH`. Existing site files are moved to
  `Backups/PreCueBookStills-<run>/` before replacement; `REVERT <that-backup-dir>` with
  `--confirm REVERT_CUEBOOK_STILLS_PUBLISH` restores them without deleting the published copies.

## How work is kept safe

| Layer | What it protects against |
|---|---|
| Every edit is queued on the device (browser storage) until the server confirms it | dropped wifi, closed tab, crashed browser: sent on the next open |
| Typing in an open cue is kept on the device until Save | closing the tab mid-edit |
| Writes carry an id; the server ignores a repeat | a retry saving twice |
| A field someone else changed since you opened it comes back as a conflict, both versions shown | two people overwriting each other |
| A move carries its old `ord` and neighbour keys | two people reordering the same area into an accidental shuffle |
| "Mark as cut" instead of delete | losing a cue |
| `log` sheet: append-only record of every change (who, when, before, after) | any mistake: the old text is always there |
| Google Sheets File > Version history | the sheet itself being damaged |
| A copy of the spreadsheet every 6 hours ("Puss Cue Book backup <date>" in My Drive) | the sheet being deleted |
| Backup button: download .json / .csv; restore shows every difference before changing anything | anything else |
| `cue_sync cuebook` pulls into git | all of the above |

## One-time setup (Gary, at a computer, about 10 minutes)

1. Open <https://sheets.new> and name the sheet **Puss Cue Book data**. Keep it private.
2. In the sheet: **Extensions > Apps Script**. Delete what is there, paste all of `apps_script/Code.gs`, Save.
3. **Project Settings** (gear icon) > **Script properties** > Add property: `PASSCODE` = a passcode you will give
   Klara and Cameron.
4. Back in the editor, choose the function **installBackups** in the toolbar and press **Run**. Google asks for
   permission ("Google hasn't verified this app": Advanced > Go to … > Allow). This sets up the 6-hourly copies.
5. **Deploy > New deployment** > type **Web app**. Execute as: **Me**. Who has access: **Anyone**. Deploy, and copy
   the **Web app URL**.
6. Send Claude the Web app URL (it is not secret; the passcode is). Claude puts it in `site/config.js` and publishes.
7. Open the Cue Book, sign in with the passcode, then **Backup > Choose a backup file** and pick
   `Tools/CueBook/seed/PussCueBook_seed_from_working.json`, then **Load 96 cues**. (It refuses if the list is not
   empty, so it can't overwrite anything.)
8. Send Klara and Cameron the page link and the passcode.

Changing `Code.gs` later: paste the new code, then **Deploy > Manage deployments** > edit (pencil) > Version: **New
version** > Deploy. The URL stays the same.

The surtitles, cue At/GO fields and Dog group require that redeploy. Until then the new page keeps supported cue editing available and
says “Surtitles need the updated script.”

## Testing

`python Tools/CueBook/test/build_test_site.py` builds `test/_build`: the real page with the REAL `Code.gs` running
in the browser on a fake spreadsheet (`test/mock_services.js`), so the whole flow runs locally
(`.claude/launch.json` entry `cuebook-test`, passcode `test-pass`). `window.MOCK_OFFLINE = true` simulates a dropped
connection.

`python Tools/CueBook/test/build_test_site.py --browser-harness` also injects the automated browser runner. Serve
`test/_build` and open it in a 375 px-wide browser: it finishes with `CUEBOOK_BROWSER_HARNESS_OK 26/26` after print
presets, include-cut, running-order, accessible At/GO/pause/Dog help, dog carry-forward, field/move/add/cut and surtitle undo, undo conflict,
the typing Ctrl+Z negative control, offline undo/move/line reloads, line conflict, and both old-deployment controls.
The normal build remains the interactive mock.

Checked 8 Oct in the browser against the real `Code.gs` on the fake spreadsheet:
- seed: 96 cues round-trip field for field; a second seed is refused; a wrong passcode is refused;
- text that Sheets would mangle survives (`=SUM(A1)`, `007`, `1-2`, `'quoted`, `-3 dB`), but only on the fake
  spreadsheet: re-check on the real Sheet after setup;
- save from the page;
- save while offline, then a reload: the change was kept and sent when the page came back;
- typing left unsaved, then a reload: the text came back;
- a conflicting edit from another person: both versions shown, "Keep mine" saved, theirs still in the log;
- a retried write applied once;
- add a cue while offline: it lands between the right cues;
- backup download, then restore: every difference listed and nothing changed until confirmed;
- loading into an empty list from the page;
- phone width (375 px): no sideways scroll.

Not checked: the real Google Sheet and Apps Script (not deployed yet); the browser's "leave page?" warning (the test
browser suppresses it without a real click).
