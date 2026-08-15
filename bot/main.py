"""
main.py — Entry point for the Discord bot.
Loads config, database, checks, status, then all feature modules
so commands and events register on the shared bot instance.
"""
import os
import sys
from threading import Thread

# Ensure package root is on path when run as script
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# IMPORTANT: name the Discord client something other than `bot`.
# `import bot.xxx` rebinds the name `bot` to the package and would break `.run()`.
from bot.config import bot as client
from bot.database import init_db
from bot.status import run_server

# Initialize SQLite schema
init_db()

# Register global checks (attaches @bot.check on the shared client)
import bot.checks  # noqa: F401

# Feature modules — importing them registers commands/events on the client
import bot.cogs.music  # noqa: F401
import bot.cogs.tickets  # noqa: F401
import bot.cogs.reaction_roles  # noqa: F401
import bot.cogs.marriage  # noqa: F401
import bot.cogs.moderation  # noqa: F401
import bot.cogs.vouch  # noqa: F401
import bot.cogs.applications  # noqa: F401
import bot.cogs.community  # noqa: F401
import bot.cogs.mod_slash  # noqa: F401
import bot.cogs.revenue  # noqa: F401  # Revenue tracking system
import bot.cogs.bot_control  # noqa: F401  # Bot control & owner system
import bot.cogs.role_info  # noqa: F401  # Role information commands

# Events (on_ready, on_message, member join/leave, message log, etc.)
import bot.events  # noqa: F401

# Dashboard Mongo bridge (available to events / features)
from bot import mongo_bridge  # noqa: F401


def _load_token() -> str:
    """Read bot token from env and normalize common paste mistakes."""
    raw_name = None
    raw = os.getenv("DISCORD_TOKEN")
    if raw:
        raw_name = "DISCORD_TOKEN"
    else:
        raw = os.getenv("BOT_TOKEN")
        if raw:
            raw_name = "BOT_TOKEN"

    if not raw:
        print("❌ CRITICAL ERROR: DISCORD_TOKEN or BOT_TOKEN environment variable is missing!")
        print("   On Render: Service → Environment → add DISCORD_TOKEN = (Bot token from Discord Developer Portal)")
        sys.exit(1)

    token = raw.strip()
    # Remove accidental surrounding quotes from dashboard paste
    if (token.startswith('"') and token.endswith('"')) or (token.startswith("'") and token.endswith("'")):
        token = token[1:-1].strip()

    # Safe diagnostics (never print the full token)
    print(f"🔑 Using env var: {raw_name}")
    print(f"🔑 Token length: {len(token)} (typical bot tokens are ~59–72 chars)")
    if "." not in token:
        print("⚠️ Token has no '.' — Discord bot tokens usually look like: xxxxx.yyyyy.zzzzz")
    if token.lower().startswith("bot "):
        print("⚠️ Token starts with 'Bot ' — remove that prefix; pass only the raw token.")
        token = token[4:].strip()

    return token


def main():
    token = _load_token()

    # Only expose the lightweight keepalive server when the host provides a
    # web-service port. Background workers can run the bot without it.
    if os.getenv("PORT"):
        Thread(target=run_server, daemon=True).start()

    client.run(token)


if __name__ == "__main__":
    main()
