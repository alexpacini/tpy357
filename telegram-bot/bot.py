import logging
import sys
import asyncio
from pprint import pformat
import gc
import io
from pathlib import Path

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, filters

import tpy357
from bleak import BleakScanner
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import tomli

matplotlib.use("agg")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(filename)s:%(lineno)d | "
    "%(name)s | %(funcName)s | %(processName)s:%(threadName)s -> "
    "%(message)s",
    stream=sys.stdout,
    level=logging.WARNING,
)
_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)


BT_LOCK = asyncio.Lock()


async def log_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _LOGGER.info(
        f"""
    log_id
    Chat ID: {update.effective_chat.id}
    from user: {update.effective_user})
        """
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _LOGGER.info(
        f"""
    start
    Chat ID: {update.effective_chat.id}
    from user: {update.effective_user})
        """
    )


@tpy357.repeat_BLE(n=3)
def tp357(mode):
    async def _tp357(update: Update, context: ContextTypes.DEFAULT_TYPE):
        _LOGGER.info(
            f"""
    tp357({mode})
    Chat ID: {update.effective_chat.id}
    from user: {update.effective_user})
            """
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="Reading advertising data..."
        )
        queue = asyncio.Queue()
        stop_evt = asyncio.Event()
        async with BT_LOCK:
            search_TP357_task = asyncio.create_task(
                tpy357.scan_tp357(stop_evt=stop_evt, queue=queue)
            )
            adv = await asyncio.wait_for(queue.get(), 30)
            stop_evt.set()
            await search_TP357_task
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=pformat(adv)
        )

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Searching device {adv['address']}",
        )
        async with BT_LOCK:
            dev = await BleakScanner.find_device_by_address(adv["address"], timeout=30)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Reading data from {dev} with mode='{mode}'",
        )
        async with BT_LOCK:
            data = await asyncio.wait_for(
                tpy357.query_tp357(
                    dev=dev,
                    mode=mode,
                ),
                60,
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

        img = io.BytesIO()
        fig.savefig(img, dpi=300, format="png")
        img.seek(0)

        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=img,
            write_timeout=None,
        )

        plt.close(fig)
        gc.collect()

    return _tp357


async def tp357_adv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _LOGGER.info(
        f"""
    tp357_adv
    Chat ID: {update.effective_chat.id}
    from user: {update.effective_user})
        """
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id, text="Reading advertising data..."
    )

    queue = asyncio.Queue()
    stop_evt = asyncio.Event()
    async with BT_LOCK:
        search_TP357_task = asyncio.create_task(
            tpy357.scan_tp357(stop_evt=stop_evt, queue=queue)
        )
        adv = await asyncio.wait_for(queue.get(), 30)
        stop_evt.set()
        await search_TP357_task
    await context.bot.send_message(chat_id=update.effective_chat.id, text=pformat(adv))


async def rpi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _LOGGER.info(
        f"""
    rpi
    Chat ID: {update.effective_chat.id}
    from user: {update.effective_user})
        """
    )
    proc = await asyncio.create_subprocess_exec(
        "vcgencmd",
        "measure_temp",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await proc.communicate()

    if stdout:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=stdout.decode()
        )
    if stderr:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=stderr.decode()
        )


if __name__ == "__main__":
    conf_file = Path(__file__).parent / "bot.toml"
    CONF = tomli.load(conf_file.open("rb"))

    application = ApplicationBuilder().token(CONF["TOKEN"]).build()

    handlers = []
    # handlers.append(CommandHandler("id", log_id))
    handlers.append(
        CommandHandler("start", start, filters=filters.Chat(chat_id=CONF["USERS"]))
    )
    handlers.append(
        CommandHandler("day", tp357("day"), filters=filters.Chat(chat_id=CONF["USERS"]))
    )
    handlers.append(
        CommandHandler(
            "week", tp357("week"), filters=filters.Chat(chat_id=CONF["USERS"])
        )
    )
    handlers.append(
        CommandHandler(
            "year", tp357("year"), filters=filters.Chat(chat_id=CONF["USERS"])
        )
    )
    handlers.append(
        CommandHandler("adv", tp357_adv, filters=filters.Chat(chat_id=CONF["USERS"]))
    )
    handlers.append(
        CommandHandler("rpi", rpi, filters=filters.Chat(chat_id=CONF["USERS"]))
    )
    application.add_handlers(handlers)

    application.run_polling()
