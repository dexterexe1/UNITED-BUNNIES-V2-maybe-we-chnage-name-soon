
"""Premium per-server AI Manager for United Bunnies.

Features:
- Bot-owner-controlled premium enable/disable for any guild the bot is in.
- Independent per-server AI knowledge: prices, rules, services, and bulk imports.
- Hybrid commands (prefix + slash).
- Optional per-server no-prefix AI mode.
- Gemini used for server-local Q&A and safe server-action planning.
- Server-changing AI actions require an explicit confirmation button.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import re
from typing import Any, Dict, Optional

import aiohttp
import discord
from discord.ext import commands

from bot.config import bot, style_embed, BOT_OWNER_IDS, is_staff
from bot.ai_manager_database import (
    init_ai_manager_db,
    get_server_config,
    set_ai_enabled,
    set_nonprefix_enabled,
    set_manager_role,
    list_enabled_servers,
    upsert_price,
    list_prices,
    remove_price,
    clear_prices,
    add_rule,
    list_rules,
    remove_rule,
    clear_rules,
    add_service,
    list_services,
    remove_service,
    clear_services,
    add_import,
    clear_imports,
    clear_all,
    get_ai_context,
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_AI_MANAGER_MODEL", os.getenv("GEMINI_PAYMENT_MODEL", "gemini-2.5-flash-lite")).strip()
AI_ENABLED = os.getenv("AI_MANAGER_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}

# In-memory import sessions. The actual imported data is persisted to MongoDB.
_IMPORT_SESSIONS: Dict[tuple[int, int], Dict[str, Any]] = {}
_MAX_IMPORT_MESSAGES = 30
_MAX_IMPORT_CHARS = 75000


def _owner(user: discord.abc.User) -> bool:
    return user.id in BOT_OWNER_IDS


async def _ensure_db() -> bool:
    return await init_ai_manager_db()


async def _ai_allowed(guild: Optional[discord.Guild]) -> bool:
    if guild is None:
        return False
    cfg = await get_server_config(guild.id)
    return bool(cfg.get("ai_enabled"))


async def _has_ai_access(ctx: commands.Context) -> bool:
    if ctx.guild is None:
        return False
    cfg = await get_server_config(ctx.guild.id)
    if not cfg.get("ai_enabled"):
        await ctx.send(embed=style_embed(
            "AI Manager Locked",
            description="🔒 Premium AI Manager is not enabled for this server. A bot owner must activate it first.",
            kind="error",
        ), delete_after=10)
        return False

    if _owner(ctx.author):
        return True

    if not isinstance(ctx.author, discord.Member):
        return False

    manager_role_id = cfg.get("manager_role_id")
    if manager_role_id:
        role = ctx.guild.get_role(int(manager_role_id))
        if role and role in ctx.author.roles:
            return True

    if is_staff(ctx.author, need="mod"):
        return True

    await ctx.send(embed=style_embed(
        "AI Access Denied",
        description="🔒 You do not have AI Manager access on this server.",
        kind="error",
    ), delete_after=10)
    return False


async def _find_guild(query: str) -> Optional[discord.Guild]:
    query = (query or "").strip()
    if not query:
        return None
    if query.isdigit():
        gid = int(query)
        return bot.get_guild(gid)
    lowered = query.casefold()
    exact = [g for g in bot.guilds if g.name.casefold() == lowered]
    if exact:
        return exact[0]
    partial = [g for g in bot.guilds if lowered in g.name.casefold()]
    return partial[0] if partial else None


def _guild_list_text() -> str:
    guilds = sorted(bot.guilds, key=lambda g: g.name.casefold())
    if not guilds:
        return "No guilds are available."
    lines = []
    for g in guilds[:30]:
        cfg = asyncio.run(get_server_config(g.id)) if False else None
        lines.append(f"• **{g.name}** — `{g.id}`")
    suffix = "" if len(guilds) <= 30 else f"\n…and {len(guilds) - 30} more."
    return "\n".join(lines) + suffix


class GuildSelectView(discord.ui.View):
    def __init__(self, mode: str, author_id: int):
        super().__init__(timeout=120)
        self.mode = mode
        self.author_id = author_id
        self.page = 0
        self._rebuild()

    def _rebuild(self):
        for child in list(self.children):
            self.remove_item(child)
        guilds = sorted(bot.guilds, key=lambda g: g.name.casefold())
        start = self.page * 25
        page_guilds = guilds[start:start + 25]
        select = discord.ui.Select(
            placeholder=f"Select a server ({self.page + 1}/{max(1, (len(guilds) + 24) // 25)})",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=g.name[:100],
                    value=str(g.id),
                    description=("Enabled" if self.mode in {"disable_ai", "disable_nonprefix"} else "Choose this server")[:100],
                )
                for g in page_guilds
            ],
        )
        select.callback = self._select_callback
        self.add_item(select)

        if len(guilds) > 25:
            prev_btn = discord.ui.Button(label="Previous", style=discord.ButtonStyle.secondary, disabled=self.page == 0)
            next_btn = discord.ui.Button(label="Next", style=discord.ButtonStyle.secondary, disabled=start + 25 >= len(guilds))
            prev_btn.callback = self._prev
            next_btn.callback = self._next
            self.add_item(prev_btn)
            self.add_item(next_btn)

        cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger)
        cancel.callback = self._cancel
        self.add_item(cancel)

    async def _select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Only the bot owner who opened this selector can use it.", ephemeral=True)
            return
        gid = int(interaction.data["values"][0])
        guild = bot.get_guild(gid)
        if not guild:
            await interaction.response.edit_message(content="❌ That server is no longer available.", view=None)
            self.stop()
            return

        if self.mode == "enable_ai":
            ok = await set_ai_enabled(guild.id, True)
            text = f"✅ Premium AI Manager is now **enabled** for **{guild.name}**." if ok else "❌ Could not save the AI setting."
        elif self.mode == "disable_ai":
            ok = await set_ai_enabled(guild.id, False)
            text = f"🔒 Premium AI Manager is now **disabled** for **{guild.name}**." if ok else "❌ Could not save the AI setting."
        elif self.mode == "enable_nonprefix":
            ok = await set_nonprefix_enabled(guild.id, True)
            text = f"✅ AI **non-prefix mode** is now enabled for **{guild.name}**." if ok else "❌ Could not save the setting."
        else:
            ok = await set_nonprefix_enabled(guild.id, False)
            text = f"🔒 AI **non-prefix mode** is now disabled for **{guild.name}**." if ok else "❌ Could not save the setting."
        await interaction.response.edit_message(
            content=text + f"\n\nServer ID: `{guild.id}`",
            view=None,
        )
        self.stop()

    async def _prev(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Not your selector.", ephemeral=True)
            return
        self.page = max(0, self.page - 1)
        self._rebuild()
        await interaction.response.edit_message(view=self)

    async def _next(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Not your selector.", ephemeral=True)
            return
        self.page += 1
        self._rebuild()
        await interaction.response.edit_message(view=self)

    async def _cancel(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Not your selector.", ephemeral=True)
            return
        await interaction.response.edit_message(content="❌ Cancelled.", view=None)
        self.stop()


async def _owner_target_prompt(ctx: commands.Context, mode: str):
    view = GuildSelectView(mode, ctx.author.id)
    await ctx.send(embed=style_embed(
        "Premium AI Server Selector",
        description=f"Select one of the **{len(bot.guilds)}** servers currently using this bot.\n"
                    "You do **not** need to be a member of the selected server.",
        kind="mod",
    ), view=view)


class ConfirmView(discord.ui.View):
    def __init__(self, author_id: int, action_coro):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.action_coro = action_coro

    async def _check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Only the person who requested this action can confirm it.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction):
            return
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="⏳ **Executing...**", view=self)
        try:
            result = await self.action_coro()
            await interaction.edit_original_response(content=result, view=None)
        except Exception as exc:
            await interaction.edit_original_response(content=f"❌ Action failed: `{exc}`", view=None)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction):
            return
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="❌ **Cancelled.** No changes were made.", view=self)
        self.stop()


def _allowed_role_permissions() -> dict[str, str]:
    return {
        "view_channel": "View Channels",
        "send_messages": "Send Messages",
        "read_message_history": "Read Message History",
        "embed_links": "Embed Links",
        "attach_files": "Attach Files",
        "manage_messages": "Manage Messages",
        "moderate_members": "Timeout Members",
        "kick_members": "Kick Members",
        "ban_members": "Ban Members",
    }


def _parse_hex_color(value: str | None) -> Optional[discord.Colour]:
    if not value:
        return None
    value = value.strip().lstrip("#")
    if re.fullmatch(r"[0-9a-fA-F]{6}", value):
        return discord.Colour(int(value, 16))
    return None


async def _execute_action(guild: discord.Guild, plan: Dict[str, Any]) -> str:
    action = str(plan.get("action") or "").strip().lower()
    me = guild.me or guild.get_member(bot.user.id)
    if me is None:
        return "❌ I could not resolve my own member record."
    bot_top = me.top_role

    if action == "create_role":
        if not me.guild_permissions.manage_roles:
            return "❌ I need **Manage Roles** to do that."
        name = str(plan.get("name") or "").strip()
        if not name:
            return "❌ No role name was provided."
        if discord.utils.get(guild.roles, name=name):
            return f"❌ A role named **{name}** already exists."
        perms = plan.get("permissions") or []
        allowed = _allowed_role_permissions()
        kwargs = {k: False for k in allowed}
        for p in perms:
            key = str(p).strip().lower()
            if key in kwargs:
                kwargs[key] = True
        role = await guild.create_role(name=name, reason=f"AI Manager requested by {plan.get('requested_by')}")
        try:
            await role.edit(permissions=discord.Permissions(**kwargs))
        except Exception:
            await role.delete(reason="AI role creation rollback")
            raise
        color = _parse_hex_color(plan.get("color"))
        if color:
            await role.edit(colour=color)
        return f"✅ Created role **{role.name}** with the approved safe permissions."

    if action == "create_category":
        if not me.guild_permissions.manage_channels:
            return "❌ I need **Manage Channels** to do that."
        name = str(plan.get("name") or "").strip()
        if not name:
            return "❌ No category name was provided."
        existing = discord.utils.get(guild.categories, name=name)
        if existing:
            return f"❌ Category **{name}** already exists."
        category = await guild.create_category(name=name, reason=f"AI Manager requested by {plan.get('requested_by')}")
        return f"✅ Created category **{category.name}**."

    if action == "create_text_channel":
        if not me.guild_permissions.manage_channels:
            return "❌ I need **Manage Channels** to do that."
        name = str(plan.get("name") or "").strip().lower().replace(" ", "-")
        if not name:
            return "❌ No channel name was provided."
        category_name = str(plan.get("category") or "").strip()
        category = discord.utils.get(guild.categories, name=category_name) if category_name else None
        channel = await guild.create_text_channel(
            name=name,
            category=category,
            reason=f"AI Manager requested by {plan.get('requested_by')}",
        )
        return f"✅ Created {channel.mention}."

    if action == "rename_role":
        if not me.guild_permissions.manage_roles:
            return "❌ I need **Manage Roles** to do that."
        role_name = str(plan.get("role") or "").strip()
        new_name = str(plan.get("new_name") or "").strip()
        role = discord.utils.find(lambda r: r.name.casefold() == role_name.casefold(), guild.roles)
        if not role or role.is_default() or role.managed:
            return "❌ I could not find a normal editable role with that name."
        if role >= bot_top:
            return "❌ I cannot edit a role at or above my highest role."
        if not new_name:
            return "❌ No new role name was provided."
        await role.edit(name=new_name, reason=f"AI Manager requested by {plan.get('requested_by')}")
        return f"✅ Renamed the role to **{new_name}**."

    if action in {"assign_role", "remove_role"}:
        if not me.guild_permissions.manage_roles:
            return "❌ I need **Manage Roles** to do that."
        target_id = int(plan.get("user_id") or 0)
        role_name = str(plan.get("role") or "").strip()
        member = guild.get_member(target_id)
        role = discord.utils.find(lambda r: r.name.casefold() == role_name.casefold(), guild.roles)
        if not member or not role or role.is_default() or role.managed:
            return "❌ I could not resolve the member or editable role."
        if role >= bot_top:
            return "❌ I cannot manage a role at or above my highest role."
        if action == "assign_role":
            await member.add_roles(role, reason=f"AI Manager requested by {plan.get('requested_by')}")
            return f"✅ Added **{role.name}** to **{member.display_name}**."
        await member.remove_roles(role, reason=f"AI Manager requested by {plan.get('requested_by')}")
        return f"✅ Removed **{role.name}** from **{member.display_name}**."

    return "❌ This AI action is not supported."


async def _gemini_request(prompt: str) -> Optional[str]:
    if not GEMINI_API_KEY or not AI_ENABLED:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1},
    }
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload) as response:
                body = await response.text()
                if response.status != 200:
                    print(f"⚠️ AI Manager HTTP {response.status}: {body[:300]}")
                    return None
                data = json.loads(body)
        chunks = []
        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                if isinstance(part.get("text"), str):
                    chunks.append(part["text"])
        return "\n".join(chunks).strip() or None
    except Exception as exc:
        print(f"⚠️ AI Manager request failed: {exc}")
        return None


async def _plan_action(guild: discord.Guild, question: str) -> Optional[Dict[str, Any]]:
    mentioned_ids = [int(x) for x in re.findall(r"<@!?(\d+)>", question)]
    prompt = f"""You are a Discord server-management action planner.
