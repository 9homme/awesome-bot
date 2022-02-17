import helper


def test_rounding_down_with_number_less_than_five_should_round_down():
    result = helper.round_decimals_down(2.12345)
    assert result == 2.12


def test_rounding_down_with_number_more_than_five_should_round_down():
    result = helper.round_decimals_down(2.126)
    assert result == 2.12


def test_rounding_down_with_decimal_more_than_two():
    result = helper.round_decimals_down(2.12345, 4)
    assert result == 2.1234


def test_rounding_down_with_decimal_less_than_two():
    result = helper.round_decimals_down(2.1, 2)
    assert result == 2.1
