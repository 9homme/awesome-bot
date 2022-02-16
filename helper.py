import math
from telegram_client import telegram_helper
from datetime import datetime


def round_decimals_down(number: float, decimals: int = 2):
    """
    Returns a value rounded down to a specific number of decimal places.
    """
    if not isinstance(decimals, int):
        raise TypeError("decimal places must be an integer")
    elif decimals < 0:
        raise ValueError("decimal places has to be 0 or more")
    elif decimals == 0:
        return math.floor(number)

    factor = 10**decimals
    return math.floor(number * factor) / factor


def calculate_total_revenue(
    position, current_revenue, quantity, entry_price, exit_price
):
    new_revenue = current_revenue
    if position == "long":
        new_revenue = current_revenue + (quantity * (exit_price - entry_price))

    elif position == "short":
        new_revenue = current_revenue + (quantity * (entry_price - exit_price))

    position_result = "Win" if new_revenue > current_revenue else "Lose"
    telegram_helper.send_telegram_and_print(
        datetime.now(),
        f"{position_result}!!!!! {(abs(new_revenue - current_revenue)/current_revenue)*100}%",
    )
    return new_revenue
