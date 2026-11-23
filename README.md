# Chunmi IH Cooker Slim — local Home Assistant integration

HACS-compatible custom component for the **米家超薄电磁炉** (`chunmi.ihcooker.slim`,
product ID 4899). Cooking control is local miIO using the cooker IP and 32-character
token — no Mi account and no cloud control of the appliance.

Recipe discovery, bilingual data and translation are optional runtime features.
They use anonymous HTTPS requests to Joyami (`gateway.joyami.com`) and Google
Translate (`translate.googleapis.com`); neither requires or stores a Mi account
credential.

## What works locally

Validated against real hardware with firmware `2.2.0_0005`:

- **26 readable properties**: status, work status, fault, temperatures, cook/pause/
  appointment timers, fire gears, phase, menu (including decoded menu name), recipe
  type, finish flags and diagnostics.
- **3 writable properties**: `heat_level` (2/7), `finish_push` (3/24) and
  `buzzer_mark` (3/25). The last two require JSON booleans; integer writes return
  `-4005`, which this integration handles automatically. `heat_level` accepts a
  write but some firmware versions ignore it while idle.
- **Hardware-verified actions**: `start_cook` (2/1), `cancel_cooking` (2/2),
  `pause` (2/3), and local launch of the 160-byte cloud recipes through 3/1.
  `start_cook(1)` returned `code: 0`, set `cook_time` to 120 s and raised the measured
  temperature from 22 °C to 32 °C before `cancel_cooking` cleared the timer. Recipes
  `4209 大阪烧` and `4432 油焖大虾` also returned `code: 0`; knob press advanced
  phase `1 → 2` during the latter, and cancel cleared the session cleanly. Other
  start/menu actions share the validated payload shape but have not each been
  exercised on hardware.
- Recipes are stored locally in the exact 160-byte layout used by the Mi Home plugin,
  including byte-19 normalization, GBK name encoding and CRC-16.

### Start actions: reverse-engineered and hardware-validated

Firmware `2.2.0_0005` **does** implement the MIoT start/menu actions locally.
The earlier failures were caused by the request shape: `python-miio` sends bare
values in the action's `in` list, while this firmware requires each entry to be
an object such as `{"piid": 8, "value": 3}`. Static analysis of the firmware
recovered the exact piid order and value type for every documented action, and
the integration now builds those objects automatically.

A supervised low-power test with a pot of water confirmed the fix: `start_cook(1)`
(Hotpot) returned `code: 0`, the cooker entered cooking with a 120 s timer and the
temperature rose, and `cancel_cooking` returned `code: 0` and cleared the timer.
No knob press was needed during the test, even though the cooker reported
standby states beforehand. For the bundled 160-byte recipe launch
(`4209 大阪烧`), local MIoT `3/1` was likewise accepted with `code: 0` without a
panel press, although sustained cooking still required pressing the knob. The
Mi Home app itself does not use this local path — a full Wireshark
capture while starting Hotpot showed no IP traffic to the cooker at all, because
the app goes through the cloud and asks for panel confirmation.

A read-only sweep of undocumented property IDs and the `cook-mode` write test
found no hidden *property* that can start cooking. See
[docs/local-protocol-investigation.md](docs/local-protocol-investigation.md) for
the evidence and reproduction steps.

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

### Local miIO discovery (no account needed)

The cooker answers a local UDP handshake on port 54321. From this repository:

```zsh
.venv/bin/miiocli discover --handshake --no-mdns --timeout 10
```

If broadcast discovery is blocked, query the cooker directly:

```zsh
.venv/bin/miiocli discover --network 192.168.69.206 --timeout 10
```

Look for the line with IP `192.168.69.206`, ID `494700890`, and model
`chunmi.ihcooker.slim`. The `token:` value is the 32-hex-character token.

### Import from Home Assistant

The config flow can also import the token automatically from locally installed Xiaomi
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

A token is exactly 32 hexadecimal characters; spaces and dashes are stripped
automatically. Keep it out of commits, dashboards, and issue reports — pass it
through the config flow or a shell prompt such as `read -rs 'TOKEN?miIO token: '`.

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
- **Sensor** — an `App status` sensor with English states; recipe and menu names
  in `Current action` are also forced to English so entity states stay consistent
  regardless of the Home Assistant display language. The card remains bilingual.

## App-like controls

A single `start_preset` service maps friendly names to the five built-in modes:

```yaml
action: chunmi_ihcooker_slim.start_preset
data:
  preset: hotpot        # hotpot / steam_boil / simmer / stir_fry / deep_fry
  method: built_in      # or: recipe
  minutes: 30           # optional, recipe method only
  fire: 50              # optional, recipe method only
  temperature: 100      # optional, recipe method only
```

`built_in` calls MIoT action 2/1 with the matching `cook-mode`. `recipe` builds
a Mi-Home-compatible 160-byte `CookProfile` (GBK name + byte-19 normalization +
CRC-16) and calls action 3/1. Both paths send firmware-compatible
`piid`/`value` objects. The `built_in` path was hardware-validated with the Hotpot
preset (mode `1`) without a panel press. The slim recipe profile path was
hardware-validated with bundled recipes `4209 大阪烧` and `4432 油焖大虾`, both
returning `code: 0`. Reachability from full standby is untested.

### Ready-made dashboard

[`dashboards/chunmi_ihcooker_slim.yaml`](dashboards/chunmi_ihcooker_slim.yaml)
is a native HA dashboard that groups live status, the five preset buttons,
pause/cancel, manual heat level and settings into an app-like panel. See
[`dashboards/README.md`](dashboards/README.md) for import instructions. No
extra frontend dependencies are needed.

## Services

