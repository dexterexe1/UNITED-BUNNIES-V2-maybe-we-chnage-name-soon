
"""
revenue.py — Revenue Tracking System for Service Servers
Auto-detects revenue reports, validates format, and generates reports.
"""
import discord
from discord.ext import commands
import discord.app_commands as app_commands
import datetime
import asyncio
import re
from collections import defaultdict

from bot.config import (
    bot, style_embed, BRAND_COLOR, UTC, staff_check, is_staff,
    EMOJI_BULLET, BRAND_EMOJI
)
from bot.blox_values import format_value, refresh_blox_values, cache_status
from bot.ai_payment_parser import resolve_payment

from bot.revenue_database import (
    add_revenue_entry, get_revenue_entries, get_revenue_summary,
    get_revenue_channel, set_revenue_channel, clear_revenue_channel,
    get_multi_staff_entries, get_total_entries_count, clear_revenue_data,
    update_revenue_payment_value, get_revenue_manager, set_revenue_manager,
    get_revenue_managers_due, mark_revenue_manager_weekly_dm
)

# Revenue entry format — all 6 fields required:
#
# Client   : client's name or @mention
# Service  : what service was provided (e.g. raids, trials, leveling)
# Payment  : what was received (Blox Fruits item, Robux, Cashapp, etc.)
# Done by  : @staff who completed the service
# Paid to  : @staff who received the payment
# Done at  : service completion date (e.g. 17 Aug 2026)

REVENUE_PATTERN = re.compile(
    r"Client\s*:\s*(?:<@!?(\d+)>|([^\n]+?))(?:\n|$).*?"
    r"Service\s*:\s*([^\n]+?)(?:\n|$).*?"
    r"Payment\s*:\s*([^\n]+?)(?:\n|$).*?"
    r"Done\s*by\s*:\s*(?:<@!?(\d+)>|([^\n]+?))(?:\n|$).*?"
    r"Paid\s*to\s*:\s*(?:<@!?(\d+)>|([^\n]+?))(?:\n|$).*?"
    r"Done\s*at\s*:\s*([^\n]+?)(?:\n|$)",
    re.IGNORECASE | re.DOTALL
)

CORRECT_FORMAT = """
**Required Revenue Format:**
```
Client  : @username OR customer_name
Service : service type (e.g. raids, trials, leveling)
Payment : what you received (e.g. Leopard, Tiger, Robux, Cashapp)
Done by : @staff_who_completed_it
Paid to : @staff_who_received_payment
Done at : service date (e.g. 17 Aug 2026)
```

**All 6 fields are required.** Complete the service first, then submit the entry.

**Examples:**
```
Client  : @HINATA
Service : raids
Payment : Leopard
Done by : @Detrox
Paid to : @Roger
Done at : 17 Aug 2026
```
```
Client  : HINATA
Service : trials
Payment : Robux
Done by : Detrox
Paid to : Roger
Done at : 17/08/2026
```

**Calculable Blox Fruits items:** `Tiger`, `Dough`, `Leopard`, `Kitsune`, `Dragon`, `2x Money`, `2x Mastery`, `Fast Boats`, `Red Lightning`, `Purple Lightning`, `Werewolf`
**Other payments** (Robux, Cashapp, etc.) are recorded as-is without a calculated value.
"""

DATE_FORMATS = (
    "%d %b %Y", "%d %B %Y", "%d/%m/%Y", "%d-%m-%Y",
    "%Y-%m-%d", "%Y/%m/%d", "%d.%m.%Y",
)

def _parse_done_at(raw: str):
    value = (raw or "").strip()
    if not value:
        return None
    if value.lower() in {"today", "now"}:
        now = datetime.datetime.now(UTC)
        return now
    if value.lower() == "yesterday":
        return datetime.datetime.now(UTC) - datetime.timedelta(days=1)
    for fmt in DATE_FORMATS:
        try:
            parsed = datetime.datetime.strptime(value, fmt)
            return parsed.replace(tzinfo=UTC)
        except ValueError:
            pass
    return None

def _find_member_by_name(guild: discord.Guild, raw: str):
    target = (raw or "").strip().lstrip("@").lower()
    if not target:
        return None
    for member in guild.members:
        candidates = {
            str(member.id), member.display_name.lower(), member.name.lower(),
        }
        if target in candidates:
            return member
    return None


