from bot.ui.premium_cards import quick_card_view, style_card_view, embed_to_view
"""
mod_slash.py — /mod slash group, cmdperm-*, custom commands, enable/disable.
Extracted from the original monolithic bot.py. Logic unchanged.
"""
import discord
from discord.ext import commands
import discord.app_commands as app_commands
import datetime

from bot.config import bot, quick_embed, UTC, mod_group, has_required_slash_role, staff_check
from bot.cogs.community import build_help_home_embed, HelpView
from bot.database import (
    set_config, get_config,
    set_welcome_message, clear_welcome_message, format_welcome_message,
    set_levelup_channel, clear_levelup_channel, set_leveling_enabled,
    set_trusted_role_id, clear_trusted_role_id,
    grant_noprefix, revoke_noprefix, list_noprefix_users, get_trusted_role_id,
    update_warnings, get_warnings, reset_warnings,
    add_command_permission, remove_command_permission,
    list_command_permissions, reset_command_permissions,
    add_custom_command, remove_custom_command, list_custom_commands,
    disable_feature, enable_feature,
)


@mod_group.command(name="setup", description="🤖 Launch interactive dropdown configuration dashboards.")
@has_required_slash_role()
async def setup_slash(interaction: discord.Interaction):
    await interaction.response.send_message(
        embed=discord.Embed(
            title="🛠️ Server Configuration Dashboard",
            description="Use the commands in `/mod help` to configure moderation, welcome, leveling, logs, and no-prefix settings. The dashboard link is available from the bot help menu.",
        ),
        view=HelpView(),
        ephemeral=True,
    )

@mod_group.command(name="help", description="🔨 View the Administrative Enforcement Deck.")
@has_required_slash_role()
async def mod_help_slash(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🔨 Administrative Staff Enforcement Deck", 
        description="Comprehensive matrix listing all available automated and manual system tools:",
        color=discord.Color.orange()
    )
    
    embed.add_field(
        name="`⚙️ Configuration Modules`", 
        value=(
            "• `/mod setup` — Launches the interactive dropdown UI config dashboard.\n"
            "• `/mod setwelcome <channel>` — Manually routes member join greeting embeds.\n"
            "• `/mod setwelcomemessage <text>` / `/mod clearwelcomemessage` — Customize the greeting text.\n"
            "• `/mod setlogs <channel>` — Manually maps text edit and deletion tracking streams.\n"
            "• `/mod setlevelchannel <channel>` / `/mod clearlevelchannel` — Where level-ups get posted.\n"
            "• `/mod togglelevels <true/false>` — Turn the leveling/XP system on or off.\n"
            "• `/cmdperm-allow/deny/list/reset` — Restrict specific commands to specific roles.\n"
            "• `/new-command`, `/delete-command`, `/list-commands` — Custom auto-reply triggers.\n"
            "• `/mod panel` — Posts the interactive control panel (tickets, vouching, info, music, rank)."
        ), 
        inline=False
    )
    
    embed.add_field(
        name="`⚔️ Active Enforcement Parameters`", 
        value=(
            "• `/mod warn` or `?warn` / `?w` — Warn (auto-timeout at 3).\n"
            "• `/mod warnings` or `?warnings` / `?warns` — Check warns.\n"
            "• `/mod clearwarnings` or `?cw` / `?clearwarns` — Clear warns.\n"
            "• `/mod mute` or `?mute` / `?timeout` · `/mod unmute` or `?unmute`\n"
            "• `/mod kick` or `?kick` / `?k` · `/mod ban` or `?ban` / `?b`\n"
            "• `/mod unban` or `?unban` / `?ub` · `/mod clear <amount>`\n"
            "• `?reactionrole` / `?rr` — Reaction roles · `?bon` — Joke ban."
        ), 
        inline=False
    )

    embed.add_field(
        name="`📢 Public Server Broadcasts`", 
        value=(
            "• `?p [text]` — Generates the matrix announcement template with custom block structures.\n"
            "• `?ticketpanel` — Posts a standalone button for members to open support tickets."
        ), 
        inline=False
    )
    
    embed.add_field(
        name="`💰 Revenue Tracking`", 
        value=(
            "• `?setrevenuechannel #channel` — Enable automatic revenue tracking.\n"
            "• `?weekrevenue` / `?week` — Last 7 days report.\n"
            "• `?monthrevenue` / `?month` — Last 30 days report.\n"
            "• `?todayrevenue` / `?today` — Today's report.\n"
            "• `?allrevenue` — All-time report (Admin only).\n"
            "• `?revenuevia \"staff\"` — Specific staff member report.\n"
            "• `?revenuedetails [days]` — Transaction history.\n"
            "• `?revenuehelp` — Show format & setup guide."
        ), 
        inline=False
    )
    
    embed.add_field(
        name="`🎭 Role Information`", 
        value=(
            "• `?roles` — List all server roles.\n"
            "• `?roleinfo [@role]` — Show role with key permissions.\n"
            "• `?rolefullinfo @role` — Complete role details & permissions.\n"
            "• `?rolehelp` — Show help."
        ), 
        inline=False
    )
    
    embed.set_footer(text="Core Security Verification Required • Commands limited strictly to Authorization Role ID.")
    await interaction.response.send_message(view=embed_to_view(embed))

