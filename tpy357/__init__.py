"""ThermoPro TP357 Bluetooth Python Library

.. include:: ../README.md
"""
import logging
import asyncio
import struct
import datetime
import functools

from bleak import BleakScanner, BleakClient
from bleak.exc import BleakError

__author__ = """Alex Pacini"""
__email__ = "alexpacini90@gmail.com"
__version__ = "1.1.0"

_LOGGER = logging.getLogger(__name__)
_LOGGER.addHandler(
    logging.NullHandler()
)  # Best practice not to add any handler and use the root handler
_LOGGER.setLevel(
    logging.WARNING
)  # Limit the default logging of the library to a WARNING level


QUERY_MODES = ["day", "week", "year"]
UUID_READ = "00010203-0405-0607-0809-0a0b0c0d2b10"
UUID_WRITE = "00010203-0405-0607-0809-0a0b0c0d2b11"


def repeat_BLE(n=3):
    """Repeat BLE comms on error.

    Parameters
    ----------
    n : int, optional
        The number of retries, by default `n=3`.

    Description
    -----------
    Decorator that repeat the call `n` times on BleakError.
    """

    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except BleakError as e:
                if n > 0:
                    _LOGGER.info(
                        f"Retry connection (remaining {n-1})\n"
                        f"Function name: {f.__name__}"
                    )
                    return repeat_BLE(n=n - 1)(f)(*args, **kwargs)
                else:
                    raise e

        return wrapper

    return decorator


async def scan_tp357(stop_evt: asyncio.Event, queue: asyncio.Queue):
    """Scan for TP357 devices.

    Parameters
    -----------
    stop_evt : `asyncio.Event`
        Setting this event stops the scan for advertising packets.
    queue : `asyncio.Queue`
        Each advertising packets is put into this queue.
    """

    def callback(device, advertising_data):
        if stop_evt.is_set():
            return
        if (
            advertising_data.local_name
            and "TP357 (7216)" in advertising_data.local_name
        ):
            for k, v in advertising_data.manufacturer_data.items():
                raw = struct.pack("<H4s", k, v)
                t_now = datetime.datetime.now()
                temp_100mdC, hum_rh, batt_level = struct.unpack("=hBB", raw[1:5])
                if temp_100mdC > 1024 or hum_rh > 100:
                    continue
                data = dict(
                    time=t_now.isoformat(),
                    address=device.address,
                    rssi=advertising_data.rssi,
                    hum_rh=hum_rh,
                    temp=temp_100mdC / 10,
                    batt_lv=f"{batt_level/2*100:.0f}%",
                )
                queue.put_nowait(data)

    async with BleakScanner(callback):
        await stop_evt.wait()


async def query_tp357(dev, mode: str):
    """Query a TP357 device.

    Parameters
    -----------
    dev : `bleak.backends.device.BLEDevice`
        Bleak device used for the query.
        Can be obtained using `bleak.BleakScanner` 'Easy methods',
        eg. `bleak.BleakScanner.find_device_by_address`.
    mode : `str`
        The mode of query. One of 'day', 'week', 'year'.

    Returns
    --------
    data : `list(dict)
        Data queried from the device.`
    """
    fin_evt = asyncio.Event()
    ret_data = []

    if mode == "day":
        cmd = b"\xa7\x00\x00\x00\x00\x7a"
        td = datetime.timedelta(minutes=1)
        t0 = datetime.datetime.now() - datetime.timedelta(days=1, minutes=-1)
        timespec = "minutes"
    elif mode == "week":
        cmd = b"\xa6\x00\x00\x00\x00\x6a"
        td = datetime.timedelta(hours=1)
        t0 = datetime.datetime.now() - datetime.timedelta(days=7, hours=1)
        timespec = "hours"
    elif mode == "year":
        cmd = b"\xa8\x00\x00\x00\x00\x8a"
        td = datetime.timedelta(hours=1)
        t0 = datetime.datetime.now() - datetime.timedelta(days=365, hours=-1)
        timespec = "hours"
    else:
        raise RuntimeError(f"{mode} is not one of 'day', 'week', 'year'")

    async with BleakClient(dev) as client:

        def callback(sender, data):
            if data[0] == 194:
                fin_evt.set()
                return
            if data[0] != cmd[0]:
                return
            raw = struct.unpack("h", data[1:3])[0]
            # flag = data[3]
            for i in range(5):
                ofs = 4 + i * 3
                t_a = t0 + (5 * (raw - 1) + i) * td
                temp_100mdC = struct.unpack("h", data[ofs : ofs + 2])[0]
                hum_rh = data[ofs + 2]
                if temp_100mdC > 1024 or hum_rh > 100:
                    continue
                ret_data.append(
                    dict(
                        time=t_a.isoformat(timespec=timespec),
                        hum_rh=hum_rh,
                        temp=temp_100mdC / 10,
                    )
                )

        await client.start_notify(UUID_READ, callback)
        await client.write_gatt_char(UUID_WRITE, cmd, response=False)
        await fin_evt.wait()
        await client.stop_notify(UUID_READ)  # Not necessary if I disconnnect

    return ret_data
