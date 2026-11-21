# Chunmi IH Cooker Slim — local Home Assistant integration

HACS-compatible custom component for the **米家超薄电磁炉** (`chunmi.ihcooker.slim`,
product ID 4899). It talks directly to the cooker over miIO using its IP address and
32-character token — no cloud account, no Xiaomi account, no internet required.

## What works locally

Validated against real hardware with firmware `2.2.0_0005`:

- **26 readable properties**: status, work status, fault, temperatures, cook/pause/
  appointment timers, fire gears, phase, menu (including decoded menu name), recipe
  type, finish flags and diagnostics.
- **3 writable properties**: `heat_level` (2/7), `finish_push` (3/24) and
  `buzzer_mark` (3/25). The last two require JSON booleans; integer writes return
  `-4005`, which this integration handles automatically. `heat_level` accepts a
  write but some firmware versions ignore it while idle.
- **2 working actions**: `cancel_cooking` (2/2) and `pause` (2/3).
- Recipes can be **generated** locally from the exact byte layout used by the Mi Home
  plugin, including GBK name encoding and CRC-16.

### Known firmware limitation

The cooker does **not** implement the other MIoT actions locally:

- `start_cook` (2/1) and every service-3 action (`start_cooking`, `pause_cooking`,
  `resume`, `next_step`, menu save/delete, self-check, …).
- With an empty `in` list they return MIoT code `-4003` ("does not exist"); with any
  parameters the firmware replies with malformed JSON (`{"result":,}`).
- A `tcpdump` capture while starting Hotpot in the Mi Home app showed only local
  miIO *hello* packets — no action commands. The app discovers the cooker locally but

  issues cooking commands through the cloud.

Those actions are still exposed as services so they work on firmware versions that do
implement them; on `2.2.0_0005` they fail with a clear "cloud-only on this firmware"
error instead of a stack trace. Starting a cook must currently be done in Mi Home.

## Installation

### HACS

1. Add this repository to HACS as a **custom repository** of type *Integration*.
2. Search for **Chunmi IH Cooker Slim (Local)** and install it.
3. Restart Home Assistant.
4. *Settings → Devices & Services → Add Integration → Chunmi IH Cooker Slim (Local)*.

### Manual

Copy `custom_components/chunmi_ihcooker_slim/` into your Home Assistant `config/`
directory and restart.

## Getting the token

The config flow can import the token automatically from locally installed Xiaomi
integrations:

- **Xiaomi Home (official)**: `.storage/xiaomi_home/miot_devices/*.dict`
- **Xiaomi Miot (`hass-xiaomi-miot`)**: config entry data/options

Choose *Import token from another Xiaomi integration* when adding the cooker, select
the detected device, then confirm its IP address. Only devices whose model is
`chunmi.ihcooker.slim` are shown.

Manual fallback: the official Xiaomi Home integration stores the token in the same
`*.dict` file above as JSON plus a SHA-256 checksum. Look for the record whose `did`
matches your cooker and take its 32-hex-character `token`. You can also extract a
token from a backed-up Mi Home app database or by using one of the standard miIO
token extraction methods. The integration always connects directly to the device IP
and never contacts the cloud.

## Configuration

| Field | Description |
| --- | --- |
| IP address | Cooker IP on the local network (e.g. `192.168.1.100`) |
| Token | 32 hex characters; spaces and dashes are stripped automatically |
| Device name | Friendly name shown in Home Assistant |
| Polling interval | Seconds between property reads (default 10) |
| Connection timeout | Seconds (default 5) |

Options can be changed later without re-entering the token.

## Entities

- **Sensors** — status, work status, fault, menu name and raw menu data, phase,
  temperatures, fire gears, cook/appointment/pause/step timers, recipe type and
  diagnostics.
- **Binary sensors** — cooking, paused, fault, finished.
- **Switches** — finish push notification and buzzer.
- **Number** — heat level (writable on 2.2.0_0005).
- **Buttons** — cancel cooking and pause.

## Services

All MIoT actions are available under the `chunmi_ihcooker_slim` domain. If more than
one cooker is configured, pass `device_id` to select the target.

Safe/verified:

```yaml
action: chunmi_ihcooker_slim.cancel_cooking
data:
  device_id: <optional>
```

```yaml
action: chunmi_ihcooker_slim.pause
```

Best-effort (firmware dependent): `start_cook`, `start_cooking`, `pause_cooking`,
`resume_cooking`, `cancel_cooking_v2`, `set_menu`, `delete_menu`, `continue_cooking`,
`next_step`, `factory_reset`, `set_charge`, `get_selfcheck`.

Recipe helpers:

```yaml
action: chunmi_ihcooker_slim.start_simple_recipe
data:
  name: "火锅"
  minutes: 30
  mode: fire       # or: temperature
  value: 45
  menu_index: 9
```

`set_simple_menu` takes the same fields plus `bell`. For full control,
`start_cooking` / `set_menu` accept a raw hex `cook_data` string captured from the
Mi Home plugin.

## Recipe format

`cook_data` is a hex-encoded byte array (36 bytes by default) with a CRC-16 in the
last two bytes (poly `0x1021`, init `0x0000`). The layout matches the official
plugin's `CMCookProfile`:

| Byte(s) | Meaning |
| --- | --- |
| 0–1 | device type (`03`) and small type (`02`) |
| 2 | menu index |
| 3–6 | menu ID, big endian |
| 7 | flags (bit 7 = keep on device) |
| 8–9 | cook time: hours, minutes |
| 10–13 | adjustable cook time max/min |
| 14–17 | schedule flags, duration and start time |
| 18 | recipe type (1 = fire, 2 = multi-fire, 3 = temperature, 4 = recipe) |
| 19 | operation source (`01`) |
| 28 | phase |
| 30–31 | phase marker and upper temperature |
| 32–33 | target temperature / fire level |
| 34–35 | CRC-16 |

The `menu` property is encoded differently: first byte = menu index, next four
bytes = menu ID, remainder = GBK-encoded name. Example: `0900000001bbf0b9f800` is
index 9, ID 1, "火锅".

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests/
.venv/bin/python -m compileall -q custom_components scripts
```

`scripts/probe.py` performs a read-only sweep of all properties against a real
cooker. `scripts/parse_pcap.py` decrypts a tcpdump capture of miIO UDP traffic with
the device token.

## Disclaimer

This is an independent integration, not affiliated with Xiaomi or CHUNMI. Cooking
appliances can be dangerous: verify device behaviour before relying on automation,
and never leave a cooking session unattended.
