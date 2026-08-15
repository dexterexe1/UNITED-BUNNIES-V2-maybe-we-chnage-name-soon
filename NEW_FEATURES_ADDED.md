# 🆕 New Features Added - Complete Summary

## Overview
Major enhancements to United Bunnies Bot with advanced control systems and role information commands.

---

## 1️⃣ Revenue System Improvements

### Flexible Format (@ Optional!)
**Old:** Required @mentions for User and Paid to  
**New:** Can use plain names OR @mentions

### Examples:
```
✅ With @mentions:
User : @HINATA
Service : shark trial
Payment : portal
Paid to : @Roger

✅ With plain names:
User : HINATA
Service : shark trial
Payment : portal
Paid to : Roger

✅ Mixed:
User : @HINATA
Service : shark trial  
Payment : portal
Paid to : Roger
```

### Staff Can Enable
- Changed from Admin-only to **Mod+** can setup revenue tracking
- `?setrevenuechannel` now requires Moderator permissions (not Administrator)

---

## 2️⃣ Bot Control System (NEW!)

### Owner-Only Mode 🔒
Lock the entire bot to specific users only.

**Commands:**
- `?addowner @user` - Add a bot owner
- `?removeowner @user` - Remove a bot owner
- `?listowners` - Show all bot owners
- `?owneronlymode [on/off]` - Toggle owner-only mode
- `?botstatus` - Show current bot control settings

**How It Works:**
1. Add yourself as owner: `?addowner @YourName`
2. Enable lock: `?owneronlymode on`
3. Now ONLY bot owners can use ANY command
4. Everyone else is denied access
5. Disable: `?owneronlymode off`

**Use Cases:**
- Maintenance mode
- Private bot setup
- Testing without interference
- Emergency lockdown

---

## 3️⃣ Command Disable System (NEW!)

### Per-Server Disabling
Admins can disable specific commands in their server.

**Commands:**
- `?disablecommand <command> server` - Disable in current server
- `?enablecommand <command> server` - Re-enable in current server
- `?disabledcommands` - List disabled commands

**Examples:**
```
?disablecommand marry server
```
Now `?marry` won't work in this server.

```
?enablecommand marry server
```
Re-enable the command.

### Global Disabling
Bot owners can disable commands across ALL servers.

**Commands:**
- `?disablecommand <command> global` - Disable globally
- `?enablecommand <command> global` - Re-enable globally

**Examples:**
```
?disablecommand music global
```
Disables ALL music commands globally.

```
?disabledcommands
```
Shows both server and global disabled commands.

---

## 4️⃣ No-Prefix System Toggle (NEW!)

### Global Control
Bot owners can now disable the no-prefix system entirely.

**Command:**
```
?togglenoprefix [on/off]
```

**How It Works:**
- **ON (default):** Trusted users can run commands without `?`
- **OFF:** Everyone MUST use `?` prefix, no exceptions

**Example:**
```
?togglenoprefix off
```
Now even staff must type `?warn @user` instead of just `warn @user`

```
?togglenoprefix on
```
Re-enable no-prefix for trusted users.

---

## 5️⃣ Role Information Commands (NEW!)

### Three Levels of Detail

#### Level 1: `?roles` - Simple List
Shows all server roles with member counts.

**Example Output:**
```
🐰 SERVER ROLES (15 total)

1. @Admin • 3 members
2. @Moderator • 8 members
3. @Staff • 15 members
4. @VIP • 42 members
...
```

**Usage:**
```
?roles
```

---

#### Level 2: `?roleinfo` - Key Permissions
Shows roles with their important permissions (short format).

**Example Output:**
```
🐰 ROLE INFORMATION

**@Moderator**
  › Members: 8
  › Color: #5865F2
  › Perms: 🔨 Ban 👢 Kick 🔇 Timeout 🗑️ Manage Messages 📢 Mention Everyone

**@Staff**
  › Members: 15
  › Color: #57F287
  › Perms: 🗑️ Manage Messages 🔇 Timeout
```

**Usage:**
```
?roleinfo              # Show top 10 roles
?roleinfo @Moderator   # Show specific role
```

---

#### Level 3: `?rolefullinfo` - Complete Details
Shows EVERYTHING about a role including ALL permissions with full descriptions.

