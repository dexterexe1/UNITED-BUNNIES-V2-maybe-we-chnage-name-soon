from bot.ui.premium_cards import quick_card_view, style_card_view
"""
applications.py — Application form system.
Extracted from the original monolithic bot.py. Logic unchanged.
"""
import discord
from discord.ext import commands
import discord.app_commands as app_commands
import asyncio
import datetime
import aiohttp

from bot.config import (
    bot, style_embed, UTC, has_required_slash_role, mod_group,
    now_playing, staff_check,
    BOT_API_SECRET, DASHBOARD_URL,
)
from bot import mongo_bridge
from bot.database import get_level_data, xp_for_level, get_open_ticket_for_user
from bot.cogs.tickets import open_new_ticket
from bot.cogs.community import VouchModal, make_progress_bar

class ApplicationModal(discord.ui.Modal, title="Application Form"):
    def __init__(self, form_data: dict):
        super().__init__(title=form_data.get("name", "Application"))
        self.form_data = form_data
        self.answers: list[dict] = []

        # Create TextInput fields for each question
        for q in sorted(form_data.get("questions", []), key=lambda x: x.get("order", 0)):
            q_type = q.get("type", "short_text")
            required = q.get("required", True)

            if q_type == "short_text":
                input_field = discord.ui.TextInput(
                    label=q.get("title", "Question"),
                    placeholder=q.get("description", "") or None,
                    required=required,
                    max_length=1000,
                    custom_id=q.get("id"),
                )
            elif q_type == "paragraph":
                input_field = discord.ui.TextInput(
                    label=q.get("title", "Question"),
                    placeholder=q.get("description", "") or None,
                    required=required,
                    style=discord.TextStyle.paragraph,
                    max_length=2000,
                    custom_id=q.get("id"),
                )
            elif q_type == "yes_no":
                # For yes/no, we use a short text that accepts yes/no
                input_field = discord.ui.TextInput(
                    label=q.get("title", "Question"),
                    placeholder="Yes or No",
                    required=required,
                    max_length=10,
                    custom_id=q.get("id"),
                )
            else:
                # Default to short_text
                input_field = discord.ui.TextInput(
                    label=q.get("title", "Question"),
                    placeholder=q.get("description", "") or None,
                    required=required,
                    max_length=1000,
                    custom_id=q.get("id"),
                )

            setattr(self, f"question_{q.get('id', 'default')}", input_field)
            self.add_item(input_field)

    async def on_submit(self, interaction: discord.Interaction):
        # Collect answers
        for q in self.form_data.get("questions", []):
            q_id = q.get("id", "default")
            try:
                answer_value = getattr(self, f"question_{q_id}", None)
                if answer_value:
                    self.answers.append({
                        "questionId": q_id,
                        "value": str(answer_value.value),
                    })
            except AttributeError:
                pass

        # Submit to dashboard API
        headers = {"x-bot-secret": BOT_API_SECRET} if BOT_API_SECRET else {}
        payload = {
            "formId": str(self.form_data.get("_id", "")),
            "applicant": {
                "discordUserId": str(interaction.user.id),
                "username": interaction.user.name,
                "globalName": interaction.user.global_name,
                "avatar": str(interaction.user.avatar.key) if interaction.user.avatar else None,
            },
            "answers": self.answers,
        }

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                api_url = DASHBOARD_URL.rstrip("/") + "/api/v1/guilds/" + str(interaction.guild.id) + "/applications/submissions"
                async with session.post(api_url, json=payload, headers=headers) as resp:
                    if resp.status == 201:
                        embed = discord.Embed(
                            description="✅ Your application has been submitted successfully!",
                            color=discord.Color.green(),
                        )
                        await interaction.response.send_message(embed=embed, ephemeral=True)
                    else:
                        error_text = await resp.text()
                        embed = discord.Embed(
                            description=f"❌ Failed to submit application: {resp.status}",
                            color=discord.Color.red(),
                        )
                        await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                description=f"❌ Error submitting application: {e}",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        embed = discord.Embed(
            description=f"❌ An error occurred while submitting your application: {error}",
            color=discord.Color.red(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ApplicationPanelView(discord.ui.View):
    def __init__(self, form_data: dict):
        super().__init__(timeout=None)
        self.form_data = form_data

        button_config = form_data.get("button", {})
        button_style_map = {
            "primary": discord.ButtonStyle.primary,
            "secondary": discord.ButtonStyle.secondary,
            "success": discord.ButtonStyle.success,
            "danger": discord.ButtonStyle.danger,
        }

        # Create the actual button dynamically from form config
        apply_button = discord.ui.Button(
            label=button_config.get("label", "Apply Now"),
            style=button_style_map.get(button_config.get("style", "primary"), discord.ButtonStyle.primary),
            emoji=button_config.get("emoji"),
            custom_id=f"app_apply_{form_data.get('_id', '')}",
        )
        
        # The callback will be handled by on_interaction event listener
        self.add_item(apply_button)


class ApplicationReviewView(discord.ui.View):
    def __init__(self, submission_id: str, form_id: str):
        super().__init__(timeout=None)
        self.submission_id = submission_id
        self.form_id = form_id

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, emoji="✅", custom_id="app_accept", row=0)
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        headers = {"x-bot-secret": BOT_API_SECRET} if BOT_API_SECRET else {}
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                api_url = DASHBOARD_URL.rstrip("/") + "/api/v1/guilds/" + str(interaction.guild.id) + "/applications/submissions/" + self.submission_id + "/status"
                async with session.patch(api_url, json={"status": "accepted"}, headers=headers) as resp:
                    if resp.status == 200:
                        await interaction.response.send_message(view=quick_card_view("✅ Application marked as accepted."), ephemeral=True)
                    else:
                        await interaction.response.send_message(view=quick_card_view(f"❌ Failed to update status: {resp.status}"), ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(view=quick_card_view(f"❌ Error: {e}"), ephemeral=True)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger, emoji="❌", custom_id="app_reject", row=0)
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        headers = {"x-bot-secret": BOT_API_SECRET} if BOT_API_SECRET else {}
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                api_url = DASHBOARD_URL.rstrip("/") + "/api/v1/guilds/" + str(interaction.guild.id) + "/applications/submissions/" + self.submission_id + "/status"
                async with session.patch(api_url, json={"status": "rejected"}, headers=headers) as resp:
                    if resp.status == 200:
                        await interaction.response.send_message(view=quick_card_view("❌ Application marked as rejected."), ephemeral=True)
                    else:
                        await interaction.response.send_message(view=quick_card_view(f"❌ Failed to update status: {resp.status}"), ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(view=quick_card_view(f"❌ Error: {e}"), ephemeral=True)


@bot.tree.command(name="deploy-application", description="📝 [Mod] Deploy an application form panel to a channel.")
@has_required_slash_role()
@app_commands.describe(form_id="The ID of the application form to deploy", channel="The channel to post the panel in")
async def deploy_application_slash(interaction: discord.Interaction, form_id: str, channel: discord.TextChannel):
    # Find the application form
    form_data = mongo_bridge.find_application_form_by_id(interaction.guild.id, form_id)
    if not form_data:
        await interaction.response.send_message(view=quick_card_view(f"❌ Application form not found."), ephemeral=True)
        return

    # Build the embed from form config
    embed_config = form_data.get("embed", {})
    embed = discord.Embed(
        title=embed_config.get("title") or form_data.get("name", "Application"),
        description=embed_config.get("description") or form_data.get("description", ""),
        color=int(embed_config.get("color", "5865F2").lstrip("#"), 16) if embed_config.get("color") else discord.Color.blurple(),
    )
    if embed_config.get("footer"):
        embed.set_footer(text=embed_config["footer"])

    # Create the view with the apply button
    view = ApplicationPanelView(form_data)

    # Send the panel message
    msg = await channel.send(embed=embed, view=view)

    # Mark the form as deployed in MongoDB
    await mongo_bridge.mark_application_form_deployed(form_id, msg.id)

    embed_success = discord.Embed(
        description=f"✅ Application panel deployed to {channel.mention}",
        color=discord.Color.green(),
    )
    embed_success.add_field(name="Message ID", value=str(msg.id), inline=False)
    await interaction.response.send_message(embed=embed_success, ephemeral=True)


@bot.tree.command(name="application-forms", description="📝 List all application forms for this server.")
@has_required_slash_role()
async def application_forms_slash(interaction: discord.Interaction):
    forms = mongo_bridge.get_application_forms(interaction.guild.id)
    if not forms:
        await interaction.response.send_message(view=quick_card_view("📋 No application forms configured yet."), ephemeral=True)
        return

    lines = []
    for form in forms[:10]:
        status_emoji = {"draft": "📝", "active": "✅", "archived": "🗄️"}.get(form.get("status", "draft"), "📝")
        deployed = "✅" if form.get("messageId") else "❌"
        lines.append(f"{status_emoji} **{form.get('name', 'Unnamed')}** — Deployed: {deployed}")

    embed = discord.Embed(title="📝 Application Forms", description="\n".join(lines), color=discord.Color.blurple())
    if len(forms) > 10:
        embed.set_footer(text=f"...and {len(forms) - 10} more.")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.event
async def on_interaction(interaction: discord.Interaction):
    # Handle application form button clicks
    if interaction.type == discord.InteractionType.component and interaction.data.get("custom_id", "").startswith("app_apply_"):
        form_id = interaction.data["custom_id"].replace("app_apply_", "", 1)
        form_data = mongo_bridge.find_application_form_by_id(interaction.guild.id, form_id)
        if not form_data:
            await interaction.response.send_message(view=quick_card_view("❌ This application form no longer exists."), ephemeral=True)
            return

        if form_data.get("status") != "active":
            await interaction.response.send_message(view=quick_card_view("❌ This application form is not currently accepting submissions."), ephemeral=True)
            return

        # Check if user already has a pending submission
        headers = {"x-bot-secret": BOT_API_SECRET} if BOT_API_SECRET else {}
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                api_url = DASHBOARD_URL.rstrip("/") + "/api/v1/guilds/" + str(interaction.guild.id) + "/applications/submissions?formId=" + form_id
                async with session.get(api_url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        submissions = data.get("submissions", [])
                        for sub in submissions:
                            if sub.get("applicant", {}).get("discordUserId") == str(interaction.user.id):
                                if sub.get("status") in ["pending", "reviewing"]:
                                    await interaction.response.send_message(
                                        view=quick_card_view("❗ You already have a pending application for this form."),
                                        ephemeral=True,
                                    )
                                    return
        except Exception:
            pass  # Continue even if we can't check

        modal = ApplicationModal(form_data)
        await interaction.response.send_modal(modal)
        return

    # Continue with default interaction handling
    pass


class ControlPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Ticket", style=discord.ButtonStyle.primary, emoji="🎫", custom_id="panel_open_ticket", row=0)
    async def ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        existing = get_open_ticket_for_user(interaction.guild.id, interaction.user.id)
        if existing:
            channel = interaction.guild.get_channel(existing)
            if channel:
                await interaction.response.send_message(view=quick_card_view(f"❗ You already have an open ticket: {channel.mention}"), ephemeral=True)
                return
        await interaction.response.send_message(view=quick_card_view("🎫 Creating your ticket..."), ephemeral=True)
        channel = await open_new_ticket(interaction.guild, interaction.user)
        await interaction.followup.send(f"✅ Ticket created: {channel.mention}", ephemeral=True)

    @discord.ui.button(label="Vouch Someone", style=discord.ButtonStyle.success, emoji="✅", custom_id="panel_vouch", row=0)
    async def vouch_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VouchModal())

    @discord.ui.button(label="Server Info", style=discord.ButtonStyle.secondary, emoji="📊", custom_id="panel_serverinfo", row=0)
    async def serverinfo_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        g = interaction.guild
        embed = discord.Embed(title=f"Server Info: {g.name}", color=0x2f3136, timestamp=datetime.datetime.now(UTC))
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        embed.add_field(name="ID", value=str(g.id), inline=True)
        embed.add_field(name="Owner", value=g.owner.mention if g.owner else "-", inline=True)
        embed.add_field(name="Members", value=str(g.member_count), inline=True)
        embed.add_field(name="Channels", value=str(len(g.channels)), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Now Playing", style=discord.ButtonStyle.secondary, emoji="🎵", custom_id="panel_nowplaying", row=1)
    async def nowplaying_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        current = now_playing.get(interaction.guild.id)
        if not current:
            await interaction.response.send_message(view=quick_card_view("❌ Nothing is currently playing."), ephemeral=True)
            return
        embed = discord.Embed(
            title="🎶 Now Playing",
            description=f"**[{current['title']}]({current['url']})**\n⏱️ Duration: `{current['duration']}`",
            color=0x2f3136,
        )
        if current.get("thumbnail"):
            embed.set_thumbnail(url=current["thumbnail"])
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="My Rank", style=discord.ButtonStyle.secondary, emoji="📈", custom_id="panel_rank", row=1)
    async def rank_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        xp, level = get_level_data(interaction.guild.id, interaction.user.id)
        needed_for_next = xp_for_level(level + 1)
        needed_for_current = xp_for_level(level)
        progress = xp - needed_for_current
        span = needed_for_next - needed_for_current
        bar = make_progress_bar(progress, span)
        embed = discord.Embed(title=f"📈 Rank — {interaction.user.display_name}", color=discord.Color.blurple())
        embed.add_field(name="Level", value=str(level), inline=True)
        embed.add_field(name="Total XP", value=str(xp), inline=True)
        embed.add_field(name="Progress", value=f"`{bar}` {progress}/{span} XP", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.hybrid_command(name="panel", description="[Staff] Post the interactive control panel")
@staff_check("admin")
async def control_panel_prefix(ctx):
    embed = discord.Embed(
        title="🕹️ Server Control Panel",
        description=(
            "Use the buttons below for quick access to common actions:\n\n"
            "🎫 **Open Ticket** — start a private conversation with staff\n"
            "✅ **Vouch Someone** — leave reputation feedback for a member\n"
            "📊 **Server Info** — see stats about this server\n"
            "🎵 **Now Playing** — check the current music track\n"
            "📈 **My Rank** — check your level and XP"
        ),
        color=0x2f3136,
    )
    embed.set_footer(text="🐰 United Bunnies System Active ✨")
    await ctx.send(embed=embed, view=ControlPanelView())

@mod_group.command(name="panel", description="🕹️ Post the interactive server control panel.")
@has_required_slash_role()
async def control_panel_slash(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🕹️ Server Control Panel",
        description=(
            "Use the buttons below for quick access to common actions:\n\n"
            "🎫 **Open Ticket** — start a private conversation with staff\n"
            "✅ **Vouch Someone** — leave reputation feedback for a member\n"
            "📊 **Server Info** — see stats about this server\n"
            "🎵 **Now Playing** — check the current music track\n"
            "📈 **My Rank** — check your level and XP"
        ),
        color=0x2f3136,
    )
    embed.set_footer(text="🐰 United Bunnies System Active ✨")
    await interaction.response.send_message(embed=embed, view=ControlPanelView())



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

@bot.command(name="addrevenuemanager", aliases=["addrmanager"], help="Add a revenue manager (current managers only)")
async def add_revenue_manager_cmd(ctx: commands.Context, user: discord.User):
    """Add a new revenue manager."""
    # Check if command issuer is a revenue manager
    if not is_bot_owner(ctx.author.id):
        await ctx.send(
            embed=style_embed(
                title="❌ Unauthorized",
                description="Only existing revenue managers can add new managers.",
                kind="error"
            )
        )
        return
    
    # Check if user is already a manager
    if is_bot_owner(user.id):
        await ctx.send(
            embed=style_embed(
                title="ℹ️ Already Manager",
                description=f"{user.mention} is already a revenue manager.",
                kind="info"
            )
        )
        return
    
    # Add manager
    add_bot_owner(user.id, user.name)
    
    embed = style_embed(
        title=f"{BRAND_EMOJI} Revenue Manager Added",
        description=f"✅ {user.mention} has been added as a revenue manager.\n"
                   f"They can now access revenue reports and manage the system.",
        kind="success"
    )
    await ctx.send(embed=embed)


@bot.command(name="removemanager", aliases=["removermanager"], help="Remove a revenue manager (managers only)")
async def remove_manager_cmd(ctx: commands.Context, user: discord.User):
    """Remove a revenue manager."""
    # Check if command issuer is a revenue manager
    if not is_bot_owner(ctx.author.id):
        await ctx.send(
            embed=style_embed(
                title="❌ Unauthorized",
                description="Only revenue managers can remove managers.",
                kind="error"
            )
        )
        return
    
    # Can't remove yourself if you're the only manager
    owners = get_bot_owners()
    if len(owners) == 1 and is_bot_owner(user.id):
        await ctx.send(
            embed=style_embed(
                title="❌ Cannot Remove",
                description="You cannot remove the last revenue manager. Add another manager first.",
                kind="error"
            )
        )
        return
    
    # Remove manager
    if remove_bot_owner(user.id):
        embed = style_embed(
            title=f"{BRAND_EMOJI} Manager Removed",
            description=f"✅ {user.mention} has been removed as a revenue manager.",
            kind="success"
        )
    else:
        embed = style_embed(
            title="ℹ️ Not a Manager",
            description=f"{user.mention} is not a revenue manager.",
            kind="info"
        )
    
    await ctx.send(embed=embed)


@bot.command(name="listmanagers", aliases=["revenuemanagers"], help="List all revenue managers")
async def list_managers_cmd(ctx: commands.Context):
    """List all revenue managers."""
    owners = get_bot_owners()
    
    if not owners:
        description = "No revenue managers have been set yet.\n\nUse `?addrevenuemanager @user` to add one."
    else:
        description = "**Revenue Managers:**\n\n"
        for owner_id, owner_name in owners:
            user = bot.get_user(owner_id)
            if user:
                description += f"• {user.mention} (`{user.name}`)\n"
            else:
                description += f"• {owner_name} (ID: `{owner_id}`)\n"
    
    embed = style_embed(
        title=f"{BRAND_EMOJI} Revenue Managers",
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
    
    # Bot managers
    description += f"👑 **Revenue Managers:** `{len(owners)}`\n"
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

"""
community.py — Help menu, control panel, setup dropdowns, announcements, leveling cmds, dashboard links, no-prefix helpers.
Extracted from the original monolithic bot.py. Logic unchanged.
"""
from bot.ui.premium_cards import quick_card_view, style_card_view, fun_card_view, embed_to_view
import discord
from discord.ext import commands
import discord.app_commands as app_commands
import datetime
import asyncio
import random
import re
import requests

from bot.config import (
    bot, style_embed, style_embed, UTC, BRAND_COLOR,
    afk_users,
    SUPPORT_SERVER_URL, DASHBOARD_URL, INVITE_URL, GIPHY_API_KEY, fetch_giphy_gif_url,
    has_required_slash_role, mod_group, LEVELING_SYSTEM_ENABLED, EMOJI_BULLET, staff_check,
)
from bot.database import (
    get_level_data, add_xp, level_leaderboard, xp_for_level,
    is_leveling_enabled, get_levelup_channel,
    get_all_role_menu_message_ids, get_role_menu_items,
    has_noprefix_perm, get_trusted_role_id, list_noprefix_users,
    set_config, get_config, add_vouch, count_vouches,
)


# --- LEVELING COMMANDS ---
# ==========================================
#         📈 LEVELING SYSTEM COMMANDS
# ==========================================

def make_progress_bar(current: int, needed: int, length: int = 15) -> str:
    filled = round(length * min(current / needed, 1.0)) if needed else 0
    return "█" * filled + "░" * (length - filled)

@bot.hybrid_command(name="rank", aliases=["level", "xp"], description="Check level and XP progress")
@app_commands.describe(member="User to check (defaults to yourself)")
async def rank_prefix(ctx, member: discord.Member = None):
    if not LEVELING_SYSTEM_ENABLED:
        await ctx.send(view=style_card_view(
            "Leveling Disabled",
            kind="info",
            description=f"{EMOJI_BULLET} Built-in leveling is turned off.\n{EMOJI_BULLET} Use a dedicated leveling bot if you need XP ranks.",
        ))
        return
    member = member or ctx.author
    xp, level = get_level_data(ctx.guild.id, member.id)
    needed_for_next = xp_for_level(level + 1)
    needed_for_current = xp_for_level(level)
    progress = xp - needed_for_current
    span = needed_for_next - needed_for_current
    bar = make_progress_bar(progress, span)

    embed = discord.Embed(title=f"📈 Rank — {member.display_name}", color=discord.Color.blurple())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Level", value=str(level), inline=True)
    embed.add_field(name="Total XP", value=str(xp), inline=True)
    embed.add_field(name="Progress to Next Level", value=f"`{bar}` {progress}/{span} XP", inline=False)
    await ctx.send(view=embed_to_view(embed))

@bot.hybrid_command(name="levelleaderboard", aliases=["levellb", "ranklb", "ll", "levels"], description="Show the top XP earners in this server")
async def level_leaderboard_prefix(ctx):
    if not LEVELING_SYSTEM_ENABLED:
        await ctx.send(view=style_card_view(
            "Leveling Disabled",
            kind="info",
            description=f"{EMOJI_BULLET} Built-in leveling is turned off.\n{EMOJI_BULLET} Use a dedicated leveling bot if you need XP ranks.",
        ))
        return
    rows = level_leaderboard(ctx.guild.id, limit=10)
    if not rows:
        await ctx.send(view=quick_card_view("No one has earned XP in this server yet."))
        return
    lines = []
    for i, (user_id, xp, level) in enumerate(rows, start=1):
        member = ctx.guild.get_member(user_id)
        name = member.mention if member else f"<@{user_id}>"
        lines.append(f"**{i}.** {name} — Level {level} ({xp} XP)")
    embed = discord.Embed(title="📈 Level Leaderboard", description="\n".join(lines), color=discord.Color.blurple())
    await ctx.send(view=embed_to_view(embed))



# --- DASHBOARD ---
# ==========================================
#         📊 PRIVATE GLOBAL DASHBOARD
# ==========================================

class DashboardLinks(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="Invite Bot", emoji="🤖", style=discord.ButtonStyle.link, url=INVITE_URL))
        self.add_item(discord.ui.Button(label="Support Server", emoji="🛟", style=discord.ButtonStyle.link, url=SUPPORT_SERVER_URL))
        self.add_item(discord.ui.Button(label="Dashboard", emoji="📊", style=discord.ButtonStyle.link, url=DASHBOARD_URL))

@bot.tree.command(name="dashboard", description="📊 View the server dashboard privately.")
@has_required_slash_role()
async def dashboard_slash(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📊 Server: UNITED BUNNIES",
        description="__**Commands start with `?`**__\nManage everything below from the web dashboard, or jump into support if you need a hand.",
        color=BRAND_COLOR,
        timestamp=datetime.datetime.now(UTC),
    )
    embed.add_field(name="ℹ️ Help & Support", value=f"• [Support Server]({SUPPORT_SERVER_URL})\n• [Web Dashboard]({DASHBOARD_URL})", inline=True)
    await interaction.response.send_message(embed=embed, view=DashboardLinks(), ephemeral=True)


# --- ANNOUNCE ?p ---
# ==========================================
#      📢 AESTHETIC TEXT & IMAGE ?P COMMAND
# ==========================================

@bot.hybrid_command(name="p", description="[Staff] Post a custom formatted announcement embed")
@staff_check("admin")
@app_commands.describe(text="Announcement text. Use [IMAGE] <url>, [SECTION] or [FIELD] to structure it")
async def p_prefix(ctx, *, text: str):
    try:
        if ctx.message:
            await ctx.message.delete()
    except Exception: pass

    image_urls = re.findall(r'\[IMAGE\]\s*([^\s]+)', text)
    cleaned_text = re.sub(r'\[IMAGE\]\s*[^\s]+', '', text).strip()

    if not image_urls:
        image_urls = ["https://cdn.discordapp.com/attachments/1126581404164100147/1319747806143058012/united_bunnies.png"]

    embeds = []
    if "[SECTION]" in cleaned_text:
        parts = cleaned_text.split("[SECTION]")
        main_desc = parts[0].strip()
        main_embed = discord.Embed(title="⚡ ── 𝐕𝐎𝐑𝐓𝐄𝐗 ── ⚡", description=main_desc, color=0x8B5CF6, timestamp=datetime.datetime.now(UTC))
        for part in parts[1:]:
            part = part.strip()
            if not part: continue
            lines = part.split("\n", 1)
            main_embed.add_field(name=f"⚡ ─── {lines[0].strip().upper()} ─── ⚡", value=lines[1].strip() if len(lines) > 1 else "...", inline=False)
    else:
        parts = cleaned_text.split("[FIELD]")
        main_desc = parts[0].strip()
        main_embed = discord.Embed(title="⚡ ── 𝐕𝐎𝐑𝐓𝐄𝐗 ── ⚡", description=main_desc, color=0x8B5CF6, timestamp=datetime.datetime.now(UTC))
        for part in parts[1:]:
            part = part.strip()
            if not part: continue
            lines = part.split('\n', 1)
            main_embed.add_field(name=lines[0].strip(), value=lines[1].strip() if len(lines) > 1 else "...", inline=False)

    main_embed.set_footer(text="🐰 United Bunnies System Active ✨")
    main_embed.set_image(url=image_urls[0])
    embeds.append(main_embed)

    for extra_url in image_urls[1:4]:
        extra_embed = discord.Embed(color=0x2f3136)
        extra_embed.set_image(url=extra_url)
        embeds.append(extra_embed)

    await ctx.send(embeds=embeds)


# --- CONTROL PANEL ---
# ==========================================
#         🕹️ INTERACTIVE CONTROL PANEL
# ==========================================
# A single persistent embed with buttons that ties together tickets,
# vouching, server info, and music into one place — so members don't
# need to remember every command.

class VouchModal(discord.ui.Modal, title="Vouch for a Member"):
    user_input = discord.ui.TextInput(
        label="User ID or @mention",
        placeholder="e.g. 123456789012345678 or paste their mention",
        required=True,
    )
    comment_input = discord.ui.TextInput(
        label="Comment (optional)",
        placeholder="What was it for?",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=300,
    )

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.user_input.value.strip()
        match = re.search(r"\d{15,25}", raw)
        if not match:
            await interaction.response.send_message(view=quick_card_view("❌ Couldn't find a valid user ID or mention in that."), ephemeral=True)
            return

        target_id = int(match.group())
        target = interaction.guild.get_member(target_id)
        if target is None:
            await interaction.response.send_message(view=quick_card_view("❌ Couldn't find that member in this server."), ephemeral=True)
            return
        if target.id == interaction.user.id:
            await interaction.response.send_message(view=quick_card_view("❌ You can't vouch for yourself."), ephemeral=True)
            return
        if target.bot:
            await interaction.response.send_message(view=quick_card_view("❌ You can't vouch for a bot."), ephemeral=True)
            return

        comment = self.comment_input.value.strip() or None
        add_vouch(interaction.guild.id, target.id, interaction.user.id, comment)
        total = count_vouches(interaction.guild.id, target.id)

        embed = discord.Embed(
            description=f"✅ {interaction.user.mention} vouched for {target.mention}",
            color=discord.Color.green(),
        )
        if comment:
            embed.add_field(name="Comment", value=comment, inline=False)
        embed.set_footer(text=f"{target.display_name} now has {total} vouch(es)")
        await interaction.response.send_message(view=embed_to_view(embed))


# --- SETUP DROPDOWNS ---

# ==========================================
#         ⚙️ COMMUNITY HELP MENU STRUCTURE
# ==========================================

HELP_CATEGORIES = {
    "community": {
        "label": "Community",
        "emoji": "👥",
        "title": "👥 Community Commands",
        "description": "__**Fun & everyday commands.**__ Long name and short form both work. Also available as `/slash`.",
        "fields": [
            ("🎲 Fun & Random", (
                "`?gif <keywords>` — Random GIF.\n"
                "`?meme` — Random meme.\n"
                "`?8ball <question>` — Magic 8-ball.\n"
                "`?roll [sides]` · `?coinflip` · `?choose a | b | c`\n"
                "`?hug` / `?kiss` / `?pat` / `?slap` / `?poke` / `?wave` / `?dance` / `?cry` / `?blush` `[@user]`"
            )),
            ("ℹ️ Info", (
                "`?serverinfo` · `?userinfo [@user]` · `?avatar [@user]` · `?ping`"
            )),
        ],
    },
    "marriage": {
        "label": "Marriage",
        "emoji": "💍",
        "title": "💍 Marriage System",
        "description": "__**Propose, check, or end a marriage.**__",
        "fields": [
            ("💍 Commands", (
                "`?marry @user` — Propose (Accept / Decline).\n"
                "`?family [@user]` — See who they're married to.\n"
                "`?divorce` — Request divorce (partner must confirm)."
            )),
        ],
    },
    "music": {
        "label": "Music",
        "emoji": "🎵",
        "title": "🎵 Music",
        "description": "__**Play music in voice channels.**__ Use the long name **or** the short form.",
        "fields": [
            ("🎧 Playback", (
                "`?play <name or url>` — Play / queue a track.\n"
                "`?skip` **or** `?s` **or** `?next` — Skip track.\n"
                "`?stop` **or** `?end` — Stop & clear queue.\n"
                "`?leave` **or** `?dc` **or** `?disconnect` — Leave VC.\n"
                "`?queue` **or** `?q` — Show queue.\n"
                "`?nowplaying` **or** `?np` — Now playing.\n"
                "`?volume` **or** `?vol` `[0-200]` — Set volume.\n"
                "`?loop <off|track|queue>` — Loop mode."
            )),
            ("❤️ Playlist", (
                "`?like <url> [title]` — Save a track.\n"
                "`?playlist [view|play|clear]` — Manage your playlist."
            )),
        ],
    },
    "tickets": {
        "label": "Tickets",
        "emoji": "🎫",
        "title": "🎫 Ticket System",
        "description": "__**Support tickets.**__",
        "fields": [
            ("🎫 Commands", (
                "`?ticket` — Open a ticket.\n"
                "`?ticketpanel` **or** `?tp` — Post the ticket panel.\n"
                "`?tickets` **or** `?ticketlist` — List open tickets.\n"
                "`?closeticket` **or** `?close` — Close this ticket."
            )),
        ],
    },
    "vouch": {
        "label": "Vouch",
        "emoji": "✅",
        "title": "✅ Vouch System",
        "description": "__**Vouch for trusted members.**__",
        "fields": [
            ("✅ Commands", (
                "`?vouch @user [reason]` — Give a vouch.\n"
                "`?unvouch @user` — Remove your last vouch.\n"
                "`?vouches` **or** `?vouchlist` `[@user]` — Recent vouches.\n"
                "`?vouchleaderboard` **or** `?vouchlb` — Top vouched users.\n"
                "`?setvouchchannel` **or** `?setvouch` — Staff: set channel.\n"
                "`?clearvouchchannel` **or** `?clearvouch` — Staff: clear channel."
            )),
        ],
    },
    "mod": {
        "label": "Moderation",
        "emoji": "🔨",
        "title": "🔨 Moderation",
        "description": "__**Staff only.**__ Full name **or** short form both work.\nRequires **Discord mod perms** (Kick/Ban/Moderate/Manage Messages), **Administrator**, the legacy staff role, **or** the server trusted role. Also under `/mod`.",
        "fields": [
            ("⚔️ Enforcement", (
                "`?warn` **or** `?w` `@user [reason]`\n"
                "`?warnings` **or** `?warns` `[@user]`\n"
                "`?clearwarnings` **or** `?cw` **or** `?clearwarns` `@user`\n"
                "`?mute` **or** `?timeout` `@user [mins] [reason]`\n"
                "`?unmute` **or** `?untimeout` `@user`\n"
                "`?kick` **or** `?k` `@user [reason]`\n"
                "`?ban` **or** `?b` `@user [reason]`\n"
                "`?unban` **or** `?ub` `<user_id>`\n"
                "`?bon @user` — Joke ban (not real)\n"
                "`?reactionrole` **or** `?rr` `<msg_id> <emoji> [@role]`"
            )),
            ("⚙️ Setup (`/mod`)", (
                "`/mod setup` · `/mod panel` · `/mod clear <amount>`\n"
                "`/mod setwelcome` · `/mod setlogs` · `/mod setlevelchannel`\n"
                "`/mod togglelevels` · `/mod setwelcomemessage`\n"
                "`/mod warn` · `/mod mute` · `/mod kick` · `/mod ban` (slash versions)"
            )),
        ],
    },
    "custom": {
        "label": "Custom & Perms",
        "emoji": "🔐",
        "title": "🔐 Permissions & Custom Commands",
        "description": "__**Staff-only.**__",
        "fields": [
            ("🔐 Command Perms", (
                "`/cmdperm-allow <cmd> <role>` — Restrict a command.\n"
                "`/cmdperm-deny <cmd> <role>` — Remove access.\n"
                "`/cmdperm-list` · `/cmdperm-reset <cmd>`"
            )),
            ("💬 Custom Replies", (
                "`/new-command <trigger> <response>` — Add auto-reply.\n"
                "`/delete-command <trigger>` · `/list-commands`"
            )),
            ("🔒 Toggle", (
                "`?disable <name> [command|module]` · `?enable <name>`"
            )),
        ],
    },
}


HELP_HOME_TITLE = "🐰 ── UNITED BUNNIES HELP ── 🐰"
HELP_HOME_DESCRIPTION = (
    "__**Welcome to the Command Center.**__\n"
    "Pick a category from the dropdown below to see what's inside, or use the "
    "buttons for **support** and the **web dashboard**.\n\n"
    "Most commands work with the `?` prefix **or** as a `/slash` command."
)


def build_help_home_embed() -> discord.Embed:
    embed = discord.Embed(
        title=HELP_HOME_TITLE,
        description=HELP_HOME_DESCRIPTION,
        color=BRAND_COLOR,
        timestamp=datetime.datetime.now(UTC),
    )
    category_list = "\n".join(f"{c['emoji']} **{c['label']}**" for c in HELP_CATEGORIES.values())
    embed.add_field(name="📂 Categories", value=category_list, inline=False)
    embed.set_footer(text="United Bunnies • Use the menu below to browse commands")
    return embed


def build_help_category_embed(key: str) -> discord.Embed:
    cat = HELP_CATEGORIES[key]
    embed = discord.Embed(
        title=cat["title"],
        description=cat["description"],
        color=BRAND_COLOR,
        timestamp=datetime.datetime.now(UTC),
    )
    for name, value in cat["fields"]:
        embed.add_field(name=f"__**{name}**__", value=value, inline=False)
    embed.set_footer(text="United Bunnies • Use the menu below to browse other categories")
    return embed


class HelpCategorySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=cat["label"], value=key, emoji=cat["emoji"])
            for key, cat in HELP_CATEGORIES.items()
        ]
        super().__init__(placeholder="📂 Select a command category…", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        key = self.values[0]
        embed = build_help_category_embed(key)
        await interaction.response.edit_message(embed=embed, view=HelpView())


class HelpHomeButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Home", emoji="🏠", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        embed = build_help_home_embed()
        await interaction.response.edit_message(embed=embed, view=HelpView())


class HelpView(discord.ui.View):
    """Persistent help menu: category dropdown + Home/Support/Dashboard buttons."""
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(HelpCategorySelect())
        self.add_item(HelpHomeButton())
        self.add_item(discord.ui.Button(label="Support", emoji="🛟", style=discord.ButtonStyle.link, url=SUPPORT_SERVER_URL, row=1))
        self.add_item(discord.ui.Button(label="Dashboard", emoji="📊", style=discord.ButtonStyle.link, url=DASHBOARD_URL, row=1))

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


@bot.hybrid_command(name="help", description="Show the command list")
async def help_prefix(ctx):
    embed = build_help_home_embed()
    await ctx.send(embed=embed, view=HelpView())


@bot.hybrid_command(name="afk", description="Set yourself as AFK")
@app_commands.describe(reason="Why you're AFK (optional)")
async def afk_prefix(ctx, *, reason: str = "AFK"):
    afk_users[ctx.author.id] = {"reason": reason, "timestamp": datetime.datetime.now(), "old_name": ctx.author.nick}
    try: await ctx.author.edit(nick=f"[AFK] {ctx.author.display_name[:25]}")
    except Exception: pass
    await ctx.send(view=quick_card_view(f"💤 {ctx.author.mention} is now AFK."))

@bot.hybrid_command(name="ping", description="Check the bot's latency")
async def ping_prefix(ctx):
    await ctx.send(view=style_card_view(
        "Ping",
        kind="info",
        description=f"{EMOJI_BULLET} latency: **{round(bot.latency * 1000)}ms**",
    ))

async def send_gif_embed(channel, query: str, title: str = None, *, description: str | None = None, kind: str = "fun"):
    loop = asyncio.get_running_loop()
    gif_url = await loop.run_in_executor(None, fetch_giphy_gif_url, query)
    if not gif_url:
        if not GIPHY_API_KEY:
            await channel.send(view=quick_card_view("❌ GIPHY_API_KEY is missing on the server."))
        else:
            await channel.send(view=quick_card_view("❌ No GIF found. Try different keywords."))
        return None
    await channel.send(
        view=fun_card_view(
            title or "GIF",
            description or "✨ A little something for the timeline.",
            image_url=gif_url,
            kind=kind,
        )
    )
    return gif_url

FUN_ACTIONS = {
    "hugs": ("🫂 HUG", "💕", "anime hug"),
    "kisses": ("💋 KISS", "💕", "anime kiss"),
    "pats": ("🫳 PAT PAT", "✨", "anime pat"),
    "throws": ("💨 THROW", "😂", "anime throw"),
    "slaps": ("👋 SLAP", "💥", "anime slap"),
    "pokes": ("👉 POKE", "👉", "anime poke"),
    "waves at": ("👋 WAVE", "✨", "anime wave"),
    "dances with": ("💃 DANCE", "🎶", "anime dance"),
    "cries at": ("😭 CRY", "🥲", "anime cry"),
    "blushes at": ("😊 BLUSH", "💕", "anime blush"),
}

async def action_gif(ctx, action: str, target: discord.Member = None, query: str = None):
    target = target or ctx.author
    title, emoji, default_query = FUN_ACTIONS.get(
        action,
        (action.replace(" ", " ").upper(), "✨", f"{action} gif"),
    )
    actor = discord.utils.escape_markdown(ctx.author.display_name)
    target_name = discord.utils.escape_markdown(target.display_name)
    sentence = f"**{actor}** {action} **{target_name}**! {emoji}"
    await send_gif_embed(
        ctx.channel,
        query or default_query,
        title=title,
        description=sentence,
        kind="love" if action in ("kisses", "hugs", "blushes at", "dances with") else "fun",
    )

@bot.hybrid_command(name="gif", description="Send a random GIF for a keyword")
@app_commands.describe(query="Search keywords")
async def gif_prefix(ctx, *, query: str = None):
    if not query:
        await ctx.send(view=quick_card_view("❌ Syntax: `?gif <search keywords>`"))
        return
    async with ctx.typing():
        await send_gif_embed(ctx.channel, query, title=f"GIF: {query}")

@bot.hybrid_command(name="hug", description="Give someone a hug")
@app_commands.describe(member="Who to hug")
async def hug_prefix(ctx, member: discord.Member = None):
    await action_gif(ctx, "hugs", member, "anime hug")

@bot.hybrid_command(name="kiss", description="Give someone a kiss")
@app_commands.describe(member="Who to kiss")
async def kiss_prefix(ctx, member: discord.Member = None):
    await action_gif(ctx, "kisses", member, "anime kiss")

@bot.hybrid_command(name="pat", description="Pat someone on the head")
@app_commands.describe(member="Who to pat")
async def pat_prefix(ctx, member: discord.Member = None):
    await action_gif(ctx, "pats", member, "anime pat")

@bot.hybrid_command(name="throw", description="Throw something at someone (in fun)")
@app_commands.describe(member="Who to throw at")
async def throw_prefix(ctx, member: discord.Member = None):
    await action_gif(ctx, "throws", member, "anime throw")

@bot.hybrid_command(name="slap", description="Slap someone")
@app_commands.describe(member="Who to slap")
async def slap_prefix(ctx, member: discord.Member = None):
    await action_gif(ctx, "slaps", member, "anime slap")

@bot.hybrid_command(name="poke", description="Poke someone")
@app_commands.describe(member="Who to poke")
async def poke_prefix(ctx, member: discord.Member = None):
    await action_gif(ctx, "pokes", member, "anime poke")

@bot.hybrid_command(name="wave", description="Wave at someone")
@app_commands.describe(member="Who to wave at")
async def wave_prefix(ctx, member: discord.Member = None):
    await action_gif(ctx, "waves at", member, "anime wave")

@bot.hybrid_command(name="dance", description="Dance with someone")
@app_commands.describe(member="Who to dance with")
async def dance_prefix(ctx, member: discord.Member = None):
    await action_gif(ctx, "dances with", member, "anime dance")

@bot.hybrid_command(name="cry", description="Cry at someone")
@app_commands.describe(member="Who to cry at")
async def cry_prefix(ctx, member: discord.Member = None):
    await action_gif(ctx, "cries at", member, "anime cry")

@bot.hybrid_command(name="blush", description="Blush at someone")
@app_commands.describe(member="Who to blush at")
async def blush_prefix(ctx, member: discord.Member = None):
    await action_gif(ctx, "blushes at", member, "anime blush")

@bot.hybrid_command(name="roll", description="Roll a dice")
@app_commands.describe(sides="Number of sides (default 6)")
async def roll_prefix(ctx, sides: int = 6):
    sides = max(2, min(1000, sides))
    result = random.randint(1, sides)
    await ctx.send(view=quick_card_view(f"🎲 You rolled a **{result}** (1-{sides})"))

@bot.hybrid_command(name="coinflip", aliases=["flip"], description="Flip a coin")
async def coinflip_prefix(ctx):
    result = random.choice(["Heads", "Tails"])
    await ctx.send(view=quick_card_view(f"🪙 **{result}!**"))

@bot.hybrid_command(name="choose", description="Pick randomly between options")
@app_commands.describe(options="Options separated by | (e.g. a | b | c)")
async def choose_prefix(ctx, *, options: str = None):
    if not options or "|" not in options:
        await ctx.send(view=quick_card_view("❌ Syntax: `?choose option1 | option2 | option3`"))
        return
    choices = [o.strip() for o in options.split("|") if o.strip()]
    if len(choices) < 2:
        await ctx.send(view=quick_card_view("❌ Give me at least two options, separated by `|`."))
        return
    await ctx.send(view=quick_card_view(f"🤔 I choose: **{random.choice(choices)}**"))

@bot.hybrid_command(name="8ball", description="Ask the magic 8-ball a question")
@app_commands.describe(question="Your question")
async def eightball_prefix(ctx, *, question: str = None):
    if not question:
        await ctx.send(view=quick_card_view("❌ Syntax: `?8ball <question>`"))
        return
    answers = [
        "Yes.",
        "No.",
        "Maybe.",
        "Ask again later.",
        "Absolutely.",
        "Not a chance.",
        "It is certain.",
        "Very doubtful.",
    ]
    await ctx.send(view=quick_card_view(f"🎱 {random.choice(answers)}"))

@bot.hybrid_command(name="avatar", description="Get a user's avatar")
@app_commands.describe(member="User to check (defaults to yourself)")
async def avatar_prefix(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"{member.display_name}'s Avatar", color=0x2f3136)
    embed.set_image(url=member.display_avatar.url)
    await ctx.send(view=embed_to_view(embed))

@bot.hybrid_command(name="userinfo", description="Get info about a user")
@app_commands.describe(member="User to check (defaults to yourself)")
async def userinfo_prefix(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"User Info: {member}", color=0x2f3136, timestamp=datetime.datetime.now(UTC))
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="ID", value=str(member.id), inline=True)
    embed.add_field(name="Top Role", value=member.top_role.mention if member.top_role else "-", inline=True)
    embed.add_field(name="Account Created", value=discord.utils.format_dt(member.created_at, style="F"), inline=False)
    if member.joined_at:
        embed.add_field(name="Joined Server", value=discord.utils.format_dt(member.joined_at, style="F"), inline=False)
    await ctx.send(view=embed_to_view(embed))

@bot.hybrid_command(name="serverinfo", description="Get info about this server")
async def serverinfo_prefix(ctx):
    g = ctx.guild
    embed = discord.Embed(title=f"Server Info: {g.name}", color=0x2f3136, timestamp=datetime.datetime.now(UTC))
    if g.icon:
        embed.set_thumbnail(url=g.icon.url)
    embed.add_field(name="ID", value=str(g.id), inline=True)
    embed.add_field(name="Owner", value=g.owner.mention if g.owner else "-", inline=True)
    embed.add_field(name="Created", value=discord.utils.format_dt(g.created_at, style="F"), inline=False)
    embed.add_field(name="Members", value=str(g.member_count), inline=True)
    embed.add_field(name="Channels", value=str(len(g.channels)), inline=True)
    await ctx.send(view=embed_to_view(embed))

@bot.hybrid_command(name="meme", description="Get a random meme")
async def meme_prefix(ctx):
    async with ctx.typing():
        try:
            resp = requests.get("https://meme-api.com/gimme", timeout=12)
            resp.raise_for_status()
            data = resp.json()
            meme_url = data.get("url")
            title = data.get("title") or "Meme"
        except Exception:
            meme_url = None
            title = None
    if not meme_url:
        await ctx.send(view=quick_card_view("❌ Meme fetch failed. Try again."))
        return
    embed = discord.Embed(title=title, color=0x2f3136)
    embed.set_image(url=meme_url)
    await ctx.send(view=embed_to_view(embed))

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRole) or isinstance(error, commands.MissingPermissions):
        await ctx.send(view=quick_card_view("❌ You don't have permission to use that command."), delete_after=6)
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(view=quick_card_view("❌ Missing arguments. Use `?help` for usage."), delete_after=6)
        return
    if isinstance(error, commands.CheckFailure):
        await ctx.send(str(error) or "❌ You don't have permission to use that command.", delete_after=6)
        return
    await ctx.send(view=quick_card_view(f"❌ Error: {error}"), delete_after=8)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        if interaction.response.is_done():
            await interaction.followup.send("❌ You don't have permission to use that command.", ephemeral=True)
        else:
            await interaction.response.send_message(view=quick_card_view("❌ You don't have permission to use that command."), ephemeral=True)
        return
    if interaction.response.is_done():
        await interaction.followup.send(f"❌ Error: {error}", ephemeral=True)
    else:
        await interaction.response.send_message(view=quick_card_view(f"❌ Error: {error}"), ephemeral=True)



