# Revenue Database Setup Guide

The revenue tracking system uses a **separate SQLite database** that can be stored on your PC while other bot data remains in MongoDB.

## 🖥️ Option 1: Database on Your PC (Recommended)

### Step 1: Set Up Database on Your PC

1. **Run the setup script on your PC:**
   ```bash
   python setup_pc_revenue_db.py
   ```

2. **This creates:**
   - Database file at: `C:\Users\YourName\UnitedBunniesBot\revenue_data.db`
   - All revenue data will be stored here

### Step 2: Connect Bot to Your PC

**Option A: Use ngrok (Easiest)**
1. Download ngrok: https://ngrok.com/download
2. Run: `ngrok http 8000` (or any port)
3. Copy the public URL (e.g., `https://abc123.ngrok.io`)

**Option B: Port Forwarding**
1. Set up port forwarding on your router
2. Forward port 8000 to your PC's local IP
3. Use your public IP address

### Step 3: Configure Render Environment Variables

Add these to your Render service:

```bash
REVENUE_DB_PATH=C:\Users\YourName\UnitedBunniesBot\revenue_data.db
REVENUE_DB_HOST=your_ngrok_url_or_public_ip
```

## 🌐 Option 2: Free Remote Database (Alternative)

If connecting to your PC is complex, use a free remote service:

### Supabase (Recommended)
1. Go to https://supabase.com/
2. Create free account (500MB)
3. Create new project
4. Copy connection string
5. Add to Render: `REVENUE_DB_URL=postgresql://...`

### Railway
1. Go to https://railway.app/
2. Create free PostgreSQL database (1GB)
3. Copy connection string
4. Add to Render: `REVENUE_DB_URL=postgresql://...`

## 📊 How It Works

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Discord Bot   │    │     MongoDB      │    │  Revenue DB     │
│  (on Render)    │───▶│ (warnings, etc.) │    │  (on your PC)   │
│                 │    │                  │    │                 │
│  Revenue Data   │────┼──────────────────┼───▶│  - Revenue      │
│  Only           │    │                  │    │  - Reports      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🔧 Testing the Setup

1. **Set revenue channel:** `?setrevenuechannel #revenue`
2. **Post test report:**
   ```
   User : TestUser
   Service : leopard
   Payment : portal
   Paid to : YourName
   ```
3. **Check report:** `?todayrevenue`
4. **Verify database:** Check your PC's database file for the entry

## 🚨 Troubleshooting

**Bot can't connect to database:**
- Check ngrok is running
- Verify Render environment variables
- Check firewall settings

**Database file not found:**
- Run `setup_pc_revenue_db.py` first
- Verify file path in environment variable

**Revenue reports not working:**
- Check `?setrevenuechannel` was run
- Verify message format matches exactly
- Check bot has permission to read messages