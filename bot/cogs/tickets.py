from bot.config import quick_embed
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

from bot.config import bot, quick_embed, REQUIRED_ROLE_ID, TICKET_CATEGORY_NAME, UTC
from bot.database import (
    create_ticket_record,
    close_ticket_record,
    claim_ticket_record,
    unclaim_ticket_record,
    get_ticket_record,
    get_open_ticket_for_user,
    list_open_tickets,
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
    staff_role = guild.get_role(REQUIRED_ROLE_ID)

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
        staff_role = interaction.guild.get_role(
            REQUIRED_ROLE_ID
        )

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
        staff_role = interaction.guild.get_role(
            REQUIRED_ROLE_ID
        )

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
        staff_role = interaction.guild.get_role(
            REQUIRED_ROLE_ID
        )

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
        embed=quick_embed(
            "🎫 What do you need help with?"
        ),
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

    staff_role = ctx.guild.get_role(
        REQUIRED_ROLE_ID
    )

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
