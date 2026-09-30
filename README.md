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
| Air intake | Fresh air / Mixed / Recirculation |
| AutoNanny, Night mode | Mode switches; turning them off restores the fan speed they overwrote |
| Night mode from / until | Night window |
| CO2, Room temperature, Inlet air temperature, Humidity, Actual fan speed, Water tank empty | Sensors |
| Fan throttled | On when the breezer runs slower than set for over a minute on its own (e.g. with cold inlet air) |
| Online | Cloud connectivity |

## API notes

- `GET /devices` lists devices without live condition; `GET /devices/{id}` includes it.
- `PUT /devices/{id}/params` accepts any subset of: `u_pwr_on`, `u_fan_speed` (0–6 = app 1–7), `u_damp_pos` (0 fresh, 1 mixed, 2 recirculation), `u_temp_room` (°C×10, −1000 = heater off), `u_hum_stg`, `u_auto`, `u_night`, `u_night_start`/`u_night_stop` ("HH:MM"), `u_cool_mode`, `u_time_zone` (hours; can't be reset to null).
- The server answers 200 even for unknown fields.
- Night and auto mode overwrite `u_fan_speed` and don't restore it when switched off.

## CLI

```sh
python3 atmeex.py login        # stores tokens in ~/.config/atmeex/tokens.json
python3 atmeex.py status       # settings vs. actual condition
python3 atmeex.py watch [secs] # log changes to watch.log
python3 atmeex.py get /devices/<id>
```

## License

MIT, see [LICENSE](LICENSE).
