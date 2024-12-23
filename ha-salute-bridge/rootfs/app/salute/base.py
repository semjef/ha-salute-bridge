import asyncio
import json
import logging
import os
import ssl

import aiomqtt
import requests

from devices import Devices, DeviceModelsEnum, LightAttrsEnum, ButtonAttrsEnum, SensorAttrsEnum
from options import options_change
from utils import json_read, json_write


class SaluteClient:
    def __init__(self, options, queue_write, queue_read, devices: Devices, categories_file):
        self.options = options
        self.queue_write = queue_write
        self.queue_read = queue_read
        self.devices = devices

        self.categories_file = categories_file
        self.categories = {}

        self.client = None
        self.sber_root_topic = f"sberdevices/v1/{options['sd_mqtt_login']}"
        self.stdown = f"{self.sber_root_topic}/down"

        self.load_categories()

    async def listen(self):
        client = aiomqtt.Client(
            hostname=self.options['sd_mqtt_broker'],
            port=self.options['sd_mqtt_broker_port'],
            username=self.options['sd_mqtt_login'],
            password=self.options['sd_mqtt_password'],
            tls_params=aiomqtt.TLSParameters(
                certfile=None,
                keyfile=None,
                cert_reqs=ssl.CERT_NONE,
                tls_version=None
            ),
            tls_insecure=True
        )
        interval = 5  # Seconds
        while True:
            try:
                async with client:
                    self.client = client
                    await client.subscribe(f"{self.stdown}/#")
                    await client.subscribe("sberdevices/v1/__config")
                    async for message in client.messages:
                        try:
                            if message.topic.matches(f"sberdevices/v1/__config"):
                                self.on_global_conf(message)
                            elif message.topic.matches(f"{self.stdown}/errors"):
                                self.on_errors(message)
                            elif message.topic.matches(f"{self.stdown}/commands"):
                                await self.on_message_cmd(message)
                            elif message.topic.matches(f"{self.stdown}/status_request"):
                                await self.on_message_stat(message)
                            elif message.topic.matches(f"{self.stdown}/config_request"):
                                self.on_message_conf(message)
                            else:
                                self.on_message(message)
                        except UnicodeDecodeError:
                            logging.warning(f"bad message; skip %s", message.payload)
            except aiomqtt.MqttError:
                logging.warning(f"Connection lost; Reconnecting in {interval} seconds ...")
                await asyncio.sleep(interval)

    def on_message(self, msg):
        logging.debug("on_message %s %s %s", msg.topic, msg.qos, msg.payload)

    async def send_status(self, data):
        logging.debug("send_status:%s", data)
        await self.client.publish(f"{self.sber_root_topic}/up/status", data)

    async def send_config(self, data):
        logging.debug("send_config:%s", data)
        await self.client.publish(f"{self.sber_root_topic}/up/config", data)

    def on_errors(self, msg):
        logging.info("Sber MQTT Errors: %s %s %s", msg.topic, msg.qos, msg.payload)

    async def on_message_cmd(self, msg):
        data = json.loads(msg.payload)
        # Command: {'devices': {'Relay_03': {'states': [{'key': 'on_off', 'value': {'type': 'BOOL'}}]}}}
        logging.info("Sber MQTT Command: %s", data)
        for entity_id, v in data['devices'].items():
            device = self.devices[entity_id]
            if device is None:
                continue
            for state in v['states']:
                val_type = state['value'].get('type', '')
                val = ''
                match val_type:
                    case 'BOOL':
                        val = state['value'].get('bool_value', False)
                    case 'INTEGER':
                        val = int(state['value'].get('integer_value', 0))
                    case 'ENUM':
                        val = state['value'].get('enum_value', '')
                match state['key']:
                    case 'on_off':
                        device.state = "on" if val else "off"
                    case 'light_brightness':
                        val = round(val / 10 * 2.55)  # приводим из 50-1000 к диапозону 1-255
                        device.attributes["brightness"] = val
                    case 'button_event':
                        device.state = "on" if val == "click" else "off"
            self.devices.update(entity_id, device)
            await self.send_data(entity_id)
            # await self.send_status(self.devices.do_mqtt_json_states_list([_id]))
        # log(DevicesDB.mqtt_json_states_list)

    async def on_message_stat(self, msg):
        data = json.loads(msg.payload).get('devices', [])
        logging.info("GetStatus: %s", msg.payload)
        await self.send_status(self.get_salute_states_list(data))
        # log.debug("Answer: " + self.devices.mqtt_json_states_list)

    def on_message_conf(self, msg):
        logging.info("Config: %s %s %s", msg.topic, msg.qos, msg.payload)

    def on_global_conf(self, msg):
        data = json.loads(msg.payload)
        options_change(self.options, 'sd_http_api_endpoint', data.get('http_api_endpoint', ''))

    async def send_data(self, data):
        await self.queue_write.put(data)

    def get_salute_devices_list(self):
        manufacturer = 'HA SaluteBridge'
        devices = [{
            "id": "root",
            "name": "HA Bridge hub",
            'model': {
                'id': 'ID_root_hub',
                'manufacturer': manufacturer,
                'model': 'SBHub',
                'description': "HA SaluteBridge HUB",
                'category': 'hub',
                'features': ['online']
            }
        }]
        for entity_id, device in self.devices:
            if not device.enabled:
                continue
            data = {
                'id': entity_id,
                'name': device.name,
                'model_id': ''
            }
            if device.model is None:
                match device.category:
                    case "light":
                        device.model = DeviceModelsEnum.light
                    case _:
                        continue
            category = self.categories.get(device.model)
            features = []
            for ft in category:
                if ft.get('required', False):
                    features.append(ft['name'])
                elif (
                    ft['name'] == 'light_brightness' and
                    device.features and
                    LightAttrsEnum.brightness in device.features
                ):
                    features.append(ft['name'])
                elif device.features and ft['name'] in device.features:
                    features.append(ft['name'])
                # Будем выдавать список из доступных фич для каждого типа в вебе и
                # юзер сам будет включать их для каждого элемента
            data['model'] = {
                'id': f'ID_{entity_id}',
                'manufacturer': manufacturer,
                'model': 'Model_' + device.model,
                'category': device.model,
                'features': features
            }
            devices.append(data)
        return json.dumps({'devices': devices}, ensure_ascii=False, sort_keys=True)

    def get_salute_states_list(self, entitys: list | None = None):
        devices = {}
        if not entitys:
            entitys = self.devices.keys()
        for entity_id in entitys:
            device = self.devices[entity_id]
            if device is None or not device.enabled:
                continue
            features = self.get_features(device)
            devices[entity_id] = {'states': features}
        return json.dumps({'devices': devices}, ensure_ascii=False, sort_keys=True)

    def get_features(self, device):
        category = self.categories.get(device.model)
        features = []
        for ft in category:
            if ft.get('required'):
                if ft['name'] == "online":
                    features.append(self.get_state_value("online", "BOOL", device.state != "unavailable"))
                elif ft['name'] == "on_off":
                    features.append(self.get_state_value("on_off", "BOOL", device.state == "on"))
        match device.category:
            case 'light':
                if device.features:
                    if "brightness" in device.features:
                        val = device.attributes.get("brightness")
                        if val is not None:  # Включено, но нету - не передаём
                            val = round(val / 2.55 * 10)  # приводим из 1-255 к диапозону 50-1000
                            if val < 50:
                                val = 50
                            if val > 1000:
                                val = 1000
                            features.append(self.get_state_value("light_brightness", "INTEGER", val))
            case 'input_boolean':
                if device.features:
                    if ButtonAttrsEnum.button_event in device.features:
                        val = "click" if device.state == "on" else "double_click"
                        features.append(self.get_state_value("button_event", "ENUM", val))
            case 'sensor':
                if device.features:
                    if SensorAttrsEnum.temperature in device.features:
                        try:
                            val = float(device.state)
                        except:
                            val = 0
                        features.append(self.get_state_value("temperature", "INTEGER", val))
        return features

    @staticmethod
    def get_state_value(name, data_type, value):
        r = {}
        if name == 'temperature':
            value = value * 10
        if data_type == 'BOOL':
            r = {'key': name, 'value': {'type': 'BOOL', 'bool_value': bool(value)}}
        if data_type == 'INTEGER':
            r = {'key': name, 'value': {'type': 'INTEGER', 'integer_value': int(value)}}
        if data_type == 'ENUM':
            r = {'key': name, 'value': {'type': 'ENUM', 'enum_value': value}}
        return r


    async def queue_processer(self):
        while True:
            if self.client is not None:
                break
            await asyncio.sleep(1)
        while True:
            data = await self.queue_read.get()
            match data["type"]:
                case "conf":
                    await self.send_config(self.get_salute_devices_list())
                case "status":
                    entity_id = data["data"]
                    await self.send_status(self.get_salute_states_list([entity_id]))
            self.queue_read.task_done()

    def load_categories(self):
        hds = {'content-type': 'application/json'}
        auth = (self.options['sd_mqtt_login'], self.options['sd_mqtt_password'])
        categories_url = f"{self.options['sd_http_api_endpoint']}/v1/mqtt-gate/categories"
        if not os.path.exists(self.categories_file):
            logging.info('Файл категорий отсутствует. Получаем...')
            categories = {}
            SD_Categories = requests.get(
                categories_url,
                headers=hds,
                auth=auth
            ).json()
            for id in SD_Categories['categories']:
                logging.debug('Получаем опции для котегории: %s', id)
                SD_Features = requests.get(
                    f"{categories_url}/{id}/features",
                    headers=hds,
                    auth=auth
                ).json()
                categories[id] = SD_Features['features']
            #   log(Categories)
            logging.info('Категории получены. Сохраняем в файл.')
            json_write('categories.json', categories)
        else:
            logging.info('Список категорий получен из файла: %s', self.categories_file)
            categories = json_read(self.categories_file)
        self.categories = categories
