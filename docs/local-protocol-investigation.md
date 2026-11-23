# Local protocol investigation

Firmware: `2.2.0_0005`, model `chunmi.ihcooker.slim`, product ID 4899.
Goal: find a local-only path to start a cooking program before considering cloud
control.

## Result

The local start actions **are implemented in firmware 2.2.0_0005**. The earlier
`start_cook`/`start_cooking` failures were caused by the request shape, not by
missing firmware support: `python-miio` sends bare values in the MIoT action's
`in` list, while this firmware requires each entry to be an object with `piid`
and `value`. Static reverse engineering recovered the exact piid/type table for
every documented action, and the integration now builds those objects.

The corrected local payload was subsequently **validated on hardware** with a
supervised low-power test (pot with water, cooker awake): `start_cook(1)` returned
`code: 0`, set `cook_time` to 120 s and raised the measured temperature from
22 °C to 32 °C; `cancel_cooking` returned `code: 0` and cleared the timer. See
section 9 below.

The Mi Home app still issues cooking commands through the cloud and asks the
user to confirm on the panel. That does not mean the local RPC handlers are
absent — they are present and reachable over miIO.

## Evidence

### 1. Property sweep

`scripts/probe.py` reads every property in `const.py`. Verified readable:

```text
2/1 status, 2/2 fault, 2/5 left_time, 2/6 working_time, 2/7 heat_level
3/1 menu, 3/2 phase, 3/3 work_status, 3/4 cook_time, 3/5 appoint_time
3/6 pause_time, 3/7 temperature, 3/8 target_temperature, 3/9 fire_gears
3/10 step_time, 3/11 version, 3/13 custom_details, 3/14 error_code
3/15 recipe_type, 3/16 step_flag, 3/24 finish_push, 3/25 buzzer_mark
3/27 charge_phase, 3/28 finish, 3/29 move_temperature, 3/30 step_total_time
```

`scripts/probe_paths.py` additionally scans every piid in service 2 (1-20) and
service 3 (1-40) with read-only `get_properties` calls. It found **no**
readable property outside that list. In particular there is no hidden status,
command or recipe property that could be written to start cooking.

### 2. `cook-mode` is a dead end

The public MIoT spec marks `cook-mode` (2/8) as writable with values 1-5.
On the device:

- read returns `-4001` (not readable);
- write of value `3` returns `-4002` (not writable).

So the built-in mode cannot be selected by writing a property.

### 3. Actions

| Action | Old result (bare `in` values) | Correct `in` objects |
| --- | --- | --- |
| `cancel_cooking` 2/2 | `{'code': 1}` — works | `[]` |
| `pause` 2/3 | `{'code': 1}` — works | `[]` |
| `start_cook` 2/1 | `-4003` / malformed JSON | `[{"piid":8,"value":3}]` |
| `start_cooking` 3/1 | `-4003` / malformed JSON | `[{"piid":22,"value":"<gbk-hex>"},{"piid":17,"value":"<profile-hex>"},{"piid":19,"value":"<user-id>"}]` |
| Other service-3 actions | fail the same way | See the firmware validator table below |

`python-miio 0.5.12` sends `params` directly as `in`. The firmware's `cmdrpc.action`
parser iterates those entries as JSON objects, reads `piid` and `value`, and
returns a parse failure when they are absent. The public MIoT spec documents the
same object form in its `cook-data` example. The integration now wraps values
accordingly.

The argument order and JSON types recovered from the firmware jump table are:

| Action | Required `in` objects |
| --- | --- |
| `2/1 start-cook` | `[{"piid":8,"value":<number>}]` |
| `2/2 cancel-cooking` | `[]` |
| `2/3 pause` | `[]` |
| `3/1 start-cooking` | `22` string, `17` string, `19` string |
| `3/2 pause-cooking` | `20` string, `19` string |
| `3/3 pause-recover` | `20` string, `19` string |
| `3/4 cancel-cooking` | `20` string, `19` string |
| `3/5 set-menu` | `17` string, `19` string, `21` number, `22` string |
| `3/6 delete-menu` | `19` string, `20` string, `21` number, `23` number |
| `3/7 continue-cooking` | `20` string, `19` string |
| `3/8 next-step-cooking` | `20` string, `19` string |
| `3/9 factory-reset` | `20` string, `19` string |
| `3/10 set-charge` | `18` string |
| `3/11 get-error-recorded` | `31` number |
| `3/12 get-selfcheck` | `34` number |

