import logging
import sys
import asyncio
from datetime import datetime
import time
import argparse
from pathlib import Path
import contextlib
import sqlite3

import tpy357
from bleak import BleakScanner

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(filename)s:%(lineno)d | "
    "%(name)s | %(funcName)s | %(processName)s:%(threadName)s -> "
    "%(message)s",
    stream=sys.stdout,
    level=logging.WARNING,
)
_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)

# logging.getLogger("tpy357").setLevel(logging.INFO)


@tpy357.repeat_BLE(n=3)
async def read_tp357(address, mode, args):
    import pandas as pd

    pd.options.mode.copy_on_write = True
    import matplotlib.pyplot as plt

    dev = await BleakScanner.find_device_by_address(address, timeout=30)
    data = await asyncio.wait_for(
        tpy357.query_tp357(
            dev=dev,
            mode=mode,
        ),
        args.wait,
    )
    df = pd.DataFrame(data).set_index("time")
    df.index = pd.to_datetime(df.index)
    if df.empty:
        raise ValueError("The returned data is empty: try running it again.")

    if mode == "day":
        fig, axes = plt.subplots(2, 2, layout="constrained", figsize=(12, 12))
        df.plot(y="temp", ax=axes[0, 0])
        df.plot(y="hum_rh", ax=axes[0, 1])
        df_r = df.rolling("30min").mean()
        df_r.plot(y="temp", ax=axes[1, 0])
        df_r.plot(y="hum_rh", ax=axes[1, 1])
    else:
        fig, axes = plt.subplots(2, 1, layout="constrained", figsize=(6, 12))
        df.plot(y="temp", ax=axes[0])
        df.plot(y="hum_rh", ax=axes[1])

    if args.png:
        fp = f"tp357-{address.replace(':', '')}-{mode}-{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
        fig.savefig(fp, dpi=300)
        print(f"Saved {fp}")
    if args.csv:
        fp = f"tp357-{address.replace(':', '')}-{mode}-{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
        df.to_csv(fp)
        print(f"Saved {fp}")
    if args.sqlite:
        fp = Path(args.sqlite)
        sql_last_time = None
        with contextlib.closing(sqlite3.connect(fp)) as conn:
            if conn.execute(
                f'SELECT name FROM sqlite_schema WHERE type="table" AND name="{mode}";'
            ).fetchone():  # mode table exists
                sql_last_time = conn.execute(
                    f'SELECT max(julianday("time")), "time" FROM {mode} '
                    'WHERE "address" IS ?;',
                    (address,),
                ).fetchone()[1]
                if (
                    sql_last_time is not None
                ):  # mode table for this address is not empty
                    # Keep only new samples that are not yet in the db
                    sql_last_time = pd.to_datetime(sql_last_time)
                    df = df.loc[df.index > sql_last_time]
            if df.empty:
                print(
                    f"Nothing additional to append to table '{mode}' on sqlite DB '{fp}' for address '{address}'."
                )
                return
            df.loc[:, "address"] = address
            df.to_sql(mode, conn, if_exists="append")
        if sql_last_time is None:
            print(
                f"Saved to table '{mode}' on sqlite DB '{fp}' for address '{address}'."
            )
        else:
            initial_time = max(min(df.index), sql_last_time)
            print(
                f"Data with time > {initial_time} appended to table '{mode}' on sqlite DB '{fp}' for address '{address}'."
            )


async def tp357_adv(args):
    queue = asyncio.Queue()
    stop_evt = asyncio.Event()

    search_TP357_task = asyncio.create_task(
        tpy357.scan_tp357(stop_evt=stop_evt, queue=queue)
    )

    if args.sqlite:
        fp = Path(args.sqlite)
        conn = sqlite3.connect(fp)
        cur = conn.cursor()
        cur.execute(
            r"CREATE TABLE IF NOT EXISTS adv ("
            r"time TEXT NOT NULL,"
            r"address TEXT NOT NULL,"
            r"rssi REAL NOT NULL,"
            r"hum_rh REAL NOT NULL,"
            r"temp REAL NOT NULL,"
            r"batt_v REAL NOT NULL"
            r");"
        )
        conn.commit()

    if args.wait:
        end_time = time.monotonic() + args.wait
    while not args.wait or (time.monotonic() < end_time):
        ret = await asyncio.wait_for(queue.get(), args.wait)
        print(ret)
        if args.sqlite:
            with conn:
                conn.execute(
                    r"INSERT INTO adv VALUES("
                    r":time, :address, :rssi, :hum_rh, :temp, :batt_v"
                    r");",
                    ret,
                )
    stop_evt.set()
    conn.close()
    await search_TP357_task


def main():
    parser = argparse.ArgumentParser(
        prog="tpy357", description="Query TP357 thermo-hygrometers"
    )
    for mode in tpy357.QUERY_MODES:
        parser.add_argument(
            f"--{mode}",
            metavar="ADDRESS",
            nargs="+",
            help=f"Query '{mode}' data. If no modes are specified, scan for advertising data.",
        )
    parser.add_argument(
        "--csv",
        action="store_true",
        help=f"Option to save queries to a csv file. Can be used with {tpy357.QUERY_MODES}.",
    )
    parser.add_argument(
        "--png",
        action="store_true",
        help=f"Option to plot queries to a png image. Can be used with {tpy357.QUERY_MODES}.",
    )
    parser.add_argument(
        "--sqlite",
        metavar="DBFILE",
        help="When a file path is provided, create or append the queried data to a sqlite database with that name.",
    )
    parser.add_argument(
        "--wait",
        type=float,
        help="Seconds to wait to close the connection. Default to infinite wait (stop with ctrl+c).",
    )
    args = parser.parse_args()

    if not any(vars(args)[mode] for mode in tpy357.QUERY_MODES):
        asyncio.run(tp357_adv(args=args))
        return

    for mode in tpy357.QUERY_MODES:
        if getattr(args, mode):
            for addr in getattr(args, mode):
                print(f"Querying TP357 {addr} with mode '{mode}'")
                asyncio.run(read_tp357(addr, mode, args))


if __name__ == "__main__":
    main()
