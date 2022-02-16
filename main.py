from binance import Client, ThreadedWebsocketManager
from finta import TA
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
)

import traceback
import pandas as pd
import numpy as np
import sys
import uuid
import dill
import os

import helper
import analysis
import telegram
import config

print("Number of arguments:", len(sys.argv), "arguments.")
print("Argument List:", str(sys.argv))

# state
current_candle_datetime = None
current_position = None
current_price = None
current_quantity = None
exit_price = None
take_profit_price = None
initial_ticker = config.ticker

# binance client
client = Client(config.api_key, config.api_secret)

exchange_info = client.futures_exchange_info()


def get_symbol_decimal(symbol):
    decimal = list(filter(lambda r: r["symbol"] == symbol, exchange_info["symbols"]))[
        0
    ]["quantityPrecision"]
    return decimal


def get_kline(coin_ticker):
    klines = np.array(
        client.futures_historical_klines(
            coin_ticker,
            config.interval,
            config.begin_load_data_from,
        )
    )

    # parse binance data to dataframe
    ohlc = pd.DataFrame(
        data=klines[0:, 1:6],
        index=pd.to_datetime(klines[0:, 0], unit="ms"),
        columns=[
            "open",
            "high",
            "low",
            "close",
            "volume",
        ],
    )
    ohlc["open"] = pd.to_numeric(ohlc["open"])
    ohlc["high"] = pd.to_numeric(ohlc["high"])
    ohlc["low"] = pd.to_numeric(ohlc["low"])
    ohlc["close"] = pd.to_numeric(ohlc["close"])
    ohlc["volume"] = pd.to_numeric(ohlc["volume"])

    return ohlc


def order(
    symbol, position, price, usdt_amount, reduce_only="false", new_exit_price=None
):
    global current_position
    global current_price
    global current_quantity
    global exit_price
    global take_profit_price
    # try to set leverage and margin type
    if reduce_only == "false":
        try:
            client.futures_change_margin_type(symbol=ticker, marginType="ISOLATED")
        except Exception as e:
            print(f"Cannot set marginType, message: {str(e)}")
        try:
            client.futures_change_leverage(symbol=ticker, leverage=config.leverage)
        except Exception as e:
            print(f"Cannot change leverage, message: {str(e)}")
    total_to_invest = usdt_amount * config.leverage
    if current_quantity != None:
        quantity = current_quantity
    else:
        full_risk_quantity = total_to_invest / price
        risk = (abs(new_exit_price - price) / price) * config.leverage
        if config.risk_mode == "manage" and risk > config.max_risk:
            quantity = (full_risk_quantity / risk) * config.max_risk
        else:
            quantity = full_risk_quantity
        quantity = helper.round_decimals_down(quantity, get_symbol_decimal(symbol))
        telegram.send_telegram_and_print(
            f"Risk mode: {config.risk_mode}, risk: {risk}, max_risk: {config.max_risk} will order qty: {quantity} [full risk qty: {full_risk_quantity}]"
        )
    telegram.send_telegram_and_print(
        f"Creating '{position}' order for {symbol} at {price} with quantity: {quantity} [reduceOnly={reduce_only}]"
    )
    side = None
    if position == "long":
        side = Client.SIDE_BUY
    elif position == "short":
        side = Client.SIDE_SELL

    client_order_id = str(uuid.uuid4())
    client.futures_create_order(
        symbol=symbol,
        side=side,
        type=Client.ORDER_TYPE_MARKET,
        quantity=quantity,
        newClientOrderId=client_order_id,
        reduceOnly=reduce_only,
    )

    order = None
    while True:
        telegram.send_telegram_and_print(
            datetime.now(), f"Waiting order: {client_order_id} to be filled"
        )
        try:
            order = client.futures_get_order(
                symbol=symbol, origClientOrderId=client_order_id
            )
            if order["status"] == Client.ORDER_STATUS_FILLED:
                telegram.send_telegram_and_print(
                    datetime.now(),
                    f"Order: {client_order_id}({order['orderId']}) was filled with avg price: {order['avgPrice']} and qty: {order['executedQty']}",
                )
                break
        except Exception as e:
            print(f"Get order error {str(e)}. Retry...")

    if reduce_only == "true":
        current_position = None
        current_price = None
        current_quantity = None
        exit_price = None
        take_profit_price = None
    else:
        current_position = position
        current_price = float(order["avgPrice"])
        current_quantity = float(order["executedQty"])
    # save state every time we make an order
    save_state()
    print(order)


