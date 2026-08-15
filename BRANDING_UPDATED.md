# 🐰 United Bunnies - Complete Branding Update

## Overview
All "Vortex" branding has been replaced with "United Bunnies" throughout the bot.

---

## 🎨 Changes Made

### **bot/config.py**
- ✅ Brand color comment updated: `# United Bunnies purple`
- ✅ Emoji example comments updated to reference `unitedbunnies` instead of `vortex`
- ✅ `BRAND_EMOJI` changed from Vortex custom emoji to `🐰` (bunny emoji)
  - *Note: Replace with your custom United Bunnies emoji when available*

### **bot/cogs/applications.py**
- ✅ Footer text updated: `"🐰 United Bunnies System Active ✨"` (2 occurrences)

### **bot/cogs/community.py**
- ✅ Dashboard embed title: `"📊 Server: UNITED BUNNIES"`
- ✅ Panel embed footer: `"🐰 United Bunnies System Active ✨"`
- ✅ Help system title: `"🐰 ── UNITED BUNNIES HELP ── 🐰"`
- ✅ Help footer: `"United Bunnies • Use the menu below to browse commands"`
- ✅ Category footer: `"United Bunnies • Use the menu below to browse other categories"`

### **bot/ui/premium_cards.py**
- ✅ Header comment: `# United Bunnies brand palette - PREMIUM PURPLE THEME`
- ✅ Default title: `"UNITED BUNNIES"` (2 occurrences)

### **bot/ui/__init__.py**
- ✅ Module docstring: `"""Shared UI components for United Bunnies."""`

---

## 🎯 Brand Identity

### Colors
- **Primary Purple:** `0x8B5CF6` (unchanged - your signature purple)
- **Accent Colors:**
  - Success: `0x57F287` (green)
  - Warning: `0xFEE75C` (gold)
  - Error: `0xED4245` (red)
  - Mod: `0x9B59B6` (purple)

### Emojis
- **Brand Emoji:** 🐰 (bunny)
- **Title Decorator:** ◈ (diamond)
- **Bullet Point:** › (chevron)
- **System Status:** ✨ (sparkles)

### Typography Pattern
- **Titles:** `"🐰 ── UNITED BUNNIES [SECTION] ── 🐰"`
- **Footers:** `"🐰 United Bunnies System Active ✨"`
- **Help Text:** `"United Bunnies • [context info]"`

---

## 📋 Recommendation: Custom Emoji Setup

For complete branding, create these custom emojis in your Discord server:

1. **Brand Logo:** `<:unitedbunnies:YOUR_ID_HERE>`
   - Upload your United Bunnies logo
   - Update `BRAND_EMOJI` in `bot/config.py`

2. **Diamond Decorator:** `<:ub_diamond:YOUR_ID_HERE>`
   - Create a themed diamond icon
   - Update `EMOJI_DIAMOND` in `bot/config.py`

3. **Bullet Point:** `<:ub_bullet:YOUR_ID_HERE>`
   - Create a themed bullet/chevron icon
   - Update `EMOJI_BULLET` in `bot/config.py`

### How to Get Custom Emoji IDs:
1. Upload emoji to your Discord server
2. Type `\:emoji_name:` in any channel
3. Copy the full string (e.g., `<:name:1234567890>`)
4. Update the corresponding constant in `bot/config.py`

---

## ✅ Verification Checklist

- [x] Brand name updated in all UI text
- [x] Footer messages updated
- [x] Help system titles updated
- [x] Premium card defaults updated
- [x] Module docstrings updated
- [x] Comments referencing old brand updated
- [ ] **TODO:** Update `BRAND_EMOJI` with custom emoji once created
- [ ] **TODO:** Update `EMOJI_DIAMOND` with custom emoji once created
- [ ] **TODO:** Update `EMOJI_BULLET` with custom emoji once created

---

## 🚀 Deploy

All changes are code-only and safe to deploy immediately:

```bash
git add .
git commit -m "🐰 Rebrand: Vortex → United Bunnies"
git push
```

The bot will automatically reflect the new branding on next restart!

---

## 🎨 Brand Consistency

All user-facing text now follows the **United Bunnies** brand:
- ✅ Welcome messages
- ✅ Help command
- ✅ Dashboard links
- ✅ Application system
- ✅ Ticket system
- ✅ All embed footers
- ✅ Premium card views

**Your bot is now fully branded as United Bunnies! 🐰✨**
