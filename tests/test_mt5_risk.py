import pytest

from mt5_trading import risk


def test_calculate_sl_tp_buy():
    levels = risk.calculate_sl_tp(
        entry_price=150.123,
        atr=0.200,
        direction="BUY",
        sl_atr_mult=1.5,
        tp_atr_mult=3.0,
        digits=3,
    )
    assert levels.sl_price == pytest.approx(149.823)
    assert levels.tp_price == pytest.approx(150.723)
    assert levels.sl_distance == pytest.approx(0.3)


def test_calculate_sl_tp_sell():
    levels = risk.calculate_sl_tp(
        entry_price=150.123,
        atr=0.200,
        direction="SELL",
        sl_atr_mult=1.5,
        tp_atr_mult=3.0,
        digits=3,
    )
    assert levels.sl_price == pytest.approx(150.423)
    assert levels.tp_price == pytest.approx(149.523)


def test_calculate_sl_tp_rejects_nonpositive_atr():
    with pytest.raises(ValueError):
        risk.calculate_sl_tp(150.0, 0.0, "BUY", 1.5, 3.0, 3)


def test_calculate_lot_size_basic():
    lot = risk.calculate_lot_size(
        balance=100_000,
        risk_percent=1.0,
        sl_distance=0.30,
        tick_size=0.01,
        tick_value=0.91,
        volume_min=0.01,
        volume_max=50.0,
        volume_step=0.01,
    )
    # risk_amount = 1000; loss_per_lot = (0.30/0.01)*0.91 = 27.3
    # raw_lot = 1000 / 27.3 = 36.63...
    assert lot == pytest.approx(36.63)


def test_calculate_lot_size_clamped_to_volume_max():
    lot = risk.calculate_lot_size(
        balance=10_000_000,
        risk_percent=5.0,
        sl_distance=0.10,
        tick_size=0.01,
        tick_value=0.91,
        volume_min=0.01,
        volume_max=50.0,
        volume_step=0.01,
    )
    assert lot == 50.0


def test_calculate_lot_size_clamped_to_volume_min():
    lot = risk.calculate_lot_size(
        balance=100,
        risk_percent=0.1,
        sl_distance=1.0,
        tick_size=0.01,
        tick_value=0.91,
        volume_min=0.01,
        volume_max=50.0,
        volume_step=0.01,
    )
    assert lot == 0.01
