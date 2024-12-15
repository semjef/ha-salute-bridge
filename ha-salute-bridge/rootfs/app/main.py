import asyncio
import os
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from const import CATEGORIES_FILENAME, DEVICES_FILENAME
from devices import GetCategory, Devices, DeviceModel, DeviceModelsEnum
from options import load_options
from logger import Logger
from mqtt.base import MqttClient
from ha_api.base import HAApiClient
from web.routes import router

opt = load_options()
Logger.init(opt)

mqtt_queue = asyncio.Queue()
ha_queue = asyncio.Queue()

categories = GetCategory(opt, CATEGORIES_FILENAME)
devices = Devices(categories, DEVICES_FILENAME)

if sys.platform.lower() == "win32" or os.name.lower() == "nt":
    from asyncio import set_event_loop_policy, WindowsSelectorEventLoopPolicy
    set_event_loop_policy(WindowsSelectorEventLoopPolicy())


@asynccontextmanager
async def lifespan(app: FastAPI):
    hac = HAApiClient(opt, queue_write=mqtt_queue, queue_read=ha_queue, devices=devices)
    mqttc = MqttClient(opt, queue_write=ha_queue, queue_read=mqtt_queue, devices=devices)

    await hac.startup_load()

    asyncio.create_task(mqttc.listen())
    asyncio.create_task(mqttc.queue_processer())
    asyncio.create_task(hac.start())
    asyncio.create_task(hac.queue_processer())

    yield {"devices": devices, "mqtt_queue": mqtt_queue, "ha_queue": ha_queue}


fastapi = FastAPI(lifespan=lifespan)

fastapi.mount("/static", StaticFiles(directory="../app/static"), name="static")

fastapi.include_router(router)

uvicorn.run(
    fastapi, host=opt['host'], port=opt['port'], log_level="info"
)