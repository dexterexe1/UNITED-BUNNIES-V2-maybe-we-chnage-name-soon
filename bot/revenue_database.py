"""
revenue_database.py — Revenue tracking using MongoDB.
Stores revenue data in the same MongoDB as other bot data.
"""
import os
import datetime
from typing import List, Dict, Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

UTC = datetime.timezone.utc

# MongoDB connection - use same env var as mongo_bridge.py
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URL")
MONGO_DB = os.getenv("MONGO_DB", "bunnydb")  # Use same default as mongo_bridge.py

client = None
db: AsyncIOMotorDatabase = None

async def init_revenue_db():
    """Initialize MongoDB connection for revenue tracking."""
    global client, db
    
    if not MONGO_URI:
        print("⚠️ MONGO_URI not set - revenue tracking disabled")
        return
    
    try:
        print(f"🔗 Connecting to MongoDB for revenue tracking...")
        client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=8000)
        db = client[MONGO_DB]
        
        # Test connection
        await db.command("ping")
        print(f"✅ Revenue MongoDB connected to database: {MONGO_DB}")
        
        # Create collections if they don't exist
        collections = await db.list_collection_names()
        
        if "revenue_entries" not in collections:
            await db.create_collection("revenue_entries")
            await db["revenue_entries"].create_index("guild_id")
            await db["revenue_entries"].create_index("timestamp")
            print("✅ Created revenue_entries collection")
        
        if "revenue_channels" not in collections:
            await db.create_collection("revenue_channels")
            await db["revenue_channels"].create_index("guild_id", unique=True)
            print("✅ Created revenue_channels collection")

        if "revenue_managers" not in collections:
            await db.create_collection("revenue_managers")
            await db["revenue_managers"].create_index("guild_id", unique=True)
            await db["revenue_managers"].create_index("next_weekly_dm_at")
            print("✅ Created revenue_managers collection")
        
        print("✅ Revenue database initialized successfully!")
    except Exception as e:
        print(f"❌ Revenue MongoDB initialization failed: {e}")
        raise

# ==========================================
#         REVENUE CHANNEL MANAGEMENT
# ==========================================

async def set_revenue_channel(guild_id: int, channel_id: int, setup_by: int) -> bool:
    """Set the revenue tracking channel for a guild. Returns True on success."""
    if db is None:
        print("❌ Revenue DB not initialized")
        return False
    
    try:
        result = await db["revenue_channels"].update_one(
            {"guild_id": guild_id},
            {
                "$set": {
                    "channel_id": channel_id,
                    "setup_by": setup_by,
                    "setup_at": datetime.datetime.now(UTC)
                }
            },
            upsert=True
        )
        print(f"✅ Revenue channel set: guild={guild_id}, channel={channel_id}")
        return True
    except Exception as e:
        print(f"❌ Failed to set revenue channel: {e}")
        return False

async def get_revenue_channel(guild_id: int) -> Optional[int]:
    """Get the revenue channel ID for a guild."""
    if db is None:
        return None
    
    try:
        result = await db["revenue_channels"].find_one({"guild_id": guild_id})
        return result["channel_id"] if result else None
    except Exception as e:
        print(f"⚠️ Failed to get revenue channel: {e}")
        return None

async def clear_revenue_channel(guild_id: int) -> bool:
    """Remove revenue tracking for a guild."""
    if db is None:
        return False
    
    try:
        result = await db["revenue_channels"].delete_one({"guild_id": guild_id})
        return result.deleted_count > 0
    except Exception as e:
        print(f"⚠️ Failed to clear revenue channel: {e}")
        return False


# ==========================================
#         REVENUE MANAGER MANAGEMENT
# ==========================================

async def set_revenue_manager(guild_id: int, manager_user_id: int, setup_by: int) -> bool:
    """Assign one revenue manager for a guild and schedule weekly reminders."""
    if db is None:
        return False
    try:
        now = datetime.datetime.now(UTC)
        next_dm = now + datetime.timedelta(days=7)
        result = await db["revenue_managers"].update_one(
            {"guild_id": guild_id},
            {"$set": {
                "manager_user_id": int(manager_user_id),
                "setup_by": int(setup_by),
                "setup_at": now,
                "last_weekly_dm_at": None,
                "next_weekly_dm_at": next_dm,
            }},
            upsert=True,
        )
        print(f"✅ Revenue manager set: guild={guild_id}, manager={manager_user_id}")
        return result.acknowledged
    except Exception as e:
        print(f"❌ Failed to set revenue manager: {e}")
        return False


