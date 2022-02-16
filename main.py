from binance import ThreadedWebsocketManager
from datetime import datetime, timezone
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
)
import traceback
import sys
import os
import telegram
import config
import state
import binance
import strategy

print("Number of arguments:", len(sys.argv), "arguments.")
print("Argument List:", str(sys.argv))


def handle_socket_message(msg):
    try:
        # convert milliseconds timestamp to datetime
        # remove timezone to compatible with pandas
        message_datetime = datetime.fromtimestamp(
            msg["k"]["t"] / 1000.0, timezone.utc
        ).replace(tzinfo=None)
        latest_price = binance.futures_recent_trades(symbol=state.ticker)
        latest_price = float(latest_price[-1]["price"])
        # process atr stop loss with latest price for early exit strategy
        if state.current_candle_datetime == message_datetime:
            strategy.process_tick(message_datetime, latest_price)
        # process indicator if only candle is just closed
        elif state.current_candle_datetime != message_datetime:
            state.current_candle_datetime = message_datetime
            # if position is None then try to scouting for the best coin *** start with initial coin
            if state.current_position == None:
                strategy.process_closed_candle_without_position(message_datetime)
            # If there is current holding position
            else:
                # analyze without trend check because we are going to close position
                strategy.process_closed_candle_for_current_position(message_datetime)
    except Exception as e:
        print(f"Some error occured but just skip, message: {str(e)}")
        print(traceback.format_exc())


def main():
    try:
        # load bot state
        state.load_state()
        telegram.send_telegram_and_print(state.get_state_str())
        # socket manager using threads
        twm = ThreadedWebsocketManager()
        twm.start()

        twm.start_kline_socket(
            callback=handle_socket_message,
            symbol=state.ticker,
            interval=config.interval,
        )

        # telegram
        updater = Updater(config.telegram_token, use_context=True)
        # Get the dispatcher to register handlers
        dispatcher = updater.dispatcher

        # on different commands - answer in Telegram
        dispatcher.add_handler(CommandHandler("state", telegram.state))
        dispatcher.add_handler(CommandHandler("exit", telegram.exit_current_trade))
        dispatcher.add_handler(CommandHandler("order", telegram.manual_order))
        dispatcher.add_handler(
            CommandHandler("revenue", telegram.update_state.total_revenue)
        )

        # on non command i.e message - echo the message on Telegram
        dispatcher.add_handler(
            MessageHandler(Filters.text & ~Filters.command, telegram.echo)
        )

        # Start the Bot
        updater.start_polling()

        while True:
            twm.join(0.5)
    except KeyboardInterrupt:
        state.save_state()
        os._exit(1)

    except Exception as e:
        print(f"Some error occured but just skip, message: {str(e)}")
        main()


if __name__ == "__main__":
    main()
