"""
config.py — Core configuration, constants, intents, and shared helpers.
Extracted from the original monolithic bot.py. Logic unchanged.
"""
import os
import datetime
import discord
from discord.ext import commands
import discord.app_commands as app_commands
import requests
import random

UTC = datetime.timezone.utc

# --- CORE CONFIGURATION & INTENTS ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Setting the message prefix strictly to '?' for commands
bot = commands.Bot(command_prefix="?", intents=intents, help_command=None)

# --- TARGET ENFORCEMENT ROLE ID ---
REQUIRED_ROLE_ID = 1517514393141776506

BOT_STATUS_URL = os.getenv("BOT_STATUS_URL")
BOT_API_SECRET = os.getenv("BOT_API_SECRET")  # must match the dashboard's BOT_API_SECRET

# --- SUPPORT / DASHBOARD / INVITE LINKS ---
# Set these as environment variables on your host (Railway/Render/VPS/etc).
# Falling back to placeholders so the bot still boots if they're unset —
# update the placeholders below (or set the env vars) with your real links.
SUPPORT_SERVER_URL = os.getenv("SUPPORT_SERVER_URL", "https://discord.gg/YOUR_INVITE_CODE_HERE")
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "https://your-dashboard-website.example.com")
INVITE_URL = os.getenv(
    "INVITE_URL",
    "https://discord.com/oauth2/authorize?client_id=1517342359388426351&permissions=0&integration_type=0&scope=bot+applications.commands",
)

# --- BRAND COLOR ---
BRAND_COLOR = 0x7B68EE  # medium slate blue / purple


def quick_embed(text: str, *, title: str | None = None) -> discord.Embed:
    """Simple themed embed. Prefer style_embed() for the purple card look."""
    color = BRAND_COLOR
    if text.startswith(("❌", "❗", "🚫", "💔")):
        color = discord.Color.red().value
    elif text.startswith(("✅", "🎉", "🔓")):
        color = discord.Color.green().value
    elif text.startswith(("⚠️", "🤫", "🔒")):
        color = discord.Color.gold().value
    embed = discord.Embed(description=text, color=color, timestamp=datetime.datetime.now(UTC))
    if title:
        embed.title = title
    return embed


# Decorative markers (Unicode — swap for your server custom emojis anytime)
EMOJI_DIAMOND = "◆"       # title sides  (replace with <:name:id> if you have custom)
EMOJI_BULLET = "•"        # field bullets


def style_embed(
    title: str,
    *,
    description: str | None = None,
    fields: list[tuple[str, str, bool]] | None = None,
    color: int | None = None,
    footer: str | None = None,
    kind: str = "info",
) -> discord.Embed:
    """Purple card-style embed like:  ◆ ALL VOUCHES ◆

    kind: info | success | warn | error | mod
    fields: list of (name, value, inline)
    """
    colors = {
        "info": BRAND_COLOR,
        "success": 0x57F287,   # green
        "warn": 0xFEE75C,      # gold
        "error": 0xED4245,     # red
        "mod": 0x9B59B6,       # purple
    }
    c = color if color is not None else colors.get(kind, BRAND_COLOR)
    clean_title = title.strip()
    # Avoid double-decorating if already has diamonds
    if not (clean_title.startswith(EMOJI_DIAMOND) or clean_title.startswith("<:")):
        clean_title = f"{EMOJI_DIAMOND} {clean_title.upper()} {EMOJI_DIAMOND}"
    embed = discord.Embed(title=clean_title, color=c, timestamp=datetime.datetime.now(UTC))
    if description:
        embed.description = description
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
    if footer:
        embed.set_footer(text=footer)
    return embed


