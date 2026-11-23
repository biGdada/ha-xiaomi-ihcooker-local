#!/usr/bin/env python3
"""Read-only probe for a Chunmi IH Cooker Slim on the local network.

Usage:
    python3 scripts/probe.py --host 192.168.1.123 --token <32 hex chars>

Requires python-miio: pip install python-miio==0.5.12

This script only calls miIO.info and get_properties. It never writes a
property or calls an action, and it never prints the token.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys

try:
    from miio import MiotDevice
except ImportError:  # pragma: no cover
    sys.exit("python-miio is required: pip install python-miio==0.5.12")

ROOT = Path(__file__).resolve().parents[1]
CONST_PATH = ROOT / "custom_components" / "chunmi_ihcooker_slim" / "const.py"

spec = importlib.util.spec_from_file_location("chunmi_const", CONST_PATH)
if spec is None or spec.loader is None:
    sys.exit(f"Could not load {CONST_PATH}")
const = importlib.util.module_from_spec(spec)
spec.loader.exec_module(const)

GBK_PROPERTIES = {const.PROP_MENU}


def decode_gbk_hex(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        raw = bytes.fromhex(value)
    except ValueError:
        return None
    return raw.decode("gbk", errors="replace").strip("\x00")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="Cooker IP address")
    parser.add_argument("--token", required=True, help="32 character miIO token")
    parser.add_argument("--timeout", type=int, default=5, help="UDP timeout in seconds")
    parser.add_argument(
        "--max-properties", type=int, default=10, help="Properties per request"
    )
    args = parser.parse_args()

    device = MiotDevice(
        ip=args.host,
        token=args.token,
        timeout=args.timeout,
        model=const.MODEL,
        mapping=const.PROPERTIES,
    )

    info = device.info()
    print("=== miIO.info ===")
    print(f"model:           {info.model}")
    print(f"mac:             {getattr(info, 'mac_address', getattr(info, 'mac', None))}")
    print(f"firmware:        {info.firmware_version}")
    if info.model and info.model != const.MODEL:
        print(f"WARNING: expected model {const.MODEL}, got {info.model}")

    print("\n=== properties (did, siid, piid, code, value) ===")
    try:
        results = device.get_properties_for_mapping(
            max_properties=args.max_properties
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR reading properties: {exc}")
        return 1

    for result in results:
        if not isinstance(result, dict):
            print(f"  unexpected result: {result!r}")
            continue
        key = result.get("did")
        prop = const.PROPERTIES.get(key, {})
        line = (
            f"  {key:<20} {prop.get('siid')}-{prop.get('piid')} "
            f"code={result.get('code')} value={result.get('value')!r}"
        )
        print(line)
        if key in GBK_PROPERTIES:
            decoded = decode_gbk_hex(result.get("value"))
            if decoded is not None:
                print(f"    -> decoded: {decoded!r}")

    print("\n=== raw JSON ===")
    print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
