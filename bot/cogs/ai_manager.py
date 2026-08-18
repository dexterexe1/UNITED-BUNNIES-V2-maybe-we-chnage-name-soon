from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import aiohttp
import discord
from discord.ext import commands
import discord.app_commands as app_commands

from bot.config import bot, BOT_OWNER_IDS, is_staff, style_embed, BRAND_COLOR, UTC
from bot.ai_manager_database import (
    init as init_ai_db,
    get_guild,
    set_ai_enabled,
    set_nonprefix_enabled,
    set_manager_role,
    clear_category,
    clear_price_sheets,
    clear_rule_sheets,
    clear_all,
    add_price,
    remove_price,
    add_price_sheet,
    add_rule_sheet,
    add_rule,
    remove_rule,
    add_service,
    remove_service,
)

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '').strip()
GEMINI_MODEL = os.getenv('GEMINI_AI_MANAGER_MODEL', os.getenv('GEMINI_PAYMENT_MODEL', 'gemini-3.5-flash-lite')).strip()
AI_ENABLED = os.getenv('AI_MANAGER_ENABLED', 'true').strip().lower() in {'1', 'true', 'yes', 'on'}

_PENDING_ACTIONS: dict[int, dict[str, Any]] = {}

_IMPORT_SESSIONS: dict[tuple[int, int], dict[str, Any]] = {}
_IMPORT_TIMEOUT_SECONDS = 10 * 60
_IMPORT_MAX_MESSAGES = 100
_IMPORT_MAX_CHARS = 120_000


def _is_owner(user_id: int) -> bool:
    return int(user_id) in BOT_OWNER_IDS


async def _ai_allowed(ctx: commands.Context) -> bool:
    if not ctx.guild or not AI_ENABLED:
        return False
    data = await get_guild(ctx.guild.id)
    if not data.get('aiEnabled'):
        return False
    member = ctx.author if isinstance(ctx.author, discord.Member) else None
    if _is_owner(ctx.author.id):
        return True
    role_id = data.get('managerRoleId')
    if member and role_id and any(r.id == int(role_id) for r in member.roles):
        return True
    return bool(member and is_staff(member, need='mod'))


async def _management_allowed(ctx: commands.Context) -> bool:
    if not await _ai_allowed(ctx):
        return False
    data = await get_guild(ctx.guild.id)
    role_id = data.get('managerRoleId')
    if _is_owner(ctx.author.id):
        return True
    member = ctx.author if isinstance(ctx.author, discord.Member) else None
    if not member:
        return False
    if role_id and any(r.id == int(role_id) for r in member.roles):
        return True
    return is_staff(member, need='mod')


def _disabled_message():
    return style_embed('AI Manager Locked', description='🔒 AI Manager is not enabled for this server yet. Ask the bot owner to enable premium AI for this server.', kind='warn')


class ServerSelectorView(discord.ui.View):
    def __init__(self, owner_id: int, action: str, guilds: list[discord.Guild], page: int = 0):
        super().__init__(timeout=120)
        self.owner_id = owner_id
        self.action = action
        self.guilds = guilds
        self.page = page
        start = page * 25
        current = guilds[start:start + 25]
        options = [
            discord.SelectOption(
                label=g.name[:100],
                value=str(g.id),
                description=('AI: ' + ('ON' if getattr(g, '_ai_on', False) else 'OFF'))[:100],
            )
            for g in current
        ]
        if not options:
            options = [discord.SelectOption(label='No servers available', value='0')]
        self.add_item(ServerSelect(self, options))
        if page > 0:
            self.add_item(PageButton(self, 'prev'))
        if (page + 1) * 25 < len(guilds):
            self.add_item(PageButton(self, 'next'))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message('❌ Only the bot owner who opened this menu can use it.', ephemeral=True)
            return False
        return True


