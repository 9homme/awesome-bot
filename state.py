import config
import dill

# state
current_candle_datetime = None
current_position = None
current_price = None
current_quantity = None
exit_price = None
take_profit_price = None
ticker = None
total_revenue = None
initial_ticker = config.ticker


def get_state_str():
    return f"current state for {ticker} datetime: {current_candle_datetime} position: {current_position} price: {current_price} quantity: {current_quantity} exit_price: {exit_price} take_profit: {take_profit_price} total_revenue: {total_revenue}"


def save_state():
    state = {}
    state["ticker"] = ticker
    state["datetime"] = current_candle_datetime
    state["position"] = current_position
    state["price"] = current_price
    state["quantity"] = current_quantity
    state["exit_price"] = round(exit_price, 5) if exit_price is not None else None
    state["take_profit_price"] = (
        round(take_profit_price, 5) if take_profit_price is not None else None
    )
    state["total_revenue"] = (
        round(total_revenue, 5) if total_revenue is not None else None
    )
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
            ticker = state["ticker"] if state["ticker"] is not None else initial_ticker
            current_candle_datetime = state["datetime"]
            current_position = state["position"]
            current_price = state["price"]
            current_quantity = state["quantity"]
            exit_price = state["exit_price"]
            take_profit_price = state["take_profit_price"]
            if state["total_revenue"] is not None:
                total_revenue = state["total_revenue"]
    except:
        print(f"No state for {ticker}, bot will start from zero")
        ticker = initial_ticker
        total_revenue = config.total_revenue
