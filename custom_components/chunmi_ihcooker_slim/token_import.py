"""Discover miIO tokens from other locally installed Xiaomi integrations.

The official Xiaomi Home integration keeps a device list in
``.storage/xiaomi_home/miot_devices/<uid>_<server>.dict``.  The format is JSON
followed by a 32-byte SHA-256 digest of the JSON bytes.  Each device entry may
contain a ``token``, ``model``, ``name`` and ``localip``.

The ``xiaomi_miot`` custom integration stores ``host``/``token``/``model`` in
its config entries.

This module deliberately has no Home Assistant imports so that the parsing
logic can be unit tested without a HA installation.  All filesystem access is
done by the caller in an executor.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

_LOGGER = logging.getLogger(__name__)

MODEL = "chunmi.ihcooker.slim"
TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")


@dataclass(frozen=True)
class TokenCandidate:
    """A token discovered in another integration's storage."""

    key: str
    source: str
    did: str | None
    model: str | None
    name: str | None
    host: str | None
    token: str

    @property
    def label(self) -> str:
        """Human readable label for the selection list."""
        title = self.name or self.model or "Xiaomi device"
        parts = [title, self.source]
        if self.host:
            parts.append(self.host)
        if self.did:
            parts.append(f"did {self.did}")
        return " — ".join(parts)


def parse_xiaomi_home_cache(raw: bytes) -> dict[str, dict[str, Any]]:
    """Parse a ``*.dict`` device cache file, verifying its checksum."""
    if len(raw) <= 32:
        return {}
    payload, digest = raw[:-32], raw[-32:]
    if hashlib.sha256(payload).digest() != digest:
        _LOGGER.debug("Xiaomi Home cache checksum mismatch; ignoring file")
        return {}
    try:
        data = json.loads(payload)
    except (UnicodeDecodeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(did): info for did, info in data.items() if isinstance(info, dict)}


def candidates_from_cache(
    data: dict[str, dict[str, Any]], *, model: str = MODEL
) -> list[TokenCandidate]:
    """Extract cooker token candidates from a Xiaomi Home device cache."""
    candidates: list[TokenCandidate] = []
    for did, info in data.items():
        token = str(info.get("token") or "").strip().lower()
        if not TOKEN_RE.fullmatch(token):
            continue
        found_model = info.get("model")
        if found_model and found_model != model:
            continue
        host = info.get("localip") or info.get("ip") or None
        candidates.append(
            TokenCandidate(
                key=f"xiaomi_home:{did}",
                source="Xiaomi Home",
                did=did,
                model=found_model,
                name=info.get("name"),
                host=str(host) if host else None,
                token=token,
            )
        )
    return candidates


def candidates_from_entries(
    entries: Iterable[Any], *, model: str = MODEL
) -> list[TokenCandidate]:
    """Extract cooker token candidates from hass-xiaomi-miot config entries."""
    candidates: list[TokenCandidate] = []
    for entry in entries:
        data = {**getattr(entry, "data", {}), **getattr(entry, "options", {})}
        token = str(data.get("token") or "").strip().lower()
        if not TOKEN_RE.fullmatch(token):
            continue
        found_model = data.get("model")
        if found_model and found_model != model:
            continue
        host = data.get("host")
        candidates.append(
            TokenCandidate(
                key=f"xiaomi_miot:{getattr(entry, 'entry_id', token[:8])}",
                source="Xiaomi Miot",
                did=str(data.get("miot_did")) if data.get("miot_did") else None,
                model=found_model,
                name=data.get("name"),
                host=str(host) if host else None,
                token=token,
            )
        )
    return candidates


def discover_tokens_sync(hass: Any) -> list[TokenCandidate]:
    """Scan known local storages for tokens (blocking; call in an executor)."""
    candidates: list[TokenCandidate] = []

    cache_dir = Path(hass.config.path(".storage", "xiaomi_home", "miot_devices"))
    if cache_dir.is_dir():
        for path in sorted(cache_dir.glob("*.dict")):
            try:
                data = parse_xiaomi_home_cache(path.read_bytes())
            except OSError as exc:
                _LOGGER.debug("Cannot read %s: %s", path, exc)
                continue
            candidates.extend(candidates_from_cache(data))

    try:
        entries = hass.config_entries.async_entries("xiaomi_miot")
    except Exception:  # noqa: BLE001 - integration may not be loaded
        entries = []
    candidates.extend(candidates_from_entries(entries))

    # Deduplicate by token, preferring entries that also carry a host.
    unique: dict[str, TokenCandidate] = {}
    for candidate in candidates:
        current = unique.get(candidate.token)
        if current is None or (current.host is None and candidate.host):
            unique[candidate.token] = candidate
    return sorted(unique.values(), key=lambda item: item.label)