from bot.ui.premium_cards import quick_card_view, style_card_view, fun_card_view, embed_to_view
"""
marriage.py — Marriage / proposal system.
Extracted from the original monolithic bot.py. Logic unchanged.
"""
import discord
from discord.ext import commands
import discord.app_commands as app_commands
import datetime

from bot.config import bot, style_embed, UTC
from bot.database import get_marriage, create_marriage, delete_marriage
from bot.cogs.community import send_gif_embed

class MarriageProposalView(discord.ui.View):
    def __init__(self, proposer: discord.Member, target: discord.Member):
        super().__init__(timeout=60)
        self.proposer = proposer
        self.target = target
        self.responded = False
        self.message = None  # set by the command after sending

    async def on_timeout(self):
        if self.responded or not self.message:
            return
        for item in self.children:
            item.disabled = True
        embed = discord.Embed(
            description=f"⏳ {self.target.mention} never responded — the proposal from {self.proposer.mention} expired.",
            color=discord.Color.dark_grey(),
        )
        try:
            await self.message.edit(embed=embed, view=self)
        except discord.HTTPException:
            pass

    @discord.ui.button(label="Accept 💍", style=discord.ButtonStyle.success)
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            await interaction.response.send_message(view=quick_card_view("❌ This proposal isn't addressed to you."), ephemeral=True)
            return
        if self.responded:
            return
        self.responded = True

        # Re-check at accept time in case either party got married elsewhere while this was pending
        if get_marriage(interaction.guild.id, self.proposer.id) or get_marriage(interaction.guild.id, self.target.id):
            for item in self.children:
                item.disabled = True
            embed = discord.Embed(
                description="❌ This proposal fell through — one of you is already married to someone else now.",
                color=discord.Color.red(),
            )
            await interaction.response.edit_message(embed=embed, view=self)
            return

        create_marriage(interaction.guild.id, self.proposer.id, self.target.id)
        for item in self.children:
            item.disabled = True
        embed = discord.Embed(
            title="💍 Just Married!",
            description=f"{self.proposer.mention} 💕 {self.target.mention}\n\nCongratulations to the happy couple!",
            color=discord.Color.pink(),
        )
        embed.set_footer(text="Use ?family to check on your marriage, or ?divorce if it doesn't work out.")
        await interaction.response.edit_message(embed=embed, view=self)
        async with interaction.channel.typing():
            await send_gif_embed(interaction.channel, "wedding celebration", title=None)

    @discord.ui.button(label="Decline 💔", style=discord.ButtonStyle.danger)
    async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            await interaction.response.send_message(view=quick_card_view("❌ This proposal isn't addressed to you."), ephemeral=True)
            return
        if self.responded:
            return
        self.responded = True
        for item in self.children:
            item.disabled = True
        embed = discord.Embed(
            description=f"💔 {self.target.mention} declined {self.proposer.mention}'s proposal.",
            color=discord.Color.red(),
        )
        await interaction.response.edit_message(embed=embed, view=self)


