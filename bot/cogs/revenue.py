py





"""
revenue.py — Revenue Tracking System for Service Servers
Auto-detects revenue reports, validates format, and generates reports.
"""
import discord
from discord.ext import commands
import discord.app_commands as app_commands
import datetime
import re
from collections import defaultdict

from bot.config import (
    bot, style_embed, BRAND_COLOR, UTC, staff_check, is_staff,
    EMOJI_BULLET, BRAND_EMOJI
)
from bot.blox_values import format_value, lookup_payment, refresh_blox_values, cache_status

from bot.revenue_database import (
    add_revenue_entry, get_revenue_entries, get_revenue_summary,
    get_revenue_channel, set_revenue_channel, clear_revenue_channel,
    get_multi_staff_entries, get_total_entries_count, clear_revenue_data
)

# Expected format (FLEXIBLE):
# User : @username OR User : plain_name
# Service : service_name (your internal service name)
# Payment : payment/item received (Blox Fruits value item OR non-ingame payment)
# Paid to : @staff_member OR Paid to : plain_name
# Done by : @helper OR helper_name (OPTIONAL - for team sales)

# Pattern matches both @mentions and plain text names
REVENUE_PATTERN = re.compile(
    r"User\s*:\s*(?:<@!?(\d+)>|([^\n]+?))(?:\n|$).*?"
    r"Service\s*:\s*([^\n]+?)(?:\n|$).*?"
    r"Payment\s*:\s*([^\n]+?)(?:\n|$).*?"
    r"Paid\s*to\s*:\s*(?:<@!?(\d+)>|([^\n]+?))(?:\n|$).*?"
    r"(?:Done\s*by\s*:\s*(?:<@!?(\d+)>|([^\n]+?))(?:\n|$))?",
    re.IGNORECASE | re.DOTALL
)

CORRECT_FORMAT = """
**Correct Format:**
```
User : @username OR customer_name
Service : service_name (e.g., trials, raids, leveling)
Payment : payment/item (e.g., Leopard, Dough, Cashapp)
Paid to : @staff OR staff_name
Done by : @helper OR helper_name (OPTIONAL)
```

**Examples:**
```
User : @HINATA
Service : trials/raids
Payment : Leopard
Paid to : @Roger
```

```
User : HINATA
Service : raids
Payment : Cashapp
Paid to : Roger
Done by : Detrox
```
"""


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
    
    # Extract data (supports both @mentions and plain names)
    user_id_str = match.group(1)  # @mention ID or None
    user_name = match.group(2)     # plain name or None
    service = match.group(3).strip()
    payment_method = match.group(4).strip()
    paid_to_id_str = match.group(5)  # @mention ID or None
    paid_to_name = match.group(6)    # plain name or None
    done_by_id_str = match.group(7)  # @mention ID or None (OPTIONAL)
    done_by_name = match.group(8)    # plain name or None (OPTIONAL)
    
    # Determine user (prefer @mention, fallback to name)
    if user_id_str:
        user_id = int(user_id_str)
        user = message.guild.get_member(user_id)
        user_display = user.display_name if user else f"User {user_id}"
    else:
        user_name = user_name.strip()
        user_id = 0  # Placeholder for plain name
        user_display = user_name
    
    # Determine paid_to (prefer @mention, fallback to name)
    if paid_to_id_str:
        paid_to_id = int(paid_to_id_str)
        paid_to = message.guild.get_member(paid_to_id)
        paid_to_display = paid_to.display_name if paid_to else f"User {paid_to_id}"
    else:
        paid_to_name = paid_to_name.strip()
        paid_to_id = 0  # Placeholder for plain name
        paid_to_display = paid_to_name
    
    # Determine done_by (OPTIONAL - prefer @mention, fallback to name)
    done_by_id = 0
    done_by_display = None
    if done_by_id_str:
        done_by_id = int(done_by_id_str)
        done_by = message.guild.get_member(done_by_id)
        done_by_display = done_by.display_name if done_by else f"User {done_by_id}"
    elif done_by_name:
        done_by_name = done_by_name.strip()
        done_by_id = 0
        done_by_display = done_by_name
    
    # Only PAYMENT is checked against Blox Fruits Values. SERVICE is never used
    # for value calculation. Unknown/non-ingame payments are intentionally
    # left uncalculated; spelling mistakes are not fuzzy-matched.
    payment_value = None
    payment_value_name = None
    payment_value_checked_at = None
    try:
        payment_value, payment_value_name, payment_value_checked_at = await lookup_payment(payment_method)
    except Exception as value_error:
        print(f"⚠️ Blox Fruits value lookup failed: {value_error}")

    # Record in database
    try:
        await add_revenue_entry(
            guild_id=message.guild.id,
            user_name=user_display,
            service=service,
            payment=payment_method,
            paid_to=paid_to_display,
            done_by_id=done_by_id,
            done_by_name=done_by_display,
            message_id=message.id,
            channel_id=message.channel.id,
            payment_value=payment_value,
            payment_value_name=payment_value_name,
            payment_value_checked_at=payment_value_checked_at
        )
        print(f"✅ Revenue entry recorded: {user_display} -> {paid_to_display} ({service}) | payment={payment_method} | value={payment_value}")
        
        # React to confirm
        await message.add_reaction("✅")
        await message.add_reaction("💰")
        
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
#           REVENUE SETUP COMMANDS
# ==========================================

