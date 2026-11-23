"""Helpers for Chunmi IH Cooker Slim recipe payloads.

The Mi Home plugin passes two strings to the ``start-cooking`` (3/1) and
``set-menu`` (3/5) actions:

* the recipe name, encoded as GBK and written as a hex string;
* the cooking program ("cook script"), a byte array serialized as a hex string
  with a CRC-16 in the last two bytes.

The byte layout below is taken verbatim from the official plugin's
``CMCookProfile`` implementation (module 10280 in the Android bundle).
It is enough to generate single-fire and single-temperature programs.
Complex multi-step programs should be captured from the Mi Home app and passed
to the integration as a raw ``cook_data`` string.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Every cloud profile captured from the app for this model is 160 bytes.  The
# old 36-byte generator never reached the phase interpreter on real hardware.
DEFAULT_PROFILE_SIZE = 160
DEFAULT_DEVICE_TYPE = 3
DEFAULT_SMALL_TYPE = 2
DEFAULT_FIRE = 45
DEFAULT_TEMPERATURE = 100
DEFAULT_MINUTES = 30
DEFAULT_UP_TEMPERATURE = 255
DEFAULT_MENU_INDEX = 9  # plugin uses 9 for start-cooking, 0 for manual mode

RECIPE_TYPE_SINGLE_FIRE = 1
RECIPE_TYPE_MULTI_FIRE = 2
RECIPE_TYPE_SINGLE_TEMPERATURE = 3
RECIPE_TYPE_RECIPE = 4


def encode_gbk(value: str) -> str:
    """Encode a recipe name the way the official Mi Home plugin does.

    ``CMCookProfile.getGBK()`` appends the literal two-character string ``"00"``
    after the GBK bytes.  It is a hex-string terminator, not an extra NUL byte;
    the hardware-tested harness uses exactly this form.
    """
    return value.encode("gbk", errors="replace").hex() + "00"


def decode_gbk(value: str | bytes | None) -> str | None:
    """Decode a GBK encoded hex string (or raw bytes) into text."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            raw = bytes.fromhex(value)
        except ValueError:
            # Some firmware returns plain text instead of hex.
            return value
    else:
        raw = value
    return raw.decode("gbk", errors="replace").strip("\x00")


def decode_menu(raw: str | bytes | None) -> dict[str, object] | None:
    """Decode the ``menu`` property into index, id and name.

    The official plugin reads the first byte as the menu index, the following
    four bytes as the menu id and treats the remaining bytes as a GBK name.
    Example: ``0900000001bbf0b9f800`` -> index 9, id 1, "火锅".
    """
    if raw is None:
        return None
    try:
        data = bytes.fromhex(raw) if isinstance(raw, str) else bytes(raw)
    except ValueError:
        return {"raw": raw}
    if len(data) < 6:
        return {"raw": raw.hex()}
    return {
        "raw": data.hex(),
        "index": data[0],
        "menu_id": int.from_bytes(data[1:5], "big"),
        "name": decode_gbk(data[5:]),
    }


def crc16(data: bytes) -> int:
    """CRC-16 used by Chunmi cook scripts (poly 0x1021, init 0x0000)."""
    crc = 0x0000
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
    return crc & 0xFFFF


def make_runnable(cookcode: str) -> str:
    """Normalize a cloud cook script for local action 3/1.

    The official plugin's ``formData()`` writes ``01`` into byte 19 and then
    recalculates the trailing CRC.  Cloud profiles ship with ``02`` there and
    were refused by the cooker until this transform was applied.
    """
    try:
        data = bytearray(bytes.fromhex(cookcode))
    except ValueError as exc:
        raise ValueError("cookcode must be a valid hex string") from exc
    if len(data) != DEFAULT_PROFILE_SIZE:
        raise ValueError(f"Unexpected cookcode length: {len(data)} bytes")
    if data[0] != DEFAULT_DEVICE_TYPE or data[2] != DEFAULT_MENU_INDEX:
        raise ValueError("Not a Chunmi slim cloud cook script")
    data[19] = 1
    data[-2:] = crc16(bytes(data[:-2])).to_bytes(2, "big")
    return data.hex()


