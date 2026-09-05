"""Command-line entry point.

    python -m mt5_trading run              # loop forever (Ctrl+C to stop)
    python -m mt5_trading run --once       # single cycle then exit
    python -m mt5_trading check-config     # print the effective configuration
"""

from __future__ import annotations

import argparse

from . import config
from .logging_setup import setup_logging
from .trader import TradingBot


def cmd_run(args: argparse.Namespace) -> None:
    setup_logging()
    bot = TradingBot()
    if args.once:
        with bot.client:
            bot.run_once()
    else:
        bot.run_forever()


def cmd_check_config(args: argparse.Namespace) -> None:
    print(f"Symbol:            {config.SYMBOL}")
    print(f"Timeframe:         {config.TIMEFRAME}")
    print(f"EMA fast/slow:     {config.FAST_EMA}/{config.SLOW_EMA}")
    print(f"RSI period/bounds: {config.RSI_PERIOD} ({config.RSI_SHORT_MIN}-{config.RSI_LONG_MAX})")
    print(f"ATR period:        {config.ATR_PERIOD}")
    print(f"SL/TP (x ATR):     {config.SL_ATR_MULT} / {config.TP_ATR_MULT}")
    print(f"Lot mode:          {config.LOT_MODE} (fixed={config.FIXED_LOT}, risk%={config.RISK_PERCENT})")
    print(f"Max spread points: {config.MAX_SPREAD_POINTS}")
    print(f"Max daily loss %:  {config.MAX_DAILY_LOSS_PERCENT}")
    print(f"Poll seconds:      {config.POLL_SECONDS}")
    print(f"LIVE TRADING:      {'ENABLED' if config.ENABLE_LIVE_TRADING else 'disabled (dry-run)'}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mt5-trading", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Run the trading loop against a connected MT5 terminal")
    p_run.add_argument("--once", action="store_true", help="Run a single cycle then exit")
    p_run.set_defaults(func=cmd_run)

    sub.add_parser(
        "check-config", help="Print the effective configuration and exit"
    ).set_defaults(func=cmd_check_config)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
