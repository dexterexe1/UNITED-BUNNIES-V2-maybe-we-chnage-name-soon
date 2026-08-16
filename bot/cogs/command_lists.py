"""Simple command directory commands for United Bunnies.

?commands      -> categorized list of all registered command names
?commandsinfo  -> flat list of every registered prefix/slash command name

Both are hybrid commands, so /commands and /commandsinfo also work.
"""
import discord
from discord.ext import commands

from bot.config import bot, style_embed, BRAND_COLOR, BRAND_EMOJI


def _all_command_names():
    """Return every registered prefix and slash command name, deduplicated."""
    names = set()

    # Prefix commands (including commands nested in command groups).
    for command in bot.walk_commands():
        if getattr(command, "hidden", False):
            continue
        name = getattr(command, "qualified_name", None) or getattr(command, "name", None)
        if name:
            names.add(name)

    # Application/slash commands, including slash command groups.
    try:
        for command in bot.tree.walk_commands():
            name = getattr(command, "qualified_name", None) or getattr(command, "name", None)
            if name:
                names.add(name)
    except Exception:
        pass

    return sorted(names, key=lambda value: value.lower())


def _category_for(command_name: str) -> str:
    root = command_name.split(" ", 1)[0].lower()
    mapping = {
        "ban": "🛡️ Moderation", "kick": "🛡️ Moderation", "timeout": "🛡️ Moderation",
        "warn": "🛡️ Moderation", "mute": "🛡️ Moderation", "unmute": "🛡️ Moderation",
        "purge": "🛡️ Moderation", "slowmode": "🛡️ Moderation", "mod": "🛡️ Moderation",
        "addrole": "🎭 Roles", "role": "🎭 Roles", "reactionrole": "🎭 Roles",
        "revenue": "💰 Revenue", "setrevenuechannel": "💰 Revenue",
        "clearrevenuechannel": "💰 Revenue",
        "play": "🎵 Music", "skip": "🎵 Music", "queue": "🎵 Music", "stop": "🎵 Music",
        "pause": "🎵 Music", "resume": "🎵 Music", "volume": "🎵 Music", "loop": "🎵 Music",
        "hug": "😂 Fun", "kiss": "😂 Fun", "slap": "😂 Fun", "pat": "😂 Fun", "ship": "😂 Fun",
        "owneronlymode": "👑 Developer", "lockbot": "👑 Developer", "devhelp": "👑 Developer",
        "developerhelp": "👑 Developer", "devcommands": "👑 Developer",
        "disablecommand": "👑 Developer", "disablecmd": "👑 Developer",
        "enablecommand": "👑 Developer", "enablecmd": "👑 Developer",
        "disabledcommands": "👑 Developer", "listdisabled": "👑 Developer",
        "togglenoprefix": "👑 Developer", "noprefixmode": "👑 Developer",
        "botstatus": "👑 Developer", "botinfo": "👑 Developer",
        "commands": "📚 General", "commandsinfo": "📚 General",
        "ai": "🤖 AI Manager", "aihelp": "🤖 AI Manager", "aiimportprice": "🤖 AI Manager", "aiimportrules": "🤖 AI Manager",
        "aiprice": "🤖 AI Manager", "airule": "🤖 AI Manager", "aiservice": "🤖 AI Manager", "aiconfig": "🤖 AI Manager", "aiclear": "🤖 AI Manager",
        "provideai": "👑 Developer", "disableai": "👑 Developer", "providenonprefix": "👑 Developer", "disablenonprefix": "👑 Developer",
        "aistatus": "👑 Developer", "ailist": "👑 Developer",
    }
    return mapping.get(root, "📦 Other")


def _chunk_lines(lines, max_chars=950):
    chunks, current, size = [], [], 0
    for line in lines:
        if current and size + len(line) + 1 > max_chars:
            chunks.append("\n".join(current))
            current, size = [], 0
        current.append(line)
        size += len(line) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks or ["No commands found."]


@bot.hybrid_command(
    name="commands",
    description="Show the bot's command names grouped by category.",
)
async def commands_list(ctx: commands.Context):
    names = _all_command_names()
    categories = {}
    for name in names:
        categories.setdefault(_category_for(name), []).append(name)

    embed = style_embed(
        title=f"{BRAND_EMOJI} United Bunnies Commands",
        description="All currently registered command names. No usage text — just the names.",
        color=BRAND_COLOR,
        kind="info",
    )

    for category in sorted(categories, key=lambda x: x.lower()):
        value = "\n".join(f"• `?{name}`" for name in categories[category])
        # Discord field values have a 1024-char limit.
        parts = _chunk_lines(value.splitlines(), 950)
        for index, part in enumerate(parts):
            field_name = category if index == 0 else f"{category} (continued)"
            embed.add_field(name=field_name, value=part, inline=False)

    embed.set_footer(text=f"{len(names)} registered command names • United Bunnies")
    await ctx.send(embed=embed)


@bot.hybrid_command(
    name="commandsinfo",
    description="Show every registered command name in the bot.",
)
async def commands_info(ctx: commands.Context):
    names = _all_command_names()
    lines = [f"• `?{name}`" for name in names]
    chunks = _chunk_lines(lines, 3500)

    for index, chunk in enumerate(chunks, start=1):
        title = f"{BRAND_EMOJI} All Commands" if len(chunks) == 1 else f"{BRAND_EMOJI} All Commands • {index}/{len(chunks)}"
        embed = style_embed(
            title=title,
            description=chunk,
            color=BRAND_COLOR,
            kind="info",
        )
        embed.set_footer(text=f"{len(names)} registered command names • United Bunnies")
        await ctx.send(embed=embed)