**Example Output:**
```
🔍 COMPLETE ROLE INFORMATION
Role: @Moderator

📊 Basic Information
• Name: Moderator
• ID: 123456789
• Members: 8
• Color: #5865F2
• Position: 5/20
• Mentionable: Yes
• Display Separately: Yes

⚙️ Administrative Permissions
• View Audit Log - See server audit logs and moderation actions

🛡️ Moderation Permissions
• Ban Members - Permanently ban members from the server
• Kick Members - Remove members from the server (they can rejoin)
• Moderate Members - Timeout members (prevent them from interacting)
• Manage Messages - Delete messages and pin messages

💬 Text Channel Permissions
• Send Messages - Send messages in text channels
• Manage Messages - Delete messages and pin messages
• Embed Links - Preview links with embeds
• Attach Files - Upload files and media to channels
... (and more)

🔊 Voice Channel Permissions
• Connect to Voice - Join voice channels
• Speak in Voice - Talk in voice channels
• Mute Members - Server mute members in voice
... (and more)

👥 Members (8 total)
@User1, @User2, @User3, ... and 5 more

Role created: 2024-01-15 14:30 UTC
```

**Usage:**
```
?rolefullinfo @Moderator
```

---

## 📊 Command Summary

### Bot Control Commands (Owner Only)
| Command | Description |
|---------|-------------|
| `?addowner @user` | Add a bot owner |
| `?removeowner @user` | Remove a bot owner |
| `?listowners` | List all bot owners |
| `?owneronlymode [on/off]` | Toggle owner-only mode |
| `?togglenoprefix [on/off]` | Toggle no-prefix system |
| `?botstatus` | Show bot control status |

### Command Management (Admin/Owner)
| Command | Description |
|---------|-------------|
| `?disablecommand <cmd> server` | Disable command in server |
| `?disablecommand <cmd> global` | Disable command globally |
| `?enablecommand <cmd> server` | Enable command in server |
| `?enablecommand <cmd> global` | Enable command globally |
| `?disabledcommands` | List disabled commands |

### Role Information (Staff Only)
| Command | Description |
|---------|-------------|
| `?roles` | Simple list of all roles |
| `?roleinfo [@role]` | Role info with key permissions |
| `?rolefullinfo @role` | Complete role details |
| `?rolehelp` | Show role command help |

### Revenue (Updated)
| Command | Description |
|---------|-------------|
| `?setrevenuechannel #ch` | Setup (Mod+, was Admin-only) |
| Revenue format | Now accepts plain names (no @ required) |

---

## 🗄️ Database Changes

### New Tables:
1. **bot_owners** - Stores bot owner user IDs
2. **bot_settings** - Stores bot-wide settings (owner-only mode, no-prefix toggle)

### Modified Tables:
1. **revenue_entries** - Added `user_name` and `paid_to_name` columns for plain name support

---

## 📁 Files Created

1. **`bot/cogs/bot_control.py`** (403 lines)
   - Owner-only mode system
   - Command disable/enable system
   - No-prefix toggle
   - Bot owner management

2. **`bot/cogs/role_info.py`** (487 lines)
   - `?roles` command
   - `?roleinfo` command
   - `?rolefullinfo` command
   - Permission descriptions and formatting

3. **`NEW_FEATURES_ADDED.md`** - This file

---

## 📝 Files Modified

1. **`bot/main.py`**
   - Imported `bot_control` cog
   - Imported `role_info` cog

2. **`bot/database.py`**
   - Added bot control functions
   - Modified revenue functions for name support
   - Added new tables

3. **`bot/cogs/revenue.py`**
   - Updated format to accept plain names
   - Changed permission from admin to mod
   - Updated regex pattern
   - Modified storage and display logic

4. **`bot/events.py`**
   - Added no-prefix system enable check

---

## 🚀 Quick Start Guide

### Setup Bot Owner (First Time)
```
?addowner @YourDiscordName
```

### Lock Bot to Yourself Only
```
?owneronlymode on
```

### Disable a Command in Your Server
```
?disablecommand marry server
```

### Disable No-Prefix System
```
?togglenoprefix off
```

### Check Role Information
```
?roles                  # List all
?roleinfo @Moderator    # Key perms
?rolefullinfo @Admin    # Full details
```

### Test Flexible Revenue Format
```
User : CustomerName
Service : test service
Payment : portal
Paid to : StaffName
```

---

## ⚙️ Use Cases

