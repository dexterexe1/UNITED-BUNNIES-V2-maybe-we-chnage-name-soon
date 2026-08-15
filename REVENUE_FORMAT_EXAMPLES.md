# 📝 Revenue Report Format - Visual Examples

## ✅ CORRECT EXAMPLES

### Example 1: Basic Report
```
User : @HINATA
Service : 1 shark trial
Payment : portal
Paid to : @Roger
```
✅ **Result:** Bot reacts with ✅💰 and saves to database

---

### Example 2: Different Payment Method
```
User : @JohnDoe
Service : Tiger premium package
Payment : cashapp
Paid to : @Detrox
```
✅ **Result:** Bot reacts with ✅💰 and saves to database

---

### Example 3: Case Doesn't Matter
```
user : @sarah
service : dragon boost
payment : paypal
paid to : @mike
```
✅ **Result:** Bot reacts with ✅💰 and saves to database

---

### Example 4: Extra Spaces Are OK
```
User  :  @Customer
Service  :  Full service pack
Payment  :  bitcoin
Paid  to  :  @Staff
```
✅ **Result:** Bot reacts with ✅💰 and saves to database

---

## ❌ WRONG EXAMPLES (Will Be Rejected)

### ❌ Example 1: Missing @ Mentions
```
User : HINATA          ← ❌ NEEDS @
Service : shark trial
Payment : portal
Paid to : Roger        ← ❌ NEEDS @
```
**Error:** Bot will ping you, delete this, and show correct format

---

### ❌ Example 2: Wrong Field Names
```
Customer : @John       ← ❌ Must be "User"
Service : trial
Method : portal        ← ❌ Must be "Payment"
Staff : @Roger         ← ❌ Must be "Paid to"
```
**Error:** Bot will ping you, delete this, and show correct format

---

### ❌ Example 3: Missing Fields
```
User : @John
Service : trial
Payment : portal
                       ← ❌ Missing "Paid to"
```
**Error:** Bot will ping you, delete this, and show correct format

---

### ❌ Example 4: Wrong Separator
```
User = @John           ← ❌ Must use : not =
Service : trial
Payment : portal
Paid to : @Roger
```
**Error:** Bot will ping you, delete this, and show correct format

---

### ❌ Example 5: All on One Line
```
User : @John Service : trial Payment : portal Paid to : @Roger
```
**Error:** Bot will ping you, delete this, and show correct format

---

## 📋 Copy-Paste Template

**Copy this and fill in the details:**

```
User : @
Service : 
Payment : 
Paid to : @
```

---

## 🎯 Real-World Examples

### Bloxfruits Services

```
User : @PlayerX
Service : Leopard fruit delivery
Payment : robux
Paid to : @FruitDealer
```

```
User : @Noob123
Service : Level boost 1-300
Payment : cashapp
Paid to : @BoostMaster
```

```
User : @ProGamer
Service : Raid carry + fruit
Payment : paypal
Paid to : @RaidHelper
```

---

### Adopt Me Trading

```
User : @PetLover
Service : Legendary pet trade
Payment : amp pets
Paid to : @Trader1
```

```
User : @Collector
Service : Neon mega bundle
Payment : robux
Paid to : @MegaMaker
```

---

### MM (Middleman) Services

```
User : @Buyer99
Service : MM for $500 trade
Payment : tip-cashapp
Paid to : @TrustedMM
```

```
User : @Seller123
Service : Large account MM
Payment : commission
Paid to : @MMPro
```

---

## 🔍 What Gets Recorded?

When you post this:
```
User : @HINATA
Service : 1 shark trial
Payment : portal
Paid to : @Roger
```

The bot saves:
- ✅ **Customer:** HINATA (ID: 123456789)
- ✅ **Service:** 1 shark trial
- ✅ **Payment Method:** portal
- ✅ **Staff Member:** Roger (ID: 987654321)
- ✅ **Who Posted:** Your ID
- ✅ **Timestamp:** 2026-08-15 14:30:45 UTC

---

## 📊 How It Appears in Reports

When admin types `?weekrevenue`:

```
🐰 WEEKLY REVENUE REPORT 🐰

📊 Total Transactions: 15

› Roger
   • portal: 8 transactions
   • cashapp: 3 transactions
   **Subtotal:** 11 transactions

› Detrox
   • tiger: 4 transactions
   **Subtotal:** 4 transactions
```

---

## 💡 Pro Tips

### Tip 1: Pin This Template in Your Channel
Right-click on a message with the template and select "Pin Message"

### Tip 2: Use Nicknames
```
User : @John "ProTrader" Smith    ← Works fine!
Service : premium boost
Payment : cashapp
Paid to : @Mike
```

### Tip 3: Services Can Be Detailed
```
User : @Customer
Service : 3x Leopard, 2x Dragon, 1x Dough + Storage boost
Payment : robux
Paid to : @Staff
```

### Tip 4: Payment Methods Can Be Anything
```
Payment : cashapp
Payment : paypal
Payment : robux
Payment : btc
Payment : gift-card
Payment : trade
Payment : portal
Payment : tiger
```
All valid! Use whatever your server uses.

---

## ⚠️ Important Notes

1. **@Mentions Are Required**
   - You MUST use actual Discord @mentions
   - Just typing @name won't work
   - The mention must turn blue/clickable

2. **Each Field On New Line**
   - Don't put everything on one line
   - Press Enter after each field

3. **Use Colon (:)**
   - Must be `User :` not `User =` or `User-`

4. **No Extra Text**
   - Don't add comments or extra info outside the format
   - Keep it clean and simple

---

## 🚨 What Happens to Invalid Reports?

1. Bot detects wrong format
2. Bot pings you with error message
3. Shows you the correct format
4. Deletes your message after 15 seconds
5. Deletes the error message too
6. Nothing is saved to database

**Just repost with correct format!**

---

## ✅ What Happens to Valid Reports?

1. Bot validates format ✅
2. Bot reacts with ✅ and 💰
3. Saves to database immediately
4. You can keep the message (not deleted)
5. Shows up in `?weekrevenue` instantly

---

## 📞 Need Help?

Type in Discord:
```
?revenuehelp
```

Ask an admin if you're still confused!

---

**Remember: Copy the template, fill it in, post it! 🐰💰**

Template:
```
User : @
Service : 
Payment : 
Paid to : @
```
