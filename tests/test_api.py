"""用 FastAPI TestClient 測試路由（關閉收費，不需要錢包或網路）。"""

import os
import sys

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

os.environ["PAYMENTS_ENABLED"] = "false"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def test_info_and_health():
    assert client.get("/health").json() == {"status": "ok"}
    info = client.get("/").json()
    assert info["payments"]["protocol"] == "x402"
    assert "POST /v1/indicators" in info["endpoints"]


def test_preview_free():
    r = client.post("/v1/preview", json={"prices": [100 + i for i in range(20)]})
    assert r.status_code == 200
    assert set(r.json()["latest"]) == {"rsi"}


def test_preview_too_many_prices():
    r = client.post("/v1/preview", json={"prices": [100.0] * 101})
    assert r.status_code == 422


def test_indicators_endpoint():
    r = client.post("/v1/indicators", json={"prices": [100 * 1.01**i for i in range(60)]})
    assert r.status_code == 200
    assert r.json()["summary"]["macd_momentum"] == "bullish"


def test_bad_body_rejected():
    r = client.post("/v1/indicators", json={"prices": [1, -1]})
    assert r.status_code == 422
