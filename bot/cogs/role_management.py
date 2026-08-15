"""Role management commands — Dyno-style role creation helpers."""

import random
from typing import Optional

import discord
from discord.ext import commands
import discord.app_commands as app_commands

from bot.config import bot, style_embed, BRAND_COLOR, BRAND_EMOJI


NAMED_COLORS = {
    "red": discord.Color.red,
    "orange": discord.Color.orange,
    "yellow": discord.Color.yellow,
    "green": discord.Color.green,
    "blue": discord.Color.blue,
    "purple": discord.Color.purple,
    "pink": discord.Color.magenta,
    "magenta": discord.Color.magenta,
    "teal": discord.Color.teal,
    "cyan": lambda: discord.Color.from_rgb(0, 255, 255),
    "aqua": discord.Color.teal,
    "gold": discord.Color.gold,
    "darkred": discord.Color.dark_red,
    "darkgreen": discord.Color.dark_green,
    "darkblue": discord.Color.dark_blue,
    "darkpurple": discord.Color.dark_purple,
    "black": lambda: discord.Color.from_rgb(0, 0, 0),
    "white": lambda: discord.Color.from_rgb(255, 255, 255),
    "gray": discord.Color.light_grey,
    "grey": discord.Color.light_grey,
}


def random_role_color() -> discord.Color:
    """Pick a readable random role color."""
    # Avoid colors that are too close to Discord's default/no-color look.
    return discord.Color.from_rgb(
        random.randint(40, 240),
        random.randint(40, 240),
        random.randint(40, 240),
    )


def parse_role_color(value: Optional[str]) -> tuple[discord.Color, str]:
    """Return (color, display_text). Missing/random uses a generated color."""
    if not value or not value.strip() or value.strip().lower() == "random":
        return random_role_color(), "Randomly selected"

    raw = value.strip().lower()

    # #RRGGBB / RRGGBB / 0xRRGGBB
    if raw.startswith("#"):
        raw = raw[1:]
    elif raw.startswith("0x"):
        raw = raw[2:]

    if len(raw) == 6:
        try:
            rgb = int(raw, 16)
            return discord.Color(rgb), f"`#{raw.upper()}`"
        except ValueError:
            pass

    # rgb(r,g,b)
    if raw.startswith("rgb(") and raw.endswith(")"):
        parts = [p.strip() for p in raw[4:-1].split(",")]
        if len(parts) == 3:
            try:
                r, g, b = (int(p) for p in parts)
                if all(0 <= n <= 255 for n in (r, g, b)):
                    return discord.Color.from_rgb(r, g, b), f"`rgb({r}, {g}, {b})`"
            except ValueError:
                pass

    named = NAMED_COLORS.get(raw)
    if named:
        color = named()
        return color, f"`{raw}`"

    raise ValueError(
        "Invalid colour. Use a hex colour like `#5865F2`, a name like `blue`, "
        "`rgb(88,101,242)`, or leave it blank for a random colour."
    )


def role_manage_check():
    """Require Manage Roles, Administrator, or a configured bot owner."""
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is None or not isinstance(ctx.author, discord.Member):
            raise commands.CheckFailure("This command can only be used inside a server.")

        from bot.database import is_bot_owner

        perms = ctx.author.guild_permissions
        if perms.administrator or perms.manage_roles or is_bot_owner(ctx.author.id):
            return True

        raise commands.CheckFailure("❌ You need **Manage Roles** permission to use this command.")

    return commands.check(predicate)


@bot.hybrid_command(
    name="addrole",
    description="Create a new server role with a chosen or automatic colour.",
)
@role_manage_check()
@app_commands.describe(
    name="The name of the new role. Use quotes with the prefix command for spaces.",
    colour="Hex (#5865F2), colour name, RGB, or leave blank for a random colour.",
)
async def addrole(ctx: commands.Context, name: str, colour: Optional[str] = None):
    """Create a role, Dyno-style, with optional automatic colour selection."""
    name = name.strip()
    if not name:
        await ctx.send(
            embed=style_embed(
                title="❌ Invalid Role Name",
                description="Please provide a name for the new role.",
                kind="error",
            )
        )
        return

    if len(name) > 100:
        await ctx.send(
            embed=style_embed(
                title="❌ Invalid Role Name",
                description="Role names can be at most **100 characters**.",
                kind="error",
            )
        )
        return

    try:
        role_color, color_display = parse_role_color(colour)
    except ValueError as exc:
        await ctx.send(
            embed=style_embed(
                title="❌ Invalid Colour",
                description=str(exc),
                kind="error",
            )
        )
        return

    me = ctx.guild.me
    if me is None:
        try:
            me = ctx.guild.get_member(bot.user.id) if bot.user else None
        except Exception:
            me = None

    if me is None or not me.guild_permissions.manage_roles:
        await ctx.send(
            embed=style_embed(
                title="❌ Missing Permission",
                description="I need the **Manage Roles** permission to create roles.",
                kind="error",
            )
        )
        return

    # Discord places a newly-created role below the bot's highest role.
    # If the bot cannot manage roles at all, create_role will fail; catch that
    # cleanly instead of exposing a traceback to the user.
    try:
        role = await ctx.guild.create_role(
            name=name,
            colour=role_color,
            reason=f"Role created by {ctx.author} ({ctx.author.id}) via addrole",
        )
    except discord.Forbidden:
        await ctx.send(
            embed=style_embed(
                title="❌ Role Creation Failed",
                description=(
                    "I don't have permission to create roles here. "
                    "Make sure I have **Manage Roles** and my highest role is high enough."
                ),
                kind="error",
            )
        )
        return
    except discord.HTTPException as exc:
        await ctx.send(
            embed=style_embed(
                title="❌ Role Creation Failed",
                description=f"Discord rejected the request: `{exc}`",
                kind="error",
            )
        )
        return

    embed = style_embed(
        title=f"{BRAND_EMOJI} Role Created",
        description=f"Successfully created {role.mention}.",
        color=role_color.value or BRAND_COLOR,
        kind="success",
    )
    embed.add_field(name="Role", value=f"{role.mention}\n`{role.name}`", inline=True)
    embed.add_field(name="Colour", value=color_display, inline=True)
    embed.add_field(name="Created By", value=ctx.author.mention, inline=True)
    embed.set_footer(text="United Bunnies • Role Management")

    await ctx.send(embed=embed)