async def validate_and_record_revenue(message: discord.Message):
    """
    Auto-detect revenue reports in the designated channel.
    Validates format, stores in database, and provides feedback.
    """
    # Check if this is the revenue channel
    revenue_channel_id = await get_revenue_channel(message.guild.id)
    print(f"🔍 Revenue validation check - DB Channel ID: {revenue_channel_id}, Message channel: {message.channel.id}")
    if not revenue_channel_id or message.channel.id != revenue_channel_id:
        print(f"❌ Not revenue channel - skipping")
        return False
    
    print(f"✅ Message is in revenue channel, validating format...")
    # Skip bot messages and commands
    if message.author.bot or message.content.startswith("?"):
        print(f"⏭️ Skipping bot message or command")
        return False
    
    # Try to parse the revenue report
    print(f"📝 Message content: {message.content}")
    match = REVENUE_PATTERN.search(message.content)
    print(f"📝 Regex match result: {match}")
    
    if not match:
        # Invalid format - notify and delete
        print(f"❌ Invalid format - sending error")
        try:
            warning = await message.reply(
                f"❌ {message.author.mention} **Invalid revenue report format!**\n{CORRECT_FORMAT}",
                mention_author=True
            )
            await message.delete()
            await warning.delete(delay=15)
        except Exception as e:
            print(f"⚠️ Error sending validation message: {e}")
        return True
    
    # Extract data — groups match REVENUE_PATTERN order:
    # 1/2 = client id / plain name
    # 3   = service
    # 4   = payment
    # 5/6 = done_by id / plain name
    # 7/8 = paid_to id / plain name
    # 9   = done_at date
    client_id_str  = match.group(1)
    client_name    = match.group(2)
    service        = match.group(3).strip()
    payment_method = match.group(4).strip()
    done_by_id_str = match.group(5)
    done_by_name   = match.group(6)
    paid_to_id_str = match.group(7)
    paid_to_name   = match.group(8)
    done_at_raw    = match.group(9).strip()

    # Required field checks
    missing = []
    if not service:
        missing.append("Service")
    if not payment_method:
        missing.append("Payment")
    if not (done_by_id_str or (done_by_name and done_by_name.strip())):
        missing.append("Done by")
    if not (paid_to_id_str or (paid_to_name and paid_to_name.strip())):
        missing.append("Paid to")
    if not done_at_raw:
        missing.append("Done at")
    if missing:
        try:
            warning = await message.reply(
                f"⚠️ {message.author.mention} **Revenue entry incomplete.**\n\n"
                f"Missing required field(s): **{', '.join(missing)}**\n\n"
                f"{CORRECT_FORMAT}",
                mention_author=True
            )
            await message.delete()
            await warning.delete(delay=20)
        except Exception as e:
            print(f"⚠️ Error sending incomplete revenue message: {e}")
        return True

    done_at = _parse_done_at(done_at_raw)
    if done_at is None:
        try:
            warning = await message.reply(
                f"❌ {message.author.mention} **Invalid Done at date.**\n"
                "Use a date like `17 Aug 2026`, `17/08/2026`, or `2026-08-17`.",
                mention_author=True
            )
            await message.delete()
            await warning.delete(delay=15)
        except Exception as e:
            print(f"⚠️ Error sending invalid-date message: {e}")
        return True

    # Resolve client
    if client_id_str:
        client_id = int(client_id_str)
        client = message.guild.get_member(client_id)
        client_display = client.display_name if client else f"User {client_id}"
    else:
        client_display = (client_name or "").strip()
        client_id = 0

    # Resolve done_by (service completer) — accept plain names as-is
    if done_by_id_str:
        done_by_id = int(done_by_id_str)
        done_by = message.guild.get_member(done_by_id)
        done_by_display = done_by.display_name if done_by else f"User {done_by_id}"
    else:
        done_by = _find_member_by_name(message.guild, done_by_name)
        done_by_id = done_by.id if done_by else 0
        done_by_display = done_by.display_name if done_by else (done_by_name or "").strip()

    # Resolve paid_to (payment recipient) — accept plain names as-is
    if paid_to_id_str:
        paid_to_id = int(paid_to_id_str)
        paid_to = message.guild.get_member(paid_to_id)
        paid_to_display = paid_to.display_name if paid_to else f"User {paid_to_id}"
    else:
        paid_to_display = (paid_to_name or "").strip()
        paid_to_id = 0

    # Payment value: try to calculate from Blox Fruits item.
    # Non-ingame payments (Robux, Cashapp, etc.) remain uncalculated — that's fine.
    payment_value = None
    payment_value_name = None
    payment_value_checked_at = None
    payment_source = None
    try:
        payment_value, payment_value_name, payment_value_checked_at, payment_source = await resolve_payment(payment_method)
    except Exception as value_error:
        print(f"⚠️ Payment parser failed: {value_error}")

    # Record in database
    try:
        await add_revenue_entry(
            guild_id=message.guild.id,
            user_name=client_display,
            service=service,
            payment=payment_method,
            paid_to=paid_to_display,
            done_by_id=done_by_id,
            done_by_name=done_by_display,
            done_at=done_at,
            message_id=message.id,
            channel_id=message.channel.id,
            payment_value=payment_value,
            payment_value_name=payment_value_name,
            payment_value_checked_at=payment_value_checked_at
        )
        print(f"✅ Revenue entry recorded: client={client_display} service={service} payment={payment_method} paid_to={paid_to_display} done_by={done_by_display} done_at={done_at} value={payment_value}")
        
        # React to confirm
        await message.add_reaction("✅")
        date_str = done_at.strftime("%d %b %Y") if done_at else done_at_raw
        value_text = f"`{format_value(float(payment_value))}`" if payment_value is not None else "`Uncalculated / Non-Ingame`"
        if payment_value is not None:
            await message.add_reaction("💰")
        await message.channel.send(
            f"✅ **Revenue Entry Recorded**\n"
            f"**Client:** {client_display}\n"
            f"**Service:** {service}\n"
            f"**Payment:** {payment_method}  →  {value_text}\n"
            f"**Done by:** {done_by_display}\n"
            f"**Paid to:** {paid_to_display}\n"
            f"**Date:** {date_str}",
            delete_after=15,
        )

    except Exception as e:
        print(f"❌ Error recording revenue: {e}")
        try:
            await message.reply(
                f"❌ Failed to record revenue entry. Please contact an administrator.",
                delete_after=10
            )
        except Exception:
            pass
    
    return True


