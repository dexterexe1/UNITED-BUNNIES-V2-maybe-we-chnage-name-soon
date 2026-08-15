"""
bot_control.py — Advanced Bot Control System
- Owner-only mode
- Command disable system (per-server and global)
- No-prefix system toggle
- Bot lockdown features
"""
import discord
from discord.ext import commands
import discord.app_commands as app_commands
from typing import Optional

from bot.config import bot, style_embed, BRAND_COLOR, BRAND_EMOJI
from bot.database import (
    is_feature_disabled, disable_feature, enable_feature,
    add_bot_owner, remove_bot_owner, is_bot_owner, get_bot_owners,
    is_owner_only_mode, set_owner_only_mode, is_noprefix_enabled, set_noprefix_enabled
)

# ==========================================
#         OWNER-ONLY MODE SYSTEM
# ==========================================

async def owner_only_check(ctx):
    """Check if bot is in owner-only mode and if user is authorized."""
    if not is_owner_only_mode():
        return True  # Owner-only mode disabled, allow all
    
    # Check if user is a bot owner
    if is_bot_owner(ctx.author.id):
        return True
    
    # Not authorized
    await ctx.send(
        embed=style_embed(
            title="🔒 Bot Locked",
            description=f"This bot is currently in **Owner-Only Mode**.\n"
                       f"Only authorized owners can use commands.",
            kind="error"
        ),
        delete_after=10
    )
    return False


async def command_enabled_check(ctx):
    """Check if command is disabled for this server or globally."""
    command_name = ctx.command.name if ctx.command else None
    if not command_name:
        return True
    
    # Check global disable
    if await is_feature_disabled(0, command_name, 'command'):
        await ctx.send(
            embed=style_embed(
                title="❌ Command Disabled",
                description=f"The command `{command_name}` has been **globally disabled** by the bot owner.",
                kind="error"
            ),
            delete_after=10
        )
        return False
    
    # Check server-specific disable
    if ctx.guild and await is_feature_disabled(ctx.guild.id, command_name, 'command'):
        await ctx.send(
            embed=style_embed(
                title="❌ Command Disabled",
                description=f"The command `{command_name}` has been disabled in this server.",
                kind="error"
            ),
            delete_after=10
        )
        return False
    
    return True


# ==========================================
#         BOT OWNER MANAGEMENT
# ==========================================

@bot.command(name="addowner", help="Add a bot owner (current owners only)")
async def add_owner_cmd(ctx: commands.Context, user: discord.User):
    """Add a new bot owner."""
    # Check if command issuer is a bot owner
    if not is_bot_owner(ctx.author.id):
        await ctx.send(
            embed=style_embed(
                title="❌ Unauthorized",
                description="Only existing bot owners can add new owners.",
                kind="error"
            )
        )
        return
    
    # Check if user is already an owner
    if is_bot_owner(user.id):
        await ctx.send(
            embed=style_embed(
                title="ℹ️ Already Owner",
                description=f"{user.mention} is already a bot owner.",
                kind="info"
            )
        )
        return
    
    # Add owner
    add_bot_owner(user.id, user.name)
    
    embed = style_embed(
        title=f"{BRAND_EMOJI} Owner Added",
        description=f"✅ {user.mention} has been added as a bot owner.\n"
                   f"They now have full control over the bot.",
        kind="success"
    )
    await ctx.send(embed=embed)


@bot.command(name="removeowner", help="Remove a bot owner (owners only)")
async def remove_owner_cmd(ctx: commands.Context, user: discord.User):
    """Remove a bot owner."""
    # Check if command issuer is a bot owner
    if not is_bot_owner(ctx.author.id):
        await ctx.send(
            embed=style_embed(
                title="❌ Unauthorized",
                description="Only bot owners can remove owners.",
                kind="error"
            )
        )
        return
    
    # Can't remove yourself if you're the only owner
    owners = get_bot_owners()
    if len(owners) == 1 and is_bot_owner(user.id):
        await ctx.send(
            embed=style_embed(
                title="❌ Cannot Remove",
                description="You cannot remove the last bot owner. Add another owner first.",
                kind="error"
            )
        )
        return
    
    # Remove owner
    if remove_bot_owner(user.id):
        embed = style_embed(
            title=f"{BRAND_EMOJI} Owner Removed",
            description=f"✅ {user.mention} has been removed as a bot owner.",
            kind="success"
        )
    else:
        embed = style_embed(
            title="ℹ️ Not an Owner",
            description=f"{user.mention} is not a bot owner.",
            kind="info"
        )
    
    await ctx.send(embed=embed)