def calculate_total_revenue(
    position, current_revenue, quantity, entry_price, exit_price
):
    new_revenue = current_revenue
    if position == "long":
        new_revenue = current_revenue + (quantity * (exit_price - entry_price))

    elif position == "short":
        new_revenue = current_revenue + (quantity * (entry_price - exit_price))

    position_result = "Win" if new_revenue > current_revenue else "Lose"
    telegram.send_telegram_and_print(
        datetime.now(),
        f"{position_result}!!!!! {(abs(new_revenue - current_revenue)/current_revenue)*100}%",
    )
    return new_revenue


def handle_socket_message(msg):
    global current_candle_datetime
    global current_position
    global current_price
    global current_quantity
    global exit_price
    global take_profit_price
    global total_revenue
    global ticker
    try:
        # convert milliseconds timestamp to datetime
        # remove timezone to compatible with pandas
        message_datetime = datetime.fromtimestamp(
            msg["k"]["t"] / 1000.0, timezone.utc
        ).replace(tzinfo=None)
        latest_price = client.futures_recent_trades(symbol=ticker)
        latest_price = float(latest_price[-1]["price"])
        # process atr stop loss with latest price for early exit strategy
        if current_candle_datetime == message_datetime:
            if current_position == "long" and latest_price < exit_price:
                telegram.send_telegram_and_print(
                    datetime.now(), f"Exit with ATR at {latest_price}"
                )
                total_revenue = calculate_total_revenue(
                    current_position,
                    total_revenue,
                    current_quantity,
                    current_price,
                    latest_price,
                )
                telegram.send_telegram_and_print(
                    datetime.now(), f"TotalRevenue: {total_revenue}"
                )
                order(ticker, "short", latest_price, total_revenue, reduce_only="true")
            # take profit
            elif current_position == "long" and latest_price >= take_profit_price:
                telegram.send_telegram_and_print(
                    datetime.now(), f"Take profit at {latest_price}"
                )
                total_revenue = calculate_total_revenue(
                    current_position,
                    total_revenue,
                    current_quantity,
                    current_price,
                    latest_price,
                )
                telegram.send_telegram_and_print(
                    datetime.now(), f"TotalRevenue: {total_revenue}"
                )
                order(ticker, "short", latest_price, total_revenue, reduce_only="true")
            # exit short with atr stop loss
            elif current_position == "short" and latest_price > exit_price:
                telegram.send_telegram_and_print(
                    datetime.now(), f"Exit with ATR at {latest_price}"
                )
                total_revenue = calculate_total_revenue(
                    current_position,
                    total_revenue,
                    current_quantity,
                    current_price,
                    latest_price,
                )
                telegram.send_telegram_and_print(
                    datetime.now(), f"TotalRevenue: {total_revenue}"
                )
                order(ticker, "long", latest_price, total_revenue, reduce_only="true")
            # take profit
            elif current_position == "short" and latest_price <= take_profit_price:
                telegram.send_telegram_and_print(
                    datetime.now(), f"Take profit at {latest_price}"
                )
                total_revenue = calculate_total_revenue(
                    current_position,
                    total_revenue,
                    current_quantity,
                    current_price,
                    latest_price,
                )
                telegram.send_telegram_and_print(
                    datetime.now(), f"TotalRevenue: {total_revenue}"
                )
                order(ticker, "long", latest_price, total_revenue, reduce_only="true")
            else:
                print(
                    datetime.now(),
                    ticker,
                    message_datetime,
                    f"Latest price = {latest_price}",
                    "already processed. Waiting for next closed candle...",
                    end="\r",
                )
        # process indicator if only candle is just closed
        elif current_candle_datetime != message_datetime:
            current_candle_datetime = message_datetime
            # if position is None then try to scouting for the best coin *** start with initial coin
            if current_position == None:
                moon_coin = coin_scouting(
                    message_datetime,
                    config.trend_check,
                    config.risk_reward_ratio,
                    config.max_risk,
                    config.leverage,
                    config.risk_mode,
                    config.heikin_check,
                    config.heikin_look_back,
                    config.rsi_check,
                    config.rsi_buy,
                    config.rsi_sell,
                    config.atr_multiplier,
                    config.signal_type,
                )
                if moon_coin != None:
                    ticker = moon_coin["symbol"]
                    latest_price = moon_coin["latest_price"]
                    position = moon_coin["position"]
                    fast_signal = moon_coin["fast_signal"]
                    slow_signal = moon_coin["slow_signal"]
                    order(
                        ticker,
                        position,
                        latest_price,
                        total_revenue,
                        reduce_only="false",
                        new_exit_price=moon_coin["exit_price"],
                    )
                    exit_price = moon_coin["exit_price"]
                    take_profit_price = moon_coin["take_profit_price"]
                    telegram.send_telegram_and_print(
                        message_datetime,
                        f"{current_position}!!!! signal_type: {config.signal_type} fast_signal: {fast_signal[message_datetime]} slow_signal: {slow_signal[message_datetime]} current_price: {current_price} exit_at: {exit_price} take_profit_at: {take_profit_price}",
                    )
            # If there is current holding position
            else:
                # analyze without trend check because we are going to close position
                analyze_result = analyze_coin(
                    message_datetime,
                    ticker,
                    False,
                    config.risk_reward_ratio,
                    config.heikin_check,
                    config.heikin_look_back,
                    config.rsi_check,
                    config.rsi_buy,
                    config.rsi_sell,
                    config.atr_multiplier,
                    config.signal_type,
                )
                new_position = analyze_result["position"]
                close_price = analyze_result["last_close_price"]
                fast_signal = analyze_result["fast_signal"]
                slow_signal = analyze_result["slow_signal"]
                latest_price = analyze_result["latest_price"]
                high_price = analyze_result["high_price"]
                low_price = analyze_result["low_price"]
                atr = analyze_result["atr"]
                in_trend = analyze_result["in_trend"]
                telegram.send_telegram_and_print(
                    message_datetime,
                    ticker,
                    config.signal_type,
                    f"closed: {close_price}",
                    f"fast_signal: {fast_signal[message_datetime]}",
                    f"slow_signal: {slow_signal[message_datetime]}",
                )
                # Exit with CDC then create new opposite order
                if new_position != None and current_position != new_position:
                    telegram.send_telegram_and_print(
                        message_datetime, f"Exit with CDC at {latest_price}"
                    )
                    total_revenue = calculate_total_revenue(
                        current_position,
                        total_revenue,
                        current_quantity,
                        current_price,
                        latest_price,
                    )
                    telegram.send_telegram_and_print(
                        message_datetime, f"TotalRevenue: {total_revenue}"
                    )
                    order(
                        ticker,
                        new_position,
                        latest_price,
                        total_revenue,
                        reduce_only="true",
                    )
                    if (
                        in_trend
                        and not too_risk(
                            ticker,
                            latest_price,
                            analyze_result["exit_price"],
                            config.leverage,
                            config.max_risk,
                            config.risk_mode,
                        )
                        and analyze_result["rsi_result"] == True
                    ):
                        order(
                            ticker,
                            new_position,
                            latest_price,
                            total_revenue,
                            reduce_only="false",
                            new_exit_price=analyze_result["exit_price"],
                        )
                        exit_price = analyze_result["exit_price"]
                        take_profit_price = analyze_result["take_profit_price"]
                        telegram.send_telegram_and_print(
                            message_datetime,
                            f"{current_position}!!!! signal_type: {config.signal_type} fast_signal: {fast_signal[message_datetime]} slow_signal: {slow_signal[message_datetime]} current_price: {current_price} exit_at: {exit_price} take_profit_at: {take_profit_price}",
                        )
                # re calculate exit price if it is higher for long
                elif current_position == "long":
                    new_exit_price = low_price - atr[message_datetime]
                    if new_exit_price > exit_price:
                        telegram.send_telegram_and_print(
                            message_datetime,
                            f"ATR trailing new exit price: {new_exit_price}",
                        )
                        exit_price = new_exit_price
                # re calculate exit price if it is lower for short
                elif current_position == "short":
                    new_exit_price = high_price + atr[message_datetime]
                    if new_exit_price < exit_price:
                        telegram.send_telegram_and_print(
                            message_datetime,
                            f"ATR trailing new exit price: {new_exit_price}",
                        )
                        exit_price = new_exit_price
    except Exception as e:
        print(f"Some error occured but just skip, message: {str(e)}")
        print(traceback.format_exc())