# ==========================================
#        REVENUE MANAGER COMMANDS
# ==========================================

@bot.hybrid_command(
    name="makerevenuemanager",
    help="Assign a staff member as the server's revenue manager (mod only)"
)
@staff_check(need="mod")
async def make_revenue_manager_cmd(ctx: commands.Context, member: discord.Member):
    """Assign one staff member as the revenue manager before revenue setup."""
    if not ctx.guild:
        return

    success = await set_revenue_manager(ctx.guild.id, member.id, ctx.author.id)
    if not success:
        await ctx.send(embed=style_embed(
            title="Revenue Manager Error",
            description="❌ I could not save the revenue manager. Please try again or contact an administrator.",
            kind="error",
        ))
        return

    try:
        dm_embed = style_embed(
            title="Revenue Manager Assigned",
            description=(
                f"You have been assigned as the **Revenue Manager** for **{ctx.guild.name}**.\n\n"
                "Each week, I will send you a private reminder to review the revenue activity and "
                "give the moderators a clear summary.\n\n"
                "**Weekly workflow**\n"
                "• Run `?weekrevenue` for the weekly summary.\n"
                "• Review `?revenuedetails 7` when you need transaction-level details.\n"
                "• Send the important totals, services, payments, and any issues to the moderators.\n\n"
                "Your DM is private and is only sent to you by the bot."
            ),
            kind="success",
        )
        await member.send(embed=dm_embed)
        dm_note = " A private confirmation was also sent to them."
    except (discord.Forbidden, discord.HTTPException):
        dm_note = " I could not DM them, so they may need to allow server-member DMs."

    await ctx.send(embed=style_embed(
        title="Revenue Manager Assigned",
        description=(
            f"{member.mention} is now the **Revenue Manager** for this server.\n\n"
            "You can now set the revenue channel with `?setrevenuechannel #channel`."
            f"{dm_note}"
        ),
        kind="success",
    ))


