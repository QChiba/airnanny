# airnanny

Home Assistant integration for Atmeex AirNanny breezers (tested with an A7), plus a small CLI for the Atmeex cloud API.

The breezer has no local API: it only keeps a connection to `api.iot.atmeex.com`, so everything goes through the cloud.

## Home Assistant integration

`custom_components/atmeex` works without HACS. To install, copy it into HA's `custom_components` and restart HA. Then add **Atmeex AirNanny** under Settings → Devices & services and log in with email+password or phone+SMS.

Deploying to the Synology HA container (the NAS has no SFTP, so `scp` doesn't work):

```sh
cd custom_components && tar cf - atmeex | ssh synology \
  'tar xf - -C /volume1/docker/smarthome/homeassistant/config/custom_components && docker restart homeassistant'
```

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