Unknown actions were not called because several are destructive (for example
factory reset). Only documented start/pause/cancel paths were exercised on
hardware; all other behaviour below is static analysis.

### 4. App traffic

An earlier narrow `tcpdump` capture on UDP port 54321 while starting Hotpot
showed only 32-byte miIO hello replies.

This was rechecked with Wireshark's bundled `tshark` on the Mac that actually
runs Xiaomi Home. A full-packet capture on `en0` (no capture filter, 43,225
frames over 35.1 s) was running while Hotpot was started:

- `ip.addr == 192.168.69.206`: **zero frames**.
- `eth.addr == 7C:C2:94:1C:D1:A0`: one gratuitous ARP from the cooker, no IP
  traffic.
- No UDP packet from the Mac (`192.168.69.150`) to port 54321 or to any local
  broadcast address. One `0x2131` miIO hello came from a different device
  (`192.168.69.130`) and is unrelated.
- The app resolved and opened TLS connections to Xiaomi cloud endpoints,
  including `api.mijia.tech`, `home.mi.com`, `gateway.joyami.com` and
  `post.joyami.com`.

Conclusion: the **app** start command is cloud-only on this firmware/app
combination — no local start packet was captured. That is separate from whether
the cooker's local miIO RPC handlers exist. The firmware analysis below shows
that they do; the app simply does not use them.

### 5. Panel prerequisites

The official manual and the Mi Home plugin confirm that the cooker's panel is
part of the normal start flow:

- The manual says to press the main knob for 0.5 s to power on, rotate to a
  mode, then press the knob to confirm and start cooking.
- Wi-Fi setup happens on first power-on. The on-device Wi-Fi menu is only for
  reset/status; the manual has no "allow app/Wi-Fi/remote control" toggle and
  no app-authorisation step.
- Pot detection is automatic: the plugin exposes error `2` / "no cooking ware"
  and says cooking resumes after the pot is replaced.
- The plugin's start button calls `startCooking`/`startCook`, then immediately
  shows the message `请在10分钟之内启动电磁炉` / "Please turn on the induction
  cooker within 10 minutes" with an image of the panel. This means the app
  command prepares/arms the program and the user still presses the cooker knob
  to actually begin heating.
- The plugin only blocks start when the device is offline, already working, in
  an error state, stopped, or finished. There is no remote-control permission
  check in that flow.

Earlier `-4003`/malformed-JSON responses are explained by the malformed `in`
list, not by a panel prerequisite or a missing action. The Wireshark capture
still shows that the app chooses the cloud path; the corrected local RPC has not
been observed on the wire.

Practical consequence: a `start_preset` call used to be suspected of only
arming the program. A supervised pot-with-water test has since confirmed that
it starts locally once the cooker is awake (section 9). Starting from full
standby remains untested because the miIO listener is unreachable while asleep.

### 6. Publicly catalogued firmware versions

