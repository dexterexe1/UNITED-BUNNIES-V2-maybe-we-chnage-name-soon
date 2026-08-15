# 🔄 Revenue Tracking System - Flow Diagram

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    UNITED BUNNIES BOT                            │
│                  Revenue Tracking System                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1️⃣ Setup Flow

```
┌──────────────┐
│   Admin      │
└──────┬───────┘
       │
       │ Types: ?setrevenuechannel #revenue-reports
       │
       ▼
┌──────────────────────┐
│   Bot (config.py)    │
│   Validates Admin    │
└──────┬───────────────┘
       │
       │ Stores channel ID
       │
       ▼
┌──────────────────────────────┐
│   Database (database.py)     │
│   UPDATE server_config       │
│   SET revenue_channel_id     │
└──────┬───────────────────────┘
       │
       │ Success!
       │
       ▼
┌──────────────────────┐
│   Discord Message    │
│   ✅ Revenue         │
│   Tracking Enabled   │
└──────────────────────┘
```

---

## 2️⃣ Revenue Report Flow

```
┌──────────────┐
│   Staff      │
└──────┬───────┘
       │
       │ Posts in #revenue-reports:
       │ User : @Customer
       │ Service : shark trial
       │ Payment : portal
       │ Paid to : @Roger
       │
       ▼
┌─────────────────────────────────┐
│   Bot (events.py)               │
│   on_message() handler          │
└──────┬──────────────────────────┘
       │
       │ Checks: Is this the revenue channel?
       │
       ▼
┌─────────────────────────────────┐
│   Revenue Cog (revenue.py)      │
│   validate_and_record_revenue() │
└──────┬──────────────────────────┘
       │
       ├──────────────┬──────────────┐
       │              │              │
       │ Valid?       │ Invalid?     │
       ▼              ▼              │
    ✅ YES         ❌ NO           │
       │              │              │
       │              │ 1. Ping user │
       │              │ 2. Show format
       │              │ 3. Delete msg
       │              │ 4. Delete after 15s
       │              └──────────────┘
       │
       │ Parse data:
       │ • user_id
       │ • service
       │ • payment_method
       │ • paid_to_id
       │
       ▼
┌─────────────────────────────────┐
│   Database (database.py)        │
│   add_revenue_entry()           │
│                                 │
│   INSERT INTO revenue_entries   │
└──────┬──────────────────────────┘
       │
       │ Stored successfully
       │
       ▼
┌─────────────────────────────────┐
│   Bot Reactions                 │
│   ✅ (confirmed)                │
│   💰 (revenue)                  │
└─────────────────────────────────┘
```

---

## 3️⃣ Report Generation Flow

```
┌──────────────┐
│   Staff      │
└──────┬───────┘
       │
       │ Types: ?weekrevenue
       │
       ▼
┌─────────────────────────────────┐
│   Revenue Cog (revenue.py)      │
│   week_revenue() command        │
└──────┬──────────────────────────┘
       │
       │ Calls: generate_revenue_report(days=7)
       │
       ▼
┌─────────────────────────────────┐
│   Database (database.py)        │
│   get_revenue_summary_by_staff()│
│                                 │
│   SELECT paid_to_id,            │
│          payment_method,        │
│          COUNT(*)               │
│   FROM revenue_entries          │
│   WHERE created_at >= 7 days ago│
│   GROUP BY paid_to_id,          │
│            payment_method       │
└──────┬──────────────────────────┘
       │
       │ Returns: [(staff_id, method, count), ...]
       │
       ▼
┌─────────────────────────────────┐
│   Revenue Cog                   │
│   Format the data               │
│   • Group by staff              │
│   • Calculate totals            │
│   • Build embed                 │
└──────┬──────────────────────────┘
       │
       │ Beautiful formatted report
       │
       ▼
┌─────────────────────────────────┐
│   Discord Message               │
│   🐰 WEEKLY REVENUE REPORT 🐰   │
│                                 │
│   📊 Total: 47                  │
│                                 │
│   › Roger                       │
│     • portal: 12                │
│     • cashapp: 5                │
│     Subtotal: 17                │
│                                 │
│   › Detrox                      │
│     • tiger: 15                 │
│     • portal: 8                 │
│     Subtotal: 23                │
└─────────────────────────────────┘
```

---

## 4️⃣ Data Storage Flow

