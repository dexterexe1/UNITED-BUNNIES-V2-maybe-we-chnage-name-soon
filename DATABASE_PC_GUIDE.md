# 💾 Database PC Connection Guide

## Overview
Your bot stores ALL data locally in `bot_data.db` on your PC. You can access, view, edit, and backup this data easily.

---

## 📍 Database Location

The database file is located at:
```
C:\Users\muphi\Downloads\UNITED-BUNNIES-V2-maybe-we-chnage-name-soon-main\UNITED-BUNNIES-V2-maybe-we-chnage-name-soon\bot_data.db
```

Or simply:
```
[Your Bot Folder]\bot_data.db
```

---

## 🔧 Method 1: DB Browser for SQLite (Recommended)

### Download & Install:
1. Go to: https://sqlitebrowser.org/
2. Download "DB Browser for SQLite" (FREE)
3. Install it on your PC

### Open Your Database:
1. Launch DB Browser for SQLite
2. Click **"Open Database"**
3. Navigate to your bot folder
4. Select `bot_data.db`
5. Done! You can now see all your data

### View Revenue Data:
1. Click **"Browse Data"** tab
2. Select **"revenue_entries"** table from dropdown
3. You'll see all revenue records!

### Columns in revenue_entries:
- `id` - Unique ID for each entry
- `guild_id` - Server ID
- `user_id` - Customer Discord ID (or 0 if plain name)
- `user_name` - Customer name
- `service` - Service provided (e.g., "tiger", "leopard")
- `payment_method` - Payment method used
- `paid_to_id` - Staff Discord ID (or 0 if plain name)
- `paid_to_name` - Staff name
- `recorded_by_id` - Who posted the report
- `created_at` - Timestamp

### Export to Excel/CSV:
1. Right-click on the table
2. Select **"Export to CSV"**
3. Choose location and filename
4. Open in Excel!

---

## 🔧 Method 2: Python Script (Advanced)

### View Revenue Data:
Create a file `view_revenue.py`:

```python
import sqlite3
import pandas as pd

# Connect to database
conn = sqlite3.connect('bot_data.db')

# Query revenue data
query = """
SELECT 
    user_name as Customer,
    service as Service,
    payment_method as Payment,
    paid_to_name as Staff,
    created_at as Date
FROM revenue_entries
WHERE guild_id = YOUR_SERVER_ID_HERE
ORDER BY created_at DESC
"""

# Load into pandas DataFrame
df = pd.read_sql_query(query, conn)

# Display
print(df)

# Export to Excel
df.to_excel('revenue_report.xlsx', index=False)

conn.close()
print("✅ Exported to revenue_report.xlsx")
```

### Run it:
```powershell
python view_revenue.py
```

### Get Staff Summary:
Create `staff_summary.py`:

```python
import sqlite3

conn = sqlite3.connect('bot_data.db')
cursor = conn.cursor()

# Get revenue by staff
cursor.execute("""
SELECT 
    paid_to_name as Staff,
    service as Service,
    COUNT(*) as Count
FROM revenue_entries
WHERE guild_id = YOUR_SERVER_ID_HERE
GROUP BY paid_to_name, service
ORDER BY paid_to_name, Count DESC
""")

print("📊 STAFF REVENUE SUMMARY\n")
print(f"{'Staff':<20} {'Service':<30} {'Count':<10}")
print("=" * 60)

for staff, service, count in cursor.fetchall():
    print(f"{staff:<20} {service:<30} {count:<10}")

conn.close()
```

---

## 🔧 Method 3: PowerShell Quick View

### View Last 10 Entries:
```powershell
sqlite3 bot_data.db "SELECT user_name, service, paid_to_name, created_at FROM revenue_entries ORDER BY created_at DESC LIMIT 10"
```

### Count Total Entries:
```powershell
sqlite3 bot_data.db "SELECT COUNT(*) FROM revenue_entries"
```

### Staff Totals:
```powershell
sqlite3 bot_data.db "SELECT paid_to_name, COUNT(*) FROM revenue_entries GROUP BY paid_to_name"
```

---

## 💾 Backup Your Database

### Manual Backup:
```powershell
# Copy with date stamp
Copy-Item bot_data.db "bot_data_backup_$(Get-Date -Format 'yyyy-MM-dd').db"
```

### Automated Daily Backup:
Create `backup.ps1`:

```powershell
# Configuration
$botFolder = "C:\Users\muphi\Downloads\UNITED-BUNNIES-V2-maybe-we-chnage-name-soon-main\UNITED-BUNNIES-V2-maybe-we-chnage-name-soon"
$backupFolder = "$botFolder\backups"
$date = Get-Date -Format "yyyy-MM-dd_HHmm"

# Create backup folder if it doesn't exist
New-Item -ItemType Directory -Force -Path $backupFolder | Out-Null

# Copy database
Copy-Item "$botFolder\bot_data.db" "$backupFolder\bot_data_$date.db"

Write-Host "✅ Backup created: bot_data_$date.db"

# Keep only last 30 days
Get-ChildItem $backupFolder -Filter "bot_data_*.db" | 
    Where-Object { $_.CreationTime -lt (Get-Date).AddDays(-30) } | 
    Remove-Item

Write-Host "✅ Old backups cleaned (kept last 30 days)"
```

### Schedule It (Windows Task Scheduler):
1. Open **Task Scheduler**
2. Create Basic Task → Name it "Backup Bot Database"
3. Trigger: **Daily** at 11:59 PM
4. Action: **Start a program**
   - Program: `powershell.exe`
   - Arguments: `-File "C:\path\to\backup.ps1"`
