import pandas as pd


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
