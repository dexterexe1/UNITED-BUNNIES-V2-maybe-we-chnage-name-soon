"""
applications.py — Application form system.
Extracted from the original monolithic bot.py. Logic unchanged.
"""
import discord
from discord.ext import commands
import discord.app_commands as app_commands
import asyncio
import datetime

from bot.config import bot, quick_embed, REQUIRED_ROLE_ID, UTC, has_required_slash_role, mod_group
from bot import mongo_bridge

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

        self.add_item(
            discord.ui.Button(
                label=button_config.get("label", "Apply Now"),
                style=button_style_map.get(button_config.get("style", "primary"), discord.ButtonStyle.primary),
                emoji=button_config.get("emoji"),
                custom_id=f"app_apply_{form_data.get('_id', '')}",
            )
        )

    @discord.ui.button(label="Apply", style=discord.ButtonStyle.blurple, custom_id="app_apply_placeholder", row=0)
    async def apply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # This is handled by the dynamic button above; this is just a placeholder
        pass


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
                        await interaction.response.send_message(embed=quick_embed("✅ Application marked as accepted."), ephemeral=True)
                    else:
                        await interaction.response.send_message(embed=quick_embed(f"❌ Failed to update status: {resp.status}"), ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(embed=quick_embed(f"❌ Error: {e}"), ephemeral=True)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger, emoji="❌", custom_id="app_reject", row=0)
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        headers = {"x-bot-secret": BOT_API_SECRET} if BOT_API_SECRET else {}
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                api_url = DASHBOARD_URL.rstrip("/") + "/api/v1/guilds/" + str(interaction.guild.id) + "/applications/submissions/" + self.submission_id + "/status"
                async with session.patch(api_url, json={"status": "rejected"}, headers=headers) as resp:
                    if resp.status == 200:
                        await interaction.response.send_message(embed=quick_embed("❌ Application marked as rejected."), ephemeral=True)
                    else:
                        await interaction.response.send_message(embed=quick_embed(f"❌ Failed to update status: {resp.status}"), ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(embed=quick_embed(f"❌ Error: {e}"), ephemeral=True)


@bot.tree.command(name="deploy-application", description="📝 [Mod] Deploy an application form panel to a channel.")
@has_required_slash_role()
@app_commands.describe(form_id="The ID of the application form to deploy", channel="The channel to post the panel in")
async def deploy_application_slash(interaction: discord.Interaction, form_id: str, channel: discord.TextChannel):
    # Find the application form
    form_data = mongo_bridge.find_application_form_by_id(interaction.guild.id, form_id)
    if not form_data:
        await interaction.response.send_message(embed=quick_embed(f"❌ Application form not found."), ephemeral=True)
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
        await interaction.response.send_message(embed=quick_embed("📋 No application forms configured yet."), ephemeral=True)
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
            await interaction.response.send_message(embed=quick_embed("❌ This application form no longer exists."), ephemeral=True)
            return

        if form_data.get("status") != "active":
            await interaction.response.send_message(embed=quick_embed("❌ This application form is not currently accepting submissions."), ephemeral=True)
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
                                        embed=quick_embed("❗ You already have a pending application for this form."),
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
                await interaction.response.send_message(embed=quick_embed(f"❗ You already have an open ticket: {channel.mention}"), ephemeral=True)
                return
        await interaction.response.send_message(embed=quick_embed("🎫 Creating your ticket..."), ephemeral=True)
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
            await interaction.response.send_message(embed=quick_embed("❌ Nothing is currently playing."), ephemeral=True)
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
@commands.has_role(REQUIRED_ROLE_ID)
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
    embed.set_footer(text="🐰 Matrix System Active 🌟")
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
    embed.set_footer(text="🐰 Matrix System Active 🌟")
    await interaction.response.send_message(embed=embed, view=ControlPanelView())


