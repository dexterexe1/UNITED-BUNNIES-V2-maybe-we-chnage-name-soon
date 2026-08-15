"""
revenue_database.py — Separate database ONLY for revenue tracking.
This database can be hosted on Supabase (PostgreSQL) while other data stays in MongoDB.
"""
import os
import datetime
from typing import List, Tuple, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

UTC = datetime.timezone.utc

# Environment variable for revenue database connection
REVENUE_DB_URL = os.getenv("REVENUE_DB_URL", "postgresql://localhost/revenue_data")

def get_connection():
    """Get database connection."""
    return psycopg2.connect(REVENUE_DB_URL, cursor_factory=RealDictCursor)

def init_revenue_db():
    """Initialize the revenue-only database."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Revenue entries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS revenue_entries (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                user_name TEXT NOT NULL,
                service TEXT NOT NULL,
                payment TEXT NOT NULL,
                paid_to TEXT NOT NULL,
                done_by_id BIGINT,
                done_by_name TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                message_id BIGINT,
                channel_id BIGINT
            )
        """)
        
        # Revenue channels table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS revenue_channels (
                guild_id BIGINT PRIMARY KEY,
                channel_id BIGINT NOT NULL,
                setup_by BIGINT NOT NULL,
                setup_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
        print("✅ Revenue database initialized successfully!")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")

# ==========================================
#         REVENUE CHANNEL MANAGEMENT
# ==========================================

def set_revenue_channel(guild_id: int, channel_id: int, setup_by: int) -> None:
    """Set the revenue tracking channel for a guild."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO revenue_channels (guild_id, channel_id, setup_by)
        VALUES (%s, %s, %s)
        ON CONFLICT (guild_id) DO UPDATE SET 
            channel_id = EXCLUDED.channel_id,
            setup_by = EXCLUDED.setup_by,
            setup_at = CURRENT_TIMESTAMP
    """, (guild_id, channel_id, setup_by))
    conn.commit()
    conn.close()

def get_revenue_channel(guild_id: int) -> Optional[int]:
    """Get the revenue channel ID for a guild."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id FROM revenue_channels WHERE guild_id = %s", (guild_id,))
    result = cursor.fetchone()
    conn.close()
    return result['channel_id'] if result else None

def clear_revenue_channel(guild_id: int) -> bool:
    """Remove revenue tracking for a guild."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM revenue_channels WHERE guild_id = %s", (guild_id,))
    changed = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return changed

# ==========================================
#         REVENUE ENTRY MANAGEMENT
# ==========================================

def add_revenue_entry(
    guild_id: int,
    user_name: str,
    service: str,
    payment: str,
    paid_to: str,
    done_by_id: Optional[int] = None,
    done_by_name: Optional[str] = None,
    message_id: Optional[int] = None,
    channel_id: Optional[int] = None
) -> None:
    """Add a new revenue entry."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO revenue_entries 
        (guild_id, user_name, service, payment, paid_to, done_by_id, done_by_name, message_id, channel_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (guild_id, user_name, service, payment, paid_to, done_by_id, done_by_name, message_id, channel_id))
    conn.commit()
    conn.close()

def get_revenue_entries(
    guild_id: int,
    days: Optional[int] = None,
    staff_name: Optional[str] = None
) -> List[dict]:
    """Get revenue entries with optional filtering."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM revenue_entries WHERE guild_id = %s"
    params = [guild_id]
    
    if days:
        query += " AND timestamp >= CURRENT_TIMESTAMP - INTERVAL '%s days'"
        params.append(days)
    
    if staff_name:
        query += " AND (paid_to ILIKE %s OR done_by_name ILIKE %s)"
        params.extend([f"%{staff_name}%", f"%{staff_name}%"])
    
    query += " ORDER BY timestamp DESC"
    
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    return [dict(row) for row in results]

def get_revenue_summary(guild_id: int, days: Optional[int] = None) -> dict:
    """Get revenue summary grouped by staff and payment type."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT paid_to, payment, COUNT(*) as count
        FROM revenue_entries 
        WHERE guild_id = %s
    """
    params = [guild_id]
    
    if days:
        query += " AND timestamp >= CURRENT_TIMESTAMP - INTERVAL '%s days'"
        params.append(days)
    
    query += " GROUP BY paid_to, payment ORDER BY paid_to, count DESC"
    
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    
    # Group by staff member
    summary = {}
    for row in results:
        paid_to = row['paid_to']
        payment = row['payment']
        count = row['count']
        
        if paid_to not in summary:
            summary[paid_to] = {}
        summary[paid_to][payment] = count
    
    return summary

def get_multi_staff_entries(guild_id: int, days: Optional[int] = None) -> List[dict]:
    """Get entries where multiple staff were involved (done_by is set)."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT * FROM revenue_entries 
        WHERE guild_id = %s AND done_by_id IS NOT NULL
    """
    params = [guild_id]
    
    if days:
        query += " AND timestamp >= CURRENT_TIMESTAMP - INTERVAL '%s days'"
        params.append(days)
    
    query += " ORDER BY timestamp DESC"
    
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    return [dict(row) for row in results]

def delete_revenue_entry(entry_id: int) -> bool:
    """Delete a revenue entry by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM revenue_entries WHERE id = %s", (entry_id,))
    changed = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return changed

def get_total_entries_count(guild_id: int) -> int:
    """Get total number of revenue entries for a guild."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM revenue_entries WHERE guild_id = %s", (guild_id,))
    result = cursor.fetchone()
    conn.close()
    return result['count'] if result else 0

# Initialize database on import (with error handling)
try:
    init_revenue_db()
except Exception as e:
    print(f"Revenue database initialization skipped: {e}")