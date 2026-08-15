"""Live Blox Fruits value lookup for the revenue system.

Source: https://bloxfruitsvalues.com/values
The site is a third-party/fan-operated value platform. Values are refreshed
periodically and cached locally so a temporary website outage does not break
revenue logging.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import os
import re
from typing import Dict, Optional, Tuple

import aiohttp
from bs4 import BeautifulSoup

SOURCE_URL = "https://bloxfruitsvalues.com/values"
REFRESH_HOURS = max(1, int(os.getenv("BLOX_VALUES_REFRESH_HOURS", "6")))

# Revenue messages are written by humans, so the same item can appear under
# several harmless names. These are explicit aliases only; we do not fuzzy
# match arbitrary text because that could assign the wrong item value.
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

# The current Blox Fruits Values page exposes the regular value in its
# server-rendered card while the Permanent toggle is client-side. Keep
# permanent overrides explicit and isolated so they can be updated without
# pretending the regular value is the permanent value.
# Tiger's current permanent trading value is 5.87B (July 2026 market data).
# Set BLOX_PERMANENT_TIGER_VALUE to override it if your server uses a different
# agreed value.
_PERMANENT_VALUE_OVERRIDES = {
    "permanent tiger": float(os.getenv("BLOX_PERMANENT_TIGER_VALUE", "5870000000")),
}

_cache: Dict[str, float] = {}
_cache_names: Dict[str, str] = {}
_last_refresh: Optional[dt.datetime] = None
_refresh_lock = asyncio.Lock()


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def _parse_number(value: str) -> Optional[float]:
    """Parse site values such as 5.55B, 10M, 7.5K, or 1234."""
    text = value.strip().replace(",", "").upper()
    if text in {"N/A", "NA", "NONE", "-", ""}:
        return None
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*([KMBT]?)", text)
    if not match:
        return None
    number = float(match.group(1))
    multiplier = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000, "T": 1_000_000_000_000}[match.group(2)]
    return number * multiplier


def _parse_page(html: str) -> Dict[str, float]:
    """Parse the server-rendered value cards. Fails closed if a card is ambiguous."""
    soup = BeautifulSoup(html, "html.parser")
    found: Dict[str, float] = {}

    # Prefer item/card-like elements. We look for a heading/name and a nearby
    # Value label, never fuzzy-match a user's payment string.
    candidates = soup.find_all(["article", "li", "div"])
    for card in candidates:
        text = " ".join(card.stripped_strings)
        if "Value" not in text:
            continue
        if len(text) > 2500:
            continue

        # Extract a compact "Value 10M" / "Value 5.55B" occurrence.
        value_match = re.search(r"\bValue\s*([0-9]+(?:\.[0-9]+)?\s*[KMBT]?)\b", text, re.I)
        if not value_match:
            continue
        numeric = _parse_number(value_match.group(1))
        if numeric is None:
            continue

        # The first meaningful heading in a card is normally the item name.
        name = None
        for tag in card.find_all(["h1", "h2", "h3", "h4", "h5", "h6"], limit=3):
            candidate = " ".join(tag.stripped_strings).strip()
            if candidate and candidate.lower() not in {"value", "values"}:
                name = candidate
                break
        if not name:
            # Fallback to the text immediately before the Value label.
            before = text.split("Value", 1)[0].strip()
            parts = [p.strip() for p in re.split(r"\s{2,}|\n", before) if p.strip()]
            if parts:
                name = parts[-1]

        if not name:
            continue
        # Avoid accidentally indexing navigation/FAQ headings.
        if len(name) > 80 or name.lower() in {"blox fruits value list", "values"}:
            continue

        key = _normalise(name)
        found[key] = numeric

    return found


async def refresh_blox_values(force: bool = False) -> Tuple[bool, int, Optional[dt.datetime]]:
    """Refresh the live value cache. Returns (success, count, timestamp)."""
    global _cache, _cache_names, _last_refresh

    async with _refresh_lock:
        now = dt.datetime.now(dt.timezone.utc)
        if not force and _last_refresh and now - _last_refresh < dt.timedelta(hours=REFRESH_HOURS):
            return True, len(_cache), _last_refresh

        timeout = aiohttp.ClientTimeout(total=25)
        headers = {"User-Agent": "UnitedBunniesRevenue/2.0 (+Discord bot)"}
        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(SOURCE_URL) as response:
                    response.raise_for_status()
                    html = await response.text()

            parsed = await asyncio.to_thread(_parse_page, html)
            if not parsed:
                raise RuntimeError("No value cards could be parsed from the Blox Fruits Values page")

            _cache = parsed
            _cache_names = {key: key for key in parsed}
            _last_refresh = now
            print(f"✅ Blox Fruits values refreshed: {len(parsed)} items")
            return True, len(parsed), _last_refresh
        except Exception as exc:
            print(f"⚠️ Blox Fruits values refresh failed: {exc}")
            # Keep the last known good cache. Never guess a price.
            return False, len(_cache), _last_refresh


async def lookup_payment(payment: str) -> Tuple[Optional[float], Optional[str], Optional[dt.datetime]]:
    """Return (value, matched_name, checked_at) for a safe explicit payment match.

    Matching order:
      1. Explicit permanent-value overrides.
      2. Exact normalized cache name.
      3. Explicit aliases such as ``tiger fruit`` -> ``tiger``.

    Arbitrary fuzzy matching is intentionally not used.
    """
    await refresh_blox_values()

    original = payment.strip()
    key = _normalise(original)

    # Permanent items need their own value; never silently use the regular
    # fruit value for a permanent payment.
    permanent_key = PAYMENT_ALIASES.get(key, key)
    if permanent_key in _PERMANENT_VALUE_OVERRIDES:
        return _PERMANENT_VALUE_OVERRIDES[permanent_key], permanent_key, _last_refresh

    # Exact match first.
    value = _cache.get(key)
    if value is not None:
        return value, _cache_names.get(key, original), _last_refresh

    # Then explicit, controlled aliases.
    alias = PAYMENT_ALIASES.get(key)
    if alias:
        value = _cache.get(alias)
        if value is not None:
            return value, _cache_names.get(alias, alias), _last_refresh

    return None, None, _last_refresh


def format_value(value: float) -> str:
    """Human-readable Blox Fruits value."""
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}".rstrip("0").rstrip(".") + "B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}".rstrip("0").rstrip(".") + "M"
    if value >= 1_000:
        return f"{value / 1_000:.2f}".rstrip("0").rstrip(".") + "K"
    return f"{value:,.0f}"


def cache_status() -> Tuple[int, Optional[dt.datetime]]:
    return len(_cache), _last_refresh