async def revenue_manager_weekly_loop():
    """Send private weekly revenue-manager reminders."""
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            due = await get_revenue_managers_due()
            for manager in due:
                guild = bot.get_guild(int(manager.get("guild_id")))
                manager_user_id = manager.get("manager_user_id")
                manager_id = manager.get("_id")
                if not guild or not manager_user_id:
                    await mark_revenue_manager_weekly_dm(manager_id)
                    continue

                member = guild.get_member(int(manager_user_id))
                if member is None:
                    try:
                        member = await guild.fetch_member(int(manager_user_id))
                    except (discord.NotFound, discord.HTTPException):
                        member = None

                if member is None:
                    await mark_revenue_manager_weekly_dm(manager_id)
                    continue

                entries = await get_revenue_entries(guild.id, days=7)
                entries = await _backfill_missing_payment_values(entries)
                total = len(entries)
                calculated_total = sum(float(e.get("payment_value") or 0) for e in entries)
                uncalculated_count = sum(1 for e in entries if not (isinstance(e.get("payment_value"), (int, float)) and e.get("payment_value") > 0))
                services = defaultdict(int)
                payments = defaultdict(int)
                for entry in entries:
                    services[str(entry.get("service") or "Unknown")] += 1
                    payments[str(entry.get("payment") or "Unknown")] += 1

                top_services = sorted(services.items(), key=lambda x: x[1], reverse=True)[:5]
                top_payments = sorted(payments.items(), key=lambda x: x[1], reverse=True)[:5]
                service_lines = "\n".join(f"• {name}: `{count}x`" for name, count in top_services) or "• None"
                payment_lines = "\n".join(f"• {name}: `{count}x`" for name, count in top_payments) or "• None"

                reminder = style_embed(
                    title="Weekly Revenue Manager Reminder",
                    description=(
                        f"Hi {member.mention} — this is your weekly private revenue reminder for **{guild.name}**.\n\n"
                        "Please review the last 7 days of revenue and **give the moderators a clear summary**. "
                        "Use `?weekrevenue` for the full weekly report and `?revenuedetails 7` for transaction details.\n\n"
                        f"**Last 7 Days**\n"
                        f"• Transactions: `{total}`\n"
                        f"• Calculated In-Game Revenue: `{format_value(calculated_total)}`\n"
                        f"• Uncalculated / Non-Ingame: `{uncalculated_count}`\n\n"
                        f"**Top Services**\n{service_lines}\n\n"
                        f"**Top Payments**\n{payment_lines}\n\n"
                        "Once reviewed, please pass the useful numbers, payment breakdown, staff activity, "
                        "and any concerns to the moderators."
                    ),
                    kind="info",
                )
                try:
                    await member.send(embed=reminder)
                except (discord.Forbidden, discord.HTTPException) as exc:
                    print(f"⚠️ Could not DM revenue manager {member.id} in guild {guild.id}: {exc}")
                finally:
                    await mark_revenue_manager_weekly_dm(manager_id)

        except Exception as exc:
            print(f"⚠️ Revenue manager weekly loop error: {exc}")

        await asyncio.sleep(1800)


_revenue_manager_loop_task = None

def start_revenue_manager_weekly_loop():
    """Start the weekly revenue-manager DM worker exactly once."""
    global _revenue_manager_loop_task
    if _revenue_manager_loop_task is None or _revenue_manager_loop_task.done():
        _revenue_manager_loop_task = asyncio.create_task(revenue_manager_weekly_loop())
        print("✅ Revenue manager weekly DM loop started")


# ==========================================
#           REVENUE SETUP COMMANDS
# ==========================================

@bot.hybrid_command(name="setrevenuechannel", help="Set the revenue tracking channel (staff/mod only)")
@staff_check(need="mod")
async def set_revenue_channel_cmd(ctx: commands.Context, channel: discord.TextChannel):
    """Set which channel should be monitored for revenue reports."""
    manager_id = await get_revenue_manager(ctx.guild.id)
    if not manager_id:
        await ctx.send(embed=style_embed(
            title="Revenue Manager Required",
            description=(
                "❌ A Revenue Manager must be assigned before the revenue channel can be set.\n\n"
                "A moderator should run:\n"
                "`?makerevenuemanager @user`\n\n"
                "After that, run `?setrevenuechannel #channel`."
            ),
            kind="warn",
        ))
        return

    success = await set_revenue_channel(ctx.guild.id, channel.id, ctx.author.id)
    
    if not success:
        embed = style_embed(
            title="Error",
            description="❌ Failed to set revenue channel. Database connection may be unavailable.",
            kind="error"
        )
        await ctx.send(embed=embed)
        return
    
    embed = style_embed(
        title="Revenue Tracking Enabled",
        description=f"Revenue reports will now be tracked in {channel.mention}.\n\n"
                    f"Staff can post reports using this format:\n{CORRECT_FORMAT}",
        kind="success"
    )
    await ctx.send(embed=embed)


@bot.hybrid_command(name="clearrevenuechannel", help="Disable revenue tracking (staff only)")
@staff_check(need="admin")
async def clear_revenue_channel_cmd(ctx: commands.Context):
    """Stop tracking revenue reports."""
    await clear_revenue_channel(ctx.guild.id)
    
    embed = style_embed(
        title="Revenue Tracking Disabled",
        description="Revenue tracking has been disabled for this server.",
        kind="info"
    )
    await ctx.send(embed=embed)