Guild: {guild.name}

User request:
{question}

Mentioned user IDs in request: {mentioned_ids}

Return JSON only. Allowed actions:
- none
- create_role: {{name, permissions[], color?}}
- create_category: {{name}}
- create_text_channel: {{name, category?}}
- rename_role: {{role, new_name}}
- assign_role: {{user_id, role}}
- remove_role: {{user_id, role}}

Safe role permissions allowed ONLY:
view_channel, send_messages, read_message_history, embed_links, attach_files,
manage_messages, moderate_members, kick_members, ban_members.

Rules:
- Never output administrator, manage_guild, manage_roles, manage_channels, mention_everyone,
  manage_webhooks, manage_permissions, or any other privileged permission.
- Only return an action when the user clearly asks to change the Discord server.
- For assign/remove_role, use a mentioned user ID when one is present.
- For ordinary questions, return action=none.

Return:
{{"action":"none"}}
or the matching action object."""
    raw = await _gemini_request(prompt)
    if not raw:
        return None
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.I)
    try:
        plan = json.loads(raw)
    except Exception:
        return None
    if not isinstance(plan, dict):
        return None
    return plan


def _looks_like_action_request(question: str) -> bool:
    q = question.casefold()
    starters = (
        "create role", "make role", "create a role", "make a role",
        "create channel", "make channel", "create a channel", "make a channel",
        "create category", "make category", "rename role", "rename the role",
        "give role", "add role", "remove role", "take role",
    )
    return any(q.lstrip().startswith(x) for x in starters)


async def _answer_ai(ctx: commands.Context, question: str):
    if not question.strip():
        await ctx.send(embed=style_embed(
            "AI Manager",
            description="Use `?ai <question>` or `/ai <question>`. Try `?aihelp` for examples.",
            kind="info",
        ))
        return

    action_plan = await _plan_action(ctx.guild, question) if _looks_like_action_request(question) else None
    if action_plan and str(action_plan.get("action", "none")) != "none":
        action = str(action_plan.get("action"))
        preview = json.dumps(action_plan, indent=2)
        action_plan["requested_by"] = ctx.author.id
        async def execute():
            return await _execute_action(ctx.guild, action_plan)
        view = ConfirmView(ctx.author.id, execute)
        await ctx.send(embed=style_embed(
            "AI ACTION PREVIEW",
            description=(
                "AI wants to make a server change. **Nothing has changed yet.**\n\n"
                f"```json\n{preview[:3500]}\n```\n"
                "Review the action and confirm it below."
            ),
            kind="warn",
        ), view=view)
        return

    context = await get_ai_context(ctx.guild.id)
    prompt = f"""You are the private AI manager for one Discord server.

