"""
mongo_bridge.py — connects the bot to the SAME MongoDB the dashboard
(server.js) writes to, so settings changed on the website actually take
effect in Discord.

This is the missing link for the "Commands", "Custom Commands", and
"Auto Responder" dashboard tabs: previously the bot only ever sent data
TO the dashboard (via publish_bot_status). It never read anything back,
so toggling a command off, or creating a custom command / auto-response
on the website, had no real effect in the server.

Collections read here (same names/shapes server.js already writes):
  - commandCategories        [{ id, label, commands: [{ name, ... }] }]
  - guildCommandOverrides    { guildId, categoryId, commandName, enabled }
  - customCommands           { guildId, trigger, response, matchType,
                                replyType, enabled, deleteInvoke, cooldown,
                                requiredRole, uses }
  - autoResponses            { guildId, trigger, response, matchType,
                                caseSensitive, cooldown, deleteInvoke,
                                enabled, channels, uses }
  - welcomeSettings          { guildId, join: {enabled, channelName, message,
                                embed, imageUrl, thumbnailUrl, footer},
                                leave: {enabled, channelName, message} }

Everything is cached in memory and refreshed on a timer so message
handling never blocks on a network round trip. If MONGO_URI isn't set,
every lookup silently returns "not found / allowed" so the bot still
runs fine without a dashboard attached (e.g. local dev).
"""

import os
import re
import time
import datetime

try:
    from motor.motor_asyncio import AsyncIOMotorClient
except ImportError:  # motor not installed — bridge just stays disabled
    AsyncIOMotorClient = None

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "bunnydb")
REFRESH_SECONDS = 20

_client = None
_db = None

# --- in-memory caches, rebuilt every REFRESH_SECONDS ---
_disabled_commands: dict[int, set[str]] = {}          # guild_id -> {"category:command", ...}
_custom_commands: dict[int, list[dict]] = {}           # guild_id -> [command, ...]
_auto_responses: dict[int, list[dict]] = {}            # guild_id -> [response, ...]
_moderation_settings: dict[int, dict] = {}             # guild_id -> settings dict
_reaction_panels: dict[int, list[dict]] = {}            # guild_id -> [panel, ...]
_leveling_settings: dict[int, dict] = {}                # guild_id -> settings dict
_welcome_settings: dict[int, dict] = {}                 # guild_id -> settings dict
_application_forms: dict[int, list[dict]] = {}          # guild_id -> [application form, ...]
_last_refresh = 0.0

DEFAULT_LEVELING_SETTINGS = {
    "enabled": True,
    "xpMin": 5,
    "xpMax": 15,
    "cooldownSeconds": 60,
    "levelupChannelName": "",  # blank = post in the channel where the member leveled up
    "stackRoles": True,
    "roleRewards": [],  # [{"level": int, "roleName": str}, ...]
    "ignoredChannels": [],
    "ignoredRoles": [],
}

DEFAULT_WELCOME_SETTINGS = {
    "join": {
        "enabled": False,
        "channelName": "",
        "message": "Welcome {user} to **{server}**! We now have **{membercount}** members. 🐰",
        "embed": False,
        "imageUrl": "",
        "thumbnailUrl": "",
        "footer": "",
    },
    "leave": {
        "enabled": False,
        "channelName": "",
        "message": "{user} has left the server. We now have {membercount} members.",
    },
}

DEFAULT_MODERATION_SETTINGS = {
    "modRoleName": "",
    "muteRoleName": "Muted",
    "logChannelName": "",
    "automod": {
        "antiSpam": {"enabled": True, "maxMsgs": 5, "interval": 5, "action": "mute", "duration": 10},
        "wordFilter": {"enabled": True, "words": [], "action": "delete", "warnUser": True},
        "linkFilter": {"enabled": True, "mode": "blacklist", "whitelist": [], "blacklist": [], "action": "delete"},
        "capsLock": {"enabled": True, "threshold": 70, "minLength": 8, "action": "delete"},
        "massPing": {"enabled": True, "maxPings": 5, "action": "mute", "duration": 5},
        "newAccounts": {"enabled": False, "minAgeDays": 7, "action": "kick"},
        "invites": {"enabled": True, "allowOwn": True, "action": "delete"},
        "emojiSpam": {"enabled": False, "maxEmojis": 10, "action": "delete"},
        "dupMessages": {"enabled": False, "threshold": 3, "action": "delete"},
    },
    "ignoredRoles": [],
    "ignoredChannels": [],
}