@bot.command(name="listowners", help="List all bot owners")
async def list_owners_cmd(ctx: commands.Context):
    """List all bot owners."""
    owners = get_bot_owners()
    
    if not owners:
        description = "No bot owners have been set yet.\n\nUse `?addowner @user` to add one."
    else:
        description = "**Bot Owners:**\n\n"
        for owner_id, owner_name in owners:
            user = bot.get_user(owner_id)
            if user:
                description += f"• {user.mention} (`{user.name}`)\n"
            else:
                description += f"• {owner_name} (ID: `{owner_id}`)\n"
    
    embed = style_embed(
        title=f"{BRAND_EMOJI} Bot Owners",
        description=description,
        color=BRAND_COLOR,
        kind="info"
    )
    
    await ctx.send(embed=embed)


# ==========================================
#         OWNER-ONLY MODE TOGGLE
# ==========================================

@bot.command(name="owneronlymode", aliases=["lockbot"], help="Toggle owner-only mode (owners only)")
async def owner_only_mode_cmd(ctx: commands.Context, enabled: Optional[bool] = None):
    """Enable/disable owner-only mode."""
    # Check if command issuer is a bot owner
    if not is_bot_owner(ctx.author.id):
        await ctx.send(
            embed=style_embed(
                title="❌ Unauthorized",
                description="Only bot owners can toggle owner-only mode.",
                kind="error"
            )
        )
        return
    
    # Toggle if not specified
    if enabled is None:
        enabled = not is_owner_only_mode()
    
    set_owner_only_mode(enabled)
    
    if enabled:
        embed = style_embed(
            title="🔒 Owner-Only Mode Enabled",
            description="The bot is now **locked**.\n\n"
                       "Only authorized bot owners can use commands.\n"
                       "All other users will be denied access.",
            kind="success"
        )
    else:
        embed = style_embed(
            title="🔓 Owner-Only Mode Disabled",
            description="The bot is now **unlocked**.\n\n"
                       "All users can use commands normally (subject to permission checks).",
            kind="success"
        )
    
    await ctx.send(embed=embed)


# ==========================================
#         COMMAND DISABLE SYSTEM
# ==========================================

@bot.command(name="disablecommand", aliases=["disablecmd"], help="Disable a command globally or per-server (owners only)")
async def disable_command_cmd(ctx: commands.Context, command_name: str, scope: str = "server"):
    """Disable a command globally or in this server."""
    # Check if command issuer is a bot owner (global) or admin (server)
    if scope.lower() == "global":
        if not is_bot_owner(ctx.author.id):
            await ctx.send(
                embed=style_embed(
                    title="❌ Unauthorized",
                    description="Only bot owners can disable commands globally.",
                    kind="error"
                )
            )
            return
        guild_id = 0
        scope_text = "globally"
    else:
        if not ctx.guild:
            await ctx.send(embed=style_embed(title="❌ Error", description="This command must be used in a server.", kind="error"))
            return
        if not ctx.author.guild_permissions.administrator:
            await ctx.send(
                embed=style_embed(
                    title="❌ Unauthorized",
                    description="Only server administrators can disable commands in this server.",
                    kind="error"
                )
            )
            return
        guild_id = ctx.guild.id
        scope_text = "in this server"
    
    # Check if command exists
    if not bot.get_command(command_name):
        await ctx.send(
            embed=style_embed(
                title="❌ Unknown Command",
                description=f"Command `{command_name}` does not exist.",
                kind="error"
            )
        )
        return
    
    # Disable the command
    await disable_feature(guild_id, command_name, 'command')
    
    embed = style_embed(
        title=f"{BRAND_EMOJI} Command Disabled",
        description=f"✅ Command `{command_name}` has been disabled **{scope_text}**.",
        kind="success"
    )
    
    await ctx.send(embed=embed)


@bot.command(name="enablecommand", aliases=["enablecmd"], help="Re-enable a disabled command (owners/admins)")
async def enable_command_cmd(ctx: commands.Context, command_name: str, scope: str = "server"):
    """Re-enable a previously disabled command."""
    # Check permissions
    if scope.lower() == "global":
        if not is_bot_owner(ctx.author.id):
            await ctx.send(
                embed=style_embed(
                    title="❌ Unauthorized",
                    description="Only bot owners can enable commands globally.",
                    kind="error"
                )
            )
            return
        guild_id = 0
        scope_text = "globally"
    else:
        if not ctx.guild:
            await ctx.send(embed=style_embed(title="❌ Error", description="This command must be used in a server.", kind="error"))
            return
        if not ctx.author.guild_permissions.administrator:
            await ctx.send(
                embed=style_embed(
                    title="❌ Unauthorized",
                    description="Only server administrators can enable commands in this server.",
                    kind="error"
                )
            )
            return
        guild_id = ctx.guild.id
        scope_text = "in this server"
    
    # Enable the command
    await enable_feature(guild_id, command_name, 'command')
    
    embed = style_embed(
        title=f"{BRAND_EMOJI} Command Enabled",
        description=f"✅ Command `{command_name}` has been re-enabled **{scope_text}**.",
        kind="success"
    )
    
    await ctx.send(embed=embed)