@mod_group.command(name="setwelcome", description="🎯 Set targeted greeting text channel updates.")
@has_required_slash_role()
async def setwelcome_slash(interaction: discord.Interaction, channel: discord.TextChannel):
    set_config(interaction.guild.id, "welcome", channel.id)
    await interaction.response.send_message(view=quick_card_view(f"🎯 **Welcome channel mapped:** {channel.mention}"))

@mod_group.command(name="setlogs", description="🎯 Target channel for message edit/deletion logs.")
@has_required_slash_role()
async def setlogs_slash(interaction: discord.Interaction, channel: discord.TextChannel):
    set_config(interaction.guild.id, "logs", channel.id)
    await interaction.response.send_message(view=quick_card_view(f"🎯 **Log channel mapped:** {channel.mention}"))

@mod_group.command(name="setwelcomemessage", description="👋 Customize the welcome message sent to new members.")
@has_required_slash_role()
@app_commands.describe(message="Use {user}, {username}, {server}, {membercount} as placeholders")
async def setwelcomemessage_slash(interaction: discord.Interaction, message: str):
    set_welcome_message(interaction.guild.id, message)
    preview = format_welcome_message(message, interaction.user)
    embed = discord.Embed(
        title="👋 Welcome Message Updated",
        description=f"**Preview:**\n{preview}",
        color=discord.Color.green(),
    )
    embed.set_footer(text="Placeholders: {user} {username} {server} {membercount}")
    await interaction.response.send_message(view=embed_to_view(embed))

@mod_group.command(name="clearwelcomemessage", description="👋 Reset the welcome message back to the default.")
@has_required_slash_role()
async def clearwelcomemessage_slash(interaction: discord.Interaction):
    clear_welcome_message(interaction.guild.id)
    await interaction.response.send_message(view=quick_card_view("✅ Welcome message reset to the default."))

@mod_group.command(name="setlevelchannel", description="📈 Set the channel where level-up announcements are posted.")
@has_required_slash_role()
async def setlevelchannel_slash(interaction: discord.Interaction, channel: discord.TextChannel):
    set_levelup_channel(interaction.guild.id, channel.id)
    await interaction.response.send_message(view=quick_card_view(f"📈 **Level-up announcements will now post in:** {channel.mention}"))

@mod_group.command(name="clearlevelchannel", description="📈 Post level-ups in whichever channel the user leveled up in.")
@has_required_slash_role()
async def clearlevelchannel_slash(interaction: discord.Interaction):
    clear_levelup_channel(interaction.guild.id)
    await interaction.response.send_message(view=quick_card_view("✅ Level-up announcements will post in the channel the member was chatting in."))

