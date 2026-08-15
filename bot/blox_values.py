"""Blox Fruits value lookup with resilient live-refresh + safe payment matching."""
from __future__ import annotations

import asyncio
import datetime as dt
import os
import re
from typing import Dict, Optional, Tuple

import aiohttp
from bs4 import BeautifulSoup

SOURCE_URL = "https://bloxfruitsvalues.com/values"
FRUIT_BASE_URL = "https://bloxfruitsvalues.com/values/fruits/{}"
REFRESH_HOURS = max(1, int(os.getenv("BLOX_VALUES_REFRESH_HOURS", "6")))

# Current fruit slugs exposed by Blox Fruits Values. Detail pages are used
# because /values is client-rendered and can return an empty "Loading value list"
# shell to normal HTTP clients.
FRUIT_SLUGS = [
    "west-dragon", "east-dragon", "kitsune", "control", "yeti", "gas", "tiger",
    "lightning", "venom", "dough", "pain", "t-rex", "gravity", "mammoth", "spirit",
    "shadow", "portal", "buddha", "blizzard", "creation", "phoenix", "sound", "spider",
    "love", "magma", "quake", "diamond", "light", "ghost", "eagle", "rubber", "ice",
    "sand", "dark", "flame", "spike", "smoke", "bomb", "spring", "blade", "spin", "rocket",
]

# Safe human-entry aliases. AI is used only after these deterministic checks fail.
PAYMENT_ALIASES = {
    "tiger fruit": "tiger",
    "tiger fruit (regular)": "tiger",
    "regular tiger": "tiger",
    "physical tiger": "tiger",
    "perm tiger": "permanent tiger",
    "perm tiger fruit": "permanent tiger",
    "permanent tiger fruit": "permanent tiger",
    "permanent tiger (fruit)": "permanent tiger",
}

# Permanent values should never silently fall back to regular values. Add agreed
# server-specific permanent overrides in Render if desired, e.g.
# BLOX_PERMANENT_TIGER_VALUE=5870000000
_PERMANENT_VALUE_OVERRIDES = {
    "permanent tiger": float(os.getenv("BLOX_PERMANENT_TIGER_VALUE", "5870000000")),
}

# Last-known baseline values. These keep Tiger and the other regular fruits
# calculable even when the public site is temporarily unreachable. Live refresh
# replaces them when successful.
_FALLBACK_VALUES: Dict[str, float] = {
    "west dragon": 5.2e9,
    "east dragon": 4.75e9,
    "kitsune": 680e6,
    "control": 170e6,
    "yeti": 130e6,
    "gas": 60e6,
    "tiger": 140e6,
    "lightning": 50e6,
    "venom": 20e6,
    "dough": 30e6,
    "pain": 10e6,
    "t-rex": 20e6,
    "gravity": 10e6,
    "mammoth": 10e6,
    "spirit": 10e6,
    "shadow": 6.5e6,
    "portal": 10e6,
    "buddha": 10e6,
    "blizzard": 5e6,
    "creation": 2.5e6,
    "phoenix": 2.75e6,
    "sound": 2.5e6,
    "spider": 1.5e6,
    "love": 1.5e6,
    "magma": 1.15e6,
    "quake": 1e6,
    "diamond": 1e6,
    "light": 800e3,
    "ghost": 800e3,
    "eagle": 800e3,
    "rubber": 700e3,
    "ice": 550e3,
    "sand": 420e3,
    "dark": 400e3,
    "flame": 250e3,
    "spike": 180e3,
    "smoke": 100e3,
    "bomb": 80e3,
    "spring": 60e3,
    "blade": 50e3,
    "spin": 7.5e3,
    "rocket": 5e3,
}

_cache: Dict[str, float] = dict(_FALLBACK_VALUES)
_cache_names: Dict[str, str] = {k: k for k in _cache}
_last_refresh: Optional[dt.datetime] = None
_refresh_lock = asyncio.Lock()


def _normalise(value: str) -> str:
    value = value.strip().casefold()
    value = re.sub(r"[^a-z0-9+]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _parse_number(value: str) -> Optional[float]:
    text = value.strip().replace(",", "").upper()
    if text in {"N/A", "NA", "NONE", "-", ""}:
        return None
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*([KMBT]?)", text)
    if not match:
        return None
    number = float(match.group(1))
    multiplier = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000, "T": 1_000_000_000_000}[match.group(2)]
    return number * multiplier


