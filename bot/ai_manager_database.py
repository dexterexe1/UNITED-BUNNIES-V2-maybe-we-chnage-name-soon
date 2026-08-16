
"""Per-server premium AI Manager data layer.

All data is scoped by guild_id. The bot owner can enable the feature for any
guild the bot is currently in; the target server does not have to include the
bot owner as a member.
"""
from __future__ import annotations

import datetime as dt
import os
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

UTC = dt.timezone.utc
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URL")
MONGO_DB = os.getenv("MONGO_DB", "bunnydb")

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


async def init_ai_manager_db() -> bool:
    global _client, _db
    if _db is not None:
        return True
    if not MONGO_URI:
        print("⚠️ AI Manager: MONGO_URI not set - premium AI data is unavailable")
        return False
    try:
        _client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=8000)
        _db = _client[MONGO_DB]
        await _db.command("ping")
        names = await _db.list_collection_names()
        collections = {
            "ai_manager_servers": {"guild_id": True},
            "ai_manager_prices": {"guild_id": False},
            "ai_manager_rules": {"guild_id": False},
            "ai_manager_services": {"guild_id": False},
            "ai_manager_imports": {"guild_id": False},
        }
        for name, meta in collections.items():
            if name not in names:
                await _db.create_collection(name)
            if name == "ai_manager_servers":
                await _db[name].create_index("guild_id", unique=True)
            else:
                await _db[name].create_index("guild_id")
        print(f"✅ AI Manager MongoDB ready: {MONGO_DB}")
        return True
    except Exception as exc:
        print(f"❌ AI Manager MongoDB initialization failed: {exc}")
        _client = None
        _db = None
        return False


async def _ensure() -> Optional[AsyncIOMotorDatabase]:
    if _db is None:
        await init_ai_manager_db()
    return _db


async def get_server_config(guild_id: int) -> Dict[str, Any]:
    db = await _ensure()
    if db is None:
        return {
            "guild_id": int(guild_id),
            "ai_enabled": False,
            "nonprefix_enabled": False,
            "manager_role_id": None,
        }
    doc = await db["ai_manager_servers"].find_one({"guild_id": int(guild_id)})
    if not doc:
        return {
            "guild_id": int(guild_id),
            "ai_enabled": False,
            "nonprefix_enabled": False,
            "manager_role_id": None,
        }
    return doc


async def set_ai_enabled(guild_id: int, enabled: bool) -> bool:
    db = await _ensure()
    if db is None:
        return False
    now = dt.datetime.now(UTC)
    result = await db["ai_manager_servers"].update_one(
        {"guild_id": int(guild_id)},
        {"$set": {"ai_enabled": bool(enabled), "updated_at": now},
         "$setOnInsert": {"guild_id": int(guild_id), "nonprefix_enabled": False, "manager_role_id": None}},
        upsert=True,
    )
    return bool(result.acknowledged)


async def set_nonprefix_enabled(guild_id: int, enabled: bool) -> bool:
    db = await _ensure()
    if db is None:
        return False
    now = dt.datetime.now(UTC)
    result = await db["ai_manager_servers"].update_one(
        {"guild_id": int(guild_id)},
        {"$set": {"nonprefix_enabled": bool(enabled), "updated_at": now},
         "$setOnInsert": {"guild_id": int(guild_id), "ai_enabled": False, "manager_role_id": None}},
        upsert=True,
    )
    return bool(result.acknowledged)


async def set_manager_role(guild_id: int, role_id: Optional[int]) -> bool:
    db = await _ensure()
    if db is None:
        return False
    result = await db["ai_manager_servers"].update_one(
        {"guild_id": int(guild_id)},
        {"$set": {"manager_role_id": int(role_id) if role_id else None, "updated_at": dt.datetime.now(UTC)}},
        upsert=True,
    )
    return bool(result.acknowledged)


async def list_enabled_servers() -> List[Dict[str, Any]]:
    db = await _ensure()
    if db is None:
        return []
    return await db["ai_manager_servers"].find({"ai_enabled": True}).sort("guild_id", 1).to_list(length=None)


async def upsert_price(guild_id: int, service: str, price: str, notes: str = "") -> bool:
    db = await _ensure()
    if db is None:
        return False
    service = service.strip()
    if not service:
        return False
    result = await db["ai_manager_prices"].update_one(
        {"guild_id": int(guild_id), "service_key": service.casefold()},
        {"$set": {
            "guild_id": int(guild_id),
            "service": service,
            "price": price.strip(),
            "notes": notes.strip(),
            "updated_at": dt.datetime.now(UTC),
        }},
        upsert=True,
    )
    return bool(result.acknowledged)


async def list_prices(guild_id: int) -> List[Dict[str, Any]]:
    db = await _ensure()
    if db is None:
        return []
    return await db["ai_manager_prices"].find({"guild_id": int(guild_id)}).sort("service_key", 1).to_list(length=None)


async def remove_price(guild_id: int, service: str) -> bool:
    db = await _ensure()
    if db is None:
        return False
    result = await db["ai_manager_prices"].delete_one({"guild_id": int(guild_id), "service_key": service.strip().casefold()})
    return result.deleted_count > 0


async def clear_prices(guild_id: int) -> int:
    db = await _ensure()
    if db is None:
        return 0
    result = await db["ai_manager_prices"].delete_many({"guild_id": int(guild_id)})
    return int(result.deleted_count)


