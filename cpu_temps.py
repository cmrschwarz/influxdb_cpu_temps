#!/usr/bin/env python3

# CPU temperature logger
# Reports temp to InfluxDB server
# Linux version
# https://mansfield-devine.com/speculatrix/2021/08/network-monitoring-2-logging-cpu-temps-with-influxdb-and-grafana/
# https://pypi.org/project/influxdb-client/#connect-to-influxdb-cloud

import os
import sys
from urllib3.exceptions import HTTPError
import random
import datetime
from socket import gethostname
import subprocess
import json5
import time
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.exceptions import InfluxDBError
from influxdb_client.client.write_api import SYNCHRONOUS

log_file = None

def time_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S ")

def log(message):
    message = time_str() + message + "\n"
    if log_file is None:
        sys.stderr.write(message)
    else:
        with open(log_file, "a+") as log:
            log.write(message)


# load and parse config
log_file_path = os.path.join(os.path.dirname(__file__), "config.jsonc")
try:
    with open(log_file_path) as cf:
        config = json5.load(cf)

    log_file = config["log_file"]
    server_name = config["server_name"]
    if server_name is None:
        server_name = gethostname()
    influx_url = config["influx_url"]
    influx_org = config["influx_org"]
    influx_token = config["influx_token"]
    influx_bucket = config["influx_bucket"]
    influx_temp_field = config["influx_temp_field"]
    influx_server_name_field = config["influx_server_name_field"]
    debug_print = bool(config["debug_print"])

    interval = float(config["interval"])
    back_off_max_interval = float(config["back_off_max_interval"])
    temp_access_path = config["temp_access_path"]
except ValueError as ex:
    log(f"failed to parse config entry: '{str(ex)}'")
except KeyError as ex:
    log(f"missing config entry: '{str(ex)}'")
except OSError as ex:
    log(f"failed to open config at {log_file_path}: {str(ex)}")

# returns the time in seconds for which it successfully ran
def report_cpu_temps() -> float:
    start = datetime.datetime.now()
    last_report_time = start
    try:
        # connect to influxdb
        influx_client = InfluxDBClient(
            url=influx_url,
            org=influx_org,
            token=influx_token,
            bucket=influx_bucket
        )
        write_api = influx_client.write_api(write_options=SYNCHRONOUS)
    except (InfluxDBError, HTTPError) as ex:
        log(f"influxdb connection failed: {str(ex)}")
        return (last_report_time - start).total_seconds()

    while True:
        try:
            # aquire data
            cmd = 'sensors -j'
            output = subprocess.run(cmd, shell=True, capture_output=True)
            stdout = output.stdout.decode("utf-8")
            result = json5.loads(stdout)
            for apc in temp_access_path:
                result = result[apc]
            result = float(result)
        except (OSError, KeyError, ValueError) as ex:
            log(f"failed to read sensor data: {str(ex)}")
            return (last_report_time - start).total_seconds()

        p = Point("cpu_temp").tag("server", server_name).field("temp", result)
        # wait for the current interval to elapse
        if last_report_time != start:
            sleep_time = (
                interval -
                (datetime.datetime.now() - last_report_time).total_seconds()
            )
            time.sleep(max(0, sleep_time))
        last_report_time = datetime.datetime.now()
        try:
            # write to influx db
            write_api.write(bucket=influx_bucket, record=p)
        except (InfluxDBError, HTTPError) as ex:
            log(f"failed to write sensor data to influxdb: {str(ex)}")
            return (last_report_time - start).total_seconds()
        if debug_print:
            print(f"{time_str()}: {server_name} temp: {result} °C")


# run
backoff_skip = 2.0
while True:
    runtime = report_cpu_temps()
    if runtime > backoff_skip * interval:
        backoff_skip = 2.0
    else:
        backoff_skip = backoff_skip ** random.uniform(1, 2)
    bt = backoff_skip * interval
    log(f"backoff time: {bt:.3f} seconds")
    time.sleep(bt)
