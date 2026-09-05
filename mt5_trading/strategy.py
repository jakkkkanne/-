"""USD/JPY trend-following strategy: EMA crossover confirmed by RSI.

Operates purely on OHLC data (a pandas DataFrame with open/high/low/close
columns, oldest row first, most recent *closed* bar last) so it can be
developed and tested without a live MT5 connection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import pandas as pd

from . import indicators

Signal = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class SignalResult:
    signal: Optional[Signal]
    reason: str
    fast_ema: float
    slow_ema: float
    rsi: float
    atr: float


def generate_signal(
    df: pd.DataFrame,
    fast_period: int = 20,
    slow_period: int = 50,
    rsi_period: int = 14,
    atr_period: int = 14,
    rsi_long_max: float = 70.0,
    rsi_short_min: float = 30.0,
) -> SignalResult:
    """Return a BUY/SELL/None signal from the last two closed bars in df.

    Entry rule: EMA(fast) crossing EMA(slow) between the previous and the
    last closed bar (a *fresh* cross, not an already-established trend),
    filtered by RSI so entries aren't taken deep into overbought/oversold
    territory.
    """
    required = max(fast_period, slow_period, rsi_period, atr_period) + 2
    if len(df) < required:
        raise ValueError(f"Need at least {required} bars, got {len(df)}")

    fast = indicators.ema(df["close"], fast_period)
    slow = indicators.ema(df["close"], slow_period)
    rsi_series = indicators.rsi(df["close"], rsi_period)
    atr_series = indicators.atr(df, atr_period)

    fast_now, fast_prev = fast.iloc[-1], fast.iloc[-2]
    slow_now, slow_prev = slow.iloc[-1], slow.iloc[-2]
    rsi_now = rsi_series.iloc[-1]
    atr_now = atr_series.iloc[-1]

    crossed_up = fast_prev <= slow_prev and fast_now > slow_now
    crossed_down = fast_prev >= slow_prev and fast_now < slow_now

    signal: Optional[Signal] = None
    reason = "no fresh crossover"

    if crossed_up:
        if rsi_now <= rsi_long_max:
            signal = "BUY"
            reason = f"golden cross (EMA{fast_period}>EMA{slow_period}), RSI={rsi_now:.1f}"
        else:
            reason = f"golden cross but RSI={rsi_now:.1f} overbought (>{rsi_long_max})"
    elif crossed_down:
        if rsi_now >= rsi_short_min:
            signal = "SELL"
            reason = f"dead cross (EMA{fast_period}<EMA{slow_period}), RSI={rsi_now:.1f}"
        else:
            reason = f"dead cross but RSI={rsi_now:.1f} oversold (<{rsi_short_min})"

    return SignalResult(
        signal=signal,
        reason=reason,
        fast_ema=float(fast_now),
        slow_ema=float(slow_now),
        rsi=float(rsi_now),
        atr=float(atr_now),
    )