class DivorceConfirmView(discord.ui.View):
    def __init__(self, initiator: discord.Member, partner: discord.Member, marriage_id: int):
        super().__init__(timeout=60)
        self.initiator = initiator
        self.partner = partner
        self.marriage_id = marriage_id
        self.responded = False
        self.message = None

    async def on_timeout(self):
        if self.responded or not self.message:
            return
        for item in self.children:
            item.disabled = True
        embed = discord.Embed(
            description=f"⏳ {self.partner.mention} never responded — the divorce request expired. Still married 💍",
            color=discord.Color.dark_grey(),
        )
        try:
            await self.message.edit(embed=embed, view=self)
        except discord.HTTPException:
            pass

    @discord.ui.button(label="Confirm Divorce 💔", style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.partner.id:
            await interaction.response.send_message(view=quick_card_view("❌ Only your partner can confirm this."), ephemeral=True)
            return
        if self.responded:
            return
        self.responded = True
        delete_marriage(self.marriage_id)
        for item in self.children:
            item.disabled = True
        embed = discord.Embed(
            title="💔 Divorced",
            description=f"{self.initiator.mention} and {self.partner.mention} are no longer married.",
            color=discord.Color.dark_grey(),
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.secondary)
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.partner.id:
            await interaction.response.send_message(view=quick_card_view("❌ Only your partner can respond to this."), ephemeral=True)
            return
        if self.responded:
            return
        self.responded = True
        for item in self.children:
            item.disabled = True
        embed = discord.Embed(
            description=f"{self.partner.mention} denied the divorce request. Still married 💍",
            color=discord.Color.green(),
        )
        await interaction.response.edit_message(embed=embed, view=self)


@bot.hybrid_command(name="marry", description="Propose marriage to someone")
@commands.guild_only()
@app_commands.describe(member="Who you want to propose to")
async def marry_prefix(ctx, member: discord.Member = None):
    if member is None:
        await ctx.send(view=quick_card_view("❌ Syntax: `?marry @user`"))
        return
    if member.id == ctx.author.id:
        await ctx.send(view=quick_card_view("❌ You can't marry yourself."))
        return
    if member.bot:
        await ctx.send(view=quick_card_view("❌ You can't marry a bot."))
        return

    if get_marriage(ctx.guild.id, ctx.author.id):
        await ctx.send(view=quick_card_view("❌ You're already married! Use `?divorce` first if you want to remarry."))
        return

    if get_marriage(ctx.guild.id, member.id):
        await ctx.send(view=fun_card_view(
            "💍 ALREADY MARRIED",
            f"**{member.display_name}** is already taken. 💐\n\nBetter luck next time!",
            kind="love",
        ))
        async with ctx.typing():
            await send_gif_embed(ctx.channel, "already married objection", title=None)
        return

    embed = discord.Embed(
        title="💍 Marriage Proposal",
        description=f"{ctx.author.mention} has proposed to {member.mention}!\n\n{member.mention}, do you accept?",
        color=discord.Color.pink(),
    )
    view = MarriageProposalView(ctx.author, member)
    msg = await ctx.send(content=member.mention, embed=embed, view=view)
    view.message = msg


@bot.hybrid_command(name="divorce", description="End your marriage")
@commands.guild_only()
async def divorce_prefix(ctx):
    marriage = get_marriage(ctx.guild.id, ctx.author.id)
    if not marriage:
        await ctx.send(view=quick_card_view("❌ You're not married to anyone."))
        return

    marriage_id, user1_id, user2_id, married_at = marriage
    partner_id = user2_id if user1_id == ctx.author.id else user1_id
    partner = ctx.guild.get_member(partner_id)

    if not partner:
        # Partner has left the server — nothing to confirm with, so dissolve it automatically.
        delete_marriage(marriage_id)
        await ctx.send(view=quick_card_view("✅ Your partner is no longer in this server — the marriage has been dissolved automatically."))
        return

    embed = discord.Embed(
        title="💔 Divorce Request",
        description=f"{ctx.author.mention} wants to divorce {partner.mention}.\n\n{partner.mention}, do you confirm?",
        color=discord.Color.orange(),
    )
    view = DivorceConfirmView(ctx.author, partner, marriage_id)
    msg = await ctx.send(content=partner.mention, embed=embed, view=view)
    view.message = msg


@bot.hybrid_command(name="family", aliases=["marriage", "spouse"], description="Check someone's marriage status")
@commands.guild_only()
@app_commands.describe(member="User to check (defaults to yourself)")
async def family_prefix(ctx, member: discord.Member = None):
    member = member or ctx.author
    marriage = get_marriage(ctx.guild.id, member.id)

    if not marriage:
        if member.id == ctx.author.id:
            await ctx.send(view=quick_card_view("💔 You're not married yet. Use `?marry @user` to propose!"))
        else:
            await ctx.send(view=quick_card_view(f"💔 **{member.display_name}** isn't married yet."))
        return

    marriage_id, user1_id, user2_id, married_at = marriage
    partner_id = user2_id if user1_id == member.id else user1_id
    partner = ctx.guild.get_member(partner_id)
    partner_name = partner.mention if partner else f"<@{partner_id}>"

    try:
        married_dt = datetime.datetime.fromisoformat(married_at)
        since_text = discord.utils.format_dt(married_dt, style="R")
    except Exception:
        since_text = "some time ago"

    embed = discord.Embed(
        title=f"👪 {member.display_name}'s Family",
        description=f"💍 Married to {partner_name}\n📅 Since {since_text}",
        color=discord.Color.magenta(),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    await ctx.send(view=embed_to_view(embed))



from bot.ui.premium_cards import quick_card_view, style_card_view, embed_to_view
"""
moderation.py — Real moderation tools (prefix) + aesthetic ?bon.
Extracted from the original monolithic bot.py. Logic unchanged.
"""
import discord
from discord.ext import commands
import discord.app_commands as app_commands
import datetime
import random

from bot.config import bot, style_embed, style_embed, staff_check, is_staff, UTC, EMOJI_BULLET
from bot.database import (
    get_warnings, update_warnings, reset_warnings,
)

# ==========================================
#         🔨 THE AESTHETIC BAN (?BON)
# ==========================================

class AestheticSelfBanView(discord.ui.View):
    def __init__(self, ctx: commands.Context):
        super().__init__(timeout=60)
        self.ctx = ctx

    @discord.ui.button(label="Proceed", style=discord.ButtonStyle.danger, emoji="⛓️")
    async def yes_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(view=quick_card_view("🌌 This timeline isn't yours to change."), ephemeral=True)
            return
        embed = discord.Embed(title="🪐 SYSTEM OVERRIDE SUCCESSFUL", description=f"**{interaction.user.name}** has willingly left the server matrix.", color=0x2f3136, timestamp=datetime.datetime.now(UTC))
        embed.set_image(url="https://media.giphy.com/media/3XiQswSmruBiw/giphy.gif")
        for item in self.children: item.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Abrupt", style=discord.ButtonStyle.secondary, emoji="🛡️")
    async def no_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(view=quick_card_view("🌌 This timeline isn't yours to change."), ephemeral=True)
            return
        embed = discord.Embed(description="🔮 *The system stabilizer kicks in. Ban sequence retracted safely.*", color=0x2f3136)
        for item in self.children: item.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

@bot.hybrid_command(name="bon", description="Cosmetic joke removal (not a real ban)")
@staff_check("mod")
@app_commands.describe(member="User to (fake) ban")
async def bon_prefix(ctx, member: discord.Member = None):
    if member is None:
        await ctx.send(view=quick_card_view("❌ **Syntax Error:** Specify a user profile. Example: `?bon @user`"))
        return
    if member.id == bot.user.id:
        embed = discord.Embed(title="🛡️ SECURITY PROTOCOL ACTIVE", description="**This bot is fully secured.** System access keys are locked down.", color=0x2f3136, timestamp=datetime.datetime.now(UTC))
        embed.set_image(url="https://media.giphy.com/media/139eZBmH1HTyY8/giphy.gif")
        await ctx.send(view=embed_to_view(embed))
        return
    if member == ctx.author:
        embed = discord.Embed(title="👾 INITIALIZING SELF DESTRUCTION SEQUENCE", description="Are you sure you want to decouple from the core frame?", color=0x2f3136)
        embed.set_image(url="https://media.giphy.com/media/a5viI92PAFUsU/giphy.gif")
        await ctx.send(embed=embed, view=AestheticSelfBanView(ctx))
        return

    funny_messages = [
        f"🚀 **{member.name}** was strapped to a rocket and launched straight into the sun! No respawns.",
        f"💥 **{member.name}** lost a 1v1 against the Ban Hammer.",
        f"🧹 **{member.name}** was mistaken for garbage and cleanly swept out of the matrix.",
        f"🛸 **{member.name}** has been abducted by aliens."
    ]
    embed = discord.Embed(title="🔨 ADMINISTRATIVE REMOVAL EXECUTED", description=random.choice(funny_messages), color=0x2f3136, timestamp=datetime.datetime.now(UTC))
    embed.set_image(url="https://cdn.discordapp.com/attachments/1126581404164100147/1319747806143058012/united_bunnies.png")
    await ctx.send(view=embed_to_view(embed))


# ==========================================
#         🔨 REAL MODERATION TOOLS
# ==========================================
# Note: ?bon above is a cosmetic joke command. These are the actual
# enforcement tools (real kick/ban/timeout + manual warnings).
#
# These stay PREFIX-ONLY on purpose: /mod warn, /mod ban, /mod kick, etc.
# below already provide slash-command equivalents. Making these hybrid
# too would just create a duplicate top-level /warn next to /mod warn.

@bot.command(name="warn", aliases=["w"])
@staff_check("mod")
async def warn_prefix(ctx, member: discord.Member = None, *, reason: str = "No reason provided"):
    if member is None:
        await ctx.send(view=quick_card_view("❌ Syntax: `?warn @user [reason]`"))
        return
    current = update_warnings(member.id, 1)
    view = style_card_view(
        "Warning Issued",
        kind="warn",
        description=(
            f"{EMOJI_BULLET} user: {member.mention}\n"
            f"{EMOJI_BULLET} moderator: {ctx.author.mention}\n"
            f"{EMOJI_BULLET} warnings: **{current}/3**\n"
            f"{EMOJI_BULLET} reason: {reason}"
        ),
        footer=f"ID: {member.id}",
    )
    await ctx.send(view=view)

    if current >= 3:
        reset_warnings(member.id)
        try:
            await member.timeout(datetime.timedelta(minutes=10), reason="Reached 3 warnings")
            await ctx.send(view=quick_card_view(f"🤫 **{member.display_name}** has been auto-timed out for 10 minutes after reaching 3 warnings."))
        except discord.Forbidden:
            await ctx.send(view=quick_card_view("⚠️ Reached 3 warnings, but I don't have permission to timeout that user."))

@bot.command(name="warnings", aliases=["warns"])
async def warnings_prefix(ctx, member: discord.Member = None):
    member = member or ctx.author
    count = get_warnings(member.id)
    view = style_card_view(
        "Warnings",
        kind="info",
        description=f"{EMOJI_BULLET} user: {member.mention}\n{EMOJI_BULLET} warnings: **{count}/3**",
        footer=f"ID: {member.id}",
    )
    await ctx.send(view=view)

@bot.command(name="clearwarnings", aliases=["cw", "clearwarns"])
@staff_check("mod")
async def clearwarnings_prefix(ctx, member: discord.Member = None):
    if member is None:
        await ctx.send(view=quick_card_view("❌ Syntax: `?clearwarnings @user`"))
        return
    reset_warnings(member.id)
    view = style_card_view(
        "Warnings Cleared",
        kind="success",
        description=f"{EMOJI_BULLET} user: {member.mention}\n{EMOJI_BULLET} warnings: **0/3**",
        footer=f"ID: {member.id}",
    )
    await ctx.send(view=view)

@bot.command(name="mute", aliases=["timeout"])
@staff_check("mod")
async def mute_prefix(ctx, member: discord.Member = None, minutes: int = 10, *, reason: str = "No reason provided"):
    if member is None:
        await ctx.send(view=quick_card_view("❌ Syntax: `?mute @user [minutes] [reason]`"))
        return
    minutes = max(1, min(40320, minutes))  # Discord's timeout cap is 28 days
    try:
        await member.timeout(datetime.timedelta(minutes=minutes), reason=f"{reason} (by {ctx.author})")
    except discord.Forbidden:
        await ctx.send(view=quick_card_view("❌ I don't have permission to timeout that user (check role hierarchy)."))
        return
    view = style_card_view(
        "Member Timed Out",
        kind="mod",
        description=(
            f"{EMOJI_BULLET} user: {member.mention}\n"
            f"{EMOJI_BULLET} duration: **{minutes}** min\n"
            f"{EMOJI_BULLET} moderator: {ctx.author.mention}\n"
            f"{EMOJI_BULLET} reason: {reason}"
        ),
        footer=f"ID: {member.id}",
    )
    await ctx.send(view=view)

@bot.command(name="unmute", aliases=["untimeout"])
@staff_check("mod")
async def unmute_prefix(ctx, member: discord.Member = None):
    if member is None:
        await ctx.send(view=quick_card_view("❌ Syntax: `?unmute @user`"))
        return
    try:
        await member.timeout(None, reason=f"Unmuted by {ctx.author}")
    except discord.Forbidden:
        await ctx.send(view=quick_card_view("❌ I don't have permission to unmute that user."))
        return
    view = style_card_view(
        "Member Unmuted",
        kind="success",
        description=f"{EMOJI_BULLET} user: {member.mention}\n{EMOJI_BULLET} moderator: {ctx.author.mention}",
        footer=f"ID: {member.id}",
    )
    await ctx.send(view=view)

@bot.command(name="kick", aliases=["k"])
@staff_check("kick")
async def kick_prefix(ctx, member: discord.Member = None, *, reason: str = "No reason provided"):
    if member is None:
        await ctx.send(view=quick_card_view("❌ Syntax: `?kick @user [reason]`"))
        return
    if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
        await ctx.send(view=quick_card_view("❌ You can't kick someone with an equal or higher role than you."))
        return
    try:
        await member.kick(reason=f"{reason} (by {ctx.author})")
    except discord.Forbidden:
        await ctx.send(view=quick_card_view("❌ I don't have permission to kick that user (check role hierarchy)."))
        return
    view = style_card_view(
        "Member Kicked",
        kind="mod",
        description=(
            f"{EMOJI_BULLET} user: **{member}**\n"
            f"{EMOJI_BULLET} moderator: {ctx.author.mention}\n"
            f"{EMOJI_BULLET} reason: {reason}"
        ),
        footer=f"ID: {member.id}",
    )
    await ctx.send(view=view)

@bot.command(name="ban", aliases=["b"])
@staff_check("ban")
async def ban_prefix(ctx, member: discord.Member = None, *, reason: str = "No reason provided"):
    if member is None:
        await ctx.send(view=quick_card_view("❌ Syntax: `?ban @user [reason]`"))
        return
        
    if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
        await ctx.send(view=quick_card_view("❌ You can't ban someone with an equal or higher role than you."))
        return
        
    try:
        await member.ban(reason=f"{reason} (by {ctx.author})")
    except discord.Forbidden:
        await ctx.send(view=quick_card_view("❌ I don't have permission to ban that user (check role hierarchy)."))
        return
        
    view = style_card_view(
        "Member Banned",
        kind="error",
        description=(
            f"{EMOJI_BULLET} user: **{member}**\n"
            f"{EMOJI_BULLET} moderator: {ctx.author.mention}\n"
            f"{EMOJI_BULLET} reason: {reason}"
        ),
        footer=f"ID: {member.id}",
    )
    await ctx.send(view=view)

@bot.command(name="unban", aliases=["ub"])
@staff_check("ban")
async def unban_prefix(ctx, user_id: int = None, *, reason: str = "No reason provided"):
    if user_id is None:
        await ctx.send(view=quick_card_view("❌ Syntax: `?unban <user_id> [reason]`"))
        return
    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user, reason=f"{reason} (by {ctx.author})")
    except discord.NotFound:
        await ctx.send(view=quick_card_view("❌ That user isn't banned."))
        return
    except discord.Forbidden:
        await ctx.send(view=quick_card_view("❌ I don't have permission to unban."))
        return
    view = style_card_view(
        "Member Unbanned",
        kind="success",
        description=f"{EMOJI_BULLET} user: **{user}**\n{EMOJI_BULLET} moderator: {ctx.author.mention}",
        footer=f"ID: {user.id}",
    )
    await ctx.send(view=view)



from bot.ui.premium_cards import quick_card_view, style_card_view, embed_to_view
"""
mod_slash.py — /mod slash group, cmdperm-*, custom commands, enable/disable.
Extracted from the original monolithic bot.py. Logic unchanged.
"""
import discord
from discord.ext import commands
import discord.app_commands as app_commands
import datetime

from bot.config import bot, style_embed, UTC, mod_group, has_required_slash_role, staff_check
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

"""
music.py — Music engine (play, queue, volume, loop, playlist).
Extracted from the original monolithic bot.py. Logic unchanged.
"""
import discord
from discord.ext import commands
import discord.app_commands as app_commands
import yt_dlp
import asyncio
import datetime
import shutil
import os

from bot.config import (
    bot, style_embed, song_queues, now_playing, song_volumes, loop_modes,
)
from bot.database import add_liked_song, get_liked_songs, clear_liked_songs

# Auto-detect ffmpeg location (works on Windows, Linux, macOS)
FFMPEG_PATH = shutil.which("ffmpeg") or os.getenv("FFMPEG_PATH") or "/usr/bin/ffmpeg"

def play_next_in_queue(ctx):
    guild_id = ctx.guild.id
    vc = ctx.voice_client
    if not vc or not vc.is_connected():
        return

    # Handle looping: re-queue the track that just finished before picking the next one
    finished_track = now_playing.get(guild_id)
    mode = loop_modes.get(guild_id, "off")
    if finished_track:
        if mode == "track":
            song_queues.setdefault(guild_id, []).insert(0, finished_track)
        elif mode == "queue":
            song_queues.setdefault(guild_id, []).append(finished_track)

    if guild_id in song_queues and len(song_queues[guild_id]) > 0:
        next_track = song_queues[guild_id].pop(0)
        now_playing[guild_id] = next_track

        ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn',
            'ffmpeg_location': FFMPEG_PATH  # Auto-detected or from env
        }

        volume = song_volumes.get(guild_id, 1.0)
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(next_track["url"], **ffmpeg_options), volume=volume)

        vc.play(
            source,
            after=lambda e: play_next_in_queue(ctx)
        )
        
        embed = discord.Embed(
            title="🎶 Now Playing",
            description=f"**[{next_track['title']}]({next_track['url']})** \n⏱️ Duration: `{next_track['duration']}`",
            color=0x2f3136
        )
        if next_track["thumbnail"]:
            embed.set_thumbnail(url=next_track["thumbnail"])
        embed.set_footer(text="Enjoy the stream session matrix 🔊")
        bot.loop.create_task(ctx.send(view=embed_to_view(embed)))
    else:
        now_playing.pop(guild_id, None)
        bot.loop.create_task(ctx.send("🏁 **Queue completed.** The audio stream has finished."))