```
┌─────────────────────────────────┐
│   Revenue Report Posted         │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│   Validated & Parsed            │
│   • user_id: 123456             │
│   • service: "shark trial"      │
│   • payment: "portal"           │
│   • paid_to_id: 789012          │
│   • recorded_by: (poster_id)    │
│   • timestamp: 2026-08-15...    │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│   bot_data.db (SQLite)          │
│   Table: revenue_entries        │
│                                 │
│   ┌──────────────────────────┐ │
│   │ id | guild_id | user_id  │ │
│   ├────┼──────────┼──────────┤ │
│   │ 1  │ 555555   │ 123456   │ │
│   │ 2  │ 555555   │ 789012   │ │
│   │ 3  │ 555555   │ 345678   │ │
│   └────┴──────────┴──────────┘ │
│                                 │
│   ┌──────────────────────────┐ │
│   │ service | payment | ... │ │
│   ├─────────┼─────────┼─────┤ │
│   │ shark   │ portal  │ ... │ │
│   │ tiger   │ cashapp │ ... │ │
│   │ dragon  │ portal  │ ... │ │
│   └─────────┴─────────┴─────┘ │
└─────────────────────────────────┘
       │
       │ Stored on YOUR PC
       │ File: bot_data.db
       │
       ▼
┌─────────────────────────────────┐
│   Accessible via:               │
│   • ?weekrevenue (bot commands) │
│   • DB Browser for SQLite       │
│   • Python scripts              │
│   • SQL queries                 │
└─────────────────────────────────┘
```

---

## 5️⃣ Error Handling Flow

```
┌──────────────┐
│   Staff      │
└──────┬───────┘
       │
       │ Posts WRONG format:
       │ User HINATA          (❌ missing @)
       │ Service: trial
       │ Payment: portal
       │ Staff: Roger         (❌ wrong field name)
       │
       ▼
┌─────────────────────────────────┐
│   Revenue Cog                   │
│   validate_and_record_revenue() │
└──────┬──────────────────────────┘
       │
       │ Regex pattern match fails
       │
       ▼
┌─────────────────────────────────┐
│   Error Response                │
│                                 │
│   ❌ @Staff Invalid format!     │
│                                 │
│   **Correct Format:**           │
│   User : @mention               │
│   Service : name                │
│   Payment : method              │
│   Paid to : @staff              │
└──────┬──────────────────────────┘
       │
       ├─────────────┬─────────────┐
       │             │             │
       ▼             ▼             ▼
   Delete        Send Error    Auto-delete
   Original      Message       after 15s
   Message                     
       │             │             │
       └─────────────┴─────────────┘
                     │
                     ▼
┌─────────────────────────────────┐
│   Staff sees error,             │
│   reposts with correct format   │
└─────────────────────────────────┘
```

---

## 6️⃣ Permission Flow

```
┌─────────────────────────────────┐
│   User Types Command            │
└──────┬──────────────────────────┘
       │
       ├──────────────┬──────────────┬──────────────┐
       │              │              │              │
       ▼              ▼              ▼              ▼
   ?weekrevenue  ?setrevenue  ?allrevenue    ?revenuehelp
   (Staff)       (Admin)      (Admin)        (Everyone)
       │              │              │              │
       ▼              ▼              ▼              ▼
   Check perms    Check perms  Check perms    No check
       │              │              │              │
       ▼              ▼              ▼              ▼
   Has mod role?  Has admin?   Has admin?     ✅ Allow
       │              │              │              
   ┌───┴───┐      ┌───┴───┐    ┌───┴───┐
   │       │      │       │    │       │
   ▼       ▼      ▼       ▼    ▼       ▼
  YES     NO     YES     NO   YES     NO
   │       │      │       │    │       │
   ▼       ▼      ▼       ▼    ▼       ▼
  ✅      ❌     ✅      ❌   ✅      ❌
  Run    Error   Run    Error Run    Error
```

---

## 7️⃣ Complete System Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                        DISCORD SERVER                          │
│                                                                │
│  ┌──────────────┐         ┌──────────────┐                   │
│  │   Staff      │         │   Admin      │                   │
│  │   Members    │         │              │                   │
│  └──────┬───────┘         └──────┬───────┘                   │
│         │                        │                            │
│         │ Post Revenue           │ Setup                      │
│         ▼                        ▼                            │
│  ┌─────────────────────────────────────────┐                 │
│  │     #revenue-reports channel            │                 │
│  └──────┬──────────────────────────────────┘                 │
└─────────┼─────────────────────────────────────────────────────┘
          │
          │ Messages flow to bot
          │
          ▼
