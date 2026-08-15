# 💰 Revenue Tracking System - Complete Guide

## Overview
Automatic revenue tracking system for service servers. The bot monitors a designated channel, validates revenue reports, stores them in a local SQLite database, and generates beautiful formatted reports.

---

## 🎯 Features

### ✅ Auto-Detection & Validation
- Bot monitors specific channel for revenue reports
- Validates format automatically
- Pings staff if format is wrong and deletes invalid reports after 15 seconds
- Reacts with ✅ and 💰 when successfully recorded

### 📊 Comprehensive Reports
- **Daily Revenue** - Today's transactions
- **Weekly Revenue** - Last 7 days
- **Monthly Revenue** - Last 30 days  
- **All-Time Revenue** - Complete history
- **Detailed View** - Last 10 transactions with timestamps

### 💾 Local Database Storage
- All data stored in `bot_data.db` on your PC
- SQLite database (no external services needed)
- Persistent across bot restarts
- Can be backed up easily

---

## 🚀 Quick Setup

### 1. Enable Revenue Tracking
```
?setrevenuechannel #revenue-reports
```
This designates the channel where staff will post revenue reports.

### 2. Staff Posts Revenue Reports
Post in the designated channel using this **EXACT** format:
```
User : @HINATA
Service : 1 shark trial
Payment : portal
Paid to : @Roger
```

### 3. View Reports
```
?weekrevenue
?monthrevenue
?todayrevenue
```

---

## 📝 Correct Format

### Required Format (Case-Insensitive):
```
User : @username
Service : service_name
Payment : payment_method
Paid to : @staff_member
```

### ✅ Valid Examples:
```
User : @HINATA
Service : 1 shark trial
Payment : portal
Paid to : @Roger
```

```
user : @JohnDoe
service : Tiger premium
payment : cashapp
paid to : @Detrox
```

### ❌ Invalid Examples:
```
❌ Missing mentions:
User : HINATA (needs @)
Paid to : Roger (needs @)

❌ Wrong field names:
Customer : @User (must be "User")
Method : portal (must be "Payment")

❌ Missing fields:
User : @Someone
Service : Trial
(missing Payment and Paid to)
```

---

## 🎮 Commands

### 👨‍💼 Staff Commands (Requires Mod Role)

| Command | Aliases | Description |
|---------|---------|-------------|
| `?weekrevenue` | `?week`, `?weeklyrevenue` | 7-day revenue summary |
| `?monthrevenue` | `?month`, `?monthlyrevenue` | 30-day revenue summary |
| `?todayrevenue` | `?today`, `?dailyrevenue` | Today's revenue |
| `?revenuedetails [days]` | `?revdetails` | Last 10 transactions (default: 7 days) |
| `?revenuehelp` | `?revhelp` | Show revenue system help |

### 👑 Admin Commands (Requires Admin Role)

| Command | Description |
|---------|-------------|
| `?setrevenuechannel #channel` | Enable revenue tracking in a channel |
| `?clearrevenuechannel` | Disable revenue tracking |
| `?allrevenue` | All-time revenue summary |

---

## 📊 Report Format Example

### Command:
```
?weekrevenue
```

### Output:
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

› Sarah
   • paypal: 7 transactions
   **Subtotal:** 7 transactions

United Bunnies Revenue System • Generated at 2026-08-15 14:30 UTC
```

---

## 💾 Database & Backup

### Database Location
The revenue data is stored in:
```
bot_data.db
```
Located in your bot's root directory (same folder as `run_bot.py`)

### How to Backup
**Option 1: Copy the file**
```powershell
# On Windows PowerShell
Copy-Item bot_data.db bot_data_backup_$(Get-Date -Format 'yyyy-MM-dd').db
```

**Option 2: Scheduled Backup**
Create a backup script that runs daily:
```powershell
# backup_revenue.ps1
$date = Get-Date -Format "yyyy-MM-dd"
Copy-Item bot_data.db "backups\bot_data_$date.db"
```

### Connecting from Your PC
Since you're running the bot on your PC, you can:

1. **Direct Database Access:**
   - Use [DB Browser for SQLite](https://sqlitebrowser.org/) (free tool)
   - Open `bot_data.db`
   - View the `revenue_entries` table

2. **Export to Excel:**
   ```sql
   SELECT 
       datetime(created_at) as Date,
       service as Service,
       payment_method as Payment,
       paid_to_id as StaffID,
       user_id as UserID
   FROM revenue_entries
   WHERE guild_id = YOUR_SERVER_ID
   ORDER BY created_at DESC;
   ```

3. **Python Script for Analysis:**
   ```python
   import sqlite3
   import pandas as pd
   
   conn = sqlite3.connect('bot_data.db')
   df = pd.read_sql_query(
       "SELECT * FROM revenue_entries WHERE guild_id = ?",
       conn,
       params=(YOUR_SERVER_ID,)
   )
   df.to_excel('revenue_report.xlsx', index=False)
   conn.close()
   ```

---

## 🔒 Permissions

### Who Can View Reports?
- Staff members (anyone with Mod permissions)
- Configured trusted role
- Users with Moderate Members, Manage Messages, Kick, or Ban permissions

### Who Can Post Reports?
- Anyone can post in the revenue channel
- Bot validates format and only accepts correct entries
- Invalid formats are deleted automatically

### Who Can Configure?
- Server administrators only
- Users with Manage Guild or Manage Channels permissions

---

## 🛠️ Advanced Features

### Custom Date Ranges
Use `?revenuedetails` with custom days:
```
?revenuedetails 14    # Last 14 days
?revenuedetails 60    # Last 60 days
```

### Export Revenue Data
Access the database directly to export:
```sql
-- All revenue from August 2026
SELECT * FROM revenue_entries 
WHERE created_at LIKE '2026-08%'
ORDER BY created_at DESC;

