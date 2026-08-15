# 💰 Revenue Report - New Professional Format

## 📊 Example Output

### Command: `?weekrevenue`

```
🐰 WEEKLY REVENUE REPORT 🐰

📊 Total Transactions: 47

› Roger (23 sales)
   • **leopard**: 8x
   • **tiger**: 6x
   • **dough**: 4x
   • **venom**: 3x
   • **dragon**: 2x
   💳 Payments: portal (15), cashapp (8)

› Detrox (15 sales)
   • **shark**: 5x
   • **buddha**: 4x
   • **light**: 3x
   • **yeti**: 2x
   • **phoenix**: 1x
   💳 Payments: tiger (10), portal (5)

› Sarah (9 sales)
   • **magma**: 3x
   • **ice**: 2x
   • **flame**: 2x
   • **sand**: 2x
   💳 Payments: paypal (7), cashapp (2)

United Bunnies Revenue System • Generated at 2026-08-15 14:30 UTC
```

---

## 🎯 New Command: `?revenuevia`

### Show specific staff's performance

**Command:** `?revenuevia Roger`

```
🐰 STAFF REVENUE REPORT

**Staff Member:** Roger
**Period:** Last 30 days
**Total Sales:** 45
**Unique Clients:** 32

**🎯 Services Provided:**
• **leopard**: 12x (26.7%)
• **tiger**: 8x (17.8%)
• **dough**: 7x (15.6%)
• **venom**: 6x (13.3%)
• **dragon**: 5x (11.1%)
• **buddha**: 3x (6.7%)
• **light**: 2x (4.4%)
• **phoenix**: 2x (4.4%)

**💳 Payment Methods:**
• portal: 28x (62.2%)
• cashapp: 15x (33.3%)
• paypal: 2x (4.4%)

United Bunnies Revenue System
```

---

## 📝 How It Works

### Revenue Reports Show:
1. **Staff Name** with total sales count
2. **Services** (fruit names: leopard, tiger, etc.) sorted by most sold
3. **Payment Methods** breakdown at the end

### Why This Format?

**Old Format:**
```
› Detrox
   • tiger: 15 transactions  ← Payment method (confusing!)
   • portal: 8 transactions
   Subtotal: 23 transactions
```
❌ Shows payment methods as main items (confusing)

**New Format:**
```
› Detrox (23 sales)
   • **leopard**: 8x           ← Service/fruit name (clear!)
   • **tiger**: 6x
   • **dough**: 4x
   💳 Payments: portal (15), cashapp (8)  ← Payment summary
```
✅ Shows services first, payments as summary (professional!)

---

## 🎮 Use Cases

### Use Case 1: Weekly Team Meeting
```
?weekrevenue
```
Shows what each staff sold this week - perfect for performance review!

### Use Case 2: Check Staff Performance
```
?revenuevia "Detrox"
```
See everything Detrox sold, what clients bought, payment methods used.

### Use Case 3: Monthly Report
```
?monthrevenue
```
Full month breakdown - perfect for commission calculations!

### Use Case 4: Individual Lookup
```
?revenuevia Roger 7
```
See Roger's sales for last 7 days only.

---

## 📊 Real-World Example

### Bloxfruits Service Server

**Report Entry:**
```
User : PlayerX
Service : leopard fruit
Payment : robux
Paid to : Roger
```

**Weekly Report Shows:**
```
› Roger (12 sales)
   • **leopard fruit**: 5x
   • **dough fruit**: 3x
   • **venom fruit**: 2x
   • **buddha fruit**: 2x
   💳 Payments: robux (8), portal (4)
```

**Staff Specific Report (`?revenuevia Roger`):**
```
**Staff Member:** Roger
**Total Sales:** 45
**Unique Clients:** 32

**🎯 Services Provided:**
• **leopard fruit**: 15x (33.3%)
• **dough fruit**: 10x (22.2%)
• **venom fruit**: 8x (17.8%)
... (shows percentages!)
```

---

## 🎯 Command Usage

### All Revenue Commands:

```bash
# Overall reports (all staff)
?weekrevenue          # Last 7 days
?monthrevenue         # Last 30 days
?todayrevenue         # Today only
?allrevenue           # All time (admin only)

# Staff-specific reports
?revenuevia "Roger"              # Default: last 30 days
?revenuevia "Detrox" 7           # Last 7 days
?revenuevia "Sarah" 60           # Last 60 days

# Detailed view
?revenuedetails 7     # Last 10 transactions with timestamps

# Help
?revenuehelp          # Show all commands
```

---

## 💡 Tips

### Best Practices:

1. **Use Clear Service Names**
   ```
   ✅ Service : leopard fruit
   ✅ Service : tiger premium
   ✅ Service : dough + storage
   ❌ Service : stuff
   ```

2. **Consistent Naming**
   ```
   ✅ Always use: leopard, tiger, dough
   ❌ Mixing: Leopard, TIGER, doUgh
   ```

3. **Check Individual Staff**
   ```
   # Before discussing performance:
   ?revenuevia "StaffName"
   # Shows exactly what they sold!
   ```

4. **Weekly Team Reviews**
   ```
   # Every Monday:
   ?weekrevenue
   # See who's performing well
   ```

---

## 📈 Understanding the Data

### What Each Metric Means:

**Total Transactions:**
- Number of sales completed
- Each revenue report = 1 transaction

**Unique Clients:**
- Different customers served
- Same customer multiple times = still 1 unique

**Percentages:**
- `(15.6%)` = 15.6% of this staff's total sales
- Helps identify their specialties

**Payment Methods:**
- Shows how customers paid
- Useful for accounting

---

## 🔍 Finding Top Sellers

### By Staff:
```
?weekrevenue
```
Look at sales count next to each name:
- `Roger (23 sales)` ← Top seller!
- `Detrox (15 sales)`
- `Sarah (9 sales)`

### By Service:
```
?revenuevia "Roger"
```
Look at service counts:
- `leopard: 12x` ← Best selling service!
- `tiger: 8x`
- `dough: 7x`

---

## 💳 Payment Analysis

### Check Payment Preferences:
```
?revenuevia "Staff Name"
```

Shows payment breakdown:
```
💳 Payment Methods:
• portal: 28x (62.2%)    ← Most customers use portal
• cashapp: 15x (33.3%)
• paypal: 2x (4.4%)      ← Few use paypal
```

**Use This For:**
- Deciding which payment methods to support
- Identifying issues with specific methods
- Commission calculations

---

## 📊 Database Connection

All this data is stored in `bot_data.db` on your PC!

**Access it:**
1. Download [DB Browser for SQLite](https://sqlitebrowser.org/)
2. Open `bot_data.db`
3. View `revenue_entries` table
4. Export to Excel for charts!

**See full guide:** `DATABASE_PC_GUIDE.md`

---

## 🎯 Quick Reference

| Command | What It Shows | Example |
|---------|--------------|---------|
| `?weekrevenue` | All staff, last 7 days | Team overview |
| `?monthrevenue` | All staff, last 30 days | Monthly performance |
| `?revenuevia "Roger"` | One staff, last 30 days | Individual report |
| `?revenuevia "Roger" 7` | One staff, last 7 days | Recent performance |
| `?revenuedetails 7` | Last 10 transactions | Transaction log |

---

**Your revenue system now shows services (fruits) instead of payment methods! 🐰💰**

**Try it:** `?weekrevenue` to see the new format!