@bot.hybrid_command(name="play", description="Play or queue a song in your voice channel")
@app_commands.describe(search_or_url="Song name, search term, or a direct URL")
async def play_audio_command(ctx, *, search_or_url: str = None):
    if not ctx.author.voice:
        await ctx.send(view=quick_card_view("❌ You must join a voice channel first!"))
        return

    if search_or_url is None and ctx.message and ctx.message.attachments:
        search_or_url = ctx.message.attachments[0].url

    if not search_or_url:
        await ctx.send(view=quick_card_view("❌ Provide a track name or URL! Syntax: `?play <song title or link>`"))
        return

    vc = ctx.voice_client
    if not vc:
        vc = await ctx.author.voice.channel.connect()

    async with ctx.typing():
        info = None
        stream_url = None
        
        # Try SoundCloud search loop first to handle cloud engines safely
        try:
            with yt_dlp.YoutubeDL({'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True, 'default_search': 'scsearch'}) as ydl:
                info = ydl.extract_info(search_or_url, download=False)
                if 'entries' in info and len(info['entries']) > 0:
                    info = info['entries'][0]
                elif 'entries' in info and len(info['entries']) == 0:
                    info = None
                
                if info:
                    stream_url = info['url']
        except Exception:
            info = None  

        # Fallback Strategy: If SoundCloud fails or hits DRM, automatically use alternate parsing
        if not stream_url:
            try:
                with yt_dlp.YoutubeDL({'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True, 'default_search': 'ytsearch'}) as ydl:
                    info = ydl.extract_info(search_or_url, download=False)
                    if 'entries' in info:
                        info = info['entries'][0]
                    stream_url = info['url']
            except Exception as e:
                await ctx.send(view=quick_card_view(f"❌ Failed to parse media details from all engine paths: {e}"))
                return

        song_title = info.get('title', 'Unknown Track') if info else 'Unknown Track'
        thumbnail = info.get('thumbnail', None) if info else None
        duration_secs = info.get('duration', 0) if info else 0
        duration_str = str(datetime.timedelta(seconds=duration_secs))[2:7] if duration_secs else "Live Stream"

    guild_id = ctx.guild.id
    if guild_id not in song_queues:
        song_queues[guild_id] = []

    track_data = {
        "url": stream_url,
        "title": song_title,
        "duration": duration_str,
        "thumbnail": thumbnail,
        "ctx": ctx
    }

    ffmpeg_options = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn',
        'ffmpeg_location': FFMPEG_PATH  # Auto-detected or from env
    }

    if vc.is_playing():
        song_queues[guild_id].append(track_data)
        position = len(song_queues[guild_id])
        
        embed = discord.Embed(
            title=f"Queued at position #{position}",
            description=f"**[{song_title}]({stream_url})**\n⏱️ Duration: `[{duration_str}]`",
            color=0x1E1F22
        )
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        embed.set_footer(text="Not the correct track? Try being more specific.")
        await ctx.send(view=embed_to_view(embed))
    else:
        now_playing[guild_id] = track_data
        volume = song_volumes.get(guild_id, 1.0)
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(stream_url, **ffmpeg_options), volume=volume)
        vc.play(
            source,
            after=lambda e: play_next_in_queue(ctx)
        )
        # ✅ FIXED: This embed block is now at the correct indentation level
        embed = discord.Embed(
            title="🎶 Now Playing",
            description=f"**[{song_title}]({stream_url})**\n⏱️ Duration: `[{duration_str}]`",
            color=0x2f3136
        )
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        await ctx.send(view=embed_to_view(embed))
@bot.hybrid_command(name="skip", aliases=["s", "next"], description="Skip the current track")
async def skip_audio_command(ctx):
    vc = ctx.voice_client
    if vc and vc.is_playing():
        vc.stop()
        await ctx.send(view=quick_card_view("⏭️ **Track skipped.** Loading next active layout..."))
    else:
        await ctx.send(view=quick_card_view("❌ No active music streaming tracks detected."))

@bot.hybrid_command(name="stop", aliases=["end"], description="Stop playback and clear the queue")
async def stop_audio_command(ctx):
    guild_id = ctx.guild.id
    if guild_id in song_queues:
        song_queues[guild_id] = []
    now_playing.pop(guild_id, None)
    loop_modes[guild_id] = "off"
    vc = ctx.voice_client
    if vc and vc.is_playing():
        vc.stop()
    await ctx.send(view=quick_card_view("⏹️ **Playback halted.** Core audio queues flushed completely."))

@bot.hybrid_command(name="leave", aliases=["dc", "disconnect"], description="Disconnect the bot from voice")
async def leave_voice_command(ctx):
    vc = ctx.voice_client
    if vc:
        guild_id = ctx.guild.id
        song_queues.pop(guild_id, None)
        now_playing.pop(guild_id, None)
        await vc.disconnect()
        await ctx.send(view=quick_card_view("👋 **Disconnected successfully** from local voice rooms."))
    else:
        await ctx.send(view=quick_card_view("❌ I am not connected to any voice rooms."))

@bot.hybrid_command(name="queue", aliases=["q"], description="Show the current music queue")
async def queue_command(ctx):
    guild_id = ctx.guild.id
    queue = song_queues.get(guild_id, [])
    current = now_playing.get(guild_id)

    if not current and not queue:
        await ctx.send(view=quick_card_view("📭 Nothing is playing and the queue is empty."))
        return

    embed = discord.Embed(title="🎶 Music Queue", color=0x2f3136)
    if current:
        embed.add_field(
            name="▶️ Now Playing",
            value=f"**[{current['title']}]({current['url']})** — `{current['duration']}`",
            inline=False,
        )
    if queue:
        lines = [f"**{i}.** [{t['title']}]({t['url']}) — `{t['duration']}`" for i, t in enumerate(queue[:10], 1)]
        embed.add_field(name=f"⏭️ Up Next ({len(queue)})", value="\n".join(lines), inline=False)
        if len(queue) > 10:
            embed.set_footer(text=f"...and {len(queue) - 10} more track(s) queued.")
    else:
        embed.add_field(name="⏭️ Up Next", value="Queue is empty.", inline=False)
    await ctx.send(view=embed_to_view(embed))

@bot.hybrid_command(name="nowplaying", aliases=["np"], description="Show what's currently playing")
async def nowplaying_command(ctx):
    current = now_playing.get(ctx.guild.id)
    if not current:
        await ctx.send(view=quick_card_view("❌ Nothing is currently playing."))
        return

    embed = discord.Embed(
        title="🎶 Now Playing",
        description=f"**[{current['title']}]({current['url']})**\n⏱️ Duration: `{current['duration']}`",
        color=0x2f3136,
    )
    if current.get("thumbnail"):
        embed.set_thumbnail(url=current["thumbnail"])
    vol = int(song_volumes.get(ctx.guild.id, 1.0) * 100)
    mode = loop_modes.get(ctx.guild.id, "off")
    embed.set_footer(text=f"🔊 Volume: {vol}%  •  🔁 Loop: {mode}")
    await ctx.send(view=embed_to_view(embed))

@bot.hybrid_command(name="volume", aliases=["vol"], description="Get or set the playback volume")
@app_commands.describe(percent="Volume percentage (0-200)")
async def volume_command(ctx, percent: int = None):
    guild_id = ctx.guild.id
    if percent is None:
        current_vol = int(song_volumes.get(guild_id, 1.0) * 100)
        await ctx.send(view=quick_card_view(f"🔊 Current volume: **{current_vol}%**. Usage: `?volume <0-200>`"))
        return

    percent = max(0, min(200, percent))
    song_volumes[guild_id] = percent / 100

    vc = ctx.voice_client
    if vc and vc.source and isinstance(vc.source, discord.PCMVolumeTransformer):
        vc.source.volume = percent / 100

    await ctx.send(view=quick_card_view(f"🔊 Volume set to **{percent}%**."))

@bot.hybrid_command(name="loop", description="Set the loop mode (off, track, or queue)")
@app_commands.describe(mode="off, track, or queue")
async def loop_command(ctx, mode: str = None):
    guild_id = ctx.guild.id
    valid_modes = ["off", "track", "queue"]
    if mode is None or mode.lower() not in valid_modes:
        current_mode = loop_modes.get(guild_id, "off")
        await ctx.send(view=quick_card_view(f"🔁 Usage: `?loop <off|track|queue>`. Current mode: **{current_mode}**"))
        return

    loop_modes[guild_id] = mode.lower()
    await ctx.send(view=quick_card_view(f"🔁 Loop mode set to **{mode.lower()}**."))

@bot.hybrid_command(name="like", description="Save a song link to your personal playlist")
@app_commands.describe(song_url="Link to the track", title="Title to save it under")
async def like_song_command(ctx, song_url: str = None, *, title: str = "Saved Track"):
    if song_url is None and ctx.message and ctx.message.attachments:
        song_url = ctx.message.attachments[0].url

    if not song_url:
        await ctx.send(view=quick_card_view("❌ Specify a link or attach a track file to save! Syntax: `?like <url> [title]`"))
        return

    add_liked_song(ctx.author.id, title, song_url)
    await ctx.send(view=quick_card_view(f"❤️ **Track Saved!** Added **'{title}'** directly to your personal Database Playlist."))

@bot.hybrid_command(name="playlist", description="View, play, or clear your saved playlist")
@app_commands.describe(action="view, play, or clear")
async def view_or_play_playlist(ctx, action: str = "view"):
    songs = get_liked_songs(ctx.author.id)
    if not songs:
        await ctx.send(view=quick_card_view("💔 Your private Liked Playlist is empty! Log songs using `?like <url>` first."))
        return

    if action.lower() == "play":
        if not ctx.author.voice:
            await ctx.send(view=quick_card_view("❌ You must join a voice channel first!"))
            return
        vc = ctx.voice_client
        if not vc: vc = await ctx.author.voice.channel.connect()

        guild_id = ctx.guild.id
        if guild_id not in song_queues: song_queues[guild_id] = []

        for title, url in songs:
            song_queues[guild_id].append({"url": url, "title": title, "duration": "Saved Track", "thumbnail": None, "ctx": ctx})

        await ctx.send(view=quick_card_view(f"📦 Loaded **{len(songs)} tracks** out of your playlist directly into active queues!"))
        if not vc.is_playing():
            play_next_in_queue(ctx)
    elif action.lower() == "clear":
        clear_liked_songs(ctx.author.id)
        await ctx.send(view=quick_card_view("🗑️ Your Liked Playlist ledger has been wiped out completely."))
    else:
        embed = discord.Embed(title=f"❤️ {ctx.author.display_name}'s Private Playlist Ledger", color=discord.Color.magenta())
        description_text = ""
        for i, (title, url) in enumerate(songs, 1):
            description_text += f"**{i}. {title}**\n🔗 [Stream Track]({url})\n\n"
        embed.description = description_text
        await ctx.send(view=embed_to_view(embed))



from bot.ui.premium_cards import quick_card_view, style_card_view, embed_to_view
"""
reaction_roles.py — Reaction role panels and role menus.
Extracted from the original monolithic bot.py. Logic unchanged.
"""
import discord
from discord.ext import commands
import discord.app_commands as app_commands
import asyncio
import re

from bot.config import bot, style_embed, staff_check
from bot.database import (
    add_reaction_role, remove_reaction_role, get_reaction_role,
    add_role_menu_items, get_role_menu_items, get_all_role_menu_message_ids,
    delete_role_menu,
)
from bot import mongo_bridge

async def reaction_panel_post_loop():
    """Every ~20s (right after mongo_bridge refreshes), checks each guild for
    reaction-role panels created on the dashboard that the bot hasn't posted
    to Discord yet, posts them, and writes the resulting message id back so
    they're only posted once."""
    await bot.wait_until_ready()
    while not bot.is_closed():
        if mongo_bridge.enabled():
            for guild in bot.guilds:
                for panel in mongo_bridge.get_unposted_panels(guild.id):
                    await _post_reaction_panel(guild, panel)
        await asyncio.sleep(20)


async def _post_reaction_panel(guild: discord.Guild, panel: dict):
    channel = discord.utils.get(guild.text_channels, name=panel.get("channel", ""))
    if not channel:
        return
    mappings = panel.get("mappings", [])
    if not mappings:
        return
    lines = [f"{m['emoji']} — **{m['role']}**" + (f"\n> {m['description']}" if m.get("description") else "") for m in mappings]
    embed = discord.Embed(
        title=panel.get("title", "Reaction Roles"),
        description="React below to get a role!\n\n" + "\n".join(lines),
        color=discord.Color.blurple(),
    )
    try:
        message = await channel.send(view=embed_to_view(embed))
        for m in mappings:
            try:
                await message.add_reaction(m["emoji"])
            except Exception:
                pass  # invalid/unavailable emoji — skip it, don't block the rest of the panel
        await mongo_bridge.mark_panel_posted(panel.get("_id"), message.id)
    except discord.Forbidden:
        pass


def _emoji_key(payload_emoji) -> str:
    # Custom emojis need their ID to match reliably; unicode emojis use the name/string directly.
    return str(payload_emoji.id) if payload_emoji.id else str(payload_emoji.name)


async def _resolve_panel_role(guild, panel, mapping):
    return discord.utils.get(guild.roles, name=mapping.get("role", ""))


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.user_id == bot.user.id or payload.guild_id is None:
        return
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    member = guild.get_member(payload.user_id)
    if not member:
        return

    panel = mongo_bridge.find_panel_by_message(payload.guild_id, payload.message_id) if mongo_bridge.enabled() else None
    if panel:
        mapping = mongo_bridge.find_mapping(panel, _emoji_key(payload.emoji))
        if not mapping:
            return
        role = await _resolve_panel_role(guild, panel, mapping)
        if not role:
            return
        panel_type = panel.get("type", "normal")
        try:
            if panel_type == "unique":
                # Only one role from this panel at a time — drop any other
                # mapped roles the member currently holds before adding the new one.
                other_role_names = {m["role"] for m in panel.get("mappings", []) if m["role"] != mapping["role"]}
                other_roles = [r for r in member.roles if r.name in other_role_names]
                if other_roles:
                    await member.remove_roles(*other_roles, reason="Reaction role: unique panel switch")
                await member.add_roles(role, reason=f"Reaction role panel: {panel.get('title')}")
            elif panel_type == "limit":
                panel_role_names = {m["role"] for m in panel.get("mappings", [])}
                current_count = sum(1 for r in member.roles if r.name in panel_role_names)
                max_roles = panel.get("maxRoles") or 1
                if current_count >= max_roles:
                    channel = guild.get_channel(payload.channel_id)
                    if channel:
                        try:
                            msg = await channel.fetch_message(payload.message_id)
                            await msg.remove_reaction(payload.emoji, member)
                        except Exception:
                            pass
                    return
                await member.add_roles(role, reason=f"Reaction role panel: {panel.get('title')}")
            else:  # 'normal' and 'verify' both just grant on react
                await member.add_roles(role, reason=f"Reaction role panel: {panel.get('title')}")
        except discord.Forbidden:
            pass
        return

    # Legacy fallback: messages bound via the older `!reactionrole` command.
    role_id = get_reaction_role(payload.message_id, _emoji_key(payload.emoji))
    if not role_id:
        return
    role = guild.get_role(role_id)
    if role:
        try:
            await member.add_roles(role, reason="Reaction role")
        except discord.Forbidden:
            pass

@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    if payload.guild_id is None:
        return
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    member = guild.get_member(payload.user_id)
    if not member:
        return

    panel = mongo_bridge.find_panel_by_message(payload.guild_id, payload.message_id) if mongo_bridge.enabled() else None
    if panel:
        # 'verify' panels are one-way: unreacting never takes the role back.
        if panel.get("type") == "verify":
            return
        mapping = mongo_bridge.find_mapping(panel, _emoji_key(payload.emoji))
        if not mapping:
            return
        role = await _resolve_panel_role(guild, panel, mapping)
        if role:
            try:
                await member.remove_roles(role, reason=f"Reaction role panel removed: {panel.get('title')}")
            except discord.Forbidden:
                pass
        return

    # Legacy fallback
    role_id = get_reaction_role(payload.message_id, _emoji_key(payload.emoji))
    if not role_id:
        return
    role = guild.get_role(role_id)
    if role:
        try:
            await member.remove_roles(role, reason="Reaction role removed")
        except discord.Forbidden:
            pass

@bot.hybrid_command(name="reactionrole", aliases=["rr"], description="Bind or remove an emoji-role reaction on a message")
@staff_check("admin")
@app_commands.describe(message_id="The ID of the message to bind to", emoji="The emoji to react with", role="Role to grant (omit to remove the binding)")
async def reaction_role_command(ctx, message_id: str, emoji: str, role: discord.Role = None):
    """
    Binds an emoji on a message to a role, or removes a binding.
    Usage: ?rr <message_id> <emoji> @role   -> add a binding
           ?rr <message_id> <emoji>         -> remove a binding
    """
    try:
        message_id = int(message_id)
    except ValueError:
        await ctx.send(view=quick_card_view("❌ That doesn't look like a valid message ID."))
        return

    try:
        target_message = await ctx.channel.fetch_message(message_id)
    except discord.NotFound:
        await ctx.send(view=quick_card_view("❌ Couldn't find that message in this channel. Run this command in the same channel as the message."))
        return

    custom_emoji_match = re.match(r"<a?:\w+:(\d+)>", emoji)
    key = custom_emoji_match.group(1) if custom_emoji_match else emoji

    if role is None:
        remove_reaction_role(message_id, key)
        await ctx.send(view=quick_card_view(f"✅ Removed reaction role binding for {emoji} on that message."))
        return

    add_reaction_role(ctx.guild.id, message_id, key, role.id)
    try:
        await target_message.add_reaction(emoji)
    except discord.HTTPException:
        await ctx.send(view=quick_card_view(f"⚠️ Binding saved, but I couldn't react with {emoji} myself — add it manually so people have something to click."))
        return
    await ctx.send(view=quick_card_view(f"✅ {emoji} on that message now grants {role.mention}."))



"""
revenue.py — Revenue Tracking System for Service Servers
Auto-detects revenue reports, validates format, and generates reports.
"""
import discord
from discord.ext import commands
import discord.app_commands as app_commands
import datetime
import re
from collections import defaultdict

from bot.config import (
    bot, style_embed, BRAND_COLOR, UTC, staff_check, is_staff,
    EMOJI_BULLET, BRAND_EMOJI
)
from bot.revenue_database import (
    add_revenue_entry, get_revenue_entries, get_revenue_summary,
    get_revenue_channel, set_revenue_channel, clear_revenue_channel,
    get_multi_staff_entries, get_total_entries_count
)

# Expected format (FLEXIBLE):
# User : @username OR User : plain_name
# Service : service_name (e.g., leopard, tiger, dough)
# Payment : payment_method (e.g., portal, cashapp, robux)
# Paid to : @staff_member OR Paid to : plain_name
# Done by : @helper OR helper_name (OPTIONAL - for team sales)

# Pattern matches both @mentions and plain text names
REVENUE_PATTERN = re.compile(
    r"User\s*:\s*(?:<@!?(\d+)>|(.+?))(?:\n|$).*?"
    r"Service\s*:\s*(.+?)(?:\n|$).*?"
    r"Payment\s*:\s*(.+?)(?:\n|$).*?"
    r"Paid\s*to\s*:\s*(?:<@!?(\d+)>|(.+?))(?:\n|$).*?"
    r"(?:Done\s*by\s*:\s*(?:<@!?(\d+)>|(.+?))(?:\n|$))?",
    re.IGNORECASE | re.DOTALL
)

CORRECT_FORMAT = """
**Correct Format:**
```
User : @username OR customer_name
Service : fruit_name (e.g., leopard, tiger, dough)
Payment : payment_method (e.g., portal, cashapp, robux)
Paid to : @staff OR staff_name
Done by : @helper OR helper_name (OPTIONAL)
```

**Examples:**
```
User : @HINATA
Service : leopard
Payment : portal
Paid to : @Roger
```

```
User : HINATA
Service : tiger premium
Payment : cashapp
Paid to : Roger
Done by : Detrox
```
"""


async def validate_and_record_revenue(message: discord.Message):
    """
    Auto-detect revenue reports in the designated channel.
    Validates format, stores in database, and provides feedback.
    """
    # Check if this is the revenue channel
    revenue_channel_id = get_revenue_channel(message.guild.id)
    if not revenue_channel_id or message.channel.id != revenue_channel_id:
        return False
    
    # Skip bot messages and commands
    if message.author.bot or message.content.startswith("?"):
        return False
    
    # Try to parse the revenue report
    match = REVENUE_PATTERN.search(message.content)
    
    if not match:
        # Invalid format - notify and delete
        try:
            warning = await message.reply(
                f"❌ {message.author.mention} **Invalid revenue report format!**\n{CORRECT_FORMAT}",
                mention_author=True
            )
            await message.delete()
            await warning.delete(delay=15)
        except Exception:
            pass
        return True
    
    # Extract data (supports both @mentions and plain names)
    user_id_str = match.group(1)  # @mention ID or None
    user_name = match.group(2)     # plain name or None
    service = match.group(3).strip()
    payment_method = match.group(4).strip()
    paid_to_id_str = match.group(5)  # @mention ID or None
    paid_to_name = match.group(6)    # plain name or None
    done_by_id_str = match.group(7)  # @mention ID or None (OPTIONAL)
    done_by_name = match.group(8)    # plain name or None (OPTIONAL)
    
    # Determine user (prefer @mention, fallback to name)
    if user_id_str:
        user_id = int(user_id_str)
        user = message.guild.get_member(user_id)
        user_display = user.display_name if user else f"User {user_id}"
    else:
        user_name = user_name.strip()
        user_id = 0  # Placeholder for plain name
        user_display = user_name
    
    # Determine paid_to (prefer @mention, fallback to name)
    if paid_to_id_str:
        paid_to_id = int(paid_to_id_str)
        paid_to = message.guild.get_member(paid_to_id)
        paid_to_display = paid_to.display_name if paid_to else f"User {paid_to_id}"
    else:
        paid_to_name = paid_to_name.strip()
        paid_to_id = 0  # Placeholder for plain name
        paid_to_display = paid_to_name
    
    # Determine done_by (OPTIONAL - prefer @mention, fallback to name)
    done_by_id = 0
    done_by_display = None
    if done_by_id_str:
        done_by_id = int(done_by_id_str)
        done_by = message.guild.get_member(done_by_id)
        done_by_display = done_by.display_name if done_by else f"User {done_by_id}"
    elif done_by_name:
        done_by_name = done_by_name.strip()
        done_by_id = 0
        done_by_display = done_by_name
    
    # Record in database
    try:
        add_revenue_entry(
            guild_id=message.guild.id,
            user_id=user_id,
            user_name=user_display,
            service=service,
            payment_method=payment_method,
            paid_to_id=paid_to_id,
            paid_to_name=paid_to_display,
            done_by_id=done_by_id,
            done_by_name=done_by_display,
            recorded_by_id=message.author.id
        )
        
        # React to confirm
        await message.add_reaction("✅")
        await message.add_reaction("💰")
        
    except Exception as e:
        print(f"Error recording revenue: {e}")
        try:
            await message.reply(
                f"❌ Failed to record revenue entry. Please contact an administrator.",
                delete_after=10
            )
        except Exception:
            pass
    
    return True


# ==========================================
#           REVENUE SETUP COMMANDS
# ==========================================

@bot.command(name="setrevenuechannel", help="Set the revenue tracking channel (staff/mod only)")
@staff_check(need="mod")
async def set_revenue_channel_cmd(ctx: commands.Context, channel: discord.TextChannel):
    """Set which channel should be monitored for revenue reports."""
    set_revenue_channel(ctx.guild.id, channel.id)
    
    embed = style_embed(
        title="Revenue Tracking Enabled",
        description=f"Revenue reports will now be tracked in {channel.mention}.\n\n"
                    f"Staff can post reports using this format:\n{CORRECT_FORMAT}",
        kind="success"
    )
    await ctx.send(embed=embed)


@bot.command(name="clearrevenuechannel", help="Disable revenue tracking (staff only)")
@staff_check(need="admin")
async def clear_revenue_channel_cmd(ctx: commands.Context):
    """Stop tracking revenue reports."""
    clear_revenue_channel(ctx.guild.id)
    
    embed = style_embed(
        title="Revenue Tracking Disabled",
        description="Revenue tracking has been disabled for this server.",
        kind="info"
    )
    await ctx.send(embed=embed)


# ==========================================
#         REVENUE REPORT COMMANDS
# ==========================================

@bot.command(name="weekrevenue", aliases=["week", "weeklyrevenue"], help="Show revenue for the past 7 days")
@staff_check(need="mod")
async def week_revenue(ctx: commands.Context):
    """Display weekly revenue summary grouped by staff member."""
    await generate_revenue_report(ctx, days=7, period_name="Weekly")


@bot.command(name="monthrevenue", aliases=["month", "monthlyrevenue"], help="Show revenue for the past 30 days")
@staff_check(need="mod")
async def month_revenue(ctx: commands.Context):
    """Display monthly revenue summary grouped by staff member."""
    await generate_revenue_report(ctx, days=30, period_name="Monthly")


@bot.command(name="todayrevenue", aliases=["today", "dailyrevenue"], help="Show revenue for today")
@staff_check(need="mod")
async def today_revenue(ctx: commands.Context):
    """Display today's revenue summary."""
    await generate_revenue_report(ctx, days=1, period_name="Today's")


@bot.command(name="allrevenue", aliases=["totalrevenue"], help="Show all-time revenue")
@staff_check(need="admin")
async def all_revenue(ctx: commands.Context):
    """Display all-time revenue summary."""
    await generate_revenue_report(ctx, days=None, period_name="All-Time")


async def generate_revenue_report(ctx: commands.Context, days: int = None, period_name: str = "Revenue"):
    """Generate a formatted revenue report grouped by staff and showing services provided."""
    
    # Get all entries
    entries = get_revenue_entries(ctx.guild.id, days=days)
    
    if not entries:
        embed = style_embed(
            title=f"{period_name} Revenue Report",
            description="No revenue entries found for this period.",
            kind="info"
        )
        await ctx.send(embed=embed)
        return
    
    # Group by staff member, then by service
    # Separate: single staff vs multi-staff (with done_by)
    single_staff_data = defaultdict(lambda: {'services': defaultdict(int), 'payments': defaultdict(int)})
    multi_staff_data = defaultdict(lambda: {'services': defaultdict(int), 'payments': defaultdict(int)})
    total_entries = len(entries)
    
    for user_id, user_name, service, payment_method, paid_to_id, paid_to_name, done_by_id, done_by_name, recorded_by_id, created_at in entries:
        # Get staff name (prefer Discord member, fallback to stored name)
        if paid_to_id and paid_to_id != 0:
            staff_member = ctx.guild.get_member(paid_to_id)
            staff_key = staff_member.display_name if staff_member else paid_to_name
        else:
            staff_key = paid_to_name
        
        # Check if multi-staff (done_by exists)
        if done_by_name and done_by_name.strip():
            # Multi-staff service - create combined key
            multi_key = f"{staff_key} & {done_by_name}"
            multi_staff_data[multi_key]['services'][service] += 1
            multi_staff_data[multi_key]['payments'][payment_method] += 1
        else:
            # Single staff service
            single_staff_data[staff_key]['services'][service] += 1
            single_staff_data[staff_key]['payments'][payment_method] += 1
    
    # Build the report
    description = f"📊 **Total Transactions:** {total_entries}\n\n"
    
    # Single staff section
    sorted_staff = sorted(single_staff_data.items(), key=lambda x: sum(x[1]['services'].values()), reverse=True)
    
    for staff_name, data in sorted_staff:
        services = data['services']
        payments = data['payments']
        staff_total = sum(services.values())
        
        description += f"**{EMOJI_BULLET} {staff_name}** ({staff_total} ticket{'s' if staff_total != 1 else ''} done)\n\n"
        
        # Services section
        description += f"**Services:**\n"
        sorted_services = sorted(services.items(), key=lambda x: x[1], reverse=True)
        for service, count in sorted_services[:10]:
            description += f"   • {service}: `{count}x`\n"
        
        if len(sorted_services) > 10:
            remaining = sum(s[1] for s in sorted_services[10:])
            description += f"   • ... and {len(sorted_services) - 10} more (`{remaining}x`)\n"
        
        description += "\n"
        
        # Payment methods section
        description += f"**💳 Payments:**\n"
        sorted_payments = sorted(payments.items(), key=lambda x: x[1], reverse=True)
        for method, cnt in sorted_payments:
            description += f"   • {method}: `{cnt}x`\n"
        
        description += "\n"
    
    # Multi-staff section (if any)
    if multi_staff_data:
        multi_total = sum(sum(d['services'].values()) for d in multi_staff_data.values())
        description += "━━━━━━━━━━━━━━━━━━━━━━\n"
        description += f"**👥 MULTI-STAFF SERVICES** ({multi_total} ticket{'s' if multi_total != 1 else ''})\n\n"
        
        sorted_multi = sorted(multi_staff_data.items(), key=lambda x: sum(x[1]['services'].values()), reverse=True)
        
        for staff_names, data in sorted_multi:
            services = data['services']
            payments = data['payments']
            multi_staff_total = sum(services.values())
            
            description += f"**{EMOJI_BULLET} {staff_names}** ({multi_staff_total} ticket{'s' if multi_staff_total != 1 else ''})\n\n"
            
            # Services
            description += f"**Services:**\n"
            sorted_services = sorted(services.items(), key=lambda x: x[1], reverse=True)
            for service, count in sorted_services[:10]:
                description += f"   • {service}: `{count}x`\n"
            
            description += "\n"
            
            # Payments
            description += f"**💳 Payments:**\n"
            sorted_payments = sorted(payments.items(), key=lambda x: x[1], reverse=True)
            for method, cnt in sorted_payments:
                description += f"   • {method}: `{cnt}x`\n"
            
            description += "\n"
    
    embed = style_embed(
        title=f"{BRAND_EMOJI} {period_name} Revenue Report {BRAND_EMOJI}",
        description=description,
        color=BRAND_COLOR,
        kind="info"
    )
    
    # Add timestamp
    embed.set_footer(text=f"United Bunnies Revenue System • Generated at {datetime.datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}")
    
    await ctx.send(embed=embed)


@bot.command(name="revenuedetails", aliases=["revdetails"], help="Show detailed revenue entries (last 10)")
@staff_check(need="mod")
async def revenue_details(ctx: commands.Context, days: int = 7):
    """Show detailed list of recent revenue entries."""
    
    entries = get_revenue_entries(ctx.guild.id, days=days)
    
    if not entries:
        embed = style_embed(
            title="Revenue Details",
            description=f"No revenue entries found in the last {days} days.",
            kind="info"
        )
        await ctx.send(embed=embed)
        return
    
    # Show last 10 entries
    entries = entries[:10]
    
    description = f"**Last {len(entries)} Entries (Past {days} Days)**\n\n"
    
    for user_id, user_name, service, payment_method, paid_to_id, paid_to_name, done_by_id, done_by_name, recorded_by_id, created_at in entries:
        # Use stored names if available
        user_display = user_name if user_name else (ctx.guild.get_member(user_id).display_name if ctx.guild.get_member(user_id) else f"User {user_id}")
        staff_display = paid_to_name if paid_to_name else (ctx.guild.get_member(paid_to_id).display_name if ctx.guild.get_member(paid_to_id) else f"User {paid_to_id}")
        
        # Add "done by" if exists
        if done_by_name and done_by_name.strip():
            staff_display = f"{staff_display}, {done_by_name}"
        
        # Parse date
        try:
            date_obj = datetime.datetime.fromisoformat(created_at)
            date_str = date_obj.strftime("%m/%d %H:%M")
        except Exception:
            date_str = "Unknown"
        
        description += f"**{date_str}** • {service}\n"
        description += f"  {EMOJI_BULLET} User: {user_display} → Staff: {staff_display}\n"
        description += f"  {EMOJI_BULLET} Payment: {payment_method}\n\n"
    
    embed = style_embed(
        title=f"{BRAND_EMOJI} Revenue Details",
        description=description,
        color=BRAND_COLOR,
        kind="info"
    )
    
    embed.set_footer(text="United Bunnies Revenue System")
    
    await ctx.send(embed=embed)


@bot.command(name="revenuevia", aliases=["staffrevenue", "revvia"], help="Show revenue for a specific staff member")
@staff_check(need="mod")
async def revenue_via_staff(ctx: commands.Context, *, staff_name: str, days: int = 30):
    """Show all services provided by a specific staff member."""
    
    # Get all entries
    all_entries = get_revenue_entries(ctx.guild.id, days=days)
    
    if not all_entries:
        embed = style_embed(
            title="No Revenue Data",
            description=f"No revenue entries found in the last {days} days.",
            kind="info"
        )
        await ctx.send(embed=embed)
        return
    
    # Clean staff name (remove @ if present)
    staff_name = staff_name.strip().lstrip('@')
    
    # Filter entries for this staff member
    staff_entries = []
    matched_staff_name = None
    
    for user_id, user_name, service, payment_method, paid_to_id, paid_to_name, done_by_id, done_by_name, recorded_by_id, created_at in all_entries:
        # Get staff name for this entry
        if paid_to_id and paid_to_id != 0:
            staff_member = ctx.guild.get_member(paid_to_id)
            entry_staff_name = staff_member.display_name if staff_member else paid_to_name
        else:
            entry_staff_name = paid_to_name
        
        # Check if this matches our search (case-insensitive)
        # Also check "done_by" field
        staff_match = entry_staff_name and staff_name.lower() in entry_staff_name.lower()
        done_by_match = done_by_name and staff_name.lower() in done_by_name.lower()
        
        if staff_match or done_by_match:
            staff_entries.append((user_id, user_name, service, payment_method, created_at))
            if not matched_staff_name:
                matched_staff_name = entry_staff_name
    
    if not staff_entries:
        embed = style_embed(
            title="No Results",
            description=f"No revenue entries found for staff member matching **{staff_name}**.",
            kind="info"
        )
        await ctx.send(embed=embed)
        return
    
    # Analyze the data
    services_count = defaultdict(int)
    payments_count = defaultdict(int)
    clients = set()
    
    for user_id, user_name, service, payment_method, created_at in staff_entries:
        services_count[service] += 1
        payments_count[payment_method] += 1
        clients.add(user_name if user_name else user_id)
    
    total_sales = len(staff_entries)
    
    # Build the report
    description = f"**Staff Member:** {matched_staff_name}\n"
    description += f"**Period:** Last {days} days\n"
    description += f"**Total Tickets:** `{total_sales}`\n"
    description += f"**Unique Clients:** `{len(clients)}`\n\n"
    
    # Services provided (sorted by count)
    description += "**Services:**\n"
    sorted_services = sorted(services_count.items(), key=lambda x: x[1], reverse=True)
    for service, count in sorted_services[:15]:  # Top 15
        percentage = (count/total_sales*100)
        description += f"   • {service}: `{count}x` ({percentage:.1f}%)\n"
    
    if len(sorted_services) > 15:
        remaining = sum(s[1] for s in sorted_services[15:])
        description += f"   • ... and {len(sorted_services) - 15} more (`{remaining}x`)\n"
    
    description += "\n"
    
    # Payment methods breakdown
    description += "**💳 Payments:**\n"
    sorted_payments = sorted(payments_count.items(), key=lambda x: x[1], reverse=True)
    for payment, count in sorted_payments:
        percentage = (count/total_sales*100)
        description += f"   • {payment}: `{count}x` ({percentage:.1f}%)\n"
    
    embed = style_embed(
        title=f"{BRAND_EMOJI} Staff Revenue Report",
        description=description,
        color=BRAND_COLOR,
        kind="info"
    )
    
    embed.set_footer(text=f"United Bunnies Revenue System • Use ?revenuevia \"staff name\" <days>")
    
    await ctx.send(embed=embed)


@bot.command(name="revenuehelp", aliases=["revhelp"], help="Show revenue system help")
async def revenue_help(ctx: commands.Context):
    """Display help for the revenue tracking system."""
    
    embed = style_embed(
        title=f"{BRAND_EMOJI} Revenue Tracking System",
        description="Automatically track service revenue and generate reports.",
        color=BRAND_COLOR,
        kind="info"
    )
    
    embed.add_field(
        name="📝 How to Report Revenue",
        value=CORRECT_FORMAT,
        inline=False
    )
    
    embed.add_field(
        name="📊 Staff Commands",
        value=(
            "`?weekrevenue` - Weekly revenue summary\n"
            "`?monthrevenue` - Monthly revenue summary\n"
            "`?todayrevenue` - Today's revenue\n"
            "`?allrevenue` - All-time revenue (Admin only)\n"
            "`?revenuedetails [days]` - Detailed transaction list\n"
            "`?revenuevia \"staff name\" [days]` - Specific staff's sales\n"
        ),
        inline=False
    )
    
    embed.add_field(
        name="⚙️ Admin Commands",
        value=(
            "`?setrevenuechannel #channel` - Enable tracking in a channel\n"
            "`?clearrevenuechannel` - Disable tracking\n"
        ),
        inline=False
    )
    
    embed.set_footer(text="United Bunnies Revenue System")
    
    await ctx.send(embed=embed)


# Export the validation function for use in events.py
__all__ = ['validate_and_record_revenue']

"""
role_info.py — Role Information Commands
Shows server roles with varying levels of detail
"""
import discord
from discord.ext import commands
from typing import Dict, List

from bot.config import bot, style_embed, BRAND_COLOR, BRAND_EMOJI, staff_check, EMOJI_BULLET

# Permission descriptions (short)
PERM_SHORT_DESC = {
    'administrator': '👑 Full Control',
    'manage_guild': '⚙️ Manage Server',
    'manage_roles': '🎭 Manage Roles',
    'manage_channels': '📝 Manage Channels',
    'kick_members': '👢 Kick',
    'ban_members': '🔨 Ban',
    'moderate_members': '🔇 Timeout',
    'manage_messages': '🗑️ Manage Messages',
    'manage_nicknames': '✏️ Manage Nicknames',
    'manage_webhooks': '🔗 Manage Webhooks',
    'manage_emojis': '😀 Manage Emojis',
    'view_audit_log': '📋 View Logs',
    'mention_everyone': '📢 Mention Everyone',
    'send_messages': '💬 Send Messages',
    'manage_threads': '🧵 Manage Threads',
    'create_public_threads': '🧵 Create Threads',
    'send_messages_in_threads': '💬 Send in Threads',
    'attach_files': '📎 Attach Files',
    'embed_links': '🔗 Embed Links',
    'add_reactions': '😊 Add Reactions',
    'external_emojis': '😀 External Emojis',
    'external_stickers': '🎨 External Stickers',
    'connect': '🔊 Connect Voice',
    'speak': '🎤 Speak',
    'mute_members': '🔇 Mute Members',
    'deafen_members': '🔇 Deafen Members',
    'move_members': '↔️ Move Members',
    'use_voice_activation': '🎤 Voice Activity',
}

# Full permission descriptions
PERM_FULL_DESC = {
    'administrator': 'Administrator - Full server control, bypasses all permissions',
    'manage_guild': 'Manage Server - Change server name, region, icon, and settings',
    'manage_roles': 'Manage Roles - Create, edit, and delete roles (lower than their highest role)',
    'manage_channels': 'Manage Channels - Create, edit, and delete channels',
    'kick_members': 'Kick Members - Remove members from the server (they can rejoin)',
    'ban_members': 'Ban Members - Permanently ban members from the server',
    'moderate_members': 'Moderate Members - Timeout members (prevent them from interacting)',
    'manage_messages': 'Manage Messages - Delete messages and pin messages',
    'manage_nicknames': 'Manage Nicknames - Change other members\' nicknames',
    'manage_webhooks': 'Manage Webhooks - Create, edit, and delete webhooks',
    'manage_emojis': 'Manage Emojis and Stickers - Create, edit, and delete emojis/stickers',
    'manage_events': 'Manage Events - Create, edit, and delete scheduled events',
    'view_audit_log': 'View Audit Log - See server audit logs and moderation actions',
    'view_channel': 'View Channels - See channels (can be overridden per channel)',
    'view_guild_insights': 'View Server Insights - Access server analytics',
    'change_nickname': 'Change Nickname - Change their own nickname',
    'mention_everyone': 'Mention @everyone, @here, and All Roles - Ping entire server',
    'read_message_history': 'Read Message History - See past messages in channels',
    'send_messages': 'Send Messages - Send messages in text channels',
    'send_tts_messages': 'Send TTS Messages - Send text-to-speech messages',
    'manage_threads': 'Manage Threads - Rename, delete, archive/unarchive threads',
    'create_public_threads': 'Create Public Threads - Start threads in channels',
    'create_private_threads': 'Create Private Threads - Start private threads',
    'send_messages_in_threads': 'Send Messages in Threads - Reply in threads',
    'attach_files': 'Attach Files - Upload files and media to channels',
    'embed_links': 'Embed Links - Preview links with embeds',
    'add_reactions': 'Add Reactions - React to messages with emojis',
    'use_external_emojis': 'Use External Emojis - Use emojis from other servers',
    'use_external_stickers': 'Use External Stickers - Use stickers from other servers',
    'use_application_commands': 'Use Application Commands - Use slash commands',
    'connect': 'Connect to Voice - Join voice channels',
    'speak': 'Speak in Voice - Talk in voice channels',
    'stream': 'Video/Screen Share - Stream video or share screen',
    'use_embedded_activities': 'Use Activities - Start activities in voice channels',
    'use_soundboard': 'Use Soundboard - Play soundboard sounds',
    'use_external_sounds': 'Use External Sounds - Use sounds from other servers',
    'mute_members': 'Mute Members - Server mute members in voice',
    'deafen_members': 'Deafen Members - Server deafen members in voice',
    'move_members': 'Move Members - Move members between voice channels',
    'use_voice_activation': 'Use Voice Activity - Use voice activity detection (no push-to-talk)',
    'priority_speaker': 'Priority Speaker - Be heard more clearly in voice (louder)',
    'request_to_speak': 'Request to Speak - Request to speak in stage channels',
}


def get_key_permissions(permissions: discord.Permissions) -> List[str]:
    """Get list of important permissions (excluding basic ones)."""
    important_perms = [
        'administrator', 'manage_guild', 'manage_roles', 'manage_channels',
        'kick_members', 'ban_members', 'moderate_members', 'manage_messages',
        'manage_nicknames', 'manage_webhooks', 'view_audit_log', 'mention_everyone',
        'manage_threads', 'manage_emojis', 'manage_events'
    ]
    
    perms = []
    for perm_name in important_perms:
        if getattr(permissions, perm_name, False):
            perms.append(perm_name)
    
    return perms


def get_all_permissions(permissions: discord.Permissions) -> List[str]:
    """Get all enabled permissions."""
    perms = []
    for perm_name, value in permissions:
        if value:
            perms.append(perm_name)
    return perms


def format_role_color(role: discord.Role) -> str:
    """Format role color as hex."""
    if role.color.value == 0:
        return "Default (No Color)"
    return f"#{role.color.value:06x}"


# ==========================================
#         ROLES COMMAND (Simple List)
# ==========================================

@bot.command(name="roles", help="List all server roles (staff only)")
@staff_check(need="mod")
async def roles_cmd(ctx: commands.Context):
    """Show a simple list of all server roles."""
    roles = sorted(ctx.guild.roles, key=lambda r: r.position, reverse=True)
    
    # Exclude @everyone
    roles = [r for r in roles if r.name != "@everyone"]
    
    if not roles:
        await ctx.send(embed=style_embed(
            title="Server Roles",
            description="This server has no custom roles.",
            kind="info"
        ))
        return
    
    # Split into chunks if too many roles
    role_list = []
    for i, role in enumerate(roles, 1):
        member_count = len(role.members)
        role_list.append(f"{i}. {role.mention} • `{member_count}` member{'s' if member_count != 1 else ''}")
    
    # Create pages if needed
    chunks = []
    chunk_size = 25
    for i in range(0, len(role_list), chunk_size):
        chunks.append(role_list[i:i + chunk_size])
    
    # Send first page
    description = "\n".join(chunks[0])
    
    embed = style_embed(
        title=f"{BRAND_EMOJI} Server Roles ({len(roles)} total)",
        description=description,
        color=BRAND_COLOR,
        kind="info"
    )
    
    embed.set_footer(text=f"{ctx.guild.name} • Page 1/{len(chunks)}")
    
    await ctx.send(embed=embed)
    
    # Send additional pages if needed
    for i, chunk in enumerate(chunks[1:], 2):
        description = "\n".join(chunk)
        embed = style_embed(
            title=f"{BRAND_EMOJI} Server Roles (continued)",
            description=description,
            color=BRAND_COLOR,
            kind="info"
        )
        embed.set_footer(text=f"{ctx.guild.name} • Page {i}/{len(chunks)}")
        await ctx.send(embed=embed)


# ==========================================
#         ROLEINFO COMMAND (Key Permissions)
# ==========================================

@bot.command(name="roleinfo", help="Show role info with key permissions (staff only)")
@staff_check(need="mod")
async def roleinfo_cmd(ctx: commands.Context, *, role: discord.Role = None):
    """Show information about a role including key permissions."""
    
    if role is None:
        # Show all roles with key info
        roles = sorted(ctx.guild.roles, key=lambda r: r.position, reverse=True)
        roles = [r for r in roles if r.name != "@everyone"]
        
        if not roles:
            await ctx.send(embed=style_embed(
                title="Server Roles",
                description="This server has no custom roles.",
                kind="info"
            ))
            return
        
        # Limit to top 10 roles
        roles = roles[:10]
        
        description = ""
        for role in roles:
            key_perms = get_key_permissions(role.permissions)
            member_count = len(role.members)
            
            description += f"**{role.mention}**\n"
            description += f"  {EMOJI_BULLET} Members: `{member_count}`\n"
            description += f"  {EMOJI_BULLET} Color: `{format_role_color(role)}`\n"
            
            if key_perms:
                perm_icons = [PERM_SHORT_DESC.get(p, p) for p in key_perms[:5]]
                description += f"  {EMOJI_BULLET} Perms: {' '.join(perm_icons)}\n"
                if len(key_perms) > 5:
                    description += f"     ... +{len(key_perms) - 5} more\n"
            else:
                description += f"  {EMOJI_BULLET} Perms: No special permissions\n"
            
            description += "\n"
        
        embed = style_embed(
            title=f"{BRAND_EMOJI} Role Information",
            description=description,
            color=BRAND_COLOR,
            kind="info"
        )
        
        embed.set_footer(text=f"Showing top {len(roles)} roles • Use ?roleinfo @role for detailed info")
        
        await ctx.send(embed=embed)
    
    else:
        # Show detailed info for specific role
        key_perms = get_key_permissions(role.permissions)
        member_count = len(role.members)
        
        embed = discord.Embed(
            title=f"Role: {role.name}",
            color=role.color if role.color.value != 0 else BRAND_COLOR,
            timestamp=role.created_at
        )
        
        # Basic info
        embed.add_field(
            name="📊 Basic Info",
            value=f"**ID:** `{role.id}`\n"
                  f"**Members:** `{member_count}`\n"
                  f"**Color:** `{format_role_color(role)}`\n"
                  f"**Position:** `{role.position}`\n"
                  f"**Mentionable:** `{'Yes' if role.mentionable else 'No'}`\n"
                  f"**Hoisted:** `{'Yes' if role.hoist else 'No'}`",
            inline=False
        )
        
        # Key permissions
        if key_perms:
            perm_list = []
            for perm in key_perms:
                icon = PERM_SHORT_DESC.get(perm, perm)
                perm_list.append(icon)
            
            embed.add_field(
                name="🔑 Key Permissions",
                value="\n".join(perm_list) if perm_list else "None",
                inline=False
            )
        
        embed.set_footer(text=f"Created at")
        
        await ctx.send(embed=embed)


# ==========================================
#         ROLEFULLINFO COMMAND (All Permissions)
# ==========================================

@bot.command(name="rolefullinfo", aliases=["roledetails"], help="Show complete role information (staff only)")
@staff_check(need="mod")
async def rolefullinfo_cmd(ctx: commands.Context, *, role: discord.Role):
    """Show complete information about a role including all permissions."""
    
    all_perms = get_all_permissions(role.permissions)
    member_count = len(role.members)
    
    embed = discord.Embed(
        title=f"🔍 Complete Role Information",
        description=f"**Role:** {role.mention}",
        color=role.color if role.color.value != 0 else BRAND_COLOR,
        timestamp=role.created_at
    )
    
    # Basic info
    embed.add_field(
        name="📊 Basic Information",
        value=f"**Name:** {role.name}\n"
              f"**ID:** `{role.id}`\n"
              f"**Members:** `{member_count}`\n"
              f"**Color:** `{format_role_color(role)}`\n"
              f"**Position:** `{role.position}/{len(ctx.guild.roles)}`\n"
              f"**Mentionable:** `{'Yes' if role.mentionable else 'No'}`\n"
              f"**Display Separately:** `{'Yes' if role.hoist else 'No'}`\n"
              f"**Managed:** `{'Yes (Bot/Integration)' if role.managed else 'No'}`",
        inline=False
    )
    
    # Permissions section
    if role.permissions.administrator:
        embed.add_field(
            name="🔑 Permissions",
            value="**👑 ADMINISTRATOR**\n"
                  "This role has full control over the server and bypasses all permission checks.",
            inline=False
        )
    elif all_perms:
        # Group permissions by category
        admin_perms = []
        moderation_perms = []
        text_perms = []
        voice_perms = []
        other_perms = []
        
        for perm in all_perms:
            desc = PERM_FULL_DESC.get(perm, perm.replace('_', ' ').title())
            
            if perm in ['administrator', 'manage_guild', 'manage_roles', 'manage_channels', 'view_audit_log']:
                admin_perms.append(f"• {desc}")
            elif perm in ['kick_members', 'ban_members', 'moderate_members', 'manage_messages', 'manage_nicknames']:
                moderation_perms.append(f"• {desc}")
            elif 'message' in perm or 'thread' in perm or 'embed' in perm or 'reaction' in perm or 'emoji' in perm or 'sticker' in perm:
                text_perms.append(f"• {desc}")
            elif 'voice' in perm or 'speak' in perm or 'stream' in perm or 'sound' in perm or 'mute' in perm or 'deafen' in perm or 'connect' in perm or 'move' in perm:
                voice_perms.append(f"• {desc}")
            else:
                other_perms.append(f"• {desc}")
        
        # Add sections
        if admin_perms:
            embed.add_field(
                name="⚙️ Administrative Permissions",
                value="\n".join(admin_perms[:10]),
                inline=False
            )
        
        if moderation_perms:
            embed.add_field(
                name="🛡️ Moderation Permissions",
                value="\n".join(moderation_perms[:10]),
                inline=False
            )
        
        if text_perms:
            # Split if too many
            if len(text_perms) > 10:
                embed.add_field(
                    name="💬 Text Channel Permissions (1/2)",
                    value="\n".join(text_perms[:10]),
                    inline=False
                )
                embed.add_field(
                    name="💬 Text Channel Permissions (2/2)",
                    value="\n".join(text_perms[10:20]),
                    inline=False
                )
            else:
                embed.add_field(
                    name="💬 Text Channel Permissions",
                    value="\n".join(text_perms),
                    inline=False
                )
        
        if voice_perms:
            embed.add_field(
                name="🔊 Voice Channel Permissions",
                value="\n".join(voice_perms[:10]),
                inline=False
            )
        
        if other_perms:
            embed.add_field(
                name="🔧 Other Permissions",
                value="\n".join(other_perms[:10]),
                inline=False
            )
    else:
        embed.add_field(
            name="🔑 Permissions",
            value="This role has no special permissions.",
            inline=False
        )
    
    # Member list (first 10)
    if member_count > 0:
        members = role.members[:10]
        member_list = ", ".join([m.mention for m in members])
        if member_count > 10:
            member_list += f"\n... and {member_count - 10} more"
        
        embed.add_field(
            name=f"👥 Members ({member_count} total)",
            value=member_list,
            inline=False
        )
    
    embed.set_footer(text=f"Role created")
    
    await ctx.send(embed=embed)


@bot.command(name="rolehelp", help="Show help for role information commands")
async def rolehelp_cmd(ctx: commands.Context):
    """Show help for role commands."""
    
    embed = style_embed(
        title=f"{BRAND_EMOJI} Role Information Commands",
        description="Learn about server roles and their permissions.",
        color=BRAND_COLOR,
        kind="info"
    )
    
    embed.add_field(
        name="📋 ?roles",
        value="Show a simple list of all server roles with member counts.\n"
              "**Example:** `?roles`",
        inline=False
    )
    
    embed.add_field(
        name="🔍 ?roleinfo [@role]",
        value="Show role information with key permissions (short format).\n"
              "• No mention: Shows top 10 roles\n"
              "• With mention: Shows specific role details\n"
              "**Example:** `?roleinfo @Staff`",
        inline=False
    )
    
    embed.add_field(
        name="📖 ?rolefullinfo @role",
        value="Show COMPLETE role information with ALL permissions explained.\n"
              "Requires a role mention.\n"
              "**Example:** `?rolefullinfo @Moderator`",
        inline=False
    )
    
    embed.add_field(
        name="🔒 Permissions",
        value="These commands are **staff-only** (Moderator+ permissions required).",
        inline=False
    )
    
    embed.set_footer(text="United Bunnies Role System")
    
    await ctx.send(embed=embed)

from bot.config import style_embed
from bot.ui.premium_cards import quick_card_view, style_card_view

"""
tickets.py — Ticket system (panel, open/close/claim, manage views).
Extracted from the original monolithic bot.py. Logic unchanged.
"""

import discord
from discord.ext import commands
import discord.app_commands as app_commands
import datetime
import asyncio
import re

from bot.config import bot, style_embed, TICKET_CATEGORY_NAME, UTC, staff_check
from bot.database import (
    create_ticket_record,
    close_ticket_record,
    claim_ticket_record,
    unclaim_ticket_record,
    get_ticket_record,
    get_open_ticket_for_user,
    list_open_tickets,
    get_trusted_role_id,
)

TICKET_TYPES = {
    "general": ("🎫", "General Support"),
    "report": ("🚨", "Report a Member"),
    "billing": ("💳", "Billing / Payment"),
    "bug": ("🐛", "Bug Report"),
    "other": ("❔", "Other"),
}


async def get_or_create_ticket_category(
    guild: discord.Guild,
) -> discord.CategoryChannel:
    category = discord.utils.get(
        guild.categories,
        name=TICKET_CATEGORY_NAME,
    )

    if category is None:
        category = await guild.create_category(TICKET_CATEGORY_NAME)

    return category


async def open_new_ticket(
    guild: discord.Guild,
    user: discord.Member,
    ticket_type_key: str = "general",
) -> discord.TextChannel:
    emoji, type_label = TICKET_TYPES.get(
        ticket_type_key,
        TICKET_TYPES["general"],
    )

    category = await get_or_create_ticket_category(guild)
    
    # Tickets are visible to staff with Moderate Members permission
    # No specific role needed - uses Discord permissions

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=False
        ),
        user: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
        ),
        guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_channels=True,
        ),
    }

    # Note: Staff with Moderate Members permission can access tickets
    # No specific role overwrites needed - permission-based access via commands

    safe_name = (
        re.sub(
            r"[^a-z0-9]+",
            "-",
            user.name.lower(),
        ).strip("-")
        or "user"
    )

    channel = await guild.create_text_channel(
        name=f"ticket-{safe_name}",
        category=category,
        overwrites=overwrites,
        topic=f"{type_label} | Opened by {user} ({user.id})",
        reason=f"Ticket opened by {user}",
    )

    create_ticket_record(
        channel.id,
        guild.id,
        user.id,
        type_label,
    )

    embed = discord.Embed(
        title=f"{emoji} Ticket Opened — {type_label}",
        description=(
            f"Welcome {user.mention}! A staff member will be with you shortly.\n\n"
            f"Describe your issue below. Staff can **Claim** this ticket "
            f"to take ownership, and either side can **Close** it when resolved."
        ),
        color=0x2F3136,
        timestamp=datetime.datetime.now(UTC),
    )

    embed.set_footer(
        text=f"Ticket type: {type_label}"
    )

    await channel.send(
        content=f"{user.mention}",
        embed=embed,
        view=TicketManageView(),
    )

    return channel


class TicketTypeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=label,
                emoji=emoji,
                value=key,
            )
            for key, (emoji, label) in TICKET_TYPES.items()
        ]

        super().__init__(
            placeholder="What do you need help with?",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(
        self,
        interaction: discord.Interaction,
    ):
        existing = get_open_ticket_for_user(
            interaction.guild.id,
            interaction.user.id,
        )

        if existing:
            channel = interaction.guild.get_channel(existing)

            if channel:
                await interaction.response.edit_message(
                    content=(
                        f"❗ You already have an open ticket: "
                        f"{channel.mention}"
                    ),
                    view=None,
                )
                return

        await interaction.response.edit_message(
            content="🎫 Creating your ticket...",
            view=None,
        )

        channel = await open_new_ticket(
            interaction.guild,
            interaction.user,
            self.values[0],
        )

        await interaction.followup.send(
            f"✅ Ticket created: {channel.mention}",
            ephemeral=True,
        )


class TicketTypeSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(TicketTypeSelect())


class TicketManageView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Claim",
        style=discord.ButtonStyle.primary,
        emoji="🙋",
        custom_id="ticket_claim_button",
    )
    async def claim_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        # Staff access is managed by Discord permissions, not roles

        is_staff = (
            staff_role
            and staff_role in interaction.user.roles
        )

        if not is_staff:
            await interaction.response.send_message(
                view=quick_card_view(
                    "❌ Only staff can claim tickets."
                ),
                ephemeral=True,
            )
            return

        record = get_ticket_record(
            interaction.channel.id
        )

        if not record:
            await interaction.response.send_message(
                view=quick_card_view(
                    "❌ This isn't a ticket channel."
                ),
                ephemeral=True,
            )
            return

        _, status, _, claimed_by = record

        if claimed_by == interaction.user.id:
            unclaim_ticket_record(
                interaction.channel.id
            )

            button.label = "Claim"
            button.style = discord.ButtonStyle.primary

            await interaction.response.edit_message(
                view=self
            )

            await interaction.followup.send(
                f"↩️ {interaction.user.mention} "
                f"unclaimed this ticket."
            )
            return

        if claimed_by:
            await interaction.response.send_message(
                view=quick_card_view(
                    f"❗ This ticket is already claimed by "
                    f"<@{claimed_by}>."
                ),
                ephemeral=True,
            )
            return

        claim_ticket_record(
            interaction.channel.id,
            interaction.user.id,
        )

        button.label = (
            f"Claimed by {interaction.user.display_name}"
        )

        button.style = discord.ButtonStyle.secondary

        await interaction.response.edit_message(
            view=self
        )

        await interaction.followup.send(
            f"🙋 {interaction.user.mention} claimed this "
            f"ticket and will be assisting you."
        )

    @discord.ui.button(
        label="Add Member",
        style=discord.ButtonStyle.secondary,
        emoji="➕",
        custom_id="ticket_add_member_button",
    )
    async def add_member_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        # Staff access is managed by Discord permissions, not roles

        is_staff = (
            staff_role
            and staff_role in interaction.user.roles
        )

        if not is_staff:
            await interaction.response.send_message(
                view=quick_card_view(
                    "❌ Only staff can add members to a ticket."
                ),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "➕ Mention the member to add, e.g. "
            "`@username` (paste it as your next message here — staff only).",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="ticket_close_button",
    )
    async def close_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        # Staff access is managed by Discord permissions, not roles

        is_staff = (
            staff_role
            and staff_role in interaction.user.roles
        )

        record = get_ticket_record(
            interaction.channel.id
        )

        is_owner = (
            record
            and record[0] == interaction.user.id
        )

        if not (is_staff or is_owner):
            await interaction.response.send_message(
                view=quick_card_view(
                    "❌ Only the ticket opener or staff can close this ticket."
                ),
                ephemeral=True,
            )
            return

        close_ticket_record(
            interaction.channel.id
        )

        await interaction.response.send_message(
            view=quick_card_view(
                "🔒 **Closing this ticket in 5 seconds...**"
            )
        )

        await asyncio.sleep(5)

        try:
            await interaction.channel.delete(
                reason=f"Ticket closed by {interaction.user}"
            )
        except discord.NotFound:
            pass


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Create Ticket",
        style=discord.ButtonStyle.primary,
        emoji="🎫",
        custom_id="ticket_create_button",
    )
    async def create_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        existing = get_open_ticket_for_user(
            interaction.guild.id,
            interaction.user.id,
        )

        if existing:
            channel = interaction.guild.get_channel(existing)

            if channel:
                await interaction.response.send_message(
                    view=quick_card_view(
                        f"❗ You already have an open ticket: "
                        f"{channel.mention}"
                    ),
                    ephemeral=True,
                )
                return

        await interaction.response.send_message(
            view=TicketTypeSelectView(),
            content="🎫 **What do you need help with?**",
            ephemeral=True,
        )