@bot.hybrid_command(name="setrevenuechannel", help="Set the revenue tracking channel (staff/mod only)")
@staff_check(need="mod")
async def set_revenue_channel_cmd(ctx: commands.Context, channel: discord.TextChannel):
    """Set which channel should be monitored for revenue reports."""
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


async def generate_revenue_report(ctx: commands.Context, days: int = None, period_name: str = "Revenue"):
    """Generate a formatted revenue report grouped by staff and showing services provided."""
    
    # Get all entries
    entries = await get_revenue_entries(ctx.guild.id, days=days)
    
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


@bot.hybrid_command(name="revenuedetails", aliases=["revdetails"], help="Show detailed revenue entries (last 10)")
@staff_check(need="mod")
async def revenue_details(ctx: commands.Context, days: int = 7):
    """Show detailed list of recent revenue entries."""
    
    entries = await get_revenue_entries(ctx.guild.id, days=days)
    
    if not entries:
        embed = style_embed(
            title="Revenue Details",
            description=f"No revenue entries found in the last {days} days.",
            kind="info"
        )
        await ctx.send(embed=embed)
        return
    
    # Show last 10 entries
    entries = entries[:10]
    
    description = f"**Last {len(entries)} Entries (Past {days} Days)**\n\n"
    
    for entry in entries:
        # Extract fields from dictionary
        user_name = entry.get("user_name", "Unknown")
        service = entry.get("service", "Unknown")
        payment_method = entry.get("payment", "Unknown")
        paid_to_name = entry.get("paid_to", "Unknown")
        done_by_name = entry.get("done_by_name")
        timestamp = entry.get("timestamp")
        
        # Add "done by" if exists
        staff_display = paid_to_name
        if done_by_name and done_by_name.strip():
            staff_display = f"{paid_to_name}, {done_by_name}"
        
        # Parse date
        try:
            if isinstance(timestamp, datetime.datetime):
                date_str = timestamp.strftime("%m/%d %H:%M")
            else:
                date_str = "Unknown"
        except Exception:
            date_str = "Unknown"
        
        description += f"**{date_str}** • {service}\n"
        description += f"  {EMOJI_BULLET} User: {user_name} → Staff: {staff_display}\n"
        payment_value = entry.get("payment_value")
        if isinstance(payment_value, (int, float)) and payment_value > 0:
            description += f"  {EMOJI_BULLET} Payment: {payment_method} → `{format_value(float(payment_value))}`\n"
        else:
            description += f"  {EMOJI_BULLET} Payment: {payment_method} → ⚠️ Uncalculated / Non-Ingame Payment\n"
        description += "\n"
    
    embed = style_embed(
        title=f"{BRAND_EMOJI} Revenue Details",
        description=description,
        color=BRAND_COLOR,
        kind="info"
    )
    
    embed.set_footer(text="United Bunnies Revenue System")
    
    await ctx.send(embed=embed)


