# 💰 Revenue System - Quick Start (5 Minutes)

## Step 1: Start Your Bot
```powershell
python run_bot.py
```

## Step 2: Setup Revenue Channel (Admin Only)
In Discord, type:
```
?setrevenuechannel #revenue-reports
```
Replace `#revenue-reports` with your actual channel.

## Step 3: Test It!
In the revenue channel you just set, post this exact message:
```
User : @YourName
Service : Test Service
Payment : test-method
Paid to : @StaffMember
```

✅ Bot should react with ✅ and 💰

## Step 4: View Report
```
?todayrevenue
```

You should see your test entry!

---

## ✅ Daily Usage

### Staff Posts Revenue:
```
User : @CustomerName
Service : 1 shark trial
Payment : portal
Paid to : @StaffName
```

### View Weekly Report:
```
?weekrevenue
```

### View Monthly Report:
```
?monthrevenue
```

---

## 📋 Format Must Be EXACT

**Field Names (case-insensitive):**
- `User :` (must use @mention)
- `Service :`
- `Payment :`
- `Paid to :` (must use @mention)

**Each field on its own line!**

---

## ⚠️ Common Mistakes

❌ **Missing @ symbol**
```
User : John          ← WRONG
User : @John         ← CORRECT
```

❌ **Wrong field name**
```
Customer : @John     ← WRONG
User : @John         ← CORRECT
```

❌ **Missing fields**
```
User : @John
Service : Trial      ← WRONG (missing Payment and Paid to)
```

---

## 🎯 All Commands

```
?weekrevenue              # Weekly report
?monthrevenue             # Monthly report
?todayrevenue             # Today's report
?revenuedetails 7         # Last 10 entries (7 days)
?revenuehelp              # Show help

?setrevenuechannel #ch    # Admin: Setup
?clearrevenuechannel      # Admin: Disable
?allrevenue               # Admin: All-time stats
```

---

## 💡 Tips

1. **Pin the format** in your revenue channel
2. **Train your staff** on the exact format
3. **Bot auto-deletes** invalid reports after 15 seconds
4. **Data is saved** in `bot_data.db` on your PC
5. **Backup regularly** by copying `bot_data.db`

---

## 🔧 Need Help?

Type in Discord: `?revenuehelp`

Read full guide: `REVENUE_SYSTEM_GUIDE.md`

---

**That's it! Your revenue tracking is ready! 🐰💰**
