import asyncio
import os
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from const import CATEGORIES_FILENAME, DEVICES_FILENAME
from devices import Devices, DeviceModel, DeviceModelsEnum
from options import load_options
from logger import Logger
from salute.base import SaluteClient
from ha_api.base import HAApiClient
from web.routes import router

opt = load_options()
Logger.init(opt)

mqtt_queue = asyncio.Queue()
ha_queue = asyncio.Queue()

devices = Devices(DEVICES_FILENAME)

if sys.platform.lower() == "win32" or os.name.lower() == "nt":
    from asyncio import set_event_loop_policy, WindowsSelectorEventLoopPolicy
    set_event_loop_policy(WindowsSelectorEventLoopPolicy())


@asynccontextmanager
async def lifespan(app: FastAPI):
    ha_client = HAApiClient(opt, queue_write=mqtt_queue, queue_read=ha_queue, devices=devices)
    salute_client = SaluteClient(
        opt, queue_write=ha_queue, queue_read=mqtt_queue, devices=devices, categories_file=CATEGORIES_FILENAME
    )

    await ha_client.startup_load()

    asyncio.create_task(salute_client.listen())
    asyncio.create_task(salute_client.queue_processer())
    asyncio.create_task(ha_client.start())
    asyncio.create_task(ha_client.queue_processer())

    yield {"devices": devices, "mqtt_queue": mqtt_queue, "ha_queue": ha_queue}


fastapi = FastAPI(lifespan=lifespan)

fastapi.mount("/static", StaticFiles(directory="../app/static"), name="static")

fastapi.include_router(router)

uvicorn.run(
    fastapi, host=opt['host'], port=opt['port'], log_level="info"
)