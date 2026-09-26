"""Send a recorded clip to the user's Telegram via their existing bot (outbound only).

Usage: python send_clip_telegram.py <clip.mp4> [--caption "text"]

Credentials are NOT stored by this script and are never typed in by an agent. The user places them
themselves in C:/Users/Administrator/.claude/channels/telegram/.env:
    TELEGRAM_BOT_TOKEN=...      (the existing bot's token)
    TELEGRAM_CHAT_ID=...        (the user's own chat id with that bot)
Sending only (sendVideo) does not poll for updates, so it does not conflict with the bot's channel
running on another machine. Telegram bot uploads are limited to 50 MB.
"""
import argparse, json, os, subprocess, sys

ENV = os.path.expanduser(r"~/.claude/channels/telegram/.env")


def load_env(path):
    vals = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1); vals[k.strip()] = v.strip().strip('"')
    return vals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("--caption", default="")
    a = ap.parse_args()
    env = {**load_env(ENV), **{k: v for k, v in os.environ.items() if k.startswith("TELEGRAM_")}}
    token, chat = env.get("TELEGRAM_BOT_TOKEN"), env.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        sys.exit(f"missing TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID in {ENV}")
    if os.path.getsize(a.clip) > 49 * 1024 * 1024:
        sys.exit("clip over Telegram's 50 MB bot limit")
    r = subprocess.run(["curl", "-s", "-F", f"chat_id={chat}", "-F", "supports_streaming=true",
                        "-F", f"caption={a.caption[:1000]}", "-F", f"video=@{a.clip}",
                        f"https://api.telegram.org/bot{token}/sendVideo"], capture_output=True, text=True)
    try:
        ok = json.loads(r.stdout).get("ok")
    except Exception:
        ok = False
    print("sent" if ok else "failed: " + (r.stdout or r.stderr)[:300].replace(token, "<token>"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
