"""
DotsAndBoxes Telegram Bot — Entry Point

Run with: python -m bot.main
"""

import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from bot.config import BOT_TOKEN, logger
from bot.handlers.start import start_command, main_menu_callback, show_main_menu
from bot.handlers.play import play_callback
from bot.handlers.game import game_callback


async def menu_text_handler(update: Update, context) -> None:
    """Handle 'Меню' text message to show main menu."""
    await show_main_menu(update, context)


async def support_handler(update: Update, context) -> None:
    """Handle 'Поддержать' button (stub)."""
    await update.message.reply_text(
        "💝 *Поддержать проект*\n\n"
        "Спасибо за интерес к игре!\n"
        "Способы поддержки появятся позже.\n\n"
        "🚧 Раздел в разработке",
        parse_mode="Markdown",
    )


async def clear_chat_handler(update: Update, context) -> None:
    """Handle 'Очистить чат' button - delete recent bot messages."""
    await update.message.reply_text(
        "🗑 *Очистка чата*\n\n"
        "К сожалению, Telegram не позволяет ботам удалять все сообщения.\n"
        "Вы можете очистить историю вручную:\n"
        "• Откройте меню чата (три точки)\n"
        "• Выберите «Очистить историю»",
        parse_mode="Markdown",
    )


async def post_init(application) -> None:
    """Set bot commands after initialization."""
    from telegram import BotCommand
    commands = [
        BotCommand("start", "Главное меню"),
        BotCommand("menu", "Показать меню"),
    ]
    await application.bot.set_my_commands(commands)


def main() -> None:
    """Initialize and run the bot."""
    logger.info("Starting DotsAndBoxes bot...")
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Set bot commands on startup
    application.post_init = post_init
    
    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("menu", menu_text_handler))
    
    # Handle reply keyboard buttons
    application.add_handler(MessageHandler(filters.Regex(r"^📋 Меню$"), menu_text_handler))
    application.add_handler(MessageHandler(filters.Regex(r"^▶️ Продолжить$"), start_command))
    # Retire old persistent keyboards into a screen with working actions.
    application.add_handler(MessageHandler(filters.Regex(r"^(💝 Поддержать|🗑 Очистить чат)$"), menu_text_handler))
    
    # Menu navigation
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern=r"^menu:"))
    
    # Play mode selection (mode, size, diff, cancel queue)
    application.add_handler(CallbackQueryHandler(play_callback, pattern=r"^(mode:|size:|diff:|cq$)"))
    
    # In-game actions (edges, noop, rematch, afk, leave)
    # e:h:r:c for horizontal edges, e:v:r:c for vertical edges
    # noop:reason for non-clickable cells
    application.add_handler(CallbackQueryHandler(game_callback, pattern=r"^(e:|noop:|rm|afk:|leave|num:|pg:)"))
    
    async def unhandled_callback(update: Update, context) -> None:
        print(f"DEBUG: Unhandled callback: {update.callback_query.data}")
        await update.callback_query.answer()
        
    application.add_handler(CallbackQueryHandler(unhandled_callback))
    
    # Start polling
    logger.info("Bot is running. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
