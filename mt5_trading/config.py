"""Environment-driven configuration for the USD/JPY MT5 trading bot.

Nothing here talks to MT5 directly, so this module (and anything that
only depends on it) can be imported and tested on any platform.
"""

from __future__ import annotations

import os


def _bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    val = os.environ.get(name)
    return int(val) if val else default


def _float(name: str, default: float) -> float:
    val = os.environ.get(name)
    return float(val) if val else default


# --- MT5 terminal connection ---
MT5_LOGIN = _int("MT5_LOGIN", 0) or None
MT5_PASSWORD = os.environ.get("MT5_PASSWORD")
MT5_SERVER = os.environ.get("MT5_SERVER")
MT5_PATH = os.environ.get("MT5_PATH") or None

# --- Instrument / timeframe ---
SYMBOL = os.environ.get("MT5_SYMBOL", "USDJPY")
TIMEFRAME = os.environ.get("MT5_TIMEFRAME", "M15")
BARS = _int("MT5_BARS", 300)
MAGIC = _int("MT5_MAGIC", 20260905)

# --- Strategy parameters (EMA crossover confirmed by RSI) ---
FAST_EMA = _int("MT5_FAST_EMA", 20)
SLOW_EMA = _int("MT5_SLOW_EMA", 50)
RSI_PERIOD = _int("MT5_RSI_PERIOD", 14)
RSI_LONG_MAX = _float("MT5_RSI_LONG_MAX", 70.0)
RSI_SHORT_MIN = _float("MT5_RSI_SHORT_MIN", 30.0)
ATR_PERIOD = _int("MT5_ATR_PERIOD", 14)
SL_ATR_MULT = _float("MT5_SL_ATR_MULT", 1.5)
TP_ATR_MULT = _float("MT5_TP_ATR_MULT", 3.0)

# --- Risk management ---
LOT_MODE = os.environ.get("MT5_LOT_MODE", "risk")  # "risk" or "fixed"
FIXED_LOT = _float("MT5_FIXED_LOT", 0.01)
RISK_PERCENT = _float("MT5_RISK_PERCENT", 1.0)
MAX_SPREAD_POINTS = _int("MT5_MAX_SPREAD_POINTS", 30)
MAX_DAILY_LOSS_PERCENT = _float("MT5_MAX_DAILY_LOSS_PERCENT", 3.0)

# --- Runtime ---
POLL_SECONDS = _int("MT5_POLL_SECONDS", 60)
LOG_FILE = os.environ.get("MT5_LOG_FILE", "mt5_trading.log")

# Safety default: the bot never sends real orders unless this is explicitly
# set to "true". Always validate on a demo account first.
ENABLE_LIVE_TRADING = _bool("MT5_ENABLE_LIVE_TRADING", False)
