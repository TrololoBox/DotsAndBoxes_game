"""Text screens work on both ordinary messages and game photo captions."""


async def show_screen(update, context, text, keyboard, parse_mode="HTML"):
    query = update.callback_query
    if query:
        if getattr(query.message, "photo", None):
            await query.edit_message_caption(
                caption=text, parse_mode=parse_mode, reply_markup=keyboard,
            )
        else:
            await query.edit_message_text(
                text, parse_mode=parse_mode, reply_markup=keyboard,
            )
    else:
        await update.message.reply_text(text, parse_mode=parse_mode, reply_markup=keyboard)
