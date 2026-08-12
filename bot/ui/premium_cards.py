import discord

# United Bunnies brand palette
PURPLE = 0x9B59B6
DEEP_PURPLE = 0x6C3483
GREEN = 0x57F287
GOLD = 0xFEE75C
RED = 0xED4245
BLUE = 0x5865F2


def _accent(kind: str = "info") -> int:
    return {
        "info": PURPLE,
        "success": GREEN,
        "warn": GOLD,
        "warning": GOLD,
        "error": RED,
        "mod": DEEP_PURPLE,
        "purple": PURPLE,
        "blue": BLUE,
    }.get((kind or "info").lower(), PURPLE)


def premium_card_view(
    *,
    title: str,
    description: str | None = None,
    fields: list[tuple[str, str, bool]] | None = None,
    footer: str | None = None,
    kind: str = "info",
    accent_color: int | discord.Colour | None = None,
) -> discord.ui.LayoutView:
    """Build a Discord Components V2 card.

    This uses Discord's native Container/TextDisplay components, so all text
    remains real selectable/copyable Discord text and there is no classic
    embed left border.
    """
    view = discord.ui.LayoutView(timeout=None)

    parts: list[discord.ui.Item] = []
    heading = str(title).strip()

    # The large heading is deliberately a TextDisplay, not an embed title.
    parts.append(discord.ui.TextDisplay(f"## ✦ {heading.upper()} ✦"))

    if description:
        parts.append(discord.ui.Separator())
        parts.append(discord.ui.TextDisplay(description.strip()))

    for name, value, inline in (fields or []):
        parts.append(discord.ui.Separator())
        label = str(name).strip()
        body = str(value).strip()
        if label:
            parts.append(discord.ui.TextDisplay(f"**{label}**\n{body}"))
        else:
            parts.append(discord.ui.TextDisplay(body))

    if footer:
        parts.append(discord.ui.Separator())
        parts.append(discord.ui.TextDisplay(f"-# {footer.strip()}"))

    container = discord.ui.Container(
        *parts,
        accent_color=accent_color if accent_color is not None else _accent(kind),
    )
    view.add_item(container)
    return view


def quick_card_view(text: str, *, title: str | None = None) -> discord.ui.LayoutView:
    """Premium replacement for the bot's small one-message responses."""
    if text.startswith(("❌", "❗", "🚫", "💔")):
        kind = "error"
        default_title = "ACTION FAILED"
    elif text.startswith(("✅", "🎉", "🔓")):
        kind = "success"
        default_title = "SUCCESS"
    elif text.startswith(("⚠️", "🤫", "🔒")):
        kind = "warn"
        default_title = "NOTICE"
    else:
        kind = "info"
        default_title = "UNITED BUNNIES"

    return premium_card_view(
        title=title or default_title,
        description=text,
        kind=kind,
    )


def style_card_view(
    title: str,
    *,
    description: str | None = None,
    fields: list[tuple[str, str, bool]] | None = None,
    color: int | None = None,
    footer: str | None = None,
    kind: str = "info",
) -> discord.ui.LayoutView:
    """Premium replacement for style_embed()."""
    return premium_card_view(
        title=title,
        description=description,
        fields=fields,
        footer=footer,
        kind=kind,
        accent_color=color,
    )