def is_in_trend(
    position,
    trend_check,
    close_price,
    ohlc,
    message_datetime,
    heikin_check,
    heikin_look_back,
):
    result = False
    if config.trend_mode == "ema":
        ema50 = TA.EMA(ohlc, 50)
        if position == "long":
            result = not trend_check or close_price > ema50[message_datetime]
        elif position == "short":
            result = not trend_check or close_price < ema50[message_datetime]
        telegram.send_telegram_and_print(
            f"Analyzing trending[{config.trend_mode}] with trend_check: {trend_check} EMA50: {ema50[message_datetime]} close_price: {close_price} position: {position}, result: {result}"
        )
    elif config.trend_mode == "adx":
        adx = TA.ADX(ohlc)
        result = not trend_check or adx[message_datetime] >= 20
        telegram.send_telegram_and_print(
            f"Analyzing trending[{config.trend_mode}] with trend_check: {trend_check} ADX:{adx[message_datetime]}, result: {result}"
        )
    # use both strategy
    elif config.trend_mode == "both":
        adx = TA.ADX(ohlc)
        ema50 = TA.EMA(ohlc, 50)
        if position == "long":
            result = not trend_check or (
                close_price > ema50[message_datetime] and adx[message_datetime] >= 20
            )
        elif position == "short":
            result = not trend_check or (
                close_price < ema50[message_datetime] and adx[message_datetime] >= 20
            )
        telegram.send_telegram_and_print(
            f"Analyzing trending[{config.trend_mode}] with trend_check: {trend_check} ADX:{adx[message_datetime]} EMA50: {ema50[message_datetime]} close_price: {close_price} position: {position}, result: {result}"
        )
    else:
        result = not trend_check

    # after trend check, if it in trend, then check for heikin if required.
    if trend_check and result == True and heikin_check:
        telegram.send_telegram_and_print("Going to check for heikinashi")
        # this to remove 1st row which have NaN value
        heikin = analysis.heikinashi(ohlc.iloc[1:, :])
        for i in range(0, heikin_look_back):
            checking_heikin_candle = heikin.shift(i)
            open_heikin = checking_heikin_candle["open"][message_datetime]
            close_heikin = checking_heikin_candle["close"][message_datetime]
            if position == "long":
                result = close_heikin > open_heikin
            elif position == "short":
                result = close_heikin < open_heikin
            telegram.send_telegram_and_print(
                f"heikinashi open: {open_heikin} close: {close_heikin} result: {result}"
            )
            if result == False:
                break

    return result


