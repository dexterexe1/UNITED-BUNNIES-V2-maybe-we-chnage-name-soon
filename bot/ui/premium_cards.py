import discord

# United Bunnies brand palette - PREMIUM PURPLE THEME
PURPLE = 0x9B59B6           # Main brand purple
DEEP_PURPLE = 0x6C3483      # Dark purple accent
GRADIENT_PURPLE = 0x8B5CF6  # Vibrant gradient purple (matches the image)
GREEN = 0x57F287
GOLD = 0xFEE75C
RED = 0xED4245
BLUE = 0x5865F2


def _accent(kind: str = "info") -> int:
    """Returns the purple gradient color for all embeds to match the premium aesthetic."""
    return {
        "info": GRADIENT_PURPLE,      # Changed to gradient purple
        "success": GREEN,
        "warn": GOLD,
        "warning": GOLD,
        "error": RED,
        "mod": DEEP_PURPLE,
        "purple": GRADIENT_PURPLE,    # Changed to gradient purple
        "blue": GRADIENT_PURPLE,      # Changed to gradient purple for consistency
        "fun": GRADIENT_PURPLE,       # Changed to gradient purple
        "love": 0xFF6B9A,
        "music": GRADIENT_PURPLE,     # Changed to gradient purple
    }.get((kind or "info").lower(), GRADIENT_PURPLE)  # Default to gradient purple


def _color_value(color) -> int | None:
    if color is None:
        return None
    try:
        value = color.value
        return value if value else None
    except AttributeError:
        return int(color)


def premium_card_view(
    *,
    title: str,
    description: str | None = None,
    fields: list[tuple[str, str, bool]] | None = None,
    footer: str | None = None,
    kind: str = "info",
    accent_color: int | discord.Colour | None = None,
    image_url: str | None = None,
    thumbnail_url: str | None = None,
) -> discord.ui.LayoutView:
    """Build a real Discord Components V2 card with purple gradient premium theme.

    Uses LayoutView + Container + TextDisplay/Section/MediaGallery. It does not
    create a classic discord.Embed, so there is no classic embed accent strip.
    """
    view = discord.ui.LayoutView(timeout=None)
    parts: list[discord.ui.Item] = []
    
    # Add sparkle decorations to title for premium look
    heading = str(title).strip()
    if not heading.startswith("✨") and not heading.startswith("<:"):
        heading = f"✨ {heading} ✨"

    if thumbnail_url and description:
        section = discord.ui.Section(accessory=discord.ui.Thumbnail(media=thumbnail_url))
        section.add_item(discord.ui.TextDisplay(f"## {heading}"))
        section.add_item(discord.ui.TextDisplay(description.strip()))
        parts.append(section)
    else:
        parts.append(discord.ui.TextDisplay(f"## {heading}"))
        if description:
            parts.append(discord.ui.Separator())
            parts.append(discord.ui.TextDisplay(description.strip()))
        if thumbnail_url:
            section = discord.ui.Section(accessory=discord.ui.Thumbnail(media=thumbnail_url))
            section.add_item(discord.ui.TextDisplay(""))
            parts.append(section)

    for name, value, _inline in (fields or []):
        parts.append(discord.ui.Separator())
        label = str(name).strip()
        body = str(value).strip()
        parts.append(discord.ui.TextDisplay(f"**{label}**\n{body}" if label else body))

    if image_url:
        parts.append(discord.ui.Separator())
        gallery = discord.ui.MediaGallery()
        gallery.add_item(media=image_url)
        parts.append(gallery)

    if footer:
        parts.append(discord.ui.Separator(visible=False))
        parts.append(discord.ui.TextDisplay(f"-# {footer.strip()}"))

    container = discord.ui.Container(
        *parts,
        accent_color=(accent_color if accent_color is not None else _accent(kind)),
    )
    view.add_item(container)
    return view


def fun_card_view(
    title: str,
    description: str,
    *,
    image_url: str | None = None,
    kind: str = "fun",
) -> discord.ui.LayoutView:
    """Single-message card for social/fun commands."""
    return premium_card_view(
        title=title,
        description=description,
        kind=kind,
        image_url=image_url,
    )


def error_card_view(text: str) -> discord.ui.LayoutView:
    return premium_card_view(
        title="ACTION FAILED",
        description=text,
        kind="error",
    )


def quick_card_view(text: str, *, title: str | None = None) -> discord.ui.LayoutView:
    """Small Components V2 response.

    Only genuine error prefixes use ACTION FAILED. Romantic/fun messages such
    as 💔 are deliberately not classified as errors.
    """
    clean = str(text).strip()
    if clean.startswith(("❌", "🚫")) or clean.lower().startswith(("error:", "failed:")):
        kind = "error"
        default_title = "ACTION FAILED"
    elif clean.startswith(("✅", "🎉", "🔓")):
        kind = "success"
        default_title = "DONE"
    elif clean.startswith(("⚠️", "🤫", "🔒")):
        kind = "warn"
        default_title = "NOTICE"
    else:
        kind = "info"
        default_title = "UNITED BUNNIES"

    return premium_card_view(
        title=title or default_title,
        description=clean,
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
    image_url: str | None = None,
    thumbnail_url: str | None = None,
) -> discord.ui.LayoutView:
    return premium_card_view(
        title=title,
        description=description,
        fields=fields,
        footer=footer,
        kind=kind,
        accent_color=color,
        image_url=image_url,
        thumbnail_url=thumbnail_url,
    )


def embed_to_view(embed: discord.Embed) -> discord.ui.LayoutView:
    """Convert a legacy Embed into a real Components V2 card.

    Used as a safe compatibility bridge for the bot's older commands while
    keeping the existing message content, fields and images.
    """
    title = embed.title or "UNITED BUNNIES"
    description = embed.description
    fields = [(f.name, f.value, f.inline) for f in embed.fields]
    footer = embed.footer.text if embed.footer else None
    image_url = embed.image.url if embed.image and embed.image.url else None
    thumbnail_url = embed.thumbnail.url if embed.thumbnail and embed.thumbnail.url else None
    return premium_card_view(
        title=title,
        description=description,
        fields=fields,
        footer=footer,
        accent_color=_color_value(embed.color),
        image_url=image_url,
        thumbnail_url=thumbnail_url,
    )


def purple_embed(
    title: str,
    description: str | None = None,
    *,
    fields: list[tuple[str, str, bool]] | None = None,
    footer: str | None = None,
    thumbnail_url: str | None = None,
    image_url: str | None = None,
) -> discord.Embed:
    """Create a classic discord.Embed with the premium purple gradient aesthetic.
    
    This matches the style from the reference image:
    - Purple gradient color (#8B5CF6)
    - Sparkle emojis ✨ in the title
    - Clean, premium look
    
    Use this for commands that need classic embeds (e.g., when mixing with buttons/selects).
    """
    # Add sparkle decorations to title
    clean_title = str(title).strip()
    if not clean_title.startswith("✨") and not clean_title.startswith("<:"):
        clean_title = f"✨ {clean_title} ✨"
    
    embed = discord.Embed(
        title=clean_title,
        description=description,
        color=GRADIENT_PURPLE,  # The premium purple gradient
    )
    
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
    
    if footer:
        embed.set_footer(text=footer)
    
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    
    if image_url:
        embed.set_image(url=image_url)
    
    return embed