5. Done! Auto-backup every day

---

## 📊 Common Queries

### Get All Services by Staff:
```sql
SELECT 
    paid_to_name as Staff,
    service as Service,
    COUNT(*) as Sales
FROM revenue_entries
WHERE guild_id = YOUR_SERVER_ID
GROUP BY paid_to_name, service
ORDER BY paid_to_name, Sales DESC;
```

### Revenue for Specific Date Range:
```sql
SELECT 
    paid_to_name as Staff,
    COUNT(*) as Sales
FROM revenue_entries
WHERE guild_id = YOUR_SERVER_ID
  AND created_at >= '2026-08-01'
  AND created_at <= '2026-08-31'
GROUP BY paid_to_name
ORDER BY Sales DESC;
```

### Top 10 Services:
```sql
SELECT 
    service,
    COUNT(*) as Sales
FROM revenue_entries
WHERE guild_id = YOUR_SERVER_ID
GROUP BY service
ORDER BY Sales DESC
LIMIT 10;
```

### Payment Method Breakdown:
```sql
SELECT 
    payment_method,
    COUNT(*) as Count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM revenue_entries), 2) as Percentage
FROM revenue_entries
WHERE guild_id = YOUR_SERVER_ID
GROUP BY payment_method
ORDER BY Count DESC;
```

### Staff Performance (Last 7 Days):
```sql
SELECT 
    paid_to_name as Staff,
    COUNT(*) as Sales,
    COUNT(DISTINCT user_name) as UniqueClients
FROM revenue_entries
WHERE guild_id = YOUR_SERVER_ID
  AND datetime(created_at) >= datetime('now', '-7 days')
GROUP BY paid_to_name
ORDER BY Sales DESC;
```

---

## 🔍 Finding Your Server ID

In Discord:
1. Enable Developer Mode:
   - User Settings → Advanced → Developer Mode: **ON**
2. Right-click your server icon
3. Click **"Copy Server ID"**
4. That's your `guild_id`!

---

## 📊 Excel Dashboard (Advanced)

### Create Excel Dashboard:
1. Open Excel
2. Go to **Data** → **Get Data** → **From Database** → **From SQLite**
3. Select `bot_data.db`
4. Choose `revenue_entries` table
5. Click **Load**

Now you have live data in Excel!

### Create Pivot Table:
1. Select your data
2. Insert → PivotTable
3. Drag fields:
   - **Rows:** `paid_to_name` (Staff)
   - **Columns:** `service` (Service)
   - **Values:** Count of `id`
4. You now have a staff × service matrix!

### Auto-Refresh:
- Right-click table → Refresh
- Or set auto-refresh every hour

---

## 🛠️ Editing Data

### Using DB Browser:
1. Open `bot_data.db`
2. Go to **"Browse Data"** tab
3. Select `revenue_entries`
4. Double-click any cell to edit
5. **Write Changes** button to save

### ⚠️ Be Careful:
- Always backup before editing!
- Don't change `id` or `guild_id` columns
- Invalid data may cause bot errors

---

## 🔒 Security

### Best Practices:
1. **Don't share** `bot_data.db` - contains user IDs
2. **Regular backups** - prevents data loss
3. **Keep local** - don't upload to cloud with sensitive data
4. **Close DB Browser** - before starting bot (file locking)

---

## 📞 Troubleshooting

### "Database is locked"
- Close DB Browser for SQLite
- Make sure bot isn't running
- Restart both

### "File not found"
- Check path is correct
- Run bot once to create database
- Look in bot's root folder

### "No data showing"
- Check you're looking at correct server
- Verify `guild_id` in queries
- Check if any revenue posted yet

### Changes not appearing in bot
- Bot caches data - restart it
- Check file saved properly
- Verify no SQL errors

---

## 📈 Example: Monthly Report

Create `monthly_report.py`:

```python
import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict

conn = sqlite3.connect('bot_data.db')
cursor = conn.cursor()

# Get current month
today = datetime.now()
first_day = today.replace(day=1).strftime('%Y-%m-%d')

cursor.execute("""
SELECT 
    paid_to_name,
    service,
    payment_method,
    created_at
FROM revenue_entries
WHERE guild_id = YOUR_SERVER_ID
  AND created_at >= ?
ORDER BY paid_to_name, service
""", (first_day,))

# Organize data
staff_data = defaultdict(lambda: {'services': defaultdict(int), 'total': 0})

for staff, service, payment, date in cursor.fetchall():
    staff_data[staff]['services'][service] += 1
    staff_data[staff]['total'] += 1

# Print report
print(f"\n📊 MONTHLY REVENUE REPORT - {today.strftime('%B %Y')}\n")
print("=" * 80)

for staff, data in sorted(staff_data.items(), key=lambda x: x[1]['total'], reverse=True):
    print(f"\n{staff} ({data['total']} sales)")
    print("-" * 40)
    
    for service, count in sorted(data['services'].items(), key=lambda x: x[1], reverse=True):
        print(f"  • {service:<30} {count:>3}x")

conn.close()
```

---

**Your database is ready to use! 💾**

**Quick Start:**
1. Download DB Browser for SQLite
2. Open `bot_data.db`
3. Browse `revenue_entries` table
4. Export to Excel if needed

**For automated analysis:** Use the Python scripts provided above!
