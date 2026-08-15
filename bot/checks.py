"""
checks.py — Global command permission checks and related helpers.
Extracted from the original monolithic bot.py. Logic unchanged.
"""
import discord
from discord.ext import commands

from bot.config import bot, BOT_OWNER_IDS, is_staff
from bot.database import (
    is_feature_disabled,
    get_command_permission_roles,
)
from bot import mongo_bridge

# Commands with no configured roles stay open to everyone (opt-in restriction
# model). Staff with proper Discord permissions always bypass restrictions.
# Applies to every prefix/hybrid command; pure app_commands.Group commands
# (like /mod ...) already gate on the staff role.
CMDPERM_EXEMPT_COMMANDS = {"cmdperm-allow", "cmdperm-deny", "cmdperm-list", "cmdperm-reset", "help"}


@bot.check
async def global_command_permission_check(ctx: commands.Context) -> bool:
    if ctx.guild is None or ctx.command is None:
        return True

    cmd_name = ctx.command.qualified_name.split(" ")[0]

    # 1. Check SQLite: Discord /disable command toggles
    if await is_feature_disabled(ctx.guild.id, cmd_name, 'command'):
        raise commands.CheckFailure("🔒 This command has been disabled via Discord.")

    # 2. Check MongoDB: Dashboard toggles (your existing mongo_bridge function)
    if mongo_bridge.is_command_disabled(ctx.guild.id, cmd_name):
        raise commands.CheckFailure("🔒 This command has been disabled on the dashboard for this server.")

    # 3. Check role-based permissions (your existing logic)
    allowed_roles = get_command_permission_roles(ctx.guild.id, cmd_name)
    if not allowed_roles:
        return True

    member = ctx.author
    if isinstance(member, discord.Member):
        # Bot owners bypass everything
        if member.id in BOT_OWNER_IDS:
            return True
        # Staff with proper permissions bypass
        if is_staff(member):
            return True
        # Check if user has allowed role
        if any(r.id in allowed_roles for r in member.roles):
            return True

    raise commands.CheckFailure("🔒 This command is restricted to specific roles here.")