@mod_group.command(name="togglelevels", description="📈 Turn the leveling/XP system on or off for this server.")
@has_required_slash_role()
@app_commands.describe(enabled="True to enable XP gain, False to disable it")
async def togglelevels_slash(interaction: discord.Interaction, enabled: bool):
    set_leveling_enabled(interaction.guild.id, enabled)
    status = "enabled ✅" if enabled else "disabled ❌"
    await interaction.response.send_message(view=quick_card_view(f"📈 Leveling system is now **{status}** in this server."))

@mod_group.command(name="clear", description="🗑️ Purge text streams from active channels.")
@has_required_slash_role()
async def clear_slash(interaction: discord.Interaction, amount: int):
    await interaction.response.defer(ephemeral=True)
    await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🗑️ Wiped {amount} messages.", ephemeral=True)

@mod_group.command(name="setnoprefixrole", description="🔓 Set a role whose members can use commands without the ? prefix.")
@has_required_slash_role()
async def set_noprefix_role_slash(interaction: discord.Interaction, role: discord.Role):
    set_trusted_role_id(interaction.guild.id, role.id)
    await interaction.response.send_message(
        f"🔓 **No-prefix role set:** anyone with {role.mention} can now run any command without typing `?` first.\n"
        f"⚠️ Moderation commands (ban/kick/mute/warn/etc.) will still ask for confirmation before running.",
    )

@mod_group.command(name="clearnoprefixrole", description="🔒 Remove the no-prefix trusted role.")
@has_required_slash_role()
async def clear_noprefix_role_slash(interaction: discord.Interaction):
    clear_trusted_role_id(interaction.guild.id)
    await interaction.response.send_message(view=quick_card_view("🔒 No-prefix trusted role cleared."))

@mod_group.command(name="grantnoprefix", description="🔓 Let a specific user run commands without the ? prefix.")
@has_required_slash_role()
async def grant_noprefix_slash(interaction: discord.Interaction, member: discord.Member):
    grant_noprefix(interaction.guild.id, member.id)
    await interaction.response.send_message(view=quick_card_view(f"🔓 {member.mention} can now use bot commands without the `?` prefix."))

@mod_group.command(name="revokenoprefix", description="🔒 Remove a user's individual no-prefix permission.")
@has_required_slash_role()
async def revoke_noprefix_slash(interaction: discord.Interaction, member: discord.Member):
    removed = revoke_noprefix(interaction.guild.id, member.id)
    if removed:
        await interaction.response.send_message(view=quick_card_view(f"🔒 {member.mention}'s no-prefix permission was removed."))
    else:
        await interaction.response.send_message(view=quick_card_view(f"❗ {member.mention} didn't have an individual no-prefix grant (they may still have it via a role)."), ephemeral=True)

@mod_group.command(name="listnoprefix", description="📋 List users individually granted no-prefix permission.")
@has_required_slash_role()
async def list_noprefix_slash(interaction: discord.Interaction):
    user_ids = list_noprefix_users(interaction.guild.id)
    trusted_id = get_trusted_role_id(interaction.guild.id)
    lines = []
    if trusted_id:
        role = interaction.guild.get_role(trusted_id)
        lines.append(f"**Trusted role:** {role.mention if role else '*(deleted role)*'}")
    if user_ids:
        mentions = ", ".join(f"<@{uid}>" for uid in user_ids)
        lines.append(f"**Individually granted:** {mentions}")
    if not lines:
        lines.append("No no-prefix role or individual grants configured yet.")
    embed = discord.Embed(title="🔓 No-Prefix Permissions", description="\n\n".join(lines), color=discord.Color.blurple())
    await interaction.response.send_message(view=embed_to_view(embed))

