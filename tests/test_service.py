import math
import os
import sys

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from service import IndicatorRequest, analyze, preview  # noqa: E402


def uptrend(n=60):
    return [100 * 1.01**i for i in range(n)]


def test_analyze_defaults_return_all_indicators():
    out = analyze(IndicatorRequest(prices=uptrend()))
    assert set(out["latest"]) == {"sma", "ema", "rsi", "macd", "bollinger"}
    assert out["summary"]["price_vs_sma"] == "above"
    assert out["summary"]["rsi_state"] == "overbought"
    assert out["summary"]["macd_momentum"] == "bullish"
    assert "series" not in out
    assert "warnings" not in out
    assert out["disclaimer"]


def test_analyze_full_series_lengths():
    prices = uptrend(40)
    out = analyze(IndicatorRequest(prices=prices, indicators=["rsi", "macd"], full_series=True))
    assert len(out["series"]["rsi"]) == 40
    assert len(out["series"]["macd"]["histogram"]) == 40
    assert set(out["latest"]) == {"rsi", "macd"}


def test_analyze_warns_when_too_short():
    out = analyze(IndicatorRequest(prices=[1, 2, 3, 4, 5]))
    assert out["latest"]["rsi"] is None
    assert any("rsi" in w for w in out["warnings"])


def test_downtrend_oversold_and_below_lower_band():
    prices = [100.0] * 30 + [100 * 0.97**i for i in range(1, 15)]
    out = analyze(IndicatorRequest(prices=prices))
    assert out["summary"]["rsi_state"] == "oversold"
    assert out["summary"]["price_vs_sma"] == "below"
    assert out["summary"]["macd_momentum"] == "bearish"


def test_macd_bullish_cross_detected():
    # 先跌後急漲，讓 MACD 柱狀體在最後一根翻正
    prices = [100 - i * 0.5 for i in range(40)]
    found = False
    for i in range(1, 30):
        p = prices + [prices[-1] + j * 1.5 for j in range(1, i + 1)]
        s = analyze(IndicatorRequest(prices=p, indicators=["macd"]))["summary"]
        if s.get("macd_cross") == "bullish_cross":
            found = True
            break
    assert found


def test_macd_crosses_on_sine_wave():
    # 正弦波會反覆產生黃金交叉和死亡交叉
    wave = [100 + 5 * math.sin(i / 6) for i in range(200)]
    crosses = set()
    for n in range(40, 200):
        s = analyze(IndicatorRequest(prices=wave[:n], indicators=["macd"]))["summary"]
        if "macd_cross" in s:
            crosses.add(s["macd_cross"])
    assert crosses == {"bullish_cross", "bearish_cross"}


def test_duplicate_indicators_deduped():
    req = IndicatorRequest(prices=uptrend(), indicators=["rsi", "rsi", "sma"])
    assert req.indicators == ["rsi", "sma"]


@pytest.mark.parametrize(
    "body",
    [
        {"prices": [1]},  # 太短
        {"prices": [1, -2, 3]},  # 負價
        {"prices": [1, 0, 3]},  # 零
        {"prices": [1, float("nan"), 3]},
        {"prices": [1, 2, 3], "indicators": ["kdj"]},  # 不支援的指標
        {"prices": [1, 2, 3], "indicators": []},
        {"prices": [1, 2, 3], "params": {"macd_fast": 30, "macd_slow": 26}},
        {"prices": [1, 2, 3], "params": {"rsi_oversold": 80}},
        {"prices": [1, 2, 3], "unknown": 1},  # 多餘欄位
        {"prices": [1.0] * 5001},  # 超過上限
    ],
)
def test_validation_errors(body):
    with pytest.raises(ValidationError):
        IndicatorRequest(**body)


def test_preview_only_rsi_and_limit():
    out = preview(IndicatorRequest(prices=uptrend(30)))
    assert set(out["latest"]) == {"rsi"}
    with pytest.raises(ValueError):
        preview(IndicatorRequest(prices=uptrend(101)))


def test_output_is_json_serialisable():
    import json

    out = analyze(IndicatorRequest(prices=[100 + math.sin(i) for i in range(50)], full_series=True))
    json.dumps(out, allow_nan=False)
