import asyncio
import logging
import os
from typing import Any, Callable

import requests
from hass_client.exceptions import (
    CannotConnect,
    ConnectionFailed,
    FailedCommand,
    NotConnected,
    NotFoundError,
)
from hass_client.models import Event

from devices import Devices, DeviceModel, DeviceModelsEnum, LightAttrsEnum, ButtonAttrsEnum, SensorAttrsEnum
from models.exceptions import NotFoundAgainError, ServiceTimeoutError
from .client import HomeAssistantClient


class HAApiClient:
    def __init__(self, options, queue_write, queue_read, devices):
        self.options = options
        self.queue_write = queue_write
        self.queue_read = queue_read
        self.devices: Devices = devices

        self.connection_task: asyncio.Task | None = None
        self.update_task: asyncio.Task | None = None
        self.loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        self.loop.set_exception_handler(self.handle_exception_in_loop)

        if ha_api_url := options.get("ha_api_url"):
            ha_api_url = ha_api_url.removesuffix('/')
            self.ha_api_url = ha_api_url + '/api'
            ha_api_url = ha_api_url.split('://', 1)[1]
            self.ha_ws_url = f"ws://{ha_api_url}/api/websocket"
            self.ha_api_token = options.get("ha_api_token")
        else:
            self.ha_api_url = "http://supervisor/core/api"
            self.ha_ws_url = "ws://supervisor/core/websocket"
            self.ha_api_token = os.getenv("SUPERVISOR_TOKEN")

        self.client = HomeAssistantClient(self.ha_ws_url, self.ha_api_token)
        self.client.register_on_connection(self.on_connection)

    async def start(self):
        """Handle application start."""

        await self.client.connect()

    async def on_connection(self):
        async def on_event(event: Event):
            await self.handle_exception_in_func(self.on_events, event)

        await self.handle_exception_in_func(
            self.client.subscribe_events,
            on_event,
        )

        if (
            self.update_task is None
            or self.update_task.done()
            or self.update_task.cancelled()
        ):
            self.update_task = self.loop.create_task(self.update())

    @staticmethod
    async def update():
        while True:
            await asyncio.sleep(0.25)

    def handle_exception_in_loop(
        self, loop: asyncio.AbstractEventLoop, context: dict[str, Any]
    ):
        """Handle an exception in the event loop."""

        exception = context.get("exception")

        if exception is None:
            return

        self.handle_exception(exception)

    async def handle_exception_in_func(self, func: Callable, *args, **kwargs):
        try:
            await func(*args, **kwargs)
        except Exception as ex:
            self.handle_exception(ex)

    def handle_exception(self, exception: Exception):
        """Handle an exception in the event loop."""

        match exception:
            case NotFoundError():
                logging.error(exception)
            case NotFoundAgainError():
                logging.debug(exception)
            case ServiceTimeoutError():
                logging.debug(exception)
            case asyncio.CancelledError():
                logging.error("Operation was cancelled")
            case FailedCommand():
                logging.error(exception)
            case NotConnected() | CannotConnect() | ConnectionFailed():
                logging.error("connection error")
                if (
                    self.update_task is not None
                    and not self.update_task.done()
                    and not self.update_task.cancelled()
                ):
                    self.update_task.cancel()

                if self.connection_task is not None and not self.connection_task.done():
                    return
                self.connection_task = self.loop.create_task(
                    self.client.connect()
                )
            case Exception():
                logging.exception(exception)

    async def on_events(self, event: Event):
        try:
            # logging.debug("on_events %s", event)
            if event.event_type != 'state_changed':
                return
            entity_id = event.data['new_state']['entity_id']
            old_state = event.data.get('old_state', {}).get('state')
            new_state = event.data.get('new_state', {}).get('state', "unavailable")
            attrs = event.data['new_state']['attributes']
            device = self.devices[entity_id]
            if device is None or not device.enabled:
                return
            logging.debug('HA Event: %s: %s -> %s', entity_id, old_state, new_state)
            device.state = new_state
            device.attributes = {}
            if 'brightness' in attrs:
                device.attributes["brightness"] = attrs["brightness"]
            if 'hvac_modes' in attrs:
                device.attributes["hvac_modes"] = attrs["hvac_modes"]
            if 'preset_modes' in attrs:
                device.attributes["preset_modes"] = attrs["preset_modes"]
            if 'current_temperature' in attrs:
                device.attributes["current_temperature"] = attrs["current_temperature"]
            if 'temperature' in attrs:
                device.attributes["temperature"] = attrs["temperature"]
            if 'percentage' in attrs:
                device.attributes["percentage"] = attrs["percentage"]
            if 'percentage_step' in attrs:
                device.attributes["percentage_step"] = attrs["percentage_step"]
            self.devices.update(entity_id, device)
            await self.send_data(entity_id)
        except:
            logging.exception("HA Event failed %s", event.data)

    async def send_data(self, data):
        await self.queue_write.put({"type": "status", "data": data})

    async def send_conf(self):
        await self.queue_write.put({"type": "conf"})

    async def queue_processer(self):
        while True:
            if self.client is not None:
                break
            await asyncio.sleep(1)
        while True:
            entity_id = await self.queue_read.get()
            try:
                logging.debug('Отправляем команду в HA для %s', entity_id)
                device = self.devices[entity_id]
                match device.category:
                    case 'light':
                        data = self.process_light(device)
                    case 'switch':
                        data = self.process_switch(device)
                    case 'input_boolean':
                        data = self.process_switch(device)
                    case 'script':
                        data = self.process_switch(device)
                    case _:
                        # Не обрабатываем ничего, кроме этих типов
                        continue
                req = {
                    "domain": data["entity_domain"],
                    "service": data["service"],
                    "target": {
                        "entity_id": f"{data['entity_domain']}.{data['entity_name']}"
                    },
                    "return_response": False
                }
                if data.get('service_data'):
                    req['service_data'] = data['service_data']
                logging.debug('Отправляем команду в HA для %s %s', entity_id, data)
                await self.client.send_command("call_service", **req)
            except:
                logging.error('Ошибка при обработке %s', entity_id)
            self.queue_read.task_done()

    @staticmethod
    def process_light(device):
        service = 'turn_on' if device.state == "on" else 'turn_off'
        data = {
            "entity_domain": device.category,
            "entity_name": device.entity_id,
            "service": service
        }

        if (
                device.state == "on" and
                device.attributes and
                "brightness" in device.attributes and
                device.attributes["brightness"] is not None
        ):
            data['service_data'] = {"brightness": device.attributes["brightness"]}
        return data

    @staticmethod
    def process_switch(device):
        service = 'turn_on' if device.state == "on" else 'turn_off'
        data = {
            "entity_domain": device.category,
            "entity_name": device.entity_id,
            "service": service
        }
        return data

    async def startup_load(self):
        hds = {'Authorization': f'Bearer {self.ha_api_token}', 'content-type': 'application/json'}
        url = f'{self.ha_api_url}/states'
        logging.debug('Подключаемся к HA, (ha-api_url: %s)', url)
        cx = 0
        ha_dev = []
        loading = True
        while cx < 10 and loading:
            cx = cx + 1
            try:
                res = requests.get(url, headers=hds)
                if res.status_code == 200:
                    logging.info('Запрос устройств из Home Assistant выполнен штатно.')
                    ha_dev = res.json()
                    logging.debug(ha_dev)
                    loading = False
                else:
                    logging.error('ОШИБКА! Запрос устройств из Home Assistant выполнен некоректно. (%s)', str(res.status_code))
            except:
                logging.error('Ошибка подключения к HA. Ждём 5 сек перед повторным подключением.')
                await asyncio.sleep(5)

        for s in ha_dev:
            category = s['entity_id'].split('.')[0]
            entity_id = s['entity_id'].split('.')[1]
            attributes = s.get('attributes', {})
            dc = attributes.get('device_class', '')
            fn = attributes.get('friendly_name', '')
            state = s.get('state', "")
            match category:
                case "switch":
                    logging.debug('switch: %s %s', s['entity_id'], fn)
                    entity = DeviceModel(
                        entity_id=entity_id,
                        category=category,
                        name=fn,
                        state=state,
                        model=DeviceModelsEnum.relay
                    )
                    self.devices.update(s['entity_id'], entity)
                case "light":
                    logging.debug('light: %s %s', s['entity_id'], fn)
                    entity = DeviceModel(
                        entity_id=entity_id,
                        category=category,
                        name=fn,
                        state=state,
                        # model=DeviceModelsEnum.light
                    )
                    if "brightness" in attributes:
                        entity.attributes = {"brightness": attributes["brightness"]}
                    self.devices.update(s['entity_id'], entity)
                case "script":
                    logging.debug('script: %s %s', s['entity_id'], fn)
                    entity = DeviceModel(
                        entity_id=entity_id,
                        category=category,
                        name=fn,
                        state=state,
                        model=DeviceModelsEnum.relay
                    )
                    self.devices.update(s['entity_id'], entity)
                case "sensor":
                    if dc == 'temperature':
                        logging.debug('sensor (temperature): %s %s', s['entity_id'], fn)
                        entity = DeviceModel(
                            entity_id=entity_id,
                            category=category,
                            name=fn,
                            state=state,
                            model=DeviceModelsEnum.sensor_temp,
                            features=[SensorAttrsEnum.temperature]
                        )
                        self.devices.update(s['entity_id'], entity)
                case "input_boolean":
                    logging.debug('input_boolean: %s %s', s['entity_id'], fn)
                    entity = DeviceModel(
                        entity_id=entity_id,
                        category=category,
                        name=fn,
                        state=state,
                        model=DeviceModelsEnum.scenario_button,
                        features=[ButtonAttrsEnum.button_event]
                    )
                    self.devices.update(s['entity_id'], entity)
                case "climate":
                    logging.debug('climate: %s %s', s['entity_id'], fn)
                    # entity = DeviceModel(
                    #     entity_id=entity_id,
                    #     category=category,
                    #     name=fn,
                    #     state=state
                    # )
                    # self.devices.update(s['entity_id'], entity)
                case _:
                    logging.debug('Неиспользуемый тип: %s',s['entity_id'])
        self.devices.save()
        await self.send_conf()