@bot.hybrid_command(name="clearrevenue", help="Delete all revenue history for this server (admin only)")
@staff_check(need="admin")
async def clear_revenue_cmd(ctx: commands.Context):
    """Delete all revenue entries for the current server only."""
    if not ctx.guild:
        return

    deleted_count = await clear_revenue_data(ctx.guild.id)

    embed = style_embed(
        title="Revenue Data Cleared",
        description=(
            f"🧹 Successfully deleted **{deleted_count}** revenue entries "
            "from this server.\n\n"
            "Revenue tracking is still enabled."
        ),
        kind="success"
    )
    await ctx.send(embed=embed)


# ==========================================
#         REVENUE REPORT COMMANDS
# ==========================================

@bot.hybrid_command(name="refreshbloxvalues", aliases=["refreshvalues", "bloxvaluesrefresh"], help="Refresh the live Blox Fruits value cache")
@staff_check(need="mod")
async def refresh_blox_values_cmd(ctx: commands.Context):
    """Force-refresh Blox Fruits Values from the configured source website."""
    success, count, refreshed_at = await refresh_blox_values(force=True)
    if success:
        when = refreshed_at.strftime("%Y-%m-%d %H:%M UTC") if refreshed_at else "unknown"
        description = f"✅ Refreshed **{count}** Blox Fruits values.\n\nLast refresh: `{when}`"
    else:
        description = (
            "⚠️ Could not refresh Blox Fruits Values right now. "
            f"The bot kept its last known cache ({count} items)."
        )
    await ctx.send(embed=style_embed(
        title=f"{BRAND_EMOJI} Blox Fruits Values",
        description=description,
        color=BRAND_COLOR,
        kind="info"
    ))


@bot.hybrid_command(name="weekrevenue", aliases=["week", "weeklyrevenue"], help="Show revenue for the past 7 days")
@staff_check(need="mod")
async def week_revenue(ctx: commands.Context):
    """Display weekly revenue summary grouped by staff member."""
    await generate_revenue_report(ctx, days=7, period_name="Weekly")


@bot.hybrid_command(name="monthrevenue", aliases=["month", "monthlyrevenue"], help="Show revenue for the past 30 days")
@staff_check(need="mod")
async def month_revenue(ctx: commands.Context):
    """Display monthly revenue summary grouped by staff member."""
    await generate_revenue_report(ctx, days=30, period_name="Monthly")


@bot.hybrid_command(name="todayrevenue", aliases=["today", "dailyrevenue"], help="Show revenue for today")
@staff_check(need="mod")
async def today_revenue(ctx: commands.Context):
    """Display today's revenue summary."""
    await generate_revenue_report(ctx, days=1, period_name="Today's")


@bot.hybrid_command(name="allrevenue", aliases=["totalrevenue"], help="Show all-time revenue")
@staff_check(need="admin")
async def all_revenue(ctx: commands.Context):
    """Display all-time revenue summary."""
    await generate_revenue_report(ctx, days=None, period_name="All-Time")


async def _backfill_missing_payment_values(entries):
    """Re-check older MongoDB entries that were previously saved without a value."""
    changed = 0
    for entry in entries:
        if entry.get("payment_value") is not None:
            continue
        payment = str(entry.get("payment") or "").strip()
        if not payment:
            continue
        try:
            value, name, checked_at, _source = await resolve_payment(payment)
        except Exception:
            continue
        if value is None:
            continue
        entry["payment_value"] = value
        entry["payment_value_name"] = name
        entry["payment_value_checked_at"] = checked_at
        try:
            if await update_revenue_payment_value(entry.get("_id"), value, name, checked_at):
                changed += 1
        except Exception as exc:
            print(f"⚠️ Could not backfill revenue entry: {exc}")
    if changed:
        print(f"♻️ Backfilled {changed} revenue payment value(s)")
    return entries


