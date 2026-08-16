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
GAMEPASS_INDEX_URL = "https://bloxfruitsvalues.com/values/gamepasses"
GAMEPASS_BASE_URL = "https://bloxfruitsvalues.com/values/gamepasses/{}"
LIMITED_INDEX_URL = "https://bloxfruitsvalues.com/values/limiteds"
LIMITED_BASE_URL = "https://bloxfruitsvalues.com/values/limiteds/{}"
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
    # Regular fruit wording
    "tiger fruit": "tiger",
    "tiger fruit regular": "tiger",
    "regular tiger": "tiger",
    "physical tiger": "tiger",

    # Generic permanent wording/aliases. The normaliser below handles common typos.
}

# Permanent fruit values are kept separate from physical/regular fruit values.
# Values can be overridden per server/environment with BLOX_PERM_<FRUIT>_VALUE.
# These defaults are fallback values only; they are not used to replace a live
# value when a trusted live permanent value is available.
_PERMANENT_VALUE_DEFAULTS = {
    "west dragon": 15.00e9,
    "east dragon": 14.00e9,
    "kitsune": 1.80e9,
    "control": 8.34e9,
    "yeti": 6.97e9,
    "gas": 5.80e9,
    "tiger": 6.96e9,
    "lightning": 4.20e9,
    "venom": 4.84e9,
    "dough": 5.15e9,
    "pain": 2.97e9,
    "t-rex": 4.47e9,
    "gravity": 4.28e9,
    "mammoth": 5.57e9,
    "spirit": 5.80e9,
    "shadow": 5.15e9,
    "portal": 3.00e9,
    "buddha": 2.36e9,
    "blizzard": 4.26e9,
    "creation": 2.89e9,
    "phoenix": 3.36e9,
    "sound": 3.25e9,
    "spider": 2.99e9,
    "love": 2.42e9,
    "magma": 1.80e9,
    "quake": 2.02e9,
    "diamond": 954.16e6,
    "light": 1.23e9,
    "ghost": 1.40e9,
    "eagle": 910.39e6,
    "rubber": 1.45e9,
    "ice": 555.53e6,
    "sand": 774.60e6,
    "dark": 994.85e6,
    "flame": 450.78e6,
    "spike": 139.91e6,
    "smoke": 120.83e6,
    "bomb": 90.03e6,
    "spring": 59.94e6,
    "blade": 19.91e6,
    "spin": 15.04e6,
    "rocket": 9.98e6,
}