@mod_group.command(name="warn", description="⚠️ Issue a manual warning to a member.")
@has_required_slash_role()
async def warn_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    current = update_warnings(member.id, 1)
    embed = discord.Embed(
        title="⚠️ Warning Issued",
        description=f"{member.mention} has been warned by {interaction.user.mention}.\n__**Reason:**__ {reason}\n__**Total warnings:**__ {current}/3",
        color=discord.Color.orange(),
    )
    await interaction.response.send_message(view=embed_to_view(embed))
    if current >= 3:
        reset_warnings(member.id)
        try:
            await member.timeout(datetime.timedelta(minutes=10), reason="Reached 3 warnings")
            await interaction.followup.send(f"🤫 **{member.display_name}** has been auto-timed out for 10 minutes after reaching 3 warnings.")
        except discord.Forbidden:
            await interaction.followup.send("⚠️ Reached 3 warnings, but I don't have permission to timeout that user.")

@mod_group.command(name="warnings", description="📋 Check a member's current warning count.")
@has_required_slash_role()
async def warnings_slash(interaction: discord.Interaction, member: discord.Member):
    count = get_warnings(member.id)
    await interaction.response.send_message(view=quick_card_view(f"📋 **{member.display_name}** currently has **{count}/3** warnings."))

@mod_group.command(name="clearwarnings", description="✅ Reset a member's warning count to zero.")
@has_required_slash_role()
async def clearwarnings_slash(interaction: discord.Interaction, member: discord.Member):
    reset_warnings(member.id)
    await interaction.response.send_message(view=quick_card_view(f"✅ Cleared all warnings for **{member.display_name}**."))

@mod_group.command(name="mute", description="🤫 Timeout a member for a number of minutes.")
@has_required_slash_role()
async def mute_slash(interaction: discord.Interaction, member: discord.Member, minutes: int = 10, reason: str = "No reason provided"):
    minutes = max(1, min(40320, minutes))
    try:
        await member.timeout(datetime.timedelta(minutes=minutes), reason=f"{reason} (by {interaction.user})")
    except discord.Forbidden:
        await interaction.response.send_message(view=quick_card_view("❌ I don't have permission to timeout that user."), ephemeral=True)
        return
    embed = discord.Embed(
        title="🤫 Member Muted",
        description=f"{member.mention} has been muted for **{minutes} minute(s)**.\n__**Reason:**__ {reason}",
        color=discord.Color.orange(),
    )
    await interaction.response.send_message(view=embed_to_view(embed))

@mod_group.command(name="unmute", description="🔊 Remove a member's timeout.")
@has_required_slash_role()
async def unmute_slash(interaction: discord.Interaction, member: discord.Member):
    try:
        await member.timeout(None, reason=f"Unmuted by {interaction.user}")
    except discord.Forbidden:
        await interaction.response.send_message(view=quick_card_view("❌ I don't have permission to unmute that user."), ephemeral=True)
        return
    await interaction.response.send_message(view=quick_card_view(f"🔊 **{member.display_name}** has been unmuted."))

@mod_group.command(name="kick", description="👢 Kick a member from the server.")
@has_required_slash_role()
async def kick_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message(view=quick_card_view("❌ You can't kick someone with an equal or higher role than you."), ephemeral=True)
        return
    try:
        await member.kick(reason=f"{reason} (by {interaction.user})")
    except discord.Forbidden:
        await interaction.response.send_message(view=quick_card_view("❌ I don't have permission to kick that user."), ephemeral=True)
        return
    embed = discord.Embed(title="👢 Member Kicked", description=f"**{member}** was kicked.\n__**Reason:**__ {reason}", color=discord.Color.orange())
    await interaction.response.send_message(view=embed_to_view(embed))

@mod_group.command(name="ban", description="🔨 Ban a member from the server.")
@has_required_slash_role()
async def ban_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message(view=quick_card_view("❌ You can't ban someone with an equal or higher role than you."), ephemeral=True)
        return
    try:
        await member.ban(reason=f"{reason} (by {interaction.user})")
    except discord.Forbidden:
        await interaction.response.send_message(view=quick_card_view("❌ I don't have permission to ban that user."), ephemeral=True)
        return
    embed = discord.Embed(title="🔨 Member Banned", description=f"**{member}** was banned.\n__**Reason:**__ {reason}", color=discord.Color.red())
    await interaction.response.send_message(view=embed_to_view(embed))