class ServerSelect(discord.ui.Select):
    def __init__(self, parent: ServerSelectorView, options):
        self.parent_view = parent
        super().__init__(placeholder='Select a server…', options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        gid = int(self.values[0])
        guild = discord.utils.get(self.parent_view.guilds, id=gid)
        if not guild:
            await interaction.response.send_message('❌ Server not found in the bot guild list.', ephemeral=True)
            return
        data = await get_guild(gid)
        if self.parent_view.action == 'ai':
            data = await set_ai_enabled(gid, True)
            text = f'✅ **AI Manager enabled** for **{guild.name}**.\nAI commands are now available to that server’s staff/AI Manager role.'
        elif self.parent_view.action == 'ai_disable':
            data = await set_ai_enabled(gid, False)
            await set_nonprefix_enabled(gid, False)
            text = f'🔒 **AI Manager disabled** for **{guild.name}**. AI non-prefix was disabled too.'
        elif self.parent_view.action == 'nonprefix':
            if not data.get('aiEnabled'):
                await interaction.response.send_message('❌ Enable AI Manager for that server first.', ephemeral=True)
                return
            await set_nonprefix_enabled(gid, True)
            text = f'✅ **AI non-prefix enabled** for **{guild.name}**.'
        else:
            await set_nonprefix_enabled(gid, False)
            text = f'🔒 **AI non-prefix disabled** for **{guild.name}**.'
        embed = style_embed('Premium AI Manager', description=text, kind='success')
        await interaction.response.edit_message(embed=embed, view=None)


class PageButton(discord.ui.Button):
    def __init__(self, parent: ServerSelectorView, direction: str):
        super().__init__(label='Previous' if direction == 'prev' else 'Next', style=discord.ButtonStyle.secondary)
        self.parent_view = parent
        self.direction = direction

    async def callback(self, interaction: discord.Interaction):
        delta = -1 if self.direction == 'prev' else 1
        page = self.parent_view.page + delta
        await interaction.response.edit_message(view=ServerSelectorView(self.parent_view.owner_id, self.parent_view.action, self.parent_view.guilds, page))


class AIActionView(discord.ui.View):
    def __init__(self, author_id: int, action_id: int):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.action_id = action_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message('❌ Only the person who requested the action can confirm it.', ephemeral=True)
            return False
        return True

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.success, emoji='✅')
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        action = _PENDING_ACTIONS.pop(self.action_id, None)
        if not action:
            await interaction.response.edit_message(content='⌛ This action expired.', view=None)
            return
        for child in self.children:
            child.disabled = True
        guild = interaction.guild
        try:
            if action['type'] == 'create_role':
                perms = discord.Permissions.none()
                for p in action.get('permissions', []):
                    if hasattr(perms, p) and p not in {'administrator', 'manage_guild'}:
                        setattr(perms, p, True)
                role = await guild.create_role(name=action['name'][:100], permissions=perms, reason='AI Manager confirmed action')
                result = f'✅ Created role {role.mention}.'
            elif action['type'] == 'create_channel':
                channel = await guild.create_text_channel(name=action['name'][:90], reason='AI Manager confirmed action')
                result = f'✅ Created channel {channel.mention}.'
            elif action['type'] == 'add_role':
                member = guild.get_member(int(action['member_id']))
                role = discord.utils.get(guild.roles, name=action['role_name'])
                if not member or not role:
                    raise ValueError('Member or role was not found.')
                await member.add_roles(role, reason='AI Manager confirmed action')
                result = f'✅ Added {role.mention} to {member.mention}.'
            else:
                raise ValueError('Unsupported AI action.')
            await interaction.response.edit_message(content=result, view=None)
        except Exception as exc:
            await interaction.response.edit_message(content=f'❌ Could not complete the action: `{exc}`', view=None)

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.secondary, emoji='✖️')
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        _PENDING_ACTIONS.pop(self.action_id, None)
        await interaction.response.edit_message(content='❌ Action cancelled.', view=None)


def _session_key(guild_id: int, user_id: int) -> tuple[int, int]:
    return (int(guild_id), int(user_id))


def _start_import_session(guild_id: int, user_id: int, kind: str, title: str = "") -> dict[str, Any]:
    session = {
        "guild_id": int(guild_id),
        "user_id": int(user_id),
        "kind": kind,
        "title": title.strip() or ("Imported Prices" if kind == "price" else "Imported Rules"),
        "parts": [],
        "started_at": time.monotonic(),
    }
    _IMPORT_SESSIONS[_session_key(guild_id, user_id)] = session
    return session


def _cancel_import_session(guild_id: int, user_id: int) -> None:
    _IMPORT_SESSIONS.pop(_session_key(guild_id, user_id), None)


def _get_import_session(guild_id: int, user_id: int) -> dict[str, Any] | None:
    session = _IMPORT_SESSIONS.get(_session_key(guild_id, user_id))
    if not session:
        return None
    if time.monotonic() - float(session.get("started_at", 0)) > _IMPORT_TIMEOUT_SECONDS:
        _cancel_import_session(guild_id, user_id)
        return None
    return session


async def _finish_import_session(ctx: commands.Context, session: dict[str, Any]) -> None:
    combined = "\n".join(session.get("parts") or []).strip()
    if not combined:
        _cancel_import_session(ctx.guild.id, ctx.author.id)
        await ctx.send(embed=style_embed("AI Import Cancelled", description="❌ No text was collected.", kind="warn"), delete_after=8)
        return
    title = session.get("title") or ("Imported Prices" if session.get("kind") == "price" else "Imported Rules")
    if session.get("kind") == "price":
        await add_price_sheet(ctx.guild.id, title, combined)
        heading = "AI Price Data Imported"
        desc = f"✅ Imported **{len(session['parts'])} message(s)** / **{len(combined):,} characters** as **{title}**.\n\nThe complete pricing text is stored for this server and used by `?ai` for price questions."
    else:
        await add_rule_sheet(ctx.guild.id, title, combined)
        heading = "AI Rules Imported"
        desc = f"✅ Imported **{len(session['parts'])} message(s)** / **{len(combined):,} characters** as **{title}**.\n\nThe complete rules/policy text is stored for this server and used by `?ai` for rule questions."
    _cancel_import_session(ctx.guild.id, ctx.author.id)
    await ctx.send(embed=style_embed(heading, description=desc, kind="success"))


