import pandas as pd
import pytest

from mt5_trading import strategy

FAST, SLOW, RSI_P, ATR_P = 5, 10, 8, 5
REQUIRED = max(FAST, SLOW, RSI_P, ATR_P) + 2


def _make_df(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c + 0.05 for c in closes],
            "low": [c - 0.05 for c in closes],
            "close": closes,
        }
    )


def _signal_at_any_prefix(df: pd.DataFrame) -> str | None:
    """Run the strategy over growing prefixes and return the first non-None signal."""
    for end in range(REQUIRED, len(df) + 1):
        result = strategy.generate_signal(
            df.iloc[:end],
            fast_period=FAST,
            slow_period=SLOW,
            rsi_period=RSI_P,
            atr_period=ATR_P,
        )
        if result.signal is not None:
            return result.signal
    return None


def test_uptrend_after_downtrend_triggers_buy():
    closes = [110.0 - i * 0.2 for i in range(30)] + [104.0 + i * 0.6 for i in range(1, 31)]
    df = _make_df(closes)
    assert _signal_at_any_prefix(df) == "BUY"


def test_downtrend_after_uptrend_triggers_sell():
    closes = [100.0 + i * 0.2 for i in range(30)] + [106.0 - i * 0.6 for i in range(1, 31)]
    df = _make_df(closes)
    assert _signal_at_any_prefix(df) == "SELL"


def test_flat_price_never_triggers_a_signal():
    closes = [100.0] * 40
    df = _make_df(closes)
    for end in range(REQUIRED, len(df) + 1):
        result = strategy.generate_signal(
            df.iloc[:end], fast_period=FAST, slow_period=SLOW, rsi_period=RSI_P, atr_period=ATR_P
        )
        assert result.signal is None


def test_raises_when_not_enough_bars():
    df = _make_df([100.0] * 3)
    with pytest.raises(ValueError):
        strategy.generate_signal(df, fast_period=FAST, slow_period=SLOW, rsi_period=RSI_P, atr_period=ATR_P)
