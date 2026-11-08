import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discovery  # noqa: E402
from service import ALL_INDICATORS, IndicatorRequest  # noqa: E402


def test_example_input_is_valid_request():
    req = IndicatorRequest(**discovery.EXAMPLE_INPUT)
    assert len(req.prices) == len(discovery.EXAMPLE_INPUT["prices"])


def test_example_output_matches_api_shape():
    out = discovery.EXAMPLE_OUTPUT
    assert set(out["latest"]) == set(discovery.EXAMPLE_INPUT["indicators"])
    assert "summary" in out and "disclaimer" in out
    json.dumps(out, allow_nan=False)


def test_schema_matches_service():
    props = discovery.INPUT_SCHEMA["properties"]
    assert props["indicators"]["items"]["enum"] == list(ALL_INDICATORS)
    assert discovery.INPUT_SCHEMA["required"] == ["prices"]
    assert set(props) == set(IndicatorRequest.model_fields)


def test_description_within_bazaar_limit():
    assert 0 < len(discovery.DESCRIPTION) <= 500


def test_bazaar_extension_builds():
    bazaar = pytest.importorskip("x402.extensions.bazaar")
    ext = bazaar.declare_discovery_extension(
        input=discovery.EXAMPLE_INPUT,
        input_schema=discovery.INPUT_SCHEMA,
        body_type="json",
        output=bazaar.OutputConfig(example=discovery.EXAMPLE_OUTPUT),
    )
    assert "bazaar" in ext
    json.dumps(ext, default=str)


def test_cdp_facilitator_config_uses_v2():
    cdp_x402 = pytest.importorskip("cdp.x402")
    cfg = cdp_x402.create_facilitator_config("test-key-id", "test-key-secret")
    assert cfg["url"].endswith("/platform/v2/x402")
    assert callable(cfg["create_headers"])
