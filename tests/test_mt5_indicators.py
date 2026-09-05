import pandas as pd

from mt5_trading import indicators


def test_ema_converges_to_constant_price():
    series = pd.Series([100.0] * 30)
    result = indicators.ema(series, period=10)
    assert result.iloc[-1] == 100.0


def test_ema_reacts_faster_with_shorter_period():
    series = pd.Series([100.0] * 20 + [110.0] * 5)
    fast = indicators.ema(series, period=3)
    slow = indicators.ema(series, period=15)
    # After a jump, the shorter-period EMA should have moved further
    # toward the new price than the longer-period one.
    assert fast.iloc[-1] > slow.iloc[-1]


def test_rsi_is_bounded_and_high_in_uptrend():
    series = pd.Series([100.0 + i for i in range(30)])
    result = indicators.rsi(series, period=14)
    valid = result.dropna()
    assert ((valid >= 0) & (valid <= 100)).all()
    assert valid.iloc[-1] > 70


def test_rsi_is_low_in_downtrend():
    series = pd.Series([130.0 - i for i in range(30)])
    result = indicators.rsi(series, period=14)
    assert result.dropna().iloc[-1] < 30


def test_atr_is_nonnegative():
    df = pd.DataFrame(
        {
            "high": [101.0, 102.0, 100.5, 103.0, 104.0] * 6,
            "low": [99.0, 100.0, 98.5, 101.0, 102.0] * 6,
            "close": [100.0, 101.0, 99.5, 102.0, 103.0] * 6,
        }
    )
    result = indicators.atr(df, period=10)
    assert (result.dropna() >= 0).all()
