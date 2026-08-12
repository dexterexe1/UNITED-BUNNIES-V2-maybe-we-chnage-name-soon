from bot.ui.premium_cards import quick_card_view, style_card_view
"""
vouch.py — Vouching system.
Extracted from the original monolithic bot.py. Logic unchanged.
"""
import discord
from discord.ext import commands
import discord.app_commands as app_commands
import datetime

import re
import sqlite3

from bot.config import bot, quick_embed, REQUIRED_ROLE_ID, UTC
from bot.database import (
    DB_FILE,
    add_vouch, remove_last_vouch, count_vouches, list_vouches, vouch_leaderboard,
    get_vouch_channel, set_vouch_channel, clear_vouch_channel,
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

    embed = discord.Embed(
        description=f"✅ {ctx.author.mention} vouched for {member.mention}",
        color=discord.Color.green(),
    )
    if comment:
        embed.add_field(name="Comment", value=comment, inline=False)
    embed.set_footer(text=f"{member.display_name} now has {total} vouch(es)")
    await ctx.send(view=view)


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

    embed = discord.Embed(
        title=f"Vouches for {member.display_name}",
        description=f"**Total:** {total}",
        color=discord.Color.gold(),
    )
    embed.set_thumbnail(url=member.display_avatar.url)

    if recent:
        lines = []
        for author_id, comment, created_at in recent:
            author = ctx.guild.get_member(author_id)
            author_name = author.mention if author else f"<@{author_id}>"
            line = f"- {author_name}"
            if comment:
                line += f" — {comment}"
            lines.append(line)
        embed.add_field(name="Recent", value="\n".join(lines), inline=False)

    await ctx.send(view=view)


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
        lines.append(f"**{i}.** {name} — {c} vouch(es)")
        
    embed = discord.Embed(
        title="🏆 Vouch Leaderboard", 
        description="\n".join(lines), 
        color=discord.Color.gold()
    )
    await ctx.send(view=view)


# ------------- Configuration -------------

@bot.hybrid_command(name="setvouchchannel", aliases=["setvouch"], description="[Mod] Set the channel where vouching happens")
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
@app_commands.describe(channel="The channel to dedicate to vouching")
async def set_vouch_channel_prefix(ctx: commands.Context, channel: discord.TextChannel):
    """Restricts vouching and tracking to a single dedicated text channel."""
    set_vouch_channel(ctx.guild.id, channel.id)
    embed = discord.Embed(
        description=f"✅ Vouch channel successfully set to {channel.mention}.\n\nUsers can now chat normally here to issue auto-vouches, or use manual lookup commands.",
        color=discord.Color.green()
    )
    await ctx.send(view=view)


@bot.hybrid_command(name="clearvouchchannel", aliases=["clearvouch"], description="[Mod] Remove the vouch channel restriction")
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
async def clear_vouch_channel_prefix(ctx: commands.Context):
    """Removes the channel restriction so vouch commands work everywhere."""
    clear_vouch_channel(ctx.guild.id)
    await ctx.send(view=quick_card_view("✅ Vouch channel restriction cleared. Vouch commands will now work across all channels."))


