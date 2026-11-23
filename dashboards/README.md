# App-like dashboard

`chunmi_ihcooker_slim.yaml` is a native Home Assistant Lovelace dashboard that
mirrors the Mi Home cooker screen: live status, temperatures, timers, five
built-in presets, pause/cancel, manual heat level and settings. It uses only
built-in cards, so no extra HACS frontend resources are needed.

The file contains a `views:` list, which is the format Home Assistant expects
for a YAML dashboard. The dashboard title is set where you register the file.

## Import

### Option A — register a YAML dashboard

1. Copy the file to `config/dashboards/chunmi_ihcooker_slim.yaml`.
2. Add this to `configuration.yaml`:

   ```yaml
   lovelace:
     dashboards:
       chunmi-cooker:
         mode: yaml
         filename: dashboards/chunmi_ihcooker_slim.yaml
         title: 米家超薄电磁炉
         icon: mdi:stove
         show_in_sidebar: true
   ```

3. Restart Home Assistant (or reload YAML dashboards).

### Option B — paste into a UI dashboard

1. Go to **Settings → Dashboards → Add Dashboard → New dashboard from scratch**.
2. Open the new dashboard, go to the three-dot menu and choose **Take control**
   if asked.
3. Open **Edit YAML** and paste the file contents.
4. Save.

After importing, open **Developer Tools → States** and verify the cooker entity
IDs. If your device was not named `Chunmi IH Cooker Slim`, replace the example
IDs in the YAML with the IDs shown in your instance.

## What the buttons do

| Button | Action | Local support on 2.2.0_0005 |
| --- | --- | --- |
| 火锅 / 蒸煮 / 煲汤 / 煎炒 / 油炸 | `chunmi_ihcooker_slim.start_preset` | Calls MIoT 2/1; verified working |
| 手动 15 分钟 | `chunmi_ihcooker_slim.start_simple_recipe` | Calls MIoT 3/1 with a 160-byte profile |
| 暂停 | `button.press` on the pause button | Verified working |
| 取消烹饪 | `button.press` on the cancel button | Verified working |
| 火力 / 完成推送 / 蜂鸣提示 | Native entity controls | Verified writable, see README |

The preset buttons include confirmation dialogs because starting a cooking
appliance is a safety-critical action. If your firmware implements only the
recipe action, call `start_preset` with `method: recipe` from Developer Tools →
Actions; the integration will generate a Mi-Home-compatible cook profile.


## Recipe card

The integration registers `custom:chunmi-ihcooker-card` automatically in
Lovelace storage mode. It searches the bundled Joyami catalogue, shows localized
ingredients/steps, manages favorites, translates missing text and starts recipes
through local miIO. The YAML dashboard also includes the card on a dedicated
"菜谱" view plus native recipe status entities as a fallback.
