"""
database.py — All SQLite helpers for the bot.
Extracted from the original monolithic bot.py. Logic unchanged.
"""
import sqlite3
import datetime
import discord

from bot.config import BOT_OWNER_IDS

UTC = datetime.timezone.utc
DB_FILE = "bot_data.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            user_id INTEGER PRIMARY KEY,
            warning_count INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS server_config (
            guild_id INTEGER PRIMARY KEY,
            welcome_channel_id INTEGER DEFAULT 0,
            log_channel_id INTEGER DEFAULT 0,
            vouch_channel_id INTEGER DEFAULT NULL
        )
    """)
    # Migration: older databases (created before the vouch system existed)
    # won't have this column yet. ALTER TABLE ADD COLUMN is a safe way to
    # backfill it without losing existing welcome/log config.
    cursor.execute("PRAGMA table_info(server_config)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    if "vouch_channel_id" not in existing_cols:
        cursor.execute("ALTER TABLE server_config ADD COLUMN vouch_channel_id INTEGER DEFAULT NULL")
    if "trusted_role_id" not in existing_cols:
        cursor.execute("ALTER TABLE server_config ADD COLUMN trusted_role_id INTEGER DEFAULT NULL")
    if "welcome_message" not in existing_cols:
        cursor.execute("ALTER TABLE server_config ADD COLUMN welcome_message TEXT DEFAULT NULL")
    if "levelup_channel_id" not in existing_cols:
        cursor.execute("ALTER TABLE server_config ADD COLUMN levelup_channel_id INTEGER DEFAULT NULL")
    if "levels_enabled" not in existing_cols:
        cursor.execute("ALTER TABLE server_config ADD COLUMN levels_enabled INTEGER DEFAULT 0")
    if "revenue_channel_id" not in existing_cols:
        cursor.execute("ALTER TABLE server_config ADD COLUMN revenue_channel_id INTEGER DEFAULT NULL")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS noprefix_users (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS role_menu_items (
            message_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            emoji TEXT,
            label TEXT NOT NULL,
            PRIMARY KEY (message_id, role_id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS liked_songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            song_title TEXT,
            song_url TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vouches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL,
            author_id INTEGER NOT NULL,
            comment TEXT,
            created_at TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS levels (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reaction_roles (
            guild_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            emoji TEXT NOT NULL,
            role_id INTEGER NOT NULL,
            PRIMARY KEY (message_id, emoji)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            channel_id INTEGER PRIMARY KEY,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            status TEXT DEFAULT 'open',
            created_at TEXT
        )
    """)
    cursor.execute("PRAGMA table_info(tickets)")
    ticket_cols = {row[1] for row in cursor.fetchall()}
    if "ticket_type" not in ticket_cols:
        cursor.execute("ALTER TABLE tickets ADD COLUMN ticket_type TEXT DEFAULT 'General Support'")
    if "claimed_by" not in ticket_cols:
        cursor.execute("ALTER TABLE tickets ADD COLUMN claimed_by INTEGER DEFAULT NULL")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS marriages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user1_id INTEGER NOT NULL,
            user2_id INTEGER NOT NULL,
            married_at TEXT
        )
    """)
    # Per-command role restrictions ("/cmdperm-allow", "/cmdperm-deny", etc).
    # A command with no rows here is open to everyone by default.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS command_permissions (
            guild_id INTEGER NOT NULL,
            command_name TEXT NOT NULL,
            role_id INTEGER NOT NULL,
            PRIMARY KEY (guild_id, command_name, role_id)
        )
    """)
    # Custom auto-responder pairs ("/new-command"): trigger text -> response text.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS custom_commands (
            guild_id INTEGER NOT NULL,
            trigger TEXT NOT NULL,
            response TEXT NOT NULL,
            created_by INTEGER,
            PRIMARY KEY (guild_id, trigger)
        )
    """)
    # ... [all your existing cursor.execute() calls] ...

    # ================= NEW TABLES (ADD THESE) =================
    
    # Discord /disable & /enable commands (SQLite only)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS disabled_features (
        guild_id INTEGER NOT NULL,
        feature_name TEXT NOT NULL,
        type TEXT NOT NULL,
        PRIMARY KEY (guild_id, feature_name, type)
    )
    """)
    
    
    # Adoption System
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS adoptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        child_id INTEGER NOT NULL,
        parent1_id INTEGER NOT NULL,
        parent2_id INTEGER NOT NULL,
        adopted_at TEXT
    )
    """)
    
    # Configurable Ticket Panels
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ticket_panels (
        panel_id TEXT PRIMARY KEY,
        guild_id INTEGER NOT NULL,
        channel_id INTEGER NOT NULL,
        message_id INTEGER,
        config TEXT
    )
    """)
    
    # Revenue Tracking System
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS revenue_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        user_name TEXT,
        service TEXT NOT NULL,
        payment_method TEXT NOT NULL,
        paid_to_id INTEGER NOT NULL,
        paid_to_name TEXT,
        done_by_id INTEGER DEFAULT 0,
        done_by_name TEXT,
        recorded_by_id INTEGER NOT NULL,
        created_at TEXT NOT NULL
    )
    """)
    
    # Bot Control System
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bot_owners (
        user_id INTEGER PRIMARY KEY,
        username TEXT NOT NULL
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bot_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)
    
    # ================= END NEW TABLES =================

    conn.commit()  # ← Keep this line exactly where it is
    conn.close()

# init_db() is called explicitly in main.py, so no need to call it at module level

# --- PLAYLIST DATABASE UTILITIES ---
def add_liked_song(user_id: int, title: str, url: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO liked_songs (user_id, song_title, song_url) VALUES (?, ?, ?)", (user_id, title, url))
    conn.commit()
    conn.close()

def get_liked_songs(user_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT song_title, song_url FROM liked_songs WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def clear_liked_songs(user_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM liked_songs WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# --- GENERAL DB UTILITIES ---
def get_config(guild_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT welcome_channel_id, log_channel_id FROM server_config WHERE guild_id = ?", (guild_id,))
    row = cursor.fetchone()
    conn.close()
    return row if row else (0, 0)

def set_config(guild_id: int, col_name: str, channel_id: int):
    welcome, logs = get_config(guild_id)
    if col_name == "welcome": welcome = channel_id
    if col_name == "logs": logs = channel_id
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO server_config (guild_id, welcome_channel_id, log_channel_id)
        VALUES (?, ?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET welcome_channel_id = ?, log_channel_id = ?
    """, (guild_id, welcome, logs, welcome, logs))
    conn.commit()
    conn.close()