def get_all_coins_list():
    all_coins = [initial_ticker]
    if config.auto_scouting == True:
        # if manual override coins list
        if len(config.all_coins_list) > 0:
            all_coins = config.all_coins_list
        else:
            # then get all coins from binance
            # get only top X coin by value trade
            all_coins = list(
                filter(
                    lambda symbol: symbol.endswith("USDT"),
                    map(
                        lambda row: row["symbol"],
                        sorted(
                            client.futures_ticker(),
                            key=lambda r: float(r["volume"])
                            * float(r["weightedAvgPrice"]),
                            reverse=True,
                        ),
                    ),
                )
            )[config.offset_top_coin_scouting : config.max_top_coin_scouting]
    return all_coins


def coin_scouting(
    message_datetime,
    trend_check,
    risk_reward_ratio,
    max_risk,
    leverage,
    risk_mode,
    heikin_check,
    heikin_look_back,
    rsi_check,
    rsi_buy,
    rsi_sell,
    atr_multiplier,
    signal_type,
):
    telegram.send_telegram_and_print(
        datetime.now(), f"Try scouting for the best trade..."
    )
    coin_list = get_all_coins_list()
    moon_coin = None
    for coin in coin_list:
        result = analyze_coin(
            message_datetime,
            coin,
            trend_check,
            risk_reward_ratio,
            heikin_check,
            heikin_look_back,
            rsi_check,
            rsi_buy,
            rsi_sell,
            atr_multiplier,
            signal_type,
        )
        if (
            result != None
            and result["position"] != None
            and not too_risk(
                coin,
                result["latest_price"],
                result["exit_price"],
                leverage,
                max_risk,
                risk_mode,
            )
            and result["rsi_result"] == True
        ):
            moon_coin = result
            break
    return moon_coin