async def handle_ai_import_message(message: discord.Message) -> bool:
    """Consume messages while a staff member is in an AI price/rules import session."""
    if not message.guild or message.author.bot:
        return False
    session = _get_import_session(message.guild.id, message.author.id)
    if not session:
        return False
    content = message.content.strip()
    if content.casefold() in {"cancel", "abort", "stop"}:
        _cancel_import_session(message.guild.id, message.author.id)
        await message.reply("❌ AI import cancelled. Nothing was saved.", mention_author=False, delete_after=8)
        return True
    if content.casefold() in {"done", "finish", "finished"}:
        ctx = await bot.get_context(message)
        await _finish_import_session(ctx, session)
        return True
    if len(session["parts"]) >= _IMPORT_MAX_MESSAGES:
        _cancel_import_session(message.guild.id, message.author.id)
        await message.reply(f"❌ Import stopped after {_IMPORT_MAX_MESSAGES} messages. Nothing was saved.", mention_author=False, delete_after=10)
        return True
    current = sum(len(part) for part in session["parts"])
    if current + len(content) > _IMPORT_MAX_CHARS:
        _cancel_import_session(message.guild.id, message.author.id)
        await message.reply(f"❌ Import is too large. Maximum is {_IMPORT_MAX_CHARS:,} characters. Nothing was saved.", mention_author=False, delete_after=10)
        return True
    session["parts"].append(content)
    await message.reply(
        f"✅ Added **part {len(session['parts'])}**. Total **{current + len(content):,} chars**. Send more or type `done`.",
        mention_author=False,
        delete_after=5,
    )
    return True


def _relevant_sheet_text(text: str, query: str, max_chars: int = 14000) -> str:
    raw = str(text or "").strip()
    if len(raw) <= max_chars:
        return raw
    tokens = [t for t in re.findall(r"[a-z0-9+]+", query.casefold()) if len(t) >= 3]
    blocks = re.split(r"\n\s*\n", raw)
    scored = []
    for idx, block in enumerate(blocks):
        low = block.casefold()
        score = sum(low.count(tok) for tok in tokens)
        if score:
            scored.append((score, idx, block))
    if not scored:
        return raw[:max_chars] + "\n…[import truncated for this query]"
    scored.sort(key=lambda row: (-row[0], row[1]))
    out = []
    size = 0
    for _, _, block in scored:
        if size + len(block) + 2 > max_chars:
            break
        out.append(block)
        size += len(block) + 2
    return "\n\n".join(out) or raw[:max_chars]