Use ONLY the server data below for prices, rules, services and imported business information.
Never invent a price, rule, refund policy, or service. If the information is not configured,
say that clearly. You may perform normal arithmetic using configured prices.
Keep answers concise and professional for moderators/staff.

SERVER DATA:
{context}

STAFF QUESTION:
{question}
"""
    answer = await _gemini_request(prompt)
    if not answer:
        reason = "GEMINI_API_KEY is missing" if not GEMINI_API_KEY else "Gemini is unavailable right now"
        await ctx.send(embed=style_embed(
            "AI Manager Unavailable",
            description=f"⚠️ {reason}. The normal AI Manager configuration is still safe.",
            kind="error",
        ), delete_after=12)
        return
    if len(answer) > 3900:
        answer = answer[:3890] + "…"
    await ctx.send(embed=style_embed(
        "AI Manager",
        description=answer,
        kind="info",
    ))


# ==========================================
# BOT OWNER / PREMIUM CONTROL
# ==========================================

@bot.hybrid_command(name="provideai", help="Enable premium AI Manager for one of the bot's servers (bot owner only)")
async def provide_ai(ctx: commands.Context, server: Optional[str] = None):
    if not _owner(ctx.author):
        raise commands.CheckFailure("🔒 Bot owner only.")
    if not await _ensure_db():
        await ctx.send(embed=style_embed("AI Manager Error", description="❌ MongoDB is unavailable.", kind="error"))
        return
    if not server:
        await _owner_target_prompt(ctx, "enable_ai")
        return
    guild = await _find_guild(server)
    if not guild:
        await ctx.send(embed=style_embed("Server Not Found", description="❌ I could not find that server in the bot's guild list.", kind="error"))
        return
    await set_ai_enabled(guild.id, True)
    await ctx.send(embed=style_embed(
        "Premium AI Enabled",
        description=f"✅ **{guild.name}** now has Premium AI Manager access.\nServer ID: `{guild.id}`",
        kind="success",
    ))


@bot.hybrid_command(name="disableai", help="Disable premium AI Manager for a bot server (bot owner only)")
async def disable_ai(ctx: commands.Context, server: Optional[str] = None):
    if not _owner(ctx.author):
        raise commands.CheckFailure("🔒 Bot owner only.")
    if not server:
        await _owner_target_prompt(ctx, "disable_ai")
        return
    guild = await _find_guild(server)
    if not guild:
        await ctx.send(embed=style_embed("Server Not Found", description="❌ Server not found.", kind="error"))
        return
    await set_ai_enabled(guild.id, False)
    await ctx.send(embed=style_embed("Premium AI Disabled", description=f"🔒 AI Manager disabled for **{guild.name}**.", kind="warn"))


@bot.hybrid_command(name="providenonprefix", help="Enable premium AI no-prefix commands for a bot server (bot owner only)")
async def provide_nonprefix(ctx: commands.Context, server: Optional[str] = None):
    if not _owner(ctx.author):
        raise commands.CheckFailure("🔒 Bot owner only.")
    if not server:
        await _owner_target_prompt(ctx, "enable_nonprefix")
        return
    guild = await _find_guild(server)
    if not guild:
        await ctx.send(embed=style_embed("Server Not Found", description="❌ Server not found.", kind="error"))
        return
    await set_nonprefix_enabled(guild.id, True)
    await ctx.send(embed=style_embed(
        "AI Non-Prefix Enabled",
        description=f"✅ AI no-prefix commands are enabled for **{guild.name}**.\n\n"
                    "Normal no-prefix permissions still apply to non-owner staff.",
        kind="success",
    ))


@bot.hybrid_command(name="disablenonprefix", help="Disable premium AI no-prefix commands (bot owner only)")
async def disable_nonprefix(ctx: commands.Context, server: Optional[str] = None):
    if not _owner(ctx.author):
        raise commands.CheckFailure("🔒 Bot owner only.")
    if not server:
        await _owner_target_prompt(ctx, "disable_nonprefix")
        return
    guild = await _find_guild(server)
    if not guild:
        await ctx.send(embed=style_embed("Server Not Found", description="❌ Server not found.", kind="error"))
        return
    await set_nonprefix_enabled(guild.id, False)
    await ctx.send(embed=style_embed("AI Non-Prefix Disabled", description=f"🔒 AI no-prefix disabled for **{guild.name}**.", kind="warn"))


@bot.hybrid_command(name="aistatus", help="Show premium AI status for this server or a bot server (bot owner only)")
async def ai_status(ctx: commands.Context, server: Optional[str] = None):
    if not _owner(ctx.author):
        raise commands.CheckFailure("🔒 Bot owner only.")
    if server:
        guilds = [await _find_guild(server)]
    else:
        guilds = sorted(bot.guilds, key=lambda g: g.name.casefold())[:30]
    lines = []
    for guild in guilds:
        if not guild:
            continue
        cfg = await get_server_config(guild.id)
        lines.append(
            f"• **{guild.name}** — AI: {'✅' if cfg.get('ai_enabled') else '❌'} | "
            f"Non-prefix: {'✅' if cfg.get('nonprefix_enabled') else '❌'} | ID: `{guild.id}`"
        )
    if not lines:
        lines = ["• No matching servers."]
    await ctx.send(embed=style_embed("Premium AI Status", description="\n".join(lines), kind="info"))


@bot.hybrid_command(name="ailist", help="List servers with Premium AI enabled (bot owner only)")
async def ai_list(ctx: commands.Context):
    if not _owner(ctx.author):
        raise commands.CheckFailure("🔒 Bot owner only.")
    enabled = await list_enabled_servers()
    if not enabled:
        text = "No servers currently have Premium AI enabled."
    else:
        text = "\n".join(
            f"• **{bot.get_guild(int(x['guild_id'])).name if bot.get_guild(int(x['guild_id'])) else x['guild_id']}** — `{x['guild_id']}`"
            for x in enabled
        )
    await ctx.send(embed=style_embed("Premium AI Servers", description=text[:3900], kind="info"))


# ==========================================
# SERVER AI MANAGER
# ==========================================

@bot.hybrid_command(name="aihelp", help="Show the Premium AI Manager guide")
async def ai_help(ctx: commands.Context):
    if not await _has_ai_access(ctx):
        return
    text = """**AI**