@mod_group.command(name="unban", description="✅ Unban a user by ID.")
@has_required_slash_role()
async def unban_slash(interaction: discord.Interaction, user_id: str, reason: str = "No reason provided"):
    try:
        uid = int(user_id)
        user = await bot.fetch_user(uid)
        await interaction.guild.unban(user, reason=f"{reason} (by {interaction.user})")
    except ValueError:
        await interaction.response.send_message(view=quick_card_view("❌ That doesn't look like a valid user ID."), ephemeral=True)
        return
    except discord.NotFound:
        await interaction.response.send_message(view=quick_card_view("❌ That user isn't banned."), ephemeral=True)
        return
    except discord.Forbidden:
        await interaction.response.send_message(view=quick_card_view("❌ I don't have permission to unban."), ephemeral=True)
        return
    await interaction.response.send_message(view=quick_card_view(f"✅ Unbanned **{user}**."))


# ==========================================
#     🔐 PER-COMMAND ROLE PERMISSIONS (/cmdperm-*)
# ==========================================
# Lets staff restrict any prefix/hybrid command to one or more roles. A
# command with no restrictions configured stays open to everyone. Staff with
# proper Discord permissions can always use every command regardless of this table.

@bot.tree.command(name="cmdperm-allow", description="🔐 [Mod] Restrict a command to a specific role.")
@has_required_slash_role()
@app_commands.describe(command="Exact command name (e.g. 'play', 'ticket')", role="Role allowed to use it")
async def cmdperm_allow_slash(interaction: discord.Interaction, command: str, role: discord.Role):
    command = command.strip().lstrip("?/").lower()
    if bot.get_command(command) is None:
        await interaction.response.send_message(view=quick_card_view(f"❌ No command named `{command}` exists."), ephemeral=True)
        return
    add_command_permission(interaction.guild.id, command, role.id)
    await interaction.response.send_message(view=quick_card_view(f"🔐 `{command}` is now restricted to {role.mention} (and staff)."))

@bot.tree.command(name="cmdperm-deny", description="🔐 [Mod] Remove a role's access to a restricted command.")
@has_required_slash_role()
@app_commands.describe(command="Exact command name", role="Role to remove access from")
async def cmdperm_deny_slash(interaction: discord.Interaction, command: str, role: discord.Role):
    command = command.strip().lstrip("?/").lower()
    removed = remove_command_permission(interaction.guild.id, command, role.id)
    if removed:
        await interaction.response.send_message(view=quick_card_view(f"🔒 {role.mention} can no longer use `{command}` (unless another allowed role/staff)."))
    else:
        await interaction.response.send_message(view=quick_card_view(f"❗ {role.mention} wasn't specifically allowed for `{command}`."), ephemeral=True)

@bot.tree.command(name="cmdperm-list", description="🔐 Show which commands are restricted and to whom.")
@has_required_slash_role()
async def cmdperm_list_slash(interaction: discord.Interaction):
    perms = list_command_permissions(interaction.guild.id)
    if not perms:
        await interaction.response.send_message(view=quick_card_view("📋 No commands are currently restricted — everything is open to everyone (plus staff)."))
        return
    lines = []
    for cmd_name, role_ids in perms.items():
        mentions = ", ".join(f"<@&{rid}>" for rid in role_ids)
        lines.append(f"**?{cmd_name}** — {mentions}")
    embed = discord.Embed(title="🔐 Restricted Commands", description="\n".join(lines), color=discord.Color.blurple())
    embed.set_footer(text="Staff (the required role) can always use every command.")
    await interaction.response.send_message(view=embed_to_view(embed))

