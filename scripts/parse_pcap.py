#!/usr/bin/env python3
"""Decrypt miIO UDP payloads from a tcpdump capture.

Usage:
    .venv/bin/python scripts/parse_pcap.py <capture.pcap> <token>

Requires: pip install scapy cryptography
"""

from __future__ import annotations

import hashlib
import sys

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from scapy.all import UDP, IP, rdpcap  # type: ignore[import-not-found]


def decrypt(payload: bytes, token: bytes) -> bytes | None:
    """Decrypt a miIO packet body, returning the JSON payload."""
    if len(payload) < 32 or payload[:2] != b"\x21\x31":
        return None
    key = hashlib.md5(token).digest()
    iv = hashlib.md5(key + token).digest()
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    plaintext = decryptor.update(payload[32:]) + decryptor.finalize()
    return plaintext.rstrip(b"\x00\x01\x02\x03\x04\x05\x06\x07\x08")


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    path, token_hex = sys.argv[1], sys.argv[2]
    token = bytes.fromhex(token_hex)

    packets = rdpcap(path)
    print(f"=== {len(packets)} packets ===")
    for i, pkt in enumerate(packets):
        if UDP not in pkt or IP not in pkt:
            continue
        payload = bytes(pkt[UDP].payload)
        text = decrypt(payload, token)
        if text is None or not text.strip():
            # Hello/discovery packets carry no JSON payload.
            continue
        direction = "<-" if pkt[UDP].sport == 54321 else "->"
        print(f"\n[{i}] {pkt[IP].src} {direction} {pkt[IP].dst}")
        try:
            print(text.decode("utf-8"))
        except UnicodeDecodeError:
            print(repr(text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
