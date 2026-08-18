"""AI-assisted payment parser for the revenue system."""
from __future__ import annotations

import json
import os
import re
from typing import Optional

import aiohttp

from bot.blox_values import get_cached_value_names, lookup_payment

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_PAYMENT_MODEL", "gemini-3.5-flash-lite").strip()
AI_ENABLED = os.getenv("AI_PAYMENT_PARSER_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}


def _clean(text: str) -> str:
    text = text.strip().casefold()
    text = re.sub(r"[^a-z0-9+]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _simple_aliases(payment: str) -> list[str]:
    raw = _clean(payment)
    candidates = [raw]
    prefixes = ("payment:", "payment -", "payment", "item:", "item -", "item")
    for prefix in prefixes:
        if raw.startswith(prefix):
            stripped = raw[len(prefix):].strip(" :–-")
            if stripped:
                candidates.append(stripped)
    expanded = list(candidates)
    for value in candidates:
        if value.endswith(" fruit"):
            expanded.append(value[:-6].strip())
        typo_fixed = re.sub(r"\bpemanent\b|\bpermenant\b|\bpermament\b|\bperment\b|\bpermant\b", "permanent", value)
        if typo_fixed != value:
            expanded.append(typo_fixed)
            value = typo_fixed
        if value.startswith("perm "):
            expanded.append("permanent " + value[5:])
        if value.startswith("permanent "):
            expanded.append("perm " + value[10:])
        if value.startswith("physical "):
            expanded.append(value[9:].strip())
        if "x2 " in value:
            expanded.append(value.replace("x2 ", "2x "))
        if value.startswith("2x "):
            expanded.append(value.replace("2x ", "x2 ", 1))
        stripped = re.sub(r"\b(?:gamepass|game pass|limited|skin|cosmetic|item)\b", " ", value)
        stripped = _clean(stripped)
        if stripped:
            expanded.append(stripped)
    return list(dict.fromkeys(x for x in expanded if x))


async def _gemini_resolve(payment: str, item_names: list[str]) -> Optional[str]:
    if not GEMINI_API_KEY or not AI_ENABLED or not item_names:
        return None

    names_text = "\n".join(f"- {name}" for name in sorted(set(item_names), key=str.casefold))
    prompt = f"""Classify this Discord revenue payment into one exact Blox Fruits item name.

Payment text: {payment!r}

Allowed item names:
{names_text}

Rules:
- Ignore capitalization and harmless wording such as fruit, physical, gamepass, skin, limited, item, perm, and permanent.
- Preserve whether the payment is REGULAR or PERMANENT. "Permanent Buddha" must match "permanent buddha", not regular "buddha".
- Correct obvious spelling mistakes such as "pemanent" -> "permanent" when the intended item is unambiguous.
- Choose ONLY an exact item from the list.
- If the payment is not a Blox Fruits item, return null.
- Never invent an item name.

Return JSON only: {{"matched_name": "EXACT NAME OR null"}}"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }

    try:
        timeout = aiohttp.ClientTimeout(total=12)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    body = await response.text()
                    print(f"⚠️ AI payment parser HTTP {response.status}: {body[:250]}")
                    return None
                data = await response.json()
        text = "".join(
            part.get("text", "")
            for candidate in data.get("candidates", [])
            for part in candidate.get("content", {}).get("parts", [])
            if isinstance(part.get("text"), str)
        ).strip()
        if not text:
            return None
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
        parsed = json.loads(text)
        matched = parsed.get("matched_name")
        if not isinstance(matched, str) or not matched.strip() or _clean(matched) == "null":
            return None
        by_normalized = {_clean(name): name for name in item_names}
        return by_normalized.get(_clean(matched))
    except Exception as exc:
        print(f"⚠️ AI payment parser failed: {exc}")
        return None


async def resolve_payment(payment: str):
    """Return (value, matched_name, checked_at, source)."""
    payment = payment.strip()
    for candidate in _simple_aliases(payment):
        value, name, checked_at = await lookup_payment(candidate)
        if value is not None:
            print(f"🤖 Payment parser: {payment!r} -> {name!r} | source=direct | value={value}")
            return value, name, checked_at, "direct"

    item_names = get_cached_value_names()
    matched_name = await _gemini_resolve(payment, item_names)
    if matched_name:
        value, name, checked_at = await lookup_payment(matched_name)
        if value is not None:
            print(f"🤖 Payment parser: {payment!r} -> {name!r} | source=ai | value={value}")
            return value, name, checked_at, "ai"

    print(f"🤖 Payment parser: {payment!r} -> uncalculated/non-ingame")
    return None, None, None, None