@dataclass
class CookProfile:
    """Mutable representation of a cook script byte array."""

    data: bytearray = field(default_factory=bytearray)

    def __init__(self, raw: bytes | bytearray | str | None = None) -> None:
        if raw is None:
            self.data = bytearray(DEFAULT_PROFILE_SIZE)
            self.data[0] = DEFAULT_DEVICE_TYPE
            self.data[1] = DEFAULT_SMALL_TYPE
            self.data[2] = DEFAULT_MENU_INDEX
            self.data[19] = 1  # operation source, "01" in the plugin
            self.data[30] = 255  # phaseTime() marker
            self.data[31] = DEFAULT_UP_TEMPERATURE
        elif isinstance(raw, str):
            try:
                self.data = bytearray(bytes.fromhex(raw))
            except ValueError as exc:
                raise ValueError("cook_data must be a valid hex string") from exc
        else:
            self.data = bytearray(raw)
        if len(self.data) < 4:
            raise ValueError("cook_data is too short")
        if len(self.data) < DEFAULT_PROFILE_SIZE:
            self.data.extend(bytearray(DEFAULT_PROFILE_SIZE - len(self.data)))

    @classmethod
    def from_hex(cls, value: str) -> CookProfile:
        """Build a profile from a hex string captured from the Mi Home app."""
        return cls(value)

    # -- simple field accessors ------------------------------------------
    @property
    def device_type(self) -> int:
        return self.data[0]

    @device_type.setter
    def device_type(self, value: int) -> None:
        self.data[0] = value & 0xFF

    @property
    def small_type(self) -> int:
        return self.data[1]

    @small_type.setter
    def small_type(self, value: int) -> None:
        self.data[1] = value & 0xFF

    @property
    def menu_index(self) -> int:
        return self.data[2]

    @menu_index.setter
    def menu_index(self, value: int) -> None:
        self.data[2] = value & 0xFF

    @property
    def menu_id(self) -> int:
        return int.from_bytes(self.data[3:7], "big")

    @menu_id.setter
    def menu_id(self, value: int) -> None:
        self.data[3:7] = (value & 0xFFFFFFFF).to_bytes(4, "big")

    @property
    def flags(self) -> int:
        return self.data[7]

    @property
    def keep_on_device(self) -> bool:
        return bool(self.data[7] & 0x80)

    @keep_on_device.setter
    def keep_on_device(self, value: bool) -> None:
        if value:
            self.data[7] |= 0x80
        else:
            self.data[7] &= 0x7F

    @property
    def schedule_enabled(self) -> bool:
        return bool(self.data[14] & 0x80)

    @schedule_enabled.setter
    def schedule_enabled(self, value: bool) -> None:
        if value:
            self.data[14] |= 0x80
        else:
            self.data[14] &= 0x7F

    @property
    def cook_time(self) -> int:
        """Total cooking time in minutes."""
        return self.data[8] * 60 + self.data[9]

    @cook_time.setter
    def cook_time(self, minutes: int) -> None:
        minutes = max(0, int(minutes))
        self.data[8] = (minutes // 60) & 0xFF
        self.data[9] = minutes % 60

    @property
    def cook_time_max(self) -> int:
        """Upper limit for the adjustable cooking time, in minutes."""
        return self.data[10] * 60 + self.data[11]

    @cook_time_max.setter
    def cook_time_max(self, minutes: int) -> None:
        minutes = max(0, int(minutes))
        self.data[10] = (minutes // 60) & 0xFF
        self.data[11] = minutes % 60

    @property
    def cook_time_min(self) -> int:
        """Lower limit for the adjustable cooking time, in minutes."""
        return self.data[12] * 60 + self.data[13]

    @cook_time_min.setter
    def cook_time_min(self, minutes: int) -> None:
        minutes = max(0, int(minutes))
        self.data[12] = (minutes // 60) & 0xFF
        self.data[13] = minutes % 60

    @property
    def schedule_duration(self) -> int:
        """Scheduled cooking duration in minutes (bits 7 of bytes 14/15 are flags)."""
        return (self.data[14] & 0x7F) * 60 + (self.data[15] & 0x7F)

    @schedule_duration.setter
    def schedule_duration(self, minutes: int) -> None:
        minutes = max(0, int(minutes))
        flag14 = 0x80 if self.data[14] & 0x80 else 0
        flag15 = 0x80 if self.data[15] & 0x80 else 0
        self.data[14] = ((minutes // 60) & 0x7F) | flag14
        self.data[15] = (minutes % 60) & 0x7F | flag15

    @property
    def schedule_time(self) -> int:
        """Start time of a scheduled program, in minutes after midnight."""
        return self.data[16] * 60 + self.data[17]

    @schedule_time.setter
    def schedule_time(self, minutes: int) -> None:
        minutes = max(0, int(minutes))
        self.data[16] = (minutes // 60) & 0xFF
        self.data[17] = minutes % 60

    @property
    def recipe_type(self) -> int:
        return self.data[18]

    @recipe_type.setter
    def recipe_type(self, value: int) -> None:
        self.data[18] = value & 0xFF

    @property
    def operation_source(self) -> int:
        """Byte 19: nonzero means use the supplied profile, not a stored one."""
        return self.data[19]

    @property
    def phase(self) -> int:
        return self.data[28]

    @property
    def up_temperature(self) -> int:
        return self.data[31]

    @up_temperature.setter
    def up_temperature(self, value: int) -> None:
        self.data[31] = value & 0xFF

    @property
    def temperature(self) -> int:
        return self.data[32]

    @temperature.setter
    def temperature(self, value: int) -> None:
        self.data[32] = value & 0xFF

    @property
    def fire(self) -> int:
        return self.data[33]

    @fire.setter
    def fire(self, value: int) -> None:
        self.data[33] = value & 0xFF

    def summary(self) -> dict[str, object]:
        """Return a JSON friendly description of the program."""
        return {
            "device_type": self.device_type,
            "small_type": self.small_type,
            "menu_index": self.menu_index,
            "menu_id": self.menu_id,
            "keep_on_device": self.keep_on_device,
            "schedule_enabled": self.schedule_enabled,
            "cook_time_minutes": self.cook_time,
            "cook_time_max_minutes": self.cook_time_max,
            "cook_time_min_minutes": self.cook_time_min,
            "schedule_duration_minutes": self.schedule_duration,
            "schedule_time_minutes": self.schedule_time,
            "recipe_type": self.recipe_type,
            "phase": self.phase,
            "up_temperature": self.up_temperature,
            "temperature": self.temperature,
            "fire": self.fire,
        }

    # -- serialization ----------------------------------------------------
    def to_hex(self) -> str:
        """Serialize the profile and refresh the trailing CRC-16."""
        payload = bytearray(self.data)
        if len(payload) < 4:
            raise ValueError("cook_data is too short")
        checksum = crc16(bytes(payload[:-2]))
        payload[-2] = (checksum >> 8) & 0xFF
        payload[-1] = checksum & 0xFF
        self.data = payload
        return payload.hex()


def build_simple_profile(
    *,
    minutes: int = DEFAULT_MINUTES,
    fire: int = DEFAULT_FIRE,
    temperature: int = DEFAULT_TEMPERATURE,
    recipe_type: int = RECIPE_TYPE_SINGLE_FIRE,
    menu_index: int = DEFAULT_MENU_INDEX,
    menu_id: int = 0,
    device_type: int = DEFAULT_DEVICE_TYPE,
    small_type: int = DEFAULT_SMALL_TYPE,
    keep_on_device: bool = False,
) -> str:
    """Build a single-stage cook script as a hex string.

    ``recipe_type`` 1 produces a fire/power program (``fire`` is used), 3
    produces a temperature program (``temperature`` is used).
    """
    profile = CookProfile()
    profile.device_type = device_type
    profile.small_type = small_type
    profile.menu_index = menu_index
    profile.menu_id = menu_id
    profile.keep_on_device = keep_on_device
    profile.schedule_enabled = False
    profile.cook_time = minutes
    profile.cook_time_max = max(minutes, 60)
    profile.cook_time_min = 1
    profile.recipe_type = recipe_type
    profile.up_temperature = DEFAULT_UP_TEMPERATURE
    profile.temperature = temperature
    profile.fire = fire
    return profile.to_hex()