async def _gemini(text: str, ctx: commands.Context, data: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """Call Gemini and return (result, error_reason). error_reason is None on success."""
    if not AI_ENABLED:
        return None, 'disabled'
    if not GEMINI_API_KEY:
        return None, 'no_key'
    knowledge = {
        'prices': data.get('prices') or [],
        'rules': data.get('rules') or [],
        'services': data.get('services') or [],
        'priceSheets': [
            {'title': s.get('title', 'Imported Prices'), 'text': _relevant_sheet_text(s.get('text', ''), text)}
            for s in (data.get('priceSheets') or [])
        ],
        'ruleSheets': [
            {'title': s.get('title', 'Imported Rules'), 'text': _relevant_sheet_text(s.get('text', ''), text)}
            for s in (data.get('ruleSheets') or [])
        ],
    }
    prompt = f"""You are the private AI manager for the Discord server {ctx.guild.name!r}.
Use ONLY the server knowledge below for prices, services, rules, and policies. Never invent a price or rule. If the answer is not in the knowledge, say it is not configured.

SERVER KNOWLEDGE:
{json.dumps(knowledge, ensure_ascii=False)}

USER REQUEST:
{text}

Return JSON only with this shape:
{{"mode":"answer|action","answer":"...","action":{{"type":"create_role|create_channel|add_role|null","name":"","permissions":[],"role_name":"","member_id":""}}}}

Safe action rules:
- create_role permissions may include manage_messages, moderate_members, kick_members, ban_members, manage_channels, read_message_history, send_messages, view_channel, mute_members, deafen_members.
- NEVER request administrator or manage_guild.
- Only create a role/channel/add an existing role if the user clearly asks.
- For questions, use mode=answer and action=null.
"""
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent'
    payload = {'contents': [{'parts': [{'text': prompt}]}], 'generationConfig': {'temperature': 0, 'responseMimeType': 'application/json'}}
    headers = {'Content-Type': 'application/json', 'x-goog-api-key': GEMINI_API_KEY}
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 400:
                    body = await response.text()
                    print(f'❌ Gemini API 400 Bad Request: {body[:2000]}')
                    return None, 'bad_request'
                if response.status == 401 or response.status == 403:
                    body = await response.text()
                    print(f'❌ Gemini API {response.status} Auth error: {body[:2000]}')
                    return None, 'bad_key'
                if response.status == 429:
                    print(f'❌ Gemini API 429 Rate limited')
                    return None, 'rate_limit'
                if response.status != 200:
                    body = await response.text()
                    print(f'❌ Gemini API error {response.status}: {body[:2000]}')
                    return None, f'http_{response.status}'
                raw = await response.json()
        text_out = ''.join(part.get('text', '') for c in raw.get('candidates', []) for part in c.get('content', {}).get('parts', []) if isinstance(part.get('text'), str)).strip()
        text_out = re.sub(r'^```(?:json)?\s*|\s*```$', '', text_out, flags=re.I)
        result = json.loads(text_out)
        return (result if isinstance(result, dict) else None), None
    except aiohttp.ClientConnectorError as exc:
        print(f'⚠️ AI Manager network error: {exc}')
        return None, 'network'
    except aiohttp.ServerTimeoutError:
        print(f'⚠️ AI Manager request timed out')
        return None, 'timeout'
    except json.JSONDecodeError as exc:
        print(f'⚠️ AI Manager bad JSON response: {exc}')
        return None, 'bad_response'
    except Exception as exc:
        print(f'⚠️ AI Manager request failed: {exc}')
        return None, 'unknown'


@bot.hybrid_command(name='provideai', help='Bot owner: enable premium AI Manager for a server, using a server selector if no server is given.')
@app_commands.describe(server='Server name or ID; leave empty to open the full bot server selector.')
async def provide_ai(ctx: commands.Context, *, server: str = ''):
    if not _is_owner(ctx.author.id):
        await ctx.send(embed=style_embed('Unauthorized', description='Only bot owners can provide premium AI Manager access.', kind='error'))
        return
    guilds = list(bot.guilds)
    if not server.strip():
        embed = style_embed('Premium AI Manager', description=f'Select a server below. The bot is currently in **{len(guilds)}** servers. You do not need to personally be a member of the selected server.', kind='info')
        await ctx.send(embed=embed, view=ServerSelectorView(ctx.author.id, 'ai', guilds))
        return
    target = _find_guild(server)
    if not target:
        await ctx.send(embed=style_embed('Server Not Found', description='Use the server name/ID of a guild the bot is currently in, or omit the argument to use the selector.', kind='error'))
        return
    await set_ai_enabled(target.id, True)
    await ctx.send(embed=style_embed('AI Manager Enabled', description=f'✅ Premium AI Manager is enabled for **{target.name}**.', kind='success'))


def _find_guild(query: str):
    q = query.strip().casefold().strip('"')
    if q.isdigit():
        g = bot.get_guild(int(q))
        if g:
            return g
    exact = [g for g in bot.guilds if g.name.casefold() == q]
    if exact:
        return exact[0]
    return next((g for g in bot.guilds if q in g.name.casefold()), None)


@bot.hybrid_command(name='disableai', help='Bot owner: disable premium AI Manager for a server.')
@app_commands.describe(server='Server name or ID; leave empty for the selector.')
async def disable_ai(ctx: commands.Context, *, server: str = ''):
    if not _is_owner(ctx.author.id):
        await ctx.send(embed=style_embed('Unauthorized', description='Only bot owners can disable premium AI.', kind='error'))
        return
    if not server.strip():
        await ctx.send(embed=style_embed('Disable AI', description='Select a server.', kind='warn'), view=ServerSelectorView(ctx.author.id, 'ai_disable', list(bot.guilds)))
        return
    target = _find_guild(server)
    if not target:
        await ctx.send(embed=style_embed('Server Not Found', description='The bot is not in that server.', kind='error'))
        return
    await set_ai_enabled(target.id, False)
    await set_nonprefix_enabled(target.id, False)
    await ctx.send(embed=style_embed('AI Manager Disabled', description=f'🔒 AI Manager and AI non-prefix are disabled for **{target.name}**.', kind='success'))


@bot.hybrid_command(name='providenonprefix', help='Bot owner: enable AI non-prefix for a server with AI Manager already enabled.')
@app_commands.describe(server='Server name or ID; leave empty for the selector.')
async def provide_nonprefix(ctx: commands.Context, *, server: str = ''):
    if not _is_owner(ctx.author.id):
        await ctx.send(embed=style_embed('Unauthorized', description='Only bot owners can enable premium AI non-prefix.', kind='error'))
        return
    if not server.strip():
        await ctx.send(embed=style_embed('AI Non-Prefix', description='Select a server.', kind='info'), view=ServerSelectorView(ctx.author.id, 'nonprefix', list(bot.guilds)))
        return
    target = _find_guild(server)
    if not target:
        await ctx.send(embed=style_embed('Server Not Found', description='The bot is not in that server.', kind='error'))
        return
    data = await get_guild(target.id)
    if not data.get('aiEnabled'):
        await ctx.send(embed=style_embed('Enable AI First', description='Run `?provideai` for this server first.', kind='warn'))
        return
    await set_nonprefix_enabled(target.id, True)
    await ctx.send(embed=style_embed('AI Non-Prefix Enabled', description=f'✅ Non-prefix AI commands are enabled for **{target.name}**.', kind='success'))


@bot.hybrid_command(name='disablenonprefix', help='Bot owner: disable AI non-prefix for a server.')
@app_commands.describe(server='Server name or ID; leave empty for the selector.')
async def disable_nonprefix(ctx: commands.Context, *, server: str = ''):
    if not _is_owner(ctx.author.id):
        await ctx.send(embed=style_embed('Unauthorized', description='Only bot owners can disable premium AI non-prefix.', kind='error'))
        return
    if not server.strip():
        await ctx.send(embed=style_embed('AI Non-Prefix', description='Select a server.', kind='info'), view=ServerSelectorView(ctx.author.id, 'nonprefix_disable', list(bot.guilds)))
        return
    target = _find_guild(server)
    if not target:
        await ctx.send(embed=style_embed('Server Not Found', description='The bot is not in that server.', kind='error'))
        return
    await set_nonprefix_enabled(target.id, False)
    await ctx.send(embed=style_embed('AI Non-Prefix Disabled', description=f'🔒 Non-prefix AI commands are disabled for **{target.name}**.', kind='success'))


@bot.hybrid_command(name='aistatus', help='Bot owner: check premium AI status for a server.')
@app_commands.describe(server='Server name or ID; leave empty for the current server.')
async def ai_status(ctx: commands.Context, *, server: str = ''):
    if not _is_owner(ctx.author.id):
        await ctx.send(embed=style_embed('Unauthorized', description='Only bot owners can use AI status.', kind='error'))
        return
    target = _find_guild(server) if server.strip() else ctx.guild
    if not target:
        await ctx.send(embed=style_embed('Server Not Found', description='Select/provide a server.', kind='error'))
        return
    data = await get_guild(target.id)
    role = target.get_role(int(data['managerRoleId'])) if data.get('managerRoleId') else None
    desc = f"**Server:** {target.name}\n**Server ID:** `{target.id}`\n**AI Manager:** {'✅ Enabled' if data.get('aiEnabled') else '❌ Disabled'}\n**AI Non-Prefix:** {'✅ Enabled' if data.get('nonPrefixEnabled') else '❌ Disabled'}\n**AI Manager Role:** {role.mention if role else 'Not set (staff permissions)'}"
    await ctx.send(embed=style_embed('AI Manager Status', description=desc, kind='info'))


@bot.hybrid_command(name='ailist', help='Bot owner: list servers with premium AI enabled.')
async def ai_list(ctx: commands.Context):
    if not _is_owner(ctx.author.id):
        await ctx.send(embed=style_embed('Unauthorized', description='Only bot owners can list premium AI servers.', kind='error'))
        return
    rows = await __import__('bot.ai_manager_database', fromlist=['list_enabled_guilds']).list_enabled_guilds()
    if not rows:
        await ctx.send(embed=style_embed('AI Servers', description='No servers currently have premium AI enabled.', kind='info'))
        return
    lines = []
    for row in rows:
        g = bot.get_guild(int(row.get('guildId', 0)))
        if g:
            lines.append(f"• **{g.name}** — `{g.id}` — non-prefix {'✅' if row.get('nonPrefixEnabled') else '❌'}")
    await ctx.send(embed=style_embed('Premium AI Servers', description='\n'.join(lines) or 'No matching guilds are currently cached.', kind='info'))


@bot.hybrid_command(name='aihelp', help='Show the complete premium AI Manager guide for this server.')
async def ai_help(ctx: commands.Context):
    if not await _ai_allowed(ctx):
        await ctx.send(embed=_disabled_message())
        return
    data = await get_guild(ctx.guild.id)
    role_text = f"<@&{data['managerRoleId']}>" if data.get('managerRoleId') else 'Not set (staff permissions)'
    embed = style_embed('AI Manager Help', description='Use AI as a private, server-specific assistant. It reads only this server’s imported prices, rules, and services.', kind='info')
    embed.add_field(name='🤖 Ask AI', value='`?ai <question>` or `/ai <question>`\nWith premium non-prefix enabled: `ai <question>`', inline=False)
    embed.add_field(name='📥 Import Data', value='`?aiimportprice [title]` / `/aiimportprice [title]` — start a bulk price import. Paste the full text across multiple messages, then type `done`.\n`?aiimportrules [title]` / `/aiimportrules [title]` — start a bulk rules/policy import. Paste the full text across multiple messages, then type `done`.\nDuring an import: send more text, `done` = save, `cancel` = discard.\nWith AI non-prefix enabled, the same commands can be typed without `?`.', inline=False)
    embed.add_field(name='💰 Prices', value='`?aiprice set <service> <price>` — add/update a price.\n`?aiprice list` — view prices.\n`?aiprice remove <service>` — remove one.\n`?aiprice clear` — delete all prices.', inline=False)
    embed.add_field(name='📜 Rules', value='`?airule add <rule>` — add a rule.\n`?airule list` — view rules.\n`?airule remove <number>` — remove one.\n`?airule clear` — delete all rules.', inline=False)
    embed.add_field(name='🧰 Services', value='`?aiservice add <service>` — add a service.\n`?aiservice list` — view services.\n`?aiservice remove <service>` — remove one.\n`?aiservice clear` — delete all services.', inline=False)
    embed.add_field(name='🛠️ Server Actions', value='`?ai create a role called Trial Staff with timeout members` — AI prepares a safe action preview.\n`?ai create a channel called staff-chat` — AI can prepare a channel action.\n`Confirm` is required before changes are made.', inline=False)
    embed.add_field(name='⚙️ Configuration', value=f'`?aiconfig` — show AI status.\n`?aiconfig manager @role` — set the AI Manager role.\n**AI Manager Role:** {role_text}', inline=False)
    embed.add_field(name='🧹 Clear Data', value='`?aiclear` — clear all AI Manager data for this server.', inline=False)
    embed.set_footer(text='All AI Manager data is isolated per server.')
    await ctx.send(embed=embed)


@bot.hybrid_command(name='ai', help='Ask the server-specific AI Manager a question or request a safe server action.')
@app_commands.describe(question='Your question/request for the AI Manager.')
async def ai_cmd(ctx: commands.Context, *, question: str):
    if not await _ai_allowed(ctx):
        await ctx.send(embed=_disabled_message())
        return
    data = await get_guild(ctx.guild.id)
    result, error = await _gemini(question, ctx, data)
    if error:
        _error_messages = {
            'no_key':       '❌ `GEMINI_API_KEY` is not set. The bot owner needs to add it to the environment variables.',
            'disabled':     '❌ The AI Manager is disabled globally (`AI_MANAGER_ENABLED=false`).',
            'bad_key':      '❌ The Gemini API key was rejected (401/403). It may be invalid or expired — the bot owner needs to update `GEMINI_API_KEY`.',
            'rate_limit':   '⏳ Gemini is rate limiting the bot right now. Try again in a few seconds.',
            'timeout':      '⏳ The AI took too long to respond. Try again.',
            'network':      '❌ Could not reach the Gemini API. Check the bot\'s internet connection.',
            'bad_response': '❌ Gemini returned an unexpected response format. Try again or contact the bot owner.',
            'bad_request':  '❌ The request was rejected by Gemini (400). This may be a prompt or model issue — contact the bot owner.',
        }
        msg = _error_messages.get(error) or f'⚠️ AI is temporarily unavailable (`{error}`). Check the bot logs.'
        await ctx.send(embed=style_embed('AI Manager', description=msg, kind='warn'))
        return
    if result.get('mode') != 'action' or not result.get('action') or result.get('action', {}).get('type') in (None, 'null'):
        answer = str(result.get('answer') or 'I could not find that in this server’s configured information.')
        await ctx.send(embed=style_embed('AI Manager', description=answer, kind='info'))
        return
    action = result['action']
    if action.get('type') == 'create_role' and 'name' in action:
        perms = [p for p in action.get('permissions', []) if isinstance(p, str) and p not in {'administrator', 'manage_guild'}]
        summary = f"**Action:** Create role\n**Name:** `{action['name']}`\n**Permissions:** {', '.join(perms) if perms else 'None'}"
    elif action.get('type') == 'create_channel' and 'name' in action:
        summary = f"**Action:** Create text channel\n**Name:** `#{action['name']}`"
    elif action.get('type') == 'add_role':
        summary = f"**Action:** Add role `{action.get('role_name', '')}` to <@{action.get('member_id', '')}>"
    else:
        await ctx.send(embed=style_embed('AI Manager', description='I understood the request, but that action is not supported yet.', kind='warn'))
        return
    action_id = hash((ctx.message.id if ctx.message else 0, ctx.author.id, question))
    _PENDING_ACTIONS[action_id] = action
    await ctx.send(embed=style_embed('AI Action Preview', description=summary + '\n\nNothing has been changed yet. Confirm to execute.', kind='warn'), view=AIActionView(ctx.author.id, action_id))


@bot.hybrid_command(name='aitest', help='Bot owner: test the Gemini API connection and show a live diagnostic.')
async def ai_test(ctx: commands.Context):
    if not _is_owner(ctx.author.id):
        await ctx.send(embed=style_embed('Unauthorized', description='Only bot owners can run the AI diagnostic.', kind='error'))
        return

    lines = []
    lines.append(f"**`GEMINI_API_KEY`:** {'✅ Set (`' + GEMINI_API_KEY[:6] + '...`)' if GEMINI_API_KEY else '❌ Not set'}")
    lines.append(f"**`AI_MANAGER_ENABLED`:** {'✅ True' if AI_ENABLED else '❌ False'}")
    lines.append(f"**Model:** `{GEMINI_MODEL}`")

    if not GEMINI_API_KEY:
        lines.append('\n❌ Cannot reach Gemini — API key is missing.')
        await ctx.send(embed=style_embed('AI Diagnostic', description='\n'.join(lines), kind='warn'))
        return
    if not AI_ENABLED:
        lines.append('\n❌ AI is disabled via `AI_MANAGER_ENABLED`.')
        await ctx.send(embed=style_embed('AI Diagnostic', description='\n'.join(lines), kind='warn'))
        return

    lines.append('\n⏳ Pinging Gemini API...')
    msg = await ctx.send(embed=style_embed('AI Diagnostic', description='\n'.join(lines), kind='info'))

    url = f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent'
    payload = {
        'contents': [{'parts': [{'text': 'Reply with {"ok": true}'}]}],
        'generationConfig': {'temperature': 0, 'responseMimeType': 'application/json'},
    }
    headers = {'Content-Type': 'application/json', 'x-goog-api-key': GEMINI_API_KEY}
    try:
        import time as _time
        t0 = _time.monotonic()
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.post(url, json=payload, headers=headers) as response:
                elapsed = round((_time.monotonic() - t0) * 1000)
                body = await response.text()
                if response.status == 200:
                    lines[-1] = f'✅ Gemini responded OK in **{elapsed}ms** (HTTP 200).'
                    kind = 'success'
                elif response.status in (401, 403):
                    lines[-1] = f'❌ Auth failed (HTTP {response.status}) — API key is invalid or expired.\n```\n{body[:300]}\n```'
                    kind = 'error'
                elif response.status == 429:
                    lines[-1] = f'⏳ Rate limited (HTTP 429). Try again in a moment.'
                    kind = 'warn'
                else:
                    lines[-1] = f'❌ HTTP {response.status}:\n```\n{body[:300]}\n```'
                    kind = 'error'
    except aiohttp.ServerTimeoutError:
        lines[-1] = '❌ Request timed out (>15s). Gemini may be unreachable.'
        kind = 'error'
    except Exception as exc:
        lines[-1] = f'❌ Exception: `{exc}`'
        kind = 'error'

    await msg.edit(embed=style_embed('AI Diagnostic', description='\n'.join(lines), kind=kind))


@bot.hybrid_command(name='aiimportprice', help='Import a large pricing document by sending multiple messages, then type done.')
@app_commands.describe(title='Optional title for the imported pricing document.')
async def ai_import_price(ctx: commands.Context, title: str = ''):
    if not await _management_allowed(ctx):
        await ctx.send(embed=_disabled_message())
        return
    session = _start_import_session(ctx.guild.id, ctx.author.id, 'price', title)
    await ctx.send(embed=style_embed(
        'AI Price Import Started',
        description=(
            f"📥 **Title:** `{session['title']}`\n\n"
            'Send the complete pricing text in the next message(s). Long documents can be split across many messages.\n\n'
            'When finished, type **`done`**.\n'
            'Type **`cancel`** to discard everything.\n\n'
            'The full text is stored only for this server and used by its AI Manager.'
        ),
        kind='info',
    ))


@bot.hybrid_command(name='aiimportrules', help='Import a large rules/policy document by sending multiple messages, then type done.')
@app_commands.describe(title='Optional title for the imported rules document.')
async def ai_import_rules(ctx: commands.Context, title: str = ''):
    if not await _management_allowed(ctx):
        await ctx.send(embed=_disabled_message())
        return
    session = _start_import_session(ctx.guild.id, ctx.author.id, 'rules', title)
    await ctx.send(embed=style_embed(
        'AI Rules Import Started',
        description=(
            f"📥 **Title:** `{session['title']}`\n\n"
            'Send the complete rules/policies in the next message(s). Long documents can be split across many messages.\n\n'
            'When finished, type **`done`**.\n'
            'Type **`cancel`** to discard everything.\n\n'
            'The full text is stored only for this server and used by its AI Manager.'
        ),
        kind='info',
    ))


@bot.hybrid_command(name='aiprice', help='Manage per-server AI prices: set, list, remove, clear.')
@app_commands.describe(action='set, list, remove, or clear', service='Service name', price='Price text')
async def ai_price(ctx: commands.Context, action: str, service: str = '', *, price: str = ''):
    if not await _management_allowed(ctx):
        await ctx.send(embed=_disabled_message())
        return
    action = action.lower().strip()
    if action == 'set':
        if not service or not price:
            await ctx.send('Usage: `?aiprice set <service> <price>`')
            return
        await add_price(ctx.guild.id, service, price)
        await ctx.send(embed=style_embed('AI Price Updated', description=f'✅ **{service}** → `{price}`', kind='success'))
    elif action == 'list':
        data = await get_guild(ctx.guild.id)
        rows = data.get('prices') or []
        desc = '\n'.join(f"• **{r.get('service')}** — `{r.get('price')}`" for r in rows) or 'No prices configured.'
        await ctx.send(embed=style_embed('AI Prices', description=desc, kind='info'))
    elif action == 'remove':
        ok = await remove_price(ctx.guild.id, service)
        await ctx.send(embed=style_embed('AI Price Removed', description='✅ Removed.' if ok else '❗ Price not found.', kind='success' if ok else 'warn'))
    elif action == 'clear':
        await clear_category(ctx.guild.id, 'prices')
        await clear_price_sheets(ctx.guild.id)
        await ctx.send(embed=style_embed('AI Prices Cleared', description='✅ All structured prices and imported pricing sheets for this server were cleared.', kind='success'))
    else:
        await ctx.send('Usage: `?aiprice set <service> <price>` · `list` · `remove <service>` · `clear`')


@bot.hybrid_command(name='airule', help='Manage per-server AI rules: add, list, remove, clear.')
@app_commands.describe(action='add, list, remove, or clear', value='Rule text or rule number')
async def ai_rule(ctx: commands.Context, action: str, *, value: str = ''):
    if not await _management_allowed(ctx):
        await ctx.send(embed=_disabled_message())
        return
    action = action.lower().strip()
    if action == 'add':
        if not value.strip():
            await ctx.send('Usage: `?airule add <rule>`')
            return
        await add_rule(ctx.guild.id, value)
        await ctx.send(embed=style_embed('AI Rule Added', description='✅ Rule saved for this server.', kind='success'))
    elif action == 'list':
        data = await get_guild(ctx.guild.id)
        rows = data.get('rules') or []
        shown = '\n'.join(f"**{i}.** {r.replace('RULE_SHEET::', '📄 ').replace('PRICE_SHEET::', '💰 ')}" for i, r in enumerate(rows, 1)) or 'No AI rules/imports configured.'
        await ctx.send(embed=style_embed('AI Rules', description=shown[:3900], kind='info'))
    elif action == 'remove':
        try:
            idx = int(value)
        except ValueError:
            await ctx.send('Usage: `?airule remove <number>`')
            return
        ok = await remove_rule(ctx.guild.id, idx)
        await ctx.send(embed=style_embed('AI Rule Removed', description='✅ Removed.' if ok else '❗ Rule number not found.', kind='success' if ok else 'warn'))
    elif action == 'clear':
        await clear_category(ctx.guild.id, 'rules')
        await clear_rule_sheets(ctx.guild.id)
        await ctx.send(embed=style_embed('AI Rules Cleared', description='✅ All structured rules and imported rules/policy sheets for this server were cleared.', kind='success'))
    else:
        await ctx.send('Usage: `?airule add <rule>` · `list` · `remove <number>` · `clear`')


@bot.hybrid_command(name='aiservice', help='Manage per-server AI services: add, list, remove, clear.')
@app_commands.describe(action='add, list, remove, or clear', service='Service name')
async def ai_service(ctx: commands.Context, action: str, *, service: str = ''):
    if not await _management_allowed(ctx):
        await ctx.send(embed=_disabled_message())
        return
    action = action.lower().strip()
    if action == 'add':
        if not service:
            await ctx.send('Usage: `?aiservice add <service>`')
            return
        await add_service(ctx.guild.id, service)
        await ctx.send(embed=style_embed('AI Service Added', description=f'✅ Added **{service}**.', kind='success'))
    elif action == 'list':
        data = await get_guild(ctx.guild.id)
        desc = '\n'.join(f'• {s}' for s in (data.get('services') or [])) or 'No services configured.'
        await ctx.send(embed=style_embed('AI Services', description=desc, kind='info'))
    elif action == 'remove':
        ok = await remove_service(ctx.guild.id, service)
        await ctx.send(embed=style_embed('AI Service Removed', description='✅ Removed.' if ok else '❗ Service not found.', kind='success' if ok else 'warn'))
    elif action == 'clear':
        await clear_category(ctx.guild.id, 'services')
        await ctx.send(embed=style_embed('AI Services Cleared', description='✅ All AI services for this server were cleared.', kind='success'))
    else:
        await ctx.send('Usage: `?aiservice add <service>` · `list` · `remove <service>` · `clear`')


@bot.hybrid_command(name='aiconfig', help='Show AI configuration or set the AI Manager role.')
@app_commands.describe(manager='Optional AI Manager role to assign')
async def ai_config(ctx: commands.Context, manager: discord.Role | None = None):
    if not await _management_allowed(ctx):
        await ctx.send(embed=_disabled_message())
        return
    data = await get_guild(ctx.guild.id)
    if manager is not None:
        if manager.is_default() or manager.is_bot_managed():
            await ctx.send(embed=style_embed('Invalid Role', description='Choose a normal server role.', kind='error'))
            return
        await set_manager_role(ctx.guild.id, manager.id)
        data = await get_guild(ctx.guild.id)
    role = ctx.guild.get_role(int(data['managerRoleId'])) if data.get('managerRoleId') else None
    desc = f"**AI Enabled:** {'✅' if data.get('aiEnabled') else '❌'}\n**Non-Prefix:** {'✅' if data.get('nonPrefixEnabled') else '❌'}\n**AI Manager Role:** {role.mention if role else 'Not set (staff permissions)'}\n**Structured Prices:** `{len(data.get('prices') or [])}`\n**Price Sheets:** `{len(data.get('priceSheets') or [])}`\n**Rules:** `{len(data.get('rules') or [])}`\n**Rule Sheets:** `{len(data.get('ruleSheets') or [])}`\n**Services:** `{len(data.get('services') or [])}`"
    await ctx.send(embed=style_embed('AI Manager Configuration', description=desc, kind='info'))


@bot.hybrid_command(name='aiclear', help='Clear all AI Manager data for this server.')
async def ai_clear(ctx: commands.Context):
    if not await _management_allowed(ctx):
        await ctx.send(embed=_disabled_message())
        return
    await clear_all(ctx.guild.id)
    await ctx.send(embed=style_embed('AI Manager Cleared', description='✅ All AI Manager prices, rules, services, and the Manager role setting were cleared for this server.', kind='success'))


async def init():
    await init_ai_db()
