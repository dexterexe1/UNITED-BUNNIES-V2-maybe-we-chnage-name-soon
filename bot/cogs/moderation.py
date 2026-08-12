"""
moderation.py — Real moderation tools (prefix) + aesthetic ?bon.
Extracted from the original monolithic bot.py. Logic unchanged.
"""
import discord
from discord.ext import commands
import discord.app_commands as app_commands
import datetime
import random

from bot.config import bot, quick_embed, style_embed, staff_check, is_staff, REQUIRED_ROLE_ID, UTC, EMOJI_BULLET
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
            await interaction.response.send_message(embed=quick_embed("🌌 This timeline isn't yours to change."), ephemeral=True)
            return
        embed = discord.Embed(title="🪐 SYSTEM OVERRIDE SUCCESSFUL", description=f"**{interaction.user.name}** has willingly left the server matrix.", color=0x2f3136, timestamp=datetime.datetime.now(UTC))
        embed.set_image(url="https://media.giphy.com/media/3XiQswSmruBiw/giphy.gif")
        for item in self.children: item.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Abrupt", style=discord.ButtonStyle.secondary, emoji="🛡️")
    async def no_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(embed=quick_embed("🌌 This timeline isn't yours to change."), ephemeral=True)
            return
        embed = discord.Embed(description="🔮 *The system stabilizer kicks in. Ban sequence retracted safely.*", color=0x2f3136)
        for item in self.children: item.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

