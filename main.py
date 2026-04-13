import os
import logging
from dotenv import load_dotenv

load_dotenv()

from slack_bolt.adapter.socket_mode import SocketModeHandler
from src.bot import app
from src.commands import register_commands
from src.db import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("data/bot.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("claude-slack-bot")


def main():
    import time
    os.makedirs("data", exist_ok=True)
    init_db()
    register_commands(app)

    while True:
        try:
            logger.info("Bot starting...")
            handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
            handler.start()
        except (BrokenPipeError, ConnectionError, OSError) as e:
            logger.error(f"Connection lost: {e}. Reconnecting in 5s...")
            time.sleep(5)
        except KeyboardInterrupt:
            logger.info("Shutting down.")
            break
        except Exception as e:
            logger.exception(f"Unexpected error: {e}. Restarting in 10s...")
            time.sleep(10)


if __name__ == "__main__":
    main()