def _permanent_env_key(base_key: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", base_key.casefold()).strip("_")
    return f"BLOX_PERM_{slug.upper()}_VALUE"

_PERMANENT_VALUE_OVERRIDES = {
    f"permanent {name}": float(os.getenv(_permanent_env_key(name), str(value)))
    for name, value in _PERMANENT_VALUE_DEFAULTS.items()
}

# Backwards compatibility for the old Tiger-specific environment variable.
if os.getenv("BLOX_PERMANENT_TIGER_VALUE"):
    _PERMANENT_VALUE_OVERRIDES["permanent tiger"] = float(os.getenv("BLOX_PERMANENT_TIGER_VALUE"))


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

    # Gamepasses / tradeable passes (seed values used if the site is temporarily unavailable).
    "fruit notifier": 4.7e9,
    "dark blade": 1.11e9,
    "mythical scrolls": 1.49e9,
    "legendary scrolls": 740e6,
    "+1 fruit storage": 450e6,
    "2x mastery": 450e6,
    "2x money": 450e6,
    "2x boss drops": 300e6,
    "fast boats": 300e6,

    # Limited / cosmetic items currently known to have numeric values.
    "fiend yeti": 960e6,
    "galaxy empyrean kitsune": 14.35e9,
    "ember west dragon": 8.21e9,
    "crimson kitsune": 9.9e9,
    "meme-meme": 6.06e9,
    "divine portal": 1.9e9,
    "purple lightning": 6.06e9,
    "red lightning": 3.51e9,
    "yellow lightning": 2.07e9,
    "green lightning": 430e6,
    "werewolf": 1.05e9,
    "rose quartz diamond": 370e6,
    "emerald diamond": 230e6,
    "topaz diamond": 230e6,
    "ruby diamond": 170e6,
    "super spirit pain": 4.02e9,
    "torment pain": 180e6,
    "sadness pain": 1.08e9,
    "frustration pain": 1.11e9,
    "celestial pain": 1.22e9,
    "eagle requiem": 170e6,
    "eagle glacier": 20e6,
    "eagle matrix": 260e6,
    "celebration bomb": 10e6,
    "azura bomb": 560e6,
    "thermite bomb": 560e6,
    "nuclear bomb": 560e6,
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


def _parse_detail_page(html: str, fallback_name: str) -> tuple[str, Optional[float]]:
    soup = BeautifulSoup(html, "html.parser")
    display_name = fallback_name.replace("-", " ").strip()
    h1 = soup.find("h1")
    if h1:
        candidate = " ".join(h1.stripped_strings).strip()
        if candidate:
            display_name = candidate

    text = " ".join(soup.stripped_strings)
    match = re.search(r"\bValue\s+([0-9]+(?:\.[0-9]+)?\s*[KMBT]?)\b", text, re.I)
    return display_name, (_parse_number(match.group(1)) if match else None)


async def _fetch_detail(session: aiohttp.ClientSession, url: str, fallback_name: str, sem: asyncio.Semaphore) -> tuple[str, Optional[float]]:
    async with sem:
        for attempt in range(2):
            try:
                async with session.get(url) as response:
                    response.raise_for_status()
                    html = await response.text()
                return _parse_detail_page(html, fallback_name)
            except Exception:
                if attempt == 1:
                    return fallback_name, None
                await asyncio.sleep(0.5)
    return fallback_name, None


def _discover_slugs(html: str, category: str) -> dict[str, str]:
    """Discover detail-page slugs from a category index page."""
    soup = BeautifulSoup(html, "html.parser")
    prefix = f"/values/{category}/"
    found: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        href = str(a.get("href", "")).strip()
        if not href.startswith(prefix):
            continue
        slug = href[len(prefix):].split("?", 1)[0].split("#", 1)[0].strip("/")
        if not slug or "/" in slug:
            continue
        label = " ".join(a.stripped_strings).strip() or slug.replace("-", " ")
        found[slug] = label
    return found


async def _fetch_category_index(session: aiohttp.ClientSession, url: str, category: str) -> dict[str, str]:
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            html = await response.text()
        return _discover_slugs(html, category)
    except Exception as exc:
        print(f"⚠️ Could not discover {category}: {exc}")
        return {}


async def refresh_blox_values(force: bool = False) -> Tuple[bool, int, Optional[dt.datetime]]:
    """Refresh fruits, gamepasses, and limited/cosmetic items.

    Category index pages are used only to discover item detail URLs; actual
    values are read from the server-rendered detail pages. Fallback values remain
    available when the public site is temporarily unavailable.
    """
    global _cache, _cache_names, _last_refresh

    async with _refresh_lock:
        now = dt.datetime.now(dt.timezone.utc)
        if not force and _last_refresh and now - _last_refresh < dt.timedelta(hours=REFRESH_HOURS):
            return True, len(_cache), _last_refresh

        timeout = aiohttp.ClientTimeout(total=45)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
        }
        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                sem = asyncio.Semaphore(10)
                fruit_tasks = [
                    _fetch_detail(session, FRUIT_BASE_URL.format(slug), slug.replace("-", " "), sem)
                    for slug in FRUIT_SLUGS
                ]

                gamepass_slugs = await _fetch_category_index(session, GAMEPASS_INDEX_URL, "gamepasses")
                limited_slugs = await _fetch_category_index(session, LIMITED_INDEX_URL, "limiteds")

                gamepass_tasks = [
                    _fetch_detail(session, GAMEPASS_BASE_URL.format(slug), label, sem)
                    for slug, label in gamepass_slugs.items()
                ]
                limited_tasks = [
                    _fetch_detail(session, LIMITED_BASE_URL.format(slug), label, sem)
                    for slug, label in limited_slugs.items()
                ]

                results = await asyncio.gather(*(fruit_tasks + gamepass_tasks + limited_tasks))

            parsed: Dict[str, float] = {}
            for display_name, value in results:
                if value is None:
                    continue
                key = _normalise(display_name)
                parsed[key] = value

            merged = dict(_cache)
            merged.update(parsed)
            _cache = merged
            _cache_names = {key: key for key in _cache}
            _last_refresh = now

            print(
                f"✅ Blox values refresh: {len(parsed)} live items "
                f"(fruits={len(FRUIT_SLUGS)}, gamepasses={len(gamepass_slugs)}, limiteds={len(limited_slugs)}), "
                f"{len(_cache)} total cached"
            )
            success = bool(parsed)
            if not success:
                print("⚠️ No live values parsed; using last-known fallback/cache")
            return success, len(_cache), _last_refresh
        except Exception as exc:
            print(f"⚠️ Blox values refresh failed: {exc}; keeping {len(_cache)} cached items")
            return False, len(_cache), _last_refresh


