"""Position sizing and stop-loss/take-profit calculation.

Pure math with no MT5 dependency, so it's unit testable in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class OrderLevels:
    sl_price: float
    tp_price: float
    sl_distance: float


def calculate_sl_tp(
    entry_price: float,
    atr: float,
    direction: Literal["BUY", "SELL"],
    sl_atr_mult: float,
    tp_atr_mult: float,
    digits: int,
) -> OrderLevels:
    if atr <= 0:
        raise ValueError("ATR must be positive")

    sl_distance = atr * sl_atr_mult
    tp_distance = atr * tp_atr_mult

    if direction == "BUY":
        sl_price = entry_price - sl_distance
        tp_price = entry_price + tp_distance
    else:
        sl_price = entry_price + sl_distance
        tp_price = entry_price - tp_distance

    return OrderLevels(
        sl_price=round(sl_price, digits),
        tp_price=round(tp_price, digits),
        sl_distance=sl_distance,
    )


def calculate_lot_size(
    balance: float,
    risk_percent: float,
    sl_distance: float,
    tick_size: float,
    tick_value: float,
    volume_min: float,
    volume_max: float,
    volume_step: float,
) -> float:
    """Risk-based position sizing.

    risk_amount (account currency) = balance * risk_percent / 100
    loss_per_lot = (sl_distance / tick_size) * tick_value
    lot = risk_amount / loss_per_lot, rounded down to the broker's volume
    step and clamped to [volume_min, volume_max].
    """
    if sl_distance <= 0 or tick_size <= 0 or tick_value <= 0:
        raise ValueError("sl_distance, tick_size and tick_value must be positive")
    if volume_step <= 0:
        raise ValueError("volume_step must be positive")

    risk_amount = balance * risk_percent / 100
    loss_per_lot = (sl_distance / tick_size) * tick_value

    raw_lot = risk_amount / loss_per_lot
    steps = max(1, int(raw_lot / volume_step))
    lot = steps * volume_step
    lot = max(volume_min, min(volume_max, lot))
    return round(lot, 2)
