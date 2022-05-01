# CPU Temperature Reporter for InfluxDB
Periodically report the current CPU temperature to an InfluxDB,
while gracefully dealing with connection problems and other errors.

## Setup
- `pip install json5 influxdb_client`
- Make sure you have the `sensors` linux utility installed (the debian package is called `lm-sensors`)

## Usage:
- Copy `config_default.jsonc` to `config.jsonc` and enter your InfluxDB settings there
- Run cpu_temps.py (manually, as an @reboot cron job, a systemd service, etc.)
