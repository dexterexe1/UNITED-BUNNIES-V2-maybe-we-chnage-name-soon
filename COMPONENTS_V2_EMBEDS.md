# United Bunnies — Components V2 Premium Cards

The bot's standardized quick/style responses now use Discord Components V2:
`discord.ui.LayoutView` + `discord.ui.Container` + `discord.ui.TextDisplay`.

This is real Discord text (selectable/copyable), not an image and not a classic
embed, so it does not have the classic embed color strip.

## Requirement
`requirements.txt` now requires `discord.py[voice]>=2.6.0,<3.0` because Components V2
support was added in discord.py 2.6.

## New shared UI
`bot/ui/premium_cards.py`
- `quick_card_view()`
- `style_card_view()`
- `premium_card_view()`

Commands using `quick_embed()` / `style_embed()` in send calls were migrated to
the Components V2 versions.

Custom rich embeds that are built manually with `discord.Embed(...)` are not
automatically converted because they often need images, thumbnails, buttons,
or other embed-specific behavior. They can be migrated separately without
breaking those commands.