The public [mindsolo firmware catalog for this model](https://vacuum.mindsolo.net/en/models/chunmi.ihcooker.slim)
lists only two distinct device firmware versions:

| Version | Date | Changelog | Notes |
| --- | --- | --- | --- |
| `2.2.0_0005` | 2023-04-03 | "Optimize user experience" | Current device. The catalog has three records for it (two named `2.2.0_0005`, one named `upd_chunmi.ihcooker.slim.bin`); these are duplicate entries, not separate releases. Sizes: 1,346,052 / 1,346,122 bytes. |
| `2.2.0_0003` | 2021-06-18 | "Migrate the 2.2.0 version SDK" | Older release, 1,336,634 bytes. No public changelog suggests a MIoT start-action fix. |

Sources: [2.2.0_0005 record](https://vacuum.mindsolo.net/en/firmwares/3477/versions/26999),
[2.2.0_0003 record](https://vacuum.mindsolo.net/en/firmwares/3477/versions/27000),
and the [full firmware project](https://vacuum.mindsolo.net/en/firmwares/3477).

No newer public firmware was found. Xiaomi's authoritative OTA endpoint
(`/app/home/latest_version`) requires an authenticated Mi Home session, so it
could not be queried anonymously. The MIoT spec revisions `v1`/`v2` and any
app/plugin version numbers are protocol/app metadata, **not** device firmware.

Conclusion: this cooker is already on the newest publicly catalogued firmware.
Downgrading to `2.2.0_0003` is not needed to fix the payload-shape problem and
would risk the device.

### 7. Other Xiaomi HA integrations with local support

Two popular community/official integrations were checked at these commits:

- `al-one/hass-xiaomi-miot`: `8ac4df7005aefb6a92ae5f66f53fa56e2e548c16`
- `XiaoMi/ha_xiaomi_home`: `75b3acb6325a3a8d295688b13904737d6738a6a5`

`hass-xiaomi-miot` has direct local support. Its setup flow has an
"Add device using host/token (局域网集成)" option
(`config_flow.py:323-385`), and a config entry without a Mi Account is treated as
`local` (`core/device.py:312-324`). It creates an `AsyncMiIO(host, token)`
client (`core/device.py:1656-1667`) and sends the standard miIO methods
`get_properties`, `set_properties`, and `action`
(`core/device.py:1300-1328`, `1677-1683`, `1712-1722`). Its
`MIOT_LOCAL_MODELS` list explicitly contains `chunmi.ihcooker.slim`
(`core/miot_local_devices.py:129`), and `use_local` returns true for models in
that list (`core/device.py:873-889`). Generic `*.ihcooker.*` customizations
expose `start_cook`, `pause`, `cancel_cooking`, and `heat_level`
(`core/device_customizes.py:3478-3483`). There is no special app-compatible
start implementation for this model; it uses the same MIoT `action` RPC. That
integration also passes bare values in `in`, so it would hit the same firmware
parser failure.

`ha_xiaomi_home` also supports local control, but it requires Xiaomi OAuth
login to import devices. Its default `AUTO` control mode prefers a Xiaomi
central hub gateway, then Xiaomi LAN control, then cloud
(`miot/miot_client.py:643-836`; `miot/const.py:138`). Hub control uses local
MIPS `proxy/rpcReq` (`miot/miot_mips.py:1318-1383`), while LAN control uses UDP
port `54321`, the `0x2131` miIO header, and the device token for AES encryption
(`miot/miot_lan.py:167-260`, `438-445`, `820-877`). The LAN device filter skips
models in `lan/profile_models.yaml`; `chunmi.ihcooker.slim` is not in that list
and is not in `UNSUPPORTED_MODELS`, so the LAN path would be attempted if
enabled. The official documentation describes LAN control as partial/unstable
and recommends against enabling it (`README.md:94-102`). Its central-hub local
mode is China-only and needs hub firmware `3.3.0_0023+`
(`README_zh.md:94-102`).

Neither integration contains a workaround for the malformed local start
payload: no corrected GBK/`cookData` action request over LAN, no cloud-recipe
synthesis, and no panel-confirmation automation. The only meaningfully different local transport
found is the official integration's central-hub MIPS path, which would require
a compatible hub and has not been tested.

### 8. Firmware disassembly

The OTA image was downloaded from Xiaomi's authenticated `/home/latest_version`
endpoint and verified as firmware `2.2.0_0005`:

```text
size   1346052 bytes
md5    1aa78b0c6570852e76ca7bfba7d2d4e2
sha256 a134179a3acd9bf6ce6eafa4576a01ed7ea4fbcd8ea36ff2a4bde1ecc1f40c34
```

`esptool image-info` identifies an ESP32 ESP-IDF app (not a full flash dump):
entry point `0x40081270`, 7 segments, flash 16 MB/DIO/40 MHz, built from
ESP-IDF `v4.0.1-476-gd229aa044-dirty`, project `miio_app`, build string
`封样版本2.2.0_0003-5-g35333`, compiled `Dec 31 2022 15:05:52`.

With radare2 and the ESP32 segment mapping (DROM VA `0x3f400020` → file `0x20`,
IROM VA `0x400d0018` → file `0x30018`), the command table at DRAM4 VA
`0x3ffc2d70` was decoded. Entries are 20 bytes:
`[name, fully-qualified name, handler, arg/help, count/flags]`. It contains:

| Command | Handler |
| --- | --- |
| `cmdrpc.action` | `0x4010008c` |
| `cmdrpc.get_properties` | `0x401002e0` |
| `cmdrpc.set_properties` | `0x40100658` |
| `user.action` | `0x40129b68` |
| `user.get_properties` | `0x40129b9c` |
| `user.set_properties` | `0x40129b30` |
| `user.set_start`, `user.set_menu`, pause/resume/cancel | `0x40129580` |

`cmdrpc.action` (`0x4010008c`) reads `siid`, `aiid` and `in[]`, and rejects
missing `piid`/`value` with messages such as
`[E] %s: "piid" not found (%s,%d)` and `[E] %s: params parse error (%s,%d)`.
`action_operation_decoder` (`0x4012af58`) reads `siid` from context offset
`+132`: value `2` selects the service-2 validator `0x4012b944`, value `3`
selects the service-3 validator `0x4012b4e0`, and anything else returns
`0xfffff05d` (`-4003`). The service-3 validator jumps through the table at
`0x3f415484`, indexed by `aiid`, into one validator per documented action.

Those validators confirm the table in section 3. For example:

- Service-2 `aiid=1` requires one argument with `piid=8` and a JSON **number**;
  `aiid=2` and `aiid=3` require exactly zero arguments.
- `3/1` requires three strings: `piid=22`, `17`, `19`.
- `3/5` requires `17` string, `19` string, `21` number, `22` string.
- `3/6` requires `19` string, `20` string, `21` number, `23` number.
- `3/10`, `3/11` and `3/12` require one argument each (`18` string, `31`
  number, `34` number).

The conversion helpers tag parsed values internally as type 1 (bool), 2
(string) or 3 (number). The shared `user.set_start` wrapper (`0x40129580`)
builds the miIO response, validates parsed arguments, calls the command-specific
callback and formats `error`/`code`/`message`/`result`. State gating beyond the
argument validators has not been fully traced.

This is static analysis of the exact firmware running on the device. It
explains the old `-4003`/malformed-JSON responses.

### 9. Supervised hardware validation

A pot with water was placed on the cooker, the panel was awake, and the local
start path was exercised with a hard cancellation in a `finally` block:

```text
before:            status=5  work_status=11  heat_level=0  temperature=22  cook_time=0
heat_level write:  accepted by protocol; value stayed 0 while idle
start_cook(1):     {"code": 0, "out": []}
after 0.3 s:       status=0  work_status=1   cook_time=120  temperature=22
after 0.7 s:       status=0  work_status=1   cook_time=120  temperature=22
after 1.5 s:       status=0  work_status=1   cook_time=120  temperature=32
cancel_cooking():  {"code": 0, "out": []}
after cancel:      status=0  work_status=1   cook_time=0    temperature=15
```

Conclusions:

- The `{"piid": ..., "value": ...}` argument wrapper is correct and sufficient
  for the local start action. The old `-4003`/malformed-JSON responses are fixed.
- Action `2/1` with `piid 8 = 1` starts the Hotpot program without any panel
  press. The cooker was reporting `status=5`/`work_status=11` beforehand and
  still armed and heated within ~1.5 s.
- Action `2/2` stops the program and clears `cook_time`.
- Writing `heat_level` while idle is acknowledged but ignored by this firmware;
  a low-power precondition cannot be set before starting.
- The temperature sensor reads 22 °C before the test and 15 °C afterwards, so
  absolute readings should be treated cautiously; the 22 → 32 rise is the
  useful heating evidence.
- `start_cook(1)` and two slim cloud profiles (`4209 大阪烧`, `4432 油焖大虾`)
  were tested. Other built-in modes use the same argument wrapper but were not
  individually exercised.
- Reachability from full power-off standby was not established. ICMP/UDP probes
  from one shell failed while another shell on the same Mac succeeded, so the
  cause could not be isolated. The test itself needed no panel press.

## Re-running the checks

```bash
python3 scripts/probe.py --host <IP> --token <TOKEN>
python3 scripts/probe_paths.py --host <IP> --token <TOKEN>
```

Both scripts are read-only. Do not replace the token in this repository; pass
it on the command line or through your shell history tool of choice.

## Implication for this integration

The integration now builds the firmware-compatible `piid`/`value` objects for
every documented action. The app-like preset buttons therefore send valid
local start requests on `2.2.0_0005`, and the built-in Hotpot path has been
confirmed to actually heat and to be cancellable locally without a panel press.
Reachability from full standby remains untested. Other built-in modes share the
validated wrapper but were not individually exercised. Bundled slim recipes are
launched by the same local miIO path after byte-19/CRC normalization; Joyami is
used only to obtain recipe data, never to control the appliance.


## Slim cloud profile normalization (confirmed)

All 22 saved recipes for `chunmi.ihcooker.slim` are 160-byte, CRC-valid profiles
with header `03 10 09` and `data[7] = 0x80`. Cloud profiles ship with
`data[19] = 0x02`; the official plugin writes `0x01` before computing the final
CRC. The cooker refused the raw cloud value and accepted the normalized profile
on hardware (`4209 大阪烧`, `4432 油焖大虾`, both `code: 0`). Both launches were
accepted without a knob press, but acceptance is not the same as sustained
cooking: with `4209`, an 8-second observation showed the profile loaded
(`recipe_type 4`, `menu` = 大阪烧, `cook_time 5`) and temperature rising from
15 °C to 32 °C, while `status 0`, `work_status 1` and `phase 19` still reported
idle. A panel press was required to enter active cooking.

`09 0a 00` seen in captures belongs to the name argument stream, not to the
160-byte cook script. The actual phase list is 15 records of 8 bytes starting at
byte 31. Runtime launch uses MIoT 3/1 with
`[GBK-name + "00", 160-byte-profile-hex, uid]`; MIoT 3/5 is only for persistent
device menu slots and is not needed to start bundled recipes.

During a supervised `4432 油焖大虾` run, MIoT 3/8 `next_step` returned `code: 0`
without any `setCharge`/`set_charge` call. The cooker moved from `phase: 1` to
`phase: 2`, and the step timer changed from `step: 27, total: 60` to
`step: 180, total: 180`. Temperature continued to rise and `cancel_cooking`
later returned `code: 0`. This confirms that phase advance is a normal local
action and that no charge command is required. For `4209`, `phase 19` is the
idle/ready marker after a no-press start. Calling `3/8 next_step` returned
`code: 0` but left `phase 19`, `status 0` and `work_status 1` unchanged, so it
cannot replace the panel press for that profile.

The integration therefore reports the distinction explicitly: `start_recipe`
now returns `active_cooking` and `waiting_for_panel`, and `Current action`
shows `<recipe> — waiting for panel` while `Recipe ID` keeps the loaded ID until
cancel or another action clears it. Pressing the knob during the observation
changed the state to `status 1`, `work_status 2`, `phase 1`, `recipe_type 4` and
`active_cooking: True`; cancel then returned `code: 0`. The behavior is therefore
fully characterized: local miIO loads and controls the recipe, while the knob
press is a hardware safety step.
