"""
community.py — Help menu, control panel, setup dropdowns, announcements, leveling cmds, dashboard links, no-prefix helpers.
Extracted from the original monolithic bot.py. Logic unchanged.
"""
import discord
from discord.ext import commands
import discord.app_commands as app_commands
import datetime
import asyncio
import random
import re
import requests

from bot.config import (
    bot, quick_embed, style_embed, REQUIRED_ROLE_ID, UTC, BRAND_COLOR,
    afk_users,
    SUPPORT_SERVER_URL, DASHBOARD_URL, INVITE_URL, GIPHY_API_KEY, fetch_giphy_gif_url,
    has_required_slash_role, mod_group, LEVELING_SYSTEM_ENABLED, EMOJI_BULLET,
)
from bot.database import (
    get_level_data, add_xp, level_leaderboard, xp_for_level,
    is_leveling_enabled, get_levelup_channel,
    get_all_role_menu_message_ids, get_role_menu_items,
    has_noprefix_perm, get_trusted_role_id, list_noprefix_users,
    set_config, get_config, add_vouch, count_vouches,
)


# --- NO-PREFIX ---
# ==========================================
#      🔓 NO-PREFIX COMMAND EXECUTION
# ==========================================
# Commands that change server/member state enough that a typo or joke
# message could cause real damage if it fired instantly with no prefix.
# These always get a Confirm/Cancel button before running when triggered
# without "?".
NOPREFIX_CONFIRM_COMMANDS = {
    "warn", "clearwarnings", "mute", "unmute", "kick", "ban", "unban", "bon",
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
            await interaction.response.send_message(embed=quick_embed("❌ Only the person who typed this command can confirm it."), ephemeral=True)
            return
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="✅ **Confirmed — executing...**", view=self)
        await run_message_as_command(self.message)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(embed=quick_embed("❌ Only the person who typed this command can cancel it."), ephemeral=True)
            return
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="❌ **Cancelled.** No action was taken.", view=self)
        self.stop()