async def generate_revenue_report(ctx: commands.Context, days: int = None, period_name: str = "Revenue"):
    """Generate a formatted revenue report grouped by staff and showing services provided."""
    
    # Get all entries
    entries = await get_revenue_entries(ctx.guild.id, days=days)
    entries = await _backfill_missing_payment_values(entries)
    
    if not entries:
        embed = style_embed(
            title=f"{period_name} Revenue Report",
            description="No revenue entries found for this period.",
            kind="info"
        )
        await ctx.send(embed=embed)
        return
    
    # Group by staff member, then by service
    # Separate: single staff vs multi-staff (with done_by)
    single_staff_data = defaultdict(lambda: {'services': defaultdict(int), 'payments': defaultdict(int)})
    multi_staff_data = defaultdict(lambda: {'services': defaultdict(int), 'payments': defaultdict(int)})
    total_entries = len(entries)
    calculated_total = sum(float(e.get("payment_value") or 0) for e in entries)
    uncalculated = defaultdict(int)
    calculated_payments = defaultdict(lambda: {"count": 0, "value": 0.0})

    for entry in entries:
        payment = entry.get("payment", "Unknown")
        value = entry.get("payment_value")
        if isinstance(value, (int, float)) and value > 0:
            calculated_payments[payment]["count"] += 1
            calculated_payments[payment]["value"] += float(value)
        else:
            uncalculated[payment] += 1
    
    for entry in entries:
        # Extract fields from dictionary
        user_name = entry.get("user_name")
        service = entry.get("service", "Unknown")
        payment_method = entry.get("payment", "Unknown")
        paid_to_name = entry.get("paid_to", "Unknown")
        done_by_name = entry.get("done_by_name")
        
        # Staff key is just the paid_to name
        staff_key = paid_to_name
        
        # Check if multi-staff (done_by exists)
        if done_by_name and done_by_name.strip():
            # Multi-staff service - create combined key
            multi_key = f"{staff_key} & {done_by_name}"
            multi_staff_data[multi_key]['services'][service] += 1
            multi_staff_data[multi_key]['payments'][payment_method] += 1
        else:
            # Single staff service
            single_staff_data[staff_key]['services'][service] += 1
            single_staff_data[staff_key]['payments'][payment_method] += 1
    
    # Build the report
    description = f"📊 **Total Transactions:** {total_entries}\n"
    description += f"💰 **Calculated In-Game Revenue:** `{format_value(calculated_total)}`\n\n"
    description += "**💰 Calculated Payments:**\n"
    for payment, data in sorted(calculated_payments.items(), key=lambda item: item[1]["value"], reverse=True):
        description += f"   • {payment}: `{data['count']}x` → `{format_value(data['value'])}`\n"
    if not calculated_payments:
        description += "   • None\n"

    description += "\n**⚠️ Uncalculated / Non-Ingame Payment:**\n"
    if uncalculated:
        for payment, count in sorted(uncalculated.items(), key=lambda item: item[1], reverse=True):
            description += f"   • {payment}: `{count}x`\n"
    else:
        description += "   • None\n"

    description += "\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # Single staff section
    sorted_staff = sorted(single_staff_data.items(), key=lambda x: sum(x[1]['services'].values()), reverse=True)
    
    for staff_name, data in sorted_staff:
        services = data['services']
        payments = data['payments']
        staff_total = sum(services.values())
        
        description += f"**{EMOJI_BULLET} {staff_name}** ({staff_total} ticket{'s' if staff_total != 1 else ''} done)\n\n"
        
        # Services section
        description += f"**Services:**\n"
        sorted_services = sorted(services.items(), key=lambda x: x[1], reverse=True)
        for service, count in sorted_services[:10]:
            description += f"   • {service}: `{count}x`\n"
        
        if len(sorted_services) > 10:
            remaining = sum(s[1] for s in sorted_services[10:])
            description += f"   • ... and {len(sorted_services) - 10} more (`{remaining}x`)\n"
        
        description += "\n"
        
        # Payment methods section
        description += f"**💳 Payments:**\n"
        sorted_payments = sorted(payments.items(), key=lambda x: x[1], reverse=True)
        for method, cnt in sorted_payments:
            description += f"   • {method}: `{cnt}x`\n"
        
        description += "\n"
    
    # Multi-staff section (if any)
    if multi_staff_data:
        multi_total = sum(sum(d['services'].values()) for d in multi_staff_data.values())
        description += "━━━━━━━━━━━━━━━━━━━━━━\n"
        description += f"**👥 MULTI-STAFF SERVICES** ({multi_total} ticket{'s' if multi_total != 1 else ''})\n\n"
        
        sorted_multi = sorted(multi_staff_data.items(), key=lambda x: sum(x[1]['services'].values()), reverse=True)
        
        for staff_names, data in sorted_multi:
            services = data['services']
            payments = data['payments']
            multi_staff_total = sum(services.values())
            
            description += f"**{EMOJI_BULLET} {staff_names}** ({multi_staff_total} ticket{'s' if multi_staff_total != 1 else ''})\n\n"
            
            # Services
            description += f"**Services:**\n"
            sorted_services = sorted(services.items(), key=lambda x: x[1], reverse=True)
            for service, count in sorted_services[:10]:
                description += f"   • {service}: `{count}x`\n"
            
            description += "\n"
            
            # Payments
            description += f"**💳 Payments:**\n"
            sorted_payments = sorted(payments.items(), key=lambda x: x[1], reverse=True)
            for method, cnt in sorted_payments:
                description += f"   • {method}: `{cnt}x`\n"
            
            description += "\n"
    
    embed = style_embed(
        title=f"{BRAND_EMOJI} {period_name} Revenue Report {BRAND_EMOJI}",
        description=description,
        color=BRAND_COLOR,
        kind="info"
    )
    
    # Add timestamp
    embed.set_footer(text=f"United Bunnies Revenue System • Generated at {datetime.datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}")
    
    await ctx.send(embed=embed)