def _parse_detail_page(html: str, expected_name: str) -> Optional[float]:
    soup = BeautifulSoup(html, "html.parser")
    text = " ".join(soup.stripped_strings)
    # Detail pages are server-rendered. Prefer the first explicit Value number.
    match = re.search(r"\bValue\s+([0-9]+(?:\.[0-9]+)?\s*[KMBT]?)\b", text, re.I)
    if match:
        return _parse_number(match.group(1))
    return None


async def _fetch_detail(session: aiohttp.ClientSession, slug: str, sem: asyncio.Semaphore) -> tuple[str, Optional[float]]:
    async with sem:
        url = FRUIT_BASE_URL.format(slug)
        for attempt in range(2):
            try:
                async with session.get(url) as response:
                    response.raise_for_status()
                    html = await response.text()
                key = slug.replace("-", " ")
                return key, _parse_detail_page(html, key)
            except Exception:
                if attempt == 1:
                    return slug.replace("-", " "), None
                await asyncio.sleep(0.5)
    return slug.replace("-", " "), None


async def refresh_blox_values(force: bool = False) -> Tuple[bool, int, Optional[dt.datetime]]:
    """Refresh regular fruit values from server-rendered detail pages.

    The main /values page is client-rendered, so scraping it with aiohttp can
    legitimately return zero cards. Detail pages provide server-rendered SEO
    content and are much more reliable for a bot.
    """
    global _cache, _cache_names, _last_refresh

    async with _refresh_lock:
        now = dt.datetime.now(dt.timezone.utc)
        if not force and _last_refresh and now - _last_refresh < dt.timedelta(hours=REFRESH_HOURS):
            return True, len(_cache), _last_refresh

        timeout = aiohttp.ClientTimeout(total=30)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
        }
        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                sem = asyncio.Semaphore(8)
                results = await asyncio.gather(*(_fetch_detail(session, slug, sem) for slug in FRUIT_SLUGS))

            parsed: Dict[str, float] = {}
            for raw_key, value in results:
                if value is None:
                    continue
                key = _normalise(raw_key)
                parsed[key] = value

            # Merge successful live values over the last-known fallback/cache.
            merged = dict(_cache)
            merged.update(parsed)
            _cache = merged
            _cache_names = {key: key for key in _cache}
            _last_refresh = now

            success = bool(parsed)
            print(f"✅ Blox Fruits values refresh: {len(parsed)} live items, {len(_cache)} total cached")
            if not success:
                print("⚠️ No live fruit detail pages could be parsed; using last-known cache")
            return success, len(_cache), _last_refresh
        except Exception as exc:
            print(f"⚠️ Blox Fruits values refresh failed: {exc}; keeping {len(_cache)} cached items")
            return False, len(_cache), _last_refresh


async def lookup_payment(payment: str) -> Tuple[Optional[float], Optional[str], Optional[dt.datetime]]:
    """Return (value, matched_name, checked_at) using exact/safe aliases."""
    await refresh_blox_values()
    original = payment.strip()
    key = _normalise(original)

    # Permanent item values are separate. Never use a regular value for a perm.
    permanent_key = PAYMENT_ALIASES.get(key, key)
    if permanent_key in _PERMANENT_VALUE_OVERRIDES:
        return _PERMANENT_VALUE_OVERRIDES[permanent_key], permanent_key, _last_refresh

    value = _cache.get(key)
    if value is not None:
        return value, _cache_names.get(key, original), _last_refresh

    # Common staff form: "Tiger Fruit" / "Dough Fruit" -> regular item.
    if key.endswith(" fruit"):
        base_key = key[:-6].strip()
        value = _cache.get(base_key)
        if value is not None:
            return value, _cache_names.get(base_key, base_key), _last_refresh

    alias = PAYMENT_ALIASES.get(key)
    if alias:
        value = _cache.get(alias)
        if value is not None and not alias.startswith("permanent "):
            return value, _cache_names.get(alias, alias), _last_refresh

    return None, None, _last_refresh


def get_cached_value_names() -> list[str]:
    """Return all currently known calculable item names for the AI parser."""
    return sorted(_cache_names.values(), key=str.casefold)


def format_value(value: float) -> str:
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}".rstrip("0").rstrip(".") + "B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}".rstrip("0").rstrip(".") + "M"
    if value >= 1_000:
        return f"{value / 1_000:.2f}".rstrip("0").rstrip(".") + "K"
    return f"{value:,.0f}"


def cache_status() -> Tuple[int, Optional[dt.datetime]]:
    return len(_cache), _last_refresh