All MIoT actions are available under the `chunmi_ihcooker_slim` domain. If more than
one cooker is configured, pass `device_id` to select the target.

Hardware-verified (`2.2.0_0005`):

```yaml
action: chunmi_ihcooker_slim.start_cook
data:
  mode: 1
```

```yaml
action: chunmi_ihcooker_slim.cancel_cooking
data:
  device_id: <optional>
```

```yaml
action: chunmi_ihcooker_slim.pause
```

Best-effort (validated payload shape, individual actions not each tested):
`start_preset`, `start_cooking`, `pause_cooking`, `resume_cooking`,
`cancel_cooking_v2`, `set_menu`, `delete_menu`, `continue_cooking`, `next_step`,
`factory_reset`, `set_charge`, `get_selfcheck`.

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

## Recipes, translation and custom card

The integration ships 22 verified cloud recipes as `recipes.json`, with Chinese
names and English translations. A refresh button/service downloads the public
Joyami catalogue, preserves existing translations, and fills missing English text
with Google Translate. Failures keep the bundled catalogue.

Services:

- `search_recipes`, `get_recipe`, `start_recipe`
- `list_favorites`, `add_favorite`, `remove_favorite`
- `refresh_recipes`, `translate_recipe`, `set_recipe_language`

Entities: `Recipe library`, `Recipe translation status`, `Recipe refresh status`,
`Recipe search query`, `Current action`, `Recipe ID` and `Start preset`.

`start_recipe` returns `active_cooking` and `waiting_for_panel`. On profiles such
as `4209` that stay in `phase 19` after a no-press start, `Current action` shows
`<recipe> — waiting for panel` and the card asks you to press the cooker knob.
`next_step` cannot replace that press on this firmware.

A searchable Lovelace custom card is registered automatically as
`custom:chunmi-ihcooker-card`. Add it from **Add Card → Search**, or paste:

```yaml
type: custom:chunmi-ihcooker-card
```

The card calls the same domain services and binds to the configured cooker
automatically. It is auto-added to Lovelace storage resources; YAML-mode users
should add `/chunmi_ihcooker_slim/chunmi-ihcooker-card.js?v=0.1.0` manually.

`start_recipe` sends the normalized 160-byte cloud profile through the local
miIO action 3/1. Profiles are not re-sent to the cloud, and no cloud service
controls the cooker.

## Recipe format

The verified cloud profiles for this model are 160 bytes, with a CRC-16/XMODEM
in the last two bytes (poly `0x1021`, init `0x0000`):

| Byte(s) | Meaning |
| --- | --- |
| 0 | device type (`03`) |
| 1 | small type (`10`) |
| 2 | menu index (`09`) |
| 3–6 | recipe ID, big endian |
| 7 | flags (`0x80` = keep on device) |
| 8–9 | cook time: hours, minutes |
| 10–13 | adjustable cook time max/min |
| 14–17 | schedule flags, duration and start time |
| 18 | profile/recipe type (`4` or `5` for bundled recipes) |
| 19 | operation source — cloud `02` is rewritten to plugin-compatible `01` |
| 31–158 | 15 × 8-byte phase records from byte 31 |
| 158–159 | CRC-16/XMODEM over bytes 0–157 |

The CRC is recomputed after changing byte 19. Recipe names are sent as GBK hex
plus the literal `00`, for example `火锅` → `bbf0b9f800`.

The `menu` property is encoded differently: first byte = menu index, next four
bytes = menu ID, remainder = GBK-encoded name. `0900000001bbf0b9f800` is index 9,
ID 1, "火锅".

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests/
.venv/bin/python -m compileall -q custom_components scripts
```

`scripts/probe.py` performs a read-only sweep of all mapped properties against a
real cooker. `scripts/probe_paths.py` also scans undocumented property IDs
without writing anything. `scripts/parse_pcap.py` decrypts a tcpdump capture of
miIO UDP traffic with the device token.

For a supervised local recipe test, `tools/smoke_test_recipe.py` lists the bundled
recipes, reads device state, starts one normalized profile over miIO, and cancels
it. It requires `--confirm` before any cooking command and never uses a cloud
service:

```zsh
read -rs 'TOKEN?miIO token: '
printf '\n'
.venv/bin/python tools/smoke_test_recipe.py --list
.venv/bin/python tools/smoke_test_recipe.py --host 192.168.69.206 --token "$TOKEN" --read
.venv/bin/python tools/smoke_test_recipe.py --host 192.168.69.206 --token "$TOKEN" \
  --recipe 4209 --start --confirm
.venv/bin/python tools/smoke_test_recipe.py --host 192.168.69.206 --token "$TOKEN" --cancel
```

The `read -rs 'TOKEN?...'` form is zsh's silent prompt. Do not paste `#` comment
lines into an interactive zsh session unless `setopt INTERACTIVE_COMMENTS` is enabled.

`code: 0` only proves the command was accepted. To confirm real heating, add
`--observe 8` to the `--start` line; the helper waits 8 seconds, prints live
`status`, `phase`, `recipe_type`, `cook_time` and `temperature`, and reports
`active_cooking: True/False`. With `4209`, the observed state was idle
(`status 0`, `work_status 1`, `phase 19`) despite the profile being loaded and
the temperature rising from 15 °C to 32 °C, so a panel press was still needed.

To test the local phase-advance path without touching the panel, use `--next`:

```zsh
.venv/bin/python tools/smoke_test_recipe.py \
  --host 192.168.69.206 --token "$TOKEN" --next --observe 5
```

## Disclaimer

This is an independent integration, not affiliated with Xiaomi or CHUNMI. Cooking
appliances can be dangerous: verify device behaviour before relying on automation,
and never leave a cooking session unattended.
