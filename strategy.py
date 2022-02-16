from datetime import datetime
import telegram
import state
import binance
import helper
import analysis
import config


def process_tick(message_datetime, latest_price):
    if state.current_position == "long" and latest_price < state.exit_price:
        telegram.send_telegram_and_print(
            datetime.now(), f"Exit with ATR at {latest_price}"
        )
        state.total_revenue = helper.calculate_state.total_revenue(
            state.current_position,
            state.total_revenue,
            state.current_quantity,
            state.current_price,
            latest_price,
        )
        telegram.send_telegram_and_print(
            datetime.now(), f"TotalRevenue: {state.total_revenue}"
        )
        binance.order(
            state.ticker, "short", latest_price, state.total_revenue, reduce_only="true"
        )
    # take profit
    elif state.current_position == "long" and latest_price >= state.take_profit_price:
        telegram.send_telegram_and_print(
            datetime.now(), f"Take profit at {latest_price}"
        )
        state.total_revenue = helper.calculate_state.total_revenue(
            state.current_position,
            state.total_revenue,
            state.current_quantity,
            state.current_price,
            latest_price,
        )
        telegram.send_telegram_and_print(
            datetime.now(), f"TotalRevenue: {state.total_revenue}"
        )
        binance.order(
            state.ticker, "short", latest_price, state.total_revenue, reduce_only="true"
        )
    # exit short with atr stop loss
    elif state.current_position == "short" and latest_price > state.exit_price:
        telegram.send_telegram_and_print(
            datetime.now(), f"Exit with ATR at {latest_price}"
        )
        state.total_revenue = helper.calculate_state.total_revenue(
            state.current_position,
            state.total_revenue,
            state.current_quantity,
            state.current_price,
            latest_price,
        )
        telegram.send_telegram_and_print(
            datetime.now(), f"TotalRevenue: {state.total_revenue}"
        )
        binance.order(
            state.ticker, "long", latest_price, state.total_revenue, reduce_only="true"
        )
    # take profit
    elif state.current_position == "short" and latest_price <= state.take_profit_price:
        telegram.send_telegram_and_print(
            datetime.now(), f"Take profit at {latest_price}"
        )
        state.total_revenue = helper.calculate_state.total_revenue(
            state.current_position,
            state.total_revenue,
            state.current_quantity,
            state.current_price,
            latest_price,
        )
        telegram.send_telegram_and_print(
            datetime.now(), f"TotalRevenue: {state.total_revenue}"
        )
        binance.order(
            state.ticker, "long", latest_price, state.total_revenue, reduce_only="true"
        )
    else:
        print(
            datetime.now(),
            state.ticker,
            message_datetime,
            f"Latest price = {latest_price}",
            "already processed. Waiting for next closed candle...",
            end="\r",
        )


def process_closed_candle_without_position(message_datetime):
    moon_coin = analysis.coin_scouting(
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
        state.ticker = moon_coin["symbol"]
        latest_price = moon_coin["latest_price"]
        position = moon_coin["position"]
        fast_signal = moon_coin["fast_signal"]
        slow_signal = moon_coin["slow_signal"]
        binance.order(
            state.ticker,
            position,
            latest_price,
            state.total_revenue,
            reduce_only="false",
            new_exit_price=moon_coin["exit_price"],
        )
        state.exit_price = moon_coin["exit_price"]
        state.take_profit_price = moon_coin["take_profit_price"]
        telegram.send_telegram_and_print(
            message_datetime,
            f"{state.current_position}!!!! signal_type: {config.signal_type} fast_signal: {fast_signal[message_datetime]} slow_signal: {slow_signal[message_datetime]} state.current_price: {state.current_price} exit_at: {state.exit_price} take_profit_at: {state.take_profit_price}",
        )


def process_closed_candle_for_current_position(message_datetime):
    analyze_result = analysis.analyze_coin(
        message_datetime,
        state.ticker,
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
        state.ticker,
        config.signal_type,
        f"closed: {close_price}",
        f"fast_signal: {fast_signal[message_datetime]}",
        f"slow_signal: {slow_signal[message_datetime]}",
    )
    # Exit with CDC then create new opposite order
    if new_position != None and state.current_position != new_position:
        telegram.send_telegram_and_print(
            message_datetime, f"Exit with CDC at {latest_price}"
        )
        state.total_revenue = helper.calculate_state.total_revenue(
            state.current_position,
            state.total_revenue,
            state.current_quantity,
            state.current_price,
            latest_price,
        )
        telegram.send_telegram_and_print(
            message_datetime, f"TotalRevenue: {state.total_revenue}"
        )
        binance.order(
            state.ticker,
            new_position,
            latest_price,
            state.total_revenue,
            reduce_only="true",
        )
        if (
            in_trend
            and not analysis.too_risk(
                state.ticker,
                latest_price,
                analyze_result["exit_price"],
                config.leverage,
                config.max_risk,
                config.risk_mode,
            )
            and analyze_result["rsi_result"] == True
        ):
            binance.order(
                state.ticker,
                new_position,
                latest_price,
                state.total_revenue,
                reduce_only="false",
                new_exit_price=analyze_result["exit_price"],
            )
            state.exit_price = analyze_result["exit_price"]
            state.take_profit_price = analyze_result["take_profit_price"]
            telegram.send_telegram_and_print(
                message_datetime,
                f"{state.current_position}!!!! signal_type: {config.signal_type} fast_signal: {fast_signal[message_datetime]} slow_signal: {slow_signal[message_datetime]} state.current_price: {state.current_price} exit_at: {state.exit_price} take_profit_at: {state.take_profit_price}",
            )
    # re calculate exit price if it is higher for long
    elif state.current_position == "long":
        new_exit_price = low_price - atr[message_datetime]
        if new_exit_price > state.exit_price:
            telegram.send_telegram_and_print(
                message_datetime,
                f"ATR trailing new exit price: {new_exit_price}",
            )
            state.exit_price = new_exit_price
    # re calculate exit price if it is lower for short
    elif state.current_position == "short":
        new_exit_price = high_price + atr[message_datetime]
        if new_exit_price < state.exit_price:
            telegram.send_telegram_and_print(
                message_datetime,
                f"ATR trailing new exit price: {new_exit_price}",
            )
            state.exit_price = new_exit_price
