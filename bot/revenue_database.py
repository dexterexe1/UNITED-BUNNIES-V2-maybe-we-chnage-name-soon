"""
revenue_database.py — Revenue tracking using MongoDB.
Stores revenue data in the same MongoDB as other bot data.
"""
import os
import datetime
from typing import List, Dict, Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

UTC = datetime.timezone.utc

# MongoDB connection
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
client = None
db: AsyncIOMotorDatabase = None

async def init_revenue_db():
    """Initialize MongoDB connection for revenue tracking."""
    global client, db
    try:
        client = AsyncIOMotorClient(MONGODB_URL)
        db = client["united_bunnies"]
        
        # Create collections if they don't exist
        collections = await db.list_collection_names()
        
        if "revenue_entries" not in collections:
            await db.create_collection("revenue_entries")
            await db["revenue_entries"].create_index("guild_id")
            await db["revenue_entries"].create_index("timestamp")
        
        if "revenue_channels" not in collections:
            await db.create_collection("revenue_channels")
            await db["revenue_channels"].create_index("guild_id", unique=True)
        
        print("✅ Revenue MongoDB initialized successfully!")
    except Exception as e:
        print(f"⚠️ Revenue MongoDB initialization failed: {e}")

# ==========================================
#         REVENUE CHANNEL MANAGEMENT
# ==========================================

async def set_revenue_channel(guild_id: int, channel_id: int, setup_by: int) -> None:
    """Set the revenue tracking channel for a guild."""
    if not db:
        return
    
    try:
        await db["revenue_channels"].update_one(
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
    except Exception as e:
        print(f"⚠️ Failed to set revenue channel: {e}")

async def get_revenue_channel(guild_id: int) -> Optional[int]:
    """Get the revenue channel ID for a guild."""
    if not db:
        return None
    
    try:
        result = await db["revenue_channels"].find_one({"guild_id": guild_id})
        return result["channel_id"] if result else None
    except Exception as e:
        print(f"⚠️ Failed to get revenue channel: {e}")
        return None

async def clear_revenue_channel(guild_id: int) -> bool:
    """Remove revenue tracking for a guild."""
    if not db:
        return False
    
    try:
        result = await db["revenue_channels"].delete_one({"guild_id": guild_id})
        return result.deleted_count > 0
    except Exception as e:
        print(f"⚠️ Failed to clear revenue channel: {e}")
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
    message_id: Optional[int] = None,
    channel_id: Optional[int] = None
) -> None:
    """Add a new revenue entry."""
    if not db:
        return
    
    try:
        await db["revenue_entries"].insert_one({
            "guild_id": guild_id,
            "user_name": user_name,
            "service": service,
            "payment": payment,
            "paid_to": paid_to,
            "done_by_id": done_by_id,
            "done_by_name": done_by_name,
            "message_id": message_id,
            "channel_id": channel_id,
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
    if not db:
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
    if not db:
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
    if not db:
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
    if not db:
        return False
    
    try:
        from bson import ObjectId
        result = await db["revenue_entries"].delete_one({"_id": ObjectId(entry_id)})
        return result.deleted_count > 0
    except Exception as e:
        print(f"⚠️ Failed to delete revenue entry: {e}")
        return False

async def get_total_entries_count(guild_id: int) -> int:
    """Get total number of revenue entries for a guild."""
    if not db:
        return 0
    
    try:
        count = await db["revenue_entries"].count_documents({"guild_id": guild_id})
        return count
    except Exception as e:
        print(f"⚠️ Failed to get entry count: {e}")
        return 0
