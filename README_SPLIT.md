# Discord Bot — Modular Structure

Original ~4400-line monolith split into smaller modules. **Command logic unchanged.**

## Layout

```
artifacts/
├── run_bot.py                 # launcher → bot.main
├── requirements.txt
├── bot_data.db
├── bot_monolith_original.py   # full original backup
└── bot/
    ├── main.py                # entry point
    ├── config.py              # bot instance, intents, constants, quick_embed
    ├── database.py            # all SQLite helpers + init_db
    ├── status.py              # keepalive + publish_bot_status
    ├── checks.py              # global command permission check
    ├── events.py              # on_ready, on_message, join/leave, logs
    ├── mongo_bridge.py        # dashboard Mongo sync
    └── cogs/
        ├── music.py
        ├── tickets.py
        ├── reaction_roles.py
        ├── marriage.py
        ├── moderation.py      # prefix mod tools + ?bon
        ├── vouch.py
        ├── applications.py
        ├── community.py       # help, panel, setup, announce, leveling, noprefix
        └── mod_slash.py       # /mod group, cmdperm, custom commands, enable/disable
```

## Bug fixed

`enable_feature()` had a leftover `return rows` where `rows` was never defined. Removed.

## Original issue (still noted)

`on_ready` referenced `RoleMenuView` which was **never defined** in the original file. Registration is optional so the bot still starts.

## Run

```bash
cd artifacts
# with DISCORD_TOKEN / BOT_TOKEN set:
python run_bot.py
# or:
python -m bot.main
```

Fallback to original if needed:

```bash
python bot_monolith_original.py
```

## Verified

- All modules import cleanly
- 61 prefix/hybrid commands register
- ~63 app/slash tree commands register
