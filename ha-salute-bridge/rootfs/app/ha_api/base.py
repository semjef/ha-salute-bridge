import asyncio
import os
from typing import Any, Callable
import logging as log
import requests

from hass_client.exceptions import (
    CannotConnect,
    ConnectionFailed,
    FailedCommand,
    NotConnected,
    NotFoundError,
)
from hass_client.models import Event

from models.exceptions import NotFoundAgainError, ServiceTimeoutError
from .client import HomeAssistantClient


class HAApiClient:
    def __init__(self, options, queue_write, queue_read, devices):
        self.options = options
        self.queue_write = queue_write
        self.queue_read = queue_read
        self.devices = devices

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
            self.ha_api_url = "http://supervisor/core"
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

    async def update(self):
        while True:
            # await self.handle_exception_in_func(self.clock.run)
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
                log.error(exception)
            case NotFoundAgainError():
                log.debug(exception)
            case ServiceTimeoutError():
                log.debug(exception)
            case asyncio.CancelledError():
                log.error("Operation was cancelled")
            case FailedCommand():
                log.error(exception)
            case NotConnected() | CannotConnect() | ConnectionFailed():
                log.error("connection error")
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
                log.exception(exception)

    async def on_events(self, event: Event):
        # log.debug("on_events %s", event)
        if event.event_type != 'state_changed':
            return
        _id = event.data['new_state']['entity_id']
        old_state = event.data['old_state']['state']
        new_state = event.data['new_state']['state']
        dev = self.devices.DB.get(_id, None)
        if dev is not None:
            if dev['enabled']:
                log.debug('HA Event: %s: %s -> %s', _id, old_state, new_state)
                if dev['category'] == 'sensor_temp':
                    self.devices.change_state(_id, 'temperature', float(new_state))
                if new_state == 'on':
                    self.devices.change_state(_id, 'on_off', True)
                    if not (self.devices.DB[_id]['States'].get('button_event', None) is None):
                        self.devices.DB[_id]['States']['button_event'] = 'click'
                else:
                    self.devices.change_state(_id, 'on_off', False)
                    if not (self.devices.DB[_id]['States'].get('button_event', None) is None):
                        self.devices.DB[_id]['States']['button_event'] = 'double_click'
                await self.send_data(self.devices.do_mqtt_json_states_list([_id]))

    async def send_data(self, data):
        await self.queue_write.put({"type": "status", "data": data})

    async def send_conf(self):
        await self.queue_write.put({"type": "conf", "data": self.devices.do_mqtt_json_devices_list()})

    async def queue_processer(self):
        while True:
            if self.client is not None:
                break
            await asyncio.sleep(1)
        while True:
            entity_id = await self.queue_read.get()
            log.debug('Отправляем команду в HA для %s', entity_id)
            data = self.devices.get_ha_entity_data(entity_id)
            req = {
                "domain": data["entity_domain"],
                "service": data["service"],
                "target": {
                    "entity_id": f"{data["entity_domain"]}.{data["entity_name"]}"
                },
                "return_response": False
            }
            if data.get('service_data'):
                req['service_data'] = data['service_data']
            await self.client.send_command("call_service", **req)
            self.queue_read.task_done()

    async def startup_load(self):
        hds = {'Authorization': f'Bearer {self.ha_api_token}', 'content-type': 'application/json'}
        url = f'{self.ha_api_url}/states'
        log.debug('Подключаемся к HA, (ha-api_url: %s)', url)
        cx = 0
        ha_dev = []
        loading = True
        while cx < 10 or loading:
            cx = cx + 1
            try:
                res = requests.get(url, headers=hds)
                if res.status_code == 200:
                    log.info('Запрос устройств из Home Assistant выполнен штатно.')
                    ha_dev = res.json()
                    log.debug(ha_dev)
                    loading = False
                else:
                    log.error('ОШИБКА! Запрос устройств из Home Assistant выполнен некоректно. (%s)', str(res.status_code))
            except:
                log.error('Ошибка подключения к HA. Ждём 5 сек перед повторным подключением.')
                await asyncio.sleep(5)

        for s in ha_dev:
            entity_type = s['entity_id'].split('.')[0]
            dc = s.get('attributes', {}).get('device_class', '')
            fn = s.get('attributes', {}).get('friendly_name', '')
            match entity_type:
                case "switch":
                    log.debug('switch: %s %s', s['entity_id'], fn)
                    self.devices.update(
                        s['entity_id'],
                        {'entity_ha': True, 'entity_type': 'sw', 'friendly_name': fn, 'category': 'relay'}
                    )
                case "light":
                    log.debug('light: %s %s', s['entity_id'], fn)
                    self.devices.update(
                        s['entity_id'],
                        {'entity_ha': True, 'entity_type': 'light', 'friendly_name': fn, 'category': 'light'}
                    )
                    # {'entity_id': 'light.0x54ef441000b86867_l1', 'state': 'on',
                    #  'attributes': {'min_color_temp_kelvin': 2702, 'max_color_temp_kelvin': 6535, 'min_mireds': 153,
                    #                 'max_mireds': 370, 'supported_color_modes': ['color_temp', 'xy'], 'color_mode': 'xy',
                    #                 'brightness': 255, 'color_temp_kelvin': None, 'color_temp': None,
                    #                 'hs_color': [27.458, 23.137], 'rgb_color': [255, 223, 196], 'xy_color': [0.382, 0.354],
                    #                 'friendly_name': 'Подсветка кабинет 1 L1', 'supported_features': 40},
                    #  'last_changed': '2024-12-11T11:59:04.194943+00:00',
                    #  'last_reported': '2024-12-11T11:59:04.194943+00:00',
                    #  'last_updated': '2024-12-11T11:59:04.194943+00:00',
                    #  'context': {'id': '01JETSCGSD599T5JBGZFA0VX00', 'parent_id': None, 'user_id': None}}
                case "script":
                    log.debug('script: %s %s', s['entity_id'], fn)
                    self.devices.update(
                        s['entity_id'],
                        {'entity_ha': True, 'entity_type': 'scr', 'friendly_name': fn, 'category': 'relay'}
                    )
                case "sensor":
                    if dc == 'temperature':
                        log.debug('sensor (temperature): %s %s', s['entity_id'], fn)
                        self.devices.update(
                            s['entity_id'],
                            {'entity_ha': True, 'entity_type': 'sensor_temp', 'friendly_name': fn,
                              'category': 'sensor_temp'}
                        )
                case "input_boolean":
                    log.debug('input_boolean: %s %s', s['entity_id'], fn)
                    self.devices.update(
                        s['entity_id'],
                        {'entity_ha': True, 'entity_type': 'input_boolean', 'friendly_name': fn,
                         'category': 'scenario_button'}
                    )
                case "hvac_radiator":
                    if dc == 'temperature':
                        log.debug('hvac_radiator (temperature): %s %s', s['entity_id'], fn)
                        self.devices.update(
                            s['entity_id'],
                            {'entity_ha': True, 'entity_type': 'hvac_radiator', 'friendly_name': fn,
                             'category': 'hvac_radiator'}
                        )
                case _:
                    log.debug('Неиспользуемый тип: %s',s['entity_id'])
        self.devices.save_DB()
        await self.send_conf()

