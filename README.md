# airnanny

Home Assistant integration for Atmeex AirNanny breezers (tested with an A7), plus a small CLI for the Atmeex cloud API.

The breezer has no local API: it only keeps a connection to `api.iot.atmeex.com`, so everything goes through the cloud.

## Home Assistant integration

### Before you start

The integration only sees devices that are already in your Atmeex cloud account. First install the official **Atmeex** app, log in, and add your breezer there (together with a room, if the app asks for one). Once the device shows up in the app, it's in the Atmeex cloud and the integration will find it.

Use the same login in Home Assistant as in the app. Email+password and phone+SMS are separate sign-in methods: signing in by phone with a number the app doesn't know creates a new, empty account.

### Install

`custom_components/atmeex` works without HACS:

1. Copy the `custom_components/atmeex` folder into the `custom_components` folder of your Home Assistant config directory.
2. Restart Home Assistant.
3. Go to Settings → Devices & services → Add integration → **Atmeex AirNanny**, and log in with email+password or phone+SMS.

### Entities

| Entity | What it does |
|---|---|
| Fan | Power on/off. Off also closes the damper (recirculation), like the remote's power button; on restores the previous damper position |
| Fan speed | Slider 1–7 |
| Heater / Heater temperature | Heater on/off, and target 10.0–30.0 °C in 0.5° steps (the target is remembered while the heater is off) |
| Humidifier | Slider 0–3, 0 = off |
| Air intake | Fresh air / Mixed / Recirculation (these also switch the fan on) / Supply air valve (fan off, damper open, as in the app) |
| AutoNanny, Night mode | Mode switches; turning them off restores the fan speed they overwrote |
| Night mode from / until | Night window |
| Time zone | UTC offset in hours for the device clock (the app and remote can't set it; unset means UTC). Kept in sync automatically |
| CO2, Room temperature, Inlet air temperature, Humidity, Actual fan speed, Water tank empty | Sensors |
| Fan throttled | On when the breezer runs slower than set for over a minute on its own (e.g. with cold inlet air) |
| Online | Cloud connectivity |

## API notes

- `GET /devices` lists devices without live condition; `GET /devices/{id}` includes it.
- `PUT /devices/{id}/params` accepts any subset of: `u_pwr_on`, `u_fan_speed` (0–6 = app 1–7), `u_damp_pos` (0 fresh, 1 mixed, 2 recirculation), `u_temp_room` (°C×10, −1000 = heater off), `u_hum_stg`, `u_auto`, `u_night`, `u_night_start`/`u_night_stop` ("HH:MM"; values written by the device come back as "H:MM", e.g. "8:00"), `u_cool_mode`, `u_time_zone` (hours; can't be reset to null).
- The app's speeds 1–7 are `u_fan_speed` 0–6. The fan is stopped only when `u_pwr_on` is false.
- The app's "supply air valve" mode is `u_pwr_on: false` with `u_damp_pos: 0` (the app also sets `u_fan_speed: 0`).
- The server answers 200 even for unknown fields.
- Night and auto mode overwrite `u_fan_speed` and don't restore it when switched off.
- Night mode takes effect as soon as `u_night` is set (fan to the lowest speed). The device ignores `u_night_start`/`u_night_stop` (firmware 1.9/3.1/2.11), and the cloud doesn't act on them either.
- The device applies `u_time_zone` from each command it receives and falls back to UTC when a command omits it. The integration therefore sends it with every command, and re-sends it when the device clock (condition `time` vs. the cloud's UTC `created_at`) is on the wrong zone, e.g. after an app command.

## CLI

```sh
python3 atmeex.py login        # stores tokens in ~/.config/atmeex/tokens.json
python3 atmeex.py status       # settings vs. actual condition
python3 atmeex.py watch [secs] # log changes to watch.log
python3 atmeex.py get /devices/<id>
```

## License

MIT, see [LICENSE](LICENSE).
