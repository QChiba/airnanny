"""Constants for the Atmeex AirNanny integration."""
from datetime import timedelta

DOMAIN = "atmeex"
API_BASE = "https://api.iot.atmeex.com"

CONF_LOGIN = "login"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"

SCAN_INTERVAL = timedelta(seconds=30)
# access tokens live 3 hours; refresh this long before they expire
TOKEN_REFRESH_MARGIN_SECONDS = 300

# u_temp_room value that switches the heater off
HEATER_OFF = -1000
# u_damp_pos values
DAMPER_OPEN = 0
DAMPER_CLOSED = 2
# the device reports fan speed 0..6, the app shows 1..7
FAN_SPEEDS = 7
# how long the actual fan speed must stay below the set one to count as throttled
THROTTLE_GRACE_SECONDS = 60
# heater target used when the heater is switched on with no remembered target
DEFAULT_HEAT_TARGET = 20.0
HUMIDIFIER_STAGES = 3


def temp_to_api(celsius: float) -> int:
    """°C to the API's °C*10, rounded to 0.5° steps."""
    return int(round(celsius * 2) * 5)
