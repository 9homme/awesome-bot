# Awesome Bot
***
![To the moon](https://upload.wikimedia.org/wikipedia/commons/3/36/Bitcoin-to-the-moon.store.png)

### This is just simple crypto trading bot for Binance Futures API
***

## Trading Strategy

This bot will trade on both `LONG` and `SHORT` position

with 2 signal options for entering into the trade

1. CDC Action Zone (ema12, ema26)

2. WaveTrend Oscillator

with **Optional** trend checking indicator

1. EMA50 - Only open `LONG` position when price trading above EMA50 and `SHORT` when below.

2. ADX - Only open position if ADX is greater or equal to 20.

3. HeikinAshi - Only open `LONG`|`SHORT` position when HeikinAshi candle is `green`|`red` for specific period.

4. RSI - Only open `LONG` position when RSI is greater or equal to 60 (Configurable) and `SHORT` when less or equal to 40 (Configurable).

You can select trading signal you want in `user.cfg`
with `signal_type` = `wavetrend` or `cdc`

After bot enter the trade, it will calculate **Exit price** (ATR Trailing Stop price), **Take profit** price, 
**Position Quantity**
based on

1. ATR value

2. Risk percentage

3. Risk/Reward Ratio

There are 3 situations that bot will close the position

1. When signal cross in opposite direction

2. When price trading below or above `ATR Trailing Stop price`

3. When price reach `Take profit price`

## Get started

1. Install dependencies
```
pip install -r requirements.txt
```
2. Create configuration file by copy `sample.user.cfg` into `user.cfg`
```
api_key - Binance API Key
api_secret - Binance API secret
telegram_token - Telegram token id (How to create a bot in telegram https://www.geeksforgeeks.org/create-a-telegram-bot-using-python/)
chat_id - Telegram chat id (How to find telegram chat id https://sean-bradley.medium.com/get-telegram-chat-id-80b575520659)
ticker - i.e. BTCUSDT initial ticker for trading
total_revenue - Total initial revenue
interval - i.e. 1h 4h 15m 1d 
atr_multiplier - ATR multiplier for ATR Trailing Stop price calculation
risk_reward_ratio - Risk to reward ration to calculate Take profit price
begin_load_data_from - i.e. 10 day ago UTC (This should be around 30 candles from current time based on your interval)
leverage - Leverage that you want to use to open position
offset_top_coin_scouting - offset value to get coin from Binance
max_top_coin_scouting - Limit value to get coin from Binance
auto_scouting - true|false (if true, bot will use all_coins_list or get all coins from Binance. If false, bot will use only ticker)
trend_check - Want to do trend checking before open position or not
trend_mode - adx , ema or both
max_risk - i.e. 0.03 = 3% risk per trade
risk_mode - skip (will skip the trade ) or manage (will open position with lower quantity)
heikin_check - Want to use HeikinAshi for trend checking or not
heikin_look_back - Number of candle period to look back
rsi_check - Want to use RSI for trend checking or not
rsi_buy - LONG when RSI >= this value
rsi_sell - SHORT when RSI <= this value
all_coins_list - List of all coins you want to trade (If empty, bot will get all coins from Binance)
signal_type - wavetrend or cdc
```

3. Run a bot
```
python main.py [Optional config name. if not specified, bot will use default config]
```
