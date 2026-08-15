# 🚀 Revenue System - Deployment Checklist

## ✅ Files Added/Modified

### New Files Created:
- ✅ `bot/cogs/revenue.py` - Revenue tracking system (287 lines)
- ✅ `REVENUE_SYSTEM_GUIDE.md` - Complete documentation
- ✅ `REVENUE_SYSTEM_SUMMARY.md` - Quick summary
- ✅ `REVENUE_QUICK_START.md` - 5-minute setup guide
- ✅ `REVENUE_FORMAT_EXAMPLES.md` - Visual format examples
- ✅ `REVENUE_DEPLOYMENT.md` - This file

### Files Modified:
- ✅ `bot/database.py` - Added revenue tables & functions
- ✅ `bot/main.py` - Imported revenue cog
- ✅ `bot/events.py` - Added revenue validation to on_message

---

## 📦 What's Included

### Features:
1. ✅ Auto-detect revenue reports in designated channel
2. ✅ Validate format and reject invalid entries
3. ✅ Store in SQLite database (`bot_data.db`)
4. ✅ Generate weekly/monthly/daily/all-time reports
5. ✅ Group by staff member and payment method
6. ✅ Detailed transaction history
7. ✅ Format help command

### Commands Added (10 total):
1. `?setrevenuechannel #channel` - Setup (Admin)
2. `?clearrevenuechannel` - Disable (Admin)
3. `?weekrevenue` - Weekly report (Staff)
4. `?monthrevenue` - Monthly report (Staff)
5. `?todayrevenue` - Daily report (Staff)
6. `?allrevenue` - All-time report (Admin)
7. `?revenuedetails [days]` - Transaction history (Staff)
8. `?revenuehelp` - Show help (Everyone)
9. `?week` - Alias for weekrevenue
10. `?month` - Alias for monthrevenue

### Database Changes:
- ✅ New table: `revenue_entries` (8 columns)
- ✅ New column: `revenue_channel_id` in `server_config`

---

## 🔧 Installation Steps

### 1. Verify Files Are In Place
```powershell
# Check if all files exist
Test-Path bot/cogs/revenue.py
Test-Path REVENUE_SYSTEM_GUIDE.md
Test-Path REVENUE_QUICK_START.md
```

### 2. Test Import (Optional)
```powershell
python -c "import bot.cogs.revenue; print('✅ Revenue cog imports successfully')"
```

### 3. Start Bot
```powershell
python run_bot.py
```

### 4. Verify Bot Starts
Look for:
```
✨ Success! United Bunnies is online.
📋 Prefix/hybrid commands loaded: [number should be 70+]
🔄 Successfully synced [number] slash commands globally!
```

### 5. Check Revenue Commands Loaded
In Discord:
```
?help
```
Scroll and look for revenue commands.

### 6. Setup Revenue Channel
```
?setrevenuechannel #revenue-reports
```

### 7. Test With Sample Report
In the revenue channel:
```
User : @YourName
Service : Test Service
Payment : test
Paid to : @StaffName
```

### 8. Verify Storage
```
?todayrevenue
```
Should show your test entry!

---

## 🎯 Post-Deployment Tasks

### For Admins:

1. **Create Revenue Channel**
   - Create a staff-only channel called `#revenue-reports`
   - Set permissions so only staff can post

2. **Setup Revenue Tracking**
   ```
   ?setrevenuechannel #revenue-reports
   ```

3. **Pin Format Template**
   - Post the format in the channel
   - Pin it so staff always see it

4. **Train Staff**
   - Share `REVENUE_QUICK_START.md` with staff
   - Do a test run with them
   - Show them `?revenuehelp`

5. **Setup Backups**
   - Create backup script for `bot_data.db`
   - Schedule it to run daily

### For Staff:

1. **Learn the Format**
   - Read `REVENUE_FORMAT_EXAMPLES.md`
   - Practice with test entries
   - Save the template somewhere

2. **Bookmark Commands**
   ```
   ?weekrevenue      # Weekly report
   ?monthrevenue     # Monthly report
   ?todayrevenue     # Today's report
   ?revenuedetails   # Transaction history
   ```

3. **Report Regularly**
   - Post revenue as services are completed
   - Don't batch them at end of day
   - Use exact format every time

---

## 📊 Testing Checklist

### Test 1: Setup
- [ ] `?setrevenuechannel #test` works
- [ ] Bot confirms with success message
- [ ] Channel is recorded in database

### Test 2: Valid Report
- [ ] Post correctly formatted report
- [ ] Bot reacts with ✅ and 💰
- [ ] No error messages appear

### Test 3: Invalid Report
- [ ] Post incorrectly formatted report
- [ ] Bot pings you with error
- [ ] Shows correct format
- [ ] Deletes messages after 15 seconds

### Test 4: Commands
- [ ] `?todayrevenue` shows test entry
- [ ] `?weekrevenue` shows test entry
- [ ] `?revenuedetails` shows test entry
- [ ] `?revenuehelp` displays help

### Test 5: Permissions
- [ ] Only staff can run revenue commands
- [ ] Only admins can setup/clear channel
- [ ] Anyone can post in revenue channel

