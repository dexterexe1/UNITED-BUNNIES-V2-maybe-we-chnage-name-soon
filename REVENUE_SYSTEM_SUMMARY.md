# 💰 Revenue Tracking System - Quick Summary

## What Was Added

A complete automatic revenue tracking system for your service server that:
- ✅ Monitors a designated channel for revenue reports
- ✅ Validates format and rejects invalid entries
- ✅ Stores all data in SQLite on your PC (`bot_data.db`)
- ✅ Generates weekly/monthly/daily reports
- ✅ Groups revenue by staff member and payment method

---

## Files Created/Modified

### New Files:
1. **`bot/cogs/revenue.py`** - Complete revenue tracking cog (287 lines)
2. **`REVENUE_SYSTEM_GUIDE.md`** - Full documentation
3. **`REVENUE_SYSTEM_SUMMARY.md`** - This file

### Modified Files:
1. **`bot/database.py`**
   - Added `revenue_entries` table
   - Added `revenue_channel_id` column to `server_config`
   - Added 7 new database functions for revenue tracking

2. **`bot/main.py`**
   - Imported `bot.cogs.revenue` to register commands

3. **`bot/events.py`**
   - Added revenue validation at the start of `on_message()`
   - Checks revenue reports BEFORE any other processing

---

## How It Works

### 1️⃣ Setup (One Time)
```
?setrevenuechannel #revenue-reports
```

### 2️⃣ Staff Posts Revenue
In the designated channel, post using this EXACT format:
```
User : @HINATA
Service : 1 shark trial
Payment : portal
Paid to : @Roger
```

### 3️⃣ Bot Validates & Stores
- ✅ Correct format → Reacts with ✅💰 and saves to database
- ❌ Wrong format → Pings user, shows correct format, deletes after 15 seconds

### 4️⃣ View Reports
```
?weekrevenue    # Last 7 days
?monthrevenue   # Last 30 days
?todayrevenue   # Today only
?allrevenue     # All-time (admin only)
```

---

## Commands Reference

### Staff Commands:
- `?weekrevenue` / `?week` - Weekly summary grouped by staff
- `?monthrevenue` / `?month` - Monthly summary
- `?todayrevenue` / `?today` - Today's revenue
- `?revenuedetails [days]` - Last 10 detailed entries
- `?revenuehelp` - Show help

### Admin Commands:
- `?setrevenuechannel #channel` - Enable tracking
- `?clearrevenuechannel` - Disable tracking
- `?allrevenue` - All-time stats

---

## Example Report Output

```
🐰 WEEKLY REVENUE REPORT 🐰

📊 Total Transactions: 47

› Roger
   • portal: 12 transactions
   • cashapp: 5 transactions
   **Subtotal:** 17 transactions

› Detrox
   • tiger: 15 transactions
   • portal: 8 transactions
   **Subtotal:** 23 transactions

United Bunnies Revenue System • Generated at 2026-08-15 14:30 UTC
```

---

## Database Details

### Table: `revenue_entries`
```sql
CREATE TABLE revenue_entries (
    id INTEGER PRIMARY KEY,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    service TEXT NOT NULL,
    payment_method TEXT NOT NULL,
    paid_to_id INTEGER NOT NULL,
    recorded_by_id INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
```

### Location:
`bot_data.db` (in your bot's root folder)

### Access:
- Use [DB Browser for SQLite](https://sqlitebrowser.org/) to view/export data
- All data stays on your PC (no cloud services)
- Easy to backup: just copy the `.db` file

---

## Testing Instructions

1. **Start your bot**
   ```powershell
   python run_bot.py
   ```

2. **Setup revenue channel**
   ```
   ?setrevenuechannel #revenue-reports
   ```

3. **Post a test report** (in #revenue-reports):
   ```
   User : @YourUsername
   Service : Test Service
   Payment : test-payment
   Paid to : @StaffMember
   ```

4. **Check if recorded**
   ```
   ?todayrevenue
   ```

5. **View details**
   ```
   ?revenuedetails 1
   ```

---

## Format Validation Examples

### ✅ VALID:
```
User : @HINATA
Service : 1 shark trial
Payment : portal
Paid to : @Roger
```

### ✅ VALID (case insensitive):
```
user : @john
service : premium tiger
payment : cashapp
paid to : @detrox
```

### ❌ INVALID (missing @):
```
User : HINATA        ❌ needs @mention
Service : trial
Payment : portal
Paid to : Roger      ❌ needs @mention
```

### ❌ INVALID (wrong field names):
```
Customer : @User     ❌ must be "User"
Service : trial
Method : portal      ❌ must be "Payment"
Staff : @Roger       ❌ must be "Paid to"
```

---

## Key Features

### 🎯 Auto-Detection
- Bot monitors only the designated channel
- Validates every message against the format
- Non-command messages are checked automatically

### 🛡️ Format Enforcement
- Invalid formats get deleted after 15 seconds
- User is pinged with correct format example
- Prevents database pollution with bad data

### 📊 Smart Grouping
- Reports group by staff member
- Shows payment methods per staff
- Calculates subtotals automatically
- Tracks total transaction count

### 💾 Local Database
- All data stored in SQLite
- No external dependencies
- Easy backup (copy .db file)
- Queryable with standard SQL tools

---

## Permissions Required

### Bot Needs:
- ✅ Read Messages
- ✅ Send Messages
- ✅ Manage Messages (to delete invalid reports)
- ✅ Add Reactions (for confirmation)

### Users Need:
- **To view reports:** Mod role / Moderate Members permission
- **To configure:** Admin role / Manage Guild permission
- **To post reports:** None (anyone can post, bot validates)

---

## Backup Strategy

### Quick Backup:
```powershell
Copy-Item bot_data.db "bot_data_backup_$(Get-Date -Format 'yyyy-MM-dd').db"
```

### Automated Daily Backup:
Create `backup.ps1`:
```powershell
$date = Get-Date -Format "yyyy-MM-dd"
New-Item -ItemType Directory -Force -Path "backups"
Copy-Item bot_data.db "backups\bot_data_$date.db"
```

Run with Task Scheduler daily.

---

## Next Steps

1. ✅ **Setup the channel:** `?setrevenuechannel #revenue-reports`
2. ✅ **Test with a report:** Post a properly formatted entry
3. ✅ **View results:** `?weekrevenue`
4. ✅ **Train your staff:** Share the correct format
5. ✅ **Setup backups:** Copy `bot_data.db` regularly

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Bot doesn't react to reports | Check channel is set with `?revenuehelp` |
| Format keeps failing | Copy example EXACTLY, use real @mentions |
| Reports don't show in commands | Check `?revenuedetails 1` to verify storage |
| Can't access database | Close DB Browser, it locks the file |
| Need to delete an entry | Use DB Browser for SQLite to manually edit |

---

## Support Commands

```
?revenuehelp       # Show help in Discord
?weekrevenue       # Test the system
?revenuedetails 1  # Verify entries are storing
```

---

**Your revenue tracking system is ready to use! 🐰💰**

Read the full guide: `REVENUE_SYSTEM_GUIDE.md`
