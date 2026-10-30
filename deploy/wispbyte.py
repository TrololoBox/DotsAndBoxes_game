"""Deployment entry point: pinned source, quiet HTTP logs and offline preflight."""
import logging
import os
from pathlib import Path
import sys

APP = Path(__file__).resolve().parent.parent
os.chdir(APP)
sys.path.insert(0, str(APP))
os.environ["LOG_LEVEL"] = "INFO"
for name in ("httpx", "httpcore", "telegram"):
    logging.getLogger(name).setLevel(logging.WARNING)

if "--preflight" in sys.argv:
    os.environ["BOT_TOKEN"] = "123456789:OFFLINE_PREFLIGHT_NOT_A_REAL_TOKEN"
    from bot.main import main
    from game.board import Board
    from render.board_renderer import render_board
    for size in (3, 6):
        board = Board(size, size)
        board.place_edge("h_0_0", "1")
        for theme in ("classic", "forest", "night"):
            png = render_board(board, theme, "1", "bot", show_numbers=True,
                               last_edge_id="h_0_0", recent_edge_ids=["h_0_0"])
            assert png.startswith(b"\x89PNG\r\n\x1a\n")
    print("PREFLIGHT PASS: numbered UX, last move, 3 themes, 3x3 and 6x6; no Telegram calls", flush=True)
else:
    from dotenv import load_dotenv
    # Reuse the existing host secret, independently of the deployed source folder.
    load_dotenv(os.environ.get("DOTS_ENV_FILE", str(APP / ".env")))
    from bot.config import BOT_TOKEN
    original_factory = logging.getLogRecordFactory()

    def safe_record(*args, **kwargs):
        record = original_factory(*args, **kwargs)
        record.msg = record.getMessage().replace(BOT_TOKEN, "[REDACTED]")
        record.args = ()
        return record

    logging.setLogRecordFactory(safe_record)
    import bot.main as entry
    original_post_init = entry.post_init

    async def verified_post_init(application):
        await original_post_init(application)
        revision = os.environ.get("DEPLOYMENT_REVISION", "local")
        print(f"TELEGRAM CONNECTED: @{application.bot.username} | numbered-ux-v2 | {revision}", flush=True)

    entry.post_init = verified_post_init
    logging.getLogger("telegram.ext.Application").setLevel(logging.INFO)
    entry.main()