async def get_revenue_manager(guild_id: int) -> Optional[int]:
    """Get the assigned revenue manager user ID for a guild."""
    if db is None:
        return None
    try:
        result = await db["revenue_managers"].find_one({"guild_id": guild_id})
        return int(result["manager_user_id"]) if result and result.get("manager_user_id") else None
    except Exception as e:
        print(f"⚠️ Failed to get revenue manager: {e}")
        return None


async def get_revenue_managers_due(now: Optional[datetime.datetime] = None) -> List[Dict]:
    """Return revenue managers whose weekly private reminder is due."""
    if db is None:
        return []
    try:
        now = now or datetime.datetime.now(UTC)
        cursor = db["revenue_managers"].find({
            "next_weekly_dm_at": {"$lte": now}
        })
        return await cursor.to_list(length=None)
    except Exception as e:
        print(f"⚠️ Failed to get due revenue managers: {e}")
        return []


async def mark_revenue_manager_weekly_dm(manager_id, *, sent_at: Optional[datetime.datetime] = None, retry_days: int = 7) -> bool:
    """Move the next weekly reminder forward after a send attempt."""
    if db is None or manager_id is None:
        return False
    try:
        from bson import ObjectId
        now = sent_at or datetime.datetime.now(UTC)
        result = await db["revenue_managers"].update_one(
            {"_id": ObjectId(manager_id) if isinstance(manager_id, str) else manager_id},
            {"$set": {
                "last_weekly_dm_at": now,
                "next_weekly_dm_at": now + datetime.timedelta(days=retry_days),
            }}
        )
        return result.matched_count > 0
    except Exception as e:
        print(f"⚠️ Failed to update revenue manager reminder: {e}")
        return False

# ==========================================
#         REVENUE ENTRY MANAGEMENT
# ==========================================

async def add_revenue_entry(
    guild_id: int,
    user_name: str,
    service: str,
    payment: str,
    paid_to: str,
    done_by_id: Optional[int] = None,
    done_by_name: Optional[str] = None,
    done_at: Optional[datetime.datetime] = None,
    message_id: Optional[int] = None,
    channel_id: Optional[int] = None,
    payment_value: Optional[float] = None,
    payment_value_name: Optional[str] = None,
    payment_value_checked_at: Optional[datetime.datetime] = None
) -> None:
    """Add a new revenue entry."""
    if db is None:
        return
    
    try:
        await db["revenue_entries"].insert_one({
            "guild_id": guild_id,
            "user_name": user_name,
            "client_name": user_name,
            "service": service,
            "payment": payment,
            "paid_to": paid_to,
            "done_by_id": done_by_id,
            "done_by_name": done_by_name,
            "done_at": done_at,
            "message_id": message_id,
            "channel_id": channel_id,
            "payment_value": payment_value,
            "payment_value_name": payment_value_name,
            "payment_value_checked_at": payment_value_checked_at,
            "timestamp": datetime.datetime.now(UTC)
        })
    except Exception as e:
        print(f"⚠️ Failed to add revenue entry: {e}")

async def get_revenue_entries(
    guild_id: int,
    days: Optional[int] = None,
    staff_name: Optional[str] = None
) -> List[Dict]:
    """Get revenue entries with optional filtering."""
    if db is None:
        return []
    
    try:
        query = {"guild_id": guild_id}
        
        if days:
            cutoff = datetime.datetime.now(UTC) - datetime.timedelta(days=days)
            query["timestamp"] = {"$gte": cutoff}
        
        if staff_name:
            query["$or"] = [
                {"paid_to": {"$regex": staff_name, "$options": "i"}},
                {"done_by_name": {"$regex": staff_name, "$options": "i"}}
            ]
        
        cursor = db["revenue_entries"].find(query).sort("timestamp", -1)
        results = await cursor.to_list(length=None)
        return results
    except Exception as e:
        print(f"⚠️ Failed to get revenue entries: {e}")
        return []

