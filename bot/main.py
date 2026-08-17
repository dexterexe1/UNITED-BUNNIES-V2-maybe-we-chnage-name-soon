

"""
events.py — Bot lifecycle and message/member event handlers.
Extracted from the original monolithic bot.py. Logic unchanged.
"""
from bot.ui.premium_cards import quick_card_view, style_card_view, embed_to_view
import discord
from discord.ext import commands
import discord.app_commands as app_commands
import datetime
import asyncio
import random
import re
import time

from bot.config import (
    bot, style_embed, style_embed, UTC, BRAND_COLOR,
    user_message_cooldowns, afk_users, _recent_messages,
    xp_cooldowns, XP_COOLDOWN_SECONDS, XP_MIN, XP_MAX,
    LEVELING_SYSTEM_ENABLED,
    EMOJI_BULLET, BOT_OWNER_IDS,
)
from bot.database import (
    get_config, get_welcome_message, format_welcome_message,
    is_leveling_enabled, get_levelup_channel, add_xp, xp_for_level,
    get_level_data, has_noprefix_perm, level_leaderboard,
    get_all_role_menu_message_ids, get_role_menu_items,
    get_vouch_channel, add_vouch, count_vouches, get_custom_command,
    update_warnings, reset_warnings,
)
from bot.status import publish_bot_status
from bot.config import mod_group
from bot import mongo_bridge


# Persistent views (defined in feature modules)
try:
    from bot.cogs.tickets import TicketPanelView, TicketManageView
except Exception:
    TicketPanelView = TicketManageView = None
try:
    from bot.cogs.applications import ControlPanelView
except Exception:
    ControlPanelView = None
try:
    from bot.cogs.community import RoleMenuView  # may not exist yet
except Exception:
    RoleMenuView = None

# --- SYNC MODERN SLASH COMMAND TREES ---
_ready_initialized = False
_background_tasks_started = False

