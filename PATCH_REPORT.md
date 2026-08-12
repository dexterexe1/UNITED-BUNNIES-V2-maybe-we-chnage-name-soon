# United Bunnies V2 — Debug Patch Report

Patched from the uploaded ZIP.

## Critical fixes
- Added the missing `get_custom_command` import used by `events.on_message`.
- Added missing imports in tickets (`asyncio`, `re`), moderation (`random`), music (`datetime`), reaction roles (`re`), and community (`random`, `re`, `requests`, GIPHY helpers, vouch helpers, AFK state).
- Added missing dashboard/application imports (`aiohttp`, dashboard URL/secret, ticket helpers, leveling helpers, vouch modal, music state).
- Fixed `database.has_noprefix_perm()` so `REQUIRED_ROLE_ID` is actually available.
- Replaced the broken `/mod setup` reference to nonexistent `SetupDashboardView` with the working help/dashboard view.
- Prevented repeated slash-command registration and duplicated background loops when Discord fires `on_ready` again after reconnects.

## Important remaining upgrade opportunities
- Move all blocking SQLite operations and `requests.get()` calls off the Discord event loop.
- Replace repeated `asyncio`/status tasks with `discord.ext.tasks.loop` and centralized lifecycle management.
- Add structured logging and exception tracebacks instead of sending raw exception strings to users.
- Add command cooldowns and rate limiting for public network-backed commands.
- Add persistent state migration/versioning for SQLite.
- Add tests for moderation, reaction roles, applications, and dashboard synchronization.
- Replace the hard-coded staff role/client IDs with environment variables or per-guild configuration where appropriate.
