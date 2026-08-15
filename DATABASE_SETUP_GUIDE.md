# 🗄️ Database Setup Guide

Your bot now uses **TWO separate databases**:

1. **MongoDB** - Existing data (warnings, tickets, etc.) ✅ Keep unchanged
2. **Revenue SQLite** - New revenue data only 📊 Store on your PC

## 🖥️ Step 1: Setup Revenue Database on Your PC

### Download and Run Setup Script

1. **On your PC**, navigate to the bot folder:
   ```bash
   cd "C:\Users\muphi\Downloads\UNITED-BUNNIES-V2-maybe-we-chnage-name-soon-main\UNITED-BUNNIES-V2-maybe-we-chnage-name-soon"
   ```

2. **Run the setup script:**
   ```bash
   python setup_pc_revenue_db.py
   ```

3. **This creates the database at:**
   ```
   C:\Users\muphi\UnitedBunniesBot\revenue_data.db
   ```

## 🌐 Step 2: Connect Bot to Your PC (Choose One)

### Option A: ngrok (Recommended - Easy Setup)

1. **Download ngrok:** https://ngrok.com/download
2. **Extract it** to a folder (e.g., `C:\ngrok\`)
3. **Open Command Prompt** and run:
   ```bash
   cd C:\ngrok
   ngrok http file://C:\Users\muphi\UnitedBunniesBot\
   ```
4. **Copy the public URL** (e.g., `https://abc123.ngrok.io`)

### Option B: Use Free Remote Database (Easier Alternative)

If connecting to your PC is too complex:

1. **Go to Supabase:** https://supabase.com/
2. **Create free account** (500MB free)
3. **Create new project**
4. **Copy the connection URL**

## ☁️ Step 3: Configure Render (Your Cloud Bot)

### Add Environment Variables

1. **Go to your Render dashboard**
2. **Click your service** → **Environment**
3. **Add these variables:**

**If using ngrok (PC connection):**
```bash
REVENUE_DB_PATH=C:\Users\muphi\UnitedBunniesBot\revenue_data.db
REVENUE_DB_HOST=https://your-ngrok-url.ngrok.io
```

**If using Supabase (remote):**
```bash
REVENUE_DB_URL=postgresql://your-supabase-connection-string
```

4. **Redeploy your bot** (Render will restart automatically)

## 🧪 Step 4: Test the Setup

### 4.1 Test Bot Permissions (New Dyno-like System)

Your bot now uses **Discord permissions** instead of hardcoded roles:

| Command Type | Required Permission |
|-------------|-------------------|
| Basic mod (`?warn`, `?mute`) | **Moderate Members** OR **Manage Messages** |
| Kick commands | **Kick Members** |
| Ban commands | **Ban Members** |
| Admin setup | **Manage Server** |

**To give someone mod access:**
1. **Create a role** (e.g., "Moderator")
2. **Give the role** → **Moderate Members** permission
3. **Assign role to user** ✅ They can now use mod commands

### 4.2 Test Revenue Tracking

1. **Set revenue channel:**
   ```
   ?setrevenuechannel #revenue-reports
   ```

2. **Post a test report:**
   ```
   User : TestUser
   Service : leopard  
   Payment : portal
   Paid to : YourName
   ```

3. **Check if it worked:**
   ```
   ?todayrevenue
   ```

4. **Verify on your PC:**
   - Check if `C:\Users\muphi\UnitedBunniesBot\revenue_data.db` exists
   - File should contain the test entry

## 🔧 Troubleshooting

### Bot Commands Not Working
**Problem:** "You need moderation permissions"
**Solution:** 
- Give users **Moderate Members** OR **Manage Messages** permission
- No specific role required anymore

### Revenue Database Not Connecting
**Problem:** Revenue reports not saving
**Solutions:**
1. **Check ngrok is running** (if using PC connection)
2. **Verify environment variables** on Render
3. **Check bot logs** for database errors
4. **Try Supabase** instead (easier setup)

### Database File Not Found
**Problem:** Can't find revenue_data.db
**Solution:** 
1. **Run setup script again:** `python setup_pc_revenue_db.py`
2. **Check file path** is correct in Render environment variables

## 📊 How It All Works

```
Discord Server
      ↓
   Your Bot (Render)
      ↓
  ┌─────────────────┐
  │    MongoDB      │ ← Warnings, tickets, etc.
  │   (unchanged)   │
  └─────────────────┘
      ↓
  ┌─────────────────┐
  │  Revenue DB     │ ← Revenue data only
  │  (on your PC)   │ ← You control this!
  └─────────────────┘
```

## 🎯 Quick Start Commands

Once setup is complete:

```bash
# Set your Discord ID as bot owner
?addrevenuemanager @YourDiscordName

# Setup revenue tracking  
?setrevenuechannel #revenue-reports

# Test a report
User : TestUser
Service : leopard
Payment : portal  
Paid to : Staff

# Check reports
?todayrevenue
?weekrevenue
?monthrevenue
```

## ✅ Success Checklist

- [ ] Revenue database created on PC
- [ ] ngrok or Supabase configured  
- [ ] Environment variables added to Render
- [ ] Bot redeployed
- [ ] Permission system tested (no more role requirements)
- [ ] Revenue tracking tested and working
- [ ] Your Discord ID added as bot owner

Need help? The new system is much cleaner - no hardcoded roles, just Discord permissions like Dyno! 🎉