@bot.hybrid_command(name="revenuedetails", aliases=["revdetails"], help="Show detailed revenue entries with client, service, payment, paid-to, done-by, date, and value")
@staff_check(need="mod")
async def revenue_details(ctx: commands.Context, days: int = 7):
    """Show detailed recent revenue entries with all stored fields."""
    if days < 1 or days > 3650:
        await ctx.send(embed=style_embed(title="Revenue Details", description="❌ Days must be between 1 and 3650.", kind="error"))
        return

    entries = await get_revenue_entries(ctx.guild.id, days=days)
    entries = await _backfill_missing_payment_values(entries)
    if not entries:
        await ctx.send(embed=style_embed(title="Revenue Details", description=f"No revenue entries found in the last {days} days.", kind="info"))
        return

    entries = entries[:25]
    description = f"**Last {len(entries)} Entries (Past {days} Days)**\n\n"
    for entry in entries:
        client = entry.get("client_name") or entry.get("user_name") or "Unknown"
        service = entry.get("service", "Unknown")
        payment = entry.get("payment", "Unknown")
        paid_to = entry.get("paid_to", "Unknown")
        done_by = entry.get("done_by_name") or "Unknown"
        done_at = entry.get("done_at") or entry.get("timestamp")
        if isinstance(done_at, datetime.datetime):
            if done_at.tzinfo is None:
                done_at = done_at.replace(tzinfo=UTC)
            date_str = done_at.strftime("%d %b %Y")
        else:
            date_str = "Unknown"
        value = entry.get("payment_value")
        value_text = format_value(float(value)) if isinstance(value, (int, float)) and value > 0 else "Uncalculated / Non-Ingame"

        description += (
            f"**{date_str}**\n"
            f"  👤 **Client:** {client}\n"
            f"  🛠️ **Service:** {service}\n"
            f"  💳 **Payment:** {payment}  •  `{value_text}`\n"
            f"  ✅ **Done by:** {done_by}\n"
            f"  💰 **Paid to:** {paid_to}\n\n"
        )

    if len(entries) < len(await get_revenue_entries(ctx.guild.id, days=days)):
        description += "_Showing the latest 25 entries._\n"

    embed = style_embed(title=f"{BRAND_EMOJI} Revenue Details", description=description, color=BRAND_COLOR, kind="info")
    embed.set_footer(text="United Bunnies Revenue System")
    await ctx.send(embed=embed)