def is_staff(member: discord.Member, *, need: str = "mod") -> bool:
    """Option C: Discord permissions OR legacy REQUIRED_ROLE_ID OR trusted role.

    need:
      mod / warn / mute / clear → Moderate Members | Manage Messages | Kick
      kick → Kick Members
      ban → Ban Members
      admin → Manage Guild | Administrator
    """
    if member is None or not isinstance(member, discord.Member):
        return False
    perms = member.guild_permissions
    if perms.administrator:
        return True
    # Legacy hardcoded staff role still works
    if any(r.id == REQUIRED_ROLE_ID for r in member.roles):
        return True
    # Per-server trusted / mod role (from ?setnoprefixrole / DB)
    try:
        from bot.database import get_trusted_role_id
        trusted_id = get_trusted_role_id(member.guild.id)
        if trusted_id and any(r.id == trusted_id for r in member.roles):
            return True
    except Exception:
        pass

    need = (need or "mod").lower()
    if need in ("ban",):
        return bool(perms.ban_members)
    if need in ("kick",):
        return bool(perms.kick_members)
    if need in ("admin", "setup", "config"):
        return bool(perms.manage_guild or perms.manage_channels)
    # default mod actions
    return bool(
        perms.moderate_members
        or perms.manage_messages
        or perms.kick_members
        or perms.ban_members
    )


def staff_check(need: str = "mod"):
    """Prefix-command check: Discord perms + optional mod role (option C)."""
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is None:
            return False
        member = ctx.author
        if not isinstance(member, discord.Member):
            return False
        if is_staff(member, need=need):
            return True
        raise commands.CheckFailure(
            "❌ You need **mod permissions** (or the staff role) to use this command."
        )
    return commands.check(predicate)

# --- AUTOMOD INITIALIZATION PARAMETERS ---
# --- LEGACY AUTOMOD DEFAULTS ---
# No longer used directly — on_message now reads live thresholds/actions from
# mongo_bridge.get_moderation_settings() (populated from the dashboard). Left
# here only as a reference for the bundled defaults in mongo_bridge.py.
BANNED_WORDS = ["badword1", "badword2", "toxictext"]
MAX_EMOJIS = 5
MAX_PINGS = 4
CAPS_PERCENTAGE = 0.75

user_message_cooldowns = {}
afk_users = {}
_recent_messages = {}  # user_id -> list of recent lowercased message contents (for dupMessages filter)

# --- LEVELING SYSTEM CONFIG ---
# Global kill switch: set True only if you want built-in XP again.
LEVELING_SYSTEM_ENABLED = False
xp_cooldowns = {}  # user_id -> last xp grant timestamp
XP_COOLDOWN_SECONDS = 60
XP_MIN = 5
XP_MAX = 15

# --- TICKET SYSTEM CONFIG ---
TICKET_CATEGORY_NAME = "🎫 Tickets"

# --- MUSIC QUEUES ---
song_queues = {}
now_playing = {}      # guild_id -> currently playing track dict
song_volumes = {}     # guild_id -> float (0.0 - 2.0), default 1.0
loop_modes = {}        # guild_id -> "off" | "track" | "queue"

GIPHY_API_KEY = os.getenv("GIPHY_API_KEY") or os.getenv("GIPHY_KEY")


def fetch_giphy_gif_url(query: str):
    if not query:
        return None
    if not GIPHY_API_KEY:
        return None
    try:
        resp = requests.get(
            "https://api.giphy.com/v1/gifs/search",
            params={
                "q": query,
                "api_key": GIPHY_API_KEY,
                "limit": 30,
                "rating": "pg-13",
            },
            timeout=12,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("data") or []
        if not results:
            return None
        pick = random.choice(results)
        images = pick.get("images") or {}
        chosen = (
            images.get("original")
            or images.get("downsized_large")
            or images.get("fixed_height")
            or images.get("fixed_width")
        )
        if not chosen:
            return None
        return chosen.get("url")
    except Exception:
        return None


# Create the modern slash command group structure for '/mod'
mod_group = app_commands.Group(
    name="mod",
    description="🔨 Administrative Enforcement and Moderation commands deck."
)


# --- SLASH COMMAND STAFF CHECK (option C) ---
def has_required_slash_role(need: str = "mod"):
    """Slash check: Discord permissions OR staff/trusted role."""
    def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            return False
        member = interaction.user
        if not isinstance(member, discord.Member):
            return False
        return is_staff(member, need=need)
    return app_commands.check(predicate)
