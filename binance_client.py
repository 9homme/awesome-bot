import state
import config
from binance import Client
from telegram_client import telegram_helper
import numpy as np
import pandas as pd
import datetime
import uuid

# binance client
client = Client(config.api_key, config.api_secret)

exchange_info = client.futures_exchange_info()


def futures_recent_trades(symbol):
    client.futures_recent_trades(symbol=symbol)


def get_all_coins_list():
    all_coins = [state.initial_ticker]
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
    # try to set leverage and margin type
    if reduce_only == "false":
        try:
            client.futures_change_margin_type(symbol=symbol, marginType="ISOLATED")
        except Exception as e:
            print(f"Cannot set marginType, message: {str(e)}")
        try:
            client.futures_change_leverage(symbol=symbol, leverage=config.leverage)
        except Exception as e:
            print(f"Cannot change leverage, message: {str(e)}")
    total_to_invest = usdt_amount * config.leverage
    if state.current_quantity != None:
        quantity = state.current_quantity
    else:
        full_risk_quantity = total_to_invest / price
        risk = (abs(new_exit_price - price) / price) * config.leverage
        if config.risk_mode == "manage" and risk > config.max_risk:
            quantity = (full_risk_quantity / risk) * config.max_risk
        else:
            quantity = full_risk_quantity
        quantity = telegram_helper.round_decimals_down(
            quantity, get_symbol_decimal(symbol)
        )
        telegram_helper.send_telegram_and_print(
            f"Risk mode: {config.risk_mode}, risk: {risk}, max_risk: {config.max_risk} will order qty: {quantity} [full risk qty: {full_risk_quantity}]"
        )
    telegram_helper.send_telegram_and_print(
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
        telegram_helper.send_telegram_and_print(
            datetime.now(), f"Waiting order: {client_order_id} to be filled"
        )
        try:
            order = client.futures_get_order(
                symbol=symbol, origClientOrderId=client_order_id
            )
            if order["status"] == Client.ORDER_STATUS_FILLED:
                telegram_helper.send_telegram_and_print(
                    datetime.now(),
                    f"Order: {client_order_id}({order['orderId']}) was filled with avg price: {order['avgPrice']} and qty: {order['executedQty']}",
                )
                break
        except Exception as e:
            print(f"Get order error {str(e)}. Retry...")

    if reduce_only == "true":
        state.current_position = None
        state.current_price = None
        state.current_quantity = None
        state.exit_price = None
        state.take_profit_price = None
    else:
        state.current_position = position
        state.current_price = float(order["avgPrice"])
        state.current_quantity = float(order["executedQty"])
    # save state every time we make an order
    state.save_state()
    print(order)
