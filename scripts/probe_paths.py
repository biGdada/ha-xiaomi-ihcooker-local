#!/usr/bin/env python3
"""Read-only discovery of local MIoT property paths on the cooker.

This complements ``probe.py`` by scanning every piid in the documented
services, not just the properties in ``const.py``. It only issues
``get_properties`` requests: it never writes a property and never calls an
action, so it cannot start, pause or reset a cooking session.

Usage:
    python3 scripts/probe_paths.py --host 192.168.1.123 --token <32 hex chars>
"""

from __future__ import annotations

import argparse
import importlib.util
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

KNOWN = {(item["siid"], item["piid"]): key for key, item in const.PROPERTIES.items()}


def scan(device: MiotDevice, siid: int, first: int, last: int, chunk_size: int) -> list[tuple[int, int, object]]:
    """Return readable (siid, piid, value) tuples for one service."""
    found = []
    for start in range(first, last + 1, chunk_size):
        properties = [
            {"did": f"scan_{siid}_{piid}", "siid": siid, "piid": piid}
            for piid in range(start, min(start + chunk_size, last + 1))
        ]
        try:
            results = device.get_properties(
                properties, property_getter="get_properties", max_properties=chunk_size
            )
        except Exception as exc:  # noqa: BLE001 - miio exception hierarchy varies
            print(f"  request {siid}/{start} failed: {exc}", file=sys.stderr)
            continue
        for result in results:
            if not isinstance(result, dict) or result.get("code") not in const.SUCCESS_CODES:
                continue
            found.append((siid, int(result["piid"]), result.get("value")))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="Cooker IP address")
    parser.add_argument("--token", required=True, help="32 character miIO token")
    parser.add_argument("--timeout", type=int, default=5, help="UDP timeout in seconds")
    parser.add_argument("--chunk-size", type=int, default=10, help="Properties per request")
    args = parser.parse_args()

    device = MiotDevice(
        ip=args.host,
        token=args.token,
        timeout=args.timeout,
        model=const.MODEL,
        mapping={},
    )
    info = device.info()
    print(f"model: {info.model}, firmware: {info.firmware_version}")
    print("Scanning services 2 (piid 1-20) and 3 (piid 1-40). No writes or actions.\n")

    for siid, first, last in ((2, 1, 20), (3, 1, 40)):
        print(f"Service {siid}:")
        for found_siid, piid, value in scan(device, siid, first, last, args.chunk_size):
            name = KNOWN.get((found_siid, piid), "<undocumented>")
            print(f"  {found_siid}/{piid:<2} {name:<20} {value!r}")
        print()

    print("No start/write path was probed: those require an explicit, approved test.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
