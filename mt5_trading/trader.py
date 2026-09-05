"""Trading loop: fetch data -> compute signal -> manage position -> order.

Requires a running MetaTrader 5 terminal (Windows, or Wine) logged into
the target account - see README for setup. Defaults to dry-run: set
MT5_ENABLE_LIVE_TRADING=true only after validating the strategy on a demo
account.
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timezone
from typing import Optional

from . import config, risk, strategy
from .mt5_client import MT5Client

log = logging.getLogger(__name__)

# MT5's POSITION_TYPE_BUY constant is stable across brokers/terminals.
_POSITION_TYPE_BUY = 0


class TradingBot:
    def __init__(self, client: Optional[MT5Client] = None) -> None:
        self.client = client or MT5Client()
        self._session_start_equity: Optional[float] = None
        self._halted_for_today = False
        self._halt_date: Optional[date] = None

    def _daily_loss_breached(self) -> bool:
        account = self.client.get_account_info()
        today = datetime.now(timezone.utc).date()
        if self._halt_date != today:
            self._halt_date = today
            self._halted_for_today = False
            self._session_start_equity = account.equity

        if self._halted_for_today:
            return True

        loss_percent = (self._session_start_equity - account.equity) / self._session_start_equity * 100
        if loss_percent >= config.MAX_DAILY_LOSS_PERCENT:
            log.warning(
                "Daily loss limit hit (%.2f%% >= %.2f%%) - halting new entries until tomorrow",
                loss_percent,
                config.MAX_DAILY_LOSS_PERCENT,
            )
            self._halted_for_today = True
            return True
        return False

    def run_once(self) -> None:
        symbol_info = self.client.get_symbol_info(config.SYMBOL)
        if symbol_info.spread_points > config.MAX_SPREAD_POINTS:
            log.info(
                "Spread too wide (%d > %d points) - skipping this cycle",
                symbol_info.spread_points,
                config.MAX_SPREAD_POINTS,
            )
            return

        if self._daily_loss_breached():
            return

        df = self.client.get_rates(config.SYMBOL, config.TIMEFRAME, config.BARS)
        result = strategy.generate_signal(
            df,
            fast_period=config.FAST_EMA,
            slow_period=config.SLOW_EMA,
            rsi_period=config.RSI_PERIOD,
            atr_period=config.ATR_PERIOD,
            rsi_long_max=config.RSI_LONG_MAX,
            rsi_short_min=config.RSI_SHORT_MIN,
        )
        log.info(
            "Signal=%s (%s) fastEMA=%.3f slowEMA=%.3f RSI=%.1f ATR=%.4f",
            result.signal, result.reason, result.fast_ema, result.slow_ema, result.rsi, result.atr,
        )

        if result.signal is None:
            return

        positions = self.client.get_open_positions(config.SYMBOL, config.MAGIC)
        open_direction = None
        if positions:
            open_direction = "BUY" if positions[0].type == _POSITION_TYPE_BUY else "SELL"

        if open_direction == result.signal:
            log.info("Already in a %s position - no action", open_direction)
            return

        if open_direction is not None:
            log.info("Reversing: closing existing %s position", open_direction)
            if config.ENABLE_LIVE_TRADING:
                self.client.close_position(positions[0])
            else:
                log.info("[DRY RUN] would close position %s", positions[0].ticket)

        entry_price = float(df["close"].iloc[-1])
        levels = risk.calculate_sl_tp(
            entry_price=entry_price,
            atr=result.atr,
            direction=result.signal,
            sl_atr_mult=config.SL_ATR_MULT,
            tp_atr_mult=config.TP_ATR_MULT,
            digits=symbol_info.digits,
        )

        if config.LOT_MODE == "fixed":
            lot = config.FIXED_LOT
        else:
            account = self.client.get_account_info()
            lot = risk.calculate_lot_size(
                balance=account.balance,
                risk_percent=config.RISK_PERCENT,
                sl_distance=levels.sl_distance,
                tick_size=symbol_info.trade_tick_size,
                tick_value=symbol_info.trade_tick_value,
                volume_min=symbol_info.volume_min,
                volume_max=symbol_info.volume_max,
                volume_step=symbol_info.volume_step,
            )

        log.info(
            "%s %s lot=%.2f entry~%.3f sl=%.3f tp=%.3f",
            result.signal, config.SYMBOL, lot, entry_price, levels.sl_price, levels.tp_price,
        )

        if not config.ENABLE_LIVE_TRADING:
            log.info("[DRY RUN] MT5_ENABLE_LIVE_TRADING=false - order not sent")
            return

        self.client.send_market_order(
            symbol=config.SYMBOL,
            direction=result.signal,
            lot=lot,
            sl_price=levels.sl_price,
            tp_price=levels.tp_price,
            magic=config.MAGIC,
            comment="ema-cross-bot",
        )

    def run_forever(self, poll_seconds: Optional[int] = None) -> None:
        poll_seconds = poll_seconds or config.POLL_SECONDS
        with self.client:
            log.info(
                "Starting %s bot on %s - live_trading=%s",
                config.SYMBOL, config.TIMEFRAME, config.ENABLE_LIVE_TRADING,
            )
            while True:
                try:
                    self.run_once()
                except Exception:
                    log.exception("Error in trading cycle")
                time.sleep(poll_seconds)
