import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import indicators as ind  # noqa: E402

# StockCharts 的經典 RSI(14) 範例資料
WILDER_CLOSES = [
    44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08,
    45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64,
    46.21, 46.25, 45.71, 46.45, 45.78, 45.35, 44.03, 44.18, 44.22, 44.57,
    43.42, 42.66, 43.13,
]


def test_sma_basic():
    assert ind.sma([1, 2, 3, 4, 5], 3) == [None, None, 2.0, 3.0, 4.0]


def test_sma_period_one_is_identity():
    assert ind.sma([3, 1, 4], 1) == [3.0, 1.0, 4.0]


def test_ema_constant_series():
    out = ind.ema([5.0] * 10, 4)
    assert out[:3] == [None, None, None]
    assert all(v == pytest.approx(5.0) for v in out[3:])


def test_ema_known_values():
    # period 3 → alpha 0.5，起始值是前三筆平均 2
    out = ind.ema([1, 2, 3, 4, 5], 3)
    assert out == [None, None, 2.0, 3.0, 4.0]


def test_ema_with_leading_none():
    out = ind.ema([None, None, 1, 2, 3, 4], 3)
    assert out == [None, None, None, None, 2.0, 3.0]


def test_ema_rejects_gap():
    with pytest.raises(ValueError):
        ind.ema([1, None, 3], 2)


def test_rsi_matches_stockcharts_reference():
    out = ind.rsi(WILDER_CLOSES, 14)
    assert out[13] is None
    expected = [70.46, 66.25, 66.48, 69.35, 66.29, 57.92, 62.88, 63.21]
    assert out[14:22] == pytest.approx(expected, abs=0.01)


def test_rsi_all_up_is_100_flat_is_50():
    assert ind.rsi(list(range(1, 20)), 14)[-1] == 100.0
    assert ind.rsi([10.0] * 20, 14)[-1] == 50.0


def test_rsi_bounds():
    prices = [100 + 10 * math.sin(i / 2) for i in range(200)]
    vals = [v for v in ind.rsi(prices, 14) if v is not None]
    assert vals and all(0 <= v <= 100 for v in vals)


def test_rsi_not_enough_data():
    assert ind.rsi([1, 2, 3], 14) == [None, None, None]


def test_macd_alignment_and_identity():
    prices = [100 + i * 0.5 + math.sin(i) for i in range(80)]
    m = ind.macd(prices)
    assert len(m["macd"]) == len(prices)
    assert m["macd"][24] is None and m["macd"][25] is not None
    # 訊號線從第 26 + 9 - 1 = 34 筆開始有值
    assert m["signal"][32] is None and m["signal"][33] is not None
    for line, sig, hist in zip(m["macd"], m["signal"], m["histogram"]):
        if hist is not None:
            assert hist == pytest.approx(line - sig)


def test_macd_uptrend_positive():
    prices = [100 * 1.01**i for i in range(60)]
    assert ind.macd(prices)["macd"][-1] > 0


def test_macd_fast_must_be_smaller():
    with pytest.raises(ValueError):
        ind.macd([1.0] * 50, fast=26, slow=12)


def test_bollinger_constant_series():
    b = ind.bollinger([10.0] * 25, 20, 2)
    assert b["upper"][-1] == b["lower"][-1] == b["middle"][-1] == 10.0
    assert b["percent_b"][-1] == 0.5
    assert b["bandwidth"][-1] == 0.0


def test_bollinger_known_values():
    prices = [2, 4, 4, 4, 5, 5, 7, 9]  # 母體標準差 = 2，平均 = 5
    b = ind.bollinger(prices, 8, 2)
    assert b["middle"][-1] == pytest.approx(5)
    assert b["upper"][-1] == pytest.approx(9)
    assert b["lower"][-1] == pytest.approx(1)
    assert b["percent_b"][-1] == pytest.approx(1.0)  # 9 剛好碰到上軌


def test_bad_period():
    with pytest.raises(ValueError):
        ind.sma([1, 2], 0)
