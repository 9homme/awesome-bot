from telegram.ext import (
    Updater,
)
import config


def send_telegram_and_print(*messages, end: str = None):
    updater = Updater(config.telegram_token, use_context=True)
    message = " ".join(map(lambda msg: str(msg), messages))
    updater.bot.send_message(config.chat_id, message)
    print(message, end=end)