@bot.event
async def on_ready():
    global _ready_initialized, _background_tasks_started
    if not _ready_initialized:
        try:
            bot.tree.add_command(mod_group)
        except discord.app_commands.CommandAlreadyRegistered:
            pass
    
    print("=" * 60)
    print(f"✨ Success! {bot.user.name} is online.")
    print(f"📋 Prefix/hybrid commands loaded: {len(bot.commands)}")
    print("=" * 60)
    
    # Sample public commands so deploy logs prove help/ping exist
    for name in ("help", "ping", "play", "warn", "vouch"):
        c = bot.get_command(name)
        print(f"   - {name}: {'OK' if c else 'MISSING'}")
    
    # Initialize revenue database
    print("🔧 Initializing revenue database...")
    try:
        from bot.revenue_database import init_revenue_db
        await init_revenue_db()
        print("✅ Revenue database initialized")
        try:
            from bot.cogs.revenue import start_revenue_manager_weekly_loop
            start_revenue_manager_weekly_loop()
        except Exception as e:
            print(f"⚠️ Revenue manager weekly DM loop not started: {e}")
    except Exception as e:
        print(f"⚠️ Revenue database init error: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        from bot.cogs.ai_manager import init as init_ai_manager
        await init_ai_manager()
    except Exception as e:
        print(f"⚠️ AI Manager init error: {e}")

    await publish_bot_status()
    if _ready_initialized:
        return
    _ready_initialized = True

    # Re-register persistent views (buttons with custom_id) so they keep
    # working after a restart, not just for the session that created them.
    if TicketPanelView:
        bot.add_view(TicketPanelView())
    if TicketManageView:
        bot.add_view(TicketManageView())
    if ControlPanelView:
        bot.add_view(ControlPanelView())

    # Dropdown self-role menus are dynamic (their options differ per message),
    # so each stored menu needs its own view instance registered against its message ID.
    # Note: RoleMenuView was referenced in original on_ready but never defined in the
    # original file — left as optional until that class is implemented.
    try:
        if RoleMenuView:
            for msg_id in get_all_role_menu_message_ids():
                items = get_role_menu_items(msg_id)
                if items:
                    bot.add_view(RoleMenuView(msg_id, items), message_id=msg_id)
    except Exception as e:
        print(f"⚠️ Failed to re-register role menus: {e}")

    try:
        synced = await bot.tree.sync()
        print(f"🔄 Successfully synced {len(synced)} slash commands globally!")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")

    async def status_loop():
        while not bot.is_closed():
            await publish_bot_status()
            await asyncio.sleep(15)

    if not _background_tasks_started:
        bot.loop.create_task(status_loop())

    # Dashboard sync: pulls command toggles / custom commands / auto-responses
    # from the same MongoDB the website writes to, so changes made on the
    # dashboard actually take effect here. Safe no-op if MONGO_URI is unset.
    await mongo_bridge.connect()
    if not _background_tasks_started:
        bot.loop.create_task(mongo_bridge.refresh_loop())

    # Optional background loops (defined in cogs / later in this file)
    try:
        from bot.cogs.reaction_roles import reaction_panel_post_loop
        if not _background_tasks_started:
            bot.loop.create_task(reaction_panel_post_loop())
    except Exception as e:
        print(f"⚠️ reaction_panel_post_loop not started: {e}")

    if LEVELING_SYSTEM_ENABLED:
        if not _background_tasks_started:
            bot.loop.create_task(leaderboard_push_loop())
    _background_tasks_started = True

# --- GUILD LIST FRESHNESS ---
@bot.event
async def on_guild_join(guild):
    print(f"➕ Joined guild: {guild.name} ({guild.id})")
    await publish_bot_status()

@bot.event
async def on_guild_remove(guild):
    print(f"➖ Removed from guild: {guild.name} ({guild.id})")
    await publish_bot_status()

# --- AUTOMOD EVENT LOOPS & GREETINGS SYSTEMS ---
@bot.event
async def on_member_join(member):
    # --- DASHBOARD WELCOME/GOODBYE ("Welcome / Goodbye" tab) ---
    # Managed on the dashboard (Mongo), so it's checked first and takes
    # priority over the older SQLite-based welcomer below, mirroring the
    # dashboard-first pattern used for custom commands / auto-responses.
    if mongo_bridge.enabled():
        join_cfg = mongo_bridge.get_welcome_settings(member.guild.id).get("join", {})
        if join_cfg.get("enabled"):
            channel_name = (join_cfg.get("channelName") or "").lstrip("#")
            channel = discord.utils.get(member.guild.text_channels, name=channel_name) if channel_name else None
            if channel:
                text = mongo_bridge.substitute_variables(
                    join_cfg.get("message") or "Welcome {user} to **{server}**!",
                    member=member, guild=member.guild, channel=channel,
                )
                if join_cfg.get("embed"):
                    embed = discord.Embed(
                        description=text,
                        color=discord.Color.green(),
                        timestamp=datetime.datetime.now(UTC),
                    )
                    if join_cfg.get("imageUrl"):
                        embed.set_image(url=join_cfg["imageUrl"])
                    if join_cfg.get("thumbnailUrl"):
                        embed.set_thumbnail(url=join_cfg["thumbnailUrl"])
                    if join_cfg.get("footer"):
                        embed.set_footer(text=join_cfg["footer"])
                    await channel.send(view=embed_to_view(embed))
                else:
                    await channel.send(text)
                return

    # --- LEGACY SQLITE WELCOMER (predates the dashboard) ---
    # Only runs if the dashboard join message isn't enabled/configured, so
    # servers that haven't touched the new "Welcome / Goodbye" tab keep
    # their existing behavior exactly as before.
    welcome_id, _ = get_config(member.guild.id)
    if welcome_id:
        channel = bot.get_channel(welcome_id)
        if channel:
            custom_template = get_welcome_message(member.guild.id)
            if custom_template:
                description = format_welcome_message(custom_template, member)
            else:
                description = f"Welcome {member.mention}! We are thrilled to have you here.\nTake a look around and make yourself comfortable!"
            embed = discord.Embed(
                title=f"👋 Welcome to {member.guild.name}!",
                description=description,
                color=discord.Color.green(),
                timestamp=datetime.datetime.now(UTC)
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_image(url="https://media.giphy.com/media/l0MYC0LajbaPoEADu/giphy.gif")
            embed.set_footer(text=f"Member Count Total: {member.guild.member_count}")
            await channel.send(content=member.mention, view=embed_to_view(embed))


@bot.event
async def on_member_remove(member):
    # --- DASHBOARD WELCOME/GOODBYE ("Welcome / Goodbye" tab) ---
    # No legacy leave/goodbye system exists in the SQLite era, so this is
    # purely additive — nothing to fall back to or preserve here.
    if not member.guild or not mongo_bridge.enabled():
        return
    leave_cfg = mongo_bridge.get_welcome_settings(member.guild.id).get("leave", {})
    if not leave_cfg.get("enabled"):
        return
    channel_name = (leave_cfg.get("channelName") or "").lstrip("#")
    channel = discord.utils.get(member.guild.text_channels, name=channel_name) if channel_name else None
    if not channel:
        return
    text = mongo_bridge.substitute_variables(
        leave_cfg.get("message") or "{user} has left {server}.",
        member=member, guild=member.guild, channel=channel,
    )
    await channel.send(text)

@bot.event
async def on_message_delete(message):
    if message.author.bot or not message.guild: return
    _, log_id = get_config(message.guild.id)
    if log_id:
        channel = bot.get_channel(log_id)
        if channel:
            embed = discord.Embed(title="🗑️ Message Deleted", color=discord.Color.red(), timestamp=datetime.datetime.now(UTC))
            embed.add_field(name="Author Profile", value=f"{message.author.mention} (`{message.author.id}`)", inline=True)
            embed.add_field(name="Location Stream", value=message.channel.mention, inline=True)
            embed.add_field(name="Deleted Payload Content", value=message.content or "*No text payload (image/embed)*", inline=False)
            await channel.send(view=embed_to_view(embed))

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content or not before.guild: return
    _, log_id = get_config(before.guild.id)
    if log_id:
        channel = bot.get_channel(log_id)
        if channel:
            embed = discord.Embed(title="📝 Message Edited", color=discord.Color.orange(), timestamp=datetime.datetime.now(UTC))
            embed.add_field(name="Author Profile", value=f"{before.author.mention}", inline=True)
            embed.add_field(name="Location Stream", value=before.channel.mention, inline=True)
            embed.add_field(name="Original Payload", value=before.content, inline=False)
            embed.add_field(name="Edited Revision Payload", value=after.content, inline=False)
            await channel.send(view=embed_to_view(embed))

# ==========================================
#         ✅ VOUCH AUTO-DETECT (pattern only; commands live in cogs/vouch.py)
# ==========================================

MAX_REASON_LENGTH = 300

VOUCH_PATTERN = re.compile(
    r"\bvouch(?:es|ed|ing)?\b.*?<@!?(?P<id>\d+)>\s*(?:for\s+)?(?P<reason>.*)",
    re.IGNORECASE | re.DOTALL,
)


# ==========================================
#      🔓 NO-PREFIX COMMAND EXECUTION
# ==========================================
# Commands that change server/member state enough that a typo or joke
# message could cause real damage if it fired instantly with no prefix.
# These always get a Confirm/Cancel button before running when triggered
# without "?".
NOPREFIX_CONFIRM_COMMANDS = {
    "warn", "clearwarnings", "mute", "unmute", "kick", "ban", "unban", "bon", "clearrevenue",
    "makerevenuemanager",
}

async def run_message_as_command(message: discord.Message):
    """Re-parses a plain (non-prefixed) message as if it had been sent with
    the bot's '?' prefix, then invokes it."""
    original_content = message.content
    message.content = "?" + original_content
    try:
        ctx = await bot.get_context(message)
        if ctx.valid:
            await bot.invoke(ctx)
    finally:
        message.content = original_content

class NoPrefixModConfirmView(discord.ui.View):
    def __init__(self, message: discord.Message, author: discord.Member):
        super().__init__(timeout=30)
        self.message = message
        self.author = author

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(view=quick_card_view("❌ Only the person who typed this command can confirm it."), ephemeral=True)
            return
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="✅ **Confirmed — executing...**", view=self)
        await run_message_as_command(self.message)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(view=quick_card_view("❌ Only the person who typed this command can cancel it."), ephemeral=True)
            return
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="❌ **Cancelled.** No action was taken.", view=self)
        self.stop()