@bot.hybrid_command(
    name="ticketpanel",
    aliases=["tp"],
    description="[Staff] Post a button-based ticket-creation panel",
)
@commands.has_role(REQUIRED_ROLE_ID)
async def ticket_panel_prefix(ctx):
    embed = discord.Embed(
        title="🎫 Support Tickets",
        description=(
            "Need help? Click the button below to open "
            "a private ticket with staff."
        ),
        color=0x2F3136,
    )

    await ctx.send(
        embed=embed,
        view=TicketPanelView(),
    )


@bot.hybrid_command(
    name="ticket",
    description="Open a private support ticket",
)
async def ticket_prefix(ctx):
    existing = get_open_ticket_for_user(
        ctx.guild.id,
        ctx.author.id,
    )

    if existing:
        channel = ctx.guild.get_channel(existing)

        if channel:
            await ctx.send(
                view=quick_card_view(
                    f"❗ You already have an open ticket: "
                    f"{channel.mention}"
                )
            )
            return

    await ctx.send(
        content="🎫 **What do you need help with?**",
        view=TicketTypeSelectView(),
    )


@bot.hybrid_command(
    name="closeticket",
    aliases=["close"],
    description="Close the ticket you're currently in",
)
async def close_ticket_prefix(ctx):
    record = get_ticket_record(
        ctx.channel.id
    )

    if not record:
        await ctx.send(
            view=quick_card_view(
                "❌ This isn't a ticket channel."
            )
        )
        return

    # Staff access is managed by Discord permissions, not roles

    is_staff = (
        staff_role
        and staff_role in ctx.author.roles
    )

    is_owner = (
        record[0] == ctx.author.id
    )

    if not (is_staff or is_owner):
        await ctx.send(
            view=quick_card_view(
                "❌ Only the ticket opener or staff can close this ticket."
            )
        )
        return

    close_ticket_record(
        ctx.channel.id
    )

    await ctx.send(
        view=quick_card_view(
            "🔒 **Closing this ticket in 5 seconds...**"
        )
    )

    await asyncio.sleep(5)

    try:
        await ctx.channel.delete(
            reason=f"Ticket closed by {ctx.author}"
        )
    except discord.NotFound:
        pass


