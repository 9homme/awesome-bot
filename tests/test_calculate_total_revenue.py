import helper
from constant import POSITION_LONG, POSITION_SHORT


def test_calculate_total_revenue_for_win_long(mocker):
    # patch send_telegram_and_print to ignore telegram message sending during unit test
    mocker.patch("client.telegram_helper.send_telegram_and_print")
    result = helper.calculate_total_revenue(POSITION_LONG, 100, 3, 10, 12)
    assert result == 106


def test_calculate_total_revenue_for_lose_long(mocker):
    mocker.patch("client.telegram_helper.send_telegram_and_print")
    result = helper.calculate_total_revenue(POSITION_LONG, 100, 3, 10, 8)
    assert result == 94


def test_calculate_total_revenue_for_win_short(mocker):
    mocker.patch("client.telegram_helper.send_telegram_and_print")
    result = helper.calculate_total_revenue(POSITION_SHORT, 100, 3, 10, 8)
    assert result == 106


def test_calculate_total_revenue_for_lose_short(mocker):
    mocker.patch("client.telegram_helper.send_telegram_and_print")
    result = helper.calculate_total_revenue(POSITION_SHORT, 100, 3, 10, 12)
    assert result == 94
