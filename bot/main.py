"""
DotsAndBoxes Telegram Bot — Entry Point

Run with: python -m bot.main
"""

import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from bot.config import BOT_TOKEN, logger
from bot.handlers.start import start_command, main_menu_callback
from bot.handlers.play import play_callback
from bot.handlers.game import game_callback


def main() -> None:
    """Initialize and run the bot."""
    logger.info("Starting DotsAndBoxes bot...")
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    
    # Menu navigation
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern=r"^menu:"))
    
    # Play mode selection (mode, size, diff, cancel queue)
    application.add_handler(CallbackQueryHandler(play_callback, pattern=r"^(mode|size|diff|cq):"))
    
    # In-game actions (edges, noop, rematch, afk, leave)
    # e:h:r:c for horizontal edges, e:v:r:c for vertical edges
    # noop:reason for non-clickable cells
    application.add_handler(CallbackQueryHandler(game_callback, pattern=r"^(e:|noop:|rm|afk:|leave)"))
    
    # Start polling
    logger.info("Bot is running. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