`?ai <question>` / `/ai <question>`
Ask about this server's configured prices, rules, services, quotes, or summaries.

**BULK IMPORT**
`?aiimportprice <title>`
Starts a multi-message price import. Paste as many chunks as needed, then send `done`.
`?aiimportrules <title>`
Same process for rules.

**PRICES**
`?aiprice set <service> = <price>`
`?aiprice list`
`?aiprice remove <service>`
`?aiprice clear`

**RULES**
`?airule add <rule>`
`?airule list`
`?airule remove <number>`
`?airule clear`

**SERVICES**
`?aiservice add <service> [description]`
`?aiservice list`
`?aiservice remove <service>`
`?aiservice clear`

**CONFIG**
`?aiconfig`
`?aiconfig manager @role`
`?aiconfig resetmanager`

**ALL DATA**
`?aiclear` — clears this server's AI prices, rules, services and imports after confirmation.

**SERVER ACTIONS**
`?ai create a role called Trial Staff with Manage Messages and Timeout Members`
`?ai create a private staff channel called staff-chat`
`?ai give @user Trial Staff`
`?ai remove Trial Staff from @user`

AI can plan server changes, but it never applies them without a confirmation button. Dangerous administrator-level permissions are not allowed.

**IMPORTANT**
• Premium AI is enabled by the bot owner per server.
• This server's data is isolated from every other server.
• AI does not invent configured prices or rules.
• AI no-prefix works only when the bot owner has enabled it for this server, plus normal no-prefix user permissions.
• All management/destructive actions are permission-checked.
"""
    await ctx.send(embed=style_embed("AI Manager Help", description=text, kind="info"))


@bot.hybrid_command(name="ai", help="Ask this server's Premium AI Manager a question")
async def ai_command(ctx: commands.Context, *, question: Optional[str] = None):
    if not await _has_ai_access(ctx):
        return
    if ctx.guild is None:
        return
    await _answer_ai(ctx, question or "")


@bot.hybrid_command(name="aiconfig", help="Show or configure AI Manager access for this server")
async def ai_config(ctx: commands.Context, action: str = "show", role: Optional[discord.Role] = None):
    if not await _has_ai_access(ctx):
        return
    action = action.casefold().strip()
    if action in {"manager", "setmanager"}:
        if not is_staff(ctx.author, need="admin") and not _owner(ctx.author):
            await ctx.send(embed=style_embed("Permission Denied", description="❌ Manage Server/Admin access is required to change the AI Manager role.", kind="error"), delete_after=10)
            return
        if role is None:
            await ctx.send(embed=style_embed("AI Manager Role", description="Usage: `?aiconfig manager @role`", kind="info"), delete_after=10)
            return
        await set_manager_role(ctx.guild.id, role.id)
        await ctx.send(embed=style_embed("AI Manager Role Set", description=f"✅ AI Manager access role is now {role.mention}.", kind="success"))
        return
    if action in {"resetmanager", "clearmanager"}:
        if not is_staff(ctx.author, need="admin") and not _owner(ctx.author):
            await ctx.send(embed=style_embed("Permission Denied", description="❌ Manage Server/Admin access is required.", kind="error"), delete_after=10)
            return
        await set_manager_role(ctx.guild.id, None)
        await ctx.send(embed=style_embed("AI Manager Role Reset", description="✅ AI Manager role restriction cleared. Staff permissions can use AI again.", kind="success"))
        return
    cfg = await get_server_config(ctx.guild.id)
    role_text = f"<@&{cfg['manager_role_id']}>" if cfg.get("manager_role_id") else "Not set (staff permissions)"
    text = (
        f"**Premium AI:** {'✅ Enabled' if cfg.get('ai_enabled') else '❌ Disabled'}\n"
        f"**AI Non-Prefix:** {'✅ Enabled' if cfg.get('nonprefix_enabled') else '❌ Disabled'}\n"
        f"**AI Manager Role:** {role_text}"
    )
    await ctx.send(embed=style_embed("AI Manager Configuration", description=text, kind="info"))


def _split_action(action: str, data: str) -> tuple[str, str]:
    return action.casefold().strip(), data.strip()


@bot.hybrid_command(name="aiprice", help="Manage this server's AI prices")
async def ai_price(ctx: commands.Context, action: str = "list", *, data: str = ""):
    if not await _has_ai_access(ctx):
        return
    action, data = _split_action(action, data)
    if action == "set":
        if not data:
            await ctx.send("Usage: `?aiprice set <service> = <price>`", delete_after=10)
            return
        if "=" in data:
            service, price = [x.strip() for x in data.split("=", 1)]
        else:
            parts = data.rsplit(None, 1)
            if len(parts) != 2:
                await ctx.send("Usage: `?aiprice set <service> = <price>`", delete_after=10)
                return
            service, price = parts
        if not await upsert_price(ctx.guild.id, service, price):
            await ctx.send("❌ Could not save that price.", delete_after=10)
            return
        await ctx.send(embed=style_embed("AI Price Saved", description=f"✅ **{service}** → `{price}`", kind="success"), delete_after=10)
        return
    if action == "remove":
        ok = await remove_price(ctx.guild.id, data)
        await ctx.send(embed=style_embed("AI Price Removed", description=("✅ Removed." if ok else "❌ Price not found."), kind="info"), delete_after=10)
        return
    if action == "clear":
        count = len(await list_prices(ctx.guild.id))
        async def do_clear():
            removed = await clear_prices(ctx.guild.id)
            return f"✅ Cleared **{removed}** AI price entries for **{ctx.guild.name}**."
        view = ConfirmView(ctx.author.id, do_clear)
        await ctx.send(embed=style_embed(
            "Clear AI Prices",
            description=f"⚠️ This will remove **{count}** configured prices from this server only.",
            kind="warn",
        ), view=view)
        return
    prices = await list_prices(ctx.guild.id)
    lines = [f"• **{p['service']}** → `{p['price']}`" for p in prices]
    await ctx.send(embed=style_embed("AI Prices", description="\n".join(lines)[:3900] if lines else "No individual prices configured. Use `?aiimportprice` for bulk data.", kind="info"))


@bot.hybrid_command(name="airule", help="Manage this server's AI rules")
async def ai_rule(ctx: commands.Context, action: str = "list", *, data: str = ""):
    if not await _has_ai_access(ctx):
        return
    action = action.casefold().strip()
    if action == "add":
        if not data:
            await ctx.send("Usage: `?airule add <rule>`", delete_after=10)
            return
        ok = await add_rule(ctx.guild.id, data)
        await ctx.send(embed=style_embed("AI Rule Added", description=("✅ Rule saved." if ok else "❌ Could not save the rule."), kind="success" if ok else "error"), delete_after=10)
        return
    if action == "remove":
        try:
            index = int(data)
        except Exception:
            index = 0
        ok = await remove_rule(ctx.guild.id, index)
        await ctx.send(embed=style_embed("AI Rule Removed", description=("✅ Removed." if ok else "❌ Rule number not found."), kind="info"), delete_after=10)
        return
    if action == "clear":
        count = len(await list_rules(ctx.guild.id))
        async def do_clear():
            removed = await clear_rules(ctx.guild.id)
            return f"✅ Cleared **{removed}** AI rules for **{ctx.guild.name}**."
        await ctx.send(embed=style_embed(
            "Clear AI Rules",
            description=f"⚠️ This removes **{count}** rules from this server only.",
            kind="warn",
        ), view=ConfirmView(ctx.author.id, do_clear))
        return
    rules = await list_rules(ctx.guild.id)
    if not rules:
        await ctx.send(embed=style_embed("AI Rules", description="No individual rules configured. Use `?aiimportrules` for bulk data.", kind="info"))
        return
    lines = [f"**{i}.** [{r.get('category', 'General')}] {r.get('rule')}" for i, r in enumerate(rules, 1)]
    await ctx.send(embed=style_embed("AI Rules", description="\n".join(lines)[:3900], kind="info"))


@bot.hybrid_command(name="aiservice", help="Manage this server's AI service catalog")
async def ai_service(ctx: commands.Context, action: str = "list", *, data: str = ""):
    if not await _has_ai_access(ctx):
        return
    action = action.casefold().strip()
    if action == "add":
        if not data:
            await ctx.send("Usage: `?aiservice add <service> | <description>`", delete_after=10)
            return
        if "|" in data:
            service, desc = [x.strip() for x in data.split("|", 1)]
        else:
            service, desc = data, ""
        ok = await add_service(ctx.guild.id, service, desc)
        await ctx.send(embed=style_embed("AI Service Saved", description=("✅ Service saved." if ok else "❌ Could not save the service."), kind="success" if ok else "error"), delete_after=10)
        return
    if action == "remove":
        ok = await remove_service(ctx.guild.id, data)
        await ctx.send(embed=style_embed("AI Service Removed", description=("✅ Removed." if ok else "❌ Service not found."), kind="info"), delete_after=10)
        return
    if action == "clear":
        count = len(await list_services(ctx.guild.id))
        async def do_clear():
            removed = await clear_services(ctx.guild.id)
            return f"✅ Cleared **{removed}** AI services for **{ctx.guild.name}**."
        await ctx.send(embed=style_embed(
            "Clear AI Services",
            description=f"⚠️ This removes **{count}** services from this server only.",
            kind="warn",
        ), view=ConfirmView(ctx.author.id, do_clear))
        return
    services = await list_services(ctx.guild.id)
    lines = [f"• **{x['service']}**" + (f" — {x['description']}" if x.get('description') else "") for x in services]
    await ctx.send(embed=style_embed("AI Services", description="\n".join(lines)[:3900] if lines else "No services configured.", kind="info"))


async def _start_import(ctx: commands.Context, kind: str, title: str):
    if not await _has_ai_access(ctx):
        return
    key = (ctx.guild.id, ctx.author.id)
    _IMPORT_SESSIONS[key] = {
        "guild_id": ctx.guild.id,
        "user_id": ctx.author.id,
        "channel_id": ctx.channel.id,
        "kind": kind,
        "title": title.strip() or ("Prices" if kind == "price" else "Rules"),
        "chunks": [],
        "chars": 0,
        "started_at": dt.datetime.now(dt.timezone.utc),
    }
    await ctx.send(embed=style_embed(
        f"AI {kind.title()} Import Started",
        description=(
            f"**Title:** {title.strip() or ('Prices' if kind == 'price' else 'Rules')}\n\n"
            "Send the data in as many messages as needed. I will collect up to "
            f"**{_MAX_IMPORT_MESSAGES} messages / {_MAX_IMPORT_CHARS:,} characters**.\n\n"
            "When finished, send **`done`** in this same channel.\n"
            "The data is stored only for this server."
        ),
        kind="info",
    ))


@bot.hybrid_command(name="aiimportprice", help="Bulk-import server-specific AI pricing data")
async def ai_import_price(ctx: commands.Context, *, title: str = "Imported Prices"):
    await _start_import(ctx, "price", title)


@bot.hybrid_command(name="aiimportrules", help="Bulk-import server-specific AI rules")
async def ai_import_rules(ctx: commands.Context, *, title: str = "Imported Rules"):
    await _start_import(ctx, "rule", title)


@bot.hybrid_command(name="aiclear", help="Clear all Premium AI data for this server")
async def ai_clear(ctx: commands.Context):
    if not await _has_ai_access(ctx):
        return
    cfg = await get_server_config(ctx.guild.id)
    if not (_owner(ctx.author) or is_staff(ctx.author, need="admin")):
        await ctx.send(embed=style_embed("Permission Denied", description="❌ Manage Server/Admin access is required to clear all AI data.", kind="error"), delete_after=10)
        return
    async def do_clear():
        removed = await clear_all(ctx.guild.id)
        return (
            f"✅ Cleared this server's AI Manager data.\n"
            f"Prices: `{removed['prices']}` • Rules: `{removed['rules']}` • "
            f"Services: `{removed['services']}` • Imports: `{removed['imports']}`"
        )
    await ctx.send(embed=style_embed(
        "Clear All AI Data",
        description="⚠️ This deletes **all AI Manager prices, rules, services and imported documents for this server only**.",
        kind="warn",
    ), view=ConfirmView(ctx.author.id, do_clear))


async def handle_import_message(message: discord.Message) -> bool:
    """Consume messages belonging to an active bulk AI import session."""
    if not message.guild or message.author.bot:
        return False
    key = (message.guild.id, message.author.id)
    session = _IMPORT_SESSIONS.get(key)
    if not session:
        return False
    if message.channel.id != session["channel_id"]:
        return False

    content = message.content.strip()
    if not content:
        return True

    if content.casefold() == "cancel":
        _IMPORT_SESSIONS.pop(key, None)
        await message.channel.send("❌ AI import cancelled.", delete_after=8)
        return True

    if content.casefold() == "done":
        combined = "\n\n".join(session["chunks"]).strip()
        if not combined:
            await message.channel.send("❌ No data was collected. Import cancelled.", delete_after=8)
            _IMPORT_SESSIONS.pop(key, None)
            return True
        ok = await add_import(
            session["guild_id"],
            session["kind"],
            session["title"],
            combined,
        )
        _IMPORT_SESSIONS.pop(key, None)
        await message.channel.send(
            embed=style_embed(
                "AI Import Complete",
                description=(
                    f"✅ Stored **{len(combined):,} characters** as **{session['title']}**.\n"
                    f"Type: `{session['kind']}`\n"
                    f"Server: **{message.guild.name}**\n\n"
                    "The AI will now use this server-local data when answering `?ai` questions."
                ),
                kind="success" if ok else "error",
            ),
            delete_after=20,
        )
        return True

    if len(session["chunks"]) >= _MAX_IMPORT_MESSAGES or session["chars"] + len(content) > _MAX_IMPORT_CHARS:
        await message.channel.send(
            "⚠️ Import size limit reached. Send `done` to save the collected data or `cancel` to discard it.",
            delete_after=10,
        )
        return True

    session["chunks"].append(content)
    session["chars"] += len(content)
    await message.channel.send(
        f"📥 Import chunk received — `{len(session['chunks'])}/{_MAX_IMPORT_MESSAGES}` messages, `{session['chars']:,}` characters.",
        delete_after=4,
    )
    return True


async def initialize_ai_manager():
    await init_ai_manager_db()