# per-(guild, trigger-key) cooldown tracking, kept in-process (mirrors the
# dashboard's per-command "cooldown" field)
_cooldown_until: dict[tuple, float] = {}


def enabled() -> bool:
    return _client is not None


async def connect():
    """Call once, e.g. from on_ready. No-op if MONGO_URI is unset or
    motor isn't installed — the bot keeps working without dashboard sync."""
    global _client, _db
    if not MONGO_URI:
        print("ℹ️ MONGO_URI not set — dashboard sync (commands/auto-responses) disabled.")
        return
    if AsyncIOMotorClient is None:
        print("⚠️ motor is not installed — run `pip install motor` to enable dashboard sync.")
        return
    try:
        _client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=8000)
        _db = _client[MONGO_DB]
        await _db.command("ping")
        print(f"✅ Connected to dashboard MongoDB ({MONGO_DB}) — commands/auto-responses will sync.")
        await refresh()
    except Exception as e:
        print(f"❌ Could not connect to dashboard MongoDB: {e}")
        _client = None
        _db = None


async def refresh_loop():
    while True:
        await refresh()
        await __import__("asyncio").sleep(REFRESH_SECONDS)


async def refresh():
    """Pull the latest command overrides / custom commands / auto-responses
    for every guild the dashboard has data for, and rebuild the caches."""
    global _last_refresh
    if _db is None:
        return
    try:
        categories = await _db["commandCategories"].find().to_list(length=None)
        overrides = await _db["guildCommandOverrides"].find().to_list(length=None)
        customs = await _db["customCommands"].find().to_list(length=None)
        autos = await _db["autoResponses"].find().to_list(length=None)
        moderation = await _db["moderationSettings"].find().to_list(length=None)
        panels = await _db["reactionRolePanels"].find().to_list(length=None)
        leveling = await _db["levelingSettings"].find().to_list(length=None)
        welcome = await _db["welcomeSettings"].find().to_list(length=None)
        application_forms = await _db["applicationForms"].find().to_list(length=None)

        # Build a set of every (category:command) pair that DEFAULTS to
        # enabled, so we only need to track the ones explicitly disabled.
        new_disabled: dict[int, set[str]] = {}
        for o in overrides:
            if o.get("enabled") is False:
                gid = int(o["guildId"])
                key = f"{o['categoryId']}:{o['commandName']}"
                new_disabled.setdefault(gid, set()).add(key)

        new_customs: dict[int, list[dict]] = {}
        for c in customs:
            if not c.get("enabled", True):
                continue
            gid = int(c["guildId"])
            new_customs.setdefault(gid, []).append(c)

        new_autos: dict[int, list[dict]] = {}
        for a in autos:
            if not a.get("enabled", True):
                continue
            gid = int(a["guildId"])
            new_autos.setdefault(gid, []).append(a)

        new_moderation: dict[int, dict] = {}
        for m in moderation:
            gid = int(m["guildId"])
            new_moderation[gid] = _deep_merge_defaults(DEFAULT_MODERATION_SETTINGS, m)

        new_panels: dict[int, list[dict]] = {}
        for p in panels:
            gid = int(p["guildId"])
            new_panels.setdefault(gid, []).append(p)

        new_leveling: dict[int, dict] = {}
        for l in leveling:
            gid = int(l["guildId"])
            new_leveling[gid] = _deep_merge_defaults(DEFAULT_LEVELING_SETTINGS, l)

        new_welcome: dict[int, dict] = {}
        for w in welcome:
            gid = int(w["guildId"])
            new_welcome[gid] = _deep_merge_defaults(DEFAULT_WELCOME_SETTINGS, w)

        new_application_forms: dict[int, list[dict]] = {}
        for af in application_forms:
            gid = int(af["guildId"])
            new_application_forms.setdefault(gid, []).append(af)

        global _disabled_commands, _custom_commands, _auto_responses, _moderation_settings, _reaction_panels, _leveling_settings, _welcome_settings, _application_forms
        _disabled_commands = new_disabled
        _custom_commands = new_customs
        _auto_responses = new_autos
        _moderation_settings = new_moderation
        _reaction_panels = new_panels
        _leveling_settings = new_leveling
        _welcome_settings = new_welcome
        _application_forms = new_application_forms
        _last_refresh = time.time()
    except Exception as e:
        print(f"⚠️ mongo_bridge refresh failed: {e}")