def analyze_coin(
    message_datetime,
    coin,
    trend_check,
    risk_reward_ratio,
    heikin_check,
    heikin_look_back,
    rsi_check,
    rsi_buy,
    rsi_sell,
    atr_multiplier,
    signal_type,
):
    # load historical data
    ohlc = None
    moon_coin = None
    retry_limit = 20
    count = 0
    while True:
        try:
            ohlc = get_kline(coin)
            ohlc["close"][message_datetime]
            break
        except:
            print("kline historical data in not complete, retry...")
            count = count + 1
            if count > retry_limit:
                telegram.send_telegram_and_print(f"{coin} is unavailable, will skip!!")
                break

    # shift ohlc for 1 row, we expect to take action based on last closed candle
    ohlc = ohlc.shift(1)
    fast_signal = None
    slow_signal = None
    if signal_type == "wavetrend":
        wt = TA.WTO(ohlc)
        wt1 = wt["WT1."]
        wt2 = wt["WT2."]
        fast_signal = wt1
        slow_signal = wt2
    elif signal_type == "cdc":
        ema12 = TA.EMA(ohlc, 12)
        ema26 = TA.EMA(ohlc, 26)
        fast_signal = ema12
        slow_signal = ema26
    atr = TA.ATR(ohlc)
    atr = atr * atr_multiplier
    rsi = TA.RSI(ohlc)
    last_close_price = ohlc["close"][message_datetime]
    low_price = ohlc["low"][message_datetime]
    high_price = ohlc["high"][message_datetime]
    latest_price = client.futures_recent_trades(symbol=coin)
    latest_price = float(latest_price[-1]["price"])
    print(
        f"Analyzing {coin} last_close_price: {last_close_price} latest_price: {latest_price} signal_type: {signal_type} fast_signal: {fast_signal[message_datetime]} slow_signal: {slow_signal[message_datetime]}"
    )
    moon_coin = {}
    moon_coin["position"] = None
    moon_coin["in_trend"] = None
    moon_coin["rsi_result"] = None
    moon_coin["symbol"] = coin
    moon_coin["ohlc"] = ohlc
    moon_coin["fast_signal"] = fast_signal
    moon_coin["slow_signal"] = slow_signal
    moon_coin["atr"] = atr
    moon_coin["latest_price"] = latest_price
    moon_coin["last_close_price"] = last_close_price
    moon_coin["high_price"] = high_price
    moon_coin["low_price"] = low_price

    if analysis.crossover(message_datetime, fast_signal, slow_signal) and is_in_trend(
        "long",
        trend_check,
        last_close_price,
        ohlc,
        message_datetime,
        heikin_check,
        heikin_look_back,
    ):
        moon_coin["in_trend"] = is_in_trend(
            "long",
            True,
            last_close_price,
            ohlc,
            message_datetime,
            heikin_check,
            heikin_look_back,
        )
        moon_coin["position"] = "long"
        moon_coin["exit_price"] = low_price - atr[message_datetime]
        moon_coin["take_profit_price"] = latest_price + (
            (latest_price - moon_coin["exit_price"]) * risk_reward_ratio
        )
    elif analysis.crossover(message_datetime, slow_signal, fast_signal) and is_in_trend(
        "short",
        trend_check,
        last_close_price,
        ohlc,
        message_datetime,
        heikin_check,
        heikin_look_back,
    ):
        moon_coin["in_trend"] = is_in_trend(
            "short",
            True,
            last_close_price,
            ohlc,
            message_datetime,
            heikin_check,
            heikin_look_back,
        )
        moon_coin["position"] = "short"
        moon_coin["exit_price"] = high_price + atr[message_datetime]
        moon_coin["take_profit_price"] = latest_price + (
            (latest_price - moon_coin["exit_price"]) * risk_reward_ratio
        )
    if moon_coin["position"] != None:
        moon_coin["rsi_result"] = check_rsi(
            moon_coin["position"], rsi_check, rsi[message_datetime], rsi_buy, rsi_sell
        )
    return moon_coin