-- Revenue by payment method
SELECT payment_method, COUNT(*) as count 
FROM revenue_entries 
GROUP BY payment_method 
ORDER BY count DESC;

-- Revenue by staff member
SELECT paid_to_id, COUNT(*) as count 
FROM revenue_entries 
GROUP BY paid_to_id 
ORDER BY count DESC;
```

---

## 🔧 Troubleshooting

### Bot Doesn't React to Reports
1. Check if revenue channel is set: `?revenuehelp`
2. Verify you're in the correct channel
3. Check bot has permissions: Send Messages, Add Reactions, Manage Messages
4. Verify format exactly matches the required template

### Format Keeps Getting Rejected
- Copy the example format EXACTLY
- Make sure to use actual @mentions (not just typing @name)
- Check for extra spaces or line breaks
- Each field must be on its own line
- Use `:` (colon) after field names

### Reports Don't Show Up
1. Check if entries were recorded: `?revenuedetails 1`
2. Verify the bot didn't crash (check console)
3. Make sure `bot_data.db` file exists
4. Check file permissions on the database

### Database Connection Issues
- Close DB Browser if you have it open (it locks the file)
- Check if `bot_data.db` is readable/writable
- Restart the bot to reset connections

---

## 📈 Use Cases

### 1. Weekly Staff Performance Review
```
?weekrevenue
```
See which staff processed the most transactions.

### 2. Payment Method Analysis
```
?monthrevenue
```
See which payment methods are most popular.

### 3. Daily Monitoring
```
?todayrevenue
```
Quick check on today's activity.

### 4. Audit Trail
```
?revenuedetails 30
```
Review recent transactions with full details.

---

## 🎨 Customization

### Change Validation Format
Edit `bot/cogs/revenue.py`:
```python
REVENUE_PATTERN = re.compile(
    r"User\s*:\s*<@!?(\d+)>.*?"
    r"Service\s*:\s*(.+?)(?:\n|$).*?"
    r"Payment\s*:\s*(.+?)(?:\n|$).*?"
    r"Paid\s*to\s*:\s*<@!?(\d+)>",
    re.IGNORECASE | re.DOTALL
)
```

### Add More Fields
Modify the database schema in `bot/database.py` `init_db()`:
```python
cursor.execute("""
CREATE TABLE IF NOT EXISTS revenue_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    service TEXT NOT NULL,
    payment_method TEXT NOT NULL,
    paid_to_id INTEGER NOT NULL,
    recorded_by_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    amount REAL DEFAULT 0.0,  -- Add amount field
    notes TEXT  -- Add notes field
)
""")
```

---

## 📞 Support

### Need Help?
Type `?revenuehelp` in your server for quick reference.

### Common Questions

**Q: Can I track multiple servers?**  
A: Yes! Each server has its own revenue data automatically separated by `guild_id`.

**Q: How far back can I see data?**  
A: Forever! Use `?allrevenue` to see all-time stats (admin only).

**Q: Can I delete entries?**  
A: Not via commands (by design to prevent tampering). Use DB Browser to manually remove if needed.

**Q: Does this work with the dashboard?**  
A: This is SQLite-only (no dashboard integration yet). Data stays on your PC.

---

## ✨ Features Coming Soon

- [ ] CSV export command
- [ ] Revenue per staff member detailed breakdown
- [ ] Service-specific reports
- [ ] Monthly comparison charts
- [ ] Edit/delete commands for admins
- [ ] Dashboard integration

---

**Your revenue tracking system is ready! 🐰💰**

Setup: `?setrevenuechannel #your-channel`  
Test: Post a revenue report  
View: `?weekrevenue`