def _normalise_payment_key(value: str) -> str:
    key = _normalise(value)
    # Common staff typos for "permanent".
    key = re.sub(r"\bpemanent\b|\bpermenant\b|\bpermament\b|\bperment\b|\bpermant\b", "permanent", key)
    key = re.sub(r"\bperm\b", "permanent", key)
    return re.sub(r"\s+", " ", key).strip()


def _permanent_key_from_payment(key: str) -> Optional[str]:
    key = _normalise_payment_key(key)
    key = re.sub(r"\b(?:fruit|gamepass|game pass|item)\b", " ", key)
    key = _normalise(key)
    if key.startswith("permanent "):
        base = key[len("permanent "):].strip()
        base = re.sub(r"\bfruit$", "", base).strip()
        return f"permanent {base}" if base else None
    return None


async def lookup_payment(payment: str) -> Tuple[Optional[float], Optional[str], Optional[dt.datetime]]:
    """Return (value, matched_name, checked_at) using safe aliases and permanent variants."""
    await refresh_blox_values()
    original = payment.strip()
    key = _normalise_payment_key(original)

    # Permanent fruit/payment must never silently fall back to the regular fruit value.
    permanent_key = _permanent_key_from_payment(key)
    if permanent_key:
        value = _PERMANENT_VALUE_OVERRIDES.get(permanent_key)
        if value is not None:
            return value, permanent_key, _last_refresh
        value = _cache.get(permanent_key)
        if value is not None:
            return value, _cache_names.get(permanent_key, permanent_key), _last_refresh
        return None, None, _last_refresh

    alias = PAYMENT_ALIASES.get(key, key)
    value = _cache.get(alias)
    if value is not None:
        return value, _cache_names.get(alias, alias), _last_refresh

    # Common staff form: "Tiger Fruit" / "Dough Fruit" -> regular item.
    if key.endswith(" fruit"):
        base_key = key[:-6].strip()
        value = _cache.get(base_key)
        if value is not None:
            return value, _cache_names.get(base_key, base_key), _last_refresh

    # Common staff wording for gamepasses/limiteds.
    variants = {
        key.replace("x2 ", "2x "),
        key.replace(" 2x", " x2"),
        re.sub(r"\b(?:gamepass|game pass|limited|skin|cosmetic|item)\b", " ", key),
    }
    variants = {_normalise_payment_key(v) for v in variants if v and _normalise_payment_key(v) != key}
    for variant in variants:
        value = _cache.get(variant)
        if value is not None:
            return value, _cache_names.get(variant, variant), _last_refresh

    return None, None, _last_refresh


def get_cached_value_names() -> list[str]:
    """Return all currently known calculable item names for the AI parser."""
    names = set(_cache_names.values())
    names.update(_PERMANENT_VALUE_OVERRIDES.keys())
    return sorted(names, key=str.casefold)


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