def _deep_merge_defaults(defaults: dict, override: dict) -> dict:
    """Fills in any field missing from `override` (e.g. a guild saved before
    a new automod filter was added) with the matching value from `defaults`."""
    out = dict(defaults)
    for key, value in override.items():
        if key == "_id" or key == "guildId":
            continue
        if isinstance(value, dict) and isinstance(defaults.get(key), dict):
            out[key] = _deep_merge_defaults(defaults[key], value)
        else:
            out[key] = value
    return out


def get_moderation_settings(guild_id: int) -> dict:
    return _moderation_settings.get(guild_id, DEFAULT_MODERATION_SETTINGS)


def is_ignored(guild_id: int, member, channel) -> bool:
    """True if this member/channel should be exempt from automod entirely."""
    settings = get_moderation_settings(guild_id)
    channel_name = getattr(channel, "name", "")
    if channel_name and channel_name in settings.get("ignoredChannels", []):
        return True
    ignored_roles = {r.lower() for r in settings.get("ignoredRoles", [])}
    if ignored_roles and any(r.name.lower() in ignored_roles for r in getattr(member, "roles", [])):
        return True
    return False


def is_command_disabled(guild_id: int, command_name: str) -> bool:
    """True only if the dashboard has an explicit disable for this command
    in ANY category (categoryId isn't known at the call site, and command
    names are unique across categories in the seeded catalog)."""
    if not enabled():
        return False
    keys = _disabled_commands.get(guild_id)
    if not keys:
        return False
    return any(k.endswith(f":{command_name}") for k in keys)


def _member_has_required_role(member, required_role: str) -> bool:
    if not required_role or required_role.lower() == "everyone":
        return True
    return any(r.name.lower() == required_role.lower() for r in getattr(member, "roles", []))


def _matches(trigger: str, content: str, match_type: str, case_sensitive: bool = False) -> bool:
    t, c = trigger, content
    if not case_sensitive:
        t, c = t.lower(), c.lower()
    try:
        if match_type == "exact":
            return c == t
        if match_type == "contains":
            return t in c
        if match_type == "startsWith":
            return c.startswith(t)
        if match_type == "endsWith":
            return c.endswith(t)
        if match_type == "regex":
            return re.search(trigger, content, 0 if case_sensitive else re.IGNORECASE) is not None
    except re.error:
        return False
    return False


def _on_cooldown(guild_id: int, item_id: str, cooldown: int, user_id: int) -> bool:
    if not cooldown:
        return False
    key = (guild_id, item_id, user_id)
    until = _cooldown_until.get(key, 0)
    now = time.time()
    if now < until:
        return True
    _cooldown_until[key] = now + cooldown
    return False