@bot.hybrid_command(name="revenuevia", aliases=["staffrevenue", "revvia"], help="Show detailed revenue for a specific staff member")
@staff_check(need="mod")
async def revenue_via_staff(ctx: commands.Context, staff_name: str, days: int = 30):
    """Show revenue where a staff member was the payment recipient or service completer."""
    staff_name = staff_name.strip().lstrip('@')
    if not staff_name:
        await ctx.send(embed=style_embed(title="Revenue Staff Report", description="❌ Provide a staff member name.", kind="error"))
        return

    entries = await get_revenue_entries(ctx.guild.id, days=days, staff_name=staff_name)
    entries = await _backfill_missing_payment_values(entries)
    if not entries:
        await ctx.send(embed=style_embed(title="No Results", description=f"No revenue entries found for **{staff_name}** in the last {days} days.", kind="info"))
        return

    total = len(entries)
    calculated_total = sum(float(e.get("payment_value") or 0) for e in entries)
    clients = {str(e.get("client_name") or e.get("user_name") or "Unknown") for e in entries}
    services = defaultdict(int)
    payments = defaultdict(int)
    done_by_count = defaultdict(int)
    paid_to_count = defaultdict(int)

    for e in entries:
        services[str(e.get("service") or "Unknown")] += 1
        payments[str(e.get("payment") or "Unknown")] += 1
        paid_to_count[str(e.get("paid_to") or "Unknown")] += 1
        done_by_count[str(e.get("done_by_name") or "Unknown")] += 1

    description = (
        f"**Staff:** `{staff_name}`\n"
        f"**Period:** Last `{days}` days\n"
        f"**Total Transactions:** `{total}`\n"
        f"**Unique Clients:** `{len(clients)}`\n"
        f"**Calculated Revenue:** `{format_value(calculated_total)}`\n\n"
        "**Services:**\n"
    )
    for service, count in sorted(services.items(), key=lambda x: x[1], reverse=True)[:15]:
        description += f"• {service}: `{count}x`\n"
    description += "\n**Payments:**\n"
    for payment, count in sorted(payments.items(), key=lambda x: x[1], reverse=True)[:15]:
        description += f"• {payment}: `{count}x`\n"

    description += "\n**Recent Transactions:**\n"
    for e in entries[:10]:
        client = e.get("client_name") or e.get("user_name") or "Unknown"
        service = e.get("service") or "Unknown"
        payment = e.get("payment") or "Unknown"
        done_by = e.get("done_by_name") or "Unknown"
        paid_to = e.get("paid_to") or "Unknown"
        dt = e.get("done_at") or e.get("timestamp")
        date_str = dt.strftime("%d %b %Y") if isinstance(dt, datetime.datetime) else "Unknown"
        description += f"• `{date_str}` — {client} — {service} — {payment} — paid to {paid_to} — done by {done_by}\n"

    embed = style_embed(title=f"{BRAND_EMOJI} Staff Revenue Report", description=description, color=BRAND_COLOR, kind="info")
    embed.set_footer(text=f"United Bunnies Revenue System • ?revenuevia \"staff name\" {days}")
    await ctx.send(embed=embed)


@bot.hybrid_command(name="revenuehelp", aliases=["revhelp"], help="Show revenue system commands and reporting details")
async def revenue_help(ctx: commands.Context):
    """Display the complete revenue system help."""
    embed = style_embed(
        title=f"{BRAND_EMOJI} Revenue Tracking System",
        description=(
            "Track every completed service with client, service, payment, paid-to, done-by, "
            "completion date, and calculated payment value."
        ),
        color=BRAND_COLOR,
        kind="info"
    )

    embed.add_field(name="📝 Revenue Entry — ALL FIELDS REQUIRED", value=CORRECT_FORMAT, inline=False)
    embed.add_field(
        name="📊 Report Commands",
        value=(
            "`?todayrevenue` / `/todayrevenue` — today's totals and breakdown\n"
            "`?weekrevenue` / `/weekrevenue` — last 7 days\n"
            "`?monthrevenue` / `/monthrevenue` — last 30 days\n"
            "`?allrevenue` / `/allrevenue` — all-time report (Admin)\n"
            "`?revenuedetails [days]` / `/revenuedetails` — full transaction details (client, service, payment, value, paid to, done by, done at)\n"
            "`?revenuevia <staff> [days]` / `/revenuevia` — staff-specific totals + recent transactions\n"
        ), inline=False
    )
    embed.add_field(
        name="👤 Revenue Manager",
        value=(
            "`?makerevenuemanager @user` / `/makerevenuemanager` — assign the weekly revenue manager\n"
            "`?setrevenuechannel #channel` / `/setrevenuechannel` — enable revenue tracking after manager setup\n"
            "`?clearrevenuechannel` / `/clearrevenuechannel` — disable tracking\n"
            "The Revenue Manager receives a private weekly reminder to review totals and send the moderators a summary.\n"
        ), inline=False
    )
    embed.add_field(
        name="🛠️ Admin",
        value=(
            "`?clearrevenue` / `/clearrevenue` — delete this server's revenue history (Admin only)\n"
            "`?refreshbloxvalues` / `/refreshbloxvalues` — refresh Blox Fruits values (Mod)\n"
        ), inline=False
    )
    embed.add_field(
        name="⚠️ Important",
        value=(
            "`Done by` is the staff member who completed the service.\n"
            "`Paid to` is the staff member who received the payment.\n"
            "`Done at` records the service completion date.\n"
            "Payment value is auto-calculated for Blox Fruits items. Robux, Cashapp, and other non-ingame payments are saved as Uncalculated."
        ), inline=False
    )
    embed.set_footer(text="United Bunnies Revenue System")
    await ctx.send(embed=embed)


# Export the validation function for use in events.py
__all__ = ['validate_and_record_revenue']