@bot.hybrid_command(name="revenuevia", aliases=["staffrevenue", "revvia"], help="Show revenue for a specific staff member")
@staff_check(need="mod")
async def revenue_via_staff(ctx: commands.Context, staff_name: str, days: int = 30):
    """Show all services provided by a specific staff member."""
    
    # Get all entries
    all_entries = await get_revenue_entries(ctx.guild.id, days=days)
    
    if not all_entries:
        embed = style_embed(
            title="No Revenue Data",
            description=f"No revenue entries found in the last {days} days.",
            kind="info"
        )
        await ctx.send(embed=embed)
        return
    
    # Clean staff name (remove @ if present)
    staff_name = staff_name.strip().lstrip('@')
    
    # Filter entries for this staff member
    staff_entries = []
    matched_staff_name = None
    
    for entry in all_entries:
        # Extract fields from dictionary
        user_name = entry.get("user_name", "Unknown")
        service = entry.get("service", "Unknown")
        payment_method = entry.get("payment", "Unknown")
        paid_to_name = entry.get("paid_to", "Unknown")
        done_by_name = entry.get("done_by_name")
        timestamp = entry.get("timestamp")
        
        # Check if this matches our search (case-insensitive)
        # Check both "paid_to" and "done_by" fields
        staff_match = paid_to_name and staff_name.lower() in paid_to_name.lower()
        done_by_match = done_by_name and staff_name.lower() in done_by_name.lower()
        
        if staff_match or done_by_match:
            staff_entries.append({
                "user_name": user_name,
                "service": service,
                "payment": payment_method,
                "timestamp": timestamp
            })
            if not matched_staff_name:
                matched_staff_name = paid_to_name
    
    if not staff_entries:
        embed = style_embed(
            title="No Results",
            description=f"No revenue entries found for staff member matching **{staff_name}**.",
            kind="info"
        )
        await ctx.send(embed=embed)
        return
    
    # Analyze the data
    services_count = defaultdict(int)
    payments_count = defaultdict(int)
    clients = set()
    
    for entry in staff_entries:
        user_name = entry["user_name"]
        service = entry["service"]
        payment_method = entry["payment"]
        
        services_count[service] += 1
        payments_count[payment_method] += 1
        clients.add(user_name)
    
    total_sales = len(staff_entries)
    
    # Build the report
    description = f"**Staff Member:** {matched_staff_name}\n"
    description += f"**Period:** Last {days} days\n"
    description += f"**Total Tickets:** `{total_sales}`\n"
    description += f"**Unique Clients:** `{len(clients)}`\n\n"
    
    # Services provided (sorted by count)
    description += "**Services:**\n"
    sorted_services = sorted(services_count.items(), key=lambda x: x[1], reverse=True)
    for service, count in sorted_services[:15]:  # Top 15
        percentage = (count/total_sales*100)
        description += f"   • {service}: `{count}x` ({percentage:.1f}%)\n"
    
    if len(sorted_services) > 15:
        remaining = sum(s[1] for s in sorted_services[15:])
        description += f"   • ... and {len(sorted_services) - 15} more (`{remaining}x`)\n"
    
    description += "\n"
    
    # Payment methods breakdown
    description += "**💳 Payments:**\n"
    sorted_payments = sorted(payments_count.items(), key=lambda x: x[1], reverse=True)
    for payment, count in sorted_payments:
        percentage = (count/total_sales*100)
        description += f"   • {payment}: `{count}x` ({percentage:.1f}%)\n"
    
    embed = style_embed(
        title=f"{BRAND_EMOJI} Staff Revenue Report",
        description=description,
        color=BRAND_COLOR,
        kind="info"
    )
    
    embed.set_footer(text=f"United Bunnies Revenue System • Use ?revenuevia \"staff name\" <days>")
    
    await ctx.send(embed=embed)


@bot.hybrid_command(name="revenuehelp", aliases=["revhelp"], help="Show revenue system help")
async def revenue_help(ctx: commands.Context):
    """Display help for the revenue tracking system."""
    
    embed = style_embed(
        title=f"{BRAND_EMOJI} Revenue Tracking System",
        description="Automatically track service revenue and generate reports.",
        color=BRAND_COLOR,
        kind="info"
    )
    
    embed.add_field(
        name="📝 How to Report Revenue",
        value=CORRECT_FORMAT,
        inline=False
    )
    
    embed.add_field(
        name="📊 Staff Commands",
        value=(
            "`?weekrevenue` - Weekly revenue summary\n"
            "`?monthrevenue` - Monthly revenue summary\n"
            "`?todayrevenue` - Today's revenue\n"
            "`?allrevenue` - All-time revenue (Admin only)\n"
            "`?revenuedetails [days]` - Detailed transaction list\n"
            "`?revenuevia \"staff name\" [days]` - Specific staff's sales\n"
        ),
        inline=False
    )
    
    embed.add_field(
        name="⚙️ Admin Commands",
        value=(
            "`?setrevenuechannel #channel` - Enable tracking in a channel\n"
            "`?clearrevenuechannel` - Disable tracking\n"
        ),
        inline=False
    )
    
    embed.set_footer(text="United Bunnies Revenue System")
    
    await ctx.send(embed=embed)


# Export the validation function for use in events.py
__all__ = ['validate_and_record_revenue']
