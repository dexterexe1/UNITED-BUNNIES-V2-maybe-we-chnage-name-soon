"""
setup_pc_revenue_db.py — Setup script to connect bot to your PC's revenue database.

INSTRUCTIONS:
1. Run this on your PC to set up the revenue database
2. Set up remote access (port forwarding or ngrok)
3. Add environment variables to Render

This allows the bot (hosted on Render) to store revenue data on your PC.
"""
import sqlite3
import os
from pathlib import Path

def setup_local_revenue_db():
    """Set up revenue database on your PC."""
    
    # Create revenue database in a specific folder
    db_folder = Path.home() / "UnitedBunniesBot"
    db_folder.mkdir(exist_ok=True)
    
    db_path = db_folder / "revenue_data.db"
    
    print(f"Creating revenue database at: {db_path}")
    
    # Initialize the database
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Revenue entries table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS revenue_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_name TEXT NOT NULL,
            service TEXT NOT NULL,
            payment TEXT NOT NULL,
            paid_to TEXT NOT NULL,
            done_by_id INTEGER,
            done_by_name TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            message_id INTEGER,
            channel_id INTEGER
        )
    """)
    
    # Revenue channels table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS revenue_channels (
            guild_id INTEGER PRIMARY KEY,
            channel_id INTEGER NOT NULL,
            setup_by INTEGER NOT NULL,
            setup_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    
    print("✅ Revenue database created successfully!")
    print(f"📂 Database location: {db_path}")
    print()
    print("🌐 NEXT STEPS:")
    print("1. Install ngrok: https://ngrok.com/download")
    print("2. Run: ngrok tcp 5432")
    print("3. Copy the forwarding URL (e.g., tcp://0.tcp.ngrok.io:12345)")
    print("4. Add to Render environment variables:")
    print(f"   REVENUE_DB_PATH = {db_path}")
    print()
    print("OR use a free remote database service like Supabase for easier setup.")

if __name__ == "__main__":
    setup_local_revenue_db()