# 🐰 United Bunnies Bot - Quick Reference Card

## 🚀 First Time Setup

```bash
# Start bot
python run_bot.py

# Make yourself owner
?addowner @YourName

# Enable revenue tracking
?setrevenuechannel #revenue-reports

# Check everything
?botstatus
```

---

## 💰 Revenue System

### Post Revenue:
```
User : CustomerName
Service : leopard
Payment : portal
Paid to : StaffName
Done by : Helper (optional)
```

### View Reports:
```
?weekrevenue          # Last 7 days
?monthrevenue         # Last 30 days
?todayrevenue         # Today
?revenuevia "Staff"   # Specific staff
?revenuedetails       # Last 10 transactions
```

### Report Shows:
```
› Roger (23 tickets done)

**Services:**
   • leopard: 8x
   • tiger: 6x

**💳 Payments:**
   • portal: 15x
   • cashapp: 8x
```

---

## 🔒 Bot Control

### Owner Management:
```
?addowner @user       # Add owner
?removeowner @user    # Remove owner
?listowners           # Show all
?owneronlymode        # Lock bot
?botstatus            # Check status
```

### Disable Commands:
```
?disablecommand marry server    # This server only
?disablecommand music global    # All servers
?enablecommand marry server     # Re-enable
?disabledcommands              # List disabled
```

### System Control:
```
?togglenoprefix       # Enable/disable no-prefix
?botstatus           # Show all settings
```

---

## 🎭 Role Information

```
?roles                  # List all roles
?roleinfo              # Top 10 roles with key perms
?roleinfo @Moderator   # Specific role key perms
?rolefullinfo @Admin   # Complete role details
```

---

## 💾 Database

**Location:**
```
[Bot Folder]\bot_data.db
```

**Access:**
1. Download: https://sqlitebrowser.org/
2. Open `bot_data.db`
3. Browse `revenue_entries` table

**Backup:**
```powershell
Copy-Item bot_data.db "bot_data_backup_$(Get-Date -Format 'yyyy-MM-dd').db"
```

---

## 📋 Command Categories

### Revenue (11):
`setrevenuechannel`, `clearrevenuechannel`, `weekrevenue`, `monthrevenue`, `todayrevenue`, `allrevenue`, `revenuevia`, `revenuedetails`, `revenuehelp`

### Bot Control (9):
`addowner`, `removeowner`, `listowners`, `owneronlymode`, `togglenoprefix`, `botstatus`, `disablecommand`, `enablecommand`, `disabledcommands`

### Role Info (4):
`roles`, `roleinfo`, `rolefullinfo`, `rolehelp`

### Plus All Existing:
Music, Tickets, Moderation, Marriage, Vouch, Applications, Community

---

## 🎯 Common Tasks

### Lock Bot to Yourself:
```
?addowner @You
?owneronlymode on
```

### Disable Problematic Command:
```
?disablecommand <commandname> server
```

### Check Staff Performance:
```
?revenuevia "StaffName"
```

### View Role Permissions:
```
?rolefullinfo @Moderator
```

### Weekly Team Meeting:
```
?weekrevenue
```

---

## ⚙️ Permissions

| Level | Can Do |
|-------|--------|
| **Owner** | Everything |
| **Admin** | Disable commands (server), all staff commands |
| **Mod** | Revenue setup/reports, role info |
| **Staff** | Revenue reports, role viewing |
| **Member** | Basic commands |

---

## 🐛 Troubleshooting

### Bot Not Responding:
```
?botstatus    # Check if owner-only mode is on
```

### Command Not Working:
```
?disabledcommands    # Check if disabled
```

### Revenue Not Saving:
- Check format exactly
- Each field on own line
- Restart bot (database changes)

### Database Locked:
- Close DB Browser
- Restart bot

---

## 📖 Full Guides

| Topic | File |
|-------|------|
| Revenue Setup | `REVENUE_QUICK_START.md` |
| Complete Revenue Guide | `REVENUE_SYSTEM_GUIDE.md` |
| Format Examples | `REVENUE_FORMAT_EXAMPLES.md` |
| Database Access | `DATABASE_PC_GUIDE.md` |
| All New Features | `NEW_FEATURES_ADDED.md` |
| Complete Summary | `COMPLETE_FEATURES_SUMMARY.md` |

---

## 🎉 Quick Tips

1. **@ is optional** - Use names or @mentions
2. **"Done by" is optional** - Add if multiple staff helped
3. **Services = what was sold** - leopard, tiger, etc.
4. **Payments = how they paid** - portal, cashapp, etc.
5. **Backup weekly** - Copy `bot_data.db`
6. **Check `?botstatus`** - Know your bot's state
7. **Use `?revenuevia`** - Check individual staff
8. **Pin format in channel** - Help staff remember

---

**Need Help?**
- Type `?revenuehelp` for revenue commands
- Type `?rolehelp` for role commands
- Type `?botstatus` to check bot state
- Read guides in documentation files

🐰 **United Bunnies Bot - Ready to use!** ✨