async def add_rule(guild_id: int, rule: str, category: str = "General") -> bool:
    db = await _ensure()
    if db is None:
        return False
    rule = rule.strip()
    if not rule:
        return False
    result = await db["ai_manager_rules"].insert_one({
        "guild_id": int(guild_id),
        "rule": rule,
        "category": category.strip() or "General",
        "created_at": dt.datetime.now(UTC),
    })
    return result.acknowledged


async def list_rules(guild_id: int) -> List[Dict[str, Any]]:
    db = await _ensure()
    if db is None:
        return []
    return await db["ai_manager_rules"].find({"guild_id": int(guild_id)}).sort("_id", 1).to_list(length=None)


async def remove_rule(guild_id: int, index: int) -> bool:
    db = await _ensure()
    if db is None:
        return False
    docs = await list_rules(guild_id)
    if index < 1 or index > len(docs):
        return False
    result = await db["ai_manager_rules"].delete_one({"_id": docs[index - 1]["_id"]})
    return result.deleted_count > 0


async def clear_rules(guild_id: int) -> int:
    db = await _ensure()
    if db is None:
        return 0
    result = await db["ai_manager_rules"].delete_many({"guild_id": int(guild_id)})
    return int(result.deleted_count)


async def add_service(guild_id: int, service: str, description: str = "") -> bool:
    db = await _ensure()
    if db is None:
        return False
    service = service.strip()
    if not service:
        return False
    result = await db["ai_manager_services"].update_one(
        {"guild_id": int(guild_id), "service_key": service.casefold()},
        {"$set": {
            "guild_id": int(guild_id),
            "service": service,
            "description": description.strip(),
            "updated_at": dt.datetime.now(UTC),
        }},
        upsert=True,
    )
    return bool(result.acknowledged)


async def list_services(guild_id: int) -> List[Dict[str, Any]]:
    db = await _ensure()
    if db is None:
        return []
    return await db["ai_manager_services"].find({"guild_id": int(guild_id)}).sort("service_key", 1).to_list(length=None)


async def remove_service(guild_id: int, service: str) -> bool:
    db = await _ensure()
    if db is None:
        return False
    result = await db["ai_manager_services"].delete_one({"guild_id": int(guild_id), "service_key": service.strip().casefold()})
    return result.deleted_count > 0


async def clear_services(guild_id: int) -> int:
    db = await _ensure()
    if db is None:
        return 0
    result = await db["ai_manager_services"].delete_many({"guild_id": int(guild_id)})
    return int(result.deleted_count)


async def add_import(guild_id: int, kind: str, title: str, content: str) -> bool:
    db = await _ensure()
    if db is None:
        return False
    result = await db["ai_manager_imports"].insert_one({
        "guild_id": int(guild_id),
        "kind": kind,
        "title": title.strip() or ("Prices" if kind == "price" else "Rules"),
        "content": content,
        "created_at": dt.datetime.now(UTC),
    })
    return result.acknowledged


async def list_imports(guild_id: int, kind: Optional[str] = None) -> List[Dict[str, Any]]:
    db = await _ensure()
    if db is None:
        return []
    query: Dict[str, Any] = {"guild_id": int(guild_id)}
    if kind:
        query["kind"] = kind
    return await db["ai_manager_imports"].find(query).sort("created_at", -1).to_list(length=None)


async def clear_imports(guild_id: int, kind: Optional[str] = None) -> int:
    db = await _ensure()
    if db is None:
        return 0
    query: Dict[str, Any] = {"guild_id": int(guild_id)}
    if kind:
        query["kind"] = kind
    result = await db["ai_manager_imports"].delete_many(query)
    return int(result.deleted_count)


async def clear_all(guild_id: int) -> Dict[str, int]:
    return {
        "prices": await clear_prices(guild_id),
        "rules": await clear_rules(guild_id),
        "services": await clear_services(guild_id),
        "imports": await clear_imports(guild_id),
    }


async def get_ai_context(guild_id: int, max_chars: int = 50000) -> str:
    """Build compact, server-local context for the AI manager."""
    config = await get_server_config(guild_id)
    prices = await list_prices(guild_id)
    rules = await list_rules(guild_id)
    services = await list_services(guild_id)
    imports = await list_imports(guild_id)

    parts = [
        "SERVER AI CONFIGURATION (ONLY FOR THIS SERVER)",
        f"AI enabled: {config.get('ai_enabled', False)}",
        "",
        "SERVICES:",
    ]
    parts.extend(
        f"- {x.get('service')}: {x.get('description')}" if x.get("description") else f"- {x.get('service')}"
        for x in services
    )
    parts.append("")
    parts.append("PRICES:")
    parts.extend(
        f"- {x.get('service')}: {x.get('price')}" + (f" ({x.get('notes')})" if x.get("notes") else "")
        for x in prices
    )
    parts.append("")
    parts.append("RULES:")
    parts.extend(
        f"- [{x.get('category', 'General')}] {x.get('rule')}" for x in rules
    )

    for item in imports:
        parts.append("")
        parts.append(f"IMPORTED {str(item.get('kind', 'data')).upper()} — {item.get('title')}:")
        parts.append(str(item.get("content") or ""))

    text = "\n".join(parts)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n[Context truncated by server AI manager.]"
