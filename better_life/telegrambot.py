import os
import time

import dotenv
import telegram

dotenv.load_dotenv()

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
import logging

logger = logging.getLogger(__name__)


def get_bot():
    return telegram.Bot(TOKEN)


async def send_message(text: str, parse_mode="HTML"):
    while True:
        try:
            async with get_bot() as bot:
                # https://core.telegram.org/bots/api#html-style
                await bot.send_message(text=text, chat_id=CHAT_ID, parse_mode=parse_mode)
            break

        except telegram.error.TimedOut as e:
            logger.warning(f'텔레그램 에러로 잠시 후 다시 시도합니다. {text=!r} {e!r}')
            time.sleep(0.5)

        except Exception as e:
            logger.error(f'텔레그램 메세지를 보내지 못했어요. {text=!r} {e!r}')
            break