async def send_noprefix_confirmation(message: discord.Message, command_name: str):
    view = NoPrefixModConfirmView(message, message.author)
    await message.reply(
        f"⚠️ You typed a **staff command** (`{command_name}`) without the `?` prefix.\n"
        f"Run `{message.content}`?",
        view=view,
        mention_author=False,
    )


# --- STRIP-CHECK / AUTOMOD / AFK / LEVELING / VOUCH ON_MESSAGE HANDLER ---
# NOTE: There is only ONE on_message handler. discord.py only keeps the
# last @bot.event-registered on_message, so all message-driven behavior
# (AFK clearing, automod, XP grants, and the vouch auto-listener) has to
# live in this single function or the earlier registrations get silently
# dropped.

async def handle_leveling(message):
    """Grants XP when LEVELING_SYSTEM_ENABLED is True. Disabled by default."""
    if not LEVELING_SYSTEM_ENABLED:
        return
    guild = message.guild
    author = message.author
    settings = mongo_bridge.get_leveling_settings(guild.id) if mongo_bridge.enabled() else {
        **mongo_bridge.DEFAULT_LEVELING_SETTINGS, "enabled": is_leveling_enabled(guild.id),
        "xpMin": XP_MIN, "xpMax": XP_MAX, "cooldownSeconds": XP_COOLDOWN_SECONDS,
    }
    if not settings.get("enabled", True):
        return
    if mongo_bridge.enabled() and mongo_bridge.is_leveling_ignored(guild.id, author, message.channel):
        return

    now = datetime.datetime.now()
    last_grant = xp_cooldowns.get(author.id)
    if last_grant and (now - last_grant).total_seconds() < settings["cooldownSeconds"]:
        return
    xp_cooldowns[author.id] = now

    gained = random.randint(settings["xpMin"], settings["xpMax"])
    new_xp, new_level, leveled_up = add_xp(guild.id, author.id, gained)
    if not leveled_up:
        return

    # Role rewards: grant the highest-threshold role the member has reached.
    # stackRoles=True keeps every lower-tier reward role too; False swaps up.
    rewards = sorted(settings.get("roleRewards", []), key=lambda r: r.get("level", 0))
    earned = [r for r in rewards if r.get("level", 0) <= new_level]
    if earned:
        try:
            top_role = discord.utils.get(guild.roles, name=earned[-1]["roleName"])
            if top_role and top_role not in author.roles:
                await author.add_roles(top_role, reason=f"Leveling reward: reached level {new_level}")
            if not settings.get("stackRoles", True):
                lower_role_names = {r["roleName"] for r in earned[:-1]}
                lower_roles = [r for r in author.roles if r.name in lower_role_names]
                if lower_roles:
                    await author.remove_roles(*lower_roles, reason="Leveling reward: superseded by a higher tier")
        except discord.Forbidden:
            pass

    embed = discord.Embed(
        description=f"🎉 **{author.display_name}** leveled up to **Level {new_level}**!",
        color=discord.Color.gold(),
    )
    channel_name = settings.get("levelupChannelName")
    target_channel = discord.utils.get(guild.text_channels, name=channel_name) if channel_name else None
    if not target_channel:
        legacy_channel_id = get_levelup_channel(guild.id)
        target_channel = bot.get_channel(legacy_channel_id) if legacy_channel_id else message.channel
    if target_channel:
        await target_channel.send(embed=embed, delete_after=10)


