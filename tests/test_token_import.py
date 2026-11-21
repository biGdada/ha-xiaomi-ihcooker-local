"""Tests for importing tokens from other local Xiaomi integrations."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "custom_components" / "chunmi_ihcooker_slim"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


const = _load("chunmi_const_for_import", PACKAGE / "const.py")
token_import = _load("chunmi_token_import", PACKAGE / "token_import.py")

TOKEN = "0123456789abcdef0123456789abcdef"
OTHER_TOKEN = "fedcba9876543210fedcba9876543210"


def _cache_bytes(data: dict) -> bytes:
    payload = json.dumps(data).encode("utf-8")
    return payload + hashlib.sha256(payload).digest()


def test_default_model_matches_integration() -> None:
    assert token_import.MODEL == const.MODEL


def test_parse_cache_verifies_sha256() -> None:
    expected = {"1234567890": {"model": const.MODEL, "token": TOKEN}}
    raw = _cache_bytes(expected)
    assert token_import.parse_xiaomi_home_cache(raw) == expected
    assert token_import.parse_xiaomi_home_cache(raw[:-1] + b"0") == {}
    assert token_import.parse_xiaomi_home_cache(b"short") == {}


def test_candidates_from_cache_filter_and_label() -> None:
    data = {
        "1234567890": {
            "model": const.MODEL,
            "name": "Kitchen cooker",
            "token": TOKEN.upper(),
            "ip": "192.0.2.10",
        },
        "2": {"model": "other.model", "token": OTHER_TOKEN},
        "3": {"model": const.MODEL, "token": "not-a-token"},
    }
    candidates = token_import.candidates_from_cache(data)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.token == TOKEN
    assert candidate.host == "192.0.2.10"
    assert candidate.did == "1234567890"
    assert "Xiaomi Home" in candidate.label


class FakeEntry:
    def __init__(self, data: dict, options: dict | None = None) -> None:
        self.entry_id = "entry-1"
        self.data = data
        self.options = options or {}


def test_candidates_from_entries() -> None:
    entries = [
        FakeEntry({"model": const.MODEL, "token": TOKEN, "host": "192.0.2.11"}),
        FakeEntry({"model": "other.model", "token": OTHER_TOKEN}),
    ]
    candidates = token_import.candidates_from_entries(entries)
    assert len(candidates) == 1
    assert candidates[0].source == "Xiaomi Miot"
    assert candidates[0].token == TOKEN


def test_discover_tokens_sync(tmp_path: Path) -> None:
    cache_dir = tmp_path / ".storage" / "xiaomi_home" / "miot_devices"
    cache_dir.mkdir(parents=True)
    (cache_dir / "1_default.dict").write_bytes(
        _cache_bytes(
            {
                "1234567890": {
                    "model": const.MODEL,
                    "name": "Cooker",
                    "token": TOKEN,
                    "ip": "192.0.2.12",
                }
            }
        )
    )

    class FakeConfig:
        @staticmethod
        def path(*parts: str) -> str:
            return str(tmp_path.joinpath(*parts))

    class FakeConfigEntries:
        @staticmethod
        def async_entries(domain: str) -> list:
            assert domain == "xiaomi_miot"
            return []

    class FakeHass:
        config = FakeConfig()
        config_entries = FakeConfigEntries()

    candidates = token_import.discover_tokens_sync(FakeHass())
    assert [item.token for item in candidates] == [TOKEN]