def check_rsi(position, rsi_check, current_rsi, rsi_buy, rsi_sell):
    telegram.send_telegram_and_print(
        f"Checking RSI:{rsi_check}, potition: {position}, rsi: {current_rsi}"
    )
    return (
        not rsi_check
        or (position == "long" and current_rsi >= rsi_buy)
        or (position == "short" and current_rsi <= rsi_sell)
    )


def too_risk(symbol, latest_price, exit_price, leverage, max_risk, risk_mode):
    if risk_mode == "skip":
        risk = (abs(latest_price - exit_price) / latest_price) * leverage
        telegram.send_telegram_and_print(
            symbol,
            f"Checking risk percentage latest_price: {latest_price} exit_price: {exit_price} leverage: {leverage} risk: {risk*100}%",
        )
        if risk <= max_risk:
            telegram.send_telegram_and_print(symbol, f"Going to take risk...")
            return False
        else:
            telegram.send_telegram_and_print(symbol, f"Too much risk, will skip...")
            return True
    else:
        telegram.send_telegram_and_print(
            symbol, f"Risk mode: {risk_mode}, will not skip the trade"
        )
        return False


def save_state():
    state = {}
    state["ticker"] = ticker
    state["datetime"] = current_candle_datetime
    state["position"] = current_position
    state["price"] = current_price
    state["quantity"] = current_quantity
    state["exit_price"] = round(exit_price, 5) if exit_price != None else None
    state["take_profit_price"] = (
        round(take_profit_price, 5) if take_profit_price != None else None
    )
    state["total_revenue"] = round(total_revenue, 5) if total_revenue != None else None
    with open(f"{config.config_name}_state.pkl", "wb") as file:
        dill.dump(state, file)


def load_state():
    global current_candle_datetime
    global current_position
    global current_price
    global current_quantity
    global exit_price
    global ticker
    global take_profit_price
    global total_revenue
    try:
        with open(f"{config.config_name}_state.pkl", "rb") as file:
            state = dill.load(file)
            ticker = state["ticker"] if state["ticker"] != None else initial_ticker
            current_candle_datetime = state["datetime"]
            current_position = state["position"]
            current_price = state["price"]
            current_quantity = state["quantity"]
            exit_price = state["exit_price"]
            take_profit_price = state["take_profit_price"]
            if state["total_revenue"] != None:
                total_revenue = state["total_revenue"]
    except:
        print(f"No state for {ticker}, bot will start from zero")