async def leaderboard_push_loop():
    """Every ~60s, snapshots the top 10 XP earners per guild into MongoDB so
    the dashboard's Leveling tab can show a real leaderboard without needing
    a live connection into the bot's SQLite database."""
    await bot.wait_until_ready()
    while not bot.is_closed():
        if mongo_bridge.enabled():
            for guild in bot.guilds:
                rows = level_leaderboard(guild.id, limit=10)
                entries = []
                for user_id, xp, level in rows:
                    member = guild.get_member(user_id)
                    entries.append({
                        "userId": str(user_id),
                        "username": member.display_name if member else f"User {user_id}",
                        "avatarUrl": str(member.display_avatar.url) if member else None,
                        "xp": xp,
                        "level": level,
                    })
                await mongo_bridge.push_leaderboard(guild.id, entries)
        await asyncio.sleep(60)


@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return
    
    # --- REVENUE TRACKING AUTO-DETECTION ---
    # Check revenue reports FIRST before any other processing
    try:
        from bot.cogs.revenue import validate_and_record_revenue
        if await validate_and_record_revenue(message):
            return  # Message was a revenue report, already handled
    except Exception as e:
        print(f"⚠️ Revenue validation error: {e}")

    # --- AI LARGE-TEXT IMPORT SESSIONS ---
    try:
        from bot.cogs.ai_manager import handle_ai_import_message
        if await handle_ai_import_message(message):
            return
    except Exception as e:
        print(f"⚠️ AI import session handling error: {e}")

    if message.author.id in afk_users:
        data = afk_users.pop(message.author.id)
        try: await message.author.edit(nick=data["old_name"])
        except Exception: pass
        await message.channel.send(view=quick_card_view(f"👋 Welcome back {message.author.mention}! Your AFK status has been cleared."), delete_after=5)

    for mention in message.mentions:
        if mention.id in afk_users:
            data = afk_users[mention.id]
            embed = discord.Embed(description=f"💤 **{mention.display_name}** is currently AFK: `{data['reason']}`", color=discord.Color.light_grey())
            await message.channel.send(embed=embed, delete_after=6)

    # --- Vouch channel auto-listener (natural-language "vouch @user for X") ---
    vouch_channel_id = get_vouch_channel(message.guild.id)
    if vouch_channel_id and message.channel.id == vouch_channel_id:
        ctx = await bot.get_context(message)
        if ctx.valid:
            await bot.process_commands(message)
            return

        match = VOUCH_PATTERN.search(message.content)
        if match:
            target_id = int(match.group("id"))
            target = message.guild.get_member(target_id)

            if not target:
                return
            if target.id == message.author.id:
                await message.reply("❌ You can't vouch for yourself.", mention_author=False)
                return
            if target.bot:
                await message.reply("❌ You can't vouch for a bot.", mention_author=False)
                return

            reason = match.group("reason").strip(" .,!") or None
            if reason and len(reason) > MAX_REASON_LENGTH:
                reason = reason[:MAX_REASON_LENGTH].rstrip() + "…"

            add_vouch(message.guild.id, target.id, message.author.id, reason)
            total = count_vouches(message.guild.id, target.id)

            embed = discord.Embed(
                description=f"✅ {message.author.mention} vouched for {target.mention}",
                color=discord.Color.green(),
            )
            if reason:
                embed.add_field(name="Comment", value=reason, inline=False)
            embed.set_footer(text=f"{target.display_name} now has {total} vouch(es)")

            await message.reply(embed=embed, mention_author=False)
            return

    # --- DASHBOARD CUSTOM COMMANDS (from the website's "Custom Commands" tab) ---
    # These are managed on the dashboard (Mongo), so they're checked first and
    # take priority over the older SQLite-based custom command system below.
    dash_cmd = mongo_bridge.check_and_consume_custom_command(message.guild.id, message)
    if dash_cmd:
        text = mongo_bridge.substitute_variables(
            dash_cmd.get("response", ""), member=message.author, guild=message.guild, channel=message.channel
        )
        if dash_cmd.get("deleteInvoke"):
            try:
                await message.delete()
            except Exception:
                pass
        if dash_cmd.get("replyType") == "dm":
            try:
                await message.author.send(text)
            except Exception:
                pass
        elif dash_cmd.get("replyType") == "embed":
            await message.channel.send(view=quick_card_view(text))
        else:
            await message.channel.send(text)
        await mongo_bridge.bump_uses("customCommands", dash_cmd.get("_id"))
        return

    # --- DASHBOARD AUTO-RESPONDER (from the website's "Auto Responder" tab) ---
    dash_auto = mongo_bridge.check_and_consume_auto_response(message.guild.id, message)
    if dash_auto:
        text = mongo_bridge.substitute_variables(
            dash_auto.get("response", ""), member=message.author, guild=message.guild, channel=message.channel
        )
        if dash_auto.get("deleteInvoke"):
            try:
                await message.delete()
            except Exception:
                pass
        await message.channel.send(text)
        await mongo_bridge.bump_uses("autoResponses", dash_auto.get("_id"))
        return

    # --- CUSTOM AUTO-RESPONDER ("if someone writes X, bot sends Y") ---
    # Legacy SQLite-based system (predates the dashboard). Checked before
    # prefix/command handling so it works regardless of "?" and regardless
    # of role — anyone can trigger a custom auto-response.
    custom_response = get_custom_command(message.guild.id, message.content.strip().lower())
    if custom_response:
        await message.channel.send(custom_response)
        return

    if message.content.strip().startswith("?"):
        await bot.process_commands(message)
        return

    # --- NO-PREFIX COMMAND EXECUTION ---
    # Users granted no-prefix permission (staff, the trusted role, or an
    # individual grant) can run any bot command by typing it plain, e.g.
    # "kiss @user" or "ban @user spamming". Moderation-impact commands
    # still require a click-to-confirm step since there's no prefix to
    # signal "this is a command" and mistakes here are hard to undo.
    
    # Check if no-prefix system is globally enabled
    from bot.database import is_noprefix_enabled
    if is_noprefix_enabled():
        first_word = message.content.strip().split(" ")[0].lower() if message.content.strip() else ""
        candidate_command = bot.get_command(first_word) if first_word else None
        if candidate_command:
            ai_commands = {
                "ai", "aihelp", "aiimportprice", "aiimportrules", "aiprice",
                "airule", "aiservice", "aiconfig", "aiclear",
            }
            if first_word in ai_commands:
                try:
                    from bot.ai_manager_database import get_guild as get_ai_guild
                    ai_cfg = await get_ai_guild(message.guild.id)
                    if ai_cfg.get("aiEnabled") and ai_cfg.get("nonPrefixEnabled"):
                        # The hybrid command itself enforces staff / AI Manager role access.
                        await run_message_as_command(message)
                        return
                except Exception as exc:
                    print(f"⚠️ AI non-prefix check failed: {exc}")
                    return
            if has_noprefix_perm(message.guild, message.author):
                if first_word in NOPREFIX_CONFIRM_COMMANDS:
                    await send_noprefix_confirmation(message, first_word)
                else:
                    await run_message_as_command(message)
                return

    # Staff with Manage Messages skip automod, but MUST still run prefix commands.
    if message.author.guild_permissions.manage_messages:
        await handle_leveling(message)
        await bot.process_commands(message)
        return

    now = datetime.datetime.now()
    author_id = message.author.id
    settings = mongo_bridge.get_moderation_settings(message.guild.id)
    am = settings["automod"]

    if mongo_bridge.enabled() and mongo_bridge.is_ignored(message.guild.id, message.author, message.channel):
        # Still let leveling/commands run for exempt members — just skip automod.
        await handle_leveling(message)
        await bot.process_commands(message)
        return

    async def log_automod_action(reason_text: str):
        log_name = settings.get("logChannelName")
        if not log_name:
            return
        channel = discord.utils.get(message.guild.text_channels, name=log_name)
        if not channel:
            return
        embed = discord.Embed(
            description=f"🛡️ **{message.author.mention}** in {message.channel.mention}: {reason_text}",
            color=discord.Color.orange(),
        )
        try:
            await channel.send(view=embed_to_view(embed))
        except Exception:
            pass

    async def apply_automod_action(action: str, reason_text: str, duration_minutes: int = 10):
        current_warns = update_warnings(author_id, 1)
        try:
            await message.delete()
        except Exception:
            pass
        await log_automod_action(f"{reason_text} → action: `{action}`")

        if action == "warn":
            if current_warns >= 3:
                reset_warnings(author_id)
                try:
                    await message.author.timeout(datetime.timedelta(minutes=10), reason="AutoMod Violation Threshold")
                    await message.channel.send(view=quick_card_view(f"🤫 **{message.author.display_name}** has been auto-timed out for 10 minutes after receiving 3 warnings."))
                except Exception:
                    pass
            else:
                await message.channel.send(view=quick_card_view(f"⚠️ **{message.author.display_name}**, your message was removed for **{reason_text}**. ({current_warns}/3)"), delete_after=6)
        elif action == "mute":
            try:
                await message.author.timeout(datetime.timedelta(minutes=duration_minutes), reason=f"AutoMod: {reason_text}")
                await message.channel.send(view=quick_card_view(f"🔇 **{message.author.display_name}** was muted for {duration_minutes}m — {reason_text}."), delete_after=8)
            except Exception:
                pass
        elif action == "kick":
            try:
                await message.author.kick(reason=f"AutoMod: {reason_text}")
                await message.channel.send(view=quick_card_view(f"👢 **{message.author.display_name}** was kicked — {reason_text}."), delete_after=8)
            except Exception:
                pass
        elif action == "ban":
            try:
                await message.author.ban(reason=f"AutoMod: {reason_text}")
                await message.channel.send(view=quick_card_view(f"🔨 **{message.author.display_name}** was banned — {reason_text}."), delete_after=8)
            except Exception:
                pass
        # action == "delete" falls through — message is already gone above.

    # Legacy fallback path when there's no dashboard/Mongo connection at all,
    # so the bot still has *some* automod instead of none.
    async def issue_warning(reason_text):
        await apply_automod_action("warn", reason_text)

    if am["antiSpam"]["enabled"]:
        if author_id in user_message_cooldowns:
            timestamps = user_message_cooldowns[author_id]
            timestamps = [t for t in timestamps if (now - t).total_seconds() < am["antiSpam"]["interval"]]
            timestamps.append(now)
            user_message_cooldowns[author_id] = timestamps
            if len(timestamps) > am["antiSpam"]["maxMsgs"]:
                await apply_automod_action(am["antiSpam"]["action"], "Spamming messages too fast", am["antiSpam"]["duration"])
                return
        else:
            user_message_cooldowns[author_id] = [now]

    if am["massPing"]["enabled"] and ((len(message.mentions) + len(message.role_mentions)) > am["massPing"]["maxPings"] or message.mention_everyone):
        await apply_automod_action(am["massPing"]["action"], "Mass ping violations", am["massPing"]["duration"])
        return

    msg_lower = message.content.lower()

    if am["invites"]["enabled"] and ("discord.gg/" in msg_lower or "discord.com/invite/" in msg_lower):
        own_code = getattr(message.guild, "vanity_url_code", None)
        is_own_invite = bool(am["invites"]["allowOwn"] and own_code and own_code.lower() in msg_lower)
        if not is_own_invite:
            await apply_automod_action(am["invites"]["action"], "Advertising external invite links")
            return

    if am["linkFilter"]["enabled"]:
        urls = re.findall(r"https?://([\w.-]+)", msg_lower)
        if urls:
            mode = am["linkFilter"]["mode"]
            if mode == "blacklist":
                blocked = any(any(bad.lower() in url for bad in am["linkFilter"]["blacklist"]) for url in urls)
            else:  # whitelist mode — block anything NOT explicitly allowed
                allowed = [w.lower() for w in am["linkFilter"]["whitelist"]]
                blocked = any(not any(ok in url for ok in allowed) for url in urls)
            if blocked:
                await apply_automod_action(am["linkFilter"]["action"], "Posted a disallowed link")
                return

    if am["emojiSpam"]["enabled"] and (message.content.count("<:") + message.content.count("<a:")) > am["emojiSpam"]["maxEmojis"]:
        await apply_automod_action(am["emojiSpam"]["action"], "Emoji flood violations")
        return

    if am["wordFilter"]["enabled"] and am["wordFilter"]["words"] and any(word.lower() in msg_lower for word in am["wordFilter"]["words"]):
        await apply_automod_action(am["wordFilter"]["action"], "Using blocked language")
        return

    if am["dupMessages"]["enabled"]:
        history = _recent_messages.setdefault(author_id, [])
        history.append(msg_lower)
        del history[:-am["dupMessages"]["threshold"]]  # keep only the last `threshold` messages
        if len(history) >= am["dupMessages"]["threshold"] and len(set(history)) == 1:
            await apply_automod_action(am["dupMessages"]["action"], "Repeated duplicate messages")
            return

    if am["capsLock"]["enabled"] and len(message.content) > am["capsLock"]["minLength"]:
        uppercase_letters = sum(1 for c in message.content if c.isupper())
        total_letters = sum(1 for c in message.content if c.isalpha())
        if total_letters > 0 and (uppercase_letters / total_letters) > (am["capsLock"]["threshold"] / 100):
            await apply_automod_action(am["capsLock"]["action"], "Excessive Caps Lock usage")
            return

    # --- LEVELING: grant XP for messages that passed every automod check ---
    await handle_leveling(message)

    # Fallback: ensure any remaining prefix commands still process
    await bot.process_commands(message)


# --- PROCESS ENTRY POINT ---
def _load_token() -> str:
    raw = os.getenv("DISCORD_TOKEN") or os.getenv("BOT_TOKEN")
    if not raw:
        raise RuntimeError("DISCORD_TOKEN or BOT_TOKEN is not configured")
    token = raw.strip()
    if (token.startswith("\"") and token.endswith("\"")) or (token.startswith("'") and token.endswith("'")):
        token = token[1:-1].strip()
    if token.lower().startswith("bot "):
        token = token[4:].strip()
    return token


def main():
    token = _load_token()
    port = os.getenv("PORT")
    if port:
        try:
            from threading import Thread
            from bot.status import run_server
            Thread(target=run_server, daemon=True).start()
        except Exception as exc:
            print(f"⚠️ Keepalive server not started: {exc}")
    bot.run(token)
