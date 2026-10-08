# Puss Cue Book

A web page where Klara, Cameron (and anyone with the passcode) can click through the cue list segment by
segment, with stills, and edit it. No accounts. Built 8 Oct 2026 for Gary.

- **Page:** `site/`, published on GitHub Pages from the repo `rokeby/puss-cue-book`.
- **Data:** a private Google Sheet on Gary's account, reached through `apps_script/Code.gs` (an Apps Script web
  app). The page holds no cue text, so the public page shows nothing without the passcode.
- **Into the project:** `python Tools/CueSheet/cue_sync.py cuebook` (with `CUEBOOK_PASS` set) downloads the list,
  keeps the download in `Docs/CueSheet/pulls/`, and merges it into `Docs/CueSheet/working.csv`. A field edited both
  on the page and in the working copy keeps the working copy and is listed in `Docs/CueSheet/web_report.md`.

## How work is kept safe

| Layer | What it protects against |
|---|---|
| Every edit is queued on the device (browser storage) until the server confirms it | dropped wifi, closed tab, crashed browser: sent on the next open |
| Typing in an open cue is kept on the device until Save | closing the tab mid-edit |
| Writes carry an id; the server ignores a repeat | a retry saving twice |
| A field someone else changed since you opened it comes back as a conflict, both versions shown | two people overwriting each other |
| "Mark as cut" instead of delete | losing a cue |
| `log` sheet: append-only record of every change (who, when, before, after) | any mistake: the old text is always there |
| Google Sheets File > Version history | the sheet itself being damaged |
| A copy of the spreadsheet every 6 hours into Drive "Puss Cue Book backups" | the sheet being deleted |
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

## Testing

`python Tools/CueBook/test/build_test_site.py` builds `test/_build`: the real page with the REAL `Code.gs` running
in the browser on a fake spreadsheet (`test/mock_services.js`), so the whole flow runs locally
(`.claude/launch.json` entry `cuebook-test`, passcode `test-pass`). `window.MOCK_OFFLINE = true` simulates a dropped
connection.

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