@bot.command(name="disabledcommands", aliases=["listdisabled"], help="List all disabled commands")
async def list_disabled_commands(ctx: commands.Context):
    """List all disabled commands for this server and globally."""
    from bot.database import list_disabled_features
    
    # Get global disabled commands
    global_disabled = list_disabled_features(0, 'command')
    
    # Get server disabled commands
    server_disabled = []
    if ctx.guild:
        server_disabled = list_disabled_features(ctx.guild.id, 'command')
    
    description = ""
    
    if global_disabled:
        description += "**🌐 Globally Disabled:**\n"
        for cmd in global_disabled:
            description += f"• `{cmd}`\n"
        description += "\n"
    
    if server_disabled:
        description += f"**🏠 Disabled in This Server:**\n"
        for cmd in server_disabled:
            description += f"• `{cmd}`\n"
        description += "\n"
    
    if not global_disabled and not server_disabled:
        description = "No commands are currently disabled."
    
    embed = style_embed(
        title=f"{BRAND_EMOJI} Disabled Commands",
        description=description,
        color=BRAND_COLOR,
        kind="info"
    )
    
    await ctx.send(embed=embed)


# ==========================================
#         NO-PREFIX SYSTEM TOGGLE
# ==========================================

@bot.command(name="togglenoprefix", aliases=["noprefixmode"], help="Enable/disable no-prefix system (owners only)")
async def toggle_noprefix_cmd(ctx: commands.Context, enabled: Optional[bool] = None):
    """Toggle the no-prefix command system globally."""
    # Check if command issuer is a bot owner
    if not is_bot_owner(ctx.author.id):
        await ctx.send(
            embed=style_embed(
                title="❌ Unauthorized",
                description="Only bot owners can toggle the no-prefix system.",
                kind="error"
            )
        )
        return
    
    # Toggle if not specified
    if enabled is None:
        enabled = not is_noprefix_enabled()
    
    set_noprefix_enabled(enabled)
    
    if enabled:
        embed = style_embed(
            title="✅ No-Prefix System Enabled",
            description="The no-prefix command system is now **active**.\n\n"
                       "Users with no-prefix permission can run commands without `?`",
            kind="success"
        )
    else:
        embed = style_embed(
            title="❌ No-Prefix System Disabled",
            description="The no-prefix command system is now **disabled**.\n\n"
                       "All users must use `?` prefix for commands.",
            kind="info"
        )
    
    await ctx.send(embed=embed)


@bot.command(name="botstatus", aliases=["botinfo"], help="Show bot control status")
async def bot_status_cmd(ctx: commands.Context):
    """Show current bot control settings."""
    owners = get_bot_owners()
    owner_mode = is_owner_only_mode()
    noprefix_mode = is_noprefix_enabled()
    
    description = ""
    
    # Owner-only mode
    if owner_mode:
        description += "🔒 **Owner-Only Mode:** `ENABLED`\n"
        description += "   Only bot owners can use commands\n\n"
    else:
        description += "🔓 **Owner-Only Mode:** `DISABLED`\n"
        description += "   All users can use commands\n\n"
    
    # No-prefix system
    if noprefix_mode:
        description += "✅ **No-Prefix System:** `ENABLED`\n"
        description += "   Trusted users can run commands without `?`\n\n"
    else:
        description += "❌ **No-Prefix System:** `DISABLED`\n"
        description += "   All users must use `?` prefix\n\n"
    
    # Bot owners
    description += f"👑 **Bot Owners:** `{len(owners)}`\n"
    if owners:
        for owner_id, owner_name in owners[:3]:  # Show first 3
            user = bot.get_user(owner_id)
            if user:
                description += f"   • {user.mention}\n"
        if len(owners) > 3:
            description += f"   • ... and {len(owners) - 3} more\n"
    
    embed = style_embed(
        title=f"{BRAND_EMOJI} Bot Control Status",
        description=description,
        color=BRAND_COLOR,
        kind="info"
    )
    
    embed.set_footer(text="United Bunnies Bot Control System")
    
    await ctx.send(embed=embed)


# ==========================================
#         COMMAND CHECK HOOKS
# ==========================================

# Register checks globally
@bot.check
async def global_command_checks(ctx):
    """Global checks that run before every command."""
    # Check owner-only mode
    if not await owner_only_check(ctx):
        return False
    
    # Check if command is disabled
    if not await command_enabled_check(ctx):
        return False
    
    return True