┌───────────────────────────────────────────────────────────────┐
│                     UNITED BUNNIES BOT                         │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │              bot/events.py                              │  │
│  │         on_message() handler                            │  │
│  └──────┬──────────────────────────────────────────────────┘  │
│         │                                                      │
│         ▼                                                      │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │           bot/cogs/revenue.py                           │  │
│  │     validate_and_record_revenue()                       │  │
│  │     • Validate format                                   │  │
│  │     • Parse data                                        │  │
│  │     • Store in DB                                       │  │
│  │     • Generate reports                                  │  │
│  └──────┬──────────────────────────────────────────────────┘  │
│         │                                                      │
│         ▼                                                      │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │           bot/database.py                               │  │
│  │     • add_revenue_entry()                               │  │
│  │     • get_revenue_entries()                             │  │
│  │     • get_revenue_summary_by_staff()                    │  │
│  │     • set_revenue_channel()                             │  │
│  └──────┬──────────────────────────────────────────────────┘  │
└─────────┼─────────────────────────────────────────────────────┘
          │
          │ SQLite operations
          │
          ▼
┌───────────────────────────────────────────────────────────────┐
│                     YOUR PC (Local Storage)                    │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │               bot_data.db (SQLite)                      │  │
│  │                                                         │  │
│  │   ┌─────────────────────────────────────────────┐      │  │
│  │   │   Table: revenue_entries                    │      │  │
│  │   │   • id                                      │      │  │
│  │   │   • guild_id                                │      │  │
│  │   │   • user_id                                 │      │  │
│  │   │   • service                                 │      │  │
│  │   │   • payment_method                          │      │  │
│  │   │   • paid_to_id                              │      │  │
│  │   │   • recorded_by_id                          │      │  │
│  │   │   • created_at                              │      │  │
│  │   └─────────────────────────────────────────────┘      │  │
│  │                                                         │  │
│  │   ┌─────────────────────────────────────────────┐      │  │
│  │   │   Table: server_config                      │      │  │
│  │   │   • guild_id                                │      │  │
│  │   │   • revenue_channel_id (NEW!)               │      │  │
│  │   │   • welcome_channel_id                      │      │  │
│  │   │   • log_channel_id                          │      │  │
│  │   │   • ... (other config)                      │      │  │
│  │   └─────────────────────────────────────────────┘      │  │
│  │                                                         │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                │
│  Access Methods:                                               │
│  • DB Browser for SQLite (GUI)                                 │
│  • Python scripts                                              │
│  • SQL queries                                                 │
│  • Backup: Copy .db file                                       │
└───────────────────────────────────────────────────────────────┘
```

---

## 8️⃣ Commands & Their Actions

```
?setrevenuechannel #channel
    ↓
set_revenue_channel(guild_id, channel_id)
    ↓
UPDATE server_config SET revenue_channel_id = ?
    ↓
✅ Revenue Tracking Enabled

─────────────────────────────────

?weekrevenue
    ↓
get_revenue_summary_by_staff(guild_id, days=7)
    ↓
SELECT paid_to_id, payment_method, COUNT(*)
FROM revenue_entries
WHERE created_at >= 7 days ago
GROUP BY paid_to_id, payment_method
    ↓
Format data → Build embed → Send to Discord
    ↓
🐰 WEEKLY REVENUE REPORT 🐰

─────────────────────────────────

?revenuedetails 7
    ↓
get_revenue_entries(guild_id, days=7)
    ↓
SELECT user_id, service, payment_method, paid_to_id, created_at
FROM revenue_entries
WHERE created_at >= 7 days ago
ORDER BY created_at DESC
LIMIT 10
    ↓
Format data → Build embed → Send to Discord
    ↓
📊 Last 10 Entries (Past 7 Days)
```

---

## 🎯 Key Takeaways

1. **Setup**: Admin sets channel once
2. **Daily Use**: Staff posts formatted reports
3. **Validation**: Bot checks format automatically
4. **Storage**: SQLite database on your PC
5. **Reports**: Commands generate beautiful summaries
6. **Backup**: Just copy the `.db` file

**Everything flows through the bot → Stored locally → Accessible anytime!**
