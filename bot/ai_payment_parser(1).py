"""AI-assisted Blox Fruits payment-name parser.

AI is used only to identify what an entered payment name refers to. It never
supplies or invents a price. The trusted Blox Fruits value cache remains the
source of truth for the numeric value.
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional

import aiohttp

from bot.blox_values import lookup_payment, get_cached_value_names

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_PAYMENT_MODEL", "gemini-2.5-flash-lite")
AI_ENABLED = os.getenv("AI_PAYMENT_PARSER_ENABLED", "true").strip().lower() in {
    "1", "true", "yes", "on"
}


def _clean(text: str) -> str:
    text = text.strip().casefold()
    text = re.sub(r"\s+", " ", text)
    return text


def _simple_aliases(payment: str) -> list[str]:
    """Generate safe, deterministic aliases before asking AI."""
    raw = _clean(payment)
    candidates = [raw]

    # Common staff shorthand. This is deliberately conservative.
    for prefix in ("payment:", "payment -", "payment", "item:", "item -", "item"):
        if raw.startswith(prefix):
            stripped = raw[len(prefix):].strip(" :-")
            if stripped:
                candidates.append(stripped)

    expanded = list(candidates)
    for value in candidates:
        if value.endswith(" fruit"):
            expanded.append(value[:-6].strip())
        if value.startswith("perm "):
            expanded.append("permanent " + value[5:])
        if value.startswith("permanent "):
            expanded.append("perm " + value[10:])
        if value.startswith("physical "):
            expanded.append(value[9:].strip())

    # Preserve order and uniqueness.
    return list(dict.fromkeys(x for x in expanded if x))


async def _gemini_resolve(payment: str, item_names: list[str]) -> Optional[str]:
    if not GEMINI_API_KEY or not AI_ENABLED or not item_names:
        return None

    # Keep the prompt bounded even if the source site contains a large list.
    names = sorted(set(item_names), key=str.casefold)
    names_text = "\n".join(f"- {name}" for name in names)
    prompt = f"""You classify a Discord revenue payment into one exact Blox Fruits item name.

User payment text:
{payment!r}

Allowed Blox Fruits item names (choose ONLY one exact name from this list):
{names_text}

Rules:
- Ignore capitalization, punctuation, and harmless words such as 'fruit', 'physical', 'perm', and 'permanent' when they clearly refer to a listed item.
- 'perm X' means the listed permanent X item when one exists; never turn it into regular X.
- If the payment is not a Blox Fruits item, return null.
- If the text is ambiguous, return null.
- Never invent a name.

Return JSON only: {{"matched_name": "EXACT LIST NAME OR null"}}"""

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
        },
    }

    timeout = aiohttp.ClientTimeout(total=12)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    print(f"⚠️ AI payment parser HTTP {response.status}")
                    return None
                data = await response.json()

        text = ""
        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                if isinstance(part.get("text"), str):
                    text += part["text"]
        if not text:
            return None

        parsed = json.loads(text.strip().strip("`").replace("json\n", "", 1))
        matched = parsed.get("matched_name")
        if not isinstance(matched, str) or not matched.strip():
            return None

        # Never trust the model's spelling. Resolve it against the exact list.
        by_normalized = {_clean(name): name for name in item_names}
        return by_normalized.get(_clean(matched))
    except Exception as exc:
        print(f"⚠️ AI payment parser failed: {exc}")
        return None


async def resolve_payment(payment: str):
    """Resolve a payment to (value, matched_name, checked_at).

    Deterministic matching is attempted first. AI is only a fallback for names
    that are not an exact match. Non-ingame payments return (None, None, ...).
    """
    for candidate in _simple_aliases(payment):
        value, name, checked_at = await lookup_payment(candidate)
        if value is not None:
            return value, name, checked_at, "direct"

    item_names = get_cached_value_names()
    matched_name = await _gemini_resolve(payment, item_names)
    if matched_name:
        value, name, checked_at = await lookup_payment(matched_name)
        if value is not None:
            return value, name, checked_at, "ai"

    return None, None, None, None
