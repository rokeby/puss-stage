# Recording a PIE take and sending it to Telegram

Ported from MHFat's conductor tooling, 2026-09-26. Same two steps, Puss paths.

```bash
python Scripts/Conductor/record_clip.py --seconds 60 --label "p03 rig drop"
python Scripts/Conductor/send_clip_telegram.py <the .mp4 it printed> --caption "P03 after the rig"
```

`record_clip.py` finds the first visible window whose title contains `Preview [NetMode`
(the PIE window), falling back to the Puss editor, captures just that window's
rectangle with Desktop Duplication and encodes H.264 on the GPU at about
1 Mbit/s — roughly 5–10 MB for 60–90 s at 960 px wide, which is inside
Telegram's 50 MB bot limit. Clips land in `Saved/Conductor/Clips/` with a
`.json` sidecar recording the label, start time and window.

It **records only**. It drives nothing in the engine, so PIE has to be running
and the take has to be underway before it starts.

**The display must be awake and unlocked** — Desktop Duplication captures what is
actually on screen, so a locked session or a minimised PIE window records nothing
useful.

## Credentials

`send_clip_telegram.py` reads:

```
C:/Users/Administrator/.claude/channels/telegram/.env
    TELEGRAM_BOT_TOKEN=...
    TELEGRAM_CHAT_ID=...
```

**Gary places that file himself.** No agent types, reads back or stores those
values, and they are not in the repo. That file does not currently exist on this
machine — it has to be created before the first send. Sending uses `sendVideo`
only and never polls for updates, so it cannot conflict with the bot's channel
running elsewhere.