def get_warnings(user_id: int) -> int:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT warning_count FROM warnings WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0

def update_warnings(user_id: int, increment: int) -> int:
    current = get_warnings(user_id)
    new_total = max(0, current + increment)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO warnings (user_id, warning_count) 
        VALUES (?, ?) 
        ON CONFLICT(user_id) DO UPDATE SET warning_count = ?
    """, (user_id, new_total, new_total))
    conn.commit()
    conn.close()
    return new_total

def reset_warnings(user_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM warnings WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# --- NO-PREFIX PERMISSION DB UTILITIES ---
def get_trusted_role_id(guild_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT trusted_role_id FROM server_config WHERE guild_id = ?", (guild_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] else None

def set_trusted_role_id(guild_id: int, role_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO server_config (guild_id, welcome_channel_id, log_channel_id, trusted_role_id)
        VALUES (?, 0, 0, ?)
        ON CONFLICT(guild_id) DO UPDATE SET trusted_role_id = ?
    """, (guild_id, role_id, role_id))
    conn.commit()
    conn.close()

def clear_trusted_role_id(guild_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE server_config SET trusted_role_id = NULL WHERE guild_id = ?", (guild_id,))
    conn.commit()
    conn.close()

def grant_noprefix(guild_id: int, user_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO noprefix_users (guild_id, user_id) VALUES (?, ?)", (guild_id, user_id))
    conn.commit()
    conn.close()

def revoke_noprefix(guild_id: int, user_id: int) -> bool:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM noprefix_users WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
    changed = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return changed

def is_noprefix_user(guild_id: int, user_id: int) -> bool:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM noprefix_users WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def list_noprefix_users(guild_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM noprefix_users WHERE guild_id = ?", (guild_id,))
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def has_noprefix_perm(guild: discord.Guild, member: discord.Member) -> bool:
    """Bot owners and individually-granted users can run commands without '?' prefix."""
    # Bot owners bypass everything
    if member.id in BOT_OWNER_IDS:
        return True
    # Check individual database grants
    return is_noprefix_user(guild.id, member.id)


# --- VOUCH SYSTEM DB UTILITIES ---
def add_vouch(guild_id: int, target_id: int, author_id: int, comment: str = None):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO vouches (guild_id, target_id, author_id, comment, created_at) VALUES (?, ?, ?, ?, ?)",
        (guild_id, target_id, author_id, comment, datetime.datetime.now(UTC).isoformat()),
    )
    conn.commit()
    conn.close()

def remove_last_vouch(guild_id: int, target_id: int, author_id: int) -> bool:
    """Remove the most recent vouch the given author gave to target. Used by regular users."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM vouches WHERE guild_id = ? AND target_id = ? AND author_id = ? ORDER BY id DESC LIMIT 1",
        (guild_id, target_id, author_id),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
    cursor.execute("DELETE FROM vouches WHERE id = ?", (row[0],))
    conn.commit()
    conn.close()
    return True


def staff_remove_vouch(guild_id: int, target_id: int) -> bool:
    """Remove the most recent vouch for target regardless of who gave it. Staff-only action."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM vouches WHERE guild_id = ? AND target_id = ? ORDER BY id DESC LIMIT 1",
        (guild_id, target_id),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
    cursor.execute("DELETE FROM vouches WHERE id = ?", (row[0],))
    conn.commit()
    conn.close()
    return True


def staff_clear_all_vouches(guild_id: int, target_id: int) -> int:
    """Delete every vouch for target in this guild. Returns count removed. Staff-only action."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM vouches WHERE guild_id = ? AND target_id = ?",
        (guild_id, target_id),
    )
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count

def count_vouches(guild_id: int, target_id: int) -> int:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM vouches WHERE guild_id = ? AND target_id = ?", (guild_id, target_id))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0

def list_vouches(guild_id: int, target_id: int, limit: int = 5):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT author_id, comment, created_at FROM vouches WHERE guild_id = ? AND target_id = ? ORDER BY id DESC LIMIT ?",
        (guild_id, target_id, limit),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

def vouch_leaderboard(guild_id: int, limit: int = 10):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT target_id, COUNT(*) as c FROM vouches WHERE guild_id = ? GROUP BY target_id ORDER BY c DESC LIMIT ?",
        (guild_id, limit),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

# --- LEVELING SYSTEM DB UTILITIES ---
def xp_for_level(level: int) -> int:
    # Total XP required to reach this level. Gently increasing curve.
    return 5 * (level ** 2) + 50 * level + 100

def get_level_data(guild_id: int, user_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT xp, level FROM levels WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
    row = cursor.fetchone()
    conn.close()
    return row if row else (0, 0)

def add_xp(guild_id: int, user_id: int, amount: int):
    """Adds XP and returns (new_xp, new_level, leveled_up: bool)."""
    xp, level = get_level_data(guild_id, user_id)
    new_xp = xp + amount
    new_level = level
    while new_xp >= xp_for_level(new_level + 1):
        new_level += 1

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO levels (guild_id, user_id, xp, level) VALUES (?, ?, ?, ?)
        ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = ?, level = ?
        """,
        (guild_id, user_id, new_xp, new_level, new_xp, new_level),
    )
    conn.commit()
    conn.close()
    return new_xp, new_level, new_level > level

def level_leaderboard(guild_id: int, limit: int = 10):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_id, xp, level FROM levels WHERE guild_id = ? ORDER BY xp DESC LIMIT ?",
        (guild_id, limit),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

# --- REACTION ROLES DB UTILITIES ---
def add_reaction_role(guild_id: int, message_id: int, emoji: str, role_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO reaction_roles (guild_id, message_id, emoji, role_id) VALUES (?, ?, ?, ?)
        ON CONFLICT(message_id, emoji) DO UPDATE SET role_id = ?
        """,
        (guild_id, message_id, emoji, role_id, role_id),
    )
    conn.commit()
    conn.close()

def remove_reaction_role(message_id: int, emoji: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reaction_roles WHERE message_id = ? AND emoji = ?", (message_id, emoji))
    conn.commit()
    conn.close()

def get_reaction_role(message_id: int, emoji: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT role_id FROM reaction_roles WHERE message_id = ? AND emoji = ?", (message_id, emoji))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

# --- TICKET SYSTEM DB UTILITIES ---
def create_ticket_record(channel_id: int, guild_id: int, user_id: int, ticket_type: str = "General Support"):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tickets (channel_id, guild_id, user_id, status, created_at, ticket_type) VALUES (?, ?, ?, 'open', ?, ?)",
        (channel_id, guild_id, user_id, datetime.datetime.now(UTC).isoformat(), ticket_type),
    )
    conn.commit()
    conn.close()

def close_ticket_record(channel_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE tickets SET status = 'closed' WHERE channel_id = ?", (channel_id,))
    conn.commit()
    conn.close()

def claim_ticket_record(channel_id: int, staff_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE tickets SET claimed_by = ? WHERE channel_id = ?", (staff_id, channel_id))
    conn.commit()
    conn.close()

def unclaim_ticket_record(channel_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE tickets SET claimed_by = NULL WHERE channel_id = ?", (channel_id,))
    conn.commit()
    conn.close()

def get_ticket_record(channel_id: int):
    """Returns (user_id, status, ticket_type, claimed_by) or None."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, status, ticket_type, claimed_by FROM tickets WHERE channel_id = ?", (channel_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def get_open_ticket_for_user(guild_id: int, user_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT channel_id FROM tickets WHERE guild_id = ? AND user_id = ? AND status = 'open'",
        (guild_id, user_id),
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def list_open_tickets(guild_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT channel_id, user_id, ticket_type, claimed_by, created_at FROM tickets WHERE guild_id = ? AND status = 'open' ORDER BY created_at ASC",
        (guild_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


# --- DROPDOWN ROLE MENU DB UTILITIES ---
def add_role_menu_items(message_id: int, guild_id: int, channel_id: int, entries):
    """entries: list of (role_id, emoji, label) tuples"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    for role_id, emoji, label in entries:
        cursor.execute(
            """
            INSERT INTO role_menu_items (message_id, guild_id, channel_id, role_id, emoji, label)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(message_id, role_id) DO UPDATE SET emoji = ?, label = ?
            """,
            (message_id, guild_id, channel_id, role_id, emoji, label, emoji, label),
        )
    conn.commit()
    conn.close()

def get_role_menu_items(message_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT role_id, emoji, label FROM role_menu_items WHERE message_id = ?", (message_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_all_role_menu_message_ids():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT message_id FROM role_menu_items")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def delete_role_menu(message_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM role_menu_items WHERE message_id = ?", (message_id,))
    conn.commit()
    conn.close()

# --- MARRIAGE SYSTEM DB UTILITIES ---
def get_marriage(guild_id: int, user_id: int):
    """Returns (id, user1_id, user2_id, married_at) if this user is married in this guild, else None."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, user1_id, user2_id, married_at FROM marriages WHERE guild_id = ? AND (user1_id = ? OR user2_id = ?)",
        (guild_id, user_id, user_id),
    )
    row = cursor.fetchone()
    conn.close()
    return row

def create_marriage(guild_id: int, user1_id: int, user2_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO marriages (guild_id, user1_id, user2_id, married_at) VALUES (?, ?, ?, ?)",
        (guild_id, user1_id, user2_id, datetime.datetime.now(UTC).isoformat()),
    )
    conn.commit()
    conn.close()

def delete_marriage(marriage_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM marriages WHERE id = ?", (marriage_id,))
    conn.commit()
    conn.close()

# --- WELCOMER MESSAGE DB UTILITIES ---
def get_welcome_message(guild_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT welcome_message FROM server_config WHERE guild_id = ?", (guild_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] else None

def set_welcome_message(guild_id: int, message: str):
    welcome, logs = get_config(guild_id)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO server_config (guild_id, welcome_channel_id, log_channel_id, welcome_message)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET welcome_message = ?
    """, (guild_id, welcome, logs, message, message))
    conn.commit()
    conn.close()

def clear_welcome_message(guild_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE server_config SET welcome_message = NULL WHERE guild_id = ?", (guild_id,))
    conn.commit()
    conn.close()

def format_welcome_message(template: str, member: discord.Member) -> str:
    return (
        template.replace("{user}", member.mention)
        .replace("{username}", member.display_name)
        .replace("{server}", member.guild.name)
        .replace("{membercount}", str(member.guild.member_count))
    )

# --- LEVELING CONFIG DB UTILITIES ---
def get_levelup_channel(guild_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT levelup_channel_id FROM server_config WHERE guild_id = ?", (guild_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] else None

def set_levelup_channel(guild_id: int, channel_id: int):
    welcome, logs = get_config(guild_id)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO server_config (guild_id, welcome_channel_id, log_channel_id, levelup_channel_id)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET levelup_channel_id = ?
    """, (guild_id, welcome, logs, channel_id, channel_id))
    conn.commit()
    conn.close()

def clear_levelup_channel(guild_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE server_config SET levelup_channel_id = NULL WHERE guild_id = ?", (guild_id,))
    conn.commit()
    conn.close()

def is_leveling_enabled(guild_id: int) -> bool:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT levels_enabled FROM server_config WHERE guild_id = ?", (guild_id,))
    row = cursor.fetchone()
    conn.close()
    if row is None or row[0] is None:
        return False  # leveling off by default (use external leveling bots)
    return bool(row[0])

def set_leveling_enabled(guild_id: int, enabled: bool):
    welcome, logs = get_config(guild_id)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO server_config (guild_id, welcome_channel_id, log_channel_id, levels_enabled)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET levels_enabled = ?
    """, (guild_id, welcome, logs, int(enabled), int(enabled)))
    conn.commit()
    conn.close()

# --- COMMAND PERMISSIONS DB UTILITIES ---
def get_command_permission_roles(guild_id: int, command_name: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role_id FROM command_permissions WHERE guild_id = ? AND command_name = ?",
        (guild_id, command_name),
    )
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def add_command_permission(guild_id: int, command_name: str, role_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO command_permissions (guild_id, command_name, role_id) VALUES (?, ?, ?)",
        (guild_id, command_name, role_id),
    )
    conn.commit()
    conn.close()

def remove_command_permission(guild_id: int, command_name: str, role_id: int) -> bool:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM command_permissions WHERE guild_id = ? AND command_name = ? AND role_id = ?",
        (guild_id, command_name, role_id),
    )
    changed = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return changed

def reset_command_permissions(guild_id: int, command_name: str) -> bool:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM command_permissions WHERE guild_id = ? AND command_name = ?",
        (guild_id, command_name),
    )
    changed = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return changed

def list_command_permissions(guild_id: int):
    """Returns {command_name: [role_id, ...]} for every restricted command in this guild."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT command_name, role_id FROM command_permissions WHERE guild_id = ? ORDER BY command_name",
        (guild_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    result = {}
    for cmd, role_id in rows:
        result.setdefault(cmd, []).append(role_id)
    return result

# --- CUSTOM AUTO-RESPONDER ("NEW COMMAND") DB UTILITIES ---
def add_custom_command(guild_id: int, trigger: str, response: str, created_by: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO custom_commands (guild_id, trigger, response, created_by) VALUES (?, ?, ?, ?)
        ON CONFLICT(guild_id, trigger) DO UPDATE SET response = ?, created_by = ?
        """,
        (guild_id, trigger, response, created_by, response, created_by),
    )
    conn.commit()
    conn.close()

def remove_custom_command(guild_id: int, trigger: str) -> bool:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM custom_commands WHERE guild_id = ? AND trigger = ?", (guild_id, trigger))
    changed = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return changed

def get_custom_command(guild_id: int, trigger: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT response FROM custom_commands WHERE guild_id = ? AND trigger = ?", (guild_id, trigger))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def list_custom_commands(guild_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT trigger, response FROM custom_commands WHERE guild_id = ? ORDER BY trigger", (guild_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

# ================= DISCORD TOGGLE DB UTILS (SQLite only) =================
async def is_feature_disabled(guild_id: int, feature: str, type: str = 'command') -> bool:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM disabled_features WHERE guild_id = ? AND feature_name = ? AND type = ?", (guild_id, feature, type))
    row = cursor.fetchone()
    conn.close()
    return row is not None

async def disable_feature(guild_id: int, feature: str, type: str = 'command'):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO disabled_features (guild_id, feature_name, type) VALUES (?, ?, ?)", (guild_id, feature, type))
    conn.commit()
    conn.close()

async def enable_feature(guild_id: int, feature: str, type: str = 'command'):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM disabled_features WHERE guild_id = ? AND feature_name = ? AND type = ?", (guild_id, feature, type))
    conn.commit()
    conn.close()


# --- VOUCH CHANNEL CONFIG (was defined near vouch commands in original) ---
def get_vouch_channel(guild_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT vouch_channel_id FROM server_config WHERE guild_id = ?", (guild_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        return row[0]
    return None

def set_vouch_channel(guild_id: int, channel_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO server_config (guild_id, welcome_channel_id, log_channel_id, vouch_channel_id)
        VALUES (?, 0, 0, ?)
        ON CONFLICT(guild_id) DO UPDATE SET vouch_channel_id = ?
    """, (guild_id, channel_id, channel_id))
    conn.commit()
    conn.close()

def clear_vouch_channel(guild_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE server_config SET vouch_channel_id = NULL WHERE guild_id = ?", (guild_id,))
    conn.commit()
    conn.close()


# ================= REVENUE TRACKING SYSTEM =================
def add_revenue_entry(guild_id: int, user_id: int, user_name: str, service: str, payment_method: str, paid_to_id: int, paid_to_name: str, done_by_id: int, done_by_name: str, recorded_by_id: int):
    """Add a new revenue entry to the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO revenue_entries (guild_id, user_id, user_name, service, payment_method, paid_to_id, paid_to_name, done_by_id, done_by_name, recorded_by_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (guild_id, user_id, user_name, service, payment_method, paid_to_id, paid_to_name, done_by_id, done_by_name, recorded_by_id, datetime.datetime.now(UTC).isoformat())
    )
    conn.commit()
    conn.close()

def get_revenue_entries(guild_id: int, days: int = None, start_date: str = None, end_date: str = None):
    """Get revenue entries with optional date filtering.
    
    Args:
        guild_id: Server ID
        days: Number of days to look back (e.g., 7 for week, 30 for month)
        start_date: ISO format start date (overrides days)
        end_date: ISO format end date (overrides days)
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    if start_date and end_date:
        cursor.execute(
            """
            SELECT user_id, user_name, service, payment_method, paid_to_id, paid_to_name, done_by_id, done_by_name, recorded_by_id, created_at
            FROM revenue_entries
            WHERE guild_id = ? AND created_at BETWEEN ? AND ?
            ORDER BY created_at DESC
            """,
            (guild_id, start_date, end_date)
        )
    elif days:
        cutoff = (datetime.datetime.now(UTC) - datetime.timedelta(days=days)).isoformat()
        cursor.execute(
            """
            SELECT user_id, user_name, service, payment_method, paid_to_id, paid_to_name, done_by_id, done_by_name, recorded_by_id, created_at
            FROM revenue_entries
            WHERE guild_id = ? AND created_at >= ?
            ORDER BY created_at DESC
            """,
            (guild_id, cutoff)
        )
    else:
        cursor.execute(
            """
            SELECT user_id, user_name, service, payment_method, paid_to_id, paid_to_name, done_by_id, done_by_name, recorded_by_id, created_at
            FROM revenue_entries
            WHERE guild_id = ?
            ORDER BY created_at DESC
            """,
            (guild_id,)
        )
    
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_revenue_summary_by_staff(guild_id: int, days: int = None):
    """Get revenue summary grouped by staff member (paid_to)."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    if days:
        cutoff = (datetime.datetime.now(UTC) - datetime.timedelta(days=days)).isoformat()
        cursor.execute(
            """
            SELECT paid_to_id, paid_to_name, payment_method, COUNT(*) as count
            FROM revenue_entries
            WHERE guild_id = ? AND created_at >= ?
            GROUP BY paid_to_id, paid_to_name, payment_method
            ORDER BY paid_to_id, paid_to_name, payment_method
            """,
            (guild_id, cutoff)
        )
    else:
        cursor.execute(
            """
            SELECT paid_to_id, paid_to_name, payment_method, COUNT(*) as count
            FROM revenue_entries
            WHERE guild_id = ?
            GROUP BY paid_to_id, paid_to_name, payment_method
            ORDER BY paid_to_id, paid_to_name, payment_method
            """,
            (guild_id,)
        )
    
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_revenue_channel(guild_id: int):
    """Get the revenue tracking channel ID for this server."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT revenue_channel_id FROM server_config WHERE guild_id = ?", (guild_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] else None

def set_revenue_channel(guild_id: int, channel_id: int):
    """Set the revenue tracking channel for this server."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO server_config (guild_id, welcome_channel_id, log_channel_id, revenue_channel_id)
        VALUES (?, 0, 0, ?)
        ON CONFLICT(guild_id) DO UPDATE SET revenue_channel_id = ?
    """, (guild_id, channel_id, channel_id))
    conn.commit()
    conn.close()

def clear_revenue_channel(guild_id: int):
    """Clear the revenue tracking channel for this server."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE server_config SET revenue_channel_id = NULL WHERE guild_id = ?", (guild_id,))
    conn.commit()
    conn.close()


# ================= BOT CONTROL SYSTEM =================
def add_bot_owner(user_id: int, username: str):
    """Add a bot owner."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO bot_owners (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    conn.close()

def remove_bot_owner(user_id: int) -> bool:
    """Remove a bot owner. Returns True if removed, False if not found."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bot_owners WHERE user_id = ?", (user_id,))
    changed = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return changed

def is_bot_owner(user_id: int) -> bool:
    """Check if user is a bot owner."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM bot_owners WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def get_bot_owners():
    """Get all bot owners. Returns list of (user_id, username) tuples."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username FROM bot_owners")
    rows = cursor.fetchall()
    conn.close()
    return rows


# ================= REVENUE MANAGER SYSTEM =================
def add_revenue_manager(guild_id: int, user_id: int, username: str):
    """Add a revenue manager for a guild."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO revenue_managers (guild_id, user_id, username, added_at) VALUES (?, ?, ?, ?)", 
                   (guild_id, user_id, username, datetime.datetime.now(UTC).isoformat()))
    conn.commit()
    conn.close()

def remove_revenue_manager(guild_id: int, user_id: int) -> bool:
    """Remove a revenue manager. Returns True if removed, False if not found."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM revenue_managers WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
    changed = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return changed

def get_revenue_managers(guild_id: int):
    """Get all revenue managers for a guild. Returns list of (user_id, username) tuples."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username FROM revenue_managers WHERE guild_id = ?", (guild_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_all_revenue_managers():
    """Get all revenue managers across all guilds. Returns list of (guild_id, user_id, username, added_at) tuples."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT guild_id, user_id, username, added_at FROM revenue_managers")
    rows = cursor.fetchall()
    conn.close()
    return rows

def update_last_reminder(guild_id: int, user_id: int):
    """Update the last reminder timestamp for a revenue manager."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE revenue_managers SET last_reminder = ? WHERE guild_id = ? AND user_id = ?",
                   (datetime.datetime.now(UTC).isoformat(), guild_id, user_id))
    conn.commit()
    conn.close()


# ================= BOT SETTINGS =================
def is_owner_only_mode() -> bool:
    """Check if bot is in owner-only mode."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM bot_settings WHERE key = 'owner_only_mode'")
    row = cursor.fetchone()
    conn.close()
    return row and row[0] == '1'

def set_owner_only_mode(enabled: bool):
    """Set owner-only mode on/off."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO bot_settings (key, value) VALUES ('owner_only_mode', ?)
        ON CONFLICT(key) DO UPDATE SET value = ?
    """, ('1' if enabled else '0', '1' if enabled else '0'))
    conn.commit()
    conn.close()

def is_noprefix_enabled() -> bool:
    """Check if no-prefix system is enabled."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM bot_settings WHERE key = 'noprefix_enabled'")
    row = cursor.fetchone()
    conn.close()
    # Default to enabled (True) if not set
    return not row or row[0] == '1'

def set_noprefix_enabled(enabled: bool):
    """Enable/disable no-prefix system."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO bot_settings (key, value) VALUES ('noprefix_enabled', ?)
        ON CONFLICT(key) DO UPDATE SET value = ?
    """, ('1' if enabled else '0', '1' if enabled else '0'))
    conn.commit()
    conn.close()

def list_disabled_features(guild_id: int, type: str = 'command'):
    """List all disabled features for a guild. Returns list of feature names."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT feature_name FROM disabled_features WHERE guild_id = ? AND type = ?", (guild_id, type))
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]
