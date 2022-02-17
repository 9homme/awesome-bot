import configparser
import json
import sys

config_name = sys.argv[1] if len(sys.argv) > 1 else "default"
print(f"Loading config from [{config_name}]")
config = configparser.ConfigParser()
config.read("user.cfg")
user_config = config[config_name]

# binance client
api_key = user_config["api_key"]
api_secret = user_config["api_secret"]

# telegram bot
telegram_token = user_config["telegram_token"]
chat_id = user_config["chat_id"]
chat_id = int(chat_id) if chat_id else None

ticker = user_config["ticker"]
total_revenue = float(user_config["total_revenue"])
interval = user_config["interval"]
atr_multiplier = float(user_config["atr_multiplier"])
risk_reward_ratio = int(user_config["risk_reward_ratio"])
begin_load_data_from = user_config["begin_load_data_from"]
leverage = int(user_config["leverage"])
max_top_coin_scouting = int(user_config["max_top_coin_scouting"])
offset_top_coin_scouting = int(user_config["offset_top_coin_scouting"])
auto_scouting = bool(user_config["auto_scouting"] == "true")
trend_check = bool(user_config["trend_check"] == "true")
trend_mode = user_config["trend_mode"]
max_risk = float(user_config["max_risk"])
risk_mode = user_config["risk_mode"]
heikin_check = bool(user_config["heikin_check"] == "true")
heikin_look_back = int(user_config["heikin_look_back"])
rsi_check = bool(user_config["rsi_check"] == "true")
rsi_buy = int(user_config["rsi_buy"])
rsi_sell = int(user_config["rsi_sell"])
all_coins_list = json.loads(user_config["all_coins_list"])
signal_type = user_config["signal_type"]