def state(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(get_state_str())


def update_total_revenue(update: Update, context: CallbackContext) -> None:
    global total_revenue
    if len(context.args) == 1:
        total_revenue = float(context.args[0])
        update.message.reply_text(f"Total revenue updated to {total_revenue}")
    else:
        update.message.reply_text("Invalid arguments. Require [total_revenue]")


def exit_current_trade(update: Update, context: CallbackContext) -> None:
    global total_revenue
    if current_position != None:
        order_position = None
        if current_position == "short":
            order_position = "long"
        elif current_position == "long":
            order_position = "short"
        latest_price = client.futures_recent_trades(symbol=ticker)
        latest_price = float(latest_price[-1]["price"])
        total_revenue = calculate_total_revenue(
            current_position,
            total_revenue,
            current_quantity,
            current_price,
            latest_price,
        )
        update.message.reply_text(f"TotalRevenue: {total_revenue}")
        order(ticker, order_position, latest_price, total_revenue, reduce_only="true")
    else:
        update.message.reply_text("There is no holding position.")
        update.message.reply_text(get_state_str())


def manual_order(update: Update, context: CallbackContext) -> None:
    global ticker
    global exit_price
    global take_profit_price
    if len(context.args) == 2:
        if current_position == None:
            order_position = context.args[0]
            order_symbol = context.args[1]
            update.message.reply_text(
                f"Going to proceed {order_position} for {order_symbol}"
            )
            ticker = order_symbol
            latest_price = client.futures_recent_trades(symbol=ticker)
            latest_price = float(latest_price[-1]["price"])
            # load historical data
            ohlc = get_kline(ticker)
            last_closed_candle = ohlc.iloc[-2]
            close_price = last_closed_candle["close"]
            low_price = last_closed_candle["low"]
            high_price = last_closed_candle["high"]
            atr = TA.ATR(ohlc)
            last_atr = atr[-2]
            if order_position == "long":
                exit_price = low_price - last_atr
            elif order_position == "short":
                exit_price = high_price + last_atr
            take_profit_price = close_price + (
                (close_price - exit_price) * config.risk_reward_ratio
            )
            order(
                ticker,
                order_position,
                latest_price,
                total_revenue,
                reduce_only="false",
                new_exit_price=exit_price,
            )
        else:
            update.message.reply_text(
                "There is current holding position. Please exit from current position first"
            )
            update.message.reply_text(get_state_str())
    else:
        update.message.reply_text(
            "Invalid order arguments. Require [short|long] [SYMBOL]"
        )


def echo(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(update.message.text)


def get_state_str():
    return f"current state for {ticker} datetime: {current_candle_datetime} position: {current_position} price: {current_price} quantity: {current_quantity} exit_price: {exit_price} take_profit: {take_profit_price} total_revenue: {total_revenue}"


def main():
    try:
        # load bot state
        load_state()
        telegram.send_telegram_and_print(get_state_str())
        # socket manager using threads
        twm = ThreadedWebsocketManager()
        twm.start()

        twm.start_kline_socket(
            callback=handle_socket_message,
            symbol=ticker,
            interval=config.interval,
        )

        # telegram
        updater = Updater(config.telegram_token, use_context=True)
        # Get the dispatcher to register handlers
        dispatcher = updater.dispatcher

        # on different commands - answer in Telegram
        dispatcher.add_handler(CommandHandler("state", state))
        dispatcher.add_handler(CommandHandler("exit", exit_current_trade))
        dispatcher.add_handler(CommandHandler("order", manual_order))
        dispatcher.add_handler(CommandHandler("revenue", update_total_revenue))

        # on non command i.e message - echo the message on Telegram
        dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))

        # Start the Bot
        updater.start_polling()

        while True:
            twm.join(0.5)
    except KeyboardInterrupt:
        save_state()
        os._exit(1)

    except Exception as e:
        print(f"Some error occured but just skip, message: {str(e)}")
        main()


if __name__ == "__main__":
    main()