def substitute_variables(text: str, *, member, guild, channel) -> str:
    now = datetime.datetime.now()
    replacements = {
        "{user}": member.mention,
        "{user.name}": member.display_name,
        "{user.id}": str(member.id),
        "{author}": member.display_name,
        "{server}": guild.name,
        "{membercount}": str(guild.member_count or 0),
        "{channel}": channel.mention if hasattr(channel, "mention") else f"#{channel}",
        "{prefix}": "?",
        "{date}": now.strftime("%Y-%m-%d"),
        "{time}": now.strftime("%H:%M:%S"),
        "{random}": str(__import__("random").randint(1, 100)),
        "{bot}": guild.me.display_name if guild.me else "Bot",
    }
    for token, value in replacements.items():
        text = text.replace(token, value)
    return text


def find_custom_command(guild_id: int, message):
    """Returns the matching dashboard-configured custom command dict for
    this message, or None. Does NOT apply cooldown/role gating — call
    check_and_consume_custom_command for the full check.

    The bot prefix ("?") is stripped from the raw message before matching so
    that triggers saved in the dashboard WITHOUT the prefix (e.g. "hello world")
    correctly fire when a user types "?hello world" in Discord.
    """
    BOT_PREFIX = "?"
    content = message.content.strip()
    if content.startswith(BOT_PREFIX):
        content = content[len(BOT_PREFIX):]
    for cmd in _custom_commands.get(guild_id, []):
        if _matches(cmd.get("trigger", ""), content, cmd.get("matchType", "exact")):
            return cmd
    return None


def check_and_consume_custom_command(guild_id: int, message):
    """Full check: match + role gate + cooldown. Returns the command dict
    if it should fire (and marks the cooldown as consumed), else None."""
    cmd = find_custom_command(guild_id, message)
    if not cmd:
        return None
    if not _member_has_required_role(message.author, cmd.get("requiredRole", "everyone")):
        return None
    if _on_cooldown(guild_id, str(cmd.get("_id", cmd.get("trigger"))), cmd.get("cooldown", 0), message.author.id):
        return None
    return cmd


def check_and_consume_auto_response(guild_id: int, message):
    content = message.content.strip()
    channel_name = getattr(message.channel, "name", "")
    for item in _auto_responses.get(guild_id, []):
        channels = item.get("channels", "all")
        if channels and channels != "all" and channels.lower() != channel_name.lower():
            continue
        if _matches(item.get("trigger", ""), content, item.get("matchType", "contains"), item.get("caseSensitive", False)):
            if _on_cooldown(guild_id, str(item.get("_id", item.get("trigger"))), item.get("cooldown", 0), message.author.id):
                return None
            return item
    return None


async def bump_uses(collection: str, doc_id) -> None:
    if _db is None or doc_id is None:
        return
    try:
        from bson import ObjectId
        await _db[collection].update_one({"_id": ObjectId(str(doc_id))}, {"$inc": {"uses": 1}})
    except Exception:
        pass  # best-effort; never let a stats update break the bot


def get_leveling_settings(guild_id: int) -> dict:
    return _leveling_settings.get(guild_id, DEFAULT_LEVELING_SETTINGS)


def get_welcome_settings(guild_id: int) -> dict:
    return _welcome_settings.get(guild_id, DEFAULT_WELCOME_SETTINGS)


def is_leveling_ignored(guild_id: int, member, channel) -> bool:
    settings = get_leveling_settings(guild_id)
    channel_name = getattr(channel, "name", "")
    if channel_name and channel_name in settings.get("ignoredChannels", []):
        return True
    ignored_roles = {r.lower() for r in settings.get("ignoredRoles", [])}
    if ignored_roles and any(r.name.lower() in ignored_roles for r in getattr(member, "roles", [])):
        return True
    return False


async def push_leaderboard(guild_id: int, entries: list[dict]) -> None:
    """Bot -> dashboard, one-way: writes a leaderboard snapshot so the
    website can display it without needing a live query into the bot's
    SQLite database. `entries` is a list of
    {userId, username, avatarUrl, xp, level}, already sorted highest first."""
    if _db is None:
        return
    try:
        await _db["guildLeaderboards"].update_one(
            {"guildId": str(guild_id)},
            {"$set": {"guildId": str(guild_id), "entries": entries, "updatedAt": time.time()}},
            upsert=True,
        )
    except Exception as e:
        print(f"⚠️ mongo_bridge: failed to push leaderboard for guild {guild_id}: {e}")