### Use Case 1: Private Bot Setup
```
1. ?addowner @YourID
2. ?owneronlymode on
3. Configure everything
4. ?owneronlymode off
5. Invite users
```

### Use Case 2: Disable Problematic Commands
```
# Server admin disables gambling commands
?disablecommand coinflip server
?disablecommand gamble server
```

### Use Case 3: Maintenance Mode
```
# Owner locks bot during updates
?owneronlymode on
# Do maintenance
?owneronlymode off
```

### Use Case 4: Check Staff Permissions
```
# View what permissions @Moderator has
?rolefullinfo @Moderator
```

### Use Case 5: Revenue Without Discord Mentions
```
# Staff can type names instead of @mentioning
User : John Doe
Service : Premium boost
Payment : cashapp
Paid to : Roger
```

---

## 🔒 Permission Requirements

### Bot Owner Commands
- Requires being in `bot_owners` table
- No Discord permissions needed
- Bypass all checks when owner-only mode is on

### Admin Commands (Server)
- `?disablecommand` / `?enablecommand` (server scope)
- Requires Administrator permission

### Mod Commands
- `?roles`, `?roleinfo`, `?rolefullinfo`
- `?setrevenuechannel` (updated from admin)
- Requires Moderate Members OR Manage Messages OR Kick/Ban permissions

---

## 🛠️ Configuration

### Check Current Status
```
?botstatus
```

**Output:**
```
🐰 BOT CONTROL STATUS

🔒 Owner-Only Mode: ENABLED
   Only bot owners can use commands

✅ No-Prefix System: ENABLED
   Trusted users can run commands without ?

👑 Bot Owners: 2
   • @You
   • @YourCoowner
```

### View Disabled Commands
```
?disabledcommands
```

**Output:**
```
🐰 DISABLED COMMANDS

🌐 Globally Disabled:
• music
• play
• skip

🏠 Disabled in This Server:
• marry
• divorce
```

---

## 📖 Documentation

### Bot Control
- See command help: `?help` (look for bot control section)
- Check status: `?botstatus`
- List owners: `?listowners`

### Role Info
- Show help: `?rolehelp`
- Quick start: `?roles` then `?roleinfo @role`

### Revenue
- Updated guide: `REVENUE_SYSTEM_GUIDE.md`
- New format examples showing plain names

---

## ⚠️ Important Notes

1. **Bot Owners vs Discord Owners**
   - Bot owners = Set via `?addowner`
   - Server owners = Discord server ownership
   - Different concepts!

2. **Owner-Only Mode**
   - When ON: Only bot owners can use ANY command
   - Staff/Admin permissions ignored
   - Use for maintenance only

3. **Command Disabling**
   - Global disabling overrides server settings
   - Core commands (help, ping) can't be disabled
   - Disabled commands still show in `?help`

4. **No-Prefix Toggle**
   - When OFF: All users need `?` prefix
   - When ON: Trusted users don't need prefix
   - Staff always affected by this

5. **Revenue Plain Names**
   - Names stored as text
   - Can't ping users later if using plain names
   - Use @mentions for Discord integration

---

## 🐛 Troubleshooting

### "Unauthorized" Error
- Check: Are you a bot owner? `?listowners`
- Add yourself: `?addowner @You`

### Commands Not Working
- Check: `?botstatus` - Is owner-only mode on?
- Check: `?disabledcommands` - Is command disabled?

### Can't Disable Command
- Global scope: Requires bot owner
- Server scope: Requires Administrator permission

### No-Prefix Not Working
- Check: `?botstatus` - Is it enabled?
- Check: Do you have no-prefix permission?

### Revenue Won't Accept Names
- Restart bot (database changes applied)
- Check format is exact (each field on new line)
- Try @mention format if issues persist

---

## ✅ Testing Checklist

- [ ] Add yourself as bot owner
- [ ] Test owner-only mode on/off
- [ ] Disable a command in server
- [ ] Disable a command globally
- [ ] List disabled commands
- [ ] Toggle no-prefix system
- [ ] Check bot status
- [ ] Test `?roles`
- [ ] Test `?roleinfo`
- [ ] Test `?rolefullinfo @role`
- [ ] Test revenue with plain names
- [ ] Test revenue with @mentions

---

**All features are live and ready to use! 🐰✨**

Quick start: `?addowner @You` then explore `?botstatus`