@bot.hybrid_command(name="bon", description="Cosmetic joke removal (not a real ban)")
@staff_check("mod")
@app_commands.describe(member="User to (fake) ban")
async def bon_prefix(ctx, member: discord.Member = None):
    if member is None:
        await ctx.send(embed=quick_embed("❌ **Syntax Error:** Specify a user profile. Example: `?bon @user`"))
        return
    if member.id == bot.user.id:
        embed = discord.Embed(title="🛡️ SECURITY PROTOCOL ACTIVE", description="**This bot is fully secured.** System access keys are locked down.", color=0x2f3136, timestamp=datetime.datetime.now(UTC))
        embed.set_image(url="https://media.giphy.com/media/139eZBmH1HTyY8/giphy.gif")
        await ctx.send(embed=embed)
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
    await ctx.send(embed=embed)


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
        await ctx.send(embed=quick_embed("❌ Syntax: `?warn @user [reason]`"))
        return
    current = update_warnings(member.id, 1)
    embed = style_embed(
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
    await ctx.send(embed=embed)

    if current >= 3:
        reset_warnings(member.id)
        try:
            await member.timeout(datetime.timedelta(minutes=10), reason="Reached 3 warnings")
            await ctx.send(embed=quick_embed(f"🤫 **{member.display_name}** has been auto-timed out for 10 minutes after reaching 3 warnings."))
        except discord.Forbidden:
            await ctx.send(embed=quick_embed("⚠️ Reached 3 warnings, but I don't have permission to timeout that user."))

@bot.command(name="warnings", aliases=["warns"])
async def warnings_prefix(ctx, member: discord.Member = None):
    member = member or ctx.author
    count = get_warnings(member.id)
    embed = style_embed(
        "Warnings",
        kind="info",
        description=f"{EMOJI_BULLET} user: {member.mention}\n{EMOJI_BULLET} warnings: **{count}/3**",
        footer=f"ID: {member.id}",
    )
    await ctx.send(embed=embed)

@bot.command(name="clearwarnings", aliases=["cw", "clearwarns"])
@staff_check("mod")
async def clearwarnings_prefix(ctx, member: discord.Member = None):
    if member is None:
        await ctx.send(embed=quick_embed("❌ Syntax: `?clearwarnings @user`"))
        return
    reset_warnings(member.id)
    embed = style_embed(
        "Warnings Cleared",
        kind="success",
        description=f"{EMOJI_BULLET} user: {member.mention}\n{EMOJI_BULLET} warnings: **0/3**",
        footer=f"ID: {member.id}",
    )
    await ctx.send(embed=embed)

@bot.command(name="mute", aliases=["timeout"])
@staff_check("mod")
async def mute_prefix(ctx, member: discord.Member = None, minutes: int = 10, *, reason: str = "No reason provided"):
    if member is None:
        await ctx.send(embed=quick_embed("❌ Syntax: `?mute @user [minutes] [reason]`"))
        return
    minutes = max(1, min(40320, minutes))  # Discord's timeout cap is 28 days
    try:
        await member.timeout(datetime.timedelta(minutes=minutes), reason=f"{reason} (by {ctx.author})")
    except discord.Forbidden:
        await ctx.send(embed=quick_embed("❌ I don't have permission to timeout that user (check role hierarchy)."))
        return
    embed = style_embed(
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
    await ctx.send(embed=embed)

@bot.command(name="unmute", aliases=["untimeout"])
@staff_check("mod")
async def unmute_prefix(ctx, member: discord.Member = None):
    if member is None:
        await ctx.send(embed=quick_embed("❌ Syntax: `?unmute @user`"))
        return
    try:
        await member.timeout(None, reason=f"Unmuted by {ctx.author}")
    except discord.Forbidden:
        await ctx.send(embed=quick_embed("❌ I don't have permission to unmute that user."))
        return
    embed = style_embed(
        "Member Unmuted",
        kind="success",
        description=f"{EMOJI_BULLET} user: {member.mention}\n{EMOJI_BULLET} moderator: {ctx.author.mention}",
        footer=f"ID: {member.id}",
    )
    await ctx.send(embed=embed)

@bot.command(name="kick", aliases=["k"])
@staff_check("kick")
async def kick_prefix(ctx, member: discord.Member = None, *, reason: str = "No reason provided"):
    if member is None:
        await ctx.send(embed=quick_embed("❌ Syntax: `?kick @user [reason]`"))
        return
    if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
        await ctx.send(embed=quick_embed("❌ You can't kick someone with an equal or higher role than you."))
        return
    try:
        await member.kick(reason=f"{reason} (by {ctx.author})")
    except discord.Forbidden:
        await ctx.send(embed=quick_embed("❌ I don't have permission to kick that user (check role hierarchy)."))
        return
    embed = style_embed(
        "Member Kicked",
        kind="mod",
        description=(
            f"{EMOJI_BULLET} user: **{member}**\n"
            f"{EMOJI_BULLET} moderator: {ctx.author.mention}\n"
            f"{EMOJI_BULLET} reason: {reason}"
        ),
        footer=f"ID: {member.id}",
    )
    await ctx.send(embed=embed)

@bot.command(name="ban", aliases=["b"])
@staff_check("ban")
async def ban_prefix(ctx, member: discord.Member = None, *, reason: str = "No reason provided"):
    if member is None:
        await ctx.send(embed=quick_embed("❌ Syntax: `?ban @user [reason]`"))
        return
        
    if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
        await ctx.send(embed=quick_embed("❌ You can't ban someone with an equal or higher role than you."))
        return
        
    try:
        await member.ban(reason=f"{reason} (by {ctx.author})")
    except discord.Forbidden:
        await ctx.send(embed=quick_embed("❌ I don't have permission to ban that user (check role hierarchy)."))
        return
        
    embed = style_embed(
        "Member Banned",
        kind="error",
        description=(
            f"{EMOJI_BULLET} user: **{member}**\n"
            f"{EMOJI_BULLET} moderator: {ctx.author.mention}\n"
            f"{EMOJI_BULLET} reason: {reason}"
        ),
        footer=f"ID: {member.id}",
    )
    await ctx.send(embed=embed)

@bot.command(name="unban", aliases=["ub"])
@staff_check("ban")
async def unban_prefix(ctx, user_id: int = None, *, reason: str = "No reason provided"):
    if user_id is None:
        await ctx.send(embed=quick_embed("❌ Syntax: `?unban <user_id> [reason]`"))
        return
    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user, reason=f"{reason} (by {ctx.author})")
    except discord.NotFound:
        await ctx.send(embed=quick_embed("❌ That user isn't banned."))
        return
    except discord.Forbidden:
        await ctx.send(embed=quick_embed("❌ I don't have permission to unban."))
        return
    embed = style_embed(
        "Member Unbanned",
        kind="success",
        description=f"{EMOJI_BULLET} user: **{user}**\n{EMOJI_BULLET} moderator: {ctx.author.mention}",
        footer=f"ID: {user.id}",
    )
    await ctx.send(embed=embed)