async def get_revenue_summary(guild_id: int, days: Optional[int] = None) -> dict:
    """Get revenue summary grouped by staff and payment type."""
    if db is None:
        return {}
    
    try:
        match_query = {"guild_id": guild_id}
        
        if days:
            cutoff = datetime.datetime.now(UTC) - datetime.timedelta(days=days)
            match_query["timestamp"] = {"$gte": cutoff}
        
        pipeline = [
            {"$match": match_query},
            {
                "$group": {
                    "_id": {"paid_to": "$paid_to", "payment": "$payment"},
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"_id.paid_to": 1, "count": -1}}
        ]
        
        results = await db["revenue_entries"].aggregate(pipeline).to_list(length=None)
        
        # Group by staff member
        summary = {}
        for doc in results:
            paid_to = doc["_id"]["paid_to"]
            payment = doc["_id"]["payment"]
            count = doc["count"]
            
            if paid_to not in summary:
                summary[paid_to] = {}
            summary[paid_to][payment] = count
        
        return summary
    except Exception as e:
        print(f"⚠️ Failed to get revenue summary: {e}")
        return {}

async def get_multi_staff_entries(guild_id: int, days: Optional[int] = None) -> List[Dict]:
    """Get entries where multiple staff were involved (done_by is set)."""
    if db is None:
        return []
    
    try:
        query = {"guild_id": guild_id, "done_by_id": {"$ne": None}}
        
        if days:
            cutoff = datetime.datetime.now(UTC) - datetime.timedelta(days=days)
            query["timestamp"] = {"$gte": cutoff}
        
        cursor = db["revenue_entries"].find(query).sort("timestamp", -1)
        results = await cursor.to_list(length=None)
        return results
    except Exception as e:
        print(f"⚠️ Failed to get multi-staff entries: {e}")
        return []

async def delete_revenue_entry(entry_id: str) -> bool:
    """Delete a revenue entry by ID."""
    if db is None:
        return False
    
    try:
        from bson import ObjectId
        result = await db["revenue_entries"].delete_one({"_id": ObjectId(entry_id)})
        return result.deleted_count > 0
    except Exception as e:
        print(f"⚠️ Failed to delete revenue entry: {e}")
        return False

async def clear_revenue_data(guild_id: int) -> int:
    """Delete all revenue entries for one guild only.

    Returns the number of deleted entries. Revenue channel configuration is
    intentionally preserved so clearing history does not disable tracking.
    """
    if db is None:
        return 0

    try:
        result = await db["revenue_entries"].delete_many({"guild_id": guild_id})
        print(
            f"🧹 Cleared revenue data: guild={guild_id}, "
            f"deleted={result.deleted_count}"
        )
        return result.deleted_count
    except Exception as e:
        print(f"⚠️ Failed to clear revenue data for guild {guild_id}: {e}")
        return 0


async def update_revenue_payment_value(
    entry_id,
    payment_value: float,
    payment_value_name: Optional[str],
    payment_value_checked_at: Optional[datetime.datetime],
) -> bool:
    """Backfill a calculated payment value on an existing revenue entry."""
    if db is None or entry_id is None:
        return False
    try:
        result = await db["revenue_entries"].update_one(
            {"_id": entry_id},
            {"$set": {
                "payment_value": float(payment_value),
                "payment_value_name": payment_value_name,
                "payment_value_checked_at": payment_value_checked_at,
            }}
        )
        return result.modified_count > 0 or result.matched_count > 0
    except Exception as e:
        print(f"⚠️ Failed to backfill revenue payment value: {e}")
        return False


async def get_total_entries_count(guild_id: int) -> int:
    """Get total number of revenue entries for a guild."""
    if db is None:
        return 0
    
    try:
        count = await db["revenue_entries"].count_documents({"guild_id": guild_id})
        return count
    except Exception as e:
        print(f"⚠️ Failed to get entry count: {e}")
        return 0
