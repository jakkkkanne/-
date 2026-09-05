"""Thin wrapper around the MetaTrader5 terminal API.

The `MetaTrader5` Python package only works against a running MetaTrader 5
terminal (Windows, or Wine on Linux/Mac) that is logged into a trading
account. It is imported lazily here so the rest of this package
(indicators/strategy/risk) and the test suite work without it installed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from . import config

log = logging.getLogger(__name__)

TIMEFRAME_ATTRS = {
    "M1": "TIMEFRAME_M1",
    "M5": "TIMEFRAME_M5",
    "M15": "TIMEFRAME_M15",
    "M30": "TIMEFRAME_M30",
    "H1": "TIMEFRAME_H1",
    "H4": "TIMEFRAME_H4",
    "D1": "TIMEFRAME_D1",
}


def _mt5():
    try:
        import MetaTrader5 as mt5
    except ImportError as exc:  # pragma: no cover - only exercised on a Windows/MT5 host
        raise RuntimeError(
            "The MetaTrader5 package is not available. This module only runs "
            "on a machine with the MetaTrader 5 terminal installed (Windows, "
            "or Wine). Install it with `pip install MetaTrader5`."
        ) from exc
    return mt5


@dataclass(frozen=True)
class AccountInfo:
    balance: float
    equity: float
    currency: str


@dataclass(frozen=True)
class SymbolInfo:
    digits: int
    point: float
    trade_tick_size: float
    trade_tick_value: float
    volume_min: float
    volume_max: float
    volume_step: float
    spread_points: int


class MT5Client:
    """Wraps the MetaTrader5 module for a single terminal connection."""

    def __init__(self) -> None:
        self._mt5 = None

    def connect(self) -> None:
        mt5 = _mt5()
        init_kwargs = {}
        if config.MT5_PATH:
            init_kwargs["path"] = config.MT5_PATH
        if not mt5.initialize(**init_kwargs):
            raise RuntimeError(f"MT5 initialize() failed: {mt5.last_error()}")

        if config.MT5_LOGIN:
            authorized = mt5.login(
                login=config.MT5_LOGIN,
                password=config.MT5_PASSWORD,
                server=config.MT5_SERVER,
            )
            if not authorized:
                mt5.shutdown()
                raise RuntimeError(f"MT5 login() failed: {mt5.last_error()}")

        self._mt5 = mt5
        log.info("Connected to MT5 terminal (account=%s)", config.MT5_LOGIN)

    def shutdown(self) -> None:
        if self._mt5 is not None:
            self._mt5.shutdown()
            self._mt5 = None

    def __enter__(self) -> "MT5Client":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.shutdown()

    def _require(self):
        if self._mt5 is None:
            raise RuntimeError("Not connected - call connect() first")
        return self._mt5

    def get_rates(self, symbol: str, timeframe: str, bars: int) -> pd.DataFrame:
        mt5 = self._require()
        tf = getattr(mt5, TIMEFRAME_ATTRS[timeframe])
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, bars)
        if rates is None or len(rates) == 0:
            raise RuntimeError(f"copy_rates_from_pos returned no data: {mt5.last_error()}")
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df

    def get_account_info(self) -> AccountInfo:
        mt5 = self._require()
        info = mt5.account_info()
        if info is None:
            raise RuntimeError(f"account_info() failed: {mt5.last_error()}")
        return AccountInfo(balance=info.balance, equity=info.equity, currency=info.currency)

    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        mt5 = self._require()
        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"symbol_select({symbol}) failed: {mt5.last_error()}")
        info = mt5.symbol_info(symbol)
        if info is None:
            raise RuntimeError(f"symbol_info({symbol}) failed: {mt5.last_error()}")
        return SymbolInfo(
            digits=info.digits,
            point=info.point,
            trade_tick_size=info.trade_tick_size or info.point,
            trade_tick_value=info.trade_tick_value,
            volume_min=info.volume_min,
            volume_max=info.volume_max,
            volume_step=info.volume_step,
            spread_points=info.spread,
        )

    def get_open_positions(self, symbol: str, magic: int) -> list:
        mt5 = self._require()
        positions = mt5.positions_get(symbol=symbol) or ()
        return [p for p in positions if p.magic == magic]

    def send_market_order(
        self,
        symbol: str,
        direction: str,
        lot: float,
        sl_price: float,
        tp_price: float,
        magic: int,
        comment: str,
        deviation: int = 20,
    ):
        mt5 = self._require()
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"symbol_info_tick({symbol}) failed: {mt5.last_error()}")

        price = tick.ask if direction == "BUY" else tick.bid
        order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": order_type,
            "price": price,
            "sl": sl_price,
            "tp": tp_price,
            "deviation": deviation,
            "magic": magic,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(f"order_send failed: {result}")
        return result

    def close_position(self, position, deviation: int = 20):
        mt5 = self._require()
        symbol = position.symbol
        tick = mt5.symbol_info_tick(symbol)
        closing_buy = position.type == mt5.POSITION_TYPE_SELL
        order_type = mt5.ORDER_TYPE_BUY if closing_buy else mt5.ORDER_TYPE_SELL
        price = tick.ask if closing_buy else tick.bid
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": position.volume,
            "type": order_type,
            "position": position.ticket,
            "price": price,
            "deviation": deviation,
            "magic": position.magic,
            "comment": "close by bot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(f"order_send (close) failed: {result}")
        return result