### Test 6: Multiple Entries
- [ ] Post 3-5 different reports
- [ ] `?weekrevenue` groups by staff
- [ ] `?weekrevenue` shows payment methods
- [ ] Totals are calculated correctly

---

## 🐛 Troubleshooting

### Bot Won't Start
**Check:** Syntax errors in modified files
```powershell
python -m py_compile bot/cogs/revenue.py
python -m py_compile bot/database.py
python -m py_compile bot/events.py
```

### Revenue Commands Missing
**Check:** Is revenue cog imported in `bot/main.py`?
```python
import bot.cogs.revenue  # noqa: F401
```

### Bot Doesn't React to Reports
**Check:** 
1. Is channel set? `?revenuehelp`
2. Are you in the correct channel?
3. Is format exactly correct?
4. Does bot have permissions?

### Format Always Fails
**Check:**
1. Using actual @mentions (blue/clickable)?
2. Each field on its own line?
3. Using colon `:` not equals `=`?
4. All 4 fields present?

### Reports Don't Show in Commands
**Check:**
1. `?revenuedetails 1` to see if storing
2. Check console for errors
3. Verify `bot_data.db` exists
4. Check file permissions

### Database Errors
**Check:**
1. Close DB Browser if open (locks file)
2. Check `bot_data.db` is readable/writable
3. Delete and recreate database (loses data!)
4. Check disk space

---

## 📁 Backup Instructions

### Manual Backup
```powershell
# Create backups folder
New-Item -ItemType Directory -Force -Path "backups"

# Copy database with date
$date = Get-Date -Format "yyyy-MM-dd"
Copy-Item bot_data.db "backups\bot_data_$date.db"
```

### Automated Backup (Windows Task Scheduler)

1. **Create backup script** (`backup_revenue.ps1`):
```powershell
$date = Get-Date -Format "yyyy-MM-dd_HHmm"
$source = "C:\path\to\your\bot\bot_data.db"
$dest = "C:\path\to\your\bot\backups\bot_data_$date.db"

New-Item -ItemType Directory -Force -Path "C:\path\to\your\bot\backups"
Copy-Item $source $dest

# Keep only last 30 days
Get-ChildItem "C:\path\to\your\bot\backups" -Filter "bot_data_*.db" | 
    Where-Object { $_.CreationTime -lt (Get-Date).AddDays(-30) } | 
    Remove-Item
```

2. **Schedule it:**
   - Open Task Scheduler
   - Create Basic Task
   - Name: "Backup Bot Revenue Database"
   - Trigger: Daily at 11:59 PM
   - Action: Start a program
   - Program: `powershell.exe`
   - Arguments: `-File "C:\path\to\backup_revenue.ps1"`

---

## 🎉 Success Criteria

### ✅ Deployment Successful If:
1. Bot starts without errors
2. Revenue commands appear in `?help`
3. `?setrevenuechannel` works
4. Test report gets ✅💰 reaction
5. `?todayrevenue` shows test entry
6. Invalid format gets rejected
7. All 10 commands work correctly

### ✅ System Working If:
1. Staff can post reports daily
2. Invalid formats are rejected
3. `?weekrevenue` shows accurate data
4. Data persists across bot restarts
5. Database file grows with entries
6. No errors in console

---

## 📞 Support Resources

### Documentation Files:
- `REVENUE_QUICK_START.md` - Fast 5-minute setup
- `REVENUE_SYSTEM_GUIDE.md` - Complete documentation
- `REVENUE_FORMAT_EXAMPLES.md` - Visual examples
- `REVENUE_SYSTEM_SUMMARY.md` - Technical summary

### In-Discord Help:
```
?revenuehelp
```

### Database Tool:
[DB Browser for SQLite](https://sqlitebrowser.org/) - Free, open-source

---

## 🔄 Rollback Instructions

If something goes wrong and you need to undo:

### 1. Remove Revenue Cog
Edit `bot/main.py`, remove:
```python
import bot.cogs.revenue  # noqa: F401
```

### 2. Remove Revenue Validation
Edit `bot/events.py`, remove these lines from `on_message()`:
```python
# --- REVENUE TRACKING AUTO-DETECTION ---
try:
    from bot.cogs.revenue import validate_and_record_revenue
    if await validate_and_record_revenue(message):
        return
except Exception as e:
    print(f"⚠️ Revenue validation error: {e}")
```

### 3. Restart Bot
```powershell
python run_bot.py
```

Bot will work without revenue system. Database tables remain but unused.

---

## 📈 Future Enhancements

Planned features (not yet implemented):
- [ ] CSV export command
- [ ] Edit/delete revenue entries
- [ ] Service-specific reports
- [ ] Monthly comparison charts
- [ ] Revenue per staff detailed breakdown
- [ ] Dashboard integration
- [ ] Amount tracking ($ values)
- [ ] Commission calculations
- [ ] Revenue goals/targets

---

## ✅ Final Checklist

Before going live:
- [ ] All files in place
- [ ] Bot starts successfully
- [ ] Revenue commands work
- [ ] Format validation works
- [ ] Reports show correct data
- [ ] Staff trained on format
- [ ] Backup system configured
- [ ] Documentation distributed

---

**Your revenue tracking system is ready to deploy! 🐰💰**

Next step: `python run_bot.py` and `?setrevenuechannel #your-channel`
