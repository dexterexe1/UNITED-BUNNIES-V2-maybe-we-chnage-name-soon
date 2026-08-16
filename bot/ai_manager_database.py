from __future__ import annotations

import os
from typing import Any

try:
    from motor.motor_asyncio import AsyncIOMotorClient
except ImportError:
    AsyncIOMotorClient = None

MONGO_URI = os.getenv('MONGO_URI') or os.getenv('MONGODB_URL')
MONGO_DB = os.getenv('MONGO_DB', 'bunnydb')
COLLECTION = 'aiManagerGuilds'

_client = None
_db = None

DEFAULT = {
    'guildId': 0,
    'aiEnabled': False,
    'nonPrefixEnabled': False,
    'managerRoleId': None,
    'prices': [],
    'rules': [],
    'services': [],
    'priceSheets': [],
    'ruleSheets': [],
}


def _doc(guild_id: int) -> dict[str, Any]:
    return {**DEFAULT, 'guildId': int(guild_id)}


async def connect() -> bool:
    global _client, _db
    if _db is not None:
        return True
    if not MONGO_URI or AsyncIOMotorClient is None:
        return False
    try:
        _client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=8000)
        _db = _client[MONGO_DB]
        await _db.command('ping')
        print(f'✅ AI Manager Mongo connected ({MONGO_DB})')
        return True
    except Exception as exc:
        print(f'⚠️ AI Manager Mongo connection failed: {exc}')
        _client = None
        _db = None
        return False


async def init() -> bool:
    return await connect()


async def get_guild(guild_id: int) -> dict[str, Any]:
    if not await connect():
        return _doc(guild_id)
    found = await _db[COLLECTION].find_one({'guildId': int(guild_id)})
    if not found:
        found = _doc(guild_id)
        await _db[COLLECTION].insert_one(found.copy())
    found.pop('_id', None)
    for key, default in DEFAULT.items():
        found.setdefault(key, default if key not in {'prices', 'rules', 'services'} else list(default))
    return found


async def update_guild(guild_id: int, updates: dict[str, Any]) -> dict[str, Any]:
    if not await connect():
        merged = _doc(guild_id)
        merged.update(updates)
        return merged
    await _db[COLLECTION].update_one(
        {'guildId': int(guild_id)},
        {'$set': updates},
        upsert=True,
    )
    return await get_guild(guild_id)


async def set_ai_enabled(guild_id: int, enabled: bool):
    return await update_guild(guild_id, {'aiEnabled': bool(enabled)})


async def set_nonprefix_enabled(guild_id: int, enabled: bool):
    return await update_guild(guild_id, {'nonPrefixEnabled': bool(enabled)})


async def set_manager_role(guild_id: int, role_id: int | None):
    return await update_guild(guild_id, {'managerRoleId': role_id})


async def clear_category(guild_id: int, category: str):
    if category not in {'prices', 'rules', 'services'}:
        raise ValueError(category)
    return await update_guild(guild_id, {category: []})


async def add_price(guild_id: int, service: str, price: str):
    data = await get_guild(guild_id)
    rows = list(data.get('prices') or [])
    service_key = service.strip().casefold()
    rows = [r for r in rows if str(r.get('service', '')).strip().casefold() != service_key]
    rows.append({'service': service.strip(), 'price': price.strip()})
    return await update_guild(guild_id, {'prices': rows})


async def remove_price(guild_id: int, service: str):
    data = await get_guild(guild_id)
    service_key = service.strip().casefold()
    rows = [r for r in (data.get('prices') or []) if str(r.get('service', '')).strip().casefold() != service_key]
    changed = len(rows) != len(data.get('prices') or [])
    await update_guild(guild_id, {'prices': rows})
    return changed


async def add_price_sheet(guild_id: int, title: str, text: str):
    data = await get_guild(guild_id)
    rows = list(data.get('priceSheets') or [])
    rows.append({'title': title.strip(), 'text': text.strip()})
    return await update_guild(guild_id, {'priceSheets': rows})


async def add_rule_sheet(guild_id: int, title: str, text: str):
    data = await get_guild(guild_id)
    rows = list(data.get('ruleSheets') or [])
    rows.append({'title': title.strip(), 'text': text.strip()})
    return await update_guild(guild_id, {'ruleSheets': rows})


async def clear_price_sheets(guild_id: int):
    return await update_guild(guild_id, {'priceSheets': []})


async def clear_rule_sheets(guild_id: int):
    return await update_guild(guild_id, {'ruleSheets': []})


async def add_rule(guild_id: int, rule: str):
    data = await get_guild(guild_id)
    rows = list(data.get('rules') or [])
    rows.append(rule.strip())
    return await update_guild(guild_id, {'rules': rows})


async def remove_rule(guild_id: int, index: int):
    data = await get_guild(guild_id)
    rows = list(data.get('rules') or [])
    if index < 1 or index > len(rows):
        return False
    rows.pop(index - 1)
    await update_guild(guild_id, {'rules': rows})
    return True


async def add_service(guild_id: int, service: str):
    data = await get_guild(guild_id)
    rows = list(data.get('services') or [])
    key = service.strip().casefold()
    if not any(str(x).strip().casefold() == key for x in rows):
        rows.append(service.strip())
    return await update_guild(guild_id, {'services': rows})


async def remove_service(guild_id: int, service: str):
    data = await get_guild(guild_id)
    key = service.strip().casefold()
    rows = [x for x in (data.get('services') or []) if str(x).strip().casefold() != key]
    changed = len(rows) != len(data.get('services') or [])
    await update_guild(guild_id, {'services': rows})
    return changed


async def clear_all(guild_id: int):
    return await update_guild(guild_id, {
        'prices': [], 'rules': [], 'services': [], 'priceSheets': [], 'ruleSheets': [], 'managerRoleId': None,
    })


async def list_enabled_guilds() -> list[dict[str, Any]]:
    if not await connect():
        return []
    return await _db[COLLECTION].find({'aiEnabled': True}).to_list(length=None)