@bot.tree.command(name="cmdperm-reset", description="🔐 [Mod] Clear all role restrictions on a command.")
@has_required_slash_role()
@app_commands.describe(command="Exact command name to fully unrestrict")
async def cmdperm_reset_slash(interaction: discord.Interaction, command: str):
    command = command.strip().lstrip("?/").lower()
    changed = reset_command_permissions(interaction.guild.id, command)
    if changed:
        await interaction.response.send_message(view=quick_card_view(f"✅ `{command}` is now open to everyone again."))
    else:
        await interaction.response.send_message(view=quick_card_view(f"❗ `{command}` had no restrictions to clear."), ephemeral=True)


# ==========================================
#   💬 CUSTOM AUTO-RESPONDER ("if someone types X, bot sends Y")
# ==========================================

@bot.tree.command(name="new-command", description="💬 [Mod] Make the bot auto-reply when someone types an exact phrase.")
@has_required_slash_role()
@app_commands.describe(trigger="Exact phrase that fires the response (not case-sensitive)", response="What the bot should send back")
async def new_command_slash(interaction: discord.Interaction, trigger: str, response: str):
    trigger_key = trigger.strip().lower()
    if not trigger_key:
        await interaction.response.send_message(view=quick_card_view("❌ Trigger can't be empty."), ephemeral=True)
        return
    add_custom_command(interaction.guild.id, trigger_key, response, interaction.user.id)
    embed = discord.Embed(
        title="💬 Custom Command Saved",
        description=f"When someone types:\n> {trigger}\n\nI'll reply with:\n> {response}",
        color=discord.Color.green(),
    )
    await interaction.response.send_message(view=embed_to_view(embed))

@bot.tree.command(name="delete-command", description="💬 [Mod] Remove a custom auto-responder trigger.")
@has_required_slash_role()
@app_commands.describe(trigger="The exact trigger phrase to remove")
async def delete_command_slash(interaction: discord.Interaction, trigger: str):
    removed = remove_custom_command(interaction.guild.id, trigger.strip().lower())
    if removed:
        await interaction.response.send_message(view=quick_card_view(f"🗑️ Removed the custom command for `{trigger}`."))
    else:
        await interaction.response.send_message(view=quick_card_view(f"❗ No custom command found for `{trigger}`."), ephemeral=True)

@bot.tree.command(name="list-commands", description="💬 List all custom auto-responder triggers in this server.")
@has_required_slash_role()
async def list_commands_slash(interaction: discord.Interaction):
    rows = list_custom_commands(interaction.guild.id)
    if not rows:
        await interaction.response.send_message(view=quick_card_view("📋 No custom commands set up yet. Use `/new-command` to add one."))
        return
    lines = [f"**{trig}** → {resp}" for trig, resp in rows[:25]]
    embed = discord.Embed(title="💬 Custom Commands", description="\n".join(lines), color=discord.Color.blurple())
    if len(rows) > 25:
        embed.set_footer(text=f"...and {len(rows) - 25} more.")
    await interaction.response.send_message(view=embed_to_view(embed))


@bot.hybrid_command(name="disable", description="[Staff] Disable a command/module from Discord")
@staff_check("admin")
@app_commands.describe(feature="Name of command or module", type="command or module")
async def disable_prefix(ctx, feature: str, type: str = "command"):
    feature = feature.lower()
    if type not in ["command", "module"]:
        return await ctx.send(view=quick_card_view("❌ Type must be 'command' or 'module'."))
    await disable_feature(ctx.guild.id, feature, type)
    await ctx.send(view=quick_card_view(f"🔒 **{feature}** ({type}) has been disabled for this server."))

@bot.hybrid_command(name="enable", description="[Staff] Enable a command/module from Discord")
@staff_check("admin")
@app_commands.describe(feature="Name of command or module", type="command or module")
async def enable_prefix(ctx, feature: str, type: str = "command"):
    feature = feature.lower()
    if type not in ["command", "module"]:
        return await ctx.send(view=quick_card_view("❌ Type must be 'command' or 'module'."))
    await enable_feature(ctx.guild.id, feature, type)
    await ctx.send(view=quick_card_view(f"✅ **{feature}** ({type}) has been enabled for this server."))
