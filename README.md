# tpy357

tpy357 is an unofficial small cross-platform Python 3 (>3.10) library to interface with ThermoPro TP357 thermo-hygrometers.

The module provides a small API to query the thermometer.
It can query TP357 real-time advertising data, or query daily, weekly, or yearly data stored in the device.
The CLI allows to store the results of the queries in a sqlite database, also incrementally, or exported to png plots or csv files. As an example, a Telegram bot is also provided.

## Install
```bash
python3 -m pip install --upgrade --user tpy357
```
or, using venvs
```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade tpy357
```

Using [`pipx`](https://pipx.pypa.io/stable/)
```bash
pipx install tpy357
```
or even, just run directly with (see below for examples of usage)
```bash
pipx run tpy357
```
See [`pipx`](https://pipx.pypa.io/stable/) documentation for more information.

Be aware that that bluez is required when using Linux. It is generally included in distros with a desktop environment.


### Raspberry Pi
The installation on the RaspberryPi is slightly more involved, as Debian uses [externally managed environments](https://packaging.python.org/en/latest/specifications/externally-managed-environments/).
Using venvs or [`pipx`](https://pipx.pypa.io/stable/) should work without problems, but might use more storage space
with duplicated module installs.
Some additional options are shown below.

#### System Packages with venv
All the dependencies can be installed using `apt`.
This uses the least space and the dependencies are updated with system updates.
```bash
sudo apt update
sudo apt install python3-bleak python3-tomli python3-pandas python3-matplotlib
```
then a venv can be created with access to system modules:
```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python3 -m pip install --upgrade tpy357
```
the installation using apt, also installs other system dependencies as bluez.

#### System Packages with pipx
If not already installed, install [`pipx`](https://pipx.pypa.io/stable/)
```bash
sudo apt update
sudo apt install pipx
sudo apt install python3-bleak python3-tomli python3-pandas python3-matplotlib
```
then can be installed in a automatically managed venv with [`pipx`](https://pipx.pypa.io/stable/)
```bash
pipx install --system-site-packages tpy357
```
To upgrade
```bash
pipx upgrade --system-site-packages tpy357
```
Or again, just use run with access to system site packages (see below for examples of usage)
```bash
pipx run --system-site-packages tpy357 ...
```

## Usage
### API
The API is basically composed of two async functions.

#### scan_tp357
```python
async def scan_tp357(stop_evt: asyncio.Event, queue: asyncio.Queue):
    """Scan for TP357 devices.

    Parameters
    -----------
    stop_evt : `asyncio.Event`
        Setting this event stops the scan for advertising packets.
    queue : `asyncio.Queue`
        Each advertising packets is put into this queue.
    """
```

#### query_tp357
```python
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
    data : `list(dict)`
        Data queried from the device.`
    """
```

### CLI
```bash
usage: tpy357 [-h] [--day ADDRESS [ADDRESS ...]] [--week ADDRESS [ADDRESS ...]] [--year ADDRESS [ADDRESS ...]] [--csv]
              [--png] [--sqlite DBFILE] [--wait WAIT]

Query TP357 thermo-hygrometers

options:
  -h, --help            show this help message and exit
  --day ADDRESS [ADDRESS ...]
                        Query 'day' data. If no modes are specified, scan for advertising data.
  --week ADDRESS [ADDRESS ...]
                        Query 'week' data. If no modes are specified, scan for advertising data.
  --year ADDRESS [ADDRESS ...]
                        Query 'year' data. If no modes are specified, scan for advertising data.
  --csv                 Option to save queries to a csv file. Can be used with ['day', 'week', 'year'].
  --png                 Option to plot queries to a png image. Can be used with ['day', 'week', 'year'].
  --sqlite DBFILE       When a file path is provided, create or append the queried data to a sqlite database with that
                        name.
  --wait WAIT           Seconds to wait to close the connection. Default to infinite wait (stop with ctrl+c).
```

if venvs are used, it either needs the environment to be activated first, eg:
```bash
source .venv/bin/activate
tpy357 ...
```
or a full path to the python executable inside the venv should be provided, eg:
```bash
.venv/bin/python3 -m tpy357 ...
```

#### Examples
Query advertising data and print it to the terminal (Stop with Ctrl-C). Useful to retrieve the address.
```bash
tpy357 --wait 120 --sqlite tp357.sqlite
```

Query advertising data for 120 seconds and store the data to a sqlite database with filename `tp357.sqlite` in the current directory.
```bash
tpy357 --wait 120 --sqlite tp357.sqlite
```

Query daily and yearly device stored data, with a time limit of 60 seconds for each connection,
and store the data in the current directory to a sqlite database with filename `tp357.sqlite`, a csv file, and a png image.
```bash
tpy357 --day AD:DR:ES:SX:XX:XX --year AD:DR:ES:SX:XX:XX --wait 60 --sqlite tp357.sqlite --csv --png
```

Query daily data from two devices, with a time limit of 60 seconds for each connection,
and store the data in the current directory to a sqlite database with filename `tp357.sqlite`.
```bash
tpy357 --day AD:DR:ES:S1:XX:XX AD:DR:ES:S2:XX:XX --wait 60 --sqlite tp357.sqlite
```

### Telegram Bot
The script `bot.py` is provided in the telegram-bot folder, with an example simple configuration toml file.
The toml file contains the token used to authenticate on Telegram (which is provided by BotFather), and
the list of users to whom the bot will respond.
If the `log_id` handler is enabled, the `/id` commands prints the user data on the terminal, so that it can be easily copied into the toml file.
The example bot uses long polling, so that port-forwarding is not required, for simplicity.

The dependencies can be installed using the `requirements.txt` provided in the same `telegram-bot` folder,
with `python3 -m pip install --upgrade -r requirements.txt`.
Be aware of using the correct python3 executable or to activate the venv, also for the installation.

## Similar projects
There are other similar projects that can be found over the web:

* https://github.com/pasky/tp357 uses GLib and I believe is mainly for Linux (which is fair...).
* https://decoder.theengs.io/ only provides advertising data and was also failing to install on Windows (which is also fair...).
* https://www.home-assistant.io/integrations/thermopro/ Home Assistant integration, obviously requires Home Assistant to run, and captures advertising data only.

## License
This project is released under GNU GPLv3, unless agreed or expressed differently.
tpy357 is provided AS-IS, without any warranty or liability.

This project is not related or endorsed with ThermoPro brand, and the protocol was mainly found
by reverse-engineering through "packet sniffing" and/or resources publicly available.

## Changelog
### v1.1.0 (023.02.2024)
* Fix battery level indication for advertising packets.
### v1.0.0 (04.02.2024)
* First release.