async def send_noprefix_confirmation(message: discord.Message, command_name: str):
    view = NoPrefixModConfirmView(message, message.author)
    await message.reply(
        f"⚠️ You typed a **moderation command** (`{command_name}`) without the `?` prefix.\n"
        f"Run `{message.content}`?",
        view=view,
        mention_author=False,
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
        await ctx.send(embed=style_embed(
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
    await ctx.send(embed=embed)

@bot.hybrid_command(name="levelleaderboard", aliases=["levellb", "ranklb", "ll", "levels"], description="Show the top XP earners in this server")
async def level_leaderboard_prefix(ctx):
    if not LEVELING_SYSTEM_ENABLED:
        await ctx.send(embed=style_embed(
            "Leveling Disabled",
            kind="info",
            description=f"{EMOJI_BULLET} Built-in leveling is turned off.\n{EMOJI_BULLET} Use a dedicated leveling bot if you need XP ranks.",
        ))
        return
    rows = level_leaderboard(ctx.guild.id, limit=10)
    if not rows:
        await ctx.send(embed=quick_embed("No one has earned XP in this server yet."))
        return
    lines = []
    for i, (user_id, xp, level) in enumerate(rows, start=1):
        member = ctx.guild.get_member(user_id)
        name = member.mention if member else f"<@{user_id}>"
        lines.append(f"**{i}.** {name} — Level {level} ({xp} XP)")
    embed = discord.Embed(title="📈 Level Leaderboard", description="\n".join(lines), color=discord.Color.blurple())
    await ctx.send(embed=embed)



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
@commands.has_role(REQUIRED_ROLE_ID)
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
        main_embed = discord.Embed(title="🐰 ── 𝐔𝐍𝐈𝐓𝐄𝐃 𝐁𝐔𝐍𝐍𝐈𝐄𝐒 ── 🐰", description=main_desc, color=0x2f3136, timestamp=datetime.datetime.now(UTC))
        for part in parts[1:]:
            part = part.strip()
            if not part: continue
            lines = part.split("\n", 1)
            main_embed.add_field(name=f"🐰 ─── {lines[0].strip().upper()} ─── 🐰", value=lines[1].strip() if len(lines) > 1 else "...", inline=False)
    else:
        parts = cleaned_text.split("[FIELD]")
        main_desc = parts[0].strip()
        main_embed = discord.Embed(title="🐰 ── 𝐔𝐍𝐈𝐓𝐄𝐃 𝐁𝐔𝐍𝐍𝐈𝐄𝐒 ── 🐰", description=main_desc, color=0x2f3136, timestamp=datetime.datetime.now(UTC))
        for part in parts[1:]:
            part = part.strip()
            if not part: continue
            lines = part.split('\n', 1)
            main_embed.add_field(name=lines[0].strip(), value=lines[1].strip() if len(lines) > 1 else "...", inline=False)

    main_embed.set_footer(text="🐰 Matrix System Active 🌟")
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
            await interaction.response.send_message(embed=quick_embed("❌ Couldn't find a valid user ID or mention in that."), ephemeral=True)
            return

        target_id = int(match.group())
        target = interaction.guild.get_member(target_id)
        if target is None:
            await interaction.response.send_message(embed=quick_embed("❌ Couldn't find that member in this server."), ephemeral=True)
            return
        if target.id == interaction.user.id:
            await interaction.response.send_message(embed=quick_embed("❌ You can't vouch for yourself."), ephemeral=True)
            return
        if target.bot:
            await interaction.response.send_message(embed=quick_embed("❌ You can't vouch for a bot."), ephemeral=True)
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
        await interaction.response.send_message(embed=embed)


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
    await ctx.send(embed=quick_embed(f"💤 {ctx.author.mention} is now AFK."))

@bot.hybrid_command(name="ping", description="Check the bot's latency")
async def ping_prefix(ctx):
    await ctx.send(embed=style_embed(
        "Ping",
        kind="info",
        description=f"{EMOJI_BULLET} latency: **{round(bot.latency * 1000)}ms**",
    ))

async def send_gif_embed(channel, query: str, title: str = None):
    loop = asyncio.get_running_loop()
    gif_url = await loop.run_in_executor(None, fetch_giphy_gif_url, query)
    if not gif_url:
        if not GIPHY_API_KEY:
            await channel.send(embed=quick_embed("❌ GIPHY_API_KEY is missing on the server."))
        else:
            await channel.send(embed=quick_embed("❌ No GIF found. Try different keywords."))
        return
    embed = discord.Embed(color=0x2f3136, timestamp=datetime.datetime.now(UTC))
    if title:
        embed.title = title
    embed.set_image(url=gif_url)
    await channel.send(embed=embed)

@bot.hybrid_command(name="gif", description="Send a random GIF for a keyword")
@app_commands.describe(query="Search keywords")
async def gif_prefix(ctx, *, query: str = None):
    if not query:
        await ctx.send(embed=quick_embed("❌ Syntax: `?gif <search keywords>`"))
        return
    async with ctx.typing():
        await send_gif_embed(ctx.channel, query, title=f"GIF: {query}")

async def action_gif(ctx, action: str, target: discord.Member = None, query: str = None):
    target = target or ctx.author
    text = f"{ctx.author.mention} {action} {target.mention}"
    await ctx.send(text)
    async with ctx.typing():
        await send_gif_embed(ctx.channel, query or f"{action} gif", title=None)

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
    await ctx.send(embed=quick_embed(f"🎲 You rolled a **{result}** (1-{sides})"))

@bot.hybrid_command(name="coinflip", aliases=["flip"], description="Flip a coin")
async def coinflip_prefix(ctx):
    result = random.choice(["Heads", "Tails"])
    await ctx.send(embed=quick_embed(f"🪙 **{result}!**"))

@bot.hybrid_command(name="choose", description="Pick randomly between options")
@app_commands.describe(options="Options separated by | (e.g. a | b | c)")
async def choose_prefix(ctx, *, options: str = None):
    if not options or "|" not in options:
        await ctx.send(embed=quick_embed("❌ Syntax: `?choose option1 | option2 | option3`"))
        return
    choices = [o.strip() for o in options.split("|") if o.strip()]
    if len(choices) < 2:
        await ctx.send(embed=quick_embed("❌ Give me at least two options, separated by `|`."))
        return
    await ctx.send(embed=quick_embed(f"🤔 I choose: **{random.choice(choices)}**"))

@bot.hybrid_command(name="8ball", description="Ask the magic 8-ball a question")
@app_commands.describe(question="Your question")
async def eightball_prefix(ctx, *, question: str = None):
    if not question:
        await ctx.send(embed=quick_embed("❌ Syntax: `?8ball <question>`"))
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
    await ctx.send(embed=quick_embed(f"🎱 {random.choice(answers)}"))

@bot.hybrid_command(name="avatar", description="Get a user's avatar")
@app_commands.describe(member="User to check (defaults to yourself)")
async def avatar_prefix(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"{member.display_name}'s Avatar", color=0x2f3136)
    embed.set_image(url=member.display_avatar.url)
    await ctx.send(embed=embed)

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
    await ctx.send(embed=embed)

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
    await ctx.send(embed=embed)

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
        await ctx.send(embed=quick_embed("❌ Meme fetch failed. Try again."))
        return
    embed = discord.Embed(title=title, color=0x2f3136)
    embed.set_image(url=meme_url)
    await ctx.send(embed=embed)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRole) or isinstance(error, commands.MissingPermissions):
        await ctx.send(embed=quick_embed("❌ You don't have permission to use that command."), delete_after=6)
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(embed=quick_embed("❌ Missing arguments. Use `?help` for usage."), delete_after=6)
        return
    if isinstance(error, commands.CheckFailure):
        await ctx.send(str(error) or "❌ You don't have permission to use that command.", delete_after=6)
        return
    await ctx.send(embed=quick_embed(f"❌ Error: {error}"), delete_after=8)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        if interaction.response.is_done():
            await interaction.followup.send("❌ You don't have permission to use that command.", ephemeral=True)
        else:
            await interaction.response.send_message(embed=quick_embed("❌ You don't have permission to use that command."), ephemeral=True)
        return
    if interaction.response.is_done():
        await interaction.followup.send(f"❌ Error: {error}", ephemeral=True)
    else:
        await interaction.response.send_message(embed=quick_embed(f"❌ Error: {error}"), ephemeral=True)


