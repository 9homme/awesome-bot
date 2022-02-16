import pandas as pd
import telegram
import datetime
import binance
import config
from finta import TA


def heikinashi(bars):
    bars = bars.copy()

    bars["ha_close"] = (bars["open"] + bars["high"] + bars["low"] + bars["close"]) / 4

    # ha open
    index = bars.index[0]
    bars.at[index, "ha_open"] = (bars.at[index, "open"] + bars.at[index, "close"]) / 2
    for i in range(1, len(bars)):
        index = bars.index[i]
        previous_index = bars.index[i - 1]
        bars.at[index, "ha_open"] = (
            bars.at[previous_index, "ha_open"] + bars.at[previous_index, "ha_close"]
        ) / 2

    bars["ha_high"] = bars.loc[:, ["high", "ha_open", "ha_close"]].max(axis=1)
    bars["ha_low"] = bars.loc[:, ["low", "ha_open", "ha_close"]].min(axis=1)

    return pd.DataFrame(
        index=bars.index,
        data={
            "open": bars["ha_open"],
            "high": bars["ha_high"],
            "low": bars["ha_low"],
            "close": bars["ha_close"],
        },
    )


def crossover(index, s1, s2):
    s1_lag = s1.shift(1)
    s2_lag = s2.shift(1)
    return s1_lag[index] <= s2_lag[index] and s1[index] > s2[index]


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
    coin_list = binance.get_all_coins_list()
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
            ohlc = binance.get_kline(coin)
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
    latest_price = binance.futures_recent_trades(symbol=coin)
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

    if crossover(message_datetime, fast_signal, slow_signal) and is_in_trend(
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
    elif crossover(message_datetime, slow_signal, fast_signal) and is_in_trend(
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
        heikin = heikinashi(ohlc.iloc[1:, :])
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
