from bot.ui.premium_cards import quick_card_view, style_card_view
"""
marriage.py — Marriage / proposal system.
Extracted from the original monolithic bot.py. Logic unchanged.
"""
import discord
from discord.ext import commands
import discord.app_commands as app_commands
import datetime

from bot.config import bot, quick_embed, UTC
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
        embed = discord.Embed(
            description=f"💍 **{member.display_name}** is already married! Better luck next time.",
            color=discord.Color.red(),
        )
        await ctx.send(view=view)
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
    await ctx.send(view=view)