@bot.hybrid_command(
    name="tickets",
    aliases=["ticketlist"],
    description="[Staff] List all currently open tickets",
)
@commands.has_role(REQUIRED_ROLE_ID)
async def list_tickets_prefix(ctx):
    rows = list_open_tickets(
        ctx.guild.id
    )

    if not rows:
        await ctx.send(
            view=quick_card_view(
                "📭 No open tickets right now."
            )
        )
        return

    lines = []

    for (
        channel_id,
        user_id,
        ticket_type,
        claimed_by,
        created_at,
    ) in rows:
        channel = ctx.guild.get_channel(
            channel_id
        )

        chan_text = (
            channel.mention
            if channel
            else f"`#deleted-{channel_id}`"
        )

        claim_text = (
            f"claimed by <@{claimed_by}>"
            if claimed_by
            else "unclaimed"
        )

        lines.append(
            f"{chan_text} — <@{user_id}> — "
            f"*{ticket_type}* — {claim_text}"
        )

    embed = discord.Embed(
        title=f"🎫 Open Tickets ({len(rows)})",
        description="\n".join(lines),
        color=0x2F3136,
    )

    await ctx.send(
        embed=embed
    )

from bot.config import style_embed
from bot.ui.premium_cards import quick_card_view, style_card_view

"""
tickets.py — Ticket system (panel, open/close/claim, manage views).
Extracted from the original monolithic bot.py. Logic unchanged.
"""