def get_reaction_panels(guild_id: int) -> list[dict]:
    return _reaction_panels.get(guild_id, [])


def get_unposted_panels(guild_id: int) -> list[dict]:
    """Panels the dashboard created that the bot hasn't posted to Discord yet."""
    return [p for p in _reaction_panels.get(guild_id, []) if not p.get("messageId")]


def find_panel_by_message(guild_id: int, message_id: int) -> dict | None:
    for p in _reaction_panels.get(guild_id, []):
        if str(p.get("messageId")) == str(message_id):
            return p
    return None


def find_mapping(panel: dict, emoji_key: str) -> dict | None:
    for m in panel.get("mappings", []):
        if m.get("emoji") == emoji_key:
            return m
    return None


async def mark_panel_posted(panel_id, message_id: int) -> None:
    """Called right after the bot actually sends a panel message, so future
    refreshes (and the dashboard) know it's live and stop re-posting it."""
    if _db is None:
        return
    try:
        from bson import ObjectId
        await _db["reactionRolePanels"].update_one(
            {"_id": ObjectId(str(panel_id))}, {"$set": {"messageId": str(message_id)}}
        )
        # Reflect the change in the in-memory cache immediately so the
        # refresh loop doesn't try to re-post it before its next tick.
        for panels in _reaction_panels.values():
            for p in panels:
                if str(p.get("_id")) == str(panel_id):
                    p["messageId"] = str(message_id)
    except Exception as e:
        print(f"⚠️ mongo_bridge: failed to mark panel {panel_id} as posted: {e}")


# --- Application Forms API ---

def get_application_forms(guild_id: int) -> list[dict]:
    """Return all application forms for a guild."""
    return _application_forms.get(guild_id, [])


def get_unposted_application_forms(guild_id: int) -> list[dict]:
    """Application forms the dashboard created that the bot hasn't posted to Discord yet."""
    return [af for af in _application_forms.get(guild_id, []) if not af.get("messageId")]


def find_application_form_by_message(guild_id: int, message_id: int) -> dict | None:
    """Find an application form by its deployed message ID."""
    for af in _application_forms.get(guild_id, []):
        if str(af.get("messageId")) == str(message_id):
            return af
    return None


def find_application_form_by_id(guild_id: int, form_id: str) -> dict | None:
    """Find an application form by its MongoDB _id."""
    for af in _application_forms.get(guild_id, []):
        if str(af.get("_id")) == str(form_id):
            return af
    return None


async def mark_application_form_deployed(form_id, message_id: int) -> None:
    """Called right after the bot sends an application panel message, so future
    refreshes (and the dashboard) know it's live and stop re-posting it."""
    if _db is None:
        return
    try:
        from bson import ObjectId
        await _db["applicationForms"].update_one(
            {"_id": ObjectId(str(form_id))}, {"$set": {"messageId": str(message_id)}}
        )
        # Reflect the change in the in-memory cache immediately.
        for forms in _application_forms.values():
            for af in forms:
                if str(af.get("_id")) == str(form_id):
                    af["messageId"] = str(message_id)
    except Exception as e:
        print(f"⚠️ mongo_bridge: failed to mark application form {form_id} as deployed: {e}")

# mongo_bridge.py
async def get_guild_settings(guild_id: int):
    if _db is None: return {}
    return await _db["guilds"].find_one({"guildId": str(guild_id)}, {"_id": 0}) or {}

async def update_guild_settings(guild_id: int, updates: dict):
    if _db is None: return
    await _db["guilds"].update_one(
        {"guildId": str(guild_id)},
        {"$set": updates, "$setOnInsert": {"guildId": str(guild_id)}},
        upsert=True
    )
