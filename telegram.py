from telegram import Update
from telegram.ext import (
    Updater,
    CallbackContext,
)
import config
import state
import helper
import binance
from finta import TA


def send_telegram_and_print(*messages, end: str = None):
    updater = Updater(config.telegram_token, use_context=True)
    message = " ".join(map(lambda msg: str(msg), messages))
    updater.bot.send_message(config.chat_id, message)
    print(message, end=end)


def state(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(state.get_state_str())


def update_total_revenue(update: Update, context: CallbackContext) -> None:
    if len(context.args) == 1:
        state.total_revenue = float(context.args[0])
        update.message.reply_text(f"Total revenue updated to {state.total_revenue}")
    else:
        update.message.reply_text("Invalid arguments. Require [total_revenue]")


def exit_current_trade(update: Update, context: CallbackContext) -> None:
    if state.current_position != None:
        order_position = None
        if state.current_position == "short":
            order_position = "long"
        elif state.current_position == "long":
            order_position = "short"
        latest_price = binance.futures_recent_trades(symbol=state.ticker)
        latest_price = float(latest_price[-1]["price"])
        state.total_revenue = helper.calculate_total_revenue(
            state.current_position,
            state.total_revenue,
            state.current_quantity,
            state.current_price,
            latest_price,
        )
        update.message.reply_text(f"TotalRevenue: {state.total_revenue}")
        binance.order(
            state.ticker,
            order_position,
            latest_price,
            state.total_revenue,
            reduce_only="true",
        )
    else:
        update.message.reply_text("There is no holding position.")
        update.message.reply_text(state.get_state_str())


def manual_order(update: Update, context: CallbackContext) -> None:
    if len(context.args) == 2:
        if state.current_position == None:
            order_position = context.args[0]
            order_symbol = context.args[1]
            update.message.reply_text(
                f"Going to proceed {order_position} for {order_symbol}"
            )
            state.ticker = order_symbol
            latest_price = binance.futures_recent_trades(symbol=state.ticker)
            latest_price = float(latest_price[-1]["price"])
            # load historical data
            ohlc = binance.get_kline(state.ticker)
            last_closed_candle = ohlc.iloc[-2]
            close_price = last_closed_candle["close"]
            low_price = last_closed_candle["low"]
            high_price = last_closed_candle["high"]
            atr = TA.ATR(ohlc)
            last_atr = atr[-2]
            if order_position == "long":
                state.exit_price = low_price - last_atr
            elif order_position == "short":
                state.exit_price = high_price + last_atr
            state.take_profit_price = close_price + (
                (close_price - state.exit_price) * config.risk_reward_ratio
            )
            binance.order(
                state.ticker,
                order_position,
                latest_price,
                state.total_revenue,
                reduce_only="false",
                new_exit_price=state.exit_price,
            )
        else:
            update.message.reply_text(
                "There is current holding position. Please exit from current position first"
            )
            update.message.reply_text(state.get_state_str())
    else:
        update.message.reply_text(
            "Invalid order arguments. Require [short|long] [SYMBOL]"
        )


def echo(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(update.message.text)