import discord
from discord.ext import commands
import discord.app_commands as app_commands
import datetime
import asyncio
import re

from bot.config import bot, style_embed, TICKET_CATEGORY_NAME, UTC, staff_check
from bot.database import (
    create_ticket_record,
    close_ticket_record,
    claim_ticket_record,
    unclaim_ticket_record,
    get_ticket_record,
    get_open_ticket_for_user,
    list_open_tickets,
    get_trusted_role_id,
)

TICKET_TYPES = {
    "general": ("🎫", "General Support"),
    "report": ("🚨", "Report a Member"),
    "billing": ("💳", "Billing / Payment"),
    "bug": ("🐛", "Bug Report"),
    "other": ("❔", "Other"),
}


async def get_or_create_ticket_category(
    guild: discord.Guild,
) -> discord.CategoryChannel:
    category = discord.utils.get(
        guild.categories,
        name=TICKET_CATEGORY_NAME,
    )

    if category is None:
        category = await guild.create_category(TICKET_CATEGORY_NAME)

    return category


async def open_new_ticket(
    guild: discord.Guild,
    user: discord.Member,
    ticket_type_key: str = "general",
) -> discord.TextChannel:
    emoji, type_label = TICKET_TYPES.get(
        ticket_type_key,
        TICKET_TYPES["general"],
    )

    category = await get_or_create_ticket_category(guild)
    # Staff access is managed by Discord permissions, not roles

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=False
        ),
        user: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
        ),
        guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_channels=True,
        ),
    }

    if staff_role:
        overwrites[staff_role] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
        )

    safe_name = (
        re.sub(
            r"[^a-z0-9]+",
            "-",
            user.name.lower(),
        ).strip("-")
        or "user"
    )

    channel = await guild.create_text_channel(
        name=f"ticket-{safe_name}",
        category=category,
        overwrites=overwrites,
        topic=f"{type_label} | Opened by {user} ({user.id})",
        reason=f"Ticket opened by {user}",
    )

    create_ticket_record(
        channel.id,
        guild.id,
        user.id,
        type_label,
    )

    embed = discord.Embed(
        title=f"{emoji} Ticket Opened — {type_label}",
        description=(
            f"Welcome {user.mention}! A staff member will be with you shortly.\n\n"
            f"Describe your issue below. Staff can **Claim** this ticket "
            f"to take ownership, and either side can **Close** it when resolved."
        ),
        color=0x2F3136,
        timestamp=datetime.datetime.now(UTC),
    )

    embed.set_footer(
        text=f"Ticket type: {type_label}"
    )

    await channel.send(
        content=f"{user.mention}",
        embed=embed,
        view=TicketManageView(),
    )

    return channel


class TicketTypeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=label,
                emoji=emoji,
                value=key,
            )
            for key, (emoji, label) in TICKET_TYPES.items()
        ]

        super().__init__(
            placeholder="What do you need help with?",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(
        self,
        interaction: discord.Interaction,
    ):
        existing = get_open_ticket_for_user(
            interaction.guild.id,
            interaction.user.id,
        )

        if existing:
            channel = interaction.guild.get_channel(existing)

            if channel:
                await interaction.response.edit_message(
                    content=(
                        f"❗ You already have an open ticket: "
                        f"{channel.mention}"
                    ),
                    view=None,
                )
                return

        await interaction.response.edit_message(
            content="🎫 Creating your ticket...",
            view=None,
        )

        channel = await open_new_ticket(
            interaction.guild,
            interaction.user,
            self.values[0],
        )

        await interaction.followup.send(
            f"✅ Ticket created: {channel.mention}",
            ephemeral=True,
        )


class TicketTypeSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(TicketTypeSelect())


class TicketManageView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Claim",
        style=discord.ButtonStyle.primary,
        emoji="🙋",
        custom_id="ticket_claim_button",
    )
    async def claim_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        # Staff access is managed by Discord permissions, not roles

        is_staff = (
            staff_role
            and staff_role in interaction.user.roles
        )

        if not is_staff:
            await interaction.response.send_message(
                view=quick_card_view(
                    "❌ Only staff can claim tickets."
                ),
                ephemeral=True,
            )
            return

        record = get_ticket_record(
            interaction.channel.id
        )

        if not record:
            await interaction.response.send_message(
                view=quick_card_view(
                    "❌ This isn't a ticket channel."
                ),
                ephemeral=True,
            )
            return

        _, status, _, claimed_by = record

        if claimed_by == interaction.user.id:
            unclaim_ticket_record(
                interaction.channel.id
            )

            button.label = "Claim"
            button.style = discord.ButtonStyle.primary

            await interaction.response.edit_message(
                view=self
            )

            await interaction.followup.send(
                f"↩️ {interaction.user.mention} "
                f"unclaimed this ticket."
            )
            return

        if claimed_by:
            await interaction.response.send_message(
                view=quick_card_view(
                    f"❗ This ticket is already claimed by "
                    f"<@{claimed_by}>."
                ),
                ephemeral=True,
            )
            return

        claim_ticket_record(
            interaction.channel.id,
            interaction.user.id,
        )

        button.label = (
            f"Claimed by {interaction.user.display_name}"
        )

        button.style = discord.ButtonStyle.secondary

        await interaction.response.edit_message(
            view=self
        )

        await interaction.followup.send(
            f"🙋 {interaction.user.mention} claimed this "
            f"ticket and will be assisting you."
        )

    @discord.ui.button(
        label="Add Member",
        style=discord.ButtonStyle.secondary,
        emoji="➕",
        custom_id="ticket_add_member_button",
    )
    async def add_member_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        # Staff access is managed by Discord permissions, not roles

        is_staff = (
            staff_role
            and staff_role in interaction.user.roles
        )

        if not is_staff:
            await interaction.response.send_message(
                view=quick_card_view(
                    "❌ Only staff can add members to a ticket."
                ),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "➕ Mention the member to add, e.g. "
            "`@username` (paste it as your next message here — staff only).",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="ticket_close_button",
    )
    async def close_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        # Staff access is managed by Discord permissions, not roles

        is_staff = (
            staff_role
            and staff_role in interaction.user.roles
        )

        record = get_ticket_record(
            interaction.channel.id
        )

        is_owner = (
            record
            and record[0] == interaction.user.id
        )

        if not (is_staff or is_owner):
            await interaction.response.send_message(
                view=quick_card_view(
                    "❌ Only the ticket opener or staff can close this ticket."
                ),
                ephemeral=True,
            )
            return

        close_ticket_record(
            interaction.channel.id
        )

        await interaction.response.send_message(
            view=quick_card_view(
                "🔒 **Closing this ticket in 5 seconds...**"
            )
        )

        await asyncio.sleep(5)

        try:
            await interaction.channel.delete(
                reason=f"Ticket closed by {interaction.user}"
            )
        except discord.NotFound:
            pass


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Create Ticket",
        style=discord.ButtonStyle.primary,
        emoji="🎫",
        custom_id="ticket_create_button",
    )
    async def create_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        existing = get_open_ticket_for_user(
            interaction.guild.id,
            interaction.user.id,
        )

        if existing:
            channel = interaction.guild.get_channel(existing)

            if channel:
                await interaction.response.send_message(
                    view=quick_card_view(
                        f"❗ You already have an open ticket: "
                        f"{channel.mention}"
                    ),
                    ephemeral=True,
                )
                return

        await interaction.response.send_message(
            view=TicketTypeSelectView(),
            content="🎫 **What do you need help with?**",
            ephemeral=True,
        )


@bot.hybrid_command(
    name="ticketpanel",
    aliases=["tp"],
    description="[Staff] Post a button-based ticket-creation panel",
)
@staff_check("admin")
async def ticket_panel_prefix(ctx):
    embed = discord.Embed(
        title="🎫 Support Tickets",
        description=(
            "Need help? Click the button below to open "
            "a private ticket with staff."
        ),
        color=0x2F3136,
    )

    await ctx.send(
        embed=embed,
        view=TicketPanelView(),
    )


@bot.hybrid_command(
    name="ticket",
    description="Open a private support ticket",
)
async def ticket_prefix(ctx):
    existing = get_open_ticket_for_user(
        ctx.guild.id,
        ctx.author.id,
    )

    if existing:
        channel = ctx.guild.get_channel(existing)

        if channel:
            await ctx.send(
                view=quick_card_view(
                    f"❗ You already have an open ticket: "
                    f"{channel.mention}"
                )
            )
            return

    await ctx.send(
        content="🎫 **What do you need help with?**",
        view=TicketTypeSelectView(),
    )


@bot.hybrid_command(
    name="closeticket",
    aliases=["close"],
    description="Close the ticket you're currently in",
)
async def close_ticket_prefix(ctx):
    record = get_ticket_record(
        ctx.channel.id
    )

    if not record:
        await ctx.send(
            view=quick_card_view(
                "❌ This isn't a ticket channel."
            )
        )
        return

    # Staff access is managed by Discord permissions, not roles

    is_staff = (
        staff_role
        and staff_role in ctx.author.roles
    )

    is_owner = (
        record[0] == ctx.author.id
    )

    if not (is_staff or is_owner):
        await ctx.send(
            view=quick_card_view(
                "❌ Only the ticket opener or staff can close this ticket."
            )
        )
        return

    close_ticket_record(
        ctx.channel.id
    )

    await ctx.send(
        view=quick_card_view(
            "🔒 **Closing this ticket in 5 seconds...**"
        )
    )

    await asyncio.sleep(5)

    try:
        await ctx.channel.delete(
            reason=f"Ticket closed by {ctx.author}"
        )
    except discord.NotFound:
        pass


@bot.hybrid_command(
    name="tickets",
    aliases=["ticketlist"],
    description="[Staff] List all currently open tickets",
)
@staff_check("admin")
async def list_tickets_prefix(ctx):
    rows = list_open_tickets(
        ctx.guild.id
    )

    if not rows:
        await ctx.send(
            view=quick_card_view(
                "📭 No open tickets right now."
            )
        )
        return

    lines = []

    for (
        channel_id,
        user_id,
        ticket_type,
        claimed_by,
        created_at,
    ) in rows:
        channel = ctx.guild.get_channel(
            channel_id
        )

        chan_text = (
            channel.mention
            if channel
            else f"`#deleted-{channel_id}`"
        )

        claim_text = (
            f"claimed by <@{claimed_by}>"
            if claimed_by
            else "unclaimed"
        )

        lines.append(
            f"{chan_text} — <@{user_id}> — "
            f"*{ticket_type}* — {claim_text}"
        )

    embed = discord.Embed(
        title=f"🎫 Open Tickets ({len(rows)})",
        description="\n".join(lines),
        color=0x2F3136,
    )

    await ctx.send(
        embed=embed
    )

"""
vouch.py — Vouching system.
Extracted from the original monolithic bot.py. Logic unchanged.
"""
from bot.ui.premium_cards import quick_card_view, style_card_view, embed_to_view, purple_embed
import discord
from discord.ext import commands
import discord.app_commands as app_commands
import datetime

import re
import sqlite3

from bot.config import bot, style_embed, UTC, is_staff, staff_check
from bot.database import (
    DB_FILE,
    add_vouch, remove_last_vouch, count_vouches, list_vouches, vouch_leaderboard,
    get_vouch_channel, set_vouch_channel, clear_vouch_channel,
    staff_remove_vouch, staff_clear_all_vouches,
)


# Configuration Limits
MAX_REASON_LENGTH = 300

# Regular expression to extract: "vouch @user for [reason]"
VOUCH_PATTERN = re.compile(
    r"\bvouch(?:es|ed|ing)?\b.*?<@!?(?P<id>\d+)>\s*(?:for\s+)?(?P<reason>.*)",
    re.IGNORECASE | re.DOTALL,
)


async def _check_vouch_channel(ctx: commands.Context) -> bool:
    """Helper function to verify if the command is run in the allowed channel."""
    vouch_channel_id = get_vouch_channel(ctx.guild.id)
    if vouch_channel_id is None or ctx.channel.id == vouch_channel_id:
        return True
    await ctx.send(view=quick_card_view(f"❌ Vouching commands are restricted to <#{vouch_channel_id}> in this server."))
    return False

# ----------------- Commands -----------------

@bot.hybrid_command(name="vouch", description="Vouch for a user")
@commands.guild_only()
@app_commands.describe(member="User to vouch for", comment="Optional comment (e.g. what for)")
async def vouch_prefix(ctx: commands.Context, member: discord.Member = None, *, comment: str = None):
    # If a member is tagged but no comment is provided, redirect to showing their profile status
    if member is not None and comment is None:
        await vouches_prefix(ctx, member)
        return

    if member is None:
        await ctx.send(view=quick_card_view(f"❌ Syntax: `{ctx.prefix}vouch @user [comment]`"))
        return
        
    if not await _check_vouch_channel(ctx):
        return
        
    if member.id == ctx.author.id:
        await ctx.send(view=quick_card_view("❌ You can't vouch for yourself."))
        return
    if member.bot:
        await ctx.send(view=quick_card_view("❌ You can't vouch for a bot."))
        return

    add_vouch(ctx.guild.id, member.id, ctx.author.id, comment)
    total = count_vouches(ctx.guild.id, member.id)

    # Premium purple gradient embed like the reference image
    description = f"✨ {ctx.author.mention} vouched for {member.mention}"
    fields = []
    if comment:
        fields.append(("💬 Comment", comment, False))
    
    embed = purple_embed(
        title="VOUCH SYSTEM",
        description=description,
        fields=fields,
        footer=f"✨ User: @{member.display_name} • Vouches: {total}",
        thumbnail_url=member.display_avatar.url,
    )
    await ctx.send(embed=embed)


@bot.hybrid_command(name="unvouch", description="Remove your most recent vouch for a user")
@commands.guild_only()
@app_commands.describe(member="User to remove your vouch from")
async def unvouch_prefix(ctx: commands.Context, member: discord.Member = None):
    if member is None:
        await ctx.send(view=quick_card_view(f"❌ Syntax: `{ctx.prefix}unvouch @user`"))
        return
        
    if not await _check_vouch_channel(ctx):
        return
        
    removed = remove_last_vouch(ctx.guild.id, member.id, ctx.author.id)
    if removed:
        await ctx.send(view=quick_card_view(f"Removed your vouch for {member.mention}."))
    else:
        await ctx.send(view=quick_card_view(f"You haven't vouched for {member.mention}."))


@bot.hybrid_command(name="vouches", aliases=["vouchlist"], description="Show vouches for a user")
@commands.guild_only()
@app_commands.describe(member="User to check (defaults to yourself)")
async def vouches_prefix(ctx: commands.Context, member: discord.Member = None):
    member = member or ctx.author
    
    total = count_vouches(ctx.guild.id, member.id)
    recent = list_vouches(ctx.guild.id, member.id, limit=5)

    # Build the description with user vouches
    lines = [f"**✨ Total Vouches:** {total}\n"]
    if recent:
        lines.append("**Recent Vouches:**")
        for author_id, comment, created_at in recent:
            author = ctx.guild.get_member(author_id)
            author_name = author.mention if author else f"<@{author_id}>"
            line = f"• {author_name}"
            if comment:
                line += f" — *{comment}*"
            lines.append(line)
    else:
        lines.append("*No vouches yet*")
    
    embed = purple_embed(
        title="VOUCH SYSTEM",
        description="\n".join(lines),
        footer=f"✨ User: @{member.display_name}",
        thumbnail_url=member.display_avatar.url,
    )
    await ctx.send(embed=embed)


@bot.hybrid_command(name="vouchleaderboard", aliases=["vouchlb"], description="Show the most-vouched users in this server")
@commands.guild_only()
async def vouch_leaderboard_prefix(ctx: commands.Context):
    rows = vouch_leaderboard(ctx.guild.id, limit=10)
    if not rows:
        await ctx.send(view=quick_card_view("No vouches yet in this server."))
        return
        
    lines = []
    for i, (target_id, c) in enumerate(rows, start=1):
        member = ctx.guild.get_member(target_id)
        name = member.mention if member else f"<@{target_id}>"
        
        # Add medals for top 3
        medal = ""
        if i == 1: medal = "🥇 "
        elif i == 2: medal = "🥈 "
        elif i == 3: medal = "🥉 "
        
        lines.append(f"{medal}**{i}.** {name} — `{c} vouch(es)`")
        
    embed = purple_embed(
        title="VOUCH LEADERBOARD",
        description="\n".join(lines),
        footer="✨ Top vouched members in this server"
    )
    await ctx.send(embed=embed)


# ------------- Configuration -------------

@bot.hybrid_command(name="setvouchchannel", aliases=["setvouch"], description="[Mod] Set the channel where vouching happens")
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
@app_commands.describe(channel="The channel to dedicate to vouching")
async def set_vouch_channel_prefix(ctx: commands.Context, channel: discord.TextChannel):
    """Restricts vouching and tracking to a single dedicated text channel."""
    set_vouch_channel(ctx.guild.id, channel.id)
    embed = purple_embed(
        title="VOUCH CHANNEL SET",
        description=f"✅ Vouch channel successfully set to {channel.mention}.\n\nUsers can now chat naturally here to issue auto-vouches, or use manual lookup commands.",
        footer="✨ Vouch system configured"
    )
    await ctx.send(embed=embed)


@bot.hybrid_command(name="clearvouchchannel", aliases=["clearvouch"], description="[Mod] Remove the vouch channel restriction")
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
async def clear_vouch_channel_prefix(ctx: commands.Context):
    """Removes the channel restriction so vouch commands work everywhere."""
    clear_vouch_channel(ctx.guild.id)
    await ctx.send(view=quick_card_view("✅ Vouch channel restriction cleared. Vouch commands will now work across all channels."))





