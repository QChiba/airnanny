#!/usr/bin/env python3
"""Read-only diagnostics for AirNanny/Atmeex breezers via the Atmeex cloud API.

Usage:
  python3 atmeex.py login            # interactive: email+password or phone+SMS
  python3 atmeex.py status           # dump settings + current condition of each device
  python3 atmeex.py watch [secs]     # poll forever, log changes to watch.log
  python3 atmeex.py get <path>       # raw GET, e.g. /devices/123
"""
import getpass
import json
import os
import sys
import urllib.error
import urllib.request

BASE = "https://api.iot.atmeex.com"
HEADERS = {"accept": "application/json", "user-agent": "okhttp/3.14.9",
           "content-type": "application/json"}
TOKENS = os.path.expanduser("~/.config/atmeex/tokens.json")

DAMPER = {0: "open (fresh air)", 1: "mixed", 2: "closed (recirculation)"}


def http(method, path, body=None, token=None):
    headers = dict(HEADERS)
    if token:
        headers["authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")


def save_tokens(data):
    os.makedirs(os.path.dirname(TOKENS), exist_ok=True)
    fd = os.open(TOKENS, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"access_token": data["access_token"],
                   "refresh_token": data["refresh_token"]}, f)


def login():
    choice = input("Sign in with (e)mail or (p)hone? ").strip().lower()
    if choice.startswith("p"):
        phone = input("Phone (e.g. +79991234567): ").strip()
        status, resp = http("POST", "/auth/signup", {"grant_type": "phone_code", "phone": phone})
        if status >= 300:
            sys.exit(f"SMS request failed: {status} {resp}")
        code = input("SMS code: ").strip()
        body = {"grant_type": "phone_code", "phone": phone, "phone_code": code}
    else:
        email = input("Email: ").strip()
        body = {"grant_type": "basic", "email": email, "password": getpass.getpass("Password: ")}
    status, resp = http("POST", "/auth/signin", body)
    if status >= 300:
        sys.exit(f"Login failed: {status} {resp}")
    save_tokens(resp)
    print(f"OK, tokens saved to {TOKENS}")


def authed_get(path):
    try:
        with open(TOKENS) as f:
            tok = json.load(f)
    except FileNotFoundError:
        sys.exit("Not logged in. Run: python3 atmeex.py login")
    status, resp = http("GET", path, token=tok["access_token"])
    if status == 401:
        status, new = http("POST", "/auth/signin",
                           {"grant_type": "refresh_token", "refresh_token": tok["refresh_token"]})
        if status >= 300:
            sys.exit("Session expired. Run: python3 atmeex.py login")
        save_tokens(new)
        status, resp = http("GET", path, token=new["access_token"])
    if status >= 300:
        sys.exit(f"GET {path} failed: {status} {resp}")
    return resp


def temp(v):
    return "off" if v in (None, -1000) else f"{v / 10:.1f}°C"


def devices():
    # /devices omits "condition"; the per-device endpoint includes it
    return [authed_get(f"/devices/{d['id']}") for d in authed_get("/devices")]


def watch(interval=60, logfile=os.path.expanduser("~/develop/airnanny/watch.log")):
    """Poll forever; log every change of settings (commands) or condition (device state)."""
    import time
    last = {}
    while True:
        try:
            for d in devices():
                s, c = d.get("settings") or {}, d.get("condition") or {}
                snap = {"online": d.get("online"),
                        **{k: s.get(k) for k in ("u_pwr_on", "u_fan_speed", "u_damp_pos", "u_temp_room",
                                                 "u_hum_stg", "u_auto", "u_night", "u_cool_mode")},
                        **{k: c.get(k) for k in ("pwr_on", "fan_speed", "damp_pos", "hum_stg", "no_water")}}
                env = {k: c.get(k) for k in ("temp_in", "temp_room", "hum_room", "co2_ppm")}
                prev = last.get(d["id"])
                if prev != snap:
                    diff = snap if prev is None else {k: f"{prev[k]} -> {v}" for k, v in snap.items() if prev[k] != v}
                    mismatch = [k for k in ("pwr_on", "fan_speed", "damp_pos")
                                if c.get(k) is not None and int(c[k]) != int(s.get("u_" + k) or 0)]
                    line = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "dev_time": c.get("time"),
                            "changed": diff, "env": env, "updated_at": d.get("updated_at"),
                            "DEVICE_OVERRIDES_SETTINGS": mismatch or None}
                    with open(logfile, "a") as f:
                        f.write(json.dumps(line, ensure_ascii=False) + "\n")
                    last[d["id"]] = snap
        except (Exception, SystemExit) as e:
            with open(logfile, "a") as f:
                f.write(json.dumps({"t": time.strftime("%Y-%m-%d %H:%M:%S"), "error": str(e)}) + "\n")
        time.sleep(interval)


def status():
    for d in devices():
        s, c = d.get("settings") or {}, d.get("condition") or {}
        print(f"=== {d.get('name')} (id {d.get('id')}, model {d.get('model')}, fw {d.get('fw_ver')}) ===")
        print(f"  MAC {d.get('mac')}  online={d.get('online')}")
        print("  -- settings (what you asked for) --")
        print(f"  power={s.get('u_pwr_on')} fan_speed={s.get('u_fan_speed')} "
              f"damper={DAMPER.get(s.get('u_damp_pos'), s.get('u_damp_pos'))} "
              f"heat_target={temp(s.get('u_temp_room'))} humidify_stage={s.get('u_hum_stg')}")
        print(f"  AUTO={s.get('u_auto')}  NIGHT={s.get('u_night')} "
              f"({s.get('u_night_start')}–{s.get('u_night_stop')})  cool_mode={s.get('u_cool_mode')} "
              f"tz={s.get('u_time_zone')}")
        print("  -- condition (what the device is actually doing) --")
        print(f"  at {c.get('time')}: power={c.get('pwr_on')} fan_speed={c.get('fan_speed')} "
              f"damper={DAMPER.get(c.get('damp_pos'), c.get('damp_pos'))}")
        print(f"  outside/inlet={temp(c.get('temp_in'))} room={temp(c.get('temp_room'))} "
              f"hum={c.get('hum_room')}% co2={c.get('co2_ppm')}ppm no_water={c.get('no_water')}")
        print("  -- raw --")
        print(json.dumps(d, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "login":
        login()
    elif cmd == "status":
        status()
    elif cmd == "watch":
        watch(int(sys.argv[2]) if len(sys.argv) > 2 else 60)
    elif cmd == "get" and len(sys.argv) > 2:
        print(json.dumps(authed_get(sys.argv[2]), ensure_ascii=False, indent=2))
    else:
        sys.exit(__doc__)
