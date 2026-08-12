from bot.ui.premium_cards import quick_card_view, style_card_view
"""
reaction_roles.py — Reaction role panels and role menus.
Extracted from the original monolithic bot.py. Logic unchanged.
"""
import discord
from discord.ext import commands
import discord.app_commands as app_commands
import asyncio
import re

from bot.config import bot, quick_embed, REQUIRED_ROLE_ID
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
        message = await channel.send(view=view)
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
@commands.has_role(REQUIRED_ROLE_ID)
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


